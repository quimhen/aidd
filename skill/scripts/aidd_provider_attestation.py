"""Generic, local-trust provider attestations; no database or project-specific code.

No caller-supplied report or self-declared approval is authoritative. A trusted
host must supply an approval verifier and invoke the configured provider itself.
This module does not alter the full-spec close gate.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath

_HASH = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]*\Z')
_SAFE_ENV = frozenset(('PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'HOME', 'USERPROFILE', 'LANG', 'LC_ALL'))


def _pairs(items):
    out = {}
    for key, value in items:
        if key in out:
            raise ValueError('duplicate JSON key')
        out[key] = value
    return out


def _read_file(root, name):
    if (not isinstance(name, str) or not name or '\\' in name or PurePosixPath(name).is_absolute()
            or PureWindowsPath(name).drive or any(p in ('', '.', '..') for p in name.split('/'))):
        raise ValueError('invalid relative path')
    path = Path(root)
    for part in name.split('/'):
        path /= part
        junction = getattr(path, 'is_junction', None)
        if path.is_symlink() or (callable(junction) and junction()):
            raise ValueError('linked path is not eligible')
    resolved = path.resolve(strict=True)
    resolved.relative_to(Path(root).resolve(strict=True))
    stat = path.stat()
    if not path.is_file() or stat.st_nlink != 1 or stat.st_size > 20 * 1024 * 1024:
        raise ValueError('ambiguous or oversized input')
    data = path.read_bytes()
    after = path.stat()
    if (stat.st_size, stat.st_mtime_ns, stat.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError('input changed while reading')
    return data


def _json_file(root, path):
    raw = _read_file(root, path)
    return raw, json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs)


def validate_contract(root, coverage_path, policy_path, approval_verifier):
    """Validate exact approved task map, provider binary and environment policy."""
    root = Path(root).resolve(strict=True)
    coverage_raw, coverage = _json_file(root, coverage_path)
    policy_raw, policy = _json_file(root, policy_path)
    if (not isinstance(coverage, dict) or set(coverage) != {'format', 'spec', 'unit', 'provider', 'tasks'}
            or coverage['format'] != 'aidd-provider-coverage-v1'
            or not _ID.fullmatch(str(coverage['spec'])) or not _ID.fullmatch(str(coverage['provider']))
            or not isinstance(coverage['unit'], str) or not _ID.fullmatch(coverage['unit'])
            or not isinstance(coverage['tasks'], dict) or not coverage['tasks']):
        raise ValueError('invalid coverage manifest')
    for task, entry in coverage['tasks'].items():
        if (not re.fullmatch(r'T-\d+', task) or not isinstance(entry, dict)
                or set(entry) != {'targets', 'tests', 'rows'}):
            raise ValueError('invalid task coverage')
        for key in ('targets', 'tests', 'rows'):
            values = entry[key]
            if not isinstance(values, list) or not values or len(set(values)) != len(values):
                raise ValueError('empty or duplicate coverage')
            if key != 'rows':
                for path in values:
                    _read_file(root, path)
            elif any(not isinstance(row, str) or not row for row in values):
                raise ValueError('invalid verification row')
    if (not isinstance(policy, dict) or set(policy) != {'format', 'provider', 'executable', 'executable_sha256', 'python_sha256',
            'coverage_sha256', 'environment', 'variables', 'argv', 'inputs', 'catalogs'} or policy['format'] != 'aidd-provider-policy-v1'
            or policy['provider'] != coverage['provider'] or not isinstance(policy['environment'], dict)
            or not policy['environment'] or not isinstance(policy['argv'], list) or not policy['argv']
            or any(not isinstance(arg, str) or not arg for arg in policy['argv'])
            or policy['argv'].count('{receipt}') != 1 or not isinstance(policy['inputs'], list)
            or any(not isinstance(name, str) for name in policy['inputs'])
            or len({name.casefold() for name in policy['inputs']}) != len(policy['inputs'])):
        raise ValueError('invalid provider policy')
    controlled_environment(policy)
    required = {path for task in coverage['tasks'].values() for kind in ('targets', 'tests') for path in task[kind]}
    required.update((coverage_path, policy_path, policy['executable']))
    if not required <= set(policy['inputs']):
        raise ValueError('provider policy lacks required inputs')
    for name in policy['inputs']:
        _read_file(root, name)
    if any(not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_]{1,80}', key)
           or re.search(r'(?i)secret|password|token|api_?key', key)
           or not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', value)
           for key, value in policy['environment'].items()):
        raise ValueError('environment identity must contain non-secret versions or digests')
    if not catalogs_match(root, policy['catalogs'], policy['inputs']):
        raise ValueError('provider input catalogs are incomplete or changed')
    if hashlib.sha256(coverage_raw).hexdigest() != policy['coverage_sha256']:
        raise ValueError('coverage policy digest mismatch')
    if hashlib.sha256(_read_file(root, policy['executable'])).hexdigest() != policy['executable_sha256']:
        raise ValueError('provider executable changed')
    if hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest() != policy['python_sha256']:
        raise ValueError('Python interpreter changed')
    if not callable(approval_verifier) or approval_verifier(coverage['spec'],
            hashlib.sha256(coverage_raw).hexdigest(), hashlib.sha256(policy_raw).hexdigest()) is not True:
        raise ValueError('coverage and provider policy lack verified owner approval')
    return coverage, policy, hashlib.sha256(coverage_raw).hexdigest(), hashlib.sha256(policy_raw).hexdigest()


def controlled_environment(policy):
    """Only explicitly fingerprinted non-secret OS variables reach the provider."""
    variables = policy.get('variables')
    if (not isinstance(variables, dict) or not set(variables) <= _SAFE_ENV or 'PATH' not in variables
            or (os.name == 'nt' and os.environ.get('SYSTEMROOT') and 'SYSTEMROOT' not in variables)):
        raise ValueError('provider OS environment is incomplete or unsafe')
    result = {}
    for name, expected in variables.items():
        value = os.environ.get(name)
        if (not isinstance(expected, str) or not _HASH.fullmatch(expected) or value is None
                or hashlib.sha256(value.encode('utf-8')).hexdigest() != expected):
            raise ValueError('provider OS environment changed or is unavailable')
        result[name] = value
    return result


def catalogs_match(root, catalogs, inputs):
    """Detect staged, deleted or untracked files in declared input catalogs."""
    try:
        root = Path(root).resolve(strict=True)
        if not isinstance(catalogs, list):
            return False
        raw = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z'], timeout=15)
        indexed = {entry.decode('utf-8') for entry in raw.split(b'\0') if entry}
        unique = set()
        for item in catalogs:
            if (not isinstance(item, dict) or set(item) != {'directory', 'suffix', 'contains', 'exclude_suffix', 'present', 'active'}
                    or type(item['present']) is not bool or type(item['active']) is not bool
                    or any(not isinstance(item[key], str) for key in ('directory', 'suffix', 'contains', 'exclude_suffix'))
                    or not item['suffix'] or any('/' in item[key] or '\\' in item[key] for key in ('suffix', 'contains', 'exclude_suffix'))):
                return False
            directory = item['directory']
            if (not directory or directory.startswith('/') or '\\' in directory or ':' in directory
                    or any(part in ('', '.', '..') for part in directory.split('/'))):
                return False
            identity = (directory.casefold(), item['suffix'], item['contains'], item['exclude_suffix'])
            if identity in unique:
                return False
            unique.add(identity)
            path = root
            for component in directory.split('/'):
                path /= component
                junction = getattr(path, 'is_junction', None)
                if path.is_symlink() or (callable(junction) and junction()):
                    return False
            if path.exists() != item['present'] or (path.exists() and not path.is_dir()):
                return False
            if not item['active']:
                continue
            prefix = directory + '/'
            def matches(name):
                return (name.startswith(prefix) and '/' not in name[len(prefix):]
                        and name.endswith(item['suffix']) and item['contains'] in name[len(prefix):]
                        and not (item['exclude_suffix'] and name.endswith(item['exclude_suffix'])))
            disk = ({prefix + entry.name for entry in path.iterdir() if (entry.is_file() or entry.is_symlink())
                     and matches(prefix + entry.name)} if path.is_dir() else set())
            if disk != {name for name in indexed if matches(name)} or disk != {name for name in inputs if matches(name)}:
                return False
        return True
    except (OSError, UnicodeError, ValueError, TypeError, subprocess.SubprocessError):
        return False


def unit_approval_verifier(root, coverage_path, policy_path, evidence):
    """Bind to the existing real unit approval, including material the owner saw."""
    def verify(spec, coverage_hash, policy_hash):
        try:
            try:
                from . import aidd_rules as rules, aidd_units as units, aidd_guard as guard, aidd_status as status
            except ImportError:
                import aidd_rules as rules
                import aidd_units as units
                import aidd_guard as guard
                import aidd_status as status
            coverage_raw, coverage = _json_file(root, coverage_path)
            policy_raw, policy = _json_file(root, policy_path)
            if (coverage.get('spec') != spec or hashlib.sha256(coverage_raw).hexdigest() != coverage_hash
                    or hashlib.sha256(policy_raw).hexdigest() != policy_hash):
                return False
            unit_id = coverage.get('unit')
            if not isinstance(unit_id, str) or not _ID.fullmatch(unit_id):
                return False
            manifest = Path(root) / 'specs' / spec / 'amendments' / unit_id / 'manifest.json'
            unit = units.load_unit(manifest, Path(root).resolve(strict=True))
            if unit.schema_version != 2 or not {coverage_path, policy_path} <= set(unit.paths):
                return False
            targets = {name for item in coverage['tasks'].values() for name in item['targets']}
            tests = {name for item in coverage['tasks'].values() for name in item['tests']}
            if not targets <= set(unit.targets) or not tests <= set(unit.targets + unit.inputs + unit.paths):
                return False
            closure = units.discover_unit_scope(Path(root), spec, [unit.key])
            required_inputs = set()
            for item in closure:
                required_inputs.update(item.paths + item.targets + item.inputs + item.config)
                required_inputs.add(f'specs/{item.spec_id}/amendments/{item.unit_id}/manifest.json')
                for visual in item.visual_refs:
                    required_inputs.add(visual.source)
                    required_inputs.update(visual.assets)
            if not required_inputs <= set(policy.get('inputs') or []):
                return False
            prefix = f'specs/{spec}/amendments/{unit_id}/'
            tasks = [name for name in unit.paths if name.startswith(prefix)
                     and re.fullmatch(r'tasks(?:-[A-Za-z0-9_-]+)?\.md', name[len(prefix):])]
            shown = '\n'.join(_read_file(root, name).decode('utf-8') for name in tasks)
            declared = set()
            for line in shown.splitlines():
                heading = re.match(r'^\s*#{1,3}\s+(T-\d+)\b', line, re.I)
                table = re.match(r'^\s*\|\s*`?(T-\d+)`?\s*\|', line, re.I)
                if heading or table:
                    declared.add((heading or table).group(1).upper())
            if not set(coverage['tasks']) <= declared:
                return False
            unit_rows = rules.parse_verification(shown)
            expected_command = f'aidd provider run --coverage {coverage_path} --policy {policy_path}'
            base_rows = rules.parse_verification((Path(root) / 'specs' / spec / 'spec.md').read_text(encoding='utf-8')) if (Path(root) / 'specs' / spec / 'spec.md').is_file() else []
            base_ids = {str(row.get('n')) for row in base_rows}
            for task, item in coverage['tasks'].items():
                selected_rows = status._task_rows(shown, unit_rows, [task])
                if set(item['rows']) != {str(row.get('n')) for row in selected_rows}:
                    return False
                if any(row.get('cmd') != expected_command or str(row.get('expected', '')).lower() != 'exit 0'
                       or str(row.get('n')) in base_ids for row in selected_rows):
                    return False
            documents = []
            base_tasks = Path(root) / 'specs' / spec / 'tasks.md'
            if base_tasks.exists():
                documents.append(base_tasks.read_text(encoding='utf-8'))
            for peer in units.discover_unit_scope(Path(root), spec):
                if peer.spec_id != spec:
                    continue
                peer_prefix = f'specs/{spec}/amendments/{peer.unit_id}/'
                peer_tasks = [name for name in peer.paths if name.startswith(peer_prefix)
                              and re.fullmatch(r'tasks(?:-[A-Za-z0-9_-]+)?\.md', name[len(peer_prefix):])]
                if not peer_tasks:
                    return False
                documents.extend(_read_file(root, name).decode('utf-8') for name in peer_tasks)
            owners = [guard._task_owners(document) for document in documents]
            for target in targets:
                coowners = {task for mapping in owners for task, paths in mapping.items()
                            if guard._owns(paths, target, rules)}
                if not coowners or not coowners <= set(coverage['tasks']):
                    return False
            # Unit approval presents task text. Require the exact canonical
            # coverage and policy there, not merely hashes of unseen files.
            canonical = lambda obj: json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
            if canonical(coverage) not in shown or canonical(policy) not in shown:
                return False
            return any(state.get('unit') == unit_id and state.get('approved') is True
                       for state in rules.unit_approval_states(root, spec, evidence))
        except (OSError, ValueError, TypeError, KeyError, UnicodeError):
            return False
    return verify


def current_index_matches(root, inputs):
    """Compare every observed tracked input to its exact Git index blob in one scan."""
    root = Path(root).resolve(strict=True)
    if not isinstance(inputs, dict) or not inputs:
        return False
    if len({str(name).casefold() for name in inputs}) != len(inputs):
        return False
    try:
        fmt = subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--show-object-format'], timeout=5).decode().strip()
        if fmt not in ('sha1', 'sha256'):
            return False
        raw = subprocess.check_output(['git', '-C', str(root), 'ls-files', '--stage', '-z'], timeout=15)
        index = {}
        for entry in filter(None, raw.split(b'\0')):
            metadata, path = entry.split(b'\t', 1)
            mode, oid, stage = metadata.split()
            name = path.decode('utf-8')
            if name in index:
                return False
            index[name] = (mode, oid.decode(), stage)
        for name, want in inputs.items():
            if not isinstance(want, str) or not _HASH.fullmatch(want):
                return False
            data = _read_file(root, name)
            if hashlib.sha256(data).hexdigest() != want:
                return False
            mode, oid, stage = index[name]
            object_id = hashlib.new(fmt, b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            if mode not in (b'100644', b'100755') or stage != b'0' or object_id != oid:
                return False
        return True
    except (OSError, ValueError, KeyError, UnicodeError, subprocess.SubprocessError):
        return False


def _observation_valid(observation, coverage, policy, inputs):
    if (not isinstance(observation, dict)
            or set(observation) != {'format', 'provider', 'status', 'environment', 'inputs', 'tasks', 'results', 'artifacts'}
            or observation['format'] != 'aidd-provider-observation-v1' or observation['provider'] != policy['provider']
            or observation['status'] != 'verified' or observation['environment'] != policy['environment']
            or observation['tasks'] != coverage['tasks'] or observation['inputs'] != inputs
            or not isinstance(observation['inputs'], dict) or set(observation['inputs']) != set(policy['inputs'])
            or not isinstance(observation['results'], list) or not isinstance(observation['artifacts'], dict)
            or not observation['artifacts']):
        return False
    expected = {row for task in coverage['tasks'].values() for row in task['rows']}
    rows = observation['results']
    if len(rows) != len(expected) or {row.get('row') for row in rows if isinstance(row, dict)} != expected:
        return False
    return all(set(row) == {'row', 'status', 'assertions', 'skipped'} and row['status'] == 'PASS'
               and type(row['assertions']) is int and row['assertions'] > 0
               and type(row['skipped']) is int and row['skipped'] == 0 for row in rows)


def _artifacts_valid(root, spec, artifacts):
    try:
        prefix = f'specs/{spec}/evidence/'
        for path, digest in artifacts.items():
            if (not isinstance(path, str) or not path.startswith(prefix) or '/' in path[len(prefix):]
                    or not isinstance(digest, str) or not _HASH.fullmatch(digest)
                    or hashlib.sha256(_read_file(root, path)).hexdigest() != digest):
                return False
        return True
    except (OSError, ValueError, TypeError):
        return False


def _run_provider_once(root, coverage_path, policy_path, approval_verifier, evidence, launched):
    """Run one approved process and record its actual result; no imported receipts."""
    root = Path(root).resolve(strict=True)
    coverage, policy, coverage_hash, policy_hash = validate_contract(root, coverage_path, policy_path, approval_verifier)
    input_hashes = {name: hashlib.sha256(_read_file(root, name)).hexdigest() for name in policy['inputs']}
    if not current_index_matches(root, input_hashes):
        raise ValueError('provider inputs do not match the Git index before execution')
    # The provider is an explicitly approved executable. Arguments are an array,
    # never a shell; the only interpolated argument is the private receipt path.
    with tempfile.TemporaryDirectory(prefix='aidd-provider-') as scratch:
        receipt_path = Path(scratch) / 'observation.json'
        argv = [sys.executable, '-I', '-S', '-B', str(root / policy['executable'])] + [
            str(receipt_path) if item == '{receipt}' else item for item in policy['argv']]
        process = subprocess.Popen(argv, cwd=root, stdin=subprocess.DEVNULL, env=controlled_environment(policy),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        launched['pid'] = process.pid
        try:
            stdout, _stderr = process.communicate(timeout=1800)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise ValueError('provider timed out; no attestation recorded')
        if process.returncode != 0 or not receipt_path.is_file() or receipt_path.is_symlink():
            raise ValueError('provider failed or did not produce an observation')
        raw = receipt_path.read_bytes()
        if len(raw) > 10 * 1024 * 1024:
            raise ValueError('provider observation too large')
        observation = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs)
        if not _observation_valid(observation, coverage, policy, input_hashes):
            raise ValueError('provider observation is incomplete or mismatched')
        if not _artifacts_valid(root, coverage['spec'], observation['artifacts']):
            raise ValueError('provider result artifacts are missing or changed')
        required = {path for task in coverage['tasks'].values() for kind in ('targets', 'tests') for path in task[kind]}
        required.update((coverage_path, policy_path, policy['executable']))
        if not required <= observation['inputs'].keys() or not current_index_matches(root, observation['inputs']):
            raise ValueError('provider inputs do not match the exact Git index')
        # Revalidate after the external process; do not accept a moving policy.
        if validate_contract(root, coverage_path, policy_path, approval_verifier)[2:] != (coverage_hash, policy_hash):
            raise ValueError('contract changed during execution')
        spec_evidence = root / 'specs' / coverage['spec'] / 'evidence'
        for directory in (root / 'specs', root / 'specs' / coverage['spec'], spec_evidence):
            junction = getattr(directory, 'is_junction', None)
            if not directory.is_dir() or directory.is_symlink() or (callable(junction) and junction()):
                raise ValueError('spec evidence directory is unavailable or linked')
        name = 'provider-' + uuid.uuid4().hex + '.json'
        destination = spec_evidence / name
        with destination.open('xb') as stream:
            stream.write(raw)
        detail = {'spec': coverage['spec'], 'provider': policy['provider'], 'tasks': coverage['tasks'],
                  'outcome': 'PASS',
                  'coverage_path': coverage_path, 'policy_path': policy_path, 'coverage_sha256': coverage_hash,
                  'policy_sha256': policy_hash, 'observation_path': destination.relative_to(root).as_posix(),
                  'observation_sha256': hashlib.sha256(raw).hexdigest(), 'stdout_sha256': hashlib.sha256(stdout).hexdigest(),
                  'pid': process.pid, 'exit_code': process.returncode, 'inputs': observation['inputs'],
                  'environment': observation['environment']}
        if not evidence.append(root, name, 'provider_verify_run', **detail):
            raise ValueError('provider event could not be recorded')
        return detail


def run_provider(root, coverage_path, policy_path, approval_verifier, evidence, *, fresh=False):
    """Record a failed attempt only if the approved process was actually launched."""
    coverage, policy, _, _ = validate_contract(root, coverage_path, policy_path, approval_verifier)
    targets = sorted({path for task in coverage['tasks'].values() for path in task['targets']})
    root_path = Path(root).resolve(strict=True)
    evidence_dir = root_path / 'specs' / coverage['spec'] / 'evidence'
    for directory in (root_path / 'specs', root_path / 'specs' / coverage['spec'], evidence_dir):
        junction = getattr(directory, 'is_junction', None)
        if not directory.is_dir() or directory.is_symlink() or (callable(junction) and junction()):
            raise ValueError('spec evidence directory is unavailable or linked')
    marker = evidence_dir / ('provider-' + coverage['unit'] + '.pending')
    if marker.exists() or marker.is_symlink():
        raise ValueError('a prior provider execution is unresolved')
    latest_task_failure = max((float(event.get('ts') or 0) for event in evidence.events(root, kind='task_verify_run')
        if (event.get('detail') or {}).get('spec') == coverage['spec']
        and (event.get('detail') or {}).get('ok') is False
        and set((event.get('detail') or {}).get('tasks') or []) & set(coverage['tasks'])), default=0.0)
    for event in ([] if fresh else reversed(evidence.events(root, kind='provider_verify_run'))):
        detail = event.get('detail') or {}
        event_tasks = detail.get('tasks') or {}
        if not isinstance(event_tasks, dict):
            break
        event_targets = {path for task in event_tasks.values() if isinstance(task, dict)
                         for path in task.get('targets') or []}
        if detail.get('spec') == coverage['spec'] and event_targets & set(targets) and detail.get('outcome') != 'PASS':
            break
        if (detail.get('spec') != coverage['spec'] or detail.get('coverage_path') != coverage_path
                or detail.get('policy_path') != policy_path):
            continue
        if (detail.get('outcome') == 'PASS' and float(event.get('ts') or 0) > latest_task_failure
                and evaluate_event(root, event, targets, approval_verifier)['eligible']):
            return {**detail, 'reused': True}
        break  # a newer failed, changed or unreadable execution cannot be bypassed
    launched = {}
    marker_data = {'format': 'aidd-provider-pending-v1', 'spec': coverage['spec'],
                   'targets': [hashlib.sha256(('aidd-provider-target-v1\0' + path).encode('utf-8')).hexdigest()
                               for path in targets]}
    with marker.open('x', encoding='utf-8') as stream:
        json.dump(marker_data, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    recorded = False
    try:
        result = _run_provider_once(root, coverage_path, policy_path, approval_verifier, evidence, launched)
        recorded = True
        return result
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, subprocess.SubprocessError):
        if launched:
            recorded = evidence.append(root, uuid.uuid4().hex, 'provider_verify_run', spec=coverage['spec'],
                                       provider=policy['provider'], tasks=coverage['tasks'], outcome='FAIL',
                                       coverage_path=coverage_path, policy_path=policy_path,
                                       pid=launched['pid'], reason='provider failed or its observation was invalid')
        else:
            recorded = True
        raise
    finally:
        if recorded:
            try:
                marker.unlink()
            except OSError:
                pass  # a surviving marker fails closed in the guard


def evaluate_event(root, event, code_paths, approval_verifier):
    """Check a recorded process receipt and exact index; never runs a provider or a database."""
    try:
        root = Path(root).resolve(strict=True)
        if not isinstance(event, dict) or event.get('kind') != 'provider_verify_run':
            return {'eligible': False, 'reason': 'provider event missing'}
        detail = event.get('detail') or {}
        coverage, policy, coverage_hash, policy_hash = validate_contract(
            root, detail['coverage_path'], detail['policy_path'], approval_verifier)
        if (detail.get('coverage_sha256') != coverage_hash or detail.get('policy_sha256') != policy_hash
                or detail.get('spec') != coverage['spec'] or detail.get('provider') != policy['provider']
                or detail.get('tasks') != coverage['tasks'] or detail.get('environment') != policy['environment']
                or detail.get('outcome') != 'PASS' or type(detail.get('pid')) is not int
                or detail['pid'] <= 0 or detail.get('exit_code') != 0):
            raise ValueError('provider execution or policy changed')
        raw = _read_file(root, detail['observation_path'])
        if hashlib.sha256(raw).hexdigest() != detail.get('observation_sha256'):
            raise ValueError('provider observation changed')
        observation = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs)
        if (not _observation_valid(observation, coverage, policy, detail.get('inputs'))
                or set((observation.get('inputs') or {}).keys()) != set(policy['inputs'])):
            raise ValueError('provider observation does not match execution')
        if not _artifacts_valid(root, coverage['spec'], observation['artifacts']):
            raise ValueError('provider result artifact changed')
        targets = {path for task in coverage['tasks'].values() for path in task['targets']}
        required = {path for task in coverage['tasks'].values() for kind in ('targets', 'tests') for path in task[kind]}
        required.update((detail['coverage_path'], detail['policy_path'], policy['executable']))
        if not code_paths or not set(code_paths) <= targets or not required <= observation['inputs'].keys():
            raise ValueError('staged path or required input is outside proven coverage')
        if not current_index_matches(root, observation['inputs']):
            raise ValueError('an input differs from the observed Git index')
        return {'eligible': True, 'reason': 'approved provider execution and exact index inputs match'}
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        return {'eligible': False, 'reason': 'provider attestation unavailable or changed'}


def main(argv=None):
    import argparse
    try:
        from . import aidd_evidence as evidence
    except ImportError:
        import aidd_evidence as evidence
    parser = argparse.ArgumentParser(description='Run an owner-approved provider without weakening spec close')
    parser.add_argument('action', choices=['run'])
    parser.add_argument('--root', default='.')
    parser.add_argument('--coverage', required=True)
    parser.add_argument('--policy', required=True)
    parser.add_argument('--fresh', action='store_true', help='explicitly run again instead of reusing current evidence')
    args = parser.parse_args(argv)
    try:
        root = evidence.find_root(Path(args.root).resolve())
        approve = unit_approval_verifier(root, args.coverage, args.policy, evidence)
        result = run_provider(root, args.coverage, args.policy, approve, evidence, fresh=args.fresh)
        print(json.dumps({'status': 'reused' if result.get('reused') else 'passed',
                          'spec': result['spec'], 'provider': result['provider'],
                          'observation_path': result['observation_path'], 'scope': 'partial; no spec close'}, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, subprocess.SubprocessError):
        print('Provider run unavailable: approval, policy, inputs or observed result are invalid.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
