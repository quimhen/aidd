#!/usr/bin/env python3
"""
aidd marketplace — install/list/search/remove third-party packages from
catalog/, AIDD's optimized take on spec-kit's install-manifest mechanism.

spec-kit's IntegrationManifest hashes every file it writes so `upgrade`/
`uninstall` never clobbers something the user hand-edited afterward, across
an install/upgrade/teardown lifecycle spanning extensions, presets, bundles,
and workflows. This module keeps exactly that one load-bearing idea —
content hashing so a remove only touches files that still match what was
installed — and drops the rest: no upgrade command (re-install after
bumping the version in catalog.json), no separate manifest class hierarchy
(one JSON file, one dict), no presets/bundles/workflows layer.

Two catalogs merge at load time: catalog.json (first-party, this repo's own
maintainers) and catalog.community.json (third-party submissions, reviewed
via catalog/CONTRIBUTING.md's process). A package id must be unique across
both — see validate_catalog_entry.py for the check that enforces this
before a submission is ever merged.

Install manifest: <project-root>/.aidd/marketplace-manifest.json
    {"<package-id>": {"version": "1.0.0",
                       "files": {"<dest-relative-path>": "<sha256>"}}}

Kinds actually installable in v1: "adapter" and "template" — pure file
copy into the project, no code wiring needed elsewhere. "provider" and
"hook" packages validate and can be reviewed/merged, but installing one
prints a clear not-yet-supported message (see catalog/schema.json's own
"kind" description) rather than silently doing nothing — AIDD's provider
dispatch (tasks_to_issues.py) and hook installer (install_hooks.py) are
still fixed lists, not dynamic loaders.

Usage:
    python marketplace.py list
    python marketplace.py search <query>
    python marketplace.py install <package-id> [project-root] [--force]
    python marketplace.py remove <package-id> [project-root] [--force]
"""
import hashlib
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CATALOG_DIR = Path(__file__).resolve().parent.parent.parent / "catalog"
NOT_YET_INSTALLABLE_KINDS = {"provider", "hook"}


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {"packages": []}
    return json.loads(path.read_text(encoding="utf-8"))


def load_catalog(catalog_dir: Path = CATALOG_DIR) -> list[dict]:
    """Merge catalog.json (first-party) and catalog.community.json (third-party)
    into one flat list of {"id": ...} entries, each resolved against its own
    catalog/packages/<id>/package.json for the full metadata."""
    entries = []
    seen_ids = set()
    for filename in ("catalog.json", "catalog.community.json"):
        data = _load_json(catalog_dir / filename)
        for entry in data.get("packages", []):
            pkg_id = entry.get("id")
            if not pkg_id or pkg_id in seen_ids:
                continue
            seen_ids.add(pkg_id)
            manifest = load_package_manifest(pkg_id, catalog_dir)
            if manifest is not None:
                entries.append(manifest)
    return entries


def load_package_manifest(package_id: str, catalog_dir: Path = CATALOG_DIR) -> dict | None:
    manifest_path = catalog_dir / "packages" / package_id / "package.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def search_catalog(query: str, catalog_dir: Path = CATALOG_DIR) -> list[dict]:
    query_lower = query.lower()
    return [
        pkg for pkg in load_catalog(catalog_dir)
        if query_lower in pkg.get("id", "").lower()
        or query_lower in pkg.get("name", "").lower()
        or query_lower in pkg.get("description", "").lower()
    ]


# ---------------------------------------------------------------------------
# Install manifest — per-project record of what's installed, content-hashed
# ---------------------------------------------------------------------------


def _manifest_path(project_root: Path) -> Path:
    return project_root / ".aidd" / "marketplace-manifest.json"


def _read_project_manifest(project_root: Path) -> dict:
    path = _manifest_path(project_root)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_project_manifest(project_root: Path, manifest: dict) -> None:
    path = _manifest_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def find_file_conflicts(pkg: dict, project_root: Path, installed: dict) -> list[str]:
    """Return destination paths this package would write that are already
    tracked by a DIFFERENT installed package — the one real "two packages
    fight over the same file" case spec-kit's conflict.py exists to catch."""
    conflicts = []
    for dest in pkg.get("files", {}):
        for other_id, other in installed.items():
            if other_id == pkg["id"]:
                continue
            if dest in other.get("files", {}):
                conflicts.append(f"{dest} (already installed by {other_id!r})")
    return conflicts


def install_package(package_id: str, project_root: Path, force: bool = False,
                     catalog_dir: Path = CATALOG_DIR) -> list[Path]:
    pkg = load_package_manifest(package_id, catalog_dir)
    if pkg is None:
        raise ValueError(f"Unknown package {package_id!r} — run 'marketplace.py list' to see available packages.")

    if pkg["kind"] in NOT_YET_INSTALLABLE_KINDS:
        raise NotImplementedError(
            f"Package {package_id!r} is kind={pkg['kind']!r}, which isn't installable yet — "
            "AIDD's provider dispatch and hook installer are still fixed lists, not dynamic "
            "loaders. This package can still be reviewed/merged; see catalog/schema.json."
        )

    installed = _read_project_manifest(project_root)
    conflicts = find_file_conflicts(pkg, project_root, installed)
    if conflicts and not force:
        raise ValueError(
            f"Refusing to install {package_id!r} — file conflict(s) with another "
            f"installed package: {'; '.join(conflicts)}. Pass force=True to override."
        )

    package_root = catalog_dir / "packages" / package_id
    files_root = package_root / "files"
    written: list[Path] = []
    file_hashes: dict[str, str] = {}

    for dest_rel, src_rel in pkg["files"].items():
        src = (files_root / src_rel).resolve()
        try:
            src.relative_to(files_root.resolve())
        except ValueError:
            raise ValueError(
                f"Package {package_id!r}'s files entry {src_rel!r} escapes its own "
                "files/ folder — refusing to install."
            )
        if not src.is_file():
            raise ValueError(f"Package {package_id!r} declares {src_rel!r} but that file doesn't exist.")

        dest = project_root / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = src.read_bytes()
        dest.write_bytes(data)
        file_hashes[dest_rel] = _sha256(data)
        written.append(dest)

    installed[package_id] = {"version": pkg["version"], "files": file_hashes}
    _write_project_manifest(project_root, installed)
    return written


def remove_package(package_id: str, project_root: Path, force: bool = False) -> tuple[list[Path], list[Path]]:
    """Returns (removed, skipped). A file whose current hash no longer
    matches what was recorded (hand-edited since install) is skipped unless
    force=True — same "never discard a local edit silently" rule
    generate_adapters.py's --force flag already follows."""
    installed = _read_project_manifest(project_root)
    entry = installed.get(package_id)
    if entry is None:
        raise ValueError(f"{package_id!r} is not installed in {project_root}.")

    removed: list[Path] = []
    skipped: list[Path] = []
    for dest_rel, recorded_hash in entry.get("files", {}).items():
        dest = project_root / dest_rel
        if not dest.exists():
            continue
        current_hash = _sha256(dest.read_bytes())
        if current_hash != recorded_hash and not force:
            skipped.append(dest)
            continue
        dest.unlink()
        removed.append(dest)

    if not skipped:
        installed.pop(package_id, None)
        _write_project_manifest(project_root, installed)
    return removed, skipped


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if args else 2)

    command = args[0]

    if command == "list":
        for pkg in load_catalog():
            print(f"{pkg['id']:20s} v{pkg['version']:8s} [{pkg['kind']:8s}] {pkg['description']}")
        sys.exit(0)

    if command == "search":
        if len(args) < 2:
            print("Usage: marketplace.py search <query>", file=sys.stderr)
            sys.exit(2)
        for pkg in search_catalog(args[1]):
            print(f"{pkg['id']:20s} v{pkg['version']:8s} [{pkg['kind']:8s}] {pkg['description']}")
        sys.exit(0)

    if command in ("install", "remove"):
        if len(args) < 2:
            print(f"Usage: marketplace.py {command} <package-id> [project-root] [--force]", file=sys.stderr)
            sys.exit(2)
        force = "--force" in args
        positional = [a for a in args[1:] if a != "--force"]
        package_id = positional[0]
        project_root = Path(positional[1]) if len(positional) > 1 else Path.cwd()

        try:
            if command == "install":
                written = install_package(package_id, project_root, force=force)
                for f in written:
                    print(f"wrote {f}")
                print(f"\nInstalled {package_id!r} ({len(written)} file(s)).")
            else:
                removed, skipped = remove_package(package_id, project_root, force=force)
                for f in removed:
                    print(f"removed {f}")
                for f in skipped:
                    print(f"skip (modified since install): {f}", file=sys.stderr)
                print(f"\nRemoved {package_id!r}: {len(removed)} file(s), {len(skipped)} skipped.")
        except (ValueError, NotImplementedError) as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    print(f"Unknown command {command!r}. See --help.", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
