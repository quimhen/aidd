import tempfile
import unittest
from pathlib import Path

from skill.scripts.aidd_review import visual_revision_binding


class VisualRevision(unittest.TestCase):
    def test_role_is_bound_in_v2_and_v1_is_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / 'specs' / 's'
            spec.mkdir(parents=True)
            (root / 'screen.html').write_text('visual', encoding='utf-8')
            v1 = dict(screen_id='SCREEN-01', revision_id='v1', source='screen.html',
                      assets=[], states=['empty'], viewports=['1280x720'])
            old = visual_revision_binding(spec, v1)
            self.assertEqual(old, 'a2fcc7e96945cc7233902410e2c67a2877790347f7bf647f4def64d20b6d2c52')
            v2 = {**v1, 'roles': ['admin']}
            admin = visual_revision_binding(spec, v2)
            self.assertNotEqual(old, admin)
            v2['roles'] = ['reviewer']
            self.assertNotEqual(admin, visual_revision_binding(spec, v2))
            self.assertEqual(old, visual_revision_binding(spec, v1))
            v2['roles'] = []
            with self.assertRaises(ValueError):
                visual_revision_binding(spec, v2)

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
