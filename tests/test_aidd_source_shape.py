"""FR-970..975: structural evidence cannot invent runtime authority."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skill'/'scripts'))
import aidd_source_shape as shape


class SourceShape(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='aidd-shape-test-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def write(self,text,name='source.py'):
        p=self.root/name;p.write_text(text,encoding='utf-8');return p

    def findings(self,path,kind):
        return [f for f in shape.inspect_python(path)['findings'] if f['kind']==kind]

    def test_duplicate_final_stub_is_reported(self):
        p=self.write('def normalize(source):\n    return source\n\ndef normalize(source):\n    raise NotImplementedError("pending")\n')
        r=shape.inspect_python(p)
        self.assertEqual(r['status'],'findings')
        duplicate=self.findings(p,'duplicate_definition')
        self.assertEqual(len(duplicate),1)
        self.assertEqual((duplicate[0]['symbol'],duplicate[0]['previous_line'],duplicate[0]['line']),('normalize',1,4))
        self.assertEqual(len(self.findings(p,'stub')),1)

    def test_long_stub_is_not_implementation(self):
        p=self.write('# '+'comment '*100+'\nasync def fetch():\n    """contract"""\n    raise NotImplementedError\n')
        self.assertGreater(p.stat().st_size,40)
        self.assertEqual(self.findings(p,'stub')[0]['symbol'],'fetch')

    def test_docstring_only_is_stub(self):
        p=self.write('def only_documentation():\n    """No implementation."""\n')
        self.assertEqual(shape.inspect_python(p)['status'],'findings')
        self.assertEqual(self.findings(p,'stub')[0]['line'],1)

    def test_two_classes_same_method_are_distinct(self):
        p=self.write('class A:\n    def run(self):\n        return 1\nclass B:\n    def run(self):\n        return 2\n')
        self.assertEqual(shape.inspect_python(p)['status'],'clean')
        self.assertEqual(self.findings(p,'duplicate_definition'),[])

    def test_overload_then_implementation_is_allowed(self):
        p=self.write('from typing import overload\n@overload\ndef convert(x: int)->int: ...\n@overload\ndef convert(x: str)->str: ...\ndef convert(x):\n    return x\n')
        self.assertEqual(shape.inspect_python(p)['status'],'clean')
        self.assertEqual(self.findings(p,'duplicate_definition'),[])
        self.assertEqual(len(self.findings(p,'declaration')),2)

    def test_abstract_protocol_and_property_declarations_are_distinct(self):
        p=self.write('from abc import abstractmethod\nfrom typing import Protocol\nclass Contract(Protocol):\n    def save(self): ...\nclass Abstract:\n    @abstractmethod\n    def work(self): pass\nclass Model:\n    @property\n    def value(self): return 1\n    @value.setter\n    def value(self,v): self._v=v\n    @value.deleter\n    def value(self): del self._v\n')
        self.assertEqual(shape.inspect_python(p)['status'],'clean')
        self.assertEqual(len(self.findings(p,'declaration')),2)
        self.assertEqual(self.findings(p,'duplicate_definition'),[])

    def test_generic_protocol_is_a_declaration_not_a_stub(self):
        p=self.write('from typing import Protocol, TypeVar\nT=TypeVar("T")\nclass Port(Protocol[T]):\n    def read(self)->T: ...\n')
        self.assertEqual(shape.inspect_python(p)['status'],'clean')
        self.assertEqual(self.findings(p,'stub'),[])
        self.assertEqual(self.findings(p,'declaration')[0]['symbol'],'Port.read')

    def test_oversized_sources_are_unknown_without_reading_or_parsing(self):
        p=self.write('#'*(2*1024*1024+1))
        self.assertEqual(shape.inspect_python(p)['status'],'unknown')

    def test_non_regular_sources_are_rejected_before_opening(self):
        p=self.root/'directory.py';p.mkdir()
        with patch.object(shape.tokenize,'open',side_effect=AssertionError('must not read non-regular target')):
            self.assertEqual(shape.inspect_python(p)['status'],'unknown')

    def test_conditional_siblings_not_inferred_mutually_exclusive(self):
        p=self.write('if enabled:\n    def work(): return 1\n    def work(): return 2\nelse:\n    def work(): return 3\n')
        duplicates=self.findings(p,'duplicate_definition')
        self.assertEqual(len(duplicates),1)
        self.assertEqual((duplicates[0]['previous_line'],duplicates[0]['line']),(2,3))

    def test_unreadable_and_syntax_error_are_unknown(self):
        for p,kind in [(self.root/'missing.py','unreadable'),(self.write('def (broken syntax\n'),'parse_error')]:
            result=shape.inspect_python(p)
            self.assertEqual(result['status'],'unknown')
            self.assertEqual(result['findings'][0]['kind'],kind)

    def test_targets_are_not_imported(self):
        marker=self.root/'do-not-create'
        p=self.write('from pathlib import Path\nPath('+repr(str(marker))+').touch()\nraise RuntimeError("MUST_NOT_IMPORT")\n')
        results=shape.inspect_targets([p])
        self.assertEqual(results[0]['status'],'clean')
        self.assertFalse(marker.exists())

    def test_cli_codes_and_json(self):
        for body,expected in [('def f(): return 1\n',0),('def f(): pass\n',1),('def syntax(\n',2)]:
            p=self.write(body)
            r=subprocess.run([sys.executable,shape.__file__,'--files',str(p),'--json'],capture_output=True,text=True)
            self.assertEqual(r.returncode,expected,r.stderr)
            self.assertEqual(json.loads(r.stdout)[0]['path'],str(p))


class SourceShapeReadRace(unittest.TestCase):
    def _inspect_during_same_inode_mutation(self, rewrite):
        with tempfile.TemporaryDirectory(prefix='aidd-shape-read-race-') as temporary:
            path=Path(temporary)/'source.py'
            initial=b'def unfinished():\n    pass\n'
            path.write_bytes(initial)
            identity=lambda info:(info.st_dev,info.st_ino)
            initial_identity=identity(path.stat())
            real_fdopen=shape.os.fdopen
            mutations=[]

            def opened(descriptor,*args,**kwargs):
                stream=real_fdopen(descriptor,*args,**kwargs)
                class Reader:
                    def __enter__(reader):
                        stream.__enter__();return reader
                    def __exit__(reader,*exception):
                        return stream.__exit__(*exception)
                    def fileno(reader):return stream.fileno()
                    def read(reader,*read_args):
                        before=shape.os.fstat(stream.fileno())
                        self.assertEqual(identity(before),initial_identity)
                        replacement=(b'completed = True'+b' '*(len(initial)-len(b'completed = True\n'))+b'\n') if rewrite else b''
                        path.write_bytes(replacement)
                        if rewrite:
                            self.assertEqual(len(replacement),len(initial))
                            shape.os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns+2_000_000_000))
                        after=shape.os.fstat(stream.fileno())
                        self.assertEqual(identity(after),initial_identity)
                        self.assertEqual(identity(path.stat()),initial_identity)
                        mutations.append({'beforeSize':before.st_size,'afterSize':after.st_size})
                        return stream.read(*read_args)
                return Reader()

            with patch.object(shape.os,'fdopen',side_effect=opened):
                result=shape.inspect_python(path)
            self.assertEqual(len(mutations),1,'must mutate the real opened source descriptor')
            self.assertEqual(result['status'],'unknown',result)
            self.assertEqual([f['kind'] for f in result['findings']],['unreadable'],result)

    def test_same_inode_truncate_after_open_is_unknown(self):
        self._inspect_during_same_inode_mutation(rewrite=False)

    def test_same_inode_same_size_rewrite_after_open_is_unknown(self):
        self._inspect_during_same_inode_mutation(rewrite=True)




class PropertyAccessorDuplicates(unittest.TestCase):
    def _check_repeated_accessor(self, first, middle):
        bodies={'setter': ('self, value', 'self._value = value'),
                'deleter': ('self', 'del self._value')}
        lines=['class Model:', '    @property', '    def value(self):',
               '        return self._value']
        for kind in (first, middle, first):
            args, body=bodies[kind]
            lines.extend(['    @value.'+kind, '    def value('+args+'):',
                          '        '+body])
        with tempfile.TemporaryDirectory(prefix='aidd-property-accessors-') as directory:
            path=Path(directory)/'model.py'
            path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
            result=shape.inspect_python(path)
        self.assertEqual(result['status'],'findings')
        duplicates=[f for f in result['findings'] if f['kind']=='duplicate_definition']
        self.assertEqual(len(duplicates),1)
        self.assertEqual((duplicates[0]['symbol'],duplicates[0]['previous_line'],
                          duplicates[0]['line']),('Model.value',6,12))
        self.assertEqual([f for f in result['findings'] if f['kind']=='stub'],[])

    def test_repeated_setter_after_deleter_is_duplicate(self):
        self._check_repeated_accessor('setter','deleter')

    def test_repeated_deleter_after_setter_is_duplicate(self):
        self._check_repeated_accessor('deleter','setter')


if __name__=='__main__':unittest.main()
