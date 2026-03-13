from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType
from typing import Any


TABLE_SPECS: dict[str, dict[str, str]] = {
    "anthology": {"filename": "anthology.json", "title": "Anthology"},
    "samras": {"filename": "demo-SAMRAS_MSN.json", "title": "SAMRAS"},
}

PRESENTATION_SCHEMA = "mycite.presentation.datum_icons.v0"
SAMRAS_INSTANCE_RE = re.compile(r"^(?P<msn>[0-9]+(?:-[0-9]+)*)\.(?P<instance>[0-9]+(?:-[0-9]+)*)\.json$")


def _load_shared_contract() -> ModuleType:
    shared_path = Path(__file__).resolve().parents[2] / "_shared" / "portal" / "data_contract" / "anthology_pairs.py"
    spec = importlib.util.spec_from_file_location("mycite_shared_data_contract_anthology_pairs", shared_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load shared data contract module from {shared_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SHARED = _load_shared_contract()
compact_row_to_record = _SHARED.compact_row_to_record
record_to_compact_row = _SHARED.record_to_compact_row
pairs_from_row = _SHARED.pairs_from_row


def _load_shared_anthology_normalization() -> ModuleType:
    shared_path = (
        Path(__file__).resolve().parents[2]
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


_SHARED_NORMALIZATION = _load_shared_anthology_normalization()
datum_sort_key = _SHARED_NORMALIZATION.datum_sort_key


class JsonStorageBackend:
    """JSON-backed adapter for anthology/SAMRAS payloads and presentation sidecars."""

    def __init__(self, data_dir: Path | str):
        self.data_dir = Path(data_dir)
        self._anthology_parse_warnings: list[str] = []
        self._anthology_payload_valid = True

    def known_tables(self) -> list[str]:
        return list(TABLE_SPECS.keys())

    def table_title(self, table_id: str) -> str:
        spec = TABLE_SPECS.get(str(table_id or "").strip().lower(), {})
        return str(spec.get("title") or table_id)

    def _table_path(self, table_id: str) -> Path:
        token = str(table_id or "").strip().lower()
        spec = TABLE_SPECS.get(token)
        if not spec:
            raise ValueError(f"Unknown table_id: {table_id}")
        return self.data_dir / str(spec["filename"])

    def _read_json_path(self, path: Path) -> dict[str, Any]:
        if not path.exists() or not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _samras_instance_filename(msn_id: str, instance_id: str) -> str:
        return f"{msn_id}.{instance_id}.json"

    def samras_instance_path(self, msn_id: str, instance_id: str) -> Path:
        msn_token = str(msn_id or "").strip()
        instance_token = str(instance_id or "").strip()
        if not msn_token or not instance_token:
            raise ValueError("msn_id and instance_id are required")
        return self.data_dir / self._samras_instance_filename(msn_token, instance_token)

    def list_samras_instances(self, msn_id: str) -> list[dict[str, Any]]:
        msn_token = str(msn_id or "").strip()
        if not msn_token:
            return []

        out: list[dict[str, Any]] = []
        pattern = f"{msn_token}.*.json"
        for path in sorted(self.data_dir.glob(pattern), key=lambda item: item.name):
            match = SAMRAS_INSTANCE_RE.fullmatch(path.name)
            if match is None:
                continue
            if str(match.group("msn") or "") != msn_token:
                continue
            instance_id = str(match.group("instance") or "").strip()
            if not instance_id:
                continue
            payload = self._read_json_path(path)
            row_count = len(payload) if isinstance(payload, dict) else 0
            out.append(
                {
                    "instance_id": instance_id,
                    "msn_id": msn_token,
                    "filename": path.name,
                    "path": str(path),
                    "row_count": row_count,
                }
            )
        return out

    def load_samras_instance_rows(self, msn_id: str, instance_id: str) -> list[dict[str, Any]]:
        payload = self._read_json_path(self.samras_instance_path(msn_id, instance_id))
        rows: list[dict[str, Any]] = []
        for key, value in payload.items():
            address_id = self._as_text(key).strip()
            if not address_id:
                continue
            names = value if isinstance(value, list) else [value]
            title = self._as_text(names[0] if names else "").strip()
            rows.append(
                {
                    "row_id": address_id,
                    "address_id": address_id,
                    "msn_id": address_id,
                    "title": title,
                    "name": title,
                    "_source": "samras",
                }
            )
        return rows

    def persist_samras_instance_rows(
        self,
        msn_id: str,
        instance_id: str,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        path = self.samras_instance_path(msn_id, instance_id)
        payload: dict[str, Any] = {}
        try:
            for index, row in enumerate(rows):
                key = str(
                    row.get("address_id")
                    or row.get("row_id")
                    or row.get("msn_id")
                    or f"row-{index + 1}"
                ).strip()
                if not key:
                    continue
                title = self._as_text(row.get("title") or row.get("name")).strip()
                payload[key] = [title]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            return {"ok": True, "errors": [], "warnings": []}
        except Exception as exc:
            return {"ok": False, "errors": [str(exc)], "warnings": []}

    def create_samras_instance(self, msn_id: str, instance_id: str) -> dict[str, Any]:
        path = self.samras_instance_path(msn_id, instance_id)
        if path.exists():
            return {"ok": False, "errors": [f"SAMRAS instance already exists: {instance_id}"], "warnings": []}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
            return {"ok": True, "errors": [], "warnings": [], "path": str(path)}
        except Exception as exc:
            return {"ok": False, "errors": [str(exc)], "warnings": []}

    def presentation_path(self) -> Path:
        return self.data_dir / "presentation" / "datum_icons.json"

    def read_payload(self, table_id: str) -> dict[str, Any]:
        path = self._table_path(table_id)
        if not path.exists() or not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def write_payload(self, table_id: str, payload: dict[str, Any]) -> None:
        path = self._table_path(table_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        token = str(table_id or "").strip().lower()
        if token == "anthology":
            path.write_text(self._format_anthology_payload(payload), encoding="utf-8")
            return
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def load_all_rows(self) -> dict[str, list[dict[str, Any]]]:
        return {table_id: self.load_rows(table_id) for table_id in self.known_tables()}

    def load_rows(self, table_id: str) -> list[dict[str, Any]]:
        token = str(table_id or "").strip().lower()
        payload = self.read_payload(token)
        if token == "anthology":
            return self._anthology_rows(payload)
        if token == "samras":
            return self._samras_rows(payload)
        return []

    def persist_rows(self, table_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        token = str(table_id or "").strip().lower()
        try:
            if token == "anthology":
                if not self._anthology_payload_valid:
                    return {
                        "ok": False,
                        "errors": ["anthology payload contains odd compact pair token(s); fix JSON before saving edits"],
                        "warnings": list(self._anthology_parse_warnings),
                    }
                payload = self._rows_to_anthology(rows)
            elif token == "samras":
                payload = self._rows_to_samras(rows)
            else:
                return {"ok": False, "errors": [f"Unknown table_id: {table_id}"], "warnings": []}
            self.write_payload(token, payload)
            return {"ok": True, "errors": [], "warnings": []}
        except Exception as exc:
            return {"ok": False, "errors": [str(exc)], "warnings": []}

    def anthology_parse_warnings(self) -> list[str]:
        return list(self._anthology_parse_warnings)

    def load_datum_icons_map(self) -> dict[str, str]:
        path = self.presentation_path()
        if not path.exists() or not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        mapping = payload.get("map") if isinstance(payload.get("map"), dict) else {}

        out: dict[str, str] = {}
        for key, value in mapping.items():
            datum_id = str(key or "").strip()
            rel = self._normalize_icon_relpath(value)
            if datum_id and rel:
                out[datum_id] = rel
        return out

    def persist_datum_icons_map(self, mapping: dict[str, str]) -> dict[str, Any]:
        path = self.presentation_path()
        try:
            existing_meta: dict[str, Any] = {}
            if path.exists() and path.is_file():
                current = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(current, dict) and isinstance(current.get("_meta"), dict):
                    existing_meta = dict(current.get("_meta") or {})

            payload = {
                "_meta": {
                    "schema": str(existing_meta.get("schema") or PRESENTATION_SCHEMA),
                    "icon_root": str(existing_meta.get("icon_root") or "assets/icons"),
                },
                "map": {},
            }

            cleaned: dict[str, str] = {}
            for key, value in dict(mapping or {}).items():
                datum_id = str(key or "").strip()
                rel = self._normalize_icon_relpath(value)
                if datum_id and rel:
                    cleaned[datum_id] = rel
            payload["map"] = cleaned

            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            return {"ok": True, "errors": [], "warnings": []}
        except Exception as exc:
            return {"ok": False, "errors": [str(exc)], "warnings": []}

    @staticmethod
    def _as_text(value: object) -> str:
        return "" if value is None else str(value)

    @staticmethod
    def _normalize_icon_relpath(value: object) -> str:
        token = str(value or "").strip().replace("\\", "/")
        token = token.lstrip("/")
        if token.startswith("assets/icons/"):
            token = token[len("assets/icons/") :]
        if token.startswith("/"):
            token = token[1:]
        return token

    @staticmethod
    def _anthology_sort_key(identifier: object, fallback: object = "") -> tuple[int, int, int, str]:
        return datum_sort_key(identifier, fallback)

    def _anthology_rows(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        warnings: list[str] = []
        payload_valid = True

        for key, value in payload.items():
            record, row_warnings, row_valid = compact_row_to_record(str(key), value)
            record["_source"] = "anthology"
            rows.append(record)
            warnings.extend(list(row_warnings or []))
            payload_valid = payload_valid and bool(row_valid)

        rows.sort(
            key=lambda row: self._anthology_sort_key(
                row.get("identifier"),
                row.get("row_id"),
            )
        )

        self._anthology_parse_warnings = warnings
        self._anthology_payload_valid = payload_valid
        return rows

    def _samras_rows(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key, value in payload.items():
            names = value if isinstance(value, list) else [value]
            rows.append(
                {
                    "row_id": self._as_text(key),
                    "msn_id": self._as_text(key),
                    "name": self._as_text(names[0] if names else ""),
                    "_source": "samras",
                }
            )
        return rows

    def _rows_to_anthology(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        ordered_rows = sorted(
            list(rows or []),
            key=lambda row: self._anthology_sort_key(
                row.get("identifier"),
                row.get("row_id"),
            ),
        )
        for index, row in enumerate(ordered_rows):
            key, value = record_to_compact_row(row, index + 1)
            if not key:
                continue
            out[key] = value
        return out

    def _rows_to_samras(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for index, row in enumerate(rows):
            key = str(row.get("row_id") or row.get("msn_id") or f"row-{index + 1}").strip()
            if not key:
                continue
            out[key] = [self._as_text(row.get("name"))]
        return out

    @staticmethod
    def _format_anthology_payload(payload: dict[str, Any]) -> str:
        if not isinstance(payload, dict) or not payload:
            return "{}\n"

        lines = ["{"]
        items = list(payload.items())
        last = len(items) - 1
        for index, (key, value) in enumerate(items):
            key_token = json.dumps(str(key))
            value_token = json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
            comma = "," if index < last else ""
            lines.append(f"  {key_token}: {value_token}{comma}")
        lines.append("}")
        return "\n".join(lines) + "\n"
