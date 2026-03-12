# mycite-ne_mt

MT natural-entity portal runtime (`mark_trapp`).

## Role in current milestone

- Local-first natural-entity portal for TFF/CVCC POC workflows.
- Board-member progeny links resolve to CVCC board workspace by default embed mapping.
- Uses `private/mycite-config-*.json` as the runtime config source for organization behavior overlays.

## Local run

```bash
cd /srv/repo/mycite-core/portals/mycite-ne_mt
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Runtime notes

- Source of truth is this repo path.
- Compose runtime state is under `/srv/compose/portals/state/mt_portal/`.
