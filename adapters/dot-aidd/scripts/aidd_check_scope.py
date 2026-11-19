"""Read-only structural-check scope; unit consent is never a build/close authorization."""
from dataclasses import dataclass
from pathlib import Path
import re

import aidd_evidence
import aidd_rules
import aidd_units


@dataclass(frozen=True)
class CheckScope:
    root: Path
    base: Path
    directory: Path
    unit: object = None
    closure: tuple = ()


def resolve_check_scope(spec, unit_id=None):
    directory = Path(spec).resolve(strict=True)
    if not directory.is_dir():
        raise ValueError('spec directory does not exist')
    if unit_id is None:
        if directory.parent.name == 'amendments':
            raise ValueError('select an amendment explicitly: check <base-spec> --unit <unit-id>')
        root = aidd_evidence.known_root(directory) or directory
        return CheckScope(root, directory, directory)
    if not isinstance(unit_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', unit_id):
        raise ValueError('invalid unit identity')
    if directory.parent.name != 'specs':
        raise ValueError('--unit requires the base specs/<spec-id> directory')
    root = directory.parent.parent.resolve(strict=True)
    key = f'{directory.name}:{unit_id}'
    closure = aidd_units.discover_unit_scope(root, directory.name, [key])
    selected = next(item for item in closure if item.key == key)
    if any(item.schema_version != 2 for item in closure):
        raise ValueError('structural unit checking requires manifest schema 2')
    for item in closure:
        folder = root / 'specs' / item.spec_id / 'amendments' / item.unit_id
        required = ['spec.md', 'plan.md', 'tasks.md', *aidd_rules.tasks_batch_names(folder)]
        if any(not (folder / name).is_file() or (folder / name).relative_to(root).as_posix() not in item.paths
               for name in required):
            raise ValueError(f'{item.key} must seal its spec, plan and task files')
    return CheckScope(root, directory, root / 'specs' / selected.spec_id / 'amendments' / selected.unit_id,
                      selected, tuple(closure))


def consent_states(scope):
    if scope.unit is None:
        return []
    events = aidd_evidence.events(scope.root, kind='unit_approved')
    states = []
    for item in scope.closure:
        digest = aidd_rules.unit_approval_hash(item, scope.root)
        records = [(event.get('detail') or {}) for event in events
                   if (event.get('detail') or {}).get('spec') == item.spec_id
                   and (event.get('detail') or {}).get('unit_id') == item.unit_id]
        approved = any(record.get('digest') == digest
                       and re.fullmatch(r'[0-9a-f]{64}', str(record.get('review_sha256', '')))
                       for record in records)
        states.append({'unit': item.key, 'digest': digest,
                       'state': 'approved' if approved else 'invalid' if records else 'pending'})
    return states


def structural_rules(scope):
    findings = aidd_rules.check_spec_dir(scope.directory, root=scope.root, static_only=True)
    if scope.unit is None:
        return findings
    findings = [finding for finding in findings if finding['rule'] != 'R6']
    for consent in consent_states(scope):
        if consent['state'] != 'approved':
            state = consent['state']
            findings.append({'rule': 'R6', 'message': f"Unit {consent['unit']} native owner consent {state}.",
                             'fix': 'Review and approve the current native unit; this report grants no authorization.'})
    return findings


def observed_scope_paths(scope):
    """Extra observed inputs, not a complete dependency or evidence fingerprint."""
    result = {}
    for item in scope.closure:
        names = {f'specs/{item.spec_id}/amendments/{item.unit_id}/manifest.json',
                 *item.paths, *item.inputs, *item.config}
        for name in sorted(names):
            path = (scope.root / name).resolve(strict=False)
            path.relative_to(scope.root)
            result[f'unit-input/{name}'] = path
    return result
