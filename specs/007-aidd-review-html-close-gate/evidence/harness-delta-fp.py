import json, os, subprocess, sys, tempfile
from pathlib import Path
HOOK = r'D:\Fuentes\AIDD\skill\hooks\rule_gate.py'
HEADHOOK = sys.argv[1] if len(sys.argv) > 1 else None
td = Path(tempfile.mkdtemp()).resolve()
evd = td / 'evd'; evd.mkdir()
env = dict({k: v for k, v in os.environ.items() if k != 'AIDD_RULES'}, AIDD_EVIDENCE_DIR=str(evd), AIDD_TESTING='1')
cases = []
nested = td / 'specs' / 'proj'; (nested / 'src').mkdir(parents=True); (nested / 'build').mkdir()
plain = td / 'plain'; (plain / 'src').mkdir(parents=True); (plain / 'specs' / 'F23-eDoc-POS').mkdir(parents=True)
jsdir = plain / 'tests' / 'specs'; jsdir.mkdir(parents=True)
for cwd, cmd in [(nested, 'rm *'), (nested, 'rm build/*'), (nested, 'rm -rf dist/*'), (nested, 'echo x > plan.md'),
                 (nested, 'echo "# notes" > spec.md'), (nested, 'ls'), (nested, 'cp a.txt b.txt'),
                 (jsdir, 'rm *'), (jsdir, 'echo x > spec.md'),
                 (plain, 'cd specs/F23-eDoc-POS && cd ../.. && rm *'),
                 (plain, 'cd specs/F23-eDoc-POS && cd ../../src && echo x > plan.md'),
                 (plain, 'cd tests/specs && rm *.snap'), (plain, 'cd tests/specs && rm *')]:
    for label, hook in (('NEW', HOOK),) + ((('HEAD', HEADHOOK),) if HEADHOOK else ()):
        ev = {'session_id': 's-fp', 'cwd': str(cwd), 'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
              'tool_input': {'command': cmd}}
        r = subprocess.run([sys.executable, hook], input=json.dumps(ev).encode(), capture_output=True, env=env, timeout=60)
        print(f'{label} rc={r.returncode} cwd={cwd.relative_to(td)} | {cmd} | {r.stderr.decode()[:90]!r}')
