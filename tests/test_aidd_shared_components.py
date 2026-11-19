"""G8 exact registry exception must not become a directory or index-content bypass."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'skill' / 'scripts'))
import aidd_shared_components as shared
import aidd_readiness as readiness
import check_spec


class SharedRegistryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.base = self.root / 'specs' / 'example'
        self.base.mkdir(parents=True)
        self.write('specs/example/spec.md', '# Screens\nSCREEN-01 SCREEN-02\n')
        self.target = self.write('src/app/Shell.tsx', 'export function SharedShell(){ return <main/>; }\n')
        self.consumer = self.write('src/routes.tsx', "import {SharedShell} from './app/Shell';\nexport const routes = <SharedShell/>;\n")
        self.index = self.root / 'design-system' / 'components-index.md'
        self.row = ['COMP-001', 'SharedShell', 'src/app/Shell.tsx', 'specs/example', 'SCREEN-01, SCREEN-02', 'src/routes.tsx', '']
        self.register()
        self.plan = '| COMP-nnn | File/component | Pattern | Used by |\n|---|---|---|---|\n| COMP-001 | src/app/Shell.tsx | Slot | SCREEN-01, SCREEN-02 |\n'

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def register(self, rows=None):
        header = '| COMP-nnn | Name | File | First defined in (spec folder) | Used in (SCREEN-XX across all specs) | Consumers | Notes |\n|---|---|---|---|---|---|---|\n'
        self.write('design-system/components-index.md', header + ''.join('| ' + ' | '.join(row) + ' |\n' for row in (rows or [self.row])))

    def accepts(self):
        return shared.registered_shared('COMP-001', 'src/app/Shell.tsx', [self.index], self.root,
                                        shared.declared_screens(self.base, self.base))

    def test_exact_registry_two_screens_one_production_host_passes(self):
        self.assertTrue(self.accepts())
        self.assertEqual(check_spec.check_g8_shared_first_path(self.plan, [self.index], self.root,
                         shared.declared_screens(self.base, self.base)), [])

    def test_without_index_legacy_g8_is_unchanged(self):
        self.assertEqual(len(check_spec.check_g8_shared_first_path(self.plan)), 1)
        self.assertEqual(check_spec.check_g8_shared_first_path(self.plan.replace('src/app/', 'src/shared/components/')), [])

    def test_registered_file_does_not_allow_its_directory(self):
        sibling = self.plan.replace('Shell.tsx', 'Other.tsx')
        self.write('src/app/Other.tsx', 'export function Other(){}')
        self.assertEqual(len(check_spec.check_g8_shared_first_path(sibling, [self.index], self.root, {'SCREEN-01', 'SCREEN-02'})), 1)

    def test_missing_source_fails(self):
        self.target.unlink()
        self.assertFalse(self.accepts())

    def test_wrong_comp_namespace_fails(self):
        self.row[0] = 'COMP-001-F99'
        self.register()
        self.assertFalse(self.accepts())

    def test_duplicate_identifier_fails_even_if_rows_identical(self):
        self.register([self.row, self.row])
        self.assertFalse(self.accepts())

    def test_other_identifier_claiming_same_file_is_ambiguous(self):
        other = [*self.row]
        other[0] = 'COMP-002'
        self.register([self.row, other])
        self.assertFalse(self.accepts())

    def test_wrong_exact_file_not_matched_by_basename(self):
        self.write('src/other/Shell.tsx', self.target.read_text(encoding='utf-8'))
        self.row[2] = 'src/other/Shell.tsx'
        self.register()
        self.assertFalse(self.accepts())

    def test_index_path_escape_is_rejected(self):
        self.row[2] = 'src/app/../app/Shell.tsx'
        self.register()
        self.assertFalse(self.accepts())

    def test_one_screen_is_insufficient(self):
        self.row[4] = 'SCREEN-01'
        self.register()
        self.assertFalse(self.accepts())

    def test_duplicate_screen_is_not_two_screens(self):
        self.row[4] = 'SCREEN-01, SCREEN-01'
        self.register()
        self.assertFalse(self.accepts())

    def test_undeclared_screen_is_not_evidence(self):
        self.row[4] = 'SCREEN-01, SCREEN-99'
        self.register()
        self.assertFalse(self.accepts())

    def test_test_only_consumer_is_rejected(self):
        self.write('src/routes.test.tsx', self.consumer.read_text(encoding='utf-8'))
        self.row[5] = 'src/routes.test.tsx'
        self.register()
        self.assertFalse(self.accepts())

    def test_fixture_only_consumer_is_rejected(self):
        self.write('src/fixtures/routes.tsx', self.consumer.read_text(encoding='utf-8'))
        self.row[5] = 'src/fixtures/routes.tsx'
        self.register()
        self.assertFalse(self.accepts())

    def test_type_only_import_is_not_runtime_use(self):
        self.consumer.write_text("import type {SharedShell} from './app/Shell';\nconst fake = <SharedShell/>;", encoding='utf-8')
        self.assertFalse(self.accepts())

    def test_comment_and_template_cannot_fake_import_use(self):
        for text in ("/* import {SharedShell} from './app/Shell';\n<SharedShell/> */",
                     "const sample = `import {SharedShell} from './app/Shell';\n<SharedShell/>`; "):
            with self.subTest(text=text):
                self.consumer.write_text(text, encoding='utf-8')
                self.assertFalse(self.accepts())

    def test_string_jsx_is_not_runtime_use(self):
        self.consumer.write_text("import {SharedShell} from './app/Shell';\nconst fake = '<SharedShell/>';", encoding='utf-8')
        self.assertFalse(self.accepts())

    def test_import_without_jsx_use_fails(self):
        self.consumer.write_text("import {SharedShell} from './app/Shell';\nconst other = <Other/>;", encoding='utf-8')
        self.assertFalse(self.accepts())

    def test_jsx_shaped_regex_is_not_runtime_use(self):
        self.consumer.write_text("import {SharedShell} from './app/Shell';\nconst probe=/<SharedShell[ >]/;\nexport function Host(){return null;}", encoding='utf-8')
        self.assertFalse(self.accepts())

    def test_jsx_literal_pattern_sweep_is_not_runtime_use(self):
        probes = (
            "const probe = '<SharedShell />';",
            'const probe = "<SharedShell />";',
            "const probe = `<SharedShell />`;",
            "const probe = /<SharedShell[ >]/g;",
            r"const probe = /[\/]?<SharedShell[ >]/;",
            "// <SharedShell />\nconst probe = null;",
            "/* <SharedShell /> */ const probe = null;",
            'const probe = "\\\n<SharedShell />";',
        )
        for probe in probes:
            with self.subTest(probe=probe):
                self.consumer.write_text("import {SharedShell} from './app/Shell';\n" + probe + '\nexport function Host(){return null;}', encoding='utf-8')
                self.assertFalse(self.accepts())

    def test_import_export_jsx_masks_preserve_offsets_and_newlines(self):
        source = 'const sample = "\\\nimport {SharedShell} from \'./app/Shell\';";\nconst probe=/<SharedShell[ >]/;\n'
        masked = shared.code_text(source, mask_strings=True)
        self.assertEqual(len(masked), len(source))
        self.assertEqual([i for i, char in enumerate(masked) if char == '\n'],
                         [i for i, char in enumerate(source) if char == '\n'])
        self.assertNotIn('import', masked)
        self.assertNotIn('<SharedShell', masked)

    def test_real_jsx_after_division_and_comments_still_passes(self):
        self.consumer.write_text("import {SharedShell} from './app/Shell';\nconst n=4/2; /* preparatory arithmetic */\nexport const routes = <SharedShell/>;", encoding='utf-8')
        self.assertTrue(self.accepts())

    def test_wrong_export_name_fails(self):
        self.row[1] = 'DifferentName'
        self.register()
        self.assertFalse(self.accepts())

    def test_renamed_named_import_with_actual_jsx_passes(self):
        self.consumer.write_text("import {SharedShell as Layout} from './app/Shell';\nconst routes = <Layout/>;", encoding='utf-8')
        self.assertTrue(self.accepts())

    def test_default_import_cannot_use_a_named_only_export(self):
        self.consumer.write_text("import SharedShell from './app/Shell';\nconst routes = <SharedShell/>;", encoding='utf-8')
        self.assertFalse(self.accepts())

    def test_named_import_cannot_use_a_default_only_export(self):
        self.target.write_text('export default function SharedShell(){ return <main/>; }', encoding='utf-8')
        self.assertFalse(self.accepts())

    def test_default_export_and_renamed_default_import_pass(self):
        self.target.write_text('export default function SharedShell(){ return <main/>; }', encoding='utf-8')
        self.consumer.write_text("import Layout from './app/Shell';\nconst routes = <Layout/>;", encoding='utf-8')
        self.assertTrue(self.accepts())

    def test_explicit_default_export_of_declared_symbol_passes(self):
        self.target.write_text('function SharedShell(){ return <main/>; }\nexport default SharedShell;', encoding='utf-8')
        self.consumer.write_text("import Layout from './app/Shell';\nconst routes = <Layout/>;", encoding='utf-8')
        self.assertTrue(self.accepts())

    def test_export_shaped_string_is_not_an_export(self):
        self.target.write_text('const sample = "\\\nexport function SharedShell(){}";', encoding='utf-8')
        self.assertFalse(self.accepts())

    def test_import_shaped_string_is_not_an_import(self):
        self.consumer.write_text('const sample = "\\\nimport {SharedShell} from \'./app/Shell\';";\nconst routes = <SharedShell/>;', encoding='utf-8')
        self.assertFalse(self.accepts())

    def test_validated_tsconfig_alias_passes(self):
        self.write('tsconfig.json', json.dumps({'compilerOptions': {'baseUrl': '.', 'paths': {'@/*': ['src/*']}}}))
        self.consumer.write_text("import {SharedShell} from '@/app/Shell';\nconst routes = <SharedShell/>;", encoding='utf-8')
        self.assertTrue(self.accepts())

    def test_alias_is_not_guessed_without_config(self):
        self.consumer.write_text("import {SharedShell} from '@/app/Shell';\nconst routes = <SharedShell/>;", encoding='utf-8')
        self.assertFalse(self.accepts())

    def test_alias_configuration_not_basename_controls_resolution(self):
        self.write('tsconfig.json', json.dumps({'compilerOptions': {'paths': {'@/*': ['wrong/*']}}}))
        self.consumer.write_text("import {SharedShell} from '@/app/Shell';\nconst routes = <SharedShell/>;", encoding='utf-8')
        self.assertFalse(self.accepts())

    def test_inherited_alias_is_not_guessed(self):
        self.write('tsconfig.json', json.dumps({'extends': './unknown.json', 'compilerOptions': {'paths': {'@/*': ['src/*']}}}))
        self.consumer.write_text("import {SharedShell} from '@/app/Shell';\nconst routes = <SharedShell/>;", encoding='utf-8')
        self.assertFalse(self.accepts())

    def test_local_unit_index_is_not_project_registration(self):
        nested = self.write('specs/example/components-index.md', self.index.read_text(encoding='utf-8'))
        self.assertFalse(shared.registered_shared('COMP-001', 'src/app/Shell.tsx', [nested], self.root, {'SCREEN-01', 'SCREEN-02'}))

    def test_readiness_observes_consumer_source_and_alias_config(self):
        self.write('tsconfig.json', json.dumps({'compilerOptions': {'paths': {'@/*': ['src/*']}}}))
        scope = SimpleNamespace(root=self.root, base=self.base, directory=self.base, unit=None)
        before = readiness.snapshot(self.base, scope)
        for name in ('src/routes.tsx', 'src/app/Shell.tsx', 'tsconfig.json', 'design-system/components-index.md'):
            self.assertIn('shared-evidence/' + name, before)
        with self.consumer.open('a', encoding='utf-8') as stream:
            stream.write('\nChanged consumer.\n')
        after = readiness.snapshot(self.base, scope)
        self.assertNotEqual(before['shared-evidence/src/routes.tsx'], after['shared-evidence/src/routes.tsx'])
