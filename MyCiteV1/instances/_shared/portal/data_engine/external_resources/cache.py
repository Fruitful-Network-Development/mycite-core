from __future__ import annotations

from typing import Any


class ExternalResourceCache:
    """Ephemeral compatibility cache.

    Canonical binary payloads and decoded MSS cache now live under
    ``data/payloads`` and ``data/payloads/cache``. This cache is only for
    transient bundle objects that do not belong in the filesystem contract.
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
