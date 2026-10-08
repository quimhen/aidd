#!/usr/bin/env python3
"""Run the AIDD tests: only the modules a change can affect, in parallel (stdlib only).

    python tests/run_parallel.py --changed          modules that mention a changed file (fast loop while editing)
    python tests/run_parallel.py --changed --deep   plus the modules reaching it through imports (before a commit)
    python tests/run_parallel.py                    every module (before a release)
Run any of them in the background and keep working: nothing here needs the conversation to wait.
    python tests/run_parallel.py [-j N] [module ...]

The selection is a small graph built from the sources, not a guess: source file -> files that import it
(transitively) -> test modules that mention any of them. A changed file the graph does not know (a new kind of
code file) runs everything; documentation-only changes run nothing. Each module runs in its own process; a
module that fails is re-run once alone, so a timing-sensitive test that only fails under load neither hides
a real failure nor raises a false one. "NO TESTS RAN" is not a failure.
"""
import os
import re
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
            continue
        if pp.stem in src and pp.suffix == '.py':
            stems.add(pp.stem)
            continue
        return list(all_mods), f'unknown changed file {path}: running everything'
    hit = closure(stems, rev) if deep else set(stems)
    mods = set(direct)
    for m in all_mods:
        if mentions(ROOT / 'tests' / f'{m}.py', set(src)) & hit:
            mods.add(m)
    why.append(f'changed sources {sorted(stems)} -> {len(hit)} affected file(s) -> {len(mods)} of {len(all_mods)} module(s)')
    return sorted(mods), '; '.join(why)


CLASS_RE = re.compile(r'^class\s+(\w+)\s*\(', re.M)


def targets(mod):
    """Unit(s) to run for a module: one per TestCase class when it has several (balances the workers: one slow
    module no longer runs alone while the others sit idle), else the module itself."""
    text = (ROOT / 'tests' / f'{mod}.py').read_text(encoding='utf-8', errors='replace')
    cls = [c for c in CLASS_RE.findall(text) if c.startswith('Test')]
    return [f'tests.{mod}.{c}' for c in cls] if len(cls) > 1 else [f'tests.{mod}']


def run(unit):
    mod = unit
    t = time.monotonic()
    p = subprocess.run([sys.executable, '-m', 'unittest', unit], cwd=str(ROOT),
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    out = p.stdout + p.stderr
    rc = 0 if (p.returncode == 0 or 'NO TESTS RAN' in out) else p.returncode
    return mod, rc, out, time.monotonic() - t


def main(argv):
    jobs = min(8, os.cpu_count() or 2)
    mods, want_changed, deep = [], False, False
    it = iter(argv)
    for a in it:
        if a == '-j':
            jobs = max(1, int(next(it, '1')))
        elif a == '--changed':
            want_changed = True
        elif a == '--deep':
            deep = True
        else:
            mods.append(a.replace('.py', '').replace('tests.', '').replace('tests/', ''))
    every = sorted(p.stem for p in (ROOT / 'tests').glob('test_*.py'))
    if want_changed and not mods:
        mods, why = affected(every, deep)
        print(why, flush=True)
        if not mods:
            print('nothing to run: no code file changed')
            return 0
    mods = mods or every
    units = [u for m in mods for u in targets(m)]
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(run, units))
    failed = []
    for mod, rc, out, secs in results:
        if rc != 0:
            _m, rc2, out2, _s = run(mod)                # one solo retry
            if rc2 != 0:
                failed.append((mod, out2))
            else:
                print(f'  (flaky under load, passed alone: {mod})')
    for mod, rc, out, secs in sorted(results, key=lambda r: -r[3])[:3]:
        print(f'  slowest: {mod:36s} {secs:6.1f}s')
    for mod, out in failed:
        print(f'\nFAILED {mod}\n' + '\n'.join(out.strip().splitlines()[-25:]))
    print(f'\n{len(mods)} module(s) in {len(units)} unit(s), {len(failed)} failed, '
          f'{time.monotonic() - t0:.0f}s wall with {jobs} workers')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
