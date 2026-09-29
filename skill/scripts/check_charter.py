#!/usr/bin/env python3
"""
aidd charter checker — runs a project's charter.md "Checkable
rules" table for real, mechanically, instead of trusting an agent to
remember and follow prose. Own design — this is the part that makes AIDD's
charter concept a genuine step past a plain principles document: the
rules that CAN be checked, are.

Two rule types, from charter.md's Checkable rules table:
  forbidden — the pattern must not appear anywhere under the glob. Any match
              is a violation (file:line reported).
  required  — the pattern must appear at least once somewhere under the
              glob's matching files. Zero matches anywhere is a violation.
              (This checks project-wide presence, not "every single file
              matching the glob has it" — a true per-file requiredness check
              needs per-file semantics this v1 doesn't attempt; state that
              limitation rather than silently under- or over-reporting.)

Usage:
    python check_charter.py [project-root]   # defaults to cwd

Exit code 0 = no violations (or no checkable rules — an empty table is valid).
Exit code 1 = violations found.
Exit code 2 = usage error, or no charter.md found.
"""
import fnmatch
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

TABLE_ROW_RE = re.compile(r'^\|(.+)\|\s*$')
UNESCAPED_PIPE_RE = re.compile(r'(?<!\\)\|')


def split_cells(inner: str):
    """Split one table row's inner text on '|', but not on a backslash-
    escaped '\\|' — a regex alternation like `A\\|B\\|C` is a normal, expected
    thing to want in a Pattern cell (check_charter.py's own Checkable rules
    table), and a naive `.split('|')` would silently shred it into extra,
    garbage columns instead of erroring loudly. Each cell then has its own
    `\\|` unescaped back to a literal `|` — the escaping only exists to
    survive this split, not to appear in the value itself."""
    return [c.strip().replace('\\|', '|') for c in UNESCAPED_PIPE_RE.split(inner)]


def unbacktick(cell: str) -> str:
    """Charter.md's own template wraps Pattern/glob cells in backticks for
    markdown readability (`` `console\\.log\\(` ``) — strip exactly one
    leading+trailing backtick pair if both are present, so the compiled regex
    is the pattern itself, not the pattern plus two literal backticks that
    will never appear in real source and would make a `forbidden` rule
    silently never match anything (false "no violations")."""
    if len(cell) >= 2 and cell.startswith('`') and cell.endswith('`'):
        return cell[1:-1]
    return cell


def table_rows(text, header_hint):
    """Same mechanism as check_spec.py / tasks_to_issues.py — kept as its own
    copy in each script deliberately (see check_spec.py's own note): these
    are small, standalone, stdlib-only tools, not a shared library."""
    lines = text.splitlines()
    rows = []
    found_hint = False
    in_table = False
    header_seen = False
    for line in lines:
        if not found_hint:
            if header_hint in line:
                found_hint = True
            continue
        if not in_table:
            stripped = line.strip()
            if stripped.startswith('|'):
                in_table = True
            elif stripped.startswith('#'):
                found_hint = False
                continue
            else:
                continue
        m = TABLE_ROW_RE.match(line.strip())
        if not m:
            if header_seen:
                in_table = False
                found_hint = False
            continue
        cells = split_cells(m.group(1))
        if not header_seen:
            header_seen = True
            continue
        if set(''.join(cells)) <= set('-: '):
            continue
        rows.append(cells)
    return rows


def parse_checkable_rules(text):
    """Rule | Type | Pattern | Applies to (glob). Rows whose Type isn't
    exactly 'forbidden' or 'required' are skipped, not guessed at — a typo
    in the table should be visibly ignored, not silently misapplied."""
    rows = table_rows(text, 'Checkable rules')
    rules = []
    for r in rows:
        if len(r) < 4:
            continue
        rule, rule_type, pattern, glob = r[0], r[1].strip().lower(), unbacktick(r[2]), unbacktick(r[3])
        if rule_type not in ('forbidden', 'required'):
            continue
        if not pattern or pattern in ('-', ''):
            continue
        rules.append({'rule': rule, 'type': rule_type, 'pattern': pattern, 'glob': glob})
    return rules


def expand_glob(root: Path, glob_pattern: str):
    """Supports a brace list at one path segment (e.g. src/**/*.{ts,tsx}),
    which Path.glob alone doesn't — charter.md's own example uses one."""
    brace_match = re.search(r'\{([^{}]+)\}', glob_pattern)
    if not brace_match:
        return sorted(p for p in root.glob(glob_pattern) if p.is_file())
    alternatives = brace_match.group(1).split(',')
    files = set()
    for alt in alternatives:
        expanded = glob_pattern[:brace_match.start()] + alt.strip() + glob_pattern[brace_match.end():]
        files.update(p for p in root.glob(expanded) if p.is_file())
    return sorted(files)


def check_rule(root: Path, rule: dict):
    """Returns a list of violation strings for one rule; empty = passes."""
    try:
        pattern_re = re.compile(rule['pattern'])
    except re.error as e:
        return [f"rule '{rule['rule']}': invalid regex pattern {rule['pattern']!r} ({e})"]

    files = expand_glob(root, rule['glob'])
    violations = []

    if rule['type'] == 'forbidden':
        for f in files:
            try:
                text = f.read_text(encoding='utf-8', errors='ignore')
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if pattern_re.search(line):
                    violations.append(
                        f"'{rule['rule']}' — forbidden pattern found: "
                        f"{f.relative_to(root)}:{lineno}"
                    )
        return violations

    # required
    if not files:
        return [f"'{rule['rule']}' — required pattern, but no files matched glob {rule['glob']!r}"]
    found = False
    for f in files:
        try:
            text = f.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        if pattern_re.search(text):
            found = True
            break
    if not found:
        violations.append(
            f"'{rule['rule']}' — required pattern {rule['pattern']!r} not found anywhere "
            f"under {rule['glob']!r} ({len(files)} file(s) checked)"
        )
    return violations


def main():
    args = sys.argv[1:]
    if len(args) > 1:
        print(__doc__)
        sys.exit(2)

    root = Path(args[0]) if args else Path.cwd()
    if not root.is_dir():
        print(f"Not a directory: {root}")
        sys.exit(2)

    charter_path = root / 'charter.md'
    if not charter_path.exists():
        print(f"No charter.md found at {root} — nothing to check.")
        sys.exit(2)

    text = charter_path.read_text(encoding='utf-8')
    rules = parse_checkable_rules(text)

    print(f"aidd charter check — {charter_path}")
    print("=" * 60)

    if not rules:
        print("No checkable rules defined — the table is empty. That's valid, not a gap.")
        sys.exit(0)

    all_violations = []
    for rule in rules:
        all_violations.extend(check_rule(root, rule))

    if not all_violations:
        print(f"{len(rules)} rule(s) checked, no violations.")
        sys.exit(0)

    for i, v in enumerate(all_violations, 1):
        print(f"{i}. {v}")
    print(f"\n{len(all_violations)} violation(s) across {len(rules)} rule(s).")
    sys.exit(1)


if __name__ == '__main__':
    main()
