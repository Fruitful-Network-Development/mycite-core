from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_shared_module() -> ModuleType:
    shared_root = Path(__file__).resolve().parents[3] / "_shared" / "portal"
    module_path = shared_root / "progeny_embed.py"
    spec = importlib.util.spec_from_file_location("mycite_shared_progeny_embed", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load shared progeny embed module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MOD = _load_shared_module()

build_embed_progeny_landing = _MOD.build_embed_progeny_landing
ensure_broadcast_body_config = _MOD.ensure_broadcast_body_config
