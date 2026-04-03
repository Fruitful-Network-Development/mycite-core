from __future__ import annotations

import importlib.util
import json
import os
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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_fnd_app_module(temp_root: Path):
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    runtime_root = portals_root / "runtime"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)

    private_dir = temp_root / "private"
    public_dir = temp_root / "public"
    data_dir = temp_root / "data"
    private_dir.mkdir(parents=True, exist_ok=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    _write_json(private_dir / "config.json", {"msn_id": FND_MSN_ID, "title": "fnd"})
    _write_json(public_dir / f"msn-{FND_MSN_ID}.json", {"msn_id": FND_MSN_ID, "title": "fnd"})
    _write_json(public_dir / f"fnd-{FND_MSN_ID}.json", {"schema": "mycite.fnd.profile.v1", "msn_id": FND_MSN_ID, "title": "fnd"})
    _write_json(public_dir / f"msn-{SENDER_MSN_ID}.json", {"msn_id": SENDER_MSN_ID, "title": "sender"})

    os.environ["PRIVATE_DIR"] = str(private_dir)
    os.environ["PUBLIC_DIR"] = str(public_dir)
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ["MSN_ID"] = FND_MSN_ID
    os.environ["MYCITE_ENABLE_DEV_KEYGEN"] = "1"
    os.environ["MYCITE_ALLOW_INSECURE_SIGNATURES"] = "0"
    os.environ["PORTAL_RUNTIME_FLAVOR"] = "fnd"
    os.environ["MYCITE_PORTALS_ROOT"] = str(portals_root)

    path = runtime_root / "app.py"
    spec = importlib.util.spec_from_file_location("fnd_contract_flow_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class ContractHandshakeFlowTests(unittest.TestCase):
    def test_request_receive_and_confirmation_receive_are_signed(self):
        with TemporaryDirectory() as temp_dir:
            module = _load_fnd_app_module(Path(temp_dir))
            client = module.app.test_client()

            from portal.services.crypto_signatures import ensure_dev_keypair, sign_payload

            sender_keys = ensure_dev_keypair(
                SENDER_MSN_ID,
                private_dir=module.PRIVATE_DIR,
                public_dir=module.PUBLIC_DIR,
            )
            self.assertEqual(sender_keys.get("ok"), "true")

            proposal = {
                "proposal_id": "cp-test-001",
                "contract_id": "contract-fnd-tff-member-001",
                "contract_type": "portal_demo_contract",
                "sender_msn_id": SENDER_MSN_ID,
                "receiver_msn_id": FND_MSN_ID,
                "owner_mss": "1010101",
                "owner_selected_refs": ["4-2-1", "4-2-2"],
                "event_datum": "4-1-77",
                "status": "3-1-5",
                "confirmation_callback_url": "",
            }
            signed_request = {
                "schema": "mycite.contract.proposal.signed.v1",
                "proposal": proposal,
                "signature": {
                    "alg": "ed25519",
                    "signer_msn_id": SENDER_MSN_ID,
                    "signature_b64": sign_payload(proposal, sender_keys["private_key_path"]),
                    "signed_unix_ms": 1770000000000,
                },
            }

            response = client.post(f"/api/contracts/request/{FND_MSN_ID}", json=signed_request)
            self.assertEqual(response.status_code, 202)
            payload = response.get_json()
            self.assertTrue(payload["ok"])
            self.assertIn("confirmation", payload)
            stored_contract = json.loads(
                (
                    module.PRIVATE_DIR
                    / "contracts"
                    / "contract-contract-fnd-tff-member-001.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(stored_contract["counterparty_mss"], "1010101")

            confirmation_payload = {
                "proposal_id": "cp-test-001",
                "contract_id": "contract-fnd-tff-member-001",
                "contract_type": "portal_demo_contract",
                "sender_msn_id": SENDER_MSN_ID,
                "receiver_msn_id": FND_MSN_ID,
                "owner_mss": "1110001",
                "owner_selected_refs": ["5-0-1"],
                "event_datum": "4-1-77",
                "status": "3-1-6",
                "confirmed_unix_ms": 1770000002000,
                "details": {"result": "accepted"},
            }
            signed_confirmation = {
                "schema": "mycite.contract.confirmation.signed.v1",
                "confirmation": confirmation_payload,
                "signature": {
                    "alg": "ed25519",
                    "signer_msn_id": SENDER_MSN_ID,
                    "signature_b64": sign_payload(confirmation_payload, sender_keys["private_key_path"]),
                    "signed_unix_ms": 1770000003000,
                },
            }

            confirm_response = client.post(
                f"/api/contracts/confirmation/{FND_MSN_ID}",
                json=signed_confirmation,
            )
            self.assertEqual(confirm_response.status_code, 202)
            self.assertTrue(confirm_response.get_json()["ok"])
            stored_contract = json.loads(
                (
                    module.PRIVATE_DIR
                    / "contracts"
                    / "contract-contract-fnd-tff-member-001.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(stored_contract["counterparty_mss"], "1110001")

            log_text = (
                module.PRIVATE_DIR / "network" / "external_events" / "external_events.ndjson"
            ).read_text(encoding="utf-8")
            self.assertIn("contract_proposal", log_text)
            self.assertIn("contract_proposal.confirmed", log_text)


if __name__ == "__main__":
    unittest.main()
