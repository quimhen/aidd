"""Tests for scripts/sql_graph.py - stdlib unittest/pytest, throwaway project roots."""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import sql_graph as sg  # noqa: E402

M1 = """-- initial schema
CREATE TABLE IF NOT EXISTS public.customers (
    id SERIAL PRIMARY KEY,
    name varchar(100) NOT NULL,
    legacy text,
    CreateDate timestamp DEFAULT now()
);
CREATE TABLE orders (
    id serial,
    customer_id int NOT NULL REFERENCES customers(id),
    total numeric(10, 2) NOT NULL DEFAULT 0,
    status text,
    is_paid boolean,
    PRIMARY KEY (id)
);
CREATE TABLE order_lines (
    id serial PRIMARY KEY,
    order_id int NOT NULL,
    sku text,
    qty int
);
CREATE INDEX idx_orders_cust ON orders (customer_id, status);
CREATE TABLE broken (id int,;
COMMENT ON TABLE orders IS 'Customer orders';
COMMENT ON COLUMN orders.total IS 'Order total, tax included';
"""

M2 = """/* second migration */
ALTER TABLE order_lines ADD CONSTRAINT fk_ol_order FOREIGN KEY (order_id) REFERENCES orders(id);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS email text, ADD COLUMN phone text;
ALTER TABLE customers DROP COLUMN legacy;
ALTER TABLE customers RENAME COLUMN phone TO mobile;
ALTER TABLE orders ALTER COLUMN status SET NOT NULL;
ALTER TABLE orders ALTER COLUMN total TYPE numeric(12,2);

CREATE VIEW v_orders AS
SELECT c.name, o.total
FROM orders o JOIN customers c ON c.id = o.customer_id;

CREATE OR REPLACE FUNCTION add_line(p_order int, p_sku text) RETURNS void AS $$
BEGIN
    -- a comment mentioning DELETE FROM customers
    INSERT INTO order_lines (order_id, sku) VALUES (p_order, p_sku);
    UPDATE orders o SET total = total + 1 WHERE o.id = p_order;
    PERFORM touch_order(p_order);
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION touch_order(p int) RETURNS void AS $fn$
BEGIN
    UPDATE orders SET status = 'x' WHERE id = p;
END;
$fn$ LANGUAGE plpgsql;

CREATE FUNCTION dyn(tname text) RETURNS void AS $$
BEGIN
    EXECUTE 'DELETE FROM ' || tname;
    SELECT name FROM customers;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_orders AFTER UPDATE ON orders FOR EACH ROW EXECUTE FUNCTION touch_order();
COMMENT ON COLUMN customers.email IS 'Contact e-mail';
"""


def project(tmp, files):
    root = Path(tmp)
    mig = root / "migrations"
    mig.mkdir()
    for name, text in files.items():
        (mig / name).write_text(text, encoding="utf-8")
    return root, mig


def rel_set(g, relation):
    return {(e["source"], e["target"]) for e in g["edges"] if e["relation"] == relation}


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root, self.mig = project(self.tmp.name, {"001_init.sql": M1, "002_more.sql": M2})
        self.g = sg.build_graph(self.root, [self.mig])
        self.nodes = {n["id"]: n for n in self.g["nodes"]}

    def test_final_state_columns(self):
        n = self.nodes
        self.assertNotIn("db:column:customers.legacy", n)
        self.assertNotIn("db:column:customers.phone", n)
        self.assertIn("db:column:customers.mobile", n)
        self.assertIn("db:column:customers.email", n)
        self.assertTrue(n["db:column:orders.status"]["nullable"] is False)
        self.assertEqual(n["db:column:orders.total"]["data_type"], "numeric(12,2)")
        self.assertEqual(n["db:column:orders.total"]["default"], "0")
        self.assertTrue(n["db:column:orders.id"]["is_pk"])
        self.assertTrue(n["db:column:customers.id"]["is_pk"])

    def test_fk_inline_and_alter(self):
        self.assertIn(("db:table:orders", "db:table:customers"), rel_set(self.g, "fk"))
        self.assertIn(("db:table:order_lines", "db:table:orders"), rel_set(self.g, "fk"))
        cols = rel_set(self.g, "fk_col")
        self.assertIn(("db:column:orders.customer_id", "db:column:customers.id"), cols)
        self.assertIn(("db:column:order_lines.order_id", "db:column:orders.id"), cols)
        self.assertTrue(self.nodes["db:column:orders.customer_id"]["is_fk"])
        self.assertEqual(self.nodes["db:column:order_lines.order_id"]["purpose"], "Reference to orders.id")

    def test_comments_and_purpose(self):
        t = self.nodes["db:column:orders.total"]
        self.assertEqual((t["purpose"], t["purpose_source"]), ("Order total, tax included", "comment"))
        self.assertEqual(self.nodes["db:table:orders"]["purpose_source"], "comment")
        self.assertEqual(self.nodes["db:column:customers.email"]["purpose_source"], "comment")
        self.assertEqual(self.nodes["db:column:customers.CreateDate"]["purpose_source"], "inferred_rule")
        self.assertEqual(self.nodes["db:column:order_lines.qty"]["purpose"], "Quantity")
        self.assertEqual(self.nodes["db:column:orders.is_paid"]["purpose_source"], "inferred_rule")
        self.assertEqual(self.nodes["db:column:order_lines.sku"]["purpose_source"], "none")

    def test_index_edges(self):
        self.assertEqual(self.nodes["db:index:idx_orders_cust"]["type"], "index")
        self.assertIn(("db:index:idx_orders_cust", "db:table:orders"), rel_set(self.g, "pertenece_a"))
        self.assertEqual(rel_set(self.g, "idx_col") & {("db:index:idx_orders_cust", "db:column:orders.status"),
                                                       ("db:index:idx_orders_cust", "db:column:orders.customer_id")},
                         {("db:index:idx_orders_cust", "db:column:orders.status"),
                          ("db:index:idx_orders_cust", "db:column:orders.customer_id")})

    def test_function_edges(self):
        f = self.nodes["db:function:add_line"]
        self.assertEqual(f["language"], "plpgsql")
        self.assertEqual(f["signatures"], ["p_order int, p_sku text"])
        ops = {(e["target"], e["relation"], e.get("op")) for e in self.g["edges"] if e["source"] == "db:function:add_line"}
        self.assertIn(("db:table:order_lines", "escribe", "INSERT"), ops)
        self.assertIn(("db:table:orders", "escribe", "UPDATE"), ops)
        self.assertNotIn(("db:table:customers", "escribe", "DELETE"), ops)  # comment ignored
        self.assertIn(("db:column:order_lines.sku", "escribe_col", None), ops)
        self.assertIn(("db:column:orders.total", "escribe_col", None), ops)
        self.assertIn(("db:column:orders.id", "lee_col", None), ops)
        self.assertIn(("db:function:touch_order", "llama", None), ops)

    def test_dynamic_function(self):
        d = self.nodes["db:function:dyn"]
        self.assertFalse(d["analyzed"])
        self.assertIn("EXECUTE", d["analysis_reason"])
        self.assertIn(("db:function:dyn", "db:table:customers"), rel_set(self.g, "lee"))
        self.assertTrue(self.nodes["db:function:add_line"]["analyzed"])
        self.assertEqual(self.g["meta"]["coverage"]["funcs_analyzed_pct"], 66.7)

    def test_view_alias_join(self):
        cols = {t for s, t in rel_set(self.g, "usa_col") if s == "db:view:v_orders"}
        self.assertTrue({"db:column:customers.name", "db:column:orders.total", "db:column:customers.id",
                         "db:column:orders.customer_id"} <= cols)

    def test_trigger(self):
        self.assertIn(("db:table:orders", "db:function:touch_order"), rel_set(self.g, "dispara_trigger"))

    def test_malformed_skipped_and_meta(self):
        self.assertEqual(self.g["meta"]["skipped_statements"], 1)
        self.assertNotIn("db:table:broken", self.nodes)
        cov = self.g["meta"]["coverage"]
        self.assertGreater(cov["cols_total"], 10)
        self.assertGreater(cov["cols_with_purpose_pct"], 50)

    def test_edges_reference_existing_nodes(self):
        for e in self.g["edges"]:
            self.assertIn(e["source"], self.nodes)
            self.assertIn(e["target"], self.nodes)
            self.assertIn(e["confidence"], ("EXTRACTED", "INFERRED"))

    def test_source_location(self):
        n = self.nodes["db:table:customers"]
        self.assertEqual((n["source_file"], n["source_location"]), ("migrations/001_init.sql", "2"))


class SplitterTests(unittest.TestCase):
    def test_dollar_quote_and_strings(self):
        sql = "SELECT 'a;b'; -- c;d\nCREATE FUNCTION f() RETURNS int AS $x$ BEGIN; END; $x$ LANGUAGE sql; /* ; */ SELECT 2;"
        stmts = sg.split_statements(sql)
        self.assertEqual(len(stmts), 3)
        self.assertIn("BEGIN; END;", stmts[1][0])
        self.assertEqual(stmts[1][1], 2)

    def test_drop_and_rename_table(self):
        with TemporaryDirectory() as tmp:
            root, mig = project(tmp, {"1.sql": 'CREATE TABLE "Old" (id int PRIMARY KEY);\nCREATE TABLE gone (x int);\n'
                                               "ALTER TABLE gone RENAME TO gone2;\nDROP TABLE gone2;\n"
                                               'ALTER TABLE "Old" RENAME TO fresh;\n'})
            g = sg.build_graph(root, [mig])
            ids = {n["id"] for n in g["nodes"]}
            self.assertIn("db:table:fresh", ids)
            self.assertNotIn("db:table:gone2", ids)
            self.assertNotIn("db:table:Old", ids)

    def test_undecodable_file_does_not_crash(self):
        with TemporaryDirectory() as tmp:
            root, mig = project(tmp, {})
            (mig / "1.sql").write_bytes(b"CREATE TABLE t (id int); -- caf\xe9 \xff\n")
            g = sg.build_graph(root, [mig])
            self.assertEqual(g["meta"]["tables"], 1)


class CliTests(unittest.TestCase):
    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = sg.main(argv)
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def test_cli_deterministic_and_atomic(self):
        with TemporaryDirectory() as tmp:
            root, mig = project(tmp, {"001.sql": M1, "002.sql": M2})
            out = Path(tmp) / "out" / "graph.json"
            code, so, _ = self.run_cli(["--root", str(root), "--out", str(out), str(mig)])
            self.assertEqual(code, 0)
            self.assertIn("coverage:", so)
            first = out.read_bytes()
            self.assertFalse(out.with_name("graph.json.tmp").exists())
            self.assertEqual(self.run_cli(["--root", str(root), "--out", str(out), str(mig / "001.sql"), str(mig / "002.sql")])[0], 0)
            self.assertEqual(out.read_bytes(), first)
            data = json.loads(first)
            self.assertEqual(set(data), {"meta", "nodes", "edges"})

    def test_cli_bad_args(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(self.run_cli([])[0], 2)
            self.assertEqual(self.run_cli(["--root", tmp, "--out", str(Path(tmp) / "o.json")])[0], 2)
            code, _, err = self.run_cli(["--root", tmp, "--out", str(Path(tmp) / "o.json"), str(Path(tmp) / "nope")])
            self.assertEqual(code, 2)
            self.assertFalse((Path(tmp) / "o.json").exists())


if __name__ == "__main__":
    unittest.main()
