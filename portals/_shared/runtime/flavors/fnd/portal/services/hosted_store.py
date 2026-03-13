from __future__ import annotations

import sys
from pathlib import Path


def _load_shared_hosted_model():
    portals_root = Path(__file__).resolve().parents[6]
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    import _shared.portal.hosted_model as module

    return module


_SHARED = _load_shared_hosted_model()

SUPPORTED_PROGENY_TYPES = _SHARED.SUPPORTED_PROGENY_TYPES
DEFAULT_TABS = _SHARED.DEFAULT_TABS
default_progeny_template = _SHARED.default_progeny_template
default_hosted_payload = _SHARED.default_hosted_payload
normalize_hosted_payload = _SHARED.normalize_hosted_payload
get_progeny_template = _SHARED.get_progeny_template
set_progeny_template = _SHARED.set_progeny_template
read_hosted_payload = _SHARED.read_hosted_payload
write_hosted_payload = _SHARED.write_hosted_payload
