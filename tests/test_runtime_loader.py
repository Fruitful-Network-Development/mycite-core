from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


def _add_repo_root() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    token = str(repo_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return repo_root


class RuntimeLoaderTests(unittest.TestCase):
    def test_load_runtime_flavor_module_loads_fake_flavor(self):
        _add_repo_root()
        from portal_core.composition.runtime_loader import load_runtime_flavor_module

        with TemporaryDirectory() as temp_dir:
            portals_root = Path(temp_dir)
            flavor_dir = portals_root / "_shared" / "runtime" / "flavors" / "demo"
            flavor_dir.mkdir(parents=True, exist_ok=True)
            (flavor_dir / "app.py").write_text("app = {'ok': True}\nTOKEN = 'demo'\n", encoding="utf-8")
            module = load_runtime_flavor_module(portals_root, "demo")
            self.assertEqual(module.app, {"ok": True})
            self.assertEqual(module.TOKEN, "demo")

    def test_load_runtime_flavor_module_from_env_uses_portal_runtime_flavor(self):
        _add_repo_root()
        from portal_core.composition.runtime_loader import load_runtime_flavor_module_from_env

        with TemporaryDirectory() as temp_dir:
            portals_root = Path(temp_dir)
            flavor_dir = portals_root / "_shared" / "runtime" / "flavors" / "demo"
            flavor_dir.mkdir(parents=True, exist_ok=True)
            (flavor_dir / "app.py").write_text("app = {'mode': 'env'}\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"PORTAL_RUNTIME_FLAVOR": "demo"}, clear=False):
                module = load_runtime_flavor_module_from_env(portals_root)
            self.assertEqual(module.app, {"mode": "env"})


if __name__ == "__main__":
    unittest.main()
