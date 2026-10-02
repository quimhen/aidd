"""Tests for scripts/aidd_memory.py -- stdlib unittest, no dependencies.

Run: python -m unittest tests.test_aidd_memory -v
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import aidd_memory as am  # noqa: E402

SCRIPT = SCRIPTS_DIR / "aidd_memory.py"


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self._old_env = os.environ.pop("AIDD_MEMORY_DIR", None)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        os.environ.pop("AIDD_MEMORY_DIR", None)
        if self._old_env is not None:
            os.environ["AIDD_MEMORY_DIR"] = self._old_env

    def add(self, title, **kw):
        kw.setdefault("type", "decision")
        kw.setdefault("date", "2026-10-01")
        return am.add_entry(self.root, title=title, **kw)


class TestFormat(Base):
    def test_round_trip_and_header(self):
        eid = self.add("Flows use TOON", why="User asked", codes=["US-001", "CTL-004"],
                       files=["skill/scripts/flowmap.py"])
        text = (self.root / ".aidd" / "memory" / "project.toon").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("version: 1\nmemory: project\nentries[*]{"))
        e = am.load_entries(self.root)[0]
        self.assertEqual(e["id"], eid)
        self.assertEqual(e["codes"], ["US-001", "CTL-004"])
        self.assertEqual(e["files"], ["skill/scripts/flowmap.py"])
        self.assertEqual(e["scope"], "project")

    def test_reads_star_and_n_without_enforcing_count(self):
        d = self.root / ".aidd" / "memory"
        d.mkdir(parents=True)
        row = "  m-00000001,2026-01-01,decision,T,,,w,,agent\n"
        (d / "a.toon").write_text("version: 1\nmemory: a\nentries[*]{id,date,type,title,codes,files,why,supersedes,source}:\n" + row, encoding="utf-8")
        row2 = row.replace("m-00000001", "m-00000002")
        (d / "b.toon").write_text("version: 1\nmemory: b\nentries[99]{id,date,type,title,codes,files,why,supersedes,source}:\n" + row2, encoding="utf-8")
        ids = {e["id"] for e in am.load_entries(self.root)}
        self.assertEqual(ids, {"m-00000001", "m-00000002"})

    def test_csv_quoting_commas_quotes_accents(self):
        title = 'Decisión: "usar" comas, ñandú'
        why = 'Porque sí, "claro"; acción'
        self.add(title, why=why)
        raw = (self.root / ".aidd" / "memory" / "project.toon").read_text(encoding="utf-8")
        self.assertEqual(len([l for l in raw.split("\n") if l.startswith("  ")]), 1)
        e = am.load_entries(self.root)[0]
        self.assertEqual(e["title"], title)
        self.assertEqual(e["why"], why)

    def test_newlines_flattened_one_line_per_entry(self):
        self.add("T", why="line1\nline2\r\nline3")
        raw = (self.root / ".aidd" / "memory" / "project.toon").read_text(encoding="utf-8")
        self.assertEqual(len([l for l in raw.split("\n") if l.startswith("  ")]), 1)
        self.assertEqual(am.load_entries(self.root)[0]["why"], "line1 / line2 / line3")

    def test_truncation(self):
        self.add("x" * 300, why="y" * 900)
        e = am.load_entries(self.root)[0]
        self.assertEqual(len(e["title"]), 120)
        self.assertTrue(e["title"].endswith("…"))
        self.assertEqual(len(e["why"]), 400)
        self.assertTrue(e["why"].endswith("…"))

    def test_corrupt_rows_skipped_with_warning(self):
        self.add("Good one")
        p = self.root / ".aidd" / "memory" / "project.toon"
        with open(p, "a", encoding="utf-8") as f:
            f.write('  garbage,only,three\n  "unterminated,quote\n')
        import io
        import contextlib
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            hits = am.search(self.root, "good")
        self.assertEqual(len(hits), 1)
        self.assertIn("skipped malformed row", err.getvalue())


class TestIdsAndValidation(Base):
    def test_id_deterministic_and_dedupe(self):
        self.assertEqual(am.make_id("project", "2026-10-01", "T"), am.make_id("project", "2026-10-01", "T"))
        self.assertTrue(am.make_id("p", "2026-10-01", "T").startswith("m-"))
        a = self.add("Same")
        b = self.add("Same")
        self.assertEqual(a, b)
        self.assertEqual(len(am.load_entries(self.root)), 1)
        self.assertEqual(am.append_entries(self.root, "project", [{"id": a, "date": "2026-10-01", "type": "decision", "title": "Same"}]), [])

    def test_type_validation(self):
        with self.assertRaises(ValueError):
            self.add("T", type="feature")
        with self.assertRaises(ValueError):
            self.add("T", source="robot")
        with self.assertRaises(ValueError):
            self.add("T", date="01/10/2026")
        with self.assertRaises(ValueError):
            self.add("T", scope="../evil")

    def test_date_normalised(self):
        self.add("T", date="2026-10-01T12:30:00")
        self.assertEqual(am.load_entries(self.root)[0]["date"], "2026-10-01")

    def test_env_override(self):
        other = self.root / "elsewhere"
        os.environ["AIDD_MEMORY_DIR"] = str(other)
        self.add("T")
        self.assertTrue((other / "project.toon").exists())

    def test_find_root(self):
        (self.root / ".git").mkdir()
        sub = self.root / "a" / "b"
        sub.mkdir(parents=True)
        self.assertEqual(am.find_root(sub), self.root.resolve())

    def test_merge_friendly_independent_appends(self):
        self.add("Base")
        p = self.root / ".aidd" / "memory" / "project.toon"
        base = p.read_text(encoding="utf-8")
        # two "branches" append different rows to the same base; concatenating
        # their added lines (what a git merge yields) must still load.
        am.add_entry(self.root, type="risk", title="Branch A", date="2026-10-02")
        a_rows = p.read_text(encoding="utf-8")[len(base):]
        p.write_text(base, encoding="utf-8")
        am.add_entry(self.root, type="risk", title="Branch B", date="2026-10-03")
        b_rows = p.read_text(encoding="utf-8")[len(base):]
        p.write_text(base + a_rows + b_rows, encoding="utf-8")
        titles = {e["title"] for e in am.load_entries(self.root)}
        self.assertEqual(titles, {"Base", "Branch A", "Branch B"})
        # no trailing newline in the base file must not glue rows together
        p.write_text(base.rstrip("\n"), encoding="utf-8")
        self.add("After no-newline")
        self.assertIn("After no-newline", {e["title"] for e in am.load_entries(self.root)})

    def test_scopes_are_separate_files(self):
        self.add("In spec", scope="001-aidd-memory")
        self.add("In project")
        names = sorted(p.name for p in (self.root / ".aidd" / "memory").glob("*.toon"))
        self.assertEqual(names, ["001-aidd-memory.toon", "project.toon"])


class TestSearch(Base):
    def test_exact_code_beats_text(self):
        self.add("Login screen needs SCREEN-08 discussion text", codes=["SCREEN-01"])
        target = self.add("Unrelated wording entirely", codes=["SCREEN-08"])
        hits = am.search(self.root, "SCREEN-08")
        self.assertEqual(hits[0]["id"], target)

    def test_spanish_accent_and_plural(self):
        eid = self.add("Decisión sobre los botones de pago", why="Los usuarios necesitan confirmación")
        self.add("Something else about databases")
        for q in ("decisiones botón", "boton", "confirmacion usuario", "BOTONES"):
            hits = am.search(self.root, q)
            self.assertTrue(hits and hits[0]["id"] == eid, q)

    def test_stopword_only_query_returns_nothing(self):
        self.add("Hello world")
        self.assertEqual(am.search(self.root, "the de la"), [])

    def test_ranking_title_over_why(self):
        t = self.add("Pagination strategy", why="misc")
        self.add("Other thing", why="pagination pagination mentioned in passing")
        self.assertEqual(am.search(self.root, "pagination")[0]["id"], t)

    def test_filters(self):
        a = self.add("Cache invalidation", type="bugfix", codes=["API-001"], files=["src/cache.py"], scope="s1")
        self.add("Cache warmup", type="decision", codes=["API-002"], files=["src/warm.py"], scope="s2")
        self.assertEqual([e["id"] for e in am.search(self.root, "cache", type="bugfix")], [a])
        self.assertEqual([e["id"] for e in am.search(self.root, "cache", code="api-001")], [a])
        self.assertEqual([e["id"] for e in am.search(self.root, "cache", file="src\\cache.py")], [a])
        self.assertEqual([e["id"] for e in am.search(self.root, "cache", scope="s1")], [a])
        self.assertEqual(am.search(self.root, "cache", type="risk"), [])

    def test_newer_wins_ties(self):
        old = self.add("Same words here", date="2026-01-01", scope="a")
        new = self.add("Same words here", date="2026-06-01", scope="b")
        self.assertEqual([e["id"] for e in am.search(self.root, "words")], [new, old])

    def test_limit_and_empty_query_recent(self):
        for i in range(5):
            self.add(f"Item {i}", date=f"2026-01-0{i + 1}")
        hits = am.search(self.root, "", limit=2)
        self.assertEqual([e["title"] for e in hits], ["Item 4", "Item 3"])

    def test_supersede_hides_but_show_finds(self):
        old = self.add("Use JSON for flows", date="2026-09-01")
        new = self.add("Use TOON for flows", supersedes=old, date="2026-10-01")
        ids = [e["id"] for e in am.search(self.root, "flows")]
        self.assertEqual(ids, [new])
        shown = am.show(self.root, [old])
        self.assertEqual(len(shown), 1)
        self.assertEqual(shown[0]["superseded_by"], [new])
        self.assertNotIn(old, am.inject_text(self.root))

    def test_show_and_timeline_and_file(self):
        ids = [self.add(f"Entry {i}", date=f"2026-02-0{i + 1}", files=["a/b.py"]) for i in range(6)]
        tl = am.timeline(self.root, ids[3], window=1)
        self.assertEqual([e["id"] for e in tl], ids[2:5])
        self.assertEqual([e["id"] for e in am.entries_for_file(self.root, "a/b.py", limit=2)], [ids[5], ids[4]])
        self.assertEqual(am.show(self.root, ["m-nope0000"]), [])


class TestCompact(Base):
    def test_dry_run_then_apply_no_row_lost(self):
        old = self.add("Old decision", date="2025-02-10", codes=["US-009"])
        self.add("Replacement", supersedes=old, date="2026-10-01")
        self.add("Ancient but live", date="2024-11-05")
        self.add("Recent", date="2026-09-30")
        before = {e["id"] for e in am.load_entries(self.root)}
        p = self.root / ".aidd" / "memory" / "project.toon"
        snap = p.read_text(encoding="utf-8")

        r = am.compact(self.root, before="2025-01-01")
        self.assertTrue(r["dry_run"])
        self.assertEqual(r["moved"], 2)
        self.assertEqual(r["superseded"], 1)
        self.assertEqual(p.read_text(encoding="utf-8"), snap)
        self.assertFalse((self.root / ".aidd" / "memory" / "archive").exists())

        r = am.compact(self.root, before="2025-01-01", apply=True)
        self.assertEqual(r["moved"], 2)
        self.assertEqual(sorted(r["files"]), ["archive/2024-Q4.toon", "archive/2025-Q1.toon"])
        active = {e["id"] for e in am.load_entries(self.root)}
        everything = {e["id"] for e in am.load_entries(self.root, include_archive=True)}
        self.assertEqual(everything, before)
        self.assertEqual(len(active), 2)
        self.assertTrue(am.search(self.root, "ancient") == [])
        self.assertEqual(len(am.search(self.root, "ancient", include_archive=True)), 1)
        self.assertEqual(len(am.search(self.root, "old decision", include_archive=True)), 1)
        # scope survives in the archive; show still finds archived rows
        self.assertEqual(am.show(self.root, [old])[0]["scope"], "project")
        # idempotent
        self.assertEqual(am.compact(self.root, before="2025-01-01", apply=True)["moved"], 0)

    def test_compact_keeps_unparseable_lines(self):
        old = self.add("Old", date="2020-01-01")
        p = self.root / ".aidd" / "memory" / "project.toon"
        with open(p, "a", encoding="utf-8") as f:
            f.write("  hand,edited,junk\n")
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()):
            am.compact(self.root, before="2021-01-01", apply=True)
        self.assertIn("hand,edited,junk", p.read_text(encoding="utf-8"))
        self.assertEqual(am.show(self.root, [old])[0]["archived"], True)


class TestInject(Base):
    def test_empty(self):
        self.assertEqual(am.inject_text(self.root), "")
        self.assertEqual(am.file_context_text(self.root, "x.py"), "")

    def test_inject_shape_and_filter(self):
        for i in range(8):
            self.add(f"Decision number {i}", date=f"2026-03-0{i + 1}")
        self.add("A bugfix", type="bugfix", date="2026-04-01")
        txt = am.inject_text(self.root)
        lines = txt.split("\n")
        self.assertEqual(lines[0], "AIDD memory — 9 entries.")
        self.assertEqual(len(lines), 1 + 5 + 1)
        self.assertIn("Decision number 7", lines[1])
        self.assertNotIn("A bugfix", txt)
        self.assertTrue(lines[-1].startswith("Search: aidd mem search"))

    def test_inject_cap_cuts_whole_lines(self):
        for i in range(5):
            self.add(f"Decision with a fairly long title number {i}", date=f"2026-03-0{i + 1}")
        txt = am.inject_text(self.root, max_chars=120)
        self.assertLessEqual(len(txt), 120)
        for line in txt.split("\n")[1:]:
            self.assertTrue(line.startswith("m-") or line.startswith("Search:"))

    def test_file_context(self):
        for i in range(5):
            self.add(f"Touches file {i}", files=["src/x.py"], date=f"2026-05-0{i + 1}")
        txt = am.file_context_text(self.root, "src/x.py")
        lines = txt.split("\n")
        self.assertEqual(lines[0], "AIDD memory for src/x.py:")
        self.assertEqual(len(lines), 4)
        capped = am.file_context_text(self.root, "src/x.py", max_chars=70)
        self.assertLessEqual(len(capped), 70)
        self.assertEqual(am.file_context_text(self.root, "other.py"), "")

    def test_stats(self):
        self.add("A", type="risk")
        self.add("B", type="bugfix", scope="s")
        st = am.stats(self.root)
        self.assertEqual(st["entries"], 2)
        self.assertEqual(st["by_type"], {"risk": 1, "bugfix": 1})
        self.assertEqual(st["by_scope"], {"project": 1, "s": 1})
        self.assertGreater(st["bytes"], 0)


class TestCLI(Base):
    def run_cli(self, *args):
        env = dict(os.environ)
        env.pop("AIDD_MEMORY_DIR", None)
        env["PYTHONIOENCODING"] = "utf-8"
        r = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), *args],
                           capture_output=True, encoding="utf-8", env=env)
        return r.returncode, r.stdout, r.stderr

    def test_end_to_end(self):
        rc, out, _ = self.run_cli("add", "--type", "decision", "--title", "Usar TOON, no JSON",
                                  "--why", "Pidió el usuario", "--codes", "US-001,CTL-004",
                                  "--files", "skill/scripts/flowmap.py", "--date", "2026-10-01")
        self.assertEqual(rc, 0)
        eid = out.strip()
        self.assertRegex(eid, r"^m-[0-9a-f]{8}$")

        rc, out, _ = self.run_cli("search", "toon", "--code", "us-001")
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), f"{eid}  2026-10-01  decision  [US-001,CTL-004]  Usar TOON, no JSON")
        self.assertNotIn("Pidió", out)

        rc, out, _ = self.run_cli("search", "--json", "CTL-004")
        self.assertEqual(json.loads(out)[0]["id"], eid)
        self.assertNotIn("why", json.loads(out)[0])

        rc, out, _ = self.run_cli("show", eid)
        self.assertEqual(rc, 0)
        self.assertIn("Pidió el usuario", out)
        rc, out, _ = self.run_cli("show", eid, "--json")
        self.assertEqual(json.loads(out)[0]["files"], ["skill/scripts/flowmap.py"])

        rc, out, _ = self.run_cli("file", "skill/scripts/flowmap.py")
        self.assertEqual(rc, 0)
        self.assertIn(eid, out)
        rc, out, _ = self.run_cli("timeline", eid)
        self.assertEqual(rc, 0)
        rc, out, _ = self.run_cli("inject")
        self.assertIn("AIDD memory — 1 entries.", out)
        rc, out, _ = self.run_cli("inject", "--file", "skill/scripts/flowmap.py")
        self.assertIn("AIDD memory for skill/scripts/flowmap.py:", out)
        rc, out, _ = self.run_cli("compact")
        self.assertIn("dry-run", out)
        rc, out, _ = self.run_cli("compact", "--before", "2027-01-01", "--apply")
        self.assertIn("moved=1", out)
        rc, out, _ = self.run_cli("search", "toon", "--archive")
        self.assertEqual(rc, 0)
        rc, out, _ = self.run_cli("stats")
        self.assertEqual(rc, 0)
        self.assertIn("entries: 1", out)

    def test_exit_codes(self):
        self.assertEqual(self.run_cli("add", "--type", "nope", "--title", "x")[0], 1)
        self.assertEqual(self.run_cli("add", "--title", "x")[0], 1)  # missing --type
        self.assertEqual(self.run_cli("search", "zzz")[0], 2)
        self.assertEqual(self.run_cli("show", "m-00000000")[0], 2)
        self.assertEqual(self.run_cli("file", "nothing.py")[0], 2)
        self.assertEqual(self.run_cli("inject")[0], 0)
        self.assertEqual(self.run_cli()[0], 1)

    def test_import_dispatcher_without_module_is_clean_error(self):
        rc, _, err = self.run_cli("import-claude-mem", "nope.db", "--project", "x")
        if (SCRIPTS_DIR / "aidd_memory_import.py").exists():
            self.assertIn(rc, (0, 1))
        else:
            self.assertEqual(rc, 1)
            self.assertIn("aidd_memory_import", err)


# ---------------------------------------------------------------------------
# Regression tests for the independent-audit amendments (spec, Rev 1)
# ---------------------------------------------------------------------------

import contextlib  # noqa: E402
import io  # noqa: E402
import random  # noqa: E402


class TestStemming(Base):
    def test_stem_groups_collapse(self):
        groups = [("table", "tables"), ("use", "used", "using", "uses"), ("file", "files"),
                  ("rule", "rules"), ("base", "bases"), ("decision", "decisiones"),
                  ("regla", "reglas"), ("cache", "cached", "caching", "caches"),
                  ("store", "stored", "storing", "stores")]
        for g in groups:
            self.assertEqual(len({am.tokenize(w)[0] for w in g}), 1, g)

    def test_search_matches_across_forms(self):
        t = self.add("Database table schema")
        u = self.add("Use a retry wrapper")
        f = self.add("Rule files live in rules dir")
        b = self.add("Bases de datos")
        for q, want in (("tables", t), ("table", t), ("used", u), ("using", u), ("use", u),
                        ("file", f), ("files", f), ("rule", f), ("base", b), ("bases", b)):
            hits = am.search(self.root, q)
            self.assertTrue(hits and hits[0]["id"] == want, q)

    def test_spanish_and_accent_folding_still_work(self):
        eid = self.add("Decisión: reglas de validación")
        for q in ("decisiones", "decision", "regla", "reglas", "validacion", "VALIDACIÓN"):
            hits = am.search(self.root, q)
            self.assertTrue(hits and hits[0]["id"] == eid, q)


class TestCache(Base):
    def setUp(self):
        super().setUp()
        for i in range(30):
            self.add(f"Cache item number {i} about tables", why="rule files", date=f"2026-01-{i % 28 + 1:02d}",
                     codes=[f"API-{i:03d}"], files=[f"src/mod{i}.py"], scope="a" if i % 2 else "project")
        self.cdir = self.root / ".aidd" / "memory" / ".cache"

    def test_cache_written_gitignored_and_reused(self):
        am.search(self.root, "tables")
        self.assertTrue((self.cdir / "rows.bin").is_file())
        self.assertTrue((self.cdir / "index.bin").is_file())
        self.assertEqual((self.cdir / ".gitignore").read_text(encoding="utf-8").strip(), "*")
        calls = []
        orig = am._build_rows
        am._build_rows = lambda *a, **k: calls.append(1) or orig(*a, **k)
        self.addCleanup(setattr, am, "_build_rows", orig)
        am.search(self.root, "tables")
        self.assertEqual(calls, [])  # served from cache

    def test_cache_invalidates_on_change(self):
        before = am.search(self.root, "zebra")
        self.assertEqual(before, [])
        eid = self.add("Zebra crossing decision")
        hits = am.search(self.root, "zebra")
        self.assertEqual([e["id"] for e in hits], [eid])

    def test_corrupt_cache_is_ignored(self):
        am.search(self.root, "tables")
        for name in ("rows.bin", "index.bin"):
            (self.cdir / name).write_bytes(b"\x00garbage not marshal")
        self.assertEqual(len(am.search(self.root, "tables", limit=5)), 5)
        self.assertTrue(am.inject_text(self.root))

    def test_unwritable_cache_dir_is_tolerated(self):
        (self.root / ".aidd" / "memory" / ".cache").write_text("i am a file", encoding="utf-8")
        self.assertEqual(len(am.search(self.root, "tables", limit=3)), 3)
        self.assertTrue(am.inject_text(self.root))

    def test_no_memory_dir_creates_nothing(self):
        empty = self.root / "empty"
        empty.mkdir()
        self.assertEqual(am.search(empty, "x"), [])
        self.assertEqual(am.inject_text(empty), "")
        self.assertFalse((empty / ".aidd").exists())

    def test_fast_path_matches_reference(self):
        rnd = random.Random(3)
        words = "table cache rule file base use decision login payment screen retry".split()
        for i in range(120):
            self.add(" ".join(rnd.choices(words, k=4)) + f" {i}", why=" ".join(rnd.choices(words, k=9)),
                     type=rnd.choice(am.TYPES), codes=[f"US-{rnd.randint(1, 9):03d}"],
                     files=[f"src/{rnd.choice(words)}.py"], scope=rnd.choice(["project", "s1", "s2"]),
                     date=f"2026-0{rnd.randint(1, 9)}-{rnd.randint(1, 28):02d}")
        old = self.add("Old thing about tables", date="2026-01-01")
        self.add("New thing about tables", supersedes=old, date="2026-02-01")
        cases = [dict(query="tables cache"), dict(query="us-003"), dict(query="rule file"),
                 dict(query="cache", type="decision"), dict(query="cache", scope="s1"),
                 dict(query="login", code="us-004"), dict(query="", limit=7),
                 dict(query="payment", file="src/retry.py"), dict(query="zzzz")]
        for kw in cases:
            q = kw.pop("query")
            kw.setdefault("limit", 10)
            fast = [e["id"] for e in am._search_fast(self.root, q, kw.get("type"), kw.get("code"),
                                                     kw.get("file"), kw.get("scope"), kw["limit"])]
            slow = [e["id"] for e in am._search_slow(self.root, q, kw.get("type"), kw.get("code"),
                                                     kw.get("file"), kw.get("scope"), kw["limit"], False)]
            self.assertEqual(fast, slow, (q, kw))
        self.assertNotIn(old, [e["id"] for e in am.search(self.root, "tables", limit=50)])


class TestScopeValidation(Base):
    def test_bad_scopes_rejected(self):
        for bad in (".", "..", ".hidden", "a/b", "a\\b", "x" * 65, "", "-lead", "sp ace", "ñandú"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                am.add_entry(self.root, type="decision", title="T", scope=bad)
        for good in ("project", "001-aidd-memory", "a.b_c-d", "x" * 64):
            am.add_entry(self.root, type="decision", title="T", scope=good)

    def test_cli_exit_1_no_traceback(self):
        for bad in ("..", "x" * 300, ".."):
            rc, out, err = TestCLI.run_cli(self, "add", "--type", "decision", "--title", "T", "--scope", bad)
            self.assertEqual(rc, 1, bad)
            self.assertNotIn("Traceback", err)
            self.assertIn("scope", err)


class TestAmendment4(Base):
    def test_supersedes_must_exist(self):
        with self.assertRaises(ValueError):
            self.add("New", supersedes="m-deadbeef")
        old = self.add("Old")
        self.add("New", supersedes=old)  # fine
        rc, out, err = TestCLI.run_cli(self, "add", "--type", "decision", "--title", "X", "--supersedes", "m-00000000")
        self.assertEqual(rc, 1)
        self.assertNotIn("Traceback", err)

    def test_inject_max_chars_zero(self):
        self.add("Decision one")
        self.assertEqual(am.inject_text(self.root, max_chars=0), "")
        rc, out, _ = TestCLI.run_cli(self, "inject", "--max-chars", "0")
        self.assertEqual((rc, out.strip()), (0, ""))
        rc, out, _ = TestCLI.run_cli(self, "inject", "--file", "a.py", "--max-chars", "0")
        self.assertEqual((rc, out.strip()), (0, ""))
        rc, out, _ = TestCLI.run_cli(self, "inject")
        self.assertIn("AIDD memory", out)

    def test_malformed_warning_once_per_process(self):
        self.add("Good")
        p = self.root / ".aidd" / "memory" / "project.toon"
        with open(p, "a", encoding="utf-8") as f:
            f.write("  only,two\n")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            am._load_all(self.root)
            am._load_all(self.root)
            am._load_all(self.root)
        self.assertEqual(err.getvalue().count("skipped malformed row"), 1)


class TestCompactSafety(Base):
    def test_comments_preserved(self):
        self.add("Old one", date="2020-01-01")
        self.add("Keep", date="2026-01-01")
        p = self.root / ".aidd" / "memory" / "project.toon"
        text = p.read_text(encoding="utf-8")
        lines = text.split("\n")
        lines.insert(3, "# hand note: keep me")
        lines.append("  # indented comment: keep too")
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        r = am.compact(self.root, before="2021-01-01", apply=True)
        self.assertEqual(r["moved"], 1)
        out = p.read_text(encoding="utf-8")
        self.assertIn("# hand note: keep me", out)
        self.assertIn("# indented comment: keep too", out)
        self.assertIn("Keep", out)
        self.assertNotIn("Old one", out)
        self.assertEqual({e["title"] for e in am.load_entries(self.root, include_archive=True)}, {"Old one", "Keep"})

    def test_conflict_markers_refuse_rewrite(self):
        self.add("Old one", date="2020-01-01", scope="bad")
        self.add("Old two", date="2020-01-02", scope="good")
        bad = self.root / ".aidd" / "memory" / "bad.toon"
        raw = bad.read_text(encoding="utf-8")
        bad.write_text(raw + "<<<<<<< HEAD\n=======\n>>>>>>> feature\n", encoding="utf-8")
        snap = bad.read_bytes()
        r = am.compact(self.root, before="2021-01-01", apply=True)
        self.assertEqual(bad.read_bytes(), snap)
        self.assertEqual(r["refused"], ["bad.toon"])
        self.assertEqual(r["moved"], 1)  # the clean file still compacts
        titles_active = {e["title"] for e in am.load_entries(self.root)}
        self.assertEqual(titles_active, {"Old one"})
        self.assertEqual(len(am.load_entries(self.root, include_archive=True)), 2)

    def test_cli_exit_1_on_refusal(self):
        self.add("Old one", date="2020-01-01")
        p = self.root / ".aidd" / "memory" / "project.toon"
        with open(p, "a", encoding="utf-8") as f:
            f.write("this is stray junk text\n")
        snap = p.read_bytes()
        rc, out, err = TestCLI.run_cli(self, "compact", "--before", "2021-01-01", "--apply")
        self.assertEqual(rc, 1)
        self.assertEqual(p.read_bytes(), snap)
        self.assertNotIn("Traceback", err)
        self.assertFalse((self.root / ".aidd" / "memory" / "archive").exists())

    def test_rerun_after_partial_failure_does_not_duplicate_archive(self):
        self.add("Old one", date="2020-01-01")
        am.compact(self.root, before="2021-01-01", apply=True)
        arch = next((self.root / ".aidd" / "memory" / "archive").glob("*.toon"))
        n = arch.read_text(encoding="utf-8").count("Old one")
        am.compact(self.root, before="2021-01-01", apply=True)
        self.assertEqual(arch.read_text(encoding="utf-8").count("Old one"), n)


class TestInjectSanitising(Base):
    def test_prefers_non_import(self):
        for i in range(6):
            self.add(f"Imported decision {i}", source="import", date=f"2026-06-0{i + 1}")
        mine = self.add("Handwritten decision", source="agent", date="2026-01-01")
        txt = am.inject_text(self.root)
        lines = txt.split("\n")
        self.assertIn(mine, lines[1])  # older but non-import wins the first slot
        self.assertEqual(len([l for l in lines if l.startswith("m-")]), 5)
        self.assertEqual(len([l for l in lines if "Imported" in l]), 4)  # imports only fill the rest

    def test_control_chars_and_line_length(self):
        p = self.root / ".aidd" / "memory"
        p.mkdir(parents=True)
        long_title = "A" * 400
        evil = "Evil\x1b[31m red\x07 bell‮ rtl"
        (p / "project.toon").write_text(
            "version: 1\nmemory: project\nentries[*]{id,date,type,title,codes,files,why,supersedes,source}:\n"
            f"  m-0000000a,2026-01-01,decision,{long_title},,,w,,agent\n"
            f'  m-0000000b,2026-01-02,decision,"{evil}",,,w,,agent\n', encoding="utf-8")
        txt = am.inject_text(self.root, max_chars=5000)
        for line in txt.split("\n"):
            self.assertLessEqual(len(line), 160)
            self.assertFalse(any(ord(c) < 32 or 127 <= ord(c) < 160 or c == "‮" for c in line), repr(line))
        self.assertIn("Evil", txt)
        self.assertNotIn("\x1b", txt)
        self.assertTrue(any(l.endswith("…") for l in txt.split("\n")))


class TestImportSqliteError(Base):
    def test_non_sqlite_file_is_clean_exit_1(self):
        if not (SCRIPTS_DIR / "aidd_memory_import.py").exists():
            self.skipTest("importer not present")
        db = self.root / "bad.db"
        db.write_bytes(b"this is definitely not a sqlite database" * 50)
        rc, out, err = TestCLI.run_cli(self, "import-claude-mem", str(db), "--project", "x")
        self.assertEqual(rc, 1)
        self.assertNotIn("Traceback", err)

    def test_dispatcher_catches_sqlite3_error(self):
        import sqlite3
        import types
        fake = types.ModuleType("aidd_memory_import")
        fake.DEFAULT_TYPES = ()

        def boom(*a, **k):
            raise sqlite3.OperationalError("unable to open database file")
        fake.import_claude_mem = boom
        old = sys.modules.get("aidd_memory_import")
        sys.modules["aidd_memory_import"] = fake
        try:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = am.main(["--root", str(self.root), "import-claude-mem", "x.db", "--project", "p"])
        finally:
            if old is None:
                sys.modules.pop("aidd_memory_import", None)
            else:
                sys.modules["aidd_memory_import"] = old
        self.assertEqual(rc, 1)
        self.assertIn("unable to open database file", err.getvalue())


class TestRev2(Base):
    def test_stem_collision_table(self):
        S = am._stem_raw
        for a, b in [("us", "use"), ("us", "used"), ("us", "using"), ("string", "str"),
                     ("mode", "mod"), ("none", "non"), ("one", "on"), ("core", "cor"),
                     ("late", "lat"), ("done", "don"), ("role", "rol"), ("side", "sid"),
                     ("thing", "th"), ("speed", "sp"), ("bring", "br"), ("pip", "pipe"),
                     ("top", "tope"), ("bar", "bare"), ("tie", "ti")]:
            self.assertNotEqual(S(a), S(b), (a, b))
        for g in [("table", "tables"), ("use", "used", "using", "uses"), ("file", "files"),
                  ("rule", "rules"), ("base", "bases"), ("cache", "cached", "caching", "caches"),
                  ("decision", "decisiones"), ("regla", "reglas"), ("query", "queries"),
                  ("policy", "policies"), ("run", "running"), ("map", "mapped", "mapping")]:
            self.assertEqual(len({S(w) for w in g}), 1, g)

    def test_reserved_scope_names(self):
        for sc in ("con", "CON", "nul", "Aux", "prn", "com1", "COM9", "lpt3", "con.txt", "nul.x.y"):
            with self.assertRaises(ValueError, msg=sc):
                self.add("x", scope=sc)
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            rc = am.main(["--root", str(self.root), "add", "--type", "decision",
                          "--title", "t", "--scope", "com1"])
        self.assertEqual(rc, 1)
        self.assertIn("invalid scope", err.getvalue())
        self.add("ok", scope="console")  # not reserved
        self.add("ok2", scope="com10")

    def test_invalid_rows_skipped_and_junk_warned(self):
        good = self.add("good entry here")
        f = am.memory_dir(self.root) / "project.toon"
        with open(f, "a", encoding="utf-8") as fh:
            fh.write("  m-bad00001,zzzz,decision,Zeta date,,,why,,agent\n")
            fh.write("  m-bad00002,2026-13-40,decision,Bad month,,,why,,agent\n")
            fh.write("  m-bad00003,2026-10-02,bogus,Bad type,,,why,,agent\n")
            fh.write("stray junk line\n")
        am._WARNED.clear()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            ents = am.load_entries(self.root)
            am.load_entries(self.root)
        self.assertEqual([e["id"] for e in ents], [good])
        self.assertEqual(err.getvalue().count("skipped malformed row"), 3)
        self.assertEqual(err.getvalue().count("skipped unparseable line"), 1)
        hits = am.search(self.root, "")
        self.assertEqual([e["id"] for e in hits], [good])

    def test_lock_released_and_timeout_message(self):
        self.add("a")
        lock = am.memory_dir(self.root) / am.LOCK_NAME
        self.assertFalse(lock.exists())
        lock.write_text("1")
        old = am.LOCK_TIMEOUT
        am.LOCK_TIMEOUT = 0.2
        try:
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                rc = am.main(["--root", str(self.root), "add", "--type", "decision", "--title", "b"])
            self.assertEqual(rc, 1)
            self.assertIn("memory lock", err.getvalue())
            # stale lock is cleaned
            os.utime(lock, (1, 1))
            self.add("c")
            self.assertFalse(lock.exists())
        finally:
            am.LOCK_TIMEOUT = old

    def test_compact_apply_vs_concurrent_adds(self):
        import threading
        old_ids = []
        for i in range(30):
            old_ids.append(self.add(f"old {i}", date="2025-01-05"))
        added, errors = [], []
        lk = threading.Lock()

        def adder(k):
            for j in range(15):
                try:
                    i = self.add(f"new {k} {j}", date="2026-10-01")
                    with lk:
                        added.append(i)
                except Exception as e:  # pragma: no cover
                    errors.append(e)

        def compactor():
            for _ in range(8):
                try:
                    am.compact(self.root, before="2026-01-01", apply=True)
                except Exception as e:  # pragma: no cover
                    errors.append(e)

        ts = [threading.Thread(target=adder, args=(k,)) for k in range(4)] + [threading.Thread(target=compactor)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.assertEqual(errors, [])
        got = {e["id"] for e in am.load_entries(self.root, include_archive=True)}
        self.assertEqual(got, set(old_ids) | set(added))
        self.assertFalse((am.memory_dir(self.root) / am.LOCK_NAME).exists())

    def test_compact_apply_vs_concurrent_add_processes(self):
        for i in range(10):
            self.add(f"old {i}", date="2025-01-05")
        procs = []
        for k in range(4):
            procs.append(subprocess.Popen(
                [sys.executable, str(SCRIPT), "--root", str(self.root), "add", "--type", "decision",
                 "--title", f"proc {k}", "--date", "2026-10-01"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
            procs.append(subprocess.Popen(
                [sys.executable, str(SCRIPT), "--root", str(self.root), "compact", "--before",
                 "2026-01-01", "--apply"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        printed = []
        for p in procs:
            out, _ = p.communicate()
            self.assertEqual(p.returncode, 0)
            if "compact" not in out:
                printed.append(out.strip())
        got = {e["id"] for e in am.load_entries(self.root, include_archive=True)}
        self.assertEqual(len(got), 14)
        self.assertTrue(set(printed) <= got)


if __name__ == "__main__":
    unittest.main()
