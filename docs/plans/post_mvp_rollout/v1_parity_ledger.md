# V1 Parity Ledger

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

This ledger maps old portal workflow areas to post-MVP rollout intent.

The unit of classification is workflow area, not file parity.

Admin and provider replacement is broken out further in [admin_first/admin_first_parity_ledger.md](admin_first/admin_first_parity_ledger.md).

| Workflow area | V1 evidence | Classification | Target band | V2 rebuild note |
|---|---|---|---|---|
| Portal home, service navigation, network cards, shell landing | `instances/_shared/runtime/flavors/fnd/app.py`, `instances/_shared/runtime/flavors/fnd/portal/core_services/runtime.py` | first-band target | Band 1 | Rebuild as a read-only home and tenant status surface. Do not recreate host-owned navigation logic. |
| Local audit and activity visibility | `mycite_core/local_audit/store.py`, `instances/_shared/runtime/flavors/fnd/portal/services/local_audit_log.py`, `instances/_shared/runtime/flavors/fnd/portal/core_services/runtime.py` | first-band target | Band 1 | Start with `local_audit` only. Do not merge with `external_events` in the first client-visible band. |
| Narrow operational status and rollout visibility | `instances/_shared/runtime/flavors/fnd/portal/api/admin_integrations.py`, `instances/_shared/runtime/flavors/fnd/portal/api/website_analytics.py` | first-band target | Band 1 | Rebuild as one read-only status surface that shows portal availability and exposure status, not provider-admin dashboards. |
| Tenant and profile summary read models | `instances/_shared/runtime/flavors/fnd/portal/api/aliases.py`, `instances/_shared/runtime/flavors/fnd/portal/services/progeny_store.py` | first-band target | Band 1 | Keep the first read-only summary narrow and publication-backed. Do not revive alias and progeny service coupling in runtime. |
| Trusted-tenant profile basics editing | `instances/_shared/runtime/flavors/fnd/portal/api/tenant_progeny.py`, `mycite_core/publication/profile_paths.py` | later-band target | Band 2 | The first writable candidate is a bounded publication-backed profile basics slice only. |
| Contract workflows and handshake flows | `instances/_shared/portal/api/contracts.py`, `instances/_shared/portal/api/contract_handshake.py`, `mycite_core/contract_line/*` | later-band target | Band 2 or later | Rebuild only after the `contracts` domain module exists. |
| External event inbox and externally meaningful event visibility | `instances/_shared/runtime/flavors/fnd/portal/api/inbox.py`, `mycite_core/external_events/*` | later-band target | Band 2 or later | Requires `external_events` as its own cross-domain owner. Not needed for the first client-visible band. |
| Tenant and progeny workspace management | `instances/_shared/runtime/flavors/fnd/portal/api/progeny_workbench.py`, `instances/_shared/runtime/flavors/fnd/portal/services/progeny_workspace.py` | later-band target | Band 2 or later | Blocked by frozen hosted and progeny decisions. Do not pull this forward through convenience. |
| Website analytics and member analytics | `instances/_shared/runtime/flavors/fnd/portal/api/website_analytics.py`, `instances/_shared/runtime/flavors/fnd/portal/services/website_analytics_store.py` | later-band target | Band 2 or later | Only after read-only home and operational slices are stable. |
| Data workspace, document workbench, and publish flows | `instances/_shared/portal/api/data_workspace.py`, `instances/_shared/portal/application/workbench/*` | deferred | not assigned | Too mixed with sandbox and workbench concerns for the first rollout bands. |
| Tool surfaces and service-tool mediation | `instances/_shared/portal/application/service_tools.py`, `instances/_shared/runtime/flavors/fnd/portal/tools/*`, `docs/plans/tool_dev.md` | deferred | not assigned | Tools remain outside the next operating band until shell-attached portal slices are stable. |
| Sandbox-driven flows and session staging | `instances/_shared/portal/sandbox/*`, `instances/_shared/portal/application/workbench/sandbox_sessions.py` | deferred | not assigned | Sandboxes are orchestration boundaries, not next-band client surfaces. |
| Maps, AGRO, and HOPS-specific mediation | `instances/_shared/portal/application/agro/*`, `instances/_shared/portal/application/time_address_schema.py`, `docs/plans/tool_dev.md` | deferred | not assigned | Requires later mediation and HOPS work. Not a post-MVP first-band target. |
| Standalone newsletter-admin tool surface | `instances/_shared/runtime/flavors/fnd/portal/api/newsletter_admin.py`, `packages/tools/newsletter_admin/*` | discard | none | Do not rebuild newsletter parity as a standalone shared portal target. Any future operator flow must be re-specified as its own slice. |
| AWS-CMS, PayPal, and provider-admin integration control planes | `instances/_shared/runtime/flavors/fnd/portal/api/admin_integrations.py`, `instances/_shared/runtime/flavors/fnd/portal/api/paypal_checkout.py` | evidence only | none | These are instance and operator specific. They must not define the shared post-MVP portal roadmap. |
| Board workspace, streams, and calendar workbench | `instances/_shared/runtime/flavors/fnd/portal/services/workspace_store.py` | evidence only | none | Useful as workflow evidence only, not as a shared rollout target. |
