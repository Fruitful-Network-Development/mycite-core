# Tool Modules

Canonical standalone tool code lives under `mycite-core/tools/`.

Rules:

- tool code and UI belong in `mycite-core`;
- persisted tool data normally belongs in the portal instance state bubble, not
  in git;
- service-tool patterns may instead point at a canonical client-owned tree when
  the public website is the intended source of truth;
- host/runtime glue in `srv-infra` may execute a tool entrypoint, but it should not own the tool's application logic.

Current examples of that split:

- AWS-CMS mailbox state stays under
  `/srv/mycite-state/instances/<instance_id>/private/utilities/tools/aws-csm/`
- FND-EBI analytics mediation reads website-owned files under
  `/srv/webapps/clients/<domain>/analytics/`
- planned newsletter contact-list management should treat
  `/srv/webapps/clients/<domain>/contacts/<domain>-contact_log.json` as the
  canonical contact-log location instead of storing that list under
  `private/utilities/tools`

Current live tool-aligned runtime modules:

- `paypal_csm/backend/webhook_compat_app.py`

The long-term target is for additional standalone tool entrypoints, state adapters, and UI surfaces to live here while their mutable data stays under `/srv/mycite-state/instances/<instance_id>/...`.
