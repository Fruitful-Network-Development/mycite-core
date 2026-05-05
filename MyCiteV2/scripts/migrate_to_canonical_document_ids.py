"""Idempotent migration of legacy document identifiers to canonical MOS form.

Reads every row in ``datum_document_semantics`` for a given SQLite authority
database, derives the canonical ``lv./stl./cptr.`` identifier via
``derive_canonical_id_from_legacy`` (using each portal's ``msn_id`` from
``private/config.json`` plus the existing ``version_hash``), and inserts the
result into the ``documents`` table with ``legacy_alias`` set to the original
identifier.

The script is idempotent: repeated runs either leave canonical rows alone
(``ON CONFLICT(document_id) DO NOTHING``) or replace stale entries when the
version_hash changes. It does not mutate ``datum_document_semantics``.

Usage::

    python -m MyCiteV2.scripts.migrate_to_canonical_document_ids \\
        --db /srv/mycite-state/instances/fnd/private/mos_authority.sqlite3 \\
        --msn-id 3-2-3-17-77-1-6-4-1-4
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql._sqlite import open_sqlite
from MyCiteV2.packages.core.document_naming import (
    CanonicalNameError,
    derive_canonical_id_from_legacy,
    is_canonical_document_id,
    parse_canonical_document_id,
)


_CANONICAL_REGEX = re.compile(
    r"^(lv|stl|cptr)\.[^.]+(\.[^.]+)?\.[^.]+\.[a-f0-9]{64}$"
)


def _msn_id_from_private_dir(private_dir: Path) -> str:
    config_file = private_dir / "config.json"
    if not config_file.exists():
        return ""
    try:
        payload = json.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(payload.get("msn_id") or "").strip()


def _now_unix_ms() -> int:
    return int(time.time() * 1000)


def _classify_legacy_id(legacy_id: str) -> tuple[str, str | None, str, bool]:
    """Return (prefix, sandbox, name, is_anchor) for a legacy id."""

    parsed = parse_canonical_document_id(
        derive_canonical_id_from_legacy(
            legacy_id,
            msn_id="X",  # placeholder; we only need prefix/sandbox/name structure
            version_hash="0" * 64,
        )
    )
    is_anchor = parsed.prefix == "lv" and parsed.name in ("anchor", "anthology")
    return parsed.prefix, parsed.sandbox, parsed.name, is_anchor


def migrate(
    *,
    db_file: Path,
    msn_id: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the canonical-id migration on the given authority database."""

    if not msn_id:
        raise ValueError("msn_id is required for canonical id derivation")

    rows_seen = 0
    rows_canonicalized = 0
    rows_already_canonical = 0
    rows_unsupported: list[str] = []
    rows_inserted = 0
    rows_replaced = 0

    with open_sqlite(db_file) as connection:
        cursor = connection.execute(
            "SELECT tenant_id, document_id, version_hash FROM datum_document_semantics"
        )
        legacy_rows = list(cursor.fetchall())

        for row in legacy_rows:
            rows_seen += 1
            tenant_id = str(row["tenant_id"]).strip()
            legacy_id = str(row["document_id"]).strip()
            version_hash = str(row["version_hash"]).strip().lower()
            if not version_hash:
                rows_unsupported.append(legacy_id)
                continue

            if is_canonical_document_id(legacy_id):
                rows_already_canonical += 1
                canonical_id = legacy_id
                try:
                    parsed = parse_canonical_document_id(canonical_id)
                except CanonicalNameError:
                    rows_unsupported.append(legacy_id)
                    continue
                prefix = parsed.prefix
                sandbox = parsed.sandbox
                name = parsed.name
                is_anchor = prefix == "lv" and name in ("anchor", "anthology")
                legacy_alias: str | None = None
            else:
                try:
                    canonical_id = derive_canonical_id_from_legacy(
                        legacy_id,
                        msn_id=msn_id,
                        version_hash=version_hash,
                    )
                except CanonicalNameError:
                    rows_unsupported.append(legacy_id)
                    continue
                prefix, sandbox, name, is_anchor = _classify_legacy_id(legacy_id)
                legacy_alias = legacy_id
                rows_canonicalized += 1

            if not _CANONICAL_REGEX.fullmatch(canonical_id):
                rows_unsupported.append(legacy_id)
                continue

            if dry_run:
                continue

            existing = connection.execute(
                "SELECT id, version_hash FROM documents WHERE document_id = ?",
                (canonical_id,),
            ).fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO documents ("
                    "tenant_id, document_id, prefix, msn_id, sandbox, name, "
                    "version_hash, is_anchor, origin, legacy_alias, created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'local', ?, ?)",
                    (
                        tenant_id,
                        canonical_id,
                        prefix,
                        msn_id,
                        sandbox,
                        name,
                        version_hash,
                        1 if is_anchor else 0,
                        legacy_alias,
                        _now_unix_ms(),
                    ),
                )
                rows_inserted += 1
            elif str(existing["version_hash"]).strip().lower() != version_hash:
                connection.execute(
                    "UPDATE documents SET version_hash = ?, legacy_alias = COALESCE(legacy_alias, ?) "
                    "WHERE document_id = ?",
                    (version_hash, legacy_alias, canonical_id),
                )
                rows_replaced += 1

        if not dry_run:
            connection.commit()

    return {
        "rows_seen": rows_seen,
        "rows_canonicalized": rows_canonicalized,
        "rows_already_canonical": rows_already_canonical,
        "rows_inserted": rows_inserted,
        "rows_replaced": rows_replaced,
        "rows_unsupported": rows_unsupported,
        "dry_run": dry_run,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        required=True,
        type=Path,
        help="Path to the MOS authority SQLite database.",
    )
    parser.add_argument(
        "--msn-id",
        default="",
        help="Portal msn_id used for canonical id derivation. "
        "Falls back to ``msn_id`` in ``private/config.json`` next to the db.",
    )
    parser.add_argument(
        "--private-dir",
        default="",
        type=Path,
        help="Optional explicit private dir (containing config.json).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute canonical ids but do not insert any rows.",
    )
    args = parser.parse_args(argv)

    msn_id = (args.msn_id or "").strip()
    if not msn_id:
        candidate_dirs = []
        if args.private_dir:
            candidate_dirs.append(args.private_dir)
        candidate_dirs.append(args.db.parent)
        for candidate in candidate_dirs:
            msn_id = _msn_id_from_private_dir(Path(candidate))
            if msn_id:
                break

    if not msn_id:
        parser.error(
            "Could not resolve msn_id. Pass --msn-id or place config.json next to the db."
        )

    summary = migrate(db_file=Path(args.db), msn_id=msn_id, dry_run=bool(args.dry_run))
    json.dump(summary, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
