# mycite-core

Canonical source for the MyCite portal framework, shared runtime, portal build specs, and product documentation.

## Active portal specs

Active portal spec directories in this repo:

- `portals/mycite-le_example`
- `portals/mycite-le_fnd`
- `portals/mycite-le_tff`

Retired from active scope:

- `portals/mycite-ne_mt`

These directories are no longer treated as standalone runnable app roots. Runtime code now lives under the shared runtime tree.

## Source-of-truth boundaries

- Repo code lives under `/srv/repo/mycite-core`
- Live file-backed portal state lives under `/srv/compose/portals/state/<portal_instance>/`
- There is no application database in the portal runtime; state is JSON/ndjson/file backed
- Keycloak remains the only external database-backed identity system in scope

Example anthology currently being evolved as the base abstraction:

- `/srv/compose/portals/state/example_portal/data/anthology.json`

## Portal build model

Portal-specific authoring now starts from per-portal repo specs:

- `portals/mycite-le_example/build.json`
- `portals/mycite-le_fnd/build.json`
- `portals/mycite-le_tff/build.json`

Build specs are phase-1 authoritative for:

- enabled tools and mount behavior
- canonical private config payloads
- hosted payloads, including hosted subject-congregation metadata, broadcaster metadata, and default progeny templates
- public profile/card payloads
- seed file lists for alias/profile scaffolding plus unified progeny instances

Anthology remains state-owned in this phase. Build specs record anthology metadata/checksum only and do not overwrite anthology files during materialization.

Build/update script:

- `python3 portals/scripts/portal_build.py capture`
- `python3 portals/scripts/portal_build.py materialize`

## Shared runtime model

Runnable runtime code now lives under:

- `portals/runtime/` generic runtime entrypoint and image
- `portals/_shared/runtime/flavors/fnd/` FND runtime flavor
- `portals/_shared/runtime/flavors/tff/` TFF/runtime flavor used by TFF and the current example portal

Per-portal directories are being reduced toward spec-only ownership.

Hosted/progeny direction in the current phase:

- `private/network/hosted.json` is the canonical hosted metadata container
- default progeny templates live inside hosted metadata
- canonical progeny instance storage is `private/network/progeny/msn-<provider_msn_id>.<progeny_type>-<alias_associated_msn_id>.json`
- FND keeps AWS/PayPal split by operational scope and now carries a separate `website_analytics` tool for hosted member websites

## Repository layout

- `portals/_shared/` shared runtime, network, data-engine, and tool-loading modules
- `portals/runtime/` generic runtime image + loader
- `portals/assets/` shared icons/UI assets
- `portals/scripts/` portal build/update helpers
- `portals/mycite-le_example/` example/demo portal build spec
- `portals/mycite-le_fnd/` FND portal build spec
- `portals/mycite-le_tff/` TFF portal build spec
- `docs/` canonical product and runtime documentation

## Canonical docs

- [`docs/README.md`](docs/README.md)
- [`docs/PORTAL_BUILD_SPEC.md`](docs/PORTAL_BUILD_SPEC.md)
- [`docs/TOOLS_SHELL.md`](docs/TOOLS_SHELL.md)
- [`docs/CANONICAL_DATA_ENGINE.md`](docs/CANONICAL_DATA_ENGINE.md)
- [`docs/NETWORK_PAGE_MODEL.md`](docs/NETWORK_PAGE_MODEL.md)
- [`docs/AWS_EMAILER_ABSTRACTION.md`](docs/AWS_EMAILER_ABSTRACTION.md)
- [`docs/PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md`](docs/PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md)
- [`docs/REQUEST_LOG_V1.md`](docs/REQUEST_LOG_V1.md)
- [`docs/PROGENY_PROFILE_CARDS.md`](docs/PROGENY_PROFILE_CARDS.md)
- [`docs/PROGENY_CONFIG_MODEL.md`](docs/PROGENY_CONFIG_MODEL.md)
- [`docs/DATA_TOOL.md`](docs/DATA_TOOL.md)
- [`docs/DOCUMENTATION_POLICY.md`](docs/DOCUMENTATION_POLICY.md)
- [`docs/repo_policy.md`](docs/repo_policy.md)

## Runtime note

Live FND/TFF containers are built from this repo through `/srv/compose/portals/docker-compose.yml`.

Do not edit running-container files directly. Update repo code/build specs, materialize state, then rebuild the target portal container.
