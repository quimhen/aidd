"""F47 T-02: Pruebas unitarias para el modelo y generador del explorador unificado."""
import sys
import unittest
from pathlib import Path

# Agregar docs/db-graph al path de búsqueda
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from unified_graph_model import UnifiedGraphModel


class TestUnifiedExplorer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = UnifiedGraphModel(root=ROOT_DIR)
        cls.graph = cls.model.load()

    def test_sources_exist(self):
        """Verifica la existencia física de los 4 grafos fuente del monorepositorio."""
        self.assertTrue(self.model.db_graph_path.exists(), "docs/db-graph/graph.json debe existir")
        self.assertTrue(self.model.code_graph_path.exists(), ".aidd/graphs/code.json debe existir")
        self.assertTrue(self.model.spec_graph_path.exists(), "specs/index.toon debe existir")
        self.assertTrue(self.model.ui_graph_path.exists(), ".aidd/graphs/ui.toon debe existir")

    def test_unified_graph_loads_all_layers(self):
        """FR-001: Valida que el modelo cargue nodos de las 4 capas (DB, AST, Spec, UI)."""
        summary = self.graph.get("summary", {})
        by_layer = summary.get("by_layer", {})

        # Validar umbrales mínimos según charter y estado actual
        self.assertGreater(by_layer.get("db", 0), 6000, "Debe cargar > 6,000 nodos de base de datos")
        self.assertGreater(by_layer.get("code", 0), 1000, "Debe cargar > 1,000 nodos de código AST")
        self.assertGreater(by_layer.get("spec", 0), 60, "Debe cargar > 60 especificaciones AIDD")
        self.assertGreater(by_layer.get("ui", 0), 400, "Debe cargar > 400 componentes de interfaz UI")
        self.assertGreater(summary.get("total_edges", 0), 40000, "Debe cargar > 40,000 aristas totales")

    def test_cross_layer_linking(self):
        """FR-002: Valida la presencia de aristas cruzadas entre capas (cross-layer links)."""
        edges = self.graph.get("edges", [])
        cross_edges = [e for e in edges if e.get("cross_layer") is True]
        self.assertGreater(len(cross_edges), 100, "Debe descubrir más de 100 enlaces cruzados entre capas")

        # Verificar tipos de relaciones cross-layer
        relations = {e["relation"] for e in cross_edges}
        self.assertTrue("consumido_por" in relations or "impacta_tabla" in relations)

    def test_hop_radius_neighborhood(self):
        """FR-003: Valida el cálculo de vecindario por BFS restringido por radio de saltos."""
        # Tomar un nodo representativo de BD
        sub_r1 = self.model.compute_neighborhood(self.graph, "OPRM", hop_radius=1)
        self.assertIsNotNone(sub_r1.get("focal_node"))
        self.assertGreater(len(sub_r1.get("nodes", [])), 1)

        sub_r2 = self.model.compute_neighborhood(self.graph, "OPRM", hop_radius=2)
        self.assertGreater(len(sub_r2.get("nodes", [])), len(sub_r1.get("nodes", [])))

        # Todos los nodos en sub_r1 deben pertenecer a sub_r2
        r1_ids = {n["id"] for n in sub_r1["nodes"]}
        r2_ids = {n["id"] for n in sub_r2["nodes"]}
        self.assertTrue(r1_ids.issubset(r2_ids))

    def test_layer_and_domain_filtering(self):
        """FR-005: Valida el filtrado multi-criterio por capas y dominios."""
        # Filtrar solo capa DB
        db_only = self.model.filter_graph(self.graph, active_layers={"db"})
        for n in db_only["nodes"]:
            self.assertEqual(n["layer"], "db")

        # Filtrar solo capa UI
        ui_only = self.model.filter_graph(self.graph, active_layers={"ui"})
        for n in ui_only["nodes"]:
            self.assertEqual(n["layer"], "ui")

        # Filtrar por dominio eDoc
        edoc_sub = self.model.filter_graph(self.graph, active_domains={"eDoc"})
        for n in edoc_sub["nodes"]:
            self.assertEqual(n["domain"], "eDoc")
        self.assertGreater(len(edoc_sub["nodes"]), 0)


if __name__ == "__main__":
    unittest.main()
