# R5 independent delta review — Graph V5 generation migration

**Verdict: PASS for the final revised adoption plan [tasks:6e7dec92].** Owner: Julio. Final task hash supplied by Root:6e7dec9276b7. Final package context supplied by Root:67358f9516848b9b23dd8d030a2367b98f79f646f464c98ff7a0197aefcb7f5b. This supersedes the earlier planning verdict only for the expanded proposal; the original R5 report remains preserved. No current implementation, execution, owner consent or publication PASS is implied.

## Reviewed delta

The added FR-379 correctly closes two different legacy-state paths that the earlier no-filters-only prototype cannot repair by itself:

1. Existing code_graph._cache_files checks only schema/extractor identity before allowing equal-hash AST reuse. Advancing EXTRACTOR_VERSION3 to4 while retaining SCHEMA_VERSION1 rejects all legacy extractor3/missing-generation parse-cache entries, including the poisoned case where old ASTA carries future rawB's hash. New generation4 entries can still reuse normally.
2. Existing aidd_graphs._inputs_hashes hashes watched path/hash bytes without producer generation. Salting only explicit builtin:code entries with the canonical producer's schema/extractor identity changes old freshness stamps even when producer code lies outside the consumer's watch. Unavailable/invalid generation omits the aggregate rather than inventing fresh identity. Existing status then remains uncertain/stale; unrelated custom/non-code providers retain their old hash bytes and behavior.

The proposed helper loads the existing canonical sibling module via _module, validates positive integer constants and returns a deterministic ASCII generation token. It does not use4b EVIDENCE_ALGORITHM or introduce a new graph schema/provider. Implementation must treat malformed generation as unavailable, including noninteger values; no inferred/default producer version is authorized.

## Task consistency and verification

- The three sequential tasks now total28 minutes/45k tokens, matching their individual estimates. T-951 owns the existing test module and adds both named regression scenarios before generation changes. T-952 owns both production modules and their canonical mirrors. T-953 owns frozen execution/context evidence and later independent audits. One source owner/static-only builders and one Root runtime verifier remain explicit.
- The historical2d9eaca source is correctly described as the starting no-filters/extractor3 prototype, not the final migrated hash. Fresh final source hashes are required. The guarded old source, historical prototype/test and five4b dependency pins remain the explicit adoption prerequisites. Final context includes both production modules, both mirrors and the expanded test module through actual official transitive closure, rather than a hand-invented context digest.
- The poison test is meaningful: synthesize legacy ASTA/hashB/extractor3, switch actual source toB, use actual raw hashing, then require B-only graph facts, parsed1/reused0/dirtyTrue/extractor4. The immediate unchanged call must retain current-generation reuse. Limited patched hashing is confined to constructing the historical poisoned fixture; the two original filter regressions continue exercising actual Git.
- The freshness test holds watched bytes/hash constant, excludes producer code from watch, compares the old unsalted aggregate with current builtin identity, and requires stale legacy status without launching refresh. Producer-generation-only change, unavailable producer and unchanged non-code aggregate are separately asserted. These distinguish actual producer migration from incidental watched-source changes.
- New generation tests require actual RED against the existing no-filters/extractor3 starting body before generation implementation. The older two-case RED/GREEN does not cover them. V-GR1 remains the focused raw-hash module, now four cases; V-GR2..4 retain bounded graph/generation/default/opt-in regression coverage. Git skips cannot satisfy acceptance. No DB or broad123 suite is authorized.
- Retained FR-370..374 still require bounded one-refresh/one-requery opt-in behavior, explicit running/uncertain status, existing lock/timeout/debounce, unchanged defaults and no Graphify/refresh-all/automatic legacy refresh. No cache-format change, custom provider refactor, SQL/UI work or installed/main edit is added. Advancing the cache generation and adding the explicit stamp salt are the precise allowed exceptions to general unchanged-cache/behavior wording.

The original conservative RED interpretation remains binding:4b historical reuse qualifies eligible PASS, not prior failed RED. T-951's retained historical-RED eligibility wording cannot waive the explicit actual RED fallback; the new generation cases unconditionally require their specified actual RED. No RED-reuse mechanism or retroactive prebuild approval is approved here.

## Gates and boundaries

Fresh consent for the revised task hash remains pending; the old unapproved fd7/a664 scopes do not authorize this expansion. The final wording explicitly allows only the declared generation/cache policy changes and separates baseline raw-hash RED from the no-filters/extractor3 generation RED reference. Those clarifications were read before this final verdict. The three backend-only R2 visual-step confirmations remain pending genuine owner response and can be bundled with the corrective adoption task question. Later exact V5 context approval and current functional/security audits remain separate gates. V4 ownerFALSE/auditFAIL is preserved; no old seal transfers. R1/R10 clear status reported by Root is not substituted for owner consent or executed migration proof.

Reviewer queried the native graph first (_code_generation absent), then read bounded revised proposal and actual canonical cache/hash/status ranges. No implementation/tests/DB/probes/install/state changes were performed. The source identification is code_graph.file_shas (actual canonical function); no nonexistent _blob_shas implementation is introduced by an abbreviated assignment label. Original one-argv adoption review remains applicable to that function.

## Reviewed proposal SHA256

| Document | SHA256 |
|---|---|
| spec.md |ad92cf912501fd80dda07b2d227473f23ccc2f8dddc089a077a806d51b9acf7b |
| plan.md |7e1921ee4e79ef9c7c43fc6cefcf4de4da37ada365dc33e3ebfa9f68febbbcaf |
| tasks.md |3af37879b308c114f408d65be599668ea6d0b5a82f0771388054338563d21884 |

Any later source/task/package drift requires the corresponding current review/proof, not relabeling this plan verdict as implementation success.
