from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from MyCiteV2.packages.ports.datum_store import (
    PublicationTenantSummaryPort,
    PublicationTenantSummaryRequest,
    PublicationTenantSummaryResult,
    PublicationTenantSummarySource,
)

_WEBSITE_KEYS = ("public_website_url", "website_url", "website", "url")
_EMAIL_KEYS = ("contact_email", "email")


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_lower(value: object) -> str:
    return _as_text(value).lower()


def _looks_like_email(value: object) -> bool:
    token = _as_lower(value)
    return bool(token and "@" in token and not token.startswith("@") and not token.endswith("@"))


def _looks_like_public_website(value: object) -> bool:
    token = _as_text(value)
    return token.startswith("https://") or token.startswith("http://")


def _pretty_label(value: object, *, fallback: str) -> str:
    token = _as_text(value)
    if not token:
        token = fallback
    normalized = token.replace("_", " ").replace("-", " ").strip()
    return " ".join(part.capitalize() for part in normalized.split()) or fallback


def _safe_profile(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict(payload or {})


def _document_names(source: PublicationTenantSummarySource) -> tuple[str, ...]:
    names: list[str] = []
    if source.public_profile:
        names.append("public_profile")
    if source.tenant_profile:
        names.append("tenant_profile")
    return tuple(names)


def _summary_text(source: PublicationTenantSummarySource) -> str:
    tenant_profile = _safe_profile(source.tenant_profile)
    public_profile = _safe_profile(source.public_profile)
    return _as_text(
        tenant_profile.get("summary")
        or tenant_profile.get("bio")
        or public_profile.get("summary")
        or public_profile.get("bio")
    )


def _entity_type(source: PublicationTenantSummarySource) -> str:
    public_profile = _safe_profile(source.public_profile)
    tenant_profile = _safe_profile(source.tenant_profile)
    return _as_text(public_profile.get("entity_type") or tenant_profile.get("entity_type"))


def _display_title(source: PublicationTenantSummarySource) -> str:
    tenant_profile = _safe_profile(source.tenant_profile)
    public_profile = _safe_profile(source.public_profile)
    return _pretty_label(
        tenant_profile.get("title") or public_profile.get("title"),
        fallback=source.tenant_id,
    )


def _find_contact_email(payload: dict[str, Any]) -> str:
    for key in _EMAIL_KEYS:
        candidate = payload.get(key)
        if _looks_like_email(candidate):
            return _as_lower(candidate)
    options_public = payload.get("options_public")
    if isinstance(options_public, dict):
        for key in _EMAIL_KEYS:
            candidate = options_public.get(key)
            if _looks_like_email(candidate):
                return _as_lower(candidate)
    links = payload.get("links")
    if isinstance(links, list):
        for entry in links:
            if not isinstance(entry, dict):
                continue
            href = _as_text(entry.get("href") or entry.get("url"))
            if href.startswith("mailto:"):
                email = href.split(":", 1)[1].strip().lower()
                if _looks_like_email(email):
                    return email
            for key in _EMAIL_KEYS:
                candidate = entry.get(key)
                if _looks_like_email(candidate):
                    return _as_lower(candidate)
    return ""


def _find_public_website(payload: dict[str, Any]) -> str:
    for key in _WEBSITE_KEYS:
        candidate = payload.get(key)
        if _looks_like_public_website(candidate):
            return _as_text(candidate)
    options_public = payload.get("options_public")
    if isinstance(options_public, dict):
        for key in _WEBSITE_KEYS:
            candidate = options_public.get(key)
            if _looks_like_public_website(candidate):
                return _as_text(candidate)
    links = payload.get("links")
    if isinstance(links, list):
        for entry in links:
            if not isinstance(entry, dict):
                continue
            href = _as_text(entry.get("href") or entry.get("url"))
            if _looks_like_public_website(href):
                return href
            for key in _WEBSITE_KEYS:
                candidate = entry.get(key)
                if _looks_like_public_website(candidate):
                    return _as_text(candidate)
    return ""


@dataclass(frozen=True)
class PublicationTenantSummary:
    tenant_id: str
    tenant_domain: str
    profile_title: str
    profile_summary: str
    entity_type: str
    contact_email: str
    public_website_url: str
    available_documents: tuple[str, ...]
    profile_resolution: str
    publication_mode: str
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        tenant_id = _as_lower(self.tenant_id)
        tenant_domain = _as_lower(self.tenant_domain)
        profile_title = _as_text(self.profile_title)
        profile_resolution = _as_text(self.profile_resolution).lower()
        publication_mode = _as_text(self.publication_mode).lower()
        if not tenant_id:
            raise ValueError("publication_tenant_summary.tenant_id is required")
        if not tenant_domain or "." not in tenant_domain:
            raise ValueError("publication_tenant_summary.tenant_domain must be a domain-like value")
        if not profile_title:
            raise ValueError("publication_tenant_summary.profile_title is required")
        if profile_resolution not in {
            "publication_profiles_loaded",
            "publication_profiles_partial",
            "publication_identity_only",
            "publication_unresolved",
        }:
            raise ValueError("publication_tenant_summary.profile_resolution is invalid")
        if publication_mode != "publication-only":
            raise ValueError("publication_tenant_summary.publication_mode must be publication-only")
        object.__setattr__(self, "tenant_id", tenant_id)
        object.__setattr__(self, "tenant_domain", tenant_domain)
        object.__setattr__(self, "profile_title", profile_title)
        object.__setattr__(self, "profile_summary", _as_text(self.profile_summary))
        object.__setattr__(self, "entity_type", _as_text(self.entity_type))
        object.__setattr__(
            self,
            "contact_email",
            _as_lower(self.contact_email) if _looks_like_email(self.contact_email) else "",
        )
        object.__setattr__(
            self,
            "public_website_url",
            _as_text(self.public_website_url) if _looks_like_public_website(self.public_website_url) else "",
        )
        object.__setattr__(
            self,
            "available_documents",
            tuple(_as_text(item) for item in self.available_documents if _as_text(item)),
        )
        object.__setattr__(self, "profile_resolution", profile_resolution)
        object.__setattr__(self, "publication_mode", publication_mode)
        object.__setattr__(self, "warnings", tuple(_as_text(item) for item in self.warnings if _as_text(item)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "tenant_domain": self.tenant_domain,
            "profile_title": self.profile_title,
            "profile_summary": self.profile_summary,
            "entity_type": self.entity_type,
            "contact_email": self.contact_email,
            "public_website_url": self.public_website_url,
            "available_documents": list(self.available_documents),
            "profile_resolution": self.profile_resolution,
            "publication_mode": self.publication_mode,
            "warnings": list(self.warnings),
        }

    @classmethod
    def fallback(
        cls,
        *,
        tenant_id: str,
        tenant_domain: str,
        warnings: tuple[str, ...] = (),
    ) -> "PublicationTenantSummary":
        fallback_title = _pretty_label(tenant_id, fallback=_as_text(tenant_id) or "Tenant")
        return cls(
            tenant_id=tenant_id,
            tenant_domain=tenant_domain,
            profile_title=fallback_title,
            profile_summary="",
            entity_type="",
            contact_email="",
            public_website_url="",
            available_documents=(),
            profile_resolution="publication_unresolved",
            publication_mode="publication-only",
            warnings=warnings,
        )


def normalize_publication_tenant_summary(
    payload: PublicationTenantSummarySource | dict[str, Any],
    *,
    warnings: tuple[str, ...] = (),
) -> PublicationTenantSummary:
    if isinstance(payload, PublicationTenantSummarySource):
        source = payload
    elif isinstance(payload, dict):
        source = PublicationTenantSummarySource.from_dict(payload)
    else:
        raise ValueError("publication_tenant_summary_source must be a dict or PublicationTenantSummarySource")

    available_documents = _document_names(source)
    if len(available_documents) == 2:
        profile_resolution = "publication_profiles_loaded"
    elif available_documents:
        profile_resolution = "publication_profiles_partial"
    else:
        profile_resolution = "publication_identity_only"

    public_profile = _safe_profile(source.public_profile)
    tenant_profile = _safe_profile(source.tenant_profile)

    return PublicationTenantSummary(
        tenant_id=source.tenant_id,
        tenant_domain=source.tenant_domain,
        profile_title=_display_title(source),
        profile_summary=_summary_text(source),
        entity_type=_entity_type(source),
        contact_email=_find_contact_email(tenant_profile) or _find_contact_email(public_profile),
        public_website_url=_find_public_website(tenant_profile) or _find_public_website(public_profile),
        available_documents=available_documents,
        profile_resolution=profile_resolution,
        publication_mode="publication-only",
        warnings=warnings,
    )


class PublicationTenantSummaryService:
    def __init__(self, datum_store: PublicationTenantSummaryPort) -> None:
        self._datum_store = datum_store

    def read_projection(self, tenant_id: str, tenant_domain: str) -> PublicationTenantSummaryResult:
        return self._datum_store.read_publication_tenant_summary(
            PublicationTenantSummaryRequest(
                tenant_id=tenant_id,
                tenant_domain=tenant_domain,
            )
        )

    def read_summary(self, tenant_id: str, tenant_domain: str) -> PublicationTenantSummary | None:
        projection = self.read_projection(tenant_id, tenant_domain)
        if projection.source is None:
            return None
        return normalize_publication_tenant_summary(
            projection.source,
            warnings=projection.warnings,
        )
