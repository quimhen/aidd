#!/usr/bin/env python3
"""
test_gen_execution_evidence.py — Unit tests for gen_execution_evidence.py (Iteration 2).

Uses an isolated temporary synthetic spec directory created inside the staging folder.
Tests:
1. Literal token matching (Rule 1)
2. Unmapped codes listed as not-verified candidates (Rule 4)
3. Stale evidence freshness warning and dry-run safety
4. Verification table Covers matching with passed Closing gates (Rule 3)
5. Screenshot mapping by number (Rule 2: s<NN>-* or SCREEN-<NN>*)
6. Precedence ordering (literal > by-number > covers)
7. Invalid Kind detection ('command' -> 'command-output')
"""

import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

# Import the module under test
from gen_execution_evidence import (
    generate_execution_evidence,
    format_markdown_proposal,
    parse_qa_audit,
    parse_closing_gates,
    parse_verification_table,
    find_evidence_files,
    classify_kind,
    audit_existing_kinds,
)


class TestGenExecutionEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.staging_dir = Path(__file__).resolve().parent
        cls.test_dir = cls.staging_dir / "tmp_synthetic_spec"
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)
        cls.test_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setUp(self):
        # Clear synthetic dir between tests
        for item in self.test_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    def test_complete_mapping_and_r10_table(self):
        """Test 1: Full literal mapping where codes have matching evidence on disk."""
        qa_audit_content = """# QA Audit

## Mapping ledger

| Code | Status | Evidence (file/class/resource id) | PR/Spec ref | Screenshot diff done? |
|---|---|---|---|---|
| SCREEN-01 | \u2705 IMPLEMENTED | `src/pages/UsersPage.tsx` | prototype/SCREEN-01.png | \u2611 |
| API-101 | \u2705 IMPLEMENTED | `src/api/users.ts` | contracts.md | \u2611 |
| API-102 | \u2705 IMPLEMENTED | `supabase/migrations/01_users.sql` | contracts.md | \u2611 |
| COMP-01 | \u2705 IMPLEMENTED | `src/components/UserCard.tsx` | plan.md | \u2611 |
"""
        (self.test_dir / "qa-audit.md").write_text(qa_audit_content, encoding="utf-8")

        evidence_dir = self.test_dir / "evidence"
        evidence_dir.mkdir()
        (evidence_dir / "SCREEN-01-desktop.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (evidence_dir / "verify-v1.txt").write_text("# vitest run\nPASS API-101 users test\n", encoding="utf-8")
        (evidence_dir / "db_query.sql").write_text("-- SELECT API-102 from db\nSELECT 1;\n", encoding="utf-8")

        res = generate_execution_evidence(self.test_dir)
        summary = res["summary"]

        self.assertEqual(summary["total_codes"], 3)
        self.assertEqual(summary["mapped_count"], 3)
        self.assertEqual(summary["unmapped_count"], 0)
        self.assertEqual(summary["mapped_by_literal"], 3)

        mapped_dict = {r["code"]: r for r in res["mapped_rows"]}
        self.assertEqual(mapped_dict["SCREEN-01"]["kind"], "screenshot")
        self.assertEqual(mapped_dict["SCREEN-01"]["method"], "literal")
        self.assertEqual(mapped_dict["API-101"]["kind"], "command-output")
        self.assertEqual(mapped_dict["API-101"]["method"], "literal")
        self.assertEqual(mapped_dict["API-102"]["kind"], "query-result")
        self.assertEqual(mapped_dict["API-102"]["method"], "literal")

        md = format_markdown_proposal(res)
        self.assertIn("## Execution evidence", md)
        self.assertIn("| SCREEN-01 | screenshot | evidence/SCREEN-01-desktop.png | agent | literal |", md)
        self.assertIn("| API-101 | command-output | evidence/verify-v1.txt | agent | literal |", md)

    def test_unmapped_codes_and_not_verified_candidates(self):
        """Test 2: Spec with missing evidence lists unmapped codes as not-verified candidates."""
        qa_audit_content = """# QA Audit

## Mapping ledger

| Code | Status | Evidence | PR/Spec ref | Screenshot diff done? |
|---|---|---|---|---|
| SCREEN-05 | \u2705 IMPLEMENTED | `src/pages/SettingsPage.tsx` | prototype/SCREEN-05.png | \u2611 |
| API-205 | \u2705 IMPLEMENTED | `src/api/settings.ts` | contracts.md | \u2611 |

## Open exceptions

| Code | Reason |
|---|---|
| API-999 | Excluded |
"""
        (self.test_dir / "qa-audit.md").write_text(qa_audit_content, encoding="utf-8")

        evidence_dir = self.test_dir / "evidence"
        evidence_dir.mkdir()
        (evidence_dir / "SCREEN-05-view.png").write_bytes(b"\x89PNG\r\n\x1a\n")

        res = generate_execution_evidence(self.test_dir)
        summary = res["summary"]

        self.assertEqual(summary["total_codes"], 2)
        self.assertEqual(summary["mapped_count"], 1)
        self.assertEqual(summary["unmapped_count"], 1)

        unmapped = res["unmapped_codes"][0]
        self.assertEqual(unmapped["code"], "API-205")
        self.assertIn("no evidence file mentions code", unmapped["reason"])

        md = format_markdown_proposal(res)
        self.assertIn("## Unmapped codes (candidates for `not-verified`)", md)
        self.assertIn("API-205", md)
        self.assertIn("`not-verified` candidate", md)

    def test_freshness_warning_and_dry_run_integrity(self):
        """Test 3: Stale evidence detection (older than target code file) and immutability."""
        project_root = self.test_dir / "project"
        spec_folder = project_root / "specs" / "S01-Test"
        spec_folder.mkdir(parents=True)
        code_dir = project_root / "src" / "features"
        code_dir.mkdir(parents=True)

        target_code = code_dir / "Feature.tsx"
        target_code.write_text("// New implementation code", encoding="utf-8")

        qa_audit_content = """# QA Audit
## Mapping ledger
| Code | Status | Evidence | PR/Spec ref |
|---|---|---|---|
| SCREEN-99 | \u2705 IMPLEMENTED | `src/features/Feature.tsx` | proto |
"""
        qa_file = spec_folder / "qa-audit.md"
        qa_file.write_text(qa_audit_content, encoding="utf-8")
        original_qa_bytes = qa_file.read_bytes()

        ev_dir = spec_folder / "evidence"
        ev_dir.mkdir()
        ev_file = ev_dir / "SCREEN-99.png"
        ev_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        now = time.time()
        os.utime(ev_file, (now - 200, now - 200))
        os.utime(target_code, (now, now))

        res = generate_execution_evidence(spec_folder)
        self.assertEqual(res["summary"]["freshness_warnings_count"], 1)
        warning = res["freshness_warnings"][0]
        self.assertEqual(warning["code"], "SCREEN-99")
        self.assertIn("older than newest target code file", warning["message"])

        # Dry-run check: qa-audit.md must NEVER be modified
        self.assertEqual(qa_file.read_bytes(), original_qa_bytes)

    def test_mapping_by_covers(self):
        """Test 4 (Iteration 2): Mapping codes via Verification Covers table with passed Closing gates."""
        spec_content = """# Spec

## Verification

| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | `npm test -- users` | exit 0 | API-301..API-303, FR-001 |
| V-2 | `npm test -- billing` | exit 0 | API-304 |
"""
        (self.test_dir / "spec.md").write_text(spec_content, encoding="utf-8")

        qa_audit_content = """# QA Audit

## Mapping ledger
| Code | Status | Evidence | PR/Spec ref |
|---|---|---|---|
| API-301 | \u2705 IMPLEMENTED | `src/users.ts` | contracts.md |
| API-302 | \u2705 IMPLEMENTED | `src/users.ts` | contracts.md |
| API-303 | \u2705 IMPLEMENTED | `src/users.ts` | contracts.md |
| API-304 | \u2705 IMPLEMENTED | `src/billing.ts` | contracts.md |

### Closing gates
| # | Command (exact) | Exit | Result | Evidence | Owner if not green |
|---|-----------------|------|--------|----------|--------------------|
| V-1 | `npm test -- users` | 0 | PASS — 12 tests passed | `evidence/verify-V-1.txt` | — |
| V-2 | `npm test -- billing` | 1 | FAIL — 1 test failed | `evidence/verify-V-2.txt` | — |
"""
        (self.test_dir / "qa-audit.md").write_text(qa_audit_content, encoding="utf-8")

        evidence_dir = self.test_dir / "evidence"
        evidence_dir.mkdir()
        # verify-V-1 does NOT mention API-301..303 tokens literally
        (evidence_dir / "verify-V-1.txt").write_text("Test suite passed successfully in 3s\n", encoding="utf-8")
        (evidence_dir / "verify-V-2.txt").write_text("Test suite failed\n", encoding="utf-8")

        res = generate_execution_evidence(self.test_dir)
        summary = res["summary"]

        # V-1 passed, so API-301, 302, 303 must map via covers
        # V-2 failed, so API-304 must NOT map via covers and remain unmapped
        self.assertEqual(summary["total_codes"], 4)
        self.assertEqual(summary["mapped_count"], 3)
        self.assertEqual(summary["mapped_by_covers"], 3)
        self.assertEqual(summary["unmapped_count"], 1)

        mapped_dict = {r["code"]: r for r in res["mapped_rows"]}
        for code in ("API-301", "API-302", "API-303"):
            self.assertEqual(mapped_dict[code]["kind"], "command-output")
            self.assertEqual(mapped_dict[code]["evidence"], "evidence/verify-V-1.txt")
            self.assertEqual(mapped_dict[code]["method"], "covers")

        unmapped = res["unmapped_codes"][0]
        self.assertEqual(unmapped["code"], "API-304")

    def test_mapping_by_number(self):
        """Test 5 (Iteration 2): Mapping SCREEN codes by number to evidence/**/s<NN>-* and SCREEN-<NN>*."""
        qa_audit_content = """# QA Audit

## Mapping ledger
| Code | Status | Evidence | PR/Spec ref |
|---|---|---|---|
| SCREEN-44 | \u2705 IMPLEMENTED | `src/pages/Page44.tsx` | proto |
| SCREEN-045 | \u2705 IMPLEMENTED | `src/pages/Page45.tsx` | proto |
"""
        (self.test_dir / "qa-audit.md").write_text(qa_audit_content, encoding="utf-8")

        visual_dir = self.test_dir / "evidence" / "visual"
        s44_dir = visual_dir / "s44-loaded-admin"
        s44_dir.mkdir(parents=True)
        # Mockup and pair should have lower score than app.png
        (s44_dir / "mockup.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (s44_dir / "app.png").write_bytes(b"\x89PNG\r\n\x1a\n")

        s45_dir = visual_dir / "s45-loaded-aprobador"
        s45_dir.mkdir(parents=True)
        (s45_dir / "app.png").write_bytes(b"\x89PNG\r\n\x1a\n")

        res = generate_execution_evidence(self.test_dir)
        summary = res["summary"]

        self.assertEqual(summary["total_codes"], 2)
        self.assertEqual(summary["mapped_count"], 2)
        self.assertEqual(summary["mapped_by_number"], 2)

        mapped_dict = {r["code"]: r for r in res["mapped_rows"]}
        self.assertEqual(mapped_dict["SCREEN-44"]["kind"], "screenshot")
        self.assertEqual(mapped_dict["SCREEN-44"]["evidence"], "evidence/visual/s44-loaded-admin/app.png")
        self.assertEqual(mapped_dict["SCREEN-44"]["method"], "by-number")

        self.assertEqual(mapped_dict["SCREEN-045"]["kind"], "screenshot")
        self.assertEqual(mapped_dict["SCREEN-045"]["evidence"], "evidence/visual/s45-loaded-aprobador/app.png")
        self.assertEqual(mapped_dict["SCREEN-045"]["method"], "by-number")

    def test_precedence_literal_over_by_number_and_covers(self):
        """Test 6 (Iteration 2): Precedence ordering (literal > by-number > covers)."""
        spec_content = """# Spec
## Verification
| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | `npm test` | exit 0 | SCREEN-10, API-10 |
"""
        (self.test_dir / "spec.md").write_text(spec_content, encoding="utf-8")

        qa_audit_content = """# QA Audit
## Mapping ledger
| Code | Status | Evidence | PR/Spec ref |
|---|---|---|---|
| SCREEN-10 | \u2705 IMPLEMENTED | `src/Screen10.tsx` | proto |
| API-10 | \u2705 IMPLEMENTED | `src/api.ts` | proto |

### Closing gates
| # | Command (exact) | Exit | Result | Evidence | Owner |
|---|-----------------|------|--------|----------|-------|
| V-1 | `npm test` | 0 | PASS | `evidence/verify-V-1.txt` | — |
"""
        (self.test_dir / "qa-audit.md").write_text(qa_audit_content, encoding="utf-8")

        ev_dir = self.test_dir / "evidence"
        ev_dir.mkdir()
        # Literal file for SCREEN-10
        (ev_dir / "SCREEN-10-full.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        # By-number file for SCREEN-10 (should be superseded by literal)
        s10_dir = ev_dir / "s10-view"
        s10_dir.mkdir()
        (s10_dir / "app.png").write_bytes(b"\x89PNG\r\n\x1a\n")

        # Literal file for API-10
        (ev_dir / "api_test.txt").write_text("API-10 passed in unit test\n", encoding="utf-8")
        # verify-V-1 also covers API-10 (should be superseded by literal)
        (ev_dir / "verify-V-1.txt").write_text("Verification suite\n", encoding="utf-8")

        res = generate_execution_evidence(self.test_dir)
        mapped_dict = {r["code"]: r for r in res["mapped_rows"]}

        self.assertEqual(mapped_dict["SCREEN-10"]["method"], "literal")
        self.assertEqual(mapped_dict["SCREEN-10"]["evidence"], "evidence/SCREEN-10-full.png")

        self.assertEqual(mapped_dict["API-10"]["method"], "literal")
        self.assertEqual(mapped_dict["API-10"]["evidence"], "evidence/api_test.txt")

    def test_invalid_kind_audit(self):
        """Test 7 (Iteration 2): Detect invalid Kind 'command' and propose 'command-output'."""
        qa_audit_content = """# QA Audit
## Execution evidence
| Code | Kind | Evidence | Verified by |
|---|---|---|---|
| SCREEN-01 | screenshot | prototype/SCREEN-01.png | agent |
| V-1 | command | evidence/verify-V-1.txt | agent |
| V-2 | command | evidence/verify-V-2.txt | agent |
"""
        qa_file = self.test_dir / "qa-audit.md"
        qa_file.write_text(qa_audit_content, encoding="utf-8")

        invalid_rows = audit_existing_kinds(qa_file)
        self.assertEqual(len(invalid_rows), 2)
        self.assertEqual(invalid_rows[0]["invalid_kind"], "command")
        self.assertEqual(invalid_rows[0]["proposed_kind"], "command-output")
        self.assertEqual(invalid_rows[1]["invalid_kind"], "command")
        self.assertEqual(invalid_rows[1]["proposed_kind"], "command-output")


if __name__ == "__main__":
    unittest.main()
