"""T-10 performance checklist for spec 007 (scratch only). Writes evidence/perf.txt."""
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(r'D:\Fuentes\AIDD')
HEAD = Path(__file__).resolve().parent / 'head' / 'skill'
NEW = REPO / 'skill'
OUT = REPO / 'specs' / '007-aidd-review-html-close-gate' / 'evidence' / 'perf.txt'
sys.path.insert(0, str(REPO / 'tests'))
lines = []


def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s)
    lines.append(s)


td = Path(tempfile.mkdtemp()).resolve()
root = td / 'proj'
evd = td / 'evd'
root.mkdir()
evd.mkdir()
os.environ['AIDD_EVIDENCE_DIR'] = str(evd)
os.environ['AIDD_TESTING'] = '1'
sys.path.insert(0, str(NEW / 'scripts'))
import gate_fixtures as G  # noqa: E402
import aidd_evidence as EV  # noqa: E402
import aidd_rules as R  # noqa: E402

(root / '.aidd').mkdir()
(root / 'src').mkdir()
(root / 'src' / 'cart.py').write_text('x = 1\n', encoding='utf-8')
ids = [f'F{i:02d}-eDoc-Spec-{i}' for i in range(1, 28)]
sess = 's-perf'
at = G.approved_tasks()
for i, sid in enumerate(ids):
    d = root / 'specs' / sid
    d.mkdir(parents=True)
    (d / 'spec.md').write_text(G.verified_spec(), encoding='utf-8')
    (d / 'tasks.md').write_text(at if sid == 'F23-eDoc-Spec-23' else G.tasks_text(), encoding='utf-8')
t0 = time.time()
n = 0
for k in range(5000):
    sid = ids[k % 27]
    kind = k % 5
    if kind == 0:
        EV.append(root, None, 'spec_edit', path=f'specs/{sid}/tasks.md', spec=sid, file='tasks.md')
    elif kind == 1:
        EV.append(root, None, 'spec_edit', path=f'specs/{sid}/plan.md', spec=sid, file='plan.md')
    elif kind == 2:
        EV.append(root, sess, 'code_edit', path='src/cart.py', target='', active='')
    elif kind == 3:
        EV.append(root, sess, 'prompt', text='hello world ' * 5)
    else:
        EV.append(root, sess, 'subagent', type='g', desc='auditor', head='independent audit', model='sonnet')
    n += 1
EV.append_approved(root, sess, 'F23-eDoc-Spec-23', R.approval_hash(at))
log(f'synthetic log: 27 specs, {n} events appended in {time.time() - t0:.1f}s; project log size',
    sum(p.stat().st_size for p in evd.rglob('*') if p.is_file()), 'bytes')
(root / '.aidd' / 'gate_spec').write_text('F23-eDoc-Spec-23\n', encoding='utf-8')


def time_hook(skill, name, event, reps=7, env=None):
    e = dict(os.environ)
    e.update(env or {})
    ts = []
    rc = None
    for _ in range(reps):
        a = time.perf_counter()
        r = subprocess.run([sys.executable, str(skill / 'hooks' / name)], input=json.dumps(event).encode(),
                           capture_output=True, env=e, timeout=60)
        ts.append(time.perf_counter() - a)
        rc = r.returncode
    return statistics.median(ts), max(ts), rc


import _common  # noqa: E402
_common.marker_path(sess).write_text('invoked', encoding='utf-8')
code_ev = {'session_id': sess, 'cwd': str(root), 'hook_event_name': 'PreToolUse', 'tool_name': 'Write',
           'tool_input': {'file_path': str(root / 'src' / 'app.py'), 'content': 'x'}}
for label, skill in (('HEAD (pre-007)', HEAD), ('working tree (007)', NEW)):
    med, mx, rc = time_hook(skill, 'rule_gate.py', code_ev)
    log(f'rule_gate code write [{label}]: median {med * 1000:.0f} ms, max {mx * 1000:.0f} ms, rc={rc}')
post = {'session_id': sess, 'cwd': str(root), 'hook_event_name': 'PostToolUse', 'tool_name': 'Edit',
        'tool_input': {'file_path': str(root / 'src' / 'cart.py')}}
for label, skill in (('HEAD (pre-007)', HEAD), ('working tree (007)', NEW)):
    med, mx, rc = time_hook(skill, 'mark_code_edit.py', post)
    log(f'mark_code_edit [{label}]: median {med * 1000:.0f} ms, max {mx * 1000:.0f} ms')
stop = {'session_id': sess, 'cwd': str(root), 'hook_event_name': 'Stop'}
for label, skill in (('HEAD (pre-007)', HEAD), ('working tree (007)', NEW)):
    med, mx, rc = time_hook(skill, 'stop_gate.py', stop, reps=3, env={'AIDD_RULES': 'warn'})
    log(f'stop_gate (warn, no budget use) [{label}]: median {med * 1000:.0f} ms, max {mx * 1000:.0f} ms')

# in-process function costs
a = time.perf_counter()
for _ in range(20):
    EV.gate_target_specs(root)
log(f'gate_target_specs (pointer) in-process: {(time.perf_counter() - a) / 20 * 1000:.1f} ms/call')
(root / '.aidd' / 'gate_spec').unlink()
a = time.perf_counter()
for _ in range(20):
    tg = EV.gate_target_specs(root)
log(f'gate_target_specs (inferred scan) in-process: {(time.perf_counter() - a) / 20 * 1000:.1f} ms/call -> {tg}')
a = time.perf_counter()
for _ in range(20):
    EV.open_specs(root)
log(f'open_specs alone: {(time.perf_counter() - a) / 20 * 1000:.1f} ms/call')
a = time.perf_counter()
for _ in range(20):
    EV.last_code_edit_ts(root)
log(f'last_code_edit_ts: {(time.perf_counter() - a) / 20 * 1000:.1f} ms/call')

# worktree_fingerprint on this repo (git) and on a non-git copy
for budget in (8.0,):
    a = time.perf_counter()
    fp = EV.worktree_fingerprint(REPO, budget)
    log(f'worktree_fingerprint(D:/Fuentes/AIDD, git) = {fp} in {(time.perf_counter() - a) * 1000:.0f} ms')
a = time.perf_counter()
fp = EV.worktree_fingerprint(Path(os.path.expanduser('~')) / 'AppData' / 'Local' / 'Programs', 8.0)
log(f'worktree_fingerprint(large non-git dir) = {fp} in {(time.perf_counter() - a) * 1000:.0f} ms (None = over cap/budget)')

# generate on an F13-sized spec: 84 KB tasks.md, 151 headings, five sources
import aidd_review as RV  # noqa: E402
d = root / 'specs' / 'F13-big'
d.mkdir()
(d / 'spec.md').write_text(G.verified_spec() + ''.join(f'\n## Spec sec {i}\n\ntext {i}\n' for i in range(9)),
                           encoding='utf-8')
(d / 'plan.md').write_text('# plan\n' + ''.join(f'\n## Plan sec {i}\n\n| a | b |\n|---|---|\n| x | y |\n' for i in range(16)),
                           encoding='utf-8')
body = ''.join(f'\n### T-{i:03d}\n- Agent min: 5\n- Human ref hours: 1\n- Tokens (est): 10k\n- Agent role: builder\n'
               f'- Model tier: medium\n' + ('Some long description of the task with `code` and **bold**. ' * 9) + '\n'
               for i in range(104))
(d / 'tasks.md').write_text(G.tasks_text().replace('## Waves', body + '\n## Waves'), encoding='utf-8')
(d / 'mockup-audit.md').write_text('# m\n' + ''.join(f'\n## M {i}\n' for i in range(7)), encoding='utf-8')
(d / 'contracts.md').write_text('# c\n' + ''.join(f'\n## C {i}\n' for i in range(13)), encoding='utf-8')
log('F13-like tasks.md bytes:', (d / 'tasks.md').stat().st_size, '| reviewable keys:', len(RV.reviewable_keys(d)))
a = time.perf_counter()
p, wrote = RV.generate(d)
log(f'generate (first): {(time.perf_counter() - a) * 1000:.0f} ms, wrote={wrote}, html {p.stat().st_size} bytes')
a = time.perf_counter()
p, wrote = RV.generate(d)
log(f'generate (idempotent): {(time.perf_counter() - a) * 1000:.0f} ms, wrote={wrote}')
a = time.perf_counter()
for _ in range(5):
    RV.review_state(d)
log(f'review_state: {(time.perf_counter() - a) / 5 * 1000:.0f} ms/call')
OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
