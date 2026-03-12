from __future__ import annotations

import importlib.util
import importlib
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def _load_inheritance_module():
    path = Path(__file__).resolve().parents[1] / "portals" / "_shared" / "portal" / "progeny_model" / "inheritance.py"
    spec = importlib.util.spec_from_file_location("shared_progeny_inheritance_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_network_cards_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.core_services.network_cards")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class ProgenyInheritanceRuntimeTests(unittest.TestCase):
    def test_alias_overrides_when_enabled(self):
        inheritance = _load_inheritance_module()
        out = inheritance.resolve_inherited_fields(
            alias_payload={"fields": {"email": "alias@example.com", "name": "Alias"}},
            progeny_payload={"fields": {"email": "progeny@example.com", "status": "active"}},
            inheritance_rules={"alias_profile_overrides": True},
        )
        self.assertEqual(out["resolved_fields"]["email"], "alias@example.com")
        self.assertEqual(out["resolved_fields"]["status"], "active")

    def test_progeny_overrides_when_disabled(self):
        inheritance = _load_inheritance_module()
        out = inheritance.resolve_inherited_fields(
            alias_payload={"fields": {"email": "alias@example.com"}},
            progeny_payload={"fields": {"email": "progeny@example.com"}},
            inheritance_rules={"alias_profile_overrides": False},
        )
        self.assertEqual(out["resolved_fields"]["email"], "progeny@example.com")

    def test_network_cards_include_inheritance_model(self):
        network_cards = _load_network_cards_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_json(
                private_dir / "network" / "progeny" / "internal" / "member-1.json",
                {
                    "progeny_type": "member",
                    "progeny_id": "member-1",
                    "msn_id": "member-1",
                    "fields": {"email": "progeny@example.com", "status": "active"},
                },
            )
            _write_json(
                private_dir / "network" / "aliases" / "alias-1.json",
                {
                    "progeny_type": "member",
                    "member_msn_id": "member-1",
                    "fields": {"email": "alias@example.com"},
                },
            )
            config = {"inheritance_rules": {"alias_profile_overrides": True}}
            payload = network_cards.build_network_cards(private_dir, config)

            self.assertIn("model", payload)
            self.assertIn("legal_entity_baseline_classes", payload["model"])
            aliases = payload.get("alias") or []
            self.assertEqual(len(aliases), 1)
            alias_card = aliases[0]
            self.assertEqual(alias_card.get("inheritance", {}).get("matched_progeny_id"), "member-1")
            resolved_fields = alias_card.get("resolved_profile", {}).get("fields") or {}
            self.assertEqual(resolved_fields.get("email"), "alias@example.com")
            self.assertEqual(resolved_fields.get("status"), "active")


if __name__ == "__main__":
    unittest.main()
