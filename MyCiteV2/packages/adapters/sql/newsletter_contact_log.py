"""Transitional filesystem-backed shim.

This module's class name still says ``MosDatum...`` for API-compat with
the mutation runtime; the implementation is filesystem-only per the
peripheral architecture (no MOS for grantee/extension state).

Going forward, callers should construct ``FilesystemNewsletterStateAdapter``
directly. This shim exists only to satisfy the mutation runtime's
historical import.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.filesystem.newsletter_state import (
    FilesystemNewsletterStateAdapter,
)


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


class MosDatumNewsletterContactLogAdapter:
    """Filesystem-backed shim with the legacy class name.

    Constructor accepts ``authority_db_file`` + ``tenant_id`` for
    call-site compatibility; derives ``private_dir`` as the sibling
    ``private/`` of the authority DB (canonical layout). When the
    canonical layout doesn't apply (tests, etc.), the caller can
    set ``private_dir`` explicitly.
    """

    def __init__(
        self,
        *,
        authority_db_file: str | Path,
        tenant_id: str,
        private_dir: str | Path | None = None,
    ) -> None:
        self._tenant_id = _as_text(tenant_id)
        if private_dir is not None:
            self._private_dir = Path(private_dir)
        else:
            # Canonical layout: <root>/authority.sqlite3 + <root>/private/
            self._private_dir = Path(authority_db_file).parent / "private"
        self._fs = FilesystemNewsletterStateAdapter(self._private_dir)

    def load_contact_log(self, *, domain: str) -> dict[str, Any]:
        return self._fs.load_contact_log(domain=domain)

    def save_contact_log(self, *, domain: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._fs.save_contact_log(domain=domain, payload=payload)

    @staticmethod
    def _split_legacy_name(name: object) -> tuple[str, str, str]:
        """Split a single-string name into (first, middle, last)."""
        token = _as_text(name)
        if not token:
            return ("", "", "")
        parts = token.split()
        if len(parts) == 1:
            return (parts[0], "", "")
        if len(parts) == 2:
            return (parts[0], "", parts[1])
        return (parts[0], " ".join(parts[1:-1]), parts[-1])


__all__ = ["MosDatumNewsletterContactLogAdapter"]
