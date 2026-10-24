#!/usr/bin/env python3
"""aidd_doctor.py -- check that AIDD is correctly installed for a host (Gemini CLI / OpenCode / Antigravity).

Usage: python aidd_doctor.py [--host gemini|opencode|antigravity] [--root DIR] [--json]

One line per check: `PASS|FAIL|WARN <id> <message> -> <exact fix>`.
Exit 1 when any of D1-D5 fails, else 0. Stdlib only. Read-only on the project (D5 uses a temp fixture).

aidd:FR-909 aidd:FR-911
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

CORE_MAX_BYTES = 12288
IGNORED_PARTS = {'__pycache__', 'memory', 'evidence'}
IGNORED_NAMES = {'gate_spec', 'active_spec'}
HOSTS = ('gemini', 'opencode', 'antigravity')
BLOCKING_IDS = ('D1', 'D2', 'D3', 'D4', 'D5', 'D8', 'D9')
PLUGIN_SHAPE_KEYS = ('id', 'server', 'setup')
GITHOOK_NAMES = ('pre-commit', 'pre-push')
GUARD_CALLS = ('aidd guard', 'aidd_guard.py')
NEXT_LINE_NEEDLE = 'aidd next'
OPENCODE2_GATE_LINE = 'write gate: none on opencode 2.x, enforcement: git guard'
PLUGIN_ENTRY = '.opencode/plugins/aidd.js'
GEMINI_MATCHER = 'write_file|replace|run_shell_command'
RULE_MAX_BYTES = 24000
AGY_COMMANDS = {'PreToolUse': 'python ../.aidd/hooks/host_adapter.py antigravity pre',
                'PostToolUse': 'python ../.aidd/hooks/host_adapter.py antigravity post'}
# (installed path under the project, shipped template under adapters/antigravity/)
AGY_FILES = (('.agents/skills/aidd/SKILL.md', 'skills/aidd/SKILL.md'),
             ('.agents/rules/aidd.md', 'rules/aidd.md'))


def repo_root() -> Path:
    """skill/scripts/aidd_doctor.py -> repo root (same layout aidd/cli.py assumes). When the scripts come from the
    INSTALLED skill (~/.claude/skills/aidd/scripts) there is no sibling adapters/: use the copy bundled in the aidd
    package (aidd/_data), as install_host.py does, so `aidd doctor` can compare against the shipped files."""
    here = Path(__file__).resolve()
    candidates = [here.parent.parent.parent]
    try:
        import importlib.util
        spec = importlib.util.find_spec("aidd")
        if spec and spec.origin:
            candidates.append(Path(spec.origin).parent / "_data")
            candidates.append(Path(spec.origin).parent.parent)  # aidd imported from a checkout (PYTHONPATH)
    except Exception:
        pass
    for c in candidates:
        if (c / "adapters").is_dir():
            return c
    return candidates[0]


def result(check_id, status, message, fix=''):
    return {'id': check_id, 'status': status, 'message': message, 'fix': fix}


def short_sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()[:10]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return None


def is_ignored(rel: Path) -> bool:
    return any(p in IGNORED_PARTS for p in rel.parts) or rel.name in IGNORED_NAMES


def is_link(path) -> bool:
    """True for a symlink or a junction. Windows: the reparse TAG decides (the plain reparse attribute is also
    set by OneDrive placeholders); elsewhere os.path.islink."""
    path = str(path)
    if os.name == 'nt':
        try:
            tag = getattr(os.lstat(path), 'st_reparse_tag', 0)
        except OSError:
            return False
        return tag in (stat.IO_REPARSE_TAG_SYMLINK, stat.IO_REPARSE_TAG_MOUNT_POINT)
    return os.path.islink(path)


def agy_entry(data):
    """The `aidd` entry of a parsed .agents/hooks.json (top level, or under a `hooks` object), or None."""
    if not isinstance(data, dict):
        return None
    entry = data.get('aidd')
    if entry is None and isinstance(data.get('hooks'), dict):
        entry = data['hooks'].get('aidd')
    return entry if isinstance(entry, dict) else None


def shipped_files(shipped: Path):
    for p in sorted(shipped.rglob('*')):
        if p.is_file() and not is_ignored(p.relative_to(shipped)):
            yield p.relative_to(shipped)


class Doctor:
    def __init__(self, root: Path):
        self.root = root
        self.aidd = root / '.aidd'
        self.shipped = repo_root() / 'adapters' / 'dot-aidd'

    # ---- D1 ----
    def check_d1(self, host):
        fix = f'aidd install --host {host}'
        if not self.aidd.is_dir():
            return result('D1', 'FAIL', '.aidd/ not found in the project', fix)
        if not self.shipped.is_dir():
            return result('D1', 'WARN', f'shipped adapters/dot-aidd not found at {self.shipped}; cannot compare', '')
        diffs = []
        total = 0
        for rel in shipped_files(self.shipped):
            target = self.aidd / rel
            if not target.is_file():
                total += 1
                if len(diffs) < 5:
                    diffs.append(f'missing {rel.as_posix()}')
                continue
            try:
                same = target.read_bytes() == (self.shipped / rel).read_bytes()
            except OSError:
                same = False
            if not same:
                total += 1
                if len(diffs) < 5:
                    diffs.append(f'differs {rel.as_posix()}')
        if host == 'antigravity':
            total += self._d1_antigravity(diffs)
        if total:
            more = f' (+{total - len(diffs)} more)' if total > len(diffs) else ''
            return result('D1', 'FAIL', f'{total} file(s) differ from shipped: ' + '; '.join(diffs) + more,
                          f'aidd install --host {host} --force')
        return result('D1', 'PASS', '.aidd/ complete and equal to the shipped adapters/dot-aidd')

    def _d1_antigravity(self, diffs):
        """Compare the two antigravity templates with the installed copies; returns the number of differences."""
        base = repo_root() / 'adapters' / 'antigravity'
        count = 0
        for installed, tpl in AGY_FILES:
            target = self.root / installed
            src = base / tpl
            if not target.is_file():
                problem = f'missing {installed}'
            elif not src.is_file():
                continue  # shipped template not found: cannot compare
            else:
                try:
                    same = target.read_bytes() == src.read_bytes()
                except OSError:
                    same = False
                if same:
                    continue
                problem = f'differs {installed}'
            count += 1
            if len(diffs) < 5:
                diffs.append(problem)
        return count

    # ---- D2 ----
    def check_d2(self, host):
        core = self.aidd / 'CORE.md'
        fix = f'aidd install --host {host}'
        if not core.is_file():
            return result('D2', 'FAIL', '.aidd/CORE.md missing', fix)
        size = core.stat().st_size
        if size >= CORE_MAX_BYTES:
            return result('D2', 'FAIL', f'.aidd/CORE.md is {size} bytes (limit {CORE_MAX_BYTES})',
                          f'aidd install --host {host} --force')
        if host == 'antigravity':
            rule = self.root / '.agents' / 'rules' / 'aidd.md'
            if not rule.is_file():
                return result('D2', 'FAIL', '.agents/rules/aidd.md missing', fix)
            rsize = rule.stat().st_size
            if rsize >= RULE_MAX_BYTES:
                return result('D2', 'FAIL', f'.agents/rules/aidd.md is {rsize} bytes (limit {RULE_MAX_BYTES})',
                              f'aidd install --host {host} --force')
            return result('D2', 'PASS', f'.aidd/CORE.md {size} bytes (< {CORE_MAX_BYTES}), '
                          f'.agents/rules/aidd.md {rsize} bytes (< {RULE_MAX_BYTES})')
        return result('D2', 'PASS', f'.aidd/CORE.md present, {size} bytes (< {CORE_MAX_BYTES})')

    # ---- D3 ----
    def check_d3(self, host):
        fix = f'aidd install --host {host}'
        if host == 'antigravity':
            return self._d3_antigravity(fix)
        if host == 'gemini':
            path = self.root / 'GEMINI.md'
            needle = '@.aidd/CORE.md'
        else:
            path = self.root / '.opencode' / 'skills' / 'aidd' / 'SKILL.md'
            needle = '.aidd/CORE.md'
        if not path.is_file():
            return result('D3', 'FAIL', f'{path.relative_to(self.root).as_posix()} missing', fix)
        text = read_text(path)
        rel = path.relative_to(self.root).as_posix()
        if needle not in text:
            if host == 'gemini':
                own_fix = ('add the line `@.aidd/CORE.md` to GEMINI.md '
                           '(do not use --force: it would overwrite your own GEMINI.md)')
            else:
                own_fix = ('add a pointer to `.aidd/CORE.md` in .opencode/skills/aidd/SKILL.md '
                           '(do not use --force: it would overwrite your own SKILL.md)')
            return result('D3', 'FAIL', f'{rel} does not reference {needle}', own_fix)
        for line in text.splitlines():
            ll = line.lower()
            if 'aidd.md' in ll and 'in full' in ll and 'core.md' not in ll:
                return result('D3', 'FAIL', f'{rel} tells the agent to read AIDD.md "in full"', fix + ' --force')
        return result('D3', 'PASS', f'{rel} points to .aidd/CORE.md')

    def _d3_antigravity(self, fix):
        skill_dir = self.root / '.agents' / 'skills' / 'aidd'
        if is_link(skill_dir):
            return result('D3', 'FAIL', '.agents/skills/aidd is a link (symlink or junction): the AIDD files would '
                          'be written through it', 'aidd install --host antigravity --force '
                          '(replaces only the link, never its target)')
        for rel in ('.agents/skills/aidd/SKILL.md', '.agents/rules/aidd.md'):
            path = self.root / rel
            if not path.is_file():
                return result('D3', 'FAIL', f'{rel} missing', fix)
            if '.aidd/CORE.md' not in read_text(path).replace('\\', '/'):
                return result('D3', 'FAIL', f'{rel} does not name .aidd/CORE.md', fix + ' --force')
        return result('D3', 'PASS', '.agents/skills/aidd/SKILL.md and .agents/rules/aidd.md name .aidd/CORE.md; '
                      'the skill folder is not a link')

    # ---- D4 ----
    def check_d4(self, host):
        fix = f'aidd install --host {host}'
        if host == 'antigravity':
            return self._d4_antigravity(fix)
        if host == 'gemini':
            return self._d4_gemini(fix)
        return self._d4_opencode(fix)

    def _d4_gemini(self, fix):
        path = self.root / '.gemini' / 'settings.json'
        data = load_json(path)
        if data is None:
            return result('D4', 'FAIL', '.gemini/settings.json missing or not valid JSON', fix)
        hooks = data.get('hooks') if isinstance(data, dict) else None
        if not isinstance(hooks, dict):
            return result('D4', 'FAIL', '.gemini/settings.json has no "hooks" object', fix)
        found = {}
        for event, name in (('BeforeTool', 'aidd-gate'), ('AfterTool', 'aidd-record')):
            entries = hooks.get(event)
            hit = self._find_named(entries, name)
            if hit is None:
                return result('D4', 'FAIL', f'hooks.{event} has no entry named "{name}" running '
                              '.aidd/hooks/host_adapter.py', fix)
            found[event], matcher = hit
            if matcher != GEMINI_MATCHER:
                return result('D4', 'FAIL', f'hooks.{event} group of "{name}" has matcher {matcher!r}, '
                              f'expected exactly {GEMINI_MATCHER!r} (altered matcher)',
                              'aidd install --host gemini --force')
        sig = json.dumps(found, sort_keys=True).encode('utf-8')
        return result('D4', 'PASS', f'hooks.BeforeTool aidd-gate and hooks.AfterTool aidd-record registered '
                      f'(sha1 {short_sha1(sig)})')

    def _d4_antigravity(self, fix):
        force = fix + ' --force'
        data = load_json(self.root / '.agents' / 'hooks.json')
        if data is None:
            return result('D4', 'FAIL', '.agents/hooks.json missing or not valid JSON', fix)
        entry = agy_entry(data)
        if entry is None:
            return result('D4', 'FAIL', '.agents/hooks.json has no "aidd" entry', fix)
        for event, command in AGY_COMMANDS.items():
            groups = entry.get(event)
            if not isinstance(groups, list) or not groups:
                return result('D4', 'FAIL', f'aidd entry has no {event} group', force)
            hit = None
            for group in groups:
                inner = group.get('hooks') if isinstance(group, dict) else None
                if isinstance(inner, list) and any(isinstance(h, dict) and h.get('command') == command
                                                   for h in inner):
                    hit = group
                    break
            if hit is None:
                seen = [h.get('command') for g in groups if isinstance(g, dict) and isinstance(g.get('hooks'), list)
                        for h in g['hooks'] if isinstance(h, dict)]
                return result('D4', 'FAIL', f'aidd {event} command differs: found {seen!r}, expected exactly '
                              f'{command!r}', force)
            if hit.get('matcher') != '*':
                return result('D4', 'FAIL', f'aidd {event} group has matcher {hit.get("matcher")!r}, '
                              "expected exactly '*' (altered matcher)", force)
        sig = json.dumps(entry, sort_keys=True).encode('utf-8')
        return result('D4', 'PASS', f'aidd PreToolUse and PostToolUse registered with matcher * and the exact '
                      f'commands (sha1 {short_sha1(sig)})')

    def _find_named(self, entries, name):
        """Find a named hook whose command is the adapter; return (entry, matcher of its group) or None."""
        stack = [(e, None) for e in entries] if isinstance(entries, list) else []
        while stack:
            item, matcher = stack.pop()
            if not isinstance(item, dict):
                continue
            nested = item.get('hooks')
            if isinstance(nested, list):
                stack.extend((n, item.get('matcher')) for n in nested)
            command = str(item.get('command', '')).replace('\\', '/')
            if item.get('name') == name and '.aidd/hooks/host_adapter.py' in command:
                return item, (matcher if matcher is not None else item.get('matcher'))
        return None

    def _d4_opencode(self, fix):
        # The "plugin" entry in opencode.json is optional (opencode 2.x auto-loads .opencode/plugins/).
        plugin = self.root / PLUGIN_ENTRY
        if not plugin.is_file():
            return result('D4', 'FAIL', f'{PLUGIN_ENTRY} missing', fix)
        try:
            data = plugin.read_bytes()
        except OSError as exc:
            return result('D4', 'FAIL', f'{PLUGIN_ENTRY} unreadable: {exc}', fix)
        text = data.decode('utf-8', errors='replace')
        if 'export default' not in text or not all(key in text for key in PLUGIN_SHAPE_KEYS):
            return result('D4', 'FAIL', f'{PLUGIN_ENTRY} has no default export with {{id, server, setup}}',
                          fix + ' --force')
        shipped = repo_root() / 'adapters' / 'opencode' / 'plugins' / 'aidd.js'
        if not shipped.is_file():
            shipped = self.shipped.parent / 'opencode' / 'plugins' / 'aidd.js'
        try:
            differs = shipped.is_file() and shipped.read_bytes() != data
        except OSError:
            differs = False
        if differs:
            return result('D4', 'FAIL', f'{PLUGIN_ENTRY} differs from the shipped plugin (sha1 {short_sha1(data)})',
                          fix + ' --force')
        note = '' if shipped.is_file() else ' (shipped copy not found, content not compared)'
        cfg = load_json(self.root / '.opencode' / 'opencode.json')
        plugins = cfg.get('plugin') if isinstance(cfg, dict) else None
        norm = []
        for p in (plugins if isinstance(plugins, list) else []):
            p = str(p).replace('\\', '/')
            norm.append(p[2:] if p.startswith('./') else p)
        where = 'registered in opencode.json' if PLUGIN_ENTRY in norm else 'not listed in opencode.json (optional)'
        return result('D4', 'PASS', f'plugin {where} and file unaltered (sha1 {short_sha1(data)}){note}')

    # ---- D5 ----
    def check_d5(self, host):
        fix = f'aidd install --host {host}'
        adapter = self.aidd / 'hooks' / 'host_adapter.py'
        if not adapter.is_file():
            return result('D5', 'FAIL', '.aidd/hooks/host_adapter.py missing', fix)
        py = shutil.which('python')
        if py is None:
            return result('D5', 'FAIL', 'python is not on PATH: the registered hook and plugin call bare `python` '
                          'and would silently do nothing',
                          'install Python 3 and make `python` resolvable on PATH '
                          '(on Linux/macOS create a `python` alias for python3)')
        if host == 'antigravity':
            return self._d5_antigravity(fix, py)
        real_md = self.aidd / 'AIDD.md'
        tmp = Path(tempfile.mkdtemp(prefix='aidd-doctor-'))
        try:
            (tmp / '.aidd').mkdir()
            if real_md.is_file():
                shutil.copyfile(real_md, tmp / '.aidd' / 'AIDD.md')
            else:
                (tmp / '.aidd' / 'AIDD.md').write_text('# AIDD (doctor fixture stub)\n', encoding='utf-8')
            spec_dir = tmp / 'specs' / '001-x'
            spec_dir.mkdir(parents=True)
            (spec_dir / 'spec.md').write_text('# Spec 001-x\n', encoding='utf-8')
            (spec_dir / 'plan.md').write_text('# Plan\n', encoding='utf-8')
            (spec_dir / 'tasks.md').write_text('# Tasks\n\nApproved: PENDING\n', encoding='utf-8')
            target = tmp / 'src' / 'app.py'
            target.parent.mkdir()
            content = 'print("doctor")\n'
            if host == 'gemini':
                event = {'session_id': 'aidd-doctor', 'cwd': str(tmp), 'hook_event_name': 'BeforeTool',
                         'tool_name': 'write_file', 'tool_input': {'file_path': str(target), 'content': content}}
            else:
                event = {'sessionID': 'aidd-doctor', 'cwd': str(tmp), 'tool': 'write',
                         'args': {'filePath': str(target), 'content': content}}
            # A spec is "open" only after a recorded edit of its plan.md / tasks.md, so replay those two
            # edits through the adapter's own `post` phase first (as a real session would produce them).
            for name in ('plan.md', 'tasks.md'):
                path = str(spec_dir / name)
                if host == 'gemini':
                    spec_evt = {'session_id': 'aidd-doctor', 'cwd': str(tmp), 'hook_event_name': 'AfterTool',
                                'tool_name': 'write_file', 'tool_input': {'file_path': path, 'content': 'x'}}
                else:
                    spec_evt = {'sessionID': 'aidd-doctor', 'cwd': str(tmp), 'tool': 'write',
                                'args': {'filePath': path, 'content': 'x'}}
                try:
                    subprocess.run([py, str(adapter), host, 'post'],
                                   input=json.dumps(spec_evt).encode('utf-8'), cwd=str(tmp),
                                   capture_output=True, timeout=30)
                except (OSError, subprocess.TimeoutExpired) as exc:
                    return result('D5', 'FAIL', f'gate dry-run could not record the fixture spec: {exc}', fix)
            try:
                proc = subprocess.run([py, str(adapter), host, 'pre'],
                                      input=json.dumps(event).encode('utf-8'), cwd=str(tmp),
                                      capture_output=True, timeout=30)
            except (OSError, subprocess.TimeoutExpired) as exc:
                return result('D5', 'FAIL', f'gate dry-run could not run: {exc}', fix)
            if proc.returncode == 2:
                return result('D5', 'PASS', 'gate dry-run blocked an unapproved code write (exit 2)')
            err = proc.stderr.decode('utf-8', errors='replace').strip().replace('\n', ' | ')[:400]
            return result('D5', 'FAIL', f'gate dry-run exited {proc.returncode}, expected 2; stderr: {err or "(empty)"}',
                          fix + ' --force')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _d5_antigravity(self, fix, py):
        """Run the REGISTERED hook commands from the hook cwd (<tmp>/.agents) on an Antigravity-shaped payload."""
        force = fix + ' --force'
        tmp = Path(tempfile.mkdtemp(prefix='aidd-doctor-'))
        try:
            shutil.copytree(self.aidd / 'hooks', tmp / '.aidd' / 'hooks',
                            ignore=shutil.ignore_patterns('__pycache__'))
            if (self.aidd / 'scripts').is_dir():
                shutil.copytree(self.aidd / 'scripts', tmp / '.aidd' / 'scripts',
                                ignore=shutil.ignore_patterns('__pycache__'))
            real_md = self.aidd / 'AIDD.md'
            if real_md.is_file():
                shutil.copyfile(real_md, tmp / '.aidd' / 'AIDD.md')
            else:
                (tmp / '.aidd' / 'AIDD.md').write_text('# AIDD (doctor fixture stub)\n', encoding='utf-8')
            spec_dir = tmp / 'specs' / '001-x'
            spec_dir.mkdir(parents=True)
            (spec_dir / 'spec.md').write_text('# Spec 001-x\n', encoding='utf-8')
            (spec_dir / 'plan.md').write_text('# Plan\n', encoding='utf-8')
            (spec_dir / 'tasks.md').write_text('# Tasks\n\nApproved: PENDING\n', encoding='utf-8')
            target = tmp / 'src' / 'app.py'
            target.parent.mkdir()
            hook_cwd = tmp / '.agents'
            hook_cwd.mkdir()

            def payload(path, content):
                return {'toolCall': {'name': 'write_to_file', 'args': {'TargetFile': str(path),
                                                                         'CodeContent': content}},
                        'conversationId': 'aidd-doctor', 'workspacePaths': [str(tmp)]}

            def run(phase, evt):
                argv = AGY_COMMANDS['PreToolUse' if phase == 'pre' else 'PostToolUse'].split()
                argv[0] = py
                return subprocess.run(argv, input=json.dumps(evt).encode('utf-8'), cwd=str(hook_cwd),
                                      capture_output=True, timeout=30)

            for name in ('plan.md', 'tasks.md'):
                try:
                    run('post', payload(spec_dir / name, 'x'))
                except (OSError, subprocess.TimeoutExpired) as exc:
                    return result('D5', 'FAIL', f'gate dry-run could not record the fixture spec: {exc}', fix)
            try:
                proc = run('pre', payload(target, 'print("doctor")\n'))
            except (OSError, subprocess.TimeoutExpired) as exc:
                return result('D5', 'FAIL', f'gate dry-run could not run: {exc}', fix)
            out = proc.stdout.decode('utf-8', errors='replace').strip()
            try:
                answer = json.loads(out)
            except ValueError:
                answer = None
            if proc.returncode == 0 and isinstance(answer, dict) and answer.get('decision') == 'deny':
                return result('D5', 'PASS', 'gate dry-run denied an unapproved code write (exit 0, decision deny) '
                              'running the registered command from .agents')
            err = proc.stderr.decode('utf-8', errors='replace').strip().replace('\n', ' | ')[:400]
            return result('D5', 'FAIL', f'gate dry-run exited {proc.returncode} with stdout {out[:200]!r}, expected '
                          f'exit 0 and JSON decision "deny"; stderr: {err or "(empty)"}', force)
        except OSError as exc:
            return result('D5', 'FAIL', f'gate dry-run fixture could not be built: {exc}', fix)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ---- D6 ----
    def check_d6(self):
        log = self.aidd / 'evidence' / 'events.toon'
        if not log.is_file():
            return result('D6', 'PASS', 'no evidence log yet (no rules_override events)')
        count = 0
        newest = ''
        try:
            with open(log, 'r', encoding='utf-8', errors='replace') as fh:
                for line in fh:
                    if ',rules_override,' in line or ',guard_override,' in line:
                        count += 1
                        newest = line.strip().split(',', 1)[0]
        except OSError as exc:
            return result('D6', 'WARN', f'could not read evidence log: {exc}', '')
        if not count:
            return result('D6', 'PASS', 'no rules_override events in the evidence log')
        date = newest
        try:
            import datetime
            date = datetime.datetime.fromtimestamp(float(newest)).strftime('%Y-%m-%d %H:%M')
        except (ValueError, OSError, OverflowError):
            pass
        return result('D6', 'WARN', f'{count} rules_override event(s), newest {date}',
                      'review them: aidd status; unset AIDD_RULES=off if it is set')

    # ---- D7 ----
    def check_d7(self, host):
        binary = 'agy' if host == 'antigravity' else host
        exe = shutil.which(binary)
        if not exe:
            return result('D7', 'WARN', f'{binary} binary not installed', f'install the {binary} CLI')
        try:
            proc = subprocess.run([exe, '--version'], capture_output=True, timeout=5)
            out = (proc.stdout or proc.stderr).decode('utf-8', errors='replace').strip().splitlines()
            return result('D7', 'WARN', f'{binary} version: {out[0] if out else "(no output)"} (informational)', '')
        except (OSError, subprocess.TimeoutExpired):
            return result('D7', 'WARN', f'{binary} --version did not answer within 5 s', '')

    def run_host(self, host):
        d1 = self.check_d1(host)
        out = [d1]
        if d1['status'] == 'FAIL' and not self.aidd.is_dir():
            out.append(self.check_d7(host))
            return out
        out.append(self.check_d2(host))
        out.append(self.check_d3(host))
        out.append(self.check_d4(host))
        out.append(self.check_d5(host))
        out.append(self.check_d6())
        out.append(self.check_d7(host))
        if host in ('opencode', 'antigravity'):
            out.append(self.check_d8(host))
            out.append(self.check_d9(host))
        return out

    # ---- D8 ----
    def git_hooks_dir(self):
        """Hooks dir from `git rev-parse --git-path hooks` (worktree-safe), or None when git cannot answer."""
        try:
            proc = subprocess.run(['git', 'rev-parse', '--git-path', 'hooks'], cwd=str(self.root),
                                  capture_output=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            return None
        out = proc.stdout.decode('utf-8', errors='replace').strip()
        if proc.returncode != 0 or not out:
            return None
        path = Path(out)
        return path if path.is_absolute() else self.root / path

    def opencode_major(self):
        """Major version of `opencode --version`, or None (binary missing, silent, unparsable, slow)."""
        exe = shutil.which('opencode')
        if not exe:
            return None
        try:
            proc = subprocess.run([exe, '--version'], capture_output=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            return None
        match = re.search(r'(\d+)\.\d+', (proc.stdout or proc.stderr).decode('utf-8', errors='replace'))
        return int(match.group(1)) if match else None

    def check_d8(self, host):
        fix = 'aidd install --githooks'
        prefix = ''
        if host == 'opencode' and self.opencode_major() == 2:
            prefix = OPENCODE2_GATE_LINE + '; '
        hooks = self.git_hooks_dir()
        if hooks is None:
            return result('D8', 'FAIL', f'{prefix}git hooks dir not found (not a git repo, or git unavailable)', fix)
        bad = []
        for name in GITHOOK_NAMES:
            text = read_text(hooks / name)
            if not any(call in text for call in GUARD_CALLS):
                bad.append(name)
        if bad:
            return result('D8', 'FAIL', f'{prefix}git hook(s) missing or not calling `aidd guard`: '
                          + ', '.join(bad), fix)
        return result('D8', 'PASS', f'{prefix}git hooks {", ".join(GITHOOK_NAMES)} call `aidd guard`')

    # ---- D9 ----
    def check_d9(self, host):
        fix = f'aidd install --host {host} --force'
        nxt = self.aidd / 'NEXT.md'
        if not nxt.is_file() and not (self.aidd.is_dir() and os.access(str(self.aidd), os.W_OK)):
            return result('D9', 'FAIL', '.aidd/NEXT.md missing and .aidd/ is not writable', 'aidd next --write')
        files = ['.aidd/CORE.md']
        if host == 'antigravity':
            files.append('.agents/rules/aidd.md')
        for rel in files:
            if NEXT_LINE_NEEDLE not in read_text(self.root / rel).lower():
                return result('D9', 'FAIL', f'{rel} lacks the line telling the agent to run `aidd next` '
                              'before each step', fix)
        state = 'present' if nxt.is_file() else 'creatable'
        return result('D9', 'PASS', f'.aidd/NEXT.md {state}; "run aidd next" line found in {", ".join(files)}')


def detect_hosts(root: Path):
    hosts = []
    if (root / '.gemini' / 'settings.json').is_file() or (root / 'GEMINI.md').is_file():
        hosts.append('gemini')
    if (root / '.opencode').exists():
        hosts.append('opencode')
    hooks_json = root / '.agents' / 'hooks.json'
    has_entry = hooks_json.is_file() and agy_entry(load_json(hooks_json)) is not None
    if has_entry or (root / '.agents' / 'rules' / 'aidd.md').is_file():
        hosts.append('antigravity')
    return hosts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='aidd_doctor', description='Check an AIDD host install.')
    ap.add_argument('--host', choices=HOSTS)
    ap.add_argument('--root', default='.')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    hosts = [args.host] if args.host else detect_hosts(root)
    if not hosts:
        if (root / '.aidd').is_dir():
            msg = 'cannot detect the host (no GEMINI.md, .gemini/settings.json, .opencode/ or .agents/hooks.json)'
            rows = [result('D1', 'FAIL', msg, 'aidd doctor --host gemini|opencode|antigravity')]
        else:
            rows = [result('D1', 'FAIL', '.aidd/ not found in the project', 'aidd install --host gemini|opencode|antigravity')]
    else:
        rows = []
        doctor = Doctor(root)
        for host in hosts:
            for row in doctor.run_host(host):
                if len(hosts) > 1:
                    row = dict(row, message=f'[{host}] {row["message"]}')
                rows.append(row)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            line = f'{r["status"]} {r["id"]} {r["message"]}'
            if r['fix']:
                line += f' -> {r["fix"]}'
            print(line)
    failed = any(r['status'] == 'FAIL' and r['id'] in BLOCKING_IDS for r in rows)
    return 1 if failed else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:  # no tracebacks to the user
        print(f'FAIL doctor internal error: {exc} -> report this to the AIDD maintainers')
        sys.exit(1)
