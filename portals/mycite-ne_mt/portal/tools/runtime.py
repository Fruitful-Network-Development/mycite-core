from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_shared_runtime() -> ModuleType:
    shared_path = Path(__file__).resolve().parents[3] / "_shared" / "portal" / "tools" / "runtime.py"
    spec = importlib.util.spec_from_file_location("mycite_shared_tool_runtime", shared_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load shared tool runtime from {shared_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SHARED = _load_shared_runtime()

read_enabled_tools = _SHARED.read_enabled_tools
register_tool_blueprints = _SHARED.register_tool_blueprints
active_tool_for_path = _SHARED.active_tool_for_path
first_tool_home = _SHARED.first_tool_home
