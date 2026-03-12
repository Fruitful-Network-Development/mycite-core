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
    module_path = Path(__file__).resolve().parents[1] / "portals" / "_shared" / "portal" / "datum_refs.py"
    spec = importlib.util.spec_from_file_location("shared_datum_refs_test", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_fnd_request_log_store():
    portal_root = Path(__file__).resolve().parents[1] / "portals" / "mycite-le_fnd"
    token = str(portal_root)
    if token in sys.path:
        sys.path.remove(token)
    sys.path.insert(0, token)
    for module_name in ("portal.services.request_log_store", "portal.services.datum_refs", "portal"):
        sys.modules.pop(module_name, None)
    return importlib.import_module("portal.services.request_log_store")


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


class RequestLogDotWriteTests(unittest.TestCase):
    def test_request_log_writes_dot_and_reads_legacy_hyphen(self):
        request_log_store = _load_fnd_request_log_store()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)

            request_log_store.append_event(
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
            request_log_store.append_event(
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

            log_path = private_dir / "network" / "request_log" / "request_log.ndjson"
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

            read_back = request_log_store.read_events(private_dir, MSN_ID, limit=20, offset=0, reverse=False)
            self.assertLessEqual(read_back.parse_errors, 1)
            self.assertGreaterEqual(read_back.total_lines, 2)


if __name__ == "__main__":
    unittest.main()
