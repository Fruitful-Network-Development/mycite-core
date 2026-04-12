# V2.3 Tool Surface Packet

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

This packet turns the 2026-04-12 audit into one foundational implementation
plan plus one plan per concrete tool or legacy portal tool surface.

Read in this order:

1. [../../audits/v2_tool_surface_and_legacy_tool_audit_2026-04-12.md](../../audits/v2_tool_surface_and_legacy_tool_audit_2026-04-12.md)
2. [../v2.3-tool_exposure_and_admin_activity_bar_alignment.md](../v2.3-tool_exposure_and_admin_activity_bar_alignment.md)
3. [../../contracts/tool_exposure_and_admin_activity_bar_contract.md](../../contracts/tool_exposure_and_admin_activity_bar_contract.md)
4. the per-tool plan that matches the next tool decision

## Current V2 tools

| Plan | Disposition | Config gate target |
| --- | --- | --- |
| [aws.md](aws.md) | `current_v2` | `aws` |
| [aws_narrow_write.md](aws_narrow_write.md) | `current_v2` | `aws_narrow_write` |
| [aws_csm_sandbox.md](aws_csm_sandbox.md) | `current_v2` | `aws_csm_sandbox` |
| [aws_csm_onboarding.md](aws_csm_onboarding.md) | `current_v2` | `aws_csm_onboarding` |
| [maps.md](maps.md) | `current_v2` | `maps` |

## Legacy-to-V2 crosswalks

| Plan | Disposition | Config gate target |
| --- | --- | --- |
| [aws_platform_admin.md](aws_platform_admin.md) | `carry_forward` | `aws` |
| [aws_tenant_actions.md](aws_tenant_actions.md) | `carry_forward` | `aws_csm_onboarding` |

## Carry-forward and deferred tool candidates

| Plan | Disposition | Config gate target |
| --- | --- | --- |
| [agro_erp.md](agro_erp.md) | `carry_forward` | `agro_erp` |
| [fnd_ebi.md](fnd_ebi.md) | `carry_forward` | `fnd_ebi` |
| [data_tool.md](data_tool.md) | `legacy_isolation` | `data_tool` |
| [fnd_provisioning.md](fnd_provisioning.md) | `defer` | `fnd_provisioning` |
| [operations.md](operations.md) | `legacy_isolation` | `operations` |
| [analytics.md](analytics.md) | `defer` | `analytics` |
| [keycloak_sso.md](keycloak_sso.md) | `defer` | `keycloak_sso` |
| [tenant_progeny_profiles.md](tenant_progeny_profiles.md) | `defer` | `tenant_progeny_profiles` |
| [paypal_service_agreement.md](paypal_service_agreement.md) | `defer` | `paypal_service_agreement` |
| [paypal_tenant_actions.md](paypal_tenant_actions.md) | `defer` | `paypal_tenant_actions` |
| [paypal_demo.md](paypal_demo.md) | `legacy_isolation` | `paypal_demo` |

## Retirement and isolation

| Plan | Disposition | Config gate target |
| --- | --- | --- |
| [newsletter_admin.md](newsletter_admin.md) | `discard` | `newsletter_admin` |
| [legacy_admin.md](legacy_admin.md) | `legacy_isolation` | `legacy_admin` |
