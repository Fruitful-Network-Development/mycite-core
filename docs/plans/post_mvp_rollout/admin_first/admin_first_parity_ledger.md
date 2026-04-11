# Admin-First Parity Ledger

Authority: [../../v2-authority_stack.md](../../v2-authority_stack.md)

This ledger classifies old portal admin and provider workflow areas for the admin-first replacement path.

The unit of classification is workflow area, not file parity.

| Workflow area | V1 evidence | Classification | Target admin band | V2 rebuild note |
|---|---|---|---|---|
| Admin shell landing, service navigation, and provider entry cards | `instances/_shared/runtime/flavors/fnd/app.py`, `instances/_shared/runtime/flavors/fnd/portal/core_services/runtime.py` | first-band target | `Admin Band 0` | Rebuild as one admin shell entry plus one home/status surface. Do not recreate host-owned tab sprawl. |
| Service-tool catalog and launch affordances | `instances/_shared/portal/application/service_tools.py`, `instances/_shared/portal/application/shell/tools.py`, `instances/_shared/runtime/flavors/fnd/portal/tools/runtime.py` | first-band target | `Admin Band 0` | Rebuild as a shell-owned tool registry/launcher. Do not scan tool packages at runtime to decide legality. |
| Runtime/admin posture and operational status | `instances/_shared/runtime/flavors/fnd/app.py`, `instances/_shared/runtime/flavors/fnd/portal/api/config.py`, `instances/_shared/runtime/flavors/fnd/portal/services/local_audit_log.py` | first-band target | `Admin Band 0` | Rebuild as one read-only admin home/status surface that makes rollout band and exposure posture explicit. |
| AWS-CMS admin status, mailbox readiness, and newsletter operational visibility | `instances/_shared/runtime/flavors/fnd/portal/api/admin_integrations.py`, `packages/tools/aws_csm/*`, `docs/plans/tool_dev.md`, `docs/plans/news_letter_workflow_correction.md` | first-band target | `Admin Band 1` then `Admin Band 2` | AWS is the first real tool-bearing target. Start read-only, then add one bounded write slice only if the read-only slice is stable. |
| Standalone newsletter-admin portal/tool surface | `instances/_shared/runtime/flavors/fnd/portal/api/newsletter_admin.py`, `packages/tools/newsletter_admin/*`, `docs/plans/news_letter_workflow_correction.md` | discard | none | Do not rebuild newsletter as a standalone tool. Newsletter mediation belongs inside the AWS admin surface. |
| PayPal provider-admin and checkout control plane | `instances/_shared/runtime/flavors/fnd/portal/api/paypal_checkout.py`, `packages/tools/paypal_csm/*` | later-band target | after `Admin Band 2` | PayPal may return later as its own slice family. It must not join the AWS-first band. |
| Keycloak and auth-provider operations | `packages/tools/keycloak_sso/*` | later-band target | after AWS | Only after the shell, registry, and AWS-first path are stable. |
| Website analytics and member analytics | `instances/_shared/runtime/flavors/fnd/portal/api/website_analytics.py`, `packages/tools/analytics/*` | deferred | not assigned | Analytics is not part of the fastest safe operational replacement path. |
| Progeny config, tenant-progeny, and related admin workbench flows | `instances/_shared/runtime/flavors/fnd/portal/api/progeny_config.py`, `instances/_shared/runtime/flavors/fnd/portal/api/progeny_workbench.py`, `instances/_shared/runtime/flavors/fnd/portal/api/tenant_progeny.py` | deferred | not assigned | Too mixed with hosted and progeny decisions for the admin-first band. |
| Data workspace, publish, and sandbox-driven admin flows | `instances/_shared/portal/application/workbench/*`, `instances/_shared/portal/application/workbench/sandbox_sessions.py` | deferred | not assigned | These reopen tool and sandbox drift too early. |
| Maps tool mediation | `docs/plans/tool_dev.md`, `docs/plans/hanus_interface_model.md` | later-band target | after AWS | Maps follows AWS. It should reopen mediation work only after the admin shell and launcher model are proven. |
| AGRO-ERP admin mediation and time/HOPS binding | `instances/_shared/portal/application/agro/config_bindings.py`, `instances/_shared/portal/application/time_address_schema.py`, `docs/plans/tool_dev.md` | later-band target | after Maps | AGRO-ERP follows Maps. Do not rebuild AGRO as the first tool-bearing target. |
| Generic operations workspace and board/workspace surfaces | `packages/tools/operations/*`, `instances/_shared/runtime/flavors/fnd/portal/services/workspace_store.py` | evidence only | none | Useful as operational evidence only. It must not define the new admin-first structure. |

## Admin-first reading of v1

- Break mixed provider dashboards into separate future slices.
- Keep AWS-first because it has the clearest operational pressure, the clearest v1 evidence, and the clearest retirement rule for `newsletter-admin`.
- Treat PayPal, analytics, and progeny admin flows as later or deferred so the first admin shell stays small and stable.
