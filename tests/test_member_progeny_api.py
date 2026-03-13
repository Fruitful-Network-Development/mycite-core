from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    from flask import Flask

    HAS_FLASK = True
except ModuleNotFoundError:  # pragma: no cover - environment-dependent
    HAS_FLASK = False
    Flask = None  # type: ignore[assignment]


def _load_tenant_progeny_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    flavor_root = portals_root / "_shared" / "runtime" / "flavors" / "fnd"
    for token in (str(portals_root), str(flavor_root)):
        if token not in sys.path:
            sys.path.insert(0, token)
    path = flavor_root / "portal" / "api" / "tenant_progeny.py"
    spec = importlib.util.spec_from_file_location("fnd_tenant_progeny_api_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class MemberProgenyApiTests(unittest.TestCase):
    def test_members_endpoint_reads_legacy_tenant_file(self):
        module = _load_tenant_progeny_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            app = Flask(__name__)

            _write_json(
                private_dir / "progeny" / "tenant" / "1.json",
                {
                    "tenant_id": "1",
                    "tenant_msn_id": "3-2-3-17-77-2-6-1-1-2",
                    "display": {"title": "Legacy Tenant"},
                    "capabilities": {"paypal": True, "aws": True},
                    "profile_refs": {"aws_emailer_list_ref": "10-0-1"},
                },
            )

            module.register_tenant_progeny_routes(app, private_dir=private_dir)
            client = app.test_client()

            response = client.get("/portal/api/progeny/members")
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["schema"], "mycite.progeny.member.list.v1")
            self.assertEqual(payload["items"][0]["member_id"], "1")
            self.assertEqual(payload["items"][0]["tenant_id"], "1")

    def test_member_put_writes_canonical_member_profile_only(self):
        module = _load_tenant_progeny_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            app = Flask(__name__)
            module.register_tenant_progeny_routes(app, private_dir=private_dir)
            client = app.test_client()

            response = client.put(
                "/portal/api/progeny/members/2",
                json={
                    "display": {"title": "Member Two"},
                    "capabilities": {"paypal": True, "aws": False},
                    "profile_refs": {"paypal_profile_id": "paypal:member:2"},
                },
            )
            self.assertEqual(response.status_code, 200)

            canonical_path = private_dir / "network" / "progeny" / "member_progeny" / "2.json"
            legacy_path = private_dir / "progeny" / "tenant" / "2.json"
            self.assertTrue(canonical_path.exists())
            self.assertFalse(legacy_path.exists())

            legacy_get = client.get("/portal/api/progeny/tenants/2")
            self.assertEqual(legacy_get.status_code, 200)
            payload = legacy_get.get_json()
            self.assertEqual(payload["item"]["member_id"], "2")
            self.assertEqual(payload["item"]["tenant_id"], "2")
            self.assertIn("deprecation", payload)


if __name__ == "__main__":
    unittest.main()
