"""Fixed mapping, dry-run by default, apply then byte-check; no protected project writes."""
import argparse
import hashlib
import json
from pathlib import Path

NAMES = ('aidd_check_scope.py', 'aidd_readiness.py', 'check_spec.py', 'aidd_shared_components.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    rows = []
    for name in NAMES:
        source = root / 'skill' / 'scripts' / name
        target = root / 'adapters' / 'dot-aidd' / 'scripts' / name
        source.resolve(strict=True).relative_to(root)
        target.resolve(strict=False).relative_to(root / 'adapters' / 'dot-aidd' / 'scripts')
        payload = source.read_bytes()
        changed = not target.exists() or target.read_bytes() != payload
        if args.apply and changed:
            target.write_bytes(payload)
        if args.apply and target.read_bytes() != payload:
            raise RuntimeError('mirror post-check failed: ' + name)
        rows.append({'source': source.relative_to(root).as_posix(),
                     'target': target.relative_to(root).as_posix(), 'changed': changed,
                     'sha256': hashlib.sha256(payload).hexdigest()})
    print(json.dumps({'mode': 'apply' if args.apply else 'dry-run', 'mapping': rows}))


if __name__ == '__main__':
    main()
