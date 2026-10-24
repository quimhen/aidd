#!/usr/bin/env python3
"""aidd triage: which `aidd verify` failures are shared by several specs and which are specific to one.
Read-only, stdlib only, no LLM. Ported from b1SycLink tools/verify_triage.py.  # aidd:FR-037

Usage: aidd_triage.py [spec_glob ...] [--root R] [--json]
Ends with: RESULT: ok|fail - <N> items - evidence <specs/<id>/evidence dir or ->
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")  # aidd:FR-037
HEADER = re.compile(r"^# (?P<cmd>.*) \| exit (?P<code>-?\d+) \| ")
PATTERNS = [  # aidd:FR-037
    ("pgtap", re.compile(r"^\[FAIL\]\s+(\S+\.test\.sql)")),
    ("pgtap-apply", re.compile(r"^\[FAIL\]\s+((?:migration|seed)\s+\S+)")),
    ("vitest", re.compile(r"^\s*FAIL\s+(\S+\.test\.\w+(?:\s+>\s+.+?)?)\s*$")),
    ("pytest", re.compile(r"^FAILED\s+(?!\()(\S+)")),
    ("tsc", re.compile(r"^(\S+\(\d+,\d+\): error TS\d+)")),
]


UNITTEST = re.compile(r"^(?:FAIL|ERROR): (\w+) \(([\w.]+)\)\s*$")  # aidd:FR-037
UNITTEST_SUMMARY = re.compile(r"^FAILED \((?:failures|errors)=\d+.*\)\s*$")


def parse_row(path: Path) -> dict:  # aidd:FR-037
    try:
        text = ANSI.sub("", path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        text = ""
    lines = text.splitlines()
    m = HEADER.match(lines[0]) if lines else None
    items: list[tuple[str, str]] = []
    seen = set()
    summary = None
    for ln in lines[1:]:
        um = UNITTEST.match(ln)
        if um:
            name, ref = um.groups()
            key = ref if ref.endswith("." + name) else f"{ref}.{name}"
            if ("unittest", key) not in seen:
                seen.add(("unittest", key))
                items.append(("unittest", key))
            continue
        if UNITTEST_SUMMARY.match(ln):
            summary = ln.strip()
            continue
        for kind, rx in PATTERNS:
            mm = rx.match(ln)
            if mm and (kind, mm.group(1)) not in seen:
                seen.add((kind, mm.group(1)))
                items.append((kind, mm.group(1)))
    if summary and not any(k == "unittest" for k, _ in items):
        items.append(("unittest", summary))  # fallback: no named test could be extracted
    return {"row": path.stem.replace("verify-", "", 1), "cmd": (m.group("cmd") if m else "?")[:90],
            "exit": int(m.group("code")) if m else None, "items": items}


def main(argv: list[str]) -> int:  # aidd:FR-037
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    as_json = "--json" in argv
    root = Path.cwd()
    globs: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--root" and i + 1 < len(argv):
            root = Path(argv[i + 1])
            i += 1
        elif not a.startswith("--"):
            globs.append(a)
        i += 1
    globs = globs or ["*"]
    specs_dir = root / "specs"
    found = set()
    try:
        for g in globs:
            for d in specs_dir.glob(g):
                try:
                    if (d / "evidence").is_dir():
                        found.add(d)
                except OSError:
                    pass
    except (OSError, ValueError, NotImplementedError):
        pass
    specs = sorted(found)
    report, groups = {}, defaultdict(set)
    for d in specs:
        try:
            files = sorted((d / "evidence").glob("verify-*.txt"))
        except OSError:
            files = []
        rows = [parse_row(p) for p in files]
        report[d.name] = rows
        for r in rows:
            if r["exit"] not in (0, None):
                for kind, ident in r["items"]:
                    groups[(kind, ident)].add(d.name)
    shared = {k: sorted(v) for k, v in groups.items() if len(v) > 1}
    own = {k: sorted(v) for k, v in groups.items() if len(v) == 1}
    n = len(groups)
    ev = f"specs/{specs[0].name}/evidence" if len(specs) == 1 else (f"{len(specs)} specs under specs/*/evidence" if specs else "-")
    result = f"RESULT: {'ok' if n == 0 else 'fail'} - {n} items - evidence {ev}"
    if as_json:
        print(json.dumps({"specs": report, "shared": {f"{k[0]}:{k[1]}": v for k, v in shared.items()},
                          "own": {f"{k[0]}:{k[1]}": v for k, v in own.items()}, "items": n, "result": result}, indent=1))
        return 0 if n == 0 else 1
    for name, rows in report.items():
        bad = [r for r in rows if r["exit"] not in (0, None)]
        print(f"{name}: {len(rows) - len(bad)}/{len(rows)} rows pass" + ("" if not bad else "  <- FAIL rows: " + ", ".join(r["row"] for r in bad)))
        for r in rows:
            print(f"    {'FAIL' if r in bad else 'PASS'} {r['row']} exit {r['exit']}: {r['cmd']}")
            for k, it in r["items"][:6] if r in bad else []:
                print(f"       {k}:{it}" + (" [SHARED]" if (k, it) in shared else ""))
    print(f"\n== {len(shared)} failing item(s) shared by 2+ specs (fix once), {len(own)} specific to one spec")
    for (kind, ident), who in sorted(shared.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        print(f"  SHARED {len(who):2d} specs  {kind}:{ident}  ({', '.join(who)})")
    for (kind, ident), who in sorted(own.items()):
        print(f"  specific  {kind}:{ident}  ({who[0]})")
    print(result)
    return 0 if n == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
