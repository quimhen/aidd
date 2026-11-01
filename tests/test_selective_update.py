import importlib.util
import csv
import io
import json
import os
import py_compile
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    'selective_update', Path(__file__).resolve().parents[1] / 'tools' / 'aidd_selective_update.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SelectiveUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'source'
        self.target = self.base / 'target'
        self.baseline = self.base / 'baseline'
        for directory in (self.source, self.target, self.baseline):
            (directory / 'scripts').mkdir(parents=True)
            (directory / 'hooks').mkdir()
            (directory / 'templates').mkdir()
        (self.source / 'scripts' / 'x.py').write_bytes(b'new')
        (self.target / 'scripts' / 'x.py').write_bytes(b'old')
        (self.baseline / 'scripts' / 'x.py').write_bytes(b'old')
        (self.target / 'evidence.jsonl').write_bytes(b'keep')

    def test_plan_is_read_only_apply_only_selected_and_detects_drift(self):
        plan = module.make_plan(self.source, self.target, ['scripts/x.py'], self.baseline)
        self.assertEqual((self.target / 'scripts' / 'x.py').read_bytes(), b'old')
        self.assertEqual(module.apply_plan(plan, self.base / 'journal'), 1)
        self.assertEqual((self.target / 'scripts' / 'x.py').read_bytes(), b'new')
        self.assertEqual((self.target / 'evidence.jsonl').read_bytes(), b'keep')
        with self.assertRaises(ValueError):
            module.apply_plan(plan, self.base / 'second-journal')

    def test_missing_target_can_be_created_and_source_change_fails(self):
        (self.source / 'hooks' / 'x.py').write_bytes(b'code')
        plan = module.make_plan(self.source, self.target, ['hooks/x.py'])
        (self.source / 'hooks' / 'x.py').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            module.apply_plan(plan, self.base / 'journal')
        self.assertFalse((self.target / 'hooks' / 'x.py').exists())

    def test_refuses_duplicates_traversal_protected_and_symlink(self):
        for names in (['../x.py'], ['/absolute/x.py'], ['scripts/a.py:stream.py'], ['SKILL.md'], ['scripts/x.py', 'scripts/x.py']):
            with self.subTest(names=names), self.assertRaises(ValueError):
                module.make_plan(self.source, self.target, names)
        link = self.target / 'hooks' / 'link.py'
        try:
            link.symlink_to(self.target / 'scripts' / 'x.py')
        except OSError:
            return
        (self.source / 'hooks' / 'link.py').write_bytes(b'code')
        with self.assertRaises(ValueError):
            module.make_plan(self.source, self.target, ['hooks/link.py'])

    def test_tampered_plan_rejected_before_any_write(self):
        plan = module.make_plan(self.source, self.target, ['scripts/x.py'], self.baseline)
        plan['files'][0]['path'] = '../evidence.jsonl'
        with self.assertRaises(ValueError):
            module.apply_plan(plan, self.base / 'journal')
        self.assertEqual((self.target / 'scripts' / 'x.py').read_bytes(), b'old')

    def test_personalized_file_never_overwritten(self):
        (self.target / 'scripts' / 'x.py').write_bytes(b'custom')
        with self.assertRaises(ValueError):
            module.make_plan(self.source, self.target, ['scripts/x.py'], self.baseline)
        with self.assertRaises(ValueError):
            module.make_plan(self.source, self.target, ['scripts/x.py'])
        self.assertEqual((self.target / 'scripts' / 'x.py').read_bytes(), b'custom')

    def test_changed_baseline_rejects_plan_before_any_replacement(self):
        plan = module.make_plan(self.source, self.target, ['scripts/x.py'], self.baseline)
        (self.baseline / 'scripts' / 'x.py').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            module.apply_plan(plan, self.base / 'journal')
        self.assertEqual((self.target / 'scripts' / 'x.py').read_bytes(), b'old')

    def test_identical_file_is_not_replaced(self):
        (self.target / 'scripts' / 'x.py').write_bytes(b'new')
        plan = module.make_plan(self.source, self.target, ['scripts/x.py'])
        journal = self.base / 'journal'
        self.assertEqual(module.apply_plan(plan, journal), 0)
        self.assertFalse(journal.exists())

    def test_recovery_removes_only_new_file_from_interrupted_transaction(self):
        (self.source / 'hooks' / 'x.py').write_bytes(b'created')
        plan = module.make_plan(self.source, self.target, ['hooks/x.py', 'scripts/x.py'], self.baseline)
        original = module._replace_file
        def interrupt(src, dst, security, expected):
            if Path(dst) == self.target / 'scripts' / 'x.py':
                raise KeyboardInterrupt()
            return original(src, dst, security, expected)
        with patch.object(module, '_replace_file', side_effect=interrupt), self.assertRaises(KeyboardInterrupt):
            module.apply_plan(plan, self.base / 'journal')
        self.assertEqual((self.target / 'hooks' / 'x.py').read_bytes(), b'created')
        module.recover_transaction(self.base / 'journal')
        self.assertFalse((self.target / 'hooks' / 'x.py').exists())
        self.assertEqual((self.target / 'scripts' / 'x.py').read_bytes(), b'old')

    def test_customized_skill_is_preserved(self):
        (self.source / 'SKILL.md').write_bytes(b'new')
        (self.target / 'SKILL.md').write_bytes(b'personal')
        (self.baseline / 'SKILL.md').write_bytes(b'old')
        with self.assertRaises(ValueError):
            module.make_plan(self.source, self.target, ['SKILL.md'], self.baseline)
        self.assertEqual((self.target / 'SKILL.md').read_bytes(), b'personal')

    def test_installs_navigator_and_only_explicit_template(self):
        (self.source / 'scripts' / 'aidd_navigator.py').write_bytes(b'navigator')
        (self.source / 'templates' / 'navigator.html').write_bytes(b'<html></html>')
        (self.source / 'templates' / 'other.html').write_bytes(b'other')
        with self.assertRaises(ValueError):
            module.make_plan(self.source, self.target, ['templates/other.html'])
        plan = module.make_plan(self.source, self.target,
                                ['scripts/aidd_navigator.py', 'templates/navigator.html'])
        self.assertEqual(module.apply_plan(plan, self.base / 'journal'), 2)
        self.assertEqual((self.target / 'scripts' / 'aidd_navigator.py').read_bytes(), b'navigator')
        self.assertEqual((self.target / 'templates' / 'navigator.html').read_bytes(), b'<html></html>')
        self.assertFalse((self.target / 'templates' / 'other.html').exists())

    def test_update_package_record_only_changes_selected_rows(self):
        original = b'aidd/cli.py,sha256=old,3\r\nother/file.py,sha256=keep,4\r\n'
        updated = module.update_package_record(original, {'aidd/cli.py': b'new',
            'aidd/_data/skill/templates/navigator.html': b'<html>'})
        rows = list(csv.reader(io.StringIO(updated.decode('utf-8'), newline='')))
        self.assertEqual(rows[1], ['other/file.py', 'sha256=keep', '4'])
        self.assertEqual(rows[0][2], '3')
        self.assertTrue(rows[0][1].startswith('sha256='))
        self.assertEqual(rows[2][0], 'aidd/_data/skill/templates/navigator.html')
        with self.assertRaises(ValueError):
            module.update_package_record(original, {'../unrelated': b'bad'})
        with self.assertRaises(ValueError):
            module.update_package_record(b'aidd/cli.py,,\naidd/cli.py,,\n', {'aidd/cli.py': b'new'})

    def test_cli_and_record_update_together_and_roll_back(self):
        installed = self.base / 'site-packages' / 'aidd'
        metadata = self.base / 'site-packages' / 'aidd_cli-0.2.0.dist-info'
        installed.mkdir(parents=True)
        metadata.mkdir()
        wrapper = self.base / 'aidd.exe'
        wrapper.write_bytes(b'keep-launcher')
        (installed / 'cli.py').write_bytes(b'old')
        (self.source / 'cli.py').write_bytes(b'new')
        (self.baseline / 'cli.py').write_bytes(b'old')
        old_record = module.update_package_record(
            b'other/file.py,sha256=keep,4\naidd_cli-0.2.0.dist-info/RECORD,,\n', {'aidd/cli.py': b'old'})
        (metadata / 'RECORD').write_bytes(old_record)
        (self.baseline / 'RECORD').write_bytes(old_record)
        (self.source / 'RECORD').write_bytes(module.update_package_record(old_record, {'aidd/cli.py': b'new'}))
        plans = [module.make_plan(self.source, installed, ['cli.py'], self.baseline, bind_runtime=True),
                 module.make_plan(self.source, metadata, ['RECORD'], self.baseline, bind_runtime=True)]
        module.apply_transaction(plans, self.base / 'package-journal')
        self.assertEqual((installed / 'cli.py').read_bytes(), b'new')
        self.assertEqual((metadata / 'RECORD').read_bytes(), (self.source / 'RECORD').read_bytes())
        self.assertEqual(wrapper.read_bytes(), b'keep-launcher')
        module.recover_transaction(self.base / 'package-journal')
        self.assertEqual((installed / 'cli.py').read_bytes(), b'old')
        self.assertEqual((metadata / 'RECORD').read_bytes(), old_record)
        self.assertEqual(wrapper.read_bytes(), b'keep-launcher')

    def _package_fixture(self):
        package = self.base / 'site-packages' / 'aidd'
        metadata = package.parent / 'aidd_cli-0.2.0.dist-info'
        (package / '_data' / 'skill' / 'scripts').mkdir(parents=True)
        (package / '_data' / 'adapters' / 'dot-aidd' / 'templates').mkdir(parents=True)
        metadata.mkdir()
        (package / 'cli.py').write_bytes(b'old-cli')
        (package / '_data' / 'skill' / 'scripts' / 'x.py').write_bytes(b'old')
        (package / '_data' / 'skill' / 'scripts' / 'personal.py').write_bytes(b'keep')
        (self.source / 'cli.py').write_bytes(b'new-cli')
        (self.baseline / 'cli.py').write_bytes(b'old-cli')
        (self.source / 'templates' / 'navigator.html').write_bytes(b'<html>new</html>')
        original = module.update_package_record(b'unrelated.py,sha256=keep,4\naidd_cli-0.2.0.dist-info/RECORD,,\n', {
            'aidd/cli.py': b'old-cli', 'aidd/_data/skill/scripts/x.py': b'old'})
        (metadata / 'RECORD').write_bytes(original)
        return package, metadata, original

    def test_package_staging_cli_and_resources_transaction(self):
        package, metadata, original = self._package_fixture()
        wrapper = self.base / 'aidd.exe'
        wrapper.write_bytes(b'keep-launcher')
        stage = self.base / 'stage'
        rc = module.main(['package-plan', '--package-root', str(package), '--dist-info', str(metadata),
            '--stage', str(stage), '--cli', '--source-package', str(self.source),
            '--baseline-package', str(self.baseline), '--source-skill', str(self.source),
            '--baseline-skill', str(self.baseline), '--skill-file', 'scripts/x.py',
            '--source-adapter', str(self.source), '--adapter-file', 'templates/navigator.html'])
        self.assertEqual(rc, 0)
        self.assertEqual((package / 'cli.py').read_bytes(), b'old-cli')
        self.assertEqual((metadata / 'RECORD').read_bytes(), original)
        self.assertEqual(module.main(['apply', '--plan', str(stage / 'package-plans.json'),
                                      '--journal', str(self.base / 'journal')]), 0)
        self.assertEqual((package / 'cli.py').read_bytes(), b'new-cli')
        self.assertEqual((package / '_data' / 'skill' / 'scripts' / 'x.py').read_bytes(), b'new')
        self.assertEqual((package / '_data' / 'adapters' / 'dot-aidd' / 'templates' / 'navigator.html').read_bytes(), b'<html>new</html>')
        self.assertEqual((package / '_data' / 'skill' / 'scripts' / 'personal.py').read_bytes(), b'keep')
        self.assertEqual(wrapper.read_bytes(), b'keep-launcher')
        rows = list(csv.reader(io.StringIO((metadata / 'RECORD').read_text(encoding='utf-8'))))
        self.assertIn('aidd/_data/adapters/dot-aidd/templates/navigator.html', [row[0] for row in rows])
        self.assertEqual(module.recover_transaction(self.base / 'journal'), 4)
        self.assertEqual((package / 'cli.py').read_bytes(), b'old-cli')
        self.assertEqual((metadata / 'RECORD').read_bytes(), original)
        self.assertFalse((package / '_data' / 'adapters' / 'dot-aidd' / 'templates' / 'navigator.html').exists())

    def test_package_staging_refuses_record_mismatch_without_install(self):
        package, metadata, _ = self._package_fixture()
        (package / 'cli.py').write_bytes(b'local change')
        stage = self.base / 'stage'
        with self.assertRaises(ValueError):
            module.prepare_package_plan(package, metadata, self.source, self.baseline,
                None, None, None, None, stage, include_cli=True)
        self.assertFalse(stage.exists())
        self.assertEqual((package / 'cli.py').read_bytes(), b'local change')

    def test_cli_update_requires_matching_record_in_same_transaction(self):
        package, metadata, original = self._package_fixture()
        cli = module.make_plan(self.source, package, ['cli.py'], self.baseline, bind_runtime=True)
        with self.assertRaises(ValueError):
            module.apply_plan(cli, self.base / 'no-record')
        # This intentionally wrong RECORD changes an unrelated row only.
        (self.source / 'RECORD').write_bytes(original.replace(b'unrelated.py', b'changed.py'))
        (self.baseline / 'RECORD').write_bytes(original)
        record = module.make_plan(self.source, metadata, ['RECORD'], self.baseline, bind_runtime=True)
        with self.assertRaises(ValueError):
            module.apply_transaction([cli, record], self.base / 'wrong-record')
        self.assertEqual((package / 'cli.py').read_bytes(), b'old-cli')
        self.assertEqual((metadata / 'RECORD').read_bytes(), original)

    def test_package_staging_refuses_stage_inside_installed_package(self):
        package, metadata, _ = self._package_fixture()
        stage = package / 'stage'
        with self.assertRaises(ValueError):
            module.prepare_package_plan(package, metadata, self.source, self.baseline,
                None, None, None, None, stage, include_cli=True)
        self.assertFalse(stage.exists())

    def test_record_must_preserve_unselected_and_cannot_update_alone(self):
        package, metadata, original = self._package_fixture()
        cli = module.make_plan(self.source, package, ['cli.py'], self.baseline, bind_runtime=True)
        (self.baseline / 'RECORD').write_bytes(original)
        malicious = module.update_package_record(
            b'aidd_cli-0.2.0.dist-info/RECORD,,\n', {'aidd/cli.py': b'new-cli'})
        (self.source / 'RECORD').write_bytes(malicious)
        record = module.make_plan(self.source, metadata, ['RECORD'], self.baseline, bind_runtime=True)
        with self.assertRaises(ValueError):
            module.apply_transaction([cli, record], self.base / 'removed-row-journal')
        with self.assertRaises(ValueError):
            module.apply_plan(record, self.base / 'record-only-journal')
        self.assertEqual((package / 'cli.py').read_bytes(), b'old-cli')
        self.assertEqual((metadata / 'RECORD').read_bytes(), original)

    def test_package_staging_rejects_ambiguous_distributions(self):
        package, metadata, _ = self._package_fixture()
        (package.parent / 'aidd_cli-0.1.0.dist-info').mkdir()
        with self.assertRaises(ValueError):
            module.prepare_package_plan(package, metadata, self.source, self.baseline,
                None, None, None, None, self.base / 'stage', include_cli=True)
        self.assertFalse((self.base / 'stage').exists())

    def test_codex_lifecycle_merge_preserves_existing_and_is_idempotent(self):
        original = {'description': 'keep', 'hooks': {'PreToolUse': [{'hooks': [{'type': 'command', 'command': 'other'}]}],
            'SubagentStop': [{'matcher': 'auditor', 'hooks': [{'type': 'command', 'command': 'existing'}]}]}}
        data = json.dumps(original).encode('utf-8')
        updated = module.merge_codex_subagent_hooks(data)
        merged = json.loads(updated)
        self.assertEqual(merged['description'], original['description'])
        self.assertEqual(merged['hooks']['PreToolUse'], original['hooks']['PreToolUse'])
        self.assertEqual(merged['hooks']['SubagentStop'][0], original['hooks']['SubagentStop'][0])
        for event in ('SubagentStart', 'SubagentStop'):
            matches = [handler for group in merged['hooks'][event] for handler in group['hooks']
                       if handler.get('command') == module._CODEX_SUBAGENT_COMMAND]
            self.assertEqual(len(matches), 1)
        self.assertEqual(module.merge_codex_subagent_hooks(updated), updated)

    def test_codex_lifecycle_conflict_and_duplicate_json_are_refused(self):
        conflict = {'hooks': {'SubagentStart': [{'hooks': [{'type': 'command', 'command': 'other/codex_subagent.py'}]}]}}
        with self.assertRaises(ValueError):
            module.merge_codex_subagent_hooks(json.dumps(conflict).encode('utf-8'))
        with self.assertRaises(ValueError):
            module.merge_codex_subagent_hooks(b'{"hooks":{},"hooks":{}}')

    def test_codex_hooks_stage_apply_and_rollback_do_not_touch_trust(self):
        codex = self.base / '.codex'
        codex.mkdir()
        hooks = codex / 'hooks.json'
        original = b'{"hooks":{"SessionStart":[]},"custom":true}\n'
        hooks.write_bytes(original)
        trust = codex / 'config.toml'
        trust.write_bytes(b'[hooks.state]\nunchanged = true\n')
        stage = self.base / 'hooks-stage'
        plan = module.prepare_codex_hooks_plan(codex, stage)
        self.assertEqual(hooks.read_bytes(), original)
        module.apply_plan(plan, self.base / 'hooks-journal')
        self.assertIn('SubagentStart', json.loads(hooks.read_bytes())['hooks'])
        self.assertEqual(trust.read_bytes(), b'[hooks.state]\nunchanged = true\n')
        module.recover_transaction(self.base / 'hooks-journal')
        self.assertEqual(hooks.read_bytes(), original)
        self.assertEqual(trust.read_bytes(), b'[hooks.state]\nunchanged = true\n')

    def test_multitarget_failure_rolls_back_all(self):
        other = self.base / 'other'
        (other / 'scripts').mkdir(parents=True)
        (other / 'scripts' / 'x.py').write_bytes(b'old')
        plans = [module.make_plan(self.source, self.target, ['scripts/x.py'], self.baseline),
                 module.make_plan(self.source, other, ['scripts/x.py'], self.baseline)]
        original = module._replace_file
        def fail_second(src, dst, security, expected):
            if Path(dst) == other / 'scripts' / 'x.py':
                raise OSError('injected replacement failure')
            return original(src, dst, security, expected)
        with patch.object(module, '_replace_file', side_effect=fail_second), self.assertRaises(OSError):
            module.apply_transaction(plans, self.base / 'journal')
        self.assertEqual((self.target / 'scripts' / 'x.py').read_bytes(), b'old')
        self.assertEqual((other / 'scripts' / 'x.py').read_bytes(), b'old')

    def test_interrupted_transaction_can_recover_without_clobbering_edits(self):
        other = self.base / 'other'
        (other / 'scripts').mkdir(parents=True)
        (other / 'scripts' / 'x.py').write_bytes(b'old')
        plans = [module.make_plan(self.source, self.target, ['scripts/x.py'], self.baseline),
                 module.make_plan(self.source, other, ['scripts/x.py'], self.baseline)]
        original = module._replace_file
        def interrupt(src, dst, security, expected):
            if Path(dst) == other / 'scripts' / 'x.py':
                raise KeyboardInterrupt()
            return original(src, dst, security, expected)
        with patch.object(module, '_replace_file', side_effect=interrupt), self.assertRaises(KeyboardInterrupt):
            module.apply_transaction(plans, self.base / 'journal')
        self.assertEqual((self.target / 'scripts' / 'x.py').read_bytes(), b'new')
        (self.target / 'scripts' / 'x.py').write_bytes(b'user edit')
        with self.assertRaises(ValueError):
            module.recover_transaction(self.base / 'journal')
        self.assertEqual((self.target / 'scripts' / 'x.py').read_bytes(), b'user edit')
        (self.target / 'scripts' / 'x.py').write_bytes(b'new')
        module.recover_transaction(self.base / 'journal')
        self.assertEqual((self.target / 'scripts' / 'x.py').read_bytes(), b'old')

    def test_refuses_journal_resolving_inside_target(self):
        (self.base / 'outside').mkdir()
        plan = module.make_plan(self.source, self.target, ['scripts/x.py'], self.baseline)
        journal = self.base / 'outside' / '..' / 'target' / 'journal'
        with self.assertRaises(ValueError):
            module.apply_plan(plan, journal)
        self.assertFalse((self.target / 'journal').exists())

    def test_refuses_all_reparse_point_attributes(self):
        path = self.target / 'scripts' / 'x.py'
        original = Path.lstat
        def flagged(item, *args, **kwargs):
            if item == path:
                return types.SimpleNamespace(st_mode=0o100600, st_reparse_tag=0, st_file_attributes=0x400)
            return original(item, *args, **kwargs)
        with patch.object(Path, 'lstat', flagged), self.assertRaises(ValueError):
            module.make_plan(self.source, self.target, ['scripts/x.py'], self.baseline)

    def test_hardlink_rejected_during_plan_apply_and_recovery(self):
        path = self.target / 'scripts' / 'x.py'
        alias = self.base / 'alias'
        try:
            os.link(path, alias)
        except OSError as exc:
            self.skipTest(f'hardlinks unavailable: {exc}')
        with self.assertRaises(ValueError):
            module.make_plan(self.source, self.target, ['scripts/x.py'], self.baseline)
        alias.unlink()
        plan = module.make_plan(self.source, self.target, ['scripts/x.py'], self.baseline)
        os.link(path, alias)
        with self.assertRaises(ValueError):
            module.apply_plan(plan, self.base / 'unapplied')
        alias.unlink()
        module.apply_plan(plan, self.base / 'journal')
        os.link(path, alias)
        with self.assertRaises(ValueError):
            module.recover_transaction(self.base / 'journal')
        self.assertEqual(path.read_bytes(), b'new')
        alias.unlink()

    def test_detects_write_during_replacement_and_keeps_backup(self):
        path = self.target / 'scripts' / 'x.py'
        plan = module.make_plan(self.source, self.target, ['scripts/x.py'], self.baseline)
        original = module.tempfile.mkstemp
        def concurrent(*args, **kwargs):
            result = original(*args, **kwargs)
            if Path(kwargs['dir']) == path.parent:
                path.write_bytes(b'concurrent edit')
            return result
        with patch.object(module.tempfile, 'mkstemp', side_effect=concurrent), self.assertRaises(RuntimeError):
            module.apply_plan(plan, self.base / 'journal')
        self.assertEqual(path.read_bytes(), b'concurrent edit')
        self.assertEqual((self.base / 'journal' / '000000.bak').read_bytes(), b'old')

    def test_detects_write_during_recovery_and_keeps_backup(self):
        path = self.target / 'scripts' / 'x.py'
        plan = module.make_plan(self.source, self.target, ['scripts/x.py'], self.baseline)
        module.apply_plan(plan, self.base / 'journal')
        original = module.tempfile.mkstemp
        def concurrent(*args, **kwargs):
            result = original(*args, **kwargs)
            if Path(kwargs['dir']) == path.parent:
                path.write_bytes(b'concurrent edit')
            return result
        with patch.object(module.tempfile, 'mkstemp', side_effect=concurrent), self.assertRaises(ValueError):
            module.recover_transaction(self.base / 'journal')
        self.assertEqual(path.read_bytes(), b'concurrent edit')
        self.assertEqual((self.base / 'journal' / '000000.bak').read_bytes(), b'old')

    def test_new_file_creation_does_not_overwrite_concurrent_creator(self):
        path = self.target / 'hooks' / 'x.py'
        (self.source / 'hooks' / 'x.py').write_bytes(b'new')
        plan = module.make_plan(self.source, self.target, ['hooks/x.py'])
        original = module._move_new_no_replace
        def concurrent(src, dst):
            if Path(dst) == path:
                path.write_bytes(b'concurrent creation')
            return original(src, dst)
        with patch.object(module, '_move_new_no_replace', side_effect=concurrent), self.assertRaises(RuntimeError):
            module.apply_plan(plan, self.base / 'journal')
        self.assertEqual(path.read_bytes(), b'concurrent creation')

    @unittest.skipUnless(os.name == 'nt', 'Windows security descriptor behavior')
    def test_new_file_acl_failure_after_creation_rolls_back(self):
        path = self.target / 'hooks' / 'x.py'
        (self.source / 'hooks' / 'x.py').write_bytes(b'new')
        plan = module.make_plan(self.source, self.target, ['hooks/x.py'])
        original = module._windows_security_descriptor
        injected = False
        def fail_once(item):
            nonlocal injected
            if Path(item) == path and path.exists() and not injected:
                injected = True
                raise OSError('injected ACL read failure')
            return original(item)
        with patch.object(module, '_windows_security_descriptor', side_effect=fail_once), self.assertRaises(OSError):
            module.apply_plan(plan, self.base / 'journal')
        self.assertTrue(injected)
        self.assertFalse(path.exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows security descriptor behavior')
    def test_new_file_interruption_before_acl_recheck_can_recover(self):
        path = self.target / 'hooks' / 'x.py'
        (self.source / 'hooks' / 'x.py').write_bytes(b'new')
        plan = module.make_plan(self.source, self.target, ['hooks/x.py'])
        original = module._atomic_write
        def interrupt(item, *args, **kwargs):
            result = original(item, *args, **kwargs)
            if Path(item) == path:
                raise KeyboardInterrupt()
            return result
        with patch.object(module, '_atomic_write', side_effect=interrupt), self.assertRaises(KeyboardInterrupt):
            module.apply_plan(plan, self.base / 'journal')
        self.assertEqual(path.read_bytes(), b'new')
        module.recover_transaction(self.base / 'journal')
        self.assertFalse(path.exists())

    def test_new_file_interruption_after_move_can_recover(self):
        path = self.target / 'hooks' / 'x.py'
        (self.source / 'hooks' / 'x.py').write_bytes(b'new')
        plan = module.make_plan(self.source, self.target, ['hooks/x.py'])
        original = module._move_new_no_replace
        def interrupt(src, dst):
            result = original(src, dst)
            if Path(dst) == path:
                raise KeyboardInterrupt()
            return result
        with patch.object(module, '_move_new_no_replace', side_effect=interrupt), self.assertRaises(KeyboardInterrupt):
            module.apply_plan(plan, self.base / 'journal')
        self.assertEqual(path.stat().st_nlink, 1)
        module.recover_transaction(self.base / 'journal')
        self.assertFalse(path.exists())

    def test_real_python_import_invalidates_same_second_bytecode_on_apply_and_recovery(self):
        path = self.target / 'scripts' / 'x.py'
        old, new = b'VALUE="old"\n', b'VALUE="new"\n'
        path.write_bytes(old)
        (self.source / 'scripts' / 'x.py').write_bytes(new)
        (self.baseline / 'scripts' / 'x.py').write_bytes(old)
        bytecode = Path(py_compile.compile(str(path), doraise=True,
            invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP))
        timestamp = int.from_bytes(bytecode.read_bytes()[8:12], 'little')
        plan = module.make_plan(self.source, self.target, ['scripts/x.py'], self.baseline)
        with patch.object(module.time, 'time', return_value=timestamp):
            module.apply_plan(plan, self.base / 'journal')
        code = 'import sys;sys.path.insert(0,sys.argv[1]);import x;print(x.VALUE)'
        result = subprocess.run([sys.executable, '-c', code, str(path.parent)], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), 'new')
        bytecode = Path(py_compile.compile(str(path), doraise=True,
            invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP))
        timestamp = int.from_bytes(bytecode.read_bytes()[8:12], 'little')
        with patch.object(module.time, 'time', return_value=timestamp):
            module.recover_transaction(self.base / 'journal')
        result = subprocess.run([sys.executable, '-c', code, str(path.parent)], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), 'old')

    def test_unchecked_hash_bytecode_blocks_replacement_without_deleting_it(self):
        path = self.target / 'scripts' / 'x.py'
        old, new = b'VALUE="old"\n', b'VALUE="new"\n'
        path.write_bytes(old)
        (self.source / 'scripts' / 'x.py').write_bytes(new)
        (self.baseline / 'scripts' / 'x.py').write_bytes(old)
        bytecode = Path(py_compile.compile(str(path), doraise=True,
            invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH))
        prior = bytecode.read_bytes()
        plan = module.make_plan(self.source, self.target, ['scripts/x.py'], self.baseline)
        with self.assertRaises(ValueError):
            module.apply_plan(plan, self.base / 'journal')
        self.assertEqual(path.read_bytes(), old)
        self.assertEqual(bytecode.read_bytes(), prior)

    def test_custom_python_cache_prefix_is_checked(self):
        path = self.target / 'scripts' / 'x.py'
        old, new = b'VALUE="old"\n', b'VALUE="new"\n'
        path.write_bytes(old)
        (self.source / 'scripts' / 'x.py').write_bytes(new)
        (self.baseline / 'scripts' / 'x.py').write_bytes(old)
        prefix = self.base / 'custom-bytecode'
        with patch.object(sys, 'pycache_prefix', str(prefix)):
            bytecode = Path(py_compile.compile(str(path), doraise=True,
                invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP))
            timestamp = int.from_bytes(bytecode.read_bytes()[8:12], 'little')
            plan = module.make_plan(self.source, self.target, ['scripts/x.py'], self.baseline)
            with patch.object(module.time, 'time', return_value=timestamp):
                module.apply_plan(plan, self.base / 'journal')
            env = os.environ.copy()
            env['PYTHONPYCACHEPREFIX'] = str(prefix)
            code = 'import sys;sys.path.insert(0,sys.argv[1]);import x;print(x.VALUE)'
            result = subprocess.run([sys.executable, '-c', code, str(path.parent)],
                                    capture_output=True, text=True, check=True, env=env)
            self.assertEqual(result.stdout.strip(), 'new')

    def test_bound_runtime_refuses_changed_prefix_before_apply_and_recovery(self):
        plan = module.make_plan(self.source, self.target, ['scripts/x.py'], self.baseline, bind_runtime=True)
        with patch.object(sys, 'pycache_prefix', str(self.base / 'different-prefix')):
            with self.assertRaises(ValueError):
                module.apply_plan(plan, self.base / 'invalid-journal')
        self.assertEqual((self.target / 'scripts' / 'x.py').read_bytes(), b'old')
        module.apply_plan(plan, self.base / 'journal')
        with patch.object(sys, 'pycache_prefix', str(self.base / 'different-prefix')):
            with self.assertRaises(ValueError):
                module.recover_transaction(self.base / 'journal')
        self.assertEqual((self.target / 'scripts' / 'x.py').read_bytes(), b'new')
        module.recover_transaction(self.base / 'journal')
        self.assertEqual((self.target / 'scripts' / 'x.py').read_bytes(), b'old')

    def test_installed_package_rejects_unbound_runtime(self):
        package, _, _ = self._package_fixture()
        plan = module.make_plan(self.source, package, ['cli.py'], self.baseline)
        with self.assertRaises(ValueError):
            module.apply_plan(plan, self.base / 'journal')
        self.assertEqual((package / 'cli.py').read_bytes(), b'old-cli')

    @unittest.skipUnless(os.name == 'nt', 'Windows security descriptor behavior')
    def test_acl_changed_after_backup_is_refused(self):
        path = self.target / 'scripts' / 'x.py'
        plan = module.make_plan(self.source, self.target, ['scripts/x.py'], self.baseline)
        original = module._windows_security_snapshot
        captures = 0
        def changed(item):
            nonlocal captures
            snap = original(item)
            if Path(item) == path:
                captures += 1
                if captures == 2:
                    return {**snap, 'sddl': snap['sddl'] + 'changed'}
            return snap
        with patch.object(module, '_windows_security_snapshot', side_effect=changed), self.assertRaises(ValueError):
            module.apply_plan(plan, self.base / 'journal')
        self.assertEqual(path.read_bytes(), b'old')

    @unittest.skipUnless(os.name == 'nt', 'Windows security descriptor behavior')
    def test_windows_security_descriptor_survives_apply_and_recovery(self):
        path = self.target / 'scripts' / 'x.py'
        try:
            before = module._windows_security_descriptor(path)
        except OSError:
            self.skipTest('audit ACL privilege unavailable; replacement must fail closed')
        plan = module.make_plan(self.source, self.target, ['scripts/x.py'], self.baseline)
        module.apply_plan(plan, self.base / 'journal')
        self.assertEqual(module._windows_security_descriptor(path), before)
        module.recover_transaction(self.base / 'journal')
        self.assertEqual(module._windows_security_descriptor(path), before)

    @unittest.skipUnless(os.name == 'nt', 'Windows security descriptor behavior')
    def test_windows_replacement_refused_if_security_unreadable(self):
        path = self.target / 'scripts' / 'x.py'
        before = module._digest(path)
        with patch.object(module, '_windows_security_snapshot', side_effect=OSError('denied')):
            with self.assertRaises(OSError):
                module._atomic_write(path, b'new', expected=before)
        self.assertEqual(path.read_bytes(), b'old')

    @unittest.skipIf(os.name == 'nt', 'portable directory fsync is unavailable on Windows')
    def test_directory_fsync_is_called_on_linux(self):
        with patch.object(module.os, 'fsync', wraps=module.os.fsync) as synced:
            self.assertTrue(module._fsync_dir(self.base))
        synced.assert_called_once()
