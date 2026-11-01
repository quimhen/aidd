"""Plan and apply selected AIDD files with a durable rollback journal.

Existing customizations are refused when they differ from a supplied baseline.
Recovery restores only bytes known to belong to this transaction. Serialize
updates: for existing files a writer can still race the last hash and the OS
replacement; there is no portable atomic compare-and-swap for that operation.
"""
from __future__ import annotations

import argparse
import base64
import csv
import io
from contextlib import contextmanager
import errno
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath, PureWindowsPath


def _relative(value):
    if not isinstance(value, str) or any(character in value for character in ('\\', ':', '\x00')):
        raise ValueError('path must be a forward-slash relative path')
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or PureWindowsPath(value).drive
            or any(part in ('', '.', '..') for part in value.split('/'))):
        raise ValueError('invalid relative path')
    if value not in ('AIDD.md', 'SKILL.md', 'cli.py', 'RECORD', 'hooks.json', 'templates/navigator.html') and not (len(path.parts) == 2
            and path.parts[0] in ('hooks', 'scripts')
            and path.parts[1].endswith('.py') and not path.parts[1].startswith('.')):
        raise ValueError('path is not a distributed runtime file')
    return value


def _target_location(target, name):
    if name == 'cli.py' and (target.name.casefold() != 'aidd' or target.parent.name.casefold() != 'site-packages'):
        raise ValueError('cli.py target must be the installed aidd package')
    if name == 'RECORD' and (target.parent.name.casefold() != 'site-packages'
            or not re.fullmatch(r'aidd_cli-[A-Za-z0-9_.+-]+\.dist-info', target.name, re.I)):
        raise ValueError('RECORD target must be the aidd-cli distribution metadata')
    if name == 'hooks.json' and target.name.casefold() != '.codex':
        raise ValueError('hooks.json target must be the user Codex configuration directory')


_CODEX_SUBAGENT_COMMAND = ('python -c "import os,sys,runpy;'
    "p=os.path.expanduser('~/.claude/skills/aidd/hooks/codex_subagent.py');"
    "sys.path.insert(0,os.path.dirname(p));runpy.run_path(p,run_name='__main__')\"")


def _unique_json_pairs(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError('duplicate JSON key: ' + key)
        output[key] = value
    return output


def merge_codex_subagent_hooks(data):
    """Merge lifecycle definitions only; never modify host trust state."""
    if not isinstance(data, bytes) or len(data) > 4 * 1024 * 1024:
        raise ValueError('invalid Codex hooks configuration')
    try:
        config = json.loads(data.decode('utf-8-sig'), object_pairs_hook=_unique_json_pairs)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('invalid Codex hooks configuration') from exc
    if not isinstance(config, dict) or not isinstance(config.get('hooks'), dict):
        raise ValueError('Codex hooks must contain a hooks object')
    changed = False
    for event in ('SubagentStart', 'SubagentStop'):
        groups = config['hooks'].setdefault(event, [])
        if not isinstance(groups, list):
            raise ValueError('invalid Codex lifecycle hook list: ' + event)
        present = False
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get('hooks'), list):
                raise ValueError('invalid Codex lifecycle hook group: ' + event)
            for handler in group['hooks']:
                if not isinstance(handler, dict):
                    raise ValueError('invalid Codex lifecycle hook handler: ' + event)
                command = handler.get('command')
                if isinstance(command, str) and 'codex_subagent.py' in command:
                    if (command != _CODEX_SUBAGENT_COMMAND or handler.get('type') != 'command'
                            or group.get('matcher') not in (None, '', '*') or present
                            or set(handler) - {'type', 'command', 'timeout'}
                            or handler.get('timeout', 10) != 10
                            or set(group) - {'matcher', 'hooks'}):
                        raise ValueError('conflicting Codex lifecycle hook: ' + event)
                    present = True
        if not present:
            groups.append({'hooks': [{'type': 'command', 'command': _CODEX_SUBAGENT_COMMAND, 'timeout': 10}]})
            changed = True
    if not changed:
        return data
    newline = '\r\n' if b'\r\n' in data else '\n'
    output = (json.dumps(config, ensure_ascii=False, indent=2) + '\n').replace('\n', newline).encode('utf-8')
    return (b'\xef\xbb\xbf' if data.startswith(b'\xef\xbb\xbf') else b'') + output


def prepare_codex_hooks_plan(config_root, stage):
    """Stage only hooks.json; leave config.toml and trust state untouched."""
    target = _root(config_root)
    _target_location(target, 'hooks.json')
    current = target / 'hooks.json'
    before = _digest(current)
    original = current.read_bytes()
    updated = merge_codex_subagent_hooks(original)
    if _digest(current) != before:
        raise ValueError('Codex hooks changed during staging')
    staging = Path(stage).absolute()
    _no_links(staging)
    staging = staging.resolve(strict=False)
    try:
        common = os.path.commonpath((os.path.normcase(str(staging)), os.path.normcase(str(target))))
    except ValueError:
        common = ''
    if common == os.path.normcase(str(target)):
        raise ValueError('staging directory must be outside Codex configuration')
    staging.mkdir(mode=0o700, parents=False, exist_ok=False)
    (staging / 'source').mkdir()
    (staging / 'baseline').mkdir()
    _atomic_write(staging / 'source' / 'hooks.json', updated, 0o600)
    _atomic_write(staging / 'baseline' / 'hooks.json', original, 0o600)
    plan = make_plan(staging / 'source', target, ['hooks.json'], staging / 'baseline', bind_runtime=True)
    _atomic_write(staging / 'codex-hooks-plan.json', json.dumps(plan, indent=2).encode('utf-8'), 0o600)
    return plan


def _unique_distribution(site, expected):
    """A RECORD must belong to the only installed aidd-cli distribution here."""
    try:
        candidates = [entry for entry in site.iterdir()
                      if re.fullmatch(r'aidd_cli-[A-Za-z0-9_.+-]+\.dist-info', entry.name, re.I)]
    except OSError as exc:
        raise ValueError('cannot enumerate installed aidd-cli distributions') from exc
    if len(candidates) != 1:
        raise ValueError('ambiguous or missing aidd-cli distribution metadata')
    _no_links(candidates[0])
    if not candidates[0].is_dir() or candidates[0].resolve(strict=True) != expected.resolve(strict=True):
        raise ValueError('RECORD does not belong to the unique installed distribution')


def update_package_record(record_bytes, replacements):
    """Update hashes/sizes only for explicitly selected aidd package files."""
    if not isinstance(record_bytes, bytes) or len(record_bytes) > 4 * 1024 * 1024:
        raise ValueError('invalid package RECORD')
    try:
        text = record_bytes.decode('utf-8')
        rows = list(csv.reader(io.StringIO(text, newline='')))
    except (UnicodeError, csv.Error) as exc:
        raise ValueError('invalid package RECORD') from exc
    if any(len(row) != 3 for row in rows) or len({row[0] for row in rows}) != len(rows):
        raise ValueError('invalid or duplicate package RECORD rows')
    if not isinstance(replacements, dict) or not replacements:
        raise ValueError('empty package update')
    by_path = {row[0]: row for row in rows}
    for name, data in replacements.items():
        if not isinstance(name, str) or not isinstance(data, bytes) or '\\' in name:
            raise ValueError('invalid package replacement')
        if name != 'aidd/cli.py':
            prefixes = ('aidd/_data/skill/', 'aidd/_data/adapters/dot-aidd/')
            prefix = next((p for p in prefixes if name.startswith(p)), None)
            if prefix is None:
                raise ValueError('replacement is outside the aidd package')
            _relative(name[len(prefix):])
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode('ascii')
        row = [name, 'sha256=' + digest, str(len(data))]
        if name in by_path:
            by_path[name][:] = row
        else:
            rows.append(row)
    output = io.StringIO(newline='')
    csv.writer(output, lineterminator='\r\n' if '\r\n' in text else '\n').writerows(rows)
    return output.getvalue().encode('utf-8')


def prepare_package_plan(package_root, dist_info, source_package, baseline_package,
                         source_skill, baseline_skill, source_adapter, baseline_adapter,
                         stage, include_cli=False, skill_files=(), adapter_files=()):
    """Prepare package/RECORD plans in a new staging directory; install nothing."""
    package, metadata = _root(package_root), _root(dist_info)
    if package.name.casefold() != 'aidd':
        raise ValueError('package root must be the installed aidd package')
    _target_location(metadata, 'RECORD')
    if metadata.parent != package.parent:
        raise ValueError('package and metadata must have the same site-packages parent')
    _unique_distribution(package.parent, metadata)
    record_path = metadata / 'RECORD'
    _digest(record_path)
    original = record_path.read_bytes()
    try:
        rows = list(csv.reader(io.StringIO(original.decode('utf-8'), newline='')))
    except (UnicodeError, csv.Error) as exc:
        raise ValueError('invalid package RECORD') from exc
    if any(len(row) != 3 for row in rows) or len({row[0] for row in rows}) != len(rows):
        raise ValueError('invalid or duplicate package RECORD rows')
    recorded = {row[0]: row for row in rows}
    groups = []
    if include_cli:
        if source_package is None:
            raise ValueError('source package is required for cli.py')
        groups.append((source_package, package, baseline_package, ['cli.py'], 'aidd/'))
    if skill_files:
        if source_skill is None:
            raise ValueError('source skill is required for bundled skill files')
        groups.append((source_skill, package / '_data' / 'skill', baseline_skill,
                       list(skill_files), 'aidd/_data/skill/'))
    if adapter_files:
        if source_adapter is None:
            raise ValueError('source adapter is required for bundled adapter files')
        groups.append((source_adapter, package / '_data' / 'adapters' / 'dot-aidd', baseline_adapter,
                       list(adapter_files), 'aidd/_data/adapters/dot-aidd/'))
    if not groups:
        raise ValueError('select at least one package file')
    plans, replacements = [], {}
    for source, target, baseline, names, prefix in groups:
        plan = make_plan(source, target, names, baseline, bind_runtime=True)
        plans.append(plan)
        for item in plan['files']:
            name = prefix + item['path']
            if name in replacements:
                raise ValueError('duplicate package file')
            existing = recorded.get(name)
            if item['target_sha256'] is None:
                if existing is not None:
                    raise ValueError('recorded package file is missing: ' + name)
            else:
                path = _root(target) / item['path']
                digest = 'sha256=' + base64.urlsafe_b64encode(bytes.fromhex(item['target_sha256'])).rstrip(b'=').decode('ascii')
                if existing is None or existing[1] != digest or existing[2] != str(path.stat().st_size):
                    raise ValueError('installed package RECORD differs: ' + name)
            data = (_root(source) / item['path']).read_bytes()
            if hashlib.sha256(data).hexdigest() != item['source_sha256']:
                raise ValueError('source changed during package staging: ' + name)
            replacements[name] = data
    updated = update_package_record(original, replacements)
    if _digest(record_path) != hashlib.sha256(original).hexdigest():
        raise ValueError('package RECORD changed during staging')
    staging = Path(stage).absolute()
    _no_links(staging)
    staging = staging.resolve(strict=False)
    for target in [metadata, package, *[group[1] for group in groups]]:
        try:
            common = os.path.commonpath((os.path.normcase(str(staging)), os.path.normcase(str(_root(target)))))
        except ValueError:
            continue
        if common == os.path.normcase(str(_root(target))):
            raise ValueError('staging directory must be outside package targets')
    staging.mkdir(mode=0o700, parents=False, exist_ok=False)
    (staging / 'metadata-source').mkdir()
    (staging / 'metadata-baseline').mkdir()
    _atomic_write(staging / 'metadata-source' / 'RECORD', updated, 0o600)
    _atomic_write(staging / 'metadata-baseline' / 'RECORD', original, 0o600)
    plans.append(make_plan(staging / 'metadata-source', metadata, ['RECORD'], staging / 'metadata-baseline', bind_runtime=True))
    _atomic_write(staging / 'package-plans.json', json.dumps(plans, indent=2).encode('utf-8'), 0o600)
    return plans


def _no_links(path):
    for item in reversed((path, *path.parents)):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if (stat.S_ISLNK(info.st_mode) or getattr(info, 'st_reparse_tag', 0)
                or getattr(info, 'st_file_attributes', 0) & 0x400):
            raise ValueError('link or junction refused: ' + str(item))


def _digest(path, optional=False):
    _no_links(path)
    try:
        if not path.is_file():
            if optional and not path.exists():
                return None
            raise ValueError('not a regular file: ' + str(path))
        if path.stat().st_nlink > 1:
            raise ValueError('hardlinked file refused: ' + str(path))
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError('cannot read file: ' + str(path)) from exc


def _root(value):
    path = Path(value).absolute()
    _no_links(path)
    if not path.is_dir():
        raise ValueError('root directory is missing: ' + str(path))
    return path.resolve(strict=True)


def _runtime_identity():
    return {'executable': os.path.normcase(os.path.realpath(sys.executable)),
            'version': list(sys.version_info[:3]), 'cache_tag': sys.implementation.cache_tag,
            'pycache_prefix': (os.path.normcase(os.path.realpath(sys.pycache_prefix))
                               if sys.pycache_prefix is not None else None)}


def make_plan(source, target, files, baseline=None, bind_runtime=False):
    source, target = _root(source), _root(target)
    baseline = _root(baseline) if baseline is not None else None
    if source == target:
        raise ValueError('source and target must differ')
    files = [_relative(name) for name in files]
    if not files or len(set(name.casefold() for name in files)) != len(files):
        raise ValueError('empty or duplicate selection')
    items = []
    for name in sorted(files):
        _target_location(target, name)
        src, dst = source / name, target / name
        if not dst.parent.is_dir():
            raise ValueError('target parent missing: ' + str(dst.parent))
        source_hash, target_hash = _digest(src), _digest(dst, optional=True)
        baseline_hash = None
        if target_hash is not None and target_hash != source_hash:
            if baseline is None:
                raise ValueError('baseline required for existing changed file: ' + name)
            reference = baseline / name
            baseline_hash = _digest(reference)
            # Git distributes LF; Windows checkouts commonly materialize CRLF.
            if dst.read_bytes().replace(b'\r\n', b'\n') != reference.read_bytes().replace(b'\r\n', b'\n'):
                raise ValueError('installed file has local changes: ' + name)
        items.append({'path': name, 'source_sha256': source_hash,
                      'target_sha256': target_hash, 'baseline_sha256': baseline_hash})
    result = {'version': 2 if bind_runtime else 1, 'source': str(source), 'target': str(target),
              'baseline': str(baseline) if baseline is not None else None, 'files': items}
    if bind_runtime:
        result['runtime'] = _runtime_identity()
    return result


_NO_PRECONDITION = object()
_DIRSYNC_WARNED = False


@contextmanager
def _windows_security_privilege():
    """Temporarily enable audit-ACL access; refuse when it is unavailable."""
    import ctypes
    from ctypes import wintypes
    adv = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    adv.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]

    class Luid(ctypes.Structure):
        _fields_ = [('low', wintypes.DWORD), ('high', wintypes.LONG)]

    class Entry(ctypes.Structure):
        _fields_ = [('luid', Luid), ('attributes', wintypes.DWORD)]

    class Privileges(ctypes.Structure):
        _fields_ = [('count', wintypes.DWORD), ('entries', Entry * 1)]

    adv.AdjustTokenPrivileges.argtypes = [wintypes.HANDLE, wintypes.BOOL, ctypes.POINTER(Privileges),
                                          wintypes.DWORD, ctypes.POINTER(Privileges), ctypes.POINTER(wintypes.DWORD)]
    adv.AdjustTokenPrivileges.restype = wintypes.BOOL
    token = wintypes.HANDLE()
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(), 0x28, ctypes.byref(token)):
        raise OSError(ctypes.get_last_error(), 'cannot query Windows security privileges')
    old, previous_size = Privileges(), wintypes.DWORD()
    enabled = False
    try:
        luid = Luid()
        if not adv.LookupPrivilegeValueW(None, 'SeSecurityPrivilege', ctypes.byref(luid)):
            raise OSError(ctypes.get_last_error(), 'cannot find Windows audit privilege')
        requested = Privileges(1, (Entry(luid, 2),))
        ctypes.set_last_error(0)
        if not adv.AdjustTokenPrivileges(token, False, ctypes.byref(requested), ctypes.sizeof(old),
                                         ctypes.byref(old), ctypes.byref(previous_size)) or ctypes.get_last_error():
            raise OSError(ctypes.get_last_error(), 'cannot enable Windows audit privilege')
        enabled = True
        yield adv, kernel
    finally:
        restore_error = 0
        if enabled:
            ctypes.set_last_error(0)
            if not adv.AdjustTokenPrivileges(token, False, ctypes.byref(old), 0, None, None) or ctypes.get_last_error():
                restore_error = ctypes.get_last_error() or 1
        kernel.CloseHandle(token)
        if restore_error:
            raise OSError(restore_error, 'could not restore Windows audit privilege')


def _windows_security_snapshot(path):
    """Capture owner, group, DACL and SACL or fail closed."""
    import ctypes
    from ctypes import wintypes
    with _windows_security_privilege() as (adv, kernel):
        get = adv.GetFileSecurityW
        get.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p,
                        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        get.restype = wintypes.BOOL
        size = wintypes.DWORD()
        get(str(path), 15, None, 0, ctypes.byref(size))
        if not size.value or size.value > 1024 * 1024:
            raise OSError(ctypes.get_last_error(), 'cannot read full Windows security descriptor')
        data = ctypes.create_string_buffer(size.value)
        if not get(str(path), 15, data, size.value, ctypes.byref(size)):
            raise OSError(ctypes.get_last_error(), 'cannot read full Windows security descriptor')
        get_control = adv.GetSecurityDescriptorControl
        get_control.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.WORD), ctypes.POINTER(wintypes.DWORD)]
        get_control.restype = wintypes.BOOL
        control, revision = wintypes.WORD(), wintypes.DWORD()
        if not get_control(data, ctypes.byref(control), ctypes.byref(revision)):
            raise OSError(ctypes.get_last_error(), 'cannot inspect Windows security descriptor')
        convert = adv.ConvertSecurityDescriptorToStringSecurityDescriptorW
        convert.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                            ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(wintypes.DWORD)]
        convert.restype = wintypes.BOOL
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        output = wintypes.LPWSTR()
        if not convert(data, 1, 15, ctypes.byref(output), None):
            raise OSError(ctypes.get_last_error(), 'cannot compare Windows security descriptor')
        try:
            return {'sddl': output.value,
                    'descriptor': base64.b64encode(data.raw[:size.value]).decode('ascii'),
                    'flags': 3 | (4 if control.value & 0x4 else 0) | (8 if control.value & 0x10 else 0)}
        finally:
            kernel.LocalFree(ctypes.cast(output, ctypes.c_void_p))


def _windows_security_descriptor(path):
    return _windows_security_snapshot(path)['sddl']


def _only_missing_dacl_auto_inheritance(expected, actual):
    return 'D:AI(' in expected and actual == expected.replace('D:AI(', 'D:(', 1)


def _restore_windows_security(path, snapshot):
    import ctypes
    from ctypes import wintypes
    if not isinstance(snapshot, dict) or set(snapshot) != {'sddl', 'descriptor', 'flags'}:
        raise ValueError('invalid Windows security snapshot')
    try:
        raw = base64.b64decode(snapshot['descriptor'], validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError('invalid Windows security descriptor') from exc
    with _windows_security_privilege() as (adv, _kernel):
        setter = adv.SetFileSecurityW
        setter.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
        setter.restype = wintypes.BOOL
        data = ctypes.create_string_buffer(raw)
        if not setter(str(path), snapshot['flags'], data):
            raise OSError(ctypes.get_last_error(), 'cannot restore Windows security descriptor')
    actual = _windows_security_descriptor(path)
    expected = snapshot['sddl']
    if actual != expected and _only_missing_dacl_auto_inheritance(expected, actual):
        # ReplaceFileW can clear only the auto-inherited control flag. Ask
        # Windows to re-evaluate inheritance, then require exact equality.
        system_root = os.environ.get('SystemRoot')
        if not system_root:
            raise RuntimeError('Windows system directory is unavailable')
        executable = Path(system_root) / 'System32' / 'icacls.exe'
        result = subprocess.run([str(executable), str(path), '/inheritance:e'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode:
            raise RuntimeError('Windows ACL inheritance restoration failed: ' + str(path))
        actual = _windows_security_descriptor(path)
    if actual != expected:
        raise RuntimeError('Windows security descriptor could not be restored: ' + str(path))


def _fsync_dir(path):
    """Persist directory metadata where supported; Windows has no portable API here."""
    global _DIRSYNC_WARNED
    if os.name == 'nt':
        if not _DIRSYNC_WARNED:
            print('NOTE: directory fsync is unavailable; power-loss durability is not guaranteed.', file=sys.stderr)
            _DIRSYNC_WARNED = True
        return False
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return True
    except OSError as exc:
        if exc.errno in (errno.EINVAL, errno.ENOTSUP, getattr(errno, 'EOPNOTSUPP', errno.ENOTSUP)):
            if not _DIRSYNC_WARNED:
                print('NOTE: directory fsync is unsupported; power-loss durability is not guaranteed.', file=sys.stderr)
                _DIRSYNC_WARNED = True
            return False
        raise


def _move_new_no_replace(temporary, path):
    """Atomically move a new file without overwriting an existing destination."""
    import ctypes
    if os.name == 'nt':
        from ctypes import wintypes
        move = ctypes.WinDLL('kernel32', use_last_error=True).MoveFileExW
        move.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
        move.restype = wintypes.BOOL
        if not move(str(temporary), str(path), 0):
            raise OSError(ctypes.get_last_error(), 'atomic no-replace move failed')
        return
    if not sys.platform.startswith('linux'):
        raise OSError(errno.ENOTSUP, 'atomic no-replace move is not supported on this platform')
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        rename = libc.renameat2
    except AttributeError as exc:
        raise OSError(errno.ENOTSUP, 'renameat2 is unavailable') from exc
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(temporary), -100, os.fsencode(path), 1) != 0:
        raise OSError(ctypes.get_errno(), 'atomic no-replace move failed')


def _require_cache_alias_safety(paths):
    # Prefixed bytecode is keyed by the spelling of the import path; on Windows
    # 8.3 aliases can map the same source to another, uninspected cache tree.
    if os.name == 'nt' and sys.pycache_prefix is not None and any(Path(path).suffix.casefold() == '.py' for path in paths):
        raise ValueError('Windows Python update with a cache prefix cannot safely enumerate path aliases')


def _python_cache_timestamps(source):
    """Find timestamp pycs; reject hash pycs because runtimes may trust them unchecked."""
    caches = [source.parent / '__pycache__']
    if sys.pycache_prefix is not None:
        caches.append(Path(importlib.util.cache_from_source(str(source))).parent)
    timestamps = set()
    prefix = source.stem.casefold() + '.'
    for cache in dict.fromkeys(caches):
        _no_links(cache)
        if not cache.exists():
            continue
        if not cache.is_dir():
            raise ValueError('Python cache path is not a directory: ' + str(cache))
        for path in cache.iterdir():
            if not (path.name.casefold().startswith(prefix) and path.name.casefold().endswith('.pyc')):
                continue
            _no_links(path)
            before = path.stat()
            if not stat.S_ISREG(before.st_mode) or before.st_nlink > 1:
                raise ValueError('ambiguous Python bytecode: ' + str(path))
            with path.open('rb') as stream:
                header = stream.read(16)
            after = path.stat()
            if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                    != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
                raise ValueError('Python bytecode changed while checking: ' + str(path))
            if len(header) != 16 or header[2:4] != b'\r\n':
                raise ValueError('invalid Python bytecode header: ' + str(path))
            flags = int.from_bytes(header[4:8], 'little')
            if flags & 1:
                raise ValueError('hash-based Python bytecode requires manual reconciliation: ' + str(path))
            if flags != 0:
                raise ValueError('unsupported Python bytecode flags: ' + str(path))
            timestamps.add(int.from_bytes(header[8:12], 'little'))
    return timestamps


def _prepare_python_mtime(path, temporary):
    if path.suffix.casefold() != '.py':
        return None
    timestamps = _python_cache_timestamps(path)
    candidate = int(time.time()) & 0xffffffff
    for _ in range(len(timestamps) + 2):
        if candidate and candidate not in timestamps:
            break
        candidate = (candidate - 1) & 0xffffffff
    else:
        raise ValueError('cannot select a fresh Python source timestamp')
    os.utime(temporary, (candidate, candidate))
    return candidate


def _replace_file(temporary, path, security, expected=_NO_PRECONDITION):
    if expected is None:
        _move_new_no_replace(temporary, path)
        return
    if os.name != 'nt' or security is None:
        if expected is not _NO_PRECONDITION and _digest(path, optional=True) != expected:
            raise ValueError('destination changed immediately before replacement: ' + str(path))
        os.replace(temporary, path)
        return
    import ctypes
    from ctypes import wintypes
    replace = ctypes.WinDLL('kernel32', use_last_error=True).ReplaceFileW
    replace.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                        wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]
    replace.restype = wintypes.BOOL
    if _windows_security_descriptor(path) != security['sddl']:
        raise ValueError('Windows security descriptor changed before replacement: ' + str(path))
    if expected is not _NO_PRECONDITION and _digest(path, optional=True) != expected:
        raise ValueError('destination changed immediately before replacement: ' + str(path))
    if not replace(str(path), temporary, None, 0, None, None):
        raise OSError(ctypes.get_last_error(), 'Windows metadata-preserving replacement failed')
    if _windows_security_descriptor(path) != security['sddl']:
        _restore_windows_security(path, security)


def _atomic_write(path, data, mode=None, expected=_NO_PRECONDITION, expected_acl=None):
    _no_links(path)
    fd, temporary = tempfile.mkstemp(prefix='.aidd-update-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        python_mtime = _prepare_python_mtime(path, temporary) if expected is not _NO_PRECONDITION else None
        _no_links(path)
        if os.name == 'nt' and expected is None:
            if not isinstance(expected_acl, dict) or _windows_security_descriptor(temporary) != expected_acl.get('sddl'):
                raise ValueError('Windows inherited ACL changed before creation: ' + str(path))
        security = _windows_security_snapshot(path) if os.name == 'nt' and path.exists() else None
        if os.name == 'nt' and expected is not _NO_PRECONDITION and expected is not None:
            if not isinstance(expected_acl, dict) or security is None or security['sddl'] != expected_acl.get('sddl'):
                raise ValueError('Windows ACL changed since backup: ' + str(path))
        if expected is not _NO_PRECONDITION and _digest(path, optional=True) != expected:
            raise ValueError('destination changed immediately before replacement: ' + str(path))
        if python_mtime is not None and python_mtime in _python_cache_timestamps(path):
            raise ValueError('Python bytecode appeared during replacement: ' + str(path))
        _replace_file(temporary, path, security, expected)
        if python_mtime is not None:
            actual = int(path.stat().st_mtime) & 0xffffffff
            if actual != python_mtime or actual in _python_cache_timestamps(path):
                raise RuntimeError('Python source timestamp cannot invalidate bytecode: ' + str(path))
        _fsync_dir(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _write_journal(path, value):
    _atomic_write(path, json.dumps(value, sort_keys=True, indent=2).encode('utf-8'))


def _expected_new_windows_acl(parent):
    """Observe ACL inherited by the same mkstemp operation before journaling."""
    fd, temporary = tempfile.mkstemp(prefix='.aidd-acl-probe-', dir=parent)
    os.close(fd)
    try:
        return _windows_security_snapshot(temporary)
    finally:
        os.unlink(temporary)
        _fsync_dir(parent)


def _plan_entries(plan):
    if not isinstance(plan, dict) or plan.get('version') not in (1, 2):
        raise ValueError('invalid plan')
    keys = {'version', 'source', 'target', 'baseline', 'files'}
    if plan['version'] == 2:
        keys.add('runtime')
    if set(plan) != keys:
        raise ValueError('invalid plan')
    runtime = plan.get('runtime')
    if plan['version'] == 2 and runtime != _runtime_identity():
        raise ValueError('runtime or Python bytecode prefix changed after planning')
    source, target = _root(plan['source']), _root(plan['target'])
    baseline = _root(plan['baseline']) if plan['baseline'] is not None else None
    if source == target:
        raise ValueError('source and target must differ')
    items = plan['files']
    if not isinstance(items, list) or not items or any(not isinstance(x, dict)
            or set(x) != {'path', 'source_sha256', 'target_sha256', 'baseline_sha256'} for x in items):
        raise ValueError('invalid plan entries')
    names = [_relative(item['path']) for item in items]
    if len(set(name.casefold() for name in names)) != len(names):
        raise ValueError('duplicate selection')
    entries = []
    for item in items:
        _target_location(target, item['path'])
        if (_package_membership(target, item['path']) is not None or item['path'] == 'RECORD') and runtime is None:
            raise ValueError('installed package update requires a runtime-bound plan')
        src, dst = source / item['path'], target / item['path']
        if not dst.parent.is_dir() or _digest(src) != item['source_sha256']:
            raise ValueError('source changed or target directory missing: ' + item['path'])
        if _digest(dst, optional=True) != item['target_sha256']:
            raise ValueError('destination changed: ' + item['path'])
        if item['target_sha256'] is not None and item['target_sha256'] != item['source_sha256']:
            if baseline is None or _digest(baseline / item['path']) != item['baseline_sha256']:
                raise ValueError('baseline missing or changed: ' + item['path'])
            if dst.read_bytes().replace(b'\r\n', b'\n') != (baseline / item['path']).read_bytes().replace(b'\r\n', b'\n'):
                raise ValueError('installed file has local changes: ' + item['path'])
        data = src.read_bytes()
        if hashlib.sha256(data).hexdigest() != item['source_sha256']:
            raise ValueError('source changed while reading: ' + item['path'])
        if item['target_sha256'] != item['source_sha256']:
            entries.append((target, {**item, '_runtime': runtime}, data))
    return entries


def _load_journal(journal_dir):
    journal = _root(journal_dir)
    path = journal / 'transaction.json'
    _no_links(path)
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('invalid transaction journal') from exc
    if not isinstance(value, dict) or set(value) != {'version', 'state', 'files'} or value['version'] != 1:
        raise ValueError('invalid transaction journal')
    if value['state'] not in ('prepared', 'applying', 'committed', 'rolling_back', 'rolled_back'):
        raise ValueError('unknown transaction state')
    if not isinstance(value['files'], list) or not value['files']:
        raise ValueError('invalid transaction entries')
    for index, item in enumerate(value['files']):
        keys = {'target', 'path', 'before', 'after', 'backup', 'mode', 'acl', 'after_acl', 'runtime'}
        if not isinstance(item, dict) or set(item) != keys:
            raise ValueError('invalid transaction entry')
        target = _root(item['target'])
        _relative(item['path'])
        _target_location(target, item['path'])
        if item['runtime'] is not None and item['runtime'] != _runtime_identity():
            raise ValueError('recovery runtime or Python bytecode prefix changed')
        if (not isinstance(item['after'], str) or not re.fullmatch(r'[0-9a-f]{64}', item['after'])
                or (item['before'] is not None and (not isinstance(item['before'], str)
                    or not re.fullmatch(r'[0-9a-f]{64}', item['before'])))):
            raise ValueError('invalid transaction hashes')
        if item['backup'] != (f'{index:06d}.bak' if item['before'] is not None else None):
            raise ValueError('invalid backup identifier')
        if item['before'] is not None and _digest(journal / item['backup']) != item['before']:
            raise ValueError('backup integrity failure')
    keys = [str(_root(item['target']) / item['path']).casefold() for item in value['files']]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate transaction target')
    return journal, value


def recover_transaction(journal_dir):
    journal, record = _load_journal(journal_dir)
    if record['state'] == 'rolled_back':
        return 0
    # Validate all paths first: never partially roll back over an unrelated edit.
    restore = []
    for item in reversed(record['files']):
        target = _root(item['target']) / _relative(item['path'])
        current = _digest(target, optional=True)
        if current not in (item['before'], item['after']):
            raise ValueError('destination modified after transaction: ' + str(target))
        if os.name == 'nt' and current is not None:
            expected_acl = item['after_acl'] if current == item['after'] and current != item['before'] else item['acl']
            if not isinstance(expected_acl, dict) or _windows_security_descriptor(target) != expected_acl.get('sddl'):
                raise ValueError('Windows ACL changed or cannot be reconciled automatically: ' + str(target))
        if current == item['after'] and current != item['before']:
            restore.append((target, item))
    _require_cache_alias_safety(target for target, item in restore if item['before'] is not None)
    record['state'] = 'rolling_back'
    _write_journal(journal / 'transaction.json', record)
    for target, item in restore:
        if _digest(target, optional=True) != item['after']:
            raise ValueError('destination changed during recovery: ' + str(target))
        if item['before'] is None:
            _no_links(target)
            if _digest(target, optional=True) != item['after']:
                raise ValueError('destination changed before removal: ' + str(target))
            if os.name == 'nt' and _windows_security_descriptor(target) != item['after_acl'].get('sddl'):
                raise ValueError('Windows ACL changed before removal: ' + str(target))
            target.unlink()
            _fsync_dir(target.parent)
        else:
            data = (journal / item['backup']).read_bytes()
            if hashlib.sha256(data).hexdigest() != item['before']:
                raise ValueError('backup changed during recovery')
            _atomic_write(target, data, item['mode'], expected=item['after'], expected_acl=item['after_acl'])
        if _digest(target, optional=True) != item['before']:
            raise ValueError('recovery could not be verified: ' + str(target))
    record['state'] = 'rolled_back'
    _write_journal(journal / 'transaction.json', record)
    return len(restore)


def _package_membership(target, name):
    """Return (site-packages, RECORD path) for an installed package file."""
    if name == 'cli.py':
        return target.parent, 'aidd/cli.py'
    parts = tuple(part.casefold() for part in target.parts)
    if len(parts) >= 3 and parts[-3:] == ('aidd', '_data', 'skill'):
        package = target.parents[1]
        if package.parent.name.casefold() == 'site-packages':
            return package.parent, 'aidd/_data/skill/' + name
    if len(parts) >= 4 and parts[-4:] == ('aidd', '_data', 'adapters', 'dot-aidd'):
        package = target.parents[2]
        if package.parent.name.casefold() == 'site-packages':
            return package.parent, 'aidd/_data/adapters/dot-aidd/' + name
    return None


def _record_rows(data):
    try:
        rows = list(csv.reader(io.StringIO(data.decode('utf-8'), newline='')))
    except (UnicodeError, csv.Error) as exc:
        raise ValueError('invalid package RECORD') from exc
    if any(len(row) != 3 or not row[0] for row in rows):
        raise ValueError('invalid package RECORD row')
    names = [row[0].casefold() for row in rows]
    if len(set(names)) != len(names):
        raise ValueError('duplicate package RECORD row')
    return rows


def _check_package_records(prepared):
    """Require a complete, bidirectional RECORD update for each changed package."""
    metadata = [(target, data) for target, item, data in prepared if item['path'] == 'RECORD']
    changes = {}
    for target, item, data in prepared:
        membership = _package_membership(target, item['path'])
        if membership is not None:
            site, name = membership
            changes.setdefault(site, []).append((name, target, item, data))
    if len(metadata) != len(changes):
        raise ValueError('package files and RECORD must change together')
    for metadata_dir, updated in metadata:
        site = metadata_dir.parent
        _unique_distribution(site, metadata_dir)
        selected = changes.get(site)
        if not selected:
            raise ValueError('RECORD update has no package changes')
        old_rows = _record_rows((metadata_dir / 'RECORD').read_bytes())
        new_rows = _record_rows(updated)
        old = {row[0]: row for row in old_rows}
        new = {row[0]: row for row in new_rows}
        record_name = metadata_dir.name + '/RECORD'
        if old.get(record_name) != [record_name, '', ''] or new.get(record_name) != old[record_name]:
            raise ValueError('distribution RECORD self-entry is missing or changed')
        selected_names = {name for name, _, _, _ in selected}
        if len(selected_names) != len(selected):
            raise ValueError('duplicate package change')
        old_unselected = [row for row in old_rows if row[0] not in selected_names]
        new_unselected = [row for row in new_rows if row[0] not in selected_names]
        if old_unselected != new_unselected:
            raise ValueError('unselected RECORD entries changed')
        for name, target, item, data in selected:
            current = old.get(name)
            if item['target_sha256'] is None:
                if current is not None:
                    raise ValueError('recorded package file is missing: ' + name)
            else:
                original_digest = 'sha256=' + base64.urlsafe_b64encode(
                    bytes.fromhex(item['target_sha256'])).rstrip(b'=').decode('ascii')
                expected_original = [name, original_digest, str((target / item['path']).stat().st_size)]
                if current != expected_original:
                    raise ValueError('installed package RECORD differs: ' + name)
            digest = 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode('ascii')
            if new.get(name) != [name, digest, str(len(data))]:
                raise ValueError('package RECORD does not match replacement: ' + name)
    if changes and {directory.parent for directory, _ in metadata} != set(changes):
        raise ValueError('package files and RECORD belong to different installations')


def apply_transaction(plans, journal_dir):
    if not isinstance(plans, list) or not plans:
        raise ValueError('empty transaction')
    prepared = [entry for plan in plans for entry in _plan_entries(plan)]
    if not prepared:
        return 0
    _require_cache_alias_safety(target / item['path'] for target, item, _ in prepared)
    _check_package_records(prepared)
    keys = [str(target / item['path']).casefold() for target, item, _ in prepared]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate transaction target')
    journal = Path(journal_dir).absolute()
    _no_links(journal)
    journal = journal.resolve(strict=False)
    for target, _, _ in prepared:
        try:
            common = os.path.commonpath((os.path.normcase(str(journal)), os.path.normcase(str(target))))
        except ValueError:
            continue
        if common == os.path.normcase(str(target)):
            raise ValueError('journal must be outside every target root')
    journal.mkdir(mode=0o700, parents=False, exist_ok=False)
    _fsync_dir(journal.parent)
    record = {'version': 1, 'state': 'prepared', 'files': []}
    for index, (target, item, _) in enumerate(prepared):
        dst = target / item['path']
        before = item['target_sha256']
        if _digest(dst, optional=True) != before:
            raise ValueError('destination changed before backup: ' + str(dst))
        backup = f'{index:06d}.bak' if before is not None else None
        mode = stat.S_IMODE(dst.stat().st_mode) if before is not None else None
        acl = _windows_security_snapshot(dst) if os.name == 'nt' and before is not None else None
        after_acl = (acl if before is not None else _expected_new_windows_acl(dst.parent)) if os.name == 'nt' else None
        if backup:
            data = dst.read_bytes()
            if hashlib.sha256(data).hexdigest() != before:
                raise ValueError('destination changed during backup: ' + str(dst))
            _atomic_write(journal / backup, data, 0o600)
        record['files'].append({'target': str(target), 'path': item['path'], 'before': before,
                                'after': item['source_sha256'], 'backup': backup, 'mode': mode,
                                'acl': acl, 'after_acl': after_acl, 'runtime': item['_runtime']})
    _write_journal(journal / 'transaction.json', record)
    try:
        record['state'] = 'applying'
        _write_journal(journal / 'transaction.json', record)
        for index, (target, item, data) in enumerate(prepared):
            dst = target / item['path']
            if _digest(dst, optional=True) != item['target_sha256']:
                raise ValueError('destination changed before replacement: ' + str(dst))
            mode = stat.S_IMODE(dst.stat().st_mode) if dst.exists() else None
            _atomic_write(dst, data, mode, expected=item['target_sha256'], expected_acl=record['files'][index]['after_acl'])
            if _digest(dst) != item['source_sha256']:
                raise ValueError('replacement could not be verified: ' + str(dst))
            if os.name == 'nt' and item['target_sha256'] is None:
                if _windows_security_descriptor(dst) != record['files'][index]['after_acl']['sddl']:
                    raise ValueError('Windows ACL changed after creation: ' + str(dst))
        record['state'] = 'committed'
        _write_journal(journal / 'transaction.json', record)
    except Exception as original:
        try:
            recover_transaction(journal)
        except Exception as recovery:
            raise RuntimeError(f'transaction failed; recovery required at {journal}: {recovery}') from original
        raise
    return len(prepared)


def apply_plan(plan, journal_dir):
    return apply_transaction([plan], journal_dir)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    plan = commands.add_parser('plan')
    plan.add_argument('--source', required=True)
    plan.add_argument('--target', required=True)
    plan.add_argument('--file', action='append', required=True)
    plan.add_argument('--baseline', help='known previously distributed files for customization checks')
    plan.add_argument('--bind-runtime', action='store_true', help='require this Python runtime and bytecode prefix at apply/recover')
    package = commands.add_parser('package-plan', help='stage CLI, bundled resources and RECORD plans')
    package.add_argument('--package-root', required=True)
    package.add_argument('--dist-info', required=True)
    package.add_argument('--stage', required=True)
    package.add_argument('--cli', action='store_true')
    package.add_argument('--source-package')
    package.add_argument('--baseline-package')
    package.add_argument('--source-skill')
    package.add_argument('--baseline-skill')
    package.add_argument('--skill-file', action='append', default=[])
    package.add_argument('--source-adapter')
    package.add_argument('--baseline-adapter')
    package.add_argument('--adapter-file', action='append', default=[])
    hooks = commands.add_parser('codex-hooks-plan', help='stage lifecycle hooks without changing trust state')
    hooks.add_argument('--config-root', required=True)
    hooks.add_argument('--stage', required=True)
    apply = commands.add_parser('apply')
    apply.add_argument('--plan', action='append', required=True, help='repeat for each profile/project')
    apply.add_argument('--journal', required=True, help='new durable backup directory outside targets')
    recover = commands.add_parser('recover')
    recover.add_argument('--journal', required=True, help='existing transaction backup directory')
    args = parser.parse_args(argv)
    try:
        if args.command == 'plan':
            print(json.dumps(make_plan(args.source, args.target, args.file, args.baseline, args.bind_runtime), indent=2))
        elif args.command == 'package-plan':
            planned = prepare_package_plan(args.package_root, args.dist_info, args.source_package,
                args.baseline_package, args.source_skill, args.baseline_skill, args.source_adapter,
                args.baseline_adapter, args.stage, args.cli, args.skill_file, args.adapter_file)
            print(f'Staged {len(planned)} package plan(s) in {args.stage}; no installation was changed.')
        elif args.command == 'codex-hooks-plan':
            prepare_codex_hooks_plan(args.config_root, args.stage)
            print(f'Staged Codex lifecycle hooks in {args.stage}; trust state was not changed.')
        elif args.command == 'apply':
            saved = []
            for path in args.plan:
                with open(path, encoding='utf-8') as inp:
                    value = json.load(inp)
                    saved.extend(value if isinstance(value, list) else [value])
            print(f'Updated {apply_transaction(saved, args.journal)} selected file(s).')
        else:
            print(f'Restored {recover_transaction(args.journal)} selected file(s).')
    except (ValueError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f'Refused: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
