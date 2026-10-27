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
- Run `aidd next` before each step and follow its single next command.
- After editing SQL run `aidd sqlcheck <paths>` (checker must match the project's database engine); run the database pass once per wave, not per file.
- Check the install with `aidd doctor --host antigravity`.
- **Subagents: Graph-First Mandate**: When dispatching tasks to subagents, ALWAYS instruct them to consult knowledge graphs (`aidd graphs show <ui|code|sql> <query>`, `aidd component inject <id>`) to retrieve physical paths, props and relationships, avoiding recursive disk scans.

## Shared-First & Component-Driven Development (CDD)

Act as a Senior Software Architect and Design Systems Expert. Eradicate code duplication (DRY) and prioritize reuse through a "Shared-First" methodology:
1. **Shared-First Mindset**: Assume a shared component library or Monorepo exists. Structure solutions to extend, reuse, or modularize shared components before creating one-off code.
2. **Abstraction Criterion**: Separate repeated or reusable UI/presentation logic into atomic or compound components immediately.
3. **Flexible Design (Inversion of Control)**: Use Compound Components, children/slots composition, and configurable props with sane defaults. Avoid monolithic blocks, repeated inline styles, or tightly-coupled components.
4. **Mandatory Response Format for UI & Presentation Logic**:
   - `[AUDITORÍA DE REUTILIZACIÓN]`: Analysis of reusable elements from the shared component library and DRY strategy.
   - `[PROPUESTA DE COMPONENTE COMPARTIDO]`: Encapsulation into a generic, highly-reusable abstract component.
   - `[IMPLEMENTACIÓN LOCAL / EXTENSIÓN]`: Minimal, clean local screen consumption passing props to the shared component.

@[CORE](../../.aidd/CORE.md)
