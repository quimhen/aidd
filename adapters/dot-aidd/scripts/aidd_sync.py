#!/usr/bin/env python3
"""
aidd_sync -- compare and update an installed AIDD bundle against the AIDD source tree (amendment 10 of spec 007,
item N, FR-413..FR-418).

    aidd_sync.py --source <aidd repo> --check   [--target skill|<path to .aidd or project>]... [--profile DIR] [--json]
    aidd_sync.py --source <aidd repo> --apply   [--target ...]... [--yes] [--dry-run] [--backup-dir DIR]
    aidd_sync.py [--source <aidd repo>] --recover <backup session dir>

Trees compared (the WHOLE tree, never a fixed file list):
  target `skill` (default)   <source>/skill/              vs the profile ($AIDD_HOME or ~/.claude/skills/aidd)
  target <path>              <source>/adapters/dot-aidd/  vs <path> (a `.aidd` folder, or a project that has one)

Every path is resolved to an absolute path once, at start-up; nothing changes the working directory. Files are equal
when their bytes are equal after normalising CRLF to LF. Local state is never compared, copied or reported:
evidence, memory, active_spec, gate_spec, calibration.toon, graphs, sqlcheck-cache.json, __pycache__, *.bak, *.pyc.

--check lists, per target, `missing` (in source, not installed), `differs` and `local-only` (installed, not in
source; informative, never deleted). Exit 0 = no missing/differs, 1 = some, 2 = usage error.

--apply is a dry run unless --yes is given (--dry-run always wins). With --yes it (1) backs up every file it will
replace into a timestamped session folder outside every target, (2) updates the files that
tools/aidd_selective_update.py accepts (AIDD.md, SKILL.md, hooks/*.py, scripts/*.py, templates/navigator.html) through
its transaction, with the backup as --baseline, (3) copies the rest (templates/**, CORE.md, extensions/**, ...)
directly, verifying the sha256 of each written file, (4) writes `sync-journal.json` for `--recover`, and (5) runs the
--check again, which must give 0. Any failure rolls back what was written. Stdlib only.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

LOCAL_NAMES = frozenset(('evidence', 'memory', 'active_spec', 'gate_spec', 'calibration.toon', 'graphs',
                         'sqlcheck-cache.json', '__pycache__'))
LOCAL_SUFFIXES = ('.bak', '.pyc')
# What tools/aidd_selective_update.py._relative accepts for a bundle (cli.py, RECORD, hooks.json are package/host files).
SELECTIVE_ROOT_FILES = frozenset(('AIDD.md', 'SKILL.md', 'templates/navigator.html'))
JOURNAL = 'sync-journal.json'


# --------------------------------------------------------------------------------------------------- comparison

def is_local(rel):
    """True for local state that sync never compares (rel = forward-slash relative path)."""
    parts = rel.split('/')
    return any(p in LOCAL_NAMES for p in parts) or parts[-1].endswith(LOCAL_SUFFIXES)


def tree_files(root):
    """{key: rel} of every non-local regular file under the absolute root (key is casefolded on Windows)."""
    root = Path(root)
    out = {}
    if not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in LOCAL_NAMES)
        for name in sorted(filenames):
            rel = Path(dirpath, name).relative_to(root).as_posix()
            if not is_local(rel):
                out[rel.casefold() if os.name == 'nt' else rel] = rel
    return out


def same_content(a, b):
    """Byte-for-byte equality, tolerating CRLF vs LF."""
    x, y = Path(a).read_bytes(), Path(b).read_bytes()
    return x == y or x.replace(b'\r\n', b'\n') == y.replace(b'\r\n', b'\n')


def compare(source_root, installed_root):
    """{'missing', 'differs', 'local-only'}: sorted forward-slash paths relative to the two absolute roots."""
    source_root, installed_root = Path(source_root), Path(installed_root)
    src, dst = tree_files(source_root), tree_files(installed_root)
    missing = sorted(src[k] for k in src if k not in dst)
    differs = sorted(src[k] for k in src if k in dst
                     and not same_content(source_root / src[k], installed_root / dst[k]))
    local = sorted(dst[k] for k in dst if k not in src)
    return {'missing': missing, 'differs': differs, 'local-only': local}


# --------------------------------------------------------------------------------------------------- targets

def default_profile():
    home = os.environ.get('AIDD_HOME')
    return Path(home).expanduser() if home else Path.home() / '.claude' / 'skills' / 'aidd'


def check_source(source):
    source = Path(source).expanduser().resolve()
    for sub in ('skill', 'adapters/dot-aidd'):
        if not (source / sub).is_dir():
            raise ValueError(f'--source {source} has no {sub}/ (pass the AIDD repo root)')
    return source


def resolve_targets(source, targets, profile=None):
    """[(label, absolute source tree, absolute installed tree)]; default target = skill."""
    out = []
    for value in targets or ['skill']:
        if value == 'skill':
            out.append(('skill', source / 'skill', Path(profile or default_profile()).expanduser().resolve()))
            continue
        path = Path(value).expanduser().resolve()
        if path.name != '.aidd' and (path / '.aidd').is_dir():
            path = path / '.aidd'
        out.append((str(path), source / 'adapters' / 'dot-aidd', path))
    return out


def run_check(resolved, as_json=False, stream=None):
    stream = stream or sys.stdout
    reports, bad = [], 0
    for label, src, dst in resolved:
        if not dst.is_dir():
            report = {'target': label, 'source': str(src), 'installed': str(dst), 'error': 'installed folder missing',
                      'missing': sorted(tree_files(src).values()), 'differs': [], 'local-only': []}
        else:
            report = {'target': label, 'source': str(src), 'installed': str(dst), **compare(src, dst)}
        bad += len(report['missing']) + len(report['differs'])
        reports.append(report)
    if as_json:
        print(json.dumps({'ok': bad == 0, 'targets': reports}, indent=2), file=stream)
    else:
        for r in reports:
            print(f"target {r['target']}: {r['source']} -> {r['installed']}"
                  + (f" ({r['error']})" if r.get('error') else ''), file=stream)
            for cat in ('missing', 'differs', 'local-only'):
                print(f'  {cat} ({len(r[cat])})', file=stream)
                for rel in r[cat]:
                    print(f'    {rel}', file=stream)
        total = {c: sum(len(r[c]) for r in reports) for c in ('missing', 'differs', 'local-only')}
        print(f"sync check: missing={total['missing']} differs={total['differs']} local-only={total['local-only']}"
              f" -> {'OK' if bad == 0 else 'OUT OF SYNC'}", file=stream)
    return (0 if bad == 0 else 1), reports


# --------------------------------------------------------------------------------------------------- apply

def load_selective(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f'tools/aidd_selective_update.py not found at {path} (pass --source <AIDD repo checkout>)')
    spec = importlib.util.spec_from_file_location('aidd_selective_update_for_sync', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def selective_accepts(rel):
    parts = rel.split('/')
    return rel in SELECTIVE_ROOT_FILES or (len(parts) == 2 and parts[0] in ('hooks', 'scripts')
                                           and parts[1].endswith('.py') and not parts[1].startswith('.'))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _inside(child, parent):
    try:
        return os.path.commonpath((os.path.normcase(str(child)), os.path.normcase(str(parent)))) \
            == os.path.normcase(str(parent))
    except ValueError:
        return False


def _write_json(path, value):
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True), encoding='utf-8')
    os.replace(tmp, path)


def _write_verified(dst, data, expected):
    fd, tmp = tempfile.mkstemp(prefix='.aidd-sync-', dir=str(dst.parent))
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    if _sha(dst) != expected:
        raise ValueError(f'copy could not be verified (sha256): {dst}')


def build_plan(resolved):
    """[{target index, label, src, dst, rel, kind: missing|differs, method: selective|copy}]."""
    items = []
    for index, (label, src, dst) in enumerate(resolved):
        if not dst.is_dir():
            raise ValueError(f'installed folder missing: {dst} (install it first: aidd init / copy the skill)')
        diff = compare(src, dst)
        for kind in ('missing', 'differs'):
            for rel in diff[kind]:
                parent_ok = (dst / rel).parent.is_dir()
                method = 'selective' if selective_accepts(rel) and parent_ok else 'copy'
                items.append({'index': index, 'label': label, 'src': str(src), 'dst': str(dst), 'rel': rel,
                              'kind': kind, 'method': method})
    return items


def _rollback_direct(entries):
    """Undo direct copies whose current bytes are still the ones sync wrote; refuse on any foreign edit."""
    todo = []
    for e in reversed(entries):
        target = Path(e['dst']) / e['rel']
        current = _sha(target) if target.is_file() else None
        if current == e['before']:
            continue
        if current != e['after']:
            raise ValueError(f'file changed after sync; restore it by hand from the backup: {target}')
        todo.append((target, e))
    return todo


def _restore_direct(todo, session, entries=()):
    for target, e in todo:
        if e['before'] is None:
            target.unlink()
        else:
            _write_verified(target, (session / e['backup']).read_bytes(), e['before'])
    for e in list(entries) or [e for _, e in todo]:
        for d in reversed(e.get('created_dirs', [])):   # only folders sync created, and only when empty
            try:
                Path(d).rmdir()
            except OSError:
                pass


def apply(source, resolved, yes=False, dry_run=False, backup_dir=None, stream=None):
    stream = stream or sys.stdout
    plan = build_plan(resolved)
    if not plan:
        print('sync apply: nothing to update.', file=stream)
        return run_check(resolved, stream=stream)[0]
    for it in plan:
        print(f"  {it['method']:9} {it['kind']:7} {it['label']}: {it['rel']}", file=stream)
    if dry_run or not yes:
        print(f'sync apply: DRY RUN, {len(plan)} file(s) would be updated; nothing written. '
              'Re-run with --yes to apply.', file=stream)
        return 0
    tool = source / 'tools' / 'aidd_selective_update.py'
    selective = load_selective(tool) if any(it['method'] == 'selective' for it in plan) else None
    root = Path(backup_dir).expanduser().resolve() if backup_dir else Path.home() / '.aidd-sync' / 'backups'
    session = root / (time.strftime('%Y%m%d-%H%M%S') + f'-{os.getpid()}')
    for _, _, dst in resolved:
        if _inside(session, dst):
            raise ValueError(f'backup folder must be outside every target: {session} is inside {dst}')
    session.mkdir(parents=True, exist_ok=False)
    # 1. Backup (= the --baseline of the selective transaction).
    direct, plans = [], {}
    for n, it in enumerate(plan):
        dst_file = Path(it['dst']) / it['rel']
        base = session / f"t{it['index']}" / 'files'
        base.mkdir(parents=True, exist_ok=True)
        before = None
        if dst_file.is_file():
            backup = base / it['rel']
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst_file, backup)
            before = _sha(dst_file)
            if _sha(backup) != before:
                raise ValueError(f'backup could not be verified: {backup}')
        if it['method'] == 'selective':
            plans.setdefault(it['index'], (it, base, []))[2].append(it['rel'])
        else:
            direct.append({'dst': it['dst'], 'rel': it['rel'], 'src': it['src'], 'before': before,
                           'after': _sha(Path(it['src']) / it['rel']), 'created_dirs': [],
                           'backup': (Path(f"t{it['index']}") / 'files' / it['rel']).as_posix() if before else None})
    journal = {'version': 1, 'state': 'prepared', 'source': str(source), 'selective_tool': str(tool),
               'selective_journal': str(session / 'selective-journal') if plans else None,
               'targets': [[label, str(src), str(dst)] for label, src, dst in resolved], 'direct': direct}
    _write_json(session / JOURNAL, journal)
    print(f'sync apply: backup and journal in {session}', file=stream)
    done = []
    try:
        journal['state'] = 'applying'
        _write_json(session / JOURNAL, journal)
        # 2. Files the selective transaction accepts, baseline = the backup just taken.
        if plans:
            made = [selective.make_plan(it['src'], it['dst'], names, base) for it, base, names in plans.values()]
            selective.apply_transaction(made, session / 'selective-journal')
        # 3. Everything else: direct copy, hash-verified.
        for e in direct:
            target = Path(e['dst']) / e['rel']
            missing_dirs = [p for p in reversed(target.parents) if _inside(p, e['dst']) and not p.exists()]
            e['created_dirs'] = [str(p) for p in missing_dirs]
            _write_json(session / JOURNAL, journal)
            target.parent.mkdir(parents=True, exist_ok=True)
            if (_sha(target) if target.is_file() else None) != e['before']:
                raise ValueError(f'destination changed before copy: {target}')
            data = (Path(e['src']) / e['rel']).read_bytes()
            if hashlib.sha256(data).hexdigest() != e['after']:
                raise ValueError(f'source changed while copying: {e["rel"]}')
            done.append(e)
            _write_verified(target, data, e['after'])
        journal['state'] = 'committed'
        _write_json(session / JOURNAL, journal)
    except Exception as exc:
        try:
            _restore_direct(_rollback_direct(done), session, done)
            if plans and (session / 'selective-journal' / 'transaction.json').is_file():
                selective.recover_transaction(session / 'selective-journal')
            journal['state'] = 'rolled_back'
            _write_json(session / JOURNAL, journal)
        except Exception as recovery:  # noqa: BLE001
            print(f'sync apply: FAILED and rollback incomplete ({recovery}); run: aidd sync --recover {session}',
                  file=sys.stderr)
            raise exc
        print(f'sync apply: FAILED ({exc}); everything written was rolled back.', file=sys.stderr)
        return 1
    print(f'sync apply: updated {len(plan)} file(s) '
          f'({sum(len(n) for _, _, n in plans.values())} selective, {len(direct)} copied).', file=stream)
    rc = run_check(resolved, stream=stream)[0]
    if rc != 0:
        print(f'sync apply: post-check FAILED; undo with: aidd sync --recover {session}', file=sys.stderr)
    return rc


def recover(session, source=None, stream=None):
    stream = stream or sys.stdout
    session = Path(session).expanduser().resolve()
    path = session / JOURNAL
    if not path.is_file():
        raise ValueError(f'no {JOURNAL} in {session}')
    journal = json.loads(path.read_text(encoding='utf-8'))
    if journal.get('version') != 1 or journal.get('state') not in ('prepared', 'applying', 'committed',
                                                                    'rolled_back'):
        raise ValueError('invalid sync journal')
    if journal['state'] == 'rolled_back':
        print('sync recover: already rolled back.', file=stream)
        return 0
    todo = _rollback_direct(journal['direct'])          # validate every direct file before touching anything
    sel = journal.get('selective_journal')
    restored = 0
    if sel and (Path(sel) / 'transaction.json').is_file():
        tool = Path(source) / 'tools' / 'aidd_selective_update.py' if source else Path(journal['selective_tool'])
        restored += load_selective(tool).recover_transaction(sel)
    _restore_direct(todo, session, journal['direct'])
    journal['state'] = 'rolled_back'
    _write_json(path, journal)
    print(f'sync recover: restored {restored + len(todo)} file(s) from {session}.', file=stream)
    return 0


# --------------------------------------------------------------------------------------------------- CLI

def main(argv=None):
    p = argparse.ArgumentParser(prog='aidd sync', description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true', help='compare; exit 1 when something is missing or differs')
    mode.add_argument('--apply', action='store_true', help='update (dry run unless --yes)')
    mode.add_argument('--recover', metavar='SESSION', help='roll back one --apply session (its backup folder)')
    p.add_argument('--source', help='AIDD repo root (has skill/ and adapters/dot-aidd/)')
    p.add_argument('--target', action='append', default=[],
                   help='`skill` (the profile, default) or a .aidd folder / project root; repeatable')
    p.add_argument('--profile', help='installed skill folder (default: $AIDD_HOME or ~/.claude/skills/aidd)')
    p.add_argument('--yes', action='store_true', help='really write (with --apply)')
    p.add_argument('--dry-run', action='store_true', help='print the plan only (default for --apply)')
    p.add_argument('--backup-dir', help='folder for backup sessions (default: ~/.aidd-sync/backups)')
    p.add_argument('--json', action='store_true', help='machine-readable --check report')
    args = p.parse_args(argv)
    try:
        if args.recover:
            return recover(args.recover, check_source(args.source) if args.source else None)
        if not args.source:
            p.error('--source is required with --check/--apply')
        source = check_source(args.source)
        resolved = resolve_targets(source, args.target, args.profile)
        if args.check:
            return run_check(resolved, as_json=args.json)[0]
        return apply(source, resolved, yes=args.yes, dry_run=args.dry_run, backup_dir=args.backup_dir)
    except (ValueError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f'aidd sync: refused: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
