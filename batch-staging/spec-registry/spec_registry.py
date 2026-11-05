#!/usr/bin/env python3
"""Spec registry: one read-only pass over every spec that resolves what `aidd pending` over-reports.

It is built ON TOP of `aidd_progress` (same path rules as `aidd progress` / `aidd pending`: declared path
shorthand, suffix lookup). It adds only what that module does not know:
  * `(delete)` targets: the file must NOT exist (a missing file means the task is done);
  * tables renamed by F30 (`docs/rename-sap-names/rename_map.csv`): `ordr_table.dart` -> `oped_table.dart`;
  * migrations renumbered or renamed: same name without the numeric prefix.
Also reports the evidence debt (R10) and mechanical gaps per spec from `check_spec.py`.
Read-only: never edits a spec, a task or the code.

    python tools/spec_registry.py [--root DIR] [--out FILE.md] [--csv FILE.csv]
    python tools/spec_registry.py --spec F37 --verbose
"""
import argparse, csv, glob, os, re, subprocess, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
DELETE_RE = re.compile(r'`([^`]+?)\s*\(delete[^)]*\)`')


def load_progress(root):
    sys.path.insert(0, os.path.join(root, '.aidd', 'scripts'))
    import aidd_progress  # noqa: E402
    return aidd_progress


def load_rename_map(root):
    """old table name (lower) -> new table name (lower), from F30's rename_map.csv."""
    m = {}
    p = os.path.join(root, 'docs/rename-sap-names/rename_map.csv')
    if os.path.exists(p):
        with open(p, encoding='utf-8', errors='ignore', newline='') as fh:
            for r in csv.DictReader(l for l in fh if not l.startswith('#')):
                if (r.get('kind') or '').endswith('table'):
                    m[(r['old'] or '').lower()] = (r['new'] or '').lower()
    return m


def kind_of(p):
    if p.endswith('.test.sql') or ('/tests/' in p and p.endswith('.sql')):
        return 'TEST'
    if p.endswith('.sql'):
        return 'SQL'
    if p.startswith('specs/') or p.startswith('docs/'):
        return 'DOC'
    return 'CODE'


class Resolver:
    def __init__(self, root):
        self.root = root
        self.prog = load_progress(root)
        self.rename = load_rename_map(root)
        self.mig = {}
        for f in glob.glob(os.path.join(root, '**/migrations/*.sql'), recursive=True):
            if 'node_modules' not in f:
                self.mig[re.sub(r'^\d+_', '', os.path.basename(f))] = f

    def found(self, p):
        return self.prog._resolve(Path(self.root), p) is not None

    def resolve(self, p, delete):
        """-> (state, note). states: PRESENT, DELETED, RENAMED, RENUMBERED, MISSING."""
        if delete:
            return ('DELETED', '') if not self.found(p) else ('MISSING', 'marked (delete) but still exists')
        if self.found(p):
            return 'PRESENT', ''
        base = os.path.basename(p)
        if '/migrations/' in p and re.sub(r'^\d+_', '', base) in self.mig:
            return 'RENUMBERED', os.path.basename(self.mig[re.sub(r'^\d+_', '', base)])
        m = re.match(r'(.+)_table\.dart$', base)
        if m and m.group(1).lower() in self.rename:
            new = os.path.join(os.path.dirname(p), self.rename[m.group(1).lower()] + '_table.dart')
            if self.found(new):
                return 'RENAMED', os.path.basename(new)
        return 'MISSING', ''


def analyse_spec(root, spec_dir, res):
    tasks = os.path.join(spec_dir, 'tasks.md')
    info = dict(spec=os.path.basename(spec_dir), has_tasks=os.path.exists(tasks), rows=0, measurable=0,
                present=0, deleted=0, renamed=0, renumbered=0, missing=[], declared=0, notarget=0)
    if not info['has_tasks']:
        return info
    txt = open(tasks, encoding='utf-8', errors='ignore').read()
    deletes = {d.strip().replace('\\', '/') for d in DELETE_RE.findall(txt)}
    seen = set()
    for t in res.prog.parse_tasks(txt):
        key = (t['id'], tuple(t['paths']))
        if key in seen:
            continue
        seen.add(key)
        info['rows'] += 1
        if not t['paths']:
            info['notarget'] += 1
            continue
        info['measurable'] += 1
        row_missing = []
        for p in t['paths']:
            st, note = res.resolve(p, p in deletes)
            if st == 'PRESENT':
                info['present'] += 1
            elif st == 'DELETED':
                info['deleted'] += 1
            elif st == 'RENAMED':
                info['renamed'] += 1
            elif st == 'RENUMBERED':
                info['renumbered'] += 1
            else:
                row_missing.append((kind_of(p), p, note))
        if row_missing:
            if re.match(r'(done|superseded|n/a)', t['status'].strip().lower()):
                info['declared'] += 1
            else:
                for kind, p, note in row_missing:
                    info['missing'].append((t['id'], kind, p))
    return info


def gaps_of(root, spec_dir):
    """(total gaps, R10 gaps) from check_spec.py."""
    cs = os.path.join(root, '.aidd/scripts/check_spec.py')
    out = subprocess.run([sys.executable, cs, spec_dir], capture_output=True, text=True, encoding='utf-8', errors='ignore').stdout
    m = re.search(r'(\d+) gap\(s\) found', out)
    return (int(m.group(1)) if m else 0), len(re.findall(r'\bR10\b', out))


def verdict(i):
    if not i['has_tasks']:
        return 'NO-TASKS'
    if i['missing']:
        return 'REAL-WORK'
    if i['r10']:
        return 'EVIDENCE-DEBT'
    if i['gaps']:
        return 'FORMAT-GAPS'
    return 'CLEAN'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--out')
    ap.add_argument('--csv')
    ap.add_argument('--spec')
    ap.add_argument('--verbose', action='store_true')
    ap.add_argument('--no-gaps', action='store_true', help='skip check_spec (faster)')
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    res = Resolver(root)
    rows = []
    for d in sorted(glob.glob(os.path.join(root, 'specs/[FPS][0-9]*'))):
        if a.spec and a.spec not in os.path.basename(d):
            continue
        i = analyse_spec(root, d, res)
        i['gaps'], i['r10'] = (0, 0) if a.no_gaps else gaps_of(root, d)
        i['verdict'] = verdict(i)
        rows.append(i)
    lines = ['# Registro de specs (generado por tools/spec_registry.py, solo lectura)', '',
             '| Spec | Veredicto | Filas | Medibles | Presentes | Borradas | Renombradas | Renumeradas | Faltantes reales | R10 | Gaps check_spec |',
             '|---|---|---|---|---|---|---|---|---|---|---|']
    for i in rows:
        lines.append(f"| {i['spec']} | {i['verdict']} | {i['rows']} | {i['measurable']} | {i['present']} | {i['deleted']} | "
                     f"{i['renamed']} | {i['renumbered']} | {len(i['missing'])} | {i['r10']} | {i['gaps']} |")
    cnt = {}
    for i in rows:
        cnt[i['verdict']] = cnt.get(i['verdict'], 0) + 1
    lines += ['', '**Resumen:** ' + ', '.join(f'{k}={v}' for k, v in sorted(cnt.items())), '',
              '## Faltantes reales por spec (tras resolver borrados, renombrados y renumeraciones)', '']
    for i in rows:
        if i['missing']:
            lines.append(f"### {i['spec']} ({len(i['missing'])})")
            for tid, kind, p in i['missing'][: (400 if a.verbose else 25)]:
                lines.append(f'- {tid} [{kind}] `{p}`')
            if not a.verbose and len(i['missing']) > 25:
                lines.append(f"- ... {len(i['missing']) - 25} mas (usar --verbose)")
            lines.append('')
    text = '\n'.join(lines)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        open(a.out, 'w', encoding='utf-8').write(text + '\n')
        print('escrito', a.out)
    else:
        print(text)
    if a.csv:
        with open(a.csv, 'w', encoding='utf-8', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['spec', 'verdict', 'rows', 'measurable', 'present', 'deleted', 'renamed', 'renumbered', 'missing', 'r10', 'gaps'])
            for i in rows:
                w.writerow([i['spec'], i['verdict'], i['rows'], i['measurable'], i['present'], i['deleted'], i['renamed'],
                            i['renumbered'], len(i['missing']), i['r10'], i['gaps']])
        print('escrito', a.csv)


if __name__ == '__main__':
    main()
