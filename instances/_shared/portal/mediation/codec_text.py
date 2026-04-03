from __future__ import annotations

from typing import Any

from .types import MediationResult, result


def _decode_hex_text(raw: str) -> tuple[str, str | None]:
    token = str(raw or "").strip()
    if not token:
        return "", None
    if len(token) % 2 != 0:
        return "", "hex token has odd length"
    try:
        data = bytes.fromhex(token)
    except Exception:
        return "", "invalid hex token"
    try:
        return data.decode("utf-8"), None
    except Exception:
        return data.decode("utf-8", errors="replace"), "hex token is not strict utf-8"


def _encode_hex_text(raw: str, *, append_null_terminator: bool) -> str:
    token = str(raw or "")
    data = token.encode("utf-8")
    encoded = data.hex()
    if append_null_terminator:
        encoded += "00"
    return encoded


def decode_ascii_char(*, standard_id: str, reference: str, magnitude: str, context: dict[str, Any] | None = None) -> MediationResult:
    _ = context
    token = str(magnitude or "").strip()
    warnings: list[str] = []
    errors: list[str] = []

    if not token:
        return result(
            standard_id=standard_id,
            reference=reference,
            magnitude="",
            value="",
            display="",
        )

    char_out = ""
    try:
        if token.isdigit():
            char_out = chr(int(token))
        elif len(token) == 2:
            char_out = bytes.fromhex(token).decode("utf-8", errors="replace")
        else:
            char_out = token[0]
    except Exception:
        errors.append("unable to decode ASCII char")

    return result(
        standard_id=standard_id,
        reference=reference,
        magnitude=token,
        value=char_out,
        display=char_out,
        warnings=warnings,
        errors=errors,
    )


def encode_ascii_char(*, standard_id: str, value: Any, context: dict[str, Any] | None = None) -> MediationResult:
    _ = context
    token = str(value or "")
    if not token:
        return result(
            standard_id=standard_id,
            reference="",
            magnitude="",
            value="",
            display="",
        )
    char_value = token[0]
    return result(
        standard_id=standard_id,
        reference="",
        magnitude=str(ord(char_value)),
        value=char_value,
        display=char_value,
    )


def decode_text_bytes(*, standard_id: str, reference: str, magnitude: str, context: dict[str, Any] | None = None) -> MediationResult:
    ctx = dict(context or {})
    token = str(magnitude or "").strip().lower()
    warnings: list[str] = []
    errors: list[str] = []

    if token.endswith("00") and bool(ctx.get("allow_trailing_null", True)):
        token = token[:-2]

    value, warning = _decode_hex_text(token)
    if warning:
        warnings.append(warning)
    if not token and magnitude:
        errors.append("empty text-byte token after normalization")

    return result(
        standard_id=standard_id,
        reference=reference,
        magnitude=token,
        value=value,
        display=value,
        warnings=warnings,
        errors=errors,
    )


def encode_text_bytes(*, standard_id: str, value: Any, context: dict[str, Any] | None = None) -> MediationResult:
    ctx = dict(context or {})
    append_null = bool(ctx.get("append_null_terminator", False))
    text_value = str(value or "")
    encoded = _encode_hex_text(text_value, append_null_terminator=append_null)
    return result(
        standard_id=standard_id,
        reference="",
        magnitude=encoded,
        value=text_value,
        display=text_value,
    )
