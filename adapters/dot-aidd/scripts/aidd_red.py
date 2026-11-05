#!/usr/bin/env python3
"""aidd_red.py - RED receipt for a test task (stdlib).  aidd: amendment 09 B5 / FR-297 (E10 (d))

Usage:
  aidd red <test-cmd...> --task T-nn [--spec <id|dir>] [--timeout S]
      Runs the test command from the project root. It MUST fail (exit != 0): then it writes the receipt
      `specs/<id>/evidence/red-T-nn.txt` (command, exit code, first failing line, timestamp, sha1 of the
      test file) and exits 0. If the command passes it prints `NO-RED: el test pasó, no hay RED`, writes
      nothing and exits 1. `--task`/`--spec`/`--timeout` may stand anywhere; use `--` to pass the
      command verbatim (`aidd red --task T-01 -- python -m pytest -x tests/t.py`).
  aidd red --check <id|dir>
      Lists the receipts present (and whether the test file changed since) and every task with
      `Agent role: tests` that has no receipt (`MISSING: T-nn`; exit 1). A task block with a line
      `RED: exempt (<reason>)` (pure refactor with an existing test) is listed as EXEMPT.

The receipt is written by this CLI process, the only writer of evidence/ under rule R9 (the same way
`aidd verify` writes evidence/verify-*.txt). Exit: 0 ok, 1 no RED / missing receipts, 2 usage error.
"""
import datetime
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import aidd_evidence as ev
except Exception:  # pragma: no cover
    ev = None

FAIL_RE = re.compile(r"(AssertionError|FAILED|FAIL\b|Error\b|Exception|not ok|✗|✘|Cannot find|panicked|expected)", re.I)
TASK_RE = re.compile(r"^T-\d+$")


def _root():
    if ev is not None:
        return ev.find_root()
    cur = Path.cwd().resolve()
    for d in [cur] + list(cur.parents):
        if (d / "specs").is_dir() or (d / ".aidd").is_dir():
            return d
    return cur


def resolve_spec(root, spec_arg):
    """-> spec dir Path or None. `spec_arg` is an id, a path, or None (active spec, else the only spec)."""
    if spec_arg:
        for cand in (Path(spec_arg), root / spec_arg, root / "specs" / spec_arg):
            if (cand / "spec.md").is_file():
                return cand.resolve()
        return None
    active = ev.get_active_spec(root) if ev is not None else None
    if active and (root / "specs" / active / "spec.md").is_file():
        return (root / "specs" / active).resolve()
    dirs = [p.parent for p in (root / "specs").glob("*/spec.md")] if (root / "specs").is_dir() else []
    return dirs[0].resolve() if len(dirs) == 1 else None


def split_args(argv):
    """-> (cmd list, task, spec, timeout, error). Flags may stand anywhere unless a `--` fixes the command."""
    task = spec = timeout = None
    cmd = []
    rest = list(argv)
    tail = []
    if "--" in rest:
        i = rest.index("--")
        rest, tail = rest[:i], rest[i + 1:]
    i = 0
    while i < len(rest):
        a = rest[i]
        if a in ("--task", "--spec", "--timeout") and i + 1 < len(rest):
            v = rest[i + 1]
            if a == "--task":
                task = v
            elif a == "--spec":
                spec = v
            else:
                timeout = v
            i += 2
            continue
        m = re.match(r"^(--task|--spec|--timeout)=(.*)$", a)
        if m and not tail:
            k, v = m.groups()
            if k == "--task":
                task = v
            elif k == "--spec":
                spec = v
            else:
                timeout = v
            i += 1
            continue
        cmd.append(a)
        i += 1
    cmd += tail
    return cmd, task, spec, timeout


def find_test_file(root, cmd, spec_dir, task):
    """Relative path of the test file: first command argument naming an existing file (pytest `::node`
    stripped), else the Target file of the task in tasks.md, else ''."""
    for a in cmd[1:] if len(cmd) > 1 else cmd:
        base = a.split("::", 1)[0]
        if not base or base.startswith("-"):
            continue
        p = (root / base)
        if p.is_file() and not base.endswith(".exe"):
            return base.replace("\\", "/")
    tgt = task_targets(spec_dir).get(task) if spec_dir else None
    return tgt or ""


def task_targets(spec_dir):
    """{T-nn: first backticked path of its table row (3rd column)}."""
    try:
        t = (Path(spec_dir) / "tasks.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    out = {}
    for line in t.splitlines():
        m = re.match(r"^\|\s*(T-\d+)\s*\|", line)
        if m:
            cols = [c.strip() for c in line.split("|")]
            if len(cols) > 3:
                p = re.search(r"`([^`]+)`", cols[3])
                if p:
                    out[m.group(1)] = p.group(1)
    return out


def task_roles(spec_dir):
    """{T-nn: {'role': str, 'exempt': bool}} from the `### T-nn` blocks of tasks.md."""
    try:
        t = (Path(spec_dir) / "tasks.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    out = {}
    blocks = re.split(r"^#{2,4}\s+(?=T-\d+)", t, flags=re.M)[1:]
    for b in blocks:
        m = re.match(r"(T-\d+)", b)
        if not m:
            continue
        r = re.search(r"Agent role:\s*([A-Za-z]+)", b)
        out[m.group(1)] = {"role": (r.group(1).lower() if r else ""),
                           "exempt": bool(re.search(r"^[ \t>*-]*RED:\s*exempt\b", b, re.I | re.M))}
    return out


def first_failure(output):
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    for ln in lines:
        if FAIL_RE.search(ln) and not ln.startswith("Traceback"):
            return ln[:300]
    return lines[0][:300] if lines else "(no output)"


def sha1_of(path):
    try:
        return hashlib.sha1(Path(path).read_bytes()).hexdigest()
    except OSError:
        return ""


def cmd_run(argv):
    cmd, task, spec_arg, timeout = split_args(argv)
    if not cmd or not task or not TASK_RE.match(task):
        print("Usage: aidd red <test-cmd...> --task T-nn [--spec <id>]   |   aidd red --check <spec>", file=sys.stderr)
        return 2
    root = _root()
    spec_dir = resolve_spec(root, spec_arg)
    if spec_dir is None:
        print("ERROR: spec not found or ambiguous: pass --spec <id>", file=sys.stderr)
        return 2
    try:
        tmo = float(timeout or os.environ.get("AIDD_RED_TIMEOUT") or 600)
    except ValueError:
        print("ERROR: invalid --timeout", file=sys.stderr)
        return 2
    started = datetime.datetime.now().isoformat(timespec="seconds")
    try:
        if len(cmd) == 1:
            res = subprocess.run(cmd[0], shell=True, cwd=str(root), capture_output=True, timeout=tmo)
        else:
            res = subprocess.run(cmd, cwd=str(root), capture_output=True, timeout=tmo)
    except subprocess.TimeoutExpired:
        print(f"ERROR: the test command exceeded {tmo:g}s; no receipt written", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"ERROR: cannot run the command ({type(e).__name__}: {e}); no receipt written", file=sys.stderr)
        return 2
    code = res.returncode
    output = (res.stdout + b"\n" + res.stderr).decode("utf-8", errors="replace").replace("\r\n", "\n")
    if code == 0:
        print("NO-RED: el test pasó, no hay RED")
        return 1
    test_file = find_test_file(root, cmd, spec_dir, task)
    sha = sha1_of(root / test_file) if test_file else ""
    command = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    body = [f"# RED {task} | exit {code} | {started}",
            f"command: {command}",
            f"exit: {code}",
            f"first_failure: {first_failure(output)}",
            f"timestamp: {started}",
            f"test_file: {test_file or '(unknown)'}",
            f"test_file_sha1: {sha or '(none)'}",
            "--- output (first 60 lines) ---"]
    body += output.strip("\n").split("\n")[:60]
    evid = spec_dir / "evidence"
    try:
        evid.mkdir(parents=True, exist_ok=True)
        (evid / f"red-{task}.txt").write_text("\n".join(body) + "\n", encoding="utf-8")
    except OSError as e:
        print(f"ERROR: cannot write the receipt ({type(e).__name__})", file=sys.stderr)
        return 2
    print(f"RED receipt: {spec_dir.name}/evidence/red-{task}.txt (exit {code}; {first_failure(output)})")
    return 0


def parse_receipt(path):
    out = {}
    try:
        for ln in Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[1:12]:
            m = re.match(r"^(\w+):\s*(.*)$", ln)
            if m:
                out[m.group(1)] = m.group(2)
    except OSError:
        pass
    return out


def cmd_check(argv):
    if len(argv) != 1:
        print("Usage: aidd red --check <spec>", file=sys.stderr)
        return 2
    root = _root()
    spec_dir = resolve_spec(root, argv[0])
    if spec_dir is None:
        print(f"ERROR: spec not found: {argv[0]}", file=sys.stderr)
        return 2
    roles = task_roles(spec_dir)
    targets = task_targets(spec_dir)
    evid = spec_dir / "evidence"
    receipts = {p.stem[4:]: p for p in sorted(evid.glob("red-T-*.txt"))} if evid.is_dir() else {}
    missing = 0
    for tid in sorted(set(roles) | set(receipts)):
        info = roles.get(tid, {})
        if tid in receipts:
            r = parse_receipt(receipts[tid])
            line = f"OK: {tid} evidence/{receipts[tid].name} (exit {r.get('exit', '?')})"
            tf = r.get("test_file", "")
            if tf and tf != "(unknown)" and r.get("test_file_sha1") not in (None, "(none)"):
                if sha1_of(root / tf) != r["test_file_sha1"]:
                    line += " - test file changed since the receipt"
            print(line)
        elif info.get("role") == "tests":
            if info.get("exempt"):
                print(f"EXEMPT: {tid} (declared RED: exempt)")
            else:
                missing += 1
                print(f"MISSING: {tid} role=tests target={targets.get(tid, '?')} has no evidence/red-{tid}.txt")
    print(f"RED check: {len(receipts)} receipt(s), {missing} test task(s) without receipt")
    return 1 if missing else 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if argv and argv[0] == "--check":
        return cmd_check(argv[1:])
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    return cmd_run(argv)


if __name__ == "__main__":
    sys.exit(main())
