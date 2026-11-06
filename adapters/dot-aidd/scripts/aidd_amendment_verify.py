"""aidd:FR-450..FR-458 `aidd verify <spec> --amendment NN [--dry-run]` and `aidd verify <spec> --dry-run`
(amendment 11 of spec 007: amendment-scoped verification).

1. The amendment declares the files it touches in `specs/<spec>/tasks-amendment-NN.md`: backticked paths on
   `Files to change:` lines, the `Target file` table column, or a fenced block  ```aidd-files  (one path per line).
2. Plan, per functional row of `## Verification` (table order):
   RUN    when the row is `Regression: always`, when a declared file matches its `Inputs` or is named by its command,
          or when its previous PASS cannot be PROVEN still valid;
   REUSED when the proof holds against the spec's latest `verify_run`: previous run stable; same row, normalised
          command and Expected; PASS (exit 0), no lint problem today; not `Reuse: never`; with `Inputs`: same
          declaration and the same `row_input_fingerprint`; without `Inputs`: same Scope and the same whole-Scope
          code fingerprint (today's rule); same environment identity (`env_id`) when the row names a `docker exec`
          container or the spec declares `Round-identity:`/vars; evidence intact (sha1) and valid today.
   Declared files only FORCE executions; they never authorise a reuse, so an undeclared edit cannot give a false
   PASS (the changed row runs, with a warning).
3. The real run goes through `aidd_status.cmd_verify(..., round_start=<state taken before the plan>,
   amendment=...)`: ONE complete `verify_run` (executed + reused rows), the normal stability check, R7/R10 and close
   unchanged. `--dry-run` prints the plan and executes and records nothing.

Lazy-imported by aidd_status (`_amendment_mod`); stdlib only."""
import hashlib
import re
import time
from datetime import datetime
from pathlib import Path

AMEND_NN_RE = re.compile(r'^\d{1,3}$')
_FILES_LINE_RE = re.compile(r'(?im)^[ \t]*(?:[-*][ \t]*)?(?:\*\*)?Files to change(?::\*\*|\*\*:|:)[ \t]*(.*)$')
_BLOCK_RE = re.compile(r'(?ms)^[ \t]*```[ \t]*aidd-files[ \t]*\r?\n(.*?)^[ \t]*```')
_TICK_RE = re.compile(r'`([^`\n]+)`')


def _rnd():
    try:
        from . import aidd_round as mod
    except ImportError:
        import aidd_round as mod
    return mod


def _norm(p):
    p = str(p or '').strip().strip('`').strip().replace('\\', '/')
    while p.startswith('./'):
        p = p[2:]
    return p


def _pathlike(p):
    return bool(p) and '<' not in p and '>' not in p and not any(c.isspace() for c in p) and ('/' in p or '.' in p)


def amendment_file(d, nn):
    """The `tasks-amendment-NN.md` of spec dir `d` (NN zero-padded or not), else None."""
    n = int(nn)
    for name in (f'tasks-amendment-{n:02d}.md', f'tasks-amendment-{nn}.md', f'tasks-amendment-{n}.md',
                 f'tasks-amendment-{n:03d}.md'):
        p = Path(d) / name
        if p.is_file():
            return p
    return None


def amendment_files(st, d, nn):
    """aidd:FR-450 (sorted root-relative declared files, path of the task file). ValueError when the file is
    missing or declares no path."""
    p = amendment_file(d, nn)
    want = f'specs/{Path(d).name}/tasks-amendment-{int(nn):02d}.md'
    if p is None:
        raise ValueError(f'{want} not found (`--amendment {nn}` reads the files it declares: `Files to change:` '
                         'lines, the `Target file` column or an ```aidd-files block)')
    text = p.read_text(encoding='utf-8', errors='replace')
    files = set()
    for m in _FILES_LINE_RE.finditer(text):
        files.update(x for x in (_norm(t) for t in _TICK_RE.findall(m.group(1))) if _pathlike(x))
    for m in _BLOCK_RE.finditer(text):
        for line in m.group(1).splitlines():
            x = _norm(line)
            if x and not x.startswith('#') and _pathlike(x):
                files.add(x)
    try:
        files.update(_norm(x) for x in st.rules.task_targets(text) if _pathlike(_norm(x)))
    except Exception:
        pass
    if not files:
        raise ValueError(f'specs/{Path(d).name}/{p.name} declares no file (write `- **Files to change:** `path``'
                         ' lines or an ```aidd-files block)')
    return sorted(files), p


def _iso(ts):
    try:
        return datetime.fromtimestamp(float(ts)).isoformat(timespec='seconds')
    except Exception:
        return '?'


def reused_line(origin, basis, nn):
    """aidd:FR-452 The `REUSED:` second line of a reused row's evidence file."""
    tail = f'aidd verify --amendment {nn}' if nn else 'aidd verify'
    return (f"REUSED: PASS del verify_run de {origin['spec']} fila {origin['n']} del {origin['date']}, "
            f"huella {origin['code_fp']}, verify hash {origin.get('verify_hash') or '?'}; "
            f"{basis}, comando y entorno sin cambios (no ejecutado: {tail})")


def _reused_evidence(data, line):
    lines = data.decode('utf-8', 'replace').split('\n')
    if len(lines) > 1 and lines[1].startswith('REUSED:'):
        del lines[1]
    lines.insert(1, line)
    return '\n'.join(lines).encode('utf-8')


def plan(st, root, d, rows, state, parts, files, scope, nn=None):
    """aidd:FR-451 One item per row: {n, row, action: RUN|REUSED, reason, entry, warning}. Never raises: any doubt
    means RUN with the reason."""
    rnd = _rnd()
    try:
        prior = st.ev.latest_verify_run(root, d.name)
    except Exception:
        prior = None
    results = [x for x in ((prior or {}).get('results') or []) if isinstance(x, dict)]
    base = Path(d).resolve()
    scope_cache = []

    def scope_proof():
        if scope_cache:
            return scope_cache[0]
        why = None
        try:
            if prior.get('code_algorithm') != st.ev.EVIDENCE_ALGORITHM or not prior.get('code_fp_end'):
                why = 'previous verify_run has no comparable code fingerprint'
            elif sorted(prior.get('code_scope') or []) != sorted(scope or []):
                why = 'Scope changed since the previous verify_run'
            elif state is None:
                why = 'cannot prove reuse: the code fingerprint of the Scope cannot be computed (budget)'
            else:
                now = rnd._code_fp_now(st, state, prior)
                if now is None:
                    why = 'cannot prove reuse: the code fingerprint of the Scope cannot be computed now'
                elif now != prior.get('code_fp_end'):
                    why = ('row declares no Inputs and code in Scope changed since its last PASS '
                           '(declare `Inputs` to scope this row)')
        except Exception as e:
            why = f'cannot prove reuse: scope check failed ({type(e).__name__})'
        scope_cache.append(why)
        return why

    def prove(r, n):
        """(None, entry) when the reuse is proven, else (reason, None)."""
        inputs = r.get('inputs') or []
        if r.get('reuse') == 'never':
            return '`Reuse: never`', None
        if not prior:
            return 'no previous verify_run of this spec', None
        if prior.get('stable') is not True:
            return 'previous verify_run was not stable', None
        res = next((x for x in results if str(x.get('n')) == n), None)
        if res is None:
            return 'new row (not in the previous verify_run)', None
        if rnd.normalize_command(res.get('cmd') or '') != rnd.normalize_command(r['cmd']):
            return 'command changed since its last PASS', None
        if str(res.get('expected') or '').strip() != str(r.get('expected') or 'exit 0').strip():
            return 'Expected changed since its last PASS', None
        if res.get('ok') is not True or res.get('exit') != 0:
            return 'previous result was not a PASS', None
        if st.rules.verification_command_problem(r['cmd'], r.get('expected') or 'exit 0', root):
            return 'the command has a lint problem today', None
        input_fp = None
        if inputs:
            if (list(res.get('input_globs') or []) != list(inputs)
                    or res.get('input_algorithm') != st.ev.EVIDENCE_ALGORITHM):
                return 'Inputs declaration changed since its last PASS', None
            input_fp = st.rules.row_input_fingerprint(root, inputs)
            if not input_fp:
                return 'cannot prove reuse: its Inputs cannot be fingerprinted (missing or unsafe path)', None
            if input_fp != res.get('input_fp'):
                return 'Inputs changed since its last PASS', None
            basis, kind = 'Inputs', 'amendment-inputs'
        elif res.get('input_globs'):
            return 'Inputs declaration changed since its last PASS', None
        else:
            why = scope_proof()
            if why:
                return why, None
            basis, kind = 'Scope', 'amendment-scope'
        env_id = rnd.row_env_id(parts, r['cmd'])
        if env_id is None:
            return ('cannot prove reuse: environment identity unavailable now (docker inspect or '
                    '`Round-identity:` failed)'), None
        if env_id and res.get('env_id') != env_id:
            if not res.get('env_id'):
                return f'cannot prove reuse: {rnd.NO_ENV_ID_REASON}', None
            return 'environment identity changed since its last PASS', None
        try:
            p = (base / str(res.get('evidence') or '')).resolve()
            p.relative_to(base)
            data = p.read_bytes()
        except Exception:
            return 'cannot prove reuse: previous evidence file unreadable', None
        want = str(res.get('sha1') or '').lower()
        if len(want) < 40 or hashlib.sha1(data).hexdigest() != want:
            return 'cannot prove reuse: previous evidence file missing or changed', None
        if not st._cached_pass_valid(data, res, r.get('expected') or 'exit 0'):
            return "previous evidence does not satisfy today's PASS rules", None
        origin = dict(res['reused_from']) if isinstance(res.get('reused_from'), dict) else {
            'spec': d.name, 'n': n, 'date': _iso(prior.get('started')),
            'code_fp': prior.get('code_fp_end'), 'verify_hash': prior.get('verify_hash') or '',
            'secs': float(res.get('secs') or 0.0)}
        if not origin.get('code_fp'):
            origin['code_fp'] = prior.get('code_fp_end') or '?'
        entry = {'data': _reused_evidence(data, reused_line(origin, basis, nn)), 'origin': origin,
                 'secs': float(origin.get('secs') or 0.0), 'env_id': env_id, 'input_fp': input_fp, 'result': res,
                 'kind': kind, 'why': f'{basis} unchanged since its last PASS'}
        return None, entry

    out = []
    for i, r in enumerate(rows, 1):
        n = str(r.get('n') or i)
        item = {'n': n, 'row': r, 'action': 'RUN', 'reason': '', 'entry': None, 'warning': None}
        try:
            inputs = r.get('inputs') or []
            cmd = str(r.get('cmd') or '').replace('\\', '/')
            in_hit = next((f for f in files if f in inputs or (inputs and st.rules._glob_hit(f, inputs))), None)
            cmd_hit = next((f for f in files if f in cmd), None)
            if r.get('regression') == 'always':
                item['reason'] = 'Regression: always'
            elif in_hit:
                item['reason'] = f'Inputs match amendment file {in_hit}'
            elif cmd_hit:
                item['reason'] = f'command names amendment file {cmd_hit}'
            else:
                why, entry = prove(r, n)
                if entry is not None:
                    item.update(action='REUSED', reason=entry['why'], entry=entry)
                else:
                    item['reason'] = why
                    if nn and why == 'Inputs changed since its last PASS':
                        item['warning'] = (f'warning: row {n}: its Inputs changed since its last PASS but amendment '
                                           f'{nn} declares none of them (undeclared change?)')
        except Exception as e:
            item.update(action='RUN', reason=f'cannot prove reuse: plan failed ({type(e).__name__})', entry=None)
        out.append(item)
    return out


def print_plan(spec, items, perf_rows, nn, files, plain=False):
    """aidd:FR-458 One line per row and the savings summary."""
    if nn:
        shown = ', '.join(files[:8]) + (f' (+{len(files) - 8} more)' if len(files) > 8 else '')
        print(f'amendment {nn} of {spec} declares {len(files)} file(s): {shown}')
    saved = 0.0
    k_run = k_reused = 0
    for it in items:
        if plain:
            extra = (f" (with --amendment NN it would be REUSED: {it['reason']})" if it['action'] == 'REUSED' else '')
            print(f"RUN    {it['n']}: a plain `aidd verify` runs every functional row{extra}")
            k_run += 1
            if it['action'] == 'REUSED':
                saved += float(it['entry'].get('secs') or 0.0)
            continue
        if it['action'] == 'REUSED':
            e = it['entry']
            o = e['origin']
            saved += float(e.get('secs') or 0.0)
            k_reused += 1
            print(f"REUSED {it['n']}: {it['reason']} (PASS of {o.get('date')}, huella {o.get('code_fp')}, "
                  f"~{float(e.get('secs') or 0.0):g} s saved)")
        else:
            k_run += 1
            print(f"RUN    {it['n']}: {it['reason']}")
        if it.get('warning'):
            print(it['warning'])
    for r in perf_rows:
        print(f"PERF   {r.get('n') or '?'}: not run (Tier: perf runs once per spec before close: "
              f"aidd verify {spec} --perf)")
    if plain:
        print(f'plan {spec}: {k_run} row(s) to RUN, {len(perf_rows)} perf row(s) not run; '
              f'`--amendment NN` could reuse {sum(1 for x in items if x["action"] == "REUSED")} of them '
              f'(~{round(saved, 1):g} s from the previous verify_run)')
    else:
        print(f'plan {spec}: {k_run} row(s) to RUN, {k_reused} REUSED, {len(perf_rows)} perf row(s) not run; '
              f'~{round(saved, 1):g} s saved versus running every row (from the previous verify_run)')


def run(st, spec_arg, nn=None, dry_run=False):
    """`aidd verify <spec> --amendment NN [--dry-run]` / `aidd verify <spec> --dry-run`."""
    root = st.ev.find_root()
    d = st._resolve_spec(spec_arg, root)
    if d is None:
        print(f'Refused: not a spec directory: {spec_arg}; nothing was executed.')
        return 1
    root = st.ev.find_root(d)
    spec_text = st._read(d / 'spec.md')
    rows = st.rules.parse_verification(spec_text)
    if not rows:
        print(f'Refused: {d.name}/spec.md has no runnable "## Verification" row - nothing was executed.')
        return 1
    files = []
    if nn:
        try:
            files, _src = amendment_files(st, d, nn)
        except (OSError, ValueError) as e:
            print(f'Refused: {e}; nothing was executed.')
            return 1
    functional = [r for r in rows if st.rules.row_tier(r) != 'perf']
    perf_rows = [r for r in rows if st.rules.row_tier(r) == 'perf']
    if not functional:
        print(f'Refused: every Verification row of {d.name} is `Tier: perf`; run `aidd verify {d.name} --perf`. '
              'Nothing was executed.')
        return 1
    scope = st.rules.verification_scope(spec_text, st._read_tasks(d))
    gen = st.rules.verification_generated(spec_text)
    try:
        st.ev._scope_re(scope)
        st.ev._scope_re(gen)
    except (ValueError, re.error):
        print('Refused: invalid Scope or Generated pattern; nothing was executed.')
        return 1
    for r in functional:
        if r.get('inputs') and not st.rules.row_input_fingerprint(root, r['inputs']):
            if not dry_run:
                print(f"Refused: row {r.get('n') or '?'} has missing or invalid Inputs; nothing was executed.")
                return 1
            print(f"note: row {r.get('n') or '?'} has missing or invalid Inputs; the real run would refuse.")
    started = time.time()
    fp_start = st.ev.worktree_fingerprint(root)
    state = st.ev.code_state(root, budget_s=st._fingerprint_budget(), scope=scope, skip=gen)
    if state is None:
        if not dry_run:
            print(st.fingerprint_refusal(d.name, 'nothing was executed'), flush=True)
            return 1
        print('note: ' + st.fingerprint_refusal(d.name, 'the real run would refuse to start'), flush=True)
    rnd = _rnd()
    try:
        spec_info = {'identity': rnd.identity_commands(spec_text),
                     'vars': rnd.declared_vars(st, spec_text, functional)}
        parts = rnd.env_parts(st, root, spec_info, [r['cmd'] for r in functional])
    except Exception:
        parts = None          # row_env_id(None) = unavailable: rows that need an identity run (fail closed)
    items = plan(st, root, d, functional, state, parts, files, scope, nn)
    print_plan(d.name, items, perf_rows, nn, files, plain=not nn)
    if dry_run:
        print('dry run: nothing was executed and nothing was recorded.')
        return 0
    reused = {it['n']: it['entry'] for it in items if it['action'] == 'REUSED'}
    return st.cmd_verify(str(d), round_start={'started': started, 'fp_start': fp_start, 'st_start': state},
                         amendment={'id': nn, 'files': files, 'reused': reused})


def main(st, args):
    """Argument parsing for the `--amendment` / `--dry-run` forms (args = everything after `verify`)."""
    args = list(args)
    nn = None
    if '--amendment' in args:
        if args.count('--amendment') != 1:
            print('Refused: --amendment may appear only once; nothing was executed.')
            return 1
        pos = args.index('--amendment')
        value = args[pos + 1] if pos + 1 < len(args) else ''
        if not AMEND_NN_RE.match(value):
            print('Refused: --amendment requires the amendment number (1-3 digits, e.g. `--amendment 07`); '
                  'nothing was executed.')
            return 1
        nn = value
        args = args[:pos] + args[pos + 2:]
    if args.count('--dry-run') > 1:
        print('Refused: --dry-run may appear only once; nothing was executed.')
        return 1
    dry = '--dry-run' in args
    args = [a for a in args if a != '--dry-run']
    others = [a for a in args if a.startswith('-')]
    what = '--amendment' if nn else '--dry-run'
    if others:
        print(f'Refused: {what} cannot be combined with {", ".join(others)} (use `--full` alone to run every row, '
              f'`--round ... --dry-run` for a round plan); nothing was executed.')
        return 1
    if len(args) != 1:
        print(f'Refused: {what} takes exactly one spec; nothing was executed.')
        return 1
    return run(st, args[0], nn, dry)
