from __future__ import annotations

from pathlib import Path

from .state_roots import (
    DEFAULT_INSTANCES_ROOT,
    InstanceStateDirs,
    build_instance_state_dirs,
    canonical_instances_root,
    infer_instance_state_root,
    instance_state_root,
)


def _unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def _existing_or_declared(paths: list[Path]) -> list[Path]:
    existing = [path for path in paths if path.exists()]
    return _unique_paths(existing or paths)


def network_dir(private_dir: Path) -> Path:
    return private_dir / "network"


def utilities_dir(private_dir: Path) -> Path:
    return private_dir / "utilities"


def aliases_dir(private_dir: Path) -> Path:
    return network_dir(private_dir) / "aliases"


def alias_read_dirs(private_dir: Path) -> list[Path]:
    return _existing_or_declared([aliases_dir(private_dir), private_dir / "aliases"])


def contracts_dir(private_dir: Path) -> Path:
    return private_dir / "contracts"


def contract_read_dirs(private_dir: Path) -> list[Path]:
    return _existing_or_declared([contracts_dir(private_dir)])


def external_event_log_dir(private_dir: Path) -> Path:
    return network_dir(private_dir) / "external_events"


def _compatibility_request_log_dir(private_dir: Path) -> Path:
    return network_dir(private_dir) / "request_log"


def external_event_types_dir(private_dir: Path) -> Path:
    return external_event_log_dir(private_dir) / "types"


def _compatibility_request_log_types_dir(private_dir: Path) -> Path:
    return _compatibility_request_log_dir(private_dir) / "types"


def external_event_log_path(private_dir: Path) -> Path:
    return external_event_log_dir(private_dir) / "external_events.ndjson"


def _compatibility_request_log_path(private_dir: Path) -> Path:
    return _compatibility_request_log_dir(private_dir) / "request_log.ndjson"


def legacy_request_log_dir(private_dir: Path) -> Path:
    return private_dir / "request_log"


def external_event_read_paths(private_dir: Path, msn_id: str | None = None) -> list[Path]:
    paths = [external_event_log_path(private_dir), _compatibility_request_log_path(private_dir)]
    if msn_id:
        token = str(msn_id or "").strip()
        if token:
            paths.append(legacy_request_log_dir(private_dir) / f"{token}.ndjson")
    legacy_shared = legacy_request_log_dir(private_dir) / "request_log.ndjson"
    paths.append(legacy_shared)
    return _unique_paths(paths)


def local_audit_dir(private_dir: Path) -> Path:
    return private_dir / "audit"


def local_audit_path(private_dir: Path) -> Path:
    return local_audit_dir(private_dir) / "local.ndjson"


def reference_exchange_dir(private_dir: Path) -> Path:
    return network_dir(private_dir) / "reference_exchange"


def reference_subscription_registry_path(private_dir: Path) -> Path:
    return reference_exchange_dir(private_dir) / "subscriptions.json"


def hosted_path(private_dir: Path) -> Path:
    return network_dir(private_dir) / "hosted.json"


def hosted_read_paths(private_dir: Path) -> list[Path]:
    return _existing_or_declared([hosted_path(private_dir), private_dir / "hosted.json"])


def progeny_root(private_dir: Path) -> Path:
    return network_dir(private_dir) / "progeny"


def admin_progeny_dir(private_dir: Path) -> Path:
    return progeny_root(private_dir) / "admin_progeny"


def member_progeny_dir(private_dir: Path) -> Path:
    return progeny_root(private_dir) / "member_progeny"


def user_progeny_dir(private_dir: Path) -> Path:
    return progeny_root(private_dir) / "user_progeny"


def legacy_progeny_dir(private_dir: Path) -> Path:
    return private_dir / "progeny"


def legacy_member_progeny_dir(private_dir: Path) -> Path:
    return legacy_progeny_dir(private_dir) / "member"


def legacy_tenant_progeny_dir(private_dir: Path) -> Path:
    return legacy_progeny_dir(private_dir) / "tenant"


def internal_progeny_read_dirs(private_dir: Path) -> list[Path]:
    return _existing_or_declared(
        [
            progeny_root(private_dir) / "internal",
            legacy_progeny_dir(private_dir) / "internal",
        ]
    )


def unified_progeny_read_paths(private_dir: Path) -> list[Path]:
    return _existing_or_declared(
        [
            progeny_root(private_dir) / "progeny.json",
            legacy_progeny_dir(private_dir) / "progeny.json",
        ]
    )


def member_profile_read_dirs(private_dir: Path) -> list[Path]:
    return _existing_or_declared(
        [
            member_progeny_dir(private_dir),
            progeny_root(private_dir),
            legacy_member_progeny_dir(private_dir),
            legacy_tenant_progeny_dir(private_dir),
        ]
    )


def vault_dir(private_dir: Path) -> Path:
    return utilities_dir(private_dir) / "vault"


def legacy_vault_dir(private_dir: Path) -> Path:
    return private_dir / "vault"


def vault_contracts_dir(private_dir: Path) -> Path:
    return vault_dir(private_dir) / "contracts"


def vault_contract_read_dirs(private_dir: Path) -> list[Path]:
    return _existing_or_declared([vault_contracts_dir(private_dir), legacy_vault_dir(private_dir) / "contracts"])


def vault_keys_dir(private_dir: Path) -> Path:
    return vault_dir(private_dir) / "keys"


def vault_key_read_dirs(private_dir: Path) -> list[Path]:
    return _existing_or_declared([vault_keys_dir(private_dir), legacy_vault_dir(private_dir) / "keys"])


def keypass_db_path(private_dir: Path) -> Path:
    return vault_dir(private_dir) / "keypass.kdbx"


def keypass_inventory_path(private_dir: Path) -> Path:
    return vault_dir(private_dir) / "keypass_inventory.json"


def utility_tools_dir(private_dir: Path) -> Path:
    return utilities_dir(private_dir) / "tools"


def utility_peripherals_dir(private_dir: Path) -> Path:
    return utilities_dir(private_dir) / "peripherals"
