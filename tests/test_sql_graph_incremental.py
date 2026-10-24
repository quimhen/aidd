"""Spec 004 amendment (FR-028, FR-029, FR-030): tests of sql_graph.py (no-raise, schema replay, dml cache).

Synthetic migrations are written to a temp dir; the CLI is run as a subprocess (timeout 60 s).
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "skill" / "scripts" / "sql_graph.py"

M001 = """create table oinv(id int primary key, qty int not null, wh text references owhs(code));
create table owhs(code text primary key, name text);
create index oinv_wh_idx on oinv(wh);
comment on column oinv.qty is 'On hand';
alter table oinv add column lot text;
"""
M002 = "create view oitw as select i.id, i.qty, w.name from oinv i join owhs w on w.code = i.wh;\n"
M003 = """create or replace function helper() returns int language sql as $$ select count(*) from owhs $$;
create or replace function post_stock() returns trigger language plpgsql as $$
begin
  update oinv set qty = qty + 1 where id = new.id;
  insert into owhs(code, name) values ('a', 'b');
  perform helper();
  return new;
end $$;
create trigger trg_post after insert on oinv for each row execute function post_stock();
"""
M_ALIAS = """create or replace function lock_stock() returns void language plpgsql as $$
begin
  update oitw set qty = 1 from oinv where oitw.id = oinv.id;
  merge into oitw using owhs on oitw.id = owhs.code when matched then update set qty = 2;
  select name from owhs;
end $$;
"""
M_APPEND = "create table extra_t(id int primary key, note text);\n"
M_ALTER = "alter table oinv add column extra_col int;\n"


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name)
        self.mig = self.root / "migrations"
        self.mig.mkdir()
        self.out = self.root / "out" / "g.json"

    def put(self, name, text):
        (self.mig / name).write_text(text, encoding="utf-8", newline="\n")

    def base(self):
        self.put("001_init.sql", M001)
        self.put("002_view.sql", M002)
        self.put("003_func.sql", M003)

    def run_cli(self, *extra, out=None, expect=0):
        out = out or self.out
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), "--out", str(out),
                            *extra, str(self.mig)],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, expect, p.stdout + p.stderr)
        return p.stdout

    def load(self, out=None):
        return json.loads((out or self.out).read_text(encoding="utf-8"))

    def ck(self):
        p = Path(str(self.out) + ".ckpt.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def cache(self):
        p = Path(str(self.out) + ".dml.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def edges(g):
        return {(e["source"], e["target"], e["relation"], e.get("op", "")) for e in g["edges"]}


class TestAliasNoRaise(Base):  # AC-021 / FR-028
    def test_alias_view_as_update_and_merge_target(self):
        self.base()
        self.put("004_alias.sql", M_ALIAS)
        self.run_cli()
        g = self.load()
        self.assertGreater(g["meta"]["skipped_statements"], 0)
        ids = {n["id"] for n in g["nodes"]}
        self.assertIn("db:table:oinv", ids)
        self.assertIn("db:table:owhs", ids)
        self.assertIn("db:function:post_stock", ids)
        self.assertIn("db:function:lock_stock", ids)
        escribe = [e for e in g["edges"] if e["relation"] == "escribe"]
        self.assertTrue(escribe)
        self.assertIn(("db:function:post_stock", "db:table:oinv"), {(e["source"], e["target"]) for e in escribe})

    def test_alias_in_every_kind(self):
        self.base()
        self.put("004_alias.sql", M_ALIAS)
        for kind in ("all", "schema", "dml"):
            self.run_cli("--kind", kind, out=self.root / f"{kind}.json")
            g = self.load(self.root / f"{kind}.json")
            self.assertGreaterEqual(g["meta"]["skipped_statements"], 0)
            self.assertTrue(g["nodes"])


class TestKindAllUnchanged(Base):  # default output
    def test_all_equals_schema_plus_dml(self):
        self.base()
        self.put("004_alias.sql", M_ALIAS)
        self.run_cli(out=self.root / "all.json")
        self.run_cli("--kind", "all", out=self.root / "all2.json")
        self.run_cli("--kind", "schema", out=self.root / "s.json")
        self.run_cli("--kind", "dml", out=self.root / "d.json")
        a, a2 = self.load(self.root / "all.json"), self.load(self.root / "all2.json")
        s, d = self.load(self.root / "s.json"), self.load(self.root / "d.json")
        self.assertEqual(a, a2)  # default kind is all
        self.assertEqual(a["meta"]["kind"], "db-schema")
        self.assertEqual(s["meta"]["kind"], "db-schema")
        self.assertEqual(d["meta"]["kind"], "db-dml")
        self.assertEqual(self.edges(a), self.edges(s) | self.edges(d))
        self.assertEqual({n["id"] for n in a["nodes"]}, {n["id"] for n in s["nodes"]} | {n["id"] for n in d["nodes"]})

    def test_all_writes_no_side_files_by_default(self):
        self.base()
        self.run_cli()
        self.assertFalse(self.ck().exists())
        self.assertFalse(self.cache().exists())


class TestSchemaCheckpoint(Base):  # AC-022 / FR-029
    def test_first_run_full_replay_then_nothing_to_replay(self):
        self.base()
        out1 = self.run_cli("--kind", "schema")
        self.assertIn("db-schema: full replay (no checkpoint)", out1)
        self.assertTrue(self.ck().is_file())
        out2 = self.run_cli("--kind", "schema")
        self.assertIn("db-schema: replayed 0 of 3 migrations", out2)

    def test_appended_migration_replays_one_and_matches_fresh(self):
        self.base()
        self.run_cli("--kind", "schema")
        self.put("004_extra.sql", M_APPEND)
        out = self.run_cli("--kind", "schema")
        self.assertIn("db-schema: replayed 1 of 4 migrations", out)
        resumed = self.out.read_bytes()
        fresh_out = self.root / "fresh" / "g.json"
        out_f = self.run_cli("--kind", "schema", out=fresh_out)
        self.assertIn("db-schema: full replay (no checkpoint)", out_f)
        self.assertEqual(resumed, fresh_out.read_bytes())
        self.assertIn("db:table:extra_t", {n["id"] for n in self.load()["nodes"]})

    def test_edited_old_migration_forces_full_replay(self):
        self.base()
        self.run_cli("--kind", "schema")
        self.put("001_init.sql", M001 + "alter table owhs add column region text;\n")
        out = self.run_cli("--kind", "schema")
        self.assertRegex(out, r"db-schema: full replay \(changed (?:.*[/\\])?001_init\.sql\)")
        self.assertIn("db:column:owhs.region", {n["id"] for n in self.load()["nodes"]})

    def test_removed_or_renamed_migration_forces_full_replay(self):
        self.base()
        self.run_cli("--kind", "schema")
        (self.mig / "002_view.sql").rename(self.mig / "002_view_renamed.sql")
        out = self.run_cli("--kind", "schema")
        self.assertRegex(out, r"db-schema: full replay \((removed|changed) ")

    def test_removed_migration_says_removed(self):
        self.base()
        self.run_cli("--kind", "schema")
        (self.mig / "003_func.sql").unlink()
        out = self.run_cli("--kind", "schema")
        self.assertRegex(out, r"db-schema: full replay \(removed (?:.*[/\\])?003_func\.sql\)")

    def test_explicit_checkpoint_path_in_kind_all(self):
        self.base()
        ck = self.root / "my.ck"
        self.run_cli("--checkpoint", str(ck))
        self.assertTrue(ck.is_file())
        out = self.run_cli("--checkpoint", str(ck))
        self.assertIn("replayed 0 of 3 migrations", out)


class TestDmlCache(Base):  # FR-030
    @staticmethod
    def counts(out):
        m = re.search(r"db-dml: analysed (\d+) bodies, reused (\d+)", out)
        assert m, out
        return int(m.group(1)), int(m.group(2))

    def test_first_run_analyses_all_rerun_reuses_all(self):
        self.base()
        a1, r1 = self.counts(self.run_cli("--kind", "dml"))
        self.assertGreater(a1, 0)
        self.assertEqual(r1, 0)
        first = self.out.read_bytes()
        a2, r2 = self.counts(self.run_cli("--kind", "dml"))
        self.assertEqual((a2, r2), (0, a1))
        self.assertEqual(first, self.out.read_bytes())

    def test_table_change_reanalyses_only_bodies_touching_it(self):
        self.base()
        total, _ = self.counts(self.run_cli("--kind", "dml"))
        self.put("004_alter.sql", M_ALTER)  # touches oinv; helper() only reads owhs
        a, r = self.counts(self.run_cli("--kind", "dml"))
        self.assertGreaterEqual(a, 1)
        self.assertGreaterEqual(r, 1)  # helper's body is reused
        self.assertEqual(a + r, total)
        # same graph as a fresh build without cache
        fresh = self.root / "fresh" / "d.json"
        self.run_cli("--kind", "dml", out=fresh)
        self.assertEqual(self.out.read_bytes(), fresh.read_bytes())

    def test_explicit_cache_path(self):
        self.base()
        c = self.root / "my.cache.json"
        self.run_cli("--kind", "dml", "--cache", str(c))
        self.assertTrue(c.is_file())
        a, r = self.counts(self.run_cli("--kind", "dml", "--cache", str(c)))
        self.assertEqual(a, 0)
        self.assertGreater(r, 0)


class TestCorruptState(Base):  # never raises
    GARBAGE = ["not json at all {{{", "[]", "null", '{"version": 1}', '{"prefix": 5, "key": 1, "state": []}', ""]

    def test_corrupt_checkpoint_forces_full_replay(self):
        self.base()
        self.run_cli("--kind", "schema")
        good = self.out.read_bytes()
        for junk in self.GARBAGE:
            self.ck().write_text(junk, encoding="utf-8")
            out = self.run_cli("--kind", "schema")
            self.assertIn("db-schema: full replay (", out, junk)
            self.assertEqual(good, self.out.read_bytes(), junk)

    def test_garbage_checkpoint_reports_unreadable(self):
        self.base()
        self.ck().write_text("garbage", encoding="utf-8")
        out = self.run_cli("--kind", "schema")
        self.assertIn("db-schema: full replay (checkpoint unreadable", out)

    def test_corrupt_cache_never_raises(self):
        self.base()
        self.run_cli("--kind", "dml")
        good = self.out.read_bytes()
        for junk in self.GARBAGE + ['{"version": 1, "entries": {"x": 5}}', '{"entries": []}']:
            self.cache().write_text(junk, encoding="utf-8")
            self.run_cli("--kind", "dml")
            self.assertEqual(good, self.out.read_bytes(), junk)

    def test_corrupt_cache_entries_with_valid_header_never_raise(self):
        self.base()
        self.run_cli("--kind", "dml")
        doc = json.loads(self.cache().read_text(encoding="utf-8"))
        doc["entries"] = {h: {"ids": 5, "schema": None, "result": "bad"} for h in doc["entries"]}
        self.cache().write_text(json.dumps(doc), encoding="utf-8")
        good_out = self.root / "ref.json"
        self.run_cli("--kind", "dml", out=good_out)
        self.run_cli("--kind", "dml")
        self.assertEqual(self.load()["edges"], self.load(good_out)["edges"])


if __name__ == "__main__":
    unittest.main()
