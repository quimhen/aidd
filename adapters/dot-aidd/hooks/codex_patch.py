"""Strict path extraction for documented apply_patch text, not a host hook."""

import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath


@dataclass(frozen=True)
class PatchTarget:
    operation: str
    source: str
    destination: str | None
    original: str | None
    prospective: str


_MAX_FILE = 2 * 1024 * 1024
_MAX_TARGETS = 100


def _checked_path(root, name):
    """Refuse aliases, escapes, non-portable names and unresolved parents."""
    if (not name or not name.isascii() or name != name.strip() or '\\' in name
            or PureWindowsPath(name).drive or PureWindowsPath(name).root
            or PurePosixPath(name).is_absolute() or ':' in name
            or any(x in ('', '.', '..') or x.endswith(('.', ' ')) for x in name.split('/'))):
        raise ValueError('unsupported target path')
    current = root
    for part in name.split('/'):
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            if current != root / name:
                raise ValueError('missing parent directory')
            break
        except OSError as exc:
            raise ValueError('cannot inspect path') from exc
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('links and reparse points are unsupported')
    try:
        current.resolve(strict=False).relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError('target escapes root') from exc
    return current


def project_patch(command: str, cwd: str) -> list[PatchTarget]:
    """Project a strict native-patch subset, without writing or authorizing it.

    Exact ASCII/LF, a single unique contiguous hunk, no moves/deletes/aliases.
    A projection is not a guarantee against mutation after this function returns.
    """
    if (not isinstance(command, str) or len(command) > 4 * 1024 * 1024 or not command.isascii()
            or any(ord(c) < 32 and c not in '\n\t' for c in command)):
        raise ValueError('unsupported patch encoding')
    try:
        root = Path(cwd).resolve(strict=True)
        if not root.is_dir():
            raise ValueError('cwd is not a directory')
    except (OSError, RuntimeError, TypeError) as exc:
        raise ValueError('invalid cwd') from exc
    lines = command.splitlines()
    if len(lines) < 3 or lines[0] != '*** Begin Patch' or lines[-1] != '*** End Patch':
        raise ValueError('invalid patch boundaries')
    out, seen, i = [], set(), 1
    while i < len(lines) - 1:
        header = lines[i]
        if header.startswith('*** Add File: '):
            operation, name = 'add', header[len('*** Add File: '):]
        elif header.startswith('*** Update File: '):
            operation, name = 'update', header[len('*** Update File: '):]
        else:
            raise ValueError('unsupported operation')
        path = _checked_path(root, name)
        key = os.path.normcase(str(path)).casefold()
        if key in seen or len(out) >= _MAX_TARGETS:
            raise ValueError('duplicate target or target limit exceeded')
        seen.add(key)
        i += 1
        if operation == 'add':
            if path.exists():
                raise ValueError('add target already exists')
            added = []
            while i < len(lines) - 1 and not lines[i].startswith('*** '):
                if not lines[i].startswith('+'):
                    raise ValueError('invalid add line')
                added.append(lines[i][1:])
                i += 1
            prospective = ''.join(x + '\n' for x in added)
            if len(prospective) > _MAX_FILE:
                raise ValueError('file too large')
            out.append(PatchTarget(operation, name, None, None, prospective))
            continue
        if i >= len(lines) - 1 or lines[i] != '@@':
            raise ValueError('update requires one unlabeled hunk')
        i += 1
        before, after = [], []
        while i < len(lines) - 1 and not lines[i].startswith('*** '):
            line = lines[i]
            if not line or line[0] not in ' +-':
                raise ValueError('unsupported hunk line')
            if line[0] != '+':
                before.append(line[1:])
            if line[0] != '-':
                after.append(line[1:])
            i += 1
        if not before:
            raise ValueError('empty hunk preimage')
        try:
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > _MAX_FILE:
                raise ValueError('unsupported original file')
            raw = path.read_bytes()
            if raw != path.read_bytes():
                raise ValueError('file changed during projection')
            if not raw or len(raw) > _MAX_FILE or b'\r' in raw or b'\x00' in raw or not raw.endswith(b'\n'):
                raise ValueError('unsupported original encoding')
            original = raw.decode('ascii')
        except (OSError, UnicodeDecodeError) as exc:
            raise ValueError('unreadable original file') from exc
        source_lines = original[:-1].split('\n')
        positions = [n for n in range(len(source_lines) - len(before) + 1)
                     if source_lines[n:n + len(before)] == before]
        if len(positions) != 1:
            raise ValueError('hunk must match exactly once')
        n = positions[0]
        projected = source_lines[:n] + after + source_lines[n + len(before):]
        prospective = ''.join(x + '\n' for x in projected)
        if len(prospective) > _MAX_FILE:
            raise ValueError('file too large')
        out.append(PatchTarget(operation, name, None, original, prospective))
    if not out:
        raise ValueError('empty patch')
    return out


def normalize_codex_patch(event):
    if not isinstance(event, dict):
        raise ValueError('event must be an object')
    args = event.get('tool_input')
    text = args.get('command') if isinstance(args, dict) else None
    if not isinstance(text, str) or not text or '\x00' in text:
        raise ValueError('missing or invalid patch command')
    lines = text.splitlines()
    if len(lines) < 3 or lines[0] != '*** Begin Patch' or lines[-1] != '*** End Patch':
        raise ValueError('patch boundaries missing')
    paths, seen = [], set()
    current = None
    moved = False
    for line in lines[1:-1]:
        headers = ('*** Add File: ', '*** Update File: ', '*** Delete File: ')
        if line.startswith(headers):
            prefix = next(h for h in headers if line.startswith(h))
            path = line[len(prefix):]
            if not path or path != path.strip() or path in seen:
                raise ValueError('invalid or duplicate patch path')
            seen.add(path)
            paths.append(path)
            current = prefix
            moved = False
        elif line.startswith('*** Move to: '):
            path = line[len('*** Move to: '):]
            if current != '*** Update File: ' or moved or not path or path != path.strip() or path in seen:
                raise ValueError('invalid or duplicate move destination')
            seen.add(path)
            paths.append(path)
            moved = True
        elif line.startswith('*** ') and line != '*** End of File':
            raise ValueError('unknown patch marker')
        elif current is None:
            raise ValueError('content before file header')
    if not paths:
        raise ValueError('empty patch')
    result = {'tool_name': 'MultiEdit',
              'tool_input': {'file_path': paths[0], 'edits': [{'file_path': p} for p in paths]}}
    for key in ('cwd', 'session_id'):
        if key in event:
            result[key] = event[key]
    return result
