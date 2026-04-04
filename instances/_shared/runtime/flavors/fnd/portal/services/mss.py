from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType


def _load_shared_mss() -> ModuleType:
    app_root = Path(__file__).resolve().parents[3]
    app_root_token = str(app_root)
    if app_root_token not in sys.path:
        sys.path.insert(0, app_root_token)
    return importlib.import_module("_shared.portal.mss")


_SHARED = _load_shared_mss()

MSS_ENCODING = _SHARED.MSS_ENCODING
MSS_SCHEMA = _SHARED.MSS_SCHEMA
MSS_WIRE_VARIANT_CANONICAL = _SHARED.MSS_WIRE_VARIANT_CANONICAL
compile_mss_payload = _SHARED.compile_mss_payload
decode_mss_payload = _SHARED.decode_mss_payload
load_anthology_payload = _SHARED.load_anthology_payload
preview_mss_context = _SHARED.preview_mss_context
resolve_contract_datum_ref = _SHARED.resolve_contract_datum_ref
validate_mss_payload = _SHARED.validate_mss_payload
