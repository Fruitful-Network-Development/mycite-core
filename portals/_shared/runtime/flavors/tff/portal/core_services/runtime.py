from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType


def _load_shared_module(module_name: str) -> ModuleType:
    app_root = Path(__file__).resolve().parents[3]
    app_root_token = str(app_root)
    if app_root_token not in sys.path:
        sys.path.insert(0, app_root_token)
    return importlib.import_module(f"_shared.portal.core_services.{module_name}")


_CFG = _load_shared_module("config_loader")
_REG = _load_shared_module("registry")
_NET = _load_shared_module("network_cards")
_GEO = _load_shared_module("geography")

load_active_private_config = _CFG.load_active_private_config
resolve_active_private_config_path = _CFG.resolve_active_private_config_path
active_private_config_filename = _CFG.active_private_config_filename

build_service_nav = _REG.build_service_nav
build_network_tabs = _REG.build_network_tabs
normalize_network_tab = _REG.normalize_network_tab
build_system_tabs = _REG.build_system_tabs
normalize_system_tab = _REG.normalize_system_tab
active_service_from_path = _REG.active_service_from_path
resolve_service_order = _REG.resolve_service_order
DEFAULT_SERVICE_ORDER = _REG.DEFAULT_SERVICE_ORDER
NETWORK_TAB_ORDER = _REG.NETWORK_TAB_ORDER

build_network_cards = _NET.build_network_cards
build_property_geography_model = _GEO.build_property_geography_model
