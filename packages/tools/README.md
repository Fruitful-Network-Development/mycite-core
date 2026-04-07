# Tool Modules

Canonical tool code lives under `packages/tools/`.

Rules:

- tool code and state adapters belong in this repo;
- mutable tool state belongs in live instance state, not in git;
- utility JSON and profile files live under `/srv/mycite-state/instances/<instance_id>/private/utilities/tools/<tool>/`;
- tool datum anchors live under `/srv/mycite-state/instances/<instance_id>/data/sandbox/<tool>/`;
- payload binaries and decoded caches live under `/srv/mycite-state/instances/<instance_id>/data/payloads/`;
- tools attach to portal-owned surfaces; they do not define their own shell model.

Current examples:

- AWS-CMS mailbox and newsletter utility state:
  `/srv/mycite-state/instances/<instance_id>/private/utilities/tools/aws-csm/`
- FND-EBI analytics mediation reads website-owned files under
  `/srv/webapps/clients/<domain>/analytics/`
- Canonical newsletter contact logs remain website-owned under
  `/srv/webapps/clients/<domain>/contacts/<domain>-contact_log.json`

Current live tool-aligned runtime module:

- `paypal_csm/backend/webhook_compat_app.py`
