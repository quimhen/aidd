# Tasks — Native future output targets

Wave AIDD-FUTURE-TARGETS, owner /root. DRAFT for exact native unit approval, not consent.
Pre-build independent review: batch-staging/future-targets-independent-plan.md.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Explicitly out of scope |
|---|---|---|---|---|
| T-1191 | FR-1190, FR-1191, FR-1193 | `tests/test_aidd_unit_migration.py` | LOGIC | any other file; financial app, DB, gates/evidence weakening |
| T-1192 | FR-1191, FR-1192, FR-1193 | `tests/test_aidd_unit_impact.py` | LOGIC | any other file; financial app, DB, gates/evidence weakening |
| T-1193 | FR-1190, FR-1191, FR-1192, FR-1193 | `skill/scripts/aidd_units.py` | LOGIC | any other file; financial app, DB, gates/evidence weakening |
| T-1194 | FR-1190, FR-1193 | `adapters/dot-aidd/scripts/aidd_units.py` | LOGIC | any other file; financial app, DB, gates/evidence weakening |
| T-1195 | FR-1193 | `pyproject.toml` | LOGIC | any other file; financial app, DB, gates/evidence weakening |
| T-1196 | FR-1193 | `aidd/__init__.py` | LOGIC | any other file; financial app, DB, gates/evidence weakening |

### T-1191
**Classify**
- Nature: INCIDENT
- Priority: 2
- Kind: LOGIC
**Estimate**
- Agent min: 6
- Human ref hours: 0.30
- Tokens (est): 50k
- Agent role: tests
- Model tier: high
- Wave: 1
**Detail**
- Files to change: `tests/test_aidd_unit_migration.py`
- Behaviour: Extend UnitMigrationTests with exact migration, strict-role, race and workflow cases from plan. Use temporary fixture roots; no live project registration.
- Read first: unit spec.md/plan.md and exact native graph targets; preserve current function signatures and snake_case Python/PascalCase class conventions.
- Verification: builders static-only; coordinator executes spec Verification command1 once after tests-first RED and stable source, then command2. Do not claim executed PASS from inspection.
- Do NOT: change files outside this row, create fake outputs, loosen inputs/config/visual/parent checks, fabricate consent/audit, alter reuse/cache, run DB/build/tests as builder or publish before verification.
- Standards: SOLID; one production class per file; fail closed on filesystem ambiguity; no swallowed I/O errors or unbounded retry. Tools-first mapping/dry-run/apply/postcheck. DB only official db_verify default/slots1..3 if ever required; none here.
- Status: done

### T-1192
**Classify**
- Nature: INCIDENT
- Priority: 2
- Kind: LOGIC
**Estimate**
- Agent min: 6
- Human ref hours: 0.30
- Tokens (est): 50k
- Agent role: tests
- Model tier: high
- Wave: 1
**Detail**
- Files to change: `tests/test_aidd_unit_impact.py`
- Behaviour: Extend UnitImpact with missing output planning versus strict executed snapshot, overlap/cache, deterministic digest, ancestry and review/build reachability cases. Reuse existing native test fixture helpers; no production evidence.
- Read first: unit spec.md/plan.md and exact native graph targets; preserve current function signatures and snake_case Python/PascalCase class conventions.
- Verification: builders static-only; coordinator executes spec Verification command1 once after tests-first RED and stable source, then command2. Do not claim executed PASS from inspection.
- Do NOT: change files outside this row, create fake outputs, loosen inputs/config/visual/parent checks, fabricate consent/audit, alter reuse/cache, run DB/build/tests as builder or publish before verification.
- Standards: SOLID; one production class per file; fail closed on filesystem ambiguity; no swallowed I/O errors or unbounded retry. Tools-first mapping/dry-run/apply/postcheck. DB only official db_verify default/slots1..3 if ever required; none here.
- Status: done

### T-1193
**Classify**
- Nature: INCIDENT
- Priority: 2
- Kind: LOGIC
**Estimate**
- Agent min: 10
- Human ref hours: 0.50
- Tokens (est): 75k
- Agent role: builder
- Model tier: high
- Wave: 2
**Detail**
- Files to change: `skill/scripts/aidd_units.py`
- Behaviour: Implement plan steps1–5 exactly; one private typed state helper, no other production files. Preserve strict singular audit snapshot and public consent ABI.
- Read first: unit spec.md/plan.md and exact native graph targets; preserve current function signatures and snake_case Python/PascalCase class conventions.
- Verification: builders static-only; coordinator executes spec Verification command1 once after tests-first RED and stable source, then command2. Do not claim executed PASS from inspection.
- Do NOT: change files outside this row, create fake outputs, loosen inputs/config/visual/parent checks, fabricate consent/audit, alter reuse/cache, run DB/build/tests as builder or publish before verification.
- Standards: SOLID; one production class per file; fail closed on filesystem ambiguity; no swallowed I/O errors or unbounded retry. Tools-first mapping/dry-run/apply/postcheck. DB only official db_verify default/slots1..3 if ever required; none here.
- Status: done

### T-1194
**Classify**
- Nature: INCIDENT
- Priority: 2
- Kind: LOGIC
**Estimate**
- Agent min: 2
- Human ref hours: 0.10
- Tokens (est): 5k
- Agent role: builder
- Model tier: high
- Wave: 3
**Detail**
- Files to change: `adapters/dot-aidd/scripts/aidd_units.py`
- Behaviour: Generate byte-identical mirror from canonical source using fixed source→target mapping, dry-run/apply/postcheck. Same production owner as T-1193; do not hand edit mirror.
- Read first: unit spec.md/plan.md and exact native graph targets; preserve current function signatures and snake_case Python/PascalCase class conventions.
- Verification: builders static-only; coordinator executes spec Verification command1 once after tests-first RED and stable source, then command2. Do not claim executed PASS from inspection.
- Do NOT: change files outside this row, create fake outputs, loosen inputs/config/visual/parent checks, fabricate consent/audit, alter reuse/cache, run DB/build/tests as builder or publish before verification.
- Standards: SOLID; one production class per file; fail closed on filesystem ambiguity; no swallowed I/O errors or unbounded retry. Tools-first mapping/dry-run/apply/postcheck. DB only official db_verify default/slots1..3 if ever required; none here.
- Status: done

### T-1195
**Classify**
- Nature: INCIDENT
- Priority: 2
- Kind: LOGIC
**Estimate**
- Agent min: 1
- Human ref hours: 0.05
- Tokens (est): 2k
- Agent role: builder
- Model tier: high
- Wave: 3
**Detail**
- Files to change: `pyproject.toml`
- Behaviour: Replace project.version0.5.1 with0.5.2 only. Root release lane, same owner as T-1196; no dependency/build-system change.
- Read first: unit spec.md/plan.md and exact native graph targets; preserve current function signatures and snake_case Python/PascalCase class conventions.
- Verification: builders static-only; coordinator executes spec Verification command1 once after tests-first RED and stable source, then command2. Do not claim executed PASS from inspection.
- Do NOT: change files outside this row, create fake outputs, loosen inputs/config/visual/parent checks, fabricate consent/audit, alter reuse/cache, run DB/build/tests as builder or publish before verification.
- Standards: SOLID; one production class per file; fail closed on filesystem ambiguity; no swallowed I/O errors or unbounded retry. Tools-first mapping/dry-run/apply/postcheck. DB only official db_verify default/slots1..3 if ever required; none here.
- Status: done

### T-1196
**Classify**
- Nature: INCIDENT
- Priority: 2
- Kind: LOGIC
**Estimate**
- Agent min: 1
- Human ref hours: 0.05
- Tokens (est): 2k
- Agent role: builder
- Model tier: high
- Wave: 3
**Detail**
- Files to change: `aidd/__init__.py`
- Behaviour: Replace __version__0.5.1 with0.5.2 only. Root release lane, same owner as T-1195; no import/runtime change.
- Read first: unit spec.md/plan.md and exact native graph targets; preserve current function signatures and snake_case Python/PascalCase class conventions.
- Verification: builders static-only; coordinator executes spec Verification command1 once after tests-first RED and stable source, then command2. Do not claim executed PASS from inspection.
- Do NOT: change files outside this row, create fake outputs, loosen inputs/config/visual/parent checks, fabricate consent/audit, alter reuse/cache, run DB/build/tests as builder or publish before verification.
- Standards: SOLID; one production class per file; fail closed on filesystem ambiguity; no swallowed I/O errors or unbounded retry. Tools-first mapping/dry-run/apply/postcheck. DB only official db_verify default/slots1..3 if ever required; none here.
- Status: done

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-1191, T-1192 | tests | 6 | 100 | 0.30 |
| 2 | T-1193 | builder | 10 | 75 | 0.50 |
| 3 | T-1194, T-1195, T-1196 | builder | 2 | 9 | 0.10 |

Total agent time (critical path): 18 min
Total tokens (k): 184

Wave1 tests independent; coordinator records genuine RED before Wave2. Wave2 depends on RED.
Wave3 depends on canonical freeze; mirror/version actions serialized by root. Total26 agent
minutes,18 critical-path minutes,184k tokens. Root then executes verification once and independent
closing audit; no source task is done based only on static checks.

## Approval gate

Present exact unit review package and wait for native owner consent before Step5.
Historical base approval does not approve this new scope. Do not write an Approved line or
approval event. Root runs rules check with --unit future-targets --phase build and explicit
--target for the lane files after legitimate consent. Publication0.5.2 only after verification;
no automatic host-spec close.

## Definition of Done

All declared behaviors proven by coordinated tests; mirror/version check pass; independent
audit receives exact stable scope and results. No unrelated file, fake target or manufactured
evidence. Root performs official release and installed/project sync with backups; source scope
approval is separate from service credentials. Final full host-spec verification remains required.
