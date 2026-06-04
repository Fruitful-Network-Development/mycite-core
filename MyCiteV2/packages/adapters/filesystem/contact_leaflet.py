"""Per-entity YAML contact-leaflet roster store.

The newsletter CONTACT ROSTER (the ``contacts[]`` list — every person who has
signed up, donated, or used a Connect form) lives here as one YAML "leaflet"
per grantee ENTITY:

    <webapps_root>/clients/_shared/site-core/contacts/
        0000-00-00.record-data.<entity>.contacts.yaml

Envelope schema ``mycite.site_core.contact_record.v1``. DISPATCH-SEND HISTORY
(the ``dispatches[]`` list) is NOT here — it stays in the legacy per-domain JSON
contact log (see ``newsletter_state.py``). This module is roster-only.

PII NOTE: the *.contacts.yaml files hold personal data and are runtime,
untracked artifacts. Never commit a real leaflet.

The store is keyed by ENTITY (e.g. ``trapp_family_farm``); one entity may own
several domains (CVCC owns two), so every contact row carries a ``domain``
field recording which site the contact came in through. ``load_roster`` /
``save_roster`` work in terms of entity; helpers also accept a domain and
resolve it to the owning entity via :func:`entity_for_domain`.

All writes are atomic (temp file in the same dir + ``os.replace``) so a torn
write can never read back as an empty roster and silently drop every contact.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

_log = logging.getLogger("mycite.portal_host")

CONTACT_RECORD_SCHEMA = "mycite.site_core.contact_record.v1"
_ACCEPTED_CONTACT_RECORD_SCHEMAS = frozenset({CONTACT_RECORD_SCHEMA})

# Roster-scoped fields persisted for every contact. Additional canonical
# contact-entry fields (created_at / updated_at / subscribed_at / the
# connect-form subject+message + dispatch tracking) are preserved verbatim
# when present so a round-trip never drops data — these are just the fields
# the roster is guaranteed to carry.
ROSTER_FIELDS: tuple[str, ...] = (
    "email",
    "first_name",
    "middle_name",
    "last_name",
    "phone",
    "zip",
    "organization",
    "source",
    "subscribed",
    "signup_date",
    "domain",
)

# Explicit domain -> entity slug map. The grantee profiles don't carry the
# entity slug, so this map is authoritative; :func:`entity_for_domain` consults
# the grantee loader first only to confirm a domain is owned, then falls back
# here. Multiple domains may map to ONE entity (CVCC owns two).
_DOMAIN_TO_ENTITY: dict[str, str] = {
    "fruitfulnetworkdevelopment.com": "fruitful_network_development_llc",
    "cuyahogavalleycountrysideconservancy.org": "cuyahoga_valley_countryside_conservancy_inc",
    "cvccboard.org": "cuyahoga_valley_countryside_conservancy_inc",
    "brockspressurewashing.com": "brocks_pressure_washing",
    "trappfamilyfarm.com": "trapp_family_farm",
}


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalized_domain(value: object) -> str:
    token = _as_text(value).lower()
    if token.startswith("www."):
        token = token[4:]
    return token


def _entity_slug(value: object) -> str:
    """Sanitize an entity slug to a filesystem-safe lowercase token."""
    token = _as_text(value).lower()
    out = []
    for ch in token:
        if ch.isalnum() or ch in "_-":
            out.append(ch)
        elif ch in " .":
            out.append("_")
    return "".join(out).strip("_")


def entity_for_domain(domain: str, *, private_dir: str | Path | None = None) -> str:
    """Resolve a domain to its owning entity slug.

    Uses the explicit :data:`_DOMAIN_TO_ENTITY` map (authoritative — the entity
    slugs aren't stored on the grantee profiles). When the domain is unknown,
    derives a deterministic slug from the domain itself so the store never
    silently routes an unmapped grantee's contacts to the wrong leaflet.

    ``private_dir`` is accepted for forward-compatibility (a future grantee
    profile may carry the slug); it is currently unused for resolution.
    """
    token = normalized_domain(domain)
    if token in _DOMAIN_TO_ENTITY:
        return _DOMAIN_TO_ENTITY[token]
    # Unknown domain: derive a stable slug from the domain (strip TLD dot to _).
    slug = _entity_slug(token)
    return slug or "unknown_entity"


def _contacts_dir_for(private_dir: str | Path, webapps_root: str | Path | None) -> Path:
    """Resolve the contacts-leaflet directory from a private_dir.

    Live layout is ``<webapps_root>/mycite/<instance>/private``; the leaflets
    live at ``<webapps_root>/clients/_shared/site-core/contacts``. When an
    explicit ``webapps_root`` is given (and the live layout matches), use it.

    For test/dev layouts that don't match the live tail, the webapps root is
    ambiguous, so we anchor the contacts dir UNDER ``private_dir`` itself. That
    keeps the leaflet inside the same sandbox the caller passed (so a route
    adapter and a verification adapter built from the same ``private_dir``
    always resolve the SAME path, and the files stay inside a test's tmp dir).
    """
    path = Path(private_dir)
    parts = path.resolve().parts
    leaf = ("clients", "_shared", "site-core", "contacts")
    # Live layout: .../mycite/<instance>/private -> webapps_root is 3 levels up.
    if len(parts) >= 4 and parts[-1] == "private" and parts[-3] == "mycite":
        return Path(*parts[:-3]).joinpath(*leaf)
    if webapps_root is not None:
        return Path(webapps_root).joinpath(*leaf)
    # Test/dev fallback: anchor under private_dir so it's deterministic + contained.
    return path.joinpath(*leaf)


class ContactLeafletStore:
    """Roster-only YAML store, one leaflet per entity."""

    def __init__(
        self,
        *,
        private_dir: str | Path,
        webapps_root: str | Path | None = None,
    ) -> None:
        self._private_dir = Path(private_dir)
        self._contacts_dir = _contacts_dir_for(private_dir, webapps_root)

    @property
    def contacts_dir(self) -> Path:
        return self._contacts_dir

    def leaflet_path(self, entity: str) -> Path:
        slug = _entity_slug(entity)
        return self._contacts_dir / f"0000-00-00.record-data.{slug}.contacts.yaml"

    def leaflet_present(self, entity: str) -> bool:
        path = self.leaflet_path(entity)
        return path.exists() and path.is_file()

    # -- low level read/write -------------------------------------------------

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists() or not path.is_file():
            return {}
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            _log.warning(
                "contact_leaflet_yaml_parse_failed path=%s", path, exc_info=True
            )
            return {}
        return dict(payload) if isinstance(payload, dict) else {}

    def _write_yaml(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = yaml.safe_dump(
            payload, sort_keys=False, allow_unicode=True, default_flow_style=False
        )
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent), prefix=".tmp-", suffix=".yaml"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp_path, str(path))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # -- roster API -----------------------------------------------------------

    def load_roster(self, entity: str) -> list[dict[str, Any]]:
        """Return the contact list for an entity (``[]`` when absent/unreadable)."""
        payload = self._read_yaml(self.leaflet_path(entity))
        if _as_text(payload.get("schema")) not in _ACCEPTED_CONTACT_RECORD_SCHEMAS:
            return []
        contacts = payload.get("contacts")
        if not isinstance(contacts, list):
            return []
        return [dict(c) for c in contacts if isinstance(c, dict)]

    def save_roster(self, entity: str, contacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Atomically persist the full contact list for an entity."""
        slug = _entity_slug(entity)
        rows = [dict(c) for c in (contacts or []) if isinstance(c, dict)]
        payload = {
            "schema": CONTACT_RECORD_SCHEMA,
            "entity": slug,
            "contacts": rows,
        }
        self._write_yaml(self.leaflet_path(slug), payload)
        return rows

    def _find_index(self, contacts: list[dict[str, Any]], email: str) -> int | None:
        key = _as_text(email).lower()
        for i, c in enumerate(contacts):
            if _as_text(c.get("email")).lower() == key:
                return i
        return None

    def upsert_contact(self, entity: str, contact: dict[str, Any]) -> dict[str, Any]:
        """Insert or replace a contact by email. Returns the stored row."""
        email = _as_text(contact.get("email")).lower()
        if not email:
            raise ValueError("email is required for upsert_contact")
        row = dict(contact)
        row["email"] = email
        contacts = self.load_roster(entity)
        index = self._find_index(contacts, email)
        if index is not None:
            contacts[index] = row
        else:
            contacts.append(row)
        self.save_roster(entity, contacts)
        return row

    def edit_contact(self, entity: str, email: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        """Shallow-merge ``patch`` onto an existing contact. ``None`` if absent."""
        contacts = self.load_roster(entity)
        index = self._find_index(contacts, email)
        if index is None:
            return None
        row = dict(contacts[index])
        row.update({k: v for k, v in patch.items()})
        row["email"] = _as_text(row.get("email")).lower() or _as_text(email).lower()
        contacts[index] = row
        self.save_roster(entity, contacts)
        return row

    def mark_unsubscribed(self, entity: str, email: str, *, now: str = "") -> bool:
        """Flip a contact's subscribed flag off. Returns whether one matched."""
        contacts = self.load_roster(entity)
        index = self._find_index(contacts, email)
        if index is None:
            return False
        row = dict(contacts[index])
        row["subscribed"] = False
        if now:
            row["unsubscribed_at"] = now
        contacts[index] = row
        self.save_roster(entity, contacts)
        return True

    def set_subscription(self, entity: str, email: str, subscribed: bool) -> bool:
        """Set a contact's subscribed flag. Returns whether one matched."""
        contacts = self.load_roster(entity)
        index = self._find_index(contacts, email)
        if index is None:
            return False
        row = dict(contacts[index])
        row["subscribed"] = bool(subscribed)
        contacts[index] = row
        self.save_roster(entity, contacts)
        return True


# Module-level convenience wrappers (the task's named functions). Each builds a
# store from ``private_dir`` and resolves the domain to its entity.


def _store(private_dir: str | Path, webapps_root: str | Path | None = None) -> ContactLeafletStore:
    return ContactLeafletStore(private_dir=private_dir, webapps_root=webapps_root)


def load_roster(
    entity: str,
    *,
    private_dir: str | Path,
    webapps_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    return _store(private_dir, webapps_root).load_roster(entity)


def save_roster(
    entity: str,
    contacts: list[dict[str, Any]],
    *,
    private_dir: str | Path,
    webapps_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    return _store(private_dir, webapps_root).save_roster(entity, contacts)


def upsert_contact(
    entity: str,
    contact: dict[str, Any],
    *,
    private_dir: str | Path,
    webapps_root: str | Path | None = None,
) -> dict[str, Any]:
    return _store(private_dir, webapps_root).upsert_contact(entity, contact)


def edit_contact(
    entity: str,
    email: str,
    patch: dict[str, Any],
    *,
    private_dir: str | Path,
    webapps_root: str | Path | None = None,
) -> dict[str, Any] | None:
    return _store(private_dir, webapps_root).edit_contact(entity, email, patch)


def mark_unsubscribed(
    entity: str,
    email: str,
    *,
    now: str = "",
    private_dir: str | Path,
    webapps_root: str | Path | None = None,
) -> bool:
    return _store(private_dir, webapps_root).mark_unsubscribed(entity, email, now=now)


def set_subscription(
    entity: str,
    email: str,
    subscribed: bool,
    *,
    private_dir: str | Path,
    webapps_root: str | Path | None = None,
) -> bool:
    return _store(private_dir, webapps_root).set_subscription(entity, email, subscribed)
