"""Manifest selection is deterministic and never executes collected tests."""
import unittest


class TestCoverageManifest(unittest.TestCase):
    def build(self, found, selected):
        from tests.coverage_manifest import build_manifest
        return build_manifest(found, selected)

    def test_complete_sorted(self):
        self.assertEqual(self.build(['tests.test_a.C.test_b', 'test_a.C.test_a'],
                                    ['test_a.C.test_a', 'test_a.C.test_b']),
                         b'test_a.C.test_a\ntest_a.C.test_b\n')

    def test_missing_fails(self):
        with self.assertRaises(ValueError):
            self.build(['test_a.C.test_a'], ['test_a.C.test_b'])

    def test_duplicate_fails(self):
        with self.assertRaises(ValueError):
            self.build(['test_a.C.test_a', 'tests.test_a.C.test_a'], ['test_a.C.test_a'])

    def test_collection_error_fails(self):
        with self.assertRaises(ValueError):
            self.build(['unittest.loader._FailedTest.test_a'], ['test_a.C.test_a'])

    def test_no_test_execution(self):
        from tests.coverage_manifest import suite_ids
        class Case(unittest.TestCase):
            def test_not_called(self):
                raise AssertionError('executed')
        self.assertEqual(suite_ids(unittest.TestSuite([Case('test_not_called')])),
                         [Case('test_not_called').id()])

    def test_added_or_renamed_id_fails(self):
        for found in (['test_a.C.test_a', 'test_a.C.test_new'], ['test_a.C.test_renamed']):
            with self.subTest(found=found), self.assertRaises(ValueError):
                self.build(found, ['test_a.C.test_a'])

    def test_check_requires_matching_manifest(self):
        from tests.coverage_manifest import check_bytes
        self.assertTrue(check_bytes(b'a\n', b'a\n'))
        self.assertFalse(check_bytes(b'a\n', b'b\n'))
