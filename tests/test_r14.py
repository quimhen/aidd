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


class TestIsLowTier(unittest.TestCase):
    def test_haiku_variants(self):
        for m in ("haiku", "HAIKU", "claude-haiku-4-5-20251001"):
            self.assertTrue(R.is_low_tier(m), m)

    def test_not_low(self):
        for m in ("sonnet", "opus", "", None, "inherit"):
            self.assertFalse(R.is_low_tier(m), m)


class TestR14R7(Helpers):
    def setUp(self):
        super().setUp()
        self.put(TASKS, approved_tasks())  # cites COMP-001 => performance + ui
        self.ev("code_edit", path="src/app.py", spec="001-x")

    def test_haiku_blocks_with_message(self):
        self.model_sub("haiku")
        self.sub("UI auditor", "mockup check", model="sonnet")
        self.assertBlocked(self.gate(QA, content="# qa"), "R7", "model tier too low")

    def test_full_haiku_id_blocks(self):
        self.model_sub("claude-haiku-4-5-20251001")
        self.sub("UI auditor", "mockup check", model="sonnet")
        self.assertBlocked(self.gate(QA, content="# qa"), "model tier too low")

    def test_uppercase_haiku_blocks(self):
        self.model_sub("HAIKU")
        self.sub("UI auditor", "mockup check", model="sonnet")
        self.assertBlocked(self.gate(QA, content="# qa"), "model tier too low")

    def _allowed_with(self, model):
        if model is None:
            self.sub("Perf auditor", "performance review of the change")
        else:
            self.model_sub(model)
        self.sub("UI auditor", "mockup check", model="sonnet")
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
        r = self.stop()
        self.assertEqual(r.returncode, 2, r.err)
        self.assertIn("performance", r.err.lower())

    def test_sonnet_satisfies(self):
        self.implemented()
        self.model_sub("sonnet")
        self.sub("UI", "mockup check", model="sonnet")
        r = self.stop()
        self.assertEqual(r.returncode, 0, r.err)


class TestR14R5(Helpers):
    def setUp(self):
        super().setUp()
        self.put(PLAN, "# plan\n")
        self.ev("find_spec", rebuilt=False, ok=True, source="bash")

    def test_haiku_subagent_does_not_satisfy_tasks_chain(self):
        self.sub("Auditor", "independent auditor over plan.md", model="haiku")
        self.assertBlocked(self.gate(TASKS, content=tasks_text()), "subagent")

    def test_sonnet_subagent_satisfies_tasks_chain(self):
        self.sub("Auditor", "independent auditor over plan.md", model="sonnet")
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
