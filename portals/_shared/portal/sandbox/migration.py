from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..data_contract.anthology_pairs import compact_row_to_record, record_to_compact_row
from .engine import SandboxEngine


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _read_payload(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class SandboxAnthologyMigrationResult:
    ok: bool
    migrated_rows: list[str]
    replaced_rows: list[str]
    retained_rows: list[str]
    sandbox_resources: list[str]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "migrated_rows": list(self.migrated_rows),
            "replaced_rows": list(self.replaced_rows),
            "retained_rows": list(self.retained_rows),
            "sandbox_resources": list(self.sandbox_resources),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


def migrate_fnd_samras_rows_to_sandbox(
    *,
    anthology_path: Path,
    data_root: Path,
    apply_changes: bool,
) -> SandboxAnthologyMigrationResult:
    payload = _read_payload(anthology_path)
    if not payload:
        return SandboxAnthologyMigrationResult(
            ok=False,
            migrated_rows=[],
            replaced_rows=[],
            retained_rows=[],
            sandbox_resources=[],
            warnings=[],
            errors=[f"unable to load anthology payload: {anthology_path}"],
        )
    sandbox = SandboxEngine(data_root=data_root)

    migrated_rows: list[str] = []
    replaced_rows: list[str] = []
    retained_rows: list[str] = []
    sandbox_resources: list[str] = []
    warnings: list[str] = []
    out_rows: list[dict[str, Any]] = []

    candidate_rows = {
        "5-0-1": "txa-samras",
        "5-0-2": "msn-samras",
    }
    for key, value in payload.items():
        record, row_warnings, _ = compact_row_to_record(str(key), value)
        warnings.extend(list(row_warnings or []))
        identifier = _as_text(record.get("identifier") or record.get("row_id") or key)
        if identifier in candidate_rows:
            resource_id = candidate_rows[identifier]
            magnitude = _as_text(record.get("magnitude"))
            rows: list[dict[str, Any]] = []
            if magnitude.startswith("[") and magnitude.endswith("]"):
                try:
                    raw_items = json.loads(magnitude)
                except Exception:
                    raw_items = []
                if isinstance(raw_items, list):
                    rows = [
                        {"address_id": _as_text(item), "title": _as_text(item)}
                        for item in raw_items
                        if _as_text(item)
                    ]
            staged = sandbox.create_or_update_samras_resource(
                resource_id=resource_id,
                structure_payload="3-3-0-0-1-1-4",
                rows=rows,
                value_kind="txa_id" if resource_id.startswith("txa") else "msn_id",
                source="migration_from_anthology",
            )
            if staged.ok:
                sandbox_resources.append(resource_id)
                migrated_rows.append(identifier)
                record["magnitude"] = f"sandbox://samras/{resource_id}"
                record["pairs"] = [{"reference": _as_text(record.get("reference")), "magnitude": record["magnitude"]}]
                label = _as_text(record.get("label"))
                if label:
                    record["label"] = f"{label} [sandbox-managed]"
                replaced_rows.append(identifier)
            else:
                warnings.extend(list(staged.errors))
                retained_rows.append(identifier)
            out_rows.append(record)
            continue
        retained_rows.append(identifier)
        out_rows.append(record)

    if apply_changes:
        out_payload: dict[str, Any] = {}
        ordered = sorted(out_rows, key=lambda item: _as_text(item.get("identifier") or item.get("row_id")))
        for index, row in enumerate(ordered):
            out_key, out_value = record_to_compact_row(row, index + 1)
            if out_key:
                out_payload[out_key] = out_value
        _write_payload(anthology_path, out_payload)

    return SandboxAnthologyMigrationResult(
        ok=True,
        migrated_rows=migrated_rows,
        replaced_rows=replaced_rows,
        retained_rows=retained_rows,
        sandbox_resources=sandbox_resources,
        warnings=warnings,
        errors=[],
    )
