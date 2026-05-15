"""Tool eligibility recognizer for the portal palette.

Pure function. Given a selected datum (document + address) and the tool
registry, returns the subset of palette tools whose `applies_to_archetype`
or `applies_to_source_kind` intersects the document's archetype/source_kind
set. Extensions (`is_extension=True`) are never included in the palette.

The archetype set is derived from:
  1. `datum_doc.document_metadata.get("archetype")` if a non-empty string,
  2. Per-row `archetype` tokens reached via the hyphae chain
     (`derive_hyphae_chain` in packages/core/mss/datum_identity.py).

See `portal_tool_surface_contract.md` for the architectural intent.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from MyCiteV2.packages.core.mss.datum_identity import derive_hyphae_chain

from .shell import PortalToolRegistryEntry


def _normalize_token(value: Any) -> str:
    """Match the same slug shape used by PortalToolRegistryEntry normalization
    and by AuthoritativeDatumDocument.source_kind (lowercase, trimmed,
    hyphens/spaces -> underscores)."""
    if value is None:
        return ""
    text = str(value).strip()
    return text.lower().replace("-", "_").replace(" ", "_")


def _row_archetype(row: Any) -> str:
    """Best-effort archetype extraction from a datum row's raw payload."""
    raw = getattr(row, "raw", None)
    if isinstance(raw, dict):
        return _normalize_token(raw.get("archetype"))
    return ""


def _document_archetype_set(datum_doc: Any, hyphae_chain: Iterable[str]) -> frozenset[str]:
    archetypes: set[str] = set()
    metadata = getattr(datum_doc, "document_metadata", None) or {}
    if isinstance(metadata, dict):
        doc_archetype = _normalize_token(metadata.get("archetype"))
        if doc_archetype:
            archetypes.add(doc_archetype)

    rows = getattr(datum_doc, "rows", ())
    rows_by_address = {getattr(row, "datum_address", ""): row for row in rows}
    for rudi_address in hyphae_chain:
        row = rows_by_address.get(rudi_address)
        if row is None:
            continue
        archetype = _row_archetype(row)
        if archetype:
            archetypes.add(archetype)
    return frozenset(archetypes)


def recognize_applicable_tools(
    datum_doc: Any,
    datum_address: str,
    registry: tuple[PortalToolRegistryEntry, ...],
) -> tuple[PortalToolRegistryEntry, ...]:
    """Return the palette-eligible subset of `registry` for the given datum.

    A tool is eligible when:
      - it is NOT an extension (is_extension == False), AND
      - either its `applies_to_archetype` intersects the document's archetype
        set, OR its `applies_to_source_kind` intersects the document's
        source_kind (a single-element set).

    The archetype set is widened by the hyphae chain so tools applicable to
    upstream rudis are also offered.

    Output ordering is deterministic, sorted by `tool_id`.

    Returns () when:
      - datum_address is empty
      - datum_address is not present in datum_doc (derive_hyphae_chain raises;
        we treat that as no eligibility rather than re-raising)
    """
    address = str(datum_address or "").strip()
    if not address:
        return ()

    try:
        hyphae_chain = derive_hyphae_chain(datum_doc, address)
    except ValueError:
        return ()

    archetype_set = _document_archetype_set(datum_doc, hyphae_chain)
    source_kind = _normalize_token(getattr(datum_doc, "source_kind", ""))
    source_kind_set = frozenset({source_kind}) if source_kind else frozenset()

    eligible: list[PortalToolRegistryEntry] = []
    for entry in registry:
        if entry.is_extension:
            continue
        applies_archetype = frozenset(entry.applies_to_archetype)
        applies_source_kind = frozenset(entry.applies_to_source_kind)
        if archetype_set & applies_archetype:
            eligible.append(entry)
            continue
        if source_kind_set & applies_source_kind:
            eligible.append(entry)
    eligible.sort(key=lambda e: e.tool_id)
    return tuple(eligible)


__all__ = ["recognize_applicable_tools"]
