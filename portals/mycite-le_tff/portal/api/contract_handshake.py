from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from flask import abort, jsonify, make_response, request

from portal.services.crypto_signatures import ensure_dev_keypair, sign_payload, verify_payload_signature
from portal.services.request_log_store import append_event

FND_MSN_ID = "3-2-3-17-77-1-6-4-1-4"
TFF_MSN_ID = "3-2-3-17-77-2-6-3-1-6"

DEFAULT_EVENT_DATUM = "4-1-77"
DEFAULT_REQUEST_STATUS = "3-1-5"
DEFAULT_CONFIRM_STATUS = "3-1-6"


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _as_str(value: Any) -> str:
    return str(value or "").strip()


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

    event_datum = _as_str(confirmation.get("event_datum")) or default_event_datum
    confirm_status = _as_str(confirmation.get("status")) or DEFAULT_CONFIRM_STATUS
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
):
    @app.post("/portal/api/network/contracts/request")
    def contract_request_send():
        local_msn_id = _as_str(msn_id_provider())
        if not local_msn_id:
            abort(400, description="Portal msn_id is not configured")
        if not request.is_json:
            abort(415, description="Expected application/json body")

        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            abort(400, description="Expected JSON object body")

        target_msn_id = _as_str(body.get("target_msn_id"))
        if not target_msn_id:
            abort(400, description="Missing required field: target_msn_id")
        target_base_url = _as_str(body.get("target_base_url")) or _default_target_base_url(target_msn_id)
        if not target_base_url:
            abort(400, description="Missing target_base_url and no default target URL is configured")

        proposal_id = _as_str(body.get("proposal_id")) or f"cp-{uuid.uuid4().hex[:16]}"
        event_datum = _as_str(body.get("event_datum")) or DEFAULT_EVENT_DATUM
        request_status = _as_str(body.get("status")) or DEFAULT_REQUEST_STATUS
        details = body.get("details") if isinstance(body.get("details"), dict) else {}
        callback_url = _as_str(body.get("confirmation_callback_url"))

        proposal = {
            "proposal_id": proposal_id,
            "contract_id": _as_str(body.get("contract_id")) or f"contract-{proposal_id}",
            "sender_msn_id": local_msn_id,
            "receiver_msn_id": target_msn_id,
            "host_title": _as_str(body.get("host_title")),
            "progeny_type": _as_str(body.get("progeny_type")) or "member",
            "member_msn_id": _as_str(body.get("member_msn_id")),
            "template_version": _as_str(body.get("template_version")) or "1.0.0",
            "event_datum": event_datum,
            "status": request_status,
            "request_unix_ms": int(time.time() * 1000),
            "confirmation_callback_url": callback_url,
            "details": details,
        }

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
                },
            },
        )

        request_url = f"{target_base_url.rstrip('/')}/api/contracts/request/{target_msn_id}"
        status_code, remote_payload = _json_request(request_url, signed_request)
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
                        "target_url": request_url,
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
                        "status": DEFAULT_CONFIRM_STATUS,
                        "details": {
                            "proposal_id": proposal_id,
                            "target_url": request_url,
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
            "target_url": request_url,
            "http_status": status_code,
            "response": remote_payload,
            "confirmation_logged": confirmation_logged,
            "confirmation_error": confirmation_error,
        }
        if options_private_fn is not None:
            out["options_private"] = options_private_fn(local_msn_id)
        return jsonify(out), (200 if accepted else 502)

    @app.post("/api/contracts/request/<msn_id>")
    def contract_request_receive(msn_id: str):
        local_msn_id = _as_str(msn_id_provider())
        if not local_msn_id:
            abort(400, description="Portal msn_id is not configured")
        if _as_str(msn_id) != local_msn_id:
            abort(404, description=f"No contract ingress for msn_id={msn_id}")
        if not request.is_json:
            abort(415, description="Expected application/json body")

        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            abort(400, description="Expected JSON object body")

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
        event_datum = _as_str(proposal.get("event_datum")) or DEFAULT_EVENT_DATUM
        request_status = _as_str(proposal.get("status")) or DEFAULT_REQUEST_STATUS

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
                },
            },
        )

        confirmation = {
            "proposal_id": proposal_id,
            "contract_id": _as_str(proposal.get("contract_id")) or f"contract-{proposal_id}",
            "sender_msn_id": local_msn_id,
            "receiver_msn_id": sender_msn_id,
            "event_datum": event_datum,
            "status": DEFAULT_CONFIRM_STATUS,
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
                "event_datum": event_datum,
                "status": DEFAULT_CONFIRM_STATUS,
                "details": {
                    "proposal_id": proposal_id,
                    "confirmation": confirmation,
                    "signature": signed_confirmation.get("signature"),
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
            }
        ), 202

    @app.post("/api/contracts/confirmation/<msn_id>")
    def contract_confirmation_receive(msn_id: str):
        local_msn_id = _as_str(msn_id_provider())
        if not local_msn_id:
            abort(400, description="Portal msn_id is not configured")
        if _as_str(msn_id) != local_msn_id:
            abort(404, description=f"No confirmation ingress for msn_id={msn_id}")
        if not request.is_json:
            abort(415, description="Expected application/json body")

        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            abort(400, description="Expected JSON object body")

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

        event_datum = _as_str(confirmation.get("event_datum")) or DEFAULT_EVENT_DATUM
        confirm_status = _as_str(confirmation.get("status")) or DEFAULT_CONFIRM_STATUS

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
                },
            },
        )
        return jsonify({"ok": True, "accepted": True, "proposal_id": confirmation.get("proposal_id")}), 202

    @app.route("/portal/api/network/contracts/request", methods=["OPTIONS"])
    def contract_request_send_options():
        resp = make_response("", 204)
        resp.headers["Allow"] = "POST, OPTIONS"
        return resp

    @app.route("/api/contracts/request/<msn_id>", methods=["OPTIONS"])
    @app.route("/api/contracts/confirmation/<msn_id>", methods=["OPTIONS"])
    def contract_machine_options(msn_id: str):
        _ = msn_id
        resp = make_response("", 204)
        resp.headers["Allow"] = "POST, OPTIONS"
        return resp
