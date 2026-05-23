"""One-shot purge: remove any analytics-summary datum rows from MOS.

Background: the `MosDatumAnalyticsSummaryAdapter` was retired in
2026-05 when the analytics storage doctrine was clarified — raw events
live in append-only NDJSON under
`<private>/utilities/tools/analytics/`, and derived insights are
computed on demand. No analytics state belongs in
`mos_authority.sqlite3` any more. See
`docs/contracts/analytics_event_schema.md` and the "Allowed:
append-only observation logs" section of
`docs/contracts/mos_authority_enforcement.md`.

This script deletes:
  * Any `documents` row whose `name` starts with `fnd_analytics_summary_`.
  * The matching rows in `datum_document_semantics` and
    `datum_row_semantics` (cascade by `document_id`).

It is idempotent: subsequent runs are a no-op once the rows are gone.

Usage:
    python -m MyCiteV2.scripts.drop_mos_analytics_tables \\
        --authority-db /srv/webapps/mycite/fnd/private/mos_authority.sqlite3 \\
        [--dry-run]
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def _matching_document_ids(con: sqlite3.Connection) -> list[str]:
    cur = con.execute(
        "SELECT document_id FROM documents "
        "WHERE name LIKE 'fnd_analytics_summary_%'"
    )
    return [row[0] for row in cur.fetchall()]


def run(authority_db: Path, *, dry_run: bool) -> dict[str, int]:
    if not authority_db.exists():
        raise SystemExit(f"authority DB not found: {authority_db}")
    con = sqlite3.connect(authority_db)
    try:
        ids = _matching_document_ids(con)
        if not ids:
            return {"matched": 0, "removed_documents": 0, "removed_semantics": 0, "removed_rows": 0}

        if dry_run:
            return {"matched": len(ids), "removed_documents": 0, "removed_semantics": 0, "removed_rows": 0}

        placeholders = ",".join(["?"] * len(ids))

        removed_rows = con.execute(
            f"DELETE FROM datum_row_semantics WHERE document_id IN ({placeholders})",
            ids,
        ).rowcount
        removed_semantics = con.execute(
            f"DELETE FROM datum_document_semantics WHERE document_id IN ({placeholders})",
            ids,
        ).rowcount
        removed_documents = con.execute(
            f"DELETE FROM documents WHERE document_id IN ({placeholders})",
            ids,
        ).rowcount
        con.commit()
        return {
            "matched": len(ids),
            "removed_documents": removed_documents,
            "removed_semantics": removed_semantics,
            "removed_rows": removed_rows,
        }
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--authority-db",
        required=True,
        type=Path,
        help="Path to mos_authority.sqlite3.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts without deleting.",
    )
    args = parser.parse_args(argv)
    result = run(args.authority_db, dry_run=args.dry_run)
    if result["matched"] == 0:
        print("nothing to do — no fnd_analytics_summary_* documents in MOS")
    else:
        prefix = "would remove" if args.dry_run else "removed"
        print(
            f"{prefix} {result['matched']} document(s); "
            f"{result['removed_documents']} doc rows, "
            f"{result['removed_semantics']} semantic rows, "
            f"{result['removed_rows']} datum_row rows"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
