#!/usr/bin/env python3
"""aidd code graph — the built-in `code` graph of a project's Python (stdlib `ast`, no LLM, no third-party tool).

Spec 004 amendment 2026-10-24 (aidd:FR-014, aidd:FR-015, aidd:FR-023, aidd:FR-024, aidd:T-12).

  nodes   FILE (sha = git blob hash of the WORKING-TREE content, parsed), FUNC (id `rel::qual.name`, lineno,
          rule_ids, markers, ext, ext_in_loop), CLASS, SINK (sink_kind file | spawn | unresolved)
  edges   defines, imports, calls (+ambiguous, +in_loop when true), reads (+path when literal), spawns (+argv0
          when literal), implements (FUNC/FILE -> plain code id such as `FR-205`, from `aidd:<CODE>` markers)

Ambiguity policy: a call to a builtin, to a stdlib/external module, or to a well-known container/str/path/io
method name (EXT_METHODS, `assert*`) on a receiver that is not resolved in the project is no edge and no SINK:
it is recorded in the caller's sorted `ext` list (`ext_in_loop` lists those also called inside a loop). An
unknown-receiver method call with at most MAX_CANDIDATES project candidates keeps one ambiguous edge per
candidate; with more, ONE ambiguous edge to `sink:unresolved:<name>`. Nothing is dropped silently.

Incremental: per-file facts live in the sidecar `<out>.cache.json` (keyed by file sha, never part of a
snapshot). A FILE whose sha equals the cached one (same SCHEMA_VERSION and EXTRACTOR_VERSION) is not re-parsed;
the global call linking is recomputed on every build. A missing or unreadable sidecar means a full re-parse.
Never stat/mtime. A file that fails to parse yields a warning; the rest of the graph survives.

Usage:
    python code_graph.py [--root DIR] [--out FILE] [--globs G1,G2] [--full] [--quiet]
Prints `code graph: N files, re-parsed P, reused R, warnings W`. Exit 0 on success (even with warnings),
1 when the graph cannot be written, 2 on usage error. Stdlib only.
"""
import argparse
import ast
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
import tokenize
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

GRAPH_REL = '.aidd/graphs/code.json'
CACHE_SUFFIX = '.cache.json'
SCHEMA_VERSION = 1
EXTRACTOR_VERSION = 3
EMPTY_BLOB = 'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391'
MAX_CANDIDATES = 3
# aidd:FR-014 default globs: the AIDD repo's own Python; `**/*.py` minus vendor dirs anywhere else
DEFAULT_GLOBS = ('skill/**', 'aidd/**', 'adapters/**', 'tests/**')
GENERIC_GLOBS = ('**/*.py',)
SKIP_DIRS = frozenset({'.git', '.hg', '.svn', 'node_modules', 'venv', '.venv', 'env', '.env', '__pycache__',
                       'site-packages', 'dist', 'build', '.tox', '.nox', '.eggs', '.mypy_cache', '.pytest_cache',
                       '.ruff_cache', 'vendor', 'third_party', 'graphify-out'})
SKIP_TOP = frozenset({'.aidd'})
# aidd:FR-014 reads: open, read_text, read_bytes (last name segment); json.load is a read with no path
READ_FUNCS = ('open', 'read_text', 'read_bytes')
READ_NO_PATH = ('json.load',)
NOT_READ_RECEIVERS = frozenset({'webbrowser'})
SPAWN_FUNCS = ('subprocess.run', 'subprocess.Popen', 'subprocess.call', 'subprocess.check_output',
               'subprocess.check_call', 'os.system', 'os.popen')
MARKER_RE = re.compile(r'aidd:([A-Za-z]+-\d+(?:-F\d+)?)\b')
RULE_RE = re.compile(r'(?<![\w-])(R\d{1,3})\b')
# Fixed name lists (never computed per run): builtins and well-known exceptions called by simple name ...
EXT_BUILTINS = frozenset("""
abs aiter all anext any ascii bin bool breakpoint bytearray bytes callable chr classmethod compile complex
delattr dict dir divmod enumerate eval exec filter float format frozenset getattr globals hasattr hash help
hex id input int isinstance issubclass iter len list locals map max memoryview min next object oct open ord
pow print property range repr reversed round set setattr slice sorted staticmethod str sum super tuple type
vars zip __import__
BaseException Exception ArithmeticError AssertionError AttributeError BlockingIOError BrokenPipeError
ConnectionError EOFError FileExistsError FileNotFoundError ImportError IndexError InterruptedError
IsADirectoryError KeyError KeyboardInterrupt LookupError MemoryError ModuleNotFoundError NameError
NotADirectoryError NotImplementedError OSError OverflowError PermissionError ProcessLookupError
RecursionError ReferenceError RuntimeError StopIteration SyntaxError SystemExit TimeoutError TypeError
UnboundLocalError UnicodeDecodeError UnicodeEncodeError UnicodeError ValueError ZeroDivisionError
Warning DeprecationWarning UserWarning RuntimeWarning
""".split())
# ... and container / str / bytes / path / io / re / logging / argparse / threading / unittest method names
EXT_METHODS = frozenset("""
capitalize casefold center count encode endswith expandtabs find format format_map index isalnum isalpha
isascii isdecimal isdigit isidentifier islower isnumeric isprintable isspace istitle isupper join ljust lower
lstrip maketrans partition removeprefix removesuffix replace rfind rindex rjust rpartition rsplit rstrip split
splitlines startswith strip swapcase title translate upper zfill decode hex fromhex
append clear copy extend insert pop remove reverse sort
fromkeys get items keys popitem setdefault update values most_common elements subtract appendleft popleft
add difference difference_update discard intersection intersection_update isdisjoint issubset issuperset
symmetric_difference union
read readline readlines write writelines flush close seek tell fileno truncate readable writable getvalue
exists is_file is_dir is_symlink mkdir rmdir iterdir glob rglob resolve relative_to with_name with_suffix
with_stem joinpath unlink rename touch stat lstat as_posix as_uri is_absolute absolute expanduser samefile
write_text write_bytes match search fullmatch findall finditer sub subn group groups groupdict span start end
escape put get_nowait put_nowait task_done acquire release wait notify notify_all is_set is_alive
communicate poll kill terminate send_signal
isoformat strftime strptime timestamp total_seconds astimezone date time weekday hexdigest digest
add_argument add_argument_group add_parser add_subparsers add_mutually_exclusive_group parse_args
parse_known_args print_help print_usage set_defaults error exit
debug info warning exception critical log setLevel addHandler getLogger
subTest skipTest fail addCleanup enterContext setUp tearDown setUpClass tearDownClass run_until_complete
dumps loads dump load reconfigure
""".split())
GIT_TIMEOUT = 30
SHA_RE = re.compile(r'^[0-9a-f]{40}([0-9a-f]{24})?$')
_CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def _is_ext_method(name):
    return name in EXT_METHODS or name.startswith('assert')


# ---------------------------------------------------------------------------------------------------- files

def default_globs(root):
    root = Path(root)
    if (root / 'skill' / 'SKILL.md').is_file() and (root / 'aidd' / 'cli.py').is_file():
        return list(DEFAULT_GLOBS)
    return list(GENERIC_GLOBS)


def _glob_re(pattern):
    p = pattern.replace('\\', '/').strip()
    if p.startswith('./'):
        p = p[2:]
    out, i = [], 0
    while i < len(p):
        if p.startswith('**/', i):
            out.append('(?:.*/)?')
            i += 3
        elif p.startswith('**', i):
            out.append('.*')
            i += 2
        elif p[i] == '*':
            out.append('[^/]*')
            i += 1
        elif p[i] == '?':
            out.append('[^/]')
            i += 1
        else:
            out.append(re.escape(p[i]))
            i += 1
    return re.compile('^' + ''.join(out) + '$', re.I if os.name == 'nt' else 0)


def _git(root, args, data=None):
    """stdout bytes of a git command, or None (git missing, not a repo, timeout, non-zero exit)."""
    try:
        env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', LC_ALL='C')
        r = subprocess.run(['git'] + list(args), cwd=str(root), env=env, input=data,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=GIT_TIMEOUT,
                           creationflags=_CREATE_NO_WINDOW)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _keep(rel, rxs):
    if not rel.endswith('.py') or '\n' in rel:
        return False
    parts = rel.split('/')
    if parts[0] in SKIP_TOP or any(s in SKIP_DIRS for s in parts[:-1]):
        return False
    return any(rx.match(rel) for rx in rxs)


def list_files(root, globs):
    """Sorted relative ('/') paths of the Python files under `root` matching `globs`: `git ls-files -c -o
    --exclude-standard` (honours .gitignore), falling back to os.walk with SKIP_DIRS."""
    root = Path(root)
    rxs = [_glob_re(g) for g in (globs or default_globs(root)) if g and g.strip()]
    found = set()
    raw = _git(root, ['ls-files', '-c', '-o', '--exclude-standard', '-z'])
    if raw is not None:
        for rel in raw.decode('utf-8', errors='surrogateescape').split('\0'):
            rel = rel.replace('\\', '/')
            if rel and _keep(rel, rxs) and os.path.isfile(os.path.join(str(root), rel)):
                found.add(rel)
        return sorted(found)
    base = str(root)
    for cur, dirs, files in os.walk(base):
        relcur = os.path.relpath(cur, base).replace('\\', '/')
        relcur = '' if relcur == '.' else relcur
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not (not relcur and d in SKIP_TOP))
        for f in files:
            rel = (relcur + '/' + f) if relcur else f
            if _keep(rel, rxs):
                found.add(rel)
    return sorted(found)


def _blob_sha(data):
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def file_shas(root, rels):
    """aidd:FR-023 {rel: git blob sha of the WORKING-TREE content}. One `git hash-object --stdin-paths`;
    pure-Python `sha1(b"blob %d\\0" + data)` when git is unavailable or answers short. Never stat/mtime.
    A file that cannot be read is left out."""
    rels = [r for r in rels if '\n' not in r]
    if not rels:
        return {}
    out = _git(root, ['hash-object', '--stdin-paths'],
               data=('\n'.join(rels) + '\n').encode('utf-8', errors='surrogateescape'))
    if out is not None:
        shas = out.decode('ascii', errors='replace').split()
        if len(shas) == len(rels) and all(SHA_RE.match(s) for s in shas):
            return dict(zip(rels, shas))
    res = {}
    for rel in rels:
        try:
            res[rel] = _blob_sha((Path(root) / rel).read_bytes())
        except OSError:
            continue
    return res


# ---------------------------------------------------------------------------------------------------- parse

def _dotted(n):
    """'a.b.c' for a Name/Attribute chain; '?.attr' when the receiver is not a plain name chain."""
    if isinstance(n, ast.Name):
        return n.id
    if isinstance(n, ast.Attribute):
        inner = _dotted(n.value)
        if inner is None or inner.startswith('?'):
            return '?.' + n.attr
        return inner + '.' + n.attr
    return None


def _str_const(n):
    return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None


def _argv0(n):
    s = _str_const(n)
    if s is not None:
        s = s.strip().split()
        return s[0] if s else None
    if isinstance(n, (ast.List, ast.Tuple)) and n.elts:
        return _argv0(n.elts[0])
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
        return _argv0(n.left)
    if _dotted(n) == 'sys.executable':
        return 'python'
    return None


def _norm_argv0(s):
    s = os.path.basename(s.replace('\\', '/').strip('"\''))
    return s[:-4] if s.lower().endswith('.exe') else s


def _codes(text):
    if not text or ('aidd:' not in text and 'R' not in text):
        return [], []
    markers = sorted({m.upper() for m in MARKER_RE.findall(text)})
    rules = sorted({r.upper() for r in RULE_RE.findall(text)})
    return markers, rules


def _sink(kind, label):
    return {'id': 'sink:%s:%s' % (kind, label), 'type': 'SINK', 'label': label, 'source_file': '',
            'source_location': '', 'sink_kind': kind}


_LEAF_BASES = (ast.expr_context, ast.operator, ast.unaryop, ast.cmpop, ast.boolop)
LEAF_TYPES = frozenset([c for c in vars(ast).values() if isinstance(c, type) and issubclass(c, _LEAF_BASES)]
                       + [ast.Name, ast.alias, ast.Pass, ast.Break, ast.Continue, ast.Global, ast.Nonlocal])


class _Visitor:
    """One pass over the tree (own dispatch, leaves skipped): defs, calls, imports and string spans."""

    def __init__(self, rel):
        self.rel, self.imap = rel, {}
        self._disp = {ast.FunctionDef: self.visit_FunctionDef, ast.AsyncFunctionDef: self.visit_FunctionDef,
                      ast.ClassDef: self.visit_ClassDef, ast.For: self.visit_For, ast.AsyncFor: self.visit_For,
                      ast.While: self.visit_While, ast.ListComp: self._comp, ast.SetComp: self._comp,
                      ast.GeneratorExp: self._comp, ast.DictComp: self._comp, ast.Call: self.visit_Call,
                      ast.Constant: self.visit_Constant, ast.JoinedStr: self.visit_JoinedStr,
                      ast.Import: self.visit_Import, ast.ImportFrom: self.visit_ImportFrom}
        self.nodes, self.edges = [], []
        self.owner = [rel]           # FUNC id (or the FILE) that a call is attributed to
        self.parent = [(rel, '')]    # (node id, qual) for `defines`
        self.loop = [0]
        self.ranges = []             # (start, end, func id) for comment attribution
        self.spans = []              # (line, col, end line, end col) of string literals, to tell '#' apart

    def visit(self, n):
        m = self._disp.get(type(n))
        if m is not None:
            m(n)
        else:
            self.generic_visit(n)

    def generic_visit(self, n):
        for f in n._fields:
            v = getattr(n, f, None)
            if type(v) is list:
                for x in v:
                    if isinstance(x, ast.AST) and type(x) not in LEAF_TYPES:
                        self.visit(x)
            elif isinstance(v, ast.AST) and type(v) not in LEAF_TYPES:
                self.visit(v)

    def visit_Import(self, n):
        m = self.imap
        for a in n.names:
            if a.asname:
                m[a.asname] = (a.name, '', 0)
            else:
                head = a.name.split('.')[0]
                m.setdefault(head, (head, '', 0))
                if a.name != head:
                    m[a.name] = (a.name, '', 0)

    def visit_ImportFrom(self, n):
        for a in n.names:
            if a.name != '*':
                self.imap[a.asname or a.name] = (n.module or '', a.name, n.level or 0)

    def _canon(self, dotted):
        if not dotted or dotted.startswith('?'):
            return dotted
        parts = dotted.split('.')
        for i in range(len(parts), 0, -1):
            key = '.'.join(parts[:i])
            if key in self.imap:
                mod, name, level = self.imap[key]
                head = '.'.join(x for x in (mod, name) if x) if level == 0 else key
                return '.'.join([head] + parts[i:])
        return dotted

    def _def(self, n, typ):
        pid, pqual = self.parent[-1]
        qual = (pqual + '.' + n.name) if pqual else n.name
        nid = '%s::%s' % (self.rel, qual)
        node = {'id': nid, 'type': typ, 'label': qual, 'source_file': self.rel,
                'source_location': '%s:%d' % (self.rel, n.lineno), 'lineno': n.lineno}
        doc = ast.get_docstring(n, clean=False)
        if typ == 'FUNC':
            node['markers'], node['rule_ids'] = _codes(doc)
            start = min([n.lineno] + [d.lineno for d in n.decorator_list])
            self.ranges.append((start, getattr(n, 'end_lineno', None) or n.lineno, nid))
        else:
            node['_doc'] = doc or ''
            bases = sorted({d for d in (_dotted(b) for b in n.bases) if d and not d.startswith('?')})
            if bases:
                node['bases'] = bases   # resolved at link time: `self.m()` follows project base classes
        self.nodes.append(node)
        self.edges.append({'source': pid, 'target': nid, 'relation': 'defines'})
        return nid, qual

    def _visit_def(self, n, typ):
        for d in n.decorator_list:
            self.visit(d)
        if typ == 'FUNC':
            for d in list(n.args.defaults) + [x for x in n.args.kw_defaults if x is not None]:
                self.visit(d)
        else:
            for b in list(n.bases) + [k.value for k in n.keywords]:
                self.visit(b)
        nid, qual = self._def(n, typ)
        self.parent.append((nid, qual))
        if typ == 'FUNC':
            self.owner.append(nid)
            self.loop.append(0)
        for stmt in n.body:
            self.visit(stmt)
        if typ == 'FUNC':
            self.owner.pop()
            self.loop.pop()
        self.parent.pop()

    def visit_FunctionDef(self, n):
        self._visit_def(n, 'FUNC')

    def visit_ClassDef(self, n):
        self._visit_def(n, 'CLASS')

    def _in_loop(self, nodes):
        self.loop[-1] += 1
        for x in nodes:
            self.visit(x)
        self.loop[-1] -= 1

    def visit_For(self, n):
        self.visit(n.target)
        self.visit(n.iter)
        self._in_loop(list(n.body) + list(n.orelse))

    def visit_While(self, n):
        self._in_loop([n.test] + list(n.body) + list(n.orelse))

    def _comp(self, n):
        self.loop[-1] += 1
        self.generic_visit(n)
        self.loop[-1] -= 1

    def _span(self, n):
        end = getattr(n, 'end_lineno', None)
        if end is not None:
            self.spans.append((n.lineno, n.col_offset, end, n.end_col_offset))

    def visit_Constant(self, n):
        if isinstance(n.value, (str, bytes)):
            self._span(n)

    def visit_JoinedStr(self, n):
        self._span(n)
        self.generic_visit(n)

    def visit_Call(self, n):
        owner, in_loop = self.owner[-1], self.loop[-1] > 0
        dotted = _dotted(n.func)
        canon = self._canon(dotted)
        last = (dotted or '').split('.')[-1]
        if canon in SPAWN_FUNCS:                                   # aidd:FR-014 spawns -> SINK spawn
            first = n.args[0] if n.args else next((k.value for k in n.keywords if k.arg == 'args'), None)
            a0 = _argv0(first) if first is not None else None
            a0 = _norm_argv0(a0) if a0 else None
            sink = _sink('spawn', a0 or '?')
            self.nodes.append(sink)
            e = {'source': owner, 'target': sink['id'], 'relation': 'spawns'}
            if a0:
                e['argv0'] = a0
            if in_loop:
                e['in_loop'] = True
            self.edges.append(e)
        elif canon in READ_NO_PATH or (dotted and last in READ_FUNCS and
                                        dotted.split('.')[0] not in NOT_READ_RECEIVERS):
            path = None                                            # aidd:FR-014 reads -> SINK file
            if canon not in READ_NO_PATH:
                if dotted in ('open', 'io.open', 'codecs.open', 'builtins.open') and n.args:
                    path = _str_const(n.args[0])
                elif isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Call) \
                        and n.func.value.args:
                    path = _str_const(n.func.value.args[0])
            sink = _sink('file', path.replace('\\', '/') if path else '*')
            self.nodes.append(sink)
            e = {'source': owner, 'target': sink['id'], 'relation': 'reads'}
            if path:
                e['path'] = path.replace('\\', '/')
            if in_loop:
                e['in_loop'] = True
            self.edges.append(e)
        else:  # never dropped: a callee that is not a name chain (`handlers[k]()`) is kept as '?'
            self.edges.append({'source': owner, 'target': '', 'relation': 'calls', 'callee': dotted or '?',
                               'in_loop': in_loop})
        self.generic_visit(n)


def _comments_tokenize(text):
    """[(line, comment text)] via tokenize; only used when `ast` failed. Never raises."""
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                out.append((tok.start[0], tok.string))
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        pass
    return out


def _comments_fast(text, spans):
    """[(line, comment text)] for the lines that may carry a marker or rule id; a '#' that falls inside a
    string literal span (from the ast already built) is not a comment. No second tokenizer pass."""
    out, cand = [], []
    for i, line in enumerate(text.splitlines(), 1):
        if '#' in line and ('aidd:' in line or RULE_RE.search(line)):
            cand.append((i, line))
    if not cand:
        return out
    lines = {i for i, _ in cand}
    lo, hi = min(lines), max(lines)
    near = [s for s in spans if s[0] <= hi and s[2] >= lo]
    for i, line in cand:
        here = [s for s in near if s[0] <= i <= s[2]]
        pos = line.find('#')
        while pos >= 0:
            col = len(line[:pos].encode('utf-8'))
            inside = any((i > sl or col >= sc) and (i < el or col < ec) for sl, sc, el, ec in here)
            if not inside:
                out.append((i, line[pos:]))
                break
            pos = line.find('#', pos + 1)
    return out


def parse_file(rel, text):
    """aidd:FR-014 (nodes, edges, warnings) of one file. Call edges come back RAW (`target` '' and `callee`),
    imports as raw `imports` edges carrying `local`/`module`/`name`/`level`; resolve_calls links them.
    Never raises: a syntax error leaves the FILE node (`parsed` False) and a warning."""
    rel = rel.replace('\\', '/')
    fnode = {'id': rel, 'type': 'FILE', 'label': rel.split('/')[-1], 'source_file': rel,
             'source_location': rel + ':1', 'parsed': True, 'markers': [], 'rule_ids': []}
    warnings, nodes, edges = [], [fnode], []
    tree = None
    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as ex:
        warnings.append('%s: syntax error line %s: %s' % (rel, ex.lineno, ex.msg))
    except Exception as ex:  # ValueError (null bytes), RecursionError, MemoryError on giant files
        warnings.append('%s: not parsed (%s)' % (rel, type(ex).__name__))
    file_text, ranges, comments = [], [], None
    if tree is not None:
        try:
            v = _Visitor(rel)
            for stmt in tree.body:
                v.visit(stmt)
            imap = v.imap
            for n in v.nodes:
                if n['type'] == 'CLASS':
                    file_text.append(n.pop('_doc', ''))
            nodes.extend(v.nodes)
            edges.extend(v.edges)
            ranges = v.ranges
            for local, (mod, name, level) in sorted(imap.items()):
                edges.append({'source': rel, 'target': '', 'relation': 'imports', 'local': local,
                              'module': mod, 'name': name, 'level': level})
            file_text.append(ast.get_docstring(tree, clean=False) or '')
            comments = _comments_fast(text, v.spans)
        except Exception as ex:  # a visitor bug must not lose the other files
            warnings.append('%s: partial parse (%s: %s)' % (rel, type(ex).__name__, ex))
            fnode['parsed'] = False
    else:
        fnode['parsed'] = False
    if comments is None:
        comments = _comments_tokenize(text)
    # aidd:FR-015 markers and rule ids from comments go to the innermost FUNC containing the line, else FILE
    funcs = {n['id']: n for n in nodes if n['type'] == 'FUNC'}
    for line, comment in comments:
        owner = None
        for start, end, fid in ranges:
            if start <= line <= end and (owner is None or start >= owner[0]):
                owner = (start, fid)
        if owner and owner[1] in funcs:
            m, r = _codes(comment)
            fn = funcs[owner[1]]
            fn['markers'] = sorted(set(fn['markers']) | set(m))
            fn['rule_ids'] = sorted(set(fn['rule_ids']) | set(r))
        else:
            file_text.append(comment)
    fnode['markers'], fnode['rule_ids'] = _codes('\n'.join(file_text))
    if warnings:
        fnode['warnings'] = list(warnings)
    return nodes, edges, warnings


# ---------------------------------------------------------------------------------------------------- link

class _Index:
    def __init__(self, nodes):
        self.types = {n['id']: n['type'] for n in nodes}
        self.files = {n['id'] for n in nodes if n['type'] == 'FILE'}
        top, meth, self.mod = {}, {}, {}
        for n in nodes:
            if n['type'] in ('FUNC', 'CLASS') and '::' in n['id']:
                qual = n['id'].split('::', 1)[1]
                if '.' not in qual:
                    top.setdefault(qual, []).append(n['id'])
                if n['type'] == 'FUNC':
                    meth.setdefault(qual.rsplit('.', 1)[-1], []).append(n['id'])
        self.top = {k: sorted(v) for k, v in top.items()}
        self.meth = {k: sorted(v) for k, v in meth.items()}
        self.bases = {n['id']: n['bases'] for n in nodes if n['type'] == 'CLASS' and n.get('bases')}
        self._mro = {}
        # byte-identical mirror copies resolve to their canonical file only (never to themselves)
        self.alias = {n['id']: n['mirror_of'] for n in nodes if n['type'] == 'FILE' and n.get('mirror_of')}
        for rel in self.files:
            if rel in self.alias:
                continue
            parts = rel[:-3].split('/') if rel.endswith('.py') else rel.split('/')
            if parts[-1] == '__init__':
                parts = parts[:-1]
            for i in range(len(parts)):
                self.mod.setdefault('.'.join(parts[i:]), set()).add(rel)
        self._cache = {}

    def module_files(self, importer, module, level):
        key = (importer, module, level)
        res = self._cache.get(key)
        if res is not None:
            return res
        parts = [p for p in module.split('.') if p]
        idir = importer.split('/')[:-1]
        res = []
        if level > 0:
            base = idir[:len(idir) - (level - 1)] if level - 1 <= len(idir) else []
            res = self._at(base + parts)
        elif parts:
            res = self._at(idir + parts) or self._at(parts) or sorted(self.mod.get('.'.join(parts), ()))
        self._cache[key] = res
        return res

    def _at(self, parts):
        stem = '/'.join(parts)
        cands = ('__init__.py',) if not parts else (stem + '.py', stem + '/__init__.py')
        return [self.alias.get(x, x) for x in cands if x in self.files][:1]


def _caller_parts(caller):
    if '::' in caller:
        f, q = caller.split('::', 1)
        return f, q.split('.')
    return caller, []


# A resolution is ('edges', [targets], ambiguous) | ('ext', name) | ('sink', label).

def _by_method(ix, name, f=''):
    """Unknown receiver: ext for well-known names; otherwise the project methods of that name, narrowed by
    scope (same file, else same directory, else all; still ambiguous). <= MAX_CANDIDATES = one ambiguous edge
    each; more (or none) = one ambiguous edge to `sink:unresolved:<name>`."""
    if _is_ext_method(name):
        return ('ext', name)
    c = ix.meth.get(name, ())
    if len(c) > 1 and f:
        same = [x for x in c if x.split('::', 1)[0] == f]
        if not same:
            d = f.rsplit('/', 1)[0] + '/' if '/' in f else ''
            same = [x for x in c if x.split('::', 1)[0].rsplit('/', 1)[0] + '/' == d] if d else []
        c = same or c
    if 0 < len(c) <= MAX_CANDIDATES:
        return ('edges', list(c), True)
    return ('sink', name)


def _class_method(ix, imaps, cid, name, depth=0):
    """`cid.name` or the first one found up the project base classes (depth-first, bounded)."""
    key = (cid, name)
    if key in ix._mro:
        return ix._mro[key]
    ix._mro[key] = None                       # cycle guard
    t = cid + '.' + name
    found = t if t in ix.types else None
    if found is None and depth < 8:
        f = cid.split('::', 1)[0]
        for b in ix.bases.get(cid, ()):
            res = _resolve_one(ix, imaps, f, b)
            if res[0] != 'edges':
                continue
            for bc in res[1]:
                if ix.types.get(bc) == 'CLASS':
                    found = _class_method(ix, imaps, bc, name, depth + 1)
                    if found:
                        break
            if found:
                break
    ix._mro[key] = found
    return found


def _resolve_one(ix, imaps, caller, callee):
    f, qparts = _caller_parts(caller)
    parts = callee.split('.')
    imap = imaps.get(f, {})
    if parts[0] == '?':
        return _by_method(ix, parts[-1], f)
    if parts[0] in ('self', 'cls') and len(parts) == 2:
        for i in range(len(qparts), 0, -1):
            cid = '%s::%s' % (f, '.'.join(qparts[:i]))
            if ix.types.get(cid) == 'CLASS':
                t = _class_method(ix, imaps, cid, parts[1])
                if t:
                    return ('edges', [t], False)
                break
        return _by_method(ix, parts[1], f)
    if len(parts) == 1:
        name = parts[0]
        for i in range(len(qparts), -1, -1):              # scope first: enclosing functions, then the module
            prefix = '.'.join(qparts[:i])
            if prefix and ix.types.get('%s::%s' % (f, prefix)) != 'FUNC':
                continue
            t = '%s::%s' % (f, (prefix + '.' + name) if prefix else name)
            if t in ix.types:
                return ('edges', [t], False)
        if name in imap:                                   # then explicit imports
            mod, sym, level = imap[name]
            if sym:
                files = ix.module_files(f, mod, level)
                if files:
                    c = sorted(x + '::' + sym for x in files if x + '::' + sym in ix.types)
                    if c:
                        return ('edges', c, len(c) > 1)
                elif not ix.module_files(f, (mod + '.' + sym) if mod else sym, level):
                    return ('ext', '.'.join(x for x in (mod, sym) if x))   # stdlib / third-party symbol
        if name in EXT_BUILTINS:
            return ('ext', name)
        c = ix.top.get(name, ())                           # then the global name
        if c:
            return ('edges', list(c), len(c) > 1)
        return ('sink', name)
    for i in range(len(parts) - 1, 0, -1):                 # dotted: longest imported prefix
        key = '.'.join(parts[:i])
        if key not in imap:
            continue
        rest = '.'.join(parts[i:])
        mod, sym, level = imap[key]
        if sym:
            sub = (mod + '.' + sym) if mod else sym
            files, qual = ix.module_files(f, sub, level), rest
            if not files:
                files, qual = ix.module_files(f, mod, level), sym + '.' + rest
        else:
            files, qual = ix.module_files(f, mod, level), rest
        if files:
            c = sorted(x + '::' + qual for x in files if x + '::' + qual in ix.types)
            if c:
                return ('edges', c, len(c) > 1)
            return _by_method(ix, parts[-1], f)
        canon = '.'.join(x for x in (mod, sym) if x) if level == 0 else key
        return ('ext', canon + '.' + rest)                 # stdlib / third-party module call
    local = '%s::%s' % (f, '.'.join(parts))
    if local in ix.types:
        return ('edges', [local], False)
    return _by_method(ix, parts[-1], f)


def resolve_calls(nodes, edges):
    """aidd:FR-014 global linking, recomputed on every build from the per-file raw facts (linear: one dict
    lookup chain per raw call). Scope first (same module), explicit imports, then the global name; >1
    candidate = one edge per candidate with ambiguous:true; 0 = SINK `unresolved` with ambiguous:true;
    builtin/stdlib/well-known method calls go to the caller's `ext` list. Returns (nodes, edges)."""
    ix = _Index(nodes)
    imaps = {}
    for e in edges:
        if e.get('relation') == 'imports' and not e.get('target'):
            imaps.setdefault(e['source'], {})[e['local']] = (e.get('module', ''), e.get('name', ''),
                                                             int(e.get('level', 0) or 0))
    out, merged, sinks, ext = [], {}, {}, {}
    memo = {}
    for e in edges:
        rel = e.get('relation')
        if rel == 'imports' and not e.get('target'):
            mod, sym, level = e.get('module', ''), e.get('name', ''), int(e.get('level', 0) or 0)
            files = []
            if sym:
                files = ix.module_files(e['source'], (mod + '.' + sym) if mod else sym, level)
            files = files or ix.module_files(e['source'], mod, level)
            for t in files:
                if t != e['source']:
                    k = (e['source'], t, 'imports')
                    cur = merged.setdefault(k, {'source': e['source'], 'target': t, 'relation': 'imports'})
                    if len(files) > 1:
                        cur['ambiguous'] = True
            continue
        if rel == 'calls' and not e.get('target'):
            src, callee, in_loop = e['source'], e.get('callee') or '?', bool(e.get('in_loop'))
            mk = (src.split('::', 1)[0], src, callee) if callee.startswith(('self.', 'cls.')) or '.' not in \
                callee else (src.split('::', 1)[0], callee)
            res = memo.get(mk)
            if res is None:
                try:
                    res = _resolve_one(ix, imaps, src, callee)
                except Exception:
                    res = ('sink', callee)
                memo[mk] = res
            if res[0] == 'ext':
                d = ext.setdefault(src, {})
                d[res[1]] = d.get(res[1], False) or in_loop
                continue
            if res[0] == 'sink':
                s = _sink('unresolved', res[1] or '?')
                sinks[s['id']] = s
                targets, amb = [s['id']], True
            else:
                targets, amb = res[1], res[2]
            for t in targets:
                k = (src, t, 'calls')
                cur = merged.get(k)
                if cur is None:
                    cur = merged[k] = {'source': src, 'target': t, 'relation': 'calls'}
                if amb:
                    cur['ambiguous'] = True
                if in_loop:
                    cur['in_loop'] = True
            continue
        k = (e.get('source', ''), e.get('target', ''), rel)
        cur = merged.get(k)
        if cur is None:
            merged[k] = dict(e)
        elif e.get('in_loop'):
            cur['in_loop'] = True
    out = list(merged.values())
    res_nodes = []
    for n in nodes:
        d = ext.get(n['id'])
        if d or 'ext' in n:
            n = dict(n)
            n.pop('ext', None)
            n.pop('ext_in_loop', None)
            if d:
                n['ext'] = sorted(d)
                loop = sorted(k for k, v in d.items() if v)
                if loop:
                    n['ext_in_loop'] = loop
        res_nodes.append(n)
    have = {n['id'] for n in nodes}
    res_nodes += [s for sid, s in sorted(sinks.items()) if sid not in have]
    return res_nodes, out


def link_markers(graph):
    """aidd:FR-015 `implements` edges FUNC/FILE -> plain code id (`FR-205`) from their `aidd:<CODE>` markers.
    Idempotent: existing `implements` edges are rebuilt."""
    edges = [e for e in graph.get('edges', []) if e.get('relation') != 'implements']
    seen = set()
    for n in graph.get('nodes', []):
        if n.get('type') in ('FUNC', 'FILE'):
            for code in n.get('markers') or ():
                if (n['id'], code) not in seen:
                    seen.add((n['id'], code))
                    edges.append({'source': n['id'], 'target': code, 'relation': 'implements'})
    graph['edges'] = edges
    return graph


# ---------------------------------------------------------------------------------------------------- build

def _edge_key(e):
    return (e.get('source', ''), e.get('target', ''), e.get('relation', ''))


def _dedupe_nodes(nodes):
    by = {}
    for n in nodes:
        by.setdefault(n['id'], n)
    return [by[k] for k in sorted(by)]


def _entry(sha, nodes, edges, warnings):
    """Sidecar cache entry of one file: its nodes, its local edges and its raw facts (imports, calls)."""
    local, imports, calls = [], [], []
    for e in edges:
        r = e.get('relation')
        if r == 'imports' and not e.get('target'):
            imports.append([e['local'], e.get('module', ''), e.get('name', ''), int(e.get('level', 0) or 0)])
        elif r == 'calls' and not e.get('target'):
            calls.append([e['source'], e['callee'], 1 if e.get('in_loop') else 0])
        elif r != 'defines':                    # defines are rebuilt from the node ids (_unpack)
            local.append(e)
    return {'sha': sha, 'nodes': nodes, 'edges': local, 'imports': imports, 'calls': calls,
            'warnings': list(warnings)}


def _unpack(ent):
    rel = ent['nodes'][0]['id']
    ids = {n['id'] for n in ent['nodes']}
    edges = []
    for n in ent['nodes']:
        if n.get('type') in ('FUNC', 'CLASS') and '::' in n['id']:
            f, qual = n['id'].split('::', 1)
            parent = '%s::%s' % (f, qual.rsplit('.', 1)[0]) if '.' in qual else f
            edges.append({'source': parent if parent in ids else f, 'target': n['id'], 'relation': 'defines'})
    edges += list(ent.get('edges') or [])
    edges += [{'source': rel, 'target': '', 'relation': 'imports', 'local': l, 'module': m, 'name': n,
               'level': lv} for l, m, n, lv in ent.get('imports') or []]
    edges += [{'source': s, 'target': '', 'relation': 'calls', 'callee': c, 'in_loop': bool(il)}
              for s, c, il in ent.get('calls') or []]
    return edges


def _cache_files(cache):
    """{rel: entry} of a compatible sidecar cache; {} otherwise (aidd:FR-024)."""
    if not isinstance(cache, dict) or cache.get('schema') != SCHEMA_VERSION \
            or cache.get('extractor') != EXTRACTOR_VERSION or not isinstance(cache.get('files'), dict):
        return {}
    return cache['files']


def _read_text(path):
    data = path.read_bytes()
    try:
        return data.decode('utf-8-sig'), None
    except UnicodeDecodeError:
        return data.decode('latin-1'), 'not utf-8, decoded as latin-1'


def _canonical_rank(rel):
    return (0 if rel.startswith('skill/') else 2 if rel.startswith('adapters/') else 1, rel)


def _mirrors(rels, shas):
    """{mirror rel: canonical rel} for files whose content sha equals another file's. Canonical: the copy
    under skill/, else the first non-adapters path, else the first path (deterministic)."""
    groups = {}
    for rel in rels:
        sha = shas.get(rel)
        # empty files and package __init__.py keep their own identity (a package is not its copy)
        if sha and sha != EMPTY_BLOB and not rel.endswith('__init__.py'):
            groups.setdefault(sha, []).append(rel)
    out = {}
    for group in groups.values():
        if len(group) > 1:
            group.sort(key=_canonical_rank)
            for m in group[1:]:
                out[m] = group[0]
    return out


def build_with_cache(root, globs=None, cache=None, lazy=False):
    """aidd:FR-014 aidd:FR-024 (graph, stats, new_cache, cache_dirty). A FILE whose sha equals the sidecar
    entry's is reused (nodes, local edges and raw facts); everything else is parsed. Never raises per file.
    `lazy`: when nothing changed (no file parsed, same file set) the linking is skipped and graph is None."""
    root = Path(root)
    globs = list(globs) if globs else default_globs(root)
    rels = list_files(root, globs)
    shas = file_shas(root, rels)
    old = _cache_files(cache)
    mirror_of = _mirrors(rels, shas)
    nodes, edges, warnings, files = [], [], [], {}
    parsed = reused = 0
    for rel in rels:
        sha = shas.get(rel, '')
        if rel in mirror_of:      # byte-identical copy: FILE node only, no facts, no edges of its own
            nodes.append({'id': rel, 'type': 'FILE', 'label': rel.split('/')[-1], 'source_file': rel,
                          'source_location': rel + ':1', 'sha': sha, 'mirror_of': mirror_of[rel],
                          'markers': [], 'rule_ids': []})
            reused += 1
            continue
        ent = old.get(rel)
        ok = False
        if sha and isinstance(ent, dict) and ent.get('sha') == sha:
            try:
                fe = _unpack(ent)
                fn = [dict(n) for n in ent['nodes']]
                ok = True
            except Exception:
                ok = False
        if ok:
            files[rel] = ent
            nodes.extend(fn)
            edges.extend(fe)
            warnings.extend(ent.get('warnings') or [])
            reused += 1
            continue
        parsed += 1
        try:
            text, note = _read_text(root / rel)
        except OSError as ex:
            w = '%s: not read (%s)' % (rel, ex.__class__.__name__)
            warnings.append(w)
            nodes.append({'id': rel, 'type': 'FILE', 'label': rel.split('/')[-1], 'source_file': rel,
                          'source_location': rel + ':1', 'sha': sha, 'parsed': False, 'markers': [],
                          'rule_ids': [], 'warnings': [w]})
            continue
        fn, fe, fw = parse_file(rel, text)
        if note:
            fw = fw + ['%s: %s' % (rel, note)]
            fn[0]['warnings'] = list(fw)
        fn[0]['sha'] = sha
        if sha:
            files[rel] = _entry(sha, [dict(n) for n in fn], fe, fw)
        nodes.extend(fn)
        edges.extend(fe)
        warnings.extend(fw)
    new_cache = {'schema': SCHEMA_VERSION, 'extractor': EXTRACTOR_VERSION, 'globs': globs, 'files': files}
    dirty = parsed > 0 or set(files) != set(old) or not old
    if lazy and not dirty:
        stats = {'files': len(rels), 'parsed': 0, 'reused': reused, 'warnings': len(set(warnings))}
        return None, stats, new_cache, False
    nodes = _dedupe_nodes(nodes)
    nodes, edges = resolve_calls(nodes, edges)
    graph = {'schema': SCHEMA_VERSION, 'extractor': EXTRACTOR_VERSION, 'generated': time.time(),
             'globs': globs, 'nodes': _dedupe_nodes(nodes), 'edges': edges, 'warnings': sorted(set(warnings))}
    link_markers(graph)
    graph['edges'] = sorted(graph['edges'], key=_edge_key)
    stats = {'files': len(rels), 'parsed': parsed, 'reused': reused, 'warnings': len(graph['warnings'])}
    return graph, stats, new_cache, dirty


def build(root, globs=None, previous=None):
    """aidd:FR-014 aidd:FR-024 (graph, stats); stats = {parsed, reused, warnings, files}. `previous` is the
    sidecar cache dict (`<out>.cache.json`); None or an incompatible dict means a full parse."""
    graph, stats, _, _ = build_with_cache(root, globs=globs, cache=previous)
    return graph, stats


def _graph_sha(path):
    try:
        return hashlib.sha1(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def _write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('%s.tmp.%d' % (path.name, os.getpid()))
    try:
        tmp.write_bytes(data)
        os.replace(str(tmp), str(path))
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def main(argv=None):
    ap = argparse.ArgumentParser(prog='code_graph.py',
                                 description='Build the built-in AIDD code graph (%s).' % GRAPH_REL)
    ap.add_argument('--root', default=None, help='project root (default: cwd)')
    ap.add_argument('--out', default=None, help='output file (default: <root>/%s; the reuse cache is '
                                                '<out>%s)' % (GRAPH_REL, CACHE_SUFFIX))
    ap.add_argument('--globs', default=None, help='comma-separated globs (default: AIDD repo dirs or **/*.py)')
    ap.add_argument('--full', action='store_true', help='ignore the reuse cache and re-parse every file')
    ap.add_argument('--quiet', action='store_true', help='do not list the warnings (summary line only)')
    try:
        a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as ex:
        return int(ex.code or 0)
    root = Path(a.root or os.getcwd()).resolve()
    if not root.is_dir():
        print('code graph: root not found: %s' % root, file=sys.stderr)
        return 2
    out = Path(a.out) if a.out else root / GRAPH_REL
    if not out.is_absolute():
        out = root / out
    cache_path = out.with_name(out.name + CACHE_SUFFIX)
    globs = [g.strip() for g in a.globs.split(',') if g.strip()] if a.globs else None
    cache = None
    if not a.full and cache_path.is_file():
        try:
            cache = json.loads(cache_path.read_text(encoding='utf-8'))
        except Exception:
            cache = None
    graph, stats, new_cache, _ = build_with_cache(root, globs=globs, cache=cache, lazy=True)
    if graph is None:
        # aidd:FR-024 nothing changed: keep the written graph when it is the one this cache produced
        if new_cache.get('globs') == (cache or {}).get('globs') and _graph_sha(out) == (cache or {}).get('graph_sha'):
            print('code graph: %d files, re-parsed %d, reused %d, warnings %d'
                  % (stats['files'], stats['parsed'], stats['reused'], stats['warnings']))
            return 0
        graph, stats, new_cache, _ = build_with_cache(root, globs=globs, cache=cache)
    body = json.dumps(graph, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    try:
        _write_atomic(out, body)
    except Exception as ex:
        print('code graph: not written (%s)' % ex, file=sys.stderr)
        return 1
    new_cache['graph_sha'] = hashlib.sha1(body).hexdigest()
    try:
        _write_atomic(cache_path, json.dumps(new_cache, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
    except Exception as ex:  # the graph is written; only the next build loses its reuse
        print('warning: reuse cache not written (%s)' % ex, file=sys.stderr)
    if not a.quiet:
        for w in graph['warnings'][:20]:
            print('warning: ' + w, file=sys.stderr)
        if len(graph['warnings']) > 20:
            print('warning: ... %d more' % (len(graph['warnings']) - 20), file=sys.stderr)
    print('code graph: %d files, re-parsed %d, reused %d, warnings %d'
          % (stats['files'], stats['parsed'], stats['reused'], stats['warnings']))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
