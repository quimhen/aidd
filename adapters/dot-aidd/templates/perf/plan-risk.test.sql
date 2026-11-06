-- aidd:FR-406 Functional-tier test of a PERFORMANCE RISK without volume (pgTAP). Runs in seconds.
-- Measured (b1SycLink F38, 2026-11-05): plpgsql switches to a generic plan from the 6th execution of a statement in
-- the same session; fe_rpt_import_buildup went from ~80 ms to ~950 ms. With `plan_cache_mode = force_custom_plan`
-- on the function it stayed at 68-109 ms. None of that needs 38 000 rows to be detected.
--
-- Replace the <placeholders>. Keep only the checks that apply. No psql metacommands (\set, \gset) are used, so
-- `aidd sqlcheck` compiles this file as is.

BEGIN;
SELECT plan(4);

-- 1. The hot function pins the custom plan (cheapest, deterministic check).
SELECT ok(
    EXISTS (SELECT 1
            FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = '<schema>' AND p.proname = '<hot_function>'
              AND 'plan_cache_mode=force_custom_plan' = ANY (coalesce(p.proconfig, '{}'))),
    '<hot_function> declares SET plan_cache_mode = force_custom_plan'
);

-- 2. Call it more than 5 times in one session (the switch happens at the 6th execution): the 7th call must stay
--    within a factor of the first. Small fixture data; the ratio, not the absolute time, is asserted (margin >= 3x).
CREATE TEMP TABLE _aidd_calls(n int, ms numeric) ON COMMIT DROP;
DO $$
DECLARE i int; t0 timestamptz;
BEGIN
    FOR i IN 1..7 LOOP
        t0 := clock_timestamp();
        PERFORM <schema>.<hot_function>(<small_fixture_args>);
        INSERT INTO _aidd_calls VALUES (i, extract(epoch FROM clock_timestamp() - t0) * 1000);
    END LOOP;
END $$;
SELECT ok(
    (SELECT ms FROM _aidd_calls WHERE n = 7) <= 3 * greatest((SELECT ms FROM _aidd_calls WHERE n = 1), 1),
    '7th call is not more than 3x the 1st (no generic-plan regression)'
);

-- 3. Under a forced generic plan the hot query must not Seq Scan the hot table.
SET LOCAL plan_cache_mode = force_generic_plan;
PREPARE _aidd_hot(<param_types>) AS <hot_query_with_$1_params>;
CREATE TEMP TABLE _aidd_plan(line text) ON COMMIT DROP;
DO $$
DECLARE r record;
BEGIN
    FOR r IN EXECUTE 'EXPLAIN (COSTS OFF) EXECUTE _aidd_hot(<sample_args>)' LOOP
        INSERT INTO _aidd_plan VALUES (r."QUERY PLAN");
    END LOOP;
END $$;
SELECT ok(
    NOT EXISTS (SELECT 1 FROM _aidd_plan WHERE line ILIKE '%Seq Scan on <hot_table>%'),
    'generic plan of the hot query has no Seq Scan on <hot_table>'
);
DEALLOCATE _aidd_hot;
RESET plan_cache_mode;

-- 4. At small scale (after ANALYZE of the fixture, enable_seqscan left ON) the plan uses the expected index.
--    Uses pgTAP's performs_ok-free plan check: EXPLAIN text must mention the index.
CREATE TEMP TABLE _aidd_plan2(line text) ON COMMIT DROP;
DO $$
DECLARE r record;
BEGIN
    FOR r IN EXECUTE 'EXPLAIN (COSTS OFF) <hot_query_with_literal_args>' LOOP
        INSERT INTO _aidd_plan2 VALUES (r."QUERY PLAN");
    END LOOP;
END $$;
SELECT ok(
    EXISTS (SELECT 1 FROM _aidd_plan2 WHERE line ILIKE '%<expected_index_name>%'),
    'hot query uses <expected_index_name> at small scale'
);

SELECT * FROM finish();
ROLLBACK;
