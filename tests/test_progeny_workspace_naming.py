from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def _load_workspace_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    flavor_root = portals_root / "_shared" / "runtime" / "flavors" / "fnd"
    for token in (str(portals_root), str(flavor_root)):
        if token not in sys.path:
            sys.path.insert(0, token)
    path = flavor_root / "portal" / "services" / "progeny_workspace.py"
    spec = importlib.util.spec_from_file_location("fnd_progeny_workspace_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProgenyWorkspaceNamingTests(unittest.TestCase):
    def test_canonical_logical_id_and_filename_mapping(self):
        mod = _load_workspace_module()
        logical = mod.canonical_logical_instance_id("3-2-3-17-77-1-6-4-1-4", "member", "3-2-3-17-77-2-6-3-1-6")
        self.assertEqual(
            logical,
            "progeny.3-2-3-17-77-1-6-4-1-4.member.3-2-3-17-77-2-6-3-1-6",
        )
        filename = mod.canonical_instance_filename("3-2-3-17-77-1-6-4-1-4", "member", "3-2-3-17-77-2-6-3-1-6")
        self.assertEqual(
            filename,
            "msn-3-2-3-17-77-1-6-4-1-4.member-3-2-3-17-77-2-6-3-1-6.json",
        )

    def test_load_instance_accepts_logical_id(self):
        mod = _load_workspace_module()
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            target = private_dir / "network" / "progeny" / "msn-provider.member-alias.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps({"profile_type": "member", "alias_associated_msn_id": "alias", "msn_id": "alias"}) + "\n",
                encoding="utf-8",
            )
            record = mod.load_instance(private_dir, "progeny.provider.member.alias")
            self.assertIsNotNone(record)
            self.assertEqual((record or {}).get("instance_id"), "msn-provider.member-alias")


if __name__ == "__main__":
    unittest.main()
