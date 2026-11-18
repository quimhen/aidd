"""Real status/active-lock regression for opt-in graph misses; no generator runs."""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill" / "scripts"))
import aidd_graphs as G


@pytest.mark.parametrize("opt_in, hit", [(True, False), (False, False), (True, True), (False, True)])
def test_show_observes_real_running_lock_without_duplicate_refresh(tmp_path, opt_in, hit):
    output = tmp_path / "graph.json"
    nodes = [{"id": "src/new.py::needle", "label": "needle", "type": "FUNC", "path": "src/new.py", "line": 1}] if hit else []
    output.write_text(json.dumps({"nodes": nodes, "edges": []}), encoding="utf-8")
    entry = {"name": "code", "kind": "code", "output": str(output), "refresh": "builtin:code", "watch": []}
    _, lock, _ = G._paths(tmp_path, "code")
    lock.parent.mkdir(parents=True, exist_ok=True)
    guard = G._refresh_guard(lock)
    assert guard is not None
    lock.write_text(str(os.getpid()), encoding="utf-8")
    try:
        # status(), _lock_live(), PID liveness and graph lookup remain real. Input hashing
        # is irrelevant to a live lock and is stubbed solely to avoid external Git work.
        with patch.object(G, "load_registry", return_value=[entry]), patch.object(G, "_inputs_hashes", return_value={}), patch.object(G, "refresh") as refresh:
            assert G.status(tmp_path, names=["code"])[0]["state"] == "running"
            result = G.show(tmp_path, "code", "needle", refresh_on_miss=opt_in)
        refresh.assert_not_called()
        if hit:
            assert "src/new.py::needle" in result
            assert "Graph refresh pending" not in result
        elif opt_in:
            assert "Graph refresh pending" in result
            assert "not confirmed fresh" in result
            assert "No FUNC/FILE matching" not in result
        else:
            assert result.startswith("No FUNC/FILE matching")
            assert "Graph refresh pending" not in result
    finally:
        lock.unlink(missing_ok=True)
        guard.close()
