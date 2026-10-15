---
trigger: always_on
description: This project uses AIDD for any change; read .aidd/CORE.md first.
---

# AIDD is mandatory in this project

- Any change (feature, bugfix, refactor, UI or not) goes through AIDD. Read `.aidd/CORE.md` first (it is short).
- Never load `.aidd/AIDD.md` whole (120 KB, hosts truncate it). CORE.md section 6 shows how to read one section.
- Before creating anything run `python .aidd/scripts/find_spec.py <keywords>` and state: `AIDD intake: NEW SPEC | AMENDMENT | AMENDMENT — Fast Lane — <reason>`.
- A write to code is blocked by the hook unless the spec has the owner's approval (`aidd rules check specs/<id>`).
- A task is done only when executed and, for any screen, compared with its mockup.
- Check the install with `aidd doctor --host antigravity`.

@[CORE](../../.aidd/CORE.md)
