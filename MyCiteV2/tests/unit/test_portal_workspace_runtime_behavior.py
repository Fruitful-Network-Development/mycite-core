from __future__ import annotations

import json
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import (
    _cts_gis_source_path,
    build_portal_cts_gis_surface_bundle,
    run_portal_cts_gis,
    run_portal_cts_gis_action,
)
from MyCiteV2.instances._shared.runtime.portal_aws_runtime import (
    _project_domain_readiness,
    build_portal_aws_surface_bundle,
    run_portal_aws_csm,
)
from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry
from MyCiteV2.instances._shared.runtime.portal_system_workspace_runtime import (
    build_system_workspace_bundle,
    read_system_workbench_projection,
)
from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.adapters.filesystem.network_root_read_model import build_system_log_document
from MyCiteV2.packages.core.structures.samras import encode_canonical_structure_from_addresses
from MyCiteV2.packages.state_machine.portal_shell import (
    AWS_CSM_TOOL_SURFACE_ID,
    FOCUS_LEVEL_OBJECT,
    FOCUS_LEVEL_SANDBOX,
    NETWORK_ROOT_SURFACE_ID,
    PortalScope,
    SYSTEM_ROOT_SURFACE_ID,
    TRANSITION_BACK_OUT,
    TRANSITION_FOCUS_DATUM,
    TRANSITION_FOCUS_FILE,
    TRANSITION_FOCUS_OBJECT,
    TRANSITION_SET_VERB,
    build_shell_composition_payload,
    UTILITIES_ROOT_SURFACE_ID,
    VERB_MEDIATE,
    VERB_NAVIGATE,
    initial_portal_shell_state,
    reduce_portal_shell_state,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _domain_readiness_payload() -> dict[str, object]:
    return {
        "schema": "mycite.service_tool.aws_csm.domain.v1",
        "identity": {
            "tenant_id": "cvccboard",
            "domain": "cvccboard.org",
            "region": "us-east-1",
            "hosted_zone_id": "Z05968042395KDRPX4PLG",
        },
        "dns": {
            "hosted_zone_present": True,
            "nameserver_match": True,
            "registrar_nameservers": ["ns-1.example.com"],
            "hosted_zone_nameservers": ["ns-1.example.com"],
            "mx_record_present": True,
            "mx_record_values": ["10 inbound-smtp.us-east-1.amazonaws.com"],
            "dkim_records_present": True,
            "dkim_record_values": [
                "token-1.dkim.amazonses.com",
                "token-2.dkim.amazonses.com",
                "token-3.dkim.amazonses.com",
            ],
        },
        "ses": {
            "identity_exists": True,
            "identity_status": "verified",
            "verified_for_sending_status": True,
            "dkim_status": "verified",
            "dkim_tokens": ["token-1", "token-2", "token-3"],
        },
        "receipt": {
            "status": "ok",
            "rule_name": "portal-capture-cvccboard-org",
            "expected_recipient": "cvccboard.org",
            "expected_lambda_name": "newsletter-inbound-capture",
            "bucket": "ses-inbound-fnd-mail",
            "prefix": "inbound/cvccboard.org/",
        },
        "observation": {"last_checked_at": "2026-04-18T00:00:00+00:00"},
    }


def _ascii_bits(text: str) -> str:
    return "".join(format(value, "08b") for value in text.encode("ascii"))


def _cts_gis_valid_addresses() -> list[str]:
    addresses = [str(index) for index in range(1, 9)]
    addresses.extend(f"3-{index}" for index in range(1, 32))
    addresses.extend(f"4-{index}" for index in range(1, 7))
    addresses.extend(f"3-2-{index}" for index in range(1, 4))
    addresses.extend(f"3-2-3-{index}" for index in range(1, 18))
    addresses.extend(f"3-2-3-17-{index}" for index in range(1, 78))
    addresses.append("3-2-3-17-77-1")
    return addresses


def _cts_gis_node_titles() -> dict[str, str]:
    titles = {
        "1": "neg",
        "2": "neh",
        "3": "nwh",
        "4": "nwg",
        "5": "seg",
        "6": "seh",
        "7": "swh",
        "8": "swg",
        "3-1": "united_kingdom",
        "3-2": "united_states_of_america",
        "3-3": "cuba",
        "3-4": "dominican_republic",
        "3-5": "el_salvador",
        "3-6": "haiti",
        "3-7": "nicaragua",
        "3-8": "costa_rica",
        "3-9": "liberia",
        "3-10": "colombia",
        "3-11": "canada",
        "3-12": "panama",
        "3-13": "venezuela",
        "3-14": "honduras",
        "3-15": "iceland",
        "3-16": "ireland",
        "3-17": "portugal",
        "3-18": "spain",
        "3-19": "morocco",
        "3-20": "ghana",
        "3-21": "mali",
        "3-22": "senegal",
        "3-23": "sierra_leone",
        "3-24": "mauritania",
        "3-25": "jamaica",
        "3-26": "trinidad_and_tobago",
        "3-27": "the_gambia",
        "3-28": "guyana",
        "3-29": "bahamas",
        "3-30": "grenada",
        "3-31": "guinea_bissau",
        "4-1": "suriname",
        "4-2": "dominica",
        "4-3": "saint_lucia",
        "4-4": "saint_vincent_grenadines",
        "4-5": "belize",
        "4-6": "saint_kitts_nevis",
        "3-2-1": "free_associate",
        "3-2-2": "insular_area",
        "3-2-3": "states",
        "3-2-3-17": "ohio",
        "3-2-3-17-77": "summit_county",
    }
    for index in range(1, 17):
        titles[f"3-2-3-{index}"] = f"state_{index}"
    for index in range(1, 77):
        titles[f"3-2-3-17-{index}"] = f"county_{index}"
    return titles


def _cts_gis_navigation_row(
    row_index: int,
    *,
    node_id: str,
    title_bits: str,
    label: str,
) -> tuple[str, list[object]]:
    return (
        f"4-2-{row_index}",
        [
            [f"4-1-{row_index}", "rf.3-1-2", node_id, "rf.3-1-3", title_bits],
            [label],
        ],
    )


def _write_cts_gis_profile_source(
    data_dir: Path,
    *,
    node_id: str,
    document_name: str | None = None,
    profile_label: str | None = None,
    extra_payload: dict[str, object] | None = None,
    coordinate_tokens: tuple[str, ...] = (
        "3-76-11-40-92-20-21-92-51-75-26-64-11-48-77-78-73",
        "3-76-11-40-92-20-21-92-81-29-56-60-79-56-3-4-39",
        "3-76-11-40-92-20-21-92-81-25-68-43-68-84-44-22-24",
    ),
) -> None:
    titles = _cts_gis_node_titles()
    label = profile_label or titles.get(node_id, node_id)
    file_name = document_name or f"sc.3-2-3-17-77-1-6-4-1-4.fnd.{node_id}.json"
    coordinate_row_address = f"4-{len(coordinate_tokens)}-1"
    coordinate_row = [coordinate_row_address]
    for token in coordinate_tokens:
        coordinate_row.extend(["rf.3-1-1", token])
    _write_json(
        data_dir / "sandbox" / "cts-gis" / "sources" / file_name,
        {
            **dict(extra_payload or {}),
            "datum_addressing_abstraction_space": {
                coordinate_row_address: [coordinate_row, [f"{label}_polygon"]],
                "5-0-1": [["5-0-1", "~", coordinate_row_address], [f"{label}_boundary"]],
                "7-3-1": [
                    [
                        "7-3-1",
                        "rf.3-1-2",
                        node_id,
                        "rf.3-1-3",
                        _ascii_bits(label),
                        "5-0-1",
                        "1",
                    ],
                    [label],
                ],
            }
        },
    )


def _write_cts_gis_fixture(
    data_dir: Path,
    private_dir: Path,
    *,
    selected_node_projection: str = "3-2-3-17-77",
    extra_projection_nodes: tuple[str, ...] = (),
    duplicate_node_ids: tuple[str, ...] = (),
    outside_node_ids: tuple[str, ...] = (),
    invalid_title_node_ids: tuple[str, ...] = ("3-2-3-17-77-1",),
    magnitude_bitstream: str | None = None,
    cache_magnitude_bitstream: str | None = None,
    anchor_magnitude_bitstream: str | None = None,
) -> None:
    (data_dir / "system").mkdir(parents=True, exist_ok=True)
    (data_dir / "payloads" / "cache").mkdir(parents=True, exist_ok=True)
    (data_dir / "sandbox" / "cts-gis" / "sources").mkdir(parents=True, exist_ok=True)
    (data_dir / "sandbox" / "cts-gis" / "sources" / "precincts").mkdir(parents=True, exist_ok=True)
    (private_dir / "utilities" / "tools" / "cts-gis").mkdir(parents=True, exist_ok=True)
    _write_json(data_dir / "system" / "anthology.json", {"1-0-1": [["1-0-1", "~", "0-0-0"], ["anchor-root"]]})
    _write_json(
        private_dir / "utilities" / "tools" / "cts-gis" / "spec.json",
        {"schema": "mycite.portal.tool_spec.v1", "tool_id": "cts_gis"},
    )

    addresses = _cts_gis_valid_addresses()
    magnitude = magnitude_bitstream or encode_canonical_structure_from_addresses(addresses).bitstream
    cache_magnitude = cache_magnitude_bitstream or magnitude
    anchor_magnitude = anchor_magnitude_bitstream or magnitude
    _write_json(
        data_dir / "payloads" / "cache" / "sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json",
        {
            "schema": "mycite.datum_payload.v1",
            "payload_id": "sc.3-2-3-17-77-1-6-4-1-4.msn-administrative",
            "datum_addressing_abstraction_space": {
                "0-0-5": [["0-0-5", "~", "0-0-0"], ["nominal-ordinal-position"]],
                "1-1-1": [["1-1-1", "0-0-5", cache_magnitude], ["msn-SAMRAS"]],
            },
        },
    )
    _write_json(
        data_dir / "payloads" / "cache" / "sc.3-2-3-17-77-1-6-4-1-4.registrar.json",
        {
            "payload_id": "sc.3-2-3-17-77-1-6-4-1-4.registrar",
            "target_mss_anchor_datum": "5-0-1",
        },
    )
    _write_json(
        data_dir / "sandbox" / "cts-gis" / "tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
        {
            "datum_addressing_abstraction_space": {
                "0-0-11": [["0-0-11", "~", "0-0-0"], ["json-file-unit"]],
                "1-0-1": [["1-0-1", "~", "0-0-11"], ["sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json"]],
                "1-1-2": [["1-1-2", "0-0-5", anchor_magnitude], ["msn-SAMRAS"]],
                "2-0-2": [["2-0-2", "~", "1-1-2"], ["SAMRAS-space-msn"]],
                "2-1-1": [["2-1-1", "1-1-3", "64"], ["niu-baciloid-256-64"]],
                "3-1-1": [["3-1-1", "2-0-2", "0"], ["HOPS-babelette-coordinate"]],
                "3-1-2": [["3-1-2", "2-0-2", "0"], ["SAMRAS-babelette-msn_id"]],
                "3-1-3": [["3-1-3", "2-1-1", "0"], ["title-babelette"]],
            },
        },
    )

    titles = _cts_gis_node_titles()
    row_entries: dict[str, list[object]] = {}
    row_index = 1
    for node_id in addresses:
        if node_id in invalid_title_node_ids:
            title_bits = "HERE"
        else:
            title_bits = _ascii_bits(titles.get(node_id, ""))
        row_key, row_value = _cts_gis_navigation_row(
            row_index,
            node_id=node_id,
            title_bits=title_bits,
            label=titles.get(node_id, node_id),
        )
        row_entries[row_key] = row_value
        row_index += 1
    for node_id in duplicate_node_ids:
        row_key, row_value = _cts_gis_navigation_row(
            row_index,
            node_id=node_id,
            title_bits=_ascii_bits(f"duplicate_{node_id.replace('-', '_')}"),
            label=f"duplicate_{node_id.replace('-', '_')}",
        )
        row_entries[row_key] = row_value
        row_index += 1
    for node_id in outside_node_ids:
        row_key, row_value = _cts_gis_navigation_row(
            row_index,
            node_id=node_id,
            title_bits=_ascii_bits(f"outside_{node_id.replace('-', '_')}"),
            label=f"outside_{node_id.replace('-', '_')}",
        )
        row_entries[row_key] = row_value
        row_index += 1
    _write_json(
        data_dir / "sandbox" / "cts-gis" / "sources" / "sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json",
        {"datum_addressing_abstraction_space": row_entries},
    )
    _write_json(
        data_dir / "sandbox" / "cts-gis" / "sources" / "sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77.json",
        {
            "datum_addressing_abstraction_space": {
                "4-3-1": [[
                    "4-3-1",
                    "rf.3-1-1",
                    "3-76-11-40-92-20-21-92-51-75-26-64-11-48-77-78-73",
                    "rf.3-1-1",
                    "3-76-11-40-92-20-21-92-81-29-56-60-79-56-3-4-39",
                    "rf.3-1-1",
                    "3-76-11-40-92-20-21-92-81-25-68-43-68-84-44-22-24",
                ], ["polygon_1"]],
                "5-0-1": [["5-0-1", "~", "4-3-1"], ["summit_boundary"]],
                "7-3-1": [
                    [
                        "7-3-1",
                        "rf.3-1-2",
                        selected_node_projection,
                        "rf.3-1-3",
                        _ascii_bits("summit_county"),
                        "5-0-1",
                        "1",
                    ],
                    ["summit_county"],
                ],
            }
        },
    )
    for node_id in extra_projection_nodes:
        _write_cts_gis_profile_source(data_dir, node_id=node_id)


def _write_network_chronology_authority(data_dir: Path) -> None:
    (data_dir / "system").mkdir(parents=True, exist_ok=True)
    _write_json(
        data_dir / "system" / "anthology.json",
        {
            "1-1-1": [
                [
                    "1-1-1",
                    "0-0-1",
                    "00000010000110000000110011010101111000011011001100011101111001111101000111110100011111010001011011010111000111100111100",
                ],
                ["HOPS-chronological"],
            ]
        },
    )
    _write_json(
        data_dir / "system" / "sources" / "sc.fnd.quadrennium_cycle.json",
        {
            "datum_addressing_abstraction_space": {
                "1-1-1": [["1-1-1", "rf.0-0-1", "00000100011100000101100100011011111101110110110101110001111001111001111101000"], ["HOPS-quadrennium_cycle"]],
                "2-0-1": [["2-0-1", "~", "1-1-1"], ["HOPS-space-quadrennium"]],
                "3-1-1": [["3-1-1", "2-0-1", "0"], ["HOPS-babelette-quadrennium_cycle"]],
            }
        },
    )


_OUT_OF_SCOPE_CTS_GIS_RUNTIME_TESTS = frozenset(
    {
        "test_tool_runtime_hides_workbench_by_default_and_returns_canonical_url",
        "test_cts_gis_runtime_normalizes_legacy_mediation_keys_into_tool_state_and_mounts_interface_body",
        "test_cts_gis_node_navigation_shell_request_preserves_source_document_pin",
        "test_cts_gis_valid_magnitude_renders_single_root_dropdown_on_initial_load",
        "test_cts_gis_default_runtime_uses_county_root_projection_with_administrative_supporting_document",
        "test_cts_gis_structural_selection_keeps_blank_profile_projection_state",
        "test_cts_gis_selected_node_with_matching_profile_document_populates_garland_from_that_node",
        "test_cts_gis_descendants_intention_overlays_focused_county_and_projectable_descendants",
        "test_cts_gis_descendants_time_context_adds_matching_precinct_profiles",
        "test_cts_gis_runtime_prefers_reference_geometry_when_projection_parity_warnings_exist",
        "test_cts_gis_children_intention_keeps_focused_county_when_no_child_projection_exists",
        "test_cts_gis_branch_intention_overlays_attention_plus_target_child",
        "test_cts_gis_explicit_feature_selection_does_not_replace_attention_focus_bounds",
        "test_cts_gis_invalid_branch_intention_normalizes_to_self",
        "test_cts_gis_duplicate_node_rows_do_not_block_directory_navigation",
        "test_cts_gis_nodes_outside_magnitude_do_not_block_directory_navigation",
        "test_cts_gis_invalid_cache_magnitude_falls_back_to_valid_tool_anchor",
        "test_cts_gis_drifted_decodable_magnitude_is_overridden_by_reconstructed_authority",
        "test_cts_gis_invalid_magnitude_blocks_without_fabricated_dropdown_tree",
    }
)


class PortalWorkspaceRuntimeBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        if self._testMethodName in _OUT_OF_SCOPE_CTS_GIS_RUNTIME_TESTS:
            self.skipTest("Out of scope for shell unification closeout: CTS-GIS compiled-state/navigation runtime behavior.")

    def test_cts_gis_source_path_prefers_precinct_subdirectory_when_present(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            source_root = data_dir / "sandbox" / "cts-gis" / "sources"
            precinct_root = source_root / "precincts"
            precinct_root.mkdir(parents=True, exist_ok=True)
            _write_json(precinct_root / "sc.precinct.json", {"datum_addressing_abstraction_space": {}})

            resolved = _cts_gis_source_path(data_dir, document_name="sc.precinct.json")

            self.assertEqual(resolved, precinct_root / "sc.precinct.json")

    def test_mediation_transition_opens_interface_panel_and_back_out_clears_removed_subject(self) -> None:
        scope = {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]}
        state = initial_portal_shell_state(surface_id=SYSTEM_ROOT_SURFACE_ID, portal_scope=scope)
        datum_state = reduce_portal_shell_state(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope=scope,
            current_state=state,
            transition={"kind": TRANSITION_FOCUS_DATUM, "file_key": "anthology", "datum_id": "1-1-1"},
            seed_anchor_file=False,
        )
        object_state = reduce_portal_shell_state(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope=scope,
            current_state=datum_state,
            transition={"kind": TRANSITION_FOCUS_OBJECT, "file_key": "anthology", "datum_id": "1-1-1", "object_id": "1-0-0"},
            seed_anchor_file=False,
        )
        mediation_state = reduce_portal_shell_state(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope=scope,
            current_state=object_state,
            transition={"kind": TRANSITION_SET_VERB, "verb": VERB_MEDIATE},
            seed_anchor_file=False,
        )
        self.assertEqual(mediation_state.verb, VERB_MEDIATE)
        self.assertTrue(mediation_state.chrome.interface_panel_open)
        self.assertEqual(mediation_state.mediation_subject, {"level": FOCUS_LEVEL_OBJECT, "id": "1-0-0"})

        backed_out = reduce_portal_shell_state(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope=scope,
            current_state=mediation_state,
            transition={"kind": TRANSITION_BACK_OUT},
            seed_anchor_file=False,
        )
        self.assertEqual(backed_out.verb, VERB_NAVIGATE)
        self.assertFalse(backed_out.chrome.interface_panel_open)
        self.assertIsNone(backed_out.mediation_subject)

    def test_tool_runtime_hides_workbench_by_default_and_returns_canonical_url(self) -> None:
        bundle = build_portal_cts_gis_surface_bundle(
            portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
            shell_state=initial_portal_shell_state(
                surface_id="system.tools.cts_gis",
                portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
            ),
            data_dir=None,
        )
        self.assertFalse(bundle["workbench"]["visible"])
        self.assertEqual(bundle["surface_payload"]["tool_state"]["aitas"]["attention_node_id"], "")
        self.assertEqual(bundle["surface_payload"]["tool_state"]["active_path"], [])
        self.assertEqual(bundle["surface_payload"]["tool_state"]["selected_node_id"], "")
        self.assertEqual(
            bundle["surface_payload"]["tool_state"]["aitas"]["intention_rule_id"],
            "descendants_depth_1_or_2",
        )
        self.assertEqual(bundle["surface_payload"]["source_evidence"]["readiness"]["state"], "no_authoritative_cts_gis_documents")
        interface_body = bundle["inspector"]["interface_body"]
        self.assertNotIn("kind", interface_body)
        self.assertIn("navigation_canvas", interface_body)
        self.assertIn("garland_split_projection", interface_body)
        self.assertEqual(interface_body["tab_host"], "shared_interface_tabs")
        self.assertEqual(interface_body["default_tab_id"], "diktataograph")
        self.assertEqual(
            [tab["id"] for tab in interface_body["tabs"]],
            ["diktataograph", "garland"],
        )
        self.assertEqual(interface_body["navigation_canvas"]["title"], "Diktataograph")
        self.assertEqual(
            interface_body["garland_split_projection"]["geospatial_projection"]["title"],
            "Geospatial Projection",
        )
        self.assertEqual(
            interface_body["garland_split_projection"]["profile_projection"]["title"],
            "Profile Projection",
        )
        self.assertEqual(interface_body["layout"], "diktataograph_garland_split")
        self.assertEqual(interface_body["narrow_layout"], "diktataograph_garland_stack")
        self.assertEqual(interface_body["navigation_canvas"]["mode"], "directory_dropdowns")
        self.assertEqual(interface_body["navigation_canvas"]["decode_state"], "blocked_invalid_magnitude")
        self.assertEqual(interface_body["navigation_canvas"]["source_authority"], "samras_magnitude")
        self.assertEqual(interface_body["navigation_canvas"]["dropdowns"], [])
        self.assertEqual(interface_body["navigation_canvas"]["active_path"], [])
        self.assertNotIn("context_strip", interface_body)
        self.assertEqual(
            interface_body["garland_split_projection"]["geospatial_projection"]["data_source"],
            "",
        )
        self.assertFalse(interface_body["garland_split_projection"]["geospatial_projection"]["has_real_projection"])
        self.assertFalse(interface_body["garland_split_projection"]["profile_projection"]["has_real_projection"])
        self.assertIn(
            "geospatial_projection",
            interface_body["garland_split_projection"],
        )
        self.assertIn(
            "profile_projection",
            interface_body["garland_split_projection"],
        )
        self.assertIn(
            "empty_message",
            interface_body["garland_split_projection"]["geospatial_projection"],
        )
        self.assertEqual(
            [group["title"] for group in bundle["control_panel"]["groups"][:3]],
            ["STATE DIRECTIVE"],
        )
        self.assertNotIn("Attention", [group["title"] for group in bundle["control_panel"]["groups"]])
        runtime_diagnostics = dict(bundle["surface_payload"].get("runtime_diagnostics") or {})
        self.assertIn("phase_timings_ms", runtime_diagnostics)
        self.assertIn("total_bundle_build", dict(runtime_diagnostics.get("phase_timings_ms") or {}))
        self.assertIn("service_surface_read", dict(runtime_diagnostics.get("phase_timings_ms") or {}))
        self.assertIn("navigation_canvas", dict(runtime_diagnostics.get("phase_timings_ms") or {}))
        self.assertGreaterEqual(float(dict(runtime_diagnostics.get("phase_timings_ms") or {}).get("total_bundle_build") or 0.0), 0.0)

        envelope = run_portal_cts_gis(
            {
                "schema": "mycite.v2.portal.system.tools.cts_gis.request.v1",
                "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
            },
            data_dir=None,
        )
        self.assertEqual(envelope["surface_id"], "system.tools.cts_gis")
        self.assertTrue(envelope["reducer_owned"])
        self.assertEqual(envelope["canonical_query"]["file"], "anthology")
        self.assertEqual(envelope["canonical_query"]["verb"], "mediate")
        self.assertEqual(envelope["canonical_url"], "/portal/system/tools/cts-gis?file=anthology&verb=mediate")
        self.assertEqual(
            envelope["surface_payload"]["tool_state"]["aitas"]["intention_rule_id"],
            "descendants_depth_1_or_2",
        )

    def test_aws_tool_runtime_keeps_workbench_hidden_on_first_shell_composition(self) -> None:
        bundle = build_portal_aws_surface_bundle(
            surface_id="system.tools.aws_csm",
            portal_scope=PortalScope(scope_id="fnd", capabilities=("fnd_peripheral_routing",)),
            shell_state=None,
            surface_query=None,
            private_dir=None,
        )
        self.assertFalse(bundle["workbench"]["visible"])
        self.assertEqual(bundle["control_panel"]["family_contract"]["family"], "directive_panel")
        self.assertEqual(bundle["workbench"]["family_contract"]["family"], "reflective_workspace")
        self.assertEqual(bundle["inspector"]["family_contract"]["family"], "presentation_surface")

        envelope = run_portal_shell_entry(
            {
                "schema": "mycite.v2.portal.shell.request.v1",
                "requested_surface_id": "system.tools.aws_csm",
                "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            },
            portal_instance_id="fnd",
            portal_domain="fruitfulnetworkdevelopment.com",
            data_dir=None,
            public_dir=None,
            private_dir=None,
            audit_storage_file=None,
            webapps_root=None,
            tool_exposure_policy=None,
        )
        composition = envelope["shell_composition"]
        self.assertTrue(composition["workbench_collapsed"])
        self.assertFalse(composition["interface_panel_collapsed"])
        self.assertEqual(composition["foreground_shell_region"], "interface-panel")
        self.assertFalse(composition["regions"]["workbench"]["visible"])
        self.assertEqual(composition["regions"]["interface_panel"], composition["regions"]["inspector"])
        self.assertEqual(composition["regions"]["control_panel"]["family_contract"]["family"], "directive_panel")
        self.assertEqual(composition["regions"]["workbench"]["family_contract"]["family"], "reflective_workspace")
        self.assertEqual(composition["regions"]["interface_panel"]["family_contract"]["family"], "presentation_surface")

    def test_direct_aws_csm_endpoint_matches_shell_runtime_envelope(self) -> None:
        request_payload = {
            "schema": "mycite.v2.portal.system.tools.aws_csm.request.v1",
            "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            "surface_query": {
                "domain": "FruitfulNetworkDevelopment.com",
                "section": "newsletter",
            },
        }

        direct_envelope = run_portal_aws_csm(
            request_payload,
            private_dir=None,
            tool_exposure_policy=None,
            portal_instance_id="fnd",
            portal_domain="fruitfulnetworkdevelopment.com",
        )
        shell_envelope = run_portal_shell_entry(
            {
                "schema": "mycite.v2.portal.shell.request.v1",
                "requested_surface_id": "system.tools.aws_csm",
                "portal_scope": request_payload["portal_scope"],
                "surface_query": request_payload["surface_query"],
            },
            portal_instance_id="fnd",
            portal_domain="fruitfulnetworkdevelopment.com",
            data_dir=None,
            public_dir=None,
            private_dir=None,
            audit_storage_file=None,
            webapps_root=None,
            tool_exposure_policy=None,
        )

        self.assertEqual(direct_envelope, shell_envelope)

    def test_aws_csm_domain_readiness_projects_identity_missing(self) -> None:
        payload = _domain_readiness_payload()
        payload["ses"]["identity_exists"] = False
        payload["ses"]["identity_status"] = "not_started"
        payload["ses"]["dkim_status"] = "not_started"
        payload["dns"]["mx_record_present"] = True
        payload["dns"]["dkim_records_present"] = False

        readiness = _project_domain_readiness(payload)

        self.assertEqual(readiness["state"], "identity_missing")
        self.assertIn("SES domain identity has not been created yet.", readiness["blockers"])

    def test_aws_csm_domain_readiness_projects_dns_pending(self) -> None:
        payload = _domain_readiness_payload()
        payload["dns"]["dkim_records_present"] = False
        payload["dns"]["dkim_record_values"] = []
        payload["ses"]["identity_status"] = "pending"
        payload["ses"]["dkim_status"] = "pending"

        readiness = _project_domain_readiness(payload)

        self.assertEqual(readiness["state"], "dns_pending")
        self.assertIn("The SES DKIM CNAME records are incomplete in Route 53.", readiness["blockers"])

    def test_aws_csm_domain_readiness_projects_receipt_pending(self) -> None:
        payload = _domain_readiness_payload()
        payload["receipt"]["status"] = "not_ready"

        readiness = _project_domain_readiness(payload)

        self.assertEqual(readiness["state"], "receipt_pending")
        self.assertIn("The bare-domain receipt rule is not configured yet.", readiness["blockers"])

    def test_aws_csm_domain_readiness_projects_ready_for_mailboxes(self) -> None:
        readiness = _project_domain_readiness(_domain_readiness_payload())

        self.assertEqual(readiness["state"], "ready_for_mailboxes")
        self.assertEqual(readiness["blockers"], [])

    def test_shell_composition_builder_owns_root_and_tool_visibility_defaults(self) -> None:
        root_composition = build_shell_composition_payload(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_instance_id="fnd",
            page_title="System",
            page_subtitle="",
            activity_items=[],
            control_panel={},
            workbench={},
            inspector={},
            shell_state=initial_portal_shell_state(
                surface_id=SYSTEM_ROOT_SURFACE_ID,
                portal_scope={"scope_id": "fnd", "capabilities": []},
            ),
        )
        self.assertFalse(root_composition["workbench_collapsed"])
        self.assertTrue(root_composition["interface_panel_collapsed"])
        self.assertEqual(root_composition["regions"]["interface_panel"], root_composition["regions"]["inspector"])

        aws_tool_composition = build_shell_composition_payload(
            active_surface_id=AWS_CSM_TOOL_SURFACE_ID,
            portal_instance_id="fnd",
            page_title="AWS-CSM",
            page_subtitle="",
            activity_items=[],
            control_panel={},
            workbench={},
            inspector={},
            shell_state=None,
        )
        self.assertTrue(aws_tool_composition["workbench_collapsed"])
        self.assertFalse(aws_tool_composition["interface_panel_collapsed"])
        self.assertEqual(aws_tool_composition["foreground_shell_region"], "interface-panel")
        self.assertTrue(aws_tool_composition["regions"]["inspector"]["primary_surface"])
        self.assertEqual(aws_tool_composition["regions"]["inspector"]["layout_mode"], "dominant")
        self.assertEqual(
            aws_tool_composition["regions"]["interface_panel"],
            aws_tool_composition["regions"]["inspector"],
        )

        evidence_composition = build_shell_composition_payload(
            active_surface_id=AWS_CSM_TOOL_SURFACE_ID,
            portal_instance_id="fnd",
            page_title="AWS-CSM",
            page_subtitle="",
            activity_items=[],
            control_panel={},
            workbench={"visible": True},
            inspector={},
            shell_state=None,
        )
        self.assertTrue(evidence_composition["workbench_collapsed"])
        self.assertEqual(evidence_composition["foreground_shell_region"], "interface-panel")

    def test_cts_gis_query_widening_is_ignored_at_shell_entry(self) -> None:
        envelope = run_portal_shell_entry(
            {
                "schema": "mycite.v2.portal.shell.request.v1",
                "requested_surface_id": "system.tools.cts_gis",
                "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                "surface_query": {"record": "7-3-1", "view": "system_logs", "type": "unexpected"},
            },
            portal_instance_id="fnd",
            portal_domain="fruitfulnetworkdevelopment.com",
            data_dir=None,
            public_dir=None,
            private_dir=None,
            audit_storage_file=None,
            webapps_root=None,
            tool_exposure_policy=None,
        )
        self.assertEqual(envelope["surface_id"], "system.tools.cts_gis")
        self.assertEqual(envelope["canonical_query"]["file"], "anthology")
        self.assertEqual(envelope["canonical_query"]["verb"], "mediate")
        self.assertNotIn("record", envelope["canonical_query"])
        self.assertNotIn("type", envelope["canonical_query"])
        self.assertNotIn("view", envelope["canonical_query"])

    def test_cts_gis_runtime_normalizes_legacy_mediation_keys_into_tool_state_and_mounts_interface_body(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(data_dir, private_dir)

            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={
                    "mediation_state": {
                        "attention_document_id": "sandbox:cts_gis:sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json",
                        "attention_node_id": "3-2-3-17-77",
                        "intention_token": "descendants_depth_1_or_2",
                    }
                },
            )

            self.assertEqual(bundle["surface_payload"]["tool_state"]["source"]["attention_document_id"], "sandbox:cts_gis:sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json")
            self.assertEqual(bundle["surface_payload"]["tool_state"]["aitas"]["attention_node_id"], "3-2-3-17-77")
            self.assertEqual(
                bundle["surface_payload"]["tool_state"]["active_path"],
                ["3", "3-2", "3-2-3", "3-2-3-17", "3-2-3-17-77"],
            )
            self.assertEqual(bundle["surface_payload"]["tool_state"]["aitas"]["intention_rule_id"], "3-2-3-17-77-0-0")
            self.assertEqual(bundle["surface_payload"]["source_evidence"]["readiness"]["state"], "ready")
            self.assertEqual(bundle["inspector"]["interface_body"]["layout"], "diktataograph_garland_split")
            self.assertEqual(bundle["inspector"]["interface_body"]["narrow_layout"], "diktataograph_garland_stack")
            self.assertNotIn("kind", bundle["inspector"]["interface_body"])
            self.assertIn("navigation_canvas", bundle["inspector"]["interface_body"])
            self.assertIn("garland_split_projection", bundle["inspector"]["interface_body"])
            self.assertEqual(bundle["inspector"]["interface_body"]["tab_host"], "shared_interface_tabs")
            self.assertEqual(bundle["inspector"]["interface_body"]["default_tab_id"], "diktataograph")
            self.assertEqual(
                [tab["id"] for tab in bundle["inspector"]["interface_body"]["tabs"]],
                ["diktataograph", "garland"],
            )
            self.assertEqual(
                bundle["inspector"]["interface_body"]["navigation_canvas"]["mode"],
                "directory_dropdowns",
            )
            self.assertEqual(
                bundle["inspector"]["interface_body"]["navigation_canvas"]["decode_state"],
                "ready",
            )
            self.assertEqual(
                len(bundle["inspector"]["interface_body"]["navigation_canvas"]["dropdowns"]),
                6,
            )
            self.assertEqual(
                [entry["node_id"] for entry in bundle["inspector"]["interface_body"]["navigation_canvas"]["active_path"]],
                ["3", "3-2", "3-2-3", "3-2-3-17", "3-2-3-17-77"],
            )
            self.assertIn(
                "geospatial_projection",
                bundle["inspector"]["interface_body"]["garland_split_projection"],
            )
            self.assertIn(
                "profile_projection",
                bundle["inspector"]["interface_body"]["garland_split_projection"],
            )
            self.assertIn("STATE DIRECTIVE", [group["title"] for group in bundle["control_panel"]["groups"]])
            self.assertNotIn("Source Evidence", [group["title"] for group in bundle["control_panel"]["groups"]])
            geo = bundle["inspector"]["interface_body"]["garland_split_projection"]["geospatial_projection"]
            self.assertIn("empty_message", geo)
            self.assertIn("features", geo)
            self.assertIn("projection_state", geo)
            self.assertIn("feature_collection", geo)
            self.assertIn(
                "active_profile",
                bundle["inspector"]["interface_body"]["garland_split_projection"]["profile_projection"],
            )
            self.assertIn(
                "hierarchy",
                bundle["inspector"]["interface_body"]["garland_split_projection"]["profile_projection"],
            )
            self.assertNotIn("context_strip", bundle["inspector"]["interface_body"])
            self.assertEqual(
                bundle["inspector"]["interface_body"]["navigation_canvas"]["dropdowns"][0]["options"][0]["display_label"],
                "1 NEG",
            )

            envelope = run_portal_shell_entry(
                {
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": "system.tools.cts_gis",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                    "tool_state": {
                        "aitas": {
                            "attention_node_id": "3-2-3-17-77",
                            "intention_rule_id": "descendants_depth_1_or_2",
                        }
                    },
                },
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                data_dir=data_dir,
                public_dir=None,
                private_dir=private_dir,
                audit_storage_file=None,
                webapps_root=None,
                tool_exposure_policy=None,
            )
            self.assertEqual(
                envelope["surface_payload"]["tool_state"]["aitas"]["attention_node_id"],
                "3-2-3-17-77",
            )
            self.assertEqual(
                envelope["surface_payload"]["tool_state"]["aitas"]["intention_rule_id"],
                "3-2-3-17-77-0-0",
            )
            self.assertNotIn("kind", envelope["shell_composition"]["regions"]["inspector"]["interface_body"])
            self.assertTrue(envelope["shell_composition"]["workbench_collapsed"])
            self.assertFalse(envelope["shell_composition"]["interface_panel_collapsed"])

    def test_cts_gis_node_navigation_shell_request_preserves_source_document_pin(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(
                data_dir,
                private_dir,
                extra_projection_nodes=("3-2-3",),
            )
            pinned_document_id = "sandbox:cts_gis:sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json"

            pinned_bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={
                    "tool_state": {
                        "source": {"attention_document_id": pinned_document_id},
                        "aitas": {
                            "attention_node_id": "3-2-3-17-77",
                            "intention_rule_id": "self",
                        },
                    }
                },
            )

            self.assertEqual(
                pinned_bundle["surface_payload"]["tool_state"]["source"]["attention_document_id"],
                pinned_document_id,
            )
            navigation_canvas = pinned_bundle["inspector"]["interface_body"]["navigation_canvas"]
            option_for_state_node = next(
                option
                for dropdown in navigation_canvas["dropdowns"]
                for option in dropdown["options"]
                if option["node_id"] == "3-2-3"
            )
            node_shell_request = option_for_state_node["shell_request"]
            self.assertEqual(
                node_shell_request["tool_state"]["source"]["attention_document_id"],
                pinned_document_id,
            )

            navigated_bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={"tool_state": node_shell_request["tool_state"]},
            )

            self.assertEqual(
                navigated_bundle["surface_payload"]["tool_state"]["source"]["attention_document_id"],
                pinned_document_id,
            )
            summary_by_label = {
                row["label"]: row["value"]
                for row in navigated_bundle["inspector"]["interface_body"]["garland_split_projection"]["profile_projection"]["summary_rows"]
            }
            self.assertEqual(summary_by_label["Projection state"], "awaiting_real_projection")

    def test_cts_gis_intention_shell_request_preserves_source_document_pin(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(data_dir, private_dir)
            pinned_document_id = "sandbox:cts_gis:sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json"

            pinned_bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={
                    "tool_state": {
                        "source": {"attention_document_id": pinned_document_id},
                        "aitas": {
                            "attention_node_id": "3-2-3-17-77",
                            "intention_rule_id": "self",
                        },
                    }
                },
            )

            aitas_group = next(
                group
                for group in pinned_bundle["control_panel"]["groups"]
                if group["title"] == "STATE DIRECTIVE"
            )
            descendants_entry = next(
                entry
                for entry in aitas_group["entries"]
                if entry.get("prefix") == "3-2-3-17-77-0-0"
            )
            intention_shell_request = descendants_entry["shell_request"]
            self.assertEqual(
                intention_shell_request["tool_state"]["source"]["attention_document_id"],
                pinned_document_id,
            )

            descendants_bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={"tool_state": intention_shell_request["tool_state"]},
            )

            self.assertEqual(
                descendants_bundle["surface_payload"]["tool_state"]["source"]["attention_document_id"],
                pinned_document_id,
            )
            self.assertEqual(
                descendants_bundle["surface_payload"]["tool_state"]["aitas"]["intention_rule_id"],
                "3-2-3-17-77-0-0",
            )

    def test_cts_gis_state_directive_group_contains_attention_intention_time_controls(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(data_dir, private_dir)

            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={"tool_state": {"selected_node_id": "3-2-3-17-77"}},
            )

            state_group = next(group for group in bundle["control_panel"]["groups"] if group["title"] == "STATE DIRECTIVE")
            labels = [entry["label"] for entry in state_group["entries"]]
            self.assertIn("NIMM directive", labels)
            self.assertTrue(any(label.startswith("Attention · ") for label in labels))
            self.assertTrue(any(label.startswith("Intention · ") for label in labels))
            self.assertNotIn("Tool posture", labels)
            self.assertIn("Time · 4-447-751-507-819", labels)
            self.assertIn("NAV", labels)
            self.assertIn("INV", labels)
            self.assertIn("MED", labels)
            self.assertIn("MAN", labels)
            intention_entries = [entry for entry in state_group["entries"] if entry["label"].startswith("Intention · ")]
            self.assertTrue(all(isinstance(entry.get("shell_request"), dict) for entry in intention_entries))
            self.assertEqual(bundle["control_panel"]["verb_tabs"], [])

    def test_cts_gis_state_directive_time_shell_request_updates_time_context(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(data_dir, private_dir)

            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
            )

            state_directive_group = next(
                group
                for group in bundle["control_panel"]["groups"]
                if group["title"] == "STATE DIRECTIVE"
            )
            time_today_entry = next(
                entry
                for entry in state_directive_group["entries"]
                if entry["label"] == "Time · 4-447-751-507-819"
            )
            source_shell_request = time_today_entry["shell_request"]
            self.assertEqual(
                source_shell_request["tool_state"]["aitas"]["time_directive"],
                "4-447-751-507-819",
            )

            selected_bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={"tool_state": source_shell_request["tool_state"]},
            )

            self.assertEqual(
                selected_bundle["surface_payload"]["tool_state"]["aitas"]["time_directive"],
                "4-447-751-507-819",
            )

    def test_cts_gis_default_runtime_uses_county_root_projection_with_administrative_supporting_document(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(data_dir, private_dir)

            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={
                    "tool_state": {
                        "aitas": {
                            "attention_node_id": "3-2-3-17-77",
                            "intention_rule_id": "self",
                        }
                    }
                },
            )

            self.assertEqual(bundle["surface_payload"]["tool_state"]["aitas"]["attention_node_id"], "3-2-3-17-77")
            self.assertEqual(
                bundle["surface_payload"]["tool_state"]["active_path"],
                ["3", "3-2", "3-2-3", "3-2-3-17", "3-2-3-17-77"],
            )
            interface_body = bundle["inspector"]["interface_body"]
            navigation_canvas = interface_body["navigation_canvas"]
            garland = interface_body["garland_split_projection"]
            self.assertEqual(navigation_canvas["mode"], "directory_dropdowns")
            self.assertEqual(navigation_canvas["decode_state"], "ready")
            self.assertEqual(len(navigation_canvas["dropdowns"]), 6)
            self.assertEqual(garland["profile_projection"]["active_profile"]["node_id"], "3-2-3-17-77")
            self.assertTrue(garland["geospatial_projection"]["feature_collection"]["features"])
            self.assertGreater(garland["geospatial_projection"]["feature_count"], 0)
            self.assertEqual(
                garland["geospatial_projection"]["data_source"],
                "cts_gis_polygon_projection",
            )
            self.assertEqual(garland["geospatial_projection"]["projection_source"], "hops")
            self.assertEqual(garland["geospatial_projection"]["decode_summary"]["failed_token_count"], 0)
            ordered_path_ids = [entry["node_id"] for entry in navigation_canvas["active_path"]]
            self.assertEqual(
                ordered_path_ids[:5],
                ["3", "3-2", "3-2-3", "3-2-3-17", "3-2-3-17-77"],
            )
            blank_child_dropdown = navigation_canvas["dropdowns"][-1]
            blank_child_entry = next(
                entry
                for entry in blank_child_dropdown["options"]
                if entry["node_id"] == "3-2-3-17-77-1"
            )
            self.assertEqual(blank_child_entry["title"], "")
            summary_by_label = {
                row["label"]: row["value"]
                for row in garland["profile_projection"]["summary_rows"]
            }
            self.assertEqual(
                summary_by_label["Supporting document"],
                "sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json",
            )
            self.assertEqual(
                summary_by_label["Projection document"],
                "sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77.json",
            )
            self.assertEqual(summary_by_label["Projection source"], "hops")
            self.assertIn(summary_by_label["Projection state"], {"projectable", "projectable_degraded"})
            self.assertEqual(
                summary_by_label["Decode summary"],
                "3/3 decoded · 0 failed",
            )

    def test_cts_gis_valid_magnitude_renders_single_root_dropdown_on_initial_load(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(data_dir, private_dir)

            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
            )

            tool_state = bundle["surface_payload"]["tool_state"]
            navigation_canvas = bundle["inspector"]["interface_body"]["navigation_canvas"]
            geo = bundle["inspector"]["interface_body"]["garland_split_projection"]["geospatial_projection"]
            self.assertEqual(navigation_canvas["decode_state"], "ready")
            self.assertEqual(tool_state["selected_node_id"], "3-2-3-17-77")
            self.assertEqual(
                tool_state["active_path"],
                ["3", "3-2", "3-2-3", "3-2-3-17", "3-2-3-17-77"],
            )
            self.assertEqual(tool_state["aitas"]["intention_rule_id"], "self")
            self.assertEqual(len(navigation_canvas["dropdowns"]), 6)
            self.assertEqual(
                [entry["node_id"] for entry in navigation_canvas["active_path"]],
                ["3", "3-2", "3-2-3", "3-2-3-17", "3-2-3-17-77"],
            )
            self.assertEqual(geo["projection_source"], "hops")
            self.assertEqual(geo["decode_summary"]["failed_token_count"], 0)
            self.assertEqual(
                [option["display_label"] for option in navigation_canvas["dropdowns"][0]["options"][:4]],
                ["1 NEG", "2 NEH", "3 NWH", "4 NWG"],
            )

    def test_cts_gis_structural_selection_keeps_blank_profile_projection_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(data_dir, private_dir)

            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={"tool_state": {"selected_node_id": "3-2"}},
            )

            garland = bundle["inspector"]["interface_body"]["garland_split_projection"]
            self.assertFalse(garland["geospatial_projection"]["has_real_projection"])
            profile = garland["profile_projection"]
            self.assertFalse(profile["has_real_projection"])
            self.assertTrue(profile["has_profile_state"])
            self.assertEqual(profile["active_profile"]["node_id"], "3-2")
            self.assertEqual(profile["active_profile"]["label"], "united_states_of_america")
            self.assertEqual(
                [entry["node_id"] for entry in profile["hierarchy"]],
                ["3", "3-2"],
            )
            self.assertNotIn("projected_rows", profile)
            self.assertNotIn("correlated_profiles", profile)
            summary_by_label = {
                row["label"]: row["value"]
                for row in profile["summary_rows"]
            }
            self.assertEqual(
                summary_by_label["Supporting document"],
                "sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json",
            )
            self.assertEqual(summary_by_label["Projection document"], "—")
            self.assertEqual(summary_by_label["Projection source"], "none")
            self.assertEqual(summary_by_label["Projection state"], "awaiting_real_projection")
            self.assertEqual(
                bundle["surface_payload"]["tool_state"]["aitas"]["intention_rule_id"],
                "self",
            )

    def test_cts_gis_selected_node_with_matching_profile_document_populates_garland_from_that_node(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(
                data_dir,
                private_dir,
                extra_projection_nodes=("3-2-3",),
            )

            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={"tool_state": {"selected_node_id": "3-2-3"}},
            )

            garland = bundle["inspector"]["interface_body"]["garland_split_projection"]
            profile = garland["profile_projection"]
            geo = garland["geospatial_projection"]
            self.assertTrue(profile["has_real_projection"])
            self.assertTrue(geo["has_real_projection"])
            self.assertEqual(profile["active_profile"]["node_id"], "3-2-3")
            self.assertEqual(profile["active_profile"]["label"], "states")
            self.assertNotIn("projected_rows", profile)
            self.assertNotIn("correlated_profiles", profile)
            self.assertGreater(profile["active_profile"]["feature_count"], 0)
            summary_by_label = {row["label"]: row["value"] for row in profile["summary_rows"]}
            self.assertEqual(
                summary_by_label["Projection document"],
                "sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3.json",
            )
            self.assertEqual(summary_by_label["Projection source"], "hops")
            self.assertEqual(summary_by_label["Projection state"], "projectable")
            self.assertEqual(
                [feature["node_id"] for feature in geo["features"]],
                ["3-2-3"],
            )
            self.assertEqual(
                bundle["surface_payload"]["tool_state"]["aitas"]["intention_rule_id"],
                "self",
            )

    def test_cts_gis_descendants_intention_overlays_focused_county_and_projectable_descendants(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(
                data_dir,
                private_dir,
                extra_projection_nodes=("3-2-3-17-77-1-1", "3-2-3-17-77-1-2"),
            )

            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={
                    "tool_state": {
                        "selected_node_id": "3-2-3-17-77",
                        "aitas": {"intention_rule_id": "3-2-3-17-77-0-0"},
                    }
                },
            )

            garland = bundle["inspector"]["interface_body"]["garland_split_projection"]
            geo = garland["geospatial_projection"]
            profile = garland["profile_projection"]
            self.assertEqual(bundle["surface_payload"]["tool_state"]["aitas"]["intention_rule_id"], "3-2-3-17-77-0-0")
            self.assertEqual(profile["active_profile"]["node_id"], "3-2-3-17-77")
            self.assertEqual(
                [feature["node_id"] for feature in geo["features"]],
                ["3-2-3-17-77", "3-2-3-17-77-1-1", "3-2-3-17-77-1-2"],
            )
            self.assertEqual(geo["render_feature_count"], 3)
            self.assertGreater(geo["render_row_count"], 3)
            self.assertEqual(geo["projection_source"], "hops")
            self.assertNotIn("Attention", [group["title"] for group in bundle["control_panel"]["groups"]])
            self.assertNotIn("Projection Rules", [group["title"] for group in bundle["control_panel"]["groups"]])

    def test_cts_gis_descendants_time_context_adds_matching_precinct_profiles(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(
                data_dir,
                private_dir,
                extra_projection_nodes=(
                    "3-2-3-17-77-1-1",
                    "247-17-77-1",
                    "247-17-25-1",
                ),
            )
            district_source_path = (
                data_dir
                / "sandbox"
                / "cts-gis"
                / "sources"
                / "sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77.json"
            )
            district_payload = json.loads(district_source_path.read_text(encoding="utf-8"))
            district_space = dict(district_payload.get("datum_addressing_abstraction_space") or {})
            district_space["5-0-26"] = [["5-0-26", "~", "4-3-1"], ["23_present-district_31"]]
            district_payload["datum_addressing_abstraction_space"] = district_space
            district_source_path.write_text(json.dumps(district_payload, indent=2) + "\n", encoding="utf-8")

            base_bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={
                    "tool_state": {
                        "selected_node_id": "3-2-3-17-77",
                        "aitas": {"intention_rule_id": "3-2-3-17-77-0-0"},
                    }
                },
            )
            base_geo = base_bundle["inspector"]["interface_body"]["garland_split_projection"]["geospatial_projection"]
            self.assertNotIn("247-17-77-1", [feature["node_id"] for feature in base_geo["features"]])
            self.assertNotIn("247-17-25-1", [feature["node_id"] for feature in base_geo["features"]])

            timed_bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={
                    "tool_state": {
                        "selected_node_id": "3-2-3-17-77",
                        "aitas": {
                            "intention_rule_id": "3-2-3-17-77-0-0",
                            "time_directive": "23",
                        },
                        "source": {"precinct_district_overlay_enabled": True},
                    }
                },
            )
            timed_geo = timed_bundle["inspector"]["interface_body"]["garland_split_projection"]["geospatial_projection"]
            timed_feature_ids = [feature["node_id"] for feature in timed_geo["features"]]
            self.assertIn("247-17-77-1", timed_feature_ids)
            self.assertNotIn("247-17-25-1", timed_feature_ids)
            profile_projection = timed_bundle["inspector"]["interface_body"]["garland_split_projection"]["profile_projection"]
            self.assertTrue(bool((profile_projection.get("district_overlay_toggle") or {}).get("enabled")))
            collections = list(profile_projection.get("district_precinct_collections") or [])
            self.assertEqual(len(collections), 1)
            self.assertEqual(collections[0]["label"], "District 31 · 23 Present")
            self.assertEqual(collections[0]["summary_state"], "loaded")
            self.assertIn("247-17-77-1", list(collections[0]["member_node_ids"] or []))

    def test_cts_gis_precinct_toggle_shell_request_preserves_runtime_mode_and_transitions_overlay_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(
                data_dir,
                private_dir,
                extra_projection_nodes=(
                    "3-2-3-17-77-1-1",
                    "247-17-77-1",
                    "247-17-25-1",
                ),
            )
            district_source_path = (
                data_dir
                / "sandbox"
                / "cts-gis"
                / "sources"
                / "sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77.json"
            )
            district_payload = json.loads(district_source_path.read_text(encoding="utf-8"))
            district_space = dict(district_payload.get("datum_addressing_abstraction_space") or {})
            district_space["5-0-26"] = [["5-0-26", "~", "4-3-1"], ["23_present-district_31"]]
            district_payload["datum_addressing_abstraction_space"] = district_space
            district_source_path.write_text(json.dumps(district_payload, indent=2) + "\n", encoding="utf-8")

            scope = PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection"))
            shell_state = initial_portal_shell_state(
                surface_id="system.tools.cts_gis",
                portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
            )
            base_bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=scope,
                shell_state=shell_state,
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={
                    "runtime_mode": "audit_forensic",
                    "tool_state": {
                        "selected_node_id": "3-2-3-17-77",
                        "aitas": {
                            "attention_node_id": "3-2-3-17-77",
                            "intention_rule_id": "3-2-3-17-77-0-0",
                            "time_directive": "23",
                        },
                        "source": {"precinct_district_overlay_enabled": False},
                    }
                },
            )
            base_profile = base_bundle["inspector"]["interface_body"]["garland_split_projection"]["profile_projection"]
            base_collections = list(base_profile.get("district_precinct_collections") or [])
            self.assertEqual(base_collections[0]["summary_state"], "deferred")
            toggle_request = dict(
                (
                    (
                        base_profile.get("district_overlay_toggle")
                        or {}
                    ).get("shell_request")
                    or {}
                )
            )

            self.assertEqual(toggle_request.get("runtime_mode"), "audit_forensic")
            self.assertTrue(
                bool(
                    ((toggle_request.get("tool_state") or {}).get("source") or {}).get(
                        "precinct_district_overlay_enabled"
                    )
                )
            )

            toggled_envelope = run_portal_shell_entry(
                toggle_request,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                data_dir=data_dir,
                public_dir=None,
                private_dir=private_dir,
                audit_storage_file=None,
                webapps_root=None,
                tool_exposure_policy=None,
            )
            toggled_profile = (
                toggled_envelope["shell_composition"]["regions"]["interface_panel"]["interface_body"][
                    "garland_split_projection"
                ]["profile_projection"]
            )

            self.assertTrue(bool((toggled_profile.get("district_overlay_toggle") or {}).get("enabled")))
            collections = list(toggled_profile.get("district_precinct_collections") or [])
            self.assertEqual(len(collections), 1)
            self.assertNotEqual(collections[0]["summary_state"], "deferred")
            self.assertTrue(collections[0]["overlay_requested"])

    def test_cts_gis_toggle_overlay_action_updates_tool_state_and_transitions_precinct_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(
                data_dir,
                private_dir,
                extra_projection_nodes=(
                    "3-2-3-17-77-1-1",
                    "247-17-77-1",
                    "247-17-25-1",
                ),
            )
            district_source_path = (
                data_dir
                / "sandbox"
                / "cts-gis"
                / "sources"
                / "sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77.json"
            )
            district_payload = json.loads(district_source_path.read_text(encoding="utf-8"))
            district_space = dict(district_payload.get("datum_addressing_abstraction_space") or {})
            district_space["5-0-26"] = [["5-0-26", "~", "4-3-1"], ["23_present-district_31"]]
            district_payload["datum_addressing_abstraction_space"] = district_space
            district_source_path.write_text(json.dumps(district_payload, indent=2) + "\n", encoding="utf-8")

            action_envelope = run_portal_cts_gis_action(
                {
                    "schema": "mycite.v2.portal.system.tools.cts_gis.action.request.v1",
                    "portal_scope": {
                        "scope_id": "fnd",
                        "capabilities": ["datum_recognition", "spatial_projection"],
                    },
                    "shell_state": initial_portal_shell_state(
                        surface_id="system.tools.cts_gis",
                        portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                    ).to_dict(),
                    "runtime_mode": "audit_forensic",
                    "tool_state": {
                        "selected_node_id": "3-2-3-17-77",
                        "aitas": {
                            "attention_node_id": "3-2-3-17-77",
                            "intention_rule_id": "3-2-3-17-77-0-0",
                            "time_directive": "23",
                        },
                        "source": {"precinct_district_overlay_enabled": False},
                    },
                    "action_kind": "toggle_overlay",
                    "action_payload": {"enabled": True},
                },
                data_dir=data_dir,
                private_dir=private_dir,
                authority_db_file=None,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                tool_exposure_policy=None,
            )
            profile_projection = (
                action_envelope["shell_composition"]["regions"]["interface_panel"]["interface_body"][
                    "garland_split_projection"
                ]["profile_projection"]
            )

            self.assertTrue(bool((profile_projection.get("district_overlay_toggle") or {}).get("enabled")))
            collections = list(profile_projection.get("district_precinct_collections") or [])
            self.assertEqual(len(collections), 1)
            self.assertNotEqual(collections[0]["summary_state"], "deferred")
            self.assertTrue(collections[0]["overlay_requested"])

    def test_cts_gis_runtime_prefers_reference_geometry_when_projection_parity_warnings_exist(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(data_dir, private_dir)
            _write_cts_gis_profile_source(
                data_dir,
                node_id="3-2-3",
                profile_label="reference_guarded_states",
                extra_payload={
                    "reference_geojson_node_id": "3-2-3",
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
                                "properties": {"community_name": "reference_guarded_states"},
                            }
                        ],
                    },
                },
            )

            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={"tool_state": {"selected_node_id": "3-2-3"}},
            )

            geo = bundle["inspector"]["interface_body"]["garland_split_projection"]["geospatial_projection"]
            self.assertEqual(geo["projection_source"], "hops")
            self.assertEqual(geo["projection_state"], "projectable_degraded")
            self.assertEqual(len(geo["collection_bounds"]), 4)
            self.assertEqual(len(geo["selected_feature_bounds"]), 4)
            self.assertLess(geo["collection_bounds"][0], geo["collection_bounds"][2])
            self.assertLess(geo["collection_bounds"][1], geo["collection_bounds"][3])
            self.assertEqual(
                [feature["properties"]["profile_label"] for feature in geo["feature_collection"]["features"]],
                ["reference_guarded_states"],
            )
            self.assertNotIn("reference GeoJSON geometry", " ".join(geo["warnings"]))
            self.assertIn("did not align", " ".join(geo["warnings"]))

    def test_cts_gis_children_intention_keeps_focused_county_when_no_child_projection_exists(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(
                data_dir,
                private_dir,
                extra_projection_nodes=("3-2-3-17-77-1-1", "3-2-3-17-77-1-2"),
            )

            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={
                    "tool_state": {
                        "selected_node_id": "3-2-3-17-77",
                        "aitas": {"intention_rule_id": "3-2-3-17-77-0"},
                    }
                },
            )

            geo = bundle["inspector"]["interface_body"]["garland_split_projection"]["geospatial_projection"]
            self.assertEqual(bundle["surface_payload"]["tool_state"]["aitas"]["intention_rule_id"], "3-2-3-17-77-0")
            self.assertEqual([feature["node_id"] for feature in geo["features"]], ["3-2-3-17-77"])

    def test_cts_gis_branch_intention_overlays_attention_plus_target_child(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(
                data_dir,
                private_dir,
                extra_projection_nodes=("3-2-3-17-77-1-1", "3-2-3-17-77-1-2"),
            )

            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={
                    "tool_state": {
                        "selected_node_id": "3-2-3-17-77-1",
                        "aitas": {"intention_rule_id": "branch:3-2-3-17-77-1-1"},
                    }
                },
            )

            garland = bundle["inspector"]["interface_body"]["garland_split_projection"]
            geo = garland["geospatial_projection"]
            self.assertEqual(
                bundle["surface_payload"]["tool_state"]["aitas"]["intention_rule_id"],
                "branch:3-2-3-17-77-1-1",
            )
            self.assertEqual(
                [feature["node_id"] for feature in geo["features"]],
                ["3-2-3-17-77-1-1"],
            )
            self.assertNotIn("3-2-3-17-77-1-2", [feature["node_id"] for feature in geo["features"]])
            self.assertEqual(geo["render_feature_count"], geo["feature_count"])

    def test_cts_gis_explicit_feature_selection_does_not_replace_attention_focus_bounds(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(
                data_dir,
                private_dir,
                extra_projection_nodes=("3-2-3-17-77-1-1", "3-2-3-17-77-1-2"),
            )
            base_bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={
                    "tool_state": {
                        "selected_node_id": "3-2-3-17-77",
                        "aitas": {"intention_rule_id": "3-2-3-17-77-0-0"},
                    }
                },
            )
            base_geo = base_bundle["inspector"]["interface_body"]["garland_split_projection"]["geospatial_projection"]
            target_feature_id = base_geo["features"][1]["feature_id"]

            selected_bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={
                    "tool_state": {
                        "selected_node_id": "3-2-3-17-77",
                        "aitas": {"intention_rule_id": "3-2-3-17-77-0-0"},
                        "selection": {
                            "selected_feature_id": target_feature_id,
                            "selected_feature_explicit": True,
                        },
                    }
                },
            )

            geo = selected_bundle["inspector"]["interface_body"]["garland_split_projection"]["geospatial_projection"]
            self.assertTrue(geo["selected_feature_explicit"])
            self.assertEqual(geo["selected_feature_id"], target_feature_id)
            self.assertEqual(geo["focus_bounds"], base_geo["focus_bounds"])
            self.assertNotEqual(geo["selected_feature_bounds"], [])

    def test_cts_gis_invalid_branch_intention_normalizes_to_self(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(data_dir, private_dir)

            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={
                    "tool_state": {
                        "selected_node_id": "3-2-3-17-77",
                        "aitas": {"intention_rule_id": "branch:missing-child"},
                    }
                },
            )

            self.assertEqual(bundle["surface_payload"]["tool_state"]["aitas"]["intention_rule_id"], "self")
            warnings = list((bundle["surface_payload"]["service_surface"] or {}).get("warnings") or [])
            self.assertTrue(any("normalized to `self`" in warning for warning in warnings))

    def test_cts_gis_duplicate_node_rows_do_not_block_directory_navigation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(data_dir, private_dir, duplicate_node_ids=("3-2-3-17",))

            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={"tool_state": {"aitas": {"attention_node_id": "3-2-3-17-77"}}},
            )

            navigation_canvas = bundle["inspector"]["interface_body"]["navigation_canvas"]
            self.assertEqual(navigation_canvas["decode_state"], "ready")
            self.assertEqual(len(navigation_canvas["dropdowns"]), 6)
            diagnostic_codes = [item["code"] for item in navigation_canvas["diagnostics"]]
            self.assertIn("duplicate_node_row", diagnostic_codes)

    def test_cts_gis_nodes_outside_magnitude_do_not_block_directory_navigation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(data_dir, private_dir, outside_node_ids=("9",))

            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
            )

            navigation_canvas = bundle["inspector"]["interface_body"]["navigation_canvas"]
            self.assertEqual(navigation_canvas["decode_state"], "ready")
            self.assertEqual(len(navigation_canvas["dropdowns"]), 6)
            diagnostics_by_code = {
                item["code"]: item
                for item in navigation_canvas["diagnostics"]
            }
            if "node_outside_magnitude" in diagnostics_by_code:
                self.assertEqual(diagnostics_by_code["node_outside_magnitude"]["node_ids"], ["9"])
            else:
                self.assertIn("reconstructed_magnitude_override", diagnostics_by_code)

    def test_cts_gis_invalid_cache_magnitude_falls_back_to_valid_tool_anchor(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(
                data_dir,
                private_dir,
                cache_magnitude_bitstream=(
                    "00000000001000000000011001101110000000010000000001010000001001000000111100000100010000010010000001001100000101110000011000000001101100000111000000011110000010000100001000100000100011000010010000001001"
                ),
            )

            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
            )

            navigation_canvas = bundle["inspector"]["interface_body"]["navigation_canvas"]
            self.assertEqual(navigation_canvas["decode_state"], "ready")
            self.assertEqual(navigation_canvas["magnitude_source_kind"], "tool_anchor")
            self.assertEqual(navigation_canvas["magnitude_datum_address"], "1-1-2")
            self.assertEqual(len(navigation_canvas["dropdowns"]), 6)
            diagnostic_codes = [item["code"] for item in navigation_canvas["diagnostics"]]
            self.assertIn("invalid_magnitude_candidate", diagnostic_codes)

    def test_cts_gis_drifted_decodable_magnitude_is_overridden_by_reconstructed_authority(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            stale_root_only_magnitude = encode_canonical_structure_from_addresses(
                [str(index) for index in range(1, 9)]
            ).bitstream
            _write_cts_gis_fixture(
                data_dir,
                private_dir,
                cache_magnitude_bitstream=stale_root_only_magnitude,
                anchor_magnitude_bitstream=stale_root_only_magnitude,
            )

            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
            )

            navigation_canvas = bundle["inspector"]["interface_body"]["navigation_canvas"]
            self.assertEqual(navigation_canvas["decode_state"], "ready")
            self.assertEqual(navigation_canvas["magnitude_source_kind"], "administrative_source_reconstructed")
            self.assertGreaterEqual(len(navigation_canvas["dropdowns"]), 5)
            diagnostic_codes = [item["code"] for item in navigation_canvas["diagnostics"]]
            self.assertIn("reconstructed_magnitude_override", diagnostic_codes)

    def test_cts_gis_invalid_magnitude_blocks_without_fabricated_dropdown_tree(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            _write_cts_gis_fixture(
                data_dir,
                private_dir,
                cache_magnitude_bitstream=(
                    "00000000001000000000011001101110000000010000000001010000001001000000111100000100010000010010000001001100000101110000011000000001101100000111000000011110000010000100001000100000100011000010010000001001"
                ),
                anchor_magnitude_bitstream=(
                    "00000000001000000000011001101110000000010000000001010000001001000000111100000100010000010010000001001100000101110000011000000001101100000111000000011110000010000100001000100000100011000010010000001001"
                ),
            )
            _write_json(
                data_dir / "sandbox" / "cts-gis" / "sources" / "sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json",
                {"datum_addressing_abstraction_space": {}},
            )

            bundle = build_portal_cts_gis_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition", "spatial_projection")),
                shell_state=initial_portal_shell_state(
                    surface_id="system.tools.cts_gis",
                    portal_scope={"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                ),
                data_dir=data_dir,
                private_dir=private_dir,
                request_payload={"tool_state": {"aitas": {"attention_node_id": "3-2-3-17-77"}}},
            )

            navigation_canvas = bundle["inspector"]["interface_body"]["navigation_canvas"]
            self.assertEqual(navigation_canvas["decode_state"], "blocked_invalid_magnitude")
            self.assertEqual(navigation_canvas["dropdowns"], [])
            self.assertEqual(navigation_canvas["active_path"], [])
            invalid_diagnostic = next(
                item for item in navigation_canvas["diagnostics"] if item["code"] == "invalid_magnitude"
            )
            self.assertIn("could not decode", invalid_diagnostic["message"].lower())

    def test_unknown_removed_surface_falls_back_to_system_workspace(self) -> None:
        envelope = run_portal_shell_entry(
            {
                "schema": "mycite.v2.portal.shell.request.v1",
                "requested_surface_id": "system.legacy_removed_surface",
                "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            },
            portal_instance_id="fnd",
            portal_domain="fruitfulnetworkdevelopment.com",
            data_dir=None,
            public_dir=None,
            private_dir=None,
            audit_storage_file=None,
            webapps_root=None,
            tool_exposure_policy=None,
        )
        self.assertTrue(envelope["reducer_owned"])
        self.assertEqual(envelope["surface_id"], SYSTEM_ROOT_SURFACE_ID)
        self.assertEqual(envelope["canonical_route"], "/portal/system")
        self.assertEqual(envelope["canonical_query"]["file"], "anthology")
        self.assertEqual(envelope["error"]["code"], "surface_unknown")

    def test_network_root_projects_system_log_workbench_without_reducer_ownership(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            private_dir = root / "private"
            public_dir = root / "public"
            for path in (data_dir, private_dir, public_dir):
                path.mkdir(parents=True, exist_ok=True)
            _write_network_chronology_authority(data_dir)
            _write_json(
                data_dir / "system" / "system_log.json",
                build_system_log_document(
                    records=[
                        {
                            "source_key": "canonical-general",
                            "source_kind": "canonical_seed",
                            "source_timestamp": "2026-07-04T00:00:00Z",
                            "title": "americas_250th_anniversary_2026_07_04",
                            "label": "americas_250th_anniversary_2026_07_04",
                            "event_type_slug": "general_event",
                            "event_type_label": "general_event",
                            "status": "scheduled",
                            "counterparty": "",
                            "contract_id": "",
                            "hops_timestamp": "0-0-0-507-916-0-0-0",
                            "raw": {"kind": "calendar"},
                        }
                    ],
                    preserved_kind_labels={"general_event": "general_event"},
                ),
            )
            _write_json(private_dir / "config.json", {"msn_id": "3-2-3-17-77-1-6-4-1-4"})

            envelope = run_portal_shell_entry(
                {
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": NETWORK_ROOT_SURFACE_ID,
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                    "surface_query": {"view": "system_logs"},
                },
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                data_dir=data_dir,
                public_dir=public_dir,
                private_dir=private_dir,
                audit_storage_file=None,
                webapps_root=None,
                tool_exposure_policy=None,
            )

            self.assertFalse(envelope["reducer_owned"])
            self.assertEqual(envelope["surface_id"], NETWORK_ROOT_SURFACE_ID)
            self.assertEqual(envelope["canonical_route"], "/portal/network")
            self.assertEqual(envelope["canonical_query"], {"view": "system_logs"})
            self.assertEqual(envelope["surface_payload"]["kind"], "network_system_log_workspace")
            self.assertEqual(envelope["surface_payload"]["workspace"]["state"], "ready")
            self.assertEqual(
                envelope["shell_composition"]["regions"]["workbench"]["kind"],
                "network_system_log_workbench",
            )
            self.assertEqual(
                envelope["shell_composition"]["regions"]["inspector"]["kind"],
                "summary_panel",
            )
            self.assertTrue(envelope["shell_composition"]["inspector_collapsed"])
            self.assertTrue(envelope["shell_composition"]["interface_panel_collapsed"])
            self.assertFalse(envelope["shell_composition"]["workbench_collapsed"])
            self.assertFalse(envelope["shell_composition"]["regions"]["inspector"]["visible"])
            self.assertEqual(
                envelope["shell_composition"]["regions"]["interface_panel"],
                envelope["shell_composition"]["regions"]["inspector"],
            )

            record_id = envelope["surface_payload"]["workspace"]["records"][0]["datum_address"]
            focused_envelope = run_portal_shell_entry(
                {
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": NETWORK_ROOT_SURFACE_ID,
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                    "surface_query": {"view": "system_logs", "record": record_id},
                },
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                data_dir=data_dir,
                public_dir=public_dir,
                private_dir=private_dir,
                audit_storage_file=None,
                webapps_root=None,
                tool_exposure_policy=None,
            )
            self.assertEqual(
                focused_envelope["canonical_query"],
                {"view": "system_logs", "record": record_id},
            )
            self.assertFalse(focused_envelope["shell_composition"]["inspector_collapsed"])
            self.assertFalse(focused_envelope["shell_composition"]["interface_panel_collapsed"])
            self.assertFalse(focused_envelope["shell_composition"]["workbench_collapsed"])
            self.assertTrue(focused_envelope["shell_composition"]["regions"]["inspector"]["visible"])
            self.assertEqual(
                focused_envelope["shell_composition"]["regions"]["inspector"]["subject"],
                {"level": "record", "id": record_id},
            )
            self.assertEqual(
                focused_envelope["shell_composition"]["regions"]["interface_panel"],
                focused_envelope["shell_composition"]["regions"]["inspector"],
            )
            self.assertEqual(
                focused_envelope["shell_state"],
                {"schema": "mycite.v2.portal.shell.state.v1"},
            )
            self.assertIsNone(focused_envelope["shell_composition"]["shell_state"])

    def test_system_root_shell_composition_uses_logo_as_the_only_system_activity_entry(self) -> None:
        envelope = run_portal_shell_entry(
            {
                "schema": "mycite.v2.portal.shell.request.v1",
                "requested_surface_id": "system.root",
                "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            },
            portal_instance_id="fnd",
            portal_domain="fruitfulnetworkdevelopment.com",
            data_dir=None,
            public_dir=None,
            private_dir=None,
            audit_storage_file=None,
            webapps_root=None,
            tool_exposure_policy=None,
        )
        activity_items = envelope["shell_composition"]["regions"]["activity_bar"]["items"]
        self.assertNotIn("system.root", [item["item_id"] for item in activity_items])
        operational_envelope = run_portal_shell_entry(
            {
                "schema": "mycite.v2.portal.shell.request.v1",
                "requested_surface_id": "system.legacy_removed_surface",
                "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            },
            portal_instance_id="fnd",
            portal_domain="fruitfulnetworkdevelopment.com",
            data_dir=None,
            public_dir=None,
            private_dir=None,
            audit_storage_file=None,
            webapps_root=None,
            tool_exposure_policy=None,
        )
        control_panel = operational_envelope["shell_composition"]["regions"]["control_panel"]
        self.assertEqual(control_panel["kind"], "focus_selection_panel")
        self.assertEqual(control_panel["surface_label"], "SYSTEM")
        self.assertTrue(envelope["shell_composition"]["inspector_collapsed"])
        self.assertTrue(envelope["shell_composition"]["interface_panel_collapsed"])
        self.assertFalse(envelope["shell_composition"]["workbench_collapsed"])
        self.assertFalse(envelope["shell_composition"]["regions"]["inspector"]["visible"])
        self.assertEqual(
            envelope["shell_composition"]["regions"]["interface_panel"],
            envelope["shell_composition"]["regions"]["inspector"],
        )

    def test_utilities_root_uses_minimal_section_led_control_panel_and_collapsed_interface_panel(self) -> None:
        envelope = run_portal_shell_entry(
            {
                "schema": "mycite.v2.portal.shell.request.v1",
                "requested_surface_id": UTILITIES_ROOT_SURFACE_ID,
                "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            },
            portal_instance_id="fnd",
            portal_domain="fruitfulnetworkdevelopment.com",
            data_dir=None,
            public_dir=None,
            private_dir=None,
            audit_storage_file=None,
            webapps_root=None,
            tool_exposure_policy=None,
        )
        control_panel = envelope["shell_composition"]["regions"]["control_panel"]
        self.assertEqual(control_panel["kind"], "focus_selection_panel")
        self.assertEqual(control_panel["title"], "Control Panel")
        self.assertEqual(control_panel["surface_label"], "UTILITIES")
        self.assertEqual(
            control_panel["context_items"],
            [
                {"label": "Root", "value": "UTILITIES"},
                {"label": "Section", "value": "Overview"},
            ],
        )
        self.assertEqual(control_panel["verb_tabs"], [])
        self.assertEqual([group["title"] for group in control_panel["groups"]], ["Sections"])
        self.assertEqual(
            [entry["label"] for entry in control_panel["groups"][0]["entries"]],
            ["Tool Exposure", "Integrations"],
        )
        self.assertTrue(envelope["shell_composition"]["inspector_collapsed"])
        self.assertTrue(envelope["shell_composition"]["interface_panel_collapsed"])
        self.assertFalse(envelope["shell_composition"]["workbench_collapsed"])
        self.assertFalse(envelope["shell_composition"]["regions"]["inspector"]["visible"])
        self.assertEqual(
            envelope["shell_composition"]["regions"]["interface_panel"],
            envelope["shell_composition"]["regions"]["inspector"],
        )

    def test_runtime_owned_surface_does_not_emit_client_supplied_shell_state(self) -> None:
        envelope = run_portal_shell_entry(
            {
                "schema": "mycite.v2.portal.shell.request.v1",
                "requested_surface_id": NETWORK_ROOT_SURFACE_ID,
                "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                "surface_query": {"view": "overview"},
                "shell_state": {
                    "schema": "mycite.v2.portal.shell.state.v1",
                    "active_surface_id": SYSTEM_ROOT_SURFACE_ID,
                    "focus_path": [{"level": FOCUS_LEVEL_SANDBOX, "id": "fnd"}],
                    "focus_subject": {"level": FOCUS_LEVEL_SANDBOX, "id": "fnd"},
                    "mediation_subject": {"level": FOCUS_LEVEL_OBJECT, "id": "1-0-0"},
                    "verb": VERB_MEDIATE,
                    "chrome": {"control_panel_collapsed": True, "interface_panel_open": True},
                },
            },
            portal_instance_id="fnd",
            portal_domain="fruitfulnetworkdevelopment.com",
            data_dir=None,
            public_dir=None,
            private_dir=None,
            audit_storage_file=None,
            webapps_root=None,
            tool_exposure_policy=None,
        )
        self.assertFalse(envelope["reducer_owned"])
        self.assertEqual(envelope["surface_id"], NETWORK_ROOT_SURFACE_ID)
        self.assertEqual(
            envelope["shell_state"],
            {"schema": "mycite.v2.portal.shell.state.v1"},
        )
        self.assertIsNone(envelope["shell_composition"]["shell_state"])

    def test_system_workspace_bundle_projects_anthology_as_layered_datum_table(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system").mkdir(parents=True, exist_ok=True)
            public_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "system" / "anthology.json").write_text(
                '{\n'
                '  "1-0-1": [["1-0-1", "rf.3-1-1", "0"], ["anchor-root"]],\n'
                '  "1-1-1": [["1-1-1", "rf.1-0-1", "111"], ["first-datum"]],\n'
                '  "1-1-2": [["1-1-2", "rf.1-0-1", "222"], ["second-datum"]],\n'
                '  "2-3-1": [["2-3-1", "rf.1-0-1", "333"], ["third-datum"]]\n'
                '}\n',
                encoding="utf-8",
            )
            SqliteSystemDatumStoreAdapter(db_file).bootstrap_from_filesystem(
                data_dir=data_dir,
                public_dir=public_dir,
                tenant_id="fnd",
            )

            base_state = initial_portal_shell_state(
                surface_id=SYSTEM_ROOT_SURFACE_ID,
                portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            )
            bundle = build_system_workspace_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("fnd_peripheral_routing",)),
                portal_domain="fruitfulnetworkdevelopment.com",
                shell_state=base_state,
                data_dir=data_dir,
                public_dir=public_dir,
                audit_storage_file=None,
                tool_rows=[],
                authority_db_file=db_file,
                authority_mode="sql_primary",
            )
            workspace = bundle["surface_payload"]["workspace"]
            document = workspace["document"]
            control_panel = bundle["control_panel"]
            self.assertEqual(document["presentation"], "anthology_layered_table")
            self.assertEqual(document["layer_groups"][0]["layer"], 1)
            self.assertEqual(document["layer_groups"][0]["value_groups"][0]["value_group"], 0)
            self.assertEqual(document["layer_groups"][0]["value_groups"][1]["rows"][1]["coordinates"]["iteration"], 2)
            self.assertIsNone(document["selected_datum"])
            self.assertEqual(control_panel["kind"], "focus_selection_panel")
            self.assertEqual(control_panel["surface_label"], "SYSTEM")
            self.assertEqual(
                control_panel["context_items"][:2],
                [
                    {"label": "Sandbox", "value": "SYSTEM"},
                    {"label": "File", "value": "anthology.json"},
                ],
            )
            self.assertIn("Layer 1", [group["title"] for group in control_panel["groups"]])

            datum_state = reduce_portal_shell_state(
                active_surface_id=SYSTEM_ROOT_SURFACE_ID,
                portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                current_state=base_state,
                transition={"kind": TRANSITION_FOCUS_DATUM, "file_key": "anthology", "datum_id": "1-1-2"},
                seed_anchor_file=False,
            )
            selected_bundle = build_system_workspace_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("fnd_peripheral_routing",)),
                portal_domain="fruitfulnetworkdevelopment.com",
                shell_state=datum_state,
                data_dir=data_dir,
                public_dir=public_dir,
                audit_storage_file=None,
                tool_rows=[],
                authority_db_file=db_file,
                authority_mode="sql_primary",
            )
            selected_datum = selected_bundle["surface_payload"]["workspace"]["document"]["selected_datum"]
            self.assertEqual(selected_datum["datum_id"], "1-1-2")
            self.assertEqual(selected_datum["coordinates"]["layer"], 1)
            self.assertEqual(selected_datum["coordinates"]["value_group"], 1)
            self.assertEqual(selected_datum["coordinates"]["iteration"], 2)
            self.assertIn("reference_bindings", selected_datum)
            self.assertIn("raw", selected_datum)
            selected_panel = selected_bundle["control_panel"]
            self.assertEqual(selected_panel["context_items"][2]["label"], "Datum")
            self.assertEqual(selected_panel["groups"][0]["title"], "Below Focus")

    def test_non_anthology_documents_keep_generic_workspace_rendering(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system").mkdir(parents=True, exist_ok=True)
            (data_dir / "sandbox" / "cts-gis" / "sources").mkdir(parents=True, exist_ok=True)
            (data_dir / "sandbox" / "cts-gis" / "sources" / "precincts").mkdir(parents=True, exist_ok=True)
            public_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "system" / "anthology.json").write_text(
                '{\n  "1-0-1": [["1-0-1", "rf.3-1-1", "0"], ["anchor-root"]]\n}\n',
                encoding="utf-8",
            )
            (data_dir / "sandbox" / "cts-gis" / "tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json").write_text(
                '{\n  "datum_addressing_abstraction_space": {\n    "3-1-1": [["3-1-1", "2-1-1", "0"], ["cts-gis-anchor"]]\n  }\n}\n',
                encoding="utf-8",
            )
            (data_dir / "sandbox" / "cts-gis" / "sources" / "sc.example.json").write_text(
                '{\n  "4-2-118": [["4-2-118", "rf.3-1-1", "HERE"], ["summit_county_cities"]]\n}\n',
                encoding="utf-8",
            )
            SqliteSystemDatumStoreAdapter(db_file).bootstrap_from_filesystem(
                data_dir=data_dir,
                public_dir=public_dir,
                tenant_id="fnd",
            )

            scope = PortalScope(scope_id="fnd", capabilities=("fnd_peripheral_routing",))
            projection = read_system_workbench_projection(
                portal_scope=scope,
                data_dir=data_dir,
                public_dir=public_dir,
                authority_db_file=db_file,
                authority_mode="sql_primary",
            )
            sandbox_document_id = [
                document.document_id for document in projection.documents if document.document_id != "system:anthology"
            ][0]
            shell_state = reduce_portal_shell_state(
                active_surface_id=SYSTEM_ROOT_SURFACE_ID,
                portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                current_state=initial_portal_shell_state(
                    surface_id=SYSTEM_ROOT_SURFACE_ID,
                    portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                ),
                transition={"kind": TRANSITION_FOCUS_FILE, "file_key": sandbox_document_id},
                seed_anchor_file=False,
            )
            bundle = build_system_workspace_bundle(
                portal_scope=scope,
                portal_domain="fruitfulnetworkdevelopment.com",
                shell_state=shell_state,
                data_dir=data_dir,
                public_dir=public_dir,
                audit_storage_file=None,
                tool_rows=[],
                authority_db_file=db_file,
                authority_mode="sql_primary",
            )
            document = bundle["surface_payload"]["workspace"]["document"]
            self.assertNotIn("presentation", document)
            self.assertEqual(document["document_id"], sandbox_document_id)


    def test_system_workbench_projection_uses_cache_until_authority_mtime_changes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system").mkdir(parents=True, exist_ok=True)
            public_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "system" / "anthology.json").write_text(
                '{\n  "1-0-1": [["1-0-1", "rf.3-1-1", "0"], ["anchor-root"]]\n}\n',
                encoding="utf-8",
            )
            SqliteSystemDatumStoreAdapter(db_file).bootstrap_from_filesystem(
                data_dir=data_dir,
                public_dir=public_dir,
                tenant_id="fnd",
            )

            scope = PortalScope(scope_id="fnd", capabilities=("fnd_peripheral_routing",))

            from MyCiteV2.instances._shared.runtime import portal_system_workspace_runtime as workspace_runtime

            workspace_runtime._invalidate_workbench_projection_cache()
            with patch.object(
                workspace_runtime.DatumWorkbenchService,
                "read_workbench",
                autospec=True,
                side_effect=workspace_runtime.DatumWorkbenchService.read_workbench,
            ) as read_workbench:
                read_system_workbench_projection(
                    portal_scope=scope,
                    data_dir=data_dir,
                    public_dir=public_dir,
                    authority_db_file=db_file,
                    authority_mode="sql_primary",
                )
                read_system_workbench_projection(
                    portal_scope=scope,
                    data_dir=data_dir,
                    public_dir=public_dir,
                    authority_db_file=db_file,
                    authority_mode="sql_primary",
                )
                self.assertEqual(read_workbench.call_count, 1)

                stat = db_file.stat()
                new_ns = stat.st_mtime_ns + 1_000_000
                import os

                os.utime(db_file, ns=(new_ns, new_ns))
                read_system_workbench_projection(
                    portal_scope=scope,
                    data_dir=data_dir,
                    public_dir=public_dir,
                    authority_db_file=db_file,
                    authority_mode="sql_primary",
                )
                self.assertEqual(read_workbench.call_count, 2)

            workspace_runtime._invalidate_workbench_projection_cache()


if __name__ == "__main__":
    unittest.main()
