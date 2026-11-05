"""Waste already paid: repeated real executions of shared commands in the event log (read-only).

Usage: python measure_paid_waste.py <events.toon> <shared.json> <since ISO date>

For each command shared by 2+ specs (from measure_shared_rows.py --json), looks at
real (non-reused) executions recorded in verify_run events since <since> and counts:
  strict  = a run whose (cmd, verify fingerprint_start) was already seen in an earlier
            run of a DIFFERENT spec -> the same command on a tree with the same
            recorded fingerprint ran again (fingerprint_start is scoped per spec,
            so this is a lower bound and may be 0 even when code was identical);
  window  = a run of the same cmd by a different spec within 2 h of the previous run
            of that cmd (looser upper-bound proxy: code may have changed in between).
Seconds use each run's recorded `secs`; runs without `secs` are counted as UNKNOWN.
"""
import csv
import io
import json
import sys
from collections import defaultdict
from datetime import datetime

events, shared_json, since = sys.argv[1], sys.argv[2], sys.argv[3]
since_ts = datetime.fromisoformat(since).timestamp()
shared = {x['cmd']: x for x in json.load(open(shared_json, encoding='utf-8'))}
runs = defaultdict(list)  # cmd -> [(ts, spec, fp_start, secs)]
for line in open(events, encoding='utf-8', errors='replace'):
    if ',verify_run,' not in line:
        continue
    try:
        rec = next(csv.reader(io.StringIO(line.strip())))
        ts, p = float(rec[0]), json.loads(rec[3])
    except Exception:
        continue
    if ts < since_ts:
        continue
    for r in p.get('results') or []:
        c = str(r.get('cmd') or '').strip()
        if c not in shared or r.get('reused'):
            continue
        s = r.get('secs')
        runs[c].append((ts, p.get('spec'), p.get('fingerprint_start'), s if isinstance(s, (int, float)) and s > 0 else None))

tot = {'runs': 0, 'strict': 0, 'strict_s': 0.0, 'window': 0, 'window_s': 0.0, 'window_unknown': 0}
rows = []
for c, lst in runs.items():
    lst.sort()
    seen = {}
    st = sts = w = ws = wu = 0
    for i, (ts, spec, fp, s) in enumerate(lst):
        if fp and (c, fp) in seen and seen[(c, fp)] != spec:
            st += 1
            sts += s or 0
        seen.setdefault((c, fp), spec)
        if i and lst[i - 1][1] != spec and ts - lst[i - 1][0] <= 7200:
            w += 1
            if s is None:
                wu += 1
            else:
                ws += s
    rows.append((ws, c, len(lst), st, sts, w, ws, wu, shared[c]['db']))
    tot['runs'] += len(lst)
    tot['strict'] += st
    tot['strict_s'] += sts
    tot['window'] += w
    tot['window_s'] += ws
    tot['window_unknown'] += wu
    cat = 'DB' if shared[c]['db'] else ('python-file (contract surface ok)' if shared[c]['surface_ok'] else 'other non-DB')
    tot.setdefault('cat', {}).setdefault(cat, [0, 0.0, 0, 0.0])
    tot['cat'][cat][0] += st
    tot['cat'][cat][1] += sts
    tot['cat'][cat][2] += w
    tot['cat'][cat][3] += ws
rows.sort(reverse=True)
for k, (a, b, w_, x) in sorted(tot.get('cat', {}).items()):
    print(f'category {k}: strict {a} runs / {b/60:.1f} min; 2h-window {w_} runs / {x/60:.1f} min')
print(f'since {since}: real runs of shared commands = {tot["runs"]}')
print(f'strict repeats (same cmd + same recorded fingerprint_start, other spec) = {tot["strict"]}, {tot["strict_s"]/60:.1f} min')
print(f'2h-window repeats (same cmd, other spec, <=2h after previous run) = {tot["window"]}, '
      f'{tot["window_s"]/60:.1f} min known, {tot["window_unknown"]} with unknown duration')
for _, c, n, st, sts, w, ws, wu, db in rows[:12]:
    print(f'  {"DB " if db else "   "} runs={n:3} strict={st} ({sts/60:.1f} min) window={w} ({ws/60:.1f} min, unknown={wu}) :: {c[:110]}')
