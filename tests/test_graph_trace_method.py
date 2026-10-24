"""Spec 004 amendment (FR-016, FR-017, FR-018, FR-021; AC-011, AC-012, AC-013, AC-015): tests of
method_graph, graph_snapshot `repeats`, graph_trace and `aidd_graphs status`.

Every test works on a temp project (git init where needed); the evidence log goes to a scratch dir through
the evidence-dir variable (honoured only in testing mode). Stdlib unittest; every subprocess has a timeout.
Run: python -m unittest tests.test_graph_trace_method -v
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import code_graph as cg  # noqa: E402
import graph_snapshot as gs  # noqa: E402
import method_graph as mg  # noqa: E402

HAVE_GIT = shutil.which("git") is not None
TIMEOUT = 180
ENV_KEYS = ("AIDD_EVIDENCE_DIR", "AIDD_TESTING", "AIDD_SESSION_ID")


def git(root, *args):
    r = subprocess.run(["git", *args], cwd=str(root), capture_output=True, timeout=TIMEOUT)
    if r.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (args, r.stderr.decode(errors="replace")))
    return r.stdout.decode(errors="replace").strip()


class TempBase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name).resolve()
        self.root = self.tmp / "proj"
        self.root.mkdir()
        self.evdir = self.tmp / "evd"
        self.evdir.mkdir()
        self._old = {k: os.environ.get(k) for k in ENV_KEYS}
        os.environ[ENV_KEYS[0]] = str(self.evdir)
        os.environ[ENV_KEYS[1]] = "1"
        os.environ.pop(ENV_KEYS[2], None)

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

    def init_git(self):
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "t")
        git(self.root, "config", "core.autocrlf", "false")


# ------------------------------------------------------------------------------------------ AC-011 method

SKILL_MD = """# Skill

## Hard rules

| Rule | What |
|---|---|
| **R10** executed evidence | Evidence must be executed. |
| **R11** orphan rule | Nobody enforces this one. |

## Steps

### Step 6 - converge

Audit independently; cite R10 for the executed evidence.
"""
ENFORCER_PY = 'def check():\n    """Enforces R10 (executed evidence) and, wrongly, R8."""\n    return 1\n'


class TestMethodGraph(TempBase):  # AC-011 / FR-016
    def _build(self):
        self.put("skill/SKILL.md", SKILL_MD)
        self.put("skill/scripts/enf.py", ENFORCER_PY)
        code, _stats = cg.build(self.root)
        return mg.build(self.root, code_graph=code), code

    def test_parsers(self):
        self.assertEqual([r[0] for r in mg.parse_rules(SKILL_MD)], ["R10", "R11"])
        self.assertEqual([s[0] for s in mg.parse_steps(SKILL_MD)], ["6"])

    def test_rule_enforced_by_func_and_cited_by_step(self):
        g, code = self._build()
        nodes = {n["id"]: n for n in g["nodes"]}
        self.assertEqual(nodes["R10"]["type"], "RULE")
        self.assertFalse(nodes["R10"].get("unlinked"))
        fid = "skill/scripts/enf.py::check"
        self.assertTrue(any(f["id"] == fid and "R10" in (f.get("rule_ids") or ())
                            for f in code["nodes"] if f.get("type") == "FUNC"),
                        "fixture: code graph must carry rule_ids from the docstring")
        enf = [e for e in g["edges"] if e["relation"] == "enforced_by" and e["source"] == "R10"]
        self.assertEqual([e["target"] for e in enf], [fid])
        self.assertEqual(enf[0].get("via"), "mention")
        self.assertIn(fid, nodes)
        cites = [(e["source"], e["target"]) for e in g["edges"] if e["relation"] == "cites"]
        self.assertIn(("STEP:6", "R10"), cites)

    def test_unenforced_rule_is_unlinked(self):
        g, _ = self._build()
        nodes = {n["id"]: n for n in g["nodes"]}
        self.assertTrue(nodes["R11"].get("unlinked"))

    def test_rule_absent_from_table_warns(self):
        g, _ = self._build()
        self.assertTrue(any("R8" in w and "absent" in w for w in g["warnings"]), g["warnings"])
        self.assertNotIn("R8", {n["id"] for n in g["nodes"]})


# ------------------------------------------------------------------------------------------ AC-012 repeats

def _fix_graph():
    p = "skill/scripts/demo.py::"

    def func(name, **kw):
        n = {"id": p + name, "type": "FUNC", "label": name}
        n.update(kw)
        return n

    def edge(s, t, rel):
        return {"source": s, "target": t, "relation": rel}

    nodes = [func("main"), func("left"), func("right"),
             func("looper", ext=["resolve"], ext_in_loop=["resolve"]),
             {"id": "sink:file:*", "type": "SINK", "label": "file read"}]
    edges = [edge(p + "main", p + "left", "calls"),
             edge(p + "main", p + "right", "calls"),
             edge(p + "main", p + "looper", "calls"),
             edge(p + "left", "sink:file:*", "reads"),
             edge(p + "right", "sink:file:*", "reads")]
    return {"nodes": nodes, "edges": edges}


class TestRepeats(TempBase):  # AC-012 / FR-017
    def setUp(self):
        super().setUp()
        self._saved = (gs.entrypoints, gs._current_code_graph)
        gs.entrypoints = lambda cli_path=None: {"demo": {"script": "demo.py", "func": "main"}}
        gs._current_code_graph = lambda root: _fix_graph()

    def tearDown(self):
        gs.entrypoints, gs._current_code_graph = self._saved
        super().tearDown()

    def test_sink_by_two_paths_and_in_loop_ext(self):
        rc, lines = gs._repeats(self.root, cmd="demo")
        self.assertEqual(rc, 0, lines)
        text = "\n".join(lines)
        self.assertTrue(any(l.startswith("SINK sink:file:* paths=2") for l in lines), text)
        self.assertTrue(any("skill/scripts/demo.py::looper" in l and "ext_in_loop=resolve" in l
                            for l in lines), text)

    def test_unknown_cmd_is_rc_2(self):
        rc, lines = gs._repeats(self.root, cmd="nope")
        self.assertEqual(rc, 2)
        self.assertIn("unknown command", lines[0])


class TestEntrypoints(TempBase):  # AC-012 / FR-017
    def test_fake_cli_maps_demo_to_script(self):
        cli = self.put("aidd/cli.py",
                       'def cmd_demo(args):\n    return _run("demo.py", ["demo"] + list(args))\n')
        eps = gs.entrypoints(str(cli))
        self.assertIn("demo", eps)
        self.assertEqual(eps["demo"]["script"], "demo.py")

    def test_missing_cli_gives_empty(self):
        self.assertEqual(gs.entrypoints(str(self.tmp / "nope" / "cli.py")), {})


# ------------------------------------------------------------------------------------------ AC-013 trace

DEMO_PY = '''"""Fake aidd script: reads data.txt twice, spawns git once."""
import subprocess
import sys


def read_it():
    with open("data.txt", "r") as f:
        return f.read()


def main():
    read_it()
    read_it()
    subprocess.run(["git", "--version"], capture_output=True, timeout=60)
    return 3 if "fail" in sys.argv[1:] else 0


if __name__ == "__main__":
    sys.exit(main())
'''
FAKE_CLI = 'def cmd_demo(args):\n    return _run("demo.py", ["demo"] + list(args))\n'


class TestTrace(TempBase):  # AC-013 / FR-018
    def setUp(self):
        if not HAVE_GIT:
            self.skipTest("git is not available")
        super().setUp()
        sd = self.root / "skill" / "scripts"
        sd.mkdir(parents=True)
        for name in ("graph_trace.py", "graph_snapshot.py"):
            shutil.copy2(str(SCRIPTS_DIR / name), str(sd / name))
        self.put("skill/scripts/find_spec.py", "")
        self.put("skill/scripts/demo.py", DEMO_PY)
        self.put("aidd/cli.py", FAKE_CLI)
        self.put("data.txt", "hello\n")
        spec = importlib.util.spec_from_file_location("gt_tmp_copy", str(sd / "graph_trace.py"))
        self.gt = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.gt)

    def _trace(self, *extra):
        holder = []
        with contextlib.redirect_stderr(io.StringIO()):
            rc = self.gt.run_traced(self.root, ["aidd", "demo"] + list(extra), tracer_out=holder)
        self.assertEqual(len(holder), 1)
        return rc, holder[0]

    @staticmethod
    def _sum(tracer, prefix):
        pairs = [c for (f, s), c in tracer.counts.items() if s.startswith(prefix)]
        return sum(c["count"] for c in pairs), sum(c["rereads"] for c in pairs)

    def test_two_runs_identical_counts_and_rereads(self):
        rc1, t1 = self._trace()
        rc2, t2 = self._trace()
        self.assertEqual((rc1, rc2), (0, 0))
        reads1, rer1 = self._sum(t1, "sink:file:")
        reads2, rer2 = self._sum(t2, "sink:file:")
        sp1, _ = self._sum(t1, "sink:spawn:")
        sp2, _ = self._sum(t2, "sink:spawn:")
        self.assertEqual((reads1, sp1), (reads2, sp2))
        self.assertEqual(rer1, rer2)
        self.assertGreaterEqual(reads1, 2)
        self.assertEqual(sp1, 1)
        self.assertGreaterEqual(rer1, 1, "the second read of the unchanged data.txt must count as a reread")
        self.assertIn("skill/scripts/demo.py::read_it", {f for (f, s) in t1.counts})
        spawn_sinks = {s for (f, s) in t1.counts if s.startswith("sink:spawn:")}
        self.assertEqual(len(spawn_sinks), 1)
        self.assertIn("git", next(iter(spawn_sinks)))

    def test_exit_code_returned_and_profiler_removed(self):
        before = sys.getprofile()
        rc, _t = self._trace("fail")
        self.assertEqual(rc, 3)
        self.assertIs(sys.getprofile(), before)
        self.assertIsNone(sys.getprofile())

    def test_scripts_dir_runs_the_other_demo(self):
        old_dir = self.root / "old" / "skill" / "scripts"
        old_dir.mkdir(parents=True)
        (old_dir / "demo.py").write_text(
            'import sys\n\n\ndef read_it():\n    with open("data.txt", "r") as f:\n        return f.read()\n\n\n'
            'def main():\n    read_it()\n    return 0\n\n\nif __name__ == "__main__":\n    sys.exit(main())\n',
            encoding="utf-8")
        holder_new, holder_old = [], []
        with contextlib.redirect_stderr(io.StringIO()):
            rc_new = self.gt.run_traced(self.root, ["aidd", "demo"], tracer_out=holder_new)
            rc_old = self.gt.run_traced(self.root, ["aidd", "demo"], tracer_out=holder_old,
                                        scripts_dir=str(old_dir))
        self.assertEqual((rc_new, rc_old), (0, 0))
        tn, to = holder_new[0], holder_old[0]
        self.assertEqual(self._sum(tn, "sink:file:")[0], 2)
        self.assertEqual(self._sum(tn, "sink:spawn:")[0], 1)
        self.assertEqual(self._sum(to, "sink:file:")[0], 1)
        self.assertEqual(self._sum(to, "sink:spawn:")[0], 0)
        for t in (tn, to):
            fids = {f for (f, s) in t.counts}
            self.assertTrue(fids and all(f.startswith("skill/scripts/demo.py::") for f in fids), fids)
        self.assertIsNone(sys.getprofile())

    def test_main_returns_exit_code_and_prints_totals(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = self.gt.main(["--root", str(self.root), "--", "aidd", "demo", "fail"])
        self.assertEqual(rc, 3)
        self.assertIn("totals: reads", out.getvalue())
        self.assertIsNone(sys.getprofile())

    def test_unknown_command_is_rc_2(self):
        with contextlib.redirect_stderr(io.StringIO()):
            rc = self.gt.run_traced(self.root, ["aidd", "no-such-sub"])
        self.assertEqual(rc, 2)
        self.assertIsNone(sys.getprofile())


# ------------------------------------------------------------------------------------------ AC-015 status

NAMES = ("code", "method", "spec", "progress")


class TestGraphStatus(TempBase):  # AC-015 / FR-021
    def setUp(self):
        if not HAVE_GIT:
            self.skipTest("git is not available")
        super().setUp()
        self.init_git()
        self.put("skill/SKILL.md", SKILL_MD)
        self.put("src/app.py", "def run():\n    return 1\n")
        self.put("specs/001-x/spec.md", "# Spec\n")
        self.put("specs/001-x/tasks.md", "# Tasks\n\n### T-1\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "init")
        self.env = dict(os.environ)
        self.env["AIDD_GRAPHS"] = "off"

    def graphs(self, *args):
        r = subprocess.run([sys.executable, str(SCRIPTS_DIR / "aidd_graphs.py"), "--root", str(self.root)]
                           + list(args), capture_output=True, timeout=TIMEOUT, env=self.env)
        return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")

    def states(self):
        rc, out, err = self.graphs("status", "--json")
        self.assertEqual(rc, 0, err)
        return {r["name"]: r["state"] for r in json.loads(out)}

    def _refresh_all(self):
        for n in NAMES:
            rc, out, err = self.graphs("refresh", n, "--wait", "--force")
            self.assertEqual(rc, 0, "%s: %s %s" % (n, out, err))

    def test_four_graphs_refreshable_then_fresh(self):
        st = self.states()
        for n in NAMES:
            self.assertIn(n, st)
            self.assertNotEqual(st[n], "no-refresh", n)
        self._refresh_all()
        st = self.states()
        for n in NAMES:
            self.assertNotEqual(st[n], "no-refresh", n)
            self.assertNotEqual(st[n], "stale", "%s: %s" % (n, st))
            self.assertEqual(st[n], "fresh", "%s: %s" % (n, st))

    def test_edit_makes_only_watching_graph_stale_by_content_hash(self):
        self._refresh_all()
        p = self.root / "src" / "app.py"
        old = p.stat()
        p.write_bytes(b"def run():\n    return 2\n")          # same size, different content
        os.utime(str(p), ns=(old.st_atime_ns, old.st_mtime_ns))
        self.assertEqual(p.stat().st_size, old.st_size)
        st = self.states()
        self.assertEqual(st["code"], "stale", st)
        for n in ("method", "spec", "progress"):
            self.assertEqual(st[n], "fresh", "%s: %s" % (n, st))


if __name__ == "__main__":
    unittest.main()
