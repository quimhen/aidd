#!/usr/bin/env python3
"""Run the AIDD tests: only the modules a change can affect, in parallel (stdlib only).

    python tests/run_parallel.py --changed          modules that mention a changed file (fast loop while editing)
    python tests/run_parallel.py --changed --deep   plus the modules reaching it through imports (before a commit)
    python tests/run_parallel.py                    every module (before a release)
Run any of them in the background and keep working: nothing here needs the conversation to wait.
    python tests/run_parallel.py [-j N] [--timeout SECONDS] [--retry] [--json] [module ...]

The selection is a small graph built from the sources, not a guess: source file -> files that import it
(transitively) -> test modules that mention any of them. A changed file the graph does not know (a new kind of
code file) runs everything; documentation-only changes run nothing. Each module runs in its own process.
An optional solo retry diagnoses flaky tests but never changes a failed run into a success.
"""
import os
import argparse
import ast
import json
import re
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIRS = ('skill/scripts', 'skill/hooks', 'adapters/dot-aidd/scripts', 'aidd')
DOC_EXT = {'.md', '.markdown', '.txt', '.rst'}
IMPORT_RE = re.compile(r'^\s*(?:import|from)\s+([A-Za-z_]\w*)', re.M)


def sources():
    """{stem: [relative paths]} of the code under test (the adapters mirror maps to the same stem)."""
    out = {}
    for d in SRC_DIRS:
        for p in (ROOT / d).glob('*.py'):
            out.setdefault(p.stem, []).append(p.relative_to(ROOT).as_posix())
    return out


def dependents(src):
    """{stem: set of stems that import it directly}."""
    rev = {s: set() for s in src}
    for s, paths in src.items():
        text = ''.join((ROOT / p).read_text(encoding='utf-8', errors='replace') for p in paths)
        for name in set(IMPORT_RE.findall(text)):
            if name in rev and name != s:
                rev[name].add(s)
    return rev


def closure(stems, rev):
    seen, todo = set(stems), list(stems)
    while todo:
        for d in rev.get(todo.pop(), ()):
            if d not in seen:
                seen.add(d)
                todo.append(d)
    return seen


def mentions(test_file, stems):
    text = test_file.read_text(encoding='utf-8', errors='replace')
    hit = {s for s in stems if s != 'cli' and re.search(r'\b' + re.escape(s) + r'\b', text)}
    if 'cli' in stems and ('cli' in test_file.stem or re.search(r'aidd[/\\.]cli\b', text)):
        hit.add('cli')
    return hit


def changed_paths():
    p = subprocess.run(['git', 'status', '--porcelain', '-uall'], cwd=str(ROOT), capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    if p.returncode:
        raise RuntimeError(f'git status failed (exit {p.returncode}): {p.stderr.strip()}')
    out = []
    for ln in p.stdout.splitlines():
        path = ln[3:].strip().strip('"')
        if ' -> ' in path:
            path = path.split(' -> ')[1]
        if path and not path.startswith('.aidd/'):
            out.append(path.replace('\\', '/'))
    return out


def affected(all_mods, deep=False):
    """(modules to run, reason). By default only the modules that mention a changed file directly (the fast
    loop while editing); `deep` adds every module that mentions a file importing a changed one (before a
    commit). All modules when a changed code file is unknown to the graph."""
    src = sources()
    rev = dependents(src)
    stems, direct, why = set(), set(), []
    for path in changed_paths():
        pp = Path(path)
        if pp.suffix.lower() in DOC_EXT or path.startswith(('specs/', 'docs/')):
            continue
        if pp.parts[:1] == ('tests',):
            if pp.stem in all_mods:
                direct.add(pp.stem)
            elif pp.suffix == '.py':
                return list(all_mods), f'changed test helper {path}: running everything'
            continue
        if pp.stem in src and pp.suffix == '.py':
            stems.add(pp.stem)
            continue
        return list(all_mods), f'unknown changed file {path}: running everything'
    hit = closure(stems, rev) if deep else set(stems)
    mods = set(direct)
    if hit:
        for m in all_mods:
            if mentions(ROOT / 'tests' / f'{m}.py', hit):
                mods.add(m)
        if not mods:
            return list(all_mods), f'no tests mapped to changed sources {sorted(stems)}: running everything'
    why.append(f'changed sources {sorted(stems)} -> {len(hit)} affected file(s) -> {len(mods)} of {len(all_mods)} module(s)')
    return sorted(mods), '; '.join(why)


CLASS_RE = re.compile(r'^class\s+(\w+)\s*\(', re.M)


def uses_pytest(mod):
    """Run pytest for functions and pytest-style classes, including mixed modules."""
    try:
        tree = ast.parse((ROOT / 'tests' / f'{mod}.py').read_text(encoding='utf-8'))
        classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
        testcase_names = {'TestCase'}
        unittest_names = {'unittest'}
        for item in tree.body:
            if isinstance(item, ast.ImportFrom) and item.module == 'unittest':
                testcase_names.update(a.asname or a.name for a in item.names if a.name == 'TestCase')
            elif isinstance(item, ast.Import):
                unittest_names.update(a.asname or a.name for a in item.names if a.name == 'unittest')

        def is_unittest_class(node, seen=None):
            seen = set() if seen is None else seen
            if node.name in seen:
                return False
            seen.add(node.name)
            for base in node.bases:
                if isinstance(base, ast.Name):
                    if base.id in testcase_names:
                        return True
                    if base.id in classes and is_unittest_class(classes[base.id], seen):
                        return True
                if (isinstance(base, ast.Attribute) and base.attr == 'TestCase'
                        and isinstance(base.value, ast.Name) and base.value.id in unittest_names):
                    return True
            return False

        def may_have_tests(node, seen=None):
            seen = set() if seen is None else seen
            if node.name in seen:
                return False
            seen.add(node.name)
            if any(isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)) and x.name.startswith('test_')
                   for x in node.body):
                return True
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id in classes:
                    if may_have_tests(classes[base.id], seen):
                        return True
                elif not (isinstance(base, ast.Name) and base.id == 'object'):
                    # Imported base classes can themselves define tests.
                    return True
            return False

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                return True
            if isinstance(node, ast.ClassDef) and node.name.startswith('Test'):
                # Unknown base classes are treated conservatively: pytest can
                # discover unittest classes, whereas unittest skips pytest classes.
                if not is_unittest_class(node) and may_have_tests(node):
                    return True
        return False
    except (OSError, SyntaxError, UnicodeError):
        # The actual runner reports missing/unreadable/invalid modules as failures.
        return False


def targets(mod, split_classes=False):
    """Unit(s) to run for a module: one per TestCase class when it has several (balances the workers: one slow
    module no longer runs alone while the others sit idle), else the module itself."""
    if not split_classes or uses_pytest(mod):
        return [f'tests.{mod}']
    text = (ROOT / 'tests' / f'{mod}.py').read_text(encoding='utf-8', errors='replace')
    cls = [c for c in CLASS_RE.findall(text) if c.startswith('Test')]
    return [f'tests.{mod}.{c}' for c in cls] if len(cls) > 1 else [f'tests.{mod}']


def run(unit, timeout=600):
    mod = unit
    t = time.monotonic()
    parts = unit.split('.')
    module = parts[1] if len(parts) >= 2 and parts[0] == 'tests' else unit
    if uses_pytest(module):
        command = [sys.executable, '-m', 'pytest', str(ROOT / 'tests' / f'{module}.py'), '-q']
    else:
        command = [sys.executable, '-m', 'unittest', unit]
    try:
        p = subprocess.Popen(command, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, encoding='utf-8', errors='replace',
                             start_new_session=(os.name != 'nt'))
    except OSError as exc:
        return mod, 1, f'failed to start test process: {exc}', time.monotonic() - t
    try:
        stdout, stderr = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(p.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            else:
                os.killpg(p.pid, signal.SIGKILL)
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            p.kill()
        except OSError:
            pass
        try:
            p.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            if p.stdout:
                p.stdout.close()
            if p.stderr:
                p.stderr.close()
        return mod, 124, f'timeout after {timeout} seconds', time.monotonic() - t
    out = stdout + stderr
    rc = p.returncode or (1 if re.search(r'\b(?:NO TESTS RAN|Ran 0 tests?)\b', out, re.I) else 0)
    return mod, rc, out, time.monotonic() - t


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-j', type=int, default=min(8, os.cpu_count() or 2))
    parser.add_argument('--changed', action='store_true')
    parser.add_argument('--deep', action='store_true')
    parser.add_argument('--split-classes', action='store_true')
    parser.add_argument('--retry', action='store_true')
    parser.add_argument('--timeout', type=float, default=600)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('modules', nargs='*')
    args = parser.parse_args(argv)
    if args.j < 1 or args.timeout <= 0:
        parser.error('jobs and timeout must be positive')
    jobs = args.j
    mods = list(dict.fromkeys(a.removesuffix('.py').removeprefix('tests.').removeprefix('tests/') for a in args.modules))
    every = sorted(p.stem for p in (ROOT / 'tests').glob('test_*.py'))
    why = 'explicit modules' if mods else 'all modules'
    if args.changed and not mods:
        try:
            mods, why = affected(every, args.deep)
        except (OSError, RuntimeError) as exc:
            if args.json:
                print(json.dumps({'status': 'error', 'error': str(exc), 'results': []}))
            else:
                print(f'ERROR selecting tests: {exc}', file=sys.stderr)
            return 2
        if not args.json:
            print(why, flush=True)
        if not mods:
            if args.json:
                print(json.dumps({'status': 'no_changes', 'reason': why, 'results': []}))
            else:
                print('nothing to run: no code file changed')
            return 0
    mods = mods or every
    units = [u for m in mods for u in targets(m, args.split_classes)]
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(lambda unit: run(unit, args.timeout), units))
    failed = []
    retries = {}
    for mod, rc, out, secs in results:
        if rc != 0:
            failed.append((mod, out))
            if args.retry:
                _m, rc2, out2, retry_secs = run(mod, args.timeout)
                retries[mod] = {'exit': rc2, 'output': out2, 'seconds': round(retry_secs, 3)}
    if args.json:
        print(json.dumps({'status': 'fail' if failed else 'ok', 'reason': why,
                          'wall_seconds': round(time.monotonic() - t0, 3), 'workers': jobs,
                          'results': [{'unit': mod, 'exit': rc, 'seconds': round(secs, 3),
                                       'output': out, 'retry': retries.get(mod)}
                                      for mod, rc, out, secs in results]}))
        return 1 if failed else 0
    for mod, result in retries.items():
        print(f"  retry {mod}: {'passed (original failure retained)' if result['exit'] == 0 else 'failed'}")
    for mod, rc, out, secs in sorted(results, key=lambda r: -r[3])[:3]:
        print(f'  slowest: {mod:36s} {secs:6.1f}s')
    for mod, out in failed:
        print(f'\nFAILED {mod}\n' + '\n'.join(out.strip().splitlines()[-25:]))
    print(f'\n{len(mods)} module(s) in {len(units)} unit(s), {len(failed)} failed, '
          f'{time.monotonic() - t0:.0f}s wall with {jobs} workers')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
