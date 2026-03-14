from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_shared_tool_specs() -> ModuleType:
    shared_path = Path(__file__).resolve().parents[3] / "_shared" / "portal" / "tools" / "specs.py"
    spec = importlib.util.spec_from_file_location("mycite_shared_tool_specs", shared_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load shared tool specs module from {shared_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SHARED = _load_shared_tool_specs()

TOOL_SPEC_SCHEMA = _SHARED.TOOL_SPEC_SCHEMA
ToolDataSpec = _SHARED.ToolDataSpec
parse_tool_spec = _SHARED.parse_tool_spec
load_tool_spec = _SHARED.load_tool_spec
load_tool_spec_for_id = _SHARED.load_tool_spec_for_id

