from pathlib import Path
from hashlib import sha256
import sys
p = Path(__file__).with_name("tasks.md")
old = p.read_bytes()
before = b"| T-19 | FR-917, AC-909 | `skill/hooks/rule_gate.py` |"
after = b"| T-19 | FR-917, AC-909 | `skill/hooks/rule_gate.py` (same owner as T-02) |"
if old.count(before) != 1:
    raise SystemExit("anchor missing or duplicated")
new = old.replace(before, after, 1)
print("input=" + sha256(old).hexdigest() + " candidate=" + sha256(new).hexdigest())
if sys.argv[1:] == ["--dry-run"]:
    print("DRY RUN")
elif len(sys.argv) == 3 and sys.argv[1] == "--apply" and sys.argv[2] == sha256(old).hexdigest():
    p.write_bytes(new)
    assert p.read_bytes() == new
    print("APPLIED; byte postcheck passed")
else:
    raise SystemExit("usage: --dry-run | --apply INPUT_SHA256")
