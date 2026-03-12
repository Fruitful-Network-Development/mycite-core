from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable, TypedDict
import string


_COORD_SCALE = 10_000_000.0


class MediationResult(TypedDict):
    ok: bool
    standard_id: str
    reference: str
    magnitude: str
    value: Any
    display: str
    warnings: list[str]
    errors: list[str]


class ValidationResult(TypedDict):
    warnings: list[str]
    errors: list[str]


class MediationTypeSpec(TypedDict):
    standard_id: str
    aliases: list[str]
    matcher_rule: str
    matcher: Callable[[str], bool]
    decode: Callable[[str, str, str, dict[str, Any]], MediationResult]
    encode: Callable[[str, Any, dict[str, Any]], MediationResult]
    validate_magnitude: Callable[[str, dict[str, Any]], ValidationResult]
    validate_value: Callable[[Any, dict[str, Any]], ValidationResult]
    render_hint: str


def _result(
    *,
    standard_id: str,
    reference: str,
    magnitude: str,
    value: Any,
    display: str,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> MediationResult:
    warnings_out = list(warnings or [])
    errors_out = list(errors or [])
    return {
        "ok": not errors_out,
        "standard_id": str(standard_id or "").strip().lower(),
        "reference": str(reference or "").strip(),
        "magnitude": str(magnitude or "").strip(),
        "value": value,
        "display": str(display or ""),
        "warnings": warnings_out,
        "errors": errors_out,
    }


def normalize_standard_id(value: str) -> str:
    return str(value or "").strip().lower()


def _validate_ok() -> ValidationResult:
    return {"warnings": [], "errors": []}


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
    encoded = str(raw or "").encode("utf-8").hex()
    if append_null_terminator:
        encoded += "00"
    return encoded


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
        try:
            label_bytes = label.encode("ascii", errors="strict")
        except Exception:
            errors.append("dns wire labels must be ASCII")
            break
        if len(label_bytes) > 63:
            errors.append("dns wire label exceeds 63 bytes")
            break
        encoded.append(len(label_bytes))
        encoded.extend(label_bytes)
    encoded.append(0)

    if len(encoded) > 255:
        errors.append("dns wire format exceeds 255 bytes")

    return encoded.hex(), warnings, errors


def _signed_axis_value(raw: int, axis_bits: int) -> int:
    sign = 1 << (axis_bits - 1)
    if raw & sign:
        return raw - (1 << axis_bits)
    return raw


def _decode_fixed_hex_coordinate(raw_value: str) -> dict[str, Any] | None:
    token = str(raw_value or "").strip()
    if token.lower().startswith("0x"):
        token = token[2:]
    token = token.replace("_", "").strip()
    if not token or (len(token) % 2) != 0:
        return None
    if any(ch not in string.hexdigits for ch in token):
        return None

    half = len(token) // 2
    if half < 1:
        return None
    row_hex = token[:half].upper()
    col_hex = token[half:].upper()
    axis_bits = half * 4
    row_value = int(row_hex, 16)
    col_value = int(col_hex, 16)
    longitude_signed = _signed_axis_value(row_value, axis_bits)
    latitude_signed = _signed_axis_value(col_value, axis_bits)
    longitude = longitude_signed / _COORD_SCALE
    latitude = latitude_signed / _COORD_SCALE
    return {
        "normalized_hex": f"0x{token.upper()}",
        "axis_bits": axis_bits,
        "row": {"hex": f"0x{row_hex}", "value": row_value},
        "column": {"hex": f"0x{col_hex}", "value": col_value},
        "longitude": {"signed_value": longitude_signed, "value": longitude},
        "latitude": {"signed_value": latitude_signed, "value": latitude},
        "pair": [longitude, latitude],
    }


# boolean_ref

def _boolean_matcher(token: str) -> bool:
    return token in {"boolean", "boolean_ref"}


def _validate_boolean_magnitude(magnitude: str, context: dict[str, Any]) -> ValidationResult:
    _ = context
    token = str(magnitude or "").strip().lower()
    if token in {"", "0", "false", "no", "off", "n", "1", "true", "yes", "on", "y"}:
        return _validate_ok()
    try:
        int(token)
        return _validate_ok()
    except Exception:
        return {"warnings": ["boolean magnitude uses non-standard token"], "errors": []}


def _validate_boolean_value(value: Any, context: dict[str, Any]) -> ValidationResult:
    _ = context
    if isinstance(value, bool):
        return _validate_ok()
    return {"warnings": ["boolean encode received non-bool value"], "errors": []}


def _decode_boolean(standard_id: str, reference: str, magnitude: str, context: dict[str, Any]) -> MediationResult:
    _ = context
    raw = str(magnitude or "").strip().lower()
    if raw in {"", "0", "false", "no", "off", "n"}:
        value = False
    elif raw in {"1", "true", "yes", "on", "y"}:
        value = True
    else:
        try:
            value = int(raw) != 0
        except Exception:
            value = bool(raw)
    return _result(
        standard_id=standard_id,
        reference=reference,
        magnitude=("1" if value else "0"),
        value=value,
        display=("true" if value else "false"),
    )


def _encode_boolean(standard_id: str, value: Any, context: dict[str, Any]) -> MediationResult:
    return _decode_boolean(standard_id, "", str(value), context)


# char / ascii

def _ascii_matcher(token: str) -> bool:
    return token in {"char", "ascii", "ascii_char"}


def _validate_ascii_magnitude(magnitude: str, context: dict[str, Any]) -> ValidationResult:
    _ = context
    token = str(magnitude or "").strip()
    if not token:
        return _validate_ok()
    if token.isdigit() or len(token) <= 2:
        return _validate_ok()
    return {"warnings": ["ascii magnitude is interpreted using first character"], "errors": []}


def _validate_ascii_value(value: Any, context: dict[str, Any]) -> ValidationResult:
    _ = context
    token = str(value or "")
    if len(token) <= 1:
        return _validate_ok()
    return {"warnings": ["ascii encode uses only first character"], "errors": []}


def _decode_ascii(standard_id: str, reference: str, magnitude: str, context: dict[str, Any]) -> MediationResult:
    _ = context
    raw = str(magnitude or "").strip()
    warnings: list[str] = []
    errors: list[str] = []
    if not raw:
        return _result(standard_id=standard_id, reference=reference, magnitude="", value="", display="")
    try:
        if raw.isdigit():
            char_out = chr(int(raw))
        elif len(raw) == 2:
            char_out = bytes.fromhex(raw).decode("utf-8", errors="replace")
        else:
            char_out = raw[0]
    except Exception:
        char_out = ""
        errors.append("unable to decode ASCII char")
    return _result(
        standard_id=standard_id,
        reference=reference,
        magnitude=raw,
        value=char_out,
        display=char_out,
        warnings=warnings,
        errors=errors,
    )


def _encode_ascii(standard_id: str, value: Any, context: dict[str, Any]) -> MediationResult:
    _ = context
    text = str(value or "")
    char_value = text[0] if text else ""
    magnitude = str(ord(char_value)) if char_value else ""
    return _result(
        standard_id=standard_id,
        reference="",
        magnitude=magnitude,
        value=char_value,
        display=char_value,
    )


# text byte formats

def _text_byte_matcher(token: str) -> bool:
    return token in {"text_byte_format", "text_byte_email_format"}


def _validate_text_byte_magnitude(magnitude: str, context: dict[str, Any]) -> ValidationResult:
    _ = context
    token = str(magnitude or "").strip().lower()
    if not token:
        return _validate_ok()
    if len(token) % 2 != 0:
        return {"warnings": [], "errors": ["text byte magnitude has odd hex length"]}
    if any(ch not in string.hexdigits for ch in token):
        return {"warnings": [], "errors": ["text byte magnitude must be hex"]}
    return _validate_ok()


def _validate_text_byte_value(value: Any, context: dict[str, Any]) -> ValidationResult:
    _ = context
    if isinstance(value, (str, bytes, bytearray)):
        return _validate_ok()
    return {"warnings": ["text byte encode coerces value to string"], "errors": []}


def _decode_text_bytes(standard_id: str, reference: str, magnitude: str, context: dict[str, Any]) -> MediationResult:
    ctx = dict(context or {})
    raw = str(magnitude or "").strip().lower()
    warnings: list[str] = []
    if raw.endswith("00") and bool(ctx.get("allow_trailing_null", True)):
        raw = raw[:-2]
    value, warning = _decode_hex_text(raw)
    if warning:
        warnings.append(warning)
    return _result(
        standard_id=standard_id,
        reference=reference,
        magnitude=raw,
        value=value,
        display=value,
        warnings=warnings,
    )


def _encode_text_bytes(standard_id: str, value: Any, context: dict[str, Any]) -> MediationResult:
    ctx = dict(context or {})
    append_null = bool(ctx.get("append_null_terminator", False))
    text_value = str(value or "")
    encoded = _encode_hex_text(text_value, append_null_terminator=append_null)
    return _result(
        standard_id=standard_id,
        reference="",
        magnitude=encoded,
        value=text_value,
        display=text_value,
    )


# dns

def _dns_matcher(token: str) -> bool:
    return token == "dns_wire_format"


def _validate_dns_magnitude(magnitude: str, context: dict[str, Any]) -> ValidationResult:
    _ = context
    _, _, errors = _decode_dns_wire(magnitude)
    return {"warnings": [], "errors": errors}


def _validate_dns_value(value: Any, context: dict[str, Any]) -> ValidationResult:
    _ = context
    encoded, warnings, errors = _encode_dns_wire(str(value or ""))
    _ = encoded
    return {"warnings": warnings, "errors": errors}


def _decode_dns(standard_id: str, reference: str, magnitude: str, context: dict[str, Any]) -> MediationResult:
    _ = context
    domain, warnings, errors = _decode_dns_wire(magnitude)
    return _result(
        standard_id=standard_id,
        reference=reference,
        magnitude=str(magnitude or "").strip().lower(),
        value=domain,
        display=domain,
        warnings=warnings,
        errors=errors,
    )


def _encode_dns(standard_id: str, value: Any, context: dict[str, Any]) -> MediationResult:
    _ = context
    encoded, warnings, errors = _encode_dns_wire(str(value or ""))
    display = str(value or "").strip().strip(".")
    return _result(
        standard_id=standard_id,
        reference="",
        magnitude=encoded,
        value=display,
        display=display,
        warnings=warnings,
        errors=errors,
    )


# timestamp

def _timestamp_matcher(token: str) -> bool:
    return token == "timestamp_unix_s"


def _validate_timestamp_magnitude(magnitude: str, context: dict[str, Any]) -> ValidationResult:
    _ = context
    try:
        if int(str(magnitude or "0").strip()) < 0:
            return {"warnings": [], "errors": ["timestamp must be >= 0"]}
        return _validate_ok()
    except Exception:
        return {"warnings": [], "errors": ["invalid unix timestamp"]}


def _validate_timestamp_value(value: Any, context: dict[str, Any]) -> ValidationResult:
    _ = context
    if isinstance(value, (int, float)):
        return _validate_ok()
    raw = str(value or "").strip()
    if not raw:
        return {"warnings": [], "errors": ["timestamp value is empty"]}
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        datetime.fromisoformat(raw)
        return _validate_ok()
    except Exception:
        try:
            int(raw)
            return _validate_ok()
        except Exception:
            return {"warnings": [], "errors": ["invalid timestamp value"]}


def _decode_timestamp(standard_id: str, reference: str, magnitude: str, context: dict[str, Any]) -> MediationResult:
    _ = context
    errors: list[str] = []
    try:
        unix_s = int(str(magnitude or "0").strip())
        if unix_s < 0:
            errors.append("timestamp must be >= 0")
            unix_s = 0
    except Exception:
        unix_s = 0
        errors.append("invalid unix timestamp")
    iso = datetime.fromtimestamp(unix_s, tz=UTC).isoformat().replace("+00:00", "Z")
    return _result(
        standard_id=standard_id,
        reference=reference,
        magnitude=str(unix_s),
        value=unix_s,
        display=iso,
        errors=errors,
    )


def _encode_timestamp(standard_id: str, value: Any, context: dict[str, Any]) -> MediationResult:
    token = str(value or "").strip()
    if isinstance(value, (int, float)):
        token = str(int(value))
    return _decode_timestamp(standard_id, "", token, context)


# duration

def _duration_matcher(token: str) -> bool:
    return token in {"time_span_s", "duration_s"}


def _validate_duration_magnitude(magnitude: str, context: dict[str, Any]) -> ValidationResult:
    _ = context
    try:
        seconds = int(str(magnitude or "0").strip())
    except Exception:
        return {"warnings": [], "errors": ["invalid duration"]}
    if seconds < 0:
        return {"warnings": [], "errors": ["duration must be >= 0"]}
    return _validate_ok()


def _validate_duration_value(value: Any, context: dict[str, Any]) -> ValidationResult:
    return _validate_duration_magnitude(str(value), context)


def _duration_display(seconds: int) -> str:
    display = f"{seconds}s"
    if seconds >= 60:
        minutes, sec = divmod(seconds, 60)
        display = f"{minutes}m {sec}s"
    if seconds >= 3600:
        hours, rem = divmod(seconds, 3600)
        minutes, sec = divmod(rem, 60)
        display = f"{hours}h {minutes}m {sec}s"
    return display


def _decode_duration(standard_id: str, reference: str, magnitude: str, context: dict[str, Any]) -> MediationResult:
    _ = context
    errors: list[str] = []
    try:
        seconds = int(str(magnitude or "0").strip())
    except Exception:
        seconds = 0
        errors.append("invalid duration")
    if seconds < 0:
        errors.append("duration must be >= 0")
        seconds = 0
    return _result(
        standard_id=standard_id,
        reference=reference,
        magnitude=str(seconds),
        value=seconds,
        display=_duration_display(seconds),
        errors=errors,
    )


def _encode_duration(standard_id: str, value: Any, context: dict[str, Any]) -> MediationResult:
    return _decode_duration(standard_id, "", str(value), context)


# length

def _length_matcher(token: str) -> bool:
    return token == "length_m"


def _validate_length_magnitude(magnitude: str, context: dict[str, Any]) -> ValidationResult:
    _ = context
    try:
        float(str(magnitude or "0").strip())
        return _validate_ok()
    except Exception:
        return {"warnings": [], "errors": ["invalid length value"]}


def _validate_length_value(value: Any, context: dict[str, Any]) -> ValidationResult:
    return _validate_length_magnitude(str(value), context)


def _decode_length(standard_id: str, reference: str, magnitude: str, context: dict[str, Any]) -> MediationResult:
    _ = context
    errors: list[str] = []
    try:
        value = float(str(magnitude or "0").strip())
    except Exception:
        value = 0.0
        errors.append("invalid length value")
    return _result(
        standard_id=standard_id,
        reference=reference,
        magnitude=f"{value}",
        value=value,
        display=f"{value:g} m",
        errors=errors,
    )


def _encode_length(standard_id: str, value: Any, context: dict[str, Any]) -> MediationResult:
    return _decode_length(standard_id, "", str(value), context)


# coordinates

def _coordinate_matcher(token: str) -> bool:
    return token in {"coordinate", "coordinate_fixed_hex"}


def _validate_coordinate_magnitude(magnitude: str, context: dict[str, Any]) -> ValidationResult:
    _ = context
    raw = str(magnitude or "").strip()
    if not raw:
        return _validate_ok()
    if "," in raw:
        parts = [part.strip() for part in raw.split(",")]
        if len(parts) != 2:
            return {"warnings": [], "errors": ["coordinate must be 'lat,lon'"]}
        try:
            float(parts[0])
            float(parts[1])
            return _validate_ok()
        except Exception:
            return {"warnings": [], "errors": ["invalid coordinate tuple"]}

    decoded = _decode_fixed_hex_coordinate(raw)
    if decoded is None:
        return {"warnings": [], "errors": ["invalid fixed-hex coordinate token"]}
    return {"warnings": ["coordinate interpreted as fixed-hex pair"], "errors": []}


def _validate_coordinate_value(value: Any, context: dict[str, Any]) -> ValidationResult:
    _ = context
    if isinstance(value, dict):
        if "lat" in value and "lon" in value:
            return _validate_ok()
        if "latitude" in value and "longitude" in value:
            return _validate_ok()
    return _validate_coordinate_magnitude(str(value), context)


def _decode_coordinate(standard_id: str, reference: str, magnitude: str, context: dict[str, Any]) -> MediationResult:
    _ = context
    errors: list[str] = []
    warnings: list[str] = []
    raw = str(magnitude or "").strip()

    if not raw:
        return _result(
            standard_id=standard_id,
            reference=reference,
            magnitude="",
            value={"lat": 0.0, "lon": 0.0},
            display="(0, 0)",
        )

    if "," in raw:
        parts = [part.strip() for part in raw.split(",")]
        lat = 0.0
        lon = 0.0
        if len(parts) == 2:
            try:
                lat = float(parts[0])
                lon = float(parts[1])
            except Exception:
                errors.append("invalid coordinate tuple")
        else:
            errors.append("coordinate must be 'lat,lon'")
        return _result(
            standard_id=standard_id,
            reference=reference,
            magnitude=f"{lat:g},{lon:g}",
            value={"lat": lat, "lon": lon},
            display=f"({lat:g}, {lon:g})",
            warnings=warnings,
            errors=errors,
        )

    decoded_fixed = _decode_fixed_hex_coordinate(raw)
    if decoded_fixed is None:
        errors.append("invalid fixed-hex coordinate token")
        return _result(
            standard_id=standard_id,
            reference=reference,
            magnitude=raw,
            value={"lat": 0.0, "lon": 0.0},
            display="(0, 0)",
            warnings=warnings,
            errors=errors,
        )

    longitude_value = float(decoded_fixed.get("longitude", {}).get("value") or 0.0)
    latitude_value = float(decoded_fixed.get("latitude", {}).get("value") or 0.0)
    warnings.append("coordinate decoded via fixed-width hex split")
    return _result(
        standard_id=standard_id,
        reference=reference,
        magnitude=str(decoded_fixed.get("normalized_hex") or raw),
        value={
            "lat": latitude_value,
            "lon": longitude_value,
            "encoding": "fixed_hex",
            "decoded": decoded_fixed,
        },
        display=f"({longitude_value:g}, {latitude_value:g})",
        warnings=warnings,
        errors=errors,
    )


def _encode_coordinate(standard_id: str, value: Any, context: dict[str, Any]) -> MediationResult:
    _ = context
    if isinstance(value, dict):
        if "lat" in value and "lon" in value:
            return _decode_coordinate(standard_id, "", f"{value.get('lat')},{value.get('lon')}", context)
        if "latitude" in value and "longitude" in value:
            return _decode_coordinate(
                standard_id,
                "",
                f"{value.get('latitude')},{value.get('longitude')}",
                context,
            )
    return _decode_coordinate(standard_id, "", str(value or ""), context)


def _register(spec: MediationTypeSpec) -> MediationTypeSpec:
    return spec


_MEDIATION_SPECS: list[MediationTypeSpec] = [
    _register(
        {
            "standard_id": "boolean_ref",
            "aliases": ["boolean"],
            "matcher_rule": "explicit standard id boolean_ref or boolean",
            "matcher": _boolean_matcher,
            "decode": _decode_boolean,
            "encode": _encode_boolean,
            "validate_magnitude": _validate_boolean_magnitude,
            "validate_value": _validate_boolean_value,
            "render_hint": "boolean_chip",
        }
    ),
    _register(
        {
            "standard_id": "ascii_char",
            "aliases": ["ascii", "char"],
            "matcher_rule": "explicit standard id ascii_char/ascii/char",
            "matcher": _ascii_matcher,
            "decode": _decode_ascii,
            "encode": _encode_ascii,
            "validate_magnitude": _validate_ascii_magnitude,
            "validate_value": _validate_ascii_value,
            "render_hint": "monospace_char",
        }
    ),
    _register(
        {
            "standard_id": "dns_wire_format",
            "aliases": [],
            "matcher_rule": "explicit standard id dns_wire_format",
            "matcher": _dns_matcher,
            "decode": _decode_dns,
            "encode": _encode_dns,
            "validate_magnitude": _validate_dns_magnitude,
            "validate_value": _validate_dns_value,
            "render_hint": "dns_domain",
        }
    ),
    _register(
        {
            "standard_id": "text_byte_format",
            "aliases": ["text_byte_email_format"],
            "matcher_rule": "explicit standard id text_byte_format/text_byte_email_format",
            "matcher": _text_byte_matcher,
            "decode": _decode_text_bytes,
            "encode": _encode_text_bytes,
            "validate_magnitude": _validate_text_byte_magnitude,
            "validate_value": _validate_text_byte_value,
            "render_hint": "text_preview",
        }
    ),
    _register(
        {
            "standard_id": "timestamp_unix_s",
            "aliases": [],
            "matcher_rule": "explicit standard id timestamp_unix_s",
            "matcher": _timestamp_matcher,
            "decode": _decode_timestamp,
            "encode": _encode_timestamp,
            "validate_magnitude": _validate_timestamp_magnitude,
            "validate_value": _validate_timestamp_value,
            "render_hint": "timestamp_iso8601",
        }
    ),
    _register(
        {
            "standard_id": "duration_s",
            "aliases": ["time_span_s"],
            "matcher_rule": "explicit standard id duration_s/time_span_s",
            "matcher": _duration_matcher,
            "decode": _decode_duration,
            "encode": _encode_duration,
            "validate_magnitude": _validate_duration_magnitude,
            "validate_value": _validate_duration_value,
            "render_hint": "duration_human",
        }
    ),
    _register(
        {
            "standard_id": "length_m",
            "aliases": [],
            "matcher_rule": "explicit standard id length_m",
            "matcher": _length_matcher,
            "decode": _decode_length,
            "encode": _encode_length,
            "validate_magnitude": _validate_length_magnitude,
            "validate_value": _validate_length_value,
            "render_hint": "metric_length",
        }
    ),
    _register(
        {
            "standard_id": "coordinate",
            "aliases": ["coordinate_fixed_hex"],
            "matcher_rule": "explicit standard id coordinate/coordinate_fixed_hex",
            "matcher": _coordinate_matcher,
            "decode": _decode_coordinate,
            "encode": _encode_coordinate,
            "validate_magnitude": _validate_coordinate_magnitude,
            "validate_value": _validate_coordinate_value,
            "render_hint": "coordinate_pair",
        }
    ),
]

_ENTRY_BY_STANDARD_ID: dict[str, MediationTypeSpec] = {}
for entry in _MEDIATION_SPECS:
    canonical = normalize_standard_id(str(entry.get("standard_id") or ""))
    if canonical:
        _ENTRY_BY_STANDARD_ID[canonical] = entry
    for alias in list(entry.get("aliases") or []):
        token = normalize_standard_id(alias)
        if token and token not in _ENTRY_BY_STANDARD_ID:
            _ENTRY_BY_STANDARD_ID[token] = entry


def resolve_entry(standard_id: str) -> MediationTypeSpec | None:
    token = normalize_standard_id(standard_id)
    if not token:
        return None
    direct = _ENTRY_BY_STANDARD_ID.get(token)
    if direct is not None:
        return direct
    for entry in _MEDIATION_SPECS:
        matcher = entry.get("matcher")
        if callable(matcher) and matcher(token):
            return entry
    return None


def list_registry_entries() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in _MEDIATION_SPECS:
        out.append(
            {
                "standard_id": str(entry.get("standard_id") or ""),
                "aliases": list(entry.get("aliases") or []),
                "matcher_rule": str(entry.get("matcher_rule") or ""),
                "render_hint": str(entry.get("render_hint") or ""),
            }
        )
    return out


def decode_value(
    *,
    standard_id: str,
    reference: str,
    magnitude: str,
    context: dict[str, Any] | None = None,
) -> MediationResult:
    ctx = dict(context or {})
    token = normalize_standard_id(standard_id)
    entry = resolve_entry(token)
    if entry is None:
        return _result(
            standard_id=token,
            reference=reference,
            magnitude=str(magnitude or "").strip(),
            value=str(magnitude or ""),
            display=str(magnitude or ""),
            warnings=[f"unknown standard_id: {token}" if token else "standard_id is empty"],
        )

    validation = entry["validate_magnitude"](str(magnitude or ""), ctx)
    decoded = entry["decode"](str(entry.get("standard_id") or token), reference, str(magnitude or ""), ctx)
    warnings = list(decoded.get("warnings") or []) + list(validation.get("warnings") or [])
    errors = list(decoded.get("errors") or []) + list(validation.get("errors") or [])
    decoded["warnings"] = warnings
    decoded["errors"] = errors
    decoded["ok"] = not errors
    return decoded


def encode_value(
    *,
    standard_id: str,
    value: Any,
    context: dict[str, Any] | None = None,
) -> MediationResult:
    ctx = dict(context or {})
    token = normalize_standard_id(standard_id)
    entry = resolve_entry(token)
    if entry is None:
        return _result(
            standard_id=token,
            reference="",
            magnitude=str(value or ""),
            value=value,
            display=str(value or ""),
            warnings=[f"unknown standard_id: {token}" if token else "standard_id is empty"],
        )

    validation = entry["validate_value"](value, ctx)
    encoded = entry["encode"](str(entry.get("standard_id") or token), value, ctx)
    warnings = list(encoded.get("warnings") or []) + list(validation.get("warnings") or [])
    errors = list(encoded.get("errors") or []) + list(validation.get("errors") or [])
    encoded["warnings"] = warnings
    encoded["errors"] = errors
    encoded["ok"] = not errors
    return encoded
