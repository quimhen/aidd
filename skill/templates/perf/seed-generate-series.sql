-- aidd:FR-405 Light seed: volume by set-based SQL, not by the business logic document by document.
-- Measured (b1SycLink F38, 2026-11-05): 38 000 lines through the business logic = ~40 min (~2 min per 2 000 lines,
-- worse with volume). One INSERT ... SELECT ... FROM generate_series builds the same shape in seconds.
--
-- Use it ONLY for the perf tier (`Tier: perf` rows). The functional tier keeps minimal data created through the
-- real business path, so behaviour is still proven end to end.
--
-- Rules:
--   * Run it through the project's DB-pass tool on its work database (one-test-DB rule, AIDD E8 (d')); never
--     create a database by hand. If the tool supports it, keep the seeded database as a cached template keyed by
--     (migration-set hash + this file's hash) so later perf runs clone it instead of seeding again.
--   * One transaction, then ANALYZE, so the planner sees the volume.
--   * Generate valid foreign keys from the parent rows you insert first (no random ids).
--   * Keep the scale in a variable and justify it in spec.md `## Capacity & test budget`.
--   * No psql metacommands are needed; `aidd sqlcheck` compiles this file as is.
--
-- Replace the <placeholders>; the example shape is header + lines.

BEGIN;

-- 1. parents: N headers
INSERT INTO <schema>.<header_table> (<id_col>, <company_col>, <doc_date_col>, <status_col>)
SELECT
    <id_expr_from_g>,                                   -- e.g. 900000000 + g (an id range no fixture uses)
    <company_id>,
    DATE '2026-01-01' + (g % 300),
    'draft'
FROM generate_series(1, 2000) AS g;                     -- N headers

-- 2. children: M lines per header, FK taken from the rows inserted above
INSERT INTO <schema>.<line_table> (<header_fk_col>, <line_no_col>, <item_col>, <qty_col>, <price_col>)
SELECT
    h.<id_col>,
    l,
    <item_expr>,                                        -- e.g. (SELECT id FROM items ORDER BY id OFFSET (l % 50) LIMIT 1)
    1 + (l % 7),
    round((10 + (l % 90))::numeric, 2)
FROM <schema>.<header_table> AS h
CROSS JOIN generate_series(1, 19) AS l                  -- M lines per header -> N*M lines (2 000 * 19 = 38 000)
WHERE h.<id_col> >= <first_seed_id>;

-- 3. derived state the business logic would have written (totals, ledgers): one set-based UPDATE/INSERT each,
--    computed from the rows above, never by calling the per-document function in a loop.
-- UPDATE <schema>.<header_table> h SET <total_col> = s.total
-- FROM (SELECT <header_fk_col> AS id, sum(<qty_col> * <price_col>) AS total
--       FROM <schema>.<line_table> GROUP BY 1) s
-- WHERE h.<id_col> = s.id AND h.<id_col> >= <first_seed_id>;

COMMIT;

ANALYZE <schema>.<header_table>;
ANALYZE <schema>.<line_table>;
