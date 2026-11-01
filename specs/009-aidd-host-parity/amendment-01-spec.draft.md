# Draft amendment 01 — host and CI portability (spec 009)

**DRAFT — not approved; not an authorization to change code.** Candidate amendment following the spec search and the GitHub Actions Test run 40691930673; 010 remains the owner of the shell-guard equivalence and performance contract, and 004 owns flowmap behavior. The prior approval of spec 009 does not cover these new rows.

Risk: high — protected-file gates are security-sensitive; audit security, functional and performance independently after executed checks.

## Minimum Requirements Checklist (fill before Step 3 starts)

| Question | Answer | Source | If unanswered |
|---|---|---|---|
| Which module/area of the system? | AIDD CI, path guards, memory import, flowmap and corresponding tests | repo — .github/workflows/test.yml:1 | → Step 2 align question |
| New development or modification of something existing? | Modification of host parity and guard compatibility | repo — specs/009-aidd-host-parity/spec.md:20 | → Step 2 align question |
| Does it involve an external service, API, or integration? | GitHub Actions executes the CI matrix | repo — .github/workflows/test.yml:1 | → Step 2 align question |
| Who is requesting it? (role/profile, not necessarily the name) | Project owner | repo — specs/009-aidd-host-parity/spec.md:15 | → Step 2 align question |
| Dependencies on other modules or active developments? | Specs 004 and 010, mirror copies and fingerprint work sharing aidd_evidence.py | repo — specs/010-aidd-shell-guard-speed/spec.md:23 | → Step 2 align question |
| Business objective (1 sentence — what it achieves and why) | Run the documented Python/OS matrix with protective gate behavior and actual test coverage | repo — pyproject.toml:12 | → Step 2 align question |
| Expected visual fidelity level (if there's a mockup): exact \| functional behavior only | No screen or visual surface | repo — specs/009-aidd-host-parity/spec.md:37 | → Step 2 align question |

## Executive summary

- **Objective:** make the existing Linux/Windows CI matrix execute the actual suite on Python 3.10–3.12 while preserving R6/R9 protection.
- **Scope:** convert the two pytest-only modules to stdlib unittest, keep pinned test-only pytest for existing verification commands, remove the Python 3.10/3.11 syntax failure, fix native/foreign path classification and Windows memory-import regression, and restore pinned guard-equivalence coverage in CI. No package runtime dependency or deployment.
- **Cost:** proposed 11 implementation or diagnostic tasks plus one coordinated verification, four serial waves, 55 agent minutes on the critical path, 1050k tokens; excludes any pause to approve a confirmed spec-010 exception.
- **Risks:** false-allow in protected paths; false-block from treating Windows path strings as native POSIX; loss of existing cases during test conversion; unresolved root cause of Windows memory import. Cover each with both deny and legitimate-path tests and full OS matrix.
- **Open decisions:** an exception to spec 010 FR-1003 requires owner review of the exact observed old/new/desired cases before acceptance; this draft does not approve a blanket exception.

## Scope

Included: Python 3.10, 3.11 and 3.12 on Ubuntu and Windows; R6/R9 spec/artifact and protected path guards; drive-letter, UNC, extended UNC, relative and native POSIX paths; existing test-only pytest imports; flowmap HTML serialization; memory importer absolute-in-root vs outside paths; pinned baseline availability. Out: publishing, production deployment, changes to rule meanings, deliberate authorization bypass, new runtime dependencies, unsupported OS promises and changes to fingerprint/reuse ownership held by the separate optimization lane.

## Functional requirements

| FR-nnn | Requirement | Cites (SCREEN-XX-Fnn / CTL-nnn / API-nnn) |
|---|---|---|
| FR-915 | CI matrix executes stdlib discovery and actually collects all cases previously defined in the two pytest-only modules without requiring pytest. | — |
| FR-916 | flowmap parses and renders on Python 3.10–3.12 without changing JSON escaping or script boundary behavior. | — |
| FR-917 | R6/R9 correctly classify native POSIX and Windows paths, drive, UNC and extended UNC spellings; ambiguous foreign-platform spellings fail closed for protected artifacts without treating an unrelated native path as inside the project. | FR-905 |
| FR-918 | Memory import keeps absolute in-project files as relative paths, keeps valid relative paths and rejects outside, traversal and sensitive paths on Windows and POSIX. | — |
| FR-919 | CI loads the pinned old guard and confirms required equivalence cases actually ran; absent history, loader errors, missing cases or skips fail the check. | FR-1003 |
| FR-920 | On each OS, record the old/current/desired decision for each path probe before implementing any owner-reviewed, enumerated security correction; all other FR-1003 cases retain exact decision and message equivalence. | FR-1003 |
| FR-921 | Existing `python -m pytest` verification rows use pinned test-only pytest without a runtime dependency; changing those rows requires separate approval. | FR-901 |

## Acceptance cases

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| AC-907 | CI discovery, `test_aidd_readiness.py` | At least nine unittest cases run, including both parameter values, no missing pytest. | no |
| AC-908 | CI discovery, `test_visual_review_binding.py` | At least six unittest cases run, including snapshot approval binding. | no |
| AC-909 | `D:/proj/specs/F23-eDoc-POS/tasks.md`, `\\\\server\\share\\specs\\F23-eDoc-POS\\tasks.md`, extended UNC, native POSIX and `..` | Protected tokens cannot bypass R6/R9; legitimate unrelated paths are allowed. | yes |
| AC-910 | An absolute existing file inside temp project and `C:/Users/someone/.claude/plans/x.md` outside | Import records only the inside path in relative POSIX form. | yes |
| AC-911 | CI 3.10/3.11/3.12 on Ubuntu and Windows | Syntax/import and full discovery pass; old-guard comparison is executed, not skipped because of a shallow clone. | no |
| AC-912 | Old/current/desired comparison for every reported guard regression and foreign drive/UNC spelling | Any intentional old-to-new difference is enumerated, security-justified and owner-reviewed; all other results and messages remain equivalent. | yes |
| AC-913 | Runner fixture: missing, skipped, failing, crashing or timed-out required case | CI exits nonzero with a useful diagnostic; zero-case or skipped coverage is never success. | yes |
| AC-914 | Missing relative file, in-root path whose parent symlink points outside, foreign absolute and sibling-prefix path | A missing relative file remains allowed only after existing-parent containment is established; outside or unprovable absolute paths are rejected. | yes |

## Verification

| # | Command | Expected | Covers |
|---|---|---|---|
| V-5 | `python tests/run_parallel.py --ci-guard` | exit 0 | FR-901..FR-921, AC-907..AC-914 |

Proposed consolidation: V-5 replaces the existing V-1–V-5 executable rows only after the collection-only comparison and per-case coverage checks in T-25 prove that V-1–V-4's five targeted modules are included in full with identical case identities and no unexpected skips. Preserve the prior rows and outputs as historical provenance outside the executable Verification table; map every covered FR to V-5. If a specific case or assertion cannot be proven equivalent, keep only that uncovered check as a separate row and do not declare consolidation complete. The V-5 change requires R10 and fresh approval of the final table; it does not authorize any fabricated result. Focused commands in T-15–T-20 and T-24–T-25 are wave checks only; they do not become extra final verification rows. Each matrix cell executes V-5 exactly once. Local Windows results do not prove Ubuntu. No row is declared hermetic; no CI result is claimed.
