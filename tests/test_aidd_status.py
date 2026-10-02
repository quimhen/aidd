"""Tests for skill/scripts/aidd_status.py — the hard-rules ledger and `aidd rules ...` commands.
Stdlib unittest; evidence is hand-made through aidd_evidence and ALWAYS lives in a temp dir via
AIDD_EVIDENCE_DIR (no test writes <repo>/.aidd)."""
import json
import os
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
import aidd_rules  # noqa: E402
import aidd_status  # noqa: E402

SPEC = r"""# 001-x

## Minimum Requirements Checklist

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | billing | repo — src/billing.py:1 | ask |
| New development or modification of something existing? | modification | repo — src/billing.py:1 | ask |
| Does it involve an external service, API, or integration? | no | repo — src/billing.py:1 | ask |
| Who is requesting it? (role/profile, not necessarily the name) | accounting | user — "only the invoices screen" | ask |
| Dependencies on other modules or active developments? | none | repo — src/billing.py:1 | ask |
| Business objective (1 sentence — what it achieves and why) | invoices | repo — src/billing.py:1 | ask |
| Expected visual fidelity level (if there's a mockup): exact \| functional behavior only | functional | repo — src/billing.py:1 | ask |

## Pipeline route

| Step | Status | Reason | Confirmation |
|---|---|---|---|
| -1 | run | | |
| 0 | waived | backend only | user — "no mockup for this one" |
| 1 | waived | backend only | user — "no mockup for this one" |
| 1.5 | waived | backend only | user — "no mockup for this one" |
| 2 | run | | |
| 3 | run | | |
| 4 | run | | |
"""

TASKS = """# Tasks

## Waves

| Wave | Tasks | Agent time (min) | Human ref (h) |
|---|---|---|---|
| 1 | T-01, T-02 | 20 | 4 |
| 2 | T-03 | 15 | 2 |

Total agent time (critical path): 35 min

### T-01
- Agent min: 10
- Human ref hours: 2
- Status: todo

### T-02
- Agent min: 20
- Human ref hours: 2

### T-03
- Agent min: 15
- Human ref hours: 2
"""

ROUTE_PROMPT = "please go on, no mockup for this one, thanks"
SPEC_OTHER = SPEC.replace("001-x", "002-y")


def backdate(path, seconds=100):
    t = time.time() - seconds
    os.utime(path, (t, t))


def tick():
    time.sleep(0.004)  # distinct, increasing event timestamps


def make_project(tasks=TASKS, spec=SPEC, plan=True, name="001-x"):
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    (root / "src").mkdir()
    (root / "src" / "billing.py").write_text("x = 1\n", encoding="utf-8")
    d = add_spec(root, name, tasks, spec, plan)
    return tmp, root, d


def add_spec(root, name, tasks=TASKS, spec=SPEC, plan=True):
    d = root / "specs" / name
    d.mkdir(parents=True)
    (d / "spec.md").write_bytes(spec.encode("utf-8"))
    if plan:
        (d / "plan.md").write_text("# plan\n", encoding="utf-8")
    if tasks is not None:
        (d / "tasks.md").write_bytes(tasks.encode("utf-8"))
    for f in d.iterdir():
        backdate(f)
    return d


def run_script(*args, cwd=None):
    return subprocess.run([sys.executable, str(SCRIPTS_DIR / "aidd_status.py"), *args],
                          cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True, encoding="utf-8")


def run_cli(*args, cwd):
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT), PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-m", "aidd.cli", *args], cwd=str(cwd), env=env,
                          capture_output=True, text=True, encoding="utf-8")


class EvBase(unittest.TestCase):
    """Isolates the evidence log in a temp dir for the test and its subprocesses."""

    def setUp(self):
        self._evtmp = tempfile.TemporaryDirectory()
        self._old = os.environ.get("AIDD_EVIDENCE_DIR")
        self._old_testing = os.environ.get("AIDD_TESTING")
        os.environ["AIDD_EVIDENCE_DIR"] = self._evtmp.name
        os.environ["AIDD_TESTING"] = "1"      # Rev 2: the override is honoured ONLY with AIDD_TESTING=1
        for k in ("AIDD_SESSION_ID", "CLAUDE_SESSION_ID"):
            self.addCleanup(self._restore, k, os.environ.pop(k, None))

    def tearDown(self):
        if self._old is None:
            os.environ.pop("AIDD_EVIDENCE_DIR", None)
        else:
            os.environ["AIDD_EVIDENCE_DIR"] = self._old
        if self._old_testing is None:
            os.environ.pop("AIDD_TESTING", None)
        else:
            os.environ["AIDD_TESTING"] = self._old_testing
        self._evtmp.cleanup()

    @staticmethod
    def _restore(k, v):
        if v is not None:
            os.environ[k] = v

    # -- evidence helpers (every call is separated by a tick so ts strictly increases)
    @staticmethod
    def aq(d, text="Approve these tasks?"):
        """An approval question carrying the tag that binds it to the CURRENT tasks.md."""
        return f"{text} {aidd_status.approval_tag((Path(d) / 'tasks.md').read_text(encoding='utf-8'))}"

    def prompt(self, root, text="continue please", session="s1"):
        tick()
        ev.append(root, session, "prompt", text=text)

    def answer(self, root, q, a, session="s1", options=None):
        """What mark_user_question records: the question with its offered option labels, then the
        answer pairs anchored on that known question."""
        tick()
        ev.append(root, session, "question", text=q, options=[options or [a, "Other"]])
        tick()
        ev.append_answer(root, session, f'"{q}"="{a}"', [[q, a]], options=[options or [a, "Other"]])

    def spec_edit(self, root, spec="001-x", file="tasks.md", h=""):
        tick()
        d = {"path": f"specs/{spec}/{file}", "spec": spec, "file": file}
        if h:
            d["hash"] = h
        ev.append(root, "s1", "spec_edit", **d)

    def evidence_for_check(self, root):
        self.spec_edit(root, file="spec.md")
        self.prompt(root, ROUTE_PROMPT)
        self.answer(root, "Which scope?", "only the invoices screen")
        tick()
        ev.append(root, "s1", "find_spec", rebuilt=False, ok=True, source="bash")
        tick()
        ev.append(root, "s1", "subagent", type="x", desc="Mapper", head="")

    def approve(self, root, d):
        self.spec_edit(root, file="tasks.md")
        self.prompt(root)
        self.answer(root, self.aq(d, "Approve these tasks?"), "Approve")
        r = run_script("rules", "approve", str(d), cwd=root)
        self.assertEqual(r.returncode, 0, r.stdout)
        return r


class TestLedger(EvBase):
    def test_ledger_from_evidence(self):
        tmp, root, d = make_project()
        with tmp:
            self.spec_edit(root, file="spec.md")
            self.prompt(root, ROUTE_PROMPT)
            tick()
            ev.append(root, "s1", "find_spec", rebuilt=False, ok=True, source="bash")
            tick()
            ev.append(root, "s1", "subagent", type="general-purpose", desc="Mapper", head="You are the Mapper")
            for i in range(3):
                tick()
                ev.append(root, "s1", "code_edit", path=f"src/a{i}.py", spec="001-x")
            tick()
            ev.append(root, "s1", "subagent", type="general-purpose", desc="performance audit", head="best practice")
            tick()
            ev.append(root, "s1", "hook_error", hook="rule_gate", error="boom")
            st = aidd_status.build_status(d)
            self.assertEqual(st["spec"], "001-x")
            self.assertEqual(st["route"]["0"], {"status": "waived", "confirmed": True})
            self.assertEqual(st["route"]["2"]["status"], "run")
            # the checklist quote "only the invoices screen" was never recorded (prompt needs 5 words)
            self.assertEqual(st["alignment"], {"proposed": 0, "unanswered": 0, "unverified_quotes": 1})
            self.assertTrue(st["mapper"])
            self.assertTrue(st["graph"])
            self.assertEqual(st["tasks"], {"approval": "pending", "waves": 2, "critical_path_min": 35,
                                         "approval_recorded": False})
            self.assertEqual(st["code_edits"], 3)
            self.assertEqual(st["auditors"], {"performance": True})
            text = aidd_status.format_status(st) + "\n" + aidd_status.format_global(aidd_status._global(root))
            self.assertIn("0/1/1.5 WAIVED(confirmed)", text)
            self.assertIn("critical path 35 min", text)
            self.assertIn("3 code edits", text)
            self.assertIn("Hook errors: 1", text)
            self.assertIn("rule_gate: boom", text)

    def test_quote_before_first_spec_edit_does_not_confirm(self):
        tmp, root, d = make_project()
        with tmp:
            self.prompt(root, ROUTE_PROMPT)       # said BEFORE the spec was first written
            self.spec_edit(root, file="spec.md")
            self.assertFalse(aidd_status.build_status(d)["route"]["0"]["confirmed"])

    def test_unconfirmed_waiver_and_missing_evidence(self):
        tmp, root, d = make_project()
        with tmp:
            st = aidd_status.build_status(d)
            self.assertFalse(st["route"]["0"]["confirmed"])
            self.assertFalse(st["mapper"])
            self.assertFalse(st["graph"])
            self.assertEqual(st["auditors"], {"performance": False})
            self.assertIn("WAIVED(unconfirmed)", aidd_status.format_status(st))

    def test_proposed_and_unanswered_rows_counted(self):
        spec = SPEC.replace("repo — src/billing.py:1", "[Proposed — unconfirmed]", 1).replace(
            "| accounting |", "| |")
        tmp, root, d = make_project(spec=spec)
        with tmp:
            a = aidd_status.build_status(d)["alignment"]
            self.assertEqual((a["proposed"], a["unanswered"]), (1, 1))

    def test_stale_graph_rebuild_without_subagent(self):
        tmp, root, d = make_project()
        with tmp:
            ev.append(root, "s1", "find_spec", rebuilt=True, ok=True, source="bash")
            self.assertFalse(aidd_status.build_status(d)["graph"])
            tick()
            ev.append(root, "s1", "subagent", type="x", desc="graph audit", head="")
            self.assertTrue(aidd_status.build_status(d)["graph"])

    def test_required_domains_in_ledger(self):
        tasks = TASKS + "\nUses SCREEN-01 and API-002.\n"
        tmp, root, d = make_project(tasks=tasks)
        with tmp:
            self.assertEqual(set(aidd_status.build_status(d)["auditors"]), {"performance", "ui", "backend"})

    def test_one_subagent_cannot_cover_two_domains(self):
        tasks = TASKS + "\nUses SCREEN-01 and API-002.\n"
        tmp, root, d = make_project(tasks=tasks)
        with tmp:
            ev.append(root, "s1", "code_edit", path="src/a.py", spec="001-x")
            tick()
            ev.append(root, "s1", "subagent", type="x", desc="ui backend performance audit", head="")
            aud = aidd_status.build_status(d)["auditors"]
            self.assertEqual(sum(aud.values()), 1)

    def test_visual_debt_counted(self):
        spec = SPEC + ("\n## Visual debt\n\n| Codes | Blocks spec | Status | Mockup source |\n|---|---|---|---|\n"
                       "| SCREEN-01 | 001-x | open | |\n")
        tmp, root, d = make_project(spec=spec)
        with tmp:
            st = aidd_status.build_status(d)
            self.assertEqual(st["visual_debt_open"], 1)
            self.assertEqual(st["debt_blocking"], 1)
            self.assertTrue(any(w.startswith("R4") for w in st["why_blocked"]))


QA_LEDGER = "## Mapping ledger\n\n| Code | Status |\n|---|---|\n| SCREEN-01 | ✅ DONE |\n"
QA_EVID = ("## Execution evidence\n\n| Code | Kind | Evidence | Verified by |\n|---|---|---|---|\n"
           "| SCREEN-01 | screenshot | evidence/login.png | agent |\n")
QA_BUGS = ("## Bug reports\n\n| # | Code | Symptom | Root cause | Fix | Pattern sweep |\n|---|---|---|---|---|---|\n"
           "| 1 | SCREEN-01 | a | | x | |\n| 2 | SCREEN-01 | b | | y | |\n")


class TestQaEvidenceStatus(EvBase):
    def _qa(self, d, text):
        (d / "qa-audit.md").write_text(text, encoding="utf-8", newline="\n")

    def test_no_qa_audit_is_unchecked(self):
        tmp, root, d = make_project()
        with tmp:
            st = aidd_status.build_status(d)
            self.assertEqual(st["qa_evidence"], {"checked": False, "r10": 0, "r11": 0})
            self.assertNotIn("evidence", aidd_status.format_status(st).split("qa-audit.md:")[1])

    def test_missing_evidence_counts_r10_and_shows_in_why_blocked(self):
        tmp, root, d = make_project()
        with tmp:
            self._qa(d, "# qa\n\n" + QA_LEDGER)
            st = aidd_status.build_status(d)
            self.assertTrue(st["qa_evidence"]["checked"])
            self.assertGreaterEqual(st["qa_evidence"]["r10"], 1)
            self.assertTrue(any(w.startswith("R10") for w in st["why_blocked"]), st["why_blocked"])
            self.assertIn("evidence ✘", aidd_status.format_status(st))

    def test_repeat_bug_report_counts_r11(self):
        tmp, root, d = make_project()
        with tmp:
            self._qa(d, "# qa\n\n" + QA_BUGS)
            st = aidd_status.build_status(d)
            self.assertGreaterEqual(st["qa_evidence"]["r11"], 1)
            self.assertTrue(any(w.startswith("R11") for w in st["why_blocked"]), st["why_blocked"])

    def test_valid_evidence_is_ok(self):
        tmp, root, d = make_project()
        with tmp:
            p = root / "specs" / "001-x" / "evidence" / "login.png"
            p.parent.mkdir()
            p.write_bytes(b"png")
            self._qa(d, "# qa\n\n" + QA_LEDGER + "\n" + QA_EVID)
            st = aidd_status.build_status(d)
            self.assertEqual((st["qa_evidence"]["r10"], st["qa_evidence"]["r11"]), (0, 0))
            self.assertIn("evidence ✔", aidd_status.format_status(st))

    def test_stale_evidence_after_code_edit(self):
        tmp, root, d = make_project()
        with tmp:
            p = d / "evidence" / "login.png"
            p.parent.mkdir()
            p.write_bytes(b"png")
            backdate(p, 100)
            self._qa(d, "# qa\n\n" + QA_LEDGER + "\n" + QA_EVID)
            tick()
            ev.append(root, "s1", "code_edit", path="src/a.py", spec="001-x")
            st = aidd_status.build_status(d)
            self.assertGreaterEqual(st["qa_evidence"]["r10"], 1)

    def test_degraded_dict_has_qa_evidence(self):
        from unittest import mock
        tmp, root, d = make_project()
        with tmp, mock.patch.object(aidd_status, "_build_status", side_effect=RuntimeError("x")):
            st = aidd_status.build_status(d)
            self.assertTrue(st["unparseable"])
            self.assertEqual(st["qa_evidence"], {"checked": False, "r10": 0, "r11": 0})
            aidd_status.format_status(st)  # must not raise on the degraded dict


class TestStatusCommand(EvBase):
    def test_json_and_text_exit_zero(self):
        tmp, root, d = make_project()
        with tmp:
            r = run_script("status", str(d), "--json", cwd=root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["tasks"]["waves"], 2)
            r = run_script("status", str(d), cwd=root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("001-x", r.stdout)
            self.assertIn("Waves: 2", r.stdout)

    def test_lists_all_open_specs_with_approval_state_and_why(self):
        tmp, root, d = make_project()
        with tmp:
            d2 = add_spec(root, "002-y", spec=SPEC_OTHER)
            self.spec_edit(root, "001-x")
            self.spec_edit(root, "002-y")
            r = run_script("status", cwd=root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("001-x", r.stdout)
            self.assertIn("002-y", r.stdout)
            self.assertIn("Open specs: 001-x (approval pending), 002-y (approval pending)", r.stdout)
            self.assertIn("WHY blocked", r.stdout)
            self.assertIn("BLOCKED", r.stdout)
            j = json.loads(run_script("status", "--json", cwd=root).stdout)
            self.assertEqual(sorted(j["open_specs"]), ["001-x", "002-y"])
            self.assertEqual(len(j["specs"]), 2)

    def test_status_shows_answers_stop_blocks_and_hook_errors(self):
        tmp, root, d = make_project()
        with tmp:
            self.spec_edit(root)
            r = run_script("status", cwd=root)
            self.assertIn("(AskUserQuestion answered): 0", r.stdout)
            self.answer(root, "Approve the tasks?", "Approve")
            tick()
            ev.append_stop_block(root, "s1", "001-x", "k")
            ev.append_stop_block(root, "s1", "001-x", "k")
            tick()
            ev.append_hook_error(root, "s1", "stop_gate", "oops")
            out = run_script("status", cwd=root).stdout
            self.assertIn("(AskUserQuestion answered): 1", out)
            self.assertIn("Stop blocks: 001-x x2", out)
            self.assertIn("Hook errors: 1 (last: stop_gate: oops)", out)

    def test_pointer_is_informational_only(self):
        tmp, root, d = make_project()
        with tmp:
            ev.set_active_spec(root, "001-x")
            r = run_script("status", cwd=root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("001-x", r.stdout)
            self.assertIn("ACTIVE pointer", r.stdout)
            self.assertIn("Open specs: none", r.stdout)   # not open: no tasks.md edit recorded

    def test_no_open_spec_lists_specs(self):
        tmp, root, d = make_project()
        with tmp:
            r = run_script("status", cwd=root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("No open specs", r.stdout)
            self.assertIn("001-x", r.stdout)

    def test_empty_project_exit_zero(self):
        with tempfile.TemporaryDirectory() as t:
            r = run_script("status", cwd=t)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("Traceback", r.stderr)

    def test_usage_error(self):
        self.assertEqual(run_script("rules", "check").returncode, 2)
        self.assertEqual(run_script("rules", "abandon").returncode, 2)
        self.assertEqual(run_script("rules", "bogus", "x").returncode, 2)
        self.assertEqual(run_script().returncode, 2)


class TestRulesCheck(EvBase):
    def test_valid_static_rules_pass_and_evidence_rules_fail(self):
        tmp, root, d = make_project()
        with tmp:
            r = run_script("rules", "check", str(d), cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("PASS R1", r.stdout)
            self.assertIn("PASS R2", r.stdout)
            self.assertIn("FAIL R5", r.stdout)  # no find_spec / mapper evidence
            self.assertIn("FAIL R6", r.stdout)  # approval pending
            self.assertIn("→", r.stdout)

    def test_all_pass_exit_zero(self):
        tmp, root, d = make_project()
        with tmp:
            self.evidence_for_check(root)
            self.approve(root, d)
            r = run_script("rules", "check", str(d), cwd=root)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertNotIn("FAIL", r.stdout)

    def test_repo_source_must_exist(self):
        tmp, root, d = make_project(spec=SPEC.replace("src/billing.py:1", "src/ghost.py:1"))
        with tmp:
            r = run_script("rules", "check", str(d), cwd=root)
            self.assertIn("FAIL R3", r.stdout)

    def test_bad_estimates_fail_r1(self):
        tasks = TASKS.replace("Total agent time (critical path): 35 min", "Total agent time (critical path): 99 min")
        tmp, root, d = make_project(tasks=tasks)
        with tmp:
            r = run_script("rules", "check", str(d), cwd=root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("FAIL R1", r.stdout)

    def test_not_a_directory(self):
        r = run_script("rules", "check", str(REPO_ROOT / "nope-nope"))
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)


class TestRulesApprove(EvBase):
    def _refused(self, root, d, before):
        r = run_script("rules", "approve", str(d), cwd=root)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual((d / "tasks.md").read_bytes(), before)
        return r

    def test_refused_without_any_question(self):
        tmp, root, d = make_project()
        with tmp:
            before = (d / "tasks.md").read_bytes()
            r = self._refused(root, d, before)
            self.assertIn("AskUserQuestion", r.stdout)
            self.assertIn('"Approve"', r.stdout)

    def test_refused_with_only_a_question_no_answer(self):
        tmp, root, d = make_project()
        with tmp:
            before = (d / "tasks.md").read_bytes()
            self.prompt(root)
            tick()
            ev.append(root, "s1", "question", text="Do you approve the tasks?")   # asked, never answered
            self._refused(root, d, before)

    def test_refused_with_no_answer(self):
        tmp, root, d = make_project()
        with tmp:
            before = (d / "tasks.md").read_bytes()
            self.prompt(root)
            self.answer(root, self.aq(d, "Approve these tasks?"), "No")
            self._refused(root, d, before)
            self.answer(root, self.aq(d, "Approve these tasks?"), "Reject, needs changes")
            self._refused(root, d, before)

    def test_refused_when_label_is_not_approve(self):
        tmp, root, d = make_project()
        with tmp:
            before = (d / "tasks.md").read_bytes()
            self.prompt(root)
            self.answer(root, self.aq(d, "Approve these tasks?"), "Yes", options=["Yes", "No"])
            self._refused(root, d, before)
            self.answer(root, self.aq(d, "Approve these tasks?"), "Sure, go ahead", options=["Sure, go ahead", "Wait"])
            r = self._refused(root, d, before)
            self.assertIn('"Approve"', r.stdout)

    def test_refused_when_question_did_not_offer_approve(self):
        tmp, root, d = make_project()
        with tmp:
            before = (d / "tasks.md").read_bytes()
            self.prompt(root)
            # the chosen text looks like Approve but the question never offered such an option
            ev.append(root, "s1", "question", text=self.aq(d), options=[["Reject", "Later"]])
            tick()
            ev.append_answer(root, "s1", "x", [[self.aq(d), "Approve"]],
                             options=[["Reject", "Later"]])
            self._refused(root, d, before)

    def test_raw_text_without_pairs_is_not_evidence(self):
        tmp, root, d = make_project()
        with tmp:
            before = (d / "tasks.md").read_bytes()
            self.prompt(root)
            tick()
            ev.append_answer(root, "s1", "x", [])   # unusable (count mismatch)
            self._refused(root, d, before)

    def test_override_env_ignored_without_testing_flag(self):
        tmp, root, d = make_project()
        with tmp:
            before = (d / "tasks.md").read_bytes()
            self.prompt(root)
            self.answer(root, self.aq(d, "Approve these tasks?"), "Approve")
            env = {k: v for k, v in os.environ.items() if k != "AIDD_TESTING"}   # AIDD_EVIDENCE_DIR stays set
            r = subprocess.run([sys.executable, str(SCRIPTS_DIR / "aidd_status.py"), "rules", "approve", str(d)],
                               cwd=str(root), env=env, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 1, r.stdout)       # the forged/override log is not read
            self.assertEqual((d / "tasks.md").read_bytes(), before)

    def test_refused_without_or_with_stale_tasks_tag(self):
        tmp, root, d = make_project()
        with tmp:
            before = (d / "tasks.md").read_bytes()
            self.prompt(root)
            self.answer(root, "Approve these tasks?", "Approve")                   # no [tasks:<hash8>] tag
            r = self._refused(root, d, before)
            self.assertIn("[tasks:" + aidd_rules.approval_hash(before.decode("utf-8"))[:8] + "]", r.stdout)
            self.answer(root, "Approve these tasks? [tasks:deadbeef]", "Approve")   # tag of another version
            self._refused(root, d, before)

    def test_answer_for_older_tasks_version_is_void_after_edit(self):
        tmp, root, d = make_project()
        with tmp:
            self.prompt(root)
            self.answer(root, self.aq(d), "Approve")
            text = (d / "tasks.md").read_text(encoding="utf-8")
            (d / "tasks.md").write_text(text.replace("Agent min: 10", "Agent min: 12").replace(
                "| 1 | T-01, T-02 | 20 | 4 |", "| 1 | T-01, T-02 | 20 | 4 |"), encoding="utf-8")
            backdate(d / "tasks.md", 200)                                           # mtime alone would not catch it
            self._refused(root, d, (d / "tasks.md").read_bytes())

    def test_refused_for_unrelated_yes(self):
        tmp, root, d = make_project()
        with tmp:
            before = (d / "tasks.md").read_bytes()
            self.prompt(root)
            self.answer(root, "Which colour do you prefer?", "Yes")
            self._refused(root, d, before)

    def test_refused_with_answer_from_another_session(self):
        tmp, root, d = make_project()
        with tmp:
            before = (d / "tasks.md").read_bytes()
            self.answer(root, self.aq(d, "Approve these tasks?"), "Approve", session="s-other")
            self.prompt(root, session="s1")        # the current session is s1 (newest prompt)
            self._refused(root, d, before)

    def test_session_env_override(self):
        tmp, root, d = make_project()
        with tmp:
            self.answer(root, self.aq(d, "Approve these tasks?"), "Approve", session="s-other")
            self.prompt(root, session="s1")
            env = dict(os.environ, AIDD_SESSION_ID="s-other")      # honoured: AIDD_TESTING=1 is set
            r = subprocess.run([sys.executable, str(SCRIPTS_DIR / "aidd_status.py"), "rules", "approve", str(d)],
                               cwd=str(root), env=env, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stdout)

    def test_refused_when_tasks_not_r1_valid_even_with_yes(self):
        bad = TASKS.replace("Total agent time (critical path): 35 min", "Total agent time (critical path): 99 min")
        tmp, root, d = make_project(tasks=bad)
        with tmp:
            before = (d / "tasks.md").read_bytes()
            self.prompt(root)
            self.answer(root, self.aq(d, "Approve these tasks?"), "Approve")
            r = self._refused(root, d, before)
            self.assertIn("R1", r.stdout)
        legacy = "# Tasks\n\n### T-01\n- Estimated hours: 4\n"
        tmp, root, d = make_project(tasks=legacy)
        with tmp:
            before = (d / "tasks.md").read_bytes()
            self.prompt(root)
            self.answer(root, self.aq(d, "Approve these tasks?"), "Approve")
            self._refused(root, d, before)

    def test_refused_for_answer_older_than_tasks(self):
        tmp, root, d = make_project()
        with tmp:
            self.prompt(root)
            self.answer(root, self.aq(d, "Approve these tasks?"), "Approve")
            t = time.time() + 30
            os.utime(d / "tasks.md", (t, t))     # tasks.md changed after the answer
            self._refused(root, d, (d / "tasks.md").read_bytes())

    def test_accepted_and_round_trips(self):
        tmp, root, d = make_project()
        with tmp:
            self.prompt(root)
            self.answer(root, self.aq(d, "¿Aprobar las tareas?"), "Aprobar")
            r = run_script("rules", "approve", str(d), cwd=root)
            self.assertEqual(r.returncode, 0, r.stdout)
            text = (d / "tasks.md").read_text(encoding="utf-8")
            self.assertRegex(text, r"(?m)^Approved: \d{4}-\d{2}-\d{2} hash:[0-9a-f]{12}$")
            self.assertTrue(aidd_rules.approval_valid(text))
            self.assertEqual(aidd_status.build_status(d)["tasks"]["approval"], "valid")
            ap = ev.events(root, kind="approved")
            self.assertEqual(len(ap), 1)
            self.assertEqual(ap[0]["detail"]["hash"], aidd_rules.approval_hash(text))
            # a Status-only edit does not void it; any other edit does
            (d / "tasks.md").write_text(text.replace("Status: todo", "Status: done"), encoding="utf-8")
            self.assertTrue(aidd_rules.approval_valid((d / "tasks.md").read_text(encoding="utf-8")))
            (d / "tasks.md").write_text(text.replace("Agent min: 10", "Agent min: 11"), encoding="utf-8")
            self.assertFalse(aidd_rules.approval_valid((d / "tasks.md").read_text(encoding="utf-8")))
            self.assertEqual(aidd_status.build_status(d)["tasks"]["approval"], "invalid")

    def test_replaces_pending_placeholder_and_keeps_crlf(self):
        tasks = (TASKS + "\nApproved: PENDING\n").replace("\n", "\r\n")
        tmp, root, d = make_project(tasks=tasks)
        with tmp:
            self.prompt(root)
            self.answer(root, self.aq(d, "Do you approve the tasks?"), "Approve")
            self.assertEqual(run_script("rules", "approve", str(d), cwd=root).returncode, 0)
            raw = (d / "tasks.md").read_bytes()
            self.assertNotIn(b"PENDING", raw)
            self.assertEqual(raw.count(b"Approved:"), 1)
            self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))
            self.assertTrue(aidd_rules.approval_valid(raw.decode("utf-8")))

    def test_missing_tasks(self):
        tmp, root, d = make_project(tasks=None)
        with tmp:
            self.assertEqual(run_script("rules", "approve", str(d), cwd=root).returncode, 1)


class TestRulesClose(EvBase):
    def _approved_project(self):
        tmp, root, d = make_project()
        self.approve(root, d)
        backdate(d / "tasks.md", 50)
        ev.set_active_spec(root, "001-x")
        return tmp, root, d

    def _ready_to_close(self, root, d):
        tick()
        ev.append(root, "s1", "code_edit", path="src/a.py", spec="001-x")
        tick()
        ev.append(root, "s1", "subagent", type="x", desc="performance auditor", head="best practice")
        (d / "qa-audit.md").write_text("# qa\n", encoding="utf-8")

    def test_refused_when_not_open(self):
        tmp, root, d = make_project()
        with tmp:
            r = run_script("rules", "close", "001-x", cwd=root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("not an open spec", r.stdout)

    def test_refused_when_not_approved(self):
        tmp, root, d = make_project()
        with tmp:
            self.spec_edit(root)
            ev.set_active_spec(root, "001-x")
            r = run_script("rules", "close", "001-x", cwd=root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("R6", r.stdout)
            self.assertEqual(ev.get_active_spec(root), "001-x")
            self.assertEqual(ev.open_specs(root), ["001-x"])

    def test_refused_without_qa_or_auditor(self):
        tmp, root, d = self._approved_project()
        with tmp:
            tick()
            ev.append(root, "s1", "code_edit", path="src/a.py", spec="001-x")
            r = run_script("rules", "close", "001-x", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("qa-audit.md", r.stdout)
            self.assertEqual(ev.get_active_spec(root), "001-x")
            (d / "qa-audit.md").write_text("# qa\n", encoding="utf-8")
            r = run_script("rules", "close", "001-x", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("R7", r.stdout)
            self.assertIn("performance", r.stdout)
            self.assertEqual(ev.open_specs(root), ["001-x"])

    def test_refused_without_matching_affirmative_answer(self):
        tmp, root, d = self._approved_project()
        with tmp:
            self._ready_to_close(root, d)
            r = run_script("rules", "close", "001-x", cwd=root)          # no answer at all
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("AskUserQuestion", r.stdout)
            self.answer(root, "Close spec 001-x as completed?", "No")     # a No
            self.assertEqual(run_script("rules", "close", "001-x", cwd=root).returncode, 1)
            self.answer(root, "Approve these tasks again?", "Approve")    # wrong topic
            self.assertEqual(run_script("rules", "close", "001-x", cwd=root).returncode, 1)
            self.assertEqual(ev.open_specs(root), ["001-x"])
            self.assertEqual(ev.get_active_spec(root), "001-x")

    def test_close_answer_older_than_qa_audit_refused(self):
        tmp, root, d = self._approved_project()
        with tmp:
            self.answer(root, "Close spec 001-x as completed?", "Yes, close")   # before the audit
            self._ready_to_close(root, d)
            t = time.time() + 30
            os.utime(d / "qa-audit.md", (t, t))
            self.assertEqual(run_script("rules", "close", "001-x", cwd=root).returncode, 1)

    def test_closes_when_covered_and_status_only_edit_keeps_it_closed(self):
        tmp, root, d = self._approved_project()
        with tmp:
            self._ready_to_close(root, d)
            self.answer(root, "Close spec 001-x as completed?", "Yes, close")
            r = run_script("rules", "close", "001-x", cwd=root)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIsNone(ev.get_active_spec(root))
            self.assertEqual(ev.open_specs(root), [])
            closed = ev.events(root, kind="spec_closed")[-1]["detail"]
            self.assertEqual(closed["reason"], "completed")
            text = (d / "tasks.md").read_text(encoding="utf-8")
            self.assertEqual(closed["hash"], aidd_rules.approval_hash(text))
            # a Status-column-only edit: same hash -> stays closed
            new = text.replace("Status: todo", "Status: done")
            self.spec_edit(root, file="tasks.md", h=aidd_rules.approval_hash(new))
            self.assertEqual(ev.open_specs(root), [])
            # adding a task changes the hash -> re-opens
            new2 = new + "\n### T-04\n- Agent min: 5\n- Human ref hours: 1\n"
            self.spec_edit(root, file="tasks.md", h=aidd_rules.approval_hash(new2))
            self.assertEqual(ev.open_specs(root), ["001-x"])

    def test_code_edit_of_any_spec_postdates_auditors(self):
        tmp, root, d = self._approved_project()
        with tmp:
            self._ready_to_close(root, d)
            self.answer(root, "Close spec 001-x as completed?", "Yes, close")
            tick()
            ev.append(root, "s1", "code_edit", path="src/other.py", spec="002-other")   # no per-spec attribution
            r = run_script("rules", "close", "001-x", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("R7", r.stdout)

    def test_refused_when_approval_event_missing(self):
        tmp, root, d = make_project()
        with tmp:
            self.spec_edit(root)
            text = (d / "tasks.md").read_text(encoding="utf-8")
            (d / "tasks.md").write_text(text + "\nApproved: 2026-01-01 hash:" + aidd_rules.approval_hash(text) + "\n",
                                        encoding="utf-8")
            self._ready_to_close(root, d)
            self.answer(root, "Close spec 001-x as completed?", "Yes, close")
            r = run_script("rules", "close", "001-x", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("approved", r.stdout)

    def test_close_needs_the_exact_label(self):
        tmp, root, d = self._approved_project()
        with tmp:
            self._ready_to_close(root, d)
            self.answer(root, "Close spec 001-x as completed?", "Yes", options=["Yes", "No"])
            r = run_script("rules", "close", "001-x", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn('"Yes, close"', r.stdout)

    def test_unknown_spec(self):
        with tempfile.TemporaryDirectory() as t:
            r = run_script("rules", "close", "999-nope", cwd=t)
            self.assertEqual(r.returncode, 1)
            self.assertNotIn("Traceback", r.stderr)


class TestRulesAbandon(EvBase):
    def _open(self):
        tmp, root, d = make_project()
        self.spec_edit(root)
        ev.set_active_spec(root, "001-x")
        return tmp, root, d

    def test_refused_without_answer(self):
        tmp, root, d = self._open()
        with tmp:
            self.prompt(root)
            r = run_script("rules", "abandon", "001-x", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("AskUserQuestion", r.stdout)
            self.assertEqual(ev.open_specs(root), ["001-x"])

    def test_refused_with_no_or_wrong_topic_answer(self):
        tmp, root, d = self._open()
        with tmp:
            self.prompt(root)
            self.answer(root, "Abandon spec 001-x?", "No, keep it")
            self.assertEqual(run_script("rules", "abandon", "001-x", cwd=root).returncode, 1)
            self.answer(root, "Close spec 001-x as completed?", "Yes, close")   # close != abandon
            self.assertEqual(run_script("rules", "abandon", "001-x", cwd=root).returncode, 1)
            self.assertEqual(ev.open_specs(root), ["001-x"])

    def test_abandon_needs_the_exact_label(self):
        tmp, root, d = self._open()
        with tmp:
            self.prompt(root)
            self.answer(root, "Abandon spec 001-x?", "Yes", options=["Yes", "No"])
            r = run_script("rules", "abandon", "001-x", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn('"Abandon"', r.stdout)
            self.assertEqual(ev.open_specs(root), ["001-x"])

    def test_refused_when_not_open(self):
        tmp, root, d = make_project()
        with tmp:
            self.prompt(root)
            self.answer(root, "Abandon spec 001-x?", "Abandon")
            self.assertEqual(run_script("rules", "abandon", "001-x", cwd=root).returncode, 1)

    def test_abandon_unblocks_and_status_reflects_it(self):
        tmp, root, d = self._open()
        with tmp:
            self.prompt(root)
            self.assertIn("Open specs: 001-x", run_script("status", cwd=root).stdout)
            self.answer(root, "Abandon spec 001-x?", "Abandon")
            r = run_script("rules", "abandon", "001-x", "--reason", "scope dropped by the user", cwd=root)
            self.assertEqual(r.returncode, 0, r.stdout)       # no qa-audit.md needed, tasks not approved
            self.assertIn("scope dropped", r.stdout)
            self.assertEqual(ev.open_specs(root), [])
            self.assertIsNone(ev.get_active_spec(root))
            self.assertEqual(ev.events(root, kind="spec_closed")[-1]["detail"]["reason"], "abandoned")
            out = run_script("status", cwd=root).stdout
            self.assertIn("No open specs", out)
            j = json.loads(run_script("status", "--json", cwd=root).stdout)
            self.assertEqual(j["open_specs"], [])

    def test_abandon_by_spec_dir_path(self):
        tmp, root, d = self._open()
        with tmp:
            self.prompt(root)
            self.answer(root, "Descartar la spec?", "Descartar")
            self.assertEqual(run_script("rules", "abandon", str(d), cwd=root).returncode, 0)
            self.assertEqual(ev.open_specs(root), [])


class TestRev2Status(EvBase):
    def test_spec_md_edit_alone_does_not_open_a_spec(self):
        tmp, root, d = make_project()
        with tmp:
            self.spec_edit(root, file="spec.md")
            self.assertEqual(json.loads(run_script("status", "--json", cwd=root).stdout)["open_specs"], [])
            self.spec_edit(root, file="plan.md")             # open from the first plan.md OR tasks.md edit
            self.assertEqual(json.loads(run_script("status", "--json", cwd=root).stdout)["open_specs"], ["001-x"])

    def test_open_spec_without_tasks_shows_step_4_missing(self):
        tmp, root, d = make_project(tasks=None)
        with tmp:
            self.spec_edit(root, file="plan.md")
            out = run_script("status", cwd=root)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("Step 4 missing", out.stdout)
            self.assertIn("001-x [OPEN]", out.stdout)

    def test_valid_line_without_recorded_event_is_flagged(self):
        tmp, root, d = make_project()
        with tmp:
            self.spec_edit(root)
            text = (d / "tasks.md").read_text(encoding="utf-8")
            (d / "tasks.md").write_text(text + "\nApproved: 2026-01-01 hash:" + aidd_rules.approval_hash(text) + "\n",
                                        encoding="utf-8")        # forged through Bash: no `approved` event
            st = aidd_status.build_status(d)
            self.assertEqual(st["tasks"]["approval"], "valid")
            self.assertFalse(st["tasks"]["approval_recorded"])
            out = run_script("status", cwd=root).stdout
            self.assertIn("NOT recorded", out)
            self.assertIn("BLOCKED", out)

    def test_pathological_tasks_never_internal_error(self):
        cases = {
            "huge": "x" * (3 * 1024 * 1024),
            "over_read_cap": "|" * (5 * 1024 * 1024),
            "nul_and_separators": "# t\x00\n## Waves\n|\u2028|\x0b|\n" + "Approved: " * 2000,
            "ragged_tables": "## Waves\n| a |\n|---|\n" + "| 1 |\n" * 5000
                             + "### T-01\n- Agent min: 99999999999999999999\n",
        }
        for name, body in cases.items():
            with self.subTest(name):
                tmp, root, d = make_project(tasks=body)
                with tmp:
                    self.spec_edit(root)
                    for args in (["status"], ["status", "--json"], ["status", str(d)]):
                        r = run_script(*args, cwd=root)
                        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                        self.assertNotIn("internal error", r.stdout + r.stderr)
                        self.assertNotIn("Traceback", r.stderr)


class TestViaAiddCli(EvBase):
    def test_status_and_rules_through_cli(self):
        tmp, root, d = make_project()
        with tmp:
            r = run_cli("status", str(d), "--json", cwd=root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["spec"], "001-x")
            r = run_cli("rules", "check", str(d), cwd=root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("PASS R1", r.stdout)
            r = run_cli("rules", "approve", str(d), cwd=root)
            self.assertEqual(r.returncode, 1)
            r = run_cli("rules", "abandon", "001-x", cwd=root)
            self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
