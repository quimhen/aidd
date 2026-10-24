#!/usr/bin/env python3
"""aidd graph trace — runtime overlay of the built-in code graph (stdlib profiler, no LLM, off by default).

Spec 004 amendment 2026-10-24 (aidd:FR-018, aidd:AC-013, aidd:T-14).

`aidd graphs trace -- aidd <subcommand> [args]` maps the subcommand to the script the CLI would launch and runs
that script IN THIS PROCESS (`runpy.run_path`, patched `sys.argv`, cwd = the traced project root, graph refresh
disabled with AIDD_GRAPHS=off). `aidd.cli.main` is not used: its `_run` launches a child process that a profiler
cannot see. A `Tracer` (`sys.setprofile` + `threading.setprofile`, installed only inside `run_traced`) reacts to a
CLOSED set of sinks and counts, per FUNC -> SINK pair, how many times each fired:

  file reads  builtins.open / io.open (mode without w/a/x/+), pathlib.Path.read_text / read_bytes, json.load
  spawns      subprocess.Popen.__init__ (argv0 from its args), os.system

Each event is attributed to the nearest caller frame that belongs to the AIDD bundle (repo `skill/` or
`adapters/`, or the installed skill scripts dir); the FUNC id is `skill/scripts/<basename>::<qualname>` so the
installed copy and the repo map to the same ids (module level -> the FILE id `skill/scripts/<basename>`). Paths
are relative to the traced root ('/' separators). A re-read of a path whose (size, mtime_ns) did not change is
counted (a counter, not a validity check). Grandchild processes are counted as spawns, never profiled.

The C-level sinks (open, os.system) do not expose their arguments to a profiler; while a trace is active a
gated audit hook (`sys.addaudithook`, a no-op whenever no trace runs) supplies the path/mode and the command.

Usage:
    python graph_trace.py --root <project> [--graph <code.json>] [--out <json>] -- <aidd command ...>
Prints the top 25 FUNC -> sink pairs by count and the totals. Exit code = the traced command's exit code.
Stdlib only.
"""
import argparse
import ast
import builtins
import io
import json
import os
import runpy
import shlex
import subprocess
import sys
import threading
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

RUNTIME_KEY = 'runtime'                       # aidd:FR-018 integer count on the FUNC -> SINK edge
RUNTIME_DETAIL_KEY = 'runtime_detail'
READ_SINK = 'sink:file:*'
TOP_N = 25
GRAPH_REL = '.aidd/graphs/code.json'
_HERE = Path(__file__).resolve()
_SELF_BASENAMES = frozenset({'graph_trace.py'})
_EXEC_NAMES = ('execl', 'execle', 'execlp', 'execlpe', 'execv', 'execve', 'execvp', 'execvpe')

_OPEN_IDS = frozenset({id(builtins.open), id(io.open)})
_OS_SYSTEM = getattr(os, 'system', None)
_C_SINK_IDS = _OPEN_IDS | ({id(_OS_SYSTEM)} if _OS_SYSTEM is not None else frozenset())

_ACTIVE = None              # the Tracer currently running (read by the audit hook); None outside run_traced
_AUDIT_INSTALLED = False


def _warn(msg):
    try:
        sys.stderr.write('graph_trace: warning: %s\n' % msg)
        sys.stderr.flush()
    except Exception:
        pass


def _norm_argv0(s):
    try:
        s = os.path.basename(str(s).replace('\\', '/').strip().strip('"\''))
        return (s[:-4] if s.lower().endswith('.exe') else s) or '?'
    except Exception:
        return '?'


def _argv0_of(args, executable=None):
    try:
        if isinstance(args, (str, bytes)):
            text = args.decode('utf-8', 'replace') if isinstance(args, bytes) else args
            try:
                first = shlex.split(text, posix=(os.name != 'nt'))[0]
            except Exception:
                first = text.strip().split(' ')[0] if text.strip() else '?'
            return _norm_argv0(first)
        if isinstance(args, os.PathLike):
            return _norm_argv0(os.fspath(args))
        seq = list(args or [])
        if seq:
            return _norm_argv0(os.fspath(seq[0]) if isinstance(seq[0], os.PathLike) else seq[0])
        if executable:
            return _norm_argv0(executable)
    except Exception:
        pass
    return '?'


def _is_read_mode(mode):
    if mode is None:
        return True
    try:
        return not any(c in str(mode) for c in 'wax+')
    except Exception:
        return False


def _norm_drive(p):
    return p[0].lower() + p[1:] if len(p) > 1 and p[1] == ':' else p


# ---------------------------------------------------------------------------------------------------- tracer

class Tracer:
    """aidd:FR-018 counts closed-set sink events per (func_id, sink_id). Use only through `run_traced`:
    `start()` installs the profile hooks, `stop()` restores the previous ones. Never raises."""

    def __init__(self, root, bundle_dirs):
        self.root = os.path.abspath(str(root))
        self._root_nc = os.path.normcase(self.root)
        self._bundle = tuple(sorted({os.path.normcase(os.path.abspath(str(d))) + os.sep
                                     for d in bundle_dirs if d}))
        self.counts = {}                       # (func_id, sink_id) -> {count, by_path, by_argv0, rereads}
        self.totals = {'reads': 0, 'spawns': 0, 'rereads': 0}
        self.errors = 0
        self._sigs = {}                        # rel path -> (size, mtime_ns) at its last read
        self._fid_cache = {}                   # code object -> func id or None
        self._tls = threading.local()
        self._lock = threading.Lock()
        self._prev = None
        self._prev_thread = None
        codes = {}
        for kind, fn in (('read_text', getattr(Path, 'read_text', None)),
                         ('read_bytes', getattr(Path, 'read_bytes', None)),
                         ('json_load', getattr(json, 'load', None)),
                         ('popen', getattr(subprocess.Popen, '__init__', None))):
            code = getattr(fn, '__code__', None)
            if code is not None:
                codes[code] = kind
        self._call_codes = codes
        self._pathlib_read_codes = frozenset(c for c, k in codes.items() if k in ('read_text', 'read_bytes'))

    # -- hooks -------------------------------------------------------------------------------------------
    def start(self):
        global _ACTIVE
        try:
            _install_audit_hook()
            self._prev = sys.getprofile()
            self._prev_thread = threading.getprofile() if hasattr(threading, 'getprofile') else None
            _ACTIVE = self
            threading.setprofile(self._profile)
            sys.setprofile(self._profile)
        except Exception:
            self.errors += 1

    def stop(self):
        global _ACTIVE
        try:
            sys.setprofile(self._prev)
        except Exception:
            self.errors += 1
        try:
            threading.setprofile(self._prev_thread)
        except Exception:
            self.errors += 1
        if _ACTIVE is self:
            _ACTIVE = None

    def _stack(self):
        st = getattr(self._tls, 'stack', None)
        if st is None:
            st = self._tls.stack = []
        return st

    def _profile(self, frame, event, arg):
        try:
            if event == 'call':
                kind = self._call_codes.get(frame.f_code)
                if kind is not None:
                    self._on_py_sink(kind, frame)
            elif event == 'c_call':
                if id(arg) in _OPEN_IDS:
                    fid = None if self._inside_pathlib_read(frame) else self._attribute(frame)
                    self._stack().append(['open', fid, False])
                elif _OS_SYSTEM is not None and arg is _OS_SYSTEM:
                    self._stack().append(['system', self._attribute(frame), False])
            elif event in ('c_return', 'c_exception'):
                if id(arg) in _C_SINK_IDS:
                    st = self._stack()
                    if st:
                        kind, fid, done = st.pop()
                        if kind == 'system' and fid and not done:
                            self._record_spawn(fid, '?')
        except Exception:
            self.errors += 1

    def on_audit(self, event, args):
        """Supplies the arguments of the C-level sinks the profiler announced (open path/mode, os.system)."""
        try:
            if event not in ('open', 'os.system'):
                return
            st = getattr(self._tls, 'stack', None)
            if not st:
                return
            top = st[-1]
            if top[2]:
                return
            if event == 'open' and top[0] == 'open':
                top[2] = True
                path, mode = (args[0] if args else None), (args[1] if len(args) > 1 else None)
                if top[1] and path is not None and not isinstance(path, int) and _is_read_mode(mode):
                    self._record_read(top[1], path)
            elif event == 'os.system' and top[0] == 'system':
                top[2] = True
                if top[1]:
                    self._record_spawn(top[1], _argv0_of(args[0] if args else ''))
        except Exception:
            self.errors += 1

    # -- attribution -------------------------------------------------------------------------------------
    def _inside_pathlib_read(self, frame):
        f, depth = frame, 0
        while f is not None and depth < 3:     # Path.read_text -> Path.open -> io.open: counted once
            if f.f_code in self._pathlib_read_codes:
                return True
            f, depth = f.f_back, depth + 1
        return False

    def _func_id(self, code):
        try:
            return self._fid_cache[code]
        except KeyError:
            pass
        fid = None
        try:
            fn = code.co_filename or ''
            if fn and not fn.startswith('<'):
                nc = os.path.normcase(os.path.abspath(fn))
                base = os.path.basename(fn)
                if base not in _SELF_BASENAMES and any(nc.startswith(b) for b in self._bundle):
                    qual = getattr(code, 'co_qualname', code.co_name) or ''
                    parts = [p for p in qual.split('.') if p and not p.startswith('<')]
                    rel = 'skill/scripts/' + base
                    fid = '%s::%s' % (rel, '.'.join(parts)) if parts else rel
        except Exception:
            fid = None
        self._fid_cache[code] = fid
        return fid

    def _attribute(self, frame):
        f = frame
        while f is not None:
            fid = self._func_id(f.f_code)
            if fid:
                return fid
            f = f.f_back
        return None

    def _rel(self, path):
        try:
            p = os.fsdecode(os.fspath(path))
            ab = os.path.abspath(p)
            nc = os.path.normcase(ab)
            if nc == self._root_nc:
                return '.'
            if nc.startswith(self._root_nc.rstrip(os.sep) + os.sep):
                return ab[len(self.root.rstrip(os.sep)) + 1:].replace('\\', '/')
            return _norm_drive(ab.replace('\\', '/'))
        except Exception:
            return '?'

    def _entry(self, key):
        e = self.counts.get(key)
        if e is None:
            e = self.counts[key] = {'count': 0, 'by_path': {}, 'by_argv0': {}, 'rereads': 0}
        return e

    def _on_py_sink(self, kind, frame):
        caller = frame.f_back
        fid = self._attribute(caller) if caller is not None else None
        if not fid:
            return
        loc = frame.f_locals
        if kind in ('read_text', 'read_bytes'):
            obj = loc.get('self')
            self._record_read(fid, obj if obj is not None else None)
        elif kind == 'json_load':
            name = getattr(loc.get('fp'), 'name', None)
            self._record_read(fid, name if isinstance(name, (str, bytes, os.PathLike)) else None)
        elif kind == 'popen':
            self._record_spawn(fid, _argv0_of(loc.get('args'), loc.get('executable')))

    def _record_read(self, fid, path):
        rel, sig = '*', None
        if path is not None:
            rel = self._rel(path)
            try:
                st = os.stat(os.fspath(path))
                sig = (st.st_size, st.st_mtime_ns)
            except Exception:
                sig = None
        with self._lock:
            e = self._entry((fid, READ_SINK))
            e['count'] += 1
            e['by_path'][rel] = e['by_path'].get(rel, 0) + 1
            self.totals['reads'] += 1
            if sig is not None:
                if self._sigs.get(rel) == sig:
                    e['rereads'] += 1
                    self.totals['rereads'] += 1
                self._sigs[rel] = sig

    def _record_spawn(self, fid, argv0):
        argv0 = argv0 or '?'
        with self._lock:
            e = self._entry((fid, 'sink:spawn:%s' % argv0))
            e['count'] += 1
            e['by_argv0'][argv0] = e['by_argv0'].get(argv0, 0) + 1
            self.totals['spawns'] += 1


def _audit_hook(event, args):
    t = _ACTIVE
    if t is not None:
        t.on_audit(event, args)


def _install_audit_hook():
    """Audit hooks cannot be removed; this one is a no-op whenever no trace is active (installed lazily, only by
    `run_traced`)."""
    global _AUDIT_INSTALLED
    if not _AUDIT_INSTALLED:
        sys.addaudithook(_audit_hook)
        _AUDIT_INSTALLED = True


# ---------------------------------------------------------------------------------------------------- mapping

def _repo_root_of(scripts_dir):
    try:
        root = Path(scripts_dir).resolve().parent.parent
        return root if (root / 'aidd' / 'cli.py').is_file() else None
    except Exception:
        return None


def find_scripts_dir():
    """Like aidd.cli._find_scripts_dir, but a repo checkout (this file under <repo>/skill/scripts) wins."""
    here = _HERE.parent
    cands = []
    if _repo_root_of(here) is not None:
        cands.append(here)
    if os.environ.get('AIDD_HOME'):
        cands.append(Path(os.environ['AIDD_HOME']).expanduser() / 'scripts')
    cands += [Path.home() / '.claude' / 'skills' / 'aidd' / 'scripts', here]
    for c in cands:
        try:
            if (c / 'find_spec.py').is_file():
                return c
        except Exception:
            continue
    return here


def _cli_path(scripts_dir):
    for base in (_repo_root_of(scripts_dir), _repo_root_of(_HERE.parent)):
        if base is not None:
            return base / 'aidd' / 'cli.py'
    try:
        import aidd.cli as _c                                   # installed package
        return Path(_c.__file__)
    except Exception:
        return None


def _run_call(node):
    """First `_run("<script>.py", [...])` call under node -> (script, literal leading args) or None."""
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == '_run' and n.args:
            a0 = n.args[0]
            if not (isinstance(a0, ast.Constant) and isinstance(a0.value, str)):
                continue
            prefix = []
            if len(n.args) > 1 and isinstance(n.args[1], (ast.List, ast.Tuple)):
                for el in n.args[1].elts:
                    if isinstance(el, ast.Constant) and isinstance(el.value, str):
                        prefix.append(el.value)
                    else:
                        break
            return a0.value, prefix
    return None


def scan_cli(cli_path):
    """aidd:FR-018 own minimal `ast` scan of aidd/cli.py: {subcommand: (script, literal arg prefix)}. Never raises."""
    out = {}
    try:
        tree = ast.parse(Path(cli_path).read_text(encoding='utf-8'))
    except Exception:
        return out
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    pvars = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) \
                and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute) \
                and n.value.func.attr == 'add_parser' and n.value.args \
                and isinstance(n.value.args[0], ast.Constant) and isinstance(n.value.args[0].value, str):
            pvars[n.targets[0].id] = n.value.args[0].value
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'set_defaults' \
                and isinstance(n.func.value, ast.Name) and n.func.value.id in pvars:
            for k in n.keywords:
                if k.arg != 'func':
                    continue
                target = funcs.get(k.value.id) if isinstance(k.value, ast.Name) else k.value
                found = _run_call(target) if target is not None else None
                if found:
                    out.setdefault(pvars[n.func.value.id], found)
    for name, fn in funcs.items():                            # cmd_<sub> not registered through a variable
        if name.startswith('cmd_'):
            found = _run_call(fn)
            if found:
                out.setdefault(name[4:].replace('_', '-'), found)
    return out


def resolve_command(argv, scripts_dir):
    """['aidd'?, sub, *rest] -> (script path, script argv) or (None, reason)."""
    argv = [str(a) for a in argv]
    if argv and _norm_argv0(argv[0]).lower() == 'aidd':
        argv = argv[1:]
    if not argv:
        return None, 'no aidd subcommand given'
    sub, rest = argv[0], argv[1:]
    cli = _cli_path(scripts_dir)
    own = scan_cli(cli) if cli is not None else {}
    script, prefix = None, []
    saved_path = list(sys.path)
    try:
        import importlib
        sys.path.insert(0, str(scripts_dir))
        gs = importlib.import_module('graph_snapshot')       # contract: entrypoints(cli_path=None) -> {sub: {...}}
        eps = gs.entrypoints(str(cli) if cli is not None else None) or {}
        ent = eps.get(sub) or {}
        script = ent.get('script') or None
    except Exception:
        script = None
    finally:
        sys.path[:] = saved_path
    if script:
        if sub in own and own[sub][0] == script:
            prefix = list(own[sub][1])
    elif sub in own:
        script, prefix = own[sub][0], list(own[sub][1])
    if not script:
        return None, 'unknown aidd subcommand %r (no _run("<script>.py", ...) found for it)' % sub
    path = Path(scripts_dir) / script
    if not path.is_file():
        return None, 'script %s not found in %s' % (script, scripts_dir)
    return path, prefix + rest


# ---------------------------------------------------------------------------------------------------- run

def run_traced(root, argv, graph_path=None, tracer_out=None, scripts_dir=None):
    """aidd:FR-018 run the script behind `aidd <argv>` in this process under a Tracer; return its exit code.
    `tracer_out` (a list) receives the Tracer. `graph_path` is accepted for symmetry with main (the merge is
    done by the caller with `merge_runtime`). `scripts_dir` runs the script from that folder (e.g. an older
    revision extracted with `git archive`) with its sibling imports resolved there; its files keep the FUNC ids
    `skill/scripts/<basename>::<qualname>` so two runs compare. Restores argv, cwd, sys.path, sys.modules
    (sibling script modules), env, profile hooks and os patches."""
    try:
        scripts_dir = Path(scripts_dir).expanduser().resolve() if scripts_dir else find_scripts_dir()
        script, sargv = resolve_command(list(argv), scripts_dir)
    except Exception as ex:
        script, sargv = None, 'cannot map the command (%s)' % ex.__class__.__name__
    if script is None:
        _warn(sargv)
        return 2
    bundle = [scripts_dir, Path.home() / '.claude' / 'skills' / 'aidd' / 'scripts']
    if os.environ.get('AIDD_HOME'):
        bundle.append(Path(os.environ['AIDD_HOME']).expanduser() / 'scripts')
    for rr in (_repo_root_of(scripts_dir), _repo_root_of(_HERE.parent)):
        if rr is not None:
            bundle += [rr / 'skill', rr / 'adapters']
    tracer = Tracer(root, bundle)
    if isinstance(tracer_out, list):
        tracer_out.append(tracer)

    saved_argv, saved_path = list(sys.argv), list(sys.path)
    saved_cwd = os.getcwd()
    had_env, old_env = 'AIDD_GRAPHS' in os.environ, os.environ.get('AIDD_GRAPHS')
    saved_os, saved_mods, stems = {}, {}, set()
    rc = 0

    def _fake_exit(code=0):
        _warn('the traced command called os._exit(%r): converted to SystemExit so the counts survive' % (code,))
        raise SystemExit(code)

    def _wrap_exec(name, orig):
        def _exec(*a, **k):
            _warn('the traced command re-execs (os.%s): the counts after this point are lost' % name)
            return orig(*a, **k)
        return _exec

    try:
        if hasattr(os, '_exit'):
            saved_os['_exit'] = os._exit
            os._exit = _fake_exit
        for name in _EXEC_NAMES:
            if hasattr(os, name):
                saved_os[name] = getattr(os, name)
                setattr(os, name, _wrap_exec(name, saved_os[name]))
        os.environ['AIDD_GRAPHS'] = 'off'
        os.chdir(str(root))
        sys.argv = [str(script)] + list(sargv)
        sys.path.insert(0, str(script.parent))
        try:                                                  # sibling imports must resolve to THIS folder
            stems = {p.stem for p in Path(script.parent).glob('*.py')} - {'graph_trace'}
        except Exception:
            stems = set()
        for m in stems:
            if m in sys.modules:
                saved_mods[m] = sys.modules.pop(m)
        tracer.start()
        try:
            runpy.run_path(str(script), run_name='__main__')
            rc = 0
        except SystemExit as ex:
            code = ex.code
            if code is None:
                rc = 0
            elif isinstance(code, int):
                rc = code
            else:
                try:
                    sys.stderr.write('%s\n' % code)
                except Exception:
                    pass
                rc = 1
        except KeyboardInterrupt:
            rc = 130
        except BaseException:
            import traceback
            traceback.print_exc()
            rc = 1
        finally:
            tracer.stop()
    except Exception as ex:                                   # setup failure (chdir, patching): never raise
        tracer.stop()
        _warn('trace setup failed (%s: %s)' % (ex.__class__.__name__, ex))
        rc = 2
    finally:
        for name, orig in saved_os.items():
            try:
                setattr(os, name, orig)
            except Exception:
                pass
        if had_env:
            os.environ['AIDD_GRAPHS'] = old_env
        else:
            os.environ.pop('AIDD_GRAPHS', None)
        try:
            os.chdir(saved_cwd)
        except Exception:
            pass
        sys.argv = saved_argv
        sys.path[:] = saved_path
        for m in stems:
            sys.modules.pop(m, None)
        sys.modules.update(saved_mods)
    if tracer.errors:
        _warn('%d tracer error(s) ignored (counts may be incomplete)' % tracer.errors)
    return rc


# ---------------------------------------------------------------------------------------------------- merge

def _static_read_match(rel, edges_from):
    for e in edges_from:
        lit = (e.get('path') or '').replace('\\', '/')
        while lit.startswith('./'):
            lit = lit[2:]
        if lit and lit != '*' and (rel == lit or rel.endswith('/' + lit)):
            return e
    return None


def merge_runtime(graph, counts):
    """aidd:FR-018 add integer `runtime` + `runtime_detail` to each counted FUNC -> SINK edge. A read whose path
    matches a literal static `reads` edge of the same FUNC lands on that edge; the rest on `sink:file:*`. Edges or
    SINK nodes the static graph lacks are created with `observed: true`. Idempotent (old runtime data is
    dropped first). Returns the graph."""
    try:
        graph = graph if isinstance(graph, dict) else {}
        nodes = graph.setdefault('nodes', [])
        edges = graph.setdefault('edges', [])
        edges[:] = [e for e in edges if not e.get('observed')]
        for e in edges:
            e.pop(RUNTIME_KEY, None)
            e.pop(RUNTIME_DETAIL_KEY, None)
        node_ids = {n.get('id') for n in nodes}
        index, reads_from = {}, {}
        for e in edges:
            if e.get('relation') in ('reads', 'spawns'):
                index.setdefault((e.get('source'), e.get('target')), e)
                if e.get('relation') == 'reads':
                    reads_from.setdefault(e.get('source'), []).append(e)

        def _edge(src, tgt):
            e = index.get((src, tgt))
            if e is None:
                kind = tgt.split(':')[1] if tgt.count(':') >= 2 else 'file'
                if tgt not in node_ids:
                    nodes.append({'id': tgt, 'type': 'SINK', 'label': tgt.split(':', 2)[-1], 'source_file': '',
                                  'source_location': '', 'sink_kind': kind, 'observed': True})
                    node_ids.add(tgt)
                e = {'source': src, 'target': tgt, 'relation': 'spawns' if kind == 'spawn' else 'reads',
                     'observed': True}
                edges.append(e)
                index[(src, tgt)] = e
            return e

        def _add(e, n, detail_key, label, rereads):
            e[RUNTIME_KEY] = int(e.get(RUNTIME_KEY, 0)) + int(n)
            d = e.setdefault(RUNTIME_DETAIL_KEY, {})
            if label is not None:
                bucket = d.setdefault(detail_key, {})
                bucket[label] = bucket.get(label, 0) + int(n)
            if rereads:
                d['rereads'] = d.get('rereads', 0) + int(rereads)

        for (fid, sink) in sorted(counts or {}):
            c = counts[(fid, sink)]
            if sink == READ_SINK:
                rest_rereads = int(c.get('rereads', 0))
                for rel, n in sorted((c.get('by_path') or {}).items()):
                    hit = _static_read_match(rel, reads_from.get(fid, []))
                    _add(hit if hit is not None else _edge(fid, READ_SINK), n, 'by_path', rel, 0)
                if rest_rereads:
                    _add(_edge(fid, READ_SINK), 0, 'by_path', None, rest_rereads)
            else:
                e = _edge(fid, sink)
                by = c.get('by_argv0') or {}
                if by:
                    for a0, n in sorted(by.items()):
                        _add(e, n, 'by_argv0', a0, 0)
                else:
                    _add(e, int(c.get('count', 0)), 'by_argv0', None, 0)
                if c.get('rereads'):
                    _add(e, 0, 'by_argv0', None, c['rereads'])
    except Exception as ex:
        _warn('merge_runtime failed (%s)' % ex.__class__.__name__)
    return graph


# ---------------------------------------------------------------------------------------------------- cli

def _load_graph(path):
    try:
        if path and Path(path).is_file():
            g = json.loads(Path(path).read_text(encoding='utf-8'))
            if isinstance(g, dict):
                return g
    except Exception as ex:
        _warn('graph %s not loaded (%s); merging into an empty graph' % (path, ex.__class__.__name__))
    return {'nodes': [], 'edges': []}


def print_table(counts, totals, out=None):
    out = out or sys.stdout
    rows = sorted(counts.items(), key=lambda kv: (-kv[1]['count'], kv[0][0], kv[0][1]))
    out.write('\nruntime trace: top %d FUNC -> sink pairs by count\n' % TOP_N)
    out.write('%7s %7s  %s\n' % ('count', 'reread', 'func -> sink  [top detail]'))
    for (fid, sink), c in rows[:TOP_N]:
        det = c['by_path'] or c['by_argv0']
        top = sorted(det.items(), key=lambda kv: (-kv[1], kv[0]))[:1]
        extra = '  [%s x%d]' % top[0] if top else ''
        out.write('%7d %7d  %s -> %s%s\n' % (c['count'], c['rereads'], fid, sink, extra))
    if len(rows) > TOP_N:
        out.write('  ... %d more pair(s)\n' % (len(rows) - TOP_N))
    out.write('totals: reads %d, spawns %d, rereads %d, pairs %d\n'
              % (totals.get('reads', 0), totals.get('spawns', 0), totals.get('rereads', 0), len(rows)))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = []
    if '--' in argv:
        i = argv.index('--')
        argv, cmd = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(
        prog='graph_trace.py',
        usage='graph_trace.py --root <project> [--graph <code.json>] [--out <json>] -- <aidd command ...>',
        description='Run one aidd command in process under a stdlib profiler and count FUNC -> sink events '
                    '(file reads, spawns, re-reads) as the runtime overlay of the code graph (aidd:FR-018).')
    ap.add_argument('--root', default=None, help='traced project root (default: cwd)')
    ap.add_argument('--graph', default=None, help='static code graph (default: <root>/%s)' % GRAPH_REL)
    ap.add_argument('--out', default=None, help='write the graph with runtime counts merged to this file')
    ap.add_argument('--scripts-dir', default=None,
                    help='run the command script from this folder (e.g. an older revision from git archive); '
                         'FUNC ids stay skill/scripts/<basename>::<qualname> so runs compare')
    a = ap.parse_args(argv)
    if not cmd:
        ap.print_usage(sys.stderr)
        sys.stderr.write('graph_trace.py: error: missing "-- <aidd command ...>"\n')
        return 2
    root = Path(a.root or os.getcwd()).resolve()
    holder = []
    rc = run_traced(root, cmd, a.graph, tracer_out=holder, scripts_dir=a.scripts_dir)
    if not holder:
        return rc
    tracer = holder[0]
    try:
        print_table(tracer.counts, tracer.totals)
        if a.out:
            graph = merge_runtime(_load_graph(a.graph or (root / GRAPH_REL)), tracer.counts)
            outp = Path(a.out)
            outp.parent.mkdir(parents=True, exist_ok=True)
            tmp = outp.with_name('%s.tmp.%d' % (outp.name, os.getpid()))
            tmp.write_text(json.dumps(graph, indent=1, sort_keys=True), encoding='utf-8')
            os.replace(str(tmp), str(outp))
            print('runtime graph written: %s' % outp)
    except Exception as ex:
        _warn('report/merge failed (%s); the traced exit code is kept' % ex.__class__.__name__)
    return rc


if __name__ == '__main__':
    sys.exit(main())
