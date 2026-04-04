from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_CANONICAL_ID_RE = re.compile(
    r"^(?P<prefix>rc|rf|sc)\.(?P<msn>[0-9]+(?:-[0-9]+)*)\.(?P<name>[A-Za-z0-9_.-]+)$",
    re.IGNORECASE,
)


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _safe_token(value: object) -> str:
    token = _as_text(value).lower()
    out: list[str] = []
    for ch in token:
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("_")
    return "".join(out).strip("._")


def payloads_root(data_root: Path) -> Path:
    return Path(data_root) / "payloads"


def payload_cache_root(data_root: Path) -> Path:
    return payloads_root(data_root) / "cache"


def ensure_payload_layout(data_root: Path) -> None:
    payloads_root(data_root).mkdir(parents=True, exist_ok=True)
    payload_cache_root(data_root).mkdir(parents=True, exist_ok=True)


def _payload_stem(identifier: str, *, default_prefix: str, source_msn_id: str) -> str:
    token = _as_text(identifier)
    if token.endswith(".json"):
        token = token[: -len(".json")]
    if token.endswith(".bin"):
        token = token[: -len(".bin")]
    match = _CANONICAL_ID_RE.fullmatch(token)
    if match is not None:
        return f"{_as_text(match.group('prefix')).lower()}.{_as_text(match.group('msn'))}.{_as_text(match.group('name')).lower()}"
    safe_name = _safe_token(token) or "payload"
    safe_source = _safe_token(source_msn_id)
    if not safe_source:
        raise ValueError(f"source_msn_id is required to materialize payload identifier '{identifier}'")
    return f"{_safe_token(default_prefix) or 'rf'}.{safe_source}.{safe_name}"


def payload_bin_path(data_root: Path, identifier: str, *, default_prefix: str = "rf", source_msn_id: str = "") -> Path:
    ensure_payload_layout(data_root)
    return payloads_root(data_root) / f"{_payload_stem(identifier, default_prefix=default_prefix, source_msn_id=source_msn_id)}.bin"


def decoded_payload_cache_path(
    data_root: Path,
    identifier: str,
    *,
    default_prefix: str = "rf",
    source_msn_id: str = "",
) -> Path:
    ensure_payload_layout(data_root)
    return payload_cache_root(data_root) / f"{_payload_stem(identifier, default_prefix=default_prefix, source_msn_id=source_msn_id)}.json"


def persist_mss_payload(
    data_root: Path,
    *,
    identifier: str,
    bitstring: str,
    decoded_payload: dict[str, Any] | None = None,
    default_prefix: str = "rf",
    source_msn_id: str = "",
) -> dict[str, str]:
    ensure_payload_layout(data_root)
    bin_path = payload_bin_path(data_root, identifier, default_prefix=default_prefix, source_msn_id=source_msn_id)
    cache_path = decoded_payload_cache_path(
        data_root,
        identifier,
        default_prefix=default_prefix,
        source_msn_id=source_msn_id,
    )
    bin_path.write_text(_as_text(bitstring), encoding="utf-8")
    if isinstance(decoded_payload, dict) and decoded_payload:
        cache_path.write_text(json.dumps(decoded_payload, indent=2) + "\n", encoding="utf-8")
    else:
        try:
            cache_path.unlink()
        except FileNotFoundError:
            pass
    return {"payload_path": str(bin_path), "cache_path": str(cache_path)}
