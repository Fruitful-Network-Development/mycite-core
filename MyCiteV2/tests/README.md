# Tests

Authority: [../docs/README.md](../docs/README.md)

`tests/` is organized by boundary loop rather than by implementation
convenience.

The suite protects one live shell model:

- `/portal` redirects to `/portal/system`
- root surfaces are `SYSTEM`, `NETWORK`, and `UTILITIES`
- no split-instance public ingress remains in the active repo
- no retired bridge or compatibility package remains in the active repo

## Running

Fast subset (unit + integration + architecture + adapters + contracts), no
browser:

```bash
/srv/venvs/fnd_portal/bin/pytest MyCiteV2/tests/ --ignore=MyCiteV2/tests/smoke
```

Whole suite including the headless browser smoke (requires playwright +
chromium-headless-shell — see Smoke setup below):

```bash
/srv/venvs/fnd_portal/bin/pytest MyCiteV2/tests/
```

Expected: green-when-clean. There are 46 reasoned `@unittest.skip` /
`@unittest.skipUnless` tests pinned to CTS-GIS data-domain drift,
fixture-only paths, or Phase-3 retirement cascade — every skip carries
a one-line note explaining what to reauthor (or what fixture to provide)
to enable it.

## Smoke setup

`tests/smoke/test_phase12h_browser_smoke.py` boots a tempdir-backed
portal on a free localhost port and drives Chromium at
`/portal/utilities/tool-exposure` to verify the Phase 12h grantee
selector renders, dispatches, and pivots extension payloads. This is
the only test in the suite that loads real JS — the rest are
pure-Python contract tests.

Install once per dev box / CI runner:

```bash
/srv/venvs/fnd_portal/bin/pip install playwright
/srv/venvs/fnd_portal/bin/playwright install chromium-headless-shell
```

When either is missing the smoke is `@unittest.skipUnless`-skipped, so
the suite stays green on hosts that haven't run the install.

## CI

`.github/workflows/tests.yml` runs two parallel jobs on push / PR to
`main`:

- `pytest` — fast: installs `requirements-dev.txt`, runs
  `pytest MyCiteV2/tests/ --ignore=MyCiteV2/tests/smoke`.
- `smoke` — installs `requirements-dev.txt` + chromium-headless-shell,
  runs `pytest MyCiteV2/tests/smoke/`. Currently `continue-on-error:
  true` while we stabilize; promote to required after ~10 clean runs.

Dependencies: `../requirements-dev.txt` at repo root.
