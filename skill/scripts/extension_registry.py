#!/usr/bin/env python3
"""
aidd extension registry — real auto-discovery for provider/adapter/hook
extensions.

This closes the gap catalog/schema.json's own "kind" field description
already flagged: a `provider`/`hook` package could be validated and merged
into the catalog, but installing one printed a "not-yet-supported" message
because "AIDD's provider dispatch (tasks_to_issues.py) and hook installer
(install_hooks.py) are still fixed lists, not dynamic loaders." This module
is that dynamic loader.

Two discovery roots, later wins on a (kind, id) collision:
  1. skill/extensions/**/manifest.json   — bundled with AIDD itself, always
     on, zero install step. Today's skill/scripts/providers/*.py and
     adapter_targets.py's TARGETS entries live here now, unchanged behavior,
     just data-driven instead of a hardcoded dict/import.
  2. <project_root>/.aidd/extensions/**/manifest.json — project-local, or
     dropped there by `aidd marketplace install` for a provider/hook/adapter
     kind catalog package (see marketplace.py). A project can override a
     first-party extension by shipping one with the same (kind, id) here.

Manifest shape (skill/extensions/<name>/manifest.json, or
<project>/.aidd/extensions/<id>/manifest.json) — a different, simpler
document than catalog/packages/<id>/package.json. That one is the
*publishing* manifest marketplace.py installs FROM (it still has the
"files" mapping used to copy this manifest.json + the extension's code into
a project). This one is the *runtime* descriptor this registry reads once
an extension is bundled or installed:

    {
      "id": "github",
      "name": "GitHub",
      "description": "GitHub issue tracker provider (gh CLI).",
      "version": "1.0.0",
      "kind": "provider" | "adapter" | "hook",
      "enabled": true,                          // optional, default true

      // kind == "provider":
      "entry": "provider.py",                    // python file in this folder
      "contract": "tracker.v2",                  // informational only today

      // kind == "adapter" (one multi-agent command-file target):
      "adapter": {
        "dir": ".gemini/commands", "format": "toml", "filename": "aidd-{stem}.toml",
        "arg_placeholder": "{{args}}", "invoke_phrase": "...",
        "frontmatter_extra": {}
      },

      // kind == "hook" (a Claude Code enforcement/advisory hook):
      "events": [{"event": "PreToolUse", "matcher": "Write|Edit", "script": "hook.py"}]
    }

No jsonschema dependency — this repo ships zero third-party dependencies
(pyproject.toml: dependencies = []). Validation below is hand-rolled, same
style as check_charter.py/validate_catalog_entry.py.
"""
import importlib.util
import json
import sys
from pathlib import Path

SKILL_EXTENSIONS_DIR = Path(__file__).resolve().parent.parent / "extensions"

REQUIRED_FIELDS = ("id", "name", "description", "version", "kind")
VALID_KINDS = {"provider", "adapter", "hook"}


class Extension:
    """One discovered, validated manifest.json plus the folder it lives in."""

    def __init__(self, manifest: dict, folder: Path, source: str):
        self.manifest = manifest
        self.folder = folder
        self.source = source  # "first-party" | "project"

    @property
    def id(self) -> str:
        return self.manifest["id"]

    @property
    def kind(self) -> str:
        return self.manifest["kind"]

    @property
    def enabled(self) -> bool:
        return bool(self.manifest.get("enabled", True))

    def __repr__(self):
        return f"Extension(id={self.id!r}, kind={self.kind!r}, source={self.source!r})"


def validate_manifest(manifest: dict) -> list[str]:
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in manifest:
            errors.append(f"missing required field {field!r}")
    if errors:
        return errors  # further checks assume these fields exist

    if manifest["kind"] not in VALID_KINDS:
        errors.append(f"kind {manifest['kind']!r} not in {sorted(VALID_KINDS)}")
        return errors

    if manifest["kind"] == "provider" and not manifest.get("entry"):
        errors.append("kind=provider requires a non-empty 'entry'")
    if manifest["kind"] == "adapter" and not isinstance(manifest.get("adapter"), dict):
        errors.append("kind=adapter requires an 'adapter' object")
    if manifest["kind"] == "hook" and not manifest.get("events"):
        errors.append("kind=hook requires a non-empty 'events' list")
    return errors


def _load_manifest(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"warning: {path}: invalid manifest.json ({e}) — skipped", file=sys.stderr)
        return None
    errors = validate_manifest(data)
    if errors:
        print(f"warning: {path}: {'; '.join(errors)} — skipped", file=sys.stderr)
        return None
    return data


def _scan(root: Path, source: str) -> list[Extension]:
    if not root.is_dir():
        return []
    found = []
    for manifest_path in sorted(root.rglob("manifest.json")):
        if "__pycache__" in manifest_path.parts:
            continue
        manifest = _load_manifest(manifest_path)
        if manifest is None:
            continue
        found.append(Extension(manifest, manifest_path.parent, source))
    return found


def discover(project_root: Path | str | None = None, include_disabled: bool = False) -> list[Extension]:
    """First-party extensions, then project-local ones — a project-local
    entry with the same (kind, id) shadows the first-party one."""
    by_key: dict[tuple, Extension] = {}
    for ext in _scan(SKILL_EXTENSIONS_DIR, "first-party"):
        by_key[(ext.kind, ext.id)] = ext
    if project_root is not None:
        for ext in _scan(Path(project_root) / ".aidd" / "extensions", "project"):
            by_key[(ext.kind, ext.id)] = ext
    extensions = list(by_key.values())
    if not include_disabled:
        extensions = [ext for ext in extensions if ext.enabled]
    return extensions


def get_providers(project_root: Path | str | None = None) -> dict[str, object]:
    """id -> imported provider module, for every enabled kind=provider extension."""
    providers = {}
    for ext in discover(project_root):
        if ext.kind != "provider":
            continue
        entry = ext.folder / ext.manifest["entry"]
        if not entry.is_file():
            print(f"warning: provider {ext.id!r} entry {entry} not found — skipped", file=sys.stderr)
            continue
        spec = importlib.util.spec_from_file_location(f"aidd_ext_provider_{ext.id}", entry)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        providers[ext.id] = module
    return providers


def get_adapter_targets(project_root: Path | str | None = None) -> dict[str, dict]:
    """id -> adapter config dict, shaped exactly like the old adapter_targets.TARGETS
    entries (dir/format/filename/arg_placeholder/invoke_phrase/frontmatter_extra),
    plus 'name' filled in from the manifest."""
    targets = {}
    for ext in discover(project_root):
        if ext.kind != "adapter":
            continue
        cfg = dict(ext.manifest["adapter"])
        cfg.setdefault("name", ext.manifest.get("name", ext.id))
        targets[ext.id] = cfg
    return targets


def get_hooks(event: str, project_root: Path | str | None = None) -> list[dict]:
    """Every {"matcher", "script", "extension_id"} entry any enabled
    kind=hook extension registers for `event` — consumed by
    hooks/extension_dispatch.py."""
    hooks = []
    for ext in discover(project_root):
        if ext.kind != "hook":
            continue
        for e in ext.manifest.get("events", []):
            if e.get("event") != event:
                continue
            hooks.append({
                "matcher": e.get("matcher"),
                "script": str(ext.folder / e["script"]),
                "extension_id": ext.id,
            })
    return hooks


def set_enabled(ext_id: str, enabled: bool, project_root: Path | str | None = None) -> bool:
    """Flip 'enabled' in place for one extension's manifest.json, searched
    project-local first (most specific), then first-party. Returns True iff
    a manifest with this id was found and updated."""
    roots = []
    if project_root is not None:
        roots.append(Path(project_root) / ".aidd" / "extensions")
    roots.append(SKILL_EXTENSIONS_DIR)

    for root in roots:
        if not root.is_dir():
            continue
        for manifest_path in sorted(root.rglob("manifest.json")):
            if "__pycache__" in manifest_path.parts:
                continue
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if data.get("id") != ext_id:
                continue
            data["enabled"] = enabled
            manifest_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return True
    return False


def _format(ext: Extension) -> str:
    status = "enabled" if ext.enabled else "disabled"
    return (f"{ext.id:15s} [{ext.kind:9s}] ({ext.source:11s}, {status:8s}) "
            f"{ext.manifest.get('description', '')}")


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if args else 2)

    command = args[0]
    rest = args[1:]
    project_root = Path.cwd()

    if command == "list":
        extensions = sorted(discover(project_root, include_disabled=True), key=lambda e: (e.kind, e.id))
        if not extensions:
            print("No extensions discovered.")
            sys.exit(0)
        for ext in extensions:
            print(_format(ext))
        sys.exit(0)

    if command == "info":
        if not rest:
            print("Usage: extension_registry.py info <id>", file=sys.stderr)
            sys.exit(2)
        matches = [e for e in discover(project_root, include_disabled=True) if e.id == rest[0]]
        if not matches:
            print(f"No extension named {rest[0]!r}.", file=sys.stderr)
            sys.exit(1)
        for ext in matches:
            print(_format(ext))
            print(json.dumps(ext.manifest, indent=2, ensure_ascii=False))
        sys.exit(0)

    if command in ("enable", "disable"):
        if not rest:
            print(f"Usage: extension_registry.py {command} <id>", file=sys.stderr)
            sys.exit(2)
        ok = set_enabled(rest[0], enabled=(command == "enable"), project_root=project_root)
        if not ok:
            print(f"No extension named {rest[0]!r}.", file=sys.stderr)
            sys.exit(1)
        print(f"{rest[0]}: {command}d.")
        sys.exit(0)

    print(f"Unknown command {command!r}. See --help.", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
