# Draft plan — 010 portable path exceptions

DRAFT / NOT APPROVED. Input: `amendment-portable-path-exceptions-spec.draft.md`; evidence T-23 is local, not approval. Do not implement until owner has reviewed the exact exceptions and approved the resulting tasks. No UI or database work.

## Naming & File Contract
| Item | Convention |
|---|---|
| Python module, functions and variables | existing snake_case; keep current helper signatures |
| Tests | existing unittest classes and `test_...` methods |
| Mirror | `skill/hooks/rule_gate.py` → `adapters/dot-aidd/hooks/rule_gate.py`, byte-identical |

## Scope and behavior
The only proposed old→new full gate changes are the four Linux T-23 cases: drive `tasks.md` allow→deny; case-distinct native `.AIDD/Evidence/events.toon` deny→allow under other applicable guards; `CMakeLists.txt` allow→deny under R6; `docs/A.MD` deny→allow under other applicable guards. Review the detailed specification before approving; neither allow is an exemption from protected paths. Drive `review.md` forms remain deny with same message but gain protected lexical classification. Other decisions and messages remain unchanged. Never access a real UNC share; lexical analysis must not assert foreign tokens refer to native objects.

## Responsibilities and dependencies
Wave 1 test owner adds narrowly specified regression tests in `tests/test_cross_platform_paths.py`; wave 2 guard owner changes `skill/hooks/rule_gate.py` and mirrors via a script, retaining existing names `_specs_tok`, `_abs_path_raw`, `_locate`. Do not edit `skill/scripts/aidd_evidence.py`: T-19 already conditions such edits on need, and necessity is not established; stop and report if necessary. Coordinate with 009 T-18/T-19 and spec 007 before any shared change. A fresh independent auditor reviews the resulting delta once after the coordinated verification.

## Verification plan
The owner/orchestrator runs one coordinated targeted discovery on Windows and Linux with `python -m unittest discover -s tests -p test_cross_platform_paths.py -v`, `python -m unittest discover -s tests -p test_rule_gate.py -v`, `python -m unittest discover -s tests -p test_rule_gate_shell_speed.py -v`, `python -m unittest discover -s tests -p test_dot_aidd_mirror.py -v`; execute each module once per verified environment, serially. Compare the pinned old guard for all unchanged corpus cases, including decisions and messages; the four approved exceptions are verified independently and must not disable the equivalence corpus. Count missing baseline/loader and platform skips as not verified, not success. Record outputs and provenance without secrets; no full-suite rerun in this scope unless a distinct final gate requires it, and reuse eligible prior evidence under AIDD rules.
