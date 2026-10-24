"""Spec 004 amendment (FR-019, FR-020, FR-023; AC-014, AC-016, AC-017, AC-018): tests of
skill/scripts/graph_snapshot.py and of the `<spec-id>@open` baseline that `aidd rules activate` takes.

Every test builds a tiny git project in a temp dir with a few .py files under skill/scripts/ and runs with
AIDD_EVIDENCE_DIR (honoured only with AIDD_TESTING=1) pointing at a scratch dir, so no `graph_snapshot`
event ever reaches the real project log. Stdlib unittest; every subprocess has a timeout.
Run: python -m unittest tests.test_graph_snapshot -v
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import aidd_evidence as ev  # noqa: E402
import graph_snapshot as gs  # noqa: E402

HAVE_GIT = shutil.which("git") is not None
SPEC = "001-x"

A_PY = "from skill.scripts import b\n\n\ndef run_a():\n    return b.helper_b()\n"
B_PY = "def helper_b():\n    return 1\n"
C_PY = "def solo_c():\n    return 'c'\n"


def git(root, *args):
    r = subprocess.run(["git", *args], cwd=str(root), capture_output=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (args, r.stderr.decode(errors="replace")))
    return r.stdout.decode(errors="replace").strip()


class SnapBase(unittest.TestCase):
    def setUp(self):
        if not HAVE_GIT:
            self.skipTest("git is not available")
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name).resolve() / "proj"
        self.root.mkdir()
        self.evdir = Path(self._td.name).resolve() / "evd"
        self.evdir.mkdir()
        self._old = {k: os.environ.get(k) for k in ("AIDD_EVIDENCE_DIR", "AIDD_TESTING", "AIDD_SESSION_ID")}
        os.environ["AIDD_EVIDENCE_DIR"] = str(self.evdir)
        os.environ["AIDD_TESTING"] = "1"
        os.environ.pop("AIDD_SESSION_ID", None)
        self.env = dict(os.environ)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "t")
        git(self.root, "config", "core.autocrlf", "false")
        self.put("skill/scripts/a.py", A_PY)
        self.put("skill/scripts/b.py", B_PY)
        self.put("skill/scripts/c.py", C_PY)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "init")
        self.head = git(self.root, "rev-parse", "HEAD")

    def tearDown(self):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._td.cleanup()

    def put(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))
        return p

    def snap(self, label, name="code", **kw):
        return gs.snapshot(self.root, name, label, **kw)

    def events(self, name, label):
        return ev.graph_snapshot_events(self.root, name, label)


class TestSnapshotFile(SnapBase):
    def test_file_sha_equals_logged_event_sha(self):  # FR-019
        r = self.snap("before")
        self.assertEqual(r["rc"], 0, r["message"])
        p = self.root / ".aidd" / "graphs" / "snapshots" / "code" / "before.json"
        self.assertTrue(p.is_file())
        self.assertEqual(Path(r["path"]).resolve(), p.resolve())
        evs = self.events("code", "before")
        self.assertEqual(len(evs), 1)
        d = evs[0]["detail"]
        self.assertEqual(d["sha256"], gs._sha256(p.read_bytes()))
        self.assertEqual(d["sha256"], r["sha256"])
        self.assertEqual(d["nodes"], r["nodes"])
        self.assertEqual(d["edges"], r["edges"])
        self.assertGreater(r["nodes"], 0)
        body = json.loads(p.read_bytes().decode("ascii"))
        self.assertEqual((body["name"], body["label"]), ("code", "before"))

    def test_snapshot_has_no_absolute_paths(self):  # FR-019 canonical form
        r = self.snap("before")
        self.assertEqual(r["rc"], 0, r["message"])
        text = Path(r["path"]).read_text(encoding="ascii")
        self.assertNotIn(str(self.root).replace("\\", "\\\\"), text)
        self.assertNotIn(str(self.root).replace("\\", "/"), text)

    def test_invalid_labels_refused(self):
        for bad in ("..", "a/b", "x" * 65, "", "a b", "a\\b"):
            r = self.snap(bad)
            self.assertEqual(r["rc"], 2, "label %r should be refused" % bad)
            self.assertTrue(r["message"])
        self.assertEqual(self.events("code", ".."), [])
        self.assertFalse((self.root / ".aidd" / "graphs" / "snapshots" / "code").exists()
                         and any((self.root / ".aidd" / "graphs" / "snapshots" / "code").iterdir()))
        self.assertEqual(self.snap("x" * 64)["rc"], 0)  # the 64-char boundary is valid

    def test_repeated_label_refused_and_replace_logs_second_event(self):
        r1 = self.snap("dup")
        self.assertEqual(r1["rc"], 0, r1["message"])
        self.assertEqual(self.snap("dup")["rc"], 2)
        self.assertEqual(len(self.events("code", "dup")), 1)
        self.put("skill/scripts/d.py", "def new_d():\n    return 4\n")
        r2 = self.snap("dup", replace=True)
        self.assertEqual(r2["rc"], 0, r2["message"])
        evs = self.events("code", "dup")
        self.assertEqual(len(evs), 2)
        self.assertNotEqual(r1["sha256"], r2["sha256"])
        self.assertEqual(evs[-1]["detail"]["sha256"], r2["sha256"])
        self.assertEqual(self.snap("other")["rc"], 0)
        rc, text = gs.diff(self.root, "dup", "other")
        self.assertEqual(rc, 0, text)
        self.assertIn("label was replaced", text)

    def test_same_label_different_graphs_do_not_collide(self):
        rc_ = self.snap("same", "code")
        self.assertEqual(rc_["rc"], 0, rc_["message"])
        rm = self.snap("same", "method")
        name2 = "method"
        if rm["rc"] != 0:  # method_graph may not run in a bare temp project: fall back to the progress graph
            self.put(".aidd/graphs/progress.json", json.dumps({"nodes": [{"id": "T-01"}], "edges": []}))
            rm = self.snap("same", "progress")
            name2 = "progress"
        self.assertEqual(rm["rc"], 0, rm["message"])
        base = self.root / ".aidd" / "graphs" / "snapshots"
        pc, pm = base / "code" / "same.json", base / name2 / "same.json"
        self.assertTrue(pc.is_file() and pm.is_file())
        self.assertNotEqual(pc.read_bytes(), pm.read_bytes())
        self.assertEqual(len(self.events("code", "same")), 1)
        self.assertEqual(len(self.events(name2, "same")), 1)
        self.assertEqual(self.events("code", "same")[0]["detail"]["sha256"], gs._sha256(pc.read_bytes()))
        self.assertEqual(self.events(name2, "same")[0]["detail"]["sha256"], gs._sha256(pm.read_bytes()))
        self.assertEqual(self.snap("same", "code")["rc"], 2)  # only the code one is a repeat

    def test_rev_snapshot_ignores_uncommitted_edits(self):  # AC-018
        self.put("skill/scripts/a.py", A_PY + "\n\ndef dirty_edit():\n    return 99\n")  # modified, uncommitted
        self.put("skill/scripts/e.py", "def untracked_e():\n    return 5\n")            # untracked
        old = self.snap("old", rev=self.head)
        self.assertEqual(old["rc"], 0, old["message"])
        self.assertEqual(old["rev"], self.head)
        text = Path(old["path"]).read_text(encoding="ascii")
        self.assertNotIn("dirty_edit", text)
        self.assertNotIn("untracked_e", text)
        self.assertIn("run_a", text)
        self.assertEqual(self.events("code", "old")[0]["detail"]["rev"], self.head)
        now = self.snap("now")
        self.assertEqual(now["rc"], 0, now["message"])
        self.assertIn("dirty_edit", Path(now["path"]).read_text(encoding="ascii"))
        self.assertEqual(now["rev"], "")
        self.assertEqual(self.snap("bad", rev="no-such-rev-xyz")["rc"], 2)
        self.assertEqual(git(self.root, "status", "--porcelain", "--", "skill").count("\n") + 1, 2)  # tree untouched


class TestDiff(SnapBase):
    def make_pair(self):
        self.assertEqual(self.snap("before", rev=self.head)["rc"], 0)
        self.put("skill/scripts/d.py", "def added_d():\n    return 4\n")
        self.assertEqual(self.snap("after")["rc"], 0)

    def test_clean_pair_exit_0_lists_added_node(self):  # AC-014
        self.make_pair()
        rc, text = gs.diff(self.root, "before", "after")
        self.assertEqual(rc, 0, text)
        self.assertIn("+ node skill/scripts/d.py", text)
        self.assertIn("+ node skill/scripts/d.py::added_d", text)
        self.assertNotIn("WARNING", text)
        rc2, text2 = gs.diff(self.root, "before", "before")
        self.assertEqual(rc2, 0, text2)
        self.assertNotIn("+ node", text2)

    def test_diff_output_is_capped_unless_full(self):  # FR-020
        self.assertEqual(self.snap("before", rev=self.head)["rc"], 0)
        for i in range(40):
            self.put("skill/scripts/gen%02d.py" % i, "def g%02d():\n    return %d\n" % (i, i))
        self.assertEqual(self.snap("after")["rc"], 0)
        rc, text = gs.diff(self.root, "before", "after")
        self.assertEqual(rc, 0, text)
        self.assertIn("--full", text)
        rc, full = gs.diff(self.root, "before", "after", full=True)
        self.assertEqual(rc, 0)
        self.assertGreater(len(full.splitlines()), len(text.splitlines()))
        self.assertIn("gen39", full)

    def test_hand_edited_snapshot_exits_2_altered(self):  # AC-014
        self.make_pair()
        p = self.root / ".aidd" / "graphs" / "snapshots" / "code" / "before.json"
        body = json.loads(p.read_bytes().decode("ascii"))
        body["nodes"] = body["nodes"][:-1]
        p.write_bytes(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("ascii"))
        rc, text = gs.diff(self.root, "before", "after")
        self.assertEqual(rc, 2)
        self.assertIn("snapshot altered", text)
        self.assertIn("before", text)
        # the same refusal through the CLI exit code
        r = subprocess.run([sys.executable, str(SCRIPTS_DIR / "graph_snapshot.py"), "--root", str(self.root),
                            "diff", "before", "after"], env=self.env, capture_output=True, timeout=120)
        self.assertEqual(r.returncode, 2)
        self.assertIn("snapshot altered", r.stderr.decode("utf-8", "replace"))

    def test_snapshot_without_event_exits_2(self):
        self.make_pair()
        d = self.root / ".aidd" / "graphs" / "snapshots" / "code"
        shutil.copyfile(str(d / "after.json"), str(d / "ghost.json"))  # a file, never logged
        rc, text = gs.diff(self.root, "before", "ghost", name="code")
        self.assertEqual(rc, 2)
        self.assertIn("no event for ghost", text)

    def test_diff_unknown_label_exits_2(self):
        self.make_pair()
        rc, _text = gs.diff(self.root, "before", "nope")
        self.assertEqual(rc, 2)
        rc, _text = gs.diff(self.root, "before", "../x")
        self.assertEqual(rc, 2)


class TestChanged(SnapBase):
    def test_no_baseline_exits_2_and_names_the_command(self):  # FR-023
        res = gs.changed(self.root, spec=SPEC)
        self.assertEqual(res["rc"], 2)
        self.assertIn("snapshot", res["message"])
        self.assertIn("--label %s@open" % SPEC, res["message"])
        r = subprocess.run([sys.executable, str(SCRIPTS_DIR / "graph_snapshot.py"), "--root", str(self.root),
                            "changed", "--spec", SPEC], env=self.env, capture_output=True, timeout=120)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--label %s@open" % SPEC, r.stderr.decode("utf-8", "replace"))

    def test_lists_exactly_the_two_edited_files(self):  # AC-016
        self.assertEqual(self.snap("%s@open" % SPEC)["rc"], 0)
        res0 = gs.changed(self.root, spec=SPEC)
        self.assertEqual(res0["rc"], 0, res0["message"])
        self.assertEqual((res0["added"], res0["modified"], res0["removed"]), ([], [], []))
        self.put("skill/scripts/a.py", A_PY + "\n\ndef more_a():\n    return 2\n")
        self.put("skill/scripts/b.py", B_PY.replace("return 1", "return 22"))
        res = gs.changed(self.root, spec=SPEC)
        self.assertEqual(res["rc"], 0, res["message"])
        self.assertEqual(res["modified"], ["skill/scripts/a.py", "skill/scripts/b.py"])
        self.assertEqual(res["added"], [])
        self.assertEqual(res["removed"], [])
        self.assertNotIn("skill/scripts/c.py", res["affected"] + res["modified"])
        self.put("skill/scripts/n.py", "def n():\n    return 0\n")
        (self.root / "skill" / "scripts" / "c.py").unlink()
        res = gs.changed(self.root, spec=SPEC)
        self.assertEqual(res["added"], ["skill/scripts/n.py"])
        self.assertEqual(res["removed"], ["skill/scripts/c.py"])

    def test_same_size_backdated_rewrite_is_modified_identical_is_not(self):  # AC-017
        self.assertEqual(self.snap("%s@open" % SPEC)["rc"], 0)
        c = self.root / "skill" / "scripts" / "c.py"
        b = self.root / "skill" / "scripts" / "b.py"
        st_c, st_b = os.stat(str(c)), os.stat(str(b))
        new_c = C_PY.replace("'c'", "'d'")
        self.assertEqual(len(new_c), len(C_PY))
        c.write_bytes(new_c.encode("utf-8"))
        os.utime(str(c), ns=(st_c.st_atime_ns, st_c.st_mtime_ns))       # same size, mtime set back
        self.assertEqual(os.stat(str(c)).st_size, st_c.st_size)
        b.write_bytes(B_PY.encode("utf-8"))                               # rewritten, identical content
        os.utime(str(b), (time.time() + 50, time.time() + 50))            # even with a newer mtime
        res = gs.changed(self.root, spec=SPEC)
        self.assertEqual(res["rc"], 0, res["message"])
        self.assertEqual(res["modified"], ["skill/scripts/c.py"])


def _manifest_path(root, spec=SPEC):
    return Path(root) / ".aidd" / "graphs" / "snapshots" / "manifests" / ("%s@open.json" % spec)


class TestOpenManifest(SnapBase):
    def test_open_manifest_first_second_replace_invalid(self):
        r = gs.open_manifest(self.root, SPEC)
        self.assertEqual(r["rc"], 0, r)
        m = json.loads(_manifest_path(self.root).read_text(encoding="utf-8"))
        self.assertEqual(m["spec"], SPEC)
        self.assertIn("taken", m)
        code = m["graphs"]["code"]
        for rel in ("skill/scripts/a.py", "skill/scripts/b.py", "skill/scripts/c.py"):
            self.assertIn(rel, code)
        self.assertEqual(code["skill/scripts/b.py"], git(self.root, "hash-object", "skill/scripts/b.py"))
        self.assertEqual(gs.open_manifest(self.root, SPEC)["rc"], 2)
        self.put("skill/scripts/d.py", "def d():\n    return 4\n")
        self.assertEqual(gs.open_manifest(self.root, SPEC, replace=True)["rc"], 0)
        m2 = json.loads(_manifest_path(self.root).read_text(encoding="utf-8"))
        self.assertIn("skill/scripts/d.py", m2["graphs"]["code"])
        for bad in ("..", "a/b", "x" * 70, ""):
            self.assertEqual(gs.open_manifest(self.root, bad)["rc"], 2, bad)
        self.assertEqual(self.events("code", "%s@open" % SPEC), [])  # a manifest is not a graph_snapshot event


class TestChangedFromManifest(SnapBase):
    def test_lists_exactly_the_two_edited_files(self):
        self.assertEqual(gs.open_manifest(self.root, SPEC)["rc"], 0)
        res0 = gs.changed(self.root, spec=SPEC)
        self.assertEqual(res0["rc"], 0, res0["message"])
        self.assertEqual((res0["added"], res0["modified"], res0["removed"]), ([], [], []))
        self.put("skill/scripts/a.py", A_PY + "\n\ndef more_a():\n    return 2\n")
        self.put("skill/scripts/b.py", B_PY.replace("return 1", "return 22"))
        res = gs.changed(self.root, spec=SPEC)
        self.assertEqual(res["rc"], 0, res["message"])
        self.assertEqual(res["modified"], ["skill/scripts/a.py", "skill/scripts/b.py"])
        self.assertEqual((res["added"], res["removed"]), ([], []))

    def test_affected_empty_with_message_without_code_json(self):
        self.assertEqual(gs.open_manifest(self.root, SPEC)["rc"], 0)
        self.assertFalse((self.root / ".aidd" / "graphs" / "code.json").exists())
        self.put("skill/scripts/b.py", B_PY.replace("return 1", "return 22"))
        res = gs.changed(self.root, spec=SPEC)
        self.assertEqual(res["rc"], 0, res["message"])
        self.assertEqual(res["modified"], ["skill/scripts/b.py"])
        self.assertEqual(res["affected"], [])
        self.assertTrue(res["message"])

    def test_same_size_backdated_rewrite_is_modified_identical_is_not(self):  # AC-017
        self.assertEqual(gs.open_manifest(self.root, SPEC)["rc"], 0)
        c = self.root / "skill" / "scripts" / "c.py"
        b = self.root / "skill" / "scripts" / "b.py"
        st_c = os.stat(str(c))
        new_c = C_PY.replace("'c'", "'d'")
        self.assertEqual(len(new_c), len(C_PY))
        c.write_bytes(new_c.encode("utf-8"))
        os.utime(str(c), ns=(st_c.st_atime_ns, st_c.st_mtime_ns))
        b.write_bytes(B_PY.encode("utf-8"))
        os.utime(str(b), (time.time() + 50, time.time() + 50))
        res = gs.changed(self.root, spec=SPEC)
        self.assertEqual(res["rc"], 0, res["message"])
        self.assertEqual(res["modified"], ["skill/scripts/c.py"])

    def test_manifest_wins_over_snapshot_of_same_label(self):
        self.assertEqual(self.snap("%s@open" % SPEC)["rc"], 0)  # snapshot taken first
        self.put("skill/scripts/b.py", B_PY.replace("return 1", "return 22"))
        self.assertEqual(gs.open_manifest(self.root, SPEC)["rc"], 0)  # manifest already has the edit
        res = gs.changed(self.root, spec=SPEC)
        self.assertEqual(res["rc"], 0, res["message"])
        self.assertEqual(res["modified"], [])  # the snapshot alone would list b.py

    def test_neither_manifest_nor_snapshot_exits_2_naming_both_commands(self):
        res = gs.changed(self.root, spec=SPEC)
        self.assertEqual(res["rc"], 2)
        self.assertIn("aidd rules activate", res["message"])
        self.assertIn("aidd graphs snapshot", res["message"])


class TestActivateManifest(SnapBase):
    def activate(self):
        import aidd_status
        buf = io.StringIO()
        old_cwd = os.getcwd()
        os.chdir(str(self.root))
        try:
            with contextlib.redirect_stdout(buf):
                rc = aidd_status.cmd_activate(SPEC)
        finally:
            os.chdir(old_cwd)
        return rc, buf.getvalue()

    def test_activate_writes_only_a_manifest(self):  # AC-033
        sd = self.root / "specs" / SPEC
        sd.mkdir(parents=True)
        (sd / "spec.md").write_text("# %s\n" % SPEC, encoding="utf-8")
        (sd / "tasks.md").write_text("# tasks\n", encoding="utf-8")
        ev.append(self.root, "sess-t18", "spec_edit", path=str(sd / "tasks.md"), spec=SPEC, file="tasks.md")
        rc, out = self.activate()
        self.assertEqual(rc, 0, out)
        self.assertIn("baseline manifest written", out)
        mp = _manifest_path(self.root)
        self.assertTrue(mp.is_file())
        m = json.loads(mp.read_text(encoding="utf-8"))
        self.assertEqual(m["spec"], SPEC)
        self.assertIn("taken", m)
        for rel in ("skill/scripts/a.py", "skill/scripts/b.py", "skill/scripts/c.py"):
            self.assertEqual(m["graphs"]["code"][rel], git(self.root, "hash-object", rel))
        self.assertFalse((self.root / ".aidd" / "graphs" / "code.json").exists())
        self.assertFalse((self.root / ".aidd" / "graphs" / "snapshots" / "code").exists())
        self.assertEqual(ev.events(self.root, kind="graph_snapshot"), [])
        before = mp.read_bytes()
        mtime = os.stat(str(mp)).st_mtime_ns
        rc2, out2 = self.activate()
        self.assertEqual(rc2, 0, out2)
        self.assertNotIn("baseline manifest written", out2)
        self.assertEqual(mp.read_bytes(), before)
        self.assertEqual(os.stat(str(mp)).st_mtime_ns, mtime)


if __name__ == "__main__":
    unittest.main()
