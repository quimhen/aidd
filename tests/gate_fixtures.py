"""Shared fixtures for the gate tests (test_rule_gate.py, test_stop_gate.py). Not a test module."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO / "skill" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(REPO / "skill" / "scripts"))

import _common  # noqa: E402
import aidd_evidence as EV  # noqa: E402
import aidd_rules as R  # noqa: E402

QUOTE = "no hace falta el flowmap"          # 5 words (M3: a prompt quote needs >= 5 words)
CHECKLIST_QUOTE = "es el modulo de checkout"  # 5 words
SID = "s-test"


def route(overrides=None):
    rows = {s: ("run", "", "") for s in R.ROUTE_STEPS}
    rows.update(overrides or {})
    body = "\n".join(f"| {s} | {a} | {b} | {c} |" for s, (a, b, c) in rows.items())
    return f"## Pipeline route\n\n| Step | Status | Reason | Confirmation |\n|---|---|---|---|\n{body}\n"


def _checklist_ok():
    """Every question of the shipped template (D6), answered; row 1 quotes the user, row 2 cites a real file."""
    rows = []
    for i, q in enumerate(R.REQUIRED_QUESTIONS):
        q = q.replace("|", "\\|")
        if i == 1:
            rows.append(f"| {q} | Modification | repo — src/cart.py:12 | ask |")
        else:
            rows.append(f'| {q} | Checkout | user — "es el modulo de checkout" | ask |')
    head = "## Minimum Requirements Checklist\n\n| Question | Answer | Source | If unanswered |\n|---|---|---|---|\n"
    return head + "\n".join(rows) + "\n"


CHECKLIST_OK = _checklist_ok()

CHECKLIST_PROPOSED = CHECKLIST_OK + '| Objective | Faster pay | [Proposed — unconfirmed] | ask |\n'
CHECKLIST_FABRICATED = CHECKLIST_OK.replace("es el modulo de checkout", "el usuario dijo algo que nunca dijo")
CHECKLIST_BLANK = CHECKLIST_OK + '| Who signs off? |  |  | ask |\n'
CHECKLIST_FAKE_REPO = CHECKLIST_OK.replace("repo — src/cart.py:12", "repo — nope.py")
CHECKLIST_SHORT_QUOTE = CHECKLIST_OK.replace("es el modulo de checkout", "modulo de checkout")  # 3 words


def spec_text(checklist=CHECKLIST_OK, route_overrides=None, extra=""):
    return f"# Spec — x\n\n{checklist}\n{route(route_overrides)}\n{extra}"


DEBT_OPEN = """
## Visual debt

| Codes | Blocks spec | Status | Mockup source |
|---|---|---|---|
| SCREEN-001 | 001-x | open | |
"""
DEBT_RESOLVED = DEBT_OPEN.replace("| open | |", "| resolved | mockups/login.html |")
WAIVED_VISUAL = {s: ("waived", "backend only", f'user — "{QUOTE}"') for s in ("0", "1", "1.5")}
MOCKUP_AUDIT = "# Mockup audit\n\n| Code | Screen |\n|---|---|\n| SCREEN-001 | Login |\n"


def debt_spec(debt=DEBT_OPEN):
    return spec_text(route_overrides=WAIVED_VISUAL, extra="Uses SCREEN-001.\n" + debt)


def tasks_text(a1=30, a2=20, w1=30, w2=20, total=50, ids="COMP-001", approved="Approved: PENDING"):
    return f"""# Tasks — x

| Task | Codes |
|---|---|
| T-01 | {ids} |

### T-01
- Agent min: {a1}
- Human ref hours: 8

### T-02
- Agent min: {a2}
- Human ref hours: 4

## Waves

| Wave | Tasks | Agent time (min) | Human ref (h) |
|---|---|---|---|
| 1 | T-01 | {w1} | 8 |
| 2 | T-02 | {w2} | 4 |

Total agent time (critical path): {total} min

{approved}
"""


def approved_tasks(**kw):
    t = tasks_text(**kw)
    return t.replace("Approved: PENDING", f"Approved: 2026-10-01 hash:{R.approval_hash(t)}")


QA_LEDGER = "## Mapping ledger\n\n| Code | Status |\n|---|---|\n| SCREEN-01 | ✅ DONE |\n"
QA_EVIDENCE_HEAD = "## Execution evidence\n\n| Code | Kind | Evidence | Verified by |\n|---|---|---|---|\n"


def qa_text(evidence_rows="", ledger=QA_LEDGER, extra=""):
    """qa-audit.md body: a ✅ SCREEN-01 ledger row plus an `Execution evidence` table with `evidence_rows`
    (empty string => no evidence table at all, i.e. an R10 violation)."""
    head = QA_EVIDENCE_HEAD + evidence_rows if evidence_rows else ""
    return f"# QA audit\n\n{ledger}\n{head}\n{extra}"


QA_ROW_OK = "| SCREEN-01 | screenshot | evidence/login.png | agent |\n"
QA_BUGS_REPEAT_BLANK = (
    "## Bug reports\n\n| # | Code | Symptom | Root cause | Fix | Pattern sweep |\n|---|---|---|---|---|---|\n"
    "| 1 | SCREEN-01 | N/D card | | patched | |\n"
    "| 2 | SCREEN-01 | N/D again | | patched | |\n")


class Base(unittest.TestCase):
    """Synthetic project dir (specs/001-x/…, a real src/cart.py) + helpers to build evidence and run a hook.
    Every test runs with AIDD_EVIDENCE_DIR pointing at a scratch dir OUTSIDE the project (and outside the
    repo), so no test ever writes `.aidd/evidence` anywhere real."""

    SPEC = "001-x"

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name).resolve()
        self.evdir = self.root.parent / (self.root.name + "-evd")
        self.evdir.mkdir(exist_ok=True)
        self._old_evdir = os.environ.get("AIDD_EVIDENCE_DIR")
        self._old_testing = os.environ.get("AIDD_TESTING")
        os.environ["AIDD_EVIDENCE_DIR"] = str(self.evdir)
        os.environ["AIDD_TESTING"] = "1"          # Rev 2 (D4): AIDD_EVIDENCE_DIR is honoured only with this
        self.session = f"{SID}-{uuid.uuid4().hex[:8]}"
        self.sd = self.root / "specs" / self.SPEC
        self.sd.mkdir(parents=True)
        (self.root / "src").mkdir()
        (self.root / "src" / "cart.py").write_text("".join(f"x{i} = {i}\n" for i in range(40)),
                                                          encoding="utf-8")
        self.env = {k: v for k, v in os.environ.items() if k != "AIDD_RULES"}
        self.env["AIDD_EVIDENCE_DIR"] = str(self.evdir)
        self.env["AIDD_TESTING"] = "1"

    def tearDown(self):
        _common.marker_path(self.session).unlink(missing_ok=True)
        _common.timestamps_path(self.session).unlink(missing_ok=True)
        if self._old_evdir is None:
            os.environ.pop("AIDD_EVIDENCE_DIR", None)
        else:
            os.environ["AIDD_EVIDENCE_DIR"] = self._old_evdir
        if self._old_testing is None:
            os.environ.pop("AIDD_TESTING", None)
        else:
            os.environ["AIDD_TESTING"] = self._old_testing
        shutil.rmtree(self.evdir, ignore_errors=True)
        self._td.cleanup()

    # -- fixtures ---------------------------------------------------------
    def put(self, rel, text, age=100.0):
        """Write a file whose mtime is `age` seconds in the past (negative = future)."""
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
        t = time.time() - age
        os.utime(p, (t, t))
        return p

    def ev(self, kind, **detail):
        time.sleep(0.012)
        EV.append(self.root, self.session, kind, **detail)
        time.sleep(0.012)

    def prompt(self, text):
        self.ev("prompt", text=text)

    def subagent(self, desc="Mapper", head="independent review"):
        self.ev("subagent", type="general-purpose", desc=desc, head=head)

    def spec_edit(self, file="spec.md", spec=None):
        self.ev("spec_edit", path=str(self.root / "specs" / (spec or self.SPEC) / file), spec=spec or self.SPEC,
                file=file)

    def open_spec(self, spec=None):
        """The recorder saw tasks.md of `spec` written => the spec is OPEN (until a spec_closed event)."""
        self.spec_edit("tasks.md", spec)

    def approve_spec(self, text=None, spec=None):
        """The recorder saw a hash-valid `Approved:` line written for `spec` (project event `approved`)."""
        t = text if text is not None else approved_tasks()
        time.sleep(0.012)
        EV.append_approved(self.root, self.session, spec or self.SPEC, R.approval_hash(t))   # N1: the only minting API
        time.sleep(0.012)

    def close_spec(self, spec=None, reason="abandoned"):
        self.ev("spec_closed", spec=spec or self.SPEC, reason=reason)

    @staticmethod
    def tag(text=None):
        """N4: the tag every approval question must carry: [tasks:<first 8 hex of approval_hash(tasks.md)>]."""
        return "[tasks:%s]" % R.approval_hash(text if text is not None else tasks_text())[:8]

    def answer(self, question, chosen, session=None, options=None, tagged=None, tasks=None):
        """A user answer as the recorder stores it: `pairs` anchored on the question, plus the option labels the
        question OFFERED (default: the chosen label and a 'Something else' one)."""
        time.sleep(0.012)
        if tagged is None:       # approval questions are tagged by default (pass tagged=False for a decoy)
            tagged = "approv" in question.lower() or "aprob" in question.lower()
        if tagged:
            question = f"{question} {self.tag(tasks)}"
        opts = [list(options) if options is not None else [chosen, "Something else"]]
        EV.append_answer(self.root, session or self.session, f'"{question}"="{chosen}"', [[question, chosen]],
                         options=opts)
        time.sleep(0.012)

    def make_mockup(self):
        self.put("mockups/login.html", "<html></html>")
        self.put("specs/001-x/mockup-audit.md", MOCKUP_AUDIT)

    def marker(self):
        _common.marker_path(self.session).write_text("invoked", encoding="utf-8")

    def events(self, kind=None):
        return EV.events(self.root, kind=kind)

    # -- running ----------------------------------------------------------
    def run_hook(self, name, event, env=None, raw=None):
        e = dict(self.env)
        for k, v in (env or {}).items():
            if v is None:
                e.pop(k, None)     # None = remove the variable from the child environment
            else:
                e[k] = v
        data = raw if raw is not None else json.dumps(event).encode("utf-8")
        r = subprocess.run([sys.executable, str(HOOKS_DIR / name)], input=data, capture_output=True,
                           timeout=30, env=e)
        r.out = r.stdout.decode("utf-8", "replace")
        r.err = r.stderr.decode("utf-8", "replace")
        return r

    def gate(self, path, tool="Write", env=None, **tool_input):
        p = path if os.path.isabs(str(path)) else str(self.root / path)
        key = "notebook_path" if tool == "NotebookEdit" else "file_path"
        ti = dict(tool_input, **{key: p})
        return self.run_hook("rule_gate.py", {"session_id": self.session, "cwd": str(self.root),
                                              "hook_event_name": "PreToolUse", "tool_name": tool,
                                              "tool_input": ti}, env=env)

    def bash(self, command, env=None, cwd=None):
        return self.run_hook("rule_gate.py", {"session_id": self.session, "cwd": str(cwd or self.root),
                                              "hook_event_name": "PreToolUse", "tool_name": "Bash",
                                              "tool_input": {"command": command}}, env=env)

    def assertBlocked(self, r, *needles):
        self.assertEqual(r.returncode, 2, f"expected a block, got rc={r.returncode} stderr={r.err!r}")
        self.assertNotIn("Traceback", r.err)
        self.assertTrue(r.err.strip())
        for n in needles:
            self.assertIn(n.lower(), r.err.lower(), r.err)

    def assertAllowed(self, r):
        self.assertEqual(r.returncode, 0, f"expected allow, got rc={r.returncode} stderr={r.err!r}")
        self.assertNotIn("Traceback", r.err)
        self.assertEqual(r.err.strip(), "", r.err)
