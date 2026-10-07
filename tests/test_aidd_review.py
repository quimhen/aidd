"""Tests for skill/scripts/aidd_review.py, the facade of spec 008 (T-08: FR-301, FR-303, FR-304,
FR-306, FR-309, FR-312, FR-313) over the two pure modules aidd_review_items (T-01) and
aidd_review_state (T-07).

Every facade test replaces both modules with the fakes below (`mock.patch.object(aidd_review,
'_items' / '_state', return_value=fake)`): the shapes are the frozen ones of plan.md "Exact
interfaces", never the real unfinished modules. `TestRealModules` runs the real three modules
together and is skipped while the environment variable AIDD_REVIEW_FAKES_ONLY=1 is set (the
builder's in-wave run); the main agent runs it at the end of wave 1.

Every build_html/generate test uses the minimal inline TEMPLATE below; the real templates are
never read here (T-02 owns and tests them).

Run: python -m unittest tests.test_aidd_review
"""
import base64
import contextlib
import hashlib
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO / "skill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import aidd_review  # noqa: E402
import aidd_rules  # noqa: E402

FAKES_ONLY = os.environ.get("AIDD_REVIEW_FAKES_ONLY") == "1"
SCRIPT_TEXT = "\n(function(){var d=document.getElementById('aidd-data');})();\n"
TEMPLATE = (
    "<!doctype html><html><head><meta charset=\"utf-8\">"
    "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; "
    "script-src 'sha256-{{SCRIPT_SHA256}}'\">"
    "<title>{{TITLE}}</title></head>"
    "<body data-spec=\"{{SPEC_ID}}\" data-h=\"{{TASKS_HASH}}\" data-h8=\"{{TASKS_HASH8}}\" "
    "data-d=\"{{SOURCES_DIGEST}}\" data-g=\"{{GENERATED}}\">"
    "<main>{{BODY}}</main>"
    "<script type=\"application/json\" id=\"aidd-data\">{{DATA_JSON}}</script>"
    "<script id=\"aidd-js\">" + SCRIPT_TEXT + "</script></body></html>"
)
IDS = ("002-aidd-hard-rules", "F23-eDoc-POS")
# plan.md "Code grammar" literal (the facade never compiles its own: it uses _items().CODE_RE)
CODE_RE_SRC = (r"^(SUMMARY|Q\d{1,3}|D\d{1,3}(?:-?[a-z])?|V-\d{1,3}|(?:FR|AC|T)-\d{1,4}(?:-?[a-z])?|"
               r"(?:API|COMP|CTL|SCREEN)-\d{1,5}(?:-?[a-z])?)$")
SPLIT_REASON = ("aidd_review_items/aidd_review_state is not importable next to aidd_review.py "
                "(reinstall AIDD)")
INP_KEYS = {"review_bytes", "review_error", "review_mtime", "page_mtime", "page_meta", "tasks_hash",
            "digest", "oversize", "item_count", "max_items", "keys", "code_re"}
STATUS_RE = re.compile(r"^STATE=(complete|pending|stale|legacy|too_many_items) approved=\d+/\d+ "
                       r"comments=\d+ stale=(yes|no) legacy=(yes|no) tag=(\[tasks:[0-9a-f]{8}\]|none)$")

SPEC_MD = """# Spec

## Requirements
| Code | Requirement |
|---|---|
| FR-001 | Do X. |
| FR-002 | Do Y. |

## Verification
| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | `python -m unittest tests.test_x` | exit 0 | FR-001 |
"""
PLAN_MD = """# Plan

## Naming
Names.

### Interfaces
Details.

```
## not a heading
```
"""
TASKS_MD = """# Tasks

Approved: PENDING

| Task | Codes satisfied | Target file | Status |
|---|---|---|---|
| T-01 | FR-001 | a.py | |
| T-02 | FR-002 | b.py | |

## Per-task detail

### T-01
Do a.

### T-02
Do b.
"""


def _write(p, text, crlf=False):
    p.parent.mkdir(parents=True, exist_ok=True)
    data = text.replace("\n", "\r\n") if crlf else text
    p.write_bytes(data.encode("utf-8"))


def _make_spec(root, spec_id, spec=SPEC_MD, plan=PLAN_MD, tasks=TASKS_MD, crlf=False):
    d = Path(root) / "specs" / spec_id
    d.mkdir(parents=True, exist_ok=True)
    if spec is not None:
        _write(d / "spec.md", spec, crlf)
    if plan is not None:
        _write(d / "plan.md", plan, crlf)
    if tasks is not None:
        _write(d / "tasks.md", tasks, crlf)
    return d


def _th(d):
    return aidd_rules.approval_hash((Path(d) / "tasks.md").read_text(encoding="utf-8"))


def _headings_md(spec_dir, checked=True, approved=True, comments=None, tasks_hash=None, digest=None):
    """A 007 heading-grammar review.md over the --full keys."""
    keys = aidd_review.reviewable_keys(spec_dir, full=True)
    th = tasks_hash or _th(spec_dir)
    dg = digest or aidd_review.sources_digest(spec_dir)
    out = ["---", f"spec: {Path(spec_dir).name}", f"tasks_hash: {th}", f"sources_digest: {dg}",
           f"approved: {'true' if approved else 'false'}", "generated: 2026-10-05",
           "reviewed: 2026-10-05T10:00:00", "---"]
    for k in keys:
        out.append(f"## {k}")
        out.append(f"- [{'x' if checked else ' '}] Approved")
        for line in (comments or {}).get(k, "").split("\n"):
            if line:
                out.append("> " + line)
    return "\n".join(out) + "\n"


def _codes_md(spec, th, dg, lines, approved=True, reviewed="2026-10-05T10:00:00"):
    """A codes-v2 review.md: `lines` = [(code, checked, digest_or_None, comment_or_None)]."""
    out = ["---", f"spec: {spec}", f"tasks_hash: {th}", f"sources_digest: {dg}", "format: codes-v2",
           f"approved: {'true' if approved else 'false'}", "generated: 2026-10-05",
           f"reviewed: {reviewed}", "---"]
    for code, checked, d8, comment in lines:
        out.append(f"- [{'x' if checked else ' '}] {code}" + (f" @{d8}" if d8 else ""))
        for c in (comment or "").split("\n"):
            if c:
                out.append("> " + c)
    return "\n".join(out) + "\n"


def _age(path, seconds):
    t = time.time() - seconds
    os.utime(path, (t, t))


def _page_data(text):
    m = re.search(r'<script type="application/json" id="aidd-data">(.*?)</script>', text, re.S)
    return json.loads(m.group(1))


def _body(text):
    return text.split("<main>", 1)[1].split("</main>", 1)[0]


def _snapshot(d):
    out = {}
    for p in sorted(Path(d).rglob("*")):
        if p.is_file():
            out[str(p.relative_to(d))] = (p.read_bytes(), p.stat().st_mtime)
    return out


# ---------------------------------------------------------------------------
# Fakes of the two modules (documented shapes only)
# ---------------------------------------------------------------------------

_ROW_RE = re.compile(r"^\|\s*`?([A-Z]+-[^\s|`]+)`?\s*\|(.*)$", re.M)


class FakeItems:
    """aidd_review_items as plan.md documents it: extract_items(sources) -> {tabs, items, order,
    warnings}; the fake reads `| FR-nnn |` rows of spec.md and `| T-nn |` rows of tasks.md."""
    CODE_RE = re.compile(CODE_RE_SRC, re.ASCII)
    MAX_ITEMS = 2000

    def __init__(self, extra=0, warnings=None, carry=None, carry_raises=False):
        self.extra = extra
        self.warnings = list(warnings or [])
        self.carry = carry
        self.carry_raises = carry_raises
        self.calls = {"extract_items": 0, "carry_decision": [], "build_summary": [],
                      "target_files": [], "wave_count": []}

    def extract_items(self, sources):
        self.calls["extract_items"] += 1
        assert isinstance(sources, dict)
        items = {"SUMMARY": {"code": "SUMMARY", "kind": "summary", "text": "Summary of the spec",
                             "fields": {}, "edge": False, "unanswered": False, "mandatory": True,
                             "source": "spec.md#executive-summary", "canon": "summary"}}
        tabs = {"summary": ["SUMMARY"], "fr": [], "tasks": []}
        for name, tab, prefix in (("spec.md", "fr", "FR-"), ("tasks.md", "tasks", "T-")):
            for m in _ROW_RE.finditer(sources.get(name) or ""):
                code = m.group(1)
                if not code.startswith(prefix) or not self.CODE_RE.fullmatch(code) or code in items:
                    continue
                cells = [c.strip() for c in m.group(2).split("|")]
                items[code] = {"code": code, "kind": tab, "text": cells[0][:240], "fields":
                               {"target": cells[1]} if tab == "tasks" and len(cells) > 1 else {},
                               "edge": False, "unanswered": False, "mandatory": False,
                               "source": name, "canon": " | ".join(cells)}
                tabs[tab].append(code)
        for i in range(self.extra):
            code = f"AC-{i + 1}"
            items[code] = {"code": code, "kind": "ac", "text": "x", "fields": {}, "edge": False,
                           "unanswered": False, "mandatory": False, "source": "spec.md", "canon": "x"}
            tabs.setdefault("ac", []).append(code)
        labels = {"summary": "Resumen", "fr": "Requisitos", "ac": "Casos", "tasks": "Tareas"}
        tab_list = [{"id": t, "label": labels[t], "items": [items[c] for c in codes]}
                    for t, codes in tabs.items() if codes]
        order = [c for t in tab_list for c in (x["code"] for x in t["items"])]
        return {"tabs": tab_list, "items": items, "order": order, "warnings": list(self.warnings)}

    def item_digest(self, item):
        return hashlib.sha1((item["kind"] + "\x1f" + item["code"] + "\x1f" + item["canon"])
                            .encode("utf-8")).hexdigest()[:8]

    def build_summary(self, sources, extracted=None):
        self.calls["build_summary"].append(sources)
        return {"objective": "Fake objective", "scope": "", "cost": "", "risks": "",
                "open_decisions": [], "counts": {"fr": 2, "tasks": 2}, "minutes": 10,
                "tokens_k": 5, "source": "generated"}

    def carry_decision(self, prev_lines, prev_blob_digests, new_digests, order):
        self.calls["carry_decision"].append((prev_lines, prev_blob_digests, new_digests, list(order)))
        if self.carry_raises:
            raise RuntimeError("boom")
        if self.carry is not None:
            return self.carry
        prior = {c: {"approved": v["approved"], "comment": v["comment"]}
                 for c, v in prev_lines.items()
                 if c in new_digests and v.get("digest") == new_digests[c] == prev_blob_digests.get(c)}
        return prior, {"carried": len(prior), "total": len(order),
                       "pending": [c for c in order if c not in prior]}

    def target_files(self, tasks_text):
        self.calls["target_files"].append(tasks_text)
        return ["a.py", "b.py"]

    def wave_count(self, tasks_text):
        self.calls["wave_count"].append(tasks_text)
        return 1


class FakeState:
    """aidd_review_state as plan.md documents it. parse_review is a minimal two-grammar parser;
    evaluate_review records its `inp` and returns `self.result` (or a pending state)."""
    FORMAT_COMPACT = "codes-v2"
    FORMAT_FULL = "headings-v1"
    _LINE = re.compile(r"- \[( |x|X)\] (\S+)(?: @([0-9a-f]{8}))?[ \t]*", re.ASCII)

    def __init__(self, result=None, comments=(0, []), parse=None):
        self.result = result
        self.comments = comments
        self.parse = parse
        self.inputs = []
        self.parse_calls = []
        self.summary_args = []

    def parse_review(self, text, code_re):
        self.parse_calls.append((text, code_re))
        if self.parse is not None:
            return self.parse
        res = {"ok": False, "errors": [], "warnings": [], "meta": {}, "format": None,
               "sections": {}, "digests": {}}
        lines = str(text).replace("\r\n", "\n").split("\n")
        if not lines or lines[0] != "---" or "---" not in lines[1:]:
            res["errors"].append("front matter")
            return res
        end = lines.index("---", 1)
        meta = {}
        for ln in lines[1:end]:
            k, _s, v = ln.partition(":")
            meta[k.strip()] = v.strip()
        meta["approved"] = meta.get("approved") == "true"
        fmt = meta.get("format", "headings-v1")
        res.update(meta=meta, format=fmt)
        cur = None
        for ln in lines[end + 1:]:
            m = self._LINE.fullmatch(ln)
            if fmt == "codes-v2" and m and code_re.fullmatch(m.group(2)):
                cur = m.group(2)
                res["sections"][cur] = {"approved": m.group(1) != " ", "comment": ""}
                if m.group(3):
                    res["digests"][cur] = m.group(3)
            elif fmt == "headings-v1" and ln.startswith("## "):
                cur = ln[3:].strip()
                res["sections"][cur] = {"approved": False, "comment": ""}
            elif fmt == "headings-v1" and cur and ln.strip() in ("- [x] Approved", "- [X] Approved"):
                res["sections"][cur]["approved"] = True
            elif cur and ln.startswith("> "):
                c = res["sections"][cur]["comment"]
                res["sections"][cur]["comment"] = (c + "\n" if c else "") + ln[2:]
        res["ok"] = fmt in ("codes-v2", "headings-v1")
        return res

    def evaluate_review(self, inp):
        self.inputs.append(inp)
        if self.result is not None:
            return dict(self.result)
        return dict(aidd_review._blank_state("fake"), item_count=inp.get("item_count", 0))

    def derive_approval(self, rs, tag):
        state = rs.get("_state", "pending")
        return {"state": state, "approved": rs.get("_a", 0), "total": rs.get("item_count", 0),
                "comments": len(rs.get("comments") or []), "stale": bool(rs.get("_stale")),
                "legacy": state == "legacy", "tag": tag}

    def status_line(self, st):
        return (f"STATE={st['state']} approved={st['approved']}/{st['total']} comments={st['comments']} "
                f"stale={'yes' if st['stale'] else 'no'} legacy={'yes' if st['legacy'] else 'no'} "
                f"tag={st['tag'] or 'none'}")

    def exit_for(self, state):
        return {"complete": 0, "pending": 2, "stale": 3, "legacy": 3, "too_many_items": 3}.get(state, 3)

    def comment_lines(self, rs):
        return self.comments

    def summary_lines(self, summary, files, waves):
        self.summary_args.append((summary, files, waves))
        return [f"Objective: {summary.get('objective')}", f"Changes by component/file: {', '.join(files)}",
                f"Tasks/waves: 2 tasks, {waves} waves"]


class _Tmp(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()


class _Faked(_Tmp):
    """Both modules replaced by fakes for the whole test."""

    def setUp(self):
        super().setUp()
        self.items = FakeItems()
        self.state = FakeState()
        self._p1 = mock.patch.object(aidd_review, "_items", side_effect=lambda: self.items)
        self._p2 = mock.patch.object(aidd_review, "_state", side_effect=lambda: self.state)
        self._p1.start()
        self._p2.start()

    def tearDown(self):
        self._p2.stop()
        self._p1.stop()
        super().tearDown()


# ---------------------------------------------------------------------------
# 007 heading machinery, behind full=True (aidd:FR-303 --full, AC-311)
# ---------------------------------------------------------------------------

class TestSlugsAndHeadings(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(aidd_review.slugify("T-07 API endpoints"), "t-07-api-endpoints")
        self.assertEqual(aidd_review.slugify("Configuración Ñandú"), "configuracion-nandu")
        self.assertEqual(aidd_review.slugify("  ¿¡!!  "), "section")

    def test_duplicates_and_fences(self):
        md = "# T\n## A\n## A\n### A\n```\n## Fenced\n```\n~~~\n## Tilde\n~~~\n#### Four\n##### Five\n"
        hs = aidd_review.parse_headings(md, "plan.md")
        self.assertEqual([h[0] for h in hs], ["plan/t", "plan/a", "plan/a-2", "plan/a-3", "plan/four"])
        self.assertEqual([h[1] for h in hs], [1, 2, 2, 3, 4])

    def test_crlf_and_closing_hashes(self):
        hs = aidd_review.parse_headings("## Title ##\r\n## Otro título\r\n", "spec.md")
        self.assertEqual([h[0] for h in hs], ["spec/title", "spec/otro-titulo"])

    def test_full_keys_levels_2_3_only_and_no_module_needed(self):
        with tempfile.TemporaryDirectory() as td:
            d = _make_spec(td, IDS[1])
            with mock.patch.object(aidd_review, "_items", side_effect=ImportError("x")):
                keys = aidd_review.reviewable_keys(d, full=True)
            self.assertIn("spec/verification", keys)
            self.assertIn("plan/interfaces", keys)
            self.assertIn("tasks/t-01", keys)
            self.assertNotIn("spec/spec", keys)
            self.assertNotIn("plan/not-a-heading", keys)


class TestSafeUrl(unittest.TestCase):
    BAD = [
        "javascript:alert(1)", "java\tscript:alert(1)", "java\rscript:x", "java\nscript:x",
        "\x01javascript:alert(1)", " javascript:alert(1)", "\x7fjavascript:x", "java\x7fscript:x",
        "JaVaScRiPt:alert(1)", "&#106;avascript:alert(1)", "&colon;x", "/\\evil.example/",
        "\\\\host\\share\\a.png", "//evil.example/a", "/abs/path", "../../x", "%2e%2e/x",
        "%252e%252e/x", "a/../b", "data:text/html,x", "vbscript:x", "file:///c:/x", "",
        "mailto:a@b.c", "a b",
    ]

    def test_rejected(self):
        for u in self.BAD:
            self.assertIsNone(aidd_review.safe_url(u), repr(u))

    def test_accepted(self):
        for u in ("https://ok.example/x", "HTTP://ok.example", "notes.md", "img/a.png", "a.md#sec",
                  "x?y=1&z=2", "./a.md"):
            self.assertEqual(aidd_review.safe_url(u), u, u)

    def test_images_never_take_a_scheme(self):
        self.assertIsNone(aidd_review.safe_url("https://evil.example/a.png", image=True))
        self.assertEqual(aidd_review.safe_url("img/a.png", image=True), "img/a.png")


XSS_SPEC = """# Spec

## Hostile "quoted" --> heading
<script>alert(1)</script>
[a](javascript:alert(1))
[b](java\tscript:alert(1))
[e](&#106;avascript:alert(1))
[h](//evil.example/a)
![i](data:text/html,x)
![j](https://evil.example/a.png)
[k](../../x)
[ok](https://ok.example/x)
<img src=x onerror=alert(1)>
<p style="color:red">styled</p>
Inline `a*b|c*d` code and **bold** and *em*.

| Col | Other |
|---|---|
| `x | y` | *z* |

- [ ] open item
- [x] done item
  - nested

> quoted <b>x</b>

```html
</script><script>alert(2)</script>
```

## Verification
| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | `python -m unittest tests.test_x` | exit 0 | FR-1 |
"""


class TestFullPage(_Tmp):
    """The 007 long page, now only behind full=True; it needs neither review module to render."""

    def _page(self, spec=XSS_SPEC):
        d = _make_spec(self.root, IDS[1], spec=spec)
        with mock.patch.object(aidd_review, "_items", side_effect=ImportError("x")):
            return d, aidd_review.build_html(d, template_text=TEMPLATE, full=True)

    def test_xss_list_is_inert(self):
        _d, page = self._page()
        body = _body(page)
        self.assertNotIn("<script", body.lower())
        self.assertEqual(page.lower().count("<script"), 2)
        for t in re.findall(r"<[a-z][^>]*>", page.lower()):
            self.assertNotRegex(t, r"\son\w+\s*=", t)
            self.assertNotRegex(t, r"\sstyle\s*=", t)
        urls = re.findall(r'(?:href|src)="([^"]*)"', body)
        for u in urls:
            dec = html.unescape(html.unescape(u)).lower()
            self.assertNotIn("javascript:", dec)
            self.assertNotIn("data:", dec)
            self.assertNotIn("..", dec)
        self.assertEqual([u for u in urls if ":" in u], ["https://ok.example/x"])
        self.assertNotIn("<img", body)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", body)
        self.assertIn("Hostile &quot;quoted&quot; --&gt; heading", body)

    def test_inline_code_table_lists_quote(self):
        _d, page = self._page()
        body = _body(page)
        self.assertIn("<code>a*b|c*d</code>", body)
        self.assertIn("<td><code>x | y</code></td><td><em>z</em></td>", body)
        self.assertIn('<input type="checkbox" disabled checked> done item', body)
        self.assertIn("<blockquote><p>quoted &lt;b&gt;x&lt;/b&gt;</p></blockquote>", body)

    def test_mandatory_verification_and_heading_keys(self):
        d, page = self._page()
        data = _page_data(page)
        self.assertEqual(data["format"], "headings-v1")
        self.assertEqual([k["key"] for k in data["keys"] if k["mandatory"]], ["spec/verification"])
        keys = aidd_review.reviewable_keys(d, full=True)
        for k in keys:
            self.assertEqual(page.count(f'data-key="{k}"'), 1, k)
        self.assertEqual(data["picker_id"], "aidd-" + hashlib.sha1(IDS[1].encode()).hexdigest()[:8])

    def test_csp_hash_and_tokens(self):
        d, page = self._page(spec="# S\n\n## Tokens\nliteral {{SPEC_ID}} and {{BODY}}\n")
        want = base64.b64encode(hashlib.sha256(SCRIPT_TEXT.encode("utf-8")).digest()).decode()
        self.assertIn(f"script-src 'sha256-{want}'", page)
        self.assertIn("literal {{SPEC_ID}} and {{BODY}}", page)
        blob = re.search(r'id="aidd-data">(.*?)</script>', page, re.S).group(1)
        self.assertFalse(set("<>&") & set(blob))
        self.assertEqual(json.loads(blob)["tasks_hash"], _th(d))

    def test_template_script_must_be_constant(self):
        d = _make_spec(self.root, IDS[0])
        bad = TEMPLATE.replace(SCRIPT_TEXT, "var x='{{SPEC_ID}}';")
        with self.assertRaises(ValueError):
            aidd_review.build_html(d, template_text=bad, full=True)
        with self.assertRaises(ValueError):
            aidd_review.build_html(d, template_text="<html>{{BODY}}</html>", full=True)

    def test_absent_sources_listed(self):
        _d, page = self._page()
        self.assertIn("mockup-audit.md: absent", page)


class TestGenerateFull(_Faked):
    def test_both_ids_absolute_relative_and_idempotent(self):
        for sid in IDS:
            d = _make_spec(self.root, sid)
            path, wrote = aidd_review.generate(d, template_text=TEMPLATE, full=True)
            self.assertTrue(wrote)
            self.assertEqual(path, d.resolve() / "review.html")
            self.assertEqual(aidd_review._page_meta(path),
                             (_th(d), aidd_review.sources_digest(d), "headings-v1"))
        cwd = os.getcwd()
        try:
            os.chdir(self.root)
            for sid in IDS:
                path, wrote = aidd_review.generate(f"specs/{sid}", template_text=TEMPLATE, full=True)
                self.assertFalse(wrote)
                self.assertTrue(path.is_absolute())
        finally:
            os.chdir(cwd)

    def test_prior_prefilled_only_from_matching_headings_review(self):
        d = _make_spec(self.root, IDS[1])
        path, _ = aidd_review.generate(d, template_text=TEMPLATE, full=True)
        (d / "review.md").write_text(_headings_md(d, comments={"tasks/t-01": "looks fine"}), encoding="utf-8")
        path.unlink()
        aidd_review.generate(d, template_text=TEMPLATE, full=True)
        data = _page_data(path.read_text(encoding="utf-8"))
        self.assertTrue(data["prior_approved"])
        self.assertEqual(data["prior"]["tasks/t-01"], {"approved": True, "comment": "looks fine"})
        (d / "review.md").write_text(_headings_md(d, tasks_hash="0" * 12), encoding="utf-8")
        path.unlink()
        aidd_review.generate(d, template_text=TEMPLATE, full=True)
        self.assertEqual(_page_data(path.read_text(encoding="utf-8"))["prior"], {})

    def test_switching_mode_regenerates(self):
        d = _make_spec(self.root, IDS[0])
        _p, wrote = aidd_review.generate(d, template_text=TEMPLATE, full=True)
        self.assertTrue(wrote)
        _p, wrote = aidd_review.generate(d, template_text=TEMPLATE)
        self.assertTrue(wrote)
        self.assertEqual(aidd_review._page_meta(_p)[2], "codes-v2")
        _p, wrote = aidd_review.generate(d, template_text=TEMPLATE)
        self.assertFalse(wrote)
        _p, wrote = aidd_review.generate(d, template_text=TEMPLATE, full=True)
        self.assertTrue(wrote)

    def test_refusals_nothing_written(self):
        d = _make_spec(self.root, IDS[1], tasks=None)
        with self.assertRaises(ValueError) as cm:
            aidd_review.generate(d, template_text=TEMPLATE)
        self.assertIn("tasks.md", str(cm.exception))
        self.assertFalse((d / "review.html").exists())
        for name in ("tasks.md", "plan.md"):
            d = _make_spec(self.root / name.replace(".", "_"), IDS[0])
            (d / name).write_text(TASKS_MD + "x" * 450_000 if name == "tasks.md" else "x" * 450_000,
                                  encoding="utf-8")
            for full in (False, True):
                with self.assertRaises(ValueError) as cm:
                    aidd_review.generate(d, template_text=TEMPLATE, full=full)
                self.assertIn(name, str(cm.exception))
                self.assertIn("limit 400000", str(cm.exception))
            self.assertFalse((d / "review.html").exists())
            self.assertEqual(list(d.glob("*.tmp")), [])
            self.assertEqual(list(d.glob(".*.tmp")), [])


# ---------------------------------------------------------------------------
# Compact page (aidd:FR-301, FR-303, FR-312) with fakes
# ---------------------------------------------------------------------------

class TestCompactPage(_Faked):
    def test_blob_fields_both_ids(self):
        for sid in IDS:
            d = _make_spec(self.root, sid)
            path, wrote = aidd_review.generate(d, template_text=TEMPLATE)
            self.assertTrue(wrote)
            data = _page_data(path.read_text(encoding="utf-8"))
            self.assertEqual(data["format"], "codes-v2")
            self.assertEqual(data["picker_id"], "aidd-" + hashlib.sha1(sid.encode("utf-8")).hexdigest()[:8])
            self.assertRegex(data["picker_id"], r"^[A-Za-z0-9_-]{1,32}$")
            order = self.items.extract_items(dict(aidd_review._load_sources(d)))["order"]
            self.assertEqual(data["codes"], order)
            self.assertEqual(order[0], "SUMMARY")
            self.assertEqual(data["codes"], aidd_review.reviewable_keys(d))
            ex = self.items.extract_items(dict(aidd_review._load_sources(d)))
            self.assertEqual(data["digests"], {c: self.items.item_digest(ex["items"][c]) for c in order})
            self.assertEqual(data["summary"]["objective"], "Fake objective")
            self.assertEqual(data["tasks_hash"], _th(d))
            self.assertEqual(data["tasks_hash8"], _th(d)[:8])
            self.assertEqual(data["prior"], {})
            self.assertEqual(data["carry"], {"carried": 0, "total": len(order), "pending": order})
            self.assertEqual([t["id"] for t in data["tabs"]], ["summary", "fr", "tasks"])
            self.assertNotIn("canon", json.dumps(data))
            self.assertEqual(data["links"], {"summary": "spec.md", "fr": "spec.md", "tasks": "tasks.md"})

    def test_markup_tabs_items_and_warnings(self):
        self.items.warnings = [{"tab": "fr", "text": "FR: 1 coded row skipped: FR-4.1"},
                               {"tab": "ac", "text": "29 rows without a code are not reviewable: <b>x</b>"},
                               {"tab": "", "text": "general"}]
        d = _make_spec(self.root, IDS[1])
        page = aidd_review.build_html(d, template_text=TEMPLATE)
        body = _body(page)
        panels = re.findall(r'<section role="tabpanel" id="tab-([a-z]+)" data-tab="\1"', body)
        self.assertEqual(panels, ["summary", "fr", "tasks"])
        fr = body.split('id="tab-fr"', 1)[1].split("</section>", 1)[0]
        self.assertIn('<ul class="aidd-warn" role="status"><li>FR: 1 coded row skipped: FR-4.1</li></ul>', fr)
        summ = body.split('id="tab-summary"', 1)[1].split("</section>", 1)[0]
        self.assertIn("29 rows without a code are not reviewable: &lt;b&gt;x&lt;/b&gt;", summ)
        self.assertIn("<li>general</li>", summ)
        self.assertIn("3 warning(s) in total", summ)
        self.assertIn('<div class="aidd-item" data-code="SUMMARY" data-mandatory="1">', summ)
        self.assertIn('<div class="aidd-item" data-code="FR-001">', fr)
        self.assertEqual(len(_page_data(page)["warnings"]), 3)

    def test_html_safety(self):
        spec = SPEC_MD.replace("| FR-002 | Do Y. |",
                               "| FR-002 | <script>alert(1)</script> {{SCRIPT_SHA256}} {{BODY}} |\n"
                               "| FR-301\"><img src=x onerror=1> | hostile cell |")
        d = _make_spec(self.root, IDS[0], spec=spec)
        page = aidd_review.build_html(d, template_text=TEMPLATE)
        body = _body(page)
        self.assertNotIn("<script", body.lower())
        self.assertNotIn("<img", body.lower())
        self.assertEqual(page.lower().count("<script"), 2)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt; {{SCRIPT_SHA256}} {{BODY}}", body)
        want = base64.b64encode(hashlib.sha256(SCRIPT_TEXT.encode("utf-8")).digest()).decode()
        self.assertIn(f"script-src 'sha256-{want}'", page)
        self.assertEqual(page.count(f"'sha256-{want}'"), 1)
        data = _page_data(page)
        self.assertFalse(any("img" in c for c in data["codes"]))
        blob = re.search(r'id="aidd-data">(.*?)</script>', page, re.S).group(1)
        self.assertFalse(set("<>&") & set(blob))
        for tag in re.findall(r"<[a-z][^>]*>", body.lower()):
            self.assertNotRegex(tag, r"\son\w+\s*=", tag)
            self.assertNotRegex(tag, r"\sstyle\s*=", tag)
        hrefs = re.findall(r'href="([^"]*)"', body)
        self.assertTrue(hrefs)
        self.assertTrue(set(hrefs) <= set(aidd_review.SOURCES), hrefs)

    def test_over_cap_refused_nothing_written(self):
        d = _make_spec(self.root, IDS[1])
        self.items.extra = 2001
        n = len(self.items.extract_items(dict(aidd_review._load_sources(d)))["order"])
        want = f"too many items ({n} > 2000): split the spec or run aidd review <spec> --full"
        with self.assertRaises(ValueError) as cm:
            aidd_review.generate(d, template_text=TEMPLATE)
        self.assertEqual(str(cm.exception), want)
        self.assertFalse((d / "review.html").exists())
        self.items.extra = 0
        page, _ = aidd_review.generate(d, template_text=TEMPLATE)
        before = page.read_bytes()
        (d / "plan.md").write_text(PLAN_MD + "\nchanged\n", encoding="utf-8")
        self.items.extra = 2001
        with self.assertRaises(ValueError) as cm:
            aidd_review.generate(d, template_text=TEMPLATE)
        self.assertTrue(str(cm.exception).startswith("too many items ("))
        self.assertEqual(page.read_bytes(), before)
        self.assertEqual(list(d.glob(".*.tmp")), [])
        # --full is never capped
        _p, wrote = aidd_review.generate(d, template_text=TEMPLATE, full=True)
        self.assertTrue(wrote)

    def test_idempotence_digest_hash_format(self):
        d = _make_spec(self.root, IDS[1])
        path, _ = aidd_review.generate(d, template_text=TEMPLATE)
        _age(path, 100)
        before = path.stat().st_mtime
        _p, wrote = aidd_review.generate(d, template_text=TEMPLATE)
        self.assertFalse(wrote)
        self.assertEqual(path.stat().st_mtime, before)
        # neutral tasks.md edits (Status cell, Approved line) keep the page
        t = (d / "tasks.md").read_text(encoding="utf-8")
        t = t.replace("| T-01 | FR-001 | a.py | |", "| T-01 | FR-001 | a.py | done |")
        t = t.replace("Approved: PENDING", "Approved: 2026-10-05 hash:0123456789ab")
        (d / "tasks.md").write_text(t, encoding="utf-8")
        self.assertFalse(aidd_review.generate(d, template_text=TEMPLATE)[1])
        # a 007 page (blob without format) is regenerated by the compact mode
        text = path.read_text(encoding="utf-8")
        data = _page_data(text)
        del data["format"]
        path.write_text(text.replace(re.search(r'id="aidd-data">(.*?)</script>', text, re.S).group(1),
                                     json.dumps(data)), encoding="utf-8")
        self.assertEqual(aidd_review._page_meta(path)[2], "headings-v1")
        self.assertTrue(aidd_review.generate(d, template_text=TEMPLATE)[1])

    def test_import_error_fails_closed(self):
        d = _make_spec(self.root, IDS[0])
        with mock.patch.object(aidd_review, "_items", side_effect=ImportError("no module")):
            with self.assertRaises(ImportError):
                aidd_review.generate(d, template_text=TEMPLATE)
            self.assertFalse((d / "review.html").exists())
            r = aidd_review.parse_review("---\n---\n")
            self.assertFalse(r["ok"])
            self.assertEqual(r["errors"], [SPLIT_REASON])
            self.assertEqual(r["digests"], {})


class TestCarryOver(_Faked):
    def _first(self, sid=IDS[1]):
        d = _make_spec(self.root, sid)
        path, _ = aidd_review.generate(d, template_text=TEMPLATE)
        return d, path, _page_data(path.read_text(encoding="utf-8"))

    def test_computed_before_overwrite_and_review_md_untouched(self):
        for sid in IDS:
            d, path, data = self._first(sid)
            old_digests = data["digests"]
            lines = [(c, True, old_digests[c], "ok" if c == "FR-001" else None) for c in data["codes"]]
            md = d / "review.md"
            md.write_text(_codes_md(sid, data["tasks_hash"], data["sources_digest"], lines), encoding="utf-8")
            _age(md, 30)
            sha_before = hashlib.sha1(md.read_bytes()).hexdigest()
            mtime_before = md.stat().st_mtime
            (d / "spec.md").write_text(SPEC_MD.replace("Do Y.", "Do Y differently."), encoding="utf-8")
            self.items.calls["carry_decision"].clear()
            aidd_review.generate(d, template_text=TEMPLATE)
            prev_lines, prev_blob, new_digests, order = self.items.calls["carry_decision"][-1]
            self.assertEqual(prev_blob, old_digests)                     # the OLD page blob
            self.assertNotEqual(new_digests["FR-002"], old_digests["FR-002"])
            self.assertEqual(prev_lines["FR-001"], {"approved": True, "comment": "ok",
                                                    "digest": old_digests["FR-001"]})
            self.assertEqual(set(prev_lines), set(data["codes"]))
            new = _page_data(path.read_text(encoding="utf-8"))
            self.assertEqual(new["carry"]["pending"], ["FR-002"])
            self.assertEqual(new["prior"]["FR-001"], {"approved": True, "comment": "ok"})
            self.assertNotIn("FR-002", new["prior"])
            self.assertEqual(hashlib.sha1(md.read_bytes()).hexdigest(), sha_before)
            self.assertEqual(md.stat().st_mtime, mtime_before)

    def test_merge_step_line_without_digest(self):
        d, _path, data = self._first()
        lines = [(c, True, None if c == "T-01" else data["digests"][c], None) for c in data["codes"]]
        (d / "review.md").write_text(_codes_md(d.name, data["tasks_hash"], data["sources_digest"], lines),
                                     encoding="utf-8")
        self.items.calls["carry_decision"].clear()
        prior, carry = aidd_review._carry_over(d, data["codes"], data["digests"])
        prev_lines = self.items.calls["carry_decision"][-1][0]
        self.assertEqual(prev_lines["T-01"], {"approved": True, "comment": "", "digest": None})
        for v in prev_lines.values():
            self.assertEqual(set(v), {"approved", "comment", "digest"})
        self.assertNotIn("T-01", prior)
        self.assertIn("T-01", carry["pending"])

    def test_headings_invalid_or_other_spec_give_empty_map(self):
        d, _path, data = self._first()
        good = [(c, True, data["digests"][c], None) for c in data["codes"]]
        cases = [
            _headings_md(d),
            "garbage\n",
            _codes_md("F28-DB-Unification-Sync", data["tasks_hash"], data["sources_digest"], good),
        ]
        for text in cases:
            (d / "review.md").write_text(text, encoding="utf-8")
            self.items.calls["carry_decision"].clear()
            prior, carry = aidd_review._carry_over(d, data["codes"], data["digests"])
            self.assertEqual(self.items.calls["carry_decision"][-1][0], {})
            self.assertEqual(prior, {})
            self.assertEqual(carry["carried"], 0)

    def test_errors_mean_no_carry(self):
        d, path, data = self._first()
        self.items.carry_raises = True
        prior, carry = aidd_review._carry_over(d, data["codes"], data["digests"])
        self.assertEqual((prior, carry), ({}, {"carried": 0, "total": len(data["codes"]),
                                               "pending": data["codes"]}))
        self.items.carry_raises = False
        self.items.carry = "not a tuple"
        self.assertEqual(aidd_review._carry_over(d, data["codes"], data["digests"])[0], {})
        self.items.carry = None
        path.write_text("<html>no blob</html>", encoding="utf-8")
        aidd_review._carry_over(d, data["codes"], data["digests"])
        self.assertEqual(self.items.calls["carry_decision"][-1][1], {})

    def test_explicit_prior_still_wins(self):
        d = _make_spec(self.root, IDS[0])
        page = aidd_review.build_html(d, template_text=TEMPLATE,
                                      prior={"sections": {"FR-001": {"approved": True, "comment": "c"},
                                                          "NOPE-1": {"approved": True}}})
        data = _page_data(page)
        self.assertEqual(data["prior"], {"FR-001": {"approved": True, "comment": "c"}})
        self.assertEqual(data["carry"]["carried"], 1)
        self.assertEqual(self.items.calls["carry_decision"], [])


# ---------------------------------------------------------------------------
# review_state IO half (aidd:FR-304) with fakes
# ---------------------------------------------------------------------------

class TestReviewStateIO(_Faked):
    def test_inp_contract_keys_no_page_both_ids(self):
        for sid in IDS:
            d = _make_spec(self.root, sid)
            self.state.inputs.clear()
            aidd_review.review_state(d)
            inp = self.state.inputs[-1]
            self.assertEqual(set(inp), INP_KEYS)
            self.assertIsNone(inp["page_mtime"])
            self.assertEqual(inp["page_meta"], (None, None, None))
            order = self.items.extract_items(dict(aidd_review._load_sources(d)))["order"]
            self.assertEqual(inp["item_count"], len(order))          # computed with no page
            self.assertEqual(inp["keys"], order)
            self.assertIsNone(inp["review_bytes"])
            self.assertEqual(inp["review_error"], "")
            self.assertEqual(inp["review_mtime"], 0.0)
            self.assertEqual(inp["tasks_hash"], _th(d))
            self.assertEqual(inp["digest"], aidd_review.sources_digest(d))
            self.assertIsNone(inp["oversize"])
            self.assertEqual(inp["max_items"], 2000)
            self.assertIs(inp["code_re"], FakeItems.CODE_RE)

    def test_inp_compact_and_full_page(self):
        d = _make_spec(self.root, IDS[1])
        aidd_review.generate(d, template_text=TEMPLATE)
        (d / "review.md").write_bytes(b"---\nspec: x\n---\n")
        aidd_review.review_state(d)
        inp = self.state.inputs[-1]
        self.assertEqual(inp["page_meta"], (_th(d), aidd_review.sources_digest(d), "codes-v2"))
        self.assertIsInstance(inp["page_mtime"], float)
        self.assertEqual(inp["review_bytes"], b"---\nspec: x\n---\n")
        self.assertGreater(inp["review_mtime"], 0.0)
        self.assertEqual(inp["keys"][0], "SUMMARY")
        aidd_review.generate(d, template_text=TEMPLATE, full=True)
        n = self.items.calls["extract_items"]
        aidd_review.review_state(f"{d}")
        inp = self.state.inputs[-1]
        self.assertEqual(inp["page_meta"][2], "headings-v1")
        self.assertEqual(inp["keys"], aidd_review.reviewable_keys(d, full=True))
        self.assertEqual(inp["item_count"], len(inp["keys"]))
        self.assertEqual(self.items.calls["extract_items"], n)       # no extraction for --full

    def test_relative_path_and_oversize(self):
        d = _make_spec(self.root, IDS[0])
        (d / "plan.md").write_text("x" * 450_000, encoding="utf-8")
        cwd = os.getcwd()
        try:
            os.chdir(self.root)
            aidd_review.review_state(f"specs/{IDS[0]}")
        finally:
            os.chdir(cwd)
        inp = self.state.inputs[-1]
        self.assertEqual(inp["oversize"], "plan.md")
        self.assertEqual((inp["item_count"], inp["keys"]), (0, []))

    def test_result_passthrough_and_never_raises(self):
        d = _make_spec(self.root, IDS[1])
        self.state.result = {"complete": True, "reason": "", "x": 1}
        self.assertEqual(aidd_review.review_state(d), {"complete": True, "reason": "", "x": 1})
        self.state.result = None
        with mock.patch.object(self.state, "evaluate_review", side_effect=RuntimeError("boom")):
            st = aidd_review.review_state(d)
        self.assertFalse(st["complete"])
        self.assertIn("review state unavailable", st["reason"])
        for k in ("legacy", "item_count", "format", "page_format", "page_current", "missing"):
            self.assertIn(k, st)

    def test_import_error_reason(self):
        d = _make_spec(self.root, IDS[0])
        for target in ("_items", "_state"):
            with mock.patch.object(aidd_review, target, side_effect=ImportError("gone")):
                st = aidd_review.review_state(d)
            self.assertEqual(st["reason"], SPLIT_REASON)
            self.assertFalse(st["complete"])

    def test_page_meta_three_tuple(self):
        d = _make_spec(self.root, IDS[0])
        p = d / "review.html"
        self.assertEqual(aidd_review._page_meta(p), (None, None, None))
        p.write_text("<html></html>", encoding="utf-8")
        self.assertEqual(aidd_review._page_meta(p), (None, None, None))
        p.write_text('<script type="application/json" id="aidd-data">{bad</script>', encoding="utf-8")
        self.assertEqual(aidd_review._page_meta(p), (None, None, None))
        p.write_text('<script type="application/json" id="aidd-data">'
                     '{"tasks_hash":"a","sources_digest":"b"}</script>', encoding="utf-8")
        self.assertEqual(aidd_review._page_meta(p), ("a", "b", "headings-v1"))
        p.write_text('<script type="application/json" id="aidd-data">[1]</script>', encoding="utf-8")
        self.assertEqual(aidd_review._page_meta(p), (None, None, None))

    def test_content_only_module(self):
        names = [n for n in dir(aidd_review) if callable(getattr(aidd_review, n))
                 and re.search(r"mint|append|activate", n, re.I)]
        self.assertEqual(names, [])
        src = (SCRIPTS_DIR / "aidd_review.py").read_text(encoding="utf-8")
        self.assertNotIn("aidd_evidence", src)
        self.assertNotIn("Approved: ", src)
        self.assertFalse(hasattr(aidd_review, "_print_state"))
        self.assertFalse(hasattr(aidd_review, "_check_exit"))
        self.assertFalse(hasattr(aidd_review, "MAX_REVIEW_MD_BYTES"))
        # the two modules are never imported at module import time
        self.assertNotRegex(src, r"(?m)^import aidd_review_(items|state)")
        self.assertNotRegex(src, r"(?m)^from aidd_review_(items|state)")


# ---------------------------------------------------------------------------
# Approval state wrappers and summary (aidd:FR-309, FR-313)
# ---------------------------------------------------------------------------

class TestWrappers(_Faked):
    def test_approval_state_tag_and_never_raises(self):
        for sid in IDS:
            d = _make_spec(self.root, sid)
            st = aidd_review.approval_state(d)
            self.assertEqual(st["tag"], f"[tasks:{_th(d)[:8]}]")
            self.assertEqual(aidd_review._approval_tag(d), f"[tasks:{_th(d)[:8]}]")
        d = _make_spec(self.root / "nt", IDS[0], tasks=None)
        self.assertIsNone(aidd_review._approval_tag(d))
        with mock.patch.object(self.state, "derive_approval", side_effect=RuntimeError("x")):
            st = aidd_review.approval_state(d)
        self.assertEqual(st["state"], "stale")
        self.assertTrue(st["stale"])

    def test_review_comments(self):
        d = _make_spec(self.root, IDS[1])
        self.state.comments = (0, ["FR-001: a / b"])
        self.assertEqual(aidd_review.review_comments(d), (0, ["FR-001: a / b"]))
        with mock.patch.object(self.state, "comment_lines", side_effect=RuntimeError("x")):
            self.assertEqual(aidd_review.review_comments(d), (3, []))

    def test_summary_lines_wiring_writes_nothing(self):
        d = _make_spec(self.root, IDS[0])
        before = _snapshot(d)
        lines = aidd_review.summary_lines(d)
        self.assertEqual(lines[0], "Objective: Fake objective")
        summary, files, waves = self.state.summary_args[-1]
        self.assertEqual((files, waves), (["a.py", "b.py"], 1))
        self.assertEqual(self.items.calls["target_files"][-1], TASKS_MD)
        self.assertEqual(self.items.calls["wave_count"][-1], TASKS_MD)
        self.assertEqual(_snapshot(d), before)


# ---------------------------------------------------------------------------
# --wait (aidd:FR-306, AC-309) with an injected clock and sleeper
# ---------------------------------------------------------------------------

def _rs(state, page_current=True, reason="", a=0, n=175, stale=False):
    return {"_state": state, "page_current": page_current, "reason": reason, "_a": a,
            "item_count": n, "_stale": stale, "comments": []}


class TestWait(_Faked):
    TAG = "[tasks:5c3cbb5b]"

    def _wait(self, seq, timeout=10.0, tag=TAG):
        seq = list(seq)
        calls = {"n": 0}

        def fake_state(_d):
            calls["n"] += 1
            return seq[min(calls["n"] - 1, len(seq) - 1)]
        t = {"now": 0.0}
        out, sleeps = [], []

        def sleep(s):
            sleeps.append(s)
            t["now"] += s
        d = _make_spec(self.root, "F28-DB-Unification-Sync")
        (d / "review (1).md").write_text("stray", encoding="utf-8")
        before = _snapshot(d)
        with mock.patch.object(aidd_review, "review_state", side_effect=fake_state), \
                mock.patch.object(aidd_review, "_approval_tag", return_value=tag):
            code = aidd_review.review_wait(d, timeout=timeout, interval=2.0, out=out.append,
                                           sleep=sleep, clock=lambda: t["now"])
        self.assertEqual(_snapshot(d), before)                    # never writes a file
        return code, out, sleeps

    def test_a_b_c_keep_polling_then_complete(self):
        seq = [_rs("pending", a=0),                     # (a) no review.md
               _rs("legacy"),                           # (b) legacy review.md
               _rs("pending", a=174),                   # (c) one unchecked code
               _rs("stale", stale=True),                # (e) older tasks_hash, page current
               _rs("complete", a=175)]                  # (d)
        code, out, sleeps = self._wait(seq)
        self.assertEqual(code, 0)
        self.assertEqual(out, [f"STATE=complete approved=175/175 comments=0 stale=no legacy=no tag={self.TAG}"])
        self.assertEqual(len(sleeps), 4)

    def test_timeout_prints_last_state_only(self):
        code, out, sleeps = self._wait([_rs("pending", a=174)], timeout=6.0)
        self.assertEqual(code, 2)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith("STATE=pending approved=174/175 "))
        self.assertEqual(len(sleeps), 3)

    def test_cannot_help_exit_3(self):
        cases = [
            _rs("stale", page_current=False, reason="no review.html: run aidd review <spec>", n=0, stale=True),
            _rs("too_many_items", page_current=False, reason="too many items (2001 > 2000): x"),
            _rs("stale", page_current=False, reason="", stale=True),          # page not current
            _rs("stale", reason="source too large: plan.md", stale=True),
            _rs("pending", reason=SPLIT_REASON),
        ]
        for rs in cases:
            code, out, sleeps = self._wait([rs])
            self.assertEqual(code, 3, rs)
            self.assertEqual(len(out), 1)
            self.assertEqual(sleeps, [])
        code, out, _s = self._wait([_rs("pending")], tag=None)              # no tasks.md
        self.assertEqual(code, 3)
        self.assertTrue(out[0].endswith("tag=none"))

    def test_complete_but_stale_or_legacy_never_exits_0(self):
        code, _out, _s = self._wait([_rs("complete", stale=True)], timeout=2.0)
        self.assertEqual(code, 2)

    def test_import_error_and_errors(self):
        d = _make_spec(self.root, IDS[0])
        out = []
        with mock.patch.object(aidd_review, "_state", side_effect=ImportError("x")):
            self.assertEqual(aidd_review.review_wait(d, out=out.append, sleep=lambda s: None), 3)
        self.assertEqual(out, [])
        with mock.patch.object(aidd_review, "review_state", side_effect=RuntimeError("x")):
            self.assertEqual(aidd_review.review_wait(d, out=out.append, sleep=lambda s: None), 3)
        self.assertEqual(len(out), 1)
        self.assertNotIn("RuntimeError", out[0])


# ---------------------------------------------------------------------------
# main (aidd:FR-309, FR-313) in process, with fakes
# ---------------------------------------------------------------------------

class TestMain(_Faked):
    def _main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = aidd_review.main(list(argv))
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def test_check_prints_only_status_line_both_orders(self):
        for sid in IDS:
            d = _make_spec(self.root, sid)
            for state, want in (("pending", 2), ("complete", 0), ("stale", 3), ("legacy", 3),
                                ("too_many_items", 3)):
                self.state.result = dict(_rs(state, a=3, n=5), comments=[{"key": "FR-001", "text": "SENTINEL"}])
                for argv in ((str(d), "--check"), ("--check", f"{d}")):
                    code, out, _err = self._main(*argv)
                    self.assertEqual(code, want, (state, argv))
                    lines = out.splitlines()
                    self.assertEqual(len(lines), 1)
                    self.assertTrue(lines[0].startswith(f"STATE={state} approved=3/5 comments=1 "))
                    self.assertNotIn("SENTINEL", out)

    def test_comments(self):
        d = _make_spec(self.root, IDS[1])
        self.state.comments = (0, ["FR-001: one / - [x] FR-002", "T-02: split"])
        code, out, _e = self._main(str(d), "--comments")
        self.assertEqual((code, out), (0, "FR-001: one / - [x] FR-002\nT-02: split\n"))
        self.state.comments = (0, [])
        self.assertEqual(self._main(str(d), "--comments")[:2], (0, ""))
        self.state.comments = (3, [])
        self.assertEqual(self._main("--comments", str(d))[:2], (3, ""))

    def test_summary(self):
        d = _make_spec(self.root, IDS[0])
        before = _snapshot(d)
        code, out, _e = self._main("--summary", str(d))
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[0], "Objective: Fake objective")
        self.assertEqual(_snapshot(d), before)
        d2 = _make_spec(self.root / "nt", IDS[1], tasks=None)
        code, out, err = self._main(str(d2), "--summary")
        self.assertEqual((code, out), (3, ""))
        self.assertIn("tasks.md", err)
        self.assertEqual(list(d2.glob("review.*")), [])

    def test_wait_flags_forwarded(self):
        d = _make_spec(self.root, IDS[1])
        with mock.patch.object(aidd_review, "review_wait", return_value=2) as w:
            code, _o, _e = self._main("--wait", str(d), "--timeout", "5", "--interval", "0.5")
        self.assertEqual(code, 2)
        self.assertEqual(w.call_args.kwargs, {"timeout": 5.0, "interval": 0.5})
        for bad in (("--interval", "0"), ("--interval", "-1"), ("--timeout", "-1"), ("--timeout", "nan")):
            self.assertEqual(self._main(str(d), "--wait", *bad)[0], 1, bad)
        self.assertEqual(self._main(str(d), "--check", "--wait")[0], 1)

    def test_import_error_exit_3(self):
        d = _make_spec(self.root, IDS[0])
        with mock.patch.object(aidd_review, "_state", side_effect=ImportError("x")), \
                mock.patch.object(aidd_review, "_items", side_effect=ImportError("x")):
            for flag in ("--check", "--wait", "--comments", "--summary"):
                code, out, err = self._main(str(d), flag)
                self.assertEqual((code, out), (3, ""), flag)
                self.assertIn("reinstall AIDD", err)
                self.assertNotIn("Traceback", err)
            code, out, err = self._main(str(d))
            self.assertEqual(code, 3)
            self.assertFalse((d / "review.html").exists())

    def test_generate_mode_prints_no_state(self):
        d = _make_spec(self.root, IDS[1])
        with mock.patch.object(aidd_review, "_template_path",
                               return_value=self._tpl()):
            code, out, _e = self._main(str(d))
            self.assertEqual(code, 0)
            self.assertTrue(out.startswith("wrote: "))
            self.assertNotIn("STATE=", out)
            code, out, _e = self._main(str(d), "--full")
            self.assertEqual(code, 0)
            self.assertEqual(aidd_review._page_meta(d / "review.html")[2], "headings-v1")

    def _tpl(self):
        p = self.root / "tpl.html"
        p.write_text(TEMPLATE, encoding="utf-8")
        return p


class TestCliSubprocess(_Tmp):
    """Refusals that happen before either review module is needed."""

    def _run(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS_DIR / "aidd_review.py"), *args],
                              cwd=str(self.root), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=60)

    def test_generate_refusals_exit_1(self):
        d = _make_spec(self.root, IDS[1], tasks=None)
        r = self._run(str(d))
        self.assertEqual(r.returncode, 1)
        self.assertIn("tasks.md", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        d2 = _make_spec(self.root / "big", IDS[0])
        (d2 / "tasks.md").write_text(TASKS_MD + "x" * 450_000, encoding="utf-8")
        r = self._run(f"big/specs/{IDS[0]}")
        self.assertEqual(r.returncode, 1)
        self.assertIn("limit 400000", r.stderr)
        self.assertFalse((d2 / "review.html").exists())
        self.assertEqual(self._run(str(self.root / "specs" / "nope")).returncode, 1)
        self.assertEqual(self._run().returncode, 1)             # usage error is 1, never 2


def _cli(cwd, *args):
    """The REAL CLI entry (`aidd.cli.main`) in a child process, so the passthrough's own
    subprocess output and exit code are what the test sees."""
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import aidd.cli as c; "
            "c.main(sys.argv[2:])")
    return subprocess.run([sys.executable, "-c", code, str(REPO), *args], cwd=str(cwd),
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=120)


class TestCliHelp(unittest.TestCase):
    def test_p_review_help(self):
        sys.path.insert(0, str(REPO))
        import aidd.cli as cli
        # `aidd review -h` is passed through to aidd_review.py's own parser (aidd:FR-313)
        r = _cli(REPO, "review", "-h")
        self.assertEqual(r.returncode, 0, r.stderr)
        text = r.stdout
        for flag in ("--open", "--check", "--wait", "--comments", "--summary", "--full", "--timeout",
                     "--interval"):
            self.assertIn(flag, text)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit):
                cli.main(["-h"])
        top = re.sub(r"\s+", " ", out.getvalue())
        self.assertIn("aidd review <spec> [--open] [--check] [--wait] [--comments] [--summary] [--full]", top)


@unittest.skipIf(FAKES_ONLY, "AIDD_REVIEW_FAKES_ONLY=1: the main agent runs this with the real modules")
class TestCliFlagOrder(_Tmp):
    """aidd:FR-313 / closing-audit finding 3: `aidd review --check <spec>` and
    `aidd review <spec> --check` (same for --summary/--wait/--comments) give the same result
    through the real CLI entry; a leading flag is never an argparse error (exit 2)."""

    def _both(self, rel, *flags):
        after = _cli(self.root, "review", rel, *flags)
        before = _cli(self.root, "review", *flags, rel)
        for r in (after, before):
            self.assertNotIn("unrecognized arguments", r.stderr)
            self.assertNotIn("Traceback", r.stderr)
        self.assertEqual((before.returncode, before.stdout), (after.returncode, after.stdout))
        return after

    def test_flags_in_any_order_both_ids(self):
        for sid in IDS:
            d = _make_spec(self.root, sid, spec=REAL_SPEC)
            rel = f"specs/{sid}"
            aidd_review.generate(d, template_text=TEMPLATE)
            n = len(aidd_review.reviewable_keys(d))
            tag = f"[tasks:{_th(d)[:8]}]"
            r = self._both(rel, "--check")                                   # no review.md: pending
            self.assertEqual(r.returncode, 2)
            self.assertEqual(r.stdout.splitlines(),
                             [f"STATE=pending approved=0/{n} comments=0 stale=no legacy=no tag={tag}"])
            r = self._both(rel, "--wait", "--timeout", "0")
            self.assertEqual(r.returncode, 2)
            self.assertRegex(r.stdout.strip(), STATUS_RE)
            r = self._both(rel, "--comments")
            self.assertEqual(r.stdout, "")
            r = self._both(rel, "--summary")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(r.stdout.strip())
            self.assertFalse((d / "review.md").exists())


class TestItemHtmlAnswers(unittest.TestCase):
    """closing-audit finding 4 / aidd:AC-305: the extractor's capitalised `Answer` renders as
    `.ans`; an unanswered question (F28 Q11/Q12 shape) shows `pending - resolve in Align`."""

    def test_fake_items_capitalised_answer_and_pending(self):
        done = aidd_review._item_html({"code": "Q1", "kind": "question", "text": "Who signs?",
                                        "fields": {"Answer": "The owner", "Source": "kickoff"}})
        self.assertIn('<span class="ans">The owner</span>', done)
        self.assertNotIn('data-field="Answer"', done)
        self.assertIn('data-field="Source"', done)
        pend = aidd_review._item_html({"code": "Q11", "kind": "question", "text": "Which printer?",
                                        "fields": {"Answer": "", "Source": ""}, "unanswered": True})
        self.assertIn('data-unanswered="1"', pend)
        self.assertIn('<span class="ans">pending - resolve in Align</span>', pend)
        dec = aidd_review._item_html({"code": "D1", "kind": "decision", "text": "Use X",
                                       "fields": {"Decision": "Use X"}})
        self.assertIn('<span class="ans">Use X</span>', dec)

    @unittest.skipIf(FAKES_ONLY, "AIDD_REVIEW_FAKES_ONLY=1: real extractor not used")
    def test_real_extractor_f28_shape(self):
        import aidd_review_items as items
        spec = ("# Spec\n\n## Minimum Requirements Checklist\n"
                "| Question | Answer | Source | If unanswered |\n|---|---|---|---|\n"
                "| Q10 Who approves? | The owner | kickoff | block |\n"
                "| Q11 Which printer? | - |  | block |\n"
                "| Q12 Which tax? |  |  | block |\n")
        out = {it["code"]: aidd_review._item_html(it) for it in items._ex_questions({"spec.md": spec}, [])}
        self.assertIn('<span class="ans">The owner</span>', out["Q10"])
        self.assertNotIn("pending - resolve in Align", out["Q10"])
        for code in ("Q11", "Q12"):
            self.assertIn('data-unanswered="1"', out[code])
            self.assertIn('<span class="ans">pending - resolve in Align</span>', out[code])


# ---------------------------------------------------------------------------
# Integration with the REAL modules (end-of-wave gate; skipped in the builder's run)
# ---------------------------------------------------------------------------

B1_SPECS = Path(os.environ.get("AIDD_B1_SPECS", r"D:\Fuentes\b1SycLink\specs"))
REAL_SPEC = """# Spec

## Functional requirements
| Code | Requirement |
|---|---|
| FR-001 | Do X. SENTINEL-ITEM |
| FR-002 | Do Y. |

## Verification
| # | Command | Expected | Covers |
|---|---|---|---|
| V-1 | `python -m unittest tests.test_x` | exit 0 | FR-001 |
"""


def _copy_sources(src_dir, root, spec_id):
    """Copy ONLY the five sources (never review.md / review.html) into a scratch project."""
    d = Path(root) / "specs" / spec_id
    d.mkdir(parents=True, exist_ok=True)
    for name in aidd_review.SOURCES:
        if (Path(src_dir) / name).is_file():
            shutil.copyfile(Path(src_dir) / name, d / name)
    return d


@unittest.skipIf(FAKES_ONLY, "AIDD_REVIEW_FAKES_ONLY=1: the main agent runs this with the real modules")
class TestRealModules(_Tmp):
    def _run(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS_DIR / "aidd_review.py"), *args],
                              cwd=str(self.root), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120)

    def _line(self, d, *flags):
        r = self._run(str(d), *flags)
        lines = r.stdout.splitlines()
        self.assertEqual(len(lines), 1, r.stdout + r.stderr)
        self.assertRegex(lines[0], STATUS_RE)
        self.assertNotIn("Traceback", r.stderr)
        return r.returncode, lines[0]

    def _save(self, d, page, uncheck=(), comments=None, tasks_hash=None, age=60):
        data = _page_data(page.read_text(encoding="utf-8"))
        lines = [(c, c not in uncheck, data["digests"].get(c), (comments or {}).get(c)) for c in data["codes"]]
        md = d / "review.md"
        md.write_text(_codes_md(d.name, tasks_hash or data["tasks_hash"], data["sources_digest"], lines,
                                approved=not uncheck, reviewed="SENTINEL-REVIEWED"), encoding="utf-8")
        _age(page, age)
        return data

    def test_constants_match_contract(self):
        import aidd_review_items as items
        import aidd_review_state as state
        self.assertEqual(aidd_review._FMT_COMPACT, state.FORMAT_COMPACT)
        self.assertEqual(aidd_review._FMT_FULL, state.FORMAT_FULL)
        self.assertEqual(items.MAX_ITEMS, 2000)
        self.assertEqual(items.CODE_RE.pattern, CODE_RE_SRC)

    def test_ac317_states_and_exits_both_ids(self):
        for sid in IDS:
            d = _make_spec(self.root, sid, spec=REAL_SPEC)
            tag = f"[tasks:{_th(d)[:8]}]"
            code, line = self._line(d, "--check")                           # no review.html
            self.assertEqual(code, 3)
            self.assertRegex(line, r"^STATE=stale approved=0/0 comments=0 stale=yes legacy=no ")
            page, _ = aidd_review.generate(d, template_text=TEMPLATE)
            n = len(aidd_review.reviewable_keys(d))
            code, line = self._line(d, "--check")                           # no review.md
            self.assertEqual((code, line), (2, f"STATE=pending approved=0/{n} comments=0 stale=no legacy=no tag={tag}"))
            self._save(d, page, uncheck=("FR-002",))
            code, line = self._line(d, "--check")
            self.assertEqual(code, 2)
            self.assertTrue(line.startswith(f"STATE=pending approved={n - 1}/{n} "), line)
            self._save(d, page, comments={"FR-001": "SENTINEL-COMMENT\n- [x] FR-002", "T-02": "split"})
            code, line = self._line(d, "--check")
            self.assertEqual((code, line), (0, f"STATE=complete approved={n}/{n} comments=2 stale=no legacy=no tag={tag}"))
            r = self._run(str(d), "--comments")
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout.splitlines(), ["FR-001: SENTINEL-COMMENT / - [x] FR-002", "T-02: split"])
            code, line = self._line(d, "--wait", "--timeout", "0")
            self.assertEqual(code, 0)
            self.assertNotIn("SENTINEL", line)
            self._save(d, page, tasks_hash="0" * 12)                        # older tasks_hash
            code, line = self._line(d, "--check")
            self.assertEqual(code, 3)
            self.assertRegex(line, r"^STATE=stale .* stale=yes ")
            self.assertEqual(self._run(str(d), "--comments").stdout, "")
            (d / "review.md").write_text(_headings_md(d), encoding="utf-8")  # 007 grammar, compact page
            code, line = self._line(d, "--check")
            self.assertEqual(code, 3)
            self.assertRegex(line, r"^STATE=legacy .* legacy=yes ")

    def test_too_many_items_with_and_without_page(self):
        rows = "".join(f"| FR-{i:04d} | r |\n" for i in range(1, 2002))
        spec = "# Spec\n\n## Functional requirements\n| Code | Requirement |\n|---|---|\n" + rows
        for with_page in (False, True):
            d = _make_spec(self.root / str(with_page), IDS[1], spec=REAL_SPEC)
            if with_page:
                aidd_review.generate(d, template_text=TEMPLATE)
            (d / "spec.md").write_text(spec, encoding="utf-8")
            code, line = self._line(d, "--check")
            self.assertEqual(code, 3)
            self.assertTrue(line.startswith("STATE=too_many_items "), line)
            self.assertTrue(aidd_review.review_state(d)["reason"].startswith("too many items ("))
            code, _line = self._line(d, "--wait", "--timeout", "0")
            self.assertEqual(code, 3)
            r = self._run(str(d))
            self.assertEqual(r.returncode, 1)
            self.assertIn("too many items (", r.stderr)

    def test_summary_real_specs(self):
        cases = [(REPO / "specs" / "002-aidd-hard-rules", "002-aidd-hard-rules")]
        for sid in ("F28-DB-Unification-Sync", "F23-eDoc-POS"):
            if (B1_SPECS / sid / "tasks.md").is_file():
                cases.append((B1_SPECS / sid, sid))
        for src, sid in cases:
            d = _copy_sources(src, self.root, sid)
            if not (d / "tasks.md").is_file():
                # aidd:AC-326 the real 002 ships only spec.md, and a spec without tasks.md
                # must exit 3: pair its real spec.md with the fixture tasks.md.
                (d / "tasks.md").write_text(TASKS_MD, encoding="utf-8")
            r1, r2 = self._run(str(d), "--summary"), self._run("--summary", str(d))
            self.assertEqual(r1.returncode, 0, r1.stderr)
            self.assertEqual(r1.stdout, r2.stdout)
            lines = r1.stdout.splitlines()
            self.assertTrue(1 <= len(lines) <= 30, sid)
            self.assertEqual(list(d.glob("review.*")), [])
        d = _make_spec(self.root / "nt", IDS[0], tasks=None)
        self.assertEqual(self._run(str(d), "--summary").returncode, 3)

    def test_f28_generate_state_and_carry(self):
        src = B1_SPECS / "F28-DB-Unification-Sync"
        if not (src / "tasks.md").is_file():
            self.skipTest("b1SycLink F28 sources not available")
        d = _copy_sources(src, self.root, "F28-DB-Unification-Sync")
        page, wrote = aidd_review.generate(d, template_text=TEMPLATE)
        self.assertTrue(wrote)
        codes = aidd_review.reviewable_keys(d)
        tag = f"[tasks:{_th(d)[:8]}]"
        if tag == "[tasks:5c3cbb5b]":
            self.assertEqual(len(codes), 177)
        data = self._save(d, page)
        self.assertEqual(data["codes"], codes)
        code, line = self._line(d, "--check")
        self.assertEqual((code, line), (0, f"STATE=complete approved={len(codes)}/{len(codes)} "
                                           f"comments=0 stale=no legacy=no tag={tag}"))
        st = aidd_review.review_state(d)
        self.assertTrue(st["complete"], st["reason"])
        self.assertFalse(st["legacy"])
        self.assertEqual(st["item_count"], len(codes))
        # AC-321 (b): only plan.md prose edited -> the page is regenerated, every item is carried
        with open(d / "plan.md", "a", encoding="utf-8", newline="\n") as f:
            f.write("\nA prose paragraph added after the review.\n")
        md_before = (d / "review.md").read_bytes()
        _p, wrote = aidd_review.generate(d, template_text=TEMPLATE)
        self.assertTrue(wrote)
        new = _page_data(page.read_text(encoding="utf-8"))
        self.assertEqual(new["carry"], {"carried": len(codes), "total": len(codes), "pending": []})
        self.assertEqual((d / "review.md").read_bytes(), md_before)
        # AC-320: one task row edited -> only that code is pending
        t = (d / "tasks.md").read_text(encoding="utf-8")
        row = next((ln for ln in t.splitlines() if re.match(r"^\|\s*T-17\s*\|", ln)), None)
        if row is not None:
            self._save(d, page)
            cells = row.split("|")
            cells[2] = cells[2].rstrip() + " edited "
            (d / "tasks.md").write_text(t.replace(row, "|".join(cells)), encoding="utf-8")
            aidd_review.generate(d, template_text=TEMPLATE)
            self.assertEqual(_page_data(page.read_text(encoding="utf-8"))["carry"]["pending"], ["T-17"])


if __name__ == "__main__":
    unittest.main()
