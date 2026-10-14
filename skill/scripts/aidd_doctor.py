#!/usr/bin/env python3
"""aidd_doctor.py -- check that AIDD is correctly installed for a host (Gemini CLI / OpenCode).

Usage: python aidd_doctor.py [--host gemini|opencode] [--root DIR] [--json]

One line per check: `PASS|FAIL|WARN <id> <message> -> <exact fix>`.
Exit 1 when any of D1-D5 fails, else 0. Stdlib only. Read-only on the project (D5 uses a temp fixture).

aidd:FR-909 aidd:FR-911
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CORE_MAX_BYTES = 12288
IGNORED_PARTS = {'__pycache__', 'memory', 'evidence'}
IGNORED_NAMES = {'gate_spec', 'active_spec'}
HOSTS = ('gemini', 'opencode')
BLOCKING_IDS = ('D1', 'D2', 'D3', 'D4', 'D5')
PLUGIN_ENTRY = '.opencode/plugins/aidd.js'
GEMINI_MATCHER = 'write_file|replace|run_shell_command'


def repo_root() -> Path:
    """skill/scripts/aidd_doctor.py -> repo root (same layout aidd/cli.py assumes)."""
    return Path(__file__).resolve().parent.parent.parent


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
        if total:
            more = f' (+{total - len(diffs)} more)' if total > len(diffs) else ''
            return result('D1', 'FAIL', f'{total} file(s) differ from shipped: ' + '; '.join(diffs) + more,
                          f'aidd install --host {host} --force')
        return result('D1', 'PASS', '.aidd/ complete and equal to the shipped adapters/dot-aidd')

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
        return result('D2', 'PASS', f'.aidd/CORE.md present, {size} bytes (< {CORE_MAX_BYTES})')

    # ---- D3 ----
    def check_d3(self, host):
        fix = f'aidd install --host {host}'
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

    # ---- D4 ----
    def check_d4(self, host):
        fix = f'aidd install --host {host}'
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
        cfg = load_json(self.root / '.opencode' / 'opencode.json')
        if cfg is None:
            return result('D4', 'FAIL', '.opencode/opencode.json missing or not valid JSON', fix)
        plugins = cfg.get('plugin') if isinstance(cfg, dict) else None
        norm = []
        for p in (plugins if isinstance(plugins, list) else []):
            p = str(p).replace('\\', '/')
            norm.append(p[2:] if p.startswith('./') else p)
        if PLUGIN_ENTRY not in norm:
            return result('D4', 'FAIL', f'opencode.json "plugin" array does not contain {PLUGIN_ENTRY}', fix)
        plugin = self.root / PLUGIN_ENTRY
        if not plugin.is_file():
            return result('D4', 'FAIL', f'{PLUGIN_ENTRY} missing', fix)
        shipped = repo_root() / 'adapters' / 'opencode' / 'plugins' / 'aidd.js'
        if not shipped.is_file():
            shipped = self.shipped.parent / 'opencode' / 'plugins' / 'aidd.js'
        data = plugin.read_bytes()
        if shipped.is_file() and shipped.read_bytes() != data:
            return result('D4', 'FAIL', f'{PLUGIN_ENTRY} differs from the shipped plugin (sha1 {short_sha1(data)})',
                          fix + ' --force')
        note = '' if shipped.is_file() else ' (shipped copy not found, content not compared)'
        return result('D4', 'PASS', f'plugin registered and file unaltered (sha1 {short_sha1(data)}){note}')

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
                    if ',rules_override,' in line:
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
        exe = shutil.which(host)
        if not exe:
            return result('D7', 'WARN', f'{host} binary not installed', f'install the {host} CLI')
        try:
            proc = subprocess.run([exe, '--version'], capture_output=True, timeout=5)
            out = (proc.stdout or proc.stderr).decode('utf-8', errors='replace').strip().splitlines()
            return result('D7', 'WARN', f'{host} version: {out[0] if out else "(no output)"} (informational)', '')
        except (OSError, subprocess.TimeoutExpired):
            return result('D7', 'WARN', f'{host} --version did not answer within 5 s', '')

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
        return out


def detect_hosts(root: Path):
    hosts = []
    if (root / '.gemini' / 'settings.json').is_file() or (root / 'GEMINI.md').is_file():
        hosts.append('gemini')
    if (root / '.opencode').exists():
        hosts.append('opencode')
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
            msg = 'cannot detect the host (no GEMINI.md, .gemini/settings.json or .opencode/)'
            rows = [result('D1', 'FAIL', msg, 'aidd doctor --host gemini|opencode')]
        else:
            rows = [result('D1', 'FAIL', '.aidd/ not found in the project', 'aidd install --host gemini|opencode')]
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
