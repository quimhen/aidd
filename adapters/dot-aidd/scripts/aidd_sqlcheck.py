#!/usr/bin/env python3
"""
aidd sqlcheck -- static "compile" of SQL migrations BEFORE any database is touched. No LLM. No database.

Why: a static check takes milliseconds; discovering the same syntax error through a DB apply costs a container
round-trip, a transaction and a rollback. Compile first, then do ONE database pass for the whole batch (several
specs at once).

DATABASE-AGNOSTIC: AIDD fixes the contract (static compile -> ONE database pass), not the engine. The checker
MUST match the project's database engine. Built-in adapter: `--engine postgres` (default; also Supabase), the
real PostgreSQL parser via the optional `pglast` package. Any other engine (SQL Server, MySQL, Oracle, SQLite...):
pass its own compiler/linter with `--cmd`, where `{file}` is replaced by the quoted file path and a non-zero exit
code means "does not compile", e.g. `--cmd "sqlfluff lint --dialect tsql {file}"`. Declare the project's choice
once (charter or spec `## Verification`) so every agent uses the same one.

Usage:
    aidd_sqlcheck.py <file.sql|dir>... [--engine postgres] [--cmd "<command with {file}>"]
                     [--cache FILE] [--no-cache] [--json]
        Several paths (e.g. the migration dirs of several specs) are checked in ONE run and reported as ONE
        batch. Files whose sha256 (line endings normalised) already passed with the same checker are skipped via
        the cache (default <cwd>/.aidd/sqlcheck-cache.json), so the same file is never compiled twice.
        Output ends with the apply manifest: every file in natural order, i.e. the exact input of the single
        database pass. Run the DB pass only when the exit code is 0.

Exit codes: 0 all files compile (or checker unavailable: static check skipped, warning printed),
            1 at least one file does not compile, 2 usage / unreadable path.
Optional dependency for the postgres adapter: pip install pglast. Never prints a traceback.
"""
import hashlib
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

CACHE_VERSION = 1
USAGE = ('usage: aidd_sqlcheck.py <file.sql|dir>... [--engine postgres] [--cmd "<command with {file}>"] '
         '[--cache FILE] [--no-cache] [--json]')


def _natural_key(p):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', str(p))]


def _sha(data):
    return hashlib.sha256(data.replace(b'\r\n', b'\n').replace(b'\r', b'\n')).hexdigest()


def collect(paths):
    """Files (deduplicated, natural order) from files and directories; raises FileNotFoundError."""
    out = {}
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for f in p.rglob('*.sql'):
                out[f.resolve()] = f
        elif p.is_file():
            out[p.resolve()] = p
        else:
            raise FileNotFoundError(raw)
    # Migration version (file name) decides the order across directories, the path only breaks ties.
    return [out[k] for k in sorted(out, key=lambda k: (_natural_key(k.name), _natural_key(k)))]


def _line_of(text, location):
    return text.count('\n', 0, max(0, location)) + 1


def compile_text(text, parser):
    """None when the text compiles, else 'line N: message'. `parser` is the pglast.parser module."""
    try:
        parser.parse_sql(text)
    except Exception as exc:
        loc = getattr(exc, 'location', None)
        msg = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        return f'line {_line_of(text, loc)}: {msg}' if isinstance(loc, int) else msg
    return None


def command_checker(template):
    """Checker backed by an external command: None when it exits 0, else its first output line."""
    def check(path, _text):
        cmd = template.replace('{file}', shlex.quote(str(path)))
        try:
            p = subprocess.run(cmd, shell=True, capture_output=True, timeout=120)
        except Exception as exc:
            return f'{type(exc).__name__}: {exc}'
        if p.returncode == 0:
            return None
        out = (p.stdout + p.stderr).decode('utf-8', 'replace').strip().splitlines()
        return out[0] if out else f'exit {p.returncode}'
    return check


def _load_cache(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if data.get('version') == CACHE_VERSION and isinstance(data.get('ok'), dict):
            return data
    except Exception:
        pass
    return {'version': CACHE_VERSION, 'ok': {}}


def _save_cache(path, cache):
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix('.tmp')
        tmp.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding='utf-8')
        tmp.replace(p)
    except Exception:
        pass


def run(files, check, cache_path=None, tag=''):
    """Check every file once with `check(path, text) -> None|error`; `tag` identifies the checker in the cache.
    Returns {'checked','cached','failed':[(file, err)],'files':[...]}."""
    cache = _load_cache(cache_path) if cache_path else {'version': CACHE_VERSION, 'ok': {}}
    res = {'checked': 0, 'cached': 0, 'failed': [], 'files': [str(f) for f in files]}
    for f in files:
        data = f.read_bytes()
        sha = _sha(data) + tag
        key = str(f.resolve())
        if cache['ok'].get(key) == sha:
            res['cached'] += 1
            continue
        res['checked'] += 1
        err = check(f, data.decode('utf-8', 'replace').replace('\r\n', '\n'))
        if err:
            res['failed'].append((str(f), err))
            cache['ok'].pop(key, None)
        else:
            cache['ok'][key] = sha
    if cache_path:
        _save_cache(cache_path, cache)
    return res


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if any(a in ('-h', '--help') for a in argv):
        print(__doc__.strip())
        return 0
    as_json = '--json' in argv
    no_cache = '--no-cache' in argv
    cache_path = None
    engine = 'postgres'
    cmd = None
    paths = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ('--cache', '--engine', '--cmd'):
            if i + 1 >= len(argv):
                print(USAGE)
                return 2
            if a == '--cache':
                cache_path = argv[i + 1]
            elif a == '--engine':
                engine = argv[i + 1].lower()
            else:
                cmd = argv[i + 1]
            i += 1
        elif a not in ('--json', '--no-cache'):
            paths.append(a)
        i += 1
    if not paths:
        print(USAGE)
        return 2
    try:
        files = collect(paths)
    except FileNotFoundError as exc:
        print(f'not found: {exc}')
        return 2
    if cmd:
        check, tag = command_checker(cmd), '|cmd:' + hashlib.sha1(cmd.encode()).hexdigest()[:8]
    elif engine in ('postgres', 'postgresql', 'supabase'):
        try:
            import pglast.parser as parser
        except Exception:
            print('WARNING: pglast is not installed (pip install pglast): static SQL check SKIPPED, '
                  'the database pass will catch syntax errors instead.')
            return 0
        check, tag = (lambda _p, text: compile_text(text, parser)), '|postgres'
    else:
        print(f'no built-in static checker for engine "{engine}": pass its own compiler/linter with '
              f'--cmd "<command with {{file}}>". Static check SKIPPED.')
        return 0
    if not no_cache and cache_path is None:
        cache_path = str(Path.cwd() / '.aidd' / 'sqlcheck-cache.json')
    res = run(files, check, None if no_cache else cache_path, tag)
    if as_json:
        print(json.dumps({'checked': res['checked'], 'cached': res['cached'],
                          'failed': [{'file': f, 'error': e} for f, e in res['failed']],
                          'manifest': res['files']}, indent=1))
        return 1 if res['failed'] else 0
    print(f"sqlcheck: {len(files)} file(s): {res['checked']} compiled now, {res['cached']} unchanged (cached), "
          f"{len(res['failed'])} failed")
    for f, e in res['failed']:
        print(f'  FAIL {f}: {e}')
    if res['failed']:
        print('Fix these BEFORE the database pass (nothing was sent to the DB).')
        return 1
    print('Apply manifest (ONE database pass, in this order):')
    for f in res['files']:
        print(f'  {f}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
