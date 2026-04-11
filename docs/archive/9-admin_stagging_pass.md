# Admin Staging Pass

## PROMPT

Work only inside `MyCiteV2/`.

Your task is not to implement more portal logic yet.

Your task is to perform one docs-only, admin-first staging pass that externalizes exactly how MyCiteV2 should replace the old portal operationally, so that later implementation can proceed cleanly per tool.

Optimize for:
- fastest safe path back to a usable admin portal
- preserving v2 structural integrity
- making AWS the first real tool-bearing target
- making later prompts smaller and more precise
- preventing multi-agent drift

Do not implement runtime behavior.
Do not implement tools.
Do not add ports/adapters/modules beyond docs.
Do not port v1 code.
This is a planning-and-structure pass only.

==================================================
PRIMARY GOAL
==================================================

Externalize the next operating surface for V2 so future agents can build:

1. one stable admin shell entry
2. one tenant-safe admin runtime envelope
3. one admin home/status surface
4. one tool registry / tool launcher surface
5. one AWS-first admin slice
6. then Maps
7. then AGRO-ERP

The result must make it clear how V2 replaces the old portal without collapsing back into v1 structure.

==================================================
AUTHORITIES TO USE
==================================================

Read and follow, in order:

1. `MyCiteV2/README.md`
2. `MyCiteV2/docs/plans/authority_stack.md`
3. `MyCiteV2/docs/plans/README.md`
4. `MyCiteV2/docs/ontology/structural_invariants.md`
5. `MyCiteV2/docs/ontology/dependency_direction.md`
6. `MyCiteV2/docs/ontology/interface_surfaces.md`
7. `MyCiteV2/docs/contracts/import_rules.md`
8. `MyCiteV2/docs/testing/architecture_boundary_checks.md`
9. `MyCiteV2/docs/plans/master_build_sequence.md`
10. `MyCiteV2/docs/plans/phase_completion_definition.md`
11. `MyCiteV2/docs/testing/phase_gates.md`
12. `MyCiteV2/docs/plans/mvp_boundary.md`
13. `MyCiteV2/docs/plans/mvp_acceptance_criteria.md`
14. `MyCiteV2/docs/plans/mvp_end_to_end_slice.md`
15. `MyCiteV2/docs/plans/post_mvp_rollout/README.md`
16. `MyCiteV2/docs/plans/post_mvp_rollout/portal_rollout_bands.md`
17. `MyCiteV2/docs/plans/post_mvp_rollout/v1_parity_ledger.md`
18. `MyCiteV2/docs/plans/post_mvp_rollout/client_exposure_gates.md`
19. `MyCiteV2/docs/plans/post_mvp_rollout/runtime_entrypoints.md`
20. `MyCiteV2/docs/plans/post_mvp_rollout/port_adapter_ownership_matrix.md`
21. `MyCiteV2/docs/plans/post_mvp_rollout/frozen_decisions_current_band.md`
22. `MyCiteV2/docs/plans/post_mvp_rollout/agent_prompt_templates.md`
23. `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/README.md`
24. the existing slice files already created there
25. `MyCiteV2/docs/plans/v1-migration/v1_drift_ledger.md`
26. `MyCiteV2/docs/plans/v1-migration/v1_audit_map.md`
27. `MyCiteV2/docs/plans/v1-migration/v1_retention_vs_recreation.md`
28. `MyCiteV2/docs/plans/v1-migration/source_authority_index.md`

Then use v1 planning docs as lower-precedence evidence:
- `docs/plans/tool_dev.md`
- `docs/plans/tool_alignment.md`
- `docs/plans/hanus_interface_model.md`
- other relevant `docs/plans/*.md`

Use v1 code only as workflow and drift evidence.
Do not treat v1 package layout as a template.

==================================================
WHAT THIS PASS MUST DECIDE
==================================================

Create the authoritative admin-first rollout surface for post-MVP V2.

You must explicitly define:

1. the first stable admin operating band
2. the admin shell entry requirements
3. the tenant-safe admin runtime envelope
4. the admin home/status surface requirements
5. the tool registry / tool launcher model
6. the AWS-first rollout sequence
7. the rule that Maps follows AWS and AGRO-ERP follows Maps
8. what remains internal-only during this band
9. what must be true before any admin tool becomes trusted-tenant usable
10. which v1 admin/provider surfaces are:
   - first-band target
   - later-band target
   - deferred
   - discard
   - evidence only

==================================================
TARGET OPERATING ORDER
==================================================

Use this order as the planning target unless the existing authority docs forbid it:

1. admin shell entry
2. tenant-safe admin runtime envelope
3. admin home / status surface
4. tool registry / launcher surface
5. AWS-first read-only/status surface
6. AWS-first narrow writable/admin workflow if justified
7. Maps follow-on planning surface
8. AGRO-ERP follow-on planning surface

Do not make Maps or AGRO-ERP first.
Do not make broad client rollout first.
Do not make tools bypass the admin shell.

==================================================
DIRECTORY AND FILE TASK
==================================================

Create or update a coherent subtree under:

`MyCiteV2/docs/plans/post_mvp_rollout/admin_first/`

At minimum create or update:

- `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/README.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/admin_first_rollout_band.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/admin_first_parity_ledger.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/admin_shell_entry_requirements.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/admin_runtime_envelope.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/admin_home_and_status_surface.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/tool_registry_and_launcher_surface.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/aws_first_surface.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/maps_follow_on_surface.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/agro_erp_follow_on_surface.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/frozen_decisions_admin_band.md`

Create or update slice-registry entries for the admin-first path, such as:

- `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band0_shell_entry.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band0_home_status.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band0_tool_registry.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band1_aws_read_only_surface.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band2_aws_narrow_write_surface.md`

Only create entries that are concrete enough to guide later implementation.

Also update if needed:
- `MyCiteV2/docs/plans/post_mvp_rollout/agent_prompt_templates.md`
- `MyCiteV2/docs/testing/slice_gate_template.md`
- `MyCiteV2/docs/decisions/` with a new ADR if needed, for example:
  `decision_record_0011_admin_first_tool_bearing_rollout.md`

==================================================
WHAT THE DOCS MUST ANSWER
==================================================

The new docs must answer all of these:

- What is the first stable admin-visible band?
- What must exist before the old portal can begin to be operationally replaced?
- How does the admin shell stay composition-only and not become semantic ownership?
- How does the tool registry work without letting tools define shell legality?
- Why is AWS first?
- What exact AWS slice should be built first?
- What is explicitly not allowed during the AWS-first band?
- What has to be true before Maps starts?
- What has to be true before AGRO-ERP starts?
- Which old portal admin/provider surfaces are being rebuilt first, and which are postponed?

==================================================
AWS-FIRST RULE
==================================================

Treat AWS as the first real post-MVP tool-bearing target.

But do not jump straight to “implement AWS tool.”

Instead, define the planning surface that makes AWS implementation safe:
- what the AWS first slice is
- whether it starts read-only
- what runtime entrypoint it needs
- what ports/adapters it will likely require later
- what semantics remain outside AWS
- what provider-admin or newsletter-admin parity from v1 is discarded vs deferred
- what must already be stable in the admin shell before AWS can be exposed

==================================================
PROHIBITED SHORTCUTS
==================================================

Do not:
- implement admin runtime code
- implement AWS code
- implement Maps code
- implement AGRO-ERP code
- broaden client rollout planning
- let tool planning bypass shell and runtime entrypoint policy
- recreate v1 provider-admin structure directly
- create vague “later roadmap” prose without slice and gate structure
- let admin shell planning become host-owned semantics

==================================================
REQUIRED CONTENT STYLE
==================================================

The docs must be operational and execution-oriented.

Prefer:
- checklists
- ownership tables
- rollout-band criteria
- slice files
- explicit in-scope / out-of-scope sections
- exact gating rules
- prompt-ready language

Avoid:
- long abstract essays
- vague future statements
- feature wishlists
- parity promises without boundaries

==================================================
END-OF-TASK RESPONSE
==================================================

Return:
1. the exact files created or updated
2. the admin-first rollout band you defined
3. the first AWS slice you defined
4. the ordering you established for AWS, Maps, and AGRO-ERP
5. the main v1 admin/provider classifications added
6. the frozen decisions preserved for this band
7. how this will reduce the size of future implementation prompts
8. any remaining ambiguity that still needs explicit future choice

---


## OUTPUT

The admin-first staging surface is now in place as docs only, inside `MyCiteV2/`, with no new runtime, tool, port, adapter, or domain code.

**Files**
Created:
- [admin_first/README.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/README.md)
- [admin_first_rollout_band.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/admin_first_rollout_band.md)
- [admin_first_parity_ledger.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/admin_first_parity_ledger.md)
- [admin_shell_entry_requirements.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/admin_shell_entry_requirements.md)
- [admin_runtime_envelope.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/admin_runtime_envelope.md)
- [admin_home_and_status_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/admin_home_and_status_surface.md)
- [tool_registry_and_launcher_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/tool_registry_and_launcher_surface.md)
- [aws_first_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/aws_first_surface.md)
- [maps_follow_on_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/maps_follow_on_surface.md)
- [agro_erp_follow_on_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/agro_erp_follow_on_surface.md)
- [frozen_decisions_admin_band.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/frozen_decisions_admin_band.md)
- [admin_band0_shell_entry.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band0_shell_entry.md)
- [admin_band0_home_status.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band0_home_status.md)
- [admin_band0_tool_registry.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band0_tool_registry.md)
- [admin_band1_aws_read_only_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band1_aws_read_only_surface.md)
- [admin_band2_aws_narrow_write_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band2_aws_narrow_write_surface.md)
- [decision_record_0011_admin_first_tool_bearing_rollout.md](/srv/repo/mycite-core/MyCiteV2/docs/decisions/decision_record_0011_admin_first_tool_bearing_rollout.md)

Updated:
- [README.md](/srv/repo/mycite-core/MyCiteV2/README.md)
- [plans/README.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/README.md)
- [post_mvp_rollout/README.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/README.md)
- [portal_rollout_bands.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/portal_rollout_bands.md)
- [frozen_decisions_current_band.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/frozen_decisions_current_band.md)
- [v1_parity_ledger.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/v1_parity_ledger.md)
- [client_exposure_gates.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/client_exposure_gates.md)
- [slice_registry/README.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/README.md)
- [slice_template.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/slice_template.md)
- [agent_prompt_templates.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/agent_prompt_templates.md)
- [slice_gate_template.md](/srv/repo/mycite-core/MyCiteV2/docs/testing/slice_gate_template.md)

**Admin-First Band**
The first stable admin operating band is `Admin Band 0 Internal Admin Replacement`, nested under the global `Band 0 Internal Only` posture. It requires, in order, one stable admin shell entry, one tenant-safe admin runtime envelope, one admin home/status surface, and one shell-owned tool registry/launcher.

**First AWS Slice**
The first AWS slice is [admin_band1_aws_read_only_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band1_aws_read_only_surface.md). It is explicitly read-only and limited to AWS operational visibility: mailbox/profile readiness, SMTP-ready vs Gmail-pending vs verified evidence state, selected verified sender, canonical newsletter operational profile summary, and safe compatibility warnings.

**Ordering**
The admin-first ordering is now fixed as:
- admin shell entry
- tenant-safe admin runtime envelope
- admin home/status
- tool registry/launcher
- AWS read-only
- AWS narrow write
- Maps follow-on
- AGRO-ERP follow-on

**Main V1 Classifications**
The new [admin_first_parity_ledger.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/admin_first_parity_ledger.md) classifies:
- first-band target: old admin shell/service navigation, admin home/status posture, service-tool catalog/launcher model, AWS-CMS plus newsletter operational visibility
- later-band target: PayPal, keycloak, Maps, AGRO-ERP
- deferred: analytics, progeny/admin workbench flows, sandbox/workbench/data-workspace admin surfaces
- discard: standalone `newsletter-admin`
- evidence only: generic operations/workspace surfaces

**Frozen Decisions**
The admin band now preserves all of these as explicit freezes:
- AWS is the first real tool-bearing target
- Maps cannot start before AWS
- AGRO-ERP cannot start before Maps
- `newsletter-admin` stays retired as a standalone surface
- no tool may bypass the shell-owned registry/launcher
- no tool may define shell legality
- no direct provider-admin route may become the v2 entry surface
- no PayPal, analytics, keycloak, progeny workbench, or sandbox surface may displace AWS in this track

**Why Future Prompts Get Smaller**
Future implementation prompts can now point to:
- [admin_first/README.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/README.md)
- one admin slice file
- one tool-track doc such as [aws_first_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/aws_first_surface.md)
- [agent_prompt_templates.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/agent_prompt_templates.md)
- [slice_gate_template.md](/srv/repo/mycite-core/MyCiteV2/docs/testing/slice_gate_template.md)

That removes the need to restate admin-band ordering, tool-launch policy, AWS-first rationale, and the shell/runtime boundary every time.

**Remaining Explicit Ambiguities**
These stay intentionally unresolved for now:
- the exact future port and adapter names for AWS read-only and AWS narrow-write seams
- whether admin home/status and tool registry stay separate views or later become one shell payload
- the exact bounded field set for the first AWS narrow write
- whether dispatch-health belongs in the first AWS read-only slice or a later AWS follow-up slice

I left unrelated `MyCiteV2/docs/archive/` worktree changes alone.

---
