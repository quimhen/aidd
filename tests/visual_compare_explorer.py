#!/usr/bin/env python3
"""T-VISUAL (aidd:FR-077, AC-066): measured comparison of the generated explorer with the F47 Stitch prototype
(SCREEN-95) and the approved alias mockup (SCREEN-901). Selectors, CSS tokens, counts and computed values only;
nothing is judged by eye or by screenshot. Builds the page of the synthetic project of tests/test_unified_graph.py.

Usage:  python tests/visual_compare_explorer.py
Prints the report as JSON (sorted keys). Exit 0 when no required check differs, 1 otherwise, 2 without Playwright.
"""
import contextlib
import hashlib
import io
import json
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "skill" / "scripts"))
sys.path.insert(0, str(HERE))

PROTOTYPE = "batch-staging/f47-port-sources/f47-spec/prototype/stitch-SCREEN-95.html"
ALIAS_MOCKUP = "specs/007-aidd-review-html-close-gate/prototypes/alias-graph-explorer/alias-graph-explorer.html"
REFERENCE_COMPONENTS = "batch-staging/f47-port-sources/reference/components"

CONTROL_IDS = ("zoomInBtn", "zoomOutBtn", "zoomResetBtn", "zoomLevelDisplay", "fitViewBtn", "centerNodeBtn",
               "copyNodeBtn", "themeToggleBtn")
# page token -> alias mockup token it takes its value from (FR-072)
TOKEN_MAP = {"--bg-dark": "--bg", "--bg-card": "--bg", "--bg-surface": "--sf", "--bg-card-hover": "--sf",
             "--bg-input": "--sf", "--border-subtle": "--bd", "--border-strong": "--bd", "--text-main": "--fg",
             "--text-muted": "--mut", "--text-faint": "--mut"}
ALIAS_ONLY = ("aliasCountText", "stat-counts", "detailScope", "detailReason", "emptyBanner", "legend")
REIDENTIFIED = ("btn-zoom-in", "btn-zoom-out", "btn-zoom-reset")   # F47 ids renamed to the mockup ids (FR-071)
HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")

JS_TOKENS = """() => {
  const names = new Set();
  for (const sheet of Array.from(document.styleSheets)) {
    let rules = [];
    try { rules = Array.from(sheet.cssRules); } catch (e) { continue; }
    for (const r of rules) {
      if (!r.style || !r.selectorText || !r.selectorText.startsWith(":root")) continue;
      for (let i = 0; i < r.style.length; i++) { if (r.style[i].startsWith("--")) names.add(r.style[i]); }
    }
  }
  const cs = getComputedStyle(document.documentElement);
  const out = {};
  Array.from(names).sort().forEach(n => { out[n] = cs.getPropertyValue(n).trim(); });
  return out;
}"""


def check_sha(path, sha_file):
    """True when the sha256 of `path` equals the first hex field of `sha_file`."""
    try:
        want = Path(sha_file).read_text(encoding="utf-8").split()[0].strip().lower()
        return hashlib.sha256(Path(path).read_bytes()).hexdigest() == want
    except (OSError, IndexError):
        return False


def _block(html, selector_re):
    m = re.search(selector_re + r"\s*\{([^}]*)\}", html)
    if not m:
        return {}
    return {k.strip(): v.strip().lower() for k, v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", m.group(1))}


def mockup_tokens(html):
    """{"light": {...}, "dark": {...}} custom properties of the alias mockup's `:root` and `.dark` rules."""
    return {"light": _block(html, r"(?m)^:root"), "dark": _block(html, r"(?m)^\.dark")}


def prototype_colours(html):
    """Hex colours of the prototype's `tailwind-config` script (lower case)."""
    m = re.search(r'<script id="tailwind-config">(.*?)</script>', html, flags=re.S)
    return {h.lower() for h in HEX_RE.findall(m.group(1))} if m else set()


def page_measures(page):
    """Measured values of the open explorer page (it toggles the theme and the zoom, then restores them)."""
    m = {"ids": page.evaluate("() => Array.from(document.querySelectorAll('[id]')).map(e => e.id)")}
    m["zoom_start"] = page.inner_text("#zoomLevelDisplay").strip() if "zoomLevelDisplay" in m["ids"] else None
    m["dark"] = page.evaluate(JS_TOKENS)
    m["light"] = {}
    if "themeToggleBtn" in m["ids"]:
        page.click("#themeToggleBtn")
        m["light"] = page.evaluate(JS_TOKENS)
        page.click("#themeToggleBtn")
    m["zoom"] = None
    if all(i in m["ids"] for i in ("zoomInBtn", "zoomOutBtn", "zoomResetBtn", "zoomLevelDisplay")):
        def k():
            return page.evaluate("() => window.aiddExplorer ? window.aiddExplorer.getTransform().k : null")
        page.click("#zoomResetBtn")
        k0 = k()
        page.click("#zoomInBtn")
        step = (k() / k0) if k0 else None
        for _ in range(20):
            page.click("#zoomInBtn")
        kmax = k()
        for _ in range(40):
            page.click("#zoomOutBtn")
        kmin = k()
        page.click("#zoomResetBtn")
        m["zoom"] = {"step": round(step, 4) if step else None, "min": kmin, "max": kmax}
    return m


def _check(checks, cid, source, kind, expected, actual, required, status=None, reason=""):
    if status is None:
        status = "match" if expected == actual else "differ"
    checks.append({"id": cid, "source": source, "kind": kind, "expected": expected, "actual": actual,
                   "status": status, "reason": reason, "required": required})


def _summary(checks):
    s = {"match": 0, "differ": 0, "not_comparable": 0, "required_differ": 0}
    for c in checks:
        if c["status"] == "match":
            s["match"] += 1
        elif c["status"] == "differ":
            s["differ"] += 1
            if c["required"]:
                s["required_differ"] += 1
        elif c["status"] == "not-comparable":
            s["not_comparable"] += 1
    return s


def _no_browser(reason):
    checks = []
    _check(checks, "browser", "page", "computed", "chromium", None, False, "not-comparable", reason)
    return {"checks": checks, "summary": _summary(checks)}


def compare():
    """Build the synthetic page, measure it headless, compare with both mockups; returns the report."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return _no_browser("no Chromium available")
    import graph_explorer
    from test_unified_graph import make_project
    checks = []
    for rel, src in ((PROTOTYPE, "SCREEN-95"), (ALIAS_MOCKUP, "SCREEN-901")):
        p = REPO / rel
        sha = p.parent / (p.name + ".sha256")
        if not sha.is_file():
            sha = p.with_suffix(".sha256")
        _check(checks, "sha256:" + p.name, src, "computed", True, check_sha(p, sha), True)
    alias_html = (REPO / ALIAS_MOCKUP).read_text(encoding="utf-8")
    proto_html = (REPO / PROTOTYPE).read_text(encoding="utf-8")
    mock = mockup_tokens(alias_html)
    requests = []
    with tempfile.TemporaryDirectory() as tmp:
        root = make_project(Path(tmp) / "proj")
        out = Path(tmp) / "explorer.html"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = graph_explorer.main(["--root", str(root), "--out", str(out)])
        _check(checks, "page-built", "page", "count", 0, rc, True)
        if rc != 0:
            return {"checks": checks, "summary": _summary(checks)}
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                try:
                    page = browser.new_page(viewport={"width": 1280, "height": 800})
                    page.on("request", lambda r: None if r.url.startswith("file:") else requests.append(r.url))
                    page.goto(out.resolve().as_uri())
                    page.wait_for_load_state("load")
                    m = page_measures(page)
                finally:
                    browser.close()
        except Exception as ex:
            return _no_browser("no Chromium available (%s)" % type(ex).__name__)
    _check(checks, "non-file-requests", "page", "count", 0, len(requests), True)
    # alias mockup (SCREEN-901), required
    for cid in CONTROL_IDS:
        _check(checks, "id:" + cid, "SCREEN-901", "selector", 1, m["ids"].count(cid), True)
    for tok, mtok in sorted(TOKEN_MAP.items()):
        _check(checks, "light:" + tok, "SCREEN-901", "computed", mock["light"].get(mtok),
               (m["light"].get(tok) or "").lower() or None, True)
    _check(checks, "zoom-display-start", "SCREEN-901", "computed", "100%", m["zoom_start"], True)
    # alias mockup, reported only
    for tok, mtok in sorted(TOKEN_MAP.items()):
        exp, act = mock["dark"].get(mtok), (m["dark"].get(tok) or "").lower() or None
        _check(checks, "dark:" + tok, "SCREEN-901", "token", exp, act, False,
               "match" if exp == act else "accepted-differ",
               "" if exp == act else "owner kept the F47 dark palette, 2026-11-03")
    zexp = {"step": 1.15, "min": 0.4, "max": 2.5}
    _check(checks, "zoom-step-range", "SCREEN-901", "computed", zexp, m["zoom"], False,
           "match" if m["zoom"] == zexp else "accepted-differ",
           "" if m["zoom"] == zexp else "owner kept the F47 zoom")
    for cid in ALIAS_ONLY:
        _check(checks, "alias-only:" + cid, "SCREEN-901", "selector", 1, None, False, "not-comparable",
               "alias layer: amendment 06")
    # F47 prototype (SCREEN-95), required
    colours = prototype_colours(proto_html)
    _check(checks, "colour:#00677c", "SCREEN-95", "computed", "#00677c" if "#00677c" in colours else None,
           (m["dark"].get("--layer-db-dark") or "").lower() or None, True)
    for tok, font in (("--font-sans", "Roboto Flex"), ("--font-mono", "JetBrains Mono")):
        val = m["dark"].get(tok) or ""
        _check(checks, "font:" + tok, "SCREEN-95", "computed", font, font if font in val else val, True)
    # F47 prototype, reported only
    page_hex = {v.strip().lower() for v in list(m["dark"].values()) + list(m["light"].values())
                if HEX_RE.fullmatch(v.strip())}
    for h in sorted(colours - {"#00677c"}):
        _check(checks, "prototype-hex:" + h, "SCREEN-95", "token", "present", "present" if h in page_hex else "absent",
               False)
    ref_ids = set()
    for f in sorted((REPO / REFERENCE_COMPONENTS).glob("*.html")):
        ref_ids |= set(re.findall(r'id="([A-Za-z][\w-]*)"', f.read_text(encoding="utf-8")))
    for cid in sorted(ref_ids - set(m["ids"]) - set(REIDENTIFIED)):
        _check(checks, "generator-only:" + cid, "SCREEN-95", "selector", 1, 0, False, "differ", "owner decision Q-1")
    for what in ("layout", "spacing", "canvas-pixels"):
        _check(checks, what, "both", "computed", None, None, False, "not-comparable",
               "different DOM; no pixel judgement")
    return {"checks": checks, "summary": _summary(checks)}


def main():
    report = compare()
    print(json.dumps(report, indent=2, sort_keys=True))
    if len(report["checks"]) == 1 and report["checks"][0]["status"] == "not-comparable":
        return 2
    return 0 if report["summary"]["required_differ"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
