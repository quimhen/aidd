#!/usr/bin/env python3
"""Collect, compare and serialize required unittest identities without running them."""
import argparse
import hashlib
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEST = ROOT / 'specs/008-aidd-compact-review-direct-save/verification-required-ids.txt'
MODULES = frozenset(('test_aidd_review', 'test_review_template', 'test_aidd_status',
                     'test_cli_rules', 'test_typed_confirmations', 'test_rule_gate',
                     'test_aidd_rules', 'test_dot_aidd_mirror'))
ID = re.compile(r'^test_[A-Za-z0-9_]+(?:\.[A-Za-z_][A-Za-z0-9_]*){2,}$')


def normalize(ident):
    return ident.removeprefix('tests.')


def suite_ids(suite):
    ids = []
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            ids.extend(suite_ids(test))
        else:
            ids.append(test.id())
    return ids


def build_manifest(discovered_ids, selected_ids):
    found = [normalize(i) for i in discovered_ids]
    selected = [normalize(i) for i in selected_ids]
    for items in (found, selected):
        if not items or len(items) != len(set(items)) or any(not ID.fullmatch(i) for i in items):
            raise ValueError('empty, duplicate, malformed or failed collection')
    if set(found) != set(selected):
        raise ValueError('selected and discovered identities differ')
    return ('\n'.join(sorted(found)) + '\n').encode('utf-8')


def check_bytes(candidate, existing):
    return candidate == existing


def collect():
    loader = unittest.TestLoader()
    discovered = suite_ids(loader.discover(str(ROOT / 'tests')))
    if loader.errors:
        raise ValueError('discovery failed: ' + '; '.join(loader.errors))
    selected = [normalize(i) for i in discovered if normalize(i).split('.', 1)[0] in MODULES]
    # Independently load the original module rows and require exact equivalence.
    loader = unittest.TestLoader()
    original = suite_ids(loader.loadTestsFromNames(['tests.' + m for m in sorted(MODULES)]))
    if loader.errors:
        raise ValueError('module collection failed: ' + '; '.join(loader.errors))
    return build_manifest(selected, original)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ('dry-run', 'check', 'write'):
        modes.add_argument('--' + mode, action='store_true')
    args = parser.parse_args(argv)
    try:
        data = collect()
        digest = hashlib.sha256(data).hexdigest()
        if args.check and not check_bytes(data, DEST.read_bytes()):
            raise ValueError('manifest differs from current collection')
        if args.write:
            DEST.write_bytes(data)
        print(f'{len(data.splitlines())} IDs; SHA-256 {digest}')
        return 0
    except (OSError, ValueError) as exc:
        print(f'coverage manifest: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
