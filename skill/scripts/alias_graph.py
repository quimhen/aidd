"""The alias reader and graph converter module (spec 007 amendment 06, task T-36).
FR-252, FR-254. Reads .aidd/graphs/path-aliases.toon.
"""
import re
from pathlib import Path

SECTION_RE = re.compile(r'^aliases\[(\d+)\]\{old,new,scope,reason\}:\s*$')
ALIAS_REL_PATH = Path(".aidd") / "graphs" / "path-aliases.toon"
MISSING_MSG = "Graph 'aliases' is missing; the project must generate .aidd/graphs/path-aliases.toon"


def is_alias_toon(text):
    """True when any line matches SECTION_RE."""
    try:
        for line in str(text).splitlines():
            if SECTION_RE.match(line.strip()):
                return True
        return False
    except Exception:
        return False


def parse_aliases(text):
    """Parse alias lines from TOON text.
    Ignore lines not starting with two spaces; split on ',' maxsplit 3;
    keep rows with at least 2 non-empty fields; base names only; scope and reason default to ''.
    """
    rows = []
    try:
        for line in str(text).splitlines():
            if not line.startswith("  "):
                continue
            content = line[2:]
            parts = [p.strip() for p in content.split(",", 3)]
            if len(parts) < 2:
                continue
            old, new = parts[0], parts[1]
            if not old or not new:
                continue
            if any(c in old + new for c in ("/", "\\", "\x00")) or ".." in old or ".." in new or old in (".", "..") or new in (".", ".."):
                continue
            scope = parts[2] if len(parts) > 2 else ""
            reason = parts[3] if len(parts) > 3 else ""
            rows.append({
                "old": old,
                "new": new,
                "scope": scope,
                "reason": reason,
            })
    except Exception:
        return []
    return rows


def load_aliases(path):
    """Load aliases from file at path. Fail closed: any error returns []."""
    try:
        p = Path(path)
        if not p.is_file():
            return []
        text = p.read_text(encoding="utf-8")
        if not is_alias_toon(text):
            return []
        return parse_aliases(text)
    except (OSError, UnicodeDecodeError, ValueError):
        return []
    except Exception:
        return []


def to_graph(rows):
    """Convert alias rows to graph dict {"nodes": [...], "edges": [...]}.
    Node: {"id": "old:<base>"|"new:<base>", "label": <base>, "type": "alias_old"|"alias_new", "scope", "reason"}.
    Edge: {"source": <old id>, "target": <new id>, "type": "RENAMED_TO"}.
    Edges de-duplicated by (source, target); node ids unique.
    """
    nodes = []
    edges = []
    seen_nodes = set()
    seen_edges = set()

    for r in rows:
        old = r.get("old", "")
        new = r.get("new", "")
        if not old or not new:
            continue
        old_id = "old:" + old
        new_id = "new:" + new

        if old_id not in seen_nodes:
            seen_nodes.add(old_id)
            nodes.append({
                "id": old_id,
                "label": old,
                "type": "alias_old",
                "scope": r.get("scope", ""),
                "reason": r.get("reason", ""),
            })

        if new_id not in seen_nodes:
            seen_nodes.add(new_id)
            nodes.append({
                "id": new_id,
                "label": new,
                "type": "alias_new",
                "scope": r.get("scope", ""),
                "reason": r.get("reason", ""),
            })

        edge_key = (old_id, new_id)
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            edges.append({
                "source": old_id,
                "target": new_id,
                "type": "RENAMED_TO",
            })

    return {"nodes": nodes, "edges": edges}


def show_aliases(root, query, limit=25):
    """Show alias rows matching query for graph at <root>/.aidd/graphs/path-aliases.toon.
    Returns at most limit lines. Fail closed: never raises.
    """
    try:
        p = Path(root) / ALIAS_REL_PATH
        if not p.is_file():
            return MISSING_MSG
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, ValueError):
            return MISSING_MSG
        if not is_alias_toon(text):
            return MISSING_MSG

        rows = parse_aliases(text)
        q = str(query).lower()
        matched = [r for r in rows if q in r["old"].lower() or q in r["new"].lower()]
        if not matched:
            return "No alias matching '%s'." % query

        lines = []
        for r in matched[:limit]:
            line = "%s -> %s" % (r["old"], r["new"])
            if r.get("scope"):
                line += " [%s]" % r["scope"]
            if r.get("reason"):
                line += " %s" % r["reason"]
            lines.append(line)
        return "\n".join(lines)
    except Exception:
        return MISSING_MSG
