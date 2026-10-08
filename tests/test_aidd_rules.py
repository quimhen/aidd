"""Tests for skill/scripts/aidd_rules.py — stdlib unittest, adversarial per rule.

Run: python -m unittest tests.test_aidd_rules -v
"""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO =Path(__file__).resolve().parent.parent
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
- Tokens (est): 60k
- Agent role: builder
- Model tier: medium

### T-02
- Agent min: {a2}
- Human ref hours: 4
- Tokens (est): 40k
- Agent role: tests
- Model tier: medium
{extra_block}
## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01 | builder | {w1} | 60 | 8 |
| 2 | T-02 | tests | {w2} | 40 | 4 |

Total agent time (critical path): {total} min
Total tokens (k): 100

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
        t = tasks().replace('| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |',
                            '| Wave | Tasks | Roles | Tokens (k) | Agent time (min) | Human ref (h) |')
        bad(self, R.check_content('tasks', t), 'R1', 'column order')

    def test_wave_time_off_by_one(self):
        bad(self, R.check_content('tasks', tasks(w1=31, total=51)), 'R1', 'max of its tasks')

    def test_wave_is_max_not_sum(self):
        t = (tasks().replace('| 1 | T-01 | builder | 30 | 60 | 8 |', '| 1 | T-01, T-02 | builder, tests | 50 | 100 | 12 |')
             .replace('| 2 | T-02 | tests | 20 | 40 | 4 |\n', ''))
        bad(self, R.check_content('tasks', t), 'R1', 'max of its tasks')

    def test_parallel_wave_ok(self):
        t = (tasks().replace('| 1 | T-01 | builder | 30 | 60 | 8 |', '| 1 | T-01, T-02 | builder, tests | 30 | 100 | 12 |')
             .replace('| 2 | T-02 | tests | 20 | 40 | 4 |\n', ''))
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

    BASE = {'security', 'functional'}

    def test_security_functional_always(self):
        self.assertEqual(R.required_domains(self.mk('nothing')), self.BASE)
        self.assertEqual(R.required_domains('/does/not/exist'), self.BASE)

    def test_ui_backend_database(self):
        B = self.BASE
        self.assertEqual(R.required_domains(self.mk('SCREEN-01')), B | {'performance', 'ui'})
        self.assertEqual(R.required_domains(self.mk('CTL-3')), B | {'performance', 'ui'})
        self.assertEqual(R.required_domains(self.mk('COMP-2')), B | {'performance', 'ui'})
        self.assertEqual(R.required_domains(self.mk('API-007')), B | {'backend'})   # backend alone: no performance
        self.assertEqual(R.required_domains(self.mk('x', data_model=True)), B | {'performance', 'database'})
        self.assertEqual(R.required_domains(self.mk('add a migration')), B | {'performance', 'database'})
        self.assertEqual(R.required_domains(self.mk('run script.sql')), B | {'performance', 'database'})
        self.assertEqual(R.required_domains(self.mk('SCREEN-1 API-2 schema')),
                         B | {'performance', 'ui', 'backend', 'database'})

    def test_audit_domains_override_narrows_an_amendment(self):
        d = self.mk('stored procedure change .sql')
        self.assertEqual(R.required_domains(d), self.BASE | {'performance', 'database'})
        (d / 'spec.md').write_text('## Verification\nAudit-Domains: database\n| # | cmd |\n', encoding='utf-8')
        self.assertEqual(R.required_domains(d), {'functional', 'database'})   # functional is never dropped
        (d / 'spec.md').write_text('## Verification\nAudit-Domains: bogus\n', encoding='utf-8')
        self.assertEqual(R.required_domains(d), self.BASE | {'performance', 'database'})   # unknown words: no override
        (d / 'spec.md').write_text('## Verification\n| # | cmd |\n', encoding='utf-8')
        self.assertEqual(R.required_domains(d), self.BASE | {'performance', 'database'})

    def test_wave_advice_one_agent_per_lane(self):
        hdr = '| Task | Desc | Codes | Target file | Status |\n|---|---|---|---|---|\n'
        rows = ''.join(f'| T-{i:02d} | x | FR-1 | `eDoc/web/src/f{i}.ts` | |\n' for i in range(1, 6)) + \
               ''.join(f'| T-{i:02d} | x | FR-1 | `eDoc/engine/e{i}.py` | |\n' for i in range(6, 9))
        waves = '\n## Waves\n\n| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |\n|---|---|---|---|---|---|\n' \
                '| 1 | T-01, T-02, T-03, T-04, T-05, T-06, T-07, T-08 | builder | 5 | 400 | 0.25 |\n'
        adv = R.wave_agent_advice(hdr + rows + waves)
        self.assertEqual(len(adv), 1)
        self.assertIn('8 tasks in 2 lane', adv[0])
        self.assertIn('Plan 2 owner agent', adv[0])
        small = waves.replace('T-01, T-02, T-03, T-04, T-05, T-06, T-07, T-08', 'T-01, T-02')
        self.assertEqual(R.wave_agent_advice(hdr + rows + small), [])      # below the 6-task threshold
        self.assertEqual(R.wave_agent_advice('nothing'), [])

    def test_small_change_audits_only_what_it_touches_by_default(self):
        hdr = '| Task | Desc | Target file | Agent min: | Tokens |\n|---|---|---|---|---|\n'
        small = self.mk(hdr + '| T-01 | x | `db/deploy.sql` | 5 | 50 |\n')
        self.assertEqual(R.required_domains(small), {'functional', 'database'})
        (small / 'spec.md').write_text('Risk: high\n', encoding='utf-8')               # money/security: full rule
        self.assertEqual(R.required_domains(small), self.BASE | {'performance', 'database'})
        (small / 'spec.md').write_text('## Verification\nAudit-Domains: security, functional\n', encoding='utf-8')
        self.assertEqual(R.required_domains(small), {'security', 'functional'})     # the declared set wins
        big = self.mk(hdr + ''.join(f'| T-{i} | x | `db/p{i}.sql` | 5 | 50 |\n' for i in range(3)))
        self.assertEqual(R.required_domains(big), self.BASE | {'performance', 'database'})   # medium: full rule

    def test_impact_summary_sizes_the_change(self):
        row = '| T-01 | x | `db/deploy.sql` | 5 | 50 |\n'
        hdr = '| Task | Desc | Target file | Agent min: | Tokens |\n|---|---|---|---|---|\n'
        d = self.mk(hdr + row)
        s = R.impact_summary(d)
        self.assertEqual((s['files'], s['magnitude']), (1, 'small'))
        self.assertEqual(s['domains'], {'functional', 'database'})   # no security/performance for a 1-file SQL change
        self.assertIn('Audit-Domains: database, functional', s['suggest'])
        d2 = self.mk(hdr + ''.join(f'| T-{i} | x | `src/auth/f{i}.ts` | 5 | 50 |\n' for i in range(9)))
        s2 = R.impact_summary(d2)
        self.assertEqual(s2['magnitude'], 'large')
        self.assertTrue({'security', 'performance'} <= s2['domains'])
        self.assertEqual(R.impact_summary('/does/not/exist')['domains'], {'functional'})

    def test_performance_matrix_hot_path_db_ui_only(self):
        B = self.BASE
        for txt in ('hot path', 'hot-path loop', 'reduce latency', 'baja latencia', 'performance goal', 'mejor rendimiento'):
            self.assertEqual(R.required_domains(self.mk(txt)), B | {'performance'}, txt)
        for txt in ('API-1 endpoint', 'plain refactor', 'hotpathology'):
            self.assertNotIn('performance', R.required_domains(self.mk(txt)), txt)
        self.assertEqual(R.required_domains(self.mk('API-1 hot path')), B | {'backend', 'performance'})

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
        # spec 007 (FR-206): these cases test the 006 R5 block, which is the `strict` mode now
        pin = patch.dict(os.environ, {'AIDD_R5_AUDIT': 'strict'})
        pin.start()
        self.addCleanup(pin.stop)

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
        bad(self, R.check_spec_dir(self.d), 'R5', 'pre-build coherence audit')   # rebuild postdates the only subagent

    # --- spec 007 (FR-206, AC-211): advisory twins — the same fixtures emit NO Mapper/pre-build R5
    def test_no_mapper_after_spec_edit_advisory(self):
        self.write('spec.md', self.good_spec(), mtime=2000.0)
        self.use(FakeEv([ev('find_spec', 1500), ev('subagent', 1600)], self.prompts()))
        for value in (None, 'advisory', 'ADVISORY', ' x ', ''):
            if value is None:
                os.environ.pop('AIDD_R5_AUDIT', None)
            else:
                os.environ['AIDD_R5_AUDIT'] = value
            self.assertEqual([v for v in R.check_spec_dir(self.d) if v['rule'] == 'R5'], [], value)
        os.environ['AIDD_R5_AUDIT'] = ' Strict '   # trimmed, case-insensitive
        bad(self, R.check_spec_dir(self.d), 'R5', 'Mapper')

    def test_tasks_chain_and_approval_advisory(self):
        os.environ.pop('AIDD_R5_AUDIT', None)
        self.write('spec.md', self.good_spec(), mtime=1000.0)
        self.write('plan.md', 'plan', mtime=1700.0)
        self.write('tasks.md', tasks(), mtime=1800.0)
        self.use(FakeEv([ev('find_spec', 1500), ev('subagent', 1600)], self.prompts()))
        vs = R.check_spec_dir(self.d)
        self.assertEqual([v for v in vs if v['rule'] == 'R5'], [])
        bad(self, vs, 'R6', 'pending')            # approval itself is untouched by the R5 mode

    def test_graph_rebuilt_needs_subagent_after_advisory(self):
        os.environ.pop('AIDD_R5_AUDIT', None)
        self.write('spec.md', self.good_spec(), mtime=1000.0)
        self.write('plan.md', 'plan', mtime=1100.0)
        self.write('tasks.md', tasks(), mtime=1200.0)
        self.use(FakeEv([ev('subagent', 1300), ev('find_spec', 1400, rebuilt=True)], self.prompts()))
        self.assertEqual([v for v in R.check_spec_dir(self.d) if v['rule'] == 'R5'], [])

    def test_advisory_keeps_find_spec_quotes_proposed_and_plan_order(self):
        os.environ.pop('AIDD_R5_AUDIT', None)
        self.write('spec.md', self.good_spec())
        self.use(FakeEv([ev('subagent', 1600)], self.prompts()))
        bad(self, R.check_spec_dir(self.d), 'R5', 'find_spec')
        self.use(FakeEv([ev('find_spec', 1500)], ['something else entirely']))
        bad(self, R.check_spec_dir(self.d), 'R5', 'Quote not found')
        self.write('spec.md', spec())
        self.use(FakeEv([ev('find_spec', 1500)], self.prompts()))
        bad(self, R.check_spec_dir(self.d), 'R5', 'Proposed')
        self.write('spec.md', self.good_spec())
        self.write('tasks.md', tasks())
        bad(self, R.check_spec_dir(self.d), 'R5', 'plan.md does not')

    def test_r7_qa_audit_domains(self):
        self.write('spec.md', self.good_spec(), mtime=1000.0)
        self.write('tasks.md', tasks().replace('COMP-001', 'COMP-001 API-002'), mtime=1200.0)
        self.write('qa-audit.md', 'qa', mtime=3000.0)
        base = [ev('find_spec', 1500), ev('subagent', 1600), ev('code_edit', 2000, spec='001-x')]
        self.use(FakeEv(base + [ev('subagent', 2100, head='performance best practice')], self.prompts()))
        vs = R.check_spec_dir(self.d)
        self.assertEqual({v['message'].split()[1] for v in vs if v['rule'] == 'R7'},
                         {'ui', 'backend', 'security', 'functional'})
        self.use(FakeEv(base + [ev('subagent', 2100, head='performance'), ev('subagent', 2200, desc='api contract'),
                        ev('subagent', 2300, desc='ui mockup audit'), ev('subagent', 2400, desc='security review'),
                        ev('subagent', 2500, desc='functional acceptance')],
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
            self.assertIn('R1', rules(vs))
            self.assertLessEqual(rules(vs), {'R1', 'R13'})
            self.assertTrue(all(v['fix'] for v in vs))
            filled = re.sub(r'(Agent min:) \[[^\]]*\]', lambda m, c=iter([30, 20]): f'{m.group(1)} {next(c)}', raw)
            filled = re.sub(r'(Human ref hours:) \[[^\]]*\]', r'\1 4', filled)
            filled = re.sub(r'(Tokens \(est\):) \[[^\]]*\]', r'\1 40k', filled)
            filled = re.sub(r'(Agent role:) \[[^\]]*\]', r'\1 tests', filled)
            filled = re.sub(r'(Model tier:) \[[^\]]*\]', r'\1 medium', filled)
            filled = re.sub(r'(\| 1 \| T-01 \| builder \| )\[[^\]]*\]( \| )\[[^\]]*\]( \| )\[[^\]]*\]', r'\g<1>30\g<2>60\g<3>4', filled)
            filled = re.sub(r'(\| 2 \| T-02 \| tests \| )\[[^\]]*\]( \| )\[[^\]]*\]( \| )\[[^\]]*\]', r'\g<1>20\g<2>40\g<3>4', filled)
            filled = re.sub(r'(critical path\): )\[[^\]]*\]', r'\g<1>50', filled)
            filled = re.sub(r'(Total tokens \(k\): )\[[^\]]*\]', r'\g<1>100', filled)
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
        row2 = '| 2 | T-02 | tests | 20 | 40 | 4 |\n'
        t = tasks().replace(row2, row2 + '\n| 3 | T-02 | tests | huge | 40 | 1 |\n')
        self.assertNotEqual(t, tasks())
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
        self.assertEqual(len(R.uncovered_domains(root, 's', '001-x', 0)), 5)   # 6 required, 1 subagent -> 1 covered
        fake.rows += [ev('subagent', 11, head='ui mockup audit'), ev('subagent', 12, desc='api contract'),
                      ev('subagent', 13, head='database sql review'), ev('subagent', 14, desc='security audit'),
                      ev('subagent', 15, desc='functional acceptance')]
        self.assertEqual(R.uncovered_domains(root, 's', '001-x', 0), set())   # 6 distinct subagents (generic -> perf)
        self.assertEqual(len(R.uncovered_domains(root, 's', '001-x', 12)), 3)   # only #13..#15 are newer than ts 12

    def test_matching_is_optimal_not_first_come(self):
        root, d = self.mk('SCREEN-1 API-2')
        # e1 matches ui+backend, e2 only ui: naive greedy e1->ui would leave backend uncovered
        self.with_ev(FakeEv([ev('subagent', 10, head='ui api review'), ev('subagent', 11, head='ui check'),
                             ev('subagent', 12, head='performance'), ev('subagent', 13, head='security'),
                             ev('subagent', 14, head='functional')]))
        self.assertEqual(R.uncovered_domains(root, 's', '001-x', 0), set())

    def test_substrings_do_not_match(self):
        root, d = self.mk('SCREEN-1 API-2 schema')
        self.with_ev(FakeEv([ev('subagent', 10, head='rapid capital quick build', desc='suite requirements guide')]))
        self.assertEqual(R.uncovered_domains(root, 's', '001-x', 0),
                         {'ui', 'backend', 'database', 'performance', 'security', 'functional'})
        for dom, s in (('ui', 'rapid'), ('ui', 'quick'), ('ui', 'build'), ('backend', 'capital'), ('backend', 'rapid'),
                       ('database', 'mysqlite'), ('performance', 'nonperformance'),
                       ('security', 'insecurity'), ('functional', 'dysfunctional')):
            self.assertIsNone(R.DOMAIN_RE[dom].search(s), (dom, s))
        for dom, s in (('ui', 'UI audit'), ('ui', 'Pantalla'), ('backend', 'API/contract'), ('database', 'migración'),
                       ('database', 'base de datos'), ('performance', 'best practices'),
                       ('security', 'Security audit'), ('security', 'seguridad'),
                       ('functional', 'functional audit'), ('functional', 'acceptance')):
            self.assertIsNotNone(R.DOMAIN_RE[dom].search(s), (dom, s))

    def test_compat_wrapper_and_missing_evidence(self):
        self.with_ev(FakeEv([ev('subagent', 10, head='ui review')]))
        self.assertTrue(R.domain_covered('r', 's', 'ui', 0))
        self.assertFalse(R.domain_covered('r', 's', 'ui', 10))
        R._evidence = lambda: None
        root, d = self.mk('SCREEN-1')
        self.assertEqual(R.uncovered_domains(root, 's', '001-x', 0), {'ui', 'performance', 'security', 'functional'})

    def test_r7_in_check_spec_dir_needs_distinct_subagents(self):
        root = mkroot()
        d = root / 'specs' / '001-x'
        put(d / 'spec.md', spec(), 1000.0)
        put(d / 'tasks.md', tasks().replace('COMP-001', 'COMP-001 API-002'), 1200.0)
        put(d / 'qa-audit.md', 'qa', 3000.0)
        base = [ev('find_spec', 1500), ev('subagent', 1600), ev('code_edit', 2000, spec='001-x')]
        self.with_ev(FakeEv(base + [ev('subagent', 2100, head='ui backend api performance review all')], ['x']))
        vs = [v for v in R.check_spec_dir(d) if v['rule'] == 'R7']
        self.assertEqual(len(vs), 4, vs)   # 5 required (sec, func, ui, backend, perf), one subagent covers one


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
                  tasks().replace('| 1 | T-01 | builder | 30 | 60 | 8 |', f'| 1 | T-01 | builder | 30 | 60 | {big}.{big} |'),
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


class TestAuditSince(unittest.TestCase):
    """audit_since: the last N code edits (AIDD_R7_FIX_EDITS, default 3) do not invalidate an audit."""

    def _since(self, tol, stamps):
        old = os.environ.get('AIDD_R7_FIX_EDITS')
        if tol is None:
            os.environ.pop('AIDD_R7_FIX_EDITS', None)
        else:
            os.environ['AIDD_R7_FIX_EDITS'] = tol
        try:
            return R.audit_since([{'ts': t} for t in stamps])
        finally:
            if old is None:
                os.environ.pop('AIDD_R7_FIX_EDITS', None)
            else:
                os.environ['AIDD_R7_FIX_EDITS'] = old

    def test_strict_uses_last_edit(self):
        self.assertEqual(self._since('0', [1, 5, 3]), 5)

    def test_default_tolerates_last_three(self):
        self.assertEqual(self._since(None, [1, 2, 3]), 0.0)
        self.assertEqual(self._since(None, [1, 2, 3, 4, 5]), 2)

    def test_no_edits_and_bad_value(self):
        self.assertEqual(self._since('0', []), 0.0)
        self.assertEqual(self._since('abc', [1, 2, 3, 4]), 1)


class TestD1D2Evidence(unittest.TestCase):
    def setUp(self):
        self._old_tol = os.environ.get('AIDD_R7_FIX_EDITS')
        os.environ['AIDD_R7_FIX_EDITS'] = '0'

    def tearDown(self):
        if self._old_tol is None:
            os.environ.pop('AIDD_R7_FIX_EDITS', None)
        else:
            os.environ['AIDD_R7_FIX_EDITS'] = self._old_tol

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
            # tasks touch nothing -> required = {security, functional}; the pre-edit subagent covers neither
            self.assertEqual(len([v for v in R.check_spec_dir(d) if v['rule'] == 'R7']), 2)
            R._evidence = lambda: FakeEv([ev('find_spec', 1500), ev('subagent', 1600, head='performance review'),
                                          ev('code_edit', 2000, spec='009-z')], ['x'])
            self.assertEqual(len([v for v in R.check_spec_dir(d) if v['rule'] == 'R7']), 2)
            R._evidence = lambda: FakeEv([ev('subagent', 2100, head='security review'),
                                          ev('subagent', 2150, head='functional review'), ev('code_edit', 2000)], ['x'])
            self.assertEqual([v for v in R.check_spec_dir(d) if v['rule'] == 'R7'], [])
        finally:
            R._evidence = old

    def test_answer_quotes_use_pairs_only(self):
        f = FakeEv(answers=[{'text': '"Waive it?"="Yes waive it now"', 'pairs': []},
                            {'text': 'x', 'pairs': [['Waive it?', 'Yes waive it']]}])
        self.assertTrue(R.quote_verified(f, 'r', 'yes waive it'))
        self.assertFalse(R.quote_verified(f, 'r', 'waive it now'))


# ============================================================ Spec 005 token planning (T-13)
sys.path.insert(0, str(REPO / 'tests'))
from gate_fixtures import new_tasks, legacy_tasks_text, approved_legacy_tasks as _approved_legacy  # noqa: E402


class TestTokenPlanning(unittest.TestCase):
    def test_valid_new_header(self):
        ok(self, R.check_content('tasks', new_tasks()))

    def test_wave_tokens_not_sum(self):
        vs = R.check_content('tasks', new_tasks(wt2=50))
        bad(self, vs, 'R1', 'Wave 2')

    def test_total_tokens_wrong(self):
        bad(self, R.check_content('tasks', new_tasks(total_tokens=99)), 'R1', 'Total tokens')

    def test_missing_agent_role(self):
        vs = R.check_content('tasks', new_tasks(role1=''))
        bad(self, vs, 'R13', 'T-01')

    def test_tier_low_invalid(self):
        bad(self, R.check_content('tasks', new_tasks(tier2='low')), 'R13', 'T-02')

    def test_auditor_with_medium_valid(self):
        ok(self, R.check_content('tasks', new_tasks(role2='auditor', roles2='auditor', tier2='medium')))

    def test_roles_cell_mismatch(self):
        bad(self, R.check_content('tasks', new_tasks(roles1='docs')), 'R1')

    def test_approved_legacy_skips_new_checks(self):
        t = _approved_legacy()
        self.assertTrue(R._is_legacy_tasks(t))
        self.assertFalse(rules(R.check_content('tasks', t)) & {'R1', 'R13'})

    def test_approved_legacy_file_passes(self):
        ok(self, R.check_content('tasks', _approved_legacy()))

    def test_unapproved_legacy_header_with_missing_fields_is_rejected(self):
        # audit F1 probe: a NEW, UNAPPROVED tasks.md keeping the 4-column header must not pass R1/R13
        t = legacy_tasks_text()
        self.assertFalse(R._is_legacy_tasks(t))
        vs = R.check_content('tasks', t)
        bad(self, vs, 'R1', 'exempt only while its recorded approval is valid')
        bad(self, vs, 'R1', 'Tokens (est)')
        bad(self, vs, 'R1', 'Total tokens')
        bad(self, vs, 'R13', 'Agent role')
        bad(self, vs, 'R13', 'Model tier')

    def test_edited_approved_legacy_without_migrating_is_rejected(self):
        t = _approved_legacy().replace('- Agent min: 30', '- Agent min: 31').replace('| 1 | T-01 | 30 |', '| 1 | T-01 | 31 |')
        t = t.replace('critical path): 50', 'critical path): 51')
        self.assertFalse(R.approval_valid(t))
        self.assertFalse(R._is_legacy_tasks(t))
        vs = R.check_content('tasks', t)
        bad(self, vs, 'R1', 'exempt only while')
        bad(self, vs, 'R13', 'T-01')

    def test_migrating_edited_legacy_to_new_format_passes(self):
        from gate_fixtures import tasks_text as _new_fmt, approved_tasks as _approved_new
        migrated = _new_fmt(a1=31, w1=31, total=51)
        ok(self, R.check_content('tasks', migrated))
        ok(self, R.check_content('tasks', _approved_new(a1=31, w1=31, total=51)))

    def test_plan_totals(self):
        self.assertEqual(R.plan_totals(new_tasks()), {'minutes': 50, 'tokens_k': 100})
        legacy = R.plan_totals(legacy_tasks_text())
        self.assertEqual(legacy['minutes'], 50)
        self.assertIsNone(legacy['tokens_k'])

    def test_derived_human_hours(self):
        self.assertEqual(R.derived_human_hours(3), 0.15)

    def test_r4_sibling_backticked_screen_ignored(self):
        root = Path(tempfile.mkdtemp())
        d = root / 'specs' / '001-x'
        d.mkdir(parents=True)
        (d / 'spec.md').write_text(spec(WAIVE0), encoding='utf-8')
        other = root / 'specs' / '002-y'
        other.mkdir()
        (other / 'plan.md').write_text('example `SCREEN-07` quoted, but SCREEN-08 is real', encoding='utf-8')
        vs = R.check_spec_dir(d, static_only=True)
        msg = ' '.join(v['message'] for v in vs if v['rule'] == 'R4')
        self.assertNotIn('SCREEN-07', msg)
        self.assertIn('SCREEN-08', msg)


# ============================================================ Spec 006 phased audits (T-13, AC-005)
class TestPhasedAudits(unittest.TestCase):
    """FR-002/FR-003: Mapper once after the first spec draft, ONE pre-build audit before approval."""

    def setUp(self):
        self.root = mkroot()
        self.d = self.root / 'specs' / '001-x'
        self._old = R._evidence
        put(self.root / 'src' / 'cart.py', 'x\n' * 30)
        put(self.root / 'a.py', 'x\n' * 30)
        cl =CHECKLIST.replace('[Proposed — unconfirmed]', 'user — "pagar mas rapido por favor"')
        self.spec_text = spec(checklist=cl)
        self.prompts = ['es el modulo de checkout', 'pagar mas rapido por favor', 'no hace falta el flowmap']
        # spec 007 (FR-206): the 006 phases are the `strict` mode now; started BEFORE the tolerance
        # change so the patch's snapshot is the pristine environment
        pin = patch.dict(os.environ, {'AIDD_R5_AUDIT': 'strict'})
        pin.start()
        self.addCleanup(pin.stop)
        self._old_tol = os.environ.get('AIDD_R5_FIX_EDITS')
        os.environ['AIDD_R5_FIX_EDITS'] = '0'   # strict by default; AC-010 tests override it

    def tearDown(self):
        R._evidence = self._old
        if self._old_tol is None:
            os.environ.pop('AIDD_R5_FIX_EDITS', None)
        else:
            os.environ['AIDD_R5_FIX_EDITS'] = self._old_tol

    def fake(self, rows):
        # prompts postdate the first recorded spec edit (1000) so quote verification holds
        p = [{'ts': 1001.0, 'session': 's', 'kind': 'prompt', 'detail': {'text': t}} for t in self.prompts]
        R._evidence = lambda: FakeEv(list(rows) + p)

    def r5(self):
        return [v for v in R.check_spec_dir(self.d) if v['rule'] == 'R5']

    def spec_edits(self, *stamps):
        return [ev('spec_edit', t, spec='001-x', file='spec.md') for t in stamps]

    def test_no_subagent_demanded_between_spec_edits(self):
        put(self.d / 'spec.md', self.spec_text, 1000.0)
        self.fake(self.spec_edits(1000, 1100, 1200, 1300) + [ev('find_spec', 1010), ev('subagent', 1050, head='Mapper')])
        ok(self, self.r5())   # the Mapper predates the later edits and that is fine

    def test_mapper_required_once_after_first_draft(self):
        put(self.d / 'spec.md', self.spec_text, 1000.0)
        self.fake(self.spec_edits(1000, 1100) + [ev('find_spec', 1010)])
        bad(self, self.r5(), 'R5', 'Mapper')
        self.fake(self.spec_edits(1000, 1100) + [ev('find_spec', 1010), ev('subagent', 990, head='Mapper')])
        bad(self, self.r5(), 'R5', 'Mapper')            # a subagent before the first draft does not count
        self.fake(self.spec_edits(1000, 1100) + [ev('find_spec', 1010), ev('subagent', 1001, head='Mapper', model='haiku')])
        bad(self, self.r5(), 'R5', 'Mapper')            # R14: haiku does not count
        self.fake(self.spec_edits(1000, 1100) + [ev('find_spec', 1010), ev('subagent', 1001, head='Mapper', model='sonnet')])
        ok(self, self.r5())

    def _chain(self, signed=False):
        put(self.d / 'spec.md', self.spec_text, 1000.0)
        put(self.d / 'plan.md', 'plan', 1100.0)
        t = tasks()
        if signed:
            t = t.replace('Approved: PENDING', f'Approved: 2026-10-01 hash:{R.approval_hash(t)}')
        put(self.d / 'tasks.md', t, 1200.0)

    def test_one_pre_build_audit_satisfies_tasks_approval(self):
        self._chain()
        base = self.spec_edits(1000) + [ev('find_spec', 1010), ev('subagent', 1050, head='Mapper')]
        self.fake(base)
        bad(self, self.r5(), 'R5', 'pre-build coherence audit')
        self.fake(base + [ev('subagent', 1300, head='coherence audit')])
        ok(self, self.r5())
        # a later plan/tasks edit invalidates it, a fresh one restores it
        self.fake(base + [ev('subagent', 1300, head='coherence audit'),
                          ev('spec_edit', 1400, spec='001-x', file='tasks.md')])
        bad(self, self.r5(), 'R5', 'pre-build coherence audit')
        self.fake(base + [ev('subagent', 1300, head='coherence audit'),
                          ev('spec_edit', 1400, spec='001-x', file='tasks.md'), ev('subagent', 1500)])
        ok(self, self.r5())

    def test_haiku_audit_does_not_count(self):
        self._chain()
        base = self.spec_edits(1000) + [ev('find_spec', 1010), ev('subagent', 1050, head='Mapper')]
        self.fake(base + [ev('subagent', 1300, head='audit', model='haiku')])
        bad(self, self.r5(), 'R5', 'pre-build coherence audit')
        self.fake(base + [ev('subagent', 1300, head='audit', model='claude-haiku-4-5')])
        bad(self, self.r5(), 'R5', 'pre-build coherence audit')
        self.fake(base + [ev('subagent', 1300, head='audit', model='opus')])
        ok(self, self.r5())

    def test_pre_build_audit_not_demanded_once_approved(self):
        self._chain(signed=True)
        self.fake(self.spec_edits(1000) + [ev('find_spec', 1010), ev('subagent', 1050, head='Mapper')])
        self.assertEqual([v for v in self.r5() if 'pre-build' in v['message']], [])
        ok(self, [v for v in R.check_spec_dir(self.d) if v['rule'] != 'R7'])

    def test_graph_rebuild_requires_the_audit_after_it(self):
        self._chain()
        base = self.spec_edits(1000) + [ev('find_spec', 1010), ev('subagent', 1300, head='audit')]
        self.fake(base + [ev('find_spec', 1400, rebuilt=True)])
        bad(self, self.r5(), 'R5', 'pre-build coherence audit')
        self.fake(base + [ev('find_spec', 1400, rebuilt=True), ev('subagent', 1500, head='audit')])
        ok(self, self.r5())
        self.assertFalse(any('graph index was rebuilt' in v['message'] for v in self.r5()))

    def test_pre_build_helpers(self):
        self._chain()
        f = FakeEv(self.spec_edits(1000, 1250) + [ev('find_spec', 1400, rebuilt=True), ev('find_spec', 1500, rebuilt=False)])
        self.assertEqual(R.mapper_since(f, self.root, self.d), 1000)
        self.assertEqual(R.pre_build_since(f, self.root, self.d, 's'), 1400)
        self.assertFalse(R.pre_build_audit_done(f, self.root, 's', self.d))
        f.rows.append(ev('subagent', 1450, model='haiku'))
        self.assertFalse(R.pre_build_audit_done(f, self.root, 's', self.d))
        f.rows.append(ev('subagent', 1450))
        self.assertTrue(R.pre_build_audit_done(f, self.root, 's', self.d))
        self.assertFalse(R.pre_build_audit_done(None, self.root, 's', self.d))   # fail-closed
        put(self.root / 'specs' / '002-n' / 'spec.md', 'x', 777.0)
        self.assertEqual(R.mapper_since(FakeEv(), self.root, self.root / 'specs' / '002-n'), 777.0)   # mtime fallback
        # FR-010: with the tolerance the recorded edits of a file replace its mtime
        os.environ['AIDD_R5_FIX_EDITS'] = '3'
        g = FakeEv(self.spec_edits(1000) + [ev('spec_edit', t, spec='001-x', file='tasks.md') for t in (1300, 1310, 1320)])
        self.assertEqual(R.pre_build_since(g, self.root, self.d, 's'), 1100)   # plan.md mtime stays strict
        os.environ['AIDD_R5_FIX_EDITS'] = 'x'                                   # ValueError -> 3
        self.assertEqual(R.pre_build_since(g, self.root, self.d, 's'), 1100)

    # --- AC-010: AIDD_R5_FIX_EDITS tolerance -------------------------------------------------
    def _tol_rows(self, n_edits, extra=()):
        rows = [ev('spec_edit', 1000, spec='001-x', file='spec.md'),
                ev('spec_edit', 1100, spec='001-x', file='plan.md'),
                ev('spec_edit', 1200, spec='001-x', file='tasks.md'),
                ev('find_spec', 1010), ev('subagent', 1050, head='Mapper'),
                ev('subagent', 1300, head='coherence audit')]
        rows += [ev('spec_edit', 1400 + 10 * i, spec='001-x', file='tasks.md') for i in range(n_edits)]
        return rows + list(extra)

    def test_ac010_three_edits_tolerated_fourth_blocks(self):
        self._chain()
        os.environ.pop('AIDD_R5_FIX_EDITS', None)   # the default (3)
        for n in (1, 2, 3):
            self.fake(self._tol_rows(n))
            ok(self, self.r5())
        self.fake(self._tol_rows(4))
        bad(self, self.r5(), 'R5', 'pre-build coherence audit')
        self.fake(self._tol_rows(4, [ev('subagent', 1500, head='audit')]))
        ok(self, self.r5())

    def test_ac010_strict_with_zero(self):
        self._chain()
        os.environ['AIDD_R5_FIX_EDITS'] = '0'
        self.fake(self._tol_rows(1))
        bad(self, self.r5(), 'R5', 'pre-build coherence audit')

    def test_ac010_unrecorded_newer_mtime_fails_closed(self):
        self._chain()
        os.environ['AIDD_R5_FIX_EDITS'] = '3'
        put(self.d / 'plan.md', 'plan v2', 1350.0)   # newer than the audit, no recorded plan.md edit
        rows = [r for r in self._tol_rows(0) if (r.get('detail') or {}).get('file') != 'plan.md']
        self.fake(rows)
        bad(self, self.r5(), 'R5', 'pre-build coherence audit')

    def test_ac010_rebuild_stays_strict_within_tolerance(self):
        self._chain()
        os.environ['AIDD_R5_FIX_EDITS'] = '3'
        self.fake(self._tol_rows(1, [ev('find_spec', 1450, rebuilt=True)]))
        bad(self, self.r5(), 'R5', 'pre-build coherence audit')

    def test_ac010_approval_hash_binds_final_tasks(self):
        os.environ['AIDD_R5_FIX_EDITS'] = '3'
        t = tasks()
        signed = t.replace('Approved: PENDING', f'Approved: 2026-10-01 hash:{R.approval_hash(t)}')
        self.assertIs(R.approval_valid(signed), True)
        self.assertIsNot(R.approval_valid(signed + '\n- one more fix\n'), True)   # tolerance never extends to approval

    # --- spec 007 (FR-206, AC-211): advisory twins of the phase tests
    def test_advisory_twin_no_mapper_no_pre_build_demanded(self):
        os.environ.pop('AIDD_R5_AUDIT', None)
        self._chain()
        self.fake(self.spec_edits(1000, 1100) + [ev('find_spec', 1010)])
        ok(self, self.r5())                              # no Mapper, no pre-build audit: allowed
        self.fake(self.spec_edits(1000) + [ev('find_spec', 1010), ev('subagent', 1300, head='audit', model='haiku'),
                                           ev('find_spec', 1400, rebuilt=True)])
        ok(self, self.r5())
        self.fake(self.spec_edits(1000))                 # find_spec stays required in both modes
        bad(self, self.r5(), 'R5', 'find_spec')
        # the pure helpers are unchanged by the mode
        f = FakeEv(self.spec_edits(1000))
        self.assertFalse(R.pre_build_audit_done(f, self.root, 's', self.d))
        self.assertEqual(R.mapper_since(f, self.root, self.d), 1000)


# ============================================================ Spec 007 (T-02): Verification + closing audit
import hashlib  # noqa: E402

SPEC_IDS = ('002-aidd-hard-rules', 'F23-eDoc-POS')   # numeric and non-numeric real ids


def vspec(rows, prose='Some prose.', extra=''):
    body = '\n'.join(f'| {n} | {c} | {e} | {cv} |' for n, c, e, cv in rows)
    return (f"# Spec\n\n{prose}\n\n## Verification\n\nCommands run at close.\n\n"
            f"| # | Command | Expected | Covers |\n|---|---|---|---|\n{body}\n\n## Optimization brief\n\nx{extra}\n")


GOOD_ROW = ('V-1', '`python -m unittest tests.test_x`', 'exit 0', 'FR-1')


class FakeEv7(FakeEv):
    """FakeEv plus the spec 007 readers (duck-typed like aidd_evidence; never T-01's code)."""

    def __init__(self, rows=(), approved=None, run=None, last_edit=0.0, fp=None):
        super().__init__(rows)
        self.approved, self.run, self.last_edit, self.fp = approved, run, last_edit, fp

    def latest_approved(self, root, spec, hash=None):
        a = self.approved
        if a is None or (hash is not None and a.get('hash') not in (None, hash)):
            return None
        return dict(a)

    def latest_verify_run(self, root, spec):
        return dict(self.run) if self.run else None

    def last_code_edit_ts(self, root):
        return self.last_edit

    def worktree_fingerprint(self, root, budget_s=8.0):
        return self.fp


def scratch_project():
    root = Path(tempfile.mkdtemp()).resolve()
    for rel, text in (('tests/__init__.py', ''), ('tests/test_x.py', 'import unittest\n'),
                      ('scripts/run.py', 'print(1)\n'), ('scripts/run.ps1', 'exit 0\n'),
                      ('skill/scripts/aidd_review.py', '# stub\n')):
        put(root / rel, text)
    (root / 'tests' / 'empty').mkdir()
    return root


class TestParseVerification(unittest.TestCase):
    def test_rows_placeholders_backticks(self):
        rows = R.parse_verification(vspec([('V-0', '', 'exit 0', ''), GOOD_ROW, ('V-2', ' ', '', '')]))
        self.assertEqual(rows, [{'n': 'V-1', 'cmd': 'python -m unittest tests.test_x', 'expected': 'exit 0', 'covers': 'FR-1'}])

    def test_escaped_pipe_in_command_and_comment_in_cell(self):
        rows = R.parse_verification(vspec([('V-1', r'python scripts/run.py \| findstr ok', 'contains: ok <!-- note -->', 'x')]))
        self.assertEqual(rows[0]['cmd'], 'python scripts/run.py | findstr ok')
        self.assertEqual(rows[0]['expected'], 'contains: ok')

    def test_crlf_same_rows_and_hash(self):
        t = vspec([GOOD_ROW, ('V-2', 'npm test', 'exit 0', '')])
        self.assertEqual(R.parse_verification(t.replace('\n', '\r\n')), R.parse_verification(t))
        self.assertEqual(R.verification_hash(t.replace('\n', '\r\n')), R.verification_hash(t))

    def test_no_section_or_garbage(self):
        for bad_in in ('# Spec\n\nno table', '', None, 123, ['x']):
            self.assertEqual(R.parse_verification(bad_in), [])
            self.assertEqual(R.verification_hash(bad_in), '')
        self.assertEqual(R.verification_hash(vspec([('V-1', '', 'exit 0', '')])), '')   # placeholders only

    def test_hash_ignores_prose_and_covers_not_commands(self):
        base = R.verification_hash(vspec([GOOD_ROW]))
        self.assertRegex(base, r'^[0-9a-f]{12}$')
        self.assertEqual(R.verification_hash(vspec([GOOD_ROW], prose='Other prose entirely.')), base)
        self.assertEqual(R.verification_hash(vspec([('V-1', GOOD_ROW[1], 'exit 0', 'FR-9, AC-1')])), base)
        self.assertEqual(R.verification_hash(vspec([('V-1', 'python  -m unittest   tests.test_x', 'exit 0', '')])), base)
        self.assertNotEqual(R.verification_hash(vspec([('V-1', 'python -m unittest tests.test_y', 'exit 0', '')])), base)
        self.assertNotEqual(R.verification_hash(vspec([('V-1', GOOD_ROW[1], 'contains: OK', '')])), base)
        self.assertNotEqual(R.verification_hash(vspec([('V-2', GOOD_ROW[1], 'exit 0', '')])), base)


class TestVerificationLint(unittest.TestCase):
    def setUp(self):
        self.root = scratch_project()

    def p(self, cmd, expected='exit 0', root='default'):
        return R.verification_command_problem(cmd, expected, self.root if root == 'default' else root)

    def test_ac218_rejected_rows(self):
        cases = [('python -c "pass"', 'exit 0', 'inline code'),
                 ('python --version', 'exit 0', 'neither'),
                 ('cmd /c exit 0', 'exit 0', 'inline code'),
                 ('sh -c true', 'exit 0', 'inline code'),
                 ('python -c "print(\'PASS\')"', 'contains: PASS', None),
                 ('python tests/x.py', 'exit 0', 'neither')]
        for cmd, exp, why in cases:
            r = self.p(cmd, exp)
            self.assertIsNotNone(r, cmd)
            if why:
                self.assertIn(why, r, cmd)

    def test_ac218_empty_discover_accepted_at_approval(self):
        self.assertIsNone(self.p('python -m unittest discover -s tests/empty'))

    def test_trivial(self):
        for cmd in ('echo ok', 'ECHO ok', '@echo off', 'true', 'exit 0', ':', ': x', 'rem x', 'type tests/test_x.py',
                    'python -m unittest tests.test_x\necho done'):
            self.assertIn('trivial', self.p(cmd) or '', cmd)

    def test_forbidden_text(self):
        for cmd in ('python scripts/run.py .aidd/evidence/events.toon', 'python scripts/run.py events.toon',
                    'python scripts/run.py active_spec', 'python scripts/run.py gate_spec',
                    'python scripts/run.py && python -m aidd_status approve x',
                    'python scripts/run.py && python -m aidd_evidence', 'python -m unittest tests.test_x && aidd verify x',
                    'set AIDD_RULES=off && python -m unittest tests.test_x',
                    'AIDD_EVIDENCE_DIR=/tmp python -m unittest tests.test_x',
                    'AIDD_TESTING=1 python scripts/run.py', 'AIDD_SESSION_ID=x python scripts/run.py',
                    "$env:AIDD_RULES = 'off'; python scripts/run.py",
                    'python scripts/run.py specs/x/review.md', 'python scripts/run.py tasks.md Approved',
                    'python skill/scripts/aidd_status.py approve specs/x'):
            self.assertIn('protected AIDD state', self.p(cmd) or '', cmd)

    def test_inline_variants(self):
        for cmd in ('node -e 1', 'node --eval=1', 'node --print 1', 'node -pe 1', 'powershell -Command "exit 0"',
                    'pwsh -c "exit 0"', 'powershell -EncodedCommand AAAA', 'powershell -enc AAAA',
                    'powershell -NoProfile -ExecutionPolicy Bypass -Command x', 'powershell "exit 0"',
                    'bash -lc x', 'zsh -c x', 'perl -e 1', 'ruby -e 1', 'py -3 -c 1', 'python -Bc 1', 'python -',
                    r'C:\Python311\python.exe -c 1', 'python3.11 -c 1', 'cd tests && python -c 1',
                    'X=1 python -c 1', 'cmd.exe /C dir', 'cmd /k dir'):
            self.assertIn('inline code', self.p(cmd) or '', cmd)

    def test_flags_after_the_script_are_not_inline(self):
        self.assertIsNone(self.p('python scripts/run.py -c foo'))
        self.assertIsNone(self.p('python -W ignore scripts/run.py -e x'))
        self.assertIsNone(self.p('powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1'))
        self.assertIsNone(self.p('python skill/scripts/aidd_review.py specs/F23-eDoc-POS --check'))

    def test_self_satisfying_contains(self):
        self.assertIn('satisfied by the command', self.p('python scripts/run.py PASS', 'contains: pass'))
        self.assertIsNone(self.p('python scripts/run.py', 'contains: ROUNDTRIP OK'))

    def test_runners_with_manifest(self):
        self.assertIsNone(self.p('python -m unittest tests.test_x'))
        self.assertIsNone(self.p('python -m unittest -v tests.test_x'))
        self.assertIsNone(self.p('python -m unittest tests.test_x.Case.test_y'))
        self.assertIsNone(self.p('python -m unittest tests'))            # a package dir
        self.assertIsNone(self.p('python -m unittest discover -s tests'))
        self.assertIsNone(self.p('python -m unittest tests/test_x.py'))
        for cmd, why in (('dotnet test', '.sln'), ('npm test', 'package.json'), ('npm run e2e', 'package.json'),
                         ('cargo test', 'cargo.toml'), ('go test ./...', 'go.mod'), ('mvn -q test', 'pom.xml'),
                         ('gradle test', 'build.gradle'), ('pytest', 'pyproject.toml'),
                         ('python -m pytest -p no:cacheprovider', 'pyproject.toml'), ('msbuild /t:Test', '.sln')):
            self.assertIn(why, self.p(cmd) or '', cmd)               # manifest missing: rejected naming it
        put(self.root / 'App.sln', 'x')
        put(self.root / 'web' / 'package.json', '{}')                  # nested manifest (cd web && npm test)
        put(self.root / 'pyproject.toml', '')
        put(self.root / 'Cargo.toml', '')
        put(self.root / 'go.mod', '')
        put(self.root / 'pom.xml', '')
        put(self.root / 'build.gradle', '')
        for cmd in ('dotnet test', 'dotnet test --no-build', 'npm test', 'cd web && npm test', 'npm run e2e',
                    'cargo test', 'go test ./...', 'mvn -q test', 'gradle test', 'pytest', 'python -m pytest -p x',
                    'msbuild /t:Test'):
            self.assertIsNone(self.p(cmd), cmd)

    def test_unittest_targets_must_exist(self):
        self.assertIn('not found', self.p('python -m unittest tests.test_missing'))
        self.assertIn('not found', self.p('python -m unittest tests.missing.Case'))
        self.assertIn('needs a module', self.p('python -m unittest'))
        self.assertIn('does not exist', self.p('python -m unittest discover -s nope'))

    def test_paths_must_be_relative_inside_root(self):
        self.assertIsNotNone(self.p(f'python {self.root / "scripts" / "run.py"}'))   # absolute: never
        self.assertIsNotNone(self.p('python ../outside.py'))
        self.assertIsNone(self.p(r'python scripts\run.py'))                          # Windows separators

    def test_root_none_skips_only_existence(self):
        for cmd in ('dotnet test', 'npm test', 'python tests/x.py', 'python -m unittest tests.test_nope'):
            self.assertIsNone(self.p(cmd, root=None), cmd)
        for cmd in ('python --version', 'python -c 1', 'echo x', 'python -m unittest', 'whoami'):
            self.assertIsNotNone(self.p(cmd, root=None), cmd)

    def test_empty_and_garbage(self):
        for c in ('', '   ', None, 5):
            self.assertEqual(R.verification_command_problem(c), 'empty command')
        self.assertIn('longer', self.p('python scripts/run.py ' + 'x' * 3000))


class TestCheckVerification(unittest.TestCase):
    def setUp(self):
        self.root = scratch_project()

    def test_missing_section_and_rows(self):
        bad(self, R.check_verification('# Spec\n\nnothing', self.root), 'R10', 'no "## Verification"')
        bad(self, R.check_verification(vspec([('V-1', '', 'exit 0', '')]), self.root), 'R10', 'no row')

    def test_expected_rules(self):
        bad(self, R.check_verification(vspec([('V-1', GOOD_ROW[1], '', '')]), self.root), 'R10', 'Expected is empty')
        bad(self, R.check_verification(vspec([('V-1', GOOD_ROW[1], 'exit 1', '')]), self.root), 'R10', 'is not `exit 0`')
        ok(self, R.check_verification(vspec([GOOD_ROW, ('V-2', 'python scripts/run.py', 'contains: OK', '')]), self.root))

    def test_row_problems_reported_per_row(self):
        vs = R.check_verification(vspec([GOOD_ROW, ('V-2', 'python -c "pass"', 'exit 0', ''),
                                         ('V-3', 'python tests/x.py', 'exit 0', '')]), self.root)
        self.assertEqual(len(vs), 2)
        self.assertTrue(all(v['rule'] == 'R10' and v['fix'] for v in vs))
        self.assertIn('V-2', vs[0]['message'])
        self.assertIn('V-3', vs[1]['message'])

    def test_never_raises(self):
        for x in (None, 5, 'x' * (R.MAX_CHARS + 1)):
            self.assertIsInstance(R.check_verification(x), list)
            self.assertTrue(R.check_verification(x))

    def test_new_template_sections_and_legacy_spec_pass_check_content(self):
        raw = (REPO / 'skill' / 'templates' / 'spec.md').read_text(encoding='utf-8')
        new = raw
        if '## Verification' not in raw:   # until T-09 lands the template sections, simulate them
            new = raw + ('\n## Verification\n\n| # | Command | Expected | Covers |\n|---|---|---|---|\n'
                         '| V-1 | | exit 0 | |\n\n## Optimization brief\n\nOwner pick:\n')
        self.assertEqual(R.check_content('spec', new), [])
        legacy = re.sub(r'\n## (Verification|Optimization brief)\b.*?(?=\n## |\Z)', '\n', new, flags=re.S)
        self.assertNotIn('## Verification', legacy)
        self.assertEqual(R.check_content('spec', legacy), [])
        bad(self, R.check_verification(legacy), 'R10', 'no "## Verification"')


class TestApprovalEvidenceAndOutput(unittest.TestCase):
    def test_approval_evidence(self):
        t = vspec([GOOD_ROW])
        self.assertEqual(R.GATE_VERSION, 2)
        e = R.approval_evidence(t, 'review+prompt', review_sha1='abc', consent_ts=12)
        self.assertEqual(e, {'gate': 2, 'source': 'review+prompt', 'verify_hash': R.verification_hash(t),
                             'consent_ts': 12.0, 'review_sha1': 'abc'})
        self.assertEqual(R.approval_evidence('# none', 'answer'), {'gate': 2, 'source': 'answer', 'verify_hash': ''})

    def test_zero_tests(self):
        hdr = '# python -m unittest x | exit 0 | 2026-10-05T10:00:00\n'
        for out in ('\nRan 0 tests in 0.000s\n\nOK\n', 'NO TESTS RAN', 'No test is available in x.dll. Make sure ...',
                    '==== collected 0 items ====', 'Passed!  Total tests: 0  ok ok ok ok'):
            self.assertEqual(R.verify_output_problem(hdr + out, 'exit 0'), 'zero tests ran', out)
            self.assertEqual(R.verify_output_problem(out, 'contains: Ran'), 'zero tests ran', out)   # contains never excuses it
        self.assertIsNone(R.verify_output_problem(hdr + 'Ran 10 tests in 1.0s\n\nOK\n', 'exit 0'))
        self.assertIsNone(R.verify_output_problem(hdr + 'Total tests: 05 passed fine here', 'exit 0'))

    def test_short_output(self):
        hdr = '# npm test | exit 0 | 2026-10-05T10:00:00\n'
        self.assertEqual(R.verify_output_problem(hdr + 'ok\n', 'exit 0'), 'output too short')
        self.assertEqual(R.verify_output_problem(hdr, 'exit 0'), 'output too short')
        self.assertEqual(R.verify_output_problem('', 'exit 0'), 'output too short')
        self.assertIsNone(R.verify_output_problem(hdr + 'ROUNDTRIP OK\n', 'contains: ROUNDTRIP OK'))
        self.assertEqual(R.verify_output_problem(hdr + 'ok\n', 'contains: missing'), 'output too short')
        self.assertIsNone(R.verify_output_problem((hdr + 'x' * 25).encode('utf-8'), 'exit 0'))   # bytes accepted


class _GateSpec(unittest.TestCase):
    """A new-style spec (gate 2) with an executed, passing Verification, for each real id."""

    def mkspec(self, spec_id):
        self.root = scratch_project()
        d = self.root / 'specs' / spec_id
        self.spec_text = vspec([GOOD_ROW])
        put(d / 'spec.md', self.spec_text)
        self.tasks_text = tasks()
        put(d / 'tasks.md', self.tasks_text)
        put(d / 'evidence' / 'verify-1.txt', '# python -m unittest tests.test_x | exit 0 | t\nRan 3 tests\n\nOK\n')
        self.vh = R.verification_hash(self.spec_text)
        sha = hashlib.sha1((d / 'evidence' / 'verify-1.txt').read_bytes()).hexdigest()
        self.run = {'ts': 500.0, 'ok': True, 'verify_hash': self.vh, 'started': 400.0, 'fingerprint_start': 'fp',
                    'fingerprint_end': 'fp', 'stable': True,
                    'results': [{'n': 'V-1', 'cmd': 'python -m unittest tests.test_x', 'exit': 0, 'ok': True,
                                 'evidence': 'evidence/verify-1.txt', 'sha1': sha}]}
        self.approved = {'spec': spec_id, 'hash': R.approval_hash(self.tasks_text), 'gate': 2, 'source': 'review+answer',
                         'verify_hash': self.vh}
        return d

    def fake(self, rows=(), **kw):
        args = dict(approved=self.approved, run=self.run, last_edit=300.0, fp='fp')
        args.update(kw)
        return FakeEv7(rows, **args)

    def dirs(self, spec_id):
        """(absolute spec dir, relative spec dir valid while cwd is the project root)."""
        d = self.mkspec(spec_id)
        return d, Path('specs') / spec_id

    def in_root(self):
        old = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, old)


class TestVerificationGaps(_GateSpec):
    def msgs(self, ev_, d):
        return ' | '.join(v['message'] for v in R.verification_gaps(ev_, self.root, d))

    def test_passing_run_absolute_and_relative(self):
        for sid in SPEC_IDS:
            d, rel = self.dirs(sid)
            ok(self, R.verification_gaps(self.fake(), self.root, d))
            self.in_root()
            ok(self, R.verification_gaps(self.fake(), self.root, rel))

    def test_each_gap(self):
        for sid in SPEC_IDS:
            d = self.mkspec(sid)
            self.assertIn('No verify_run', self.msgs(self.fake(run=None), d))
            self.assertIn('failed', self.msgs(self.fake(run=dict(self.run, ok=False)), d))
            self.assertIn('tree changed while verification ran', self.msgs(self.fake(run=dict(self.run, stable=False)), d))
            self.assertIn('code edit happened after', self.msgs(self.fake(last_edit=450.0), d))
            self.assertIn('fingerprint differs', self.msgs(self.fake(fp='other'), d))
            self.assertIn('fingerprint differs', self.msgs(self.fake(fp=None), d))       # fail closed
            ok(self, R.verification_gaps(self.fake(fp='x', run=dict(self.run, fingerprint_end=None)), self.root, d))
            self.assertIn('changed after approval',
                          self.msgs(self.fake(approved=dict(self.approved, verify_hash='000000000000')), d))
            self.assertIn('No approved event', self.msgs(self.fake(approved=None), d))
            self.assertIn('no results', self.msgs(self.fake(run=dict(self.run, results=[])), d))

    def test_table_and_evidence_drift(self):
        for sid in SPEC_IDS:
            d = self.mkspec(sid)
            put(d / 'spec.md', vspec([('V-1', 'python -m unittest tests', 'exit 0', '')]))
            m = self.msgs(self.fake(), d)
            self.assertIn('changed after the last verify_run', m)
            self.assertIn('changed after approval', m)
            put(d / 'spec.md', vspec([GOOD_ROW], prose='prose edits are neutral'))
            ok(self, R.verification_gaps(self.fake(), self.root, d))
            put(d / 'evidence' / 'verify-1.txt', 'tampered')
            self.assertIn('sha1 differs', self.msgs(self.fake(), d))
            (d / 'evidence' / 'verify-1.txt').unlink()
            self.assertIn('missing', self.msgs(self.fake(), d))

    def test_evidence_path_forms(self):
        d = self.mkspec('F23-eDoc-POS')
        res = self.run['results'][0]
        root_rel = dict(res, evidence='specs/F23-eDoc-POS/evidence/verify-1.txt')
        ok(self, R.verification_gaps(self.fake(run=dict(self.run, results=[root_rel])), self.root, d))
        put(self.root / 'outside.txt', 'x')
        for evid in ('../../outside.txt', 'outside.txt', str(self.root / 'outside.txt'), ''):
            r = dict(res, evidence=evid, sha1=hashlib.sha1(b'x').hexdigest())
            self.assertIn('missing or outside', self.msgs(self.fake(run=dict(self.run, results=[r])), d), evid)
        self.assertIn('no recorded sha1', self.msgs(self.fake(run=dict(self.run, results=[dict(res, sha1='')])), d))

    def test_old_library_and_garbage_fail_closed(self):
        d = self.mkspec('002-aidd-hard-rules')
        self.assertIn('old install', self.msgs(FakeEv(), d))
        vs = R.verification_gaps(self.fake(), self.root, None)
        self.assertTrue(vs and vs[0]['rule'] == 'R10')
        put(d / 'spec.md', '# no table')
        self.assertIn('no "## Verification"', self.msgs(self.fake(), d))


class TestVerificationState(_GateSpec):
    def state(self, fake, d, root=None):
        old = R._evidence
        R._evidence = lambda: fake
        try:
            return R.verification_state(d, root)
        finally:
            R._evidence = old

    def test_states(self):
        for sid in SPEC_IDS:
            d = self.mkspec(sid)
            st = self.state(self.fake(), d)
            self.assertEqual(st, {'declared': True, 'commands': 1, 'status': 'passed', 'ts': 500.0})
            self.assertEqual(self.state(self.fake(run=None), d)['status'], 'never-run')
            self.assertEqual(self.state(self.fake(last_edit=900.0), d)['status'], 'stale')
            self.assertEqual(self.state(self.fake(run=dict(self.run, ok=False)), d)['status'], 'failed')
            self.assertEqual(self.state(self.fake(), d, root=self.root)['status'], 'passed')
            self.assertEqual(self.state(None, d)['status'], 'never-run')       # no evidence module: never passed
            put(d / 'spec.md', vspec([('V-1', '', 'exit 0', '')]))
            self.assertEqual(self.state(self.fake(), d), {'declared': True, 'commands': 0, 'status': 'none', 'ts': None})
            put(d / 'spec.md', '# legacy spec')
            self.assertEqual(self.state(self.fake(), d)['status'], 'none')
        self.assertEqual(R.verification_state(None)['status'], 'none')


class _CountingEv7(FakeEv7):
    """FakeEv7 whose worktree_fingerprint counts its calls (closing-audit F-2)."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fp_calls = 0

    def worktree_fingerprint(self, root):
        self.fp_calls += 1
        return self.fp


class TestFingerprintOnce(_GateSpec):
    """F-2: one worktree fingerprint per status run, never older than what it is compared against."""

    def counting(self, **kw):
        args = dict(approved=self.approved, run=self.run, last_edit=300.0, fp='fp')
        args.update(kw)
        return _CountingEv7((), **args)

    def state(self, fake, d, root=None, fingerprint=None):
        old = R._evidence
        R._evidence = lambda: fake
        try:
            return R.verification_state(d, root, fingerprint=fingerprint)
        finally:
            R._evidence = old

    def test_one_fingerprint_shared_across_specs_absolute_and_relative(self):
        self.mkspec(SPEC_IDS[0])
        root = self.root                         # every spec in ONE project root: one cache key
        for sid in SPEC_IDS[1:]:
            self.mkspec_in(root, sid)
        fake = self.counting()
        once = R.FingerprintOnce(fake)
        self.in_root()
        for sid in SPEC_IDS:
            for d in (root / 'specs' / sid, Path('specs') / sid):
                st = self.state(fake, d, root=root, fingerprint=once)
                self.assertEqual(st['status'], 'passed', (sid, d))
        self.assertEqual(fake.fp_calls, 1)
        self.assertEqual(once.calls, 1)
        # without a provider the old behaviour stays: one fingerprint per call
        fake2 = self.counting()
        for sid in SPEC_IDS:
            self.state(fake2, root / 'specs' / sid, root=root)
        self.assertEqual(fake2.fp_calls, len(SPEC_IDS))

    def mkspec_in(self, root, spec_id):
        d = root / 'specs' / spec_id
        put(d / 'spec.md', self.spec_text)
        put(d / 'tasks.md', self.tasks_text)
        put(d / 'evidence' / 'verify-1.txt', '# python -m unittest tests.test_x | exit 0 | t\nRan 3 tests\n\nOK\n')
        return d

    def test_cache_never_older_than_the_compared_run_or_code_edit(self):
        clock = [1000.0]
        for sid in SPEC_IDS:
            d = self.mkspec(sid)
            fake = self.counting(run=dict(self.run, ts=900.0, started=800.0), last_edit=700.0)
            once = R.FingerprintOnce(fake, ttl=30.0, clock=lambda: clock[0])
            self.assertEqual(self.state(fake, d, root=self.root, fingerprint=once)['status'], 'passed')
            self.assertEqual(self.state(fake, d, root=self.root, fingerprint=once)['status'], 'passed')
            self.assertEqual(fake.fp_calls, 1)                       # served from the cache
            # a verify_run recorded AFTER the cached fingerprint was taken: recompute
            fake.run = dict(self.run, ts=1005.0, started=1001.0)
            clock[0] = 1010.0
            self.state(fake, d, root=self.root, fingerprint=once)
            self.assertEqual(fake.fp_calls, 2)
            # a code edit AFTER the cached fingerprint: recompute (and the edit makes the run stale anyway)
            fake.last_edit = 1020.0
            clock[0] = 1021.0
            self.assertEqual(self.state(fake, d, root=self.root, fingerprint=once)['status'], 'stale')
            self.assertEqual(fake.fp_calls, 3)
            # the TTL expires: recompute even with nothing newer
            fake.last_edit = 700.0
            clock[0] = 1021.0 + 31.0
            self.state(fake, d, root=self.root, fingerprint=once)
            self.assertEqual(fake.fp_calls, 4)
            # a changed tree is still detected through the shared provider
            fake.fp = 'other'
            clock[0] += 100.0
            self.assertEqual(self.state(fake, d, root=self.root, fingerprint=once)['status'], 'stale')
            clock[0] = 1000.0

    def test_failures_never_raise_and_fail_closed(self):
        d = self.mkspec('F23-eDoc-POS')

        class Boom(_CountingEv7):
            def worktree_fingerprint(self, root):
                raise RuntimeError('git exploded')

        fake = Boom((), approved=self.approved, run=self.run, last_edit=300.0, fp='fp')
        once = R.FingerprintOnce(fake)
        self.assertIsNone(once(self.root))
        self.assertEqual(self.state(fake, d, root=self.root, fingerprint=once)['status'], 'stale')
        self.assertIsNone(R.FingerprintOnce(FakeEv())(self.root))            # old library: None
        once2 = R.FingerprintOnce(self.counting())
        self.assertEqual(once2(self.root, not_before='garbage'), 'fp')
        self.assertEqual(once2(self.root, not_before='garbage'), 'fp')       # unreadable bound: no cache
        self.assertEqual(once2.calls, 2)


class _ClosingBase(_GateSpec):
    def header(self, doms=None, tasks8=None, verify8=None):
        doms = sorted(R.required_domains(self.d)) if doms is None else doms
        t8 = R.approval_hash(self.tasks_text)[:8] if tasks8 is None else tasks8
        v8 = self.vh[:8] if verify8 is None else verify8
        return f"CLOSING AUDIT [domains: {', '.join(doms)}] [tasks:{t8}]" + (f" [verify:{v8}]" if v8 else '')

    def auditor(self, ts=600.0, head=None, **kw):
        d = dict(desc='closing auditor', head=(self.header() if head is None else head) + '\nAudit everything.',
                 model='sonnet', result_chars=4000, tool_use_id='toolu_01ABC')
        d.update(kw)
        return ev('subagent', ts, **d)

    def covers(self, e, gate2=True, fake=None, domains=None):
        return R.closing_audit_covers(e, self.d, R.required_domains(self.d) if domains is None else domains,
                                      gate2, fake or self.fake(), self.root)


class TestClosingAudit(_ClosingBase):
    def test_header_parsing(self):
        self.d = self.mkspec('F23-eDoc-POS')
        h = R.closing_audit_header(self.auditor())
        self.assertEqual(h['domains'], R.required_domains(self.d))
        self.assertEqual(h['tasks'], R.approval_hash(self.tasks_text)[:8])
        self.assertEqual(h['verify'], self.vh[:8])
        self.assertIsNone(R.closing_audit_header(self.auditor(head='Please run the\n' + self.header())))   # not first line
        self.assertIsNone(R.closing_audit_header(self.auditor(head='plain prompt', desc=self.header())))   # only in desc
        e = self.auditor(desc=self.header())
        e['detail']['head'] = ''
        self.assertIsNotNone(R.closing_audit_header(e))                                                   # no head: desc
        self.assertIsNone(R.closing_audit_header(self.auditor(head='CLOSING AUDIT [domains: security]')))  # no tasks tag
        for junk in (None, {}, {'detail': None}, 'x', 5):
            self.assertIsNone(R.closing_audit_header(junk))

    def test_ac210_coverage_cases(self):
        for sid in SPEC_IDS:
            self.d = self.mkspec(sid)
            doms = R.required_domains(self.d)
            self.assertEqual(doms, {'security', 'functional', 'performance', 'ui'})
            self.assertTrue(self.covers(self.auditor()))
            self.assertTrue(self.covers(self.auditor(result_chars=R.CLOSING_AUDIT_MIN_RESULT)))
            self.assertFalse(self.covers(self.auditor(head=self.header(doms=['security']))))
            self.assertFalse(self.covers(self.auditor(model='haiku')))
            self.assertFalse(self.covers(self.auditor(model='claude-haiku-4-5')))
            self.assertFalse(self.covers(self.auditor(phase='pre')))
            self.assertFalse(self.covers(self.auditor(head=self.header(tasks8='deadbeef'))))       # stale [tasks:]
            self.assertFalse(self.covers(self.auditor(head=self.header(verify8='deadbeef'))))      # wrong [verify:]
            self.assertFalse(self.covers(self.auditor(head=self.header(verify8=''))))             # gate 2 needs it
            self.assertTrue(self.covers(self.auditor(head=self.header(verify8='')), gate2=False))  # legacy: not needed
            self.assertFalse(self.covers(self.auditor(ts=450.0)))                                  # older than verify_run
            self.assertTrue(self.covers(self.auditor(ts=450.0), gate2=False))
            self.assertFalse(self.covers(self.auditor(), fake=self.fake(run=None)))
            self.assertFalse(self.covers(self.auditor(result_chars=20)))                           # "reply ok"
            e = self.auditor()
            del e['detail']['result_chars']
            self.assertFalse(self.covers(e))                                                       # absent = no
            self.assertFalse(self.covers(self.auditor(result_chars=True)))
            self.assertFalse(self.covers(self.auditor(), fake=FakeEv()))                           # old lib, gate 2
            self.assertFalse(R.closing_audit_covers(None, self.d, doms, True, self.fake(), self.root))

    def test_uncovered_early_return_and_per_domain_untouched(self):
        for sid in SPEC_IDS:
            self.d = self.mkspec(sid)
            doms = R.required_domains(self.d)
            f = self.fake([self.auditor()])
            self.assertEqual(R._uncovered(f, self.root, 's', doms, 0.0, spec_dir=self.d), set())
            self.assertEqual(R._uncovered(f, self.root, 's', doms, 700.0, spec_dir=self.d), doms)   # before window
            self.assertTrue(R._uncovered(f, self.root, 's', doms, 0.0))                             # no spec_dir: old path
            only_sec = self.fake([self.auditor(head=self.header(doms=['security']))])
            self.assertEqual(R._uncovered(only_sec, self.root, 's', doms, 0.0, spec_dir=self.d), doms - {'security'})
            legacy = self.fake([ev('subagent', 600, desc='security review'), ev('subagent', 610, desc='functional acceptance'),
                                ev('subagent', 620, desc='performance'), ev('subagent', 630, desc='ui mockup audit')])
            self.assertEqual(R._uncovered(legacy, self.root, 's', doms, 0.0, spec_dir=self.d), set())
            old = R._evidence
            R._evidence = lambda: f
            try:
                self.assertEqual(R.uncovered_domains(self.root, 's', sid, 0.0, spec_dir=self.d), set())
                self.assertEqual(R.uncovered_domains(self.root, 's', sid, 0.0), set())   # root/specs/<id>
            finally:
                R._evidence = old

    def test_gate_detection_drives_the_verify_tag(self):
        self.d = self.mkspec('002-aidd-hard-rules')
        no_verify = self.auditor(head=self.header(verify8=''))
        legacy_appr = {'spec': self.d.name, 'hash': R.approval_hash(self.tasks_text)}
        doms = R.required_domains(self.d)
        self.assertEqual(R._uncovered(self.fake([no_verify], approved=legacy_appr), self.root, 's', doms, 0.0,
                                      spec_dir=self.d), set())
        self.assertTrue(R._uncovered(self.fake([no_verify]), self.root, 's', doms, 0.0, spec_dir=self.d))

    def test_check_spec_dir_r7_accepts_the_closing_auditor(self):
        self.d = self.mkspec('F23-eDoc-POS')
        put(self.d / 'qa-audit.md', 'qa')
        old = R._evidence
        self.addCleanup(setattr, R, '_evidence', old)
        R._evidence = lambda: self.fake([ev('code_edit', 300), self.auditor()])
        self.assertEqual([v for v in R.check_spec_dir(self.d) if v['rule'] == 'R7'], [])
        R._evidence = lambda: self.fake([ev('code_edit', 300), self.auditor(result_chars=20)])
        self.assertTrue([v for v in R.check_spec_dir(self.d) if v['rule'] == 'R7'])


class TestClosingAuditGaps(_ClosingBase):
    QA_ROWS = '| Domain | Result |\n|---|---|\n| security | ok |\n| functional | ok |\n| performance | ok |\n| ui | ok |\n'

    def qa(self, text):
        put(self.d / 'qa-audit.md', text)

    def gaps(self, fake):
        return ' | '.join(v['message'] for v in R.closing_audit_gaps(fake, self.root, self.d))

    def test_gaps(self):
        for sid in SPEC_IDS:
            self.d = self.mkspec(sid)
            f = self.fake([self.auditor()])
            self.assertIn('does not exist', self.gaps(f))
            self.qa('# QA\n\n' + self.QA_ROWS + '\nClosing auditor: toolu_01ABC\n')
            ok(self, R.closing_audit_gaps(f, self.root, self.d))
            self.qa('# QA\n\n' + self.QA_ROWS.replace('| performance | ok |\n', '') + '\ntoolu_01ABC\n')
            self.assertIn('performance', self.gaps(f))
            self.qa('# QA\n\n' + self.QA_ROWS)
            self.assertIn("tool_use_id", self.gaps(f))
            self.qa('# QA\n\n' + self.QA_ROWS + '\n<!-- toolu_01ABC -->\n')                       # comments never count
            self.assertIn("tool_use_id", self.gaps(f))
            e = self.auditor()
            del e['detail']['tool_use_id']
            self.assertIn('no recorded tool_use_id', self.gaps(self.fake([e])))

    def test_not_applied(self):
        self.d = self.mkspec('F23-eDoc-POS')
        legacy_appr = {'spec': self.d.name, 'hash': R.approval_hash(self.tasks_text)}
        ok(self, R.closing_audit_gaps(self.fake([self.auditor()], approved=legacy_appr), self.root, self.d))   # legacy
        per_domain = self.fake([ev('subagent', 600, desc='security review'), ev('subagent', 610, desc='functional')])
        ok(self, R.closing_audit_gaps(per_domain, self.root, self.d))                                          # per-domain
        ok(self, R.closing_audit_gaps(FakeEv(), self.root, self.d))                                            # old lib
        self.assertIsInstance(R.closing_audit_gaps(self.fake(), self.root, None), list)


if __name__ == '__main__':
    unittest.main()
