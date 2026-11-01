import hashlib
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'scripts'))
import aidd_status as status
import aidd_rules as rules


class DeclaredHermetic(unittest.TestCase):
    def test_declared_hermetic_rows_run_again_without_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / 'specs' / 's'
            spec.mkdir(parents=True)
            (root / 'test.py').write_text('print(1)', encoding='utf-8')
            (spec / 'tasks.md').write_text('| Task | Target file |\n|---|---|\n| T-01 | `test.py` |\n', encoding='utf-8')
            (spec / 'spec.md').write_text(
                '## Verification\n| # | Command | Expected | Inputs | Reuse | Environment |\n'
                '|---|---|---|---|---|---|\n| V1 | python test.py | exit 0 | test.py | hermetic | none |\n', encoding='utf-8')
            state = ('git', {'test.py': b'x'})
            prior = [None]
            calls = []
            def run(cmd, _root, output, _timeout):
                calls.append(cmd)
                output.write_text('three assertions passed successfully\n', encoding='utf-8')
                return 0, ''
            def record(_root, _session, _spec, ok, _hash, results, _started, _start, _end, stable, **kw):
                prior[0] = {'ok': ok, 'stable': stable, 'results': results, 'code_fp_end': kw.get('code_fp_end')}
                return True
            fingerprint = ['one']
            with patch.object(status.ev, 'find_root', return_value=root), \
                 patch.object(status, '_resolve_spec', return_value=spec), \
                 patch.object(status, '_current_session', return_value='session'), \
                 patch.object(status.ev, 'latest_verify_run', side_effect=lambda *_: prior[0]), \
                 patch.object(status.ev, 'code_state', return_value=state), \
                 patch.object(status.ev, 'state_diff', return_value=[]), \
                 patch.object(status.ev, 'fingerprint_of', return_value='fingerprint'), \
                 patch.object(status.ev, 'worktree_fingerprint', return_value='fp'), \
                 patch.object(status.rules, 'row_input_fingerprint', side_effect=lambda *_: fingerprint[0]), \
                 patch.object(status.ev, 'append_verify_run', side_effect=record), \
                 patch.object(status, '_run_row', side_effect=run), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(status.cmd_verify(str(spec)), 0, output.getvalue())
                self.assertEqual(status.cmd_verify(str(spec)), 0, output.getvalue())
                self.assertEqual(len(calls), 2)
                fingerprint[0] = 'two'
                self.assertEqual(status.cmd_verify(str(spec)), 0, output.getvalue())
                self.assertEqual(len(calls), 3)
                self.assertEqual(status.cmd_verify(str(spec), full=True), 0, output.getvalue())
                self.assertEqual(len(calls), 4)


if __name__ == '__main__':
    unittest.main()
