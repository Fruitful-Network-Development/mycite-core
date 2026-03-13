# mycite-le_tff

TFF legal-entity portal runtime.

## Current role

- classroom-style member workspace surface
- hosts the TFF-specific optional tools:
  - `config_schema`
  - `agro_erp`

## Build spec

Repo-owned build source:

- [`build.json`](build.json)

Materialized live state:

- `/srv/compose/portals/state/tff_portal/`

## Local run

```bash
cd /srv/repo/mycite-core/portals/mycite-le_tff
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Canonical docs

- [mycite-core root](../../README.md)
- [Portal Build Spec](../../docs/PORTAL_BUILD_SPEC.md)
- [Canonical Data Engine](../../docs/CANONICAL_DATA_ENGINE.md)
- [Network Page Model](../../docs/NETWORK_PAGE_MODEL.md)
- [AGRO ERP Tool](../../docs/AGRO_ERP_TOOL.md)
