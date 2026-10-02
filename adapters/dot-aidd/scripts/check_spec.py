#!/usr/bin/env python3
"""
aidd spec checker — mechanical gap-finder for a specs/[###-feature]/ folder.

Stdlib only, no dependencies. Run it before an Auditor agent spends judgment
re-reading everything by hand — this catches the mechanical gaps (dangling
codes, empty PR/Spec ref, unresolved [Not Verified], orphaned components,
missing backend governance fields) in milliseconds, so the Auditor's time
goes to what a script can't check: does the screenshot match, is the logic
right.

Usage:
    python check_spec.py <path-to-spec-folder>

Exit code 0 = no gaps found. Exit code 1 = gaps found (usable as a gate).
"""
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CODE_RE = re.compile(r'\b(SCREEN-\d+(?:-F\d+)?|CTL-\d+|COMP-\d+|API-\d+|US-\d+)\b')
TABLE_ROW_RE = re.compile(r'^\|(.+)\|\s*$')


def read(path):
    return path.read_text(encoding='utf-8') if path.exists() else ''


def all_codes(text):
    return set(CODE_RE.findall(text))


def table_rows(text, header_hint):
    """Return list of cell-lists for table rows in the first table following a line
    containing header_hint — whether that hint sits in a '## Section' heading (no pipe)
    or directly in the table's own header row (has pipes)."""
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
                # fall through to process this line
            elif stripped.startswith('#'):
                # hit the next section before any table appeared under this hint — give up
                found_hint = False
                continue
            else:
                continue  # skip prose/blank lines while seeking the table
        m = TABLE_ROW_RE.match(line.strip())
        if not m:
            if header_seen:
                in_table = False
                found_hint = False
            continue
        cells = [c.strip() for c in m.group(1).split('|')]
        if not header_seen:
            header_seen = True  # header row
            continue
        if set(''.join(cells)) <= set('-: '):
            continue  # separator row
        rows.append(cells)
    return rows


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)

    spec_dir = Path(sys.argv[1])
    if not spec_dir.is_dir():
        print(f"Not a directory: {spec_dir}")
        sys.exit(2)

    gaps = []

    mockup_audit = read(spec_dir / 'mockup-audit.md')
    plan = read(spec_dir / 'plan.md')
    tasks = read(spec_dir / 'tasks.md')
    qa_audit = read(spec_dir / 'qa-audit.md')
    contracts = read(spec_dir / 'contracts.md')
    spec_text = read(spec_dir / 'spec.md')

    audit_codes = all_codes(mockup_audit) | all_codes(contracts)

    # 0. Step 1.5 Flowmap (visual-flow.toon): must parse, validate and cite real codes
    flow_file = spec_dir / 'visual-flow.toon'
    if (spec_dir / 'visual-flow.md').exists() and not flow_file.exists():
        gaps.append("visual-flow.md is the legacy Mermaid format — migrate it to visual-flow.toon "
                    "(templates/visual-flow.toon, render with `aidd flow`); the user cannot walk a "
                    "raw Mermaid block, and Flowmap validates what Mermaid cannot.")
    if flow_file.exists():
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import flowmap
        _flows, flow_errors, flow_warnings = flowmap.check_file(flow_file, spec_dir)
        for msg in flow_errors:
            gaps.append(f"visual-flow.toon: {msg}")
        for msg in flow_warnings:
            gaps.append(f"visual-flow.toon (warning): {msg}")

    # 1. [Not Verified] rows still open
    not_verified = mockup_audit.count('[Not Verified]')
    if not_verified:
        gaps.append(f"{not_verified} row(s) still tagged [Not Verified] in mockup-audit.md — "
                     f"each one needs a Step 2 align question before planning.")

    # 1b. spec.md's Minimum Requirements Checklist: any row with a blank Answer column
    if 'Minimum Requirements Checklist' in spec_text:
        rows = table_rows(spec_text, 'Minimum Requirements Checklist')
        blank_reqs = [r for r in rows if r and r[0] and (len(r) < 2 or not r[1] or r[1] in ('', '-'))]
        if blank_reqs:
            gaps.append(f"spec.md Minimum Requirements Checklist: {len(blank_reqs)} unanswered "
                         f"question(s) — Step 3 must not start until these are answered or "
                         f"turned into explicit Step 2 align questions.")

    # 2. Codes cited in tasks.md that don't resolve in mockup-audit.md/contracts.md
    if tasks:
        task_codes = all_codes(tasks)
        placeholder_like = {c for c in task_codes if re.search(r'-0*[01]\b', c) is False}
        dangling = sorted(c for c in task_codes if c not in audit_codes)
        if dangling:
            gaps.append(f"Codes cited in tasks.md but not found in mockup-audit.md/contracts.md: "
                         f"{', '.join(dangling)} — either the audit is missing them or they're typos.")

    # 3. Empty PR/Spec ref columns (best-effort: look for rows with a trailing empty cell
    #    where the header row mentioned "PR/Spec ref" or "PR ref")
    for fname, text in (('mockup-audit.md', mockup_audit), ('plan.md', plan), ('contracts.md', contracts)):
        if 'PR/Spec ref' in text or 'PR ref' in text or 'PR (once opened)' in text:
            rows = table_rows(text, 'PR')
            empty_ref_rows = [r for r in rows if r and r[0] and (not r[-1] or r[-1] in ('', '-'))]
            if empty_ref_rows and any('[' not in r[0] and re.match(r'^(SCREEN|CTL|COMP|API)-\d', r[0]) for r in empty_ref_rows):
                gaps.append(f"{fname}: {len(empty_ref_rows)} row(s) with an empty PR/Spec ref — "
                             f"fine before implementation, a gap once Step 5 has started on that code.")

    # 4. Orphaned components: a COMP-nnn in mockup-audit.md never referenced by any SCREEN-XX
    comp_defined = set(re.findall(r'\bCOMP-\d+\b', mockup_audit))
    if comp_defined:
        screen_section = mockup_audit.split('## Component inventory')[0] if '## Component inventory' in mockup_audit else mockup_audit
        used_in_screens = set(re.findall(r'\bCOMP-\d+\b', screen_section))
        orphaned = sorted(comp_defined - used_in_screens)
        if orphaned:
            gaps.append(f"Component(s) defined but not referenced by any screen's 'Uses' column: "
                         f"{', '.join(orphaned)} — dead component, or the screen inventory is missing the reference.")

    # 5. Backend governance gaps in contracts.md: missing stored procedure and no exception reason
    if contracts:
        rows = table_rows(contracts, 'API-nnn')
        for r in rows:
            if len(r) >= 10 and r[0].startswith('API-'):
                sp, exception = r[6] if len(r) > 6 else '', r[9] if len(r) > 9 else ''
                if not sp or sp in ('', '-'):
                    if not exception or exception in ('', '-'):
                        gaps.append(f"{r[0]}: no stored procedure listed and no exception reason — "
                                     f"gap under the 'stored procedures by default' rule.")

    # 6. tasks.md rows missing an explicit out-of-scope note
    if tasks:
        rows = table_rows(tasks, 'Explicitly out of scope')
        for r in rows:
            if r and r[0] and (len(r) < 5 or not r[-1] or r[-1] in ('', '-')):
                gaps.append(f"tasks.md row '{r[0]}': no 'Explicitly out of scope' note — "
                             f"scope discipline requires stating it, not leaving it implicit.")

    # 7. qa-audit.md: any row still without a status
    if qa_audit:
        rows = table_rows(qa_audit, 'Mapping ledger') or table_rows(qa_audit, 'Status')
        unresolved = [r for r in rows if r and r[0] and (len(r) < 2 or not r[1] or r[1] in ('', '-'))]
        if unresolved:
            gaps.append(f"qa-audit.md: {len(unresolved)} code(s) with no status yet — "
                         f"not done while these are blank without an entry in Open Exceptions.")

    # 8. qa-audit.md: Database robustness check rows with any blank/'no' cell
    if 'Database robustness check' in qa_audit:
        rows = table_rows(qa_audit, 'Database robustness check')
        for r in rows:
            if not r or not r[0]:
                continue
            blanks = [c for c in r[1:] if not c or c.strip().lower() in ('', '-', 'no', 'n')]
            if blanks:
                gaps.append(f"qa-audit.md Database robustness check, {r[0]}: "
                             f"{len(blanks)} unresolved column(s) (blank or 'no') — "
                             f"pooling/release/validation/transactions/index-plan must each be "
                             f"answered or moved to Open Exceptions.")

    # 8b. qa-audit.md: Performance & Best Practices check rows with any blank/'no' cell
    if 'Performance & Best Practices check' in qa_audit:
        rows = table_rows(qa_audit, 'Performance & Best Practices check')
        for r in rows:
            if not r or not r[0]:
                continue
            blanks = [c for c in r[1:] if not c or c.strip().lower() in ('', '-', 'no', 'n')]
            if blanks:
                gaps.append(f"qa-audit.md Performance & Best Practices, {r[0]}: "
                             f"{len(blanks)} unresolved column(s) (blank or 'no') — "
                             f"OOP/interfaces/locking/pooling/N+1/blocking-call must each be "
                             f"answered or moved to Open Exceptions.")

    # 9. data-model.md present but missing the Entity -> Table/Column mapping
    data_model_path = spec_dir / 'data-model.md'
    if data_model_path.exists():
        dm_text = read(data_model_path)
        if 'Entity → Table/Column mapping' in dm_text or 'Entity -> Table/Column mapping' in dm_text:
            rows = table_rows(dm_text, 'Table/Column mapping')
            if not rows:
                gaps.append("data-model.md: 'Entity → Table/Column mapping' section has no rows — "
                             "the ER diagram alone doesn't tell code which table/column to hit.")

        # 10. RLS & session table (Supabase/Postgres-with-RLS): any row with an empty condition
        if 'RLS & session' in dm_text:
            rls_rows = table_rows(dm_text, 'RLS & session')
            incomplete = [r for r in rls_rows if r and r[0] and (len(r) < 4 or not r[3] or r[3] in ('', '-'))]
            if incomplete:
                gaps.append(f"data-model.md RLS & session: {len(incomplete)} row(s) with no "
                             f"condition/role — a table with no explicit policy is either fully "
                             f"open or fully locked depending on the platform default; never "
                             f"leave that implicit.")

    # 11. AIDD hard rules (R1 agent-time estimates, R2 route, R3 provenance, R4 visual debt,
    #     R6 approval) — static checks only; the evidence-based rules are enforced by the hooks.
    #     Applied only to artifacts that exist, and to tasks.md only once it has the per-task
    #     blocks / Waves table the rules describe (older table-only tasks.md files stay untouched).
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import aidd_rules
        rule_violations = []
        tasks_structured = bool(re.search(r'^#{2,3}\s*(T-\d+|Waves)(?!\w)', tasks, re.M))
        if (spec_dir / 'spec.md').exists() and (not tasks or tasks_structured):
            rule_violations = aidd_rules.check_spec_dir(spec_dir, static_only=True)
        else:
            if (spec_dir / 'spec.md').exists():
                rule_violations += aidd_rules.check_content('spec', spec_text)
            if tasks_structured:
                rule_violations += aidd_rules.check_content('tasks', tasks)
        for v in rule_violations:
            gaps.append(f"{v['rule']} {v['message']} → {v['fix']}")
    except Exception as e:  # never let the rules library break the mechanical checker
        gaps.append(f"(warning) hard-rules check skipped: {e}")

    print(f"aidd spec check — {spec_dir}")
    print("=" * 60)
    if not gaps:
        print("No mechanical gaps found. (This does not check screenshots, business logic, "
              "or anything requiring judgment — that's still the Auditor's job.)")
        sys.exit(0)

    for i, g in enumerate(gaps, 1):
        print(f"{i}. {g}")
    print(f"\n{len(gaps)} gap(s) found.")
    sys.exit(1)


if __name__ == '__main__':
    main()
