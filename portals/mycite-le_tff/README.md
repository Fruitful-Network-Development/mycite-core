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

- `/srv/compose/portals/state/tff_portal/`

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
- [Portal Build Spec](../../docs/PORTAL_BUILD_SPEC.md)
- [Canonical Data Engine](../../docs/CANONICAL_DATA_ENGINE.md)
- [Network Page Model](../../docs/NETWORK_PAGE_MODEL.md)
- [AGRO ERP Tool](../../docs/AGRO_ERP_TOOL.md)
