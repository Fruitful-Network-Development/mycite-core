from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import build_portal_cts_gis_surface_bundle
from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import run_portal_cts_gis_action
from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.modules.cross_domain.cts_gis import compiled_artifact_path, write_compiled_artifact
from MyCiteV2.packages.modules.cross_domain.cts_gis.compiled_artifact import validate_compiled_artifact
from MyCiteV2.packages.modules.cross_domain.cts_gis.contracts import CTS_GIS_COMPILED_ARTIFACT_SCHEMA
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    CTS_GIS_TOOL_SURFACE_ID,
    PortalScope,
    initial_portal_shell_state,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


_LIVE_INVALID_MSN_SAMRAS = (
    "000000000010000000000110011011100000000100000000010100000010010000001111"
    "000001000100000100100000010011000001011100000110000000011011000001110000"
    "00011110000010000100001000100000100011000010010000001001"
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

    def test_apply_stage_rebuilds_compiled_artifact_from_sql_authority(self) -> None:
        def ascii_bits(value: str, width: int = 256) -> str:
            bitstream = "".join(format(ord(char), "08b") for char in value)
            return bitstream.ljust(width, "0")

        def row(datum_address: str, node_address: str, title: str) -> AuthoritativeDatumDocumentRow:
            return AuthoritativeDatumDocumentRow(
                datum_address=datum_address,
                raw=[
                    [datum_address, "rf.3-1-2", node_address, "rf.3-1-3", ascii_bits(title)],
                    [title.replace(" ", "_")],
                ],
            )

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            db_file = root / "authority.sqlite3"
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            source_rows = {
                "4-1-1": [["4-1-1", "rf.3-1-1", "3-76-11-40-92-20-21-92-51-75-26-64-11-48-77-78-73"], ["polygon_1"]],
                "4-2-1": row("4-2-1", "3-2-3-17-77-1", "ALPHA STREET").raw,
                "4-2-2": row("4-2-2", "3-2-3-17-77-2", "BETA STREET").raw,
                "4-2-3": row("4-2-3", "3-2-3-17-77-2", "GAMMA STREET").raw,
                "5-0-1": [["5-0-1", "~", "4-1-1"], ["summit_boundary"]],
                "7-3-1": [[
                    "7-3-1",
                    "rf.3-1-2",
                    "3-2-3-17-77",
                    "rf.3-1-3",
                    ascii_bits("SUMMIT COUNTY"),
                    "5-0-1",
                    "1",
                ], ["summit_county"]],
            }
            _write_json(
                data_dir / "sandbox" / "cts-gis" / "sources" / "sc.example.json",
                {"datum_addressing_abstraction_space": source_rows},
            )
            _write_json(
                data_dir / "payloads" / "cache" / "sc.example.registrar.json",
                {
                    "payload_id": "sc.example.registrar",
                    "target_mss_anchor_datum": "5-0-1",
                },
            )
            _write_json(
                data_dir / "sandbox" / "cts-gis" / "tool.fnd.cts-gis.json",
                {
                    "datum_addressing_abstraction_space": {
                        "1-1-1": [["1-1-1", "0-0-5", _LIVE_INVALID_MSN_SAMRAS], ["msn-SAMRAS"]],
                        "2-0-2": [["2-0-2", "~", "1-1-1"], ["SAMRAS-space-msn"]],
                        "3-1-1": [["3-1-1", "2-0-2", "0"], ["HOPS-babelette-coordinate"]],
                        "3-1-2": [["3-1-2", "2-0-2", "0"], ["SAMRAS-babelette-msn_id"]],
                        "3-1-3": [["3-1-3", "2-0-2", "0"], ["title-babelette"]],
                    }
                },
            )
            SqliteSystemDatumStoreAdapter(db_file).store_authoritative_catalog(
                AuthoritativeDatumDocumentCatalogResult(
                    tenant_id="fnd",
                    documents=(
                        AuthoritativeDatumDocument(
                            document_id="sandbox:cts_gis:sc.example.json",
                            source_kind="sandbox_source",
                            document_name="sc.example.json",
                            relative_path="sandbox/cts-gis/sources/sc.example.json",
                            tool_id="cts_gis",
                            rows=(
                                AuthoritativeDatumDocumentRow(
                                    datum_address="4-1-1",
                                    raw=source_rows["4-1-1"],
                                ),
                                row("4-2-1", "3-2-3-17-77-1", "ALPHA STREET"),
                                row("4-2-2", "3-2-3-17-77-2", "BETA STREET"),
                                row("4-2-3", "3-2-3-17-77-2", "GAMMA STREET"),
                                AuthoritativeDatumDocumentRow(
                                    datum_address="5-0-1",
                                    raw=source_rows["5-0-1"],
                                ),
                                AuthoritativeDatumDocumentRow(
                                    datum_address="7-3-1",
                                    raw=source_rows["7-3-1"],
                                ),
                            ),
                        ),
                    ),
                    source_files={"sandbox/cts-gis/sources/sc.example.json": {"exists": True}},
                    readiness_status={"authoritative_catalog": "loaded"},
                )
            )

            staged = run_portal_cts_gis_action(
                {
                    "schema": "mycite.v2.portal.system.tools.cts_gis.action.request.v1",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                    "tool_state": {
                        "selected_node_id": "3-2-3-17-77-1",
                        "source": {"attention_document_id": "sandbox:cts_gis:sc.example.json"},
                    },
                    "action_kind": "stage_insert_yaml",
                    "action_payload": {
                        "stage_document": {
                            "schema": "mycite.v2.cts_gis.stage_insert.v1",
                            "document_id": "sandbox:cts_gis:sc.example.json",
                            "document_name": "sc.example.json",
                            "operation": "insert_datums",
                            "datums": [
                                {
                                    "family": "administrative_street",
                                    "valueGroup": 2,
                                    "targetNodeAddress": "3-2-3-17-77-1",
                                    "title": "MAIN STREET",
                                    "references": [
                                        {"type": "title", "text": "MAIN STREET"},
                                        {"type": "msn-samras", "nodeAddress": "3-2-3-17-77-1"},
                                    ],
                                }
                            ],
                        }
                    },
                },
                data_dir=data_dir,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            preview = run_portal_cts_gis_action(
                {
                    "schema": "mycite.v2.portal.system.tools.cts_gis.action.request.v1",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                    "tool_state": staged["surface_payload"]["tool_state"],
                    "action_kind": "preview_apply",
                    "action_payload": {},
                },
                data_dir=data_dir,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            run_portal_cts_gis_action(
                {
                    "schema": "mycite.v2.portal.system.tools.cts_gis.action.request.v1",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                    "tool_state": preview["surface_payload"]["tool_state"],
                    "action_kind": "apply_stage",
                    "action_payload": {},
                },
                data_dir=data_dir,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )

            compiled_path = compiled_artifact_path(data_dir, portal_scope_id="fnd")
            self.assertIsNotNone(compiled_path)
            self.assertTrue(compiled_path.exists())
            compiled_artifact = json.loads(compiled_path.read_text(encoding="utf-8"))
            self.assertEqual(compiled_artifact["schema"], CTS_GIS_COMPILED_ARTIFACT_SCHEMA)
            self.assertEqual(compiled_artifact["default_tool_state"]["source"]["attention_document_id"], "sandbox:cts_gis:sc.example.json")
            self.assertEqual(compiled_artifact["navigation_model"]["decode_state"], "ready")
            self.assertTrue(compiled_artifact["evidence_model"]["source_evidence"]["tool_anchor"]["exists"])
            self.assertTrue(compiled_artifact["evidence_model"]["source_evidence"]["registrar_payload"]["exists"])


if __name__ == "__main__":
    unittest.main()
