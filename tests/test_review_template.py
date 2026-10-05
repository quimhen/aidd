"""Tests for the review page templates (spec 008 T-02): skill/templates/review.html (compact,
tabbed) and skill/templates/review-full.html (the 007 long page under its new name).

Template files only: no aidd_review import. `aidd_review_items.CODE_RE` is compared only when
that module is importable (the main agent's end-of-wave run); node tests skip when node is missing.

aidd:FR-303 aidd:FR-304 aidd:FR-305 aidd:FR-308 aidd:FR-310 aidd:FR-311 aidd:FR-312
aidd:AC-306 aidd:AC-308 aidd:AC-312 aidd:AC-314 aidd:AC-323 aidd:AC-324
"""
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "skill" / "templates"
MIRRORS = ROOT / "adapters" / "dot-aidd" / "templates"
COMPACT = TEMPLATES / "review.html"
FULL = TEMPLATES / "review-full.html"
TOKENS = ["TITLE", "SPEC_ID", "TASKS_HASH", "TASKS_HASH8", "SOURCES_DIGEST",
          "GENERATED", "BODY", "DATA_JSON", "SCRIPT_SHA256"]
CSP = ("default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; "
       "script-src 'sha256-{{SCRIPT_SHA256}}'; base-uri 'none'; form-action 'none'")
SCRIPT_RE = re.compile(r'<script id="aidd-js">(.*?)</script>', re.S)
# the code grammar, equal to aidd_review_items.CODE_RE.pattern: FR/AC/T keep 1 to 4 digits,
# the SCREEN/COMP/CTL/API families take 1 to 5 digits
CODE_RE_LITERAL = (r"^(SUMMARY|Q\d{1,3}|D\d{1,3}(?:-?[a-z])?|V-\d{1,3}|(?:FR|AC|T)-\d{1,4}(?:-?[a-z])?|"
                   r"(?:API|COMP|CTL|SCREEN)-\d{1,5}(?:-?[a-z])?)$")
CANDIDATES = ["FR-004b", "AC-01-n", "V-5", "D24b", "FR-4.1", "FR-" + chr(0x0663), "FR-1\n",
              'FR-301"><img', "SUMMARY", "Q12", "T-1", "AC-01a", "API-027", "SCREEN-04",
              "FR-nnn", "summary", "FR-12345", "X-1", "",
              "SCREEN-12345", "COMP-10001", "CTL-00042b", "API-12345", "SCREEN-123456", "T-12345",
              "AC-12345", "COMP-" + chr(0x0663) * 5]
FIVE_DIGIT = {"SCREEN-12345": True, "COMP-10001": True, "CTL-00042b": True, "API-12345": True,
              "SCREEN-123456": False, "T-12345": False, "AC-12345": False, "FR-12345": False,
              "COMP-" + chr(0x0663) * 5: False}
F28 = "F28-DB-Unification-Sync"
F13 = "F13-eDoc-Emission-Engine"
F23 = "F23-eDoc-POS"
NUM = "002-aidd-hard-rules"
H_F28 = "5c3cbb5b0a1d"
NODE = shutil.which("node")

# Shared golden (same front matter, codes and digests as tests/test_aidd_review_state.py
# GOLDEN_REVIEW_MD). The page writes ONE `> ` line per comment (newlines collapsed, tasks.md T-02),
# so the hostile and two-line comments of AC-306 appear here collapsed onto one line each.
GOLDEN = (
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
GOLDEN_INPUT = {
    "spec": F28, "tasks_hash": H_F28, "sources_digest": "abcdef012345",
    "generated": "2026-10-05", "reviewed": "2026-10-05T10:00:00",
    "codes": ["SUMMARY", "Q1", "FR-301", "FR-302", "V-1"],
    "digests": {"SUMMARY": "3f9a0c21", "Q1": "a1b2c3d4", "FR-301": "0e4d77b9",
                "FR-302": "1a2b3c4d", "V-1": "5c6d7e8f"},
    "items": {"SUMMARY": {"approved": True, "comment": ""},
              "Q1": {"approved": True, "comment": "optional short comment"},
              "FR-301": {"approved": False, "comment": "---\n- [x] FR-302"},
              "FR-302": {"approved": False, "comment": "line one\r\nline two"},
              "V-1": {"approved": False, "comment": ""}},
}


def _text(path):
    return path.read_text(encoding="utf-8")


def _js(path):
    found = SCRIPT_RE.findall(_text(path))
    assert len(found) == 1, "expected one <script id=aidd-js> in %s" % path
    return found[0]


def _js_decoded(path):
    """The script with JS \\uXXXX escapes decoded (the script itself is ASCII)."""
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), _js(path))


def _picker_id(spec):
    return "aidd-" + hashlib.sha1(spec.encode("utf-8")).hexdigest()[:8]


def _fill(template_text, blob, body=""):
    """A minimal filled page (the generator's job, done here only to get a realistic review.html)."""
    js = SCRIPT_RE.search(template_text).group(1)
    sha = base64.b64encode(hashlib.sha256(js.encode("utf-8")).digest()).decode("ascii")
    payload = json.dumps(blob).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    values = {"{{TITLE}}": "Review " + blob.get("spec", ""), "{{SPEC_ID}}": blob.get("spec", ""),
              "{{TASKS_HASH}}": blob.get("tasks_hash", ""), "{{TASKS_HASH8}}": blob.get("tasks_hash", "")[:8],
              "{{SOURCES_DIGEST}}": "abcdef012345", "{{GENERATED}}": "2026-10-05", "{{BODY}}": body,
              "{{DATA_JSON}}": payload, "{{SCRIPT_SHA256}}": sha}
    rx = re.compile("|".join(re.escape(k) for k in values))
    return rx.sub(lambda m: values[m.group(0)], template_text)


def _items_module():
    """aidd_review_items when importable (built by T-01), else None."""
    sys.path.insert(0, str(ROOT / "skill" / "scripts"))
    try:
        import aidd_review_items  # noqa: PLC0415
        return aidd_review_items
    except Exception:  # noqa: BLE001 -- absent inside the wave: the main agent's run covers it
        return None
    finally:
        try:
            sys.path.remove(str(ROOT / "skill" / "scripts"))
        except ValueError:
            pass


class _Common:
    """Checks every review template passes (mixed into one TestCase per template)."""
    SRC = None

    def test_mirror_is_byte_identical(self):
        mirror = MIRRORS / self.SRC.name
        self.assertTrue(mirror.is_file(), "adapters mirror missing: %s" % mirror)
        self.assertEqual(self.SRC.read_bytes(), mirror.read_bytes())

    def test_utf8_lf(self):
        raw = self.SRC.read_bytes()
        raw.decode("utf-8")
        self.assertNotIn(b"\r", raw)

    def test_tokens_present_and_no_unknown(self):
        t = _text(self.SRC)
        self.assertEqual(sorted(set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", t))), sorted(TOKENS))
        for tok in ("BODY", "DATA_JSON", "SCRIPT_SHA256"):
            self.assertEqual(t.count("{{%s}}" % tok), 1, tok)
        self.assertRegex(t, r'<script type="application/json" id="aidd-data">\{\{DATA_JSON\}\}</script>')
        self.assertIn("<title>Review - {{TITLE}}</title>", t)
        self.assertRegex(t, r'id="aidd-root"[^>]*data-spec="\{\{SPEC_ID\}\}"')
        for attr in ('data-tasks-hash="{{TASKS_HASH}}"', 'data-tasks-hash8="{{TASKS_HASH8}}"',
                     'data-sources-digest="{{SOURCES_DIGEST}}"', 'data-generated="{{GENERATED}}"'):
            self.assertIn(attr, t)
        self.assertLess(t.index("{{BODY}}"), t.index('id="aidd-data"'))
        self.assertLess(t.index('id="aidd-data"'), t.index('id="aidd-js"'))

    def test_csp_exact_policy(self):
        csp = re.findall(r'Content-Security-Policy" content="([^"]*)"', _text(self.SRC))
        self.assertEqual(csp, [CSP])

    def test_single_script_with_constant_text(self):
        t = _text(self.SRC)
        self.assertEqual(len(re.findall(r"<script\b", t)), 2)  # the JSON data block + the one script
        self.assertEqual(len(re.findall(r'<script id="aidd-js">', t)), 1)
        js = _js(self.SRC)
        self.assertNotIn("{{", js)
        self.assertNotIn("</script", js.lower())

    def test_script_hash_substitutes_into_csp(self):
        js = _js(self.SRC)
        b64 = base64.b64encode(hashlib.sha256(js.encode("utf-8")).digest()).decode("ascii")
        page = _fill(_text(self.SRC), {"spec": F23, "tasks_hash": "0123456789ab"},
                     body="<p>{{SCRIPT_SHA256}} &lt;script&gt;alert(1)&lt;/script&gt;</p>")
        self.assertIn("script-src 'sha256-%s'" % b64, page)
        self.assertEqual(SCRIPT_RE.search(page).group(1), js)
        # single pass: a {{TOKEN}} inside a substituted value is never substituted again
        self.assertIn("<p>{{SCRIPT_SHA256}} ", page)

    def test_no_external_resource(self):
        t = _text(self.SRC)
        self.assertNotRegex(t, r"https?://")
        self.assertNotRegex(t, r"""(?:src|href)\s*=\s*["']?\s*(?:https?:)?//""")
        self.assertNotIn("@import", t)

    def test_no_inline_handler_or_eval(self):
        t = _text(self.SRC)
        self.assertNotRegex(t, r"<[a-zA-Z][^<>]*\son[a-z]+\s*=")
        self.assertNotRegex(t, r"\beval\s*\(")
        self.assertNotRegex(t, r"new\s+Function\s*\(")
        self.assertNotIn("innerHTML", t)
        self.assertNotIn("outerHTML", t)
        self.assertNotIn("insertAdjacentHTML", t)
        self.assertNotIn("document.write", t)

    def test_download_type_and_name(self):
        js = _js(self.SRC)
        self.assertNotIn("text/markdown", _text(self.SRC))
        self.assertIn("application/octet-stream", js)
        self.assertRegex(js, r"\.download = 'review\.md'")

    def test_storage_and_picker_uses_guarded(self):
        js = _js(self.SRC)
        for api in ("showDirectoryPicker", "indexedDB", "localStorage", "sessionStorage"):
            for m in re.finditer(api, js):
                before = js[max(0, m.start() - 200):m.start()]
                line = js[js.rfind("\n", 0, m.start()) + 1:m.start()]
                self.assertTrue("try" in before or "typeof" in line,
                                "%s at %d is neither inside try nor feature-tested" % (api, m.start()))


class CompactTemplate(_Common, unittest.TestCase):
    SRC = COMPACT

    def test_ui_contract_markers(self):
        t = _text(COMPACT)
        for needle in ('role="tablist"', 'role="tab"', 'role="tabpanel"', "aria-selected", "aria-live",
                       "application/octet-stream", "maxlength", 'id="aidd-approve"', 'role="alert"',
                       "prefers-color-scheme:dark", "min-width:360px", "overflow-x:auto", "min-height:44px",
                       "@media print", "<noscript>", "codes-v2", "Fallback: typed consent",
                       "approve [tasks:{{TASKS_HASH8}}]", "data-mandatory", "localStorage", "sessionStorage",
                       "buildReviewMd", "missingSummary", "folderMatches", "pickerId", "saveReview",
                       "aidd-warn", "module.exports"):
            self.assertIn(needle, t, needle)

    def test_owner_texts(self):
        js = _js_decoded(COMPACT)
        for needle in ("Guardar progreso", "Aprobar y guardar", "Aprobar todo en esta pestaña",
                       "Cada verificación se marca a mano: confirma que el comando y lo esperado son correctos.",
                       "Progreso guardado (", "): no es una aprobación", "Arrastrados ", "; pendientes: ",
                       "Folder picker failed (", "): using the download instead", "This folder belongs to ",
                       ": pick specs/", "if the browser renamed it, save it over specs/",
                       "Nothing else to do: the agent is waiting and will ask you once.",
                       "'verification'", "Falta: "):
            self.assertIn(needle, js, needle)

    def test_removed_controls(self):
        t = _text(COMPACT)
        for gone in ("Save draft", "Approve all (except mandatory)", "Approve all", "Check all in"):
            self.assertNotIn(gone, t, gone)

    def test_code_re_src_equals_plan_literal(self):
        m = re.search(r"var CODE_RE_SRC = '((?:[^'\\]|\\.)*)';", _js(COMPACT))
        self.assertIsNotNone(m)
        js_src = re.sub(r"\\(.)", r"\1", m.group(1))  # JS string literal -> its value
        self.assertEqual(js_src, CODE_RE_LITERAL)
        py = re.compile(js_src, re.ASCII)
        self.assertEqual({c: py.fullmatch(c) is not None for c in FIVE_DIGIT}, FIVE_DIGIT)
        items = _items_module()
        if items is not None:  # the end-of-wave run: Python CODE_RE is the same string
            self.assertEqual(items.CODE_RE.pattern, js_src)

    def test_items_get_one_line_comment_input(self):
        js = _js(COMPACT)
        self.assertIn("setAttribute('maxlength', '200')", js)
        self.assertIn("'aidd-c'", js)

    def test_no_markdown_rendering_in_compact_page(self):
        t = _text(COMPACT)
        self.assertNotIn("render_markdown", t)
        self.assertNotIn("<article", t)


class FullTemplate(_Common, unittest.TestCase):
    SRC = FULL

    def test_front_matter_format_line(self):
        js = _js(FULL)
        self.assertIn("'format: headings-v1'", js)
        self.assertNotIn("codes-v2", js)

    def test_keeps_007_page(self):
        t = _text(FULL)
        for needle in ("section[data-key]", "Approve all (except mandatory)", "## ", "- [", "] Approved"):
            self.assertIn(needle, t, needle)


@unittest.skipUnless(NODE, "node not on PATH: page JS tests skipped")
class NodeCompact(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="aidd-rt-"))
        cls.js = cls.tmp / "aidd.js"
        cls.js.write_text(_js(COMPACT), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _call(self, fn, *args):
        harness = self.tmp / "call.js"
        harness.write_text(
            "const m=require(process.argv[2]);const a=JSON.parse(require('fs').readFileSync(process.argv[3],'utf8'));"
            "const r=m[a.fn].apply(null,a.args);process.stdout.write(JSON.stringify(r===undefined?null:r));",
            encoding="utf-8")
        argf = self.tmp / "args.json"
        argf.write_text(json.dumps({"fn": fn, "args": list(args)}), encoding="utf-8")
        r = subprocess.run([NODE, str(harness), str(self.js), str(argf)], capture_output=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        return json.loads(r.stdout.decode("utf-8"))

    # ---- syntax, grammar parity ----
    def test_node_check(self):
        r = subprocess.run([NODE, "--check", str(self.js)], capture_output=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))

    def test_code_re_parity(self):
        harness = self.tmp / "parity.js"
        harness.write_text(
            "const m=require(process.argv[2]);const c=JSON.parse(require('fs').readFileSync(process.argv[3],'utf8'));"
            "const rx=new RegExp(m.CODE_RE_SRC);"
            "process.stdout.write(JSON.stringify({src:m.CODE_RE_SRC,res:c.map(x=>rx.test(x))}));", encoding="utf-8")
        cf = self.tmp / "cand.json"
        cf.write_text(json.dumps(CANDIDATES), encoding="utf-8")
        r = subprocess.run([NODE, str(harness), str(self.js), str(cf)], capture_output=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        out = json.loads(r.stdout.decode("utf-8"))
        self.assertEqual(out["src"], CODE_RE_LITERAL)
        py = re.compile(CODE_RE_LITERAL, re.ASCII)
        expected = [bool(py.fullmatch(c)) for c in CANDIDATES]
        self.assertEqual(out["res"], expected)
        self.assertEqual(dict(zip(CANDIDATES[:8], expected[:8])),
                         {"FR-004b": True, "AC-01-n": True, "V-5": True, "D24b": True, "FR-4.1": False,
                          "FR-" + chr(0x0663): False, "FR-1\n": False, 'FR-301"><img': False})
        got = dict(zip(CANDIDATES, out["res"]))
        self.assertEqual({c: got[c] for c in FIVE_DIGIT}, FIVE_DIGIT)
        items = _items_module()
        if items is not None:
            self.assertEqual(out["res"], [bool(items.CODE_RE.fullmatch(c)) for c in CANDIDATES])

    # ---- buildReviewMd (aidd:FR-304, AC-306) ----
    def test_golden_string(self):
        self.assertEqual(self._call("buildReviewMd", GOLDEN_INPUT), GOLDEN)

    def test_golden_equals_state_golden(self):
        """The page output (single `> ` line per comment) is the canonical form the state module parses."""
        try:
            from tests.test_aidd_review_state import GOLDEN_REVIEW_MD  # noqa: PLC0415
        except Exception:  # noqa: BLE001 -- run outside the repo root: nothing to compare
            self.skipTest("tests.test_aidd_review_state not importable")
        self.assertEqual(GOLDEN, GOLDEN_REVIEW_MD)

    def test_hostile_comments_cannot_forge(self):
        out = self._call("buildReviewMd", GOLDEN_INPUT)
        lines = out.split("\n")
        self.assertEqual([ln for ln in lines if ln == "---"], ["---", "---"])
        checks = [ln for ln in lines if ln.startswith("- [")]
        self.assertEqual(checks, ["- [x] SUMMARY @3f9a0c21", "- [x] Q1 @a1b2c3d4", "- [ ] FR-301 @0e4d77b9",
                                  "- [ ] FR-302 @1a2b3c4d", "- [ ] V-1 @5c6d7e8f"])
        for ln in lines[9:]:
            self.assertTrue(ln == "" or ln.startswith("- [") or ln.startswith("> "), repr(ln))
        self.assertNotIn("\r", out)

    def test_one_line_per_code_and_order(self):
        codes = ["SUMMARY", "Q1", "D24b", "FR-004b", "AC-01-n", "T-1", "V-5"]
        out = self._call("buildReviewMd", {"spec": NUM, "tasks_hash": "0123456789ab",
                                           "sources_digest": "ba9876543210", "codes": codes, "items": {}})
        body = out.split("---\n", 2)[2]
        self.assertEqual(body, "".join("- [ ] %s\n" % c for c in codes))
        self.assertIn("approved: false", out)
        self.assertIn("format: codes-v2", out)
        self.assertNotIn("generated:", out)

    def test_non_codes_dropped_and_counted(self):
        r = self._call("buildReviewMdEx", {"spec": F23, "tasks_hash": "0123456789ab", "sources_digest": "ba9876543210",
                                           "codes": ["FR-004b", "spec/goal", 'FR-301"><img', "D24b", "FR-1\n",
                                                     "FR-004b", "__proto__"],
                                           "items": {"FR-004b": {"approved": True}, "D24b": {"approved": True}}})
        self.assertEqual(r["skipped"], 5)
        self.assertEqual(r["text"].split("---\n", 2)[2], "- [x] FR-004b\n- [x] D24b\n")
        self.assertIn("approved: true", r["text"])
        self.assertIn("spec: F23-eDoc-POS\n", r["text"])

    def test_digest_only_when_8_hex(self):
        out = self._call("buildReviewMd", {"spec": F23, "tasks_hash": "0123456789ab", "sources_digest": "ba9876543210",
                                           "codes": ["FR-1", "FR-2", "FR-3"],
                                           "digests": {"FR-1": "0123abcd", "FR-2": "0123ABCD", "FR-3": "12 34"},
                                           "items": {}})
        self.assertIn("- [ ] FR-1 @0123abcd\n- [ ] FR-2\n- [ ] FR-3\n", out)

    def test_all_checked_is_approved_true(self):
        codes = ["SUMMARY", "Q1", "V-1"]
        out = self._call("buildReviewMd", {"spec": NUM, "tasks_hash": "0123456789ab", "sources_digest": "ba9876543210",
                                           "codes": codes, "items": {c: {"approved": True, "comment": "ok"} for c in codes}})
        self.assertIn("approved: true", out)
        self.assertEqual(out.count("> ok\n"), 3)

    def test_empty_codes_never_approved(self):
        out = self._call("buildReviewMd", {"spec": NUM, "tasks_hash": "0123456789ab", "sources_digest": "ba9876543210",
                                           "codes": []})
        self.assertIn("approved: false", out)
        self.assertTrue(out.endswith("---\n"))
        none = self._call("buildReviewMd", {"spec": NUM})
        self.assertIn("approved: false", none)

    def test_comment_capped_and_collapsed(self):
        out = self._call("buildReviewMd", {"spec": NUM, "tasks_hash": "0123456789ab", "sources_digest": "ba9876543210",
                                           "codes": ["FR-1"], "items": {"FR-1": {"approved": False,
                                                                              "comment": "a\r\n\r\nb\t" + "x" * 900}}})
        cl = [ln for ln in out.split("\n") if ln.startswith("> ")]
        self.assertEqual(len(cl), 1)
        self.assertTrue(cl[0].startswith("> a b x"))
        self.assertLessEqual(len(cl[0]) - 2, 500)

    # ---- missingSummary (aidd:FR-310, AC-323) ----
    def _f28_codes(self):
        return (["SUMMARY"] + ["Q%d" % i for i in range(1, 13)] + ["D%d" % i for i in range(1, 39)]
                + ["D24b", "D24c"] + ["FR-%03d" % i for i in range(1, 29)] + ["FR-004b", "FR-004c"]
                + ["AC-%03d" % i for i in range(1, 17)] + ["AC-007b"] + ["API-%03d" % i for i in range(1, 22)]
                + ["T-%02d" % i for i in range(1, 50)] + ["V-%d" % i for i in range(1, 6)])

    def test_missing_summary_f28(self):
        codes = self._f28_codes()
        self.assertEqual(len(codes), 175)
        checked = {c: not c.startswith("V-") for c in codes}
        self.assertEqual(self._call("missingSummary", {"codes": codes}, checked), "Falta: Verificación V-1..V-5")
        checked["T-17"] = False
        self.assertEqual(self._call("missingSummary", {"codes": codes}, checked),
                         "Falta: Tareas T-17; Verificación V-1..V-5")
        self.assertEqual(self._call("missingSummary", {"codes": codes}, {c: True for c in codes}), "")
        arr = [c for c in codes if c != "SUMMARY"]
        self.assertEqual(self._call("missingSummary", {"codes": codes}, arr), "Falta: Resumen SUMMARY")

    def test_missing_summary_ranges_and_cap(self):
        codes = ["T-1", "T-2", "T-4", "FR-004b", "FR-005", "FR-006", "Q1", "Q2", "D1", "D24b"]
        out = self._call("missingSummary", {"codes": codes}, {})
        self.assertEqual(out, "Falta: Preguntas Q1..Q2, D1, D24b; Requisitos FR-004b, FR-005..FR-006; Tareas T-1..T-2, T-4")
        many = ["T-%d" % (2 * i) for i in range(1, 20)]  # 19 non-consecutive groups
        out = self._call("missingSummary", {"codes": many}, {})
        self.assertTrue(out.endswith("; +7 more"), out)
        self.assertEqual(out.count(", ") + 1, 12)

    # ---- pickerId (aidd:FR-305, AC-308) ----
    def test_picker_id(self):
        valid = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
        for spec in (F28, F13, F23, NUM):
            pid = self._call("pickerId", {"spec": spec, "picker_id": _picker_id(spec)})
            self.assertEqual(pid, _picker_id(spec))
            self.assertEqual(len(pid), 13)
        bare = self._call("pickerId", {"spec": F28})
        self.assertRegex(bare, r"^aidd-[0-9a-f]{8}$")
        self.assertEqual(bare, self._call("pickerId", {"spec": F28}))
        self.assertNotEqual(bare, self._call("pickerId", {"spec": F13}))
        raw = self._call("pickerId", {"spec": F28, "picker_id": "aidd-spec-" + F28})  # 33 chars
        self.assertRegex(raw, valid)
        self.assertEqual(raw, ("aidd-spec-" + F28)[:32])
        self.assertEqual(self._call("pickerId", {"spec": F28, "picker_id": 'a"b /c<>d'}), "abcd")
        self.assertRegex(self._call("pickerId", {"spec": F28, "picker_id": "/// "}), r"^aidd-[0-9a-f]{8}$")
        self.assertRegex(self._call("pickerId", {}), r"^aidd-[0-9a-f]{8}$")
        self.assertRegex(self._call("pickerId", None), r"^aidd-[0-9a-f]{8}$")

    # ---- folderMatches (aidd:FR-305) ----
    def _page(self, blob):
        return _fill(_text(COMPACT), blob, body='<p>id="aidd-data" {"spec":"x"}</p>')

    def test_folder_matches(self):
        data = {"spec": F28, "tasks_hash": H_F28}
        self.assertTrue(self._call("folderMatches", self._page({"spec": F28, "tasks_hash": H_F28}), data))
        self.assertFalse(self._call("folderMatches", self._page({"spec": F23, "tasks_hash": H_F28}), data))
        self.assertFalse(self._call("folderMatches", self._page({"spec": F28, "tasks_hash": "000000000000"}), data))
        self.assertFalse(self._call("folderMatches", self._page({"tasks_hash": H_F28}), data))
        self.assertFalse(self._call("folderMatches", "<html><body>no blob</body></html>", data))
        broken = self._page({"spec": F28, "tasks_hash": H_F28}).replace('{"spec": ', '{spec: ', 1)
        self.assertFalse(self._call("folderMatches", broken, data))
        self.assertFalse(self._call("folderMatches", None, data))
        num = {"spec": NUM, "tasks_hash": "0123456789ab"}
        self.assertTrue(self._call("folderMatches", self._page(num), num))
        self.assertFalse(self._call("folderMatches", self._page(num), {"spec": NUM, "tasks_hash": ""}))

    # ---- saveReview against stubs (aidd:FR-305, AC-308) ----
    HARNESS = r"""
const m = require(process.argv[2]);
const cfg = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
const keep = setInterval(function () {}, 1000);
const VALID = /^[A-Za-z0-9_-]{1,32}$/;
function err(name) { const e = new Error(name); e.name = name; return e; }
function mkReq() { const h = {}; return { addEventListener(n, f) { (h[n] = h[n] || []).push(f); }, fire(n) { (h[n] || []).forEach(function (f) { f(); }); } }; }
function fakeIdb(map, mode) {
  return { open() {
    if (mode === 'throw') throw err('SecurityError');
    const req = mkReq();
    if (mode === 'hang') return req;
    setTimeout(function () {
      req.result = { close() {}, createObjectStore() {}, transaction() { return { objectStore() { return {
        get(k) { const r = mkReq(); setTimeout(function () { r.result = map[k]; r.fire('success'); }, 0); return r; },
        put(v, k) { const r = mkReq(); setTimeout(function () { map[k] = v; r.fire('success'); }, 0); return r; } }; } }; } };
      req.fire('success');
    }, 0);
    return req; } };
}
function mkDir(files, opts) {
  opts = opts || {};
  const dir = { files: Object.assign({}, files), writes: 0, perm: opts.perm || 'granted',
    async queryPermission() { return dir.perm; }, async requestPermission() { return dir.perm; },
    async getFileHandle(name, o) {
      if (!(name in dir.files)) { if (!(o && o.create)) throw err('NotFoundError'); dir.files[name] = ''; }
      return { async getFile() { const t = dir.files[name]; return { size: t.length, async text() { return t; } }; },
        async createWritable() { let buf = ''; return { async write(x) { buf += x; },
          async close() { dir.writes++; dir.files[name] = opts.corrupt ? buf + 'X' : buf; }, async abort() {} }; } };
    } };
  return dir;
}
function mkWin(picker, idb) {
  const w = { calls: [], downloads: [] };
  if (picker) w.showDirectoryPicker = async function (o) {
    w.calls.push(o);
    if (o && Object.prototype.hasOwnProperty.call(o, 'id') && !VALID.test(o.id)) throw new TypeError('bad id');
    return picker(o, w.calls.length);
  };
  w.Blob = function (parts, opt) { this.parts = parts; this.type = opt && opt.type; };
  w.URL = { createObjectURL(b) { w._blob = b; return 'blob:x'; }, revokeObjectURL() {} };
  w.document = { body: { appendChild() {}, removeChild() {} }, createElement() {
    const a = { click() { w.downloads.push({ name: a.download, type: w._blob.type, text: w._blob.parts.join('') }); } };
    return a; } };
  if (idb) w.indexedDB = idb;
  return w;
}
async function run(name, w, dirs, data) {
  const status = [];
  const res = await m.saveReview(cfg.text, { data: data || cfg.data, w: w, status: function (s) { status.push(s); } });
  const out = { name: name, res: res, status: status, calls: w.calls, downloads: w.downloads, dirs: {} };
  Object.keys(dirs || {}).forEach(function (k) { const t = dirs[k].files['review.md']; out.dirs[k] = { review_md: t === undefined ? null : t, writes: dirs[k].writes }; });
  return out;
}
(async function () {
  const P = cfg.pages, results = [];
  const page = function () { return { 'review.html': P.good }; };
  let d;
  d = mkDir(page()); results.push(await run('good', mkWin(function () { return d; }), { d: d }));
  d = mkDir({}); results.push(await run('no_page', mkWin(function () { return d; }), { d: d }));
  d = mkDir({ 'review.html': P.other }); results.push(await run('other_spec', mkWin(function () { return d; }), { d: d }));
  d = mkDir({ 'review.html': P.older }); results.push(await run('older_page', mkWin(function () { return d; }), { d: d }));
  d = mkDir({ 'review.html': P.noblob }); results.push(await run('no_blob', mkWin(function () { return d; }), { d: d }));
  d = mkDir({ 'review.html': P.broken }); results.push(await run('broken_blob', mkWin(function () { return d; }), { d: d }));
  results.push(await run('abort', mkWin(function () { throw err('AbortError'); }), {}));
  results.push(await run('type_error', mkWin(function () { throw new TypeError('x'); }), {}));
  d = mkDir(page());
  results.push(await run('retry_ok', mkWin(function (o, n) { if (n === 1) throw err('SecurityError'); return d; }), { d: d }));
  results.push(await run('no_api', mkWin(null), {}));
  d = mkDir(page()); results.push(await run('idb_throws', mkWin(function () { return d; }, fakeIdb({}, 'throw')), { d: d }));
  d = mkDir(page()); results.push(await run('idb_hangs', mkWin(function () { return d; }, fakeIdb({}, 'hang')), { d: d }));
  const mem = {};
  const remembered = mkDir(page());
  mem[cfg.data.spec] = remembered;
  const unused = mkDir(page());
  results.push(await run('remembered', mkWin(function () { return unused; }, fakeIdb(mem, 'ok')), { r: remembered, u: unused }));
  const mem2 = {}, stale = mkDir({ 'review.html': P.other }), picked = mkDir(page());
  mem2[cfg.data.spec] = stale;
  const w2 = mkWin(function () { return picked; }, fakeIdb(mem2, 'ok'));
  const r2 = await run('remembered_other', w2, { s: stale, p: picked });
  r2.stored_is_picked = mem2[cfg.data.spec] === picked;
  results.push(r2);
  d = mkDir(page(), { corrupt: true }); results.push(await run('readback_mismatch', mkWin(function () { return d; }), { d: d }));
  d = mkDir({ 'review.html': P.good, 'review.md': '---\ntasks_hash: 999999999999\n---\n' });
  results.push(await run('overwrite_notice', mkWin(function () { return d; }), { d: d }));
  d = mkDir({ 'review.html': P.num });
  results.push(await run('numeric_id', mkWin(function () { return d; }), { d: d }, cfg.num));
  clearInterval(keep);
  process.stdout.write(JSON.stringify(results));
})().catch(function (e) { clearInterval(keep); process.stderr.write(String(e && e.stack || e)); process.exit(1); });
"""

    @classmethod
    def _save_results(cls):
        if getattr(cls, "_results", None) is not None:
            return cls._results
        data = {"spec": F28, "tasks_hash": H_F28, "picker_id": _picker_id(F28)}
        num = {"spec": NUM, "tasks_hash": "0123456789ab"}  # no picker_id: the fallback id
        tpl = _text(COMPACT)
        good = _fill(tpl, {"spec": F28, "tasks_hash": H_F28})
        cfg = {"data": data, "num": num, "text": GOLDEN, "pages": {
            "good": good,
            "other": _fill(tpl, {"spec": F23, "tasks_hash": "0123456789ab"}),
            "older": _fill(tpl, {"spec": F28, "tasks_hash": "000000000000"}),
            "noblob": "<!DOCTYPE html><html><body><p>no data</p></body></html>",
            "broken": good.replace('{"spec": ', '{spec: ', 1),
            "num": _fill(tpl, num)}}
        cf = cls.tmp / "save_cfg.json"
        cf.write_text(json.dumps(cfg), encoding="utf-8")
        h = cls.tmp / "save.js"
        h.write_text(cls.HARNESS, encoding="utf-8")
        r = subprocess.run([NODE, str(h), str(cls.js), str(cf)], capture_output=True, timeout=120)
        if r.returncode != 0:
            raise AssertionError(r.stderr.decode("utf-8", "replace"))
        cls._results = {x["name"]: x for x in json.loads(r.stdout.decode("utf-8"))}
        return cls._results

    def _r(self, name):
        return self._save_results()[name]

    def test_save_into_spec_folder(self):
        r = self._r("good")
        self.assertEqual(r["res"]["method"], "fs")
        self.assertTrue(r["res"]["ok"])
        self.assertEqual(r["dirs"]["d"]["review_md"], GOLDEN)
        self.assertEqual(r["calls"], [{"id": _picker_id(F28), "mode": "readwrite"}])
        self.assertEqual(r["downloads"], [])
        self.assertEqual(r["status"], [])

    def test_wrong_folder_writes_nothing(self):
        for name in ("no_page", "other_spec", "older_page", "no_blob", "broken_blob"):
            with self.subTest(case=name):
                r = self._r(name)
                self.assertEqual(r["res"]["method"], "mismatch")
                self.assertFalse(r["res"]["ok"])
                self.assertIsNone(r["dirs"]["d"]["review_md"])
                self.assertEqual(r["dirs"]["d"]["writes"], 0)
                self.assertEqual(r["downloads"], [])
                self.assertEqual(len(r["status"]), 1)
                self.assertTrue(r["status"][0].startswith("This folder belongs to "), r["status"][0])
                self.assertTrue(r["status"][0].endswith(": pick specs/%s/" % F28), r["status"][0])
        self.assertIn("This folder belongs to F23-eDoc-POS/01234567: pick specs/", self._r("other_spec")["status"][0])
        self.assertIn("This folder belongs to %s/00000000: pick specs/" % F28, self._r("older_page")["status"][0])

    def test_abort_is_silent_and_offers_download(self):
        r = self._r("abort")
        self.assertEqual(r["res"]["method"], "cancelled")
        self.assertEqual(r["status"], [])
        self.assertEqual(r["downloads"], [])
        self.assertEqual(len(r["calls"]), 1)

    def test_picker_error_retries_then_visible_line_and_download(self):
        r = self._r("type_error")
        self.assertEqual(r["calls"], [{"id": _picker_id(F28), "mode": "readwrite"}, {"mode": "readwrite"}])
        self.assertEqual(r["status"][0], "Folder picker failed (TypeError): using the download instead")
        self.assertEqual(r["res"]["method"], "download")
        self.assertEqual(r["downloads"], [{"name": "review.md", "type": "application/octet-stream", "text": GOLDEN}])
        ok = self._r("retry_ok")
        self.assertEqual(ok["res"]["method"], "fs")
        self.assertEqual(ok["calls"][1], {"mode": "readwrite"})
        self.assertEqual(ok["dirs"]["d"]["review_md"], GOLDEN)

    def test_no_api_downloads_review_md(self):
        r = self._r("no_api")
        self.assertEqual(r["res"]["method"], "download")
        self.assertEqual(r["downloads"], [{"name": "review.md", "type": "application/octet-stream", "text": GOLDEN}])
        self.assertIn("if the browser renamed it, save it over specs/%s/review.md" % F28, r["status"][0])

    def test_indexeddb_errors_never_block(self):
        for name in ("idb_throws", "idb_hangs"):
            with self.subTest(case=name):
                r = self._r(name)
                self.assertEqual(r["res"]["method"], "fs")
                self.assertEqual(r["dirs"]["d"]["review_md"], GOLDEN)

    def test_remembered_handle(self):
        r = self._r("remembered")
        self.assertEqual(r["res"]["method"], "fs")
        self.assertEqual(r["calls"], [])
        self.assertEqual(r["dirs"]["r"]["review_md"], GOLDEN)
        self.assertIsNone(r["dirs"]["u"]["review_md"])
        s = self._r("remembered_other")  # the remembered handle is re-validated, then the picker runs
        self.assertEqual(len(s["calls"]), 1)
        self.assertIsNone(s["dirs"]["s"]["review_md"])
        self.assertEqual(s["dirs"]["p"]["review_md"], GOLDEN)
        self.assertTrue(s["stored_is_picked"])

    def test_readback_mismatch_falls_back(self):
        r = self._r("readback_mismatch")
        self.assertEqual(r["res"]["method"], "download")
        self.assertIn("did not read back identical", r["status"][0])
        self.assertEqual(len(r["downloads"]), 1)

    def test_overwrite_notice(self):
        r = self._r("overwrite_notice")
        self.assertEqual(r["res"]["method"], "fs")
        self.assertIn("another tasks hash (99999999)", r["status"][0])
        self.assertEqual(r["dirs"]["d"]["review_md"], GOLDEN)

    def test_numeric_id_without_picker_id(self):
        r = self._r("numeric_id")
        self.assertEqual(r["res"]["method"], "fs")
        self.assertRegex(r["calls"][0]["id"], r"^aidd-[0-9a-f]{8}$")


class PathForms(unittest.TestCase):
    """Absolute and relative template paths resolve to the same bytes (repo-root relative)."""

    def test_relative_and_absolute(self):
        rel = Path("skill") / "templates" / "review.html"
        cwd = os.getcwd()
        try:
            os.chdir(ROOT)
            self.assertEqual(rel.read_bytes(), COMPACT.resolve().read_bytes())
            self.assertEqual((Path("skill") / "templates" / "review-full.html").read_bytes(), FULL.read_bytes())
        finally:
            os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
