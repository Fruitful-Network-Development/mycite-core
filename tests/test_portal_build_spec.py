from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def _load_portal_build_module():
    path = Path(__file__).resolve().parents[1] / "instances" / "scripts" / "portal_build.py"
    spec = importlib.util.spec_from_file_location("portal_build_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PortalBuildSpecTests(unittest.TestCase):
    def test_capture_is_stable_and_filters_legacy_tools(self):
        module = _load_portal_build_module()
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            portal_dir = root / "mycite-demo"
            state_root = root / "state"
            (portal_dir / "private" / "network" / "aliases").mkdir(parents=True, exist_ok=True)
            (portal_dir / "private" / "network" / "progeny" / "member_progeny").mkdir(parents=True, exist_ok=True)
            (portal_dir / "public").mkdir(parents=True, exist_ok=True)
            (state_root / "private").mkdir(parents=True, exist_ok=True)
            (state_root / "public").mkdir(parents=True, exist_ok=True)
            (state_root / "data").mkdir(parents=True, exist_ok=True)

            msn_id = "3-2-3-demo"
            repo_config = {
                "msn_id": msn_id,
                "schema": "mycite.profile.v0",
                "title": "demo",
                "enabled_tools": ["data_tool", "keep_one", "legacy_admin", "keep_two", "paypal_demo"],
                "data_tool": {"default_mode": "general"},
                "organization_config": {"file_name": "demo.json"},
            }
            state_config = {
                "msn_id": msn_id,
                "schema": "mycite.profile.v0",
                "title": "demo",
                "tools_configuration": [
                    {"tool_id": "keep_two", "mount_target": "utilities"},
                    {"tool_id": "keep_one", "mount_target": "peripherals.tools"},
                ],
                "progeny": {
                    "admin": {"poc": ["alias-poc.json"]},
                    "member": {"tenant": ["member-tenant.json"], "board_member": ["member-board_member.json"]},
                },
                "organization_config": {
                    "default_values": {
                        "legal_entity_defaults": {
                            "role_groups": {"members": ["m1"], "users": [], "poc_admin": ["a1"]},
                        }
                    }
                },
                "property": {"title": "state-property"},
            }
            hosted = {"type": "demo_hosted", "type_values": {"hero": "demo"}}
            msn_card = {"msn_id": msn_id, "title": "demo", "public_key": "abc"}
            fnd_card = {"schema": "mycite.fnd.profile.v1", "msn_id": msn_id, "title": "demo"}

            (portal_dir / "private" / f"mycite-config-{msn_id}.json").write_text(json.dumps(repo_config) + "\n", encoding="utf-8")
            (portal_dir / "private" / "network" / "hosted.json").write_text(json.dumps(hosted) + "\n", encoding="utf-8")
            (portal_dir / "private" / "network" / "aliases" / "alias-demo.json").write_text("{}\n", encoding="utf-8")
            (portal_dir / "private" / "network" / "progeny" / "member_progeny" / "member-config.json").write_text("{}\n", encoding="utf-8")
            (portal_dir / "public" / f"msn-{msn_id}.json").write_text(json.dumps(msn_card) + "\n", encoding="utf-8")
            (portal_dir / "public" / f"fnd-{msn_id}.json").write_text(json.dumps(fnd_card) + "\n", encoding="utf-8")

            (state_root / "private" / "config.json").write_text(json.dumps(state_config) + "\n", encoding="utf-8")
            (state_root / "data" / "anthology.json").write_text(json.dumps({"4-0-1": {"magnitude": "demo"}}) + "\n", encoding="utf-8")

            spec_a = module.build_portal_spec("mycite-demo", portal_dir, state_root, "demo", "demo")
            spec_b = module.build_portal_spec("mycite-demo", portal_dir, state_root, "demo", "demo")

            self.assertEqual(spec_a, spec_b)
            self.assertEqual(spec_a["runtime_flavor"], "demo")
            self.assertEqual(spec_a["tools"]["enabled"], ["keep_two", "keep_one"])
            self.assertEqual(spec_a["tools"]["core_system_surfaces"], ["data_tool"])
            self.assertEqual(
                spec_a["tools"]["configuration"],
                [
                    {"tool_id": "keep_two", "mount_target": "utilities"},
                    {"tool_id": "keep_one", "mount_target": "peripherals.tools"},
                ],
            )
            self.assertEqual(spec_a["private_config"]["canonical"]["property"]["title"], "state-property")
            self.assertIn("data_tool", spec_a["private_config"]["canonical"])
            self.assertEqual(
                spec_a["private_config"]["canonical"]["tools_configuration"],
                [
                    {"tool_id": "keep_two", "mount_target": "utilities"},
                    {"tool_id": "keep_one", "mount_target": "peripherals.tools"},
                ],
            )
            self.assertNotIn("enabled_tools", spec_a["private_config"]["canonical"])
            self.assertEqual(
                spec_a["private_config"]["canonical"]["progeny"],
                {
                    "admin": ["alias-admin.json"],
                    "member": ["member-member.json"],
                    "user": [],
                },
            )
            role_groups = (
                spec_a["private_config"]["canonical"]["organization_config"]["default_values"]["legal_entity_defaults"]["role_groups"]
            )
            self.assertEqual(role_groups["admins"], ["a1"])
            self.assertEqual(role_groups["members"], ["m1"])
            self.assertEqual(role_groups["users"], [])

    def test_materialize_writes_state_without_touching_anthology(self):
        module = _load_portal_build_module()
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            portal_dir = root / "mycite-demo"
            target_root = root / "target-state"
            (portal_dir / "private" / "network" / "aliases").mkdir(parents=True, exist_ok=True)
            (portal_dir / "public").mkdir(parents=True, exist_ok=True)
            (target_root / "data").mkdir(parents=True, exist_ok=True)

            (portal_dir / "private" / "network" / "aliases" / "alias-demo.json").write_text("{\"ok\":true}\n", encoding="utf-8")
            build_spec = {
                "schema": module.BUILD_SCHEMA,
                "portal_id": "mycite-demo",
                "portal_instance_id": "demo",
                "state_root_hint": str(target_root),
                "meta": {"msn_id": "3-2-3-demo", "title": "demo"},
                "tools": {
                    "configuration": [{"tool_id": "keep_one", "mount_target": "peripherals.tools"}],
                    "enabled": ["keep_one"],
                    "core_system_surfaces": ["data_tool"],
                    "retired": ["legacy_admin", "paypal_demo"],
                    "mount_targets": {"keep_one": "peripherals.tools"},
                },
                "private_config": {
                    "canonical": {"msn_id": "3-2-3-demo", "schema": "mycite.profile.v0", "title": "demo"},
                    "legacy_compat": [
                        {
                            "filename": "mycite-config-3-2-3-demo.json",
                            "payload": {"msn_id": "3-2-3-demo", "schema": "mycite.profile.v0", "title": "demo"},
                        }
                    ],
                },
                "hosted": {"filename": "hosted.json", "payload": {"type": "demo"}},
                "public_profiles": {
                    "msn_card": {"filename": "msn-3-2-3-demo.json", "payload": {"msn_id": "3-2-3-demo"}},
                    "fnd_card": {"filename": "fnd-3-2-3-demo.json", "payload": {"msn_id": "3-2-3-demo"}},
                },
                "seed_files": [{"source": "private/network/aliases/alias-demo.json", "target": "private/network/aliases/alias-demo.json"}],
                "anthology": {
                    "authoritative": False,
                    "path_hint": str(target_root / "data" / "anthology.json"),
                    "sha256": "",
                    "notes": ["do not overwrite"],
                },
            }
            build_path = portal_dir / "build.json"
            build_path.parent.mkdir(parents=True, exist_ok=True)
            build_path.write_text(json.dumps(build_spec, indent=2) + "\n", encoding="utf-8")

            anthology_path = target_root / "data" / "anthology.json"
            anthology_payload = {"4-0-1": {"magnitude": "preserve"}}
            anthology_path.write_text(json.dumps(anthology_payload) + "\n", encoding="utf-8")

            module.materialize_build_spec(build_path, target_root)

            canonical = json.loads((target_root / "private" / "config.json").read_text(encoding="utf-8"))
            legacy = json.loads((target_root / "private" / "mycite-config-3-2-3-demo.json").read_text(encoding="utf-8"))
            self.assertFalse((target_root / "private" / "tools.manifest.json").exists())
            self.assertNotIn("enabled_tools", canonical)
            self.assertNotIn("enabled_tools", legacy)
            self.assertEqual(
                canonical["tools_configuration"],
                [{"tool_id": "keep_one", "mount_target": "peripherals.tools"}],
            )
            self.assertTrue((target_root / "private" / "network" / "aliases" / "alias-demo.json").exists())
            self.assertEqual(
                json.loads(anthology_path.read_text(encoding="utf-8")),
                anthology_payload,
            )


if __name__ == "__main__":
    unittest.main()
