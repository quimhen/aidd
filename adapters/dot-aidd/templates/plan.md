# Plan — [feature name]

## Naming & File Contract (fill this first — everything below depends on it)
| Item | Convention |
|---|---|
| Classes / components / types | PascalCase |
| Functions / variables / methods | camelCase |
| File names | [project's own convention — snake_case, kebab-case, PascalCase-per-file; state it, don't default to a personal preference] |
| Classes per file | **One. Never bundle multiple classes into one file** — it makes the file unsustainable to edit and collides unrelated tasks on the same file. |
| File-path pattern (if one exists) | [e.g. `feature/presentation/pages/<snake_case>.dart` matching the mockup screen title] |

### Database object naming (fill only if this feature touches a database — same contract, same rigor)
| Item | Convention |
|---|---|
| Tables | [state it — e.g. PascalCase singular `Order`, or snake_case plural `orders`; whichever this DB already uses] |
| Columns | [state it — e.g. PascalCase `OrderId`, or snake_case `order_id`] |
| Primary keys | [e.g. `Id`, or `<table>_id`] |
| Foreign keys | [e.g. `<TargetTable>Id`, or `<target_table>_id`] |
| Stored procedures | [e.g. `sp_<Verb><Entity>` → `sp_CreateOrder`] |
| Indexes | [e.g. `ix_<table>_<column(s)>` → `ix_orders_client_id`] |
| Constraints (unique/check) | [e.g. `uq_<table>_<column>`, `ck_<table>_<rule>`] |
| Views | [e.g. `vw_<name>`] |

An agent unsure which casing applies to what stops and asks — it never picks one on its own. This applies identically to database objects: never invent a naming style per-procedure because the contract above didn't cover it — extend the table instead, don't improvise around it.

## Screen → Code map
One row per SCREEN-XX — its page file. Pages import components; they don't reimplement them.

| SCREEN-XX | File/component | Spec folder | PR (once opened) | Notes / exception to the convention |
|---|---|---|---|---|
| SCREEN-01 | | | | |

## Component → Code map
One row per COMP-nnn — its shared component file, built once and imported by every screen that uses it.
Never let a component get re-implemented inline inside a page file just because that's where it was first needed.

| COMP-nnn | File/component | Used by (SCREEN-XX list) | PR (once opened) |
|---|---|---|---|
| COMP-001 | | | |

## Design system source (Step 0)
| Item | Value |
|---|---|
| Mockup exists? | yes → source in mockup-audit.md / no → design-system/MASTER.md written before Step 1 |
| Approved design-system doc (if any) | |
| Fidelity level decided in Clarify | exact structure/style \| functional behavior only |
