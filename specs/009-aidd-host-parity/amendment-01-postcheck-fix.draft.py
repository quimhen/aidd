"""Fix mechanical integration findings; --dry-run or --apply expected input SHA256."""
from hashlib import sha256
from pathlib import Path
import sys

p = Path(__file__).with_name("tasks.md")
old = p.read_bytes()
edits = ((b"| T-19 | FR-917, AC-909 | `skill/hooks/rule_gate.py` | LOGIC | | | fingerprint semantic changes |", b"| T-19 | FR-917, AC-909 | `skill/hooks/rule_gate.py` | LOGIC | | | fingerprint semantic changes; same owner as T-02 |"),
         (b"Total agent time (critical path): 42 min", b"Total agent time (critical path): 97 min"),
         (b"Total tokens (k): 845", b"Total tokens (k): 1895"),
         (b"Amendment estimate: 55 min, 1050k tokens; prior totals below cover the original waves only.", b"Amendment estimate: 55 min, 1050k tokens; totals below include all waves."))
new = old
for before, after in edits:
    if new.count(before) != 1:
        raise SystemExit("missing or ambiguous anchor; no writes")
    new = new.replace(before, after, 1)
print("input=" + sha256(old).hexdigest() + " candidate=" + sha256(new).hexdigest())
if sys.argv[1:] == ["--dry-run"]:
    print("DRY RUN")
elif len(sys.argv) == 3 and sys.argv[1] == "--apply" and sys.argv[2] == sha256(old).hexdigest():
    p.write_bytes(new)
    assert p.read_bytes() == new
    print("APPLIED; byte postcheck passed")
else:
    raise SystemExit("usage: --dry-run | --apply INPUT_SHA256")
