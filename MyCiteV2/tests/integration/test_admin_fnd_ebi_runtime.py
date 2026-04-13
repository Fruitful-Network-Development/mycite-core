from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.admin_fnd_ebi_runtime import run_admin_fnd_ebi_read_only
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    ADMIN_FND_EBI_READ_ONLY_REQUEST_SCHEMA,
    ADMIN_RUNTIME_ENVELOPE_SCHEMA,
    ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE,
    build_admin_tool_exposure_policy,
)
from MyCiteV2.packages.state_machine.hanus_shell import FND_EBI_READ_ONLY_ENTRYPOINT_ID, FND_EBI_READ_ONLY_SLICE_ID


def _write_fnd_ebi_fixture(root: Path, *, year_month: str = "2026-04") -> tuple[Path, Path]:
    private_dir = root / "private"
    webapps_root = root / "webapps"
    client_root = webapps_root / "clients" / "fruitfulnetworkdevelopment.com"
    site_root = client_root / "site"
    analytics_root = client_root / "analytics"
    tool_root = private_dir / "utilities" / "tools" / "fnd-ebi"
    (analytics_root / "nginx").mkdir(parents=True, exist_ok=True)
    (analytics_root / "events").mkdir(parents=True, exist_ok=True)
    site_root.mkdir(parents=True, exist_ok=True)
    tool_root.mkdir(parents=True, exist_ok=True)
    (tool_root / "fnd-ebi.fnd.json").write_text(
        json.dumps(
            {
                "schema": "mycite.service_tool.fnd_ebi.profile.v1",
                "domain": "fruitfulnetworkdevelopment.com",
                "site_root": str(site_root),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (analytics_root / "nginx" / "access.log").write_text(
        '127.0.0.1 - - [12/Apr/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 120 "-" "Mozilla/5.0"\n',
        encoding="utf-8",
    )
    (analytics_root / "nginx" / "error.log").write_text(
        "[2026/04/12 10:00:00] [warn] 100#0: *1 sample warning\n",
        encoding="utf-8",
    )
    (analytics_root / "events" / f"{year_month}.ndjson").write_text(
        json.dumps({"event_type": "page_view", "timestamp": "2026-04-12T10:00:00+00:00", "session_id": "sess-1"}) + "\n",
        encoding="utf-8",
    )
    return private_dir, webapps_root


class AdminFndEbiRuntimeIntegrationTests(unittest.TestCase):
    def test_fnd_ebi_read_only_returns_profile_led_surface_when_enabled(self) -> None:
        with TemporaryDirectory() as temp_dir:
            private_dir, webapps_root = _write_fnd_ebi_fixture(Path(temp_dir))
            policy = build_admin_tool_exposure_policy(
                {"fnd_ebi": {"enabled": True}},
                known_tool_ids=["aws", "aws_narrow_write", "aws_csm_sandbox", "aws_csm_onboarding", "cts_gis", "fnd_ebi"],
            )

            result = run_admin_fnd_ebi_read_only(
                {
                    "schema": ADMIN_FND_EBI_READ_ONLY_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
                    "year_month": "2026-04",
                },
                private_dir=private_dir,
                webapps_root=webapps_root,
                portal_tenant_id="fnd",
                portal_tenant_domain="fruitfulnetworkdevelopment.com",
                tool_exposure_policy=policy,
            )

            self.assertEqual(result["schema"], ADMIN_RUNTIME_ENVELOPE_SCHEMA)
            self.assertEqual(result["entrypoint_id"], FND_EBI_READ_ONLY_ENTRYPOINT_ID)
            self.assertEqual(result["slice_id"], FND_EBI_READ_ONLY_SLICE_ID)
            self.assertIsNone(result["error"])
            self.assertEqual(result["surface_payload"]["overview"]["domain"], "fruitfulnetworkdevelopment.com")
            self.assertEqual(result["surface_payload"]["files"]["events_file"]["state"], "ready")
            self.assertEqual(result["shell_composition"]["regions"]["workbench"]["kind"], "fnd_ebi_workbench")

    def test_fnd_ebi_read_only_returns_tool_not_exposed_before_root_validation(self) -> None:
        policy = build_admin_tool_exposure_policy(
            {"fnd_ebi": {"enabled": False}},
            known_tool_ids=["aws", "aws_narrow_write", "aws_csm_sandbox", "aws_csm_onboarding", "cts_gis", "fnd_ebi"],
        )

        result = run_admin_fnd_ebi_read_only(
            {
                "schema": ADMIN_FND_EBI_READ_ONLY_REQUEST_SCHEMA,
                "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
            },
            private_dir=None,
            webapps_root=None,
            portal_tenant_id="fnd",
            tool_exposure_policy=policy,
        )

        self.assertEqual(result["error"]["code"], ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE)
        self.assertEqual(result["shell_state"]["reason_code"], ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE)

    def test_fnd_ebi_read_only_reports_missing_roots_when_enabled(self) -> None:
        policy = build_admin_tool_exposure_policy(
            {"fnd_ebi": {"enabled": True}},
            known_tool_ids=["aws", "aws_narrow_write", "aws_csm_sandbox", "aws_csm_onboarding", "cts_gis", "fnd_ebi"],
        )

        result = run_admin_fnd_ebi_read_only(
            {
                "schema": ADMIN_FND_EBI_READ_ONLY_REQUEST_SCHEMA,
                "tenant_scope": {"scope_id": "internal-admin", "audience": "internal"},
            },
            private_dir=None,
            webapps_root=None,
            portal_tenant_id="fnd",
            tool_exposure_policy=policy,
        )

        self.assertEqual(result["error"]["code"], "fnd_ebi_root_not_configured")
        self.assertEqual(result["surface_payload"]["error"], "fnd_ebi_root_not_configured")


if __name__ == "__main__":
    unittest.main()
