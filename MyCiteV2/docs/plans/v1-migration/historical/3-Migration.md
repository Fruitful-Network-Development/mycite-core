# Comprehensive Audit and Migration Plan for MyCite‑v2
This document outlines a meticulous plan for auditing MyCite‑v1 (mycite-core) and creating MyCite‑v2 following the structural and ontological recommendations in hanus_interface_analysis.md and mycite_v2_structure_report.md. Each phase includes the rationale, targeted references to existing documentation or code in mycite-core, and the expected outcomes.
## 1 Audit Phase
### 1.1 Collect and Study Documentation
    1. Gather modularity documents. Review docs/modularity/module_inventory.md to understand the current allocation of responsibilities and transitional modules[1]. Study module_contracts.md to internalise what each module owns and must not own[2]. Note transitional wrappers under instances/_shared mentioned in the runtime alignment report[3].
    2. Review tool development plans. Read docs/plans/tool_dev.md and summarise the separation of tool code from state and the requirement that tools live under packages/tools and attach to portal surfaces without defining their own shell model[4]. Note design guidelines such as message representation and newsletter workflow corrections.
    3. Study the Hanus interface model. From docs/plans/hanus_interface_model.md, internalise the compound state model (focus, resolution, semantic filters) and the concept of a button shell that encapsulates navigation state and view functions[5]. Understand that the model allows addressing hierarchical structures even when datum files do not yet hold those nodes[6]. Note the proposal for a calendar tool using HOPS structures and treating time as space.
    4. Read HOPS and sandbox contracts. Consult docs/wiki/hops/homogeneous_ordinal_partition_structure.md to understand the time‑line partitioning system used by calendar datums. Review docs/wiki/architecture/sandboxes.md for responsibilities and dependencies of sandboxes[7].
### 1.2 Inspect Current Code Modules
    1. State machine. Audit mycite_core/state_machine modules. Identify pure functions (actions, reducer, state, view model, controls, document, tool_capabilities) and note dependencies on other modules[8][9]. Ensure these modules only depend on core utilities and not on portal‑specific code.
    2. Core utilities. Examine mycite_core/datum_refs.py for parsing and normalising datum references[10][11]. Check mycite_core/local_audit/store.py for audit logs[12] and mycite_core/external_events/store.py for event storage[13]. Identify these as pure operations suitable for relocation to packages/core.
    3. Domain‑specific modules. Inspect mycite_core/contract_line, mycite_core/reference_exchange (registry and imported_refs), and any other domain modules. Note cross‑dependencies on instances/_shared.portal (sandbox or data engine) in modules like reference_exchange/imported_refs.py[14]. Mark these couplings for decoupling via ports.
    4. Runtime host. Review mycite_core/runtime_host/instance_context.py, paths.py and state_roots.py to understand how file paths and instance contexts are computed. Determine which functions can remain as part of packages/adapters and which should be moved.
    5. MSS resolution. Investigate the large module mycite_core/mss_resolution/core.py. Determine how compile/resolve functions interact with contract modules and whether they should be broken into generic operations (for packages/core) and domain‑specific functions (for packages/modules/contracts).
    6. External events and feeds. Note that mycite_core/external_events/feed.py builds network message feeds and summarises events[15]. Decide where this logic belongs in the new repository (likely in a events module under packages/core).
### 1.3 Assess Tools and Hosts
    1. Tools. Inspect packages/tools to catalogue existing tools and ensure they follow guidelines: canonical code lives under packages/tools/<tool>; state lives outside the repo; tools attach to portal surfaces[4].
    2. Hosts. Confirm that packages/hosts/server_portal contains transitional Flask bootstrap code and route registration[16]. Check if there are any unimplemented desktop_app or cli packages. Plan to remove this directory in V2 and move host‑specific code under instances/_shared/runtime/flavours.
## 2 Design and Planning Phase
### 2.1 Define Ontological Categories
Use the categories identified in mycite_v2_structure_report.md: 1. Core operations – pure utility functions (datum_refs, audit, events, mss compilation). These modules have no external dependencies and can reside under packages/core. 2. State and navigation – the Hanus/AITAS state machine and button shell logic, to be placed in packages/state_machine. 3. Domain modules – packages for contracts, publications, reference exchange, etc., each with clearly defined models, operations and ports. 4. Ports and adapters – abstract interfaces for datastores, scheduling (HOPS), audit logging, etc., with host‑specific implementations under packages/adapters (server, desktop, CLI). 5. Tools – canonical tool code under packages/tools, defining tool capabilities for integration with the state machine. 6. Sandboxes – runtime contexts bridging UI state and data, dependent on state machine and ports, but free of domain semantics[7]. 7. Runtimes – host‑specific composition and bootstrap code, under instances/_shared/runtime/flavours. The packages/hosts directory will be deleted after migration.
### 2.2 Design the Repository Layout
Adopt the directory layout proposed in mycite_v2_structure_report.md (reproduced here for clarity):
mycite-v2/
├── packages/
│   ├── core/
│   │   ├── datum_refs/
│   │   ├── local_audit/
│   │   ├── external_events/
│   │   ├── mss_resolution/
│   │   └── ...
│   ├── modules/
│   │   ├── contracts/
│   │   ├── publications/
│   │   ├── reference_exchange/
│   │   └── ...
│   ├── state_machine/
│   ├── ports/
│   ├── adapters/
│   └── tools/
├── instances/
│   ├── _shared/
│   │   ├── runtime/
│   │   │   └── flavours/
│   │   ├── portal/api/
│   │   └── portal/ui/
│   └── <instance>/
├── data/
│   ├── sandbox/<tool>/
│   └── payloads/
└── docs/
This layout separates concerns: pure code vs. domain modules vs. ports vs. adapters vs. tools vs. runtime and data. It eliminates packages/hosts and mycite_core entirely, relocating all functionality into modules or adapters.
### 2.3 Define Migration Milestones
To avoid conflating multiple refactors, break the migration into milestones, each focusing on a core pillar:
    1. Module Skeletons – create the new directory structure with empty module files, README stubs and basic initialisation.
    2. Core Operations Migration – move datum_refs, local_audit, external_events, mss_resolution and other pure utilities to packages/core. Update imports accordingly in other modules.
    3. State Machine Migration – move mycite_core/state_machine into packages/state_machine. Remove dependencies on mycite_core.runtime_paths by injecting path functions via ports. Implement the Hanus button shell interface; update tests to verify state transitions and view models.
    4. Ports Definition – define abstract interfaces for data storage (datastore), scheduling (scheduler using HOPS), audit (audit), etc. Write unit tests that use mock implementations of these ports. Ensure domain modules rely only on ports.
    5. Domain Module Refactoring – for each domain (contracts, reference_exchange, etc.), create a module under packages/modules/<domain> with submodules model.py, operations.py and ports.py. Move pure business logic into operations.py; define data classes in model.py; define port interfaces and exceptions in ports.py. Replace direct calls to sandbox or portal services with injected port functions. For instance, in reference_exchange/imported_refs.py, remove imports of instances._shared.portal.data_engine and replace them with functions passed via a ResourceResolver port[14].
    6. Adapters Implementation – implement server‑specific adapters in packages/adapters/server to satisfy the port interfaces. These adapters will use filesystem paths, Flask contexts and other environment‑specific details. Implement desktop and CLI adapters as needed for cross‑platform support.
    7. Tool Migration – ensure each tool in packages/tools conforms to the new state machine and port definitions. Update capability definitions to match the Hanus model. Create new tools such as a calendar tool that uses the scheduler port and HOPS structures, enabling time‑as‑space navigation as proposed in hanus_interface_model.md.
    8. Sandbox Reconstruction – implement sandboxes under packages/modules/sandboxes (or integrate into each domain module) that manage staging, concurrency control and state bridging, while avoiding domain semantics[7]. Ensure sandboxes depend only on the state machine and ports.
    9. Runtime Composition – move host bootstrap and route registration code from packages/hosts/server_portal into instances/_shared/runtime/flavours/server. Use the new adapters to wire ports to domain modules. Create composition scripts for desktop and CLI as needed.
    10. Documentation Update – update docs/modularity to reflect the new ontology and module responsibilities. Provide migration guides in docs/plans detailing the reasoning behind each change and the benefits of the new structure. Include diagrams of the Hanus state machine and port architecture.
    11. Testing and Validation – for each milestone, develop unit tests and integration tests to ensure correctness. Use the scheduler port to test HOPS time navigation and the new calendar tool. Write end‑to‑end tests for contract creation, reference import, event logging and tool interactions. Confirm that the UI shell built on the new state machine can navigate hierarchical IDs and that the button shell responds correctly.
    12. Final Clean‑up – once all modules are migrated and tested, remove the mycite_core package and the packages/hosts directory. Ensure no leftover imports reference the old paths. Archive the V1 code for reference in the repository history.
## 3 Reasoning and Expected Outcomes
    • Decoupling and maintainability – By moving pure utilities into packages/core and domain logic into packages/modules, code becomes easier to understand, reuse and test. The current v1 code intermingles domain logic with portal services (e.g., reference_exchange/imported_refs.py uses portal’s data engine[14]); this coupling makes the system brittle. In V2, each domain module interacts with external systems through ports, improving maintainability.
    • Flexible UI state – The Hanus interface model decouples navigation state from rendering. By migrating the state machine into its own module and integrating Hanus button shell concepts, we can build a UI shell that can serve different tools (including the proposed calendar tool) and can treat hierarchical IDs uniformly[5]. This will allow advanced features like time‑as‑space navigation and dynamic network views.
    • Host independence – Ports and adapters ensure that domain logic is independent of specific runtime environments. This enables future expansion to desktop or CLI flavours without changing the core logic. Removing packages/hosts/server_portal and moving host code under instances/_shared/runtime/flavours reflects this design[16].
    • Tool modularity – Tools remain self‑contained packages with clear boundaries. Aligning them with the state machine and port interfaces ensures consistent integration and easier addition of new tools, such as the HOPS‑based calendar tool. The guidelines from tool_dev.md about separating tool code from state and messaging are preserved[4].
## 4 Conclusion
The migration from MyCite‑v1 to MyCite‑v2 is a substantial project requiring careful planning and staged refactoring. By auditing existing documentation and code, defining ontological categories, designing a new repository layout and executing well‑scoped milestones, we can build a more flexible, maintainable and extensible system. The Hanus interface model provides the conceptual foundation for the new UI and navigation state, while the introduction of ports and adapters ensures host independence. Each step must be supported by unit tests, integration tests and updated documentation to guarantee a smooth transition.

[1] module_inventory.md
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/modularity/module_inventory.md
[2] module_contracts.md
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/modularity/module_contracts.md
[3] runtime_alignment_report.md
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/modularity/runtime_alignment_report.md
[4] README.md
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/packages/tools/README.md
[5] [6] hanus_interface_model.md
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/plans/hanus_interface_model.md
[7] sandboxes.md
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/modularity/contracts/sandboxes.md
[8] view_model.py
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/mycite_core/state_machine/view_model.py
[9] controls.py
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/mycite_core/state_machine/controls.py
[10] [11] datum_refs.py
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/mycite_core/datum_refs.py
[12] store.py
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/mycite_core/local_audit/store.py
[13] store.py
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/mycite_core/external_events/store.py
[14] imported_refs.py
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/mycite_core/reference_exchange/imported_refs.py
[15] feed.py
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/mycite_core/external_events/feed.py
[16] README.md
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/packages/hosts/server_portal/README.md
