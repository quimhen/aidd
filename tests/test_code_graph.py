"""Spec 004 amendment (FR-014, FR-015, FR-023, FR-024; AC-009, AC-010, AC-016, AC-017): tests of
skill/scripts/code_graph.py and of `aidd_graphs refresh code`.

Every test builds a tiny git project in a temp dir; the evidence dir variable (with the testing flag) points at a
scratch dir so nothing reaches the real evidence log. Stdlib unittest; every subprocess has a timeout.
Run: python -m unittest tests.test_code_graph -v
"""
import contextlib
import io
import json
import os
import re
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

HAVE_GIT = shutil.which("git") is not None
SUMMARY_RE = re.compile(r"code graph: (\d+) files, re-parsed (\d+), reused (\d+), warnings (\d+)")
ENV_KEYS = ("AIDD_" + "EVIDENCE_DIR", "AIDD_" + "TESTING", "AIDD_" + "SESSION_ID")


def git(root, *args):
    r = subprocess.run(["git", *args], cwd=str(root), capture_output=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (args, r.stderr.decode(errors="replace")))


class Base(unittest.TestCase):
    def setUp(self):
        if not HAVE_GIT:
            self.skipTest("git is not available")
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name).resolve() / "proj"
        self.root.mkdir()
        evdir = Path(self._td.name).resolve() / "evd"
        evdir.mkdir()
        self._old = {k: os.environ.get(k) for k in ENV_KEYS}
        os.environ[ENV_KEYS[0]] = str(evdir)
        os.environ[ENV_KEYS[1]] = "1"
        os.environ.pop(ENV_KEYS[2], None)
        self.addCleanup(self._restore)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "t")
        git(self.root, "config", "core.autocrlf", "false")

    def _restore(self):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))
        return p

    def run_main(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cg.main(["--root", str(self.root)] + list(extra))
        return rc, out.getvalue(), err.getvalue()

    def stats(self, *extra):
        rc, out, _ = self.run_main(*extra)
        self.assertEqual(rc, 0)
        m = SUMMARY_RE.search(out)
        self.assertIsNotNone(m, out)
        return tuple(int(x) for x in m.groups())  # files, parsed, reused, warnings

    def graph(self):
        return json.loads((self.root / cg.GRAPH_REL).read_text(encoding="utf-8"))

    @staticmethod
    def node(g, nid):
        for n in g["nodes"]:
            if n["id"] == nid:
                return n
        return None

    @staticmethod
    def edges(g, src=None, rel=None, tgt=None):
        return [e for e in g["edges"] if (src is None or e["source"] == src) and (rel is None or e["relation"] == rel)
                and (tgt is None or e["target"] == tgt)]


class TestCalls(Base):
    def test_transitive_sink_and_syntax_error(self):  # AC-009
        self.write("m.py", "import subprocess\n\n\ndef b():\n    subprocess.run(['git', 'status'])\n\n\n"
                           "def a():\n    b()\n")
        self.write("bad.py", "def broken(:\n    pass\n")
        rc, _, err = self.run_main()
        self.assertEqual(rc, 0)
        g = self.graph()
        self.assertTrue(self.edges(g, "m.py::a", "calls", "m.py::b"))
        self.assertTrue(self.edges(g, "m.py::b", "spawns", "sink:spawn:git"))
        self.assertIsNotNone(self.node(g, "sink:spawn:git"))
        adj = {}
        for e in g["edges"]:
            if e["relation"] in ("calls", "spawns"):
                adj.setdefault(e["source"], set()).add(e["target"])
        seen, todo = set(), ["m.py::a"]
        while todo:
            cur = todo.pop()
            for nx in adj.get(cur, ()):
                if nx not in seen:
                    seen.add(nx)
                    todo.append(nx)
        self.assertIn("sink:spawn:git", seen)
        self.assertTrue(any("bad.py" in w for w in g["warnings"]), g["warnings"])
        self.assertIsNotNone(self.node(g, "bad.py"))
        self.assertIsNotNone(self.node(g, "m.py::a"))
        self.assertIn("bad.py", err)

    def test_ambiguity_and_ext(self):
        self.write("c1.py", "class A:\n    def process(self):\n        return 1\n\n\n"
                            "class B:\n    def process(self):\n        return 2\n\n\n"
                            "class C:\n    def many(self):\n        return 3\n\n\n"
                            "class D:\n    def many(self):\n        return 4\n")
        self.write("c2.py", "class E:\n    def many(self):\n        return 5\n\n\n"
                            "class F:\n    def many(self):\n        return 6\n")
        self.write("use.py", "def two(obj):\n    return obj.process()\n\n\n"
                             "def four(obj):\n    return obj.many()\n\n\n"
                             "def ext_user(items):\n    n = len(items)\n    items.append(n)\n    for i in items:\n"
                             "        items.append(i)\n    return n\n")
        self.assertEqual(self.stats()[3], 0)
        g = self.graph()
        two = self.edges(g, "use.py::two", "calls")
        self.assertEqual(len(two), 2)
        self.assertTrue(all(e.get("ambiguous") for e in two))
        self.assertEqual({e["target"] for e in two}, {"c1.py::A.process", "c1.py::B.process"})
        four = self.edges(g, "use.py::four", "calls")
        self.assertEqual([e["target"] for e in four], ["sink:unresolved:many"])
        f = self.node(g, "use.py::ext_user")
        self.assertIn("len", f["ext"])
        self.assertIn("append", f["ext"])
        self.assertEqual(self.edges(g, "use.py::ext_user", "calls"), [])
        self.assertIn("append", f["ext_in_loop"])
        self.assertNotIn("len", f.get("ext_in_loop", []))
        for e in g["edges"]:  # ambiguous / in_loop are written only when true
            self.assertNotIn(e.get("ambiguous"), (False,))
            self.assertNotIn(e.get("in_loop"), (False,))

    def test_implements_markers(self):
        self.write("impl.py", 'def latest():\n    """Does it. aidd:FR-205"""\n    return 1\n\n\n'
                              "def other():\n    # aidd:AC-001\n    return 2\n")
        self.stats()
        g = self.graph()
        self.assertTrue(self.edges(g, "impl.py::latest", "implements", "FR-205"))
        self.assertTrue(self.edges(g, "impl.py::other", "implements", "AC-001"))


class TestIncremental(Base):
    N = 5

    def seed(self):
        for i in range(self.N):
            self.write("pkg/f%d.py" % i, "def fn%d():\n    return %d\n" % (i, i))

    def test_reuse_counts(self):
        self.seed()
        self.assertEqual(self.stats()[:3], (self.N, self.N, 0))
        self.write("pkg/f0.py", "def fn0():\n    return 100\n")
        self.write("pkg/f1.py", "def fn1():\n    return 101\n\n\ndef extra():\n    return 1\n")
        self.assertEqual(self.stats()[:3], (self.N, 2, self.N - 2))
        self.assertEqual(self.stats()[:3], (self.N, 0, self.N))

    def test_same_size_older_mtime_is_reparsed(self):  # AC-017
        self.seed()
        self.stats()
        p = self.root / "pkg" / "f2.py"
        st = p.stat()
        p.write_bytes(b"def fn2():\n    return 9\n")  # same byte length as the original
        self.assertEqual(p.stat().st_size, st.st_size)
        os.utime(str(p), ns=(st.st_atime_ns, st.st_mtime_ns - 5_000_000_000))
        self.assertEqual(self.stats()[1], 1)

    def test_version_change_forces_full_parse(self):
        self.seed()
        self.stats()
        cache_path = self.root / (cg.GRAPH_REL + cg.CACHE_SUFFIX)
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        cache["extractor"] = cg.EXTRACTOR_VERSION + 100
        cache_path.write_text(json.dumps(cache), encoding="utf-8")
        self.assertEqual(self.stats()[:3], (self.N, self.N, 0))
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        cache["schema"] = cg.SCHEMA_VERSION + 100
        cache_path.write_text(json.dumps(cache), encoding="utf-8")
        self.assertEqual(self.stats()[1], self.N)

    def test_build_api_with_previous_cache(self):
        self.seed()
        g1, s1, cache, _ = cg.build_with_cache(self.root)
        self.assertEqual(s1["parsed"], self.N)
        g2, s2 = cg.build(self.root, previous=cache)
        self.assertEqual((s2["parsed"], s2["reused"]), (0, self.N))
        self.assertEqual({n["id"] for n in g1["nodes"]}, {n["id"] for n in g2["nodes"]})


class TestMirror(Base):
    def test_mirror_dedupe(self):
        body = "def shared():\n    return 1\n"
        self.write("skill/scripts/tool.py", body)
        self.write("adapters/dot-aidd/scripts/tool.py", body)
        self.assertEqual(self.stats()[0], 2)
        g = self.graph()
        canon = self.node(g, "skill/scripts/tool.py")
        copy = self.node(g, "adapters/dot-aidd/scripts/tool.py")
        self.assertNotIn("mirror_of", canon)
        self.assertEqual(copy["mirror_of"], "skill/scripts/tool.py")
        funcs = [n["id"] for n in g["nodes"] if n["type"] == "FUNC"]
        self.assertEqual(funcs, ["skill/scripts/tool.py::shared"])


class TestRegistryCommand(Base):
    def cli(self, *args):
        r = subprocess.run([sys.executable, str(SCRIPTS_DIR / "aidd_graphs.py"), "--root", str(self.root)] + list(args),
                           cwd=str(self.root), capture_output=True, timeout=180, env=dict(os.environ))
        return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")

    def test_refresh_wait_force_and_show(self):  # AC-016, AC-010
        self.write("svc.py", "import subprocess\n\n\ndef leaf():\n    subprocess.run(['git', 'log'])\n\n\n"
                             "def latest_run():\n    \"\"\"Newest run. aidd:FR-205\"\"\"\n    leaf()\n\n\n"
                             "def top():\n    latest_run()\n")
        rc, out, err = self.cli("refresh", "code", "--wait", "--force")
        self.assertEqual(rc, 0, out + err)
        m = re.search(r"re-parsed (\d+), reused (\d+)", out)
        self.assertIsNotNone(m, out)
        self.assertEqual((m.group(1), m.group(2)), ("1", "0"))
        rc, out, err = self.cli("show", "code", "latest_run")
        self.assertEqual(rc, 0, out + err)
        self.assertLessEqual(len(out.strip().splitlines()), 25)
        self.assertIn("latest_run", out)
        self.assertIn("top", out)    # caller
        self.assertIn("leaf", out)   # callee
        self.assertIn("FR-205", out)


if __name__ == "__main__":
    unittest.main()
