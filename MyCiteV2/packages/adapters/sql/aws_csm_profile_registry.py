"""MOS-backed adapter for AWS-CSM tool profiles + domain records.

The legacy filesystem store at
``<private>/utilities/tools/aws-csm/aws-csm.*.json`` and
``aws-csm-domain.*.json`` keeps per-operator and per-domain JSON
records. This adapter mirrors that registry inside MOS so:

* Workbench-UI can introspect AWS-CSM profile state.
* The Email tab can read profiles without touching the filesystem.
* Future writes can flow through the canonical mutation lifecycle.

Each record becomes one datum document in the ``fnd_csm`` sandbox:

* Header rows at layer 0: ``schema``, ``record_kind`` (``"profile"`` /
  ``"domain"``), ``record_id``, ``tenant_id``, ``updated_at``.
* One row at layer 1 carrying the full record JSON in its ``raw``.

This nested-blob approach is intentional: operator profiles and domain
records are heavily nested config objects, not row-shaped collections.
Putting the whole document on a single row keeps the v1 schema simple
and lossless. Phase E or later can break sections into per-row
magnitudes if needed.

Canonical document names:

* Operator profile: ``aws_csm_profile_<tenant>_<local>``
* Domain record:    ``aws_csm_domain_<tenant>``
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.ports.aws_csm_profile_registry import AwsCsmProfileRegistryPort
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.state_machine.portal_shell import FND_CSM_SANDBOX_TOKEN


PROFILE_SCHEMA = "mycite.v2.datum.aws_csm.operator_profile.v1"
DOMAIN_SCHEMA = "mycite.v2.datum.aws_csm.domain.v1"
SANDBOX = FND_CSM_SANDBOX_TOKEN
DEFAULT_TENANT_ID = "fnd"
DEFAULT_MSN_ID = "3-2-3-17-77-1-6-4-1-4"
PROFILE_NAME_PREFIX = "aws_csm_profile_"
DOMAIN_NAME_PREFIX = "aws_csm_domain_"


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _profile_canonical_name(profile_id: str) -> str:
    token = _as_text(profile_id).lower().replace(".", "_").replace("-", "_")
    if token.startswith("aws_csm_"):
        token = token[len("aws_csm_") :]
    return f"{PROFILE_NAME_PREFIX}{token}"


def _domain_canonical_name(tenant_id: str) -> str:
    return f"{DOMAIN_NAME_PREFIX}{_as_text(tenant_id).lower()}"


class MosDatumAwsCsmProfileAdapter(AwsCsmProfileRegistryPort):
    """MOS-backed twin of :class:`FilesystemAwsCsmToolProfileStore`.

    Implements the operator-profile + domain-record halves of the
    filesystem store's API against the SQLite authority database. Reads
    are cheap; writes go through
    :meth:`SqliteSystemDatumStoreAdapter.replace_single_document_efficient`.
    """

    def __init__(
        self,
        *,
        authority_db_file: str | Path,
        tenant_id: str = DEFAULT_TENANT_ID,
        msn_id: str = DEFAULT_MSN_ID,
    ) -> None:
        self._authority_db_file = Path(authority_db_file)
        self._tenant_id = tenant_id
        self._msn_id = msn_id

    # -- AwsCsmProfileRegistryPort methods --------------------------------

    def list_profiles(self) -> list[dict[str, Any]]:
        return [self._record_from_doc(d) for d in self._docs_named_with(PROFILE_NAME_PREFIX)]

    def list_domains(self) -> list[dict[str, Any]]:
        return [self._record_from_doc(d) for d in self._docs_named_with(DOMAIN_NAME_PREFIX)]

    def load_profile(self, *, tenant_scope_id: str, profile_id: str) -> dict[str, Any] | None:
        canonical = _profile_canonical_name(profile_id)
        doc = self._find_doc(canonical)
        if doc is None:
            return None
        record = self._record_from_doc(doc)
        if not _matches_tenant_scope(record, tenant_scope_id):
            return None
        return record

    def load_domain(self, *, domain: str) -> dict[str, Any] | None:
        target = _as_text(domain).lower()
        for record in self.list_domains():
            identity = _as_dict(record.get("identity"))
            if _as_text(identity.get("domain")).lower() == target:
                return record
        return None

    def resolve_domain_seed(self, *, domain: str) -> dict[str, Any] | None:
        record = self.load_domain(domain=domain)
        if record is None:
            return None
        identity = _as_dict(record.get("identity"))
        ses = _as_dict(record.get("ses"))
        observation = _as_dict(record.get("observation"))
        return {
            "tenant_id": _as_text(identity.get("tenant_id")).lower(),
            "region": _as_text(identity.get("region")) or "us-east-1",
            "provider": {
                "aws_ses_identity_status": _as_text(ses.get("identity_status")),
                "last_checked_at": _as_text(observation.get("last_checked_at")),
            },
            "profile_id": _as_text(identity.get("profile_id")),
        }

    def create_profile(self, *, profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._save_record(
            canonical_name=_profile_canonical_name(profile_id),
            record_kind="profile",
            record_id=profile_id,
            schema=PROFILE_SCHEMA,
            payload=payload,
        )
        return payload

    def save_profile(
        self, *, tenant_scope_id: str, profile_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        # Lighter wrapper for the live tool actions.
        _ = tenant_scope_id
        return self.create_profile(profile_id=profile_id, payload=payload)

    def save_domain(self, *, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._save_record(
            canonical_name=_domain_canonical_name(tenant_id),
            record_kind="domain",
            record_id=f"aws-csm-domain.{tenant_id}",
            schema=DOMAIN_SCHEMA,
            payload=payload,
        )
        return payload

    # -- internals --------------------------------------------------------

    def _docs_named_with(self, prefix: str) -> list[AuthoritativeDatumDocument]:
        store = SqliteSystemDatumStoreAdapter(self._authority_db_file)
        catalog = store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id=self._tenant_id)
        )
        out: list[AuthoritativeDatumDocument] = []
        for doc in catalog.documents:
            if f".{SANDBOX}." not in doc.document_id:
                continue
            if not doc.canonical_name.startswith(prefix):
                continue
            out.append(doc)
        return out

    def _find_doc(self, canonical_name: str) -> AuthoritativeDatumDocument | None:
        store = SqliteSystemDatumStoreAdapter(self._authority_db_file)
        catalog = store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id=self._tenant_id)
        )
        for doc in catalog.documents:
            if doc.canonical_name == canonical_name and f".{SANDBOX}." in doc.document_id:
                return doc
        return None

    @staticmethod
    def _record_from_doc(doc: AuthoritativeDatumDocument) -> dict[str, Any]:
        for row in doc.rows:
            if not row.datum_address.startswith("1-"):
                continue
            raw = row.raw
            if isinstance(raw, dict):
                return dict(raw)
            # SAMRAS row shape: [[address, parent, magnitude], {payload}]
            if isinstance(raw, list) and len(raw) >= 2 and isinstance(raw[1], dict):
                return dict(raw[1])
        return {}

    def _save_record(
        self,
        *,
        canonical_name: str,
        record_kind: str,
        record_id: str,
        schema: str,
        payload: dict[str, Any],
    ) -> None:
        from MyCiteV2.packages.core.document_naming import format_canonical_document_id
        from MyCiteV2.packages.core.mss import compute_mss_hash

        store = SqliteSystemDatumStoreAdapter(self._authority_db_file, allow_legacy_writes=True)
        existing = self._find_doc(canonical_name)
        prior_document_id = existing.document_id if existing is not None else None
        document_name = f"{canonical_name}.json"
        relative_path = f"sandbox/fnd-csm/{document_name}"
        updated_at = _utc_now_iso()
        tenant_id_value = _as_text(_as_dict(payload.get("identity")).get("tenant_id"))

        rows: list[AuthoritativeDatumDocumentRow] = [
            AuthoritativeDatumDocumentRow(datum_address="0-0-1", raw=schema),
            AuthoritativeDatumDocumentRow(datum_address="0-0-2", raw=record_kind),
            AuthoritativeDatumDocumentRow(datum_address="0-0-3", raw=record_id),
            AuthoritativeDatumDocumentRow(datum_address="0-0-4", raw=tenant_id_value),
            AuthoritativeDatumDocumentRow(datum_address="0-0-5", raw=updated_at),
            AuthoritativeDatumDocumentRow(
                datum_address="1-0-1",
                raw=[["1-0-1", "~", "0-0-11"], dict(payload)],
            ),
        ]

        placeholder_id = format_canonical_document_id(
            prefix="lv",
            msn_id=self._msn_id,
            sandbox=SANDBOX,
            name=canonical_name,
            version_hash="0" * 64,
        )
        candidate = AuthoritativeDatumDocument(
            document_id=placeholder_id,
            source_kind="sandbox_source",
            document_name=document_name,
            relative_path=relative_path,
            canonical_name=canonical_name,
            tool_id=SANDBOX,
            is_anchor=False,
            rows=tuple(rows),
        )
        identity = compute_mss_hash(candidate)
        real_hash = identity["version_hash"]
        if real_hash.startswith("sha256:"):
            real_hash = real_hash[len("sha256:") :]
        real_id = format_canonical_document_id(
            prefix="lv",
            msn_id=self._msn_id,
            sandbox=SANDBOX,
            name=canonical_name,
            version_hash=real_hash,
        )
        final_document = AuthoritativeDatumDocument(
            document_id=real_id,
            source_kind="sandbox_source",
            document_name=document_name,
            relative_path=relative_path,
            canonical_name=canonical_name,
            tool_id=SANDBOX,
            is_anchor=False,
            rows=tuple(rows),
        )
        store.replace_single_document_efficient(
            tenant_id=self._tenant_id,
            prior_document_id=prior_document_id,
            updated_document=final_document,
        )


def _matches_tenant_scope(record: dict[str, Any], tenant_scope_id: str) -> bool:
    identity = _as_dict(record.get("identity"))
    requested = _as_text(tenant_scope_id).lower()
    candidates = {
        _as_text(identity.get("tenant_id")).lower(),
        _as_text(identity.get("domain")).lower(),
        _as_text(identity.get("profile_id")).lower(),
    }
    return bool(requested and requested in candidates)


__all__ = [
    "DOMAIN_SCHEMA",
    "MosDatumAwsCsmProfileAdapter",
    "PROFILE_SCHEMA",
]
