# Completion Gate Stage & Prime Pass

Completion Gate Stage & Prime Pass
## PROMPT:

Work only inside `MyCiteV2/`.

Your task is not to implement more portal logic yet.

Your task is to perform one comprehensive staging/priming pass that externalizes the next operating system for building out the rest of MyCiteV2 into a client-stable portal, while preserving the architecture that the MVP has already proven.

The purpose of this pass is to maximize:
- accuracy
- architectural integrity
- pace
- low-drift execution across multiple future agents
- safe rollout toward client access

Do not implement new portal workflows.
Do not port v1 code.
Do not broaden runtime behavior.
Do not add tools or sandboxes.
Do not add new domain logic.
This is a planning-and-structure pass only.

==================================================
PRIMARY GOAL
==================================================

Create the authoritative post-MVP planning surface that tells future agents:

- how the rest of the portal should be built out
- in what order
- how old portal workflows map into the new paradigm
- what can be exposed to clients safely and when
- how to keep slices narrow
- how to avoid reintroducing v1 drift
- how to stage rollout from internal-only to client-stable access
- how each future slice should be specified, implemented, tested, and exposed

The output must make future work more executable with smaller prompts and less ambiguity.

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
15. `MyCiteV2/docs/plans/mvp_out_of_scope.md`
16. `MyCiteV2/docs/plans/v1-migration/v1_drift_ledger.md`
17. `MyCiteV2/docs/plans/v1-migration/v1_audit_map.md`
18. `MyCiteV2/docs/plans/v1-migration/v1_retention_vs_recreation.md`
19. `MyCiteV2/docs/plans/v1-migration/source_authority_index.md`

Then use v1 planning docs as lower-precedence evidence:
- `docs/plans/tool_dev.md`
- `docs/plans/hanus_interface_model.md`
- `docs/plans/tool_alignment.md`
- other relevant `docs/plans/*.md`

Use v1 code only as workflow and drift evidence.
Do not treat v1 package layout as a template.

Also consider the current repo state:
- the architecture MVP is complete
- one narrow runtime composition path exists
- the next work is no longer “prove architecture”
- the next work is “expand stable operating bands” carefully

==================================================
WHAT THIS PASS MUST EXTERNALIZE
==================================================

You must create a comprehensive post-MVP staging/priming surface that externalizes all of the following:

1. Portal rollout bands
   Define how V2 should move from:
   - internal-only
   - trusted-tenant read-only
   - trusted-tenant writable slice
   - broader client rollout

2. V1 parity ledger
   For each meaningful old-portal workflow or capability area, classify it as:
   - first-band target
   - later-band target
   - deferred
   - discard
   - evidence only

3. Slice registry
   Define how every future V2 slice must be specified before implementation.
   Each slice must state:
   - user-facing purpose
   - client value
   - owning layers
   - required ports
   - required adapters
   - required runtime composition
   - tests
   - rollout band
   - out-of-scope items
   - exposure status

4. Client exposure gates
   Define exactly what must be true before any slice becomes client-visible.

5. Runtime entrypoint policy
   Define how runtime entrypoints are cataloged and constrained so hosts remain composition-only.

6. Port/adapter ownership matrix
   Define for each future seam:
   - who owns semantics
   - who owns contracts
   - who owns adapter behavior
   - what is forbidden to drift across those boundaries

7. Frozen decisions for the current band
   Define which unresolved questions must remain frozen so future agents do not widen scope.

8. Prompt operating templates
   Create reusable task-prompt templates for future agents so later work can be assigned with minimal context.

==================================================
DIRECTORY AND FILE TASK
==================================================

Create or update a coherent post-MVP planning subtree under `MyCiteV2/docs/plans/`.

At minimum create or update:

- `MyCiteV2/docs/plans/post_mvp_rollout/README.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/portal_rollout_bands.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/v1_parity_ledger.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/client_exposure_gates.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/runtime_entrypoints.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/port_adapter_ownership_matrix.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/frozen_decisions_current_band.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/agent_prompt_templates.md`

Create a slice registry area:

- `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/README.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/slice_template.md`

Create at least a few initial slice entries, based on the best next stable-band candidates, for example:
- portal home / tenant status surface
- audit/activity visibility surface
- one narrow operational status surface
- one first writable workflow candidate

Only create slice entries if they are concrete enough to be useful.
Do not create filler entries.

Also create or update a testing support doc:

- `MyCiteV2/docs/testing/slice_gate_template.md`

And create or update one decisions doc if needed:

- `MyCiteV2/docs/decisions/decision_record_0010_post_mvp_staging_and_rollout_surface.md`

==================================================
DECISION RULES
==================================================

Use these rules when producing the planning surface:

- Prefer stable operating bands over broad feature parity.
- Prefer read-only exposure before writable exposure.
- Prefer one vertical slice at a time.
- Prefer workflow-level parity mapping, not file-level porting.
- Prefer explicit rollout gates over vague “ready later” language.
- Prefer slice templates that force narrow ownership declarations.
- Prefer future agent execution surfaces over narrative prose.
- Do not let runtime entrypoints become semantic owners.
- Do not assume tools or sandboxes are next.
- Do not assume broad client access comes immediately after MVP.

==================================================
WHAT TO CLASSIFY FROM V1
==================================================

Audit the current v1 portal logic and planning material as workflow evidence and classify major areas such as:

- portal shell / home / navigation
- audit / activity / event visibility
- tool surfaces
- sandbox-driven flows
- contract or reference workflows
- newsletter / AWS-style admin flows if relevant
- tenant or profile management surfaces
- status/reporting surfaces
- any read-only vs writable operational areas

For each area, decide:
- first-band
- later-band
- deferred
- discard
- evidence only

The goal is not to preserve v1.
The goal is to decide what should be rebuilt first for stable client access.

==================================================
REQUIRED CONTENT CHARACTERISTICS
==================================================

The new docs must be operational, not abstract.

They should answer questions like:
- What should be the next stable client-visible band?
- What workflow slices should be built before tools?
- What should stay internal-only for now?
- What must exist before clients can safely use V2?
- How should future slices be specified before code is written?
- How can an agent know what to build next without prior chat context?
- How can rollout happen without structural drift?

==================================================
PROHIBITED SHORTCUTS
==================================================

Do not:
- implement portal code
- add runtime behavior
- add ports/adapters/modules/tools/sandboxes
- recreate v1 package layout
- treat this as a generic “roadmap” with vague future intentions
- produce a report outside the repo docs
- create broad parity promises without slice/gate structure
- let client exposure planning bypass the existing authority stack or phase gates

==================================================
END-OF-TASK RESPONSE
==================================================

Return:
1. the exact files created or updated
2. the rollout bands you defined
3. the first-band slice candidates
4. the main classifications added to the v1 parity ledger
5. the key frozen decisions preserved
6. how future agent prompts will become smaller because of this pass
7. any remaining ambiguity that still needs explicit future choice

---


## OUTPUT:

The post-MVP rollout surface is now in place as docs-only guidance inside `MyCiteV2/`, with no new portal logic added.

**Files**
Created:
- [post_mvp_rollout/README.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/README.md)
- [portal_rollout_bands.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/portal_rollout_bands.md)
- [v1_parity_ledger.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/v1_parity_ledger.md)
- [client_exposure_gates.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/client_exposure_gates.md)
- [runtime_entrypoints.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/runtime_entrypoints.md)
- [port_adapter_ownership_matrix.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/port_adapter_ownership_matrix.md)
- [frozen_decisions_current_band.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/frozen_decisions_current_band.md)
- [agent_prompt_templates.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/agent_prompt_templates.md)
- [slice_registry/README.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/README.md)
- [slice_registry/slice_template.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/slice_template.md)
- [slice_registry/band1_portal_home_tenant_status.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/band1_portal_home_tenant_status.md)
- [slice_registry/band1_audit_activity_visibility.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/band1_audit_activity_visibility.md)
- [slice_registry/band1_operational_status_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/band1_operational_status_surface.md)
- [slice_registry/band2_profile_basics_write_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/band2_profile_basics_write_surface.md)
- [slice_gate_template.md](/srv/repo/mycite-core/MyCiteV2/docs/testing/slice_gate_template.md)
- [decision_record_0010_post_mvp_staging_and_rollout_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/decisions/decision_record_0010_post_mvp_staging_and_rollout_surface.md)

Updated:
- [README.md](/srv/repo/mycite-core/MyCiteV2/README.md)
- [plans/README.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/README.md)

**Rollout Bands**
- `Band 0 Internal Only`
- `Band 1 Trusted-Tenant Read-Only`
- `Band 2 Trusted-Tenant Writable Slice`
- `Band 3 Broader Client Rollout`

**First-Band Slice Candidates**
- [band1_portal_home_tenant_status.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/band1_portal_home_tenant_status.md) is the recommended first slice.
- [band1_audit_activity_visibility.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/band1_audit_activity_visibility.md) and [band1_operational_status_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/band1_operational_status_surface.md) are the next read-only candidates.
- [band2_profile_basics_write_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/band2_profile_basics_write_surface.md) is the first writable candidate, but it stays spec-only until a Band 1 slice is safely exposed.

**V1 Parity Ledger**
Main classifications now recorded in [v1_parity_ledger.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/v1_parity_ledger.md):
- First-band target: portal home/navigation orientation, local audit/activity visibility, operational status, tenant/profile summary reads.
- Later-band target: profile basics editing, contracts/handshake, external-event inbox, progeny workspace management, analytics.
- Deferred: data workspace/publish flows, tool surfaces, sandbox-driven flows, maps/AGRO/HOPS mediation.
- Discard: standalone newsletter-admin parity.
- Evidence only: AWS/PayPal/provider-admin control planes, board/streams/calendar workspace.

**Frozen Decisions**
Preserved in [frozen_decisions_current_band.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/frozen_decisions_current_band.md):
- stay in `Band 0` until a `Band 1` slice passes its gate
- read-only before any writable exposure
- preferred order: home first, then one visibility slice
- no tools, sandboxes, or flavor expansion in the current band
- no second public runtime entrypoint without a slice file and runtime-catalog update
- `external_events`, hosted/progeny breadth, and `mediation_surface` stay frozen out
- the first writable candidate remains the bounded publication-backed profile-basics slice only

**Why Future Prompts Get Smaller**
Future agents can now work from a compact packet:
- one slice file
- [agent_prompt_templates.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/agent_prompt_templates.md)
- [client_exposure_gates.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/client_exposure_gates.md)
- [runtime_entrypoints.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/runtime_entrypoints.md)
- [port_adapter_ownership_matrix.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/port_adapter_ownership_matrix.md)
- [slice_gate_template.md](/srv/repo/mycite-core/MyCiteV2/docs/testing/slice_gate_template.md)

That means less restating architecture, ownership, rollout policy, and test expectations in every prompt.

**Remaining Explicit Ambiguities**
These are intentionally left open rather than solved in this pass:
- whether the first tenant summary stays publication-only or later becomes a publication-plus-alias/progeny composite
- whether audit visibility and operational status stay separate slices or merge later
- whether broader analytics belongs in Band 2 or Band 3
- which of the two read-only visibility candidates should follow the home slice first


---


## CONSIDERATION & ASSSMENT

HERE


---
