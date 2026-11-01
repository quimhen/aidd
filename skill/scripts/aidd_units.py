"""Read-only, fail-closed discovery of versioned amendment units.

Unit manifests describe proposed work; they are not approval evidence.
"""
from __future__ import annotations

import heapq
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Sequence

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_KEYS = {"schema_version", "spec_id", "unit_id", "sequence", "parents", "paths", "targets"}
_MAX_BYTES = 1024 * 1024


@dataclass(frozen=True)
class UnitManifest:
    schema_version: int
    spec_id: str
    unit_id: str
    sequence: int
    parents: tuple[str, ...]
    paths: tuple[str, ...]
    targets: tuple[str, ...]

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
        if not isinstance(data, dict) or set(data) != _KEYS:
            raise ValueError("invalid manifest keys")
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ValueError("unsupported schema version")
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
        return UnitManifest(1, spec, unit, sequence, tuple(parents),
                            _paths(data["paths"], root, "paths"),
                            _paths(data["targets"], root, "targets"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load unit manifest: {path}") from exc


def discover_units(project_root: Path) -> tuple[UnitManifest, ...]:
    """Discover drafts too: an incomplete amendment must not disappear silently."""
    try:
        root = project_root.resolve(strict=True)
        specs = root / "specs"
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
    sequences: set[tuple[str, int]] = set()
    for unit in units:
        if unit.key in by_key or (unit.spec_id, unit.sequence) in sequences:
            raise ValueError(f"duplicate unit ID or sequence: {unit.key}")
        by_key[unit.key] = unit
        sequences.add((unit.spec_id, unit.sequence))
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
