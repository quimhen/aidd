"""aidd:FR-419..FR-426 `aidd verify --round <spec>...` / `aidd verify --all-open --round`: ONE verification pass
over several specs (amendment 10, item O, spec 007).

1. Collect the `## Verification` rows of every requested spec (rows with `Tier: perf` are excluded, rows with a
   lint problem are left to the per-spec bookkeeping, which never runs them).
2. Normalise each command (whitespace outside quotes, double quotes around a plain word) and group identical ones.
3. Execute each group ONCE, in series (a heavy runner is always alone; non-heavy groups may run in parallel only
   when every spec of the round declares `Jobs:` > 1, the smallest value wins; `AIDD_VERIFY_JOBS` overrides).
4. Record each spec's own `verify_run` through `aidd_status.cmd_verify(..., round_shared=...)`: same evidence files
   (`evidence/verify-<n>.txt`, with a `ROUND-SHARED:` second line), same stability check (the code state taken
   BEFORE the round is compared with the one after it), so R7/R10 of each spec read it like a normal run.
5. Safety: a group of 2+ rows is shared only when the ENVIRONMENT FINGERPRINT (content of the union of the
   group's `Scope:` + `Inputs`, or the whole code tree when one spec has no Scope, minus `Generated:`; identity of
   every `docker exec` container named by the command; stdout of each spec's `Round-identity:` command; the values
   of the declared variables) is identical at the start and at the end of its execution. A changed or unavailable
   fingerprint INVALIDATES the group (every consumer row FAILS, nothing is shared). A failure is shared as a
   failure, never as a pass: each row's own Expected is evaluated on the shared output.
6. `--dry-run` prints the plan (groups vs rows, saved executions, estimated seconds from the previous verify_run)
   and executes nothing.

Never imported at module level by aidd_status (lazy, both directions), stdlib only."""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Commands that hold a database, a browser, a big build or a whole test suite: never run beside anything else.
HEAVY_RE = re.compile(r'db_verify|psql|pg_prove|docker|supabase|--tap|vitest|playwright|\bnpm\s+(?:run\s+)?test\b'
                      r'|\btsc\b|\bnpx\b|\bpytest\b|\bgradle|\bmvn\b|\bdotnet\s+test\b', re.I)
_PLAIN_WORD_RE = re.compile(r'^[A-Za-z0-9_./:=@%+,\\-]+$')
_DOCKER_EXEC_RE = re.compile(r'\bdocker(?:\.exe)?\s+exec\b(?P<rest>[^|&;]*)', re.I)
_DOCKER_VALUE_OPTS = {'-u', '--user', '-w', '--workdir', '-e', '--env', '--env-file', '--detach-keys'}
_IDENTITY_RE = re.compile(r'^[ \t>*_-]*round-identity\s*:\s*`?(.+?)`?\s*$', re.I | re.M)
IDENTITY_TIMEOUT = 30
WHOLE_TREE_BUDGET = 120


# --- normalisation and grouping -------------------------------------------------------------------------------

def _tokens(cmd):
    """Split on whitespace OUTSIDE quotes; quotes stay part of the token (spaces inside quotes are significant)."""
    out, cur, quote = [], [], None
    for ch in str(cmd or '').strip():
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
        elif ch in '"\'':
            quote = ch
            cur.append(ch)
        elif ch.isspace():
            if cur:
                out.append(''.join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        out.append(''.join(cur))
    return out


def normalize_command(cmd):
    """Grouping key text of a command: tokens joined by one space; a token that is a plain word wrapped in double
    quotes (or single quotes outside Windows, where cmd.exe keeps them literally) loses its quotes. Anything else is
    kept byte for byte, so commands that only look alike never merge."""
    norm = []
    quotes = ('"',) if os.name == 'nt' else ('"', "'")
    for t in _tokens(cmd):
        if len(t) >= 2 and t[0] == t[-1] and t[0] in quotes and _PLAIN_WORD_RE.match(t[1:-1]):
            t = t[1:-1]
        norm.append(t)
    return ' '.join(norm)


def group_key(root, cmd):
    return f'{Path(root).resolve()}\0{normalize_command(cmd)}'


def heavy(cmd):
    return bool(HEAVY_RE.search(str(cmd or '')))


# --- environment fingerprint ----------------------------------------------------------------------------------

def docker_containers(cmd):
    """Container names of every `docker exec [opts] <name> ...` in the command (sorted, unique)."""
    names = set()
    for m in _DOCKER_EXEC_RE.finditer(str(cmd or '')):
        toks = [t.strip('"\'') for t in _tokens(m.group('rest'))]
        i = 0
        while i < len(toks):
            t = toks[i]
            if t in _DOCKER_VALUE_OPTS:
                i += 2
                continue
            if t.startswith('-'):
                i += 1
                continue
            if re.fullmatch(r'[A-Za-z0-9][\w.-]*', t):
                names.add(t)
            break
    return sorted(names)


def _docker_identity(name):
    """`<container id>|<started at>` or None (docker absent, container missing, timeout)."""
    try:
        r = subprocess.run(['docker', 'inspect', '-f', '{{.Id}}|{{.State.StartedAt}}', name], capture_output=True,
                           timeout=IDENTITY_TIMEOUT, stdin=subprocess.DEVNULL,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        out = r.stdout.decode('utf-8', 'replace').strip()
        return out if r.returncode == 0 and out else None
    except Exception:
        return None


def _identity_output(root, cmd):
    """sha256 of the stdout of a `Round-identity:` command, or None when it fails."""
    try:
        r = subprocess.run(cmd, shell=True, cwd=str(root), capture_output=True, timeout=IDENTITY_TIMEOUT,
                           stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            return None
        return hashlib.sha256(r.stdout.replace(b'\r\n', b'\n').strip()).hexdigest()
    except Exception:
        return None


def identity_commands(spec_text):
    try:
        t = spec_text if isinstance(spec_text, str) else ''
        m = re.search(r'^#{2,3}[ \t]+verification[ \t]*$', t, re.I | re.M)
        if not m:
            return []
        rest = t[m.end():]
        nxt = re.search(r'^#{2,3}[ \t]+\S', rest, re.M)
        sec = rest[:nxt.start()] if nxt else rest
        return sorted({x.group(1).strip() for x in _IDENTITY_RE.finditer(sec)
                       if x.group(1).strip() and '<' not in x.group(1)})
    except Exception:
        return []


def declared_vars(st, spec_text, rows):
    """Variables named by `Round-vars: A, B` and by each row's `Environment` `vars=` section."""
    names = set(st.rules._verification_globs(spec_text, 'round-vars'))
    for r in rows:
        for sec in str(r.get('environment') or '').split(';'):
            sec = sec.strip()
            if sec.lower().startswith('vars='):
                names.update(v.strip() for v in sec[5:].split(',') if v.strip() and v.strip().lower() != 'none')
    return sorted(n for n in names if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', n))


def env_fingerprint(st, root, scope, exclude, cmds, identity_cmds, var_names):
    """(16-hex fingerprint, None) or (None, reason). `scope` None = whole code tree."""
    budget = st._fingerprint_budget() if scope else WHOLE_TREE_BUDGET
    state = st.ev.code_state(root, budget_s=budget, scope=scope or None)
    files = st.ev.fingerprint_of(state, scope or None, exclude=exclude) if state else None
    if files is None:
        return None, 'files in scope could not be fingerprinted'
    containers = {}
    for cmd in cmds:
        for c in docker_containers(cmd):
            if c not in containers:
                containers[c] = _docker_identity(c)
                if containers[c] is None:
                    return None, f'identity of container {c} unavailable'
    identities = {}
    for c in identity_cmds:
        identities[c] = _identity_output(root, c)
        if identities[c] is None:
            return None, f'Round-identity command failed: {c[:80]}'
    env = {v: (hashlib.sha256(os.environ[v].encode('utf-8', 'replace')).hexdigest() if v in os.environ else '<unset>')
           for v in var_names}
    blob = json.dumps({'files': files, 'containers': containers, 'identity': identities, 'vars': env},
                      sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(blob.encode('ascii')).hexdigest()[:16], None


# --- planning ---------------------------------------------------------------------------------------------------

def open_specs(st, root):
    try:
        names = {p.name for p in st._spec_dirs(root)}
        return [s for s in st.ev.open_specs(root) if s in names]
    except Exception:
        return []


def _pending(st, root, d):
    """True when the spec has no passing verify_run of its CURRENT Verification table."""
    try:
        run = st.ev.latest_verify_run(root, d.name)
        vhash = st.rules.verification_hash(st._read(d / 'spec.md'))
        return not (run and run.get('ok') is True and run.get('verify_hash') == vhash)
    except Exception:
        return True


def collect(st, root, spec_args):
    """(specs, rows, notes). specs = [{name, dir, text, scope, generated, identity, vars, jobs}];
    rows = [{spec, n, i, cmd, expected, inputs, key, heavy}] of the functional tier."""
    specs, rows, notes = [], [], []
    seen = set()
    for arg in spec_args:
        d = st._resolve_spec(arg, root)
        if d is None:
            notes.append(f'Refused: not a spec directory: {arg}')
            continue
        if d.name in seen:
            continue
        seen.add(d.name)
        text = st._read(d / 'spec.md')
        all_rows = st.rules.parse_verification(text)
        func = [r for r in all_rows if st.rules.row_tier(r) != 'perf']
        perf_n = len(all_rows) - len(func)
        if perf_n:
            notes.append(f'{d.name}: {perf_n} `Tier: perf` row(s) excluded from the round (aidd verify {d.name} --perf)')
        if not func:
            notes.append(f'Refused: {d.name} has no functional Verification row; left out of the round.')
            continue
        try:
            jobs = int(float((st.rules._verification_globs(text, 'jobs') or ['1'])[0]))
        except Exception:
            jobs = 1
        info = {'name': d.name, 'dir': d, 'text': text,
                'scope': st.rules.verification_scope(text, st._read_tasks(d)),
                'generated': st.rules.verification_generated(text),
                'identity': identity_commands(text), 'vars': declared_vars(st, text, func), 'jobs': max(1, jobs)}
        specs.append(info)
        for i, r in enumerate(func, 1):
            expected = r.get('expected') or 'exit 0'
            rows.append({'spec': d.name, 'n': str(r.get('n') or i), 'i': i, 'cmd': r['cmd'], 'expected': expected,
                         'inputs': r.get('inputs') or [], 'key': group_key(root, r['cmd']), 'heavy': heavy(r['cmd'])})
    return specs, rows, notes


def plan(rows):
    """Groups of identical normalised commands, in order of first appearance: [{key, cmd, heavy, members}]."""
    groups = {}
    for r in rows:
        g = groups.setdefault(r['key'], {'key': r['key'], 'cmd': r['cmd'], 'heavy': r['heavy'], 'members': []})
        g['members'].append(r)
    return list(groups.values())


def estimates(st, root, specs):
    """{group key: seconds} from each spec's previous verify_run (the slowest recorded run of that command)."""
    out = {}
    for s in specs:
        try:
            run = st.ev.latest_verify_run(root, s['name']) or {}
        except Exception:
            run = {}
        for r in run.get('results') or []:
            if not isinstance(r, dict) or r.get('reused') or not isinstance(r.get('secs'), (int, float)):
                continue
            k = group_key(root, r.get('cmd') or '')
            out[k] = max(out.get(k, 0.0), float(r['secs']))
    return out


def savings(st, root, specs, groups):
    """(rows, executions, saved executions, estimated seconds saved or None)."""
    est = estimates(st, root, specs)
    n_rows = sum(len(g['members']) for g in groups)
    saved_s, known = 0.0, False
    for g in groups:
        if g['key'] in est and len(g['members']) > 1:
            saved_s += est[g['key']] * (len(g['members']) - 1)
            known = True
    return n_rows, len(groups), n_rows - len(groups), (round(saved_s, 1) if known else None)


def print_plan(st, root, specs, groups):
    est = estimates(st, root, specs)
    n_rows, n_exec, saved, saved_s = savings(st, root, specs, groups)
    print(f'round plan: {len(specs)} spec(s), {n_rows} functional row(s), {n_exec} execution(s); '
          f'{saved} execution(s) saved' + (f' (~{saved_s:g} s from the previous verify_run)' if saved_s else ''))
    total = 0.0
    for k, g in enumerate(groups, 1):
        secs = est.get(g['key'])
        total += secs or 0.0
        who = ', '.join(f"{m['spec']}:{m['n']}" for m in g['members'])
        print(f"  G{k} x{len(g['members'])}{' heavy' if g['heavy'] else ''}"
              f"{f' ~{secs:g} s' if secs is not None else ' (no previous time)'}: {g['cmd'][:110]}")
        print(f'      rows: {who}')
    if total:
        print(f'estimated round time: ~{round(total, 1):g} s (one execution per group)')


# --- execution ------------------------------------------------------------------------------------------------

def _group_scope(specs_by_name, g):
    """(scope list or None for the whole tree, exclude globs, identity commands, variables)."""
    scope, excl, ident, var_names, whole = set(), set(), set(), set(), False
    for m in g['members']:
        s = specs_by_name[m['spec']]
        if not s['scope']:
            whole = True
        scope.update(s['scope'])
        scope.update(m['inputs'])
        excl.update(s['generated'])
        ident.update(s['identity'])
        var_names.update(s['vars'])
    return (None if whole else sorted(scope)), sorted(excl), sorted(ident), sorted(var_names)


def _execute(st, root, g, specs_by_name, timeout):
    """Run one group once; returns the shared entry {code, note, body, secs, source_spec, source_n, fp, ts, invalid}."""
    src = g['members'][0]
    shared = len(g['members']) > 1
    scope, excl, ident, var_names = _group_scope(specs_by_name, g)
    fp_pre, why = (env_fingerprint(st, root, scope, excl, [g['cmd']], ident, var_names) if shared else (None, None))
    evid = specs_by_name[src['spec']]['dir'] / 'evidence'
    evid.mkdir(parents=True, exist_ok=True)
    tmp = evid / f".round-{st._row_file_id(src['n'], src['i'])}.{os.getpid()}.{id(g)}.out"
    ts = datetime.now().isoformat(timespec='seconds')
    t0 = time.monotonic()
    problem = st.rules.verification_command_problem(g['cmd'], src['expected'], root)
    if problem:
        code, note, body = -1, f'not run: {problem}', ''
    else:
        code, note = st._run_row(g['cmd'], root, tmp, timeout)
        try:
            body = tmp.read_bytes().decode('utf-8', errors='replace')
        except Exception:
            body = ''
    try:
        tmp.unlink()
    except Exception:
        pass
    secs = round(time.monotonic() - t0, 1)
    invalid = None
    fp_post = None
    if shared:
        if fp_pre is None:
            invalid = f'environment fingerprint unavailable ({why}); not shared'
        else:
            fp_post, why2 = env_fingerprint(st, root, scope, excl, [g['cmd']], ident, var_names)
            if fp_post != fp_pre:
                invalid = ('environment fingerprint changed during the execution '
                           f'({fp_pre} -> {fp_post or why2}); not shared')
    return {'code': code, 'note': note, 'body': body, 'secs': secs, 'source_spec': src['spec'],
            'source_n': src['n'], 'fp': fp_pre if shared else 'not-shared', 'ts': ts, 'invalid': invalid}


def _batches(groups, jobs):
    """Heavy groups alone; consecutive light groups in batches of at most `jobs`."""
    out, cur = [], []
    for g in groups:
        if g['heavy'] or jobs <= 1:
            if cur:
                out.append(cur)
                cur = []
            out.append([g])
            continue
        cur.append(g)
        if len(cur) >= jobs:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def round_jobs(specs):
    try:
        env = os.environ.get('AIDD_VERIFY_JOBS', '')
        if env:
            return max(1, min(int(float(env)), 8))
    except Exception:
        pass
    return max(1, min(min((s['jobs'] for s in specs), default=1), 8))


def run_round(st, spec_args, dry_run=False, full=False):
    """The `aidd verify --round` command. Exit 0 only when every spec's verify_run PASSED."""
    root = st.ev.find_root()
    specs, rows, notes = collect(st, root, spec_args)
    for n in notes:
        print(n, flush=True)
    if any(n.startswith('Refused: not a spec directory') for n in notes):
        print('Refused: fix the spec list; nothing was executed.')
        return 1
    if not specs:
        print('Refused: no spec with functional Verification rows; nothing was executed.')
        return 1
    groups = plan(rows)
    print_plan(st, root, specs, groups)
    if dry_run:
        print('dry run: nothing was executed and nothing was recorded.')
        return 0
    by_name = {s['name']: s for s in specs}
    # Code state of each spec BEFORE the first execution: the per-spec stability check covers the whole round.
    starts = {}
    for s in specs:
        st_start = st.ev.code_state(root, budget_s=st._fingerprint_budget(), scope=s['scope'])
        if st_start is None:
            print(f"Refused: cannot fingerprint the verification inputs of {s['name']}; nothing was executed.")
            return 1
        starts[s['name']] = {'started': time.time(), 'fp_start': st.ev.worktree_fingerprint(root), 'st_start': st_start}
    timeout = st._verify_timeout()
    jobs = round_jobs(specs)
    shared = {}
    print(f'round: executing {len(groups)} group(s)' + (f', up to {jobs} light group(s) at a time' if jobs > 1 else
                                                       ', one at a time'), flush=True)
    for batch in _batches(groups, jobs):
        if len(batch) == 1:
            entries = [_execute(st, root, batch[0], by_name, timeout)]
        else:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=len(batch)) as pool:
                entries = list(pool.map(lambda g: _execute(st, root, g, by_name, timeout), batch))
        for g, e in zip(batch, entries):
            state = 'INVALIDATED' if e['invalid'] else ('exit 0' if e['code'] == 0 else f"exit {e['code']}")
            print(f"ROUND group x{len(g['members'])} ({state}, {e['secs']} s, fingerprint {e['fp']}): "
                  f"{g['cmd'][:100]}" + (f" - {e['invalid']}" if e['invalid'] else ''), flush=True)
            for m in g['members']:
                shared[(m['spec'], m['n'])] = e
    worst, out = 0, []
    for s in specs:
        print(f"\n=== aidd verify {s['name']} (round) ===", flush=True)
        rc = st.cmd_verify(str(s['dir']), full=full, round_shared=shared, round_start=starts[s['name']])
        out.append((s['name'], rc))
        worst = max(worst, rc)
    print('\n=== round summary ===')
    n_rows, n_exec, saved, _ = savings(st, root, specs, groups)
    print(f'{n_exec} execution(s) for {n_rows} row(s) ({saved} saved)')
    for name, rc in out:
        print(f"{'PASS' if rc == 0 else 'FAIL'}  {name}")
    return worst


def evidence_line(entry):
    """The `ROUND-SHARED:` second line of a consumer's evidence file."""
    return (f"ROUND-SHARED: ejecutado una vez por {entry['source_spec']} fila {entry['source_n']}, "
            f"huella {entry['fp']}, {entry['ts']}")


# --- suggestions ----------------------------------------------------------------------------------------------

def suggestion(st, root, current=None):
    """One line suggesting a round, or ''. With `current`: only when that spec shares an identical row with
    another open spec (the `aidd verify <spec>` hint); without it: when 2+ open specs have pending verification
    (the `aidd status` / `aidd next` hint). Never raises, never executes a row."""
    try:
        names = open_specs(st, root)
        dirs = {p.name: p for p in st._spec_dirs(root)}
        pending = [n for n in names if n in dirs and (n == current or _pending(st, root, dirs[n]))]
        if current is not None and current not in pending:
            pending.append(current)
        if len(pending) < 2:
            return ''
        specs, rows, _ = collect(st, root, [str(dirs[n]) if n in dirs else n for n in pending])
        groups = [g for g in plan(rows) if len({m['spec'] for m in g['members']}) > 1]
        if current is not None:
            groups = [g for g in groups if any(m['spec'] == current for m in g['members'])]
            if not groups:
                return ''
            others = sorted({m['spec'] for g in groups for m in g['members']} - {current})
            return (f'round: {sum(1 for g in groups for m in g["members"] if m["spec"] == current)} row(s) of '
                    f'{current} are identical to rows of other open specs ({", ".join(others)}); run them ONCE with '
                    f'`aidd verify --round {current} {" ".join(others)}` (preview: add --dry-run).')
        if not groups:
            return ''
        n_rows, n_exec, saved, saved_s = savings(st, root, specs, plan(rows))
        return (f'round: {len(specs)} open specs with pending verification share {len(groups)} identical row '
                f'command(s): `aidd verify --round {" ".join(s["name"] for s in specs)}` runs {n_exec} instead of '
                f'{n_rows} ({saved} saved' + (f', ~{saved_s:g} s' if saved_s else '') + '); preview with --dry-run.')
    except Exception:
        return ''


def _status_module():
    try:
        from . import aidd_status as st  # type: ignore
    except ImportError:
        import aidd_status as st  # type: ignore
    return st


if __name__ == '__main__':   # `python aidd_round.py <spec>... [--dry-run]` (same as `aidd verify --round`)
    _args = sys.argv[1:]
    sys.exit(_status_module().main(['verify', '--round', *_args]))
