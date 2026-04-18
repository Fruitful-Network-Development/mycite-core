from __future__ import annotations

import json
import re
from typing import Any

from MyCiteV2.packages.ports.fnd_dcm_read_only import (
    FndDcmReadOnlyPort,
    FndDcmReadOnlyRequest,
)

_CANONICAL_SOCIAL_ALIASES = {
    "facebook.com": "facebook",
    "fb": "facebook",
    "instagram.com": "instagram",
    "ig": "instagram",
    "linkedin.com": "linkedin",
    "site": "website",
    "web": "website",
    "www": "website",
}
_SENTINEL_EMPTY_VALUES = {"", "~"}


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _slugify(value: object) -> str:
    token = _as_text(value).lower()
    token = re.sub(r"[^a-z0-9]+", "-", token)
    return token.strip("-")


def _clean_optional_text(value: object) -> str | None:
    token = _as_text(value)
    if token in _SENTINEL_EMPTY_VALUES:
        return None
    return token or None


def _clean_bio_lines(value: object) -> list[str]:
    lines: list[str] = []
    for raw_item in _as_list(value):
        token = _as_text(raw_item)
        if token:
            lines.append(token)
    return lines


def _canonical_social_platform(value: object) -> str:
    token = _as_text(value).lower().replace(" ", "_").replace("-", "_")
    return _CANONICAL_SOCIAL_ALIASES.get(token, token)


def _normalize_socials(value: object) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in _as_list(value):
        platform = ""
        raw_value = ""
        if isinstance(row, dict):
            if _as_text(row.get("platform")) and _as_text(row.get("value")):
                platform = _canonical_social_platform(row.get("platform"))
                raw_value = _as_text(row.get("value"))
            else:
                for key, item in row.items():
                    token = _as_text(item)
                    if token:
                        platform = _canonical_social_platform(key)
                        raw_value = token
                        break
        if not platform or not raw_value:
            continue
        identity = (platform, raw_value)
        if identity in seen:
            continue
        seen.add(identity)
        normalized.append({"platform": platform, "value": raw_value})
    return normalized


def normalize_board_profile(record: dict[str, Any]) -> dict[str, Any]:
    raw = _as_dict(record)
    summary_bio = _clean_optional_text(raw.get("summary_bio"))
    bio = _clean_bio_lines(raw.get("bio"))
    email = _clean_optional_text(raw.get("email"))
    secondary_email = _clean_optional_text(raw.get("secondary_email") or raw.get("alternative_email"))
    phone = _clean_optional_text(raw.get("phone") or raw.get("contact_phone_number"))
    why_joined = _clean_optional_text(raw.get("why_joined_the_board") or raw.get("why_joined_board"))
    year_joined = raw.get("year_joined_board")
    if year_joined in _SENTINEL_EMPTY_VALUES:
        year_joined = None
    if isinstance(year_joined, str) and year_joined.isdigit():
        year_joined = int(year_joined)
    if not isinstance(year_joined, int):
        year_joined = None
    tags = []
    for item in _as_list(raw.get("tags")):
        token = _slugify(item).replace("-", "_")
        if token and token not in tags:
            tags.append(token)
    canonical = {
        "id": _clean_optional_text(raw.get("id")) or _slugify(raw.get("name")) or "board-profile",
        "name": _as_text(raw.get("name")) or "Board member",
        "image": _clean_optional_text(raw.get("image")),
        "summary_bio": summary_bio or (bio[0] if bio else None),
        "bio": list(bio),
        "email": email,
        "secondary_email": secondary_email,
        "phone": phone,
        "why_joined_the_board": why_joined,
        "year_joined_board": year_joined,
        "socials": _normalize_socials(raw.get("socials")),
        "tags": tags,
    }
    return canonical


def normalize_board_profiles(value: object) -> list[dict[str, Any]]:
    return [normalize_board_profile(item) for item in _as_list(value) if isinstance(item, dict)]


def _dedupe_warnings(*sources: object) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for source in sources:
        if not isinstance(source, list):
            continue
        for item in source:
            token = _as_text(item)
            if not token or token in seen:
                continue
            seen.add(token)
            out.append(token)
    return out


def _dedupe_issue_rows(rows: object) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        issue = dict(row)
        identity = (
            _as_text(issue.get("code")),
            _as_text(issue.get("message")),
            _as_text(issue.get("path")),
        )
        if identity in seen:
            continue
        seen.add(identity)
        out.append(issue)
    return out


class FndDcmReadOnlyService:
    def __init__(self, read_port: FndDcmReadOnlyPort) -> None:
        self._read_port = read_port

    def read_surface(
        self,
        *,
        portal_tenant_id: str,
        portal_tenant_domain: object = "",
        site: object = "",
        view: object = "overview",
        page: object = "",
        collection: object = "",
    ) -> dict[str, Any]:
        result = self._read_port.read_fnd_dcm_read_only(
            FndDcmReadOnlyRequest(
                portal_tenant_id=portal_tenant_id,
                site=site,
                view=view,
                page=page,
                collection=collection,
            )
        )

        payload = _as_dict(result.source.payload) if result.source is not None else {}
        profiles = [dict(item) for item in _as_list(payload.get("profiles")) if isinstance(item, dict)]
        requested_site = _as_text(site).lower()
        tenant_domain = _as_text(portal_tenant_domain).lower()

        selected_profile: dict[str, Any] | None = None
        if requested_site:
            selected_profile = next(
                (profile for profile in profiles if _as_text(profile.get("domain")).lower() == requested_site),
                None,
            )
        if selected_profile is None and tenant_domain:
            selected_profile = next(
                (profile for profile in profiles if _as_text(profile.get("domain")).lower() == tenant_domain),
                None,
            )
        if selected_profile is None and profiles:
            selected_profile = profiles[0]

        selected = dict(selected_profile or {})
        projection = _as_dict(selected.get("projection"))
        pages = [dict(item) for item in _as_list(projection.get("pages")) if isinstance(item, dict)]
        collections = [dict(item) for item in _as_list(projection.get("collections")) if isinstance(item, dict)]
        issues = _dedupe_issue_rows(_as_list(projection.get("issues")) + _as_list(selected.get("issues")))
        view_token = _as_text(view).lower() or "overview"
        if view_token not in {"overview", "pages", "collections", "issues"}:
            view_token = "overview"
        page_id = _as_text(page)
        collection_id = _as_text(collection)
        selected_page = next((item for item in pages if _as_text(item.get("id")) == page_id), None)
        selected_collection = next((item for item in collections if _as_text(item.get("id")) == collection_id), None)
        if view_token != "pages":
            selected_page = None
            page_id = ""
        elif selected_page is None:
            page_id = ""
        if view_token != "collections":
            selected_collection = None
            collection_id = ""
        elif selected_collection is None:
            collection_id = ""

        canonical_query = {
            "site": _as_text(selected.get("domain")),
            "view": view_token,
        }
        if selected_page is not None and page_id:
            canonical_query["page"] = page_id
        if selected_collection is not None and collection_id:
            canonical_query["collection"] = collection_id

        selected_collection_sources = [
            dict(item)
            for item in _as_list(selected.get("collection_sources"))
            if isinstance(item, dict)
        ]
        if selected_collection is not None:
            selected_collection_sources = [
                row
                for row in selected_collection_sources
                if _as_text(row.get("collection_id")) == _as_text(selected_collection.get("id"))
            ]
        elif selected_page is not None:
            referenced = {
                _as_text(item)
                for item in _as_list(selected_page.get("collection_refs"))
                if _as_text(item)
            }
            if referenced:
                selected_collection_sources = [
                    row
                    for row in selected_collection_sources
                    if _as_text(row.get("collection_id")) in referenced
                ]

        board_profile_preview = None
        if selected_collection is not None and _as_text(selected_collection.get("id")) == "board_profiles":
            preview_payload = selected_collection.get("preview_payload")
            if isinstance(preview_payload, list):
                normalized_profiles = normalize_board_profiles(preview_payload)
                board_profile_preview = {
                    "count": len(normalized_profiles),
                    "ids": [_as_text(item.get("id")) for item in normalized_profiles[:6]],
                    "summary_count": sum(1 for item in normalized_profiles if _clean_optional_text(item.get("summary_bio"))),
                }

        selected_site_payload = _as_dict(projection.get("site"))
        selected_footer = _as_dict(projection.get("footer"))
        selected_navigation = _as_list(projection.get("navigation"))
        site_cards = []
        for profile in profiles:
            profile_projection = _as_dict(profile.get("projection"))
            site_cards.append(
                {
                    "domain": _as_text(profile.get("domain")),
                    "label": _as_text(profile.get("label")) or _as_text(profile_projection.get("site", {}).get("name")),
                    "schema": _as_text(profile.get("manifest_schema")),
                    "page_count": len(_as_list(profile_projection.get("pages"))),
                    "collection_count": len(_as_list(profile_projection.get("collections"))),
                    "issue_count": len(_dedupe_issue_rows(_as_list(profile_projection.get("issues")) + _as_list(profile.get("issues")))),
                    "selected": bool(_as_text(profile.get("domain")) and _as_text(profile.get("domain")) == _as_text(selected.get("domain"))),
                }
            )

        overview = {
            "domain": _as_text(selected.get("domain")),
            "label": _as_text(selected.get("label")) or _as_text(selected_site_payload.get("name")),
            "manifest_schema": _as_text(selected.get("manifest_schema")),
            "manifest_path": _as_text(selected.get("manifest_path")),
            "render_script_path": _as_text(selected.get("render_script_path")),
            "site_name": _as_text(selected_site_payload.get("name")),
            "site_description": _as_text(selected_site_payload.get("description")),
            "homepage_href": _as_text(selected_site_payload.get("homepage_href")),
            "navigation_count": len(selected_navigation),
            "footer_columns": int(selected_footer.get("column_count") or 0),
            "page_count": len(pages),
            "collection_count": len(collections),
            "issue_count": len(issues),
        }

        warnings = _dedupe_warnings(payload.get("warnings"), selected.get("warnings"))
        if not selected:
            warnings = _dedupe_warnings(warnings, ["No FND-DCM profile matched the requested site."])

        return {
            "site_cards": site_cards,
            "selected_site": _as_text(selected.get("domain")),
            "selected_label": _as_text(selected.get("label")) or _as_text(selected_site_payload.get("name")),
            "view": view_token,
            "page": page_id,
            "collection": collection_id,
            "canonical_query": canonical_query,
            "overview": overview,
            "pages": pages,
            "collections": collections,
            "issues": issues,
            "selected_page": selected_page,
            "selected_collection": selected_collection,
            "selected_collection_sources": selected_collection_sources,
            "raw_manifest_json": json.dumps(_as_dict(selected.get("raw_manifest")), indent=2, sort_keys=True),
            "normalization_evidence": [str(item) for item in _as_list(selected.get("normalization_evidence")) if _as_text(item)],
            "board_profile_preview": board_profile_preview,
            "tool_files": {
                "profile_file": _as_text(selected.get("profile_file")),
                "manifest_path": _as_text(selected.get("manifest_path")),
                "render_script_path": _as_text(selected.get("render_script_path")),
            },
            "warnings": warnings,
        }


__all__ = [
    "FndDcmReadOnlyService",
    "normalize_board_profile",
    "normalize_board_profiles",
]
