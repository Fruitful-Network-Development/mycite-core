from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .contact_cards import (
    find_local_public_card,
    public_key_fingerprint,
    read_json_object,
    resolve_contact_card,
    sanitize_contact_card,
)
from .contract_store import ContractNotFoundError, get_contract, upsert_contract
from .crypto_signatures import ensure_dev_keypair, sign_payload, verify_payload_signature

FND_MSN_ID = "3-2-3-17-77-1-6-4-1-4"
TFF_MSN_ID = "3-2-3-17-77-2-6-3-1-6"
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]")


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _sanitize_env_suffix(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(value or "")).upper()


def post_json(
    url: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float = 5.0,
) -> tuple[int, dict[str, Any]]:
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


def default_target_base_url(target_msn_id: str) -> str:
    specific = _as_str(os.environ.get(f"MYCITE_TARGET_BASE_URL_{_sanitize_env_suffix(target_msn_id)}"))
    if specific:
        return specific.rstrip("/")
    if target_msn_id == FND_MSN_ID:
        return _as_str(os.environ.get("MYCITE_FND_INTERNAL_BASE_URL") or "http://fnd_portal:5000").rstrip("/")
    if target_msn_id == TFF_MSN_ID:
        return _as_str(os.environ.get("MYCITE_TFF_INTERNAL_BASE_URL") or "http://tff_portal:5000").rstrip("/")
    return _as_str(os.environ.get("MYCITE_DEFAULT_CONTRACT_TARGET_BASE_URL")).rstrip("/")


def build_signed_payload(
    *,
    local_msn_id: str,
    payload_key: str,
    payload_value: dict[str, Any],
    private_dir: Path,
    public_dir: Path,
) -> dict[str, Any]:
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
        "public_key_fingerprint": public_key_fingerprint(public_key_pem),
        "signed_unix_ms": int(time.time() * 1000),
    }
    sender_contact_card: dict[str, Any] = {}
    card_path = find_local_public_card(public_dir, local_msn_id)
    if card_path is not None:
        try:
            card_payload = read_json_object(card_path)
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


def validate_signed_envelope(payload_key: str, body: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    payload_value = body.get(payload_key)
    signature = body.get("signature")
    if not isinstance(payload_value, dict):
        raise ValueError(f"Missing or invalid '{payload_key}' object")
    if not isinstance(signature, dict):
        raise ValueError("Missing or invalid 'signature' object")
    return payload_value, signature


def verify_sender_signature(
    *,
    public_dir: Path,
    signer_msn_id: str,
    payload_value: dict[str, Any],
    signature: dict[str, Any],
    sender_contact_card: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fallback_card = sanitize_contact_card(sender_contact_card or {})
    try:
        contact_card = resolve_contact_card(public_dir, signer_msn_id)
    except Exception:
        if fallback_card:
            contact_card = dict(fallback_card)
        else:
            raise
    if fallback_card:
        resolved_key = _as_str(contact_card.get("public_key"))
        fallback_key = _as_str(fallback_card.get("public_key"))
        if resolved_key and fallback_key and resolved_key != fallback_key:
            raise ValueError("sender_contact_card public_key does not match resolved contact card")

    card_msn_id = _as_str(contact_card.get("msn_id"))
    if card_msn_id and card_msn_id != signer_msn_id:
        raise ValueError("Signer msn_id does not match resolved contact card msn_id")

    sender_public_key = _as_str(contact_card.get("public_key"))
    if not sender_public_key and fallback_card:
        sender_public_key = _as_str(fallback_card.get("public_key"))
    if not sender_public_key:
        raise ValueError("Sender contact card does not include a public_key")

    signature_b64 = _as_str(signature.get("signature_b64"))
    if not verify_payload_signature(sender_public_key, payload_value, signature_b64):
        raise ValueError("Invalid signed payload")

    return {
        "contact_card_msn_id": card_msn_id or signer_msn_id,
        "public_key_fingerprint": public_key_fingerprint(sender_public_key),
    }


def load_contract_line(private_dir: Path, contract_id: str) -> dict[str, Any]:
    try:
        return get_contract(private_dir, contract_id)
    except ContractNotFoundError:
        return {"contract_id": _as_str(contract_id)}


def contract_symmetric_meta(payload: dict[str, Any]) -> dict[str, Any]:
    section = payload.get("symmetric") if isinstance(payload.get("symmetric"), dict) else {}
    return dict(section)


def persist_symmetric_meta(private_dir: Path, contract_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    contract_payload = load_contract_line(private_dir, contract_id)
    merged = dict(contract_symmetric_meta(contract_payload))
    merged.update(payload)
    merged.setdefault("schema", "mycite.contract.symmetric.v1")
    upsert_contract(
        private_dir,
        contract_id,
        {
            "symmetric": merged,
        },
        owner_msn_id=_as_str(contract_payload.get("owner_msn_id")),
    )
    return merged
