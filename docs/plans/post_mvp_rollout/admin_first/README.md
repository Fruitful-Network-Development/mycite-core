# Admin-First Rollout

Authority: [../../authority_stack.md](../../authority_stack.md)

This subtree defines the post-MVP operating surface for replacing the old portal operationally through an admin-first path.

Use this subtree when the goal is:

- restore one usable admin shell before broader client rollout
- stage tool-bearing work without letting tools own shell legality
- make AWS the first real tool-bearing target
- keep Maps and AGRO-ERP sequenced after AWS

## Relationship to the global rollout bands

The admin-first track is a nested rollout track, not a second authority stack.

| Admin-first band | Parent rollout band | Meaning |
|---|---|---|
| `Admin Band 0 Internal Admin Replacement` | `Band 0 Internal Only` | build the stable admin shell, runtime envelope, home/status surface, and tool registry/launcher |
| `Admin Band 1 Trusted-Tenant AWS Read-Only` | `Band 1 Trusted-Tenant Read-Only` | first trusted-tenant-safe tool-bearing exposure, with AWS status and visibility only |
| `Admin Band 2 Trusted-Tenant AWS Narrow Write` | `Band 2 Trusted-Tenant Writable Slice` | first bounded AWS write workflow after the read-only AWS slice is stable |

Maps and AGRO-ERP remain follow-on planning surfaces. They do not displace AWS-first ordering.

## Use order

1. Read [admin_first_rollout_band.md](admin_first_rollout_band.md).
2. Read [frozen_decisions_admin_band.md](frozen_decisions_admin_band.md).
3. Read [admin_first_parity_ledger.md](admin_first_parity_ledger.md).
4. Read [admin_shell_entry_requirements.md](admin_shell_entry_requirements.md).
5. Read [admin_runtime_envelope.md](admin_runtime_envelope.md).
6. Read [admin_home_and_status_surface.md](admin_home_and_status_surface.md).
7. Read [tool_registry_and_launcher_surface.md](tool_registry_and_launcher_surface.md).
8. Read [aws_first_surface.md](aws_first_surface.md).
9. After AWS read-only and AWS narrow-write are complete, read [../post_aws_tool_platform/README.md](../post_aws_tool_platform/README.md).
10. Read [maps_follow_on_surface.md](maps_follow_on_surface.md).
11. Read [agro_erp_follow_on_surface.md](agro_erp_follow_on_surface.md).
12. Use the matching slice files in [../slice_registry/](../slice_registry/).

## Core rules

- The admin shell comes before any tool-bearing slice.
- The runtime envelope comes before any trusted-tenant admin exposure.
- The admin home/status surface comes before the tool registry/launcher surface.
- The tool registry/launcher surface comes before AWS.
- AWS comes before Maps.
- Maps comes before AGRO-ERP.
- Tools launch through shell-owned registry entries and runtime entrypoints only.
- The old portal is replaced by slice-by-slice operational takeover, not by package or route parity.

## Current planning target

- `Admin Band 0 Internal Admin Replacement` is the stable admin shell base.
- `Admin Band 1 Trusted-Tenant AWS Read-Only` and `Admin Band 2 Trusted-Tenant AWS Narrow Write` are the reference tool slices.
- [../post_aws_tool_platform/README.md](../post_aws_tool_platform/README.md) now governs future tool drop-in work.
- The next allowed tool track is Maps; AGRO-ERP still follows Maps.
