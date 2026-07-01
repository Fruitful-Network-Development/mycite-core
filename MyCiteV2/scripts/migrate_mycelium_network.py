"""Create the ``mycelium_network`` sandbox and retire ``cts_gis``.

One-shot MOS migration (operator TASK-2026-07-01-001). In a single pass it:

1. Re-keys every ``cts_gis`` geo document (anchor, administrative, address_nodes,
   247_17_77, the 33 ``3-2-3-17-77-*`` node docs) into ``mycelium_network`` — rows and
   anchor_rows verbatim (a content-stable re-key: version_hash is unchanged), so the
   GEO vocabulary the docs are authored in is preserved 1:1.
2. Extends the (re-homed) anchor with two non-conflicting babelettes so the entity
   docs fit the geo vocab: ``rf.3-1-8``=email, ``rf.3-1-9``=dns.
3. Re-authors ``system.natural_entity`` and ``system.legal_entity`` into the geo vocab
   (head-marker remap only; magnitudes preserved) and ingests the one ``sos_voterid``
   record into ``natural_entity`` (name decoded from binary, voter id → native
   ``rf.3-1-7`` sosvid slot).
4. Adds a new ``msn_registry`` identity doc (canonical msn_id + tenant metadata).
5. Removes all 38 ``cts_gis`` docs and the two ``system`` entity docs from the catalog.
6. Reconciles the secondary ``documents`` index table (which store_authoritative_catalog
   does not touch).

Default is a DRY RUN: it builds + validates the target catalog and prints a summary
WITHOUT writing. Pass ``--write`` to persist (portal MUST be stopped).

Usage::

    # dry run against a throwaway copy
    python -m MyCiteV2.scripts.migrate_mycelium_network --db /srv/tmp/mos_dryrun.sqlite3
    # persist (portal stopped)
    python -m MyCiteV2.scripts.migrate_mycelium_network --db <live> --write
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.document_naming import (
    format_canonical_document_id,
    is_canonical_document_id,
    parse_canonical_document_id,
)
from MyCiteV2.packages.core.mss import compute_mss_hash
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)

TENANT = "fnd"
MSN = "3-2-3-17-77-1-6-4-1-4"
OLD_GEO = "cts_gis"
NEW = "mycelium_network"

# cts_gis docs whose content is re-homed verbatim (everything except sos_voterid,
# which is ingested into natural_entity).
GEO_KEEP_VERBATIM_EXCLUDE = {"sos_voterid"}

# system docs re-authored into the geo vocab + moved to mycelium_network.
ENTITY_DOCS = ("natural_entity", "legal_entity")


# ----------------------------------------------------------------------------- helpers
def _sb(doc_id: str) -> str:
    try:
        return parse_canonical_document_id(doc_id).sandbox or ""
    except Exception:
        return ""


def _nm(doc_id: str) -> str:
    try:
        return parse_canonical_document_id(doc_id).name
    except Exception:
        return ""


def _decode_bits(value: str) -> str:
    """Binary-ASCII babelette → text (NUL-terminated, printable only). Plain text passes through."""
    text = str(value)
    if not text or len(text) % 8 or set(text) - {"0", "1"}:
        return text
    out: list[str] = []
    for i in range(0, len(text), 8):
        byte = int(text[i : i + 8], 2)
        if byte == 0:
            break
        if 32 <= byte <= 126:
            out.append(chr(byte))
    return "".join(out)


def _hash(document: AuthoritativeDatumDocument) -> str:
    vh = compute_mss_hash(document)["version_hash"]
    return vh[len("sha256:") :] if vh.startswith("sha256:") else vh


def _mint(
    *,
    name: str,
    is_anchor: bool,
    rows: tuple[AuthoritativeDatumDocumentRow, ...],
    anchor_rows: tuple = (),
    source_kind: str = "sandbox_source",
    document_metadata: dict | None = None,
    canonical_name: str | None = None,
) -> AuthoritativeDatumDocument:
    """Build a mycelium_network doc, computing the real MSS hash via a placeholder pass."""
    metadata = dict(document_metadata or {})
    placeholder = format_canonical_document_id(
        prefix="lv", msn_id=MSN, sandbox=NEW, name=name, version_hash="0" * 64
    )
    common = dict(
        source_kind=source_kind,
        document_name=name,
        canonical_name=name if canonical_name is None else canonical_name,
        relative_path=f"sandbox/mycelium-network/lv.{MSN}.{NEW}.{name}.json",
        tool_id=NEW,
        is_anchor=is_anchor,
        document_metadata=metadata,
        anchor_rows=anchor_rows,
        rows=rows,
    )
    real_hash = _hash(AuthoritativeDatumDocument(document_id=placeholder, **common))
    real_id = format_canonical_document_id(
        prefix="lv", msn_id=MSN, sandbox=NEW, name=name, version_hash=real_hash
    )
    return AuthoritativeDatumDocument(document_id=real_id, **common)


def _rekey_verbatim(src: AuthoritativeDatumDocument) -> AuthoritativeDatumDocument:
    """Content-stable re-key of a geo doc into mycelium_network (rows/anchor_rows/metadata kept).

    Names the doc by its canonical id NAME segment (``document_name`` is a source
    filename with dots and is not a valid id segment). ``document_name`` is not part
    of the MSS hash, so the re-key stays content-stable.
    """
    doc = _mint(
        name=_nm(src.document_id),
        is_anchor=src.is_anchor,
        rows=tuple(src.rows),
        anchor_rows=tuple(src.anchor_rows),
        source_kind=src.source_kind,
        document_metadata=dict(src.document_metadata or {}),
        canonical_name=src.canonical_name or src.document_name,
    )
    # Content-stable check: the re-keyed doc's MSS hash must equal the SOURCE doc's
    # MSS hash (not the source id's hash — several live cts_gis ids are stale, their
    # hash predating an anchor_file_version metadata addition). Equal content hashes
    # prove rows/anchor_rows/metadata/source_kind were preserved 1:1.
    if _hash(doc) != _hash(src):
        raise SystemExit(
            f"re-key altered content for {_nm(src.document_id)}: {_hash(src)} -> {_hash(doc)}"
        )
    return doc


def _remap_entity_rows(
    src: AuthoritativeDatumDocument, remap: dict[str, str], *, extra_rows=()
) -> AuthoritativeDatumDocumentRow:
    """Remap head marker tokens (rf.3-1-a -> rf.3-1-b); magnitudes/tail preserved."""
    new_rows: list[AuthoritativeDatumDocumentRow] = []
    for row in src.rows:
        raw = row.raw
        if not (isinstance(raw, list) and raw and isinstance(raw[0], list)):
            new_rows.append(AuthoritativeDatumDocumentRow(datum_address=row.datum_address, raw=raw))
            continue
        head = list(raw[0])
        for i in range(1, len(head) - 1, 2):  # markers at odd slots
            tok = str(head[i])
            if tok in remap:
                head[i] = remap[tok]
        new_raw = [head, *list(raw)[1:]]
        new_rows.append(AuthoritativeDatumDocumentRow(datum_address=row.datum_address, raw=new_raw))
    new_rows.extend(extra_rows)
    return tuple(new_rows)


def _anchor_with_extra_babelettes(src_anchor: AuthoritativeDatumDocument) -> AuthoritativeDatumDocument:
    """Re-home the cts_gis anchor + add rf.3-1-8=email, rf.3-1-9=dns babelettes.

    The added babelettes abstract off the anchor's existing nominal abstraction
    (2-1-1 = niu-baciloid-256-64), a valid 64-char field — non-conflicting with the
    existing geo docs (which use only rf.3-1-1..rf.3-1-3).
    """
    rows = list(src_anchor.rows)
    existing = {r.datum_address for r in rows}
    additions = [
        ("3-1-8", "2-1-1", "email-babelette"),
        ("3-1-9", "2-1-1", "dns-babelette"),
    ]
    for addr, absn, label in additions:
        if addr in existing:
            raise SystemExit(f"anchor already defines {addr}; refuse to clobber")
        rows.append(
            AuthoritativeDatumDocumentRow(datum_address=addr, raw=[[addr, absn, "0"], [label]])
        )
    return _mint(
        name="anchor",
        is_anchor=True,
        rows=tuple(rows),
        anchor_rows=tuple(src_anchor.anchor_rows),
        source_kind=src_anchor.source_kind,
        document_metadata=dict(src_anchor.document_metadata or {}),
        canonical_name="anchor",
    )


def _build_msn_registry() -> AuthoritativeDatumDocument:
    """A small identity doc: the canonical msn_id node + tenant metadata (geo vocab)."""
    rows = (
        AuthoritativeDatumDocumentRow(
            datum_address="4-9-1",
            raw=[["4-9-1", "rf.3-1-2", MSN, "rf.3-1-3", "fruitful_network_development"],
                 ["fruitful_network_development"]],
        ),
        AuthoritativeDatumDocumentRow(
            datum_address="4-9-2",
            raw=[["4-9-2", "rf.3-1-3", "fnd"], ["tenant_id"]],
        ),
    )
    return _mint(name="msn_registry", is_anchor=False, rows=rows,
                 document_metadata={"note": "canonical msn_id + tenant registry (TASK-2026-07-01-001)"})


def _build_natural_entity(src: AuthoritativeDatumDocument, voter: AuthoritativeDatumDocument):
    """Re-author natural_entity into geo vocab + append the ingested voter row."""
    remap = {"rf.3-1-3": "rf.3-1-2", "rf.3-1-9": "rf.3-1-8"}  # geo-node, email
    # ingest: decode the single voter record.
    vhead = voter.rows[0].raw[0]
    node = ""
    names: list[str] = []
    voter_id = ""
    i = 1
    while i < len(vhead) - 1:
        marker, mag = str(vhead[i]), vhead[i + 1]
        if marker == "rf.3-1-2":
            node = str(mag)
        elif marker == "rf.3-1-4":
            names.append(_decode_bits(mag))
        elif marker == "rf.3-1-7":
            voter_id = _decode_bits(mag)
        i += 2
    first = " ".join(n for n in names[:-1] if n).strip() if len(names) > 1 else (names[0] if names else "")
    last = names[-1] if len(names) > 1 else ""
    next_idx = 1 + max((int(r.datum_address.split("-")[-1]) for r in src.rows), default=0)
    voter_row = AuthoritativeDatumDocumentRow(
        datum_address=f"4-1-{next_idx}",
        raw=[["4-1-" + str(next_idx), "rf.3-1-2", node, "rf.3-1-4", first, "rf.3-1-4", last,
              "rf.3-1-7", voter_id], [f"{first} {last}".strip()]],
    )
    rows = _remap_entity_rows(src, remap, extra_rows=(voter_row,))
    return _mint(name="natural_entity", is_anchor=False, rows=rows,
                 document_metadata={"note": "re-homed from system, geo vocab + sos_voterid ingest (TASK-2026-07-01-001)"}), \
        {"voter_node": node, "voter_name": f"{first} {last}".strip(), "voter_id": voter_id}


def _build_legal_entity(src: AuthoritativeDatumDocument) -> AuthoritativeDatumDocument:
    remap = {"rf.3-1-3": "rf.3-1-2", "rf.3-1-8": "rf.3-1-9"}  # geo-node, dns
    rows = _remap_entity_rows(src, remap)
    return _mint(name="legal_entity", is_anchor=False, rows=rows,
                 document_metadata={"note": "re-homed from system, geo vocab (TASK-2026-07-01-001)"})


# ----------------------------------------------------------------------------- documents index
def _reconcile_documents_index(db: Path, mycelium: list[AuthoritativeDatumDocument]) -> None:
    now = int(time.time() * 1000)
    conn = sqlite3.connect(db)
    try:
        conn.execute("DELETE FROM documents WHERE tenant_id=? AND sandbox=?", (TENANT, OLD_GEO))
        conn.execute(
            "DELETE FROM documents WHERE tenant_id=? AND sandbox='system' AND name IN (?,?)",
            (TENANT, *ENTITY_DOCS),
        )
        for doc in mycelium:
            p = parse_canonical_document_id(doc.document_id)
            conn.execute(
                "INSERT INTO documents (tenant_id, document_id, prefix, msn_id, sandbox, name, "
                "version_hash, is_anchor, origin, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (TENANT, doc.document_id, "lv", MSN, NEW, doc.document_name,
                 f"sha256:{p.version_hash}", 1 if doc.is_anchor else 0, "local", now),
            )
        conn.commit()
    finally:
        conn.close()


# ----------------------------------------------------------------------------- main build
def build(db: Path, write: bool) -> dict:
    store = SqliteSystemDatumStoreAdapter(db, allow_legacy_writes=False)
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    by_key = {(_sb(d.document_id), _nm(d.document_id)): d for d in catalog.documents}

    def need(sandbox, name):
        d = by_key.get((sandbox, name))
        if d is None:
            raise SystemExit(f"missing source doc {sandbox}.{name}")
        return d

    mycelium: list[AuthoritativeDatumDocument] = []

    # 1. anchor (extended geo vocab)
    mycelium.append(_anchor_with_extra_babelettes(need(OLD_GEO, "anchor")))
    # 2. identity registry
    mycelium.append(_build_msn_registry())
    # 3. entity docs (re-authored) + voter ingest
    ne_doc, voter_info = _build_natural_entity(need("system", "natural_entity"), need(OLD_GEO, "sos_voterid"))
    mycelium.append(ne_doc)
    mycelium.append(_build_legal_entity(need("system", "legal_entity")))
    # 4. geo docs re-homed verbatim (all cts_gis except anchor + sos_voterid)
    rekeyed = 0
    for (sbx, nm), doc in by_key.items():
        if sbx != OLD_GEO or nm in ({"anchor"} | GEO_KEEP_VERBATIM_EXCLUDE):
            continue
        mycelium.append(_rekey_verbatim(doc))
        rekeyed += 1

    # target catalog = keep everything not removed + mycelium
    removed_ids = {d.document_id for (sbx, nm), d in by_key.items() if sbx == OLD_GEO}
    removed_ids |= {need("system", n).document_id for n in ENTITY_DOCS}
    kept = [d for d in catalog.documents if d.document_id not in removed_ids]
    final_docs = tuple(kept) + tuple(mycelium)

    # ---- validation
    problems: list[str] = []
    for d in mycelium:
        if not is_canonical_document_id(d.document_id):
            problems.append(f"non-canonical id: {d.document_id}")
    ids = [d.document_id for d in final_docs]
    if len(ids) != len(set(ids)):
        problems.append("duplicate document_ids in final catalog")
    if any(_sb(d.document_id) == OLD_GEO for d in final_docs):
        problems.append("cts_gis docs still present after build")
    myc_names = sorted(d.document_name for d in mycelium)
    anchors = [d.document_name for d in mycelium if d.is_anchor]
    if anchors != ["anchor"]:
        problems.append(f"expected exactly one anchor, got {anchors}")

    summary = {
        "db": str(db),
        "write": write,
        "source_counts": {s: sum(1 for k in by_key if k[0] == s) for s in sorted({k[0] for k in by_key})},
        "mycelium_doc_count": len(mycelium),
        "mycelium_names": myc_names,
        "geo_rekeyed_verbatim": rekeyed,
        "natural_entity_rows": next(len(d.rows) for d in mycelium if d.document_name == "natural_entity"),
        "legal_entity_rows": next(len(d.rows) for d in mycelium if d.document_name == "legal_entity"),
        "voter_ingest": voter_info,
        "removed_doc_count": len(removed_ids),
        "final_doc_count": len(final_docs),
        "problems": problems,
    }
    if problems:
        summary["status"] = "INVALID"
        return summary
    if not write:
        summary["status"] = "dry_run_ok"
        return summary

    # ---- persist
    next_catalog = AuthoritativeDatumDocumentCatalogResult(
        tenant_id=catalog.tenant_id,
        documents=final_docs,
        source_files=dict(catalog.source_files),
        readiness_status=dict(catalog.readiness_status),
        warnings=tuple(catalog.warnings),
    )
    store.store_authoritative_catalog(next_catalog)
    _reconcile_documents_index(db, mycelium)
    summary["status"] = "written"
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--write", action="store_true", help="persist (portal MUST be stopped)")
    args = ap.parse_args(argv)
    if not args.db.exists():
        raise SystemExit(f"db missing: {args.db}")
    result = build(args.db, args.write)
    import json
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status") in {"dry_run_ok", "written"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
