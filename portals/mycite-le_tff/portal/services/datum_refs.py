from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_shared_datum_refs() -> ModuleType:
    shared_path = Path(__file__).resolve().parents[3] / "_shared" / "portal" / "datum_refs.py"
    spec = importlib.util.spec_from_file_location("mycite_shared_datum_refs", shared_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load shared datum refs from {shared_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_SHARED = _load_shared_datum_refs()

ParsedDatumRef = _SHARED.ParsedDatumRef
datum_identifier_candidates = _SHARED.datum_identifier_candidates
is_datum_ref = _SHARED.is_datum_ref
normalize_datum_ref = _SHARED.normalize_datum_ref
parse_datum_ref = _SHARED.parse_datum_ref
