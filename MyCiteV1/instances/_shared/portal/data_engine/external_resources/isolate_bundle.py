from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mycite_core.mss_resolution import stable_datum_id
from .isolate_identity import compute_closure_signature, compute_isolate_identity
from .provenance import ResourceProvenance


@dataclass(frozen=True)
class IsolateDatum:
    canonical_ref: str
    label: str
    row: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"canonical_ref": self.canonical_ref, "label": self.label, "row": dict(self.row)}


@dataclass(frozen=True)
class IsolateBundle:
    schema: str
    source_msn_id: str
    resource_id: str
    export_family: str
    wire_variant: str
    isolate_identity: str
    root_isolate_ref: str
    closure_signature: str
    closure_size: int
    provenance: ResourceProvenance
    isolates: list[IsolateDatum]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "source_msn_id": self.source_msn_id,
            "resource_id": self.resource_id,
            "export_family": self.export_family,
            "wire_variant": self.wire_variant,
            "isolate_identity": self.isolate_identity,
            "root_isolate_ref": self.root_isolate_ref,
            "closure_signature": self.closure_signature,
            "closure_size": self.closure_size,
            "provenance": self.provenance.to_dict(),
            "isolates": [item.to_dict() for item in self.isolates],
            "metadata": dict(self.metadata),
        }


def _coerce_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    if isinstance(rows, list):
        return [item for item in rows if isinstance(item, dict)]
    if isinstance(payload.get("accessible"), dict):
        out: list[dict[str, Any]] = []
        for key, value in payload.get("accessible", {}).items():
            meta = value if isinstance(value, dict) else {"display_title": str(value)}
            out.append({"identifier": str(key), "label": str(meta.get("display_title") or key), "metadata": meta})
        return out
    return []


def build_isolate_bundle(
    *,
    source_msn_id: str,
    resource_id: str,
    export_family: str,
    wire_variant: str,
    payload_sha256: str,
    payload: dict[str, Any],
    provenance: ResourceProvenance,
    source_card_revision: str = "",
) -> IsolateBundle:
    rows = _coerce_rows(payload)
    isolates: list[IsolateDatum] = []
    canonical_refs: list[str] = []
    for row in rows:
        identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
        if not identifier:
            continue
        canonical = stable_datum_id(identifier, local_msn_id=source_msn_id or "", field_name="identifier")
        canonical_refs.append(canonical)
        isolates.append(IsolateDatum(canonical_ref=canonical, label=str(row.get("label") or identifier), row=dict(row)))
    closure_signature = compute_closure_signature(canonical_refs)
    isolate_identity = compute_isolate_identity(
        source_msn_id=source_msn_id,
        resource_id=resource_id,
        export_family=export_family,
        payload_sha256=payload_sha256,
        closure_signature=closure_signature,
        wire_variant=wire_variant,
        source_card_revision=source_card_revision,
    )
    root = canonical_refs[0] if canonical_refs else ""
    return IsolateBundle(
        schema="mycite.external.isolate_bundle.v1",
        source_msn_id=source_msn_id,
        resource_id=resource_id,
        export_family=export_family,
        wire_variant=wire_variant,
        isolate_identity=isolate_identity,
        root_isolate_ref=root,
        closure_signature=closure_signature,
        closure_size=len(canonical_refs),
        provenance=provenance,
        isolates=isolates,
        metadata={
            "source_card_revision": source_card_revision,
            "canonical_refs": canonical_refs,
        },
    )
