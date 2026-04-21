from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from MyCiteV2.packages.adapters.filesystem import FilesystemSystemDatumStoreAdapter
from MyCiteV2.packages.adapters.sql._sqlite import dumps_json, loads_json, open_sqlite
from MyCiteV2.packages.adapters.sql.datum_semantics import (
    build_document_semantics,
    preview_document_delete as preview_document_delete_mutation,
    preview_document_insert as preview_document_insert_mutation,
    preview_document_move as preview_document_move_mutation,
)
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentPort,
    AuthoritativeDatumDocumentRequest,
    PublicationProfileBasicsWritePort,
    PublicationProfileBasicsWriteRequest,
    PublicationProfileBasicsWriteResult,
    PublicationTenantSummaryPort,
    PublicationTenantSummaryRequest,
    PublicationTenantSummaryResult,
    SystemDatumResourceRow,
    SystemDatumStorePort,
    SystemDatumStoreRequest,
    SystemDatumWorkbenchResult,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _workbench_from_payload(payload: dict[str, object]) -> SystemDatumWorkbenchResult:
    rows = payload.get("rows") or ()
    warnings = payload.get("warnings") or ()
    return SystemDatumWorkbenchResult(
        tenant_id=payload.get("tenant_id"),
        rows=tuple(
            row if isinstance(row, SystemDatumResourceRow) else SystemDatumResourceRow.from_dict(row)
            for row in rows
        ),
        source_files=payload.get("source_files") or {},
        materialization_status=payload.get("materialization_status") or {},
        warnings=tuple(str(item) for item in warnings),
    )


class SqliteSystemDatumStoreAdapter(
    SystemDatumStorePort,
    AuthoritativeDatumDocumentPort,
    PublicationTenantSummaryPort,
    PublicationProfileBasicsWritePort,
):
    def __init__(
        self,
        db_file: str | Path,
        *,
        clock: Callable[[], int] | None = None,
    ) -> None:
        self._db_file = Path(db_file)
        self._clock = clock or (lambda: int(time.time() * 1000))

    def _connect(self):
        return open_sqlite(self._db_file)

    def has_authoritative_catalog(self, tenant_id: str) -> bool:
        token = _as_text(tenant_id).lower()
        if not token:
            return False
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM authoritative_catalog_snapshots WHERE tenant_id = ?",
                (token,),
            ).fetchone()
        return row is not None

    def has_system_workbench(self, tenant_id: str) -> bool:
        token = _as_text(tenant_id).lower()
        if not token:
            return False
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM system_workbench_snapshots WHERE tenant_id = ?",
                (token,),
            ).fetchone()
        return row is not None

    def has_publication_summary(self, tenant_id: str, tenant_domain: str) -> bool:
        normalized_request = PublicationTenantSummaryRequest(
            tenant_id=tenant_id,
            tenant_domain=tenant_domain,
        )
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM publication_summary_snapshots WHERE tenant_id = ? AND tenant_domain = ?",
                (normalized_request.tenant_id, normalized_request.tenant_domain),
            ).fetchone()
        return row is not None

    def store_authoritative_catalog(self, result: AuthoritativeDatumDocumentCatalogResult) -> None:
        normalized = (
            result
            if isinstance(result, AuthoritativeDatumDocumentCatalogResult)
            else AuthoritativeDatumDocumentCatalogResult.from_dict(result)
        )
        updated_at = self._clock()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO authoritative_catalog_snapshots (tenant_id, payload_json, updated_at_unix_ms)
                VALUES (?, ?, ?)
                ON CONFLICT(tenant_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at_unix_ms = excluded.updated_at_unix_ms
                """,
                (normalized.tenant_id, dumps_json(normalized.to_dict()), updated_at),
            )
            connection.execute("DELETE FROM datum_row_semantics WHERE tenant_id = ?", (normalized.tenant_id,))
            connection.execute("DELETE FROM datum_document_semantics WHERE tenant_id = ?", (normalized.tenant_id,))
            for document in normalized.documents:
                semantics = build_document_semantics(document)
                connection.execute(
                    """
                    INSERT INTO datum_document_semantics (
                        tenant_id,
                        document_id,
                        policy,
                        version_hash,
                        canonical_payload_json,
                        updated_at_unix_ms
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized.tenant_id,
                        document.document_id,
                        semantics["document"]["policy"],
                        semantics["document"]["version_hash"],
                        dumps_json(semantics["document"]["canonical_payload"]),
                        updated_at,
                    ),
                )
                for datum_address, row_semantics in semantics["rows"].items():
                    connection.execute(
                        """
                        INSERT INTO datum_row_semantics (
                            tenant_id,
                            document_id,
                            datum_address,
                            policy,
                            semantic_hash,
                            hyphae_hash,
                            hyphae_chain_json,
                            local_references_json,
                            warnings_json,
                            updated_at_unix_ms
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            normalized.tenant_id,
                            document.document_id,
                            datum_address,
                            row_semantics["policy"],
                            row_semantics["semantic_hash"],
                            row_semantics["hyphae_hash"],
                            dumps_json(row_semantics["hyphae_chain"]),
                            dumps_json(row_semantics["local_references"]),
                            dumps_json(row_semantics["warnings"]),
                            updated_at,
                        ),
                    )
            connection.commit()

    def store_system_workbench(self, result: SystemDatumWorkbenchResult) -> None:
        normalized = (
            result
            if isinstance(result, SystemDatumWorkbenchResult)
            else SystemDatumWorkbenchResult.from_dict(result)
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO system_workbench_snapshots (tenant_id, payload_json, updated_at_unix_ms)
                VALUES (?, ?, ?)
                ON CONFLICT(tenant_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at_unix_ms = excluded.updated_at_unix_ms
                """,
                (normalized.tenant_id, dumps_json(normalized.to_dict()), self._clock()),
            )
            connection.commit()

    def store_publication_summary(self, result: PublicationTenantSummaryResult, *, tenant_id: str, tenant_domain: str) -> None:
        normalized_request = PublicationTenantSummaryRequest(tenant_id=tenant_id, tenant_domain=tenant_domain)
        normalized_result = (
            result
            if isinstance(result, PublicationTenantSummaryResult)
            else PublicationTenantSummaryResult.from_dict(result)
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO publication_summary_snapshots (tenant_id, tenant_domain, payload_json, updated_at_unix_ms)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(tenant_id, tenant_domain) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at_unix_ms = excluded.updated_at_unix_ms
                """,
                (
                    normalized_request.tenant_id,
                    normalized_request.tenant_domain,
                    dumps_json(normalized_result.to_dict()),
                    self._clock(),
                ),
            )
            connection.commit()

    def bootstrap_from_filesystem(
        self,
        *,
        data_dir: str | Path,
        public_dir: str | Path | None,
        tenant_id: str,
        tenant_domain: str | None = None,
    ) -> None:
        filesystem = FilesystemSystemDatumStoreAdapter(Path(data_dir), public_dir=public_dir)
        normalized_tenant_id = _as_text(tenant_id).lower()
        self.store_authoritative_catalog(
            filesystem.read_authoritative_datum_documents(
                AuthoritativeDatumDocumentRequest(tenant_id=normalized_tenant_id)
            )
        )
        self.store_system_workbench(
            filesystem.read_system_resource_workbench(
                SystemDatumStoreRequest(tenant_id=normalized_tenant_id)
            )
        )
        if tenant_domain:
            self.store_publication_summary(
                filesystem.read_publication_tenant_summary(
                    PublicationTenantSummaryRequest(
                        tenant_id=normalized_tenant_id,
                        tenant_domain=tenant_domain,
                    )
                ),
                tenant_id=normalized_tenant_id,
                tenant_domain=tenant_domain,
            )

    def read_authoritative_datum_documents(
        self,
        request: AuthoritativeDatumDocumentRequest,
    ) -> AuthoritativeDatumDocumentCatalogResult:
        normalized_request = (
            request
            if isinstance(request, AuthoritativeDatumDocumentRequest)
            else AuthoritativeDatumDocumentRequest.from_dict(request)
        )
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM authoritative_catalog_snapshots WHERE tenant_id = ?",
                (normalized_request.tenant_id,),
            ).fetchone()
        if row is None:
            return AuthoritativeDatumDocumentCatalogResult(
                tenant_id=normalized_request.tenant_id,
                documents=(),
                source_files={},
                readiness_status={"authoritative_catalog": "missing"},
                warnings=("sql_authoritative_catalog_missing",),
            )
        return AuthoritativeDatumDocumentCatalogResult.from_dict(loads_json(row["payload_json"]))

    def read_system_resource_workbench(self, request: SystemDatumStoreRequest) -> SystemDatumWorkbenchResult:
        normalized_request = (
            request if isinstance(request, SystemDatumStoreRequest) else SystemDatumStoreRequest.from_dict(request)
        )
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM system_workbench_snapshots WHERE tenant_id = ?",
                (normalized_request.tenant_id,),
            ).fetchone()
        if row is None:
            return SystemDatumWorkbenchResult(
                tenant_id=normalized_request.tenant_id,
                rows=(),
                source_files={},
                materialization_status={"canonical_source": "missing", "authoritative_catalog": "missing"},
                warnings=("sql_system_workbench_missing",),
            )
        return _workbench_from_payload(loads_json(row["payload_json"]))

    def read_publication_tenant_summary(
        self,
        request: PublicationTenantSummaryRequest,
    ) -> PublicationTenantSummaryResult:
        normalized_request = (
            request
            if isinstance(request, PublicationTenantSummaryRequest)
            else PublicationTenantSummaryRequest.from_dict(request)
        )
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM publication_summary_snapshots
                WHERE tenant_id = ? AND tenant_domain = ?
                """,
                (normalized_request.tenant_id, normalized_request.tenant_domain),
            ).fetchone()
        if row is None:
            return PublicationTenantSummaryResult(
                source=None,
                resolution_status={"publication_summary": "missing"},
                warnings=("sql_publication_summary_missing",),
            )
        return PublicationTenantSummaryResult.from_dict(loads_json(row["payload_json"]))

    def read_document_version_identity(self, *, tenant_id: str, document_id: str) -> dict[str, Any] | None:
        normalized_request = AuthoritativeDatumDocumentRequest(tenant_id=tenant_id)
        document_token = _as_text(document_id)
        if not document_token:
            raise ValueError("document_id is required")
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT policy, version_hash, canonical_payload_json
                FROM datum_document_semantics
                WHERE tenant_id = ? AND document_id = ?
                """,
                (normalized_request.tenant_id, document_token),
            ).fetchone()
        if row is None:
            return None
        return {
            "policy": row["policy"],
            "version_hash": row["version_hash"],
            "canonical_payload": loads_json(row["canonical_payload_json"]),
        }

    def read_datum_semantic_identity(
        self,
        *,
        tenant_id: str,
        document_id: str,
        datum_address: str,
    ) -> dict[str, Any] | None:
        normalized_request = AuthoritativeDatumDocumentRequest(tenant_id=tenant_id)
        document_token = _as_text(document_id)
        datum_token = _as_text(datum_address)
        if not document_token:
            raise ValueError("document_id is required")
        if not datum_token:
            raise ValueError("datum_address is required")
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT policy, semantic_hash, hyphae_hash, hyphae_chain_json, local_references_json, warnings_json
                FROM datum_row_semantics
                WHERE tenant_id = ? AND document_id = ? AND datum_address = ?
                """,
                (normalized_request.tenant_id, document_token, datum_token),
            ).fetchone()
        if row is None:
            return None
        return {
            "policy": row["policy"],
            "semantic_hash": row["semantic_hash"],
            "hyphae_hash": row["hyphae_hash"],
            "hyphae_chain": loads_json(row["hyphae_chain_json"]),
            "local_references": loads_json(row["local_references_json"]),
            "warnings": loads_json(row["warnings_json"]),
        }

    def _catalog_with_document(
        self,
        *,
        tenant_id: str,
        document_id: str,
    ) -> tuple[AuthoritativeDatumDocumentCatalogResult, AuthoritativeDatumDocument]:
        catalog = self.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=tenant_id))
        for document in catalog.documents:
            if document.document_id == _as_text(document_id):
                return catalog, document
        raise ValueError("authoritative_document_missing")

    def _persist_updated_document(
        self,
        *,
        tenant_id: str,
        document_id: str,
        updated_document: AuthoritativeDatumDocument,
    ) -> AuthoritativeDatumDocumentCatalogResult:
        catalog = self.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=tenant_id))
        documents: list[AuthoritativeDatumDocument] = []
        found = False
        for document in catalog.documents:
            if document.document_id == _as_text(document_id):
                documents.append(updated_document)
                found = True
            else:
                documents.append(document)
        if not found:
            raise ValueError("authoritative_document_missing")
        next_catalog = AuthoritativeDatumDocumentCatalogResult(
            tenant_id=catalog.tenant_id,
            documents=tuple(documents),
            source_files=dict(catalog.source_files),
            readiness_status=dict(catalog.readiness_status),
            warnings=tuple(catalog.warnings),
        )
        self.store_authoritative_catalog(next_catalog)
        return self.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=tenant_id))

    def preview_document_insert(
        self,
        *,
        tenant_id: str,
        document_id: str,
        target_address: str,
        raw: Any,
    ) -> dict[str, Any]:
        _, document = self._catalog_with_document(tenant_id=tenant_id, document_id=document_id)
        preview = preview_document_insert_mutation(document, target_address=target_address, raw=raw)
        preview["updated_document"] = preview["updated_document"].to_dict()
        return preview

    def apply_document_insert(
        self,
        *,
        tenant_id: str,
        document_id: str,
        target_address: str,
        raw: Any,
    ) -> dict[str, Any]:
        _, document = self._catalog_with_document(tenant_id=tenant_id, document_id=document_id)
        preview = preview_document_insert_mutation(document, target_address=target_address, raw=raw)
        persisted_catalog = self._persist_updated_document(
            tenant_id=tenant_id,
            document_id=document_id,
            updated_document=preview["updated_document"],
        )
        latest_identity = self.read_document_version_identity(tenant_id=tenant_id, document_id=document_id)
        preview["updated_document"] = next(
            item.to_dict() for item in persisted_catalog.documents if item.document_id == _as_text(document_id)
        )
        preview["persisted_version_hash"] = latest_identity["version_hash"] if latest_identity else ""
        return preview

    def preview_document_delete(
        self,
        *,
        tenant_id: str,
        document_id: str,
        target_address: str,
    ) -> dict[str, Any]:
        _, document = self._catalog_with_document(tenant_id=tenant_id, document_id=document_id)
        preview = preview_document_delete_mutation(document, target_address=target_address)
        preview["updated_document"] = preview["updated_document"].to_dict()
        return preview

    def apply_document_delete(
        self,
        *,
        tenant_id: str,
        document_id: str,
        target_address: str,
    ) -> dict[str, Any]:
        _, document = self._catalog_with_document(tenant_id=tenant_id, document_id=document_id)
        preview = preview_document_delete_mutation(document, target_address=target_address)
        persisted_catalog = self._persist_updated_document(
            tenant_id=tenant_id,
            document_id=document_id,
            updated_document=preview["updated_document"],
        )
        latest_identity = self.read_document_version_identity(tenant_id=tenant_id, document_id=document_id)
        preview["updated_document"] = next(
            item.to_dict() for item in persisted_catalog.documents if item.document_id == _as_text(document_id)
        )
        preview["persisted_version_hash"] = latest_identity["version_hash"] if latest_identity else ""
        return preview

    def preview_document_move(
        self,
        *,
        tenant_id: str,
        document_id: str,
        source_address: str,
        destination_address: str,
    ) -> dict[str, Any]:
        _, document = self._catalog_with_document(tenant_id=tenant_id, document_id=document_id)
        preview = preview_document_move_mutation(
            document,
            source_address=source_address,
            destination_address=destination_address,
        )
        preview["updated_document"] = preview["updated_document"].to_dict()
        return preview

    def apply_document_move(
        self,
        *,
        tenant_id: str,
        document_id: str,
        source_address: str,
        destination_address: str,
    ) -> dict[str, Any]:
        _, document = self._catalog_with_document(tenant_id=tenant_id, document_id=document_id)
        preview = preview_document_move_mutation(
            document,
            source_address=source_address,
            destination_address=destination_address,
        )
        persisted_catalog = self._persist_updated_document(
            tenant_id=tenant_id,
            document_id=document_id,
            updated_document=preview["updated_document"],
        )
        latest_identity = self.read_document_version_identity(tenant_id=tenant_id, document_id=document_id)
        preview["updated_document"] = next(
            item.to_dict() for item in persisted_catalog.documents if item.document_id == _as_text(document_id)
        )
        preview["persisted_version_hash"] = latest_identity["version_hash"] if latest_identity else ""
        return preview

    def write_publication_profile_basics(
        self,
        request: PublicationProfileBasicsWriteRequest,
    ) -> PublicationProfileBasicsWriteResult:
        normalized_request = (
            request
            if isinstance(request, PublicationProfileBasicsWriteRequest)
            else PublicationProfileBasicsWriteRequest.from_dict(request)
        )
        current = self.read_publication_tenant_summary(
            PublicationTenantSummaryRequest(
                tenant_id=normalized_request.tenant_id,
                tenant_domain=normalized_request.tenant_domain,
            )
        )
        if current.source is None:
            raise ValueError("No SQL-backed publication summary exists for the requested tenant domain.")

        next_source = current.source.to_dict()
        tenant_profile = dict(next_source.get("tenant_profile") or {})
        tenant_profile["title"] = normalized_request.profile_title
        tenant_profile["summary"] = normalized_request.profile_summary
        tenant_profile["contact_email"] = normalized_request.contact_email
        tenant_profile["public_website_url"] = normalized_request.public_website_url
        next_source["tenant_profile"] = tenant_profile

        result = PublicationTenantSummaryResult(
            source=next_source,
            resolution_status=dict(current.resolution_status),
            warnings=tuple(current.warnings),
        )
        self.store_publication_summary(
            result,
            tenant_id=normalized_request.tenant_id,
            tenant_domain=normalized_request.tenant_domain,
        )
        confirmed = self.read_publication_tenant_summary(
            PublicationTenantSummaryRequest(
                tenant_id=normalized_request.tenant_id,
                tenant_domain=normalized_request.tenant_domain,
            )
        )
        if confirmed.source is None:
            raise ValueError("SQL publication profile basics read-after-write confirmation failed.")
        return PublicationProfileBasicsWriteResult(
            source=confirmed.source,
            resolution_status=confirmed.resolution_status,
            warnings=confirmed.warnings,
        )
