import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location('prepare_release', TOOLS / 'aidd_prepare_release.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReleaseInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        for root in ('skill', 'adapters/dot-aidd'):
            (self.repo / root / 'scripts').mkdir(parents=True)
            (self.repo / root / 'scripts' / 'example.py').write_text('old', encoding='utf-8')
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        subprocess.run(['git', 'add', '.'], cwd=self.repo, check=True)
        subprocess.run(['git', '-c', 'user.name=test', '-c', 'user.email=test@example.invalid',
                        'commit', '-qm', 'base'], cwd=self.repo, check=True)

    def test_tracks_changes_and_new_mirrored_files_without_missing_one_side(self):
        left = self.repo / 'skill' / 'scripts' / 'example.py'
        right = self.repo / 'adapters' / 'dot-aidd' / 'scripts' / 'example.py'
        left.write_text('new', encoding='utf-8')
        with self.assertRaises(ValueError):
            module.inventory(self.repo, 'HEAD')
        right.write_text('new', encoding='utf-8')
        for root in ('skill', 'adapters/dot-aidd'):
            (self.repo / root / 'scripts' / 'aidd_unit_consent.py').write_text('new', encoding='utf-8')
        skill, adapter = module.inventory(self.repo, 'HEAD')
        self.assertEqual(skill, ['scripts/aidd_unit_consent.py', 'scripts/example.py'])
        self.assertEqual(adapter, skill)

    def test_refuses_unlisted_distributed_file_and_runtime_mismatch(self):
        (self.repo / 'skill' / 'templates').mkdir()
        (self.repo / 'skill' / 'templates' / 'unsupported.html').write_text('x', encoding='utf-8')
        with self.assertRaises(ValueError):
            module.inventory(self.repo, 'HEAD')
        with patch.object(module.os.path, 'samefile', return_value=False):
            with self.assertRaises(ValueError):
                module.prepare(self.repo, self.repo, [self.repo], None, self.repo / 'stage',
                               'HEAD', Path(sys.executable), 'none')
        self.assertFalse((self.repo / 'stage').exists())

    def test_unicode_inventory_and_unsupported_package_change(self):
        for root in ('skill', 'adapters/dot-aidd'):
            (self.repo / root / 'scripts' / 'módulo.py').write_text('x', encoding='utf-8')
        skill, adapter = module.inventory(self.repo, 'HEAD')
        self.assertIn('scripts/módulo.py', skill)
        self.assertEqual(skill, adapter)
        (self.repo / 'aidd').mkdir()
        (self.repo / 'aidd' / '__init__.py').write_text('x', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'unsupported changed package'):
            module.inventory(self.repo, 'HEAD')

    def test_rename_does_not_hide_removed_distributed_file(self):
        source = self.repo / 'skill' / 'scripts' / 'example.py'
        source.rename(source.with_name('renamed.py'))
        subprocess.run(['git', 'add', '-A'], cwd=self.repo, check=True)
        with self.assertRaisesRegex(ValueError, 'does not delete distributed files'):
            module.inventory(self.repo, 'HEAD')

    def test_skill_three_way_merge_and_conflict(self):
        source = self.repo / 'source.md'
        current_dir = self.repo / 'profile'
        current_dir.mkdir()
        current = current_dir / 'SKILL.md'
        baseline = self.repo / 'base.md'
        baseline.write_text('one\ntwo\nthree\n', encoding='utf-8')
        current.write_text('one\ntwo\nlocal\n', encoding='utf-8')
        source.write_text('upstream\ntwo\nthree\n', encoding='utf-8')
        plan = module._stage_profile_skill(source, current, baseline, self.repo / 'stage')
        self.assertEqual((Path(plan['source']) / 'SKILL.md').read_text(), 'upstream\ntwo\nlocal\n')
        self.assertEqual(current.read_text(), 'one\ntwo\nlocal\n')
        source.write_text('one\ntwo\nconflict\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            module._stage_profile_skill(source, current, baseline, self.repo / 'conflict')

    def test_hook_override_is_rejected(self):
        handler = {'type': 'command', 'command': module.updater._CODEX_SUBAGENT_COMMAND,
                   'commandWindows': 'other-command', 'timeout': 10}
        config = {'hooks': {'SubagentStart': [{'hooks': [handler]}]}}
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            module.updater.merge_codex_subagent_hooks(json.dumps(config).encode())

    def test_only_known_impact_insertion_conflict_is_resolved(self):
        prefix = b'## Verification and approval economy (user preference)\n\n'
        suffix = b'- Reuse valid execution evidence and preserve preferences.\n'
        conflict = (prefix + b'<<<<<<< local\n=======\n' + module._IMPACT_LINE
                    + b'\n>>>>>>> upstream\n' + suffix)
        resolved = module._resolve_impact_conflict(conflict, prefix + suffix,
                                                  prefix + module._IMPACT_LINE + b'\n' + suffix)
        self.assertEqual(resolved, prefix + module._IMPACT_LINE + b'\n' + suffix)
        with self.assertRaises(ValueError):
            module._resolve_impact_conflict(conflict.replace(b'=======\n', b'local edit\n=======\n'),
                                            prefix + suffix, module._IMPACT_LINE)
