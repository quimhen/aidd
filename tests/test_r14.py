"""R14 (spec 005): a low-tier (haiku) subagent does not count as an auditor for R5/R7/R8."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gate_fixtures import Base, approved_tasks, tasks_text  # noqa: E402
import aidd_rules as R  # noqa: E402

PLAN = "specs/001-x/plan.md"
TASKS = "specs/001-x/tasks.md"
QA = "specs/001-x/qa-audit.md"


class Helpers(Base):
    def sub(self, desc, head, **extra):
        self.ev("subagent", type="general-purpose", desc=desc, head=head, **extra)

    def model_sub(self, model, desc="Perf auditor", head="performance review of the change"):
        self.sub(desc, head, model=model)

    def sec_func(self):
        """FR-002: security and functional auditors are always required (distinct subagents)."""
        self.sub("Security auditor", "security review of the change", model="sonnet")
        self.sub("Functional auditor", "functional acceptance review", model="sonnet")


class TestIsLowTier(unittest.TestCase):
    def test_haiku_variants(self):
        for m in ("haiku", "HAIKU", "claude-haiku-4-5-20251001"):
            self.assertTrue(R.is_low_tier(m), m)

    def test_not_low(self):
        for m in ("sonnet", "opus", "", None, "inherit"):
            self.assertFalse(R.is_low_tier(m), m)

    def test_pre_rows_never_count(self):
        for model in ("sonnet", "opus", "", "haiku"):
            self.assertFalse(R._subagent_counts({"detail": {"phase": "pre", "model": model}}), model)
        self.assertTrue(R._subagent_counts({"detail": {"phase": "post", "model": "sonnet"}}))
        self.assertTrue(R._subagent_counts({"detail": {"model": ""}}))         # old rows (no phase) count
        self.assertFalse(R._subagent_counts({"detail": {"phase": "post", "model": "haiku"}}))


class TestR14R7(Helpers):
    def setUp(self):
        super().setUp()
        self.put(TASKS, approved_tasks())  # cites COMP-001 => security + functional + performance + ui
        self.ev("code_edit", path="src/app.py", spec="001-x")

    def test_haiku_blocks_with_message(self):
        self.model_sub("haiku")
        self.sub("UI auditor", "mockup check", model="sonnet")
        self.sec_func()
        self.assertBlocked(self.gate(QA, content="# qa"), "R7", "model tier too low")

    def test_full_haiku_id_blocks(self):
        self.model_sub("claude-haiku-4-5-20251001")
        self.sub("UI auditor", "mockup check", model="sonnet")
        self.sec_func()
        self.assertBlocked(self.gate(QA, content="# qa"), "model tier too low")

    def test_uppercase_haiku_blocks(self):
        self.model_sub("HAIKU")
        self.sub("UI auditor", "mockup check", model="sonnet")
        self.sec_func()
        self.assertBlocked(self.gate(QA, content="# qa"), "model tier too low")

    def test_haiku_security_and_functional_do_not_count(self):
        """FR-002 domains keep R14: haiku never satisfies security/functional either."""
        self.model_sub("sonnet")
        self.sub("UI auditor", "mockup check", model="sonnet")
        self.sub("Security auditor", "security review", model="haiku")
        self.sub("Functional auditor", "functional acceptance review", model="haiku")
        g = self.gate(QA, content="# qa")
        self.assertBlocked(g, "R7", "security")
        self.assertBlocked(g, "functional")

    def test_only_performance_and_ui_is_no_longer_enough(self):
        self.model_sub("sonnet")
        self.sub("UI auditor", "mockup check", model="sonnet")
        self.assertBlocked(self.gate(QA, content="# qa"), "R7", "security")

    def _allowed_with(self, model):
        if model is None:
            self.sub("Perf auditor", "performance review of the change")
        else:
            self.model_sub(model)
        self.sub("UI auditor", "mockup check", model="sonnet")
        self.sec_func()
        self.assertAllowed(self.gate(QA, content="# qa"))

    def test_sonnet_allowed(self):
        self._allowed_with("sonnet")

    def test_opus_allowed(self):
        self._allowed_with("opus")

    def test_no_model_field_allowed(self):
        self._allowed_with(None)

    def test_empty_model_allowed(self):
        self._allowed_with("")

    def test_inherit_allowed(self):
        self._allowed_with("inherit")

    def test_mixed_haiku_and_sonnet_allowed(self):
        self.model_sub("haiku")
        self.model_sub("sonnet")
        self.sub("UI auditor", "mockup check", model="sonnet")
        self.sec_func()
        self.assertAllowed(self.gate(QA, content="# qa"))

    def test_pre_row_never_counts_for_r7(self):
        """F1 D1/D2: a PreToolUse attribution row (phase 'pre', e.g. a denied dispatch) is no audit."""
        self.sub("Perf auditor", "performance review of the change", model="sonnet", phase="pre")
        self.sub("UI auditor", "mockup check", model="sonnet")
        self.sec_func()
        g = self.gate(QA, content="# qa")
        self.assertBlocked(g, "R7", "performance")
        self.assertNotIn("model tier too low", g.err)

    def test_pre_haiku_row_is_not_reported_as_tier(self):
        self.sub("Perf auditor", "performance review of the change", model="haiku", phase="pre")
        self.sub("UI auditor", "mockup check", model="sonnet")
        self.sec_func()
        g = self.gate(QA, content="# qa")
        self.assertBlocked(g, "R7", "performance")
        self.assertNotIn("model tier too low", g.err)

    def test_post_row_with_same_id_as_pre_counts(self):
        self.sub("Perf auditor", "performance review", model="sonnet", phase="pre", tool_use_id="t1")
        self.sub("Perf auditor", "performance review", model="sonnet", phase="post", tool_use_id="t1")
        self.sub("UI auditor", "mockup check", model="sonnet")
        self.sec_func()
        self.assertAllowed(self.gate(QA, content="# qa"))


class TestR14R8(Helpers):
    TASKS_P = "specs/001-x/tasks.md"

    def implemented(self):
        t = approved_tasks()
        self.put(TASKS, t, age=100)
        self.open_spec()
        self.ev("approved", spec="001-x", hash=R.approval_hash(t))
        self.ev("code_edit", path="src/app.py", spec="001-x")
        self.put(QA, "# qa")

    def stop(self):
        return self.run_hook("stop_gate.py", {"session_id": self.session, "cwd": str(self.root),
                                              "hook_event_name": "Stop"})

    def test_haiku_only_leaves_domain_uncovered(self):
        self.implemented()
        self.model_sub("haiku")
        self.sub("UI", "mockup check", model="sonnet")
        self.sec_func()
        r = self.stop()
        self.assertEqual(r.returncode, 2, r.err)
        self.assertIn("performance", r.err.lower())

    def test_sonnet_satisfies(self):
        self.implemented()
        self.model_sub("sonnet")
        self.sub("UI", "mockup check", model="sonnet")
        self.sec_func()
        r = self.stop()
        self.assertEqual(r.returncode, 0, r.err)

    def test_pre_row_only_leaves_domain_uncovered(self):
        self.implemented()
        self.sub("Perf auditor", "performance review of the change", model="sonnet", phase="pre")
        self.sub("UI", "mockup check", model="sonnet")
        self.sec_func()
        r = self.stop()
        self.assertEqual(r.returncode, 2, r.err)
        self.assertIn("performance", r.err.lower())


class TestR14R5(Helpers):
    """The 006 pre-build demand is the `strict` R5 mode since spec 007 (FR-206): pinned here."""

    def setUp(self):
        super().setUp()
        self.env["AIDD_R5_AUDIT"] = "strict"     # the hook child process sees strict
        self.put(PLAN, "# plan\n")
        self.ev("find_spec", rebuilt=False, ok=True, source="bash")

    def test_haiku_subagent_does_not_satisfy_tasks_chain(self):
        self.sub("Auditor", "independent auditor over plan.md", model="haiku")
        self.assertBlocked(self.gate(TASKS, content=tasks_text()), "subagent")

    def test_sonnet_subagent_satisfies_tasks_chain(self):
        self.sub("Auditor", "independent auditor over plan.md", model="sonnet")
        self.assertAllowed(self.gate(TASKS, content=tasks_text()))

    def test_pre_row_does_not_satisfy_tasks_chain(self):
        self.sub("Auditor", "independent auditor over plan.md", model="sonnet", phase="pre")
        self.assertBlocked(self.gate(TASKS, content=tasks_text()), "subagent")


_RULE_GATE_SRC = (Path(__file__).resolve().parent.parent / "skill" / "hooks" / "rule_gate.py")


def _rule_gate_has_r5_mode():
    try:
        return "r5_audit_mode" in _RULE_GATE_SRC.read_text(encoding="utf-8")
    except OSError:
        return False


class TestR14R5Modes(Helpers):
    """Spec 007 (FR-206, AC-211): the library's R5 mode; the hook twin activates once rule_gate reads it."""

    def setUp(self):
        super().setUp()
        self.put(PLAN, "# plan\n")
        self.ev("find_spec", rebuilt=False, ok=True, source="bash")

    def test_library_mode_values(self):
        import os
        from unittest.mock import patch
        for value, want in ((None, "advisory"), ("", "advisory"), ("advisory", "advisory"), ("x", "advisory"),
                            ("strict", "strict"), (" STRICT ", "strict")):
            with patch.dict(os.environ):
                os.environ.pop("AIDD_R5_AUDIT", None)
                if value is not None:
                    os.environ["AIDD_R5_AUDIT"] = value
                self.assertEqual(R.r5_audit_mode(), want, value)

    def test_haiku_still_never_counts_in_strict(self):
        self.env["AIDD_R5_AUDIT"] = "strict"
        self.sub("Auditor", "independent auditor over plan.md", model="haiku")
        self.assertBlocked(self.gate(TASKS, content=tasks_text()), "subagent")

    @unittest.skipUnless(_rule_gate_has_r5_mode(), "rule_gate does not read r5_audit_mode yet (T-06)")
    def test_advisory_twin_haiku_only_is_allowed(self):
        self.env.pop("AIDD_R5_AUDIT", None)
        self.sub("Auditor", "independent auditor over plan.md", model="haiku")
        self.assertAllowed(self.gate(TASKS, content=tasks_text()))


class TestDispatchModelResolution(Helpers):
    """Effective model of a dispatch with no explicit `model` (built-in Explore, custom agent files)."""

    def dispatch(self, **ti):
        ti.setdefault("description", "security audit of the change")
        ti.setdefault("prompt", "audit it")
        r = self.run_hook("mark_agent_dispatch.py", {"session_id": self.session, "cwd": str(self.root),
                                                     "hook_event_name": "PostToolUse", "tool_name": "Agent",
                                                     "tool_input": ti})
        self.assertEqual(r.returncode, 0, r.err)
        return self.events("subagent")[-1]

    def agent_file(self, name, model_line):
        self.put(".claude/agents/%s.md" % name, "---\nname: %s\n%s\ntools: Read\n---\nBody\n" % (name, model_line))

    @staticmethod
    def d(e):
        return e.get("detail", e)

    def test_explore_without_model_is_haiku_builtin(self):
        self.put(TASKS, approved_tasks())
        self.ev("code_edit", path="src/app.py", spec="001-x")
        e = self.d(self.dispatch(subagent_type="Explore", description="Perf auditor",
                                 prompt="performance review of the change"))
        self.assertEqual((e["model"], e["model_source"]), ("haiku", "builtin"))
        self.sub("UI auditor", "mockup check", model="sonnet")
        self.sec_func()
        self.assertBlocked(self.gate(QA, content="# qa"), "model tier too low")

    def test_explore_with_explicit_model_keeps_it(self):
        e = self.d(self.dispatch(subagent_type="Explore", model="sonnet"))
        self.assertEqual((e["model"], e["model_source"]), ("sonnet", "tool_input"))

    def test_custom_agent_file_haiku(self):
        self.agent_file("zz-r14-cheap", "model: haiku")
        e = self.d(self.dispatch(subagent_type="zz-r14-cheap"))
        self.assertEqual((e["model"], e["model_source"]), ("haiku", "agent_file"))

    def test_custom_agent_file_opus_quoted(self):
        self.agent_file("zz-r14-strong", "model: 'opus'")
        e = self.d(self.dispatch(subagent_type="zz-r14-strong"))
        self.assertEqual((e["model"], e["model_source"]), ("opus", "agent_file"))

    def test_unknown_type_unresolved(self):
        e = self.d(self.dispatch(subagent_type="zz-r14-nonexistent"))
        self.assertEqual((e["model"], e["model_source"]), ("", ""))


if __name__ == "__main__":
    unittest.main()
