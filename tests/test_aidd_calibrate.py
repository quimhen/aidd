"""Tests for scripts/aidd_calibrate.py (AC-006) — stdlib unittest, throwaway roots."""
import contextlib
import io
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import aidd_calibrate as ac  # noqa: E402

TASKS = (
    "# Tasks\n\n"
    "### T-01 first\n- Effort: Low\n- Agent min: 1\n- Tokens (est): 40k\n\n"
    "### T-02 second\n- Effort: Low\n- Agent min: 2.5\n- Tokens (est): 10k\n\n"
    "### T-03 third\n- Effort: Medium\n- Agent min: 3\n- Tokens (est): 60k\n\n"
    "### T-04 fourth\n- Effort: High\n- Agent min: 5\n- Tokens (est): 100k\n"
)


def make_spec(root, name="001-x", text=TASKS):
    d = Path(root) / "specs" / name
    d.mkdir(parents=True)
    (d / "tasks.md").write_text(text, encoding="utf-8")
    return d


class TestLoadCalibration(unittest.TestCase):
    def assert_seed(self, cal):
        self.assertEqual(cal["human_factor"], 3)
        c = cal["classes"]
        self.assertEqual((c["Low"]["agent_min"], c["Low"]["tokens_k"]), (1, 45))
        self.assertEqual((c["Medium"]["agent_min"], c["Medium"]["tokens_k"]), (2, 62))
        self.assertEqual((c["High"]["agent_min"], c["High"]["tokens_k"]), (4, 90))

    def test_no_file_returns_seed(self):
        with TemporaryDirectory() as t:
            self.assert_seed(ac.load_calibration(t))

    def test_malformed_falls_back_to_seed(self):
        with TemporaryDirectory() as t:
            p = Path(t) / ".aidd"
            p.mkdir()
            (p / "calibration.toon").write_text(
                "human_factor: abc\nclasses[1]{a,b,c,d}:\n  Low,x,y,z\n", encoding="utf-8")
            self.assert_seed(ac.load_calibration(t))

    def test_garbage_falls_back_to_seed(self):
        with TemporaryDirectory() as t:
            p = Path(t) / ".aidd"
            p.mkdir()
            (p / "calibration.toon").write_bytes(b"\xff\xfe\x00garbage")
            self.assert_seed(ac.load_calibration(t))


class TestParseClosedTasks(unittest.TestCase):
    def test_sums_per_class(self):
        out = ac.parse_closed_tasks(TASKS)
        self.assertEqual(out["Low"], {"agent_min": 3.5, "tokens_k": 50.0, "n": 2})
        self.assertEqual(out["Medium"]["n"], 1)
        self.assertEqual(out["High"]["agent_min"], 5.0)
        self.assertEqual(out["High"]["tokens_k"], 100.0)

    def test_measured_overrides_estimates(self):
        out = ac.parse_closed_tasks(TASKS, {"T-01": {"agent_min": 10, "tokens_k": 7}})
        self.assertEqual(out["Low"]["agent_min"], 12.5)
        self.assertEqual(out["Low"]["tokens_k"], 17.0)

    def test_empty_and_no_effort(self):
        self.assertEqual(ac.parse_closed_tasks(""), {})
        self.assertEqual(ac.parse_closed_tasks(None), {})
        self.assertEqual(ac.parse_closed_tasks("### T-01 x\n- Agent min: 1\n"), {})


class TestRecord(unittest.TestCase):
    def read_runs(self, root):
        return ac.load_calibration(root)["runs"]

    def test_creates_file_from_seed_and_one_row_per_class(self):
        with TemporaryDirectory() as t:
            d = make_spec(t)
            rows = ac.record(d, t)
            self.assertTrue((Path(t) / ".aidd" / "calibration.toon").exists())
            self.assertEqual([r["class"] for r in rows], ["Low", "Medium", "High"])
            cal = ac.load_calibration(t)
            self.assertEqual(cal["human_factor"], 3)
            self.assertEqual(cal["classes"]["Low"]["tokens_k"], 45)
            runs = cal["runs"]
            self.assertEqual(len(runs), 3)
            low = [r for r in runs if r["class"] == "Low"][0]
            self.assertEqual(low["spec"], "001-x")
            self.assertEqual((low["agent_min"], low["tokens_k"]), (3.5, 50))

    def test_idempotent(self):
        with TemporaryDirectory() as t:
            d = make_spec(t)
            ac.record(d, t)
            first = (Path(t) / ".aidd" / "calibration.toon").read_text(encoding="utf-8")
            ac.record(d, t)
            second = (Path(t) / ".aidd" / "calibration.toon").read_text(encoding="utf-8")
            self.assertEqual(first, second)
            self.assertEqual(len(self.read_runs(t)), 3)

    def test_replaces_values_when_tasks_change(self):
        with TemporaryDirectory() as t:
            d = make_spec(t)
            ac.record(d, t)
            (d / "tasks.md").write_text(
                "### T-01 a\n- Effort: Low\n- Agent min: 9\n- Tokens (est): 20k\n",
                encoding="utf-8")
            ac.record(d, t)
            runs = self.read_runs(t)
            lows = [r for r in runs if r["class"] == "Low"]
            self.assertEqual(len(lows), 1)
            self.assertEqual((lows[0]["agent_min"], lows[0]["tokens_k"]), (9, 20))
            self.assertEqual(len(runs), 3)  # Medium/High rows of old run are kept

    def test_two_specs_coexist(self):
        with TemporaryDirectory() as t:
            ac.record(make_spec(t, "001-x"), t)
            ac.record(make_spec(t, "002-y"), t)
            runs = self.read_runs(t)
            self.assertEqual(len(runs), 6)
            self.assertEqual({r["spec"] for r in runs}, {"001-x", "002-y"})

    def test_missing_tasks_returns_empty(self):
        with TemporaryDirectory() as t:
            d = Path(t) / "specs" / "003-z"
            d.mkdir(parents=True)
            self.assertEqual(ac.record(d, t), [])

    def test_root_defaults_two_levels_above_spec_dir(self):
        with TemporaryDirectory() as t:
            d = make_spec(t)
            ac.record(d)
            self.assertTrue((Path(t).resolve() / ".aidd" / "calibration.toon").exists())
            self.assertEqual(len(self.read_runs(Path(t).resolve())), 3)


class TestMain(unittest.TestCase):
    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ac.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_record_prints_rows(self):
        with TemporaryDirectory() as t:
            d = make_spec(t)
            code, out, _ = self.run_main(["record", str(d)])
            self.assertEqual(code, 0)
            self.assertIn("001-x,Low,3.5,50", out)
            self.assertIn("001-x,Medium,3,60", out)
            self.assertIn("001-x,High,5,100", out)

    def test_bad_usage_exits_2(self):
        self.assertEqual(self.run_main([])[0], 2)
        self.assertEqual(self.run_main(["bogus"])[0], 2)
        self.assertEqual(self.run_main(["bogus", "x"])[0], 2)


if __name__ == "__main__":
    unittest.main()
