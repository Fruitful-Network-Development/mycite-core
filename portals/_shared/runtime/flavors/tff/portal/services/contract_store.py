from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType


def _load_shared_contract_store() -> ModuleType:
    app_root = Path(__file__).resolve().parents[3]
    app_root_token = str(app_root)
    if app_root_token not in sys.path:
        sys.path.insert(0, app_root_token)
    return importlib.import_module("_shared.portal.services.contract_store")


_SHARED = _load_shared_contract_store()

ALLOWED_STATUS = _SHARED.ALLOWED_STATUS
CONTRACT_SCHEMA_V1 = _SHARED.CONTRACT_SCHEMA_V1
CONTRACT_SCHEMA_V2 = _SHARED.CONTRACT_SCHEMA_V2
FORBIDDEN_SECRET_KEYS = _SHARED.FORBIDDEN_SECRET_KEYS
ContractAlreadyExistsError = _SHARED.ContractAlreadyExistsError
ContractNotFoundError = _SHARED.ContractNotFoundError
ContractValidationError = _SHARED.ContractValidationError
apply_compact_array_update = _SHARED.apply_compact_array_update
create_contract = _SHARED.create_contract
get_contract = _SHARED.get_contract
list_contracts = _SHARED.list_contracts
normalize_contract_payload = _SHARED.normalize_contract_payload
update_contract = _SHARED.update_contract
upsert_contract = _SHARED.upsert_contract

__all__ = [
    "ALLOWED_STATUS",
    "CONTRACT_SCHEMA_V1",
    "CONTRACT_SCHEMA_V2",
    "FORBIDDEN_SECRET_KEYS",
    "ContractAlreadyExistsError",
    "ContractNotFoundError",
    "ContractValidationError",
    "apply_compact_array_update",
    "create_contract",
    "get_contract",
    "list_contracts",
    "normalize_contract_payload",
    "update_contract",
    "upsert_contract",
]
