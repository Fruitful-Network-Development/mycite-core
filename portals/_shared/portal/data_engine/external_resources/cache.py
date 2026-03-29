from __future__ import annotations

from typing import Any


class ExternalResourceCache:
    """Ephemeral compatibility cache.

    The canonical filesystem contract does not allow JSON materialization under
    ``data/cache`` for external resources, so this cache is intentionally
    in-memory only.
    """

    _CACHE: dict[tuple[str, str], dict[str, Any]] = {}

    def __init__(self, data_dir) -> None:  # pragma: no cover - signature stability
        self._data_dir = data_dir

    def get(self, *, source_msn_id: str, resource_id: str) -> dict[str, Any] | None:
        payload = self._CACHE.get((str(source_msn_id or ""), str(resource_id or "")))
        return dict(payload) if isinstance(payload, dict) else None

    def put(self, *, source_msn_id: str, resource_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        cleaned = dict(payload if isinstance(payload, dict) else {})
        self._CACHE[(str(source_msn_id or ""), str(resource_id or ""))] = cleaned
        return cleaned
