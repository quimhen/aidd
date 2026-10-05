"""T-10 closing audit harness for spec 007: executes AC-201, AC-202, AC-205..AC-218 in SCRATCH projects
(gate_fixtures.Base: temp project + AIDD_EVIDENCE_DIR scratch log, AIDD_TESTING=1). Never touches the real log.
Each test writes specs/007-aidd-review-html-close-gate/evidence/ac-<n>.txt with its transcript and verdict."""
import io
import json
import os
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(r'D:\Fuentes\AIDD')
sys.path.insert(0, str(REPO / 'tests'))
import gate_fixtures as G  # noqa: E402
from gate_fixtures import EV, R  # noqa: E402
sys.path.insert(0, str(REPO / 'skill' / 'scripts'))
sys.path.insert(0, str(REPO / 'skill' / 'hooks'))
import aidd_review as RV  # noqa: E402

OUT = REPO / 'specs' / '007-aidd-review-html-close-gate' / 'evidence'
OUT.mkdir(parents=True, exist_ok=True)
SCRIPTS = REPO / 'skill' / 'scripts'
HOOKS = REPO / 'skill' / 'hooks'

PENDING14 = ['F13-eDoc-Emission-Engine', 'F14-eDoc-A', 'F15-eDoc-B', 'F16-eDoc-C', 'F17-eDoc-D', 'F18-eDoc-E',
             'F19-eDoc-F', 'F20-eDoc-G', 'F21-eDoc-Inventory', 'F22-eDoc-Pricing', 'F23-eDoc-POS',
             'F24-eDoc-Traceability', 'F26-eDoc-Tax-Catalogs', 'F27-Correction-Backlog']
F23 = 'F23-eDoc-POS'


def status_tasks(status=''):
    t = G.tasks_text()
    return t.replace('| Task | Codes |\n|---|---|\n| T-01 | COMP-001 |',
                     f'| Task | Codes | Status |\n|---|---|---|\n| T-01 | COMP-001 | {status} |')


class A(G.Base):
    AC = 'x'

    def setUp(self):
        super().setUp()
        self.buf = []
        self.verdicts = []
        os.environ.pop('AIDD_R5_AUDIT', None)
        self.env.pop('AIDD_R5_AUDIT', None)
        (self.root / '.aidd').mkdir(exist_ok=True)
        self.marker()

    def tearDown(self):
        ok = all(v for _n, v in self.verdicts) and bool(self.verdicts)
        head = f'{self.AC}: {"PASS" if ok else "FAIL"}\n' + '\n'.join(
            f'  [{"PASS" if v else "FAIL"}] {n}' for n, v in self.verdicts)
        try:
            (OUT / f'{self.AC.lower()}.txt').write_text(head + '\n\n' + '\n'.join(self.buf) + '\n', encoding='utf-8',
                                                        newline='\n')
        finally:
            super().tearDown()

    # ---- helpers
    def log(self, *a):
        self.buf.append(' '.join(str(x) for x in a))

    def check(self, name, cond, detail=''):
        self.verdicts.append((name, bool(cond)))
        self.log(f'--> {"PASS" if cond else "FAIL"}: {name}' + (f' | {detail}' if detail else ''))

    def mk_spec(self, sid, tasks=None, spec=None, open_=True):
        d = self.root / 'specs' / sid
        d.mkdir(parents=True, exist_ok=True)
        self.put(f'specs/{sid}/spec.md', spec if spec is not None else G.verified_spec(), age=300)
        if tasks is not False:
            self.put(f'specs/{sid}/tasks.md', tasks if tasks is not None else G.tasks_text(), age=300)
        if open_:
            self.spec_edit('tasks.md', sid)
        return d

    def cli(self, *args, env=None, stdin=subprocess.DEVNULL):
        e = dict(self.env)
        e['AIDD_SESSION_ID'] = self.session
        e.update(env or {})
        r = subprocess.run([sys.executable, str(SCRIPTS / 'aidd_status.py'), *args], cwd=str(self.root), env=e,
                           capture_output=True, timeout=300, stdin=stdin)
        out = r.stdout.decode('utf-8', 'replace') + r.stderr.decode('utf-8', 'replace')
        self.log(f'$ aidd_status.py {" ".join(args)}  -> exit {r.returncode}\n{out.rstrip()}')
        return r.returncode, out

    def review(self, *args, env=None):
        e = dict(self.env)
        e.update(env or {})
        r = subprocess.run([sys.executable, str(SCRIPTS / 'aidd_review.py'), *args], cwd=str(self.root), env=e,
                           capture_output=True, timeout=120)
        out = r.stdout.decode('utf-8', 'replace') + r.stderr.decode('utf-8', 'replace')
        self.log(f'$ aidd_review.py {" ".join(args)}  -> exit {r.returncode}\n{out.rstrip()}')
        return r.returncode, out

    def hook(self, name, event, env=None):
        r = self.run_hook(name, event, env=env)
        self.log(f'[hook {name} {event.get("tool_name", event.get("hook_event_name", ""))}] rc={r.returncode} '
                 f'stdout={r.out.strip()[:600]!r} stderr={r.err.strip()[:900]!r}')
        return r

    def g(self, path, tool='Write', env=None, **ti):
        r = self.gate(path, tool=tool, env=env, **ti)
        self.log(f'[gate {tool} {path}] rc={r.returncode} stderr={r.err.strip()[:900]!r}')
        return r

    def b(self, cmd, cwd=None, env=None):
        r = self.bash(cmd, env=env, cwd=cwd)
        self.log(f'[bash] {cmd!r} cwd={cwd or "root"} rc={r.returncode}')
        return r

    def write_review(self, d, keys=None, approved=True, uncheck=None, comment_key=None, tasks_hash=None,
                     digest=None, newer=True):
        t = (d / 'tasks.md').read_text(encoding='utf-8')
        keys = keys if keys is not None else RV.reviewable_keys(d)
        lines = ['---', f'spec: {d.name}', f'tasks_hash: {tasks_hash or R.approval_hash(t)}',
                 f'sources_digest: {digest or RV.sources_digest(d)}', f'approved: {"true" if approved else "false"}',
                 'generated: 2026-10-05', 'reviewed: 2026-10-05T10:00:00', '---']
        for k in keys:
            lines.append(f'## {k}')
            lines.append('- [ ] Approved' if k == uncheck else '- [x] Approved')
            if k == comment_key:
                lines.append('> please rename this section')
        p = d / 'review.md'
        p.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
        now = time.time()
        if (d / 'review.html').exists():
            os.utime(d / 'review.html', (now - 60, now - 60))
        tt = now - 30 if newer else now - 90
        os.utime(p, (tt, tt))
        return p

    def code_write(self, rel='src/app.py'):
        return self.g(rel, content='x = 1\n')


# ------------------------------------------------------------------------------------------- AC-201
class T201(A):
    AC = 'AC-201'

    def test(self):
        for sid in PENDING14:
            self.mk_spec(sid)
        (self.root / '.aidd' / 'gate_spec').write_text(F23 + '\n', encoding='utf-8')
        self.log('gate_target_specs ->', EV.gate_target_specs(self.root))
        # F23 approved and recorded
        at = G.approved_tasks()
        self.put(f'specs/{F23}/tasks.md', at)
        EV.append_approved(self.root, self.session, F23, R.approval_hash(at))
        r = self.code_write()
        self.check('F23 approved+recorded: code write allowed although 13 others PENDING', r.returncode == 0, r.err[:200])
        # F23 PENDING
        self.put(f'specs/{F23}/tasks.md', G.tasks_text())
        r = self.code_write()
        n = r.err.count('Code edits are blocked')
        self.check('F23 PENDING: write blocked', r.returncode == 2)
        self.check('exactly ONE violation message', n == 1, f'count={n}')
        self.check('names F23, "pointer" and the unblock path',
                   F23 in r.err and 'pointer' in r.err and 'aidd review' in r.err and 'aidd rules approve' in r.err)
        others = [s for s in PENDING14 if s != F23 and s in r.err]
        self.check('no other spec named', not others, str(others))


# ------------------------------------------------------------------------------------------- AC-202
class T202(A):
    AC = 'AC-202'

    def test(self):
        import rule_gate
        for sid in PENDING14:
            self.mk_spec(sid)
        f28 = self.root / 'specs' / 'F28-DB-Unification-Sync'
        f28.mkdir(parents=True)
        self.put('specs/F28-DB-Unification-Sync/spec.md', G.verified_spec())
        self.spec_edit('spec.md', 'F28-DB-Unification-Sync')
        (self.root / '.aidd' / 'active_spec').write_text('F28-DB-Unification-Sync\n1.0\n', encoding='utf-8')
        self.spec_edit('plan.md', F23)
        tgt = EV.gate_target_specs(self.root)
        self.log('(1) gate_target_specs ->', tgt)
        self.check('(1) target = F23 inferred', tgt == ([F23], False, 'inferred'))
        r = self.code_write()
        self.check('(1) ONE violation naming F23 and "inferred", never F28',
                   r.returncode == 2 and r.err.count('Code edits are blocked') == 1 and F23 in r.err
                   and 'inferred' in r.err and 'F28' not in r.err)
        # SECURITY PROBE: no pointer; inferred target flips to an approved spec on a hash-neutral tasks.md edit
        at = G.approved_tasks()
        self.put('specs/F22-eDoc-Pricing/tasks.md', at)
        EV.append_approved(self.root, self.session, 'F22-eDoc-Pricing', R.approval_hash(at))
        r0 = self.code_write()
        self.spec_edit('tasks.md', 'F22-eDoc-Pricing')      # e.g. a Status write-back of the approved F22
        tflip = EV.gate_target_specs(self.root)
        r1 = self.code_write()
        self.log('PROBE inferred flip: before rc', r0.returncode, '| after F22 tasks.md edit target', tflip,
                 'rc', r1.returncode, '| gate_pointer events:', len(EV.events(self.root, kind='gate_pointer')))
        self.spec_edit('plan.md', F23)
        # (2) ambiguous: unreachable with real events (open_specs requires a plan/tasks spec_edit); show it
        self.check('(2a) real log: 14 open specs always infer (ambiguous branch unreachable without mocks)',
                   EV.gate_target_specs(self.root)[2] == 'inferred')
        fake = [f'G{i:02d}-x' for i in range(14)]
        with mock.patch.object(EV, 'open_specs', return_value=fake):
            tgt2 = EV.gate_target_specs(self.root)
            vs = rule_gate._code_gate(EV, R, [self.root])
        self.log('(2b) mocked open_specs ->', tgt2, '\n', json.dumps(vs, indent=1))
        self.check('(2b) mocked: ONE violation, 5 ids "and 9 more", `aidd rules activate`',
                   tgt2 == ([], True, 'ambiguous') and len(vs) == 1 and 'and 9 more' in vs[0]['message']
                   and 'aidd rules activate' in vs[0]['fix'] and all(f in vs[0]['message'] for f in fake[:5]))
        # (3) F99-none treated as unset
        (self.root / '.aidd' / 'gate_spec').write_text('F99-none\n', encoding='utf-8')
        tgt3 = EV.gate_target_specs(self.root)
        self.log('(3) gate_spec=F99-none ->', tgt3)
        self.check('(3) F99-none treated as unset (falls back to inferred)', tgt3 == ([F23], False, 'inferred'))
        rc, out = self.cli('rules', 'activate', 'F13-eDoc-Emission-Engine')
        gp = (self.root / '.aidd' / 'gate_spec').read_text(encoding='utf-8').strip()
        evs = EV.events(self.root, kind='gate_pointer')
        self.check('(3) activate sets gate_spec and appends gate_pointer',
                   rc == 0 and gp == 'F13-eDoc-Emission-Engine' and evs
                   and evs[-1]['detail'].get('spec') == 'F13-eDoc-Emission-Engine'
                   and evs[-1]['detail'].get('prev') == 'F99-none', f'{gp} {evs[-1]["detail"] if evs else None}')
        # R9: agent cannot write the pointers
        bl = []
        for p in ('.aidd/gate_spec', '.aidd/active_spec', '.AIDD/GATE_SPEC.', '.aidd/gate_spec::$DATA'):
            bl.append(self.g(p, content='F23-eDoc-POS\n').returncode == 2)
        for c in ('echo F23-eDoc-POS > .aidd/gate_spec', 'echo x > .aidd/active_spec',
                  'cp /tmp/x .aidd/gate_spec', 'cd .aidd && echo F23 > gate_spec',
                  'python -c "open(\'.aidd/gate_spec\',\'w\').write(\'F23\')"'):
            bl.append(self.b(c).returncode == 2)
        self.check('(3) .aidd/gate_spec and active_spec not writable by the agent (Write + Bash)', all(bl), str(bl))
        # spec-file edit moves active_spec but not gate_spec
        sp = str(self.root / 'specs' / 'F24-eDoc-Traceability' / 'spec.md')
        self.hook('mark_code_edit.py', {'session_id': self.session, 'cwd': str(self.root),
                                        'hook_event_name': 'PostToolUse', 'tool_name': 'Write',
                                        'tool_input': {'file_path': sp}})
        act = EV.get_active_spec(self.root)
        gp2 = EV.get_gate_spec(self.root)
        self.check('(3) spec-file edit moves active_spec, NOT gate_spec',
                   act == 'F24-eDoc-Traceability' and gp2 == 'F13-eDoc-Emission-Engine', f'active={act} gate={gp2}')


# ------------------------------------------------------------------------------------------- AC-205
class T205(A):
    AC = 'AC-205'

    def prep(self, sid, tasks=None):
        d = self.mk_spec(sid, tasks=tasks)
        self.put(f'specs/{sid}/plan.md', '# plan\n\n## Approach\n\ntext\n', age=300)
        rc, out = self.review(str(d))
        assert rc == 0, out
        return d

    def test(self):
        d = self.prep(F23)
        t = (d / 'tasks.md').read_text(encoding='utf-8')
        h8 = R.approval_hash(t)[:8]
        tag = f'[tasks:{h8}]'
        keys = RV.reviewable_keys(d)
        self.write_review(d, comment_key=keys[0])
        st = RV.review_state(d)
        self.log('review_state:', {k: st[k] for k in ('present', 'valid', 'hash_ok', 'digest_ok', 'fresh',
                                                     'page_current', 'complete', 'reason')})
        self.check('complete review.md downloaded after review.html', st['complete'])
        rc, out = self.cli('rules', 'approve', str(d))
        self.check('only review.md, no TTY: REFUSED with the owner-consent message',
                   rc != 0 and 'review.md is complete; the owner must confirm' in out and tag in out
                   and f'approve {tag}' in out)
        self.prompt(f'do not approve {tag}')
        rc, out = self.cli('rules', 'approve', str(d))
        self.check('"do not approve <tag>" prompt does not count', rc != 0)
        self.prompt(f'looks fine {tag}')
        rc, out = self.cli('rules', 'approve', str(d))
        self.check('tagged prompt without an approve word does not count', rc != 0)
        self.prompt(f'approve {tag}')
        rc, out = self.cli('rules', 'approve', str(d))
        t2 = (d / 'tasks.md').read_text(encoding='utf-8')
        a = EV.latest_approved(self.root, F23)
        self.log('approved event:', a)
        self.check('prompt `approve <tag>` newer than review.md: approves',
                   rc == 0 and re.search(r'^Approved: \d{4}-\d\d-\d\d hash:[0-9a-f]{12}$', t2, re.M) is not None)
        self.check('approved{gate:2, source:review+prompt, consent_ts, verify_hash, review_sha1}',
                   a and a.get('gate') == 2 and a.get('source') == 'review+prompt' and a.get('consent_ts')
                   and a.get('verify_hash') and a.get('review_sha1'))
        self.check('activates F23 (gate pointer)', EV.get_gate_spec(self.root) == F23)
        self.check('comment on a checked heading printed as a note', 'note: ' + keys[0] in out)
        # answer route on a second spec
        d2 = self.prep('F22-eDoc-Pricing')
        self.write_review(d2)
        t22 = (d2 / 'tasks.md').read_text(encoding='utf-8')
        self.answer('Approve these tasks?', 'Approve', tasks=t22)
        rc, out = self.cli('rules', 'approve', str(d2))
        a2 = EV.latest_approved(self.root, 'F22-eDoc-Pricing')
        self.check('tagged AskUserQuestion Approve answer: approves with source review+answer',
                   rc == 0 and a2 and a2.get('source') == 'review+answer' and a2.get('gate') == 2, str(a2))
        # TTY route (in-process, injected TTY)
        d3 = self.prep('F21-eDoc-Inventory', tasks=G.tasks_text(ids='COMP-009'))
        self.write_review(d3)
        t3 = (d3 / 'tasks.md').read_text(encoding='utf-8')
        import aidd_status as S
        tag3 = S.approval_tag(t3)
        self.check('_tty_confirm: non-TTY -> False', S._tty_confirm(tag3, isatty=False, reader=lambda p: f'approve {tag3}') is False)
        self.check('_tty_confirm: TTY + typed tag -> True', S._tty_confirm(tag3, isatty=True, reader=lambda p: f'approve {tag3}') is True)
        self.check('_tty_confirm: TTY + wrong text -> False', S._tty_confirm(tag3, isatty=True, reader=lambda p: 'yes') is False)
        os.environ['AIDD_SESSION_ID'] = self.session
        try:
            with mock.patch.object(S, '_tty_confirm', lambda tag: tag == tag3):
                buf = io.StringIO()
                with mock.patch('sys.stdout', buf):
                    rc3 = S.cmd_approve(str(d3))
            self.log('in-process cmd_approve (TTY injected):', rc3, buf.getvalue())
        finally:
            os.environ.pop('AIDD_SESSION_ID', None)
        a3 = EV.latest_approved(self.root, 'F21-eDoc-Inventory')
        self.check('TTY with the typed tag: source review+tty', rc3 == 0 and a3 and a3.get('source') == 'review+tty', str(a3))


# ------------------------------------------------------------------------------------------- AC-206
class T206(A):
    AC = 'AC-206'

    def test(self):
        d = self.mk_spec(F23, tasks=status_tasks(''))
        self.log('check_content(tasks) on the Status-column fixture:', R.check_content('tasks', status_tasks('')))
        self.put(f'specs/{F23}/plan.md', '# plan\n\n## Approach\n\ntext\n', age=300)
        self.review(str(d))
        self.write_review(d)
        old = R.approval_hash((d / 'tasks.md').read_text(encoding='utf-8'))
        # (b) Status cell only
        self.put(f'specs/{F23}/tasks.md', status_tasks('done'), age=300)
        rc, out = self.review(str(d), '--check')
        self.check('(b) Status-cell-only edit: review still complete (--check exit 0)', rc == 0)
        # (a) title cell edit
        self.put(f'specs/{F23}/tasks.md', status_tasks('done').replace('| T-01 | COMP-001 |', '| T-01 | COMP-002 |'),
                 age=300)
        new = R.approval_hash((d / 'tasks.md').read_text(encoding='utf-8'))
        rc, out = self.cli('rules', 'approve', str(d))
        self.check('(a) title-cell edit refused: "generated for tasks hash X; current is Y: run aidd review again"',
                   rc != 0 and old in out and new in out and 'aidd review' in out)
        # restore (b) and approve via prompt; then (c)
        self.put(f'specs/{F23}/tasks.md', status_tasks('done'), age=300)
        t = (d / 'tasks.md').read_text(encoding='utf-8')
        self.prompt(f'approve [tasks:{R.approval_hash(t)[:8]}]')
        rc, out = self.cli('rules', 'approve', str(d))
        self.check('(b) approve still works after the Status-only edit', rc == 0)
        m0 = os.path.getmtime(d / 'review.html')
        rc, out = self.review(str(d), '--check')
        self.check('(c) after approve rewrote the Approved: line: --check exit 0', rc == 0)
        rc2, out2 = self.review(str(d))
        self.check('(c) `aidd review` does not rewrite the page',
                   rc2 == 0 and 'unchanged' in out2 and os.path.getmtime(d / 'review.html') == m0)
        # (d) digest mismatch: plan.md edited -> refused the same way (on a fresh spec)
        d2 = self.mk_spec('F22-eDoc-Pricing')
        self.put('specs/F22-eDoc-Pricing/plan.md', '# plan\n\n## A\n', age=300)
        self.review(str(d2))
        self.write_review(d2)
        self.put('specs/F22-eDoc-Pricing/plan.md', '# plan\n\n## A\n\nchanged\n', age=300)
        t2 = (d2 / 'tasks.md').read_text(encoding='utf-8')
        self.prompt(f'approve [tasks:{R.approval_hash(t2)[:8]}]')
        rc, out = self.cli('rules', 'approve', str(d2))
        self.check('(d) sources_digest mismatch (plan.md edited) refused and asks for `aidd review` again',
                   rc != 0 and 'aidd review' in out and ('digest' in out.lower() or 'sources' in out.lower()))


# ------------------------------------------------------------------------------------------- AC-207
class T207(A):
    AC = 'AC-207'

    def test(self):
        ids = ['F13-eDoc-Emission-Engine', F23, '002-aidd-hard-rules']
        for sid in ids:
            d = self.mk_spec(sid)
            self.put(f'specs/{sid}/plan.md', '# plan\n\n## A\n', age=300)
        res = []
        for sid in ids:
            for name in ('review.md', 'REVIEW.MD.', 'review.md::$DATA', 'sub/../review.md', 'review.html',
                         'Review.Html ', 'review.html::$DATA'):
                p = f'specs/{sid}/{name}'
                for tool, ti in (('Write', {'content': 'x'}), ('Edit', {'old_string': 'a', 'new_string': 'b'}),
                                 ('MultiEdit', {'edits': [{'old_string': 'a', 'new_string': 'b'}]}),
                                 ('NotebookEdit', {'new_source': 'x'})):
                    r = self.g(p, tool=tool, **ti)
                    res.append((f'{tool} {p}', r.returncode == 2))
                # absolute too
                r = self.g(str(self.root / 'specs' / sid / name), content='x')
                res.append((f'Write abs {sid}/{name}', r.returncode == 2))
        bad = [n for n, okk in res if not okk]
        self.check(f'file tools blocked on every variant ({len(res)} probes)', not bad, str(bad[:10]))
        R_ = str(self.root).replace('\\', '/')
        cmds = []
        for sid in ids:
            cmds += [f'echo ok > specs/{sid}/review.md', f'echo ok > {R_}/specs/{sid}/review.md',
                     f'cp /tmp/r.md {R_}/specs/{sid}/review.md', f'cd specs/{sid} && echo x > review.md',
                     f'cd specs/{sid} && printf x | tee review.md', f'mv ~/Downloads/review.md {R_}/specs/{sid}/',
                     f'python -c "open(\'specs/{sid}/review.md\',\'w\').write(\'x\')"', f'rm specs/{sid}/review.html',
                     f'Copy-Item C:/Users/x/Downloads/review.md -Destination specs/{sid}/review.md',
                     f'echo x >> specs\\{sid}\\REVIEW.MD']
        blocked = [(c, self.b(c).returncode == 2) for c in cmds]
        bad = [c for c, okk in blocked if not okk]
        self.check(f'Bash forging variants blocked ({len(cmds)} probes, numeric + non-numeric, rel + abs)', not bad,
                   str(bad))
        allowed = [f'cat specs/{F23}/review.md', f'aidd review specs/{F23}', f'aidd review specs/{F23} --check',
                   f'aidd verify specs/{F23}', f'python {SCRIPTS}/aidd_review.py specs/{F23} --check']
        al = [(c, self.b(c).returncode == 0) for c in allowed]
        self.check('reads and `aidd review [--check]` allowed', all(x for _c, x in al), str(al))
        # lexical bypass probes (informational: the spec says the guard is lexical; consent is the trust root)
        sid = F23
        probes = [f"cd specs/{sid} && echo x > rev''iew.md", f'cd specs/{sid} && rm review.*',
                  f'cd specs/{sid} && rm revie?.html', f'cd specs/{sid} && echo x > "review".md']
        pr = [(c, self.b(c).returncode) for c in probes]
        self.log('LEXICAL BYPASS PROBES (rc 0 = allowed):', pr)
        # hand-built complete review.md placed by other means
        d = self.root / 'specs' / sid
        self.review(str(d))
        self.write_review(d)
        st = RV.review_state(d)
        self.check('hand-built file is content-complete', st['complete'])
        rc, out = self.cli('rules', 'approve', str(d))
        self.check('CLI approve refuses it without a consent act', rc != 0 and 'owner must confirm' in out)
        t = (d / 'tasks.md').read_text(encoding='utf-8')
        h = R.approval_hash(t)
        self.ev('find_spec', rebuilt=False, ok=True, source='bash')
        r = self.g(f'specs/{sid}/tasks.md', tool='Edit', old_string='Approved: PENDING',
                   new_string=f'Approved: 2026-10-05 hash:{h}')
        self.check('hook-route Edit adding Approved: line blocked with the same consent message',
                   r.returncode == 2 and 'owner must confirm' in r.err)
        keys = RV.reviewable_keys(d)
        self.write_review(d, uncheck=keys[1])
        rc, out = self.cli('rules', 'approve', str(d))
        self.check('incomplete file names the missing key', rc != 0 and keys[1] in out, keys[1])
        self.write_review(d, newer=False)
        rc, out = self.cli('rules', 'approve', str(d))
        self.check('older-than-html file says "older than review.html"', rc != 0 and 'older than review.html' in out)


# ------------------------------------------------------------------------------------------- AC-208
class T208(A):
    AC = 'AC-208'

    def test(self):
        sid = '006-aidd-phased-audits-attribution'
        at = G.approved_tasks()
        d = self.mk_spec(sid, tasks=at, spec=G.spec_text())      # legacy: no ## Verification
        EV.append_approved(self.root, self.session, sid, R.approval_hash(at))   # no gate
        self.ev('code_edit', path=str(self.root / 'src' / 'cart.py'))
        doms = sorted(R.required_domains(d))
        self.log('required domains:', doms)
        for dom in doms:
            self.ev('subagent', type='general-purpose', desc=f'{dom} auditor', head=f'independent {dom} audit',
                    model='sonnet')
        self.put(f'specs/{sid}/evidence/login.png', 'png', age=5)
        self.put(f'specs/{sid}/qa-audit.md', G.qa_text(G.QA_ROW_OK), age=2)
        rc, out = self.cli('status', str(d))
        self.check('aidd status shows it', rc == 0 and sid in out)
        self.answer(f'Close spec {sid} as completed? [spec:{sid}]', 'Yes, close', tagged=False)
        rc, out = self.cli('rules', 'close', str(d))
        self.check('legacy close via per-domain auditors, no Verification / verify / review demanded',
                   rc == 0 and 'closed as completed' in out and 'verify' not in out.lower().replace('verified', ''))


# ------------------------------------------------------------------------------------------- AC-209 / 216 / 210
class GateTwo(A):
    def gate2_spec(self, rows=None, sid=F23):
        (self.root / 'tests').mkdir(exist_ok=True)
        (self.root / 'tests' / '__init__.py').write_text('', encoding='utf-8')
        (self.root / 'tests' / 'test_ok.py').write_text(
            'import unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertTrue(True)\n',
            encoding='utf-8')
        rows = rows or '| 1 | `python -m unittest tests.test_ok` | exit 0 | FR-001 |\n'
        spec = G.spec_text(extra='\n## Verification\n\n| # | Command | Expected | Covers |\n|---|---|---|---|\n' + rows)
        d = self.mk_spec(sid, spec=spec)
        t = (d / 'tasks.md').read_text(encoding='utf-8')
        self.answer('Approve these tasks?', 'Approve', tasks=t)
        rc, out = self.cli('rules', 'approve', str(d))
        assert rc == 0, out
        return d

    def gaps(self, d):
        g = R.verification_gaps(EV, self.root, d)
        self.log('verification_gaps:', [v['message'] for v in g])
        return g


class T209(GateTwo):
    AC = 'AC-209'

    def test(self):
        d = self.gate2_spec()
        self.check('approved event has gate 2', (EV.latest_approved(self.root, F23) or {}).get('gate') == 2)
        rc, out = self.cli('rules', 'close', str(d))
        self.check('before verify: close refused "no verify_run"', rc != 0 and 'No verify_run recorded' in out)
        rc, out = self.cli('verify', str(d))
        ev1 = d / 'evidence' / 'verify-1.txt'
        self.check('aidd verify exit 0 and evidence/verify-1.txt saved', rc == 0 and ev1.is_file())
        self.check('verification passes (no gaps)', self.gaps(d) == [])
        self.ev('code_edit', path=str(self.root / 'src' / 'cart.py'))
        g = self.gaps(d)
        self.check('later code_edit: stale', any('after the last verify_run started' in v['message'] for v in g))
        rc, out = self.cli('rules', 'close', str(d))
        self.check('close refused while stale', rc != 0 and 'stale' in out)
        rc, out = self.cli('verify', str(d))
        self.check('re-running fixes it', rc == 0 and self.gaps(d) == [])
        ev1.write_text(ev1.read_text(encoding='utf-8') + 'x', encoding='utf-8')
        self.check('editing evidence/verify-1.txt refused (sha1)', any('sha1' in v['message'] for v in self.gaps(d)))
        self.cli('verify', str(d))
        sp = (d / 'spec.md').read_text(encoding='utf-8').replace('| exit 0 | FR-001 |', '| exit 0 | FR-001 |\n'
                                                                  '| 2 | `python -m unittest tests.test_ok` | exit 0 | x |')
        (d / 'spec.md').write_text(sp, encoding='utf-8')
        self.check('editing the table afterwards refused (verify_hash)',
                   any('verify_hash' in v['message'] for v in self.gaps(d)))


class T216(GateTwo):
    AC = 'AC-216'

    def test(self):
        d = self.gate2_spec()
        rc, _ = self.cli('verify', str(d))
        self.check('baseline verify passes', rc == 0 and self.gaps(d) == [])
        # (a) css/json/config via mark_code_edit
        rec = []
        for rel in ('src/app.css', 'appsettings.json', 'web.config'):
            self.put(rel, 'x')
            n0 = len(EV.events(self.root, kind='code_edit'))
            self.hook('mark_code_edit.py', {'session_id': self.session, 'cwd': str(self.root), 'tool_name': 'Edit',
                                            'hook_event_name': 'PostToolUse',
                                            'tool_input': {'file_path': str(self.root / rel)}})
            rec.append(len(EV.events(self.root, kind='code_edit')) == n0 + 1)
        last = EV.events(self.root, kind='code_edit')[-1]['detail']
        self.log('last code_edit detail:', last)
        self.check('(a) .css/.json/web.config recorded as code_edit (stamped target/active)',
                   all(rec) and last.get('target') == F23 and 'active' in last, str(rec))
        self.check('(a) verification becomes stale', any('code edit' in v['message'] for v in self.gaps(d)))
        # (b) a parallel code edit between started and end
        rc, _ = self.cli('verify', str(d))
        run = EV.latest_verify_run(self.root, F23)
        EV.append(self.root, self.session, 'code_edit', path='src/x.py')
        self.check('(b) code edit after `started`: stale',
                   EV.last_code_edit_ts(self.root) > run['started']
                   and any('after the last verify_run started' in v['message'] for v in self.gaps(d)))
        # (c) tree change without code_edit (Bash/git): fingerprint differs (mtime fallback: not a git repo)
        rc, _ = self.cli('verify', str(d))
        self.check('(c) precondition: fresh pass', self.gaps(d) == [])
        time.sleep(0.05)
        (self.root / 'src' / 'cart.py').write_text('changed = 1\n', encoding='utf-8')
        self.check('(c) tree change with no code_edit: fingerprint differs -> stale',
                   any('fingerprint' in v['message'] for v in self.gaps(d)))
        # (c-git) same in a git repo
        subprocess.run(['git', 'init', '-q'], cwd=str(self.root))
        subprocess.run(['git', '-c', 'user.email=a@b', '-c', 'user.name=a', 'add', '-A'], cwd=str(self.root))
        subprocess.run(['git', '-c', 'user.email=a@b', '-c', 'user.name=a', 'commit', '-qm', 'x'], cwd=str(self.root))
        rc, _ = self.cli('verify', str(d))
        ok0 = self.gaps(d) == []
        (self.root / 'src' / 'cart.py').write_text('changed = 2\n', encoding='utf-8')
        self.check('(c-git) git repo: tracked change w/o code_edit -> fingerprint stale',
                   ok0 and any('fingerprint' in v['message'] for v in self.gaps(d)))
        subprocess.run(['git', 'checkout', '-q', '--', 'src/cart.py'], cwd=str(self.root))
        # (d) a verify command that generates an untracked non-ignored file
        (self.root / 'tools').mkdir(exist_ok=True)
        (self.root / 'tools' / 'gen.py').write_text(
            "import pathlib\npathlib.Path('generated_out.txt').write_text('fixed content')\n"
            "print('generator ran and produced its output file ok')\n", encoding='utf-8')
        sp = (d / 'spec.md').read_text(encoding='utf-8')
        # editing the table changes verify_hash: re-approve through a new answer
        sp = sp.replace('`python -m unittest tests.test_ok`', '`python tools/gen.py`')
        (d / 'spec.md').write_text(sp, encoding='utf-8')
        rc, out = self.cli('verify', str(d))
        run = EV.latest_verify_run(self.root, F23)
        self.check('(d) first run: stable=false and close refused "tree changed while verification ran"',
                   rc != 0 and run.get('stable') is False
                   and any('tree changed while verification ran' in v['message'] for v in self.gaps(d)))
        rc, out = self.cli('verify', str(d))
        run = EV.latest_verify_run(self.root, F23)
        self.check('(d) second run is stable', run.get('stable') is True)


class T210(GateTwo):
    AC = 'AC-210'

    def test(self):
        d = self.gate2_spec()
        doms = sorted(R.required_domains(d))
        self.log('required domains (fixture):', doms)
        self.cli('verify', str(d))
        run = EV.latest_verify_run(self.root, F23)
        t = (d / 'tasks.md').read_text(encoding='utf-8')
        h8, v8 = R.approval_hash(t)[:8], run['verify_hash'][:8]
        since = max(EV.last_code_edit_ts(self.root), run['ts'])
        allh = f'CLOSING AUDIT [domains: {", ".join(doms + ["performance"])}] [tasks:{h8}] [verify:{v8}]'

        def sub(head, **kw):
            det = dict(type='general-purpose', desc='closing audit', head=head + '\nchecklist...', model='sonnet',
                       result_chars=4000, tool_use_id='toolu_ABC')
            det.update(kw)
            det = {k: v for k, v in det.items() if v is not None}
            return {'ts': time.time() + 1, 'session': self.session, 'kind': 'subagent', 'detail': det}

        def unc(e):
            class FEV:
                def events(s, root, session=None, kind=None, since=0.0):
                    return [e] if kind == 'subagent' else EV.events(root, session, kind, since)

                def __getattr__(s, n):
                    return getattr(EV, n)
            return R._uncovered(FEV(), self.root, None, set(doms) | {'performance'}, since, spec_dir=d)

        cases = [('full header, sonnet, 4000 chars', sub(allh), set()),
                 ('only security named', sub(f'CLOSING AUDIT [domains: security] [tasks:{h8}] [verify:{v8}]'),
                  None),
                 ('haiku', sub(allh, model='claude-haiku-4'), None),
                 ('phase=pre', sub(allh, phase='pre'), None),
                 ('stale [tasks:] tag', sub(allh.replace(h8, '00000000')), None),
                 ('wrong [verify:] tag', sub(allh.replace(v8, '00000000')), None),
                 ('result_chars 20', sub(allh, result_chars=20), None),
                 ('no result_chars', sub(allh, result_chars=None), None),
                 ('header not on the first line', sub('please audit\n' + allh), None)]
        for name, e, want in cases:
            u = unc(e)
            self.log(name, '->', sorted(u))
            if want == set():
                self.check(f'{name}: uncovered = none', u == set())
            elif name == 'only security named':
                self.check(f'{name}: functional (and performance) stay uncovered', 'functional' in u and 'security' in u or 'functional' in u)
            else:
                self.check(f'{name}: does NOT count', u != set())
        old = sub(allh)
        old['ts'] = run['ts'] - 1
        self.check('closing auditor older than verify_run refused (gate 2)',
                   not R.closing_audit_covers(old, d, set(doms), True, EV, self.root))
        per = [{'ts': time.time() + 1, 'session': self.session, 'kind': 'subagent',
                'detail': {'type': 'g', 'desc': f'{x} auditor', 'head': f'independent {x} audit', 'model': 'sonnet'}}
               for x in doms]

        class FEV2:
            def events(s, root, session=None, kind=None, since=0.0):
                return per if kind == 'subagent' else EV.events(root, session, kind, since)

            def __getattr__(s, n):
                return getattr(EV, n)
        self.check('legacy per-domain auditors still cover', R._uncovered(FEV2(), self.root, None, set(doms), since,
                                                                           spec_dir=d) == set())
        # qa-audit rows + tool_use_id (real log)
        time.sleep(0.02)
        EV.append(self.root, self.session, 'subagent', type='general-purpose', desc='closing audit',
                  head=allh + '\nchecklist', model='sonnet', result_chars=4000, tool_use_id='toolu_XYZ')
        self.put(f'specs/{F23}/qa-audit.md', G.qa_text(G.QA_ROW_OK) + '\n| Domain | Result |\n|---|---|\n'
                 '| security | ok |\n', age=-1)
        g = R.closing_audit_gaps(EV, self.root, d)
        self.log('closing_audit_gaps (missing functional row + tool_use_id):', [v['message'] for v in g])
        self.check('close refuses when qa-audit.md lacks a domain row or the tool_use_id',
                   any('functional' in v['message'] for v in g) and any('tool_use_id' in v['message'] for v in g))
        self.put(f'specs/{F23}/qa-audit.md', G.qa_text(G.QA_ROW_OK) + '\n| Domain | Result | Auditor |\n|---|---|---|\n'
                 + ''.join(f'| {x} | ok | toolu_XYZ |\n' for x in doms), age=-1)
        g = R.closing_audit_gaps(EV, self.root, d)
        self.check('with all rows and the tool_use_id: no closing-audit gap', g == [], str(g))


# ------------------------------------------------------------------------------------------- AC-211
class T211(A):
    AC = 'AC-211'

    def test(self):
        PLAN = 'specs/001-x/plan.md'
        self.put('specs/001-x/spec.md', G.spec_text())
        self.spec_edit('spec.md')
        self.prompt(G.CHECKLIST_QUOTE)
        self.prompt(G.QUOTE)
        self.ev('find_spec', rebuilt=False, ok=True, source='bash')
        r = self.g(PLAN, content='# plan\n')
        self.check('default (advisory): plan.md without a Mapper allowed', r.returncode == 0)
        r = self.g(PLAN, content='# plan\n', env={'AIDD_R5_AUDIT': 'strict'})
        self.check('strict: plan.md without a Mapper blocked', r.returncode == 2 and 'R5' in r.err)
        # graph rebuilt, no subagent after it
        self.subagent('Mapper', 'independent mapper over spec.md')
        self.ev('find_spec', rebuilt=True, ok=True, source='bash')
        self.ev('graph_rebuild', source='find_spec')
        import _common
        _common.write_timestamp(self.session, 'last_graph_rebuild_ts')
        r = self.g(PLAN, content='# plan\n')
        self.check('default: post-rebuild plan.md write allowed (graph-coherence dispatch branch skipped)',
                   r.returncode == 0)
        r = self.g(PLAN, content='# plan\n', env={'AIDD_R5_AUDIT': 'strict'})
        self.check('strict: post-rebuild write blocked', r.returncode == 2)
        rc, out = self.cli('status', 'specs/001-x')
        self.check('aidd status reports the mapper state', 'mapper' in out.lower())
        # find_spec missing -> blocked in both modes (fresh session)
        self.session = self.session + '-2'
        for v in (None, 'strict'):
            r = self.g(PLAN, content='# plan\n', env={'AIDD_R5_AUDIT': v})
            self.check(f'no find_spec in session blocks (mode={v or "advisory"})', r.returncode == 2 and 'find_spec' in r.err)
        # [Proposed row blocks in both modes
        self.session = self.session + '-3'
        self.put('specs/001-x/spec.md', G.spec_text(checklist=G.CHECKLIST_PROPOSED))
        self.prompt(G.CHECKLIST_QUOTE)
        self.prompt(G.QUOTE)
        self.ev('find_spec', rebuilt=False, ok=True, source='bash')
        for v in (None, 'strict'):
            r = self.g(PLAN, content='# plan\n', env={'AIDD_R5_AUDIT': v})
            self.check(f'[Proposed row blocks (mode={v or "advisory"})', r.returncode == 2)
        self.put('specs/001-x/spec.md', G.spec_text(checklist=G.CHECKLIST_FABRICATED))
        for v in (None, 'strict'):
            r = self.g(PLAN, content='# plan\n', env={'AIDD_R5_AUDIT': v})
            self.check(f'unverifiable user quote blocks (mode={v or "advisory"})', r.returncode == 2)


# ------------------------------------------------------------------------------------------- AC-212
class T212(A):
    AC = 'AC-212'

    def test(self):
        for sid in PENDING14:
            self.mk_spec(sid)
        (self.root / '.aidd' / 'gate_spec').write_text(F23 + '\n', encoding='utf-8')
        subprocess.run(['git', 'init', '-q'], cwd=str(self.root))
        subprocess.run(['git', '-c', 'user.email=a@b', '-c', 'user.name=a', 'add', 'src'], cwd=str(self.root))
        subprocess.run(['git', '-c', 'user.email=a@b', '-c', 'user.name=a', 'commit', '-qm', 'init'], cwd=str(self.root))
        (self.root / 'specs' / F23 / 'notes.md').write_text('x', encoding='utf-8')
        rc, out = self.cli('status', '--refresh')
        self.check('--refresh: branch/last commit/dirty/untracked',
                   rc == 0 and re.search(r'branch', out, re.I) and re.search(r'commit', out, re.I)
                   and re.search(r'untracked', out, re.I))
        self.check('--refresh: untracked under specs/F23-eDoc-POS/', f'specs/{F23}/' in out.replace('\\', '/'))
        self.check('--refresh: "14 pending"', '14 pending' in out)
        self.check('--refresh: gate pointer + effective AIDD_RULES', 'gate pointer' in out.lower() and 'AIDD_RULES' in out)
        self.check('--refresh: review and verification state per spec', 'review' in out.lower() and 'verif' in out.lower())
        rc, out_j = self.cli('status', '--refresh', '--json')
        try:
            j = json.loads(out_j[out_j.index('{'):])
            hasd = 'derived' in j
        except Exception:
            hasd = False
        self.check('--json adds "derived"', rc == 0 and hasd)
        # non-git directory
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'specs').mkdir()
            e = dict(self.env, AIDD_SESSION_ID=self.session, GIT_CEILING_DIRECTORIES=str(Path(td).parent))
            r = subprocess.run([sys.executable, str(SCRIPTS / 'aidd_status.py'), 'status', '--refresh'], cwd=td,
                               env=e, capture_output=True, timeout=60)
            o = r.stdout.decode('utf-8', 'replace') + r.stderr.decode('utf-8', 'replace')
            self.log('$ (non-git) status --refresh -> exit', r.returncode, '\n', o)
            self.check('non-git directory prints `git: unavailable`, exit 0', r.returncode == 0 and 'git: unavailable' in o)
        rc, out2 = self.cli('status')
        self.check('without --refresh: still prints, plus the pointer line', rc == 0 and 'gate pointer' in out2.lower())


# ------------------------------------------------------------------------------------------- AC-213
class T213(GateTwo):
    AC = 'AC-213'

    def test(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / 'check_spec.py'),
                            str(REPO / 'specs' / '006-aidd-phased-audits-attribution')], capture_output=True,
                           timeout=120, cwd=str(REPO))
        o = r.stdout.decode('utf-8', 'replace')
        self.log('$ check_spec.py specs/006 -> exit', r.returncode, '\n', o[:1500])
        first = '\n'.join(o.splitlines()[:4])
        self.check('006: first lines say STRUCTURAL CHECK ONLY - nothing was executed',
                   'STRUCTURAL CHECK ONLY - nothing was executed' in first)
        self.check('exit code unchanged semantics (0 or 1)', r.returncode in (0, 1))
        d = self.gate2_spec()
        self.cli('verify', str(d))
        r = subprocess.run([sys.executable, str(SCRIPTS / 'check_spec.py'), str(d)], capture_output=True, timeout=120,
                           cwd=str(self.root), env=dict(self.env))
        o = r.stdout.decode('utf-8', 'replace')
        self.log('$ check_spec.py (passed verify_run) -> exit', r.returncode, '\n', o[:1500])
        self.check('with a passed verify_run: execution-evidence line instead of the banner',
                   'STRUCTURAL CHECK ONLY' not in o and re.search(r'execut', o, re.I) is not None)


# ------------------------------------------------------------------------------------------- AC-214
class T214(A):
    AC = 'AC-214'

    def test(self):
        self.mk_spec(F23)
        n0 = EV.count(self.root, 'rules_override')
        r = self.g('src/app.py', content='x', env={'AIDD_RULES': 'warn'})
        n1 = EV.count(self.root, 'rules_override')
        self.check('warn: blocked write passes with the stderr notice and records rules_override',
                   r.returncode == 0 and r.err.strip() and n1 > n0)
        ev_ss = {'session_id': self.session, 'cwd': str(self.root), 'hook_event_name': 'SessionStart'}
        self.hook('session_start.py', ev_ss, env={'AIDD_RULES': 'off'})
        self.hook('stop_gate.py', dict(ev_ss, hook_event_name='Stop'), env={'AIDD_RULES': 'off'})
        offs = [e['detail'] for e in EV.events(self.root, kind='rules_override') if e['detail'].get('mode') == 'off']
        self.log('off overrides:', offs)
        self.check('off: session_start and Stop record rules_override{mode:off}',
                   {o.get('hook') for o in offs} >= {'session_start', 'stop_gate'})
        rc, out = self.cli('status', env={'AIDD_RULES': 'off'})
        self.check('aidd status shows "warn overrides: N" and "AIDD_RULES=off (rules disabled)"',
                   re.search(r'warn overrides:\s*\d+', out) is not None and 'AIDD_RULES=off (rules disabled)' in out)
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            e = {'session_id': self.session, 'cwd': td, 'hook_event_name': 'SessionStart'}
            r1 = self.hook('session_start.py', e, env={'AIDD_RULES': 'off'})
            r2 = self.hook('stop_gate.py', dict(e, hook_event_name='Stop'), env={'AIDD_RULES': 'off'})
            self.check('no project root: nothing fails', r1.returncode == 0 and r2.returncode == 0
                       and 'Traceback' not in r1.err + r2.err)


# ------------------------------------------------------------------------------------------- AC-215
class T215(A):
    AC = 'AC-215'

    def test(self):
        ids = ['F21-eDoc-Inventory', 'F22-eDoc-Pricing', F23]
        at = G.approved_tasks()
        for sid in ids:
            self.mk_spec(sid, tasks=at)
            EV.append_approved(self.root, self.session, sid, R.approval_hash(at), gate=2)
        (self.root / '.aidd' / 'gate_spec').write_text(F23 + '\n', encoding='utf-8')
        time.sleep(0.02)
        EV.append(self.root, self.session, 'code_edit', path='src/a.py', target='F21-eDoc-Inventory', active='')
        EV.append(self.root, self.session, 'code_edit', path='src/b.py', target=F23, active='')
        stop = {'session_id': self.session, 'cwd': str(self.root), 'hook_event_name': 'Stop'}
        r = self.hook('stop_gate.py', stop)
        self.check('Stop BLOCKS naming only F23 with the three closing steps',
                   r.returncode == 2 and f'spec {F23} not closed' in r.err and 'aidd verify' in r.err
                   and 'CLOSING AUDIT' in r.err and 'aidd rules close' in r.err
                   and 'spec F22-eDoc-Pricing not closed' not in r.err and 'spec F21-eDoc-Inventory not closed' not in r.err)
        self.check('once per session, a reminder names F21', 'F21-eDoc-Inventory is approved' in r.err)
        r2 = self.hook('stop_gate.py', stop)
        self.check('second Stop: reminder not repeated', 'F21-eDoc-Inventory is approved' not in r2.err)
        # pointer moves to F22 (through the CLI)
        rc, out = self.cli('rules', 'activate', 'F22-eDoc-Pricing')
        r3 = self.hook('stop_gate.py', stop)
        msg = r3.out + r3.err
        self.check('after pointer -> F22: reminder lists F21 and F23 (non-blocking)',
                   r3.returncode == 0 and 'F21-eDoc-Inventory' in msg and F23 in msg)
        rc, out = self.cli('status')
        self.check('aidd status prints "gate pointer: F23 -> F22"',
                   re.search(r'gate pointer.*F23-eDoc-POS\s*->\s*F22-eDoc-Pricing', out) is not None)
        # no pointer + several open specs: R8 blocks none
        (self.root / '.aidd' / 'gate_spec').unlink()
        tg = EV.gate_target_specs(self.root)
        self.log('no pointer -> gate_target_specs', tg)
        r4 = self.hook('stop_gate.py', dict(stop, session_id=self.session + '-b'))
        self.check('no pointer + several open specs: R8 blocks none',
                   r4.returncode == 0, f'rc={r4.returncode} (target={tg})')
        # AIDD_STOP_BLOCKS=1
        (self.root / '.aidd' / 'gate_spec').write_text(F23 + '\n', encoding='utf-8')
        s2 = dict(stop, session_id=self.session + '-c')
        rcs = [self.hook('stop_gate.py', s2, env={'AIDD_STOP_BLOCKS': '1'}).returncode for _ in range(2)]
        self.log('AIDD_STOP_BLOCKS=1 rcs:', rcs)
        self.check('AIDD_STOP_BLOCKS=1 allows after one block (budget already consumed earlier)', rcs[-1] == 0)


# ------------------------------------------------------------------------------------------- AC-217
class T217(A):
    AC = 'AC-217'

    def test(self):
        d = self.mk_spec(F23)
        big = G.tasks_text().replace('Approved: PENDING', ('padding line of prose text\n' * 17000) + '\nApproved: PENDING')
        self.put(f'specs/{F23}/tasks.md', big, age=300)
        self.log('tasks.md chars:', len(big), 'check_content:', [v['message'][:80] for v in R.check_content('tasks', big)])
        rc, out = self.review(str(d))
        self.check('aidd review exits non-zero naming tasks.md and the size, writes nothing',
                   rc != 0 and 'tasks.md' in out and str(len(big)) in out and not (d / 'review.html').exists())
        st = RV.review_state(d)
        self.check('review_state: source too large, complete false',
                   st['reason'].startswith('source too large') and st['complete'] is False, st['reason'])
        self.answer('Approve these tasks?', 'Approve', tasks=big)
        rc, out = self.cli('rules', 'approve', str(d))
        a = EV.latest_approved(self.root, F23)
        self.check('approve falls back to the answer-only route (source answer, gate 2)',
                   rc == 0 and a and a.get('source') == 'answer' and a.get('gate') == 2, str(a))


# ------------------------------------------------------------------------------------------- AC-218
class T218(A):
    AC = 'AC-218'

    def test(self):
        (self.root / 'emptydir').mkdir()
        rows = [('python -c "pass"', 'exit 0'), ('python --version', 'exit 0'), ('cmd /c exit 0', 'exit 0'),
                ('sh -c true', 'exit 0'), ('python -c "print(\'PASS\')"', 'contains: PASS'),
                ('python tests/x.py', 'exit 0')]
        for c, e in rows:
            p = R.verification_command_problem(c, e, self.root)
            self.check(f'rejected at approval: {c!r}', p is not None, str(p))
        extra = [('python -Bc "pass"', 'exit 0'), ('python3.11 -c pass', 'exit 0'), ('bash -lc true', 'exit 0'),
                 ('node --eval=1', 'exit 0'), ('pwsh -Command 1', 'exit 0'), ('cmd.exe /C ver', 'exit 0'),
                 ('python - < src/cart.py', 'exit 0'), ('py -3 -c 1', 'exit 0')]
        for c, e in extra:
            self.log('extra lint probe', repr(c), '->', R.verification_command_problem(c, e, self.root))
        c = 'python -m unittest discover -s emptydir'
        self.check('`unittest discover -s <empty dir>` accepted at approval',
                   R.verification_command_problem(c, 'exit 0', self.root) is None)
        spec = G.spec_text(extra='\n## Verification\n\n| # | Command | Expected | Covers |\n|---|---|---|---|\n'
                                 f'| 1 | `{c}` | exit 0 | FR-001 |\n')
        d = self.mk_spec(F23, spec=spec)
        t = (d / 'tasks.md').read_text(encoding='utf-8')
        self.answer('Approve these tasks?', 'Approve', tasks=t)
        rc, out = self.cli('rules', 'approve', str(d))
        rc, out = self.cli('verify', str(d))
        run = EV.latest_verify_run(self.root, F23) or {}
        evf = d / 'evidence' / 'verify-1.txt'
        vop = R.verify_output_problem(evf.read_text(encoding='utf-8'), 'exit 0') if evf.exists() else None
        self.log('verify_output_problem(evidence) ->', vop, '| python', sys.version.split()[0])
        self.check('aidd verify marks it failed (exit 5 on this Python; output heuristic says "zero tests ran" for 3.10/3.11 exit 0)',
                   rc != 0 and run.get('ok') is False and vop == 'zero tests ran')
        self.put(f'specs/{F23}/plan.md', '# plan\n\n## A\n', age=300)
        self.review(str(d))
        h = (d / 'review.html').read_text(encoding='utf-8')
        m = re.search(r'<section[^>]*data-key="spec/verification"[^>]*>', h)
        self.log('verification section tag:', m.group(0) if m else None)
        self.check('Verification rendered in the highlighted mandatory section',
                   bool(m) and 'data-mandatory="1"' in m.group(0) and 'mandatory' in m.group(0))
        js = re.search(r'<script id="aidd-js">(.*?)</script>', h, re.S).group(1)
        self.check('"Approve all" JS skips data-mandatory sections (static read)',
                   'mandatory' in js.lower())


if __name__ == '__main__':
    unittest.main(verbosity=2)


class TPerfStatus(GateTwo):
    AC = 'perf-status-fingerprint'

    def test(self):
        ids = [f'F{i}-eDoc-X' for i in range(30, 36)]
        for sid in ids:
            d = self.gate2_spec(sid=sid)
            self.cli('verify', str(d))
        import aidd_status as S
        calls = []
        orig = EV.worktree_fingerprint

        def wrapped(root, budget_s=8.0):
            calls.append(1)
            return orig(root, budget_s)
        with mock.patch.object(EV, 'worktree_fingerprint', wrapped):
            os.environ['AIDD_SESSION_ID'] = self.session
            here = os.getcwd()
            os.chdir(self.root)
            try:
                buf = io.StringIO()
                with mock.patch('sys.stdout', buf):
                    S.cmd_status(['--refresh'])
                n_refresh = len(calls)
                with mock.patch('sys.stdout', buf):
                    S.cmd_status([])
                n_plain = len(calls) - n_refresh
            finally:
                os.chdir(here)
                os.environ.pop('AIDD_SESSION_ID', None)
        self.log(f'plain `aidd status`: {n_plain} fingerprint calls; --refresh: {n_refresh}')
        self.log(f'specs with a verify_run: {len(ids)}; worktree_fingerprint calls during one `aidd status --refresh`: {len(calls)}')
        self.check('fingerprint is recomputed once per spec (no memoisation) - informational', len(calls) >= len(ids),
                   f'{len(calls)} calls')
