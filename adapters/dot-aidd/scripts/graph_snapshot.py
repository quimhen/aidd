#!/usr/bin/env python3
"""aidd graph snapshots — canonical, hash-logged snapshots of the AIDD graphs, their diff, the content-hash
change set since a spec opened, and the static "same step runs several times" report.

Spec 004 amendment 2026-10-24 (aidd:FR-017, aidd:FR-019, aidd:FR-020, aidd:FR-023, aidd:FR-024, aidd:T-15).

  snapshot <name> --label L [--rev R] [--replace]
      writes .aidd/graphs/snapshots/<name>/<L>.json (the exact canonical bytes) and logs a `graph_snapshot`
      event {name, label, sha256, nodes, edges, rev[, spec]} in the PROJECT evidence log. `--rev` builds from
      `git archive <rev>` extracted into a temp dir (the worktree is never touched). A used label is refused
      unless --replace, which logs a NEW event (diff trusts the most recent one).
  diff <A> <B> [--name N] [--full]
      recomputes each snapshot's sha256 and refuses (exit 2, `snapshot altered: <L>` / `no event for <L>`)
      when it differs from the most recent logged event; else prints counts, added/removed nodes and edges and
      metric deltas (sink call counts, repeats, runtime counts), capped at DIFF_CAP lines unless --full.
  changed [--spec ID] [--name code] [--full]
      files whose git blob sha differs from the `<spec>@open` baseline (added/modified/removed; one
      `git hash-object` pass, never stat/mtime) plus `affected` (one hop of reverse imports/calls).
  repeats [--cmd SUB] [--label L] [--include-ambiguous]
      sinks, unresolved calls and FUNCs reached from a command's entry point by more than one distinct call
      path, or called inside a loop. Unknown --cmd exits 2.

Exit codes: 0 ok, 2 refusal. Never raises from analysis. Stdlib only; aidd_evidence is imported lazily
inside try/except (no event log = refusal, never a crash).
"""
import argparse
import ast
import glob as _glob
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
SNAP_DIR_REL = '.aidd/graphs/snapshots'
DIFF_CAP = 25
LABEL_RE = re.compile(r'^[A-Za-z0-9._@-]{1,64}$')
NAME_RE = re.compile(r'^[A-Za-z0-9._-]{1,64}$')
CODE_GRAPH_REL = '.aidd/graphs/code.json'
PROGRESS_REL = '.aidd/graphs/progress.json'
SPEC_INDEX_REL = 'specs/index.toon'
MIGRATION_DIRS = ('supabase/migrations', 'migrations', 'db/migrations', 'prisma/migrations', 'db/migrate')
NAMES = ('code', 'method', 'spec', 'progress', 'db-schema', 'db-dml')
PATH_DEPTH = 12
PATH_BIG = 10 ** 6
TRAVERSE = ('calls', 'reads', 'spawns')
GIT_TIMEOUT = 120
SQL_TIMEOUT = 300
CLI_SESSION = 'aidd-graphs-cli'
_ABS_RE = re.compile(r'^(?:[A-Za-z]:[\\/]|\\\\|/)')
_CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


# ---------------------------------------------------------------------------------------------------- helpers

def _evidence():
    """aidd_evidence module or None (never raises; scripts must run without it)."""
    try:
        if str(HERE) not in sys.path:
            sys.path.insert(0, str(HERE))
        import aidd_evidence  # noqa: WPS433 (lazy on purpose)
        return aidd_evidence
    except Exception:
        return None


def _module(name):
    try:
        if str(HERE) not in sys.path:
            sys.path.insert(0, str(HERE))
        return __import__(name)
    except Exception:
        return None


def _session():
    if os.environ.get('AIDD_TESTING') == '1':
        for k in ('AIDD_SESSION_ID', 'CLAUDE_SESSION_ID'):
            v = os.environ.get(k, '').strip()
            if v:
                return v
    return CLI_SESSION


def _git(root, args, timeout=GIT_TIMEOUT):
    """stdout bytes or None. Always `git -C root`."""
    try:
        env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', LC_ALL='C')
        r = subprocess.run(['git', '-C', str(root)] + list(args), env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=timeout, creationflags=_CREATE_NO_WINDOW)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _valid_label(label):
    return isinstance(label, str) and bool(LABEL_RE.match(label)) and '..' not in label


def _valid_name(name):
    return isinstance(name, str) and bool(NAME_RE.match(name)) and '..' not in name


def snap_path(root, name, label):
    return Path(root) / SNAP_DIR_REL / name / (label + '.json')


def _load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8', errors='replace'))
    except Exception:
        return None


def _edges_of(g):
    if not isinstance(g, dict):
        return []
    return list(g.get('edges') or g.get('links') or [])


def _cap(lines, full, cap=DIFF_CAP):
    if full or len(lines) <= cap:
        return lines
    return lines[:cap - 1] + ['... %d more (--full)' % (len(lines) - cap + 1)]


# ---------------------------------------------------------------------------------------------------- canonical

def _strip_abs(obj, root=None):
    """Copy of `obj` with absolute paths made root-relative ('/') or dropped (aidd:FR-019)."""
    rootp = os.path.normcase(os.path.abspath(str(root))) if root else None
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(v, str) and _ABS_RE.match(v):
                if rootp:
                    try:
                        cand = os.path.normcase(os.path.abspath(v))
                        if cand == rootp or cand.startswith(rootp + os.sep):
                            out[k] = os.path.relpath(os.path.abspath(v), str(root)).replace('\\', '/')
                    except Exception:
                        pass
                continue
            out[k] = _strip_abs(v, root)
        return out
    if isinstance(obj, list):
        return [_strip_abs(v, root) for v in obj if not (isinstance(v, str) and _ABS_RE.match(v))]
    return obj


def _edge_sort_key(e):
    attrs = {k: v for k, v in e.items() if k not in ('source', 'target', 'relation')}
    return (str(e.get('source', '')), str(e.get('target', '')), str(e.get('relation', '')),
            json.dumps(attrs, sort_keys=True, ensure_ascii=True, separators=(',', ':')))


def canonical(graph):  # aidd:FR-019
    """Canonical bytes: {schema, name, label, rev, nodes (by id), edges (by source,target,relation,attrs)[, inputs]}
    with sort_keys, separators (',',':'), ensure_ascii; `generated`, `warnings` and absolute paths excluded.
    FILE nodes keep `sha` (and `mirror_of` for byte-identical copies); per-file facts live in code_graph's
    sidecar cache and are never part of a snapshot."""
    g = graph if isinstance(graph, dict) else {}
    nodes = [_strip_abs(n) for n in (g.get('nodes') or []) if isinstance(n, dict)]
    edges = [_strip_abs(e) for e in _edges_of(g) if isinstance(e, dict)]
    nodes.sort(key=lambda n: (str(n.get('id', n.get('name', ''))), json.dumps(n, sort_keys=True)))
    edges.sort(key=_edge_sort_key)
    body = {'schema': g.get('schema', 1), 'name': str(g.get('name', '')), 'label': str(g.get('label', '')),
            'rev': str(g.get('rev', '') or ''), 'nodes': nodes, 'edges': edges}
    if isinstance(g.get('inputs'), dict):
        body['inputs'] = {str(k): str(v) for k, v in g['inputs'].items() if not _ABS_RE.match(str(k))}
    return json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


# ---------------------------------------------------------------------------------------------------- builders

def _build_code(root, previous=None):
    cg = _module('code_graph')
    if cg is None:
        raise RuntimeError('code_graph.py not found next to graph_snapshot.py')
    graph, _stats = cg.build(root, previous=previous)
    return graph


def _current_code_graph(root):
    """Current code graph, built incrementally from code_graph's sidecar cache (`.aidd/graphs/code.json` +
    CACHE_SUFFIX) when present; nothing is written."""
    return _build_code(root, previous=_code_cache(root))


def _code_cache(root):
    cg = _module('code_graph')
    suffix = getattr(cg, 'CACHE_SUFFIX', '.cache.json') if cg is not None else '.cache.json'
    prev = _load_json(Path(root) / (CODE_GRAPH_REL + suffix))
    return prev if isinstance(prev, dict) else None


def _method_inputs(root):
    mg = _module('method_graph')
    cg = _module('code_graph')
    if mg is None or cg is None:
        return {}
    try:
        rels = mg._list_sources(root)
    except Exception:
        rels = []
    try:
        return cg.file_shas(root, rels)
    except Exception:
        return {}


def _build_method(root):
    mg = _module('method_graph')
    if mg is None or not hasattr(mg, 'build'):
        raise RuntimeError('method_graph.py is not available: the method graph cannot be built')
    g = mg.build(root)
    if isinstance(g, tuple):
        g = g[0]
    g = dict(g)
    g['inputs'] = _method_inputs(root)  # content shas of the method inputs, for `changed --name method`
    return g


def _migration_dirs(root):
    out = []
    for d in MIGRATION_DIRS:
        p = Path(root) / d
        if p.is_dir() and any(p.glob('*.sql')):
            out.append(d)
    return out


def _build_sql(root, kind):
    dirs = _migration_dirs(root)
    if not dirs:
        raise RuntimeError('no migrations dir with *.sql under the root (looked in %s)' % ', '.join(MIGRATION_DIRS))
    tmp = tempfile.mkdtemp(prefix='aidd-snap-sql-')
    try:
        out = os.path.join(tmp, 'g.json')
        try:
            r = subprocess.run([sys.executable, str(HERE / 'sql_graph.py'), '--root', str(root), '--out', out,
                                '--kind', kind] + dirs, cwd=str(root), stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=SQL_TIMEOUT, creationflags=_CREATE_NO_WINDOW)
        except subprocess.TimeoutExpired:
            raise RuntimeError('sql_graph.py --kind %s timed out after %ds' % (kind, SQL_TIMEOUT))
        if r.returncode != 0:
            raise RuntimeError('sql_graph.py --kind %s failed (exit %d): %s'
                               % (kind, r.returncode, r.stderr.decode('utf-8', 'replace').strip()[-300:]))
        g = _load_json(out)
        if not isinstance(g, dict):
            raise RuntimeError('sql_graph.py wrote no readable graph')
        return {'schema': 1, 'nodes': g.get('nodes') or [], 'edges': _edges_of(g)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _build_spec(root):
    p = Path(root) / SPEC_INDEX_REL
    if not p.is_file():
        raise RuntimeError('%s not found (run `aidd reindex`)' % SPEC_INDEX_REL)
    text = p.read_text(encoding='utf-8', errors='replace')
    fs = _module('find_spec')
    nodes, edges = [], []
    specs = None
    if fs is not None and hasattr(fs, 'loads_index'):
        try:
            res = fs.loads_index(text)
            specs = res[1] if isinstance(res, tuple) else (res.get('specs') if isinstance(res, dict) else None)
        except Exception:
            specs = None
    if isinstance(specs, dict):
        for sid in sorted(specs):
            s = specs[sid] or {}
            nodes.append({'id': sid, 'type': 'SPEC', 'label': str(s.get('title', '')),
                          'codes': sorted(s.get('codes') or [])})
            for c in sorted(set(s.get('codes') or [])):
                edges.append({'source': sid, 'target': c, 'relation': 'defines'})
    else:  # no parser: one node per data row (volatile header lines skipped)
        for line in text.splitlines():
            t = line.strip()
            if t and line.startswith(' ') and ',' in t:
                nodes.append({'id': t.split(',', 1)[0], 'type': 'SPEC', 'label': ''})
    return {'schema': 1, 'nodes': nodes, 'edges': edges}


def _build_progress(root):
    g = _load_json(Path(root) / PROGRESS_REL)
    if not isinstance(g, dict):
        raise RuntimeError('%s not found or unreadable (run `aidd progress`)' % PROGRESS_REL)
    return {'schema': 1, 'nodes': g.get('nodes') or [], 'edges': _edges_of(g)}


def _build(root, name):
    if name == 'code':
        return _build_code(root, previous=_code_cache(root))
    if name == 'method':
        return _build_method(root)
    if name in ('db-schema', 'db-dml'):
        return _build_sql(root, name.split('-', 1)[1])
    if name == 'spec':
        return _build_spec(root)
    if name == 'progress':
        return _build_progress(root)
    raise RuntimeError('unknown graph %r (known: %s)' % (name, ', '.join(NAMES)))


def _resolve_rev(root, rev):
    if not rev or rev.startswith('-') or any(c.isspace() for c in rev):
        return None
    out = _git(root, ['rev-parse', '--verify', '--quiet', rev + '^{commit}'], timeout=30)
    if not out:
        return None
    sha = out.decode('ascii', 'replace').strip()
    return sha if re.match(r'^[0-9a-f]{40}([0-9a-f]{24})?$', sha) else None


def _extract_tar(data, dest):
    dest = Path(dest)
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as tf:
        for m in tf.getmembers():
            name = m.name.replace('\\', '/')
            parts = [p for p in name.split('/') if p not in ('', '.')]
            if not parts or name.startswith('/') or '..' in parts or _ABS_RE.match(name):
                continue
            target = dest.joinpath(*parts)
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif m.isfile():
                f = tf.extractfile(m)
                if f is None:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(str(target), 'wb') as w:
                    shutil.copyfileobj(f, w)
            # links and specials are skipped on purpose


def _build_at_rev(root, name, rev):  # aidd:FR-019
    """(graph, full sha) built from `git archive <rev>` in a temp dir; the worktree is never touched."""
    sha = _resolve_rev(root, rev)
    if sha is None:
        raise RuntimeError('unknown git revision %r' % rev)
    data = _git(root, ['archive', '--format=tar', sha])
    if data is None:
        raise RuntimeError('git archive %s failed' % rev)
    tmp = tempfile.mkdtemp(prefix='aidd-snap-rev-')
    try:
        _extract_tar(data, tmp)
        g = _build(tmp, name)
        g = _strip_abs(g, tmp)
        return g, sha
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------------------------------- snapshot

def _write_tmp(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('%s.tmp.%d' % (path.name, os.getpid()))
    with open(str(tmp), 'wb') as f:
        f.write(data)
    return tmp


def snapshot(root, name, label, rev=None, replace=False):  # aidd:FR-019
    """Write snapshots/<name>/<label>.json (exact canonical bytes) and log a `graph_snapshot` event.
    Returns {rc, message, path, sha256, nodes, edges, rev}. rc 2 = refusal (invalid/used label, build error,
    event not logged). Never raises."""
    res = {'rc': 2, 'message': '', 'path': '', 'sha256': '', 'nodes': 0, 'edges': 0, 'rev': ''}
    try:
        root = Path(root).resolve()
        if not _valid_name(name):
            res['message'] = 'invalid graph name %r' % (name,)
            return res
        if not _valid_label(label):
            res['message'] = ('invalid label %r: must match %s and contain no ".."' % (label, LABEL_RE.pattern))
            return res
        path = snap_path(root, name, label)
        ev = _evidence()
        prior = ev.graph_snapshot_events(root, name, label) if ev is not None else []
        if (path.exists() or prior) and not replace:
            res['message'] = 'label %r already used for %s (use --replace to log a new event)' % (label, name)
            return res
        if ev is None:
            res['message'] = 'aidd_evidence.py is not available: the snapshot event cannot be logged (refused)'
            return res
        try:
            if rev:
                graph, full = _build_at_rev(root, name, rev)
            else:
                graph, full = _strip_abs(_build(root, name), root), ''
        except Exception as ex:
            res['message'] = 'cannot build %s: %s' % (name, ex)
            return res
        graph = dict(graph)
        graph.update({'name': name, 'label': label, 'rev': full})
        data = canonical(graph)
        body = json.loads(data.decode('ascii'))
        sha = _sha256(data)
        n_nodes, n_edges = len(body['nodes']), len(body['edges'])
        spec = label[:-len('@open')] if label.endswith('@open') else ''
        tmp = _write_tmp(path, data)
        try:
            ok = ev.append_graph_snapshot(root, _session(), name, label, sha, n_nodes, n_edges, rev=full, spec=spec)
            if not ok:
                res['message'] = 'graph_snapshot event not logged (project log unavailable): snapshot refused'
                return res
            os.replace(str(tmp), str(path))
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
        res.update({'rc': 0, 'path': str(path), 'sha256': sha, 'nodes': n_nodes, 'edges': n_edges, 'rev': full,
                    'message': 'snapshot %s/%s: sha256 %s, %d nodes, %d edges, rev %s%s'
                               % (name, label, sha, n_nodes, n_edges, full or 'worktree',
                                  ' (replaced: %d earlier event(s))' % len(prior) if prior else '')})
        return res
    except Exception as ex:
        res['message'] = 'snapshot failed: %s' % ex
        return res


# ---------------------------------------------------------------------------------------------------- diff

def _sink_calls(g):
    ids = {n.get('id') for n in g.get('nodes', []) if n.get('type') == 'SINK'}
    c = {}
    for e in g.get('edges', []):
        if e.get('relation') in TRAVERSE and e.get('target') in ids:
            c[e['target']] = c.get(e['target'], 0) + 1
    return c


def _runtime(g):
    out = {}
    for e in g.get('edges', []):
        if isinstance(e.get('runtime'), int):
            out['%s -> %s' % (e.get('source'), e.get('target'))] = e['runtime']
    return out


def _repeat_total(g):
    try:
        eps = entrypoints()
        adj = _adjacency(g, False)
        memo = {}
        total = 0
        for sub in sorted(eps):
            fid = _entry_id(g, eps[sub])
            if fid:
                total += len(_repeat_items(g, adj, fid, memo))
        return total
    except Exception:
        return None


def _ext_totals(g):
    """(total `ext` entries, total `ext_in_loop` entries) over the FUNC nodes; missing key = empty."""
    t = tl = 0
    for n in g.get('nodes', []):
        if n.get('type') == 'FUNC':
            t += len(n.get('ext') or ())
            tl += len(n.get('ext_in_loop') or ())
    return t, tl


def _find_name(root, a, b):
    base = Path(root) / SNAP_DIR_REL
    try:
        names = sorted(p.name for p in base.iterdir() if p.is_dir())
    except OSError:
        names = []
    both = [n for n in names if (base / n / (a + '.json')).is_file() and (base / n / (b + '.json')).is_file()]
    if 'code' in both:
        return 'code'
    return both[0] if both else None


def diff(root, a, b, full=False, name=None):  # aidd:FR-020
    """(rc, text). Verifies each label's file sha256 against its MOST RECENT `graph_snapshot` event first."""
    try:
        root = Path(root).resolve()
        for lab in (a, b):
            if not _valid_label(lab):
                return 2, 'invalid label %r' % (lab,)
        name = name or _find_name(root, a, b)
        if not name or not _valid_name(name):
            return 2, 'no graph has both snapshots %r and %r under %s' % (a, b, SNAP_DIR_REL)
        ev = _evidence()
        head, bodies, bad = [], {}, []
        for lab in (a, b):
            p = snap_path(root, name, lab)
            try:
                data = p.read_bytes()
            except OSError:
                bad.append('snapshot missing: %s (%s)' % (lab, p))
                continue
            sha = _sha256(data)
            evs = ev.graph_snapshot_events(root, name, lab) if ev is not None else []
            if not evs:
                bad.append('no event for %s' % lab)
                continue
            last = evs[-1].get('detail') or {}
            if str(last.get('sha256', '')) != sha:
                bad.append('snapshot altered: %s (file sha256 %s, logged %s)' % (lab, sha, last.get('sha256', '')))
                continue
            line = '%s: sha256 %s, %d event(s), rev %s' % (lab, sha, len(evs), last.get('rev') or 'worktree')
            if len(evs) > 1:
                line += '  WARNING: label was replaced'
            head.append(line)
            try:
                bodies[lab] = json.loads(data.decode('ascii'))
            except Exception:
                bad.append('snapshot unreadable: %s' % lab)
        if bad:
            return 2, '\n'.join(bad)
        ga, gb = bodies[a], bodies[b]
        na = {n.get('id'): n for n in ga.get('nodes', [])}
        nb = {n.get('id'): n for n in gb.get('nodes', [])}
        ka = {_edge_sort_key(e)[:3] for e in ga.get('edges', [])}
        kb = {_edge_sort_key(e)[:3] for e in gb.get('edges', [])}
        out = ['diff %s %s -> %s' % (name, a, b)] + head
        out.append('nodes %d -> %d (+%d -%d), edges %d -> %d (+%d -%d)' % (
            len(na), len(nb), len(set(nb) - set(na)), len(set(na) - set(nb)),
            len(ka), len(kb), len(kb - ka), len(ka - kb)))
        body = []
        sa, sb = _sink_calls(ga), _sink_calls(gb)
        for k in sorted(set(sa) | set(sb)):
            if sa.get(k, 0) != sb.get(k, 0):
                body.append('sink calls %s: %d -> %d' % (k, sa.get(k, 0), sb.get(k, 0)))
        if name == 'code':
            (xa, xla), (xb, xlb) = _ext_totals(ga), _ext_totals(gb)
            body.append('ext entries: %d -> %d (in loop %d -> %d)' % (xa, xb, xla, xlb))
            ra, rb = _repeat_total(ga), _repeat_total(gb)
            if ra is not None and rb is not None:
                body.append('repeats (all entry points): %d -> %d' % (ra, rb))
        ta, tb = _runtime(ga), _runtime(gb)
        for k in sorted(set(ta) | set(tb)):
            if ta.get(k, 0) != tb.get(k, 0):
                body.append('runtime %s: %d -> %d' % (k, ta.get(k, 0), tb.get(k, 0)))
        body += ['+ node %s' % k for k in sorted(set(nb) - set(na))]
        body += ['- node %s' % k for k in sorted(set(na) - set(nb))]
        body += ['+ edge %s -> %s (%s)' % k for k in sorted(kb - ka)]
        body += ['- edge %s -> %s (%s)' % k for k in sorted(ka - kb)]
        return 0, '\n'.join(out + _cap(body, full))
    except Exception as ex:
        return 2, 'diff failed: %s' % ex


# ---------------------------------------------------------------------------------------------------- changed

def _file_shas_of(graph):
    out = {}
    for n in graph.get('nodes', []):
        if n.get('type') == 'FILE' and n.get('sha'):
            out[str(n.get('id'))] = str(n['sha'])
    return out


def _affected(graph, changed_files):
    """One hop of reverse imports/calls from the changed files (aidd:FR-024). Mirror FILE nodes (`mirror_of`,
    byte-identical copies with no FUNC/edges) are never searched for callers."""
    owner, mirrors = {}, set()
    for n in graph.get('nodes', []):
        if n.get('type') == 'FILE':
            if n.get('mirror_of'):
                mirrors.add(n.get('id'))
                continue
            owner[n.get('id')] = n.get('id')
        elif n.get('source_file'):
            owner[n.get('id')] = n.get('source_file')
    changed_files = set(changed_files)
    hit = set()
    for e in graph.get('edges', []):
        if e.get('relation') not in ('imports', 'calls'):
            continue
        tf, sf = owner.get(e.get('target')), owner.get(e.get('source'))
        if tf in changed_files and sf and sf not in changed_files and sf not in mirrors:
            hit.add(sf)
    return sorted(hit)


METHOD_SOURCES = ('skill/SKILL.md', 'skill/AIDD.md', 'commands/*.md', 'skill/templates/*')


def manifest_path(root, spec):
    return Path(root) / SNAP_DIR_REL / 'manifests' / ('%s@open.json' % spec)


def _method_sources(root):
    """Existing methodology source files (method_graph.SOURCES when importable); no parsing."""
    mg = _module('method_graph')
    pats = tuple(getattr(mg, 'SOURCES', ())) if mg is not None else ()
    found = set()
    for pat in pats or METHOD_SOURCES:
        for p in _glob.glob(str(Path(root) / pat)):
            if os.path.isfile(p):
                found.add(Path(p).resolve().relative_to(Path(root).resolve()).as_posix())
    return sorted(found)


def open_manifest(root, spec, replace=False):  # aidd:FR-023
    """Write snapshots/manifests/<spec>@open.json = {spec, taken, graphs: {code: {rel: sha}, method: {rel: sha}}}:
    the content sha of every file each graph watches, in ONE code_graph.file_shas pass. No graph build, no
    parsing, no evidence event. Refuses (rc 2) an existing manifest unless replace. Returns
    {rc, spec, path, files, message}. Never raises."""
    res = {'rc': 2, 'spec': str(spec or ''), 'path': '', 'files': 0, 'message': ''}
    try:
        root = Path(root).resolve()
        if not spec or not _valid_label(str(spec)) or not _valid_label('%s@open' % spec):
            res['message'] = 'invalid spec id %r: must match %s and contain no ".."' % (spec, LABEL_RE.pattern)
            return res
        path = manifest_path(root, spec)
        res['path'] = str(path)
        if path.exists() and not replace:
            res['message'] = 'manifest %s already exists (use --replace)' % path
            return res
        cg = _module('code_graph')
        if cg is None:
            res['message'] = 'code_graph.py is not available: manifest not written'
            return res
        code_rels = list(cg.list_files(root, cg.default_globs(root)))
        method_rels = _method_sources(root)
        shas = cg.file_shas(root, sorted(set(code_rels) | set(method_rels)))
        graphs = {'code': {r: shas[r] for r in code_rels if r in shas},
                  'method': {r: shas[r] for r in method_rels if r in shas}}
        import time as _time
        body = {'spec': str(spec), 'taken': _time.time(), 'graphs': graphs}
        tmp = _write_tmp(path, json.dumps(body, sort_keys=True, separators=(',', ':'),
                                          ensure_ascii=True).encode('ascii'))
        try:
            os.replace(str(tmp), str(path))
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
        res['files'] = len(graphs['code']) + len(graphs['method'])
        res['rc'] = 0
        res['message'] = 'manifest %s@open: %d code files, %d method files -> %s' % (
            spec, len(graphs['code']), len(graphs['method']), path)
        return res
    except Exception as ex:
        res['message'] = 'manifest failed: %s' % ex
        res['rc'] = 2
        return res


def changed(root, spec=None, name='code'):  # aidd:FR-023 aidd:FR-024
    """{rc, spec, baseline, added, modified, removed, affected, message}. rc 2 without a baseline."""
    res = {'rc': 2, 'spec': spec or '', 'name': name, 'baseline': '', 'added': [], 'modified': [],
           'removed': [], 'affected': [], 'message': ''}
    try:
        root = Path(root).resolve()
        if not spec:
            ev = _evidence()
            spec = ev.get_active_spec(root) if ev is not None else None
            res['spec'] = spec or ''
        if not spec:
            res['message'] = 'no active spec: pass --spec <full spec id>'
            return res
        label = '%s@open' % spec
        if not _valid_label(label) or not _valid_name(name):
            res['message'] = 'invalid spec id or graph name'
            return res
        # baseline order: manifest graphs[name] (taken at activation, no graph built), then the full snapshot
        old, base = None, None
        mpath = manifest_path(root, spec)
        man = _load_json(mpath)
        if isinstance(man, dict) and isinstance((man.get('graphs') or {}).get(name), dict):
            old = {str(k): str(v) for k, v in man['graphs'][name].items()}
            res['baseline'] = str(mpath)
        else:
            path = snap_path(root, name, label)
            base = _load_json(path)
            if isinstance(base, dict):
                old = (dict(base.get('inputs') or {}) if name != 'code' else {}) or _file_shas_of(base)
                res['baseline'] = str(path)
        if old is None:
            res['message'] = ('no baseline for %s: create the manifest with `aidd rules activate %s`, or a graph '
                              'snapshot with `aidd graphs snapshot %s --label %s`' % (label, spec, name, label))
            return res
        cg = _module('code_graph')
        if cg is None:
            res['message'] = 'code_graph.py is not available'
            return res
        if name == 'code':
            rels = cg.list_files(root, cg.default_globs(root))
        else:
            rels = _method_sources(root) if name == 'method' else []
            rels = sorted(set(rels) | {r for r in old if (root / r).is_file()})
        cur = cg.file_shas(root, rels)  # one `git hash-object --stdin-paths` pass, never stat/mtime
        res['added'] = sorted(set(cur) - set(old))
        res['removed'] = sorted(set(old) - set(cur))
        res['modified'] = sorted(r for r in set(cur) & set(old) if cur[r] != old[r])
        ch = set(res['added']) | set(res['modified']) | set(res['removed'])
        if ch and name == 'code':
            # affected only from an EXISTING code graph: never build or parse one just for this
            current_graph = _load_json(root / CODE_GRAPH_REL)
            if not isinstance(current_graph, dict):
                res['message'] = ('affected not computed: no %s (run `aidd graphs refresh code`)'
                                  % CODE_GRAPH_REL)
            else:
                try:
                    aff = set(_affected(current_graph, ch))
                    if isinstance(base, dict):
                        aff |= set(_affected(base, res['removed']))
                    res['affected'] = sorted(aff - ch)
                except Exception as ex:
                    res['message'] = 'affected not computed: %s' % ex
        res['rc'] = 0
        return res
    except Exception as ex:
        res['message'] = 'changed failed: %s' % ex
        return res


# ---------------------------------------------------------------------------------------------------- entrypoints

def _cli_path(cli_path=None):
    if cli_path:
        p = Path(cli_path)
        return p if p.is_file() else None
    for cand in (HERE.parent.parent / 'aidd' / 'cli.py',):
        if cand.is_file():
            return cand
    try:
        import importlib.util
        spec = importlib.util.find_spec('aidd.cli')
        if spec is not None and spec.origin and os.path.isfile(spec.origin):
            return Path(spec.origin)
    except Exception:
        pass
    return None


def _script_funcs(script):
    """Top-level function names of skill/scripts/<script> (empty when absent)."""
    p = HERE / script
    try:
        tree = ast.parse(p.read_text(encoding='utf-8', errors='replace'))
    except Exception:
        return set()
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _run_calls(node):
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == '_run' and n.args:
            a0 = n.args[0]
            if isinstance(a0, ast.Constant) and isinstance(a0.value, str) and a0.value.endswith('.py'):
                first = None
                if len(n.args) > 1 and isinstance(n.args[1], (ast.List, ast.Tuple)) and n.args[1].elts:
                    e0 = n.args[1].elts[0]
                    if isinstance(e0, ast.Constant) and isinstance(e0.value, str) and not e0.value.startswith('-'):
                        first = e0.value
                yield a0.value, first


def entrypoints(cli_path=None):  # aidd:FR-017 (contract shared with graph_trace.py: do not change)
    """{subcommand: {"script": "<file>.py", "func": "cmd_<sub>" or "main"}} from an `ast` scan of the
    `_run("<script>.py", [<subcommand>, ...])` calls of aidd/cli.py (subcommand = the enclosing `cmd_<x>`
    function or `p_<x>.set_defaults(func=lambda ...)`; a literal first list element is also registered),
    plus `hook:<name>` -> main for every skill/hooks/*.py. {} when cli.py is not found."""
    out = {}
    try:
        p = _cli_path(cli_path)
        if p is None:
            return {}
        tree = ast.parse(p.read_text(encoding='utf-8', errors='replace'))
        funcs_cache = {}

        def func_for(script, subs):
            if script not in funcs_cache:
                funcs_cache[script] = _script_funcs(script)
            for s in subs:
                if s and ('cmd_' + s.replace('-', '_')) in funcs_cache[script]:
                    return 'cmd_' + s.replace('-', '_')
            return 'main'

        def add(sub, script, first):
            if not sub or sub in out:
                return
            out[sub] = {'script': script, 'func': func_for(script, [first, sub])}

        for n in tree.body:
            if isinstance(n, ast.FunctionDef) and n.name.startswith('cmd_'):
                sub = n.name[4:].replace('_', '-')
                for script, first in _run_calls(n):
                    add(sub, script, first)
                    if first and first != sub:
                        add(first, script, first)
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'set_defaults'):
                continue
            recv = n.func.value
            if not (isinstance(recv, ast.Name) and recv.id.startswith('p_')):
                continue
            for kw in n.keywords:
                if kw.arg == 'func' and isinstance(kw.value, ast.Lambda):
                    for script, first in _run_calls(kw.value):
                        add(recv.id[2:].replace('_', '-'), script, first)
        hooks = HERE.parent / 'hooks'
        for hp in sorted(_glob.glob(str(hooks / '*.py'))):
            base = os.path.basename(hp)
            if base.startswith('_'):
                continue
            out['hook:' + base[:-3]] = {'script': base, 'func': 'main'}
    except Exception:
        return out
    return out


# ---------------------------------------------------------------------------------------------------- repeats

def _entry_id(graph, ep):
    """FUNC id `<rel>::<func>` whose file basename is ep['script'], preferring skill/scripts and skill/hooks."""
    script, func = ep.get('script'), ep.get('func')
    cands = []
    for n in graph.get('nodes', []):
        nid = str(n.get('id', ''))
        if n.get('type') != 'FUNC' or '::' not in nid:
            continue
        rel, qual = nid.split('::', 1)
        if qual == func and rel.split('/')[-1] == script:
            cands.append(rel)
    if not cands:
        return None
    cands.sort(key=lambda r: (not (r.startswith('skill/scripts/') or r.startswith('skill/hooks/')), len(r), r))
    return cands[0] + '::' + func


def _adjacency(graph, include_ambiguous):
    """{source: [(target, edge)]} over calls/reads/spawns. Ambiguous calls (several candidates) are left out
    unless include_ambiguous; calls to an unresolved SINK are always kept (that ambiguity means 'unresolved')."""
    adj = {}
    for e in graph.get('edges', []):
        if e.get('relation') not in TRAVERSE:
            continue
        t = str(e.get('target', ''))
        if e.get('ambiguous') and not include_ambiguous and not t.startswith('sink:unresolved:'):
            continue
        adj.setdefault(str(e.get('source', '')), []).append((t, e))
    for v in adj.values():
        v.sort(key=lambda te: te[0])
    return adj


def _path_counts(adj, entry, memo):
    """{node: number of distinct simple call paths from entry} (depth cap PATH_DEPTH, cycle guard, memoised
    by (node, remaining depth); the memo ignores the caller's stack, so counts on cyclic graphs are an
    approximation), plus {node: [callers whose edge is in_loop]}."""
    loops = {}

    def walk(node, left, stack):
        key = (node, left)
        if key in memo:
            return memo[key]
        res = {}
        if left > 0:
            for t, _e in adj.get(node, ()):
                if t in stack:
                    continue
                res[t] = min(res.get(t, 0) + 1, PATH_BIG)
                stack.add(t)
                for k, v in walk(t, left - 1, stack).items():
                    res[k] = min(res.get(k, 0) + v, PATH_BIG)
                stack.discard(t)
        memo[key] = res
        return res

    counts = walk(entry, PATH_DEPTH, {entry})
    reach = set(counts) | {entry}
    for s in reach:
        for t, e in adj.get(s, ()):
            if e.get('in_loop'):
                loops.setdefault(t, set()).add(s)
    return counts, loops


def _tier(it):
    """0 = in-loop ext FUNC or SINK reached by >1 path; 1 = other SINK; 2 = FUNC; 3 = ext name."""
    typ, c = it[0], it[2]
    if typ == 'EXTLOOP' or (typ == 'SINK' and c > 1):
        return 0
    return {'SINK': 1, 'FUNC': 2, 'EXT': 3}.get(typ, 2)


def _item_key(it):
    return (_tier(it), -it[2], it[1])


def _repeat_items(graph, adj, entry, memo):
    """[(type, id, paths, loop_callers, literal_paths, callers)] sorted by _item_key (most telling first)."""
    kinds = {str(n.get('id')): n for n in graph.get('nodes', [])}
    counts, loops = _path_counts(adj, entry, memo)
    paths_by_sink, callers_by = {}, {}
    for s in set(counts) | {entry}:
        for t, e in adj.get(s, ()):
            callers_by.setdefault(t, set()).add(s)
            if e.get('path'):
                paths_by_sink.setdefault(t, set()).add(str(e['path']))
    items = []
    for t in set(counts) | set(loops):
        n = kinds.get(t, {})
        typ = n.get('type') or ('SINK' if t.startswith('sink:') else 'FUNC')
        if typ not in ('SINK', 'FUNC'):
            continue
        c = counts.get(t, 0)
        if c > 1 or t in loops:
            items.append((typ, t, c, sorted(loops.get(t, ())), sorted(paths_by_sink.get(t, ()))[:3],
                          sorted(callers_by.get(t, ()))))
    # `ext` calls (builtins, stdlib/external, well-known methods) are names on the calling FUNC, never
    # project FUNCs: a reachable FUNC with a non-empty `ext_in_loop` is an in-loop line (AC-012), and an
    # `ext` name called by several reachable FUNCs is reported once with its caller count.
    ext_callers = {}
    for f in set(counts) | {entry}:
        n = kinds.get(f) or {}
        if n.get('type') != 'FUNC':
            continue
        in_loop = sorted(n.get('ext_in_loop') or ())
        if in_loop:
            items.append(('EXTLOOP', f, max(counts.get(f, 0), 1), in_loop, [], []))
        for x in n.get('ext') or ():
            ext_callers.setdefault(str(x), set()).add(f)
    for x, fs in ext_callers.items():
        if len(fs) > 1:
            items.append(('EXT', x, len(fs), [], [], sorted(fs)))
    items.sort(key=_item_key)
    return items


def _fmt_item(it):
    typ, t, c, loop_callers, paths, callers = it
    if typ == 'EXTLOOP':
        return 'FUNC %s paths=%d ext_in_loop=%s' % (t, c, ','.join(loop_callers[:5]))
    if typ == 'EXT':
        return 'ext %s callers=%d' % (t, c)
    s = '%s %s paths=%d' % ('unresolved' if t.startswith('sink:unresolved:') else typ, t, c)
    if paths:
        s += ' [%s]' % ', '.join(paths)
    if typ == 'SINK':
        s += ' callers=%d (%s%s)' % (len(callers), ', '.join(callers[:3]), ', ...' if len(callers) > 3 else '')
    if loop_callers:
        s += ' in_loop@' + ','.join(x.split('::')[-1] for x in loop_callers[:3])
    return s


def _repeats(root, cmd=None, label=None, include_ambiguous=False, full=False):  # aidd:FR-017
    """(rc, lines). Most telling lines first (in-loop ext FUNCs and multi-path SINKs by paths desc, then
    other SINKs, FUNCs, ext names); capped at DIFF_CAP unless full. rc 2 for an unknown cmd, a missing
    snapshot or an entry point absent from the graph."""
    try:
        root = Path(root).resolve()
        eps = entrypoints()
        if not eps:
            return 2, ['no entry points: aidd/cli.py not found']
        if cmd and cmd not in eps:
            return 2, ['unknown command %r (known: %s)' % (cmd, ', '.join(sorted(eps))[:400])]
        if label:
            if not _valid_label(label):
                return 2, ['invalid label %r' % (label,)]
            graph = _load_json(snap_path(root, 'code', label))
            if not isinstance(graph, dict):
                return 2, ['no snapshot code/%s' % label]
        else:
            graph = _current_code_graph(root)
        adj = _adjacency(graph, include_ambiguous)
        memo = {}
        subs = [cmd] if cmd else sorted(eps)
        keyed = []
        for sub in subs:
            fid = _entry_id(graph, eps[sub])
            if fid is None:
                if cmd:
                    return 2, ['entry point %s::%s of %r is not in the code graph'
                               % (eps[sub]['script'], eps[sub]['func'], sub)]
                continue
            for it in _repeat_items(graph, adj, fid, memo):
                keyed.append((_item_key(it), sub, ('' if cmd else sub + ': ') + _fmt_item(it)))
        keyed.sort(key=lambda k: (k[0], k[1]))
        lines = [k[2] for k in keyed]
        if not lines:
            lines = ['no repeats from %s' % (cmd or 'any entry point')]
        return 0, _cap(lines, full)
    except Exception as ex:
        return 2, ['repeats failed: %s' % ex]


def repeats(root, cmd=None, label=None, include_ambiguous=False, full=False):  # aidd:FR-017
    """Lines (<= DIFF_CAP unless full). Use _repeats() for the exit code (2 = unknown cmd / no graph)."""
    return _repeats(root, cmd, label, include_ambiguous, full)[1]


# ---------------------------------------------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(prog='graph_snapshot.py',
                                 description='AIDD graph snapshots, diff, changed set and repeats (FR-017..FR-024).')
    ap.add_argument('--root', default=None, help='project root (default: cwd)')
    sp = ap.add_subparsers(dest='cmd_name')
    s = sp.add_parser('snapshot', help='write a canonical snapshot and log its sha256')
    s.add_argument('name_pos', nargs='?', default=None, metavar='name')
    s.add_argument('--name', default=None, help='graph name (%s)' % ', '.join(NAMES))
    s.add_argument('--label', required=True)
    s.add_argument('--rev', default=None, help='build from `git archive <rev>` in a temp dir')
    s.add_argument('--replace', action='store_true', help='re-use a label (logs a new event)')
    s.add_argument('--root', dest='root2', default=None)
    d = sp.add_parser('diff', help='diff two snapshots after verifying their logged sha256')
    d.add_argument('a')
    d.add_argument('b')
    d.add_argument('--name', default=None)
    d.add_argument('--full', action='store_true')
    d.add_argument('--root', dest='root2', default=None)
    c = sp.add_parser('changed', help='files changed since <spec>@open (content hash) and affected files')
    c.add_argument('--spec', default=None)
    c.add_argument('--name', default='code')
    c.add_argument('--full', action='store_true')
    c.add_argument('--root', dest='root2', default=None)
    r = sp.add_parser('repeats', help='sinks/unresolved calls/FUNCs reached by >1 path or in a loop')
    r.add_argument('--cmd', default=None)
    r.add_argument('--label', default=None)
    r.add_argument('--include-ambiguous', action='store_true')
    r.add_argument('--full', action='store_true', help='no line cap')
    r.add_argument('--root', dest='root2', default=None)
    m = sp.add_parser('manifest', help='write the <spec>@open content-hash manifest (no graph build)')
    m.add_argument('--spec', required=True)
    m.add_argument('--replace', action='store_true')
    m.add_argument('--root', dest='root2', default=None)
    try:
        a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as ex:
        return int(ex.code or 0)
    if not a.cmd_name:
        ap.print_help()
        return 2
    root = Path(getattr(a, 'root2', None) or a.root or os.getcwd()).resolve()
    if not root.is_dir():
        print('graph snapshot: root not found: %s' % root, file=sys.stderr)
        return 2
    if a.cmd_name == 'snapshot':
        name = a.name or a.name_pos or 'code'
        res = snapshot(root, name, a.label, rev=a.rev, replace=a.replace)
        print(res['message'], file=sys.stdout if res['rc'] == 0 else sys.stderr)
        return res['rc']
    if a.cmd_name == 'diff':
        rc, text = diff(root, a.a, a.b, full=a.full, name=a.name)
        print(text, file=sys.stdout if rc == 0 else sys.stderr)
        return rc
    if a.cmd_name == 'manifest':
        res = open_manifest(root, a.spec, replace=a.replace)
        print(res['message'], file=sys.stdout if res['rc'] == 0 else sys.stderr)
        return res['rc']
    if a.cmd_name == 'changed':
        res = changed(root, spec=a.spec, name=a.name)
        if res['rc'] != 0:
            print(res['message'], file=sys.stderr)
            return 2
        lines = ['M ' + x for x in res['modified']] + ['A ' + x for x in res['added']] + \
                ['D ' + x for x in res['removed']]
        print('changed since %s@open (%s): %d modified, %d added, %d removed'
              % (res['spec'], res['name'], len(res['modified']), len(res['added']), len(res['removed'])))
        for ln in _cap(lines, a.full):
            print(ln)
        aff = res['affected']
        print('affected: %s' % (', '.join(aff if a.full else aff[:DIFF_CAP]) or 'none')
              + ('' if a.full or len(aff) <= DIFF_CAP else ' ... %d more (--full)' % (len(aff) - DIFF_CAP)))
        if res['message']:
            print(res['message'], file=sys.stderr)
        return 0
    rc, lines = _repeats(root, cmd=a.cmd, label=a.label, include_ambiguous=a.include_ambiguous, full=a.full)
    print('\n'.join(lines), file=sys.stdout if rc == 0 else sys.stderr)
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
