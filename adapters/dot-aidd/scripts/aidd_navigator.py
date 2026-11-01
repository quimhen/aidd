"""Build a read-only navigator from local AIDD specification files."""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

MAX_SOURCE_BYTES = 512 * 1024


def _objective(text: str) -> str:
    for line in text.splitlines():
        cells = [part.strip() for part in line.strip().strip('|').split('|')]
        if len(cells) >= 2 and ('business objective' in cells[0].casefold()
                                or cells[0].casefold().startswith('objetivo')):
            return cells[1].strip('`') or 'Objetivo no disponible.'
    return 'Objetivo no disponible.'


def _verification_history(root: Path) -> dict:
    """Read recorded rounds once, without treating historical success as current."""
    if not (root / '.aidd').is_dir():
        return {}
    try:
        try:
            from . import aidd_evidence as ev
        except ImportError:
            import aidd_evidence as ev
        history = {}
        for event in ev.events(root, kind='verify_run'):
            detail = event.get('detail') or {}
            spec = detail.get('spec')
            if not isinstance(spec, str) or not spec:
                continue
            item = history.setdefault(spec, {'rounds': 0, 'last': '', 'result': 'indeterminado'})
            item['rounds'] += 1
            timestamp = event.get('ts')
            if isinstance(timestamp, (int, float)) and timestamp > 0:
                item['last'] = datetime.fromtimestamp(timestamp, timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
            item['result'] = ('aprobada' if detail.get('ok') is True else
                              'no aprobada' if detail.get('ok') is False else 'indeterminado')
        return history
    except (OSError, ValueError, TypeError, OverflowError):
        return {}


def _screen_revisions(units, spec_id):
    lines = []
    for unit in units:
        if unit.spec_id != spec_id:
            continue
        for ref in unit.visual_refs:
            lines.append(f'{ref.screen_id} · versión {ref.revision_id} · enmienda {unit.unit_id}'
                         f' · roles: {", ".join(ref.roles)} · estados: {", ".join(ref.states)}'
                         f' · resoluciones: {", ".join(ref.viewports)}')
    return sorted(lines)


def _link(path: Path) -> bool:
    try:
        stat = os.lstat(path)
    except FileNotFoundError:
        return False
    return path.is_symlink() or bool(getattr(stat, 'st_file_attributes', 0) & 0x400)


def _read(path: Path) -> str:
    if _link(path) or not path.is_file():
        return ''
    try:
        with path.open('rb') as source:
            data = source.read(MAX_SOURCE_BYTES + 1)
        if len(data) > MAX_SOURCE_BYTES:
            return '[Archivo demasiado grande para mostrar]'
        return data.decode('utf-8')
    except (OSError, UnicodeError):
        return '[No se pudo leer el archivo]'


def collect_specs(project: Path) -> list[dict]:
    root = project.resolve(strict=True)
    specs = root / 'specs'
    if _link(specs) or not specs.is_dir():
        return []
    try:
        try:
            from .aidd_units import discover_units
        except ImportError:
            from aidd_units import discover_units
        units = discover_units(root)
        unit_error = ''
    except (ImportError, OSError, ValueError) as exc:
        units, unit_error = (), f'No se pudieron leer las unidades: {type(exc).__name__}'
    history = _verification_history(root)
    output = []
    for directory in sorted(specs.iterdir(), key=lambda item: item.name.casefold()):
        if _link(directory) or not directory.is_dir():
            continue
        text = _read(directory / 'spec.md')
        if not text:
            continue
        plan, tasks = _read(directory / 'plan.md'), _read(directory / 'tasks.md')
        title = next((line.lstrip('# ').strip() for line in text.splitlines()
                      if line.startswith('# ')), directory.name)
        task_ids = set(re.findall(r'(?m)^\|\s*(T-\d+)\s*\|', tasks))
        files = sorted(p.name for p in directory.iterdir() if p.is_file() and not _link(p))
        amendments = [name for name in files if name.lower().startswith('amendment')]
        screens = sorted(set(re.findall(r'\bSCREEN-\d+\b', text + '\n' + _read(directory / 'mockup-audit.md'))))
        evidence = directory / 'evidence'
        evidence_names = (sorted(p.name for p in evidence.iterdir() if p.is_file() and not _link(p))
                          if evidence.is_dir() and not _link(evidence) else [])
        unit_lines = [f'{u.unit_id} · secuencia {u.sequence} · dependencias: {", ".join(u.parents) or "ninguna"} · estado sin verificar'
                      for u in units if u.spec_id == directory.name]
        if unit_error:
            unit_lines.append(unit_error)
        review = directory / 'review.html'
        review_url = review.resolve().as_uri() if review.is_file() and not _link(review) else ''
        output.append({'id': directory.name, 'title': title, 'summary': _objective(text),
                       'spec': text, 'plan': plan or 'Plan no disponible.', 'tasks': len(task_ids),
                       'tasks_text': tasks or 'Tareas no disponibles.',
                       'amendments': amendments, 'units': unit_lines, 'screens': screens,
                       'screen_revisions': _screen_revisions(units, directory.name), 'evidence': evidence_names, 'files': files,
                       'review_url': review_url, 'history': history.get(directory.name)})
    return output


def build_navigator(project: Path) -> str:
    template = Path(__file__).resolve().parents[1] / 'templates' / 'navigator.html'
    content = template.read_text(encoding='utf-8')
    marker = '__AIDD_NAVIGATOR_DATA__'
    if content.count(marker) != 1:
        raise ValueError('invalid navigator template')
    payload = json.dumps(collect_specs(project), ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return content.replace(marker, payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output.absolute()
    project = args.project.resolve(strict=True)
    if output.suffix.lower() != '.html' or output.name.lower() == 'review.html':
        raise ValueError('output must be an HTML file distinct from review.html')
    if _link(output) or any(_link(parent) for parent in output.parents):
        raise ValueError('output links are not supported')
    try:
        output.resolve().relative_to(project / '.aidd')
    except ValueError:
        pass
    else:
        raise ValueError('output cannot be inside AIDD state')
    output.write_text(build_navigator(project), encoding='utf-8')
    print('Navigator written:', args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
