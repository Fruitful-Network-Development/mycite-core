"""
Local audit log for tool and data-engine actions.

This log is distinct from the canonical external event stream. Use it for:
  - Local tool CRUD (e.g. AGRO-ERP product-type create/update/delete)
  - Data-engine audit events that are not cross-portal

Do NOT use the external event stream for these; that stream is reserved for
externally meaningful portal/network activity (see AGRO_ERP_INTENTION.md).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _audit_log_path(private_dir: Path, *, log_name: str = "tool_actions") -> Path:
    """Return path to the audit log file (NDJSON). Default: private/audit/tool_actions.ndjson."""
    return Path(private_dir) / "audit" / f"{log_name}.ndjson"


def append_audit_event(
    private_dir: Path,
    event: Dict[str, Any],
    *,
    log_name: str = "tool_actions",
    ts_unix_ms: int | None = None,
) -> Path:
    """
    Append a single event to the local audit log (NDJSON).

    Does not store secrets. Adds ts_unix_ms if missing.
    """
    payload = dict(event)
    payload.setdefault("ts_unix_ms", ts_unix_ms or int(time.time() * 1000))
    path = _audit_log_path(private_dir, log_name=log_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, separators=(",", ":")) + "\n")
    return path
