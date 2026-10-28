"""aidd_sqlcheck: engine-agnostic static SQL compile with a content-hash cache (stdlib unittest)."""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skill" / "scripts"))
import aidd_sqlcheck as sc  # noqa: E402

OK_SQL = "CREATE TABLE a(id int primary key);\n"
BAD_SQL = "CREATE TABLE b(id int,\nSELEC 1;\n"
PASS_CMD = f'"{sys.executable}" -c "import sys; sys.exit(0)" {{file}}'
FAIL_CMD = f'"{sys.executable}" -c "import sys; sys.exit(3)" {{file}}'


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = sc.main(argv)
    return rc, buf.getvalue()


class SqlCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.cache = str(self.dir / "cache.json")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        (self.dir / name).write_text(text, encoding="utf-8")

    def test_collect_natural_order_across_paths(self):
        a, b = self.dir / "a", self.dir / "b"
        a.mkdir()
        b.mkdir()
        (a / "10_x.sql").write_text(OK_SQL)
        (a / "2_x.sql").write_text(OK_SQL)
        (b / "3_x.sql").write_text(OK_SQL)
        names = [f.name for f in sc.collect([str(a), str(b)])]
        self.assertEqual(names, ["2_x.sql", "3_x.sql", "10_x.sql"])

    def test_missing_path_exit_2(self):
        rc, _ = _run([str(self.dir / "nope.sql")])
        self.assertEqual(rc, 2)

    def test_no_args_exit_2(self):
        rc, _ = _run([])
        self.assertEqual(rc, 2)

    def test_unknown_engine_without_cmd_fails_closed(self):
        self.write("1.sql", OK_SQL)
        rc, out = _run([str(self.dir), "--engine", "mssql", "--no-cache"])
        self.assertEqual(rc, 2)
        self.assertIn("--cmd", out)

    def test_empty_selection_fails_closed(self):
        rc, out = _run([str(self.dir), "--engine", "mssql"])
        self.assertEqual(rc, 2)
        self.assertIn("no SQL files", out)

    def test_cmd_checker_pass_fail_and_cache(self):
        self.write("1.sql", OK_SQL)
        rc, out = _run([str(self.dir), "--cmd", PASS_CMD, "--cache", self.cache])
        self.assertEqual(rc, 0)
        self.assertIn("1 compiled now", out)
        rc, out = _run([str(self.dir), "--cmd", PASS_CMD, "--cache", self.cache])
        self.assertIn("1 unchanged (cached)", out)
        # a different checker never reuses the other checker's verdict
        rc, out = _run([str(self.dir), "--cmd", FAIL_CMD, "--cache", self.cache])
        self.assertEqual(rc, 1)
        self.assertIn("FAIL", out)

    def test_changed_file_is_rechecked(self):
        self.write("1.sql", OK_SQL)
        _run([str(self.dir), "--cmd", PASS_CMD, "--cache", self.cache])
        self.write("1.sql", OK_SQL + "-- edit\n")
        _, out = _run([str(self.dir), "--cmd", PASS_CMD, "--cache", self.cache])
        self.assertIn("1 compiled now", out)

    def test_crlf_is_not_a_change(self):
        (self.dir / "1.sql").write_bytes(OK_SQL.encode().replace(b"\n", b"\r\n"))
        _run([str(self.dir), "--cmd", PASS_CMD, "--cache", self.cache])
        (self.dir / "1.sql").write_bytes(OK_SQL.encode())
        _, out = _run([str(self.dir), "--cmd", PASS_CMD, "--cache", self.cache])
        self.assertIn("1 unchanged (cached)", out)

    def test_postgres_adapter(self):
        try:
            import pglast  # noqa: F401
        except Exception:
            self.skipTest("pglast not installed")
        self.write("1_ok.sql", OK_SQL)
        self.write("2_bad.sql", BAD_SQL)
        rc, out = _run([str(self.dir), "--no-cache"])
        self.assertEqual(rc, 1)
        self.assertIn("2_bad.sql", out)
        self.assertNotIn("FAIL " + str(self.dir / "1_ok.sql"), out)
        (self.dir / "2_bad.sql").unlink()
        rc, out = _run([str(self.dir), "--no-cache"])
        self.assertEqual(rc, 0)
        self.assertIn("Apply manifest", out)


if __name__ == "__main__":
    unittest.main()
