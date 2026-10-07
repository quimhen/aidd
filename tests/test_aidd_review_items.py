"""Tests for skill/scripts/aidd_review_items.py (spec 008, T-01: FR-301, FR-302, FR-311, FR-312, FR-313).

The module is pure: every test feeds plain texts. The fixtures rebuild the REAL shapes of the
b1SycLink specs read on 2026-10-05 (headings, table headers, code lists and their order, the
uncoded rows); `TestRealFiles` additionally runs on the real files when that checkout exists
(only the five review sources are read, never review.md / review.html).

Run: python -m unittest tests.test_aidd_review_items
"""
import json
import os
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import aidd_review_items as I  # noqa: E402

SOURCES = ('spec.md', 'plan.md', 'tasks.md', 'mockup-audit.md', 'contracts.md')
CODE_RE_LITERAL = (r'^(SUMMARY|Q\d{1,3}|D\d{1,3}(?:-?[a-z])?|V-\d{1,3}|(?:FR|AC|T)-\d{1,4}(?:-?[a-z])?|'
                   r'(?:API|COMP|CTL|SCREEN)-\d{1,5}(?:-?[a-z])?)$')
SPEC_IDS = ('002-aidd-hard-rules', 'F23-eDoc-POS')


def table(header, rows):
    out = ['| ' + ' | '.join(header) + ' |', '|' + '---|' * len(header)]
    out += ['| ' + ' | '.join(r) + ' |' for r in rows]
    return '\n'.join(out)


CHECKLIST_Q = (
    'Which module/area of the system?',
    'New development or modification of something existing?',
    'Does it involve an external service, API, or integration?',
    'Who is requesting it? (role/profile, not necessarily the name)',
    'Dependencies on other modules or active developments?',
    'Business objective (1 sentence — what it achieves and why)',
    'Expected visual fidelity level (if there\'s a mockup): exact \\| functional behavior only',
)
ALIGN_Q = (
    'Which states must each screen/flow handle (empty, loading, error, offline)?',
    'Who may see or do this (permissions/roles)?',
    'Entry route: how does the user reach this from the app\'s start?',
    'Target devices (phone, tablet, desktop, orientation)?',
    'Contract owner and status (who defines the backend contract, is it final or still moving)?',
)
# F28 real orders (spec.md read 2026-10-05)
F28_D = (['D%d' % n for n in range(1, 14)] + ['D15', 'D16', 'D17', 'D18', 'D19', 'D20']
         + ['D%d' % n for n in range(25, 31)] + ['D21', 'D22', 'D23', 'D24', 'D24b', 'D24c']
         + ['D%d' % n for n in range(31, 39)] + ['D14'])
F28_FR = (['FR-001', 'FR-002', 'FR-003', 'FR-004', 'FR-004b', 'FR-004c']
          + ['FR-%03d' % n for n in range(5, 17)] + ['FR-027', 'FR-028', 'FR-017']
          + ['FR-%03d' % n for n in range(22, 27)] + ['FR-019', 'FR-020', 'FR-021', 'FR-018'])
F28_AC = ['AC-%03d' % n for n in range(1, 8)] + ['AC-007b'] + ['AC-%03d' % n for n in range(8, 17)]
F28_API = (['API-%d' % n for n in range(501, 512)] + ['API-520', 'API-521']
           + ['API-%d' % n for n in range(512, 520)])
F28_T = ['T-%02d' % n for n in range(1, 50)]
F28_OBJECTIVE = 'Que las tablas del core y del mobile sincronicen sin duplicados'


def f28_spec(extra_fr=None, drop_fr=None, insert_before_q4=None, risks='Riesgos del core.'):
    chk = [[q, 'Respuesta %d' % i if 'Business objective' not in q else F28_OBJECTIVE,
            'user — "respuesta del owner %d"' % i, '→ Step 2 align question']
           for i, q in enumerate(CHECKLIST_Q, 1)]
    if insert_before_q4:
        chk.insert(3, [insert_before_q4, 'Nueva respuesta', 'user — "nueva fila"', ''])
    fr_rows = [[c, 'Requisito %s del hub de sync' % c, 'D1'] for c in F28_FR if c != drop_fr]
    if extra_fr:
        fr_rows += extra_fr
    align = [[ALIGN_Q[0], 'Estados vacios y offline', 'user — "estados del owner"'],
             [ALIGN_Q[1], 'El vendedor ve solo sus sucursales', 'user — "permisos del owner"'],
             [ALIGN_Q[2], '', ''], [ALIGN_Q[3], '', ''], [ALIGN_Q[4], 'Supabase', 'repo — x.sql:1']]
    return '\n\n'.join([
        '# F28 · DB Unification & Sync (b1SyncLink core ↔ mobile offline)',
        '## Pipeline route',
        table(['Step', 'Status', 'Reason', 'Confirmation'], [['-1', 'run', 'x', 'user — "si"']]),
        '## Minimum Requirements Checklist',
        table(['Question', 'Answer', 'Source', 'If unanswered'], chk),
        '## Decisions (docs/db-graph/sync-optimization.md §9)',
        table(['#', 'Decision', 'Source'],
              [[d, 'Decision %s del owner' % d, 'user — "cita %s"' % d] for d in F28_D]),
        '## Functional requirements (cite codes, don\'t redescribe the UI)',
        table(['FR-nnn', 'Requirement', 'Cites'], fr_rows),
        '## Acceptance cases',
        table(['Case', 'Real data (id)', 'Expected', 'Edge?'],
              [[c, 'pendiente: dato real %s' % c, 'Resultado %s' % c, 'yes' if c in ('AC-002', 'AC-007b') else 'no']
               for c in F28_AC]),
        '## Verification',
        table(['#', 'Command', 'Expected', 'Covers'],
              [['V-%d' % n, '`python -m pytest suite%d -q`' % n, 'exit 0', 'FR-00%d' % n] for n in range(1, 6)]),
        '## Risks and residuals',
        '- ' + risks,
        '## Optional Align questions',
        table(['Question', 'Answer', 'Source'], align),
    ]) + '\n'


def f28_contracts():
    return '\n\n'.join([
        '# API Contracts — F28 DB Unification & Sync',
        table(['API-nnn', 'Method + path', 'Request schema', 'Response schema'],
              [[a, '`POST /rest/v1/rpc/fe_%s`' % a.lower().replace('-', '_'), '{ p_comp }', '{ ok }'] for a in F28_API]),
        '## Contract details',
        '### API-501 — `fe_sync_push` (motor anti-duplicados y proceso)',
        '### API-502 / API-503 — resolución de conflictos y sospechas',
    ]) + '\n'


def f28_target(t):
    n = int(t[2:])
    return '`eDoc/supabase/migrations/%04d_sync.sql` + `eDoc/supabase/tests/%04d.test.sql`' % (240 + n, 240 + n)


def f28_tasks(t17_text=None):
    rows = []
    for t in F28_T:
        codes = 'FR-001, D1, D11' if t != 'T-17' else (t17_text or 'FR-012, D30')
        rows.append([t, codes, f28_target(t), 'LOGIC', '', 'pending', 'archivos no listados'])
    blocks = []
    for t in F28_T:
        blocks.append('### %s\n**Classify**\n- Nature: REQUIREMENT\n\n**Estimate**\n- Agent min: 6\n'
                      '- Human ref hours: 0.3\n- Tokens (est): 45k\n- Agent role: sql\n\n**Decompose**\n'
                      '- Objective: objetivo de %s\n' % (t, t))
    waves = [[str(i), 'T-%02d' % i, 'builder', '30', '100', '1.5'] for i in range(1, 11)]
    return '\n\n'.join([
        '# Tasks — F28 DB Unification & Sync',
        table(['Task', 'Codes satisfied (FR/D/API/AC)', 'Target file', 'View / logic', 'Tracker ref',
               'Status', 'Explicitly out of scope'], rows),
        '## Per-task detail (one block per row above)',
        '\n\n'.join(blocks),
        '## Waves',
        table(['Wave', 'Tasks', 'Roles', 'Agent time (min)', 'Tokens (k)', 'Human ref (h)'], waves),
        'Total agent time (critical path): 300 min\nTotal tokens (k): 1000',
        '## Coverage cross-check',
        'Verificado por script.',
    ]) + '\n'


def f28_sources(**kw):
    t17 = kw.pop('t17_text', None)
    return {'spec.md': f28_spec(**kw), 'plan.md': '# Plan\n\nprosa\n', 'tasks.md': f28_tasks(t17),
            'mockup-audit.md': None, 'contracts.md': f28_contracts()}


F23_DECISIONS = ('C1, C2, C3', 'C5', 'C6', 'C9', 'C10', 'C11', 'C12', 'C13, D18', 'C14, C17', 'C15',
                 'D12–D15', '8c', 'F12', 'User')
F23_CASES = ('Mixed payment sale', 'Payment one cent short', 'Consumer final at the limit',
             'Cash count at the threshold', 'Held sale retention', 'Prorated return', 'Return threshold',
             'Terminal point not in the branch', 'Close versus sale', 'Grant bound to another line',
             'Terminal and method catalog', 'Shift open guards', 'Card count difference', 'Ticket text',
             'Row level security', 'Barcode reading speed', 'Performance and last unit', 'Isolation grep',
             'POS disabled', 'Idempotency mismatch', 'Cash move threshold', 'Hold reservation', 'Audit trail',
             'Parameter defaults', 'Document checks', 'Parameter suite stays green', 'Shift summary',
             'Authorizations in report', 'Applied migrations')


def f23_spec(summary=None, align_rows=None):
    chk = [[q, 'Answer %d' % i if i != 5 else '', '[Proposed — unconfirmed]' if i == 2 else 'user — "owner words %d"' % i, '']
           for i, q in enumerate(CHECKLIST_Q, 1)]
    parts = ['# Spec — F23 · eDoc POS (b1SyncLink.eDoc)',
             '## Minimum Requirements Checklist',
             table(['Question', 'Answer', 'Source', 'If unanswered'], chk)]
    if summary is not None:
        parts += ['## Executive summary', summary]
    parts += [
        '## Decisions inherited (not reopened here)',
        table(['Id', 'Decision', 'Where it came from'], [[d, 'decision text', 'proposal'] for d in F23_DECISIONS]),
        '## Functional requirements',
        table(['FR-nnn', 'Requirement', 'Cites (SCREEN / COMP / API / tables)'],
              [['FR-%03d' % n, '**Requirement %d.** text' % n, 'API-300'] for n in range(1, 33)]),
        '## Acceptance cases',
        'Real-data cases (ids are the seed ids of the pgTAP fixtures).',
        table(['Case', 'Real data (id)', 'Expected', 'Edge?'], [[c, 'data', 'expected', 'yes'] for c in F23_CASES]),
        '## Acceptance (verifiable, per spec)',
        '1. Applying migrations 0200-0207 succeeds.',
    ]
    if align_rows is not None:
        parts += ['## Optional Align questions', table(['Question', 'Answer', 'Source'], align_rows)]
    return '\n\n'.join(parts) + '\n'


def f23_tasks():
    rows = [['T-01', 'FR-001, FR-002, API-312', '`eDoc/supabase/migrations/0200_pos_pay_methods.sql`', 'LOGIC', '', '', 'x'],
            ['T-02', 'FR-003, API-311', '`eDoc/supabase/migrations/0201_pos_terminals_shifts.sql`', 'LOGIC', '', '', 'x'],
            ['T-03', 'FR-012, API-027', '`eDoc/supabase/migrations/0202_pos_document_columns.sql`', 'LOGIC', '', '', 'x'],
            ['T-04', 'SCREEN-21', '`edoc-web/src/pos/PosScreen.tsx`; `edoc-web/src/pos/PosScreen.test.tsx`', 'VIEW-new', '', '', 'x']]
    return '\n\n'.join([
        '# Tasks — F23',
        table(['Task', 'Codes satisfied (SCREEN/COMP/CTL/API)', 'Target file', 'View / logic', 'Tracker ref',
               'Status', 'Explicitly out of scope'], rows),
        '## Waves',
        'Waves run one after another.',
        table(['Wave', 'Tasks', 'Roles', 'Agent time (min)', 'Tokens (k)', 'Human ref (h)'],
              [['1', 'T-01, T-02', 'builder, sql', '25', '214', '48'], ['2', 'T-03, T-04', 'builder', '25', '321', '49']]),
    ]) + '\n'


def template_sources():
    """The untouched skill templates (shapes of skill/templates/*.md)."""
    spec = '\n\n'.join([
        '# Spec — [feature name]',
        '## Minimum Requirements Checklist (fill before Step 3 starts)',
        table(['Question', 'Answer', 'Source', 'If unanswered'], [[q, '', '', '→ Step 2 align question'] for q in CHECKLIST_Q]),
        '## Visual debt',
        '<!--\n' + table(['Codes', 'Blocks spec', 'Status', 'Mockup source'], [['SCREEN-04, SCREEN-05', '007-checkout', 'open', '']]) + '\n-->',
        '## Functional requirements (cite codes, don\'t redescribe the UI)',
        table(['FR-nnn', 'Requirement', 'Cites (SCREEN-XX-Fnn / CTL-nnn / API-nnn)'], [['FR-001', '', '']]),
        '## Acceptance cases',
        table(['Case', 'Real data (id)', 'Expected', 'Edge?'], [['AC-001', '', '', '']]),
        '## Verification',
        table(['#', 'Command', 'Expected', 'Covers'], [['V-1', '', 'exit 0', '']]),
        '## Optional Align questions',
        table(['Question', 'Answer', 'Source'], [[q, '', ''] for q in ALIGN_Q]),
    ]) + '\n'
    audit = '\n\n'.join([
        '# Mockup Audit — [feature name]',
        '## Screen inventory',
        table(['SCREEN-XX', 'DOM/node id', 'Name', 'Type (view/modal/sheet)'], [['SCREEN-01', '', '', '']]),
        '## Component inventory',
        table(['COMP-nnn', 'Name', 'Used in (SCREEN-XX list)'], [['COMP-001', '', '']]),
        '## Navigation map',
        table(['Origin', 'Action', 'Destination'], [['SCREEN-01', '', '']]),
        '## Behavior list per screen',
        table(['SCREEN-XX-Fnn', 'Screen', 'Rule (one testable sentence)'], [['SCREEN-01-F01', 'SCREEN-01', '']]),
    ]) + '\n'
    contracts = '# Contracts\n\n' + table(['API-nnn', 'Method + path', 'Request schema'], [['API-nnn', '', '']]) + '\n'
    return {'spec.md': spec, 'plan.md': '# Plan\n', 'tasks.md': None, 'mockup-audit.md': audit, 'contracts.md': contracts}


def codes_of(result, tab):
    for t in result['tabs']:
        if t['id'] == tab:
            return [it['code'] for it in t['items']]
    return []


def warn_texts(result, tab=None):
    return [w['text'] for w in result['warnings'] if tab is None or w['tab'] == tab]


def digests(result):
    return {c: I.item_digest(it) for c, it in result['items'].items()}


# ---------------------------------------------------------------------------

class TestCodeGrammar(unittest.TestCase):
    """aidd:FR-301 aidd:AC-314"""

    def test_pattern_literal_and_flags(self):
        self.assertEqual(I.CODE_RE.pattern, CODE_RE_LITERAL)
        self.assertEqual(I.GENERIC_CODE_RE.pattern, r'^(FR|AC|API|T|SCREEN|COMP|CTL|V)-\S+')
        self.assertEqual(I.PLACEHOLDER_RE.pattern, r'^[A-Z]+-[nNxX]+(?:-F[nNxX]+)?$')
        self.assertEqual(I.FIELD_ROW_RE.pattern, r'^(?:SCREEN|COMP)-\d+-F\d+$')
        for rx in (I.CODE_RE, I.GENERIC_CODE_RE, I.PLACEHOLDER_RE, I.FIELD_ROW_RE):
            self.assertTrue(rx.flags & re.ASCII, rx.pattern)

    def test_shared_candidate_list(self):
        expected = {'FR-004b': True, 'AC-01-n': True, 'V-5': True, 'D24b': True, 'FR-4.1': False,
                    'FR-٣': False, 'FR-1\n': False, 'FR-301"><img': False}
        for cand, ok in expected.items():
            self.assertEqual(I.CODE_RE.fullmatch(cand) is not None, ok, repr(cand))

    def test_real_shapes_accepted(self):
        for c in ('FR-004b', 'FR-004c', 'AC-007b', 'AC-01', 'AC-25', 'AC-01-b', 'AC-01a', 'T-1', 'D24b',
                  'D24c', 'V-1', 'V-5', 'SUMMARY', 'Q12', 'API-027', 'SCREEN-12', 'COMP-001', 'CTL-001',
                  'FR-004-x'):
            self.assertIsNotNone(I.CODE_RE.fullmatch(c), c)
        for c in ('FR-4.1', 'AC-A', 'FR-nnn', 'SCREEN-01-F01', 'fr-001', 'FR-00001', 'D24B', ''):
            self.assertIsNone(I.CODE_RE.fullmatch(c), c)

    def test_five_digit_screen_families(self):
        """F15 CTL-15001.. (175 rows), F23 CTL-23001.. (93), F19 (30): 5 digits for SCREEN/COMP/CTL/API."""
        for c in ('CTL-15001', 'CTL-15175', 'CTL-23001', 'CTL-23093', 'CTL-19030', 'SCREEN-15001',
                  'COMP-23001', 'API-15001', 'CTL-15001b', 'CTL-15001-a', 'CTL-1', 'API-027'):
            self.assertIsNotNone(I.CODE_RE.fullmatch(c), c)
        for c in ('CTL-150011', 'API-123456', 'FR-00001', 'AC-00001', 'T-00001', 'CTL-15001B',
                  'CTL-15001\n', 'CTL-1500٣', 'CTL-nnnnn', 'SCREEN-01-F01', 'ctl-15001'):
            self.assertIsNone(I.CODE_RE.fullmatch(c), c)
        for c in ('CTL-nnnnn', 'SCREEN-nn', 'SCREEN-XX', 'COMP-nnn'):
            self.assertIsNotNone(I.PLACEHOLDER_RE.fullmatch(c), c)

    def test_placeholders_anchored(self):
        for c in ('FR-nnn', 'COMP-nnn', 'SCREEN-XX', 'SCREEN-XX-Fnn', 'API-nnn', 'T-nn'):
            self.assertIsNotNone(I.PLACEHOLDER_RE.fullmatch(c), c)
        for c in ('AC-01-n', 'FR-004-x', 'FR-001', 'SCREEN-01'):
            self.assertIsNone(I.PLACEHOLDER_RE.fullmatch(c), c)
        self.assertIsNotNone(I.FIELD_ROW_RE.fullmatch('SCREEN-01-F01'))
        self.assertIsNotNone(I.FIELD_ROW_RE.fullmatch('COMP-02-F10'))
        self.assertIsNone(I.FIELD_ROW_RE.fullmatch('SCREEN-01'))

    def test_constants(self):
        self.assertEqual((I.MAX_ITEMS, I.MAX_ITEM_TEXT, I.MAX_SUMMARY, I.MAX_SUMMARY_FIELD, I.MAX_WARN_NAMES),
                         (2000, 240, 2000, 400, 8))
        self.assertEqual(I.TAB_ORDER, ('summary', 'questions', 'fr', 'ac', 'screens', 'api', 'tasks', 'verification'))
        self.assertEqual([I.TAB_LABELS[t] for t in I.TAB_ORDER],
                         ['Resumen', 'Preguntas', 'Requisitos', 'Casos', 'Pantallas', 'API', 'Tareas', 'Verificación'])


class TestHelpers(unittest.TestCase):
    def test_first_token(self):
        self.assertEqual(I._first_token('`API-027` `fe_param`'), 'API-027')
        self.assertEqual(I._first_token('**FR-001**,'), 'FR-001')
        self.assertEqual(I._first_token('SCREEN-12 (F25)'), 'SCREEN-12')
        self.assertEqual(I._first_token('C13, D18'), 'C13')
        self.assertEqual(I._first_token('V-1;'), 'V-1')
        self.assertEqual(I._first_token(''), '')
        self.assertEqual(I._first_token(None), '')

    def test_short(self):
        self.assertEqual(I._short('a  b\n c'), 'a b c')
        s = I._short('x' * 300)
        self.assertEqual(len(s), 240)
        self.assertTrue(s.endswith('...'))
        self.assertEqual(I._short('Payment one cent short', 21), 'Payment one cent s...')
        self.assertEqual(I._short(None), '')

    def test_iter_tables_each_table_separately(self):
        text = '\n'.join([
            '# Title', '## Functional requirements',
            table(['FR-nnn', 'Requirement'], [['FR-001', 'a']]), '',
            table(['Code', 'Text', 'Extra'], [['FR-002', 'b', 'c']]),
            '```', table(['FR-nnn', 'R'], [['FR-099', 'fenced']]), '```',
            '<!--', table(['FR-nnn', 'R'], [['FR-098', 'commented']]), '-->',
            '### Sub', table(['A', 'B'], [['1', '2']]),
        ])
        tabs = I._iter_tables(text)
        self.assertEqual(len(tabs), 3)
        self.assertEqual(tabs[0], ('Functional requirements', ['FR-nnn', 'Requirement'], [['FR-001', 'a']]))
        self.assertEqual(tabs[1], ('Functional requirements', ['Code', 'Text', 'Extra'], [['FR-002', 'b', 'c']]))
        self.assertEqual(tabs[2][0], 'Sub')
        self.assertEqual(I._iter_tables(None), [])
        self.assertEqual(I._iter_tables(b'| a |\n|---|\n| 1 |\n'), [('', ['a'], [['1']])])

    def test_iter_tables_blank_line_inside_table_keeps_rows(self):
        text = '## X\n| FR-nnn | R |\n|---|---|\n| FR-001 | a |\n\n| FR-002 | b |\n'
        self.assertEqual(I._iter_tables(text), [('X', ['FR-nnn', 'R'], [['FR-001', 'a'], ['FR-002', 'b']])])

    def test_escaped_pipe_and_crlf_bom(self):
        text = '\ufeff## Q\r\n| Question | Answer |\r\n|---|---|\r\n| a \\| b | c |\r\n'
        self.assertEqual(I._iter_tables(text), [('Q', ['Question', 'Answer'], [['a | b', 'c']])])


class TestF28Extraction(unittest.TestCase):
    """aidd:AC-301 aidd:AC-315 aidd:FR-311 — the real F28 shape: 175 codes, no warning."""

    @classmethod
    def setUpClass(cls):
        cls.src = f28_sources()
        cls.r = I.extract_items(cls.src)

    def test_175_codes_in_tab_order(self):
        r = self.r
        self.assertEqual([t['id'] for t in r['tabs']],
                         ['summary', 'questions', 'fr', 'ac', 'api', 'tasks', 'verification'])
        self.assertEqual([t['label'] for t in r['tabs']],
                         ['Resumen', 'Preguntas', 'Requisitos', 'Casos', 'API', 'Tareas', 'Verificación'])
        self.assertEqual(len(r['order']), 175)
        self.assertEqual(r['order'][0], 'SUMMARY')
        self.assertEqual(len(set(r['order'])), 175)
        self.assertEqual(set(r['items']), set(r['order']))
        expected = (['SUMMARY'] + ['Q%d' % n for n in range(1, 13)] + F28_D + F28_FR + F28_AC + F28_API
                    + F28_T + ['V-%d' % n for n in range(1, 6)])
        self.assertEqual(r['order'], expected)
        self.assertEqual(r['warnings'], [])

    def test_decisions_after_questions_with_source(self):
        q = codes_of(self.r, 'questions')
        self.assertEqual(q[:12], ['Q%d' % n for n in range(1, 13)])
        self.assertEqual(q[12:], F28_D)
        self.assertEqual(len(q[12:]), 40)
        d = self.r['items']['D24b']
        self.assertEqual(d['kind'], 'decision')
        self.assertEqual(d['text'], 'Decision D24b del owner')
        self.assertEqual(d['fields']['Source'], 'user — "cita D24b"')
        q8 = self.r['items']['Q8']
        self.assertEqual(q8['kind'], 'question')
        self.assertTrue(q8['text'].startswith('Which states'))
        self.assertFalse(q8['unanswered'])
        self.assertTrue(self.r['items']['Q10']['unanswered'])

    def test_item_shape(self):
        keys = {'code', 'kind', 'text', 'fields', 'edge', 'unanswered', 'mandatory', 'source', 'canon'}
        for code, it in self.r['items'].items():
            self.assertEqual(set(it), keys, code)
            self.assertLessEqual(len(it['text']), I.MAX_ITEM_TEXT)
            self.assertIn(it['source'], SOURCES)
        ac = self.r['items']['AC-007b']
        self.assertTrue(ac['edge'])
        self.assertFalse(self.r['items']['AC-001']['edge'])
        self.assertEqual(ac['fields']['Expected'], 'Resultado AC-007b')
        self.assertEqual(self.r['items']['FR-004b']['text'], 'Requisito FR-004b del hub de sync')
        self.assertEqual(self.r['items']['API-504']['source'], 'contracts.md')

    def test_verification_items_mandatory(self):
        for n in range(1, 6):
            it = self.r['items']['V-%d' % n]
            self.assertTrue(it['mandatory'])
            self.assertEqual(it['kind'], 'verification')
            self.assertEqual(it['text'], 'python -m pytest suite%d -q' % n)
            self.assertEqual(it['fields'], {'Expected': 'exit 0', 'Covers': 'FR-00%d' % n})
        self.assertTrue(self.r['items']['SUMMARY']['mandatory'])
        self.assertFalse(self.r['items']['FR-001']['mandatory'])

    def test_tasks_fields(self):
        t = self.r['items']['T-17']
        self.assertEqual(t['kind'], 'task')
        self.assertEqual(t['fields']['Minutes'], '6')
        self.assertEqual(t['fields']['Tokens'], '45k')
        self.assertIn('eDoc/supabase/migrations/0257_sync.sql', t['fields']['Target file'])

    def test_generated_summary(self):
        s = self.r['items']['SUMMARY']
        self.assertEqual(s['kind'], 'summary')
        self.assertEqual(s['text'], F28_OBJECTIVE)
        summ = I.build_summary(self.src)
        self.assertEqual(summ['source'], 'generated')
        self.assertEqual(summ['objective'], F28_OBJECTIVE)
        self.assertEqual(summ['counts'], {'fr': 30, 'ac': 17, 'edge_ac': 2, 'screens': 0, 'comps': 0, 'ctls': 0,
                                          'apis': 21, 'tasks': 49, 'questions': 12, 'unanswered': 2})
        self.assertEqual((summ['minutes'], summ['tokens_k']), (300, 1000))
        self.assertEqual(summ['cost'], '300 min / 1000k tokens')
        self.assertEqual(len(summ['open_decisions']), 2)
        self.assertEqual(s['canon'], json.dumps(summ, sort_keys=True, separators=(',', ':')))
        self.assertEqual(I.build_summary(self.src, self.r), summ)

    def test_deterministic(self):
        again = I.extract_items(f28_sources())
        self.assertEqual(json.dumps(again, sort_keys=True), json.dumps(self.r, sort_keys=True))
        self.assertEqual(digests(again), digests(self.r))

    def test_list_of_pairs_accepted(self):
        pairs = [(n, self.src.get(n)) for n in SOURCES]
        self.assertEqual(I.extract_items(pairs)['order'], self.r['order'])


class TestF23Extraction(unittest.TestCase):
    """aidd:AC-305 aidd:AC-315 — Q1..Q7 only, uncoded decision and acceptance rows reported."""

    @classmethod
    def setUpClass(cls):
        cls.src = {'spec.md': f23_spec(), 'tasks.md': f23_tasks(), 'plan.md': None,
                   'mockup-audit.md': None, 'contracts.md': None}
        cls.r = I.extract_items(cls.src)

    def test_questions_only_q1_q7(self):
        self.assertEqual(codes_of(self.r, 'questions'), ['Q%d' % n for n in range(1, 8)])
        self.assertTrue(self.r['items']['Q5']['unanswered'])
        self.assertEqual(self.r['items']['Q2']['fields']['Source'], '[Proposed — unconfirmed]')
        self.assertEqual(self.r['items']['Q1']['fields']['Answer'], 'Answer 1')
        self.assertFalse(any(c.startswith('D') for c in self.r['order']))

    def test_uncoded_rows_warned_never_invented(self):
        self.assertNotIn('ac', [t['id'] for t in self.r['tabs']])
        self.assertFalse(any(c.startswith('AC-') for c in self.r['order']))
        q = warn_texts(self.r, 'questions')
        self.assertEqual(len(q), 1)
        self.assertTrue(q[0].startswith('14 decision rows without a D code are not reviewable: '
                                        'C1, C2, C3; C5; C6; C9; C10; C11; C12; C13, D18; ...'), q[0])
        ac = warn_texts(self.r, 'ac')
        self.assertEqual(len(ac), 1)
        self.assertTrue(ac[0].startswith('29 acceptance rows without an AC code are not reviewable: '
                                         'Mixed payment sale; Payment one cent s...'), ac[0])

    def test_fr_bold_stripped_and_counts(self):
        self.assertEqual(len(codes_of(self.r, 'fr')), 32)
        self.assertEqual(self.r['items']['FR-001']['text'], 'Requirement 1. text')
        s = I.build_summary(self.src)
        self.assertEqual(s['counts']['questions'], 7)
        self.assertEqual(s['counts']['unanswered'], 1)
        self.assertEqual(s['counts']['ac'], 0)
        self.assertEqual(s['open_decisions'], [CHECKLIST_Q[4]])

    def test_optional_align_two_rows_give_q8_q9(self):
        src = dict(self.src, **{'spec.md': f23_spec(align_rows=[['Which states?', 'empty', 'repo — a.py:1'],
                                                                 ['Who may see this?', '', '']])})
        r = I.extract_items(src)
        self.assertEqual(codes_of(r, 'questions'), ['Q%d' % n for n in range(1, 10)])
        self.assertEqual(r['items']['Q8']['text'], 'Which states?')
        self.assertTrue(r['items']['Q9']['unanswered'])


class TestCodeShapes(unittest.TestCase):
    """aidd:AC-314 — F13/F15 shapes, two FR tables, flow table repeats, completeness."""

    def spec(self):
        return '\n\n'.join([
            '# Spec — F15 · eDoc Backoffice Web',
            '## Functional requirements',
            table(['FR-nnn', 'Requirement', 'Cites (SCREEN / API-nnn / table)'],
                  [['FR-001', 'Vite project', 'x'], ['FR-002', 'tokens.css', 'y'], ['FR-4.1', 'dotted shape', 'z']]),
            'Second table of the same section:',
            table(['Code', 'Requirement'], [['FR-028', 'second table row'], ['FR-004-x', 'hyphen suffix']]),
            '## Acceptance cases',
            table(['Case', 'Real data (id)', 'Expected', 'Edge?'],
                  [['AC-01', 'Empty database', 'ok', 'no'], ['AC-01-b', '0102 applied twice', 'ok', 'yes'],
                   ['AC-25', 'last F13 case', 'ok', 'no'], ['AC-01a', 'wrong password', 'message', 'yes'],
                   ['AC-01-n', 'n-suffixed real code', 'ok', 'no'], ['AC-nnn', '', '', '']]),
        ]) + '\n'

    def audit(self):
        return '\n\n'.join([
            '# Mockup Audit — F15',
            '## Screen inventory',
            table(['SCREEN-XX', 'DOM/node id', 'Name', 'Type (view/modal/sheet)'],
                  [['SCREEN-01', '`prototype/SCREEN-01.html`', 'Inicio de sesión', 'view'],
                   ['SCREEN-02', '`prototype/SCREEN-02.html`', 'Panel operativo', 'view'],
                   ['SCREEN-12 (F25)', 'x', 'Auditoria', 'view']]),
            '## Control inventory',
            table(['CTL-nnn', 'Screen or COMP-nnn', 'Visible text', 'id', 'Action/handler', 'Destination'],
                  [['CTL-001', 'SCREEN-01', 'Ingresar', 'btn', 'submit', 'SCREEN-02']]),
            '## Navigation map',
            table(['Origin', 'Action', 'Destination', 'Data passed'],
                  [['SCREEN-01', 'CTL-001 sign in succeeds', 'SCREEN-02', 'session'],
                   ['SCREEN-01', 'CTL-002', 'SCREEN-01 recover view', 'none'],
                   ['SCREEN-02', 'menu', 'SCREEN-01', 'none']]),
            '## Behavior list per screen',
            table(['SCREEN-XX-Fnn', 'Screen', 'Rule (one testable sentence)'],
                  [['SCREEN-01-F01', 'SCREEN-01', 'Every sign-in failure shows one message'],
                   ['SCREEN-01-F02', 'SCREEN-01', 'Submit disabled while pending']]),
        ]) + '\n'

    def contracts(self):
        return '# Contracts\n\n' + table(['API-nnn', 'Owner spec', 'Used by'],
                                         [['`API-027` `fe_param`', 'F12', 'all screens (thresholds)'],
                                          ['API-147', 'F15', 'admin']]) + '\n'

    def tasks(self):
        return '# Tasks\n\n' + table(['Task', 'Codes satisfied', 'Target file'],
                                     [['T-1', 'FR-001', '`eDoc/web/package.json`']]) + \
            '\n\n## Per-task detail\n\n### T-1\n- Agent min: 5\n- Tokens (est): 30k\n\n' \
            '### T-2\n- Objective: block only task\n- Agent min: 7\n- Tokens (est): 20k\n- Target file: `a/b.py`\n'

    def setUp(self):
        self.r = I.extract_items({'spec.md': self.spec(), 'mockup-audit.md': self.audit(),
                                  'contracts.md': self.contracts(), 'tasks.md': self.tasks(), 'plan.md': None})

    def test_every_coded_row_once(self):
        self.assertEqual(codes_of(self.r, 'fr'), ['FR-001', 'FR-002', 'FR-028', 'FR-004-x'])
        self.assertEqual(codes_of(self.r, 'ac'), ['AC-01', 'AC-01-b', 'AC-25', 'AC-01a', 'AC-01-n'])
        self.assertEqual(codes_of(self.r, 'screens'), ['SCREEN-01', 'SCREEN-02', 'SCREEN-12', 'CTL-001'])
        self.assertEqual(codes_of(self.r, 'api'), ['API-027', 'API-147'])
        self.assertEqual(codes_of(self.r, 'tasks'), ['T-1', 'T-2'])
        self.assertEqual(self.r['items']['API-027']['text'], 'F12')
        self.assertIn('fe_param', self.r['items']['API-027']['canon'].replace('feparam', 'fe_param'))
        self.assertEqual(self.r['items']['SCREEN-01']['text'], 'Inicio de sesión')
        self.assertEqual(self.r['items']['CTL-001']['fields']['Destination'], 'SCREEN-02')
        self.assertEqual(self.r['items']['T-1']['fields'], {'Target file': 'eDoc/web/package.json',
                                                            'Minutes': '5', 'Tokens': '30k'})
        t2 = self.r['items']['T-2']
        self.assertEqual(t2['text'], 'block only task')
        self.assertEqual(t2['fields'], {'Target file': 'a/b.py', 'Minutes': '7', 'Tokens': '20k'})

    def test_repeats_one_counted_line(self):
        w = [t for t in warn_texts(self.r, 'screens') if 'repeated' in t]
        self.assertEqual(w, ['3 repeated codes skipped (first row wins): SCREEN-01, SCREEN-02'])

    def test_completeness_names_skipped_code(self):
        self.assertIn('FR: 1 coded row skipped: FR-4.1', warn_texts(self.r, 'fr'))
        allw = ' '.join(warn_texts(self.r))
        for absent in ('SCREEN-01-F01', 'AC-nnn', 'SCREEN-XX', 'FR-nnn'):
            self.assertNotIn(absent, allw)

    def test_completeness_independent_of_extractor(self):
        items = I.extract_items({'spec.md': self.spec()})['items']
        broken = {c: it for c, it in items.items() if c != 'FR-002'}
        w = I._completeness({'spec.md': self.spec()}, broken)
        self.assertIn({'tab': 'fr', 'text': 'FR: 2 coded rows skipped: FR-002, FR-4.1'}, w)
        self.assertEqual(I._completeness(None, None), [])

    def test_unicode_digit_and_newline_never_codes(self):
        spec = '## Functional requirements\n\n' + table(['FR-nnn', 'Requirement'],
                                                        [['FR-٣', 'arabic digit'], ['FR-001', 'ok']]) + '\n'
        r = I.extract_items({'spec.md': spec})
        self.assertEqual(codes_of(r, 'fr'), ['FR-001'])
        self.assertIn('FR: 1 coded row skipped: FR-٣', warn_texts(r, 'fr'))

    def test_hostile_code_cell_is_not_an_item(self):
        spec = '## Functional requirements\n\n' + table(['FR-nnn', 'Requirement'],
                                                        [['FR-301"><img src=x onerror=1>', 'x'],
                                                         ['FR-302', '<script>alert(1)</script>']]) + '\n'
        r = I.extract_items({'spec.md': spec})
        self.assertEqual(codes_of(r, 'fr'), ['FR-302'])
        self.assertEqual(r['items']['FR-302']['text'], '<script>alert(1)</script>')
        self.assertTrue(any(t.startswith('FR: 1 coded row skipped: FR-301"') for t in warn_texts(r, 'fr')))

    def test_warning_names_capped(self):
        rows = [['FR-%d.1' % n, 'x'] for n in range(1, 12)]
        r = I.extract_items({'spec.md': '## FR\n\n' + table(['FR-nnn', 'R'], rows) + '\n'})
        w = [t for t in warn_texts(r, 'fr') if 'coded rows skipped' in t][0]
        self.assertTrue(w.startswith('FR: 11 coded rows skipped: FR-1.1, FR-2.1'), w)
        self.assertEqual(w.count(','), 8)
        self.assertTrue(w.endswith(', ...'))


def five_digit_audit(prefix, count, spec_name):
    """Mockup audit with per-spec 5-digit control codes (CTL-<nn>001..), placeholder rows included."""
    ctl = ['CTL-%s%03d' % (prefix, n) for n in range(1, count + 1)]
    return ctl, '\n\n'.join([
        '# Mockup Audit — %s' % spec_name,
        '## Screen inventory',
        table(['SCREEN-XX', 'DOM/node id', 'Name', 'Type (view/modal/sheet)'],
              [['SCREEN-%s' % prefix, 'x', 'Pantalla %s' % prefix, 'view'], ['SCREEN-nn', '', '', '']]),
        '## Control inventory',
        table(['CTL-nnn', 'Screen or COMP-nnn', 'Visible text', 'id', 'Action/handler', 'Destination'],
              [['CTL-nnnnn', '', '', '', '', '']]
              + [[c, 'SCREEN-%s' % prefix, 'Control %s' % c, 'id', 'click', 'SCREEN-%s' % prefix] for c in ctl]),
        '## Behavior list per screen',
        table(['SCREEN-XX-Fnn', 'Screen', 'Rule (one testable sentence)'],
              [['SCREEN-%s-F01' % prefix, 'SCREEN-%s' % prefix, 'rule']]),
    ]) + '\n'


class TestFiveDigitControls(unittest.TestCase):
    """F15 (CTL-15001..15175), F23 (CTL-23001..23093), F19 (CTL-19001..19030) reach the Pantallas tab."""

    def test_real_shaped_counts_all_reviewable(self):
        for prefix, count, name in (('15', 175, 'F15'), ('23', 93, 'F23-eDoc-POS'), ('19', 30, 'F19')):
            ctl, audit = five_digit_audit(prefix, count, name)
            r = I.extract_items({'spec.md': None, 'mockup-audit.md': audit})
            self.assertEqual(codes_of(r, 'screens'), ['SCREEN-%s' % prefix] + ctl, name)
            self.assertEqual(r['items'][ctl[-1]]['kind'], 'ctl')
            self.assertEqual(r['items'][ctl[-1]]['text'], 'Control %s' % ctl[-1])
            self.assertEqual(r['items'][ctl[0]]['fields']['Destination'], 'SCREEN-%s' % prefix)
            self.assertFalse(any('skipped' in t for t in warn_texts(r)), warn_texts(r))
            allw = ' '.join(warn_texts(r))
            for absent in ('CTL-nnnnn', 'SCREEN-nn', 'SCREEN-%s-F01' % prefix):
                self.assertNotIn(absent, allw)
                self.assertNotIn(absent, r['items'])
            self.assertEqual(I.build_summary({'mockup-audit.md': audit})['counts']['ctls'], count)
        self.assertIn('CTL-23093', I.extract_items({'mockup-audit.md': five_digit_audit('23', 93, 'F23')[1]})['items'])

    def test_six_digits_still_skipped_and_named(self):
        _, audit = five_digit_audit('15', 2, 'F15')
        audit = audit.replace('| CTL-15002 |', '| CTL-150002 |')
        r = I.extract_items({'mockup-audit.md': audit})
        self.assertEqual(codes_of(r, 'screens'), ['SCREEN-15', 'CTL-15001'])
        self.assertIn('CTL: 1 coded row skipped: CTL-150002', warn_texts(r, 'screens'))


class TestQuestions(unittest.TestCase):
    def test_two_optional_align_tables_no_header_rows(self):
        spec = '\n\n'.join([
            '## Minimum Requirements Checklist',
            table(['Question', 'Answer', 'Source', 'If unanswered'], [['Which module?', 'Core', 'user — "core del hub"', '']]),
            '## Optional Align questions',
            table(['Question', 'Answer', 'Source'], [['Which states?', 'empty', 'repo — a.py:1']]),
            'More questions:',
            table(['Question', 'Answer', 'Source'], [['Who may see this?', 'owner', 'repo — b.py:2'],
                                                      ['Q9 Explicit code?', 'yes', 'repo — c.py:3']]),
        ]) + '\n'
        qs = I._questions(spec)
        self.assertEqual([q['code'] for q in qs], ['Q1', 'Q2', 'Q3', 'Q9'])
        self.assertEqual([q['question'] for q in qs],
                         ['Which module?', 'Which states?', 'Who may see this?', 'Explicit code?'])
        for q in qs:
            self.assertNotIn(q['question'].lower(), ('question', '---'))
            self.assertEqual(set(q), {'code', 'kind', 'question', 'answer', 'source', 'unanswered', 'canon'})

    def test_never_raises(self):
        self.assertEqual(I._questions(None), [])
        self.assertEqual(I._questions(''), [])
        self.assertEqual(I._questions(12), [])

    def test_fallback_without_aidd_rules(self):
        with mock.patch.object(I, '_rules', side_effect=ImportError('no aidd_rules')):
            r = I.extract_items(f28_sources())
            self.assertEqual(codes_of(r, 'questions')[:12], ['Q%d' % n for n in range(1, 13)])
            self.assertEqual(len(r['order']), 175)
            self.assertEqual(r['items']['T-17']['fields'].get('Minutes'), None)
            s = I.build_summary(f28_sources())
            self.assertEqual((s['minutes'], s['tokens_k']), (None, None))

    def test_fallback_without_check_spec(self):
        with mock.patch.object(I, '_check_spec', return_value=None):
            self.assertEqual(I.extract_items(f28_sources())['order'], I.extract_items(f28_sources())['order'])
            self.assertEqual(len(I.extract_items(f28_sources())['order']), 175)


class TestTemplateAndEdges(unittest.TestCase):
    """aidd:AC-302 aidd:AC-303 aidd:AC-324"""

    def test_template_only(self):
        r = I.extract_items(template_sources())
        ids = [t['id'] for t in r['tabs']]
        self.assertEqual(ids, ['summary', 'questions'])
        self.assertEqual(codes_of(r, 'questions'), ['Q%d' % n for n in range(1, 13)])
        for t in warn_texts(r):
            self.assertNotIn('skipped', t)
        self.assertNotIn('V-1', r['order'])
        summ = I.build_summary(template_sources())
        self.assertEqual(summ['counts']['fr'], 0)
        self.assertEqual(summ['counts']['screens'], 0)
        self.assertEqual(summ['objective'], '')
        self.assertEqual(r['items']['SUMMARY']['text'], 'n/a')
        self.assertFalse(any(o.startswith('Visual debt') for o in summ['open_decisions']))

    def test_source_with_content_and_zero_items_warns_on_resumen(self):
        r = I.extract_items({'spec.md': '# Spec\n\nprose only\n', 'contracts.md': '# Contracts\n\nnothing coded\n'})
        texts = warn_texts(r, 'summary')
        self.assertIn('spec.md: the file has content but no reviewable item was found (0 items)', texts)
        self.assertIn('contracts.md: the file has content but no reviewable item was found (0 items)', texts)
        self.assertEqual(r['order'], ['SUMMARY'])
        self.assertEqual([t['id'] for t in r['tabs']], ['summary'])

    def test_non_standard_header_rows_still_extracted(self):
        spec = '## Requisitos\n\n' + table(['Código', 'Descripción'], [['FR-001', 'uno'], ['FR-002', 'dos']]) + '\n'
        r = I.extract_items({'spec.md': spec})
        self.assertEqual(codes_of(r, 'fr'), ['FR-001', 'FR-002'])
        self.assertEqual(r['items']['FR-002']['text'], 'dos')

    def test_empty_and_garbage_sources(self):
        for src in (None, {}, [], {'spec.md': None}, {'spec.md': b'\xff\xfe'}, {'spec.md': 5}, 'junk'):
            r = I.extract_items(src)
            self.assertEqual(r['order'], ['SUMMARY'])
            self.assertEqual(set(r), {'tabs', 'items', 'order', 'warnings'})

    def test_2001_rows_never_refused(self):
        rows = [['FR-%d' % n, 'requirement %d' % n] for n in range(1, 2002)]
        r = I.extract_items({'spec.md': '## Functional requirements\n\n' + table(['FR-nnn', 'Requirement'], rows) + '\n'})
        self.assertEqual(len(r['order']), 2002)
        self.assertGreater(len(r['order']), I.MAX_ITEMS)

    def test_long_cell_cut_but_canon_full(self):
        long = 'a' * 300 + ' END'
        spec = '## FR\n\n' + table(['FR-nnn', 'Requirement'], [['FR-001', long]]) + '\n'
        it = I.extract_items({'spec.md': spec})['items']['FR-001']
        self.assertEqual(len(it['text']), 240)
        self.assertTrue(it['text'].endswith('...'))
        self.assertIn('END', it['canon'])


class TestSummary(unittest.TestCase):
    """aidd:AC-304 aidd:FR-302"""

    def test_written_summary_capped(self):
        summary = ('- Objective: Sell at the counter with mixed payment.\n'
                   '- **Scope:** POS screens, shifts\n  and returns.\n'
                   '- Cost: 120 min / 500k tokens\n'
                   '- Risks: ' + 'r' * 3000 + '\n'
                   '- Open decisions: O-1 printing mode\n')
        src = {'spec.md': f23_spec(summary=summary), 'tasks.md': f23_tasks()}
        s = I.build_summary(src)
        self.assertEqual(s['source'], 'spec.md#executive-summary')
        self.assertEqual(s['objective'], 'Sell at the counter with mixed payment.')
        self.assertEqual(s['scope'], 'POS screens, shifts and returns.')
        self.assertEqual(s['cost'], '120 min / 500k tokens')
        self.assertEqual(len(s['risks']), I.MAX_SUMMARY_FIELD)
        self.assertTrue(s['risks'].endswith('...'))
        self.assertEqual(s['open_decisions'], ['O-1 printing mode'])
        self.assertEqual((s['minutes'], s['tokens_k']), (50, 535))
        self.assertEqual(s['counts']['fr'], 32)
        total = sum(len(s[k]) for k in ('objective', 'scope', 'cost', 'risks')) + sum(map(len, s['open_decisions']))
        self.assertLessEqual(total, I.MAX_SUMMARY)
        self.assertEqual(json.dumps(I.build_summary(src)), json.dumps(s))

    def test_spanish_labels(self):
        sec = I.exec_summary_section('## Resumen ejecutivo\n\n- Objetivo: vender\n- Alcance: POS\n'
                                     '- Costo: 10 min\n- Riesgos: ninguno\n- Decisiones abiertas: O-2\n')
        self.assertEqual(sec, {'objective': 'vender', 'scope': 'POS', 'cost': '10 min', 'risks': 'ninguno',
                               'open_decisions': ['O-2']})

    def test_absent_summary_on_002_is_generated(self):
        spec = f23_spec().replace('F23 · eDoc POS', '002 — AIDD Hard Rules')
        s = I.build_summary({'spec.md': spec, 'tasks.md': None})
        self.assertEqual(s['source'], 'generated')
        self.assertEqual(s['objective'], 'Answer 6')
        self.assertEqual((s['minutes'], s['tokens_k']), (None, None))
        self.assertEqual(s['cost'], '')
        self.assertIsNone(I.exec_summary_section(spec))

    def test_empty_section_is_generated(self):
        spec = f23_spec(summary='- Objective:\n- Scope:\n')
        self.assertIsNone(I.exec_summary_section(spec))
        s = I.build_summary({'spec.md': spec, 'tasks.md': f23_tasks()})
        self.assertEqual(s['source'], 'generated')
        self.assertEqual(s['objective'], 'Answer 6')
        self.assertEqual(s['cost'], '50 min / 535k tokens')

    def test_shape_and_never_raises(self):
        keys = {'objective', 'scope', 'cost', 'risks', 'open_decisions', 'counts', 'minutes', 'tokens_k', 'source'}
        for src in (None, {}, {'spec.md': 'x'}, f28_sources()):
            s = I.build_summary(src)
            self.assertEqual(set(s), keys)
            self.assertEqual(set(s['counts']), {'fr', 'ac', 'edge_ac', 'screens', 'comps', 'ctls', 'apis',
                                                'tasks', 'questions', 'unanswered'})
        self.assertIsNone(I.exec_summary_section(None))

    def test_section_ends_at_next_heading(self):
        sec = I.exec_summary_section('## Executive summary\n- Objective: a\n## Scope\n- Scope: not this one\n')
        self.assertEqual(sec['objective'], 'a')
        self.assertEqual(sec['scope'], '')


class TestDigests(unittest.TestCase):
    """aidd:FR-312 aidd:AC-325"""

    def test_formula_and_determinism(self):
        import hashlib
        it = {'kind': 'fr', 'code': 'FR-001', 'canon': 'FR-001 | text'}
        exp = hashlib.sha1('fr\x1fFR-001\x1fFR-001 | text'.encode()).hexdigest()[:8]
        self.assertEqual(I.item_digest(it), exp)
        self.assertRegex(I.item_digest(it), r'^[0-9a-f]{8}$')
        self.assertRegex(I.item_digest(None), r'^[0-9a-f]{8}$')
        self.assertEqual(digests(I.extract_items(f28_sources())), digests(I.extract_items(f28_sources())))

    def test_whitespace_only_change_same_digest(self):
        a = I.extract_items({'spec.md': '## FR\n\n| FR-nnn | R |\n|---|---|\n| FR-001 | the `hub` text |\n'})
        b = I.extract_items({'spec.md': '## FR\n\n| FR-nnn | R |\n|---|---|\n|  FR-001  |  the   hub\ttext  |\n'})
        self.assertEqual(I.item_digest(a['items']['FR-001']), I.item_digest(b['items']['FR-001']))

    def test_change_after_char_240_changes_digest(self):
        base = 'x' * 260
        a = I.extract_items({'spec.md': '## FR\n\n' + table(['FR-nnn', 'R'], [['FR-001', base + 'A']]) + '\n'})
        b = I.extract_items({'spec.md': '## FR\n\n' + table(['FR-nnn', 'R'], [['FR-001', base + 'B']]) + '\n'})
        self.assertEqual(a['items']['FR-001']['text'], b['items']['FR-001']['text'])
        self.assertNotEqual(I.item_digest(a['items']['FR-001']), I.item_digest(b['items']['FR-001']))

    def test_inserted_checklist_row_shifts_q4_on(self):
        old = I.extract_items(f28_sources())
        new = I.extract_items(f28_sources(insert_before_q4='Inserted question?'))
        od, nd = digests(old), digests(new)
        prev_lines = {c: {'approved': True, 'comment': '', 'digest': d} for c, d in od.items()}
        prior, carry = I.carry_decision(prev_lines, od, nd, new['order'])
        self.assertEqual(carry['pending'], ['SUMMARY'] + ['Q%d' % n for n in range(4, 14)])
        for c in ('Q1', 'Q2', 'Q3', 'FR-001', 'T-49', 'V-5', 'D24b'):
            self.assertIn(c, prior)


class TestCarryDecision(unittest.TestCase):
    """aidd:FR-312 aidd:AC-320 aidd:AC-321 aidd:AC-322"""

    @classmethod
    def setUpClass(cls):
        cls.base = I.extract_items(f28_sources())
        cls.bd = digests(cls.base)

    def lines(self, ds, comment_on=('FR-001',)):
        return {c: {'approved': True, 'comment': 'nota' if c in comment_on else '', 'digest': d} for c, d in ds.items()}

    def test_ac320_only_edited_task_pending(self):
        new = I.extract_items(f28_sources(t17_text='FR-012, D30, texto editado'))
        nd = digests(new)
        prior, carry = I.carry_decision(self.lines(self.bd), self.bd, nd, new['order'])
        self.assertEqual(carry, {'carried': 174, 'total': 175, 'pending': ['T-17']})
        self.assertEqual(prior['FR-001'], {'approved': True, 'comment': 'nota'})
        self.assertNotIn('T-17', prior)

    def test_ac321_no_change_all_carried(self):
        prior, carry = I.carry_decision(self.lines(self.bd), self.bd, self.bd, self.base['order'])
        self.assertEqual(carry, {'carried': 175, 'total': 175, 'pending': []})
        risks = I.extract_items(f28_sources(risks='Otra prosa de riesgos.'))
        self.assertEqual(digests(risks), self.bd)

    def test_ac322_removed_then_readded_is_pending(self):
        removed = I.extract_items(f28_sources(drop_fr='FR-012'))
        rd = digests(removed)
        self.assertEqual(len(removed['order']), 174)
        prior, carry = I.carry_decision(self.lines(self.bd), self.bd, rd, removed['order'])
        self.assertEqual(carry['pending'], ['SUMMARY'])
        self.assertEqual(carry['carried'], 173)
        readded = I.extract_items(f28_sources())
        prior2, carry2 = I.carry_decision(self.lines(self.bd), rd, digests(readded), readded['order'])
        self.assertEqual(carry2['pending'], ['SUMMARY', 'FR-012'])
        self.assertEqual(carry2['carried'], 173)

    def test_any_missing_digest_not_carried(self):
        order = ['FR-001', 'FR-002', 'FR-003', 'FR-004']
        new = {'FR-001': 'aaaaaaaa', 'FR-002': 'bbbbbbbb', 'FR-003': 'cccccccc', 'FR-004': 'dddddddd'}
        lines = {'FR-001': {'approved': True, 'comment': 'c1', 'digest': 'aaaaaaaa'},
                 'FR-002': {'approved': True, 'comment': '', 'digest': None},
                 'FR-003': {'approved': False, 'comment': 'x', 'digest': 'cccccccc'},
                 'FR-004': {'approved': True, 'comment': '', 'digest': 'dddddddd'}}
        blob = {'FR-001': 'aaaaaaaa', 'FR-002': 'bbbbbbbb', 'FR-003': 'cccccccc'}
        prior, carry = I.carry_decision(lines, blob, new, order)
        self.assertEqual(prior, {'FR-001': {'approved': True, 'comment': 'c1'},
                                 'FR-003': {'approved': False, 'comment': 'x'}})
        self.assertEqual(carry, {'carried': 2, 'total': 4, 'pending': ['FR-002', 'FR-004']})

    def test_malformed_entries_and_errors(self):
        order = ['FR-001', 'FR-002', 'FR-003']
        d = {'FR-001': 'aaaaaaaa', 'FR-002': 'bbbbbbbb', 'FR-003': 'cccccccc'}
        lines = {'FR-001': 'not a dict', 'FR-002': {'approved': True, 'digest': 'bbbbbbbb'},
                 'FR-003': {'approved': True, 'comment': '', 'digest': 'cccccccc'}}
        prior, carry = I.carry_decision(lines, d, d, order)
        self.assertEqual(list(prior), ['FR-003'])
        self.assertEqual(carry['pending'], ['FR-001', 'FR-002'])
        self.assertEqual(I.carry_decision(None, None, None, order),
                         ({}, {'carried': 0, 'total': 3, 'pending': order}))
        self.assertEqual(I.carry_decision({}, {}, {}, None), ({}, {'carried': 0, 'total': 0, 'pending': []}))
        self.assertEqual(I.carry_decision({}, {}, {}, 5), ({}, {'carried': 0, 'total': 0, 'pending': []}))


class TestTasksFacts(unittest.TestCase):
    """aidd:FR-313"""

    def test_f28_target_files_and_waves(self):
        files = I.target_files(f28_tasks())
        self.assertEqual(len(files), 98)
        self.assertEqual(files[:2], ['eDoc/supabase/migrations/0241_sync.sql', 'eDoc/supabase/tests/0241.test.sql'])
        self.assertEqual(I.wave_count(f28_tasks()), 10)

    def test_f23_split_on_semicolon(self):
        self.assertEqual(I.target_files(f23_tasks()), [
            'eDoc/supabase/migrations/0200_pos_pay_methods.sql',
            'eDoc/supabase/migrations/0201_pos_terminals_shifts.sql',
            'eDoc/supabase/migrations/0202_pos_document_columns.sql',
            'edoc-web/src/pos/PosScreen.tsx', 'edoc-web/src/pos/PosScreen.test.tsx'])
        self.assertEqual(I.wave_count(f23_tasks()), 2)

    def test_002_without_tasks(self):
        for t in (None, '', '# Tasks\n\nno table\n', '| Task | Codes |\n|---|---|\n| T-01 | FR-001 |\n'):
            self.assertEqual(I.target_files(t), [])
            self.assertEqual(I.wave_count(t), 0)

    def test_comma_and_dedupe(self):
        t = table(['Task', 'Target file'], [['T-01', '`a.py`, `b.py`'], ['T-02', 'a.py + c.py'], ['T-nn', 'tpl.py'], ['T-03', '-']])
        self.assertEqual(I.target_files(t), ['a.py', 'b.py', 'c.py'])


class TestPurity(unittest.TestCase):
    """plan.md module split: no file IO, no print, never imports aidd_review / aidd_review_state."""

    def test_source_has_no_io_and_no_forbidden_imports(self):
        import ast
        src = (SCRIPTS_DIR / 'aidd_review_items.py').read_text(encoding='utf-8')
        tree = ast.parse(src)
        imported, called = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or '')
            elif isinstance(node, ast.Call):
                f = node.func
                called.add(f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else '')
        self.assertFalse(imported & {'aidd_review', 'aidd_review_state', 'os', 'io', 'shutil', 'subprocess'},
                         sorted(imported))
        self.assertFalse(called & {'open', 'print', 'read_text', 'write_text', 'read_bytes', 'write_bytes',
                                   'unlink', 'mkdir'}, sorted(called & {'open', 'print'}))
        for code in ('aidd:FR-301', 'aidd:FR-302', 'aidd:FR-311', 'aidd:FR-312', 'aidd:FR-313'):
            self.assertIn(code, src)


REAL_ROOT = Path(os.environ.get('AIDD_B1SYCLINK_SPECS', r'D:\Fuentes\b1SycLink\specs'))


def load_real(spec_dir):
    out = {}
    for n in SOURCES:
        p = Path(spec_dir) / n
        out[n] = p.read_text(encoding='utf-8', errors='replace') if p.is_file() else None
    return out


@unittest.skipUnless((REAL_ROOT / 'F28-DB-Unification-Sync' / 'spec.md').is_file(), 'b1SycLink checkout not present')
class TestRealFiles(unittest.TestCase):
    """The real b1SycLink files (only the five sources are read)."""

    def test_f28_175_codes_absolute_and_relative(self):  # F28 now has 177 codes
        d = REAL_ROOT / 'F28-DB-Unification-Sync'
        r = I.extract_items(load_real(d.resolve()))
        self.assertEqual(len(r['order']), 177)
        self.assertEqual(r['warnings'], [])
        self.assertEqual([t['id'] for t in r['tabs']],
                         ['summary', 'questions', 'fr', 'ac', 'api', 'tasks', 'verification'])
        for c in ('FR-004b', 'FR-004c', 'AC-007b', 'D24b', 'D24c', 'V-5', 'Q12'):
            self.assertIn(c, r['items'])
        try:
            rel = os.path.relpath(d)
        except ValueError:      # another drive on Windows: no relative path exists
            rel = None
        if rel is not None:
            self.assertEqual(I.extract_items(load_real(rel))['order'], r['order'])
        self.assertGreater(len(I.target_files(load_real(d)['tasks.md'])), 0)
        self.assertEqual(I.wave_count(load_real(d)['tasks.md']), 10)

    def test_f23_questions_and_warnings(self):
        r = I.extract_items(load_real(REAL_ROOT / 'F23-eDoc-POS'))
        self.assertEqual(codes_of(r, 'questions'), ['Q%d' % n for n in range(1, 8)])
        self.assertNotIn('ac', [t['id'] for t in r['tabs']])
        self.assertTrue(any(t.startswith('14 decision rows without a D code') for t in warn_texts(r, 'questions')))
        self.assertTrue(any(t.startswith('29 acceptance rows without an AC code') for t in warn_texts(r, 'ac')))

    def test_f13_f15_shapes(self):
        f13 = REAL_ROOT / 'F13-eDoc-Emission-Engine'
        if f13.is_dir():
            r = I.extract_items(load_real(f13))
            for c in ('AC-01', 'AC-25', 'AC-01-b'):
                self.assertIn(c, r['items'])
        f15 = REAL_ROOT / 'F15-eDoc-Backoffice-Web'
        if f15.is_dir():
            r = I.extract_items(load_real(f15))
            self.assertIn('AC-01a', r['items'])
            self.assertIn('API-027', r['items'])
            self.assertLessEqual(len(r['order']), I.MAX_ITEMS)
            self.assertTrue(any('repeated' in t for t in warn_texts(r, 'screens')))


if __name__ == '__main__':
    unittest.main()
