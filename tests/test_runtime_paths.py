from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def _load_runtime_paths_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.runtime_paths")


class RuntimePathsTests(unittest.TestCase):
    def test_request_log_prefers_canonical_network_path(self):
        runtime_paths = _load_runtime_paths_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            canonical = runtime_paths.request_log_path(private_dir)
            legacy = private_dir / "request_log" / "alpha.ndjson"
            canonical.parent.mkdir(parents=True, exist_ok=True)
            legacy.parent.mkdir(parents=True, exist_ok=True)
            canonical.write_text("", encoding="utf-8")
            legacy.write_text("", encoding="utf-8")

            paths = runtime_paths.request_log_read_paths(private_dir, "alpha")
            self.assertEqual(paths[0], canonical)
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
            legacy_dir = runtime_paths.network_dir(private_dir) / "contracts"
            canonical_dir.mkdir(parents=True, exist_ok=True)
            legacy_dir.mkdir(parents=True, exist_ok=True)

            read_dirs = runtime_paths.contract_read_dirs(private_dir)
            self.assertEqual(read_dirs[0], canonical_dir)
            self.assertIn(legacy_dir, read_dirs)


if __name__ == "__main__":
    unittest.main()
