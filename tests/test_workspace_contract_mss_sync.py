from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


MSN_ID = "3-2-3-17-77-1-6-4-1-4"
REMOTE_MSN_ID = "3-2-3-17-77-2-6-3-1-6"


def _load_stack():
    repo_root = Path(__file__).resolve().parents[1]
    flavor_root = repo_root / "instances" / "_shared" / "runtime" / "flavors" / "fnd"
    for token in (str(flavor_root), str(repo_root)):
        if token not in sys.path:
            sys.path.insert(0, token)

    from data.engine.workspace import Workspace  # type: ignore
    from data.storage_json import JsonStorageBackend  # type: ignore
    from mycite_core.mss_resolution import compile_mss_payload, decode_mss_payload  # type: ignore
    from mycite_core.contract_line.store import create_contract, get_contract  # type: ignore

    return Workspace, JsonStorageBackend, compile_mss_payload, decode_mss_payload, create_contract, get_contract


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class WorkspaceContractMssSyncTests(unittest.TestCase):
    def _workspace(self):
        Workspace, JsonStorageBackend, compile_mss_payload, decode_mss_payload, create_contract, get_contract = _load_stack()
        temp = TemporaryDirectory()
        root = Path(temp.name)
        data_dir = root / "data"
        private_dir = root / "private"
        data_dir.mkdir(parents=True, exist_ok=True)
        private_dir.mkdir(parents=True, exist_ok=True)

        anthology = {
            "0-0-1": [["0-0-1", "0", "0"], ["top"]],
            "1-1-1": [["1-1-1", "0-0-1", "1"], ["first"]],
            "1-1-2": [["1-1-2", "0-0-1", "2"], ["second"]],
            "3-2-2": [["3-2-2", "0-0-1", "10"], ["point_ref"]],
            "3-2-3": [["3-2-3", "0-0-1", "20"], ["duration_ref"]],
        }
        _write_json(data_dir / "anthology.json", anthology)

        storage = JsonStorageBackend(data_dir)
        workspace = Workspace(
            storage,
            config={
                "state_path": str(private_dir / "daemon_state" / "data_workspace.json"),
                "msn_id": MSN_ID,
            },
        )

        compiled = compile_mss_payload(anthology, ["1-1-2"], local_msn_id=MSN_ID)
        contract_id = create_contract(
            private_dir,
            {
                "contract_id": "contract-sync-demo",
                "contract_type": "portal_demo_contract",
                "owner_msn_id": MSN_ID,
                "counterparty_msn_id": REMOTE_MSN_ID,
                "owner_selected_refs": ["1-1-2"],
                "owner_mss": compiled["bitstring"],
                "status": "active",
            },
            owner_msn_id=MSN_ID,
        )
        return temp, workspace, private_dir, get_contract, compile_mss_payload, decode_mss_payload, contract_id

    def test_delete_recompiles_contract_and_remaps_selected_refs(self):
        temp, workspace, private_dir, get_contract, compile_mss_payload, decode_mss_payload, contract_id = self._workspace()
        try:
            result = workspace.delete_anthology_datum(row_id="1-1-1")
            self.assertTrue(result["ok"])
            sync = result.get("contract_mss_sync") or {}
            self.assertIn(contract_id, sync.get("recompiled_contract_ids") or [])

            anthology_payload = json.loads((private_dir.parent / "data" / "anthology.json").read_text(encoding="utf-8"))
            stored_contract = get_contract(private_dir, contract_id)
            self.assertEqual(stored_contract["owner_selected_refs"], ["1-1-1"])
            expected = compile_mss_payload(anthology_payload, ["1-1-1"], local_msn_id=MSN_ID)
            self.assertEqual(stored_contract["owner_mss"], expected["bitstring"])
            self.assertEqual((decode_mss_payload(stored_contract["owner_mss"]) or {}).get("wire_variant"), "canonical_v2")
        finally:
            temp.cleanup()

    def test_append_update_and_time_series_mutations_report_contract_sync(self):
        temp, workspace, _private_dir, _get_contract, _compile_mss_payload, _decode_mss_payload, _contract_id = self._workspace()
        try:
            append_result = workspace.append_anthology_datum(
                layer=2,
                value_group=1,
                reference="1-1-2",
                magnitude="7",
                label="appended",
            )
            self.assertTrue(append_result["ok"])
            self.assertIn("contract_mss_sync", append_result)

            update_result = workspace.update_anthology_profile(
                row_id="1-1-2",
                label="second-updated",
                pairs=[{"reference": "0-0-1", "magnitude": "3"}],
            )
            self.assertTrue(update_result["ok"])
            self.assertIn("contract_mss_sync", update_result)

            ensure_result = workspace.time_series_ensure_base()
            self.assertTrue(ensure_result["ok"])
            self.assertIn("contract_mss_sync", ensure_result)

            event_result = workspace.time_series_create_event(
                point_ref="3-2-2",
                duration_ref="3-2-3",
                start_unix_s=1,
                duration_s=2,
                label="demo-event",
            )
            self.assertTrue(event_result["ok"])
            self.assertIn("contract_mss_sync", event_result)
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
