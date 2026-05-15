"""MOS-backed newsletter contact log adapter.

Implements the contact-log half of
:class:`MyCiteV2.packages.ports.aws_csm_newsletter.AwsCsmNewsletterStatePort`
on top of the SQLite-backed authoritative datum store.

Data shape on disk (per the v2 contract at
``docs/contracts/fnd_newsletter_contact_log_datum.md``):

* Header rows at layer 0 — schema/domain/msn_id/updated_at.
* One row per subscriber at layer 1, address ``1-0-<n>``. Raw payload
  is ``[[address, "~", "0-0-11"], {magnitudes}]`` where magnitudes
  carry both ASCII forms (``email_ascii``, ``name_ascii``) and
  bacillete-encoded binary forms (``email_binary``, ``name_binary``)
  plus their ``*_confirmed`` booleans.

The legacy filesystem callsites (signup endpoint, dispatcher subscriber
enumeration, etc.) read and write the older ``contact_log.v1`` shape:
``{"contacts": [{"email", "name", "subscribed", ...}]}``. This adapter
translates between the v2 row shape and that legacy shape so the
callsites stay unchanged — the only thing that flips is *which* port
implementation is wired in.

Profile, secret, and bootstrap methods delegate to a wrapped
:class:`AwsCsmNewsletterStatePort` (the legacy filesystem adapter).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.datum_templates.bacillete import (
    encode_email_bacillete,
    encode_name_bacillete,
)
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.state_machine.portal_shell import FND_CSM_SANDBOX_TOKEN

V2_SCHEMA = "mycite.v2.datum.fnd.newsletter.contact_log.v2"
SANDBOX = FND_CSM_SANDBOX_TOKEN
DEFAULT_TENANT_ID = "fnd"
DEFAULT_MSN_ID = "3-2-3-17-77-1-6-4-1-4"


def _domain_token(domain: str) -> str:
    return (domain or "").strip().lower().replace(".", "_").replace("-", "_")


def _canonical_name_for(domain: str) -> str:
    return f"fnd_newsletter_contact_log_{_domain_token(domain)}"


def _utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return _as_text(value).lower() in {"1", "true", "yes"}


def _as_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


class MosDatumNewsletterContactLogAdapter:
    """Read/write the contact log half of :class:`AwsCsmNewsletterStatePort`
    against a MOS authority database.

    Other port methods (profile, secret, bootstrap) raise
    :class:`NotImplementedError`. Use
    :class:`CompositeAwsCsmNewsletterStateAdapter` to combine this with
    a legacy filesystem adapter for the non-contact-log methods.
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

    # -- contact-log methods ----------------------------------------------

    def load_contact_log(self, *, domain: str) -> dict[str, Any]:
        document = self._find_document(domain=domain)
        if document is None:
            return {}
        contacts: list[dict[str, Any]] = []
        for row in document.rows:
            magnitudes = self._row_magnitudes(row)
            if magnitudes is None:
                continue
            email = _as_text(magnitudes.get("email_ascii"))
            if not email:
                continue
            # Phase 15b: hydrate first/middle/last from the new magnitudes
            # when present; otherwise back-fill from the legacy single
            # ``name_ascii`` so callers that still read `name` continue
            # to work while the migration runs.
            first_name = _as_text(magnitudes.get("first_name_ascii"))
            middle_name = _as_text(magnitudes.get("middle_name_ascii"))
            last_name = _as_text(magnitudes.get("last_name_ascii"))
            composed = _as_text(magnitudes.get("name_ascii"))
            if not (first_name or middle_name or last_name) and composed:
                first_name, middle_name, last_name = (
                    MosDatumNewsletterContactLogAdapter._split_legacy_name(composed)
                )
            name = composed or " ".join(t for t in (first_name, middle_name, last_name) if t)
            # Phase 16a: phone / zip / signup_date. signup_date falls
            # back to the date prefix of created_at for rows imported
            # before the magnitude landed.
            created_at = _as_text(magnitudes.get("created_at"))
            signup_date = _as_text(magnitudes.get("signup_date"))
            if not signup_date and created_at and len(created_at) >= 10:
                signup_date = created_at[:10]
            contacts.append(
                {
                    "email": email,
                    "name": name,
                    "first_name": first_name,
                    "middle_name": middle_name,
                    "last_name": last_name,
                    "phone": _as_text(magnitudes.get("phone_ascii")),
                    "zip": _as_text(magnitudes.get("zip_ascii")),
                    "signup_date": signup_date,
                    "subscribed": _as_bool(magnitudes.get("subscribed")),
                    "source": _as_text(magnitudes.get("source")),
                    "last_newsletter_sent_at": _as_text(
                        magnitudes.get("last_newsletter_sent_at")
                    ),
                    "send_count": _as_int(magnitudes.get("send_count")),
                    "created_at": created_at,
                    "name_binary": _as_text(magnitudes.get("name_binary")),
                    "name_confirmed": _as_bool(magnitudes.get("name_confirmed")),
                    "email_binary": _as_text(magnitudes.get("email_binary")),
                    "email_confirmed": _as_bool(magnitudes.get("email_confirmed")),
                }
            )
        header = self._header_field_map(document.rows)
        return {
            "schema": V2_SCHEMA,
            "domain": header.get("domain", domain),
            "msn_id": header.get("msn_id", self._msn_id),
            "contacts": contacts,
            "dispatches": [],
            "updated_at": header.get("updated_at", ""),
        }

    def save_contact_log(self, *, domain: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = dict(payload if isinstance(payload, dict) else {})
        contacts_in = list(body.get("contacts") or [])
        msn_id = _as_text(body.get("msn_id")) or self._msn_id
        updated_at = _utc_now_iso()
        store = SqliteSystemDatumStoreAdapter(self._authority_db_file, allow_legacy_writes=True)
        existing = self._find_document(domain=domain)
        canonical_name = (
            existing.canonical_name if existing is not None else _canonical_name_for(domain)
        )
        document_name = (
            existing.document_name
            if existing is not None
            else f"fnd-newsletter-contact-log.{domain}.json"
        )
        relative_path = (
            existing.relative_path
            if existing is not None
            else f"sandbox/fnd-csm/{document_name}"
        )

        rows: list[AuthoritativeDatumDocumentRow] = [
            AuthoritativeDatumDocumentRow(datum_address="0-0-1", raw=V2_SCHEMA),
            AuthoritativeDatumDocumentRow(datum_address="0-0-2", raw=domain),
            AuthoritativeDatumDocumentRow(datum_address="0-0-3", raw=msn_id),
            AuthoritativeDatumDocumentRow(datum_address="0-0-4", raw=updated_at),
        ]
        for index, contact in enumerate(contacts_in, start=1):
            magnitudes = self._magnitudes_from_contact(contact)
            address = f"1-0-{index}"
            rows.append(
                AuthoritativeDatumDocumentRow(
                    datum_address=address,
                    raw=[[address, "~", "0-0-11"], magnitudes],
                )
            )

        # Build a candidate doc to compute the canonical hash, then mint
        # the final document_id with that hash.
        from MyCiteV2.packages.core.document_naming import format_canonical_document_id
        from MyCiteV2.packages.core.mss import compute_mss_hash

        placeholder_id = format_canonical_document_id(
            prefix="lv", msn_id=msn_id, sandbox=SANDBOX,
            name=canonical_name, version_hash="0" * 64,
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
            prefix="lv", msn_id=msn_id, sandbox=SANDBOX,
            name=canonical_name, version_hash=real_hash,
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

        # Persist via the efficient single-doc replacement path. Reads
        # the catalog (cached), swaps just our doc, rewrites the snapshot
        # row, and re-encodes semantics ONLY for the changed doc. Cost
        # is O(rows_in_doc) instead of O(all_rows_in_catalog) — the
        # difference between ~30 ms and ~3-5 s for the trapp contact log
        # (1172 rows over a 124-doc cts_gis catalog).
        prior_document_id = (
            existing.document_id if existing is not None else None
        )
        store.replace_single_document_efficient(
            tenant_id=self._tenant_id,
            prior_document_id=prior_document_id,
            updated_document=final_document,
        )
        return self.load_contact_log(domain=domain)

    # -- internals --------------------------------------------------------

    def _find_document(self, *, domain: str) -> AuthoritativeDatumDocument | None:
        store = SqliteSystemDatumStoreAdapter(self._authority_db_file)
        catalog = store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id=self._tenant_id)
        )
        canonical_name = _canonical_name_for(domain)
        for document in catalog.documents:
            if document.canonical_name == canonical_name and f".{SANDBOX}." in document.document_id:
                return document
        return None

    @staticmethod
    def _row_magnitudes(row: AuthoritativeDatumDocumentRow) -> dict[str, Any] | None:
        raw = row.raw
        if isinstance(raw, dict):
            return dict(raw)
        if isinstance(raw, list) and len(raw) >= 2 and isinstance(raw[1], dict):
            return dict(raw[1])
        return None

    @staticmethod
    def _header_field_map(
        rows: tuple[AuthoritativeDatumDocumentRow, ...],
    ) -> dict[str, str]:
        out: dict[str, str] = {}
        mapping = {
            "0-0-1": "schema",
            "0-0-2": "domain",
            "0-0-3": "msn_id",
            "0-0-4": "updated_at",
        }
        for row in rows:
            field = mapping.get(row.datum_address)
            if field is not None:
                out[field] = _as_text(row.raw)
        return out

    @staticmethod
    def _split_legacy_name(name: str) -> tuple[str, str, str]:
        """Decompose a single ``name`` token into (first, middle, last).

        Back-compat helper for callers that still pass a single ``name``
        field (e.g. the public /__fnd/newsletter/subscribe endpoint
        before Phase 15b). Conventions:

          * 1 token  → first only
          * 2 tokens → first + last
          * 3+ tokens → first + middle (joined) + last
        """
        tokens = [t for t in _as_text(name).split() if t]
        if not tokens:
            return "", "", ""
        if len(tokens) == 1:
            return tokens[0], "", ""
        if len(tokens) == 2:
            return tokens[0], "", tokens[1]
        return tokens[0], " ".join(tokens[1:-1]), tokens[-1]

    @staticmethod
    def _magnitudes_from_contact(contact: Any) -> dict[str, Any]:
        if not isinstance(contact, dict):
            return {}
        email_ascii = _as_text(contact.get("email_ascii") or contact.get("email")).lower()

        # Phase 15b: prefer the split first/middle/last fields. Fall back
        # to splitting a legacy single ``name`` for callers that haven't
        # migrated. ``name_ascii`` is always composed from the split for
        # the bacillete encoder + legacy readers.
        first_name = _as_text(contact.get("first_name_ascii") or contact.get("first_name"))
        middle_name = _as_text(contact.get("middle_name_ascii") or contact.get("middle_name"))
        last_name = _as_text(contact.get("last_name_ascii") or contact.get("last_name"))
        if not (first_name or middle_name or last_name):
            legacy_name = _as_text(contact.get("name_ascii") or contact.get("name"))
            first_name, middle_name, last_name = (
                MosDatumNewsletterContactLogAdapter._split_legacy_name(legacy_name)
            )
        name_ascii = " ".join(t for t in (first_name, middle_name, last_name) if t)

        email_binary, email_confirmed = encode_email_bacillete(email_ascii)
        name_binary, name_confirmed = encode_name_bacillete(name_ascii)
        # Phase 16a: capture phone / zip / signup_date. signup_date
        # defaults to today's date if neither it nor created_at is
        # supplied — every new subscriber lands with a date the
        # operator can sort + filter on.
        phone_ascii = _as_text(contact.get("phone_ascii") or contact.get("phone"))
        zip_ascii = _as_text(contact.get("zip_ascii") or contact.get("zip"))
        signup_date = _as_text(contact.get("signup_date"))
        if not signup_date:
            created_at = _as_text(contact.get("created_at"))
            if created_at and len(created_at) >= 10:
                signup_date = created_at[:10]  # ISO-8601 date prefix
        magnitudes: dict[str, Any] = {
            "email_ascii": email_ascii,
            "email_binary": email_binary,
            "email_confirmed": email_confirmed,
            "name_ascii": name_ascii,
            "name_binary": name_binary,
            "name_confirmed": name_confirmed,
            "first_name_ascii": first_name,
            "middle_name_ascii": middle_name,
            "last_name_ascii": last_name,
            "phone_ascii": phone_ascii,
            "zip_ascii": zip_ascii,
            "signup_date": signup_date,
            "subscribed": _as_bool(contact.get("subscribed")),
            "source": _as_text(contact.get("source")),
            "last_newsletter_sent_at": _as_text(contact.get("last_newsletter_sent_at")),
            "send_count": _as_int(contact.get("send_count")),
        }
        if contact.get("created_at"):
            magnitudes["created_at"] = _as_text(contact.get("created_at"))
        return magnitudes


class CompositeAwsCsmNewsletterStateAdapter:
    """:class:`AwsCsmNewsletterStatePort` whose contact-log methods route to
    a MOS adapter and whose profile/secret/bootstrap methods route to a
    wrapped legacy filesystem adapter.

    Single drop-in replacement for ``FilesystemAwsCsmNewsletterStateAdapter``
    at every callsite.
    """

    def __init__(
        self,
        *,
        private_dir: str | Path,
        authority_db_file: str | Path,
        tenant_id: str = DEFAULT_TENANT_ID,
        msn_id: str = DEFAULT_MSN_ID,
    ) -> None:
        from MyCiteV2.packages.adapters.filesystem import (
            FilesystemAwsCsmNewsletterStateAdapter,
        )

        self._fs = FilesystemAwsCsmNewsletterStateAdapter(private_dir)
        self._mos = MosDatumNewsletterContactLogAdapter(
            authority_db_file=authority_db_file,
            tenant_id=tenant_id,
            msn_id=msn_id,
        )

    # contact-log → MOS
    def load_contact_log(self, *, domain: str) -> dict[str, Any]:
        return self._mos.load_contact_log(domain=domain)

    def save_contact_log(self, *, domain: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._mos.save_contact_log(domain=domain, payload=payload)

    # everything else → filesystem (delegated by attribute access)
    def __getattr__(self, name: str) -> Any:
        return getattr(self._fs, name)


__all__ = [
    "V2_SCHEMA",
    "CompositeAwsCsmNewsletterStateAdapter",
    "MosDatumNewsletterContactLogAdapter",
]
