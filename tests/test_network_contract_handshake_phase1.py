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
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    HAS_FLASK = False
    Flask = None  # type: ignore[assignment]


FND_MSN_ID = "3-2-3-17-77-1-6-4-1-4"
SENDER_MSN_ID = "3-2-3-17-77-2-6-3-1-6"


def _load_contract_handshake_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    flavor_root = portals_root / "_shared" / "runtime" / "flavors" / "fnd"
    for token in (str(portals_root), str(flavor_root)):
        if token not in sys.path:
            sys.path.insert(0, token)
    module_path = flavor_root / "portal" / "api" / "contract_handshake.py"
    spec = importlib.util.spec_from_file_location("fnd_contract_handshake_phase1_test", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class _WorkspaceStub:
    def __init__(self):
        self.last_collection_ref = ""
        self.last_tokens: list[str] = []

    def resolve_contact_collection(self, *, collection_ref: str) -> dict:
        self.last_collection_ref = str(collection_ref or "")
        return {
            "ok": True,
            "status_code": 200,
            "source": {
                "collection_ref": collection_ref,
                "resolved_collection_ref": "8-0-7",
                "resolved_collection_identifier": "8-0-7",
                "resolution_chain": [
                    {"kind": "collection", "input_ref": collection_ref, "resolved_identifier": "8-0-7"}
                ],
            },
            "contacts": [
                {
                    "contact_identifier": "9-0-1",
                    "display_name": "Test Contact",
                    "email_local_text": "test@example.com",
                }
            ],
            "summary": {"contacts_total": 1},
            "warnings": [],
            "errors": [],
        }


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class NetworkContractHandshakePhase1Tests(unittest.TestCase):
    def _stack(self):
        module = _load_contract_handshake_module()
        temp = TemporaryDirectory()
        root = Path(temp.name)
        private_dir = root / "private"
        public_dir = root / "public"
        private_dir.mkdir(parents=True, exist_ok=True)
        public_dir.mkdir(parents=True, exist_ok=True)
        workspace = _WorkspaceStub()
        app = Flask(__name__)
        module.register_contract_handshake_routes(
            app,
            private_dir=private_dir,
            public_dir=public_dir,
            msn_id_provider=lambda: FND_MSN_ID,
            workspace=workspace,
        )
        local_keys = module.ensure_dev_keypair(
            FND_MSN_ID,
            private_dir=private_dir,
            public_dir=public_dir,
            update_contact_card=True,
        )
        sender_keys = module.ensure_dev_keypair(
            SENDER_MSN_ID,
            private_dir=private_dir,
            public_dir=public_dir,
            update_contact_card=True,
        )
        self.assertEqual(local_keys.get("ok"), "true")
        self.assertEqual(sender_keys.get("ok"), "true")
        return temp, module, app, workspace, private_dir, public_dir, sender_keys

    def test_asymmetric_grouped_routes_and_legacy_shim(self):
        temp, module, app, _workspace, private_dir, _public_dir, sender_keys = self._stack()
        try:
            client = app.test_client()

            def _signed_request(proposal_id: str) -> dict:
                proposal = {
                    "proposal_id": proposal_id,
                    "contract_id": f"contract-{proposal_id}",
                    "sender_msn_id": SENDER_MSN_ID,
                    "receiver_msn_id": FND_MSN_ID,
                    "event_datum": "4-1-77",
                    "status": "3-1-5",
                    "confirmation_callback_url": "",
                }
                return {
                    "schema": "mycite.contract.proposal.signed.v1",
                    "proposal": proposal,
                    "signature": {
                        "alg": "ed25519",
                        "signer_msn_id": SENDER_MSN_ID,
                        "signature_b64": module.sign_payload(proposal, sender_keys["private_key_path"]),
                        "signed_unix_ms": 1770000000000,
                    },
                }

            grouped_resp = client.post(
                f"/api/network/asymmetric/contracts/request/{FND_MSN_ID}",
                json=_signed_request("cp-phase1-grouped"),
            )
            self.assertEqual(grouped_resp.status_code, 202)
            self.assertTrue(grouped_resp.get_json()["ok"])

            shim_resp = client.post(
                f"/api/contracts/request/{FND_MSN_ID}",
                json=_signed_request("cp-phase1-shim"),
            )
            self.assertEqual(shim_resp.status_code, 202)
            self.assertTrue(shim_resp.get_json()["ok"])

            options_resp = client.get(f"/api/network/anonymous/options/{FND_MSN_ID}")
            self.assertEqual(options_resp.status_code, 200)
            qualifiers = options_resp.get_json().get("qualifiers") or {}
            self.assertIn("asymmetric", qualifiers)
            self.assertIn("symmetric", qualifiers)
            self.assertIn("anonymous", qualifiers)

            contact_resp = client.get(f"/api/network/anonymous/contact/{FND_MSN_ID}")
            self.assertEqual(contact_resp.status_code, 200)
            contact_payload = contact_resp.get_json()
            self.assertTrue(contact_payload.get("ok"))
            self.assertEqual((contact_payload.get("contact") or {}).get("msn_id"), FND_MSN_ID)

            log_path = private_dir / "network" / "request_log" / "request_log.ndjson"
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn(f"{SENDER_MSN_ID}.4-1-77", log_text)
            self.assertIn(f"{SENDER_MSN_ID}.3-1-5", log_text)
        finally:
            temp.cleanup()

    def test_contact_collection_source_priority_and_options_drop_daemon_wrapper(self):
        temp, _module, app, workspace, private_dir, _public_dir, _sender_keys = self._stack()
        try:
            client = app.test_client()
            alias_dir = private_dir / "network" / "aliases"
            _write_json(
                alias_dir / "alias-priority.json",
                {
                    "alias_id": "alias-priority",
                    "msn_id": FND_MSN_ID,
                    "profile_refs": {"contact_collection_ref": "8-0-7"},
                    "fields": {"contact_collection_ref": "8-0-8"},
                },
            )
            _write_json(
                alias_dir / "alias-override.json",
                {
                    "alias_id": "alias-override",
                    "msn_id": FND_MSN_ID,
                    "profile_refs": {},
                    "fields": {},
                },
            )

            priority_resp = client.get(
                "/portal/api/network/contacts/collection?alias_id=alias-priority&collection_ref=8-0-9"
            )
            self.assertEqual(priority_resp.status_code, 200)
            priority_payload = priority_resp.get_json()
            self.assertTrue(priority_payload.get("ok"))
            self.assertEqual(
                priority_payload.get("selected_source"),
                "alias.profile_refs.contact_collection_ref",
            )
            self.assertEqual(workspace.last_collection_ref, f"{FND_MSN_ID}-8-0-7")

            override_resp = client.get(
                "/portal/api/network/contacts/collection?alias_id=alias-override&collection_ref=8-0-9"
            )
            self.assertEqual(override_resp.status_code, 200)
            override_payload = override_resp.get_json()
            self.assertTrue(override_payload.get("ok"))
            self.assertEqual(override_payload.get("selected_source"), "api.collection_ref_override")
            self.assertEqual(workspace.last_collection_ref, f"{FND_MSN_ID}-8-0-9")

            options_resp = client.get(f"/api/network/anonymous/options/{FND_MSN_ID}")
            self.assertEqual(options_resp.status_code, 200)
            endpoints = options_resp.get_json().get("endpoints") or {}
            self.assertNotIn("network_daemon_resolve_references", endpoints)
        finally:
            temp.cleanup()

    def test_symmetric_renewal_envelope_behaviors(self):
        temp, module, app, _workspace, private_dir, _public_dir, _sender_keys = self._stack()
        try:
            client = app.test_client()
            contract_id = "contract-phase1-symmetric"
            key_id, key_bytes = module._load_or_create_symmetric_key(
                private_dir=private_dir,
                contract_id=contract_id,
                sender_msn_id=SENDER_MSN_ID,
                receiver_msn_id=FND_MSN_ID,
                preferred_key_id="phase1-key",
            )
            plaintext = module._renewal_plaintext(
                contract_id=contract_id,
                sender_msn_id=SENDER_MSN_ID,
                receiver_msn_id=FND_MSN_ID,
                event_datum=f"{SENDER_MSN_ID}.4-1-77",
                status=f"{SENDER_MSN_ID}.3-1-6",
                rotation_interval_seconds=3600,
                details={"source": "test"},
            )
            envelope = module._encrypt_renewal_envelope(
                key_bytes=key_bytes,
                key_id=key_id,
                contract_id=contract_id,
                sender_msn_id=SENDER_MSN_ID,
                receiver_msn_id=FND_MSN_ID,
                plaintext=plaintext,
            )

            first = client.post(f"/api/network/symmetric/contracts/{contract_id}/renew/{FND_MSN_ID}", json=envelope)
            self.assertEqual(first.status_code, 202)
            self.assertTrue(first.get_json()["ok"])

            replay = client.post(f"/api/network/symmetric/contracts/{contract_id}/renew/{FND_MSN_ID}", json=envelope)
            self.assertEqual(replay.status_code, 409)

            mismatch = dict(envelope)
            mismatch["key_id"] = "phase1-key-mismatch"
            mismatch_resp = client.post(
                f"/api/network/symmetric/contracts/{contract_id}/renew/{FND_MSN_ID}",
                json=mismatch,
            )
            self.assertEqual(mismatch_resp.status_code, 409)

            tampered = module._encrypt_renewal_envelope(
                key_bytes=key_bytes,
                key_id=key_id,
                contract_id=contract_id,
                sender_msn_id=SENDER_MSN_ID,
                receiver_msn_id=FND_MSN_ID,
                plaintext=plaintext,
            )
            tampered["aad"] = str(tampered.get("aad") or "") + "-tampered"
            tampered_resp = client.post(
                f"/api/network/symmetric/contracts/{contract_id}/renew/{FND_MSN_ID}",
                json=tampered,
            )
            self.assertIn(tampered_resp.status_code, {400, 401})

            due = client.get("/portal/api/network/symmetric/contracts/due?all=1")
            self.assertEqual(due.status_code, 200)
            due_payload = due.get_json()
            contracts = due_payload.get("contracts") or []
            self.assertTrue(any(item.get("contract_id") == contract_id for item in contracts))
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
