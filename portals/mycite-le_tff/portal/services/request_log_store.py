from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_shared_request_log_store() -> ModuleType:
    shared_path = Path(__file__).resolve().parents[3] / "_shared" / "portal" / "services" / "request_log_store.py"
    spec = importlib.util.spec_from_file_location("mycite_shared_request_log_store", shared_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load shared request log store from {shared_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_SHARED = _load_shared_request_log_store()

FORBIDDEN_SECRET_KEYS = _SHARED.FORBIDDEN_SECRET_KEYS
ReadResult = _SHARED.ReadResult
RequestLogValidationError = _SHARED.RequestLogValidationError
append_event = _SHARED.append_event
read_events = _SHARED.read_events
