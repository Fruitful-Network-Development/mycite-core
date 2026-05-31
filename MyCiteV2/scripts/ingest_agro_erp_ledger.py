#!/usr/bin/env python3
"""Extend the agro_erp datum graph into a small farm *ledger*.

Adds four new sandbox documents on top of the existing
``anchor``/``txa``/``lcl``/``product_profiles``/``farm_profile`` graph, plus the
supporting anchor + lcl structure they reference:

1. **anchor** — adds a **HOPS-chronological** spine (``1-1-6`` magnitude → ``2-0-5``
   space → ``3-1-6`` HOPS-babelette-UTC), copied verbatim from the proven cts_gis
   anchor time schema; a **nominal-256-17** placeholder bacillete (``2-1-4``
   abstraction → ``3-1-7`` nominal-babelette) for not-yet-abstracted weight/cost/
   amount strings; file pointers ``1-0-3..1-0-6`` for the new docs; and recompiles
   the ``1-1-5`` lcl-SAMRAS magnitude over the extended lcl node set.
2. **lcl** — extends the SAMRAS structure + node-address titles with a ``1-1-4``
   contact branch (+ one node per supplier), a ``1-4`` invoice branch (+ one node
   per invoice line), a ``1-5`` contract type node, and one ``1-3-1-N`` product
   leaf per unique supply SKU. Nodes are reused-by-title when already present
   (idempotent; re-run = byte-identical canonical ids).
3. **contacts** — one ``4-5-N`` PAIRS row per supplier (msn_id/title/email/phone/
   website).
4. **invoices** — one ``4-6-N`` PAIRS row per supply line (msn_id/date/product_id/
   weight/cost/supplier); dates are real quadrennium HOPS UTC addresses.
5. **contracts** — header-only (structure documented; rows filled later by the
   farm-plan workflow tool that draws contract weight down against an invoice).
6. **plots** — farm_profile-style HOPS geometry (family 4 rings → 5 polygons → 7
   filaments) linking each land plot (``1-2-2``/``1-2-3``) to a polygon.

weight/cost/amount are operator-chosen **placeholders**: ASCII strings encoded to
136 bits (17 bytes) against the new ``nominal-256-17`` bacillete, pending proper
unit abstraction. The polygon-fits-inside-field relation is a *vision of use*,
NOT validated here.

Discipline mirrors scripts/ingest_agro_erp_product_profiles.py:
  - Always --dry-run against an isolated DB copy first.
  - STEP 0 takes a timestamped .bak of the live DB before any write.
  - Self-verifies post-write and raises on any mismatch.
  - Idempotent: re-running yields byte-identical canonical document_ids.

Usage::

    python3 MyCiteV2/scripts/ingest_agro_erp_ledger.py \\
        --authority-db /srv/webapps/mycite/fnd/private/mos_authority.sqlite3 [--dry-run]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]  # /srv/repo/mycite-core
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.datum_rules import classify_row, validate_row
from MyCiteV2.packages.core.document_naming import format_canonical_document_id
from MyCiteV2.packages.core.mss import compute_mss_hash
from MyCiteV2.packages.core.structures.hops import (
    build_chronology_authority,
    encode_utc_datetime_as_hops,
    schema_from_anchor_payload,
)
from MyCiteV2.packages.core.structures.samras.codec import (
    decode_canonical_bitstream,
    encode_canonical_structure_from_addresses,
)
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.scripts.cts_gis_geojson_hops_utils import encode_hops_coordinate

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
TENANT = "fnd"
MSN_ID = "3-2-3-17-77-1-6-4-1-4"
SANDBOX = "agro_erp"
TITLE_BITS = 512            # niu-baciloid-256-64 title width
NOMINAL_BITS = 136          # nominal-256-17 = 17 bytes x 8 bits

# Reference (rf.) markers (positional pairs shape).
RF_LCL_ID = "rf.3-1-5"      # lcl id-babelette: record identity + cross-doc refs
RF_TXA_ID = "rf.3-1-1"      # SAMRAS-babelette-txa_id: structural/type parents
RF_TITLE = "rf.3-1-2"       # title-babelette (512-bit ASCII)
RF_COORD = "rf.3-1-3"       # HOPS-babelette-coordinate (existing; plot polygons)
RF_UTC = "rf.3-1-6"         # HOPS-babelette-UTC (NEW; dates)
RF_NOMINAL = "rf.3-1-7"     # nominal-babelette (NEW; weight/cost/amount placeholders)

# Anchor addresses minted/updated (free slots verified live 2026-05-31).
ANCHOR_HOPS_CHRONO_MAG = "1-1-6"
ANCHOR_HOPS_CHRONO_SPACE = "2-0-5"
ANCHOR_HOPS_UTC_BABELETTE = "3-1-6"
ANCHOR_NOMINAL_ABS = "2-1-4"
ANCHOR_NOMINAL_BABELETTE = "3-1-7"
ANCHOR_NOMINAL_BASE = "1-1-2"   # nominal-bacillete-256 (existing)
ANCHOR_LCL_SAMRAS = "1-1-5"     # recompiled over the extended lcl node set
ANCHOR_TIME_PRIMITIVE = "0-0-1"  # time-ordinal-position (chronological mag base)
ANCHOR_FILE_PRIMITIVE = "0-0-11"  # json-file-unit (file pointers)

# LCL structural anchors.
LCL_ENTITY = "1-1"
LCL_CONTACT_TYPE = "1-1-4"      # under entity 1-1 (1-1-1/2/3 = owner/animal/employee)
LCL_INVOICE_TYPE = "1-4"        # new top-level branch
LCL_CONTRACT_TYPE = "1-5"       # new top-level branch (type node only for now)
LCL_PRODUCT_TYPE = "1-3-1"      # product leaves mint as 1-3-1-N
LCL_PLOT_NODES = ("1-2-2", "1-2-3")  # plot_1, plot_2 (existing land plots)

# Value-groups for the new record docs (address vg == pair count).
CONTACTS_VG = 5
INVOICES_VG = 6

# Placeholder contact detail (no real data yet).
CONTACT_PLACEHOLDER = {
    "berlin_seeds": ("info@berlinseeds.example", "000-000-0000", "berlinseeds.example"),
    "holmes_seed": ("info@holmesseed.example", "000-000-0000", "holmesseed.example"),
    "middlefield_seed": ("info@middlefieldseed.example", "000-000-0000", "middlefieldseed.example"),
}

# Placeholder plot polygons: real vertices inside parcel_1 of farm_profile (so the
# "fits in field" vision is incidentally honoured; not enforced).
PLOT_RINGS = {
    "1-2-2": [  # plot_1
        (-81.5192433060284, 41.2358431404797),
        (-81.5192077635349, 41.2403864479658),
        (-81.5208272951516, 41.2403471538513),
        (-81.5223023446175, 41.2403113450354),
    ],
    "1-2-3": [  # plot_2
        (-81.5242733660313, 41.2385239109637),
        (-81.5266925610451, 41.2385314601604),
        (-81.5274180210586, 41.2385337141494),
        (-81.5274897614449, 41.2355360558574),
    ],
}

# --------------------------------------------------------------------------- #
# Supply-invoice sample data (operator-provided; one corrupted key repaired:
# the stuttg onion_sets line's local_id was a mangled token -> berlin_seeds).
# Each row: (supplier, product, dollars, weight_str, (mm, dd, yyyy))
# --------------------------------------------------------------------------- #
SUPPLY_INVOICE: tuple[tuple[str, str, str, str, tuple[int, int, int]], ...] = (
    ("berlin_seeds", "blue_lake_bush_274", "95.00", "25 lbs", (1, 8, 2025)),
    ("berlin_seeds", "sugar_snap_peas", "62.00", "10 lbs", (1, 8, 2025)),
    ("berlin_seeds", "waltham_butternut_squash", "28.00", "1 lbs", (1, 8, 2025)),
    ("berlin_seeds", "ct_field_pumpkin", "42.00", "2 lbs", (1, 8, 2025)),
    ("berlin_seeds", "detroit_dark_red_beet", "38.00", "2 lbs", (1, 8, 2025)),
    ("berlin_seeds", "stuttg_zephyr_zoidisarter_onion_sets", "160.00", "100 lbs", (1, 8, 2025)),
    ("berlin_seeds", "silver_queen_sweet_corn", "210.00", "15 lbs", (1, 8, 2025)),
    ("berlin_seeds", "clemson_spineless_okra", "18.00", "0.5 lbs", (1, 8, 2025)),
    ("berlin_seeds", "red_clover_seed", "175.00", "50 lbs", (1, 8, 2025)),
    ("berlin_seeds", "beauregard_slips", "240.00", "500 slips", (1, 8, 2025)),
    ("holmes_seed", "amish_paste_tomato", "48.00", "0.5 oz", (1, 12, 2025)),
    ("holmes_seed", "ca_wonder_pepper", "18.00", "0.25 oz", (1, 12, 2025)),
    ("holmes_seed", "golden_acre_cabbage", "12.00", "1 oz", (1, 12, 2025)),
    ("holmes_seed", "lacinato_kale", "35.00", "0.25 lbs", (1, 12, 2025)),
    ("holmes_seed", "nantes_coreless_carrot", "58.00", "1 lbs", (1, 12, 2025)),
    ("holmes_seed", "black_seeded_simpson", "32.00", "1 lbs", (1, 12, 2025)),
    ("holmes_seed", "bloomsdale_spinach", "44.00", "2 lbs", (1, 12, 2025)),
    ("holmes_seed", "genovese_basil", "35.00", "4 oz", (1, 12, 2025)),
    ("holmes_seed", "mammoth_grey_stripe_sunflower", "14.00", "1 lbs", (1, 12, 2025)),
    ("middlefield_seed", "field_corn_open_pollinated", "65.00", "50 lbs", (2, 4, 2025)),
    ("middlefield_seed", "oats_jerry_variety", "48.00", "100 lbs", (2, 4, 2025)),
    ("middlefield_seed", "buckwheat", "110.00", "100 lbs", (2, 4, 2025)),
    ("middlefield_seed", "mary_washington_asparagus", "150.00", "200 roots", (2, 4, 2025)),
    ("middlefield_seed", "victoria_rhubarb", "85.00", "25 roots", (2, 4, 2025)),
    ("berlin_seeds", "daikon_radish_driller", "45.00", "5 lbs", (6, 15, 2025)),
    ("berlin_seeds", "winter_rye", "85.00", "150 lbs", (6, 15, 2025)),
    ("berlin_seeds", "provider_bush_bean", "42.00", "10 lbs", (6, 15, 2025)),
    ("berlin_seeds", "winter_density_lettuce", "22.00", "4 oz", (6, 15, 2025)),
)


# --------------------------------------------------------------------------- #
# Pure helpers (copied from the canonical ingest/bootstrap scripts)
# --------------------------------------------------------------------------- #
def _encode_label_bits(label: str, *, bits: int = TITLE_BITS) -> str:
    raw = "".join(format(b, "08b") for b in label.encode("ascii"))
    if len(raw) > bits:
        raise ValueError(f"label {label!r} exceeds {bits} bits ({bits // 8} chars)")
    return raw.ljust(bits, "0")


def _decode_label_bits(bits: str) -> str:
    chars = []
    for i in range(0, len(bits), 8):
        byte = int(bits[i:i + 8], 2)
        if byte == 0:
            break
        chars.append(chr(byte))
    return "".join(chars)


def _prefix_closure(named_addresses: set[str]) -> set[str]:
    full: set[str] = set()
    for addr in named_addresses:
        segments = addr.split("-")
        for depth in range(1, len(segments) + 1):
            full.add("-".join(segments[:depth]))
    return full


def _build_magnitude_bitstream(named_addresses: set[str]) -> str:
    full = _prefix_closure(named_addresses)
    structure = encode_canonical_structure_from_addresses(sorted(full))
    decoded = decode_canonical_bitstream(structure.bitstream)
    if set(decoded.addresses) != full:
        raise SystemExit("SAMRAS magnitude roundtrip address-set mismatch")
    return structure.bitstream


def _row(datum_address: str, raw) -> AuthoritativeDatumDocumentRow:
    return AuthoritativeDatumDocumentRow(datum_address=datum_address, raw=raw)


def _as_rows(document: AuthoritativeDatumDocument) -> list[AuthoritativeDatumDocumentRow]:
    out: list[AuthoritativeDatumDocumentRow] = []
    for r in document.rows:
        if isinstance(r, AuthoritativeDatumDocumentRow):
            out.append(r)
        else:
            out.append(AuthoritativeDatumDocumentRow(datum_address=r["datum_address"], raw=r["raw"]))
    return out


def _rebuild_document(
    *,
    existing: AuthoritativeDatumDocument,
    overlay: dict[str, AuthoritativeDatumDocumentRow],
    name: str,
) -> tuple[AuthoritativeDatumDocument, str]:
    """Existing rows kept in order with overlay replacements applied in place;
    overlay rows for never-seen addresses appended. Re-derives canonical id from
    the content hash (order-independent; idempotent)."""
    out: list[AuthoritativeDatumDocumentRow] = []
    seen: set[str] = set()
    for r in _as_rows(existing):
        a = r.datum_address
        if a in overlay:
            out.append(overlay[a])
            seen.add(a)
        else:
            out.append(r)
    for a, r in overlay.items():
        if a not in seen:
            out.append(r)
    return _finalize(dataclasses.replace(existing, rows=tuple(out)), name)


def _finalize(candidate: AuthoritativeDatumDocument, name: str) -> tuple[AuthoritativeDatumDocument, str]:
    placeholder = format_canonical_document_id(
        prefix="lv", msn_id=MSN_ID, sandbox=SANDBOX, name=name, version_hash="0" * 64
    )
    candidate = dataclasses.replace(candidate, document_id=placeholder)
    identity = compute_mss_hash(candidate)
    real_hash = identity["version_hash"]
    if real_hash.startswith("sha256:"):
        real_hash = real_hash[len("sha256:"):]
    real_id = format_canonical_document_id(
        prefix="lv", msn_id=MSN_ID, sandbox=SANDBOX, name=name, version_hash=real_hash
    )
    return dataclasses.replace(candidate, document_id=real_id), real_hash


def _make_new_doc(name: str, rows: list[AuthoritativeDatumDocumentRow], *, metadata: dict) -> tuple[AuthoritativeDatumDocument, str]:
    candidate = AuthoritativeDatumDocument(
        document_id=format_canonical_document_id(
            prefix="lv", msn_id=MSN_ID, sandbox=SANDBOX, name=name, version_hash="0" * 64),
        source_kind="sandbox_source",
        document_name=f"lv.{MSN_ID}.{SANDBOX}.{name}",
        relative_path=f"sandbox/agro-erp/lv.{MSN_ID}.{SANDBOX}.{name}.json",
        canonical_name=name,
        tool_id=SANDBOX,
        is_anchor=False,
        document_metadata=metadata,
        rows=tuple(rows),
    )
    return _finalize(candidate, name)


def _upsert_documents_row(authority_db: Path, *, name: str, document_id: str, version_hash: str, is_anchor: bool) -> None:
    now = int(time.time() * 1000)
    conn = sqlite3.connect(authority_db)
    try:
        conn.execute(
            "DELETE FROM documents WHERE tenant_id=? AND sandbox=? AND name=?",
            (TENANT, SANDBOX, name),
        )
        conn.execute(
            "INSERT INTO documents (tenant_id, document_id, prefix, msn_id, sandbox, name, "
            "version_hash, is_anchor, origin, created_at) VALUES (?, ?, 'lv', ?, ?, ?, ?, ?, 'local', ?)",
            (TENANT, document_id, MSN_ID, SANDBOX, name, f"sha256:{version_hash}", 1 if is_anchor else 0, now),
        )
        conn.commit()
    finally:
        conn.close()


def _hdr(addr: str, value: str) -> AuthoritativeDatumDocumentRow:
    """Static header row (provenance). Idempotent: no timestamps."""
    return _row(addr, [[addr, "~", "0-0-0"], [value]])


# --------------------------------------------------------------------------- #
# LCL extension (reuse-by-title; mint absent)
# --------------------------------------------------------------------------- #
class LclBuilder:
    """Extends the lcl node-address tree with reuse-by-title idempotency."""

    def __init__(self, lcl_rows: list[AuthoritativeDatumDocumentRow]):
        self.label_to_node: dict[str, str] = {}
        self.node_set: set[str] = set()
        self.max_42 = 0
        self.child_max: dict[str, int] = {}
        for r in lcl_rows:
            if not r.datum_address.startswith("4-2-"):
                continue
            self.max_42 = max(self.max_42, int(r.datum_address.split("-")[2]))
            head = r.raw[0]
            node = str(head[2]) if len(head) >= 3 else None
            label = str(r.raw[1][0]) if len(r.raw) > 1 and r.raw[1] else ""
            if not node:
                continue
            self.node_set.add(node)
            self.label_to_node.setdefault(label.lower(), node)
            parent = node.rsplit("-", 1)[0] if "-" in node else "<root>"
            ordn = int(node.rsplit("-", 1)[1]) if "-" in node else int(node)
            self.child_max[parent] = max(self.child_max.get(parent, 0), ordn)
        self.overlay: dict[str, AuthoritativeDatumDocumentRow] = {}
        self._next_42 = self.max_42 + 1

    def _add_row(self, node: str, label: str, marker: str) -> None:
        key = f"4-2-{self._next_42}"
        self._next_42 += 1
        self.overlay[key] = _row(
            key, [[key, marker, node, RF_TITLE, _encode_label_bits(label)], [label]]
        )
        self.node_set.add(node)
        self.label_to_node[label.lower()] = node
        parent = node.rsplit("-", 1)[0] if "-" in node else "<root>"
        ordn = int(node.rsplit("-", 1)[1]) if "-" in node else int(node)
        self.child_max[parent] = max(self.child_max.get(parent, 0), ordn)

    def ensure(self, node: str, label: str, marker: str) -> str:
        """Ensure a fixed-address titled node exists; reuse by title."""
        if label.lower() in self.label_to_node:
            return self.label_to_node[label.lower()]
        self._add_row(node, label, marker)
        return node

    def mint_child(self, parent: str, label: str, marker: str) -> str:
        """Mint (or reuse-by-title) the next contiguous child under ``parent``."""
        if label.lower() in self.label_to_node:
            return self.label_to_node[label.lower()]
        nxt = self.child_max.get(parent, 0) + 1
        node = f"{parent}-{nxt}"
        self._add_row(node, label, marker)
        return node


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
@dataclasses.dataclass
class BuildResult:
    docs: dict[str, AuthoritativeDatumDocument]
    hashes: dict[str, str]
    prior_ids: dict[str, str | None]
    report: dict
    expect: dict


def _date_label(d: tuple[int, int, int]) -> str:
    return f"{d[0]:02d}{d[1]:02d}{d[2]}"


def build(store: SqliteSystemDatumStoreAdapter) -> BuildResult:
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    live: dict[str, AuthoritativeDatumDocument] = {}
    cts_anchor: AuthoritativeDatumDocument | None = None
    for d in catalog.documents:
        if f".{SANDBOX}." in d.document_id:
            live[d.document_id.split(".")[3]] = d
        elif ".cts_gis.anchor." in d.document_id:
            cts_anchor = d
    for name in ("anchor", "lcl"):
        if name not in live:
            raise SystemExit(f"live agro_erp.{name} not found in catalog")
    if cts_anchor is None:
        raise SystemExit("cts_gis anchor (HOPS-chronological schema source) not found")

    report: dict = {}

    # --- chronology authority (from cts_gis time schema) ---------------------
    cts_rows = {r.datum_address: r.raw for r in _as_rows(cts_anchor)}
    chrono_mag = str(cts_rows["1-1-5"][0][2])  # cts HOPS-chronological magnitude bits
    schema_payload = schema_from_anchor_payload(
        {"1-1-1": [["1-1-1", ANCHOR_TIME_PRIMITIVE, chrono_mag], ["HOPS-chronological"]]}
    )
    if not schema_payload.get("ok"):
        raise SystemExit(f"cts time schema decode failed: {schema_payload.get('error')}")
    chrono = build_chronology_authority(
        schema_payload=schema_payload,
        quadrennium_payload={"3-1-1": [["3-1-1", "~", "0"], ["quadrennium"]]},
        cosmological_prefix=(0, 0),
    )
    report["time_denotations"] = schema_payload["schema"]["denotations"]

    # --- LCL extension -------------------------------------------------------
    lcl_rows = _as_rows(live["lcl"])
    lb = LclBuilder(lcl_rows)
    # contact branch + suppliers
    lb.ensure(LCL_CONTACT_TYPE, "contact", RF_TXA_ID)
    supplier_node: dict[str, str] = {}
    for supplier in dict.fromkeys(e[0] for e in SUPPLY_INVOICE):
        supplier_node[supplier] = lb.mint_child(LCL_CONTACT_TYPE, supplier, RF_LCL_ID)
    # invoice branch + one node per line
    lb.ensure(LCL_INVOICE_TYPE, "invoice", RF_TXA_ID)
    invoice_node: list[str] = []
    for supplier, product, _dollars, _weight, d in SUPPLY_INVOICE:
        label = f"{supplier}_{product}_{_date_label(d)}"
        invoice_node.append(lb.mint_child(LCL_INVOICE_TYPE, label, RF_LCL_ID))
    # contract type node (instances deferred)
    lb.ensure(LCL_CONTRACT_TYPE, "contract", RF_TXA_ID)
    # product leaves (one per unique SKU)
    product_node: dict[str, str] = {}
    for product in dict.fromkeys(e[1] for e in SUPPLY_INVOICE):
        product_node[product] = lb.mint_child(LCL_PRODUCT_TYPE, product, RF_LCL_ID)

    new_lcl, lcl_hash = _rebuild_document(existing=live["lcl"], overlay=lb.overlay, name="lcl")
    report["lcl_rows_added"] = len(lb.overlay)
    report["lcl_node_count"] = len(lb.node_set)
    report["lcl_closure"] = len(_prefix_closure(lb.node_set))

    # plot nodes must already exist
    for pn in LCL_PLOT_NODES:
        if pn not in lb.node_set:
            raise SystemExit(f"expected land plot node {pn} missing from lcl")

    # --- anchor extension ----------------------------------------------------
    lcl_samras_bits = _build_magnitude_bitstream(lb.node_set)
    anchor_overlay: dict[str, AuthoritativeDatumDocumentRow] = {
        ANCHOR_HOPS_CHRONO_MAG: _row(ANCHOR_HOPS_CHRONO_MAG, [[ANCHOR_HOPS_CHRONO_MAG, ANCHOR_TIME_PRIMITIVE, chrono_mag], ["HOPS-chronological"]]),
        ANCHOR_HOPS_CHRONO_SPACE: _row(ANCHOR_HOPS_CHRONO_SPACE, [[ANCHOR_HOPS_CHRONO_SPACE, "~", ANCHOR_HOPS_CHRONO_MAG], ["HOPS-space-chronological"]]),
        ANCHOR_HOPS_UTC_BABELETTE: _row(ANCHOR_HOPS_UTC_BABELETTE, [[ANCHOR_HOPS_UTC_BABELETTE, ANCHOR_HOPS_CHRONO_SPACE, "0"], ["HOPS-babelette-UTC"]]),
        ANCHOR_NOMINAL_ABS: _row(ANCHOR_NOMINAL_ABS, [[ANCHOR_NOMINAL_ABS, ANCHOR_NOMINAL_BASE, "17"], ["nominal-256-17"]]),
        ANCHOR_NOMINAL_BABELETTE: _row(ANCHOR_NOMINAL_BABELETTE, [[ANCHOR_NOMINAL_BABELETTE, ANCHOR_NOMINAL_ABS, "0"], ["nominal-babelette"]]),
        ANCHOR_LCL_SAMRAS: _row(ANCHOR_LCL_SAMRAS, [[ANCHOR_LCL_SAMRAS, "0-0-5", lcl_samras_bits], ["lcl-SAMRAS"]]),
        "1-0-3": _row("1-0-3", [["1-0-3", "~", ANCHOR_FILE_PRIMITIVE], [f"sc.{MSN_ID}.{SANDBOX}.contacts.<hash>.json"]]),
        "1-0-4": _row("1-0-4", [["1-0-4", "~", ANCHOR_FILE_PRIMITIVE], [f"sc.{MSN_ID}.{SANDBOX}.invoices.<hash>.json"]]),
        "1-0-5": _row("1-0-5", [["1-0-5", "~", ANCHOR_FILE_PRIMITIVE], [f"sc.{MSN_ID}.{SANDBOX}.contracts.<hash>.json"]]),
        "1-0-6": _row("1-0-6", [["1-0-6", "~", ANCHOR_FILE_PRIMITIVE], [f"sc.{MSN_ID}.{SANDBOX}.plots.<hash>.json"]]),
    }
    new_anchor, anchor_hash = _rebuild_document(existing=live["anchor"], overlay=anchor_overlay, name="anchor")

    # --- CONTACTS doc --------------------------------------------------------
    contacts_rows = [
        _hdr("0-0-1", "mycite.v2.datum.agro_erp.contacts.v1"),
        _hdr("0-0-2", SANDBOX),
        _hdr("0-0-3", MSN_ID),
    ]
    dangling: list[str] = []
    for i, supplier in enumerate(supplier_node, start=1):
        email, phone, website = CONTACT_PLACEHOLDER.get(supplier, ("", "", ""))
        addr = f"4-{CONTACTS_VG}-{i}"
        # title/email/phone/website are free-text strings -> 512-bit title-babelette
        # (nominal-256-17 is reserved for the numeric weight/cost/amount placeholders).
        head = [
            addr,
            RF_LCL_ID, supplier_node[supplier],
            RF_TITLE, _encode_label_bits(supplier, bits=TITLE_BITS),
            RF_TITLE, _encode_label_bits(email, bits=TITLE_BITS),
            RF_TITLE, _encode_label_bits(phone, bits=TITLE_BITS),
            RF_TITLE, _encode_label_bits(website, bits=TITLE_BITS),
        ]
        contacts_rows.append(_row(addr, [head, [supplier]]))
        if supplier_node[supplier] not in lb.node_set:
            dangling.append(f"contacts {addr} supplier={supplier_node[supplier]}")
    contacts_doc, contacts_hash = _make_new_doc(
        "contacts", contacts_rows, metadata={"schema": "mycite.v2.datum.agro_erp.contacts.v1", "note": "supplier/contact directory"}
    )

    # --- INVOICES doc --------------------------------------------------------
    invoices_rows = [
        _hdr("0-0-1", "mycite.v2.datum.agro_erp.invoices.v1"),
        _hdr("0-0-2", SANDBOX),
        _hdr("0-0-3", MSN_ID),
    ]
    for idx, (supplier, product, dollars, weight, d) in enumerate(SUPPLY_INVOICE, start=1):
        addr = f"4-{INVOICES_VG}-{idx}"
        hops_date = encode_utc_datetime_as_hops(datetime(d[2], d[0], d[1], tzinfo=UTC), authority=chrono)
        head = [
            addr,
            RF_LCL_ID, invoice_node[idx - 1],
            RF_UTC, hops_date,
            RF_LCL_ID, product_node[product],
            RF_NOMINAL, _encode_label_bits(weight, bits=NOMINAL_BITS),
            RF_NOMINAL, _encode_label_bits(f"${dollars}", bits=NOMINAL_BITS),
            RF_LCL_ID, supplier_node[supplier],
        ]
        invoices_rows.append(_row(addr, [head, [f"{supplier}_{product}"]]))
        for node, lbl in ((invoice_node[idx - 1], "invoice_id"), (product_node[product], "product_id"), (supplier_node[supplier], "supplier")):
            if node not in lb.node_set:
                dangling.append(f"invoices {addr} {lbl}={node}")
    invoices_doc, invoices_hash = _make_new_doc(
        "invoices", invoices_rows, metadata={"schema": "mycite.v2.datum.agro_erp.invoices.v1", "note": "supply invoice line items"}
    )

    # --- CONTRACTS doc (header-only) -----------------------------------------
    contracts_rows = [
        _hdr("0-0-1", "mycite.v2.datum.agro_erp.contracts.v1"),
        _hdr("0-0-2", SANDBOX),
        _hdr("0-0-3", MSN_ID),
        _hdr("0-0-4", "archetype:4-5-N=[date,invoice_id,plot_id,amount,cost]; rows filled by farm-plan workflow"),
    ]
    contracts_doc, contracts_hash = _make_new_doc(
        "contracts", contracts_rows, metadata={"schema": "mycite.v2.datum.agro_erp.contracts.v1", "note": "contract ledger (structure only; instances deferred)"}
    )

    # --- PLOTS doc (farm_profile-style HOPS geometry) ------------------------
    plots_rows = [_hdr("0-0-1", "mycite.v2.datum.agro_erp.plots.v1")]
    for i, plot_node in enumerate(LCL_PLOT_NODES, start=1):
        verts = PLOT_RINGS[plot_node]
        ring_addr = f"4-{len(verts)}-{i}"
        ring_head = [ring_addr]
        for lon, lat in verts:
            ring_head += [RF_COORD, encode_hops_coordinate(lon, lat)]
        plots_rows.append(_row(ring_addr, [ring_head, [f"plot_{i}_ring"]]))
        poly_addr = f"5-0-{i}"
        plots_rows.append(_row(poly_addr, [[poly_addr, "~", ring_addr], [f"plot_{i}_polygon"]]))
        fil_addr = f"7-{i}-1"
        label = f"plot_{i}"
        plots_rows.append(_row(fil_addr, [[fil_addr, RF_LCL_ID, plot_node, RF_TITLE, _encode_label_bits(label), poly_addr, "1"], [label]]))
    plots_doc, plots_hash = _make_new_doc(
        "plots", plots_rows, metadata={"schema": "mycite.v2.datum.agro_erp.plots.v1", "note": "plot HOPS geometry (placeholder coords; fits-in-field is a vision, not enforced)"}
    )

    # --- validation gate -----------------------------------------------------
    issues: list[str] = []
    for doc, vg in ((contacts_doc, CONTACTS_VG), (invoices_doc, INVOICES_VG)):
        for r in _as_rows(doc):
            if not r.datum_address.startswith(f"4-{vg}-"):
                continue
            v = validate_row(r.datum_address, r.raw)
            if v:
                issues.append(f"{doc.canonical_name} {r.datum_address}: {v}")
            s = classify_row(r.datum_address, r.raw)
            if not (s.shape == "pairs" and s.value_group == vg and s.pair_count == vg and s.well_formed):
                issues.append(f"{doc.canonical_name} {r.datum_address}: classify {s.shape}/vg{s.value_group}/pairs{s.pair_count}/wf{s.well_formed}")
    # date roundtrip sanity (decode back)
    for r in _as_rows(invoices_doc):
        if r.datum_address.startswith(f"4-{INVOICES_VG}-"):
            hops = r.raw[0][4]
            if hops.count("-") < 5:
                issues.append(f"invoices {r.datum_address}: bad hops date {hops}")
    if issues:
        raise SystemExit(f"validation gate failed ({len(issues)}): {issues[:5]}")
    if dangling:
        raise SystemExit(f"dangling cross-refs ({len(dangling)}): {dangling[:5]}")

    docs = {
        "anchor": new_anchor, "lcl": new_lcl, "contacts": contacts_doc,
        "invoices": invoices_doc, "contracts": contracts_doc, "plots": plots_doc,
    }
    hashes = {
        "anchor": anchor_hash, "lcl": lcl_hash, "contacts": contacts_hash,
        "invoices": invoices_hash, "contracts": contracts_hash, "plots": plots_hash,
    }
    prior_ids = {n: (live[n].document_id if n in live else None) for n in docs}
    report["row_counts"] = {n: len(d.rows) for n, d in docs.items()}
    report["product_leaves_minted"] = sum(1 for p in product_node.values())
    expect = {
        "row_counts": report["row_counts"],
        "lcl_closure": report["lcl_closure"],
    }
    return BuildResult(docs=docs, hashes=hashes, prior_ids=prior_ids, report=report, expect=expect)


# --------------------------------------------------------------------------- #
# Report + verify
# --------------------------------------------------------------------------- #
def _print_report(result: BuildResult, *, dry_run: bool) -> None:
    r = result.report
    print("\n================ LEDGER INGEST PLAN ================")
    print(f"time denotations (UTC radices): {r['time_denotations']}")
    print(f"lcl rows added                : {r['lcl_rows_added']}")
    print(f"lcl node count / closure      : {r['lcl_node_count']} / {r['lcl_closure']}")
    print(f"product leaves                : {r['product_leaves_minted']}")
    print("derived document ids:")
    for name in ("anchor", "lcl", "contacts", "invoices", "contracts", "plots"):
        d = result.docs[name]
        prior = result.prior_ids[name]
        tag = "(new)" if prior is None else ("(unchanged)" if d.document_id == prior else "(CHANGED)")
        print(f"  {name:11} rows={len(d.rows):5}  …{d.document_id.split('.')[-1][:14]}  {tag}")
    print("====================================================")
    if dry_run:
        print("DRY RUN — nothing written.\n")


def _verify_live(authority_db: Path, *, expect: dict) -> None:
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    docs = {d.document_id.split(".")[3]: d for d in catalog.documents if f".{SANDBOX}." in d.document_id}
    failures: list[str] = []
    for name, n in expect["row_counts"].items():
        if name not in docs:
            failures.append(f"{name} missing from catalog")
        elif len(docs[name].rows) != n:
            failures.append(f"{name} rows={len(docs[name].rows)} expected {n}")
    # lcl-SAMRAS roundtrip closure
    anchor_rows = _as_rows(docs["anchor"])
    bits = next((r.raw[0][2] for r in anchor_rows if r.datum_address == ANCHOR_LCL_SAMRAS), None)
    if bits is None:
        failures.append("anchor 1-1-5 missing")
    elif len(decode_canonical_bitstream(bits).addresses) != expect["lcl_closure"]:
        failures.append(f"1-1-5 closure {len(decode_canonical_bitstream(bits).addresses)} != {expect['lcl_closure']}")
    # new HOPS-chronological spine present
    for addr in (ANCHOR_HOPS_CHRONO_MAG, ANCHOR_HOPS_UTC_BABELETTE, ANCHOR_NOMINAL_ABS, ANCHOR_NOMINAL_BABELETTE):
        if not any(r.datum_address == addr for r in anchor_rows):
            failures.append(f"anchor {addr} missing")
    # invoice rows classify clean
    bad = [r.datum_address for r in _as_rows(docs["invoices"])
           if r.datum_address.startswith(f"4-{INVOICES_VG}-") and classify_row(r.datum_address, r.raw).issues]
    if bad:
        failures.append(f"{len(bad)} invoice rows with classify issues")
    if failures:
        raise SystemExit("POST-WRITE VERIFY FAILED:\n  " + "\n  ".join(failures))
    print("[verify] post-write checks PASSED")


def run(*, authority_db: Path, dry_run: bool) -> dict:
    if not authority_db.exists():
        raise SystemExit(f"authority db missing: {authority_db}")
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    result = build(store)
    _print_report(result, dry_run=dry_run)
    if dry_run:
        return {"status": "dry_run", **result.report}

    # STEP 0 — mandatory backup
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    backup = authority_db.with_name(authority_db.name + f".pre-ledger-{stamp}.bak")
    if backup.exists():
        raise SystemExit(f"backup target already exists: {backup}")
    shutil.copy2(authority_db, backup)
    print(f"[backup] {backup}")

    order = ["anchor", "lcl", "contacts", "invoices", "contracts", "plots"]
    for name in order:
        doc = result.docs[name]
        if doc.document_id == result.prior_ids[name]:
            print(f"[skip] {name} already current")
            continue
        store.replace_single_document_efficient(
            tenant_id=TENANT, prior_document_id=result.prior_ids[name], updated_document=doc
        )
        _upsert_documents_row(
            authority_db, name=name, document_id=doc.document_id,
            version_hash=result.hashes[name], is_anchor=(name == "anchor"),
        )
        print(f"[write] {name} → …{doc.document_id.split('.')[-1][:14]}")

    _verify_live(authority_db, expect=result.expect)
    return {"status": "applied", "backup": str(backup), **result.report,
            "document_ids": {n: result.docs[n].document_id for n in order}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--authority-db", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    result = run(authority_db=args.authority_db, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
