#!/usr/bin/env python3
"""aidd_close_ledger.py - draft of a spec's closing audit (READ ONLY, stdlib, no network).  aidd: amendment 09 B12 / FR-300 (h)

Usage: aidd close-ledger <spec_dir> [--check-fresh] [--json] [--domains a,b,c] [--verify-hash <hex>]

Prints to stdout (never writes under specs/):
  1. the heading `CLOSING AUDIT [domains: ...] [tasks:<h8>] [verify:<v8>]`
  2. the `## Verification summary` table built from `## Verification` of spec.md and the
     evidence/verify-<V-n>.txt files
  3. with --check-fresh: the evidence files (verify-*.txt and those cited under `## Execution evidence`
     of qa-audit.md) marked STALE when older than the newest code file of the scope; `LISTO PARA AUDITAR`
     only when nothing is STALE or missing.

Sources of the heading: domains = --domains, else the `CLOSING AUDIT [domains: ...]` of an existing
closing-audit.md, else `aidd_rules.required_domains(spec)` (the same rule `aidd rules close` applies);
tasks hash = the `Approved: <date> hash:<hex>` line of tasks.md; verify hash = --verify-hash, else the newest
`verify_run` of the spec in the evidence log. An agent copies the output with its Write tool.
Exit: 0 printed, 2 usage error (no spec.md).
"""
import argparse
import datetime
import glob
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import aidd_rules as rules
except Exception:  # pragma: no cover - the script still works with its own parsers
    rules = None
try:
    import aidd_evidence as ev
except Exception:  # pragma: no cover
    ev = None

ANSI = re.compile(r"\x1b\[[0-9;]*m")
IGNORED_DIRS = {"node_modules", "__pycache__", ".git", "dist", "build", ".venv", ".pytest_cache"}
ROW = re.compile(r"^\|\s*(V-\d+)\s*\|\s*`(.+?)`\s*\|\s*(.*?)\s*\|")


def read_text(path):
    try:
        return Path(path).read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    except OSError:
        return None


def section(text, title):
    """Body of a `## title` section up to the next `## `."""
    m = re.search(r"^##\s+" + re.escape(title) + r"[^\n]*\n", text, re.M)
    if not m:
        return ""
    rest = text[m.end():]
    n = re.search(r"^##\s", rest, re.M)
    return rest[: n.start()] if n else rest


def parse_verification(spec_text, tasks_text=""):
    """-> (rows [{id, cmd, expected}], scope globs). Uses aidd_rules when present, else a small own parser."""
    rows = []
    if rules is not None:
        for r in rules.parse_verification(spec_text):
            rows.append({"id": r["n"], "cmd": r["cmd"], "expected": r.get("expected", "")})
        return rows, [s for s in rules.verification_scope(spec_text, tasks_text) if s.lower() != "auto"]
    body = section(spec_text, "Verification")
    for line in body.split("\n"):
        m = ROW.match(line)
        if m:
            rows.append({"id": m.group(1), "cmd": m.group(2), "expected": m.group(3)})
    sm = re.search(r"^Scope:\s*(.+)$", body, re.M)
    scope = []
    if sm:
        scope = [s.strip().strip("`") for s in re.split(r",\s+|,(?=[A-Za-z.\w]+/)", sm.group(1)) if s.strip()]
        scope = [s for s in scope if s.lower() != "auto"]
    return rows, scope


def row_file_id(n, i):
    """Same naming as `aidd verify` (aidd_status._row_file_id): evidence/verify-<id>.txt."""
    s = re.sub(r"[^A-Za-z0-9_-]+", "", str(n or ""))[:20]
    return s or str(i)


def summarize_evidence(text):
    """-> (exit, short result). Patterns: pgTAP, pytest, vitest, Playwright, tsc/npm."""
    clean = ANSI.sub("", text)
    first = clean.split("\n", 1)[0]
    ex = ""
    if first.startswith("#"):
        parts = first.rsplit("|", 2)
        if len(parts) == 3:
            m = re.search(r"exit\s+(-?\d+)", parts[1])
            ex = m.group(1) if m else ""
    bits = []
    pg = re.findall(r"RESULT:\s*OK \((\d+) failing item\(s\)\)", clean)
    if pg:
        oks = [(int(a), int(b)) for a, b in re.findall(r"\[ok\]\s+\S+:\s*ok=(\d+)\s+not_ok=(\d+)", clean)]
        s = f"pgTAP RESULT: OK ({pg[-1]} failing)"
        if oks:
            s += f"; {len(oks)} files, ok={sum(a for a, _ in oks)} not_ok={sum(b for _, b in oks)}"
        bits.append(s)
    else:
        bad = re.findall(r"RESULT:\s*(?!OK)(.+)", clean)
        if bad:
            bits.append("pgTAP " + bad[-1].strip())
    passed = re.findall(r"(\d+) passed", clean)
    failed = re.findall(r"(\d+) failed", clean)
    if passed or failed:
        bits.append(f"{passed[-1] if passed else 0} passed" + (f", {failed[-1]} failed" if failed else ""))
    if not bits:
        bits.append("no recognised pattern (tsc/npm: see exit)" if ex == "0" else "no recognised pattern")
    return ex, "; ".join(bits)


def find_root(spec_dir):
    p = Path(spec_dir).resolve()
    for cand in [p] + list(p.parents):
        if (cand / ".aidd").is_dir() or (cand / "AGENTS.md").is_file():
            return cand
    for cand in [p] + list(p.parents):       # a repo without .aidd/: the folder that holds specs/
        if cand.name == "specs":
            return cand.parent
    return p.parent.parent


def tasks_hash8(spec_dir):
    t = read_text(Path(spec_dir) / "tasks.md") or ""
    m = re.search(r"^Approved:\s*\S+\s+hash:([0-9a-fA-F]+)", t, re.M)
    return (m.group(1)[:8], None) if m else ("????????", "tasks.md has no `Approved: <date> hash:<hex>` line")


def verify_hash_from_log(root, spec_name):
    if ev is None:
        return None
    try:
        run = ev.latest_verify_run(root, spec_name)
    except Exception:
        return None
    return (run or {}).get("verify_hash") or None


def domains_from_audit(spec_dir):
    t = read_text(Path(spec_dir) / "closing-audit.md")
    if t:
        m = re.search(r"CLOSING AUDIT \[domains:\s*([^\]]*)\]", t)
        if m:
            return [d.strip() for d in m.group(1).split(",") if d.strip()]
    return None


def task_targets(spec_dir):
    """Backticked paths of the 3rd column of every `| T-nn |` row (works with or without a header)."""
    t = read_text(Path(spec_dir) / "tasks.md") or ""
    out = []
    for line in t.split("\n"):
        if re.match(r"^\|\s*T-\d+", line):
            cols = [c.strip() for c in line.split("|")]
            if len(cols) > 3:
                out += [m.group(1) for m in re.finditer(r"`([^`]+)`", cols[3])]
    if rules is not None:
        out += [x for x in rules.task_targets(t) if x not in out]
    return out


def newest_code(root, patterns):
    """(mtime, path) of the newest code file the patterns cover; (None, None) when none."""
    best = (None, None)
    for pat in patterns:
        pat = pat.replace("\\", "/")
        for f in glob.glob(str(Path(root) / pat), recursive=True):
            fp = Path(f)
            cands = [fp] if fp.is_file() else [q for q in fp.rglob("*") if q.is_file()]
            for q in cands:
                if IGNORED_DIRS & set(q.parts):
                    continue
                try:
                    mt = q.stat().st_mtime
                except OSError:
                    continue
                if best[0] is None or mt > best[0]:
                    best = (mt, str(q.relative_to(root)).replace("\\", "/") if Path(root) in q.parents else str(q))
    return best


def cited_evidence(spec_dir, root):
    t = read_text(Path(spec_dir) / "qa-audit.md") or ""
    body = section(t, "Execution evidence")
    paths = []
    for line in body.split("\n"):
        if not line.startswith("|") or re.match(r"^\|\s*(Code|-)", line):
            continue
        for m in re.finditer(r"[\w.\-]+(?:[/\\][\w.\- ]+)+", line):
            tok = m.group(0).strip().replace("\\", "/")
            if tok not in paths:
                paths.append(tok)
    out = []
    for tok in paths:
        for base in (Path(root), Path(spec_dir)):
            if (base / tok).exists():
                out.append((tok, base / tok))
                break
        else:
            out.append((tok, None))
    return out


def mtime_of(p):
    if p.is_dir():
        files = [q.stat().st_mtime for q in p.rglob("*") if q.is_file()]
        return min(files) if files else p.stat().st_mtime
    return p.stat().st_mtime


def build(spec_dir, domains=None, verify_hash=None, check_fresh=False):
    spec_dir = Path(spec_dir)
    root = find_root(spec_dir)
    name = spec_dir.resolve().name
    warnings = []
    spec_text = read_text(spec_dir / "spec.md") or ""
    tasks_text = read_text(spec_dir / "tasks.md") or ""
    vrows, scope = parse_verification(spec_text, tasks_text)

    if not domains:
        domains = domains_from_audit(spec_dir)
    if not domains and rules is not None:
        domains = sorted(rules.required_domains(spec_dir))
    if not domains:
        domains = []
        warnings.append("unknown domains: pass --domains a,b,c")
    h8, w = tasks_hash8(spec_dir)
    if w:
        warnings.append(w)
    vh = verify_hash or verify_hash_from_log(root, name)
    if not vh:
        v8 = "????????"
        warnings.append("verify hash not found in the evidence log: pass --verify-hash <hex>")
    else:
        v8 = vh[:8]
    header = f"CLOSING AUDIT [domains: {', '.join(domains)}] [tasks:{h8}] [verify:{v8}]"

    rows = []
    ev_dir = spec_dir / "evidence"
    for i, r in enumerate(vrows, 1):
        f = ev_dir / f"verify-{row_file_id(r['id'], i)}.txt"
        t = read_text(f)
        if t is None:
            rows.append({**r, "exit": "?", "result": "FALTA evidencia", "evidence": f"evidence/{f.name}",
                         "_path": None})
        else:
            ex, res = summarize_evidence(t)
            rows.append({**r, "exit": ex or "?", "result": res, "evidence": f"evidence/{f.name}", "_path": f})

    data = {"spec": name, "header": header, "warnings": warnings, "rows": [], "check_fresh": check_fresh,
            "stale": [], "missing": [], "scope": scope, "newest_code": None, "ready": False}

    if check_fresh:
        patterns = scope or task_targets(spec_dir)
        data["scope_source"] = "Scope:" if scope else "Target file of tasks.md"
        mt, who = newest_code(root, patterns)
        if mt is None:
            warnings.append("scope has no code files: freshness cannot be checked")
        else:
            data["newest_code"] = {"path": who, "mtime": mt}
        files = [(f"evidence/{r['evidence'].split('/')[-1]}", r["_path"]) for r in rows]
        files += cited_evidence(spec_dir, root)
        seen, checked = set(), []
        for label, p in files:
            if label in seen:
                continue
            seen.add(label)
            if p is None:
                data["missing"].append(label)
                checked.append({"file": label, "status": "FALTA"})
                continue
            m = mtime_of(p)
            stale = mt is not None and m < mt
            checked.append({"file": label, "status": "STALE" if stale else "OK", "mtime": m})
            if stale:
                data["stale"].append(label)
        data["checked"] = checked
        data["ready"] = bool(mt is not None and not data["stale"] and not data["missing"] and rows)
    for r in rows:
        r.pop("_path", None)
        data["rows"].append(r)
    return data


def render_text(d):
    out = [d["header"], ""]
    for w in d["warnings"]:
        out.append(f"> AVISO: {w}")
    if d["warnings"]:
        out.append("")
    out += ["## Verification summary", "", "| # | Command | Exit | Result | Evidence |", "|---|---|---|---|---|"]
    for r in d["rows"]:
        cmd = r["cmd"].replace("|", "\\|")
        out.append(f"| {r['id']} | `{cmd}` | {r['exit']} | {r['result']} | {r['evidence']} |")
    if d["check_fresh"]:
        out += ["", "## Frescura de la evidencia", ""]
        nc = d.get("newest_code")
        if nc:
            ts = datetime.datetime.fromtimestamp(nc["mtime"]).isoformat(timespec="seconds")
            out.append(f"Codigo mas reciente del alcance ({d.get('scope_source')}): {nc['path']} ({ts})")
        else:
            out.append("Codigo mas reciente del alcance: no determinado")
        out.append("")
        for c in d.get("checked", []):
            out.append(f"- {c['status']}: {c['file']}")
        out.append("")
        out.append("LISTO PARA AUDITAR" if d["ready"] else
                   "NO LISTO: hay evidencia STALE o faltante, o el alcance no se pudo comprobar. "
                   "Re-ejecutar `aidd verify` antes de auditar.")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="aidd close-ledger", description="Closing-audit draft of a spec (read only).")
    ap.add_argument("spec")
    ap.add_argument("--check-fresh", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--domains")
    ap.add_argument("--verify-hash")
    a = ap.parse_args(argv)
    spec = Path(a.spec)
    if not (spec / "spec.md").is_file():
        print(f"ERROR: {spec / 'spec.md'} does not exist", file=sys.stderr)
        return 2
    doms = [x.strip() for x in a.domains.split(",") if x.strip()] if a.domains else None
    d = build(spec, doms, a.verify_hash, a.check_fresh)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else render_text(d), end="" if not a.json else "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
