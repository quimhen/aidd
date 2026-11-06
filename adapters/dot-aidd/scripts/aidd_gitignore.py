#!/usr/bin/env python3
"""
aidd_gitignore -- make a project's .gitignore ignore what AIDD generates (amendment 10 of spec 007, FR-412).

    aidd_gitignore.py <project_root> [--dry-run]

Reads the pattern list from templates/gitignore.aidd (next to this script's folder) and appends ONLY the missing
lines, once, under its comment header. Idempotent; never removes or reorders a line; never untracks a file that is
already versioned (that stays the owner's `git rm --cached` decision). Exit 0 always except on an unwritable file (1).
"""
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / 'templates' / 'gitignore.aidd'


def wanted_lines(template=TEMPLATE):
    """(header, [pattern]) of the template."""
    lines = [ln.rstrip() for ln in Path(template).read_text(encoding='utf-8').splitlines()]
    header = next((ln for ln in lines if ln.startswith('#')), '# AIDD generated files')
    return header, [ln for ln in lines if ln and not ln.startswith('#')]


def ensure(project_root, dry_run=False, template=TEMPLATE):
    """The patterns added to <project_root>/.gitignore (empty when all were present)."""
    gi = Path(project_root) / '.gitignore'
    text = gi.read_text(encoding='utf-8') if gi.is_file() else ''
    have = {ln.strip() for ln in text.splitlines()}
    header, pats = wanted_lines(template)
    missing = [p for p in pats if p not in have]
    if missing and not dry_run:
        block = ('' if not text or text.endswith('\n') else '\n') + ('\n' if text else '')
        block += (header + '\n' if header not in have else '') + '\n'.join(missing) + '\n'
        with open(gi, 'a', encoding='utf-8', newline='\n') as fh:
            fh.write(block)
    return missing


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = '--dry-run' in argv
    args = [a for a in argv if a != '--dry-run']
    if len(args) != 1:
        print(__doc__.strip())
        return 2
    try:
        added = ensure(args[0], dry_run=dry)
    except OSError as exc:
        print(f'aidd gitignore: cannot update .gitignore ({exc})', file=sys.stderr)
        return 1
    verb = 'would add' if dry else 'added'
    print(f'.gitignore: {verb} {len(added)} AIDD generated pattern(s)' + (': ' + ', '.join(added) if added else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
