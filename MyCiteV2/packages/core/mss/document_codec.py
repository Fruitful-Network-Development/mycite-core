"""Binary MSS document codec — the canonical single-sequence wire form.

This implements the **firm** MSS (Mycelium Schema Standardisation) rules recovered
in ``docs/contracts/mss_binary_sequence/`` with one *internally-consistent,
documented* bit micro-grammar (the maintainer authorized a clean grammar over
byte-exactness to the historical example). It is proven by exhaustive
encode→decode round-trips and validated against the ``anthology-notes`` structure.

Model
-----
A document is a set of datums. Each datum has address ``<layer>-<value_group>-
<iteration>`` and either:
  - **VG0** (value_group == 0): *references only* — a list of referenced datums
    (e.g. the rudimentary datums ``0-0-*``), or
  - **VG>0**: exactly ``value_group`` ``(reference, magnitude)`` tuples.

Addresses are NOT stored — they are *derived* from the per-layer / per-value-group
/ per-iteration counts (SAMRAS-style ordinal derivation). The codec therefore
operates on a **canonical (contiguous) isolated anthology**: layers ``0..L-1``,
value-groups ``0..G-1`` within a layer, iterations ``1..K`` within a group. Use
:func:`reindex_into_isolated_anthology` to canonicalize an arbitrary datum set
first (it returns the address map); ``refs`` point *downward* (to strictly lower
layers — the transitive downward reference closure), which is what lets each layer
carry a fixed reference width.

Wire grammar (MSS-DOC.v1)
-------------------------
All integers use a self-delimiting **Elias-gamma** code on ``value + 1`` (``g``):
``g(v) = "0"*(k-1) + bin(v+1)[2:]`` where ``k = (v+1).bit_length()``. Decode reads
``k-1`` leading zeros then ``k`` bits. Fixed-width fields use big-endian binary of a
known width (width 0 ⇒ the field is omitted; the single possible value is implied).

    g(L)                                   # layer count
    for layer in 0..L-1: g(vg_count)       # value-groups in each layer
    for (layer,vg): g(vg_value)            # the VG number = tuple count (0 ⇒ refs-only)
    for (layer,vg): g(iter_count)          # datum count in that value-group
    for layer in 1..L-1:                    # COBM section (layer 0 has no priors)
        <prior_count bits>                  # bitmap over all datums in layers<layer;
                                            # 1 ⇒ that datum is in this layer's active
                                            # (referenceable) set
    g(stop_width); g(stop_count)            # stop-index table (uniform slice)
    stop_count × <stop_width bits>          # cumulative exclusive ends of each object
    <value stream>                          # concatenated per-datum object blobs

Per-datum object blob (the non-uniform slice), in canonical datum order:
    VG0:  g(ref_count) + ref_count × <ref_width(layer) bits>      # active-set indices
    VG>0: vg_value × ( <ref_width(layer) bits> + g(magnitude) )

``ref_width(layer) = bits_required(active_set_size - 1)`` (0 when size ≤ 1). The
active set for a layer is the COBM-marked subset of all lower-layer datums, in
canonical order; a reference is its index into that set.

The document **hash** is ``sha256`` over the encoded bitstream; **hyphae** is the
same codec over a single datum's reindexed downward closure (rudi-inclusive).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

MSS_DOC_POLICY = "mos.mss_binary_v1"


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class MssDatum:
    layer: int
    value_group: int
    iteration: int
    refs: tuple[str, ...] = ()                       # VG0: referenced addresses
    tuples: tuple[tuple[str, int], ...] = ()         # VG>0: (ref_address, magnitude)

    @property
    def address(self) -> str:
        return f"{self.layer}-{self.value_group}-{self.iteration}"

    def dependency_addresses(self) -> tuple[str, ...]:
        if self.value_group == 0:
            return tuple(self.refs)
        return tuple(ref for ref, _mag in self.tuples)


@dataclass
class EncodedMss:
    bitstream: str
    datum_count: int

    @property
    def hash(self) -> str:
        digest = hashlib.sha256(f"{MSS_DOC_POLICY}:{self.bitstream}".encode()).hexdigest()
        return f"sha256:{digest}"


class MssFormatError(ValueError):
    """The datum set or bitstream violates the MSS document grammar."""


# --------------------------------------------------------------------------- #
# Bit primitives
# --------------------------------------------------------------------------- #
def bits_required(max_value: int) -> int:
    """Bits needed to hold values ``0..max_value`` (≥1; 0 needs 1 bit)."""
    if max_value <= 0:
        return 1
    return max_value.bit_length()


def _g_encode(value: int) -> str:
    if value < 0:
        raise MssFormatError("cannot encode a negative integer")
    payload = bin(value + 1)[2:]            # starts with '1'
    return "0" * (len(payload) - 1) + payload


def _g_decode(bits: str, cursor: int) -> tuple[int, int]:
    zeros = 0
    i = cursor
    n = len(bits)
    while i < n and bits[i] == "0":
        zeros += 1
        i += 1
    width = zeros + 1
    if i + width > n:
        raise MssFormatError("truncated gamma integer")
    value = int(bits[i:i + width], 2) - 1
    return value, i + width


def _fixed_encode(value: int, width: int) -> str:
    if width == 0:
        if value != 0:
            raise MssFormatError("non-zero value in a zero-width field")
        return ""
    if value < 0 or value >= (1 << width):
        raise MssFormatError(f"value {value} does not fit in {width} bits")
    return format(value, f"0{width}b")


def _fixed_decode(bits: str, cursor: int, width: int) -> tuple[int, int]:
    if width == 0:
        return 0, cursor
    if cursor + width > len(bits):
        raise MssFormatError("truncated fixed-width field")
    return int(bits[cursor:cursor + width], 2), cursor + width


# --------------------------------------------------------------------------- #
# Canonicalization (reindex into an isolated anthology)
# --------------------------------------------------------------------------- #
def _canonical_sort_key(datum: MssDatum) -> tuple[int, int, int]:
    return (datum.layer, datum.value_group, datum.iteration)


def reindex_into_isolated_anthology(
    datums: list[MssDatum],
) -> tuple[list[MssDatum], dict[str, str]]:
    """Renumber an arbitrary datum set into a canonical contiguous anthology:
    layers ``0..L-1`` (in ascending order of original layer), value-groups
    ``0..G-1`` within a layer (ascending original value_group), iterations
    ``1..K`` within a group (ascending original iteration). Returns the canonical
    datums and the ``old_address -> new_address`` map. References are remapped.
    """
    ordered = sorted(datums, key=_canonical_sort_key)
    layers_seen = sorted({d.layer for d in ordered})
    layer_map = {old: new for new, old in enumerate(layers_seen)}

    # value_group is preserved verbatim — it is the *tuple count* (semantic),
    # not a positional index — so only layers (→ contiguous from 0) and
    # iterations (→ 1..K within each (layer, value_group)) are renumbered.
    address_map: dict[str, str] = {}
    iter_counter: dict[tuple[int, int], int] = {}
    for d in ordered:
        new_layer = layer_map[d.layer]
        key = (new_layer, d.value_group)
        iter_counter[key] = iter_counter.get(key, 0) + 1
        address_map[d.address] = f"{new_layer}-{d.value_group}-{iter_counter[key]}"

    # Second pass: rebuild datums with remapped addresses + refs.
    def remap(ref: str) -> str:
        if ref not in address_map:
            raise MssFormatError(f"reference to a datum not in the set: {ref!r}")
        return address_map[ref]

    canonical: list[MssDatum] = []
    for d in ordered:
        new_addr = address_map[d.address]
        layer, group, iteration = (int(p) for p in new_addr.split("-"))
        canonical.append(
            MssDatum(
                layer=layer,
                value_group=group,
                iteration=iteration,
                refs=tuple(remap(r) for r in d.refs),
                tuples=tuple((remap(r), m) for r, m in d.tuples),
            )
        )
    canonical.sort(key=_canonical_sort_key)
    return canonical, address_map


# --------------------------------------------------------------------------- #
# Metadata
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class _Metadata:
    layer_count: int
    vg_count_per_layer: list[int]
    vg_value: list[int]          # flattened (layer-major) value_group numbers
    iter_count: list[int]        # flattened (layer-major) iteration counts


def _validate_canonical(datums: list[MssDatum]) -> None:
    addresses = [d.address for d in datums]
    if len(set(addresses)) != len(addresses):
        raise MssFormatError("duplicate datum address")
    by_addr = {d.address: d for d in datums}
    layers = sorted({d.layer for d in datums})
    if layers and layers != list(range(len(layers))):
        raise MssFormatError("layers must be contiguous from 0 (reindex first)")
    for d in datums:
        if d.value_group == 0:
            if d.tuples:
                raise MssFormatError(f"VG0 datum {d.address} must not carry tuples")
        else:
            if len(d.tuples) != d.value_group:
                raise MssFormatError(
                    f"datum {d.address}: value_group {d.value_group} requires exactly "
                    f"{d.value_group} tuples, got {len(d.tuples)}"
                )
            if d.refs:
                raise MssFormatError(f"VG>0 datum {d.address} must not carry refs-only")
        for ref in d.dependency_addresses():
            if ref not in by_addr:
                raise MssFormatError(f"datum {d.address} references missing {ref}")
            if by_addr[ref].layer >= d.layer:
                raise MssFormatError(
                    f"datum {d.address} references {ref} which is not in a lower layer "
                    "(refs must point downward)"
                )


def _build_metadata(datums: list[MssDatum]) -> _Metadata:
    layers = sorted({d.layer for d in datums})
    vg_count_per_layer: list[int] = []
    vg_value: list[int] = []
    iter_count: list[int] = []
    for layer in layers:
        groups = sorted({d.value_group for d in datums if d.layer == layer})
        vg_count_per_layer.append(len(groups))
        for group in groups:
            members = [d for d in datums if d.layer == layer and d.value_group == group]
            vg_value.append(group)               # group number == tuple count
            iter_count.append(len(members))
    return _Metadata(
        layer_count=len(layers),
        vg_count_per_layer=vg_count_per_layer,
        vg_value=vg_value,
        iter_count=iter_count,
    )


def _datums_in_canonical_order(datums: list[MssDatum]) -> list[MssDatum]:
    return sorted(datums, key=_canonical_sort_key)


# --------------------------------------------------------------------------- #
# Encode
# --------------------------------------------------------------------------- #
def encode_document(datums: list[MssDatum]) -> EncodedMss:
    """Encode a *canonical* (reindexed) datum set into the MSS bitstream."""
    _validate_canonical(datums)
    ordered = _datums_in_canonical_order(datums)
    meta = _build_metadata(ordered)

    out: list[str] = []
    out.append(_g_encode(meta.layer_count))
    for c in meta.vg_count_per_layer:
        out.append(_g_encode(c))
    for v in meta.vg_value:
        out.append(_g_encode(v))
    for c in meta.iter_count:
        out.append(_g_encode(c))

    # Group datums by layer (canonical order), and precompute the active set +
    # ref width per layer; emit the COBM for layers > 0.
    by_layer: dict[int, list[MssDatum]] = {}
    for d in ordered:
        by_layer.setdefault(d.layer, []).append(d)

    prior: list[MssDatum] = []                  # accumulated lower-layer datums
    active_set_per_layer: dict[int, list[MssDatum]] = {}
    for layer in range(meta.layer_count):
        layer_rows = by_layer.get(layer, [])
        if layer > 0:
            referenced = {
                ref for d in layer_rows for ref in d.dependency_addresses()
            }
            cobm = "".join("1" if p.address in referenced else "0" for p in prior)
            out.append(cobm)
            active_set_per_layer[layer] = [p for p in prior if p.address in referenced]
        else:
            active_set_per_layer[layer] = []
        prior = prior + layer_rows

    # Build each datum's object blob (the value stream), then the stop table.
    objects: list[str] = []
    for layer in range(meta.layer_count):
        active = active_set_per_layer[layer]
        ref_width = bits_required(len(active) - 1) if len(active) > 1 else 0
        index_of = {p.address: i for i, p in enumerate(active)}
        for d in by_layer.get(layer, []):
            blob: list[str] = []
            if d.value_group == 0:
                blob.append(_g_encode(len(d.refs)))
                for ref in d.refs:
                    blob.append(_fixed_encode(index_of[ref], ref_width))
            else:
                for ref, mag in d.tuples:
                    blob.append(_fixed_encode(index_of[ref], ref_width))
                    blob.append(_g_encode(mag))
            objects.append("".join(blob))

    # Stop-index table: cumulative exclusive ends of all objects except the last.
    stops: list[int] = []
    total = 0
    for blob in objects[:-1]:
        total += len(blob)
        stops.append(total)
    value_stream = "".join(objects)
    max_stop = stops[-1] if stops else 0
    stop_width = bits_required(max_stop)
    out.append(_g_encode(stop_width))
    out.append(_g_encode(len(stops)))
    for s in stops:
        out.append(_fixed_encode(s, stop_width))
    out.append(value_stream)

    bitstream = "".join(out)
    return EncodedMss(bitstream=bitstream, datum_count=len(ordered))


# --------------------------------------------------------------------------- #
# Decode
# --------------------------------------------------------------------------- #
def decode_document(bitstream: str) -> list[MssDatum]:
    cursor = 0
    layer_count, cursor = _g_decode(bitstream, cursor)

    vg_count_per_layer: list[int] = []
    for _ in range(layer_count):
        c, cursor = _g_decode(bitstream, cursor)
        vg_count_per_layer.append(c)
    total_groups = sum(vg_count_per_layer)

    vg_value: list[int] = []
    for _ in range(total_groups):
        v, cursor = _g_decode(bitstream, cursor)
        vg_value.append(v)
    iter_count: list[int] = []
    for _ in range(total_groups):
        c, cursor = _g_decode(bitstream, cursor)
        iter_count.append(c)

    # Reconstruct the canonical (layer, group, iteration) address of every datum
    # and how many datums precede each layer.
    specs: list[tuple[int, int, int]] = []       # (layer, value_group_number, iteration)
    datums_per_layer: list[int] = [0] * layer_count
    gi = 0
    for layer in range(layer_count):
        for _ in range(vg_count_per_layer[layer]):
            group_number = vg_value[gi]
            count = iter_count[gi]
            gi += 1
            for it in range(1, count + 1):
                specs.append((layer, group_number, it))
                datums_per_layer[layer] += 1

    # COBM per layer (layer 0 has none) → active set membership over prior datums.
    prior_addresses: list[str] = []
    layer_start_index: list[int] = []
    idx = 0
    for layer in range(layer_count):
        layer_start_index.append(idx)
        idx += datums_per_layer[layer]
    spec_address = [f"{lyr}-{g}-{it}" for (lyr, g, it) in specs]

    active_set_per_layer: dict[int, list[str]] = {0: []}
    accumulated_before_layer: list[list[str]] = []
    running: list[str] = []
    for layer in range(layer_count):
        accumulated_before_layer.append(list(running))
        start = layer_start_index[layer]
        running = running + spec_address[start:start + datums_per_layer[layer]]

    for layer in range(1, layer_count):
        prior_addresses = accumulated_before_layer[layer]
        width = len(prior_addresses)
        cobm = bitstream[cursor:cursor + width]
        if len(cobm) != width:
            raise MssFormatError("truncated COBM")
        cursor += width
        active_set_per_layer[layer] = [
            addr for addr, bit in zip(prior_addresses, cobm, strict=True) if bit == "1"
        ]

    # Stop-index table.
    stop_width, cursor = _g_decode(bitstream, cursor)
    stop_count, cursor = _g_decode(bitstream, cursor)
    stops: list[int] = []
    for _ in range(stop_count):
        s, cursor = _fixed_decode(bitstream, cursor, stop_width)
        stops.append(s)
    value_stream = bitstream[cursor:]

    # Slice the value stream into per-datum object blobs.
    object_count = len(specs)
    blobs: list[str] = []
    start = 0
    for stop in stops:
        blobs.append(value_stream[start:stop])
        start = stop
    blobs.append(value_stream[start:])
    if len(blobs) != object_count:
        raise MssFormatError(
            f"stop table yields {len(blobs)} objects but metadata expects {object_count}"
        )

    # Parse each blob per its value-group rule.
    datums: list[MssDatum] = []
    for (layer, group_number, iteration), blob in zip(specs, blobs, strict=True):
        active = active_set_per_layer.get(layer, [])
        ref_width = bits_required(len(active) - 1) if len(active) > 1 else 0
        bc = 0
        if group_number == 0:
            ref_count, bc = _g_decode(blob, bc)
            refs: list[str] = []
            for _ in range(ref_count):
                ridx, bc = _fixed_decode(blob, bc, ref_width)
                refs.append(active[ridx])
            datums.append(MssDatum(layer, group_number, iteration, refs=tuple(refs)))
        else:
            tuples: list[tuple[str, int]] = []
            for _ in range(group_number):
                ridx, bc = _fixed_decode(blob, bc, ref_width)
                mag, bc = _g_decode(blob, bc)
                tuples.append((active[ridx], mag))
            datums.append(MssDatum(layer, group_number, iteration, tuples=tuple(tuples)))

    return datums


# --------------------------------------------------------------------------- #
# Hashing
# --------------------------------------------------------------------------- #
def mss_document_hash(datums: list[MssDatum]) -> str:
    """Canonical document hash = sha256 over the MSS bitstream of the reindexed set."""
    canonical, _ = reindex_into_isolated_anthology(datums)
    return encode_document(canonical).hash


__all__ = [
    "MSS_DOC_POLICY",
    "EncodedMss",
    "MssDatum",
    "MssFormatError",
    "bits_required",
    "decode_document",
    "encode_document",
    "mss_document_hash",
    "reindex_into_isolated_anthology",
]
