"""Tests for skill/scripts/aidd_graphs.py (project graphs registry)."""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill" / "scripts"))
import aidd_graphs as G  # noqa: E402

CHARTER = """# Charter

## Graphs

| Name | Kind | Output | Refresh | Watch |
|------|------|--------|---------|-------|
| `db`  |  DB | `.aidd/graphs/db.json` | `builtin:sql` | `eDoc/supabase/migrations/**` |
| code | code | graphify-out/graph.json |  | src/**, lib\\**/*.py |

## Other
text
"""


def _w(p, text="x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_charter_parsing_tolerant(tmp_path):
    _w(tmp_path / "charter.md", CHARTER)
    reg = {e["name"]: e for e in G.load_registry(tmp_path)}
    assert set(reg) == {"db", "code"}
    assert reg["db"]["kind"] == "db" and reg["db"]["refresh"] == "builtin:sql"
    assert reg["db"]["watch"] == ["eDoc/supabase/migrations/**"]
    assert reg["db"]["source"] == "charter"
    assert reg["db"]["output"].endswith(".aidd/graphs/db.json") and Path(reg["db"]["output"]).is_absolute()
    assert reg["code"]["watch"] == ["src/**", "lib/**/*.py"] and reg["code"]["refresh"] == ""


def test_missing_charter_and_empty(tmp_path):
    assert G.load_registry(tmp_path) == []
    assert G.status(tmp_path) == []
    assert G.match_watch(tmp_path, "a/b") == []


def test_autodetect_and_charter_wins(tmp_path):
    _w(tmp_path / "graphify-out" / "graph.json", "{}")
    _w(tmp_path / "db" / "migrations" / "001.sql", "create table t(id int);")
    _w(tmp_path / "specs" / "index.toon", "")
    reg = {e["name"]: e for e in G.load_registry(tmp_path)}
    assert set(reg) == {"code", "db", "spec"}
    assert reg["db"]["refresh"] == "builtin:sql" and reg["db"]["watch"] == ["db/migrations/**"]
    assert reg["db"]["source"] == "auto"
    _w(tmp_path / "charter.md", "## Graphs\n| Name | Kind | Output | Refresh | Watch |\n|--|--|--|--|--|\n| db | db | x/db.json | echo hi | a/** |\n")
    reg = {e["name"]: e for e in G.load_registry(tmp_path)}
    assert reg["db"]["source"] == "charter" and reg["db"]["refresh"] == "echo hi"
    assert reg["code"]["source"] == "auto"


def test_match_watch_globs(tmp_path):
    _w(tmp_path / "charter.md", CHARTER)
    assert G.match_watch(tmp_path, "eDoc/supabase/migrations/a/b/001.sql") == ["db"]
    assert G.match_watch(tmp_path, "eDoc\\supabase\\migrations\\001.sql") == ["db"]
    assert G.match_watch(tmp_path, str(tmp_path / "src" / "x" / "y.ts")) == ["code"]
    assert G.match_watch(tmp_path, "lib/a/b/c.py") == ["code"]
    assert G.match_watch(tmp_path, "lib/a/b/c.txt") == []
    assert G.match_watch(tmp_path, "src/node_modules/x.js") == []
    assert G.match_watch(tmp_path, "src/.git/x") == []
    assert G.match_watch(tmp_path, "other/file") == []


def test_match_watch_ignores_own_output(tmp_path):
    _w(tmp_path / "charter.md", "## Graphs\n| Name | Kind | Output | Refresh | Watch |\n|--|--|--|--|--|\n| g | code | src/out.json | echo | src/** |\n")
    assert G.match_watch(tmp_path, "src/out.json") == []
    assert G.match_watch(tmp_path, "src/a.ts") == ["g"]


def test_status_states(tmp_path):
    _w(tmp_path / "charter.md", CHARTER + "")
    _w(tmp_path / "eDoc" / "supabase" / "migrations" / "001.sql")
    st = {r["name"]: r for r in G.status(tmp_path)}
    assert st["db"]["state"] == "missing" and st["code"]["state"] == "missing"
    out = _w(tmp_path / ".aidd" / "graphs" / "db.json", "{}")
    now = time.time()
    os.utime(tmp_path / "eDoc/supabase/migrations/001.sql", (now - 100, now - 100))
    os.utime(out, (now - 10, now - 10))
    st = {r["name"]: r for r in G.status(tmp_path)}
    assert st["db"]["state"] == "fresh" and st["db"]["age_s"] >= 9
    os.utime(tmp_path / "eDoc/supabase/migrations/001.sql", (now, now))
    os.utime(out, (now - 50, now - 50))
    assert {r["name"]: r for r in G.status(tmp_path)}["db"]["state"] == "stale"
    # read-only graph: just exists/missing
    _w(tmp_path / "graphify-out" / "graph.json", "{}")
    assert {r["name"]: r for r in G.status(tmp_path)}["code"]["state"] == "no-refresh"


def test_status_running(tmp_path, monkeypatch):
    _w(tmp_path / "charter.md", CHARTER)
    _, lock, _ = G._paths(tmp_path, "db")
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(str(os.getpid()))            # this very process is alive
    try:
        assert {r["name"]: r for r in G.status(tmp_path)}["db"]["state"] == "running"
        old = time.time() - G.LOCK_MAX_AGE - 5   # stale lock no longer holds
        os.utime(lock, (old, old))
        assert {r["name"]: r for r in G.status(tmp_path)}["db"]["state"] == "missing"
    finally:
        lock.unlink()


def _cmd_charter(tmp_path, cmd):
    _w(tmp_path / "charter.md", "## Graphs\n| Name | Kind | Output | Refresh | Watch |\n|--|--|--|--|--|\n| t | code | out/t.json | %s | src/** |\n" % cmd)


def _clean(root, name):
    for p in G._paths(root, name):
        if p.exists():
            p.unlink()


def test_refresh_sync_and_debounce(tmp_path):
    _cmd_charter(tmp_path, '`python -c "print(1)"`')
    _clean(tmp_path, "t")
    try:
        r = G.refresh(tmp_path, "t", background=False)
        assert r["started"] and r["exit"] == 0
        assert Path(r["log"]).read_text().strip() == "1"
        r2 = G.refresh(tmp_path, "t", background=False)
        assert not r2["started"] and r2["reason"] == "debounced"
        _, _, stamp = G._paths(tmp_path, "t")
        old = time.time() - 120
        os.utime(stamp, (old, old))
        assert G.refresh(tmp_path, "t", background=False)["started"]
    finally:
        _clean(tmp_path, "t")


def test_refresh_lock_and_unknown(tmp_path):
    _cmd_charter(tmp_path, 'python -c "print(1)"')
    _clean(tmp_path, "t")
    try:
        assert "unknown" in G.refresh(tmp_path, "nope")["reason"]
        _, lock, _ = G._paths(tmp_path, "t")
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(str(os.getpid()))
        r = G.refresh(tmp_path, "t", background=False)
        assert not r["started"] and r["reason"] == "already running" and r["pid"] == os.getpid()
    finally:
        _clean(tmp_path, "t")


def test_refresh_readonly(tmp_path):
    _w(tmp_path / "graphify-out" / "graph.json", "{}")
    r = G.refresh(tmp_path, "code")
    assert not r["started"] and "read-only" in r["reason"]


def test_refresh_background_detached(tmp_path):
    _cmd_charter(tmp_path, 'python -c "print(2)"')
    _clean(tmp_path, "t")
    try:
        r = G.refresh(tmp_path, "t", background=True)
        assert r["started"] and r["pid"]
        for _ in range(100):                      # wait for the short child so nothing is left behind
            if not G._pid_alive(r["pid"]):
                break
            time.sleep(0.1)
        assert not G._pid_alive(r["pid"])
    finally:
        _clean(tmp_path, "t")


def _graph(tmp_path, key):
    g = {"nodes": [{"id": "orders", "type": "table", "source_file": "m/001.sql", "source_location": "L3"},
                   {"id": "orders.total", "type": "column", "data_type": "numeric", "nullable": False, "purpose": "sum"},
                   {"id": "customers", "type": "table"}],
         key: [{"source": "orders", "target": "orders.total", "relation": "has_column"},
               {"source": "orders", "target": "customers", "relation": "references"}]}
    _w(tmp_path / "graphify-out" / "graph.json", json.dumps(g))


def test_show_edges_and_links(tmp_path):
    for key in ("edges", "links"):
        _graph(tmp_path, key)
        out = G.show(tmp_path, "code", "ORDERS")
        assert out.splitlines()[0].startswith("orders  [table]")
        assert "-> has_column: orders.total" in out and "-> references: customers" in out
        assert "source: m/001.sql:L3" in out
        out = G.show(tmp_path, "code", "total")
        assert "orders.total" in out and "<- has_column: orders" in out and "data_type: numeric" in out


def test_show_limit_messages(tmp_path):
    _graph(tmp_path, "edges")
    out = G.show(tmp_path, "code", "orders", limit=3)
    assert len(out.splitlines()) == 3 and "more" in out.splitlines()[-1]
    assert "No node matching" in G.show(tmp_path, "code", "zzz")
    assert "No graph named" in G.show(tmp_path, "nope", "x")
    (tmp_path / "graphify-out" / "graph.json").unlink()
    _w(tmp_path / "charter.md", "## Graphs\n| Name | Kind | Output | Refresh | Watch |\n|--|--|--|--|--|\n| code | code | graphify-out/graph.json | echo | src/** |\n")
    assert "aidd graphs refresh code --background" in G.show(tmp_path, "code", "x")


def test_show_spec_hint(tmp_path):
    _w(tmp_path / "specs" / "index.toon", "")
    out = G.show(tmp_path, "spec", "FR-1")
    assert "find_spec.py" in out and "--code FR-1" in out


def test_cli_list_status(tmp_path, capsys):
    _w(tmp_path / "charter.md", CHARTER)
    assert G.main(["--root", str(tmp_path), "list"]) == 0
    assert "db" in capsys.readouterr().out
    assert G.main(["--root", str(tmp_path), "status", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert {r["name"] for r in rows} == {"db", "code"}
    assert G.main(["--root", str(tmp_path), "explorer", "nope"]) == 1
    assert G.main(["--root", str(tmp_path)]) == 2
