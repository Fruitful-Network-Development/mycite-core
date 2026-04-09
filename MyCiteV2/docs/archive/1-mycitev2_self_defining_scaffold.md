# MyCiteV2 Self-Defining Scaffold

## IDEA
- Convert the current `MyCiteV2/` skeleton into a documentation-first, inert scaffold that makes v2 architecture, authority order, dependency direction, phase order, and v1 drift explicit.
- Treat v1 as audit evidence only. Encode current drift examples from [aitas.py](/srv/repo/mycite-core/mycite_core/state_machine/aitas.py), [imported_refs.py](/srv/repo/mycite-core/mycite_core/reference_exchange/imported_refs.py), [context.py](/srv/repo/mycite-core/mycite_core/contract_line/context.py), [alias_service.py](/srv/repo/mycite-core/mycite_core/contract_line/alias_service.py), [service_tools.py](/srv/repo/mycite-core/instances/_shared/portal/application/service_tools.py), and [time_address_schema.py](/srv/repo/mycite-core/instances/_shared/portal/application/time_address_schema.py) into migration docs and ADRs.
- Make [tool_dev.md](/srv/repo/mycite-core/docs/plans/tool_dev.md), [hanus_interface_model.md](/srv/repo/mycite-core/docs/plans/hanus_interface_model.md), [tool_alignment.md](/srv/repo/mycite-core/docs/plans/tool_alignment.md), plus named synthesis docs inside `MyCiteV2/docs/plans/v1-migration/` the top authority chain.

#### Planned Structure
- Create this stable tree:
```text
MyCiteV2/
  README.md
  docs/
    README.md
    audits/README.md
    wiki/README.md
    ontology/
      structural_invariants.md
      dependency_direction.md
      interface_surfaces.md
      progressive_solidification.md
      tool_structure.md
      service_structure.md
    glossary/
      ontology_terms.md
    contracts/
      README.md
      module_contract_template.md
    testing/
      testing_philosophy.md
      phase_gates.md
    decisions/
      README.md
      decision_record_0001_v2_docs_are_authoritative.md
      decision_record_0002_no_direct_reuse_of_v1_package_structure.md
      decision_record_0003_dependency_direction_ports_and_adapters.md
      decision_record_0004_tools_attach_through_shell_surfaces.md
      decision_record_0005_state_machine_purity_and_serializability.md
      decision_record_0006_sandboxes_orchestrate_not_semantics.md
      decision_record_0007_hosts_compose_do_not_own_domain_logic.md
      decision_record_0008_payloads_and_caches_are_derived.md
    plans/
      README.md
      authority_stack.md
      master_build_sequence.md
      phases/
        01_ontology_and_structure.md
        02_core_pure_modules.md
        03_state_machine_and_hanus_shell.md
        04_ports.md
        05_domain_modules.md
        06_adapters.md
        07_tools.md
        08_sandboxes.md
        09_runtime_composition.md
        10_integration_testing.md
        11_cleanup_and_v1_retirement_review.md
      v1-migration/
        README.md
        hanus_interface_analysis.md
        mycite_v2_structure_report.md
        mycite2_migration_plan.md
        v1_audit_map.md
        v1_retention_vs_recreation.md
        source_authority_index.md
        recreation_sequence.md
        historical/
          1-Analysis.md
          2-Report.md
          3-Migration.md
  packages/
    core/
      datum_refs/
      identities/
      structures/samras/
      structures/hops/
      mss/
      mediation/
    state_machine/
      aitas/
      nimm/
      hanus_shell/
    modules/
      domains/contracts/
      domains/reference_exchange/
      domains/publication/
      services/local_audit/
      services/external_events/
      services/vault_session/
      services/sandboxes/
    ports/
      shell_surface/
      datum_store/
      payload_store/
      audit_log/
      event_log/
      resource_resolution/
      time_projection/
    adapters/
      filesystem/
      portal_runtime/
      external_services/
    tools/
      _shared/
  instances/
    README.md
    _shared/runtime/flavors/
    CVCC/
    FND/
    TFF/
  tests/
    README.md
    unit/
    contracts/
    adapters/
    tools/
    sandboxes/
    integration/
    architecture/
```
- Every layer root and every predeclared module dir gets `README.md` and `module_contract.md`.
- Every layer root gets `allowed_dependencies.md`, `forbidden_dependencies.md`, `testing_strategy.md`, and `phase_plan.md`.
- Only importable directories get `__init__.py`, and those files stay empty or docstring-only. No `model.py`, `operations.py`, `ports.py`, runtime code, or v1 re-exports are created in this pass.

#### Documentation Content
- `README.md` becomes the start-here surface: what v2 is, what it is not, authority order, anti-goals, repo navigation, build order, and “do not implement from v1 structure”.
- Ontology docs define the non-negotiables: pure domain inwardness, shell-defined tool attachment, pure and serializable navigation state, explicit datum authority, derived-artifact status of payloads and caches, sandboxes as orchestration, host composition only, and no outward imports.
- `interface_surfaces.md`, `tool_structure.md`, and `service_structure.md` explicitly separate shell surfaces, mediation surfaces, service seams, ports, adapters, tools, sandboxes, widgets, domain APIs, and runtime routes.
- `master_build_sequence.md` and the 11 phase docs lock the development order, phase gates, required docs, forbidden shortcuts, and required tests for each phase.
- `v1_audit_map.md`, `v1_retention_vs_recreation.md`, `source_authority_index.md`, and `recreation_sequence.md` map v1 paths to v2 concepts, classify each area as recreate/split/discard/history, and assign recreation order from evidence. They must explicitly cover `mycite_core/`, `packages/tools/`, `packages/hosts/`, `instances/_shared/`, runtime host, state machine, datum references, contracts, reference exchange, external events, local audit, and time/HOPS handling.
- The three existing numbered migration docs are demoted into `historical/`; the named versions become canonical and cross-link back to the root sources [tool_dev.md](/srv/repo/mycite-core/docs/plans/tool_dev.md), [hanus_interface_model.md](/srv/repo/mycite-core/docs/plans/hanus_interface_model.md), [tool_alignment.md](/srv/repo/mycite-core/docs/plans/tool_alignment.md), plus the current synthesis drafts [1-Analysis.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/v1-migration/1-Analysis.md), [2-Report.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/v1-migration/2-Report.md), and [3-Migration.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/v1-migration/3-Migration.md).

#### Interfaces And Phase Outputs
- New authoritative interfaces are documentary, not executable: the authority stack, module contract template, ADR set, package boundary docs, and phase-gated build sequence.
- No runtime or API behavior changes happen in this task. The only filesystem mutations in implementation will be directories, Markdown docs, empty `__init__.py`, and removal of placeholder `.gitkeep` files that become redundant.
- The “next best tasks” are documented, not implemented: phase 2 pure core recreation, phase 3 Hanus/AITAS/NIMM state machine recreation, phase 4 port contracts, phase 5 domain/service modules, phase 6 adapters, phase 7 tools, phase 8 sandboxes, phase 9 runtime composition, phase 10 integration/boundary tests, and phase 11 v1 retirement review.

#### Verification And Defaults
- Acceptance checks for this scaffold are structural: every declared directory exists, every major root explains purpose, contents, forbidden contents, dependencies, tests, and sources, every phase has entry criteria and gates, every required doc cross-links the root `docs/plans/` sources and the v2 migration sources, and there is no functional code in `MyCiteV2/` beyond inert package markers.
- Default choices: keep `CVCC`, `FND`, and `TFF` as declared instance placeholders; keep `docs/wiki/` only as explicitly non-authoritative scratch space; keep `docs/audits/` for evidence only; do not predeclare tool-specific packages beyond `tools/_shared/`; do not predeclare hosted or progeny modules until a later ADR promotes them.
- Explicit future decisions to record, not infer: whether hosted and progeny become first-class v2 domains, whether audit and external event services later merge under one event model, how coarse or fine the first port set should be in phase 4, and the exact initial tool set after the shell, state, and port layers are stable.


---


## PROMPT 1
You are working inside the `mycite-core` repository.

Your task is not to implement MyCiteV2 application code yet.

Your task is to make `MyCiteV2/` become a self-defining, low-drift, agent-legible program space that can guide future agents to build MyCite version 2 correctly from scratch, while being informed by the existing MyCite-v1 code and planning documents.

You must optimize for:
- ontological organization
- explicit dependency direction
- prevention of drift across multiple future agents
- externalized reasoning and decision surfaces
- clean recreation of modules later, not premature implementation now

The output of this task should be:
1. a precise directory structure for `MyCiteV2/`
2. placeholder files and placeholder directories where needed
3. authoritative planning and guidance documents inside `MyCiteV2/docs/plans/`
4. module-boundary documents that define what each module may and may not do
5. migration-oriented task docs that tell future agents what to recreate, from where, and in what order
6. decision records and invariant files that prevent later confusion
7. explicit references to both:
   - `mycite-core/docs/plans/`
   - `mycite-core/MyCiteV2/docs/plans/v1-migration/`
   wherever relevant

Do not implement clean module code yet except for minimal empty package scaffolds, `__init__.py` files, README stubs, and similarly inert structural files needed to define the space.

Do not silently infer architecture from convenience.
Do not collapse phases.
Do not create “working” code that bypasses the planning and ontology.
Do not import v1 code into v2.
Do not create compatibility shims unless a planning document explicitly calls for one.
Do not leave future agents to infer module purpose from filenames alone.

Your job is to plan the planning environment so well that later agents can proceed without prior context.

==================================================
PRIMARY SOURCES TO DRAW FROM
==================================================

Treat the following as the main decision sources, in this priority order:

1. `mycite-core/docs/plans/tool_dev.md`
2. `mycite-core/docs/plans/hanus_interface_model.md`
3. `mycite-core/docs/plans/tool_alignment.md`
4. all relevant files under `mycite-core/docs/plans/`
5. all relevant files under `mycite-core/MyCiteV2/docs/plans/v1-migration/`
6. the existing v1 code only as an implementation-history and audit source
7. the documents:
   - `hanus_interface_analysis.md`
   - `mycite_v2_structure_report.md`
   - `mycite2_migration_plan.md`

Assume these three documents exist inside the new repo context and should be referenced as authoritative synthesis documents.

Use the v1 repo to understand:
- what exists
- what drift occurred
- what boundaries were previously mixed
- what must be separated in v2

Do not use v1 structure as a template to copy directly.
Use it as audit evidence only.

==================================================
CORE DEVELOPMENT PRINCIPLES YOU MUST EXTERNALIZE
==================================================

You must explicitly externalize the following concepts into the MyCiteV2 docs and structure.

A. Structural Invariants
Create documentation that defines non-negotiable truths such as:
- domain logic must not depend on runtime adapters
- tools must attach only through shell-defined interface surfaces
- navigation state must be pure and serializable
- datum authority must be explicit and fail-closed
- payload binaries and caches are derived artifacts, never source truth
- sandboxes orchestrate mediation, not domain semantics
- hosts compose modules; they do not own domain logic
- no module may import “outward” across dependency layers
- v2 documentation is authoritative for v2, not scattered prompts

B. Layered Dependency Direction
Create docs that define inward dependency flow such as:
- core
- state/navigation
- domain modules
- ports
- adapters
- tools
- hosts/runtime composition

Make explicit:
- what each layer may import
- what it may not import
- what kinds of files belong there
- what kinds of files are forbidden there

C. Progressive Solidification Development
Create docs that force future implementation to happen in ordered phases, such as:
1. ontology and structure
2. core pure modules
3. state machine and Hanus shell model
4. ports
5. domain modules
6. adapters
7. tools
8. sandboxes
9. runtime composition
10. integration testing
11. cleanup and v1 retirement review

For each phase, define:
- purpose
- entry criteria
- outputs
- forbidden shortcuts
- required tests
- docs to consult
- docs to update

D. Interface Surfaces
Externalize what “surface” means in v2:
- shell surface
- tool surface
- mediation surface
- service seam
- port interface
- sandbox boundary

Future agents must not confuse:
- UI widgets
- application state surfaces
- service interfaces
- domain APIs
- runtime routes

E. Tool Structure
Define exactly how tools are to be understood in v2:
- what a tool is
- what a tool is not
- what belongs in `packages/tools/`
- what belongs in a sandbox
- what belongs in ports/adapters instead of a tool
- how a tool declares capabilities
- how a tool consumes shell context
- how a tool must avoid inventing its own shell model

F. Service Structure
Define exactly how services are to be understood in v2:
- service modules vs domain modules
- pure service contracts vs runtime service adapters
- when a capability is a tool
- when it is a host adapter
- when it is a core module concern
- when it is a sandbox concern

==================================================
DIRECTORY AND DOCUMENTATION TASK
==================================================

Create and/or populate the `MyCiteV2/` tree so it becomes self-describing.

You must create a precise, coherent scaffold, including at minimum the following kinds of locations if they do not already exist:

- `MyCiteV2/README.md`
- `MyCiteV2/docs/`
- `MyCiteV2/docs/plans/`
- `MyCiteV2/docs/plans/v1-migration/`
- `MyCiteV2/docs/ontology/`
- `MyCiteV2/docs/contracts/`
- `MyCiteV2/docs/decisions/`
- `MyCiteV2/docs/testing/`
- `MyCiteV2/docs/glossary/`
- `MyCiteV2/packages/`
- `MyCiteV2/packages/core/`
- `MyCiteV2/packages/modules/`
- `MyCiteV2/packages/state_machine/`
- `MyCiteV2/packages/ports/`
- `MyCiteV2/packages/adapters/`
- `MyCiteV2/packages/tools/`
- `MyCiteV2/instances/`
- `MyCiteV2/instances/_shared/`
- `MyCiteV2/tests/`

Also create empty package scaffolds and README files wherever useful so future agents do not have to infer intent.

Where appropriate, create:
- `__init__.py`
- `README.md`
- `module_contract.md`
- `phase_plan.md`
- `allowed_dependencies.md`
- `forbidden_dependencies.md`
- `testing_strategy.md`
- `decision_record_*.md`

The point is not volume.
The point is complete legibility and low ambiguity.

==================================================
REQUIRED DOCUMENT SET
==================================================

Create a coherent document set inside `MyCiteV2/` that includes, at minimum, documents covering the following:

1. `MyCiteV2/README.md`
A top-level statement of what v2 is, what it is not, why it exists, and how future agents should navigate the repo.

2. `MyCiteV2/docs/ontology/structural_invariants.md`
State the architectural invariants.

3. `MyCiteV2/docs/ontology/dependency_direction.md`
Define allowed dependency flow.

4. `MyCiteV2/docs/ontology/interface_surfaces.md`
Define shell surfaces, mediation surfaces, service seams, ports, adapters, and tool attachment rules.

5. `MyCiteV2/docs/ontology/progressive_solidification.md`
Define the ordered implementation phases and why order matters.

6. `MyCiteV2/docs/glossary/ontology_terms.md`
Define terms such as:
- shell
- tool
- module
- service
- port
- adapter
- sandbox
- mediation
- attention
- intention
- AITAS
- Hanus interface surface
- HOPS
- datum authority
- derived artifact
- runtime composition

7. `MyCiteV2/docs/plans/master_build_sequence.md`
The master ordered roadmap for building v2 from scratch.

8. `MyCiteV2/docs/plans/v1-migration/v1_audit_map.md`
Map v1 locations to v2 conceptual destinations.
This is not a copy plan.
It is a conceptual relocation map.

9. `MyCiteV2/docs/plans/v1-migration/v1_retention_vs_recreation.md`
For each major v1 area, determine:
- retain as concept only
- recreate from scratch
- split apart before recreation
- discard
- treat as historical evidence only

10. `MyCiteV2/docs/plans/v1-migration/source_authority_index.md`
List which v1 files are authoritative for which subjects.

11. `MyCiteV2/docs/contracts/module_contract_template.md`
A reusable module contract template for future modules.

12. `MyCiteV2/docs/testing/testing_philosophy.md`
Describe the testing loops:
- pure unit loop
- contract loop
- adapter loop
- tool loop
- sandbox loop
- integration loop
- architecture boundary loop

13. `MyCiteV2/docs/testing/phase_gates.md`
Define what must be true before the next phase can begin.

14. `MyCiteV2/docs/decisions/`
Seed this directory with initial ADR-style decision records for major choices such as:
- no direct reuse of v1 package structure
- ports/adapters dependency direction
- tools attach through shell surfaces
- state machine purity
- sandboxes as orchestration only
- hosts do not own domain logic

15. package-level README and contract files
For each major v2 package root, create documentation describing:
- purpose
- contents
- forbidden contents
- dependency rules
- expected test scope
- source docs to consult

==================================================
HOW TO USE V1 AS AN AUDIT SOURCE
==================================================

Audit the current v1 repo and use it to inform the docs.

You must inspect and synthesize from the existing v1 structure, especially areas such as:
- `mycite_core/`
- `packages/`
- `packages/tools/`
- `packages/hosts/`
- `instances/_shared/`
- runtime host logic
- state machine logic
- datum references
- contract-related modules
- reference exchange modules
- external event logic
- local audit logic
- any modularity docs

For each significant area, determine:
- what ontological category it belongs to in v2
- what was mixed incorrectly in v1
- what must be separated in v2
- whether the v1 code is evidence, a warning, or a source concept

Write those findings into the migration docs.

==================================================
AGENT-PRIMING GOAL
==================================================

The main objective is to make `MyCiteV2/` act as an externalized priming surface for future agents.

That means future agents should be able to answer all of these questions by reading the repo itself:

- What is v2 trying to become?
- What must not be repeated from v1?
- What is the correct build order?
- Which docs are authoritative?
- What belongs in core?
- What belongs in modules?
- What belongs in tools?
- What belongs in adapters?
- What is a sandbox?
- What is a shell surface?
- What is the role of Hanus?
- How should AITAS be treated?
- How should HOPS/calendar concepts be treated?
- What tests must exist before implementation can advance?
- What is forbidden even if it seems convenient?
- Which v1 files are historical reference only?

If a future agent would still need unstated architectural context after your work, the task is incomplete.

==================================================
WORKING METHOD
==================================================

Follow this order:

1. Audit the relevant v1 docs and code.
2. Extract architectural lessons and drift patterns.
3. Define the ontology and invariant set for v2.
4. Design the v2 directory structure.
5. Create the directories and empty scaffolds.
6. Write the authoritative docs.
7. Cross-link the docs to each other.
8. Make sure each major package root explains itself.
9. Make sure the build phases are ordered and gated.
10. Make sure later agents can act without prior chat context.

==================================================
OUTPUT REQUIREMENTS
==================================================

- Create the directories and files.
- Populate the documentation with real, precise content.
- Keep content concrete and operational.
- Reference source files explicitly.
- Prefer strong statements over vague intentions.
- Use checklists where they reduce ambiguity.
- Use tables only if truly useful.
- Do not write filler.
- Do not implement application logic beyond inert scaffolding.
- Do not stop at a single summary file.
- The repo itself must become the roadmap.

At the end, provide:
1. a concise summary of what was created
2. the key authoritative files
3. any unresolved ambiguities requiring future explicit decisions
4. a list of the next best implementation-phase tasks, but only as docs, not code implementation

Proceed carefully and exhaustively.

---

## AGENT PLAN 1

### Summary
- Convert the current `MyCiteV2/` skeleton into a documentation-first, inert scaffold that makes v2 architecture, authority order, dependency direction, phase order, and v1 drift explicit.
- Treat v1 as audit evidence only. Encode current drift examples from [aitas.py](/srv/repo/mycite-core/mycite_core/state_machine/aitas.py), [imported_refs.py](/srv/repo/mycite-core/mycite_core/reference_exchange/imported_refs.py), [context.py](/srv/repo/mycite-core/mycite_core/contract_line/context.py), [alias_service.py](/srv/repo/mycite-core/mycite_core/contract_line/alias_service.py), [service_tools.py](/srv/repo/mycite-core/instances/_shared/portal/application/service_tools.py), and [time_address_schema.py](/srv/repo/mycite-core/instances/_shared/portal/application/time_address_schema.py) into migration docs and ADRs.
- Make [tool_dev.md](/srv/repo/mycite-core/docs/plans/tool_dev.md), [hanus_interface_model.md](/srv/repo/mycite-core/docs/plans/hanus_interface_model.md), [tool_alignment.md](/srv/repo/mycite-core/docs/plans/tool_alignment.md), plus named synthesis docs inside `MyCiteV2/docs/plans/v1-migration/` the top authority chain.

### Planned Structure
- Create this stable tree:
```text
MyCiteV2/
  README.md
  docs/
    README.md
    audits/README.md
    wiki/README.md
    ontology/
      structural_invariants.md
      dependency_direction.md
      interface_surfaces.md
      progressive_solidification.md
      tool_structure.md
      service_structure.md
    glossary/
      ontology_terms.md
    contracts/
      README.md
      module_contract_template.md
    testing/
      testing_philosophy.md
      phase_gates.md
    decisions/
      README.md
      decision_record_0001_v2_docs_are_authoritative.md
      decision_record_0002_no_direct_reuse_of_v1_package_structure.md
      decision_record_0003_dependency_direction_ports_and_adapters.md
      decision_record_0004_tools_attach_through_shell_surfaces.md
      decision_record_0005_state_machine_purity_and_serializability.md
      decision_record_0006_sandboxes_orchestrate_not_semantics.md
      decision_record_0007_hosts_compose_do_not_own_domain_logic.md
      decision_record_0008_payloads_and_caches_are_derived.md
    plans/
      README.md
      authority_stack.md
      master_build_sequence.md
      phases/
        01_ontology_and_structure.md
        02_core_pure_modules.md
        03_state_machine_and_hanus_shell.md
        04_ports.md
        05_domain_modules.md
        06_adapters.md
        07_tools.md
        08_sandboxes.md
        09_runtime_composition.md
        10_integration_testing.md
        11_cleanup_and_v1_retirement_review.md
      v1-migration/
        README.md
        hanus_interface_analysis.md
        mycite_v2_structure_report.md
        mycite2_migration_plan.md
        v1_audit_map.md
        v1_retention_vs_recreation.md
        source_authority_index.md
        recreation_sequence.md
        historical/
          1-Analysis.md
          2-Report.md
          3-Migration.md
  packages/
    core/
      datum_refs/
      identities/
      structures/samras/
      structures/hops/
      mss/
      mediation/
    state_machine/
      aitas/
      nimm/
      hanus_shell/
    modules/
      domains/contracts/
      domains/reference_exchange/
      domains/publication/
      services/local_audit/
      services/external_events/
      services/vault_session/
      services/sandboxes/
    ports/
      shell_surface/
      datum_store/
      payload_store/
      audit_log/
      event_log/
      resource_resolution/
      time_projection/
    adapters/
      filesystem/
      portal_runtime/
      external_services/
    tools/
      _shared/
  instances/
    README.md
    _shared/runtime/flavors/
    CVCC/
    FND/
    TFF/
  tests/
    README.md
    unit/
    contracts/
    adapters/
    tools/
    sandboxes/
    integration/
    architecture/
```
- Every layer root and every predeclared module dir gets `README.md` and `module_contract.md`.
- Every layer root gets `allowed_dependencies.md`, `forbidden_dependencies.md`, `testing_strategy.md`, and `phase_plan.md`.
- Only importable directories get `__init__.py`, and those files stay empty or docstring-only. No `model.py`, `operations.py`, `ports.py`, runtime code, or v1 re-exports are created in this pass.

### Documentation Content
- `README.md` becomes the start-here surface: what v2 is, what it is not, authority order, anti-goals, repo navigation, build order, and “do not implement from v1 structure”.
- Ontology docs define the non-negotiables: pure domain inwardness, shell-defined tool attachment, pure and serializable navigation state, explicit datum authority, derived-artifact status of payloads and caches, sandboxes as orchestration, host composition only, and no outward imports.
- `interface_surfaces.md`, `tool_structure.md`, and `service_structure.md` explicitly separate shell surfaces, mediation surfaces, service seams, ports, adapters, tools, sandboxes, widgets, domain APIs, and runtime routes.
- `master_build_sequence.md` and the 11 phase docs lock the development order, phase gates, required docs, forbidden shortcuts, and required tests for each phase.
- `v1_audit_map.md`, `v1_retention_vs_recreation.md`, `source_authority_index.md`, and `recreation_sequence.md` map v1 paths to v2 concepts, classify each area as recreate/split/discard/history, and assign recreation order from evidence. They must explicitly cover `mycite_core/`, `packages/tools/`, `packages/hosts/`, `instances/_shared/`, runtime host, state machine, datum references, contracts, reference exchange, external events, local audit, and time/HOPS handling.
- The three existing numbered migration docs are demoted into `historical/`; the named versions become canonical and cross-link back to the root sources [tool_dev.md](/srv/repo/mycite-core/docs/plans/tool_dev.md), [hanus_interface_model.md](/srv/repo/mycite-core/docs/plans/hanus_interface_model.md), [tool_alignment.md](/srv/repo/mycite-core/docs/plans/tool_alignment.md), plus the current synthesis drafts [1-Analysis.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/v1-migration/1-Analysis.md), [2-Report.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/v1-migration/2-Report.md), and [3-Migration.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/v1-migration/3-Migration.md).

### Interfaces And Phase Outputs
- New authoritative interfaces are documentary, not executable: the authority stack, module contract template, ADR set, package boundary docs, and phase-gated build sequence.
- No runtime or API behavior changes happen in this task. The only filesystem mutations in implementation will be directories, Markdown docs, empty `__init__.py`, and removal of placeholder `.gitkeep` files that become redundant.
- The “next best tasks” are documented, not implemented: phase 2 pure core recreation, phase 3 Hanus/AITAS/NIMM state machine recreation, phase 4 port contracts, phase 5 domain/service modules, phase 6 adapters, phase 7 tools, phase 8 sandboxes, phase 9 runtime composition, phase 10 integration/boundary tests, and phase 11 v1 retirement review.

### Verification And Defaults
- Acceptance checks for this scaffold are structural: every declared directory exists, every major root explains purpose, contents, forbidden contents, dependencies, tests, and sources, every phase has entry criteria and gates, every required doc cross-links the root `docs/plans/` sources and the v2 migration sources, and there is no functional code in `MyCiteV2/` beyond inert package markers.
- Default choices: keep `CVCC`, `FND`, and `TFF` as declared instance placeholders; keep `docs/wiki/` only as explicitly non-authoritative scratch space; keep `docs/audits/` for evidence only; do not predeclare tool-specific packages beyond `tools/_shared/`; do not predeclare hosted or progeny modules until a later ADR promotes them.
- Explicit future decisions to record, not infer: whether hosted and progeny become first-class v2 domains, whether audit and external event services later merge under one event model, how coarse or fine the first port set should be in phase 4, and the exact initial tool set after the shell, state, and port layers are stable.



---


## CORECTION PROMPT 2

The plan is strong. It is correctly biased toward documentation-first structure, explicit authority, and inert scaffolding rather than premature implementation. The main issue is that some of the proposed v2 package names still carry v1 ambiguity.

Tighten the ontology around three words in particular: 'service', 'mediation', and 'sandbox'.
E.g. `packages/modules/services/` is too loose. The goal is ontological clarity, so “services” should not sit beside domains unless the word is defined very narrowly. In practice, `local_audit`, `external_events`, and especially `vault_session` are not the same kind of thing. `vault_session` sounds runtime- or adapter-bound, while `external_events` may be a domain concern or a cross-domain event substrate. Addressing this will prevent leaving `services/` too broad that otherwise may allow future agents to dump mixed concerns into it.

`packages/core/mediation/` is also risky. Mediation is not obviously “core” in the same sense as datum refs, identities, HOPS, or MSS. In the clear ontology, mediation is closer to shell/interface surface behavior than pure core logic. If left there, agents may place UI-state-bearing logic into core.

`packages/modules/services/sandboxes/` is ontologically off. Sandboxes are not just services. In the present framing they are orchestration boundaries. They deserve their own top-level conceptual location, or at minimum a contract doc explaining why they are nested there.

`instances/CVCC`, `instances/FND`, and `instances/TFF` as placeholders may also cause drift. That layout can imply that v2 is still instance-led rather than architecture-led. They have been removed to prevent confusion.

There is also one major omission: the scaffold should include architecture-enforcement docs, not just architecture-description docs. You need at least these additional files or equivalent content:
* `docs/testing/architecture_boundary_checks.md`
* `docs/contracts/import_rules.md`
* `docs/ontology/non_authoritative_zones.md`
* `docs/plans/phase_completion_definition.md`

The plan also needs a stronger naming normalization layer. Right now there are several naming systems in play: MyCite-v1, MyCiteV2, MyCite2, Hanus, AITAS, NIMM, shell surface, service seam, module, service, sandbox. You already included a glossary, which is correct, but you should explicitly require that every package root and phase plan use glossary-defined terms only. Otherwise future docs will reintroduce synonym drift.

The other needed tightening is source precedence. The plan says to reference both `mycite-core/docs/plans/` and `mycite-core/MyCiteV2/docs/plans/v1-migration/`, which is correct, but it should force a precedence order among:
1. v2 structural invariants
2. v2 ADRs
3. v2 phase docs
4. v2 migration docs
5. v1 plan docs
6. v1 code as evidence only

That precedence needs to be written once, clearly, and linked everywhere.

### 1.) Replace broad ambiguous folders with clearer ontology:
* `packages/modules/domains/`
* `packages/modules/cross_domain/`
* `packages/sandboxes/`
* `packages/state_machine/`
* `packages/ports/`
* `packages/adapters/`
* `packages/tools/`

### 2.) Require every major root to contain exactly these five documents:
* `README.md`
* `module_contract.md`
* `allowed_dependencies.md`
* `forbidden_dependencies.md`
* `testing_strategy.md`

### 3. Require every phase doc to include the same fixed sections:
* purpose
* source authorities
* inputs
* outputs
* prohibited shortcuts
* required tests
* completion gate
* follow-on phase dependencies

### 4. Add one file whose entire purpose is to stop future agents from “helpfully” implementing code too early:
* `docs/plans/implementation_prohibition_for_scaffold_phase.md`

### 5. Add a specific v1 drift ledger:
* mixed runtime/domain imports
* mixed shell/tool ownership
* mixed service/domain naming
* mixed authority between datum, utility JSON, and derived payloads
* instance-path assumptions embedded in reusable logic
> That should be a named file, not just buried in migration prose.

And add explicit enforcement docs for:
* import boundaries
* non-authoritative zones
* phase completion gates

---


## PLAN 2


# MyCiteV2 Ontology-First Scaffold, Revised

## Summary
- Rebuild `MyCiteV2/` as an architecture-led, documentation-first scaffold with inert package markers only.
- Remove ambiguous bucket names. `service` is not used as a catch-all package category. `mediation` is treated as shell/state-surface behavior, not core. `sandboxes` become their own top-level conceptual package.
- Keep v1 as audit evidence only. The scaffold must explain what to recreate, what to split, what to discard, and what must never be inferred from v1 layout.

## Authority And Vocabulary
- Create `MyCiteV2/docs/plans/authority_stack.md` and make it the single precedence source, linked from the top-level README, every phase doc, every major-root `README.md`, `docs/contracts/module_contract_template.md`, and `docs/plans/v1-migration/README.md`.
- The precedence order is fixed:
  1. `docs/ontology/structural_invariants.md`
  2. `docs/decisions/*.md`
  3. `docs/plans/phases/*.md` and `docs/plans/phase_completion_definition.md`
  4. `docs/plans/v1-migration/*.md`
  5. `../docs/plans/*.md` from v1
  6. v1 code as implementation-history evidence only
- Add `docs/contracts/terminology_usage_rules.md` plus `docs/glossary/ontology_terms.md`.
- Require every package-root README, every module contract, and every phase doc to use glossary-defined terms only. Synonyms like “MyCite2”, “service layer”, “tool shell”, or “runtime service” are forbidden unless explicitly normalized in the glossary.

## Planned Structure
```text
MyCiteV2/
  README.md
  docs/
    README.md
    audits/README.md
    wiki/README.md
    ontology/
      structural_invariants.md
      dependency_direction.md
      interface_surfaces.md
      progressive_solidification.md
      non_authoritative_zones.md
    glossary/
      ontology_terms.md
    contracts/
      README.md
      module_contract_template.md
      import_rules.md
      terminology_usage_rules.md
    testing/
      testing_philosophy.md
      phase_gates.md
      architecture_boundary_checks.md
    decisions/
      README.md
      decision_record_0001_v2_docs_are_authoritative.md
      decision_record_0002_no_direct_reuse_of_v1_package_structure.md
      decision_record_0003_dependency_direction_ports_and_adapters.md
      decision_record_0004_tools_attach_through_shell_surfaces.md
      decision_record_0005_state_machine_purity_and_serializability.md
      decision_record_0006_sandboxes_are_orchestration_boundaries.md
      decision_record_0007_hosts_compose_but_do_not_own_domain_logic.md
      decision_record_0008_payloads_and_caches_are_derived.md
    plans/
      README.md
      authority_stack.md
      master_build_sequence.md
      phase_completion_definition.md
      implementation_prohibition_for_scaffold_phase.md
      phases/
        01_ontology_and_structure.md
        02_core_pure_modules.md
        03_state_machine_and_hanus_shell.md
        04_ports.md
        05_domain_and_cross_domain_modules.md
        06_adapters.md
        07_tools.md
        08_sandboxes.md
        09_runtime_composition.md
        10_integration_testing.md
        11_cleanup_and_v1_retirement_review.md
      v1-migration/
        README.md
        hanus_interface_analysis.md
        mycite_v2_structure_report.md
        mycite2_migration_plan.md
        v1_audit_map.md
        v1_retention_vs_recreation.md
        source_authority_index.md
        v1_drift_ledger.md
        recreation_sequence.md
        historical/
          1-Analysis.md
          2-Report.md
          3-Migration.md
  packages/
    core/
      datum_refs/
      identities/
      structures/samras/
      structures/hops/
      mss/
      crypto/
    modules/
      domains/
        contracts/
        publication/
        reference_exchange/
      cross_domain/
        external_events/
        local_audit/
    state_machine/
      aitas/
      nimm/
      hanus_shell/
      mediation_surface/
    sandboxes/
      tool/
      system/
      orchestration/
    ports/
      datum_store/
      payload_store/
      audit_log/
      event_log/
      resource_resolution/
      session_keys/
      time_projection/
      shell_surface/
    adapters/
      filesystem/
      event_transport/
      session_vault/
      portal_runtime/
    tools/
      _shared/
  instances/
    _shared/
      runtime/
        flavors/
  tests/
    unit/
    contracts/
    adapters/
    tools/
    sandboxes/
    integration/
    architecture/
```
- Do not create `instances/CVCC`, `instances/FND`, or `instances/TFF`.
- Do not create any broad `services/` package.
- Do not create `packages/core/mediation/`.
- Do not create `vault_session/` as a v2 module root. Its v1 concerns are explicitly split across `packages/core/crypto/`, `packages/ports/session_keys/`, and `packages/adapters/session_vault/`.

## Major-Root Contract
- Every major root must contain exactly these five documents and no extra local prose files:
  - `README.md`
  - `module_contract.md`
  - `allowed_dependencies.md`
  - `forbidden_dependencies.md`
  - `testing_strategy.md`
- Apply that rule to:
  - `packages/core/`
  - `packages/modules/`
  - `packages/modules/domains/`
  - `packages/modules/cross_domain/`
  - `packages/state_machine/`
  - `packages/sandboxes/`
  - `packages/ports/`
  - `packages/adapters/`
  - `packages/tools/`
  - `instances/`
  - `instances/_shared/`
  - `tests/`
- Subdirectories created only as future package placeholders get inert `README.md` plus empty `__init__.py` only where importable.

## Required Docs And Enforcement Content
- `docs/ontology/non_authoritative_zones.md` defines zones that must never become v2 truth: `docs/wiki/`, `docs/audits/`, legacy prompts, v1 code, runtime state, utility JSON when datum authority exists, payload binaries, caches, and host wrappers.
- `docs/contracts/import_rules.md` defines allowed import direction and the exact forbidden patterns to check for.
- `docs/testing/architecture_boundary_checks.md` defines static checks for layer imports, shell/tool ownership, datum-authority misuse, instance-path leakage, and derived-artifact writes.
- `docs/plans/phase_completion_definition.md` defines what “phase complete” means and ties directly to `docs/testing/phase_gates.md`.
- `docs/plans/implementation_prohibition_for_scaffold_phase.md` explicitly forbids helpful early implementation during the scaffold phase.
- `docs/plans/v1-migration/v1_drift_ledger.md` is a named ledger covering:
  - mixed runtime/domain imports
  - mixed shell/tool ownership
  - mixed service/domain naming
  - mixed datum vs utility JSON vs derived payload authority
  - instance-path assumptions embedded in reusable logic

## Phase Doc Standard
- Every phase doc under `docs/plans/phases/` must use the same fixed sections in this exact order:
  - purpose
  - source authorities
  - inputs
  - outputs
  - prohibited shortcuts
  - required tests
  - completion gate
  - follow-on phase dependencies

## Migration Decisions To Encode
- `external_events` is treated as a cross-domain module, not core and not adapter code.
- `local_audit` is treated as a cross-domain module, not generic utility.
- `vault_session` is treated as a split concern and must not be recreated as one v2 module.
- `mediation_surface` belongs under `packages/state_machine/` because it is a serialized shell/interface-state concern.
- `sandboxes` are orchestration boundaries and get their own top-level package with explicit contracts stating they do not own domain semantics.

## Acceptance Criteria
- The scaffold is complete only when the repo itself answers authority order, allowed names, non-authoritative zones, build order, import boundaries, drift history, and prohibited shortcuts without prior chat context.
- No functional application code is added beyond inert directory markers, empty `__init__.py`, and structural docs.
- The existing numbered migration docs are preserved but demoted into `historical/`; the named v2 migration docs become authoritative.


---



## OUTPUT


Implemented the ontology-first scaffold under [MyCiteV2](/srv/repo/mycite-core/MyCiteV2) with inert package markers only. The tree now has the full authority/ontology/contracts/testing/plans set, the major-root five-document contract on every required root, the renamed v2 module layout, and the old numbered migration drafts preserved under [historical](/srv/repo/mycite-core/MyCiteV2/docs/plans/v1-migration/historical). No application logic was added.

The main authority files are [README.md](/srv/repo/mycite-core/MyCiteV2/README.md), [authority_stack.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/authority_stack.md), [structural_invariants.md](/srv/repo/mycite-core/MyCiteV2/docs/ontology/structural_invariants.md), [import_rules.md](/srv/repo/mycite-core/MyCiteV2/docs/contracts/import_rules.md), [architecture_boundary_checks.md](/srv/repo/mycite-core/MyCiteV2/docs/testing/architecture_boundary_checks.md), [master_build_sequence.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/master_build_sequence.md), [implementation_prohibition_for_scaffold_phase.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/implementation_prohibition_for_scaffold_phase.md), and [v1_drift_ledger.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/v1-migration/v1_drift_ledger.md).

Unresolved decisions that still need explicit future choice are:
- whether hosted/progeny becomes a first-class domain in v2 or stays split across later modules
- the exact granularity of early ports around resource resolution, session keys, and shell-facing seams
- whether `external_events` and `local_audit` remain separate cross-domain modules long-term
- which concrete tools, beyond `_shared`, get first phase-7 implementation priority

Next best implementation-phase tasks, as already documented rather than coded, are:
- phase 02 in [02_core_pure_modules.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/phases/02_core_pure_modules.md)
- phase 03 in [03_state_machine_and_hanus_shell.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/phases/03_state_machine_and_hanus_shell.md)
- phase 04 in [04_ports.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/phases/04_ports.md)
- phase 05 in [05_domain_and_cross_domain_modules.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/phases/05_domain_and_cross_domain_modules.md)

Verification: I ran structural checks confirming all 11 phase docs use the fixed section schema, every required major root has exactly the five mandated docs, and the old instance placeholder directories are gone. I did not run application test suites because this change is documentation/scaffold only.


---
