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
from unittest import mock

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

## Verification

| # | Command | Expected | Covers |
|---|---|---|---|
| 1 | `python src/check.py` | exit 0 | FR-001 |
"""

LEGACY_TASKS = """# Tasks

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

# FR-009: an unapproved tasks.md must use the NEW format (only an approved legacy file is exempt)
TASKS = """# Tasks

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01, T-02 | builder | 20 | 150 | 4 |
| 2 | T-03 | tests | 15 | 80 | 2 |

Total agent time (critical path): 35 min
Total tokens (k): 230

### T-01
- Agent min: 10
- Human ref hours: 2
- Tokens (est): 60k
- Agent role: builder
- Model tier: medium
- Status: todo

### T-02
- Agent min: 20
- Human ref hours: 2
- Tokens (est): 90k
- Agent role: builder
- Model tier: medium

### T-03
- Agent min: 15
- Human ref hours: 2
- Tokens (est): 80k
- Agent role: tests
- Model tier: medium
"""

ROUTE_PROMPT = "please go on, no mockup for this one, thanks"
SPEC_OTHER = SPEC.replace("001-x", "002-y")


# spec 007: the Verification row of SPEC runs this project script (an existing repo path, AC-218 lint)
CHECK_PY = 'print("check ok: billing totals verified, 3 assertions passed")\n'


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
    (root / "src" / "check.py").write_text(CHECK_PY, encoding="utf-8")
    for f in (root / "src").iterdir():
        backdate(f, 300)
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

    def approve_legacy(self, root, d, spec="001-x"):
        """A spec approved BEFORE spec 007 (AC-208): Approved line + an `approved` event without `gate`."""
        self.spec_edit(root, spec=spec, file="tasks.md")
        text = (d / "tasks.md").read_text(encoding="utf-8")
        h = aidd_rules.approval_hash(text)
        (d / "tasks.md").write_text(text + f"\nApproved: 2026-01-01 hash:{h}\n", encoding="utf-8")
        tick()
        ev.append_approved(root, "s1", spec, h)
        backdate(d / "tasks.md", 50)

    def approve(self, root, d):
        self.spec_edit(root, file="tasks.md")
        self.prompt(root)
        self.answer(root, self.aq(d, "Approve these tasks?"), "Approve")
        r = run_script("rules", "approve", str(d), cwd=root)
        self.assertEqual(r.returncode, 0, r.stdout)
        return r


NEW_TASKS = """# Tasks

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01, T-02 | builder | 20 | 150 | 4 |
| 2 | T-03 | tester | 15 | 80 | 2 |

Total agent time (critical path): 35 min
Total tokens (k): 230

### T-01
- Agent min: 10
- Tokens (est): 60k
- Human ref hours: 2

### T-02
- Agent min: 20
- Tokens (est): 90k
- Human ref hours: 2

### T-03
- Agent min: 15
- Tokens (est): 80k
- Human ref hours: 2
"""


class TestPlanTokens(EvBase):
    def test_new_header_reports_tokens(self):
        tmp, root, d = make_project(tasks=NEW_TASKS)
        with tmp:
            self.spec_edit(root, file="spec.md")
            st = aidd_status.build_status(d)
            self.assertEqual(st["tasks"]["tokens_k"], 230)
            self.assertEqual(st["tasks"]["critical_path_min"], 35)
            text = aidd_status.format_status(st)
            self.assertIn("~", text)
            self.assertIn("k tokens", text)
            self.assertIn("~230k tokens", text)

    def test_legacy_header_has_no_tokens(self):
        tmp, root, d = make_project(tasks=LEGACY_TASKS)
        with tmp:
            self.spec_edit(root, file="spec.md")
            st = aidd_status.build_status(d)
            self.assertIsNone(st["tasks"]["tokens_k"])
            text = aidd_status.format_status(st)
            self.assertIn("critical path 35 min", text)
            self.assertNotIn("tokens", text)

    def test_waves_reads_columns_by_header(self):
        self.assertEqual(aidd_status._waves(NEW_TASKS), (2, 35, [150, 80]))
        self.assertEqual(aidd_status._waves(LEGACY_TASKS), (2, 35, []))

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
            ev.append(root, "s1", "subagent", type="general-purpose", desc="security audit", head="best practice")
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
                                         "approval_recorded": False, "tokens_k": 230})
            self.assertEqual(st["code_edits"], 3)
            self.assertEqual(st["auditors"], {"functional": False, "security": True})
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
            self.assertEqual(st["auditors"], {"functional": False, "security": False})
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
            # security+functional always; ui/backend by codes; performance because the UI is touched
            self.assertEqual(set(aidd_status.build_status(d)["auditors"]),
                             {"functional", "security", "ui", "backend", "performance"})
            # without SCREEN/API/db/hot-path codes performance is NOT required
            tmp2, root2, d2 = make_project()
            with tmp2:
                self.assertEqual(set(aidd_status.build_status(d2)["auditors"]), {"functional", "security"})

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
        """A LEGACY approved spec (AC-208): the old close path, per-domain auditors, no verify_run."""
        tmp, root, d = make_project()
        self.approve_legacy(root, d)
        ev.set_active_spec(root, "001-x")
        return tmp, root, d

    def _ready_to_close(self, root, d):
        tick()
        ev.append(root, "s1", "code_edit", path="src/a.py", spec="001-x")
        tick()
        ev.append(root, "s1", "subagent", type="x", desc="functional auditor", head="best practice")
        tick()
        ev.append(root, "s1", "subagent", type="x", desc="security auditor", head="best practice")
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
            self.assertIn("functional", r.stdout)
            self.assertIn("security", r.stdout)
            self.assertEqual(ev.open_specs(root), ["001-x"])

    def test_refused_without_matching_affirmative_answer(self):
        tmp, root, d = self._approved_project()
        with tmp:
            self._ready_to_close(root, d)
            r = run_script("rules", "close", "001-x", cwd=root)          # no answer at all
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("AskUserQuestion", r.stdout)
            self.answer(root, "Close spec 001-x as completed? [spec:001-x]", "No")     # a No
            self.assertEqual(run_script("rules", "close", "001-x", cwd=root).returncode, 1)
            self.answer(root, "Approve these tasks again? [spec:001-x]", "Approve")    # wrong topic
            self.assertEqual(run_script("rules", "close", "001-x", cwd=root).returncode, 1)
            self.assertEqual(ev.open_specs(root), ["001-x"])
            self.assertEqual(ev.get_active_spec(root), "001-x")

    def test_close_answer_older_than_qa_audit_refused(self):
        tmp, root, d = self._approved_project()
        with tmp:
            self.answer(root, "Close this spec? [spec:001-x]", "Yes, close")   # before the audit
            self._ready_to_close(root, d)
            t = time.time() + 30
            os.utime(d / "qa-audit.md", (t, t))
            self.assertEqual(run_script("rules", "close", "001-x", cwd=root).returncode, 1)

    def test_closes_when_covered_and_status_only_edit_keeps_it_closed(self):
        tmp, root, d = self._approved_project()
        with tmp:
            self._ready_to_close(root, d)
            self.answer(root, "Close this spec? [spec:001-x]", "Yes, close")
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
            self.answer(root, "Close this spec? [spec:001-x]", "Yes, close")
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
            self.answer(root, "Close this spec? [spec:001-x]", "Yes, close")
            r = run_script("rules", "close", "001-x", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("approved", r.stdout)

    def test_close_needs_the_exact_label(self):
        tmp, root, d = self._approved_project()
        with tmp:
            self._ready_to_close(root, d)
            self.answer(root, "Close spec 001-x as completed? [spec:001-x]", "Yes", options=["Yes", "No"])
            r = run_script("rules", "close", "001-x", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn('"Yes, close"', r.stdout)

    def test_close_needs_the_spec_tag(self):
        tmp, root, d = self._approved_project()
        with tmp:
            self._ready_to_close(root, d)
            self.answer(root, "Close this spec? [spec:002-y]", "Yes, close")    # wrong tag
            self.assertEqual(run_script("rules", "close", "001-x", cwd=root).returncode, 1)
            self.answer(root, "Close this spec?", "Yes, close")                 # no tag
            self.assertEqual(run_script("rules", "close", "001-x", cwd=root).returncode, 1)
            self.assertEqual(ev.open_specs(root), ["001-x"])

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
            self.answer(root, "Abandon spec 001-x? [spec:001-x]", "No, keep it")
            self.assertEqual(run_script("rules", "abandon", "001-x", cwd=root).returncode, 1)
            self.answer(root, "Close this spec? [spec:001-x]", "Yes, close")   # close != abandon
            self.assertEqual(run_script("rules", "abandon", "001-x", cwd=root).returncode, 1)
            self.assertEqual(ev.open_specs(root), ["001-x"])

    def test_abandon_needs_the_exact_label(self):
        tmp, root, d = self._open()
        with tmp:
            self.prompt(root)
            self.answer(root, "Abandon spec 001-x? [spec:001-x]", "Yes", options=["Yes", "No"])
            r = run_script("rules", "abandon", "001-x", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn('"Abandon"', r.stdout)
            self.assertEqual(ev.open_specs(root), ["001-x"])

    def test_abandon_needs_the_spec_tag(self):
        tmp, root, d = self._open()
        with tmp:
            self.prompt(root)
            self.answer(root, "Abandon this spec? [spec:002-y]", "Abandon")     # wrong tag
            self.assertEqual(run_script("rules", "abandon", "001-x", cwd=root).returncode, 1)
            self.answer(root, "Abandon this spec?", "Abandon")                  # no tag
            self.assertEqual(run_script("rules", "abandon", "001-x", cwd=root).returncode, 1)
            self.assertEqual(ev.open_specs(root), ["001-x"])

    def test_refused_when_not_open(self):
        tmp, root, d = make_project()
        with tmp:
            self.prompt(root)
            self.answer(root, "Abandon this spec? [spec:001-x]", "Abandon")
            self.assertEqual(run_script("rules", "abandon", "001-x", cwd=root).returncode, 1)

    def test_abandon_unblocks_and_status_reflects_it(self):
        tmp, root, d = self._open()
        with tmp:
            self.prompt(root)
            self.assertIn("Open specs: 001-x", run_script("status", cwd=root).stdout)
            self.answer(root, "Abandon this spec? [spec:001-x]", "Abandon")
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
            self.answer(root, "Descartar esta spec? [spec:001-x]", "Descartar")
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


class CallerBase(EvBase):
    """Spec 006: redirects the caller-marker directory (in-process and in subprocesses) to a scratch dir."""

    def setUp(self):
        super().setUp()
        self._hooks_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._hooks_tmp.cleanup)
        base = Path(self._hooks_tmp.name)
        patcher = mock.patch.object(ev, "HOOKS_TMP", base / "aidd-hooks")
        patcher.start()
        self.addCleanup(patcher.stop)
        for k in ("TEMP", "TMP", "TMPDIR"):
            old = os.environ.get(k)
            os.environ[k] = str(base)
            self.addCleanup(lambda k=k, old=old: os.environ.pop(k, None) if old is None
                            else os.environ.__setitem__(k, old))
        os.environ.pop("AIDD_CALLER_TTL", None)

    def write_marker(self, root, session, age=0.0, raw=None):
        p = ev.caller_marker_path(ev.find_root(root))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(raw if raw is not None else json.dumps({"session": session, "ts": time.time() - age}),
                     encoding="utf-8")
        return p

    def cur(self, root):
        return aidd_status._current_session(ev.find_root(root))


class TestCallerSession(CallerBase):
    """FR-001 / AC-001 / AC-002: the caller marker beats 'newest prompt'; synthetic prompts never count."""

    def test_ac001_busy_window_a_marker_for_b_finds_bs_answer(self):
        tmp, root, d = make_project()
        with tmp:
            self.spec_edit(root, file="tasks.md")
            self.prompt(root, session="sB")
            self.answer(root, self.aq(d, "Approve these tasks?"), "Approve", session="sB")
            self.prompt(root, "keep going with the build please", session="sA")      # A is the busy window
            self.prompt(root, "<task-notification>agent done</task-notification>", session="sA")
            r = run_script("rules", "approve", str(d), cwd=root)       # no marker: infers A, B's answer is invisible
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("Inferred session: sA", r.stdout)
            self.write_marker(root, "sB")                              # rule_gate wrote B's marker before the command
            r = run_script("rules", "approve", str(d), cwd=root)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertEqual(len(ev.events(root, kind="approved")), 1)

    def test_ac001_close_finds_bs_answer_through_the_marker(self):
        tmp, root, d = make_project()
        with tmp:
            self.approve_legacy(root, d)                               # legacy close path (AC-208)
            ev.set_active_spec(root, "001-x")
            tick()
            ev.append(root, "sB", "code_edit", path="src/a.py", spec="001-x")
            for desc in ("functional auditor", "security auditor"):
                tick()
                ev.append(root, "sB", "subagent", type="x", desc=desc, head="best practice")
            (d / "qa-audit.md").write_text("# qa\n", encoding="utf-8")
            self.answer(root, "Close this spec? [spec:001-x]", "Yes, close", session="sB")
            self.prompt(root, "another window typing here", session="sA")
            # the inferred session is sA but the tagged click was recorded under sB's window: the `[spec:<id>]`
            # tag binds it to this spec, so the owner is NOT asked to click or type again (no "listo" loop)
            r = run_script("rules", "close", "001-x", cwd=root)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertEqual(ev.open_specs(root), [])

    def test_untagged_close_answer_from_another_window_is_not_adopted(self):
        tmp, root, d = make_project()
        with tmp:
            self.approve_legacy(root, d)
            ev.set_active_spec(root, "001-x")
            tick()
            ev.append(root, "sB", "code_edit", path="src/a.py", spec="001-x")
            for desc in ("functional auditor", "security auditor"):
                tick()
                ev.append(root, "sB", "subagent", type="x", desc=desc, head="best practice")
            (d / "qa-audit.md").write_text("# qa\n", encoding="utf-8")
            self.answer(root, "Close this spec?", "Yes, close", session="sB")          # no [spec:<id>] tag
            self.prompt(root, "another window typing here", session="sA")
            self.assertEqual(run_script("rules", "close", "001-x", cwd=root).returncode, 1)
            self.write_marker(root, "sB")
            self.assertEqual(run_script("rules", "close", "001-x", cwd=root).returncode, 1)   # untagged never counts
            self.assertEqual(ev.open_specs(root), ["001-x"])

    def test_ac002_stale_marker_is_ignored(self):
        tmp, root, d = make_project()
        with tmp:
            self.prompt(root, "I type in window A", session="sA")
            self.write_marker(root, "sB", age=300)
            self.assertEqual(self.cur(root), "sA")
            self.write_marker(root, "sB", age=30)
            self.assertEqual(self.cur(root), "sB")
            self.write_marker(root, "sB", age=121)
            self.assertEqual(self.cur(root), "sA")
            self.write_marker(root, "sB", age=-60)                     # far in the future: not trusted either
            self.assertEqual(self.cur(root), "sA")

    def test_caller_ttl_env_can_only_shorten(self):
        tmp, root, d = make_project()
        with tmp:
            self.prompt(root, "I type in window A", session="sA")
            self.write_marker(root, "sB", age=30)
            with mock.patch.dict(os.environ, {"AIDD_CALLER_TTL": "10"}):
                self.assertEqual(self.cur(root), "sA")
            self.write_marker(root, "sB", age=200)
            with mock.patch.dict(os.environ, {"AIDD_CALLER_TTL": "100000"}):
                self.assertEqual(self.cur(root), "sA")

    def test_ac002_synthetic_prompts_are_skipped(self):
        tmp, root, d = make_project()
        with tmp:
            self.prompt(root, "a real message typed by the user", session="sB")
            self.prompt(root, "<task-notification><summary>done</summary></task-notification>", session="sA")
            self.prompt(root, "[Request interrupted by user]", session="sA")
            self.prompt(root, "<system-reminder>x</system-reminder>", session="sA")
            self.assertEqual(self.cur(root), "sB")
            self.prompt(root, "typed later in A", session="sA")
            self.assertEqual(self.cur(root), "sA")

    def test_corrupt_marker_is_ignored(self):
        tmp, root, d = make_project()
        with tmp:
            self.prompt(root, "I type in window A", session="sA")
            for raw in ("{not json", "[]", '"sB"', "null", "", json.dumps({"session": "sB"}),
                        json.dumps({"session": "sB", "ts": "now"}), json.dumps({"session": "sB", "ts": True}),
                        json.dumps({"session": 5, "ts": time.time()}),
                        json.dumps({"session": "unknown-session", "ts": time.time()}),
                        json.dumps({"session": "  ", "ts": time.time()}),
                        json.dumps({"session": "sB", "ts": time.time(), "pad": "x" * 5000})):
                self.write_marker(root, "sB", raw=raw)
                self.assertEqual(self.cur(root), "sA", raw[:40])

    def test_refusal_names_the_inferred_session_for_approve_close_abandon(self):
        tmp, root, d = make_project()
        with tmp:
            self.spec_edit(root, file="tasks.md")
            ev.set_active_spec(root, "001-x")
            self.prompt(root, "I am in window A today", session="sA")
            for args in (("approve", str(d)), ("abandon", "001-x")):
                r = run_script("rules", *args, cwd=root)
                self.assertEqual(r.returncode, 1, (args, r.stdout))
                self.assertIn("Inferred session: sA", r.stdout, args)
            # close: the note rides on the missing-answer refusal (the gaps are closed first)
            self.approve_legacy(root, d)
            tick()
            ev.append(root, "sA", "code_edit", path="src/a.py", spec="001-x")
            for desc in ("functional auditor", "security auditor"):
                tick()
                ev.append(root, "sA", "subagent", type="x", desc=desc, head="best practice")
            (d / "qa-audit.md").write_text("# qa\n", encoding="utf-8")
            self.prompt(root, "still window A", session="sA")
            r = run_script("rules", "close", "001-x", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("Inferred session: sA", r.stdout)

    def test_refusal_says_none_when_no_prompt_was_recorded(self):
        tmp, root, d = make_project()
        with tmp:
            self.spec_edit(root, file="tasks.md")
            r = run_script("rules", "approve", str(d), cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("Inferred session: none", r.stdout)

    def test_testing_override_still_wins_over_the_marker(self):
        tmp, root, d = make_project()
        with tmp:
            self.write_marker(root, "sB")
            with mock.patch.dict(os.environ, {"AIDD_SESSION_ID": "forced"}):
                self.assertEqual(self.cur(root), "forced")


class TestWhyAbsentWhenClosed(EvBase):
    def test_closed_spec_has_no_why_lines_open_one_does(self):
        tmp, root, d = make_project()
        with tmp:
            self.spec_edit(root, file="tasks.md")
            self.assertTrue(aidd_status.build_status(d)["why_blocked"])
            tick()
            ev.append_spec_closed(root, "s1", "001-x", reason="abandoned", hash="")
            st = aidd_status.build_status(d)
            self.assertFalse(st["open"])
            self.assertEqual(st["why_blocked"], [])


class TestAbandonKeepIt(EvBase):
    """FR-006 / AC-006: a typed "No, keep it" cancels an earlier clicked Abandon."""

    def _open(self):
        tmp, root, d = make_project()
        self.spec_edit(root)
        ev.set_active_spec(root, "001-x")
        return tmp, root, d

    def _abandon(self, root):
        return run_script("rules", "abandon", "001-x", cwd=root)

    def test_typed_keep_it_cancels_an_earlier_abandon_answer(self):
        tmp, root, d = self._open()
        with tmp:
            self.prompt(root)
            self.answer(root, "Abandon spec 001-x? [spec:001-x]", "Abandon")
            self.prompt(root, "No, keep it")
            r = self._abandon(root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertEqual(ev.open_specs(root), ["001-x"])
            self.answer(root, "Abandon spec 001-x? [spec:001-x]", "Abandon")      # a NEW click after it counts
            self.assertEqual(self._abandon(root).returncode, 0)
            self.assertEqual(ev.open_specs(root), [])

    def test_keep_it_variants_and_unknown_session(self):
        for text, session in (("no keep it, thanks", "s1"), ("No, keep it [spec:001-x]", "s1"),
                              ("No, keep it", "unknown-session")):
            tmp, root, d = self._open()
            with tmp:
                self.prompt(root)
                self.answer(root, "Abandon spec 001-x? [spec:001-x]", "Abandon")
                self.prompt(root, text, session=session)
                self.assertEqual(self._abandon(root).returncode, 1, (text, session))

    def test_keep_it_that_does_not_count(self):
        cases = (("No, keep it [spec:002-y]", "s1"),            # names another spec
                 ("<task-notification>No, keep it</task-notification>", "s1"),   # synthetic
                 ("[No, keep it]", "s1"),
                 ("Please, no, keep it", "s1"))                  # does not START with the phrase
        for text, session in cases:
            tmp, root, d = self._open()
            with tmp:
                self.prompt(root)
                self.answer(root, "Abandon spec 001-x? [spec:001-x]", "Abandon")
                self.prompt(root, text, session=session)
                self.assertEqual(self._abandon(root).returncode, 0, (text, session))

    def test_keep_it_before_the_answer_does_not_cancel(self):
        tmp, root, d = self._open()
        with tmp:
            self.prompt(root, "No, keep it")
            self.answer(root, "Abandon spec 001-x? [spec:001-x]", "Abandon")
            self.assertEqual(self._abandon(root).returncode, 0)


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


# ========================================================================= spec 007 (T-05)
# FR-201 activate / FR-204 review + consent approval / FR-205 verify + gate-2 close / FR-208 status

import contextlib  # noqa: E402
import hashlib  # noqa: E402
import io  # noqa: E402
import shutil  # noqa: E402

import aidd_review  # noqa: E402

IDS = ("002-aidd-hard-rules", "F23-eDoc-POS")      # a numeric and a non-numeric real spec id
REVIEW_TEMPLATE = (                                # minimal page: the real template belongs to T-04/T-11
    "<!doctype html><html><head><meta charset=\"utf-8\">"
    "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; "
    "script-src 'sha256-{{SCRIPT_SHA256}}'\"><title>{{TITLE}}</title></head>"
    "<body data-spec=\"{{SPEC_ID}}\" data-h=\"{{TASKS_HASH}}\" data-h8=\"{{TASKS_HASH8}}\" "
    "data-d=\"{{SOURCES_DIGEST}}\" data-g=\"{{GENERATED}}\"><main>{{BODY}}</main>"
    "<script type=\"application/json\" id=\"aidd-data\">{{DATA_JSON}}</script>"
    "<script id=\"aidd-js\">var aidd = 1;</script></body></html>"
)
PLAN_MD = "# plan\n\n## Approach\n\nreuse billing.\n"


def spec_with_rows(rows):
    """SPEC with its Verification table replaced by `rows` [(cmd, expected)]; [] drops the section."""
    head = SPEC.split("## Verification")[0]
    if not rows:
        return head
    body = "".join(f"| {i} | `{c}` | {e} | FR-001 |\n" for i, (c, e) in enumerate(rows, 1))
    return head + "## Verification\n\n| # | Command | Expected | Covers |\n|---|---|---|---|\n" + body


class Spec007Base(EvBase):
    def setUp(self):
        env = mock.patch.dict(os.environ)          # the owner's shell may export AIDD_RULES / AIDD_R5_AUDIT
        env.start()                                # snapshot BEFORE EvBase: the whole env is restored after
        self.addCleanup(env.stop)
        super().setUp()
        for k in ("AIDD_RULES", "AIDD_R5_AUDIT", "AIDD_VERIFY_TIMEOUT", "AIDD_R7_FIX_EDITS"):
            os.environ.pop(k, None)

    def fresh_log(self):
        """A new evidence log: subTests that build a project each must not share recorded events."""
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        os.environ["AIDD_EVIDENCE_DIR"] = t.name

    def project(self, name="001-x", spec=SPEC, tasks=TASKS):
        self.fresh_log()
        tmp, root, d = make_project(name=name, spec=spec, tasks=tasks)
        (d / "plan.md").write_text(PLAN_MD, encoding="utf-8")
        backdate(d / "plan.md")
        self.spec_edit(root, spec=name, file="tasks.md")
        return tmp, root, d

    @staticmethod
    def tag(d):
        return aidd_status.approval_tag((Path(d) / "tasks.md").read_text(encoding="utf-8"))

    @staticmethod
    def page(d, age=10):
        path, _wrote = aidd_review.generate(d, template_text=REVIEW_TEMPLATE)
        backdate(path, age)
        return path

    @staticmethod
    def review(d, checked=True, approved=True, comments=None, skip=(), tasks_hash=None, digest=None, age=5):
        keys = aidd_review.reviewable_keys(d)
        th = tasks_hash or aidd_rules.approval_hash((Path(d) / "tasks.md").read_text(encoding="utf-8"))
        dg = digest or aidd_review.sources_digest(d)
        # aidd:FR-304 the compact grammar `codes-v2` the page writes: one `- [x] <code>` line per reviewable code
        out = ["---", f"spec: {Path(d).name}", f"tasks_hash: {th}", f"sources_digest: {dg}",
               "format: codes-v2", f"approved: {'true' if approved else 'false'}", "generated: 2026-10-05",
               "reviewed: 2026-10-05T10:00:00", "---"]
        for k in keys:
            if k in skip:
                continue
            out += [f"- [{'x' if checked else ' '}] {k}"]
            if (comments or {}).get(k):
                out.append("> " + comments[k])
        p = Path(d) / "review.md"
        p.write_text("\n".join(out) + "\n", encoding="utf-8")
        backdate(p, age)
        return p

    def reviewed(self, name="001-x", **kw):
        tmp, root, d = self.project(name)
        self.page(d)
        self.review(d, **kw)
        self.prompt(root, "looks good overall")          # the current session is s1
        return tmp, root, d

    def approve_rc(self, root, d):
        return run_script("rules", "approve", str(d), cwd=root)

    def inproc(self, fn, *args, tty=False):
        buf = io.StringIO()
        with mock.patch.object(aidd_status, "_tty_confirm", return_value=tty), contextlib.redirect_stdout(buf):
            rc = fn(*args)
        return rc, buf.getvalue()

    def assert_refused(self, root, d, *needles):
        before = (d / "tasks.md").read_bytes()
        r = self.approve_rc(root, d)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual((d / "tasks.md").read_bytes(), before)
        for n in needles:
            self.assertIn(n, r.stdout)
        return r


class TestReviewApproval(Spec007Base):
    """FR-204 / AC-205 / AC-206 / AC-217: review content + one owner consent act."""

    def test_ac205_complete_review_without_consent_is_refused(self):
        for sid in IDS:
            with self.subTest(sid):
                tmp, root, d = self.reviewed(sid)
                with tmp:
                    self.assertTrue(aidd_review.review_state(d)["complete"])
                    tag = self.tag(d)
                    self.assert_refused(root, d, "review.md is complete; the owner must confirm: answer the "
                                        f"question tagged `{tag}` or type `approve {tag}`")
                    self.assertEqual(ev.events(root, kind="approved"), [])
                    self.assertEqual(ev.get_gate_spec(root), "")

    def test_tagged_answer_approves_as_review_answer_and_activates(self):
        for sid in IDS:
            with self.subTest(sid):
                tmp, root, d = self.project(sid)
                with tmp:
                    self.page(d)
                    first = aidd_review.reviewable_keys(d)[0]
                    md = self.review(d, comments={first: "rename the billing helper"})
                    self.answer(root, self.aq(d), "Approve")
                    r = self.approve_rc(root, d)
                    self.assertEqual(r.returncode, 0, r.stdout)
                    self.assertIn(f"note: {first}: rename the billing helper", r.stdout)
                    a = ev.latest_approved(root, sid)
                    self.assertEqual((a["gate"], a["source"]), (2, "review+answer"))
                    self.assertEqual(a["review_sha1"], hashlib.sha1(md.read_bytes()).hexdigest())
                    self.assertEqual(a["verify_hash"], aidd_rules.verification_hash(SPEC))
                    self.assertIn("consent_ts", a)
                    self.assertEqual(ev.get_gate_spec(root), sid)
                    ch = ev.recent_gate_pointer_changes(root)
                    self.assertEqual((ch[0]["spec"], ch[0]["by"]), (sid, "approve"))

    def test_tagged_prompt_approves_as_review_prompt(self):
        for text in ("approve {tag}", "ok, I approve it {tag}"):
            with self.subTest(text):
                tmp, root, d = self.reviewed()
                with tmp:
                    self.prompt(root, text.format(tag=self.tag(d)))
                    r = self.approve_rc(root, d)
                    self.assertEqual(r.returncode, 0, r.stdout)
                    self.assertEqual(ev.latest_approved(root, "001-x")["source"], "review+prompt")

    def test_tty_confirmation_approves_as_review_tty(self):
        tmp, root, d = self.reviewed("F23-eDoc-POS")
        with tmp:
            rc, out = self.inproc(aidd_status.cmd_approve, str(d), tty=False)
            self.assertEqual(rc, 1, out)
            rc, out = self.inproc(aidd_status.cmd_approve, str(d), tty=True)
            self.assertEqual(rc, 0, out)
            self.assertEqual(ev.latest_approved(root, "F23-eDoc-POS")["source"], "review+tty")

    def test_negated_untagged_or_wrong_tag_prompt_does_not_count(self):
        tmp, root, d = self.reviewed()
        with tmp:
            tag = self.tag(d)
            for text in (f"do not approve {tag}", "approve it", "approve [tasks:deadbeef]",
                         f"I reject this {tag}", f"<agent-message> approve {tag}"):
                self.prompt(root, text)
                self.assert_refused(root, d, "the owner must confirm")
            self.prompt(root, f"approve {tag}", session="s-other")
            self.prompt(root, "still here", session="s1")
            self.assert_refused(root, d, "the owner must confirm")

    def test_consent_older_than_review_md_is_refused(self):
        tmp, root, d = self.project()
        with tmp:
            self.page(d)
            self.answer(root, self.aq(d), "Approve")
            md = self.review(d)
            t = time.time() + 30
            os.utime(md, (t, t))                       # the review.md arrived after the answer
            self.assert_refused(root, d, "the owner must confirm")

    def test_stale_or_incomplete_review_is_refused_naming_the_cause(self):
        cases = {
            "hash": ("review.md was generated for tasks hash", "run `aidd review` again"),
            "digest": ("sources digest",),
            "approved_false": ("approved: false",),
            "older": ("older than review.html",),
            "missing": ("unchecked sections",),
        }
        for case, needles in cases.items():
            with self.subTest(case):
                tmp, root, d = self.project()
                with tmp:
                    self.page(d)
                    if case == "approved_false":
                        self.review(d, approved=False)
                    elif case == "missing":
                        self.review(d, skip=(aidd_review.reviewable_keys(d)[-1],))
                    else:
                        self.review(d)
                    if case == "hash":       # title cell edit after the review (page not regenerated)
                        p = d / "tasks.md"
                        p.write_text(p.read_text(encoding="utf-8").replace("Agent min: 10", "Agent min: 11"),
                                     encoding="utf-8")
                        backdate(p, 100)
                    elif case == "digest":   # plan.md edited and the page regenerated
                        (d / "plan.md").write_text(PLAN_MD + "\nmore\n", encoding="utf-8")
                        backdate(d / "plan.md", 100)
                        self.page(d, age=7)
                    elif case == "older":
                        backdate(d / "review.md", 20)
                    self.answer(root, self.aq(d), "Approve")   # a valid answer: the review is what refuses
                    self.assert_refused(root, d, *needles)

    def test_current_page_refuses_the_answer_only_route(self):
        for sid in IDS:
            with self.subTest(sid):
                tmp, root, d = self.project(sid)
                with tmp:
                    self.page(d)
                    self.answer(root, self.aq(d), "Approve")
                    self.assert_refused(root, d, "a review exists", "complete it")

    def test_no_page_keeps_the_answer_route_with_gate_2(self):
        for sid in IDS:
            with self.subTest(sid):
                tmp, root, d = self.project(sid)
                with tmp:
                    self.answer(root, self.aq(d), "Approve")
                    r = self.approve_rc(root, d)
                    self.assertEqual(r.returncode, 0, r.stdout)
                    a = ev.latest_approved(root, sid)
                    self.assertEqual((a["gate"], a["source"]), (2, "answer"))
                    self.assertNotIn("review_sha1", a)
                    self.assertEqual(ev.get_gate_spec(root), sid)

    def test_ac217_oversize_sources_keep_the_answer_route(self):
        tmp, root, d = self.project("F23-eDoc-POS")
        with tmp:
            self.page(d)                                   # a page from before the padding
            (d / "plan.md").write_text(PLAN_MD + "x" * 450_000, encoding="utf-8")
            backdate(d / "plan.md", 100)
            with self.assertRaises(ValueError):
                aidd_review.generate(d, template_text=REVIEW_TEMPLATE)
            self.answer(root, self.aq(d), "Approve")
            r = self.approve_rc(root, d)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertEqual(ev.latest_approved(root, "F23-eDoc-POS")["source"], "answer")

    def test_status_cell_edit_and_the_approved_line_keep_the_review_valid(self):
        tmp, root, d = self.reviewed()
        with tmp:
            p = d / "tasks.md"
            p.write_text(p.read_text(encoding="utf-8").replace("Status: todo", "Status: doing"), encoding="utf-8")
            backdate(p, 100)
            self.assertTrue(aidd_review.review_state(d)["complete"])
            self.answer(root, self.aq(d), "Approve")
            self.assertEqual(self.approve_rc(root, d).returncode, 0)
            self.assertIn("Approved:", p.read_text(encoding="utf-8"))
            self.assertTrue(aidd_review.review_state(d)["complete"])          # AC-206 (c)
            self.assertFalse(aidd_review.generate(d, template_text=REVIEW_TEMPLATE)[1])

    def test_invalid_or_missing_verification_refuses_approval(self):
        for spec in (spec_with_rows([('python -c "pass"', "exit 0")]), spec_with_rows([])):
            with self.subTest(spec[-60:]):
                tmp, root, d = self.project(spec=spec)
                with tmp:
                    self.answer(root, self.aq(d), "Approve")
                    self.assert_refused(root, d, "R10", "Verification")


def overcap_spec(rows=2001):
    """SPEC with a requirements table of `rows` coded rows: more items than the compact page can show (FR-301)."""
    head, tail = SPEC.split("## Verification")
    body = "".join(f"| FR-{i:03d} | requirement {i} |\n" for i in range(1, rows + 1))
    return (head + "## Requirements\n\n| Code | Requirement |\n|---|---|\n" + body
            + "\n## Verification" + tail)


class TestCompactReviewMessages(Spec007Base):
    """aidd:FR-307 aidd:FR-304 the owner-facing texts of the new flow and the legacy refusal."""

    def test_legacy_review_md_is_refused_with_the_regenerate_cause_and_no_traceback(self):
        for sid in IDS:
            with self.subTest(sid):
                tmp, root, d = self.project(sid)
                with tmp:
                    self.page(d)
                    lines = ["---", f"spec: {sid}", "tasks_hash: " + aidd_rules.approval_hash(
                        (d / "tasks.md").read_text(encoding="utf-8")), f"sources_digest: {aidd_review.sources_digest(d)}",
                        "approved: true", "generated: 2026-10-05", "reviewed: 2026-10-05T10:00:00", "---"]
                    for k in aidd_review.reviewable_keys(d):
                        lines += [f"## {k}", "- [x] Approved"]
                    p = d / "review.md"
                    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    backdate(p, 5)
                    self.answer(root, self.aq(d), "Approve")
                    before = (d / "tasks.md").read_bytes()
                    rc, out = self.inproc(aidd_status.cmd_approve, str(d))
                    self.assertEqual(rc, 1, out)
                    self.assertIn("old per-heading grammar", out)
                    self.assertIn("run aidd review", out)
                    self.assertNotIn("Traceback", out)
                    self.assertEqual((d / "tasks.md").read_bytes(), before)
                    self.assertEqual(ev.events(root, kind="approved"), [])
                    # `aidd status --json`: the new `legacy` field of the review summary
                    j = json.loads(run_script("status", str(d), "--json", cwd=root).stdout)
                    self.assertIs(self.find_key(j, "legacy", within="review"), True)
                    self.assertEqual(aidd_status._review_text(aidd_status._review_summary(d)),
                                     "legacy review.md (regenerate)")

    @staticmethod
    def find_key(obj, key, within=None):
        """The value of `key` inside the first dict stored under the key `within` (any depth)."""
        if isinstance(obj, dict):
            if within in obj and isinstance(obj[within], dict) and key in obj[within]:
                return obj[within][key]
            for v in obj.values():
                r = TestCompactReviewMessages.find_key(v, key, within)
                if r is not None:
                    return r
        elif isinstance(obj, list):
            for v in obj:
                r = TestCompactReviewMessages.find_key(v, key, within)
                if r is not None:
                    return r
        return None

    def test_complete_review_without_consent_tells_the_wait_then_one_question_flow(self):
        for sid in IDS:
            with self.subTest(sid):
                tmp, root, d = self.reviewed(sid)
                with tmp:
                    tag = self.tag(d)
                    r = self.assert_refused(root, d, f"review.md is complete; the owner must confirm: answer the "
                                            f"question tagged `{tag}` or type `approve {tag}`",
                                            f"aidd review specs/{sid} --wait", "ONE question")
                    self.assertNotIn("move the downloaded", r.stdout)

    def test_incomplete_review_fix_names_wait_and_never_tells_the_owner_to_move_a_file(self):
        tmp, root, d = self.project()
        with tmp:
            self.page(d)
            self.answer(root, self.aq(d), "Approve")
            r = self.assert_refused(root, d, "a review exists", "complete it", "aidd review specs/001-x --wait",
                                    "Aprobar y guardar", "ONE question")
            self.assertNotIn("move the downloaded", r.stdout)
            self.assertNotIn("press Send", r.stdout)

    def test_comment_of_a_checked_code_is_printed_as_a_note(self):
        spec = SPEC.replace("## Verification", "## Requirements\n\n| Code | Requirement |\n|---|---|\n"
                            "| FR-301 | the compact page |\n\n## Verification")
        for sid in IDS:
            with self.subTest(sid):
                tmp, root, d = self.project(sid, spec=spec)
                with tmp:
                    self.page(d)
                    self.assertIn("FR-301", aidd_review.reviewable_keys(d))
                    self.review(d, comments={"FR-301": "keep it short"})
                    self.answer(root, self.aq(d), "Approve")
                    r = self.approve_rc(root, d)
                    self.assertEqual(r.returncode, 0, r.stdout)
                    self.assertIn("note: FR-301: keep it short", r.stdout)

    def test_review_text_states(self):
        base = {"page": True, "page_current": True, "present": False, "complete": False, "legacy": False}
        self.assertEqual(aidd_status._review_text(base), "waiting for owner")
        self.assertEqual(aidd_status._review_text(dict(base, present=True, legacy=True)),
                         "legacy review.md (regenerate)")
        self.assertEqual(aidd_status._review_text(dict(base, page_current=False)), "page stale (run `aidd review`)")
        self.assertEqual(aidd_status._review_text({"page": False}), "no page")
        self.assertEqual(aidd_status._review_text(dict(base, complete=True)), "complete ✔")

    def test_why_blocked_line_names_the_wait_flow(self):
        tmp, root, d = self.project()
        with tmp:
            out = run_script("status", str(d), cwd=root).stdout
            self.assertIn("aidd review 001-x --wait", out)


class TestOverCapNeverApprovedByAnAnswer(Spec007Base):
    """aidd:FR-307 aidd:AC-303 a spec the compact page cannot show (2 001 coded rows) has no answer-only route."""

    def overcap_project(self, sid, with_page):
        tmp, root, d = self.project(sid)
        if with_page:
            self.page(d)                                   # a (now stale) page from before the padding
        (d / "spec.md").write_text(overcap_spec(), encoding="utf-8")
        backdate(d / "spec.md", 100)
        return tmp, root, d

    def test_bare_tagged_answer_is_refused_with_and_without_a_review_html(self):
        for sid in IDS:
            for with_page in (False, True):
                with self.subTest(sid=sid, page=with_page):
                    tmp, root, d = self.overcap_project(sid, with_page)
                    with tmp:
                        self.assertTrue(aidd_review.review_state(d)["reason"].startswith("too many items"))
                        self.answer(root, self.aq(d), "Approve")
                        r = self.assert_refused(root, d, "too many items")
                        self.assertNotIn("no review.html", r.stdout)
                        self.assertNotIn("Traceback", r.stdout)
                        self.assertEqual(ev.events(root, kind="approved"), [])
                        self.assertEqual(ev.get_gate_spec(root), "")

    def test_summary_label_is_refused_for_an_over_cap_spec(self):
        for sid in IDS:
            for with_page in (False, True):
                with self.subTest(sid=sid, page=with_page):
                    tmp, root, d = self.overcap_project(sid, with_page)
                    with tmp:
                        self.answer(root, f"¿Aprobar las tareas? {self.tag(d)}", "Aprobar con resumen")
                        self.assert_refused(root, d, "too many items")
                        self.assertEqual(ev.events(root, kind="approved"), [])

    def test_source_too_large_keeps_its_answer_only_route(self):
        tmp, root, d = self.project("F23-eDoc-POS")
        with tmp:
            (d / "plan.md").write_text(PLAN_MD + "x" * 450_000, encoding="utf-8")
            backdate(d / "plan.md", 100)
            self.assertTrue(aidd_review.review_state(d)["reason"].startswith("source too large"))
            self.answer(root, self.aq(d), "Approve")
            r = self.approve_rc(root, d)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertEqual(ev.latest_approved(root, "F23-eDoc-POS")["source"], "answer")


class TestSummaryRoute(Spec007Base):
    """aidd:FR-313 aidd:AC-327..AC-330 the owner's exact-label `Aprobar con resumen` answer."""

    LABEL = "Aprobar con resumen"

    def ask(self, root, d, label=None, question=None, options=None, session="s1"):
        q = question or f"¿Aprobar las tareas? {self.tag(d)}"
        self.answer(root, q, label or self.LABEL, session=session, options=options)

    def approved_source(self, root, sid):
        a = ev.latest_approved(root, sid)
        return None if a is None else a.get("source")

    def test_exact_label_and_outer_spaces_approve_with_source_summary_without_a_page(self):
        for sid in IDS:
            for label in (self.LABEL, f"  {self.LABEL} "):
                with self.subTest(sid=sid, label=label):
                    tmp, root, d = self.project(sid)
                    with tmp:
                        self.ask(root, d, label)
                        r = self.approve_rc(root, d)
                        self.assertEqual(r.returncode, 0, r.stdout)
                        self.assertIn("approved through summary", r.stdout)
                        a = ev.latest_approved(root, sid)
                        self.assertEqual((a["gate"], a["source"]), (2, "summary"))
                        self.assertNotIn("review_sha1", a)
                        self.assertIn("consent_ts", a)
                        self.assertEqual(ev.get_gate_spec(root), sid)
                        self.assertFalse((d / "review.md").exists())
                        self.assertFalse((d / "review.html").exists())

    def test_near_misses_are_refused_and_never_approve_through_the_generic_route(self):
        for sid in IDS:
            for label in ("aprobar con resumen", "APROBAR CON RESUMEN", "Aprobar con resumem", "Aprobar con resumen ya",
                          "Aprobar con resumen.", "Aprobar con  resumen"):
                with self.subTest(sid=sid, label=label):
                    tmp, root, d = self.project(sid)
                    with tmp:
                        self.ask(root, d, label)
                        self.assert_refused(root, d, "Refused")
                        self.assertEqual(ev.events(root, kind="approved"), [])

    def test_missing_older_tag_and_question_without_the_approve_word_are_refused(self):
        for sid in IDS:
            cases = {
                "no tag": lambda d: "¿Aprobar las tareas?",
                "older tag": lambda d: "¿Aprobar las tareas? [tasks:deadbeef]",
                "no approve word": lambda d: f"¿Cómo seguimos? {self.tag(d)}",
            }
            for name, qf in cases.items():
                with self.subTest(sid=sid, case=name):
                    tmp, root, d = self.project(sid)
                    with tmp:
                        # the word is only in the OPTION labels for "no approve word": the topic reads the question
                        self.ask(root, d, question=qf(d), options=[self.LABEL, "Revisar en HTML visual"])
                        self.assert_refused(root, d, "Refused")
                        self.assertEqual(ev.events(root, kind="approved"), [])

    def test_typed_prompt_has_no_route_to_source_summary(self):
        for sid in IDS:
            with self.subTest(sid):
                tmp, root, d = self.project(sid)
                with tmp:
                    self.prompt(root, f"Aprobar con resumen {self.tag(d)}")
                    self.assert_refused(root, d, "Refused")
                    self.assertEqual(ev.events(root, kind="approved"), [])
                    self.assertIsNone(aidd_status._summary_answer(ev, root, "s1", 0.0, self.tag(d)))

    def test_agent_forged_text_is_not_accepted(self):
        for sid in IDS:
            with self.subTest(sid):
                tmp, root, d = self.project(sid)
                with tmp:
                    tag = self.tag(d)
                    # a question the agent asked but the owner never answered
                    tick()
                    ev.append(root, "s1", "question", text=f"¿Aprobar las tareas? {tag}",
                              options=[[self.LABEL, "Revisar en HTML visual"]])
                    # a file the agent wrote, an assistant-style message and a Bash echo recorded as other events
                    (d / "answer.txt").write_text(f"{self.LABEL} {tag}\n", encoding="utf-8")
                    self.prompt(root, f"<assistant> {self.LABEL} {tag}")
                    tick()
                    ev.append(root, "s1", "bash", command=f"echo '{self.LABEL} {tag}'")
                    # an answer recorded for ANOTHER session
                    self.answer(root, f"¿Aprobar las tareas? {tag}", self.LABEL, session="s-other")
                    self.prompt(root, "still here", session="s1")        # the current session is s1 again
                    self.assertIsNone(aidd_status._summary_answer(ev, root, "s1", 0.0, tag))
                    self.assert_refused(root, d, "Refused")
                    self.assertEqual(ev.events(root, kind="approved"), [])

    def test_stale_page_current_page_and_complete_review_approve_with_summary(self):
        for sid in IDS:
            for mode in ("stale", "current", "complete"):
                with self.subTest(sid=sid, mode=mode):
                    tmp, root, d = self.project(sid)
                    with tmp:
                        page = self.page(d)
                        if mode == "stale":
                            (d / "plan.md").write_text(PLAN_MD + "\nmore\n", encoding="utf-8")
                            backdate(d / "plan.md", 100)
                        elif mode == "complete":
                            self.review(d)
                        html_before = page.read_bytes()
                        had_md = (d / "review.md").exists()
                        self.ask(root, d)
                        r = self.approve_rc(root, d)
                        self.assertEqual(r.returncode, 0, r.stdout)
                        a = ev.latest_approved(root, sid)
                        self.assertEqual(a["source"], "summary")      # never review+answer, never answer
                        self.assertNotIn("review_sha1", a)
                        self.assertEqual(page.read_bytes(), html_before)
                        self.assertEqual((d / "review.md").exists(), had_md)

    def test_current_page_and_bare_approve_stay_refused_and_a_newer_approve_cancels_the_summary(self):
        for sid in IDS:
            with self.subTest(sid):
                tmp, root, d = self.project(sid)
                with tmp:
                    self.page(d)
                    self.answer(root, self.aq(d), "Approve")
                    self.assert_refused(root, d, "a review exists", "complete it")
                    self.ask(root, d)                                  # the owner picks the summary ...
                    self.answer(root, self.aq(d), "Approve")           # ... and later a bare Approve: newest wins
                    self.assert_refused(root, d, "a review exists")
                    self.assertEqual(ev.events(root, kind="approved"), [])

    def test_answer_older_than_tasks_md_does_not_count(self):
        tmp, root, d = self.project()
        with tmp:
            self.ask(root, d)
            p = d / "tasks.md"
            t = time.time() + 30
            os.utime(p, (t, t))                      # tasks.md changed after the answer (tag unchanged: status cell)
            self.assertIsNone(aidd_status._summary_answer(ev, root, "s1", aidd_status._mtime(p), self.tag(d)))

    def test_approve_label_regression_and_no_page_bare_approve_keeps_source_answer(self):
        rx = aidd_status.APPROVE_LABEL
        for ok in ("Approve", "Aprobar", "Aprobado", "Aprobar las tareas", "approve these tasks", "APROBAR"):
            self.assertTrue(rx.search(ok), ok)
        for bad in ("Aprobar con resumen", "aprobar con resumen", "Aprobar con resumem", "Aprobar con resumen ya",
                    "Aprobar  con   resumen"):
            self.assertFalse(rx.search(bad), bad)
        for sid in IDS:
            with self.subTest(sid):
                tmp, root, d = self.project(sid)
                with tmp:
                    self.answer(root, self.aq(d), "Approve")
                    self.assertEqual(self.approve_rc(root, d).returncode, 0)
                    self.assertEqual(self.approved_source(root, sid), "answer")

    def test_summary_answer_never_raises(self):
        self.assertIsNone(aidd_status._summary_answer(object(), "/nowhere", "s1", 0.0, "[tasks:abcdef12]"))
        self.assertIsNone(aidd_status._summary_answer(ev, "/nowhere", "s1", 0.0, ""))
        self.assertIsNone(aidd_status._summary_answer(ev, None, None, None, None))


class TestActivate(Spec007Base):
    """FR-201 / AC-202: `aidd rules activate <id>` is the explicit gate-pointer writer."""

    def test_activate_writes_the_pointer_and_logs_each_change(self):
        for sid in IDS:
            with self.subTest(sid):
                tmp, root, d = self.project(sid)
                with tmp:
                    add_spec(root, "003-other", spec=SPEC_OTHER)
                    self.spec_edit(root, spec="003-other", file="plan.md")
                    for arg in (sid, f"specs/{sid}", str(d)):
                        r = run_script("rules", "activate", arg, cwd=root)
                        self.assertEqual(r.returncode, 0, r.stdout)
                        self.assertEqual(ev.get_gate_spec(root), sid)
                    self.assertEqual(len(ev.events(root, kind="gate_pointer")), 1)   # only on change
                    r = run_script("rules", "activate", "003-other", cwd=root)
                    self.assertIn(f"gate pointer: {sid} -> 003-other", r.stdout)
                    ch = ev.recent_gate_pointer_changes(root)
                    self.assertEqual((ch[0]["spec"], ch[0]["prev"]), ("003-other", sid))
                    out = run_script("status", cwd=root).stdout
                    self.assertIn(f"gate pointer: 003-other · last changes: {sid} -> 003-other", out)

    def test_activate_refuses_a_spec_that_is_not_open(self):
        tmp, root, d = make_project(name="F23-eDoc-POS")          # no plan/tasks edit recorded
        with tmp:
            r = run_script("rules", "activate", "F23-eDoc-POS", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("not an open spec", r.stdout)
            self.assertEqual(run_script("rules", "activate", "999-ghost", cwd=root).returncode, 1)
            self.assertEqual(ev.get_gate_spec(root), "")
            self.assertEqual(ev.events(root, kind="gate_pointer"), [])


SCRIPTS = {
    "fail.py": 'print("billing check FAILED: 1 of 3 assertions")\nraise SystemExit(3)\n',
    "zero.py": 'import sys\nsys.stderr.write("\\nRan 0 tests in 0.000s\\n\\nOK\\n")\n',
    "sleep.py": 'import time\nprint("starting a long check", flush=True)\ntime.sleep(20)\n',
    "gen.py": ('from pathlib import Path\np = Path("src/gen_out.txt")\n'
               'if not p.exists():\n    p.write_text("generated", encoding="utf-8")\n'
               'print("generator check ok: 3 assertions passed")\n'),
}


class TestVerify(Spec007Base):
    """FR-205 / AC-209 / AC-216 / AC-218: `aidd verify <spec>` executes the Verification table."""

    def vproject(self, rows, name="F23-eDoc-POS"):
        tmp, root, d = self.project(name, spec=spec_with_rows(rows))
        for n, body in SCRIPTS.items():
            (root / "src" / n).write_text(body, encoding="utf-8")
            backdate(root / "src" / n, 300)
        return tmp, root, d

    def test_pass_writes_evidence_and_records_the_event(self):
        for sid in IDS:
            with self.subTest(sid):
                tmp, root, d = self.vproject([("python src/check.py", "exit 0"),
                                              ("python src/check.py", "contains: assertions passed")], sid)
                with tmp:
                    r = run_script("verify", sid, cwd=root)
                    self.assertEqual(r.returncode, 0, r.stdout)
                    f = d / "evidence" / "verify-1.txt"
                    lines = f.read_text(encoding="utf-8").split("\n")
                    self.assertRegex(lines[0], r"^# python src/check\.py \| exit 0 \| \d{4}-\d{2}-\d{2}T")
                    self.assertIn("3 assertions passed", lines[1])
                    run = ev.latest_verify_run(root, sid)
                    self.assertTrue(run["ok"] and run["stable"])
                    self.assertEqual(run["verify_hash"], aidd_rules.verification_hash((d / "spec.md").read_text(encoding="utf-8")))
                    self.assertEqual(run["results"][0]["evidence"], "evidence/verify-1.txt")
                    self.assertEqual(run["results"][0]["sha1"], hashlib.sha1(f.read_bytes()).hexdigest())
                    self.assertLessEqual(run["started"], run["ts"])
                    self.assertEqual(aidd_rules.verification_state(d, root)["status"], "passed")

    def test_reverify_is_incremental_and_full_reruns_everything(self):
        """Amendment to spec 007: after a table edit only the new/changed rows run; the rest are REUSED while
        the code is unchanged; --full and a code change re-run everything."""
        rows = [("python src/check.py", "exit 0")]
        tmp, root, d = self.vproject(rows)
        with tmp:
            self.assertEqual(run_script("verify", "F23-eDoc-POS", cwd=root).returncode, 0)
            first = ev.latest_verify_run(root, "F23-eDoc-POS")
            self.assertEqual(first["results"][0]["expected"], "exit 0")
            self.assertTrue(first["code_fp_end"].startswith("c2:"))
            (d / "spec.md").write_text(spec_with_rows(rows + [("python src/check.py", "contains: assertions passed")]),
                                       encoding="utf-8")
            self.assertEqual(aidd_rules.verification_state(d, root)["status"], "stale")   # a row was added
            r = run_script("verify", "F23-eDoc-POS", cwd=root)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("REUSED row 1", r.stdout)
            self.assertIn("PASS row 2", r.stdout)
            second = ev.latest_verify_run(root, "F23-eDoc-POS")
            self.assertEqual([x.get("reused") for x in second["results"]], [True, None])
            self.assertEqual(second["code_since"], first["started"])
            self.assertEqual(aidd_rules.verification_state(d, root)["status"], "passed")
            r = run_script("verify", "F23-eDoc-POS", "--full", cwd=root)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertNotIn("REUSED", r.stdout)
            cp = root / "src" / "check.py"
            cp.write_text(cp.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
            self.assertEqual(aidd_rules.verification_state(d, root)["status"], "stale")   # a code change
            r = run_script("verify", "F23-eDoc-POS", cwd=root)
            self.assertNotIn("REUSED", r.stdout)

    def test_scope_lets_other_specs_change_code_while_this_one_stays_verified(self):
        """A `Scope:` line in ## Verification: edits outside it (another spec in parallel) never make the run
        stale or unstable; an edit inside it does."""
        tmp, root, d = self.vproject([("python src/check.py", "exit 0")])
        with tmp:
            spec = d / "spec.md"
            spec.write_text(spec.read_text(encoding="utf-8").replace("## Verification\n", "## Verification\n\nScope: src/check.py\n", 1),
                            encoding="utf-8")
            r = run_script("verify", "F23-eDoc-POS", cwd=root)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("scope: src/check.py", r.stdout)
            self.assertEqual(ev.latest_verify_run(root, "F23-eDoc-POS")["code_scope"], ["src/check.py"])
            tick()
            (root / "src" / "other_spec.py").write_text("print('parallel work of another spec')\n", encoding="utf-8")
            ev.append(root, "s1", "code_edit", path=str(root / "src" / "other_spec.py"), target="F99-other")
            self.assertEqual(aidd_rules.verification_state(d, root)["status"], "passed")
            cp = root / "src" / "check.py"
            cp.write_text(cp.read_text(encoding="utf-8") + "\n# mine\n", encoding="utf-8")
            self.assertEqual(aidd_rules.verification_state(d, root)["status"], "stale")

    def test_generated_outputs_never_loop_the_verification(self):
        """A command that rewrites a file with a new timestamp every run used to fail forever ("tree changed")
        and pushed the agent to edit the generator, which staled the run again. Now the failure names the files,
        and declaring `Generated:` makes the gate accept THAT run: no re-run, no code edit."""
        tmp, root, d = self.vproject([("python src/stamp.py", "exit 0")])
        with tmp:
            (root / "src" / "stamp.py").write_text(
                'import time\nopen("src/graph_out.json", "w").write(str(time.time()))\n'
                'print("stamp ok: 3 assertions passed")\n', encoding="utf-8")
            r = run_script("verify", "F23-eDoc-POS", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("rewrote files: src/graph_out.json", r.stdout)
            self.assertIn("Generated: src/graph_out.json", r.stdout)
            run = ev.latest_verify_run(root, "F23-eDoc-POS")
            self.assertFalse(run["ok"])
            self.assertEqual(run["code_changed"], ["src/graph_out.json"])
            probs =aidd_rules.verification_gaps(ev, root, d)
            self.assertTrue(any("rewrote files" in p["message"] and "Generated:" in p["fix"] for p in probs), probs)
            spec = d / "spec.md"                                   # the ONLY fix: declare the output
            spec.write_text(spec.read_text(encoding="utf-8").replace("## Verification\n", "## Verification\n\nGenerated: src/graph_out.json\n", 1),
                            encoding="utf-8")
            self.assertEqual(aidd_rules.verification_state(d, root)["status"], "passed")
            self.assertEqual(ev.latest_verify_run(root, "F23-eDoc-POS")["ts"], run["ts"])    # same run, not re-executed
            tick()
            (root / "src" / "graph_out.json").write_text("rewritten by a later regeneration", encoding="utf-8")
            self.assertEqual(aidd_rules.verification_state(d, root)["status"], "passed")     # outputs never stale it
            (root / "src" / "stamp.py").write_text((root / "src" / "stamp.py").read_text(encoding="utf-8") + "\n# edit\n", encoding="utf-8")
            self.assertEqual(aidd_rules.verification_state(d, root)["status"], "stale")      # real code still does
            r = run_script("verify", "F23-eDoc-POS", cwd=root)
            self.assertEqual(r.returncode, 0, r.stdout)                                      # declared: stable from the start
            self.assertIn("declared Generated", r.stdout)

    def test_failing_zero_test_and_short_output_rows_fail(self):
        for cmd, why in (("python src/fail.py", "exit 3"), ("python src/zero.py", "zero tests ran"),
                         ("python src/billing.py", "output too short")):
            with self.subTest(cmd):
                tmp, root, d = self.vproject([(cmd, "exit 0")])
                with tmp:
                    r = run_script("verify", str(d), cwd=root)
                    self.assertEqual(r.returncode, 1, r.stdout)
                    self.assertIn("FAIL row 1", r.stdout)
                    self.assertIn(why, r.stdout)
                    self.assertTrue((d / "evidence" / "verify-1.txt").is_file())
                    run = ev.latest_verify_run(root, "F23-eDoc-POS")
                    self.assertFalse(run["ok"])
                    self.assertFalse(run["results"][0]["ok"])

    def test_rows_report_their_time_and_may_run_in_parallel(self):
        """Amendment to spec 007: every row records `secs`; `Jobs: N` / AIDD_VERIFY_JOBS runs independent rows
        concurrently, the results keep the table order, and the slowest row is named."""
        tmp, root, d = self.vproject([("python src/check.py", "exit 0"),
                                      ("python src/check.py", "contains: assertions passed")])
        with tmp, mock.patch.dict(os.environ, {"AIDD_VERIFY_JOBS": "2"}):
            r = run_script("verify", "F23-eDoc-POS", cwd=root)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("2 in parallel", r.stdout)
            self.assertIn("slowest row:", r.stdout)
            run = ev.latest_verify_run(root, "F23-eDoc-POS")
            self.assertEqual([x["n"] for x in run["results"]], ["1", "2"])
            self.assertTrue(all("secs" in x for x in run["results"]))

    def test_timeout_kills_the_row(self):
        tmp, root, d = self.vproject([("python src/sleep.py", "exit 0")])
        with tmp, mock.patch.dict(os.environ, {"AIDD_VERIFY_TIMEOUT": "2"}):
            t0 = time.time()
            r = run_script("verify", "F23-eDoc-POS", cwd=root)
            self.assertLess(time.time() - t0, 18)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("timeout after 2 s", r.stdout)
            run = ev.latest_verify_run(root, "F23-eDoc-POS")
            self.assertEqual(run["results"][0]["exit"], -1)
            self.assertIn("timeout", (d / "evidence" / "verify-1.txt").read_text(encoding="utf-8"))

    def test_unstable_tree_fails_and_a_rerun_passes(self):
        tmp, root, d = self.vproject([("python src/gen.py", "exit 0")])
        with tmp:
            r = run_script("verify", "F23-eDoc-POS", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("rewrote files: src/gen_out.txt", r.stdout)
            run = ev.latest_verify_run(root, "F23-eDoc-POS")
            self.assertFalse(run["stable"])
            self.assertNotEqual(run["fingerprint_start"], run["fingerprint_end"])
            r = run_script("verify", "F23-eDoc-POS", cwd=root)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertTrue(ev.latest_verify_run(root, "F23-eDoc-POS")["stable"])

    def test_lint_problem_row_is_not_run_and_no_table_is_refused(self):
        tmp, root, d = self.vproject([('python -c "open(\'src/x\',\'w\')"', "exit 0")])
        with tmp:
            r = run_script("verify", "F23-eDoc-POS", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("not run", r.stdout)
            self.assertFalse((root / "src" / "x").exists())
        tmp, root, d = self.vproject([])
        with tmp:
            r = run_script("verify", "F23-eDoc-POS", cwd=root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIsNone(ev.latest_verify_run(root, "F23-eDoc-POS"))
            self.assertFalse((d / "evidence").exists())


class TestGate2Close(Spec007Base):
    """FR-205 / FR-206 / AC-208 / AC-209 / AC-210: a `gate: 2` spec closes only on executed, fresh evidence."""

    def gate2(self, sid="F23-eDoc-POS"):
        tmp, root, d = self.project(sid)
        self.answer(root, self.aq(d), "Approve")
        r = self.approve_rc(root, d)
        self.assertEqual(r.returncode, 0, r.stdout)
        backdate(d / "tasks.md", 50)
        tick()
        ev.append(root, "s1", "code_edit", path="src/billing.py", target=sid)
        return tmp, root, d

    def verify(self, root, sid):
        r = run_script("verify", sid, cwd=root)
        self.assertEqual(r.returncode, 0, r.stdout)
        return ev.latest_verify_run(root, sid)

    def closing_auditor(self, root, d, run, chars=4000, tid="toolu_closing01"):
        h8 = aidd_rules.approval_hash((d / "tasks.md").read_text(encoding="utf-8"))[:8]
        tick()
        ev.append(root, "s1", "subagent", type="general-purpose", model="sonnet", tool_use_id=tid,
                  desc="closing audit", result_chars=chars,
                  head=f"CLOSING AUDIT [domains: functional, security] [tasks:{h8}] "
                       f"[verify:{run['verify_hash'][:8]}]\nAudit the spec.")

    def qa(self, d, tid="toolu_closing01"):
        (d / "qa-audit.md").write_text("# qa\n\n| Domain | Result | Auditor |\n|---|---|---|\n"
                                       f"| functional | ok | {tid} |\n| security | ok | {tid} |\n",
                                       encoding="utf-8")

    def close(self, root, sid, answer=True):
        if answer:
            self.answer(root, f"Close this spec? [spec:{sid}]", "Yes, close")
        return run_script("rules", "close", sid, cwd=root)

    def test_refused_without_verify_run(self):
        tmp, root, d = self.gate2()
        with tmp:
            for dom in ("functional", "security"):
                tick()
                ev.append(root, "s1", "subagent", type="x", desc=f"{dom} auditor", head="best practice")
            self.qa(d)
            r = self.close(root, "F23-eDoc-POS")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("No verify_run recorded", r.stdout)
            self.assertEqual(ev.open_specs(root), ["F23-eDoc-POS"])

    def test_closes_with_a_fresh_verify_run_and_one_closing_auditor(self):
        for sid in IDS:
            with self.subTest(sid):
                tmp, root, d = self.gate2(sid)
                with tmp:
                    run = self.verify(root, sid)
                    self.closing_auditor(root, d, run)
                    self.qa(d)
                    r = self.close(root, sid)
                    self.assertEqual(r.returncode, 0, r.stdout)
                    self.assertIn("closed as completed", r.stdout)
                    self.assertEqual(ev.open_specs(root, include_approved=True), [])

    def test_code_edit_after_verify_is_stale(self):
        tmp, root, d = self.gate2()
        with tmp:
            run = self.verify(root, "F23-eDoc-POS")
            tick()
            ev.append(root, "s1", "code_edit", path="src/billing.py", target="F23-eDoc-POS")
            self.closing_auditor(root, d, run)
            self.qa(d)
            r = self.close(root, "F23-eDoc-POS")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("code edit happened after the last verify_run", r.stdout)

    def test_closing_auditor_older_than_verify_or_short_report_is_refused(self):
        tmp, root, d = self.gate2()
        with tmp:
            run = self.verify(root, "F23-eDoc-POS")
            self.closing_auditor(root, d, run, chars=200)               # report too short
            self.qa(d)
            r = self.close(root, "F23-eDoc-POS")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("CLOSING AUDIT [domains: functional, security]", r.stdout)
            self.closing_auditor(root, d, run)
            tick()
            (root / "billing_changed.py").write_text("x = 1\n", encoding="utf-8")   # the CODE changes
            self.verify(root, "F23-eDoc-POS")                           # a newer run on new code: the auditor is older
            r = self.close(root, "F23-eDoc-POS", answer=False)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("R7", r.stdout)

    def test_docs_edit_and_reverify_of_same_code_keep_verification_and_auditor(self):
        """Amendment to spec 007: a management error (docs edited, re-verify of identical code) never forces
        a re-execution nor a new auditor."""
        tmp, root, d = self.gate2()
        with tmp:
            run = self.verify(root, "F23-eDoc-POS")
            self.closing_auditor(root, d, run)
            self.qa(d)
            tick()
            (root / "NOTES.md").write_text("management notes edited after verify\n", encoding="utf-8")
            st = aidd_rules.verification_state(d, root)
            self.assertEqual(st["status"], "passed", st)                # a doc edit is not a code change
            run2 = self.verify(root, "F23-eDoc-POS")                    # re-verify: rows are REUSED, same code
            self.assertTrue(all(r.get("reused") for r in run2["results"]), run2["results"])
            self.assertEqual(run2["code_since"], run["started"])
            self.assertIn(run["verify_hash"], run2["verify_lineage"])
            r = self.close(root, "F23-eDoc-POS")
            self.assertEqual(r.returncode, 0, r.stdout)

    def test_qa_audit_must_cite_the_closing_auditor(self):
        tmp, root, d = self.gate2()
        with tmp:
            run = self.verify(root, "F23-eDoc-POS")
            self.closing_auditor(root, d, run)
            self.qa(d, tid="someone-else")
            r = self.close(root, "F23-eDoc-POS")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("tool_use_id", r.stdout)

    def test_evidence_edited_after_the_run_is_refused(self):
        tmp, root, d = self.gate2()
        with tmp:
            run = self.verify(root, "F23-eDoc-POS")
            f = d / "evidence" / "verify-1.txt"
            f.write_text(f.read_text(encoding="utf-8") + "forged\n", encoding="utf-8")
            self.closing_auditor(root, d, run)
            self.qa(d)
            r = self.close(root, "F23-eDoc-POS")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("sha1", r.stdout)

    def test_legacy_approved_spec_closes_on_the_old_path(self):
        tmp, root, d = make_project(name="006-aidd-phased-audits-attribution", spec=spec_with_rows([]))
        with tmp:
            self.approve_legacy(root, d, spec="006-aidd-phased-audits-attribution")
            tick()
            ev.append(root, "s1", "code_edit", path="src/a.py")
            for dom in ("functional", "security"):
                tick()
                ev.append(root, "s1", "subagent", type="x", desc=f"{dom} auditor", head="best practice")
            (d / "qa-audit.md").write_text("# qa\n", encoding="utf-8")
            r = self.close(root, "006-aidd-phased-audits-attribution")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertNotIn("verify", r.stdout.lower())


class TestStatus007(Spec007Base):
    """FR-208 / AC-212 / AC-214: honest status, `--refresh`, effective AIDD_RULES."""

    def test_default_output_adds_only_the_pointer_line_for_a_legacy_spec(self):
        tmp, root, d = make_project(spec=spec_with_rows([]))
        with tmp:
            self.spec_edit(root)
            out = run_script("status", cwd=root).stdout
            self.assertIn("gate pointer: none", out)
            for absent in ("Review:", "Verification:", "AIDD_RULES=", "warn overrides", "Refresh"):
                self.assertNotIn(absent, out)

    def test_new_style_spec_shows_review_verification_and_attributed_edits(self):
        tmp, root, d = self.project("F23-eDoc-POS")
        with tmp:
            self.answer(root, self.aq(d), "Approve")
            self.assertEqual(self.approve_rc(root, d).returncode, 0)
            for target in ("F23-eDoc-POS", "F23-eDoc-POS", "F21-other", ""):
                tick()
                ev.append(root, "s1", "code_edit", path="src/x.py", target=target)
            st = aidd_status.build_status(d, root)
            self.assertEqual(st["code_edits_attributed"], 2)
            self.assertEqual(st["gate"], 2)
            self.assertEqual(st["verification"]["status"], "never-run")
            self.assertEqual(st["gate_pointer"], "F23-eDoc-POS")
            out = run_script("status", str(d), cwd=root).stdout
            self.assertIn("Review: no page · Verification: never-run (1 command(s)) · gate 2", out)
            self.assertIn("2 code edit(s) attributed since approval", out)

    def test_effective_rules_mode_and_override_count(self):
        tmp, root, d = self.project()
        with tmp:
            with mock.patch.dict(os.environ, {"AIDD_RULES": "off"}):
                self.assertIn("AIDD_RULES=off (rules disabled)", run_script("status", cwd=root).stdout)
            tick()
            ev.append(root, "s1", "rules_override", hook="rule_gate", mode="warn")
            ev.append(root, "s1", "rules_override", hook="stop_gate", mode="warn")
            with mock.patch.dict(os.environ, {"AIDD_RULES": "warn"}):
                out = run_script("status", cwd=root).stdout
                self.assertIn("AIDD_RULES=warn", out)
                self.assertIn("warn overrides: 2", out)
                j = json.loads(run_script("status", "--json", cwd=root).stdout)
                self.assertEqual(j["evidence"]["rules_mode"]["mode"], "warn")
                self.assertEqual(j["evidence"]["overrides"], 2)

    def test_refresh_without_git_is_unavailable_and_exit_zero(self):
        tmp, root, d = self.project("F23-eDoc-POS")
        with tmp:
            r = run_script("status", "--refresh", cwd=root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("git: unavailable", r.stdout)
            self.assertIn("1 pending", r.stdout)
            self.assertIn("F23-eDoc-POS: approval pending", r.stdout)
            self.assertIn("AIDD_RULES=enforce", r.stdout)
            with mock.patch.object(aidd_status.subprocess, "run", side_effect=FileNotFoundError("git")):
                self.assertIsNone(aidd_status._git(root, "status"))
                self.assertEqual(aidd_status._derived_facts(root)["git"], {"available": False})
            r = run_script("status", "--json", "--refresh", cwd=root)
            self.assertEqual(json.loads(r.stdout)["derived"]["git"], {"available": False})
            self.assertNotIn("derived", json.loads(run_script("status", "--json", cwd=root).stdout))

    @unittest.skipUnless(shutil.which("git"), "git not on PATH")
    def test_refresh_in_a_git_repo(self):
        tmp, root, d = self.project("F23-eDoc-POS")
        with tmp:
            def git(*a):
                subprocess.run(["git", *a], cwd=str(root), capture_output=True, check=True)
            git("init", "-q")
            git("config", "user.email", "t@example.com")
            git("config", "user.name", "t")
            git("add", "src")
            git("commit", "-q", "-m", "first commit")
            (root / "src" / "billing.py").write_text("x = 2\n", encoding="utf-8")         # dirty
            (root / "prototype").mkdir()
            (root / "prototype" / "screen.html").write_text("<p>", encoding="utf-8")     # untracked prototype
            r = run_script("status", "--refresh", cwd=root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("first commit", r.stdout)
            self.assertIn("1 dirty", r.stdout)
            self.assertIn("untracked under specs/F23-eDoc-POS/: plan.md, spec.md, tasks.md", r.stdout)
            self.assertIn("untracked prototype files: prototype/screen.html", r.stdout)
            der = json.loads(run_script("status", str(d), "--json", "--refresh", cwd=root).stdout)["derived"]
            self.assertTrue(der["git"]["available"])
            self.assertEqual(der["git"]["dirty"], 1)
            self.assertEqual(sorted(der["git"]["untracked_specs"]["F23-eDoc-POS"]), ["plan.md", "spec.md", "tasks.md"])
            self.assertEqual(der["specs"][0]["spec"], "F23-eDoc-POS")


class TestStatusFingerprintOnce(Spec007Base):
    """Closing-audit F-2: `aidd status` (plain, --json, --refresh, a named spec) computes the worktree
    fingerprint ONCE per run, not once per spec (and not twice per spec with --refresh)."""

    def two_verified_specs(self):
        tmp, root, d1 = self.project(IDS[0])
        d2 = add_spec(root, IDS[1])
        (d2 / "plan.md").write_text(PLAN_MD, encoding="utf-8")
        self.spec_edit(root, spec=IDS[1], file="tasks.md")
        for d in (d1, d2):
            body = b"# python src/check.py | exit 0 | t\ncheck ok: billing totals verified, 3 assertions passed\n"
            (d / "evidence").mkdir()
            (d / "evidence" / "verify-1.txt").write_bytes(body)
            vh = aidd_rules.verification_hash((d / "spec.md").read_text(encoding="utf-8"))
            res = [{"n": "1", "cmd": "python src/check.py", "exit": 0, "ok": True,
                    "evidence": "evidence/verify-1.txt", "sha1": hashlib.sha1(body).hexdigest()}]
            tick()
            self.assertTrue(ev.append_verify_run(root, "s1", d.name, True, vh, res, time.time() - 1,
                                                 "fp-now", "fp-now", True))
        return tmp, root, d1, d2

    def status(self, args):
        calls = []

        def fp(root, *a, **k):
            calls.append(str(root))
            return "fp-now"

        buf = io.StringIO()
        with mock.patch.object(ev, "worktree_fingerprint", side_effect=fp), contextlib.redirect_stdout(buf):
            rc = aidd_status.cmd_status(list(args))
        self.assertEqual(rc, 0)
        return calls, buf.getvalue()

    def in_root(self, root):
        old = os.getcwd()
        os.chdir(root)
        return old

    def test_one_fingerprint_per_status_run(self):
        tmp, root, d1, d2 = self.two_verified_specs()
        with tmp:
            old = self.in_root(root)                  # no positional: cmd_status finds the root from cwd
            try:
                for args in ([], ["--refresh"], ["--json"], ["--json", "--refresh"],
                             [str(d1), "--refresh"], [f"specs/{IDS[1]}", "--refresh"],
                             [str(d2), "--json", "--refresh"], [f"specs/{IDS[0]}"]):
                    with self.subTest(args=args):
                        calls, out = self.status(args)
                        self.assertEqual(len(calls), 1, (calls, out[-400:]))
                # both specs are really compared against that one fingerprint (and pass)
                _calls, out = self.status(["--json", "--refresh"])
                data = json.loads(out)
                self.assertEqual({s["spec"]: s["verification"]["status"] for s in data["specs"]},
                                 {IDS[0]: "passed", IDS[1]: "passed"})
                self.assertEqual({s["spec"]: s["verification"]["status"] for s in data["derived"]["specs"]},
                                 {IDS[0]: "passed", IDS[1]: "passed"})
            finally:
                os.chdir(old)

    def test_a_changed_tree_is_still_stale_with_the_shared_fingerprint(self):
        tmp, root, d1, d2 = self.two_verified_specs()
        with tmp:
            old = self.in_root(root)
            try:
                with mock.patch.object(ev, "worktree_fingerprint", return_value="fp-changed") as m:
                    buf = io.StringIO()
                    with contextlib.redirect_stdout(buf):
                        aidd_status.cmd_status(["--json", "--refresh"])
                    data = json.loads(buf.getvalue())
                    self.assertEqual({s["verification"]["status"] for s in data["specs"]}, {"stale"})
                    self.assertEqual(m.call_count, 1)
            finally:
                os.chdir(old)


if __name__ == "__main__":
    unittest.main()
