from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def _load_workspace_stack():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    flavor_root = portals_root / "_shared" / "runtime" / "flavors" / "fnd"
    for token in (str(flavor_root), str(portals_root)):
        if token not in sys.path:
            sys.path.insert(0, token)

    from data.engine.workspace import Workspace  # type: ignore
    from data.storage_json import JsonStorageBackend  # type: ignore

    return Workspace, JsonStorageBackend


class WorkspaceAitasDaemonTests(unittest.TestCase):
    def _workspace(self):
        Workspace, JsonStorageBackend = _load_workspace_stack()
        tmp = TemporaryDirectory()
        data_dir = Path(tmp.name)

        anthology = {
            "1-1-1": [["1-1-1", "", ""], ["Root"]],
            "1-1-2": [["1-1-2", "1-1-1", "0"], ["Child"]],
            "2-1-1": [["2-1-1", "1-1-2", "CF69268F1894171F"], ["Spatial Point"]],
        }
        (data_dir / "anthology.json").write_text(json.dumps(anthology, indent=2) + "\n", encoding="utf-8")

        storage = JsonStorageBackend(data_dir)
        workspace = Workspace(storage, config={})
        return tmp, workspace

    def test_aitas_phase_transitions(self):
        tmp, workspace = self._workspace()
        try:
            nav = workspace.apply_directive({"action": "nav", "subject": "anthology", "method": "top_level_view", "args": {}})
            self.assertEqual(nav["state"]["aitas_phase"], "navigate")

            inv_focus = workspace.apply_directive({"action": "inv", "subject": "1-1-1", "method": "summary", "args": {}})
            self.assertEqual(inv_focus["state"]["aitas_phase"], "focus")

            inv_detail = workspace.apply_directive({"action": "inv", "subject": "1-1-1", "method": "abstraction_path", "args": {}})
            self.assertEqual(inv_detail["state"]["aitas_phase"], "investigate")

            med = workspace.apply_directive({"action": "med", "subject": "geographic", "method": "spacial", "args": {"value": "geographic"}})
            self.assertEqual(med["state"]["aitas_phase"], "mediate")
            self.assertEqual(med["state"]["aitas_context"].get("spatial"), "geographic")
            self.assertEqual(med["state"]["aitas_context"].get("spacial"), "geographic")
        finally:
            tmp.cleanup()

    def test_daemon_token_resolution_uses_mediation(self):
        tmp, workspace = self._workspace()
        try:
            payload = workspace.daemon_resolve_tokens(
                tokens=["2-1-1"],
                standard_id="coordinate_fixed_hex",
                context={},
            )
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["standard_id"], "coordinate_fixed_hex")
            self.assertEqual(len(payload["resolved"]), 1)
            row = payload["resolved"][0]
            self.assertEqual(row["source"], "anthology_datum")
            self.assertEqual(row["resolved_identifier"], "2-1-1")
            mediation = row.get("mediation") or {}
            self.assertTrue(mediation.get("ok"))
            self.assertEqual(mediation.get("standard_id"), "coordinate")
            self.assertIn("value", mediation)
        finally:
            tmp.cleanup()

    def test_resolve_contact_collection(self):
        tmp, workspace = self._workspace()
        try:
            contact_result = workspace.append_anthology_datum(
                layer=7,
                value_group=1,
                reference="3-1-3",
                magnitude="74657374406578616D706C652E636F6D",
                label="Test Contact",
                pairs=[
                    {"reference": "3-1-3", "magnitude": "74657374406578616D706C652E636F6D"},
                    {"reference": "6-1-2", "magnitude": "work"},
                ],
            )
            self.assertTrue(contact_result.get("ok"))
            contact_identifier = str((contact_result.get("created") or {}).get("identifier") or "")
            self.assertTrue(contact_identifier)

            collection_result = workspace.append_anthology_datum(
                layer=8,
                value_group=0,
                reference=contact_identifier,
                magnitude="0",
                label="Contact Collection",
            )
            self.assertTrue(collection_result.get("ok"))
            collection_identifier = str((collection_result.get("created") or {}).get("identifier") or "")
            self.assertTrue(collection_identifier)

            payload = workspace.resolve_contact_collection(collection_ref=collection_identifier)
            self.assertTrue(payload.get("ok"))
            self.assertEqual(((payload.get("source") or {}).get("resolved_collection_identifier")), collection_identifier)
            self.assertEqual(((payload.get("summary") or {}).get("contacts_total")), 1)
            first_contact = (payload.get("contacts") or [{}])[0]
            self.assertEqual(str(first_contact.get("email_local_text") or "").lower(), "test@example.com")
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
