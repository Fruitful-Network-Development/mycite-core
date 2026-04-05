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
- Live file-backed portal state lives under `/srv/mycite-state/instances/<portal_instance>/`
- There is no application database in the portal runtime; state is JSON/ndjson/file backed
- Keycloak remains the only external database-backed identity system in scope
- AWS-CMS mailbox state is mailbox-scoped and lives under
  `/srv/mycite-state/instances/<portal_instance>/private/utilities/tools/aws-csm/`
- Website-owned service-tool patterns may keep canonical files alongside a
  client web root when that is the intended source of truth; for example,
  analytics can derive from `client_root/analytics`, and newsletter contact-log
  planning now targets `client_root/contacts/<domain>-contact_log.json`

Example anthology currently being evolved as the base abstraction:

- `/srv/mycite-state/instances/example_portal/data/anthology.json`

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
- FND keeps AWS/PayPal split by operational scope and carries the `fnd_ebi` tool for hosted member website analytics mediation

## Repository layout

- `portals/_shared/` shared runtime, network, data-engine, and tool-loading modules
- `portals/runtime/` generic runtime image + loader
- `portals/assets/` shared icons/UI assets
- `portals/scripts/` portal build/update helpers
- `portals/mycite-le_example/` example/demo portal build spec
- `portals/mycite-le_fnd/` FND portal build spec
- `portals/mycite-le_tff/` TFF portal build spec
- `wiki/` canonical product and runtime documentation

## Canonical docs

- [`docs/ownership-boundary.md`](docs/ownership-boundary.md)
- [`wiki/Home.md`](wiki/Home.md)
- [`wiki/architecture/system-state-machine.md`](wiki/architecture/system-state-machine.md)
- [`wiki/data-model/datum-identity-and-resolution.md`](wiki/data-model/datum-identity-and-resolution.md)
- [`wiki/contracts-mss/mss-compact-array.md`](wiki/contracts-mss/mss-compact-array.md)
- [`wiki/samras/structural-model.md`](wiki/samras/structural-model.md)
- [`wiki/runtime-build/build-and-materialization.md`](wiki/runtime-build/build-and-materialization.md)
- [`wiki/network-hosted/network-page-model.md`](wiki/network-hosted/network-page-model.md)
- [`wiki/network-hosted/request-log-and-audit.md`](wiki/network-hosted/request-log-and-audit.md)
- [`wiki/tools/member-service-integrations.md`](wiki/tools/member-service-integrations.md)
- [`wiki/governance/documentation-governance.md`](wiki/governance/documentation-governance.md)

## Runtime note

Live FND/TFF containers are built from this repo through `/srv/compose/portals/docker-compose.yml`.

Do not edit running-container files directly. Update repo code/build specs, materialize state, then rebuild the target portal container.

Runtime state under `/srv/mycite-state/instances/*` is not a source-controlled
authoring surface. Treat it as mutable runtime state that is written by the
application, initialization scripts, or controlled migrations.

Deploy and restart alignment matters:

- validate restart scripts against the canonical `PRIVATE_DIR`, `PUBLIC_DIR`,
  and `DATA_DIR` paths used by the live unit
- confirm deploy automation does not revert runtime roots back to legacy
  locations
- confirm portal restart behavior in the target environment; recent live work
  showed that `systemctl start fnd-portal.service` could require interactive
  authentication, so restart automation should be verified explicitly
