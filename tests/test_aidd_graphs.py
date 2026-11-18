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
| code | code | external-graphs/graph.json |  | src/**, lib\\**/*.py |

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
    assert set(reg) == {"db", "code-external"}
    assert reg["db"]["kind"] == "db" and reg["db"]["refresh"] == "builtin:sql"
    assert reg["db"]["watch"] == ["eDoc/supabase/migrations/**"]
    assert reg["db"]["source"] == "charter"
    assert reg["db"]["output"].endswith(".aidd/graphs/db.json") and Path(reg["db"]["output"]).is_absolute()
    assert reg["code-external"]["watch"] == ["src/**", "lib/**/*.py"] and reg["code-external"]["refresh"] == ""
    assert reg["code-external"]["renamed_from"] == "code"


def test_missing_charter_and_empty(tmp_path):
    assert G.load_registry(tmp_path) == []
    assert G.status(tmp_path) == []
    assert G.match_watch(tmp_path, "a/b") == []


def test_autodetect_and_charter_wins(tmp_path):
    _w(tmp_path / "external-graphs" / "graph.json", "{}")
    _w(tmp_path / "db" / "migrations" / "001.sql", "create table t(id int);")
    _w(tmp_path / "specs" / "index.toon", "")
    reg = {e["name"]: e for e in G.load_registry(tmp_path)}
    assert set(reg) == {"db", "db-schema", "db-dml", "spec"}
    assert reg["db"]["refresh"] == "builtin:sql" and reg["db"]["watch"] == ["db/migrations/**"]
    assert reg["db"]["source"] == "auto"
    _w(tmp_path / "charter.md", "## Graphs\n| Name | Kind | Output | Refresh | Watch |\n|--|--|--|--|--|\n| db | db | x/db.json | echo hi | a/** |\n")
    reg = {e["name"]: e for e in G.load_registry(tmp_path)}
    assert reg["db"]["source"] == "charter" and reg["db"]["refresh"] == "echo hi"
    assert reg["db-schema"]["refresh"] == "builtin:sql-schema"
    assert reg["db-dml"]["refresh"] == "builtin:sql-dml"
    _w(tmp_path / "charter.md", CHARTER)
    assert "code-external" in {e["name"] for e in G.load_registry(tmp_path)}


def test_match_watch_globs(tmp_path):
    _w(tmp_path / "charter.md", CHARTER)
    assert G.match_watch(tmp_path, "eDoc/supabase/migrations/a/b/001.sql") == ["db"]
    assert G.match_watch(tmp_path, "eDoc\\supabase\\migrations\\001.sql") == ["db"]
    assert G.match_watch(tmp_path, str(tmp_path / "src" / "x" / "y.ts")) == ["code-external"]
    assert G.match_watch(tmp_path, "lib/a/b/c.py") == ["code-external"]
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
    assert st["db"]["state"] == "missing" and st["code-external"]["state"] == "missing"
    out = _w(tmp_path / ".aidd" / "graphs" / "db.json", "{}")
    now = time.time()
    migration = tmp_path / "eDoc/supabase/migrations/001.sql"
    os.utime(migration, (now - 100, now - 100))
    os.utime(out, (now - 10, now - 10))
    entry = {e["name"]: e for e in G.load_registry(tmp_path)}["db"]
    hashed = G._inputs_hashes(tmp_path, [entry])["db"]
    G._write_stamp(tmp_path, entry, hashed)
    st = {r["name"]: r for r in G.status(tmp_path)}
    assert st["db"]["state"] == "fresh" and st["db"]["age_s"] >= 9
    os.utime(migration, (now, now))
    G._SHA_MEMO.clear()  # each CLI invocation starts with a fresh process cache
    assert {r["name"]: r for r in G.status(tmp_path)}["db"]["state"] == "fresh"
    migration.write_text("changed SQL content", encoding="utf-8")
    os.utime(migration, (now - 100, now - 100))
    G._SHA_MEMO.clear()
    assert {r["name"]: r for r in G.status(tmp_path)}["db"]["state"] == "stale"
    # read-only graph: just exists/missing
    _w(tmp_path / "external-graphs" / "graph.json", "{}")
    assert {r["name"]: r for r in G.status(tmp_path)}["code-external"]["state"] == "no-refresh"


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
    _w(tmp_path / "external-graphs" / "graph.json", "{}")
    _w(tmp_path / "charter.md", CHARTER)
    r = G.refresh(tmp_path, "code-external")
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
    _w(tmp_path / "external-graphs" / "graph.json", json.dumps(g))
    _w(tmp_path / "charter.md", CHARTER)


def test_show_edges_and_links(tmp_path):
    for key in ("edges", "links"):
        _graph(tmp_path, key)
        out = G.show(tmp_path, "code-external", "ORDERS")
        assert out.splitlines()[0].startswith("orders  [table]")
        assert "-> has_column: orders.total" in out and "-> references: customers" in out
        assert "source: m/001.sql:L3" in out
        out = G.show(tmp_path, "code-external", "total")
        assert "orders.total" in out and "<- has_column: orders" in out and "data_type: numeric" in out


def test_show_limit_messages(tmp_path):
    _graph(tmp_path, "edges")
    out = G.show(tmp_path, "code-external", "orders", limit=3)
    assert len(out.splitlines()) == 3 and "more" in out.splitlines()[-1]
    assert "No node matching" in G.show(tmp_path, "code-external", "zzz")
    assert "No graph named" in G.show(tmp_path, "nope", "x")
    (tmp_path / "external-graphs" / "graph.json").unlink()
    _w(tmp_path / "charter.md", "## Graphs\n| Name | Kind | Output | Refresh | Watch |\n|--|--|--|--|--|\n| code | code | external-graphs/graph.json | echo | src/** |\n")
    assert "aidd graphs refresh code-echo --background" in G.show(tmp_path, "code-echo", "x")


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
    assert {r["name"] for r in rows} == {"db", "code-external"}
    assert G.main(["--root", str(tmp_path), "explorer", "nope"]) == 1
    assert G.main(["--root", str(tmp_path)]) == 2


# FR-370..374. Same real graph loader/query, only refresh's process boundary is doubled.
import contextlib
import io
import tempfile
import unittest
from unittest.mock import patch


class GraphOnMiss(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='aidd-graph-query-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.path=self.root/'graph.json';self.stale=True
        self.entry={'name':'code','kind':'code','output':str(self.path),'refresh':'builtin:code'}
        self.write(False)
        self.get=patch.object(G,'_get',side_effect=lambda root,name:self.entry if name=='code' else None)
        self.status=patch.object(G,'status',side_effect=lambda *a,**kw:[{'name':'code','state':'stale' if self.stale else 'fresh'}])
        self.get.start();self.status.start();self.addCleanup(self.get.stop);self.addCleanup(self.status.stop)

    def write(self,found):
        self.path.write_text(json.dumps({'nodes':[{'id':'src/new.py::newfunc','label':'newfunc','type':'FUNC','path':'src/new.py','line':1}] if found else [],'edges':[]}),encoding='utf-8')

    def refreshed(self,*args,**kwargs):
        self.write(True);self.stale=False
        return {'started':True,'reason':'finished','exit':0,'summary':'re-parsed 1, reused 9','log':'synthetic.log'}

    def cli(self,name='code',flag=True):
        output=io.StringIO()
        args=['--root',str(self.root),'show',name,'newfunc']+(['--refresh-on-miss'] if flag else [])
        with contextlib.redirect_stdout(output):rc=G.main(args)
        return rc,output.getvalue()

    def test_stale_miss_refreshes_once_and_requeries_actual_graph(self):
        with patch.object(G,'refresh',side_effect=self.refreshed) as refresh:
            rc,out=self.cli()
        self.assertEqual(rc,0,out);refresh.assert_called_once()
        self.assertFalse(refresh.call_args.kwargs.get('background',True))
        self.assertFalse(refresh.call_args.kwargs.get('force',False))
        self.assertIn('src/new.py::newfunc',out)
        self.assertIn('re-parsed 1, reused 9',out)
        self.assertNotIn('No FUNC/FILE matching',out)

    def test_no_flag_keeps_old_abi_and_never_refreshes(self):
        with patch.object(G,'refresh') as refresh:
            rc,out=self.cli(flag=False)
        self.assertEqual(rc,0);refresh.assert_not_called()
        self.assertIn('No FUNC/FILE matching',out)

    def test_fresh_miss_never_refreshes_or_polls(self):
        self.stale=False
        with patch.object(G,'refresh') as refresh:
            rc,out=self.cli()
        self.assertEqual(rc,0);refresh.assert_not_called()
        self.assertIn("matching 'newfunc'",out)
        self.assertNotIn("newfunc --refresh-on-miss",out)

    def test_stale_hit_does_not_spawn_refresh(self):
        self.write(True)
        with patch.object(G,'refresh') as refresh:
            rc,out=self.cli()
        self.assertEqual(rc,0);refresh.assert_not_called()
        self.assertIn('src/new.py::newfunc',out)

    def test_busy_debounce_and_failure_remain_explicit_uncertainty(self):
        for value,word in [({'started':False,'reason':'already running'},'pending'),
                           ({'started':False,'reason':'debounced'},'pending'),
                           ({'started':True,'reason':'failed','exit':1},'failed')]:
            with self.subTest(reason=value['reason']),patch.object(G,'refresh',return_value=value) as refresh:
                rc,out=self.cli()
                refresh.assert_called_once();self.assertIn(word,out.lower())
                self.assertNotIn('No FUNC/FILE matching',out)

    def test_timeout_does_not_claim_absence_or_freshness(self):
        with patch.object(G,'refresh',side_effect=TimeoutError('untrusted details')) as refresh:
            rc,out=self.cli()
        refresh.assert_called_once();self.assertIn('failed',out.lower())
        self.assertNotIn('untrusted details',out);self.assertNotIn('No FUNC/FILE matching',out)

    def test_still_missing_after_success_retries_only_once(self):
        def unchanged(*a,**kw):
            self.stale=False
            return {'started':True,'reason':'finished','exit':0,'summary':'re-parsed 0, reused 10'}
        with patch.object(G,'refresh',side_effect=unchanged) as refresh:
            rc,out=self.cli()
        refresh.assert_called_once();self.assertIn("matching 'newfunc'",out)
        self.assertIn('re-parsed 0, reused 10',out)

    def test_flag_is_refused_for_other_graphs(self):
        with patch.object(G,'refresh') as refresh:
            rc,out=self.cli(name='db')
        self.assertNotEqual(rc,0);refresh.assert_not_called()
        self.assertIn('code',out.lower())


class GraphRefreshIntegration(unittest.TestCase):
    """Real status and refresh; a small actual generator is the process boundary."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='aidd-graph-integration-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'src').mkdir()
        self.source=self.root/'src'/'old.py';self.source.write_text('def old(): return 1\n',encoding='utf-8')
        self.output=self.root/'graph.json';self.output.write_text('{"nodes":[],"edges":[]}',encoding='utf-8')
        self.entry={'name':'code','kind':'code','output':str(self.output),'refresh':'builtin:code','watch':['src/**']}
        self.registry=patch.object(G,'load_registry',return_value=[self.entry]);self.registry.start();self.addCleanup(self.registry.stop)
        self.paths=G._paths(self.root,'code')
        for path in self.paths:
            path.parent.mkdir(parents=True,exist_ok=True);path.unlink(missing_ok=True)
        G._SHA_MEMO.clear();G._LS_MEMO.clear()
        self.addCleanup(self.clean)

    def clean(self):
        for path in self.paths:path.unlink(missing_ok=True)
        self.paths[1].with_suffix(self.paths[1].suffix+'.guard').unlink(missing_ok=True)
        G._SHA_MEMO.clear();G._LS_MEMO.clear()

    def command(self,body):
        script=self.root/'generator.py';script.write_text(body,encoding='utf-8')
        return patch.object(G,'_command',return_value=([sys.executable,str(script)],False))

    def test_edit_during_generation_cannot_look_fresh_from_old_hash_memo(self):
        # Prime the exact cache that the first status call fills, then change an existing input during the real child.
        self.assertEqual(G.status(self.root,names=['code'])[0]['state'],'stale')
        body='from pathlib import Path\n'+f'Path({str(self.source)!r}).write_text("def old(): return 2\\n",encoding="utf-8")\n'
        body+=f'Path({str(self.output)!r}).write_text(\'{{"nodes":[],"edges":[]}}\',encoding="utf-8")\nprint("re-parsed 1, reused 0")\n'
        with self.command(body):out=G.show(self.root,'code','not_present',refresh_on_miss=True)
        self.assertIn('pending',out.lower())
        self.assertNotIn('Query repeated once',out)
        self.assertNotIn('No FUNC/FILE matching',out)

    def test_added_input_during_generation_is_not_hidden_by_file_listing_memo(self):
        self.assertEqual(G.status(self.root,names=['code'])[0]['state'],'stale')
        added=self.root/'src'/'added.py'
        body='from pathlib import Path\n'+f'Path({str(added)!r}).write_text("def added(): return 1\\n",encoding="utf-8")\nprint("re-parsed 1, reused 1")\n'
        with self.command(body):out=G.show(self.root,'code','not_present',refresh_on_miss=True)
        self.assertIn('pending',out.lower())
        self.assertNotIn('Query repeated once',out)

    def test_foreground_refreshes_cannot_overlap_even_after_debounce_window(self):
        import threading
        entered=self.root/'entered';release=self.root/'release';runs=self.root/'runs'
        body='from pathlib import Path\nimport os,time\n'
        body+=f'with Path({str(runs)!r}).open("a",encoding="utf-8") as f:f.write(str(os.getpid())+"\\n")\n'
        body+=f'Path({str(entered)!r}).touch()\nend=time.monotonic()+5\n'
        body+=f'while not Path({str(release)!r}).exists() and time.monotonic()<end:time.sleep(.01)\nprint("re-parsed 0, reused 1")\n'
        first=[];second=[]
        with self.command(body):
            a=threading.Thread(target=lambda:first.append(G.refresh(self.root,'code',background=False,force=True)))
            b=threading.Thread(target=lambda:second.append(G.refresh(self.root,'code',background=False,force=True)))
            a.start()
            try:
                limit=time.monotonic()+2
                while not entered.exists() and time.monotonic()<limit:time.sleep(.01)
                self.assertTrue(entered.exists(),'first actual generator did not start')
                if self.paths[2].exists():os.utime(self.paths[2],(time.time()-120,time.time()-120))
                b.start();b.join(.3)
            finally:
                release.touch();a.join(6)
                if b.ident is not None:b.join(6)
        self.assertFalse(a.is_alive() or b.is_alive())
        self.assertEqual(len(runs.read_text(encoding='utf-8').splitlines()),1)
        self.assertTrue(first[0]['started']);self.assertFalse(second[0]['started'])
        self.assertEqual(second[0]['reason'],'already running')
        self.assertIsNone(G._lock_live(self.paths[1]))
