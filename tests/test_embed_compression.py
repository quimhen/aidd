"""Amendment 10 of spec 007, FR-409..FR-412 (AC-463..AC-466): AIDD compresses what it embeds by default.
Round trip pack -> unpack byte for byte; a 1 MB tasks.md is reviewable without splitting; the compact review page
embeds its data as gzip+base64 and every reader decodes it. stdlib unittest (node is used only when present)."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'skill' / 'scripts'))
import aidd_embed  # noqa: E402
import aidd_review  # noqa: E402

DATA_RE = re.compile(r'<script type="application/json" id="aidd-data">(.*?)</script>', re.S)


def big_spec(root, tasks_chars=1_000_000):
    d = Path(root) / 'specs' / '001-big'
    d.mkdir(parents=True)
    (d / 'spec.md').write_text('# Spec\n\n## Functional requirements\n\n| Code | Requirement |\n|---|---|\n'
                               '| FR-001 | one |\n', encoding='utf-8')
    block = ('### T-{n:02d} Task {n}\n\nAgent min: 5\nTokens (est): 50k\n\n'
             + 'Detalle ñandú del paso a paso con texto largo. ' * 40 + '\n\n')
    parts, n = ['# Tasks\n\n'], 1
    while sum(len(p) for p in parts) < tasks_chars:
        parts.append(block.format(n=n % 90 + 1))
        n += 1
    (d / 'tasks.md').write_text(''.join(parts), encoding='utf-8')
    return d


class RoundTrip(unittest.TestCase):
    def test_pack_unpack_identical(self):
        for text in ('', 'a', 'ñandú → 漢字   </script>', 'x' * 1_000_000, json.dumps({'k': list(range(5000))})):
            with self.subTest(n=len(text)):
                self.assertEqual(aidd_embed.unpack(aidd_embed.pack(text)), text)
                self.assertEqual(aidd_embed.unpack(aidd_embed.pack(text)).encode('utf-8'), text.encode('utf-8'))

    def test_deterministic_and_ascii(self):
        p = aidd_embed.pack('same input')
        self.assertEqual(p, aidd_embed.pack('same input'))
        p.encode('ascii')
        self.assertNotIn('<', p)

    def test_damaged_payload_raises(self):
        with self.assertRaises(ValueError):
            aidd_embed.unpack('not-base64-gzip')

    @unittest.skipUnless(shutil.which('node'), 'node not installed')
    def test_browser_decoder_round_trip_in_node(self):
        text = json.dumps({'a': 'ñ ' * 50000, 'b': '</script>'})
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / 'p.b64').write_text(aidd_embed.pack(text), encoding='ascii')
            (t / 'inflate.js').write_text(
                aidd_embed.JS_INFLATE + "\nconst fs=require('fs');aiddInflate(fs.readFileSync(process.argv[2],'utf8'))"
                ".then(x=>fs.writeFileSync(process.argv[3],x,'utf8')).catch(e=>{console.error(String(e));process.exit(1)});",
                encoding='utf-8')
            p = subprocess.run(['node', str(t / 'inflate.js'), str(t / 'p.b64'), str(t / 'out.txt')],
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual((t / 'out.txt').read_text(encoding='utf-8'), text)


class ReviewPage(unittest.TestCase):
    def test_template_decoder_matches_shared_decoder(self):
        tpl = (REPO / 'skill' / 'templates' / 'review.html').read_text(encoding='utf-8')
        norm = lambda s: re.sub(r'\s+', ' ', s).strip()
        self.assertIn(norm(aidd_embed.JS_INFLATE), norm(tpl))

    def test_one_megabyte_tasks_reviewable_and_blob_round_trips(self):
        with tempfile.TemporaryDirectory() as t:
            d = big_spec(t)
            self.assertGreaterEqual(len((d / 'tasks.md').read_text(encoding='utf-8')), 1_000_000)
            gz = aidd_review.build_html(d)
            plain = aidd_review.build_html(d, compress=False)
            head = json.loads(DATA_RE.search(gz).group(1))
            self.assertEqual(head['encoding'], 'gzip+base64')
            for k in ('spec', 'tasks_hash', 'sources_digest', 'format'):
                self.assertIn(k, head)
            full_gz = json.loads(aidd_embed.unpack(head['gz']))
            full_plain = json.loads(DATA_RE.search(plain).group(1))
            self.assertEqual(full_gz, full_plain)
            self.assertLess(len(gz), len(plain))
            page = d / 'page.html'
            page.write_text(gz, encoding='utf-8')
            self.assertEqual(aidd_review._page_blob(page), full_plain)
            self.assertEqual(aidd_review._page_meta(page)[2], 'codes-v2')

    def test_full_page_stays_plain(self):
        with tempfile.TemporaryDirectory() as t:
            d = big_spec(t, 2000)
            head = json.loads(DATA_RE.search(aidd_review.build_html(d, full=True)).group(1))
            self.assertNotIn('gz', head)


class GitIgnore(unittest.TestCase):
    """aidd:FR-412 generated files are ignored in every project AIDD sets up."""

    def test_ensure_is_idempotent_and_keeps_existing_lines(self):
        import aidd_gitignore
        with tempfile.TemporaryDirectory() as t:
            gi = Path(t) / '.gitignore'
            gi.write_text('node_modules/\ndocs/graphs/explorer.html', encoding='utf-8')
            added = aidd_gitignore.ensure(t)
            self.assertNotIn('docs/graphs/explorer.html', added)
            self.assertIn('specs/*/review.html', added)
            text = gi.read_text(encoding='utf-8')
            self.assertTrue(text.startswith('node_modules/\ndocs/graphs/explorer.html\n'))
            self.assertEqual(aidd_gitignore.ensure(t), [])
            self.assertEqual(gi.read_text(encoding='utf-8'), text)

    def test_dry_run_writes_nothing(self):
        import aidd_gitignore
        with tempfile.TemporaryDirectory() as t:
            self.assertTrue(aidd_gitignore.ensure(t, dry_run=True))
            self.assertFalse((Path(t) / '.gitignore').exists())

    def test_repo_ignores_generated_explorer(self):
        import aidd_gitignore
        have = set((REPO / '.gitignore').read_text(encoding='utf-8').splitlines())
        self.assertTrue(set(aidd_gitignore.wanted_lines()[1]) <= have)


if __name__ == '__main__':
    unittest.main()
