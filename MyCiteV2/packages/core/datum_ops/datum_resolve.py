"""Shared datum reference-resolution primitives (consolidation spine, Phase 2).

Single-sources the four things every agro_erp viewer/tool needs and that were
previously copy-pasted across the tool modules and ingest scripts:

* :class:`Markers` — the one ``rf.3-1-X`` reference-marker registry (was redeclared
  under inconsistent names: ``_LCL_MARKER`` vs ``_RF_LCL_ID``, ``_HOPS_MARKER`` vs
  ``_HOPS_COORD_MARKER``, ``RF_TITLE`` vs ``_TITLE_MARKER`` …). Re-exports the three
  in :mod:`.labels` so there is exactly one definition of each token.
* :func:`iter_marker_pairs` — the canonical ``(marker, magnitude)`` head walk, the
  loop reimplemented in contracts (×2), product_document and the invoice reader.
* :class:`NameIndex` + :func:`cached_index` — node-address → display-name resolution
  built by SHAPE (``refs._is_definition_head``, every prefix — not the hardcoded
  ``4-2-*`` the old ``LclNameIndex`` used, which silently returned nothing for
  invoice/contact definitions). One process-lifetime cache keyed on ``document_id``
  (content-hash derived) so contracts/txa stop rebuilding the 1.6k-entry decode.
* :func:`decode_label` / :func:`encode_label` / :func:`resolve_coordinate` — the
  title codec + HOPS ring decode (was hand-rolled as ``_decode_title_bits`` /
  ``_encode_bits`` / ``_ring_coords``).

Layering: this is ``core`` and must not import ``state_machine`` — the label decode
is implemented here over the same 8-bit ASCII encoding :mod:`.labels` produces
(canonical: stop at the first NUL byte), so no ``BinaryTextLens`` dependency.
"""

from __future__ import annotations

from typing import Any

from MyCiteV2.packages.core.structures.hops import decode_hops_coordinate_token
from MyCiteV2.packages.core.structures.samras.structure import as_text

from . import labels as _labels
from .refs import _head, _is_definition_head


class Markers:
    """The agro_erp ``rf.3-1-X`` reference-marker vocabulary, single-sourced.

    Each marker types the *following* magnitude slot in a row head. ``NODE_ID`` /
    ``LCL_ID`` carry node-address references; the rest carry encoded literals
    (title blob, HOPS coordinate/UTC tokens, msn id, nominal value).
    """

    NODE_ID = _labels.RF_NODE_ID      # rf.3-1-1 — txa node-id reference
    TITLE = _labels.RF_TITLE          # rf.3-1-2 — 512-bit ASCII title babelette
    COORDINATE = "rf.3-1-3"           # HOPS lon/lat coordinate token
    MSN = "rf.3-1-4"                  # msn-id literal
    LCL_ID = _labels.RF_LCL_ID        # rf.3-1-5 — lcl node-id reference
    UTC = "rf.3-1-6"                  # HOPS-UTC date token
    NOMINAL = "rf.3-1-7"              # nominal-256-17 value (weight/cost/amount)

    # Markers whose magnitude is a node-address REFERENCE (not a literal).
    NODE_REF = frozenset({NODE_ID, LCL_ID})

    @classmethod
    def is_node_ref(cls, marker: object) -> bool:
        return as_text(marker).lower() in cls.NODE_REF


def iter_marker_pairs(head: list[Any]):
    """Yield ``(marker, magnitude)`` for each pair in a datum row head.

    A head is ``[self_address, marker, magnitude, marker, magnitude, …]`` — the
    canonical positional ``2N+1`` pair model. Marker is returned stripped; the
    magnitude is returned verbatim (callers decode per the marker's kind).
    """
    for i in range(1, len(head) - 1, 2):
        yield as_text(head[i]), head[i + 1]


# Canonical title encode (re-export) + decode (inverse, NUL-terminated).
encode_label = _labels.encode_label_bits


def decode_label(bits: object) -> str:
    """Decode a fixed-width ASCII title/nominal babelette to text.

    Only a genuine binary babelette — char-set ⊆ {0,1} and length a non-zero multiple
    of 8 — is decoded; any other value (a plain label, or a short all-binary literal
    like ``"1011"``) is returned as-is, so callers may pass either an encoded blob or an
    already-plain label safely. Decoding stops at the first NUL byte and DROPS
    non-printable control bytes (restoring the safety of the replaced ``BinaryTextLens``,
    which never leaked raw control chars into rendered strings).
    """
    text = as_text(bits)
    if not text or len(text) % 8 or set(text) - {"0", "1"}:
        return text
    out: list[str] = []
    for i in range(0, len(text), 8):
        byte = int(text[i : i + 8], 2)
        if byte == 0:
            break
        if 32 <= byte <= 126:  # printable ASCII only — never leak control chars
            out.append(chr(byte))
    return "".join(out)


def resolve_coordinate(head: list[Any]) -> list[tuple[float, float]]:
    """Decode a family-4 ring head's ``rf.3-1-3`` HOPS tokens → ``(lon, lat)`` coords."""
    coords: list[tuple[float, float]] = []
    for i in range(len(head) - 1):
        if as_text(head[i]) == Markers.COORDINATE:
            decoded = decode_hops_coordinate_token(as_text(head[i + 1]))
            if decoded:
                coords.append((decoded["longitude"]["value"], decoded["latitude"]["value"]))
    return coords


class NameIndex:
    """node_address → display name, built from a document's *definition* rows.

    A definition row's head is ``[addr, <node-ref marker>, <node_addr>, rf.3-1-2,
    <title blob>]`` (every prefix family, recognized by shape — txa ``4-2-*``, lcl
    ``4-2-*``, farm_profile ``7-*`` features, …). The index prefers the plain row
    tail label, falling back to the decoded title blob.
    """

    def __init__(self, document: Any | None):
        self._by_node: dict[str, str] = {}
        if document is None:
            return
        for row in getattr(document, "rows", ()) or ():
            head = _head(getattr(row, "raw", None))
            if head is None or not _is_definition_head(head):
                continue
            node = as_text(head[2])
            if not node:
                continue
            raw = row.raw
            label = ""
            if isinstance(raw, list) and len(raw) > 1 and isinstance(raw[1], list) and raw[1]:
                label = as_text(raw[1][0])
            if not label and len(head) >= 5:
                label = decode_label(head[4])
            self._by_node.setdefault(node, label)

    def resolve(self, node_addr: object) -> str:
        return self._by_node.get(as_text(node_addr), "")

    def __len__(self) -> int:
        return len(self._by_node)


# Process-lifetime cache keyed on document_id (content-hash derived → no stale risk).
# Bounded: document_ids are content-hash derived, so every write mints a fresh key and
# superseded versions would otherwise accumulate unboundedly over the portal's lifetime.
# Cap with FIFO eviction of the oldest entry (dicts preserve insertion order).
_INDEX_CACHE: dict[str, NameIndex] = {}
_INDEX_CACHE_MAX = 64


def cached_index(document: Any | None) -> NameIndex:
    """A :class:`NameIndex` for ``document``, memoized on its ``document_id``."""
    if document is None:
        return NameIndex(None)
    key = as_text(getattr(document, "document_id", ""))
    cached = _INDEX_CACHE.get(key)
    if cached is None:
        cached = NameIndex(document)
        if key:
            _INDEX_CACHE[key] = cached
            if len(_INDEX_CACHE) > _INDEX_CACHE_MAX:
                _INDEX_CACHE.pop(next(iter(_INDEX_CACHE)))
    return cached


__all__ = [
    "Markers",
    "NameIndex",
    "cached_index",
    "decode_label",
    "encode_label",
    "iter_marker_pairs",
    "resolve_coordinate",
]
