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

_SCRIPT_DIRS = (str(HOOKS_DIR), str(REPO / "skill" / "scripts"))


_CODE_CACHE = {}


def _hook_code(script):
    """Compiled code of a hook script, cached by (path, mtime): runpy would recompile it on every call."""
    p = Path(script)
    key = (str(p), p.stat().st_mtime_ns)
    code = _CODE_CACHE.get(key)
    if code is None:
        code = _CODE_CACHE[key] = compile(p.read_text(encoding="utf-8"), str(p), "exec")
    return code


def run_script_inprocess(script, data, env, timeout=30):
    """Run a hook script like `python script < data` (exit code, stdout, stderr) WITHOUT a new interpreter.

    Starting Python costs ~180-300 ms here and the gate tests start it ~1000 times; running the script with
    runpy in this process takes a few ms. Each call is isolated the way a process is: a fresh environment, fresh
    stdin/stdout/stderr, and the AIDD modules re-imported (a snapshot of sys.modules/sys.path is restored after).
    A crash prints its traceback to stderr and returns 1, exactly like the interpreter. AIDD_TEST_SUBPROCESS=1
    (or the real thing needing it) falls back to a real subprocess, which is how to check the two agree."""
    if os.environ.get("AIDD_TEST_SUBPROCESS") == "1":
        return subprocess.run([sys.executable, str(script)], input=data, capture_output=True, timeout=timeout, env=env)
    import io
    import runpy
    import traceback

    saved_env, saved_path, saved_argv = dict(os.environ), list(sys.path), list(sys.argv)
    saved_io = (sys.stdin, sys.stdout, sys.stderr)
    saved_mods = {k: v for k, v in sys.modules.items()
                  if k in ("_common", "aidd_evidence", "aidd_rules", "aidd_status", "aidd_review", "aidd_graphs")
                  or str(getattr(v, "__file__", "") or "").startswith(_SCRIPT_DIRS)}
    out, err = io.BytesIO(), io.BytesIO()
    got_out = got_err = b""
    rc = 0
    try:
        os.environ.clear()
        os.environ.update(env)
        if os.environ.get("AIDD_TEST_FRESH") == "1":      # re-import the libraries on every call (slow, strictest)
            for k in saved_mods:
                sys.modules.pop(k, None)
        sys.argv = [str(script)]
        sys.stdin = io.TextIOWrapper(io.BytesIO(data or b""), encoding="utf-8")
        sys.stdout = io.TextIOWrapper(out, encoding="utf-8", write_through=True)
        sys.stderr = io.TextIOWrapper(err, encoding="utf-8", write_through=True)
        try:
            exec(_hook_code(script), {"__name__": "__main__", "__file__": str(script), "__builtins__": __builtins__})
        except SystemExit as ex:
            code = ex.code
            if code is None:
                rc = 0
            elif isinstance(code, int):
                rc = code
            else:
                sys.stderr.write(str(code) + "\n")
                rc = 1
        except BaseException:
            traceback.print_exc()
            rc = 1
        finally:
            for s in (sys.stdout, sys.stderr):
                try:
                    s.flush()
                except Exception:
                    pass
            got_out, got_err = out.getvalue(), err.getvalue()      # read before the wrappers are dropped (they close)
    finally:
        sys.stdin, sys.stdout, sys.stderr = saved_io
        sys.argv = saved_argv
        sys.path[:] = saved_path
        for k in [k for k, v in sys.modules.items()
                  if k not in saved_mods and str(getattr(v, "__file__", "") or "").startswith(_SCRIPT_DIRS)]:
            sys.modules.pop(k, None)
        sys.modules.update(saved_mods)
        os.environ.clear()
        os.environ.update(saved_env)
    return subprocess.CompletedProcess([str(script)], rc, got_out, got_err)


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


# aidd:FR-204 aidd:FR-205 spec 007: a NEW approval needs a valid `## Verification` (rules.check_verification).
# The row runs src/cart.py, which every Base project (and the d1b layout) creates, so the lint accepts it.
VERIFICATION = ("\n## Verification\n\n| # | Command | Expected | Covers |\n|---|---|---|---|\n"
                "| 1 | `python src/cart.py` | exit 0 | FR-001 |\n")


def verified_spec(**kw):
    """spec_text(...) plus a valid `## Verification` section."""
    kw["extra"] = kw.get("extra", "") + VERIFICATION
    return spec_text(**kw)


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
    """Valid tasks.md in the NEW format (FR-009: only an APPROVED legacy file is exempt)."""
    return f"""# Tasks — x

| Task | Codes |
|---|---|
| T-01 | {ids} |

### T-01
- Agent min: {a1}
- Human ref hours: 8
- Tokens (est): 60k
- Agent role: builder
- Model tier: medium

### T-02
- Agent min: {a2}
- Human ref hours: 4
- Tokens (est): 40k
- Agent role: tests
- Model tier: medium

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01 | builder | {w1} | 60 | 8 |
| 2 | T-02 | tests | {w2} | 40 | 4 |

Total agent time (critical path): {total} min
Total tokens (k): 100

{approved}
"""


def approved_tasks(**kw):
    t = tasks_text(**kw)
    return t.replace("Approved: PENDING", f"Approved: 2026-10-01 hash:{R.approval_hash(t)}")


def legacy_tasks_text(a1=30, a2=20, w1=30, w2=20, total=50, ids="COMP-001", approved="Approved: PENDING"):
    """Legacy (specs 001-004) 4-column tasks.md: no Tokens/role/tier. Exempt ONLY when approved (FR-009)."""
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


def approved_legacy_tasks(**kw):
    t = legacy_tasks_text(**kw)
    return t.replace("Approved: PENDING", f"Approved: 2026-10-01 hash:{R.approval_hash(t)}")


def new_tasks(t1=60, t2=40, wt1=None, wt2=None, total_tokens=None, roles1="builder", roles2="tests",
              role1="builder", role2="tests", tier1="medium", tier2="medium", extra_t1="",
              approved="Approved: PENDING", a1=30, a2=20, total=50):
    """Valid NEW-header (6 columns, tokens + roles) tasks.md: 2 tasks, 2 waves."""
    wt1 = t1 if wt1 is None else wt1
    wt2 = t2 if wt2 is None else wt2
    total_tokens = (t1 + t2) if total_tokens is None else total_tokens
    return f"""# Tasks — x

| Task | Codes |
|---|---|
| T-01 | COMP-001 |

### T-01
- Agent min: {a1}
- Human ref hours: 1.5
- Tokens (est): {t1}k
{('- Agent role: ' + role1 + chr(10)) if role1 else ''}- Model tier: {tier1}
{extra_t1}
### T-02
- Agent min: {a2}
- Human ref hours: 1
- Tokens (est): {t2}k
- Agent role: {role2}
- Model tier: {tier2}

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-01 | {roles1} | {a1} | {wt1} | 1.5 |
| 2 | T-02 | {roles2} | {a2} | {wt2} | 1 |

Total agent time (critical path): {total} min
Total tokens (k): {total_tokens}

{approved}
"""


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
        self.env["AIDD_R7_FIX_EDITS"] = "0"       # strict R7 by default; tolerance tests override it
        self.env["AIDD_R5_FIX_EDITS"] = "0"       # strict R5 by default; AC-010 tests override it
        self.env["AIDD_R5_AUDIT"] = "strict"      # spec 007 FR-206: the old R5 tests keep their meaning (default is advisory)
        self._old_r5 = os.environ.get("AIDD_R5_AUDIT")
        os.environ["AIDD_R5_AUDIT"] = "strict"    # same for the in-process decide() calls

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
        if self._old_r5 is None:
            os.environ.pop("AIDD_R5_AUDIT", None)
        else:
            os.environ["AIDD_R5_AUDIT"] = self._old_r5
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
        r = run_script_inprocess(HOOKS_DIR / name, data, e)
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
