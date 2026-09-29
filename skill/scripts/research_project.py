#!/usr/bin/env python3
"""
aidd research mode — bootstraps candidate spec folders on a brownfield
project that has code but no specs/ yet (or only a few), so the spec graph
(find_spec.py's index.toon) has something to index from day one.

Where this fits: alongside copying templates/charter.md, once per
project, BEFORE Step -1 has any specs to search. It is mechanical, stdlib
only — it never invents spec content. It only detects candidate feature
boundaries (route/page/screen/view-like files, grouped by directory) and
prints a proposed specs/[###-slug]/ list. Writing the real spec.md /
mockup-audit.md content for each proposed area is still Steps 0-2, done by
an agent with judgment — same division of labor as every other script in
this skill (check_spec.py flags gaps, find_spec.py searches; neither
fabricates spec prose).

Why this exists instead of a file-by-file knowledge-graph tool: a generic
graph builder (e.g. graphify) has no documented spec to start from, so it
must read every file in the repo and dispatch an LLM pass per chunk to
extract meaning — thorough, but token-expensive, and it re-derives structure
on every rebuild. AIDD's own graph (find_spec.py's index.toon) is built by
parsing the specs the project already maintains (mockup-audit.md's own
tables) — a few regex passes over markdown, no LLM, refreshed via a cheap
mtime check per file. That's only possible once specs exist; this script is
the one-time bridge for a project that doesn't have them yet, so the cheap
path becomes available instead of staying dependent on a full-repo re-scan
every time.

Detection heuristics (naming conventions only, no parsing of file content):
  - Directories literally named one of: pages, screens, views, routes,
    controllers, features, modules (case-insensitive), anywhere under the
    scan root (excluding common noise dirs).
  - Within a hit directory, group immediate children: a subdirectory is one
    candidate area; a bare file (e.g. login_page.dart, OrdersController.cs)
    is one candidate area named after its stem.
  - Framework-specific extras: Next.js/Nuxt `app/` or `pages/` directories
    at the project root.

Usage:
    python research_project.py [project-root] [--propose]
    python research_project.py [project-root] --json

--propose (default) prints a numbered list of candidate specs/[###-slug]/
folders, largest/most-central directories first (by file count), and does
NOT write anything — the agent reviews the list, drops noise, and creates
real spec folders for the ones worth specifying.
--json prints the same data as JSON, for a caller that wants to script the
next step instead of reading the text list.

Exit code 0 = ran fine, whether or not any candidates were found.
Exit code 2 = usage error.
"""
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HIT_DIR_NAMES = {
    'pages', 'screens', 'views', 'routes', 'controllers', 'features', 'modules',
}

ROOT_HIT_DIR_NAMES = {'app', 'pages'}  # Next.js/Nuxt-style, only meaningful at project root

NOISE_DIR_NAMES = {
    '.git', 'node_modules', '.venv', 'venv', '__pycache__', 'build', 'dist',
    '.dart_tool', '.gradle', 'target', 'bin', 'obj', '.next', '.nuxt',
    'graphify-out', 'specs', '.specify', '.aidd', 'vendor',
}

CODE_SUFFIXES = {
    '.dart', '.ts', '.tsx', '.js', '.jsx', '.py', '.rb', '.go', '.rs',
    '.java', '.kt', '.cs', '.php', '.vue', '.svelte',
}


def slugify(name: str) -> str:
    out = []
    prev_dash = False
    for ch in name.strip().lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append('-')
            prev_dash = True
    return ''.join(out).strip('-') or 'area'


def _is_noise(path_parts):
    return any(part in NOISE_DIR_NAMES or (part.startswith('.') and part not in ('.', '..'))
               for part in path_parts)


def iter_dirs(root: Path):
    for p in root.rglob('*'):
        if not p.is_dir():
            continue
        rel_parts = p.relative_to(root).parts
        if _is_noise(rel_parts):
            continue
        yield p


def find_hit_dirs(root: Path):
    """Directories matching the naming heuristic, outermost first. A hit dir
    nested inside another hit dir (e.g. features/auth/presentation/pages
    under features/) is dropped — it's the same feature area at a finer
    grain, not a second one, and counting both double-proposes it."""
    all_hits = []
    for p in iter_dirs(root):
        name = p.name.lower()
        if name in HIT_DIR_NAMES or (name in ROOT_HIT_DIR_NAMES and p.parent == root):
            all_hits.append(p)

    all_hits.sort(key=lambda p: len(p.parts))
    kept = []
    for p in all_hits:
        if any(existing in p.parents for existing in kept):
            continue
        kept.append(p)
    return kept


def count_code_files(p: Path) -> int:
    n = 0
    try:
        for f in p.rglob('*'):
            if f.is_file() and f.suffix.lower() in CODE_SUFFIXES:
                n += 1
    except OSError:
        pass
    return n


def candidates_under(hit_dir: Path):
    """One candidate per immediate child: subdirectory, or bare code file."""
    out = []
    try:
        children = sorted(hit_dir.iterdir())
    except OSError:
        return out
    for child in children:
        if child.is_dir():
            if child.name.lower() in NOISE_DIR_NAMES or child.name.startswith('.'):
                continue
            files = count_code_files(child)
            if files == 0:
                continue
            out.append({'name': child.stem, 'path': str(child), 'files': files})
        elif child.is_file() and child.suffix.lower() in CODE_SUFFIXES:
            out.append({'name': child.stem, 'path': str(child), 'files': 1})
    return out


def propose(root: Path):
    seen_paths = set()
    candidates = []
    for hit_dir in find_hit_dirs(root):
        for c in candidates_under(hit_dir):
            if c['path'] in seen_paths:
                continue
            seen_paths.add(c['path'])
            candidates.append(c)

    # Merge candidates that share a slug (e.g. "orders" found under both
    # pages/ and controllers/) into one proposed spec area.
    by_slug = {}
    for c in candidates:
        slug = slugify(c['name'])
        entry = by_slug.setdefault(slug, {'slug': slug, 'name': c['name'], 'sources': [], 'files': 0})
        entry['sources'].append(c['path'])
        entry['files'] += c['files']

    ordered = sorted(by_slug.values(), key=lambda e: e['files'], reverse=True)
    for i, entry in enumerate(ordered, start=1):
        entry['proposed_folder'] = f"specs/{i:03d}-{entry['slug']}"
    return ordered


def has_existing_specs(root: Path) -> bool:
    specs_dir = root / 'specs'
    if not specs_dir.is_dir():
        return False
    return any(p.is_dir() for p in specs_dir.iterdir())


def main():
    args = sys.argv[1:]
    out_json = '--json' in args
    args = [a for a in args if a not in ('--propose', '--json')]
    if len(args) > 1:
        print(__doc__)
        sys.exit(2)

    root = Path(args[0]).resolve() if args else Path.cwd()
    if not root.is_dir():
        print(f"Not a directory: {root}")
        sys.exit(2)

    if has_existing_specs(root) and not out_json:
        print(f"{root / 'specs'} already has spec folder(s) — research mode is for a project "
              "with none yet. Use find_spec.py to search what's already there instead.")

    candidates = propose(root)

    if out_json:
        print(json.dumps({'root': str(root), 'candidates': candidates}, indent=2))
        sys.exit(0)

    print(f"aidd research — candidate spec areas under {root}")
    print("=" * 60)
    if not candidates:
        print("No route/page/screen/controller-like directories found under common naming "
              "conventions (pages/, screens/, views/, routes/, controllers/, features/, "
              "modules/, or a root app/). Nothing to propose — create the first spec normally "
              "via Step -1/Step 0 once a real feature request comes in.")
        sys.exit(0)

    for i, entry in enumerate(candidates, start=1):
        srcs = ', '.join(entry['sources'][:3])
        more = '' if len(entry['sources']) <= 3 else f" (+{len(entry['sources']) - 3} more)"
        print(f"{i}. {entry['proposed_folder']}  —  {entry['name']}  "
              f"({entry['files']} code file(s): {srcs}{more})")

    print(f"\n{len(candidates)} candidate area(s). These are directory-name heuristics only — "
          "no file content was read and no spec was written. Review the list, drop noise (a "
          "shared/util-style folder is not a feature), then run Step 0-2 per area you keep to "
          "write its real mockup-audit.md/spec.md — this script never fabricates spec content.")
    sys.exit(0)


if __name__ == '__main__':
    main()
