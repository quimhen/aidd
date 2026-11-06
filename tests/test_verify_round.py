"""Amendment 10 item O of spec 007: `aidd verify --round` (aidd:FR-419..FR-426, AC-475..AC-484).
Real, cheap commands (python scripts in a temp project); the evidence log is patched. stdlib unittest."""
import contextlib
import io
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skill' / 'scripts'))
import aidd_round as rnd  # noqa: E402
import aidd_status as status  # noqa: E402

PY = f'"{sys.executable}"'
SCRIPTS = {
    'ok.py': "print('ran 3 tests ok, all assertions passed')\n",
    'other.py': "print('ran 5 other tests ok, all assertions passed')\n",
    'fail.py': "print('ran 3 tests, 1 FAILED assertion here'); raise SystemExit(1)\n",
    'mutate.py': "open('src/a.py', 'a').write('# edited during the round\\n'); print('ran 3 tests ok, all passed fine')\n",
    'count.py': ("import sys, time\nopen('count.txt', 'a').write(sys.argv[1] + ' start %f\\n' % time.time())\n"
                 "time.sleep(0.3)\nopen('count.txt', 'a').write(sys.argv[1] + ' end %f\\n' % time.time())\n"
                 "print('ran 3 tests ok, all assertions passed')\n"),
}


def table(rows, extra=''):
    head = '## Verification\n' + extra + '| # | Command | Expected | Covers | Tier |\n|---|---|---|---|---|\n'
    return head + ''.join(f'| {n} | {c} | {e} | FR-1 | {t} |\n' for n, c, e, t in rows)


class RoundBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / 'src').mkdir()
        (self.root / 'src' / 'a.py').write_text('x = 1\n', encoding='utf-8')
        for name, body in SCRIPTS.items():
            (self.root / name).write_text(body, encoding='utf-8')
        self.runs, self.events = [], []

    def tearDown(self):
        self._tmp.cleanup()

    def spec(self, name, rows, scope='src/**', extra=''):
        d = self.root / 'specs' / name
        d.mkdir(parents=True)
        (d / 'spec.md').write_text(f'# {name}\n\n' + table(rows, (f'Scope: {scope}\n' if scope else '') + extra),
                                   encoding='utf-8')
        (d / 'tasks.md').write_text('', encoding='utf-8')
        return d

    def _patches(self, open_specs=(), latest=None):
        real_run = status._run_row

        def run(cmd, root, out, timeout):
            self.runs.append(cmd)
            return real_run(cmd, root, out, timeout)

        def append_verify_run(_root, _s, spec, ok, vhash, results, started, fp_start, fp_end, stable, **kw):
            self.events.append({'spec': spec, 'ok': ok, 'results': results, 'stable': stable})
            return True
        root = self.root
        stack = contextlib.ExitStack()
        for p in (patch.object(status.ev, 'find_root', return_value=root),
                  patch.object(status, '_resolve_spec',
                               side_effect=lambda a, r=None: (root / 'specs' / Path(a).name)
                               if (root / 'specs' / Path(a).name / 'spec.md').is_file() else None),
                  patch.object(status, '_current_session', return_value='s'),
                  patch.object(status.ev, 'latest_verify_run', side_effect=lambda r, s: (latest or {}).get(s)),
                  patch.object(status.ev, 'open_specs', return_value=list(open_specs)),
                  patch.object(status.ev, 'append', return_value=True),
                  patch.object(status.ev, 'append_verify_run', side_effect=append_verify_run),
                  patch.object(status, '_run_row', side_effect=run)):
            stack.enter_context(p)
        return stack

    def main(self, *argv, **kw):
        with self._patches(**kw), contextlib.redirect_stdout(io.StringIO()) as out:
            rc = status.main(list(argv))
        return rc, out.getvalue()


class Normalisation(unittest.TestCase):
    def test_whitespace_and_plain_quotes(self):
        self.assertEqual(rnd.normalize_command('npm   test  --prefix "eDoc/web"'),
                         rnd.normalize_command('npm test --prefix eDoc/web'))

    def test_quoted_spaces_are_significant(self):
        a = 'python db.py --psql "docker exec -i x psql -U postgres"'
        b = 'python db.py --psql "docker exec -i x  psql -U postgres"'
        self.assertNotEqual(rnd.normalize_command(a), rnd.normalize_command(b))
        self.assertNotEqual(rnd.normalize_command('vitest run a.ts'), rnd.normalize_command('vitest run b.ts'))

    def test_docker_containers_and_heavy(self):
        cmd = 'python eDoc/tools/db_verify.py --psql "docker exec -i -u postgres supabase_db_edoc psql -U postgres" --tap'
        self.assertEqual(rnd.docker_containers(cmd), ['supabase_db_edoc'])
        self.assertTrue(rnd.heavy(cmd))
        self.assertTrue(rnd.heavy('node x/vitest.mjs run --root eDoc/web a.test.ts'))
        self.assertFalse(rnd.heavy('python ok.py'))


class Round(RoundBase):
    def test_identical_rows_run_once_and_each_spec_records_its_run(self):
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', ''), ('V-2', f'{PY} other.py', 'exit 0', '')])
        self.spec('B', [('V-1', f'{PY}   ok.py', 'contains: all assertions', '')])
        rc, out = self.main('verify', '--round', 'A', 'B')
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(self.runs), 2, out)                       # 3 rows, 2 executions
        self.assertEqual([e['spec'] for e in self.events], ['A', 'B'])
        self.assertTrue(all(e['ok'] and e['stable'] for e in self.events), out)
        b = (self.root / 'specs' / 'B' / 'evidence' / 'verify-V-1.txt').read_text(encoding='utf-8').splitlines()
        self.assertTrue(b[0].startswith('# ') and '| exit 0 |' in b[0])
        self.assertRegex(b[1], r'^ROUND-SHARED: ejecutado una vez por A fila V-1, huella [0-9a-f]{16}, \d{4}-')
        self.assertIn('all assertions passed', '\n'.join(b[2:]))
        self.assertEqual(self.events[1]['results'][0]['round_shared']['source_spec'], 'A')

    def test_different_command_not_grouped(self):
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', '')])
        self.spec('B', [('V-1', f'{PY} other.py', 'exit 0', '')])
        rc, out = self.main('verify', '--round', 'A', 'B')
        self.assertEqual((rc, len(self.runs)), (0, 2), out)

    def test_changed_fingerprint_invalidates(self):
        self.spec('A', [('V-1', f'{PY} mutate.py', 'exit 0', '')])
        self.spec('B', [('V-1', f'{PY} mutate.py', 'exit 0', '')])
        rc, out = self.main('verify', '--round', 'A', 'B')
        self.assertEqual(rc, 1, out)
        self.assertEqual(len(self.runs), 1)
        self.assertIn('INVALIDATED', out)
        for e in self.events:
            self.assertFalse(e['results'][0]['ok'])
            self.assertIn('ROUND-INVALIDATED', e['results'][0]['problem'])

    def test_fail_is_never_shared_as_pass(self):
        self.spec('A', [('V-1', f'{PY} fail.py', 'exit 0', '')])
        self.spec('B', [('V-1', f'{PY} fail.py', 'contains: FAILED', '')])
        rc, out = self.main('verify', '--round', 'A', 'B')
        self.assertEqual((rc, len(self.runs)), (1, 1), out)
        self.assertEqual([e['results'][0]['ok'] for e in self.events], [False, False])

    def test_dry_run_executes_nothing(self):
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', '')])
        self.spec('B', [('V-1', f'{PY} ok.py', 'exit 0', '')])
        latest = {'A': {'results': [{'cmd': f'{PY} ok.py', 'secs': 42.0}]}}
        rc, out = self.main('verify', '--round', 'A', 'B', '--dry-run', latest=latest)
        self.assertEqual((rc, self.runs, self.events), (0, [], []), out)
        self.assertIn('2 functional row(s), 1 execution(s); 1 execution(s) saved (~42 s', out)
        self.assertFalse((self.root / 'specs' / 'A' / 'evidence').exists())

    def test_series_one_at_a_time(self):
        self.spec('A', [('V-1', f'{PY} count.py one', 'exit 0', ''), ('V-2', f'{PY} count.py two', 'exit 0', '')])
        self.spec('B', [('V-1', f'{PY} count.py three', 'exit 0', '')], extra='Jobs: 4\n')
        rc, out = self.main('verify', '--round', 'A', 'B')
        self.assertEqual(rc, 0, out)
        spans = {}
        for line in (self.root / 'count.txt').read_text().splitlines():
            name, kind, ts = line.split()
            spans.setdefault(name, {})[kind] = float(ts)
        ordered = sorted(spans.values(), key=lambda s: s['start'])
        self.assertEqual(len(ordered), 3)
        for a, b in zip(ordered, ordered[1:]):
            self.assertLessEqual(a['end'], b['start'])               # A has no Jobs: the round stays serial

    def test_perf_rows_excluded(self):
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', ''), ('V-2', f'{PY} other.py', 'exit 0', 'perf')])
        self.spec('B', [('V-1', f'{PY} ok.py', 'exit 0', '')])
        rc, out = self.main('verify', '--round', 'A', 'B')
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(self.runs), 1)
        self.assertNotIn('other.py', ' '.join(self.runs))
        self.assertIn('`Tier: perf` row(s) excluded', out)

    def test_refused_options(self):
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', '')])
        for extra in (['--tasks', 'T-01'], ['--perf'], ['--wave', 'w1'], ['--json'], ['--bail']):
            rc, out = self.main('verify', '--round', 'A', *extra)
            self.assertEqual(rc, 1, out)
        self.assertEqual(self.runs, [])

    def test_all_open(self):
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', '')])
        self.spec('B', [('V-1', f'{PY} ok.py', 'exit 0', '')])
        rc, out = self.main('verify', '--all-open', '--round', '--dry-run', open_specs=['A', 'B', 'gone'])
        self.assertEqual(rc, 0, out)
        self.assertIn('round plan: 2 spec(s)', out)


class Suggestions(RoundBase):
    def test_status_suggests_round_and_verify_warns(self):
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', '')])
        self.spec('B', [('V-1', f'{PY} ok.py', 'exit 0', '')])
        with self._patches(open_specs=['A', 'B']):
            line = rnd.suggestion(status, self.root)
            self.assertIn('aidd verify --round A B', line)
            self.assertIn('1 saved', line)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                status.cmd_verify('A')
        self.assertIn('round: 1 row(s) of A are identical to rows of other open specs (B)', out.getvalue())
        self.assertEqual(len(self.runs), 1)

    def test_no_suggestion_for_one_spec_or_no_shared_rows(self):
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', '')])
        self.spec('B', [('V-1', f'{PY} other.py', 'exit 0', '')])
        with self._patches(open_specs=['A', 'B']):
            self.assertEqual(rnd.suggestion(status, self.root), '')
        with self._patches(open_specs=['A']):
            self.assertEqual(rnd.suggestion(status, self.root), '')

    def test_status_prints_round_line(self):
        self.spec('A', [('V-1', f'{PY} ok.py', 'exit 0', '')])
        self.spec('B', [('V-1', f'{PY} ok.py', 'exit 0', '')])
        with self._patches(open_specs=['A', 'B']), \
             patch.object(status, 'build_status', side_effect=lambda p, *a, **k: {'spec': p.name, 'open': False,
                                                                                   'tasks': {'approval': 'x'}}), \
             patch.object(status, 'format_status', return_value=''), \
             patch.object(status, 'format_global', return_value=''), \
             patch.object(status, '_global', return_value=dict(status._DEGRADED_GLOBAL, open_specs=['A', 'B'])), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            status.cmd_status([])
        self.assertIn('aidd verify --round A B', out.getvalue())


if __name__ == '__main__':
    unittest.main()
