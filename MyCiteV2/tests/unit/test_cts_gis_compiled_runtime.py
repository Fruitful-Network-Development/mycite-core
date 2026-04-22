from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import build_portal_cts_gis_surface_bundle
from MyCiteV2.packages.modules.cross_domain.cts_gis import compiled_artifact_path, write_compiled_artifact
from MyCiteV2.packages.modules.cross_domain.cts_gis.compiled_artifact import validate_compiled_artifact
from MyCiteV2.packages.modules.cross_domain.cts_gis.contracts import CTS_GIS_COMPILED_ARTIFACT_SCHEMA
from MyCiteV2.packages.state_machine.portal_shell import (
    CTS_GIS_TOOL_SURFACE_ID,
    PortalScope,
    initial_portal_shell_state,
)


class CtsGisCompiledRuntimeTests(unittest.TestCase):
    def _scope(self) -> PortalScope:
        return PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection"))

    def test_production_strict_fails_fast_when_compiled_artifact_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            scope = self._scope()
            shell_state = initial_portal_shell_state(surface_id=CTS_GIS_TOOL_SURFACE_ID, portal_scope=scope)
            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=scope,
                shell_state=shell_state,
                data_dir=tmp,
                private_dir=None,
                request_payload={"runtime_mode": "production_strict"},
            )
            payload = bundle["surface_payload"]
            self.assertEqual(payload["runtime_mode"], "production_strict")
            self.assertEqual(payload["readiness"]["state"], "compiled_state_invalid")
            self.assertIn("compiled_cts_gis_state_invalid", payload["warnings"])

    def test_production_strict_uses_compiled_artifact_models(self) -> None:
        with TemporaryDirectory() as tmp:
            scope = self._scope()
            compiled_path = compiled_artifact_path(tmp, portal_scope_id=scope.scope_id)
            self.assertIsNotNone(compiled_path)
            write_compiled_artifact(
                compiled_path,
                {
                    "schema": CTS_GIS_COMPILED_ARTIFACT_SCHEMA,
                    "artifact_version": "1",
                    "generated_at": "2026-01-01T00:00:00Z",
                    "portal_scope_id": "fnd",
                    "build_mode": "audit_forensic",
                    "default_runtime_mode": "production_strict",
                    "default_tool_state": {
                        "nimm_directive": "mediate",
                        "active_path": ["3", "3-2"],
                        "selected_node_id": "3-2",
                        "aitas": {"attention_node_id": "3-2", "intention_rule_id": "self", "time_directive": "", "archetype_family_id": "samras_nominal"},
                        "source": {"attention_document_id": "sandbox:cts_gis:doc.json", "precinct_district_overlay_enabled": False},
                        "selection": {"selected_row_address": "", "selected_feature_id": "", "selected_row_explicit": False, "selected_feature_explicit": False},
                    },
                    "navigation_model": {
                        "decode_state": "ready",
                        "source_authority": "samras_magnitude",
                        "active_node_id": "3-2",
                        "active_path": [
                            {"node_id": "3", "title": "root", "display_label": "3 root", "selected": False},
                            {"node_id": "3-2", "title": "us", "display_label": "3-2 us", "selected": True},
                        ],
                        "dropdowns": [
                            {"depth": 1, "parent_node_id": "", "selected_node_id": "3", "options": [{"node_id": "3", "title": "root", "display_label": "3 root", "selected": True}]},
                            {"depth": 2, "parent_node_id": "3", "selected_node_id": "3-2", "options": [{"node_id": "3-2", "title": "us", "display_label": "3-2 us", "selected": True}]},
                        ],
                    },
                    "projection_model": {
                        "projection_state": "projectable",
                        "projection_source": "hops",
                        "projection_health": {"state": "ok", "reason_codes": []},
                        "fallback_reason_codes": [],
                        "focus_bounds": [-1, -1, 1, 1],
                        "feature_collection": {"type": "FeatureCollection", "features": [], "bounds": [-1, -1, 1, 1]},
                        "selected_feature": {},
                        "profile_summary": {"node_id": "3-2", "label": "us", "feature_count": 0, "child_count": 0, "document_id": "sandbox:cts_gis:doc.json"},
                    },
                    "evidence_model": {"source_evidence": {"readiness": {"state": "ready"}}, "diagnostic_summary": {}, "warnings": []},
                    "invariants": {"valid": True, "issues": []},
                    "strict_invariants": {
                        "one_authority": True,
                        "authority_sources": ["tool_anchor"],
                        "one_namespace": True,
                        "namespace_roots": ["3"],
                        "valid": True,
                        "issues": [],
                    },
                },
            )
            shell_state = initial_portal_shell_state(surface_id=CTS_GIS_TOOL_SURFACE_ID, portal_scope=scope)
            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=scope,
                shell_state=shell_state,
                data_dir=tmp,
                private_dir=None,
                request_payload={"runtime_mode": "production_strict"},
            )
            payload = bundle["surface_payload"]
            nav = payload["navigation_model"]
            self.assertEqual(payload["runtime_mode"], "production_strict")
            self.assertEqual(nav["decode_state"], "ready")
            self.assertTrue(nav["dropdowns"][0]["options"][0]["action"]["kind"] == "select_node")

    def test_validate_compiled_artifact_rejects_multi_authority_strict_invariant(self) -> None:
        valid, issues = validate_compiled_artifact(
            {
                "schema": CTS_GIS_COMPILED_ARTIFACT_SCHEMA,
                "navigation_model": {},
                "projection_model": {},
                "invariants": {"valid": True, "issues": []},
                "strict_invariants": {
                    "one_authority": False,
                    "authority_sources": ["tool_anchor", "administrative_payload_cache"],
                    "one_namespace": True,
                    "namespace_roots": ["3"],
                    "valid": False,
                    "issues": ["strict_one_authority_failed"],
                },
            }
        )
        self.assertFalse(valid)
        self.assertIn("strict_one_authority_failed", issues)


if __name__ == "__main__":
    unittest.main()
