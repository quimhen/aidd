"""FR-970..975: explicit-target Python structure, never runtime correctness."""
import argparse
import ast
import json
import io
import os
from pathlib import Path
import stat
import tokenize

MAX_READ=2*1024*1024


def _name(node):
    if isinstance(node,ast.Name):return node.id
    if isinstance(node,ast.Attribute):return _name(node.value)+'.'+node.attr
    if isinstance(node,ast.Subscript):return _name(node.value)
    return ''


def _finding(kind,symbol,line,previous=None):
    return {'kind':kind,'symbol':symbol,'line':line,'previous_line':previous}


def _decorated(node,name):
    return any(_name(d).rsplit('.',1)[-1]==name for d in node.decorator_list)


def _stub(node):
    body=list(node.body)
    if body and isinstance(body[0],ast.Expr) and isinstance(body[0].value,ast.Constant) and isinstance(body[0].value.value,str):
        body=body[1:]
    if not body:return True
    if len(body)!=1:return False
    item=body[0]
    if isinstance(item,ast.Pass):return True
    if isinstance(item,ast.Expr) and isinstance(item.value,ast.Constant) and item.value.value is Ellipsis:return True
    if isinstance(item,ast.Raise):
        exc=item.exc.func if isinstance(item.exc,ast.Call) else item.exc
        return _name(exc) in ('NotImplementedError','builtins.NotImplementedError')
    return False


def _scan_body(body,scope='',protocol=False):
    findings=[];seen={};properties={}
    for node in body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            symbol=(scope+'.' if scope else '')+node.name
            function=isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))
            overload=function and _decorated(node,'overload')
            prior=seen.get(node.name)
            accessor=next((d.attr for d in node.decorator_list if isinstance(d,ast.Attribute)
                and isinstance(d.value,ast.Name) and d.value.id==node.name
                and d.attr in ('setter','deleter')),None) if function else None
            getter=function and _decorated(node,'property')
            property_lines=properties.get(node.name,{})
            allowed=prior and ((prior['overload'] and function)
                or (accessor and property_lines and accessor not in property_lines))
            if prior and not allowed:
                previous=property_lines.get('getter' if getter else accessor,prior['line'])
                findings.append(_finding('duplicate_definition',symbol,node.lineno,previous))
            seen[node.name]={'line':node.lineno,'overload':overload}
            if getter:properties[node.name]={'getter':node.lineno}
            elif accessor and property_lines:property_lines[accessor]=node.lineno
            else:properties.pop(node.name,None)
            if function:
                declaration=overload or protocol or _decorated(node,'abstractmethod')
                if declaration:findings.append(_finding('declaration',symbol,node.lineno))
                elif _stub(node):findings.append(_finding('stub',symbol,node.lineno))
                findings.extend(_scan_body(node.body,symbol))
            else:
                child_protocol=any(_name(b).rsplit('.',1)[-1]=='Protocol' for b in node.bases)
                findings.extend(_scan_body(node.body,symbol,child_protocol))
        else:
            # Branch bodies are inspected independently. No execution/exclusivity is inferred.
            for _,value in ast.iter_fields(node):
                if isinstance(value,list) and value and all(isinstance(n,ast.AST) for n in value):
                    findings.extend(_scan_body(value,scope,protocol))
    return findings


def _read_source(path):
    before=path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size>MAX_READ:
        raise ValueError('Unsupported source target')
    flags=os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NONBLOCK',0)|getattr(os,'O_NOFOLLOW',0)
    descriptor=os.open(path,flags)
    with os.fdopen(descriptor,'rb') as stream:
        current=os.fstat(stream.fileno())
        signature=lambda info:(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
        if not stat.S_ISREG(current.st_mode) or (current.st_dev,current.st_ino)!=(before.st_dev,before.st_ino):
            raise ValueError('Source target changed')
        raw=stream.read(MAX_READ+1)
        if signature(os.fstat(stream.fileno()))!=signature(current):
            raise ValueError('Source target changed during read')
    if len(raw)>MAX_READ:raise ValueError('Source exceeds size budget')
    encoding,_=tokenize.detect_encoding(io.BytesIO(raw).readline)
    return raw.decode(encoding)


def inspect_python(path: Path) -> dict:
    path=Path(path);result={'path':str(path),'status':'unknown','findings':[]}
    try:
        source=_read_source(path)
    except (OSError,UnicodeError,SyntaxError,LookupError,ValueError):
        result['findings']=[_finding('unreadable','',0)];return result
    try:tree=ast.parse(source,filename=str(path))
    except (SyntaxError,ValueError,RecursionError) as error:
        result['findings']=[_finding('parse_error','',getattr(error,'lineno',None) or 0)];return result
    try:result['findings']=_scan_body(tree.body)
    except RecursionError:
        result['findings']=[_finding('parse_error','',0)];return result
    result['status']='findings' if any(f['kind'] in ('stub','duplicate_definition') for f in result['findings']) else 'clean'
    return result


def inspect_targets(paths: list[Path]) -> list[dict]:
    return [inspect_python(Path(p)) if Path(p).suffix.lower()=='.py' else
        {'path':str(p),'status':'unknown','findings':[],'reason':'unsupported_language'} for p in paths]


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--files',nargs='+',required=True,type=Path)
    parser.add_argument('--json',action='store_true')
    args=parser.parse_args(argv);results=inspect_targets(args.files)
    if args.json:print(json.dumps(results,ensure_ascii=True))
    else:
        for result in results:
            print(f'{result["path"]}: {result["status"]} ({len(result["findings"])} structural item(s)); no runtime verdict')
            for f in result['findings']:
                print(f'  {f["line"]}: {f["kind"]} {f["symbol"]}')
    return 2 if any(r['status']=='unknown' for r in results) else 1 if any(r['status']=='findings' for r in results) else 0


if __name__ == '__main__':
    raise SystemExit(main())
