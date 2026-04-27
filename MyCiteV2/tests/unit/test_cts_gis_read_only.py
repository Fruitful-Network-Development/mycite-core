from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import FilesystemSystemDatumStoreAdapter
from MyCiteV2.packages.modules.cross_domain.cts_gis import CtsGisReadOnlyService
from MyCiteV2.packages.modules.cross_domain.cts_gis import service as cts_gis_service
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRow,
)

_SUMMIT_DATA_ROOT_CANDIDATES = (
    REPO_ROOT / "deployed" / "fnd" / "data",
    Path("/srv/mycite-state/instances/fnd/data"),
)
SUMMIT_DATA_ROOT = next(
    (candidate for candidate in _SUMMIT_DATA_ROOT_CANDIDATES if candidate.exists() and candidate.is_dir()),
    _SUMMIT_DATA_ROOT_CANDIDATES[0],
)
SUMMIT_SOURCES_ROOT = SUMMIT_DATA_ROOT / "sandbox" / "cts-gis" / "sources"


class _FakeDatumStore:
    def __init__(self, result: AuthoritativeDatumDocumentCatalogResult) -> None:
        self.result = result
        self.requests = []

    def read_authoritative_datum_documents(self, request):
        self.requests.append(request)
        return self.result


def _anchor_row(address: str, label: str) -> AuthoritativeDatumDocumentRow:
    return AuthoritativeDatumDocumentRow(
        datum_address=address,
        raw=[[address, "~", "0-0-0"], [label]],
    )


def _anchor_rows() -> tuple[AuthoritativeDatumDocumentRow, ...]:
    return (
        _anchor_row("3-1-1", "HOPS-babelette-coordinate"),
        _anchor_row("3-1-2", "SAMRAS-babelette-msn_id"),
        _anchor_row("3-1-3", "title-babelette"),
    )


def _anchor_rows_with_chronology() -> tuple[AuthoritativeDatumDocumentRow, ...]:
    return _anchor_rows() + (
        AuthoritativeDatumDocumentRow(
            datum_address="1-1-5",
            raw=[["1-1-5", "~", "10101010"], ["chronological_hops_space"]],
        ),
        AuthoritativeDatumDocumentRow(
            datum_address="2-0-4",
            raw=[["2-0-4", "~", "1-1-5"], ["chronological_hops_binding"]],
        ),
        AuthoritativeDatumDocumentRow(
            datum_address="3-1-5",
            raw=[["3-1-5", "2-0-4", "0"], ["chronological_hops_babelette"]],
        ),
    )


def _ascii_bits(text: str) -> str:
    return "".join(format(value, "08b") for value in text.encode("ascii"))


def _cts_gis_document() -> AuthoritativeDatumDocument:
    summit_binary = (
        "011100110111010101101101011011010110100101110100"
        "0000000000000000"
    )
    fairlawn_binary = (
        "011001100110000101101001011100100110110001100001"
        "011101110110111000000000"
    )
    return AuthoritativeDatumDocument(
        document_id="sandbox:cts_gis:sc.example.json",
        source_kind="sandbox_source",
        document_name="sc.example.json",
        relative_path="sandbox/cts-gis/sources/sc.example.json",
        tool_id="cts_gis",
        anchor_document_name="tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
        anchor_document_path="sandbox/cts-gis/tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
        anchor_rows=_anchor_rows(),
        rows=(
            AuthoritativeDatumDocumentRow(
                datum_address="4-1-1",
                raw=[
                    ["4-1-1", "rf.3-1-1", "3-76-11-40-92-20-21-92-51-75-26-64-11-48-77-78-73"],
                    ["polygon_1"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="4-1-2",
                raw=[
                    [
                        "4-1-2",
                        "rf.3-1-1",
                        "3-76-11-40-92-20-21-92-81-29-56-60-79-56-3-4-39",
                    ],
                    ["point_alpha"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="5-0-1",
                raw=[
                    ["5-0-1", "~", "4-1-1"],
                    ["summit_boundary"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="6-0-1",
                raw=[
                    ["6-0-1", "~", "4-1-2"],
                    ["fairlawn_boundary_collection"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="7-3-1",
                raw=[
                    ["7-3-1", "rf.3-1-2", "3-2-3-17-77-1", "rf.3-1-3", summit_binary, "5-0-1", "1"],
                    ["summit_county"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="7-3-2",
                raw=[
                    [
                        "7-3-2",
                        "rf.3-1-2",
                        "3-2-3-17-77-1-1",
                        "rf.3-1-3",
                        fairlawn_binary,
                        "6-0-1",
                        "1",
                    ],
                    ["fairlawn_city"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="7-3-3",
                raw=[
                    ["7-3-3", "rf.3-1-2", "3-2-3-17-77-1-2", "rf.3-1-3", "HERE"],
                    ["bad_title"],
                ],
            ),
        ),
    )


def _document_from_source_file(path: Path) -> AuthoritativeDatumDocument:
    payload = json.loads(path.read_text(encoding="utf-8"))
    space = dict(payload.get("datum_addressing_abstraction_space") or {})
    metadata = {key: value for key, value in payload.items() if key != "datum_addressing_abstraction_space"}
    return AuthoritativeDatumDocument(
        document_id=f"sandbox:cts_gis:{path.name}",
        source_kind="sandbox_source",
        document_name=path.name,
        relative_path=f"sandbox/cts-gis/sources/{path.name}",
        tool_id="cts_gis",
        anchor_document_name="tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
        anchor_document_path="sandbox/cts-gis/tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
        anchor_rows=_anchor_rows(),
        document_metadata=metadata,
        rows=tuple(
            AuthoritativeDatumDocumentRow(datum_address=address, raw=row)
            for address, row in sorted(space.items())
        ),
    )


def _summit_source_path(node_id: str) -> Path:
    return SUMMIT_SOURCES_ROOT / f"sc.3-2-3-17-77-1-6-4-1-4.fnd.{node_id}.json"


def _cts_gis_reference_fallback_document() -> AuthoritativeDatumDocument:
    feature_collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-81.5, 41.1],
                        [-81.45, 41.1],
                        [-81.43, 41.12],
                        [-81.45, 41.15],
                        [-81.49, 41.16],
                        [-81.5, 41.1],
                    ]],
                },
                "properties": {"community_name": "fallback_county"},
            }
        ],
    }
    return AuthoritativeDatumDocument(
        document_id="sandbox:cts_gis:sc.fallback.3-2-3-17-77.json",
        source_kind="sandbox_source",
        document_name="sc.fallback.3-2-3-17-77.json",
        relative_path="sandbox/cts-gis/sources/sc.fallback.3-2-3-17-77.json",
        tool_id="cts_gis",
        anchor_document_name="tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
        anchor_document_path="sandbox/cts-gis/tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
        anchor_rows=_anchor_rows(),
        document_metadata={
            "reference_geojson_node_id": "3-2-3-17-77",
            "reference_geojson": feature_collection,
        },
        rows=(
            AuthoritativeDatumDocumentRow(
                datum_address="4-4-1",
                raw=[
                    ["4-4-1", "rf.3-1-1", "8-0-0", "rf.3-1-1", "8-0-0", "rf.3-1-1", "8-0-0", "rf.3-1-1", "8-0-0"],
                    ["fallback_polygon"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="5-0-1",
                raw=[["5-0-1", "~", "4-4-1"], ["fallback_boundary"]],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="6-0-1",
                raw=[["6-0-1", "~", "5-0-1"], ["fallback_collection"]],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="7-3-1",
                raw=[
                    ["7-3-1", "rf.3-1-2", "3-2-3-17-77", "rf.3-1-3", "0110011001100001011011000110110001100010011000010110001101101011", "6-0-1", "1"],
                    ["fallback_county"],
                ],
            ),
        ),
    )


def _cts_gis_semantic_guardrail_document(*, with_reference_geojson: bool) -> AuthoritativeDatumDocument:
    metadata: dict[str, object] = {}
    if with_reference_geojson:
        metadata = {
            "reference_geojson_node_id": "3-2-3-17-77",
            "reference_geojson": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [-81.63, 41.02],
                                [-81.45, 41.02],
                                [-81.44, 41.16],
                                [-81.62, 41.18],
                                [-81.63, 41.02],
                            ]],
                        },
                        "properties": {"community_name": "summit_reference"},
                    }
                ],
            },
        }
    return AuthoritativeDatumDocument(
        document_id="sandbox:cts_gis:sc.semantic-guardrail.3-2-3-17-77.json",
        source_kind="sandbox_source",
        document_name="sc.semantic-guardrail.3-2-3-17-77.json",
        relative_path="sandbox/cts-gis/sources/sc.semantic-guardrail.3-2-3-17-77.json",
        tool_id="cts_gis",
        anchor_document_name="tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
        anchor_document_path="sandbox/cts-gis/tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
        anchor_rows=_anchor_rows(),
        document_metadata=metadata,
        rows=(
            AuthoritativeDatumDocumentRow(
                datum_address="4-3-1",
                raw=[
                    [
                        "4-3-1",
                        "rf.3-1-1",
                        "3-76-11-33-94-18-62-86-96-8-48-58-76-30-32-86-49-4",
                        "rf.3-1-1",
                        "3-76-11-33-94-48-33-12-77-27-69-69-38-52-19-46-63",
                        "rf.3-1-1",
                        "3-76-11-33-94-58-63-54-38-55-18-2-87-68-26-48-30-5",
                    ],
                    ["semantic_guardrail_polygon"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="5-0-1",
                raw=[["5-0-1", "~", "4-3-1"], ["semantic_guardrail_boundary"]],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="6-0-1",
                raw=[["6-0-1", "~", "5-0-1"], ["semantic_guardrail_collection"]],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="7-3-1",
                raw=[
                    ["7-3-1", "rf.3-1-2", "3-2-3-17-77", "rf.3-1-3", _ascii_bits("summit_guardrail"), "6-0-1", "1"],
                    ["summit_guardrail"],
                ],
            ),
        ),
    )


def _cts_gis_reference_guarded_document() -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id="sandbox:cts_gis:sc.reference-guarded.3-2-3-17-77-1.json",
        source_kind="sandbox_source",
        document_name="sc.reference-guarded.3-2-3-17-77-1.json",
        relative_path="sandbox/cts-gis/sources/sc.reference-guarded.3-2-3-17-77-1.json",
        tool_id="cts_gis",
        anchor_document_name="tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
        anchor_document_path="sandbox/cts-gis/tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
        anchor_rows=_anchor_rows(),
        document_metadata={
            "reference_geojson_node_id": "3-2-3-17-77-1",
            "reference_geojson": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [-81.63, 41.01],
                                [-81.57, 41.01],
                                [-81.55, 41.05],
                                [-81.58, 41.08],
                                [-81.63, 41.01],
                            ]],
                        },
                        "properties": {"community_name": "reference_guarded_city"},
                    }
                ],
            },
        },
        rows=(
            AuthoritativeDatumDocumentRow(
                datum_address="4-3-1",
                raw=[
                    [
                        "4-3-1",
                        "rf.3-1-1",
                        "3-76-11-40-92-20-21-92-51-75-26-64-11-48-77-78-73",
                        "rf.3-1-1",
                        "3-76-11-40-92-20-21-92-81-29-56-60-79-56-3-4-39",
                        "rf.3-1-1",
                        "3-76-11-40-92-20-21-92-81-25-68-43-68-84-44-22-24",
                    ],
                    ["reference_guarded_polygon"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="5-0-1",
                raw=[["5-0-1", "~", "4-3-1"], ["reference_guarded_boundary"]],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="7-3-1",
                raw=[
                    [
                        "7-3-1",
                        "rf.3-1-2",
                        "3-2-3-17-77-1",
                        "rf.3-1-3",
                        _ascii_bits("reference_guarded_city"),
                        "5-0-1",
                        "1",
                    ],
                    ["reference_guarded_city"],
                ],
            ),
        ),
    )


def _cts_gis_partial_failure_document() -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id="sandbox:cts_gis:sc.partial-failure.3-2-3-17-77-1.json",
        source_kind="sandbox_source",
        document_name="sc.partial-failure.3-2-3-17-77-1.json",
        relative_path="sandbox/cts-gis/sources/sc.partial-failure.3-2-3-17-77-1.json",
        tool_id="cts_gis",
        anchor_document_name="tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
        anchor_document_path="sandbox/cts-gis/tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
        anchor_rows=_anchor_rows(),
        document_metadata={},
        rows=(
            AuthoritativeDatumDocumentRow(
                datum_address="4-2-1",
                raw=[
                    [
                        "4-2-1",
                        "rf.3-1-1",
                        "3-76-11-40-92-20-21-92-51-75-26-64-11-48-77-78-73",
                        "rf.3-1-1",
                        "3-76-11-40-92-20-21-92-81-29-56-60-79-56-3-4-39",
                    ],
                    ["parent_polygon"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="5-0-1",
                raw=[["5-0-1", "~", "4-2-1"], ["parent_boundary"]],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="7-3-1",
                raw=[
                    ["7-3-1", "rf.3-1-2", "3-2-3-17-77-1", "rf.3-1-3", _ascii_bits("parent"), "5-0-1", "1"],
                    ["parent"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="4-2-2",
                raw=[
                    ["4-2-2", "rf.3-1-1", "INVALID-HOPS", "rf.3-1-1", "INVALID-HOPS-2"],
                    ["child_polygon"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="5-0-2",
                raw=[["5-0-2", "~", "4-2-2"], ["child_boundary"]],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="7-3-2",
                raw=[
                    ["7-3-2", "rf.3-1-2", "3-2-3-17-77-1-1", "rf.3-1-3", _ascii_bits("child"), "5-0-2", "1"],
                    ["child"],
                ],
            ),
        ),
    )


def _simple_polygon_document(
    *,
    document_name: str,
    relative_path: str,
    node_id: str,
    title: str,
    boundary_labels: list[str],
    anchor_rows: tuple[AuthoritativeDatumDocumentRow, ...] | None = None,
) -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id=f"sandbox:cts_gis:{document_name}",
        source_kind="sandbox_source",
        document_name=document_name,
        relative_path=relative_path,
        tool_id="cts_gis",
        anchor_document_name="tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
        anchor_document_path="sandbox/cts-gis/tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
        anchor_rows=anchor_rows or _anchor_rows(),
        rows=(
            AuthoritativeDatumDocumentRow(
                datum_address="4-1-1",
                raw=[
                    [
                        "4-1-1",
                        "rf.3-1-1",
                        "3-76-11-40-92-20-21-92-51-75-26-64-11-48-77-78-73",
                    ],
                    ["polygon_1"],
                ],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="5-0-1",
                raw=[["5-0-1", "~", "4-1-1"], list(boundary_labels)],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="7-3-1",
                raw=[
                    ["7-3-1", "rf.3-1-2", node_id, "rf.3-1-3", _ascii_bits(title), "5-0-1", "1"],
                    [title],
                ],
            ),
        ),
    )


class CtsGisReadOnlyUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        CtsGisReadOnlyService._DOCUMENT_PROJECTION_CACHE.clear()

    def test_builds_attention_first_surface_and_profile_linked_projection(self) -> None:
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(_cts_gis_document(),),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        surface = CtsGisReadOnlyService(store).read_surface("fnd")

        self.assertEqual(surface["map_projection"]["projection_state"], "projectable")
        self.assertEqual(surface["map_projection"]["feature_count"], 1)
        self.assertEqual(surface["map_projection"]["selected_feature"]["geometry_type"], "Polygon")
        self.assertEqual(surface["attention_profile"]["node_id"], "3-2-3-17-77-1")
        self.assertEqual(surface["selected_row"]["datum_address"], "7-3-1")
        self.assertEqual(surface["mediation_state"]["attention_node_id"], "3-2-3-17-77-1")
        self.assertEqual(surface["mediation_state"]["intention_token"], "self")
        self.assertIn("3-2-3-17-77-1-0", [item["token"] for item in surface["mediation_state"]["available_intentions"]])
        self.assertIn(
            "3-2-3-17-77-1-0-0",
            [item["token"] for item in surface["mediation_state"]["available_intentions"]],
        )
        feature_types = [feature["geometry"]["type"] for feature in surface["map_projection"]["feature_collection"]["features"]]
        self.assertEqual(feature_types, ["Polygon"])
        first_feature_props = surface["map_projection"]["feature_collection"]["features"][0]["properties"]
        self.assertEqual(first_feature_props["samras_node_id"], "3-2-3-17-77-1")
        self.assertEqual(first_feature_props["profile_label"], "summit")
        self.assertEqual(
            [item["node_id"] for item in surface["render_profiles"]],
            ["3-2-3-17-77-1"],
        )

        children_surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={
                "attention_node_id": "3-2-3-17-77-1",
                "intention_token": "3-2-3-17-77-1-0",
            },
        )
        named_row = [row for row in children_surface["rows"] if row["datum_address"] == "7-3-2"][0]
        title_overlay = [entry for entry in named_row["overlay_preview"] if entry["overlay_family"] == "title_babelette"][0]
        self.assertEqual(title_overlay["display_value"], "fairlawn")

        bad_row_surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={
                "attention_node_id": "3-2-3-17-77-1-2",
                "intention_token": "self",
            },
        )
        bad_row = [row for row in bad_row_surface["rows"] if row["datum_address"] == "7-3-3"][0]
        bad_title_overlay = [entry for entry in bad_row["overlay_preview"] if entry["overlay_family"] == "title_babelette"][0]
        self.assertEqual(bad_title_overlay["raw_value"], "HERE")
        self.assertEqual(bad_title_overlay["display_value"], "HERE")
        self.assertIn("illegal_magnitude_literal", bad_row["diagnostic_states"])

    def test_children_intention_and_legacy_row_bridge_select_child_profile(self) -> None:
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(_cts_gis_document(),),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        children_surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={
                "attention_node_id": "3-2-3-17-77-1",
                "intention_token": "3-2-3-17-77-1-0",
            },
        )

        self.assertEqual(children_surface["render_set_summary"]["render_mode"], "children")
        self.assertEqual(
            [item["node_id"] for item in children_surface["render_profiles"]],
            ["3-2-3-17-77-1", "3-2-3-17-77-1-1", "3-2-3-17-77-1-2"],
        )
        self.assertEqual(children_surface["attention_profile"]["node_id"], "3-2-3-17-77-1")
        self.assertEqual(children_surface["map_projection"]["feature_count"], 2)
        self.assertEqual(children_surface["children"][0]["node_id"], "3-2-3-17-77-1-1")
        feature_nodes = [
            feature["properties"]["samras_node_id"]
            for feature in children_surface["map_projection"]["feature_collection"]["features"]
        ]
        self.assertEqual(feature_nodes, ["3-2-3-17-77-1", "3-2-3-17-77-1-1"])
        child_feature_props = children_surface["map_projection"]["feature_collection"]["features"][1]["properties"]
        self.assertEqual(child_feature_props["profile_label"], "fairlawn")

        bridged_surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            selected_row_address="7-3-2",
        )
        self.assertEqual(bridged_surface["attention_profile"]["node_id"], "3-2-3-17-77-1-1")
        self.assertEqual(bridged_surface["selected_row"]["datum_address"], "7-3-2")

    def test_branch_intention_renders_attention_plus_target_child_only(self) -> None:
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(_cts_gis_document(),),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={
                "attention_node_id": "3-2-3-17-77-1",
                "intention_token": "branch:3-2-3-17-77-1-1",
            },
        )

        self.assertEqual(surface["render_set_summary"]["render_mode"], "branch")
        self.assertEqual(surface["mediation_state"]["intention_token"], "branch:3-2-3-17-77-1-1")
        self.assertEqual(
            [item["node_id"] for item in surface["render_profiles"]],
            ["3-2-3-17-77-1", "3-2-3-17-77-1-1"],
        )
        self.assertEqual(surface["render_set_summary"]["render_profile_count"], 2)
        self.assertEqual(
            surface["render_set_summary"]["render_feature_count"],
            surface["map_projection"]["feature_count"],
        )
        feature_nodes = [
            feature["properties"]["samras_node_id"]
            for feature in surface["map_projection"]["feature_collection"]["features"]
        ]
        self.assertEqual(feature_nodes, ["3-2-3-17-77-1", "3-2-3-17-77-1-1"])

    def test_time_context_is_exposed_without_changing_navigation_semantics(self) -> None:
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(_cts_gis_document(),),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={
                "attention_node_id": "3-2-3-17-77-1",
                "intention_token": "self",
                "time": {"value": "2026-Q1", "family": "samras-time"},
            },
        )

        self.assertEqual(surface["mediation_state"]["attention_node_id"], "3-2-3-17-77-1")
        self.assertEqual(surface["mediation_state"]["intention_token"], "self")
        self.assertEqual(surface["mediation_state"]["time"]["value_token"], "2026-Q1")
        self.assertEqual(surface["mediation_state"]["time"]["family"], "samras-time")
        self.assertTrue(surface["diagnostic_summary"]["time_context_active"])
        self.assertIn(
            "Time context requested but no chronological anchor space was found",
            " ".join(surface["warnings"]),
        )

    def test_precinct_overlay_gate_failures_are_traceable_when_prereqs_are_missing(self) -> None:
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(_cts_gis_document(),),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={
                "attention_node_id": "3-2-3-17-77-1",
                "intention_token": "self",
                "time": {"value": "2026-Q1", "family": "samras-time"},
                "precinct_district_overlay_enabled": True,
            },
        )

        district_precincts = surface["contextual_references"]["district_precincts"]
        self.assertFalse(district_precincts["overlay_active"])
        self.assertEqual(
            district_precincts["gate_failures"],
            [
                "attention_lineage_unsupported",
                "chronological_anchor_missing",
                "district_timeframe_mismatch",
            ],
        )
        self.assertIn(
            "Precinct overlays require state or county attention lineage under `3-2-3-*`; overlays were skipped.",
            surface["warnings"],
        )
        self.assertIn(
            "Time context `2026-Q1` is outside district timeframe scope; precinct overlays were skipped.",
            surface["warnings"],
        )

    def test_district_collection_summary_stays_deferred_until_overlay_is_enabled(self) -> None:
        county = _simple_polygon_document(
            document_name="sc.synthetic.3-2-3-17-77.json",
            relative_path="sandbox/cts-gis/sources/sc.synthetic.3-2-3-17-77.json",
            node_id="3-2-3-17-77",
            title="synthetic_county",
            boundary_labels=["county_boundary", "24_present-district_31"],
            anchor_rows=_anchor_rows_with_chronology(),
        )
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(county,),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={
                "attention_node_id": "3-2-3-17-77",
                "intention_token": "self",
                "time": {"value": "24_present-district_31", "family": "district-time"},
            },
        )

        district_precincts = surface["contextual_references"]["district_precincts"]
        collections = list(district_precincts.get("collections") or [])

        self.assertFalse(district_precincts["overlay_active"])
        self.assertEqual(district_precincts["collection_count"], 1)
        self.assertEqual(collections[0]["summary_state"], "deferred")
        self.assertEqual(collections[0]["timeframe_token"], "24_present-district_31")
        self.assertEqual(collections[0]["label"], "District 31 · 24 Present")
        self.assertFalse(collections[0]["precinct_count_known"])
        self.assertEqual(collections[0]["member_node_ids"], [])
        self.assertEqual(collections[0]["gate_failures"], [])

    def test_precinct_overlay_activates_when_attention_timeframe_and_anchor_gates_match(self) -> None:
        county = _simple_polygon_document(
            document_name="sc.synthetic.3-2-3-17-77.json",
            relative_path="sandbox/cts-gis/sources/sc.synthetic.3-2-3-17-77.json",
            node_id="3-2-3-17-77",
            title="synthetic_county",
            boundary_labels=["county_boundary", "24_present-district_31"],
            anchor_rows=_anchor_rows_with_chronology(),
        )
        precinct_one = _simple_polygon_document(
            document_name="sc.synthetic.247-17-77-1.json",
            relative_path="sandbox/cts-gis/sources/precincts/sc.synthetic.247-17-77-1.json",
            node_id="247-17-77-1",
            title="precinct_1",
            boundary_labels=["precinct_boundary_1"],
            anchor_rows=_anchor_rows_with_chronology(),
        )
        precinct_two = _simple_polygon_document(
            document_name="sc.synthetic.247-17-77-2.json",
            relative_path="sandbox/cts-gis/sources/precincts/sc.synthetic.247-17-77-2.json",
            node_id="247-17-77-2",
            title="precinct_2",
            boundary_labels=["precinct_boundary_2"],
            anchor_rows=_anchor_rows_with_chronology(),
        )
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(county, precinct_one, precinct_two),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={
                "attention_node_id": "3-2-3-17-77",
                "intention_token": "self",
                "time": {"value": "24_present-district_31", "family": "district-time"},
                "precinct_district_overlay_enabled": True,
            },
        )

        district_precincts = surface["contextual_references"]["district_precincts"]
        render_nodes = [profile["node_id"] for profile in surface["render_profiles"]]

        self.assertTrue(district_precincts["overlay_active"])
        self.assertTrue(district_precincts["supported_attention_lineage"])
        self.assertTrue(district_precincts["chronological_anchor_present"])
        self.assertTrue(district_precincts["timeframe_match"])
        self.assertEqual(district_precincts["gate_failures"], [])
        self.assertEqual(district_precincts["collection_count"], 1)
        collections = list(district_precincts.get("collections") or [])
        self.assertEqual(collections[0]["summary_state"], "loaded")
        self.assertEqual(collections[0]["label"], "District 31 · 24 Present")
        self.assertEqual(collections[0]["precinct_count"], 2)
        self.assertTrue(collections[0]["precinct_count_known"])
        self.assertEqual(
            collections[0]["member_node_ids"],
            ["247-17-77-1", "247-17-77-2"],
        )
        self.assertIn("247-17-77-1", render_nodes)
        self.assertIn("247-17-77-2", render_nodes)
        self.assertEqual(surface["render_set_summary"]["render_profile_count"], 3)
        self.assertEqual(
            surface["render_set_summary"]["render_feature_count"],
            surface["map_projection"]["feature_count"],
        )

    def test_reports_no_authoritative_cts_gis_documents_with_fallback_document(self) -> None:
        system_document = AuthoritativeDatumDocument(
            document_id="system:anthology",
            source_kind="system_anthology",
            document_name="anthology.json",
            relative_path="system/anthology.json",
            rows=(
                AuthoritativeDatumDocumentRow(
                    datum_address="0-0-1",
                    raw=[["0-0-1", "~", "0-0-0"], ["time-ordinal-position"]],
                ),
            ),
        )
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="tff",
                documents=(system_document,),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        surface = CtsGisReadOnlyService(store).read_surface("tff")

        self.assertEqual(surface["document_catalog"], [])
        self.assertEqual(surface["map_projection"]["projection_state"], "no_authoritative_cts_gis_documents")
        self.assertEqual(surface["map_projection"]["feature_count"], 0)
        self.assertEqual(surface["selected_document"]["document_name"], "anthology.json")
        self.assertTrue(surface["warnings"])

    def test_real_summit_county_document_projects_hops_geometry_with_guardrail_diagnostics(self) -> None:
        county_doc = _document_from_source_file(
            _summit_source_path("3-2-3-17-77")
        )
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(county_doc,),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={"attention_node_id": "3-2-3-17-77", "intention_token": "self"},
        )

        self.assertEqual(surface["map_projection"]["projection_source"], "hops")
        self.assertIn(
            surface["map_projection"]["projection_state"],
            {"projectable", "projectable_degraded"},
        )
        binding_count = int(surface["map_projection"]["decode_summary"]["reference_binding_count"])
        decoded_count = int(surface["map_projection"]["decode_summary"]["decoded_coordinate_count"])
        self.assertGreaterEqual(binding_count, 1500)
        self.assertEqual(decoded_count, binding_count)
        self.assertEqual(surface["map_projection"]["decode_summary"]["failed_token_count"], 0)
        if surface["map_projection"]["projection_state"] == "projectable_degraded":
            self.assertIn(
                "semantic_bounds_outside_expected_envelope",
                surface["map_projection"]["fallback_reason_codes"],
            )
            self.assertTrue(surface["map_projection"]["semantic_guardrails"]["triggered"])
        else:
            self.assertFalse(surface["map_projection"]["semantic_guardrails"]["triggered"])
        bounds = surface["map_projection"]["feature_collection"]["bounds"]
        self.assertEqual(len(bounds), 4)
        self.assertLess(bounds[0], bounds[2])
        self.assertLess(bounds[1], bounds[3])
        self.assertGreaterEqual(bounds[0], -180.0)
        self.assertLessEqual(bounds[2], 180.0)
        self.assertGreaterEqual(bounds[1], -90.0)
        self.assertLessEqual(bounds[3], 90.0)

    def test_attention_zero_zero_alias_normalizes_to_address_based_descendants_scope(self) -> None:
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(_cts_gis_document(),),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={
                "attention_node_id": "3-2-3-17-77-1",
                "intention_token": "3-2-3-17-77-1-0-0",
            },
        )

        self.assertEqual(surface["mediation_state"]["attention_node_id"], "3-2-3-17-77-1")
        self.assertEqual(surface["mediation_state"]["intention_token"], "3-2-3-17-77-1-0-0")
        self.assertEqual(surface["render_set_summary"]["render_mode"], "descendants_depth_1_or_2")
        self.assertEqual(
            [item["node_id"] for item in surface["render_profiles"]],
            ["3-2-3-17-77-1", "3-2-3-17-77-1-1", "3-2-3-17-77-1-2"],
        )

    def test_legacy_self_alias_normalizes_to_self(self) -> None:
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(_cts_gis_document(),),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={
                "attention_node_id": "3-2-3-17-77-1",
                "intention_token": "0",
            },
        )

        self.assertEqual(surface["mediation_state"]["intention_token"], "self")
        self.assertEqual(surface["render_set_summary"]["render_mode"], "self")

    def test_real_summit_county_and_community_documents_remain_hops_projectable(self) -> None:
        for node_id in (
            "3-2-3-17-77",
            "3-2-3-17-77-1-1",
            "3-2-3-17-77-1-2",
            "3-2-3-17-77-1-10",
        ):
            with self.subTest(node_id=node_id):
                path = _summit_source_path(node_id)
                doc = _document_from_source_file(path)
                document_id = f"sandbox:cts_gis:{path.name}"
                store = _FakeDatumStore(
                    AuthoritativeDatumDocumentCatalogResult(
                        tenant_id="fnd",
                        documents=(doc,),
                        source_files={},
                        readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
                    )
                )

                surface = CtsGisReadOnlyService(store).read_surface(
                    "fnd",
                    selected_document_id=document_id,
                    mediation_state={
                        "attention_document_id": document_id,
                        "attention_node_id": node_id,
                        "intention_token": "self",
                    },
                )
                projection = surface["map_projection"]
                decode_summary = projection["decode_summary"]
                self.assertEqual(projection["projection_source"], "hops")
                self.assertIn(projection["projection_state"], {"projectable", "projectable_degraded"})
                self.assertGreater(projection["feature_count"], 0)
                self.assertGreater(decode_summary["decoded_coordinate_count"], 0)
                self.assertEqual(decode_summary["failed_token_count"], 0)

    def test_real_summit_3_8_and_3_9_documents_project_with_self_intention(self) -> None:
        for node_id in ("3-2-3-17-77-3-8", "3-2-3-17-77-3-9"):
            with self.subTest(node_id=node_id):
                path = _summit_source_path(node_id)
                doc = _document_from_source_file(path)
                document_id = f"sandbox:cts_gis:{path.name}"
                store = _FakeDatumStore(
                    AuthoritativeDatumDocumentCatalogResult(
                        tenant_id="fnd",
                        documents=(doc,),
                        source_files={},
                        readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
                    )
                )

                surface = CtsGisReadOnlyService(store).read_surface(
                    "fnd",
                    selected_document_id=document_id,
                    mediation_state={
                        "attention_document_id": document_id,
                        "attention_node_id": node_id,
                        "intention_token": "self",
                    },
                )
                projection = surface["map_projection"]
                self.assertEqual(projection["projection_source"], "hops")
                self.assertIn(projection["projection_state"], {"projectable", "projectable_degraded"})
                self.assertGreater(projection["feature_count"], 0)
                self.assertEqual(projection["decode_summary"]["failed_token_count"], 0)

    def test_live_summit_projection_bundle_reports_projectable_documents_after_anchor_repair(self) -> None:
        store = FilesystemSystemDatumStoreAdapter(SUMMIT_DATA_ROOT)
        projection_bundle = CtsGisReadOnlyService(store).read_projection_bundle("fnd")
        projected_by_name = {
            str((document.get("document_summary") or {}).get("document_name") or ""): dict(
                document.get("document_summary") or {}
            )
            for document in list(projection_bundle.get("documents") or [])
        }
        county_summary = projected_by_name["sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77.json"]
        community_summary = projected_by_name["sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-1.json"]
        self.assertIn(county_summary["projection_state"], {"projectable", "projectable_degraded"})
        self.assertGreater(int(county_summary["projectable_feature_count"] or 0), 0)
        self.assertGreater(int(county_summary["profile_count"] or 0), 0)
        self.assertEqual(community_summary["projection_state"], "projectable")
        self.assertGreater(int(community_summary["projectable_feature_count"] or 0), 0)
        self.assertGreater(int(community_summary["profile_count"] or 0), 0)

    def test_live_summit_descendants_scope_overlays_county_and_projectable_descendants(self) -> None:
        store = FilesystemSystemDatumStoreAdapter(SUMMIT_DATA_ROOT)

        surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={
                "attention_node_id": "3-2-3-17-77",
                "intention_token": "3-2-3-17-77-0-0",
            },
        )

        render_profile_nodes = [item["node_id"] for item in surface["render_profiles"]]
        feature_nodes = [
            feature["properties"]["samras_node_id"]
            for feature in surface["map_projection"]["feature_collection"]["features"]
        ]

        self.assertEqual(surface["attention_profile"]["node_id"], "3-2-3-17-77")
        self.assertEqual(surface["mediation_state"]["intention_token"], "3-2-3-17-77-0-0")
        self.assertEqual(surface["render_set_summary"]["render_mode"], "descendants_depth_1_or_2")
        self.assertGreaterEqual(surface["render_set_summary"]["render_profile_count"], 32)
        self.assertEqual(surface["render_set_summary"]["render_feature_count"], 32)
        self.assertEqual(surface["map_projection"]["feature_count"], 32)
        self.assertEqual(surface["map_projection"]["projection_source"], "hops")
        self.assertIn(surface["map_projection"]["projection_state"], {"projectable", "projectable_degraded"})
        self.assertIn("3-2-3-17-77", render_profile_nodes)
        self.assertIn("3-2-3-17-77-1-1", render_profile_nodes)
        self.assertIn("3-2-3-17-77-3-9", render_profile_nodes)
        self.assertIn("3-2-3-17-77", feature_nodes)
        self.assertIn("3-2-3-17-77-1-1", feature_nodes)
        self.assertIn("3-2-3-17-77-3-9", feature_nodes)

    def test_stage_a_stripped_documents_preserve_feature_and_decode_counts_in_audit(self) -> None:
        report_path = (
            REPO_ROOT
            / "docs"
            / "audits"
            / "cts_gis_hops_first_stage_a_2026-04-18.json"
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        rows_by_name = {
            str(row.get("document_name")): row
            for row in list(report.get("documents") or [])
            if isinstance(row, dict)
        }
        stripped_names = list(report.get("stage_a_stripped_documents") or [])
        self.assertTrue(stripped_names)
        for name in stripped_names:
            with self.subTest(document_name=name):
                row = rows_by_name[name]
                before = dict(row.get("projection_with_reference") or {})
                after = dict(row.get("projection_without_reference") or {})
                self.assertEqual(before.get("feature_count"), after.get("feature_count"))
                self.assertEqual(
                    before.get("decoded_coordinate_count"),
                    after.get("decoded_coordinate_count"),
                )
                self.assertEqual(before.get("failed_token_count"), after.get("failed_token_count"))

    def test_reference_geojson_fallback_reports_decode_failure_summary(self) -> None:
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(_cts_gis_reference_fallback_document(),),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={"attention_node_id": "3-2-3-17-77", "intention_token": "self"},
        )

        self.assertEqual(surface["map_projection"]["projection_source"], "reference_geojson_fallback")
        self.assertEqual(surface["map_projection"]["projection_state"], "projectable_fallback")
        self.assertEqual(surface["map_projection"]["decode_summary"]["reference_binding_count"], 4)
        self.assertEqual(surface["map_projection"]["decode_summary"]["decoded_coordinate_count"], 0)
        self.assertEqual(surface["map_projection"]["decode_summary"]["failed_token_count"], 4)
        self.assertEqual(surface["map_projection"]["projection_health"]["state"], "fallback")
        self.assertIn("decode_failure", surface["map_projection"]["fallback_reason_codes"])
        self.assertIn("authority_warning", surface["map_projection"]["fallback_reason_codes"])
        self.assertTrue(surface["map_projection"]["warnings"])
        self.assertIn("reference GeoJSON geometry", " ".join(surface["map_projection"]["warnings"]))

    def test_hops_geometry_remains_authoritative_when_parity_warnings_exist(self) -> None:
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(_cts_gis_reference_guarded_document(),),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={"attention_node_id": "3-2-3-17-77-1", "intention_token": "self"},
        )

        self.assertEqual(surface["map_projection"]["projection_source"], "hops")
        self.assertEqual(surface["map_projection"]["projection_state"], "projectable_degraded")
        self.assertEqual(surface["map_projection"]["feature_count"], 1)
        self.assertEqual(surface["map_projection"]["projection_health"]["state"], "degraded")
        self.assertIn("parity_mismatch", surface["map_projection"]["fallback_reason_codes"])
        self.assertIn("did not align", " ".join(surface["map_projection"]["warnings"]))
        self.assertNotIn("reference GeoJSON geometry", " ".join(surface["map_projection"]["warnings"]))

    def test_partial_polygon_failure_does_not_collapse_descendant_projection(self) -> None:
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(_cts_gis_partial_failure_document(),),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )
        degraded_surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={
                "attention_node_id": "3-2-3-17-77-1",
                "intention_token": "3-2-3-17-77-1-0-0",
            },
        )
        feature_nodes = [
            feature["properties"]["samras_node_id"]
            for feature in degraded_surface["map_projection"]["feature_collection"]["features"]
        ]
        self.assertEqual(degraded_surface["render_set_summary"]["render_mode"], "descendants_depth_1_or_2")
        self.assertEqual(degraded_surface["map_projection"]["projection_state"], "projectable_degraded")
        self.assertEqual(degraded_surface["map_projection"]["projection_health"]["state"], "degraded")
        self.assertGreaterEqual(degraded_surface["map_projection"]["feature_count"], 1)
        self.assertIn("3-2-3-17-77-1", feature_nodes)
        self.assertEqual(
            degraded_surface["map_projection"]["focus_bounds"],
            degraded_surface["map_projection"]["feature_collection"]["bounds"],
        )

        self_surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={
                "attention_node_id": "3-2-3-17-77-1",
                "intention_token": "self",
            },
        )
        self.assertEqual(self_surface["map_projection"]["projection_state"], "projectable")
        self.assertEqual(self_surface["map_projection"]["projection_health"]["state"], "ok")
        self.assertEqual(self_surface["map_projection"]["feature_count"], 1)
        self.assertEqual(
            self_surface["map_projection"]["feature_collection"]["features"][0]["properties"]["samras_node_id"],
            "3-2-3-17-77-1",
        )

    def test_semantic_implausibility_falls_back_to_reference_geojson_when_available(self) -> None:
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(_cts_gis_semantic_guardrail_document(with_reference_geojson=True),),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )
        surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={"attention_node_id": "3-2-3-17-77", "intention_token": "self"},
        )
        projection = surface["map_projection"]
        self.assertEqual(projection["projection_source"], "reference_geojson_fallback")
        self.assertEqual(projection["projection_state"], "projectable_fallback")
        self.assertIn("semantic_bounds_outside_expected_envelope", projection["fallback_reason_codes"])
        self.assertEqual(projection["projection_health"]["state"], "fallback")
        self.assertTrue(projection["semantic_guardrails"]["triggered"])

    def test_semantic_implausibility_without_reference_keeps_hops_as_degraded(self) -> None:
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(_cts_gis_semantic_guardrail_document(with_reference_geojson=False),),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )
        surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            mediation_state={"attention_node_id": "3-2-3-17-77", "intention_token": "self"},
        )
        projection = surface["map_projection"]
        self.assertEqual(projection["projection_source"], "hops")
        self.assertEqual(projection["projection_state"], "projectable_degraded")
        self.assertEqual(projection["projection_health"]["state"], "degraded")
        self.assertGreater(projection["feature_count"], 0)
        self.assertIn("semantic_bounds_outside_expected_envelope", projection["fallback_reason_codes"])
        self.assertTrue(projection["semantic_guardrails"]["triggered"])

    def test_projection_cache_key_changes_when_metadata_changes_without_filesystem_signatures(self) -> None:
        with_reference = _cts_gis_semantic_guardrail_document(with_reference_geojson=True)
        without_reference = _cts_gis_semantic_guardrail_document(with_reference_geojson=False)
        with_key = cts_gis_service._document_projection_cache_key(with_reference, overlay_mode="auto")
        without_key = cts_gis_service._document_projection_cache_key(without_reference, overlay_mode="auto")
        self.assertNotEqual(with_key, without_key)

    def test_invalid_widened_intention_snaps_to_self_with_warning(self) -> None:
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(_cts_gis_document(),),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )
        surface = CtsGisReadOnlyService(store).read_surface(
            "fnd",
            selected_feature_id="sandbox:cts_gis:sc.example.json:7-3-2",
            mediation_state={
                "attention_node_id": "3-2-3-17-77-1",
                "intention_token": "branch:non-existent-node",
            },
        )
        self.assertEqual(surface["mediation_state"]["intention_token"], "self")
        self.assertTrue(surface["mediation_state"]["normalization_warnings"])
        self.assertEqual(surface["diagnostic_summary"]["selected_feature_id"], surface["map_projection"]["selected_feature"]["feature_id"])

    def test_self_intention_with_pinned_document_projects_only_selected_document(self) -> None:
        primary = _cts_gis_document()
        secondary = _cts_gis_reference_fallback_document()
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(primary, secondary),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        with patch(
            "MyCiteV2.packages.modules.cross_domain.cts_gis.service._build_document_projection",
            wraps=cts_gis_service._build_document_projection,
        ) as build_document_projection:
            surface = CtsGisReadOnlyService(store).read_surface(
                "fnd",
                selected_document_id=primary.document_id,
                mediation_state={
                    "attention_document_id": primary.document_id,
                    "attention_node_id": "3-2-3-17-77-1",
                    "intention_token": "self",
                },
            )

        self.assertEqual(build_document_projection.call_count, 1)
        self.assertEqual(surface["selected_document"]["document_id"], primary.document_id)
        self.assertEqual(surface["mediation_state"]["intention_token"], "self")

    def test_widened_intention_projects_full_corpus_for_overlay_scope(self) -> None:
        primary = _cts_gis_document()
        secondary = _cts_gis_reference_fallback_document()
        store = _FakeDatumStore(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd",
                documents=(primary, secondary),
                source_files={},
                readiness_status={"authoritative_catalog": "loaded", "anthology_status": "loaded"},
            )
        )

        with patch(
            "MyCiteV2.packages.modules.cross_domain.cts_gis.service._build_document_projection",
            wraps=cts_gis_service._build_document_projection,
        ) as build_document_projection:
            surface = CtsGisReadOnlyService(store).read_surface(
                "fnd",
                selected_document_id=primary.document_id,
                mediation_state={
                    "attention_document_id": primary.document_id,
                    "attention_node_id": "3-2-3-17-77-1",
                    "intention_token": "3-2-3-17-77-1-0-0",
                },
            )

        self.assertGreaterEqual(build_document_projection.call_count, 1)
        self.assertEqual(surface["mediation_state"]["intention_token"], "3-2-3-17-77-1-0-0")


if __name__ == "__main__":
    unittest.main()
