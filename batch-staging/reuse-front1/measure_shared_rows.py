"""Measure shared `## Verification` rows across the specs of a project (read-only).

Usage: python measure_shared_rows.py <project_root> <aidd_scripts_dir> [--json OUT]

Uses AIDD's own parser (aidd_rules.parse_verification) so the rows are exactly
what `aidd verify` would run. Durations come from `verify_run` events in
<project_root>/.aidd/evidence/events.toon (field `secs`, only present in newer
runs); a command without any recorded `secs` is reported as UNKNOWN.
Writes nothing inside <project_root>.
"""
import csv
import io
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(Path(sys.argv[2]).resolve()))
import aidd_rules as rules  # noqa: E402

out_json = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None

DB_RE = re.compile(r'db_verify|psql|docker|supabase|pg_prove|--tap', re.I)
SHELL_META = set('|&;<>\n\r`$')


def key(cmd):
    return str(cmd or '').strip()


def contract_surface_ok(cmd):
    """Static mirror of the command-surface part of _contract_environment_id:
    no shell metacharacters, argv[0] is python/python3, argv[1] ends with .py."""
    if any(c in cmd for c in SHELL_META):
        return False
    parts = cmd.split()
    if len(parts) < 2:
        return False
    if Path(parts[0].strip('"\'')).name.lower() not in ('python', 'python.exe', 'python3'):
        return False
    return parts[1].strip('"\'').lower().endswith('.py')


rows_total = 0
by_cmd = defaultdict(list)        # cmd -> [(spec, n, row)]
specs_with_table = 0
for sp in sorted((root / 'specs').glob('*/spec.md')):
    text = sp.read_text(encoding='utf-8', errors='replace')
    rows = rules.parse_verification(text)
    if rows:
        specs_with_table += 1
    for r in rows:
        rows_total += 1
        by_cmd[key(r['cmd'])].append((sp.parent.name, r.get('n'), r))

# ---- durations and real executions from the event log
secs = defaultdict(list)          # cmd -> [secs of real (non-reused) executions]
runs_real = defaultdict(int)      # cmd -> real executions (non-reused), with or without secs
runs_reused = defaultdict(int)
runs_specs = defaultdict(set)
ev_path = root / '.aidd' / 'evidence' / 'events.toon'
n_events = 0
if ev_path.exists():
    for line in ev_path.read_text(encoding='utf-8', errors='replace').splitlines():
        if ',verify_run,' not in line:
            continue
        try:
            rec = next(csv.reader(io.StringIO(line.strip())))
            payload = json.loads(rec[3])
        except Exception:
            continue
        n_events += 1
        for res in payload.get('results') or []:
            c = key(res.get('cmd'))
            if res.get('reused'):
                runs_reused[c] += 1
                continue
            if res.get('exit') == -1 and not res.get('secs'):
                continue  # not run (lint problem) or timeout without timing
            runs_real[c] += 1
            runs_specs[c].add(payload.get('spec'))
            if isinstance(res.get('secs'), (int, float)) and res['secs'] > 0:
                secs[c].append(float(res['secs']))

shared = {c: v for c, v in by_cmd.items() if len({s for s, _, _ in v}) >= 2}


def eligible_today(row):
    env = (row.get('environment') or '').strip().lower()
    return (row.get('reuse') == 'hermetic' and bool(row.get('inputs'))
            and env.startswith('contract:offline;') and contract_surface_ok(row['cmd']))


report = []
for c, v in shared.items():
    specs = sorted({s for s, _, _ in v})
    med = statistics.median(secs[c]) if secs[c] else None
    report.append({
        'cmd': c, 'n_specs': len(specs), 'specs': specs, 'n_rows': len(v),
        'db': bool(DB_RE.search(c)),
        'surface_ok': contract_surface_ok(c),
        'rows_hermetic_declared': sum(1 for _, _, r in v if r.get('reuse') == 'hermetic'),
        'rows_eligible_today': sum(1 for _, _, r in v if eligible_today(r)),
        'median_secs': med, 'timed_samples': len(secs[c]),
        'real_runs_logged': runs_real[c], 'reused_runs_logged': runs_reused[c],
        'distinct_specs_that_ran_it': len(runs_specs[c] - {None}),
        # waste if each sharing spec runs it separately once: (n_specs - 1) * median
        'saved_per_round_secs': (len(specs) - 1) * med if med is not None else None,
        # waste already paid in the log: real runs beyond the first per distinct spec set is not knowable
        # exactly (code changed between runs), so we report the upper bound real_runs - 1.
    })
report.sort(key=lambda x: (-x['n_specs'], -(x['median_secs'] or 0)))

print(f'specs with a parsable ## Verification table: {specs_with_table} / {len(list((root / "specs").glob("*/spec.md")))}')
print(f'rows total: {rows_total}')
print(f'distinct commands: {len(by_cmd)}')
print(f'commands shared by 2+ specs: {len(shared)}  (rows in them: {sum(len(v) for v in shared.values())})')
print(f'verify_run events parsed: {n_events}')
all_rows = [r for v in by_cmd.values() for _, _, r in v]
print(f'rows declaring Reuse: hermetic: {sum(1 for r in all_rows if r.get("reuse") == "hermetic")}')
print(f'rows with Inputs: {sum(1 for r in all_rows if r.get("inputs"))}')
print(f'rows with Environment contract:offline;...: {sum(1 for r in all_rows if (r.get("environment") or "").lower().startswith("contract:offline;"))}')
print(f'rows eligible under the current contract: {sum(1 for r in all_rows if eligible_today(r))}')
print(f'shared commands that are DB rows: {sum(1 for x in report if x["db"])}')
print(f'shared non-DB commands: {sum(1 for x in report if not x["db"])}')
print(f'shared non-DB commands whose surface passes the contract (python <file>.py, no shell meta): '
      f'{sum(1 for x in report if not x["db"] and x["surface_ok"])}')
print(f'shared commands with >=1 row eligible today: {sum(1 for x in report if x["rows_eligible_today"])}')
known = [x for x in report if x['saved_per_round_secs'] is not None]
print(f'shared commands with a recorded duration: {len(known)} / {len(report)}')
print(f'estimated secs saved per full round (known durations only): {sum(x["saved_per_round_secs"] for x in known):.0f} '
      f'(DB {sum(x["saved_per_round_secs"] for x in known if x["db"]):.0f}, non-DB '
      f'{sum(x["saved_per_round_secs"] for x in known if not x["db"]):.0f})')
print('\nTOP 10 shared commands (by number of specs, then median duration):')
for i, x in enumerate(report[:10], 1):
    d = f"{x['median_secs']:.1f}s median of {x['timed_samples']}" if x['median_secs'] is not None else 'duration UNKNOWN'
    print(f"{i:2}. [{x['n_specs']} specs, {x['n_rows']} rows, {'DB' if x['db'] else 'non-DB'}, "
          f"surface_ok={x['surface_ok']}, eligible_rows={x['rows_eligible_today']}, {d}, "
          f"real runs logged={x['real_runs_logged']}, reused logged={x['reused_runs_logged']}]")
    print(f"    cmd: {x['cmd'][:160]}")
    print(f"    specs: {', '.join(x['specs'])}")
if out_json:
    Path(out_json).write_text(json.dumps(report, indent=1), encoding='utf-8')
