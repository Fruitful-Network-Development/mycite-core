from __future__ import annotations

import importlib.util
import importlib
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


MSN_ID = "3-2-3-17-77-1-6-4-1-4"


def _load_shared_datum_refs():
    repo_root = Path(__file__).resolve().parents[1]
    token = str(repo_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("mycite_core.datum_refs")


def _load_external_event_store():
    repo_root = Path(__file__).resolve().parents[1]
    token = str(repo_root)
    if token in sys.path:
        sys.path.remove(token)
    sys.path.insert(0, token)
    for module_name in ("mycite_core.external_events.store", "mycite_core.datum_refs", "mycite_core"):
        sys.modules.pop(module_name, None)
    return importlib.import_module("mycite_core.external_events.store")


class DatumRefContractTests(unittest.TestCase):
    def test_parse_accepts_local_hyphen_dot_and_normalizes_dot(self):
        refs = _load_shared_datum_refs()

        local = refs.parse_datum_ref("4-1-77")
        self.assertEqual(local.source_format, "local")
        self.assertEqual(local.datum_address, "4-1-77")
        self.assertFalse(local.qualified)

        hyphen = refs.parse_datum_ref(f"{MSN_ID}-4-1-77")
        self.assertEqual(hyphen.source_format, "qualified_hyphen")
        self.assertTrue(hyphen.qualified)
        self.assertEqual(hyphen.msn_id, MSN_ID)

        dot = refs.parse_datum_ref(f"{MSN_ID}.4-1-77")
        self.assertEqual(dot.source_format, "qualified_dot")
        self.assertTrue(dot.qualified)
        self.assertEqual(dot.msn_id, MSN_ID)

        self.assertEqual(
            refs.normalize_datum_ref(
                "4-1-77",
                local_msn_id=MSN_ID,
                require_qualified=True,
                write_format="dot",
                field_name="event_datum",
            ),
            f"{MSN_ID}.4-1-77",
        )
        self.assertEqual(
            refs.normalize_datum_ref(
                f"{MSN_ID}-4-1-77",
                local_msn_id="",
                require_qualified=True,
                write_format="dot",
                field_name="event_datum",
            ),
            f"{MSN_ID}.4-1-77",
        )
        self.assertEqual(
            refs.normalize_datum_ref(
                f"{MSN_ID}.4-1-77",
                local_msn_id="",
                require_qualified=True,
                write_format="hyphen",
                field_name="event_datum",
            ),
            f"{MSN_ID}-4-1-77",
        )

        with self.assertRaises(ValueError):
            refs.parse_datum_ref("not-a-datum")

        with self.assertRaises(ValueError):
            refs.normalize_datum_ref(
                "4-1-77",
                local_msn_id="",
                require_qualified=True,
                write_format="dot",
                field_name="event_datum",
            )


class ExternalEventDotWriteTests(unittest.TestCase):
    def test_external_event_store_writes_canonical_path_and_reads_legacy_hyphen(self):
        external_event_store = _load_external_event_store()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)

            external_event_store.append_event(
                private_dir,
                MSN_ID,
                {
                    "type": "contract_proposal",
                    "transmitter": f"msn-{MSN_ID}",
                    "receiver": "msn-3-2-3-17-77-2-6-3-1-6",
                    "event_datum": "4-1-77",
                    "status": "3-1-5",
                    "details": {"source": "local"},
                },
            )
            external_event_store.append_event(
                private_dir,
                MSN_ID,
                {
                    "type": "contract_proposal.confirmed",
                    "transmitter": f"msn-{MSN_ID}",
                    "receiver": "msn-3-2-3-17-77-2-6-3-1-6",
                    "event_datum": f"{MSN_ID}-4-1-77",
                    "status": f"{MSN_ID}-3-1-6",
                    "details": {"source": "legacy_hyphen"},
                },
            )

            log_path = private_dir / "network" / "external_events" / "external_events.ndjson"
            lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(lines[0]["event_datum"], f"{MSN_ID}.4-1-77")
            self.assertEqual(lines[0]["status"], f"{MSN_ID}.3-1-5")
            self.assertEqual(lines[1]["event_datum"], f"{MSN_ID}.4-1-77")
            self.assertEqual(lines[1]["status"], f"{MSN_ID}.3-1-6")

            legacy_event = {
                "type": "legacy",
                "transmitter": f"msn-{MSN_ID}",
                "receiver": "msn-legacy",
                "event_datum": f"{MSN_ID}-4-1-77",
                "status": f"{MSN_ID}-3-1-5",
                "ts_unix_ms": 1770000000001,
                "msn_id": MSN_ID,
            }
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(legacy_event, separators=(",", ":")) + "\\n")

            read_back = external_event_store.read_events(private_dir, MSN_ID, limit=20, offset=0, reverse=False)
            self.assertLessEqual(read_back.parse_errors, 1)
            self.assertGreaterEqual(read_back.total_lines, 3)

    def test_external_event_store_rejects_local_only_operational_events(self):
        external_event_store = _load_external_event_store()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            with self.assertRaises(external_event_store.RequestLogValidationError):
                external_event_store.append_event(
                    private_dir,
                    MSN_ID,
                    {
                        "type": "tenant.paypal.config.saved",
                        "status": "ok",
                        "tenant_msn_id": "tenant-1",
                    },
                )


if __name__ == "__main__":
    unittest.main()
