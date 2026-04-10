# MyCiteV1

This directory is the canonical home for the current V1 MyCite portal core.

The repository root keeps compatibility links for existing imports, service scripts, and operator muscle memory:

- `instances/` -> `MyCiteV1/instances/`
- `mycite_core/` -> `MyCiteV1/mycite_core/`
- `packages/` -> `MyCiteV1/packages/`
- `docs/` -> `MyCiteV1/docs/`
- `scripts/` -> `MyCiteV1/scripts/`
- `_shared/` -> `MyCiteV1/_shared/`
- `tests/` -> `MyCiteV1/tests/`

Runtime state remains outside the repo under `/srv/mycite-state/instances/<instance_id>/`.

Hosted webapp operational data is expected under `/srv/webapps/<domain>/`:

- newsletter contact logs: `/srv/webapps/<domain>/contact/<domain>-contact_log.json`
- FND-EBI analytics: `/srv/webapps/<domain>/analytics/`

The deployed instance mirrors live under `instances/deployed/` and can be captured or materialized with:

```bash
python3 MyCiteV1/instances/scripts/portal_build.py capture
python3 MyCiteV1/instances/scripts/portal_build.py materialize
```
