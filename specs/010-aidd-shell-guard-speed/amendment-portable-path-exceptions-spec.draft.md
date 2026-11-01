# DRAFT — 010 FR-1003 portable path exceptions

Status: DRAFT, NOT APPROVED. No guard implementation or spec approval is authorized by this file. Evidence: `tests/report_guard_portability.py` output, `%TEMP%/aidd-009-guard-linux.jsonl` and `%TEMP%/aidd-009-guard-windows.jsonl`; these are local, temporary artifacts. T-23 reports synthetic events, not real cross-platform filesystem operations. Old = pinned guard, current = guard at collection; both agree for each reported case, including messages. Each file has a non-JSON NOT-VERIFIED platform note after the JSON rows.

## Executive summary

- **Objective:** reconcile byte-identical legacy decisions with narrowly enumerated platform corrections while retaining guard security and all other baseline decisions/messages.
- **Scope:** four Linux event exceptions and separate foreign drive lexical classification; Windows decisions stay unchanged for the observed cases.
- **Cost:** not estimated; tasks and waves require a subsequent plan.
- **Risks:** an overly broad exception could allow protected writes or block unrelated files; prove boundaries and retain R6/R9.
- **Open decisions:** owner review of this exact exception list and scope; wording below is proposed, not approved.

## Scope

- **Included:** amend 010 FR-1003; authorize only the exact decision changes enumerated below, once separately reviewed; test POSIX case sensitivity, file classification and foreign drive tokens.
- **Excluded:** disabling R6/R9, changing unrelated decisions/messages, interpreting foreign paths as native local files or touching UNC shares. This draft changes neither 009 nor approved artifacts.

## Functional requirements (cite codes, don't redescribe the UI)

| FR-nnn | Requirement | Cites (SCREEN-XX-Fnn / CTL-nnn / API-nnn) |
|---|---|---|
| FR-1003 amendment (proposed) | Preserve the old allow/block decision AND exact message for every command/event except the four Linux outcomes below, with normal rules still applied. No general platform exemption. Native paths use realpath with symlink/junction containment; foreign Windows drive and UNC tokens are classified lexically without resolving a foreign share. | 010 FR-1003; 009 FR-917, FR-920, T-19, T-23 |

## Acceptance cases

| Case | Real data (id) | Expected | Edge? |
|---|---|---|---|
| Foreign Windows drive task, Bash redirect on Linux | T-23 `ci-drive-tasks`: `D:/proj/specs/F23-eDoc-POS/tasks.md` | old/current allow → desired deny under applicable protected-shell gate; treat as lexical Windows drive, not as proof of native file existence. | yes |
| POSIX case-distinct ordinary path, Write on Linux | T-23 `ci-native-case-distinct`: `<root>/.AIDD/Evidence/events.toon` | Treat `.AIDD/Evidence` as an ordinary case-distinct path, not the protected `.aidd/evidence`. The `.toon` file remains blocked by R6 while the target spec is unapproved; allow only when all applicable rules permit it. Protected lowercase native paths remain denied. | yes |
| Code classification, Write on Linux | T-23 `ci-cmakelists`: `<root>/src/CMakeLists.txt` | old/current allow → desired deny in the reported unapproved-spec fixture: classify CMakeLists.txt as source subject to R6, not an unconditional ban. | yes |
| Non-code markdown classification, Write on Linux | T-23 `ci-uppercase-markdown`: `<root>/docs/A.MD` | old/current deny → desired allow in the reported fixture: classify uppercase Markdown as non-code subject to other applicable rules, not an unconditional exemption for protected files. | yes |

**Separate lexical correction, not an extra full-gate exception:** on Linux, `ci-drive-review`, `ci-drive-backslash-review` and `drive-mixed-case` already deny at the full gate but both old/current `lexical` fields are false; desired protected-token classification is true. Preserve the full deny and its existing message where unchanged. `ci-drive-tasks` is the one observed full-gate allow→deny case and its lexical classification must also change false→true. Check protected `tasks.md`, `review.md`, mixed case/separators and suffix handling without network access. Do not infer broader observed decision deltas from these four examples.

**Baseline:** both Windows and Linux reports contain 16 JSON cases each; every observed old/current full decision and message is identical. All Windows desired outcomes match old/current. On Linux the 12 remaining full-gate decisions match desired and remain byte-identical; protected UNC, extended UNC, `.aidd` paths, parent traversal and stream cases stay denied, native unrelated and the reported native uppercase plan/tasks cases retain their observed allow. Results do not prove Windows junction behavior or every possible command.

## Verification

No tests run by drafting. After owner review and task approval, use T-18/T-19 existing focused Windows and Linux verification; explicitly check the four outcomes above, drive lexical classifications, the other 12 Linux and 16 Windows decisions/messages, R6/R9 security boundaries, native symlink/junction containment and unchanged equivalence corpus. Report unavailable native cases as not verified. Do not run multiple full suites for this document.
