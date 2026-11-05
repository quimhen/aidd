"""docs/db-graph/test_gen_explorer.py
Pruebas de verificación para el generador del explorador unificado y autónomo.
Compatible con unittest y pytest.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import gen_unified_explorer as gue

SAMPLE_GRAPH = {
    "summary": {
        "total_nodes": 4,
        "total_edges": 3,
        "by_layer": {"db": 1, "code": 1, "spec": 1, "ui": 1},
    },
    "domains": ["Core", "eDoc", "Nomina"],
    "nodes": [
        {
            "id": "db:web:table:OPRM",
            "raw_id": "OPRM",
            "label": "OPRM",
            "layer": "db",
            "type": "table",
            "domain": "Core",
            "purpose": "Cabecera de Permisos y Parámetros",
        },
        {
            "id": "code:eDoc/engine/auth.py:verify_token",
            "raw_id": "verify_token",
            "label": "verify_token",
            "layer": "code",
            "type": "FUNCTION",
            "domain": "Core",
            "purpose": "Verifica tokens JWT",
        },
        {
            "id": "spec:F47",
            "raw_id": "F47",
            "label": "F47",
            "layer": "spec",
            "type": "spec",
            "domain": "Core",
            "purpose": "Unified Knowledge Graph Explorer",
        },
        {
            "id": "ui:COMP-901",
            "raw_id": "COMP-901",
            "label": "Omnibox",
            "layer": "ui",
            "type": "component",
            "domain": "Core",
            "purpose": "Búsqueda predictiva",
        },
    ],
    "edges": [
        {
            "source": "code:eDoc/engine/auth.py:verify_token",
            "target": "db:web:table:OPRM",
            "relation": "lee_col",
            "layer": "code",
            "cross_layer": True,
        },
        {
            "source": "spec:F47",
            "target": "db:web:table:OPRM",
            "relation": "impacta_tabla",
            "layer": "cross",
            "cross_layer": True,
        },
        {
            "source": "ui:COMP-901",
            "target": "spec:F47",
            "relation": "consumido_por",
            "layer": "ui",
            "cross_layer": True,
        },
    ],
}


class TestGenExplorer(unittest.TestCase):
    def test_sin_recursos_externos(self):
        """AC-005: El artefacto HTML debe ser 100% autónomo y offline sin llamadas CDN ni URLs externas."""
        html = gue.generate_html(SAMPLE_GRAPH)
        # Aislar código HTML excluyendo el bloque de datos embebido
        shell = re.sub(r'<script id="graph-data".*?</script>', "", html, flags=re.S)

        # No debe haber referencias http:// o https:// a librerías externas
        self.assertNotIn("http://", shell)
        self.assertNotIn("https://", shell)
        self.assertNotIn("cdn.tailwindcss.com", shell)
        self.assertNotIn("fonts.googleapis.com", shell)
        self.assertFalse(re.search(r'(src|href)\s*=\s*["\'](?!#)(?!data:)', shell))

    def test_datos_incrustados_escapados(self):
        """Valida que los datos JSON se incrusten sin vulnerabilidad de inyección ni corte de script."""
        html = gue.generate_html(SAMPLE_GRAPH)
        match = re.search(r'<script id="graph-data" type="application/json">(.*?)</script>', html, flags=re.S)
        self.assertIsNotNone(match, "El bloque script de datos debe existir en el HTML")

        raw_json = match.group(1)
        self.assertNotIn("</script>", raw_json)
        self.assertNotIn("<", raw_json)
        self.assertNotIn(">", raw_json)

        parsed = json.loads(raw_json)
        self.assertEqual(len(parsed.get("nodes", [])), 4)
        self.assertEqual(len(parsed.get("edges", [])), 3)

    def test_componentes_y_layout_presentes(self):
        """Valida la presencia física de los 10 componentes de SCREEN-95."""
        html = gue.generate_html(SAMPLE_GRAPH)
        required_elements = [
            'id="omnibox-input"',
            'id="layer-metrics-pills"',
            'id="select-layout"',
            'id="sidebar-panel"',
            'id="hop-radius-slider"',
            'id="toggle-impact-mode"',
            'id="network-canvas"',
            'id="minimap-container"',
            'id="inspector-drawer"',
            'id="btn-export-json"',
            'id="btn-export-svg"',
            'id="select-module"',
            'id="select-spec"',
            'id="select-table"',
            'id="select-entity"',
            'id="select-object"',
            'id="btn-reset-filters"',
        ]
        for elem in required_elements:
            self.assertIn(elem, html, f"Elemento {elem} debe estar en el HTML generado")

    def test_main_escribe_archivo_completo(self):
        """Valida la ejecución del script principal generando el artefacto físico en disco."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "test_out.html"
            gue.main(["--out", str(out_file)])
            self.assertTrue(out_file.exists())
            content = out_file.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("<!DOCTYPE html>"))
            self.assertGreater(len(content), 1_000_000, "El HTML con datos completos debe superar 1MB")


if __name__ == "__main__":
    unittest.main()
