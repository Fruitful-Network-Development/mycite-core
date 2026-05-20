"""Drop the ``documents.legacy_alias`` column from the MOS authority DB.

Scheduled for execution on **2026-06-05**, the documented end of the
one-cycle compatibility window opened by the 2026-05-05 canonical-id
migration (see
``docs/contracts/mos_authority_enforcement.md#legacy-alias-retirement-schedule``).

Preconditions (the script fails fast if violated):

- Every row in ``datum_document_semantics`` and ``datum_row_semantics``
  must use a canonical ``lv.``/``stl.``/``cptr.`` ``document_id``. No
  pre-cutover ``sandbox:`` or ``system:`` primary keys are allowed.
- Every ``documents`` row must have a non-NULL canonical ``document_id``.
- The dual-lookup ``OR legacy_alias = ?`` paths in
  ``packages/adapters/sql/datum_store.py`` must already be retired
  (no-op verifier: the script doesn't enforce this directly, but the
  test ``test_no_legacy_compatibility_document_keys_remain_as_primary_ids``
  in ``tests/unit/test_mos_program_closure.py`` does — run pytest first).

What it does:

1. Verifies the preconditions above.
2. Inside a single transaction:
   - Creates a new ``documents_new`` table without the ``legacy_alias``
     column (otherwise schema-identical).
   - Copies every row, preserving id ordering.
   - Drops the old ``documents`` table.
   - Renames ``documents_new`` to ``documents``.
   - Recreates the unique index on ``document_id``.

The script is **idempotent**: if the column is already gone, it reports
``status=already_retired`` and exits 0.

Usage::

    python -m MyCiteV2.scripts.drop_legacy_alias_column \\
        --authority-db /srv/webapps/mycite/fnd/private/mos_authority.sqlite3

Pass ``--dry-run`` to verify preconditions without writing.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _column_names(connection: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]


def _check_preconditions(connection: sqlite3.Connection) -> list[str]:
    errors: list[str] = []
    cur = connection.cursor()

    legacy_dds = cur.execute(
        "SELECT COUNT(*) FROM datum_document_semantics "
        "WHERE document_id LIKE 'sandbox:%' OR document_id LIKE 'system:%'"
    ).fetchone()[0]
    if legacy_dds:
        errors.append(
            f"datum_document_semantics has {legacy_dds} rows with legacy primary IDs"
        )

    legacy_drs = cur.execute(
        "SELECT COUNT(DISTINCT document_id) FROM datum_row_semantics "
        "WHERE document_id LIKE 'sandbox:%' OR document_id LIKE 'system:%'"
    ).fetchone()[0]
    if legacy_drs:
        errors.append(
            f"datum_row_semantics has {legacy_drs} documents with legacy primary IDs"
        )

    null_canonical = cur.execute(
        "SELECT COUNT(*) FROM documents WHERE document_id IS NULL OR document_id = ''"
    ).fetchone()[0]
    if null_canonical:
        errors.append(f"documents has {null_canonical} rows with NULL/empty document_id")

    return errors


def drop_legacy_alias(
    *,
    authority_db: Path,
    dry_run: bool,
) -> dict[str, str | int]:
    if not authority_db.exists():
        raise SystemExit(f"authority db missing: {authority_db}")
    connection = sqlite3.connect(authority_db)
    try:
        columns = _column_names(connection, "documents")
        if "legacy_alias" not in columns:
            return {"status": "already_retired", "rows_copied": 0}

        errors = _check_preconditions(connection)
        if errors:
            for line in errors:
                print(f"ERROR: {line}", file=sys.stderr)
            raise SystemExit(
                "preconditions not satisfied; re-key legacy primary IDs first"
            )

        row_count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        if dry_run:
            return {"status": "dry_run", "rows_to_copy": row_count}

        connection.execute("BEGIN")
        connection.execute("""
            CREATE TABLE documents_new (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id       TEXT    NOT NULL,
                document_id     TEXT    NOT NULL UNIQUE,
                prefix          TEXT    NOT NULL CHECK (prefix IN ('lv','stl','cptr')),
                msn_id          TEXT    NOT NULL,
                sandbox         TEXT,
                name            TEXT    NOT NULL,
                version_hash    TEXT    NOT NULL,
                is_anchor       INTEGER NOT NULL DEFAULT 0,
                origin          TEXT    NOT NULL DEFAULT 'local' CHECK (origin IN ('local','foreign')),
                created_at      INTEGER NOT NULL
            )
        """)
        connection.execute("""
            INSERT INTO documents_new (
                id, tenant_id, document_id, prefix, msn_id, sandbox, name,
                version_hash, is_anchor, origin, created_at
            )
            SELECT
                id, tenant_id, document_id, prefix, msn_id, sandbox, name,
                version_hash, is_anchor, origin, created_at
            FROM documents
            ORDER BY id
        """)
        connection.execute("DROP TABLE documents")
        connection.execute("ALTER TABLE documents_new RENAME TO documents")
        # The UNIQUE(document_id) constraint above recreates the unique index
        # automatically. Add any other indexes the original schema relied on
        # here if needed in the future.
        connection.commit()

        # Sanity: count must match
        new_count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        if new_count != row_count:
            raise SystemExit(
                f"row count mismatch after rename: expected {row_count}, got {new_count}"
            )
        post_columns = _column_names(connection, "documents")
        if "legacy_alias" in post_columns:
            raise SystemExit("legacy_alias column still present after migration")
        return {"status": "dropped", "rows_copied": new_count}
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-db", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    result = drop_legacy_alias(authority_db=args.authority_db, dry_run=args.dry_run)
    for key, value in result.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
