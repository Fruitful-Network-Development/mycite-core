"""Per-entity campaign registry leaflet.

The operator generates pre-tracked links + QR codes from the dashboard's
Campaigns sub-tab. Each campaign is a row here, keyed by a short ``token`` that
rides on the public URL as ``?fnd_c=<token>``; analytics.js stamps the token
onto the session's ``routed_from`` so every visit through that link/QR is
attributed to the campaign (while the visitor cookie still distinguishes the
people who used the same QR).

    <webapps_root>/clients/_shared/site-core/analytics/
        0000-00-00.record-campaign.<entity>-website.campaigns.yaml

Envelope ``mycite.site_core.campaign_record.v1``. Campaign rows are operator
configuration (not PII), but they live in the gitignored analytics/ dir
alongside the data they describe; only ``*.example.*`` is tracked.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .analytics_leaflet import _analytics_dir_for, atomic_write_text
from .contact_leaflet import _entity_slug  # entity→fs-safe slug, shared with the roster store

_log = logging.getLogger("mycite.portal_host")

CAMPAIGN_RECORD_SCHEMA = "mycite.site_core.campaign_record.v1"
CAMPAIGN_RECORD_KIND = "record-campaign"

_VALID_MEDIUMS = frozenset({"link", "qr", "paid_social", "email", "print", "other"})
_TOKEN_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"  # no ambiguous chars
_TOKEN_LEN = 7


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _txt(value: object) -> str:
    return "" if value is None else str(value).strip()


def _mint_token(existing: set[str]) -> str:
    for _ in range(20):
        token = "".join(secrets.choice(_TOKEN_ALPHABET) for _ in range(_TOKEN_LEN))
        if token not in existing:
            return token
    # astronomically unlikely; widen on collision
    return "".join(secrets.choice(_TOKEN_ALPHABET) for _ in range(_TOKEN_LEN + 3))


def _normalize_target_path(raw: object) -> str:
    """A campaign target is a SAME-SITE path. Strip any ?query / #fragment (the
    tracked URL appends ?fnd_c itself), reject protocol-relative ``//host`` and
    ``..`` traversal, and return a single-leading-slash path (default ``/``).
    Defeats turning a tracked link into an off-site / phishing redirect."""
    t = _txt(raw)
    for sep in ("?", "#"):
        if sep in t:
            t = t.split(sep, 1)[0]
    t = t.strip()
    if not t or t == "/":
        return "/"
    # collapse leading slashes (defeats //host) + drop traversal/empty segments
    parts = [p for p in t.split("/") if p not in ("", "..", ".")]
    return "/" + "/".join(parts) if parts else "/"


class CampaignLeafletStore:
    def __init__(
        self,
        *,
        private_dir: str | Path,
        webapps_root: str | Path | None = None,
    ) -> None:
        self._analytics_dir = _analytics_dir_for(private_dir, webapps_root)

    def leaflet_path(self, entity: str) -> Path:
        slug = _entity_slug(entity)
        return self._analytics_dir / f"0000-00-00.record-campaign.{slug}-website.campaigns.yaml"

    def _read(self, entity: str) -> dict[str, Any]:
        path = self.leaflet_path(entity)
        if not path.exists():
            return {}
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            _log.warning("campaign_leaflet_parse_failed path=%s", path, exc_info=True)
            return {}
        return dict(payload) if isinstance(payload, dict) else {}

    def _write(self, entity: str, domain: str, campaigns: list[dict[str, Any]]) -> None:
        slug = _entity_slug(entity)
        payload = {
            "schema": CAMPAIGN_RECORD_SCHEMA,
            "kind": CAMPAIGN_RECORD_KIND,
            "entity": slug,
            "domain": _txt(domain),
            "campaigns": campaigns,
        }
        text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        atomic_write_text(self.leaflet_path(slug), text)

    def list_campaigns(self, entity: str) -> list[dict[str, Any]]:
        payload = self._read(entity)
        if payload.get("schema") != CAMPAIGN_RECORD_SCHEMA:
            return []
        rows = payload.get("campaigns")
        return [dict(c) for c in rows if isinstance(c, dict)] if isinstance(rows, list) else []

    def add_campaign(
        self,
        entity: str,
        domain: str,
        *,
        label: str,
        target_path: str = "/",
        source: str = "",
        medium: str = "link",
        notes: str = "",
    ) -> dict[str, Any]:
        label = _txt(label)
        if not label:
            raise ValueError("campaign label is required")
        medium = _txt(medium).lower()
        if medium not in _VALID_MEDIUMS:
            medium = "link"
        target = _normalize_target_path(target_path)
        campaigns = self.list_campaigns(entity)
        token = _mint_token({_txt(c.get("token")) for c in campaigns})
        row = {
            "token": token,
            "label": label,
            "target_path": target,
            "source": _txt(source),
            "medium": medium,
            "created_at": _now_iso(),
            "notes": _txt(notes),
        }
        campaigns.append(row)
        self._write(entity, domain, campaigns)
        return row

    def update_campaign(
        self,
        entity: str,
        domain: str,
        token: str,
        *,
        label: str | None = None,
        target_path: str | None = None,
        source: str | None = None,
        medium: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any] | None:
        """Edit an existing campaign in place. The ``token`` (attribution key
        baked into printed QR/redirect links) is IMMUTABLE, so editing a
        campaign — including repointing its ``target_path`` — never breaks an
        already-printed code. Only the provided fields change (``None`` = leave
        as-is). Returns the updated row, or ``None`` if the token is unknown."""
        token = _txt(token)
        campaigns = self.list_campaigns(entity)
        found = next((c for c in campaigns if _txt(c.get("token")) == token), None)
        if found is None:
            return None
        if label is not None:
            lab = _txt(label)
            if not lab:
                raise ValueError("campaign label is required")
            found["label"] = lab
        if target_path is not None:
            found["target_path"] = _normalize_target_path(target_path)
        if source is not None:
            found["source"] = _txt(source)
        if medium is not None:
            m = _txt(medium).lower()
            found["medium"] = m if m in _VALID_MEDIUMS else "link"
        if notes is not None:
            found["notes"] = _txt(notes)
        found["updated_at"] = _now_iso()
        self._write(entity, domain, campaigns)
        return found

    def delete_campaign(self, entity: str, domain: str, token: str) -> bool:
        """Remove a campaign by token. Returns True iff a row was removed. The
        token is retired: any lingering ``?fnd_c=<token>`` visits simply stop
        attributing (the GET handler only tallies tokens still in the registry)."""
        token = _txt(token)
        campaigns = self.list_campaigns(entity)
        kept = [c for c in campaigns if _txt(c.get("token")) != token]
        if len(kept) == len(campaigns):
            return False
        self._write(entity, domain, kept)
        return True

    def resolve(self, entity: str, token: str) -> dict[str, Any] | None:
        token = _txt(token)
        for c in self.list_campaigns(entity):
            if _txt(c.get("token")) == token:
                return c
        return None


__all__ = [
    "CAMPAIGN_RECORD_KIND",
    "CAMPAIGN_RECORD_SCHEMA",
    "CampaignLeafletStore",
]
