"""Portable path guard regressions for spec 009 T-18; no network shares are accessed."""
import os
import sys
from pathlib import Path
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_fixtures import Base, approved_tasks, spec_text, tasks_text
from test_rule_gate_shell_speed import load_old_guard, make_link
from report_guard_portability import collect_cases
import rule_gate


class TestPortablePaths(Base):
    def decide(self, path, cwd=None):
        return rule_gate.decide({"session_id": self.session, "cwd": str(cwd or self.root),
                                 "tool_name": "Write", "tool_input": {"file_path": str(path), "content": "x"}})

    def shell(self, path, cwd=None):
        command = 'echo x > "' + str(path) + '"'
        return rule_gate.decide({"session_id": self.session, "cwd": str(cwd or self.root),
                                 "tool_name": "Bash", "tool_input": {"command": command}})

    def test_native_protected_and_unrelated(self):
        protected = self.root / ".aidd" / "evidence" / "events.toon"
        for path in (protected, Path(".aidd/evidence/events.toon")):
            with self.subTest(path=str(path)):
                blocked, message = self.decide(path)
                self.assertTrue(blocked, (path, message))
                self.assertIn("R9", message)
        blocked, message = self.decide(self.root / "docs" / "unrelated.txt")
        self.assertFalse(blocked, message)

    def test_drive_unc_extended_tokens(self):
        paths = ("D:/proj/specs/F23-eDoc-POS/tasks.md",
                 r"D:\proj\specs\F23-eDoc-POS\review.md",
                 r"\\server\share\specs\F23-eDoc-POS\tasks.md",
                 r"\\?\UNC\server\share\specs\F23-eDoc-POS\review.md",
                 r"\\server\share\.aidd\evidence\events.toon")
        for path in paths:
            with self.subTest(path=path):
                blocked, message = self.shell(path)
                self.assertTrue(blocked, (path, message))
                if "specs" in path.lower():
                    self.assertTrue(rule_gate._specs_tok(path), path)

    @unittest.skipUnless(os.name == 'posix', 'foreign drive spellings require a POSIX host')
    def test_foreign_drive_relative_and_extended_tokens(self):
        for path in (r'D:proj\specs\F23-eDoc-POS\tasks.md',
                     r'\\?\D:\proj\specs\F23-eDoc-POS\tasks.md'):
            with self.subTest(path=path):
                self.assertTrue(rule_gate._specs_tok(path), path)
                blocked, message = self.shell(path)
                self.assertTrue(blocked, (path, message))

    def test_relative_parent_and_nested_project(self):
        nested = self.root / "specs" / "nested-project"
        (nested / "specs" / "F23-eDoc-POS").mkdir(parents=True)
        for path, cwd in (("../.aidd/evidence/events.toon", self.root / "src"),
                          (".aidd/evidence/../evidence/events.toon", self.root)):
            with self.subTest(path=path):
                blocked, message = self.decide(path, cwd)
                self.assertTrue(blocked, (path, message))
        protected = nested / "specs" / "F23-eDoc-POS" / "review.md"
        blocked, message = self.shell(protected)
        self.assertTrue(blocked, message)

    def test_case_and_stream_aliases(self):
        for path in (".aidd/evidence/events.toon:stream", ".aidd/evidence/events.toon::$DATA",
                     "specs/F23-eDoc-POS/REVIEW.MD."):
            with self.subTest(path=path):
                blocked, message = self.shell(path)
                self.assertTrue(blocked, (path, message))
        # Native POSIX objects are case-sensitive; Windows aliases are not.
        variant = self.root / ".AIDD" / "evidence" / "events.toon"
        blocked, message = self.decide(variant)
        insensitive = os.name == 'nt' or rule_gate._posix_case_insensitive(str(self.root)) is not False
        self.assertEqual(blocked, insensitive, message)

    @unittest.skipUnless(os.name == "posix", "Linux/POSIX exception decisions require a native POSIX host")
    def test_linux_enumerated_decisions(self):
        self.put("specs/001-x/tasks.md", tasks_text())
        self.open_spec()
        old, reason = load_old_guard()
        self.assertIsNotNone(old, reason)
        cases = {case['id']: case for case in collect_cases(self.root)}
        expected = {
            'ci-drive-tasks': (False, True),
            # This is ordinary code, so R6 still blocks while the fixture's
            # spec is unapproved. It must not be treated as protected .aidd.
            'ci-native-case-distinct': (True, True),
            'ci-cmakelists': (False, True),
            'ci-uppercase-markdown': (True, False),
        }
        for ident, (before, after) in expected.items():
            with self.subTest(case=ident):
                event = dict(cases[ident]['event'], session_id=self.session)
                self.assertEqual(old.decide(event)[0], before, f'{ident}: pinned baseline changed')
                decision, message = rule_gate.decide(event)
                self.assertEqual(decision, after, f'{ident}: desired decision')
                if ident == 'ci-native-case-distinct':
                    if rule_gate._posix_case_insensitive(str(self.root)) is False:
                        self.assertIn('R6', message)
                        self.assertNotIn('R9', message)
                    else:
                        self.assertIn('R9', message)

        for ident in ('ci-drive-review', 'ci-drive-backslash-review', 'drive-mixed-case'):
            with self.subTest(case=ident):
                case = cases[ident]
                event = dict(case['event'], session_id=self.session)
                before = old.decide(event)
                after = rule_gate.decide(event)
                self.assertTrue(before[0], ident)
                self.assertEqual(after, before, f'{ident}: existing denial/message changed')
                self.assertTrue(rule_gate._specs_tok(case['path']), ident)

    @unittest.skipUnless(os.name == "posix", "case-distinct native paths require a POSIX host")
    def test_linux_case_distinct_path_still_obeys_r6(self):
        if rule_gate._posix_case_insensitive(str(self.root)) is not False:
            self.skipTest('requires a proven case-sensitive POSIX directory')
        path = self.root / '.AIDD' / 'Evidence' / 'events.toon'
        unapproved = tasks_text()
        self.put('specs/001-x/tasks.md', unapproved)
        self.open_spec()
        blocked, message = self.decide(path)
        self.assertTrue(blocked)
        self.assertIn('R6', message)
        self.assertNotIn('R9', message)

        approved = approved_tasks()
        self.put('specs/001-x/tasks.md', approved)
        self.approve_spec(text=approved)
        blocked, message = self.decide(path)
        self.assertFalse(blocked, message)
        blocked, message = self.decide(self.root / '.aidd' / 'evidence' / 'events.toon')
        self.assertTrue(blocked)
        self.assertIn('R9', message)

    def test_native_symlink_and_windows_junction(self):
        target = self.root / ".aidd" / "evidence"
        target.mkdir(parents=True, exist_ok=True)
        link = self.root / "outside_alias"
        if not make_link(link, target, True):
            self.skipTest("native symlink / Windows junction unavailable")
        blocked, message = self.decide(link / "events.toon")
        self.assertTrue(blocked, message)
        self.assertIn("R9", message)

    @unittest.skipUnless(os.name == "posix", "case-insensitive POSIX alias detection")
    def test_posix_case_insensitive_existing_alias_is_protected(self):
        # Simulate a volume where the two existing spellings identify the same
        # directory; native Windows mounts can expose this behavior on Linux.
        (self.root / '.aidd').mkdir(exist_ok=True)
        (self.root / '.AIDD').mkdir(exist_ok=True)
        ev = rule_gate._ev()
        cp = ev.canon_path(self.root / '.AIDD' / 'evidence' / 'events.toon')
        with mock.patch.object(rule_gate.os.path, 'samefile', return_value=True):
            self.assertTrue(rule_gate._protected(ev, cp, cp.split('/')))
        with mock.patch.object(rule_gate.os.path, 'samefile', return_value=False):
            self.assertFalse(rule_gate._protected(ev, cp, cp.split('/')))
        with mock.patch.object(rule_gate.os.path, 'samefile', side_effect=PermissionError('unavailable')):
            self.assertTrue(rule_gate._protected(ev, cp, cp.split('/')))

    @unittest.skipUnless(os.name == "posix", "case-insensitive POSIX alias detection")
    def test_posix_missing_aidd_directory_uses_parent_case_behavior(self):
        parent = self.root / 'case_probe'
        parent.mkdir()
        ev = rule_gate._ev()
        cp = ev.canon_path(parent / '.AIDD' / 'evidence' / 'events.toon')
        for result, expected in ((True, True), (False, False), (None, True)):
            with self.subTest(case_insensitive=result):
                with mock.patch.object(rule_gate, '_posix_case_insensitive', return_value=result):
                    self.assertEqual(rule_gate._protected(ev, cp, cp.split('/')), expected)

    @unittest.skipUnless(os.name == "posix", "native POSIX case probing")
    def test_posix_case_probe_is_read_only_and_fails_closed_when_unknown(self):
        parent = self.root / 'case_probe'
        parent.mkdir()
        (parent / 'Probe').write_text('fixture', encoding='utf-8')
        before = sorted(p.name for p in parent.iterdir())
        expected = os.path.exists(parent / 'pROBE')
        self.assertEqual(rule_gate._posix_case_insensitive(str(parent)), expected)
        self.assertEqual(sorted(p.name for p in parent.iterdir()), before)
        with mock.patch.object(rule_gate.os, 'scandir', side_effect=PermissionError('unavailable')):
            self.assertIsNone(rule_gate._posix_case_insensitive(str(parent)))

    @unittest.skipUnless(os.name == "posix", "native POSIX hard links")
    def test_posix_case_probe_distinguishes_two_hardlink_names(self):
        parent = self.root / 'hardlink_probe'
        parent.mkdir()
        source = parent / 'Probe'
        source.write_text('fixture', encoding='utf-8')
        target = parent / 'probe'
        if target.exists():
            self.skipTest('requires a case-sensitive directory')
        try:
            os.link(source, target)
        except OSError as exc:
            self.skipTest(f'hard links unavailable: {exc.__class__.__name__}')
        self.assertTrue(os.path.samefile(source, target))
        self.assertFalse(rule_gate._posix_case_insensitive(str(parent)))

    @unittest.skipUnless(os.name == "posix", "native POSIX case probing")
    def test_posix_case_probe_scan_limit_is_conservative(self):
        parent = self.root / 'scan_limit'
        parent.mkdir()
        for number in range(256):
            (parent / f'entry{number:03d}').touch()
        self.assertFalse(rule_gate._posix_case_insensitive(str(parent)))
        (parent / 'entry256').touch()
        self.assertIsNone(rule_gate._posix_case_insensitive(str(parent)))

    @unittest.skipUnless(os.name == "posix", "native POSIX case probing")
    def test_spec_alias_lookup_fails_closed_on_identity_errors(self):
        cp = str(self.root / 'specs/001-x/PLAN.MD')
        with mock.patch.object(rule_gate, '_posix_case_insensitive', return_value=False):
            with mock.patch.object(rule_gate.os.path, 'samefile', side_effect=PermissionError('unavailable')):
                self.assertTrue(rule_gate._posix_spec_canonical(cp, {'plan.md'}).endswith('/plan.md'))
            with mock.patch.object(rule_gate.os.path, 'samefile', side_effect=FileNotFoundError()):
                self.assertEqual(rule_gate._posix_spec_canonical(cp, {'plan.md'}), cp)

    @unittest.skipUnless(os.name == "posix", "POSIX volume case behavior")
    def test_case_insensitive_posix_spec_artifact_alias_is_guarded(self):
        self.put('specs/001-x/spec.md', spec_text())
        plan = self.put('specs/001-x/plan.md', '# existing plan\n')
        alias = self.root / 'specs/001-x/PLAN.MD'
        if not alias.exists() or not os.path.samefile(plan, alias):
            self.skipTest('requires an actual case-insensitive POSIX directory')
        for path in (alias, self.root / 'SPECS/001-x/PLAN.MD'):
            with self.subTest(path=str(path)):
                self.assertBlocked(self.gate(str(path), content='# changed plan\n'), 'find_spec')

    @unittest.skipUnless(os.name == "posix", "native POSIX hard links")
    def test_case_distinct_hardlinks_to_spec_artifacts_remain_guarded(self):
        self.put('specs/001-x/spec.md', spec_text())
        plan = self.put('specs/001-x/plan.md', '# original plan\n')
        tasks = self.put('specs/001-x/tasks.md', tasks_text())
        for original, name, body in ((plan, 'PLAN.MD', '# changed plan\n'),
                                     (tasks, 'TASKS.MD', tasks_text())):
            alias = original.with_name(name)
            if alias.exists():
                self.skipTest('requires a case-sensitive directory')
            try:
                os.link(original, alias)
            except OSError as exc:
                self.skipTest(f'hard links unavailable: {exc.__class__.__name__}')
            with self.subTest(name=name):
                self.assertTrue(os.path.samefile(original, alias))
                self.assertBlocked(self.gate(str(alias), content=body), 'find_spec')

    @unittest.skipUnless(os.name == "posix", "native POSIX case behavior")
    def test_case_distinct_spec_artifact_with_different_inode_is_ordinary(self):
        self.put('specs/001-x/spec.md', spec_text())
        original = self.put('specs/001-x/plan.md', '# original plan\n')
        alias = original.with_name('PLAN.MD')
        if alias.exists():
            self.skipTest('requires a case-sensitive directory')
        alias.write_text('# unrelated file\n', encoding='utf-8')
        self.assertFalse(os.path.samefile(original, alias))
        self.assertAllowed(self.gate(str(alias), content='# unrelated change\n'))
        self.assertBlocked(self.gate(str(original), content='# changed plan\n'), 'find_spec')


if __name__ == "__main__":
    unittest.main()
