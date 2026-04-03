from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PORTALS_ROOT = REPO_ROOT / "portals"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(PORTALS_ROOT) not in sys.path:
    sys.path.insert(0, str(PORTALS_ROOT))

from portal_core.shared.state_roots import canonical_instances_root

from _shared.portal.core_services.config_loader import normalize_private_config_contract
from _shared.portal.data_engine.resource_registry import (
    INHERITED_SCOPE,
    LOCAL_SCOPE,
    build_canonical_reference_filename,
    build_canonical_resource_filename,
    cache_scope_dir,
    ensure_layout,
    resource_file_path,
    write_resource_file,
)
from mycite_core.contract_line.store import normalize_contract_payload


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _sorted_paths(root: Path) -> list[str]:
    return sorted(str(path.relative_to(root)) for path in root.rglob("*"))


def _parse_legacy_resource_filename(name: str) -> tuple[str, str]:
    token = _as_text(name)
    if token.startswith("rec.") and token.endswith(".json"):
        parts = token[: -len(".json")].split(".", 2)
        if len(parts) == 3:
            return _as_text(parts[1]), _as_text(parts[2])
    if token.startswith("ref.") and token.endswith(".json"):
        parts = token[: -len(".json")].split(".", 2)
        if len(parts) == 3:
            return _as_text(parts[1]), _as_text(parts[2])
    if token.startswith("rc.") and token.endswith(".json"):
        parts = token[: -len(".json")].split(".", 2)
        if len(parts) == 3:
            return _as_text(parts[1]), _as_text(parts[2])
    if token.startswith("rf.") and token.endswith(".json"):
        parts = token[: -len(".json")].split(".", 2)
        if len(parts) == 3:
            return _as_text(parts[1]), _as_text(parts[2])
    return ("", "")


def _legacy_contract_id(filename: str) -> str:
    token = Path(filename).name
    if token.startswith("contract-") and token.endswith(".json"):
        return token[len("contract-") : -len(".json")]
    if token.startswith("contract.") and token.endswith(".json"):
        return token[len("contract.") : -len(".json")]
    return Path(filename).stem


def _canonical_contract_filename(filename: str) -> str:
    return f"contract-{_legacy_contract_id(filename)}.json"


def _looks_like_wrapper(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    return bool(payload.get("schema")) or bool(payload.get("resource_id")) or "anthology_compatible_payload" in payload


def _compact_payload_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    if isinstance(payload.get("anthology_compatible_payload"), dict):
        return dict(payload.get("anthology_compatible_payload") or {})
    if payload and not _looks_like_wrapper(payload):
        return dict(payload)
    return {}


def _wrapped_local_payload(*, payload: dict[str, Any], target_stem: str, name: str, local_msn_id: str) -> dict[str, Any]:
    if _looks_like_wrapper(payload):
        out = dict(payload)
        out["resource_id"] = target_stem
        out["scope"] = LOCAL_SCOPE
        out["source_msn_id"] = local_msn_id
        out["resource_kind"] = _as_text(out.get("resource_kind") or name) or name
        return out
    return {
        "schema": "mycite.portal.resource.local.v1",
        "resource_id": target_stem,
        "resource_kind": name,
        "scope": LOCAL_SCOPE,
        "source_msn_id": local_msn_id,
        "anthology_compatible_payload": _compact_payload_from_payload(payload),
        "legacy_source_payload": dict(payload) if payload and not _compact_payload_from_payload(payload) else {},
        "publish_metadata": {"migrated_unix_ms": int(time.time() * 1000)},
    }


def _wrapped_reference_payload(
    *,
    payload: dict[str, Any],
    target_stem: str,
    name: str,
    source_msn_id: str,
) -> dict[str, Any]:
    out: dict[str, Any]
    if _looks_like_wrapper(payload):
        out = dict(payload)
    else:
        out = {}
    compact_payload = _compact_payload_from_payload(payload)
    out.setdefault("schema", "mycite.portal.resource.reference.v2")
    out["resource_id"] = target_stem
    out["resource_kind"] = _as_text(out.get("resource_kind") or name) or name
    out["scope"] = INHERITED_SCOPE
    out["source_msn_id"] = source_msn_id
    out["source_resource_id"] = f"rc.{source_msn_id}.{name}"
    out["anthology_compatible_payload"] = compact_payload
    legacy_bits = payload.get("mss_bit_string_array") if isinstance(payload.get("mss_bit_string_array"), list) else []
    if legacy_bits:
        bitstring = _as_text(legacy_bits[0])
        if bitstring:
            out["mss_form"] = {"bitstring": bitstring}
    if payload and not compact_payload and not _looks_like_wrapper(payload):
        out["legacy_source_payload"] = dict(payload)
    out.setdefault("sync_metadata", {})
    return out


def _find_public_profile(public_dir: Path, msn_id: str, prefix: str) -> dict[str, Any]:
    candidates = [
        public_dir / f"{prefix}.{msn_id}.json",
        public_dir / f"{prefix}-{msn_id}.json",
        public_dir / f"{msn_id}.json" if prefix == "msn" else public_dir / f"fnd-{msn_id}.json",
    ]
    for path in candidates:
        payload = _read_json(path)
        if payload:
            return payload
    return {}


def _copy_cache_bins_to_public(data_dir: Path, public_dir: Path, *, scope: str) -> list[str]:
    copied: list[str] = []
    cache_dir = cache_scope_dir(data_dir, scope=scope)
    if not cache_dir.exists():
        return copied
    for path in sorted(cache_dir.glob("*.bin"), key=lambda item: item.name):
        target = public_dir / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(target.name)
    return copied


def _public_resource_descriptors(data_dir: Path, public_dir: Path, *, local_msn_id: str) -> list[dict[str, Any]]:
    descriptors: list[dict[str, Any]] = []
    for path in sorted((data_dir / "resources").glob(f"rc.{local_msn_id}.*.json"), key=lambda item: item.name):
        bin_name = path.name[: -len(".json")] + ".bin"
        bin_path = public_dir / bin_name
        if not bin_path.exists() or not bin_path.is_file():
            continue
        name = path.stem.split(".", 2)[2] if len(path.stem.split(".", 2)) == 3 else path.stem
        descriptors.append(
            {
                "resource_id": path.stem,
                "kind": name,
                "export_family": "mss.bin.v2",
                "href": bin_name,
                "lens_hint": "datum",
                "availability": {"public": True},
                "source_msn_id": local_msn_id,
            }
        )
    return descriptors


def _rewrite_public_profiles(instance_dir: Path, *, local_msn_id: str) -> dict[str, Any]:
    public_dir = instance_dir / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    _copy_cache_bins_to_public(instance_dir / "data", public_dir, scope=LOCAL_SCOPE)
    contact_payload = _find_public_profile(public_dir, local_msn_id, "msn")
    fnd_payload = _find_public_profile(public_dir, local_msn_id, "fnd")
    public_resources = _public_resource_descriptors(instance_dir / "data", public_dir, local_msn_id=local_msn_id)

    next_contact = dict(contact_payload)
    next_contact["msn_id"] = local_msn_id
    next_contact["schema"] = _as_text(next_contact.get("schema")) or "mycite.profile.v1"
    next_contact["public_resources"] = public_resources
    next_contact["accessible"] = {}
    options = next_contact.get("options") if isinstance(next_contact.get("options"), dict) else {}
    self_meta = options.get("self") if isinstance(options.get("self"), dict) else {}
    self_meta["href"] = f"/{local_msn_id}.json"
    self_meta["methods"] = ["GET", "OPTIONS"]
    self_meta["auth"] = "none"
    options["self"] = self_meta
    next_contact["options"] = options
    _write_json(public_dir / f"{local_msn_id}.json", next_contact)

    next_fnd = dict(fnd_payload)
    next_fnd["msn_id"] = local_msn_id
    if "schema" not in next_fnd:
        next_fnd["schema"] = "mycite.fnd.profile.v1"
    _write_json(public_dir / f"fnd-{local_msn_id}.json", next_fnd)
    return {
        "contact_card": f"{local_msn_id}.json",
        "fnd_profile": f"fnd-{local_msn_id}.json",
        "public_resources": [item.get("resource_id") for item in public_resources],
    }


def _canonical_reference_entries(config: dict[str, Any], *, contract_name_map: dict[str, str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in list(config.get("references") or []):
        if not isinstance(item, dict):
            continue
        source_msn_id = _as_text(item.get("source_msn_id"))
        name = _as_text(item.get("name")).lower()
        if not source_msn_id or not name:
            parsed_source, parsed_name = _parse_legacy_resource_filename(_as_text(item.get("mss_form") or item.get("title")))
            source_msn_id = source_msn_id or parsed_source
            name = name or parsed_name
        if not source_msn_id or not name:
            continue
        managing_contract = contract_name_map.get(
            _as_text(item.get("managing_contract")),
            _canonical_contract_filename(_as_text(item.get("managing_contract"))) if _as_text(item.get("managing_contract")) else "",
        )
        out.append(
            {
                "managing_contract": managing_contract,
                "title": f"rf.{source_msn_id}.{name}",
                "mss_form": f"rf.{source_msn_id}.{name}.bin",
                "name": name,
                "source_msn_id": source_msn_id,
            }
        )
    return out


def _rewrite_config(config_path: Path, *, contract_name_map: dict[str, str]) -> dict[str, Any]:
    payload = normalize_private_config_contract(_read_json(config_path))
    if contract_name_map:
        payload["contracts"] = sorted({value for value in contract_name_map.values() if _as_text(value)})
    else:
        payload["contracts"] = [
            _canonical_contract_filename(_as_text(item))
            for item in list(payload.get("contracts") or [])
            if _as_text(item)
        ]
    for item in list(payload.get("tools_configuration") or []):
        if not isinstance(item, dict):
            continue
        token = _as_text(item.get("managing_contract"))
        if token:
            item["managing_contract"] = contract_name_map.get(token, _canonical_contract_filename(token))
    payload["references"] = _canonical_reference_entries(payload, contract_name_map=contract_name_map)
    _write_json(config_path, payload)
    return payload


def _discover_active_instances(state_root: Path, requested: list[str] | None) -> list[Path]:
    if requested:
        return [state_root / item for item in requested]
    out: list[Path] = []
    for name in ("fnd_portal", "tff_portal"):
        path = state_root / name
        if path.exists() and path.is_dir():
            out.append(path)
    return out


def _canonical_local_source_payload(source_path: Path) -> dict[str, Any]:
    payload = _read_json(source_path)
    if _looks_like_wrapper(payload):
        compact_payload = _compact_payload_from_payload(payload)
        if compact_payload:
            return compact_payload
    return payload


def _migrate_local_resources(instance_dir: Path, *, local_msn_id: str) -> list[dict[str, str]]:
    data_dir = instance_dir / "data"
    migrated: list[dict[str, str]] = []
    sources: dict[str, Path] = {}

    for path in sorted((data_dir / "resources" / "local").glob("*.json"), key=lambda item: item.name):
        _msn_id, name = _parse_legacy_resource_filename(path.name)
        if name:
            sources.setdefault(name, path)
    for legacy_name, name in (("samras-msn.json", "msn"), ("samras-txa.json", "txa")):
        path = data_dir / legacy_name
        if path.exists() and path.is_file():
            sources.setdefault(name, path)
    for path in sorted((data_dir / "resources").glob("rc.*.json"), key=lambda item: item.name):
        _msn_id, name = _parse_legacy_resource_filename(path.name)
        if name:
            sources[name] = path

    for name, source_path in sorted(sources.items()):
        target = resource_file_path(
            data_dir,
            scope=LOCAL_SCOPE,
            source_msn_id=local_msn_id,
            resource_name=name,
        )
        payload = _read_json(source_path)
        wrapped = _wrapped_local_payload(
            payload=payload,
            target_stem=target.stem,
            name=name,
            local_msn_id=local_msn_id,
        )
        write_resource_file(target, wrapped)
        migrated.append({"source": str(source_path.relative_to(instance_dir)), "target": str(target.relative_to(instance_dir))})
    return migrated


def _source_instance_by_msn(instances: list[Path]) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for instance_dir in instances:
        config = _read_json(instance_dir / "private" / "config.json")
        msn_id = _as_text(config.get("msn_id"))
        if msn_id:
            out[msn_id] = instance_dir
    return out


def _migrate_references(instance_dir: Path, *, source_instances: dict[str, Path]) -> list[dict[str, str]]:
    data_dir = instance_dir / "data"
    config = normalize_private_config_contract(_read_json(instance_dir / "private" / "config.json"))
    candidates: dict[tuple[str, str], dict[str, Any]] = {}

    for path in sorted((data_dir / "references").glob("*.json"), key=lambda item: item.name):
        source_msn_id, name = _parse_legacy_resource_filename(path.name)
        if source_msn_id and name:
            candidates[(source_msn_id, name)] = {"source_path": path}
    inherited_root = data_dir / "resources" / "inherited"
    if inherited_root.exists():
        for path in sorted(inherited_root.rglob("*.json"), key=lambda item: item.name):
            source_msn_id = _as_text(path.parent.name)
            _parsed_source, name = _parse_legacy_resource_filename(path.name)
            if source_msn_id and name:
                candidates[(source_msn_id, name)] = {"source_path": path}
    for item in list(config.get("references") or []):
        if not isinstance(item, dict):
            continue
        source_msn_id = _as_text(item.get("source_msn_id"))
        name = _as_text(item.get("name")).lower()
        if source_msn_id and name:
            candidates.setdefault((source_msn_id, name), {}).update({"config_reference": dict(item)})

    migrated: list[dict[str, str]] = []
    for (source_msn_id, name), meta in sorted(candidates.items()):
        source_payload: dict[str, Any] = {}
        source_instance = source_instances.get(source_msn_id)
        if isinstance(source_instance, Path):
            remote_resource = source_instance / "data" / "resources" / build_canonical_resource_filename(source_msn_id, name)
            if remote_resource.exists() and remote_resource.is_file():
                source_payload = _canonical_local_source_payload(remote_resource)
        if not source_payload and isinstance(meta.get("source_path"), Path):
            source_payload = _read_json(meta["source_path"])
        target = resource_file_path(
            data_dir,
            scope=INHERITED_SCOPE,
            source_msn_id=source_msn_id,
            resource_name=name,
        )
        wrapped = _wrapped_reference_payload(
            payload=source_payload,
            target_stem=target.stem,
            name=name,
            source_msn_id=source_msn_id,
        )
        write_resource_file(target, wrapped)
        migrated.append(
            {
                "source_msn_id": source_msn_id,
                "name": name,
                "target": str(target.relative_to(instance_dir)),
            }
        )
    return migrated


def _tracked_resource_ids_from_state(instance_dir: Path, *, local_msn_id: str, counterparty: str) -> list[str]:
    reference_tracked: list[str] = []
    seen_refs: set[str] = set()
    for path in sorted((instance_dir / "data" / "references").glob("rf.*.json"), key=lambda item: item.name):
        source_msn_id, name = _parse_legacy_resource_filename(path.name)
        token = f"rc.{source_msn_id}.{name}" if source_msn_id and name else ""
        if token and token not in seen_refs:
            seen_refs.add(token)
            reference_tracked.append(token)
    if reference_tracked:
        return reference_tracked

    tracked: list[str] = []
    seen: set[str] = set()
    for path in sorted((instance_dir / "data" / "resources").glob(f"rc.{local_msn_id}.*.json"), key=lambda item: item.name):
        source_msn_id, name = _parse_legacy_resource_filename(path.name)
        token = f"rc.{source_msn_id}.{name}" if source_msn_id and name else ""
        bin_name = path.name[: -len(".json")] + ".bin"
        bin_path = instance_dir / "data" / "cache" / "RC" / bin_name
        if token and bin_path.exists() and token not in seen:
            seen.add(token)
            tracked.append(token)
    return tracked


def _migrate_contracts(instance_dir: Path, *, local_msn_id: str) -> dict[str, str]:
    contracts_dir = instance_dir / "private" / "contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    name_map: dict[str, str] = {}

    for path in sorted(contracts_dir.glob("*.json"), key=lambda item: item.name):
        payload = _read_json(path)
        contract_id = _legacy_contract_id(path.name)
        participants = [
            _as_text(payload.get("contract_initiator")),
            _as_text(payload.get("initiate_receiver")),
        ]
        participants = [item for item in participants if item]
        counterparty = next((item for item in participants if item != local_msn_id), "")
        tracked_resource_ids: list[str] = [str(item).strip() for item in list(payload.get("tracked_resource_ids") or []) if str(item).strip()]
        for item in list(payload.get("inheritance") or []):
            if not isinstance(item, dict):
                continue
            provider = _as_text(item.get("provider"))
            _provider_from_name, name = _parse_legacy_resource_filename(_as_text(item.get("resource")))
            if provider and name:
                token = f"rc.{provider}.{name}"
                if token not in tracked_resource_ids:
                    tracked_resource_ids.append(token)
        if not tracked_resource_ids:
            tracked_resource_ids = _tracked_resource_ids_from_state(
                instance_dir,
                local_msn_id=local_msn_id,
                counterparty=counterparty,
            )
        normalized = normalize_contract_payload(
            {
                **payload,
                "contract_id": contract_id,
                "contract_type": _as_text(payload.get("contract_type")) or "portal_data_exchange",
                "owner_msn_id": local_msn_id,
                "counterparty_msn_id": counterparty,
                "tracked_resource_ids": tracked_resource_ids,
                "details": {
                    **(payload.get("details") if isinstance(payload.get("details"), dict) else {}),
                    "tracked_resource_ids": tracked_resource_ids,
                },
            },
            contract_id=contract_id,
            owner_msn_id=local_msn_id,
            for_write=True,
            reject_secrets=False,
        )
        normalized.pop("inheritance", None)
        target_name = f"contract-{contract_id}.json"
        _write_json(contracts_dir / target_name, normalized)
        name_map[path.name] = target_name
        name_map[target_name] = target_name
    return name_map


def _remove_forbidden_layout(instance_dir: Path, *, local_msn_id: str) -> list[str]:
    removed: list[str] = []
    paths = [
        instance_dir / "data" / "samras-msn.json",
        instance_dir / "data" / "samras-txa.json",
        instance_dir / "data" / "resources" / "index.local.json",
        instance_dir / "data" / "resources" / "index.inherited.json",
        instance_dir / "data" / "resources" / "local",
        instance_dir / "data" / "resources" / "inherited",
        instance_dir / "data" / "presentation",
        instance_dir / "data" / "cache" / "external_resources",
        instance_dir / "data" / "cache" / "tenant",
        instance_dir / "data" / "cache" / "contacts",
        instance_dir / "data" / "refferences",
        instance_dir / "public" / f"msn.{local_msn_id}.json",
        instance_dir / "public" / f"fnd.{local_msn_id}.json",
    ]
    for path in paths:
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed.append(str(path.relative_to(instance_dir)))

    for root in (
        instance_dir / "data" / "resources",
        instance_dir / "data" / "references",
        instance_dir / "private" / "contracts",
    ):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json"), key=lambda item: item.name):
            token = path.name
            if token.startswith("rec.") or token.startswith("ref.") or token.startswith("contract."):
                path.unlink()
                removed.append(str(path.relative_to(instance_dir)))
    return removed


@dataclass
class InstanceMigrationResult:
    instance_id: str
    local_msn_id: str
    inventory_before: list[str]
    local_resources: list[dict[str, str]]
    references: list[dict[str, str]]
    public_outputs: dict[str, Any]
    removed: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "local_msn_id": self.local_msn_id,
            "inventory_before": list(self.inventory_before),
            "local_resources": [dict(item) for item in self.local_resources],
            "references": [dict(item) for item in self.references],
            "public_outputs": dict(self.public_outputs),
            "removed": list(self.removed),
        }


def migrate_instance(instance_dir: Path, *, source_instances: dict[str, Path]) -> InstanceMigrationResult:
    config_path = instance_dir / "private" / "config.json"
    config = _read_json(config_path)
    local_msn_id = _as_text(config.get("msn_id"))
    if not local_msn_id:
        raise RuntimeError(f"missing msn_id in {config_path}")
    ensure_layout(instance_dir / "data")
    inventory_before = _sorted_paths(instance_dir)
    local_resources = _migrate_local_resources(instance_dir, local_msn_id=local_msn_id)
    references = _migrate_references(instance_dir, source_instances=source_instances)
    contract_name_map = _migrate_contracts(instance_dir, local_msn_id=local_msn_id)
    _rewrite_config(config_path, contract_name_map=contract_name_map)
    public_outputs = _rewrite_public_profiles(instance_dir, local_msn_id=local_msn_id)
    removed = _remove_forbidden_layout(instance_dir, local_msn_id=local_msn_id)
    return InstanceMigrationResult(
        instance_id=instance_dir.name,
        local_msn_id=local_msn_id,
        inventory_before=inventory_before,
        local_resources=local_resources,
        references=references,
        public_outputs=public_outputs,
        removed=removed,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", default=str(canonical_instances_root()))
    parser.add_argument("--instance", action="append", default=[])
    parser.add_argument("--output", default="/tmp/portal_instance_corrective_pass_state.json")
    args = parser.parse_args()

    state_root = Path(args.state_root)
    instances = _discover_active_instances(state_root, args.instance)
    source_instances = _source_instance_by_msn(instances)
    results = [migrate_instance(instance_dir, source_instances=source_instances) for instance_dir in instances]
    Path(args.output).write_text(
        json.dumps({"results": [item.to_dict() for item in results]}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
