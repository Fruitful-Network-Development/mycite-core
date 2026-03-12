from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    from flask import Flask

    HAS_FLASK = True
except ModuleNotFoundError:  # pragma: no cover
    HAS_FLASK = False
    Flask = None  # type: ignore[assignment]


def _load_fnd_app_module(temp_root: Path):
    portal_root = Path(__file__).resolve().parents[1] / "portals" / "mycite-le_fnd"
    token = str(portal_root)
    if token not in sys.path:
        sys.path.insert(0, token)

    private_dir = temp_root / "private"
    public_dir = temp_root / "public"
    data_dir = temp_root / "data"
    private_dir.mkdir(parents=True, exist_ok=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    msn_id = "3-2-3-17-77-1-6-4-1-4"
    (private_dir / "config.json").write_text(json.dumps({"msn_id": msn_id}) + "\n", encoding="utf-8")
    (public_dir / f"msn-{msn_id}.json").write_text(json.dumps({"msn_id": msn_id, "title": "FND"}) + "\n", encoding="utf-8")
    (public_dir / f"fnd-{msn_id}.json").write_text(json.dumps({"schema": "mycite.fnd.profile.v1", "msn_id": msn_id, "title": "FND", "summary": "Brand"}) + "\n", encoding="utf-8")

    os.environ["PRIVATE_DIR"] = str(private_dir)
    os.environ["PUBLIC_DIR"] = str(public_dir)
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ["MSN_ID"] = msn_id

    path = portal_root / "app.py"
    spec = importlib.util.spec_from_file_location("fnd_portal_app_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class FndPortalShellRouteTests(unittest.TestCase):
    def test_shell_routes_follow_new_tabs_and_redirects(self):
        with TemporaryDirectory() as temp_dir:
            module = _load_fnd_app_module(Path(temp_dir))
            client = module.app.test_client()

            self.assertEqual(client.get("/portal/system").status_code, 200)
            self.assertEqual(client.get("/portal/network?tab=hosted").status_code, 200)
            self.assertEqual(client.get("/portal/network?tab=profile").status_code, 200)
            self.assertEqual(client.get("/portal/utilities?tab=vault").status_code, 200)

            self.assertEqual(client.get("/portal/tools").status_code, 302)
            self.assertIn("/portal/utilities?tab=tools", client.get("/portal/tools").headers.get("Location", ""))
            self.assertIn("/portal/utilities?tab=vault", client.get("/portal/vault").headers.get("Location", ""))
            self.assertIn("/portal/network?tab=messages&kind=log&id=request_log", client.get("/portal/inbox").headers.get("Location", ""))


if __name__ == "__main__":
    unittest.main()
