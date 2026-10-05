"""Delta audit harness for spec 007 (re-verifies closing-audit F-1..F-4 after the fixes). SCRATCH projects only:
gate_fixtures.Base (temp project, AIDD_EVIDENCE_DIR scratch log, AIDD_TESTING=1). Writes evidence/delta-<f>.txt."""
import importlib.util
import io
import os
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('h007', str(HERE / 'harness-audit007.py'))
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)
G, EV, R = H.G, H.EV, H.R
A, GateTwo = H.A, H.GateTwo

IDS = ('002-aidd-hard-rules', 'F23-eDoc-POS', 'F13-eDoc-Emission-Engine', 'login_v2')
LEAVES = ('tasks.md', 'plan.md', 'spec.md', 'review.md', 'review.html')


class DeltaF1(A):
    AC = 'delta-F1'

    def test(self):
        Rf = str(self.root).replace('\\', '/')
        Rw = str(self.root)
        fails = []
        for sid in IDS:
            d = self.root / 'specs' / sid
            d.mkdir(parents=True, exist_ok=True)
            for leaf in LEAVES:
                (d / leaf).write_text('x\n', encoding='utf-8')
                cases = [
                    (f'echo x > {Rf}/specs/{sid}/{leaf}', None),
                    (f'echo x >> {Rw}\\specs\\{sid}\\{leaf}', None),
                    (f'cp /tmp/t.md {Rf}/specs/{sid}/{leaf}', None),
                    (f'mv /tmp/t.md {Rf}/specs/{sid}/{leaf}', None),
                    (f'rm {Rf}/specs/{sid}/{leaf}', None),
                    (f'sed -i s/a/b/ {Rf}/specs/{sid}/{leaf}', None),
                    (f'Set-Content -Path {Rw}\\specs\\{sid}\\{leaf} -Value x', None),
                    (f'echo x | tee {Rf}/specs/{sid}/{leaf}', None),
                    (f'cd specs/{sid} && echo x > {leaf}', None),
                    (f'cd specs/{sid}/ && echo x > ./{leaf}', None),
                    (f'cd {Rf}/specs/{sid} && rm {leaf}', None),
                    (f'pushd specs/{sid}; cp /tmp/t {leaf}', None),
                    (f'Set-Location specs\\{sid}; Set-Content {leaf} x', None),
                    (f'cd specs/{sid} && echo x | tee {leaf}', None),
                    (f'cd specs && cd {sid} && echo x > {leaf}', None),
                    (f'cd specs/{sid} && python -c "open(\'{leaf}\',\'w\').write(\'x\')"', None),
                    (f'echo x > {leaf}', str(d)),                       # hook cwd inside specs/<id>
                    (f'rm {leaf}', str(d)),
                ]
                for c, cwd in cases:
                    r = self.b(c, cwd=cwd)
                    if r.returncode != 2 or 'Traceback' in r.err:
                        fails.append((sid, leaf, c, cwd, r.returncode))
        self.log('F-1 bypasses still allowed (should be empty):', fails)
        self.check(f'F-1: every write/delete of tasks/plan/spec/review.* for {len(IDS)} ids (abs, backslash, '
                   f'relative after cd/pushd/Set-Location, hook cwd) is blocked', not fails, str(fails[:10]))
        # negative controls (must stay allowed)
        ctrl = [('cat specs/F23-eDoc-POS/tasks.md', None), ('ls specs/F23-eDoc-POS', None),
                ('cd specs/F23-eDoc-POS && cat tasks.md', None), ('echo x > notes.txt', None),
                ('cd src && echo x > app.py', None), ('git diff specs/F23-eDoc-POS/tasks.md', None),
                ('python skill/scripts/aidd_status.py status specs/F23-eDoc-POS', None)]
        over = [c for c, cwd in ctrl if self.b(c, cwd=cwd).returncode != 0]
        self.check('F-1 controls: reads / unrelated writes stay allowed', not over, str(over))
        # residual probes (reported, not part of the F-1 verdict)
        res = [
            (f'cp /tmp/tasks.md {Rf}/specs/F23-eDoc-POS/', None),
            (f'mv /tmp/tasks.md {Rf}/specs/F23-eDoc-POS/', None),
            (f'cp /tmp/tasks.md {Rf}/specs/002-aidd-hard-rules/', None),
            ('cd specs/F23-eDoc-POS && cp /tmp/tasks.md .', None),
            ('cd sp*/F23-eDoc-POS && echo x > tasks.md', None),
            ('cd specs/F23-eDoc-POS && echo x > tas*.md', None),
            ('D=specs/F23-eDoc-POS; echo x > $D/tasks.md', None),
            ('git -C specs/F23-eDoc-POS checkout tasks.md', None),
        ]
        for c, cwd in res:
            r = self.bash(c, cwd=cwd)
            self.log(f'RESIDUAL PROBE rc={r.returncode} | {c}')


class DeltaF3(A):
    AC = 'delta-F3'

    def test(self):
        sid = 'F23-eDoc-POS'
        d = self.root / 'specs' / sid
        d.mkdir(parents=True)
        for leaf in ('review.md', 'review.html'):
            (d / leaf).write_text('x', encoding='utf-8')
        Rf = str(self.root).replace('\\', '/')
        pre = f'cd specs/{sid} && '
        must_block = [pre + c for c in (
            'rm review.*', 'rm revie?.html', 'rm review.{md,html}', "echo x > rev''iew.md", 'echo x > "review".md',
            'rm "rev"iew.html', "rm 'review.html'", 'rm [r]eview.html', 'rm ?eview.html', 'rm *.html', 'rm *',
            'Remove-Item review.*', 'rm -- review.html', 'mv review.html x.html', 'rm rev*', 'rm r*.md',
            'cp /tmp/x revi""ew.md', 'rm rev`iew.html')]
        must_block += [f'rm {Rf}/specs/{sid}/review.*', f'rm {Rf}/specs/*/review.html', 'rm specs/*/review.*',
                       f'rm specs/{sid}/revie?.md', "rm specs/F23-eDoc-POS/'review'.html"]
        cwd_block = ['rm review.*', 'rm revie?.html', "echo x > rev''iew.md", 'rm *.md']
        fails = []
        for c in must_block:
            r = self.b(c)
            if r.returncode != 2:
                fails.append(c)
        for c in cwd_block:
            r = self.b(c, cwd=str(d))
            if r.returncode != 2:
                fails.append('[cwd] ' + c)
        self.check('F-3: glob / brace / quote-split review.* writes and deletes are blocked', not fails, str(fails))
        ctrl = ['rm build/*', 'rm src/*.html', 'cat ' + pre.split(' && ')[0].split()[-1] + '/review.md',
                pre + 'cat review.md', pre + 'ls *', 'aidd review F23-eDoc-POS', 'aidd review --check F23-eDoc-POS',
                'rm -rf dist/*.md']
        over = [c for c in ctrl if self.b(c).returncode != 0]
        self.check('F-3 controls: rm build/*, rm src/*.html, cat review.md, aidd review stay allowed', not over,
                   str(over))
        for c in (pre + 'rm rev\\iew.html', pre + 'rm $(echo review.html)', pre + 'rm `echo revie`w.html',
                  pre + 'find . -name "review.*" -delete', pre + 'ls | grep revi | xargs rm',
                  pre + 'X=review; rm $X.html', pre + 'rm re{v,}iew.html'):
            r = self.bash(c)
            self.log(f'RESIDUAL PROBE rc={r.returncode} | {c}')


class DeltaF2(GateTwo):
    AC = 'delta-F2'

    def test(self):
        import aidd_status as S
        ids = [f'F{i}-eDoc-X' for i in range(30, 36)]
        for sid in ids:                          # create every spec first: gate2_spec rewrites tests/test_ok.py,
            self.gate2_spec(sid=sid)             # which would (correctly) make earlier verify_runs stale
        for sid in ids:
            self.cli('verify', str(self.root / 'specs' / sid))
        calls = []
        orig = EV.worktree_fingerprint

        def wrapped(root, budget_s=8.0):
            calls.append(time.time())
            return orig(root, budget_s)

        def run(args):
            calls.clear()
            buf = io.StringIO()
            with mock.patch.object(EV, 'worktree_fingerprint', wrapped), mock.patch('sys.stdout', buf):
                S.cmd_status(args)
            return len(calls), buf.getvalue()
        os.environ['AIDD_SESSION_ID'] = self.session
        here = os.getcwd()
        os.chdir(self.root)
        try:
            n_plain, out_plain = run([])
            n_ref, out_ref = run(['--refresh'])
            n_json, _ = run(['--refresh', '--json'])
            n_named, _ = run([str(self.root / 'specs' / ids[0])])
        finally:
            os.chdir(here)
        self.log(f'specs with a verify_run: {len(ids)}; fingerprint calls: plain={n_plain} --refresh={n_ref} '
                 f'--refresh --json={n_json} named={n_named}')
        self.log('plain status output (head):\n' + out_plain[:1500])
        self.check('F-2: plain `aidd status` computes the fingerprint once', n_plain == 1, str(n_plain))
        self.check('F-2: `aidd status --refresh` (and --json) computes it once', n_ref == 1 and n_json == 1,
                   f'{n_ref} {n_json}')
        self.check('F-2: named status computes it once', n_named == 1, str(n_named))
        self.check('baseline: every verified spec reads "passed" before any tree change',
                   out_plain.count('Verification: passed') == len(ids) and 'Verification: stale' not in out_plain,
                   out_plain[:400])
        # never stale (cross-run): change the tree with NO code_edit event -> next status run is stale
        time.sleep(1.1)
        (self.root / 'src' / 'gen_untracked.py').write_text('y = 2\n', encoding='utf-8')
        os.chdir(self.root)
        try:
            n2, out2 = run([])
            n3, out3 = run(['--refresh'])
        finally:
            os.chdir(here)
            os.environ.pop('AIDD_SESSION_ID', None)
        self.log('after an out-of-band tree change, plain status:\n' + out2[:1500])
        self.check('F-2 freshness: a tree change with no code_edit makes every verified spec stale in the next run '
                   '(plain and --refresh)', out2.count('Verification: stale') == len(ids)
                   and 'Verification: passed' not in out2 and 'verification passed' not in out3
                   and out3.count('Verification: stale') == len(ids) and n2 == 1 and n3 == 1,
                   f'stale plain={out2.count("Verification: stale")} refresh={out3.count("Verification: stale")}')
        rows = R.verification_state(self.root / 'specs' / ids[0], self.root)
        self.log('verification_state without memo (fresh path):', rows.get('status'))
        self.check('F-2 freshness: unmemoised verification_state agrees (stale)', rows.get('status') == 'stale',
                   str(rows.get('status')))
        # FingerprintOnce bound / ttl semantics with a fake clock
        clock = [1000.0]
        seq = iter(['fp1', 'fp2', 'fp3', 'fp4'])

        class FakeEv:
            @staticmethod
            def worktree_fingerprint(root):
                return next(seq)
        fo = R.FingerprintOnce(FakeEv, ttl=30.0, clock=lambda: clock[0])
        a = fo(self.root, 900.0)                 # computed at 1000
        b = fo(self.root, 950.0)                 # cached: bound older than cache
        clock[0] = 1005.0
        c = fo(self.root, 1001.0)                # bound NEWER than cache (a verify/code edit after it): recompute
        clock[0] = 1100.0
        e = fo(self.root, 0.0)                   # ttl expired: recompute
        f = fo(self.root, 'garbage')             # unreadable bound: never trust the cache
        self.log('FingerprintOnce fake-clock sequence:', a, b, c, e, f, 'calls', fo.calls)
        self.check('F-2: memo never serves a value older than its bound / ttl', (a, b, c, e) == ('fp1', 'fp1', 'fp2', 'fp3')
                   and f == 'fp4' and fo.calls == 4)


class DeltaF4(A):
    AC = 'delta-F4'

    def _record(self, rel):
        """The REAL recorder (mark_code_edit PostToolUse Edit) records the spec_edit, with its hash."""
        return self.hook('mark_code_edit.py', {'session_id': self.session, 'cwd': str(self.root),
                                               'hook_event_name': 'PostToolUse', 'tool_name': 'Edit',
                                               'tool_input': {'file_path': str(self.root / rel)}})

    def test(self):
        F21, F23 = 'F21-eDoc-Inventory', 'F23-eDoc-POS'
        at = G.approved_tasks()
        for sid in (F21, F23):
            (self.root / 'specs' / sid).mkdir(parents=True)
            self.put(f'specs/{sid}/spec.md', G.verified_spec(), age=300)
        self.put(f'specs/{F21}/tasks.md', at, age=300)
        self._record(f'specs/{F21}/tasks.md')
        EV.append_approved(self.root, self.session, F21, R.approval_hash(at))
        time.sleep(0.05)
        self.put(f'specs/{F23}/tasks.md', G.tasks_text(), age=0)
        self._record(f'specs/{F23}/tasks.md')
        self.check('setup: no gate pointer file', not (self.root / '.aidd' / 'gate_spec').exists())
        t0 = EV.gate_target_specs(self.root)
        r0 = self.code_write()
        self.log('before: target', t0, 'code write rc', r0.returncode)
        self.check('before: inferred F23 (pending) -> code write blocked', t0 == ([F23], False, 'inferred')
                   and r0.returncode == 2)
        n_gp0 = len(EV.events(self.root, kind='gate_pointer'))
        # hash-neutral tasks.md edit of approved F21: a Status column write-back (approval_hash ignores it)
        txt = (self.root / 'specs' / F21 / 'tasks.md').read_text(encoding='utf-8')
        neutral = txt.replace('| T-01 | COMP-001 |', '| T-01 | COMP-001 |', 1) + '\n<!-- status: T-01 done -->\n'
        same = R.approval_hash(neutral) == R.approval_hash(txt)
        if not same:
            neutral = txt + '\n'
            same = R.approval_hash(neutral) == R.approval_hash(txt)
        self.log('hash-neutral edit preserves approval_hash:', same)
        time.sleep(0.05)
        self.put(f'specs/{F21}/tasks.md', neutral, age=0)
        self._record(f'specs/{F21}/tasks.md')
        last = [e for e in EV.events(self.root, kind='spec_edit') if e['detail'].get('spec') == F21][-1]
        self.log('recorded F21 spec_edit hash:', last['detail'].get('hash'), 'approved hash:', R.approval_hash(at))
        t1 = EV.gate_target_specs(self.root)
        r1 = self.code_write()
        self.log('after hash-neutral F21 edit: target', t1, 'code write rc', r1.returncode)
        self.check('F-4: a hash-neutral tasks.md edit of approved F21 does NOT move the target (still F23, blocked)',
                   same and t1 == ([F23], False, 'inferred') and r1.returncode == 2)
        # a real (hash-changing) tasks.md edit of F21 still moves it (inference semantics kept) and is logged
        time.sleep(0.05)
        self.put(f'specs/{F21}/tasks.md', neutral.replace('COMP-001', 'COMP-002'), age=0)
        self._record(f'specs/{F21}/tasks.md')
        t2 = EV.gate_target_specs(self.root)
        gp = EV.events(self.root, kind='gate_pointer')
        self.log('after a hash-changing F21 edit: target', t2, '| gate_pointer events', [e['detail'] for e in gp])
        self.check('F-4: a hash-changing F21 edit moves the inferred target and logs gate_pointer{by=inferred}',
                   t2 == ([F21], False, 'inferred') and len(gp) > n_gp0
                   and gp[-1]['detail'].get('by') == 'inferred' and gp[-1]['detail'].get('spec') == F21)
        k = len(gp)
        EV.gate_target_specs(self.root)
        EV.gate_target_specs(self.root)
        self.check('F-4: repeated inference with no change logs no duplicate gate_pointer',
                   len(EV.events(self.root, kind='gate_pointer')) == k)
        # residual: a plan.md edit of an APPROVED spec moves the target to it (not hash-checked)
        self.put(f'specs/{F21}/tasks.md', at, age=0)
        self._record(f'specs/{F21}/tasks.md')
        time.sleep(0.05)
        self.put(f'specs/{F23}/tasks.md', G.tasks_text() + '\n', age=0)
        self._record(f'specs/{F23}/tasks.md')
        rA = self.code_write()
        time.sleep(0.05)
        self.put(f'specs/{F21}/plan.md', '# plan\n\ntypo fix\n', age=0)
        self._record(f'specs/{F21}/plan.md')
        tB = EV.gate_target_specs(self.root)
        rB = self.code_write()
        self.log(f'RESIDUAL PROBE plan.md edit of approved F21: before rc={rA.returncode}, after target={tB} '
                 f'rc={rB.returncode}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
