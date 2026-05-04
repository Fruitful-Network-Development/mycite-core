# MOS Database Schema Addendum

## Purpose

This addendum extends the schema proposed in `mycelial_ontological_schema.md` with tables required by findings from the 2026-05-03 datum logic precision audit.

Reference: `mycelial_ontological_schema.md` for the base schema (sandboxes/files, datums, datum_references, SAMRAS, HOPS geometry tables).

## New Tables

### 1. `documents` (replaces/renames `files`)

Primary document entity with enforced naming policy.

```sql
CREATE TABLE documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     TEXT    NOT NULL UNIQUE,   -- canonical lv.*/stl.*/cptr.* name
    prefix          TEXT    NOT NULL CHECK (prefix IN ('lv', 'stl', 'cptr')),
    msn_id          TEXT    NOT NULL,
    sandbox         TEXT    NOT NULL,
    name            TEXT    NOT NULL,
    version_hash    TEXT    NOT NULL,          -- 64-char hex SHA-256
    is_anchor       INTEGER NOT NULL DEFAULT 0 CHECK (is_anchor IN (0, 1)),
    origin          TEXT    NOT NULL DEFAULT 'local' CHECK (origin IN ('local', 'foreign')),
    created_at      INTEGER NOT NULL           -- Unix epoch ms
);

CREATE UNIQUE INDEX idx_documents_document_id ON documents (document_id);
```

Note: the application layer validates `document_id` against the naming regex
`^(lv|stl|cptr)\.[^.]+\.[^.]+\.[^.]+\.[a-f0-9]{64}$` before insert.
See `datum_document_naming_taxonomy.md` for the full naming contract.

---

### 2. `samras_namespaces` (new — supports multiple SAMRAS address spaces per anchor)

One row per SAMRAS structure in an anchor document, named by namespace.

```sql
CREATE TABLE samras_namespaces (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     INTEGER NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    datum_address   TEXT    NOT NULL,          -- e.g. '1-1-2' for msn, '1-1-3' for ruigi
    namespace_name  TEXT    NOT NULL CHECK (namespace_name IN ('msn', 'ruigi', 'other')),
    root_ref        TEXT,
    raw_bitstream   BLOB,
    decoded_json    TEXT,
    decode_state    TEXT    NOT NULL DEFAULT 'pending'
                            CHECK (decode_state IN ('ready', 'blocked_invalid_magnitude', 'pending')),
    UNIQUE (document_id, namespace_name)
);
```

Note: the `msn` namespace currently lives at datum_address `1-1-2`.
The `ruigi` namespace (for precinct `247-*` addressing) is planned at a TBD datum address
(TASK-MOS-RUIGI-SAMRAS-2026-05-03).

---

### 3. `precinct_time_windows` (new — state profile precinct collection list)

Maps ruigi-SAMRAS node refs to HOPS chronological time windows within a state profile document.

```sql
CREATE TABLE precinct_time_windows (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    state_profile_id  INTEGER NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    ruigi_node_ref    TEXT    NOT NULL,        -- e.g. '247-17-77-1'
    time_start_hops   TEXT,                   -- nullable: open-ended window start
    time_end_hops     TEXT,                   -- nullable: open-ended window end
    datum_row_addr    TEXT    NOT NULL,
    UNIQUE (state_profile_id, ruigi_node_ref, time_start_hops, time_end_hops)
);
```

Usage: when the portal AITAS time = T, query returns `ruigi_node_ref` values where
`time_start_hops <= T <= time_end_hops`. Each match maps to the precinct document
`lv.<msn_id>.cts-gis.<ruigi_node_ref>.<hash>`.

---

### 4. `datum_hyphae_chains` (new — normalized hyphae chain storage)

Stores the ordered list of rudi datums constituting the hyphae value for a datum.

```sql
CREATE TABLE datum_hyphae_chains (
    datum_document_id  INTEGER NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    datum_address      TEXT    NOT NULL,
    chain_position     INTEGER NOT NULL,
    rudi_address       TEXT    NOT NULL,
    PRIMARY KEY (datum_document_id, datum_address, chain_position)
);
```

Hyphae chain rule: for datum D using rudi datum `0-0-K` as its highest reference,
the chain is `[0-0-1, 0-0-2, ..., 0-0-K]` regardless of which intermediate rudi datums
D directly references. Every preceding rudi datum must be present in the chain even if
not used.

Note: the chain derivation algorithm is implemented at
`MyCiteV2/packages/core/mss/datum_identity.py::derive_hyphae_chain`
(TASK-MOS-MSS-HYPHAE-CORE-2026-05-03).
This table supersedes the `datum_hyphae_chain` join table from `mycelial_ontological_schema.md`
with explicit positional ordering and document-scoped addressing.

---

### 5. `document_staging_map` (new — promotion tracking)

Tracks hippo staging path to canonical MOS document mapping.

```sql
CREATE TABLE document_staging_map (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    staging_path          TEXT    NOT NULL UNIQUE,
    canonical_document_id INTEGER REFERENCES documents (id) ON DELETE SET NULL,
    promoted_at           INTEGER,             -- Unix epoch ms, nullable until promoted
    promotion_method      TEXT                 -- e.g. 'filesystem_adapter', 'manual', 'migration_script'
);
```

Purpose: enables tracking which hippo source files have been promoted to canonical MOS
documents and which remain pending. Every staging path known to the filesystem adapter
should have a row here from first discovery.

---

## Relationships to Prior Schema

| New table | Relationship to `mycelial_ontological_schema.md` |
|---|---|
| `documents` | Supersedes `files` — all `file_id` foreign keys in geometry tables should reference `documents.id` |
| `samras_namespaces` | Supersedes `samras_structures` — supports multiple SAMRAS address spaces per document rather than one structure per file |
| `precinct_time_windows` | New — no prior equivalent |
| `datum_hyphae_chains` | Formalizes `datum_hyphae_chain` from the prior schema with explicit chain position and document-scoped datum addressing |
| `document_staging_map` | New — enables migration tracking from staging-style filenames to canonical `lv.*`/`stl.*`/`cptr.*` naming |
