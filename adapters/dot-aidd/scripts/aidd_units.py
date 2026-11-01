"""Read-only, fail-closed discovery of versioned amendment units.

Unit manifests describe proposed work; they are not approval evidence.
"""
from __future__ import annotations

import heapq
import hashlib
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Sequence

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_KEYS = {"schema_version", "spec_id", "unit_id", "sequence", "parents", "paths", "targets"}
_KEYS_V2 = _KEYS | {"version", "inputs", "config", "visual_refs"}
_MAX_BYTES = 1024 * 1024


@dataclass(frozen=True)
class VisualReference:
    screen_id: str
    revision_id: str
    source: str
    assets: tuple[str, ...]
    states: tuple[str, ...]
    roles: tuple[str, ...]
    viewports: tuple[str, ...]


@dataclass(frozen=True)
class UnitManifest:
    schema_version: int
    spec_id: str
    unit_id: str
    sequence: int
    parents: tuple[str, ...]
    paths: tuple[str, ...]
    targets: tuple[str, ...]
    version: str = ''
    inputs: tuple[str, ...] = ()
    config: tuple[str, ...] = ()
    visual_refs: tuple[VisualReference, ...] = ()

    @property
    def key(self) -> str:
        return f"{self.spec_id}:{self.unit_id}"


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _contained(path: Path, root: Path) -> Path:
    try:
        resolved = path.resolve(strict=False)
        resolved.relative_to(root)
        return resolved
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(f"path escapes project or cannot be resolved: {path}") from exc


def _paths(value: object, root: Path, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise ValueError(f"{label} must be an array of strings")
    output = []
    for item in value:
        win = PureWindowsPath(item)
        posix = PurePosixPath(item)
        if (not item or "\\" in item or win.drive or win.root or posix.is_absolute()
                or any(part in (".", "..") for part in item.split("/"))
                or "//" in item or item.endswith("/")):
            raise ValueError(f"invalid project-relative path: {item!r}")
        target = _contained(root / item, root)
        output.append(target.relative_to(root).as_posix())
    if len({name.casefold() for name in output}) != len(output):
        raise ValueError(f"duplicate or case-ambiguous {label}")
    return tuple(output)


def _visual_refs(value: object, root: Path) -> tuple[VisualReference, ...]:
    keys = {'screen_id', 'revision_id', 'source', 'assets', 'states', 'roles', 'viewports'}
    if not isinstance(value, list):
        raise ValueError('visual_refs must be an array')
    result = []
    for ref in value:
        if not isinstance(ref, dict) or set(ref) != keys:
            raise ValueError('invalid visual reference fields')
        if any(not isinstance(ref[k], str) or not _ID.fullmatch(ref[k]) for k in ('screen_id', 'revision_id')):
            raise ValueError('invalid screen or revision identifier')
        source = _paths([ref['source']], root, 'visual source')[0]
        assets = _paths(ref['assets'], root, 'visual assets')
        values = []
        for key in ('states', 'roles', 'viewports'):
            items = ref[key]
            if (not isinstance(items, list) or not items
                    or any(not isinstance(x, str) or not x.strip() for x in items)
                    or len({x.casefold() for x in items}) != len(items)):
                raise ValueError('invalid visual ' + key)
            if key == 'viewports' and any(not re.fullmatch(r'[1-9][0-9]*x[1-9][0-9]*', x) for x in items):
                raise ValueError('invalid visual viewport')
            values.append(tuple(items))
        result.append(VisualReference(ref['screen_id'], ref['revision_id'], source, assets, *values))
    if len({(r.screen_id.casefold(), r.revision_id.casefold()) for r in result}) != len(result):
        raise ValueError('duplicate visual revision')
    return tuple(result)


def load_unit(path: Path, project_root: Path) -> UnitManifest:
    """Load a manifest; malformed, ambiguous or escaping inputs raise ValueError."""
    try:
        root = project_root.resolve(strict=True)
        manifest = _contained(path, root)
        relative = manifest.relative_to(root)
        if (len(relative.parts) != 5 or relative.parts[0] != "specs"
                or relative.parts[2] != "amendments" or relative.parts[4] != "manifest.json"):
            raise ValueError("manifest must be specs/<spec>/amendments/<unit>/manifest.json")
        with manifest.open("rb") as stream:
            raw = stream.read(_MAX_BYTES + 1)
        if len(raw) > _MAX_BYTES:
            raise ValueError("manifest exceeds 1 MiB")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
        if not isinstance(data, dict) or data.get('schema_version') not in (1, 2):
            raise ValueError("invalid manifest keys")
        if type(data["schema_version"]) is not int:
            raise ValueError("unsupported schema version")
        if set(data) != (_KEYS if data['schema_version'] == 1 else _KEYS_V2):
            raise ValueError('invalid manifest keys')
        spec, unit, sequence = data["spec_id"], data["unit_id"], data["sequence"]
        if (not isinstance(spec, str) or not _ID.fullmatch(spec)
                or not isinstance(unit, str) or not _ID.fullmatch(unit)
                or spec != relative.parts[1] or unit != relative.parts[3]):
            raise ValueError("manifest identifiers do not match directory")
        if type(sequence) is not int or sequence <= 0:
            raise ValueError("sequence must be a positive integer")
        parents = data["parents"]
        if not isinstance(parents, list) or any(not isinstance(p, str) for p in parents):
            raise ValueError("parents must be an array of qualified IDs")
        for parent in parents:
            parts = parent.split(":")
            if len(parts) != 2 or not all(_ID.fullmatch(part) for part in parts):
                raise ValueError(f"invalid parent: {parent}")
        if len(set(parents)) != len(parents):
            raise ValueError("duplicate parent")
        paths = _paths(data['paths'], root, 'paths')
        targets = _paths(data['targets'], root, 'targets')
        if data['schema_version'] == 1:
            return UnitManifest(1, spec, unit, sequence, tuple(parents), paths, targets)
        if not isinstance(data['version'], str) or not _ID.fullmatch(data['version']):
            raise ValueError('invalid unit version')
        return UnitManifest(2, spec, unit, sequence, tuple(parents), paths, targets,
                            data['version'], _paths(data['inputs'], root, 'inputs'),
                            _paths(data['config'], root, 'config'), _visual_refs(data['visual_refs'], root))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load unit manifest: {path}") from exc


def discover_units(project_root: Path) -> tuple[UnitManifest, ...]:
    """Discover drafts too: an incomplete amendment must not disappear silently."""
    try:
        root = project_root.resolve(strict=True)
        specs = root / "specs"
        if specs.is_symlink() and not specs.exists():
            raise ValueError(f"broken specs link: {specs}")
        if not specs.exists():
            return ()
        _contained(specs, root)
        result = []
        for spec in specs.iterdir():
            if spec.is_symlink() and not spec.exists():
                raise ValueError(f"broken spec link: {spec}")
            if not spec.is_dir():
                continue
            _contained(spec, root)
            amendments = spec / "amendments"
            if amendments.is_symlink() and not amendments.exists():
                raise ValueError(f"broken amendments link: {amendments}")
            if not amendments.exists():
                continue
            _contained(amendments, root)
            if not amendments.is_dir():
                raise ValueError(f"not a directory: {amendments}")
            for unit in amendments.iterdir():
                if not unit.is_symlink() and unit.is_file():
                    continue  # Regular notes are not unit identities.
                if not unit.is_dir():
                    raise ValueError(f"not a unit directory: {unit}")
                _contained(unit, root)
                manifest = unit / "manifest.json"
                if not manifest.is_file():
                    raise ValueError(f"missing unit manifest: {manifest}")
                result.append(load_unit(manifest, root))
        return resolve_units(result)
    except OSError as exc:
        raise ValueError("cannot discover unit manifests") from exc


def resolve_units(units: Sequence[UnitManifest]) -> tuple[UnitManifest, ...]:
    """Return a stable topological order, rejecting ambiguity and cycles."""
    by_key: dict[str, UnitManifest] = {}
    folded_keys: set[str] = set()
    sequences: set[tuple[str, int]] = set()
    for unit in units:
        if (unit.key.casefold() in folded_keys
                or (unit.spec_id.casefold(), unit.sequence) in sequences):
            raise ValueError(f"duplicate unit ID or sequence: {unit.key}")
        by_key[unit.key] = unit
        folded_keys.add(unit.key.casefold())
        sequences.add((unit.spec_id.casefold(), unit.sequence))
    indegree = {key: 0 for key in by_key}
    children: dict[str, list[str]] = {key: [] for key in by_key}
    for unit in units:
        if len(set(unit.parents)) != len(unit.parents):
            raise ValueError(f"duplicate parent: {unit.key}")
        for parent in unit.parents:
            if parent not in by_key:
                raise ValueError(f"missing parent {parent} for {unit.key}")
            indegree[unit.key] += 1
            children[parent].append(unit.key)
    ready = [(u.sequence, u.spec_id, u.unit_id) for u in units if indegree[u.key] == 0]
    heapq.heapify(ready)
    result = []
    while ready:
        _, spec, unit_id = heapq.heappop(ready)
        key = f"{spec}:{unit_id}"
        result.append(by_key[key])
        for child in children[key]:
            indegree[child] -= 1
            if not indegree[child]:
                u = by_key[child]
                heapq.heappush(ready, (u.sequence, u.spec_id, u.unit_id))
    if len(result) != len(by_key):
        raise ValueError("unit dependency cycle")
    return tuple(result)


def list_spec_unit_keys(project_root: Path, spec_id: str) -> tuple[str, ...]:
    """List unit identities without parsing unrelated unit content."""
    if not isinstance(spec_id, str) or not _ID.fullmatch(spec_id):
        raise ValueError('invalid spec identifier')
    root = Path(project_root).resolve(strict=True)
    specs = root / 'specs'
    _contained(specs, root)
    try:
        candidates = [p for p in specs.iterdir() if p.name.casefold() == spec_id.casefold()]
        if len(candidates) != 1 or candidates[0].name != spec_id or not candidates[0].is_dir():
            raise ValueError('missing or ambiguous related spec: ' + spec_id)
        spec = candidates[0]
        _contained(spec, root)
        amendments = spec / 'amendments'
        if amendments.is_symlink() and not amendments.exists():
            raise ValueError('broken amendments link: ' + spec_id)
        if not amendments.exists():
            return ()
        _contained(amendments, root)
        if not amendments.is_dir():
            raise ValueError('not an amendments directory: ' + spec_id)
        # Ordinary notes in the amendments folder are not unit identities.
        # Never ignore symlinks: they could hide a unit or a path escape.
        entries = [p for p in amendments.iterdir() if p.is_symlink() or not p.is_file()]
        names = [p.name.casefold() for p in entries]
        if len(set(names)) != len(names) or any(not _ID.fullmatch(p.name) for p in entries):
            raise ValueError('ambiguous unit identity in spec: ' + spec_id)
        return tuple(f'{spec_id}:{p.name}' for p in sorted(entries, key=lambda p: p.name))
    except OSError as exc:
        raise ValueError('related unit scope is inaccessible') from exc


def discover_unit_scope(project_root: Path, spec_id: str,
                        unit_keys: Sequence[str] | None = None) -> tuple[UnitManifest, ...]:
    """Discover selected units and their parents; refuse unprovable peer ownership."""
    root = Path(project_root).resolve(strict=True)
    selected = list(list_spec_unit_keys(root, spec_id) if unit_keys is None else unit_keys)
    if len(set(selected)) != len(selected):
        raise ValueError('duplicate unit selection')
    cache, closure, pending = {}, {}, list(selected)
    while pending:
        key = pending.pop()
        parts = key.split(':') if isinstance(key, str) else []
        if len(parts) != 2 or not all(_ID.fullmatch(part) for part in parts):
            raise ValueError('invalid related unit identity')
        if key in closure:
            continue
        parent_spec, unit_id = parts
        if parent_spec not in cache:
            cache[parent_spec] = list_spec_unit_keys(root, parent_spec)
        if key not in cache[parent_spec]:
            raise ValueError('missing related unit: ' + key)
        manifest = root / 'specs' / parent_spec / 'amendments' / unit_id / 'manifest.json'
        item = load_unit(manifest, root)
        closure[key] = item
        pending.extend(item.parents)
    targets = [name for item in closure.values() for name in item.targets]
    for parent_spec, keys in cache.items():
        for key in keys:
            if key in closure:
                continue
            unit_id = key.split(':', 1)[1]
            manifest = root / 'specs' / parent_spec / 'amendments' / unit_id / 'manifest.json'
            try:
                peer = load_unit(manifest, root)
            except ValueError:
                peer = None
            if peer is not None:
                if any(item.spec_id == parent_spec and item.sequence == peer.sequence for item in closure.values()):
                    raise ValueError('duplicate sequence in spec: ' + parent_spec)
                continue  # A valid sibling is handled by the global close/owner gate.
            try:
                if manifest.is_symlink():
                    raise ValueError('alias')
                raw = manifest.read_bytes()
                if len(raw) > _MAX_BYTES:
                    raise ValueError('oversized')
                obj = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs)
                if not isinstance(obj, dict) or obj.get('spec_id') != parent_spec or obj.get('unit_id') != unit_id:
                    raise ValueError('identity')
                if type(obj.get('sequence')) is not int or obj['sequence'] <= 0:
                    raise ValueError('unknown sequence')
                if any(item.spec_id == parent_spec and item.sequence == obj['sequence'] for item in closure.values()):
                    raise ValueError('duplicate sequence')
                peer_targets = _paths(obj.get('targets'), root, 'peer targets')
                for peer in peer_targets:
                    for target in targets:
                        if peer.casefold() == target.casefold():
                            raise ValueError('overlapping target')
                        a, b = root / peer, root / target
                        if a.exists() and b.exists() and a.samefile(b):
                            raise ValueError('hardlink target alias')
            except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
                raise ValueError('peer ownership indeterminate for ' + key) from exc
    return resolve_units(list(closure.values()))


def _unit_impact_batch(root: Path, ordered: tuple[UnitManifest, ...], unit_keys: Sequence[str]) -> dict:
    """Hash each declared file once per phase and propagate errors only to consumers."""
    by_key = {item.key: item for item in ordered}
    if len(set(unit_keys)) != len(unit_keys) or any(key not in by_key for key in unit_keys):
        raise ValueError('duplicate or unknown unit')
    required, pending = set(), list(unit_keys)
    while pending:
        key = pending.pop()
        if key not in required:
            required.add(key)
            pending.extend(by_key[key].parents)

    def file_hash(name: str) -> tuple[str, str | None]:
        try:
            path = (root / name).resolve(strict=True)
            path.relative_to(root)
            if not path.is_file():
                raise ValueError('not a file')
            before = path.stat()
            data = path.read_bytes()
            after = path.stat()
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                    after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                raise ValueError('file changed during snapshot')
            if data != path.read_bytes():
                raise ValueError('file changed during snapshot')
            raw = hashlib.sha256(data).hexdigest()
            semantic = None
            if re.fullmatch(r'tasks(?:-[A-Za-z0-9_-]+)?\.md', path.name):
                try:
                    from . import aidd_rules as rules
                except ImportError:
                    import aidd_rules as rules
                projection = rules.approval_projection(data.decode('utf-8'))
                if projection is None:
                    raise ValueError('task file exceeds semantic projection limit')
                semantic = hashlib.sha256(('aidd-task-projection-v1\n' + projection).encode('utf-8')).hexdigest()
            return raw, semantic
        except (OSError, RuntimeError, ValueError, UnicodeError) as exc:
            raise ValueError('scope input unavailable or changed: ' + name) from exc

    snapshots, observed, errors, consumers = {}, {}, {}, {}
    for item in ordered:
        if item.key not in required:
            continue
        try:
            failed_parents = [parent for parent in item.parents if parent in errors]
            if failed_parents:
                parent = failed_parents[0]
                raise ValueError('parent scope unavailable: ' + parent + ': ' + errors[parent])
            if item.schema_version != 2:
                raise ValueError('legacy unit has no complete impact scope: ' + item.key)
            unit_prefix = f'specs/{item.spec_id}/amendments/{item.unit_id}/'
            if not any(name.startswith(unit_prefix) and re.fullmatch(
                    r'tasks(?:-[A-Za-z0-9_-]+)?\.md', name[len(unit_prefix):]) for name in item.paths):
                raise ValueError('unit lacks declared task file: ' + item.key)
            if not (item.targets or item.inputs or item.config or item.visual_refs):
                raise ValueError('unit has no declared execution scope: ' + item.key)
            categories = {'paths': item.paths, 'targets': item.targets,
                          'inputs': item.inputs, 'config': item.config,
                          'visual': tuple({name for ref in item.visual_refs for name in (ref.source, *ref.assets)})}
            files = {}
            for category, names in categories.items():
                files[category] = {}
                for name in sorted(names):
                    consumers.setdefault(name, set()).add(item.key)
                    if name not in observed:
                        observed[name] = file_hash(name)
                    raw, semantic = observed[name]
                    is_unit_tasks = (category == 'paths' and name.startswith(unit_prefix)
                                     and re.fullmatch(r'tasks(?:-[A-Za-z0-9_-]+)?\.md', name[len(unit_prefix):]))
                    files[category][name] = semantic if is_unit_tasks else raw
            refs = [{'screen_id': ref.screen_id, 'revision_id': ref.revision_id,
                     'source': ref.source, 'assets': sorted(ref.assets),
                     'states': sorted(ref.states), 'roles': sorted(ref.roles),
                     'viewports': sorted(ref.viewports)} for ref in sorted(
                         item.visual_refs, key=lambda ref: (ref.screen_id, ref.revision_id))]
            payload = {'format': 'aidd-unit-impact-v3', 'unit': item.key,
                       'version': item.version, 'sequence': item.sequence,
                       'files': files, 'parents': {parent: snapshots[parent]['digest']
                                                   for parent in sorted(item.parents)},
                       'visual_refs': refs}
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
            snapshots[item.key] = {**payload, 'digest': hashlib.sha256(encoded).hexdigest()}
        except (OSError, ValueError, KeyError) as exc:
            errors[item.key] = str(exc)

    for name, digest in observed.items():
        try:
            if file_hash(name) == digest:
                continue
        except ValueError:
            pass
        for key in consumers[name]:
            errors[key] = 'scope input changed during snapshot: ' + name
    for item in ordered:
        failed_parents = [parent for parent in item.parents if parent in errors]
        if item.key in required and failed_parents:
            parent = failed_parents[0]
            errors[item.key] = 'parent scope unavailable: ' + parent + ': ' + errors[parent]
    try:
        spec_names = {by_key[key].spec_id for key in unit_keys}
        unchanged = len(spec_names) == 1 and discover_unit_scope(root, next(iter(spec_names)), unit_keys) == ordered
    except (OSError, ValueError):
        unchanged = False
    if not unchanged:
        for key in required:
            errors[key] = 'unit manifests changed during snapshot'
    return {'snapshots': {key: snapshots[key] for key in unit_keys if key in snapshots and key not in errors},
            'errors': {key: errors[key] for key in unit_keys if key in errors}}


def unit_impact_snapshots(project_root: Path, unit_keys: Sequence[str]) -> dict:
    """Snapshot by spec, isolating malformed manifests in disjoint specs."""
    root = Path(project_root).resolve(strict=True)
    if (not isinstance(unit_keys, (tuple, list)) or len(set(unit_keys)) != len(unit_keys)
            or any(not isinstance(key, str) or len(key.split(':')) != 2
                   or not all(_ID.fullmatch(part) for part in key.split(':')) for key in unit_keys)):
        raise ValueError('duplicate or invalid unit')
    groups = {}
    for key in unit_keys:
        groups.setdefault(key.split(':', 1)[0], []).append(key)
    output = {'snapshots': {}, 'errors': {}}
    for spec_id, keys in groups.items():
        try:
            batch = _unit_impact_batch(root, discover_unit_scope(root, spec_id, keys), keys)
            output['snapshots'].update(batch['snapshots'])
            output['errors'].update(batch['errors'])
        except (OSError, ValueError) as exc:
            if len(keys) == 1:
                output['errors'][keys[0]] = str(exc)
                continue
            # Isolate the invalid branch; no unit receives another's failure.
            for key in keys:
                try:
                    batch = _unit_impact_batch(root, discover_unit_scope(root, spec_id, [key]), [key])
                    output['snapshots'].update(batch['snapshots'])
                    output['errors'].update(batch['errors'])
                except (OSError, ValueError) as one_error:
                    output['errors'][key] = str(one_error)
    return output


def unit_impact_snapshot(unit: UnitManifest, project_root: Path) -> dict:
    """Snapshot one declared v2 scope; preserve the original caller contract."""
    root = Path(project_root).resolve(strict=True)
    ordered = discover_unit_scope(root, unit.spec_id, [unit.key])
    by_key = {item.key: item for item in ordered}
    from dataclasses import asdict
    try:
        if unit.key not in by_key or asdict(by_key[unit.key]) != asdict(unit):
            raise ValueError('unit absent or differs from its manifest')
    except TypeError as exc:
        raise ValueError('invalid unit representation') from exc
    result = _unit_impact_batch(root, ordered, [unit.key])
    if unit.key in result['errors']:
        raise ValueError(result['errors'][unit.key])
    return result['snapshots'][unit.key]


def _migration_link(path: Path) -> bool:
    junction = getattr(path, 'is_junction', None)
    return path.is_symlink() or (callable(junction) and junction())


def _migration_file(root: Path, relative: str) -> Path:
    """Require an existing regular, non-linked in-project input."""
    path = root
    for part in relative.split('/'):
        path = path / part
        if _migration_link(path):
            raise ValueError('migration input contains a symbolic link: ' + relative)
    if not path.is_file() or path.resolve(strict=True).relative_to(root).as_posix() != relative:
        raise ValueError('migration input missing or ambiguous: ' + relative)
    return path


def _migration_parents(root, current, keys):
    by_key = {unit.key: unit for unit in current}
    values = {}
    for key in keys:
        pending, closure = [key], set()
        while pending:
            item = pending.pop()
            if item not in by_key:
                raise ValueError('missing parent: ' + item)
            if item not in closure:
                closure.add(item)
                pending.extend(by_key[item].parents)
        files = {}
        for parent_key in sorted(closure):
            parent = by_key[parent_key]
            names = set(parent.paths + parent.targets + parent.inputs + parent.config)
            names.add(f'specs/{parent.spec_id}/amendments/{parent.unit_id}/manifest.json')
            for ref in parent.visual_refs:
                names.add(ref.source)
                names.update(ref.assets)
            for name in sorted(names):
                files[name] = hashlib.sha256(_migration_file(root, name).read_bytes()).hexdigest()
        values[key] = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return values


def migration_plan(project_root, spec_id, manifest_path):
    """Propose a unit from explicit inputs; the plan asserts no historic audit or consent."""
    root = Path(project_root).resolve(strict=True)
    if not _ID.fullmatch(spec_id):
        raise ValueError('invalid spec identifier')
    spec = root / 'specs' / spec_id
    if not spec.is_dir() or _migration_link(spec) or _migration_link(root / 'specs'):
        raise ValueError('spec directory missing or linked')
    source = Path(manifest_path)
    if _migration_link(source) or not source.is_file():
        raise ValueError('manifest must be a regular file')
    raw = source.read_bytes()
    if len(raw) > _MAX_BYTES:
        raise ValueError('manifest exceeds 1 MiB')
    data = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs)
    if not isinstance(data, dict) or data.get('spec_id') != spec_id or not isinstance(data.get('unit_id'), str) or not _ID.fullmatch(data['unit_id']):
        raise ValueError('manifest identity does not match spec')
    # Reuse the production loader in a temporary layout; validate actual paths
    # separately below against the real checkout and its symlinks.
    with tempfile.TemporaryDirectory(prefix='aidd-unit-plan-') as temp:
        temporary = Path(temp)
        location = temporary / 'specs' / spec_id / 'amendments' / data['unit_id']
        location.mkdir(parents=True)
        (location / 'manifest.json').write_bytes(raw)
        candidate = load_unit(location / 'manifest.json', temporary)
    if candidate.schema_version != 2:
        raise ValueError('migration requires complete manifest schema version 2')
    amendments = spec / 'amendments'
    if _migration_link(amendments) or (amendments.exists() and not amendments.is_dir()):
        raise ValueError('amendments directory is linked or invalid')
    candidates = [p for p in amendments.iterdir() if p.name.casefold() == candidate.unit_id.casefold()] if amendments.exists() else []
    if (len(candidates) != 1 or candidates[0].name != candidate.unit_id or _migration_link(candidates[0])
            or not candidates[0].is_dir() or (candidates[0] / 'manifest.json').exists()
            or (candidates[0] / 'manifest.json').is_symlink()):
        raise ValueError('unit directory must already exist, be unambiguous and have no manifest')
    unit_prefix = f'specs/{spec_id}/amendments/{candidate.unit_id}/'
    if not any(name.startswith(unit_prefix) and re.fullmatch(r'tasks(?:-[A-Za-z0-9_-]+)?\.md',
                                                             name[len(unit_prefix):]) for name in candidate.paths):
        raise ValueError('unit must declare its own existing task file')
    if not (candidate.targets or candidate.inputs or candidate.config or candidate.visual_refs):
        raise ValueError('unit has no declared execution scope')
    _paths(list(candidate.paths), root, 'paths')
    _paths(list(candidate.targets), root, 'targets')
    _paths(list(candidate.inputs), root, 'inputs')
    _paths(list(candidate.config), root, 'config')
    names = set(candidate.paths + candidate.targets + candidate.inputs + candidate.config)
    for ref in candidate.visual_refs:
        names.add(ref.source)
        names.update(ref.assets)
    hashes = {name: hashlib.sha256(_migration_file(root, name).read_bytes()).hexdigest() for name in sorted(names)}
    current = []
    for other_spec in (root / 'specs').iterdir():
        if not other_spec.is_dir() or not (other_spec / 'amendments').exists():
            continue
        for key in list_spec_unit_keys(root, other_spec.name):
            if key == candidate.key:
                continue
            other_id = key.split(':', 1)[1]
            current.append(load_unit(other_spec / 'amendments' / other_id / 'manifest.json', root))
    resolve_units((*current, candidate))
    parents = _migration_parents(root, current, candidate.parents)
    payload = {'format': 'aidd-unit-migration-plan-v1', 'spec': spec_id, 'unit': candidate.unit_id,
               'manifest_sha256': hashlib.sha256(raw).hexdigest(), 'files': hashes, 'parents': parents,
               'destination': f'specs/{spec_id}/amendments/{candidate.unit_id}/manifest.json'}
    payload['digest'] = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                               separators=(',', ':')).encode('utf-8')).hexdigest()
    return payload


def migration_apply(project_root, spec_id, manifest_path, digest):
    """Create a unit exclusively after verifying the exact reviewed plan."""
    root = Path(project_root).resolve(strict=True)
    plan = migration_plan(root, spec_id, manifest_path)
    if digest != plan['digest']:
        raise ValueError('migration plan changed; inspect a new plan')
    raw = Path(manifest_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != plan['manifest_sha256']:
        raise ValueError('manifest changed while applying')
    spec = root / 'specs' / spec_id
    directory = spec / 'amendments' / plan['unit']
    receipt_dir = spec / 'unit-migration-receipts'
    if _migration_link(receipt_dir) or (receipt_dir.exists() and not receipt_dir.is_dir()):
        raise ValueError('migration receipt directory is linked or invalid')
    receipt = receipt_dir / (plan['unit'] + '.json')
    if receipt.exists() or receipt.is_symlink():
        raise ValueError('migration receipt already exists')
    receipt_dir.mkdir(exist_ok=True)
    created = directory / 'manifest.json'
    try:
        with created.open('xb') as stream:
            stream.write(raw)
        load_unit(created, root)
        discover_unit_scope(root, spec_id, [spec_id + ':' + plan['unit']])
        actual_hashes = {name: hashlib.sha256(_migration_file(root, name).read_bytes()).hexdigest()
                         for name in plan['files']}
        actual_parents = _migration_parents(root, discover_units(root), plan['parents'])
        if actual_hashes != plan['files'] or actual_parents != plan['parents']:
            raise ValueError('migration inputs changed during apply')
        record = {'format': 'aidd-unit-migration-v1', 'unit': spec_id + ':' + plan['unit'],
                  'manifest_sha256': plan['manifest_sha256'], 'plan_digest': digest, 'created_at': time.time()}
        with receipt.open('x', encoding='utf-8') as stream:
            try:
                json.dump(record, stream, ensure_ascii=False, sort_keys=True)
            except Exception:
                stream.close()
                receipt.unlink()
                raise
    except Exception:
        if created.is_file() and not created.is_symlink() and created.read_bytes() == raw:
            created.unlink()
        raise
    return record


def migration_revert(project_root, spec_id, unit_id, evidence):
    """Remove only the unchanged migration-created unit with no subsequent evidence."""
    root = Path(project_root).resolve(strict=True)
    if not _ID.fullmatch(spec_id) or not _ID.fullmatch(unit_id):
        raise ValueError('invalid unit identity')
    spec = root / 'specs' / spec_id
    directory = spec / 'amendments' / unit_id
    manifest = directory / 'manifest.json'
    receipt = spec / 'unit-migration-receipts' / (unit_id + '.json')
    for part in (root / 'specs', spec, spec / 'amendments', directory, manifest, receipt.parent, receipt):
        if _migration_link(part):
            raise ValueError('linked migration path cannot be reverted')
    record = json.loads(receipt.read_text(encoding='utf-8'))
    key = spec_id + ':' + unit_id
    if record.get('format') != 'aidd-unit-migration-v1' or record.get('unit') != key:
        raise ValueError('invalid migration receipt')
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != record.get('manifest_sha256'):
        raise ValueError('unit manifest changed since migration')
    if any(key in unit.parents for unit in discover_units(root)):
        raise ValueError('other units depend on this unit')
    for kind in ('unit_approved', 'unit_audit', 'task_verify_run', 'verify_run'):
        for event in evidence.events(root, kind=kind):
            detail = event.get('detail') or {}
            refers_to_unit = detail.get('unit') == key or (detail.get('spec') == spec_id and detail.get('unit_id') == unit_id)
            newer_verification = (kind in ('task_verify_run', 'verify_run') and detail.get('spec') == spec_id
                                  and float(event.get('ts') or 0) >= float(record['created_at']) - 0.01)
            if refers_to_unit or newer_verification:
                raise ValueError('subsequent evidence exists; migration cannot be reverted safely')
    manifest.unlink()
    receipt.unlink()
    return {'unit': key, 'reverted': True, 'historical_evidence_unchanged': True}


def main(argv=None):
    import argparse
    try:
        from . import aidd_evidence as evidence
    except ImportError:
        import aidd_evidence as evidence
    parser = argparse.ArgumentParser(description='Plan, apply or safely revert a unit migration')
    sub = parser.add_subparsers(dest='action', required=True)
    for name in ('plan', 'apply'):
        command = sub.add_parser(name)
        command.add_argument('spec')
        command.add_argument('--manifest', required=True)
        if name == 'apply':
            command.add_argument('--digest', required=True)
    command = sub.add_parser('revert')
    command.add_argument('spec')
    command.add_argument('unit')
    parser.add_argument('--root', default='.')
    args = parser.parse_args(argv)
    try:
        root = evidence.find_root(Path(args.root).resolve())
        if args.action == 'plan':
            result = migration_plan(root, args.spec, args.manifest)
        elif args.action == 'apply':
            result = migration_apply(root, args.spec, args.manifest, args.digest)
        else:
            result = migration_revert(root, args.spec, args.unit, evidence)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        print('unit migration unavailable: ' + str(exc), file=__import__('sys').stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())


def unit_for_target(units: Sequence[UnitManifest], project_root: Path,
                    target: Path) -> UnitManifest | None:
    """Find the unique most-derived owner of a canonical target.

    Includes drafts: an unapproved descendant must never fall back to its
    approved ancestor. None means the path has no declared unit owner.
    """
    root = Path(project_root).resolve(strict=True)
    try:
        resolved = _contained(Path(target) if Path(target).is_absolute()
                              else root / target, root)
        name = resolved.relative_to(root).as_posix()
    except (OSError, ValueError) as exc:
        raise ValueError('invalid unit target') from exc
    ordered = resolve_units(units)
    by_key = {unit.key: unit for unit in ordered}
    # Treat case aliases conservatively even on volumes whose sensitivity is
    # unknown, so a mixed-case spelling cannot silently fall back to legacy.
    owners = [unit for unit in ordered if any(
        name.casefold() == declared.casefold() for declared in unit.targets)]
    try:
        try:
            target_stat = resolved.stat()
        except FileNotFoundError:
            target_stat = None  # a new target has no physical identity yet
        if target_stat is not None and target_stat.st_nlink > 1:
            for candidate in ordered:
                for declared in candidate.targets:
                    path = root / declared
                    try:
                        same = resolved.samefile(path)
                    except FileNotFoundError:
                        same = False
                    if same and candidate not in owners:
                        owners.append(candidate)
            if not owners:
                raise ValueError('hardlinked target has unknown ownership: ' + name)
    except OSError as exc:
        raise ValueError('cannot determine target identity') from exc
    if not owners:
        return None
    ancestors: dict[str, set[str]] = {}
    for unit in ordered:
        inherited = set(unit.parents)
        for parent in unit.parents:
            inherited.update(ancestors[parent])
        ancestors[unit.key] = inherited
    maximal = [unit for unit in owners if not any(
        unit.key in ancestors[other.key] for other in owners if other.key != unit.key)]
    if len(maximal) != 1:
        raise ValueError('incomparable unit owners for target: ' + name)
    return by_key[maximal[0].key]
