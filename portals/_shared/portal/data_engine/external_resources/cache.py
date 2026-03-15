from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ExternalResourceCache:
    def __init__(self, data_dir: Path) -> None:
        self._root = Path(data_dir) / "cache" / "external_resources"
        self._root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, source_msn_id: str, resource_id: str) -> Path:
        safe_resource = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in resource_id)
        safe_source = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in source_msn_id)
        return self._root / f"{safe_source}__{safe_resource}.json"

    def get(self, *, source_msn_id: str, resource_id: str) -> dict[str, Any] | None:
        path = self._path_for(source_msn_id, resource_id)
        if not path.exists() or not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def put(self, *, source_msn_id: str, resource_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        path = self._path_for(source_msn_id, resource_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return payload
