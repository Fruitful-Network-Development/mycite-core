"""--preload import smoke test.

The portal runs gunicorn with ``--preload``, so the whole app module graph is
imported at master start; a module-level import error there crashes the ENTIRE
service at boot (not just one worker). This guards that import chain. It imports
the app MODULE (not ``create_app``, which needs runtime env) so it stays
environment-free and CI-runnable.
"""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class PortalImportSmokeTests(unittest.TestCase):
    def test_portal_app_module_imports(self) -> None:
        mod = importlib.import_module("MyCiteV2.instances._shared.portal_host.app")
        self.assertTrue(callable(getattr(mod, "create_app", None)))

    def test_edited_runtime_modules_import(self) -> None:
        for name in (
            "MyCiteV2.instances._shared.runtime.utilities_extensions.site_content_extension",
            "MyCiteV2.instances._shared.runtime.utilities_extensions.resources_extension",
            "MyCiteV2.instances._shared.runtime.utilities_extensions.events",
        ):
            with self.subTest(module=name):
                self.assertIsNotNone(importlib.import_module(name))


if __name__ == "__main__":
    unittest.main()
