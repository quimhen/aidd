"""4a legacy recovery: real planner proof, offline hermetic fallback only; no command execution."""
import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'scripts'))
import aidd_amendment_verify as amendment
import aidd_round as rnd
import aidd_status as status
from test_verify_round import PY
from test_verify_round_reuse import ReuseBase

OFFLINE = 'contract:offline;vars=none;packages=none'
BODY = 'ran 3 tests ok, all assertions passed; ready\n'


class TruncatedCommandProof(ReuseBase):
    """Synthetic genuine-shaped prior fixture; never calls verify or a subprocess."""

    def fixture(self, cmd=None, reuse='hermetic', environment=OFFLINE, inputs='ok.py,src/a.py'):
        cmd = cmd or f'{PY} ok.py --case ' + ('a' * 650) + ' --tail intact'
        self.cmd = cmd
        self.directory = self.root / 'specs' / 'A'
        self.directory.mkdir(parents=True, exist_ok=True)
        table = ('## Verification\n'
                 '| # | Command | Expected | Inputs | Reuse | Environment | Regression |\n'
                 '|---|---|---|---|---|---|---|\n'
                 f'| V-1 | `{cmd}` | exit 0 | {inputs} | {reuse} | {environment} | |\n')
        self.row = status.rules.parse_verification(table)[0]
        self.assertEqual(self.row['cmd'], cmd)
        self.full_header = f'# {cmd} | exit 0 | 2026-11-14T14:12:21'
        self.data = (self.full_header + '\n' + BODY).encode('utf-8')
        evidence = self.directory / 'evidence' / 'verify-V-1.txt'
        evidence.parent.mkdir(exist_ok=True)
        evidence.write_bytes(self.data)
        recorded, labels = status.ev.redact_secrets(cmd, limit=500)
        self.assertEqual(len(recorded), 500)
        self.result = {'n': 'V-1', 'cmd': recorded, 'expected': 'exit 0', 'ok': True,
                       'exit': 0, 'evidence': 'evidence/verify-V-1.txt',
                       'sha1': hashlib.sha1(self.data).hexdigest(), 'secs': 0.1,
                       'input_globs': self.row['inputs'], 'reuse_policy': 'hermetic',
                       'input_algorithm': status.ev.EVIDENCE_ALGORITHM,
                       'input_fp': status.rules.row_input_fingerprint(self.root, self.row['inputs']),
                       'env_id': '', 'environment_declaration': environment,
                       'environment_id': status._contract_environment_id(cmd, environment)}
        self.prior = {'stable': True, 'results': [self.result], 'started': 1794665541,
                      'code_algorithm': status.ev.EVIDENCE_ALGORITHM,
                      'code_fp_end': 'c2:' + '1' * 16, 'verify_hash': '2' * 40}
        self.parts = {'containers': {}, 'identity': {}, 'vars': {}}
        self.files = []
        return self.row

    def plan_one(self):
        with patch.object(status.ev, 'latest_verify_run', return_value=self.prior):
            return amendment.plan(status, self.root, self.directory, [self.row],
                                  None, self.parts, self.files, ['src/**'], '01')[0]

    def assert_action(self, action):
        item = self.plan_one()
        self.assertEqual(item['action'], action, item['reason'])
        self.assertEqual(self.runs, [])
        self.assertEqual(self.events, [])
        return item

    def rewrite_artifact(self, data, bind=True):
        (self.directory / self.result['evidence']).write_bytes(data)
        if bind:
            self.result['sha1'] = hashlib.sha1(data).hexdigest()

    def test_01_truncated_direct_python_offline_hermetic_is_recovered(self):
        self.fixture()
        self.assertTrue(self.result['environment_id'], 'real offline validator must accept the positive fixture')
        item = self.assert_action('REUSED')
        self.assertEqual(item['entry']['kind'], 'amendment-inputs')
        self.assertEqual(item['entry']['result'], self.result)

    def test_02_existing_full_command_path_is_unchanged(self):
        self.fixture()
        self.result['cmd'] = self.cmd
        self.assert_action('REUSED')
        # 4b deliberately requires a contract for the full-command path too.
        self.row['reuse'] = ''
        self.row['environment'] = ''
        self.result.pop('environment_id')
        self.result.pop('environment_declaration')
        self.assert_action('RUN')

    def test_03_same_prefix_different_tail_runs(self):
        self.fixture()
        self.row['cmd'] = self.cmd.replace('--tail intact', '--tail changed')
        self.assertEqual(self.row['cmd'][:500], self.cmd[:500])
        self.assert_action('RUN')

    def test_04_prefix_and_length_fail_closed(self):
        for value in ['x' * 500, 'a' * 499, 'a' * 501]:
            with self.subTest(value_length=len(value)):
                self.fixture()
                self.result['cmd'] = value
                self.assert_action('RUN')

    def test_05_artifact_binding_and_confinement_fail_closed(self):
        for mutation in ['tamper', 'missing', 'sha', 'outside']:
            with self.subTest(mutation=mutation):
                self.fixture()
                path = self.directory / self.result['evidence']
                if mutation == 'tamper':
                    self.rewrite_artifact(self.data + b'tamper', bind=False)
                elif mutation == 'missing':
                    path.unlink()
                elif mutation == 'sha':
                    self.result['sha1'] = 'bad'
                else:
                    self.result['evidence'] = '../outside.txt'
                    (self.directory.parent / 'outside.txt').write_bytes(self.data)
                self.assert_action('RUN')

    def test_06_stable_pass_and_expected_are_mandatory(self):
        for mutation in ['unstable', 'not_ok', 'exit', 'expected', 'missing_row']:
            with self.subTest(mutation=mutation):
                self.fixture()
                if mutation == 'unstable': self.prior['stable'] = False
                elif mutation == 'not_ok': self.result['ok'] = False
                elif mutation == 'exit': self.result['exit'] = 1
                elif mutation == 'expected': self.row['expected'] = 'contains: ready'
                else: self.prior['results'] = []
                self.assert_action('RUN')

    def test_07_inputs_proof_and_policy_are_mandatory(self):
        for mutation in ['fingerprint', 'algorithm', 'declaration', 'no_inputs', 'never', 'not_hermetic']:
            with self.subTest(mutation=mutation):
                self.fixture()
                if mutation == 'fingerprint': self.result['input_fp'] = 'changed'
                elif mutation == 'algorithm': self.result['input_algorithm'] = 'unknown'
                elif mutation == 'declaration': self.result['input_globs'] = ['other.py']
                elif mutation == 'no_inputs': self.row['inputs'] = []
                elif mutation == 'never': self.row['reuse'] = 'never'
                else: self.row['reuse'] = ''
                self.assert_action('RUN')

    def test_08_environment_contract_proof_is_mandatory(self):
        for mutation in ['parts_unknown', 'missing_id', 'different_id', 'different_declaration', 'no_contract']:
            with self.subTest(mutation=mutation):
                self.fixture()
                if mutation == 'parts_unknown': self.parts = None
                elif mutation == 'missing_id': self.result.pop('environment_id')
                elif mutation == 'different_id': self.result['environment_id'] = 'other'
                elif mutation == 'different_declaration': self.result['environment_declaration'] = 'other'
                else: self.row['environment'] = ''
                self.assert_action('RUN')

    def test_09_strict_first_header_only_and_malformed_headers_run(self):
        for mutation in ['exit', 'timestamp', 'prefix', 'body_only', 'utf8', 'suffix', 'control']:
            with self.subTest(mutation=mutation):
                self.fixture()
                header = self.full_header
                if mutation == 'exit': header = header.replace(' | exit 0 | ', ' | exit 1 | ')
                elif mutation == 'timestamp': header = header.replace('2026-11-14T14:12:21', 'not-a-time')
                elif mutation == 'prefix': header = header[2:]
                elif mutation == 'body_only': header = 'not a header\n' + header
                elif mutation == 'suffix': header += ' garbage'
                elif mutation == 'control': header = header.replace('--tail', '\t--tail')
                data = (header + '\n' + BODY).encode()
                if mutation == 'utf8': data = b'\xff' + data
                self.rewrite_artifact(data)
                self.assert_action('RUN')

    def test_10_redacted_projection_and_quoted_argument_difference_run(self):
        self.fixture(cmd=f'{PY} ok.py --padding ' + 'a' * 650 + ' password=dummy')
        self.assertTrue(status.ev.redact_secrets(self.cmd, limit=500)[1])
        self.assert_action('RUN')
        self.fixture(cmd=f'{PY} ok.py --padding ' + 'a' * 650 + ' --value "two  spaces"')
        self.row['cmd'] = self.cmd.replace('two  spaces', 'two spaces')
        self.assertNotEqual(rnd.normalize_command(self.row['cmd']), rnd.normalize_command(self.cmd))
        self.assert_action('RUN')

    def test_11_forced_runs_remain_runs(self):
        for mutation in ['regression', 'input_file', 'command_file']:
            with self.subTest(mutation=mutation):
                self.fixture()
                if mutation == 'regression': self.row['regression'] = 'always'
                elif mutation == 'input_file': self.files = ['src/a.py']
                else: self.files = ['ok.py']
                self.assert_action('RUN')

    def test_12_current_output_and_lint_checks_remain_mandatory(self):
        self.fixture()
        with patch.object(status, '_cached_pass_valid', return_value=False):
            self.assert_action('RUN')
        with patch.object(status.rules, 'verification_command_problem', return_value='invalid today'):
            self.assert_action('RUN')

    def test_13_database_docker_node_unknown_external_runners_never_recover(self):
        for runner in [f'{PY} eDoc/tools/db_verify.py', 'docker exec db python ok.py', 'node check.js']:
            with self.subTest(runner=runner):
                self.fixture(cmd=runner + ' --padding ' + 'a' * 650)
                self.assertIsNone(status._contract_environment_id(self.cmd, OFFLINE))
                # Even fabricated-looking intact IDs do not replace real current validation.
                self.result['environment_id'] = 'plausible-but-not-current'
                self.assert_action('RUN')


if __name__ == '__main__':
    unittest.main()
