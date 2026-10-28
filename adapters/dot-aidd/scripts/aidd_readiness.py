#!/usr/bin/env python3
"""Create a mechanical preparation report, without granting approval.

Usage: python aidd_readiness.py path/to/spec [--output report.json]

The report captures the check_spec output once, fingerprints visible planning
artifacts, and lists explicit code references occurring on the same line. A
line is not proof of a dependency or completeness. Hashes are diagnostic, not
a cache key: the checker may consult other project files and recorded evidence.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

CODE = re.compile(r'\b(?:FR|AC|US|SCREEN|CTL|COMP|API|T)-\d+(?:-F\d+)?\b')
ARTIFACTS = ('spec.md', 'plan.md', 'tasks.md', 'mockup-audit.md', 'contracts.md',
             'traceability.md', 'visual-flow.toon', 'visual-flow.md', 'data-model.md', 'qa-audit.md')
REQUIRED = ('spec.md', 'plan.md', 'tasks.md')


def fingerprint(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def snapshot(spec):
    """Visible files only; extra project state used by check_spec is not captured."""
    result = {}
    for name in ARTIFACTS:
        result[name] = fingerprint(spec / name)
    for i, base in enumerate((spec, spec / 'design-system', spec.parent / 'design-system',
                               spec.parent.parent / 'design-system')):
        result[f'component_index_{i}'] = fingerprint(base / 'components-index.md')
    for name in ('check_spec.py', 'aidd_rules.py', 'flowmap.py'):
        result[f'checker/{name}'] = fingerprint(Path(__file__).resolve().parent / name)
    return result


def references(spec):
    result = []
    for name in ARTIFACTS:
        path = spec / name
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            codes = sorted(set(CODE.findall(line)))
            if codes:
                result.append({'file': name, 'line': number, 'codes': codes})
    return result


def preapproval_findings(output, tasks):
    """Separate two known post-approval checks; unknown output remains a gap."""
    findings = re.findall(r'^\d+\. (.+)$', output, re.MULTILINE)
    deferred, actionable = [], []
    approval_lines = re.findall(r'^\s*Approved\s*:\s*([^\r\n]*)', tasks, re.MULTILINE | re.IGNORECASE)
    pending = not approval_lines or (len(approval_lines) == 1 and approval_lines[0].strip().lower() == 'pending')
    for finding in findings:
        if ((finding.startswith('R6 tasks.md has no valid "Approved:') and
             pending) or
                ('row(s) with an empty PR/Spec ref' in finding and
                 'fine before implementation' in finding)):
            deferred.append(finding)
        else:
            actionable.append(finding)
    return actionable, deferred


def report(spec):
    spec = Path(spec).resolve()
    if not spec.is_dir():
        raise ValueError('spec directory does not exist')
    before = snapshot(spec)
    refs = references(spec)
    cmd = [sys.executable, str(Path(__file__).with_name('check_spec.py')), str(spec)]
    check = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace', timeout=60)
    tasks = (spec / 'tasks.md').read_text(encoding='utf-8') if (spec / 'tasks.md').is_file() else ''
    after = snapshot(spec)
    changed = sorted(k for k in before if before[k] != after[k])
    missing = [name for name in REQUIRED if before[name] is None]
    actionable, deferred = preapproval_findings(check.stdout, tasks)
    # A nonzero checker without parsed findings is never silently treated as success.
    has_gaps = check.returncode == 1 and (bool(actionable) or not deferred)
    status = ('unstable' if changed else 'checker_error' if check.returncode not in (0, 1)
              else 'incomplete' if missing else 'gaps' if has_gaps else 'checked')
    return {
        'format': 'aidd-readiness-v1',
        'status': status,
        'notice': ('Structural report only: no approval, execution, semantic correctness or '
                   'independent audit is implied. Fingerprints are not a complete cache key.'),
        'spec': str(spec), 'missing_required_artifacts': missing,
        'observed_input_sha256': before, 'changed_observed_inputs': changed,
        'references_by_line': refs,
        'checker': {'name': 'check_spec.py', 'exit_code': check.returncode,
                    'actionable_findings': actionable, 'deferred_until_approval_or_implementation': deferred,
                    'stdout': check.stdout, 'stderr': check.stderr},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec')
    parser.add_argument('--output', help='write JSON to this path instead of stdout')
    args = parser.parse_args(argv)
    try:
        result = report(args.spec)
        output = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
        if args.output:
            dest = Path(args.output).resolve()
            if dest.exists():
                raise ValueError('output already exists; choose a new report path')
            dest.write_text(output, encoding='utf-8')
        else:
            sys.stdout.write(output)
        return 0 if result['status'] == 'checked' else 1
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR: could not prepare report: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
