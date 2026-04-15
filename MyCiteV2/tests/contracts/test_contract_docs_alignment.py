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
        self.assertIn("/portal/api/v2/system/tools/aws-csm", route_model)
        self.assertIn("/portal/system", route_model)
        self.assertNotIn("/portal/system/activity", route_model)
        self.assertNotIn("/portal/system/profile-basics", route_model)
        self.assertNotIn("POST /portal/api/v2/system/tools/aws\n", route_model)
        self.assertNotIn("/portal/api/v2/system/tools/aws-narrow-write", route_model)
        self.assertNotIn("/portal/api/v2/system/tools/aws-csm-sandbox", route_model)
        self.assertNotIn("/portal/api/v2/system/tools/aws-csm-onboarding", route_model)
        self.assertNotIn("/portal/api/v2/" + "tenant", route_model)
        self.assertNotIn("/portal/api/v2/" + "admin" + "/shell", route_model)

    def test_contract_docs_describe_behavioral_shell_model(self) -> None:
        shell_contract = (REPO_ROOT / "docs" / "contracts" / "portal_shell_contract.md").read_text(encoding="utf-8")
        self.assertIn("ordered focus stack", shell_contract.lower())
        self.assertIn("anthology", shell_contract)
        self.assertIn("datum-file workbench", shell_contract)
        self.assertIn("system-log workbench", shell_contract)
        self.assertIn("system_log.json", shell_contract)
        self.assertIn("layered datum table", shell_contract)
        self.assertIn("activity` and `profile_basics` are workspace file modes", shell_contract)
        self.assertIn("not a tool and not a sandbox", shell_contract)
        self.assertIn("back_out", shell_contract)
        self.assertIn("current context", shell_contract.lower())
        self.assertIn("below the current focus", shell_contract.lower())
        self.assertIn("interface-panel-led", shell_contract)
        self.assertIn("AWS-CSM", shell_contract)
        self.assertIn("authenticated peripheral package", shell_contract.lower())
        self.assertNotIn("stacked focus panel", shell_contract.lower())
        self.assertNotIn("trusted" + "_tenant", shell_contract)
        self.assertNotIn("admin" + " shell", shell_contract.lower())

    def test_surface_catalog_and_routes_describe_network_as_single_workbench(self) -> None:
        route_model = (REPO_ROOT / "docs" / "contracts" / "route_model.md").read_text(encoding="utf-8")
        surface_catalog = (REPO_ROOT / "docs" / "contracts" / "surface_catalog.md").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("/portal/network", route_model)
        self.assertIn("system_log.json", route_model)
        self.assertIn("view", route_model)
        self.assertIn("contract", route_model)
        self.assertIn("type", route_model)
        self.assertIn("record", route_model)
        self.assertNotIn("/portal/network/messages", route_model.lower())
        self.assertNotIn("/portal/network/hosted", route_model.lower())
        self.assertNotIn("/portal/network/profile", route_model.lower())
        self.assertNotIn("/portal/network/contracts", route_model.lower())

        self.assertIn("portal-instance system-log workbench", surface_catalog)
        self.assertIn("not a tool and not a sandbox", surface_catalog)
        self.assertIn("Contract correspondence", surface_catalog)
        self.assertIn("no canonical Messages/Hosted/Profile/Contracts peer-tab model", surface_catalog)

        self.assertIn("portal-instance system-log workbench", readme)
        self.assertIn("system_log.json", readme)

    def test_surface_catalog_describes_one_aws_csm_tool(self) -> None:
        route_model = (REPO_ROOT / "docs" / "contracts" / "route_model.md").read_text(encoding="utf-8")
        surface_catalog = (REPO_ROOT / "docs" / "contracts" / "surface_catalog.md").read_text(encoding="utf-8")
        docs_readme = (REPO_ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("system.tools.aws_csm", surface_catalog)
        self.assertNotIn("system.tools.aws_narrow_write", surface_catalog)
        self.assertNotIn("system.tools.aws_csm_sandbox", surface_catalog)
        self.assertNotIn("system.tools.aws_csm_onboarding", surface_catalog)
        self.assertIn("/portal/system/tools/aws-csm", route_model)
        self.assertNotIn("/portal/system/tools/aws-narrow-write", route_model)
        self.assertNotIn("/portal/system/tools/aws-csm-sandbox", route_model)
        self.assertNotIn("/portal/system/tools/aws-csm-onboarding", route_model)
        self.assertIn("/portal/system/tools/aws-csm", docs_readme)


if __name__ == "__main__":
    unittest.main()
