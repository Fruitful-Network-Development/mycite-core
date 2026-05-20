"""Workbench-tool package.

Plan v2: tools are simple visualization renderers invoked from the
menubar palette. The contract is in :mod:`_contract`; the registry in
:mod:`_registry`. Each tool module self-registers on import.

To add a new tool: create ``MyCiteV2/packages/tools/<tool_id>.py``
implementing :class:`_contract.WorkbenchTool`, call
``_registry.register(MyTool())`` at module scope, then import the
module from this package's ``__init__`` so the registry is populated
when consumers import :mod:`MyCiteV2.packages.tools`.
"""

from __future__ import annotations

from ._contract import WorkbenchTool
from ._registry import TOOL_REGISTRY, all_tools, describe_for_palette, get, register

# Self-registering tool modules (import for side effect).
from . import cts_gis_map  # noqa: F401

__all__ = [
    "WorkbenchTool",
    "TOOL_REGISTRY",
    "all_tools",
    "describe_for_palette",
    "get",
    "register",
]
