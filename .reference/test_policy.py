import ast
import tempfile
import unittest
from pathlib import Path

from policy import check_import_edges


class OwnershipGraphTests(unittest.TestCase):
    def setUp(self):
        self.owners = {
            "contracts": "contracts",
            "product": "product",
            "product.local": "product",
            "alternative": "alternative",
        }
        self.allowed = {("product", "contracts"), ("alternative", "contracts")}

    def test_public_contract_and_same_owner_imports_pass(self):
        check_import_edges(
            self.owners,
            [("product", "contracts"), ("product", "product.local")],
            self.allowed,
        )

    def test_real_source_adapter_exposes_implementation_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "product.py"
            source.write_text("import alternative\n", encoding="utf-8")
            edges = [
                ("product", alias.name)
                for node in ast.walk(ast.parse(source.read_text(encoding="utf-8")))
                if isinstance(node, ast.Import)
                for alias in node.names
            ]
            with self.assertRaisesRegex(ValueError, "forbidden dependency"):
                check_import_edges(self.owners, edges, self.allowed)

    def test_shared_contract_cannot_borrow_product_implementation(self):
        with self.assertRaises(ValueError):
            check_import_edges(self.owners, [("contracts", "product")], self.allowed)

    def test_new_internal_module_requires_discovered_owner(self):
        with self.assertRaisesRegex(ValueError, "no discovered owner"):
            check_import_edges(self.owners, [("product", "new_product")], self.allowed)

    def test_retired_owner_in_allowed_graph_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "undiscovered owner"):
            check_import_edges(self.owners, [], {("product", "retired")})


if __name__ == "__main__":
    unittest.main()
