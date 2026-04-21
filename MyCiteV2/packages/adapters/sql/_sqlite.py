from __future__ import annotations

from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS authoritative_catalog_snapshots (
    tenant_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    updated_at_unix_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS system_workbench_snapshots (
    tenant_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    updated_at_unix_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS publication_summary_snapshots (
    tenant_id TEXT NOT NULL,
    tenant_domain TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    updated_at_unix_ms INTEGER NOT NULL,
    PRIMARY KEY (tenant_id, tenant_domain)
);

CREATE TABLE IF NOT EXISTS portal_authority_snapshots (
    scope_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    updated_at_unix_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_records (
    record_id TEXT PRIMARY KEY,
    recorded_at_unix_ms INTEGER NOT NULL,
    record_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS datum_document_semantics (
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    policy TEXT NOT NULL,
    version_hash TEXT NOT NULL,
    canonical_payload_json TEXT NOT NULL,
    updated_at_unix_ms INTEGER NOT NULL,
    PRIMARY KEY (tenant_id, document_id)
);

CREATE TABLE IF NOT EXISTS datum_row_semantics (
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    datum_address TEXT NOT NULL,
    policy TEXT NOT NULL,
    semantic_hash TEXT NOT NULL,
    hyphae_hash TEXT NOT NULL,
    hyphae_chain_json TEXT NOT NULL,
    local_references_json TEXT NOT NULL,
    warnings_json TEXT NOT NULL,
    updated_at_unix_ms INTEGER NOT NULL,
    PRIMARY KEY (tenant_id, document_id, datum_address),
    FOREIGN KEY (tenant_id, document_id)
        REFERENCES datum_document_semantics(tenant_id, document_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS audit_records_recorded_at_idx
ON audit_records(recorded_at_unix_ms DESC, record_id DESC);

CREATE INDEX IF NOT EXISTS datum_row_semantics_document_idx
ON datum_row_semantics(tenant_id, document_id);

CREATE TABLE IF NOT EXISTS directive_context_snapshots (
    context_id TEXT PRIMARY KEY,
    portal_instance_id TEXT NOT NULL,
    tool_id TEXT NOT NULL,
    hyphae_hash TEXT NOT NULL DEFAULT '',
    version_hash TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL,
    updated_at_unix_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS directive_context_events (
    event_id TEXT PRIMARY KEY,
    context_id TEXT NOT NULL,
    portal_instance_id TEXT NOT NULL,
    tool_id TEXT NOT NULL,
    event_kind TEXT NOT NULL,
    hyphae_hash TEXT NOT NULL DEFAULT '',
    version_hash TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    recorded_at_unix_ms INTEGER NOT NULL,
    FOREIGN KEY (context_id)
        REFERENCES directive_context_snapshots(context_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS directive_context_snapshots_lookup_idx
ON directive_context_snapshots(portal_instance_id, tool_id, hyphae_hash, version_hash, updated_at_unix_ms DESC);

CREATE INDEX IF NOT EXISTS directive_context_events_lookup_idx
ON directive_context_events(portal_instance_id, tool_id, context_id, recorded_at_unix_ms DESC);
"""


def _db_path(value: str | Path) -> Path:
    return Path(value)


def dumps_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def loads_json(value: str) -> Any:
    return json.loads(value)


def connect_sqlite(db_file: str | Path) -> sqlite3.Connection:
    path = _db_path(db_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.executescript(SCHEMA_SQL)
    return connection


@contextmanager
def open_sqlite(db_file: str | Path):
    connection = connect_sqlite(db_file)
    try:
        yield connection
    finally:
        connection.close()
