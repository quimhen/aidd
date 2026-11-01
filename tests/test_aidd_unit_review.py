import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / 'skill/scripts/aidd_review.py'
REPO = SCRIPT.parents[2]


class UnitReview(unittest.TestCase):
    def test_summary_is_read_only_and_missing_unit_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / 'specs/s'
            unit = spec / 'amendments/a'
            unit.mkdir(parents=True)
            (root / 'input.md').write_text('input', encoding='utf-8')
            (unit / 'manifest.json').write_text(json.dumps(dict(
                schema_version=1, spec_id='s', unit_id='a', sequence=1,
                parents=[], paths=['input.md'], targets=['output.py'])), encoding='utf-8')
            before = sorted(p.relative_to(root).as_posix() for p in root.rglob('*'))
            cmd = [sys.executable, str(SCRIPT), str(spec), '--unit', 'a', '--summary']
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertRegex(result.stdout, r'Digest \(SHA-256\): [0-9a-f]{64}')
            self.assertIn('not owner approval', result.stdout)
            self.assertEqual(before, sorted(p.relative_to(root).as_posix() for p in root.rglob('*')))
            result = subprocess.run([*cmd[:-2], 'missing', '--summary'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            result = subprocess.run(cmd[:-1], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            env = dict(os.environ, AIDD_HOME=str(REPO / 'skill'))
            result = subprocess.run([sys.executable, '-m', 'aidd.cli', 'review', str(spec),
                                     '--unit', 'a', '--summary'], cwd=REPO, env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Unit: s:a', result.stdout)


if __name__ == '__main__':
    unittest.main()
