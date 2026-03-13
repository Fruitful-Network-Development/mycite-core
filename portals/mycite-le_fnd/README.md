# mycite-le_fnd

FND portal build spec.

## Current role

- primary organization/admin portal
- hosts FND-scoped and member-scoped AWS/PayPal admin tools
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
- `aws_tenant_actions`
- `aws_platform_admin`
- `operations`

Core SYSTEM surface, not an optional tool:

- `data_tool`

Retired:

- `legacy_admin`
- `paypal_demo`

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
- [Portal Build Spec](../../docs/PORTAL_BUILD_SPEC.md)
- [Service Shell Standard](../../docs/TOOLS_SHELL.md)
- [AWS Emailer Abstraction](../../docs/AWS_EMAILER_ABSTRACTION.md)
- [PayPal Payment Abstraction](../../docs/PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md)
