# QA Audit — AIDD Antigravity adapter (spec 011)

**Audited by:** independent auditors that did not implement it. Pre-build coherence audit `a5157d467a8161a50` (FIX FIRST: 7 findings, all applied: the CLI `choices`, the matcher registered as `*`, reparse-tag link detection, D5 through the registered command, four places in `rule_gate`, ...). Closing: security `ac25f841eabd9ceda` (PASS WITH EXCEPTIONS) and functional `aae4439238140f9d1` (PASS WITH EXCEPTIONS: one stale-evidence finding, fixed).

## Verification summary
Verification: `aidd verify specs/011-aidd-antigravity-adapter` PASSED 4/4 rows (verify hash 0ea12d88; V-1 `test_host_gates.py`, V-2 `test_host_install.py` + `test_host_doctor.py`, V-3 `test_dot_aidd_mirror.py` + `test_rule_gate.py`, V-4 the full suite once: 0 failed). Evidence: evidence/verify-V-1.txt to evidence/verify-V-4.txt and evidence/verify-summary.md, which also records the REAL `agy` 1.3.5 runs (always-on rule injects the core; code write denied; `.agents/hooks.json` overwrite denied; `--dangerously-skip-permissions` does not skip the hooks; a planted `python.bat` did not replace the interpreter) and the b1SycLink replacement of the symlink.

## Domain checklist (filled from the single closing auditor's report)
The closing auditors' first line was `CLOSING AUDIT [domains: functional, security] [tasks:43a9c2bd] [verify:0ea12d88]`.

Closing auditor id: ac25f841eabd9ceda

| Domain | Covered by closing auditor? | Result | Key findings |
|---|---|---|---|
| security | yes | PARTIAL | 18 installer link cases (junction, directory and file symlinks at `.agents`, `.agents/skills/aidd`, `.agents/rules`, `.agents/hooks.json`, dangling) with and without `--force`: the target was never touched and only the link was removed; 33 adapter payloads (path forms, case, `::$DATA`, `\\?\`, relative path, hostile chunks, 20 MB content, 200 MB stdin) all answered one JSON object with exit 0 and every `.agents/hooks.json` write was denied; templates contain nothing that weakens the gate; D5 writes only inside its temp folder; mirrors byte-identical. Open as exceptions: JSON nested deeper than about 1,500 levels answers allow (needs the host to forward attacker-chosen fields), the `.agents/plugins/<name>/hooks.json` path is unprotected and undocumented by the host, a planted `python.bat` hijack was tested with the real host and NOT reproduced (other executable types and the app/IDE untested), a hard link planted at `.agents/rules/aidd.md` is not detected, a non-string or relative `TargetFile` without `workspacePaths` is allowed, the gate file being skipped under a linked `.agents` still exits 0 |
| functional | yes | PASS | FR-1101..FR-1108 and AC-1101..AC-1107 map to test classes (`TestAgy*`, `TestAntigravityInstall`, `TestSymlinkSafety`, `TestAntigravityDoctor`, `TestAntigravityTemplatesFR1105`) or to real runs; V-1 54, V-2 51, V-3 273 passed and V-4 0 failed; mirrors identical; docs agree with the verified facts and list the unverified ones; existing hosts unchanged; the b1SycLink doctor evidence was stale (CORE.md edited after the install): re-installed, PASS D1 to D5 for the three hosts |

## Mapping ledger
| Code | Status | Evidence (file/class/resource id) | PR/Spec ref | Screenshot diff done? |
|---|---|---|---|---|
| FR-1101, FR-1102 | ✅ IMPLEMENTED | skill/hooks/host_adapter.py (`_norm_antigravity`, `run_antigravity`); tests/test_host_gates.py `TestAgy*`; real `agy` denial | spec 011 T-01, T-06 | n/a |
| FR-1103, FR-1104 | ✅ IMPLEMENTED | skill/scripts/install_host.py (`install_antigravity`, `_guard_links`, `_remove_link`, `is_link`); tests/test_host_install.py | spec 011 T-02, T-07 | n/a |
| FR-1105 | ✅ IMPLEMENTED | skill/scripts/aidd_doctor.py (antigravity D1-D7); tests/test_host_doctor.py | spec 011 T-03, T-07 | n/a |
| FR-1106 | ✅ IMPLEMENTED | skill/hooks/rule_gate.py (`.agents/hooks.json` in four places); tests/test_host_gates.py; real `agy` overwrite denied | spec 011 T-04, T-06 | n/a |
| FR-1107 | ✅ IMPLEMENTED | adapters/README.md Tier 3b, adapters/dot-aidd/CORE.md, skill/SKILL.md | spec 011 T-09 | n/a |
| FR-1108 | ✅ IMPLEMENTED | b1SycLink: symlink replaced by a real folder, repo `skill/` fingerprint unchanged, doctor PASS D1-D5 | spec 011 T-10 | n/a |

## Device preflight
Preflight: not applicable (no device); `agy` 1.3.5 CLI was available and authenticated on this machine.

## Execution evidence
No SCREEN-nn, API-nnn or -Fnn code is claimed ✅; the rows above are backed by executed test runs (evidence/verify-V-*.txt) and by real `agy` runs recorded in evidence/verify-summary.md.

| Code | Kind | Evidence | Verified by |
|---|---|---|---|

## Bug reports
| # | Code | Symptom | Root cause | Fix | Pattern sweep |
|---|---|---|---|---|---|

## Resilience check (per code that crosses a boundary — network, DB, disk, external API, hardware)
| Code | Timeout set? | Retry/backoff? | Graceful degradation? | Recoverable trace on failure (where)? |
|---|---|---|---|---|
| host_adapter.py antigravity (spawns rule_gate, mark_code_edit) | yes, 15 s / 10 s (host default 30 s) | no | gate timeout answers deny (fail-closed); a crash or bad stdin answers allow with a hook error | `hook_error` in the evidence log |
| install_host.py (file copy, JSON merge, link removal) | n/a | no | a corrupt JSON file is skipped, never overwritten; a link is skipped without `--force` | per-file `written/unchanged/skipped` report with the link target |

## Performance & Best Practices check (Performance & Best Practices Auditor — applies to any code touched, every convergence)
| File/class | OOP/SOLID verified in code? | Interfaces used at real boundaries? | Locking/isolation deliberate for the engine? | Connection pooling verified (not just declared)? | No N+1 / unbatched loop? | No blocking call on hot path? |
|---|---|---|---|---|---|---|
| host_adapter.py, install_host.py, aidd_doctor.py | yes | yes (stdin JSON, stdout decision, exit code) | n/a | n/a | yes | partial: one extra Python process per gated call and the gate spawn, as on the other hosts; a 200 MB stdin answered in 1.9 s (security probe) |

## Revision log (append, never overwrite)
```
Rev 1 (2026-10-14) — 4/4 verification rows, 10/10 tasks; real agy runs and the b1SycLink replacement recorded; open exceptions below
```

## Open exceptions (rows left unresolved on purpose)
| Code | Reason | Approved by |
|---|---|---|
| Y1 | JSON nested deeper than about 1,500 levels in the hook stdin makes the adapter answer allow (RecursionError becomes `{}`); only reachable if the host forwards attacker-chosen extra fields (not verified); fix: answer deny on a parse failure of non-empty stdin in `pre` | pending owner at close |
| Y2 | `.agents/plugins/<name>/hooks.json` is not protected and whether the CLI loads project plugin hooks (and how decisions from several hooks combine) is not verified; the user-level `~/.gemini/config/hooks.json` is not protected either (documented) | pending owner at close |
| Y3 | interpreter hijack through the hook cwd: a planted `.agents/python.bat` did NOT replace `python` with agy 1.3.5 (tested for real); `.cmd`, `.exe`, `.com`, the app and the IDE were not tried; mitigations not done: an absolute interpreter path at install time, or protecting `.agents/python.*` and `.agents/*.{bat,cmd,exe,com}` | pending owner at close |
| Y4 | a HARD link planted as `.agents/rules/aidd.md` is not detected by the installer (an owner-run `--force` would overwrite the linked file with the template text); fix: write through a temp file and `os.replace`, or skip when `st_nlink > 1` | pending owner at close |
| Y5 | a non-string or relative `TargetFile` with no `workspacePaths` is allowed by the adapter; with `.agents` linked and no `--force` the gate registration is skipped but the install exits 0 (doctor D4 catches it) | pending owner at close |
| Y6 | not verified with the real host: the Antigravity app and IDE flavours, `multi_replace_file_content` arguments, `replace_file_content` and `run_command` denials through a real run (unit tests with the real captured payloads cover them), exit-code and crash semantics of the host (undocumented) | pending owner at close |
| Y7 | a file symlink to a protected file is not blocked by the shell guard (pre-existing gap X1 of spec 010, unchanged here) | pending owner at close |
