"""Spec 009 (T-06): the Gemini / OpenCode host gate. Tests against the CONTRACT of plan.md Interface 1:

    python skill/hooks/host_adapter.py <gemini|opencode> <pre|post>   (host JSON on stdin)
    exit 0 allow, exit 2 block (stderr = rule_gate message), stdout empty on pre and post.

The adapter spawns skill/hooks/rule_gate.py, so these tests run the adapter as a REAL subprocess and reuse the
gate fixtures (tests/gate_fixtures.py) to build the project, the open spec and the approval. The AIDD_* env
names below are TEST-side only (they are forbidden in agent shell commands, not in test code).
FR-904 FR-905 FR-906 FR-907 FR-908 FR-911 FR-912 / AC-001 AC-002 AC-003 AC-006."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_fixtures import (  # noqa: E402
    Base, EV, HOOKS_DIR, REPO, R, SID, approved_tasks, tasks_text, verified_spec, _common,
)

ADAPTER = HOOKS_DIR / "host_adapter.py"
PLUGIN = REPO / "adapters" / "opencode" / "plugins" / "aidd.js"
STATUS_SCRIPT = REPO / "skill" / "scripts" / "aidd_status.py"
TASKS = "specs/001-x/tasks.md"
SPEC = "specs/001-x/spec.md"
CLAUDE_ONLY = ("invoke the skill", "skill tool", "invoke aidd")     # FR-912: Claude-only wording must never show

# host -> logical tool kind -> the host's own tool name
TOOL = {
    "gemini": {"write": "write_file", "edit": "replace", "bash": "run_shell_command", "read": "read_file",
               "glob": "glob", "web": "web_fetch"},
    "opencode": {"write": "write", "edit": "edit", "bash": "bash", "read": "read", "glob": "glob",
                 "web": "webfetch"},
}
HOSTS = ("gemini", "opencode")


def payload(host, kind, root, rel=None, command=None, session=SID, phase="pre", cwd=None):
    """The host's own event for a logical tool call (`kind`: write|edit|bash|read|glob|web)."""
    path = str(Path(root) / rel) if rel else None
    gem = host == "gemini"
    if kind == "write":
        args = {"file_path": path, "content": "x = 1\n"} if gem else {"filePath": path, "content": "x = 1\n"}
    elif kind == "edit":
        args = ({"file_path": path, "old_string": "x1 = 1", "new_string": "x1 = 2"} if gem else
                {"filePath": path, "oldString": "x1 = 1", "newString": "x1 = 2"})
    elif kind == "bash":
        args = {"command": command}
    elif kind == "read":
        args = {"file_path": path} if gem else {"filePath": path}
    elif kind == "glob":
        args = {"pattern": "**/*.py"}
    else:
        args = {"url": "https://example.com"}
    name = TOOL[host][kind]
    if gem:
        return {"session_id": session, "cwd": str(cwd or root),
                "hook_event_name": "BeforeTool" if phase == "pre" else "AfterTool",
                "tool_name": name, "tool_input": args, **({"tool_response": {}} if phase == "post" else {})}
    return {"sessionID": session, "cwd": str(cwd or root), "tool": name, "args": args}


class HostBase(Base):
    """An AIDD project (.aidd/AIDD.md) with spec 001-x OPEN and its tasks.md still PENDING (code is blocked)."""

    def setUp(self):
        super().setUp()
        self.put(".aidd/AIDD.md", "# AIDD\n")
        self.put(TASKS, tasks_text())
        self.open_spec()

    def approve(self):
        self.put(TASKS, approved_tasks())
        self.open_spec()
        self.approve_spec()

    def adapt(self, host, phase, event=None, env=None, raw=None, cwd=None, session=None):
        e = dict(self.env)
        for k, v in (env or {}).items():
            if v is None:
                e.pop(k, None)
            else:
                e[k] = v
        data = raw if raw is not None else json.dumps(event).encode("utf-8")
        r = subprocess.run([sys.executable, str(ADAPTER), host, phase], input=data, capture_output=True,
                           cwd=str(cwd or self.root), env=e, timeout=90)
        r.out = r.stdout.decode("utf-8", "replace")
        r.err = r.stderr.decode("utf-8", "replace")
        return r

    def pre(self, host, kind, rel=None, command=None, env=None, **kw):
        return self.adapt(host, "pre", payload(host, kind, self.root, rel, command, session=self.session, **kw),
                          env=env)

    def post(self, host, kind, rel=None, **kw):
        return self.adapt(host, "post", payload(host, kind, self.root, rel, session=self.session, phase="post", **kw))

    def assertBlockedBy(self, r, *needles):
        self.assertEqual(r.returncode, 2, f"expected a block, got rc={r.returncode} err={r.err!r} out={r.out!r}")
        self.assertNotIn("Traceback", r.err)
        self.assertTrue(r.err.strip(), "a block is never silent")
        self.assertEqual(r.out.strip(), "", "stdout must stay empty on pre (Gemini parses it as JSON)")
        for n in needles:
            self.assertIn(n.lower(), r.err.lower(), r.err)

    def assertOk(self, r):
        self.assertEqual(r.returncode, 0, f"expected allow, got rc={r.returncode} err={r.err!r} out={r.out!r}")
        self.assertNotIn("Traceback", r.err)
        self.assertEqual(r.out.strip(), "", "stdout must stay empty")


class TestAc001NoApproval(HostBase):
    def test_ac001_gemini_write_file_blocked_without_approval(self):
        """AC-001 / FR-904: no valid approval -> exit 2 and stderr names the next action."""
        r = self.pre("gemini", "write", "src/app.py")
        self.assertBlockedBy(r, "R6", "next action", "approv")

    def test_fr904_every_write_shape_of_both_hosts_is_blocked(self):
        for host in HOSTS:
            for kind, rel in (("write", "src/app.py"), ("edit", "src/cart.py")):
                with self.subTest(host=host, kind=kind):
                    self.assertBlockedBy(self.pre(host, kind, rel), "R6", "next action")

    def test_fr904_code_gate_does_not_apply_to_docs_and_specs_notes(self):
        for host in HOSTS:
            with self.subTest(host=host):
                self.assertOk(self.pre(host, "write", "README.md"))
                self.assertOk(self.pre(host, "write", "notes.txt"))


class TestAc002Approved(HostBase):
    def test_ac002_approved_write_allowed_records_code_edit_no_claude_message(self):
        """AC-002 / FR-912: valid approval -> exit 0; `post` appends code_edit; no Claude-only wording."""
        self.approve()
        for host in HOSTS:
            with self.subTest(host=host):
                before = len(self.events("code_edit"))
                r = self.pre(host, "write", "src/app.py")
                self.assertOk(r)
                blob = (r.out + r.err).lower()
                for marker in CLAUDE_ONLY:
                    self.assertNotIn(marker, blob)
                self.assertTrue(_common.marker_path(self.session).exists(),
                                "the adapter must create the session 'AIDD invoked' marker (FR-912)")
                rp = self.post(host, "write", "src/app.py")
                self.assertOk(rp)
                evs = self.events("code_edit")
                self.assertGreater(len(evs), before, "post must append a code_edit event")
                self.assertTrue(any("app.py" in str((e.get("detail") or {}).get("path", "")) for e in evs), evs)

    def test_fr912_unapproved_block_never_says_invoke_the_skill(self):
        for host in HOSTS:
            with self.subTest(host=host):
                r = self.pre(host, "write", "src/app.py")
                self.assertBlockedBy(r)
                for marker in CLAUDE_ONLY:
                    self.assertNotIn(marker, r.err.lower())


class TestAc003GateTarget(HostBase):
    def test_ac003_only_the_gate_target_counts_and_the_pointer_switches(self):
        """AC-003 / FR-904: many open specs; the approved one targeted -> allowed; the pending one -> blocked."""
        self.approve()                                           # 001-x approved
        for n in range(2, 8):                                    # six more open, unapproved specs
            sid = f"00{n}-s{n}"
            (self.root / "specs" / sid).mkdir()
            self.put(f"specs/{sid}/tasks.md", tasks_text())
            self.open_spec(sid)
        self.assertTrue(EV.activate_spec(self.root, "001-x"))
        self.assertOk(self.pre("gemini", "write", "src/app.py"))
        self.assertTrue(EV.activate_spec(self.root, "002-s2"))
        r = self.pre("gemini", "write", "src/app.py")
        self.assertBlockedBy(r, "R6", "002-s2", "aidd rules activate")
        self.assertNotIn("003-s3", r.err)                        # never one violation per open spec
        self.assertTrue(EV.activate_spec(self.root, "001-x"))
        self.assertOk(self.pre("opencode", "write", "src/app.py"))


class TestAc006ReviewApproval(HostBase):
    def test_ac006_aidd_rules_approve_records_approval_then_write_allowed(self):
        """AC-006: `aidd rules approve` (real script) records the approval; the next code write is allowed.

        Simplification stated: the owner's consent is simulated with the tagged recorded answer (the typed
        fallback of plan Interface 1), because a real review.html + review.md + consent fixture costs far more
        than this test is worth; the `rules approve` -> `approved` event -> gate path is the real one."""
        self.put(SPEC, verified_spec(), age=200)
        self.put(TASKS, tasks_text())
        self.open_spec()
        self.assertBlockedBy(self.pre("gemini", "write", "src/app.py"), "R6")
        self.answer("Approve these tasks?", "Approve")
        env = dict(self.env, AIDD_SESSION_ID=self.session, PYTHONIOENCODING="utf-8")
        r = subprocess.run([sys.executable, str(STATUS_SCRIPT), "rules", "approve", str(self.root / "specs" / "001-x")],
                           cwd=str(self.root), env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self.events("approved"), "the approved event must be recorded")
        self.assertTrue(R.approval_valid((self.root / TASKS).read_text(encoding="utf-8")))
        for host in HOSTS:
            with self.subTest(host=host):
                self.assertOk(self.pre(host, "write", "src/app.py"))


class TestNonWriteAndMalformed(HostBase):
    def test_non_write_tools_exit_zero_even_with_a_pending_spec(self):
        for host in HOSTS:
            for kind, rel in (("read", "src/cart.py"), ("glob", None), ("web", None)):
                with self.subTest(host=host, kind=kind):
                    self.assertOk(self.pre(host, kind, rel))

    def test_malformed_json_exits_zero(self):
        for host in HOSTS:
            for raw in (b"{not json", b"", b"[1, 2]", b"\xff\xfe"):
                with self.subTest(host=host, raw=raw):
                    r = self.adapt(host, "pre", raw=raw)
                    self.assertEqual(r.returncode, 0, r.err)
                    self.assertNotEqual(r.returncode, 2)

    def test_unknown_host_tool_without_a_name_exits_zero(self):
        self.assertEqual(self.adapt("gemini", "pre", {"session_id": self.session, "cwd": str(self.root)}).returncode, 0)
        self.assertEqual(self.adapt("opencode", "pre", {"sessionID": self.session, "cwd": str(self.root)}).returncode, 0)


class TestFr912NoAiddProject(unittest.TestCase):
    def test_fr912_no_aidd_md_in_the_cwd_tree_exits_zero_without_calling_the_gate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            (root / "src").mkdir()
            env = {k: v for k, v in os.environ.items() if k not in ("AIDD_RULES",)}
            for host in HOSTS:
                for phase in ("pre", "post"):
                    with self.subTest(host=host, phase=phase):
                        ev = payload(host, "write", root, "src/app.py", session="s-none", phase=phase)
                        r = subprocess.run([sys.executable, str(ADAPTER), host, phase],
                                           input=json.dumps(ev).encode(), capture_output=True, cwd=str(root),
                                           env=env, timeout=90)
                        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
                        self.assertEqual(r.stdout.strip(), b"")
            self.assertFalse((root / ".aidd").exists(), "the adapter must not create .aidd outside a project")


class TestPathWithSpaces(unittest.TestCase):
    def test_project_path_with_spaces_gates_block_then_allow(self):
        td = tempfile.TemporaryDirectory(prefix="aidd host ")
        evd = tempfile.TemporaryDirectory(prefix="aidd evd ")
        self.addCleanup(td.cleanup)
        self.addCleanup(evd.cleanup)
        root = Path(td.name).resolve()
        self.assertIn(" ", str(root))
        (root / ".aidd").mkdir()
        (root / ".aidd" / "AIDD.md").write_text("# AIDD\n", encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / "cart.py").write_text("x1 = 1\n", encoding="utf-8")
        (root / "specs" / "001-x").mkdir(parents=True)
        tasks = root / "specs" / "001-x" / "tasks.md"
        tasks.write_text(tasks_text(), encoding="utf-8", newline="\n")
        env = {k: v for k, v in os.environ.items() if k != "AIDD_RULES"}
        env.update(AIDD_EVIDENCE_DIR=evd.name, AIDD_TESTING="1", AIDD_R7_FIX_EDITS="0", AIDD_R5_FIX_EDITS="0")
        old = {k: os.environ.get(k) for k in ("AIDD_EVIDENCE_DIR", "AIDD_TESTING")}
        os.environ.update(AIDD_EVIDENCE_DIR=evd.name, AIDD_TESTING="1")

        def restore():
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.addCleanup(restore)
        sess = "s-spaces"
        self.addCleanup(lambda: _common.marker_path(sess).unlink(missing_ok=True))
        self.addCleanup(lambda: _common.timestamps_path(sess).unlink(missing_ok=True))
        time.sleep(0.02)
        EV.append(root, sess, "spec_edit", path=str(tasks), spec="001-x", file="tasks.md")
        time.sleep(0.02)

        def run(host):
            ev = payload(host, "write", root, "src/app.py", session=sess)
            return subprocess.run([sys.executable, str(ADAPTER), host, "pre"], input=json.dumps(ev).encode(),
                                  capture_output=True, cwd=str(root), env=env, timeout=90)

        for host in HOSTS:
            r = run(host)
            self.assertEqual(r.returncode, 2, r.stderr.decode("utf-8", "replace"))
        text = approved_tasks()
        tasks.write_text(text, encoding="utf-8", newline="\n")
        time.sleep(0.02)
        EV.append(root, sess, "spec_edit", path=str(tasks), spec="001-x", file="tasks.md")
        time.sleep(0.02)
        EV.append_approved(root, sess, "001-x", R.approval_hash(text))
        time.sleep(0.02)
        for host in HOSTS:
            r = run(host)
            self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))


class TestFr907Fr911Protected(HostBase):
    BLOCKED = (".aidd/x", ".gemini/settings.json", ".opencode/opencode.json", ".opencode/plugins/aidd.js")
    ALLOWED = (".opencode/skills/x.md", ".opencode/plugins/graphify.js")

    def test_fr907_fr911_protected_paths_blocked_on_both_hosts(self):
        for host in HOSTS:
            for rel in self.BLOCKED:
                for kind in ("write", "edit"):
                    with self.subTest(host=host, rel=rel, kind=kind):
                        self.assertBlockedBy(self.pre(host, kind, rel))

    def test_fr911_neighbours_stay_writable(self):
        """Not an AIDD-gated file: no approval needed (spec closed) -> allowed, so the protection is narrow."""
        self.close_spec()
        for host in HOSTS:
            for rel in self.ALLOWED:
                with self.subTest(host=host, rel=rel):
                    self.assertOk(self.pre(host, "write", rel))

    def test_fr907_shell_redirect_into_aidd_is_blocked_and_plain_shell_is_allowed(self):
        for host in HOSTS:
            with self.subTest(host=host):
                self.assertBlockedBy(self.pre(host, "bash", command="echo x > .aidd/x"))
                self.assertOk(self.pre(host, "bash", command="ls -la"))


class TestFr908Override(HostBase):
    def test_fr908_aidd_rules_warn_allows_and_records_rules_override(self):
        before = len(self.events("rules_override"))
        for host in HOSTS:
            with self.subTest(host=host):
                r = self.pre(host, "write", "src/app.py", env={"AIDD_RULES": "warn"})
                self.assertEqual(r.returncode, 0, r.err)
                self.assertEqual(r.out.strip(), "")
        self.assertGreater(len(self.events("rules_override")), before, "rules_override must be recorded")

    def test_fr908_without_the_env_the_same_write_still_blocks(self):
        self.assertBlockedBy(self.pre("gemini", "write", "src/app.py"), "R6")


def _env_payload(host, tool, root, args, session):
    if host == "gemini":
        return {"session_id": session, "cwd": str(root), "hook_event_name": "BeforeTool", "tool_name": tool,
                "tool_input": args}
    return {"sessionID": session, "cwd": str(root), "tool": tool, "args": args}


class TestS3UnknownTools(HostBase):
    """S3: tools outside the known list are gated by name pattern when they carry a path."""

    def test_s3_unknown_apply_patch_with_code_file_blocked_without_approval(self):
        patch = "*** Begin Patch\n*** Add File: src/app.py\n+x = 1\n*** End Patch\n"
        ev = _env_payload("opencode", "apply_patch", self.root, {"patchText": patch}, self.session)
        self.assertBlockedBy(self.adapt("opencode", "pre", ev), "R6")

    def test_s3_unknown_apply_patch_allowed_when_approved(self):
        self.approve()
        patch = "*** Begin Patch\n*** Update File: src/cart.py\n-x1 = 1\n+x1 = 2\n*** End Patch\n"
        ev = _env_payload("opencode", "apply_patch", self.root, {"patchText": patch}, self.session)
        self.assertOk(self.adapt("opencode", "pre", ev))

    def test_s3_unknown_create_file_with_filepath_blocked(self):
        for host in HOSTS:
            with self.subTest(host=host):
                ev = _env_payload(host, "create_file", self.root,
                                  {"filePath": str(self.root / "src" / "app.py"), "content": "x = 1\n"}, self.session)
                self.assertBlockedBy(self.adapt(host, "pre", ev), "R6")

    def test_s3_unknown_write_like_tool_without_a_path_exits_zero(self):
        for host in HOSTS:
            with self.subTest(host=host):
                ev = _env_payload(host, "write_something", self.root, {"content": "x"}, self.session)
                self.assertOk(self.adapt(host, "pre", ev))

    def test_s3_read_like_tools_exit_zero(self):
        for host in HOSTS:
            for tool, args in (("read_file", {"file_path": str(self.root / "src" / "cart.py")}),
                               ("grep", {"pattern": "x", "path": str(self.root / "src")})):
                with self.subTest(host=host, tool=tool):
                    self.assertOk(self.adapt(host, "pre", _env_payload(host, tool, self.root, args, self.session)))


class TestS6SessionSanitized(HostBase):
    def test_s6_hostile_session_id_gives_safe_marker_and_same_exit_codes(self):
        marker_dir = _common.marker_path("probe-x").parent
        before = set(os.listdir(marker_dir)) if marker_dir.exists() else set()

        def cleanup():
            if marker_dir.exists():
                for n in set(os.listdir(marker_dir)) - before:
                    if (marker_dir / n).is_file():
                        (marker_dir / n).unlink()
        self.addCleanup(cleanup)
        hostile = "../x y"
        for host in HOSTS:
            with self.subTest(host=host):
                ev = payload(host, "write", self.root, "src/app.py", session=hostile)
                self.assertBlockedBy(self.adapt(host, "pre", ev), "R6")
        self.approve()
        for host in HOSTS:
            with self.subTest(host=host, approved=True):
                ev = payload(host, "write", self.root, "src/app.py", session=hostile)
                self.assertEqual(self.adapt(host, "pre", ev).returncode, 0)
        new = set(os.listdir(marker_dir)) - before if marker_dir.exists() else set()
        for name in new:
            self.assertNotIn(" ", name)
            self.assertNotIn("..", name)
        self.assertFalse((marker_dir.parent / "x y").exists())


class TestS1EnvProtection(HostBase):
    def _env_event(self, host, kind, rel, text):
        ev = payload(host, kind, self.root, rel)
        args = ev["tool_input"] if host == "gemini" else ev["args"]
        for k in ("content", "new_string", "newString"):
            if k in args:
                args[k] = text
        return ev

    def test_s1_env_with_aidd_rules_off_blocked_write_and_edit_both_hosts(self):
        self.close_spec()
        for host in HOSTS:
            for kind in ("write", "edit"):
                for text in ("AIDD_RULES=off\n", "aidd_testing=1\n", "AIDD_EVIDENCE_DIR=/tmp\n",
                             "AIDD_SESSION_ID=z\n"):
                    with self.subTest(host=host, kind=kind, text=text):
                        self.assertBlockedBy(self.adapt(host, "pre", self._env_event(host, kind, ".env", text)))

    def test_s1_env_dot_variant_with_aidd_rules_blocked(self):
        self.close_spec()
        for host in HOSTS:
            with self.subTest(host=host):
                self.assertBlockedBy(self.adapt(host, "pre",
                                                self._env_event(host, "write", ".env.local", "AIDD_RULES=off\n")))

    def test_s1_env_with_other_content_allowed(self):
        self.close_spec()
        for host in HOSTS:
            for kind in ("write", "edit"):
                with self.subTest(host=host, kind=kind):
                    self.assertOk(self.adapt(host, "pre", self._env_event(host, kind, ".env", "SUPABASE_URL=x\n")))

    def test_s1_gemini_dot_env_fully_protected(self):
        self.close_spec()
        for host in HOSTS:
            for kind in ("write", "edit"):
                with self.subTest(host=host, kind=kind):
                    self.assertBlockedBy(self.adapt(host, "pre",
                                                    self._env_event(host, kind, ".gemini/.env", "SUPABASE_URL=x\n")))


@unittest.skipUnless(shutil.which("node"), "node not installed: the aidd.js throw path cannot be exercised")
class TestOpenCodePluginNode(HostBase):
    """FR-905: aidd.js really throws on an adapter exit 2. The plugin spawns `<dir>/.aidd/hooks/host_adapter.py`,
    so the temp project gets a shim there that runs the repo's adapter (rule_gate finds its own scripts)."""

    DRIVER = """
import { pathToFileURL } from "node:url";
const [, , pluginPath, dir, sess] = process.argv;
const mod = await import(pathToFileURL(pluginPath).href);
const hooks = await mod.AiddPlugin({ directory: dir });
const out = {};
const attempt = async (name, tool, args) => {
  try { await hooks["tool.execute.before"]({ tool, sessionID: sess, callID: name }, { args }); out[name] = { threw: false }; }
  catch (e) { out[name] = { threw: true, message: String(e && e.message) }; }
};
await attempt("blocked", "write", { filePath: dir + "/src/app.py", content: "x = 1\\n" });
await attempt("read", "read", { filePath: dir + "/src/cart.py" });
let afterThrew = false;
try { await hooks["tool.execute.after"]({ tool: "read", sessionID: sess, args: {} }); } catch (e) { afterThrew = true; }
out.afterThrew = afterThrew;
console.log(JSON.stringify(out));
"""

    def _node(self, project):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        plugin = Path(tmp.name) / "aidd.mjs"                     # .js would be CommonJS without a package.json
        plugin.write_text(PLUGIN.read_text(encoding="utf-8"), encoding="utf-8")
        driver = Path(tmp.name) / "driver.mjs"
        driver.write_text(self.DRIVER, encoding="utf-8")
        env = dict(self.env)
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        r = subprocess.run([shutil.which("node"), str(driver), str(plugin), str(project), self.session],
                           capture_output=True, env=env, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        return json.loads(r.stdout.decode("utf-8").strip().splitlines()[-1])

    def test_fr905_plugin_throws_on_a_blocked_write_and_lets_reads_through(self):
        hooks = self.root / ".aidd" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        (hooks / "host_adapter.py").write_text(
            "import runpy, sys\nrunpy.run_path(%r, run_name='__main__')\n" % str(ADAPTER), encoding="utf-8")
        out = self._node(self.root)
        self.assertTrue(out["blocked"]["threw"], out)
        self.assertIn("R6", out["blocked"]["message"])
        self.assertFalse(out["read"]["threw"], out)
        self.assertFalse(out["afterThrew"], "tool.execute.after never throws")

    def test_fr905_plugin_is_a_noop_outside_an_aidd_project(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "src").mkdir()
            out = self._node(Path(td))
        self.assertFalse(out["blocked"]["threw"], out)


@unittest.skipUnless(shutil.which("node"), "node not installed: the aidd.js spawn path cannot be exercised")
class TestP1PluginSkipsNonGated(HostBase):
    """P1: for non-gated tools aidd.js spawns nothing; a gated tool still spawns the adapter."""

    DRIVER = """
import { pathToFileURL } from "node:url";
import { readFileSync, existsSync } from "node:fs";
const [, , pluginPath, dir, sess, log] = process.argv;
const mod = await import(pathToFileURL(pluginPath).href);
const hooks = await mod.AiddPlugin({ directory: dir });
const count = () => (existsSync(log) ? readFileSync(log, "utf8").split("\\n").filter(Boolean).length : 0);
const out = {};
for (const [tool, args] of [["read", { filePath: dir + "/src/cart.py" }], ["grep", { pattern: "x" }],
                            ["glob", { pattern: "*" }], ["list", { path: dir }]]) {
  await hooks["tool.execute.before"]({ tool, sessionID: sess, callID: tool }, { args });
  await hooks["tool.execute.after"]({ tool, sessionID: sess, args });
}
out.afterReads = count();
try { await hooks["tool.execute.before"]({ tool: "write", sessionID: sess, callID: "w" },
                                         { args: { filePath: dir + "/src/app.py", content: "x = 1\\n" } });
      out.threw = false; } catch (e) { out.threw = true; }
out.afterWrite = count();
console.log(JSON.stringify(out));
"""

    def test_p1_reads_spawn_nothing_and_a_blocked_write_spawns_the_adapter(self):
        hooks = self.root / ".aidd" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        log = Path(tmp.name) / "spawns.log"
        (hooks / "host_adapter.py").write_text(
            "import runpy, sys\nwith open(%r, 'a') as f:\n    f.write('run\\n')\n"
            "runpy.run_path(%r, run_name='__main__')\n" % (str(log), str(ADAPTER)), encoding="utf-8")
        plugin = Path(tmp.name) / "aidd.mjs"
        plugin.write_text(PLUGIN.read_text(encoding="utf-8"), encoding="utf-8")
        driver = Path(tmp.name) / "driver.mjs"
        driver.write_text(self.DRIVER, encoding="utf-8")
        env = dict(self.env)
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        r = subprocess.run([shutil.which("node"), str(driver), str(plugin), str(self.root), self.session, str(log)],
                           capture_output=True, env=env, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        out = json.loads(r.stdout.decode("utf-8").strip().splitlines()[-1])
        self.assertEqual(out["afterReads"], 0, "non-gated tools must not spawn the adapter")
        self.assertTrue(out["threw"], out)
        self.assertGreaterEqual(out["afterWrite"], 1, "a gated write must spawn the adapter")


class TestSecurityRegressions(HostBase):
    """Closing-audit findings that an agent or a multi-root host could trigger on purpose."""

    def test_padded_shell_command_never_skips_the_gate(self):
        """A shell command padded to ~12 KB used to make rule_gate time out and the adapter fail OPEN."""
        cmd = "echo " + "a " * 6000 + "; echo x > specs/001-x/tasks.md"
        self.assertGreater(len(cmd), 10000)
        r = self.pre("gemini", "bash", command=cmd)
        self.assertEqual(r.returncode, 2, f"a padded command must stay blocked, got rc={r.returncode} err={r.err!r}")
        self.assertEqual(r.out.strip(), "")

    def test_event_cwd_outside_the_project_still_gates_an_absolute_path(self):
        """A host whose event cwd is a foreign folder (multi-root workspace) must not skip the project's gate."""
        import tempfile
        with tempfile.TemporaryDirectory() as other:
            for host in ("gemini", "opencode"):
                with self.subTest(host=host):
                    ev = payload(host, "write", self.root, "src/app.py", session=self.session, cwd=other)
                    self.assertBlockedBy(self.adapt(host, "pre", ev, cwd=other), "R6")

    def test_event_cwd_outside_and_no_project_anywhere_is_still_a_noop(self):
        import tempfile
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            for host in ("gemini", "opencode"):
                with self.subTest(host=host):
                    ev = payload(host, "write", a, "src/app.py", session=self.session, cwd=b)
                    self.assertOk(self.adapt(host, "pre", ev, cwd=b))


def agy_payload(tool, root, rel=None, command=None, conv=None, phase="pre", cwd_arg=None, workspace=True):
    """An Antigravity (agy 1.0.13) hook payload, key names as captured from the real binary (spec 011).

    `tool` is write_to_file | replace_file_content | run_command | view_file | None (toolCall null)."""
    target = str(Path(root) / rel).replace("\\", "/") if rel else None
    if tool == "write_to_file":
        call = {"name": tool, "args": {"TargetFile": target, "CodeContent": "x = 1\n", "Overwrite": True,
                                       "Description": "write a file", "toolAction": "Creating file",
                                       "toolSummary": "create"}}
    elif tool == "replace_file_content":
        call = {"name": tool, "args": {"TargetFile": target, "TargetContent": "x1 = 1",
                                       "ReplacementContent": "x1 = 2", "StartLine": 1, "EndLine": 1,
                                       "AllowMultiple": False, "Instruction": "change x1"}}
    elif tool == "run_command":
        call = {"name": tool, "args": {"CommandLine": command, "Cwd": str(cwd_arg or root).replace("\\", "/"),
                                       "WaitMsBeforeAsync": 500}}
    elif tool == "view_file":
        call = {"name": tool, "args": {"AbsolutePath": target}}
    else:
        call = None
    ev = {"toolCall": call, "conversationId": conv or SID, "stepIdx": 3, "modelName": "gemini-3",
          "transcriptPath": "", "artifactDirectoryPath": ""}
    if workspace:
        ev["workspacePaths"] = [str(root).replace("\\", "/")]
    if phase == "post":
        ev["error"] = None
    return ev


class AgyBase(HostBase):
    """Runs `host_adapter.py antigravity pre|post`: exit 0 always, ONE JSON object on stdout."""

    def agy(self, phase, event=None, raw=None, cwd=None):
        r = self.adapt("antigravity", phase, event, raw=raw, cwd=cwd)
        self.assertEqual(r.returncode, 0, f"antigravity exits 0 always: rc={r.returncode} err={r.err!r}")
        self.assertNotIn("Traceback", r.err)
        try:
            r.obj = json.loads(r.out)
        except ValueError:
            self.fail(f"stdout must be ONE JSON object, got {r.out!r}")
        self.assertIsInstance(r.obj, dict)
        return r

    def apre(self, tool, rel=None, command=None, conv=None, cwd=None, **kw):
        return self.agy("pre", agy_payload(tool, self.root, rel, command, conv=conv or self.session, **kw), cwd=cwd)

    def apost(self, tool, rel=None, command=None, **kw):
        return self.agy("post", agy_payload(tool, self.root, rel, command, conv=self.session, phase="post", **kw))

    def assertDeny(self, r, *needles):
        self.assertEqual(r.obj.get("decision"), "deny", f"expected deny, got {r.out!r}")
        self.assertTrue(str(r.obj.get("reason", "")).strip(), "a deny always carries a reason")
        for n in needles:
            self.assertIn(n.lower(), r.obj["reason"].lower(), r.obj["reason"])

    def assertAllow(self, r):
        self.assertEqual(r.obj.get("decision"), "allow", f"expected allow, got {r.out!r}")


class TestAgyAdapterProtocol(AgyBase):
    def test_ac1101_write_to_file_denied_without_approval(self):
        r = self.apre("write_to_file", "src/app.py")
        self.assertDeny(r, "R6")

    def test_ac1102_replace_file_content_denied_and_plain_command_allowed(self):
        self.assertDeny(self.apre("replace_file_content", "src/cart.py"), "R6")
        self.assertAllow(self.apre("run_command", command="echo done"))

    def test_ac1102_run_command_writing_a_protected_path_is_denied(self):
        self.assertDeny(self.apre("run_command", command="echo x > specs/001-x/tasks.md"))

    def test_approved_write_allowed_and_post_records_code_edit(self):
        self.approve()
        for tool, rel in (("write_to_file", "src/app.py"), ("replace_file_content", "src/cart.py")):
            with self.subTest(tool=tool):
                r = self.apre(tool, rel)
                self.assertAllow(r)
                self.assertEqual(r.obj, {"decision": "allow"})
        before = len(self.events("code_edit"))
        r = self.apost("write_to_file", "src/app.py")
        self.assertEqual(r.obj, {})
        evs = self.events("code_edit")
        self.assertGreater(len(evs), before, "post must append a code_edit event")
        self.assertTrue(any("app.py" in str((e.get("detail") or {}).get("path", "")) for e in evs), evs)

    def test_view_file_is_allowed_untouched(self):
        self.assertAllow(self.apre("view_file", "src/cart.py"))

    def test_ac1104_post_with_null_toolcall_prints_empty_object(self):
        r = self.agy("post", {"toolCall": None})
        self.assertEqual(r.obj, {})
        r = self.apost(None)
        self.assertEqual(r.obj, {})

    def test_pre_with_null_toolcall_is_allowed(self):
        self.assertAllow(self.apre(None))

    def test_post_of_a_non_write_tool_prints_empty_object(self):
        self.assertEqual(self.apost("view_file", "src/cart.py").obj, {})


class TestAgyProjectRoot(AgyBase):
    def test_root_from_workspace_paths_when_process_cwd_is_foreign(self):
        with tempfile.TemporaryDirectory() as other:
            self.assertDeny(self.apre("write_to_file", "src/app.py", cwd=other), "R6")

    def test_root_from_workspace_paths_when_process_cwd_is_dot_agents(self):
        agents = self.root / ".agents"
        agents.mkdir(exist_ok=True)
        self.assertDeny(self.apre("write_to_file", "src/app.py", cwd=agents), "R6")
        self.approve()
        self.assertAllow(self.apre("write_to_file", "src/app.py", cwd=agents))

    def test_root_from_the_target_file_when_workspace_paths_is_missing(self):
        with tempfile.TemporaryDirectory() as other:
            self.assertDeny(self.apre("write_to_file", "src/app.py", cwd=other, workspace=False), "R6")

    def test_no_project_anywhere_is_allowed(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            ev = agy_payload("write_to_file", a, "src/app.py", conv=self.session)
            self.assertAllow(self.agy("pre", ev, cwd=b))
            self.assertEqual(self.agy("post", agy_payload("write_to_file", a, "src/app.py", phase="post"),
                                      cwd=b).obj, {})


class TestAgyMalformedInput(AgyBase):
    def test_garbage_empty_and_invalid_utf8_stdin_allow(self):
        for raw in (b"{not json", b"", b"[1, 2]", b"\xff\xfe", b"null"):
            with self.subTest(raw=raw):
                self.assertAllow(self.agy("pre", raw=raw))
                self.assertEqual(self.agy("post", raw=raw).obj, {})

    def test_event_without_toolcall_key_allows(self):
        self.assertAllow(self.agy("pre", {"conversationId": self.session, "workspacePaths": [str(self.root)]}))

    def test_hostile_conversation_id_is_sanitized_and_decisions_hold(self):
        for conv in ("../../evil\\x:*?\"<>|", "a\nb\r\n\t", "x" * 600, "é中😀", ""):
            with self.subTest(conv=conv):
                ev = agy_payload("write_to_file", self.root, "src/app.py", conv=conv or None)
                ev["conversationId"] = conv
                self.assertDeny(self.agy("pre", ev), "R6")
                self.assertAllow(self.agy("pre", agy_payload("view_file", self.root, "src/cart.py", conv=conv)))


class TestAgyFailClosed(AgyBase):
    def test_padded_command_touching_a_protected_path_is_denied(self):
        """Either the guard or the gate timeout must answer deny (fail-closed), never allow."""
        cmd = "echo " + "a " * 6000 + "; echo x > specs/001-x/tasks.md"
        self.assertGreater(len(cmd), 10000)
        self.assertDeny(self.apre("run_command", command=cmd))


class TestAgyFr1106ProtectedHooksFile(AgyBase):
    """FR-1106 / AC-1107: `.agents/hooks.json` is a gate file. Spec APPROVED so only the protection can block."""

    def setUp(self):
        super().setUp()
        self.approve()

    def test_writes_to_hooks_json_are_denied(self):
        for tool in ("write_to_file", "replace_file_content"):
            with self.subTest(tool=tool):
                r = self.apre(tool, ".agents/hooks.json")
                self.assertDeny(r)
                reason = r.obj["reason"].lower()
                self.assertTrue("protected" in reason or "gate" in reason, reason)

    def test_shell_redirect_into_hooks_json_is_denied(self):
        self.assertDeny(self.apre("run_command", command="echo x >> .agents/hooks.json"))

    def test_shell_removal_of_dot_agents_is_denied(self):
        self.assertDeny(self.apre("run_command", command="rm -r .agents"))

    def test_rules_and_skills_stay_writable(self):
        self.assertAllow(self.apre("write_to_file", ".agents/rules/x.md"))
        self.assertAllow(self.apre("write_to_file", ".agents/skills/y/SKILL.md"))


class TestAgyOtherHostsRegression(HostBase):
    def test_gemini_and_opencode_still_exit_2_on_a_blocked_write(self):
        for host in HOSTS:
            with self.subTest(host=host):
                self.assertBlockedBy(self.pre(host, "write", "src/app.py"), "R6")


# ---------------------------------------------------------------------------------------------------------------
# Amendment 1 (T-14): Y1 depth guard, Y2/Y3 wildcard protections, Y5 unresolved targets. Written against the contract.
# ---------------------------------------------------------------------------------------------------------------
DEEP_LEVELS = (1200, 3000)
_DEEP_TOKEN = "__DEEP__"


def _deep_raw(event, levels):
    """The event's JSON text with every "__DEEP__" string replaced by `levels` nested arrays (built by loop)."""
    text = json.dumps(event)
    deep = "[" * levels + "]" * levels
    return text.replace('"%s"' % _DEEP_TOKEN, deep).encode("utf-8")


def _protected_text(case, r_text):
    case.assertTrue("protected" in r_text.lower() or "gate" in r_text.lower(), r_text)


class TestAmendY1DepthGuard(AgyBase):
    """FR-1109: PRE stdin nested deeper than 100 is denied on every host; POST never denies."""

    def _top_level(self, host, phase, extra):
        if host == "antigravity":
            ev = agy_payload("write_to_file", self.root, "src/app.py", conv=self.session, phase=phase)
        else:
            ev = payload(host, "write", self.root, "src/app.py", session=self.session, phase=phase)
        ev["extra"] = extra
        return ev

    def test_deep_top_level_key_is_denied_in_pre_on_every_host(self):
        self.approve()                       # only the depth guard can block a write to src/app.py now
        for levels in DEEP_LEVELS:
            for host in HOSTS:
                with self.subTest(host=host, levels=levels):
                    r = self.adapt(host, "pre", raw=_deep_raw(self._top_level(host, "pre", _DEEP_TOKEN), levels))
                    self.assertBlockedBy(r)
            with self.subTest(host="antigravity", levels=levels):
                r = self.agy("pre", raw=_deep_raw(self._top_level("antigravity", "pre", _DEEP_TOKEN), levels))
                self.assertDeny(r)

    def test_deep_extra_key_inside_a_replacement_chunk_is_denied(self):
        for levels in DEEP_LEVELS:
            with self.subTest(levels=levels):
                ev = agy_payload(None, self.root, conv=self.session)
                ev["toolCall"] = {"name": "multi_replace_file_content", "args": {
                    "TargetFile": str(self.root / ".agents" / "hooks.json").replace("\\", "/"),
                    "ReplacementChunks": [{"TargetContent": "a", "ReplacementContent": "b", "StartLine": 1,
                                           "EndLine": 1, "Extra": _DEEP_TOKEN}]}}
                self.assertDeny(self.agy("pre", raw=_deep_raw(ev, levels)))
        self.approve()
        self.assertDeny(self.agy("pre", raw=_deep_raw(ev, DEEP_LEVELS[0])))

    def test_same_deep_inputs_in_post_are_never_denied(self):
        for levels in DEEP_LEVELS:
            for host in HOSTS:
                with self.subTest(host=host, levels=levels):
                    r = self.adapt(host, "post", raw=_deep_raw(self._top_level(host, "post", _DEEP_TOKEN), levels))
                    self.assertOk(r)
            with self.subTest(host="antigravity", levels=levels):
                r = self.agy("post", raw=_deep_raw(self._top_level("antigravity", "post", _DEEP_TOKEN), levels))
                self.assertNotEqual(r.obj.get("decision"), "deny", r.out)

    def test_depth_50_payload_still_passes(self):
        self.approve()
        for host in HOSTS:
            with self.subTest(host=host):
                self.assertOk(self.adapt(host, "pre", raw=_deep_raw(self._top_level(host, "pre", _DEEP_TOKEN), 50)))
        r = self.agy("pre", raw=_deep_raw(self._top_level("antigravity", "pre", _DEEP_TOKEN), 50))
        self.assertAllow(r)

    def test_garbage_and_empty_stdin_keep_their_behaviour(self):
        for raw in (b"{not json", b"", b"\xff\xfe"):
            for host in HOSTS:
                with self.subTest(host=host, raw=raw):
                    r = self.adapt(host, "pre", raw=raw)
                    self.assertEqual(r.returncode, 0, r.err)
            with self.subTest(host="antigravity", raw=raw):
                self.assertAllow(self.agy("pre", raw=raw))
                self.assertEqual(self.agy("post", raw=raw).obj, {})

    def test_real_small_payloads_still_pass(self):
        self.approve()
        for host in HOSTS:
            with self.subTest(host=host):
                self.assertOk(self.pre(host, "write", "src/app.py"))
        self.assertAllow(self.apre("write_to_file", "src/app.py"))
        self.assertAllow(self.apre("replace_file_content", "src/cart.py"))
        self.assertAllow(self.apre("run_command", command="echo done"))


# protected by Y2/Y3 and the allowed neighbours (relative to the project root)
Y_DENIED = (".agents/plugins/p/hooks.json", ".agents/python.bat", ".agents/python.exe", ".agents/Python.BAT",
            ".agents/x.cmd", ".agents/y.ps1", ".agents/z.com")
Y_ALLOWED = (".agents/rules/x.md", ".agents/skills/y/SKILL.md", ".agents/plugins/p/readme.md")


class TestAmendY2Y3Antigravity(AgyBase):
    """FR-1110 / FR-1111 / AC-1108: the wildcard protections, spec APPROVED so only the protection can block."""

    def setUp(self):
        super().setUp()
        self.approve()

    def test_file_tools_are_denied_on_every_protected_path(self):
        for rel in Y_DENIED:
            for tool in ("write_to_file", "replace_file_content"):
                with self.subTest(rel=rel, tool=tool):
                    r = self.apre(tool, rel)
                    self.assertDeny(r)
                    _protected_text(self, r.obj["reason"])

    def test_shell_writers_are_denied_on_every_protected_path(self):
        cmds = ("echo x > {p}", "echo x >> {p}", "rm {p}", "cp a.md {p}", "mv a.md {p}", "echo x | tee {p}",
                "Set-Content {p} x")
        for rel in Y_DENIED:
            for c in cmds:
                with self.subTest(rel=rel, cmd=c):
                    r = self.apre("run_command", command=c.format(p=rel))
                    self.assertDeny(r)
                    _protected_text(self, r.obj["reason"])

    def test_copier_of_an_interpreter_into_dot_agents_is_denied(self):
        for c in ("cp python.exe .agents/", "cp python.exe .agents", "cp ./python.exe .agents/"):
            with self.subTest(cmd=c):
                r = self.apre("run_command", command=c)
                self.assertDeny(r)
                _protected_text(self, r.obj["reason"])

    def test_allowed_neighbours_stay_writable(self):
        for rel in Y_ALLOWED:
            for tool in ("write_to_file", "replace_file_content"):
                with self.subTest(rel=rel, tool=tool):
                    self.assertAllow(self.apre(tool, rel))
        self.assertAllow(self.apre("run_command", command="echo x > .agents/rules/x.md"))

    def test_reading_and_copying_into_rules_is_allowed(self):
        self.assertAllow(self.apre("run_command", command="cat .agents/python.bat"))
        self.assertAllow(self.apre("run_command", command="cp a.md .agents/rules/"))


class TestAmendY2Y3OtherHosts(HostBase):
    def setUp(self):
        super().setUp()
        self.approve()

    def test_gemini_and_opencode_deny_plugin_hooks_json_and_python_bat(self):
        for host in HOSTS:
            for rel in (".agents/plugins/p/hooks.json", ".agents/python.bat"):
                for kind in ("write", "edit"):
                    with self.subTest(host=host, rel=rel, kind=kind):
                        r = self.pre(host, kind, rel)
                        self.assertBlockedBy(r)
                        _protected_text(self, r.err)
                with self.subTest(host=host, rel=rel, kind="bash"):
                    r = self.pre(host, "bash", command="echo x > " + rel)
                    self.assertBlockedBy(r)
                    _protected_text(self, r.err)

    def test_gemini_and_opencode_allow_the_neighbours(self):
        for host in HOSTS:
            for rel in Y_ALLOWED:
                with self.subTest(host=host, rel=rel):
                    self.assertOk(self.pre(host, "write", rel))
            with self.subTest(host=host, what="read"):
                self.assertOk(self.pre(host, "bash", command="cat .agents/python.bat"))
            with self.subTest(host=host, what="cp"):
                self.assertOk(self.pre(host, "bash", command="cp a.md .agents/rules/"))


class TestAmendY2UserLevelHooksFile(AgyBase):
    """The user-level ~/.gemini/config/hooks.json lives OUTSIDE the project: HOME and USERPROFILE point at a temp home."""

    def setUp(self):
        super().setUp()
        self.approve()
        self.home = Path(tempfile.mkdtemp(prefix="aidd-home-"))
        self.addCleanup(shutil.rmtree, str(self.home), True)
        self.henv = {"HOME": str(self.home), "USERPROFILE": str(self.home)}
        self.target = str(self.home / ".gemini" / "config" / "hooks.json").replace("\\", "/")

    def _agy_pre(self, call):
        ev = agy_payload(None, self.root, conv=self.session)
        ev["toolCall"] = call
        r = self.adapt("antigravity", "pre", ev, env=self.henv)
        self.assertEqual(r.returncode, 0, r.err)
        r.obj = json.loads(r.out)
        return r

    def test_antigravity_file_tools_by_absolute_path_are_denied(self):
        for name, args in (("write_to_file", {"TargetFile": self.target, "CodeContent": "{}"}),
                           ("replace_file_content", {"TargetFile": self.target, "TargetContent": "a",
                                                     "ReplacementContent": "b"})):
            with self.subTest(tool=name):
                r = self._agy_pre({"name": name, "args": args})
                self.assertDeny(r)
                _protected_text(self, r.obj["reason"])

    def test_antigravity_shell_forms_are_denied(self):
        for cmd in ("echo x > " + self.target, "echo x > $HOME/.gemini/config/hooks.json",
                    "echo x > ~/.gemini/config/hooks.json", "rm " + self.target,
                    "cp a.json $HOME/.gemini/config/hooks.json"):
            with self.subTest(cmd=cmd):
                r = self._agy_pre({"name": "run_command", "args": {"CommandLine": cmd,
                                                                    "Cwd": str(self.root).replace("\\", "/")}})
                self.assertDeny(r)
                _protected_text(self, r.obj["reason"])

    def test_gemini_write_file_by_absolute_path_is_denied(self):
        ev = payload("gemini", "write", self.home, ".gemini/config/hooks.json", session=self.session, cwd=self.root)
        r = self.adapt("gemini", "pre", ev, env=self.henv)
        self.assertBlockedBy(r)
        _protected_text(self, r.err)

    def test_gemini_and_opencode_shell_by_home_variable_is_denied(self):
        for host in HOSTS:
            with self.subTest(host=host):
                ev = payload(host, "bash", self.root, command="echo x > $HOME/.gemini/config/hooks.json",
                             session=self.session)
                self.assertBlockedBy(self.adapt(host, "pre", ev, env=self.henv))


class TestAmendY5UnresolvedTargets(AgyBase):
    """FR-1113 / AC-1109 / AC-1112: a target that cannot be resolved is denied, never allowed."""

    def _call(self, name, args, **kw):
        ev = agy_payload(None, self.root, conv=self.session, **kw)
        ev["toolCall"] = {"name": name, "args": args}
        return ev

    def test_non_string_target_file_is_denied(self):
        for approved in (False, True):
            if approved:
                self.approve()
            for bad in (["src/app.py"], {"p": "src/app.py"}, 12345):
                for name, extra in (("write_to_file", {"CodeContent": "x = 1\n"}),
                                    ("replace_file_content", {"TargetContent": "a", "ReplacementContent": "b"})):
                    with self.subTest(approved=approved, bad=repr(bad), tool=name):
                        self.assertDeny(self.agy("pre", self._call(name, {"TargetFile": bad, **extra})))

    def test_unparseable_replacement_chunks_are_denied(self):
        self.approve()
        for chunks in ("not json {", 12345, None, [1, 2], "[]", []):
            with self.subTest(chunks=repr(chunks)):
                args = {"TargetFile": str(self.root / "src" / "app.py").replace("\\", "/"),
                        "ReplacementChunks": chunks}
                self.assertDeny(self.agy("pre", self._call("multi_replace_file_content", args)))

    def test_parseable_replacement_chunks_still_follow_the_normal_gate(self):
        args = {"TargetFile": str(self.root / "src" / "app.py").replace("\\", "/"),
                "ReplacementChunks": [{"TargetContent": "a", "ReplacementContent": "b", "StartLine": 1,
                                       "EndLine": 1}]}
        self.assertDeny(self.agy("pre", self._call("multi_replace_file_content", args)), "R6")
        self.approve()
        self.assertAllow(self.agy("pre", self._call("multi_replace_file_content", args)))

    def test_relative_target_without_workspace_paths_and_cwd_dot_agents_is_gated(self):
        agents = self.root / ".agents"
        agents.mkdir(exist_ok=True)
        ev = self._call("write_to_file", {"TargetFile": "src/app.py", "CodeContent": "x = 1\n"}, workspace=False)
        self.assertDeny(self.agy("pre", ev, cwd=agents), "R6")
        hooks = self._call("write_to_file", {"TargetFile": ".agents/hooks.json", "CodeContent": "{}"},
                           workspace=False)
        self.assertDeny(self.agy("pre", hooks, cwd=agents))
        self.approve()
        self.assertAllow(self.agy("pre", ev, cwd=agents))
        self.assertDeny(self.agy("pre", hooks, cwd=agents))


if __name__ == "__main__":
    unittest.main()
