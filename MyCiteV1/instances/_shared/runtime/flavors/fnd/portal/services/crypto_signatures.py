from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from portal.services.runtime_paths import vault_keys_dir


class SignatureVerificationError(ValueError):
    pass


def _as_bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    raise SignatureVerificationError("Expected bytes or utf-8 string")


def _sha256_hex(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def canonicalize_request(request) -> bytes:
    """Build canonical bytes for request signature verification."""
    body = request.get_data(cache=True) or b""
    timestamp = (request.headers.get("X-MyCite-Timestamp") or "").strip()
    nonce = (request.headers.get("X-MyCite-Nonce") or "").strip()
    host = (request.headers.get("Host") or "").strip().lower()

    if not timestamp or not nonce:
        raise SignatureVerificationError("Missing required signature headers")

    raw_query = (request.query_string or b"").decode("utf-8", errors="replace")
    parts = [
        request.method.upper(),
        request.path,
        raw_query,
        _sha256_hex(body),
        timestamp,
        nonce,
        host,
    ]
    return "\n".join(parts).encode("utf-8")


def canonicalize_payload(payload: Dict[str, Any]) -> bytes:
    """Deterministic payload bytes for Ed25519 signing/verification."""
    if not isinstance(payload, dict):
        raise SignatureVerificationError("Expected JSON object payload for signing")
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _portal_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def _find_public_card_path(public_dir: Path, msn_id: str) -> Optional[Path]:
    for candidate in (
        public_dir / f"{msn_id}.json",
        public_dir / f"msn-{msn_id}.json",
        public_dir / f"mss-{msn_id}.json",
    ):
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def ensure_dev_keypair(
    msn_id: str,
    *,
    portal_root: Optional[Path] = None,
    private_dir: Optional[Path] = None,
    public_dir: Optional[Path] = None,
    update_contact_card: bool = True,
) -> Dict[str, str]:
    """Create a local Ed25519 keypair for dev if missing and return key metadata."""
    if os.environ.get("MYCITE_ENABLE_DEV_KEYGEN", "1").strip() not in {"1", "true", "True", "yes"}:
        return {"ok": "false", "reason": "dev_keygen_disabled"}

    if not (msn_id or "").strip():
        raise ValueError("msn_id is required")

    root = portal_root or _portal_root_from_module()
    resolved_private_dir = private_dir or Path(os.environ.get("PRIVATE_DIR", str(root / "private")))
    resolved_public_dir = public_dir or Path(os.environ.get("PUBLIC_DIR", str(root / "public")))

    key_path = vault_keys_dir(resolved_private_dir) / f"{msn_id}_private.pem"
    key_path.parent.mkdir(parents=True, exist_ok=True)

    # Lazy import keeps normal request handling lightweight when key bootstrap is unused.
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    if key_path.exists():
        private_key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    else:
        private_key = Ed25519PrivateKey.generate()
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        key_path.write_bytes(private_bytes)

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    public_path = ""
    if update_contact_card:
        card_path = _find_public_card_path(resolved_public_dir, msn_id)
        if card_path is not None:
            payload = _read_json(card_path)
            if payload.get("public_key") != public_pem:
                payload["public_key"] = public_pem
                card_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            public_path = str(card_path)

    return {
        "ok": "true",
        "msn_id": msn_id,
        "private_key_path": str(key_path),
        "public_key_pem": public_pem,
        "public_card_path": public_path,
    }


def sign_payload(payload: Dict[str, Any], private_key_path: str | Path) -> str:
    """Return base64 Ed25519 signature for canonicalized payload."""
    try:
        key_bytes = Path(private_key_path).read_bytes()
    except Exception as exc:  # pragma: no cover - path/perm dependent
        raise SignatureVerificationError(f"Unable to read private key: {exc}") from exc

    try:
        from cryptography.hazmat.primitives import serialization
    except Exception as exc:  # pragma: no cover - environment dependent
        raise SignatureVerificationError(f"Missing cryptography dependency: {exc}") from exc

    try:
        private_key = serialization.load_pem_private_key(key_bytes, password=None)
    except Exception as exc:
        raise SignatureVerificationError(f"Unable to parse private key PEM: {exc}") from exc

    message = canonicalize_payload(payload)
    signature = private_key.sign(message)
    return base64.b64encode(signature).decode("ascii")


def verify_payload_signature(public_key_pem: str, payload: Dict[str, Any], signature_b64: str) -> bool:
    """Verify a base64 Ed25519 signature for canonicalized payload."""
    sig = str(signature_b64 or "").strip()
    if not sig:
        return False

    try:
        signature = base64.b64decode(sig, validate=True)
    except Exception:
        return False

    try:
        from cryptography.hazmat.primitives import serialization
    except Exception:
        return False

    try:
        public_key = serialization.load_pem_public_key(_as_bytes(public_key_pem))
    except Exception:
        return False

    try:
        public_key.verify(signature, canonicalize_payload(payload))
        return True
    except Exception:
        return False


def verify_signed_request(request, sender_public_key: str) -> bool:
    """Verify asymmetric signed request using Ed25519."""
    signature = (request.headers.get("X-MyCite-Signature") or "").strip()
    if not signature:
        return False

    try:
        message = canonicalize_request(request)
    except SignatureVerificationError:
        return False

    try:
        signature_bytes = base64.b64decode(signature, validate=True)
    except Exception:
        return os.environ.get("MYCITE_ALLOW_INSECURE_SIGNATURES", "0") == "1"

    try:
        from cryptography.hazmat.primitives import serialization
        public_key = serialization.load_pem_public_key(_as_bytes(sender_public_key))
        public_key.verify(signature_bytes, message)
        return True
    except Exception:
        return os.environ.get("MYCITE_ALLOW_INSECURE_SIGNATURES", "0") == "1"


def verify_hmac_request(request, shared_secret: str) -> bool:
    """Verify HMAC signature for contract-authenticated calls."""
    signature_b64 = (request.headers.get("X-MyCite-Signature") or "").strip()
    if not signature_b64:
        return False

    try:
        canonical = canonicalize_request(request)
    except SignatureVerificationError:
        return False

    mac = hmac.new(_as_bytes(shared_secret), canonical, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("ascii")
    return hmac.compare_digest(signature_b64, expected)
