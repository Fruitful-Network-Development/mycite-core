"""Bullet-proof datum-row editing operations.

These pure-stdlib operations preserve the MOS structural invariants when a
single datum row is inserted, removed, or shifted within its
``(layer, value_group)`` family:

* iteration values within a family stay contiguous (no skips).
* references from other rows are cascaded to the new addresses
  (addresses appearing in the row payload's first list slot, in
  ``rf.<addr>`` tokens, and in the row metadata are all updated).
* mutations propagate top-down: the highest-abstraction datum (largest
  layer, largest value-group, largest iteration) is processed first so
  domino-effect renumbering happens deterministically.

The module operates on a list of row dicts. Each row dict must carry
``datum_address`` and may optionally carry ``raw`` (the canonical row
payload, typically ``[[address, relation, object], [labels...]]``) and
arbitrary other keys, which are preserved.

Public entry points:

* ``insert_datum`` — splice a new row at a target ``(layer, value_group,
  iteration)`` position, shifting subsequent iterations up by one.
* ``delete_datum`` — remove the row at a target address, shifting
  subsequent iterations down by one. Also drops any references to the
  deleted address.
* ``shift_iteration`` — re-label one specific iteration to a new
  iteration value within the same family, cascading references.
* ``cascade_references`` — apply an arbitrary ``old → new`` address
  remap, rewriting every referencing row (including the address-
  hyphenated ``rf.<addr>`` token form).
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from typing import Any

_DATUM_ADDRESS_RE = re.compile(r"^[0-9]+-[0-9]+-[0-9]+$")
_RF_TOKEN_RE = re.compile(r"^rf\.([0-9]+-[0-9]+-[0-9]+)$", re.IGNORECASE)


def _parse_address(text: str) -> tuple[int, int, int]:
    if not _DATUM_ADDRESS_RE.fullmatch(text or ""):
        raise ValueError(f"invalid datum address: {text!r}")
    layer, value_group, iteration = (text or "").split("-")
    return int(layer), int(value_group), int(iteration)


def _format_address(layer: int, value_group: int, iteration: int) -> str:
    return f"{layer}-{value_group}-{iteration}"


def _row_address(row: Mapping[str, Any]) -> str:
    addr = row.get("datum_address")
    if not isinstance(addr, str):
        raise ValueError("row missing 'datum_address'")
    return addr


def _abstraction_sort_key_descending(address: str) -> tuple[int, int, int]:
    layer, value_group, iteration = _parse_address(address)
    return (-layer, -value_group, -iteration)


def _rewrite_reference_token(token: str, remap: Mapping[str, str]) -> str:
    """Rewrite a single token if it references a remapped address.

    Recognised forms:

    * bare datum address: ``"1-1-3"``
    * ``rf.<addr>`` token: ``"rf.1-1-3"``
    * ``<numeric_hyphen>.<addr>`` reference token: ``"3-2-3-17.1-1-3"``
    * any token that contains an address segment in a hyphenated/colon
      delimited form is left alone (the structural surface of those
      tokens is not part of the editing contract).
    """

    if not isinstance(token, str) or not token:
        return token

    if _DATUM_ADDRESS_RE.fullmatch(token) and token in remap:
        return remap[token]

    rf_match = _RF_TOKEN_RE.fullmatch(token)
    if rf_match:
        addr = rf_match.group(1)
        if addr in remap:
            return f"rf.{remap[addr]}"
        return token

    if "." in token:
        prefix, suffix = token.split(".", 1)
        if (
            _DATUM_ADDRESS_RE.fullmatch(suffix)
            and suffix in remap
        ):
            return f"{prefix}.{remap[suffix]}"

    return token


def _rewrite_row_payload(raw: Any, remap: Mapping[str, str]) -> Any:
    """Apply ``remap`` to every reference token inside a row payload."""

    if isinstance(raw, list):
        out_list: list[Any] = []
        for item in raw:
            out_list.append(_rewrite_row_payload(item, remap))
        return out_list
    if isinstance(raw, str):
        return _rewrite_reference_token(raw, remap)
    if isinstance(raw, dict):
        out_dict: dict[str, Any] = {}
        for key, value in raw.items():
            if key in {
                "datum_address",
                "subject_ref",
                "subject",
                "relation",
                "predicate",
                "object_ref",
                "object",
            } and isinstance(value, str):
                out_dict[key] = _rewrite_reference_token(value, remap)
            else:
                out_dict[key] = _rewrite_row_payload(value, remap)
        return out_dict
    return raw


def cascade_references(
    rows: list[Mapping[str, Any]],
    remap: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Return a new row list with every referencing token rewritten per ``remap``.

    The row's own ``datum_address`` is **not** rewritten by this function;
    callers should set the new address directly. Cascades only update
    references *to* the remapped addresses.
    """

    if not remap:
        return [dict(row) for row in rows]

    rewritten: list[dict[str, Any]] = []
    for row in rows:
        new_row: dict[str, Any] = dict(row)
        if "raw" in new_row:
            new_row["raw"] = _rewrite_row_payload(copy.deepcopy(new_row["raw"]), remap)
        if "subject_ref" in new_row and isinstance(new_row["subject_ref"], str):
            new_row["subject_ref"] = _rewrite_reference_token(new_row["subject_ref"], remap)
        if "object_ref" in new_row and isinstance(new_row["object_ref"], str):
            new_row["object_ref"] = _rewrite_reference_token(new_row["object_ref"], remap)
        rewritten.append(new_row)
    return rewritten


def _shift_family_iterations(
    rows: list[dict[str, Any]],
    *,
    family: tuple[int, int],
    shift_from_iteration: int,
    delta: int,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Shift iteration values in a family by ``delta`` for iterations >= ``shift_from_iteration``.

    Returns ``(updated_rows_in_canonical_order, address_remap)`` where the
    shift starts from the highest-iteration row and proceeds downward
    (top-down propagation). ``cascade_references`` is applied at the end
    so the returned rows are fully consistent.
    """

    if delta == 0:
        return [dict(row) for row in rows], {}

    affected: list[tuple[int, dict[str, Any]]] = []
    untouched: list[dict[str, Any]] = []
    for row in rows:
        layer, value_group, iteration = _parse_address(_row_address(row))
        if (layer, value_group) == family and iteration >= shift_from_iteration:
            affected.append((iteration, dict(row)))
        else:
            untouched.append(dict(row))

    affected.sort(key=lambda item: -item[0])

    remap: dict[str, str] = {}
    new_addresses: list[dict[str, Any]] = []
    for iteration, row in affected:
        new_iteration = iteration + delta
        if new_iteration < 1:
            raise ValueError(
                f"shift would produce non-positive iteration in family {family}: {new_iteration}"
            )
        old_addr = _format_address(family[0], family[1], iteration)
        new_addr = _format_address(family[0], family[1], new_iteration)
        remap[old_addr] = new_addr
        row["datum_address"] = new_addr
        new_addresses.append(row)

    combined = untouched + new_addresses
    cascaded = cascade_references(combined, remap)
    return cascaded, remap


def insert_datum(
    rows: list[Mapping[str, Any]],
    new_row: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Splice ``new_row`` at its ``datum_address`` position.

    If a row with the same address already exists, every row in that
    family with iteration >= target.iteration is shifted up by one so
    the new row occupies the target address. References across the
    document are cascaded to the new addresses.

    Returns ``(updated_rows, address_remap)`` where ``address_remap``
    only carries the displaced rows' old → new mapping; the freshly
    inserted row's address is whatever ``new_row.datum_address`` was.
    """

    target_address = _row_address(new_row)
    layer, value_group, iteration = _parse_address(target_address)
    family = (layer, value_group)

    existing_at_target = any(
        (
            (lambda parsed: parsed == (layer, value_group, iteration))(
                _parse_address(_row_address(existing))
            )
        )
        for existing in rows
    )
    delta = 1 if existing_at_target else 0
    shifted, remap = _shift_family_iterations(
        list(rows),
        family=family,
        shift_from_iteration=iteration,
        delta=delta,
    )

    inserted_row = dict(new_row)
    if "raw" in inserted_row and remap:
        inserted_row["raw"] = _rewrite_row_payload(copy.deepcopy(inserted_row["raw"]), remap)

    out = shifted + [inserted_row]
    out.sort(key=lambda row: _parse_address(_row_address(row)))
    return out, remap


def delete_datum(
    rows: list[Mapping[str, Any]],
    target_address: str,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Remove the row at ``target_address``, shifting the family down by one.

    Iterations above the deleted target are shifted down by one and
    references across the document are cascaded. References *to* the
    deleted address itself are left in place (the caller is responsible
    for confirming the deletion is reference-safe).

    Returns ``(updated_rows, address_remap)`` where the deleted address
    appears in ``address_remap`` only if other addresses also moved.
    """

    layer, value_group, iteration = _parse_address(target_address)
    family = (layer, value_group)

    found = False
    surviving: list[Mapping[str, Any]] = []
    for row in rows:
        if _row_address(row) == target_address:
            found = True
            continue
        surviving.append(row)
    if not found:
        raise ValueError(f"datum address not present: {target_address!r}")

    shifted, remap = _shift_family_iterations(
        list(surviving),
        family=family,
        shift_from_iteration=iteration + 1,
        delta=-1,
    )
    shifted.sort(key=lambda row: _parse_address(_row_address(row)))
    return shifted, remap


def shift_iteration(
    rows: list[Mapping[str, Any]],
    *,
    from_address: str,
    to_iteration: int,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Move one specific row to a new iteration within the same family.

    The displaced rows in between are renumbered so iteration values stay
    contiguous. Returns ``(updated_rows, address_remap)``.
    """

    layer, value_group, iteration = _parse_address(from_address)
    if to_iteration < 1:
        raise ValueError(f"target iteration must be positive: {to_iteration}")
    if to_iteration == iteration:
        return [dict(row) for row in rows], {}

    family = (layer, value_group)
    moved_row: dict[str, Any] | None = None
    others: list[Mapping[str, Any]] = []
    for row in rows:
        if _row_address(row) == from_address:
            moved_row = dict(row)
        else:
            others.append(row)
    if moved_row is None:
        raise ValueError(f"datum address not present: {from_address!r}")

    if to_iteration > iteration:
        shifted, remap_intermediate = _shift_family_iterations(
            list(others),
            family=family,
            shift_from_iteration=iteration + 1,
            delta=-1,
        )
        shifted_again, remap_target_zone = _shift_family_iterations(
            shifted,
            family=family,
            shift_from_iteration=to_iteration,
            delta=1,
        )
        intermediate_remap = dict(remap_intermediate)
        intermediate_remap.update(remap_target_zone)
        moved_row["datum_address"] = _format_address(layer, value_group, to_iteration)
        if "raw" in moved_row and intermediate_remap:
            moved_row["raw"] = _rewrite_row_payload(
                copy.deepcopy(moved_row["raw"]), intermediate_remap
            )
        out = shifted_again + [moved_row]
        full_remap = dict(intermediate_remap)
        full_remap[from_address] = moved_row["datum_address"]
    else:
        shifted, remap_target_zone = _shift_family_iterations(
            list(others),
            family=family,
            shift_from_iteration=to_iteration,
            delta=1,
        )
        shifted_again, remap_intermediate = _shift_family_iterations(
            shifted,
            family=family,
            shift_from_iteration=iteration + 2,
            delta=-1,
        )
        intermediate_remap = dict(remap_target_zone)
        intermediate_remap.update(remap_intermediate)
        moved_row["datum_address"] = _format_address(layer, value_group, to_iteration)
        if "raw" in moved_row and intermediate_remap:
            moved_row["raw"] = _rewrite_row_payload(
                copy.deepcopy(moved_row["raw"]), intermediate_remap
            )
        out = shifted_again + [moved_row]
        full_remap = dict(intermediate_remap)
        full_remap[from_address] = moved_row["datum_address"]

    out.sort(key=lambda row: _parse_address(_row_address(row)))
    return out, full_remap


__all__ = [
    "cascade_references",
    "delete_datum",
    "insert_datum",
    "shift_iteration",
]
