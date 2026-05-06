"""Migrate ``datum_*_semantics`` primary keys from legacy document ids to canonical ``lv.*``.

Assumes deduplicated ``documents`` rows ``(tenant_id, legacy_alias)``. For each
``datum_document_semantics`` row whose ``document_id`` is not canonical, resolves the
matching canonical ``documents.document_id``, copies document semantics under the canonical
key (if absent), rewires ``datum_row_semantics`` FK, and deletes the legacy semantics row.

Idempotent per legacy id: skips when no legacy semantics row remains.

Usage::

    python -m MyCiteV2.scripts.migrate_semantics_to_canonical_document_ids \\
        --db /srv/mycite-state/instances/fnd/private/mos_authority.sqlite3 \\
        --evidence-jsonl /srv/agentic/evidence/logs/semantics-migrate.ndjson \\
        [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.document_naming import is_canonical_document_id


def _maintenance_conn(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def _norm_version_hash(value: object) -> str:
    token = str(value or "").strip().lower()
    if token.startswith("sha256:"):
        token = token.split(":", 1)[1]
    return token


def _utc_ms() -> int:
    return int(time.time() * 1000)


def _resolve_canonical_document_id(connection: sqlite3.Connection, tenant_id: str, legacy_id: str) -> str | None:
    sem = connection.execute(
        "SELECT version_hash FROM datum_document_semantics WHERE tenant_id = ? AND document_id = ?",
        (tenant_id, legacy_id),
    ).fetchone()
    semantics_vh = "" if sem is None else _norm_version_hash(sem["version_hash"])
    rows = connection.execute(
        """
        SELECT document_id, version_hash, created_at, id
        FROM documents AS d
        WHERE d.tenant_id = ?
          AND (d.legacy_alias = ? OR d.document_id = ?)
        """,
        (tenant_id, legacy_id, legacy_id),
    ).fetchall()
    if not rows:
        return None

    def rank(r: sqlite3.Row) -> tuple[int, int, int]:
        doc_h = _norm_version_hash(r["version_hash"])
        prefer = 0 if semantics_vh and doc_h == semantics_vh else 1
        return (prefer, -int(r["created_at"]), -int(r["id"]))

    best = sorted(rows, key=rank)[0]
    return str(best["document_id"]).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--evidence-jsonl", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"missing-db {db_path}", file=sys.stderr)
        return 2

    evidence_path = Path(args.evidence_jsonl) if args.evidence_jsonl else None
    if evidence_path:
        evidence_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(_maintenance_conn(db_path)) as connection:
        semantics_rows = connection.execute(
            """
            SELECT tenant_id, document_id, policy, version_hash, canonical_payload_json, updated_at_unix_ms
            FROM datum_document_semantics
            ORDER BY tenant_id, document_id
            """
        ).fetchall()

        migrated = 0
        skipped = 0

        for srow in semantics_rows:
            tenant_id = str(srow["tenant_id"]).strip()
            legacy_doc = str(srow["document_id"]).strip()
            if not legacy_doc or is_canonical_document_id(legacy_doc):
                skipped += 1
                continue

            canonical = _resolve_canonical_document_id(connection, tenant_id, legacy_doc)
            if not canonical:
                msg = json.dumps(
                    {
                        "kind": "semantics_migrate_blocked",
                        "ts_unix_ms": _utc_ms(),
                        "tenant_id": tenant_id,
                        "legacy_document_id": legacy_doc,
                        "reason": "no_canonical_documents_row",
                    },
                    separators=(",", ":"),
                )
                print(msg, file=sys.stderr)
                if evidence_path:
                    with evidence_path.open("a", encoding="utf-8") as fh:
                        fh.write(msg + "\n")
                continue

            if canonical == legacy_doc:
                skipped += 1
                continue

            row_count = connection.execute(
                "SELECT COUNT(*) AS c FROM datum_row_semantics WHERE tenant_id = ? AND document_id = ?",
                (tenant_id, legacy_doc),
            ).fetchone()["c"]

            rec = {
                "kind": "semantics_migrate_plan",
                "ts_unix_ms": _utc_ms(),
                "dry_run": bool(args.dry_run),
                "tenant_id": tenant_id,
                "from_document_id": legacy_doc,
                "to_document_id": canonical,
                "row_semantics_count": int(row_count),
            }
            print(json.dumps(rec, separators=(",", ":"), sort_keys=True))
            if evidence_path:
                with evidence_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, separators=(",", ":"), sort_keys=True) + "\n")

            if args.dry_run:
                continue

            existing_row = connection.execute(
                """
                SELECT version_hash, policy, canonical_payload_json
                FROM datum_document_semantics
                WHERE tenant_id = ? AND document_id = ?
                """,
                (tenant_id, canonical),
            ).fetchone()

            try:
                connection.execute("BEGIN IMMEDIATE")
                if existing_row is None:
                    connection.execute(
                        """
                        INSERT INTO datum_document_semantics (
                            tenant_id, document_id, policy, version_hash, canonical_payload_json, updated_at_unix_ms
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            tenant_id,
                            canonical,
                            srow["policy"],
                            srow["version_hash"],
                            srow["canonical_payload_json"],
                            srow["updated_at_unix_ms"],
                        ),
                    )
                else:
                    if _norm_version_hash(existing_row["version_hash"]) != _norm_version_hash(srow["version_hash"]):
                        raise RuntimeError(
                            "canonical_semantics_version_mismatch "
                            f"tenant={tenant_id} canonical={canonical} "
                            f"existing={existing_row['version_hash']!r} legacy={srow['version_hash']!r}"
                        )
                    if str(existing_row["policy"]) != str(srow["policy"]):
                        raise RuntimeError(
                            f"canonical_semantics_policy_mismatch tenant={tenant_id} canonical={canonical}"
                        )
                    if str(existing_row["canonical_payload_json"]) != str(srow["canonical_payload_json"]):
                        raise RuntimeError(
                            f"canonical_semantics_payload_mismatch tenant={tenant_id} canonical={canonical}"
                        )
                cur = connection.execute(
                    "UPDATE datum_row_semantics SET document_id = ? WHERE tenant_id = ? AND document_id = ?",
                    (canonical, tenant_id, legacy_doc),
                )
                if cur.rowcount != int(row_count):
                    connection.rollback()
                    raise RuntimeError(
                        f"row_semantics_count_mismatch expected={row_count} updated={cur.rowcount} "
                        f"tenant={tenant_id} legacy={legacy_doc}"
                    )
                connection.execute(
                    "DELETE FROM datum_document_semantics WHERE tenant_id = ? AND document_id = ?",
                    (tenant_id, legacy_doc),
                )
                connection.commit()
                migrated += 1
            except Exception as exc:  # noqa: BLE001
                connection.rollback()
                err = json.dumps(
                    {
                        "kind": "semantics_migrate_error",
                        "ts_unix_ms": _utc_ms(),
                        "tenant_id": tenant_id,
                        "legacy_document_id": legacy_doc,
                        "error": str(exc),
                    },
                    separators=(",", ":"),
                )
                print(err, file=sys.stderr)
                if evidence_path:
                    with evidence_path.open("a", encoding="utf-8") as fh:
                        fh.write(err + "\n")
                return 1

    print(
        json.dumps(
            {"kind": "semantics_migrate_summary", "migrated": migrated, "skipped_canonical_or_absent": skipped},
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
