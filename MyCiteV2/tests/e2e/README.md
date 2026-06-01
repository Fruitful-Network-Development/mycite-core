# Portal browser e2e harness

Reusable end-to-end harness for the MyCite portal. Two layers, both driven by
the `portal_server` fixture (`conftest.py`), which boots the real portal app
(`create_app`) against the live fnd MOS authority DB on an ephemeral localhost
port via `werkzeug`'s `make_server` on a daemon thread:

1. **`test_http_endpoints_smoke`** — no-browser fallback. Pure `urllib` checks
   that `/portal/system` (HTML shell) and `/portal/api/tools/eligible` (JSON
   palette payload) both return 200 with a sane body. Runs anywhere Flask is
   available; writes the palette JSON to `artifacts/tools_eligible.json`.
2. **`test_tool_search_dropdown_and_mount`** (`@pytest.mark.e2e`) — real
   chromium smoke. Loads `/portal/system`, drives the menu-bar tool search,
   screenshots the rendered shell to `artifacts/tool_search_smoke.png`, and —
   when the dropdown surfaces eligible tools — exercises the
   click → `POST /portal/api/v2/shell` → workbench-mount flow. The
   item-dependent click-through is best-effort (skips, never flakes, when no
   items surface in the headless default state).

## Run it

```bash
# from repo root
/srv/venvs/fnd_portal/bin/python -m pytest MyCiteV2/tests/e2e -q

# the browser test needs chromium (optional; the suite skips cleanly without it):
/srv/venvs/fnd_portal/bin/python -m pip install playwright
/srv/venvs/fnd_portal/bin/python -m playwright install chromium
```

Both tests **skip** (never fail) when their prerequisites are absent — the live
authority DB for `portal_server`, the Playwright package or a launchable
chromium for the browser fixtures — so the harness is safe in any CI.

## Overrides (env)

Defaults target the live fnd instance; override for CI:
`MYCITE_E2E_PORTAL_INSTANCE_ID`, `MYCITE_E2E_WEBAPPS_ROOT`,
`MYCITE_E2E_PUBLIC_DIR`, `MYCITE_E2E_PRIVATE_DIR`, `MYCITE_E2E_DATA_DIR`,
`MYCITE_E2E_AUTHORITY_DB`, `MYCITE_E2E_PORTAL_DOMAIN`.

`artifacts/` (screenshots + recorded JSON) is generated at run time and
git-ignored. This is the canonical UI-verification path referenced by
`docs/wiki/05-engineering-standards.md`.
