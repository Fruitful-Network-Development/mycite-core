from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from flask import Flask

    HAS_FLASK = True
except ModuleNotFoundError:  # pragma: no cover
    HAS_FLASK = False
    Flask = None  # type: ignore[assignment]

def _load_register_data_routes():
    path = Path(__file__).resolve().parents[1] / "portals" / "_shared" / "portal" / "api" / "data_workspace.py"
    portals_root = path.parents[4]
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    spec = importlib.util.spec_from_file_location("data_workspace_test_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.register_data_routes


class _WorkspaceStub:
    def __init__(self, *, anthology_rows: dict[str, object] | None = None, data_dir: str = ".") -> None:
        self.calls: list[dict[str, object]] = []
        self._counter = 0
        self._anthology_rows = anthology_rows if isinstance(anthology_rows, dict) else {}
        self.storage = type("StorageStub", (), {"data_dir": data_dir})()

    def append_anthology_datum(self, *, layer, value_group, reference, magnitude, label, pairs=None):
        self._counter += 1
        identifier = f"{layer}-{value_group}-{self._counter}"
        try:
            payload = json.loads(str(magnitude or ""))
        except Exception:
            payload = {}
        canonical_ref = str(payload.get("canonical_ref") or "").strip() if isinstance(payload, dict) else ""
        if "." in canonical_ref:
            identifier = canonical_ref.split(".", 1)[1]
        elif canonical_ref:
            identifier = canonical_ref
        self.calls.append(
            {
                "layer": layer,
                "value_group": value_group,
                "reference": reference,
                "magnitude": magnitude,
                "label": label,
                "pairs": pairs,
            }
        )
        self._anthology_rows[identifier] = {"identifier": identifier, "magnitude": magnitude, "label": label}
        return {
            "ok": True,
            "identifier": identifier,
            "contract_mss_sync": {"triggered": True, "reason": "test"},
        }


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class DataWritePipelineRouteTests(unittest.TestCase):
    def setUp(self):
        register_data_routes = _load_register_data_routes()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.private_dir = Path(self._tmpdir.name) / "private"
        self.private_dir.mkdir(parents=True, exist_ok=True)
        self.anthology_rows: dict[str, object] = {}
        self.workspace = _WorkspaceStub(anthology_rows=self.anthology_rows, data_dir=self._tmpdir.name)
        self.config_payload = {"display": {"title": "Before"}}
        self.app = Flask(__name__)
        register_data_routes(
            self.app,
            workspace=self.workspace,
            anthology_payload_provider=lambda: {"rows": self.anthology_rows},
            active_config_provider=lambda: dict(self.config_payload),
            active_config_saver=self._save_config,
            msn_id_provider=lambda: "9-9-9",
            private_dir=self.private_dir,
            include_home_redirect=False,
            include_legacy_shims=False,
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _save_config(self, payload):
        self.config_payload = dict(payload)
        return True

    def test_profile_field_preview_uses_contract_schema(self):
        response = self.client.post(
            "/portal/api/data/write/preview",
            json={
                "intent": {
                    "intent_type": "profile_field",
                    "field_id": "portal_title",
                    "template_id": "geometry.parcel",
                    "fields": {"local_id": "31-1-4", "title": "Parcel"},
                }
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertTrue(payload.get("ok"))
        contract = ((payload.get("validation") or {}).get("contract") or {})
        self.assertEqual(contract.get("field_id"), "portal_title")
        self.assertTrue(any(item.get("path") == "display.title" for item in payload.get("config_updates") or []))

    def test_field_contracts_include_extended_profile_fields(self):
        response = self.client.get("/portal/api/data/write/field_contracts")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        contracts = payload.get("contracts") if isinstance(payload.get("contracts"), dict) else {}
        self.assertIn("property_parcel_ref", contracts)
        self.assertIn("property_plot_refs", contracts)
        self.assertIn("inherited_product_profile_ref", contracts)
        self.assertIn("inherited_supply_log_ref", contracts)

    def test_aitas_archetype_routes_inspect_trace_and_bindings(self):
        self.anthology_rows.update(
            {
                "10-1-1": {
                    "identifier": "10-1-1",
                    "label": "ASCII root",
                    "pairs": [],
                    "magnitude": '{"family":"ascii"}',
                },
                "10-1-2": {
                    "identifier": "10-1-2",
                    "label": "Babel bridge",
                    "pairs": [{"reference": "10-1-1", "magnitude": "inherits"}],
                    "magnitude": '{"kind":"babel"}',
                },
                "10-1-3": {
                    "identifier": "10-1-3",
                    "label": "ASCII Babel 64 Field",
                    "pairs": [{"reference": "10-1-2", "magnitude": "inherits"}],
                    "magnitude": '{"field_length":64,"alphabet_cardinality":256}',
                },
            }
        )
        defs = self.client.get("/portal/api/data/aitas/archetypes")
        self.assertEqual(defs.status_code, 200)
        self.assertTrue((defs.get_json() or {}).get("ok"))
        self.assertTrue(
            any(str(item.get("archetype_key")) == "ascii_babel_64" for item in (defs.get_json() or {}).get("definitions") or [])
        )

        inspect = self.client.post("/portal/api/data/aitas/archetype/inspect", json={"datum_ref": "10-1-3"})
        self.assertEqual(inspect.status_code, 200)
        inspect_payload = inspect.get_json() or {}
        self.assertTrue(inspect_payload.get("ok"))
        self.assertEqual(
            (((inspect_payload.get("aitas") or {}).get("archetype") or {}).get("binding") or {}).get("archetype_key"),
            "ascii_babel_64",
        )

        trace = self.client.post("/portal/api/data/aitas/archetype/trace", json={"datum_ref": "10-1-3"})
        self.assertEqual(trace.status_code, 200)
        self.assertTrue((trace.get_json() or {}).get("ok"))
        self.assertTrue(((trace.get_json() or {}).get("trace") or {}).get("edges"))

        bindings = self.client.get("/portal/api/data/aitas/archetype/bindings?limit=20")
        self.assertEqual(bindings.status_code, 200)
        bindings_payload = bindings.get_json() or {}
        self.assertTrue(bindings_payload.get("ok"))
        self.assertEqual(bindings_payload.get("count"), 1)

    def test_aitas_inspect_includes_samras_compiled_constraint(self):
        self.anthology_rows.update(
            {
                "1-1-3": {
                    "identifier": "1-1-3",
                    "label": "txa-SAMRAS",
                    "pairs": [{"reference": "0-0-5", "magnitude": "def"}],
                    "magnitude": "3-3-0-0-1-1-4,0-0-0-0-8",
                },
                "2-1-12": {
                    "identifier": "2-1-12",
                    "label": "SAMRAS-space-txa",
                    "pairs": [{"reference": "1-1-3", "magnitude": "1"}],
                    "magnitude": "1",
                },
                "3-1-5": {
                    "identifier": "3-1-5",
                    "label": "txa_id-babelette-txa_id",
                    "pairs": [{"reference": "2-1-12", "magnitude": "0"}],
                    "magnitude": "0",
                },
                "8-5-1": {
                    "identifier": "8-5-1",
                    "label": "product-profile-row",
                    "pairs": [{"reference": "3-1-5", "magnitude": "3-2-3-1"}],
                    "magnitude": "3-2-3-1",
                },
            }
        )
        inspect = self.client.post("/portal/api/data/aitas/archetype/inspect", json={"datum_ref": "8-5-1"})
        self.assertEqual(inspect.status_code, 200)
        payload = inspect.get_json() or {}
        compiled = (((payload.get("aitas") or {}).get("archetype") or {}).get("compiled_constraint") or {})
        self.assertEqual(compiled.get("constraint_family"), "samras")
        self.assertEqual(compiled.get("value_kind"), "txa_id")
        self.assertTrue(compiled.get("descriptor_digest"))

    def test_sandbox_compile_txa_inherited_context_route(self):
        self.anthology_rows.update(
            {
                "1-1-3": {"identifier": "1-1-3", "label": "txa-SAMRAS", "pairs": [], "magnitude": "3-3-0-0-1-1-4"},
                "3-1-5": {"identifier": "3-1-5", "label": "txa_id-babelette-txa_id", "pairs": [], "magnitude": "0"},
            }
        )
        upsert = self.client.post(
            "/portal/api/data/sandbox/samras/upsert",
            json={
                "resource_id": "txa-samras-test",
                "structure_payload": "3-3-0-0-1-1-4",
                "value_kind": "txa_id",
                "rows": [{"address_id": "8-5-1", "title": "product row"}],
            },
        )
        self.assertEqual(upsert.status_code, 200)
        compiled = self.client.post(
            "/portal/api/data/sandbox/inherited/compile_txa",
            json={"resource_ref": "sandbox:txa-samras-test", "inherited_refs": ["7-7-7.8-5-1", "7-7-7.8-4-1"]},
        )
        self.assertEqual(compiled.status_code, 200)
        payload = compiled.get_json() or {}
        self.assertTrue(payload.get("ok"))
        self.assertTrue(payload.get("txa_refs"))
        self.assertEqual(((payload.get("txa_descriptor") or {}).get("constraint_family")), "samras")

    def test_write_pipeline_inherited_ref_slice_for_8_5_and_8_4(self):
        self.config_payload = {"agro": {"inherited": {}}}
        intent_profile = {
            "intent_type": "profile_field",
            "field_id": "inherited_product_profile_ref",
            "write_mode": "stage_inherited_ref",
            "fields": {"inherited_ref": "7-7-7.8-5-1"},
        }
        preview_profile = self.client.post("/portal/api/data/write/preview", json={"intent": intent_profile})
        self.assertEqual(preview_profile.status_code, 200)
        preview_profile_payload = preview_profile.get_json() or {}
        actions = [item.get("action") for item in preview_profile_payload.get("write_actions") or []]
        self.assertIn("stage_inherited_ref", actions)
        self.assertNotIn("create_target", actions)
        apply_profile = self.client.post("/portal/api/data/write/apply", json={"intent": intent_profile})
        self.assertEqual(apply_profile.status_code, 200)
        apply_profile_payload = apply_profile.get_json() or {}
        summary_profile = apply_profile_payload.get("mutation_summary") or {}
        self.assertEqual(summary_profile.get("created_count"), 0)
        self.assertEqual(summary_profile.get("reused_count"), 1)
        self.assertEqual((((self.config_payload.get("agro") or {}).get("inherited") or {}).get("product_profile_ref")), "7-7-7.8-5-1")

        intent_log = {
            "intent_type": "profile_field",
            "field_id": "inherited_supply_log_ref",
            "write_mode": "stage_inherited_ref",
            "fields": {"inherited_ref": "7-7-7.8-4-1"},
        }
        preview_log = self.client.post("/portal/api/data/write/preview", json={"intent": intent_log})
        self.assertEqual(preview_log.status_code, 200)
        preview_log_payload = preview_log.get_json() or {}
        actions_log = [item.get("action") for item in preview_log_payload.get("write_actions") or []]
        self.assertIn("stage_inherited_ref", actions_log)
        apply_log = self.client.post("/portal/api/data/write/apply", json={"intent": intent_log})
        self.assertEqual(apply_log.status_code, 200)
        apply_log_payload = apply_log.get_json() or {}
        summary_log = apply_log_payload.get("mutation_summary") or {}
        self.assertEqual(summary_log.get("created_count"), 0)
        self.assertEqual(summary_log.get("reused_count"), 1)
        self.assertEqual((((self.config_payload.get("agro") or {}).get("inherited") or {}).get("supply_log_ref")), "7-7-7.8-4-1")

    def test_sandbox_routes_compile_decode_stage_and_migration_dry_run(self):
        self.anthology_rows.update(
            {
                "0-0-1": [["0-0-1", "0", "0"], ["top"]],
                "0-0-2": [["0-0-2", "0", "0"], ["tiu"]],
                "1-1-1": [["1-1-1", "0-0-2", "315569254450000000000000000000000000000"], ["sec-babel"]],
                "1-1-2": [["1-1-2", "0-0-1", "946707763350000000"], ["utc-bacillete"]],
                "2-1-1": [["2-1-1", "1-1-2", "1"], ["second-isolette"]],
                "3-1-1": [["3-1-1", "2-1-1", "0"], ["utc-babelette"]],
                "4-2-1": [["4-2-1", "1-1-1", "63072000000", "3-1-1", "1"], ["y2k-event"]],
                "5-0-1": [["5-0-1", "4-2-1", "[\"4-2-1\"]"], ["samras_set_local_txa"]],
                "5-0-2": [["5-0-2", "4-2-1", "[\"4-2-1\"]"], ["samras_set_local_msn"]],
            }
        )
        listed = self.client.get("/portal/api/data/sandbox/resources")
        self.assertEqual(listed.status_code, 200)
        self.assertTrue((listed.get_json() or {}).get("ok"))

        compiled = self.client.post(
            "/portal/api/data/sandbox/mss/compile",
            json={"resource_id": "route-test-mss", "selected_refs": ["4-2-1"]},
        )
        self.assertEqual(compiled.status_code, 200)
        compiled_payload = compiled.get_json() or {}
        self.assertTrue(compiled_payload.get("ok"))
        bitstring = str(((compiled_payload.get("compiled_payload") or {}).get("bitstring")) or "")
        self.assertTrue(bitstring)

        decoded = self.client.post(
            "/portal/api/data/sandbox/mss/decode",
            json={"resource_id": "route-test-mss-decode", "bitstring": bitstring},
        )
        self.assertEqual(decoded.status_code, 200)
        self.assertTrue((decoded.get_json() or {}).get("ok"))

        staged = self.client.post(
            "/portal/api/data/sandbox/resources/route-test-resource/stage",
            json={"payload": {"kind": "manual", "value": {"a": 1}}},
        )
        self.assertEqual(staged.status_code, 200)
        self.assertTrue((staged.get_json() or {}).get("ok"))

        singular_seed = {
            "schema": "mycite.sandbox.singular_mss_resource.v1",
            "resource_id": "route-singular",
            "resource_kind": "txa",
            "origin_kind": "local",
            "source_portal": "9-9-9",
            "source_ref": "5-0-1",
            "draft_state": {"selected_ids": ["4-2-1"], "compact_payload": self.anthology_rows},
            "canonical_state": {"selected_ids": ["4-2-1"], "compact_payload": self.anthology_rows},
            "mss_form": {"bitstring": "", "wire_variant": ""},
            "abstraction_root": "4-2-1",
            "compile_metadata": {"compiled": False, "warnings": []},
            "updated_at": 0,
        }
        saved = self.client.post("/portal/api/data/sandbox/resources/route-singular/save", json={"payload": singular_seed})
        self.assertEqual(saved.status_code, 200)
        compiled_singular = self.client.post("/portal/api/data/sandbox/resources/route-singular/compile", json={})
        self.assertEqual(compiled_singular.status_code, 200)
        self.assertTrue((compiled_singular.get_json() or {}).get("ok"))
        contact_exposed = self.client.get("/portal/api/data/sandbox/exposed/contact_card")
        self.assertEqual(contact_exposed.status_code, 200)
        exposed_payload = contact_exposed.get_json() or {}
        sandbox_resources = exposed_payload.get("sandbox_exposed_resources") or []
        picked = [item for item in sandbox_resources if str(item.get("resource_id")) == "route-singular"]
        self.assertTrue(picked)
        first_value = ((picked[0] or {}).get("value") or {}) if isinstance(picked[0], dict) else {}
        self.assertIn("published_value", first_value)

        anthology_path = Path(self._tmpdir.name) / "anthology.json"
        anthology_path.write_text(json.dumps(self.anthology_rows, indent=2) + "\n", encoding="utf-8")
        migrated = self.client.post("/portal/api/data/sandbox/migrate/fnd_samras", json={"apply": False})
        self.assertEqual(migrated.status_code, 200)
        migrated_payload = migrated.get_json() or {}
        self.assertTrue(migrated_payload.get("ok"))
        self.assertIn("5-0-1", migrated_payload.get("exact_live_txa_msn_rows") or [])

    def test_resource_inventory_routes_are_index_backed_and_ignore_legacy_root_files(self):
        root = Path(self._tmpdir.name)
        (root / "samras-msn.legacy.json").write_text(
            json.dumps({"4-1-9": [["4-1-9", "2-1-7", "9"], ["legacy-root"]]}, indent=2) + "\n",
            encoding="utf-8",
        )
        local = self.client.get("/portal/api/data/resources/local")
        self.assertEqual(local.status_code, 200)
        local_payload = local.get_json() or {}
        self.assertTrue(local_payload.get("ok"))
        self.assertEqual(local_payload.get("resources"), [])

        migrate = self.client.post("/portal/api/data/resources/local/migrate_legacy_samras", json={"apply": True})
        self.assertEqual(migrate.status_code, 200)
        migrated_payload = migrate.get_json() or {}
        migrated = migrated_payload.get("migrated") or []
        self.assertTrue(any(str(item.get("resource_name") or "") == "samras.msn.json" for item in migrated))

        local_after = self.client.get("/portal/api/data/resources/local")
        self.assertEqual(local_after.status_code, 200)
        resources = (local_after.get_json() or {}).get("resources") or []
        ids = [str(item.get("resource_id") or "") for item in resources]
        self.assertIn("local:samras.msn", ids)

    def test_inherited_disconnect_cleans_index_files_and_contract_sync(self):
        from _shared.portal.services.contract_store import create_contract, get_contract
        from _shared.portal.data_engine.resource_registry import (
            INHERITED_SCOPE,
            resource_file_path,
            upsert_index_entry,
            write_resource_file,
        )

        source_msn_id = "7-7-7"
        contract_id = create_contract(
            self.private_dir,
            {
                "contract_id": "contract-test-disconnect",
                "contract_type": "resource_subscription",
                "owner_msn_id": "9-9-9",
                "counterparty_msn_id": source_msn_id,
                "status": "active",
                "tracked_resource_ids": ["samras.txa"],
                "inherited_resource_sync": {
                    "resources": [
                        {
                            "source_msn_id": source_msn_id,
                            "contract_id": "contract-test-disconnect",
                            "resource_id": "samras.txa",
                            "resource_name": "samras.txa",
                            "version_hash": "before",
                            "last_sync_unix_ms": 1,
                            "next_poll_unix_ms": 2,
                            "status": "synced",
                        }
                    ]
                },
            },
            owner_msn_id="9-9-9",
        )
        inherited_path = resource_file_path(
            Path(self._tmpdir.name),
            scope=INHERITED_SCOPE,
            source_msn_id=source_msn_id,
            resource_name="samras.txa",
        )
        write_resource_file(
            inherited_path,
            {
                "schema": "mycite.portal.resource.inherited.v1",
                "resource_id": f"foreign:{source_msn_id}:samras.txa",
                "resource_kind": "inherited_snapshot",
                "scope": "inherited",
                "source_msn_id": source_msn_id,
                "anthology_compatible_payload": {"4-1-1": [["4-1-1", "2-1-1", "1"], ["txa"]]},
            },
        )
        upsert_index_entry(
            Path(self._tmpdir.name),
            scope=INHERITED_SCOPE,
            entry={
                "resource_id": f"foreign:{source_msn_id}:samras.txa",
                "resource_name": "samras.txa.json",
                "resource_kind": "inherited_snapshot",
                "scope": "inherited",
                "source_msn_id": source_msn_id,
                "path": str(inherited_path),
                "version_hash": "before",
                "updated_at": 1,
                "status": "synced",
            },
        )

        disconnect = self.client.post(
            "/portal/api/data/resources/inherited/disconnect_source",
            json={"source_msn_id": source_msn_id},
        )
        self.assertEqual(disconnect.status_code, 200)
        disconnect_payload = disconnect.get_json() or {}
        self.assertTrue(disconnect_payload.get("ok"))
        self.assertEqual(disconnect_payload.get("removed_count"), 1)
        contract_sync = disconnect_payload.get("contract_sync") or {}
        self.assertTrue(any(str(item.get("contract_id") or "") == contract_id for item in contract_sync.get("updated_contracts") or []))

        inherited_after = self.client.get("/portal/api/data/resources/inherited")
        self.assertEqual(inherited_after.status_code, 200)
        grouped = (inherited_after.get_json() or {}).get("grouped_by_source") or {}
        self.assertNotIn(source_msn_id, grouped)

        contract_after = get_contract(self.private_dir, contract_id)
        sync = contract_after.get("inherited_resource_sync") or {}
        self.assertEqual(sync.get("status"), "disconnected")
        resources = sync.get("resources") or []
        self.assertTrue(resources)
        self.assertTrue(all(str(item.get("status") or "") == "disconnected" for item in resources))

    def test_anthology_overlay_migration_route_dry_run_and_apply(self):
        anthology_path = Path(self._tmpdir.name) / "anthology.json"
        overlay_payload = {
            "1-1-2": [["1-1-2", "0-0-6", "16"], ["nominal-bacillete-16"]],
            "8-1-9": [["8-1-9", "1-1-2", "portal"], ["portal-specific"]],
        }
        anthology_path.write_text(json.dumps(overlay_payload, indent=2) + "\n", encoding="utf-8")

        dry = self.client.post("/portal/api/data/anthology/overlay/migration", json={"apply": False})
        self.assertEqual(dry.status_code, 200)
        dry_payload = dry.get_json() or {}
        self.assertTrue(dry_payload.get("ok"))
        self.assertIn("1-1-2", dry_payload.get("removed_duplicate_ids") or [])
        self.assertIn("8-1-9", dry_payload.get("kept_ids") or [])

        apply_resp = self.client.post("/portal/api/data/anthology/overlay/migration", json={"apply": True})
        self.assertEqual(apply_resp.status_code, 200)
        updated_payload = json.loads(anthology_path.read_text(encoding="utf-8"))
        self.assertNotIn("1-1-2", updated_payload)
        self.assertIn("8-1-9", updated_payload)

    def test_apply_updates_anthology_and_config_ref(self):
        response = self.client.post(
            "/portal/api/data/write/apply",
            json={
                "intent": {
                    "intent_type": "profile_field",
                    "field_id": "portal_title",
                    "template_id": "geometry.parcel",
                    "fields": {"local_id": "31-1-9", "title": "Parcel Nine"},
                }
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertTrue(payload.get("ok"))
        self.assertTrue(payload.get("created_datum_refs"))
        self.assertEqual(((payload.get("contract_mss_sync") or {}).get("triggered")), True)
        self.assertEqual((((self.config_payload.get("display") or {})).get("title")), "9-9-9.31-1-9")

    def test_geometry_preview_and_apply_routes(self):
        preview = self.client.post(
            "/portal/api/data/geometry/preview",
            json={"template_id": "geometry.plot", "fields": {"local_id": "31-1-22", "title": "Plot 22"}},
        )
        self.assertEqual(preview.status_code, 200)
        apply_response = self.client.post(
            "/portal/api/data/geometry/apply",
            json={"template_id": "geometry.plot", "fields": {"local_id": "31-1-23", "title": "Plot 23"}},
        )
        self.assertEqual(apply_response.status_code, 200)
        self.assertTrue((apply_response.get_json() or {}).get("ok"))

    def test_profile_preview_apply_reuse_with_realistic_fixture(self):
        self.anthology_rows.update(
            {
                "31-1-1": {"identifier": "31-1-1", "label": "Existing Parcel"},
                "31-1-2": {"identifier": "31-1-2", "label": "Existing Field"},
            }
        )
        self.config_payload = {
            "display": {"title": "Before"},
            "property": {"plot_refs": ["9-9-9.31-1-1"]},
        }
        intent = {
            "intent_type": "profile_field",
            "field_id": "property_plot_refs",
            "template_id": "geometry.plot",
            "fields": {"local_id": "31-1-9", "title": "Plot Nine", "field_ref": "9-9-9.31-1-2"},
        }

        preview_one = self.client.post("/portal/api/data/write/preview", json={"intent": intent})
        self.assertEqual(preview_one.status_code, 200)
        preview_one_payload = preview_one.get_json() or {}
        self.assertTrue(preview_one_payload.get("ok"))
        self.assertIn("create_target", [item.get("action") for item in preview_one_payload.get("write_actions") or []])
        self.assertIn(
            "9-9-9.31-1-9",
            (((preview_one_payload.get("config_updates") or [{}])[0]).get("next") or []),
        )

        apply_one = self.client.post("/portal/api/data/write/apply", json={"intent": intent})
        self.assertEqual(apply_one.status_code, 200)
        apply_one_payload = apply_one.get_json() or {}
        self.assertTrue(apply_one_payload.get("ok"))
        self.assertEqual(((apply_one_payload.get("mutation_summary") or {}).get("created_count")), 1)
        self.assertEqual(((apply_one_payload.get("mutation_summary") or {}).get("reused_count")), 0)

        preview_two = self.client.post("/portal/api/data/write/preview", json={"intent": intent})
        self.assertEqual(preview_two.status_code, 200)
        preview_two_payload = preview_two.get_json() or {}
        self.assertIn("reuse_existing_target", [item.get("action") for item in preview_two_payload.get("write_actions") or []])

        apply_two = self.client.post("/portal/api/data/write/apply", json={"intent": intent})
        self.assertEqual(apply_two.status_code, 200)
        apply_two_payload = apply_two.get_json() or {}
        self.assertTrue(apply_two_payload.get("ok"))
        self.assertEqual(((apply_two_payload.get("mutation_summary") or {}).get("created_count")), 0)
        self.assertEqual(((apply_two_payload.get("mutation_summary") or {}).get("reused_count")), 1)
        plot_refs = (((self.config_payload.get("property") or {}).get("plot_refs")) or [])
        self.assertEqual(plot_refs, ["9-9-9.31-1-1", "9-9-9.31-1-9"])


if __name__ == "__main__":
    unittest.main()
