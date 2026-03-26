"""
Shared tool data-spec schema and loader.

Tools declare:
  - inherited_inputs: list of inputs (e.g. from contract or public export). Each entry
    may include canonical_datum_path (msn_id.datum_address) or role so resolution uses
    the datum-identity layer and compiled index, not raw MSS row order.
  - outputs: list of datum shapes the tool creates. Each entry may describe
    field_structure or linked primitives; when a base anthology schema exists, prefer
    canonical datum paths for references rather than local row ids.
  - mediation: optional hints for encoding/decoding.

Specs are expressed in terms of canonical datum paths and (when available) base
anthology schema, not storage addresses. See CONTRACT_COMPACT_INDEX.md and
CANONICAL_DATA_ENGINE.md.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from _shared.portal.runtime_paths import utility_tools_dir


TOOL_SPEC_SCHEMA = "mycite.portal.tool_spec.v1"


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


@dataclass(frozen=True)
class ToolDataSpec:
    tool_id: str
    schema: str
    inherited_inputs: List[Dict[str, Any]]
    outputs: List[Dict[str, Any]]
    mediation: Dict[str, Any]


def _load_json_object(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def parse_tool_spec(payload: Dict[str, Any]) -> ToolDataSpec:
    tool_id = _as_text(payload.get("tool_id"))
    schema = _as_text(payload.get("schema") or TOOL_SPEC_SCHEMA)

    inherited_inputs = [
        dict(item)
        for item in (payload.get("inherited_inputs") or [])
        if isinstance(item, dict)
    ]
    outputs = [
        dict(item)
        for item in (payload.get("outputs") or [])
        if isinstance(item, dict)
    ]
    mediation = (
        dict(payload.get("mediation") or {})
        if isinstance(payload.get("mediation"), dict)
        else {}
    )

    return ToolDataSpec(
        tool_id=tool_id,
        schema=schema,
        inherited_inputs=inherited_inputs,
        outputs=outputs,
        mediation=mediation,
    )


def load_tool_spec(path: str | Path) -> Optional[ToolDataSpec]:
    candidate = Path(path)
    if not candidate.exists() or not candidate.is_file():
        return None
    try:
        payload = _load_json_object(candidate)
    except Exception:
        return None
    try:
        return parse_tool_spec(payload)
    except Exception:
        return None


def load_tool_spec_for_id(private_dir: Path, tool_id: str) -> Optional[ToolDataSpec]:
    """
    Load a tool data-spec from a standard location under the portal's private
    directory. Specs live at: private/tools/<tool_id>.spec.json
    """
    safe_tool_id = _as_text(tool_id)
    if not safe_tool_id:
        return None
    tool_root = utility_tools_dir(Path(private_dir))
    candidates: list[Path] = []
    token_variants = [
        safe_tool_id,
        safe_tool_id.replace("_", "-"),
        safe_tool_id.replace("-", "_"),
    ]
    seen: set[Path] = set()
    for token in token_variants:
        if not token:
            continue
        candidate = tool_root / token / "spec.json"
        if candidate in seen:
            continue
        seen.add(candidate)
        candidates.append(candidate)
    legacy = Path(private_dir) / "tools" / f"{safe_tool_id}.spec.json"
    if legacy not in seen:
        candidates.append(legacy)
    for candidate in candidates:
        spec = load_tool_spec(candidate)
        if spec is not None:
            return spec
    return None

