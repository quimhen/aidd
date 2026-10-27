#!/usr/bin/env python3
"""AIDD Semantic Component Graph (builtin:ui) — stdlib only, zero LLM tokens.

Builds a compact knowledge graph of reusable UI components (.aidd/graphs/ui.toon)
from design-system/components-index.md, specs/**/{mockup-audit,plan}.md, and UI source files.
Every component node carries its exact physical path on disk, pattern, props, slots,
and relationship edges (consumes / consumers).
"""
import argparse
import datetime
import os
import re
import sys
from pathlib import Path

DEFAULT_OUT = ".aidd/graphs/ui.toon"
DEFAULT_WATCH_GLOBS = [
    "design-system/components-index.md",
    "specs/**/mockup-audit.md",
    "specs/**/plan.md",
    "src/**/*.{tsx,jsx,dart,vue}",
    "lib/**/*.{dart,tsx,jsx}",
]

SHARED_DIR_KEYWORDS = ("shared", "components", "ui", "core", "widgets", "design-system", "common")


def normalize_rel_path(path_str, root):
    """Normalize a path to be relative to root with forward slashes."""
    try:
        p = Path(path_str)
        if p.is_absolute():
            p = p.relative_to(root)
        return str(p).replace("\\", "/")
    except Exception:
        return str(path_str).replace("\\", "/")


def is_shared_path(rel_path):
    """Check if a relative path lives in a recognized shared components directory."""
    clean = rel_path.lower().replace("\\", "/").strip("/")
    parts = clean.split("/")
    return any(keyword in parts for keyword in SHARED_DIR_KEYWORDS)


def extract_props_from_source(text, ext):
    """Extract prop names and slots from source code using light lexical regex."""
    props = []
    slots = []
    if not text:
        return props, slots

    if ext in (".tsx", ".ts", ".jsx", ".js"):
        # TypeScript interface/type Props
        m_props = re.search(r'(?:interface|type)\s+(?:\w*Props)\s*(?:=\s*)?\{([^}]+)\}', text, re.DOTALL)
        if m_props:
            body = m_props.group(1)
            for line in body.splitlines():
                line = line.strip()
                m_field = re.match(r'^([a-zA-Z0-9_$]+)\s*\??\s*:\s*([^;]+)', line)
                if m_field:
                    fname, ftype = m_field.group(1), m_field.group(2).strip().lower()
                    props.append(fname)
                    if fname in ("children", "child") or "reactnode" in ftype or "reactelement" in ftype or fname.endswith("Slot") or fname.endswith("slot"):
                        slots.append(fname)

        # Check for children or slots
        if ("children" in props or "children" in text) and "children" not in slots:
            slots.append("children")
        # Compound components (e.g., Card.Header = ..., static Header = ...)
        for m_comp in re.finditer(r'(?:static\s+([A-Z]\w+)|([A-Z]\w+)\.([A-Z]\w+)\s*=)', text):
            slot_name = m_comp.group(1) or m_comp.group(3)
            if slot_name and slot_name not in slots:
                slots.append(slot_name)

    elif ext == ".dart":
        # Dart constructor parameters
        m_ctor = re.search(r'(?:const\s+)?\w+\s*\(\{([^}]+)\}\)', text, re.DOTALL)
        if m_ctor:
            body = m_ctor.group(1)
            for line in body.splitlines():
                m_param = re.search(r'(?:this\.)([a-zA-Z0-9_$]+)', line)
                if m_param:
                    pname = m_param.group(1)
                    props.append(pname)
                    if pname in ("child", "children") or "widget" in line.lower():
                        slots.append(pname)
        if "child" in props and "child" not in slots:
            slots.append("child")
        if "children" in props and "children" not in slots:
            slots.append("children")

    elif ext == ".vue":
        # Vue defineProps
        m_vue = re.search(r'defineProps\s*<\s*\{([^}]+)\}\s*>', text, re.DOTALL)
        if m_vue:
            body = m_vue.group(1)
            for line in body.splitlines():
                m_field = re.match(r'^([a-zA-Z0-9_$]+)\s*\??\s*:', line.strip())
                if m_field:
                    props.append(m_field.group(1))
        if "<slot" in text:
            slots.append("default")

    return sorted(set(props)), sorted(set(slots))


def parse_components_index(index_path, root):
    """Parse design-system/components-index.md table rows."""
    components = {}
    if not index_path.is_file():
        return components

    try:
        text = index_path.read_text(encoding="utf-8")
    except Exception:
        return components

    lines = text.splitlines()
    in_table = False
    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.split("|")[1:-1]]
        if not cells:
            continue
        if "COMP-" in cells[0].upper():
            in_table = True
            continue
        if in_table:
            if all(set(c) <= {"-", ":", " "} for c in cells):
                continue
            code = cells[0].upper()
            if not re.match(r"^COMP-\d+", code):
                continue
            name = cells[1] if len(cells) > 1 else code
            file_col = cells[2] if len(cells) > 2 else ""
            used_in = cells[4] if len(cells) > 4 else ""
            consumers_col = cells[5] if len(cells) > 5 else ""

            rel_file = normalize_rel_path(file_col, root)
            consumers = set()
            for token in re.findall(r"\bSCREEN-\d+\b", used_in):
                consumers.add(token.upper())
            for token in [t.strip() for t in consumers_col.split(",") if t.strip()]:
                consumers.add(token)

            components[code] = {
                "id": code,
                "name": name,
                "path": rel_file,
                "pattern": "Compound" if "compound" in (file_col + " " + used_in).lower() else "Atomic",
                "props": [],
                "slots": [],
                "consumes": [],
                "consumers": sorted(consumers),
            }

    return components


def parse_spec_components(spec_dir, root, components):
    """Enrich components dict with definitions from a spec folder."""
    # Read mockup-audit.md
    ma_path = spec_dir / "mockup-audit.md"
    if ma_path.is_file():
        try:
            text = ma_path.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines():
                if not line.strip().startswith("|"):
                    continue
                cells = [c.strip() for c in line.strip().split("|")[1:-1]]
                if cells and re.match(r"^COMP-\d+", cells[0].upper()):
                    code = cells[0].upper()
                    name = cells[1] if len(cells) > 1 else code
                    used_in = cells[2] if len(cells) > 2 else ""
                    pat_cell = cells[5] if len(cells) > 5 else ""
                    pattern = "Compound" if "compound" in pat_cell.lower() else "Atomic"
                    
                    if code not in components:
                        components[code] = {
                            "id": code,
                            "name": name,
                            "path": "",
                            "pattern": pattern,
                            "props": [],
                            "slots": [],
                            "consumes": [],
                            "consumers": [],
                        }
                    for token in re.findall(r"\bSCREEN-\d+\b", used_in):
                        if token.upper() not in components[code]["consumers"]:
                            components[code]["consumers"].append(token.upper())
        except Exception:
            pass

    # Read plan.md
    plan_path = spec_dir / "plan.md"
    if plan_path.is_file():
        try:
            text = plan_path.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines():
                if not line.strip().startswith("|"):
                    continue
                cells = [c.strip() for c in line.strip().split("|")[1:-1]]
                if cells and re.match(r"^COMP-\d+", cells[0].upper()):
                    code = cells[0].upper()
                    file_col = cells[1] if len(cells) > 1 else ""
                    pat_col = cells[2] if len(cells) > 2 else ""
                    used_col = cells[3] if len(cells) > 3 else ""

                    if code in components:
                        if file_col and not components[code]["path"]:
                            components[code]["path"] = normalize_rel_path(file_col, root)
                        if "compound" in pat_col.lower():
                            components[code]["pattern"] = "Compound"
                        for token in re.findall(r"\bSCREEN-\d+\b", used_col):
                            if token.upper() not in components[code]["consumers"]:
                                components[code]["consumers"].append(token.upper())
                    else:
                        components[code] = {
                            "id": code,
                            "name": Path(file_col).stem if file_col else code,
                            "path": normalize_rel_path(file_col, root),
                            "pattern": "Compound" if "compound" in pat_col.lower() else "Atomic",
                            "props": [],
                            "slots": [],
                            "consumes": [],
                            "consumers": [t.upper() for t in re.findall(r"\bSCREEN-\d+\b", used_col)],
                        }
        except Exception:
            pass


def build_component_graph(root_dir=None):
    """Build the component graph dictionary."""
    root = Path(root_dir or ".").resolve()
    components = {}

    # 1. Parse components-index.md if present
    candidates = [
        root / "design-system" / "components-index.md",
        root / "specs" / "design-system" / "components-index.md",
        root / "skill" / "templates" / "design-system" / "components-index.md",
    ]
    for c in candidates:
        if c.is_file():
            components.update(parse_components_index(c, root))
            if components:
                break

    # 2. Parse specs/**
    specs_root = root / "specs"
    if specs_root.is_dir():
        for spec_dir in sorted(specs_root.iterdir()):
            if spec_dir.is_dir():
                parse_spec_components(spec_dir, root, components)

    # 3. Enrich from physical files
    for comp_id, data in components.items():
        if data["path"]:
            phys_file = root / data["path"]
            if phys_file.is_file():
                try:
                    src_text = phys_file.read_text(encoding="utf-8", errors="ignore")
                    props, slots = extract_props_from_source(src_text, phys_file.suffix)
                    if props:
                        data["props"] = props
                    if slots:
                        data["slots"] = slots
                        if len(slots) > 1:
                            data["pattern"] = "Compound"
                except Exception:
                    pass

    return components


def serialize_toon(components, root=None):
    """Serialize components dict into AIDD-TOON format."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    count = len(components)
    lines = [
        "version: 1",
        f"generated: {now_iso}",
        f"components[{count}]{{id,name,path,pattern,props,slots,consumes,consumers}}:",
    ]

    for comp_id in sorted(components.keys()):
        c = components[comp_id]
        cid = c.get("id", "")
        name = c.get("name", "")
        path = c.get("path", "")
        pat = c.get("pattern", "Atomic")
        props_str = "|".join(c.get("props", []))
        slots_str = "|".join(c.get("slots", []))
        consumes_str = "|".join(c.get("consumes", []))
        consumers_str = "|".join(c.get("consumers", []))

        # Format TOON row
        row = f"  {cid},{name},{path},{pat},{props_str},{slots_str},{consumes_str},{consumers_str}"
        lines.append(row)

    return "\n".join(lines) + "\n"


def parse_toon(text):
    """Parse a ui.toon text into a component dict."""
    components = {}
    lines = text.splitlines()
    for line in lines:
        if not line.startswith("  "):
            continue
        parts = line.strip().split(",")
        if len(parts) >= 8:
            cid, name, path, pat, props_str, slots_str, consumes_str, consumers_str = parts[:8]
            components[cid] = {
                "id": cid,
                "name": name,
                "path": path,
                "pattern": pat,
                "props": props_str.split("|") if props_str else [],
                "slots": slots_str.split("|") if slots_str else [],
                "consumes": consumes_str.split("|") if consumes_str else [],
                "consumers": consumers_str.split("|") if consumers_str else [],
            }
    return components


deserialize_toon = parse_toon


def format_subgraph_prompt(comp_dict, query_id):
    """Format a 10-15 line micro-context prompt snippet for subagent injection."""
    q = query_id.upper()
    lines = [f"# Shared-First Component Context for {q}:"]

    matched = []
    if q.startswith("SCREEN-"):
        # Match components consumed by this screen
        for cid, data in comp_dict.items():
            if any(q == cons or q in cons for cons in data.get("consumers", [])):
                matched.append(data)
    else:
        # Match single component by id or name
        for cid, data in comp_dict.items():
            if cid == q or data.get("name", "").upper() == q or q in cid:
                matched.append(data)

    if not matched:
        lines.append(f"  note: No registered component matches '{query_id}'. Check design-system/components-index.md.")
        return "\n".join(lines)

    for c in matched:
        lines.append(f"  - {c['id']} ({c['name']}):")
        lines.append(f"      path: {c['path']}")
        lines.append(f"      pattern: {c['pattern']}")
        if c.get("props"):
            lines.append(f"      props: [{', '.join(c['props'][:6])}]")
        if c.get("slots"):
            lines.append(f"      slots: [{', '.join(c['slots'][:4])}]")
        if c.get("consumers"):
            lines.append(f"      used_by: [{', '.join(c['consumers'][:4])}]")

    lines.append("  rule: Do NOT recreate these components or edit them inline; import them from their exact path.")
    return "\n".join(lines)


def show_ui(root, query, limit=25, graph_path=None, stale=""):
    """Query UI component graph for aidd_graphs show ui <query> or aidd component show/search."""
    root = Path(root).resolve()
    comps = None
    if graph_path and Path(graph_path).is_file():
        try:
            comps = deserialize_toon(Path(graph_path).read_text(encoding="utf-8", errors="replace"))
        except Exception:
            comps = None
    if not comps:
        comps = build_component_graph(root)

    q = str(query).strip().lower()
    matches = []
    for cid, data in comps.items():
        score = 9
        cid_l = cid.lower()
        name_l = data.get("name", "").lower()
        path_l = data.get("path", "").lower()
        if q == cid_l or q == name_l:
            score = 0
        elif q in cid_l or q in name_l:
            score = 1
        elif q in path_l or any(q in c.lower() for c in data.get("consumers", [])):
            score = 2
        if score < 9:
            matches.append((score, cid, data))

    matches.sort(key=lambda item: (item[0], item[1]))

    if not matches:
        tail = f" {stale}" if stale else ""
        return f"No UI component matching '{query}' found.{tail}"

    lines = [stale] if stale else []
    for _, cid, c in matches[:10]:
        lines.append(f"{cid} ({c['name']}) [{c['pattern']}]")
        lines.append(f"  path: {c['path']}")
        if c.get("props"):
            lines.append(f"  props: {', '.join(c['props'])}")
        if c.get("slots"):
            lines.append(f"  slots: {', '.join(c['slots'])}")
        if c.get("consumers"):
            lines.append(f"  used_by: {', '.join(c['consumers'])}")
        if c.get("source_spec"):
            lines.append(f"  source_spec: {c['source_spec']}")

    if len(lines) > limit:
        lines = lines[:limit - 1] + [f"... +{len(lines) - limit + 1} more"]
    return "\n".join(lines)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(prog="component_graph.py", description="AIDD UI Component Graph generator.")
    parser.add_argument("--root", default=".", help="project root directory")
    parser.add_argument("--out", default=DEFAULT_OUT, help="output TOON file path")
    parser.add_argument("--build", action="store_true", help="build and write graph to --out")
    parser.add_argument("--query", help="query component graph by id/name")
    parser.add_argument("--inject", help="generate micro-context prompt snippet for COMP-nnn or SCREEN-XX")
    parser.add_argument("--limit", type=int, default=25, help="max lines to print")

    # Handle subcommands: search, show, inject, build
    if argv and argv[0] in ("search", "show", "inject", "build"):
        cmd = argv[0]
        rest = argv[1:]
        if cmd == "build":
            argv = ["--build"] + rest
        elif cmd == "inject" and rest:
            argv = ["--inject", rest[0]] + rest[1:]
        elif cmd in ("search", "show") and rest:
            argv = ["--query", rest[0]] + rest[1:]

    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    if args.inject:
        comps = build_component_graph(root)
        print(format_subgraph_prompt(comps, args.inject))
        return 0

    if args.query:
        out_file = root / args.out
        graph_p = out_file if out_file.is_file() else None
        print(show_ui(root, args.query, limit=args.limit, graph_path=graph_p))
        return 0

    # Build and write TOON
    comps = build_component_graph(root)
    out_path = root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    toon_content = serialize_toon(comps, root)
    out_path.write_text(toon_content, encoding="utf-8")
    print(f"Wrote {len(comps)} components to {out_path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
