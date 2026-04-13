# Admin-First Rollout

Authority: [../../v2-authority_stack.md](../../v2-authority_stack.md)

This subtree defines the admin-first sequencing context for replacing the old
portal operationally through an admin-first path.

Use this subtree now when the goal is:

- understand why the admin/AWS foundation was built in its current order
- keep CTS-GIS and AGRO-ERP sequenced correctly after the canonical V2 and V1 retirement closure
- avoid reopening completed admin-first foundation work as if it were still the active plan

## Relationship to the global rollout bands

The admin-first track is a nested rollout track, not a second authority stack.

| Admin-first band | Parent rollout band | Meaning |
|---|---|---|
| `Admin Band 0 Internal Admin Replacement` | `Band 0 Internal Only` | build the stable admin shell, runtime envelope, home/status surface, and tool registry/launcher |
| `Admin Band 1 Trusted-Tenant AWS Read-Only` | `Band 1 Trusted-Tenant Read-Only` | first trusted-tenant-safe tool-bearing exposure, with AWS status and visibility only |
| `Admin Band 2 Trusted-Tenant AWS Narrow Write` | `Band 2 Trusted-Tenant Writable Slice` | first bounded AWS write workflow after the read-only AWS slice is stable |

CTS-GIS and AGRO-ERP remain follow-on planning surfaces. They do not displace AWS-first ordering.

## Use order

1. Read [../current_planning_index.md](../current_planning_index.md).
2. Read [admin_first_rollout_band.md](admin_first_rollout_band.md).
3. Read [frozen_decisions_admin_band.md](frozen_decisions_admin_band.md).
4. Read [../post_aws_tool_platform/README.md](../post_aws_tool_platform/README.md).
5. Read [../../../records/22-v1_retirement_closure.md](../../../records/22-v1_retirement_closure.md).
6. Read [cts_gis_follow_on_surface.md](cts_gis_follow_on_surface.md) only after the active Band 1 and Band 2 sequence reaches CTS-GIS.
7. Read [agro_erp_follow_on_surface.md](agro_erp_follow_on_surface.md) only after CTS-GIS is reopened.

Historical design context for already-implemented work:

- [admin_shell_entry_requirements.md](admin_shell_entry_requirements.md)
- [admin_runtime_envelope.md](admin_runtime_envelope.md)
- [admin_home_and_status_surface.md](admin_home_and_status_surface.md)
- [tool_registry_and_launcher_surface.md](tool_registry_and_launcher_surface.md)
- [aws_first_surface.md](aws_first_surface.md)
- [aws_narrow_write_recovery.md](aws_narrow_write_recovery.md)

## Core rules

- The admin shell comes before any tool-bearing slice.
- The runtime envelope comes before any trusted-tenant admin exposure.
- The admin home/status surface comes before the tool registry/launcher surface.
- The tool registry/launcher surface comes before AWS.
- AWS comes before CTS-GIS.
- CTS-GIS comes before AGRO-ERP.
- Tools launch through shell-owned registry entries and runtime entrypoints only.
- The old portal is replaced by slice-by-slice operational takeover, not by package or route parity.

## Current planning target

- The admin shell and AWS-first foundation are implemented and should be read through [../../../records/README.md](../../../records/README.md), not as open planning.
- [../current_planning_index.md](../current_planning_index.md) now governs the reopened long-term sequence after retirement closure.
- CTS-GIS and AGRO-ERP remain deferred follow-on planning, not current execution targets.
