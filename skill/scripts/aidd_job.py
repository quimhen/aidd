#!/usr/bin/env python3
"""aidd job — launch a tool, WAIT for its verdict, never repeat the same work on the same inputs.

Spec 004 amendment 2026-10-24 (aidd:FR-035, aidd:FR-036, aidd:AC-027, aidd:T-39).

The agent does not execute an operation step by step: it launches the tool once and waits for one verdict.
A second launch of the same command on the same inputs does not execute anything: it prints the stored
verdict marked CACHED.

Usage:
    python aidd_job.py [--root DIR] run [--bg] [--key G1,G2] [--name N] [--force] [--timeout S] -- <command...>
    python aidd_job.py [--root DIR] wait <id> [--timeout S]
    python aidd_job.py [--root DIR] last <name>
    python aidd_job.py [--root DIR] list

Cache key: `inputs_hash` = sha256 over the sorted lines `rel\\0blobsha\\n` of the files the `--key` globs
match (git blob hash of the WORKING-TREE content, one `git hash-object --stdin-paths` pass; never mtime or
size). Default key (no --key), the same rule as the project's code fingerprint: every file of
`git ls-files -c -o --exclude-standard` (fallback os.walk) of ANY extension, excluding `specs/`, `.aidd/`,
`.git/`, node_modules, __pycache__, build/dist and the other skip dirs, and documentation (.md .markdown
.rst .adoc .txt); SQL, TS, Dart ... inputs count, so a stale verdict is never served (over-invalidating is
safe). An explicit `--key` restricts the inputs to those globs, any extension (a plain path without
wildcards matches that file or directory). `.aidd/` is never part of the inputs. Same `cmd_hash` (sha256 of the argv list) + same `inputs_hash` = CACHED.

Job dir: `<root>/.aidd/jobs/<name>-<inputs8>/` with `verdict.json`, `log.txt` (stdout+stderr),
`status.json` {pid, started} while running, `job.json` (what a background run executes). Only this CLI
writes `.aidd/jobs/`.

Verdict contract (FR-036): a tool's last stdout line may be
    RESULT: ok|fail|stale|refused - <N> items - evidence <path>
(' - ' or ' — '); without it the result is derived from the exit code (0 ok, 1 fail, 2 refused, other fail)
and the summary is the last output line (`source` = 'derived', else 'RESULT').

Exit codes: run / wait / last return the tool's exit code (stored one when CACHED); 3 = `last` with changed
inputs (STALE) or no job, or `wait` on an unknown id; 4 = timeout (run --timeout or wait --timeout);
2 = usage error. Stdlib only, no LLM.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (OSError, ValueError):
        pass

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
try:  # aidd:FR-035 reuse the code graph's content hashing; stdlib fallback below when it is missing
    import code_graph as _cg  # noqa: E402
except Exception:  # pragma: no cover - fallback path
    _cg = None

JOBS_REL = ('.aidd', 'jobs')
GIT_TIMEOUT = 60
POLL_S = 0.5
NO_STATUS_GRACE_S = 15.0
TAIL_ON_FAIL = 15
RESULTS = ('ok', 'fail', 'stale', 'refused')
EXIT_STALE = 3
EXIT_TIMEOUT = 4
_CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_FALLBACK_SKIP_DIRS = frozenset({'.git', '.hg', '.svn', 'node_modules', 'venv', '.venv', 'env', '.env',
                                 '__pycache__', 'site-packages', 'dist', 'build', '.tox', '.nox', '.eggs',
                                 '.mypy_cache', '.pytest_cache', '.ruff_cache', 'graphify-out'})
_SKIP_TOP = frozenset({'.aidd'})
_DEFAULT_SKIP_TOP = frozenset({'specs'})
_DOC_EXTS = ('.md', '.markdown', '.rst', '.adoc', '.txt')
# aidd:FR-036 tolerant RESULT line: ' - ', ' — ' or ' – ' separators, optional items / evidence parts
RESULT_RE = re.compile(
    r'^\s*RESULT\s*:\s*(ok|fail|stale|refused)\b'
    r'(?:\s*[-—–]+\s*(\d+)\s*items?)?'
    r'(?:\s*[-—–]+\s*evidence\s*[:=]?\s*(.*?))?\s*$', re.I)
SHA_RE = re.compile(r'^[0-9a-f]{40}([0-9a-f]{24})?$')


# ---------------------------------------------------------------------------------------------------- small io

def _now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def _jobs_dir(root):
    return Path(root).joinpath(*JOBS_REL)


_JOB_ID_RE = re.compile(r'^[A-Za-z0-9_.-]+$')


def _valid_job_id(s):  # aidd:FR-048
    """A job id is one plain path segment: letters, digits, _ . - and no '..'."""
    return isinstance(s, str) and bool(_JOB_ID_RE.match(s)) and '..' not in s


def _job_dir(root, id):  # aidd:FR-048
    """The job directory under the jobs dir, or None when the id is invalid or the path escapes it."""
    if not _valid_job_id(id):
        return None
    try:
        base = _jobs_dir(root).resolve()
        d = (base / id).resolve()
        d.relative_to(base)
    except (OSError, ValueError):
        return None
    return d if d != base else None


def _redact_cmd(cmd):  # aidd:FR-048
    """The stored copy of cmd with secrets redacted (unchanged when aidd_evidence.redact_secrets is unavailable)."""
    try:
        import aidd_evidence
        return [aidd_evidence.redact_secrets(str(a))[0] for a in cmd]  # redact_secrets -> (text, labels)
    except Exception:
        return list(cmd)


def _write_json(path, data):
    """Atomic write (tmp + os.replace, retried on Windows sharing violations). Never raises; False on failure."""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name('%s.%d.tmp' % (path.name, os.getpid()))
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    except (OSError, ValueError, TypeError):
        return False
    for i in range(10):
        try:
            os.replace(str(tmp), str(path))
            return True
        except OSError:
            time.sleep(0.05 * (i + 1))
    try:
        tmp.unlink()
    except OSError:
        pass
    return False


def _read_json(path):
    """dict from a JSON file, or None (missing, unreadable, corrupt, not an object)."""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _unlink(path):
    try:
        Path(path).unlink()
    except OSError:
        pass


def _read_verdict(jobdir):
    """aidd:FR-035 a corrupt or incomplete verdict is ignored (None), so the job re-executes."""
    v = _read_json(Path(jobdir) / 'verdict.json')
    if not v:
        return None
    if not isinstance(v.get('cmd'), list) or not isinstance(v.get('inputs_hash'), str) \
            or not isinstance(v.get('cmd_hash'), str) or not isinstance(v.get('exit'), int) \
            or v.get('result') not in RESULTS:
        return None
    return v


def _pid_alive(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == 'nt':
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            code = ctypes.c_ulong()
            ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
            k32.CloseHandle(h)
            return bool(ok) and code.value == 259  # STILL_ACTIVE
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def _running(jobdir):
    """True when the job has a live status.json pid and no verdict yet."""
    if (Path(jobdir) / 'verdict.json').exists():
        return False
    st = _read_json(Path(jobdir) / 'status.json')
    return bool(st) and _pid_alive(st.get('pid'))


# ---------------------------------------------------------------------------------------------------- inputs

def _git(root, args, data=None):
    try:
        env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', LC_ALL='C')
        r = subprocess.run(['git'] + list(args), cwd=str(root), env=env, input=data,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=GIT_TIMEOUT,
                           creationflags=_CREATE_NO_WINDOW)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _glob_re(pattern):
    p = pattern.replace('\\', '/').strip()
    if p.startswith('./'):
        p = p[2:]
    if not any(c in p for c in '*?['):
        p = p.rstrip('/')
        return re.compile('^' + re.escape(p) + '(?:/.*)?$', re.I if os.name == 'nt' else 0)
    out, i = [], 0
    while i < len(p):
        if p.startswith('**/', i):
            out.append('(?:.*/)?')
            i += 3
        elif p.startswith('**', i):
            out.append('.*')
            i += 2
        elif p[i] == '*':
            out.append('[^/]*')
            i += 1
        elif p[i] == '?':
            out.append('[^/]')
            i += 1
        else:
            out.append(re.escape(p[i]))
            i += 1
    return re.compile('^' + ''.join(out) + '$', re.I if os.name == 'nt' else 0)


def _list_any(root, globs=None):
    """Sorted relative paths: `git ls-files -c -o --exclude-standard`, else os.walk with the skip dirs.
    `.aidd/` is never an input. globs None = the default key (every file except `specs/` and documentation
    extensions); otherwise only files matching `globs`, any extension. Never raises."""
    default = globs is None
    rxs = [] if default else [_glob_re(g) for g in globs if g and g.strip()]
    if not default and not rxs:
        return []
    root = Path(root)
    skip_top = _SKIP_TOP | _DEFAULT_SKIP_TOP if default else _SKIP_TOP

    def keep(rel):
        if '\n' in rel:
            return False
        parts = rel.split('/')
        if parts[0] in skip_top or any(s in _FALLBACK_SKIP_DIRS for s in parts[:-1]):
            return False
        if default:
            return not rel.lower().endswith(_DOC_EXTS)
        return any(rx.match(rel) for rx in rxs)

    found = set()
    try:
        raw = _git(root, ['ls-files', '-c', '-o', '--exclude-standard', '-z'])
        if raw is not None:
            for rel in raw.decode('utf-8', errors='surrogateescape').split('\0'):
                rel = rel.replace('\\', '/')
                if rel and keep(rel) and os.path.isfile(os.path.join(str(root), rel)):
                    found.add(rel)
            return sorted(found)
        base = str(root)
        for cur, dirs, files in os.walk(base):
            relcur = os.path.relpath(cur, base).replace('\\', '/')
            relcur = '' if relcur == '.' else relcur
            dirs[:] = sorted(d for d in dirs if d not in _FALLBACK_SKIP_DIRS and not (not relcur and d in skip_top))
            for f in files:
                rel = (relcur + '/' + f) if relcur else f
                if keep(rel):
                    found.add(rel)
    except (OSError, ValueError):
        pass
    return sorted(found)


def _blob_sha(data):
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def _file_shas(root, rels):
    if _cg is not None:
        try:
            return _cg.file_shas(root, rels)
        except Exception:
            pass
    rels = [r for r in rels if '\n' not in r]
    if not rels:
        return {}
    out = _git(root, ['hash-object', '--stdin-paths'],
               data=('\n'.join(rels) + '\n').encode('utf-8', errors='surrogateescape'))
    if out is not None:
        shas = out.decode('ascii', errors='replace').split()
        if len(shas) == len(rels) and all(SHA_RE.match(s) for s in shas):
            return dict(zip(rels, shas))
    res = {}
    for rel in rels:
        try:
            res[rel] = _blob_sha((Path(root) / rel).read_bytes())
        except OSError:
            continue
    return res


def _list_inputs(root, key):
    """aidd:FR-035 files of the cache key. key None = the code-fingerprint default: every file of any
    extension except `specs/`, `.aidd/`, the skip dirs and documentation (over-invalidating is safe,
    serving a stale verdict is not); key = only the files matching those globs, any extension."""
    return _list_any(root, key or None)


def inputs_hash(root, key=None):
    """aidd:FR-035 (sha256 hex, file count) over sorted `rel\\0blobsha\\n` lines; content only, never mtime."""
    rels = _list_inputs(root, key)
    shas = _file_shas(root, rels)
    h = hashlib.sha256()
    for rel in sorted(shas):
        h.update(('%s\0%s\n' % (rel, shas[rel])).encode('utf-8', errors='surrogateescape'))
    return h.hexdigest(), len(shas)


def cmd_hash(cmd):
    return hashlib.sha256(json.dumps(list(cmd), ensure_ascii=False).encode('utf-8')).hexdigest()


def _job_name(name, cmd):
    if not name:
        pick = None
        for a in cmd:
            base = os.path.basename(str(a))
            if base.lower().endswith(('.py', '.ps1', '.sh', '.js', '.ts', '.cmd', '.bat')):
                pick = base
                break
        pick = pick or (os.path.basename(str(cmd[0])) if cmd else 'job')
        name = os.path.splitext(pick)[0]
    name = re.sub(r'[^A-Za-z0-9_.-]+', '-', str(name)).strip('-.')[:48]
    return name or 'job'


# ---------------------------------------------------------------------------------------------------- execute

def _parse_output(text, exit_code):
    """aidd:FR-036 (result, items, evidence, summary, source) from the tool output and its exit code."""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    for idx in range(len(lines) - 1, max(-1, len(lines) - 6), -1):  # tolerate stderr noise after RESULT
        m = RESULT_RE.match(lines[idx])
        if m:
            items = int(m.group(2)) if m.group(2) else None
            evidence = (m.group(3) or '').strip() or None
            prev = lines[idx - 1].strip() if idx > 0 else lines[idx].strip()
            return m.group(1).lower(), items, evidence, prev[:400], 'RESULT'
    result = {0: 'ok', 1: 'fail', 2: 'refused'}.get(exit_code, 'fail')
    summary = lines[-1].strip()[:400] if lines else '(no output)'
    return result, None, None, summary, 'derived'


def _resolve_cmd(cmd):
    cmd = list(cmd)
    if cmd and os.name == 'nt' and not os.path.dirname(cmd[0]):
        found = shutil.which(cmd[0])  # npx.cmd, pytest.exe ... are not found by CreateProcess alone
        if found:
            cmd[0] = found
    return cmd


def _execute(root, jobdir, job, detached=False):
    """Run the tool, write log.txt and verdict.json. Returns the verdict dict. Never raises."""
    jobdir = Path(jobdir)
    started = _now()
    _write_json(jobdir / 'status.json', {'pid': os.getpid(), 'started': started})
    log = jobdir / 'log.txt'
    timeout = job.get('timeout') or None
    t0 = time.monotonic()
    timed_out = False
    try:
        with open(str(log), 'wb') as fh:
            try:
                r = subprocess.run(_resolve_cmd(job['cmd']), cwd=str(root), stdin=subprocess.DEVNULL,
                                   stdout=fh, stderr=subprocess.STDOUT, timeout=timeout,
                                   creationflags=_CREATE_NO_WINDOW if detached else 0)
                code = r.returncode
            except subprocess.TimeoutExpired:
                timed_out, code = True, EXIT_TIMEOUT
            except (OSError, ValueError, subprocess.SubprocessError) as e:
                fh.write(('aidd job: cannot start %r: %s\n' % (job['cmd'][:1], e)).encode('utf-8', 'replace'))
                code = 1
    except OSError as e:
        code = 1
        try:
            log.write_text('aidd job: cannot write log: %s\n' % e, encoding='utf-8')
        except OSError:
            pass
    wall = round(time.monotonic() - t0, 3)
    try:
        text = log.read_bytes().decode('utf-8', errors='replace')
    except OSError:
        text = ''
    if timed_out:
        result, items, evidence, summary, source = 'fail', None, None, 'timeout after %ss' % timeout, 'derived'
    else:
        result, items, evidence, summary, source = _parse_output(text, code)
    rel_log = _rel(root, log)
    verdict = {
        'name': job['name'], 'cmd': _redact_cmd(job['cmd']), 'cmd_hash': job['cmd_hash'],
        'inputs_hash': job['inputs_hash'], 'inputs_count': job['inputs_count'],
        'key': job.get('key'), 'started': started, 'wall_s': wall, 'exit': int(code),
        'result': result, 'summary': summary, 'items': items, 'evidence': evidence or rel_log,
        'source': source, 'log': rel_log, 'timed_out': timed_out,
    }
    _write_json(jobdir / 'verdict.json', verdict)
    return verdict


def _rel(root, p):
    try:
        return os.path.relpath(str(p), str(root)).replace('\\', '/')
    except ValueError:
        return str(p)


def _result_line(v):
    return 'RESULT: %s - %d items - evidence %s' % (v.get('result'), v.get('items') or 0,
                                                     v.get('evidence') or v.get('log') or '-')


def _print_verdict(root, jobdir, v, mark=None, tail=False):
    head = '%s%s' % ((mark + ' ') if mark else '', Path(jobdir).name)
    print('%s: %s  exit %s  wall %ss  inputs %s (%s files)  started %s' % (
        head, v.get('result'), v.get('exit'), v.get('wall_s'), str(v.get('inputs_hash', ''))[:8],
        v.get('inputs_count'), v.get('started')))
    print('summary: %s' % v.get('summary'))
    print('log: %s' % (v.get('log') or _rel(root, Path(jobdir) / 'log.txt')))
    if tail and v.get('result') != 'ok':
        try:
            lines = (Path(jobdir) / 'log.txt').read_bytes().decode('utf-8', errors='replace').splitlines()
        except OSError:
            lines = []
        if lines:
            print('--- last %d log lines ---' % min(TAIL_ON_FAIL, len(lines)))
            for ln in lines[-TAIL_ON_FAIL:]:
                print(ln)
            print('---')
    print(_result_line(v))
    sys.stdout.flush()


# ---------------------------------------------------------------------------------------------------- commands

def _wait_dir(root, jobdir, timeout):
    """Block until verdict.json exists (POLL_S polling inside this process). Returns verdict, 'timeout' or 'died'."""
    t0 = time.monotonic()
    no_status_since = None
    while True:
        v = _read_verdict(jobdir)
        if v is not None:
            return v
        st = _read_json(Path(jobdir) / 'status.json')
        if st is None:
            no_status_since = no_status_since or time.monotonic()
            if time.monotonic() - no_status_since > NO_STATUS_GRACE_S:
                return 'died'
        elif not _pid_alive(st.get('pid')):
            time.sleep(POLL_S)
            v = _read_verdict(jobdir)
            return v if v is not None else 'died'
        if timeout and time.monotonic() - t0 >= timeout:
            return 'timeout'
        time.sleep(POLL_S)


def _report_wait(root, jobdir, res, timeout):
    if res == 'timeout':
        print('TIMEOUT %s: still running after %ss (aidd job wait %s again)' % (jobdir.name, timeout, jobdir.name))
        return EXIT_TIMEOUT
    if res == 'died':
        print('DIED %s: the job process ended without a verdict; see %s' % (
            jobdir.name, _rel(root, jobdir / 'log.txt')))
        print('RESULT: fail - 0 items - evidence %s' % _rel(root, jobdir / 'log.txt'))
        return 1
    _print_verdict(root, jobdir, res, tail=True)
    return int(res.get('exit', 1))


def cmd_run(root, args, cmd):  # aidd:FR-035
    if not cmd:
        print('aidd job run: missing command after --', file=sys.stderr)
        return 2
    key = [g.strip() for g in (args.key or '').split(',') if g.strip()] or None
    name = _job_name(args.name, cmd)
    ih, count = inputs_hash(root, key)
    ch = cmd_hash(cmd)
    jobdir = _jobs_dir(root) / ('%s-%s' % (name, ih[:8]))
    if not args.force:
        v = _read_verdict(jobdir)
        if v is not None and v.get('cmd_hash') == ch and v.get('inputs_hash') == ih and not v.get('timed_out'):
            _print_verdict(root, jobdir, v, mark='CACHED', tail=True)
            return int(v.get('exit', 1))
        job = _read_json(jobdir / 'job.json')
        if _running(jobdir) and job and job.get('cmd_hash') == ch:  # same work already in flight: wait for it
            if args.bg:
                print(jobdir.name)
                print('RUNNING (already in flight): aidd job wait %s' % jobdir.name)
                return 0
            return _report_wait(root, jobdir, _wait_dir(root, jobdir, args.timeout), args.timeout)
    try:
        jobdir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print('aidd job: cannot create %s: %s' % (jobdir, e), file=sys.stderr)
        return 1
    _unlink(jobdir / 'verdict.json')
    _unlink(jobdir / 'status.json')
    job = {'root': str(Path(root).resolve()), 'name': name, 'cmd': list(cmd), 'cmd_hash': ch,
           'inputs_hash': ih, 'inputs_count': count, 'key': key, 'timeout': args.timeout}
    stored = dict(job, cmd=_redact_cmd(cmd))  # the file keeps no secrets; `_exec` re-reads it (see _exec_main)
    if not _write_json(jobdir / 'job.json', stored):
        print('aidd job: cannot write %s' % (jobdir / 'job.json'), file=sys.stderr)
        return 1
    if args.bg:
        return _spawn(root, jobdir, cmd)
    v = _execute(root, jobdir, job)
    _print_verdict(root, jobdir, v, tail=True)
    return int(v.get('exit', 1))


def _spawn(root, jobdir, cmd=None):
    kw = {}
    if cmd:  # job.json holds the redacted cmd; the worker gets the real argv through its environment only
        kw['env'] = dict(os.environ, AIDD_JOB_REAL_CMD=json.dumps(list(cmd), ensure_ascii=False))
    if os.name == 'nt':
        kw['creationflags'] = _CREATE_NO_WINDOW | _DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP
    else:
        kw['start_new_session'] = True
    try:
        p = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '_exec', str(jobdir)],
                             cwd=str(root), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, close_fds=True, **kw)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        print('aidd job: cannot start background job: %s' % e, file=sys.stderr)
        return 1
    if not (jobdir / 'status.json').exists():
        _write_json(jobdir / 'status.json', {'pid': p.pid, 'started': _now()})
    print(jobdir.name)
    print('STARTED: aidd job wait %s' % jobdir.name)
    return 0


def _exec_main(argv):
    """Hidden `_exec <jobdir>`: the detached worker of `run --bg`."""
    if not argv:
        return 2
    given = Path(argv[0])
    safe = _job_dir(os.getcwd(), given.name)  # aidd:FR-048 the worker is spawned with cwd=root
    try:
        ok = safe is not None and given.resolve() == safe
    except OSError:
        ok = False
    if not ok:
        print('refused: job directory %r is not a valid job under %s' % (argv[0], '/'.join(JOBS_REL)))
        return 2
    jobdir = safe
    job = _read_json(jobdir / 'job.json')
    if not job or not isinstance(job.get('cmd'), list) or not job.get('cmd'):
        return 2
    try:
        real = json.loads(os.environ.get('AIDD_JOB_REAL_CMD') or 'null')
        if isinstance(real, list) and real and all(isinstance(a, str) for a in real):
            job['cmd'] = real
    except ValueError:
        pass
    try:
        v = _execute(job.get('root') or os.getcwd(), jobdir, job, detached=True)
    except Exception:
        return 1
    return int(v.get('exit', 1))


def cmd_wait(root, args):
    jobdir = _job_dir(root, args.id)
    if jobdir is None:
        print('refused: invalid job id %r (letters, digits, _ . - only; no "..", must stay under %s)' % (
            args.id, '/'.join(JOBS_REL)))
        return 2
    if not jobdir.is_dir():
        print('NONE %s: no such job under %s' % (args.id, _rel(root, _jobs_dir(root))))
        return EXIT_STALE
    return _report_wait(root, jobdir, _wait_dir(root, jobdir, args.timeout), args.timeout)


def _all_jobs(root):
    out = []
    try:
        dirs = [d for d in _jobs_dir(root).iterdir() if d.is_dir()]
    except OSError:
        return out
    for d in dirs:
        out.append((d, _read_verdict(d)))
    return out


def cmd_last(root, args):
    raw = args.name
    name = _job_name(raw, [])
    if (raw is not None and not _valid_job_id(raw)) or not _valid_job_id(name) or _job_dir(root, name) is None:  # aidd:FR-048
        print('refused: invalid job name %r (letters, digits, _ . - only)' % name)
        return 2
    cands = [(d, v) for d, v in _all_jobs(root) if v is not None and v.get('name') == name]
    if not cands:
        print('STALE %s: no stored verdict' % name)
        return EXIT_STALE
    d, v = max(cands, key=lambda dv: (str(dv[1].get('started') or ''), dv[0].name))
    ih, _ = inputs_hash(root, v.get('key'))
    if ih != v.get('inputs_hash'):
        print('STALE %s: inputs changed since %s (stored %s, now %s); re-run it' % (
            d.name, v.get('started'), str(v.get('inputs_hash'))[:8], ih[:8]))
        return EXIT_STALE
    _print_verdict(root, d, v, tail=True)
    return int(v.get('exit', 1))


def cmd_list(root, args):
    jobs = _all_jobs(root)
    if not jobs:
        print('no jobs under %s' % _rel(root, _jobs_dir(root)))
        return 0
    memo = {}
    rows = []
    for d, v in jobs:
        if v is None:
            state = 'running' if _running(d) else 'no-verdict'
            rows.append(('', d.name, '-', '-', '-', state))
            continue
        k = json.dumps(v.get('key'))
        if k not in memo:
            memo[k] = inputs_hash(root, v.get('key'))[0]
        state = 'cached' if memo[k] == v.get('inputs_hash') else 'stale'
        rows.append((str(v.get('started') or ''), v.get('name'), v.get('result'), v.get('wall_s'),
                     str(v.get('inputs_hash'))[:8], state))
    rows.sort(key=lambda r: r[0], reverse=True)
    for _, nm, res, wall, i8, state in rows:
        print('%-32s %-8s %8ss  %s  %s' % (nm, res, wall, i8, state))
    return 0


# ---------------------------------------------------------------------------------------------------- main

def _parser():
    p = argparse.ArgumentParser(
        prog='aidd job',
        description='Launch a tool and WAIT for its verdict; the same command on the same inputs is CACHED.',
        epilog='exit: tool exit code; 3 STALE/none; 4 timeout; 2 usage.')
    p.add_argument('--root', default='.', help='project root (default: cwd)')
    sub = p.add_subparsers(dest='sub')
    r = sub.add_parser('run', help='run a command (or print its CACHED verdict): run [opts] -- <command...>')
    r.add_argument('--bg', action='store_true', help='detach; print the job id; then `wait <id>`')
    r.add_argument('--key', default=None, help='comma globs of the input files, any extension (default: every git-listed file '
                        'except specs/, .aidd/, skip dirs and docs .md/.markdown/.rst/.adoc/.txt)')
    r.add_argument('--name', default=None, help='job name (default: from the command)')
    r.add_argument('--force', action='store_true', help='execute even when a matching verdict exists')
    r.add_argument('--timeout', type=float, default=None, help='kill the tool after S seconds (exit 4)')
    r.add_argument('rest', nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    w = sub.add_parser('wait', help='block until job <id> ends; return the tool exit code')
    w.add_argument('id')
    w.add_argument('--timeout', type=float, default=None, help='give up after S seconds (exit 4)')
    la = sub.add_parser('last', help='newest verdict of <name>; exit 3 when its inputs changed or none exists')
    la.add_argument('name')
    li = sub.add_parser('list', help='one line per job: name, result, wall_s, inputs8, cached/stale')
    for sp in (r, w, la, li):  # --root also after the subcommand; that value wins
        sp.add_argument('--root', default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ['_exec']:
        return _exec_main(argv[1:])
    cmd = []
    if '--' in argv:
        i = argv.index('--')
        argv, cmd = argv[:i], argv[i + 1:]
    p = _parser()
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0) if isinstance(e.code, int) else 2
    root = str(Path(args.root).resolve())
    if args.sub == 'run':
        rest = list(args.rest or [])
        if rest[:1] == ['--']:
            rest = rest[1:]
        return cmd_run(root, args, cmd or rest)
    if args.sub == 'wait':
        return cmd_wait(root, args)
    if args.sub == 'last':
        return cmd_last(root, args)
    if args.sub == 'list':
        return cmd_list(root, args)
    p.print_help()
    return 2


if __name__ == '__main__':
    sys.exit(main())
