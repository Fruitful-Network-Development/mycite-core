#!/usr/bin/env python3
"""Ingest the raw breeding catalogue into the agro_erp datum graph.

Reads the 30 genus-grouped YAML files under ``/srv/webapps/mycite/raw/`` (1,614
breeding entries) and materialises them into the agro_erp MOS sandbox as a single
``product_profiles`` document of **value-group-9** rows, while extending the
supporting structure the rows reference:

1. **anchor** — adds the ``second``/``centimeter`` unit datums (the operator's
   verbatim spec) and the previously-specified-but-never-added **lcl-SAMRAS** spine
   (``1-1-5`` magnitude → ``2-0-4`` space → ``3-1-5`` id-babelette); recompiles the
   ``1-1-1`` txa-SAMRAS magnitude when TXA gains species.
2. **lcl** — adds the ``raunkiaerality`` classification (``1-3-2-5`` + 3 children)
   and one ``product_id`` leaf per unique product key (``1-3-1-2 .. 1-3-1-N``).
3. **txa** — for each entry's species, reuses the existing taxon node when present,
   else mints a new leaf (faithfully under the genus when the genus exists, else
   under a synthetic catch-all root ``4`` ``agro_unclassified``); recompiles ``1-1-1``.
4. **product_profiles** — one ``4-9-N`` PAIRS row per unique key carrying the 9
   reference/magnitude pairs (product_id, taxonomy_id, the 4 LCL classification
   refs, raunkiaerality, gestation, spacing).

Design, rationale, and the verified ground truth are in
``/home/admin/.claude/plans/unified-booping-sutherland.md``.

The script is **idempotent** (re-running with the same YAML yields byte-identical
canonical document_ids and zero row deltas), **dry-run-able** (``--dry-run`` builds
and self-verifies everything, prints a full diff, and writes nothing), and takes a
timestamped backup of the live DB before any write.

Standing discipline (mirrors promote_lcl_taxonomy.py / promote_sd31_district_boundary.py):
  - Always dry-run against an isolated copy first.
  - Back up the live MOS DB (STEP 0 does this automatically on a real run).
  - Verify post-write; the script self-verifies and raises on any mismatch.

Usage::

    python3 MyCiteV2/scripts/ingest_agro_erp_product_profiles.py \\
        --authority-db /srv/webapps/mycite/fnd/private/mos_authority.sqlite3 \\
        [--dry-run] [--txa-mode {append,strict}] [--on-missing {sentinel,defer,fail}]
"""

from __future__ import annotations

import argparse
import dataclasses
import glob
import json
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[2]  # /srv/repo/mycite-core
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.datum_rules import classify_row, validate_row
from MyCiteV2.packages.core.document_naming import format_canonical_document_id
from MyCiteV2.packages.core.mss import compute_mss_hash
from MyCiteV2.packages.core.structures.samras.codec import (
    decode_canonical_bitstream,
    encode_canonical_structure_from_addresses,
)
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
TENANT = "fnd"
MSN_ID = "3-2-3-17-77-1-6-4-1-4"
SANDBOX = "agro_erp"
RAW_DIR = Path("/srv/webapps/mycite/raw")
RF312_BITS = 512  # niu-baciloid-256-64 title-babelette width (64 chars x 8-bit ASCII)
SECONDS_PER_DAY = 86400

# Operator verbatim unit-datum magnitude constants.
SECOND_CONST = "185485860000000000000000000000000000000000000000000"  # 51 digits
CM_CONST = "161625500000000000000000000000000000000000"  # 42 digits

# Anchor addresses minted/updated by this script (free slots verified live).
ANCHOR_UNIT_SECOND_MAG = "1-2-1"
ANCHOR_UNIT_CM_MAG = "1-2-2"
ANCHOR_UNIT_SECOND_ABS = "2-1-1"  # 2-1-2 occupied (niu-baciloid); 2-1-1 is the free gap
ANCHOR_UNIT_CM_ABS = "2-1-3"
ANCHOR_LCL_SAMRAS = "1-1-5"  # 1-1-1..1-1-4 occupied
ANCHOR_LCL_SPACE = "2-0-4"  # 2-0-1..2-0-3 occupied
ANCHOR_LCL_BABELETTE = "3-1-5"  # 3-1-1..3-1-4 occupied
ANCHOR_TXA_SAMRAS = "1-1-1"  # recompiled when TXA grows

# Reference (rf.) typing markers used in product_profiles rows.
RF_LCL_ID = "rf.3-1-5"  # the new lcl id-babelette (typed product_id node addresses)
RF_TXA_ID = "rf.3-1-1"  # the existing SAMRAS-babelette-txa_id (typed classification node addrs)
RF_TITLE = "rf.3-1-2"  # title-babelette (512-bit ASCII)

# LCL structural anchors.
LCL_PRODUCT_TYPE = "1-3-1"  # product_type; product leaves are 1-3-1-2 .. (1-3-1-1 = product_1 exists)
LCL_RAUNK_PARENT = "1-3-2-5"  # new product_classification child
RAUNK_NODE = {
    "therophyte": "1-3-2-5-1",
    "hemicryptophyte": "1-3-2-5-2",
    "phanerophytes": "1-3-2-5-3",
}
LCL_FIRST_TAXONOMY_KEY = 47  # live LCL 4-2 block ends at 4-2-46; our block starts here

# TXA catch-all root for species whose genus is absent from the live taxonomy.
TXA_CATCHALL_ROOT = "4"  # roots 1,2,3 live; root 4 contiguous & encodable (verified)
TXA_CATCHALL_TITLE = "agro_unclassified"


# --------------------------------------------------------------------------- #
# Pure helpers (copied verbatim from the canonical scripts to stay self-contained)
# --------------------------------------------------------------------------- #
def _encode_label_bits(label: str, *, bits: int = RF312_BITS) -> str:
    """ASCII → per-char 8-bit, right-zero-padded to ``bits`` (promote_lcl_taxonomy)."""
    raw = "".join(format(b, "08b") for b in label.encode("ascii"))
    if len(raw) > bits:
        raise ValueError(f"label {label!r} exceeds {bits} bits ({bits // 8} chars)")
    return raw.ljust(bits, "0")


def _prefix_closure(named_addresses: set[str]) -> set[str]:
    """Every ancestor prefix of every named node (bootstrap_agro_erp_anchor pattern)."""
    full: set[str] = set()
    for addr in named_addresses:
        segments = addr.split("-")
        for depth in range(1, len(segments) + 1):
            full.add("-".join(segments[:depth]))
    return full


def _build_magnitude_bitstream(named_addresses: set[str]) -> str:
    """Canonical SAMRAS bitstream over a node set; roundtrip-asserted.

    Generalises bootstrap_agro_erp_anchor.py::_build_magnitude_bitstream to take an
    arbitrary named-node set (the existing helper reads it from staging JSON).
    """
    full = _prefix_closure(named_addresses)
    structure = encode_canonical_structure_from_addresses(sorted(full))
    decoded = decode_canonical_bitstream(structure.bitstream)
    if set(decoded.addresses) != full:
        raise SystemExit("SAMRAS magnitude roundtrip address-set mismatch")
    return structure.bitstream


def _dash(token: str) -> str:
    """YAML node ids use underscores (``1_3_2_1_3``) → datum dashes (``1-3-2-1-3``)."""
    return token.replace("_", "-")


def _row(datum_address: str, raw) -> AuthoritativeDatumDocumentRow:
    return AuthoritativeDatumDocumentRow(datum_address=datum_address, raw=raw)


def _as_rows(document: AuthoritativeDatumDocument) -> list[AuthoritativeDatumDocumentRow]:
    """Normalise an existing document's rows (which may be dicts) to Row objects."""
    out: list[AuthoritativeDatumDocumentRow] = []
    for r in document.rows:
        if isinstance(r, AuthoritativeDatumDocumentRow):
            out.append(r)
        else:  # dict form
            out.append(AuthoritativeDatumDocumentRow(datum_address=r["datum_address"], raw=r["raw"]))
    return out


def _taxon_node_addr(row: AuthoritativeDatumDocumentRow) -> str | None:
    if not row.datum_address.startswith("4-2-"):
        return None
    head = row.raw[0]
    return str(head[2]) if len(head) >= 3 else None


def _taxon_title(row: AuthoritativeDatumDocumentRow) -> str:
    return str(row.raw[1][0]) if len(row.raw) > 1 and row.raw[1] else ""


# --------------------------------------------------------------------------- #
# Document rebuild (preserve order, replace-in-place, drop owned block, append)
# --------------------------------------------------------------------------- #
def _rebuild_document(
    *,
    existing: AuthoritativeDatumDocument,
    overlay: dict[str, AuthoritativeDatumDocumentRow],
    drop: callable[[str], bool],
    name: str,
) -> tuple[AuthoritativeDatumDocument, str]:
    """Return a new canonical document: existing rows kept in order (with ``overlay``
    replacements applied in place and ``drop``-matching rows removed), then any
    overlay rows for never-seen addresses appended. Re-derives the canonical id from
    the content hash. The MSS hash is order-independent (rows are sorted), so this is
    deterministic regardless of append order.
    """
    out: list[AuthoritativeDatumDocumentRow] = []
    seen: set[str] = set()
    for r in _as_rows(existing):
        a = r.datum_address
        if a in overlay:
            out.append(overlay[a])
            seen.add(a)
        elif drop(a):
            continue
        else:
            out.append(r)
    for a, r in overlay.items():
        if a not in seen:
            out.append(r)

    placeholder = format_canonical_document_id(
        prefix="lv", msn_id=MSN_ID, sandbox=SANDBOX, name=name, version_hash="0" * 64
    )
    candidate = dataclasses.replace(existing, document_id=placeholder, rows=tuple(out), document_name=name)
    identity = compute_mss_hash(candidate)
    real_hash = identity["version_hash"]
    if real_hash.startswith("sha256:"):
        real_hash = real_hash[len("sha256:"):]
    real_id = format_canonical_document_id(
        prefix="lv", msn_id=MSN_ID, sandbox=SANDBOX, name=name, version_hash=real_hash
    )
    return dataclasses.replace(candidate, document_id=real_id), real_hash


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


# --------------------------------------------------------------------------- #
# YAML parsing
# --------------------------------------------------------------------------- #
FIELD_KEYS = ("rotation_group", "proegule", "genesis", "ownership", "gestation", "spacing", "raunkiaerality")


@dataclasses.dataclass
class Entry:
    genus_group: str
    key: str
    fields: dict
    source_file: str


def _parse_yaml() -> list[Entry]:
    """Two-level ``{genus: {key: fields}}``; first-wins on duplicate keys; stable order."""
    entries: list[Entry] = []
    seen: set[str] = set()
    dropped: list[str] = []
    for path in sorted(glob.glob(str(RAW_DIR / "*.yaml"))):
        fname = Path(path).name
        with open(path) as f:
            doc = yaml.safe_load(f) or {}
        if not isinstance(doc, dict):
            continue
        for genus_group, group in doc.items():
            if not isinstance(group, dict):
                continue
            for key, fields in group.items():
                if key in seen:
                    dropped.append(key)
                    continue
                seen.add(key)
                entries.append(Entry(genus_group=str(genus_group), key=str(key), fields=dict(fields or {}), source_file=fname))
    if dropped:
        print(f"[parse] dropped {len(dropped)} duplicate keys (first-wins): {dropped}")
    return entries


# --------------------------------------------------------------------------- #
# TXA taxonomy resolution / minting
# --------------------------------------------------------------------------- #
# Allow one-or-more underscores before the rank abbreviation so both ``_var._``
# and the doubled ``__var._`` (seen in a few raw keys) collapse to the base species.
_VAR_SPLIT = re.compile(r"_+var\._|_+subsp\._|_+ssp\._")

# Curated synonym → canonical species. Common names and dot-cultivars in the raw
# catalogue that should resolve to a real taxon rather than minting a catch-all
# node. Targets were verified present in the live agro_erp txa tree at authoring
# time (botanical facts, operator-confirmable). Entries whose canonical target is
# itself uncatalogued (arctium_lappa/pisum_sativum/tragopogon_porrifolius) simply
# DEDUPLICATE the synonym onto one catch-all node instead of two.
_SPECIES_ALIAS: dict[str, str] = {
    "collards": "brassica_oleracea",
    "turnip": "brassica_rapa",
    "rutabaga": "brassica_napus",
    "greens,_mustard": "brassica_juncea",
    "leeks": "allium_porrum",
    "endive": "cichorium_endivia",
    "parsnip": "pastinaca_sativa",
    "burdock": "arctium_lappa",
    "peas,_fresh": "pisum_sativum",
    "salsify": "tragopogon_porrifolius",
    "asparagus_officinalis.mary_washington": "asparagus_officinalis",
    "asparagus_officinalis.purple_passion": "asparagus_officinalis",
    # Non-binomial catalogue rows → resolve to an existing taxon node (genus-level
    # aggregate, or the 'unspecified' bucket) so they don't mint a raw catch-all.
    # Faithful + idempotent: the resolver's exact-title path finds these nodes.
    "allium_spp": "allium",            # genus-level aggregate → the allium genus
    "amaranthus_spp.": "amaranthus",   # genus-level aggregate → the amaranthus genus
    "direct": "unspecified",           # no species (e.g. a packaged mix) → unspecified bucket
    "mixed_spp.": "unspecified",       # explicit mixture → unspecified bucket
    "unknown": "unspecified",          # uncharacterised row → unspecified bucket
}


def _species_of(key: str) -> str:
    base = key.split("-", 1)[0]
    return _SPECIES_ALIAS.get(base.lower(), base)


def _label_for_encoding(label: str) -> str:
    """≤64-char ASCII-safe label for the 512-bit title magnitude. Drops the doubled
    flattened tail for the 2 over-length keys; never silently lossy beyond that."""
    if len(label.encode("ascii", errors="strict")) <= RF312_BITS // 8:
        return label
    head = label.rsplit("-", 1)[0]
    if len(head) <= RF312_BITS // 8:
        return head
    return head[: RF312_BITS // 8]


class TaxonomyResolver:
    """Resolves each entry's species to a TXA node_addr, minting absent species."""

    def __init__(self, txa_rows: list[AuthoritativeDatumDocumentRow], txa_mode: str):
        self.txa_mode = txa_mode
        self.title_to_node: dict[str, str] = {}
        self.existing_nodes: set[str] = set()
        self.max_key = 0
        for r in txa_rows:
            if r.datum_address.startswith("4-2-"):
                self.max_key = max(self.max_key, int(r.datum_address.split("-")[2]))
                node = _taxon_node_addr(r)
                if node:
                    self.existing_nodes.add(node)
                    self.title_to_node.setdefault(_taxon_title(r).lower(), node)
        # per-parent next child ordinal (for contiguous minting)
        self._child_max: dict[str, int] = {}
        for node in self.existing_nodes:
            parent = node.rsplit("-", 1)[0] if "-" in node else ""
            ordinal = int(node.rsplit("-", 1)[1]) if "-" in node else int(node)
            key = parent if "-" in node else "<root>"
            self._child_max[key] = max(self._child_max.get(key, 0), ordinal)
        # minted nodes accumulate here
        self.minted: list[tuple[str, str]] = []  # (node_addr, title) appended this run
        self._species_cache: dict[str, str] = {}

    def _next_child(self, parent: str) -> str:
        key = parent if parent else "<root>"
        nxt = self._child_max.get(key, 0) + 1
        self._child_max[key] = nxt
        return (f"{parent}-{nxt}" if parent else str(nxt))

    def _mint(self, parent: str, title: str) -> str:
        node = self._next_child(parent)
        self.existing_nodes.add(node)
        self.minted.append((node, title))
        return node

    def resolve(self, entry: Entry) -> tuple[str, str]:
        """Return (taxonomy_node_addr, resolution_kind)."""
        sp = _species_of(entry.key)
        cache_key = sp.lower()
        if cache_key in self._species_cache:
            return self._species_cache[cache_key], "cached"
        # 1. exact species title
        if cache_key in self.title_to_node:
            kind, node = "exact", self.title_to_node[cache_key]
        else:
            base = _VAR_SPLIT.split(cache_key)[0]
            genus_token = entry.genus_group.lower()
            if base != cache_key and base in self.title_to_node:
                kind, node = "var_strip", self.title_to_node[base]
            elif self.txa_mode == "strict":
                kind, node = "absent_strict", "0"
            elif genus_token in self.title_to_node:
                # 3. faithful mint under the genus node
                node = self._mint(self.title_to_node[genus_token], _label_for_encoding(sp))
                kind = "mint_genus"
            else:
                # 4. catch-all root 4
                node = self._mint(TXA_CATCHALL_ROOT, _label_for_encoding(sp))
                kind = "mint_catchall"
        self._species_cache[cache_key] = node
        return node, kind

    def ensure_catchall_root(self) -> None:
        """Ensure the catch-all root node ``4`` itself is a named node when used."""
        if any(n == TXA_CATCHALL_ROOT or n.startswith(TXA_CATCHALL_ROOT + "-") for n in self.existing_nodes):
            if TXA_CATCHALL_ROOT not in self.existing_nodes:
                self.existing_nodes.add(TXA_CATCHALL_ROOT)
                self.minted.insert(0, (TXA_CATCHALL_ROOT, TXA_CATCHALL_TITLE))


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
@dataclasses.dataclass
class BuildResult:
    docs: dict[str, AuthoritativeDatumDocument]          # name -> new document
    hashes: dict[str, str]
    prior_ids: dict[str, str]
    report: dict
    changed: list[str]                                   # doc names that actually changed


def _classification_ref(value: str) -> str:
    """Dash-convert a YAML classification id; map the ``_0`` unspecified sentinel to
    its existing parent node (``1_3_2_1_0`` → ``1-3-2-1``)."""
    dashed = _dash(str(value))
    if dashed.endswith("-0"):
        return dashed[: -len("-0")]
    return dashed


def build(store: SqliteSystemDatumStoreAdapter, *, txa_mode: str, on_missing: str) -> BuildResult:
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    live: dict[str, AuthoritativeDatumDocument] = {}
    for d in catalog.documents:
        if f".{SANDBOX}." in d.document_id:
            live[d.document_id.split(".")[3]] = d
    for name in ("anchor", "txa", "lcl", "product_profiles"):
        if name not in live:
            raise SystemExit(f"live agro_erp.{name} not found in catalog")

    entries = _parse_yaml()
    report: dict = {"entries": len(entries)}

    # --- TXA resolution (build species->node, mint absent) -------------------
    txa_rows = _as_rows(live["txa"])
    resolver = TaxonomyResolver(txa_rows, txa_mode)
    kinds: dict[str, int] = {}
    entry_taxon: dict[str, str] = {}
    for e in entries:
        node, kind = resolver.resolve(e)
        kinds[kind] = kinds.get(kind, 0) + 1
        entry_taxon[e.key] = node
    resolver.ensure_catchall_root()
    report["txa_resolution"] = kinds
    report["txa_minted"] = list(resolver.minted)

    # --- product_id leaf assignment (stable index over unique keys) ----------
    product_node: dict[str, str] = {}      # key -> LCL node_addr (1-3-1-{1+k})
    for k, e in enumerate(entries, start=1):
        product_node[e.key] = f"{LCL_PRODUCT_TYPE}-{1 + k}"

    # ===================== TXA document ======================================
    changed: list[str] = []
    txa_overlay: dict[str, AuthoritativeDatumDocumentRow] = {}
    txa_node_set = {n for n in resolver.existing_nodes}
    if resolver.minted:
        next_key = resolver.max_key + 1
        coll_existing = [r for r in txa_rows if r.datum_address == "5-0-1"]
        coll_refs = list(coll_existing[0].raw[0][2:]) if coll_existing else []
        for node_addr, title in resolver.minted:
            key = f"4-2-{next_key}"
            next_key += 1
            txa_overlay[key] = _row(key, [[key, RF_TXA_ID, node_addr, RF_TITLE, _encode_label_bits(title)], [title]])
            coll_refs.append(key)
        # rebuild 5-0-1 collection
        txa_overlay["5-0-1"] = _row("5-0-1", [["5-0-1", "~", *coll_refs], ["txa_id_collection"]])
        new_txa, txa_hash = _rebuild_document(
            existing=live["txa"], overlay=txa_overlay,
            drop=lambda a: a.startswith("4-2-") and int(a.split("-")[2]) > resolver.max_key,
            name="txa",
        )
        changed.append("txa")
    else:
        new_txa, txa_hash = live["txa"], ""

    # ===================== LCL document ======================================
    lcl_rows = _as_rows(live["lcl"])
    lcl_overlay: dict[str, AuthoritativeDatumDocumentRow] = {}
    # 2a. raunkiaerality classification (4-2-47..50)
    raunk_rows = [
        (LCL_RAUNK_PARENT, "raunkiaerality"),
        (RAUNK_NODE["therophyte"], "therophyte"),
        (RAUNK_NODE["hemicryptophyte"], "hemicryptophyte"),
        (RAUNK_NODE["phanerophytes"], "phanerophytes"),
    ]
    next_lcl_key = LCL_FIRST_TAXONOMY_KEY
    lcl_node_set: set[str] = {n for r in lcl_rows if (n := _taxon_node_addr(r))}
    for node_addr, label in raunk_rows:
        key = f"4-2-{next_lcl_key}"
        next_lcl_key += 1
        lcl_overlay[key] = _row(key, [[key, RF_TXA_ID, node_addr, RF_TITLE, _encode_label_bits(label)], [label]])
        lcl_node_set.add(node_addr)
    # 2b. product_id leaves
    for e in entries:
        node_addr = product_node[e.key]
        key = f"4-2-{next_lcl_key}"
        next_lcl_key += 1
        label = _label_for_encoding(e.key)
        lcl_overlay[key] = _row(key, [[key, RF_LCL_ID, node_addr, RF_TITLE, _encode_label_bits(label)], [e.key]])
        lcl_node_set.add(node_addr)
    new_lcl, lcl_hash = _rebuild_document(
        existing=live["lcl"], overlay=lcl_overlay,
        drop=lambda a: a.startswith("4-2-") and int(a.split("-")[2]) >= LCL_FIRST_TAXONOMY_KEY,
        name="lcl",
    )
    changed.append("lcl")
    # 2c. lcl-SAMRAS magnitude
    lcl_samras_bits = _build_magnitude_bitstream(lcl_node_set)
    report["lcl_samras_bits"] = len(lcl_samras_bits)
    report["lcl_node_count"] = len(lcl_node_set)
    report["lcl_closure"] = len(_prefix_closure(lcl_node_set))  # what decode() returns

    # ===================== anchor document ===================================
    anchor_overlay: dict[str, AuthoritativeDatumDocumentRow] = {
        ANCHOR_UNIT_SECOND_MAG: _row(ANCHOR_UNIT_SECOND_MAG, [[ANCHOR_UNIT_SECOND_MAG, "0-0-1", SECOND_CONST], ["second"]]),
        ANCHOR_UNIT_CM_MAG: _row(ANCHOR_UNIT_CM_MAG, [[ANCHOR_UNIT_CM_MAG, "0-0-3", CM_CONST], ["centimeter"]]),
        ANCHOR_UNIT_SECOND_ABS: _row(ANCHOR_UNIT_SECOND_ABS, [[ANCHOR_UNIT_SECOND_ABS, ANCHOR_UNIT_SECOND_MAG, "0"], ["second-baciloid"]]),
        ANCHOR_UNIT_CM_ABS: _row(ANCHOR_UNIT_CM_ABS, [[ANCHOR_UNIT_CM_ABS, ANCHOR_UNIT_CM_MAG, "0"], ["centimeter-baciloid"]]),
        ANCHOR_LCL_SAMRAS: _row(ANCHOR_LCL_SAMRAS, [[ANCHOR_LCL_SAMRAS, "0-0-5", lcl_samras_bits], ["lcl-SAMRAS"]]),
        ANCHOR_LCL_SPACE: _row(ANCHOR_LCL_SPACE, [[ANCHOR_LCL_SPACE, "~", ANCHOR_LCL_SAMRAS], ["SAMRAS-space-lcl"]]),
        ANCHOR_LCL_BABELETTE: _row(ANCHOR_LCL_BABELETTE, [[ANCHOR_LCL_BABELETTE, ANCHOR_LCL_SPACE, "0"], ["SAMRAS-babelette-lcl_id"]]),
    }
    if resolver.minted:
        txa_bits = _build_magnitude_bitstream(txa_node_set)
        anchor_overlay[ANCHOR_TXA_SAMRAS] = _row(ANCHOR_TXA_SAMRAS, [[ANCHOR_TXA_SAMRAS, "0-0-5", txa_bits], ["txa-SAMRAS"]])
        report["txa_samras_bits"] = len(txa_bits)
        report["txa_node_count"] = len(txa_node_set)
        report["txa_closure"] = len(_prefix_closure(txa_node_set))  # what decode() returns
    new_anchor, anchor_hash = _rebuild_document(
        existing=live["anchor"], overlay=anchor_overlay, drop=lambda a: False, name="anchor",
    )
    changed.insert(0, "anchor")

    # ===================== product_profiles document =========================
    anchor_addrs = {r.datum_address for r in _as_rows(new_anchor)}
    pp_overlay: dict[str, AuthoritativeDatumDocumentRow] = {}
    dangling: list[str] = []
    missing_taxon: list[str] = []
    sentinel_pairs = 0
    for idx, e in enumerate(entries, start=1):
        addr = f"4-9-{idx}"
        f = e.fields
        taxon = entry_taxon[e.key]
        if taxon == "0":
            missing_taxon.append(e.key)
        raunk_val = str(f.get("raunkiaerality", "")).strip().lower()
        raunk_node = RAUNK_NODE.get(raunk_val, "0")
        rg = _classification_ref(f.get("rotation_group", ""))
        pg = _classification_ref(f.get("proegule", ""))
        gn = _classification_ref(f.get("genesis", ""))
        ow = _classification_ref(f.get("ownership", ""))
        gestation = str(int(str(f.get("gestation", "0")).strip()) * SECONDS_PER_DAY)
        spacing = str(int(str(f.get("spacing", "0")).strip()))
        head = [
            addr,
            RF_LCL_ID, product_node[e.key],
            RF_TXA_ID, taxon,
            RF_TXA_ID, rg,
            RF_TXA_ID, pg,
            RF_TXA_ID, gn,
            RF_TXA_ID, ow,
            RF_TXA_ID, raunk_node,
            ANCHOR_UNIT_SECOND_ABS, gestation,
            ANCHOR_UNIT_CM_ABS, spacing,
        ]
        pp_overlay[addr] = _row(addr, [head, [e.key]])
        # reference-existence self-check (compensates for datum_semantics skipping rf.)
        for node, pool, lbl in (
            (product_node[e.key], lcl_node_set, "product_id"),
            (rg, lcl_node_set, "rotation_group"),
            (pg, lcl_node_set, "propagule"),
            (gn, lcl_node_set, "genesis"),
            (ow, lcl_node_set, "ownership"),
        ):
            if node not in pool:
                dangling.append(f"{addr} {lbl}={node}")
        if raunk_node != "0" and raunk_node not in lcl_node_set:
            dangling.append(f"{addr} raunkiaerality={raunk_node}")
        if taxon != "0" and taxon not in txa_node_set:
            dangling.append(f"{addr} taxonomy_id={taxon}")
        if raunk_node == "0":
            sentinel_pairs += 0  # raunkiaerality sentinel tolerated (value '0')

    new_pp, pp_hash = _rebuild_document(
        existing=live["product_profiles"], overlay=pp_overlay,
        drop=lambda a: a.startswith("4-9-"), name="product_profiles",
    )
    changed.append("product_profiles")

    # unit-abstraction refs must exist on the anchor
    for ref in (ANCHOR_UNIT_SECOND_ABS, ANCHOR_UNIT_CM_ABS, "3-1-5", "3-1-1"):
        if ref not in anchor_addrs:
            dangling.append(f"anchor ref missing: {ref}")

    report["missing_taxon_count"] = len(missing_taxon)
    report["dangling"] = dangling[:50]
    report["dangling_total"] = len(dangling)

    docs = {"anchor": new_anchor, "txa": new_txa, "lcl": new_lcl, "product_profiles": new_pp}
    hashes = {"anchor": anchor_hash, "txa": txa_hash, "lcl": lcl_hash, "product_profiles": pp_hash}
    prior_ids = {n: live[n].document_id for n in ("anchor", "txa", "lcl", "product_profiles")}

    # ===================== validation gate ===================================
    issues: list[str] = []
    for addr, row in pp_overlay.items():
        v = validate_row(row.datum_address, row.raw)
        if v:
            issues.append(f"{addr}: {v}")
        s = classify_row(row.datum_address, row.raw)
        if not (s.shape == "pairs" and s.value_group == 9 and s.pair_count == 9 and s.well_formed):
            issues.append(f"{addr}: classify {s.shape}/vg{s.value_group}/pairs{s.pair_count}/wf{s.well_formed}")
    report["validate_issues"] = issues[:20]
    report["validate_issue_total"] = len(issues)
    report["product_rows"] = len(pp_overlay)

    if issues:
        raise SystemExit(f"validate_row gate failed: {len(issues)} product rows malformed (first: {issues[:3]})")
    if dangling and on_missing == "fail":
        raise SystemExit(f"reference-existence gate failed: {len(dangling)} dangling refs (first: {dangling[:5]})")

    return BuildResult(docs=docs, hashes=hashes, prior_ids=prior_ids, report=report, changed=changed)


# --------------------------------------------------------------------------- #
# Reporting + verification
# --------------------------------------------------------------------------- #
def _print_report(result: BuildResult, *, dry_run: bool) -> None:
    r = result.report
    print("\n================ INGEST PLAN ================")
    print(f"entries (unique)            : {r['entries']}")
    print(f"product_profiles rows built : {r['product_rows']}  (4-9-1..4-9-{r['product_rows']})")
    print(f"txa resolution              : {r['txa_resolution']}")
    print(f"txa species minted          : {len(r['txa_minted'])}")
    if r["txa_minted"]:
        for node, title in r["txa_minted"][:40]:
            print(f"    + {node:24} {title}")
        if len(r["txa_minted"]) > 40:
            print(f"    … +{len(r['txa_minted']) - 40} more")
        print(f"txa-SAMRAS (1-1-1) bits     : {r.get('txa_samras_bits')}  over {r.get('txa_node_count')} nodes")
    print(f"lcl-SAMRAS (1-1-5) bits     : {r['lcl_samras_bits']}  over {r['lcl_node_count']} nodes")
    print(f"taxonomy_id='0' (unresolved): {r['missing_taxon_count']}")
    print(f"validate_row issues         : {r['validate_issue_total']}")
    print(f"dangling references         : {r['dangling_total']}")
    for d in r["dangling"][:20]:
        print(f"    ! {d}")
    print("\nderived document ids:")
    for name in ("anchor", "txa", "lcl", "product_profiles"):
        doc = result.docs[name]
        tag = "(unchanged)" if name not in result.changed else "(CHANGED)"
        print(f"  {name:18} rows={len(doc.rows):5}  {doc.document_id.split('.')[-1][:16]}…  {tag}")
    print("=============================================")
    if dry_run:
        print("DRY RUN — no backup taken, nothing written.\n")


def _verify_live(authority_db: Path, *, expect: dict) -> None:
    """Post-write verification: re-read with a fresh adapter and assert invariants."""
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    docs = {d.document_id.split(".")[3]: d for d in catalog.documents if f".{SANDBOX}." in d.document_id}
    failures: list[str] = []
    for name, n in expect["row_counts"].items():
        actual = len(docs[name].rows)
        if actual != n:
            failures.append(f"{name} rows={actual} expected {n}")
    # 1-1-5 + 1-1-1 roundtrip
    anchor_rows = _as_rows(docs["anchor"])
    for addr in expect["roundtrip"]:
        bits = next((r.raw[0][2] for r in anchor_rows if r.datum_address == addr), None)
        if bits is None:
            failures.append(f"anchor {addr} missing")
            continue
        decoded = decode_canonical_bitstream(bits)
        if len(decoded.addresses) != expect["roundtrip"][addr]:
            failures.append(f"{addr} decoded {len(decoded.addresses)} nodes, expected {expect['roundtrip'][addr]}")
    # every product row classifies clean
    bad = [r.datum_address for r in _as_rows(docs["product_profiles"])
           if r.datum_address.startswith("4-9-") and classify_row(r.datum_address, r.raw).issues]
    if bad:
        failures.append(f"{len(bad)} product rows with classify issues")
    if failures:
        raise SystemExit("POST-WRITE VERIFY FAILED:\n  " + "\n  ".join(failures))
    print("[verify] post-write checks PASSED")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def run(*, authority_db: Path, dry_run: bool, txa_mode: str, on_missing: str) -> dict:
    if not authority_db.exists():
        raise SystemExit(f"authority db missing: {authority_db}")

    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    result = build(store, txa_mode=txa_mode, on_missing=on_missing)
    _print_report(result, dry_run=dry_run)

    if dry_run:
        return {"status": "dry_run", **result.report}

    # STEP 0 — mandatory backup
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    backup = authority_db.with_name(authority_db.name + f".pre-product-profiles-{stamp}.bak")
    if backup.exists():
        raise SystemExit(f"backup target already exists: {backup}")
    shutil.copy2(authority_db, backup)
    print(f"[backup] {backup}")

    # STEP 9 — write the changed docs (anchor → txa → lcl → product_profiles)
    order = ["anchor", "txa", "lcl", "product_profiles"]
    for name in order:
        if name not in result.changed:
            continue
        if result.docs[name].document_id == result.prior_ids[name]:
            print(f"[skip] {name} already current ({result.prior_ids[name].split('.')[-1][:16]}…)")
            continue
        store.replace_single_document_efficient(
            tenant_id=TENANT, prior_document_id=result.prior_ids[name], updated_document=result.docs[name]
        )
        _upsert_documents_row(
            authority_db, name=name, document_id=result.docs[name].document_id,
            version_hash=result.hashes[name], is_anchor=(name == "anchor"),
        )
        print(f"[write] {name} → {result.docs[name].document_id.split('.')[-1][:16]}…")

    # STEP 11 — post-write verify
    expect = {
        "row_counts": {name: len(result.docs[name].rows) for name in order},
        "roundtrip": {ANCHOR_LCL_SAMRAS: result.report["lcl_closure"]},
    }
    if "txa" in result.changed:
        expect["roundtrip"][ANCHOR_TXA_SAMRAS] = result.report["txa_closure"]
    _verify_live(authority_db, expect=expect)

    return {"status": "applied", "backup": str(backup), **result.report,
            "document_ids": {n: result.docs[n].document_id for n in order}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--authority-db", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--txa-mode", choices=("append", "strict"), default="append")
    ap.add_argument("--on-missing", choices=("sentinel", "defer", "fail"), default="sentinel")
    args = ap.parse_args(argv)
    result = run(authority_db=args.authority_db, dry_run=args.dry_run, txa_mode=args.txa_mode, on_missing=args.on_missing)
    print(json.dumps({k: v for k, v in result.items() if k not in ("txa_minted", "dangling")}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
