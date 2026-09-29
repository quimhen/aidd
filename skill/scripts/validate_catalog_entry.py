#!/usr/bin/env python3
"""
aidd catalog validator — the automated half of the marketplace's acceptance
gate. Runs in CI (.github/workflows/catalog-validate.yml) on every PR that
touches catalog/, and is available to run locally before opening one.

This checks structure and safety-relevant shape mechanically (schema
conformance, no path traversal, unique ids, files that actually exist) —
exactly the class of check that's cheap and reliable to automate. It does
NOT decide whether a submission's code is safe to run: a package can pass
every check here and still contain something a human reviewer would reject
(that's inherent to reviewing arbitrary third-party code, not a gap in this
script). What it CAN do cheaply is flag content worth a reviewer's attention
— network calls, subprocess/exec — so a maintainer's manual review starts
from a shortlist instead of reading every file blind. This mirrors spec-kit's
own actual model: automated schema/security-requirement checks in CI
(.github/scripts/check_security_requirements.py) gate the PR, but a human
still merges every catalog addition — there is no fully automatic accept
path here either, by design.

Usage:
    python validate_catalog_entry.py <package-id>    # one package
    python validate_catalog_entry.py --all           # every package under catalog/packages/
    python validate_catalog_entry.py --changed <base-ref>  # packages changed vs. a git ref (CI mode)

Exit code 0 = no schema/structural errors (security-review flags don't fail
the build — they're printed for the human reviewer). Exit code 1 = at least
one structural error found.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

CATALOG_DIR = Path(__file__).resolve().parent.parent.parent / "catalog"

REQUIRED_FIELDS = ("id", "name", "description", "version", "author", "license", "kind", "files")
VALID_KINDS = {"provider", "adapter", "template", "hook"}
ID_RE = re.compile(r'^[a-z0-9][a-z0-9-]{1,63}$')
SEMVER_RE = re.compile(r'^\d+\.\d+\.\d+$')

# Substrings worth a human reviewer's attention — not a security scanner,
# just a shortlist. Deliberately broad (over-flagging costs a reviewer one
# extra glance; under-flagging costs a missed review).
REVIEW_FLAG_PATTERNS = (
    'subprocess', 'os.system', 'eval(', 'exec(',
    'urllib', 'requests.', 'fetch(', 'http://', 'https://',
    '__import__',
)


def load_package(package_id: str) -> tuple[dict | None, list[str]]:
    """Returns (manifest_dict_or_None, errors)."""
    errors = []
    package_dir = CATALOG_DIR / "packages" / package_id
    manifest_path = package_dir / "package.json"

    if not package_dir.is_dir():
        return None, [f"{package_id}: no such folder under catalog/packages/"]
    if not manifest_path.exists():
        return None, [f"{package_id}: missing package.json"]

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return None, [f"{package_id}: package.json is not valid JSON ({e})"]

    return manifest, errors


def validate_manifest(package_id: str, manifest: dict) -> list[str]:
    errors = []

    for field in REQUIRED_FIELDS:
        if field not in manifest:
            errors.append(f"{package_id}: missing required field {field!r}")
    if errors:
        return errors  # further checks assume these fields exist

    if manifest["id"] != package_id:
        errors.append(f"{package_id}: package.json's id {manifest['id']!r} != folder name {package_id!r}")
    if not ID_RE.match(manifest["id"]):
        errors.append(f"{package_id}: id {manifest['id']!r} doesn't match {ID_RE.pattern}")
    if not SEMVER_RE.match(manifest["version"]):
        errors.append(f"{package_id}: version {manifest['version']!r} isn't semver (X.Y.Z)")
    if manifest["kind"] not in VALID_KINDS:
        errors.append(f"{package_id}: kind {manifest['kind']!r} not in {sorted(VALID_KINDS)}")
    if not isinstance(manifest["files"], dict) or not manifest["files"]:
        errors.append(f"{package_id}: files must be a non-empty object")
        return errors

    files_root = (CATALOG_DIR / "packages" / package_id / "files").resolve()
    for dest, src_rel in manifest["files"].items():
        if not isinstance(src_rel, str) or not src_rel:
            errors.append(f"{package_id}: files[{dest!r}] must be a non-empty string")
            continue
        src = (files_root / src_rel).resolve()
        try:
            src.relative_to(files_root)
        except ValueError:
            errors.append(f"{package_id}: files[{dest!r}] = {src_rel!r} escapes its own files/ folder")
            continue
        if not src.is_file():
            errors.append(f"{package_id}: files[{dest!r}] = {src_rel!r} does not exist")

    return errors


def find_review_flags(package_id: str) -> list[str]:
    """Non-fatal — printed for a human reviewer, never fails validation."""
    flags = []
    files_root = CATALOG_DIR / "packages" / package_id / "files"
    if not files_root.is_dir():
        return flags
    for path in sorted(files_root.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in REVIEW_FLAG_PATTERNS:
            if pattern in text:
                flags.append(f"{package_id}: {path.relative_to(files_root)} contains {pattern!r} — review before merging")
    return flags


def check_duplicate_ids() -> list[str]:
    """A package id must be unique across catalog.json + catalog.community.json —
    a community submission can't shadow a first-party package."""
    errors = []
    seen: dict[str, str] = {}
    for filename in ("catalog.json", "catalog.community.json"):
        path = CATALOG_DIR / filename
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data.get("packages", []):
            pkg_id = entry.get("id")
            if not pkg_id:
                errors.append(f"{filename}: an entry is missing 'id'")
                continue
            if pkg_id in seen:
                errors.append(f"duplicate package id {pkg_id!r} in both {seen[pkg_id]} and {filename}")
            seen[pkg_id] = filename
    return errors


def all_package_ids() -> list[str]:
    packages_dir = CATALOG_DIR / "packages"
    if not packages_dir.is_dir():
        return []
    return sorted(p.name for p in packages_dir.iterdir() if p.is_dir())


def changed_package_ids(base_ref: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", base_ref, "--", "catalog/packages"],
        capture_output=True, text=True, cwd=str(CATALOG_DIR.parent), timeout=15,
    )
    ids = set()
    for line in result.stdout.splitlines():
        parts = Path(line).parts
        if len(parts) >= 3 and parts[0] == "catalog" and parts[1] == "packages":
            ids.add(parts[2])
    return sorted(ids)


def validate(package_ids: list[str]) -> tuple[list[str], list[str]]:
    """Returns (errors, review_flags) across every given package id."""
    errors = list(check_duplicate_ids())
    flags = []
    for package_id in package_ids:
        manifest, load_errors = load_package(package_id)
        errors.extend(load_errors)
        if manifest is not None:
            errors.extend(validate_manifest(package_id, manifest))
        flags.extend(find_review_flags(package_id))
    return errors, flags


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if args else 2)

    if args[0] == "--all":
        package_ids = all_package_ids()
    elif args[0] == "--changed":
        if len(args) < 2:
            print("Usage: validate_catalog_entry.py --changed <base-ref>", file=sys.stderr)
            sys.exit(2)
        package_ids = changed_package_ids(args[1])
    else:
        package_ids = [args[0]]

    if not package_ids:
        print("No packages to validate.")
        sys.exit(0)

    errors, flags = validate(package_ids)

    print(f"aidd catalog validation — {len(package_ids)} package(s): {', '.join(package_ids)}")
    print("=" * 60)

    if flags:
        print(f"\n{len(flags)} item(s) flagged for manual security review (non-fatal):")
        for f in flags:
            print(f"  ! {f}")

    if errors:
        print(f"\n{len(errors)} structural error(s):")
        for e in errors:
            print(f"  x {e}")
        sys.exit(1)

    print("\nNo structural errors.")
    sys.exit(0)


if __name__ == "__main__":
    main()
