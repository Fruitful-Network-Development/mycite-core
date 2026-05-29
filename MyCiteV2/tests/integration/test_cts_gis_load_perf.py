"""Performance smoke test for the CTS-GIS portal surface.

Catches regressions in shell hydration / bundle build cost before users hit a 504.

Self-contained: builds an in-process Flask app from a temp directory so no
PORTAL_INSTANCE_ID / PUBLIC_DIR / PRIVATE_DIR / DATA_DIR / MYCITE_ANALYTICS_DOMAIN /
MYCITE_WEBAPPS_ROOT / MYCITE_V2_PORTAL_AUDIT_FILE / MYCITE_V2_PORTAL_AUTHORITY_DB
env vars are required at import time. If flask is unavailable the module is
skipped.
"""

from __future__ import annotations

import html
import importlib.util
import json
import re
import sys
import tempfile
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None

pytestmark = pytest.mark.skipif(not FLASK_AVAILABLE, reason="flask is not installed")

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_network_chronology_authority(data_dir: Path) -> None:
    (data_dir / "system").mkdir(parents=True, exist_ok=True)
    _write_json(
        data_dir / "system" / "anthology.json",
        {
            "1-1-1": [
                [
                    "1-1-1",
                    "0-0-1",
                    "00000010000110000000110011010101111000011011001100011101111001111101000111110100011111010001011011010111000111100111100",
                ],
                ["HOPS-chronological"],
            ]
        },
    )
    _write_json(
        data_dir / "system" / "sources" / "sc.fnd.quadrennium_cycle.json",
        {
            "datum_addressing_abstraction_space": {
                "1-1-1": [["1-1-1", "rf.0-0-1", "00000100011100000101100100011011111101110110110101110001111001111001111101000"], ["HOPS-quadrennium_cycle"]],
                "2-0-1": [["2-0-1", "~", "1-1-1"], ["HOPS-space-quadrennium"]],
                "3-1-1": [["3-1-1", "2-0-1", "0"], ["HOPS-babelette-quadrennium_cycle"]],
            }
        },
    )


@pytest.fixture(scope="module")
def portal_app():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        public_dir = root / "public"
        private_dir = root / "private"
        data_dir = root / "data"
        webapps_root = root / "webapps"
        for path in (public_dir, private_dir, data_dir, webapps_root):
            path.mkdir(parents=True, exist_ok=True)
        _write_network_chronology_authority(data_dir)
        _write_json(
            private_dir / "config.json",
            {
                "msn_id": "3-2-3-17-77-1-6-4-1-4",
                "tool_exposure": {},
            },
        )
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=public_dir,
            private_dir=private_dir,
            data_dir=data_dir,
            portal_domain="fruitfulnetworkdevelopment.com",
            webapps_root=webapps_root,
        )
        yield create_app(config)


@pytest.fixture(scope="module")
def cts_gis_bootstrap(portal_app):
    client = portal_app.test_client()
    # Plan v2: /portal/system/tools/cts-gis 302-redirects to
    # /portal/system?tool=cts_gis&<canonical query> (see app.py
    # portal_system_tool dispatcher). Follow the redirect to land on the
    # unified workbench HTML that carries the bootstrap shell request.
    response = client.get(
        "/portal/system/tools/cts-gis?file=anchor&verb=mediate",
        follow_redirects=True,
    )
    assert response.status_code == 200
    match = re.search(rb'v2-bootstrap-shell-request[^>]*>([^<]*)<', response.data)
    assert match is not None, "bootstrap shell request script not found in portal HTML"
    return json.loads(html.unescape(match.group(1).decode()))


def test_cts_gis_shell_hydration_under_perf_budget(portal_app, cts_gis_bootstrap):
    """Hydration must stay under budget regardless of upstream data state.

    The fixture intentionally provides only a minimal authority (no real CTS-GIS
    sources), so the runtime exercises the compiled_state_invalid fallback path
    — which is exactly the slow path that produced 504s in production.
    The envelope schema remains valid; only the response status differs.
    """
    client = portal_app.test_client()
    client.post("/portal/api/v2/shell", json=cts_gis_bootstrap)
    durations = []
    response = None
    for _ in range(10):
        started = time.perf_counter()
        response = client.post("/portal/api/v2/shell", json=cts_gis_bootstrap)
        durations.append((time.perf_counter() - started) * 1000.0)
        assert response.status_code in (200, 503), response.status_code
    body = json.loads(response.data)
    # Plan v2: cts_gis is a palette tool layered on /portal/system; the
    # requested surface is system.root with surface_query.tool=cts_gis.
    assert body["requested_surface_id"] == "system.root"
    assert (body.get("canonical_query") or {}).get("tool") == "cts_gis", body.get("canonical_query")
    timings = (
        body.get("surface_payload", {})
        .get("runtime_diagnostics", {})
        .get("phase_timings_ms", {})
    )
    bundle_ms = timings.get("total_bundle_build")
    median_ms = sorted(durations)[5]
    assert median_ms < 500.0, f"median slow: {sorted(durations)} ms"
    if bundle_ms is not None:
        assert bundle_ms < 300.0, f"bundle build slow: {bundle_ms} ms"
