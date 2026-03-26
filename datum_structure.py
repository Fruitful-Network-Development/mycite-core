from __future__ import annotations

"""
datum_structure.py

Canonical reference helpers for anthology/resource datum addresses.

This module is intentionally separate from:
- mss_compact_array_reference.py  (contract-scoped compact-array transport)
- samras_structures.py            (shape-addressed mixed-radix structural model)

The three contexts are related but NOT interchangeable:
1) Datum address (this file):          <layer>-<value_group>-<iteration>
2) SAMRAS node address / structure:    BFS-derived structural address space
3) MSS storage/index references:       isolated compact-array snapshot indexes

Datum-address ordering rule:
- sort numerically by (layer, value_group, iteration)
- never lexicographically by raw string
  (e.g. ...-59 comes before ...-590 lexically, but that is wrong numerically)
"""

from dataclasses import dataclass
from typing import Iterable, List
import re


_DATUM_RE = re.compile(r"^(\d+)-(\d+)-(\d+)$")


@dataclass(frozen=True, order=True)
class DatumAddress:
    layer: int
    value_group: int
    iteration: int

    @property
    def text(self) -> str:
        return f"{self.layer}-{self.value_group}-{self.iteration}"


def parse_datum_address(value: str) -> DatumAddress:
    token = str(value or "").strip()
    match = _DATUM_RE.fullmatch(token)
    if match is None:
        raise ValueError(f"Invalid datum address: {value!r}")
    return DatumAddress(
        layer=int(match.group(1)),
        value_group=int(match.group(2)),
        iteration=int(match.group(3)),
    )


def is_datum_address(value: str) -> bool:
    return _DATUM_RE.fullmatch(str(value or "").strip()) is not None


def sort_datum_addresses(values: Iterable[str]) -> List[str]:
    parsed = [parse_datum_address(item) for item in values]
    parsed.sort()
    return [item.text for item in parsed]


def is_numerically_sorted(values: Iterable[str]) -> bool:
    tokens = [str(item or "").strip() for item in values]
    return tokens == sort_datum_addresses(tokens)

