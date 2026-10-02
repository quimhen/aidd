"""Tests for R10 (execution evidence), R11 (root cause on repeat), R12 (view-vs-logic tag)
in skill/scripts/aidd_rules.py — spec 003, adversarial per rule.

Run: python -m unittest tests.test_aidd_rules_r10 -v
"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "skill" / "scripts"))

import aidd_rules as R  # noqa: E402

WARN = '\u26a0\ufe0f'   # warning sign + U+FE0F, as typed in the templates
QUOTE = 'user \u2014 "lo probe en la tablet y funciona"'


def rules(vs):
    return {v['rule'] for v in vs}


def hits(vs, rule, contains=None):
    return [v for v in vs if v['rule'] == rule and (contains is None or contains in v['message'])]


def ledger(rows, exceptions=''):
    body = '\n'.join(f'| {c} | {s} | x | PR-1 | \u2610 |' for c, s in rows)
    return ("# QA Audit\n\n## Mapping ledger\n"
            "| Code | Status | Evidence (file/class/resource id) | PR/Spec ref | Screenshot diff done? |\n"
            f"|---|---|---|---|---|\n{body}\n\n"
            f"## Open exceptions (rows left unresolved on purpose)\n| Code | Reason | Approved by |\n|---|---|---|\n{exceptions}\n")


def evidence(rows):
    body = '\n'.join(f'| {c} | {k} | {e} | {w} |' for c, k, e, w in rows)
    return f"\n## Execution evidence\n| Code | Kind | Evidence | Verified by |\n|---|---|---|---|\n{body}\n"


def qa(ledger_rows, ev_rows, exceptions='', bugs=''):
    return ledger(ledger_rows, exceptions) + evidence(ev_rows) + bugs


def bugs(rows):
    body = '\n'.join(f'| {i + 1} | {c} | {s} | {rc} | {fx} | {sw} |' for i, (c, s, rc, fx, sw) in enumerate(rows))
    return ("\n## Bug reports\n| # | Code | Symptom | Root cause | Fix | Pattern sweep |\n|---|---|---|---|---|---|\n"
            f"{body}\n")


class _Dirs(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self.spec = self.root / 'specs' / '003-x'
        (self.spec / 'evidence').mkdir(parents=True)
        (self.spec / 'evidence' / 'home.png').write_bytes(b'png')
        (self.spec / 'evidence' / 'out.txt').write_text('ok', encoding='utf-8')
        (self.spec / 'human-test.md').write_text('# steps', encoding='utf-8')
        (self.root / 'proof.log').write_text('log', encoding='utf-8')
        # a file just outside the project root, to prove escapes are rejected
        self.outside = self.root.parent / 'outside_evidence_r10.png'
        self.outside.write_bytes(b'x')
        self.addCleanup(lambda: self.outside.unlink() if self.outside.exists() else None)

    def qa_v(self, text, **kw):
        return R.check_content('qa', text, self.spec, self.root) if not kw else R.check_qa(
            text, self.spec, self.root, **kw)


class TestR10(_Dirs):
    def test_green_screen_without_evidence_blocked(self):
        v = self.qa_v(ledger([('SCREEN-01', '\u2705 IMPLEMENTED')]))
        self.assertTrue(hits(v, 'R10', 'SCREEN-01'), v)
        self.assertTrue(all(x['fix'].strip() for x in v))

    def test_screenshot_existing_passes(self):
        t = qa([('SCREEN-01', '\u2705 IMPLEMENTED')], [('SCREEN-01', 'screenshot', 'evidence/home.png', 'agent')])
        self.assertEqual(self.qa_v(t), [])

    def test_api_and_fnn_codes_require_evidence_comp_ctl_do_not(self):
        v = self.qa_v(ledger([('API-001', '\u2705'), ('SCREEN-01-F01', '\u2705'), ('COMP-001', '\u2705'),
                              ('CTL-001', '\u2705')]))
        self.assertEqual(len(hits(v, 'R10')), 2, v)
        self.assertTrue(hits(v, 'R10', 'API-001') and hits(v, 'R10', 'SCREEN-01-F01'))

    def test_non_green_rows_need_nothing(self):
        t = ledger([('SCREEN-01', f'{WARN} PARTIAL'), ('SCREEN-02', '\u274c MISSING')])
        self.assertEqual(self.qa_v(t), [])

    def test_open_exception_exempts(self):
        t = ledger([('SCREEN-01', '\u2705')], exceptions='| SCREEN-01 | tablet not available | user |')
        self.assertEqual(self.qa_v(t), [])

    def test_evidence_in_project_root_accepted(self):
        t = qa([('API-001', '\u2705')], [('API-001', 'log', 'proof.log', 'agent')])
        self.assertEqual(self.qa_v(t), [])

    def test_url_accepted_for_file_kinds(self):
        t = qa([('API-001', '\u2705')], [('API-001', 'command-output', 'https://ci.example.com/run/1', 'agent')])
        self.assertEqual(self.qa_v(t), [])

    def test_missing_file_blocked(self):
        t = qa([('API-001', '\u2705')], [('API-001', 'log', 'evidence/nope.log', 'agent')])
        self.assertTrue(hits(self.qa_v(t), 'R10', 'does not exist'))

    def test_bad_kind_blocked(self):
        t = qa([('API-001', '\u2705')], [('API-001', 'trust-me', 'proof.log', 'agent')])
        self.assertTrue(hits(self.qa_v(t), 'R10', 'trust-me'))

    def test_bad_verified_by_blocked(self):
        t = qa([('API-001', '\u2705')], [('API-001', 'log', 'proof.log', 'robot')])
        self.assertTrue(hits(self.qa_v(t), 'R10', 'Verified by'))

    def test_screenshot_wrong_extension_blocked(self):
        t = qa([('SCREEN-01', '\u2705')], [('SCREEN-01', 'screenshot', 'evidence/out.txt', 'agent')])
        self.assertTrue(hits(self.qa_v(t), 'R10', 'screenshot must be'))

    def test_path_escape_dotdot_rejected(self):
        t = qa([('SCREEN-01', '\u2705')],
               [('SCREEN-01', 'screenshot', '../../../outside_evidence_r10.png', 'agent')])
        self.assertTrue(hits(self.qa_v(t), 'R10'))

    def test_dotdot_that_would_land_inside_still_rejected(self):
        t = qa([('API-001', '\u2705')], [('API-001', 'log', 'evidence/../../../proof.log', 'agent')])
        self.assertTrue(hits(self.qa_v(t), 'R10'))

    def test_absolute_drive_letter_rejected(self):
        p = str(self.outside).replace('\\', '/')
        t = qa([('SCREEN-01', '\u2705')], [('SCREEN-01', 'screenshot', p, 'agent')])
        self.assertTrue(hits(self.qa_v(t), 'R10'))
        t = qa([('SCREEN-01', '\u2705')], [('SCREEN-01', 'screenshot', 'C:\\Windows\\x.png', 'agent')])
        self.assertTrue(hits(self.qa_v(t), 'R10'))

    def test_unc_rejected(self):
        for p in ('\\\\server\\share\\a.png', '//server/share/a.png'):
            t = qa([('SCREEN-01', '\u2705')], [('SCREEN-01', 'screenshot', p, 'agent')])
            self.assertTrue(hits(self.qa_v(t), 'R10'), p)

    def test_manual_test_user_quote_passes(self):
        t = qa([('SCREEN-01', '\u2705')], [('SCREEN-01', 'manual-test', QUOTE, 'user')])
        self.assertEqual(self.qa_v(t), [])

    def test_manual_test_short_quote_or_empty_blocked(self):
        t = qa([('SCREEN-01', '\u2705')], [('SCREEN-01', 'manual-test', 'user \u2014 "ok"', 'user')])
        self.assertTrue(hits(self.qa_v(t), 'R10', '3+ words'))
        t = qa([('SCREEN-01', '\u2705')], [('SCREEN-01', 'manual-test', 'it works', 'user')])
        self.assertTrue(hits(self.qa_v(t), 'R10'))

    def test_manual_test_existing_path_passes(self):
        t = qa([('SCREEN-01', '\u2705')], [('SCREEN-01', 'manual-test', 'evidence/out.txt', 'user')])
        self.assertEqual(self.qa_v(t), [])

    def test_not_verified_with_script_and_partial_status_passes(self):
        # the status carries U+FE0F: detection must be startswith on plain text, not equality
        t = qa([('SCREEN-01', f'{WARN} PARTIAL')], [('SCREEN-01', 'not-verified', 'human-test.md', 'agent')])
        self.assertEqual(self.qa_v(t), [])

    def test_not_verified_with_green_status_blocked(self):
        t = qa([('SCREEN-01', '\u2705 IMPLEMENTED')], [('SCREEN-01', 'not-verified', 'human-test.md', 'agent')])
        v = self.qa_v(t)
        self.assertTrue(hits(v, 'R10', 'still'), v)

    def test_not_verified_green_with_bold_markers_still_blocked(self):
        t = qa([('SCREEN-01', '**\u2705** IMPLEMENTED')], [('SCREEN-01', 'not-verified', 'human-test.md', 'agent')])
        self.assertTrue(hits(self.qa_v(t), 'R10', 'still'))

    def test_not_verified_without_script_blocked(self):
        t = qa([('SCREEN-01', f'{WARN} PARTIAL')], [('SCREEN-01', 'not-verified', 'nope.md', 'agent')])
        self.assertTrue(hits(self.qa_v(t), 'R10', 'human test script'))

    def test_placeholder_rows_in_html_comment_ignored(self):
        t = ("# QA\n\n## Mapping ledger\n| Code | Status | Evidence | PR/Spec ref | Diff |\n|---|---|---|---|---|\n"
             "<!-- | SCREEN-01 | \u2705 IMPLEMENTED | | | |\n-->\n| SCREEN-02 | " + WARN + " PARTIAL | | | |\n")
        self.assertEqual(self.qa_v(t), [])

    def test_placeholder_evidence_row_in_comment_does_not_satisfy(self):
        t = (ledger([('SCREEN-01', '\u2705')])
             + "\n## Execution evidence\n| Code | Kind | Evidence | Verified by |\n|---|---|---|---|\n"
               "<!-- | SCREEN-01 | screenshot | evidence/home.png | agent | -->\n")
        self.assertTrue(hits(self.qa_v(t), 'R10', 'SCREEN-01'))

    def test_wrong_evidence_header_blocked(self):
        t = (ledger([('SCREEN-01', '\u2705')])
             + "\n## Execution evidence\n| Code | Proof |\n|---|---|\n| SCREEN-01 | evidence/home.png |\n")
        self.assertTrue(hits(self.qa_v(t), 'R10', 'header'))

    def test_freshness_stale_blocked_and_fresh_passes(self):
        t = qa([('SCREEN-01', '\u2705')], [('SCREEN-01', 'screenshot', 'evidence/home.png', 'agent')])
        old = time.time() - 1000
        os.utime(self.spec / 'evidence' / 'home.png', (old, old))
        v = R.check_qa(t, self.spec, self.root, last_edit_ts=time.time() - 10)
        self.assertTrue(hits(v, 'R10', 'stale'), v)
        new = time.time()
        os.utime(self.spec / 'evidence' / 'home.png', (new, new))
        self.assertEqual(R.check_qa(t, self.spec, self.root, last_edit_ts=new - 10), [])

    def test_freshness_not_checked_without_last_edit_ts(self):
        t = qa([('SCREEN-01', '\u2705')], [('SCREEN-01', 'screenshot', 'evidence/home.png', 'agent')])
        old = time.time() - 100000
        os.utime(self.spec / 'evidence' / 'home.png', (old, old))
        self.assertEqual(R.check_qa(t, self.spec, self.root), [])

    def test_check_content_qa_is_total(self):
        for bad_in in (None, '', 5, '| | |\n## Execution evidence\n|'):
            self.assertIsInstance(R.check_content('qa', bad_in), list)

    def test_oversize_not_scanned(self):
        v = R.check_content('qa', 'x' * (R.MAX_CHARS + 1))
        self.assertTrue(hits(v, 'R10', 'too large'))

    def test_raw_qa_template_passes(self):
        for tree in (REPO / 'skill' / 'templates', REPO / 'adapters' / 'dot-aidd' / 'templates'):
            p = tree / 'qa-audit.md'
            if p.exists():
                v = R.check_content('qa', p.read_text(encoding='utf-8'), self.spec, self.root)
                self.assertEqual(v, [], f'{p}: {v}')

    def test_check_spec_dir_runs_check_qa_static(self):
        (self.spec / 'spec.md').write_text('# s\n', encoding='utf-8')
        (self.spec / 'qa-audit.md').write_text(ledger([('SCREEN-01', '\u2705')]), encoding='utf-8')
        v = R.check_spec_dir(self.spec, self.root, static_only=True)
        self.assertTrue(hits(v, 'R10', 'SCREEN-01'), v)
        (self.spec / 'qa-audit.md').write_text(
            qa([('SCREEN-01', '\u2705')], [('SCREEN-01', 'screenshot', 'evidence/home.png', 'agent')]), encoding='utf-8')
        v = R.check_spec_dir(self.spec, self.root, static_only=True)
        self.assertFalse(hits(v, 'R10'), v)

    def test_rule_ids_include_new_rules(self):
        for r in ('R10', 'R11', 'R12'):
            self.assertIn(r, R.RULE_IDS)


class TestR11(_Dirs):
    def v(self, rows):
        return [x for x in self.qa_v('# QA\n' + bugs(rows)) if x['rule'] == 'R11']

    def test_single_reports_need_nothing(self):
        self.assertEqual(self.v([('SCREEN-01', 'N/D', '', 'patched', ''), ('SCREEN-02', 'blank', '', 'patched', '')]), [])

    def test_second_report_without_root_cause_blocked(self):
        v = self.v([('SCREEN-01', 'N/D', '', 'patched', ''),
                    ('SCREEN-01', 'N/D again', '', 'patched again', 'grep -rn "fmt(" forms/ -> 4 hits')])
        self.assertTrue(hits(v, 'R11', 'Root cause'), v)

    def test_second_report_without_sweep_blocked(self):
        v = self.v([('SCREEN-01', 'N/D', '', 'patched', ''),
                    ('SCREEN-01', 'N/D again', 'null id from DTO', 'mapped it', 'n/a')])
        self.assertTrue(hits(v, 'R11', 'Pattern sweep'), v)

    def test_second_report_complete_passes(self):
        v = self.v([('SCREEN-01', 'N/D', '', 'patched', ''),
                    ('SCREEN-01', 'N/D again', 'null id from DTO', 'mapped it',
                     'grep -rn "fmt(" forms/ -> 4 hits fixed')])
        self.assertEqual(v, [])

    def test_third_report_needs_redesign_with_reference(self):
        base = [('SCREEN-01', 'a', '', 'p', ''),
                ('SCREEN-01', 'b', 'cause', 'p2', 'grep x -> 1'),
                ('SCREEN-01', 'c', 'cause2', 'patched again', 'grep y -> 2')]
        self.assertTrue(hits(self.v(base), 'R11', 'redesign'))
        base[2] = ('SCREEN-01', 'c', 'cause2', 'redesign', 'grep y -> 2')   # keyword but no reference
        self.assertTrue(hits(self.v(base), 'R11', 'redesign'))
        base[2] = ('SCREEN-01', 'c', 'cause2', 'redesign \u2014 spec 004-new-screen', 'grep y -> 2')
        self.assertEqual(self.v(base), [])
        base[2] = ('SCREEN-01', 'c', 'cause2', 'redesign T-12', 'grep y -> 2')
        self.assertEqual(self.v(base), [])

    def test_codes_counted_independently_and_case_insensitive(self):
        v = self.v([('SCREEN-01', 'a', '', 'p', ''), ('SCREEN-02', 'b', '', 'p', ''), ('screen-01', 'c', '', 'p', '')])
        self.assertTrue(hits(v, 'R11'))
        self.assertEqual(len(hits(v, 'R11', 'SCREEN-02')), 0)

    def test_placeholder_dash_counts_as_blank(self):
        v = self.v([('SCREEN-01', 'a', '', 'p', ''), ('SCREEN-01', 'b', 'n/a', 'p', '-')])
        self.assertEqual(len(hits(v, 'R11')), 2, v)

    def test_bug_rows_in_comment_ignored(self):
        t = ("# QA\n## Bug reports\n| # | Code | Symptom | Root cause | Fix | Pattern sweep |\n|---|---|---|---|---|---|\n"
             "<!-- | 1 | SCREEN-01 | a | | p | |\n| 2 | SCREEN-01 | b | | p | | -->\n")
        self.assertEqual(self.qa_v(t), [])

    def test_wrong_header_blocked_only_with_rows(self):
        t = "# QA\n## Bug reports\n| # | Code | Notes |\n|---|---|---|\n| 1 | SCREEN-01 | x |\n"
        self.assertTrue(hits(self.qa_v(t), 'R11', 'header'))
        t = "# QA\n## Bug reports\n| # | Code | Notes |\n|---|---|---|\n"
        self.assertEqual(self.qa_v(t), [])


def tasks_md(row_extra='', block_extra=''):
    return f"""# Tasks - x

| Task | Codes | Notes |
|---|---|---|
| T-01 | SCREEN-01 | {row_extra} |

### T-01
- Agent min: 30
- Human ref hours: 8
{block_extra}
## Waves

| Wave | Tasks | Agent time (min) | Human ref (h) |
|---|---|---|---|
| 1 | T-01 | 30 | 8 |

Total agent time (critical path): 30 min

Approved: PENDING
"""


class TestR12(unittest.TestCase):
    def r12(self, text):
        return [v for v in R.check_content('tasks', text) if v['rule'] == 'R12']

    def test_reuse_word_with_screen_and_no_kind_blocked(self):
        v = self.r12(tasks_md(row_extra='reutiliza la vista antigua'))
        self.assertTrue(v and all(x['fix'].strip() for x in v), v)

    def test_each_reuse_word_triggers(self):
        for w in ('reutiliza', 'remapea', 'envuelve', 'wrap', 'wrapper', 'reuse', 'reused', 'rewire'):
            self.assertTrue(self.r12(tasks_md(row_extra=f'{w} it')), w)

    def test_comp_code_also_triggers(self):
        t = tasks_md(row_extra='reuse header').replace('| SCREEN-01 |', '| COMP-003 |')
        self.assertTrue(self.r12(t))

    def test_no_reuse_word_or_no_code_not_flagged(self):
        self.assertEqual(self.r12(tasks_md(row_extra='build new view')), [])
        t = tasks_md(row_extra='reuse helper').replace('| SCREEN-01 |', '| API-001 |')
        self.assertEqual(self.r12(t), [])

    def test_kind_in_block_passes(self):
        for k in ('Kind: VIEW-new', 'Kind: LOGIC', '- **Kind:** VIEW-new + LOGIC',
                  'Kind: VIEW-legacy: tablet screen is frozen until v5'):
            self.assertEqual(self.r12(tasks_md(row_extra='reutiliza datos', block_extra=k)), [], k)

    def test_kind_in_row_passes(self):
        self.assertEqual(self.r12(tasks_md(row_extra='reutiliza datos. Kind: LOGIC')), [])

    def test_bare_view_legacy_blocked(self):
        for k in ('Kind: VIEW-legacy', 'Kind: VIEW-legacy:', 'Kind: VIEW-legacy: ok'):
            v = self.r12(tasks_md(row_extra='envuelve la pantalla', block_extra=k))
            self.assertTrue(hits(v, 'R12', 'justification'), (k, v))

    def test_kind_in_html_comment_does_not_count(self):
        t = tasks_md(row_extra='reutiliza datos', block_extra='<!-- Kind: LOGIC -->')
        self.assertTrue(self.r12(t))

    def test_row_in_html_comment_ignored(self):
        t = tasks_md().replace('| T-01 | SCREEN-01 |  |', '<!-- | T-01 | SCREEN-01 | wrap it | -->\n| T-01 | SCREEN-01 | ok |')
        self.assertEqual(self.r12(t), [])

    def test_waves_table_row_never_triggers(self):
        self.assertEqual(self.r12(tasks_md()), [])

    def test_kind_changes_approval_hash(self):
        a = tasks_md(row_extra='reutiliza datos', block_extra='Kind: LOGIC')
        b = tasks_md(row_extra='reutiliza datos', block_extra='Kind: VIEW-new')
        self.assertNotEqual(R.approval_hash(a), R.approval_hash(b))

    def test_raw_tasks_template_only_r1(self):
        for tree in (REPO / 'skill' / 'templates', REPO / 'adapters' / 'dot-aidd' / 'templates'):
            p = tree / 'tasks.md'
            if p.exists():
                got = rules(R.check_content('tasks', p.read_text(encoding='utf-8')))
                self.assertFalse(got & {'R12'}, f'{p}: {got}')


if __name__ == '__main__':
    unittest.main()
