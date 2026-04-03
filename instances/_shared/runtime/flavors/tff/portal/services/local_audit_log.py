from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_shared_local_audit_log() -> ModuleType:
    shared_path = Path(__file__).resolve().parents[3] / "_shared" / "portal" / "services" / "local_audit_log.py"
    spec = importlib.util.spec_from_file_location("mycite_shared_local_audit_log", shared_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load shared local audit log from {shared_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SHARED = _load_shared_local_audit_log()

append_audit_event = _SHARED.append_audit_event
