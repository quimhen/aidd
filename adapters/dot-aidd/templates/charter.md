# Charter — [project name]

**One file, project-root, not per-feature.** This is what every spec inherits without restating
it — the point is that an agent reads this once and then never has to re-derive "what stack are we
on" or "are we allowed to do X" from scratch on every single task. Fill it in before the first real
spec, keep it current as decisions change, and cite it instead of copying it into `plan.md`.

**Why this is split into two sections, not one list of principles:** a rule an agent can only
promise to follow is worth less than one a script actually checks. Spec-kit's own charter
concept is prose the agent reads and is trusted to remember — this one is prose **plus** a table
`scripts/check_charter.py` runs mechanically, the same "don't trust memory, run the check"
discipline AIDD already applies everywhere else. Put a rule in the checkable table whenever it
*can* be expressed as a pattern; the non-checkable section is for real judgment calls only, not a
dumping ground for rules someone didn't bother to make checkable.

## Stack (locked — a change here is a decision, not a typo fix)

| Layer | Choice | Version | Notes |
|---|---|---|---|
| Frontend | | | |
| Backend | | | |
| Database | | | |
| Auth | | | |

## Non-negotiable architecture rules (prose — judgment calls, not mechanically checked)

State the *project-specific* rules here — AIDD's own defaults (SOLID, Antifragile/Design-for-
Failure, stored-procedures-by-default, one-class-per-file) already apply everywhere via
`AIDD.md` and don't need restating. This section is for decisions unique to *this* project that
a generic rule wouldn't cover, and that a script genuinely can't verify (an architectural
trade-off, a reason a normal rule doesn't apply here, a deliberate exception).

- [ ] [Rule] — [why it exists, so a future agent doesn't "fix" it back]

## Checkable rules (enforced — `scripts/check_charter.py` runs these)

| Rule | Type | Pattern | Applies to (glob) |
|---|---|---|---|
| Never call `console.log` in shipped code | forbidden | `console\.log\(` | `src/**/*.{ts,tsx,js,jsx}` |
| Every API route file declares a rate limit | required | `rateLimit\(` | `src/api/**/*.ts` |
| SAP only: no `--` inside an XML comment (SAP rejects the file) | forbidden | `<!--(?:(?!-->).)*?--(?!>)` | `**/*.xml` |

- **`forbidden`** — the pattern must not appear anywhere under the glob. Any match is a violation,
  reported as `file:line`.
- **`required`** — the pattern must appear at least once somewhere under the glob. Zero matches
  across every file the glob resolves to is a violation. (Per-file requiredness — "every page must
  have X" — isn't checked yet; see the script's own docstring.)
- Delete the example rows above that do not apply before filling this in for real (keep the SAP one
  only if this project writes XML that SAP consumes). An empty table is valid — it
  means this project has no mechanically-checkable charter rules yet, not that the table was
  forgotten.

## SAP pitfalls (only if this project integrates with SAP Business One — delete otherwise)

These families of error recurred across sessions and cost many correction rounds each. The one that a
pattern can catch (`--` inside an XML comment) is the checkable row above; the rest are judgment calls,
so they are prose here, and each needs a real run against SAP before the work is called done:

- **UserFields / UDO codes (UID):** a user-defined field or object name longer than 10 characters is rejected
  by SAP; check the length before creating it, not after the add-on fails to load.
- **`Invalid item`:** raised when an item code, a UoM or a warehouse the document points at does not exist or
  is inactive for that company; validate the master data first, with the real ids.
- **Invalid `U_` property:** the DI API rejects a `U_` field that does not exist on that object or company
  database (including a typo or a field that exists only in another company); list the object's real fields
  before writing to one.
- **Queries inside a SAP transaction:** never run a read query on the same company connection between
  `StartTransaction` and `EndTransaction`; read first, then open the transaction, then write. A lock taken
  inside it can block the user for a long time.
- **Run it:** these only show up when executed against SAP (UI or DI). Record the run in the QA audit's
  "Execution evidence" table; if it cannot be run from here, the code stays ⚠️ PARTIAL until the user runs it.

## Run it

```bash
python scripts/check_charter.py [path-to-project-root]
```

Exit code 0 = no violations. Exit code 1 = violations found (usable as a CI/pre-commit gate, the
same way `check_spec.py` gates Step 6). Run this alongside `check_spec.py`, not instead of it — the
charter covers project-wide invariants, `check_spec.py` covers one spec's own internal
consistency.
