"""Bootstrap the FND-CSM sandbox anchor in the MOS authority database.

Idempotent: if an anchor for sandbox=``fnd_csm`` already exists for the
target tenant, the script reports it and exits without writing.

Usage::

    python -m MyCiteV2.scripts.bootstrap_fnd_csm_anchor \
        --authority-db /srv/mycite-state/instances/fnd/private/mos_authority.sqlite3 \
        --tenant-id fnd \
        --msn-id 3-2-3-17-77-1-6-4-1-4

The anchor mirrors the AGRO-ERP anchor's primitive layer (rows ``0-0-1``
through ``0-0-11``), defining the SAMRAS unit primitives that any
sandbox source document references via the ``json-file-unit`` (``0-0-11``).

Subsequent FND-CSM datum documents (e.g. the newsletter contact log
datum, contracted in ``docs/contracts/fnd_newsletter_contact_log_datum.md``)
will be added by the template-driven scaffold action; their reference
rows can be appended to this anchor retroactively.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.document_naming import format_canonical_document_id
from MyCiteV2.packages.core.mss import compute_mss_hash
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)


FND_CSM_SANDBOX = "fnd_csm"
ANCHOR_NAME = "anchor"
DEFAULT_TENANT_ID = "fnd"
DEFAULT_MSN_ID = "3-2-3-17-77-1-6-4-1-4"

PRIMITIVE_ROWS: tuple[tuple[str, str], ...] = (
    ("0-0-1", "time-ordinal-position"),
    ("0-0-2", "time-incramental-unit"),
    ("0-0-3", "spacial-ordinal-position"),
    ("0-0-4", "spacial-incramental-unit"),
    ("0-0-5", "nominal-ordinal-position"),
    ("0-0-6", "nominal-incramental-unit"),
    ("0-0-7", "mass-ordinal-position"),
    ("0-0-8", "miu"),
    ("0-0-9", "fiat-currency-unit"),
    ("0-0-10", "photon-particle-unit"),
    ("0-0-11", "json-file-unit"),
)


def _build_anchor_rows() -> tuple[AuthoritativeDatumDocumentRow, ...]:
    return tuple(
        AuthoritativeDatumDocumentRow(
            datum_address=address,
            raw=[[address, "~", "0-0-0"], [label]],
        )
        for address, label in PRIMITIVE_ROWS
    )


def _existing_anchor(
    catalog: AuthoritativeDatumDocumentCatalogResult,
) -> AuthoritativeDatumDocument | None:
    for document in catalog.documents:
        if not document.is_anchor:
            continue
        if document.document_id.startswith(f"lv.") and f".{FND_CSM_SANDBOX}." in document.document_id:
            return document
    return None


def _format_relative_path(msn_id: str) -> str:
    return f"sandbox/fnd-csm/tool.{msn_id}.fnd-csm.json"


def _format_document_name(msn_id: str) -> str:
    return f"tool.{msn_id}.fnd-csm.json"


def bootstrap_anchor(
    *,
    authority_db: Path,
    tenant_id: str,
    msn_id: str,
    dry_run: bool = False,
) -> dict[str, str]:
    if not authority_db.exists():
        raise SystemExit(f"authority db does not exist: {authority_db}")

    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=True)
    catalog = store.read_authoritative_datum_documents(
        AuthoritativeDatumDocumentRequest(tenant_id=tenant_id)
    )
    existing = _existing_anchor(catalog)
    if existing is not None:
        return {
            "status": "exists",
            "document_id": existing.document_id,
            "row_count": str(existing.row_count),
        }

    rows = _build_anchor_rows()
    # Build a candidate document with a placeholder hash so we can compute the
    # canonical hash; then re-build with the real document_id.
    placeholder_hash = "0" * 64
    placeholder_id = format_canonical_document_id(
        prefix="lv",
        msn_id=msn_id,
        sandbox=FND_CSM_SANDBOX,
        name=ANCHOR_NAME,
        version_hash=placeholder_hash,
    )
    candidate = AuthoritativeDatumDocument(
        document_id=placeholder_id,
        source_kind="sandbox_source",
        document_name=_format_document_name(msn_id),
        relative_path=_format_relative_path(msn_id),
        canonical_name=ANCHOR_NAME,
        tool_id=FND_CSM_SANDBOX,
        is_anchor=True,
        rows=rows,
    )
    identity = compute_mss_hash(candidate)
    real_hash = identity["version_hash"]
    if real_hash.startswith("sha256:"):
        real_hash = real_hash[len("sha256:") :]
    real_id = format_canonical_document_id(
        prefix="lv",
        msn_id=msn_id,
        sandbox=FND_CSM_SANDBOX,
        name=ANCHOR_NAME,
        version_hash=real_hash,
    )
    final_document = AuthoritativeDatumDocument(
        document_id=real_id,
        source_kind="sandbox_source",
        document_name=_format_document_name(msn_id),
        relative_path=_format_relative_path(msn_id),
        canonical_name=ANCHOR_NAME,
        tool_id=FND_CSM_SANDBOX,
        is_anchor=True,
        rows=rows,
    )

    if dry_run:
        return {
            "status": "dry_run",
            "document_id": real_id,
            "row_count": str(len(rows)),
        }

    next_documents = tuple(catalog.documents) + (final_document,)
    next_catalog = AuthoritativeDatumDocumentCatalogResult(
        tenant_id=catalog.tenant_id,
        documents=next_documents,
        source_files=dict(catalog.source_files),
        readiness_status=dict(catalog.readiness_status),
        warnings=tuple(catalog.warnings),
    )
    store.store_authoritative_catalog(next_catalog)
    return {
        "status": "created",
        "document_id": real_id,
        "row_count": str(len(rows)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--authority-db",
        type=Path,
        required=True,
        help="Path to mos_authority.sqlite3",
    )
    parser.add_argument(
        "--tenant-id",
        default=DEFAULT_TENANT_ID,
        help=f"Catalog tenant id (default: {DEFAULT_TENANT_ID!r})",
    )
    parser.add_argument(
        "--msn-id",
        default=DEFAULT_MSN_ID,
        help=f"FND portal MSN id (default: {DEFAULT_MSN_ID!r})",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    result = bootstrap_anchor(
        authority_db=args.authority_db,
        tenant_id=args.tenant_id,
        msn_id=args.msn_id,
        dry_run=args.dry_run,
    )
    print(f"status={result['status']}")
    print(f"document_id={result['document_id']}")
    print(f"row_count={result['row_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
