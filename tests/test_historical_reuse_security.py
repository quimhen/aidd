"""4b historical boundaries; temp evidence is synthetic, never a historical receipt."""
import contextlib
import copy
import hashlib
import io
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'scripts'))
import aidd_amendment_verify as amendment
import aidd_round as rnd
import aidd_status as status
import test_amendment_truncated_command as truncated_fixture
from test_verify_round import PY
from test_verify_round_reuse import ReuseBase

OFFLINE = 'contract:offline;vars=none;packages=none'


class HistoricalSecurity(ReuseBase):
    def fixture(self, cmd=None):
        self.cmd = cmd or f'{PY} ok.py'
        self.directory = self.root / 'specs' / 'A'
        self.directory.mkdir(parents=True, exist_ok=True)
        self.text = ('# A\n\n## Verification\nScope: src/a.py\n'
                     '| # | Command | Expected | Covers | Inputs | Reuse | Environment |\n'
                     '|---|---|---|---|---|---|---|\n'
                     f'| V-1 | `{self.cmd}` | exit 0 | FR-1 | ok.py,src/a.py | hermetic | {OFFLINE} |\n')
        (self.directory / 'spec.md').write_text(self.text, encoding='utf-8')
        (self.directory / 'tasks.md').write_text('', encoding='utf-8')
        self.row = status.rules.parse_verification(self.text)[0]
        self.data = (f'# {self.cmd} | exit 0 | 2026-11-14T14:12:21\n'
                     'ran 3 tests ok, all assertions passed; ready\n').encode()
        p = self.directory / 'evidence' / 'source.txt'
        p.parent.mkdir(exist_ok=True)
        p.write_bytes(self.data)
        self.result0 = {'n': 'V-1', 'cmd': self.cmd, 'expected': 'exit 0', 'ok': True,
                        'exit': 0, 'evidence': 'evidence/source.txt',
                        'sha1': hashlib.sha1(self.data).hexdigest(), 'secs': .1,
                        'input_globs': self.row['inputs'], 'reuse_policy': 'hermetic',
                        'input_algorithm': status.ev.EVIDENCE_ALGORITHM,
                        'input_fp': status.rules.row_input_fingerprint(self.root, self.row['inputs']),
                        'env_id': '', 'environment_declaration': OFFLINE,
                        'environment_id': status._contract_environment_id(self.cmd, OFFLINE)}
        self.state = status.ev.code_state(self.root, scope=['src/a.py'])
        self.prior = {'stable': True, 'ok': True, 'results': [self.result0], 'started': 1794665541,
                      'code_scope': ['src/a.py'], 'code_generated': [],
                      'code_algorithm': status.ev.EVIDENCE_ALGORITHM,
                      'code_fp_end': status.ev.fingerprint_of(self.state, ['src/a.py']),
                      'verify_hash': status.rules.verification_hash(self.text)}
        self.parts = {'containers': {}, 'identity': {}, 'vars': {}}
        self.specinfo = {'name': 'A', 'dir': self.directory, 'scope': ['src/a.py']}

    def planned(self, route):
        with patch.object(status.ev, 'latest_verify_run', return_value=self.prior):
            if route == 'amendment':
                item = amendment.plan(status, self.root, self.directory, [self.row],
                                      self.state, self.parts, [], ['src/a.py'], '01')[0]
                return item['entry'] if item['action'] == 'REUSED' else None
            return rnd.reuse_plan(status, self.root, self.specinfo, [self.row],
                                  self.state, self.parts)[0].get('V-1')

    def test_03_real_offline_validator_accepts_both_planners(self):
        self.fixture()
        self.assertTrue(self.result0['environment_id'])
        for route in ('round', 'amendment'):
            with self.subTest(route=route):
                self.assertIsNotNone(self.planned(route))
        self.assertEqual((self.runs, self.events), ([], []))

    def test_04_external_and_unsupported_commands_never_reuse_or_execute(self):
        commands = ('python eDoc/tools/db_verify.py --tap', 'docker exec stable-db psql -c SELECT',
                    'node tests.js', 'unknown tests', f'{PY} -m unittest', f'{PY} ok.py && echo done')
        for cmd in commands:
            for route in ('round', 'amendment'):
                with self.subTest(command=cmd, route=route):
                    self.fixture(cmd)
                    self.parts['containers']['stable-db'] = 'stable-container-and-start'
                    self.result0['env_id'] = rnd.row_env_id(self.parts, cmd)
                    self.assertIsNone(status._contract_environment_id(cmd, OFFLINE))
                    self.assertIsNone(self.planned(route))
        self.assertEqual((self.runs, self.events), ([], []))

    def test_05_missing_or_changed_current_and_prior_contract_refuses(self):
        mutations = ('current_policy', 'current_inputs', 'current_environment', 'prior_policy',
                     'prior_id', 'prior_environment', 'prior_algorithm', 'prior_inputs', 'prior_fp')
        for mutation in mutations:
            for route in ('round', 'amendment'):
                with self.subTest(mutation=mutation, route=route):
                    self.fixture()
                    if mutation == 'current_policy': self.row['reuse'] = ''
                    elif mutation == 'current_inputs': self.row['inputs'] = []
                    elif mutation == 'current_environment': self.row['environment'] = ''
                    else:
                        key = {'prior_policy': 'reuse_policy', 'prior_id': 'environment_id',
                               'prior_environment': 'environment_declaration', 'prior_algorithm': 'input_algorithm',
                               'prior_inputs': 'input_globs', 'prior_fp': 'input_fp'}[mutation]
                        self.result0.pop(key)
                    self.assertIsNone(self.planned(route))

    def test_06_existing_command_inputs_artifact_pass_and_state_checks_remain(self):
        for mutation in ('command', 'expected', 'input', 'environment', 'artifact', 'sha', 'fail', 'unstable', 'missing'):
            for route in ('round', 'amendment'):
                with self.subTest(mutation=mutation, route=route):
                    self.fixture()
                    if mutation == 'command': self.row['cmd'] += ' --changed-tail'
                    elif mutation == 'expected': self.row['expected'] = 'contains: ready'
                    elif mutation == 'input': self.result0['input_fp'] = 'changed'
                    elif mutation == 'environment': self.result0['environment_id'] = 'changed'
                    elif mutation == 'artifact': (self.directory / self.result0['evidence']).write_bytes(b'tampered')
                    elif mutation == 'sha': self.result0['sha1'] = '0' * 40
                    elif mutation == 'fail': self.result0['ok'] = False
                    elif mutation == 'unstable': self.prior['stable'] = False
                    else: self.prior['results'] = []
                    self.assertIsNone(self.planned(route))

    def consume(self, entry, shared=False, full=False):
        self.runs.clear()
        self.events.clear()
        kw = ({'round_shared': {}, 'round_reused': {('A', 'V-1'): entry}} if shared else
              {'amendment': {'reused': {'V-1': entry}, 'id': '01', 'files': []}})
        with self._patches(), contextlib.redirect_stdout(io.StringIO()) as out:
            rc = status.cmd_verify('A', full=full,
                                   round_start={'started': time.time(),
                                                'fp_start': status.ev.worktree_fingerprint(self.root),
                                                'st_start': self.state}, **kw)
        return rc, out.getvalue()

    def test_07_final_sink_rechecks_identity_source_and_transformed_binding(self):
        mutations = ('policy', 'command_tail', 'expected', 'artifact', 'entry_data', 'source_sha', 'full')
        for shared in (False, True):
            for mutation in mutations:
                with self.subTest(shared=shared, mutation=mutation):
                    self.fixture()
                    entry = copy.deepcopy(self.planned('amendment'))
                    self.assertIsNotNone(entry)
                    if mutation == 'policy': entry['result'].pop('reuse_policy')
                    elif mutation == 'command_tail': entry['result']['cmd'] += ' --substituted-tail'
                    elif mutation == 'expected': entry['result']['expected'] = 'contains: ready'
                    elif mutation == 'artifact': (self.directory / self.result0['evidence']).write_bytes(self.data + b'tamper')
                    elif mutation == 'entry_data': entry['data'] = entry['data'].replace(b'ready', b'forged')
                    elif mutation == 'source_sha': entry['result']['sha1'] = '0' * 40
                    rc, out = self.consume(entry, shared=shared, full=mutation == 'full')
                    self.assertEqual(self.runs, [], out)
                    self.assertNotEqual(rc, 0, out)
                    self.assertFalse(any(r.get('ok') or r.get('reused') for e in self.events for r in e['results']), out)
                    if mutation == 'full' and not shared:
                        self.assertIn('nothing was executed', out)  # caller combination already refuses --full
                    else:
                        self.assertRegex(out.lower(), 'stale|replan|not.executed|invalid')

    def test_08_consumed_proof_survives_and_allows_second_carryover(self):
        self.fixture()
        entry = self.planned('amendment')
        rc, out = self.consume(entry)
        self.assertEqual((rc, self.runs), (0, []), out)
        emitted = self.events[0]['results'][0]
        for key in ('reuse_policy', 'input_globs', 'input_fp', 'input_algorithm',
                    'environment_id', 'environment_declaration'):
            self.assertEqual(emitted.get(key), self.result0[key], key)
        self.prior = self.store['A']
        self.assertIsNotNone(self.planned('amendment'))
        self.prior['results'][0].pop('environment_id')
        self.assertIsNone(self.planned('amendment'))

    def long_sink_fixture(self):
        # Reuse the approved 4a fixture's real formatter, full header and prior metadata.
        self.fixture(f'{PY} ok.py --case ' + ('a' * 650) + ' --tail intact')
        current_prior = self.prior
        truncated_fixture.TruncatedCommandProof.fixture(self, cmd=self.cmd)
        self.result0 = self.result
        del self.result  # restore ReuseBase.result rather than shadowing its public method
        self.prior.update({k: v for k, v in current_prior.items() if k != 'results'})
        self.assertEqual(len(self.result0['cmd']), 500)
        self.assertGreater(self.cmd.index('--tail intact'), 500)
        self.assertTrue(self.result0['environment_id'])
        entry = self.planned('amendment')
        self.assertIsNotNone(entry, 'approved 4a strict full-header recovery must reach the final sink')
        return entry

    def test_08_long_truncated_full_header_is_consumed_by_real_sink(self):
        # 4a strict truncated-header recovery produces an amendment-route proof.
        entry = self.long_sink_fixture()
        rc, out = self.consume(entry)
        self.assertEqual((rc, self.runs), (0, []), out)
        self.assertEqual(len(self.events), 1, out)
        emitted = self.events[0]['results'][0]
        self.assertTrue(emitted['ok'] and emitted['reused'], out)
        self.assertEqual(emitted['cmd'], self.cmd)
        self.assertNotIn('Refused:', out)

    def test_07_long_truncated_after500_tail_change_is_refused_by_real_sink(self):
        # shared=True also proves an amendment proof cannot be injected into the round route.
        for shared in (False, True):
            with self.subTest(shared=shared):
                entry = self.long_sink_fixture()
                changed = self.cmd.replace('--tail intact', '--tail changed')
                self.assertEqual(changed[:500], self.result0['cmd'])
                (self.directory / 'spec.md').write_text(self.text.replace(self.cmd, changed), encoding='utf-8')
                rc, out = self.consume(entry, shared=shared)
                self.assertEqual(self.runs, [], out)
                self.assertNotEqual(rc, 0, out)
                self.assertEqual(len(self.events), 1, 'must reach the real final sink, not a caller refusal')
                emitted = self.events[0]['results'][0]
                self.assertFalse(emitted.get('ok') or emitted.get('reused'), out)
                self.assertRegex(out.lower(), 'stale|replan|not.executed|invalid')
                self.assertNotIn('Refused:', out)

    def problems(self):
        with patch.object(status.ev, 'last_code_edit_ts', return_value=0), \
             patch.object(status.ev, 'code_fingerprint', return_value=self.prior['code_fp_end']), \
             patch.object(status, '_contract_environment_id', side_effect=AssertionError('R10 must not probe')):
            return status.rules._run_problems(status.ev, self.root, self.directory, self.text, self.prior)

    def test_09_r10_checks_every_reused_kind_against_current_policy(self):
        for kind in ('amendment-scope', 'amendment-inputs', 'round-same-spec', 'unknown', None):
            with self.subTest(kind=kind):
                self.fixture()
                self.result0.update(reused=True, reused_from={'code_fp': self.prior['code_fp_end']})
                if kind: self.result0['reuse_kind'] = kind
                self.assertEqual(self.problems(), [], 'valid untyped/input-store proof remains valid')
                self.result0.pop('reuse_policy')
                self.assertTrue(self.problems(), 'legacy generic proof must be stale')

    def test_10_dual_shared_and_historical_flags_do_not_bypass_policy(self):
        self.fixture()
        self.result0.update(reused=True, round_shared={'source_spec': 'B'})
        self.result0.pop('reuse_policy')
        self.assertTrue(self.problems())

    def test_12_old_and_missing_algorithms_refused_for_literal_scope(self):
        for field in ('code_algorithm', 'input_algorithm'):
            for value in (None, 'raw-sql-v2-glob-v2'):
                with self.subTest(field=field, algorithm=value):
                    self.fixture()
                    target = self.prior if field == 'code_algorithm' else self.result0
                    if field == 'input_algorithm': self.result0['reused'] = True
                    if value is None: target.pop(field)
                    else: target[field] = value
                    self.assertTrue(self.problems(), 'missing/old algorithm must not gain a compatibility exemption')

    def test_12_plain_same_spec_old_or_missing_input_algorithm_executes(self):
        cases = (('input_algorithm', 'raw-sql-v2-glob-v2'), ('input_algorithm', None),
                 ('code_algorithm', 'raw-sql-v2-glob-v2'), ('code_algorithm', None))
        for field, algorithm in cases:
            with self.subTest(field=field, algorithm=algorithm):
                # Distinct full commands isolate contract-store keys between the subcases.
                suffix = algorithm or 'missing'
                if field == 'code_algorithm': suffix = f'code-{suffix}'
                self.fixture(f'{PY} ok.py --algorithm-case {suffix}')
                proof = self.prior if field == 'code_algorithm' else self.result0
                if field == 'code_algorithm':
                    self.assertEqual(self.result0['input_algorithm'], status.ev.EVIDENCE_ALGORITHM)
                if algorithm is None:
                    proof.pop(field)
                else:
                    proof[field] = algorithm
                self.store['A'] = self.prior
                self.runs.clear()
                self.events.clear()
                rc, out = self.main('verify', 'A')
                self.assertEqual((rc, len(self.runs)), (0, 1), out)
                emitted = self.events[0]['results'][0]
                self.assertFalse(emitted.get('reused'), 'plain verify must not relabel an old proof as current')
                self.assertEqual(emitted['input_algorithm'], status.ev.EVIDENCE_ALGORITHM)

    def test_10_round_collect_regression_always_remains_run(self):
        self.fixture()
        self.text = (self.text.replace('| Environment |', '| Environment | Regression |')
                     .replace('|---|---|---|---|---|---|---|', '|---|---|---|---|---|---|---|---|')
                     .replace(f'| {OFFLINE} |', f'| {OFFLINE} | always |'))
        (self.directory / 'spec.md').write_text(self.text, encoding='utf-8')
        self.assertEqual(status.rules.parse_verification(self.text)[0]['regression'], 'always')
        self.prior['verify_hash'] = status.rules.verification_hash(self.text)
        self.store['A'] = self.prior
        with self._patches():
            specs, rows, notes = rnd.collect(status, self.root, ['A'])
            self.assertEqual(notes, [])
            reused, why = rnd.reuse_plan(status, self.root, specs[0], rows, self.state, self.parts)
        self.assertEqual(reused, {}, 'Regression: always must never be selected as a historical entry')
        self.assertEqual(rows[0].get('regression'), 'always', 'real round collection must preserve canonical policy')
        self.assertIn('Regression', why['V-1'])
        self.assertEqual((self.runs, self.events), ([], []))

    def test_08_cross_spec_store_requires_latest_current_source_event(self):
        variants = ('current', 'old_input', 'missing_input', 'old_code', 'missing_code',
                    'missing_source', 'failed_source')
        for variant in variants:
            with self.subTest(variant=variant):
                # Cold A really executes and uses the normal store producer; no index is preseeded.
                self.fixture(f'{PY} ok.py --cross-store-case {variant}')
                self.store.clear()
                self.runs.clear()
                self.events.clear()
                rc, out = self.main('verify', 'A')
                self.assertEqual((rc, len(self.runs)), (0, 1), out)
                source_run = self.store['A']
                source_result = source_run['results'][0]
                self.assertFalse(source_result.get('reused'), out)
                index_path, object_dir = status._contract_store_paths(self.root)
                index = json.loads(index_path.read_text(encoding='utf-8'))
                stored = next(e for e in index['entries'] if e['cmd'] == self.cmd and e['spec'] == 'A')
                self.assertNotIn('input_algorithm', stored, 'retain the actual established store schema')
                source_data = (self.directory / source_result['evidence']).read_bytes()
                self.assertEqual((object_dir / f"{stored['sha256']}.txt").read_bytes(), source_data)
                self.assertEqual(hashlib.sha1(source_data).hexdigest(), source_result['sha1'])
                if variant == 'missing_source':
                    self.store.pop('A')
                elif variant == 'failed_source':
                    source_run['ok'] = False
                    source_result.update(ok=False, exit=1)
                elif variant in ('old_input', 'missing_input'):
                    if variant == 'old_input': source_result['input_algorithm'] = 'raw-sql-v2-glob-v2'
                    else: source_result.pop('input_algorithm')
                elif variant in ('old_code', 'missing_code'):
                    if variant == 'old_code': source_run['code_algorithm'] = 'raw-sql-v2-glob-v2'
                    else: source_run.pop('code_algorithm')
                target = self.root / 'specs' / 'B'
                target.mkdir(parents=True, exist_ok=True)
                (target / 'spec.md').write_text(self.text.replace('# A\n', '# B\n', 1), encoding='utf-8')
                (target / 'tasks.md').write_text('', encoding='utf-8')
                self.runs.clear()
                self.events.clear()
                rc, out = self.main('verify', 'B')
                self.assertEqual(rc, 0, out)
                emitted = self.events[0]['results'][0]
                if variant == 'current':
                    self.assertEqual(self.runs, [], out)
                    self.assertTrue(emitted.get('reused') and emitted.get('cross_spec'), out)
                    self.assertEqual(emitted['source_spec'], 'A')
                else:
                    self.assertEqual(len(self.runs), 1, out)
                    self.assertFalse(emitted.get('reused') or emitted.get('cross_spec'), out)


if __name__ == '__main__':
    unittest.main()
