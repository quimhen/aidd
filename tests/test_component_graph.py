#!/usr/bin/env python3
"""Tests for AIDD Semantic Component Graph & CDD Gates (Spec 013).

Verifies:
1. Lexical prop and slot extraction (TSX / Dart).
2. Shared-First path validation.
3. Component graph building and TOON serialization / deserialization.
4. Physical path retention.
5. Micro-context prompt injection (--inject) for COMP-nnn and SCREEN-XX.
6. check_spec.py G7 (Monolithic Screen Gate) and G8 (Shared-First Path Gate).
7. Execution benchmark (< 150 ms wall time).
"""
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skill" / "scripts"))

import component_graph  # noqa: E402
import check_spec       # noqa: E402


class TestLexicalExtraction(unittest.TestCase):
    def test_extract_props_tsx(self):
        tsx_code = """
        import React, { ReactNode } from 'react';

        interface ButtonProps {
            label: string;
            onClick?: () => void;
            variant?: 'primary' | 'secondary';
            children?: ReactNode;
            icon?: React.ReactElement;
        }

        export const Button: React.FC<ButtonProps> = ({ label, children }) => {
            return <button>{label}{children}</button>;
        };
        """
        props, slots = component_graph.extract_props_from_source(tsx_code, ".tsx")
        self.assertIn("label", props)
        self.assertIn("onClick", props)
        self.assertIn("variant", props)
        self.assertIn("children", slots)
        self.assertIn("icon", slots)

    def test_extract_props_dart(self):
        dart_code = """
        import 'package:flutter/material.dart';

        class AppCard extends StatelessWidget {
            final String title;
            final VoidCallback? onPressed;
            final Widget child;

            const AppCard({
                Key? key,
                required this.title,
                this.onPressed,
                required this.child,
            }) : super(key: key);

            @override
            Widget build(BuildContext context) {
                return Card(child: child);
            }
        }
        """
        props, slots = component_graph.extract_props_from_source(dart_code, ".dart")
        self.assertIn("title", props)
        self.assertIn("onPressed", props)
        self.assertIn("child", slots)


class TestSharedPath(unittest.TestCase):
    def test_is_shared_path(self):
        self.assertTrue(component_graph.is_shared_path("src/components/Button.tsx"))
        self.assertTrue(component_graph.is_shared_path("src/shared/Card.tsx"))
        self.assertTrue(component_graph.is_shared_path("lib/widgets/header.dart"))
        self.assertTrue(component_graph.is_shared_path("design-system/tokens.ts"))
        self.assertTrue(component_graph.is_shared_path("core/ui/modal.tsx"))
        self.assertFalse(component_graph.is_shared_path("src/screens/HomeScreen/Button.tsx"))
        self.assertFalse(component_graph.is_shared_path("pages/Profile/Card.tsx"))
        self.assertFalse(component_graph.is_shared_path("views/Login.tsx"))


class TestToonSerialization(unittest.TestCase):
    def test_serialize_and_deserialize(self):
        comps = {
            "COMP-001": {
                "id": "COMP-001",
                "name": "DataTable",
                "path": "src/shared/components/DataTable.tsx",
                "pattern": "Compound",
                "props": ["columns", "data", "pageSize"],
                "slots": ["headerSlot", "footerSlot"],
                "consumers": ["SCREEN-01", "SCREEN-02"],
                "source_spec": "specs/001-table",
            },
            "COMP-002": {
                "id": "COMP-002",
                "name": "Badge",
                "path": "src/components/ui/Badge.tsx",
                "pattern": "Atomic",
                "props": ["text", "color"],
                "slots": [],
                "consumers": ["SCREEN-01"],
                "source_spec": "",
            },
        }
        toon_text = component_graph.serialize_toon(comps, root=".")
        self.assertIn("components[", toon_text)
        self.assertIn("COMP-001", toon_text)
        self.assertIn("src/shared/components/DataTable.tsx", toon_text)

        deserialized = component_graph.deserialize_toon(toon_text)
        self.assertEqual(len(deserialized), 2)
        c1 = deserialized["COMP-001"]
        self.assertEqual(c1["name"], "DataTable")
        self.assertEqual(c1["path"], "src/shared/components/DataTable.tsx")
        self.assertEqual(c1["pattern"], "Compound")
        self.assertEqual(c1["props"], ["columns", "data", "pageSize"])
        self.assertEqual(c1["slots"], ["headerSlot", "footerSlot"])
        self.assertEqual(c1["consumers"], ["SCREEN-01", "SCREEN-02"])


class TestMicroContextInjection(unittest.TestCase):
    def setUp(self):
        self.comps = {
            "COMP-001": {
                "id": "COMP-001",
                "name": "PrimaryButton",
                "path": "src/shared/ui/Button.tsx",
                "pattern": "Atomic",
                "props": ["label", "onClick"],
                "slots": ["icon"],
                "consumers": ["SCREEN-01", "SCREEN-05"],
            },
            "COMP-002": {
                "id": "COMP-002",
                "name": "UserCard",
                "path": "src/shared/components/UserCard.tsx",
                "pattern": "Compound",
                "props": ["user", "expanded"],
                "slots": ["actions"],
                "consumers": ["SCREEN-01"],
            },
        }

    def test_inject_comp(self):
        snippet = component_graph.format_subgraph_prompt(self.comps, "COMP-001")
        self.assertIn("# Shared-First Component Context for COMP-001:", snippet)
        self.assertIn("path: src/shared/ui/Button.tsx", snippet)
        self.assertIn("pattern: Atomic", snippet)
        self.assertIn("props: [label, onClick]", snippet)
        self.assertIn("slots: [icon]", snippet)
        self.assertIn("used_by: [SCREEN-01, SCREEN-05]", snippet)
        self.assertIn("rule: Do NOT recreate these components", snippet)

    def test_inject_screen(self):
        snippet = component_graph.format_subgraph_prompt(self.comps, "SCREEN-01")
        self.assertIn("# Shared-First Component Context for SCREEN-01:", snippet)
        self.assertIn("COMP-001", snippet)
        self.assertIn("COMP-002", snippet)
        self.assertIn("src/shared/ui/Button.tsx", snippet)
        self.assertIn("src/shared/components/UserCard.tsx", snippet)


class TestCheckSpecG7G8(unittest.TestCase):
    def test_g7_monolithic_screen_gap(self):
        # 6 controls, 0 COMPs associated with SCREEN-01
        audit_text = """
# Mockup Audit

## Screen inventory
| SCREEN-XX | Name | Uses (COMP-nnn list) |
|---|---|---|
| SCREEN-01 | Dashboard | |

## Component inventory
| COMP-nnn | Name | Used in (SCREEN-XX list) |
|---|---|---|

## Control inventory
| CTL-nnn | Screen or COMP-nnn | Visible text |
|---|---|---|
| CTL-001 | SCREEN-01 | Title |
| CTL-002 | SCREEN-01 | Subtitle |
| CTL-003 | SCREEN-01 | Filter |
| CTL-004 | SCREEN-01 | Search Input |
| CTL-005 | SCREEN-01 | Table |
| CTL-006 | SCREEN-01 | Pagination |
"""
        gaps = check_spec.check_g7_monolithic_screen(audit_text)
        self.assertEqual(len(gaps), 1)
        self.assertIn("G7 mockup-audit.md SCREEN-01: 6 controls but 0 COMP-nnn", gaps[0])

    def test_g7_modular_screen_pass(self):
        # 6 controls, but 1 COMP mapped
        audit_text = """
# Mockup Audit

## Screen inventory
| SCREEN-XX | Name | Uses (COMP-nnn list) |
|---|---|---|
| SCREEN-01 | Dashboard | COMP-001 |

## Component inventory
| COMP-nnn | Name | Used in (SCREEN-XX list) |
|---|---|---|
| COMP-001 | FilterBar | SCREEN-01 |

## Control inventory
| CTL-nnn | Screen or COMP-nnn | Visible text |
|---|---|---|
| CTL-001 | SCREEN-01 | Title |
| CTL-002 | SCREEN-01 | Subtitle |
| CTL-003 | SCREEN-01 | Filter |
| CTL-004 | SCREEN-01 | Search Input |
| CTL-005 | SCREEN-01 | Table |
| CTL-006 | SCREEN-01 | Pagination |
"""
        gaps = check_spec.check_g7_monolithic_screen(audit_text)
        self.assertEqual(gaps, [])

    def test_g8_shared_first_path(self):
        # Non-shared path should gap
        plan_bad = """
## Component → Code map
| COMP-nnn | File/component | Pattern | Used by |
|---|---|---|---|
| COMP-001 | src/screens/HomeScreen/Button.tsx | Atomic | SCREEN-01 |
"""
        gaps = check_spec.check_g8_shared_first_path(plan_bad)
        self.assertEqual(len(gaps), 1)
        self.assertIn("G8 plan.md COMP-001: path 'src/screens/HomeScreen/Button.tsx' is not in a shared component directory", gaps[0])

        # Shared path should pass
        plan_good = """
## Component → Code map
| COMP-nnn | File/component | Pattern | Used by |
|---|---|---|---|
| COMP-001 | src/shared/components/Button.tsx | Atomic | SCREEN-01 |
| COMP-002 | lib/widgets/Card.dart | Compound | SCREEN-02 |
"""
        gaps_good = check_spec.check_g8_shared_first_path(plan_good)
        self.assertEqual(gaps_good, [])


class TestBenchmark(unittest.TestCase):
    def test_serialization_benchmark(self):
        comps = {}
        for i in range(100):
            cid = f"COMP-{i:03d}"
            comps[cid] = {
                "id": cid,
                "name": f"Component{i}",
                "path": f"src/shared/components/Component{i}.tsx",
                "pattern": "Compound" if i % 2 == 0 else "Atomic",
                "props": [f"prop{j}" for j in range(5)],
                "slots": [f"slot{j}" for j in range(2)],
                "consumers": [f"SCREEN-{j:02d}" for j in range(3)],
            }

        t0 = time.perf_counter()
        toon = component_graph.serialize_toon(comps, root=".")
        deserialized = component_graph.deserialize_toon(toon)
        duration = time.perf_counter() - t0

        self.assertEqual(len(deserialized), 100)
        # Wall time must be well under 150 ms (typically < 10 ms)
        self.assertLess(duration, 0.15, f"Serialization took {duration*1000:.2f} ms (> 150 ms)")


if __name__ == "__main__":
    unittest.main()
