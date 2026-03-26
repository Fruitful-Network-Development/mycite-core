from __future__ import annotations

import importlib
import json
import logging
import os
import re
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Iterable, List, Optional

from _shared.portal.application.shell.tools import normalize_tool_capability

_TOOL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_LOG = logging.getLogger("mycite.tool_runtime")
_LEGACY_CORE_TOOL_IDS = {"data_tool"}
_ALLOWED_MOUNT_TARGETS = {"utilities", "peripherals.tools"}
_DEFAULT_MOUNT_TARGET = "peripherals.tools"


def _safe_tool_id(value: str) -> str:
    token = (value or "").strip().lower()
    if not _TOOL_ID_RE.fullmatch(token):
        raise ValueError("Invalid tool identifier")
    return token


def _normalize_manifest_tool_id(value: str) -> str:
    token = _safe_tool_id(value)
    return token.replace("-", "_")


def _default_display_name(tool_id: str) -> str:
    return tool_id.replace("_", " ").replace("-", " ").strip().title() or tool_id


def _normalize_mount_target(value: str | None) -> str:
    token = str(value or "").strip().lower()
    return token if token in _ALLOWED_MOUNT_TARGETS else _DEFAULT_MOUNT_TARGET


def _is_enabled_status(value: object) -> bool:
    token = str(value or "").strip().lower()
    if not token:
        return True
    return token in {"enabled", "active", "on", "true", "1"}


def _read_json_payload(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_tool_configuration_entries(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []

    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        raw_id = item.get("tool_id") or item.get("id") or item.get("name")
        if not isinstance(raw_id, str):
            continue
        try:
            tool_id = _normalize_manifest_tool_id(raw_id)
        except ValueError:
            continue
        if tool_id in seen:
            continue
        seen.add(tool_id)
        out.append(
            {
                "tool_id": tool_id,
                "mount_target": _normalize_mount_target(item.get("mount_target")),
                "status": str(item.get("status") or "enabled").strip() or "enabled",
            }
        )
    return out


def _read_tool_configuration(private_dir: Path | None) -> list[dict[str, str]]:
    if private_dir is None:
        return []

    config_payload = _read_json_payload(_config_path(Path(private_dir), None))
    return _normalize_tool_configuration_entries(config_payload.get("tools_configuration"))


def _read_tool_mount_targets(private_dir: Path | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in _read_tool_configuration(private_dir):
        if not _is_enabled_status(entry.get("status")):
            continue
        tool_id = str(entry.get("tool_id") or "")
        if tool_id:
            out[tool_id] = _normalize_mount_target(entry.get("mount_target"))
    return out


def _config_path(private_dir: Path, msn_id: Optional[str]) -> Optional[Path]:
    canonical = private_dir / "config.json"
    if canonical.exists() and canonical.is_file():
        return canonical

    if msn_id:
        exact = private_dir / f"mycite-config-{msn_id}.json"
        if exact.exists() and exact.is_file():
            return exact

    env_msn = str(os.environ.get("MSN_ID") or "").strip()
    if env_msn:
        env_path = private_dir / f"mycite-config-{env_msn}.json"
        if env_path.exists() and env_path.is_file():
            return env_path

    for candidate in sorted(private_dir.glob("mycite-config-*.json")):
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def read_enabled_tools(private_dir: Path, msn_id: str | None) -> list[str] | None:
    path = _config_path(private_dir, msn_id)
    if path is None:
        return None

    payload = _read_json_payload(path)
    configured = _normalize_tool_configuration_entries(payload.get("tools_configuration"))
    return [
        str(item.get("tool_id") or "")
        for item in configured
        if str(item.get("tool_id") or "") and _is_enabled_status(item.get("status"))
    ]


def discover_tool_packages(tools_dir: Path) -> list[str]:
    discovered: list[str] = []
    if not tools_dir.exists() or not tools_dir.is_dir():
        return discovered

    for entry in sorted(tools_dir.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir():
            continue
        if entry.name.startswith(".") or entry.name.startswith("__"):
            continue
        if not (entry / "__init__.py").exists():
            continue
        try:
            discovered.append(_safe_tool_id(entry.name))
        except ValueError:
            continue
    return discovered


def load_tool_module(tool_id: str, *, tools_package: str = "portal.tools", logger: logging.Logger | None = None) -> ModuleType | None:
    log = logger or _LOG
    safe = _safe_tool_id(tool_id)
    try:
        return importlib.import_module(f"{tools_package}.{safe}")
    except Exception as exc:
        log.warning("Tool '%s' is configured but not importable: %s", safe, exc)
        return None


def _normalize_route_prefix(value: str, tool_id: str) -> str:
    token = str(value or "").strip() or f"/portal/tools/{tool_id}"
    if not token.startswith("/portal/"):
        token = f"/portal/tools/{tool_id}"
    return token.rstrip("/")


def _normalize_home_path(value: str, tool_id: str, route_prefix: str) -> str:
    token = str(value or "").strip() or f"{route_prefix}/home"
    if not token.startswith("/portal/"):
        token = f"{route_prefix}/home"
    return token


def _normalize_surface_mode(value: object) -> str:
    token = str(value or "").strip().lower()
    return "mediation_only" if token == "mediation_only" else "tool_shell"


def resolve_tool_meta(module: ModuleType, fallback_tool_id: str) -> Dict[str, Any]:
    safe_id = _safe_tool_id(fallback_tool_id)

    raw: Dict[str, Any] = {}
    get_tool = getattr(module, "get_tool", None)
    if callable(get_tool):
        try:
            candidate = get_tool()
            if isinstance(candidate, dict):
                raw = candidate
        except Exception:
            raw = {}

    raw_tool_id = raw.get("tool_id") or raw.get("id") or getattr(module, "TOOL_ID", safe_id)
    tool_id = _safe_tool_id(str(raw_tool_id or safe_id))

    display_name = (
        raw.get("display_name")
        or raw.get("name")
        or raw.get("title")
        or getattr(module, "TOOL_TITLE", "")
        or _default_display_name(tool_id)
    )
    display_name = str(display_name).strip() or _default_display_name(tool_id)

    route_prefix = _normalize_route_prefix(
        str(raw.get("route_prefix") or ""),
        tool_id,
    )
    surface_mode = _normalize_surface_mode(raw.get("surface_mode") or getattr(module, "TOOL_SURFACE_MODE", ""))
    owns_shell_state = bool(raw.get("owns_shell_state")) if "owns_shell_state" in raw else surface_mode != "mediation_only"
    if surface_mode == "mediation_only":
        route_prefix = ""
        home_path = ""
    else:
        home_path = _normalize_home_path(
            str(raw.get("home_path") or raw.get("default_route") or getattr(module, "TOOL_HOME_PATH", "")),
            tool_id,
            route_prefix,
        )

    icon_raw = raw.get("icon") or getattr(module, "TOOL_ICON", None)
    icon = str(icon_raw).strip() if isinstance(icon_raw, str) else ""
    mount_target = _normalize_mount_target(
        str(raw.get("mount_target") or getattr(module, "TOOL_MOUNT_TARGET", "")).strip()
    )

    blueprint = None
    if surface_mode != "mediation_only":
        blueprint = raw.get("blueprint") or raw.get("TOOL_BLUEPRINT") or getattr(module, "TOOL_BLUEPRINT", None)

    meta = {
        "tool_id": tool_id,
        "display_name": display_name,
        "route_prefix": route_prefix,
        "home_path": home_path,
        "icon": icon,
        "panel_id": f"tool-{tool_id}",
        "title": display_name,
        "mount_target": mount_target,
        "surface_mode": surface_mode,
        "owns_shell_state": owns_shell_state,
        "blueprint": blueprint,
    }
    capability = normalize_tool_capability({**raw, **meta})
    meta.update(
        {
            "supported_verbs": capability.get("supported_verbs") or [],
            "supported_source_contracts": capability.get("supported_source_contracts") or [],
            "config_context_support": bool(capability.get("config_context_support")),
            "source_resolution_rules": capability.get("source_resolution_rules") or [],
            "workbench_contribution": capability.get("workbench_contribution") or {},
            "inspector_card_contribution": capability.get("inspector_card_contribution") or {},
            "mutation_policy": capability.get("mutation_policy") or {},
            "preview_hooks": capability.get("preview_hooks") or {},
            "apply_hooks": capability.get("apply_hooks") or {},
            "surface_mode": capability.get("surface_mode") or surface_mode,
            "owns_shell_state": bool(capability.get("owns_shell_state", owns_shell_state)),
            "service_contract": capability.get("service_contract") or {},
        }
    )
    return meta


def register_tool_blueprints(
    app: Any,
    enabled_tool_ids: Iterable[str] | None,
    *,
    tools_package: str = "portal.tools",
    tools_dir: Path | None = None,
    private_dir: Path | None = None,
    logger: logging.Logger | None = None,
) -> list[Dict[str, Any]]:
    log = logger or _LOG
    explicit_tool_ids = enabled_tool_ids is not None

    configured: list[str] = []
    seen = set()
    for raw in (enabled_tool_ids or []):
        if not isinstance(raw, str):
            continue
        try:
            tool_id = _safe_tool_id(raw)
        except ValueError:
            log.warning("Ignoring invalid tool id in configuration: %r", raw)
            continue
        if tool_id in seen:
            continue
        if tool_id in _LEGACY_CORE_TOOL_IDS:
            log.warning("Ignoring legacy core service token in enabled_tools: %s", tool_id)
            continue
        seen.add(tool_id)
        configured.append(tool_id)

    if explicit_tool_ids:
        selected_tool_ids = configured
    else:
        selected_tool_ids = [
            tool_id
            for tool_id in discover_tool_packages(tools_dir or Path("portal/tools"))
            if tool_id not in _LEGACY_CORE_TOOL_IDS
        ]

    tabs: List[Dict[str, Any]] = []
    registered_blueprints: set[str] = set()
    manifest_mount_targets = _read_tool_mount_targets(private_dir)

    for tool_id in selected_tool_ids:
        module = load_tool_module(tool_id, tools_package=tools_package, logger=log)
        if module is None:
            continue

        meta = resolve_tool_meta(module, tool_id)
        meta["mount_target"] = manifest_mount_targets.get(
            str(meta.get("tool_id") or ""),
            _normalize_mount_target(str(meta.get("mount_target") or "")),
        )
        blueprint = meta.pop("blueprint", None)
        if blueprint is not None:
            bp_name = str(getattr(blueprint, "name", "") or "")
            if bp_name and bp_name in registered_blueprints:
                log.warning("Skipping duplicate blueprint registration for tool '%s' (%s)", meta["tool_id"], bp_name)
                continue
            try:
                app.register_blueprint(blueprint)
                if bp_name:
                    registered_blueprints.add(bp_name)
            except Exception as exc:
                log.warning("Failed to register blueprint for tool '%s': %s", meta["tool_id"], exc)
                continue

        tabs.append(meta)

    return tabs


def active_tool_for_path(tool_tabs: Iterable[Dict[str, Any]], path: str) -> Dict[str, Any] | None:
    tabs = list(tool_tabs or [])
    if not tabs:
        return None

    token = str(path or "").strip() or "/"
    token = token.rstrip("/") or "/"
    for tool in tabs:
        prefix = str(tool.get("route_prefix") or "").strip().rstrip("/")
        if not prefix:
            continue
        if token == prefix or token.startswith(prefix + "/"):
            return tool
    return None


def first_tool_home(tool_tabs: Iterable[Dict[str, Any]]) -> str:
    for tool in tool_tabs or []:
        home_path = str(tool.get("home_path") or "").strip()
        if home_path:
            return home_path
    return ""
