"""Amendment 10 item Q of spec 007: lessons measured in b1SycLink on 2026-11-06 (aidd:FR-433..FR-442,
AC-497..AC-508). Unit tests of the diagnostics added to aidd_evidence, aidd_status, aidd_rules, aidd_pending and
check_spec; the CLI-level cases live in test_verify_round, test_verify_round_reuse and test_aidd_status.
stdlib unittest, temp dirs only (no test writes <repo>/.aidd)."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / 'skill' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import aidd_evidence as ev  # noqa: E402
import aidd_pending as pending  # noqa: E402
import aidd_rules as rules  # noqa: E402
import aidd_status as status  # noqa: E402

BIG = '# code\n' + 'x = 1\n' * 20


class TmpBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text=BIG):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        return p


class FingerprintSkip(TmpBase):                                                # FR-433, FR-434
    def test_git_mode_never_hashes_skipped_or_artifact_files(self):
        listed = b'\0'.join([b'src/a.py', b'web/e2e/__screens__/s1.png', b'web/node_modules/x.js',
                             b'web/test-results/r.json', b'src/b.py']) + b'\0'
        for rel in ('src/a.py', 'src/b.py', 'web/e2e/__screens__/s1.png', 'web/node_modules/x.js',
                    'web/test-results/r.json'):
            self.write(rel)
        seen = []

        def shas(_root, rels, _deadline):
            seen.extend(rels)
            return {r: '0' * 40 for r in rels}
        with patch.object(ev, '_fp_git', return_value=listed), patch.object(ev, '_blob_shas', side_effect=shas):
            state = ev.code_state(self.root, skip=['web/e2e/__screens__/**'])
        self.assertEqual(sorted(seen), ['src/a.py', 'src/b.py'])                # never sent to git hash-object
        self.assertEqual(sorted(state[1]), ['src/a.py', 'src/b.py'])

    def test_mtime_mode_prunes_artifact_folders(self):
        self.write('src/a.py')
        self.write('src/test-results/r.json')
        self.write('src/node_modules/m.js')
        self.write('src/shots/s.png')
        with patch.object(ev, '_code_state_git', side_effect=ev._FpUnavailable):
            state = ev.code_state(self.root, scope=['src/**'], skip=['src/shots/**'])
        self.assertEqual(sorted(state[1]), ['src/a.py'])

    def test_refusal_text(self):
        with patch.dict(os.environ, {'AIDD_FINGERPRINT_BUDGET': '30'}):
            text = status.fingerprint_refusal('F36', 'nothing was executed')
        self.assertIn('inputs of F36; nothing was executed.', text)
        self.assertIn('AIDD_FINGERPRINT_BUDGET=<seconds> (default 8, now 30)', text)


class RewriteAttribution(TmpBase):                                             # FR-438
    def test_row_other_and_unknown(self):
        now = time.time()
        a = self.write('src/a.py')
        b = self.write('src/b.py')
        c = self.write('src/c.py')
        os.utime(a, (now - 50, now - 50))          # inside row 2's window
        os.utime(b, (now - 30, now - 30))          # between rows, inside the run
        os.utime(c, (now - 500, now - 500))        # outside the run (time kept by a copy)
        windows = [('1', 'python tools/x.py', now - 100, now - 80), ('2', 'python gen.py src', now - 60, now - 40)]
        got = {r: (k, line) for r, k, line in status.rewrite_attribution(
            self.root, ['src/a.py', 'src/b.py', 'src/c.py', 'src/gone.py'], windows, now - 100, now)}
        self.assertEqual(got['src/a.py'][0], 'row')
        self.assertIn('while row 2 ran (`python gen.py src`) - the command names it', got['src/a.py'][1])
        self.assertIn('`Generated: src/**`', got['src/a.py'][1])
        self.assertEqual(got['src/b.py'][0], 'other')
        self.assertIn('another process or agent', got['src/b.py'][1])
        self.assertEqual(got['src/c.py'][0], 'unknown')
        self.assertEqual(got['src/gone.py'][0], 'unknown')


class ApprovalChangeHint(TmpBase):                                             # FR-440
    TASKS = '# tasks\n\n| Task | Target file |\n|---|---|\n| T-01 | `src/a.py` |\n'
    BATCH = '| Task | Target file |\n|---|---|\n| T-10 | `src/b.py` |\n'

    def spec(self):
        d = self.root / 'specs' / '001-x'
        self.write('specs/001-x/tasks.md', self.TASKS)
        self.write('specs/001-x/tasks-amendment-01.md', self.BATCH)
        return d

    def test_per_file_hash_names_the_batch_that_changed(self):
        d = self.spec()
        seg = rules.approval_segment_hashes(rules.read_tasks(d))
        self.assertEqual(sorted(seg), ['tasks-amendment-01.md', 'tasks.md'])
        self.assertEqual(rules.approval_change_hint(d, {'segments': seg, 'ts': time.time()}), '')
        (d / 'tasks-amendment-01.md').write_text(self.BATCH + '| T-11 | `src/c.py` |\n', encoding='utf-8')
        hint = rules.approval_change_hint(d, {'segments': seg, 'ts': time.time()})
        self.assertIn('per-file hash', hint)
        self.assertIn('tasks-amendment-01.md (modified 20', hint)
        self.assertNotIn('tasks.md (modified', hint)

    def test_approved_line_alone_does_not_count_as_a_change(self):
        d = self.spec()
        seg = rules.approval_segment_hashes(rules.read_tasks(d))
        (d / 'tasks.md').write_text(self.TASKS + '\nApproved: 2026-11-06 hash:0123456789ab\n', encoding='utf-8')
        self.assertEqual(rules.approval_change_hint(d, {'segments': seg}), '')

    def test_legacy_event_uses_mtime(self):
        d = self.spec()
        old = time.time() - 100
        os.utime(d / 'tasks.md', (old - 10, old - 10))
        hint = rules.approval_change_hint(d, {'ts': old})
        self.assertIn('by mtime', hint)
        self.assertIn('tasks-amendment-01.md (modified', hint)
        self.assertNotIn(' tasks.md (modified', hint)

    def test_status_line_carries_the_hint(self):
        class Loose(dict):                          # format_status reads many keys: absent ones are neutral
            def __missing__(self, key):
                return Loose()

            def __format__(self, spec):
                return ''
        st = Loose({'spec': '001-x', 'open': True, 'alignment': Loose({'proposed': 0, 'unverified_quotes': 0}),
                    'mapper': True, 'graph': True, 'auditors': {}, 'code_edits': 0,
                    'tasks': Loose({'approval': 'invalid', 'waves': 0, 'critical_path_min': None,
                                    'approval_changed': 'changed after approval (per-file hash): '
                                                        'tasks-a.md (modified x)'})})
        with patch.object(status, '_route_summary', return_value='-'):
            line = status.format_status(st)
        self.assertIn('approval VOID ✘ (tasks changed after approval: changed after approval (per-file hash): '
                      'tasks-a.md', line)


class PendingReadsBatchesAndSharedTargets(TmpBase):                           # FR-441
    def test_batches_are_read_and_shared_targets_are_not_done(self):
        self.write('specs/001-x/tasks.md', '| Task | Target file | Status |\n|---|---|---|\n'
                   '| T-01 | `src/new.py` |  |\n| T-02 | `src/router.tsx` |  |\n')
        self.write('specs/001-x/tasks-amendment-01.md', '| Task | Target file | Status |\n|---|---|---|\n'
                   '| T-10 | `src/router.tsx` | pending |\n| T-11 | `src/missing.py` |  |\n'
                   '| T-12 | `src/solo.py` | todo |\n')
        self.write('src/new.py')
        self.write('src/router.tsx')
        self.write('src/solo.py')
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = pending.main([str(self.root / 'specs' / '001-x'), '--root', str(self.root), '--json'])
        self.assertEqual(rc, 0)
        out = json.loads(buf.getvalue())
        self.assertEqual(out['done'], ['T-01'])
        self.assertEqual(out['pending'], ['T-11'])                              # read from the batch file
        self.assertEqual(out['unverified'], ['T-02', 'T-10', 'T-12'])
        self.assertIn('target shared with T-10', out['unverified_why']['T-02'])
        self.assertIn('Status says "todo"', out['unverified_why']['T-12'])
        self.assertEqual(out['files'], ['tasks.md', 'tasks-amendment-01.md'])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            pending.main([str(self.root / 'specs' / '001-x'), '--root', str(self.root)])
        self.assertIn('existence does NOT prove the task is done', buf.getvalue())
        self.assertIn('done=1 pending=1 unverified=3', buf.getvalue())


class SlotWarnings(TmpBase):                                                   # FR-442
    def spec(self, name, rows, extra=''):
        body = ''.join(f'| {n} | `{c}` | exit 0 | FR-1 | {t} |\n' for n, c, t in rows)
        return self.write(f'specs/{name}/spec.md', f'# {name}\n\n## Verification\n{extra}'
                          '| # | Command | Expected | Covers | Tier |\n|---|---|---|---|---|\n' + body).parent

    def test_protected_slot_and_perf_heuristic(self):
        a = self.spec('A', [('1', 'python db_verify.py --slot 1 --only-tests a_', '')])
        self.spec('B', [('1', 'python db_verify.py --slot 1 --perf seeded', 'perf')])
        self.spec('C', [('1', 'python ok.py', '')], extra='Protected-slot: 1\n')
        self.spec('D', [('1', 'python db_verify.py --slot 2', 'perf')])
        got = rules.slot_warnings(a)
        self.assertEqual(len(got), 2, got)
        self.assertIn('B has `Tier: perf` row(s) 1 on slot 1', got[0])
        self.assertIn('C declares `Protected-slot: 1`', got[1])
        self.assertIn('run with `--slot 1`, which resets that work database', got[0])
        self.assertEqual(rules.slot_warnings(self.root / 'specs' / 'D'), [])

    def test_check_spec_prints_the_warning_without_a_gap(self):
        a = self.spec('A', [('1', 'python db_verify.py --slot 1', '')])
        self.spec('B', [('1', 'python db_verify.py --slot=1 --perf', 'perf')])
        r = subprocess.run([sys.executable, str(SCRIPTS / 'check_spec.py'), str(a)], capture_output=True,
                           text=True, encoding='utf-8')
        self.assertIn('WARNING: Verification row(s) 1 run with `--slot 1`', r.stdout)


if __name__ == '__main__':
    unittest.main()
