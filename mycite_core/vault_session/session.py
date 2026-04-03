from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from mycite_core.runtime_paths import vault_key_read_dirs, vault_keys_dir

_MAX_NONCE_HISTORY = 256


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _safe_identifier(value: str, *, fallback: str = "item") -> str:
    token = _as_str(value)
    cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in token)
    return cleaned or fallback


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def key_filename(key_id: str) -> str:
    return f"{_safe_identifier(key_id, fallback='key')}.json"


def key_path(private_dir: Path, key_id: str) -> Path:
    filename = key_filename(key_id)
    for directory in vault_key_read_dirs(private_dir):
        candidate = directory / filename
        if candidate.exists() and candidate.is_file():
            return candidate
    return vault_keys_dir(private_dir) / filename


def load_key_payload(private_dir: Path, key_id: str) -> Dict[str, Any] | None:
    path = key_path(private_dir, key_id)
    if not path.exists() or not path.is_file():
        return None
    try:
        return _read_json(path)
    except Exception:
        return None


def save_key_payload(private_dir: Path, key_id: str, payload: Dict[str, Any]) -> Path:
    path = vault_keys_dir(private_dir) / key_filename(key_id)
    _write_json(path, payload)
    return path


def decode_key_b64(token: str) -> bytes:
    key_bytes = base64.b64decode(token.encode("ascii"), validate=True)
    if len(key_bytes) != 32:
        raise ValueError("symmetric key must decode to 32 bytes")
    return key_bytes


def derive_symmetric_key_bytes(*, contract_id: str, sender_msn_id: str, receiver_msn_id: str) -> bytes:
    seed = _as_str(os.environ.get("MYCITE_SYMMETRIC_DERIVATION_SEED") or "mycite-dev-symmetric-seed")
    peers = sorted([_as_str(sender_msn_id), _as_str(receiver_msn_id)])
    material = f"{seed}|{_as_str(contract_id)}|{'|'.join(peers)}".encode("utf-8")
    return hashlib.sha256(material).digest()


def load_or_create_symmetric_key(
    *,
    private_dir: Path,
    contract_id: str,
    sender_msn_id: str,
    receiver_msn_id: str,
    preferred_key_id: str = "",
    current_meta: dict[str, Any] | None = None,
) -> tuple[str, bytes]:
    symmetric = dict(current_meta or {})
    key_id = _as_str(preferred_key_id) or _as_str(symmetric.get("key_id")) or f"symmetric-{_safe_identifier(contract_id)}"

    record = load_key_payload(private_dir, key_id)
    if record is not None:
        key_b64 = _as_str(record.get("key_b64"))
        if key_b64:
            return key_id, decode_key_b64(key_b64)

    key_bytes = derive_symmetric_key_bytes(
        contract_id=contract_id,
        sender_msn_id=sender_msn_id,
        receiver_msn_id=receiver_msn_id,
    )
    created_unix_ms = int(time.time() * 1000)
    save_key_payload(
        private_dir,
        key_id,
        {
            "schema": "mycite.vault.symmetric_key.v1",
            "key_id": key_id,
            "created_unix_ms": created_unix_ms,
            "key_b64": base64.b64encode(key_bytes).decode("ascii"),
            "derivation": {
                "mode": "seeded_v1",
                "contract_id": _as_str(contract_id),
                "sender_msn_id": _as_str(sender_msn_id),
                "receiver_msn_id": _as_str(receiver_msn_id),
            },
        },
    )
    return key_id, key_bytes


def b64encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def b64decode(value: str, *, field_name: str) -> bytes:
    token = _as_str(value)
    if not token:
        raise ValueError(f"{field_name} is required")
    try:
        return base64.b64decode(token.encode("ascii"), validate=True)
    except Exception as exc:
        raise ValueError(f"{field_name} must be valid base64") from exc


def renewal_aad(
    *,
    contract_id: str,
    sender_msn_id: str,
    receiver_msn_id: str,
    key_id: str,
) -> str:
    return json.dumps(
        {
            "schema": "mycite.contract.symmetric.renewal.aad.v1",
            "contract_id": _as_str(contract_id),
            "sender_msn_id": _as_str(sender_msn_id),
            "receiver_msn_id": _as_str(receiver_msn_id),
            "key_id": _as_str(key_id),
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def renewal_plaintext(
    *,
    contract_id: str,
    sender_msn_id: str,
    receiver_msn_id: str,
    event_datum: str,
    status: str,
    rotation_interval_seconds: int,
    details: Dict[str, Any],
) -> Dict[str, Any]:
    now_ms = int(time.time() * 1000)
    return {
        "schema": "mycite.contract.symmetric.renewal.payload.v1",
        "contract_id": _as_str(contract_id),
        "sender_msn_id": _as_str(sender_msn_id),
        "receiver_msn_id": _as_str(receiver_msn_id),
        "renewal_intent": "renew_contract",
        "rotation": {
            "mode": "manual_with_scheduler_hook",
            "requested_unix_ms": now_ms,
            "rotation_interval_seconds": int(rotation_interval_seconds),
        },
        "event_datum": _as_str(event_datum),
        "status": _as_str(status),
        "details": details if isinstance(details, dict) else {},
    }


def encrypt_renewal_envelope(
    *,
    key_bytes: bytes,
    key_id: str,
    contract_id: str,
    sender_msn_id: str,
    receiver_msn_id: str,
    plaintext: Dict[str, Any],
) -> Dict[str, Any]:
    aad = renewal_aad(
        contract_id=contract_id,
        sender_msn_id=sender_msn_id,
        receiver_msn_id=receiver_msn_id,
        key_id=key_id,
    )
    plaintext_bytes = json.dumps(plaintext, separators=(",", ":")).encode("utf-8")
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(key_bytes).encrypt(nonce, plaintext_bytes, aad.encode("utf-8"))
    return {
        "schema": "mycite.contract.symmetric.renewal.envelope.v1",
        "contract_id": _as_str(contract_id),
        "sender_msn_id": _as_str(sender_msn_id),
        "receiver_msn_id": _as_str(receiver_msn_id),
        "key_id": _as_str(key_id),
        "nonce_b64": b64encode(nonce),
        "ciphertext_b64": b64encode(ciphertext),
        "aad": aad,
    }


def decrypt_renewal_envelope(*, envelope: Dict[str, Any], key_bytes: bytes) -> Dict[str, Any]:
    nonce = b64decode(_as_str(envelope.get("nonce_b64")), field_name="nonce_b64")
    ciphertext = b64decode(_as_str(envelope.get("ciphertext_b64")), field_name="ciphertext_b64")
    aad = _as_str(envelope.get("aad"))
    if not aad:
        raise ValueError("aad is required")

    try:
        plaintext_bytes = AESGCM(key_bytes).decrypt(nonce, ciphertext, aad.encode("utf-8"))
    except Exception as exc:
        raise ValueError("unable to decrypt symmetric envelope") from exc

    try:
        payload = json.loads(plaintext_bytes.decode("utf-8"))
    except Exception as exc:
        raise ValueError("renewal plaintext payload is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("renewal plaintext payload must be a JSON object")
    return payload


def nonce_seen(meta: Dict[str, Any], *, direction: str, nonce_b64: str) -> bool:
    history = meta.get("nonce_history") if isinstance(meta.get("nonce_history"), dict) else {}
    values = history.get(direction) if isinstance(history.get(direction), list) else []
    token = _as_str(nonce_b64)
    return token in {str(item) for item in values}


def remember_nonce(meta: Dict[str, Any], *, direction: str, nonce_b64: str) -> Dict[str, Any]:
    out = dict(meta)
    history = out.get("nonce_history") if isinstance(out.get("nonce_history"), dict) else {}
    direction_values = history.get(direction) if isinstance(history.get(direction), list) else []
    token = _as_str(nonce_b64)
    if token:
        direction_values = [str(item) for item in direction_values if _as_str(item)]
        direction_values.append(token)
        if len(direction_values) > _MAX_NONCE_HISTORY:
            direction_values = direction_values[-_MAX_NONCE_HISTORY:]
        history[direction] = direction_values
    out["nonce_history"] = history
    return out


def coerce_positive_int(value: Any, default_value: int) -> int:
    try:
        token = int(value)
    except Exception:
        return int(default_value)
    if token < 1:
        return int(default_value)
    return token
