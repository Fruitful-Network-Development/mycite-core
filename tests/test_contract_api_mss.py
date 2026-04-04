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
except ModuleNotFoundError:  # pragma: no cover
    HAS_FLASK = False
    Flask = None  # type: ignore[assignment]


MSN_ID = "3-2-3-17-77-1-6-4-1-4"
REMOTE_MSN_ID = "3-2-3-17-77-2-6-3-1-6"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _example_payload() -> dict[str, object]:
    return {
        "0-0-1": [["0-0-1", "0", "0"], ["top"]],
        "0-0-2": [["0-0-2", "0", "0"], ["tiu"]],
        "1-1-1": [["1-1-1", "0-0-2", "315569254450000000000000000000000000000"], ["sec-babel"]],
        "1-1-2": [["1-1-2", "0-0-1", "946707763350000000"], ["utc-bacillete"]],
        "2-1-1": [["2-1-1", "1-1-2", "1"], ["second-isolette"]],
        "3-1-1": [["3-1-1", "2-1-1", "0"], ["utc-babelette"]],
        "4-2-1": [["4-2-1", "1-1-1", "63072000000", "3-1-1", "1"], ["y2k-event"]],
        "4-2-2": [["4-2-2", "1-1-1", "63072000000", "3-1-1", "3153600000"], ["21st_century-event"]],
    }


def _load_fnd_app_module(temp_root: Path):
    repo_root = Path(__file__).resolve().parents[1]
    instances_root = repo_root / "instances"
    runtime_root = instances_root / "_shared" / "runtime" / "flavors" / "fnd"
    token = str(repo_root)
    if token not in sys.path:
        sys.path.insert(0, token)

    private_dir = temp_root / "private"
    public_dir = temp_root / "public"
    data_dir = temp_root / "data"
    private_dir.mkdir(parents=True, exist_ok=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    _write_json(private_dir / "config.json", {"msn_id": MSN_ID, "title": "fnd"})
    _write_json(public_dir / f"msn-{MSN_ID}.json", {"msn_id": MSN_ID, "title": "fnd"})
    _write_json(public_dir / f"fnd-{MSN_ID}.json", {"schema": "mycite.fnd.profile.v1", "msn_id": MSN_ID, "title": "fnd"})
    _write_json(data_dir / "anthology.json", _example_payload())

    os.environ["PRIVATE_DIR"] = str(private_dir)
    os.environ["PUBLIC_DIR"] = str(public_dir)
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ["MSN_ID"] = MSN_ID
    os.environ["PORTAL_RUNTIME_FLAVOR"] = "fnd"
    os.environ["MYCITE_PORTALS_ROOT"] = str(instances_root)

    path = runtime_root / "app.py"
    spec = importlib.util.spec_from_file_location("fnd_contract_api_mss_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class ContractApiMssTests(unittest.TestCase):
    def test_contract_create_patch_and_legacy_read_compat(self):
        with TemporaryDirectory() as temp_dir:
            module = _load_fnd_app_module(Path(temp_dir))
            legacy_path = module.PRIVATE_DIR / "network" / "contracts" / "msn-legacy.contract-remote.json"
            _write_json(
                legacy_path,
                {
                    "schema": "mycite.portal.contract.v1",
                    "contract_id": "msn-legacy.contract-remote",
                    "contract_type": "portal_demo_contract",
                    "owner_msn_id": MSN_ID,
                    "counterparty_msn_id": REMOTE_MSN_ID,
                    "owner_mss": [],
                    "counterparty_mss": [],
                    "status": "active",
                },
            )

            client = module.app.test_client()
            legacy_resp = client.get("/portal/api/contracts/msn-legacy.contract-remote?msn_id=" + MSN_ID)
            self.assertEqual(legacy_resp.status_code, 200)
            legacy_contract = legacy_resp.get_json()["contract"]
            self.assertEqual(legacy_contract["schema"], "mycite.portal.contract.v2")
            self.assertEqual(legacy_contract["owner_mss"], "")

            create_resp = client.post(
                "/portal/api/contracts?msn_id=" + MSN_ID,
                json={
                    "contract_type": "portal_demo_contract",
                    "counterparty_msn_id": REMOTE_MSN_ID,
                    "owner_selected_refs": ["4-2-1", "4-2-2"],
                    "owner_mss": "10101",
                },
            )
            self.assertEqual(create_resp.status_code, 200)
            create_payload = create_resp.get_json()
            contract_id = create_payload["contract_id"]
            self.assertTrue(create_payload["mss"]["owner_mss"])
            self.assertNotEqual(create_payload["mss"]["owner_mss"], "10101")
            self.assertEqual(create_payload["mss"]["owner_preview"]["wire_variant"], "canonical")

            get_resp = client.get(
                f"/portal/api/contracts/{contract_id}?msn_id={MSN_ID}&include_mss=1"
            )
            self.assertEqual(get_resp.status_code, 200)
            get_payload = get_resp.get_json()
            self.assertEqual(get_payload["mss"]["owner_preview"]["root_identifier"], "5-0-1")
            self.assertEqual(get_payload["mss"]["owner_preview"]["wire_variant"], "canonical")
            self.assertIn("mss.owner_context", get_payload["contract"].get("payload_registry") or {})
            self.assertTrue(get_payload["contract"].get("payload_history"))

            patch_resp = client.patch(
                f"/portal/api/contracts/{contract_id}?msn_id={MSN_ID}",
                json={"counterparty_mss": "10101", "owner_selected_refs": ["4-2-1", "4-2-2"], "owner_mss": "111"},
            )
            self.assertEqual(patch_resp.status_code, 200)
            patch_payload = patch_resp.get_json()
            self.assertEqual(patch_payload["contract"]["counterparty_mss"], "10101")
            self.assertNotEqual(patch_payload["contract"]["owner_mss"], "111")
            self.assertIn("mss.counterparty_context", patch_payload["contract"].get("payload_registry") or {})


if __name__ == "__main__":
    unittest.main()
