"""LCL structure-tree viewer — the agro_erp local-id structure vs its definitions.

The sibling of :mod:`txa_tree_viewer`: it renders the node-address tree DENOTED by the
anchor's ``lcl-SAMRAS`` structured magnitude (anchor row ``1-1-5``), marking each node
DEFINED in the ``lcl`` document vs EMPTY (denoted-but-undefined). Where txa_tree browses
the *taxonomy* universe, this browses the *local-id* universe: the product-classification
subtree (``1-3-2-*``), the product leaves (``1-3-1-*``), the entity/land/invoice/contract
branches, and (once added) the operator-role nodes (``1-6-*``).

Pure reuse: the magnitude decode, defined-node scan, node-address tree algebra, and
``build_magnitude_tree`` are all shared with txa_tree. Only the magnitude address and the
defining document differ — this is the "second magnitude" that proves the builder is
structure-agnostic (and the first consumer that the spine's flattener will generalize).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.state_machine.portal_shell.shell_schemas import (
    WORKBENCH_UI_TOOL_ROUTE,
)
from MyCiteV2.packages.tools.txa_tree_viewer import build_magnitude_tree

from ._archetype import find_named_document, read_sandbox_catalog
from ._registry import register
from ._shared.utilities import as_text as _as_text

_TENANT_DEFAULT = "fnd"
_SCHEMA = "mycite.v2.portal.workbench.tool.lcl_structure.v1"
# The anchor row carrying the lcl structured magnitude (label "lcl-SAMRAS").
_LCL_MAGNITUDE_ADDR = "1-1-5"


def _error(message: str) -> dict[str, Any]:
    return {
        "schema": _SCHEMA,
        "error": message,
        "magnitude": "lcl",
        "denoted_count": 0,
        "defined_count": 0,
        "empty_count": 0,
        "tree": [],
    }


class LclStructureViewer:
    """Render the agro_erp lcl node-address tree (magnitude-denoted vs lcl-defined)."""

    tool_id = "lcl_structure"
    label = "LCL Structure"
    summary = "Local-id node-address tree from the anchor's lcl magnitude — defined nodes vs empty (denoted-but-undefined) placeholders."
    route = WORKBENCH_UI_TOOL_ROUTE
    # lcl carries the same titled 4-2 definition shape txa does, so it is recognized as
    # `samras_taxonomy`. The tool resolves anchor+lcl BY NAME regardless of the selected
    # doc and degrades gracefully off-context (mirrors txa_tree).
    applies_to_archetype: tuple[str, ...] = ("samras_taxonomy",)
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
        # Resolve lcl BY NAME, not by archetype: txa and lcl BOTH match samras_taxonomy,
        # so resolve_tool_document (archetype-first) would return whichever comes first in
        # iteration (txa) and mis-overlay txa-defined nodes onto the lcl magnitude. The
        # structure viewer always renders the named lcl magnitude, so a name resolve is
        # correct (and dodges the resolve_tool_document shared-archetype ambiguity).
        lcl = find_named_document(docs, sandbox=sandbox, name="lcl")
        if lcl is None:
            return _error("lcl document not found")

        built = build_magnitude_tree(anchor, _LCL_MAGNITUDE_ADDR, lcl)
        if built is None:
            return _error("lcl magnitude (anchor 1-1-5) missing or undecodable")

        denoted, defined = built["denoted"], built["defined"]
        return {
            "schema": _SCHEMA,
            "sandbox_id": sandbox,
            "document_id": _as_text(getattr(lcl, "document_id", "")),
            "selected_row_address": _as_text(datum_address),
            "magnitude": "lcl",
            "denoted_count": len(denoted),
            "defined_count": len(defined & denoted),
            "empty_count": len(denoted - defined),
            "tree": built["tree"],
        }


# Self-register on import.
register(LclStructureViewer())
