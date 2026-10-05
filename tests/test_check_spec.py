"""Tests for scripts/check_spec.py — stdlib unittest, no dependencies.

Run: python -m unittest discover -s tests -v
(from the repo root, or from tests/ with `python -m unittest test_check_spec -v`)
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import check_spec  # noqa: E402


class TestAllCodes(unittest.TestCase):
    def test_finds_every_code_family(self):
        text = "See SCREEN-01, SCREEN-02-F03, CTL-057, COMP-003, API-012, US-004."
        codes = check_spec.all_codes(text)
        self.assertEqual(
            codes,
            {"SCREEN-01", "SCREEN-02-F03", "CTL-057", "COMP-003", "API-012", "US-004"},
        )

    def test_no_false_positive_on_similar_text(self):
        text = "This is SCREENSHOT-01 and CONTROL-5, not real codes."
        self.assertEqual(check_spec.all_codes(text), set())


class TestTableRows(unittest.TestCase):
    def test_parses_rows_under_heading(self):
        md = (
            "## Mapping ledger\n"
            "| Code | Status |\n"
            "|---|---|\n"
            "| SCREEN-01 | OK |\n"
            "| SCREEN-02 | MISSING |\n"
        )
        rows = check_spec.table_rows(md, "Mapping ledger")
        self.assertEqual(rows, [["SCREEN-01", "OK"], ["SCREEN-02", "MISSING"]])

    def test_stops_at_next_section_with_no_table(self):
        md = "## Section A\nNo table here.\n## Section B\n| H |\n|---|\n| x |\n"
        self.assertEqual(check_spec.table_rows(md, "Section A"), [])

    def test_empty_text_returns_no_rows(self):
        self.assertEqual(check_spec.table_rows("", "Anything"), [])


class TestMainGapDetection(unittest.TestCase):
    """End-to-end: run check_spec.py's main() logic against a real temp spec folder."""

    def _run(self, spec_dir):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "check_spec.py"), str(spec_dir)],
            capture_output=True, text=True, timeout=10,
        )
        return result

    def test_clean_spec_exits_zero(self):
        with tempfile.TemporaryDirectory() as d:
            spec_dir = Path(d)
            (spec_dir / "mockup-audit.md").write_text(
                "## Screen inventory\n"
                "| SCREEN-XX | ... | Uses (COMP-nnn list) |\n"
                "|---|---|---|\n"
                "| SCREEN-01 | | |\n"
                "## Control inventory\n"
                "| CTL-nnn | Screen or COMP-nnn | ... | Status | PR/Spec ref |\n"
                "|---|---|---|---|---|\n"
                "| CTL-001 | SCREEN-01 | | Explicit | PR#1 |\n",
                encoding="utf-8",
            )
            (spec_dir / "tasks.md").write_text(
                "| Task | Codes satisfied | Target file | New view vs. reuse | Explicitly out of scope |\n"
                "|---|---|---|---|---|\n"
                "| T-01 | CTL-001 | login_page.dart | new view | everything else |\n",
                encoding="utf-8",
            )
            result = self._run(spec_dir)
            self.assertEqual(result.returncode, 0, msg=result.stdout)
            self.assertIn("No mechanical gaps found", result.stdout)

    def test_not_verified_rows_are_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            spec_dir = Path(d)
            (spec_dir / "mockup-audit.md").write_text(
                "## Control inventory\n"
                "| CTL-nnn | Screen | Status |\n"
                "|---|---|---|\n"
                "| CTL-001 | SCREEN-01 | [Not Verified] |\n"
                "| CTL-002 | SCREEN-01 | [Not Verified] |\n",
                encoding="utf-8",
            )
            result = self._run(spec_dir)
            self.assertEqual(result.returncode, 1)
            self.assertIn("2 row(s) still tagged [Not Verified]", result.stdout)

    def test_dangling_code_in_tasks_is_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            spec_dir = Path(d)
            (spec_dir / "mockup-audit.md").write_text(
                "## Control inventory\n| CTL-nnn |\n|---|\n| CTL-001 |\n",
                encoding="utf-8",
            )
            (spec_dir / "tasks.md").write_text(
                "References CTL-999 which was never audited.\n",
                encoding="utf-8",
            )
            result = self._run(spec_dir)
            self.assertEqual(result.returncode, 1)
            self.assertIn("CTL-999", result.stdout)

    def test_nonexistent_directory_is_a_usage_error(self):
        result = self._run(Path("/no/such/directory/at/all"))
        self.assertEqual(result.returncode, 2)

    def test_wrong_arg_count_prints_usage(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "check_spec.py")],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 2)


class TestHardRulesIntegration(unittest.TestCase):
    """check_spec.py reports the static aidd_rules violations as gaps (R1 ... -> fix)."""

    def _run(self, spec_dir):
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "check_spec.py"), str(spec_dir)],
            capture_output=True, text=True, encoding="utf-8", timeout=20,
        )

    def test_spec_without_route_is_a_gap(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "spec.md").write_text("# spec\n\nNo route here.\n", encoding="utf-8")
            r = self._run(d)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("R2 ", r.stdout)
            self.assertIn("\u2192", r.stdout)

    def test_legacy_estimated_hours_tasks_is_a_gap(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tasks.md").write_text(
                "# Tasks\n\n### T-01\n- Estimated hours: 4\n", encoding="utf-8")
            r = self._run(d)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("R1 ", r.stdout)

    def test_missing_approval_reported_for_structured_tasks(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "spec.md").write_text("# spec\n", encoding="utf-8")
            (Path(d) / "tasks.md").write_text("# Tasks\n\n## Waves\n", encoding="utf-8")
            r = self._run(d)
            self.assertIn("R6 ", r.stdout)

    def test_artifacts_that_do_not_exist_add_no_rule_gaps(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._run(d)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertNotIn("R2 ", r.stdout)


CTL_HDR = ("| CTL-nnn | Screen or COMP-nnn | Visible text | id | Action/handler | Destination | "
           "Data source | States | Class/style | Calls API-nnn (if any) | Status | PR/Spec ref |\n"
           "|---|---|---|---|---|---|---|---|---|---|---|---|\n")
CONTRACT_TABLE = (
    "| API-nnn | Method + path | Request schema | Response schema | Error cases | Auth | "
    "Stored procedure(s) | Swagger/OpenAPI ref | Consumed by (CTL-nnn) | Exception reason (if no SP) | PR/Spec ref |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|\n"
    "| API-001 | `POST /orders` | `{ a }` | `{ b }` | 400 | Bearer | `sp_Create` | /sw | CTL-001 | | |\n")


class TestStructuralBanner(unittest.TestCase):
    """aidd:FR-208 banner: structural-only until verification passed; exit codes unchanged."""

    def _main(self, spec_dir, state=None):
        import io
        from unittest import mock
        import aidd_rules
        buf = io.StringIO()
        code = None
        patches = [mock.patch.object(sys, 'argv', ['check_spec.py', str(spec_dir)]),
                   mock.patch.object(sys, 'stdout', buf)]
        if state is not None:
            patches.append(mock.patch.object(aidd_rules, 'verification_state', return_value=state))
        for p in patches:
            p.start()
        try:
            check_spec.main()
        except SystemExit as e:
            code = e.code
        finally:
            for p in patches:
                p.stop()
        return code, buf.getvalue()

    def test_clean_spec_prints_structural_banner(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = self._main(d)
            self.assertEqual(code, 0, msg=out)
            self.assertIn("STRUCTURAL CHECK ONLY - nothing was executed", out)
            self.assertIn("No mechanical gaps found (structural only)", out)

    def test_passed_verification_prints_execution_line(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = self._main(d, {'status': 'passed'})
            self.assertEqual(code, 0, msg=out)
            self.assertNotIn("STRUCTURAL CHECK ONLY", out)
            self.assertIn("Execution evidence", out)

    def test_verification_state_crash_defaults_to_banner(self):
        from unittest import mock
        import aidd_rules
        with tempfile.TemporaryDirectory() as d,                 mock.patch.object(aidd_rules, 'verification_state', side_effect=RuntimeError('x')):
            code, out = self._main(d)
            self.assertEqual(code, 0, msg=out)
            self.assertIn("STRUCTURAL CHECK ONLY", out)

    def test_exit_code_one_with_gaps_keeps_banner(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tasks.md").write_text("T-01 refers to COMP-999\n", encoding="utf-8")
            code, out = self._main(d)
            self.assertEqual(code, 1, msg=out)
            self.assertIn("STRUCTURAL CHECK ONLY", out)


class TestG1Controls(unittest.TestCase):
    def test_action_without_destination_data_states_is_flagged(self):
        md = "## Control inventory\n" + CTL_HDR + \
            "| CTL-001 | SCREEN-01 | Save | btn | onSave | | | | | | Explicit | |\n"
        gaps = check_spec.check_g1_controls(md)
        self.assertEqual(len(gaps), 1, gaps)
        self.assertIn("Destination, Data source, States", gaps[0])

    def test_filled_and_na_with_reason_is_clean(self):
        md = "## Control inventory\n" + CTL_HDR + \
            ("| CTL-001 | SCREEN-01 | Save | btn | onSave | SCREEN-02 | API-001 | empty/loading/error "
             "| | | Explicit | |\n"
             "| CTL-002 | SCREEN-01 | Help | btn | open | n/a — external app | n/a - static text "
             "| empty: hidden | | | Explicit | |\n")
        self.assertEqual(check_spec.check_g1_controls(md), [])

    def test_bare_na_is_flagged(self):
        md = "## Control inventory\n" + CTL_HDR + \
            "| CTL-001 | SCREEN-01 | Save | btn | onSave | n/a | n/a | loading | | | Explicit | |\n"
        self.assertEqual(len(check_spec.check_g1_controls(md)), 1)

    def test_control_without_action_is_not_flagged(self):
        md = "## Control inventory\n" + CTL_HDR + \
            "| CTL-001 | SCREEN-01 | Title | h1 | | | | | | | Explicit | |\n"
        self.assertEqual(check_spec.check_g1_controls(md), [])

    def test_old_table_without_new_columns_is_not_flagged(self):
        md = ("## Control inventory\n"
              "| CTL-nnn | Screen | Visible text | id | Action/handler | Status | PR/Spec ref |\n"
              "|---|---|---|---|---|---|---|\n"
              "| CTL-001 | SCREEN-01 | Save | btn | onSave | Explicit \\| [Not Verified] | |\n")
        self.assertEqual(check_spec.check_g1_controls(md), [])


class TestG2Acceptance(unittest.TestCase):
    HDR = "## Acceptance cases\n\n| Case | Real data (id) | Expected | Edge? |\n|---|---|---|---|\n"

    def test_missing_section_is_flagged(self):
        self.assertIn("no `## Acceptance cases`", check_spec.check_g2_acceptance("# spec\n")[0])

    def test_placeholder_row_only_is_flagged(self):
        self.assertEqual(len(check_spec.check_g2_acceptance(self.HDR + "| AC-001 | | | |\n")), 1)

    def test_no_edge_row_is_flagged(self):
        g = check_spec.check_g2_acceptance(self.HDR + "| AC-001 | emp 1234 | pays 100 | |\n")
        self.assertIn("no `edge` row", g[0])

    def test_with_edge_is_clean(self):
        md = self.HDR + "| AC-001 | emp 1234 | pays 100 | |\n| AC-002 | emp 9 | date 9999 ok | edge |\n"
        self.assertEqual(check_spec.check_g2_acceptance(md), [])


class TestG3Traceability(unittest.TestCase):
    HDR = "| Mockup field (SCREEN-XX / CTL-nnn) | Room/store | DTO | API | SP | Filled-by |\n|---|---|---|---|---|---|\n"

    def test_empty_cell_is_flagged(self):
        g = check_spec.check_g3_traceability(self.HDR + "| SCREEN-01 / CTL-001 | store | | API-001 | sp_x | T-02 |\n")
        self.assertEqual(len(g), 1)
        self.assertIn("DTO", g[0])

    def test_complete_row_and_na_are_clean(self):
        md = self.HDR + "| SCREEN-01 / CTL-001 | store | Dto.x | API-001 | n/a — no DB | T-02 |\n"
        self.assertEqual(check_spec.check_g3_traceability(md), [])


class TestG4ContractHash(unittest.TestCase):
    def _doc(self, hash_line, table=CONTRACT_TABLE):
        return f"# C\n\nContract version: 1\n{hash_line}\n\n{table}"

    def test_hash_ignores_pr_ref_and_whitespace(self):
        a = check_spec.compute_contract_hash(self._doc("Contract hash: PENDING"))
        b = CONTRACT_TABLE.replace("| CTL-001 | | |", "|   CTL-001   | | PR#9 |")
        self.assertEqual(a, check_spec.compute_contract_hash(self._doc("x", b)))
        self.assertEqual(len(a), 12)

    def test_pending_is_flagged(self):
        g = check_spec.check_g4_contract_hash(self._doc("Contract hash: PENDING"))
        self.assertIn("--stamp-contract", g[0])

    def test_match_is_clean_and_mismatch_lists_stale_tasks(self):
        h = check_spec.compute_contract_hash(self._doc(""))
        self.assertEqual(check_spec.check_g4_contract_hash(self._doc(f"Contract hash: {h}")), [])
        changed = CONTRACT_TABLE.replace("400", "400, 409")
        tasks = "| T-03 | API-001 | f.py | x |\n| T-04 | CTL-009 | g.py | x |\n"
        g = check_spec.check_g4_contract_hash(self._doc(f"Contract hash: {h}", changed), tasks)
        self.assertEqual(len(g), 1)
        self.assertIn("T-03", g[0])
        self.assertNotIn("T-04", g[0])

    def test_stamp_round_trip_via_cli(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "contracts.md"
            p.write_text(self._doc("Contract hash: PENDING"), encoding="utf-8")
            r = subprocess.run([sys.executable, str(SCRIPTS_DIR / "check_spec.py"), d, "--stamp-contract"],
                               capture_output=True, text=True, encoding="utf-8", timeout=20)
            self.assertEqual(r.returncode, 0, r.stdout)
            text = p.read_text(encoding="utf-8")
            self.assertNotIn("PENDING", text)
            self.assertEqual(check_spec.check_g4_contract_hash(text), [])
            # edit the contract -> mismatch; re-stamp -> clean again
            p.write_text(text.replace("400", "500"), encoding="utf-8")
            self.assertEqual(len(check_spec.check_g4_contract_hash(p.read_text(encoding="utf-8"))), 1)
            subprocess.run([sys.executable, str(SCRIPTS_DIR / "check_spec.py"), "--stamp-contract", d],
                           capture_output=True, text=True, timeout=20)
            self.assertEqual(check_spec.check_g4_contract_hash(p.read_text(encoding="utf-8")), [])

    def test_stamp_without_contracts_is_usage_error(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(SCRIPTS_DIR / "check_spec.py"), d, "--stamp-contract"],
                               capture_output=True, text=True, timeout=20)
            self.assertEqual(r.returncode, 2)


class TestG5Consumers(unittest.TestCase):
    HDR = ("| COMP-nnn | Name | File | First defined in | Used in (SCREEN-XX) | Consumers | Notes |\n"
           "|---|---|---|---|---|---|---|\n")

    def test_screen_without_consumers_is_flagged(self):
        g = check_spec.check_g5_consumers(self.HDR + "| COMP-001 | Card | c.dart | 003 | SCREEN-02 | | |\n")
        self.assertEqual(len(g), 1)
        self.assertIn("COMP-001", g[0])

    def test_consumers_filled_or_unused_is_clean(self):
        md = self.HDR + ("| COMP-001 | Card | c.dart | 003 | SCREEN-02 | a.dart | |\n"
                         "| COMP-002 | Hdr | h.dart | 003 | | | |\n")
        self.assertEqual(check_spec.check_g5_consumers(md), [])

    def test_old_index_without_column_is_clean(self):
        md = ("| COMP-nnn | Name | File | First defined in | Used in (SCREEN-XX) | Notes |\n|---|---|---|---|---|---|\n"
              "| COMP-001 | Card | c.dart | 003 | SCREEN-02 | |\n")
        self.assertEqual(check_spec.check_g5_consumers(md), [])


class TestG6SingleOwner(unittest.TestCase):
    HDR = ("| Task | Codes satisfied | Target file | View / logic | Tracker ref | Status | Out of scope |\n"
           "|---|---|---|---|---|---|---|\n")

    def test_same_file_two_rows_flagged(self):
        g = check_spec.check_g6_single_owner(
            self.HDR + "| T-01 | FR-1 | scripts/a.py + x.py | LOGIC | | | |\n"
                       "| T-10 | FR-2 | `scripts/A.py` (fn) | LOGIC | | | |\n")
        self.assertEqual(len(g), 1)
        self.assertIn("G6 T-01 and T-10", g[0])

    def test_same_owner_exempt(self):
        g = check_spec.check_g6_single_owner(
            self.HDR + "| T-01 | FR-1 | scripts/a.py | LOGIC | | | |\n"
                       "| T-10 | FR-2 | scripts/a.py (fn), same owner as T-01 | LOGIC | | | |\n")
        self.assertEqual(g, [])

    def test_distinct_and_empty_clean(self):
        g = check_spec.check_g6_single_owner(
            self.HDR + "| T-01 | FR-1 | a.py | LOGIC | | | |\n"
                       "| T-02 | FR-1 | b.py | LOGIC | | | |\n"
                       "| T-03 | FR-1 | | LOGIC | | | |\n"
                       "| T-04 | FR-1 | | LOGIC | | | |\n")
        self.assertEqual(g, [])

    def test_real_spec_006_t01_t10_not_flagged(self):
        p = Path(__file__).resolve().parent.parent / "specs" / "006-aidd-phased-audits-attribution" / "tasks.md"
        if not p.exists():
            self.skipTest("spec 006 absent")
        g = check_spec.check_g6_single_owner(p.read_text(encoding="utf-8"))
        self.assertFalse([x for x in g if "T-10" in x or "T-01 " in x], g)


class TestGapsEndToEnd(unittest.TestCase):
    def test_spec_without_acceptance_and_bad_traceability_exit_one(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "spec.md").write_text("# spec\n", encoding="utf-8")
            (Path(d) / "traceability.md").write_text(TestG3Traceability.HDR +
                "| SCREEN-01 / CTL-001 | | | | | |\n", encoding="utf-8")
            r = subprocess.run([sys.executable, str(SCRIPTS_DIR / "check_spec.py"), d],
                               capture_output=True, text=True, encoding="utf-8", timeout=20)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("G2 ", r.stdout)
            self.assertIn("G3 ", r.stdout)


if __name__ == "__main__":
    unittest.main()
