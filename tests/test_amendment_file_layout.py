"""FR-980..983: filename compatibility cannot mutate legacy approval identity."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import os

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skill'/'scripts'))
import aidd_amendment_verify as amendment
import aidd_rules as rules


class AmendmentFileLayout(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='aidd-amend-layout-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.spec=self.root/'specs'/'example';self.spec.mkdir(parents=True)
        self.base='# Tasks\n\n| Task | Target file |\n|---|---|\n| T-01 | `lib/value.py` |\n'
        (self.spec/'tasks.md').write_text(self.base,encoding='utf-8')

    def write(self,name,body='- **Files to change:** `lib/value.py`\n'):
        p=self.spec/name;p.write_text(body,encoding='utf-8');return p

    def test_canonical_layout_unchanged(self):
        for name in ['tasks-amendment-06.md','tasks-amendment-6.md','tasks-amendment-006.md']:
            with self.subTest(name=name):
                p=self.write(name);self.assertEqual(amendment.amendment_file(self.spec,'06'),p);p.unlink()

    def test_legacy_reverse_names_resolve_without_writes(self):
        for name in ['amendment-06-tasks.md','amendment-6-tasks.md','amendment-006-tasks.md']:
            with self.subTest(name=name):
                p=self.write(name);before=sorted(self.spec.iterdir())
                self.assertEqual(amendment.amendment_file(self.spec,'06'),p)
                self.assertEqual(sorted(self.spec.iterdir()),before);p.unlink()

    def test_equal_candidates_prefer_canonical(self):
        reverse=self.write('amendment-06-tasks.md');canonical=self.write('tasks-amendment-06.md')
        self.assertEqual(amendment.amendment_file(self.spec,'06'),canonical)
        self.assertEqual(reverse.read_bytes(),canonical.read_bytes())

    def test_different_candidates_refuse_ambiguity(self):
        self.write('amendment-06-tasks.md','- **Files to change:** `lib/other.py`\n')
        self.write('tasks-amendment-06.md')
        with self.assertRaisesRegex(ValueError,'ambiguous|differ'):
            amendment.amendment_file(self.spec,'06')

    def test_missing_and_empty_declarations_refuse(self):
        self.assertIsNone(amendment.amendment_file(self.spec,'06'))
        p=self.write('amendment-06-tasks.md','# no changed files\n')
        fake=type('Reader',(),{'rules':rules})()
        with self.assertRaisesRegex(ValueError,'declares no file'):
            amendment.amendment_files(fake,self.spec,'06')
        self.assertTrue(p.is_file())

    def test_reverse_discovery_preserves_base_hash_and_no_new_batch(self):
        self.write('amendment-06-tasks.md')
        text=rules.with_batches(self.spec,self.base);before=rules.approval_hash(text)
        fake=type('Reader',(),{'rules':rules})()
        paths,p=amendment.amendment_files(fake,self.spec,'06')
        self.assertEqual(paths,['lib/value.py'])
        self.assertEqual(p.name,'amendment-06-tasks.md')
        self.assertEqual(before,rules.approval_hash(rules.with_batches(self.spec,self.base)))
        self.assertEqual(rules.tasks_batch_names(self.spec),[])
        self.assertEqual((self.spec/'tasks.md').read_text(encoding='utf-8'),self.base)

    def test_symlink_outside_spec_refuses(self):
        outside=self.root/'outside.md';outside.write_text('external',encoding='utf-8')
        target=self.spec/'tasks-amendment-06.md'
        try:target.symlink_to(outside)
        except OSError:
            # Exercise the containment check even on Windows without symlink privilege.
            target.touch()
            real_resolve=Path.resolve
            def resolve(path,*a,**kw):return outside if path==target else real_resolve(path,*a,**kw)
            with patch.object(Path,'resolve',resolve):
                with self.assertRaisesRegex(ValueError,'outside|escape|contained|link'):
                    amendment.amendment_file(self.spec,'06')
        else:
            with self.assertRaisesRegex(ValueError,'outside|escape|contained|link'):
                amendment.amendment_file(self.spec,'06')

    def test_opened_descriptor_must_match_the_validated_candidate(self):
        candidate=self.write('tasks-amendment-06.md')
        outside=self.root/'outside.md';outside.write_text('- **Files to change:** `private/other.py`\n',encoding='utf-8')
        original_open=os.open
        def swapped(path,flags,*args,**kwargs):
            return original_open(outside if Path(path)==candidate else path,flags,*args,**kwargs)
        with patch.object(amendment,'os',os,create=True),patch.object(os,'open',side_effect=swapped):
            with self.assertRaisesRegex(ValueError,'changed|candidate|stable'):
                amendment.amendment_file(self.spec,'06')

    def test_parser_uses_validated_bytes_without_a_path_reopen(self):
        candidate=self.write('tasks-amendment-06.md')
        real_read_text=Path.read_text
        def swapped(path,*args,**kwargs):
            if path==candidate:return '- **Files to change:** `private/other.py`\n'
            return real_read_text(path,*args,**kwargs)
        fake=type('Reader',(),{'rules':rules})()
        with patch.object(Path,'read_text',swapped):
            paths,_=amendment.amendment_files(fake,self.spec,'06')
        self.assertEqual(paths,['lib/value.py'])


from tests.test_verify_amendment import AmendBase


class ReverseLayoutDryRun(AmendBase):
    def test_reverse_only_cli_uses_root_verification_without_execution_or_events(self):
        spec=self.three_rows(amendment=None)
        (spec/'amendment-06-tasks.md').write_text('- **Files to change:** `lib/b.py`\n',encoding='utf-8')
        (spec/'amendment-06-spec.md').write_text('# Conflicting local spec\n\n## Verification\n| # | Command | Expected |\n|---|---|---|\n| INTRUDER | python must_never_run.py | exit 0 |\n',encoding='utf-8')
        before={str(p.relative_to(spec)):p.read_bytes() for p in spec.rglob('*') if p.is_file()}
        rc,out=self.verify('A','--amendment','06','--dry-run')
        self.assertEqual((rc,self.runs,self.events),(0,[],[]),out)
        self.assertIn('RUN    V-1',out);self.assertIn('RUN    V-2',out);self.assertIn('RUN    V-3',out)
        self.assertNotIn('INTRUDER',out);self.assertNotIn('must_never_run',out)
        self.assertIn('nothing was executed and nothing was recorded',out)
        self.assertEqual(before,{str(p.relative_to(spec)):p.read_bytes() for p in spec.rglob('*') if p.is_file()})


if __name__=='__main__':unittest.main()
