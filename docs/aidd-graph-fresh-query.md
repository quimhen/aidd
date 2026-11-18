## Current adoption binding - 2026-11-17

The five declared mutable `proposed-targets` inputs now contain byte-exact copies of the current verified Main sources and six-case raw-hash test. These are the current adoption payloads; the initial V5 context-lock, verification-receipt and original execution logs remain immutable historical evidence of the earlier four-case baseline. They do not certify the later fsmonitor correction and must not be used as current source pins.

Current payload SHA-256:

- `batch-staging/aidd-optimization-20261113/graph-v5-corrective-adoption/proposed-targets/adapters/dot-aidd/scripts/aidd_graphs.py`: `1293eeb3cae6dd264fa65410bf44ed1922383160d4f66651911019458d026b14`.
- `batch-staging/aidd-optimization-20261113/graph-v5-corrective-adoption/proposed-targets/adapters/dot-aidd/scripts/code_graph.py`: `bcfeb0a732c6d570d6082b4198c9cb491ca249b349d09c027fa92c4a38fe90a1`.
- `batch-staging/aidd-optimization-20261113/graph-v5-corrective-adoption/proposed-targets/skill/scripts/aidd_graphs.py`: `1293eeb3cae6dd264fa65410bf44ed1922383160d4f66651911019458d026b14`.
- `batch-staging/aidd-optimization-20261113/graph-v5-corrective-adoption/proposed-targets/skill/scripts/code_graph.py`: `bcfeb0a732c6d570d6082b4198c9cb491ca249b349d09c027fa92c4a38fe90a1`.
- `batch-staging/aidd-optimization-20261113/graph-v5-corrective-adoption/proposed-targets/tests/test_code_graph_raw_hashes.py`: `1b359a7a1f593407559323c2913c80a1a501bb7215fb83576bead858db33ef64`.

Current executed cohort evidence: `batch-staging/aidd-final-fp-convergence-20261117/proof/cohort-summary.json` (SHA-256 `4530f30c821ebee326f542eef6ac5cfa7e7140dcd08412ea860abb801dbb4939`). Its actual Root receipts establish the current 99 security, 154 feature/graph/summary and 10 hook/summary methods; the 263 total uses the recorded unchanged-input proof, not a new execution by this metadata update. No official audit verdict is asserted here.

Adoption must create a fresh explicit mapping from these current bytes and bind each source SHA-256 before apply. `tools/aidd_selective_update.py` checks `source_sha256` and target preconditions in `_plan_entries` and repeats target/output checks during `apply_transaction`. Thus an old executable plan pinned to historical source bytes must fail closed after this alignment; never edit an old receipt, relax its hash checks, or treat a historical lock as a current successful transaction. Release preparation reads current Main skill/adapter sources, not historical proposed copies.

The existing Graph unit approval and its five sealed `unit.paths` remain unchanged. This note updates an already declared target; it neither extends approval to new paths nor transfers an old seal to another package. The exact-copy mapping, backups and native before/after digest checks are recorded outside Main in `D:/Fuentes/_worktrees/release-preflight-20261116/graph-mutable-adoption-20261117/result.json`.

---

# READ FIRST — CURRENT PRIMARY EVIDENCE, 2026-11-17

The old context-lock proposed-byte snapshot and earlier123/114/round06/round07 receipts are historical owner baselines, not the current executed bindings. Current verified bindings are printed below. Read this section before older appended reports. All current primary evidence is inside this declared target; external files are not needed to inspect it. No new test run or audit verdict is invented by this presentation.

**Actual ROOT cohort:263 methods,118explicit pytest subtests,287 identical before/after/current Python hashes.** Six security groups total99; feature/Graph/summary group154; selected hook-summary group10. Unit tests do not separately report a subtest total, so none is inferred.

## One exact common287-input map

The following map has exactly the values of both before/after maps in every original receipt. Repeated maps are shown once to keep this evidence readable. Every original raw receipt, including its own exact formatting/maps, is recoverable from the lossless archive below.

```json
{
  "adapters/dot-aidd/extensions/azure_devops/provider.py": "e37f707098967052b8237a13c6b7cf00c47f69a620f3b3011fdf24b8e7024cce",
  "adapters/dot-aidd/extensions/bitbucket/provider.py": "ed0c356959a0842bc677af7e69d420f7f8c17271e408587d82abf7255e0217c6",
  "adapters/dot-aidd/extensions/github/provider.py": "7c1cc7e69d0fc9a9e20ad7d00d21fc5e8739db3f8c97c0e0ad2350eb75fcd5e6",
  "adapters/dot-aidd/hooks/_common.py": "45c0cd7df40e8fc2d806c00728b92be07efbc6cf8d25549888a6a6d4969891a5",
  "adapters/dot-aidd/hooks/codex_patch.py": "80606fc63d5093b30635a60ead1033daf6cefeec2631e71decba418922394505",
  "adapters/dot-aidd/hooks/codex_subagent.py": "979ec6b972db69f259a813f3774e1d2e437b0dda767af971e69b3e0e3b42fd8c",
  "adapters/dot-aidd/hooks/host_adapter.py": "866255e711599a1dc193cd98e67d9cb68474a3e32e2cf13b53a369959ef8b5d0",
  "adapters/dot-aidd/hooks/mark_agent_dispatch.py": "f8493c2050015e77dd1099a09b46a2d10f843514d8603395ad126d04c8ba5de5",
  "adapters/dot-aidd/hooks/mark_code_edit.py": "ad079853f95fe3eecf192e3e5f6ba9b7b985a8419a434e288a74594e0333f91a",
  "adapters/dot-aidd/hooks/record_dispatch_pre.py": "fdd01a182570b472e259c25d7ed5e5a1587e87b96da5e3a75fe5f0f1c5880ee9",
  "adapters/dot-aidd/hooks/require_aidd.py": "c17ac0e89be6ca7bdee86c97cfde3fe8a6390b170221a9bf4983c9bfaaca2498",
  "adapters/dot-aidd/hooks/require_graph_coherence_audit.py": "4b7ca30c063c38ec9b7b439a76bdecb5b4f9714ab94833c6776331e040f2d5f4",
  "adapters/dot-aidd/hooks/require_independent_audit.py": "83133575c09139308b9a0e51c9bdeb1f0190f794239e8322b52f0942077821fa",
  "adapters/dot-aidd/hooks/rule_gate.py": "218144030955f377acb81a278a40259b212688c24ba037566cbfe4ed416f9153",
  "adapters/dot-aidd/scripts/aidd_amendment_verify.py": "d398f87437bba00fd834115af37824aad06efe0f803d7a5c36a58847f8565340",
  "adapters/dot-aidd/scripts/aidd_calibrate.py": "8ba2095e85e0ef70f44d635904c2152a1b67d91f0d4a48585d5bede0d7cc83e2",
  "adapters/dot-aidd/scripts/aidd_close_ledger.py": "30ac3340d9b0883c79647efcd894b9c90e7971d495cf10e87bdba7bc6f9322d8",
  "adapters/dot-aidd/scripts/aidd_coverage.py": "a5242def74461fd0b25913706e5eb0c9f09b71fb016007d54dd5859f6e404798",
  "adapters/dot-aidd/scripts/aidd_doctor.py": "c460a811bde2cd1c3aafcd26f8151481f7c6cc5d83f05dc001ccfd97c8696b65",
  "adapters/dot-aidd/scripts/aidd_embed.py": "f6128bcada85c6c550a46615f5aa5adbe7396df6c98fedbcb83a11d6aeeb58ea",
  "adapters/dot-aidd/scripts/aidd_evidence.py": "9e3641692e3a7326b971b9e5143bdd5085c7356adfc3a207245f0636eedcbe86",
  "adapters/dot-aidd/scripts/aidd_gitignore.py": "c3ffe2db014c78ecb5570b6ac7ee6966583aa4a08f08949c21b8da22c70883c7",
  "adapters/dot-aidd/scripts/aidd_graphs.py": "1293eeb3cae6dd264fa65410bf44ed1922383160d4f66651911019458d026b14",
  "adapters/dot-aidd/scripts/aidd_guard.py": "e44b113280488f859e1179fcea8b92bca13a462df3f918f1068672ed04a778e0",
  "adapters/dot-aidd/scripts/aidd_job.py": "bc9afe091955e692511a9cf979fce9c8f86273b69c7de44bec54945a1f991984",
  "adapters/dot-aidd/scripts/aidd_memory.py": "bb828833e66331e52e69c0ca1e6d0ca3dee7c38856b629d2d3be7767904edce5",
  "adapters/dot-aidd/scripts/aidd_memory_import.py": "72ec99607f61fde3411b7158798b9e389a96f454d2da4e3f0d314c62d1e92101",
  "adapters/dot-aidd/scripts/aidd_navigator.py": "8f4e401f708313772b0f1623de8f277fb7d2bacbb74f127a02b8f9e0b097fd3b",
  "adapters/dot-aidd/scripts/aidd_next.py": "cec86faf227a20283840b4c2877b0be77e39fc35670c298eafdafeee2cfe7917",
  "adapters/dot-aidd/scripts/aidd_pending.py": "8545f8154c57d4f323ec318bd0e016caaf1e7803bc9690952063605cb85490c1",
  "adapters/dot-aidd/scripts/aidd_progress.py": "f78a92171423f7585c45159fcb89453c23951d269e85b6b9dcc5adbd1e90fee3",
  "adapters/dot-aidd/scripts/aidd_provider_attestation.py": "963e3ab5433a699c742792a6c69505f3f8ef98e8034dc3fe541c77366d278e24",
  "adapters/dot-aidd/scripts/aidd_readiness.py": "9e849388f8e1f779c787da3b75f8ea3091bf62a30a3ab5bac973e4321f532a6c",
  "adapters/dot-aidd/scripts/aidd_red.py": "c79beb57f7ff4f09bf891c80e053bfdd43da5ebac963d9d661cc29a42acc9df0",
  "adapters/dot-aidd/scripts/aidd_reuse.py": "d44ab46e81460428b60adda8b5422dcf62504fc5e5c08b8f155d0a135af27b1f",
  "adapters/dot-aidd/scripts/aidd_review.py": "193ef345c12b2a6978f5c559baae133135148404124a5ef319ab93a64c2a2a71",
  "adapters/dot-aidd/scripts/aidd_review_items.py": "f60656841367524f9726c960a6e8d0114901de41ebbb7ec2f7ef0527847c6d1d",
  "adapters/dot-aidd/scripts/aidd_review_state.py": "d8aa138121481f46c1350be1f5308185f85f78a21dc05e394231c16bd1491b30",
  "adapters/dot-aidd/scripts/aidd_round.py": "f6640e4efa20b17610717e2592d51aefb798e4dd642f0f77d1960616fc926caa",
  "adapters/dot-aidd/scripts/aidd_rules.py": "31ae5f48312776a3c7130229c8cc50fdf9e553d40ed67357bfada3aca0fd8cbe",
  "adapters/dot-aidd/scripts/aidd_source_shape.py": "cc71c80afba6fbd05fc0397662d22db04ce45b232ef8a1f6b8e1fcf0e65849b8",
  "adapters/dot-aidd/scripts/aidd_sqlcheck.py": "996a3db37de2507c3b745eee7b2be53a9ad1be1eca2af3b33c202503a3274a69",
  "adapters/dot-aidd/scripts/aidd_status.py": "06d17ca5008f07640141a5fdf90f2208400d1e0de6c0b00761d1ce9df3d59e88",
  "adapters/dot-aidd/scripts/aidd_sync.py": "275c8d9341edf102edfcf6f0a5347957639f17bf560d15c2099c4a8e124f518a",
  "adapters/dot-aidd/scripts/aidd_tools.py": "7e4c83db65fffe7a3bbf3e2e00850efc54cc17e8a465ff5081b61a59ce7bac8e",
  "adapters/dot-aidd/scripts/aidd_triage.py": "8b37d88a784faeab135cfafd4621b4590db1c0cfc0925a9b05b649ec75792c7b",
  "adapters/dot-aidd/scripts/aidd_unit_audit.py": "3eb0ef12a6b451cbbcc3de0c493704cbe81506b36759f91c7ebd261298164d01",
  "adapters/dot-aidd/scripts/aidd_unit_consent.py": "b1ced4a620b1501b1f51a1a1945d7c188aeeb49ea62870e843100ccde5c28fe4",
  "adapters/dot-aidd/scripts/aidd_unit_visual.py": "ee9bf1d2c1cf713951ec3538bca49cd14bbd6b8ad29f6da648232034858c37e6",
  "adapters/dot-aidd/scripts/aidd_units.py": "3c53f71416a41b934c24d2bff646d60e1834d237e729a5e3658c41b027ff8d61",
  "adapters/dot-aidd/scripts/alias_graph.py": "ebde0c8955fecf3d04c41acd80aa6b2674ee29fcc6655701810d3ec844d82e94",
  "adapters/dot-aidd/scripts/check_charter.py": "3012c8b6f75395b7ecda621ff36407ae56baf62f72d2eb5e7f0019c6ebdef239",
  "adapters/dot-aidd/scripts/check_spec.py": "6f9e073de4c29d04674fbab33ed4825a55b811c2749601a104eba1713d029e79",
  "adapters/dot-aidd/scripts/code_graph.py": "bcfeb0a732c6d570d6082b4198c9cb491ca249b349d09c027fa92c4a38fe90a1",
  "adapters/dot-aidd/scripts/component_graph.py": "fc5f048e98ca820961c75900174e4bfbc19e93d3c9894eba840c5c161df1084d",
  "adapters/dot-aidd/scripts/extension_registry.py": "84f92e73731e3a8440b40aa045243191cb3d1750ec3f476837e335170f9c222d",
  "adapters/dot-aidd/scripts/find_spec.py": "182066815d51e8c8b489b5296179ba9d62dff30caf8ba763a7bbfb4e9178026c",
  "adapters/dot-aidd/scripts/flowmap.py": "17a30f677b4d1f0176d82831fb5374ce7a22b72af1068bfdb9b7c933c627b9bc",
  "adapters/dot-aidd/scripts/graph_explorer.py": "f88a70f48ddd3a52bc8f4c8d4a6bcca43d882eb35d849129533a76ff6ca521da",
  "adapters/dot-aidd/scripts/graph_snapshot.py": "035f67aa18a4699a89c76e9e14d066745b28d98b4c09228138a6e38f354823f3",
  "adapters/dot-aidd/scripts/graph_trace.py": "ed17b84d9b2217b8e562fefe8c2ea7908d64e8870d308b6f7532b175ef26ea94",
  "adapters/dot-aidd/scripts/link_pr_to_task.py": "d3b729bbc9d869fdfd1d1794d1bf7a960c79ce9dee279c745f0f78b974da3279",
  "adapters/dot-aidd/scripts/method_graph.py": "291bac97cb435fc1c12191d591cdfa25d40d029a9ab3745bfe1ff307ced52c65",
  "adapters/dot-aidd/scripts/sql_graph.py": "6c893e1172ba65d9f373b8b2bcd0b063267145a0ae8635424986eb138dea07ce",
  "adapters/dot-aidd/scripts/sync_issues.py": "4635e4f8e67e2c890c7d71dd03bc3bdbfd1c17629f10265c784702414da1a6f2",
  "adapters/dot-aidd/scripts/tasks_to_issues.py": "b25d960947848f467ccdead895998602f07611b6548de096d41f81713fabf2b7",
  "adapters/dot-aidd/scripts/unified_graph.py": "035be7b3427b985c7ec261101a56fe6c7cfaf42c87c966d095f964be1bc85a35",
  "aidd/__init__.py": "9570e4f1f2a4c4d891ccab27792ee5f3dc300d7c3b3fa60d0d93cb3498d30f86",
  "aidd/cli.py": "a92eac5f8e9807d2268695fa0c8b1d578a872ce6f9982de2e9a4f96bf4c97e82",
  "skill/extensions/azure_devops/provider.py": "e37f707098967052b8237a13c6b7cf00c47f69a620f3b3011fdf24b8e7024cce",
  "skill/extensions/bitbucket/provider.py": "ed0c356959a0842bc677af7e69d420f7f8c17271e408587d82abf7255e0217c6",
  "skill/extensions/github/provider.py": "7c1cc7e69d0fc9a9e20ad7d00d21fc5e8739db3f8c97c0e0ad2350eb75fcd5e6",
  "skill/hooks/_common.py": "45c0cd7df40e8fc2d806c00728b92be07efbc6cf8d25549888a6a6d4969891a5",
  "skill/hooks/codex_patch.py": "80606fc63d5093b30635a60ead1033daf6cefeec2631e71decba418922394505",
  "skill/hooks/codex_subagent.py": "979ec6b972db69f259a813f3774e1d2e437b0dda767af971e69b3e0e3b42fd8c",
  "skill/hooks/graph_refresh.py": "c2939de2d6d4e92063fac0122a3d8aedd398ad6630482f0ea65f97abc5a71a0a",
  "skill/hooks/host_adapter.py": "866255e711599a1dc193cd98e67d9cb68474a3e32e2cf13b53a369959ef8b5d0",
  "skill/hooks/mark_agent_dispatch.py": "f8493c2050015e77dd1099a09b46a2d10f843514d8603395ad126d04c8ba5de5",
  "skill/hooks/mark_code_edit.py": "ad079853f95fe3eecf192e3e5f6ba9b7b985a8419a434e288a74594e0333f91a",
  "skill/hooks/mark_graph_rebuild.py": "17e73634e1cfb4eb7ae55657b711c1149b7040fcf085451dc27ecadd2cf45598",
  "skill/hooks/mark_invoked.py": "ca84a4c72bd8e4ba1aca83a4c3cf22905d45dc7474f03fc70a4967650eeaf2c9",
  "skill/hooks/mark_user_question.py": "b15dad0fcfe697c4007bcb2421ccc064222e996f0284ab487d0380f259d84bae",
  "skill/hooks/memory_context.py": "4b21152bf64bbb9380128e4bd02c24968e6441d3605306da2ef0b98c742cb0b5",
  "skill/hooks/memory_file_context.py": "cad231bd2e42dafc253e05b66616611119a12e52c1fd0906d73667c9540dfe74",
  "skill/hooks/prompt_trigger.py": "888676a5903c9f97e2c9ce5324cb2a2233be849b7b14983ce2c07d07a2cf82e8",
  "skill/hooks/read_hint.py": "71406502245856bb2352f646089f8d8d81ec654a49c91bbeb60bf85fdebce4f9",
  "skill/hooks/record_dispatch_pre.py": "fdd01a182570b472e259c25d7ed5e5a1587e87b96da5e3a75fe5f0f1c5880ee9",
  "skill/hooks/require_aidd.py": "c17ac0e89be6ca7bdee86c97cfde3fe8a6390b170221a9bf4983c9bfaaca2498",
  "skill/hooks/require_graph_coherence_audit.py": "4b7ca30c063c38ec9b7b439a76bdecb5b4f9714ab94833c6776331e040f2d5f4",
  "skill/hooks/require_independent_audit.py": "83133575c09139308b9a0e51c9bdeb1f0190f794239e8322b52f0942077821fa",
  "skill/hooks/rule_gate.py": "218144030955f377acb81a278a40259b212688c24ba037566cbfe4ed416f9153",
  "skill/hooks/session_start.py": "b1a707dc4af6f11bcfa7441b61f39b1c60d82fb0852f292d5d5a214b3c013fc1",
  "skill/hooks/stop_gate.py": "3db5a5aef8951408da42be73a2269ff4a1a196dc4a26429b522c6f73ede6fa6f",
  "skill/hooks/tool_first_hint.py": "edd196abb526b32fe74a8fcee65bbcd870b742b428d5e6934507df314cdcedd3",
  "skill/scripts/aidd_amendment_verify.py": "d398f87437bba00fd834115af37824aad06efe0f803d7a5c36a58847f8565340",
  "skill/scripts/aidd_calibrate.py": "8ba2095e85e0ef70f44d635904c2152a1b67d91f0d4a48585d5bede0d7cc83e2",
  "skill/scripts/aidd_close_ledger.py": "30ac3340d9b0883c79647efcd894b9c90e7971d495cf10e87bdba7bc6f9322d8",
  "skill/scripts/aidd_coverage.py": "a5242def74461fd0b25913706e5eb0c9f09b71fb016007d54dd5859f6e404798",
  "skill/scripts/aidd_doctor.py": "c460a811bde2cd1c3aafcd26f8151481f7c6cc5d83f05dc001ccfd97c8696b65",
  "skill/scripts/aidd_embed.py": "f6128bcada85c6c550a46615f5aa5adbe7396df6c98fedbcb83a11d6aeeb58ea",
  "skill/scripts/aidd_evidence.py": "9e3641692e3a7326b971b9e5143bdd5085c7356adfc3a207245f0636eedcbe86",
  "skill/scripts/aidd_gitignore.py": "c3ffe2db014c78ecb5570b6ac7ee6966583aa4a08f08949c21b8da22c70883c7",
  "skill/scripts/aidd_graphs.py": "1293eeb3cae6dd264fa65410bf44ed1922383160d4f66651911019458d026b14",
  "skill/scripts/aidd_guard.py": "e44b113280488f859e1179fcea8b92bca13a462df3f918f1068672ed04a778e0",
  "skill/scripts/aidd_job.py": "bc9afe091955e692511a9cf979fce9c8f86273b69c7de44bec54945a1f991984",
  "skill/scripts/aidd_memory.py": "bb828833e66331e52e69c0ca1e6d0ca3dee7c38856b629d2d3be7767904edce5",
  "skill/scripts/aidd_memory_import.py": "72ec99607f61fde3411b7158798b9e389a96f454d2da4e3f0d314c62d1e92101",
  "skill/scripts/aidd_navigator.py": "8f4e401f708313772b0f1623de8f277fb7d2bacbb74f127a02b8f9e0b097fd3b",
  "skill/scripts/aidd_next.py": "cec86faf227a20283840b4c2877b0be77e39fc35670c298eafdafeee2cfe7917",
  "skill/scripts/aidd_pending.py": "8545f8154c57d4f323ec318bd0e016caaf1e7803bc9690952063605cb85490c1",
  "skill/scripts/aidd_progress.py": "f78a92171423f7585c45159fcb89453c23951d269e85b6b9dcc5adbd1e90fee3",
  "skill/scripts/aidd_provider_attestation.py": "963e3ab5433a699c742792a6c69505f3f8ef98e8034dc3fe541c77366d278e24",
  "skill/scripts/aidd_readiness.py": "9e849388f8e1f779c787da3b75f8ea3091bf62a30a3ab5bac973e4321f532a6c",
  "skill/scripts/aidd_red.py": "c79beb57f7ff4f09bf891c80e053bfdd43da5ebac963d9d661cc29a42acc9df0",
  "skill/scripts/aidd_reuse.py": "d44ab46e81460428b60adda8b5422dcf62504fc5e5c08b8f155d0a135af27b1f",
  "skill/scripts/aidd_review.py": "193ef345c12b2a6978f5c559baae133135148404124a5ef319ab93a64c2a2a71",
  "skill/scripts/aidd_review_items.py": "f60656841367524f9726c960a6e8d0114901de41ebbb7ec2f7ef0527847c6d1d",
  "skill/scripts/aidd_review_state.py": "d8aa138121481f46c1350be1f5308185f85f78a21dc05e394231c16bd1491b30",
  "skill/scripts/aidd_round.py": "f6640e4efa20b17610717e2592d51aefb798e4dd642f0f77d1960616fc926caa",
  "skill/scripts/aidd_rules.py": "31ae5f48312776a3c7130229c8cc50fdf9e553d40ed67357bfada3aca0fd8cbe",
  "skill/scripts/aidd_source_shape.py": "cc71c80afba6fbd05fc0397662d22db04ce45b232ef8a1f6b8e1fcf0e65849b8",
  "skill/scripts/aidd_sqlcheck.py": "996a3db37de2507c3b745eee7b2be53a9ad1be1eca2af3b33c202503a3274a69",
  "skill/scripts/aidd_status.py": "06d17ca5008f07640141a5fdf90f2208400d1e0de6c0b00761d1ce9df3d59e88",
  "skill/scripts/aidd_sync.py": "275c8d9341edf102edfcf6f0a5347957639f17bf560d15c2099c4a8e124f518a",
  "skill/scripts/aidd_tools.py": "7e4c83db65fffe7a3bbf3e2e00850efc54cc17e8a465ff5081b61a59ce7bac8e",
  "skill/scripts/aidd_triage.py": "8b37d88a784faeab135cfafd4621b4590db1c0cfc0925a9b05b649ec75792c7b",
  "skill/scripts/aidd_unit_audit.py": "3eb0ef12a6b451cbbcc3de0c493704cbe81506b36759f91c7ebd261298164d01",
  "skill/scripts/aidd_unit_consent.py": "b1ced4a620b1501b1f51a1a1945d7c188aeeb49ea62870e843100ccde5c28fe4",
  "skill/scripts/aidd_unit_visual.py": "ee9bf1d2c1cf713951ec3538bca49cd14bbd6b8ad29f6da648232034858c37e6",
  "skill/scripts/aidd_units.py": "3c53f71416a41b934c24d2bff646d60e1834d237e729a5e3658c41b027ff8d61",
  "skill/scripts/alias_graph.py": "ebde0c8955fecf3d04c41acd80aa6b2674ee29fcc6655701810d3ec844d82e94",
  "skill/scripts/check_charter.py": "3012c8b6f75395b7ecda621ff36407ae56baf62f72d2eb5e7f0019c6ebdef239",
  "skill/scripts/check_spec.py": "6f9e073de4c29d04674fbab33ed4825a55b811c2749601a104eba1713d029e79",
  "skill/scripts/code_graph.py": "bcfeb0a732c6d570d6082b4198c9cb491ca249b349d09c027fa92c4a38fe90a1",
  "skill/scripts/component_graph.py": "fc5f048e98ca820961c75900174e4bfbc19e93d3c9894eba840c5c161df1084d",
  "skill/scripts/extension_registry.py": "89550ea8e70f581e6385778523e5fa184847c9305ff9f3a9cee9d8bf3d2f0aa3",
  "skill/scripts/find_spec.py": "182066815d51e8c8b489b5296179ba9d62dff30caf8ba763a7bbfb4e9178026c",
  "skill/scripts/flowmap.py": "17a30f677b4d1f0176d82831fb5374ce7a22b72af1068bfdb9b7c933c627b9bc",
  "skill/scripts/generate_adapters.py": "a763aa4d9d880ed979fab90c75dd47ac19101cc8afcd6cbce6a91c7b61fefb1d",
  "skill/scripts/graph_explorer.py": "f88a70f48ddd3a52bc8f4c8d4a6bcca43d882eb35d849129533a76ff6ca521da",
  "skill/scripts/graph_snapshot.py": "035f67aa18a4699a89c76e9e14d066745b28d98b4c09228138a6e38f354823f3",
  "skill/scripts/graph_trace.py": "ed17b84d9b2217b8e562fefe8c2ea7908d64e8870d308b6f7532b175ef26ea94",
  "skill/scripts/install_ci.py": "61f69bbc87b3c3c0cc6c04d784290f417e9884edf8d8d802b8247075ff4d5e3b",
  "skill/scripts/install_hooks.py": "02b29415888926985f307ac939f1e41fe1d4423aa5e7fe77bba0b7ca225f507d",
  "skill/scripts/install_host.py": "8b1df766e0e9de5d02f47f1180171a792b5666fba61160b583638b687d01c0f6",
  "skill/scripts/link_pr_to_task.py": "d3b729bbc9d869fdfd1d1794d1bf7a960c79ce9dee279c745f0f78b974da3279",
  "skill/scripts/marketplace.py": "0e2fabf91b24eb592ba21843c038366dd99f3c19b995592974e05349470159f9",
  "skill/scripts/method_graph.py": "291bac97cb435fc1c12191d591cdfa25d40d029a9ab3745bfe1ff307ced52c65",
  "skill/scripts/research_project.py": "debcc9dd9023671d2a0c795f842c3e8c0dd351d9bfc6fc9860046b445a5affdc",
  "skill/scripts/sql_graph.py": "6c893e1172ba65d9f373b8b2bcd0b063267145a0ae8635424986eb138dea07ce",
  "skill/scripts/sync_issues.py": "4635e4f8e67e2c890c7d71dd03bc3bdbfd1c17629f10265c784702414da1a6f2",
  "skill/scripts/tasks_to_issues.py": "b25d960947848f467ccdead895998602f07611b6548de096d41f81713fabf2b7",
  "skill/scripts/unified_graph.py": "035be7b3427b985c7ec261101a56fe6c7cfaf42c87c966d095f964be1bc85a35",
  "skill/scripts/validate_catalog_entry.py": "88e4fa3ed51a029acebda7ffb98b26c3f211c727b99368eb3ddaccfb99759ce0",
  "tests/coverage_manifest.py": "c17ed238727a35ac5230fab2dd0c6cb1305b2493673980a80ea478bfbf389e78",
  "tests/e2e_review_roundtrip.py": "92f78022c19bd03888264bb692e655cff178381dfd967c4f83d1d33cca1ef338",
  "tests/gate_fixtures.py": "ac14082525e6e96a8f75b8c38f44523606c0e86a24dfcab2da58bde44dc97410",
  "tests/report_guard_portability.py": "95b70220a3aaf87ed68d30f95f5ab78c1ae11ce1a20f09f28212f99b5e568b09",
  "tests/run_parallel.py": "cef094fa2c88b7a068f25c94e53324b78fc252ef814a73e912541ce8879b9e3f",
  "tests/test_aidd_calibrate.py": "086c8d81b50ab1d368da352a17b97a3f838998da71abda96be25dcf74da5578a",
  "tests/test_aidd_coverage.py": "d399b5f06a3252e7a56c96b33726a250aa17bfe15dd68db8c6cf14d314b72b59",
  "tests/test_aidd_declared_hermetic.py": "fae9a918860d74706460c59a511ee33131744c7af0534480c4333f5d957de158",
  "tests/test_aidd_graphs.py": "90646af5005f167ce027991fc156ad5c28c2f2409eebc2bf58e4cc0c6d06a33a",
  "tests/test_aidd_graphs_empty_query.py": "c98d00da7278bd78df7a90cbcce53e0aea8110024fb69170bcf78702b32f8585",
  "tests/test_aidd_graphs_running_state.py": "50a1cf98fc57c02d4d1bf6998b27854c7e55271104da6fd259872591d74fb4fc",
  "tests/test_aidd_guard.py": "452f716725fbbbdde5961ad357bd34c8e91a6890e71582709ce6ea8d0d4960cc",
  "tests/test_aidd_guard_partial.py": "84c6067e3881874006259d3129b369ccc28dfd9e378aaa64b112c29dda6b84ae",
  "tests/test_aidd_job.py": "b99eb671bb3dc6bf18949047acbf7fff0fb923838c90ebc19b43e29bf87634e8",
  "tests/test_aidd_local_unit_review.py": "186460659378d8717b621b335c12a7737a9ee023823dafdb0a7f639b616171cd",
  "tests/test_aidd_memory.py": "4c613719b30e077fff965830370ffb2b235fc0ff1a96579be52ee43d8b422838",
  "tests/test_aidd_memory_import.py": "55866735df404b82e2602b1ab7c3a36c95a30def89c7cfe86f2929e1a1e4cc70",
  "tests/test_aidd_navigator.py": "15014626911e1deccc5d58917a5c6599522b8e8676376a1598c52e7e13a714b4",
  "tests/test_aidd_next.py": "8ffa0f46ecf4cfc4706760288cc92245634906f808ce81fe5470cf2e7b18d2b2",
  "tests/test_aidd_prepare_release.py": "82dda1cb0bc313dd35b5fb0271275175ff3fcd39a66207146ab938c47c3c36c1",
  "tests/test_aidd_progress.py": "24273a61fb2bce1fa8988cd96aef21e2d840fafb117bc6c15043bf15bdedf92c",
  "tests/test_aidd_provider_attestation.py": "cb95118624750a383d96929598ddfc46dce54e2484d11362e94ce93edf93199a",
  "tests/test_aidd_readiness.py": "855e310d588bf99f1688c419f6862d4045a1d89570db8112a8931d65de2cce08",
  "tests/test_aidd_review.py": "c86743a50dc4646a153b976c69b24e663714a233adc33728a18ec1d3d9fdf394",
  "tests/test_aidd_review_items.py": "efe5c77882f1780edb45861314598a16c6a8b18a60f3fefaef2fe9c4c5a88b1c",
  "tests/test_aidd_review_state.py": "c211d8edfe3ae78fc3bd2a65f0f08dfd99ee272d4316a792af810318eb4b6d85",
  "tests/test_aidd_rules.py": "e1dce47b0fdbb4aa8a9515a624bfcbe2528996cdb6d77a8985a8da8f39089add",
  "tests/test_aidd_rules_r10.py": "6e63d077bb6f915d21e69685f8fa735c7f4714916297ad7e865b689a3d44c596",
  "tests/test_aidd_source_shape.py": "6c4e131ef485bbe64cf103f5d900fefa595c67647cbdc7dc72739c16afd1e677",
  "tests/test_aidd_sqlcheck.py": "cd189dc1d2ef39dc3c2fb47a7daca0da39b95caf996062cd434fc2d3b6db9a5b",
  "tests/test_aidd_status.py": "a0c4e8801e908bef1ee428477a50c6f37c926361d6cdf6407e9c21d4c1069cc0",
  "tests/test_aidd_sync.py": "8bdf4be8eaa2de7e4962bd8dd96d5aa38a47dbf5872714614c02130ffb275e3e",
  "tests/test_aidd_task_verify.py": "fa74e973b5ad458666ea9eca7dd8a8b1f4d2e924009723d43f708c29b2c76e5c",
  "tests/test_aidd_tools.py": "9bfe9b49d64650a305c5bc7e102e390ad7b7f4b74ea7b455541bc1cfd7e001a0",
  "tests/test_aidd_triage.py": "ac2295d6792eb4eefcde90fcdae3c811ffd9b3837db125154ed3afb7465dc341",
  "tests/test_aidd_unit_approval_gate.py": "fb35aeb9598aea72525f851d99fab69baf48fe84ee50e65fc7d222c3fc8b8885",
  "tests/test_aidd_unit_audit_incremental.py": "6df99aa0fbff292fe017e7d5224d9bd3bedb3243337c5e4cdd9de36b013deb81",
  "tests/test_aidd_unit_consent.py": "be3c331d14e0cc445b6c47ba71cceeeb23e47044a915fcf2338c25fc65039b64",
  "tests/test_aidd_unit_hash.py": "d41660bdf923133efeb0d7ca70bcf6fa4431c9f0a5465363ffcc932622ffeb70",
  "tests/test_aidd_unit_hook_e2e.py": "462c852519001dba86c2dfc76537a4911e08c5b39c6a249a4e32be5b6667168e",
  "tests/test_aidd_unit_impact.py": "33af8d33c9a27279188540e354a3bc508e23dfe6868e47ad604d74d7f65d2965",
  "tests/test_aidd_unit_migration.py": "02e458cdf538d615de785821f9598244db48e929e4ef9a11bc8041226752e960",
  "tests/test_aidd_unit_review.py": "5578a9f82c50be68aa9098b492c7faa40a583b924ff6023997d2e7d0a270c544",
  "tests/test_aidd_unit_review_package.py": "38820e3325abadc77d8c35c8f9e3f2273f0d69444e01cfcae6aac51f9e313a29",
  "tests/test_aidd_unit_visual.py": "05a57c778af30b15ab99b02e0193590575ae0cb29edba34abc52fb640a2ff52a",
  "tests/test_aidd_units.py": "e7b1e545f0b488c0f7030ab7cd1d02655b32267f6b0f38666e8e4da5e3b2db25",
  "tests/test_alias_graph.py": "1cecf4126df31b67568edc8db90eca855952b5eb1ebaf668df5d6064cbd5923d",
  "tests/test_amendment_file_layout.py": "ebfa080600955ee3a0be89bd280908d7ff73911d90fdf57f3b0c8ef25fe41015",
  "tests/test_amendment_truncated_command.py": "77556f4736d58b09aebb8e0ad63a4e4eff79d5d759c658320ee525e3ba129418",
  "tests/test_approval_topic_grammar.py": "c1afdfade7e554bb49e4874a3e1bf53318891c4f513bc83717d1308f3ca861b5",
  "tests/test_b10_b11_b6.py": "fc5b9370fd98615b1646590ff5559b14ef0d9a0e7073e7ccabe9063459ebde2e",
  "tests/test_b12_b5.py": "ec841cc36aed093f493e21ff63e905032ffe6076337680340c76d4493ac71733",
  "tests/test_capacity_budget.py": "ea1a64826bd1ad2dfc983de9eef0e1ef0205b17248949dee68b831d3b6112480",
  "tests/test_check_charter.py": "0a4a2adff8b0df9c40e17075aaf818331d36a42bda54c4a25e9f9378cfd7c750",
  "tests/test_check_spec.py": "e066ca1c2f886cf7ca6ded271a9c0705019b95b472057048821b7c6351a39473",
  "tests/test_ci_runner.py": "4b380e7c91720cda4932bb78649d41ddb0d05c3aec5eace0644d71010da0a089",
  "tests/test_cli_mem.py": "882ec758964a4e1e3685d790e23b151a9aebec34bf1162a496b8fa25104f180f",
  "tests/test_cli_rules.py": "dc79912bbe41aa7e600f348eb7c7f63000b0571fd25440c3d01848f93760397e",
  "tests/test_code_fingerprint.py": "f0172ca0eb5572a33e8ebd9a9eb7847fbda03c0143a5e1281ab36e1defd34927",
  "tests/test_code_graph.py": "bdef8a867000d6ec1aa2cbdc9872b0d008985c6c4c664fd7d99e8b8c3104e885",
  "tests/test_code_graph_raw_hashes.py": "1b359a7a1f593407559323c2913c80a1a501bb7215fb83576bead858db33ef64",
  "tests/test_codex_patch_parser.py": "9104f2c898170df1867166ccdf69d4170271f8d320f4609355d5231f4b6aadc3",
  "tests/test_codex_subagent.py": "7c3a9af060d17f3637d96fcdb6feb7b76a4c7b737bea542a15bf9c6f03244bfd",
  "tests/test_component_graph.py": "c63a477d523c6783143700882d79fec1b353f16af22d10858850015db616e445",
  "tests/test_contract_store.py": "7d6c9a0ffe265256f5b9cc90a0fe6c844626ab423ad1b7e70a4e597e97701981",
  "tests/test_coverage_manifest.py": "02169d478a98a4310ed3219c53deab3388111219cc8b06c8f3f25e3f3d54e9c2",
  "tests/test_cross_platform_paths.py": "6b6128e2908e5ea3a0f5d39675b1f21aa05ce28e5f4ba83ada6cd6606d560da7",
  "tests/test_dot_aidd_mirror.py": "8f0715133acae218d6534fd629ef91b8f9ca8452f7c43ebfa4758709ef7c95a1",
  "tests/test_dry_run_identity_security.py": "11acd8e0cada45c92c5fb101ba43e5f8c5a6c4df3539a380930d6d6c410b31c8",
  "tests/test_embed_compression.py": "9db5fa50a47c92d54e6c540d2386e1effc564adcb0c92e9de0cf45adf764cc9e",
  "tests/test_evidence.py": "bfaccaec4f1ec9f93c0848b48671fa39135eb876730839f85f795b729a3ca9bc",
  "tests/test_explorer_controls.py": "a4bdfb43b81899427d1a1b18525b1f375553f0f3dad0cdef4e149bd7ff39a351",
  "tests/test_explorer_controls_browser.py": "761a8b2e551982a2d92bf41681d461c738f9647fbb62e724b6efb89483e4f9b7",
  "tests/test_extension_providers.py": "e8b3a58c03620f7c8ab0ac8a1c2c2015b86535901316327e53c69cca62d19993",
  "tests/test_find_spec.py": "1deb69a8256c21574f42af99bd1909350b185d675a032e0535b9e8d9f717d0ad",
  "tests/test_flowmap.py": "82bbba3fb8f014e100e337cb654edf51d69544626a4128f668f6d2872225247e",
  "tests/test_generate_adapters.py": "97d75bbbfac1f04d90ebb84ccf5fba44662ebd19bb57900101915a61ae55e1dd",
  "tests/test_graph_explorer.py": "0091bcc58e5fd160375b04435150130506c6d98a94e5729c6fb6bc5d037592e8",
  "tests/test_graph_refresh_hook.py": "e8639c58aa3cfde532366639489c4dd9a9d005e866d22eca51cd6e97e875608e",
  "tests/test_graph_snapshot.py": "c6c813ed760733f5d68d7537f98ad4a055790867748eb16dc65522adad3762f8",
  "tests/test_graph_trace_method.py": "71dd896656bb05a9f0fae41a5296a1fca77d3296b846084399c4188c666d3ae1",
  "tests/test_graphs_auto.py": "8a1048a5f74d996b1b3b4a5347758abe378610559893426f9db8f0c996c8ff11",
  "tests/test_guard_portability_report.py": "4d052dd131bf337d5d13dd1b5cb71cb3283ed20d2ca8ad132ab5ba378265f56f",
  "tests/test_historical_reuse_security.py": "971e7636ae124e77f7d72e4f4251b2f7a264e96a561f1f37c0fb6532416dcc37",
  "tests/test_hooks.py": "4ce6f5c9463e0f68c5d45be2084adc51b0388f5c0edcf14bdcf26d99ebc40071",
  "tests/test_host_doctor.py": "27695f97de24d8de3b25c4effcf9d9ec057f4abbbf08df01044ae9211296e92c",
  "tests/test_host_gates.py": "482f28ae1744e8827d17f4507eb81d23f3962bd5e67e873aafb0378ebb35be7f",
  "tests/test_host_install.py": "3ec35f79bbb908b4ce4f24fdd8e2e0ad5ed3b883948a6a107ea206b8737589b0",
  "tests/test_install_ci.py": "a950c7be4829d7ba13b6364ae5e6739113976a24c79248bcd082bc35434b0762",
  "tests/test_install_hooks.py": "62a6e1256429f17bc03940ab7a74108f6618a90614352b7a583740efedabe4ca",
  "tests/test_link_pr_to_task.py": "6db9ea46bd36948193b9b4742bad221acea9d07e3cf6fef9b3bbf781a4a6971f",
  "tests/test_marketplace.py": "85663620d63246cf93cb385d873b405d266fa3b284775faa08c6cd3e0b75f784",
  "tests/test_memory_hooks.py": "4f13bafd789502f30efd16915a9ca2fc8cf83f06b668a59a13d33456e0ace4cd",
  "tests/test_native_summary_approve_compat.py": "b23ecc80b46050927cbbbd5240dd2ccec548e820e375e33502fba034bcdf0523",
  "tests/test_perf_and_cache.py": "ffd010b605530e4924b9cdfcc17bb4a688a4fb6452ba5f836e92a1751d01ed81",
  "tests/test_perf_budget.py": "1b7cae539ab82d49ca7412dcc8cc2860348de089f7af47cd47153a3ec865096b",
  "tests/test_progress_resolution.py": "39bc2437a1b1b71143ef9d2a68a8e530664cd4e3301ea64b8afec4950263d0f9",
  "tests/test_prompt_trigger.py": "614a2273c9c805ee16c57e1ae849a95e091b44f4d10b58debda843903398fc9d",
  "tests/test_r14.py": "018cfec18f16512d902a1f0d4f357a7ce8d745fc4bb93fee21eac1112397815a",
  "tests/test_r9_transcript.py": "f4101f4400c03395a549e4ee23ecbe41401815bd59d3cebb4c064fc7b4094625",
  "tests/test_read_hint.py": "5b8de9977f792a110f424fa6e273e196f9e400c8025b2253eb544b92c3584d67",
  "tests/test_research_project.py": "e13a6bae17b4b56d4ac8e8dff0f788af34e53aec0688cce2b00c7c1a13ed6f2e",
  "tests/test_reuse_planner.py": "d109c71dda8efb1c96688930093bf1d5f63b8181911bcf6746563a9aaf0f4a49",
  "tests/test_review_template.py": "9e8dc126d17d4d8d1fa1f49e1e9665f24c6c0fbfc6e627a94d5075acc4d321bb",
  "tests/test_rule_gate.py": "7ed963aa16590f42af2f53835a4e0bb5e76271998346d8cd6f52f32c797a254e",
  "tests/test_rule_gate_shell_speed.py": "1e3dde83d5cd7295501b427d865fc4debf53a8f41e9da280696982535e1f67dc",
  "tests/test_run_parallel.py": "9c9119350f0f96fc28b0fa9db6d38b86e255349b9f68ab79651b9025da7af863",
  "tests/test_selective_update.py": "04627eaab4668bdeecaf4d3fc51f46c4a3d0b9b496c32182fa02e62583293a42",
  "tests/test_session_lessons.py": "ac8eec6c8d8f8b2b16454ce9b7420ee9c711cd58c3de92397298625a7ad572c3",
  "tests/test_sql_graph.py": "5e4f9d6b29b2df6c43e640c1a9449773d1f220449adb1d97958f37f84f043839",
  "tests/test_sql_graph_incremental.py": "22fb63ec79e7cb95175bfd2281906f22f49537e13bf128a7633d57b235b65712",
  "tests/test_stop_gate.py": "9c8f2e3f01caf091e6642ded7d46bc3238fdc3e13676026c651767a12f5d1150",
  "tests/test_sync_issues.py": "f1fde1b2daf03bf69c5f016625ae85db6528c1cb6c78a1ecb1ab58c4ea6afc89",
  "tests/test_tasks_batch_coverage.py": "dcbf33ca8614e63873c7186292e9d2304c78d56ff1571d7a53c6152e350ee880",
  "tests/test_tasks_to_issues.py": "3955e6caa0196eb1d0edb17e921bb4d59fc445b9bc8c2057ad93684790f48317",
  "tests/test_tool_first_hint.py": "aaf81ce25cccadd0d6d65f0fe5041a3f1de4d52d703205802356ce2c243346e5",
  "tests/test_transcript_sync.py": "9372efaca66f29c43b8a59f04301001b2bd630b45674a2ebb06852e6cf00e87c",
  "tests/test_typed_confirmations.py": "3d65773abad0fc56c9eb22cb3fc1bdf2674a89fb331ca4ae18e0ed4d364d25c7",
  "tests/test_unified_explorer.py": "e82e0febe64b180ab234d1ca5255b8f98a3147ee49094c357165de48c7a87211",
  "tests/test_unified_graph.py": "5785b352eb1a4d01e3c84a729ca888de9695ad212b7d9919384b1b4b86de9368",
  "tests/test_validate_catalog_entry.py": "8d41809e506f6a21882c00ca19ec90deeafd71e2390a71e1c9133feae442d576",
  "tests/test_verify_amendment.py": "0a6074d096085bd75858e5a95792a0aad77af8fb0820cd0a157798dfee6d79a4",
  "tests/test_verify_changed_policy.py": "0de712d0c2661f054396f7671bf0688cadfbfa057084296940c08e5f003704bb",
  "tests/test_verify_git_contract.py": "8deabfafd00dbf046286587a1a25b73a40c670729977f18c345f6f6a33955756",
  "tests/test_verify_regressions.py": "9fd78387ff6fdc1847c767e759d93c4b1855a9843e4c562eb07947b48598b0e6",
  "tests/test_verify_round.py": "bd024c8e7beb52b99f8c09f091c2e8baa37b462afc663b20f3ba612ead0ef609",
  "tests/test_verify_round_reuse.py": "87f97e5f668b5e4bd482dec1b2deded2fca825988378b6f2357c9487408a3ba6",
  "tests/test_verify_tiers.py": "5cdba30d9b6b8a7d698e57492b8548dc1d47e82d33044b002c901f30af37b491",
  "tests/test_visual_compare_explorer.py": "a2abb3a354d864b93e5df5d8d5aeff51bb310d6774a78434f40d7764bdbd5415",
  "tests/test_visual_review_binding.py": "1a93940239065a7ae981de24d49aaf0381e3eb163c41b95c339516abd79eced7",
  "tests/test_visual_unit_binding.py": "f215791c07ee018caecb28e1f01f1f9ad011ee8bb72054d20e9118c345920ab0",
  "tests/test_wave_verification.py": "2a6feacfd49670371a5546c98b5a848d28ae60533f1e8d839ff56d76ddf66fad",
  "tests/visual_compare_explorer.py": "4c1fe645c6d4c395a7ed59ef0ff77ccb594af0b6c7954983d3d20182d5177868"
}
```

## All eight current receipts and verbatim logs

### FEATURE-GRAPH-SUMMARY.json

Original raw receipt SHA256 `dbbb7d3906df32bf1cf1547ba78f933407f0bcc1b0860ddf84dc11d697cdd358`; before map and after map each equal the exact common287map above. Original raw log SHA256 `1c770c6a060499ada3d74ae313613daa652d2a1372e4344e7de59f977e7eca68`.

```json
{
  "command": [
    "C:\\Users\\jquimis\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
    "-B",
    "-m",
    "pytest",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "tests/test_aidd_source_shape.py",
    "tests/test_aidd_progress.py",
    "tests/test_progress_resolution.py",
    "tests/test_amendment_file_layout.py",
    "tests/test_dot_aidd_mirror.py",
    "tests/test_code_graph_raw_hashes.py",
    "tests/test_code_graph.py",
    "tests/test_aidd_graphs.py",
    "tests/test_aidd_graphs_empty_query.py",
    "tests/test_aidd_graphs_running_state.py",
    "tests/test_graphs_auto.py",
    "tests/test_native_summary_approve_compat.py",
    "tests/test_aidd_status.py::TestSummaryRoute"
  ],
  "cwd": "D:\\Fuentes\\_worktrees\\aidd-security-boundary-20261114\\publication-plan\\coherent-convergence-candidate",
  "exitCode": 0,
  "passedMethods": 154,
  "elapsedSeconds": 36.59399999999732,
  "inputsStable": true,
  "log": "D:\\Fuentes\\_worktrees\\aidd-security-boundary-20261114\\publication-plan\\final-fp-verification-20261117\\FEATURE-GRAPH-SUMMARY.log",
  "logSha256": "1c770c6a060499ada3d74ae313613daa652d2a1372e4344e7de59f977e7eca68",
  "status": "PASS",
  "tail": "............................................................. [ 39%]\r\n......................................................... [ 76%]\r\n....................................                                   [100%]\r\n154 passed, 100 subtests passed in 33.82s\r\n"
}
```

Verbatim log:

````text
............................................................. [ 39%]
......................................................... [ 76%]
....................................                                   [100%]
154 passed, 100 subtests passed in 33.82s

````

### HOOK-SUMMARY.json

Original raw receipt SHA256 `b97ecad567fb4b47b43e1f4e78e1ef739daf5f5dc6bd03db4da5de3a80c410b9`; before map and after map each equal the exact common287map above. Original raw log SHA256 `42cd3721e0c18511c720e8b13774f20bd04792d329bba0ea8584c1626600bcc8`.

```json
{
  "command": [
    "C:\\Users\\jquimis\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
    "-B",
    "-m",
    "pytest",
    "-q",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "tests/test_rule_gate.py",
    "-k",
    "summary"
  ],
  "cwd": "D:\\Fuentes\\_worktrees\\aidd-security-boundary-20261114\\publication-plan\\coherent-convergence-candidate",
  "exitCode": 0,
  "passedMethods": 10,
  "elapsedSeconds": 6.2810000000026776,
  "inputsStable": true,
  "log": "D:\\Fuentes\\_worktrees\\aidd-security-boundary-20261114\\publication-plan\\final-fp-verification-20261117\\HOOK-SUMMARY.log",
  "logSha256": "42cd3721e0c18511c720e8b13774f20bd04792d329bba0ea8584c1626600bcc8",
  "status": "PASS",
  "tail": "..........                                             [100%]\r\n10 passed, 256 deselected, 18 subtests passed in 4.63s\r\n"
}
```

Verbatim log:

````text
..........                                             [100%]
10 passed, 256 deselected, 18 subtests passed in 4.63s

````

### V-4B1-GREEN-round09.json

Original raw receipt SHA256 `00f1097bcaedbb987658ed5bd2f7351380c7c0be9260f556542f28e5ae624e15`; before map and after map each equal the exact common287map above. Original raw log SHA256 `de4926c76a892e81eb659483e5041b0d27e0251a31c90f99ff0990fc53379a02`.

```json
{
  "row": "V-4B1",
  "command": [
    "C:\\Users\\jquimis\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-p",
    "test_historical_reuse_security.py",
    "-v"
  ],
  "cwd": "D:\\Fuentes\\_worktrees\\aidd-security-boundary-20261114\\publication-plan\\coherent-convergence-candidate",
  "python": "3.12.10 (tags/v3.12.10:0cc8128, Apr  8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]",
  "platform": "Windows-11-10.0.26200-SP0",
  "exitCode": 0,
  "collectedMethods": 14,
  "elapsedSeconds": 14.875,
  "inputsStable": true,
  "logSha256": "de4926c76a892e81eb659483e5041b0d27e0251a31c90f99ff0990fc53379a02",
  "log": "D:\\Fuentes\\_worktrees\\aidd-security-boundary-20261114\\publication-plan\\final-fp-verification-20261117\\V-4B1-GREEN-round09.log",
  "status": "PASS",
  "scope": "actual isolated focused verification; no original/install/ERP result implied"
}
```

Verbatim log:

````text
test_03_real_offline_validator_accepts_both_planners (test_historical_reuse_security.HistoricalSecurity.test_03_real_offline_validator_accepts_both_planners) ... ok
test_04_external_and_unsupported_commands_never_reuse_or_execute (test_historical_reuse_security.HistoricalSecurity.test_04_external_and_unsupported_commands_never_reuse_or_execute) ... ok
test_05_missing_or_changed_current_and_prior_contract_refuses (test_historical_reuse_security.HistoricalSecurity.test_05_missing_or_changed_current_and_prior_contract_refuses) ... ok
test_06_existing_command_inputs_artifact_pass_and_state_checks_remain (test_historical_reuse_security.HistoricalSecurity.test_06_existing_command_inputs_artifact_pass_and_state_checks_remain) ... ok
test_07_final_sink_rechecks_identity_source_and_transformed_binding (test_historical_reuse_security.HistoricalSecurity.test_07_final_sink_rechecks_identity_source_and_transformed_binding) ... ok
test_07_long_truncated_after500_tail_change_is_refused_by_real_sink (test_historical_reuse_security.HistoricalSecurity.test_07_long_truncated_after500_tail_change_is_refused_by_real_sink) ... ok
test_08_consumed_proof_survives_and_allows_second_carryover (test_historical_reuse_security.HistoricalSecurity.test_08_consumed_proof_survives_and_allows_second_carryover) ... ok
test_08_cross_spec_store_requires_latest_current_source_event (test_historical_reuse_security.HistoricalSecurity.test_08_cross_spec_store_requires_latest_current_source_event) ... ok
test_08_long_truncated_full_header_is_consumed_by_real_sink (test_historical_reuse_security.HistoricalSecurity.test_08_long_truncated_full_header_is_consumed_by_real_sink) ... ok
test_09_r10_checks_every_reused_kind_against_current_policy (test_historical_reuse_security.HistoricalSecurity.test_09_r10_checks_every_reused_kind_against_current_policy) ... ok
test_10_dual_shared_and_historical_flags_do_not_bypass_policy (test_historical_reuse_security.HistoricalSecurity.test_10_dual_shared_and_historical_flags_do_not_bypass_policy) ... ok
test_10_round_collect_regression_always_remains_run (test_historical_reuse_security.HistoricalSecurity.test_10_round_collect_regression_always_remains_run) ... ok
test_12_old_and_missing_algorithms_refused_for_literal_scope (test_historical_reuse_security.HistoricalSecurity.test_12_old_and_missing_algorithms_refused_for_literal_scope) ... ok
test_12_plain_same_spec_old_or_missing_input_algorithm_executes (test_historical_reuse_security.HistoricalSecurity.test_12_plain_same_spec_old_or_missing_input_algorithm_executes) ... ok

----------------------------------------------------------------------
Ran 14 tests in 14.606s

OK

````

### V-4B2-GREEN-round09.json

Original raw receipt SHA256 `d7c046cb10b12364f457261790d1a521df0378b4eec7d3e7a52e69ff63fc4d85`; before map and after map each equal the exact common287map above. Original raw log SHA256 `584d4c0d50945056101624577cae2d06153e7e69b37defc3d50bda651965dfde`.

```json
{
  "row": "V-4B2",
  "command": [
    "C:\\Users\\jquimis\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-p",
    "test_dry_run_identity_security.py",
    "-v"
  ],
  "cwd": "D:\\Fuentes\\_worktrees\\aidd-security-boundary-20261114\\publication-plan\\coherent-convergence-candidate",
  "python": "3.12.10 (tags/v3.12.10:0cc8128, Apr  8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]",
  "platform": "Windows-11-10.0.26200-SP0",
  "exitCode": 0,
  "collectedMethods": 6,
  "elapsedSeconds": 4.155999999995402,
  "inputsStable": true,
  "logSha256": "584d4c0d50945056101624577cae2d06153e7e69b37defc3d50bda651965dfde",
  "log": "D:\\Fuentes\\_worktrees\\aidd-security-boundary-20261114\\publication-plan\\final-fp-verification-20261117\\V-4B2-GREEN-round09.log",
  "status": "PASS",
  "scope": "actual isolated focused verification; no original/install/ERP result implied"
}
```

Verbatim log:

````text
test_01_all_dry_run_routes_skip_real_identity_marker (test_dry_run_identity_security.DryRunIdentitySecurity.test_01_all_dry_run_routes_skip_real_identity_marker) ... ok
test_02_actual_identity_path_preserved_and_failure_unavailable (test_dry_run_identity_security.DryRunIdentitySecurity.test_02_actual_identity_path_preserved_and_failure_unavailable) ... ok
test_13_actual_amendment_dry_run_does_not_execute_tracked_clean_filter (test_dry_run_identity_security.FullDryRunTrackedFilterSecurity.test_13_actual_amendment_dry_run_does_not_execute_tracked_clean_filter) ... ok
test_14_actual_round_dry_run_does_not_execute_tracked_clean_filter (test_dry_run_identity_security.FullDryRunTrackedFilterSecurity.test_14_actual_round_dry_run_does_not_execute_tracked_clean_filter) ... ok
test_11_blob_and_code_state_do_not_invoke_clean_filter (test_dry_run_identity_security.RawGitIdentitySecurity.test_11_blob_and_code_state_do_not_invoke_clean_filter) ... ok
test_12_raw_bytes_and_crlf_changes_change_public_identity (test_dry_run_identity_security.RawGitIdentitySecurity.test_12_raw_bytes_and_crlf_changes_change_public_identity) ... ok

----------------------------------------------------------------------
Ran 6 tests in 3.962s

OK

````

### V-4B3-GREEN-round09.json

Original raw receipt SHA256 `330142cdb5262da239ec67a584f3897c021170ffea91cea7f87e6c66f6ff5048`; before map and after map each equal the exact common287map above. Original raw log SHA256 `bad974bf211342b5d8c00fb556f165d0c14720512ddaff365452b025363af992`.

```json
{
  "row": "V-4B3",
  "command": [
    "C:\\Users\\jquimis\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-p",
    "test_verify_round*.py",
    "-v"
  ],
  "cwd": "D:\\Fuentes\\_worktrees\\aidd-security-boundary-20261114\\publication-plan\\coherent-convergence-candidate",
  "python": "3.12.10 (tags/v3.12.10:0cc8128, Apr  8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]",
  "platform": "Windows-11-10.0.26200-SP0",
  "exitCode": 0,
  "collectedMethods": 32,
  "elapsedSeconds": 23.312000000005355,
  "inputsStable": true,
  "logSha256": "bad974bf211342b5d8c00fb556f165d0c14720512ddaff365452b025363af992",
  "log": "D:\\Fuentes\\_worktrees\\aidd-security-boundary-20261114\\publication-plan\\final-fp-verification-20261117\\V-4B3-GREEN-round09.log",
  "status": "PASS",
  "scope": "actual isolated focused verification; no original/install/ERP result implied"
}
```

Verbatim log:

````text
test_docker_containers_and_heavy (test_verify_round.Normalisation.test_docker_containers_and_heavy) ... ok
test_quoted_spaces_are_significant (test_verify_round.Normalisation.test_quoted_spaces_are_significant) ... ok
test_whitespace_and_plain_quotes (test_verify_round.Normalisation.test_whitespace_and_plain_quotes) ... ok
test_all_open (test_verify_round.Round.test_all_open) ... ok
test_changed_fingerprint_invalidates (test_verify_round.Round.test_changed_fingerprint_invalidates) ... ok
test_different_command_not_grouped (test_verify_round.Round.test_different_command_not_grouped) ... ok
test_dry_run_executes_nothing (test_verify_round.Round.test_dry_run_executes_nothing) ... ok
test_fail_is_never_shared_as_pass (test_verify_round.Round.test_fail_is_never_shared_as_pass) ... ok
test_fingerprint_refusal_names_the_budget_like_plain_verify (test_verify_round.Round.test_fingerprint_refusal_names_the_budget_like_plain_verify) ... ok
test_generated_artifacts_are_skipped_before_hashing (test_verify_round.Round.test_generated_artifacts_are_skipped_before_hashing) ... ok
test_identical_rows_run_once_and_each_spec_records_its_run (test_verify_round.Round.test_identical_rows_run_once_and_each_spec_records_its_run) ... ok
test_perf_rows_excluded (test_verify_round.Round.test_perf_rows_excluded) ... ok
test_refused_options (test_verify_round.Round.test_refused_options) ... ok
test_rewrite_names_the_row_that_wrote_the_file (test_verify_round.Round.test_rewrite_names_the_row_that_wrote_the_file) ... ok
test_series_one_at_a_time (test_verify_round.Round.test_series_one_at_a_time) ... ok
test_no_suggestion_for_one_spec_or_no_shared_rows (test_verify_round.Suggestions.test_no_suggestion_for_one_spec_or_no_shared_rows) ... ok
test_status_prints_round_line (test_verify_round.Suggestions.test_status_prints_round_line) ... ok
test_status_suggests_round_and_verify_warns (test_verify_round.Suggestions.test_status_suggests_round_and_verify_warns) ... ok
test_changed_command_runs (test_verify_round_reuse.SameSpecReuse.test_changed_command_runs) ... ok
test_changed_evidence_is_not_reused (test_verify_round_reuse.SameSpecReuse.test_changed_evidence_is_not_reused) ... ok
test_dry_run_reports_reuse_and_executes_nothing (test_verify_round_reuse.SameSpecReuse.test_dry_run_reports_reuse_and_executes_nothing) ... ok
test_environment_identity_changed_or_unavailable (test_verify_round_reuse.SameSpecReuse.test_environment_identity_changed_or_unavailable) ... ok
test_full_runs_everything (test_verify_round_reuse.SameSpecReuse.test_full_runs_everything) ... ok
test_new_row_runs_and_old_row_is_reused (test_verify_round_reuse.SameSpecReuse.test_new_row_runs_and_old_row_is_reused) ... ok
test_plain_verify_run_feeds_the_round (test_verify_round_reuse.SameSpecReuse.test_plain_verify_run_feeds_the_round) ... ok
test_previous_fail_is_not_reused_and_mixes_with_reused_rows (test_verify_round_reuse.SameSpecReuse.test_previous_fail_is_not_reused_and_mixes_with_reused_rows) ... ok
test_reuse_never_row_always_runs (test_verify_round_reuse.SameSpecReuse.test_reuse_never_row_always_runs) ... ok
test_reused_row_is_never_a_shared_execution (test_verify_round_reuse.SameSpecReuse.test_reused_row_is_never_a_shared_execution) ... ok
test_reuses_only_when_nothing_changed (test_verify_round_reuse.SameSpecReuse.test_reuses_only_when_nothing_changed) ... ok
test_rows_without_previous_env_id_are_listed_with_the_first_round_note (test_verify_round_reuse.SameSpecReuse.test_rows_without_previous_env_id_are_listed_with_the_first_round_note) ... ok
test_scope_file_changed_runs_again (test_verify_round_reuse.SameSpecReuse.test_scope_file_changed_runs_again) ... ok
test_unavailable_fingerprint_fails_closed (test_verify_round_reuse.SameSpecReuse.test_unavailable_fingerprint_fails_closed) ... ok

----------------------------------------------------------------------
Ran 32 tests in 23.104s

OK

````

### V-4B4-GREEN-round09.json

Original raw receipt SHA256 `5b0681af8443ca95cfa5c53ff0b9460241e2f0abd427c6cb09857cd20a12f384`; before map and after map each equal the exact common287map above. Original raw log SHA256 `67f738cd1e7c4a467e1bc20028c1ff6cb1fe8ec74c1047149a45fc2a8f2d94e0`.

```json
{
  "row": "V-4B4",
  "command": [
    "C:\\Users\\jquimis\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-p",
    "test_verify_amendment.py",
    "-v"
  ],
  "cwd": "D:\\Fuentes\\_worktrees\\aidd-security-boundary-20261114\\publication-plan\\coherent-convergence-candidate",
  "python": "3.12.10 (tags/v3.12.10:0cc8128, Apr  8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]",
  "platform": "Windows-11-10.0.26200-SP0",
  "exitCode": 0,
  "collectedMethods": 15,
  "elapsedSeconds": 12.062000000005355,
  "inputsStable": true,
  "logSha256": "67f738cd1e7c4a467e1bc20028c1ff6cb1fe8ec74c1047149a45fc2a8f2d94e0",
  "log": "D:\\Fuentes\\_worktrees\\aidd-security-boundary-20261114\\publication-plan\\final-fp-verification-20261117\\V-4B4-GREEN-round09.log",
  "status": "PASS",
  "scope": "actual isolated focused verification; no original/install/ERP result implied"
}
```

Verbatim log:

````text
test_command_naming_a_declared_file_runs (test_verify_amendment.AmendmentScope.test_command_naming_a_declared_file_runs) ... ok
test_nothing_changed_reuses_everything (test_verify_amendment.AmendmentScope.test_nothing_changed_reuses_everything) ... ok
test_only_rows_touched_by_the_amendment_run (test_verify_amendment.AmendmentScope.test_only_rows_touched_by_the_amendment_run) ... ok
test_regression_always_runs (test_verify_amendment.AmendmentScope.test_regression_always_runs) ... ok
test_undeclared_input_change_runs_with_warning (test_verify_amendment.AmendmentScope.test_undeclared_input_change_runs_with_warning) ... ok
test_forged_reused_result_is_stale (test_verify_amendment.CloseGate.test_forged_reused_result_is_stale) ... ok
test_gate_accepts_then_stales_on_reused_inputs (test_verify_amendment.CloseGate.test_gate_accepts_then_stales_on_reused_inputs) ... ok
test_amendment_dry_run_executes_nothing (test_verify_amendment.DryRun.test_amendment_dry_run_executes_nothing) ... ok
test_plain_dry_run_does_not_execute (test_verify_amendment.DryRun.test_plain_dry_run_does_not_execute) ... ok
test_unprovable_env_runs_with_reason (test_verify_amendment.Environment.test_unprovable_env_runs_with_reason) ... ok
test_fingerprint_budget_refusal (test_verify_amendment.Refusals.test_fingerprint_budget_refusal) ... ok
test_machine_block_is_read (test_verify_amendment.Refusals.test_machine_block_is_read) ... ok
test_missing_or_empty_amendment_file (test_verify_amendment.Refusals.test_missing_or_empty_amendment_file) ... ok
test_unknown_option_and_bad_combinations (test_verify_amendment.Refusals.test_unknown_option_and_bad_combinations) ... ok
test_lint_and_hash (test_verify_amendment.RegressionColumn.test_lint_and_hash) ... ok

----------------------------------------------------------------------
Ran 15 tests in 11.829s

OK

````

### V-4B5-GREEN-round09.json

Original raw receipt SHA256 `ff24f18f4d16dfee9f4103d2623cc95a0f8b8288887b3275e8ee162e363a0f6e`; before map and after map each equal the exact common287map above. Original raw log SHA256 `350986be2da9034132ace57022ed9a329e8b3d17959f3f74fbb80a0cb882170a`.

```json
{
  "row": "V-4B5",
  "command": [
    "C:\\Users\\jquimis\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-p",
    "test_amendment_truncated_command.py",
    "-v"
  ],
  "cwd": "D:\\Fuentes\\_worktrees\\aidd-security-boundary-20261114\\publication-plan\\coherent-convergence-candidate",
  "python": "3.12.10 (tags/v3.12.10:0cc8128, Apr  8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]",
  "platform": "Windows-11-10.0.26200-SP0",
  "exitCode": 0,
  "collectedMethods": 13,
  "elapsedSeconds": 0.8600000000005821,
  "inputsStable": true,
  "logSha256": "350986be2da9034132ace57022ed9a329e8b3d17959f3f74fbb80a0cb882170a",
  "log": "D:\\Fuentes\\_worktrees\\aidd-security-boundary-20261114\\publication-plan\\final-fp-verification-20261117\\V-4B5-GREEN-round09.log",
  "status": "PASS",
  "scope": "actual isolated focused verification; no original/install/ERP result implied"
}
```

Verbatim log:

````text
test_01_truncated_direct_python_offline_hermetic_is_recovered (test_amendment_truncated_command.TruncatedCommandProof.test_01_truncated_direct_python_offline_hermetic_is_recovered) ... ok
test_02_existing_full_command_path_is_unchanged (test_amendment_truncated_command.TruncatedCommandProof.test_02_existing_full_command_path_is_unchanged) ... ok
test_03_same_prefix_different_tail_runs (test_amendment_truncated_command.TruncatedCommandProof.test_03_same_prefix_different_tail_runs) ... ok
test_04_prefix_and_length_fail_closed (test_amendment_truncated_command.TruncatedCommandProof.test_04_prefix_and_length_fail_closed) ... ok
test_05_artifact_binding_and_confinement_fail_closed (test_amendment_truncated_command.TruncatedCommandProof.test_05_artifact_binding_and_confinement_fail_closed) ... ok
test_06_stable_pass_and_expected_are_mandatory (test_amendment_truncated_command.TruncatedCommandProof.test_06_stable_pass_and_expected_are_mandatory) ... ok
test_07_inputs_proof_and_policy_are_mandatory (test_amendment_truncated_command.TruncatedCommandProof.test_07_inputs_proof_and_policy_are_mandatory) ... ok
test_08_environment_contract_proof_is_mandatory (test_amendment_truncated_command.TruncatedCommandProof.test_08_environment_contract_proof_is_mandatory) ... ok
test_09_strict_first_header_only_and_malformed_headers_run (test_amendment_truncated_command.TruncatedCommandProof.test_09_strict_first_header_only_and_malformed_headers_run) ... ok
test_10_redacted_projection_and_quoted_argument_difference_run (test_amendment_truncated_command.TruncatedCommandProof.test_10_redacted_projection_and_quoted_argument_difference_run) ... ok
test_11_forced_runs_remain_runs (test_amendment_truncated_command.TruncatedCommandProof.test_11_forced_runs_remain_runs) ... ok
test_12_current_output_and_lint_checks_remain_mandatory (test_amendment_truncated_command.TruncatedCommandProof.test_12_current_output_and_lint_checks_remain_mandatory) ... ok
test_13_database_docker_node_unknown_external_runners_never_recover (test_amendment_truncated_command.TruncatedCommandProof.test_13_database_docker_node_unknown_external_runners_never_recover) ... ok

----------------------------------------------------------------------
Ran 13 tests in 0.666s

OK

````

### V-4B6-GREEN-round09.json

Original raw receipt SHA256 `6d223ac51ff02969fa0d6a5d1a2776b74e9b163a855e8aaf327b253c4ab30900`; before map and after map each equal the exact common287map above. Original raw log SHA256 `fad0431906327bc46204e40724c1a2a3cd3b7e1d7f8a41da7b872b4f206ba427`.

```json
{
  "row": "V-4B6",
  "command": [
    "C:\\Users\\jquimis\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
    "-m",
    "unittest",
    "tests.test_aidd_rules.TestVerificationGaps",
    "tests.test_aidd_rules.TestVerificationState",
    "tests.test_aidd_rules.TestFingerprintOnce",
    "tests.test_wave_verification.WaveVerificationTests",
    "tests.test_wave_verification.WaveEndToEnd.test_multi_spec_wave_runs_shared_check_once_and_preserves_coverage",
    "tests.test_wave_verification.WaveEndToEnd.test_multi_spec_wave_does_not_reuse_undeclared_external_checks",
    "-v"
  ],
  "cwd": "D:\\Fuentes\\_worktrees\\aidd-security-boundary-20261114\\publication-plan\\coherent-convergence-candidate",
  "python": "3.12.10 (tags/v3.12.10:0cc8128, Apr  8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]",
  "platform": "Windows-11-10.0.26200-SP0",
  "exitCode": 0,
  "collectedMethods": 19,
  "elapsedSeconds": 2.735000000000582,
  "inputsStable": true,
  "logSha256": "fad0431906327bc46204e40724c1a2a3cd3b7e1d7f8a41da7b872b4f206ba427",
  "log": "D:\\Fuentes\\_worktrees\\aidd-security-boundary-20261114\\publication-plan\\final-fp-verification-20261117\\V-4B6-GREEN-round09.log",
  "status": "PASS",
  "scope": "actual isolated focused verification; no original/install/ERP result implied"
}
```

Verbatim log:

````text
test_each_gap (tests.test_aidd_rules.TestVerificationGaps.test_each_gap) ... ok
test_evidence_path_forms (tests.test_aidd_rules.TestVerificationGaps.test_evidence_path_forms) ... ok
test_old_library_and_garbage_fail_closed (tests.test_aidd_rules.TestVerificationGaps.test_old_library_and_garbage_fail_closed) ... ok
test_passing_run_absolute_and_relative (tests.test_aidd_rules.TestVerificationGaps.test_passing_run_absolute_and_relative) ... ok
test_table_and_evidence_drift (tests.test_aidd_rules.TestVerificationGaps.test_table_and_evidence_drift) ... ok
test_states (tests.test_aidd_rules.TestVerificationState.test_states) ... ok
test_cache_never_older_than_the_compared_run_or_code_edit (tests.test_aidd_rules.TestFingerprintOnce.test_cache_never_older_than_the_compared_run_or_code_edit) ... ok
test_failures_never_raise_and_fail_closed (tests.test_aidd_rules.TestFingerprintOnce.test_failures_never_raise_and_fail_closed) ... ok
test_one_fingerprint_shared_across_specs_absolute_and_relative (tests.test_aidd_rules.TestFingerprintOnce.test_one_fingerprint_shared_across_specs_absolute_and_relative) ... ok
test_explicit_inputs_do_not_trigger_round_global_scan (tests.test_wave_verification.WaveVerificationTests.test_explicit_inputs_do_not_trigger_round_global_scan) ... PASS row V-1: python check.py (exit 0, 0.0 s) → evidence/verify-V-1.txt
verify wall time 0.0 s; slowest row: V-1 (0.0 s)
ok
test_hermetic_label_without_environment_identity_cannot_reuse (tests.test_wave_verification.WaveVerificationTests.test_hermetic_label_without_environment_identity_cannot_reuse) ... ok
test_json_pass_detects_corruption_inputs_and_code_changes (tests.test_wave_verification.WaveVerificationTests.test_json_pass_detects_corruption_inputs_and_code_changes) ... ok
test_json_uses_own_result_and_redacts_diagnostics (tests.test_wave_verification.WaveVerificationTests.test_json_uses_own_result_and_redacts_diagnostics) ... ok
test_old_false_passes_are_not_reused (tests.test_wave_verification.WaveVerificationTests.test_old_false_passes_are_not_reused) ... ok
test_row_reuse_survives_failed_batch_only_with_intact_evidence (tests.test_wave_verification.WaveVerificationTests.test_row_reuse_survives_failed_batch_only_with_intact_evidence) ... ok
test_wave_id_rejects_path_traversal (tests.test_wave_verification.WaveVerificationTests.test_wave_id_rejects_path_traversal) ... ok
test_wave_requires_and_selects_every_task (tests.test_wave_verification.WaveVerificationTests.test_wave_requires_and_selects_every_task) ... ok
test_multi_spec_wave_runs_shared_check_once_and_preserves_coverage (tests.test_wave_verification.WaveEndToEnd.test_multi_spec_wave_runs_shared_check_once_and_preserves_coverage) ... ok
test_multi_spec_wave_does_not_reuse_undeclared_external_checks (tests.test_wave_verification.WaveEndToEnd.test_multi_spec_wave_does_not_reuse_undeclared_external_checks) ... ok

----------------------------------------------------------------------
Ran 19 tests in 2.457s

OK
verify_run recorded for spec: PASSED (1/1 rows, verify hash 06290775bf9b)
Refused: invalid wave ID; nothing was executed.

````

## Current impact and independent T09 evidence

Property-kind duplicate detection and same-descriptor race safeguards are exercised by17inspector methods. Graph raw Git/fsmonitor behavior is exercised by the merged Graph tests. Final T09 per-offered-pair approval safeguards are exercised by12new methods,11legacy summary-route methods and10selected hook-summary methods. The six security commands ran once against the same287-file closure. Current runtime hashes:

```json
{
  "adapters/dot-aidd/scripts/aidd_evidence.py": "9e3641692e3a7326b971b9e5143bdd5085c7356adfc3a207245f0636eedcbe86",
  "adapters/dot-aidd/scripts/aidd_graphs.py": "1293eeb3cae6dd264fa65410bf44ed1922383160d4f66651911019458d026b14",
  "adapters/dot-aidd/scripts/aidd_source_shape.py": "cc71c80afba6fbd05fc0397662d22db04ce45b232ef8a1f6b8e1fcf0e65849b8",
  "adapters/dot-aidd/scripts/aidd_status.py": "06d17ca5008f07640141a5fdf90f2208400d1e0de6c0b00761d1ce9df3d59e88",
  "adapters/dot-aidd/scripts/code_graph.py": "bcfeb0a732c6d570d6082b4198c9cb491ca249b349d09c027fa92c4a38fe90a1",
  "skill/scripts/aidd_evidence.py": "9e3641692e3a7326b971b9e5143bdd5085c7356adfc3a207245f0636eedcbe86",
  "skill/scripts/aidd_graphs.py": "1293eeb3cae6dd264fa65410bf44ed1922383160d4f66651911019458d026b14",
  "skill/scripts/aidd_source_shape.py": "cc71c80afba6fbd05fc0397662d22db04ce45b232ef8a1f6b8e1fcf0e65849b8",
  "skill/scripts/aidd_status.py": "06d17ca5008f07640141a5fdf90f2208400d1e0de6c0b00761d1ce9df3d59e88",
  "skill/scripts/code_graph.py": "bcfeb0a732c6d570d6082b4198c9cb491ca249b349d09c027fa92c4a38fe90a1"
}
```

Actual independent T09 source-review artifact (not an official unit-audit event):

````json
{
  "format": "bounded-independent-source-review-v1",
  "at": "2026-11-18T00:14:12.075181+00:00",
  "reviewer": "/root/aidd_optimization_plan_review; not T09 source author",
  "scope": "Approved T09 implementation plus targeted mixed-pair consent correction, source functional/security review only; not official unit_audit or owner seal",
  "verdict": "PASS",
  "verdicts": {
    "functional": "PASS",
    "security": "PASS"
  },
  "pins": {
    "skill/scripts/aidd_status.py": "06d17ca5008f07640141a5fdf90f2208400d1e0de6c0b00761d1ce9df3d59e88",
    "adapters/dot-aidd/scripts/aidd_status.py": "06d17ca5008f07640141a5fdf90f2208400d1e0de6c0b00761d1ce9df3d59e88",
    "tests/test_native_summary_approve_compat.py": "b23ecc80b46050927cbbbd5240dd2ccec548e820e375e33502fba034bcdf0523"
  },
  "resolvedFailureReport": {
    "path": "D:\\Fuentes\\_worktrees\\release-preflight-20261116\\native-summary-policy-independent-source-review-failed.json",
    "sha256": "179784f67010926e79648fd40cf30bd778b087fa328ffc133602391eef25e9b7"
  },
  "checks": [
    "The reported mixed-pair trampoline is closed: each matching pair now validates its own offered options/index before the legacy Spanish return. An unoffered Spanish pair is skipped; the following English pair still faces exact offered label, known same session, native question anchor and positive summary intent. Missing options preserves the existing Spanish route because the added guard runs only for list options.",
    "Reviewed the new two-subcase regression: first pair is unoffered Spanish, second pair is English with either plain intent or unknown session; native public API fixtures include actual pairs/options. The original body returned an event in both actual RED subcases, while final GREEN reports the full12 methods passed.",
    "The remaining approved security contract remains intact: one newest-answer lookup, no retry of older consent, exact current tag, exact English label and offered option, time/session bounds, one matching prior native question/tool/options anchor, closed positive-intent grammar and original-event return without approval writes.",
    "Canonical/mirror full SHA256 match. Apart from _summary_answer and its one new private grammar predicate, every pre-existing top-level function/class AST equals current Main; generic evidence APIs, unit consent, hook delegation and other status behavior are unchanged.",
    "No actual owner question/answer, option, timestamp, task hash, review file or historical consent is rewritten. Root remains responsible for normal official approval from its genuine session; this source review is not a substitute approval."
  ],
  "currentEvidence": {
    "finalFocused": "Actual final log:12 tests PASS in1.594s on final helper; reviewer did not execute tests.",
    "mixedPairRED": "Actual one-method RED:two failing subcases on vulnerable helper before correction.",
    "legacyHistorical": "Existing TestSummaryRoute11PASS/32.193s log belongs to earlier13483 helper, not relabelled as a post-microfix run. Final12 includes legacy positive checks; final coordinated cohort/official audits remain separate."
  },
  "logs": {
    "native-summary-policy-RED.log": "8fee7ffa8efc426943242ab322418af8542e4139683089bc213f2559510ba2c9",
    "native-summary-policy-GREEN.log": "6c53ae0afb85904583fb3c90d29da6e0739cd836c2bbe9c90978803a7ca21e25",
    "native-summary-policy-EXISTING-GREEN.log": "4cb40fb1b735ade03b0b72348ffa0ba041e02e6396a53a50aec5f59685b975c4",
    "native-summary-policy-mixed-pair-RED.log": "ab53d3563a1a08369e043010362599a1269380031ff41f0e9d89431121a4e611",
    "native-summary-policy-FINAL-GREEN.log": "fb8bd25fea9b5a040b08b4295651bec9f42383889ff913aeac190f2b8a520dad"
  },
  "unchangedExistingTopLevelASTCount": 141,
  "blockingFindings": [],
  "reportedSizeVariance": "205 actual changed canonical/test lines versus forecast140 is recorded by author receipt; same approved3files and semantics, tests retained readable, no new scope inferred.",
  "reviewerRuntimeTests": 0,
  "reviewerDBRuns": 0,
  "reviewerSourceWrites": 0,
  "reviewerApprovalOrUnitAuditWrites": 0,
  "integrationBoundary": "PASS permits Root to proceed with its authorized controlled integration and normal F12 approval; final release still requires the coordinated current cohort and genuine official unit audit gates."
}

````

## Canonical T09 requirements, plan and tasks

### specs/008-aidd-compact-review-direct-save/spec-amendment-native-summary-approve.md

SHA256 `fd1033cad979f0c22876bc0767b49d3a3be498fc6e97327525ec78a9d31a0274`.

````markdown
# Spec amendment — AIDD 008 native explicit-summary Approve compatibility

PROPOSED policy extension to existing FR-313 / AC-327, not a repeat of F12 approval. AIDD intake: AMENDMENT — Fast Lane — one contained consent-recognition extension; no implementation yet.

The owner genuinely chose English Approve for a trusted native question explicitly asking “¿Apruebas con resumen … [tasks:hash]?” Current exact-label Spanish summary policy rejects that choice and routes to an unrelated stale review page. Preserve the genuine question, offered labels and answer unchanged. This amendment deliberately extends semantic policy and needs its own new owner approval.

## Scope

Exactly three implementation files: `skill/scripts/aidd_status.py`, `adapters/dot-aidd/scripts/aidd_status.py`, `tests/test_native_summary_approve_compat.py`. No evidence, review documents, task seals, generic answer API, unit-consent API or hooks are rewritten. Existing hook delegates to the canonical helper.

## Functional requirements

- FR-313-N1: Preserve existing exact Spanish `Aprobar con resumen` behaviour, including its current spacing handling and old regression cases.
- FR-313-N2: English choice must be exactly `Approve` after stripping outer whitespace, explicitly offered as `Approve`, from the newest trusted answer for the current tag and exact known session, after since_ts and not in the future.
- FR-313-N3: English question must start with positive explicit `¿Apruebas con resumen` intent and include the current tag in its initial question clause. Reject negated, quoted, conditional or alternative-mode intent. Unrelated narrative such as “No cambian producción” after the initial question must remain valid.
- FR-313-N4: English path requires a matching earlier trusted question event, same session/tool_use_id, question text and offered options. No typed prompt, raw answer text, missing/ambiguous anchor, nonoffered option, wrong tag, stale event or cross-session event establishes summary consent.
- FR-313-N5: Newest topical answer for the current tag is authoritative: a newer rejection, plain/ambiguous Approve or invalid offered label cancels an older eligible response. Do not retry older events through a second fallback query.
- FR-313-N6: Return the original evidence event, never rewrite its chosen label, options, native provenance, task hash or timestamp. Existing cmd_approve then records the supported summary route normally; no approval event is appended by the helper.

## Closed recognition grammar

For the new English branch only: normalize whitespace for analysis but retain original stored data. Initial clause ends at the first `?` and must begin `¿Apruebas con resumen ` (case-insensitive; repeated spaces allowed). It must contain the exact current task tag; it must contain none of the standalone tokens `no`, `sin`, `o`, `si`, `cuando`, `u`, `versus`, `vs`, none of the phrases `siempre que`, `en caso de`, `sujeto a`, `condicionado a`, `a condición de`, `hasta que`, and no quote/backtick prefix. Reject explicit approval negation anywhere in the question: `no aprobar`, `no apruebes`, `no apruebas`, `no autorizo`, `sin aprobar`, `nunca aprobar`. This intentionally conservative grammar does not accept other English/Spanish summary phrasings. Keep the legacy Spanish-label branch independent of this new grammar.

## Acceptance cases

1. Native exact question shape with current tag, offered Approve, exact same session, trusted question+answer and fresh timestamp returns the original event. Include the narrative “No cambian producción” to prevent overbroad negation matching.
2. Exact legacy Spanish-label route remains accepted and its existing negative-label cases remain refused.
3. Eight negative groups in T-09 all return None and create no approved event.

## Verification and budget

Only focused stdlib unittest commands in the task; no database, network or full regression suite. Estimated ten agent minutes including independent review. The current F12 decision remains unchanged. Root, from the genuine Root session, re-invokes ordinary official rules approve after this NEW policy change passes and is integrated. Never widen the policy to accept a child session merely to make the command convenient.

````

### specs/008-aidd-compact-review-direct-save/plan-native-summary-approve.md

SHA256 `420ecc7c98aa2b90c10b0b39083c0922418d508d2b09f678462cdb6b6ee9b0d6`.

````markdown
# Plan — AIDD 008 native explicit-summary Approve compatibility

PROPOSED; copied from matching plan template sections. Independent Root R5 review and a new actual owner decision are required before code edits.

## Naming & File Contract (fill this first — everything below depends on it)

| Item | Convention |
|---|---|
| Functions | Preserve `_summary_answer(ev, root, session, since, tag)` signature and returned original event/None |
| Private helper | `_native_summary_approve_question(question, tag)` returns bool; canonical module only, mirrored identically |
| Constants | `_SUMMARY_NATIVE_LABEL_RE`; exact legacy SUMMARY_LABEL unchanged |
| Files | Canonical script, existing adapter mirror, one focused unittest file |

## Component → Code map

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Explicitly out of scope |
|---|---|---|---|---|
| T-09 | FR-313-N1..N6, existing FR-313/AC-327 extension | `skill/scripts/aidd_status.py` + `adapters/dot-aidd/scripts/aidd_status.py` + `tests/test_native_summary_approve_compat.py` | LOGIC | Evidence files, generic consent APIs, unit seals, production/database work |

## Implementation sequence

1. Add focused RED tests using real public question/answer APIs in temporary test projects; do not represent a synthetic test event as actual owner approval.
2. Extend only the canonical summary helper and its private positive-question predicate. Query newest topical answer once with labels admitting the legacy exact label or new exact Approve; evaluate that newest event only. Preserve Spanish branch behaviour. English branch additionally validates exact known session, freshness, native tool anchor, exact offered label and the closed positive-intent grammar.
3. Copy canonical script to existing adapter mirror through a SHA-guarded mapping, preserving existing mirror policy. No hook source changes: current hook delegates to this helper.
4. Run only focused new tests and existing summary-route regressions; independently review consent negatives, mirror parity and untouched native evidence. Main integration invalidates relevant audit snapshots, so Root coordinates the final actual audit cohort rather than reusing earlier reports blindly.
5. Root invokes ordinary approval from its own genuine session for the unchanged actual F12 decision. This is verification of the new recognizer, not a new F12 question or a forged summary label.

Tools first: one mapping script with dry-run/apply/post-check; never bulk-edit mirrors by hand. Native AIDD graph first, then only named source ranges. No database creation or access; if a later unrelated task needs a DB, only db_verify default or slots1..3. No global tests, hook/rules overrides, fabricated approvals, review-checkbox edits or answer relabeling.

````

### specs/008-aidd-compact-review-direct-save/tasks-native-summary-approve.md

SHA256 `b32c7e2329aa0c7809aa2171163409efb5f2f2e2c5c06864fe817908014357f1`.

````markdown
# Tasks — AIDD 008 native explicit-summary Approve compatibility

PROPOSED. New semantic policy extension, separate from already genuine F12 approval. No source implementation is authorized until its own actual owner approval. Derived from matching tasks template.

Tools first: one mapping script with dry-run/apply/post-check; never bulk-edit mirrors by hand. Native AIDD graph first, then only named source ranges. No database creation or access; if a later unrelated task needs a DB, only db_verify default or slots1..3. No global tests, hook/rules overrides, fabricated approvals, review-checkbox edits or answer relabeling.

## File-Change Map (MANDATORY — the contract between spec and code)

| Task | Codes satisfied (SCREEN/COMP/CTL/API) | Target file | View / logic | Explicitly out of scope |
|---|---|---|---|---|
| T-09 | FR-313-N1..N6; FR-313 / AC-327 extension | `skill/scripts/aidd_status.py` + `adapters/dot-aidd/scripts/aidd_status.py` + `tests/test_native_summary_approve_compat.py` | LOGIC | Generic consent APIs, hook changes, evidence rewrites, task seals, DB or production |

## Per-task detail (one block per row above)

### T-09 — Recognize a genuine native explicit-summary English Approve
**Classify**
- Nature: INCIDENT
- Priority: 2 HIGH
- Kind: LOGIC
- Status: PROPOSED
- Size: 140 changed canonical/test lines maximum, plus mechanically identical mirror delta.
**Estimate**
- Effort: Medium
- Agent min: 10
- Human ref hours: 0.5
- Tokens (est): 16k
- Agent role: builder
- Model tier: high
**Decompose**
- Goal: Accept the original native English Approve only for an explicitly positive summary question while preserving all existing Spanish consent and refusal semantics.
- Cites: existing `specs/008-aidd-compact-review-direct-save/spec.md` FR-313 and AC-327; proposal `spec-amendment-native-summary-approve.md` FR-313-N1..N6 and Closed recognition grammar.
- Depends on: actual new owner approval and independent Root pre-build plan review; not a repeat approval of F12 tasks.
- Read first: `skill/scripts/aidd_status.py:1407`; `skill/scripts/aidd_evidence.py:1626`; `skill/hooks/rule_gate.py:450`; `tests/test_aidd_status.py:1805`; `specs/008-aidd-compact-review-direct-save/spec.md:83`; `specs/008-aidd-compact-review-direct-save/spec.md:117`.
- Files to change: `skill/scripts/aidd_status.py`, `adapters/dot-aidd/scripts/aidd_status.py`, `tests/test_native_summary_approve_compat.py`.
- Naming contract: `_summary_answer(ev, root, session, since, tag)` unchanged; private `_native_summary_approve_question(question, tag)` returns bool; `_SUMMARY_NATIVE_LABEL_RE`; existing SUMMARY_LABEL stays exactly Aprobar con resumen. Test class `TestNativeSummaryApproveCompat`, with helper `_record_native_answer` using existing public ev.append_question/ev.append_answer and synthetic callback IDs.
- Behaviour: (1) Preserve legacy exact-label Spanish path. (2) Select newest topical current-tag answer only once using existing ev._answer_event trust boundary; both exact legacy and exact English labels may reach branch validation, but newer rejection/invalid intent must terminate with None, never revive older consent. (3) English requires exact stripped Approve and exact offered Approve at the matching pair index, known same session, since < answer.ts <= time.time()+1, nonempty matching native tool_use_id and one preceding same-session question anchor with matching question/options. (4) Apply the exact closed grammar in the amendment: anchored positive initial question and same current tag, no no/sin/o/si/cuando/u/versus/vs token or siempre que/en caso de/sujeto a/condicionado a/a condición de/hasta que phrase in that clause, and no listed approval-negation phrase anywhere; unrelated post-question No cambian producción is allowed. (5) Return the original event or None; append no approvals and modify no evidence. (6) Mirror the canonical change with a SHA-guarded script; no hook or generic API changes.
- Tests first: Create the focused file using `Spec007Base` from `test_aidd_status` under unittest discovery and actual public ev APIs in temporary test projects. Positive cases: `test_native_explicit_summary_approve_accepts_original_event` with current synthetic [tasks:1234abcd], real question+answer anchor and unrelated narrative No cambian producción; `test_legacy_spanish_summary_route_unchanged`. Eight negative methods, with subTests for listed variants (the conditional/alternative group must include siempre que, cuando, en caso de, sujeto a, condicionado a, a condición de, hasta que, u otra modalidad, versus HTML and vs HTML): `test_plain_approve_without_summary_intent_refused`; `test_negated_quoted_conditional_or_alternative_intent_refused`; `test_nonoffered_or_mismatched_question_anchor_refused`; `test_wrong_or_missing_task_tag_refused`; `test_stale_or_future_answer_refused`; `test_wrong_or_unknown_session_refused`; `test_typed_or_forged_raw_answer_refused`; `test_newer_rejection_or_invalid_intent_cancels_older_consent`. Every refusal returns None and leaves approved-event count zero. Add `test_adapter_mirror_matches_canonical_summary_implementation` without editing unrelated mirror content. First demonstrate the new positive case RED on current source; existing refusal cases may already pass and must not be claimed RED.
- Verify: From D:/Fuentes/AIDD run `python -m unittest discover -s tests -p test_native_summary_approve_compat.py -v` -> exit 0, all new cases pass; `python -m unittest discover -s tests -p test_aidd_status.py -k TestSummaryRoute -v` -> exit 0, existing summary-route cases pass. Root independently reviews exact diff, native question/answer preservation and mirror mapping. No runtime is claimed from source inspection.
- Do NOT: change SUMMARY_LABEL, relabel Approve to Spanish, write review.md checkmarks or Approved lines, append synthetic approval events, accept typed prompts/raw text/nonoffered labels, permit child/cross-session consent, weaken existing Spanish route, run DB/global tests, disable hooks/rules, modify manifests/seals or historical audits, install an ad hoc helper/profile, repeat the old F12 approval question.
- Done when: both positive cases and all eight negative groups pass; newest-answer cancellation is proven; legacy tests stay green; mirror is exact for changed implementation; original actual F12 question/answer remains byte-for-byte unchanged; independent review passes before integration.
- Open questions:

## Waves

| Wave | Tasks | Roles | Agent time (min) | Tokens (k) | Human ref (h) |
|---|---|---|---|---|---|
| 008-NATIVE-1 | T-09 | builder | 10 | 16 | 0.5 |

Total agent time (critical path): 10 min
Total tokens (k): 16

## Approval gate

PROPOSED — present this NEW policy extension after independent Root R5 review. The question must offer the exact existing option Aprobar con resumen. This approval is for T-09, not the already authorized F12 work. Do not write an approval line by hand.

````

## Authentic T09 approval and R5 registration

These are genuine recorded receipts, not newly emitted decisions. They retain origin/callback/task9d28a24a080a binding and their original bytes in the archive.

### native-summary-policy-owner-registration.json

SHA256 `71fb7d0f4698327ac6e23c0244bbd8673f8a98e0060ae7018e3ebed650de7359`.

````json
{
  "origin": "Actual native full question and exact user reply validated; faithful public API registration",
  "callback": "call_f9816b9c025148c2b48d6ef57c3aac67",
  "question": "¿Autorizas aprobar con resumen la nueva tarea de AIDD [tasks:9d28a24a]? Aceptará «Approve» solo ante una pregunta explícita de aprobación con resumen, con respuesta auténtica, opción ofrecida, sesión y versión correctas. Incluye pruebas positivas y negativas; conserva los rechazos y tu respuesta original de F12. Revisión independiente PASS.",
  "questionSHA256": "dfca81b58bdbb71595403681e5122cf92e654c022f8479f49f2812a407f90b04",
  "questionLength": 342,
  "options": [
    "Aprobar con resumen",
    "Solicitar cambios"
  ],
  "answer": "Aprobar con resumen",
  "aggregateTasksHash": "9d28a24a080a",
  "taskFileSHA256": "b32c7e2329aa0c7809aa2171163409efb5f2f2e2c5c06864fe817908014357f1",
  "nativeSource": "C:\\Users\\jquimis\\.codex\\sessions\\2026\\11\\08\\rollout-2026-11-08T06-01-23-01a1bad1-eed0-7ae0-b417-8b56ef653d28.jsonl",
  "nativeRecords": {
    "question": {
      "timestamp": "2026-11-17T23:51:28.978Z",
      "recordSHA256": "b565dc36c927d8212eb4b3dfd9c318f43e3937e458d2bf91dd42d1c445c044f3"
    },
    "answer": {
      "timestamp": "2026-11-17T23:52:10.809Z",
      "recordSHA256": "f0e4ed68d1523e9c14b5fb6e4054f77885cf12dc85622fa0822bea22e3a5acc9"
    }
  },
  "registeredAnswerCount": 1,
  "ownerApprovalLineWritten": false,
  "cmdApproveExecuted": false
}
````

### native-summary-policy-r5-registration.json

SHA256 `6c65ca379a1252d3a31d5ae23b1b8ecc540d09f57dc6ffb0708dbbd6d5921fee`.

````json
{
  "action": "REGISTERED_PUBLIC_API",
  "detail": {
    "phase": "post",
    "type": "codex_native_plan_auditor",
    "model": "gpt-6.1-sol",
    "head": "Independent R5 plan review: AIDD008 native explicit-summary Approve compatibility",
    "desc": "Genuine independent R5 PASS for one proposed T-09 semantic consent policy extension. Conditional/alternative-intent finding fixed before owner approval. Exact task bytes b32c7e... promoted unchanged into canonical metadata; aggregate9d28a24a080a. No implementation/runtime approval claimed.",
    "tool_use_id": "call_ba5e53ab12084d9f8e797e26734d6e48",
    "child_thread_id": "01a1da49-659f-7e92-8773-05b44965e4e4",
    "child_turn_id": "01a1ebe7-0e3f-7421-9cc4-8c9cb6c521f5",
    "result_chars": 4562,
    "result_sha256": "81ce3165aeab5eac2f30af433b85139773bad6c6cc222e9da2dd9593ccd63e79",
    "report_path": "D:\\Fuentes\\_worktrees\\release-preflight-20261116\\aidd-008-native-summary-approve-proposal\\R5-independent-plan-review.json",
    "origin": "codex_native",
    "registration": "manual_public_api",
    "tasks_hash": "9d28a24a080a",
    "task_file_sha256": "b32c7e2329aa0c7809aa2171163409efb5f2f2e2c5c06864fe817908014357f1",
    "dispatch_proof": {
      "timestamp": "2026-11-17T23:45:50.602Z",
      "record_sha256": "abdd82adf046bf2a6f1cfb574034073b0aaa003fbac66cd4c4268bbf28d9fde4",
      "source": "C:\\Users\\jquimis\\.codex\\sessions\\2026\\11\\08\\rollout-2026-11-08T06-01-23-01a1bad1-eed0-7ae0-b417-8b56ef653d28.jsonl",
      "tool_use_id": "call_ba5e53ab12084d9f8e797e26734d6e48",
      "actual_target": "/root/aidd_optimization_plan_review"
    },
    "model_source": {
      "timestamp": "2026-11-17T23:45:51.448Z",
      "record_sha256": "174e5a29306f07534fce4a410f6926882483bf974be662fa4702bf38a8bf64b6",
      "source": "C:\\Users\\jquimis\\.codex\\sessions\\2026\\11\\14\\rollout-2026-11-14T08-40-05-01a1da49-659f-7e92-8773-05b44965e4e4.jsonl",
      "model": "gpt-6.1-sol"
    },
    "start_proof": {
      "timestamp": "2026-11-17T23:45:50.717Z",
      "record_sha256": "97dae11611e5717d38d31b0e6a9282a5dcb1616693fb978236ae04f4c953391e",
      "source": "C:\\Users\\jquimis\\.codex\\sessions\\2026\\11\\14\\rollout-2026-11-14T08-40-05-01a1da49-659f-7e92-8773-05b44965e4e4.jsonl"
    },
    "completion_proof": {
      "timestamp": "2026-11-17T23:50:50.795Z",
      "record_sha256": "7f2e8d54f5561560729b336c91ea0ea23a7a618d7df7441060385dd2666c2f32",
      "source": "C:\\Users\\jquimis\\.codex\\sessions\\2026\\11\\14\\rollout-2026-11-14T08-40-05-01a1da49-659f-7e92-8773-05b44965e4e4.jsonl"
    },
    "scope_binding": "Frozen proposed task bytes reviewed independently and promoted unchanged into three canonical planning files; no code or owner seal changed by this registration."
  },
  "owner_approval_written": false
}
````

## Supplementary final fingerprint evidence — not added to cohort totals

{
  "reviewPath": "raw-worktree-fingerprint-independent-source-review.json",
  "reviewSha256": "972f1ed3e85764c159a9592ebcc965e5a6214c3584e451ce98ec3fe267a31bd3",
  "logPath": "worktree-fingerprint-FINAL-GREEN.log",
  "logSha256": "1ec95f9f8223e3558fc93ed432efe1467951bc94b94a1fd455b13685a1983e8b",
  "actualMethods": 30,
  "actualSeconds": 8.234,
  "actualCommandVerbatimForwardedByRoot": "python -B -m unittest tests.test_dry_run_identity_security.FullDryRunTrackedFilterSecurity tests.test_evidence.TestWorktreeFingerprint tests.test_code_fingerprint -v",
  "actualCwd": "D:/Fuentes/_worktrees/aidd-security-boundary-20261114/publication-plan/coherent-convergence-candidate",
  "codeBefore": "Root confirmed author frozen evidence9e364169 handoff before execution",
  "full287BeforeAfterRecorded": false,
  "nonAdditive": "Overlaps existing coverage; not added to263cohort methods. No full287pre/post snapshot is fabricated for this supplementary30run."
}

The independently reviewed fingerprint fix removes reachable Git diff/filter execution. Its separate30-method Root run overlaps existing coverage; it is not added to the263cohort total. No full287-input before/after snapshot was recorded for that supplementary30run, and none is inferred. The current263cohort does have the complete287-input before/after binding.

### batch-staging/aidd-final-fp-convergence-20261117/proof/raw-worktree-fingerprint-independent-source-review.json

SHA256 `972f1ed3e85764c159a9592ebcc965e5a6214c3584e451ce98ec3fe267a31bd3`.

````text
{
  "format": "bounded-independent-functional-security-source-review-v1",
  "at": "2026-11-18T01:27:25.274810+00:00",
  "reviewer": "/root/aidd_optimization_plan_review; not raw worktree fingerprint implementation author",
  "scope": "Existing4b no-repository-execution corrective worktree fingerprint change; exact final source, no unit consent or official unit_audit emitted",
  "verdict": "PASS",
  "verdicts": {
    "functional": "PASS",
    "security": "PASS"
  },
  "pins": {
    "skill/scripts/aidd_evidence.py": "9e3641692e3a7326b971b9e5143bdd5085c7356adfc3a207245f0636eedcbe86",
    "adapters/dot-aidd/scripts/aidd_evidence.py": "9e3641692e3a7326b971b9e5143bdd5085c7356adfc3a207245f0636eedcbe86",
    "tests/test_dry_run_identity_security.py": "11acd8e0cada45c92c5fb101ba43e5f8c5a6c4df3539a380930d6d6c410b31c8"
  },
  "checks": [
    "The reachable unsafe git diff HEAD path is removed. Whole-tree Git fingerprint uses rev-parse HEAD and ls-files metadata only, then reads raw file bytes or symlink text in Python; no diff/status/textconv/clean-filter command is invoked.",
    "core.fsmonitor=false and core.untrackedCache=false are applied in _fp_git globally with GIT_OPTIONAL_LOCKS=0. This covers inventory reached through code_state with absent/default Scope as well as declared Scope, not only the whole-tree helper. Remaining direct _blob_shas uses fixed hash-object --no-filters --stdin-paths and is unchanged.",
    "Raw paths reject absolute/empty/traversal/colon segments and a single backslash before Windows path joining. Ancestors reject symlinks, junctions and Windows REPARSE_POINT attributes, including Python3.10 where Path.is_junction is absent. AST inspection confirms the backslash literal is exactly one codepoint92.",
    "Regular reads are bounded to1MiB+1 and validate lstat/opened descriptor metadata before and after reading plus final path metadata. Files above1MiB retain the documented size/mtime contract rather than being streamed without limit. Symlinks hash their own text via readlink and repeated metadata checks, not target contents.",
    "Deleted/unreadable inputs, unsafe types/gitlinks and unmerged index stages fail closed. _FpInputUnsafe is separate from _FpUnavailable, so unsafe inputs do not fall through to mtime-only fallback; public result remains16hex orNone. File-count/budget caps and non-Git fallback contract remain.",
    "Fingerprint includes HEAD, raw path/type/mode/content identity and a new raw-v2 salt; index object IDs are not salted, preserving stability when git add records unchanged working-tree bytes. All pre-existing top-level functions/classes outside the named fingerprint helpers remain AST-identical to Main.",
    "Inspected actual final Root log:30 tests PASS in8.234s, comprising the two real full CLI clean-filter regressions and28 existing worktree/code fingerprint tests. New tests establish a real positive clean-filter control and ensure dry runs do not run the verification sentinel. Reviewer performed no runtime tests."
  ],
  "unchangedExistingTopLevelASTCount": 127,
  "actualFinalEvidence": {
    "path": "D:\\Fuentes\\_worktrees\\release-preflight-20261116\\worktree-fingerprint-FINAL-GREEN.log",
    "sha256": "1ec95f9f8223e3558fc93ed432efe1467951bc94b94a1fd455b13685a1983e8b",
    "methods": 30,
    "seconds": 8.234,
    "status": "PASS"
  },
  "historicalEvidence": {
    "worktree-fingerprint-filter-RED.log": "149e71dc4c912bbdb5eea74aa07e1cfd12f172b1c71b1f9652e87b7aee766522",
    "worktree-fingerprint-filter-GREEN.log": "44af8bb1c2d57a79a3ad0a33e4293ab63f13ffc1805bf62df9247b23d3c18ed7",
    "worktree-fingerprint-existing-GREEN.log": "cf3de0b76458d1dc713b09013ef58495f9bfd4e4646bccd5d79ec3d16462a739",
    "raw-worktree-fingerprint-final-guards.diff": "b66a0b62aed66af899fd0e4852978782b501ee016108923a4035a32c3721d3bb"
  },
  "blockingFindings": [],
  "limits": [
    "Scope-absence Git reachability was traced statically through the same guarded inventory; no additional runtime case is claimed beyond the actual30-test log.",
    "Metadata stability checks cover observable state changes, not an OS-atomic snapshot under an adversary capable of restoring every observed attribute. Large-file metadata behavior is preserved deliberately.",
    "This bounded source PASS supports Root controlled publication of its authorized three files. Final current cohort, proof publication and official native unit audits remain separate gates."
  ],
  "reviewerRuntimeTests": 0,
  "reviewerDBRuns": 0,
  "reviewerSourceWrites": 0,
  "reviewerMainOrInstalledWrites": 0,
  "reviewerApprovalOrOfficialUnitAuditWrites": 0
}

````

### batch-staging/aidd-final-fp-convergence-20261117/proof/worktree-fingerprint-FINAL-GREEN.log

SHA256 `1ec95f9f8223e3558fc93ed432efe1467951bc94b94a1fd455b13685a1983e8b`.

````text
test_13_actual_amendment_dry_run_does_not_execute_tracked_clean_filter (tests.test_dry_run_identity_security.FullDryRunTrackedFilterSecurity.test_13_actual_amendment_dry_run_does_not_execute_tracked_clean_filter) ... ok
test_14_actual_round_dry_run_does_not_execute_tracked_clean_filter (tests.test_dry_run_identity_security.FullDryRunTrackedFilterSecurity.test_14_actual_round_dry_run_does_not_execute_tracked_clean_filter) ... ok
test_git_missing_falls_back_to_mtimes (tests.test_evidence.TestWorktreeFingerprint.test_git_missing_falls_back_to_mtimes) ... ok
test_git_repo (tests.test_evidence.TestWorktreeFingerprint.test_git_repo) ... ok
test_non_git_dir_uses_mtime_fallback (tests.test_evidence.TestWorktreeFingerprint.test_non_git_dir_uses_mtime_fallback) ... ok
test_over_file_cap_or_budget_is_none (tests.test_evidence.TestWorktreeFingerprint.test_over_file_cap_or_budget_is_none) ... ok
test_commit_does_not_change_it (tests.test_code_fingerprint.TestCodeFingerprint.test_commit_does_not_change_it) ... ok
test_doc_and_spec_edits_do_not_change_it_but_code_does (tests.test_code_fingerprint.TestCodeFingerprint.test_doc_and_spec_edits_do_not_change_it_but_code_does) ... ok
test_git_listed_sql_read_error_never_uses_fallback (tests.test_code_fingerprint.TestCodeFingerprint.test_git_listed_sql_read_error_never_uses_fallback) ... ok
test_git_unavailable_still_uses_fallback (tests.test_code_fingerprint.TestCodeFingerprint.test_git_unavailable_still_uses_fallback) ... ok
test_large_sql_is_hashed_as_raw_bytes (tests.test_code_fingerprint.TestCodeFingerprint.test_large_sql_is_hashed_as_raw_bytes) ... ok
test_listed_missing_sql_never_uses_git_fallback (tests.test_code_fingerprint.TestCodeFingerprint.test_listed_missing_sql_never_uses_git_fallback) ... ok
test_prefix_and_none_for_missing_root (tests.test_code_fingerprint.TestCodeFingerprint.test_prefix_and_none_for_missing_root) ... ok
test_sql_change_during_read_with_restored_mtime_is_unsafe (tests.test_code_fingerprint.TestCodeFingerprint.test_sql_change_during_read_with_restored_mtime_is_unsafe) ... ok
test_sql_deadline_exhaustion_refuses_snapshot (tests.test_code_fingerprint.TestCodeFingerprint.test_sql_deadline_exhaustion_refuses_snapshot) ... ok
test_sql_raw_bytes_and_restored_metadata_for_both_backends (tests.test_code_fingerprint.TestCodeFingerprint.test_sql_raw_bytes_and_restored_metadata_for_both_backends) ... ok
test_untracked_code_file_counts_deleted_file_counts (tests.test_code_fingerprint.TestCodeFingerprint.test_untracked_code_file_counts_deleted_file_counts) ... ok
test_changed_command_or_new_row_is_not (tests.test_code_fingerprint.TestRowsAlreadyExecuted.test_changed_command_or_new_row_is_not) ... ok
test_legacy_run_without_code_fingerprint_or_expected_is_not (tests.test_code_fingerprint.TestRowsAlreadyExecuted.test_legacy_run_without_code_fingerprint_or_expected_is_not) ... ok
test_wording_and_covers_edits_are_covered_by_the_run (tests.test_code_fingerprint.TestRowsAlreadyExecuted.test_wording_and_covers_edits_are_covered_by_the_run) ... ok
test_invalid_generated_does_not_hide_recorded_code_edits (tests.test_code_fingerprint.TestScope.test_invalid_generated_does_not_hide_recorded_code_edits) ... ok
test_invalid_patterns_fail_closed (tests.test_code_fingerprint.TestScope.test_invalid_patterns_fail_closed) ... ok
test_last_code_edit_ts_with_scope (tests.test_code_fingerprint.TestScope.test_last_code_edit_ts_with_scope) ... ok
test_placeholder_and_empty_scopes_are_never_trusted (tests.test_code_fingerprint.TestScope.test_placeholder_and_empty_scopes_are_never_trusted) ... ok
test_scope_auto_takes_the_task_target_files (tests.test_code_fingerprint.TestScope.test_scope_auto_takes_the_task_target_files) ... ok
test_scoped_fingerprint_ignores_other_specs_but_not_its_own_files (tests.test_code_fingerprint.TestScope.test_scoped_fingerprint_ignores_other_specs_but_not_its_own_files) ... ok
test_segment_patterns_and_character_classes (tests.test_code_fingerprint.TestScope.test_segment_patterns_and_character_classes) ... ok
test_the_shipped_template_declares_scope_auto_and_it_parses (tests.test_code_fingerprint.TestScope.test_the_shipped_template_declares_scope_auto_and_it_parses) ... ok
test_valid_patterns_match_pathlib_for_representative_files (tests.test_code_fingerprint.TestScope.test_valid_patterns_match_pathlib_for_representative_files) ... ok
test_verification_scope_parsing (tests.test_code_fingerprint.TestScope.test_verification_scope_parsing) ... ok

----------------------------------------------------------------------
Ran 30 tests in 8.234s

OK

````

## PowerShell/.NET read-only archive verification — no Python required

Run from the repository root. This code reads only this document and the25explicit metadata-declared current Python files listed in the snippet. It writes nothing, runs no product tests and reads no external evidence paths. It checks compressed/expanded lengths and SHA256, reconstructs25original artifact byte sequences, verifies every original byte length/hash, all8receipt/log bindings, both287maps, actual scoped source hashes, counts and independent T09 review.

The GZIP archive uses an exact-text dictionary only to avoid storing identical large287maps17times. Literal marker replacement restores original UTF-8 bytes before SHA checking; it does not alter metadata semantics or receipt files. Raw archive JSON bytes:142509; SHA256 `909adeeded59b5fd3deffa155088aeab437abc51b0c2d8ae08509768e6c649c6`. GZIP bytes:37734; SHA256 `f73c37785ec43991be1820b116ff15b3e8085dbf248a73c0e7d53398c77110d7`.

```powershell
$ErrorActionPreference = 'Stop'
$repoRoot = (Get-Location).Path
function Hash-Bytes([byte[]]$bytes) {
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hasher.ComputeHash($bytes))).Replace('-','').ToLowerInvariant() }
    finally { $hasher.Dispose() }
}
$text = [IO.File]::ReadAllText((Join-Path $repoRoot 'docs/aidd-graph-fresh-query.md'))
$pattern = [regex]::Escape('<!-- CURRENT-LOSSLESS-GZIP:BEGIN -->') + '\s*([A-Za-z0-9+/=\s]+?)\s*' + [regex]::Escape('<!-- CURRENT-LOSSLESS-GZIP:END -->')
$match = [regex]::Match($text, $pattern)
if (-not $match.Success) { throw 'GZIP evidence block missing' }
[byte[]]$compressed = [Convert]::FromBase64String(($match.Groups[1].Value -replace '\s',''))
if ($compressed.Length -ne 37734 -or (Hash-Bytes $compressed) -cne 'f73c37785ec43991be1820b116ff15b3e8085dbf248a73c0e7d53398c77110d7') { throw 'GZIP length/hash mismatch' }
$inputStream = [IO.MemoryStream]::new($compressed, $false)
$gzip = [IO.Compression.GZipStream]::new($inputStream, [IO.Compression.CompressionMode]::Decompress)
$outputStream = [IO.MemoryStream]::new()
try {
    [byte[]]$buffer = [byte[]]::new(8192)
    while (($count = $gzip.Read($buffer,0,$buffer.Length)) -gt 0) {
        if (($outputStream.Length + $count) -gt 142509) { throw 'Evidence expansion exceeds bound' }
        $outputStream.Write($buffer,0,$count)
    }
    [byte[]]$expanded = $outputStream.ToArray()
} finally { $gzip.Dispose(); $inputStream.Dispose(); $outputStream.Dispose() }
if ($expanded.Length -ne 142509 -or (Hash-Bytes $expanded) -cne '909adeeded59b5fd3deffa155088aeab437abc51b0c2d8ae08509768e6c649c6') { throw 'Expanded evidence length/hash mismatch' }
$utf8 = [Text.UTF8Encoding]::new($false, $true)
$bundle = $utf8.GetString($expanded) | ConvertFrom-Json
$artifacts = @{}
foreach ($item in $bundle.artifacts.PSObject.Properties) {
    $restored = [string]$item.Value.rawUtf8WithMapMarkers
    foreach ($part in $bundle.exactSharedMapText.PSObject.Properties) { $restored = $restored.Replace($part.Name, [string]$part.Value) }
    [byte[]]$bytes = $utf8.GetBytes($restored)
    if ($bytes.Length -ne $item.Value.byteLength -or (Hash-Bytes $bytes) -cne $item.Value.sha256) { throw ('Original artifact mismatch: ' + $item.Name) }
    $artifacts[$item.Name] = $bytes
}
if ($artifacts.Count -ne 25) { throw '25 original artifacts required' }
$prefix = 'batch-staging/aidd-final-fp-convergence-20261117/proof/'
$summary = $utf8.GetString($artifacts[$prefix+'cohort-summary.json']) | ConvertFrom-Json
$pins = $summary.fullTransitivePythonInputs
if (@($pins.PSObject.Properties).Count -ne 287) { throw '287-input common map required' }
# This caller's immutable metadata-derived allowlist; no other current source file is read.
$allowed = ConvertFrom-Json @'
[
  "adapters/dot-aidd/scripts/aidd_graphs.py",
  "adapters/dot-aidd/scripts/code_graph.py",
  "skill/hooks/_common.py",
  "skill/hooks/read_hint.py",
  "skill/scripts/aidd_amendment_verify.py",
  "skill/scripts/aidd_evidence.py",
  "skill/scripts/aidd_graphs.py",
  "skill/scripts/aidd_memory.py",
  "skill/scripts/aidd_memory_import.py",
  "skill/scripts/aidd_review.py",
  "skill/scripts/aidd_round.py",
  "skill/scripts/aidd_rules.py",
  "skill/scripts/aidd_status.py",
  "skill/scripts/aidd_unit_audit.py",
  "skill/scripts/aidd_unit_visual.py",
  "skill/scripts/aidd_units.py",
  "skill/scripts/code_graph.py",
  "skill/scripts/find_spec.py",
  "skill/scripts/sql_graph.py",
  "tests/test_aidd_graphs.py",
  "tests/test_aidd_graphs_empty_query.py",
  "tests/test_aidd_graphs_running_state.py",
  "tests/test_code_graph.py",
  "tests/test_code_graph_raw_hashes.py",
  "tests/test_graphs_auto.py"
]
'@
foreach ($relative in $allowed) {
    $pin = $pins.PSObject.Properties[[string]$relative].Value
    if (-not $pin -or (Hash-Bytes ([IO.File]::ReadAllBytes((Join-Path $repoRoot $relative)))) -cne $pin) { throw ('Current declared file mismatch: ' + $relative) }
}
$methods = 0; $subtests = 0
foreach ($group in $summary.groups) {
    [byte[]]$receiptBytes = $artifacts[$prefix+$group.receipt]
    [byte[]]$logBytes = $artifacts[$prefix+$group.log]
    if ((Hash-Bytes $receiptBytes) -cne $group.receiptSha256 -or (Hash-Bytes $logBytes) -cne $group.logSha256) { throw 'Receipt/log binding mismatch' }
    $receipt = $utf8.GetString($receiptBytes) | ConvertFrom-Json
    if ($receipt.exitCode -ne 0 -or $receipt.status -cne 'PASS' -or -not $receipt.inputsStable) { throw 'Nonpassing receipt' }
    foreach ($field in @('fullTransitivePythonInputsBefore','fullTransitivePythonInputsAfter')) {
        $map = $receipt.$field
        if (@($map.PSObject.Properties).Count -ne 287) { throw 'Input map length differs' }
        foreach ($pin in $pins.PSObject.Properties) {
            if ($map.PSObject.Properties[$pin.Name].Value -cne $pin.Value) { throw 'Input map value differs' }
        }
    }
    if ($null -ne $receipt.collectedMethods) { $methods += $receipt.collectedMethods } else { $methods += $receipt.passedMethods }
    $sub = [regex]::Match($utf8.GetString($logBytes), '(\d+) subtests passed')
    if ($sub.Success) { $subtests += [int]$sub.Groups[1].Value }
}
if ($methods -ne 263 -or $subtests -ne 118) { throw 'Execution count mismatch' }
$review = $utf8.GetString($artifacts[$prefix+'native-summary-policy-independent-source-review-final.json']) | ConvertFrom-Json
if ($review.verdicts.functional -cne 'PASS' -or $review.verdicts.security -cne 'PASS') { throw 'Independent T09 review mismatch' }
$owner = $utf8.GetString($artifacts['authentic-external-receipt/native-summary-policy-owner-registration.json']) | ConvertFrom-Json
if ($owner.aggregateTasksHash -cne '9d28a24a080a' -or -not $owner.answer) { throw 'Native T09 consent binding missing' }
[pscustomobject]@{ originalArtifacts=25; currentInputHashes=287; currentDeclaredFilesHashed=@($allowed).Count; methods=$methods; explicitPytestSubtests=$subtests; T09Functional=$review.verdicts.functional; T09Security=$review.verdicts.security; findings=@() } | ConvertTo-Json -Compress
```

The base64 transport below is not necessary for the plain review above. Filter between its two markers instead of dumping it to the console.

<!-- CURRENT-LOSSLESS-GZIP:BEGIN -->
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
YfnPjaDuSV1EI0asBDR8blehmVMs1eqUWH5EAPsS/haxXrA9gZP3YyBvg0bd3B231HyYZdUBS83LzOZS1CkrHCvzNHPaZjLjzBU1
FrUSWZUCt5WZskUBLJSVDDgurWSlXJGp4sGWmmf7lppn76A3MgZtOzhEEe9d6qus+75VwCST4rutvJW8PGAR6tJIC5XA4dThDZNW
JuWK2ULWAnIIgK3wZVHUEDmgcpEW4OvMZbrO07Tm9heyCPvml4DPxAaJOH6Sc+Ynuc4PmOQSarYyAPh5XvC8YKWoVUqOC7eSAd2n
spQFr0xpXJlBAAqWVrkxooCKg/EUv+BJXurZ3I5UwHKhy88Xs7/YaYcXe+gtKCWP1FrDO/nsQ1lXwTmCSLYH6ki5TQNunNjlo2QK
xIeJSAilevC4tATbYhPqMxoYLzcCX8NmJH/f9JtGDegbfdrymnY8IoCbXMu0rCUXuTCpTLkBHBKp4qqyWucZM6x2eWl04ZxiJasM
fKXC5DXwl7XkESkytwPwH4DFudfiA0fRnYGbDwCqP1oo+qm2DbwpTz0Tnz5/9vjd7948G3zz5vHrbwdvf/f994/f/J+93lGRwXYe
4B5BToBTzFZw5mrGg2PxFKiafvxupgOWer2YnS/kpf/+9efVBQBQ+1PKBf0y978M7U+boGnw9eavlxu/zoltNh2uwY+bv843fp3O
zrTUF5ZWcmzspu81GKzUfywvgDc34RVILE/p75E3pkH+SMLndjj/fO2zcxo45O+a55pHYJJhC9aeBa9pFc6IIYckAL6J/AzRveZ5
M4s9uRwvFrPFNU+SmIywSvOLEXjC4067POj5mybBP7Q87KmRvZyvPo9+XNvF5wPfgFNGEj+CrKyuW5D4uFyvZtc8FR306BlEobej
4Cbf1CPqwppGenb2Dh++DY28wRLZ3eCk/mQOcmm87C+tXkPtfB6o2XpqyGeJgu9VePAgvPryjgp9pmcXdkGeS19bQFEavwPQi2nY
n8arJ1hM6gxrP53LJbTz9xZSGWJ7PM+6VyZyjm/fwtZNw7dpMYQLV8c/ZdoFd8fT+Xq1fLuSauJJrBbrLs5EexbvFnLqo942KIQX
/oWvvcdPL/z2t8/++/GTd6O33z6muIyoytH/fvvq5Yj/9rcHtPPYrUI875BmJrPzh1ySVoFjPcau+bbR4J7iXvXtu9Xv5Ns+jtZl
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
A58rRYGtLAIA
<!-- CURRENT-LOSSLESS-GZIP:END -->

---

## Earlier documentation retained as historical

# Retry a stale code-graph miss explicitly

```powershell
python skill/scripts/aidd_graphs.py show code new_function --refresh-on-miss
```

The opt-in flag applies only to the built-in code graph. It performs at most one registered **incremental** refresh when the existing graph is stale and the original lookup has no FILE/FUNC match. It then checks freshness, reloads the graph and repeats the same query once. Generator counts such as `re-parsed N, reused M` remain visible.

Without the flag, existing behavior and the public call contract remain unchanged. A fresh miss or a stale hit starts no refresh. The flag is not a request to rebuild every graph, force a full parse, run project source or use an external provider.

Existing refresh timeout, lock and debounce behavior applies. A busy/debounced refresh is reported pending; an unsuccessful or unreadable refresh is reported failed/uncertain. The tool does not turn those states into an assertion that a symbol does not exist. If files change during refresh and freshness cannot be confirmed, no refreshed lookup is claimed.

Foreground and detached refreshes acquire the same nonblocking OS guard before running a generator or opening its log. The guard remains held through stamping and releases if the process exits. Input listings and hashes are invalidated at generation boundaries; edits made during a generator run keep its output stale.

A graph match still describes parsed source, not executed application behavior. Use narrow source reads after lookup and preserve actual runtime verification.

When testing a source checkout, the direct Python entrypoint above selects that checkout. The installed `aidd` launcher may select the user's installed skill; updating source does not silently update that installation.

<!-- ROOT-EXECUTION-RECEIPT:START -->
## Current execution evidence

Actual ROOT subprocess execution, 2026-11-14T09:41:53.302628+00:00 through 2026-11-14T09:42:16.909164+00:00. Result: **123 passed, 23 subtests passed in 22.51s**, exit 0. Before/after hashes of 123 inputs are identical.

Command: `C:\Users\jquimis\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\test_aidd_source_shape.py tests\test_aidd_progress.py tests\test_progress_resolution.py tests\test_amendment_file_layout.py tests\test_verify_amendment.py tests\test_aidd_graphs.py tests\test_graphs_auto.py tests\test_code_graph.py tests\test_dot_aidd_mirror.py tests\test_aidd_unit_visual.py -q --tb=short` from `D:\Fuentes\AIDD`.

Environment: Python 3.12.10 (tags/v3.12.10:0cc8128, Apr  8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)], pytest 9.1.1, Windows-11-10.0.26200-SP0.

Execution log: `batch-staging/aidd-optimization-20261113/regression-root-after-audit.log`, SHA256 `41bc9ae283072660ed14515ba69d467091e0a697e00f7a6ffe86c24d9fa0b107`. Receipt (including complete before/after input hashes): `batch-staging/aidd-optimization-20261113/regression-root-after-audit-receipt.json`, SHA256 `3a93e5e59f53131e1605c0f629113c0a3f234ebcb55696a8c1b52e89445bf417`.

This is executed evidence, not adoption into an AIDD verify_run or an approval/close event. It supersedes the earlier 114-test result for these current inputs. The union includes genuine generic-Protocol/size/type rejection, actual generator freshness and foreground exclusion, descriptor replacement and reverse-only CLI dry-run with root Verification/no execution/no events, plus legacy progress/resolution/mirror/review guards.

Independent review of existing runtime contracts follows. It is contextual evidence, not a change to the manifest dependency closure or a new runtime PASS.

# Independent legacy dependency contract inspection

Auditor: /root/aidd_independent_final. Inspection time: 2026-11-14T09:42:08.965135+00:00.

## Scope and verdict

PASS for the limited compatibility contracts described below, by independent source inspection. This reviewer did not implement these modules or the current fixes. This is current independent evidence covering the relevant legacy dependency contracts, not a declaration that these files are part of the approved unit closure. It is not a runtime verification, official unit audit receipt, unit approval or close authorization. No tests, application source imports, services or database operations were executed for this inspection.

The expressly authorized scope was aidd_progress plus alias_graph, aidd_rules, aidd_evidence and the two progress test files. Native graph query `aidd graphs show code _alias_target` resolved progress relationships; its stale warning was preserved. Targeted source reads followed. No graph rebuild was requested.

## Content identity

SHA-256 of raw bytes inspected (CRLF/LF differences matter):

| Path | SHA-256 |
|---|---|
| `skill/scripts/aidd_progress.py` | `f78a92171423f7585c45159fcb89453c23951d269e85b6b9dcc5adbd1e90fee3` |
| `skill/scripts/alias_graph.py` | `ebde0c8955fecf3d04c41acd80aa6b2674ee29fcc6655701810d3ec844d82e94` |
| `skill/scripts/aidd_rules.py` | `ff7e82cf4ec02c2d4673e1f1c217602309e08849a3264a9d35d4cdc88ffa3ff0` |
| `skill/scripts/aidd_evidence.py` | `9fde4fd718a3d9f0f87254e1e0909c04f4831498feb4281d7bb79a9bda870866` |
| `tests/test_aidd_progress.py` | `24273a61fb2bce1fa8988cd96aef21e2d840fafb117bc6c15043bf15bdedf92c` |
| `tests/test_progress_resolution.py` | `39bc2437a1b1b71143ef9d2a68a8e530664cd4e3301ea64b8afec4950263d0f9` |

## Contracts inspected

1. Alias resolution: aidd_progress.py:232-265 bounds the optional alias graph to MAX_READ, catches unavailable/binary readers, and caches an empty mapping on failure. alias_graph.py:13-67 requires the alias TOON section, parses rows into basenames, rejects separators/NUL/dot traversal, and returns an empty list on failure. Resolution stays in the requested directory and requires an existing target larger than STUB_BYTES. task_state at progress.py:268-297 preserves deletion, migration ambiguity, alias-rename, presence and marker semantics. The new _source_structure at :334-348 reuses these resolvers but stores a separate result; it does not mutate task state or mark a verification PASS. Tests define deletion/rename/ambiguous/binary cases in test_progress_resolution.py:42-86. These definitions were read, not executed by this reviewer.

2. Batch and approval state: progress.py:351-358 expands existing batches with aidd_rules.with_batches. rules.py:1548-1590 discovers only canonical tasks-<name>.md names, sorts them and combines their text; it does not rename or create files. approval_valid at :1718-1724 requires exactly one well-formed Approved line and equality with approval_hash at :1689-1695. Hashing uses the existing semantic projection; it does not record owner consent. New structure findings have no path into these calculations. Exceptions leave displayed approval unknown or preserve the old base-only fallback; the structural inspector is not used as approval authority.

3. Evidence stage: progress.py:300-329 reads approval, last verification, domain coverage and close events. evidence.py:1195-1218 selects the newest exact-spec verify_run and requires boolean true for ok; no event is synthesized. Missing run is displayed as none, a recorded failure as failed, exceptions remain unknown. Domain coverage uses max(scoped code edit time, verify code_since/ts); rules.py:1915-1928 returns all required domains uncovered if the evidence backend is absent or fails. rules.py:1857-1900 checks post-cutoff counting subagents, supports a separately validated closing-audit header, and otherwise uses distinct matching; pre-dispatch and low-tier events are excluded by :1813-1830. This describes the existing contract, not an assertion that those counting rules prove review quality.

4. Cache boundaries: progress.py:499-509 enables evidence.read_cache only around the reporting command. evidence.py:432-460 restores previous cache state in finally, validates cached file text using size+mtime_ns, and retries direct reads on errors. rules.py:1952-1995 resolves that helper dynamically and preserves direct-read fallback. evidence.py:769-817 filters session/kind/spec consumers and caches parsed logs only with the current size/mtime signature and without pending spill files. Its write paths call forget_read (:512,:531,:605). Cache hits neither append PASS events nor change task approval. Existing alias/path caches are process-local.

5. No false runtime inference from the new feature: progress.py:359-361 stores source_structure separately from state and declared_done; :369-375 derives Impl% only from legacy presence/marker/rename states. Rendering at :442-460 explicitly separates static source structure from integrated functionality/runtime behavior. test_aidd_progress.py:24-48 defines preservation of 100% presence for a structural stub, unknown syntax and no runtime-verified claim. Static clean/findings/unknown do not generate approval, verify or audit events.

## Material limitations preserved, not hidden

- The progress verify column displays the latest recorded ok flag; it does not independently revalidate that run against current input fingerprints or current Verification content. A historical passed label is not a current functional PASS or permission to close. Freshness/enforcement remains the responsibility of the actual verification and gate commands.
- Missing dependencies or batch-read exceptions can leave incomplete reporting. Existing broad exception fallbacks do not establish successful feature execution. No global assurance is given that every dependency is failure-proof.
- events() is not entirely free of maintenance effects: evidence.py:636-663 may drain and merge an already existing spill into its log before reading it. That preserves existing rows; it does not authorize direct ledger editing or fabricate an audit or verification result. This reviewer inspected source without invoking events for this contract pass.
- Cache invalidation uses file size+mtime, not a cryptographic freshness guarantee against adversarial same-signature replacement. Alias caches live for the process. This is appropriate to describe as existing reporting behavior, not as new stronger protection.
- Further helpers reached through existing domain/impact/header calculations were classified as legacy support; this was not an exhaustive security audit of all AIDD code or all transitive imports. No changes to dependency files were made.
- This report supplies current independent source-contract evidence only. Executed evidence must be supplied separately with actual scope fingerprints; this report cannot adopt the earlier 114-test log or create a verify_run. Official fresh unit audit still decides whether this evidence is sufficient.

No approval or unit manifest was altered. No official unit audit runner or installation was invoked during this pass.

<!-- ROOT-EXECUTION-RECEIPT:END -->


<!-- AIDD-CURRENT-COHORT-20261117 -->
## Current executed corrective cohort — 2026-11-17

Primary current evidence: [cohort-summary.json](../batch-staging/aidd-convergence-20261117/proof/cohort-summary.json), SHA256 `74b1ef515b2140b8fe165b2fd48bdc40caa8d34d399a47172ded05988c129076`. Its eight original ROOT receipts/logs are copied byte-for-byte into that directory. All287 Python inputs matched before/after every group and still match current Main. These results cover261 methods and118 explicitly reported pytest subtests; unittest subtest totals are not inferred.

| Actual ROOT receipt | Methods | Explicit pytest subtests | Receipt SHA256 | Log SHA256 |
|---|---:|---:|---|---|
| FEATURE-GRAPH-SUMMARY.json | 154 | 100 | `928ff6d868e90eb8a196230f2f4f5d9f741a26bf04db9cec3dd8fd4d882d0964` | `deeaffb53f1d991157c25aaf81c3a4db0912ecf838084fc4053685cb60ccc392` |
| HOOK-SUMMARY.json | 10 | 18 | `cc6f10fb99ad441a0ddadd09d1221d2fab9e515c382ecf00ad481c2b1bc61279` | `d37e69e0b7a57d958932e71fcca613a399e252d52f2d382e0d93ad8f2a569390` |
| V-4B1-GREEN-round08.json | 14 | not separately reported | `91fcb8e5ba91c1592dd18bd4069519ce8c4a209e81ab0fd2630810ac5fa1ab15` | `39f3cf6f459c5bd4253fc325d82b7c380af7a448cce48a15b36224f58c17db81` |
| V-4B2-GREEN-round08.json | 4 | not separately reported | `53d21685740853d46f18378e7f1a9ebfdf4e668a4fe913411380fbc56147a8c3` | `cb9b0bb9dccc2303388133fed6503bb8dae85a1d86e928db0627f5d42cfabe00` |
| V-4B3-GREEN-round08.json | 32 | not separately reported | `17ffdde3addca4226204afd33f659e8d4a843138546a50e4fc8bc50c93534cc9` | `434d1fd8dafece6ec461cc1a78cd6ff8fb8635ee63225efa9a3cd31ae58d4ae4` |
| V-4B4-GREEN-round08.json | 15 | not separately reported | `b99a775fc524f7c816368cecaefc72f1586ff8ee3ae00b9a9179edd7fe41eede` | `32f712fc6d494d992feb0cec701e89f348b63de6262469d7dddab3226aabe700` |
| V-4B5-GREEN-round08.json | 13 | not separately reported | `b9a31e0659f49916399fcc81049a4ff7f502459fe70560578bf1d1cfea011b70` | `c9b5274f38e5acba2f85e13b05a7af1eb36366345737089827379017142c31f0` |
| V-4B6-GREEN-round08.json | 19 | not separately reported | `45db5bbf2f275bdd82335a5644522477d8534730ddcccad1e290aa121027b873` | `c7681e334190d98d190f85f4a199e023a9c4f03bb64d66ed30a8141fbb0115b7` |

Impact assessment: repeated property setter/deleter definitions now retain accessor-kind lines while one getter/setter/deleter composition remains valid; same-descriptor read-race protection remains tested. Graph Git plumbing uses the reviewed raw, fsmonitor-safe current behavior; final merged Graph regressions run in the154-method group. T09 binds native summary consent to each actually offered pair; the final12 regressions, existing11 summary-route regressions and10 selected hook-summary methods are included in this cohort. Six reuse-security commands run once, not once per unit. SourceShape has17 actual methods in the feature group.

Current changed runtime pairs, directly bound to the executed287-file closure:

- `adapters/dot-aidd/scripts/aidd_graphs.py`: `1293eeb3cae6dd264fa65410bf44ed1922383160d4f66651911019458d026b14`.
- `adapters/dot-aidd/scripts/aidd_source_shape.py`: `cc71c80afba6fbd05fc0397662d22db04ce45b232ef8a1f6b8e1fcf0e65849b8`.
- `adapters/dot-aidd/scripts/aidd_status.py`: `06d17ca5008f07640141a5fdf90f2208400d1e0de6c0b00761d1ce9df3d59e88`.
- `adapters/dot-aidd/scripts/code_graph.py`: `bcfeb0a732c6d570d6082b4198c9cb491ca249b349d09c027fa92c4a38fe90a1`.
- `skill/scripts/aidd_graphs.py`: `1293eeb3cae6dd264fa65410bf44ed1922383160d4f66651911019458d026b14`.
- `skill/scripts/aidd_source_shape.py`: `cc71c80afba6fbd05fc0397662d22db04ce45b232ef8a1f6b8e1fcf0e65849b8`.
- `skill/scripts/aidd_status.py`: `06d17ca5008f07640141a5fdf90f2208400d1e0de6c0b00761d1ce9df3d59e88`.
- `skill/scripts/code_graph.py`: `bcfeb0a732c6d570d6082b4198c9cb491ca249b349d09c027fa92c4a38fe90a1`.

Independent final T09 source review: [native-summary-policy-independent-source-review-final.json](../batch-staging/aidd-convergence-20261117/proof/native-summary-policy-independent-source-review-final.json), SHA256 `dad5d0194f285cea2683bd03db1fb2e5b06a0b2a6fd6ca77e02922a2111b9d03`. This source review and current executions supply evidence to the next official reviews; they do not create an owner approval, official audit PASS, or installed result.

Earlier123/114 and round06/round07 evidence above remains historical and unmodified. It is not used as current execution for the changed inspector, Graph modules or status policy. The current cohort directly executes the relevant legacy contracts and new corrections against the same287 Main bytes. The0.5.0 metadata is already present in this cohort. No database or ERP checks are claimed by these offline AIDD results.
<!-- AIDD-CURRENT-COHORT-20261117 END -->
