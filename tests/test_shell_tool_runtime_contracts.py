from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from _shared.portal.application.agro.config_bindings import build_agro_config_context
from _shared.portal.application.shell.runtime import build_selected_context_payload
from _shared.portal.application.shell.tools import normalize_tool_capability
from _shared.portal.application.workbench.document_contract import build_workbench_document


def _load_agro_tool_meta() -> dict[str, object]:
    path = Path(__file__).resolve().parents[1] / "portals" / "_shared" / "runtime" / "flavors" / "tff" / "portal" / "tools" / "agro_erp" / "__init__.py"
    portals_root = path.parents[6]
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    spec = importlib.util.spec_from_file_location("agro_erp_shell_contracts_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError as exc:
        if str(getattr(exc, "name", "")) == "flask":
            raise unittest.SkipTest("flask is not installed in host python")
        raise
    return module.get_tool()


def _load_fnd_tool_meta(tool_id: str) -> dict[str, object]:
    path = (
        Path(__file__).resolve().parents[1]
        / "portals"
        / "_shared"
        / "runtime"
        / "flavors"
        / "fnd"
        / "portal"
        / "tools"
        / tool_id
        / "__init__.py"
    )
    portals_root = path.parents[7]
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    spec = importlib.util.spec_from_file_location(f"{tool_id}_shell_contracts_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError as exc:
        if str(getattr(exc, "name", "")) == "flask":
            raise unittest.SkipTest("flask is not installed in host python")
        raise
    return module.get_tool()


class ShellToolRuntimeContractTests(unittest.TestCase):
    def test_agro_tool_capability_contract_is_normalized(self) -> None:
        capability = normalize_tool_capability(_load_agro_tool_meta())
        self.assertEqual(capability.get("tool_id"), "agro_erp")
        self.assertTrue(capability.get("config_context_support"))
        self.assertIn("mediate", capability.get("supported_verbs") or [])
        self.assertTrue(any(bool(item.get("config_context")) for item in capability.get("supported_source_contracts") or []))

    def test_service_tool_capability_contract_is_normalized(self) -> None:
        capability = normalize_tool_capability(_load_fnd_tool_meta("website_analytics"))
        self.assertEqual(capability.get("tool_id"), "website_analytics")
        self.assertTrue(capability.get("config_context_support"))
        self.assertEqual(((capability.get("workbench_contribution") or {}).get("default_mode")), "profiles")
        self.assertTrue(any(bool(item.get("config_context")) for item in capability.get("supported_source_contracts") or []))

    def test_selected_context_includes_compatible_tool_registry(self) -> None:
        document = build_workbench_document(
            document_id="workbench:system:txa",
            instance_id="fnd",
            logical_key="txa",
            display_name="samras-txa.json",
            family_kind="resource",
            family_type="samras_txa",
            family_subtype="txa",
            scope_kind="local",
            payload={"file_key": "txa"},
        )
        payload = build_selected_context_payload(
            document=document,
            selected_row={"identifier": "8-5-11", "label": "Product Type", "file_key": "txa"},
            shell_verb="mediate",
            tool_tabs=[_load_agro_tool_meta()],
        )
        self.assertEqual(payload.get("schema"), "mycite.shell.selected_context.v1")
        self.assertEqual(((payload.get("selection") or {}).get("row_identifier")), "8-5-11")
        self.assertTrue(any(str(item.get("tool_id") or "") == "agro_erp" for item in payload.get("compatible_tools") or []))

    def test_agro_config_context_prefers_inherited_but_can_fall_back_to_local(self) -> None:
        txa_local = build_workbench_document(
            document_id="workbench:local:samras.txa",
            instance_id="fnd",
            logical_key="samras.txa",
            display_name="SAMRAS TXA",
            family_kind="resource",
            family_type="samras_txa",
            scope_kind="local",
        )
        msn_local = build_workbench_document(
            document_id="workbench:local:samras.msn",
            instance_id="fnd",
            logical_key="samras.msn",
            display_name="SAMRAS MSN",
            family_kind="resource",
            family_type="samras_msn",
            scope_kind="local",
        )
        payload = build_agro_config_context(
            active_config={"property": {"title": "Property"}},
            tool_tabs=[_load_agro_tool_meta()],
            local_documents=[txa_local, msn_local],
            inherited_documents=[],
            sandbox_documents=[],
            portal_instance_id="fnd",
            msn_id="3-2-3-17-77-1-6-4-1-4",
        )
        self.assertEqual(payload.get("schema"), "mycite.shell.config_context.v1")
        txa_binding = ((payload.get("resource_role_bindings") or {}).get("txa")) or {}
        self.assertTrue(txa_binding.get("valid"))
        self.assertEqual((((txa_binding.get("resolved") or {}).get("activation_payload") or {}).get("local_resource_id")), "samras.txa")
        self.assertTrue(any("fell back to local" in str(item) for item in txa_binding.get("warnings") or []))

    def test_unified_system_workbench_owns_shell_event_bridge(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        data_tool = (
            repo_root
            / "portals"
            / "_shared"
            / "runtime"
            / "flavors"
            / "fnd"
            / "portal"
            / "ui"
            / "static"
            / "tools"
            / "data_tool.js"
        ).read_text(encoding="utf-8")
        self.assertIn("mycite:shell:selection-input", data_tool)
        self.assertIn("mycite:shell:workbench-payload", data_tool)
        self.assertIn("mycite:shell:verb-changed", data_tool)
        self.assertNotIn("mycite:shell:workbench" + "-mode", data_tool)

        removed_assets = [
            repo_root
            / "portals"
            / "_shared"
            / "portal"
            / "ui"
            / "static"
            / "system_compatibility_runtime.js",
            repo_root
            / "portals"
            / "_shared"
            / "portal"
            / "ui"
            / "static"
            / "system_compatibility_views.js",
            repo_root
            / "portals"
            / "_shared"
            / "runtime"
            / "flavors"
            / "fnd"
            / "portal"
            / "ui"
            / "static"
            / "tools"
            / "local_resources_workbench.js",
            repo_root
            / "portals"
            / "_shared"
            / "runtime"
            / "flavors"
            / "fnd"
            / "portal"
            / "ui"
            / "static"
            / "tools"
            / "inheritance_workbench.js",
            repo_root
            / "portals"
            / "_shared"
            / "runtime"
            / "flavors"
            / "tff"
            / "portal"
            / "ui"
            / "static"
            / "tools"
            / "local_resources_workbench.js",
            repo_root
            / "portals"
            / "_shared"
            / "runtime"
            / "flavors"
            / "tff"
            / "portal"
            / "ui"
            / "static"
            / "tools"
            / "inheritance_workbench.js",
        ]
        for path in removed_assets:
            self.assertFalse(path.exists(), str(path))

    def test_shared_system_shell_runtime_is_generic_mediation_host(self) -> None:
        runtime_js = (
            Path(__file__).resolve().parents[1]
            / "portals"
            / "_shared"
            / "portal"
            / "ui"
            / "static"
            / "system_shell_runtime.js"
        ).read_text(encoding="utf-8")
        self.assertIn("ensureToolContext", runtime_js)
        self.assertIn("genericMediationProvider", runtime_js)
        self.assertIn("workbench_contribution", runtime_js)
        self.assertIn("inspector_card_contribution", runtime_js)
        self.assertIn("mutation_policy", runtime_js)
        self.assertIn("preview_hooks", runtime_js)
        self.assertIn("apply_hooks", runtime_js)
        self.assertIn("route_prefix", runtime_js)
        self.assertNotIn("agroOpenBtn", runtime_js)
        self.assertNotIn("/portal/api/data/system/config_context/agro_erp", runtime_js)
        self.assertNotIn("state.agroConfigContext", runtime_js)


if __name__ == "__main__":
    unittest.main()
