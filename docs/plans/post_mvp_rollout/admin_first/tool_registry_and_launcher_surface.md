# Tool Registry And Launcher Surface

Authority: [../../v2-authority_stack.md](../../v2-authority_stack.md)

This file defines how admin tools are discovered and launched without letting tools define shell legality.

## Model

The registry is shell-owned.
The launcher is shell-owned.
Tools do not self-register at runtime by scanning `packages/tools/`.

The registry records which slices are intentionally launchable.
The launcher invokes the matching runtime entrypoint only after shell and exposure checks pass.

## Required registry fields

Every future admin tool entry must declare:

- `tool_id`
- `label`
- `slice_id`
- `entrypoint_id`
- `admin_band`
- `exposure_status`
- `read_write_posture`
- `surface_pattern`
- `status_summary`
- `audience`
- `internal_only_reason` if not yet exposed
- `audit_required`
- `read_after_write_required`
- `discovery_mode`
- `launch_contract`
- `default_posture`

## Launcher rules

- Launching happens through the admin shell entry and registry only.
- A launch request must resolve to one approved slice id.
- A tool may not provide its own alternate launcher path.
- A tool may not define shell verbs, shell legality, or navigation truth.
- A runtime entrypoint may not be considered launchable until it is in both:
  - `runtime_entrypoints.md`
  - `instances/_shared/runtime/runtime_platform.py`
  - the shell-owned registry

## AWS-first rule

- The first externalized tool-bearing registry entry is AWS.
- CTS-GIS may not appear in the registry before the AWS read-only slice is stable.
- AGRO-ERP may not appear in the registry before the CTS-GIS follow-on conditions are met.

## Forbidden registry drift

- no direct package scanning to discover tools
- no provider-specific hidden routes outside the registry
- no standalone `newsletter-admin` entry
- no mixed provider super-entry that bundles AWS, PayPal, analytics, and other admin surfaces together

## Minimum tests for the registry/launcher surface

- registry payload-shape test
- deny-by-default test for unapproved entries
- runtime integration test proving launch resolution follows registry and catalog
- architecture boundary test proving no tool code owns shell discoverability
