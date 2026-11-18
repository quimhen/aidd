"""FR-374: actual temporary Git clean filter must not run during raw source hashing."""
import json
import os
import stat
import hashlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'scripts'))
import code_graph as cg
import aidd_graphs as graphs


@unittest.skipUnless(shutil.which('git'), 'git is required for the actual-filter regression')
class RawWorkingTreeHashes(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='aidd-raw-hash-')
        self.addCleanup(temporary.cleanup)
        self.scratch = Path(temporary.name).resolve()
        self.root = self.scratch / 'repo'
        self.root.mkdir()
        template = self.scratch / 'empty-template'
        template.mkdir()
        self.git('init', '-q', '--template=' + str(template))
        self.git('config', '--local', 'core.autocrlf', 'false')
        self.marker = self.scratch / 'clean-filter-ran.txt'
        script = self.scratch / 'constant_filter.py'
        script.write_text('import pathlib,sys\n'
                          f'pathlib.Path({str(self.marker)!r}).write_text("filter ran",encoding="utf-8")\n'
                          'sys.stdin.buffer.read()\n'
                          'sys.stdout.buffer.write(b"constant filtered content\\n")\n', encoding='utf-8')
        command = ' '.join(shlex.quote(value) for value in
                           [Path(sys.executable).as_posix(), '-I', script.as_posix()])
        self.git('config', '--local', 'filter.aiddconstant.clean', command)
        self.git('config', '--local', 'filter.aiddconstant.required', 'true')
        (self.root / '.gitattributes').write_text('src/*.py filter=aiddconstant\n', encoding='utf-8')
        (self.root / 'src').mkdir()
        self.source = self.root / 'src' / 'example.py'
        self.source.write_bytes(b'def old_function():\n    return 1\n')
        # Check attribute selection without invoking the filter as part of setup.
        self.assertIn('aiddconstant', self.git('check-attr', 'filter', '--', 'src/example.py').stdout.decode())
        self.assertFalse(self.marker.exists())

    def git(self, *args):
        result = subprocess.run(['git', *args], cwd=self.root, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return result

    def test_hashing_raw_worktree_never_executes_configured_clean_filter(self):
        result = cg.file_shas(self.root, ['src/example.py'])
        self.assertFalse(self.marker.exists(), 'hashing source executed a repository clean filter')
        data = self.source.read_bytes()
        expected = hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()
        self.assertEqual(result, {'src/example.py': expected})

    def test_constant_filter_cannot_hide_changed_bytes_or_preserve_parse_cache(self):
        first_hashes = cg.file_shas(self.root, ['src/example.py'])
        first_graph, first_stats, cache, _ = cg.build_with_cache(self.root, globs=['src/**'])
        self.assertEqual(first_stats['parsed'], 1)
        self.assertTrue(any(n['id'].endswith('::old_function') for n in first_graph['nodes']))
        self.source.write_bytes(b'def old_function():\n    return 1\n\ndef newly_added():\n    return 2\n')
        changed_hashes = cg.file_shas(self.root, ['src/example.py'])
        self.assertNotEqual(first_hashes, changed_hashes,
                            'constant clean-filter output hid different parsed working-tree bytes')
        second_graph, second_stats, next_cache, dirty = cg.build_with_cache(
            self.root, globs=['src/**'], cache=cache, lazy=True)
        self.assertTrue(dirty)
        self.assertEqual(second_stats['parsed'], 1)
        self.assertEqual(second_stats['reused'], 0)
        self.assertIsNotNone(second_graph)
        self.assertTrue(any(n['id'].endswith('::newly_added') for n in second_graph['nodes']))
        self.assertNotEqual(cache['files']['src/example.py']['sha'],
                            next_cache['files']['src/example.py']['sha'])
        self.assertFalse(self.marker.exists(), 'cache/freshness hashing executed a clean filter')


    def test_legacy_filtered_hash_alias_does_not_reuse_old_ast(self):
        # Reproduce the legacy cache's exact hazardous state: AST from A, hash from B.
        # Only legacy cache construction mocks hashing; the migration call reads real B.
        source_b = b'def replacement_only():\n    return 42\n'
        hash_b = hashlib.sha1(b'blob ' + str(len(source_b)).encode('ascii') + b'\0' + source_b).hexdigest()
        with patch.object(cg, 'file_shas', return_value={'src/example.py': hash_b}):
            old_graph, old_stats, legacy, _ = cg.build_with_cache(self.root, globs=['src/**'])
        self.assertEqual(old_stats['parsed'], 1)
        self.assertTrue(any(n['id'].endswith('::old_function') for n in old_graph['nodes']))
        self.assertFalse(any(n['id'].endswith('::replacement_only') for n in old_graph['nodes']))
        self.assertEqual(legacy['files']['src/example.py']['sha'], hash_b)
        legacy['extractor'] = 3
        # A legacy clean filter can have produced B earlier; it need not remain selected now.
        (self.root / '.gitattributes').write_text('', encoding='utf-8')
        self.source.write_bytes(source_b)
        self.assertEqual(cg.file_shas(self.root, ['src/example.py']), {'src/example.py': hash_b})
        graph, stats, current, dirty = cg.build_with_cache(
            self.root, globs=['src/**'], cache=legacy, lazy=True)
        self.assertIsNotNone(graph, 'legacy equal hash incorrectly skipped generation migration')
        self.assertEqual((stats['parsed'], stats['reused']), (1, 0))
        self.assertTrue(dirty)
        self.assertEqual(current['schema'], 1)
        self.assertEqual(current['extractor'], 4)
        self.assertTrue(any(n['id'].endswith('::replacement_only') for n in graph['nodes']))
        self.assertFalse(any(n['id'].endswith('::old_function') for n in graph['nodes']))
        unchanged, later_stats, later_cache, later_dirty = cg.build_with_cache(
            self.root, globs=['src/**'], cache=current, lazy=True)
        self.assertIsNone(unchanged)
        self.assertEqual((later_stats['parsed'], later_stats['reused']), (0, 1))
        self.assertFalse(later_dirty)
        self.assertEqual(later_cache['extractor'], 4)
        self.assertFalse(self.marker.exists())

    def test_builtin_code_generation_invalidates_legacy_freshness_stamp(self):
        # Consumer watches src only; installed producer lives outside this root/watch.
        # Freeze one source hash so a producer-only change must invalidate old freshness.
        rel = 'src/example.py'
        blob = self.source.read_bytes()
        blob_sha = hashlib.sha1(b'blob ' + str(len(blob)).encode('ascii') + b'\0' + blob).hexdigest()
        old_aggregate = hashlib.sha256((rel + '\0' + blob_sha + '\n').encode()).hexdigest()
        output = self.root / 'consumer-code.json'
        output.write_text('{"nodes":[],"edges":[]}', encoding='utf-8')
        builtin = {'name': 'code', 'kind': 'code', 'output': str(output),
                   'refresh': 'builtin:code', 'watch': ['src/**']}
        external = dict(builtin, name='custom', refresh='python custom_provider.py')
        sql = dict(builtin, name='db', kind='db', refresh='builtin:sql')
        self.assertNotIn(Path(cg.__file__).resolve(), [self.source.resolve()])
        self.assertFalse(Path(cg.__file__).resolve().is_relative_to(self.root.resolve()))
        producer3 = SimpleNamespace(SCHEMA_VERSION=1, EXTRACTOR_VERSION=3)
        producer4 = SimpleNamespace(SCHEMA_VERSION=1, EXTRACTOR_VERSION=4)
        with patch.object(graphs, '_watched_files', return_value=[rel]), \
             patch.object(graphs, '_file_shas', return_value={rel: blob_sha}), \
             patch.object(graphs, '_module', return_value=producer4):
            hashes = graphs._inputs_hashes(self.root, [builtin, external, sql])
            self.assertIn('code', hashes)
            self.assertNotEqual(hashes['code'][0], old_aggregate)
            self.assertEqual(hashes['code'][1], 1)
            self.assertEqual(hashes['custom'], (old_aggregate, 1))
            self.assertEqual(hashes['db'], (old_aggregate, 1))
            with patch.object(graphs, 'load_registry', return_value=[builtin]), \
                 patch.object(graphs, '_read_stamp', return_value={'inputs_hash': old_aggregate}), \
                 patch.object(graphs, '_newest_watched', return_value=None), \
                 patch.object(graphs, '_lock_live', return_value=False), \
                 patch.object(graphs, 'refresh') as refresh:
                self.assertEqual(graphs.status(self.root, names=['code'])[0]['state'], 'stale')
            refresh.assert_not_called()
            with patch.object(graphs, '_module', return_value=producer3):
                previous_generation = graphs._inputs_hashes(self.root, [builtin])
            self.assertNotEqual(previous_generation['code'][0], hashes['code'][0])
            for missing in (None, SimpleNamespace(), SimpleNamespace(SCHEMA_VERSION=1, EXTRACTOR_VERSION=0)):
                with self.subTest(producer=missing), patch.object(graphs, '_module', return_value=missing):
                    unknown = graphs._inputs_hashes(self.root, [builtin, external])
                    self.assertNotIn('code', unknown)
                    self.assertEqual(unknown['custom'], (old_aggregate, 1))
                    with patch.object(graphs, 'load_registry', return_value=[builtin]), \
                         patch.object(graphs, '_read_stamp', return_value={'inputs_hash': old_aggregate}), \
                         patch.object(graphs, '_newest_watched', return_value=None), \
                         patch.object(graphs, '_lock_live', return_value=False):
                        self.assertEqual(graphs.status(self.root, names=['code'])[0]['state'], 'stale')
        self.assertFalse(self.marker.exists())


@unittest.skipUnless(shutil.which('git'), 'actual fsmonitor regression requires Git')
class RepositoryFsmonitorBoundary(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='aidd-fsmonitor-boundary-')
        self.addCleanup(temporary.cleanup)
        self.scratch = Path(temporary.name).resolve()
        self.root = self.scratch / 'consumer'
        self.root.mkdir()
        template = self.scratch / 'empty-template'
        template.mkdir()
        self.git('init', '-q', '--template=' + str(template))
        self.git('config', '--local', 'core.autocrlf', 'false')
        (self.root / 'src').mkdir()
        (self.root / 'src' / 'example.py').write_text('def retained():\n    return 1\n', encoding='utf-8')
        # Build a real index without inheriting any configured fsmonitor behavior.
        self.git('-c', 'core.fsmonitor=false', 'add', '--', 'src/example.py')
        self.marker = self.scratch / 'fsmonitor-executed.txt'
        hook = self.scratch / 'fsmonitor-fixture.sh'
        hook.write_text('#!/bin/sh\n'
                        'printf "executed\\n" >> ' + shlex.quote(self.marker.as_posix()) + '\n'
                        "printf 'fixture-token\\000/\\000'\n", encoding='utf-8', newline='\n')
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.git('config', '--local', 'core.fsmonitor', hook.as_posix())
        self.git('config', '--local', 'core.fsmonitorHookVersion', '2')
        # Positive control uses the exact unprotected inventory argv, real Git and hook.
        baseline = self.git('ls-files', '-c', '-o', '--exclude-standard', '-z')
        self.assertIn(b'src/example.py', baseline.stdout)
        self.assertTrue(self.marker.is_file(), 'fixture did not exercise an executable fsmonitor hook')
        self.assertIn('executed', self.marker.read_text(encoding='utf-8'))
        self.marker.unlink()

    def git(self, *args):
        env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', LC_ALL='C')
        result = subprocess.run(['git', *args], cwd=self.root, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return result

    def test_code_graph_inventory_does_not_execute_repository_fsmonitor(self):
        # Retain actual subprocess execution; mocking _git would miss the reported path.
        files = cg.list_files(self.root, ['src/**'])
        self.assertEqual(files, ['src/example.py'])
        self.assertFalse(self.marker.exists(), 'code inventory executed repository core.fsmonitor')

    def test_graph_status_inventory_does_not_execute_repository_fsmonitor(self):
        output = self.root / 'method-graph.json'
        output.write_text(json.dumps({'nodes': [], 'edges': []}), encoding='utf-8')
        entry = {'name': 'method', 'kind': 'method', 'output': str(output),
                 'refresh': 'builtin:method', 'watch': ['src/**']}
        # This registry route uses aidd_graphs._ls_files rather than cg.list_files.
        # Only the registry is controlled; status/hash/list/Git remain real. No refresh runs.
        with patch.object(graphs, 'load_registry', return_value=[entry]), \
             patch.object(graphs, 'refresh') as refresh:
            rows = graphs.status(self.root, names=['method'])
        refresh.assert_not_called()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['state'], 'stale')
        self.assertEqual(rows[0]['inputs'], 1)
        self.assertFalse(self.marker.exists(), 'graph status inventory executed repository core.fsmonitor')


if __name__ == '__main__':
    unittest.main()
