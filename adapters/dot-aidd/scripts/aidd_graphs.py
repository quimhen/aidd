#!/usr/bin/env python3
"""
aidd graphs — the project graphs registry: knows a project's structure graphs (DB schema, code,
spec/UI), reports whether each is fresh, refreshes it in the background and lets agents query it
instead of reading SQL/code. Stdlib only. Never raises from a public function (safe defaults).

Registry: `## Graphs` table in the project-root charter.md
    | Name | Kind | Output | Refresh | Watch |
    Kind db|code|ui|spec · Output relative to root · Refresh = shell command, `builtin:sql` or empty
    (read-only) · Watch = comma-separated globs relative to root (`**` = any depth).
Without that section the registry is auto-detected (graphify-out/graph.json, a migrations dir,
specs/index.toon). Charter entries win over auto-detected ones of the same name.

Usage:
    aidd_graphs.py list
    aidd_graphs.py status [--json]
    aidd_graphs.py refresh <name|all> [--background|--wait]     (default: background)
    aidd_graphs.py show <name> <query> [--limit N]
    aidd_graphs.py explorer <name> [--out FILE]
Run from the project root (or pass --root DIR before the subcommand).
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCK_MAX_AGE = 30 * 60      # a lock older than this is stale
DEBOUNCE_S = 60             # no new refresh of the same graph within this window
SYNC_TIMEOUT = 30 * 60
SKIP_DIRS = {".git", "node_modules"}
MIGRATION_DIRS = ["supabase/migrations", "migrations", "db/migrations", "prisma/migrations", "db/migrate"]


# ----------------------------------------------------------------------------- registry

def _cell(s):
    return s.strip().strip("`").strip()


def _parse_charter(root):
    """Rows of the `## Graphs` table in charter.md; [] when the file/section is missing."""
    try:
        text = (Path(root) / "charter.md").read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    out, inside, header = [], False, None
    for line in text.splitlines():
        if re.match(r"^##\s+Graphs\b", line, re.I):
            inside = True
            continue
        if inside and re.match(r"^#{1,2}\s", line):
            break
        if not inside or not line.strip().startswith("|"):
            continue
        cells = [_cell(c) for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) or not c for c in cells):
            continue                                    # separator row
        if header is None:
            header = [c.lower() for c in cells]
            continue
        row = dict(zip(header, cells))
        name = row.get("name", "")
        if not name:
            continue
        watch = [w.strip().strip("`").replace("\\", "/") for w in row.get("watch", "").split(",")]
        out.append({"name": name, "kind": row.get("kind", "").lower(), "output": row.get("output", ""),
                    "refresh": row.get("refresh", ""), "watch": [w for w in watch if w]})
    return out


def _autodetect(root):
    root = Path(root)
    out = []
    if (root / "graphify-out" / "graph.json").is_file():
        out.append({"name": "code", "kind": "code", "output": "graphify-out/graph.json", "refresh": "", "watch": []})
    for d in MIGRATION_DIRS:
        p = root / d
        if p.is_dir() and any(p.glob("*.sql")):
            out.append({"name": "db", "kind": "db", "output": ".aidd/graphs/db.json",
                        "refresh": "builtin:sql", "watch": [d + "/**"]})
            break
    if (root / "specs" / "index.toon").is_file():
        out.append({"name": "spec", "kind": "spec", "output": "specs/index.toon", "refresh": "", "watch": []})
    if any((root / "specs").glob("*/tasks.md")):
        # amendment to spec 004: AIDD's own implementation-progress graph (no third-party tool)
        out.append({"name": "progress", "kind": "progress", "output": ".aidd/graphs/progress.json",
                    "refresh": "builtin:progress", "watch": ["specs/**"]})
    return out


def load_registry(root):
    try:
        root = Path(root)
        charter = _parse_charter(root)
        for e in charter:
            e["source"] = "charter"
        names = {e["name"] for e in charter}
        auto = [dict(e, source="auto") for e in _autodetect(root) if e["name"] not in names]
        items = []
        for e in charter + auto:
            out = Path(e["output"]) if e["output"] else Path()
            e["output"] = str(out if out.is_absolute() else root / out).replace("\\", "/") if e["output"] else ""
            items.append(e)
        return items
    except Exception:
        return []


def _get(root, name):
    for e in load_registry(root):
        if e["name"].lower() == str(name).lower():
            return e
    return None


# ----------------------------------------------------------------------------- watch matching

def _glob_re(glob):
    """Glob -> regex: `**` any depth, `*` within one segment, trailing `/**` = everything below."""
    g, i, out = glob.replace("\\", "/").lstrip("./") if glob.startswith("./") else glob.replace("\\", "/"), 0, ""
    while i < len(g):
        if g.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif g.startswith("**", i):
            out += ".*"
            i += 2
        elif g[i] == "*":
            out += "[^/]*"
            i += 1
        elif g[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(g[i])
            i += 1
    return re.compile("^" + out + "$")


def _rel(root, path):
    p = str(path).replace("\\", "/")
    r = str(Path(root).resolve()).replace("\\", "/").rstrip("/")
    for base in (r, str(root).replace("\\", "/").rstrip("/")):
        if p.lower().startswith(base.lower() + "/"):
            return p[len(base) + 1:]
    return p.lstrip("/") if not re.match(r"^[A-Za-z]:/", p) else p


def match_watch(root, path):
    try:
        rel = _rel(root, path)
        parts = rel.split("/")
        if any(x in SKIP_DIRS for x in parts):
            return []
        names = []
        for e in load_registry(root):
            if e["output"] and _rel(root, e["output"]) == rel:
                continue
            if any(_glob_re(w).match(rel) for w in e["watch"]):
                names.append(e["name"])
        return names
    except Exception:
        return []


def _newest_watched(root, e):
    """Newest mtime among files matching the entry's watch globs (None when none)."""
    root = Path(root)
    newest, own = None, _rel(root, e["output"]) if e["output"] else None
    for w in e["watch"]:
        rx = _glob_re(w)
        static = []
        for seg in w.replace("\\", "/").split("/"):
            if any(c in seg for c in "*?"):
                break
            static.append(seg)
        base = root.joinpath(*static) if static else root
        if base.is_file():
            cands = [base]
        else:
            cands = []
            for dp, dn, fn in os.walk(base):
                dn[:] = [d for d in dn if d not in SKIP_DIRS]
                cands += [Path(dp) / f for f in fn]
        for f in cands:
            rel = _rel(root, f)
            if rel == own or not rx.match(rel):
                continue
            try:
                m = f.stat().st_mtime
            except OSError:
                continue
            newest = m if newest is None or m > newest else newest
    return newest


# ----------------------------------------------------------------------------- locks / refresh

def _paths(root, name):
    d = Path(tempfile.gettempdir()) / "aidd-hooks" / "graphs"
    base = hashlib.sha1(str(Path(root).resolve()).encode("utf-8")).hexdigest()[:10] + "-" + re.sub(r"\W", "_", name)
    return d / (base + ".log"), d / (base + ".lock"), d / (base + ".stamp")


def _pid_alive(pid):
    try:
        if os.name == "nt":
            import ctypes
            k = ctypes.windll.kernel32
            h = k.OpenProcess(0x1000, False, int(pid))      # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            code = ctypes.c_ulong()
            ok = k.GetExitCodeProcess(h, ctypes.byref(code))
            k.CloseHandle(h)
            return bool(ok) and code.value == 259           # STILL_ACTIVE
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _lock_live(lock):
    """pid of the live refresh holding the lock, else None."""
    try:
        if time.time() - lock.stat().st_mtime > LOCK_MAX_AGE:
            return None
        pid = int(lock.read_text().strip())
        return pid if _pid_alive(pid) else None
    except Exception:
        return None


def _command(root, e):
    """(argv_or_str, shell) for the entry's refresh, or (None, False) when read-only."""
    r = e["refresh"].strip()
    if not r:
        return None, False
    if r.lower() == "builtin:sql":
        dirs = [w[:-3] if w.endswith("/**") else w for w in e["watch"]]
        return [sys.executable, str(HERE / "sql_graph.py"), "--root", str(root), "--out", e["output"], *dirs], False
    if r.lower() == "builtin:progress":
        return [sys.executable, str(HERE / "aidd_progress.py"), "--root", str(root), "--quiet"], False
    return r, True


def refresh(root, name, background=True):
    log, lock, stamp = _paths(root, str(name))
    res = {"started": False, "reason": "", "pid": None, "log": str(log)}
    try:
        e = _get(root, name)
        if e is None:
            res["reason"] = "unknown graph '%s'" % name
            return res
        cmd, shell = _command(root, e)
        if cmd is None:
            res["reason"] = "no refresh command (read-only graph)"
            return res
        log.parent.mkdir(parents=True, exist_ok=True)
        pid = _lock_live(lock)
        if pid:
            res.update(reason="already running", pid=pid)
            return res
        if stamp.exists() and time.time() - stamp.stat().st_mtime < DEBOUNCE_S:
            res["reason"] = "debounced"
            return res
        if e["output"]:
            Path(e["output"]).parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(str(time.time()))
        if not background:
            with open(log, "wb") as lf:
                p = subprocess.run(cmd, shell=shell, cwd=str(root), stdout=lf, stderr=subprocess.STDOUT,
                                   timeout=SYNC_TIMEOUT)
            stamp.write_text(str(time.time()))
            res.update(started=True, reason="finished", exit=p.returncode)
            return res
        kw = {}
        if os.name == "nt":
            kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000   # DETACHED|NEW_PROCESS_GROUP|NO_WINDOW
        else:
            kw["start_new_session"] = True
        with open(log, "wb") as lf:
            p = subprocess.Popen(cmd, shell=shell, cwd=str(root), stdin=subprocess.DEVNULL,
                                 stdout=lf, stderr=subprocess.STDOUT, **kw)
        lock.write_text(str(p.pid))
        res.update(started=True, reason="started", pid=p.pid)
        return res
    except Exception as ex:
        res["reason"] = "error: %s" % ex
        return res


# ----------------------------------------------------------------------------- status

def status(root):
    out = []
    try:
        now = time.time()
        for e in load_registry(root):
            row = {"name": e["name"], "kind": e["kind"], "output": e["output"], "state": "missing",
                   "age_s": None, "newest_watched_age_s": None}
            try:
                o = Path(e["output"]) if e["output"] else None
                exists = bool(o and o.is_file())
                if exists:
                    row["age_s"] = int(now - o.stat().st_mtime)
                newest = _newest_watched(root, e) if e["watch"] else None
                if newest is not None:
                    row["newest_watched_age_s"] = int(now - newest)
                if _lock_live(_paths(root, e["name"])[1]):
                    row["state"] = "running"
                elif not e["refresh"].strip():
                    row["state"] = "no-refresh" if exists else "missing"
                elif not exists:
                    row["state"] = "missing"
                elif newest is not None and newest > o.stat().st_mtime:
                    row["state"] = "stale"
                else:
                    row["state"] = "fresh"
            except Exception:
                pass
            out.append(row)
    except Exception:
        pass
    return out


# ----------------------------------------------------------------------------- show

def _load_graph(path):
    g = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    nodes = g.get("nodes", []) if isinstance(g, dict) else []
    edges = (g.get("edges") or g.get("links") or []) if isinstance(g, dict) else []
    return nodes, edges


def _nid(n):
    return str(n.get("id", n.get("name", n.get("label", ""))))


def _score(n, q):
    vals = [str(n.get(k, "")).lower() for k in ("id", "label", "name")]
    if q in vals:
        return 0
    return 1 if any(q in v for v in vals) else 9


def show(root, name, query, limit=25):
    try:
        e = _get(root, name)
        if e is None:
            return "No graph named '%s' (see: aidd graphs list)." % name
        if e["kind"] == "spec":
            return "Spec graph is a TOON index; query it with: python %s --code %s" % (HERE / "find_spec.py", query)
        if not e["output"] or not Path(e["output"]).is_file():
            return "Graph '%s' is missing; build it with: aidd graphs refresh %s --background" % (name, name)
        stale = ""
        for s in status(root):
            if s["name"] == e["name"] and s["state"] == "stale":
                stale = "(graph is stale; refresh: aidd graphs refresh %s --background)" % name
        nodes, edges = _load_graph(e["output"])
        q = str(query).lower()
        hits = sorted((n for n in nodes if _score(n, q) < 9), key=lambda n: (_score(n, q), len(_nid(n))))[:3]
        if not hits:
            return "No node matching '%s' in graph '%s'. %s" % (query, name, stale)
        lines = [stale] if stale else []
        for n in hits:
            nid = _nid(n)
            lines.append("%s  [%s]" % (nid, n.get("type", n.get("kind", n.get("file_type", "?")))))
            for k in ("data_type", "nullable", "purpose", "purpose_source", "impl_pct", "marked_pct", "tasks", "state",
                      "status", "stage_approved", "stage_verify", "stage_audit", "stage_closed"):
                if n.get(k) not in (None, ""):
                    lines.append("  %s: %s" % (k, n[k]))
            if n.get("source_file"):
                lines.append("  source: %s%s" % (n["source_file"], (":" + str(n["source_location"])) if n.get("source_location") else ""))
            groups = {}
            for ed in edges:
                s, t, rel = str(ed.get("source")), str(ed.get("target")), ed.get("relation", ed.get("type", "rel"))
                if s == nid:
                    groups.setdefault("-> %s" % rel, []).append(t)
                elif t == nid:
                    groups.setdefault("<- %s" % rel, []).append(s)
            for k, v in groups.items():
                lines.append("  %s: %s" % (k, ", ".join(v[:8]) + (" ... +%d more" % (len(v) - 8) if len(v) > 8 else "")))
        if len(lines) > limit:
            lines = lines[:limit - 1] + ["... +%d more" % (len(lines) - limit + 1)]
        return "\n".join(lines)
    except Exception as ex:
        return "Could not read graph '%s': %s" % (name, ex)


# ----------------------------------------------------------------------------- auto (Step -1)

_AUTO_TYPES = ("table", "view", "function", "procedure", "index")


def _auto_score(n, words):
    """0 = exact name match, 1 = substring of id/label, 2 = in the purpose; 9 = no match. Whole words only."""
    vals = [str(n.get(k, "")).lower() for k in ("id", "label", "name")]
    label = vals[1] or vals[2]
    best = 9
    for w in words:
        if w in vals or (label and label.split(".")[-1] == w):
            best = min(best, 0)
        elif any(w in v for v in vals):
            best = min(best, 1)
        elif w in str(n.get("purpose", "")).lower():
            best = min(best, 2)
    return best


def auto(root, words, limit=6):
    """Step -1 helper, no questions asked: for every project graph except the spec graph (find_spec covers it)
    start a background refresh when it is missing or stale (debounced, lock-protected) and return at most
    `limit` short lines: its state plus the nodes whose name or purpose match the query `words`
    (tables, views and functions first). [] when nothing is declared or AIDD_GRAPHS=off. Never raises."""
    try:
        if str(os.environ.get("AIDD_GRAPHS", "")).strip().lower() in ("off", "0", "false", "no"):
            return []
        words = [str(w).lower() for w in words if len(str(w)) >= 3]
        out = []
        for st in status(root):
            if st["kind"] == "spec":
                continue
            note = st["state"]
            if st["state"] in ("missing", "stale"):
                r = refresh(root, st["name"], background=True)
                if r.get("started"):
                    note += ", refresh started in background"
                elif r.get("reason") == "debounced":
                    note += ", refresh already requested"
            head = "Graph '%s' (%s): %s" % (st["name"], st["kind"], note)
            if not Path(st["output"]).is_file():
                out.append(head + "; no data yet, read the sources this time")
                continue
            nodes, _edges = _load_graph(st["output"])
            scored = sorted(((_auto_score(n, words), 0 if n.get("type") in _AUTO_TYPES else 1, len(_nid(n)), _nid(n), n)
                             for n in nodes), key=lambda t: t[:4])
            hits = [t for t in scored if t[0] < 9][:max(1, limit - 1)]
            out.append(head + ("" if hits else "; no node matches this query"))
            for _s, _k, _l, nid, n in hits:
                tail = str(n.get("purpose") or n.get("data_type") or "")[:90]
                out.append("  %s [%s]%s" % (nid, n.get("type", n.get("kind", "?")), (" - " + tail) if tail else ""))
        if out:
            out.append("  Details: aidd graphs show <name> <node>. Ask the graphs BEFORE reading SQL or source.")
        return out
    except Exception:
        return []


# ----------------------------------------------------------------------------- CLI

def _fmt_age(s):
    if s is None:
        return "-"
    return "%ds" % s if s < 120 else "%dm" % (s // 60) if s < 7200 else "%dh" % (s // 3600)


def main(argv):
    argv = list(argv)
    root = Path.cwd()
    if len(argv) >= 2 and argv[0] == "--root":
        root, argv = Path(argv[1]), argv[2:]
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    try:
        if cmd == "list":
            for e in load_registry(root):
                print("%-10s %-5s %-7s %s  refresh=%s  watch=%s" % (e["name"], e["kind"], e["source"], e["output"],
                                                                  e["refresh"] or "-", ",".join(e["watch"]) or "-"))
            return 0
        if cmd == "status":
            rows = status(root)
            if "--json" in rest:
                print(json.dumps(rows, indent=2))
            else:
                for r in rows:
                    print("%-10s %-10s age=%s newest_watched=%s  %s" % (r["name"], r["state"], _fmt_age(r["age_s"]),
                                                                        _fmt_age(r["newest_watched_age_s"]), r["output"]))
            return 0
        if cmd == "refresh" and rest:
            names = [e["name"] for e in load_registry(root) if e["refresh"].strip()] if rest[0] == "all" else [rest[0]]
            code = 0
            for n in names:
                r = refresh(root, n, background="--wait" not in rest)
                print("%s: %s%s (log: %s)" % (n, r["reason"], " pid=%s" % r["pid"] if r["pid"] else "", r["log"]))
                if r.get("exit"):
                    code = 1
                elif not r["started"] and r["reason"] not in ("debounced", "already running") and rest[0] != "all":
                    code = 1
            return code
        if cmd == "show" and len(rest) >= 2:
            limit = 25
            if "--limit" in rest:
                i = rest.index("--limit")
                limit = int(rest[i + 1])
                rest = rest[:i] + rest[i + 2:]
            print(show(root, rest[0], " ".join(rest[1:]), limit))
            return 0
        if cmd == "explorer" and rest:
            e = _get(root, rest[0])
            if e is None or not e["output"]:
                print("No graph named '%s'." % rest[0])
                return 1
            out = str(Path(e["output"]).with_suffix(".html"))
            if "--out" in rest:
                out = rest[rest.index("--out") + 1]
            script = HERE / "graph_explorer.py"
            if not script.is_file():
                print("graph_explorer.py is not installed next to aidd_graphs.py; cannot build the explorer.")
                return 1
            rc = subprocess.run([sys.executable, str(script), "--graph", e["output"], "--out", out], cwd=str(root)).returncode
            if rc == 0:
                print(out)
            return rc
    except Exception as ex:
        print("aidd graphs: %s" % ex)
        return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
