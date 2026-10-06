"""G1: structure graphs are used automatically at Step -1 (find_spec) and on SQL reads; nothing asks the user."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skill" / "scripts"
HOOKS = ROOT / "skill" / "hooks"
sys.path.insert(0, str(SCRIPTS))

import aidd_graphs  # noqa: E402

SQL = """
CREATE TABLE customers (id uuid PRIMARY KEY, partner_code text NOT NULL, created_at timestamptz);
COMMENT ON COLUMN customers.partner_code IS 'Business partner code from SAP';
CREATE TABLE orders (id uuid PRIMARY KEY, customer_id uuid REFERENCES customers(id), total numeric);
CREATE FUNCTION fe_close_order(p uuid) RETURNS void LANGUAGE plpgsql AS $$
BEGIN UPDATE orders SET total = 0 WHERE id = p; END $$;
"""


def make_project(td):
    root = Path(td)
    (root / "supabase" / "migrations").mkdir(parents=True)
    (root / "supabase" / "migrations" / "0001_init.sql").write_text(SQL, encoding="utf-8")
    (root / "specs" / "001-x").mkdir(parents=True)
    (root / "specs" / "001-x" / "spec.md").write_text("# 001 orders\n", encoding="utf-8")
    return root


class TestAuto(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = make_project(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_sql_migrations_are_autodetected_as_a_db_graph(self):
        reg = {g["name"]: g for g in aidd_graphs.load_registry(self.root)}
        self.assertEqual(reg["db"]["kind"], "db")
        self.assertEqual(reg["db"]["refresh"], "builtin:sql")

    def test_missing_graph_starts_background_refresh_and_says_so(self):
        with mock.patch.object(aidd_graphs, "refresh", return_value={"started": True, "reason": "", "pid": 1, "log": ""}) as r:
            out = aidd_graphs.auto(self.root, ["orders"])
        r.assert_called_once_with(self.root, "db", background=True)
        self.assertIn("refresh started in background", "\n".join(out))

    def test_built_graph_returns_matching_nodes_with_purpose(self):
        e = [g for g in aidd_graphs.load_registry(self.root) if g["name"] == "db"][0]
        r = subprocess.run([sys.executable, str(SCRIPTS / "sql_graph.py"), "--root", str(self.root), "--out", e["output"],
                            str(self.root / "supabase" / "migrations")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = "\n".join(aidd_graphs.auto(self.root, ["partner_code", "orders"]))
        self.assertIn("db:column:customers.partner_code", out)
        self.assertIn("Business partner code from SAP", out)
        self.assertIn("db:table:orders", out)
        self.assertIn("BEFORE reading SQL", out)

    def test_off_switch_and_no_graphs(self):
        with mock.patch.dict(os.environ, {"AIDD_GRAPHS": "off"}):
            self.assertEqual(aidd_graphs.auto(self.root, ["orders"]), [])
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(aidd_graphs.auto(Path(td), ["orders"]), [])

    def test_find_spec_prints_the_graph_block_before_the_spec_verdict(self):
        e = [g for g in aidd_graphs.load_registry(self.root) if g["name"] == "db"][0]
        subprocess.run([sys.executable, str(SCRIPTS / "sql_graph.py"), "--root", str(self.root), "--out", e["output"],
                        str(self.root / "supabase" / "migrations")], check=True, capture_output=True)
        env = dict(os.environ, AIDD_GRAPHS="")
        r = subprocess.run([sys.executable, str(SCRIPTS / "find_spec.py"), "orders", "partner_code"], cwd=str(self.root),
                           capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertIn("Graph 'db' (db): fresh", r.stdout)
        self.assertIn("db:table:orders", r.stdout)
        self.assertLess(r.stdout.index("Graph 'db'"), r.stdout.index("aidd spec search"))


class TestSqlReadHint(unittest.TestCase):
    def run_hook(self, root, file_path, sid="t-sql-hint", **extra):
        ev = {"session_id": sid, "cwd": str(root), "tool_input": dict({"file_path": str(file_path)}, **extra)}
        r = subprocess.run([sys.executable, str(HOOKS / "read_hint.py")], input=json.dumps(ev), capture_output=True,
                           text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0)
        return r.stdout

    def test_whole_sql_read_in_a_db_project_hints_the_graph_once(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_project(td)
            f = root / "supabase" / "migrations" / "0001_init.sql"
            sid = "t-sql-%d" % os.getpid()
            out = self.run_hook(root, f, sid=sid)
            self.assertIn("aidd graphs show db", out)
            self.assertEqual(self.run_hook(root, f, sid=sid), "")                 # once per file per session
            self.assertEqual(self.run_hook(root, f, sid=sid + "b", limit=20), "")  # a ranged read is fine

    def test_no_hint_without_a_db_graph(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "specs").mkdir()
            f = Path(td) / "x.sql"
            f.write_text("select 1;", encoding="utf-8")
            self.assertEqual(self.run_hook(td, f, sid="t-nodb-%d" % os.getpid()), "")


if __name__ == "__main__":
    unittest.main()
