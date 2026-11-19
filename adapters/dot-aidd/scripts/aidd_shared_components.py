"""Conservative, exact evidence for shared TS/JS components outside named shared folders."""
import json
import re
from pathlib import Path, PurePosixPath, PureWindowsPath

COMP = re.compile(r'COMP-\d+(?:-F\d+)?\Z')
SCREEN = re.compile(r'\bSCREEN-\d+(?:-F\d+)?\b')
EXTENSIONS = ('.tsx', '.ts', '.jsx', '.js')


def project_file(root, value):
    """No suffix matching, aliases, normalization escapes or noncanonical spelling."""
    raw = value.strip().strip('`')
    win, posix = PureWindowsPath(raw), PurePosixPath(raw)
    if (not raw or '\\' in raw or win.drive or win.root or posix.is_absolute()
            or any(part in ('', '.', '..') for part in raw.split('/'))):
        return None
    try:
        path = (root / raw).resolve(strict=True)
        if path.relative_to(root).as_posix() != raw or not path.is_file():
            return None
        return path
    except (OSError, ValueError):
        return None


def index_rows(indexes):
    rows = []
    for path in indexes:
        text = path.read_text(encoding='utf-8')
        active = False
        for line in text.splitlines():
            if not line.strip().startswith('|'):
                active = False
                continue
            cells = [cell.strip().strip('`') for cell in line.strip().strip('|').split('|')]
            if len(cells) == 7 and cells[:3] == ['COMP-nnn', 'Name', 'File']:
                active = True
                continue
            if active and len(cells) == 7 and COMP.fullmatch(cells[0]):
                rows.append(cells)
    return rows


def _masked(text):
    return ''.join('\n' if char == '\n' else ' ' for char in text)


def _regex_start(text, offset):
    prefix = text[:offset].rstrip()
    line = text[text.rfind('\n', 0, offset) + 1:offset].strip()
    if not prefix or not line:
        return True
    if prefix[-1] in '=(:,[!&|?{};+-*%^~<>)':
        return True
    token = re.search(r'([A-Za-z_$][\w$]*)$', prefix)
    return bool(token and token.group(1) in {
        'return', 'throw', 'yield', 'case', 'else', 'do', 'typeof', 'void', 'delete', 'in', 'of'})


def _regex_end(text, start):
    cursor, in_class = start + 1, False
    while cursor < len(text) and text[cursor] not in '\r\n':
        char = text[cursor]
        if char == '\\':
            cursor += 2
            continue
        if char == '[':
            if in_class:
                return None  # Nested /v sets and ambiguous classes are not guessed.
            in_class = True
        elif char == ']':
            in_class = False
        elif char == '/' and not in_class:
            cursor += 1
            while cursor < len(text) and text[cursor].isalpha():
                cursor += 1
            return cursor
        cursor += 1
    return None


def code_text(text, mask_strings=False):
    """Offset-preserving lexical masks; quoted modules survive only in the import view.

    Strings (including escaped physical newlines), templates, comments and regular-expression
    literals cannot provide import/export/JSX evidence. Ambiguous slash syntax is conservative;
    this is not a complete JS parser.
    """
    output, i = [], 0
    while i < len(text):
        if text.startswith('//', i):
            end = text.find('\n', i)
            end = len(text) if end < 0 else end
            output.append(' ' * (end - i)); i = end
        elif text.startswith('/*', i):
            end = text.find('*/', i + 2)
            end = len(text) if end < 0 else end + 2
            output.append(_masked(text[i:end])); i = end
        elif text[i] in "'\"`":
            quote, start = text[i], i
            i += 1
            while i < len(text):
                if text[i] == '\\':
                    i += 2
                elif text[i] == quote:
                    i += 1
                    break
                else:
                    i += 1
            chunk = text[start:i]
            output.append(_masked(chunk) if quote == '`' or mask_strings else chunk)
        elif (text[i] == '/' and not (i and text[i - 1] == '<')
              and text[i:i + 2] != '/>' and _regex_start(text, i)):
            end = _regex_end(text, i)
            if end is not None:
                output.append(_masked(text[i:end])); i = end
            else:
                end = text.find('\n', i)
                end = len(text) if end < 0 else end
                output.append(_masked(text[i:end])); i = end
        else:
            output.append(text[i]); i += 1
    return ''.join(output)


def nearest_tsconfig(consumer, root):
    for parent in consumer.parents:
        if parent != root and root not in parent.parents:
            break
        candidate = parent / 'tsconfig.json'
        if candidate.is_file():
            candidate.resolve(strict=True).relative_to(root)
            return candidate
        if parent == root:
            break
    return None


def resolve_module(module, consumer, root):
    if module.startswith('.'):
        candidate = consumer.parent / module
    else:
        config_path = nearest_tsconfig(consumer, root)
        if config_path is None:
            return None
        config = json.loads(config_path.read_text(encoding='utf-8'))
        if 'extends' in config:  # Do not guess inherited aliases.
            return None
        options = config.get('compilerOptions', {})
        paths = options.get('paths', {})
        matches = []
        for pattern, values in paths.items():
            if pattern.count('*') > 1:
                continue
            if '*' in pattern:
                prefix, suffix = pattern.split('*')
                if not module.startswith(prefix) or not module.endswith(suffix) or len(module) < len(prefix) + len(suffix):
                    continue
                capture = module[len(prefix):len(module)-len(suffix) if suffix else None]
                rank = (0, len(prefix), len(suffix))
            elif module == pattern:
                capture, rank = '', (1, len(pattern), 0)
            else:
                continue
            matches.append((rank, capture, values))
        if not matches:
            return None
        best = max(row[0] for row in matches)
        winners = [row for row in matches if row[0] == best]
        if len(winners) != 1:
            return None
        _, capture, values = winners[0]
        if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], str) or values[0].count('*') > 1:
            return None
        base = options.get('baseUrl', '.')
        if not isinstance(base, str):
            return None
        candidate = config_path.parent / base / values[0].replace('*', capture)
    possibilities = [candidate] if candidate.suffix in EXTENSIONS else [
        *[Path(str(candidate) + suffix) for suffix in EXTENSIONS],
        *[candidate / ('index' + suffix) for suffix in EXTENSIONS]]
    found = []
    for path in possibilities:
        if path.is_file():
            resolved = path.resolve(strict=True)
            resolved.relative_to(root)
            found.append(resolved)
    return found[0] if len(set(found)) == 1 else None


def production_consumer(path):
    parts = [part.lower() for part in path.parts]
    return (path.suffix in EXTENSIONS and not any(part in ('tests', '__tests__', 'e2e', 'fixtures', 'test-results',
                'docs', 'scratch', 'scratchpad', 'node_modules', 'dist', 'build', 'prototype') for part in parts)
            and not re.search(r'\.(?:test|spec|stories|story)\.', path.name, re.I))


def without_strings(text):
    return code_text(text, mask_strings=True)


def export_kinds(target, name):
    text = without_strings(code_text(target.read_text(encoding='utf-8')))
    symbol = re.escape(name) + r'\b'
    named = bool(re.search(r'^\s*export\s+(?:function|const|class)\s+' + symbol, text, re.M))
    default = bool(re.search(r'^\s*export\s+default\s+(?:function|class)\s+' + symbol, text, re.M))
    # An explicit default export of the same declared symbol is also unambiguous.
    if re.search(r'^\s*export\s+default\s+' + symbol + r'\s*;', text, re.M):
        default = bool(re.search(r'\b(?:function|const|class)\s+' + symbol, text))
    return named, default


def imports_and_uses(consumer, target, name, root):
    text = code_text(consumer.read_text(encoding='utf-8'))
    jsx = without_strings(text)
    named_export, default_export = export_kinds(target, name)
    pattern = r'^\s*import\s+(?!type\b)([^;]*?)\s+from\s*[\'\"]([^\'\"]+)[\'\"]'
    for match in re.finditer(pattern, text, re.M):
        start = match.start() + len(match.group()) - len(match.group().lstrip())
        if jsx[start:start + 6] != 'import':
            continue  # An import-shaped string is not an import declaration.
        if resolve_module(match.group(2), consumer, root) != target:
            continue
        binding = match.group(1).strip()
        local = None
        if default_export and re.fullmatch(r'[A-Za-z_$][\w$]*', binding):
            local = binding
        else:
            named = re.fullmatch(r'\{(.*)\}', binding, re.S)
            if named and named_export:
                for part in named.group(1).split(','):
                    item = re.fullmatch(re.escape(name) + r'(?:\s+as\s+([A-Za-z_$][\w$]*))?', part.strip())
                    if item:
                        local = item.group(1) or name
        if local and re.search(r'<' + re.escape(local) + r'(?=[\s/>])', jsx):
            return True
    return False


def declared_screens(base, directory):
    screens = set()
    for folder in {base, directory}:
        for name in ('spec.md', 'plan.md', 'mockup-audit.md'):
            path = folder / name
            if path.is_file():
                screens.update(SCREEN.findall(path.read_text(encoding='utf-8')))
    return screens


def registered_shared(code, raw_path, indexes, root, screens):
    """Evidence is sufficient only for this exact COMP/file, never for a directory."""
    try:
        root = Path(root).resolve(strict=True)
        allowed = {root / 'components-index.md', root / 'design-system' / 'components-index.md'}
        registries = []
        for index in indexes:
            resolved = index.resolve(strict=True)
            resolved.relative_to(root)
            if resolved in allowed:
                registries.append(resolved)
        rows = index_rows(registries)
        matching = [row for row in rows if row[0] == code]
        if len(matching) != 1:
            return False
        row = matching[0]
        target, claimed = project_file(root, raw_path), project_file(root, row[2])
        if target is None or target != claimed or not re.fullmatch(r'[A-Za-z_$][\w$]*', row[1]):
            return False
        # Conflicting identifiers claiming the same exact source are ambiguous.
        if any(other[0] != code and project_file(root, other[2]) == target for other in rows):
            return False
        used = set(SCREEN.findall(row[4]))
        if len(used) < 2 or not used.issubset(screens):
            return False
        if not any(export_kinds(target, row[1])):
            return False
        for name in row[5].split(','):
            consumer = project_file(root, name)
            if consumer is not None and production_consumer(consumer) and imports_and_uses(consumer, target, row[1], root):
                return True
        return False
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False


def evidence_paths(indexes, root, base, directory):
    """Observe exactly the files/configs this exception can inspect, including its screen declarations."""
    result = set(indexes)
    for folder in {base, directory}:
        result.update(folder / name for name in ('spec.md', 'plan.md', 'mockup-audit.md'))
    for row in index_rows(indexes):
        for name in [row[2], *row[5].split(',')]:
            path = project_file(root, name)
            if path is not None:
                result.add(path)
                config = nearest_tsconfig(path, root)
                if config is not None:
                    result.add(config)
    return sorted(result)
