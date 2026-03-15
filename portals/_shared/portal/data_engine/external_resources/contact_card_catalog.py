from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..datum_identity import stable_datum_id


@dataclass(frozen=True)
class PublicResourceDescriptor:
    resource_id: str
    kind: str
    export_family: str
    href: str
    lens_hint: str
    availability: dict[str, Any]
    source_msn_id: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "kind": self.kind,
            "export_family": self.export_family,
            "href": self.href,
            "lens_hint": self.lens_hint,
            "availability": dict(self.availability),
            "source_msn_id": self.source_msn_id,
            "metadata": dict(self.metadata),
        }


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _default_descriptor_for_accessible(
    key: str,
    value: Any,
    *,
    source_msn_id: str,
) -> PublicResourceDescriptor:
    meta = value if isinstance(value, dict) else {"display_title": _as_text(value)}
    canonical = stable_datum_id(key, local_msn_id=source_msn_id or "")
    rid = _as_text(meta.get("resource_id")) or f"accessible:{canonical}"
    return PublicResourceDescriptor(
        resource_id=rid,
        kind=_as_text(meta.get("kind")) or "datum_export",
        export_family=_as_text(meta.get("export_family")) or "public_accessible.v1",
        href=_as_text(meta.get("href")),
        lens_hint=_as_text(meta.get("lens_hint")) or "datum",
        availability=meta.get("availability") if isinstance(meta.get("availability"), dict) else {"public": True},
        source_msn_id=source_msn_id,
        metadata={**meta, "datum_ref": key, "canonical_datum_ref": canonical},
    )


def parse_public_resource_catalog(card_payload: dict[str, Any], *, source_msn_id: str) -> list[PublicResourceDescriptor]:
    if not isinstance(card_payload, dict):
        return []
    out: list[PublicResourceDescriptor] = []
    raw_catalog = card_payload.get("public_resources")
    if isinstance(raw_catalog, list):
        for item in raw_catalog:
            if not isinstance(item, dict):
                continue
            rid = _as_text(item.get("resource_id"))
            href = _as_text(item.get("href"))
            kind = _as_text(item.get("kind"))
            export_family = _as_text(item.get("export_family"))
            if not rid or not kind or not export_family:
                continue
            out.append(
                PublicResourceDescriptor(
                    resource_id=rid,
                    kind=kind,
                    export_family=export_family,
                    href=href,
                    lens_hint=_as_text(item.get("lens_hint")),
                    availability=item.get("availability") if isinstance(item.get("availability"), dict) else {"public": True},
                    source_msn_id=source_msn_id,
                    metadata={k: v for k, v in item.items() if k not in {"resource_id", "kind", "export_family", "href", "lens_hint", "availability"}},
                )
            )
    accessible = card_payload.get("accessible")
    if isinstance(accessible, dict):
        for key, value in accessible.items():
            out.append(_default_descriptor_for_accessible(key, value, source_msn_id=source_msn_id))

    deduped: dict[str, PublicResourceDescriptor] = {}
    for item in out:
        deduped[item.resource_id] = item
    return list(deduped.values())
