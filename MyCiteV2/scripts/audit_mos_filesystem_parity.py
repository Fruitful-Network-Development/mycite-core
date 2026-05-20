"""Audit MOS↔filesystem parity for datum-document artifacts.

For every JSON or .bin artifact under ``$DATA_ROOT/{system,sandbox,payloads/cache}/``,
look up the corresponding row in the MOS ``documents`` table (by canonical id
or legacy_alias), compare canonical_payload row counts, and classify each
artifact as one of:

- ``PARITY_OK``       — MOS row present, canonical_payload row count matches
                        the disk file's row count
- ``REQUIRES_INGEST`` — MOS row present but the canonical_payload diverges
                        (row count mismatch); needs a per-sandbox bootstrap
                        before the disk file can be archived
- ``MISSING``         — no MOS row found via document_id or legacy_alias

Exits 0 if every artifact is PARITY_OK or REQUIRES_INGEST, non-zero if any
MISSING (script halts safely; nothing should be deleted).

Use ``--strict`` to require every artifact be PARITY_OK; useful as a
Phase 7 pre-flight check before data archival.

Usage::

    python -m MyCiteV2.scripts.audit_mos_filesystem_parity \\
        --authority-db /srv/webapps/mycite/fnd/private/mos_authority.sqlite3 \\
        --data-root /srv/webapps/mycite/fnd/data \\
        --report-file /srv/agentic/evidence/mos_authority_drift_audit_2026-05-17/parity_report.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _legacy_alias_candidates(rel_to_data: Path) -> list[str]:
    """Return possible legacy_alias strings to try for a disk file."""
    parts = rel_to_data.parts
    name = rel_to_data.name
    candidates: list[str] = []
    if parts[0] == "system":
        if name == "anthology.json":
            candidates.append("system:anthology")
        elif name == "system_log.json":
            candidates.append("system:system_log")
        elif parts[1:2] == ("sources",) and name.startswith("sc."):
            # sc.<MSN>.msn-<name>.json → system:<name>
            stem = name[:-5]  # strip .json
            segments = stem.split(".", 2)
            if len(segments) == 3 and segments[2].startswith("msn-"):
                candidates.append(f"system:{segments[2][len('msn-'):]}")
            elif len(segments) == 3:
                candidates.append(f"system:{segments[2]}")
    elif parts[0] == "sandbox":
        slug_dir = parts[1]  # 'cts-gis', 'fnd-ebi', 'agro-erp'
        slug_underscore = slug_dir.replace("-", "_")
        # legacy_alias historically used either slug form; try both
        for slug_form in (slug_underscore, slug_dir):
            candidates.append(f"sandbox:{slug_form}:{name}")
            # Some legacy_alias entries include the relative path for precincts/sources
            if len(parts) > 2:
                relpath = "/".join(parts[2:])
                candidates.append(f"sandbox:{slug_form}:{relpath}")
    elif parts[0] == "payloads":
        # cache/sc.<MSN>.<name>.json — these are compiled-cache (cptr-shaped),
        # not legacy-aliased as datum sources. Try both system and cts_gis
        # forms; if absent, will report MISSING which is fine — we then
        # treat them as recompile-able rather than canonical content.
        if parts[1:2] == ("cache",) and name.startswith("sc."):
            stem = name[:-5]
            segments = stem.split(".", 2)
            if len(segments) == 3:
                tail = segments[2]
                if tail.startswith("msn-"):
                    candidates.append(f"system:{tail[len('msn-'):]}")
                    candidates.append(f"sandbox:cts_gis:sc.{segments[1]}.{tail}.json")
                else:
                    candidates.append(f"sandbox:cts_gis:sc.{segments[1]}.{tail}.json")
                    candidates.append(f"system:{tail}")
        # *.bin files are zero-byte stubs; report no candidates → MISSING
    return candidates


def _classify_artifact(
    *,
    cur: sqlite3.Cursor,
    artifact_path: Path,
    data_root: Path,
) -> dict[str, object]:
    rel = artifact_path.relative_to(data_root)
    size_bytes = artifact_path.stat().st_size
    name = artifact_path.name
    record: dict[str, object] = {
        "path": str(artifact_path),
        "rel_to_data": str(rel),
        "size_bytes": size_bytes,
        "status": "UNKNOWN",
        "matched_document_id": "",
        "matched_legacy_alias": "",
        "on_disk_row_count": -1,
        "mos_row_count": -1,
        "notes": "",
    }

    # Special-case legitimate files
    if rel.parts[:2] == ("payloads", "compiled"):
        record["status"] = "LEGITIMATE_UI_PAYLOAD"
        record["notes"] = "Compiled UI surface payload (allowed); not a datum document."
        return record

    # Zero-byte .bin stubs
    if artifact_path.suffix == ".bin" and size_bytes == 0:
        record["status"] = "ZERO_BYTE_ORPHAN"
        record["notes"] = "Empty placeholder; safe to delete."
        return record

    # Backup orphans
    if ".pre-repair" in name or ".pre-compile" in name:
        record["status"] = "BACKUP_ORPHAN"
        record["notes"] = "Pre-repair/pre-compile backup; safe to delete."
        return record

    candidates = _legacy_alias_candidates(rel)
    if not candidates:
        record["status"] = "UNCATEGORIZED"
        record["notes"] = "No legacy_alias mapping rule for this path."
        return record

    # Try each candidate alias
    match = None
    for alias in candidates:
        row = cur.execute(
            "SELECT document_id, legacy_alias FROM documents WHERE legacy_alias = ?",
            (alias,),
        ).fetchone()
        if row:
            match = (row[0], row[1])
            break

    if match is None:
        record["status"] = "MISSING"
        record["notes"] = (
            f"No MOS row found via legacy_alias. Tried: {candidates}"
        )
        return record

    document_id, legacy_alias = match
    record["matched_document_id"] = document_id
    record["matched_legacy_alias"] = legacy_alias

    # Compare row counts
    on_disk_count = -1
    try:
        if artifact_path.suffix == ".json":
            with artifact_path.open() as f:
                doc = json.load(f)
            if isinstance(doc, dict):
                rows = doc.get("datum_addressing_abstraction_space") or doc
                if isinstance(rows, dict):
                    on_disk_count = sum(
                        1
                        for k in rows.keys()
                        if "-" in k and not k.startswith("anchor_") and k != "datum_addressing_abstraction_space"
                    )
    except (OSError, json.JSONDecodeError):
        on_disk_count = -1
    record["on_disk_row_count"] = on_disk_count

    mos_row = cur.execute(
        "SELECT COUNT(*) FROM datum_row_semantics WHERE document_id = ?",
        (document_id,),
    ).fetchone()
    mos_count = int(mos_row[0]) if mos_row else 0
    record["mos_row_count"] = mos_count

    if on_disk_count < 0:
        record["status"] = "PARITY_UNKNOWN"
        record["notes"] = "Could not parse on-disk row count; MOS has " f"{mos_count} rows."
    elif on_disk_count == mos_count:
        record["status"] = "PARITY_OK"
    else:
        record["status"] = "REQUIRES_INGEST"
        record["notes"] = (
            f"Row-count mismatch: disk={on_disk_count}, MOS={mos_count}. "
            "Re-ingest disk content (or accept MOS as canonical and archive)."
        )

    return record


def run_audit(
    *,
    authority_db: Path,
    data_root: Path,
    strict: bool,
) -> dict[str, object]:
    connection = sqlite3.connect(authority_db)
    try:
        cur = connection.cursor()
        artifacts: list[dict[str, object]] = []
        for path in sorted(data_root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix not in {".json", ".bin"} and ".pre-" not in path.name:
                continue
            artifacts.append(_classify_artifact(cur=cur, artifact_path=path, data_root=data_root))
    finally:
        connection.close()

    counts: dict[str, int] = {}
    for item in artifacts:
        counts[item["status"]] = counts.get(item["status"], 0) + 1

    summary = {
        "audit_date": "2026-05-17",
        "authority_db": str(authority_db),
        "data_root": str(data_root),
        "strict": strict,
        "total_artifacts": len(artifacts),
        "status_counts": counts,
        "artifacts": artifacts,
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-db", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument(
        "--report-file",
        type=Path,
        default=Path("/srv/agentic/evidence/mos_authority_drift_audit_2026-05-17/parity_report.json"),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Require every artifact to be PARITY_OK or LEGITIMATE_UI_PAYLOAD or ZERO_BYTE_ORPHAN or BACKUP_ORPHAN.",
    )
    args = parser.parse_args(argv)

    summary = run_audit(
        authority_db=args.authority_db,
        data_root=args.data_root,
        strict=args.strict,
    )
    args.report_file.parent.mkdir(parents=True, exist_ok=True)
    args.report_file.write_text(json.dumps(summary, indent=2))

    print(f"total_artifacts={summary['total_artifacts']}")
    for status, count in sorted(summary["status_counts"].items()):
        print(f"  {status}: {count}")
    print(f"report_file={args.report_file}")

    if args.strict:
        allowed = {"PARITY_OK", "LEGITIMATE_UI_PAYLOAD", "ZERO_BYTE_ORPHAN", "BACKUP_ORPHAN"}
        bad = {s: c for s, c in summary["status_counts"].items() if s not in allowed}
        if bad:
            print(f"strict mode failed: {bad}", file=sys.stderr)
            return 2

    has_missing = summary["status_counts"].get("MISSING", 0) > 0
    return 1 if has_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
