"""docs/db-graph/unified_graph_model.py
Modelo relacional unificado y cargador de los 4 grafos del monorepositorio:
- BD (PostgreSQL): docs/db-graph/graph.json
- AST (Código Python): .aidd/graphs/code.json
- Specs (Requerimientos AIDD): specs/index.toon
- UI (Componentes React): .aidd/graphs/ui.toon
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class UnifiedGraphModel:
    """Gestiona la carga, unificación, filtrado y cálculo de vecindario

    sobre la red multidominio de b1SycLink.
    """

    def __init__(self, root: Optional[Path] = None):
        if root is None:
            self.root = Path(__file__).resolve().parent.parent.parent
        else:
            self.root = Path(root).resolve()

        self.db_graph_path = self.root / "docs" / "db-graph" / "graph.json"
        self.code_graph_path = self.root / ".aidd" / "graphs" / "code.json"
        self.spec_graph_path = self.root / "specs" / "index.toon"
        self.ui_graph_path = self.root / ".aidd" / "graphs" / "ui.toon"

    def load(self) -> Dict[str, Any]:
        """Carga y fusiona los 4 grafos del repositorio."""
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []

        # 1. Cargar Grafo de Base de Datos
        if self.db_graph_path.exists():
            try:
                db_data = json.loads(self.db_graph_path.read_text(encoding="utf-8"))
                for n in db_data.get("nodes", []):
                    nid = f"db:{n['id']}" if not n["id"].startswith("db:") else n["id"]
                    domain = n.get("domain") or self._infer_domain(n.get("label", ""))
                    nodes[nid] = {
                        "id": nid,
                        "raw_id": n["id"],
                        "label": n.get("label", n["id"]),
                        "layer": "db",
                        "type": n.get("type", "table"),
                        "origin": n.get("origin", "web"),
                        "domain": domain,
                        "purpose": n.get("purpose", ""),
                        "purpose_source": n.get("purpose_source", ""),
                        "metadata": {k: v for k, v in n.items() if k not in ("id", "label", "type", "purpose")},
                    }
                for e in db_data.get("edges", []):
                    src = f"db:{e['source']}" if not e["source"].startswith("db:") else e["source"]
                    tgt = f"db:{e['target']}" if not e["target"].startswith("db:") else e["target"]
                    edges.append({
                        "source": src,
                        "target": tgt,
                        "relation": e.get("relation", "rel"),
                        "layer": "db",
                        "cross_layer": False,
                    })
            except Exception as ex:
                print(f"Warning: error reading {self.db_graph_path}: {ex}")

        # 1.2 Cargar Esquema de Nómina (Payroll/supabase/migrations)
        pr_migrations = self.root / "Payroll" / "supabase" / "migrations"
        if pr_migrations.is_dir():
            try:
                for sql_file in sorted(pr_migrations.glob("*.sql")):
                    content = sql_file.read_text(encoding="utf-8", errors="ignore")
                    # Tablas de Nómina
                    for m in re.finditer(r'create\s+table\s+(?:if\s+not\s+exists\s+)?(?:public\.)?\"([A-Za-z0-9_]+)\"', content, re.I):
                        tname = m.group(1).upper()
                        nid = f"db:payroll:table:{tname}"
                        if nid not in nodes:
                            nodes[nid] = {
                                "id": nid,
                                "raw_id": tname,
                                "label": tname,
                                "layer": "db",
                                "type": "table",
                                "origin": "payroll",
                                "domain": "Nomina",
                                "purpose": f"Tabla de Nómina: {tname}",
                                "purpose_source": sql_file.name,
                                "metadata": {"schema": "public", "table": tname, "source_file": sql_file.name},
                            }
                    # Funciones de Nómina
                    for m in re.finditer(r'create\s+(?:or\s+replace\s+)?function\s+(?:public\.)?(pr_[a-zA-Z0-9_]+)', content, re.I):
                        fname = m.group(1).lower()
                        nid = f"db:payroll:function:{fname}"
                        if nid not in nodes:
                            nodes[nid] = {
                                "id": nid,
                                "raw_id": fname,
                                "label": fname,
                                "layer": "db",
                                "type": "function",
                                "origin": "payroll",
                                "domain": "Nomina",
                                "purpose": f"Función PL/pgSQL de Nómina: {fname}",
                                "purpose_source": sql_file.name,
                                "metadata": {"schema": "public", "function": fname, "source_file": sql_file.name},
                            }
            except Exception as ex:
                print(f"Warning: error reading Payroll migrations: {ex}")

        # 2. Cargar Grafo de Código AST
        if self.code_graph_path.exists():
            try:
                code_data = json.loads(self.code_graph_path.read_text(encoding="utf-8"))
                for n in code_data.get("nodes", []):
                    nid = f"code:{n['id']}"
                    domain = self._infer_domain(n.get("source_file", n["id"]))
                    nodes[nid] = {
                        "id": nid,
                        "raw_id": n["id"],
                        "label": n.get("label", n["id"]),
                        "layer": "code",
                        "type": n.get("type", "FILE"),
                        "origin": "repo",
                        "domain": domain,
                        "purpose": f"Módulo AST: {n.get('source_location', n['id'])}",
                        "purpose_source": "ast",
                        "metadata": {
                            "source_file": n.get("source_file", ""),
                            "source_location": n.get("source_location", ""),
                            "lineno": n.get("lineno"),
                        },
                    }
                for e in code_data.get("edges", []):
                    src = f"code:{e['source']}"
                    tgt = f"code:{e['target']}"
                    edges.append({
                        "source": src,
                        "target": tgt,
                        "relation": e.get("relation", "calls"),
                        "layer": "code",
                        "cross_layer": False,
                    })
            except Exception as ex:
                print(f"Warning: error reading {self.code_graph_path}: {ex}")

        # 3. Cargar Grafo de Especificaciones AIDD
        if self.spec_graph_path.exists():
            try:
                self._load_specs_toon(nodes, edges)
            except Exception as ex:
                print(f"Warning: error reading {self.spec_graph_path}: {ex}")

        # 4. Cargar Grafo de Componentes UI
        if self.ui_graph_path.exists():
            try:
                self._load_ui_toon(nodes, edges)
            except Exception as ex:
                print(f"Warning: error reading {self.ui_graph_path}: {ex}")

        # 5. Descubrir aristas de Trazabilidad Cruzada (Cross-Layer Links)
        self._link_cross_layers(nodes, edges)

        return {
            "summary": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "by_layer": {
                    "db": sum(1 for n in nodes.values() if n["layer"] == "db"),
                    "code": sum(1 for n in nodes.values() if n["layer"] == "code"),
                    "spec": sum(1 for n in nodes.values() if n["layer"] == "spec"),
                    "ui": sum(1 for n in nodes.values() if n["layer"] == "ui"),
                },
            },
            "nodes": list(nodes.values()),
            "edges": edges,
        }

    def _infer_domain(self, text: str) -> str:
        s = text.strip()
        # 1. Chequeo por prefijo formal de Spec
        m = re.match(r"^(P\d{2}|S\d{2}|F\d{2})", s)
        if m:
            pfx = m.group(1).upper()
            if pfx.startswith("P"):
                return "Nomina"
            if pfx.startswith("S"):
                return "Seleccion"
            if pfx in ("F06", "F09", "F55"):
                return "Sync Mobile"
            if pfx in ("F12", "F13", "F14", "F15", "F16", "F17", "F18", "F19", "F20",
                      "F21", "F22", "F23", "F24", "F25", "F26", "F36", "F37", "F38",
                      "F39", "F40", "F41", "F42", "F43", "F54"):
                return "eDoc"
            return "Core"

        # 2. Chequeo por ruta de archivo o identificador
        t = s.lower()
        if "payroll" in t or "payrol" in t or "nomina" in t or "nómina" in t or "pr_" in t or "py_" in t:
            return "Nomina"
        if "select" in t or "reclut" in t or "selección" in t or "sl_" in t:
            return "Seleccion"
        if "mobile" in t or "drift" in t or "returns" in t or "tracking" in t:
            return "Sync Mobile"
        if "edoc" in t or "factur" in t or "sri" in t or "fe_" in t or "pur_" in t or "imc_" in t:
            return "eDoc"
        return "Core"

    def _load_specs_toon(self, nodes: Dict[str, Dict[str, Any]], edges: List[Dict[str, Any]]) -> None:
        raw = self.spec_graph_path.read_text(encoding="utf-8")
        in_specs = False
        for line in raw.splitlines():
            line_str = line.strip()
            if line_str.startswith("specs["):
                in_specs = True
                continue
            if not in_specs or not line_str or line_str.startswith("#"):
                continue

            parts = [p.strip() for p in line.split(",", 6)]
            if len(parts) < 2:
                continue

            spec_id = parts[0]
            title = parts[1]
            codes_str = parts[2] if len(parts) > 2 else ""
            graph_str = parts[5] if len(parts) > 5 else ""

            nid = f"spec:{spec_id}"
            domain = self._infer_domain(spec_id)
            nodes[nid] = {
                "id": nid,
                "raw_id": spec_id,
                "label": spec_id,
                "layer": "spec",
                "type": "spec",
                "origin": "aidd",
                "domain": domain,
                "purpose": title,
                "purpose_source": "spec.md",
                "metadata": {"title": title, "codes": [c for c in codes_str.split("|") if c]},
            }

            # Parse inner relations from graph column (e.g. E:SRC:TGT:REL)
            if graph_str:
                for rel_token in graph_str.split(";"):
                    token = rel_token.strip()
                    if token.startswith("E:"):
                        rp = token[2:].split(":")
                        if len(rp) >= 3:
                            src_id = f"spec:{rp[0]}"
                            tgt_id = f"spec:{rp[1]}"
                            rel_name = rp[2]
                            edges.append({
                                "source": src_id,
                                "target": tgt_id,
                                "relation": rel_name,
                                "layer": "spec",
                                "cross_layer": False,
                            })

    def _load_ui_toon(self, nodes: Dict[str, Dict[str, Any]], edges: List[Dict[str, Any]]) -> None:
        raw = self.ui_graph_path.read_text(encoding="utf-8")
        in_comp = False
        for line in raw.splitlines():
            line_str = line.strip()
            if line_str.startswith("components["):
                in_comp = True
                continue
            if not in_comp or not line_str or line_str.startswith("#"):
                continue

            parts = [p.strip() for p in line.split(",", 7)]
            if len(parts) < 3:
                continue

            cid = parts[0]
            name = parts[1]
            path = parts[2]
            consumers = parts[7] if len(parts) > 7 else ""

            nid = f"ui:{cid}"
            domain = self._infer_domain(path)
            nodes[nid] = {
                "id": nid,
                "raw_id": cid,
                "label": name or cid,
                "layer": "ui",
                "type": "component",
                "origin": "frontend",
                "domain": domain,
                "purpose": f"Componente UI en {path}",
                "purpose_source": "ui.toon",
                "metadata": {"path": path, "consumers": [s for s in consumers.split("|") if s]},
            }

            if consumers:
                for sc in consumers.split("|"):
                    sc = sc.strip()
                    if sc:
                        sc_id = f"spec:{sc}"
                        edges.append({
                            "source": nid,
                            "target": sc_id,
                            "relation": "consumido_por",
                            "layer": "ui",
                            "cross_layer": True,
                        })

    def _link_cross_layers(self, nodes: Dict[str, Dict[str, Any]], edges: List[Dict[str, Any]]) -> None:
        """Crea aristas cruzadas entre Specs, Código, UI y BD basándose en documentos, nombres y referencias."""
        # Indexar tablas DB por label y por id
        db_by_name = {}
        for n in nodes.values():
            if n["layer"] == "db":
                db_by_name[n["label"].lower()] = n["id"]
                raw = n["id"].split(":")[-1].lower()
                db_by_name[raw] = n["id"]

        # Indexar UI components
        ui_by_id = {n["raw_id"].upper(): n["id"] for n in nodes.values() if n["layer"] == "ui"}

        # Indexar Specs por prefijo (F01, F06, F47, etc.) y por ID completo
        specs_by_prefix = {}
        for n in nodes.values():
            if n["layer"] == "spec":
                pfx = n["raw_id"].split("-")[0].upper()
                specs_by_prefix[pfx] = n["id"]

        # Indexar Código AST por ruta/nombre
        code_by_path = {n["label"].lower(): n["id"] for n in nodes.values() if n["layer"] == "code"}

        specs_dir = self.root / "specs"

        # Conectar Specs con Tablas, Componentes UI, Código y Otras Specs
        for nid, node in list(nodes.items()):
            if node["layer"] == "spec":
                spec_name = node["raw_id"]
                spec_folder = specs_dir / spec_name
                text_corpus = node.get("purpose", "") + " " + node["label"]

                # Leer documentos de la spec si existe la carpeta física
                if spec_folder.is_dir():
                    for fn in ("plan.md", "spec.md", "tasks.md", "data-model.md"):
                        doc_file = spec_folder / fn
                        if doc_file.exists():
                            try:
                                text_corpus += " " + doc_file.read_text(encoding="utf-8", errors="ignore")
                            except Exception:
                                pass

                # 1. Conectar con Tablas BD (respetando afinidad de dominio de negocio)
                matched_tables = set()
                spec_domain = node["domain"]
                allowed_domains = {spec_domain, "Core"}
                if spec_domain == "Sync Mobile":
                    allowed_domains.update(["documentos", "productos_precios", "sync_integracion"])

                for w in re.findall(r"\b[A-Za-z0-9_]{3,15}\b", text_corpus):
                    lw = w.lower()
                    if lw in db_by_name and db_by_name[lw] != nid:
                        tbl_node = nodes.get(db_by_name[lw])
                        if tbl_node and tbl_node.get("domain") in allowed_domains:
                            matched_tables.add(db_by_name[lw])

                for tbl_id in matched_tables:
                    edges.append({
                        "source": nid,
                        "target": tbl_id,
                        "relation": "impacta_tabla",
                        "layer": "cross",
                        "cross_layer": True,
                    })

                # 2. Conectar con Componentes UI
                matched_comps = set()
                for comp_code in re.findall(r"\bCOMP-\d+\b", text_corpus):
                    cc_up = comp_code.upper()
                    if cc_up in ui_by_id:
                        matched_comps.add(ui_by_id[cc_up])
                for cid in matched_comps:
                    edges.append({
                        "source": nid,
                        "target": cid,
                        "relation": "contiene_componente",
                        "layer": "cross",
                        "cross_layer": True,
                    })

                # 3. Conectar con Otras Specs citadas (SOLO dependencias explícitas arquitectónicas)
                matched_specs = set()
                dep_matches = re.findall(r"(?:depends\s+on|amends|enmienda\s+de|replaces|parent|requiere\s+a)\s*[:\s]+.*?\b([FPS]\d{2})\b", text_corpus, re.I)
                for sp_code in dep_matches:
                    sp_up = sp_code.upper()
                    if sp_up in specs_by_prefix and specs_by_prefix[sp_up] != nid:
                        rel_spec_node = nodes.get(specs_by_prefix[sp_up])
                        # Evitar vincular specs de dominios no relacionados (e.g. Nomina con Facturacion)
                        if rel_spec_node and (rel_spec_node["domain"] == spec_domain or rel_spec_node["domain"] == "Core" or spec_domain == "Core"):
                            matched_specs.add(specs_by_prefix[sp_up])

                for rel_spec_id in matched_specs:
                    edges.append({
                        "source": nid,
                        "target": rel_spec_id,
                        "relation": "relacionado_con",
                        "layer": "cross",
                        "cross_layer": True,
                    })

                # 4. Extraer archivos de código mencionados (e.g. mobile/lib/..., eDoc/...)
                file_paths = re.findall(r"[\w/\.-]+\.(?:dart|py|tsx|ts|js)", text_corpus)
                for fp in set(file_paths):
                    norm_fp = fp.lstrip("./").strip("`'\"")
                    if norm_fp in code_by_path:
                        edges.append({
                            "source": nid,
                            "target": code_by_path[norm_fp],
                            "relation": "modifica_codigo",
                            "layer": "cross",
                            "cross_layer": True,
                        })
                    else:
                        full_p = self.root / norm_fp
                        full_mob = self.root / "mobile" / norm_fp
                        if full_p.exists() or full_mob.exists():
                            actual_path = norm_fp if full_p.exists() else f"mobile/{norm_fp}"
                            cid = f"code:{actual_path}"
                            if cid not in nodes:
                                nodes[cid] = {
                                    "id": cid,
                                    "raw_id": actual_path,
                                    "label": Path(actual_path).name,
                                    "layer": "code",
                                    "type": "FILE",
                                    "origin": "repo",
                                    "domain": self._infer_domain(actual_path),
                                    "purpose": f"Archivo de código: {actual_path}",
                                    "purpose_source": "spec_reference",
                                    "metadata": {"path": actual_path},
                                }
                            edges.append({
                                "source": nid,
                                "target": cid,
                                "relation": "modifica_codigo",
                                "layer": "cross",
                                "cross_layer": True,
                            })

    @staticmethod
    def compute_neighborhood(graph: Dict[str, Any], focal_node_id: str, hop_radius: int = 2) -> Dict[str, Any]:
        """Calcula el subgrafo dentro del radio de saltos desde el nodo focal."""
        nodes_by_id = {n["id"]: n for n in graph.get("nodes", [])}
        if focal_node_id not in nodes_by_id:
            # Intentar resolver con prefijo
            matches = [nid for nid in nodes_by_id if nid.endswith(focal_node_id) or focal_node_id in nid]
            if matches:
                focal_node_id = matches[0]
            else:
                return {"nodes": [], "edges": [], "focal_node": None}

        # Construir adyacencia no dirigida para salto
        adj: Dict[str, Set[str]] = {nid: set() for nid in nodes_by_id}
        for e in graph.get("edges", []):
            s, t = e["source"], e["target"]
            if s in adj and t in adj:
                adj[s].add(t)
                adj[t].add(s)

        visited: Set[str] = {focal_node_id}
        queue: List[Tuple[str, int]] = [(focal_node_id, 0)]

        while queue:
            curr, depth = queue.pop(0)
            if depth >= hop_radius:
                continue
            for neighbor in adj.get(curr, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))

        sub_nodes = [nodes_by_id[nid] for nid in visited if nid in nodes_by_id]
        sub_edges = [
            e for e in graph.get("edges", [])
            if e["source"] in visited and e["target"] in visited
        ]

        return {
            "focal_node": nodes_by_id[focal_node_id],
            "hop_radius": hop_radius,
            "nodes": sub_nodes,
            "edges": sub_edges,
        }

    @staticmethod
    def filter_graph(
        graph: Dict[str, Any],
        active_layers: Optional[Set[str]] = None,
        active_domains: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Filtra nodos y aristas según capas y dominios seleccionados."""
        nodes = graph.get("nodes", [])
        filtered_nodes = []
        for n in nodes:
            if active_layers and n.get("layer") not in active_layers:
                continue
            if active_domains and n.get("domain") not in active_domains:
                continue
            filtered_nodes.append(n)

        node_ids = {n["id"] for n in filtered_nodes}
        filtered_edges = [
            e for e in graph.get("edges", [])
            if e["source"] in node_ids and e["target"] in node_ids
        ]

        return {
            "summary": {
                "total_nodes": len(filtered_nodes),
                "total_edges": len(filtered_edges),
            },
            "nodes": filtered_nodes,
            "edges": filtered_edges,
        }
