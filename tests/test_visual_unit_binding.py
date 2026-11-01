import tempfile
import unittest
from pathlib import Path

from skill.scripts.aidd_review import visual_revision_binding


class VisualRevision(unittest.TestCase):
    def test_binding_tracks_only_declared_sources_and_validates_viewport(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / 'specs' / 's'
            spec.mkdir(parents=True)
            (root / 'screen.html').write_text('v1', encoding='utf-8')
            (root / 'asset.png').write_bytes(b'v1')
            revision = dict(screen_id='SCREEN-01', revision_id='v1', source='screen.html',
                            assets=['asset.png'], states=['empty'], viewports=['1280x720'])
            digest = visual_revision_binding(spec, revision)
            (root / 'other.html').write_text('v2', encoding='utf-8')
            self.assertEqual(digest, visual_revision_binding(spec, revision))
            (root / 'asset.png').write_bytes(b'v2')
            self.assertNotEqual(digest, visual_revision_binding(spec, revision))
            (root / 'asset.png').unlink()
            with self.assertRaises(ValueError):
                visual_revision_binding(spec, revision)
            revision['viewports'] = ['0x720']
            with self.assertRaises(ValueError):
                visual_revision_binding(spec, revision)


if __name__ == '__main__':
    unittest.main()
