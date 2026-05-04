from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocument, AuthoritativeDatumDocumentRow
from MyCiteV2.packages.modules.shared.scalars import as_text

MSS_VERSION_HASH_POLICY = "mos.mss_sha256_v1"

_DATUM_ADDRESS_RE = re.compile(r"^[0-9]+-[0-9]+-[0-9]+$")
_RF_TOKEN_RE = re.compile(r"^rf\.([0-9]+-[0-9]+-[0-9]+)$", re.IGNORECASE)
_NUMERIC_HYPHEN_RE = re.compile(r"^[0-9]+(?:-[0-9]+)+$")


def _is_datum_address(value: object) -> bool:
    return bool(_DATUM_ADDRESS_RE.fullmatch(as_text(value)))


def _is_numeric_hyphen_token(value: object) -> bool:
    return bool(_NUMERIC_HYPHEN_RE.fullmatch(as_text(value)))


def _parse_datum_address(value: object) -> tuple[int, int, int]:
    token = as_text(value)
    if not _is_datum_address(token):
        raise ValueError(f"invalid datum address: {token!r}")
    layer, vg, iteration = token.split("-", 2)
    return int(layer), int(vg), int(iteration)


def _format_datum_address(layer: int, value_group: int, iteration: int) -> str:
    return f"{layer}-{value_group}-{iteration}"


def _datum_address_sort_key(value: object) -> tuple[int, int, int]:
    return _parse_datum_address(value)


def _dumps_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _sha256_token(*, prefix: str, payload: Any) -> str:
    digest = hashlib.sha256(f"{prefix}:{_dumps_json(payload)}".encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _row_tokens(raw: Any, *, datum_address: str) -> tuple[str, ...]:
    if isinstance(raw, list) and raw and isinstance(raw[0], list):
        return tuple(as_text(item) for item in raw[0] if as_text(item))
    if isinstance(raw, dict):
        values = (
            raw.get("datum_address"),
            raw.get("subject_ref") or raw.get("subject") or datum_address,
            raw.get("relation") or raw.get("predicate"),
            raw.get("object_ref") or raw.get("object"),
        )
        return tuple(as_text(item) for item in values if as_text(item))
    return ()


def _row_local_refs(
    row: AuthoritativeDatumDocumentRow,
    *,
    known_addresses: set[str],
) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    tokens = _row_tokens(row.raw, datum_address=row.datum_address)
    for index, token in enumerate(tokens):
        if not token:
            continue
        if index == 0 and token == row.datum_address:
            continue
        if _RF_TOKEN_RE.fullmatch(token):
            continue
        if _is_datum_address(token) and token in known_addresses and token != row.datum_address and token not in seen:
            seen.add(token)
            out.append(token)
            continue
        if "." in token:
            prefix, suffix = token.split(".", 1)
            if _is_numeric_hyphen_token(prefix) and _is_datum_address(suffix) and suffix in known_addresses:
                if suffix != row.datum_address and suffix not in seen:
                    seen.add(suffix)
                    out.append(suffix)
    return tuple(out)


def compute_mss_hash(datum_document: AuthoritativeDatumDocument) -> dict[str, Any]:
    """Return the canonical MSS version identity for a datum document.

    Produces the same version_hash as build_document_version_identity in
    MyCiteV2/packages/adapters/sql/datum_semantics.py. The hash is deterministic
    over sorted rows serialized with canonical JSON (sort_keys, no whitespace).

    Returns dict with keys: policy, version_hash, canonical_payload.
    """
    payload: dict[str, Any] = {
        "policy": MSS_VERSION_HASH_POLICY,
        "source_kind": datum_document.source_kind,
        "document_metadata": datum_document.document_metadata or {},
        "rows": [
            {"datum_address": row.datum_address, "raw": row.raw}
            for row in sorted(datum_document.rows, key=lambda r: _datum_address_sort_key(r.datum_address))
        ],
    }
    return {
        "policy": MSS_VERSION_HASH_POLICY,
        "version_hash": _sha256_token(prefix=MSS_VERSION_HASH_POLICY, payload=payload),
        "canonical_payload": payload,
    }


def derive_hyphae_chain(
    datum_doc: AuthoritativeDatumDocument,
    datum_address: str,
) -> list[str]:
    """Return the hyphae rudi chain for datum_address: [0-0-1, ..., 0-0-K].

    K is the highest rudi datum iteration (layer=0, value_group=0) reachable in
    the transitive dependency closure of datum_address. Every position 1..K is
    included even if not directly referenced by datum_address.

    Raises ValueError if datum_address is not present in datum_doc.
    """
    address_map: dict[str, AuthoritativeDatumDocumentRow] = {
        row.datum_address: row for row in datum_doc.rows
    }
    if datum_address not in address_map:
        raise ValueError(f"datum_address not found in document: {datum_address!r}")

    known_addresses = set(address_map)
    dependency_map: dict[str, tuple[str, ...]] = {
        addr: _row_local_refs(row, known_addresses=known_addresses)
        for addr, row in address_map.items()
    }

    closure: list[str] = []
    seen: set[str] = set()

    def _walk(current: str) -> None:
        if current in seen:
            return
        seen.add(current)
        for dep in sorted(dependency_map.get(current, ()), key=_datum_address_sort_key):
            _walk(dep)
        closure.append(current)

    _walk(datum_address)

    rudi_in_doc = {addr for addr in address_map if _parse_datum_address(addr)[:2] == (0, 0)}
    reachable_rudi_iters = [
        _parse_datum_address(item)[2]
        for item in closure
        if item in rudi_in_doc
    ]
    if not reachable_rudi_iters:
        return []

    max_k = max(reachable_rudi_iters)
    return [
        _format_datum_address(0, 0, k)
        for k in range(1, max_k + 1)
        if _format_datum_address(0, 0, k) in rudi_in_doc
    ]
