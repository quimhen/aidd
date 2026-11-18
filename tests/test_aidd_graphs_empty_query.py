"""Narrow CLI empty-query regression; show/refresh are mocked, no graph work."""
import sys
from pathlib import Path
from unittest.mock import patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill" / "scripts"))
import aidd_graphs as G


@pytest.mark.parametrize("rest", [
    ["code", "--refresh-on-miss"],
    ["code", "", "--refresh-on-miss"],
    ["code", "   ", "--refresh-on-miss"],
    ["code", "--refresh-on-miss", "--limit", "5"],
    ["code", "--limit", "5"],
    ["code", "", "--limit", "5"],
    ["code", ""],
    ["code"],
])
def test_empty_query_returns_usage_without_show_or_refresh(tmp_path, rest):
    with patch.object(G, "show") as show, patch.object(G, "refresh") as refresh:
        assert G.main(["--root", str(tmp_path), "show", *rest]) == 2
    show.assert_not_called()
    refresh.assert_not_called()


@pytest.mark.parametrize("rest, expected", [
    (["code", "needle"], ("code", "needle", 25, {})),
    (["code", "needle", "--refresh-on-miss"],
     ("code", "needle", 25, {"refresh_on_miss": True})),
    (["code", "needle", "--refresh-on-miss", "--limit", "7"],
     ("code", "needle", 7, {"refresh_on_miss": True})),
    (["code", "qualified", "name", "--limit", "7"],
     ("code", "qualified name", 7, {})),
])
def test_valid_query_preserves_show_dispatch(tmp_path, rest, expected):
    name, query, limit, kwargs = expected
    with patch.object(G, "show", return_value="mocked graph result") as show, patch.object(G, "refresh") as refresh:
        assert G.main(["--root", str(tmp_path), "show", *rest]) == 0
    show.assert_called_once_with(tmp_path, name, query, limit, **kwargs)
    refresh.assert_not_called()
