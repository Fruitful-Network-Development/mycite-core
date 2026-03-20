"""Shared workbench / workspace composition helpers (portal-core, flavor-agnostic)."""

from __future__ import annotations

from .samras_structural_detail import build_samras_structural_detail_vm
from .workbench_composition import build_grouped_workbench_bundle

__all__ = [
    "build_grouped_workbench_bundle",
    "build_samras_structural_detail_vm",
]
