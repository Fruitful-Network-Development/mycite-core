from __future__ import annotations

# Compatibility wrapper around the canonical externally meaningful event log.

import importlib.util
import sys
from pathlib import Path

try:  # pragma: no branch - normal package import path
    from portal.services.external_event_log import (  # type: ignore
        ExternalEventValidationError,
        FORBIDDEN_SECRET_KEYS,
        ReadResult,
        RequestLogValidationError,
        append_event,
        append_external_event,
        is_externally_meaningful_event,
        read_events,
        read_external_events,
    )
except ModuleNotFoundError:  # pragma: no cover - compatibility for spec-loaded shared module
    _path = Path(__file__).resolve().with_name("external_event_log.py")
    _spec = importlib.util.spec_from_file_location("mycite_shared_external_event_log", _path)
    if _spec is None or _spec.loader is None:
        raise
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = _module
    _spec.loader.exec_module(_module)
    ExternalEventValidationError = _module.ExternalEventValidationError
    FORBIDDEN_SECRET_KEYS = _module.FORBIDDEN_SECRET_KEYS
    ReadResult = _module.ReadResult
    RequestLogValidationError = _module.RequestLogValidationError
    append_event = _module.append_event
    append_external_event = _module.append_external_event
    is_externally_meaningful_event = _module.is_externally_meaningful_event
    read_events = _module.read_events
    read_external_events = _module.read_external_events
