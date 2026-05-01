# Mapping MyCite “datum” logic to a database schema

## Background

### Definitions and terminology from the repository

* **Filament datum** – a **source‑file owner binding row** (a `7‑*` row in a HOPS profile source file) that acts as the forward‑facing access point for a profile source.  It binds a **primary** and optional **additive** geometry collection for a particular SAMRAS node【761292837965265†L70-L136】.  Filament datums are the rows a tool interacts with; other rows provide the supporting geometry or collections.

* **Hyphae value** – the **connective value** derived from the chain of binding links when generating or repairing source files【761292837965265†L70-L78】.  In practice, a hyphae value encapsulates the minimal set of datum abstractions needed to build a datum.  When computing it, the engine must include all preceding rudi datums even if they are not used directly.  For example, if the abstraction uses address `0‑0‑5`, the hyphae value includes `0‑0‑1` through `0‑0‑5`.  This ensures that all datums are canonical and that the engine can regenerate the datum consistently.

* **SAMRAS structure** – the **shape‑addressed mixed‑radix address space** used by CTS‑GIS.  SAMRAS defines the tree of nodes, but nodes do not store full addresses directly; instead the structure stores child counts in breadth‑first order and derives addresses from ordinal positions【1240787272904†L8-L21】.  Validity conditions for SAMRAS require that the width fields decode correctly, stop addresses are increasing, children are contiguous, etc.  Mutations to the structure must decode the current magnitude, derive the address tree, apply the mutation, and regenerate the canonical bitstream【582602634194372†L20-L33】.  CTS‑GIS decodes the namespace from `msn‑SAMRAS` magnitudes, with administrative rows providing only label overlays【939378820539835†L8-L21】.

* **HOPS profile sources** – CTS‑GIS stores profile sources as HOPS‑backed rows rather than pre‑rendered GeoJSON.  A profile source uses a `4 → 5 → 6 → 7` chain: `4‑*` rows store coordinate rings (HOPS tokens), `5‑*` rows group rings into polygon members, `6‑*` rows group members into collections, and `7‑*` rows bind collections to SAMRAS nodes【761292837965265†L70-L136】.  At runtime, the Garland projection decodes HOPS tokens into `(longitude, latitude)` coordinates, joins the `5‑*` and `6‑*` rows, and constructs the final GeoJSON.  Validity rules require that every referenced row exists, counts match, and the owner row binds to the correct SAMRAS node【761292837965265†L179-L188】.

### User’s datum environment

The user describes a file‑based datum environment with several file types:

| File type (table category) | Description |
| --- | --- |
| **Anchor files** | The central file of a sandbox.  In the **system** sandbox the anchor is `anthology.json`; other sandboxes have an `anchor.json` or `anchor` file (the canonical name is always `anchor` except for the system anchor `anthology`)【761292837965265†L70-L136】.  Anchor files seed the datum table; all other files in the sandbox are tied back to the anchor. |
| **Binary payloads** | Hyphae‑form files – compiled representations of filament datums.  They may originate from a local portal or a foreign portal. |
| **Cached sources** | De‑compiled versions of the binary payloads.  They contain all datum abstractions needed to define the filament datum’s hyphae value. |
| **Sandbox sources** | Clones of payloads or newly created datum files inside a sandbox.  A sandbox file can reference datums in the anchor file as if they were “branches”; each non‑anchor file carries version hashes and metadata indicating whether it is local or foreign.  Contracts manage update rights. |
| **Other files** | Tool‑specific profiles and specs are tracked separately and referenced via their JSON unit (e.g., the tool’s `spec.json` is referenced by datum `1‑0‑1` with rudiment `0‑0‑11`).  The user wishes to exclude these from the datum schema for now. |

File names follow a canonical convention: `type.msn_id.sandbox.anchor_or_name[.<name>].<hash>` where:

* `type` is a two‑to‑four‑letter prefix indicating file type (`lv` for level files, `sc` for cached sources, `stl` for binary payloads, `cptr` for cached profile transcripts).  
* `msn_id` is the portal or sandbox identifier.  
* `sandbox` is the sandbox name (`system` for the system sandbox).  
* `anchor_or_name` is `anchor` for anchor files or the file name for other files; anchor names are always `anchor` except for the system anchor `anthology`.  
* `name` is an optional name for non‑anchor files.  
* `hash` is the MSS (monotonic structured serialization) hash of the file in its fully composed form.  Hashes allow file‑level versioning and foreign/local identification.

### Ordering and editing rules

* **Datum addresses** use a three‑segment structure: `<layer>‑<value_group>‑<iteration>`.  A datum’s position within its layer and value group (iteration) must never be skipped.  When inserting or removing datums, the system must **shift iteration values** down or up to maintain contiguous ordering.  Because datums may be referenced by other datums (e.g., a projection referencing a particular row), shifting requires **updating all dependent references** to maintain correctness.  This means insertions and deletions must propagate changes from the highest abstraction down to dependent datums to avoid domino effects.  
* Datums are ordered not only by their position but also by the **magnitude** of their references: if two datums are in the same “immediate family,” the one whose referenced magnitude is larger comes later.  
* A datum file must be written to the database only when the layer, value‑group and iteration values are properly ordered; temporary in‑memory edits may break ordering but cannot persist without enforcing these rules.  
* The engine uses **lenses** to render human‑readable forms while keeping raw data.  A lens leaves a watermark in the lower‑left cell; hovering reveals the lens being applied.  The raw datum table is always accessible via the underlying canonical values.  

These constraints make the datum environment more like a **structured ledger** than a loosely ordered set of documents.  The database must preserve ordering, support versioned files, and maintain relationships between datums across files and sandboxes.

## Proposed database schema

Because the user wishes to preserve ordering and versioning while representing complex relationships (SAMRAS trees, HOPS geometry chains and hyphae relationships), a **relational database** is appropriate.  The schema below provides tables for sandboxes, files, datums, hyphae chains and geometry rows.  Where relationships are many‑to‑many, join tables are used.  The schema is designed to be extensible to additional tools (like CTS‑GIS) while focusing on datum content.

### 1. Sandbox and file tables

| Table | Purpose | Important fields |
|---|---|---|
| **sandboxes** | Stores each sandbox/environment (e.g., `system`, `cts-gis`, other project‑specific sandboxes). | `id` (PK), `msn_id` (portal/sandbox identifier), `name` (sandbox name), `created_at` |
| **files** | Represents every file containing datums.  Each file belongs to a sandbox and has a type (anchor, payload, cache, sandbox source).  Version hash identifies the exact version (MSS) of the file. | `id` (PK), `sandbox_id` (FK → sandboxes), `type` (`anchor`, `payload`, `cache`, `source`), `canonical_name` (e.g., `anthology`, `anchor`, `natural_entity`), `name` (for non‑anchor files), `version_hash` (MSS hash), `is_local` (boolean: local vs foreign), `created_at`, `updated_at` |
| **file_versions** (optional) | Tracks historical versions of a file.  When a file is updated (new hash), a new row is inserted; the `files.version_hash` always points to the latest version. | `id` (PK), `file_id` (FK → files), `version_hash`, `payload` (binary or JSON), `created_at` |

The `files` table uses a composite unique constraint on `(sandbox_id, type, canonical_name, name, version_hash)` so each version is unique.  Additional file metadata (such as tool spec references) can be stored in a JSON column or separate tables later.

### 2. Datum tables

Datums are the core units.  Each datum belongs to exactly one file and is identified by its `<layer>‑<value_group>‑<iteration>` address.  The database enforces ordering and contiguity via constraints and triggers.

| Table | Purpose | Important fields |
|---|---|---|
| **datums** | Stores every datum row in a file. | `id` (PK), `file_id` (FK → files), `layer` (integer), `value_group` (integer), `iteration` (integer), `datum_type` (`rudi`, `filament_owner`, `geometry_ring`, `polygon_member`, `collection`, `binding` etc.), `payload` (JSON or binary depending on type), `primary_value_token` (nullable; used for hyphae recognition), `recognized_family`/`anchor` flags, `created_at` |
| **datum_references** | Captures references from one datum to another (e.g., `5-*` referencing `4-*`, `6-*` referencing `5-*`, `7-*` referencing `6-*`). | `id` (PK), `datum_id` (FK → datums, row that holds the references), `ref_datum_id` (FK → datums, referenced row), `order_index` (order of the reference), `created_at` |
| **datum_hyphae_chain** | Stores the hyphae value chain for a datum.  Each entry records the required preceding datums needed for the hyphae abstraction. | `datum_id` (FK → datums, PK), `preceding_datum_id` (FK → datums, PK), `position` (integer, ordering of chain) |

**Ordering enforcement** – create a unique index on `(file_id, layer, value_group, iteration)` so no duplicate addresses exist.  Use triggers or application logic to shift the `iteration` values of existing datums when a new datum is inserted or removed.  When insertion or deletion occurs, update the `datum_references` table accordingly: if a referenced datum’s iteration value changes, cascade updates to all referencing rows.  Because cross‑file references exist (a sandbox source may reference anchor datums), cascading updates may need to run across multiple files.

### 3. SAMRAS and HOPS geometry tables

CTS‑GIS uses SAMRAS structures and HOPS geometry.  These structures can be normalised in database tables to support efficient navigation and projection.  The following tables map directly to the `4‑5‑6‑7` chain described in the contract【761292837965265†L70-L136】.

| Table | Purpose | Important fields |
|---|---|---|
| **samras_structures** | One row per SAMRAS magnitude (found in a file or cache). | `id` (PK), `file_id` (FK → files), `raw_bitstream` (binary), `decoded` (JSON containing decoded child counts), `valid` (boolean) |
| **samras_nodes** | Represents each node in a SAMRAS tree.  Each node belongs to a structure and can store administrative labels. | `id` (PK), `structure_id` (FK → samras_structures), `node_id` (string, e.g., `3-2-3-17-77`), `parent_node_id` (nullable), `depth` (integer), `title` (ASCII title from `rf.3-1-3`), `created_at` |
| **geometry_rings** | Stores the `4‑*` rows: a ring consists of HOPS coordinate tokens. | `id` (PK), `datum_id` (FK → datums), `length` (integer), `tokens` (text array or JSON), `created_at` |
| **polygon_members** | Represents `5‑*` rows: groups of rings. | `id` (PK), `datum_id` (FK → datums), `order_in_collection` (integer), `created_at` |
| **polygon_member_rings** | Join table between polygon members and geometry rings. | `polygon_member_id` (FK → polygon_members), `ring_id` (FK → geometry_rings), `is_exterior` (boolean), `order_index` (integer) |
| **collections** | Represents `6‑*` rows: groups of polygon members. | `id` (PK), `datum_id` (FK → datums), `collection_type` (primary vs additive), `created_at` |
| **collection_members** | Join table between collections and polygon members. | `collection_id` (FK → collections), `polygon_member_id` (FK → polygon_members), `order_index` (integer) |
| **profile_bindings** | Represents `7‑*` filament owner rows.  Each binding row connects a SAMRAS node to one or more collections. | `id` (PK), `datum_id` (FK → datums), `primary_node_id` (string), `secondary_node_id` (nullable), `primary_collection_id` (FK → collections), `created_at` |

This structure allows the database to assemble a `MultiPolygon` for a given SAMRAS node by following `profile_bindings → collections → polygon_members → geometry_rings` and decoding HOPS tokens into coordinate pairs at runtime (the decode logic can reside in application code).  Validity constraints (e.g., unique references, correct counts) can be enforced via triggers or by validation routines that run when inserting rows, replicating the rules described in the contract【761292837965265†L90-L135】.

### 4. Hyphae and rudi support

To capture hyphae semantics, we need to model the relationship between datums and the rudi datums they depend on:

* The `datum_hyphae_chain` table captures the canonical chain; for each datum `d`, the chain lists the rudi datums that must be present to abstract `d`.  This ensures hyphae value reconstruction can include all preceding datums even if they are not directly referenced in the payload.  
* A `hyphae_values` view can compute the hyphae value by concatenating the `primary_value_token` fields of the chain in order.  The view can also include a hash to serve as a hyphae key.  

A `rudi_datums` table (not shown) can record which datums correspond to rudiments (e.g., `0‑0‑1` for JSON‐unit, `0‑0‑5` for SAMRAS magnitude) along with their semantics.  This helps separate generic rudiments from domain‑specific datums.

### 5. Versioned editing and foreign vs. local files

Given the user’s requirement to track local vs foreign payloads, the schema should support **contracts** that define update rights.  A table `file_contracts` can record, for each file version, whether modifications are allowed (`update_allowed` boolean), whether the file is local or foreign, and which contract governs it.  Application logic will consult this table before allowing inserts or updates to datums.

### 6. Exposing raw vs lens views

The user wants to preserve the ability to view and edit raw datum tables while presenting human‑friendly forms.  A lens is essentially a **projection** over the datum table with additional metadata (labels, units, geometry).  This can be implemented as a separate `lenses` table that records lens type (`ascii`, `geojson`, `yaml`, etc.), the dataset it applies to, and transformation rules.  When the application loads data, it can apply the appropriate lens and display the watermark.  Because the raw data remains in the `datums` and geometry tables, a developer can query or export the canonical values easily.

## Unclear or incomplete logic areas

During research, some parts of the datum system were still ambiguous or not fully documented in the repository:

1. **Rudi datums and MSS hashing** – the user mentions that the MSS form (monotonic structured serialization) of a file is well documented “if not in this repo version, in past commits.”  However, I could not locate the exact MSS hashing algorithm or the precise way rudi datums influence the hash.  Without this algorithm, it is difficult to compute the `version_hash` field or verify hyphae value consistency.  Additional documentation or code (possibly in older commits) is needed to implement the hash generator.

2. **Hyphae chain derivation** – while the high‑level definition of hyphae value is available【761292837965265†L70-L78】, the repository does not include the precise algorithm for deriving the chain from the datum references or computing the hyphae.  It is unclear how to detect all preceding datums required for hyphae beyond the explicit references (e.g., does it include all datums in the same value group? all rudi datums up to the referenced layer?).  Further investigation into `datum_recognition` modules (e.g., `MyCiteV2/packages/modules/domains/datum_recognition/`) is recommended to extract the algorithm.

3. **Editing logic for insertions/deletions** – the repository’s audit plan stresses the importance of deterministic ordering and editing rules【950437054167590†L74-L82】, but I did not find a complete specification of the algorithm for shifting iteration values and updating references.  This logic likely exists in the domain modules (e.g., `datum_store`, `datum_refs.py`) but was not accessible via this API.  When implementing the database, application‑level functions must handle these changes atomically and maintain referential integrity across multiple files.

4. **NIMM/AITAS directives** – the user refers to NIMM (Navigation, Investigation, Mediation, Manipulation) and AITAS (Attention, Intention, Time, Archetype, Space) directive/context models.  These concepts appear in personal notes and planning documents but do not have a canonical implementation in the repository (the repo restricts NIMM/AITAS to CTS‑GIS tool‑local state【650795509601885†L315-L325】).  If the user plans to extend these directives to the general datum environment, additional schema tables (e.g., `directives`, `contexts`) will be required.  At present, the schema focuses on the canonical contract.

5. **External YAML configuration** – the user is interested in using YAML files to optimise agent credit usage.  The repository does not include examples of YAML‑driven tasks, but industry practice suggests storing agent workflow configurations in YAML to make them human‑readable and editable outside of code.  For example, CodeSignal notes that externalizing agent configurations to YAML provides maintainability and flexibility【71779208011746†L14-L47】.  If adopted, a table `yaml_configs` could store parsed YAML documents associated with files or tasks, and the application could load agent instructions from these.  In some frameworks, YAML can specify tasks for an AI agent, the files to inspect, and the expected outputs; such an approach could help reduce API usage by focusing the agent on relevant modules.  Without concrete examples from the repository, this remains speculative.

## Recommendations for adopting a database schema

1. **Relational database with strong constraints** – Use a relational database (e.g., PostgreSQL) to enforce ordering, unique addresses, and referential integrity.  Create triggers or stored procedures for shifting iterations and updating references when datums are inserted or deleted.  Index the `datums` table on `(file_id, layer, value_group, iteration)` to support quick lookups and maintain contiguous ordering.

2. **Versioning and immutability** – Because files are versioned by MSS hashes, store file contents immutably in `file_versions`.  When a user edits a file, create a new version rather than overwriting the old one.  Keep `files.version_hash` pointing to the latest version to simplify lookups.  This design supports concurrent editing and easy rollback.

3. **Mapping SAMRAS and HOPS** – Represent SAMRAS structures and HOPS geometry using dedicated tables.  The chain `4‑* → 5‑* → 6‑* → 7‑*` maps naturally to tables `geometry_rings`, `polygon_members`, `collections` and `profile_bindings` with join tables for many‑to‑many relations.  Enforce validity rules (unique references, correct counts, matching node IDs) through database constraints and validation routines.

4. **Hyphae chain materialization** – Implement logic in the application layer (or stored procedures) to compute the hyphae chain for each datum by traversing its references and collecting required rudi datums.  Store this chain in `datum_hyphae_chain` for quick retrieval.  Provide functions to recalculate hyphae after editing operations.

5. **Lens support** – Keep raw data in the database and apply lens transformations in the application.  A `lenses` table can record which lens is applied to a view.  The lens information can be surfaced to users through UI watermarks while preserving raw data access for administrators.

6. **Local vs foreign files and contracts** – Use a `file_contracts` table to specify whether a file is local or foreign and what update policies apply.  Application logic should check this table before allowing modifications.  This preserves the user’s intent to manage ownership and update rights.

7. **YAML configuration for agent tasks** – If the user wants to optimize AI agent usage, consider storing agent workflow definitions in YAML files.  YAML configurations can specify which modules or files to inspect, the sequence of operations, and expected outputs.  Externalizing these instructions makes them easier to audit and reuse【71779208011746†L14-L47】.  A `yaml_configs` table could store parsed YAML definitions keyed by task name or tool.

8. **Future extensions** – As the NIMM/AITAS model becomes canonical, extend the schema with tables to capture directives (`nimm_directive`, `aitas_attention`, etc.) and tie them to datums, files or UI state.  Additional tables can model tool‑local state (as described in CTS‑GIS plans【650795509601885†L315-L325】) when needed.

## Conclusion

The MyCite datum environment is a sophisticated file‑based system that uses structured addresses, SAMRAS trees, HOPS geometry and hyphae abstractions.  To adopt a database representation, you should map sandboxes, files and datums into relational tables, enforce ordering and versioning, and model the geometry chains used by CTS‑GIS.  Where the repository provides contracts (e.g., SAMRAS decoding, HOPS profile sources, ordering rules), the schema should incorporate those constraints.  Areas where the logic is unclear (MSS hashing, hyphae chain derivation, editing algorithms) will require further investigation or your own conventions to complete the implementation.  Once implemented, this schema will allow stable and safe portal rollouts and provide a robust foundation for future expansion into database‑backed operations.
