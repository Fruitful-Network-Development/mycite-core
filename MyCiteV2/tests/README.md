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

## Linting

```bash
/srv/venvs/fnd_portal/bin/ruff check MyCiteV2/
```

Config lives at `../pyproject.toml`. The selected rule sets are E
(pycodestyle errors), F (pyflakes — unused imports, undefined names),
I (isort), UP (pyupgrade), B (flake8-bugbear), and RUF (ruff-specific).
Per-file allowlists carve out:

- Tests can `sys.path.insert` before MyCiteV2 imports (E402) and import
  fixtures they don't directly call (F401, F811).
- `__init__.py` and `shell.py` aggregators do `from .X import *` by
  design (F403, F405, RUF022).

To auto-fix the safe-fixable subset:

```bash
ruff check MyCiteV2/ --fix
```

## CI

`.github/workflows/tests.yml` runs three parallel jobs on push / PR to
`main`:

- `lint` — installs ruff, runs `ruff check MyCiteV2/`.
- `pytest` — fast: installs `requirements-dev.txt`, runs
  `pytest MyCiteV2/tests/ --ignore=MyCiteV2/tests/smoke`.
- `smoke` — installs `requirements-dev.txt` + chromium-headless-shell,
  runs `pytest MyCiteV2/tests/smoke/`. Currently `continue-on-error:
  true` while we stabilize; promote to required after ~10 clean runs.

Dependencies: `../requirements-dev.txt` at repo root.
