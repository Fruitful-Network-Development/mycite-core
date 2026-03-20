"""
FND workspace implementation — shared with TFF runtime.

The canonical module body lives under ``flavors/tff/data/engine/workspace.py``; FND loads it
so portal behavior stays single-sourced across flavors.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_tff_workspace_module() -> ModuleType:
    tff_path = Path(__file__).resolve().parents[3] / "tff" / "data" / "engine" / "workspace.py"
    spec = importlib.util.spec_from_file_location("_mycite_tff_data_engine_workspace", tff_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load TFF workspace module from {tff_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MOD = _load_tff_workspace_module()
Workspace = _MOD.Workspace

__all__ = ["Workspace"]
