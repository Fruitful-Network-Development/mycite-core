# mycite-core

Canonical source for the MyCite portal framework.

## Scope

- NE/LE portal implementations and shared portal runtime patterns
- NIMM data tool behavior and table/field icon guidance
- Contract and request-log cooperation model
- Tool runtime conventions used by portal apps

## Layout

- `portals/` portal implementations and examples
- `tools/` shared tool modules (when extracted)
- `docs/` canonical product/framework documentation
- `scripts/` developer and repo maintenance scripts

## Non-goals

- No production/deployment runtime state
- No live server secrets, certs, or `.env` values
- No host-level NGINX/systemd operational ownership (belongs to `srv-infra`)

## Related repo

Infrastructure/deployment ownership is in `/srv/repo/srv-infra`.
