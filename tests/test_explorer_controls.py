"""Static tests for the 8 controls the explorer adopts from the approved alias mockup (aidd:FR-071..FR-075, AC-062).
No browser: markup, wiring by id, the light-theme tokens and the test hook. Synthetic project only; no network."""
import contextlib
import io
import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "skill" / "scripts"))
sys.path.insert(0, str(HERE))
from test_unified_graph import make_project  # noqa: E402

CONTROL_IDS = ("zoomInBtn", "zoomOutBtn", "zoomResetBtn", "zoomLevelDisplay", "fitViewBtn", "centerNodeBtn",
               "copyNodeBtn", "themeToggleBtn")
LIGHT_TOKENS = {"--bg-dark": "#ffffff", "--bg-surface": "#f6f8fa", "--bg-card": "#ffffff", "--bg-card-hover": "#f6f8fa",
                "--bg-input": "#f6f8fa", "--border-subtle": "#d0d7de", "--border-strong": "#d0d7de",
                "--text-main": "#1b1f24", "--text-muted": "#667788", "--text-faint": "#667788"}
OLD_ZOOM_IDS = ("btn-zoom-in", "btn-zoom-out", "btn-zoom-reset")


def light_block(html):
    """Text inside the `:root.light { ... }` rule ('' when absent)."""
    m = re.search(r":root\.light\s*\{([^}]*)\}", html)
    return m.group(1) if m else ""


class ExplorerControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import graph_explorer
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        root = make_project(tmp / "proj")
        out = tmp / "u.html"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = graph_explorer.main(["--root", str(root), "--out", str(out)])
        cls.unified = out.read_text(encoding="utf-8") if rc == 0 and out.is_file() else ""
        cls.single = graph_explorer.build_html({"nodes": [{"id": "a"}], "edges": []}, "T")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def pages(self):
        self.assertTrue(self.unified, "unified page was not generated")
        return (("unified", self.unified), ("single", self.single))

    def _each_once(self, html):
        for i in CONTROL_IDS:
            self.assertEqual(html.count('id="%s"' % i), 1, i)

    def test_each_control_once_unified(self):
        self.assertTrue(self.unified, "unified page was not generated")
        self._each_once(self.unified)

    def test_each_control_once_single_graph(self):
        self._each_once(self.single)

    def test_old_zoom_ids_gone(self):
        for name, html in self.pages():
            for i in OLD_ZOOM_IDS:
                self.assertNotIn(i, html, "%s: %s" % (name, i))

    def test_controls_are_wired(self):
        for name, html in self.pages():
            for i in CONTROL_IDS:
                self.assertIn('getElementById("%s")' % i, html, "%s: %s" % (name, i))

    def test_light_theme_tokens(self):
        for name, html in self.pages():
            block = light_block(html)
            for k, v in LIGHT_TOKENS.items():
                m = re.search(re.escape(k) + r"\s*:\s*([^;]+);", block)
                self.assertIsNotNone(m, "%s: %s missing in :root.light" % (name, k))
                self.assertEqual(m.group(1).strip().lower(), v, "%s: %s" % (name, k))
            self.assertIn('classList.toggle("light")', html)

    def test_test_hook_present(self):
        for name, html in self.pages():
            self.assertIn("window.aiddExplorer", html, name)
            self.assertIn("navigator.clipboard", html, name)

    def test_self_contained(self):
        for name, html in self.pages():
            shell = re.sub(r'<script id="graph-data".*?</script>', "", html, flags=re.S)
            for bad in ("http://", "https://", "//cdn", "<script src", "<link", "@import", "url("):
                self.assertNotIn(bad, shell, "%s: %s" % (name, bad))


if __name__ == "__main__":
    unittest.main()
