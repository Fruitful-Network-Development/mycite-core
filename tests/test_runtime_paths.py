from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def _load_runtime_paths_module():
    repo_root = Path(__file__).resolve().parents[1]
    token = str(repo_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("mycite_core.runtime_paths")


class RuntimePathsTests(unittest.TestCase):
    def test_external_events_prefer_canonical_network_path(self):
        runtime_paths = _load_runtime_paths_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            canonical = runtime_paths.external_event_log_path(private_dir)
            compatibility = private_dir / "network" / "request_log" / "request_log.ndjson"
            legacy = private_dir / "request_log" / "alpha.ndjson"
            canonical.parent.mkdir(parents=True, exist_ok=True)
            compatibility.parent.mkdir(parents=True, exist_ok=True)
            legacy.parent.mkdir(parents=True, exist_ok=True)
            canonical.write_text("", encoding="utf-8")
            compatibility.write_text("", encoding="utf-8")
            legacy.write_text("", encoding="utf-8")

            paths = runtime_paths.external_event_read_paths(private_dir, "alpha")
            self.assertEqual(paths[0], canonical)
            self.assertIn(compatibility, paths)
            self.assertIn(legacy, paths)

    def test_member_profiles_prefer_network_progeny(self):
        runtime_paths = _load_runtime_paths_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            canonical_dir = runtime_paths.member_progeny_dir(private_dir)
            legacy_dir = runtime_paths.legacy_tenant_progeny_dir(private_dir)
            canonical_dir.mkdir(parents=True, exist_ok=True)
            legacy_dir.mkdir(parents=True, exist_ok=True)

            read_dirs = runtime_paths.member_profile_read_dirs(private_dir)
            self.assertEqual(read_dirs[0], canonical_dir)
            self.assertIn(legacy_dir, read_dirs)

    def test_contracts_prefer_private_contracts_over_network_contracts(self):
        runtime_paths = _load_runtime_paths_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            canonical_dir = runtime_paths.contracts_dir(private_dir)
            canonical_dir.mkdir(parents=True, exist_ok=True)

            read_dirs = runtime_paths.contract_read_dirs(private_dir)
            self.assertEqual(read_dirs, [canonical_dir])

    def test_reference_exchange_and_local_audit_paths_are_declared(self):
        runtime_paths = _load_runtime_paths_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            self.assertEqual(
                runtime_paths.reference_subscription_registry_path(private_dir),
                private_dir / "network" / "reference_exchange" / "subscriptions.json",
            )
            self.assertEqual(runtime_paths.local_audit_path(private_dir), private_dir / "audit" / "local.ndjson")


if __name__ == "__main__":
    unittest.main()
