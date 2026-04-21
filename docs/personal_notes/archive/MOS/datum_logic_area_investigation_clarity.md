# Investigation into MyCite‑core repository: Rudi datums, MSS hashing, hyphae chains, editing logic and NIMM/AITAS directives

## Introduction

The MyCite‑core repository serves as the **data engine** behind the MyCite knowledge network.  It implements a canonical contract for representing collections of *datums* (atomic facts) and provides services for **Monotonic Structured Serialization (MSS)**, *datum recognition*, and *write pipelines*.  Many of the concepts mentioned in the user’s questions relate to features that evolved across several commits.  I audited the repository’s history using the GitHub connector and reviewed documentation and code in older commits to reconstruct how MSS hashing, hyphae derivation, insertion/edit logic, and directive models were designed.  Below is a detailed report describing what could be extracted and what remains undefined.

## Rudi datums & MSS hashing

### Background

Rudi datums were mentioned in planning notes but not clearly defined in the current repository.  Searching the commit history for `rudi`, `rudi datums` and similar terms returned no code or documentation.  Based on related domain modules (`datum_recognition`, `mss_compact_array_reference`), “Rudi” appears to refer to one of the **datum families** used in the *SAMRAS* domain (possibly the `Rudi` archetype in SAMRAS taxonomy).  The `datum_recognition` module introduced in `v2.3` sets up a recognition service that classifies datums into families like `nominal` or `SAMRAS Babelette` and computes diagnostics for invalid addresses, unresolved anchors, etc.  However, there is no code implementing special hashing behaviour for a “Rudi” datum.

### MSS compact‑array and hashing algorithm

While the repository does not implement a direct **hashing algorithm** for `version_hash` or `hyphae`, older commits contain a *reference implementation* of the MSS compact‑array logic.  Commit **ef52266820c9c5f22dde16d32fe91c2c34696f3e** (titled *“MyCite portal write model hardening & review and fix of MSS compact‑array assumptions and implementations”*) introduced a comprehensive file `mss_compact_array_reference.py`.  This file documents how the MSS bitstream is constructed and acts as the canonical reference for **Monotonic Structured Serialization**:

- The code defines data models (e.g., `DatumRow`, `RefMagTuple`, `MSSMetadata`) and helper functions to encode integers using **self‑delimiting (SD) integers** and fixed‑width fields.  It uses SD integers to encode variable‑length values like counts and widths【281755566605246†L15-L23】.
- The **transitive closure** of selected datums is computed by iteratively adding referenced rows; this closure is then **re‑indexed** to a local anthology (the selected rows plus all references) and used as the basis for serialization.  The algorithm includes building metadata (e.g., number of selected rows, number of reference rows, widths of fields) and computing **carry‑over bitmasks (COBM)** that indicate whether additional bits are needed when storing magnitude values【281755566605246†L15-L23】.
- For each datum row in the re‑indexed anthology, the algorithm determines whether to encode only its references (value group 0) or to encode reference/magnitude tuples (value groups >0).  It encodes the sequence of references and magnitudes using SD integers and stores them consecutively.  Stop‑index tables and width sentinel fields are appended at the end of the bitstream【281755566605246†L42-L44】.
- In the same commit, the repository introduced **canonical_v2** wire variant.  A function `_pack_v2_bitstring` in `mss/core.py` assembles the final bitstring: it prefixes an 8‑bit header `11101110`, encodes the canonical bitstring, and appends a **source‑identifier extension** which lists the *semantic addresses* of each row.  This allows stable path resolution when datums are reindexed in different anthologies【281755566605246†L86-L88】.  The documentation emphasises that `canonical_v2` is the current writer output【281755566605246†L10-L11】.

The MSS reference model thus provides a complete algorithm for building and encoding the MSS bitstream, but there is **no explicit hashing function** that digests the bitstream into a `version_hash`.  Instead, the canonical contract uses the bitstream itself (with a base‑64 encoding) as the `mss_compact_array`.  The `version_hash` field referenced in the agent’s concerns likely refers to a not‑yet‑implemented feature for verifying bitstream integrity; no code in the repository computes a cryptographic hash over the MSS or uses *Rudi datums* to influence such a hash.  Therefore:

1. **No algorithm for MSS hashing was found.**  The repository serializes MSS bitstreams but does not compute a `version_hash` from them.
2. **Rudi datums do not influence the MSS algorithm**; datums of any family are serialized identically once recognized and re‑indexed.  The `datum_recognition` service flags irregularities but does not alter the serialization.

## Hyphae chain derivation

### High‑level concept

The “hyphae” value is presented in later commits as a universal identifier derived from the **semantic context** of a datum.  Commit **fffb00406b86de20c64b4b7c468f29c5137289c5** refactored the repository to replace `canonical_v2` with a **hyphae‑based canonical form**.  It introduced new modules `mycite_core/mss_resolution/datum_space.py` and `resolution.py` and removed the `MSS_WIRE_VARIANT_CANONICAL_V2` constant.  The diff shows functions such as `stable_datum_id`, `resolve_to_local_row`, `datum_paths_equivalent`, and `parse_datum_path`.  These functions compute a canonical path (semantic address) for a datum by combining **anchor and sources** loaded from the repository and by mapping references to local rows【566861718241572†L7-L16】.  Source identifiers are appended to the bitstring externally and the canonical path is used as a stable identifier across anthologies.

### Missing chain‑derivation algorithm

Despite the addition of hyphae‑related functions, the repository never revealed an explicit algorithm for **deriving the hyphae chain**.  In the commit message the author notes that the canonical hyphae form would replace the `canonical_v2` bitstring, but the code only supplies helpers for resolving a datum’s path and constructing a canonical path; it does not describe how to assemble a “chain” of hyphae values nor how to detect “all preceding datums” beyond the explicit references.  Some insights from the audit:

- The **datum recognition** module emphasises that **datum addresses are not stable identities**.  The new recognition service preserves irregular addresses but flags them, underscoring that **hyphae** would be the stable identity used for canonical referencing.
- The commit adds a `resolve_to_local_row` function that loads an anthology and merges anchor and sources to map canonical paths to local rows, but it does not propagate transitive dependencies beyond explicit references【566861718241572†L7-L16】.  It appears that the chain would at least include the transitive closure of references (similar to the MSS algorithm) but the repository does not codify this.
- The `datum_structure.py` file from commit `893df7c49ebd5459` clarifies that the anthology address (`layer‑value_group‑iteration`) and the MSS index are not interchangeable and must be numerically ordered【515832510963258†L8-L12】.  However, it offers no mechanism for computing hyphae.

Given these observations, there is **no implementation** of hyphae chain derivation in the repository.  The conceptual model suggests that hyphae would be derived from the canonical path (semantic address) and possibly incorporate transitive closure of references; nevertheless, the exact algorithm remains unpublished.

## Editing logic for insertions and deletions

### Deterministic ordering and address shifts

The MyCite audit plan emphasises that datums must be **inserted** or **deleted** in a deterministic manner such that references remain valid and the `layer-value_group-iteration` addresses maintain stable ordering.  Evidence from past commits includes:

- The `datum_structure.py` module introduced in commit `893df7c49ebd5459` defines a `DatumAddress` dataclass and helper functions to parse addresses and compare them **numerically** rather than lexicographically.  Comments in this file stress that *anthology address*, *SAMRAS structure* and *MSS index* are distinct and cannot be used interchangeably【515832510963258†L8-L13】.  Sorting functions always convert the `layer`, `value_group` and `iteration` components to integers to ensure numeric ordering.  This ensures deterministic iteration sequencing when inserting or deleting rows.
- The `datum_recognition` service from commit `0c34efdabaf493a3d058e1cd5b2e3d3102bf4cec` reads authoritative documents and preserves raw rows exactly, including irregular addresses or illegal placeholders.  It produces diagnostics rather than adjusting iteration numbers.  This indicates that recognition does not perform insertion logic; rather, it defers reindexing to later services.

### Missing comprehensive editing logic

Although these modules enforce ordering and recognition rules, the repository lacks a **complete specification** for shifting iteration values and updating references after insertions or deletions.  Functions for reindexing appear in the MSS reference model (e.g., `transitive_closure` and `compile_isolated_anthology`) which renumber rows during serialization, but this happens in the context of bitstream compilation, not general editing.  The write pipeline introduced in commit `ef52266820c9c5f22dde16d32fe91c2c34696f3e` implements actions like creating and reusing datums and updating contract contexts.  It ensures that updates are deterministic and reuses existing references when possible.  However, there is no generic algorithm describing how to shift iteration values when rows are inserted or removed in the anthology.  Instead, the pipeline relies on application‑level logic to maintain referential integrity.

## NIMM/AITAS directives

NIMM (Navigation, Investigation, Mediation, Manipulation) and AITAS (Attention, Intention, Time, Archetype, Space) are conceptual models described in personal notes and planning documents, but they do not have a canonical implementation in the `mycite‑core` repository.  Searching the commits reveals references to these directives only in UI notes or internal wiki pages.  The contract schema focuses on the canonical representation of datums and MSS; it does not include tables or code to manage NIMM/AITAS contexts.  The repository’s `trusted_tenant_shell_region_kinds.md` explains that UI regions include *datum_workbench* and *datum_summary* for admins, while NIMM/AITAS directives are restricted to tool‑local state and are not part of the canonical data engine.  To extend these concepts to the general datum environment, one would need to add schema tables (e.g., `directives`, `contexts`) and design services to propagate directive states, but this lies outside the current repository.

## Conclusion

Through extensive examination of past commits, the following conclusions can be drawn:

1. **MSS hashing**: The repository includes a reference implementation of the MSS compact‑array algorithm (canonical_v2) that serializes selected datums and their transitive closure into a bitstream.  It does not compute a cryptographic hash; thus the `version_hash` mentioned in the audit plan is not supported.  There is no evidence that *Rudi datums* influence the serialization; datums are treated uniformly once recognized.
2. **Hyphae chain derivation**: High‑level support for hyphae values was introduced after canonical_v2, but the repository lacks a concrete algorithm for deriving a hyphae chain.  Functions exist to resolve canonical paths and compute stable IDs, yet there is no code assembling the chain or describing the required preceding datums.
3. **Editing logic**: The system enforces numeric ordering of `layer-value_group-iteration` addresses and flags irregularities, but it does not provide a comprehensive algorithm for shifting iteration values on insertions/deletions.  The write pipeline reuses existing references and ensures deterministic updates, leaving application‑level logic responsible for atomic edits and referential integrity.
4. **NIMM/AITAS directives**: These directive models appear only in personal notes and are not implemented in the core repository.  Extending them to the canonical data engine would require new schema tables and services.

### Recommendation

To implement the missing features, developers should:

- **Specify a hashing scheme** for `version_hash` if immutability or detection of tampering is required.  Options include computing a SHA‑256 digest over the canonical MSS bitstream or over a sorted list of `semantic_address` values.
- **Define the hyphae chain algorithm** in a formal specification.  It should clearly describe how to derive a chain from a datum’s references, which families of datums are included (e.g., all preceding layers or just transitive closure), and how this interacts with MSS serialization.
- **Design editing rules** that describe how inserting or deleting datums shifts iteration numbers and how to update references.  These rules should ensure deterministic behaviour and avoid collisions.
- **Develop a separate module for NIMM/AITAS** if these directives must be integrated into the data engine, including database schema extensions and APIs.
