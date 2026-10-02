"""Tests for scripts/aidd_memory_import.py with a SYNTHETIC claude-mem DB.

Run: python -m unittest tests.test_aidd_memory_import -v
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import aidd_memory as am  # noqa: E402
import aidd_memory_import as imp  # noqa: E402

SCRIPT = SCRIPTS_DIR / "aidd_memory.py"

OBS_SCHEMA = ("CREATE TABLE observations(id INTEGER PRIMARY KEY, project TEXT, type TEXT, title TEXT, "
              "subtitle TEXT, facts TEXT, narrative TEXT, concepts TEXT, files_read TEXT, "
              "files_modified TEXT, created_at TEXT, content_hash TEXT)")
SUM_SCHEMA = ("CREATE TABLE session_summaries(id INTEGER PRIMARY KEY, project TEXT, request TEXT, "
              "investigated TEXT, learned TEXT, completed TEXT, next_steps TEXT, files_read TEXT, "
              "files_edited TEXT, created_at TEXT)")


def obs(project, type_, title, facts=None, narrative=None, fm=None, fr=None,
        created='2026-03-10T10:00:00.000Z'):
    return (project, type_, title, None, facts, narrative, None, fr, fm, created)


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "proj"
        self.root.mkdir()
        self._env = os.environ.pop("AIDD_MEMORY_DIR", None)
        self.addCleanup(lambda: os.environ.pop("AIDD_MEMORY_DIR", None))
        self.db = self.tmp / "cm.db"
        self.make_db()

    def make_db(self):
        con = sqlite3.connect(self.db)
        con.execute(OBS_SCHEMA)
        con.execute(SUM_SCHEMA)
        rows = [
            obs("AlphaApp", "decision", "Use TOON for flows", json.dumps(["fact one", "fact two"]),
                "Chosen because of US-001 and CTL-004.\nSecond line.",
                json.dumps([str(self.root / "src" / "a.py"), "src\\b.py"])),
            obs("AlphaApp", "bug-fix", "Fix null crash in SCREEN-002-F3", None, "Null deref in COMP-007.",
                None, json.dumps(["lib/x.py"])),
            obs("AlphaApp", "security_alert", "Token leak", json.dumps(["token logged"]), "",
                "[]"),
            obs("AlphaApp", "critical", "Prod down", None, "API-12 failing", None),
            obs("AlphaApp", "discovery", "Found a thing", None, "just info"),
            obs("AlphaApp", "change", "Changed a thing", None, "edit"),
            obs("AlphaApp", "feature", "New feature", None, "feat"),
            obs("BetaApp", "decision", "Beta decision", None, "other project"),
            obs("AlphaApp", "decision", "Old decision", None, "old", created="2025-01-01T00:00:00Z"),
            obs("AlphaApp", "decision", "Malformed JSON", "[not json, still text", "narr [broken",
                "{oops", created="2026-03-11T00:00:00Z"),
            obs("AlphaApp", "decision", "", None, "Narrative only becomes the title words here",
                created="2026-03-12T00:00:00Z"),
            obs("AlphaApp", "decision", "", None, None, created="2026-03-13T00:00:00Z"),
            obs("AlphaApp", "decision", "Plain facts", "line a\nline b", None, "plain/file.py",
                created="2026-03-14T00:00:00Z"),
        ]
        con.executemany("INSERT INTO observations(project,type,title,subtitle,facts,narrative,concepts,"
                        "files_read,files_modified,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", rows)
        con.executemany(
            "INSERT INTO session_summaries(project,request,investigated,learned,completed,next_steps,"
            "files_read,files_edited,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            [("AlphaApp", "Implement US-009 login", "i", "Learned lots", "Did stuff", "n", None, None,
              "2026-04-01T00:00:00Z"),
             ("AlphaApp", "Second request", "i", "", "Completed only", "n", None, None,
              "2026-04-02T00:00:00Z"),
             ("BetaApp", "Beta req", "", "x", "", "", None, None, "2026-04-03T00:00:00Z")])
        con.commit()
        con.close()

    def run_import(self, **kw):
        kw.setdefault("projects", ["Alpha"])
        return imp.import_claude_mem(self.db, self.root, **kw)

    def entries(self):
        return am.load_entries(self.root)

    def by_title(self, title):
        return next(e for e in self.entries() if e["title"] == title)


class TestImport(Base):
    def test_default_mapping_and_exclusions(self):
        r = self.run_import()
        self.assertEqual(r["decision"], 5)  # TOON, Old, Malformed, narrative-only, Plain facts
        self.assertEqual(r["bugfix"], 1)
        self.assertEqual(r["risk"], 2)
        titles = {e["title"] for e in self.entries()}
        self.assertNotIn("Found a thing", titles)
        self.assertNotIn("Changed a thing", titles)
        self.assertNotIn("New feature", titles)
        self.assertNotIn("Beta decision", titles)
        self.assertTrue(all(e["source"] == "import" for e in self.entries()))
        self.assertEqual(self.by_title("Fix null crash in SCREEN-002-F3")["type"], "bugfix")
        self.assertEqual(self.by_title("Token leak")["type"], "risk")
        self.assertEqual(r["written"], len(self.entries()))
        self.assertFalse(r["dry_run"])

    def test_codes_why_files(self):
        self.run_import()
        e = self.by_title("Use TOON for flows")
        self.assertEqual(e["codes"], ["US-001", "CTL-004"])
        self.assertNotIn("\n", e["why"])
        self.assertEqual(e["date"], "2026-03-10")
        self.assertIn("src/a.py", e["files"])
        self.assertIn("src/b.py", e["files"])
        b = self.by_title("Fix null crash in SCREEN-002-F3")
        self.assertEqual(b["codes"], ["SCREEN-002-F3", "COMP-007"])
        self.assertEqual(b["files"], ["lib/x.py"])  # fallback to files_read
        self.assertEqual(self.by_title("Token leak")["why"], "token logged")  # facts fallback

    def test_why_truncated(self):
        con = sqlite3.connect(self.db)
        con.execute("INSERT INTO observations(project,type,title,narrative,created_at) "
                    "VALUES('AlphaApp','decision','Long one',?, '2026-05-01')", ("word " * 200,))
        con.commit()
        con.close()
        self.run_import()
        self.assertLessEqual(len(self.by_title("Long one")["why"]), 400)

    def test_include_adds_discovery(self):
        r = self.run_import(types=imp.DEFAULT_TYPES + ("discovery", "change", "feature"))
        self.assertEqual(r["discovery"], 3 + 2)  # 3 observations + 2 summaries
        self.assertEqual(self.by_title("Found a thing")["type"], "discovery")
        self.assertEqual(self.by_title("New feature")["type"], "discovery")

    def test_summaries(self):
        r = self.run_import()
        self.assertEqual(r["summaries"], 2)
        e = self.by_title("Implement US-009 login")
        self.assertEqual(e["type"], "discovery")
        self.assertEqual(e["why"], "Learned lots")
        self.assertEqual(e["codes"], ["US-009"])
        self.assertEqual(self.by_title("Second request")["why"], "Completed only")
        r2 = self.run_import(include_summaries=False, scope="other")
        self.assertEqual(r2["summaries"], 0)

    def test_project_filter(self):
        r = self.run_import(projects=["Beta"])
        self.assertEqual(r["decision"], 1)
        self.assertEqual(r["summaries"], 1)
        r = self.run_import(projects=["Nothing"], scope="none")
        self.assertEqual(r["written"], 0)
        r = self.run_import(projects=["Beta", "Alpha"], scope="both")
        self.assertEqual(r["decision"], 6)

    def test_since(self):
        self.run_import(since="2026-03-11")
        titles = {e["title"] for e in self.entries()}
        self.assertNotIn("Old decision", titles)
        self.assertNotIn("Use TOON for flows", titles)
        self.assertIn("Malformed JSON", titles)

    def test_idempotent(self):
        r1 = self.run_import()
        n = len(self.entries())
        r2 = self.run_import()
        self.assertEqual(r2["written"], 0)
        self.assertEqual(r2["decision"], 0)
        self.assertEqual(len(self.entries()), n)
        self.assertGreater(r1["written"], 0)

    def test_dry_run_writes_nothing_same_counts(self):
        d = self.run_import(dry_run=True)
        self.assertTrue(d["dry_run"])
        self.assertEqual(d["written"], 0)
        self.assertFalse((self.root / ".aidd").exists())
        r = self.run_import()
        for k in ("decision", "bugfix", "risk", "discovery", "summaries"):
            self.assertEqual(d[k], r[k], k)

    def test_original_db_unchanged(self):
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        self.run_import()
        self.run_import(dry_run=True, types=imp.DEFAULT_TYPES + ("discovery",))
        self.assertEqual(before, hashlib.sha256(self.db.read_bytes()).hexdigest())
        self.assertEqual([p.name for p in self.tmp.iterdir() if p.name.startswith("cm.db")], ["cm.db"])

    def test_malformed_and_fallbacks(self):
        r = self.run_import()
        self.assertEqual(self.by_title("Malformed JSON")["type"], "decision")
        e = self.by_title("Narrative only becomes the title words here")
        self.assertTrue(e["why"])
        self.assertGreaterEqual(r["skipped"], 1)  # empty title+why row
        self.assertEqual(self.by_title("Plain facts")["why"], "line a; line b")
        self.assertEqual(self.by_title("Plain facts")["files"], ["plain/file.py"])

    def test_parse_helpers(self):
        self.assertEqual(imp._parse_list('["a","b"]'), ["a", "b"])
        self.assertEqual(imp._parse_list("x\ny"), ["x", "y"])
        self.assertEqual(imp._parse_list(None), [])
        self.assertEqual(imp._parse_files("a.py, b.py"), ["a.py", "b.py"])

    def test_missing_db(self):
        with self.assertRaises(ValueError):
            imp.import_claude_mem(self.tmp / "nope.db", self.root, projects=["x"])


class TestHardening(Base):
    def add(self, title, narrative=None, fm=None, fr=None, type_='decision', facts=None, n=[0]):
        n[0] += 1
        con = sqlite3.connect(self.db)
        con.execute("INSERT INTO observations(project,type,title,facts,narrative,files_read,files_modified,"
                    "created_at) VALUES('AlphaApp',?,?,?,?,?,?,?)",
                    (type_, title, facts, narrative, fr, fm, f'2026-06-{n[0]:02d}'))
        con.commit()
        con.close()

    def test_files_normalised(self):
        outside = "C:/Users/someone/.claude/plans/x.md"
        files = [outside, "[@HRH_OPDC] table - rubric 167 configuration (x)", "fix.sql (proposed fix",
                 "deep-cooking-candle.md (created)", str(self.root / "src" / "ok.py"),
                 "src" + chr(92) + "win.py", "./rel/p.ts", "noext", "../up/x.py", "/etc/passwd.conf",
                 "a/b c.py", "dir/file[1].py"]
        self.add("File junk", "why here", fm=json.dumps(files))
        self.run_import()
        self.assertEqual(self.by_title("File junk")["files"], ["src/ok.py", "src/win.py", "rel/p.ts"])

    def test_scrub_patterns(self):
        cases = {
            "password=hunter22": "hunter22", "PASSWD: abc123xyz": "abc123xyz", "pwd = s3cret": "s3cret",
            "secret: topvalue": "topvalue", "token=abcdef": "abcdef", "apikey: K9": "K9",
            "api_key=zzz999": "zzz999", "Bearer abcdefgh12345678": "abcdefgh12345678",
            "connectionstring=Server=db;Pwd=x": "Server=db",
            "hash " + "a1" * 16 + " end": "a1" * 16,
            "host 10.1.2.3 up": "10.1.2.3", "172.16.0.9": "172.16.0.9", "172.31.255.1": "172.31.255.1",
            "192.168.1.50": "192.168.1.50", "127.0.0.1": "127.0.0.1",
        }
        for i, (text, secret) in enumerate(cases.items()):
            self.add(f"T{i} {text}", f"narr {text}")
        self.run_import()
        for i, (text, secret) in enumerate(cases.items()):
            e = next(x for x in self.entries() if x["title"].startswith(f"T{i} "))
            self.assertNotIn(secret, e["title"], text)
            self.assertNotIn(secret, e["why"], text)
            self.assertIn("[redacted]", e["title"], text)
            self.assertIn("[redacted]", e["why"], text)

    def test_scrub_leaves_normal_text(self):
        txt = "Rotate the token every day; public IP 8.8.8.8 and 172.32.0.1 version 1.2.3.4 fine"
        self.assertEqual(imp._scrub(txt), txt)
        self.assertEqual(imp._scrub("sha " + "ab" * 8), "sha " + "ab" * 8)  # short hex untouched
        self.add("Normal token prose", "the token expires")
        self.run_import()
        self.assertEqual(self.by_title("Normal token prose")["why"], "the token expires")

    def test_scrub_home_paths_and_leaks(self):
        s = imp._scrub
        U = "FAKEUSER"
        cases = [
            ("see C:" + chr(92) + "Users" + chr(92) + U + chr(92) + "source" + chr(92) + "repos" + chr(92) + "x ok", "see ~/source/repos/x ok"),
            ("c:/users/" + U + "/source/repos/x", "~/source/repos/x"),
            ("C:/Users/" + U + "/a.txt and more", "~/a.txt and more"),
            ("/home/" + U + "/proj/f.py", "~/proj/f.py"),
            ("/Users/" + U + "/Library/x", "~/Library/x"),
            ("%USERPROFILE%" + chr(92) + "src" + chr(92) + "y", "~/src/y"),
            ("at C:" + chr(92) + "Users" + chr(92) + U, "at ~"),
            ("srv " + chr(92) * 2 + "fakehost" + chr(92) + "share" + chr(92) + "dir ok", "srv [redacted-unc] ok"),
            ("mail fake.person+x@example.invalid now", "mail [redacted-email] now"),
            ("Authorization: Basic ZmFrZTpmYWtl rest", "Authorization: [redacted] rest"),
            ("Authorization: tokenfake", "Authorization: [redacted]"),
            ("db postgres://fakeu:fakepw@db.example.invalid/x", "db postgres://[redacted]@db.example.invalid/x"),
            ("jwt eyJfake.fake_payload.fake-sig end", "jwt [redacted] end"),
            ("k sk-FAKEFAKEFAKEFAKE1234 end", "k [redacted] end"),
            ("k ghp_" + "F" * 20 + " end", "k [redacted] end"),
            ("k xoxb-FAKE-123 end", "k [redacted] end"),
            ("k AKIA" + "F" * 16 + " end", "k [redacted] end"),
        ]
        for text, want in cases:
            got = s(text)
            self.assertEqual(got, want, text)
            self.assertNotIn(U, got)

    def test_scrub_normal_text_unchanged_extra(self):
        for txt in ("Upgrade to v2.10.3 on Users table; the home page and user list",
                    "Use the Authorization header in the API", "ask-me at 12:30 about sk-short",
                    "folder Users of the app, see src/users/home.py"):
            self.assertEqual(imp._scrub(txt), txt)

    def test_files_drop_system_paths(self):
        files = ["Users/FAKEUSER/AppData/Local/Temp/claude/x/apply.ps1", "home/fake/a.py", "AppData/x/a.py",
                 "Temp/a.py", "tmp/a.py", "var/log/a.log", "etc/a.conf", "usr/lib/a.so", "opt/a.py",
                 "Windows/a.dll", "src/node_modules/p/i.js", "src/.claude/s.json", "src/scratchpad/n.md",
                 "src/AppData/a.py", "src/ok.py"]
        self.add("Sys paths", "why here", fm=json.dumps(files))
        self.run_import()
        self.assertEqual(self.by_title("Sys paths")["files"], ["src/ok.py"])

    def test_not_claude_mem_db(self):
        bad = self.tmp / "bad.db"
        con = sqlite3.connect(bad)
        con.execute("CREATE TABLE other(x)")
        con.commit()
        con.close()
        with self.assertRaises(ValueError) as c:
            imp.import_claude_mem(bad, self.root, projects=["x"])
        self.assertIn("not a claude-mem database", str(c.exception))
        bad2 = self.tmp / "bad2.db"
        con = sqlite3.connect(bad2)
        con.execute("CREATE TABLE observations(id INTEGER PRIMARY KEY, project TEXT, type TEXT)")
        con.execute("CREATE TABLE session_summaries(id INTEGER PRIMARY KEY, project TEXT)")
        con.commit()
        con.close()
        with self.assertRaises(ValueError) as c:
            imp.import_claude_mem(bad2, self.root, projects=["x"])
        self.assertIn("title", str(c.exception))
        with self.assertRaises(ValueError):
            imp.import_claude_mem(bad2, self.root, projects=["x"], include_summaries=False)

    def test_optional_columns_degrade(self):
        db = self.tmp / "min.db"
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE observations(id INTEGER PRIMARY KEY, project TEXT, type TEXT, title TEXT, "
                    "narrative TEXT, created_at TEXT)")
        con.execute("CREATE TABLE session_summaries(id INTEGER PRIMARY KEY, project TEXT, request TEXT, "
                    "learned TEXT, created_at TEXT)")
        con.execute("INSERT INTO observations(project,type,title,narrative,created_at) "
                    "VALUES('AlphaApp','decision','Minimal','works','2026-07-01')")
        con.execute("INSERT INTO session_summaries(project,request,learned,created_at) "
                    "VALUES('AlphaApp','Req','Learn','2026-07-02')")
        con.commit()
        con.close()
        r = imp.import_claude_mem(db, self.root, projects=["Alpha"])
        self.assertEqual((r["decision"], r["summaries"]), (1, 1))

    def test_quality_skips_and_trims(self):
        self.add("Continuation:", None)                       # generic only, nothing else -> skip
        self.add("Analysis of", "has a narrative")             # generic title -> title from why
        self.add("Continuation: Fix the loader", "w")          # prefix trimmed
        self.add("Analysis of loader config", "w2")            # 2+ words, no article -> trimmed
        self.add("Analysis of loader", "w3")                   # 1 word remains -> kept as is
        self.add("Title only no why", None)                    # no why, codes, files -> skipped
        self.add("Title with code US-044", None)               # code present -> kept
        self.add("Title with file", None, fm=json.dumps(["a/b.py"]))
        r = self.run_import()
        titles = {e["title"] for e in self.entries()}
        self.assertNotIn("Continuation:", titles)
        self.assertIn("has a narrative", titles)
        self.assertIn("Fix the loader", titles)
        self.assertIn("Loader config", titles)
        self.assertIn("Analysis of loader", titles)
        self.assertNotIn("Title only no why", titles)
        self.assertIn("Title with code US-044", titles)
        self.assertIn("Title with file", titles)
        self.assertGreaterEqual(r["skipped"], 2)
        for e in self.entries():
            self.assertTrue(e["why"] or e["codes"] or e["files"], e["title"])

    def test_generic_summary_skipped(self):
        con = sqlite3.connect(self.db)
        con.execute("INSERT INTO session_summaries(project,request,learned,completed,created_at) "
                    "VALUES('AlphaApp','Continuation:','','','2026-08-01')")
        con.commit()
        con.close()
        r = self.run_import()
        self.assertEqual(r["summaries"], 2)


class TestCli(Base):
    def cli(self, *args):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        env.pop("AIDD_MEMORY_DIR", None)
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), *args],
                              capture_output=True, text=True, encoding="utf-8", env=env)

    def test_dry_run_then_real_then_include(self):
        p = self.cli("import-claude-mem", str(self.db), "--project", "Alpha", "--dry-run")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("decision: 5", p.stdout)
        self.assertIn("dry_run: True", p.stdout)
        self.assertFalse((self.root / ".aidd").exists())
        p = self.cli("import-claude-mem", str(self.db), "--project", "Alpha")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(self.entries())
        p = self.cli("import-claude-mem", str(self.db), "--project", "Alpha", "--include", "discovery,change",
                     "--scope", "extra", "--dry-run")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("discovery: 4", p.stdout)  # 2 obs + 2 summaries


if __name__ == "__main__":
    unittest.main()
