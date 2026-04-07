#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTANCES_ROOT = REPO_ROOT / "instances"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
BUILD_SCHEMA = "mycite.portal.build.v1"
DEFAULT_MOUNT_TARGET = "peripherals.tools"
CORE_SYSTEM_SURFACES = ["data_tool"]
RETIRED_TOOL_IDS = {"legacy_admin", "paypal_demo"}
_TOOL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SUPPORTED_PROGENY_TYPES = ("admin", "member", "user")
LEGACY_PROGENY_TYPE_MAP = {
    "board_member": "member",
    "constituent_farm": "member",
    "poc": "admin",
    "tenant": "member",
}

from instances.scripts.declarations.registry import (
    ACTIVE_PORTAL_DECLARATIONS,
    default_portal_instance_id_for,
    default_runtime_flavor_for,
    default_state_root_for,
)

ACTIVE_PORTALS: dict[str, dict[str, str]] = {
    portal_id: {
        "portal_instance_id": declaration.portal_instance_id,
        "runtime_flavor": declaration.runtime_flavor,
        "state_dir": str(declaration.state_dir),
    }
    for portal_id, declaration in ACTIVE_PORTAL_DECLARATIONS.items()
}

SEED_PATTERNS = (
    "data/presentation/**/*.json",
    "private/network/aliases/**/*.json",
    "private/contracts/**/*.json",
    "private/network/progeny/*.json",
    "private/network/external_events/types/**/*.ndjson",
    "private/utilities/vault/keypass_inventory.json",
)


def _load_shared_hosted_model():
    token = str(INSTANCES_ROOT)
    if token not in sys.path:
        sys.path.insert(0, token)
    import _shared.portal.hosted_model as module

    return module


_HOSTED = _load_shared_hosted_model()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON at {path}")
    return payload


def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    return _load_json(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dedupe_tokens(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = str(value or "").strip().lower()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _normalize_tools_configuration(values: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()

    if isinstance(values, list):
        for item in values:
            if not isinstance(item, dict):
                continue
            token = str(item.get("tool_id") or item.get("id") or "").strip().lower()
            if not token or token in seen:
                continue
            if not _TOOL_ID_RE.fullmatch(token):
                continue
            if token in RETIRED_TOOL_IDS or token in CORE_SYSTEM_SURFACES:
                continue
            seen.add(token)
            mount_target = str(item.get("mount_target") or DEFAULT_MOUNT_TARGET).strip().lower() or DEFAULT_MOUNT_TARGET
            if mount_target not in {"utilities", "peripherals.tools"}:
                mount_target = DEFAULT_MOUNT_TARGET
            out.append({"tool_id": token, "mount_target": mount_target})
    return out


def _canonical_progeny_type(value: Any) -> str:
    token = str(value or "").strip().lower()
    if not token:
        return ""
    return LEGACY_PROGENY_TYPE_MAP.get(token, token)


def _canonicalize_progeny_ref_filename(value: Any) -> str:
    token = str(value or "").strip()
    if not token:
        return ""
    token = re.sub(
        r"\.(board_member|constituent_farm|poc|tenant)-",
        lambda match: f".{_canonical_progeny_type(match.group(1))}-",
        token,
    )
    token = re.sub(
        r"-(board_member|constituent_farm|poc|tenant)(\.json)$",
        lambda match: f"-{_canonical_progeny_type(match.group(1))}{match.group(2)}",
        token,
    )
    return token


def _normalize_alias_entries(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    out: list[dict[str, str]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        normalized: dict[str, str] = {}
        for key, value in item.items():
            host = str(key or "").strip()
            ref = _canonicalize_progeny_ref_filename(value)
            if host and ref:
                normalized[host] = ref
        if normalized:
            out.append(normalized)
    return out


def _collect_progeny_refs(node: Any, fallback_type: str = "") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []

    def _push(progeny_type: Any, ref_token: Any) -> None:
        token = _canonical_progeny_type(progeny_type)
        ref = _canonicalize_progeny_ref_filename(ref_token)
        if token not in SUPPORTED_PROGENY_TYPES or not ref:
            return
        out.append((token, ref))

    def _walk(value: Any, fallback: str = "") -> None:
        if isinstance(value, str):
            _push(fallback, value)
            return
        if isinstance(value, list):
            for item in value:
                _walk(item, fallback)
            return
        if not isinstance(value, dict):
            return

        explicit_type = _canonical_progeny_type(value.get("progeny_type") or value.get("type") or fallback)
        explicit_ref = value.get("ref") or value.get("path") or value.get("file") or value.get("source")
        if explicit_type and explicit_ref:
            _push(explicit_type, explicit_ref)
            refs = value.get("refs")
            if isinstance(refs, list):
                for ref_item in refs:
                    _push(explicit_type, ref_item)
            return

        for key, item in value.items():
            key_token = str(key or "").strip().lower()
            if key_token in {"progeny_type", "type", "ref", "path", "file", "source", "refs"}:
                continue
            next_fallback = _canonical_progeny_type(key_token) or fallback
            _walk(item, next_fallback)

    _walk(node, fallback_type)
    return out


def _normalize_progeny_config(values: Any) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {token: [] for token in SUPPORTED_PROGENY_TYPES}
    seen: dict[str, set[str]] = {token: set() for token in SUPPORTED_PROGENY_TYPES}
    for progeny_type, ref_token in _collect_progeny_refs(values):
        if ref_token in seen[progeny_type]:
            continue
        seen[progeny_type].add(ref_token)
        merged[progeny_type].append(ref_token)
    return merged


def _normalize_role_groups(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize_role_groups(item) for item in value]
    if not isinstance(value, dict):
        return value

    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if key == "role_groups" and isinstance(item, dict):
            admins = item.get("admins")
            if admins is None:
                admins = item.get("poc_admin")
            normalized[key] = {
                "admins": admins if isinstance(admins, list) else [],
                "members": item.get("members") if isinstance(item.get("members"), list) else [],
                "users": item.get("users") if isinstance(item.get("users"), list) else [],
            }
            continue
        normalized[key] = _normalize_role_groups(item)
    return normalized


def _normalize_private_config(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_role_groups(copy.deepcopy(payload))
    if not isinstance(normalized, dict):
        return {}
    normalized.pop("enabled_tools", None)
    normalized["aliases"] = _normalize_alias_entries(normalized.get("aliases"))
    normalized["progeny"] = _normalize_progeny_config(normalized.get("progeny"))
    return normalized


def _deep_fill_missing(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(primary)
    for key, fallback_value in fallback.items():
        if key not in merged:
            merged[key] = copy.deepcopy(fallback_value)
            continue
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(fallback_value, dict):
            merged[key] = _deep_fill_missing(current, fallback_value)
    return merged


def _resolve_first_json(*paths: Path) -> tuple[dict[str, Any], str] | tuple[None, str]:
    for path in paths:
        payload = _load_json_if_exists(path)
        if payload is not None:
            return payload, str(path)
    return None, ""


def _matching_legacy_config(private_root: Path, msn_id: str) -> tuple[dict[str, Any] | None, str, str]:
    if not msn_id:
        return None, "", ""
    filename = f"mycite-config-{msn_id}.json"
    path = private_root / filename
    payload = _load_json_if_exists(path)
    return payload, filename, str(path) if payload is not None else ""


def _serialize_seed_file(path: Path, target_rel: str) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "target": target_rel,
        "source_hint": str(path),
    }
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        try:
            entry["payload_json"] = json.loads(text)
            return entry
        except Exception:
            pass
    entry["payload_text"] = text
    return entry


def _collect_seed_files(portal_dir: Path, state_root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in (portal_dir, state_root):
        if not root.exists() or not root.is_dir():
            continue
        for pattern in SEED_PATTERNS:
            for path in sorted(root.glob(pattern)):
                if not path.is_file():
                    continue
                rel = path.relative_to(root).as_posix()
                if rel in seen:
                    continue
                seen.add(rel)
                out.append(_serialize_seed_file(path, rel))
    return out


def build_portal_spec(
    portal_id: str,
    portal_dir: Path,
    state_root: Path,
    portal_instance_id: str,
    runtime_flavor: str,
) -> dict[str, Any]:
    repo_private = portal_dir / "private"
    repo_public = portal_dir / "public"
    state_private = state_root / "private"
    state_public = state_root / "public"
    state_data = state_root / "data"

    state_config = _load_json_if_exists(state_private / "config.json") or {}
    repo_config = _load_json_if_exists(repo_private / "config.json") or {}

    state_msn_id = str(state_config.get("msn_id") or "").strip()
    repo_msn_id = str(repo_config.get("msn_id") or "").strip()
    msn_id = state_msn_id or repo_msn_id
    if not msn_id:
        for legacy_root in (state_private, repo_private):
            for candidate in sorted(legacy_root.glob("mycite-config-*.json")):
                payload = _load_json_if_exists(candidate)
                token = str((payload or {}).get("msn_id") or "").strip()
                if token:
                    msn_id = token
                    break
            if msn_id:
                break
    if not msn_id:
        raise RuntimeError(f"Unable to infer msn_id for {portal_id}")

    state_legacy, _, state_legacy_source = _matching_legacy_config(state_private, msn_id)
    repo_legacy, legacy_filename, repo_legacy_source = _matching_legacy_config(repo_private, msn_id)

    canonical = state_config or state_legacy or repo_config or repo_legacy or {}
    for fallback in (state_legacy or {}, repo_config or {}, repo_legacy or {}):
        canonical = _deep_fill_missing(canonical, fallback)
    canonical = _normalize_private_config(canonical)

    raw_tools_configuration = canonical.get("tools_configuration")
    tools_configuration = _normalize_tools_configuration(raw_tools_configuration)
    enabled_tools = [str(item.get("tool_id") or "") for item in tools_configuration if str(item.get("tool_id") or "")]
    canonical["tools_configuration"] = copy.deepcopy(tools_configuration)

    title = str(canonical.get("title") or portal_id).strip() or portal_id
    state_public_msn = state_public / f"msn-{msn_id}.json"
    repo_public_msn = repo_public / f"msn-{msn_id}.json"
    public_msn, public_msn_source = _resolve_first_json(state_public_msn, repo_public_msn)
    state_public_fnd = state_public / f"fnd-{msn_id}.json"
    repo_public_fnd = repo_public / f"fnd-{msn_id}.json"
    public_fnd, public_fnd_source = _resolve_first_json(state_public_fnd, repo_public_fnd)
    hosted, hosted_source = _resolve_first_json(
        state_private / "network" / "hosted.json",
        repo_private / "network" / "hosted.json",
    )
    normalized_hosted = _HOSTED.normalize_hosted_payload(hosted or {})
    normalized_hosted.pop("raw", None)
    normalized_hosted.pop("path", None)

    anthology_path = state_data / "anthology.json"
    anthology = {
        "authoritative": False,
        "path_hint": str(anthology_path),
        "sha256": _sha256(anthology_path) if anthology_path.exists() and anthology_path.is_file() else "",
        "notes": [
            "State-owned anthology; phase-1 materialize never overwrites this file.",
        ],
    }

    tools = {
        "configuration": copy.deepcopy(tools_configuration),
        "enabled": enabled_tools,
        "core_system_surfaces": list(CORE_SYSTEM_SURFACES),
        "retired": sorted(RETIRED_TOOL_IDS),
        "mount_targets": {item["tool_id"]: item["mount_target"] for item in tools_configuration},
    }

    spec = {
        "schema": BUILD_SCHEMA,
        "portal_id": portal_id,
        "portal_instance_id": portal_instance_id,
        "runtime_flavor": str(runtime_flavor or "").strip().lower() or portal_instance_id,
        "state_root_hint": str(state_root),
        "meta": {
            "msn_id": msn_id,
            "title": title,
        },
        "tools": tools,
        "private_config": {
            "canonical": canonical,
            "canonical_source": str(state_private / "config.json") if state_config else (state_legacy_source or repo_legacy_source or str(repo_private / "config.json")),
            "legacy_compat": [
                {
                    "filename": legacy_filename or f"mycite-config-{msn_id}.json",
                    "payload": copy.deepcopy(canonical),
                    "source": state_legacy_source or repo_legacy_source,
                }
            ],
        },
        "hosted": {
            "filename": "hosted.json",
            "source": hosted_source,
            "payload": normalized_hosted,
        },
        "public_profiles": {
            "msn_card": {
                "filename": f"msn-{msn_id}.json",
                "source": public_msn_source,
                "payload": public_msn or {},
            },
            "fnd_card": {
                "filename": f"fnd-{msn_id}.json",
                "source": public_fnd_source,
                "payload": public_fnd or {},
            },
        },
        "seed_files": _collect_seed_files(portal_dir, state_root),
        "anthology": anthology,
    }
    return spec


def write_build_spec(portal_dir: Path, spec: dict[str, Any]) -> Path:
    path = portal_dir / "build.json"
    _write_json(path, spec)
    return path


def load_build_spec(build_path: Path) -> dict[str, Any]:
    payload = _load_json(build_path)
    if str(payload.get("schema") or "").strip() != BUILD_SCHEMA:
        raise ValueError(f"Unsupported build schema in {build_path}")
    return payload


def _with_tool_configuration(payload: dict[str, Any], tools_configuration: list[dict[str, str]]) -> dict[str, Any]:
    out = copy.deepcopy(payload)
    out["tools_configuration"] = [dict(item) for item in tools_configuration]
    out.pop("enabled_tools", None)
    return out


def materialize_build_spec(build_path: Path, target_state_root: Path | None = None) -> Path:
    spec = load_build_spec(build_path)
    portal_dir = build_path.parent
    target_root = target_state_root or Path(str(spec.get("state_root_hint") or "").strip())
    if not str(target_root):
        raise ValueError("Target state root is required")

    raw_tools_configuration = ((spec.get("tools") or {}).get("configuration") or [])
    tools_configuration = _normalize_tools_configuration(raw_tools_configuration)
    canonical_config = _with_tool_configuration(
        _normalize_private_config((spec.get("private_config") or {}).get("canonical") or {}),
        tools_configuration,
    )
    _write_json(target_root / "private" / "config.json", canonical_config)

    expected_legacy = {
        str(entry.get("filename") or "").strip()
        for entry in ((spec.get("private_config") or {}).get("legacy_compat") or [])
        if isinstance(entry, dict) and str(entry.get("filename") or "").strip()
    }
    private_dir = target_root / "private"
    if private_dir.exists():
        for path in sorted(private_dir.glob("mycite-config-*.json")):
            if path.name not in expected_legacy:
                path.unlink()

    for entry in (spec.get("private_config") or {}).get("legacy_compat") or []:
        if not isinstance(entry, dict):
            continue
        filename = str(entry.get("filename") or "").strip()
        if not filename:
            continue
        payload = _with_tool_configuration(_normalize_private_config(entry.get("payload") or {}), tools_configuration)
        _write_json(target_root / "private" / filename, payload)

    hosted = (spec.get("hosted") or {}).get("payload")
    if isinstance(hosted, dict):
        clean_hosted = _HOSTED.normalize_hosted_payload(hosted)
        clean_hosted.pop("raw", None)
        clean_hosted.pop("path", None)
        _write_json(target_root / "private" / "network" / "hosted.json", clean_hosted)

    public_profiles = spec.get("public_profiles") or {}
    for key in ("msn_card", "fnd_card"):
        entry = public_profiles.get(key) or {}
        if not isinstance(entry, dict):
            continue
        filename = str(entry.get("filename") or "").strip()
        payload = entry.get("payload")
        if filename and isinstance(payload, dict):
            _write_json(target_root / "public" / filename, payload)

    legacy_manifest_path = target_root / "private" / "tools.manifest.json"
    if legacy_manifest_path.exists():
        legacy_manifest_path.unlink()

    for entry in spec.get("seed_files") or []:
        if not isinstance(entry, dict):
            continue
        target_rel = str(entry.get("target") or "").strip()
        if not target_rel:
            continue
        target_path = (target_root / target_rel).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if "payload_json" in entry:
            target_path.write_text(json.dumps(entry.get("payload_json"), indent=2) + "\n", encoding="utf-8")
            continue
        if "payload_text" in entry:
            target_path.write_text(str(entry.get("payload_text") or ""), encoding="utf-8")
            continue
        source_rel = str(entry.get("source") or "").strip()
        if not source_rel:
            continue
        source_path = (portal_dir / source_rel).resolve()
        if not source_path.exists() or not source_path.is_file():
            continue
        shutil.copy2(source_path, target_path)

    return target_root


def _portal_dir(portal_id: str) -> Path:
    portal_dir = PORTALS_ROOT / portal_id
    if not portal_dir.exists() or not portal_dir.is_dir():
        raise FileNotFoundError(f"Portal directory not found: {portal_id}")
    return portal_dir


def _state_root_for(portal_id: str, explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    return default_state_root_for(portal_id)


def _portal_instance_id_for(portal_id: str) -> str:
    return default_portal_instance_id_for(portal_id)


def _runtime_flavor_for(portal_id: str) -> str:
    return default_runtime_flavor_for(portal_id)


def capture_portal(portal_id: str, state_root: Path | None = None) -> Path:
    portal_dir = _portal_dir(portal_id)
    resolved_state_root = state_root or _state_root_for(portal_id)
    portal_instance_id = _portal_instance_id_for(portal_id)
    runtime_flavor = _runtime_flavor_for(portal_id)
    spec = build_portal_spec(portal_id, portal_dir, resolved_state_root, portal_instance_id, runtime_flavor)
    return write_build_spec(portal_dir, spec)


def materialize_portal(portal_id: str, state_root: Path | None = None) -> Path:
    portal_dir = _portal_dir(portal_id)
    build_path = portal_dir / "build.json"
    if not build_path.exists():
        raise FileNotFoundError(f"Build spec not found: {build_path}")
    return materialize_build_spec(build_path, state_root or _state_root_for(portal_id))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture/materialize portal build specs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture_parser = subparsers.add_parser("capture", help="Write build.json from repo/state inputs.")
    capture_parser.add_argument("portal_id", nargs="?", choices=sorted(ACTIVE_PORTALS))
    capture_parser.add_argument("--state-root", dest="state_root")

    materialize_parser = subparsers.add_parser("materialize", help="Write state files from build.json.")
    materialize_parser.add_argument("portal_id", nargs="?", choices=sorted(ACTIVE_PORTALS))
    materialize_parser.add_argument("--state-root", dest="state_root")

    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    portal_ids = [args.portal_id] if args.portal_id else sorted(ACTIVE_PORTALS)
    if args.state_root and len(portal_ids) != 1:
        raise SystemExit("--state-root requires an explicit portal_id")

    for portal_id in portal_ids:
        state_root = Path(args.state_root) if args.state_root else None
        if args.command == "capture":
            path = capture_portal(portal_id, state_root)
            print(f"captured {portal_id} -> {path}")
            continue
        path = materialize_portal(portal_id, state_root)
        print(f"materialized {portal_id} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
