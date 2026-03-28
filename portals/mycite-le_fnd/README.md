# mycite-le_fnd

FND portal build spec.

## Current role

- primary organization/admin portal
- hosts FND-scoped operator AWS-CMS tooling plus member-scoped PayPal admin tooling
- provides the canonical SYSTEM/NETWORK/UTILITIES shell for the organization-facing runtime

## Current role

- repo-owned build source for the FND live portal instance
- no longer a standalone runtime root
- materializes state for the shared generic runtime plus the `fnd` runtime flavor

## Build spec

Repo-owned spec:

- [`build.json`](build.json)

Materialized live state:

- `/srv/compose/portals/state/fnd_portal/`

Current shared runtime:

- `../runtime/`
- `../_shared/runtime/flavors/fnd/`

Phase-1 build material covers tools/config/hosted/public cards plus seed files. Anthology remains state-owned.

## Normalized tool inventory

Enabled optional tools:

- `tenant_progeny_profiles`
- `fnd_provisioning`
- `paypal_tenant_actions`
- `paypal_service_agreement`
- `aws_platform_admin`
- `fnd_ebi` (FND EBI — hosted site analytics mediation)
- `operations`

Core SYSTEM surface, not an optional tool:

- `data_tool`

Retired:

- `legacy_admin`
- `paypal_demo`

Notes:

- `tenant_progeny_profiles` is now a shortcut into the canonical `UTILITIES -> Progeny` workspace rather than a separate editing surface.
- Hosted defaults, broadcaster metadata, and progeny templates are authored through `private/network/hosted.json` via the build spec.

## Local run

```bash
cd /srv/repo/mycite-core/portals/runtime
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PORTAL_RUNTIME_FLAVOR=fnd python app.py
```

## Canonical docs

- [mycite-core root](../../README.md)
- [Build And Materialization](../../wiki/runtime-build/build-and-materialization.md)
- [Shell And Page Composition](../../wiki/architecture/shell-and-page-composition.md)
- [Member Service Integrations](../../wiki/tools/member-service-integrations.md)
