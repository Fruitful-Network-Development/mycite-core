# mycite-le_tff

TFF legal-entity portal runtime and current example portal.

## Current role

- example/base portal for evolving the starter anthology abstraction
- classroom-style member workspace surface
- hosts the TFF-specific optional tools:
  - `config_schema`
  - `agro_erp`

## Build spec

Repo-owned build source:

- [`build.json`](build.json)

Materialized live state:

- `/srv/compose/portals/state/tff_portal/`

Current example anthology in live state:

- `/srv/compose/portals/state/tff_portal/data/anthology.json`

That anthology file remains state-owned and is not overwritten by phase-1 materialization.

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
