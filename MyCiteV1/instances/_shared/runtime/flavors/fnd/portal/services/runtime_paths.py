from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_shared_runtime_paths() -> ModuleType:
    shared_path = Path(__file__).resolve().parents[3] / "_shared" / "portal" / "runtime_paths.py"
    spec = importlib.util.spec_from_file_location("mycite_shared_runtime_paths", shared_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load shared runtime paths from {shared_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SHARED = _load_shared_runtime_paths()

network_dir = _SHARED.network_dir
utilities_dir = _SHARED.utilities_dir
aliases_dir = _SHARED.aliases_dir
alias_read_dirs = _SHARED.alias_read_dirs
contracts_dir = _SHARED.contracts_dir
contract_read_dirs = _SHARED.contract_read_dirs
external_event_log_dir = _SHARED.external_event_log_dir
external_event_types_dir = _SHARED.external_event_types_dir
external_event_log_path = _SHARED.external_event_log_path
external_event_read_paths = _SHARED.external_event_read_paths
local_audit_dir = _SHARED.local_audit_dir
local_audit_path = _SHARED.local_audit_path
reference_exchange_dir = _SHARED.reference_exchange_dir
reference_subscription_registry_path = _SHARED.reference_subscription_registry_path
hosted_path = _SHARED.hosted_path
hosted_read_paths = _SHARED.hosted_read_paths
progeny_root = _SHARED.progeny_root
admin_progeny_dir = _SHARED.admin_progeny_dir
member_progeny_dir = _SHARED.member_progeny_dir
user_progeny_dir = _SHARED.user_progeny_dir
legacy_progeny_dir = _SHARED.legacy_progeny_dir
legacy_member_progeny_dir = _SHARED.legacy_member_progeny_dir
legacy_tenant_progeny_dir = _SHARED.legacy_tenant_progeny_dir
internal_progeny_read_dirs = _SHARED.internal_progeny_read_dirs
unified_progeny_read_paths = _SHARED.unified_progeny_read_paths
member_profile_read_dirs = _SHARED.member_profile_read_dirs
vault_dir = _SHARED.vault_dir
vault_contracts_dir = _SHARED.vault_contracts_dir
vault_contract_read_dirs = _SHARED.vault_contract_read_dirs
vault_keys_dir = _SHARED.vault_keys_dir
vault_key_read_dirs = _SHARED.vault_key_read_dirs
keypass_db_path = _SHARED.keypass_db_path
keypass_inventory_path = _SHARED.keypass_inventory_path
utility_tools_dir = _SHARED.utility_tools_dir
utility_peripherals_dir = _SHARED.utility_peripherals_dir
