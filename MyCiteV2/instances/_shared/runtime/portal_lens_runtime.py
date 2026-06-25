"""Lens management runtime — the backend for the Utilities → Lenses surface and
the Control-Panel per-lens toggles (docs/wiki/81-lens-authoring-guide.md).

Lenses are managed (discovered/curated) and toggled ON/OFF here; a disabled lens
falls back to the identity passthrough in the workbench render path. State is a
small control-config JSON under ``<private_dir>/utilities/control/lens_state.json``
holding the set of *disabled* lens ids — absence ⇒ everything enabled (so a fresh
portal is behavior-preserving). This is control config, not a datum document, so
it is exempt from the MOS-only on-disk rule (same posture as tool_exposure).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

from MyCiteV2.packages.state_machine.lens import DEFAULT_DATUM_LENS_REGISTRY

LENS_STATE_SUBPATH = "utilities/control/lens_state.json"
LENS_CATALOG_RESPONSE_SCHEMA = "mycite.v2.portal.lenses.catalog.response.v1"
LENS_STATE_SCHEMA = "mycite.v2.portal.lenses.state.v1"


def _state_path(private_dir: str | Path) -> Path:
    return Path(private_dir) / LENS_STATE_SUBPATH


@functools.lru_cache(maxsize=1)
def _catalog_lens_ids() -> frozenset[str]:
    # The built-in lens catalog is fixed for the process lifetime, but this is on
    # the per-surface render hot path (resolved up to 3× per request) — memoize the
    # id set instead of rebuilding the full catalog (bindings dict + sort) each call.
    return frozenset(entry["lens_id"] for entry in DEFAULT_DATUM_LENS_REGISTRY.catalog())


def read_disabled_lens_ids(private_dir: str | Path | None) -> frozenset[str]:
    """The set of operator-disabled lens ids (empty ⇒ all enabled). Only ids that
    are still in the catalog are honored (a removed lens can't stay 'disabled')."""
    if private_dir is None:
        return frozenset()
    path = _state_path(private_dir)
    if not path.is_file():
        return frozenset()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return frozenset()
    disabled = {str(item).strip() for item in (payload.get("disabled") or []) if str(item).strip()}
    return frozenset(disabled & _catalog_lens_ids())


def enabled_lens_ids(private_dir: str | Path | None) -> frozenset[str]:
    """The set of currently-ENABLED catalog lens ids — what the render path passes
    to ``resolve_datum_lens(enabled_lens_ids=...)``."""
    return frozenset(_catalog_lens_ids() - read_disabled_lens_ids(private_dir))


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomic write for lens state (private, not served — KEEP leaves the 0600;
    compact, key-sorted JSON). Thin shim over :func:`atomic_io.atomic_write_text`."""
    from MyCiteV2.packages.adapters.filesystem.atomic_io import KEEP, atomic_write_text

    atomic_write_text(
        path, json.dumps(payload, separators=(",", ":"), sort_keys=True), mode=KEEP
    )


def set_lens_enabled(
    private_dir: str | Path, *, lens_id: str, enabled: bool
) -> dict[str, Any]:
    """Toggle one lens; persist; return the refreshed catalog response.

    Raises ``ValueError`` for an unknown lens id (can't toggle what isn't built in).
    """
    lens_token = str(lens_id or "").strip()
    if lens_token not in _catalog_lens_ids():
        raise ValueError(f"unknown lens_id: {lens_id!r}")
    disabled = set(read_disabled_lens_ids(private_dir))
    if enabled:
        disabled.discard(lens_token)
    else:
        disabled.add(lens_token)
    _atomic_write_json(
        _state_path(private_dir),
        {"schema": LENS_STATE_SCHEMA, "disabled": sorted(disabled)},
    )
    return build_lens_catalog_response(private_dir)


def build_lens_catalog_response(private_dir: str | Path | None) -> dict[str, Any]:
    """The catalog + per-lens enabled flag for the management/Control-Panel UI."""
    disabled = read_disabled_lens_ids(private_dir)
    lenses = [
        {**entry, "enabled": entry["lens_id"] not in disabled}
        for entry in DEFAULT_DATUM_LENS_REGISTRY.catalog()
    ]
    return {"schema": LENS_CATALOG_RESPONSE_SCHEMA, "lenses": lenses}


__all__ = [
    "LENS_CATALOG_RESPONSE_SCHEMA",
    "LENS_STATE_SCHEMA",
    "LENS_STATE_SUBPATH",
    "build_lens_catalog_response",
    "enabled_lens_ids",
    "read_disabled_lens_ids",
    "set_lens_enabled",
]
