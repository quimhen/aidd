import importlib.util
import json
import re
import tempfile
import unittest
import sys
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / 'skill' / 'scripts' / 'aidd_navigator.py'
sys.path.insert(0, str(FILE.parent))
SPEC = importlib.util.spec_from_file_location('aidd_navigator', FILE)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class NavigatorTests(unittest.TestCase):
    def test_model_and_html_escape_project_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / 'specs' / '001-example'
            spec.mkdir(parents=True)
            (spec / 'spec.md').write_text('# Example\nSCREEN-42\n</script><script>evil()</script>', encoding='utf-8')
            (spec / 'tasks.md').write_text('| T-01 | text |\n| T-01 | duplicate |\n| T-02 | text |', encoding='utf-8')
            (spec / 'plan.md').write_text('Plan de ejemplo', encoding='utf-8')
            (spec / 'review.html').write_text('fixture', encoding='utf-8')
            (spec / 'amendment-01-spec.md').write_text('draft', encoding='utf-8')
            (spec / 'evidence').mkdir()
            (spec / 'evidence' / 'verify.txt').write_text('unverified', encoding='utf-8')
            unit = spec / 'amendments' / 'unit01'
            unit.mkdir(parents=True)
            (unit / 'manifest.json').write_text(json.dumps({'schema_version': 1, 'spec_id': '001-example',
                'unit_id': 'unit01', 'sequence': 1, 'parents': [], 'paths': [], 'targets': []}), encoding='utf-8')
            html = module.build_navigator(root)
            data = re.search(r'<script type="application/json" id="navigator-data">(.*?)</script>', html).group(1)
            self.assertNotIn('</script>', data)
            model = json.loads(data)
            self.assertEqual(model[0]['tasks'], 2)
            self.assertEqual(model[0]['screens'], ['SCREEN-42'])
            self.assertEqual(model[0]['evidence'], ['verify.txt'])
            self.assertEqual(model[0]['amendments'], ['amendment-01-spec.md'])
            self.assertIn('unit01', model[0]['units'][0])
            self.assertEqual(model[0]['review_url'], (spec / 'review.html').resolve().as_uri())
            self.assertIn('id="reviewLink"', html)

    def test_empty_project_and_external_spec_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'specs').mkdir()
            self.assertEqual(module.collect_specs(root), [])
            outside = root / 'outside'
            outside.mkdir()
            (outside / 'spec.md').write_text('# private', encoding='utf-8')
            try:
                (root / 'specs' / 'linked').symlink_to(outside, target_is_directory=True)
            except OSError:
                return
            self.assertEqual(module.collect_specs(root), [])

    def test_refuses_protected_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.aidd').mkdir()
            for path in (root / '.aidd' / 'page.html', root / 'review.html', root / 'data.txt'):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    module.main([str(root), '--output', str(path)])
                self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
