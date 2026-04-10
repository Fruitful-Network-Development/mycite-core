from __future__ import annotations

from typing import Any

from .types import MediationResult, result


def _decode_dns_wire(raw_hex: str) -> tuple[str, list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    token = str(raw_hex or "").strip().lower()
    if not token:
        return "", warnings, errors
    if len(token) % 2 != 0:
        return "", warnings, ["dns wire hex token has odd length"]

    try:
        data = bytes.fromhex(token)
    except Exception:
        return "", warnings, ["invalid dns wire hex token"]

    labels: list[str] = []
    index = 0
    while index < len(data):
        length = data[index]
        index += 1
        if length == 0:
            break
        if index + length > len(data):
            errors.append("dns wire label length exceeds payload")
            break
        label_bytes = data[index : index + length]
        index += length
        try:
            labels.append(label_bytes.decode("ascii"))
        except Exception:
            labels.append(label_bytes.decode("ascii", errors="replace"))
            warnings.append("non-ascii label bytes replaced")

    if index < len(data):
        warnings.append("trailing bytes found after dns terminator")

    return ".".join(labels), warnings, errors


def _encode_dns_wire(domain: str) -> tuple[str, list[str], list[str]]:
    token = str(domain or "").strip().strip(".")
    warnings: list[str] = []
    errors: list[str] = []
    if not token:
        return "00", warnings, errors

    labels = [label for label in token.split(".") if label]
    encoded = bytearray()
    for label in labels:
        label_bytes = label.encode("ascii", errors="strict")
        if len(label_bytes) > 63:
            errors.append("dns wire label exceeds 63 bytes")
            break
        encoded.append(len(label_bytes))
        encoded.extend(label_bytes)
    encoded.append(0)

    if len(encoded) > 255:
        errors.append("dns wire format exceeds 255 bytes")

    return encoded.hex(), warnings, errors


def decode(*, standard_id: str, reference: str, magnitude: str, context: dict[str, Any] | None = None) -> MediationResult:
    _ = context
    domain, warnings, errors = _decode_dns_wire(magnitude)
    normalized = str(magnitude or "").strip().lower()
    return result(
        standard_id=standard_id,
        reference=reference,
        magnitude=normalized,
        value=domain,
        display=domain,
        warnings=warnings,
        errors=errors,
    )


def encode(*, standard_id: str, value: Any, context: dict[str, Any] | None = None) -> MediationResult:
    _ = context
    encoded, warnings, errors = _encode_dns_wire(str(value or ""))
    return result(
        standard_id=standard_id,
        reference="",
        magnitude=encoded,
        value=str(value or "").strip().strip("."),
        display=str(value or "").strip().strip("."),
        warnings=warnings,
        errors=errors,
    )
