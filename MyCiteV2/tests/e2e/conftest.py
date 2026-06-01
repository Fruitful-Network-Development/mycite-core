"""Pytest fixtures for the portal browser e2e harness.

Provides:
  - ``portal_server``: boots ``create_app`` against the live fnd MOS authority
    DB on an ephemeral localhost port via ``werkzeug.serving.make_server`` in a
    background thread; yields the base URL; shuts down cleanly. SKIPs if the
    authority DB / required dirs are absent (safe on hosts without live data).
  - ``browser`` / ``page``: a Playwright chromium browser + page, created with
    a manual ``sync_playwright()`` context so we do NOT depend on the
    ``pytest-playwright`` plugin being installed. SKIPs if Playwright (the
    Python package) or a launchable chromium is unavailable.

All paths default to the live fnd instance but are overridable via env so CI
can point elsewhere:

  - ``MYCITE_E2E_PORTAL_INSTANCE_ID``  (default ``fnd``)
  - ``MYCITE_E2E_WEBAPPS_ROOT``        (default ``/srv/webapps/mycite``)
  - ``MYCITE_E2E_PUBLIC_DIR``          (default ``<webapps>/<inst>/public``)
  - ``MYCITE_E2E_PRIVATE_DIR``         (default ``<webapps>/<inst>/private``)
  - ``MYCITE_E2E_DATA_DIR``            (default ``<webapps>/<inst>/data``)
  - ``MYCITE_E2E_AUTHORITY_DB``        (default ``<private>/mos_authority.sqlite3``)
  - ``MYCITE_E2E_PORTAL_DOMAIN``       (default ``fruitfulnetwork.org``)

The fixtures intentionally mirror the live-server boot pattern proven in
``MyCiteV2/tests/smoke/test_phase12h_browser_smoke.py`` (free port +
``make_server`` on a daemon thread), but expose it as reusable pytest fixtures.
"""

from __future__ import annotations

import importlib.util
import os
import socket
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

# The project is not pip-installed; tests prepend the repo root so the
# ``MyCiteV2`` package imports resolve (matches every other test module).
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None
WERKZEUG_AVAILABLE = importlib.util.find_spec("werkzeug") is not None
PLAYWRIGHT_AVAILABLE = importlib.util.find_spec("playwright") is not None


def pytest_configure(config) -> None:
    """Register the ``e2e`` marker locally so the browser test does not emit a
    PytestUnknownMarkWarning (the repo has no global pytest marker config)."""
    config.addinivalue_line(
        "markers",
        "e2e: browser-driven end-to-end portal test (requires playwright + chromium)",
    )


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value and value.strip() else default


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _resolve_paths() -> dict[str, object]:
    """Resolve the V2PortalHostConfig inputs from env (defaults → live fnd)."""
    instance_id = _env("MYCITE_E2E_PORTAL_INSTANCE_ID", "fnd")
    webapps_root = Path(_env("MYCITE_E2E_WEBAPPS_ROOT", "/srv/webapps/mycite"))
    instance_root = webapps_root / instance_id
    public_dir = Path(_env("MYCITE_E2E_PUBLIC_DIR", str(instance_root / "public")))
    private_dir = Path(_env("MYCITE_E2E_PRIVATE_DIR", str(instance_root / "private")))
    data_dir = Path(_env("MYCITE_E2E_DATA_DIR", str(instance_root / "data")))
    authority_db = Path(
        _env("MYCITE_E2E_AUTHORITY_DB", str(private_dir / "mos_authority.sqlite3"))
    )
    portal_domain = _env("MYCITE_E2E_PORTAL_DOMAIN", "fruitfulnetwork.org")
    return {
        "portal_instance_id": instance_id,
        "webapps_root": webapps_root,
        "public_dir": public_dir,
        "private_dir": private_dir,
        "data_dir": data_dir,
        "authority_db_file": authority_db,
        "portal_domain": portal_domain,
    }


@pytest.fixture(scope="session")
def portal_server() -> Iterator[str]:
    """Boot the portal app against the live authority DB; yield its base URL.

    SKIPs (does not fail) when Flask/Werkzeug or the live data paths are
    missing, so the harness is safe to collect anywhere.
    """
    if not (FLASK_AVAILABLE and WERKZEUG_AVAILABLE):
        pytest.skip("portal_server requires flask + werkzeug in the venv")

    paths = _resolve_paths()
    authority_db = paths["authority_db_file"]
    assert isinstance(authority_db, Path)
    if not authority_db.exists():
        pytest.skip(
            "authority DB not found at "
            f"{authority_db} — set MYCITE_E2E_AUTHORITY_DB (and the other "
            "MYCITE_E2E_* paths) to point at a live MOS authority DB"
        )
    for key in ("public_dir", "private_dir", "data_dir", "webapps_root"):
        candidate = paths[key]
        assert isinstance(candidate, Path)
        if not candidate.is_dir():
            pytest.skip(f"{key} not found at {candidate} — cannot boot portal")

    from werkzeug.serving import make_server

    from MyCiteV2.instances._shared.portal_host.app import (
        V2PortalHostConfig,
        create_app,
    )

    config = V2PortalHostConfig(
        portal_instance_id=str(paths["portal_instance_id"]),
        public_dir=paths["public_dir"],
        private_dir=paths["private_dir"],
        data_dir=paths["data_dir"],
        portal_domain=str(paths["portal_domain"]),
        webapps_root=paths["webapps_root"],
        authority_db_file=authority_db,
    )
    app = create_app(config)
    port = _free_port()
    server = make_server("127.0.0.1", port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Give the listener a beat to come up before tests hit it.
    time.sleep(0.4)
    base_url = f"http://127.0.0.1:{port}"
    try:
        yield base_url
    finally:
        server.shutdown()
        thread.join(timeout=3)


@pytest.fixture(scope="session")
def _playwright_browser():
    """Session-scoped chromium browser via a manual sync_playwright context.

    SKIPs if the Playwright package or a launchable chromium is unavailable so
    the suite stays green on hosts that have not run ``playwright install``.
    """
    if not PLAYWRIGHT_AVAILABLE:
        pytest.skip(
            "playwright not installed — "
            "pip install playwright && playwright install chromium"
        )
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(headless=True)
    except Exception as exc:  # noqa: BLE001 — chromium binary not installed
        pw.stop()
        pytest.skip(
            "chromium not launchable (run `playwright install chromium`): "
            f"{type(exc).__name__}: {exc}"
        )
    try:
        yield browser
    finally:
        browser.close()
        pw.stop()


@pytest.fixture()
def page(_playwright_browser):
    """A fresh Playwright page in its own browser context per test."""
    context = _playwright_browser.new_context()
    page = context.new_page()
    try:
        yield page
    finally:
        context.close()


@pytest.fixture(scope="session", autouse=True)
def _artifacts_dir() -> Path:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    return ARTIFACTS_DIR
