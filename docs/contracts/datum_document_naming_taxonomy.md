# Datum Document Naming Taxonomy

## Overview

Datum documents are the atomic storage units of the MOS (Mycelial Ontological Schema).
Every datum document has a canonical identifier following a strict naming convention.

## Prefix Definitions

Three prefixes define the document type:

| Prefix | Full name | Type |
|--------|-----------|------|
| `lv.` | live | Anchor files and all sandbox datum sources |
| `stl.` | stale | Binary payloads (compiled/hyphae form of filament datums) |
| `cptr.` | capture | Cached decompiled sources (datum abstraction form of a payload) |

## Canonical Name Format

```
lv.<msn_id>.<sandbox>.<name>.<version_hash>
stl.<msn_id>.<name>.<version_hash>
cptr.<msn_id>.<name>.<version_hash>
```

Fields:

- `msn_id`: Portal/sandbox identifier (e.g., `3-2-3-17-77-1-6-4-1-4`)
- `sandbox`: Sandbox name (e.g., `cts-gis`, `system`)
- `name`: Document name — `anchor` for anchor files, `anthology` for the system sandbox anchor, or a specific name for other documents
- `version_hash`: SHA-256 of the MSS (Monotonic Structured Serialization) form of the file

## Anchor File Naming Rules

- General sandbox anchor: `lv.<msn_id>.<sandbox>.anchor.<hash>`
- System sandbox anchor: `lv.<msn_id>.system.anthology.<hash>`
- The name `anchor` is reserved for anchor files. `anthology` is reserved for the system sandbox anchor only.

## Concrete Examples

| Staging form | Canonical form |
|---|---|
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17.json` | `lv.3-2-3-17-77-1-6-4-1-4.cts-gis.3-2-3-17.<hash>` |
| `sc.3-2-3-17-77-1-6-4-1-4.cts.247_17_77_1.json` | `lv.3-2-3-17-77-1-6-4-1-4.cts-gis.247-17-77-1.<hash>` |
| `tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json` | `lv.3-2-3-17-77-1-6-4-1-4.cts-gis.anchor.<hash>` |
| `sc.3-2-3-17-77-1-6-4-1-4.registrar.bin` | `stl.3-2-3-17-77-1-6-4-1-4.registrar.<hash>` |
| `sc.3-2-3-17-77-1-6-4-1-4.registrar.json` | `cptr.3-2-3-17-77-1-6-4-1-4.registrar.<hash>` |
| `anthology.json` | `lv.3-2-3-17-77-1-6-4-1-4.system.anthology.<hash>` |

## Staging-to-Canonical Mapping

During migration from filesystem staging to SQL database:

- `sc.*` prefix = staging candidate — becomes `lv.*`, `stl.*`, or `cptr.*` based on file type and content
- `tool.*` prefix = staging anchor — becomes `lv.*.anchor.*`
- The filesystem adapter translates staging paths to canonical document IDs at read time during migration
- The sandbox segment resolves from the staging path: `fnd.*` staged geometry maps to the `cts-gis` sandbox; `msn-*` staged overlays map to the system sandbox context

## Version Hash

The `<version_hash>` field is the SHA-256 of the MSS (Monotonic Structured Serialization) form of the document:

- MSS form requires all datum iteration values to be properly ordered (no skips)
- Self-delimiting integer encoding with transitive closure
- Computed by `_sha256_token(prefix=MSS_VERSION_HASH_POLICY, payload=payload)` (see `packages/adapters/sql/datum_semantics.py`)
- A standalone `compute_mss_hash()` library function is planned (TASK-MOS-MSS-HYPHAE-CORE-2026-05-03)

## Validation

Document IDs must match the pattern:

```
^(lv|stl|cptr)\.[^.]+\.[^.]+\.[^.]+\.[a-f0-9]{64}$
```

Validation is enforced at the datum store adapter boundary.

## Migration Status (as of 2026-05-03)

Zero live database documents currently use the canonical `lv.*`/`stl.*`/`cptr.*` naming.
All live documents use staging-style prefixes. Migration is in progress per `mos_sql_backed_core_declaration_draft.md`.
