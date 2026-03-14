from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import abort, jsonify, make_response, request

from portal.services.mss import compile_mss_payload
from portal.services.contract_store import upsert_contract
from portal.services.crypto_signatures import ensure_dev_keypair, sign_payload, verify_payload_signature
from portal.services.datum_refs import normalize_datum_ref, parse_datum_ref
from portal.services.request_log_store import append_event
from portal.services.runtime_paths import (
    alias_read_dirs,
    contract_read_dirs,
    contracts_dir,
    member_profile_read_dirs,
    vault_key_read_dirs,
    vault_keys_dir,
)

FND_MSN_ID = "3-2-3-17-77-1-6-4-1-4"
TFF_MSN_ID = "3-2-3-17-77-2-6-3-1-6"

DEFAULT_EVENT_DATUM = "4-1-77"
DEFAULT_REQUEST_STATUS = "3-1-5"
DEFAULT_CONFIRM_STATUS = "3-1-6"
DEFAULT_SYMMETRIC_ROTATION_SECONDS = 7 * 24 * 60 * 60
_MAX_NONCE_HISTORY = 256
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]")


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        token = _as_str(item)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _mss_value(value: Any) -> str:
    if isinstance(value, list) and not value:
        return ""
    token = _as_str(value)
    if not token:
        return ""
    if any(char not in {"0", "1"} for char in token):
        raise ValueError("MSS contract values must be raw bitstrings")
    return token


def _safe_identifier(value: str, *, fallback: str = "item") -> str:
    token = _as_str(value)
    cleaned = _SAFE_ID_RE.sub("_", token)
    return cleaned or fallback


def _sanitize_env_suffix(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(value or "")).upper()


def _find_local_public_card(public_dir: Path, msn_id: str) -> Optional[Path]:
    token = _as_str(msn_id)
    if not token:
        return None
    candidates = [
        public_dir / f"{token}.json",
        public_dir / f"msn-{token}.json",
        public_dir / f"mss-{token}.json",
    ]
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None


def _fetch_remote_contact_card(sender_msn_id: str) -> Dict[str, Any]:
    base = _as_str(os.environ.get("MYCITE_CONTACT_BASE_URL")).rstrip("/")
    if not base:
        raise FileNotFoundError(
            "Contact card is not local and MYCITE_CONTACT_BASE_URL is unset for remote lookup."
        )
    url = f"{base}/{sender_msn_id}.json"
    with urllib.request.urlopen(url, timeout=4.0) as resp:
        body = resp.read()
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Remote contact card response was not a JSON object")
    return payload


def _resolve_contact_card(public_dir: Path, sender_msn_id: str) -> Dict[str, Any]:
    local_path = _find_local_public_card(public_dir, sender_msn_id)
    if local_path is not None:
        return _read_json(local_path)
    return _fetch_remote_contact_card(sender_msn_id)


def _sanitize_contact_card(payload: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {
        "msn_id",
        "schema",
        "title",
        "public_key",
        "entity_type",
        "accessible",
        "options_public",
        "options",
    }
    out = {key: payload.get(key) for key in allowed if key in payload}
    return out


def _public_key_fingerprint(public_key_pem: str) -> str:
    token = _as_str(public_key_pem)
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]


def _json_request(
    url: str,
    payload: Dict[str, Any],
    *,
    timeout_seconds: float = 5.0,
) -> tuple[int, Dict[str, Any]]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read()
            status = int(resp.getcode() or 0)
    except urllib.error.HTTPError as err:
        raw = err.read()
        status = int(err.code or 0)
    except urllib.error.URLError as err:
        return 0, {"ok": False, "error": str(err)}
    except TimeoutError as err:
        return 0, {"ok": False, "error": f"timeout: {err}"}

    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else {}
        if not isinstance(parsed, dict):
            parsed = {"raw": parsed}
    except Exception:
        parsed = {"raw": raw.decode("utf-8", errors="replace")}
    return status, parsed


def _default_internal_base_url(local_msn_id: str) -> str:
    override = _as_str(os.environ.get("MYCITE_INTERNAL_BASE_URL"))
    if override:
        return override.rstrip("/")
    if local_msn_id == FND_MSN_ID:
        return _as_str(os.environ.get("MYCITE_FND_INTERNAL_BASE_URL") or "http://fnd_portal:5000").rstrip("/")
    if local_msn_id == TFF_MSN_ID:
        return _as_str(os.environ.get("MYCITE_TFF_INTERNAL_BASE_URL") or "http://tff_portal:5000").rstrip("/")
    return _as_str(os.environ.get("MYCITE_DEFAULT_INTERNAL_BASE_URL")).rstrip("/")


def _default_target_base_url(target_msn_id: str) -> str:
    specific = _as_str(os.environ.get(f"MYCITE_TARGET_BASE_URL_{_sanitize_env_suffix(target_msn_id)}"))
    if specific:
        return specific.rstrip("/")
    if target_msn_id == FND_MSN_ID:
        return _as_str(os.environ.get("MYCITE_FND_INTERNAL_BASE_URL") or "http://fnd_portal:5000").rstrip("/")
    if target_msn_id == TFF_MSN_ID:
        return _as_str(os.environ.get("MYCITE_TFF_INTERNAL_BASE_URL") or "http://tff_portal:5000").rstrip("/")
    return _as_str(os.environ.get("MYCITE_DEFAULT_CONTRACT_TARGET_BASE_URL")).rstrip("/")


def _normalize_event_ref(value: Any, owner_msn_id: str, *, default_value: str = DEFAULT_EVENT_DATUM) -> str:
    raw = _as_str(value) or _as_str(default_value)
    return normalize_datum_ref(
        raw,
        local_msn_id=owner_msn_id,
        require_qualified=True,
        write_format="dot",
        field_name="event_datum",
    )


def _normalize_status_ref(value: Any, owner_msn_id: str, *, default_value: str) -> str:
    raw = _as_str(value) or _as_str(default_value)
    normalized = normalize_datum_ref(
        raw,
        local_msn_id=owner_msn_id,
        require_qualified=True,
        write_format="dot",
        field_name="status",
    )
    parsed = parse_datum_ref(normalized, field_name="status")
    if parsed.datum_address not in {"3-1-5", "3-1-6"}:
        raise ValueError("status must reference <msn_id>.3-1-5 or <msn_id>.3-1-6")
    return normalized


def _build_signed_payload(
    *,
    local_msn_id: str,
    payload_key: str,
    payload_value: Dict[str, Any],
    private_dir: Path,
    public_dir: Path,
) -> Dict[str, Any]:
    key_meta = ensure_dev_keypair(
        local_msn_id,
        private_dir=private_dir,
        public_dir=public_dir,
        update_contact_card=True,
    )
    private_key_path = _as_str(key_meta.get("private_key_path"))
    public_key_pem = _as_str(key_meta.get("public_key_pem"))
    if not private_key_path:
        raise ValueError("Signing key path was not available for this portal")

    signature_b64 = sign_payload(payload_value, private_key_path)
    signature_payload = {
        "alg": "ed25519",
        "signer_msn_id": local_msn_id,
        "signature_b64": signature_b64,
        "public_key_fingerprint": _public_key_fingerprint(public_key_pem),
        "signed_unix_ms": int(time.time() * 1000),
    }
    sender_contact_card: Dict[str, Any] = {}
    card_path = _find_local_public_card(public_dir, local_msn_id)
    if card_path is not None:
        try:
            card_payload = _read_json(card_path)
            sender_contact_card = {
                "msn_id": _as_str(card_payload.get("msn_id")),
                "title": _as_str(card_payload.get("title")),
                "schema": _as_str(card_payload.get("schema")),
                "entity_type": _as_str(card_payload.get("entity_type")),
                "public_key": _as_str(card_payload.get("public_key")),
            }
        except Exception:
            sender_contact_card = {}
    return {
        "schema": f"mycite.contract.{payload_key}.signed.v1",
        payload_key: payload_value,
        "signature": signature_payload,
        "sender_contact_card": sender_contact_card,
    }


def _validate_signed_envelope(payload_key: str, body: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    payload_value = body.get(payload_key)
    signature = body.get("signature")
    if not isinstance(payload_value, dict):
        abort(400, description=f"Missing or invalid '{payload_key}' object")
    if not isinstance(signature, dict):
        abort(400, description="Missing or invalid 'signature' object")
    return payload_value, signature


def _verify_sender_signature(
    *,
    public_dir: Path,
    signer_msn_id: str,
    payload_value: Dict[str, Any],
    signature: Dict[str, Any],
    sender_contact_card: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    fallback_card = sender_contact_card if isinstance(sender_contact_card, dict) else {}
    contact_card: Dict[str, Any]
    try:
        contact_card = _resolve_contact_card(public_dir, signer_msn_id)
    except Exception as exc:
        if fallback_card:
            contact_card = dict(fallback_card)
        else:
            abort(404, description=f"Unable to resolve sender contact card: {exc}")

    if fallback_card:
        resolved_key = _as_str(contact_card.get("public_key"))
        fallback_key = _as_str(fallback_card.get("public_key"))
        if resolved_key and fallback_key and resolved_key != fallback_key:
            abort(401, description="sender_contact_card public_key does not match resolved contact card")

    card_msn_id = _as_str(contact_card.get("msn_id"))
    if card_msn_id and card_msn_id != signer_msn_id:
        abort(401, description="Signer msn_id does not match resolved contact card msn_id")

    sender_public_key = _as_str(contact_card.get("public_key"))
    if not sender_public_key:
        abort(401, description="Sender contact card does not include a public_key")

    signature_b64 = _as_str(signature.get("signature_b64"))
    if not verify_payload_signature(sender_public_key, payload_value, signature_b64):
        abort(401, description="Invalid signed payload")

    return {
        "contact_card_msn_id": card_msn_id or signer_msn_id,
        "public_key_fingerprint": _public_key_fingerprint(sender_public_key),
    }


def _error_message(exc: Exception) -> str:
    description = getattr(exc, "description", None)
    if isinstance(description, str) and description.strip():
        return description.strip()
    text = str(exc).strip()
    return text or exc.__class__.__name__


def _contract_filename(contract_id: str) -> str:
    return f"contract-{_safe_identifier(contract_id, fallback='contract')}.json"


def _contract_path(private_dir: Path, contract_id: str) -> Path:
    filename = _contract_filename(contract_id)
    for directory in contract_read_dirs(private_dir):
        candidate = directory / filename
        if candidate.exists() and candidate.is_file():
            return candidate
    return contracts_dir(private_dir) / filename


def _load_contract_payload(private_dir: Path, contract_id: str) -> Dict[str, Any]:
    path = _contract_path(private_dir, contract_id)
    if path.exists() and path.is_file():
        try:
            payload = _read_json(path)
            payload.setdefault("contract_id", contract_id)
            return payload
        except Exception:
            pass
    return {"contract_id": contract_id}


def _save_contract_payload(private_dir: Path, contract_id: str, payload: Dict[str, Any]) -> Path:
    path = contracts_dir(private_dir) / _contract_filename(contract_id)
    normalized = dict(payload)
    normalized.setdefault("contract_id", contract_id)
    _write_json(path, normalized)
    return path


def _contract_symmetric_meta(payload: Dict[str, Any]) -> Dict[str, Any]:
    section = payload.get("symmetric") if isinstance(payload.get("symmetric"), dict) else {}
    return dict(section)


def _persist_symmetric_meta(private_dir: Path, contract_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    contract_payload = _load_contract_payload(private_dir, contract_id)
    merged = dict(_contract_symmetric_meta(contract_payload))
    merged.update(payload)
    merged.setdefault("schema", "mycite.contract.symmetric.v1")
    contract_payload["symmetric"] = merged
    _save_contract_payload(private_dir, contract_id, contract_payload)
    return merged


def _key_filename(key_id: str) -> str:
    return f"{_safe_identifier(key_id, fallback='key')}.json"


def _key_path(private_dir: Path, key_id: str) -> Path:
    filename = _key_filename(key_id)
    for directory in vault_key_read_dirs(private_dir):
        candidate = directory / filename
        if candidate.exists() and candidate.is_file():
            return candidate
    return vault_keys_dir(private_dir) / filename


def _load_key_payload(private_dir: Path, key_id: str) -> Dict[str, Any] | None:
    path = _key_path(private_dir, key_id)
    if not path.exists() or not path.is_file():
        return None
    try:
        return _read_json(path)
    except Exception:
        return None


def _save_key_payload(private_dir: Path, key_id: str, payload: Dict[str, Any]) -> Path:
    path = vault_keys_dir(private_dir) / _key_filename(key_id)
    _write_json(path, payload)
    return path


def _decode_key_b64(token: str) -> bytes:
    key_bytes = base64.b64decode(token.encode("ascii"), validate=True)
    if len(key_bytes) != 32:
        raise ValueError("symmetric key must decode to 32 bytes")
    return key_bytes


def _derive_symmetric_key_bytes(*, contract_id: str, sender_msn_id: str, receiver_msn_id: str) -> bytes:
    seed = _as_str(os.environ.get("MYCITE_SYMMETRIC_DERIVATION_SEED") or "mycite-dev-symmetric-seed")
    peers = sorted([_as_str(sender_msn_id), _as_str(receiver_msn_id)])
    material = f"{seed}|{_as_str(contract_id)}|{'|'.join(peers)}".encode("utf-8")
    return hashlib.sha256(material).digest()


def _load_or_create_symmetric_key(
    *,
    private_dir: Path,
    contract_id: str,
    sender_msn_id: str,
    receiver_msn_id: str,
    preferred_key_id: str = "",
) -> tuple[str, bytes]:
    contract_payload = _load_contract_payload(private_dir, contract_id)
    symmetric = _contract_symmetric_meta(contract_payload)
    key_id = _as_str(preferred_key_id) or _as_str(symmetric.get("key_id")) or f"symmetric-{_safe_identifier(contract_id)}"

    record = _load_key_payload(private_dir, key_id)
    if record is not None:
        key_b64 = _as_str(record.get("key_b64"))
        if key_b64:
            return key_id, _decode_key_b64(key_b64)

    key_bytes = _derive_symmetric_key_bytes(
        contract_id=contract_id,
        sender_msn_id=sender_msn_id,
        receiver_msn_id=receiver_msn_id,
    )
    created_unix_ms = int(time.time() * 1000)
    _save_key_payload(
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


def _b64encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _b64decode(value: str, *, field_name: str) -> bytes:
    token = _as_str(value)
    if not token:
        raise ValueError(f"{field_name} is required")
    try:
        return base64.b64decode(token.encode("ascii"), validate=True)
    except Exception as exc:
        raise ValueError(f"{field_name} must be valid base64") from exc


def _renewal_aad(
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


def _renewal_plaintext(
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


def _encrypt_renewal_envelope(
    *,
    key_bytes: bytes,
    key_id: str,
    contract_id: str,
    sender_msn_id: str,
    receiver_msn_id: str,
    plaintext: Dict[str, Any],
) -> Dict[str, Any]:
    aad = _renewal_aad(
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
        "nonce_b64": _b64encode(nonce),
        "ciphertext_b64": _b64encode(ciphertext),
        "aad": aad,
    }


def _decrypt_renewal_envelope(*, envelope: Dict[str, Any], key_bytes: bytes) -> Dict[str, Any]:
    nonce = _b64decode(_as_str(envelope.get("nonce_b64")), field_name="nonce_b64")
    ciphertext = _b64decode(_as_str(envelope.get("ciphertext_b64")), field_name="ciphertext_b64")
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


def _nonce_seen(meta: Dict[str, Any], *, direction: str, nonce_b64: str) -> bool:
    history = meta.get("nonce_history") if isinstance(meta.get("nonce_history"), dict) else {}
    values = history.get(direction) if isinstance(history.get(direction), list) else []
    token = _as_str(nonce_b64)
    return token in {str(item) for item in values}


def _remember_nonce(meta: Dict[str, Any], *, direction: str, nonce_b64: str) -> Dict[str, Any]:
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


def _coerce_positive_int(value: Any, default_value: int) -> int:
    try:
        token = int(value)
    except Exception:
        return int(default_value)
    if token < 1:
        return int(default_value)
    return token


def _contract_payload_rows(private_dir: Path) -> list[tuple[str, Dict[str, Any]]]:
    out: list[tuple[str, Dict[str, Any]]] = []
    seen: set[str] = set()
    for directory in contract_read_dirs(private_dir):
        if not directory.exists() or not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                payload = _read_json(path)
            except Exception:
                continue
            contract_id = _as_str(payload.get("contract_id"))
            if not contract_id:
                contract_id = path.stem.replace("contract-", "", 1) if path.stem.startswith("contract-") else path.stem
            if contract_id in seen:
                continue
            seen.add(contract_id)
            payload.setdefault("contract_id", contract_id)
            out.append((contract_id, payload))
    return out


def _alias_path(private_dir: Path, alias_id: str) -> Path | None:
    token = _as_str(alias_id)
    if not token or "/" in token or "\\" in token or ".." in token:
        return None
    for directory in alias_read_dirs(private_dir):
        candidate = directory / f"{token}.json"
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _load_alias_record(private_dir: Path, alias_id: str) -> Dict[str, Any] | None:
    path = _alias_path(private_dir, alias_id)
    if path is None:
        return None
    try:
        payload = _read_json(path)
    except Exception:
        return None
    payload.setdefault("alias_id", _as_str(alias_id))
    return payload


def _profile_matches_token(payload: Dict[str, Any], token: str) -> bool:
    candidates = {
        _as_str(payload.get("member_id")),
        _as_str(payload.get("member_msn_id")),
        _as_str(payload.get("tenant_id")),
        _as_str(payload.get("tenant_msn_id")),
        _as_str(payload.get("child_msn_id")),
        _as_str(payload.get("msn_id")),
    }
    return token in {item for item in candidates if item}


def _load_member_profile_for_alias(private_dir: Path, alias_payload: Dict[str, Any]) -> Dict[str, Any] | None:
    candidates = [
        _as_str(alias_payload.get("member_id")),
        _as_str(alias_payload.get("member_msn_id")),
        _as_str(alias_payload.get("child_msn_id")),
        _as_str(alias_payload.get("tenant_id")),
        _as_str(alias_payload.get("tenant_msn_id")),
    ]
    tokens = [item for item in candidates if item]
    if not tokens:
        return None

    for directory in member_profile_read_dirs(private_dir):
        if not directory.exists() or not directory.is_dir():
            continue
        for token in tokens:
            direct = directory / f"{token}.json"
            if direct.exists() and direct.is_file():
                try:
                    return _read_json(direct)
                except Exception:
                    pass

    for directory in member_profile_read_dirs(private_dir):
        if not directory.exists() or not directory.is_dir():
            continue
        for candidate in sorted(directory.glob("*.json")):
            try:
                payload = _read_json(candidate)
            except Exception:
                continue
            if any(_profile_matches_token(payload, token) for token in tokens):
                return payload
    return None


def _profile_refs_dict(payload: Dict[str, Any]) -> Dict[str, Any]:
    refs = payload.get("profile_refs") if isinstance(payload.get("profile_refs"), dict) else {}
    return dict(refs)


def _alias_reference_map(alias_payload: Dict[str, Any], member_payload: Dict[str, Any] | None) -> tuple[Dict[str, str], Dict[str, str]]:
    refs: Dict[str, str] = {}
    provenance: Dict[str, str] = {}

    alias_refs = _profile_refs_dict(alias_payload)
    progeny_refs = _profile_refs_dict(member_payload or {})
    field_refs = alias_payload.get("fields") if isinstance(alias_payload.get("fields"), dict) else {}

    for key, value in alias_refs.items():
        token = _as_str(value)
        if token:
            refs[str(key)] = token
            provenance[str(key)] = "alias"

    for key, value in progeny_refs.items():
        token = _as_str(value)
        if token and str(key) not in refs:
            refs[str(key)] = token
            provenance[str(key)] = "progeny"

    for key, value in field_refs.items():
        token = _as_str(value)
        if token and str(key) not in refs:
            refs[str(key)] = token
            provenance[str(key)] = "default"

    out: Dict[str, str] = {}
    out_provenance: Dict[str, str] = {}
    for key, value in refs.items():
        try:
            parse_datum_ref(value, field_name=key)
        except Exception:
            continue
        out[key] = value
        out_provenance[key] = provenance.get(key) or "default"
    return out, out_provenance


def _record_remote_confirmation(
    *,
    private_dir: Path,
    public_dir: Path,
    local_msn_id: str,
    expected_sender_msn_id: str,
    default_event_datum: str,
    envelope: Any,
) -> tuple[bool, str]:
    if not isinstance(envelope, dict):
        return False, "Remote response did not include a signed confirmation envelope"

    confirmation = envelope.get("confirmation")
    signature = envelope.get("signature")
    if not isinstance(confirmation, dict) or not isinstance(signature, dict):
        return False, "Remote confirmation envelope is missing confirmation/signature objects"

    signer_msn_id = _as_str(signature.get("signer_msn_id"))
    sender_msn_id = _as_str(confirmation.get("sender_msn_id")) or signer_msn_id
    if not sender_msn_id:
        return False, "confirmation.sender_msn_id is required"
    if signer_msn_id and signer_msn_id != sender_msn_id:
        return False, "signature.signer_msn_id must match confirmation.sender_msn_id"
    if _as_str(expected_sender_msn_id) and sender_msn_id != _as_str(expected_sender_msn_id):
        return False, "confirmation.sender_msn_id did not match target_msn_id"
    if _as_str(confirmation.get("receiver_msn_id")) != local_msn_id:
        return False, "confirmation.receiver_msn_id did not match local msn_id"

    try:
        verification = _verify_sender_signature(
            public_dir=public_dir,
            signer_msn_id=sender_msn_id,
            payload_value=confirmation,
            signature=signature,
            sender_contact_card=envelope.get("sender_contact_card"),
        )
    except Exception as exc:
        return False, _error_message(exc)

    try:
        event_datum = _normalize_event_ref(
            confirmation.get("event_datum") or default_event_datum,
            sender_msn_id,
            default_value=default_event_datum,
        )
        confirm_status = _normalize_status_ref(
            confirmation.get("status") or DEFAULT_CONFIRM_STATUS,
            sender_msn_id,
            default_value=DEFAULT_CONFIRM_STATUS,
        )
    except Exception as exc:
        return False, _error_message(exc)

    append_event(
        private_dir,
        local_msn_id,
        {
            "type": "contract_proposal.confirmed",
            "transmitter": f"msn-{sender_msn_id}",
            "receiver": f"msn-{local_msn_id}",
            "event_datum": event_datum,
            "status": confirm_status,
            "details": {
                "confirmation": confirmation,
                "signature": signature,
                "verification": verification,
                "source": "request_response",
            },
        },
    )
    return True, ""


def register_contract_handshake_routes(
    app,
    *,
    private_dir: Path,
    public_dir: Path,
    msn_id_provider: Callable[[], str],
    options_private_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    workspace: Any | None = None,
):
    def _local_msn_id() -> str:
        token = _as_str(msn_id_provider())
        if not token:
            abort(400, description="Portal msn_id is not configured")
        return token

    def _json_body() -> Dict[str, Any]:
        if not request.is_json:
            abort(415, description="Expected application/json body")
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            abort(400, description="Expected JSON object body")
        return body

    def _workspace_anthology_payload() -> Dict[str, Any]:
        if workspace is None:
            return {}
        storage = getattr(workspace, "storage", None)
        if storage is None or not hasattr(storage, "read_payload"):
            return {}
        try:
            payload = storage.read_payload("anthology")
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _compiled_owner_contract_context(body: Dict[str, Any], local_msn_id: str) -> tuple[str, list[str]]:
        selected_refs = _as_string_list(body.get("owner_selected_refs"))
        if not selected_refs:
            return _mss_value(body.get("owner_mss")), []
        anthology_payload = _workspace_anthology_payload()
        if not anthology_payload:
            raise ValueError("owner_selected_refs require a readable local anthology to compile owner_mss")
        compiled = compile_mss_payload(
            anthology_payload,
            selected_refs,
            local_msn_id=local_msn_id,
            include_selection_root=True,
        )
        return _as_str(compiled.get("bitstring")), selected_refs

    def _qualifier_endpoints(local_msn_id: str) -> Dict[str, Dict[str, Any]]:
        return {
            "network_anonymous_options": {
                "href": f"/api/network/anonymous/options/{local_msn_id}",
                "methods": ["GET", "OPTIONS"],
                "auth": "none",
                "qualifier": "anonymous",
            },
            "network_anonymous_contact": {
                "href": f"/api/network/anonymous/contact/{local_msn_id}",
                "methods": ["GET", "OPTIONS"],
                "auth": "none",
                "qualifier": "anonymous",
            },
            "network_asymmetric_request": {
                "href": f"/api/network/asymmetric/contracts/request/{local_msn_id}",
                "methods": ["POST", "OPTIONS"],
                "auth": "signed_envelope",
                "qualifier": "asymmetric",
                "compat_shim": f"/api/contracts/request/{local_msn_id}",
            },
            "network_asymmetric_confirmation": {
                "href": f"/api/network/asymmetric/contracts/confirmation/{local_msn_id}",
                "methods": ["POST", "OPTIONS"],
                "auth": "signed_envelope",
                "qualifier": "asymmetric",
                "compat_shim": f"/api/contracts/confirmation/{local_msn_id}",
            },
            "network_symmetric_renew": {
                "href": "/api/network/symmetric/contracts/<contract_id>/renew/<msn_id>",
                "methods": ["POST", "OPTIONS"],
                "auth": "vault_symmetric",
                "qualifier": "symmetric",
            },
            "network_portal_contract_request": {
                "href": "/portal/api/network/contracts/request",
                "methods": ["POST", "OPTIONS"],
                "auth": "keycloak_or_local",
                "qualifier": "asymmetric",
            },
            "network_portal_symmetric_due": {
                "href": "/portal/api/network/symmetric/contracts/due",
                "methods": ["GET", "OPTIONS"],
                "auth": "keycloak_or_local",
                "qualifier": "symmetric",
            },
            "network_portal_symmetric_renew": {
                "href": "/portal/api/network/symmetric/contracts/<contract_id>/renew",
                "methods": ["POST", "OPTIONS"],
                "auth": "keycloak_or_local",
                "qualifier": "symmetric",
            },
            "network_contacts_collection": {
                "href": "/portal/api/network/contacts/collection?alias_id=<alias_id>",
                "methods": ["GET", "OPTIONS"],
                "auth": "keycloak_or_local",
                "qualifier": "anonymous",
            },
        }

    def _compose_options_private(local_msn_id: str) -> Dict[str, Any]:
        base = options_private_fn(local_msn_id) if options_private_fn is not None else {}
        merged = dict(base)
        merged.update(_qualifier_endpoints(local_msn_id))
        return merged

    @app.post("/portal/api/network/contracts/request")
    @app.post("/portal/api/network/asymmetric/contracts/request")
    def contract_request_send():
        local_msn_id = _local_msn_id()
        body = _json_body()

        target_msn_id = _as_str(body.get("target_msn_id"))
        if not target_msn_id:
            abort(400, description="Missing required field: target_msn_id")
        target_base_url = _as_str(body.get("target_base_url")) or _default_target_base_url(target_msn_id)
        if not target_base_url:
            abort(400, description="Missing target_base_url and no default target URL is configured")

        proposal_id = _as_str(body.get("proposal_id")) or f"cp-{uuid.uuid4().hex[:16]}"
        event_datum = _normalize_event_ref(body.get("event_datum"), local_msn_id)
        request_status = _normalize_status_ref(body.get("status"), local_msn_id, default_value=DEFAULT_REQUEST_STATUS)
        details = body.get("details") if isinstance(body.get("details"), dict) else {}
        callback_url = _as_str(body.get("confirmation_callback_url"))
        try:
            owner_mss, owner_selected_refs = _compiled_owner_contract_context(body, local_msn_id)
        except ValueError as exc:
            abort(400, description=str(exc))

        proposal = {
            "proposal_id": proposal_id,
            "contract_id": _as_str(body.get("contract_id")) or f"contract-{proposal_id}",
            "contract_type": _as_str(body.get("contract_type")) or "portal_contract",
            "sender_msn_id": local_msn_id,
            "receiver_msn_id": target_msn_id,
            "host_title": _as_str(body.get("host_title")),
            "progeny_type": _as_str(body.get("progeny_type")) or "member",
            "member_msn_id": _as_str(body.get("member_msn_id")),
            "template_version": _as_str(body.get("template_version")) or "1.0.0",
            "owner_mss": owner_mss,
            "owner_selected_refs": owner_selected_refs,
            "event_datum": event_datum,
            "status": request_status,
            "request_unix_ms": int(time.time() * 1000),
            "confirmation_callback_url": callback_url,
            "details": details,
        }
        upsert_contract(
            private_dir,
            proposal["contract_id"],
            {
                "contract_type": proposal["contract_type"],
                "owner_msn_id": local_msn_id,
                "counterparty_msn_id": target_msn_id,
                "status": "pending",
                "template_version": proposal["template_version"],
                "host_title": proposal["host_title"],
                "progeny_type": proposal["progeny_type"],
                "details": details,
                "owner_mss": proposal["owner_mss"],
                "owner_selected_refs": proposal["owner_selected_refs"],
            },
            owner_msn_id=local_msn_id,
        )

        signed_request = _build_signed_payload(
            local_msn_id=local_msn_id,
            payload_key="proposal",
            payload_value=proposal,
            private_dir=private_dir,
            public_dir=public_dir,
        )

        append_event(
            private_dir,
            local_msn_id,
            {
                "type": "contract_proposal",
                "transmitter": f"msn-{local_msn_id}",
                "receiver": f"msn-{target_msn_id}",
                "event_datum": event_datum,
                "status": request_status,
                "details": {
                    "proposal": proposal,
                    "signature": signed_request.get("signature"),
                    "target_base_url": target_base_url,
                    "qualifier": "asymmetric",
                },
            },
        )

        request_url = f"{target_base_url.rstrip('/')}/api/network/asymmetric/contracts/request/{target_msn_id}"
        status_code, remote_payload = _json_request(request_url, signed_request)
        used_url = request_url

        if status_code in {404, 405}:
            legacy_url = f"{target_base_url.rstrip('/')}/api/contracts/request/{target_msn_id}"
            status_code, remote_payload = _json_request(legacy_url, signed_request)
            used_url = legacy_url

        accepted = status_code in {200, 201, 202}
        confirmation_logged = False
        confirmation_error = ""

        if not accepted:
            append_event(
                private_dir,
                local_msn_id,
                {
                    "type": "contract_proposal.delivery_failed",
                    "transmitter": f"msn-{local_msn_id}",
                    "receiver": f"msn-{target_msn_id}",
                    "event_datum": event_datum,
                    "status": request_status,
                    "details": {
                        "proposal_id": proposal_id,
                        "target_url": used_url,
                        "http_status": status_code,
                        "response": remote_payload,
                    },
                },
            )
        else:
            confirmation_logged, confirmation_error = _record_remote_confirmation(
                private_dir=private_dir,
                public_dir=public_dir,
                local_msn_id=local_msn_id,
                expected_sender_msn_id=target_msn_id,
                default_event_datum=event_datum,
                envelope=remote_payload.get("confirmation") if isinstance(remote_payload, dict) else None,
            )
            if not confirmation_logged:
                accepted = False
                append_event(
                    private_dir,
                    local_msn_id,
                    {
                        "type": "contract_proposal.confirmation_failed",
                        "transmitter": f"msn-{target_msn_id}",
                        "receiver": f"msn-{local_msn_id}",
                        "event_datum": event_datum,
                        "status": _normalize_status_ref(DEFAULT_CONFIRM_STATUS, local_msn_id, default_value=DEFAULT_CONFIRM_STATUS),
                        "details": {
                            "proposal_id": proposal_id,
                            "target_url": used_url,
                            "http_status": status_code,
                            "response": remote_payload,
                            "error": confirmation_error or "confirmation_verification_failed",
                        },
                    },
                )

        out: Dict[str, Any] = {
            "ok": accepted,
            "proposal_id": proposal_id,
            "target_msn_id": target_msn_id,
            "target_url": used_url,
            "http_status": status_code,
            "response": remote_payload,
            "confirmation_logged": confirmation_logged,
            "confirmation_error": confirmation_error,
            "qualifier": "asymmetric",
        }
        out["options_private"] = _compose_options_private(local_msn_id)
        return jsonify(out), (200 if accepted else 502)

    @app.post("/api/network/asymmetric/contracts/request/<msn_id>")
    @app.post("/api/contracts/request/<msn_id>")
    def contract_request_receive(msn_id: str):
        local_msn_id = _local_msn_id()
        if _as_str(msn_id) != local_msn_id:
            abort(404, description=f"No contract ingress for msn_id={msn_id}")

        body = _json_body()
        proposal, signature = _validate_signed_envelope("proposal", body)
        sender_msn_id = _as_str(proposal.get("sender_msn_id"))
        if not sender_msn_id:
            abort(400, description="proposal.sender_msn_id is required")
        if _as_str(signature.get("signer_msn_id")) != sender_msn_id:
            abort(400, description="signature.signer_msn_id must match proposal.sender_msn_id")
        if _as_str(proposal.get("receiver_msn_id")) != local_msn_id:
            abort(400, description="proposal.receiver_msn_id must match request path msn_id")

        verification = _verify_sender_signature(
            public_dir=public_dir,
            signer_msn_id=sender_msn_id,
            payload_value=proposal,
            signature=signature,
            sender_contact_card=body.get("sender_contact_card"),
        )

        proposal_id = _as_str(proposal.get("proposal_id")) or f"cp-{uuid.uuid4().hex[:16]}"
        event_datum = _normalize_event_ref(proposal.get("event_datum"), sender_msn_id)
        request_status = _normalize_status_ref(proposal.get("status"), sender_msn_id, default_value=DEFAULT_REQUEST_STATUS)

        append_event(
            private_dir,
            local_msn_id,
            {
                "type": "contract_proposal",
                "transmitter": f"msn-{sender_msn_id}",
                "receiver": f"msn-{local_msn_id}",
                "event_datum": event_datum,
                "status": request_status,
                "details": {
                    "proposal": proposal,
                    "signature": signature,
                    "verification": verification,
                    "qualifier": "asymmetric",
                },
            },
        )

        upsert_contract(
            private_dir,
            _as_str(proposal.get("contract_id")) or f"contract-{proposal_id}",
            {
                "contract_type": _as_str(proposal.get("contract_type")) or "portal_contract",
                "owner_msn_id": local_msn_id,
                "counterparty_msn_id": sender_msn_id,
                "status": "pending",
                "template_version": _as_str(proposal.get("template_version")) or "1.0.0",
                "host_title": _as_str(proposal.get("host_title")),
                "progeny_type": _as_str(proposal.get("progeny_type")),
                "details": proposal.get("details") if isinstance(proposal.get("details"), dict) else {},
                "counterparty_mss": _mss_value(proposal.get("owner_mss")),
                "counterparty_selected_refs": _as_string_list(proposal.get("owner_selected_refs")),
            },
            owner_msn_id=local_msn_id,
        )

        stored_contract = _load_contract_payload(private_dir, _as_str(proposal.get("contract_id")) or f"contract-{proposal_id}")
        owner_mss = _mss_value(stored_contract.get("owner_mss"))
        owner_selected_refs = _as_string_list(stored_contract.get("owner_selected_refs"))

        confirmation = {
            "proposal_id": proposal_id,
            "contract_id": _as_str(proposal.get("contract_id")) or f"contract-{proposal_id}",
            "contract_type": _as_str(proposal.get("contract_type")) or "portal_contract",
            "sender_msn_id": local_msn_id,
            "receiver_msn_id": sender_msn_id,
            "owner_mss": owner_mss,
            "owner_selected_refs": owner_selected_refs,
            "event_datum": _normalize_event_ref(event_datum, sender_msn_id, default_value=DEFAULT_EVENT_DATUM),
            "status": _normalize_status_ref(DEFAULT_CONFIRM_STATUS, local_msn_id, default_value=DEFAULT_CONFIRM_STATUS),
            "confirmed_unix_ms": int(time.time() * 1000),
            "details": {
                "verification": verification,
                "result": "accepted",
            },
        }
        signed_confirmation = _build_signed_payload(
            local_msn_id=local_msn_id,
            payload_key="confirmation",
            payload_value=confirmation,
            private_dir=private_dir,
            public_dir=public_dir,
        )

        append_event(
            private_dir,
            local_msn_id,
            {
                "type": "contract_proposal.confirmed",
                "transmitter": f"msn-{local_msn_id}",
                "receiver": f"msn-{sender_msn_id}",
                "event_datum": confirmation["event_datum"],
                "status": confirmation["status"],
                "details": {
                    "proposal_id": proposal_id,
                    "confirmation": confirmation,
                    "signature": signed_confirmation.get("signature"),
                    "qualifier": "asymmetric",
                },
            },
        )

        callback_url = _as_str(proposal.get("confirmation_callback_url"))
        callback_status = 0
        callback_payload: Dict[str, Any] = {}
        callback_ok = False
        if callback_url:
            callback_status, callback_payload = _json_request(callback_url, signed_confirmation)
            callback_ok = callback_status in {200, 201, 202}

        return jsonify(
            {
                "ok": True,
                "accepted": True,
                "proposal_id": proposal_id,
                "callback_url": callback_url,
                "callback_ok": callback_ok,
                "callback_status": callback_status,
                "callback_response": callback_payload,
                "confirmation": signed_confirmation,
                "qualifier": "asymmetric",
            }
        ), 202

    @app.post("/api/network/asymmetric/contracts/confirmation/<msn_id>")
    @app.post("/api/contracts/confirmation/<msn_id>")
    def contract_confirmation_receive(msn_id: str):
        local_msn_id = _local_msn_id()
        if _as_str(msn_id) != local_msn_id:
            abort(404, description=f"No confirmation ingress for msn_id={msn_id}")

        body = _json_body()
        confirmation, signature = _validate_signed_envelope("confirmation", body)
        sender_msn_id = _as_str(confirmation.get("sender_msn_id"))
        if not sender_msn_id:
            abort(400, description="confirmation.sender_msn_id is required")
        if _as_str(signature.get("signer_msn_id")) != sender_msn_id:
            abort(400, description="signature.signer_msn_id must match confirmation.sender_msn_id")
        if _as_str(confirmation.get("receiver_msn_id")) != local_msn_id:
            abort(400, description="confirmation.receiver_msn_id must match request path msn_id")

        verification = _verify_sender_signature(
            public_dir=public_dir,
            signer_msn_id=sender_msn_id,
            payload_value=confirmation,
            signature=signature,
            sender_contact_card=body.get("sender_contact_card"),
        )

        event_datum = _normalize_event_ref(confirmation.get("event_datum"), sender_msn_id)
        confirm_status = _normalize_status_ref(confirmation.get("status"), sender_msn_id, default_value=DEFAULT_CONFIRM_STATUS)

        append_event(
            private_dir,
            local_msn_id,
            {
                "type": "contract_proposal.confirmed",
                "transmitter": f"msn-{sender_msn_id}",
                "receiver": f"msn-{local_msn_id}",
                "event_datum": event_datum,
                "status": confirm_status,
                "details": {
                    "confirmation": confirmation,
                    "signature": signature,
                    "verification": verification,
                    "qualifier": "asymmetric",
                },
            },
        )
        upsert_contract(
            private_dir,
            _as_str(confirmation.get("contract_id")) or f"contract-{_as_str(confirmation.get('proposal_id'))}",
            {
                "contract_type": _as_str(confirmation.get("contract_type")) or "portal_contract",
                "owner_msn_id": local_msn_id,
                "counterparty_msn_id": sender_msn_id,
                "status": "active",
                "counterparty_mss": _mss_value(confirmation.get("owner_mss")),
                "counterparty_selected_refs": _as_string_list(confirmation.get("owner_selected_refs")),
            },
            owner_msn_id=local_msn_id,
        )
        return jsonify({"ok": True, "accepted": True, "proposal_id": confirmation.get("proposal_id"), "qualifier": "asymmetric"}), 202

    @app.post("/api/network/symmetric/contracts/<contract_id>/renew/<msn_id>")
    def symmetric_contract_renew_receive(contract_id: str, msn_id: str):
        local_msn_id = _local_msn_id()
        if _as_str(msn_id) != local_msn_id:
            abort(404, description=f"No symmetric renewal ingress for msn_id={msn_id}")

        envelope = _json_body()
        if _as_str(envelope.get("contract_id")) != _as_str(contract_id):
            abort(400, description="envelope.contract_id must match route contract_id")

        sender_msn_id = _as_str(envelope.get("sender_msn_id"))
        receiver_msn_id = _as_str(envelope.get("receiver_msn_id"))
        if not sender_msn_id:
            abort(400, description="sender_msn_id is required")
        if receiver_msn_id != local_msn_id:
            abort(400, description="receiver_msn_id must match request path msn_id")

        key_id = _as_str(envelope.get("key_id"))
        if not key_id:
            abort(400, description="key_id is required")

        contract_payload = _load_contract_payload(private_dir, contract_id)
        symmetric_meta = _contract_symmetric_meta(contract_payload)
        expected_key_id = _as_str(symmetric_meta.get("key_id"))
        if expected_key_id and key_id != expected_key_id:
            abort(409, description="key_id mismatch for symmetric contract renewal")

        key_id, key_bytes = _load_or_create_symmetric_key(
            private_dir=private_dir,
            contract_id=contract_id,
            sender_msn_id=sender_msn_id,
            receiver_msn_id=local_msn_id,
            preferred_key_id=key_id,
        )

        nonce_b64 = _as_str(envelope.get("nonce_b64"))
        if _nonce_seen(symmetric_meta, direction="received", nonce_b64=nonce_b64):
            abort(409, description="nonce_b64 has already been used for this contract")

        try:
            plaintext = _decrypt_renewal_envelope(envelope=envelope, key_bytes=key_bytes)
        except ValueError as exc:
            abort(401, description=str(exc))

        event_datum = _normalize_event_ref(plaintext.get("event_datum"), sender_msn_id)
        status_ref = _normalize_status_ref(plaintext.get("status"), sender_msn_id, default_value=DEFAULT_CONFIRM_STATUS)
        rotation = plaintext.get("rotation") if isinstance(plaintext.get("rotation"), dict) else {}
        rotation_interval_seconds = _coerce_positive_int(
            rotation.get("rotation_interval_seconds"),
            DEFAULT_SYMMETRIC_ROTATION_SECONDS,
        )
        now_ms = int(time.time() * 1000)

        updated_meta = _remember_nonce(symmetric_meta, direction="received", nonce_b64=nonce_b64)
        updated_meta.update(
            {
                "schema": "mycite.contract.symmetric.v1",
                "enabled": True,
                "key_id": key_id,
                "counterparty_msn_id": sender_msn_id,
                "rotation_interval_seconds": rotation_interval_seconds,
                "last_renewed_unix_ms": now_ms,
                "next_due_unix_ms": now_ms + (rotation_interval_seconds * 1000),
            }
        )
        _persist_symmetric_meta(private_dir, contract_id, updated_meta)

        append_event(
            private_dir,
            local_msn_id,
            {
                "type": "contract.symmetric.renewal.received",
                "transmitter": f"msn-{sender_msn_id}",
                "receiver": f"msn-{local_msn_id}",
                "event_datum": event_datum,
                "status": status_ref,
                "details": {
                    "contract_id": _as_str(contract_id),
                    "key_id": key_id,
                    "qualifier": "symmetric",
                    "rotation_interval_seconds": rotation_interval_seconds,
                    "aad": _as_str(envelope.get("aad")),
                    "payload": {
                        "schema": _as_str(plaintext.get("schema")),
                        "renewal_intent": _as_str(plaintext.get("renewal_intent")),
                    },
                },
            },
        )

        return jsonify(
            {
                "ok": True,
                "accepted": True,
                "contract_id": _as_str(contract_id),
                "sender_msn_id": sender_msn_id,
                "receiver_msn_id": local_msn_id,
                "key_id": key_id,
                "qualifier": "symmetric",
            }
        ), 202

    @app.post("/portal/api/network/symmetric/contracts/<contract_id>/renew")
    def symmetric_contract_renew_send(contract_id: str):
        local_msn_id = _local_msn_id()
        body = _json_body()

        contract_payload = _load_contract_payload(private_dir, contract_id)
        symmetric_meta = _contract_symmetric_meta(contract_payload)

        target_msn_id = _as_str(body.get("target_msn_id")) or _as_str(contract_payload.get("counterparty_msn_id")) or _as_str(symmetric_meta.get("counterparty_msn_id"))
        if not target_msn_id:
            abort(400, description="target_msn_id is required")

        target_base_url = _as_str(body.get("target_base_url")) or _default_target_base_url(target_msn_id)
        if not target_base_url:
            abort(400, description="Missing target_base_url and no default target URL is configured")

        rotation_interval_seconds = _coerce_positive_int(
            body.get("rotation_interval_seconds") or symmetric_meta.get("rotation_interval_seconds"),
            DEFAULT_SYMMETRIC_ROTATION_SECONDS,
        )
        key_id_hint = _as_str(body.get("key_id") or symmetric_meta.get("key_id"))
        key_id, key_bytes = _load_or_create_symmetric_key(
            private_dir=private_dir,
            contract_id=contract_id,
            sender_msn_id=local_msn_id,
            receiver_msn_id=target_msn_id,
            preferred_key_id=key_id_hint,
        )

        event_datum = _normalize_event_ref(body.get("event_datum"), local_msn_id)
        status_ref = _normalize_status_ref(body.get("status"), local_msn_id, default_value=DEFAULT_CONFIRM_STATUS)
        details = body.get("details") if isinstance(body.get("details"), dict) else {}
        plaintext = _renewal_plaintext(
            contract_id=contract_id,
            sender_msn_id=local_msn_id,
            receiver_msn_id=target_msn_id,
            event_datum=event_datum,
            status=status_ref,
            rotation_interval_seconds=rotation_interval_seconds,
            details=details,
        )
        envelope = _encrypt_renewal_envelope(
            key_bytes=key_bytes,
            key_id=key_id,
            contract_id=contract_id,
            sender_msn_id=local_msn_id,
            receiver_msn_id=target_msn_id,
            plaintext=plaintext,
        )

        append_event(
            private_dir,
            local_msn_id,
            {
                "type": "contract.symmetric.renewal.sent",
                "transmitter": f"msn-{local_msn_id}",
                "receiver": f"msn-{target_msn_id}",
                "event_datum": event_datum,
                "status": status_ref,
                "details": {
                    "contract_id": _as_str(contract_id),
                    "key_id": key_id,
                    "qualifier": "symmetric",
                    "rotation_interval_seconds": rotation_interval_seconds,
                    "target_base_url": target_base_url,
                    "nonce_b64": _as_str(envelope.get("nonce_b64")),
                },
            },
        )

        renew_url = f"{target_base_url.rstrip('/')}/api/network/symmetric/contracts/{_as_str(contract_id)}/renew/{target_msn_id}"
        status_code, remote_payload = _json_request(renew_url, envelope)
        accepted = status_code in {200, 201, 202}

        if accepted:
            now_ms = int(time.time() * 1000)
            updated_meta = _remember_nonce(symmetric_meta, direction="sent", nonce_b64=_as_str(envelope.get("nonce_b64")))
            updated_meta.update(
                {
                    "schema": "mycite.contract.symmetric.v1",
                    "enabled": True,
                    "key_id": key_id,
                    "counterparty_msn_id": target_msn_id,
                    "rotation_interval_seconds": rotation_interval_seconds,
                    "last_renewed_unix_ms": now_ms,
                    "next_due_unix_ms": now_ms + (rotation_interval_seconds * 1000),
                }
            )
            _persist_symmetric_meta(private_dir, contract_id, updated_meta)

        out = {
            "ok": accepted,
            "contract_id": _as_str(contract_id),
            "target_msn_id": target_msn_id,
            "target_url": renew_url,
            "http_status": status_code,
            "response": remote_payload,
            "key_id": key_id,
            "qualifier": "symmetric",
        }
        out["options_private"] = _compose_options_private(local_msn_id)
        return jsonify(out), (200 if accepted else 502)

    @app.get("/portal/api/network/symmetric/contracts/due")
    def symmetric_contract_due_list():
        local_msn_id = _local_msn_id()
        include_all = _as_str(request.args.get("all")).lower() in {"1", "true", "yes"}
        now_ms = int(time.time() * 1000)

        items: list[Dict[str, Any]] = []
        for contract_id, payload in _contract_payload_rows(private_dir):
            symmetric_meta = _contract_symmetric_meta(payload)
            if not symmetric_meta:
                continue
            enabled = bool(symmetric_meta.get("enabled", True))
            if not enabled:
                continue
            counterparty_msn_id = _as_str(payload.get("counterparty_msn_id")) or _as_str(symmetric_meta.get("counterparty_msn_id"))
            if not counterparty_msn_id:
                continue

            rotation_interval_seconds = _coerce_positive_int(
                symmetric_meta.get("rotation_interval_seconds"),
                DEFAULT_SYMMETRIC_ROTATION_SECONDS,
            )
            last_renewed = int(symmetric_meta.get("last_renewed_unix_ms") or 0)
            next_due = int(symmetric_meta.get("next_due_unix_ms") or 0)
            if next_due <= 0:
                next_due = (last_renewed + (rotation_interval_seconds * 1000)) if last_renewed > 0 else 0
            due = next_due <= 0 or next_due <= now_ms
            if not include_all and not due:
                continue

            items.append(
                {
                    "contract_id": contract_id,
                    "counterparty_msn_id": counterparty_msn_id,
                    "key_id": _as_str(symmetric_meta.get("key_id")),
                    "rotation_interval_seconds": rotation_interval_seconds,
                    "last_renewed_unix_ms": last_renewed,
                    "next_due_unix_ms": next_due,
                    "due": due,
                    "renew_endpoint": f"/portal/api/network/symmetric/contracts/{contract_id}/renew",
                }
            )

        out = {
            "ok": True,
            "msn_id": local_msn_id,
            "qualifier": "symmetric",
            "contracts": sorted(items, key=lambda item: (not bool(item.get("due")), int(item.get("next_due_unix_ms") or 0))),
            "scheduler_hook": {
                "mode": "manual_plus_external_scheduler",
                "recommended_flow": [
                    "GET /portal/api/network/symmetric/contracts/due",
                    "POST /portal/api/network/symmetric/contracts/<contract_id>/renew",
                ],
            },
        }
        out["options_private"] = _compose_options_private(local_msn_id)
        return jsonify(out), 200

    @app.get("/portal/api/network/contacts/collection")
    def network_contacts_collection():
        local_msn_id = _local_msn_id()
        if workspace is None or not hasattr(workspace, "resolve_contact_collection"):
            abort(501, description="network contact collection resolution is unavailable")

        alias_id = _as_str(request.args.get("alias_id"))
        override_ref = _as_str(request.args.get("collection_ref"))
        if not alias_id and not override_ref:
            abort(400, description="alias_id or collection_ref is required")

        alias_payload = _load_alias_record(private_dir, alias_id) if alias_id else None
        member_payload = _load_member_profile_for_alias(private_dir, alias_payload or {}) if alias_payload else None

        warnings: list[str] = []
        errors: list[str] = []
        resolution_chain: list[Dict[str, str]] = []

        selected_ref = ""
        selected_source = ""

        if alias_payload is not None:
            alias_refs = _profile_refs_dict(alias_payload)
            alias_collection_ref = _as_str(alias_refs.get("contact_collection_ref"))
            if alias_collection_ref:
                selected_ref = alias_collection_ref
                selected_source = "alias.profile_refs.contact_collection_ref"
            else:
                legacy_field_ref = _as_str((alias_payload.get("fields") or {}).get("contact_collection_ref")) if isinstance(alias_payload.get("fields"), dict) else ""
                if legacy_field_ref:
                    selected_ref = legacy_field_ref
                    selected_source = "alias.fields.contact_collection_ref"
                    warnings.append("Using legacy alias.fields.contact_collection_ref; migrate to alias.profile_refs.contact_collection_ref")

            if not selected_ref and member_payload is not None:
                progeny_refs = _profile_refs_dict(member_payload)
                progeny_collection_ref = _as_str(progeny_refs.get("contact_collection_ref"))
                if progeny_collection_ref:
                    selected_ref = progeny_collection_ref
                    selected_source = "progeny.profile_refs.contact_collection_ref"

        if not selected_ref and override_ref:
            selected_ref = override_ref
            selected_source = "api.collection_ref_override"

        if not selected_ref:
            abort(400, description="No contact_collection_ref could be resolved from alias/progeny profile_refs or override")

        parsed_source = parse_datum_ref(selected_ref, field_name="contact_collection_ref")
        normalized_dot = normalize_datum_ref(
            selected_ref,
            local_msn_id=local_msn_id,
            require_qualified=True,
            write_format="dot",
            field_name="contact_collection_ref",
        )
        normalized_hyphen = normalize_datum_ref(
            selected_ref,
            local_msn_id=local_msn_id,
            require_qualified=True,
            write_format="hyphen",
            field_name="contact_collection_ref",
        )

        resolution_chain.append(
            {
                "source": selected_source,
                "raw_ref": selected_ref,
                "normalized_ref": normalized_dot,
            }
        )

        result = workspace.resolve_contact_collection(collection_ref=normalized_hyphen)
        status_code = int(result.get("status_code") or (200 if bool(result.get("ok")) else 400))
        warnings.extend([str(item) for item in list(result.get("warnings") or [])])
        errors.extend([str(item) for item in list(result.get("errors") or [])])

        source_payload = result.get("source") if isinstance(result.get("source"), dict) else {}
        resolved_chain = source_payload.get("resolution_chain") if isinstance(source_payload.get("resolution_chain"), list) else []
        for item in resolved_chain:
            if isinstance(item, dict):
                resolution_chain.append({
                    "source": _as_str(item.get("kind") or "workspace"),
                    "raw_ref": _as_str(item.get("input_ref")),
                    "normalized_ref": _as_str(item.get("resolved_identifier")),
                })

        payload = {
            "ok": bool(result.get("ok")) and not errors,
            "alias_id": alias_id,
            "selected_source": selected_source,
            "resolved_collection_ref": _as_str(source_payload.get("resolved_collection_identifier") or source_payload.get("resolved_collection_ref")),
            "resolution_chain": resolution_chain,
            "contacts": list(result.get("contacts") or []),
            "summary": result.get("summary") if isinstance(result.get("summary"), dict) else {"contacts_total": len(list(result.get("contacts") or []))},
            "warnings": warnings,
            "errors": errors,
            "normalized_refs": {
                "collection_ref": {
                    "raw": selected_ref,
                    "source_format": parsed_source.source_format,
                    "normalized_dot": normalized_dot,
                    "normalized_hyphen": normalized_hyphen,
                    "datum_address": parsed_source.datum_address,
                    "msn_id": parsed_source.msn_id or local_msn_id,
                }
            },
        }
        payload["options_private"] = _compose_options_private(local_msn_id)
        return jsonify(payload), status_code

    @app.get("/api/network/anonymous/options/<msn_id>")
    def network_anonymous_options(msn_id: str):
        local_msn_id = _local_msn_id()
        if _as_str(msn_id) != local_msn_id:
            abort(404, description=f"No anonymous options for msn_id={msn_id}")

        endpoints = _qualifier_endpoints(local_msn_id)
        grouped: Dict[str, list[Dict[str, Any]]] = {"anonymous": [], "asymmetric": [], "symmetric": []}
        for endpoint in endpoints.values():
            qualifier = _as_str(endpoint.get("qualifier")) or "anonymous"
            grouped.setdefault(qualifier, []).append(endpoint)
        return jsonify(
            {
                "ok": True,
                "schema": "mycite.network.options.qualifier.v1",
                "msn_id": local_msn_id,
                "qualifiers": grouped,
                "endpoints": endpoints,
            }
        )

    @app.get("/api/network/anonymous/contact/<msn_id>")
    def network_anonymous_contact(msn_id: str):
        local_msn_id = _local_msn_id()
        if _as_str(msn_id) != local_msn_id:
            abort(404, description=f"No anonymous contact for msn_id={msn_id}")

        card_path = _find_local_public_card(public_dir, local_msn_id)
        if card_path is None:
            abort(404, description=f"No local public contact card for msn_id={local_msn_id}")
        card_payload = _sanitize_contact_card(_read_json(card_path))
        return jsonify({"ok": True, "msn_id": local_msn_id, "contact": card_payload, "qualifier": "anonymous"}), 200

    @app.route("/portal/api/network/contracts/request", methods=["OPTIONS"])
    @app.route("/portal/api/network/asymmetric/contracts/request", methods=["OPTIONS"])
    def contract_request_send_options():
        resp = make_response("", 204)
        resp.headers["Allow"] = "POST, OPTIONS"
        return resp

    @app.route("/api/contracts/request/<msn_id>", methods=["OPTIONS"])
    @app.route("/api/network/asymmetric/contracts/request/<msn_id>", methods=["OPTIONS"])
    @app.route("/api/contracts/confirmation/<msn_id>", methods=["OPTIONS"])
    @app.route("/api/network/asymmetric/contracts/confirmation/<msn_id>", methods=["OPTIONS"])
    @app.route("/api/network/anonymous/options/<msn_id>", methods=["OPTIONS"])
    @app.route("/api/network/anonymous/contact/<msn_id>", methods=["OPTIONS"])
    def contract_machine_options(msn_id: str):
        _ = msn_id
        resp = make_response("", 204)
        resp.headers["Allow"] = "POST, GET, OPTIONS"
        return resp

    @app.route("/api/network/symmetric/contracts/<contract_id>/renew/<msn_id>", methods=["OPTIONS"])
    def symmetric_machine_options(contract_id: str, msn_id: str):
        _ = contract_id
        _ = msn_id
        resp = make_response("", 204)
        resp.headers["Allow"] = "POST, OPTIONS"
        return resp

    @app.route("/portal/api/network/symmetric/contracts/<contract_id>/renew", methods=["OPTIONS"])
    @app.route("/portal/api/network/symmetric/contracts/due", methods=["OPTIONS"])
    @app.route("/portal/api/network/contacts/collection", methods=["OPTIONS"])
    def portal_network_options(contract_id: str | None = None):
        _ = contract_id
        resp = make_response("", 204)
        resp.headers["Allow"] = "GET, POST, OPTIONS"
        return resp
