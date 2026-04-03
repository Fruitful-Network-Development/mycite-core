# Tool Modules

Canonical standalone tool code lives under `mycite-core/tools/`.

Rules:

- tool code and UI belong in `mycite-core`;
- persisted tool data belongs in the portal instance state bubble, not in git;
- host/runtime glue in `srv-infra` may execute a tool entrypoint, but it should not own the tool's application logic.

Current live tool-aligned runtime modules:

- `paypal_csm/backend/webhook_compat_app.py`

The long-term target is for additional standalone tool entrypoints, state adapters, and UI surfaces to live here while their mutable data stays under `/srv/mycite-state/instances/<instance_id>/...`.
