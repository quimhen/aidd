"""Headless-browser tests: each adopted control WORKS, by measured values (aidd:FR-071..FR-075, AC-063).
Skipped visibly when Playwright or Chromium is not installed. Only file:// URLs are loaded; no screenshot judgement."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "skill" / "scripts"))
sys.path.insert(0, str(HERE))
from test_unified_graph import make_project  # noqa: E402

THEME_KEY = "aidd-explorer-theme"
BLOCK_STORAGE = ("Object.defineProperty(window, 'localStorage', {configurable: true, "
                 "get() { throw new Error('storage blocked'); }});")
BG_DARK = 'getComputedStyle(document.documentElement).getPropertyValue("--bg-dark")'


def _have_browser():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            b.close()
        return True
    except Exception:
        return False


HAVE_BROWSER = _have_browser()


@unittest.skipUnless(HAVE_BROWSER, "playwright/chromium not installed")
class ExplorerControlsBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import graph_explorer
        from playwright.sync_api import sync_playwright
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        root = make_project(tmp / "proj")
        cls.html_path = tmp / "explorer.html"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            cls.build_rc = graph_explorer.main(["--root", str(root), "--out", str(cls.html_path)])
        cls._pw = sync_playwright().start()
        cls.browser = cls._pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.browser.close()
            cls._pw.stop()
        finally:
            cls._tmp.cleanup()

    def setUp(self):
        self.assertEqual(self.build_rc, 0, "explorer page was not generated")
        self.requests, self.errors, self._contexts = [], [], []
        self.addCleanup(lambda: [c.close() for c in self._contexts])

    def open_page(self, html_path, init_script=None, context=None):
        """Open file:// html_path at 1280x800 in a (new) context; records non-file requests and page errors."""
        if context is None:
            context = self.browser.new_context(viewport={"width": 1280, "height": 800})
            context.grant_permissions(["clipboard-read", "clipboard-write"])
            if init_script:
                context.add_init_script(init_script)
            self._contexts.append(context)
        page = context.new_page()
        page.on("request", lambda r: None if r.url.startswith("file:") else self.requests.append(r.url))
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.goto(Path(html_path).resolve().as_uri())
        page.wait_for_function("() => !!window.aiddExplorer")
        return page

    def zoom_text(self, page):
        return page.inner_text("#zoomLevelDisplay").strip()

    def bg_dark(self, page):
        return page.evaluate(BG_DARK).strip().lower()

    def test_zoom_buttons_and_display(self):
        page = self.open_page(self.html_path)
        self.assertEqual(self.zoom_text(page), "100%")
        page.click("#zoomInBtn")
        self.assertEqual(self.zoom_text(page), "125%")
        page.click("#zoomResetBtn")
        self.assertEqual(self.zoom_text(page), "100%")
        page.click("#zoomOutBtn")
        self.assertEqual(self.zoom_text(page), "80%")

    def test_fit_view(self):
        page = self.open_page(self.html_path)
        before = page.evaluate("() => window.aiddExplorer.getTransform()")
        page.click("#fitViewBtn")
        value = float(self.zoom_text(page).rstrip("%"))
        self.assertTrue(20 <= value <= 400, value)
        self.assertNotEqual(page.evaluate("() => window.aiddExplorer.getTransform()"), before)

    def test_center_on_selected_node(self):
        page = self.open_page(self.html_path)
        page.evaluate('() => window.aiddExplorer.selectNode("db:table:ORDR")')
        self.assertEqual(page.evaluate("() => window.aiddExplorer.getFocalId()"), "db:table:ORDR")
        rect = page.evaluate("() => { const r = document.getElementById('network-canvas').getBoundingClientRect();"
                             " return {w: r.width, h: r.height}; }")
        fx, fy = rect["w"] / 2, rect["h"] / 2      # the focal node is laid out at the canvas centre (k = 1)
        page.click("#zoomInBtn")
        page.click("#zoomInBtn")
        t = page.evaluate("() => window.aiddExplorer.getTransform()")
        self.assertGreater(abs(fx * t["k"] + t["x"] - rect["w"] / 2), 1)
        page.click("#centerNodeBtn")
        t = page.evaluate("() => window.aiddExplorer.getTransform()")
        self.assertLessEqual(abs(fx * t["k"] + t["x"] - rect["w"] / 2), 1)
        self.assertLessEqual(abs(fy * t["k"] + t["y"] - rect["h"] / 2), 1)

    def test_copy_node(self):
        page = self.open_page(self.html_path)
        page.evaluate('() => window.aiddExplorer.selectNode("db:table:ORDR")')
        page.click("#copyNodeBtn")
        self.assertEqual(page.inner_text("#copyNodeBtn").strip(), "Copiado")
        text = page.evaluate("() => navigator.clipboard.readText()")
        self.assertEqual(json.loads(text)["id"], "db:table:ORDR")

    def test_theme_toggle_changes_tokens(self):
        page = self.open_page(self.html_path)
        self.assertEqual(self.bg_dark(page), "#091016")
        page.click("#themeToggleBtn")
        self.assertEqual(self.bg_dark(page), "#ffffff")
        page.click("#themeToggleBtn")
        self.assertEqual(self.bg_dark(page), "#091016")

    def test_theme_remembered_after_reload(self):
        page = self.open_page(self.html_path)
        page.click("#themeToggleBtn")
        page.reload()
        page.wait_for_function("() => !!window.aiddExplorer")
        self.assertEqual(self.bg_dark(page), "#ffffff")
        self.assertEqual(page.evaluate('() => localStorage.getItem("%s")' % THEME_KEY), "light")

    def test_theme_works_with_storage_blocked(self):
        page = self.open_page(self.html_path, init_script=BLOCK_STORAGE)
        page.click("#themeToggleBtn")
        self.assertEqual(self.bg_dark(page), "#ffffff")
        page.reload()
        page.wait_for_function("() => !!window.aiddExplorer")
        self.assertEqual(self.bg_dark(page), "#091016")
        self.assertEqual(self.errors, [])

    def test_no_external_requests(self):
        page = self.open_page(self.html_path)
        page.click("#zoomInBtn")
        page.click("#fitViewBtn")
        page.click("#themeToggleBtn")
        page.wait_for_timeout(200)
        self.assertEqual(self.requests, [])


if __name__ == "__main__":
    unittest.main()
