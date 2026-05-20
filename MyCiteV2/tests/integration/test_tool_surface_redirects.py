"""Plan v2 redirect tests.

Pins that the legacy per-tool URLs (cts-gis, agro-erp, workbench-ui)
302-redirect into the unified workbench at /portal/system with the
correct surface_query parameters. External bookmarks continue to
resolve while the dedicated tool surfaces have been retired.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class ToolSurfaceRedirectTests(unittest.TestCase):
    def setUp(self) -> None:
        # The portal_host app reads its config from env. Point it at a
        # tmp authority so the route registration succeeds.
        self._tmpdir = Path(tempfile.mkdtemp(prefix="tool_redirect_"))
        self._db = self._tmpdir / "authority.sqlite3"
        self._db.touch()
        self._env_keys = (
            "PORTAL_INSTANCE_ID",
            "MYCITE_ANALYTICS_DOMAIN",
            "MYCITE_WEBAPPS_ROOT",
            "DATA_DIR",
            "PRIVATE_DIR",
            "PUBLIC_DIR",
            "MYCITE_V2_PORTAL_AUTHORITY_DB",
        )
        self._prev_env = {k: os.environ.get(k) for k in self._env_keys}
        for path_key in ("data", "private", "public", "webapps"):
            (self._tmpdir / path_key).mkdir(parents=True, exist_ok=True)
        os.environ["PORTAL_INSTANCE_ID"] = "fnd"
        os.environ["MYCITE_ANALYTICS_DOMAIN"] = "test.local"
        os.environ["MYCITE_WEBAPPS_ROOT"] = str(self._tmpdir / "webapps")
        os.environ["DATA_DIR"] = str(self._tmpdir / "data")
        os.environ["PRIVATE_DIR"] = str(self._tmpdir / "private")
        os.environ["PUBLIC_DIR"] = str(self._tmpdir / "public")
        os.environ["MYCITE_V2_PORTAL_AUTHORITY_DB"] = str(self._db)

        from MyCiteV2.instances._shared.portal_host.app import create_app
        self._app = create_app()
        self._client = self._app.test_client()

    def tearDown(self) -> None:
        import shutil
        for key, value in self._prev_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_workbench_ui_redirects_to_system_root(self) -> None:
        resp = self._client.get("/portal/system/tools/workbench-ui", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers["Location"].rstrip("/"), "/portal/system")

    def test_agro_erp_redirects_with_sandbox_filter(self) -> None:
        resp = self._client.get("/portal/system/tools/agro-erp", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("sandbox=agro_erp", resp.headers["Location"])
        self.assertTrue(resp.headers["Location"].startswith("/portal/system"))

    def test_cts_gis_redirects_with_tool_filter(self) -> None:
        resp = self._client.get("/portal/system/tools/cts-gis", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("tool=cts_gis", resp.headers["Location"])
        self.assertTrue(resp.headers["Location"].startswith("/portal/system"))


if __name__ == "__main__":
    unittest.main()
