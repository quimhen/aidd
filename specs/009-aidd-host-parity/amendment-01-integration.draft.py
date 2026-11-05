"""Integrate 009 amendment for review: --dry-run or --apply SHA256_PLAN."""
from hashlib import sha256
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
PAIRS = (("spec.md", "amendment-01-spec.draft.md"), ("plan.md", "amendment-01-plan.draft.md"), ("tasks.md", "amendment-01-tasks.draft.md"))
MARK = "<!-- 009 amendment 01 integrated for review; approvals pending -->"

def digest(b):
    return sha256(b).hexdigest()

def section(text, heading, next_heading):
    return text.split(heading, 1)[1].split(next_heading, 1)[0]

def rows(text, prefix):
    return "\n".join(line for line in text.splitlines() if re.match(r"^\| " + re.escape(prefix) + r"\d", line))

def insert_before(text, anchor, extra):
    if text.count(anchor) != 1:
        raise ValueError("ambiguous anchor: " + anchor)
    before, after = text.split(anchor, 1)
    return before.rstrip() + "\n" + extra.rstrip() + "\n\n" + anchor + after

def integrate(name, base, draft):
    if MARK in base:
        raise ValueError(name + " already integrated")
    if name == "spec.md":
        fr = rows(section(draft, "## Functional requirements", "## Acceptance cases"), "FR-")
        ac = rows(section(draft, "## Acceptance cases", "## Verification"), "AC-")
        assert len(fr.splitlines()) == 7 and len(ac.splitlines()) == 8
        base = insert_before(base, "## Acceptance cases", fr)
        base = insert_before(base, "## Verification", ac)
        proposal = section(draft, "## Verification", "Proposed consolidation:")
        text = (MARK + "\n\n### Amendment 01: proposed verification, pending R10 approval\n\n"
                "Existing V-1–V-5 remain in the table and historical records remain unchanged. "
                "The following replacement is a proposal, not an additional executable row. "
                "Do not consolidate until T-22/T-25 establish coverage and report skips.\n" + proposal
                + "\nProposed consolidation:" + draft.split("Proposed consolidation:", 1)[1])
        base = insert_before(base, "## Optimization brief", text)
    elif name == "tasks.md":
        table = rows(draft.split("## Per-task detail", 1)[0], "T-")
        assert len(table.splitlines()) == 12
        base = insert_before(base, "## Per-task detail (one block per row above)", table)
        details = section(draft, "## Per-task detail (one block per row above)", "## Waves")
        base = insert_before(base, "## Waves", MARK + "\n\n" + details)
        waves = section(draft, "## Waves", "Total agent time")
        waves = "\n".join(re.sub(r"^\| ([1-4]) \|", lambda m: "| " + str(int(m.group(1)) + 3) + " |", line) for line in waves.splitlines())
        wave_rows = "\n".join(line for line in waves.splitlines() if re.match(r"^\| [4-7] \|", line))
        assert len(wave_rows.splitlines()) == 4
        base = insert_before(base, "Total agent time (critical path):", wave_rows + "\n\nAmendment estimate: 55 min, 1050k tokens; prior totals below cover the original waves only.")
        base = insert_before(base, "## Approval gate", "Amendment tasks and changed verification scope require fresh owner approval; the original seal below is historical and does not approve this amendment.")
    else:
        base += "\n\n" + MARK + "\n\n" + draft
    return base

def main():
    if len(sys.argv) not in (2, 3) or sys.argv[1] not in ("--dry-run", "--apply"):
        raise SystemExit("usage: --dry-run | --apply SHA256_PLAN")
    changes = []
    for target, source in PAIRS:
        old, draft = (ROOT / target).read_bytes(), (ROOT / source).read_bytes()
        newline = "\r\n" if b"\r\n" in old else "\n"
        orig = old.decode("utf-8").replace("\r\n", "\n")
        new = integrate(target, orig, draft.decode("utf-8").replace("\r\n", "\n"))
        for seal in re.findall(r"(?m)^Approved:.*$", orig):
            assert new.count(seal) == 1
        assert new.count(MARK) == 1
        try:
            integrate(target, new, draft.decode("utf-8"))
        except ValueError:
            pass
        else:
            raise AssertionError("idempotence check failed")
        result = new.replace("\n", newline).encode("utf-8")
        changes.append((target, old, draft, result))
        print(f"{target} original={digest(old)} draft={digest(draft)} candidate={digest(result)}")
    plan = digest("\n".join(f"{n}:{digest(o)}:{digest(d)}:{digest(v)}" for n, o, d, v in changes).encode())
    print("plan_sha256=" + plan)
    if sys.argv[1] == "--apply":
        if len(sys.argv) != 3 or sys.argv[2] != plan:
            raise SystemExit("plan hash missing or changed; no files written")
        for name, old, draft, result in changes:
            if (ROOT / name).read_bytes() != old:
                raise SystemExit("input changed; no files written")
        for name, old, draft, result in changes:
            (ROOT / name).write_bytes(result)
        for name, old, draft, result in changes:
            assert (ROOT / name).read_bytes() == result
        print("APPLIED; byte postcheck passed. Fresh approvals still required.")
    else:
        print("DRY RUN; no files written. Original approval seals preserved, repeat integration refused.")

if __name__ == "__main__":
    main()
