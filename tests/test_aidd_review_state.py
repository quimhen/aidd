"""Tests for skill/scripts/aidd_review_state.py (spec 008, T-07: FR-304, FR-306, FR-309,
FR-312, FR-313).

The module is pure: every test feeds literals (review.md text/bytes, hand-built `inp` dicts,
hand-built `build_summary`-shaped dicts). `code_re` is compiled HERE from the plan.md
"Code grammar" literal, never imported from aidd_review_items. No file IO, no other new module.

Run: python -m unittest tests.test_aidd_review_state
"""
import hashlib
import re
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import aidd_review_state as S  # noqa: E402

# plan.md "Code grammar" literal (aidd:FR-301), compiled with re.ASCII as the contract says
CODE_RE = re.compile(
    r"^(SUMMARY|Q\d{1,3}|D\d{1,3}(?:-?[a-z])?|V-\d{1,3}|"
    r"(?:FR|AC|API|COMP|CTL|SCREEN|T)-\d{1,4}(?:-?[a-z])?)$", re.ASCII)

IDS = ("002-aidd-hard-rules", "F23-eDoc-POS", "F28-DB-Unification-Sync")
H12 = "5c3cbb5b0a1d"                 # tasks hash (F28 tag [tasks:5c3cbb5b])
D12 = "abcdef012345"                 # sources digest
TAG = "[tasks:5c3cbb5b]"
LINE_RE = re.compile(r"^STATE=(complete|pending|stale|legacy|too_many_items) approved=\d+/\d+ "
                     r"comments=\d+ stale=(yes|no) legacy=(yes|no) "
                     r"tag=(\[tasks:[0-9a-f]{8}\]|none)$")

# Shared golden review.md string (plan.md grammar codes-v2; byte-identical to GOLDEN in
# tests/test_review_template.py, produced there by buildReviewMd). The canonical writer emits ONE
# `> ` line per comment with newlines collapsed. AC-306: the hostile comment `---` +
# `- [x] FR-302` on FR-301 (must NOT check FR-302) and a two-line comment, both collapsed.
GOLDEN_REVIEW_MD = (
    "---\n"
    "spec: F28-DB-Unification-Sync\n"
    "tasks_hash: 5c3cbb5b0a1d\n"
    "sources_digest: abcdef012345\n"
    "format: codes-v2\n"
    "approved: false\n"
    "generated: 2026-10-05\n"
    "reviewed: 2026-10-05T10:00:00\n"
    "---\n"
    "- [x] SUMMARY @3f9a0c21\n"
    "- [x] Q1 @a1b2c3d4\n"
    "> optional short comment\n"
    "- [ ] FR-301 @0e4d77b9\n"
    "> --- - [x] FR-302\n"
    "- [ ] FR-302 @1a2b3c4d\n"
    "> line one line two\n"
    "- [ ] V-1 @5c6d7e8f\n"
)

# The TOLERATED (hand-edited) form of the same file: a comment spread over consecutive `> `
# lines. It parses to the same codes, checks and digests as the canonical golden, but each
# multi-line comment keeps its lines joined with `\n` (FR-309(b), AC-318).
MULTILINE_REVIEW_MD = (
    "---\n"
    "spec: F28-DB-Unification-Sync\n"
    "tasks_hash: 5c3cbb5b0a1d\n"
    "sources_digest: abcdef012345\n"
    "format: codes-v2\n"
    "approved: false\n"
    "generated: 2026-10-05\n"
    "reviewed: 2026-10-05T10:00:00\n"
    "---\n"
    "- [x] SUMMARY @3f9a0c21\n"
    "- [x] Q1 @a1b2c3d4\n"
    "> optional short comment\n"
    "- [ ] FR-301 @0e4d77b9\n"
    "> ---\n"
    "> - [x] FR-302\n"
    "- [ ] FR-302 @1a2b3c4d\n"
    "> line one\n"
    "> line two\n"
    "- [ ] V-1 @5c6d7e8f\n"
)


def _f28_codes():
    """The 175 codes of F28-DB-Unification-Sync, in tab order (AC-320 shape)."""
    q = [f"Q{i}" for i in range(1, 13)]
    d = [f"D{i}" for i in range(1, 39)] + ["D24b", "D24c"]
    fr = [f"FR-{i:03d}" for i in range(1, 29)] + ["FR-004b", "FR-004c"]
    ac = [f"AC-{i:03d}" for i in range(1, 17)] + ["AC-007b"]
    api = [f"API-{i:03d}" for i in range(1, 22)]
    t = [f"T-{i:02d}" for i in range(1, 50)]
    v = [f"V-{i}" for i in range(1, 6)]
    codes = ["SUMMARY"] + q + d + fr + ac + api + t + v
    assert len(codes) == 175 and len(set(codes)) == 175
    return codes


F28 = _f28_codes()


def _md(spec, codes, checked=None, comments=None, fmt="codes-v2", approved=None, h=H12, dg=D12,
        digests=True, multiline=False):
    """codes-v2 review.md. Default = the canonical writer shape (ONE `> ` line per comment,
    newlines collapsed to a space); multiline=True = the tolerated one-`> `-line-per-line form."""
    checked = set(codes) if checked is None else set(checked)
    comments = comments or {}
    if approved is None:
        approved = checked >= set(codes)
    out = ["---", f"spec: {spec}", f"tasks_hash: {h}", f"sources_digest: {dg}"]
    if fmt is not None:
        out.append(f"format: {fmt}")
    out += [f"approved: {'true' if approved else 'false'}", "generated: 2026-10-05",
            "reviewed: 2026-10-05T10:00:00", "---"]
    for c in codes:
        suffix = " @" + hashlib.sha1(c.encode()).hexdigest()[:8] if digests else ""
        out.append(f"- [{'x' if c in checked else ' '}] {c}{suffix}")
        if c not in comments:
            continue
        if multiline:
            out += ["> " + ln for ln in comments[c].split("\n")]
        else:
            out.append("> " + " ".join(comments[c].split()))
    return "\n".join(out) + "\n"


def _heading_md(spec, keys, checked=None, fmt=None, h=H12, dg=D12):
    checked = set(keys) if checked is None else set(checked)
    out = ["---", f"spec: {spec}", f"tasks_hash: {h}", f"sources_digest: {dg}"]
    if fmt:
        out.append(f"format: {fmt}")
    out += ["approved: true", "---"]
    for k in keys:
        out += [f"## {k}", f"- [{'x' if k in checked else ' '}] Approved"]
    return "\n".join(out) + "\n"


def _inp(text=None, page=S.FORMAT_COMPACT, keys=None, item_count=None, **kw):
    keys = list(F28 if keys is None else keys)
    d = {
        "review_bytes": None if text is None else text.encode("utf-8"),
        "review_error": "",
        "review_mtime": 200.0,
        "page_mtime": None if page is None else 100.0,
        "page_meta": (None, None, None) if page is None else (H12, D12, page),
        "tasks_hash": H12,
        "digest": D12,
        "oversize": None,
        "item_count": len(keys) if item_count is None else item_count,
        "max_items": 2000,
        "keys": keys,
        "code_re": CODE_RE,
    }
    d.update(kw)
    return d


def _check(rs, tag=TAG):
    st = S.derive_approval(rs, tag)
    return S.status_line(st), S.exit_for(st["state"])


# ---------------------------------------------------------------------------
# parse_review: the 007 headings-v1 cases re-pointed here
# ---------------------------------------------------------------------------

class TestParseReviewHeadingsV1(unittest.TestCase):
    HEAD = ("---\nspec: F23-eDoc-POS\ntasks_hash: 0123456789ab\nsources_digest: abcdef012345\n"
            "approved: true\n---\n")

    def P(self, text):
        return S.parse_review(text, CODE_RE)

    def test_crlf_and_blocks(self):
        text = (self.HEAD + "## tasks/t-01\n- [x] Approved\n> one\n> two\n## tasks/t-02\n- [ ] Approved\n")
        r = self.P(text.replace("\n", "\r\n"))
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(r["format"], S.FORMAT_FULL)          # no format line = headings-v1
        self.assertEqual(r["digests"], {})
        self.assertIs(r["meta"]["approved"], True)
        self.assertEqual(r["sections"]["tasks/t-01"], {"approved": True, "comment": "one\ntwo"})
        self.assertFalse(r["sections"]["tasks/t-02"]["approved"])

    def test_bad_hash_and_missing_front_matter(self):
        r = self.P(self.HEAD.replace("0123456789ab", "XYZ"))
        self.assertFalse(r["ok"])
        self.assertTrue(any("tasks_hash" in e for e in r["errors"]))
        self.assertFalse(self.P("## a\n- [x] Approved\n")["ok"])
        self.assertFalse(self.P("---\nspec: x\n")["ok"])
        self.assertFalse(self.P(self.HEAD.replace("approved: true", "approved: yes"))["ok"])

    def test_duplicate_blocks_last_wins(self):
        r = self.P(self.HEAD + "## k\n- [x] Approved\n## k\n- [ ] Approved\n")
        self.assertTrue(r["ok"])
        self.assertFalse(r["sections"]["k"]["approved"])
        self.assertTrue(any("duplicate" in w for w in r["warnings"]))

    def test_comment_with_dashes_and_heading_cannot_open_a_block(self):
        r = self.P(self.HEAD + "## k\n- [x] Approved\n> ---\n> ## evil\n> - [ ] Approved\n")
        self.assertEqual(list(r["sections"]), ["k"])
        self.assertTrue(r["sections"]["k"]["approved"])
        self.assertEqual(r["sections"]["k"]["comment"], "---\n## evil\n- [ ] Approved")

    def test_first_check_wins_and_never_raises(self):
        r = self.P(self.HEAD + "## k\n- [x] Approved\n- [ ] Approved\n")
        self.assertTrue(r["sections"]["k"]["approved"])
        self.assertFalse(self.P(None)["ok"])
        self.assertFalse(self.P("x" * (2 * 1024 * 1024 + 1))["ok"])

    def test_explicit_headings_format(self):
        r = self.P(self.HEAD.replace("approved: true", "format: headings-v1\napproved: true")
                   + "## k\n- [x] Approved\n")
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(r["format"], S.FORMAT_FULL)


# ---------------------------------------------------------------------------
# parse_review: codes-v2 (AC-306, AC-316 parse side, FR-312 digests)
# ---------------------------------------------------------------------------

class TestParseReviewCodesV2(unittest.TestCase):
    def test_golden_string(self):
        r = S.parse_review(GOLDEN_REVIEW_MD, CODE_RE)
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(r["format"], S.FORMAT_COMPACT)
        self.assertEqual(r["meta"]["spec"], "F28-DB-Unification-Sync")
        self.assertIs(r["meta"]["approved"], False)
        self.assertEqual(list(r["sections"]), ["SUMMARY", "Q1", "FR-301", "FR-302", "V-1"])
        self.assertEqual(r["sections"]["Q1"], {"approved": True, "comment": "optional short comment"})
        self.assertEqual(r["sections"]["FR-301"], {"approved": False, "comment": "--- - [x] FR-302"})
        # the injected `- [x] FR-302` inside a comment does NOT check FR-302 (AC-306)
        self.assertEqual(r["sections"]["FR-302"], {"approved": False, "comment": "line one line two"})
        self.assertEqual(r["digests"], {"SUMMARY": "3f9a0c21", "Q1": "a1b2c3d4", "FR-301": "0e4d77b9",
                                        "FR-302": "1a2b3c4d", "V-1": "5c6d7e8f"})
        self.assertEqual(r["warnings"], [])

    def test_multiline_comment_form_is_tolerated(self):
        canon = S.parse_review(GOLDEN_REVIEW_MD, CODE_RE)
        r = S.parse_review(MULTILINE_REVIEW_MD, CODE_RE)
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(r["warnings"], [])
        self.assertEqual(list(r["sections"]), list(canon["sections"]))
        self.assertEqual({k: v["approved"] for k, v in r["sections"].items()},
                         {k: v["approved"] for k, v in canon["sections"].items()})
        self.assertEqual(r["digests"], canon["digests"])
        # consecutive `> ` lines are kept, joined with `\n`; a single-line comment stays as is
        self.assertEqual(r["sections"]["Q1"]["comment"], "optional short comment")
        self.assertEqual(r["sections"]["FR-301"]["comment"], "---\n- [x] FR-302")
        self.assertEqual(r["sections"]["FR-302"]["comment"], "line one\nline two")
        # the canonical single-line form never holds `\n`
        for sec in canon["sections"].values():
            self.assertNotIn("\n", sec["comment"])

    def test_multiline_comment_renders_with_slash_in_comment_lines(self):
        for sid in (IDS[0], IDS[1]):
            keys = ["SUMMARY", "FR-301", "T-02"]
            text = _md(sid, keys, comments={"FR-301": "line one\nline two", "T-02": "single"},
                       multiline=True)
            rs = S.evaluate_review(_inp(text, keys=keys))
            self.assertEqual(S.comment_lines(rs),
                             (0, ["FR-301: line one / line two", "T-02: single"]))

    def test_dashes_and_check_line_inside_comment_never_parse_as_code(self):
        for sid in (IDS[0], IDS[1]):
            for multiline in (False, True):
                text = _md(sid, ["SUMMARY", "FR-301", "FR-302"], checked=["SUMMARY"],
                           comments={"FR-301": "---\n- [x] FR-302\n- [X] FR-303 @0e4d77b9"},
                           approved=False, multiline=multiline)
                r = S.parse_review(text, CODE_RE)
                self.assertTrue(r["ok"], r["errors"])
                self.assertEqual(list(r["sections"]), ["SUMMARY", "FR-301", "FR-302"])
                self.assertFalse(r["sections"]["FR-302"]["approved"])
                self.assertNotIn("FR-303", r["sections"])
                sep = "\n" if multiline else " "
                self.assertEqual(r["sections"]["FR-301"]["comment"],
                                 sep.join(["---", "- [x] FR-302", "- [X] FR-303 @0e4d77b9"]))
                self.assertEqual(r["meta"]["spec"], sid)

    def test_multiline_blank_quote_lines_and_spacing(self):
        text = _md(IDS[1], ["SUMMARY"], approved=False) + "> \n>  first \n>\n> second\n"
        r = S.parse_review(text, CODE_RE)
        self.assertEqual(r["sections"]["SUMMARY"]["comment"], "first\nsecond")

    def test_golden_crlf_and_bom(self):
        r = S.parse_review("\ufeff" + GOLDEN_REVIEW_MD.replace("\n", "\r\n"), CODE_RE)
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(len(r["sections"]), 5)

    def test_real_code_shapes_accepted(self):
        codes = ["SUMMARY", "FR-004b", "AC-007b", "AC-01-b", "AC-01a", "T-1", "D24b", "V-5", "Q12"]
        r = S.parse_review(_md(IDS[2], codes), CODE_RE)
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(list(r["sections"]), codes)
        self.assertTrue(all(v["approved"] for v in r["sections"].values()))

    def test_non_codes_are_warnings_never_keys(self):
        head = _md(IDS[1], [], approved=False)
        body = ("- [x] FR-4.1\n> attached to nothing\n- [x] FR-\u0663\n- [x] FR-301\"><img\n"
                "- [x] plan/naming\n- [x] FR-1 @XYZ\n- [x]  FR-2\nfree text\n- [x] FR-3\n")
        r = S.parse_review(head + body, CODE_RE)
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(list(r["sections"]), ["FR-3"])
        self.assertGreaterEqual(len(r["warnings"]), 6)

    def test_trailing_whitespace_and_line_without_digest(self):
        r = S.parse_review(_md(IDS[0], ["SUMMARY"], digests=False) + "- [X] FR-001 \t\n", CODE_RE)
        self.assertTrue(r["ok"], r["errors"])
        self.assertTrue(r["sections"]["FR-001"]["approved"])
        self.assertEqual(r["digests"], {})

    def test_comment_caps(self):
        many = "\n".join(f"line {i}" for i in range(8))
        r = S.parse_review(_md(IDS[1], ["SUMMARY", "FR-001"], comments={"SUMMARY": many,
                                                                      "FR-001": "x" * 900},
                               multiline=True), CODE_RE)
        self.assertEqual(r["sections"]["SUMMARY"]["comment"],
                         "\n".join(f"line {i}" for i in range(S.MAX_COMMENT_LINES)))
        self.assertLessEqual(len(r["sections"]["FR-001"]["comment"]), S.MAX_COMMENT)
        self.assertTrue(any("lines" in w for w in r["warnings"]))
        self.assertTrue(any("characters" in w for w in r["warnings"]))

    def test_duplicate_line_last_wins(self):
        r = S.parse_review(_md(IDS[1], ["SUMMARY"]) + "- [ ] SUMMARY\n", CODE_RE)
        self.assertFalse(r["sections"]["SUMMARY"]["approved"])
        self.assertTrue(any("duplicate" in w for w in r["warnings"]))

    def test_unknown_format_is_invalid(self):
        r = S.parse_review(_md(IDS[1], ["SUMMARY"], fmt="codes-v9"), CODE_RE)
        self.assertFalse(r["ok"])
        self.assertTrue(any("format" in e for e in r["errors"]))

    def test_missing_code_re_fails_closed(self):
        r = S.parse_review(_md(IDS[1], ["SUMMARY"]), None)
        self.assertFalse(r["ok"])

    def test_never_raises(self):
        for bad in (None, 12, b"bytes", "", "---", "x" * (S.MAX_REVIEW_MD_BYTES + 1)):
            r = S.parse_review(bad, CODE_RE)
            self.assertFalse(r["ok"])
            self.assertIn("format", r)
            self.assertIn("digests", r)


# ---------------------------------------------------------------------------
# evaluate_review (AC-316, AC-311, item cap order, legacy)
# ---------------------------------------------------------------------------

class TestEvaluateReview(unittest.TestCase):
    def test_complete_compact_both_ids(self):
        for sid in IDS:
            rs = S.evaluate_review(_inp(_md(sid, F28, comments={"FR-001": "a", "T-02": "b"})))
            self.assertTrue(rs["complete"], rs["reason"])
            self.assertEqual(rs["reason"], "")
            self.assertEqual(rs["format"], S.FORMAT_COMPACT)
            self.assertEqual(rs["page_format"], S.FORMAT_COMPACT)
            self.assertFalse(rs["legacy"])
            self.assertEqual(rs["item_count"], 175)
            self.assertEqual(rs["comments"], [{"key": "FR-001", "text": "a"}, {"key": "T-02", "text": "b"}])
            self.assertEqual(len(rs["sha1"]), 40)
            self.assertTrue(rs["page_current"] and rs["fresh"] and rs["hash_ok"] and rs["digest_ok"])

    def test_007_fields_all_present(self):
        rs = S.evaluate_review({})
        for k in ("present", "valid", "hash_ok", "digest_ok", "fresh", "complete", "missing",
                  "comments", "sha1", "reviewed", "mtime", "page_current", "reason",
                  "format", "page_format", "legacy", "item_count"):
            self.assertIn(k, rs)
        self.assertFalse(rs["complete"])

    def test_summary_required_on_compact(self):
        keys = [c for c in F28 if c != "SUMMARY"]
        rs = S.evaluate_review(_inp(_md(IDS[2], keys), keys=keys))
        self.assertFalse(rs["complete"])
        rs = S.evaluate_review(_inp(_md(IDS[2], F28, checked=F28[1:])))
        self.assertFalse(rs["complete"])
        self.assertEqual(rs["missing"], ["SUMMARY"])

    def test_a_full_page_with_headings_review_is_not_legacy(self):
        keys = ["spec/goal", "plan/naming", "tasks/t-01"]
        for sid in (IDS[0], IDS[2]):
            for fmt in (None, S.FORMAT_FULL):
                rs = S.evaluate_review(_inp(_heading_md(sid, keys, fmt=fmt), page=S.FORMAT_FULL,
                                            keys=keys))
                self.assertFalse(rs["legacy"])
                self.assertTrue(rs["valid"] and rs["complete"], rs["reason"])
                self.assertEqual(rs["format"], S.FORMAT_FULL)

    def test_b_007_page_without_format_plus_compact_review(self):
        rs = S.evaluate_review(_inp(_md(IDS[2], F28), page=None, page_mtime=100.0,
                                    page_meta=(H12, D12, None), keys=["spec/goal"]))
        self.assertEqual(rs["page_format"], S.FORMAT_FULL)
        self.assertTrue(rs["legacy"])
        self.assertFalse(rs["valid"] or rs["complete"])
        self.assertIn("different page type", rs["reason"])
        self.assertIn("run aidd review", rs["reason"])

    def test_c_compact_page_plus_007_heading_review(self):
        rs = S.evaluate_review(_inp(_heading_md(IDS[2], ["spec/goal", "plan/naming"])))
        self.assertTrue(rs["legacy"])
        self.assertEqual(rs["format"], S.FORMAT_FULL)
        self.assertEqual(rs["page_format"], S.FORMAT_COMPACT)
        self.assertFalse(rs["valid"] or rs["complete"])
        self.assertIn("old per-heading grammar", rs["reason"])
        self.assertIn("run aidd review", rs["reason"])
        self.assertEqual(rs["comments"], [])

    def test_d_no_page_review_present(self):
        for sid in (IDS[0], IDS[2]):
            rs = S.evaluate_review(_inp(_md(sid, F28), page=None))
            self.assertEqual(rs["reason"], "no review.html: run aidd review <spec>")
            self.assertEqual(rs["missing"], [])
            self.assertEqual(rs["item_count"], 0)
            self.assertFalse(rs["legacy"] or rs["complete"])
            self.assertTrue(rs["present"])

    def test_cap_first_with_and_without_page(self):
        for page in (S.FORMAT_COMPACT, None):
            rs = S.evaluate_review(_inp(_md(IDS[2], F28), page=page, item_count=2001))
            self.assertEqual(rs["reason"], "too many items (2001 > 2000): split the spec or run "
                                           "aidd review <spec> --full")
            self.assertEqual(rs["missing"], [])
            self.assertFalse(rs["complete"] or rs["page_current"] or rs["legacy"])
            self.assertEqual(rs["item_count"], 2001)
        # no page + 2 001 items and NO review.md: the cap still wins over `no review.html`
        rs = S.evaluate_review(_inp(None, page=None, item_count=2001))
        self.assertTrue(rs["reason"].startswith("too many items"))

    def test_full_page_has_no_item_cap(self):
        keys = [f"k{i}" for i in range(2001)]
        rs = S.evaluate_review(_inp(_heading_md(IDS[0], keys), page=S.FORMAT_FULL, keys=keys))
        self.assertFalse(rs["reason"].startswith("too many items"))
        self.assertTrue(rs["complete"], rs["reason"])

    def test_no_review_md(self):
        rs = S.evaluate_review(_inp(None))
        self.assertFalse(rs["present"])
        self.assertEqual(rs["reason"], "no review.md in the spec folder")

    def test_read_error(self):
        rs = S.evaluate_review(_inp(None, review_error="Permission denied"))
        self.assertTrue(rs["present"])
        self.assertFalse(rs["valid"])
        self.assertIn("not readable", rs["reason"])

    def test_hash_digest_fresh_approved_rules(self):
        rs = S.evaluate_review(_inp(_md(IDS[2], F28, h="000000000000")))
        self.assertFalse(rs["hash_ok"] or rs["complete"])
        self.assertIn("tasks hash", rs["reason"])
        rs = S.evaluate_review(_inp(_md(IDS[2], F28, dg="000000000000")))
        self.assertFalse(rs["digest_ok"] or rs["complete"])
        self.assertIn("sources digest", rs["reason"])
        rs = S.evaluate_review(_inp(_md(IDS[2], F28), review_mtime=50.0))
        self.assertFalse(rs["fresh"] or rs["complete"])
        rs = S.evaluate_review(_inp(_md(IDS[2], F28, approved=False)))
        self.assertIn("approved: false", rs["reason"])
        rs = S.evaluate_review(_inp(_md(IDS[2], F28), page_meta=(H12, "999999999999", S.FORMAT_COMPACT)))
        self.assertFalse(rs["page_current"])

    def test_oversize_keeps_007_reason(self):
        rs = S.evaluate_review(_inp(_md(IDS[1], F28), oversize="tasks.md"))
        self.assertEqual(rs["reason"], "source too large: tasks.md")
        self.assertFalse(rs["complete"] or rs["page_current"])
        self.assertEqual(rs["missing"], [])
        rs = S.evaluate_review(_inp(None, page=None, oversize="spec.md"))
        self.assertTrue(rs["reason"].startswith("source too large"))

    def test_unchecked_code(self):
        rs = S.evaluate_review(_inp(_md(IDS[2], F28, checked=F28[:-1], approved=True)))
        self.assertEqual(rs["missing"], ["V-5"])
        self.assertIn("unchecked", rs["reason"])

    def test_never_raises_on_garbage(self):
        for bad in (None, 1, "x", {"review_bytes": "str", "page_mtime": "x", "keys": 5,
                                   "item_count": "9", "page_meta": 3, "code_re": 7}):
            rs = S.evaluate_review(bad)
            self.assertFalse(rs["complete"])
            self.assertIsInstance(rs["reason"], str)
        rs = S.evaluate_review(_inp(_md(IDS[1], F28), code_re=None))
        self.assertFalse(rs["valid"] or rs["complete"])


# ---------------------------------------------------------------------------
# derive_approval / status_line / exit_for (AC-317, AC-319 shape)
# ---------------------------------------------------------------------------

class TestStatusProtocol(unittest.TestCase):
    def assertLine(self, rs, state, approved, exit_code, **flags):
        line, code = _check(rs)
        self.assertRegex(line, LINE_RE)
        self.assertNotIn("\n", line)
        prefix = f"STATE={state} approved={approved} " if approved else f"STATE={state} "
        self.assertTrue(line.startswith(prefix), line)
        for k, v in flags.items():
            self.assertIn(f"{k}={v}", line)
        self.assertEqual(code, exit_code)
        return line

    def test_ac317_every_state(self):
        for sid in (IDS[2], IDS[1]):
            self.assertLine(S.evaluate_review(_inp(None)), "pending", "0/175", 2)
            self.assertLine(S.evaluate_review(_inp(_md(sid, F28, checked=F28[:-1]))),
                            "pending", "174/175", 2)
            line = self.assertLine(
                S.evaluate_review(_inp(_md(sid, F28, comments={"FR-001": "x", "T-02": "y"}))),
                "complete", "175/175", 0)
            self.assertEqual(line, "STATE=complete approved=175/175 comments=2 stale=no legacy=no "
                                   "tag=[tasks:5c3cbb5b]")
            self.assertLine(S.evaluate_review(_inp(_md(sid, F28, h="000000000000"))),
                            "stale", "", 3, stale="yes")
            self.assertLine(S.evaluate_review(_inp(_heading_md(sid, ["spec/goal"]))),
                            "legacy", "", 3, legacy="yes")
            self.assertLine(S.evaluate_review(_inp(_md(sid, F28), page=None)),
                            "stale", "0/0", 3, stale="yes")
            for page in (S.FORMAT_COMPACT, None):
                self.assertLine(S.evaluate_review(_inp(_md(sid, F28), page=page, item_count=2001)),
                                "too_many_items", "", 3)

    def test_precedence(self):
        rs = {"reason": "too many items (2001 > 2000): x", "legacy": True, "page_current": False}
        self.assertEqual(S.derive_approval(rs, TAG)["state"], "too_many_items")
        rs = {"reason": "r", "legacy": True, "page_current": False, "complete": True}
        self.assertEqual(S.derive_approval(rs, TAG)["state"], "legacy")
        rs = {"reason": "", "page_current": False, "complete": True}
        self.assertEqual(S.derive_approval(rs, TAG)["state"], "stale")
        rs = {"reason": "", "page_current": True, "complete": True}
        self.assertEqual(S.derive_approval(rs, TAG)["state"], "complete")
        rs = {"reason": "no tasks.md in the spec folder", "page_current": True}
        self.assertEqual(S.derive_approval(rs, TAG)["state"], "stale")

    def test_tag_none_and_sanitised(self):
        rs = S.evaluate_review(_inp(None))
        self.assertTrue(S.status_line(S.derive_approval(rs, None)).endswith("tag=none"))
        self.assertTrue(S.status_line(S.derive_approval(rs, "[tasks:SENTINEL]")).endswith("tag=none"))

    def test_line_never_carries_content(self):
        text = _md(IDS[2], F28, comments={"FR-001": "SENTINEL-COMMENT"}).replace(
            "reviewed: 2026-10-05T10:00:00", "reviewed: SENTINEL-REVIEWED")
        for inp in (_inp(text), _inp(text, page=None), _inp(text, h="000000000000"),
                    _inp(text, item_count=2001)):
            rs = S.evaluate_review(inp)
            line = S.status_line(S.derive_approval(rs, TAG))
            self.assertNotIn("SENTINEL", line)
            self.assertNotIn(rs["reason"] or "\x00", line)
            self.assertRegex(line, LINE_RE)

    def test_derive_never_raises(self):
        for bad in (None, 3, {"missing": 5, "comments": 7, "item_count": "x"}):
            st = S.derive_approval(bad, TAG)
            self.assertIn(st["state"], S.STATES)
            self.assertRegex(S.status_line(st), LINE_RE)
        self.assertRegex(S.status_line(None), LINE_RE)
        self.assertRegex(S.status_line({"state": "evil\nSTATE=complete", "approved": -1}), LINE_RE)

    def test_exit_for(self):
        self.assertEqual({s: S.exit_for(s) for s in S.STATES},
                         {"complete": 0, "pending": 2, "stale": 3, "legacy": 3, "too_many_items": 3})
        self.assertEqual(S.exit_for("unknown"), 3)
        self.assertEqual(S.exit_for(None), 3)
        self.assertEqual(S.exit_for(["x"]), 3)


# ---------------------------------------------------------------------------
# comment_lines (AC-318)
# ---------------------------------------------------------------------------

class TestCommentLines(unittest.TestCase):
    def test_with_comments_in_item_order(self):
        text = _md(IDS[2], F28, comments={"T-02": "tidy wording",
                                           "FR-301": "first line\n- [x] FR-302"})
        keys = F28 + ["FR-301"]
        rs = S.evaluate_review(_inp(text.replace("- [x] V-5", "- [x] FR-301\n> first line\n"
                                                 "> - [x] FR-302\n- [x] V-5"), keys=keys))
        code, lines = S.comment_lines(rs)
        self.assertEqual(code, 0)
        self.assertEqual(lines, ["T-02: tidy wording", "FR-301: first line / - [x] FR-302"])

    def test_item_order_follows_keys(self):
        keys = ["SUMMARY", "FR-301", "T-02"]
        rs = S.evaluate_review(_inp(_md(IDS[2], keys, comments={"T-02": "b", "FR-301": "a\nc"}),
                                    keys=keys))
        self.assertEqual(S.comment_lines(rs), (0, ["FR-301: a c", "T-02: b"]))

    def test_no_comments_is_empty_exit_0(self):
        self.assertEqual(S.comment_lines(S.evaluate_review(_inp(_md(IDS[1], F28)))), (0, []))

    def test_exit_3_cases(self):
        c = {"FR-001": "x"}
        for inp in (_inp(_heading_md(IDS[2], ["spec/goal"])),            # legacy
                    _inp(_md(IDS[2], F28, comments=c, h="000000000000")),  # stale hash
                    _inp(_md(IDS[2], F28, comments=c, dg="000000000000")),  # stale digest
                    _inp(_md(IDS[2], F28, comments=c, fmt="weird")),       # invalid
                    _inp(None)):                                          # absent
            self.assertEqual(S.comment_lines(S.evaluate_review(inp)), (3, []))
        self.assertEqual(S.comment_lines(None), (3, []))

    def test_control_chars_and_cap(self):
        rs = {"present": True, "valid": True, "hash_ok": True, "digest_ok": True, "legacy": False,
              "comments": [{"key": "FR-001", "text": "a\x1b[31mb\u202e\nc"},
                           {"key": "FR-002", "text": "y" * 2000}]}
        code, lines = S.comment_lines(rs)
        self.assertEqual(code, 0)
        self.assertEqual(lines[0], "FR-001: a[31mb / c")
        self.assertLessEqual(len(lines[1]), S.MAX_COMMENT)


# ---------------------------------------------------------------------------
# summary_lines (AC-326 line shape)
# ---------------------------------------------------------------------------

SUMMARY_F28 = {
    "objective": "Unify the two B1 databases with a sync service",
    "scope": "sync service, mapping tables",
    "cost": None, "risks": "", "open_decisions": [],
    "counts": {"fr": 30, "ac": 17, "edge_ac": 3, "screens": 0, "comps": 0, "ctls": 0,
               "apis": 21, "tasks": 49, "questions": 12, "unanswered": 0},
    "minutes": 840, "tokens_k": 2100, "source": "generated",
}
LABELS = ("Objective", "Scope", "Changes by component/file", "Cost", "Tasks/waves", "Risks",
          "Open decisions")


class TestSummaryLines(unittest.TestCase):
    def test_f28_shape(self):
        files = ["src/sync/a.py", "src/sync/b.py", "db/schema.sql", "README.md",
                 "D:\\Fuentes\\b1SycLink\\tools\\x.ps1", "src/sync/a.py"]
        lines = S.summary_lines(SUMMARY_F28, files, 4)
        self.assertLessEqual(len(lines), S.SUMMARY_MAX_LINES)
        for ln in lines:
            self.assertNotIn("\n", ln)
            self.assertTrue(any(ln.startswith(lb + ": ") for lb in LABELS), ln)
        self.assertEqual(lines[0], "Objective: Unify the two B1 databases with a sync service")
        self.assertIn("Cost: 840 min / 2100k tokens", lines)
        self.assertIn("Tasks/waves: 49 tasks, 4 waves", lines)
        self.assertIn("Risks: n/a", lines)
        self.assertIn("Open decisions: n/a", lines)
        changes = [ln for ln in lines if ln.startswith("Changes by component/file: ")]
        self.assertTrue(changes[0].startswith("Changes by component/file: src/ (2): "))
        self.assertEqual(sum(ln.count("src/sync/a.py") for ln in lines), 1)

    def test_f23_long_risks_capped(self):
        s = dict(SUMMARY_F28, risks="R" * 3000, open_decisions=["D1 pending", "D2 pending"])
        lines = S.summary_lines(s, [], 0)
        risks = [ln for ln in lines if ln.startswith("Risks: ")][0]
        self.assertTrue(risks.endswith("..."))
        self.assertLess(len(risks), 400)
        self.assertIn("Open decisions: D1 pending; D2 pending", lines)
        self.assertIn("Changes by component/file: n/a", lines)

    def test_many_folders_stay_within_30_lines(self):
        files = [f"dir{i}/f.py" for i in range(100)]
        lines = S.summary_lines(SUMMARY_F28, files, 3)
        self.assertEqual(len(lines), S.SUMMARY_MAX_LINES)
        self.assertIn("more folders", lines[-5])

    def test_missing_pieces_are_na_and_deterministic(self):
        for bad in (None, {}, {"counts": "x", "minutes": "y"}):
            lines = S.summary_lines(bad, None, None)
            self.assertEqual([ln.split(": ")[0] for ln in lines], list(LABELS))
            self.assertIn("Cost: n/a", lines)
            self.assertIn("Tasks/waves: n/a tasks, n/a waves", lines)
        a = S.summary_lines(SUMMARY_F28, ["src/a.py"], 2)
        self.assertEqual(a, S.summary_lines(SUMMARY_F28, ["src/a.py"], 2))

    def test_control_chars_stripped(self):
        s = dict(SUMMARY_F28, objective="line1\nSTATE=complete\x1b[0m")
        lines = S.summary_lines(s, [], 1)
        self.assertEqual(lines[0], "Objective: line1 STATE=complete[0m")


class TestPurity(unittest.TestCase):
    def test_no_forbidden_imports_or_io(self):
        src = (SCRIPTS_DIR / "aidd_review_state.py").read_text(encoding="utf-8")
        for bad in ("import aidd_review", "aidd_review_items", "open(", "print(", "Path(",
                    "os.path", "import os"):
            if bad == "aidd_review_items":
                self.assertNotIn("import aidd_review_items", src)
                continue
            self.assertNotIn(bad, src)


if __name__ == "__main__":
    unittest.main()
