"""Tests for skill/scripts/aidd_rules.py — stdlib unittest, adversarial per rule.

Run: python -m unittest tests.test_aidd_rules -v
"""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "skill" / "scripts"))

import aidd_rules as R  # noqa: E402

QUOTE = 'user — "no hace falta el flowmap"'


def rules(vs):
    return {v['rule'] for v in vs}


def ok(testcase, vs):
    testcase.assertEqual(vs, [], vs)


def bad(testcase, vs, rule, contains=None):
    hits = [v for v in vs if v['rule'] == rule and (contains is None or contains in v['message'])]
    testcase.assertTrue(hits, f"expected {rule} ({contains}) in {vs}")
    for v in hits:
        testcase.assertTrue(v['fix'].strip())
        testcase.assertTrue(v['message'].strip())


def route(overrides=None):
    rows = {s: ('run', '', '') for s in R.ROUTE_STEPS}
    rows.update(overrides or {})
    body = '\n'.join(f'| {s} | {a} | {b} | {c} |' for s, (a, b, c) in rows.items())
    return f"## Pipeline route\n\n| Step | Status | Reason | Confirmation |\n|---|---|---|---|\n{body}\n"


CHECKLIST = r"""## Minimum Requirements Checklist (fill before Step 3 starts)

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | Checkout | user — "es el modulo de checkout" | ask |
| New development or modification of something existing? | Modification | repo — src/cart.py:12 | ask |
| Does it involve an external service, API, or integration? | No | repo — a.py:1 | ask |
| Who is requesting it? (role/profile, not necessarily the name) | Ops | repo — a.py:2 | ask |
| Dependencies on other modules or active developments? | None | repo — a.py:3 | ask |
| Business objective (1 sentence — what it achieves and why) | Faster pay | [Proposed — unconfirmed] | ask |
| Expected visual fidelity level (if there's a mockup): exact \| functional behavior only | Exact | repo — a.py:4 | ask |
"""


def spec(route_overrides=None, checklist=CHECKLIST, extra=''):
    return f"# Spec — x\n\n{checklist}\n{route(route_overrides)}\n{extra}"


def tasks(a1=30, a2=20, w1=30, w2=20, total=50, extra_block=''):
    return f"""# Tasks — x

| Task | Codes |
|---|---|
| T-01 | COMP-001 |

### T-01
- Agent min: {a1}
- Human ref hours: 8

### T-02
- Agent min: {a2}
- Human ref hours: 4
{extra_block}
## Waves

| Wave | Tasks | Agent time (min) | Human ref (h) |
|---|---|---|---|
| 1 | T-01 | {w1} | 8 |
| 2 | T-02 | {w2} | 4 |

Total agent time (critical path): {total} min

Approved: PENDING
"""


class TestR1(unittest.TestCase):
    def test_legit(self):
        ok(self, R.check_content('tasks', tasks()))

    def test_crlf_and_spacing_and_case(self):
        t = tasks().replace('## Waves', '##   WAVES').replace('\n', '\r\n')
        ok(self, R.check_content('tasks', t))

    def test_bold_labels_and_units(self):
        t = tasks().replace('- Agent min: 30', '- **Agent min:** 30 min').replace('Human ref hours: 8', 'Human ref hours: 8.5 h')
        ok(self, R.check_content('tasks', t))

    def test_legacy_estimated_hours_alone(self):
        t = tasks().replace('- Agent min: 30\n- Human ref hours: 8', '- Estimated hours: 8')
        vs = R.check_content('tasks', t)
        bad(self, vs, 'R1', 'legacy')

    def test_missing_human_ref(self):
        bad(self, R.check_content('tasks', tasks().replace('- Human ref hours: 8\n', '')), 'R1', 'Human ref hours')

    def test_no_waves_table(self):
        t = tasks().split('## Waves')[0]
        bad(self, R.check_content('tasks', t), 'R1', 'Waves')

    def test_waves_heading_without_rows(self):
        t = re.sub(r'\| [12] \| T-0\d.*\n', '', tasks())
        bad(self, R.check_content('tasks', t), 'R1', 'no rows')

    def test_wrong_column_order(self):
        t = tasks().replace('| Wave | Tasks | Agent time (min) | Human ref (h) |',
                            '| Wave | Agent time (min) | Tasks | Human ref (h) |')
        bad(self, R.check_content('tasks', t), 'R1', 'column order')

    def test_wave_time_off_by_one(self):
        bad(self, R.check_content('tasks', tasks(w1=31, total=51)), 'R1', 'max of its tasks')

    def test_wave_is_max_not_sum(self):
        t = tasks().replace('| 1 | T-01 | 30 | 8 |', '| 1 | T-01, T-02 | 50 | 12 |').replace('| 2 | T-02 | 20 | 4 |\n', '')
        bad(self, R.check_content('tasks', t), 'R1', 'max of its tasks')

    def test_parallel_wave_ok(self):
        t = tasks().replace('| 1 | T-01 | 30 | 8 |', '| 1 | T-01, T-02 | 30 | 12 |').replace('| 2 | T-02 | 20 | 4 |\n', '')
        ok(self, R.check_content('tasks', t.replace('critical path): 50', 'critical path): 30')))

    def test_total_off_by_one(self):
        bad(self, R.check_content('tasks', tasks(total=51)), 'R1', 'sum of waves')

    def test_total_missing(self):
        t = re.sub(r'Total agent time.*\n', '', tasks())
        bad(self, R.check_content('tasks', t), 'R1', 'Total agent time')

    def test_total_bad_format(self):
        bad(self, R.check_content('tasks', tasks().replace('50 min', '50 hours')), 'R1', 'N min')

    def test_non_numeric_agent_min(self):
        bad(self, R.check_content('tasks', tasks(a1='soon')), 'R1', 'whole number')

    def test_unscheduled_task(self):
        bad(self, R.check_content('tasks', tasks(extra_block='\n### T-03\n- Agent min: 5\n- Human ref hours: 1\n')),
            'R1', 'not scheduled')

    def test_wave_cites_task_without_block(self):
        bad(self, R.check_content('tasks', tasks().replace('| 2 | T-02 |', '| 2 | T-09 |')), 'R1', 'T-09')

    def test_garbage_never_raises(self):
        for g in ('', None, '|||', '## Waves\n|', '\x00\ufffd', 5):
            self.assertIsInstance(R.check_content('tasks', g), list)
            self.assertIsInstance(R.check_content('spec', g), list)

    def test_other_kinds(self):
        self.assertEqual(R.check_content('plan', 'x'), [])
        self.assertEqual(R.check_content('qa', 'x'), [])
        self.assertEqual(R.check_content('nope', 'x'), [])


class TestR2(unittest.TestCase):
    def test_legit_all_run(self):
        ok(self, R.check_content('spec', spec()))

    def test_legit_waived_with_quote(self):
        ok(self, R.check_content('spec', spec({'1.5': ('waived', 'backend only', QUOTE)})))

    def test_missing_route(self):
        t = spec().split('## Pipeline route')[0]
        bad(self, R.check_content('spec', t), 'R2', 'no "## Pipeline route"')

    def test_missing_row(self):
        t = spec().replace('| 1.5 | run |  |  |\n', '')
        bad(self, R.check_content('spec', t), 'R2', 'step 1.5')

    def test_missing_minus_one_row(self):
        t = spec().replace('| -1 | run |  |  |\n', '')
        bad(self, R.check_content('spec', t), 'R2', 'step -1')

    def test_wrong_column_order(self):
        t = spec().replace('| Step | Status | Reason | Confirmation |', '| Step | Reason | Status | Confirmation |')
        bad(self, R.check_content('spec', t), 'R2', 'header')

    def test_invalid_status(self):
        bad(self, R.check_content('spec', spec({'2': ('skip', '', '')})), 'R2', 'Status must be')

    def test_waived_without_confirmation(self):
        bad(self, R.check_content('spec', spec({'2': ('waived', 'reason', '')})), 'R2', 'confirmation')

    def test_waived_short_quote(self):
        bad(self, R.check_content('spec', spec({'2': ('waived', 'r', 'user — "skip it"')})), 'R2', 'confirmation')

    def test_waived_without_user_prefix(self):
        bad(self, R.check_content('spec', spec({'2': ('waived', 'r', 'agent — "skip this step now"')})), 'R2')

    def test_waived_without_reason(self):
        bad(self, R.check_content('spec', spec({'2': ('waived', '', QUOTE)})), 'R2', 'Reason')

    def test_curly_quotes_and_hyphen_dash_ok(self):
        ok(self, R.check_content('spec', spec({'2': ('waived', 'r', 'user - \u201cno hace falta eso\u201d')})))

    def test_crlf(self):
        ok(self, R.check_content('spec', spec().replace('\n', '\r\n')))

    def test_heading_case_and_comment_ignored(self):
        t = spec().replace('## Pipeline route', '### PIPELINE ROUTE')
        ok(self, R.check_content('spec', t))
        commented = spec().replace('## Pipeline route', '<!--\n## Pipeline route').replace(
            '| 4 | run |  |  |\n', '| 4 | run |  |  |\n-->\n')
        bad(self, R.check_content('spec', commented), 'R2')


class TestR3(unittest.TestCase):
    def test_legit_three_source_kinds(self):
        ok(self, R.check_content('spec', spec()))

    def test_missing_source_column(self):
        cl = CHECKLIST.replace(' Source |', '').replace('|---|---|---|---|', '|---|---|---|')
        cl = re.sub(r'\| (user|repo|\[Proposed)[^|]*\|', '', cl)
        bad(self, R.check_content('spec', spec(checklist=cl)), 'R3')

    def test_source_wrong_position(self):
        cl = CHECKLIST.replace('| Answer | Source |', '| Source | Answer |')
        bad(self, R.check_content('spec', spec(checklist=cl)), 'R3', 'Source')

    def test_answer_without_source(self):
        cl = CHECKLIST.replace('| Faster pay | [Proposed — unconfirmed] |', '| Faster pay |  |')
        bad(self, R.check_content('spec', spec(checklist=cl)), 'R3', 'invalid Source')

    def test_short_quote(self):
        cl = CHECKLIST.replace('"es el modulo de checkout"', '"checkout"')
        bad(self, R.check_content('spec', spec(checklist=cl)), 'R3')

    def test_agent_invented_source(self):
        cl = CHECKLIST.replace('[Proposed — unconfirmed]', 'assumed')
        bad(self, R.check_content('spec', spec(checklist=cl)), 'R3')

    def test_blank_answer_is_open_question_not_violation(self):
        cl = CHECKLIST.replace('| Faster pay | [Proposed — unconfirmed] |', '|  |  |')
        ok(self, R.check_content('spec', spec(checklist=cl)))

    def test_no_checklist(self):
        bad(self, R.check_content('spec', route()), 'R3', 'no "Minimum')


DEBT = """## Visual debt

| Codes | Blocks spec | Status | Mockup source |
|---|---|---|---|
| SCREEN-04, SCREEN-05 | 007-x | {status} | {src} |
"""
WAIVE0 = {'0': ('waived', 'no ui', QUOTE), '1': ('waived', 'no ui', QUOTE), '1.5': ('waived', 'no ui', QUOTE)}


class TestR4(unittest.TestCase):
    def test_no_screens_no_debt_needed(self):
        ok(self, R.check_content('spec', spec(WAIVE0)))

    def test_debt_omitted(self):
        vs = R.check_content('spec', spec(WAIVE0, extra='FR-001 uses SCREEN-04 and SCREEN-05.'))
        bad(self, vs, 'R4', 'SCREEN-04')

    def test_debt_listed_open(self):
        t = spec(WAIVE0, extra='FR uses SCREEN-04, SCREEN-05.\n' + DEBT.format(status='open', src=''))
        ok(self, R.check_content('spec', t))
        self.assertEqual(len(R.open_visual_debt(t)), 1)

    def test_debt_partial_coverage(self):
        t = spec(WAIVE0, extra='SCREEN-04 SCREEN-05 SCREEN-09\n' + DEBT.format(status='open', src=''))
        bad(self, R.check_content('spec', t), 'R4', 'SCREEN-09')

    def test_resolved_needs_source(self):
        t = spec(WAIVE0, extra='SCREEN-04\n' + DEBT.format(status='resolved', src=''))
        bad(self, R.check_content('spec', t), 'R4', 'Mockup source')

    def test_resolved_with_source(self):
        t = spec(WAIVE0, extra='SCREEN-04 SCREEN-05\n' + DEBT.format(status='resolved', src='figma/abc'))
        ok(self, R.check_content('spec', t))
        self.assertEqual(R.open_visual_debt(t), [])

    def test_bad_status(self):
        t = spec(WAIVE0, extra='SCREEN-04\n' + DEBT.format(status='maybe', src=''))
        bad(self, R.check_content('spec', t), 'R4', 'open|resolved')

    def test_header_wrong(self):
        t = spec(WAIVE0, extra='SCREEN-04\n' + DEBT.format(status='open', src='').replace('Codes | Blocks spec', 'Blocks spec | Codes'))
        bad(self, R.check_content('spec', t), 'R4', 'header')

    def test_not_waived_screens_need_no_debt(self):
        ok(self, R.check_content('spec', spec(extra='SCREEN-04 is covered by mockup-audit.')))


class TestR6(unittest.TestCase):
    def sign(self, t):
        return t.replace('Approved: PENDING', f'Approved: 2026-10-01 hash:{R.approval_hash(t)}')

    def test_valid(self):
        self.assertTrue(R.approval_valid(self.sign(tasks())))

    def test_pending_invalid(self):
        self.assertFalse(R.approval_valid(tasks()))

    def test_hash_mismatch_after_edit(self):
        t = self.sign(tasks())
        self.assertFalse(R.approval_valid(t.replace('Agent min: 30', 'Agent min: 31')))

    def test_crlf_and_trailing_ws_stable(self):
        t = self.sign(tasks())
        self.assertTrue(R.approval_valid(t.replace('\n', '\r\n')))
        self.assertTrue(R.approval_valid(t.replace('Human ref hours: 8', 'Human ref hours: 8   ')))

    def test_hash_ignores_approved_line_and_is_12_hex(self):
        h = R.approval_hash(tasks())
        self.assertRegex(h, r'^[0-9a-f]{12}$')
        self.assertEqual(h, R.approval_hash(tasks().replace('Approved: PENDING', 'Approved: 2020-01-01 hash:abcdefabcdef')))

    def test_malformed_lines(self):
        for line in ('Approved: 2026-10-01', 'Approved: 2026-10-01 hash:short', 'Approved: yesterday hash:aaaaaaaaaaaa'):
            self.assertFalse(R.approval_valid(tasks().replace('Approved: PENDING', line)))
        self.assertFalse(R.approval_valid(None))

    def test_forged_hash(self):
        self.assertFalse(R.approval_valid(tasks().replace('Approved: PENDING', 'Approved: 2026-10-01 hash:000000000000')))


class TestR9(unittest.TestCase):
    def test_protected(self):
        for p in ('.aidd/evidence/events.toon', 'D:\\proj\\.aidd\\evidence\\.gitignore', '/a/b/.aidd/active_spec',
                  'x/.aidd/evidence', './.AIDD/Evidence/e.toon', 'a/../.aidd/active_spec', 'C:/p/.aidd/evidence/x/y'):
            self.assertTrue(R.is_protected_path(p), p)

    def test_not_protected(self):
        for p in ('.aidd/memory/x.md', 'src/active_spec.py', '.aidd/active_spec.md', 'specs/001/spec.md',
                  'evidence/x.toon', '.aidd/evidenceX/a', ''):
            self.assertFalse(R.is_protected_path(p), p)

    def test_garbage(self):
        self.assertFalse(R.is_protected_path(None) and False)


class FakeEv:
    """In-test evidence fake (no dependency on aidd_evidence)."""

    def __init__(self, rows=(), prompts=(), answers=()):
        self.rows = list(rows)
        for p in prompts:
            self.rows.append({'ts': 1.0, 'session': 's', 'kind': 'prompt', 'detail': {'text': p}})
        for a in answers:
            self.rows.append({'ts': 1.0, 'session': 's', 'kind': 'answer', 'detail': a if isinstance(a, dict) else {'text': a}})

    def find_root(self, start=None):
        return Path(start).parent.parent

    def events(self, root, session=None, kind=None, since=0.0):
        return [r for r in self.rows if (kind is None or r['kind'] == kind) and r['ts'] > since]

    def last_event(self, root, kind, session=None, since=0.0):
        e = self.events(root, session, kind, since)
        return e[-1] if e else None


def ev(kind, ts, **d):
    return {'ts': ts, 'session': 's', 'kind': kind, 'detail': d}


class TestDomains(unittest.TestCase):
    def mk(self, tasks_text, data_model=False):
        d = Path(tempfile.mkdtemp()) / 'specs' / '001-x'
        d.mkdir(parents=True)
        (d / 'tasks.md').write_text(tasks_text, encoding='utf-8')
        if data_model:
            (d / 'data-model.md').write_text('x', encoding='utf-8')
        return d

    def test_performance_always(self):
        self.assertEqual(R.required_domains(self.mk('nothing')), {'performance'})
        self.assertEqual(R.required_domains('/does/not/exist'), {'performance'})

    def test_ui_backend_database(self):
        self.assertEqual(R.required_domains(self.mk('SCREEN-01')), {'performance', 'ui'})
        self.assertEqual(R.required_domains(self.mk('CTL-3')), {'performance', 'ui'})
        self.assertEqual(R.required_domains(self.mk('COMP-2')), {'performance', 'ui'})
        self.assertEqual(R.required_domains(self.mk('API-007')), {'performance', 'backend'})
        self.assertEqual(R.required_domains(self.mk('x', data_model=True)), {'performance', 'database'})
        self.assertEqual(R.required_domains(self.mk('add a migration')), {'performance', 'database'})
        self.assertEqual(R.required_domains(self.mk('run script.sql')), {'performance', 'database'})
        self.assertEqual(R.required_domains(self.mk('SCREEN-1 API-2 schema')),
                         {'performance', 'ui', 'backend', 'database'})

    def test_domain_covered(self):
        fake = FakeEv([ev('code_edit', 100), ev('subagent', 90, head='ui review', desc=''),
                       ev('subagent', 110, head='x', desc='Pantalla audit'),
                       ev('subagent', 120, head='API contract check', desc='')])
        old = R._evidence
        R._evidence = lambda: fake
        try:
            self.assertTrue(R.domain_covered('r', 's', 'ui', 100))
            self.assertTrue(R.domain_covered('r', 's', 'backend', 100))
            self.assertFalse(R.domain_covered('r', 's', 'database', 100))
            self.assertFalse(R.domain_covered('r', 's', 'performance', 100))
            self.assertFalse(R.domain_covered('r', 's', 'ui', 115))  # only stale ui audit before edit... 110 < 115
            self.assertFalse(R.domain_covered('r', 's', 'bogus', 0))
        finally:
            R._evidence = old

    def test_domain_covered_without_evidence_module(self):
        old = R._evidence
        R._evidence = lambda: None
        try:
            self.assertFalse(R.domain_covered('r', 's', 'ui', 0))
        finally:
            R._evidence = old


class TestCheckSpecDir(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.d = self.root / 'specs' / '001-x'
        self.d.mkdir(parents=True)
        (self.root / 'src').mkdir()
        (self.root / 'src' / 'cart.py').write_text('x\n' * 30, encoding='utf-8')
        (self.root / 'a.py').write_text('x\n' * 30, encoding='utf-8')
        self._old = R._evidence

    def tearDown(self):
        R._evidence = self._old

    def write(self, name, text, mtime=1000.0):
        p = self.d / name
        p.write_text(text, encoding='utf-8')
        os.utime(p, (mtime, mtime))

    def use(self, fake):
        R._evidence = lambda: fake

    def good_spec(self):
        cl = CHECKLIST.replace('[Proposed — unconfirmed]', 'user — "pagar mas rapido por favor"')
        return spec(checklist=cl)

    def prompts(self):
        return ['es el modulo de checkout', 'pagar mas rapido por favor', 'no hace falta el flowmap']

    def test_static_only_no_evidence(self):
        self.write('spec.md', spec())
        R._evidence = lambda: None
        vs = R.check_spec_dir(self.d, static_only=True)
        self.assertEqual([v for v in vs if v['rule'] != 'R5'], [])
        self.assertEqual(vs, [])

    def test_missing_evidence_module_is_fail_closed(self):
        self.write('spec.md', self.good_spec())
        R._evidence = lambda: None
        bad(self, R.check_spec_dir(self.d), 'R5', 'Evidence module')

    def test_planning_ready(self):
        self.write('spec.md', self.good_spec())
        self.use(FakeEv([ev('find_spec', 1500, rebuilt=False), ev('subagent', 1600, head='Mapper', desc='')], self.prompts()))
        ok(self, R.check_spec_dir(self.d))

    def test_proposed_row_blocks(self):
        self.write('spec.md', spec())
        self.use(FakeEv([ev('find_spec', 1500), ev('subagent', 1600, head='Mapper')], self.prompts()))
        bad(self, R.check_spec_dir(self.d), 'R5', 'Proposed')

    def test_unverified_quote(self):
        self.write('spec.md', self.good_spec())
        self.use(FakeEv([ev('find_spec', 1500), ev('subagent', 1600)], ['something else entirely']))
        bad(self, R.check_spec_dir(self.d), 'R5', 'Quote not found')

    def test_waived_quote_verified_against_prompts(self):
        self.write('spec.md', spec({'1.5': ('waived', 'r', QUOTE)}, checklist=CHECKLIST.replace(
            '[Proposed — unconfirmed]', 'repo — a.py:1')))
        self.use(FakeEv([ev('find_spec', 1500), ev('subagent', 1600)], ['es el modulo de checkout']))
        bad(self, R.check_spec_dir(self.d), 'R5', 'flowmap')

    def test_no_mapper_after_spec_edit(self):
        self.write('spec.md', self.good_spec(), mtime=2000.0)
        self.use(FakeEv([ev('find_spec', 1500), ev('subagent', 1600)], self.prompts()))
        bad(self, R.check_spec_dir(self.d), 'R5', 'Mapper')

    def test_no_find_spec(self):
        self.write('spec.md', self.good_spec())
        self.use(FakeEv([ev('subagent', 1600)], self.prompts()))
        bad(self, R.check_spec_dir(self.d), 'R5', 'find_spec')

    def test_open_debt_reported(self):
        t = self.good_spec().replace(route(), route(WAIVE0)) + 'SCREEN-04 SCREEN-05\n' + DEBT.format(status='open', src='').replace('007-x', '001-x')
        self.write('spec.md', t)
        self.use(FakeEv([ev('find_spec', 1500), ev('subagent', 1600)], self.prompts()))
        bad(self, R.check_spec_dir(self.d), 'R4', 'Open visual debt')

    def test_debt_codes_found_in_plan_and_sibling_specs(self):
        t = self.good_spec().replace(route(), route(WAIVE0))
        self.write('spec.md', t)
        self.write('plan.md', 'plan cites SCREEN-07')
        other = self.root / 'specs' / '002-y'
        other.mkdir()
        (other / 'spec.md').write_text('uses SCREEN-08 and SCREEN-09', encoding='utf-8')
        (other / 'mockup-audit.md').write_text('| SCREEN-09 | audited |\n', encoding='utf-8')
        vs = R.check_spec_dir(self.d, static_only=True)
        msg = ' '.join(v['message'] for v in vs if v['rule'] == 'R4')
        self.assertIn('SCREEN-07', msg)
        self.assertIn('SCREEN-08', msg)
        self.assertNotIn('SCREEN-09', msg)

    def test_tasks_chain_and_approval(self):
        self.write('spec.md', self.good_spec(), mtime=1000.0)
        self.write('plan.md', 'plan', mtime=1700.0)
        t = tasks()
        self.write('tasks.md', t, mtime=1800.0)
        self.use(FakeEv([ev('find_spec', 1500), ev('subagent', 1600)], self.prompts()))
        vs = R.check_spec_dir(self.d)
        bad(self, vs, 'R5', 'plan.md')      # no subagent after plan.md
        bad(self, vs, 'R6', 'pending')
        signed = t.replace('Approved: PENDING', f'Approved: 2026-10-01 hash:{R.approval_hash(t)}')
        self.write('tasks.md', signed, mtime=1800.0)
        self.use(FakeEv([ev('find_spec', 1500), ev('subagent', 1900)], self.prompts()))
        ok(self, R.check_spec_dir(self.d))
        self.write('tasks.md', signed.replace('Agent min: 30', 'Agent min: 31'), mtime=1800.0)
        bad(self, R.check_spec_dir(self.d), 'R6', 'hash mismatch')

    def test_graph_rebuilt_needs_subagent_after(self):
        self.write('spec.md', self.good_spec(), mtime=1000.0)
        self.write('plan.md', 'plan', mtime=1100.0)
        self.write('tasks.md', tasks(), mtime=1200.0)
        self.use(FakeEv([ev('subagent', 1300), ev('find_spec', 1400, rebuilt=True)], self.prompts()))
        bad(self, R.check_spec_dir(self.d), 'R5', 'graph index was rebuilt')

    def test_r7_qa_audit_domains(self):
        self.write('spec.md', self.good_spec(), mtime=1000.0)
        self.write('tasks.md', tasks().replace('COMP-001', 'COMP-001 API-002'), mtime=1200.0)
        self.write('qa-audit.md', 'qa', mtime=3000.0)
        base = [ev('find_spec', 1500), ev('subagent', 1600), ev('code_edit', 2000, spec='001-x')]
        self.use(FakeEv(base + [ev('subagent', 2100, head='performance best practice')], self.prompts()))
        vs = R.check_spec_dir(self.d)
        self.assertEqual({v['message'].split()[1] for v in vs if v['rule'] == 'R7'}, {'ui', 'backend'})
        self.use(FakeEv(base + [ev('subagent', 2100, head='performance'), ev('subagent', 2200, desc='api contract'),
                        ev('subagent', 2300, desc='ui mockup audit')],
                        self.prompts()))
        self.assertEqual([v for v in R.check_spec_dir(self.d) if v['rule'] == 'R7'], [])

    def test_missing_dir_and_garbage_never_raise(self):
        R._evidence = lambda: None
        self.assertIsInstance(R.check_spec_dir(self.root / 'nope'), list)
        self.assertIsInstance(R.check_spec_dir(None), list)


class TestTemplates(unittest.TestCase):
    TREES = (REPO / 'skill' / 'templates', REPO / 'adapters' / 'dot-aidd' / 'templates')

    def read(self, tree, name):
        return (tree / name).read_text(encoding='utf-8')

    def test_trees_consistent(self):
        for n in ('spec.md', 'STATE.md'):
            self.assertEqual(self.read(self.TREES[0], n), self.read(self.TREES[1], n), n)
        # tasks.md differs intentionally (no Tracker ref / Status columns in the dot-aidd copy)
        self.assertIn('Tracker ref', self.read(self.TREES[0], 'tasks.md'))
        self.assertNotIn('Tracker ref', self.read(self.TREES[1], 'tasks.md'))
        a, b = (self.read(t, 'tasks.md') for t in self.TREES)
        for needle in ('## Waves', 'Agent min:', 'Human ref hours:', 'Total agent time (critical path)', 'Approved: PENDING'):
            self.assertIn(needle, a)
            self.assertIn(needle, b)
        self.assertNotIn('Estimated hours', a + b)
        # 003: both trees carry the new files and sections
        self.assertEqual(self.read(self.TREES[0], 'traceability.md'), self.read(self.TREES[1], 'traceability.md'))
        needles = {
            'qa-audit.md': ('## Execution evidence', '| Code | Kind | Evidence | Verified by |', '## Bug reports',
                            '| # | Code | Symptom | Root cause | Fix | Pattern sweep |', 'adb devices'),
            'mockup-audit.md': ('Destination', 'Data source', 'States'),
            'plan.md': ('## Entry route', '## Device targets'),
            'spec.md': ('## Acceptance cases', '| Case | Real data (id) | Expected | Edge? |', '## Optional Align questions'),
            'contracts.md': ('Contract version:', 'Contract hash: PENDING'),
            'charter.md': ('SAP pitfalls', '`**/*.xml`'),
            'STATE.md': ('## Test state',),
            'tasks.md': ('| View / logic |', '- Kind:'),
            'design-system/components-index.md': ('Consumers',),
            'traceability.md': ('Mockup field', 'Room/store', 'DTO', 'API', 'SP', 'Filled-by'),
        }
        for tree in self.TREES:
            for name, needs in needles.items():
                txt = self.read(tree, name)
                for needle in needs:
                    self.assertIn(needle, txt, f'{tree.parent.name}/{name}: {needle}')
            self.assertNotIn('New view vs. reuse', self.read(tree, 'tasks.md'))
        self.assertEqual(self.read(self.TREES[0], 'spec.md').count('→ Step 2 align question'), 7)
        # the optional Align questions never become checklist rows
        for tree in self.TREES:
            rows = [ln for ln in self.read(tree, 'spec.md').splitlines() if ln.endswith('| → Step 2 align question |')]
            self.assertEqual(len(rows), 7)

    def test_qa_template_green_checks_only_inside_comment(self):
        for tree in self.TREES:
            raw = self.read(tree, 'qa-audit.md')
            outside = re.sub(r'<!--.*?-->', '', raw, flags=re.S)
            rows = [ln for ln in outside.splitlines() if ln.startswith('|')]
            self.assertFalse([ln for ln in rows if '✅' in ln], 'placeholder green-check row outside a comment')
            self.assertIn('✅', raw)  # the example still exists, inside the comment

    def test_tasks_template_has_no_reuse_word_beside_codes(self):
        for tree in self.TREES:
            for ln in self.read(tree, 'tasks.md').splitlines():
                if ln.startswith('| T-') or ln.startswith('- Kind:'):
                    self.assertIsNone(re.search(r'reutiliza|remapea|envuelve|wrap|reus|rewir', ln, re.I), ln)

    def test_spec_template_filled_passes(self):
        for tree in self.TREES:
            raw = self.read(tree, 'spec.md')
            self.assertEqual(R.check_content('spec', raw), [])  # blanks = open questions, route all `run`
            lines, n = [], 0
            for line in raw.replace('\r\n', '\n').split('\n'):
                if line.endswith('| → Step 2 align question |'):
                    n += 1
                    src = '[Proposed — unconfirmed]' if n == 1 else 'repo — a.py'
                    line = line.replace('| | |', f'| yes | {src} |', 1)
                lines.append(line)
            filled = '\n'.join(lines)
            self.assertEqual(n, 7)
            self.assertNotEqual(filled, raw)
            ok(self, R.check_content('spec', filled))
            # an answer with no Source is reported
            broken = raw.replace('| Which module/area of the system? | | |', '| Which module/area of the system? | x | |')
            bad(self, R.check_content('spec', broken), 'R3')

    def test_tasks_template_unfilled_reported_sanely_then_filled_passes(self):
        for tree in self.TREES:
            raw = self.read(tree, 'tasks.md')
            vs = R.check_content('tasks', raw)
            self.assertEqual(rules(vs), {'R1'})
            self.assertTrue(all(v['fix'] for v in vs))
            filled = re.sub(r'(Agent min:) \[[^\]]*\]', lambda m, c=iter([30, 20]): f'{m.group(1)} {next(c)}', raw)
            filled = re.sub(r'(Human ref hours:) \[[^\]]*\]', r'\1 4', filled)
            filled = re.sub(r'(\| 1 \| T-01 \| )\[[^\]]*\]( \| )\[[^\]]*\]', r'\g<1>30\g<2>4', filled)
            filled = re.sub(r'(\| 2 \| T-02 \| )\[[^\]]*\]( \| )\[[^\]]*\]', r'\g<1>20\g<2>4', filled)
            filled = re.sub(r'(critical path\): )\[[^\]]*\]', r'\g<1>50', filled)
            ok(self, R.check_content('tasks', filled))
            self.assertFalse(R.approval_valid(filled))  # still PENDING
            signed = filled.replace('Approved: PENDING', f'Approved: 2026-10-01 hash:{R.approval_hash(filled)}')
            self.assertTrue(R.approval_valid(signed))

    def test_state_template_mentions_status(self):
        self.assertIn('aidd status', self.read(self.TREES[0], 'STATE.md'))


# ============================================================ Rev 1 amendments (adversarial)
import time  # noqa: E402


def mkroot():
    root = Path(tempfile.mkdtemp())
    (root / 'specs').mkdir()
    return root


def put(path, text, mtime=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    if mtime:
        os.utime(path, (mtime, mtime))


class TestM1M2Alignment(unittest.TestCase):
    def setUp(self):
        self.root = mkroot()
        self.d = self.root / 'specs' / '001-x'
        self._old = R._evidence
        (self.root / 'a.py').write_text('x\n' * 30, encoding='utf-8')

    def tearDown(self):
        R._evidence = self._old

    def run_dir(self, spec_text, prompts=('es el modulo de checkout', 'pagar mas rapido por favor'), rows=(), answers=()):
        put(self.d / 'spec.md', spec_text, 1000.0)
        R._evidence = lambda: FakeEv([ev('find_spec', 1500), ev('subagent', 1600)] + list(rows), prompts, answers)
        return R.check_spec_dir(self.d)

    def test_blank_checklist_passes_check_content_but_blocks_planning_as_r5(self):
        blank = re.sub(r'\| (?:Checkout|Modification|Faster pay) \| [^|]*\|', '|  |  |', CHECKLIST)
        sp = spec(checklist=blank)
        ok(self, R.check_content('spec', sp))                      # raw template stays accepted
        bad(self, self.run_dir(sp), 'R5', 'unanswered')

    def test_raw_template_is_r5_unanswered_in_check_spec_dir(self):
        raw = (REPO / 'skill' / 'templates' / 'spec.md').read_text(encoding='utf-8')
        bad(self, self.run_dir(raw), 'R5', 'unanswered')

    def test_fully_answered_passes(self):
        cl = CHECKLIST.replace('[Proposed — unconfirmed]', 'user — "pagar mas rapido por favor"').replace(
            'repo — src/cart.py:12', 'repo — a.py:12')
        ok(self, self.run_dir(spec(checklist=cl)))

    def test_repo_source_must_exist(self):
        cl = CHECKLIST.replace('[Proposed — unconfirmed]', 'user — "pagar mas rapido por favor"')
        bad(self, self.run_dir(spec(checklist=cl.replace('src/cart.py:12', 'nonexistent.py'))), 'R3', 'not an existing file')
        ok(self, [v for v in self.run_dir(spec(checklist=cl.replace('src/cart.py:12', 'a.py:3'))) if v['rule'] == 'R3'])

    def test_repo_source_cannot_escape_root(self):
        cl = CHECKLIST.replace('[Proposed — unconfirmed]', 'user — "pagar mas rapido por favor"')
        bad(self, self.run_dir(spec(checklist=cl.replace('src/cart.py:12', '../../../../Windows/win.ini'))),
            'R3', 'not inside the project root')

    def test_proposed_in_answer_is_unconfirmed_whatever_the_source(self):
        cl = CHECKLIST.replace('| Faster pay | [Proposed — unconfirmed] |',
                               '| Proposed: faster pay | user — "pagar mas rapido por favor" |')
        cl = cl.replace('src/cart.py:12', 'a.py:3')
        bad(self, self.run_dir(spec(checklist=cl)), 'R5', 'Proposed')


class TestM3Quotes(unittest.TestCase):
    def setUp(self):
        self.fake = FakeEv()

    def q(self, quote, since=0.0):
        return R.quote_verified(self.fake, 'r', quote, since)

    def test_three_word_quote_from_unrelated_prompt_rejected(self):
        self.fake = FakeEv(prompts=['please do not touch the checkout module today'])
        self.assertFalse(self.q('touch the checkout'))           # 3 words, present, still not enough
        self.assertTrue(self.q('do not touch the checkout'))      # 5 words
        self.assertFalse(self.q('do not touch the CHECKOUT module tomorrow'))

    def test_accents_and_punctuation_normalised(self):
        self.fake = FakeEv(prompts=['Sí, hazlo así: NO hace falta el flowmap!'])
        self.assertTrue(self.q('no hace falta el flowmap'))
        self.assertTrue(self.q('si hazlo asi no hace'))

    def test_whole_words_not_substring(self):
        self.fake = FakeEv(prompts=['the unfinished business is large'])
        self.assertFalse(self.q('finished business is large now'))
        self.assertFalse(self.q('finished business'))

    def test_two_words_ok_only_in_answers(self):
        self.fake = FakeEv(prompts=['aprobar tareas ahora'], answers=[
            {'text': '"Approve tasks?"="Approve tasks"', 'pairs': [['Approve tasks?', 'Approve tasks']]}])
        self.assertTrue(self.q('Approve tasks'))
        self.assertFalse(self.q('Approve tasks now please'))
        self.fake = FakeEv(prompts=['aprobar tareas ahora'])
        self.assertFalse(self.q('aprobar tareas'))                # 2 words in a prompt: rejected

    def test_agent_cannot_self_certify_through_question_text(self):
        self.fake = FakeEv(answers=[{'text': '"skip the flowmap entirely"="No"',
                                     'pairs': [['skip the flowmap entirely', 'No']]}])
        self.assertFalse(self.q('skip the'))                      # only in the question, not the answer

    def test_answer_without_pairs_is_never_evidence(self):
        self.fake = FakeEv(answers=['User has answered your questions: "Waive step 1?"="Yes, waive it"'])
        self.assertFalse(self.q('waive it'))      # D2: raw text is never evidence, only `pairs`
        self.assertFalse(self.q('Waive step'))

    def test_only_events_after_first_spec_edit(self):
        self.fake = FakeEv(rows=[ev('prompt', 50, text='hazlo todo como dije antes')])
        self.assertTrue(self.q('hazlo todo como dije antes', since=0.0))
        self.assertFalse(self.q('hazlo todo como dije antes', since=60.0))

    def test_spec_first_edit_ts(self):
        f = FakeEv(rows=[ev('spec_edit', 70, spec='001-x'), ev('spec_edit', 40, spec='001-x'),
                         ev('spec_edit', 5, spec='002-y')])
        self.assertEqual(R.spec_first_edit_ts(f, 'r', '001-x'), 40)
        self.assertEqual(R.spec_first_edit_ts(f, 'r', '009-z'), 0.0)

    def test_check_spec_dir_uses_first_edit_gate(self):
        root = mkroot()
        d = root / 'specs' / '001-x'
        (root / 'a.py').write_text('x\n' * 30, encoding='utf-8')
        cl = CHECKLIST.replace('[Proposed — unconfirmed]', 'repo — a.py:1').replace('src/cart.py:12', 'a.py:3')
        put(d / 'spec.md', spec(checklist=cl), 1000.0)
        old = R._evidence
        try:
            rows = [ev('find_spec', 1500), ev('subagent', 1600), ev('spec_edit', 900, spec='001-x'),
                    {'ts': 100.0, 'session': 's', 'kind': 'prompt', 'detail': {'text': 'es el modulo de checkout'}}]
            R._evidence = lambda: FakeEv(rows)
            bad(self, R.check_spec_dir(d), 'R5', 'Quote not found')   # prompt predates the first spec edit
            rows[-1]['ts'] = 950.0
            ok(self, R.check_spec_dir(d))
        finally:
            R._evidence = old


class TestM4Tables(unittest.TestCase):
    def test_blank_line_does_not_split_the_table(self):
        garbage = route().replace('| 4 | run |  |  |\n', '| 4 | run |  |  |\n\n| 2 | banana |  |  |\n')
        vs = R.check_content('spec', spec().replace(route(), garbage))
        self.assertTrue([v for v in vs if v['rule'] == 'R2'], vs)

    def test_garbage_row_after_blank_in_waves_and_debt(self):
        t = tasks().replace('| 2 | T-02 | 20 | 4 |\n', '| 2 | T-02 | 20 | 4 |\n\n| 3 | T-02 | huge | 1 |\n')
        bad(self, R.check_content('tasks', t), 'R1')
        d = spec(WAIVE0, extra='SCREEN-04\n' + DEBT.format(status='open', src='') + '\n| nothing | 007-x | maybe | |\n')
        bad(self, R.check_content('spec', d), 'R4')

    def test_table_ends_at_next_heading(self):
        t = spec().replace(route(), route() + '\n## Notes\n\n| Step | Status | Reason | Confirmation |\n|---|---|---|---|\n| 9 | zz | | |\n')
        ok(self, R.check_content('spec', t))

    def test_dash_cell_row_is_not_swallowed_as_separator(self):
        t = route().replace('| 4 | run |  |  |\n', '| 4 | run |  |  |\n| - | - | - | - |\n')
        bad(self, R.check_content('spec', spec().replace(route(), t)), 'R2', 'unknown step')

    def test_duplicate_route_rows_are_a_violation(self):
        t = spec().replace(route(), route() + '| 2 | RUN | | |\n')
        bad(self, R.check_content('spec', t), 'R2', 'duplicate')

    def test_waived_casing_normalised(self):
        ok(self, R.check_content('spec', spec({'1.5': ('WAIVED', 'backend only', QUOTE)})))
        ok(self, R.check_content('spec', spec({'1.5': ('**Waived**', 'backend only', QUOTE)})))
        self.assertEqual(R.parse_route(spec({'1.5': ('Waived', 'r', QUOTE)}))['1.5']['status'], 'waived')


def seed_specs(root, names=('001-x', '007-y')):
    for n in names:
        (root / 'specs' / n).mkdir(parents=True, exist_ok=True)


class TestM5Debt(unittest.TestCase):
    def setUp(self):
        self.root = mkroot()
        seed_specs(self.root)
        self.d = self.root / 'specs' / '001-x'

    def spec_with(self, row, extra='SCREEN-04 here.'):
        t = spec(WAIVE0, extra=extra + '\n## Visual debt\n\n| Codes | Blocks spec | Status | Mockup source |\n|---|---|---|---|\n' + row + '\n')
        put(self.d / 'spec.md', t)
        return t

    def msgs(self, extra_texts=None):
        return ' | '.join(v['message'] for v in R.check_debt(self.root, '001-x', extra_texts))

    def test_blocks_spec_must_exist(self):
        self.spec_with('| SCREEN-04 | 999 | open | |')
        self.assertIn('not an existing spec id', self.msgs())
        self.spec_with('| SCREEN-04 | n/a | open | |')
        self.assertIn('not an existing spec id', self.msgs())
        for ok_ref in ('007', '7', '007-y', '001-x'):
            self.spec_with(f'| SCREEN-04 | {ok_ref} | open | |')
            self.assertEqual(R.check_debt(self.root, '001-x', {}), [], ok_ref)

    def test_resolved_junk_sources_rejected(self):
        for junk in ('n/a', 'none', 'tbd', '-', '?', 'resolved'):
            self.spec_with(f'| SCREEN-04 | 001 | resolved | {junk} |')
            self.assertIn('Mockup source', self.msgs(), junk)
        self.spec_with('| SCREEN-04 | 001 | resolved | n/a |')
        bad(self, R.check_content('spec', (self.d / 'spec.md').read_text(encoding='utf-8')), 'R4', 'Mockup source')

    def test_resolved_needs_existing_file_or_url_and_audit_rows(self):
        put(self.root / 'mockups' / 'home.html', '<html/>')
        self.spec_with('| SCREEN-04 | 001 | resolved | mockups/nothere.html |')
        self.assertIn('not an existing file', self.msgs())
        self.spec_with('| SCREEN-04 | 001 | resolved | mockups/home.html |')
        self.assertIn('no mockup-audit.md table row', self.msgs())     # file ok, audit row missing
        put(self.d / 'mockup-audit.md', '# audit\n\n| SCREEN-04 | home | ok |\n')
        self.assertEqual(R.check_debt(self.root, '001-x', {}), [])
        for good in ('https://x.example/mock', 'figma:abc123'):
            self.spec_with(f'| SCREEN-04 | 001 | resolved | {good} |')
            self.assertEqual(R.check_debt(self.root, '001-x', {}), [], good)

    def test_audit_row_in_another_spec_counts_but_prose_mention_does_not(self):
        self.spec_with('| SCREEN-04 | 001 | resolved | figma:abc |')
        put(self.root / 'specs' / '007-y' / 'mockup-audit.md', 'SCREEN-04 mentioned in prose only\n')
        self.assertIn('no mockup-audit.md table row', self.msgs())
        put(self.root / 'specs' / '007-y' / 'mockup-audit.md', '| SCREEN-04 | ok |\n')
        self.assertEqual(R.check_debt(self.root, '001-x', {}), [])

    def test_escape_outside_root_is_not_a_source(self):
        self.spec_with('| SCREEN-04 | 001 | resolved | ../../../Windows/win.ini |')
        self.assertIn('not an existing file', self.msgs())

    def test_screen_case_insensitive_and_in_comments(self):
        vs = R.check_content('spec', spec(WAIVE0, extra='uses screen-01 and Screen-2'))
        bad(self, vs, 'R4', 'SCREEN-01')
        bad(self, vs, 'R4', 'SCREEN-2')
        bad(self, R.check_content('spec', spec(WAIVE0, extra='<!-- SCREEN-07 hidden in a comment -->')), 'R4', 'SCREEN-07')
        listed = spec(WAIVE0, extra='screen-01\n' + DEBT.format(status='open', src='').replace('SCREEN-04, SCREEN-05', 'screen-01'))
        ok(self, R.check_content('spec', listed))

    def test_would_be_plan_and_contracts_content(self):
        put(self.d / 'spec.md', spec(WAIVE0))
        self.assertEqual(R.check_debt(self.root, '001-x', {}), [])
        self.assertIn('SCREEN-09', self.msgs({'plan.md': 'the plan adds screen-09'}))
        self.assertIn('SCREEN-11', self.msgs({'specs/001-x/contracts.md': 'SCREEN-11 in contracts'}))
        self.assertNotIn('SCREEN-12', self.msgs({'plan.md': 'ok'}))
        put(self.d / 'mockup-audit.md', '| SCREEN-09 | audited |\n')
        self.assertEqual(R.check_debt(self.root, '001-x', {'plan.md': 'screen-09'}), [])

    def test_open_debt_blocking_across_specs(self):
        hdr = '\n## Visual debt\n\n| Codes | Blocks spec | Status | Mockup source |\n|---|---|---|---|\n'
        put(self.d / 'spec.md', spec(WAIVE0, extra='SCREEN-04\n' + DEBT.format(status='open', src='')))   # names 007-x (absent)
        put(self.root / 'specs' / '007-y' / 'spec.md',
            spec(extra=hdr + '| SCREEN-30 | 001-x | open | |\n| SCREEN-31 | 001-x | resolved | figma:z |\n| SCREEN-32 | 424 | open | |\n'))
        b = R.open_debt_blocking(self.root)
        self.assertEqual([r['in_spec'] for r in b['001-x']], ['007-y'])
        self.assertEqual(sorted(b['001-x'][0]['codes']), ['SCREEN-30'])
        self.assertNotIn('424', b)
        put(self.d / 'spec.md', spec(WAIVE0, extra='SCREEN-04\n' + DEBT.format(status='open', src='').replace('007-x', '007-y')))
        self.assertEqual([r['in_spec'] for r in R.open_debt_blocking(self.root)['007-y']], ['001-x'])
        self.assertEqual(R.open_debt_blocking(self.root / 'nope'), {})

    def test_check_spec_dir_reports_cross_spec_debt_as_r4(self):
        hdr = '\n## Visual debt\n\n| Codes | Blocks spec | Status | Mockup source |\n|---|---|---|---|\n'
        put(self.root / 'specs' / '007-y' / 'spec.md', spec(extra=hdr + '| SCREEN-30 | 001 | open | |\n'))
        (self.root / 'a.py').write_text('x\n' * 30, encoding='utf-8')
        cl = CHECKLIST.replace('[Proposed — unconfirmed]', 'repo — a.py:1').replace('src/cart.py:12', 'a.py:3')
        put(self.d / 'spec.md', spec(checklist=cl), 1000.0)
        old = R._evidence
        R._evidence = lambda: FakeEv([ev('find_spec', 1500), ev('subagent', 1600)], ['es el modulo de checkout'])
        try:
            bad(self, R.check_spec_dir(self.d), 'R4', 'listed in specs/007-y')
        finally:
            R._evidence = old


class TestM7Hash(unittest.TestCase):
    def sign(self, t):
        return t.replace('Approved: PENDING', f'Approved: 2026-10-01 hash:{R.approval_hash(t)}')

    def table_tasks(self, status='', tracker=''):
        return tasks().replace('| Task | Codes |\n|---|---|\n| T-01 | COMP-001 |',
                               f'| Task | Codes | Tracker ref | Status |\n|---|---|---|---|\n| T-01 | COMP-001 | {tracker} | {status} |')

    def test_status_and_tracker_cells_do_not_change_hash(self):
        h = R.approval_hash(self.table_tasks())
        self.assertNotEqual(h, R.approval_hash(tasks()))   # sanity: the table is really part of the text
        self.assertEqual(h, R.approval_hash(self.table_tasks(status='In Progress', tracker='#42')))
        signed = self.sign(self.table_tasks())
        self.assertTrue(R.approval_valid(signed.replace('|  |  |', '| #7 | Done |')))

    def test_other_cells_still_change_hash(self):
        self.assertNotEqual(R.approval_hash(self.table_tasks()),
                            R.approval_hash(self.table_tasks().replace('COMP-001', 'COMP-002')))

    def test_named_lines_excluded(self):
        base = tasks()
        for line in ('Status: done', '- **Tracker ref:** #9', 'PR/Spec ref: pr 12', '  - status : x'):
            self.assertEqual(R.approval_hash(base), R.approval_hash(base.replace('### T-01\n', f'### T-01\n{line}\n')), line)
        self.assertNotEqual(R.approval_hash(base), R.approval_hash(base.replace('### T-01\n', '### T-01\nScope: wider\n')))

    def test_hash_neutral_heading_trailing_space_still_valid(self):
        signed = self.sign(tasks())
        self.assertTrue(R.approval_valid(signed.replace('### T-01\n', '### T-01 \n')))
        self.assertFalse(R.approval_valid(signed.replace('### T-01\n', '### T-01x\n')))

    def test_duplicate_approval_lines_void_it(self):
        signed = self.sign(tasks())
        line = [l for l in signed.split('\n') if l.startswith('Approved:')][0]
        self.assertFalse(R.approval_valid(signed + '\n' + line + '\n'))
        self.assertFalse(R.approval_valid(signed + '\nApproved: PENDING\n'))
        self.assertFalse(R.approval_valid('Approved: PENDING\n' + signed))

    def test_approval_line_first_valid_only(self):
        t = 'x\nApproved: nope\nApproved: 2026-10-01 hash:AAAAAAAAAAAA\nApproved: 2026-11-01 hash:bbbbbbbbbbbb\n'
        self.assertEqual(R.approval_line(t), ('2026-10-01', 'aaaaaaaaaaaa'))
        self.assertIsNone(R.approval_line('Approved: PENDING'))
        self.assertIsNone(R.approval_line(None))

    def test_check_spec_dir_flags_duplicate_approval(self):
        root = mkroot()
        d = root / 'specs' / '001-x'
        put(d / 'spec.md', spec())
        put(d / 'tasks.md', self.sign(tasks()) + '\nApproved: 2026-10-02 hash:000000000000\n')
        bad(self, R.check_spec_dir(d, static_only=True), 'R6', 'several')


class TestM9Domains(unittest.TestCase):
    def mk(self, tasks_text):
        root = mkroot()
        d = root / 'specs' / '001-x'
        put(d / 'tasks.md', tasks_text)
        return root, d

    def with_ev(self, fake):
        old = R._evidence
        R._evidence = lambda: fake
        self.addCleanup(setattr, R, '_evidence', old)

    def test_one_generic_subagent_covers_only_one_domain(self):
        root, d = self.mk('SCREEN-1 API-2 schema')
        fake = FakeEv([ev('subagent', 10, head='check ui backend api database sql performance')])
        self.with_ev(fake)
        self.assertEqual(len(R.uncovered_domains(root, 's', '001-x', 0)), 3)   # 4 required, 1 subagent -> 1 covered
        fake.rows += [ev('subagent', 11, head='ui mockup audit'), ev('subagent', 12, desc='api contract'),
                      ev('subagent', 13, head='database sql review')]
        self.assertEqual(R.uncovered_domains(root, 's', '001-x', 0), set())   # 4 distinct subagents (generic -> perf)
        self.assertEqual(len(R.uncovered_domains(root, 's', '001-x', 12)), 3)   # only #13 is newer than ts 12

    def test_matching_is_optimal_not_first_come(self):
        root, d = self.mk('SCREEN-1 API-2')
        # e1 matches ui+backend, e2 only ui: naive greedy e1->ui would leave backend uncovered
        self.with_ev(FakeEv([ev('subagent', 10, head='ui api review'), ev('subagent', 11, head='ui check'),
                             ev('subagent', 12, head='performance')]))
        self.assertEqual(R.uncovered_domains(root, 's', '001-x', 0), set())

    def test_substrings_do_not_match(self):
        root, d = self.mk('SCREEN-1 API-2 schema')
        self.with_ev(FakeEv([ev('subagent', 10, head='rapid capital quick build', desc='suite requirements guide')]))
        self.assertEqual(R.uncovered_domains(root, 's', '001-x', 0), {'ui', 'backend', 'database', 'performance'})
        for dom, s in (('ui', 'rapid'), ('ui', 'quick'), ('ui', 'build'), ('backend', 'capital'), ('backend', 'rapid'),
                       ('database', 'mysqlite'), ('performance', 'nonperformance')):
            self.assertIsNone(R.DOMAIN_RE[dom].search(s), (dom, s))
        for dom, s in (('ui', 'UI audit'), ('ui', 'Pantalla'), ('backend', 'API/contract'), ('database', 'migración'),
                       ('database', 'base de datos'), ('performance', 'best practices')):
            self.assertIsNotNone(R.DOMAIN_RE[dom].search(s), (dom, s))

    def test_compat_wrapper_and_missing_evidence(self):
        self.with_ev(FakeEv([ev('subagent', 10, head='ui review')]))
        self.assertTrue(R.domain_covered('r', 's', 'ui', 0))
        self.assertFalse(R.domain_covered('r', 's', 'ui', 10))
        R._evidence = lambda: None
        root, d = self.mk('SCREEN-1')
        self.assertEqual(R.uncovered_domains(root, 's', '001-x', 0), {'ui', 'performance'})

    def test_r7_in_check_spec_dir_needs_distinct_subagents(self):
        root = mkroot()
        d = root / 'specs' / '001-x'
        put(d / 'spec.md', spec(), 1000.0)
        put(d / 'tasks.md', tasks().replace('COMP-001', 'COMP-001 API-002'), 1200.0)
        put(d / 'qa-audit.md', 'qa', 3000.0)
        base = [ev('find_spec', 1500), ev('subagent', 1600), ev('code_edit', 2000, spec='001-x')]
        self.with_ev(FakeEv(base + [ev('subagent', 2100, head='ui backend api performance review all')], ['x']))
        vs = [v for v in R.check_spec_dir(d) if v['rule'] == 'R7']
        self.assertEqual(len(vs), 2, vs)


class TestMDos(unittest.TestCase):
    def timed(self, fn):
        t0 = time.perf_counter()
        r = fn()
        return r, time.perf_counter() - t0

    def test_five_mb_blank_file_is_never_scanned_and_fast(self):
        big = '\n' * (5 * 1024 * 1024)
        r, t = self.timed(lambda: R.approval_hash(big))
        self.assertLess(t, 1.0)
        self.assertEqual(len(r), 12)
        self.assertFalse(R.approval_valid(big + 'Approved: PENDING'))
        self.assertIsNone(R.approval_line(big))
        for kind, rule in (('tasks', 'R1'), ('spec', 'R2')):
            vs, t = self.timed(lambda: R.check_content(kind, big))
            self.assertLess(t, 1.0)
            bad(self, vs, rule, 'too large')
        root = mkroot()
        d = root / 'specs' / '001-x'
        put(d / 'spec.md', big)
        put(d / 'tasks.md', big)
        vs, t = self.timed(lambda: R.check_spec_dir(d, static_only=True))
        self.assertLess(t, 1.0)
        self.assertEqual({v['rule'] for v in vs}, {'R1', 'R2'}, vs)
        old = R._evidence
        R._evidence = lambda: FakeEv()
        try:
            vs, t = self.timed(lambda: R.check_spec_dir(d))
        finally:
            R._evidence = old
        self.assertLess(t, 1.0)
        self.assertEqual(R.check_debt(root, '001-x', {'plan.md': big})[0]['rule'], 'R4')

    def test_just_under_limit_blank_lines_still_fast(self):
        blank = '\n' * (R.MAX_CHARS - 10)
        for fn in (lambda: R.approval_hash(tasks() + blank), lambda: R.check_content('tasks', tasks() + blank),
                   lambda: R.check_content('spec', spec() + blank), lambda: R.approval_valid(tasks() + blank),
                   lambda: R.open_visual_debt(spec() + blank)):
            _r, t = self.timed(fn)
            self.assertLess(t, 1.5)

    def test_pathological_lines_are_linear(self):
        for text in ('<!--' * 400000, '|' * 1000000, '| ' * 500000, 'user — "' + 'a ' * 100000,
                     ('Approved:' + ' ' * 1000 + '\n') * 1000, '#' * 1000000):
            for fn in (lambda: R.check_content('spec', text), lambda: R.check_content('tasks', text),
                       lambda: R.approval_hash(text), lambda: R.approval_valid(text)):
                _r, t = self.timed(fn)
                self.assertLess(t, 2.0)

    def test_unterminated_comment_kept_terminated_removed(self):
        self.assertEqual(R._strip_comments('a<!-- x -->b<!-- y'), 'ab<!-- y')


class TestTemplatesRev1(unittest.TestCase):
    def test_raw_templates_still_accepted_by_check_content(self):
        for tree in TestTemplates.TREES:
            self.assertEqual(R.check_content('spec', (tree / 'spec.md').read_text(encoding='utf-8')), [])


# ============================================================ Rev 2 amendments (D6 / D10 / D14 / D1 / D2)

class TestD6Alignment(unittest.TestCase):
    def setUp(self):
        self.root = mkroot()
        self.d = self.root / 'specs' / '001-x'
        (self.root / 'a.py').write_text('line\n' * 30, encoding='utf-8')
        (self.root / 'notes.txt').write_text('First line\nThe quick brown fox jumps\nlast', encoding='utf-8')
        (self.root / 'src').mkdir()
        (self.root / 'src' / 'cart.py').write_text('x' + chr(10) * 29, encoding='utf-8')
        self._old = R._evidence

    def tearDown(self):
        R._evidence = self._old

    def full(self, cl=CHECKLIST):
        return cl.replace('[Proposed — unconfirmed]', 'user — "pagar mas rapido por favor"')

    def run_dir(self, cl, extra=''):
        put(self.d / 'spec.md', spec(checklist=cl, extra=extra), 1000.0)
        R._evidence = lambda: FakeEv([ev('find_spec', 1500), ev('subagent', 1600)],
                                     ['es el modulo de checkout', 'pagar mas rapido por favor'])
        return R.check_spec_dir(self.d)

    def test_required_questions_equal_the_shipped_template(self):
        for tree in TestTemplates.TREES:
            raw = (tree / 'spec.md').read_text(encoding='utf-8')
            _h, rows = R._checklist_rows(R._clean(raw))
            self.assertEqual([R._qnorm(r[0]) for r in rows], [R._qnorm(q) for q in R.REQUIRED_QUESTIONS])

    def test_baseline_passes(self):
        ok(self, self.run_dir(self.full()))

    def test_missing_required_question_blocks_planning(self):
        cl = '\n'.join(l for l in self.full().split('\n') if 'Who is requesting' not in l)
        bad(self, self.run_dir(cl), 'R5', 'lacks 1 required question')

    def test_extra_rows_allowed_and_question_text_normalised(self):
        cl = self.full().replace('Which module/area of the system?', 'WHICH   module / area of the system')
        ok(self, self.run_dir(cl + '| Extra thing | yes | repo — a.py:5 | ask |\n'))

    def test_dash_na_answers_rejected(self):
        for junk in ('-', 'n/a', 'N/A', '—', 'TBD', ''):
            bad(self, self.run_dir(self.full().replace('| Ops |', f'| {junk} |')), 'R5', 'unanswered')

    def test_repo_line_must_exist_in_file(self):
        for good in ('a.py:30', 'a.py:1-30', 'notes.txt:3'):
            ok(self, self.run_dir(self.full().replace('a.py:1 ', f'{good} ')))
        for badref, why in (('a.py:31', 'out of range'), ('a.py:0', 'out of range'), ('a.py', 'no :LINE'),
                            ('.', 'directory'), ('src', 'directory'), ('./', 'directory'),
                            ('README.md', 'not an existing file')):
            bad(self, self.run_dir(self.full().replace('a.py:1 ', f'{badref} ')), 'R3', why)

    def test_repo_quote_form(self):
        ok(self, self.run_dir(self.full().replace('repo — a.py:1 ', 'repo — notes.txt "the QUICK brown fox" ')))
        bad(self, self.run_dir(self.full().replace('repo — a.py:1 ', 'repo — notes.txt "purple elephant dances" ')),
            'R3', 'not found')
        bad(self, self.run_dir(self.full().replace('repo — a.py:1 ', 'repo — notes.txt "quick brown" ')),
            'R3', '3+ words')
        bad(self, self.run_dir(self.full().replace('repo — a.py:1 ', 'repo — src "quick brown fox" ')),
            'R3', 'directory')

    def test_proposed_in_any_column(self):
        for rep in (('| ask |', '| Proposed value |'), ('| Ops |', '| Ops (proposed) |')):
            bad(self, self.run_dir(self.full().replace(rep[0], rep[1], 1)), 'R5', 'Proposed')

    def test_proposed_in_repeated_heading_and_second_table(self):
        row = '| Extra | x | [Proposed — unconfirmed] | ask |\n'
        again = ('\n## Minimum Requirements Checklist (again)\n\n| Question | Answer | Source | If unanswered |\n|---|---|---|---|\n' + row)
        bad(self, self.run_dir(self.full(), extra=again), 'R5', 'Proposed')
        second = '\n| Question | Answer | Source | If unanswered |\n|---|---|---|---|\n' + row
        bad(self, self.run_dir(self.full() + second), 'R5', 'Proposed')
        hidden = again.replace('[Proposed — unconfirmed]', '').replace('| x |', '|  |')
        bad(self, self.run_dir(self.full(), extra=hidden), 'R5', 'unanswered')

    def test_header_only_table_is_a_violation(self):
        hdr = '## Minimum Requirements Checklist\n\n| Question | Answer | Source | If unanswered |\n|---|---|---|---|\n'
        bad(self, R.check_content('spec', spec(checklist=hdr)), 'R3', 'no rows')
        bad(self, self.run_dir(hdr), 'R5', 'no question rows')

    def test_bad_header_in_second_table_is_caught(self):
        second = '\n| Question | Reason |\n|---|---|\n| a | b |\n'
        bad(self, R.check_content('spec', spec(checklist=CHECKLIST + '\n## Minimum Requirements Checklist\n' + second)),
            'R3', 'header')


class TestD10D14Tasks(unittest.TestCase):
    def with_cells(self, status='', tracker='', pr=''):
        return tasks().replace(
            '| Task | Codes |\n|---|---|\n| T-01 | COMP-001 |',
            f'| Task | Codes | Tracker ref | Status | PR/Spec ref |\n|---|---|---|---|---|\n'
            f'| T-01 | COMP-001 | {tracker} | {status} | {pr} |')

    def test_short_neutral_cells_ok_and_hash_neutral(self):
        t = self.with_cells('In progress', 'https://github.com/o/r/issues/12', 'o/r#9')
        ok(self, R.check_content('tasks', t))
        self.assertEqual(R.approval_hash(t), R.approval_hash(self.with_cells()))

    def test_long_cells_rejected(self):
        for kw in ({'status': 'x' * 61}, {'tracker': 'one two three four five six seven eight nine'},
                   {'pr': 'ship the whole redesign of the checkout page including payments'}):
            bad(self, R.check_content('tasks', self.with_cells(**kw)), 'R1', 'hash-neutral')
        ok(self, R.check_content('tasks', self.with_cells(status='x' * 60)))
        ok(self, R.check_content('tasks', self.with_cells(tracker='a b c d e f g h')))

    def test_status_lines_limited(self):
        t = tasks().replace('### T-01\n', '### T-01\nStatus: ' + 'word ' * 9 + '\n')
        bad(self, R.check_content('tasks', t), 'R1', 'hash-neutral')
        ok(self, R.check_content('tasks', tasks().replace('### T-01\n', '### T-01\nStatus: in progress\n')))
        self.assertEqual(R.approval_hash(t), R.approval_hash(tasks()))   # the hash still ignores them

    def test_pathological_numbers_never_raise(self):
        big = '9' * 5000
        for t in (tasks(a1=big), tasks(w1=big), tasks(total=big),
                  tasks().replace('Human ref hours: 8', f'Human ref hours: {big}'),
                  tasks().replace('| 1 | T-01 | 30 | 8 |', f'| 1 | T-01 | 30 | {big}.{big} |'),
                  tasks(a1=big, w1=big, total=big)):
            vs = R.check_content('tasks', t)
            self.assertTrue(vs and all(v['rule'] == 'R1' for v in vs), vs[:1])
        self.assertEqual(len(R.approval_hash(tasks(a1=big))), 12)

    def test_pathological_blocks_spec_numbers(self):
        root = mkroot()
        seed_specs(root)
        d = root / 'specs' / '001-x'
        for ref in ('9' * 5000, '²', '٣', '1' * 10):
            put(d / 'spec.md', spec(WAIVE0, extra='SCREEN-04\n' + DEBT.format(status='open', src='').replace('007-x', ref)))
            self.assertIsInstance(R.check_debt(root, '001-x', {}), list)
            self.assertIsInstance(R.open_debt_blocking(root), dict)
        self.assertEqual(R._match_spec_ref('9' * 5000, ['001-x']), [])


class TestD1D2Evidence(unittest.TestCase):
    def test_r7_ignores_code_edit_spec_attribution(self):
        root = mkroot()
        d = root / 'specs' / '001-x'
        put(d / 'spec.md', spec(), 1000.0)
        put(d / 'tasks.md', tasks().replace('COMP-001', 'none'), 1200.0)
        put(d / 'qa-audit.md', 'qa', 3000.0)
        old = R._evidence
        try:
            R._evidence = lambda: FakeEv([ev('find_spec', 1500), ev('subagent', 1600, head='performance review'),
                                          ev('code_edit', 2000, path='x.py')], ['x'])
            self.assertEqual(len([v for v in R.check_spec_dir(d) if v['rule'] == 'R7']), 1)
            R._evidence = lambda: FakeEv([ev('find_spec', 1500), ev('subagent', 1600, head='performance review'),
                                          ev('code_edit', 2000, spec='009-z')], ['x'])
            self.assertEqual(len([v for v in R.check_spec_dir(d) if v['rule'] == 'R7']), 1)
            R._evidence = lambda: FakeEv([ev('subagent', 2100, head='performance review'), ev('code_edit', 2000)], ['x'])
            self.assertEqual([v for v in R.check_spec_dir(d) if v['rule'] == 'R7'], [])
        finally:
            R._evidence = old

    def test_answer_quotes_use_pairs_only(self):
        f = FakeEv(answers=[{'text': '"Waive it?"="Yes waive it now"', 'pairs': []},
                            {'text': 'x', 'pairs': [['Waive it?', 'Yes waive it']]}])
        self.assertTrue(R.quote_verified(f, 'r', 'yes waive it'))
        self.assertFalse(R.quote_verified(f, 'r', 'waive it now'))


if __name__ == '__main__':
    unittest.main()
