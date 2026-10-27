#!/usr/bin/env python3
"""
aidd graphs — the project graphs registry: knows a project's structure graphs (DB schema, code,
methodology, spec/UI), reports whether each is fresh, refreshes it in the background and lets agents
query it instead of reading SQL/code. Stdlib only. Never raises from a public function (safe defaults).

Registry: `## Graphs` table in the project-root charter.md
    | Name | Kind | Output | Refresh | Watch |
    Kind db|code|method|ui|spec · Output relative to root · Refresh = shell command, a builtin or empty
    (read-only) · Watch = comma-separated globs relative to root (`**` = any depth).
Builtins: `builtin:code` (code_graph.py, Python ast), `builtin:method` (method_graph.py, the AIDD
methodology), `builtin:spec` (find_spec.py --reindex -> specs/index.toon), `builtin:sql` (combined `db`),
`builtin:sql-schema` (`db-schema`, append-only migration replay), `builtin:sql-dml` (`db-dml`, cached body
analysis), `builtin:progress`.
Without that section the registry is auto-detected (code, method, spec, progress, a migrations dir,
graphify-out/graph.json). Charter entries win over auto-detected ones of the same name. The name `code` is
ALWAYS the built-in code graph: any `code` row whose Refresh is not `builtin:code` (e.g. graphify) is
renamed `code-<tool>` at load, with a warning.
Freshness is by CONTENT: each successful refresh writes `.aidd/graphs/stamps/<name>.stamp.json` =
{inputs_hash, inputs} (git blob shas of the watched files; the legacy `<output>.stamp.json` is read as a
fallback); a graph is stale when that hash differs or the stamp is missing.

Usage:
    aidd_graphs.py list
    aidd_graphs.py status [--json]
    aidd_graphs.py refresh <name|all> [--background|--wait] [--force]   (default: background; --force skips
                                                                          the 60 s debounce; --wait prints the
                                                                          generator's summary line)
    aidd_graphs.py show <name> <query> [--limit N]      (code: FUNC/FILE by qualified-name suffix or path;
                                                         method: R10, STEP:6, a command or template)
    aidd_graphs.py explorer <name> [--out FILE]
    aidd_graphs.py repeats [--cmd C] [--label L] [--include-ambiguous]      (graph_snapshot.py)
    aidd_graphs.py snapshot [name] --label L [--rev REV] [--replace]        (graph_snapshot.py)
    aidd_graphs.py diff <labelA> <labelB> [--name N] [--full]               (graph_snapshot.py)
    aidd_graphs.py changed [--spec ID] [--name code] [--full]               (graph_snapshot.py)
    aidd_graphs.py trace [--graph G] [--out F] -- <aidd command ...>        (graph_trace.py)
Run from the project root (or pass --root DIR before the subcommand).
"""
import hashlib
import importlib
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
GIT_TIMEOUT = 60
SKIP_DIRS = {".git", "node_modules"}
MIGRATION_DIRS = ["supabase/migrations", "migrations", "db/migrations", "prisma/migrations", "db/migrate"]
STAMP_SUFFIX = ".stamp.json"
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_WARNINGS = []              # load-time warnings (renamed rows), printed once by the CLI
_SHA_MEMO = {}              # (root, rel) -> git blob sha: one manifest pass per process (aidd:FR-021)
_LS_MEMO = {}               # root -> [rel] from git ls-files, or None


def _warn(msg):
    if msg not in _WARNINGS:
        _WARNINGS.append(msg)


def _module(name):
    """Sibling script imported as a module, or None (missing or broken generator never raises out)."""
    try:
        if str(HERE) not in sys.path:
            sys.path.insert(0, str(HERE))
        return importlib.import_module(name)
    except Exception:
        return None


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


def _migration_dir(root):
    """First migrations dir holding *.sql (the one `builtin:sql` has always used), or None."""
    for d in MIGRATION_DIRS:
        p = Path(root) / d
        if p.is_dir() and any(p.glob("*.sql")):
            return d
    return None


_HAS_PY = {}


def _has_python(root, cg):
    """True when the project has at least one .py file (code_graph.list_files, generic globs); memoised."""
    key = str(Path(root).resolve())
    if key not in _HAS_PY:
        try:
            _HAS_PY[key] = bool(cg.list_files(Path(root), list(cg.GENERIC_GLOBS)))
        except Exception:
            _HAS_PY[key] = False
    return _HAS_PY[key]


def _autodetect(root):  # aidd:FR-014 aidd:FR-021 aidd:FR-029 aidd:FR-030
    root = Path(root)
    out = []
    if (HERE / "code_graph.py").is_file():
        cg = _module("code_graph")
        globs = None
        try:
            if cg is not None and _has_python(root, cg):     # nothing to graph -> no `code` row
                globs = list(cg.default_globs(root))
        except Exception:
            globs = None
        if globs:
            out.append({"name": "code", "kind": "code", "output": ".aidd/graphs/code.json",
                        "refresh": "builtin:code", "watch": globs})
    if (HERE / "method_graph.py").is_file() and (root / "skill" / "SKILL.md").is_file():
        out.append({"name": "method", "kind": "method", "output": ".aidd/graphs/method.json",
                    "refresh": "builtin:method", "watch": ["skill/**", "commands/**", ".aidd/graphs/code.json"]})
    if (root / "graphify-out" / "graph.json").is_file():
        # third-party graph: renamed `code-graphify` by load_registry (the name `code` is the builtin)
        out.append({"name": "code", "kind": "code", "output": "graphify-out/graph.json", "refresh": "", "watch": []})
    d = _migration_dir(root)
    if d:
        out.append({"name": "db", "kind": "db", "output": ".aidd/graphs/db.json",
                    "refresh": "builtin:sql", "watch": [d + "/**"]})
        out.append({"name": "db-schema", "kind": "db", "output": ".aidd/graphs/db-schema.json",
                    "refresh": "builtin:sql-schema", "watch": [d + "/**"]})
        out.append({"name": "db-dml", "kind": "db", "output": ".aidd/graphs/db-dml.json",
                    "refresh": "builtin:sql-dml", "watch": [d + "/**"]})
    specs = root / "specs"
    if (specs / "index.toon").is_file() or any(specs.glob("*/spec.md")):
        refresh = "builtin:spec" if (HERE / "find_spec.py").is_file() else ""
        out.append({"name": "spec", "kind": "spec", "output": "specs/index.toon", "refresh": refresh,
                    "watch": ["specs/**"] if refresh else []})
    if any(specs.glob("*/tasks.md")):
        # amendment to spec 004: AIDD's own implementation-progress graph (no third-party tool)
        out.append({"name": "progress", "kind": "progress", "output": ".aidd/graphs/progress.json",
                    "refresh": "builtin:progress", "watch": ["specs/**"]})
    if (HERE / "component_graph.py").is_file():
        out.append({"name": "ui", "kind": "ui", "output": ".aidd/graphs/ui.toon",
                    "refresh": "builtin:ui",
                    "watch": ["src/**", "components/**", "lib/**", "specs/**", "design-system/**"]})
    return out


def _rename_foreign_code(e):  # aidd:FR-014
    """A `code` row whose Refresh is not `builtin:code` becomes `code-<first word of its refresh>`."""
    if e["name"].lower() != "code" or e["refresh"].strip().lower() == "builtin:code":
        return e
    words = e["refresh"].strip().split()
    if words:
        tool = Path(words[0].strip("\"'")).stem.lower()
    else:
        tool = "graphify" if "graphify" in str(e.get("output", "")).lower() else "external"
    tool = re.sub(r"[^\w.-]", "_", tool) or "external"
    new = "code-" + tool
    _warn("warning: %s graph 'code' (refresh %s) renamed '%s'; the name 'code' is the built-in code graph "
          "(builtin:code)" % (e.get("source", "?"), e["refresh"].strip() or "-", new))
    return dict(e, name=new, renamed_from="code")


def load_registry(root):
    try:
        root = Path(root)
        charter = [_rename_foreign_code(dict(e, source="charter")) for e in _parse_charter(root)]
        names = {e["name"].lower() for e in charter}
        auto = []
        for e in _autodetect(root):
            e = _rename_foreign_code(dict(e, source="auto"))
            if e["name"].lower() in names:
                continue
            names.add(e["name"].lower())
            auto.append(e)
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


def _walk_watch(root, w):
    """Candidate files for one watch glob by os.walk below its static prefix (fallback without git)."""
    root = Path(root)
    static = []
    for seg in w.replace("\\", "/").split("/"):
        if any(c in seg for c in "*?"):
            break
        static.append(seg)
    base = root.joinpath(*static) if static else root
    if base.is_file():
        return [base]
    cands = []
    for dp, dn, fn in os.walk(base):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        cands += [Path(dp) / f for f in fn]
    return cands


def _newest_watched(root, e):
    """Newest mtime among files matching the entry's watch globs (None when none). Display only, never
    the freshness verdict (aidd:FR-021)."""
    root = Path(root)
    newest, own = None, _rel(root, e["output"]) if e["output"] else None
    for w in e["watch"]:
        rx = _glob_re(w)
        for f in _walk_watch(root, w):
            rel = _rel(root, f)
            if rel == own or not rx.match(rel):
                continue
            try:
                m = f.stat().st_mtime
            except OSError:
                continue
            newest = m if newest is None or m > newest else newest
    return newest


# ----------------------------------------------------------------------------- content hashes (aidd:FR-021)

def _git(root, args, data=None):
    try:
        env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", LC_ALL="C")
        r = subprocess.run(["git", "-C", str(Path(root).resolve())] + list(args), cwd=tempfile.gettempdir(), env=env, input=data, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=GIT_TIMEOUT, creationflags=_CREATE_NO_WINDOW)
    except Exception:
        return None
    return r.stdout if r.returncode == 0 else None


def _ls_files(root):
    """Repo files (tracked + untracked not ignored), memoised per process; None without git."""
    key = str(Path(root).resolve())
    if key not in _LS_MEMO:
        raw = _git(root, ["ls-files", "-c", "-o", "--exclude-standard", "-z"])
        _LS_MEMO[key] = None if raw is None else sorted(
            {x.replace("\\", "/") for x in raw.decode("utf-8", errors="surrogateescape").split("\0") if x})
    return _LS_MEMO[key]


def _watched_files(root, e):
    """Relative paths of the files a graph watches (its own output and sidecars excluded)."""
    root = Path(root)
    if not e["watch"]:
        return []
    if e["refresh"].strip().lower() == "builtin:code":
        cg = _module("code_graph")
        if cg is not None:
            try:
                return list(cg.list_files(root, e["watch"]))   # same file set the generator parses
            except Exception:
                pass
    own = _rel(root, e["output"]) if e["output"] else None
    rxs = [_glob_re(w) for w in e["watch"]]
    listed = _ls_files(root)
    if listed is None:
        listed = sorted({_rel(root, f) for w in e["watch"] for f in _walk_watch(root, w)})
    out = []
    for rel in listed:
        if "\n" in rel or any(x in SKIP_DIRS for x in rel.split("/")):
            continue
        if own and (rel == own or rel.startswith(own + ".")):
            continue
        if any(rx.match(rel) for rx in rxs) and (root / rel).is_file():
            out.append(rel)
    # literal watch paths (e.g. method's input .aidd/graphs/code.json) count even when git ignores them;
    # only the graph's OWN output/sidecars are excluded
    for w in e["watch"]:
        lit = w.replace("\\", "/").lstrip("/")
        if lit.startswith("./"):
            lit = lit[2:]
        if any(c in lit for c in "*?") or lit in out or (own and (lit == own or lit.startswith(own + "."))):
            continue
        if (root / lit).is_file():
            out.append(lit)
    return out


def _blob_sha(path):
    data = Path(path).read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _file_shas(root, rels):
    """{rel: blob sha} for the rels not memoised yet: ONE manifest pass (code_graph.file_shas = one
    `git hash-object --stdin-paths`), stdlib sha1 fallback. Never stat/mtime."""
    key = str(Path(root).resolve())
    need = sorted({r for r in rels if (key, r) not in _SHA_MEMO})
    if need:
        got = None
        cg = _module("code_graph")
        if cg is not None:
            try:
                got = cg.file_shas(root, need)
            except Exception:
                got = None
        if got is None:
            got = {}
            for r in need:
                try:
                    got[r] = _blob_sha(Path(root) / r)
                except OSError:
                    continue
        for r in need:
            _SHA_MEMO[(key, r)] = got.get(r)
    return {r: _SHA_MEMO.get((key, r)) for r in rels}


def _inputs_hashes(root, entries):
    """{name: (inputs_hash, count)} for the given registry entries, one sha pass for all of them."""
    files = {}
    for e in entries:
        try:
            files[e["name"]] = _watched_files(root, e)
        except Exception:
            files[e["name"]] = []
    shas = _file_shas(root, sorted({r for v in files.values() for r in v}))
    out = {}
    for name, rels in files.items():
        h = hashlib.sha256()
        n = 0
        for r in sorted(rels):
            s = shas.get(r)
            if s:
                h.update(("%s\0%s\n" % (r, s)).encode("utf-8", errors="surrogateescape"))
                n += 1
        out[name] = (h.hexdigest(), n)
    return out


def _stamp_path(root, e):
    """Stamps live under <root>/.aidd/graphs/stamps/<name>.stamp.json, never next to a tracked output."""
    return Path(root) / ".aidd" / "graphs" / "stamps" / (re.sub(r"[^\w.-]", "_", e["name"]) + STAMP_SUFFIX)


def _read_stamp(root, e):
    """New location first; the legacy `<output>.stamp.json` only as a fallback."""
    cands = [_stamp_path(root, e)] + ([Path(e["output"] + STAMP_SUFFIX)] if e["output"] else [])
    for p in cands:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                return d
        except Exception:
            continue
    return None


def _write_stamp(root, e, hashed):
    try:
        p = _stamp_path(root, e)
        if not e["output"] or not Path(e["output"]).is_file():
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name("%s.tmp.%d" % (p.name, os.getpid()))
        tmp.write_text(json.dumps({"inputs_hash": hashed[0], "inputs": hashed[1]}), encoding="utf-8")
        os.replace(str(tmp), str(p))
    except Exception:
        pass


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


def _command(root, e):  # aidd:FR-014 aidd:FR-016 aidd:FR-021 aidd:FR-029 aidd:FR-030
    """(argv_or_str, shell) for the entry's refresh, or (None, False) when read-only."""
    r = e["refresh"].strip()
    if not r:
        return None, False
    rl = r.lower()
    # builtins run with cwd = the OS temp dir (see _cwd_for) and get the project ONLY through absolute paths
    py, out, R = sys.executable, e["output"], str(Path(root).resolve())
    dirs = [str(Path(R) / (w[:-3] if w.endswith("/**") else w)) for w in e["watch"]]
    if rl == "builtin:sql":
        return [py, str(HERE / "sql_graph.py"), "--root", R, "--out", out, *dirs], False
    if rl in ("builtin:sql-schema", "builtin:sql-dml"):
        return [py, str(HERE / "sql_graph.py"), "--root", R, "--out", out,
                "--kind", "schema" if rl.endswith("schema") else "dml",
                "--checkpoint", out + ".ckpt.json", "--cache", out + ".dml.json", *dirs], False
    if rl == "builtin:progress":
        return [py, str(HERE / "aidd_progress.py"), "--root", R, "--quiet"], False
    if rl == "builtin:code":
        argv = [py, str(HERE / "code_graph.py"), "--root", R, "--out", out, "--quiet"]
        if e["watch"]:
            argv += ["--globs", ",".join(e["watch"])]
        return argv, False
    if rl == "builtin:method":   # no --quiet: it would drop the summary line
        return [py, str(HERE / "method_graph.py"), "--root", R, "--out", out], False
    if rl == "builtin:spec":     # `aidd reindex` work (find_spec build_index/save_index) by --root, not by cwd
        return [py, str(Path(__file__).resolve()), "--root", R, "_reindex"], False
    if rl == "builtin:ui":
        return [py, str(HERE / "component_graph.py"), "--root", R, "--out", out, "--build"], False
    return r, True


def _cwd_for(root, e):
    """Builtins run with cwd = the OS temp dir so no process pins the project folder (Windows cannot delete a
    directory that is a process cwd); a charter shell command keeps cwd = root (it may rely on it)."""
    return tempfile.gettempdir() if e["refresh"].strip().lower().startswith("builtin:") else str(root)


def _reindex(root):  # aidd:FR-021
    """Rebuild <root>/specs/index.toon through find_spec's own functions (same as `find_spec.py --reindex`)."""
    fs = _module("find_spec")
    if fs is None:
        print("spec index: find_spec.py is not importable next to aidd_graphs.py")
        return 1
    specs_root = Path(root).resolve() / "specs"
    if not specs_root.is_dir():
        print("spec index: no specs/ folder under %s" % specs_root.parent)
        return 1
    spec_dirs = sorted(p for p in specs_root.iterdir() if p.is_dir())
    index = fs.build_index(specs_root, spec_dirs)
    fs.save_index(specs_root, index)
    print("spec index: rebuilt %s, %d spec(s) indexed" % (specs_root / fs.INDEX_FILENAME, len(index["specs"])))
    return 0


_SUMMARY_RE = re.compile(r"re-parsed|reused|^db-schema:|^db-dml:|^method graph:|^code graph:|^db graph|^spec index:", re.I)


def _summary(log):
    """The generator's summary line(s) from its log; else its last non-empty line."""
    try:
        lines = [ln.strip() for ln in Path(log).read_text(encoding="utf-8", errors="replace").splitlines()
                 if ln.strip()]
    except Exception:
        return ""
    hits = [ln for ln in lines if _SUMMARY_RE.search(ln)]
    return " | ".join(hits[-3:]) if hits else (lines[-1][:200] if lines else "")


def _run_and_stamp(root, e, stdout=None):  # aidd:FR-021
    """Run the refresh synchronously; on exit 0 write `<output>.stamp.json` with the inputs hash taken
    BEFORE the run (an edit during the build leaves the graph stale, never falsely fresh)."""
    cmd, shell = _command(root, e)
    if cmd is None:
        return 1
    hashed = None
    try:
        hashed = _inputs_hashes(root, [e]).get(e["name"])
    except Exception:
        hashed = None
    if e["output"]:
        Path(e["output"]).parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(cmd, shell=shell, cwd=_cwd_for(root, e), stdout=stdout, stderr=subprocess.STDOUT,
                       timeout=SYNC_TIMEOUT)
    if p.returncode == 0 and hashed:
        _write_stamp(root, e, hashed)
    return p.returncode


def refresh(root, name, background=True, force=False):
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
        if not force and stamp.exists() and time.time() - stamp.stat().st_mtime < DEBOUNCE_S:
            res["reason"] = "debounced"
            return res
        if e["output"]:
            Path(e["output"]).parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(str(time.time()))
        if not background:
            with open(log, "wb") as lf:
                rc = _run_and_stamp(root, e, stdout=lf)
            stamp.write_text(str(time.time()))
            res.update(started=True, reason="finished", exit=rc, summary=_summary(log))
            return res
        kw = {}
        if os.name == "nt":
            kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000   # DETACHED|NEW_PROCESS_GROUP|NO_WINDOW
        else:
            kw["start_new_session"] = True
        # the detached wrapper runs the generator and writes the content stamp when it succeeds
        wrapper = [sys.executable, str(Path(__file__).resolve()), "--root", str(Path(root).resolve()), "_run", e["name"]]
        with open(log, "wb") as lf:
            p = subprocess.Popen(wrapper, shell=False, cwd=tempfile.gettempdir(), stdin=subprocess.DEVNULL,
                                 stdout=lf, stderr=subprocess.STDOUT, **kw)
        lock.write_text(str(p.pid))
        res.update(started=True, reason="started", pid=p.pid)
        return res
    except Exception as ex:
        res["reason"] = "error: %s" % ex
        return res


# ----------------------------------------------------------------------------- status

def status(root, names=None):  # aidd:FR-021
    """One row per graph. State running|no-refresh|missing|stale|fresh; stale/fresh by the content hash of
    the watched files against `<output>.stamp.json` (missing stamp = stale). `names` limits the rows."""
    out = []
    try:
        now = time.time()
        reg = [e for e in load_registry(root)
               if names is None or e["name"].lower() in {str(n).lower() for n in names}]
        hashable = [e for e in reg if e["refresh"].strip() and e["output"] and Path(e["output"]).is_file()]
        try:
            hashes = _inputs_hashes(root, hashable) if hashable else {}
        except Exception:
            hashes = {}
        for e in reg:
            row = {"name": e["name"], "kind": e["kind"], "output": e["output"], "state": "missing",
                   "age_s": None, "newest_watched_age_s": None, "inputs": None}
            try:
                o = Path(e["output"]) if e["output"] else None
                exists = bool(o and o.is_file())
                if exists:
                    row["age_s"] = int(now - o.stat().st_mtime)
                try:
                    newest = _newest_watched(root, e) if e["watch"] else None
                except Exception:
                    newest = None
                if newest is not None:
                    row["newest_watched_age_s"] = int(now - newest)
                cur = hashes.get(e["name"])
                if cur:
                    row["inputs"] = cur[1]
                if _lock_live(_paths(root, e["name"])[1]):
                    row["state"] = "running"
                elif not e["refresh"].strip():
                    row["state"] = "no-refresh" if exists else "missing"
                elif not exists:
                    row["state"] = "missing"
                else:
                    st = _read_stamp(root, e)
                    row["state"] = "fresh" if (st and cur and st.get("inputs_hash") == cur[0]) else "stale"
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


def _fmt_list(v, cap=8):
    v = list(v)
    return ", ".join(v[:cap]) + (" ... +%d more" % (len(v) - cap) if len(v) > cap else "") if v else "-"


def _code_titles(root, codes):  # aidd:FR-015
    """{code: 'spec-id (title): node label'} joined at query time from the find_spec index (never merged)."""
    out = {}
    fs = _module("find_spec")
    if fs is None or not codes:
        return out
    try:
        sr = fs.find_specs_root(Path(root))
        idx = fs.load_index(sr) if sr else None
        specs = (idx or {}).get("specs") or {}
    except Exception:
        return out
    graphs = {}
    for sid in sorted(specs):     # FR/AC/T rows live in each spec's graph nodes, not in the `codes` column
        try:
            graphs[sid] = {str(k).upper(): v for k, v in fs.decode_graph((specs[sid] or {}).get("graph")).get("nodes", {}).items()}
        except Exception:
            graphs[sid] = {}
    for c in codes:
        best = None
        for sid in sorted(specs):
            s = specs[sid] or {}
            node = graphs[sid].get(str(c).upper())
            if node is None and c not in (s.get("codes") or []):
                continue
            rank = 0 if node and str(node.get("file", "")).endswith("spec.md") else 1 if node else 2
            if best is None or rank < best[0]:
                best = (rank, sid, str(s.get("title", "")), str((node or {}).get("label", "")))
        if best:
            out[c] = "%s (%s)%s" % (best[1], best[2][:60], (": " + best[3][:70]) if best[3] else "")
    return out


def _task_targets(root, tcodes, src):  # aidd:FR-015
    """{T-nn: 'spec/T-nn [state] targets ...'} joined from .aidd/graphs/progress.json at query time."""
    out = {}
    try:
        nodes, edges = _load_graph(Path(root) / ".aidd" / "graphs" / "progress.json")
    except Exception:
        return out
    tg = {}
    for ed in edges:
        if ed.get("relation") == "targets":
            tg.setdefault(str(ed.get("source")), []).append(str(ed.get("target")))
    for t in tcodes:
        cands = [n for n in nodes if n.get("type") == "T" and str(n.get("label", "")).upper() == t]
        mine = [n for n in cands if src and src in tg.get(_nid(n), [])] or cands[:2]
        if mine:
            out[t] = "; ".join("%s [%s] targets %s" % (_nid(n), n.get("state", "?"), _fmt_list(tg.get(_nid(n), []), 3))
                               for n in mine[:2])
    return out


def _show_code(root, e, nodes, edges, query, limit, stale):  # aidd:FR-015 aidd:FR-014
    q = str(query).strip().replace("\\", "/").lower()
    byid = {_nid(n): n for n in nodes}

    def sc(n):
        nid, lab = _nid(n).lower(), str(n.get("label", "")).lower()
        if nid == q:
            return 0
        if n.get("type") == "FILE":
            if nid.endswith("/" + q):
                return 1
        elif lab == q or lab.endswith("." + q) or nid.endswith("::" + q):
            return 1
        return 3 if q and q in nid else 9

    scored = sorted(((sc(n), len(_nid(n)), _nid(n)) for n in nodes if n.get("type") in ("FUNC", "FILE")))
    scored = [t for t in scored if t[0] < 9]
    if not scored:
        return "No FUNC/FILE matching '%s' in graph '%s'. %s" % (query, e["name"], stale)
    nid = scored[0][2]
    n = byid[nid]
    calls_out, calls_in, sinks, impl, imports_out, imports_in, defines = {}, {}, {}, [], [], [], []
    for ed in edges:
        s, t, rel = str(ed.get("source")), str(ed.get("target")), ed.get("relation", ed.get("type", ""))
        if rel == "calls":
            calls_out.setdefault(s, []).append(t)
            calls_in.setdefault(t, []).append(s)
        elif rel in ("reads", "spawns"):
            sinks.setdefault(s, set()).add(t)
        elif rel == "implements" and s == nid:
            impl.append(t)
        elif rel == "imports":
            if s == nid:
                imports_out.append(t)
            elif t == nid:
                imports_in.append(s)
        elif rel == "defines" and s == nid:
            defines.append(t)
    lines = [stale] if stale else []
    lines.append("%s  [%s]  %s" % (nid, n.get("type", "?"), n.get("source_location", n.get("source_file", ""))))
    if len(scored) > 1:
        lines.append("  also matches: %s" % _fmt_list([t[2] for t in scored[1:]], 4))
    for k in ("sha", "runtime"):
        if n.get(k) not in (None, "", [], {}):
            lines.append("  %s: %s" % (k, json.dumps(n[k], sort_keys=True)[:160] if not isinstance(n[k], str) else n[k]))
    starts = [nid]
    if n.get("type") == "FILE":
        funcs = [d for d in defines if byid.get(d, {}).get("type") == "FUNC"]
        lines.append("  imported by: %s" % _fmt_list(sorted(set(imports_in))))
        lines.append("  imports: %s" % _fmt_list(sorted(set(imports_out))))
        lines.append("  defines: %d funcs (%s)" % (len(funcs), _fmt_list(sorted(f.split("::")[-1] for f in funcs), 6)))
        starts += funcs
    else:
        lines.append("  callers: %s" % _fmt_list(sorted(set(calls_in.get(nid, [])))))
        lines.append("  callees: %s" % _fmt_list(sorted(set(calls_out.get(nid, [])))))
    ext = n.get("ext") or []
    lines.append("  ext: %d external calls%s" % (len(ext), (" (%s)" % _fmt_list(ext, 5)) if ext else ""))
    direct = set()
    for s in starts:
        direct |= sinks.get(s, set())
    seen, todo, reached = set(starts), list(starts), set()
    while todo and len(seen) < 5000:                      # transitive sinks through `calls`
        cur = todo.pop()
        reached |= sinks.get(cur, set())
        for t in calls_out.get(cur, []):
            if t not in seen:
                seen.add(t)
                todo.append(t)

    def lab(s):
        sn = byid.get(s, {})
        return "%s (%s)" % (sn.get("label", s), sn.get("sink_kind", "sink")) if sn else s

    lines.append("  sinks direct: %s" % _fmt_list(sorted(lab(s) for s in direct)))
    lines.append("  sinks reached: %s" % _fmt_list(sorted(lab(s) for s in (reached - direct))))
    impl = sorted(set(impl))
    titles = _code_titles(root, [c for c in impl if not c.upper().startswith("T-")])
    plain = [c for c in impl if c not in titles]          # find_spec missing -> plain code ids
    if plain or not impl:
        lines.append("  implements: %s" % _fmt_list(plain))
    for c in impl:                                          # AC-010: spec id + title + FR row label
        if c in titles:
            lines.append("  implements: %s -> %s" % (c, titles[c]))
    tasks = _task_targets(root, [c.upper() for c in impl if c.upper().startswith("T-")], n.get("source_file", ""))
    for c, v in tasks.items():
        lines.append("    %s -> %s" % (c, v))
    if len(lines) > limit:
        lines = lines[:limit - 1] + ["... +%d more" % (len(lines) - limit + 1)]
    return "\n".join(lines)


def _show_method(e, nodes, edges, query, limit, stale):  # aidd:FR-016
    q = str(query).strip()
    m = re.fullmatch(r"(?i)(?:step[:\s]*)(-?\d+(?:\.\d+)?)", q)
    key = ("STEP:" + m.group(1)) if m else q
    byid = {_nid(n): n for n in nodes}
    hit = next((i for i in byid if i.lower() == key.lower()), None)
    if hit is None:
        hits = sorted((_score(n, key.lower()), len(_nid(n)), _nid(n)) for n in nodes)
        hits = [h for h in hits if h[0] < 9 and byid[h[2]].get("type") != "FUNC"] or \
               [h for h in hits if h[0] < 9]
        if not hits:
            return "No rule/step/command matching '%s' in graph '%s'. %s" % (query, e["name"], stale)
        hit = hits[0][2]
    n = byid[hit]
    lines = [stale] if stale else []
    lines.append("%s  [%s]  %s" % (hit, n.get("type", "?"), n.get("source_location", "")))
    if n.get("label") and n.get("label") != hit:
        lines.append("  %s" % str(n["label"])[:160])
    out_g, in_g = {}, {}
    for ed in edges:
        s, t, rel = str(ed.get("source")), str(ed.get("target")), ed.get("relation", "rel")
        if s == hit:
            out_g.setdefault(rel, []).append(t)
        elif t == hit:
            in_g.setdefault(rel, []).append(s)
    if n.get("type") == "RULE":
        enf = out_g.pop("enforced_by", [])
        lines.append("  enforced by: %s" % _fmt_list([byid.get(f, {}).get("source_location") and
                                                       "%s (%s)" % (f, byid[f]["source_location"]) or f for f in enf], 6))
        lines.append("  unlinked: %s" % ("yes" if n.get("unlinked") else "no"))
        lines.append("  cited by: %s" % _fmt_list(sorted(in_g.pop("cites", []))))
    for k, v in sorted(out_g.items()):
        lines.append("  -> %s: %s" % (k, _fmt_list(sorted(v))))
    for k, v in sorted(in_g.items()):
        lines.append("  <- %s: %s" % (k, _fmt_list(sorted(v))))
    if len(lines) > limit:
        lines = lines[:limit - 1] + ["... +%d more" % (len(lines) - limit + 1)]
    return "\n".join(lines)


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
        for s in status(root, names=[e["name"]]):
            if s["name"] == e["name"] and s["state"] == "stale":
                stale = "(graph is stale; refresh: aidd graphs refresh %s --background)" % name
        rl = e["refresh"].strip().lower()
        if e["kind"] == "ui" or rl == "builtin:ui":
            cg = _module("component_graph")
            if cg is not None and hasattr(cg, "show_ui"):
                return cg.show_ui(root, query, limit=limit, graph_path=Path(e["output"]), stale=stale)
            return "component_graph module not found or missing show_ui"
        nodes, edges = _load_graph(e["output"])
        if rl == "builtin:code":
            return _show_code(root, e, nodes, edges, query, limit, stale)
        if rl == "builtin:method":
            return _show_method(e, nodes, edges, query, limit, stale)
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


def auto(root, words, limit=6):  # aidd:FR-021
    """Step -1 helper, no questions asked: for every project graph start a background refresh when it is
    missing or stale (debounced, lock-protected) and return at most `limit` short lines: its state plus the
    nodes whose name or purpose match the query `words` (tables, views and functions first). The spec graph
    is refreshed only when its refresh is `builtin:spec` and never queried here (find_spec covers it).
    [] when nothing is declared or AIDD_GRAPHS=off. Never raises."""
    try:
        if str(os.environ.get("AIDD_GRAPHS", "")).strip().lower() in ("off", "0", "false", "no"):
            return []
        words = [str(w).lower() for w in words if len(str(w)) >= 3]
        refreshes = {e["name"]: e["refresh"].strip().lower() for e in load_registry(root)}
        out = []
        for st in status(root):
            is_spec = st["kind"] == "spec"
            if is_spec and refreshes.get(st["name"]) != "builtin:spec":
                continue
            note = st["state"]
            if st["state"] in ("missing", "stale"):
                r = refresh(root, st["name"], background=True)
                if r.get("started"):
                    note += ", refresh started in background"
                elif r.get("reason") == "debounced":
                    note += ", refresh already requested"
            head = "Graph '%s' (%s): %s" % (st["name"], st["kind"], note)
            if is_spec:
                if st["state"] != "fresh":
                    out.append(head)
                continue
            if not st["output"] or not Path(st["output"]).is_file():
                out.append(head + "; no data yet, read the sources this time")
                continue
            try:
                nodes, _edges = _load_graph(st["output"])
            except Exception:
                out.append(head + "; graph unreadable")
                continue
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


def _flush_warnings():
    for w in _WARNINGS:
        print(w, file=sys.stderr)
    del _WARNINGS[:]


def _delegate(cmd, root, rest):  # aidd:FR-017 aidd:FR-018 aidd:FR-019 aidd:FR-020 aidd:FR-023
    """`repeats|snapshot|diff|changed` -> graph_snapshot.main, `trace` -> graph_trace.main; their exit code."""
    modname = "graph_trace" if cmd == "trace" else "graph_snapshot"
    mod = _module(modname)
    if mod is None or not hasattr(mod, "main"):
        print("aidd graphs %s: %s.py is not installed next to aidd_graphs.py (or failed to import)."
              % (cmd, modname))
        return 1
    if cmd == "trace":
        argv = ["--root", str(root)] + (list(rest) if "--" in rest else ["--"] + list(rest))
    else:
        argv = ["--root", str(root), cmd] + list(rest)
    try:
        rc = mod.main(argv)
    except SystemExit as ex:
        rc = ex.code if isinstance(ex.code, int) else (0 if ex.code is None else 1)
    return int(rc or 0)


def main(argv):
    argv = list(argv)
    root = Path.cwd()
    if len(argv) >= 2 and argv[0] == "--root":
        root, argv = Path(argv[1]), argv[2:]
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    try:
        if cmd in ("repeats", "snapshot", "diff", "changed", "trace"):
            return _delegate(cmd, root, rest)
        if cmd == "_reindex":              # internal: builtin:spec, project by --root only
            return _reindex(root)
        if cmd == "_run" and rest:          # internal: the detached background refresh of one graph
            e = _get(root, rest[0])
            if e is None:
                print("unknown graph '%s'" % rest[0])
                return 1
            sys.stdout.flush()
            return _run_and_stamp(root, e, stdout=None)
        if cmd == "list":
            for e in load_registry(root):
                print("%-10s %-6s %-7s %s  refresh=%s  watch=%s" % (e["name"], e["kind"], e["source"], e["output"],
                                                                   e["refresh"] or "-", ",".join(e["watch"]) or "-"))
            _flush_warnings()
            return 0
        if cmd == "status":
            rows = status(root)
            if "--json" in rest:
                print(json.dumps(rows, indent=2))
            else:
                for r in rows:
                    print("%-10s %-10s age=%s newest_watched=%s inputs=%s  %s"
                          % (r["name"], r["state"], _fmt_age(r["age_s"]), _fmt_age(r["newest_watched_age_s"]),
                             "-" if r.get("inputs") is None else r["inputs"], r["output"]))
            _flush_warnings()
            return 0
        if cmd == "refresh" and rest:
            force = "--force" in rest
            wait = "--wait" in rest
            names = [e["name"] for e in load_registry(root) if e["refresh"].strip()] if rest[0] == "all" else [rest[0]]
            code = 0
            for n in names:
                r = refresh(root, n, background=not wait, force=force)
                print("%s: %s%s (log: %s)" % (n, r["reason"], " pid=%s" % r["pid"] if r["pid"] else "", r["log"]))
                if wait and r.get("summary"):
                    print("  %s" % r["summary"])                  # aidd:FR-024 `re-parsed N, reused M`
                if r.get("exit"):
                    code = 1
                elif not r["started"] and r["reason"] not in ("debounced", "already running") and rest[0] != "all":
                    code = 1
            _flush_warnings()
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
