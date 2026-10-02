# Plan — 003 AIDD Interaction Evidence

Drafted from the Mapper's verified read of the code (insertion points confirmed with line numbers; items it could
not verify are marked UNVERIFIED and are re-checked by the task that needs them).

## Naming & File Contract (fill this first — everything below depends on it)
| Item | Convention |
|---|---|
| Classes / components / types | PascalCase (tests: `TestXxx` classes, as in the existing suites) |
| Functions / variables / methods | snake_case, as every existing module under `skill/scripts/` and `skill/hooks/` (Python); private helpers prefixed `_` |
| File names | snake_case `.py` for code; kebab-case `.md` for templates (existing names kept); new test files `tests/test_<topic>.py` |
| Classes per file | One class per file where a class is introduced; the existing modules are function-style and stay so |
| File-path pattern | scripts in `skill/scripts/`, hooks in `skill/hooks/`, templates in `skill/templates/`, tests in `tests/`; byte-identical mirrors in `adapters/dot-aidd/scripts/` (see T7) |
| Rule ids | `R10` execution evidence, `R11` root cause on repeat, `R12` view-vs-logic tag; added to `RULE_IDS` |
| Shell | The Bash tool fails on this machine (Cygwin mount error): Builders use PowerShell, Grep, Read |

### Database object naming
Not applicable: this feature touches no database (stdlib file parsing only).

## Screen → Code map
No screens: this feature has no visual surface (Steps 0, 1 and 1.5 are waived in `spec.md`), so there is no
screen-code row. The equivalent map below is File → Task.

## Component → Code map
No reusable UI components. See "Contracts fixed before building".

## File → Task map (same-wave tasks own DISJOINT files)

| Task | Wave | Owns exclusively |
|---|---|---|
| T-01 rules engine R10-R12 | 1 | `skill/scripts/aidd_rules.py`; NEW `tests/test_aidd_rules_r10.py` (T-01 does NOT edit `tests/test_aidd_rules.py`) |
| T-03 templates | 1 | `skill/templates/{qa-audit,mockup-audit,plan,tasks,spec,contracts,STATE,charter}.md`, NEW `skill/templates/traceability.md`, `skill/templates/design-system/components-index.md`, the matching files under `adapters/dot-aidd/templates/`; the template-consistency class in `tests/test_aidd_rules.py` (only if a template change requires it) |
| T-05 credential hygiene | 1 | `skill/hooks/prompt_trigger.py`, `skill/hooks/mark_user_question.py`, `skill/hooks/mark_agent_dispatch.py`, `skill/scripts/aidd_evidence.py`; tests in `tests/test_hooks.py` and `tests/test_evidence.py` |
| T-08 memory import | 1 | no repo file; writes `.aidd/memory/` into the NominaOne and BusProApp repos with `aidd mem import-claude-mem` |
| T-02 gate + status | 2 | `skill/hooks/rule_gate.py`, `skill/scripts/aidd_status.py`, `tests/gate_fixtures.py`, `tests/test_rule_gate.py`, `tests/test_aidd_status.py` |
| T-04 check_spec gaps | 2 | `skill/scripts/check_spec.py`, `tests/test_check_spec.py` (needs BOTH T-01 and T-03: header names and the `Contract hash: PENDING` line come from T-03's templates) |
| T-06 docs | 3 | `skill/SKILL.md`, `skill/AIDD.md`, `adapters/dot-aidd/AIDD.md`, `README.md` (R1-R9 mention) |
| T-07 mirror, install, full run | 4 | byte-identical copies into `adapters/dot-aidd/scripts/` of `aidd_rules.py`, `aidd_evidence.py`, `aidd_status.py`, `check_spec.py`; the install copy at `C:\Users\jquimis\.claude\skills\aidd`; the full `unittest discover` |

Test-ownership rules (audit findings): `tests/gate_fixtures.py` is edited only by T-02 (wave 2); T-01 may import from it
but must not edit it and keeps its own fixtures inside `tests/test_aidd_rules_r10.py`. T-05 changes hooks that
`tests/test_rule_gate.py`, `tests/test_aidd_status.py` and `tests/test_hooks.py` also exercise: T-05 runs the full suite, may
fix only `tests/test_hooks.py` and `tests/test_evidence.py`, and REPORTS (never edits) a break in a file it does not own.
T-03's template test (`tests/test_aidd_rules.py` ~L592 asserts the raw tasks template yields only `{'R1'}`) is verified in wave 4
because it depends on T-01's R12; `traceability.md` is added to the both-trees needles in `test_trees_consistent`.

## Contracts fixed before building (so wave-1 and wave-2 agents agree)

1. **`check_content(kind, text, spec_dir=None, root=None)`**. `kind='qa'` routes to `check_qa(text, spec_dir, root)`;
   `kind='tasks'` also runs R12. Same try/except as today; never raises.
2. **`check_qa(text, spec_dir=None, root=None, last_edit_ts=None)`** returns `_v(rule, message, fix)` dicts for R10 and R11.
   File-existence checks use `spec_dir/rel` then `root/rel` through the existing `_inside_exists` (inside-root only; drive
   letters, UNC and `..` escapes are not evidence). Freshness runs only when `last_edit_ts` is given (hook path).
3. **`check_spec_dir`** adds, before the static-only return, `if qa_p.exists(): out += check_qa(read(qa_p), d, proj)`
   (file content only, no evidence log). `RULE_IDS` gains `R10`, `R11`, `R12`.
4. **Ledger parsing:** the `Mapping ledger` table; ✅ test is `_plain(status).startswith('✅')` (never whole-string compare:
   ⚠️ carries U+FE0F). Requires evidence: Code matching `^SCREEN-\d+`, `^API-\d+` or `-F\d+$`. Exempt: Codes in `Open exceptions`.
5. **R11 rows:** `## Bug reports` with `| # | Code | Symptom | Root cause | Fix | Pattern sweep |`; rows grouped by Code in table order.
6. **R12 location:** `_check_tasks` calls `_check_kind(rows, blocks)` after the neutral-cell check. Task rows are lines starting
   `|` whose first cell is `T-\d+`, joined with their `### T-nn` block (T-01 writes this scan itself: `_task_blocks` only builds
   the `### T-nn` blocks; `_clean` already drops HTML comments). Trigger: text cites `SCREEN-\d+|COMP-\d+` AND matches
   `reutiliza\w*|remapea\w*|envuelve\w*|wrap\w*|reus\w*|rewir\w*` (case-insensitive, deliberately broad: wrapper/reused count).
   Requirement: `Kind: VIEW-new` or `Kind: LOGIC` or `Kind: VIEW-legacy: <5+ chars>` (whole remainder after the first colon).
   `Kind` is hashed text: do NOT add it to `_HASH_EXCLUDED`. **The tasks template currently has a column "New view vs. reuse" and a
   placeholder `reuse logic only` next to `SCREEN-01`, which would trip R12 on the raw template: T-03 REPLACES that column with
   `View / logic` (values `VIEW-new | LOGIC | VIEW-legacy`) and keeps no reuse word beside a screen/component code.**
   Known consequence: `aidd rules approve` (`cmd_approve`) refuses a tasks.md failing `check_content`, and adding `Kind` changes
   the approval hash, so an already-approved tasks.md with reuse wording must be re-approved.
7. **Contract hash (G4/T-03/T-04):** `Contract hash: <12 hex>` line in `contracts.md`. Hash = sha1 of the table whose header
   starts `API-nnn`, rows joined by `\n`, each row = cells stripped, internal whitespace collapsed, the `PR/Spec ref` column
   removed (write-back column), joined by `|`; first 12 hex. T-03 ships `Contract hash: PENDING`; T-04 implements the
   computation and `--stamp-contract`.
8. **Redaction (T-05):** `aidd_evidence.redact_secrets(text) -> (text, labels)`. Order: cap the input at 20,000 chars, collapse whitespace (`re.sub(r'\s+',' ')`, as `prompt_trigger.py` does today) (bounds
   regex work; the existing `aidd_memory_import._scrub` uses unbounded `[\w-]*` and is quadratic-prone, so it is NOT reused), then
   redact, then truncate to the 4,000-char limit (so a secret cut by the limit is never left half-exposed). Regex is linear-time:
   bounded quantifiers only (`[\w-]{0,40}` around the keyword), no nested quantifiers. Matches `password|passwd|pwd|clave|contraseña|secret|token|api[_ -]?key|bearer`
   followed by `=` or `:` and a value → `label=[redacted]`. Used for prompts, AskUserQuestion answers and the first 400 chars of
   subagent prompts. The hygiene warning prints independent of the planning-keyword match, and `prompt_trigger.py` still ends
   in `sys.exit(0)`. Quote verification (R3/R5) must still pass for ordinary text.
9. **Tests keep passing:** `REQUIRED_QUESTIONS` stays the 7 rows; new optional Align rows live in a separate section
   (`## Optional Align questions`), never as checklist rows; `spec.md` template stays byte-identical in both template trees.
   Placeholder `✅` rows in the qa-audit template sit inside an HTML comment or follow a non-✅ first row so the template itself
   passes R10.
10. **Hook wiring for R10/R11 (T-02):** in `rule_gate.py`, add `'qa-audit.md'` to the `_would_be` list (~L509) and a content block
    mirroring the spec/tasks one (new violations only on Edit, any on a whole-file Write); `_qa_gate` returns early when there are no
    `code_edit` events, so R10/R11 content checks must run BEFORE/independent of that early return, and only freshness depends on edits.
11. **R10 freshness is best-effort, and the docs say so (limits verified by the auditor):** (a) edits made through PowerShell/Bash
    are not recorded (`mark_code_edit.py`), so evidence made stale that way passes; (b) only `CODE_EXTENSIONS` are recorded, so edits
    to `.json/.xml/.html/.css/.yml/.xaml` are invisible; (c) `code_edit` has no spec attribution, so any recorded code edit in the
    project (this session) makes all file evidence stale; (d) `http(s)://` evidence has no mtime and is not freshness-checked;
    (e) file mtime resets on git checkout or copy. `last_edit_ts` is session-scoped (`ev.events(root, session, 'code_edit')`, as
    `aidd_rules.py` ~L1243 does). The existence/kind/status checks are the hard part of R10; freshness is the soft part.
12. **Exit-0 rule:** every new check lives inside the hooks' existing `try/except`; `AIDD_RULES=warn|off` keeps working.

## Decisions on points the spec left open
- `aidd rules close` (`_close_gaps`) is NOT extended with R10/R11: they already block the write of `qa-audit.md`, which close requires.
- Redaction is also applied to answers and subagent prompt heads (same secret can arrive there); spec FR-006 is satisfied by prompts,
  this is the same helper at two more call sites.
- `stop_gate.py` is unchanged (it checks existence and audit domains, not content).

## Design system source (Step 0)
| Item | Value |
|---|---|
| Mockup exists? | no — waived in `spec.md` (no visual surface) |
| Approved design-system doc (if any) | not applicable |
| Fidelity level decided in Clarify | not applicable (no mockup) |
