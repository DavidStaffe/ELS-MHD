"""Pure geometry regression tests without a running MongoDB."""
import ast
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "routes" / "patient_disposition.py"
tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
selected = [
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name in ("km", "section_neighbors")
]
module = ast.Module(body=selected, type_ignores=[])
ns = {name: getattr(math, name) for name in ("radians", "sin", "cos", "asin", "sqrt")}
exec(compile(module, str(SOURCE), "exec"), ns)


class GeometryTests(unittest.TestCase):
    def test_distance_zero(self):
        self.assertAlmostEqual(ns["km"]((53.0, 10.0), (53.0, 10.0)), 0)

    def test_distance_positive(self):
        self.assertGreater(ns["km"]((53.0, 10.0), (53.01, 10.01)), 0)

    def test_adjacent_polygons(self):
        a = {"polygon": [[53.0, 10.0], [53.0, 10.01], [53.01, 10.01], [53.01, 10.0]]}
        b = {"polygon": [[53.0, 10.01], [53.0, 10.02], [53.01, 10.02], [53.01, 10.01]]}
        self.assertTrue(ns["section_neighbors"](a, b))

    def test_distant_polygons(self):
        a = {"polygon": [[53.0, 10.0], [53.0, 10.01], [53.01, 10.01]]}
        b = {"polygon": [[53.2, 10.2], [53.2, 10.21], [53.21, 10.21]]}
        self.assertFalse(ns["section_neighbors"](a, b))

    def test_missing_polygons_not_inferred(self):
        self.assertFalse(ns["section_neighbors"]({"name": "Nord"}, {"name": "Süd"}))


if __name__ == "__main__":
    unittest.main()
