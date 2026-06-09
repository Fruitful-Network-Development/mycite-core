"""Per-entity YAML newsletter-leaflet store.

Each NEWSLETTER a grantee composes in the dashboard is one YAML "leaflet" under:

    <webapps_root>/clients/_shared/site-core/newsletter/
        <date>.artifact-newsletter.<entity>.<slug>.yaml

Envelope schema ``mycite.site_core.newsletter.v1``. Unlike the contact roster
(one file per entity — see ``contact_leaflet.py``), there is one file per
newsletter (many per entity), identified by ``(entity, slug)`` and globbed by
name. Drafts and sent newsletters live in the same directory, distinguished by
the ``status`` field. The dashboard composer writes these; the grantee send
route reads the chosen one for its subject + body, and the contacts roster for
its audience.

PII NOTE: a newsletter is grantee operational content (its body may quote
member-facing copy), and like the contact roster it is a runtime, untracked
artifact — only the ``*.example.*`` template is committed. The portal is the
only reader (no nginx alias).

All writes are atomic (temp file in the same dir + ``os.replace``).
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from .contact_leaflet import _as_text, _entity_slug, entity_for_domain, normalized_domain

_log = logging.getLogger("mycite.portal_host")

NEWSLETTER_SCHEMA = "mycite.site_core.newsletter.v1"
_ACCEPTED_NEWSLETTER_SCHEMAS = frozenset({NEWSLETTER_SCHEMA})
NEWSLETTER_KIND = "artifact-newsletter"

# Fields a newsletter leaflet is guaranteed to carry. Extra keys round-trip
# verbatim so a future field is never dropped.
NEWSLETTER_FIELDS: tuple[str, ...] = (
    "slug",
    "subject",
    "body_text",
    "status",       # draft | sent
    "audience",     # subscribed
    "created_at",
    "updated_at",
    "sent_at",
    "dispatch_id",
    "target_count",
    "sent_count",
    "domain",
)


def _slugify(value: object) -> str:
    """Filesystem-safe lowercase token for a newsletter slug (same rules as the
    entity slug)."""
    return _entity_slug(value)


def _newsletter_dir_for(private_dir: str | Path, webapps_root: str | Path | None) -> Path:
    """Resolve the newsletter-leaflet directory from a private_dir.

    Mirrors ``contact_leaflet._contacts_dir_for``: live layout is
    ``<webapps_root>/mycite/<instance>/private`` and the leaflets live at
    ``<webapps_root>/clients/_shared/site-core/newsletter``. Tests pass an
    explicit ``webapps_root`` or fall back to anchoring under ``private_dir``.
    """
    path = Path(private_dir)
    parts = path.resolve().parts
    leaf = ("clients", "_shared", "site-core", "newsletter")
    if len(parts) >= 4 and parts[-1] == "private" and parts[-3] == "mycite":
        return Path(*parts[:-3]).joinpath(*leaf)
    if webapps_root is not None:
        return Path(webapps_root).joinpath(*leaf)
    return path.joinpath(*leaf)


class NewsletterLeafletStore:
    """One YAML leaflet per newsletter, many per entity."""

    def __init__(
        self,
        *,
        private_dir: str | Path,
        webapps_root: str | Path | None = None,
    ) -> None:
        self._private_dir = Path(private_dir)
        self._dir = _newsletter_dir_for(private_dir, webapps_root)

    @property
    def newsletter_dir(self) -> Path:
        return self._dir

    def _suffix(self, entity: str, slug: str) -> str:
        return f".artifact-newsletter.{_entity_slug(entity)}.{_slugify(slug)}.yaml"

    def _find_path(self, entity: str, slug: str) -> Path | None:
        """The existing file for ``(entity, slug)`` regardless of date prefix."""
        if not self._dir.is_dir() or not _slugify(slug):
            return None
        suffix = self._suffix(entity, slug)
        for p in sorted(self._dir.iterdir()):
            if p.name.endswith(suffix) and ".example." not in p.name:
                return p
        return None

    # -- low level read/write -------------------------------------------------

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists() or not path.is_file():
            return {}
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            _log.warning("newsletter_leaflet_parse_failed path=%s", path, exc_info=True)
            return {}
        return dict(payload) if isinstance(payload, dict) else {}

    def _write_yaml(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = yaml.safe_dump(
            payload, sort_keys=False, allow_unicode=True, default_flow_style=False
        )
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".yaml")
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

    # -- leaflet API ----------------------------------------------------------

    def list_newsletters(self, entity: str) -> list[dict[str, Any]]:
        """All of one entity's newsletter leaflets, newest-created first."""
        slug = _entity_slug(entity)
        if not self._dir.is_dir():
            return []
        marker = f".artifact-newsletter.{slug}."
        out: list[dict[str, Any]] = []
        for p in self._dir.iterdir():
            name = p.name
            if marker in name and name.endswith(".yaml") and ".example." not in name:
                payload = self._read_yaml(p)
                if _as_text(payload.get("schema")) in _ACCEPTED_NEWSLETTER_SCHEMAS:
                    out.append(payload)
        out.sort(key=lambda n: _as_text(n.get("created_at")), reverse=True)
        return out

    def load(self, entity: str, slug: str) -> dict[str, Any]:
        """Return one newsletter leaflet (``{}`` when absent / malformed)."""
        path = self._find_path(entity, slug)
        if path is None:
            return {}
        payload = self._read_yaml(path)
        if _as_text(payload.get("schema")) in _ACCEPTED_NEWSLETTER_SCHEMAS:
            return payload
        return {}

    def save(self, entity: str, newsletter: dict[str, Any]) -> dict[str, Any]:
        """Create or overwrite a newsletter leaflet (keyed by slug). The file's
        date prefix is fixed at first save from ``created_at`` (or
        ``0000-00-00``); a later save of the same slug overwrites that file."""
        slug = _slugify(newsletter.get("slug"))
        if not slug:
            raise ValueError("newsletter slug is required")
        row = dict(newsletter)
        row["schema"] = NEWSLETTER_SCHEMA
        row["kind"] = NEWSLETTER_KIND
        row["entity"] = _entity_slug(entity)
        row["slug"] = slug
        existing = self._find_path(entity, slug)
        if existing is not None:
            path = existing
        else:
            date_prefix = _as_text(row.get("created_at"))[:10] or "0000-00-00"
            path = self._dir / f"{date_prefix}{self._suffix(entity, slug)}"
        self._write_yaml(path, row)
        return row

    def delete(self, entity: str, slug: str) -> bool:
        path = self._find_path(entity, slug)
        if path is None:
            return False
        try:
            path.unlink()
            return True
        except OSError:
            return False


def _store(
    private_dir: str | Path, webapps_root: str | Path | None = None
) -> NewsletterLeafletStore:
    return NewsletterLeafletStore(private_dir=private_dir, webapps_root=webapps_root)


def list_newsletters(
    entity: str,
    *,
    private_dir: str | Path,
    webapps_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    return _store(private_dir, webapps_root).list_newsletters(entity)


def load_newsletter(
    entity: str,
    slug: str,
    *,
    private_dir: str | Path,
    webapps_root: str | Path | None = None,
) -> dict[str, Any]:
    return _store(private_dir, webapps_root).load(entity, slug)


def save_newsletter(
    entity: str,
    newsletter: dict[str, Any],
    *,
    private_dir: str | Path,
    webapps_root: str | Path | None = None,
) -> dict[str, Any]:
    return _store(private_dir, webapps_root).save(entity, newsletter)


__all__ = [
    "NEWSLETTER_FIELDS",
    "NEWSLETTER_KIND",
    "NEWSLETTER_SCHEMA",
    "NewsletterLeafletStore",
    "entity_for_domain",
    "list_newsletters",
    "load_newsletter",
    "normalized_domain",
    "save_newsletter",
]
