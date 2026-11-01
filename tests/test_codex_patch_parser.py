import sys
import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'hooks'))
from codex_patch import normalize_codex_patch, project_patch


class CodexPatchParserTests(unittest.TestCase):
    def event(self, text):
        return {'tool_name': 'apply_patch', 'tool_input': {'command': text},
                'cwd': '/project', 'session_id': 'session'}

    def test_all_operations_and_move_destinations(self):
        patch = ('*** Begin Patch\n*** Add File: ñ/a.py\n+x\n'
                 '*** Update File: old.py\n*** Move to: new.py\n@@\n-a\n+b\n'
                 '*** Delete File: z.py\n*** End Patch\n')
        result = normalize_codex_patch(self.event(patch))
        self.assertEqual([x['file_path'] for x in result['tool_input']['edits']],
                         ['ñ/a.py', 'old.py', 'new.py', 'z.py'])
        self.assertEqual(result['cwd'], '/project')
        self.assertEqual(result['session_id'], 'session')

    def test_malformed_or_ambiguous_patch_fails_closed(self):
        patches = ['', '*** Begin Patch\n*** Add File: a\n+x\n',
                   '*** Begin Patch\n*** Rename File: a\n*** End Patch\n',
                   '*** Begin Patch\n*** Add File: a\n+x\n*** Add File: a\n+y\n*** End Patch\n',
                   '*** Begin Patch\n*** Move to: a\n*** End Patch\n',
                   '*** Begin Patch\n*** Add File: a\x00b\n+x\n*** End Patch\n']
        for patch in patches:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                normalize_codex_patch(self.event(patch))

    def test_context_cannot_create_a_header(self):
        patch = ('*** Begin Patch\n*** Update File: a\n@@\n'
                 ' *** Add File: not-a-header\n+ok\n*** End Patch\n')
        self.assertEqual([x['file_path'] for x in normalize_codex_patch(self.event(patch))
                          ['tool_input']['edits']], ['a'])


class CodexPatchProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def update(self, body, name='a.txt'):
        return f'*** Begin Patch\n*** Update File: {name}\n@@\n{body}*** End Patch\n'

    def test_add_and_unique_hunk(self):
        (self.root / 'a.txt').write_bytes(b'one\ntwo\nthree\n')
        patch = ('*** Begin Patch\n*** Add File: new.txt\n+new\n'
                 '*** Update File: a.txt\n@@\n two\n-three\n+third\n*** End Patch\n')
        targets = project_patch(patch, str(self.root))
        self.assertEqual(targets[0].prospective, 'new\n')
        self.assertIsNone(targets[0].original)
        self.assertEqual(targets[1].original, 'one\ntwo\nthree\n')
        self.assertEqual(targets[1].prospective, 'one\ntwo\nthird\n')
        self.assertEqual((self.root / 'a.txt').read_bytes(), b'one\ntwo\nthree\n')
        self.assertFalse((self.root / 'new.txt').exists())

    def test_unsupported_grammar_and_ambiguous_context(self):
        (self.root / 'a.txt').write_bytes(b'a\na\n')
        commands = [self.update('-a\n+b\n'), self.update('+b\n'),
                    self.update('-missing\n+b\n'),
                    self.update('-a\n+b\n@@\n-a\n+c\n'),
                    self.update('-a\n+b\n*** End of File\n'),
                    self.update('-a\n+é\n'),
                    '*** Begin Patch\n*** Delete File: a.txt\n*** End Patch\n',
                    '*** Begin Patch\n*** Add File: ../escape\n+x\n*** End Patch\n',
                    '*** Begin Patch\r\n*** Add File: new\r\n+x\r\n*** End Patch\r\n']
        for command in commands:
            with self.subTest(command=command), self.assertRaises(ValueError):
                project_patch(command, str(self.root))

    def test_non_ascii_crlf_and_missing_newline_originals(self):
        for content in (b'a\r\n', b'a', 'é\n'.encode(), b''):
            (self.root / 'a.txt').write_bytes(content)
            with self.subTest(content=content), self.assertRaises(ValueError):
                project_patch(self.update('-a\n+b\n'), str(self.root))

    def test_aliases_and_existing_add_rejected(self):
        target = self.root / 'a.txt'
        target.write_bytes(b'a\n')
        alias = self.root / 'alias.txt'
        try:
            alias.symlink_to(target)
        except OSError:
            os.link(target, alias)
        with self.assertRaises(ValueError):
            project_patch(self.update('-a\n+b\n', 'alias.txt'), str(self.root))
        with self.assertRaises(ValueError):
            project_patch('*** Begin Patch\n*** Add File: a.txt\n+x\n*** End Patch\n', str(self.root))

    def test_hardlink_source_rejected(self):
        target = self.root / 'a.txt'
        target.write_bytes(b'a\n')
        os.link(target, self.root / 'hardlink.txt')
        with self.assertRaises(ValueError):
            project_patch(self.update('-a\n+b\n'), str(self.root))

    def test_changed_original_fails_closed(self):
        (self.root / 'a.txt').write_bytes(b'a\n')
        with patch.object(Path, 'read_bytes', side_effect=[b'a\n', b'b\n']):
            with self.assertRaises(ValueError):
                project_patch(self.update('-a\n+b\n'), str(self.root))

    def test_duplicate_and_too_many_targets_fail(self):
        for headers in (['x', 'x'], [f'f{i}' for i in range(101)]):
            command = '*** Begin Patch\n' + ''.join(f'*** Add File: {name}\n+x\n' for name in headers) + '*** End Patch\n'
            with self.subTest(count=len(headers)), self.assertRaises(ValueError):
                project_patch(command, str(self.root))

    def test_control_characters_rejected(self):
        with self.assertRaises(ValueError):
            project_patch('*** Begin Patch\n*** Add File: x\n+\v\n*** End Patch\n', str(self.root))

    def test_oversized_patch_rejected(self):
        command = '*** Begin Patch\n*** Add File: x\n+' + ('a' * (4 * 1024 * 1024)) + '\n*** End Patch\n'
        with self.assertRaises(ValueError):
            project_patch(command, str(self.root))
