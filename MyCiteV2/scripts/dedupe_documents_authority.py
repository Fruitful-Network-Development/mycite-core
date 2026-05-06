"""Deduplicate ``documents`` authority rows sharing the same ``legacy_alias``.

For each `(tenant_id, legacy_alias)` duplicate set, retain one row: prefer version_hash
matching ``datum_document_semantics.version_hash`` for that legacy identifier, else newest
`(created_at, id)`. Dry-run prints decisions; `--apply` executes ``DELETE``.

Usage::

    python -m MyCiteV2.scripts.dedupe_documents_authority \\
        --db /srv/mycite-state/instances/fnd/private/mos_authority.sqlite3 \\
        --evidence-jsonl /srv/agentic/evidence/logs/documents-dedupe.ndjson \\
        [--apply]
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


def _pick_keeper(rows: list, semantics_hash: str) -> object:
    """``rows``: sqlite Rows for duplicate ``documents``; match ``semantics_hash`` normalized."""

    def rank(r: object) -> tuple[int, int, int]:
        doc_h = _norm_version_hash(r["version_hash"])
        sem_h = semantics_hash or ""
        prefer = 0 if doc_h and sem_h and doc_h == sem_h else 1
        return (prefer, -int(r["created_at"]), -int(r["id"]))

    return sorted(rows, key=rank)[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument(
        "--evidence-jsonl",
        type=Path,
        default=None,
        help="Append one JSON object per removed row / decision (newline-delimited)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete duplicates (default dry-run)",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"missing-db {db_path}", file=sys.stderr)
        return 2

    evidence_path = Path(args.evidence_jsonl) if args.evidence_jsonl else None
    if evidence_path:
        evidence_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(_maintenance_conn(db_path)) as connection:
        dups = connection.execute(
            """
            SELECT tenant_id, legacy_alias, COUNT(*) AS c
            FROM documents
            WHERE legacy_alias IS NOT NULL AND trim(legacy_alias) != ''
            GROUP BY tenant_id, legacy_alias
            HAVING c > 1
            """
        ).fetchall()

        if not dups:
            print("documents-dedupe: no duplicate (tenant_id, legacy_alias) groups")
            return 0

        for group in dups:
            tenant_id = str(group["tenant_id"]).strip()
            legacy_alias = str(group["legacy_alias"]).strip()
            rows = connection.execute(
                """
                SELECT id, tenant_id, document_id, legacy_alias, version_hash, created_at
                FROM documents
                WHERE tenant_id = ? AND legacy_alias = ?
                ORDER BY created_at DESC, id DESC
                """,
                (tenant_id, legacy_alias),
            ).fetchall()
            sem_row = connection.execute(
                """
                SELECT version_hash FROM datum_document_semantics
                WHERE tenant_id = ? AND document_id = ?
                """,
                (tenant_id, legacy_alias),
            ).fetchone()
            sem_h = "" if sem_row is None else _norm_version_hash(sem_row["version_hash"])
            keeper = _pick_keeper(list(rows), sem_h)
            keep_id = int(keeper["id"])
            for r in rows:
                rid = int(r["id"])
                if rid == keep_id:
                    continue
                rec = {
                    "kind": "documents_dedupe_remove",
                    "ts_unix_ms": _utc_ms(),
                    "dry_run": not args.apply,
                    "tenant_id": tenant_id,
                    "legacy_alias": legacy_alias,
                    "removed_id": rid,
                    "removed_document_id": str(r["document_id"]),
                    "keeper_id": keep_id,
                    "keeper_document_id": str(keeper["document_id"]),
                    "preferred_version_match": sem_h != "",
                }
                print(json.dumps(rec, separators=(",", ":"), sort_keys=True))
                if evidence_path:
                    with evidence_path.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(rec, separators=(",", ":"), sort_keys=True) + "\n")

                if args.apply:
                    connection.execute("DELETE FROM documents WHERE id = ?", (rid,))

            if args.apply:
                connection.commit()

    print("documents-dedupe: finished", "applied" if args.apply else "(dry-run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
