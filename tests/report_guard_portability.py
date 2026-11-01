"""Report old/current/desired guard decisions (spec 009 T-23).

All events point at synthetic fixtures. Windows drive and UNC strings are lexical probes;
this program never opens or connects to those paths.
"""
import json
import os
from pathlib import Path
import platform
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_fixtures import Base, tasks_text
from test_rule_gate_shell_speed import load_old_guard
import rule_gate


def collect_cases(root):
    root = Path(root)
    specs = root / "specs" / "001-x"
    probes = [
        ("ci-drive-tasks", "D:/proj/specs/F23-eDoc-POS/tasks.md", "deny", "Bash"),
        ("ci-drive-review", "D:/proj/specs/F23-eDoc-POS/review.md", "deny", "Bash"),
        ("ci-drive-backslash-review", r"D:\proj\specs\F23-eDoc-POS\review.md", "deny", "Bash"),
        ("drive-mixed-case", r"D:\proj\SpEcS\F23-eDoc-POS\REVIEW.MD.", "deny", "Bash"),
        ("unc-tasks", r"\\server\share\specs\F23-eDoc-POS\tasks.md", "deny", "Bash"),
        ("unc-extended-review", r"\\?\UNC\server\share\specs\F23-eDoc-POS\review.md", "deny", "Bash"),
        ("unc-aidd", r"\\server\share\.aidd\evidence\events.toon", "deny", "Bash"),
        ("native-protected", str(root / ".aidd" / "evidence" / "events.toon"), "deny", "Write"),
        ("native-unrelated", str(root / "docs" / "unrelated.md"), "allow", "Write"),
        ("ci-native-case-distinct", str(root / ".AIDD" / "Evidence" / "events.toon"),
         "deny" if os.name == "nt" else "allow", "Write"),
        ("ci-uppercase-plan", str(specs / "PLAN.md"), "deny" if os.name == "nt" else "allow", "Write"),
        ("ci-uppercase-tasks", str(specs / "TASKS.MD"), "deny" if os.name == "nt" else "allow", "Write"),
        ("ci-cmakelists", str(root / "src" / "CMakeLists.txt"), "deny", "Write"),
        ("ci-uppercase-markdown", str(root / "docs" / "A.MD"), "allow", "Write"),
        ("native-relative-parent", "src/../.aidd/evidence/events.toon", "deny", "Write"),
        ("native-stream", ".aidd/evidence/events.toon:stream", "deny", "Write"),
    ]
    cases = []
    for ident, path, desired, tool in probes:
        ti = ({"command": 'echo x > "' + path + '"'} if tool == "Bash"
              else {"file_path": path, "content": "x"})
        cases.append({"id": ident, "path": path, "desired": desired,
                      "event": {"cwd": str(root), "tool_name": tool, "tool_input": ti}})
    return cases


def compare_cases(old_guard, new_guard, cases):
    rows = []
    for case in cases:
        decisions = []
        for guard in (old_guard, new_guard):
            clear = getattr(guard, "_clear_caches", None)
            if clear:
                clear()
            decisions.append(guard.decide(case["event"]))
        row = {"os": platform.system(), "id": case["id"], "path": case["path"],
               "event": case["event"], "old": decisions[0], "current": decisions[1],
               "desired": case["desired"]}
        if "specs" in case["path"].lower():
            old_lex = getattr(old_guard, "_specs_tok", None)
            new_lex = getattr(new_guard, "_specs_tok", None)
            if callable(old_lex) and callable(new_lex):
                row["lexical"] = {"old": old_lex(case["path"]), "current": new_lex(case["path"])}
        rows.append(row)
    return rows


def main():
    old_guard, reason = load_old_guard()
    if old_guard is None:
        print("FAIL: pinned previous guard unavailable:", reason, file=sys.stderr)
        return 1
    fixture = Base(methodName="runTest")
    try:
        fixture.setUp()
        fixture.put("specs/001-x/tasks.md", tasks_text())
        fixture.open_spec()
        cases = collect_cases(fixture.root)
        for case in cases:
            case["event"]["session_id"] = fixture.session
        for row in compare_cases(old_guard, rule_gate, cases):
            print(json.dumps(row, ensure_ascii=True))
        if os.name == "nt":
            print("NOT-VERIFIED: native POSIX paths require execution on Linux")
        else:
            print("NOT-VERIFIED: Windows native filesystem and junctions require execution on Windows")
        return 0
    except Exception as exc:
        print(f"FAIL: portability report could not complete: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        fixture.tearDown()


if __name__ == "__main__":
    raise SystemExit(main())
