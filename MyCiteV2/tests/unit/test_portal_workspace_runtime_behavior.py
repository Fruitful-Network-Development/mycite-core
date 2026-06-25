from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry
from MyCiteV2.instances._shared.runtime.portal_system_workspace_runtime import (
    build_system_workspace_bundle,
    read_system_workbench_projection,
)
from MyCiteV2.packages.adapters.filesystem.network_root_read_model import build_system_log_document
from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.structures.samras import encode_canonical_structure_from_addresses
from MyCiteV2.packages.state_machine.portal_shell import (
    FOCUS_LEVEL_OBJECT,
    FOCUS_LEVEL_SANDBOX,
    NETWORK_ROOT_SURFACE_ID,
    SYSTEM_ROOT_SURFACE_ID,
    TRANSITION_BACK_OUT,
    TRANSITION_FOCUS_DATUM,
    TRANSITION_FOCUS_FILE,
    TRANSITION_FOCUS_OBJECT,
    TRANSITION_SET_VERB,
    UTILITIES_ROOT_SURFACE_ID,
    VERB_MEDIATE,
    VERB_NAVIGATE,
    WORKBENCH_UI_TOOL_SURFACE_ID,
    PortalScope,
    build_shell_composition_payload,
    initial_portal_shell_state,
    reduce_portal_shell_state,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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

    # `test_cts_gis_source_path_prefers_precinct_subdirectory_when_present`
    # has been retired. The `_cts_gis_source_path` helper it exercised was
    # deleted on 2026-05-17 (Phase 6 runtime refactor) per
    # docs/contracts/mos_authority_enforcement.md — the runtime no longer
    # globs the on-disk sandbox tree. The architecture test
    # `test_no_sandbox_directory_helpers_in_runtime` now enforces the
    # absence of these helpers.

    def test_mediation_transition_sets_verb_subject_and_back_out_clears_them(self) -> None:
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
        self.assertEqual(mediation_state.mediation_subject, {"level": FOCUS_LEVEL_OBJECT, "id": "1-0-0"})

        backed_out = reduce_portal_shell_state(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope=scope,
            current_state=mediation_state,
            transition={"kind": TRANSITION_BACK_OUT},
            seed_anchor_file=False,
        )
        self.assertEqual(backed_out.verb, VERB_NAVIGATE)
        self.assertIsNone(backed_out.mediation_subject)

    def test_shell_composition_builder_owns_root_and_tool_visibility_defaults(self) -> None:
        root_composition = build_shell_composition_payload(
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_instance_id="fnd",
            page_title="System",
            page_subtitle="",
            activity_items=[],
            control_panel={},
            workbench={},
            interface_panel={},
            shell_state=initial_portal_shell_state(
                surface_id=SYSTEM_ROOT_SURFACE_ID,
                portal_scope={"scope_id": "fnd", "capabilities": []},
            ),
        )
        self.assertFalse(root_composition["workbench_collapsed"])
        self.assertTrue(root_composition["interface_panel_collapsed"])
        self.assertNotIn("inspector", root_composition["regions"])

        # cts_gis retired in Stage C; use workbench_ui as the canonical tool
        # surface. interface_panel is always collapsed.
        tool_composition = build_shell_composition_payload(
            active_surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
            portal_instance_id="fnd",
            page_title="Workbench UI",
            page_subtitle="",
            activity_items=[],
            control_panel={},
            workbench={"visible": True},
            interface_panel={},
            shell_state=None,
        )
        self.assertFalse(tool_composition["workbench_collapsed"])
        self.assertTrue(tool_composition["interface_panel_collapsed"])
        self.assertEqual(tool_composition["foreground_shell_region"], "center-workbench")
        self.assertNotIn("interface_panel", tool_composition["regions"])
        self.assertNotIn("inspector", tool_composition["regions"])

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
        # Phase A: system.root is query-native, so the unknown-surface
        # fallback resolves to a non-reducer system.root with an empty query.
        self.assertFalse(envelope["reducer_owned"])
        self.assertEqual(envelope["surface_id"], SYSTEM_ROOT_SURFACE_ID)
        self.assertEqual(envelope["canonical_route"], "/portal/system")
        self.assertNotIn("file", envelope["canonical_query"])
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
            # portal-tool-overlay-restructure: the interface_panel region was removed (tools
            # render in the menubar-search overlay); interface_panel_collapsed stays True.
            self.assertTrue(envelope["shell_composition"]["interface_panel_collapsed"])
            self.assertFalse(envelope["shell_composition"]["workbench_collapsed"])
            self.assertNotIn("interface_panel", envelope["shell_composition"]["regions"])
            self.assertNotIn("inspector", envelope["shell_composition"]["regions"])

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
            # Phase 3 (portal_tool_surface_contract.md): interface_panel is
            # always hidden after retirement. Focused record selection no longer
            # opens the panel; the workbench remains foreground.
            self.assertTrue(focused_envelope["shell_composition"]["interface_panel_collapsed"])
            self.assertFalse(focused_envelope["shell_composition"]["workbench_collapsed"])
            self.assertNotIn("interface_panel", focused_envelope["shell_composition"]["regions"])
            self.assertNotIn("inspector", focused_envelope["shell_composition"]["regions"])
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
        self.assertEqual(control_panel["kind"], "unified_directive_panel")
        self.assertEqual(control_panel["surface_label"], "SYSTEM")
        # portal-tool-overlay-restructure: /portal/system delegates to the workbench-ui
        # bundle, but the interface_panel sidebar is DORMANT (visible False — tools render in
        # the menubar-search overlay), so the composition reports it collapsed. Workbench stays.
        self.assertTrue(envelope["shell_composition"]["interface_panel_collapsed"])
        self.assertFalse(envelope["shell_composition"]["workbench_collapsed"])
        self.assertNotIn("interface_panel", envelope["shell_composition"]["regions"])
        self.assertNotIn("inspector", envelope["shell_composition"]["regions"])

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
            ["Extensions", "Grantee Profile", "Tools", "Peripherals"],
        )
        self.assertTrue(envelope["shell_composition"]["interface_panel_collapsed"])
        self.assertFalse(envelope["shell_composition"]["workbench_collapsed"])
        self.assertNotIn("interface_panel", envelope["shell_composition"]["regions"])
        self.assertNotIn("inspector", envelope["shell_composition"]["regions"])

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
            self.assertEqual(control_panel["kind"], "unified_directive_panel")
            self.assertEqual(control_panel["surface_label"], "SYSTEM")
            context_pairs = [
                (row.get("label"), row.get("value"))
                for row in control_panel["context_conditions"][:2]
            ]
            self.assertEqual(
                context_pairs,
                [("Sandbox", "SYSTEM"), ("File", "anthology.json")],
            )
            self.assertIn(
                "Layer 1",
                [group["title"] for group in control_panel["navigation_groups"]],
            )

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
            datum_rows = [
                row for row in selected_panel["context_conditions"]
                if row.get("label") == "Datum"
            ]
            self.assertTrue(datum_rows, "Datum context row missing from unified panel")
            self.assertIn(
                "Below Focus",
                [group["title"] for group in selected_panel["navigation_groups"]],
            )

    def test_system_workspace_rejects_non_system_document_focus(self) -> None:
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
            sandbox_document_id = next(
                document.document_id for document in projection.documents if document.document_id != "system:anthology"
            )
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
            self.assertEqual(document["document_id"], "system:anthology")
            self.assertEqual(document["presentation"], "anthology_layered_table")
            self.assertEqual(
                [segment.id for segment in shell_state.focus_path],
                ["system", "anthology"],
            )
            self.assertNotIn(
                "Sandbox: cts-gis",
                [group["title"] for group in bundle["control_panel"]["navigation_groups"]],
            )


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

            from MyCiteV2.instances._shared.runtime import (
                portal_system_workspace_runtime as workspace_runtime,
            )

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
