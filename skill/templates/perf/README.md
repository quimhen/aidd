# Performance templates (amendment 10 of spec 007, FR-404..FR-406)

Two test tiers:

| Tier | Data | When | Command |
|---|---|---|---|
| `functional` | minimal, created through the real business path | every `aidd verify` round | `aidd verify <spec>` |
| `perf` | volume, seeded by set-based SQL | once per spec, before close, alone | `aidd verify <spec> --perf` |

Files:

- `plan-risk.test.sql`: pgTAP checks of a performance risk **without volume** (custom plan pinned in `proconfig`,
  7 calls in a row, no Seq Scan under `force_generic_plan`, expected index at small N). These are functional-tier
  rows: they run in seconds and catch the generic-plan regression measured in b1SycLink F38 (80 ms -> 950 ms from
  the 6th call).
- `seed-generate-series.sql`: light seed for the perf tier (`INSERT ... SELECT ... FROM generate_series`), one
  transaction plus `ANALYZE`, run through the project's DB-pass tool; optionally kept as a cached template database
  by that tool. Seeding 38 000 lines through the business logic took ~40 min; a set-based seed is expected to take
  seconds (hypothesis, measure it in your project before relying on it).

Scale rule: justify every seed in `## Capacity & test budget` by the risk it covers. Linear behaviour with its plan
shown at a small N does not need 200 000 rows; whatever is not measured goes under `Not verified:`.
