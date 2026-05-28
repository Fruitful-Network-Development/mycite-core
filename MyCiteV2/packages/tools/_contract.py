"""Workbench-tool contract (Plan v2).

A workbench tool is a simple module that takes a (sandbox, document,
datum) context and produces a panel payload the JS renderer paints
into the workbench's visualization panel. Tools no longer own surfaces,
routes, or activity-bar slots — they are discovered via the menubar
search and invoked via ``surface_query.tool``.

The contract is intentionally minimal: a few identifying attributes and
one method. Tools self-register in :mod:`_registry` on import.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class WorkbenchTool(Protocol):
    """Protocol every workbench visualization tool implements.

    Attributes are read by the menubar palette for eligibility
    filtering. ``build_panel_payload`` is invoked by the workbench
    runtime when the user selects this tool; its return value is
    embedded in ``regions.visualization_panel.panel_payload`` for the
    JS renderer.
    """

    tool_id: str
    label: str
    summary: str
    # Route the menubar palette stamps onto each item's data-route attribute;
    # ``v2_portal_tool_palette.js`` renderList reads it and dispatches it on
    # click. Should be the tool's canonical surface route (the shell
    # ``portal_system_tool`` dispatcher 302-redirects deep-link tool URLs
    # into the unified ``/portal/system?tool=<id>`` workbench).
    route: str
    applies_to_archetype: tuple[str, ...]
    applies_to_source_kind: tuple[str, ...]

    def build_panel_payload(
        self,
        *,
        authority_db_file: Path | None,
        sandbox_id: str,
        document_id: str,
        datum_address: str,
    ) -> dict[str, Any]:
        """Return the panel_payload dict the JS renderer will consume."""
        ...
