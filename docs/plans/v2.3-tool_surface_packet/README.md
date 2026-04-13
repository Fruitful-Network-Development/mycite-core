# V2.3 Tool Surface Packet

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

This packet turns the 2026-04-12 audit into one foundational implementation
plan plus one plan per concrete tool or legacy portal tool surface.

The packet now uses a **family + slices** shape:

- one canonical family-root doc where the family is real and clarified
- subordinate slice/crosswalk docs where current live tools or legacy names
  still matter
- held-out leftovers where no clarified family root exists yet

Read in this order:

1. [../../audits/v2_tool_surface_and_legacy_tool_audit_2026-04-12.md](../../audits/v2_tool_surface_and_legacy_tool_audit_2026-04-12.md)
2. [../v2.3-tool_exposure_and_admin_activity_bar_alignment.md](../v2.3-tool_exposure_and_admin_activity_bar_alignment.md)
3. [../../contracts/tool_exposure_and_admin_activity_bar_contract.md](../../contracts/tool_exposure_and_admin_activity_bar_contract.md)
4. the family-root plan that matches the next tool decision
5. subordinate slice/crosswalk docs only when the family-root doc points to them

Implementation still requires an approved slice or surface entry. Family-root
docs narrow the next build family; they do not replace slice approval.

## Canonical family roots

| Plan | Queue posture | Primary gate or live ids |
| --- | --- | --- |
| [aws_csm.md](aws_csm.md) | `implemented family root; next slice pending` | existing live ids `aws`, `aws_narrow_write`, `aws_csm_sandbox`, `aws_csm_onboarding`, `aws_csm_newsletter` |
| [fnd_ebi.md](fnd_ebi.md) | `next actual build target` | `tool_exposure.fnd_ebi` |
| [maps.md](maps.md) | `near-term candidate` | current live id `maps` |
| [agro_erp.md](agro_erp.md) | `clarified family, not immediate queue` | `tool_exposure.agro_erp` |
| [fnd_dcm.md](fnd_dcm.md) | `typed family plan only` | `tool_exposure.fnd_dcm` |
| [calendar.md](calendar.md) | `typed family plan only` | `tool_exposure.calendar` |
| [paypal_ppm.md](paypal_ppm.md) | `typed family plan only` | `tool_exposure.paypal_ppm` |
| [keycloak_sso.md](keycloak_sso.md) | `typed family plan only` | `tool_exposure.keycloak_sso` |

## Current implemented slice docs and crosswalks

| Plan | Packet role | Family root |
| --- | --- | --- |
| [aws.md](aws.md) | `implemented slice doc` | [AWS-CSM](aws_csm.md) |
| [aws_narrow_write.md](aws_narrow_write.md) | `implemented slice doc` | [AWS-CSM](aws_csm.md) |
| [aws_csm_sandbox.md](aws_csm_sandbox.md) | `implemented slice doc` | [AWS-CSM](aws_csm.md) |
| [aws_csm_onboarding.md](aws_csm_onboarding.md) | `implemented slice doc` | [AWS-CSM](aws_csm.md) |
| [aws_platform_admin.md](aws_platform_admin.md) | `legacy crosswalk` | [AWS-CSM](aws_csm.md) |
| [aws_tenant_actions.md](aws_tenant_actions.md) | `legacy crosswalk` | [AWS-CSM](aws_csm.md) |
| [newsletter_admin.md](newsletter_admin.md) | `retired crosswalk` | [AWS-CSM](aws_csm.md) |
| [paypal_service_agreement.md](paypal_service_agreement.md) | `subordinate PayPal slice direction` | [PAYPAL-PPM](paypal_ppm.md) |
| [paypal_tenant_actions.md](paypal_tenant_actions.md) | `subordinate PayPal slice direction` | [PAYPAL-PPM](paypal_ppm.md) |
| [paypal_demo.md](paypal_demo.md) | `retired crosswalk` | [PAYPAL-PPM](paypal_ppm.md) |

## Child capability directions

| Plan | Packet role | Family root |
| --- | --- | --- |
| [analytics.md](analytics.md) | `subordinate capability direction` | [FND-EBI](fnd_ebi.md) |

## Held-out leftovers and isolation docs

| Plan | Queue posture | Notes |
| --- | --- | --- |
| [data_tool.md](data_tool.md) | `held out` | no clarified family root yet |
| [fnd_provisioning.md](fnd_provisioning.md) | `held out` | preserve until family-level clarification exists |
| [operations.md](operations.md) | `held out / legacy-isolation` | not an approved family root |
| [tenant_progeny_profiles.md](tenant_progeny_profiles.md) | `held out` | preserve until family-level clarification exists |
| [legacy_admin.md](legacy_admin.md) | `legacy-isolation` | outside the narrowed near-term queue |
