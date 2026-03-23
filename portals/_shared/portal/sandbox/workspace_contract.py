"""Typed declarations for sandbox-first tools (intent only; semantics stay in data_engine).

See the sandbox lifecycle and tool integration wiki pages for the current contract.
Runtime behavior lives in ``tool_sandbox_session.py`` (`ToolSandboxSession`).
"""

from __future__ import annotations

from typing import TypedDict


class SandboxResourceRef(TypedDict, total=False):
    """Resource dependency declared by a tool."""

    resource_id: str
    """Sandbox or local resource id (e.g. ``local:msn.foo``)."""

    required: bool
    """If True, workspace open fails when resource is missing."""


class ToolSandboxDeclaration(TypedDict, total=False):
    """What a tool needs from the portal sandbox — not how rows are validated."""

    tool_id: str
    required_resources: list[SandboxResourceRef]
    optional_resources: list[SandboxResourceRef]
    datum_families_touched: list[str]
    """Rule families the tool commonly edits (for UX badges only)."""

    consumes_anthology_datum_ids: list[str]
    """Explicit anthology identifiers the tool reads (optional, conservative)."""

    publish_resource_kinds: list[str]
    """e.g. ``mss_resource``, ``samras``, future ``msn_lookup_table``."""

    notes: str

    config_coordinate_paths: list[str]
    """Dotted config paths (``get_path``) exposed as ``loaded_config_inputs`` on session open."""

    optional_sandbox_resource_id_paths: list[str]
    """Dotted config paths whose string values are sandbox resource ids to load when present."""


# Back-compat alias for docs and older imports.
AGRO_ERP_SANDBOX_DECLARATION_EXAMPLE: ToolSandboxDeclaration = {
    "tool_id": "agro_erp",
    "required_resources": [],
    "optional_resources": [],
    "datum_families_touched": ["collection", "selectorate", "field", "table_like"],
    "consumes_anthology_datum_ids": [],
    "publish_resource_kinds": ["mss_resource"],
    "config_coordinate_paths": [
        "agro.inherited.product_profile_ref",
        "agro.inherited.supply_log_ref",
    ],
    "optional_sandbox_resource_id_paths": [
        "agro_erp.sandbox.txa_resource_id",
        "agro_erp.sandbox.msn_resource_id",
    ],
    "notes": "First sandbox-session client: plot-plan draft + config-derived refs; optional txa/msn resource ids from config.",
}

# Canonical runnable declaration for AGRO ERP (same payload as the example; prefer this name in code).
AGRO_ERP_SANDBOX_DECLARATION: ToolSandboxDeclaration = dict(AGRO_ERP_SANDBOX_DECLARATION_EXAMPLE)


__all__ = [
    "AGRO_ERP_SANDBOX_DECLARATION",
    "AGRO_ERP_SANDBOX_DECLARATION_EXAMPLE",
    "SandboxResourceRef",
    "ToolSandboxDeclaration",
]
