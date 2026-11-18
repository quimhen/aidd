# Tasks — Read legacy amendment-NN-tasks.md without changing batch approval identity

Pending official unit approval. No legacy approval is replaced.

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Tracker ref | Status | Explicitly out of scope |
|---|---|---|---|---|---|---|
| T-921 | FR-980, FR-981, FR-982, FR-983 | `tests/test_amendment_file_layout.py` | LOGIC | | | unrelated source, gates, DB, network, installed skill |
| T-922 | FR-980, FR-981, FR-982, FR-983 | `skill/scripts/aidd_amendment_verify.py` | LOGIC | | | unrelated source, gates, DB, network, installed skill |
| T-923 | FR-980, FR-981, FR-982, FR-983 | `adapters/dot-aidd/scripts/aidd_amendment_verify.py`, `docs/aidd-amendment-file-layout.md` | LOGIC | | | unrelated source, gates, DB, network, installed skill |

### T-921

**Classify**
- Nature: REQUIREMENT
- Priority: 2
- Kind: LOGIC

**Estimate**
- Agent min: 8
- Human ref hours: 0.40
- Tokens (est): 15k
- Agent role: tests
- Model tier: medium
- Wave: 1

**Detail**
- Files to change: `tests/test_amendment_file_layout.py`
- Behaviour: Synthetic read-only roots: canonical tasks-amendment-06/6/006 behavior preserved; reverse amendment-06/6/006-tasks resolves only when canonical is absent; both forms with same bytes select canonical; differing bytes refuse ambiguity; unparseable/missing declares nothing and refuses. Compare historical base approval_hash before/after discovery and assert no new tasks-* file, rename, symlink, log/event or write. Full dry-run fixture confirms spec.md remains verification owner, not amendment spec or plan. No row skipped or external logs adopted. Coordinator captures RED first.
- Read first: unit plan.md, target functions resolved through native graph, and existing import/test fixture style. Do not widen unrelated reads.
- Verification: coordinator runs the applicable commands in unit spec.md once after freeze; a new behavior first requires genuine RED before the body. Builders only static checks.
- Do NOT: edit any file not named; modify approvals/events; execute DB or external services; hide failures or label AST success as runtime proof.
- Open questions: none.

### T-922

**Classify**
- Nature: REQUIREMENT
- Priority: 2
- Kind: LOGIC

**Estimate**
- Agent min: 10
- Human ref hours: 0.50
- Tokens (est): 25k
- Agent role: builder
- Model tier: medium
- Wave: 2

**Detail**
- Files to change: `skill/scripts/aidd_amendment_verify.py`
- Behaviour: Extend amendment_file(d,nn) discovery only. Enumerate current canonical names plus amendment-{NN/n/NNN}-tasks.md; preserve canonical precedence when bytes agree. If multiple supported candidates differ in bytes, raise ValueError with bounded filenames and no file body/secret. Return only an existing regular file contained in spec dir; refuse symlink escape. amendment_files error lists both supported layouts. Do NOT modify aidd_rules batch discovery, approval_hash, plan/prove/reuse policy, Verification selection, environment identity, gates or external-evidence adoption. Depends T-921 RED.
- Read first: unit plan.md, target functions resolved through native graph, and existing import/test fixture style. Do not widen unrelated reads.
- Verification: coordinator runs the applicable commands in unit spec.md once after freeze; a new behavior first requires genuine RED before the body. Builders only static checks.
- Do NOT: edit any file not named; modify approvals/events; execute DB or external services; hide failures or label AST success as runtime proof.
- Open questions: none.

### T-923

**Classify**
- Nature: REQUIREMENT
- Priority: 2
- Kind: LOGIC

**Estimate**
- Agent min: 4
- Human ref hours: 0.20
- Tokens (est): 10k
- Agent role: docs
- Model tier: medium
- Wave: 3

**Detail**
- Files to change: `adapters/dot-aidd/scripts/aidd_amendment_verify.py`, `docs/aidd-amendment-file-layout.md`
- Behaviour: Byte-sync mirror with repo tooling and document both accepted filenames. Explicitly state naming compatibility does not skip legacy rows or prove DB freshness. No rename/alias in B1, no installed update. Coordinator runs one shared mirror check. Depends T-922.
- Read first: unit plan.md, target functions resolved through native graph, and existing import/test fixture style. Do not widen unrelated reads.
- Verification: coordinator runs the applicable commands in unit spec.md once after freeze; a new behavior first requires genuine RED before the body. Builders only static checks.
- Do NOT: edit any file not named; modify approvals/events; execute DB or external services; hide failures or label AST success as runtime proof.
- Open questions: none.

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 1 | T-921 | tests | 8 | 15 | 0.40 |
| 2 | T-922 | builder | 10 | 25 | 0.50 |
| 3 | T-923 | docs | 4 | 10 | 0.20 |

Total agent time (critical path): 22 min
Total tokens (k): 50

## Execution contract

One file owner per lane. Native AIDD graphs first, bounded reads and outputs. Mechanical operations use mapping/dry-run/apply/post-check. Builders run static checks only; coordinator executes RED before each body, then the union of checks once after source freeze. Preserve failures and exact inputs; no invented PASS or consent. No Graphify, database, Docker, external API, installed-skill update or B1SyncLink write. Do NOT modify approval/event logs, relax gates, change unrelated local edits, reinterpret presence as behavior, or reuse a DB result from container identity alone. Final full verification and required perf/audit of the host spec remain applicable at official close.

## Approval gate

Pending owner consent through the official unit review package. This file is not an approval. Historical base approval remains independent and unchanged. No production implementation before the exact unit is approved.
