import copy
import tempfile
import unittest
from pathlib import Path

from skill.scripts.aidd_reuse import explain_round, plan_round


class ReusePlannerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = str(Path(self.temp.name).resolve())
        self.row = dict(spec_id="s1", row_id="V-1", root=self.root,
                        cwd=self.root, cmd="python -m unittest test_one", expected="exit 0",
                        inputs=["src/**/*.py", "tests/test_one.py"], input_fp="a" * 64,
                        closure_fp="b" * 64, runner_policy="isolated-local-unit-v1",
                        effective_timeout=60, execution_context_id=b"x" * 32,
                        shared_opt_in=True)

    def pair(self):
        other = copy.deepcopy(self.row)
        other["spec_id"] = "s2"
        return [self.row, other]

    def test_equal_observations_group_without_exposing_context(self):
        groups = plan_round(self.pair(), lambda _: True)
        self.assertEqual(len(groups), 1)
        self.assertTrue(groups[0]["eligible"])
        self.assertEqual(len(groups[0]["participants"]), 2)
        self.assertNotIn("python", repr(groups))
        self.assertNotIn("xxxxxxxx", repr(explain_round(groups)))

    def test_default_refuses_without_real_capability(self):
        groups = plan_round(self.pair(), None)
        self.assertEqual([x["reason"] for x in groups], ["capability-unavailable"] * 2)
        self.assertFalse(any(x["eligible"] for x in groups))

    def test_different_contexts_never_share(self):
        for key, value in (("cmd", "other"), ("expected", "exit 1"),
                           ("inputs", ["different"]), ("input_fp", "c" * 64),
                           ("closure_fp", "c" * 64), ("effective_timeout", 90),
                           ("execution_context_id", b"y" * 32)):
            rows = self.pair()
            rows[1][key] = value
            with self.subTest(key=key):
                self.assertEqual(len(plan_round(rows, lambda _: True)), 2)

    def test_different_cwd_never_shares(self):
        rows = self.pair()
        child = Path(self.root) / "nested"
        child.mkdir()
        rows[1]["cwd"] = str(child)
        self.assertEqual(len(plan_round(rows, lambda _: True)), 2)

    def test_bad_inputs_and_unavailable_context_fail_closed(self):
        for field, value in (("inputs", []), ("input_fp", "bad"),
                             ("execution_context_id", "not-an-opaque-token"),
                             ("cwd", "relative"), ("runner_policy", "declared-hermetic")):
            rows = self.pair()
            rows[1][field] = value
            with self.subTest(field=field):
                self.assertFalse(plan_round(rows, lambda _: True)[1]["eligible"])

    def test_duplicate_participants_fail_preflight(self):
        with self.assertRaises(ValueError):
            plan_round([self.row, self.row], lambda _: True)

    def test_explicit_fallback_modes_never_group(self):
        for options in (dict(full=True), dict(bail=True), dict(jobs=2)):
            with self.subTest(options=options):
                self.assertEqual(len(plan_round(self.pair(), lambda _: True, **options)), 2)
                self.assertFalse(any(x["eligible"] for x in plan_round(self.pair(), lambda _: True, **options)))

    def test_capability_error_is_refusal(self):
        def failing(_):
            raise RuntimeError("secret must not leak")
        groups = plan_round(self.pair(), failing)
        self.assertEqual(groups[0]["reason"], "capability-unavailable")
        self.assertNotIn("secret", repr(groups))


if __name__ == "__main__":
    unittest.main()
