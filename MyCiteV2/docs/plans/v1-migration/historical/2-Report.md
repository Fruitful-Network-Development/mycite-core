Mycite‑v2 Structural Analysis and Proposed Ontology
## 1 Overview
The mycite‑core repository has evolved through several rounds of refactoring to separate tool logic from data state and to decouple UI shells from runtime hosts. The current state is transitional: domain logic still resides under mycite_core/, host‑specific bootstrap code is tucked under packages/hosts, and there is no packages/modules/ directory despite being mentioned in the modularity plan. To build mycite‑v2 we need a more explicit ontology that organizes code by operations, permissions, responsibilities, ports, packages, tools and sandboxes. This report analyses the existing repository and proposes a new structure aligning with the Hanus interface model and HOPS calendar structures.
## 2 Insights from Current Repository
### 2.1 Packages and Hosts
    • Packages/README.md states that mycite_core/ contains shared protocol/core logic; instances/_shared/ holds the shared server‑hosted runtime shell; packages/hosts/server_portal is host‑specific runtime packaging (with planned desktop_app and cli packages, which do not yet exist)[1]. The doc clarifies that host packaging is transitional—canonical runtime composition and API routes live under instances/_shared/runtime or instances/_shared/portal/api[1].
    • Packages/hosts/server_portal/README.md explains that this package currently owns Flask runtime/bootstrap, route registration, runtime composition and build helpers, but points out that canonical locations for these responsibilities are in instances/_shared/runtime and instances/_shared/portal/api[1]. This indicates the packages/hosts folder should be retired in favour of a dedicated runtime module under instances/_shared.
    • Packages/tools/README.md describes the rules for tool modules: canonical tool code lives under packages/tools; tool state is stored in instance-specific directories; tool datum anchors live in data/sandbox/<tool>; tools attach to portal surfaces and must not define their own shell model[2]. This emphasises that tools are pluggable units within the overall system.
### 2.2 State machine and Hanus model
    • The state machine in mycite_core/state_machine defines shell actions, a reducer, a view model and helper functions. It models user interaction via the AITAS (Attention, Intention, Archetype, Temporal, Spatial) context, uses hierarchical IDs to locate datum nodes and tool capabilities, and builds the view model for the UI shell[3][4].
    • The Hanus interface model document outlines a UI model in which navigation is decoupled from rendering: a compound state combines focus, resolution and semantic filters; UI buttons mutate this state; and a “link / button shell” encapsulates state transitions and view functions[5]. The model also proposes using NIMM (Non‑Interactive Mixed Model) directives for layer definitions, suggesting that data structures (such as a SAMRAS network) can be addressed even when not yet present in a datum file, because the structure is defined by the initial datum abstraction’s magnitude[6].
    • HOPS (Homogeneous Ordinal Partition Structure) is used for calendar datums; example usage in system/system_log.json shows how time lines are partitioned into ordinal segments. The Hanus document suggests building a dedicated calendar tool that treats time as a spatial dimension and uses the same interface model for hierarchical IDs. This further implies that date/time navigation should live in a module separate from general state machine logic.
### 2.3 Other core modules
    • External events: mycite_core/external_events/store.py provides functions to append and read external events from logs[7][8]. mycite_core/external_events/feed.py formats network messages and event summaries[9]. These modules are domain‑agnostic and could live in a general “events” module.
    • Reference exchange: mycite_core/reference_exchange/registry.py manages subscription registries, storing them in JSON files[10]. mycite_core/reference_exchange/imported_refs.py, however, depends on portal‑specific data engine modules and uses instances/_shared.portal.sandbox[11]. This cross‑dependency needs elimination or injection via interfaces.
    • Datum references: mycite_core/datum_refs.py defines parsing and normalisation of datum references[12][13]. It is a pure utility module and should live in a core module.
    • Local audit: mycite_core/local_audit/store.py logs audit events with timestamp and secret sanitisation[14]. This is another independent module.
    • MSS resolution: mycite_core/mss_resolution/core.py implements the Mixed Spatial Specification compile/resolve logic. It is large and heavy but can be treated as its own module. Some parts (like resolve_contract_datum_ref) rely on contract line modules, which implies coupling that needs to be broken.
    • Contract line: modules under mycite_core/contract_line manage contract creation, patching and storage. They use instances/_shared.portal.sandbox and portal/services functions, demonstrating the mixing of domain logic with host‑specific code.
### 2.4 Module contracts and inventory
    • The docs/modularity/module_contracts.md document enumerates responsibilities and dependencies for each module. For example, mycite_core/state_machine owns shell actions, reducers, view models and AITAS integration, but must not own file‑system topology, tool persistence or host bootstrap[15]. mycite_core/runtime_host owns runtime composition, path resolution and instance context, while instances/_shared/runtime should take over host bootstrap and route registration. This document is a useful authority for deciding where modules belong.
    • The module_inventory.md file summarises module assignments and indicates which modules have moved to runtime, tools, instances or packages. It notes transitional wrappers under instances/_shared that delegate to canonical owners[16].
## 3 Ontological Categories for Mycite‑v2
Based on the analysis above and the Hanus model, the following categories emerge for organising the V2 repository:
### 3.1 Core Operations
Modules that implement fundamental operations on data structures (compile/resolve MSS, parse datum refs, manage subscriptions, handle external events, maintain local audit logs). These modules must be pure and free of host‑specific dependencies.
### 3.2 State and Navigation
The UI shell state machine and Hanus button model belong here. This includes AITAS context models and view‑model builders. Navigation state should not import rendering code; it should provide pure state transitions and outputs.
### 3.3 Domain Modules
Specific domains (contracts, publications, reference exchange, etc.) should live in separate modules under packages/modules. Each domain module defines its own data types, operations and optional side‑effect interfaces. For example, a contracts module might define contract data structures and compile functions; host‑specific implementations (e.g., storing contracts on the server) are provided via pluggable ports.
### 3.4 Ports and Adapters
Ports define interfaces to external systems (filesystems, network APIs, database, instance state). For example, a datastore port defines functions to read/write contract and event logs. Adapters for server runtime or desktop runtime implement these ports. This aligns with the Hanus model’s concept of an interface surface separate from UI logic.
### 3.5 Tools
Tools are pluggable packages that operate on SAMRAS or HOPS structures. Each tool has canonical code under packages/tools/<tool> and defines its capabilities (verbs) that the state machine uses to match the tool to selected contexts[17]. Tool code should be independent of host logic and rely on core modules and ports.
### 3.6 Sandboxes
Sandboxes are runtime contexts where a tool interacts with data. They manage staging of changes, mediation of conflicting edits, and bridging between UI state and persistent storage. Sandboxes depend on state machine definitions and ports but must not implement contract semantics[18]. In V2 they should live under packages/modules/sandboxes or similar.
### 3.7 Hosts/Runtime Flavours
Specific deployments (server, desktop, CLI) are separate runtime flavours. Each flavour composes ports and modules into a running application. Host code belongs under instances/_shared/runtime or a new packages/runtimes directory; the packages/hosts directory is transitional and should be removed once modules are ported.
## 4 Proposed Repository Structure for V2
To align with the ontology above, the repository could be reorganised as follows:
mycite-v2/
├── packages/
│   ├── core/                 # Pure utility modules (datum_refs, local_audit, external_events, mss_resolution)
│   │   ├── datum_refs/
│   │   ├── local_audit/
│   │   ├── external_events/
│   │   ├── mss_resolution/
│   │   └── ...
│   ├── modules/              # Domain modules (contracts, publications, reference_exchange, etc.)
│   │   ├── contracts/
│   │   │   ├── model.py      # contract data structures
│   │   │   ├── operations.py # compile/patch logic
│   │   │   ├── ports.py      # interfaces for storage & indexing
│   │   │   └── ...
│   │   ├── publications/
│   │   ├── reference_exchange/
│   │   │   ├── registry.py   # subscription management (pure)
│   │   │   ├── operations.py # imported refs logic (with ports)
│   │   │   └── ...
│   │   └── ...
│   ├── state_machine/        # Navigation and view state (Hanus/AITAS)
│   │   ├── actions.py
│   │   ├── reducer.py
│   │   ├── view_model.py
│   │   ├── controls.py
│   │   └── ...
│   ├── ports/                # Interfaces for external systems
│   │   ├── datastore.py      # read/write contract, event logs
│   │   ├── scheduler.py      # time/calendar interactions (HOPS)
│   │   ├── audit.py          # audit logging
│   │   └── ...
│   ├── adapters/             # Host-specific implementations of ports
│   │   ├── server/
│   │   ├── desktop/
│   │   └── cli/
│   └── tools/                # Canonical tool code (existing `packages/tools`)
│       └── <tool>/
├── instances/
│   ├── _shared/
│   │   ├── runtime/
│   │   │   └── flavours/     # runtime composition for server/desktop/cli
│   │   ├── portal/api/
│   │   └── portal/ui/        # static assets, compiled UI shell using Hanus model
│   └── <instance>/           # instance-specific state roots
├── data/
│   ├── sandbox/<tool>/       # canonical tool datum anchors
│   └── payloads/             # compiled payloads (MSS bitstrings)
└── docs/
    ├── modularity/
    └── plans/
#### Explanation of Key Changes
    1. Create packages/core – house all pure utility modules. Modules like datum_refs, local_audit, external_events, mss_resolution and possibly typing helpers belong here because they implement pure operations and can be reused across domains. This removes them from mycite_core/ and clarifies that they do not depend on host logic.
    2. Create packages/modules – domain logic lives here. Each domain (contracts, publications, reference exchange, etc.) is encapsulated in its own sub‑package with clearly defined models, operations and ports. This prevents cross‑domain dependencies (e.g., reference exchange should not import portal data engine; instead, its operations.py uses ports.py to call appropriate datastore functions). Complex modules like mss_resolution may remain in packages/core if they are generic, but functions specific to contract resolution should be moved to the contracts module.
    3. Move state machine to packages/state_machine – The Hanus/AITAS state model, action definitions and view model builders should exist in a dedicated module independent of host code. It uses tools’ capabilities to build UI contexts but only depends on core modules.
    4. Define packages/ports and packages/adapters – Ports specify abstract interfaces (e.g., datastore with functions save_contract, fetch_events; scheduler for HOPS time segmentation; audit for logging). Adapters implement these interfaces for specific runtime flavours (server, desktop, CLI). This separation allows domain modules to remain independent of host details and aligns with the Hanus interface model’s decoupled surface.
    5. Eliminate packages/hosts – The packages/hosts/server_portal directory should be removed after migrating its responsibilities to instances/_shared/runtime and new packages/adapters/server. The plan calls for host‑specific runtime packaging to live under instances/_shared/runtime/flavours[1].
    6. Rework mycite_core – The existing mycite_core becomes obsolete. Its modules should be redistributed: pure utilities to packages/core, domain modules to packages/modules, and state machine to packages/state_machine. Transitional wrappers like mycite_core/runtime_paths.py can be removed once direct imports of new modules are established.
    7. Refactor cross‑dependencies – Modules like reference_exchange/imported_refs.py must not import portal data engine classes. Instead, they should define operations that accept port implementations injected at runtime. Similarly, contract line modules should not call sandbox functions directly; they can expose pure compile logic while sandboxes adapt them to runtime.
    8. Calendar tool – The HOPS calendar structures should be exposed via packages/ports/scheduler.py with a default implementation based on the current HOPS modules. A dedicated calendar tool under packages/tools/calendar can provide UI for navigating time as a spatial dimension, using the Hanus state machine for hierarchical IDs.
    9. Docs and plans – Keep docs/modularity and docs/plans updated. Add documentation describing the new ontology and design rationale, referencing the Hanus model and AITAS concepts. Provide migration guidelines for moving legacy modules into new structures.
## 5 Conclusion
The proposed mycite‑v2 structure aims to align with the ontological categories discovered through investigation. It removes the transitional mycite_core and packages/hosts directories, introduces clear separations between core operations, domain modules, ports and adapters, state machine, tools, and runtime flavours, and ensures host‑independent modules are pure. Adopting the Hanus interface model and HOPS calendar structures will enable a flexible UI shell that treats navigation and data structures uniformly, paving the way for a polished, modular system.

[1] README.md
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/packages/hosts/server_portal/README.md
[2] README.md
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/packages/tools/README.md
[3] view_model.py
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/mycite_core/state_machine/view_model.py
[4] controls.py
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/mycite_core/state_machine/controls.py
[5] [6] hanus_interface_model.md
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/plans/hanus_interface_model.md
[7] [8] store.py
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/mycite_core/external_events/store.py
[9] feed.py
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/mycite_core/external_events/feed.py
[10] registry.py
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/mycite_core/reference_exchange/registry.py
[11] imported_refs.py
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/mycite_core/reference_exchange/imported_refs.py
[12] [13] datum_refs.py
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/mycite_core/datum_refs.py
[14] store.py
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/mycite_core/local_audit/store.py
[15] module_contracts.md
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/modularity/module_contracts.md
[16] module_inventory.md
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/modularity/module_inventory.md
[17] tool_capabilities.py
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/mycite_core/state_machine/tool_capabilities.py
[18] sandboxes.md
https://github.com/Fruitful-Network-Development/mycite-core/blob/HEAD/docs/modularity/contracts/sandboxes.md
