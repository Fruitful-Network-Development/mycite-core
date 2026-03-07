from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from data.engine.constraints import compile_constraint, resolve_chain
from data.engine.graph import META_FIELDS, build_graph, summarize_node
from data.engine.lenses import get_lens
from data.engine.nimm.directives import parse_directive
from data.engine.nimm.state import DataViewState, normalize_mode, normalize_source
from data.engine.nimm.viewmodels import empty_pane, pane, response_payload
from data.engine.tables import cluster_rows, infer_tables


_DATUM_ID_RE = re.compile(r"^[0-9]+-[0-9]+-[0-9]+$")
_EVENT_DIRECTIVE_RE = re.compile(
    r"^inv;\(med;(?P<anchor>[0-9]+(?:-[0-9]+)+);event_value\);(?P<row>[0-9]+)$"
)


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
            "focus_sources": ["auto", "anthology", "conspectus", "samras"],
            "icon_relpath_mode": self._icon_relpath_mode,
            "guarantees": [
                "UI state is driven by /portal/api/data/* responses, not direct file reads.",
                "Data and icon edits are staged before commit.",
                "Icon assignments are presentation sidecar metadata only.",
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
        token = str(identifier or "").strip()
        if not _DATUM_ID_RE.fullmatch(token):
            return (None, None, None)
        try:
            layer_s, value_group_s, iteration_s = token.split("-", 2)
            return (int(layer_s), int(value_group_s), int(iteration_s))
        except Exception:
            return (None, None, None)

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
        required_pairs = [{"reference": token, "magnitude": "0"} for token in required_refs]

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
                    "magnitude": "0",
                    "pairs": list(required_pairs),
                    "label": "event_value_collection",
                    "_source": "anthology",
                }
            )
            return True

        existing_pairs = self._pairs_from_row(anchor_row)
        normalized_pairs: list[dict[str, str]] = []
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
            normalized_pairs.append({"reference": reference, "magnitude": "0"})
            seen_refs.add(reference)
            tail = self._qualified_tail_identifier(reference)
            if _DATUM_ID_RE.fullmatch(tail):
                seen_tails.add(tail)
            if _DATUM_ID_RE.fullmatch(reference):
                seen_tails.add(reference)
            if str(pair.get("magnitude") or "").strip() != "0":
                changed = True

        for required_ref in required_refs:
            if required_ref in seen_tails or required_ref in seen_refs:
                continue
            normalized_pairs.append({"reference": required_ref, "magnitude": "0"})
            changed = True

        if not normalized_pairs:
            normalized_pairs = list(required_pairs)
            changed = True

        first_reference = str(normalized_pairs[0].get("reference") or "").strip()
        if str(anchor_row.get("reference") or "").strip() != first_reference:
            changed = True
        if str(anchor_row.get("magnitude") or "").strip() != "0":
            changed = True
        if str(anchor_row.get("label") or "").strip() == "":
            changed = True

        anchor_row["row_id"] = "4-0-1"
        anchor_row["identifier"] = "4-0-1"
        anchor_row["reference"] = first_reference
        anchor_row["magnitude"] = "0"
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

    def _sync_conspectus_from_anthology(self, anthology_rows: list[dict[str, Any]]) -> dict[str, Any]:
        conspectus_map: dict[str, list[str]] = {}

        for row in anthology_rows:
            identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
            if not identifier:
                continue
            _, value_group, _ = self._parse_datum_identifier(identifier)
            if value_group != 0:
                continue

            refs = [str(item.get("reference") or "").strip() for item in self._pairs_from_row(row)]
            refs = [ref for ref in refs if ref and ref != "0"]
            conspectus_map[identifier] = refs
            qualified_identifier = self._qualified_ref(identifier)
            if qualified_identifier:
                conspectus_map[qualified_identifier] = list(refs)

        # Time Series index is anchored at 4-0-1 and mirrored under <msn_id>-4-0-1.
        event_refs = self._event_index_refs(anthology_rows)
        conspectus_map["4-0-1"] = list(event_refs)
        qualified_anchor = self._qualified_ref("4-0-1")
        if qualified_anchor:
            conspectus_map[qualified_anchor] = list(event_refs)

        conspectus_rows: list[dict[str, str]] = []
        for key in sorted(conspectus_map.keys()):
            refs = list(conspectus_map.get(key) or [])
            conspectus_rows.append(
                {
                    "row_id": key,
                    "identifier": key,
                    "references": ", ".join(refs),
                    "_source": "conspectus",
                }
            )
        conspectus_rows.sort(key=lambda item: str(item.get("row_id") or ""))
        return self.storage.persist_rows("conspectus", conspectus_rows)

    def anthology_table_view(self) -> dict[str, Any]:
        rows = list(self.storage.load_rows("anthology") or [])
        conspectus_rows = list(self.storage.load_rows("conspectus") or [])
        conspectus_by_identifier: dict[str, list[str]] = {}
        for row in conspectus_rows:
            identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
            if not identifier:
                continue
            refs_text = str(row.get("references") or "").strip()
            refs = [token.strip() for token in refs_text.split(",") if token.strip()]
            conspectus_by_identifier[identifier] = refs

        normalized_rows: list[dict[str, Any]] = []
        parse_warnings = list(self.storage.anthology_parse_warnings()) if hasattr(self.storage, "anthology_parse_warnings") else []

        for row in rows:
            datum_id = str(row.get("identifier") or row.get("row_id") or "").strip()
            layer, value_group, iteration = self._parse_datum_identifier(datum_id)
            label_text = str(row.get("label") or datum_id).strip()
            pairs = self._pairs_from_row(row)
            first_reference, first_magnitude = self._first_pair(pairs)
            conspectus_references = (
                list(conspectus_by_identifier.get(datum_id, []))
                if value_group == 0
                else []
            )
            normalized_rows.append(
                {
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
                    "conspectus_references": conspectus_references,
                    "conspectus_count": len(conspectus_references),
                    **self._icon_meta(datum_id, label_text),
                }
            )

        normalized_rows.sort(
            key=lambda item: (
                10**9 if item.get("layer") is None else int(item.get("layer")),
                10**9 if item.get("value_group") is None else int(item.get("value_group")),
                10**9 if item.get("iteration") is None else int(item.get("iteration")),
                str(item.get("identifier") or ""),
            )
        )

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

    def time_series_ensure_base(self) -> dict[str, Any]:
        rows = list(self.storage.load_rows("anthology") or [])
        changed = self._ensure_time_series_anchor_row(rows)

        warnings: list[str] = []
        if changed:
            result = self.storage.persist_rows("anthology", rows)
            if not bool(result.get("ok")):
                return {"ok": False, "errors": list(result.get("errors") or ["failed to persist anthology"]), "warnings": []}
            warnings.extend(list(result.get("warnings") or []))

        sync_result = self._sync_conspectus_from_anthology(rows)
        if not bool(sync_result.get("ok")):
            return {
                "ok": False,
                "errors": ["failed to sync conspectus"] + list(sync_result.get("errors") or []),
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
        conspectus_rows = list(self.storage.load_rows("conspectus") or [])
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

        conspectus_by_identifier: dict[str, list[str]] = {}
        for row in conspectus_rows:
            identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
            refs_text = str(row.get("references") or "").strip()
            refs = [token.strip() for token in refs_text.split(",") if token.strip()]
            conspectus_by_identifier[identifier] = refs

        anchor_internal = "4-0-1"
        anchor_qualified = self._qualified_ref(anchor_internal)
        return {
            "ok": True,
            "errors": [],
            "warnings": [],
            "anchor_internal": anchor_internal,
            "anchor_qualified": anchor_qualified,
            "anchor_directive_base": f"inv;(med;{anchor_qualified or anchor_internal};event_value);<row_number>",
            "anchor_allowed_refs": sorted(self._event_anchor_allowed_refs(anthology_rows)),
            "indexed_event_refs_internal": list(conspectus_by_identifier.get(anchor_internal, [])),
            "indexed_event_refs_qualified": list(conspectus_by_identifier.get(anchor_qualified, [])),
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

        sync_result = self._sync_conspectus_from_anthology(rows)
        if not bool(sync_result.get("ok")):
            return {
                "ok": False,
                "errors": ["anthology updated, but failed to recompute conspectus"] + list(sync_result.get("errors") or []),
                "warnings": warnings + list(sync_result.get("warnings") or []),
            }
        warnings.extend(list(sync_result.get("warnings") or []))
        self._reload()
        self._refresh_panes_for_icon_change()
        self._persist_state()
        event_row_number = self._event_row_number_for_identifier(next_identifier, rows)
        return {
            "ok": True,
            "errors": [],
            "warnings": warnings,
            "event": self._event_payload_from_row(new_row, row_number=event_row_number),
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

        sync_result = self._sync_conspectus_from_anthology(rows)
        if not bool(sync_result.get("ok")):
            return {
                "ok": False,
                "errors": ["anthology updated, but failed to recompute conspectus"] + list(sync_result.get("errors") or []),
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

        sync_result = self._sync_conspectus_from_anthology(kept_rows)
        if not bool(sync_result.get("ok")):
            return {
                "ok": False,
                "errors": ["anthology updated, but failed to recompute conspectus"] + list(sync_result.get("errors") or []),
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

        sync_result = self._sync_conspectus_from_anthology(rows)
        if not bool(sync_result.get("ok")):
            return {
                "ok": False,
                "errors": ["anthology updated, but failed to recompute conspectus"] + list(sync_result.get("errors") or []),
                "warnings": warnings + list(result.get("warnings") or []) + list(sync_result.get("warnings") or []),
            }

        self._reload()
        self._refresh_panes_for_icon_change()
        self._persist_state()

        return {
            "ok": True,
            "errors": [],
            "warnings": warnings + list(result.get("warnings") or []) + list(sync_result.get("warnings") or []),
            "created": {
                "row_id": next_identifier,
                "identifier": next_identifier,
                "layer": layer,
                "value_group": value_group,
                "iteration": next_iteration,
                "reference": first_reference,
                "magnitude": first_magnitude,
                "pairs": normalized_pairs,
                "pair_count": len(normalized_pairs),
                "label": label_token,
            },
            "created_rows": [
                {
                    "row_id": next_identifier,
                    "identifier": next_identifier,
                    "layer": layer,
                    "value_group": value_group,
                    "iteration": next_iteration,
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
        sync_result = self._sync_conspectus_from_anthology(kept_rows)
        if not bool(sync_result.get("ok")):
            return {
                "ok": False,
                "errors": ["anthology updated, but failed to recompute conspectus"] + list(sync_result.get("errors") or []),
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
        sync_result = self._sync_conspectus_from_anthology(rows)
        if not bool(sync_result.get("ok")):
            return {
                "ok": False,
                "errors": ["anthology updated, but failed to recompute conspectus"] + list(sync_result.get("errors") or []),
                "warnings": warnings + list(sync_result.get("warnings") or []),
            }
        warnings.extend(list(sync_result.get("warnings") or []))

        if icon_relpath is not None:
            canonical_icon = self._canonical_icon_relpath(icon_relpath)
            if canonical_icon and not self._icon_exists(canonical_icon):
                return {"ok": False, "errors": [f"Invalid icon_relpath: {canonical_icon}"], "warnings": warnings}

            merged_icons = dict(self._datum_icons_map)
            if canonical_icon:
                merged_icons[datum_id] = canonical_icon
            else:
                merged_icons.pop(datum_id, None)

            icon_result = self.storage.persist_datum_icons_map(merged_icons)
            if not bool(icon_result.get("ok")):
                return {"ok": False, "errors": list(icon_result.get("errors") or ["failed to persist icon mapping"]), "warnings": warnings}
            warnings.extend(list(icon_result.get("warnings") or []))
            self._datum_icons_map = merged_icons

        self._reload()
        self._refresh_panes_for_icon_change()
        self._persist_state()

        updated_icon_meta = self._icon_meta(datum_id, next_label)
        return {
            "ok": True,
            "errors": [],
            "warnings": warnings,
            "updated": {
                "row_id": str(match.get("row_id") or "").strip(),
                "identifier": datum_id,
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

        if token == "conspectus":
            nodes = [self._graph.get_node(node_id) for node_id in self._graph.find_by_source("conspectus")]
            payload["selection_mappings"] = [
                self._enrich_datum_entry(
                    node.identifier,
                    node.label,
                    {
                        "identifier": node.identifier,
                        "references": node.raw.get("references", ""),
                        "node_id": node.node_id,
                    },
                )
                for node in nodes
                if node is not None
            ]
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
            "conspectus": len(self._graph.find_by_source("conspectus")),
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

        if action == "nav":
            source = normalize_source(subject or args.get("source") or self._state.focus_source, self._default_focus_source())
            self._state.focus_source = source
            self._state.focus_subject = ""
            self._state.left_pane = pane("navigation", self._nav_payload(source, args))
            self._state.right_pane = empty_pane("investigation")

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

            else:
                errors.append(f"Unsupported inv method: {method_token}")

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
