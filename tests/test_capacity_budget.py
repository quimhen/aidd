"""Amendment 10 (extension b) of spec 007: `## Capacity & test budget` (aidd:FR-401..FR-403, AC-458..AC-459)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'scripts'))
import aidd_rules as rules  # noqa: E402

VERIF = ('## Verification\n| # | Command | Expected | Covers | Tier |\n|---|---|---|---|---|\n'
         '| V-1 | python a.py | exit 0 | FR-1 | functional |\n| V-2 | python b.py | exit 0 | FR-2 | perf |\n')
CAP = ('## Capacity & test budget\n\nRAM: 3 GB (WSL2)\nHeavy runs at a time: 1\nRound budget: 300 s\n'
       'Not verified: volume above 38 000 lines\n\n'
       '| # | Tier | Est. s | Budget s | Data scale | Scale justification |\n|---|---|---|---|---|---|\n'
       '| V-1 | functional | 40 | 120 | minimal | |\n'
       '| V-2 | perf | 15 min | 1200 | 38 000 lines | plan shown linear at N=2 000; above not-verified |\n')


def msgs(text):
    return [v['message'] for v in rules.capacity_problems(text)]


class Capacity(unittest.TestCase):
    def test_complete_section_has_no_problem(self):
        self.assertEqual(msgs(VERIF + CAP), [])
        cap = rules.parse_capacity(VERIF + CAP)
        self.assertEqual((cap['ram_mb'], cap['heavy'], cap['round_s']), (3072.0, 1, 300.0))
        self.assertEqual(cap['rows']['2']['est'], 900.0)
        self.assertEqual(cap['rows']['2']['scale'], 38000.0)

    def test_missing_section_when_opted_in(self):
        self.assertEqual(len(msgs(VERIF)), 1)
        self.assertIn('no "## Capacity & test budget"', msgs(VERIF)[0])

    def test_est_over_budget(self):
        self.assertTrue(any('over its budget' in m for m in msgs(VERIF + CAP.replace('| 40 | 120 |', '| 200 | 120 |'))))

    def test_sum_over_round_budget(self):
        t = VERIF + CAP.replace('Round budget: 300 s', 'Round budget: 30 s')
        self.assertTrue(any('round budget' in m for m in msgs(t)))

    def test_unjustified_seed(self):
        t = VERIF + CAP.replace('| minimal | |', '| 38 000 lines | |')
        self.assertTrue(any('without a scale justification' in m for m in msgs(t)))
        t = VERIF + CAP.replace('plan shown linear at N=2 000; above not-verified', '')
        self.assertTrue(any('without a scale justification' in m for m in msgs(t)))

    def test_tier_mismatch_missing_row_and_lines(self):
        t = VERIF + CAP.replace('| V-1 | functional |', '| V-1 | perf |')
        self.assertTrue(any('Make' not in m and 'but `functional` in Verification' in m for m in msgs(t)))
        t = VERIF + CAP.replace('| V-2 | perf | 15 min', '| V-9 | perf | 15 min')
        self.assertTrue(any('row V-2 has no budget row' in m for m in msgs(t)))
        t = VERIF + CAP.replace('RAM: 3 GB (WSL2)\n', '').replace('Not verified: volume above 38 000 lines\n', '')
        m = msgs(t)
        self.assertTrue(any('RAM' in x for x in m) and any('Not verified' in x for x in m))

    def test_check_verification_includes_capacity(self):
        self.assertTrue(any('Capacity' in v['message'] for v in rules.check_verification(VERIF)))

    def test_legacy_spec_only_warns(self):
        legacy = '## Verification\n| # | Command | Expected | Covers |\n|---|---|---|---|\n| V-1 | python a.py | exit 0 | FR-1 |\n'
        self.assertEqual(msgs(legacy), [])
        self.assertEqual(len(rules.capacity_warnings(legacy)), 1)

    def test_warnings_half_budget_and_jobs(self):
        t = VERIF.replace('## Verification\n', '## Verification\nJobs: 2\n') + CAP.replace('| 40 | 120 |', '| 200 | 220 |')
        w = ' '.join(rules.capacity_warnings(t))
        self.assertIn('over half the round budget', w)
        self.assertIn('Jobs: 2', w)

    def test_template_placeholder_row_ignored(self):
        tpl = (Path(__file__).resolve().parents[1] / 'skill' / 'templates' / 'spec.md').read_text(encoding='utf-8')
        cap = rules.parse_capacity(tpl)
        self.assertIsNotNone(cap)
        self.assertEqual(cap['rows'], {})


if __name__ == '__main__':
    unittest.main()
