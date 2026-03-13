from __future__ import annotations

import importlib.util
import json
import re
from collections import defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any

from data.engine.constraints import compile_constraint, resolve_chain
from data.engine.graph import META_FIELDS, build_graph, summarize_node
from data.engine.lenses import get_lens
from data.engine.nimm.directives import parse_directive
from data.engine.patterns import describe_pattern_hooks, recognize_row_patterns
from data.engine.nimm.state import (
    DataViewState,
    normalize_aitas_context,
    normalize_mode,
    normalize_source,
)
from data.engine.nimm.viewmodels import empty_pane, pane, response_payload
from data.engine.tables import cluster_rows, infer_tables


_DATUM_ID_RE = re.compile(r"^[0-9]+-[0-9]+-[0-9]+$")
_EVENT_DIRECTIVE_RE = re.compile(
    r"^inv;\(med;(?P<anchor>[0-9]+(?:-[0-9]+)+);event_value\);(?P<row>[0-9]+)$"
)
_MED_DIRECTIVE_RE = re.compile(
    r"^inv;\(med;(?P<anchor>[0-9]+(?:-[0-9]+)+);(?P<method>[a-zA-Z0-9_]+)\);(?P<row>[0-9]+)$"
)
_SAMRAS_ADDRESS_RE = re.compile(r"^[0-9]+(?:-[0-9]+)*$")
_SAMRAS_INSTANCE_RE = re.compile(r"^[0-9]+(?:-[0-9]+)*$")


def _load_shared_mediation_registry() -> ModuleType:
    shared_path = Path(__file__).resolve().parents[3] / "_shared" / "portal" / "mediation" / "registry.py"
    spec = importlib.util.spec_from_file_location("mycite_shared_mediation_registry", shared_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load shared mediation registry from {shared_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SHARED_MEDIATION = _load_shared_mediation_registry()
mediate_decode = _SHARED_MEDIATION.decode_value
mediate_encode = _SHARED_MEDIATION.encode_value


def _load_shared_anthology_normalization() -> ModuleType:
    shared_path = (
        Path(__file__).resolve().parents[3]
        / "_shared"
        / "portal"
        / "data_engine"
        / "anthology_normalization.py"
    )
    spec = importlib.util.spec_from_file_location("mycite_shared_data_engine_anthology_normalization", shared_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load shared anthology normalization module from {shared_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SHARED_ANTHOLOGY_NORMALIZATION = _load_shared_anthology_normalization()
datum_sort_key = _SHARED_ANTHOLOGY_NORMALIZATION.datum_sort_key
parse_datum_identifier = _SHARED_ANTHOLOGY_NORMALIZATION.parse_datum_identifier
compact_iterations = _SHARED_ANTHOLOGY_NORMALIZATION.compact_iterations


class Workspace:
    def __init__(self, storage_backend, config: dict[str, Any] | None = None):
        self.storage = storage_backend
        self.config = config or {}

        self._state_path = self._resolve_state_path()
        self._icon_root = self._resolve_icon_root()
        self._icon_base_url = str(self.config.get("icon_base_url") or "/portal/static/icons").rstrip("/")
        self._icon_relpath_mode = self._resolve_icon_relpath_mode()
        self._startup_warnings: list[str] = []

        self._staged: dict[tuple[str, str, str], str] = {}
        self._staged_presentation_icons: dict[str, str] = {}

        self._rows_by_table: dict[str, list[dict[str, str]]] = {}
        self._tables: dict[str, dict[str, Any]] = {}
        self._graph = build_graph({})
        self._datum_icons_map: dict[str, str] = {}

        self._reload()
        self._state = self._load_state()
        self._sync_staging_from_state()
        self._refresh_panes_for_icon_change()
        self._sync_state_staging()
        self._persist_state()

    def _resolve_state_path(self) -> Path | None:
        token = self.config.get("state_path")
        if not token:
            return None
        try:
            return Path(str(token))
        except Exception:
            return None

    def _resolve_icon_root(self) -> Path | None:
        token = self.config.get("icon_root")
        if not token:
            return None
        try:
            return Path(str(token)).resolve()
        except Exception:
            return None

    def _resolve_icon_relpath_mode(self) -> str:
        token = str(self.config.get("icon_relpath_mode") or "basename").strip().lower()
        if token in {"basename", "path"}:
            return token
        return "basename"

    def _default_focus_source(self) -> str:
        return normalize_source(str(self.config.get("default_focus_source") or "auto"), "auto")

    def _default_mode(self) -> str:
        return normalize_mode(str(self.config.get("default_mode") or "general"), "general")

    def _default_lens(self) -> str:
        token = str(self.config.get("default_lens") or "default").strip().lower()
        return token or "default"

    def _default_state(self) -> DataViewState:
        return DataViewState(
            focus_source=self._default_focus_source(),
            focus_subject="",
            left_pane=empty_pane(),
            right_pane=empty_pane(),
            mode=self._default_mode(),
            lens_context={"default": self._default_lens(), "overrides": {}},
            staged_edits={},
            staged_presentation_edits={"datum_icons": {}},
            validation_errors=[],
            selection={},
            aitas_context=normalize_aitas_context({}),
        )

    def _load_state(self) -> DataViewState:
        if self._state_path is None:
            return self._default_state()

        if not self._state_path.exists() or not self._state_path.is_file():
            return self._default_state()

        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
            return DataViewState.from_dict(
                payload,
                default_focus_source=self._default_focus_source(),
                default_mode=self._default_mode(),
                default_lens=self._default_lens(),
            )
        except Exception:
            self._startup_warnings.append("state_recovered_from_malformed_payload")
            return self._default_state()

    def _persist_state(self) -> None:
        if self._state_path is None:
            return
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(json.dumps(self._state.to_dict(), indent=2) + "\n", encoding="utf-8")
        except Exception:
            return

    def _reload(self) -> None:
        self._rows_by_table = self.storage.load_all_rows()
        self._graph = build_graph(self._rows_by_table)
        title_by_table = {table_id: self.storage.table_title(table_id) for table_id in self.storage.known_tables()}
        self._tables = infer_tables(self._graph, self._rows_by_table, title_by_table)
        self._datum_icons_map = self.storage.load_datum_icons_map()

    def _sync_staging_from_state(self) -> None:
        staged = self._state.staged_edits if isinstance(self._state.staged_edits, dict) else {}
        out: dict[tuple[str, str, str], str] = {}
        for _, item in staged.items():
            if not isinstance(item, dict):
                continue
            table_id = str(item.get("table_id") or "").strip()
            row_id = str(item.get("row_id") or "").strip()
            field_id = str(item.get("field_id") or "").strip()
            value = str(item.get("display_value") or "")
            if table_id and row_id and field_id:
                out[(table_id, row_id, field_id)] = value
        self._staged = out

        staged_presentation = (
            self._state.staged_presentation_edits
            if isinstance(self._state.staged_presentation_edits, dict)
            else {"datum_icons": {}}
        )
        datum_icons = staged_presentation.get("datum_icons") if isinstance(staged_presentation.get("datum_icons"), dict) else {}

        icon_out: dict[str, str] = {}
        for key, value in datum_icons.items():
            datum_id = str(key or "").strip()
            if not datum_id:
                continue
            icon_out[datum_id] = self._canonical_icon_relpath(value)
        self._staged_presentation_icons = icon_out

    def _sync_state_staging(self) -> None:
        staged: dict[str, dict[str, str]] = {}
        for table_id, row_id, field_id in sorted(self._staged.keys()):
            token = f"{table_id}|{row_id}|{field_id}"
            staged[token] = {
                "table_id": table_id,
                "row_id": row_id,
                "field_id": field_id,
                "display_value": self._staged[(table_id, row_id, field_id)],
            }
        self._state.staged_edits = staged
        self._state.staged_presentation_edits = {
            "datum_icons": dict(sorted(self._staged_presentation_icons.items(), key=lambda item: item[0]))
        }

    def _table(self, table_id: str) -> dict[str, Any] | None:
        return self._tables.get(str(table_id or "").strip())

    def _fallback_table_id(self) -> str:
        selected = str((self._state.selection or {}).get("table_id") or "").strip()
        if selected and selected in self._tables:
            return selected
        known = sorted(self._tables.keys())
        return known[0] if known else ""

    @staticmethod
    def _columns(rows: list[dict[str, str]]) -> list[str]:
        preferred = ["identifier", "reference", "magnitude", "label", "references", "msn_id", "name"]
        found: list[str] = []
        for key in preferred:
            for row in rows:
                if key in row and key not in META_FIELDS:
                    found.append(key)
                    break

        discovered: list[str] = []
        for row in rows:
            for key in row.keys():
                if key in META_FIELDS or key in found or key in discovered:
                    continue
                discovered.append(key)

        return found + discovered

    def _rows_for_instance(self, table_id: str, instance_id: str | None) -> list[dict[str, str]]:
        table = self._table(table_id)
        if table is None:
            return []

        rows = list(table.get("rows") or [])
        if not instance_id:
            return rows

        for bucket in cluster_rows(rows):
            if str(bucket.get("instance_id") or "") == str(instance_id):
                return list(bucket.get("rows") or [])
        return []

    @staticmethod
    def _normalize_icon_relpath(value: object) -> str:
        token = str(value or "").strip().replace("\\", "/")
        token = token.lstrip("/")
        if token.startswith("assets/icons/"):
            token = token[len("assets/icons/") :]
        return token

    def _safe_icon_relpath_exists(self, rel: str) -> bool:
        if self._icon_root is None:
            return False
        if not rel or not rel.lower().endswith(".svg"):
            return False

        rel_path = Path(rel)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            return False

        candidate = (self._icon_root / rel_path).resolve()
        try:
            candidate.relative_to(self._icon_root)
        except Exception:
            return False

        return candidate.exists() and candidate.is_file()

    def _icon_relpath_candidates(self, icon_relpath: str) -> list[str]:
        rel = self._normalize_icon_relpath(icon_relpath)
        if not rel:
            return []

        base = Path(rel).name
        if self._icon_relpath_mode == "basename":
            ordered = [base, rel]
        else:
            ordered = [rel, base]

        out: list[str] = []
        for token in ordered:
            token = str(token or "").strip()
            if token and token not in out:
                out.append(token)
        return out

    def _resolve_icon_relpath(self, icon_relpath: str) -> str:
        for candidate in self._icon_relpath_candidates(icon_relpath):
            if self._safe_icon_relpath_exists(candidate):
                return candidate
        return ""

    def _canonical_icon_relpath(self, value: object) -> str:
        rel = self._normalize_icon_relpath(value)
        if not rel:
            return ""
        resolved = self._resolve_icon_relpath(rel)
        if resolved:
            return resolved
        if self._icon_relpath_mode == "basename":
            base = Path(rel).name
            if base:
                return base
        return rel

    def _effective_icon_relpath(self, datum_id: str) -> str:
        token = str(datum_id or "").strip()
        if not token:
            return ""
        if token in self._staged_presentation_icons:
            return self._canonical_icon_relpath(self._staged_presentation_icons[token])
        return self._canonical_icon_relpath(self._datum_icons_map.get(token, ""))

    def _icon_url(self, icon_relpath: str) -> str | None:
        rel = self._resolve_icon_relpath(icon_relpath)
        if not rel:
            return None
        return f"{self._icon_base_url}/{rel}"

    def _icon_meta(self, datum_id: str, label_text: str = "") -> dict[str, Any]:
        rel = self._effective_icon_relpath(datum_id)
        return {
            "datum_id": str(datum_id or ""),
            "label_text": str(label_text or datum_id or ""),
            "icon_relpath": rel or None,
            "icon_url": self._icon_url(rel),
            "icon_assigned": bool(rel),
        }

    def _enrich_datum_entry(self, datum_id: str, label_text: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(extra or {})
        payload.update(self._icon_meta(datum_id, label_text))
        if "identifier" not in payload:
            payload["identifier"] = str(datum_id or "")
        return payload

    def _valid_datum_id(self, datum_id: str) -> bool:
        token = str(datum_id or "").strip()
        if not token:
            return False
        if self._graph.find_by_identifier(token):
            return True
        return bool(_DATUM_ID_RE.fullmatch(token))

    def _icon_exists(self, icon_relpath: str) -> bool:
        rel = self._normalize_icon_relpath(icon_relpath)
        if not rel:
            return True
        return bool(self._resolve_icon_relpath(rel))

    def list_available_icons(self) -> list[str]:
        if self._icon_root is None or not self._icon_root.exists() or not self._icon_root.is_dir():
            return []

        rels: list[str] = []
        for path in sorted(self._icon_root.rglob("*.svg")):
            if not path.is_file():
                continue
            try:
                rel = path.resolve().relative_to(self._icon_root).as_posix()
            except Exception:
                continue
            rels.append(rel)
        if self._icon_relpath_mode == "path":
            return rels

        by_name: dict[str, list[str]] = defaultdict(list)
        for rel in rels:
            by_name[Path(rel).name].append(rel)

        out: list[str] = []
        for name in sorted(by_name.keys()):
            paths = sorted(by_name[name])
            if len(paths) == 1:
                out.append(name)
            else:
                out.extend(paths)
        return out

    def model_meta(self) -> dict[str, Any]:
        return {
            "status": "prototype",
            "data_contract_schema": "mycite.data_workspace.v0",
            "nimm_actions": ["nav", "inv", "med", "man"],
            "focus_sources": ["auto", "anthology", "samras"],
            "aitas_facets": ["attention", "intention", "temporal", "archetype", "spatial", "spacial"],
            "nimm_context_model": "AITAS",
            "pattern_recognition_status": "active_hooks",
            "pattern_hooks": describe_pattern_hooks(),
            "mediation_registry": (
                _SHARED_MEDIATION.list_registry_entries()
                if hasattr(_SHARED_MEDIATION, "list_registry_entries")
                else []
            ),
            "daemon_port_contract": {
                "fields": [
                    "port_id",
                    "datum_ref",
                    "allowed_actions",
                    "default_focus",
                    "output_strategy",
                ],
                "default_output_strategy": "state_snapshot",
            },
            "daemon_ports_count": len(self.daemon_port_catalog()),
            "icon_relpath_mode": self._icon_relpath_mode,
            "guarantees": [
                "UI state is driven by /portal/api/data/* responses, not direct file reads.",
                "Data and icon edits are staged before commit.",
                "Icon assignments are presentation sidecar metadata only.",
                "VG0 selection references are persisted inside anthology magnitude payloads.",
            ],
            "non_guarantees": [
                "Table inference/archetype grouping is still an evolving model.",
                "UI labels and pane layouts are operator-facing prototypes.",
                "Storage adapter is JSON-backed and not yet the final persistence backend.",
            ],
        }

    def list_tables(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for table_id, table in sorted(self._tables.items(), key=lambda item: item[0]):
            archetype_identifier = str(table.get("archetype_identifier") or "")
            meta = self._icon_meta(archetype_identifier, str(table.get("title") or table_id)) if archetype_identifier else {
                "datum_id": "",
                "label_text": str(table.get("title") or table_id),
                "icon_relpath": None,
                "icon_url": None,
                "icon_assigned": False,
            }
            out.append(
                {
                    "table_id": table_id,
                    "title": str(table.get("title") or table_id),
                    "layer": table.get("layer"),
                    "archetype_id": str(table.get("archetype_id") or ""),
                    "archetype_identifier": archetype_identifier,
                    **meta,
                }
            )
        return out

    def list_instances(self, table_id: str) -> list[dict[str, Any]]:
        table = self._table(table_id)
        if table is None:
            return []

        rows = list(table.get("rows") or [])
        out = []
        for bucket in cluster_rows(rows):
            out.append(
                {
                    "instance_id": str(bucket.get("instance_id") or ""),
                    "signature": list(bucket.get("signature") or []),
                    "row_count": len(bucket.get("rows") or []),
                }
            )
        return out

    def daemon_port_catalog(self) -> list[dict[str, Any]]:
        configured = self.config.get("daemon_ports")
        if not isinstance(configured, list):
            return []

        valid_actions = {"nav", "inv", "med", "man"}
        output_strategies = {"state_snapshot", "directive_only", "directive_and_state"}
        action_order = {"inv": 0, "nav": 1, "med": 2, "man": 3}

        out: list[dict[str, Any]] = []
        for item in configured:
            if not isinstance(item, dict):
                continue
            port_id = str(item.get("port_id") or item.get("id") or "").strip()
            datum_ref = str(item.get("datum_ref") or item.get("datum_id") or "").strip()
            if not port_id or not datum_ref:
                continue
            raw_actions = item.get("allowed_actions")
            allowed_actions: list[str] = []
            if isinstance(raw_actions, list):
                for entry in raw_actions:
                    token = str(entry or "").strip().lower()
                    if token in valid_actions and token not in allowed_actions:
                        allowed_actions.append(token)
            elif isinstance(raw_actions, str):
                token = raw_actions.strip().lower()
                if token in valid_actions:
                    allowed_actions = [token]
            if not allowed_actions:
                allowed_actions = ["inv"]

            default_action = str(item.get("default_action") or allowed_actions[0]).strip().lower() or allowed_actions[0]
            if default_action not in valid_actions:
                default_action = allowed_actions[0]
            if default_action not in allowed_actions:
                allowed_actions.insert(0, default_action)
            allowed_actions = sorted(list(dict.fromkeys(allowed_actions)), key=lambda token: action_order.get(token, 99))

            default_method = str(item.get("default_method") or "summary").strip().lower() or "summary"
            default_focus_payload = item.get("default_focus") if isinstance(item.get("default_focus"), dict) else {}
            focus_source = normalize_source(
                str(default_focus_payload.get("focus_source") or item.get("focus_source") or self._default_focus_source()),
                self._default_focus_source(),
            )
            focus_subject = str(default_focus_payload.get("focus_subject") or item.get("focus_subject") or datum_ref).strip() or datum_ref
            output_strategy = str(item.get("output_strategy") or "state_snapshot").strip().lower() or "state_snapshot"
            if output_strategy not in output_strategies:
                output_strategy = "state_snapshot"
            out.append(
                {
                    "port_id": port_id,
                    "datum_ref": datum_ref,
                    "allowed_actions": allowed_actions,
                    "default_action": default_action,
                    "default_method": default_method,
                    "default_focus": {
                        "focus_source": focus_source,
                        "focus_subject": focus_subject,
                    },
                    "output_strategy": output_strategy,
                    "description": str(item.get("description") or "").strip(),
                    "aitas_context": normalize_aitas_context(item.get("aitas_context") if isinstance(item.get("aitas_context"), dict) else {}),
                }
            )
        out.sort(key=lambda payload: str(payload.get("port_id") or ""))
        return out

    def daemon_port_resolve(
        self,
        *,
        port_id: str,
        action: str | None = None,
        method: str | None = None,
        aitas_context: dict[str, Any] | None = None,
        focus_source: str | None = None,
        focus_subject: str | None = None,
        output_strategy: str | None = None,
    ) -> dict[str, Any]:
        token = str(port_id or "").strip()
        if not token:
            return {"ok": False, "errors": ["port_id is required"], "warnings": []}

        port = next((item for item in self.daemon_port_catalog() if str(item.get("port_id") or "") == token), None)
        if port is None:
            return {"ok": False, "errors": [f"unknown daemon port: {token}"], "warnings": []}

        valid_actions = {"nav", "inv", "med", "man"}
        allowed_actions = [
            str(entry or "").strip().lower()
            for entry in list(port.get("allowed_actions") or [])
            if str(entry or "").strip().lower() in valid_actions
        ]
        if not allowed_actions:
            allowed_actions = [str(port.get("default_action") or "inv").strip().lower() or "inv"]

        resolved_action = str(action or port.get("default_action") or allowed_actions[0]).strip().lower() or allowed_actions[0]
        if resolved_action not in valid_actions:
            resolved_action = allowed_actions[0]
        if resolved_action not in allowed_actions:
            return {
                "ok": False,
                "errors": [f"action '{resolved_action}' is not allowed for daemon port '{token}'"],
                "warnings": [],
                "allowed_actions": allowed_actions,
                "policy": {
                    "port_id": token,
                    "allowed_actions": allowed_actions,
                    "resolved_action": resolved_action,
                    "enforced": True,
                },
            }

        resolved_method = str(method or port.get("default_method") or "").strip().lower()
        merged_aitas = normalize_aitas_context(port.get("aitas_context") if isinstance(port.get("aitas_context"), dict) else {})
        merged_aitas.update(normalize_aitas_context(aitas_context if isinstance(aitas_context, dict) else {}))
        default_focus = port.get("default_focus") if isinstance(port.get("default_focus"), dict) else {}
        resolved_focus_source = normalize_source(
            str(focus_source or default_focus.get("focus_source") or self._state.focus_source or self._default_focus_source()),
            self._default_focus_source(),
        )
        resolved_focus_subject = str(focus_subject or default_focus.get("focus_subject") or port.get("datum_ref") or "").strip()
        resolved_output_strategy = str(output_strategy or port.get("output_strategy") or "state_snapshot").strip().lower() or "state_snapshot"
        if resolved_output_strategy not in {"state_snapshot", "directive_only", "directive_and_state"}:
            resolved_output_strategy = "state_snapshot"

        directive_payload = {
            "action": resolved_action,
            "subject": resolved_focus_subject,
            "method": resolved_method,
            "args": {
                **merged_aitas,
                "focus_source": resolved_focus_source,
            },
        }
        response: dict[str, Any] = {
            "ok": True,
            "errors": [],
            "warnings": [],
            "port": port,
            "allowed_actions": allowed_actions,
            "policy": {
                "port_id": token,
                "allowed_actions": allowed_actions,
                "resolved_action": resolved_action,
                "enforced": True,
            },
            "default_focus": {
                "focus_source": resolved_focus_source,
                "focus_subject": resolved_focus_subject,
            },
            "output_strategy": resolved_output_strategy,
            "directive": directive_payload,
        }
        if resolved_output_strategy == "state_snapshot":
            response["state_snapshot"] = self.get_state_snapshot().get("state", {})
        elif resolved_output_strategy == "directive_and_state":
            response["state_snapshot"] = self.get_state_snapshot()
        return response

    def daemon_resolve_tokens(
        self,
        *,
        tokens: list[str],
        standard_id: str = "coordinate",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cleaned = [str(item or "").strip() for item in list(tokens or []) if str(item or "").strip()]
        if not cleaned:
            return {"ok": False, "errors": ["tokens[] is required"], "warnings": []}

        if len(cleaned) > 2048:
            return {"ok": False, "errors": ["tokens[] exceeds maximum size of 2048"], "warnings": []}

        anthology_rows = list(self.storage.load_rows("anthology") or [])
        by_identifier: dict[str, dict[str, Any]] = {}
        for row in anthology_rows:
            identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
            if identifier:
                by_identifier[identifier] = row

        resolved_rows: list[dict[str, Any]] = []
        warnings: list[str] = []
        errors: list[str] = []
        for token in cleaned:
            source = "raw"
            resolved_identifier = ""
            resolved_reference = ""
            resolved_magnitude = token

            row = by_identifier.get(token)
            if row is None:
                for candidate in self._datum_identifier_candidates(token):
                    row = by_identifier.get(candidate)
                    if row is not None:
                        break
            if row is not None:
                source = "anthology_datum"
                resolved_identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
                first_reference, first_magnitude = self._first_pair(self._pairs_from_row(row))
                resolved_reference = first_reference
                resolved_magnitude = first_magnitude or token

            decoded = mediate_decode(
                standard_id=standard_id,
                reference=resolved_reference,
                magnitude=resolved_magnitude,
                context=context or {},
            )
            warnings.extend([str(item) for item in list(decoded.get("warnings") or [])])
            errors.extend([str(item) for item in list(decoded.get("errors") or [])])
            resolved_rows.append(
                {
                    "token": token,
                    "source": source,
                    "resolved_identifier": resolved_identifier,
                    "resolved_reference": resolved_reference,
                    "resolved_magnitude": resolved_magnitude,
                    "mediation": decoded,
                }
            )

        return {
            "ok": not errors,
            "errors": errors,
            "warnings": warnings,
            "standard_id": str(standard_id or "").strip().lower(),
            "resolved": resolved_rows,
        }

    def get_view(self, table_id: str, instance_id: str | None = None, mode: str = "general") -> dict[str, Any]:
        table_key = str(table_id or "").strip()
        mode_token = normalize_mode(mode, self._default_mode())

        errors: list[str] = []
        warnings: list[str] = []

        table = self._table(table_key)
        if table is None:
            errors.append(f"Unknown table_id: {table_key}")
            return {
                "table": {"table_id": table_key, "title": table_key, "layer": None, "archetype_id": ""},
                "instance": {"instance_id": str(instance_id or ""), "signature": [], "row_count": 0},
                "mode": mode_token,
                "columns": [],
                "rows": [],
                "staged_edits": [],
                "errors": errors,
                "warnings": warnings,
            }

        rows = self._rows_for_instance(table_key, instance_id)
        columns = self._columns(rows)

        view_rows: list[dict[str, Any]] = []
        for row in rows:
            row_id = str(row.get("row_id") or "").strip()
            row_fields: dict[str, str] = {}
            row_staged: list[str] = []
            row_errors: list[str] = []
            row_warnings: list[str] = []

            datum_id = str(row.get("identifier") or row.get("msn_id") or row_id).strip()
            label_text = str(row.get("label") or row.get("name") or datum_id).strip()

            for field_id in columns:
                lens = get_lens(field_id, lens_context=self._state.lens_context, config=self.config)
                raw_value = str(row.get(field_id) or "")
                display_value = lens.render(lens.decode(raw_value))

                staged_key = (table_key, row_id, field_id)
                if staged_key in self._staged:
                    display_value = self._staged[staged_key]
                    row_staged.append(field_id)

                row_fields[field_id] = display_value

            inspect = {}
            if mode_token == "inspect":
                node_id = str(row.get("_node_id") or f"{table_key}:{row_id}")
                node = self._graph.get_node(node_id)
                if node is not None:
                    chain = resolve_chain(self._graph, node.node_id)
                    constraint = compile_constraint(node, chain)
                    row_warnings.extend(list(constraint.get("warnings") or []))
                    inspect = {"chain": chain, "constraint": constraint}

            view_rows.append(
                {
                    "row_id": row_id,
                    "datum_id": datum_id,
                    "label_text": label_text,
                    **self._icon_meta(datum_id, label_text),
                    "fields": row_fields,
                    "staged_fields": row_staged,
                    "errors": row_errors,
                    "warnings": row_warnings,
                    "inspect": inspect,
                }
            )

        staged_edits = [
            {
                "table_id": t,
                "row_id": r,
                "field_id": f,
                "display_value": value,
            }
            for (t, r, f), value in sorted(self._staged.items())
            if t == table_key
        ]

        return {
            "table": {
                "table_id": table_key,
                "title": str(table.get("title") or table_key),
                "layer": table.get("layer"),
                "archetype_id": str(table.get("archetype_id") or ""),
            },
            "instance": {
                "instance_id": str(instance_id or ""),
                "signature": [],
                "row_count": len(rows),
            },
            "mode": mode_token,
            "columns": columns,
            "rows": view_rows,
            "staged_edits": staged_edits,
            "errors": errors,
            "warnings": warnings,
        }

    @staticmethod
    def _parse_datum_identifier(identifier: str) -> tuple[int | None, int | None, int | None]:
        return parse_datum_identifier(identifier)

    @staticmethod
    def _pairs_from_row(row: dict[str, Any]) -> list[dict[str, str]]:
        raw_pairs = row.get("pairs")
        pairs: list[dict[str, str]] = []
        if isinstance(raw_pairs, list):
            for item in raw_pairs:
                if not isinstance(item, dict):
                    continue
                reference = str(item.get("reference") or "").strip()
                magnitude = str(item.get("magnitude") or "").strip()
                if not reference and not magnitude:
                    continue
                pairs.append({"reference": reference, "magnitude": magnitude})
        if pairs:
            return pairs

        reference = str(row.get("reference") or "").strip()
        magnitude = str(row.get("magnitude") or "").strip()
        if not reference and not magnitude:
            return []
        return [{"reference": reference, "magnitude": magnitude}]

    @staticmethod
    def _first_pair(pairs: list[dict[str, str]]) -> tuple[str, str]:
        if not pairs:
            return ("", "")
        first = pairs[0]
        return (str(first.get("reference") or "").strip(), str(first.get("magnitude") or "").strip())

    @staticmethod
    def _required_pair_count(value_group: int) -> int:
        # VG0 still requires at least one reference/magnitude pair.
        if value_group <= 0:
            return 1
        return int(value_group)

    @staticmethod
    def _normalize_pairs_for_value_group(
        value_group: int,
        raw_pairs: list[dict[str, str]],
    ) -> tuple[list[dict[str, str]], list[str]]:
        normalized_pairs: list[dict[str, str]] = []
        errors: list[str] = []
        is_vg0 = value_group == 0

        for index, item in enumerate(raw_pairs):
            reference_token = str(item.get("reference") or "").strip()
            magnitude_token = str(item.get("magnitude") or "").strip()

            if not reference_token:
                errors.append(f"pair {index + 1}: reference is required")
                continue

            if is_vg0:
                normalized_pairs.append({"reference": reference_token, "magnitude": "0"})
                continue

            if not magnitude_token:
                errors.append(f"pair {index + 1}: magnitude is required")
                continue

            normalized_pairs.append({"reference": reference_token, "magnitude": magnitude_token})

        return normalized_pairs, errors

    @staticmethod
    def _encode_reference_list_magnitude(references: list[str]) -> str:
        cleaned = [str(item or "").strip() for item in references if str(item or "").strip()]
        return json.dumps(cleaned, separators=(",", ":"))

    @staticmethod
    def _parse_reference_list_magnitude(raw: Any) -> list[str]:
        token = str(raw or "").strip()
        if not token:
            return []

        values: list[str] = []
        if token.startswith("[") and token.endswith("]"):
            try:
                payload = json.loads(token)
                if isinstance(payload, list):
                    values = [str(item or "").strip() for item in payload]
            except Exception:
                values = []

        if not values:
            values = [part.strip() for part in token.split(",")]

        out: list[str] = []
        seen: set[str] = set()
        for item in values:
            if not item or item == "0" or item in seen:
                continue
            out.append(item)
            seen.add(item)
        return out

    def _selection_references_for_row(self, row: dict[str, Any], value_group: int | None = None) -> list[str]:
        group = value_group
        if group is None:
            identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
            _, group, _ = self._parse_datum_identifier(identifier)
        if group != 0:
            return []

        refs: list[str] = []
        seen: set[str] = set()
        for pair in self._pairs_from_row(row):
            reference = str(pair.get("reference") or "").strip()
            if not reference or reference == "0" or reference in seen:
                continue
            refs.append(reference)
            seen.add(reference)

        if refs:
            return refs

        for reference in self._parse_reference_list_magnitude(row.get("magnitude")):
            if reference in seen:
                continue
            refs.append(reference)
            seen.add(reference)
        return refs

    def _anthology_row_sort_key(self, row: dict[str, Any]) -> tuple[int, int, int, str]:
        return datum_sort_key(row.get("identifier"), row.get("row_id"))

    def _remap_identifier_token(self, token: str, identifier_map: dict[str, str]) -> str:
        raw = str(token or "").strip()
        if not raw:
            return ""
        direct = identifier_map.get(raw)
        if direct:
            return direct

        tail = self._qualified_tail_identifier(raw)
        if not tail:
            return raw
        mapped_tail = identifier_map.get(tail)
        if not mapped_tail:
            return raw

        parts = raw.split("-")
        if len(parts) < 4 or not all(part.isdigit() for part in parts):
            return raw
        return "-".join(parts[:-3] + mapped_tail.split("-"))

    def _remap_reference_token(
        self,
        token: str,
        identifier_map: dict[str, str],
        event_rownum_map: dict[int, int],
        iteration_map_by_group: dict[tuple[int, int], dict[int, int]],
    ) -> str:
        raw = str(token or "").strip()
        if not raw:
            return ""

        directive_match = _MED_DIRECTIVE_RE.fullmatch(raw)
        if directive_match is not None:
            anchor = str(directive_match.group("anchor") or "").strip()
            method = str(directive_match.group("method") or "").strip()
            try:
                row_number = int(str(directive_match.group("row") or ""))
            except Exception:
                row_number = 0

            if row_number > 0:
                if method == "event_value":
                    row_number = int(event_rownum_map.get(row_number, row_number))
                elif method == "samras_table":
                    row_number = int(iteration_map_by_group.get((1, 1), {}).get(row_number, row_number))

            remapped_anchor = self._remap_identifier_token(anchor, identifier_map)
            if remapped_anchor != anchor or row_number != int(str(directive_match.group("row") or "0") or 0):
                return f"inv;(med;{remapped_anchor};{method});{row_number}"

        return self._remap_identifier_token(raw, identifier_map)

    def _compact_anthology_iterations(self, anthology_rows: list[dict[str, Any]]) -> dict[str, Any]:
        rows = [dict(row) for row in list(anthology_rows or [])]
        old_event_rows = self._event_rows_from_anthology(rows)
        compaction = compact_iterations(rows)
        rows = [dict(row) for row in list(compaction.rows or [])]
        identifier_map = {
            str(old_id): str(new_id)
            for old_id, new_id in dict(compaction.identifier_map or {}).items()
        }
        changed = bool(compaction.changed)

        iteration_map_by_group: dict[tuple[int, int], dict[int, int]] = {}
        for old_identifier, new_identifier in identifier_map.items():
            old_layer, old_group, old_iteration = self._parse_datum_identifier(old_identifier)
            new_layer, new_group, new_iteration = self._parse_datum_identifier(new_identifier)
            if not all(isinstance(item, int) for item in [old_layer, old_group, old_iteration, new_layer, new_group, new_iteration]):
                continue
            if old_layer != new_layer or old_group != new_group:
                continue
            iteration_map_by_group.setdefault((int(old_layer), int(old_group)), {})[int(old_iteration)] = int(new_iteration)

        old_event_rownum_by_identifier = {
            str(row.get("identifier") or row.get("row_id") or "").strip(): index
            for index, row in enumerate(old_event_rows, start=1)
            if str(row.get("identifier") or row.get("row_id") or "").strip()
        }
        new_event_rows = self._event_rows_from_anthology(rows)
        new_event_rownum_by_identifier = {
            str(row.get("identifier") or row.get("row_id") or "").strip(): index
            for index, row in enumerate(new_event_rows, start=1)
            if str(row.get("identifier") or row.get("row_id") or "").strip()
        }
        event_rownum_map: dict[int, int] = {}
        for old_identifier, old_row_number in old_event_rownum_by_identifier.items():
            new_identifier = identifier_map.get(old_identifier, old_identifier)
            new_row_number = new_event_rownum_by_identifier.get(new_identifier)
            if isinstance(new_row_number, int) and new_row_number > 0:
                event_rownum_map[int(old_row_number)] = int(new_row_number)

        for row in rows:
            pairs = self._pairs_from_row(row)
            remapped_pairs: list[dict[str, str]] = []
            for pair in pairs:
                reference = str(pair.get("reference") or "").strip()
                magnitude = str(pair.get("magnitude") or "").strip()
                remapped_reference = self._remap_reference_token(
                    reference,
                    identifier_map,
                    event_rownum_map,
                    iteration_map_by_group,
                )
                if remapped_reference != reference:
                    changed = True
                remapped_pairs.append({"reference": remapped_reference, "magnitude": magnitude})
            row["pairs"] = remapped_pairs

            first_reference, first_magnitude = self._first_pair(remapped_pairs)
            if str(row.get("reference") or "").strip() != first_reference:
                row["reference"] = first_reference
                changed = True

            identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
            _, value_group, _ = self._parse_datum_identifier(identifier)

            if value_group == 0:
                magnitude_refs = self._parse_reference_list_magnitude(row.get("magnitude"))
                if magnitude_refs:
                    remapped_refs = [
                        self._remap_reference_token(
                            reference,
                            identifier_map,
                            event_rownum_map,
                            iteration_map_by_group,
                        )
                        for reference in magnitude_refs
                    ]
                    encoded_refs = self._encode_reference_list_magnitude(remapped_refs)
                    if str(row.get("magnitude") or "").strip() != encoded_refs:
                        row["magnitude"] = encoded_refs
                        changed = True
            else:
                if str(row.get("magnitude") or "").strip() != first_magnitude:
                    row["magnitude"] = first_magnitude
                    changed = True

        rows.sort(key=self._anthology_row_sort_key)
        return {
            "rows": rows,
            "identifier_map": identifier_map,
            "changed": changed,
        }

    def _remap_state_for_identifier_map(self, identifier_map: dict[str, str]) -> None:
        if not identifier_map:
            return

        changed = False

        remapped_staged: dict[tuple[str, str, str], str] = {}
        for (table_id, row_id, field_id), value in self._staged.items():
            if table_id != "anthology":
                remapped_staged[(table_id, row_id, field_id)] = value
                continue
            next_row_id = str(identifier_map.get(row_id) or "").strip()
            if not next_row_id:
                changed = True
                continue
            if next_row_id != row_id:
                changed = True
            remapped_staged[(table_id, next_row_id, field_id)] = value
        if changed:
            self._staged = remapped_staged

        remapped_presentation: dict[str, str] = {}
        for datum_id, icon_relpath in self._staged_presentation_icons.items():
            next_datum_id = str(identifier_map.get(datum_id) or "").strip()
            if not next_datum_id:
                changed = True
                continue
            if next_datum_id != datum_id:
                changed = True
            if next_datum_id in remapped_presentation:
                continue
            remapped_presentation[next_datum_id] = icon_relpath
        if remapped_presentation != self._staged_presentation_icons:
            self._staged_presentation_icons = remapped_presentation
            changed = True

        if isinstance(self._state.selection, dict):
            selection_table = str(self._state.selection.get("table_id") or "").strip()
            if selection_table == "anthology":
                selection_row = str(self._state.selection.get("row_id") or "").strip()
                if selection_row:
                    remapped_row = str(identifier_map.get(selection_row) or "").strip()
                    if remapped_row and remapped_row != selection_row:
                        self._state.selection["row_id"] = remapped_row
                        changed = True
                    elif not remapped_row:
                        self._state.selection.pop("row_id", None)
                        changed = True

        focus_subject = str(self._state.focus_subject or "").strip()
        remapped_focus_subject = self._remap_identifier_token(focus_subject, identifier_map)
        if remapped_focus_subject != focus_subject:
            self._state.focus_subject = remapped_focus_subject
            changed = True

        if changed:
            self._sync_state_staging()

    def _remap_icon_map_for_identifier_map(self, identifier_map: dict[str, str]) -> dict[str, Any]:
        if not identifier_map:
            return {"ok": True, "errors": [], "warnings": [], "changed": False}

        current_map = dict(self._datum_icons_map or {})
        next_map: dict[str, str] = {}
        changed = False
        warnings: list[str] = []

        for datum_id, icon_relpath in current_map.items():
            mapped_id = str(identifier_map.get(str(datum_id or "").strip()) or "").strip()
            if not mapped_id:
                changed = True
                continue
            if mapped_id != datum_id:
                changed = True
            if mapped_id in next_map and next_map[mapped_id] != icon_relpath:
                warnings.append(f"icon collision during identifier remap for {mapped_id}; kept first mapping")
                changed = True
                continue
            next_map[mapped_id] = icon_relpath

        if not changed:
            return {"ok": True, "errors": [], "warnings": warnings, "changed": False}

        result = self.storage.persist_datum_icons_map(next_map)
        if bool(result.get("ok")):
            self._datum_icons_map = next_map
        return {
            "ok": bool(result.get("ok")),
            "errors": list(result.get("errors") or []),
            "warnings": warnings + list(result.get("warnings") or []),
            "changed": True,
        }

    def _sync_vg0_magnitude_from_anthology(self, anthology_rows: list[dict[str, Any]]) -> dict[str, Any]:
        compact_result = self._compact_anthology_iterations(anthology_rows)
        compacted_rows = [dict(row) for row in list(compact_result.get("rows") or [])]
        identifier_map = (
            compact_result.get("identifier_map")
            if isinstance(compact_result.get("identifier_map"), dict)
            else {}
        )
        compaction_changed = bool(compact_result.get("changed"))

        anthology_rows[:] = compacted_rows
        changed = False
        for row in anthology_rows:
            identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
            if not identifier:
                continue
            _, value_group, _ = self._parse_datum_identifier(identifier)
            if value_group != 0:
                continue

            refs = self._selection_references_for_row(row, value_group=0)
            encoded_refs = self._encode_reference_list_magnitude(refs)
            normalized_pairs = [
                {
                    "reference": reference,
                    "magnitude": encoded_refs if index == 0 else "0",
                }
                for index, reference in enumerate(refs)
            ]
            first_reference = refs[0] if refs else ""

            if self._pairs_from_row(row) != normalized_pairs:
                row["pairs"] = normalized_pairs
                changed = True
            if str(row.get("reference") or "").strip() != first_reference:
                row["reference"] = first_reference
                changed = True
            if str(row.get("magnitude") or "").strip() != encoded_refs:
                row["magnitude"] = encoded_refs
                changed = True

        changed = changed or compaction_changed
        if not changed:
            return {
                "ok": True,
                "errors": [],
                "warnings": [],
                "changed": False,
                "identifier_map": identifier_map,
            }
        result = self.storage.persist_rows("anthology", anthology_rows)
        if not bool(result.get("ok")):
            return {
                "ok": False,
                "errors": list(result.get("errors") or []),
                "warnings": list(result.get("warnings") or []),
                "changed": True,
                "identifier_map": identifier_map,
            }

        warnings: list[str] = list(result.get("warnings") or [])
        changed_identifier_map = {
            str(old_id): str(new_id)
            for old_id, new_id in identifier_map.items()
            if str(old_id) != str(new_id)
        }
        if changed_identifier_map:
            icon_result = self._remap_icon_map_for_identifier_map(identifier_map)
            if not bool(icon_result.get("ok")):
                warnings.append("anthology normalized but failed to remap icon sidecar identifiers")
                warnings.extend(list(icon_result.get("errors") or []))
            warnings.extend(list(icon_result.get("warnings") or []))
            self._remap_state_for_identifier_map(identifier_map)

        return {
            "ok": True,
            "errors": [],
            "warnings": warnings,
            "changed": True,
            "identifier_map": identifier_map,
        }

    def _local_msn_id(self) -> str:
        return str(self.config.get("msn_id") or "").strip()

    @staticmethod
    def _is_numeric_hyphen_token(token: str) -> bool:
        parts = str(token or "").split("-")
        return bool(parts) and all(part.isdigit() for part in parts)

    @staticmethod
    def _qualified_tail_identifier(token: str) -> str:
        parts = str(token or "").split("-")
        if len(parts) < 4 or not all(part.isdigit() for part in parts):
            return ""
        return "-".join(parts[-3:])

    def _qualified_ref(self, identifier: str) -> str:
        local_msn_id = self._local_msn_id()
        if not local_msn_id:
            return str(identifier or "").strip()
        return f"{local_msn_id}-{str(identifier or '').strip()}"

    def _normalize_external_ref(self, value: str, *, field_name: str = "reference") -> tuple[str, str | None]:
        token = str(value or "").strip()
        if not token:
            return "", f"{field_name} is required"

        if _DATUM_ID_RE.fullmatch(token):
            local_msn_id = self._local_msn_id()
            if not local_msn_id:
                return "", f"{field_name}: local msn_id is not configured"
            return f"{local_msn_id}-{token}", None

        if self._is_numeric_hyphen_token(token):
            tail = self._qualified_tail_identifier(token)
            if _DATUM_ID_RE.fullmatch(tail):
                return token, None

        return "", f"{field_name}: expected <datum_address> or <msn_id>-<datum_address>"

    def _event_identifier_candidates(self, token: str) -> list[str]:
        candidate = str(token or "").strip()
        if not candidate:
            return []

        out: list[str] = []
        if _DATUM_ID_RE.fullmatch(candidate):
            out.append(candidate)
        tail = self._qualified_tail_identifier(candidate)
        if _DATUM_ID_RE.fullmatch(tail) and tail not in out:
            out.append(tail)
        return out

    def _datum_identifier_candidates(self, token: str) -> list[str]:
        candidate = str(token or "").strip()
        if not candidate:
            return []

        out: list[str] = []
        if _DATUM_ID_RE.fullmatch(candidate):
            out.append(candidate)
        tail = self._qualified_tail_identifier(candidate)
        if _DATUM_ID_RE.fullmatch(tail) and tail not in out:
            out.append(tail)
        return out

    def _resolve_anthology_row(self, token: str, anthology_rows: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
        candidates = self._datum_identifier_candidates(token)
        if not candidates:
            return None, ""

        for candidate in candidates:
            for row in anthology_rows:
                identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
                if identifier == candidate:
                    return row, candidate
        return None, ""

    def _parse_event_directive_ref(self, token: str) -> tuple[str, int] | None:
        raw = str(token or "").strip()
        match = _EVENT_DIRECTIVE_RE.fullmatch(raw)
        if not match:
            return None
        anchor = str(match.group("anchor") or "").strip()
        try:
            row_number = int(str(match.group("row") or ""))
        except Exception:
            return None
        if row_number < 1:
            return None
        return (anchor, row_number)

    def _event_directive_ref(self, row_number: int) -> str:
        if int(row_number) < 1:
            return ""
        anchor = self._qualified_ref("4-0-1") or "4-0-1"
        return f"inv;(med;{anchor};event_value);{int(row_number)}"

    def _event_row_number_for_identifier(self, identifier: str, anthology_rows: list[dict[str, Any]]) -> int | None:
        target = str(identifier or "").strip()
        if not target:
            return None
        event_rows = self._event_rows_from_anthology(anthology_rows)
        for index, row in enumerate(event_rows, start=1):
            row_identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
            if row_identifier == target:
                return index
        return None

    def _event_rows_from_anthology(self, anthology_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in anthology_rows:
            identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
            layer, value_group, iteration = self._parse_datum_identifier(identifier)
            if layer == 4 and value_group == 1 and isinstance(iteration, int):
                out.append(row)
        out.sort(
            key=lambda row: (
                self._parse_datum_identifier(str(row.get("identifier") or row.get("row_id") or ""))[2] or 10**9,
                str(row.get("identifier") or row.get("row_id") or ""),
            )
        )
        return out

    def _event_index_refs(self, anthology_rows: list[dict[str, Any]]) -> list[str]:
        refs: list[str] = []
        for row_number, _row in enumerate(self._event_rows_from_anthology(anthology_rows), start=1):
            ref = self._event_directive_ref(row_number)
            if ref:
                refs.append(ref)
        return refs

    @staticmethod
    def _row_reference_tokens(row: dict[str, Any]) -> list[str]:
        refs: list[str] = []
        pairs = row.get("pairs")
        if isinstance(pairs, list):
            for pair in pairs:
                if not isinstance(pair, dict):
                    continue
                token = str(pair.get("reference") or "").strip()
                if token:
                    refs.append(token)

        legacy_reference = str(row.get("reference") or "").strip()
        if legacy_reference:
            refs.append(legacy_reference)

        references_text = str(row.get("references") or "").strip()
        if references_text:
            refs.extend(part.strip() for part in references_text.split(",") if part.strip())
        return refs

    def _event_enabled_tables(self, anthology_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        event_rows = self._event_rows_from_anthology(anthology_rows)
        internal_ids = {
            str(item.get("identifier") or item.get("row_id") or "").strip()
            for item in event_rows
        }
        internal_ids = {item for item in internal_ids if item}
        qualified_ids = {self._qualified_ref(item) for item in internal_ids}
        directive_ids = {self._event_directive_ref(index) for index, _item in enumerate(event_rows, start=1)}
        all_event_refs = internal_ids | qualified_ids | directive_ids

        out: list[dict[str, Any]] = []
        for table_meta in self.list_tables():
            table_id = str(table_meta.get("table_id") or "").strip()
            table = self._table(table_id)
            if table is None:
                continue
            rows = list(table.get("rows") or [])
            event_row_count = 0
            for row in rows:
                refs = self._row_reference_tokens(row)
                if any(ref in all_event_refs for ref in refs):
                    event_row_count += 1
            if event_row_count == 0:
                continue
            out.append(
                {
                    "table_id": table_id,
                    "title": str(table_meta.get("title") or table_id),
                    "row_count": len(rows),
                    "event_row_count": event_row_count,
                }
            )
        out.sort(key=lambda item: str(item.get("table_id") or ""))
        return out

    def _event_anchor_allowed_refs(self, anthology_rows: list[dict[str, Any]]) -> set[str]:
        anchor_row: dict[str, Any] | None = None
        for row in anthology_rows:
            identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
            if identifier == "4-0-1":
                anchor_row = row
                break
        if anchor_row is None:
            return set()

        allowed: set[str] = set()
        for pair in self._pairs_from_row(anchor_row):
            reference = str(pair.get("reference") or "").strip()
            if not reference or reference == "0":
                continue
            allowed.add(reference)
            if _DATUM_ID_RE.fullmatch(reference):
                qualified = self._qualified_ref(reference)
                if qualified:
                    allowed.add(qualified)
            tail = self._qualified_tail_identifier(reference)
            if _DATUM_ID_RE.fullmatch(tail):
                allowed.add(tail)
                qualified_tail = self._qualified_ref(tail)
                if qualified_tail:
                    allowed.add(qualified_tail)
        return allowed

    def _ensure_time_series_anchor_row(self, anthology_rows: list[dict[str, Any]]) -> bool:
        required_refs = ["3-2-2", "3-2-3"]
        required_encoded = self._encode_reference_list_magnitude(required_refs)
        required_pairs = [
            {"reference": required_refs[0], "magnitude": required_encoded},
            {"reference": required_refs[1], "magnitude": "0"},
        ]

        anchor_row: dict[str, Any] | None = None
        for row in anthology_rows:
            identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
            if identifier == "4-0-1":
                anchor_row = row
                break

        if anchor_row is None:
            anthology_rows.append(
                {
                    "row_id": "4-0-1",
                    "identifier": "4-0-1",
                    "reference": required_pairs[0]["reference"],
                    "magnitude": required_encoded,
                    "pairs": list(required_pairs),
                    "label": "event_value_collection",
                    "_source": "anthology",
                }
            )
            return True

        existing_pairs = self._pairs_from_row(anchor_row)
        normalized_refs: list[str] = []
        seen_refs: set[str] = set()
        seen_tails: set[str] = set()
        changed = False

        for pair in existing_pairs:
            reference = str(pair.get("reference") or "").strip()
            if not reference or reference == "0":
                changed = True
                continue
            if reference in seen_refs:
                changed = True
                continue
            normalized_refs.append(reference)
            seen_refs.add(reference)
            tail = self._qualified_tail_identifier(reference)
            if _DATUM_ID_RE.fullmatch(tail):
                seen_tails.add(tail)
            if _DATUM_ID_RE.fullmatch(reference):
                seen_tails.add(reference)

        for required_ref in required_refs:
            if required_ref in seen_tails or required_ref in seen_refs:
                continue
            normalized_refs.append(required_ref)
            changed = True

        if not normalized_refs:
            normalized_refs = list(required_refs)
            changed = True

        encoded_refs = self._encode_reference_list_magnitude(normalized_refs)
        normalized_pairs = [
            {
                "reference": reference,
                "magnitude": encoded_refs if index == 0 else "0",
            }
            for index, reference in enumerate(normalized_refs)
        ]
        first_reference = str(normalized_refs[0] if normalized_refs else "").strip()
        if str(anchor_row.get("reference") or "").strip() != first_reference:
            changed = True
        if str(anchor_row.get("magnitude") or "").strip() != encoded_refs:
            changed = True
        if str(anchor_row.get("label") or "").strip() == "":
            changed = True

        anchor_row["row_id"] = "4-0-1"
        anchor_row["identifier"] = "4-0-1"
        anchor_row["reference"] = first_reference
        anchor_row["magnitude"] = encoded_refs
        anchor_row["pairs"] = normalized_pairs
        anchor_row["label"] = str(anchor_row.get("label") or "event_value_collection").strip()
        anchor_row["_source"] = "anthology"
        return changed

    @staticmethod
    def _parse_int_token(raw: Any, *, field_name: str, minimum: int = 0) -> tuple[int | None, str | None]:
        token = str(raw if raw is not None else "").strip()
        if not token:
            return None, f"{field_name} is required"
        try:
            value = int(token)
        except Exception:
            return None, f"{field_name} must be an integer"
        if value < minimum:
            return None, f"{field_name} must be >= {minimum}"
        return value, None

    def _event_payload_from_row(self, row: dict[str, Any], *, row_number: int | None = None) -> dict[str, Any]:
        identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
        pairs = self._pairs_from_row(row)
        point_pair = pairs[0] if len(pairs) >= 1 else {"reference": "", "magnitude": ""}
        duration_pair = pairs[1] if len(pairs) >= 2 else {"reference": "", "magnitude": ""}
        start_value, _ = self._parse_int_token(point_pair.get("magnitude"), field_name="start_unix_s", minimum=0)
        duration_value, _ = self._parse_int_token(duration_pair.get("magnitude"), field_name="duration_s", minimum=1)
        if row_number is None:
            _, _, parsed_iteration = self._parse_datum_identifier(identifier)
            row_number = parsed_iteration if isinstance(parsed_iteration, int) and parsed_iteration > 0 else None
        event_value_ref = self._event_directive_ref(row_number) if isinstance(row_number, int) and row_number > 0 else ""
        return {
            "row_id": str(row.get("row_id") or identifier).strip(),
            "identifier": identifier,
            "event_ref": self._qualified_ref(identifier),
            "event_value_ref": event_value_ref,
            "event_row_number": row_number,
            "label": str(row.get("label") or identifier).strip(),
            "point_ref": str(point_pair.get("reference") or "").strip(),
            "duration_ref": str(duration_pair.get("reference") or "").strip(),
            "start_unix_s": start_value,
            "duration_s": duration_value,
            "pair_count": len(pairs),
        }

    def anthology_table_view(self) -> dict[str, Any]:
        rows = list(self.storage.load_rows("anthology") or [])
        normalized_rows: list[dict[str, Any]] = []
        parse_warnings = list(self.storage.anthology_parse_warnings()) if hasattr(self.storage, "anthology_parse_warnings") else []

        for row in rows:
            datum_id = str(row.get("identifier") or row.get("row_id") or "").strip()
            layer, value_group, iteration = self._parse_datum_identifier(datum_id)
            label_text = str(row.get("label") or datum_id).strip()
            pairs = self._pairs_from_row(row)
            first_reference, first_magnitude = self._first_pair(pairs)
            selection_references = self._selection_references_for_row(row, value_group=value_group)
            if value_group == 0:
                first_magnitude = self._encode_reference_list_magnitude(selection_references)
            payload = {
                "row_id": str(row.get("row_id") or datum_id).strip(),
                "identifier": datum_id,
                "reference": first_reference,
                "magnitude": first_magnitude,
                "pairs": pairs,
                "pair_count": len(pairs),
                "label": label_text,
                "layer": layer,
                "value_group": value_group,
                "iteration": iteration,
                "selection_references": selection_references,
                "selection_count": len(selection_references),
                **self._icon_meta(datum_id, label_text),
            }
            payload["patterns"] = recognize_row_patterns(payload)
            normalized_rows.append(payload)

        normalized_rows.sort(key=lambda item: datum_sort_key(item.get("identifier"), item.get("row_id")))

        grouped: dict[int | None, dict[int | None, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        for row in normalized_rows:
            grouped[row.get("layer")][row.get("value_group")].append(row)

        layers: list[dict[str, Any]] = []
        for layer in sorted(grouped.keys(), key=lambda value: (10**9 if value is None else int(value))):
            value_groups: list[dict[str, Any]] = []
            for value_group in sorted(
                grouped[layer].keys(),
                key=lambda value: (10**9 if value is None else int(value)),
            ):
                rows_for_group = list(grouped[layer][value_group])
                value_groups.append(
                    {
                        "value_group": value_group,
                        "row_count": len(rows_for_group),
                        "rows": rows_for_group,
                    }
                )

            layers.append(
                {
                    "layer": layer,
                    "row_count": sum(item["row_count"] for item in value_groups),
                    "value_groups": value_groups,
                }
            )

        return {
            "table": {"table_id": "anthology", "title": "Anthology", "row_count": len(normalized_rows)},
            "layers": layers,
            "rows": normalized_rows,
            "warnings": parse_warnings,
        }

    def anthology_graph_view(
        self,
        *,
        focus_identifier: str = "",
        depth_limit: int | None = None,
        layout_mode: str = "linear",
        context_mode: str = "global",
    ) -> dict[str, Any]:
        table_view = self.anthology_table_view()
        rows = list(table_view.get("rows") or [])
        by_identifier = {
            str(item.get("identifier") or "").strip(): item
            for item in rows
            if str(item.get("identifier") or "").strip()
        }

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        unresolved_count = 0

        for row in rows:
            identifier = str(row.get("identifier") or "").strip()
            if not identifier:
                continue
            label_text = str(row.get("label") or identifier).strip()
            row_pairs = list(row.get("pairs") or [])
            try:
                value_group_token = int(row.get("value_group"))
            except Exception:
                value_group_token = -1
            pair_count = len([item for item in row_pairs if isinstance(item, dict)])
            if value_group_token == 0:
                pattern_kind = "collection"
            elif pair_count <= 1:
                pattern_kind = "typed_leaf"
            else:
                pattern_kind = "composite"
            nodes.append(
                {
                    "node_id": identifier,
                    "identifier": identifier,
                    "row_id": str(row.get("row_id") or identifier).strip(),
                    "label": label_text,
                    "layer": row.get("layer"),
                    "value_group": row.get("value_group"),
                    "iteration": row.get("iteration"),
                    "pair_count": pair_count,
                    "pattern_kind": pattern_kind,
                    "selection_count": int(row.get("selection_count") or 0),
                    **self._icon_meta(identifier, label_text),
                }
            )

            references: list[str] = []
            if value_group_token == 0:
                references = [str(item or "").strip() for item in list(row.get("selection_references") or [])]
            else:
                references = [
                    str((pair or {}).get("reference") or "").strip()
                    for pair in row_pairs
                    if isinstance(pair, dict)
                ]

            seen_refs: set[str] = set()
            for reference in references:
                if not reference or reference in seen_refs:
                    continue
                seen_refs.add(reference)

                target_identifier = ""
                for candidate in self._datum_identifier_candidates(reference):
                    if candidate in by_identifier:
                        target_identifier = candidate
                        break

                edge_id = f"{identifier}->{target_identifier or reference}"
                if not target_identifier:
                    unresolved_count += 1
                edges.append(
                    {
                        "edge_id": edge_id,
                        "source": identifier,
                        "target": target_identifier or reference,
                        "reference": reference,
                        "resolved": bool(target_identifier),
                    }
                )

        nodes.sort(
            key=lambda item: (
                10**9 if item.get("layer") is None else int(item.get("layer")),
                10**9 if item.get("value_group") is None else int(item.get("value_group")),
                10**9 if item.get("iteration") is None else int(item.get("iteration")),
                str(item.get("identifier") or ""),
            )
        )
        edges.sort(key=lambda item: (str(item.get("source") or ""), str(item.get("target") or ""), str(item.get("reference") or "")))

        layout_token = str(layout_mode or "linear").strip().lower() or "linear"
        if layout_token not in {"linear", "radial"}:
            layout_token = "linear"
        context_token = str(context_mode or "global").strip().lower() or "global"
        if context_token not in {"global", "local"}:
            context_token = "global"
        focus_token = str(focus_identifier or "").strip()
        depth_token = depth_limit if isinstance(depth_limit, int) and depth_limit >= 0 else 2

        filtered_nodes = list(nodes)
        filtered_edges = list(edges)
        if focus_token and focus_token in by_identifier and context_token == "local":
            adjacency: dict[str, set[str]] = defaultdict(set)
            for edge in filtered_edges:
                source = str(edge.get("source") or "").strip()
                target = str(edge.get("target") or "").strip()
                if not source or not target:
                    continue
                if source not in by_identifier or target not in by_identifier:
                    continue
                adjacency[source].add(target)
                adjacency[target].add(source)

            included: set[str] = {focus_token}
            frontier: set[str] = {focus_token}
            for _ in range(depth_token):
                next_frontier: set[str] = set()
                for node_id in frontier:
                    next_frontier.update(adjacency.get(node_id, set()))
                next_frontier -= included
                if not next_frontier:
                    break
                included.update(next_frontier)
                frontier = next_frontier

            filtered_nodes = [node for node in filtered_nodes if str(node.get("identifier") or "") in included]
            filtered_edges = [
                edge
                for edge in filtered_edges
                if str(edge.get("source") or "") in included and str(edge.get("target") or "") in included
            ]

        layers: list[dict[str, Any]] = []
        bucketed: dict[int | None, list[dict[str, Any]]] = defaultdict(list)
        for node in filtered_nodes:
            bucketed[node.get("layer")].append(node)
        for layer in sorted(bucketed.keys(), key=lambda value: (10**9 if value is None else int(value))):
            layer_nodes = list(bucketed[layer])
            layers.append(
                {
                    "layer": layer,
                    "node_count": len(layer_nodes),
                    "nodes": layer_nodes,
                }
            )

        unresolved_filtered = sum(1 for edge in filtered_edges if not bool(edge.get("resolved")))

        return {
            "ok": True,
            "errors": [],
            "warnings": list(table_view.get("warnings") or []),
            "nodes": filtered_nodes,
            "edges": filtered_edges,
            "layers": layers,
            "focus": {
                "identifier": focus_token,
                "active": bool(focus_token and focus_token in by_identifier),
                "context_mode": context_token,
                "depth_limit": depth_token,
            },
            "layout": {
                "mode": layout_token,
                "supported_modes": ["linear", "radial"],
            },
            "stats": {
                "node_count": len(filtered_nodes),
                "edge_count": len(filtered_edges),
                "unresolved_edge_count": unresolved_filtered,
            },
        }

    def time_series_ensure_base(self) -> dict[str, Any]:
        rows = list(self.storage.load_rows("anthology") or [])
        changed = self._ensure_time_series_anchor_row(rows)

        warnings: list[str] = []
        if changed:
            result = self.storage.persist_rows("anthology", rows)
            if not bool(result.get("ok")):
                return {"ok": False, "errors": list(result.get("errors") or ["failed to persist anthology"]), "warnings": []}
            warnings.extend(list(result.get("warnings") or []))

        sync_result = self._sync_vg0_magnitude_from_anthology(rows)
        if not bool(sync_result.get("ok")):
            return {
                "ok": False,
                "errors": ["failed to sync VG0 selection magnitudes"] + list(sync_result.get("errors") or []),
                "warnings": warnings + list(sync_result.get("warnings") or []),
            }

        warnings.extend(list(sync_result.get("warnings") or []))
        self._reload()
        self._refresh_panes_for_icon_change()
        self._persist_state()
        state_payload = self.time_series_state()
        return {
            "ok": True,
            "errors": [],
            "warnings": warnings + list(state_payload.get("warnings") or []),
            "changed": changed,
            "state": state_payload,
        }

    def time_series_state(self) -> dict[str, Any]:
        anthology_rows = list(self.storage.load_rows("anthology") or [])
        event_rows = self._event_rows_from_anthology(anthology_rows)
        events = [
            self._event_payload_from_row(row, row_number=index)
            for index, row in enumerate(event_rows, start=1)
        ]
        events.sort(
            key=lambda item: (
                -(item.get("start_unix_s") if isinstance(item.get("start_unix_s"), int) else -1),
                -(self._parse_datum_identifier(str(item.get("identifier") or ""))[2] or -1),
            )
        )

        anchor_internal = "4-0-1"
        anchor_qualified = self._qualified_ref(anchor_internal)
        indexed_event_refs = self._event_index_refs(anthology_rows)
        return {
            "ok": True,
            "errors": [],
            "warnings": [],
            "anchor_internal": anchor_internal,
            "anchor_qualified": anchor_qualified,
            "anchor_directive_base": f"inv;(med;{anchor_qualified or anchor_internal};event_value);<row_number>",
            "anchor_allowed_refs": sorted(self._event_anchor_allowed_refs(anthology_rows)),
            "indexed_event_refs_internal": list(indexed_event_refs),
            "indexed_event_refs_qualified": list(indexed_event_refs),
            "events": events,
            "event_enabled_tables": self._event_enabled_tables(anthology_rows),
        }

    def _resolve_event_row(self, event_ref: str, anthology_rows: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
        directive = self._parse_event_directive_ref(event_ref)
        if directive is not None:
            anchor, row_number = directive
            allowed_anchors = {"4-0-1", self._qualified_ref("4-0-1")}
            if anchor in allowed_anchors:
                event_rows = self._event_rows_from_anthology(anthology_rows)
                if 1 <= row_number <= len(event_rows):
                    row = event_rows[row_number - 1]
                    identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
                    if identifier:
                        return row, identifier

        candidates = self._event_identifier_candidates(event_ref)
        if not candidates:
            return None, ""

        for candidate in candidates:
            layer, value_group, _ = self._parse_datum_identifier(candidate)
            if layer != 4 or value_group != 1:
                continue
            for row in anthology_rows:
                identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
                if identifier == candidate:
                    return row, candidate
        return None, ""

    def time_series_create_event(
        self,
        *,
        point_ref: str,
        duration_ref: str,
        start_unix_s: Any,
        duration_s: Any,
        label: str = "",
    ) -> dict[str, Any]:
        point_norm, point_err = self._normalize_external_ref(point_ref, field_name="point_ref")
        duration_norm, duration_err = self._normalize_external_ref(duration_ref, field_name="duration_ref")
        start_value, start_err = self._parse_int_token(start_unix_s, field_name="start_unix_s", minimum=0)
        duration_value, duration_err = self._parse_int_token(duration_s, field_name="duration_s", minimum=1)

        errors = [err for err in [point_err, duration_err, start_err, duration_err] if err]
        if errors:
            return {"ok": False, "errors": errors, "warnings": []}

        rows = list(self.storage.load_rows("anthology") or [])
        self._ensure_time_series_anchor_row(rows)
        anchor_allowed_refs = self._event_anchor_allowed_refs(rows)
        if not anchor_allowed_refs:
            return {
                "ok": False,
                "errors": ["event anchor 4-0-1 has no allowed references; add 3-2-2 and 3-2-3 to 4-0-1 first"],
                "warnings": [],
            }
        anchor_errors: list[str] = []
        if point_norm not in anchor_allowed_refs:
            anchor_errors.append(f"point_ref must be defined in 4-0-1 (got: {point_norm})")
        if duration_norm not in anchor_allowed_refs:
            anchor_errors.append(f"duration_ref must be defined in 4-0-1 (got: {duration_norm})")
        if anchor_errors:
            return {"ok": False, "errors": anchor_errors, "warnings": []}

        existing_ids = {
            str(row.get("identifier") or row.get("row_id") or "").strip()
            for row in rows
            if str(row.get("identifier") or row.get("row_id") or "").strip()
        }

        next_iteration = 1
        for row in rows:
            identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
            layer, value_group, iteration = self._parse_datum_identifier(identifier)
            if layer == 4 and value_group == 1 and isinstance(iteration, int):
                next_iteration = max(next_iteration, iteration + 1)

        next_identifier = f"4-1-{next_iteration}"
        while next_identifier in existing_ids:
            next_iteration += 1
            next_identifier = f"4-1-{next_iteration}"

        pair_payload = [
            {"reference": point_norm, "magnitude": str(start_value)},
            {"reference": duration_norm, "magnitude": str(duration_value)},
        ]
        new_row = {
            "row_id": next_identifier,
            "identifier": next_identifier,
            "reference": point_norm,
            "magnitude": str(start_value),
            "pairs": pair_payload,
            "label": str(label or "").strip(),
            "_source": "anthology",
        }
        rows.append(new_row)

        result = self.storage.persist_rows("anthology", rows)
        if not bool(result.get("ok")):
            return {"ok": False, "errors": list(result.get("errors") or ["failed to persist anthology"]), "warnings": []}
        warnings = list(result.get("warnings") or [])

        sync_result = self._sync_vg0_magnitude_from_anthology(rows)
        if not bool(sync_result.get("ok")):
            return {
                "ok": False,
                "errors": ["anthology updated, but failed to recompute VG0 selection magnitudes"] + list(sync_result.get("errors") or []),
                "warnings": warnings + list(sync_result.get("warnings") or []),
            }
        warnings.extend(list(sync_result.get("warnings") or []))
        identifier_map = (
            sync_result.get("identifier_map")
            if isinstance(sync_result.get("identifier_map"), dict)
            else {}
        )
        final_identifier = str(identifier_map.get(next_identifier) or next_identifier).strip()
        self._reload()
        self._refresh_panes_for_icon_change()
        self._persist_state()

        rows_after = list(self.storage.load_rows("anthology") or [])
        final_event_row, _ = self._resolve_event_row(final_identifier, rows_after)
        event_row_number = self._event_row_number_for_identifier(final_identifier, rows_after)
        return {
            "ok": True,
            "errors": [],
            "warnings": warnings,
            "event": self._event_payload_from_row(final_event_row or new_row, row_number=event_row_number),
            "state": self.time_series_state(),
        }

    def time_series_update_event(
        self,
        *,
        event_ref: str,
        point_ref: str | None = None,
        duration_ref: str | None = None,
        start_unix_s: Any | None = None,
        duration_s: Any | None = None,
        label: str | None = None,
    ) -> dict[str, Any]:
        rows = list(self.storage.load_rows("anthology") or [])
        event_row, identifier = self._resolve_event_row(event_ref, rows)
        if event_row is None:
            return {"ok": False, "errors": [f"unknown event_ref: {event_ref}"], "warnings": []}

        existing_pairs = self._pairs_from_row(event_row)
        existing_point = existing_pairs[0] if len(existing_pairs) >= 1 else {"reference": "", "magnitude": ""}
        existing_duration = existing_pairs[1] if len(existing_pairs) >= 2 else {"reference": "", "magnitude": ""}

        point_value = point_ref if point_ref is not None else existing_point.get("reference")
        duration_value = duration_ref if duration_ref is not None else existing_duration.get("reference")
        start_value_raw = start_unix_s if start_unix_s is not None else existing_point.get("magnitude")
        duration_value_raw = duration_s if duration_s is not None else existing_duration.get("magnitude")

        point_norm, point_err = self._normalize_external_ref(str(point_value or ""), field_name="point_ref")
        duration_norm, duration_err = self._normalize_external_ref(str(duration_value or ""), field_name="duration_ref")
        start_value, start_err = self._parse_int_token(start_value_raw, field_name="start_unix_s", minimum=0)
        duration_value_int, duration_err = self._parse_int_token(duration_value_raw, field_name="duration_s", minimum=1)

        errors = [err for err in [point_err, duration_err, start_err, duration_err] if err]
        if errors:
            return {"ok": False, "errors": errors, "warnings": []}

        self._ensure_time_series_anchor_row(rows)
        anchor_allowed_refs = self._event_anchor_allowed_refs(rows)
        if not anchor_allowed_refs:
            return {
                "ok": False,
                "errors": ["event anchor 4-0-1 has no allowed references; add 3-2-2 and 3-2-3 to 4-0-1 first"],
                "warnings": [],
            }
        anchor_errors: list[str] = []
        if point_norm not in anchor_allowed_refs:
            anchor_errors.append(f"point_ref must be defined in 4-0-1 (got: {point_norm})")
        if duration_norm not in anchor_allowed_refs:
            anchor_errors.append(f"duration_ref must be defined in 4-0-1 (got: {duration_norm})")
        if anchor_errors:
            return {"ok": False, "errors": anchor_errors, "warnings": []}

        event_row["pairs"] = [
            {"reference": point_norm, "magnitude": str(start_value)},
            {"reference": duration_norm, "magnitude": str(duration_value_int)},
        ]
        event_row["reference"] = point_norm
        event_row["magnitude"] = str(start_value)
        if label is not None:
            event_row["label"] = str(label or "").strip()

        result = self.storage.persist_rows("anthology", rows)
        if not bool(result.get("ok")):
            return {"ok": False, "errors": list(result.get("errors") or ["failed to persist anthology"]), "warnings": []}
        warnings = list(result.get("warnings") or [])

        sync_result = self._sync_vg0_magnitude_from_anthology(rows)
        if not bool(sync_result.get("ok")):
            return {
                "ok": False,
                "errors": ["anthology updated, but failed to recompute VG0 selection magnitudes"] + list(sync_result.get("errors") or []),
                "warnings": warnings + list(sync_result.get("warnings") or []),
            }
        warnings.extend(list(sync_result.get("warnings") or []))

        self._reload()
        self._refresh_panes_for_icon_change()
        self._persist_state()

        # event_row may be stale after reload; resolve again for response payload.
        rows_after = list(self.storage.load_rows("anthology") or [])
        updated_row, _ = self._resolve_event_row(identifier, rows_after)
        updated_row_number = self._event_row_number_for_identifier(identifier, rows_after)
        return {
            "ok": True,
            "errors": [],
            "warnings": warnings,
            "event": self._event_payload_from_row(updated_row or event_row, row_number=updated_row_number),
            "state": self.time_series_state(),
        }

    def time_series_delete_event(self, *, event_ref: str) -> dict[str, Any]:
        rows = list(self.storage.load_rows("anthology") or [])
        event_row, identifier = self._resolve_event_row(event_ref, rows)
        if event_row is None:
            return {"ok": False, "errors": [f"unknown event_ref: {event_ref}"], "warnings": []}
        deleted_row_number = self._event_row_number_for_identifier(identifier, rows)
        deleted_event_value_ref = (
            self._event_directive_ref(deleted_row_number)
            if isinstance(deleted_row_number, int) and deleted_row_number > 0
            else ""
        )

        kept_rows: list[dict[str, Any]] = []
        for row in rows:
            row_identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
            if row_identifier == identifier:
                continue
            kept_rows.append(row)

        result = self.storage.persist_rows("anthology", kept_rows)
        if not bool(result.get("ok")):
            return {"ok": False, "errors": list(result.get("errors") or ["failed to persist anthology"]), "warnings": []}
        warnings = list(result.get("warnings") or [])

        sync_result = self._sync_vg0_magnitude_from_anthology(kept_rows)
        if not bool(sync_result.get("ok")):
            return {
                "ok": False,
                "errors": ["anthology updated, but failed to recompute VG0 selection magnitudes"] + list(sync_result.get("errors") or []),
                "warnings": warnings + list(sync_result.get("warnings") or []),
            }
        warnings.extend(list(sync_result.get("warnings") or []))

        self._reload()
        self._refresh_panes_for_icon_change()
        self._persist_state()
        return {
            "ok": True,
            "errors": [],
            "warnings": warnings,
            "deleted_event_ref": self._qualified_ref(identifier),
            "deleted_event_value_ref": deleted_event_value_ref,
            "state": self.time_series_state(),
        }

    def time_series_event_detail(self, *, event_ref: str) -> dict[str, Any]:
        anthology_rows = list(self.storage.load_rows("anthology") or [])
        event_row, identifier = self._resolve_event_row(event_ref, anthology_rows)
        if event_row is None:
            return {"ok": False, "errors": [f"unknown event_ref: {event_ref}"], "warnings": []}

        qualified_identifier = self._qualified_ref(identifier)
        event_row_number = self._event_row_number_for_identifier(identifier, anthology_rows)
        directive_identifier = (
            self._event_directive_ref(event_row_number)
            if isinstance(event_row_number, int) and event_row_number > 0
            else ""
        )
        ref_candidates = {identifier, qualified_identifier}
        if directive_identifier:
            ref_candidates.add(directive_identifier)
        referenced_by: list[dict[str, Any]] = []
        for row in anthology_rows:
            row_identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
            if row_identifier == identifier:
                continue
            refs = self._row_reference_tokens(row)
            if not any(ref in ref_candidates for ref in refs):
                continue
            layer, value_group, iteration = self._parse_datum_identifier(row_identifier)
            referenced_by.append(
                {
                    "row_id": str(row.get("row_id") or row_identifier).strip(),
                    "identifier": row_identifier,
                    "label": str(row.get("label") or row_identifier).strip(),
                    "layer": layer,
                    "value_group": value_group,
                    "iteration": iteration,
                }
            )
        referenced_by.sort(
            key=lambda item: (
                10**9 if item.get("layer") is None else int(item.get("layer")),
                10**9 if item.get("value_group") is None else int(item.get("value_group")),
                10**9 if item.get("iteration") is None else int(item.get("iteration")),
                str(item.get("identifier") or ""),
            )
        )

        return {
            "ok": True,
            "errors": [],
            "warnings": [],
            "event": self._event_payload_from_row(event_row, row_number=event_row_number),
            "referenced_by": referenced_by,
            "event_enabled_tables": self._event_enabled_tables(anthology_rows),
        }

    def time_series_table_view(self, *, table_id: str, mode: str = "normal") -> dict[str, Any]:
        table_key = str(table_id or "").strip()
        if not table_key:
            return {"ok": False, "errors": ["table_id is required"], "warnings": []}

        table = self._table(table_key)
        if table is None:
            return {"ok": False, "errors": [f"unknown table_id: {table_key}"], "warnings": []}

        anthology_rows = list(self.storage.load_rows("anthology") or [])
        event_rows = self._event_rows_from_anthology(anthology_rows)
        event_map: dict[str, dict[str, Any]] = {}
        for row_number, row in enumerate(event_rows, start=1):
            payload = self._event_payload_from_row(row, row_number=row_number)
            internal_id = str(payload.get("identifier") or "").strip()
            qualified_id = str(payload.get("event_ref") or "").strip()
            directive_id = str(payload.get("event_value_ref") or "").strip()
            if internal_id:
                event_map[internal_id] = payload
            if qualified_id:
                event_map[qualified_id] = payload
            if directive_id:
                event_map[directive_id] = payload

        out_rows: list[dict[str, Any]] = []
        for row in list(table.get("rows") or []):
            identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
            refs = self._row_reference_tokens(row)
            event_links: list[dict[str, Any]] = []
            for ref in refs:
                event_payload = event_map.get(ref)
                if not event_payload:
                    continue
                event_links.append(
                    {
                        "event_ref": str(event_payload.get("event_ref") or ""),
                        "event_value_ref": str(event_payload.get("event_value_ref") or ""),
                        "start_unix_s": event_payload.get("start_unix_s"),
                        "duration_s": event_payload.get("duration_s"),
                        "label": event_payload.get("label"),
                    }
                )
            out_rows.append(
                {
                    "row_id": str(row.get("row_id") or identifier).strip(),
                    "identifier": identifier,
                    "label": str(row.get("label") or identifier).strip(),
                    "event_links": event_links,
                    "raw": dict(row),
                }
            )

        mode_token = str(mode or "normal").strip().lower()
        if mode_token not in {"normal", "time_series"}:
            mode_token = "normal"

        if mode_token == "time_series":
            for item in out_rows:
                links = list(item.get("event_links") or [])
                links.sort(key=lambda link: (10**18 if link.get("start_unix_s") is None else int(link.get("start_unix_s"))))
                item["event_links"] = links
            out_rows.sort(
                key=lambda item: (
                    10**18 if not item.get("event_links") else int(item["event_links"][0].get("start_unix_s") or 10**18),
                    str(item.get("identifier") or ""),
                )
            )
        else:
            out_rows.sort(key=lambda item: str(item.get("identifier") or ""))

        groups: list[dict[str, Any]] = []
        if mode_token == "time_series":
            grouped: dict[str, dict[str, Any]] = {}
            for item in out_rows:
                if not item.get("event_links"):
                    key = "unlinked"
                    label = "Unlinked"
                else:
                    start_token = str(item["event_links"][0].get("start_unix_s"))
                    key = start_token
                    label = f"start_unix_s={start_token}"
                bucket = grouped.setdefault(key, {"group_key": key, "label": label, "rows": []})
                bucket["rows"].append(item)
            groups = list(grouped.values())
            groups.sort(key=lambda g: (10**18 if g.get("group_key") == "unlinked" else int(g.get("group_key") or 10**18)))

        return {
            "ok": True,
            "errors": [],
            "warnings": [],
            "mode": mode_token,
            "table": {
                "table_id": table_key,
                "title": str(table.get("title") or table_key),
                "row_count": len(out_rows),
            },
            "rows": out_rows,
            "groups": groups,
        }

    @staticmethod
    def _samras_sort_key(token: str) -> tuple[int, ...]:
        raw = str(token or "").strip()
        parts = [part for part in raw.split("-") if part != ""]
        out: list[int] = []
        for part in parts:
            try:
                out.append(int(part))
            except Exception:
                out.append(10**9)
        return tuple(out or [10**9])

    def _normalize_samras_instance_id(self, value: str) -> tuple[str, str | None]:
        token = str(value or "").strip()
        if not token:
            return "", "instance_id is required"
        if _SAMRAS_INSTANCE_RE.fullmatch(token) is None:
            return "", "instance_id must be numeric-hyphen format (e.g. 1-1-4)"
        return token, None

    def _normalize_samras_address_id(self, value: str) -> tuple[str, str | None]:
        token = str(value or "").strip()
        if not token:
            return "", "address_id is required"
        if _SAMRAS_ADDRESS_RE.fullmatch(token) is None:
            return "", "address_id must be numeric-hyphen format"
        return token, None

    @staticmethod
    def _samras_filter_match(row: dict[str, Any], filter_text: str) -> bool:
        token = str(filter_text or "").strip().lower()
        if not token:
            return True
        return token in str(row.get("address_id") or "").lower() or token in str(row.get("title") or "").lower()

    def _samras_link_metadata_from_label(self, label: str) -> dict[str, Any] | None:
        raw = str(label or "").strip()
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        if str(payload.get("schema") or "") != "mycite.samras.link.v1":
            return None
        instance_id = str(payload.get("instance_id") or "").strip()
        table_name = str(payload.get("table_name") or "").strip()
        if not instance_id:
            return None
        return {
            "schema": "mycite.samras.link.v1",
            "instance_id": instance_id,
            "table_name": table_name,
        }

    def _encode_samras_link_label(self, *, instance_id: str, table_name: str) -> str:
        payload = {
            "schema": "mycite.samras.link.v1",
            "instance_id": str(instance_id or "").strip(),
            "table_name": str(table_name or "").strip(),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def _samras_link_rows(self, anthology_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for row in anthology_rows:
            identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
            layer, value_group, iteration = self._parse_datum_identifier(identifier)
            if layer != 1 or value_group != 1:
                continue
            metadata = self._samras_link_metadata_from_label(str(row.get("label") or ""))
            if metadata is None:
                continue
            instance_id = str(metadata.get("instance_id") or "").strip()
            if not instance_id:
                continue
            out[instance_id] = {
                "instance_id": instance_id,
                "table_name": str(metadata.get("table_name") or "").strip(),
                "identifier": identifier,
                "iteration": iteration,
                "label": str(row.get("label") or "").strip(),
                "pairs": self._pairs_from_row(row),
            }
        return out

    def _samras_table_directive_ref(self, row_number: int) -> str:
        anchor = self._qualified_ref("1-0-1") or "1-0-1"
        return f"inv;(med;{anchor};samras_table);{int(row_number)}"

    def _ensure_samras_anchor_and_link(self, *, instance_id: str, table_name: str) -> dict[str, Any]:
        anthology_rows = list(self.storage.load_rows("anthology") or [])
        existing_links = self._samras_link_rows(anthology_rows)
        if instance_id in existing_links:
            return {
                "ok": True,
                "errors": [],
                "warnings": [],
                "linked": False,
                "instance_id": instance_id,
                "directive_ref": "",
                "link_identifier": str(existing_links[instance_id].get("identifier") or ""),
            }

        max_iteration = 0
        for row in anthology_rows:
            identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
            layer, value_group, iteration = self._parse_datum_identifier(identifier)
            if layer == 1 and value_group == 1 and isinstance(iteration, int):
                max_iteration = max(max_iteration, iteration)
        next_iteration = max_iteration + 1
        link_identifier = f"1-1-{next_iteration}"
        directive_ref = self._samras_table_directive_ref(next_iteration)

        link_row = {
            "row_id": link_identifier,
            "identifier": link_identifier,
            "reference": directive_ref,
            "magnitude": instance_id,
            "pairs": [{"reference": directive_ref, "magnitude": instance_id}],
            "label": self._encode_samras_link_label(instance_id=instance_id, table_name=table_name),
            "_source": "anthology",
        }
        anthology_rows.append(link_row)

        anchor_row: dict[str, Any] | None = None
        for row in anthology_rows:
            identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
            if identifier == "1-0-1":
                anchor_row = row
                break
        if anchor_row is None:
            anchor_row = {
                "row_id": "1-0-1",
                "identifier": "1-0-1",
                "reference": directive_ref,
                "magnitude": "0",
                "pairs": [{"reference": directive_ref, "magnitude": "0"}],
                "label": "samras_tables",
                "_source": "anthology",
            }
            anthology_rows.append(anchor_row)
        else:
            anchor_pairs = self._pairs_from_row(anchor_row)
            if directive_ref not in {str(item.get("reference") or "").strip() for item in anchor_pairs}:
                anchor_pairs.append({"reference": directive_ref, "magnitude": "0"})
            first_reference, _ = self._first_pair(anchor_pairs)
            anchor_row["row_id"] = "1-0-1"
            anchor_row["identifier"] = "1-0-1"
            anchor_row["reference"] = first_reference or directive_ref
            anchor_row["magnitude"] = "0"
            anchor_row["pairs"] = anchor_pairs
            anchor_row["label"] = str(anchor_row.get("label") or "samras_tables").strip()
            anchor_row["_source"] = "anthology"

        persist_result = self.storage.persist_rows("anthology", anthology_rows)
        if not bool(persist_result.get("ok")):
            return {
                "ok": False,
                "errors": list(persist_result.get("errors") or ["failed to persist anthology link row"]),
                "warnings": list(persist_result.get("warnings") or []),
            }
        sync_result = self._sync_vg0_magnitude_from_anthology(anthology_rows)
        if not bool(sync_result.get("ok")):
            return {
                "ok": False,
                "errors": ["failed to sync VG0 selection magnitudes"] + list(sync_result.get("errors") or []),
                "warnings": list(persist_result.get("warnings") or []) + list(sync_result.get("warnings") or []),
            }
        identifier_map = (
            sync_result.get("identifier_map")
            if isinstance(sync_result.get("identifier_map"), dict)
            else {}
        )
        final_link_identifier = str(identifier_map.get(link_identifier) or link_identifier).strip()
        _, _, final_link_iteration = self._parse_datum_identifier(final_link_identifier)
        final_directive_ref = (
            self._samras_table_directive_ref(final_link_iteration)
            if isinstance(final_link_iteration, int) and final_link_iteration > 0
            else directive_ref
        )
        self._reload()
        self._refresh_panes_for_icon_change()
        self._persist_state()
        return {
            "ok": True,
            "errors": [],
            "warnings": list(persist_result.get("warnings") or []) + list(sync_result.get("warnings") or []),
            "linked": True,
            "instance_id": instance_id,
            "directive_ref": final_directive_ref,
            "link_identifier": final_link_identifier,
        }

    def _samras_rows_sorted(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = [dict(row) for row in rows]
        out.sort(key=lambda item: self._samras_sort_key(str(item.get("address_id") or item.get("row_id") or "")))
        return out

    def _samras_graph(
        self,
        rows: list[dict[str, Any]],
        *,
        filter_text: str = "",
        expanded_nodes: set[str] | None = None,
        collapsed_depth: int = 2,
    ) -> dict[str, Any]:
        by_id: dict[str, dict[str, Any]] = {}
        children: dict[str, list[str]] = defaultdict(list)
        warnings: list[str] = []

        for row in rows:
            address_id = str(row.get("address_id") or row.get("row_id") or "").strip()
            title = str(row.get("title") or row.get("name") or "").strip()
            if not address_id:
                continue
            depth = len(address_id.split("-"))
            parent_id = "-".join(address_id.split("-")[:-1]) if depth > 1 else ""
            by_id[address_id] = {
                "address_id": address_id,
                "title": title,
                "depth": depth,
                "parent_id": parent_id,
            }

        for address_id, node in by_id.items():
            parent_id = str(node.get("parent_id") or "")
            if parent_id and parent_id not in by_id:
                warnings.append(f"{address_id}: missing parent {parent_id}")
            if parent_id and parent_id in by_id:
                children[parent_id].append(address_id)

        for key in list(children.keys()):
            children[key].sort(key=self._samras_sort_key)

        roots = sorted(
            [token for token, node in by_id.items() if not str(node.get("parent_id") or "") or str(node.get("parent_id")) not in by_id],
            key=self._samras_sort_key,
        )

        filter_token = str(filter_text or "").strip().lower()
        focus: set[str] = set()
        if filter_token:
            for node_id, node in by_id.items():
                if filter_token in node_id.lower() or filter_token in str(node.get("title") or "").lower():
                    focus.add(node_id)
            expanded_focus = set(focus)
            for node_id in list(focus):
                parent = str(by_id.get(node_id, {}).get("parent_id") or "")
                while parent:
                    expanded_focus.add(parent)
                    parent = str(by_id.get(parent, {}).get("parent_id") or "")
            focus = expanded_focus
        else:
            focus = set(by_id.keys())

        expanded = {str(token).strip() for token in (expanded_nodes or set()) if str(token).strip()}
        visible_nodes: list[dict[str, Any]] = []

        def _visit(node_id: str) -> None:
            if node_id not in by_id or node_id not in focus:
                return
            node = dict(by_id[node_id])
            node_children = [child for child in children.get(node_id, []) if child in focus]
            has_children = bool(node_children)
            is_expanded = bool(filter_token) or node["depth"] < collapsed_depth or node_id in expanded
            node["has_children"] = has_children
            node["is_expanded"] = bool(is_expanded and has_children)
            visible_nodes.append(node)
            if has_children and is_expanded:
                for child_id in node_children:
                    _visit(child_id)

        for root_id in roots:
            _visit(root_id)

        columns: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for node in visible_nodes:
            columns[int(node["depth"])].append(node)
        out_columns = [
            {"depth": depth, "nodes": columns[depth]}
            for depth in sorted(columns.keys())
        ]
        return {
            "collapsed_depth": collapsed_depth,
            "filter": filter_token,
            "expanded": sorted(expanded, key=self._samras_sort_key),
            "roots": roots,
            "columns": out_columns,
            "visible_count": len(visible_nodes),
            "total_count": len(by_id),
            "warnings": warnings,
        }

    def samras_instances(self) -> dict[str, Any]:
        msn_id = self._local_msn_id()
        if not msn_id:
            return {"ok": False, "errors": ["msn_id is not configured"], "warnings": []}
        if not hasattr(self.storage, "list_samras_instances"):
            return {"ok": False, "errors": ["storage backend does not support SAMRAS instances"], "warnings": []}

        discovered = list(self.storage.list_samras_instances(msn_id))  # type: ignore[attr-defined]
        anthology_rows = list(self.storage.load_rows("anthology") or [])
        link_map = self._samras_link_rows(anthology_rows)

        by_instance: dict[str, dict[str, Any]] = {}
        for item in discovered:
            instance_id = str(item.get("instance_id") or "").strip()
            if not instance_id:
                continue
            link_meta = link_map.get(instance_id, {})
            by_instance[instance_id] = {
                "instance_id": instance_id,
                "table_name": str(link_meta.get("table_name") or instance_id).strip(),
                "row_count": int(item.get("row_count") or 0),
                "linked": bool(link_meta),
                "link_identifier": str(link_meta.get("identifier") or ""),
                "filename": str(item.get("filename") or ""),
            }

        for instance_id, link_meta in link_map.items():
            if instance_id in by_instance:
                continue
            by_instance[instance_id] = {
                "instance_id": instance_id,
                "table_name": str(link_meta.get("table_name") or instance_id).strip(),
                "row_count": 0,
                "linked": True,
                "link_identifier": str(link_meta.get("identifier") or ""),
                "filename": "",
            }

        instances = list(by_instance.values())
        instances.sort(key=lambda item: self._samras_sort_key(str(item.get("instance_id") or "")))
        return {
            "ok": True,
            "errors": [],
            "warnings": [],
            "msn_id": msn_id,
            "instances": instances,
        }

    def samras_table_view(
        self,
        *,
        instance_id: str,
        filter_text: str = "",
        expanded_nodes: list[str] | None = None,
    ) -> dict[str, Any]:
        msn_id = self._local_msn_id()
        if not msn_id:
            return {"ok": False, "errors": ["msn_id is not configured"], "warnings": []}
        instance_token, err = self._normalize_samras_instance_id(instance_id)
        if err:
            return {"ok": False, "errors": [err], "warnings": []}
        if not hasattr(self.storage, "load_samras_instance_rows"):
            return {"ok": False, "errors": ["storage backend does not support SAMRAS instances"], "warnings": []}

        rows = list(self.storage.load_samras_instance_rows(msn_id, instance_token))  # type: ignore[attr-defined]
        rows = self._samras_rows_sorted(rows)
        graph = self._samras_graph(
            rows,
            filter_text=filter_text,
            expanded_nodes={str(item).strip() for item in (expanded_nodes or []) if str(item).strip()},
            collapsed_depth=2,
        )
        filtered_rows = [row for row in rows if self._samras_filter_match(row, filter_text)]
        return {
            "ok": True,
            "errors": [],
            "warnings": list(graph.get("warnings") or []),
            "instance": {
                "instance_id": instance_token,
                "msn_id": msn_id,
                "row_count": len(rows),
                "filtered_row_count": len(filtered_rows),
            },
            "rows": filtered_rows,
            "graph": graph,
        }

    def samras_graph_view(
        self,
        *,
        instance_id: str,
        filter_text: str = "",
        expanded_nodes: list[str] | None = None,
    ) -> dict[str, Any]:
        payload = self.samras_table_view(
            instance_id=instance_id,
            filter_text=filter_text,
            expanded_nodes=expanded_nodes,
        )
        if not bool(payload.get("ok")):
            return payload
        return {
            "ok": True,
            "errors": [],
            "warnings": list(payload.get("warnings") or []),
            "instance": dict(payload.get("instance") or {}),
            "graph": dict(payload.get("graph") or {}),
        }

    def samras_create_table(self, *, instance_id: str, table_name: str) -> dict[str, Any]:
        msn_id = self._local_msn_id()
        if not msn_id:
            return {"ok": False, "errors": ["msn_id is not configured"], "warnings": []}
        instance_token, instance_err = self._normalize_samras_instance_id(instance_id)
        if instance_err:
            return {"ok": False, "errors": [instance_err], "warnings": []}
        table_token = str(table_name or "").strip()
        if not table_token:
            return {"ok": False, "errors": ["table_name is required"], "warnings": []}

        if not hasattr(self.storage, "create_samras_instance"):
            return {"ok": False, "errors": ["storage backend does not support SAMRAS instances"], "warnings": []}
        create_result = self.storage.create_samras_instance(msn_id, instance_token)  # type: ignore[attr-defined]
        if not bool(create_result.get("ok")):
            return {
                "ok": False,
                "errors": list(create_result.get("errors") or ["failed to create SAMRAS table"]),
                "warnings": list(create_result.get("warnings") or []),
            }

        link_result = self._ensure_samras_anchor_and_link(instance_id=instance_token, table_name=table_token)
        if not bool(link_result.get("ok")):
            return {
                "ok": False,
                "errors": list(link_result.get("errors") or ["created table but failed to link in anthology"]),
                "warnings": list(link_result.get("warnings") or []),
            }

        table_view = self.samras_table_view(instance_id=instance_token)
        return {
            "ok": bool(table_view.get("ok")),
            "errors": list(table_view.get("errors") or []),
            "warnings": list(link_result.get("warnings") or []) + list(table_view.get("warnings") or []),
            "created": {
                "instance_id": instance_token,
                "table_name": table_token,
                "directive_ref": str(link_result.get("directive_ref") or ""),
                "link_identifier": str(link_result.get("link_identifier") or ""),
            },
            "table": table_view,
        }

    def samras_row_upsert(self, *, instance_id: str, address_id: str, title: str) -> dict[str, Any]:
        msn_id = self._local_msn_id()
        if not msn_id:
            return {"ok": False, "errors": ["msn_id is not configured"], "warnings": []}
        instance_token, instance_err = self._normalize_samras_instance_id(instance_id)
        if instance_err:
            return {"ok": False, "errors": [instance_err], "warnings": []}
        address_token, address_err = self._normalize_samras_address_id(address_id)
        if address_err:
            return {"ok": False, "errors": [address_err], "warnings": []}
        title_token = str(title or "").strip()
        if not title_token:
            return {"ok": False, "errors": ["title is required"], "warnings": []}
        if not hasattr(self.storage, "load_samras_instance_rows") or not hasattr(self.storage, "persist_samras_instance_rows"):
            return {"ok": False, "errors": ["storage backend does not support SAMRAS instances"], "warnings": []}

        rows = list(self.storage.load_samras_instance_rows(msn_id, instance_token))  # type: ignore[attr-defined]
        found = False
        for row in rows:
            token = str(row.get("address_id") or row.get("row_id") or "").strip()
            if token != address_token:
                continue
            row["address_id"] = address_token
            row["row_id"] = address_token
            row["msn_id"] = address_token
            row["title"] = title_token
            row["name"] = title_token
            row["_source"] = "samras"
            found = True
            break
        if not found:
            rows.append(
                {
                    "address_id": address_token,
                    "row_id": address_token,
                    "msn_id": address_token,
                    "title": title_token,
                    "name": title_token,
                    "_source": "samras",
                }
            )
        rows = self._samras_rows_sorted(rows)
        persist_result = self.storage.persist_samras_instance_rows(msn_id, instance_token, rows)  # type: ignore[attr-defined]
        if not bool(persist_result.get("ok")):
            return {
                "ok": False,
                "errors": list(persist_result.get("errors") or ["failed to persist SAMRAS row"]),
                "warnings": list(persist_result.get("warnings") or []),
            }
        table_view = self.samras_table_view(instance_id=instance_token)
        return {
            "ok": bool(table_view.get("ok")),
            "errors": list(table_view.get("errors") or []),
            "warnings": list(persist_result.get("warnings") or []) + list(table_view.get("warnings") or []),
            "upserted": {
                "instance_id": instance_token,
                "address_id": address_token,
                "title": title_token,
                "created": not found,
            },
            "table": table_view,
        }

    def samras_row_delete(self, *, instance_id: str, address_id: str) -> dict[str, Any]:
        msn_id = self._local_msn_id()
        if not msn_id:
            return {"ok": False, "errors": ["msn_id is not configured"], "warnings": []}
        instance_token, instance_err = self._normalize_samras_instance_id(instance_id)
        if instance_err:
            return {"ok": False, "errors": [instance_err], "warnings": []}
        address_token, address_err = self._normalize_samras_address_id(address_id)
        if address_err:
            return {"ok": False, "errors": [address_err], "warnings": []}
        if not hasattr(self.storage, "load_samras_instance_rows") or not hasattr(self.storage, "persist_samras_instance_rows"):
            return {"ok": False, "errors": ["storage backend does not support SAMRAS instances"], "warnings": []}

        rows = list(self.storage.load_samras_instance_rows(msn_id, instance_token))  # type: ignore[attr-defined]
        kept = [row for row in rows if str(row.get("address_id") or row.get("row_id") or "").strip() != address_token]
        if len(kept) == len(rows):
            return {"ok": False, "errors": [f"address_id not found: {address_token}"], "warnings": []}
        kept = self._samras_rows_sorted(kept)
        persist_result = self.storage.persist_samras_instance_rows(msn_id, instance_token, kept)  # type: ignore[attr-defined]
        if not bool(persist_result.get("ok")):
            return {
                "ok": False,
                "errors": list(persist_result.get("errors") or ["failed to persist SAMRAS row deletion"]),
                "warnings": list(persist_result.get("warnings") or []),
            }
        table_view = self.samras_table_view(instance_id=instance_token)
        return {
            "ok": bool(table_view.get("ok")),
            "errors": list(table_view.get("errors") or []),
            "warnings": list(persist_result.get("warnings") or []) + list(table_view.get("warnings") or []),
            "deleted": {
                "instance_id": instance_token,
                "address_id": address_token,
            },
            "table": table_view,
        }

    @staticmethod
    def _truthy_magnitude(token: str) -> bool:
        decoded = mediate_decode(
            standard_id="boolean_ref",
            reference="",
            magnitude=str(token or "").strip(),
            context={},
        )
        return bool(decoded.get("value"))

    @staticmethod
    def _decode_hex_text(token: str) -> tuple[str, str | None]:
        decoded = mediate_decode(
            standard_id="text_byte_email_format",
            reference="",
            magnitude=str(token or "").strip(),
            context={"allow_trailing_null": True},
        )
        warnings = list(decoded.get("warnings") or [])
        return str(decoded.get("value") or ""), (warnings[0] if warnings else None)

    def resolve_contact_collection(
        self,
        *,
        collection_ref: str,
    ) -> dict[str, Any]:
        source_ref = str(collection_ref or "").strip()
        if not source_ref:
            return {"ok": False, "errors": ["collection_ref is required"], "warnings": [], "status_code": 400}

        anthology_rows = list(self.storage.load_rows("anthology") or [])
        entry_row, entry_identifier = self._resolve_anthology_row(source_ref, anthology_rows)
        if entry_row is None:
            return {
                "ok": False,
                "errors": [f"collection_ref not found in anthology: {source_ref}"],
                "warnings": [],
                "status_code": 404,
            }

        warnings: list[str] = []
        resolution_chain: list[dict[str, str]] = []
        collection_row = entry_row
        collection_identifier = entry_identifier
        collection_ref_token = source_ref

        layer, value_group, _ = self._parse_datum_identifier(collection_identifier)
        if not (layer == 8 and value_group == 0):
            resolution_chain.append(
                {
                    "kind": "seed",
                    "input_ref": source_ref,
                    "resolved_identifier": entry_identifier,
                }
            )
            matched_row: dict[str, Any] | None = None
            matched_identifier = ""
            matched_ref = ""
            for pair in self._pairs_from_row(entry_row):
                pair_ref = str(pair.get("reference") or "").strip()
                if not pair_ref or pair_ref == "0":
                    continue
                candidate_row, candidate_identifier = self._resolve_anthology_row(pair_ref, anthology_rows)
                if candidate_row is None:
                    continue
                row_layer, row_value_group, _ = self._parse_datum_identifier(candidate_identifier)
                if row_layer == 8 and row_value_group == 0:
                    matched_row = candidate_row
                    matched_identifier = candidate_identifier
                    matched_ref = pair_ref
                    break
            if matched_row is None:
                return {
                    "ok": False,
                    "errors": [f"collection_ref did not resolve to 8-0-* and no nested collection found: {source_ref}"],
                    "warnings": warnings,
                    "status_code": 404,
                }
            collection_row = matched_row
            collection_identifier = matched_identifier
            collection_ref_token = matched_ref
            resolution_chain.append(
                {
                    "kind": "collection",
                    "input_ref": matched_ref,
                    "resolved_identifier": matched_identifier,
                }
            )

        contacts: list[dict[str, Any]] = []
        for pair in self._pairs_from_row(collection_row):
            contact_ref = str(pair.get("reference") or "").strip()
            if not contact_ref or contact_ref == "0":
                continue
            contact_row, contact_identifier = self._resolve_anthology_row(contact_ref, anthology_rows)
            if contact_row is None:
                warnings.append(f"unresolved contact ref {contact_ref} in {collection_identifier}")
                continue

            contact_label = str(contact_row.get("label") or contact_identifier).strip()
            display_name = contact_label.split("-", 1)[0].strip() if "-" in contact_label else contact_label
            email_local_hex = ""
            email_local_text = ""
            email_type_ref = ""
            email_type_value = ""
            for contact_pair in self._pairs_from_row(contact_row):
                pair_ref = str(contact_pair.get("reference") or "").strip()
                pair_mag = str(contact_pair.get("magnitude") or "").strip()
                if not pair_ref:
                    continue
                tail = pair_ref if _DATUM_ID_RE.fullmatch(pair_ref) else self._qualified_tail_identifier(pair_ref)
                if tail == "3-1-3" and not email_local_hex:
                    email_local_hex = pair_mag
                    email_local_text, decode_warning = self._decode_hex_text(email_local_hex)
                    if decode_warning:
                        warnings.append(f"{contact_identifier}: {decode_warning}")
                elif tail == "6-1-2" and not email_type_ref:
                    email_type_ref = pair_ref
                    email_type_value = pair_mag
            contacts.append(
                {
                    "contact_ref": contact_ref,
                    "contact_identifier": contact_identifier,
                    "contact_label": contact_label,
                    "display_name": display_name,
                    "email_local_hex": email_local_hex,
                    "email_local_text": email_local_text,
                    "email_type_ref": email_type_ref,
                    "email_type_value": email_type_value,
                }
            )

        return {
            "ok": True,
            "source": {
                "collection_ref": source_ref,
                "resolved_collection_ref": collection_ref_token,
                "resolved_collection_identifier": collection_identifier,
                "resolution_chain": resolution_chain,
            },
            "contacts": contacts,
            "summary": {"contacts_total": len(contacts)},
            "warnings": warnings,
            "errors": [],
            "status_code": 200,
        }

    def aws_emailer_preview(
        self,
        *,
        tenant_id: str,
        aws_emailer_list_ref: str,
        aws_emailer_entry_ref: str = "",
    ) -> dict[str, Any]:
        tenant_token = str(tenant_id or "").strip()
        list_ref_token = str(aws_emailer_list_ref or "").strip()
        entry_ref_hint = str(aws_emailer_entry_ref or "").strip()
        if not tenant_token:
            return {"ok": False, "errors": ["tenant_id is required"], "warnings": [], "status_code": 400}
        if not list_ref_token:
            return {"ok": False, "errors": ["aws_emailer_list_ref is required"], "warnings": [], "status_code": 400}

        anthology_rows = list(self.storage.load_rows("anthology") or [])
        list_row, list_identifier = self._resolve_anthology_row(list_ref_token, anthology_rows)
        if list_row is None:
            return {
                "ok": False,
                "errors": [f"aws_emailer_list_ref not found in anthology: {list_ref_token}"],
                "warnings": [],
                "status_code": 404,
            }

        list_label = str(list_row.get("label") or list_identifier).strip()
        list_pairs = self._pairs_from_row(list_row)
        entry_refs = [str(pair.get("reference") or "").strip() for pair in list_pairs]
        entry_refs = [token for token in entry_refs if token and token != "0"]
        warnings: list[str] = []
        if not entry_refs and entry_ref_hint:
            entry_refs = [entry_ref_hint]
            warnings.append("list row contained no entry refs; falling back to aws_emailer_entry_ref hint")
        if not entry_refs:
            return {
                "ok": False,
                "errors": [f"no entry references found under {list_identifier}"],
                "warnings": warnings,
                "status_code": 400,
            }

        entries: list[dict[str, Any]] = []
        resolution_chain: list[dict[str, str]] = []
        for entry_ref in entry_refs:
            entry_row, entry_identifier = self._resolve_anthology_row(entry_ref, anthology_rows)
            if entry_row is None:
                warnings.append(f"unresolved entry reference under {list_identifier}: {entry_ref}")
                continue

            entry_label = str(entry_row.get("label") or entry_identifier).strip()
            entry_pairs = self._pairs_from_row(entry_row)

            subscription_ref = ""
            subscription_magnitude = ""
            subscribed = False
            for pair in entry_pairs:
                pair_ref = str(pair.get("reference") or "").strip()
                pair_mag = str(pair.get("magnitude") or "").strip()
                if not pair_ref:
                    continue
                tail = pair_ref if _DATUM_ID_RE.fullmatch(pair_ref) else self._qualified_tail_identifier(pair_ref)
                if tail == "2-1-45":
                    subscription_ref = pair_ref
                    subscription_magnitude = pair_mag
                    subscribed = self._truthy_magnitude(pair_mag)
                    break
            if not subscription_ref:
                warnings.append(f"{entry_identifier}: missing bool subscription pair (expected ref 2-1-45)")

            contact_collection_ref = ""
            contact_collection_identifier = ""
            contact_collection_row: dict[str, Any] | None = None
            for pair in entry_pairs:
                pair_ref = str(pair.get("reference") or "").strip()
                if not pair_ref:
                    continue
                candidate_row, candidate_identifier = self._resolve_anthology_row(pair_ref, anthology_rows)
                if candidate_row is None:
                    continue
                layer, value_group, _ = self._parse_datum_identifier(candidate_identifier)
                if layer == 8 and value_group == 0:
                    contact_collection_ref = pair_ref
                    contact_collection_identifier = candidate_identifier
                    contact_collection_row = candidate_row
                    break

            contacts: list[dict[str, Any]] = []
            if contact_collection_row is None:
                warnings.append(f"{entry_identifier}: missing contact collection ref (expected 8-0-*)")
            else:
                for pair in self._pairs_from_row(contact_collection_row):
                    contact_ref = str(pair.get("reference") or "").strip()
                    if not contact_ref or contact_ref == "0":
                        continue
                    contact_row, contact_identifier = self._resolve_anthology_row(contact_ref, anthology_rows)
                    if contact_row is None:
                        warnings.append(
                            f"{entry_identifier}: unresolved contact ref {contact_ref} in {contact_collection_identifier}"
                        )
                        continue
                    contact_label = str(contact_row.get("label") or contact_identifier).strip()
                    display_name = contact_label.split("-", 1)[0].strip() if "-" in contact_label else contact_label
                    email_local_hex = ""
                    email_local_text = ""
                    email_type_ref = ""
                    email_type_value = ""
                    for contact_pair in self._pairs_from_row(contact_row):
                        pair_ref = str(contact_pair.get("reference") or "").strip()
                        pair_mag = str(contact_pair.get("magnitude") or "").strip()
                        if not pair_ref:
                            continue
                        tail = pair_ref if _DATUM_ID_RE.fullmatch(pair_ref) else self._qualified_tail_identifier(pair_ref)
                        if tail == "3-1-3" and not email_local_hex:
                            email_local_hex = pair_mag
                            email_local_text, decode_warning = self._decode_hex_text(email_local_hex)
                            if decode_warning:
                                warnings.append(f"{contact_identifier}: {decode_warning}")
                        elif tail == "6-1-2" and not email_type_ref:
                            email_type_ref = pair_ref
                            email_type_value = pair_mag
                    contacts.append(
                        {
                            "contact_identifier": contact_identifier,
                            "contact_label": contact_label,
                            "display_name": display_name,
                            "email_local_hex": email_local_hex,
                            "email_local_text": email_local_text,
                            "email_type_ref": email_type_ref,
                            "email_type_value": email_type_value,
                        }
                    )

            resolution_chain.append(
                {
                    "list_identifier": list_identifier,
                    "entry_reference": entry_ref,
                    "resolved_entry_identifier": entry_identifier,
                    "contact_collection_identifier": contact_collection_identifier,
                }
            )
            entries.append(
                {
                    "entry_identifier": entry_identifier,
                    "entry_label": entry_label,
                    "subscribed": subscribed,
                    "subscription_ref": subscription_ref,
                    "subscription_magnitude": subscription_magnitude,
                    "contact_collection_ref": contact_collection_identifier or contact_collection_ref,
                    "contacts": contacts,
                }
            )

        if not entries:
            return {
                "ok": False,
                "errors": [f"no resolvable entry rows found under {list_identifier}"],
                "warnings": warnings,
                "status_code": 404,
            }

        entries_subscribed = sum(1 for item in entries if bool(item.get("subscribed")))
        contacts_total = sum(len(item.get("contacts") or []) for item in entries)
        return {
            "ok": True,
            "tenant_id": tenant_token,
            "source": {
                "aws_emailer_list_ref": list_ref_token,
                "aws_emailer_entry_ref": entry_ref_hint,
                "resolved_list_identifier": list_identifier,
                "resolved_list_label": list_label,
                "resolution_chain": resolution_chain,
            },
            "entries": entries,
            "summary": {
                "entries_total": len(entries),
                "entries_subscribed": entries_subscribed,
                "contacts_total": contacts_total,
            },
            "warnings": warnings,
        }

    def append_anthology_datum(
        self,
        *,
        layer: int,
        value_group: int,
        reference: str,
        magnitude: str,
        label: str = "",
        pairs: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        if layer < 0:
            return {"ok": False, "errors": ["layer must be >= 0"], "warnings": []}
        if value_group < 0:
            return {"ok": False, "errors": ["value_group must be >= 0"], "warnings": []}

        raw_pairs: list[dict[str, str]] = []
        if isinstance(pairs, list) and pairs:
            for item in pairs:
                if not isinstance(item, dict):
                    continue
                raw_pairs.append(
                    {
                        "reference": str(item.get("reference") or "").strip(),
                        "magnitude": str(item.get("magnitude") or "").strip(),
                    }
                )
        else:
            raw_pairs.append(
                {
                    "reference": str(reference or "").strip(),
                    "magnitude": str(magnitude or "").strip(),
                }
            )

        label_token = str(label or "").strip()

        normalized_pairs, errors = self._normalize_pairs_for_value_group(value_group, raw_pairs)

        if not normalized_pairs:
            if value_group == 0:
                errors.append("at least one valid reference is required for value_group=0")
            else:
                errors.append("at least one valid reference/magnitude pair is required")
        required_pairs = self._required_pair_count(value_group)
        if len(normalized_pairs) < required_pairs:
            errors.append(
                f"value_group={value_group} requires at least {required_pairs} reference/magnitude pair(s)"
            )
        if errors:
            return {"ok": False, "errors": errors, "warnings": []}

        rows = list(self.storage.load_rows("anthology") or [])
        existing_ids: set[str] = set()
        max_iteration = 0
        warnings: list[str] = []

        for row in rows:
            datum_id = str(row.get("identifier") or row.get("row_id") or "").strip()
            if not datum_id:
                continue
            existing_ids.add(datum_id)
            row_layer, row_value_group, row_iteration = self._parse_datum_identifier(datum_id)
            if row_layer == layer and row_value_group == value_group and isinstance(row_iteration, int):
                max_iteration = max(max_iteration, row_iteration)

        next_iteration = max_iteration + 1
        next_identifier = f"{layer}-{value_group}-{next_iteration}"
        while next_identifier in existing_ids:
            next_iteration += 1
            next_identifier = f"{layer}-{value_group}-{next_iteration}"

        for index, pair in enumerate(normalized_pairs):
            reference_token = str(pair.get("reference") or "").strip()
            ref_layer, _, _ = self._parse_datum_identifier(reference_token)
            if isinstance(ref_layer, int) and ref_layer >= layer:
                warnings.append(f"pair {index + 1}: reference layer is not lower than datum layer (check Rule A intent).")

        first_reference, first_magnitude = self._first_pair(normalized_pairs)
        new_row = {
            "row_id": next_identifier,
            "identifier": next_identifier,
            "reference": first_reference,
            "magnitude": first_magnitude,
            "pairs": normalized_pairs,
            "label": label_token,
            "_source": "anthology",
        }
        rows.append(new_row)

        result = self.storage.persist_rows("anthology", rows)
        if not bool(result.get("ok")):
            return {"ok": False, "errors": list(result.get("errors") or ["failed to persist anthology"]), "warnings": warnings}

        sync_result = self._sync_vg0_magnitude_from_anthology(rows)
        if not bool(sync_result.get("ok")):
            return {
                "ok": False,
                "errors": ["anthology updated, but failed to recompute VG0 selection magnitudes"] + list(sync_result.get("errors") or []),
                "warnings": warnings + list(result.get("warnings") or []) + list(sync_result.get("warnings") or []),
            }
        identifier_map = (
            sync_result.get("identifier_map")
            if isinstance(sync_result.get("identifier_map"), dict)
            else {}
        )
        final_identifier = str(identifier_map.get(next_identifier) or next_identifier).strip()
        _, _, final_iteration = self._parse_datum_identifier(final_identifier)
        if not isinstance(final_iteration, int) or final_iteration < 1:
            final_iteration = next_iteration

        self._reload()
        self._refresh_panes_for_icon_change()
        self._persist_state()

        return {
            "ok": True,
            "errors": [],
            "warnings": warnings + list(result.get("warnings") or []) + list(sync_result.get("warnings") or []),
            "created": {
                "row_id": final_identifier,
                "identifier": final_identifier,
                "layer": layer,
                "value_group": value_group,
                "iteration": final_iteration,
                "reference": first_reference,
                "magnitude": first_magnitude,
                "pairs": normalized_pairs,
                "pair_count": len(normalized_pairs),
                "label": label_token,
            },
            "created_rows": [
                {
                    "row_id": final_identifier,
                    "identifier": final_identifier,
                    "layer": layer,
                    "value_group": value_group,
                    "iteration": final_iteration,
                    "reference": first_reference,
                    "magnitude": first_magnitude,
                    "pairs": normalized_pairs,
                    "pair_count": len(normalized_pairs),
                    "label": label_token,
                }
            ],
            "created_count": 1,
        }

    def delete_anthology_datum(self, *, row_id: str) -> dict[str, Any]:
        row_token = str(row_id or "").strip()
        if not row_token:
            return {"ok": False, "errors": ["row_id is required"], "warnings": []}

        rows = list(self.storage.load_rows("anthology") or [])
        kept_rows: list[dict[str, Any]] = []
        removed_row: dict[str, Any] | None = None

        for row in rows:
            candidate_row_id = str(row.get("row_id") or "").strip()
            candidate_identifier = str(row.get("identifier") or "").strip()
            if removed_row is None and row_token in {candidate_row_id, candidate_identifier}:
                removed_row = row
                continue
            kept_rows.append(row)

        if removed_row is None:
            return {"ok": False, "errors": [f"Unknown anthology row_id: {row_token}"], "warnings": []}

        row_result = self.storage.persist_rows("anthology", kept_rows)
        if not bool(row_result.get("ok")):
            return {"ok": False, "errors": list(row_result.get("errors") or ["failed to persist anthology"]), "warnings": []}

        warnings: list[str] = list(row_result.get("warnings") or [])
        sync_result = self._sync_vg0_magnitude_from_anthology(kept_rows)
        if not bool(sync_result.get("ok")):
            return {
                "ok": False,
                "errors": ["anthology updated, but failed to recompute VG0 selection magnitudes"] + list(sync_result.get("errors") or []),
                "warnings": warnings + list(sync_result.get("warnings") or []),
            }
        warnings.extend(list(sync_result.get("warnings") or []))
        deleted_identifier = str(removed_row.get("identifier") or removed_row.get("row_id") or "").strip()
        deleted_label = str(removed_row.get("label") or deleted_identifier).strip()
        deleted_pairs = self._pairs_from_row(removed_row)
        deleted_reference, deleted_magnitude = self._first_pair(deleted_pairs)

        if deleted_identifier and deleted_identifier in self._datum_icons_map:
            merged_icons = dict(self._datum_icons_map)
            merged_icons.pop(deleted_identifier, None)
            icon_result = self.storage.persist_datum_icons_map(merged_icons)
            if bool(icon_result.get("ok")):
                warnings.extend(list(icon_result.get("warnings") or []))
                self._datum_icons_map = merged_icons
            else:
                warnings.append("deleted row but failed to prune icon mapping")

        self._reload()
        self._refresh_panes_for_icon_change()
        self._persist_state()

        return {
            "ok": True,
            "errors": [],
            "warnings": warnings,
            "deleted": {
                "row_id": str(removed_row.get("row_id") or deleted_identifier).strip(),
                "identifier": deleted_identifier,
                "label": deleted_label,
                "reference": deleted_reference,
                "magnitude": deleted_magnitude,
                "pairs": deleted_pairs,
                "pair_count": len(deleted_pairs),
            },
        }

    def update_anthology_label(self, *, row_id: str, label: str) -> dict[str, Any]:
        return self.update_anthology_profile(row_id=row_id, label=label, icon_relpath=None)

    def anthology_profile(self, *, row_id: str) -> dict[str, Any]:
        row_token = str(row_id or "").strip()
        if not row_token:
            return {"ok": False, "errors": ["row_id is required"], "warnings": []}

        rows = list(self.storage.load_rows("anthology") or [])
        match: dict[str, Any] | None = None
        for row in rows:
            candidate_row_id = str(row.get("row_id") or "").strip()
            candidate_identifier = str(row.get("identifier") or "").strip()
            if row_token in {candidate_row_id, candidate_identifier}:
                match = row
                break

        if match is None:
            return {"ok": False, "errors": [f"Unknown anthology row_id: {row_token}"], "warnings": []}

        identifier = str(match.get("identifier") or match.get("row_id") or "").strip()
        label_text = str(match.get("label") or identifier).strip()
        pairs = self._pairs_from_row(match)
        reference, magnitude = self._first_pair(pairs)

        datum = {
            "row_id": str(match.get("row_id") or identifier).strip(),
            "identifier": identifier,
            "label": label_text,
            "reference": reference,
            "magnitude": magnitude,
            "pairs": pairs,
            "pair_count": len(pairs),
            **self._icon_meta(identifier, label_text),
        }

        chain = resolve_chain(self._graph, identifier)
        for item in chain:
            item_identifier = str(item.get("identifier") or "").strip()
            item_label = str(item.get("label") or item_identifier)
            item.update(self._icon_meta(item_identifier, item_label))

        return {
            "ok": True,
            "errors": [],
            "warnings": [],
            "datum": datum,
            "abstraction_path": chain,
        }

    def update_anthology_profile(
        self,
        *,
        row_id: str,
        label: str,
        magnitude: str | None = None,
        pairs: list[dict[str, str]] | None = None,
        icon_relpath: str | None = None,
    ) -> dict[str, Any]:
        row_token = str(row_id or "").strip()
        if not row_token:
            return {"ok": False, "errors": ["row_id is required"], "warnings": []}

        next_label = str(label or "").strip()
        rows = list(self.storage.load_rows("anthology") or [])
        match: dict[str, Any] | None = None

        for row in rows:
            candidate_row_id = str(row.get("row_id") or "").strip()
            candidate_identifier = str(row.get("identifier") or "").strip()
            if row_token in {candidate_row_id, candidate_identifier}:
                match = row
                break

        if match is None:
            return {"ok": False, "errors": [f"Unknown anthology row_id: {row_token}"], "warnings": []}

        datum_id = str(match.get("identifier") or match.get("row_id") or "").strip()
        match["label"] = next_label
        existing_pairs = self._pairs_from_row(match)

        next_pairs = existing_pairs
        _, row_value_group, _ = self._parse_datum_identifier(datum_id)
        required_pairs = self._required_pair_count(row_value_group if isinstance(row_value_group, int) else 0)
        if isinstance(pairs, list):
            safe_pairs: list[dict[str, str]] = []
            validation_errors: list[str] = []
            for index, item in enumerate(pairs):
                if not isinstance(item, dict):
                    validation_errors.append(f"pair {index + 1}: must be an object")
                    continue
                safe_pairs.append(
                    {
                        "reference": str(item.get("reference") or "").strip(),
                        "magnitude": str(item.get("magnitude") or "").strip(),
                    }
                )

            validated_pairs, pair_errors = self._normalize_pairs_for_value_group(
                row_value_group if isinstance(row_value_group, int) else 0,
                safe_pairs,
            )
            validation_errors.extend(pair_errors)

            if not validated_pairs:
                if row_value_group == 0:
                    validation_errors.append("at least one valid reference is required for value_group=0")
                else:
                    validation_errors.append("at least one valid reference/magnitude pair is required")
            if len(validated_pairs) < required_pairs:
                validation_errors.append(
                    f"value_group={row_value_group if isinstance(row_value_group, int) else 0} requires at least "
                    f"{required_pairs} reference/magnitude pair(s)"
                )
            if validation_errors:
                return {"ok": False, "errors": validation_errors, "warnings": []}
            next_pairs = validated_pairs
        elif magnitude is not None:
            next_pairs = list(existing_pairs)
            if next_pairs:
                next_pairs[0] = {
                    "reference": str(next_pairs[0].get("reference") or "").strip(),
                    "magnitude": str(magnitude or "").strip(),
                }
            else:
                next_pairs = [
                    {
                        "reference": str(match.get("reference") or "").strip(),
                        "magnitude": str(magnitude or "").strip(),
                    }
                ]

        first_reference, first_magnitude = self._first_pair(next_pairs)
        match["pairs"] = next_pairs
        match["reference"] = first_reference
        match["magnitude"] = first_magnitude

        row_result = self.storage.persist_rows("anthology", rows)
        if not bool(row_result.get("ok")):
            return {"ok": False, "errors": list(row_result.get("errors") or ["failed to persist anthology"]), "warnings": []}

        warnings: list[str] = list(row_result.get("warnings") or [])
        sync_result = self._sync_vg0_magnitude_from_anthology(rows)
        if not bool(sync_result.get("ok")):
            return {
                "ok": False,
                "errors": ["anthology updated, but failed to recompute VG0 selection magnitudes"] + list(sync_result.get("errors") or []),
                "warnings": warnings + list(sync_result.get("warnings") or []),
            }
        warnings.extend(list(sync_result.get("warnings") or []))
        identifier_map = (
            sync_result.get("identifier_map")
            if isinstance(sync_result.get("identifier_map"), dict)
            else {}
        )
        final_datum_id = str(identifier_map.get(datum_id) or datum_id).strip()
        final_row_id = str(identifier_map.get(str(match.get("row_id") or datum_id).strip()) or final_datum_id).strip()

        if icon_relpath is not None:
            canonical_icon = self._canonical_icon_relpath(icon_relpath)
            if canonical_icon and not self._icon_exists(canonical_icon):
                return {"ok": False, "errors": [f"Invalid icon_relpath: {canonical_icon}"], "warnings": warnings}

            merged_icons = dict(self._datum_icons_map)
            if canonical_icon:
                merged_icons[final_datum_id] = canonical_icon
            else:
                merged_icons.pop(final_datum_id, None)

            icon_result = self.storage.persist_datum_icons_map(merged_icons)
            if not bool(icon_result.get("ok")):
                return {"ok": False, "errors": list(icon_result.get("errors") or ["failed to persist icon mapping"]), "warnings": warnings}
            warnings.extend(list(icon_result.get("warnings") or []))
            self._datum_icons_map = merged_icons

        self._reload()
        self._refresh_panes_for_icon_change()
        self._persist_state()

        updated_icon_meta = self._icon_meta(final_datum_id, next_label)
        return {
            "ok": True,
            "errors": [],
            "warnings": warnings,
            "updated": {
                "row_id": final_row_id,
                "identifier": final_datum_id,
                "label": next_label,
                "reference": first_reference,
                "magnitude": first_magnitude,
                "pairs": next_pairs,
                "pair_count": len(next_pairs),
                **updated_icon_meta,
            },
        }

    def _node_for_subject(self, subject: str):
        token = str(subject or "").strip()
        if not token:
            return None
        direct = self._graph.get_node(token)
        if direct is not None:
            return direct
        matches = self._graph.find_by_identifier(token)
        if not matches:
            return None
        return self._graph.get_node(matches[0])

    def _table_for_subject(self, subject: str) -> dict[str, Any] | None:
        token = str(subject or "").strip()
        if not token:
            return None

        direct = self._table(token)
        if direct is not None:
            return direct

        for table in self._tables.values():
            archetype_id = str(table.get("archetype_id") or "").strip()
            archetype_identifier = str(table.get("archetype_identifier") or "").strip()
            if token in {archetype_id, archetype_identifier}:
                return table

        return None

    def _nav_payload(self, source: str, args: dict[str, Any]) -> dict[str, Any]:
        token = normalize_source(source, "auto")
        payload: dict[str, Any] = {"source": token}

        if token == "anthology":
            nodes = [self._graph.get_node(node_id) for node_id in self._graph.find_by_source("anthology")]
            nodes = [node for node in nodes if node is not None]
            layers: dict[int, int] = defaultdict(int)
            recent: list[dict[str, Any]] = []
            for node in nodes[:50]:
                if node.layer is not None:
                    layers[node.layer] += 1
                recent.append(
                    self._enrich_datum_entry(
                        node.identifier,
                        node.label,
                        {"node_id": node.node_id, "identifier": node.identifier},
                    )
                )

            payload["table_archetypes"] = [
                self._enrich_datum_entry(
                    str(item.get("archetype_identifier") or ""),
                    str(item.get("title") or item.get("table_id") or ""),
                    {
                        "table_id": item.get("table_id"),
                        "title": item.get("title"),
                        "layer": item.get("layer"),
                        "archetype_id": item.get("archetype_id"),
                        "archetype_identifier": item.get("archetype_identifier"),
                    },
                )
                for item in self.list_tables()
                if str(item.get("archetype_id") or "")
            ]
            payload["recent_datums"] = recent
            payload["layer_filters"] = [{"layer": layer, "count": count} for layer, count in sorted(layers.items())]
            return payload

        if token == "samras":
            page = int(args.get("page") or 1)
            page_size = int(args.get("page_size") or 50)
            if page < 1:
                page = 1
            if page_size < 1:
                page_size = 50

            nodes = [self._graph.get_node(node_id) for node_id in self._graph.find_by_source("samras")]
            nodes = [node for node in nodes if node is not None]

            start = (page - 1) * page_size
            end = start + page_size
            payload["page"] = page
            payload["page_size"] = page_size
            payload["total"] = len(nodes)
            payload["nodes"] = [
                self._enrich_datum_entry(
                    node.identifier,
                    str(node.raw.get("name") or node.label),
                    {
                        "msn_id": node.raw.get("msn_id", node.identifier),
                        "name": node.raw.get("name", node.label),
                        "node_id": node.node_id,
                        "identifier": node.identifier,
                    },
                )
                for node in nodes[start:end]
            ]
            return payload

        payload["sources"] = {
            "anthology": len(self._graph.find_by_source("anthology")),
            "samras": len(self._graph.find_by_source("samras")),
        }
        payload["tables"] = self.list_tables()
        return payload

    def _refresh_panes_for_icon_change(self) -> None:
        self._state.left_pane = pane("navigation", self._nav_payload(self._state.focus_source, {}))

        right_kind = str((self._state.right_pane or {}).get("kind") or "")
        subject = str(self._state.focus_subject or "").strip()
        if right_kind == "datum_summary" and subject:
            node = self._node_for_subject(subject)
            if node is not None:
                datum = summarize_node(node)
                datum.update(self._icon_meta(node.identifier, node.label))
                self._state.right_pane = pane("datum_summary", {"datum": datum})
        elif right_kind == "abstraction_path" and subject:
            chain = resolve_chain(self._graph, subject)
            for item in chain:
                datum_id = str(item.get("identifier") or "")
                item.update(self._icon_meta(datum_id, str(item.get("label") or datum_id)))
            self._state.right_pane = pane("abstraction_path", {"subject": subject, "chain": chain})
        elif right_kind == "table_instances":
            table_id = str(((self._state.right_pane or {}).get("payload") or {}).get("table", {}).get("table_id") or "")
            if table_id:
                table = self._table(table_id)
                if table is not None:
                    self._state.right_pane = pane(
                        "table_instances",
                        {
                            "table": {
                                "table_id": table_id,
                                "title": table.get("title"),
                                "layer": table.get("layer"),
                                "archetype_id": table.get("archetype_id"),
                                "archetype_identifier": table.get("archetype_identifier"),
                            },
                            "instances": self.list_instances(table_id),
                        },
                    )

    def _merge_aitas_context(self, updates: dict[str, Any] | None = None) -> None:
        current = normalize_aitas_context(self._state.aitas_context if isinstance(self._state.aitas_context, dict) else {})
        for key, value in dict(updates or {}).items():
            normalized_key = "spatial" if key == "spacial" else key
            if normalized_key not in current:
                continue
            token = str(value or "").strip()
            current[normalized_key] = token
            if normalized_key == "spatial":
                current["spacial"] = token
        self._state.aitas_context = current

    def _state_response(self, errors: list[str] | None = None, warnings: list[str] | None = None) -> dict[str, Any]:
        staged_list = list((self._state.staged_edits or {}).values())
        merged_warnings = list(self._startup_warnings)
        if warnings:
            merged_warnings.extend(list(warnings))

        payload = response_payload(
            state=self._state.to_dict(),
            left_pane_vm=dict(self._state.left_pane),
            right_pane_vm=dict(self._state.right_pane),
            errors=list(errors or []),
            warnings=merged_warnings,
            staged_edits=staged_list,
        )
        payload["staged_presentation_edits"] = {
            "datum_icons": dict(self._staged_presentation_icons)
        }
        payload["datum_icons_map"] = dict(self._datum_icons_map)
        payload["daemon_ports"] = self.daemon_port_catalog()
        payload["model_meta"] = self.model_meta()
        return payload

    def get_state_snapshot(self) -> dict[str, Any]:
        return self._state_response()

    def apply_directive(self, payload: dict[str, Any] | str) -> dict[str, Any]:
        parsed = parse_directive(payload)
        errors = list(parsed.errors)
        warnings = list(parsed.warnings)

        if errors:
            return self._state_response(errors=errors, warnings=warnings)

        action = parsed.action
        subject = parsed.subject
        method = parsed.method
        args = parsed.args
        aitas_updates = {
            key: args.get(key)
            for key in ("attention", "intention", "temporal", "archetype", "spatial", "spacial")
            if key in args
        }

        if action == "nav":
            source = normalize_source(subject or args.get("source") or self._state.focus_source, self._default_focus_source())
            self._state.focus_source = source
            self._state.focus_subject = ""
            self._state.left_pane = pane("navigation", self._nav_payload(source, args))
            self._state.right_pane = empty_pane("investigation")
            self._state.aitas_phase = "navigate"
            aitas_updates.setdefault("attention", source)
            aitas_updates.setdefault("intention", "nav")
            self._merge_aitas_context(aitas_updates)

        elif action == "inv":
            self._state.focus_subject = subject
            method_token = str(method or "summary").strip().lower() or "summary"

            node = self._node_for_subject(subject)
            if method_token == "summary":
                if node is None:
                    errors.append(f"Unknown datum subject: {subject}")
                else:
                    datum = summarize_node(node)
                    datum.update(self._icon_meta(node.identifier, node.label))
                    self._state.right_pane = pane("datum_summary", {"datum": datum})
                    self._state.aitas_phase = "focus"

            elif method_token == "abstraction_path":
                if node is None:
                    errors.append(f"Unknown datum subject: {subject}")
                else:
                    chain = resolve_chain(self._graph, node.node_id)
                    for item in chain:
                        datum_id = str(item.get("identifier") or "")
                        item.update(self._icon_meta(datum_id, str(item.get("label") or datum_id)))
                    self._state.right_pane = pane(
                        "abstraction_path",
                        {
                            "subject": subject,
                            "chain": chain,
                        },
                    )
                    self._state.aitas_phase = "investigate"

            elif method_token == "instances":
                table = self._table_for_subject(subject)
                if table is None:
                    errors.append(f"Unknown table/archetype subject: {subject}")
                else:
                    table_id = str(table.get("table_id") or "")
                    self._state.selection["table_id"] = table_id
                    self._state.right_pane = pane(
                        "table_instances",
                        {
                            "table": {
                                "table_id": table_id,
                                "title": table.get("title"),
                                "layer": table.get("layer"),
                                "archetype_id": table.get("archetype_id"),
                                "archetype_identifier": table.get("archetype_identifier"),
                            },
                            "instances": self.list_instances(table_id),
                        },
                    )
                    self._state.aitas_phase = "investigate"

            else:
                errors.append(f"Unsupported inv method: {method_token}")
            aitas_updates.setdefault("attention", subject)
            aitas_updates.setdefault("intention", f"inv:{method_token}")
            if node is not None:
                aitas_updates.setdefault("archetype", node.identifier)
            self._merge_aitas_context(aitas_updates)

        elif action == "med":
            method_token = str(method or "").strip().lower()
            if method_token.startswith("mode="):
                mode_token = method_token.split("=", 1)[1].strip().lower()
            else:
                mode_token = str(args.get("mode") or "").strip().lower()

            if mode_token:
                if mode_token not in {"general", "inspect", "raw", "inferred"}:
                    errors.append("mode must be one of: general, inspect, raw, inferred")
                else:
                    self._state.mode = mode_token

            if method_token.startswith("lens="):
                lens_id = method_token.split("=", 1)[1].strip().lower()
            else:
                lens_id = str(args.get("lens") or "").strip().lower()
            if lens_id:
                self._state.lens_context["default"] = lens_id
            if method_token in {"attention", "intention", "temporal", "archetype", "spatial", "spacial"}:
                value = str(args.get("value") or subject or "").strip()
                if value:
                    aitas_updates[method_token] = value
            aitas_updates.setdefault("intention", "med")
            self._state.aitas_phase = "mediate"
            self._merge_aitas_context(aitas_updates)

        elif action == "man":
            method_token = str(method or "").strip().lower()
            if subject == "datum_icon" and method_token == "set":
                datum_id = str(args.get("datum_id") or "").strip()
                icon_relpath = self._canonical_icon_relpath(args.get("icon_relpath") or "")

                if not self._valid_datum_id(datum_id):
                    errors.append("datum_id must be an existing datum id or a valid id token (L-V-I).")
                elif not self._icon_exists(icon_relpath):
                    errors.append("icon_relpath must reference an existing .svg under assets/icons.")
                else:
                    self._staged_presentation_icons[datum_id] = icon_relpath
                    self._refresh_panes_for_icon_change()

            elif method_token in {"edit_cell", "stage_edit"}:
                result = self.stage_edit(
                    row_id=str(args.get("row_id") or ""),
                    field_id=str(args.get("field_id") or ""),
                    display_value=str(args.get("new_value") or args.get("display_value") or ""),
                    table_id=str(args.get("table_id") or subject or "") or None,
                    instance_id=str(args.get("instance_id") or "") or None,
                )
                errors.extend(list(result.get("errors") or []))
                warnings.extend(list(result.get("warnings") or []))
            elif method_token == "commit":
                result = self.commit(
                    scope=str(args.get("scope") or "all"),
                    table_id=str(args.get("table_id") or subject or "") or None,
                    row_id=str(args.get("row_id") or "") or None,
                )
                errors.extend(list(result.get("errors") or []))
                warnings.extend(list(result.get("warnings") or []))
            elif method_token in {"reset", "reset_staging"}:
                result = self.reset_staging(
                    scope=str(args.get("scope") or "all"),
                    table_id=str(args.get("table_id") or subject or "") or None,
                    row_id=str(args.get("row_id") or "") or None,
                )
                errors.extend(list(result.get("errors") or []))
                warnings.extend(list(result.get("warnings") or []))
            else:
                errors.append(f"Unsupported man method: {method_token}")
            aitas_updates.setdefault("intention", f"man:{method_token}" if method_token else "man")
            self._merge_aitas_context(aitas_updates)

        self._state.validation_errors = list(errors)
        self._sync_state_staging()
        self._persist_state()
        return self._state_response(errors=errors, warnings=warnings)

    def stage_edit(
        self,
        row_id: str,
        field_id: str,
        display_value: str,
        table_id: str | None = None,
        instance_id: str | None = None,
    ) -> dict[str, Any]:
        table_key = str(table_id or self._fallback_table_id()).strip()
        row_key = str(row_id or "").strip()
        field_key = str(field_id or "").strip()

        if not table_key:
            return {"ok": False, "errors": ["No table selected."], "warnings": []}
        if not row_key or not field_key:
            return {"ok": False, "errors": ["row_id and field_id are required."], "warnings": []}

        rows = self._rows_for_instance(table_key, instance_id)
        row_match = None
        for row in rows:
            if str(row.get("row_id") or "").strip() == row_key:
                row_match = row
                break

        if row_match is None:
            return {"ok": False, "errors": [f"Unknown row_id: {row_key}"], "warnings": []}

        columns = set(self._columns(rows))
        if field_key not in columns:
            return {"ok": False, "errors": [f"Unknown field_id for table: {field_key}"], "warnings": []}

        lens = get_lens(field_key, lens_context=self._state.lens_context, config=self.config)
        validation = lens.validate(str(display_value or ""))
        if not validation.ok:
            return {"ok": False, "errors": list(validation.errors), "warnings": list(validation.warnings)}

        warnings = list(validation.warnings)
        node_id = str(row_match.get("_node_id") or "")
        node = self._graph.get_node(node_id)
        if node is not None:
            chain = resolve_chain(self._graph, node.node_id)
            constraint = compile_constraint(node, chain)
            warnings.extend(list(constraint.get("warnings") or []))
            if constraint.get("errors"):
                return {
                    "ok": False,
                    "errors": list(constraint.get("errors") or []),
                    "warnings": warnings,
                }

        self._staged[(table_key, row_key, field_key)] = str(display_value or "")
        self._state.selection = {
            "table_id": table_key,
            "row_id": row_key,
            "field_id": field_key,
            "instance_id": str(instance_id or ""),
        }
        self._sync_state_staging()
        self._persist_state()
        return {"ok": True, "errors": [], "warnings": warnings}

    def revert_edit(self, table_id: str, row_id: str, field_id: str) -> dict[str, Any]:
        key = (str(table_id or "").strip(), str(row_id or "").strip(), str(field_id or "").strip())
        if not all(key):
            return {"ok": False, "errors": ["table_id, row_id, and field_id are required."], "warnings": []}

        if key not in self._staged:
            return {"ok": True, "errors": [], "warnings": ["No staged edit found for requested cell."]}

        self._staged.pop(key, None)
        self._sync_state_staging()
        self._persist_state()
        return {"ok": True, "errors": [], "warnings": []}

    def reset_staging(self, scope: str = "all", table_id: str | None = None, row_id: str | None = None) -> dict[str, Any]:
        scope_token = str(scope or "all").strip().lower()
        table_key = str(table_id or self._fallback_table_id()).strip()
        row_key = str(row_id or "").strip()

        if scope_token not in {"all", "table", "row"}:
            return {"ok": False, "errors": ["scope must be one of: all, table, row"], "warnings": []}

        warnings: list[str] = []

        if scope_token == "all":
            self._staged.clear()
            self._staged_presentation_icons.clear()
        elif scope_token == "table":
            if not table_key:
                return {"ok": False, "errors": ["No table selected for table-scope reset."], "warnings": []}
            for key in [k for k in self._staged if k[0] == table_key]:
                self._staged.pop(key, None)
            warnings.append("presentation icon staging is global and was not reset by table scope")
        else:
            if not table_key or not row_key:
                return {"ok": False, "errors": ["table_id and row_id are required for row scope reset."], "warnings": []}
            for key in [k for k in self._staged if k[0] == table_key and k[1] == row_key]:
                self._staged.pop(key, None)
            warnings.append("presentation icon staging is global and was not reset by row scope")

        self._sync_state_staging()
        self._persist_state()
        return {"ok": True, "errors": [], "warnings": warnings}

    def commit(self, scope: str = "all", table_id: str | None = None, row_id: str | None = None) -> dict[str, Any]:
        scope_token = str(scope or "all").strip().lower()
        table_key = str(table_id or self._fallback_table_id()).strip()
        row_key = str(row_id or "").strip()

        if scope_token not in {"all", "table", "row"}:
            return {"ok": False, "errors": ["scope must be one of: all, table, row"], "warnings": []}

        pending_data: dict[tuple[str, str, str], str] = {}
        for key, value in self._staged.items():
            key_table, key_row, _ = key
            include = False
            if scope_token == "all":
                include = True
            elif scope_token == "table":
                include = bool(table_key and key_table == table_key)
            elif scope_token == "row":
                include = bool(table_key and row_key and key_table == table_key and key_row == row_key)
            if include:
                pending_data[key] = value

        pending_icons = dict(self._staged_presentation_icons)

        if not pending_data and not pending_icons:
            return {"ok": True, "errors": [], "warnings": ["no staged edits"]}

        validation_errors: list[str] = []
        validation_warnings: list[str] = []

        for (table_token, row_token, field_token), display_value in pending_data.items():
            lens = get_lens(field_token, lens_context=self._state.lens_context, config=self.config)
            validation = lens.validate(display_value)
            if not validation.ok:
                for err in validation.errors:
                    validation_errors.append(f"{table_token}/{row_token}/{field_token}: {err}")
            validation_warnings.extend(list(validation.warnings))

        canonical_pending_icons: dict[str, str] = {}
        for datum_id, icon_rel in pending_icons.items():
            canonical_icon_rel = self._canonical_icon_relpath(icon_rel)
            canonical_pending_icons[datum_id] = canonical_icon_rel
            if not self._valid_datum_id(datum_id):
                validation_errors.append(f"Invalid datum_id for icon assignment: {datum_id}")
            if not self._icon_exists(canonical_icon_rel):
                validation_errors.append(f"Invalid icon_relpath for datum {datum_id}: {canonical_icon_rel}")

        if validation_errors:
            return {"ok": False, "errors": validation_errors, "warnings": validation_warnings}

        errors: list[str] = []
        warnings = list(validation_warnings)

        # Persist core table edits.
        if pending_data:
            by_table: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
            for key in pending_data.keys():
                by_table[key[0]].append(key)

            known_storage_tables = {str(item).strip().lower() for item in self.storage.known_tables()}
            for target_table, edit_keys in by_table.items():
                table = self._table(target_table)
                if table is None:
                    errors.append(f"Unknown table during commit: {target_table}")
                    continue

                normalized_target = str(target_table or "").strip().lower()
                if normalized_target in known_storage_tables:
                    rows = [dict(row) for row in list(table.get("rows") or [])]
                    by_row = {str(row.get("row_id") or "").strip(): row for row in rows}

                    for _, target_row, target_field in edit_keys:
                        row_payload = by_row.get(target_row)
                        if row_payload is None:
                            errors.append(f"Unknown row during commit: {target_table}/{target_row}")
                            continue
                        lens = get_lens(target_field, lens_context=self._state.lens_context, config=self.config)
                        row_payload[target_field] = lens.encode(self._staged[(target_table, target_row, target_field)])

                    result = self.storage.persist_rows(normalized_target, rows)
                    if not bool(result.get("ok")):
                        errors.extend(list(result.get("errors") or []))
                    continue

                # Inferred/archetype table ids are persisted back to their source payloads.
                source_rows: dict[str, list[dict[str, str]]] = {}
                source_row_lookup: dict[str, dict[str, dict[str, str]]] = {}
                row_source: dict[str, str] = {}

                for row in list(table.get("rows") or []):
                    row_id_token = str(row.get("row_id") or "").strip()
                    source_token = str(row.get("_source") or "").strip().lower()
                    if not row_id_token or not source_token:
                        continue
                    row_source[row_id_token] = source_token
                    if source_token not in source_rows:
                        source_payload_rows = [dict(item) for item in list(self._rows_by_table.get(source_token) or [])]
                        source_rows[source_token] = source_payload_rows
                        source_row_lookup[source_token] = {
                            str(item.get("row_id") or "").strip(): item for item in source_payload_rows
                        }

                touched_sources: set[str] = set()
                for _, target_row, target_field in edit_keys:
                    source_token = row_source.get(target_row)
                    if not source_token:
                        errors.append(f"Unable to resolve source table for row: {target_table}/{target_row}")
                        continue
                    if source_token not in known_storage_tables:
                        errors.append(f"Unknown source table during commit: {source_token}")
                        continue

                    source_row = source_row_lookup.get(source_token, {}).get(target_row)
                    if source_row is None:
                        errors.append(f"Unknown source row during commit: {source_token}/{target_row}")
                        continue

                    lens = get_lens(target_field, lens_context=self._state.lens_context, config=self.config)
                    source_row[target_field] = lens.encode(self._staged[(target_table, target_row, target_field)])
                    touched_sources.add(source_token)

                for source_token in sorted(touched_sources):
                    result = self.storage.persist_rows(source_token, source_rows.get(source_token, []))
                    if not bool(result.get("ok")):
                        errors.extend(list(result.get("errors") or []))

        # Persist sidecar icon presentation edits.
        if canonical_pending_icons:
            merged_icons = dict(self._datum_icons_map)
            for datum_id, icon_rel in canonical_pending_icons.items():
                rel = self._canonical_icon_relpath(icon_rel)
                if rel:
                    merged_icons[datum_id] = rel
                else:
                    merged_icons.pop(datum_id, None)

            icon_result = self.storage.persist_datum_icons_map(merged_icons)
            if not bool(icon_result.get("ok")):
                errors.extend(list(icon_result.get("errors") or []))
            else:
                self._datum_icons_map = merged_icons

        if errors:
            return {"ok": False, "errors": errors, "warnings": warnings}

        for key in pending_data.keys():
            self._staged.pop(key, None)
        for key in canonical_pending_icons.keys():
            self._staged_presentation_icons.pop(key, None)

        self._reload()
        self._sync_state_staging()
        self._persist_state()
        self._refresh_panes_for_icon_change()
        return {"ok": True, "errors": [], "warnings": warnings}
