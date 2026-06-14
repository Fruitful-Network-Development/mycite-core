"""TXA structure-tree viewer — the agro_erp taxonomy magnitude vs its definitions.

Renders the full node-address tree DENOTED by the anchor's ``txa-SAMRAS`` structured
magnitude (anchor row ``1-1-1``), marking each node DEFINED in the ``txa`` document vs
EMPTY (denoted to exist by the magnitude but not given a definition row). This is the
"browse the reference universe, see what's materialized" surface — a precursor to the
still/capture model (knowledge/still_capture_live_contract.md).

Pure reuse of the SAMRAS/datum_ops core: the magnitude decode, the defined-node scan, the
node-address tree algebra, and LclNameIndex for labels are all existing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.core.datum_ops.datum_resolve import cached_index
from MyCiteV2.packages.core.datum_ops.node_addrs import direct_children
from MyCiteV2.packages.core.datum_ops.refs import defined_node_addrs
from MyCiteV2.packages.core.structures.samras.codec import decode_canonical_bitstream
from MyCiteV2.packages.state_machine.portal_shell.shell_schemas import (
    WORKBENCH_UI_TOOL_ROUTE,
)

from ._archetype import find_named_document, read_sandbox_catalog, resolve_tool_document
from ._registry import register
from ._shared.utilities import as_text as _as_text
from ._shared.utilities import row_head as _row_head

_TENANT_DEFAULT = "fnd"
_SCHEMA = "mycite.v2.portal.workbench.tool.txa_tree.v1"
# The anchor row carrying the txa structured magnitude (label "txa-SAMRAS").
_TXA_MAGNITUDE_ADDR = "1-1-1"


def _error(message: str) -> dict[str, Any]:
    return {
        "schema": _SCHEMA,
        "error": message,
        "magnitude": "txa",
        "denoted_count": 0,
        "defined_count": 0,
        "empty_count": 0,
        "tree": [],
    }


def build_magnitude_tree(
    anchor: Any, magnitude_addr: str, defining_doc: Any
) -> dict[str, Any] | None:
    """Decode the anchor magnitude at ``magnitude_addr`` and overlay which of its
    denoted node addresses are DEFINED in ``defining_doc``.

    Returns ``{denoted, defined, tree}`` (sets + nested tree) or None when the magnitude
    row is missing/undecodable. Factored so lcl/msn trees are a one-line addition later.
    """
    magnitude_row = next(
        (r for r in (getattr(anchor, "rows", ()) or []) if _as_text(r.datum_address) == magnitude_addr),
        None,
    )
    if magnitude_row is None:
        return None
    head = _row_head(magnitude_row)
    bitstream = _as_text(head[2]) if len(head) > 2 else ""
    if not bitstream:
        return None
    try:
        structure = decode_canonical_bitstream(bitstream)
    except Exception:
        return None

    denoted: set[str] = set(structure.addresses)
    defined: set[str] = defined_node_addrs(defining_doc) if defining_doc is not None else set()
    labels = cached_index(defining_doc) if defining_doc is not None else None

    def _node(addr: str) -> dict[str, Any]:
        return {
            "address": addr,
            "label": (labels.resolve(addr) if labels is not None else "") or "",
            "status": "defined" if addr in defined else "empty",
            "children": [_node(child) for child in direct_children(addr, denoted)],
        }

    tree = [_node(root) for root in direct_children("", denoted)]
    return {"denoted": denoted, "defined": defined, "tree": tree}


class TxaTreeViewer:
    """Render the agro_erp txa node-address tree (magnitude-denoted vs txa-defined)."""

    tool_id = "txa_tree"
    label = "TXA Tree"
    summary = "Taxonomy node-address tree from the anchor's txa magnitude — defined nodes vs empty (denoted-but-undefined) placeholders."
    route = WORKBENCH_UI_TOOL_ROUTE
    # txa itself carries no archetype (only a legacy_alias); the taxonomy archetype lives
    # on the lcl doc, so the tool surfaces in the taxonomy context. It resolves anchor+txa
    # BY NAME regardless of the selected doc, and degrades gracefully off-context.
    # Recognized by SHAPE: `samras_taxonomy` is derived structurally from the 4-2-N
    # titled-definition rows (txa + lcl both have it; txa carries no metadata token).
    # The two metadata tokens stay for back-compat with lcl's stamped metadata.
    applies_to_archetype: tuple[str, ...] = (
        "samras_taxonomy",
        "agro_erp_taxonomy_row",
        "mycite.v2.datum.agro_erp.taxonomy_source.v1",
    )
    applies_to_source_kind: tuple[str, ...] = ()

    def build_panel_payload(
        self,
        *,
        authority_db_file: Path | None,
        sandbox_id: str,
        document_id: str,
        datum_address: str,
    ) -> dict[str, Any]:
        docs, err = read_sandbox_catalog(authority_db_file, tenant_id=_TENANT_DEFAULT)
        if err:
            return _error(err)
        sandbox = sandbox_id or "agro_erp"
        anchor = find_named_document(docs, sandbox=sandbox, name="anchor")
        if anchor is None:
            return _error("anchor document not found")
        txa = resolve_tool_document(
            docs, tool=self, sandbox=sandbox, document_id=document_id, canonical_name="txa"
        )
        if txa is None:
            return _error("txa document not found")

        built = build_magnitude_tree(anchor, _TXA_MAGNITUDE_ADDR, txa)
        if built is None:
            return _error("txa magnitude (anchor 1-1-1) missing or undecodable")

        denoted, defined = built["denoted"], built["defined"]
        return {
            "schema": _SCHEMA,
            "sandbox_id": sandbox,
            "document_id": _as_text(getattr(txa, "document_id", "")),
            "selected_row_address": _as_text(datum_address),
            "magnitude": "txa",
            "denoted_count": len(denoted),
            "defined_count": len(defined & denoted),
            "empty_count": len(denoted - defined),
            "tree": built["tree"],
        }


# Self-register on import.
register(TxaTreeViewer())
