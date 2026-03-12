# mycite-le_tff

TFF legal-entity portal runtime (`trapp_family_farm`).

## Role in current milestone

- Board-member classroom surface for TFF.
- Tabs: `feed`, `calendar`, `people`, and `workflow`.
- Workflow content is config-driven from active config (`private/config.json`, with legacy fallback) via `organization_config`/`organization_configuration` (`file_name`, `default_values`, and `added_values`).

## Local run

```bash
cd /srv/repo/mycite-core/portals/mycite-le_tff
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Runtime notes

- Source of truth is this repo path.
- Compose runtime state is under `/srv/compose/portals/state/tff_portal/`.
- Missing config progeny refs are auto-seeded into `private/progeny/` local profile files.
- Config structure/default-field inspector is available at `/portal/tools/config_schema/home`.
- AGRO ERP daemon tool is available at `/portal/tools/agro_erp/home` for anthology-aware property coordinate resolution.
- Auth model matches FND via Keycloak `fruitful` realm (portal oauth2-proxy client).
- Footer auth action is `Sign out`; switch-user session fanout is intentionally disabled.
