# mycite-le_tff

TFF portal build spec.

## Current role

- repo-owned build source for the TFF live portal instance
- no longer a standalone runtime root
- materializes state for the shared generic runtime plus the `tff` runtime flavor
- classroom-style member workspace surface with the TFF-specific optional tools:
  - `config_schema`
  - `agro_erp`

## Build spec

Repo-owned build source:

- [`build.json`](build.json)

Materialized live state:

- `/srv/mycite-state/instances/tff/`

Current shared runtime:

- `../runtime/`
- `../_shared/runtime/flavors/tff/`

## Local run

```bash
cd /srv/repo/mycite-core/portals/runtime
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PORTAL_RUNTIME_FLAVOR=tff python app.py
```

## Canonical docs

- [mycite-core root](../../README.md)
- [Build And Materialization](../../wiki/runtime-build/build-and-materialization.md)
- [Canonical Data Artifacts](../../wiki/data-model/canonical-data-artifacts.md)
- [Network Page Model](../../wiki/network-hosted/network-page-model.md)
- [AGRO-ERP Mediation](../../wiki/tools/agro-erp-mediation.md)
