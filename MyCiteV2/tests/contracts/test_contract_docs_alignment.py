from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class ContractDocsAlignmentTests(unittest.TestCase):
    def test_contract_docs_use_one_shell_routes(self) -> None:
        route_model = (REPO_ROOT / "docs" / "contracts" / "route_model.md").read_text(encoding="utf-8")
        self.assertIn("/portal/api/v2/shell", route_model)
        self.assertIn("/portal/system/tools/<tool_slug>", route_model)
        self.assertNotIn("/portal/api/v2/" + "tenant", route_model)
        self.assertNotIn("/portal/api/v2/" + "admin" + "/shell", route_model)

    def test_contract_docs_use_one_shell_terminology(self) -> None:
        shell_contract = (REPO_ROOT / "docs" / "contracts" / "portal_shell_contract.md").read_text(encoding="utf-8")
        self.assertIn("SYSTEM", shell_contract)
        self.assertIn("NETWORK", shell_contract)
        self.assertIn("UTILITIES", shell_contract)
        self.assertNotIn("trusted" + "_tenant", shell_contract)
        self.assertNotIn("admin" + " shell", shell_contract.lower())


if __name__ == "__main__":
    unittest.main()
