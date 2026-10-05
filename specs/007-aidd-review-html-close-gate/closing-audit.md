CLOSING AUDIT [domains: security, functional, performance] [tasks:73c2d22c]

# Closing audit (T-10): spec 007, review-driven approval, per-spec R6 and the executed close gate

Auditor: one independent closing auditor (read-only, did not implement anything). Date: 2026-10-05. Python 3.12.10, Windows 11.
Scope: the working tree on `feat/004-aidd-graph-first` (`git diff --stat`: 36 files, +7035/-229, plus new `aidd_review.py`, `review.html`, two test files and `tests/e2e_review_roundtrip.py`).

Where I started:
- `python skill/scripts/check_spec.py specs/007-...`: exit 0. It printed the new banner `STRUCTURAL CHECK ONLY - nothing was executed`.
- `find_spec.py --code FR-201..FR-209`: every FR is linked to its tasks. There are 200 `aidd:FR-20n` markers in 27 files.
- Mirrors: `aidd_evidence`, `aidd_rules`, `aidd_status`, `check_spec`, `aidd_review`, `AIDD.md`, `templates/spec.md`, `templates/qa-audit.md` and `templates/review.html` are byte-identical to their `adapters/dot-aidd` copies.
- Full suite (V-1), `python -m unittest discover -s tests`: **1500 tests, OK**. See `evidence/full-suite.txt`.
- V-6, `python tests/e2e_review_roundtrip.py`: prints `ROUNDTRIP OK`.

How the ACs were run: every case ran in a SCRATCH project, using `gate_fixtures.Base` with `AIDD_EVIDENCE_DIR` pointing to a temp directory and `AIDD_TESTING=1`. The real evidence log was never used. The hooks and the CLI ran as real subprocesses. The harness is saved as `evidence/harness-audit007.py`, and each case wrote its own transcript to `evidence/ac-<n>.txt`.

## Domain checklist

| Domain | Result | Evidence |
|---|---|---|
| security | 1 medium and 1 low finding (below). Consent as the trust root holds: a forged, complete review.md approves nothing through the CLI or the hook | ac-205.txt, ac-207.txt, probe-d8-nonnumeric.txt, xss-static.txt |
| functional | 15 of 16 ACs PASS. AC-215 FAIL on one sub-case, and AC-202(2) can only be reproduced with a mock (low finding) | ac-201.txt .. ac-218.txt |
| performance | 1 medium and 1 low finding. Hook hot paths stay well under their timeouts | perf.txt, perf-status-fingerprint.txt |

## Per-AC results

| AC | Result | Evidence | Note |
|---|---|---|---|
| AC-201 | PASS | evidence/ac-201.txt | Once F23 is approved and its approval recorded, a code write is allowed even though 13 specs are PENDING. With F23 PENDING there is ONE message naming F23, "pointer" and `aidd review` / `aidd rules approve` |
| AC-202 | PASS (note) | evidence/ac-202.txt | (1) F23 is inferred and F28 is never chosen; (3) F99-none is treated as unset; activate plus a `gate_pointer` event works; R9 blocks agent writes to `gate_spec`/`active_spec`; a spec-file edit moves `active_spec` only. (2) "ambiguous" can only be reproduced with a mocked `open_specs`; see F-4 |
| AC-205 | PASS | evidence/ac-205.txt | With only review.md: refused. "do not approve <tag>" and a prompt with the tag but no approve word do not count. `approve <tag>` gives `review+prompt`; the tagged answer gives `review+answer`; an injected TTY gives `review+tty`. Every one carries `gate:2`, `consent_ts`, `verify_hash` and `review_sha1`, activates the spec and prints the notes |
| AC-206 | PASS | evidence/ac-206.txt | Title edit: refused naming both hashes. Status-only edit: still valid. After approve: `--check` exits 0 and the page is "unchanged". Digest drift: refused |
| AC-207 | PASS | evidence/ac-207.txt | 105 file-tool probes and 30 Bash probes, numeric and non-numeric ids, relative and absolute paths, ADS forms and trailing dots: all blocked. `cat` and `aidd review [--check]` are allowed. A hand-built file mints nothing (CLI and hook route). Missing key and "older than review.html" are named. Lexical bypasses are listed under F-3 |
| AC-208 | PASS | evidence/ac-208.txt | A legacy approved event (no `gate`) closes through per-domain auditors, with no verify and no review |
| AC-209 | PASS | evidence/ac-209.txt | No verify_run means refused. After verify it passes; a later code_edit makes it stale; a re-run fixes it; editing the evidence file (sha1) or the table (verify_hash) is refused |
| AC-210 | PASS | evidence/ac-210.txt | A full header covers every domain. Not counted: a header naming only security, haiku, `phase=pre`, a stale tasks tag, a wrong verify tag, `result_chars` of 20 or missing, the header not on the first line, and an auditor older than `verify_run`. Per-domain auditors still cover. qa-audit rows and the tool_use_id are enforced |
| AC-211 | PASS | evidence/ac-211.txt | Advisory allows a missing Mapper and the post-rebuild write; strict blocks both. A missing find_spec, a `[Proposed` row or a fabricated quote blocks in both modes |
| AC-212 | PASS | evidence/ac-212.txt | `--refresh` shows branch, commit, dirty/untracked, untracked files under specs/F23, "14 pending", review/verification, pointer and effective AIDD_RULES. `--json` includes `derived`. Outside git it prints `git: unavailable` with exit 0 |
| AC-213 | PASS | evidence/ac-213.txt | specs/006 gets the banner (exit 0). A spec with a passing verify_run gets the execution-evidence line |
| AC-214 | PASS | evidence/ac-214.txt | warn mode records `rules_override`. off mode records it for session_start and stop_gate. Status shows "warn overrides: N" and "AIDD_RULES=off (rules disabled)". With no project root nothing fails |
| AC-215 | **FAIL** (1 sub-case) | evidence/ac-215.txt | These hold: F23 alone blocks with the three steps; the F21 reminder appears once; after the pointer moves to F22 the reminder lists F21 and F23; status shows `F23 -> F22`; AIDD_STOP_BLOCKS works. This fails: "no pointer + several open specs: R8 blocks none". Stop blocks the inferred F23 (exit 2); see F-4 |
| AC-216 | PASS | evidence/ac-216.txt | (a) css/json/web.config are recorded and stamped. (b) An edit after `started` makes it stale. (c) A tree change with no code_edit makes it stale (mtime fallback and git). (d) An untracked generated file gives `stable=false` and close is refused; the second run is stable |
| AC-217 | PASS | evidence/ac-217.txt | A 459,544-char tasks.md: refused naming the file and size, nothing written; `source too large`; the answer-only route approves (`source: answer`, gate 2) |
| AC-218 | PASS | evidence/ac-218.txt | All six rows are rejected with reasons; the extra probes (`-Bc`, `python3.11 -c`, `bash -lc`, `--eval=`, `pwsh -Command`, `cmd.exe /C`, `python -`, `py -3 -c`) are rejected too. `discover -s <empty>` is accepted at approval, then `aidd verify` marks it failed (exit 5 on 3.12; the evidence also matches `zero tests ran`). Verification is rendered with `data-mandatory`, and the JS skips it |

AC-203 and AC-204 belong to T-11 (real browser). A static XSS sweep of a generated page found nothing (evidence/xss-static.txt): only the page's own two script tags, a CSP hash equal to the sha256 of `#aidd-js`, no javascript:/data:/`//`/`..` in any href or src, no live `on*=` or `style=` attribute, the JSON blob parses with no raw `<`, and https links carry `rel="noopener noreferrer"`.

## Confirmed findings (ranked)

### F-1 MEDIUM security: the Bash guard for spec artifacts misses non-numeric ids (absolute path) and the relative form after `cd`
- Where: `skill/hooks/rule_gate.py:951-968` (`_specs_tok`). A path counts as a specs token only when `specs` is segment 0 or the next segment is `NNN-...`. The 007 extension covers only `review.md`/`review.html` leaves.
- Verified (evidence/probe-d8-nonnumeric.txt): with `002-aidd-hard-rules` these are blocked. With `F23-eDoc-POS`, `echo x > D:/proj/specs/F23-eDoc-POS/tasks.md` and `cp /tmp/t.md D:/proj/specs/F23-eDoc-POS/plan.md` are allowed (rc 0). `cd specs/<any-id> && echo x > spec.md` is allowed for numeric ids too.
- Impact: on the real project shape (b1SycLink ids), the agent can rewrite tasks.md, plan.md or spec.md through the shell. That skips the R1/R2/R5 content rules and leaves no `spec_edit` evidence. Approval forging is still stopped: the code gate needs a hook-recorded `approved` event for the current hash. This gap predates 007, but spec.md "Evidence from real use" requires every path-shape guard to handle such ids.
- Fix: in `_specs_tok`, treat any `specs/<segment>/<leaf in SPEC_ARTIFACT_NAMES or review files>` as a specs token for any id. Extend the text-level rule (`_review_write`) to the spec artifact names when a redirect or writer verb appears after `cd specs/<x>`.

### F-2 MEDIUM performance: `worktree_fingerprint` is recomputed for every spec in `aidd status` (twice per spec with `--refresh`)
- Where: `skill/scripts/aidd_rules.py:2443-2451` (`_run_problems`, reached through `verification_state`), called per spec from `skill/scripts/aidd_status.py:388` (`_build_status`) and again from `:796` (`_derived_facts`). Nothing is memoised.
- Verified (evidence/perf-status-fingerprint.txt): with 6 specs that have a verify_run, plain `aidd status` makes 6 fingerprint calls and `--refresh` makes 12. One fingerprint takes 899 ms on this repo (git). On a large non-git tree it takes 8,001 ms and returns None (evidence/perf.txt).
- Impact: once b1SycLink's 14 open specs have been verified, plain `aidd status` costs about 13 s in a git repo and about 112 s outside git; `--refresh` doubles that. It is not in a hook, but status is the "honest status" command of FR-208.
- Fix: compute the fingerprint once per root per process (a module-level cache keyed by root with a short TTL), or pass a precomputed `fingerprint` into `verification_state`.

### F-3 LOW security: the review-file Bash rule is lexical and is bypassed by globs and quote splitting after `cd`
- Where: `skill/hooks/rule_gate.py:971` (`_REVIEW_NAME_RE` runs on the raw command text) and `:982-1004`.
- Verified (evidence/ac-207.txt, "LEXICAL BYPASS PROBES"): after `cd specs/F23-eDoc-POS`, these are all allowed: `rm review.*`, `rm revie?.html`, `echo x > rev''iew.md`, `echo x > "review".md`.
- Impact: deleting review.html sends both the hook and the CLI back to the answer-only route. That route still needs the owner's tagged answer, and the agent could get the same effect by never generating a page. A forged review.md still mints nothing (verified). The design accepts a lexical guard, but AC-207 promises `rm .../review.html` is blocked.
- Fix: strip quotes before the regex, fnmatch glob tokens against `review.md`/`review.html`, and record a protected `review_generated{spec, digest}` event so a deleted page does not reopen the answer route.

### F-4 LOW functional: the `ambiguous` gate target can never happen with real events; AC-215 (no pointer) and AC-202(2) disagree with FR-201
- Where: `skill/scripts/aidd_evidence.py:1553-1564`. `open_specs` only returns specs that have a plan.md/tasks.md `spec_edit`, so the inference always finds a candidate. The tests reach "ambiguous" only by patching (`tests/test_evidence.py:1224`, `tests/test_stop_gate.py:272`).
- Verified: with real events, AC-215 "no pointer + several open specs: R8 blocks none" fails (Stop exit 2 on the inferred F23). A probe in ac-202.txt shows that with no pointer, one hash-neutral tasks.md edit of an approved spec (for example a Status write-back) moves the inferred target to that spec and unblocks code writes. No `gate_pointer` event is recorded (rc 2 before, rc 0 after, 0 events).
- Fix: either change AC-202(2) and AC-215 to the inferred semantics, or make inference stricter. Examples: ignore hash-neutral tasks.md edits (the recorder already stores `hash`); infer only from edits newer than the spec's last approval. Also log inferred-target changes.

### F-5 LOW performance: stop_gate is about 46% slower per Stop
- Measured on a synthetic log (27 specs, 5,000 events, warn mode): stop_gate median 237 ms at HEAD and 345 ms on the working tree. mark_code_edit went from 144 to 162 ms (+12%). The rule_gate code write takes 251 ms median (HEAD 436 ms, but that baseline is not strictly comparable). `gate_target_specs` costs 36 ms with the pointer and 67 ms when it infers. `generate` on a spec sized like F13 (69 KB tasks.md, 155 keys) takes 77 ms the first time and 27 ms when idempotent; `review_state` takes 12 ms. All of these are far below the 15 s hook timeout.
- Cause: the project log is parsed several times per Stop (`gate_target_specs` twice, plus `_approved_at`, `code_edits_for` and `count` for each spec).
- Fix (optional): parse the project log once per hook run and pass the events to the helpers.

## Not findings (checked and holding)
- Consent is the trust root. A complete review.md without a consent act is refused by the CLI and by the hook route. The TTY route needs both stdin and stdout to be TTYs (the agent's Bash tool has neither); the pty residual is documented. Prompt consent rejects negations, untagged prompts, prompts with no approve word and prompts older than review.md.
- The verification lint rejects every AC-218 row and 8 more bypass shapes. `cmd_verify` sanitises the evidence file id (`[A-Za-z0-9_-]`). Evidence sha1, verify_hash binding and fingerprint staleness are all enforced.
- Closing-auditor spoofing: a header-only dispatch or a short report does not count. The residual (an agent can tell the subagent to write a long report) is documented in spec.md.
- `.aidd/gate_spec` is protected by R9 (Write, Edit and Bash variants all blocked). `activate_spec` refuses unknown or closed ids and sanitises separators.

## Delta audit

Auditor: one independent delta auditor. I implemented nothing. I was read-only except for this section and the evidence files listed below. Date: 2026-10-05. Python 3.12.10, Windows 11.

How the probes ran: every probe used a SCRATCH project (`gate_fixtures.Base`: a temp project, `AIDD_EVIDENCE_DIR` in a temp directory, `AIDD_TESTING=1`). `AIDD_RULES` was removed from the child environment, so the strict default applied. Hooks and the CLI ran as real subprocesses. For F-4 the real `mark_code_edit.py` PostToolUse hook recorded the spec edits, so they carry the real `hash`.
- Harnesses: `evidence/harness-delta007.py` (it reuses the helpers in `harness-audit007.py`) and `evidence/harness-delta-fp.py`.
- Transcripts: `evidence/delta-f1.txt`, `delta-f2.txt`, `delta-f3.txt`, `delta-f4.txt` and `delta-false-positives.txt`.

Baseline after the fixes:
- Full suite, `python -m unittest discover -s tests`: **1518 tests, OK** (`evidence/delta-full-suite.txt`).
- `python tests/e2e_review_roundtrip.py` prints `ROUNDTRIP OK`.
- The nine `skill/` and `adapters/dot-aidd/` mirrors are still byte-identical.

| Finding | Result | Evidence | Note |
|---|---|---|---|
| F-1 | **PASS** for every shape F-1 names. Residual R-1 below | delta-f1.txt | 360 probes, all rc 2: 4 ids (`002-aidd-hard-rules`, `F23-eDoc-POS`, `F13-eDoc-Emission-Engine`, `login_v2`) x 5 leaves (tasks.md, plan.md, spec.md, review.md, review.html) x 18 shapes. The shapes: absolute `/` and `\` paths, `>` and `>>`, cp, mv, rm, `sed -i`, Set-Content -Path, tee, a relative path after `cd`, `cd .../` then `./leaf`, an absolute `cd`, pushd, Set-Location, chained `cd specs && cd <id>`, `python -c open(...,'w')` after cd, and a hook cwd inside `specs/<id>`. The controls stay allowed: cat, ls, git diff, writes to src/ or notes.txt, and `aidd status` |
| F-3 | **PASS** for globs, braces and quote splitting with `'`, `"` or backtick. Residual R-2 below | delta-f3.txt | 27 probes blocked: `rm review.*`, `revie?.html`, `review.{md,html}`, `[r]eview.html`, `?eview.html`, `*.html`, `*`, `rev*`, `r*.md`, `rev''iew.md`, `"review".md`, `"rev"iew.html`, the backtick-split name, Remove-Item, `rm --`, mv, cp, absolute and `specs/*/review.*` globs, and four of these run from a hook cwd inside the spec. With the hook cwd at a normal project root these controls stay allowed: `rm build/*`, `rm src/*.html`, `rm -rf dist/*.md`, `cat review.md`, `ls *` inside the spec, and `aidd review [--check]`. The optional `review_generated` event from the F-3 fix was not implemented. As before, deleting review.html by a route the guard misses sends the CLI back to the answer-only route |
| F-2 | **PASS** | delta-f2.txt | With 6 verified specs, `worktree_fingerprint` now runs **once** per command: plain `aidd status`, `--refresh`, `--refresh --json` and a named status (it was 6 and 12). Freshness: right after verify, all 6 specs read `Verification: passed`. After an out-of-band tree change (a new file, no code_edit event), the next plain and `--refresh` runs show all 6 as `stale`, which matches the unmemoised `verification_state`. `FingerprintOnce` with a fake clock reuses a cached value only when it is at least as new as the bound (verify_run ts, started or last code edit) and inside the 30 s ttl. A newer bound, an expired ttl or an unreadable bound all recompute (4 calls for 5 lookups). `cmd_verify` still computes its start and end fingerprints fresh |
| F-4 | **PASS** for the hash-neutral tasks.md case | delta-f4.txt | Setup: no pointer, F21 approved, F23 pending with the newest tasks.md edit. The target is `F23 inferred` and a code write gets rc 2. Then a tasks.md edit of F21 that keeps `approval_hash` (recorded hash `e9a09d9bac61`, equal to the approved hash) leaves the target on F23, and the code write still gets rc 2. A hash-changing F21 edit still moves the target, so inference is kept, and it logs `gate_pointer{spec: F21, prev: F23, by: inferred}`. Repeated calls with no change add no duplicate event. Not fixed: AC-202(2) and AC-215 ("no pointer + several open specs: R8 blocks none") still describe the `ambiguous` semantics, which real events cannot reach. The spec.md text is unchanged, so this documentation mismatch from F-4 stays open (see R-3) |

### New regression (reproduced)

**N-1 MEDIUM functional (false positives): the new `cwd_specs` rule from the F-1/F-3 fixes treats any absolute cwd with a `specs` segment as being inside a spec.** That includes a project whose root sits under a folder named `specs`, and test folders such as `tests/specs`.
- Where: `skill/hooks/rule_gate.py:1304` runs `in_specs = _path_in_specs(cwd)` on the absolute hook cwd, not on the path relative to the project root. At `:1200-1203`, a relative `cd ..` never clears `cwd_specs`. The flag feeds `_specs_tok` (`:991`) and the glob branch of `_names_review` (`:1038`).
- Verified (evidence/delta-false-positives.txt, strict mode, working tree compared with `git archive HEAD`): with the hook cwd at a project root `<tmp>/specs/proj`, the working tree **blocks (rc 2)** `rm *`, `rm build/*`, `rm -rf dist/*`, `echo x > plan.md` and `echo "# notes" > spec.md`. HEAD allows all five (rc 0). The same happens:
  - from `tests/specs`: `rm *` and `echo x > spec.md`;
  - for `cd tests/specs && rm *`;
  - after leaving a spec with a relative cd: `cd specs/F23-eDoc-POS && cd ../.. && rm *` and `... && cd ../../src && echo x > plan.md`.
- Impact: in a strict project whose path contains a `specs` folder, the hook refuses every glob delete with the R9 message. It also refuses every write to a file named like a spec artifact, anywhere in the tree. In this user's setup, `AIDD_RULES=warn` turns each of these into a warning instead. This is over-blocking only, not a security hole.
- Fix: compute `in_specs` from the cwd relative to the project root, so `specs` must be segment 0 of `rel_to_root(cwd)`. Update `cwd_specs` on a relative `cd` by resolving the target against the tracked cwd, or clear it on any relative cd that does not stay under `specs/`.

### Residuals (not regressions: pre-existing, or accepted lexical limits)

**R-1 LOW security (F-1 class, non-numeric ids).** A copy or move whose destination is the spec DIRECTORY is still allowed for non-numeric ids, while numeric ids are blocked.
- `cp /tmp/tasks.md <root>/specs/F23-eDoc-POS/` and `mv ... <root>/specs/F23-eDoc-POS/` get rc 0, but `cp /tmp/tasks.md <root>/specs/002-aidd-hard-rules/` gets rc 2.
- `cd specs/F23-eDoc-POS && cp /tmp/tasks.md .` gets rc 0.
- These lexical shapes also get through:
  - `cd sp*/F23-eDoc-POS && echo x > tasks.md`;
  - `cd specs/F23-eDoc-POS && echo x > tas*.md`. Git bash expands a glob in a redirect when it matches one file, so this really overwrites tasks.md;
  - `D=specs/F23-eDoc-POS; echo x > $D/tasks.md`.
- Approval forging is still stopped, because the code gate needs a hook-recorded `approved` event.
- Fix: in `_specs_tok`, also count a copy or move destination that is `specs/<segment>` (or `.` when `cwd_specs` is set) for any id. Match glob leaves against the artifact names, as `_names_review` already does.

**R-2 LOW security (F-3 class).** `_unquote` does not remove bash backslash escapes.
- `cd specs/F23-eDoc-POS && rm rev\iew.html` is allowed (rc 0), and Git bash does delete review.html with it.
- `X=review; rm $X.html` is allowed. This is variable indirection, an accepted lexical limit.
- Fix: in a POSIX shell context, drop a backslash that comes before a non-separator character before matching the name. Today the `\` to `/` normalisation turns `rev\iew.html` into `rev/iew.html`, so the name no longer matches.

**R-3 LOW functional (what is left of F-4).** A `plan.md` edit of an APPROVED spec still moves the inferred target to that spec and unblocks code writes.
- Probe: with no pointer and F23 pending with the newest edit, a code write gets rc 2. After a one-line plan.md edit of approved F21, the target is `F21 inferred` and the code write gets rc 0.
- The move is now logged as `gate_pointer{by: inferred}`, so it shows in `aidd status`.
- The AC-202(2) and AC-215 (no pointer) text still disagrees with the inferred semantics.
