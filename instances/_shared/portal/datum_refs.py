from __future__ import annotations

import re
from dataclasses import dataclass

_DATUM_ADDRESS_RE = re.compile(r"^[0-9]+-[0-9]+-[0-9]+$")
_NUMERIC_HYPHEN_RE = re.compile(r"^[0-9]+(?:-[0-9]+)+$")


def _as_text(value: object) -> str:
    return str(value or "").strip()


def _is_numeric_hyphen_token(token: str) -> bool:
    return bool(_NUMERIC_HYPHEN_RE.fullmatch(_as_text(token)))


def _qualified_tail_identifier(token: str) -> str:
    parts = _as_text(token).split("-")
    if len(parts) < 4 or not all(part.isdigit() for part in parts):
        return ""
    return "-".join(parts[-3:])


def _validate_msn_id(msn_id: str, *, field_name: str = "msn_id") -> str:
    token = _as_text(msn_id)
    if not _is_numeric_hyphen_token(token):
        raise ValueError(f"{field_name} must be a numeric hyphen token")
    return token


@dataclass(frozen=True)
class ParsedDatumRef:
    raw: str
    datum_address: str
    msn_id: str
    source_format: str  # local | qualified_hyphen | qualified_dot

    @property
    def qualified(self) -> bool:
        return bool(self.msn_id)

    @property
    def canonical_dot(self) -> str:
        if not self.msn_id:
            return self.datum_address
        return f"{self.msn_id}.{self.datum_address}"

    @property
    def canonical_hyphen(self) -> str:
        if not self.msn_id:
            return self.datum_address
        return f"{self.msn_id}-{self.datum_address}"

    @property
    def legacy_hyphen_source(self) -> str:
        return self.raw if self.source_format == "qualified_hyphen" else ""


def parse_datum_ref(value: object, *, field_name: str = "datum_ref") -> ParsedDatumRef:
    token = _as_text(value)
    if not token:
        raise ValueError(f"{field_name} is required")

    if _DATUM_ADDRESS_RE.fullmatch(token):
        return ParsedDatumRef(raw=token, datum_address=token, msn_id="", source_format="local")

    if "." in token:
        msn_id, datum_address = token.split(".", 1)
        msn_id = _as_text(msn_id)
        datum_address = _as_text(datum_address)
        if _DATUM_ADDRESS_RE.fullmatch(datum_address) and _is_numeric_hyphen_token(msn_id):
            return ParsedDatumRef(
                raw=token,
                datum_address=datum_address,
                msn_id=msn_id,
                source_format="qualified_dot",
            )

    if _is_numeric_hyphen_token(token):
        datum_address = _qualified_tail_identifier(token)
        if _DATUM_ADDRESS_RE.fullmatch(datum_address):
            msn_id = token[: -(len(datum_address) + 1)]
            if _is_numeric_hyphen_token(msn_id):
                return ParsedDatumRef(
                    raw=token,
                    datum_address=datum_address,
                    msn_id=msn_id,
                    source_format="qualified_hyphen",
                )

    raise ValueError(
        f"{field_name} must be <datum_address>, <msn_id>-<datum_address>, or <msn_id>.<datum_address>"
    )


def is_datum_ref(value: object) -> bool:
    try:
        parse_datum_ref(value)
        return True
    except Exception:
        return False


def normalize_datum_ref(
    value: object,
    *,
    local_msn_id: object = "",
    require_qualified: bool = False,
    write_format: str = "dot",
    field_name: str = "datum_ref",
) -> str:
    parsed = parse_datum_ref(value, field_name=field_name)

    msn_id = _as_text(parsed.msn_id)
    if not msn_id and require_qualified:
        msn_id = _validate_msn_id(local_msn_id, field_name=f"{field_name}.local_msn_id")
    elif not msn_id and _as_text(local_msn_id):
        msn_id = _validate_msn_id(local_msn_id, field_name=f"{field_name}.local_msn_id")

    target = _as_text(write_format).lower() or "dot"
    if target == "local":
        return parsed.datum_address
    if not msn_id:
        return parsed.datum_address
    if target == "dot":
        return f"{msn_id}.{parsed.datum_address}"
    if target == "hyphen":
        return f"{msn_id}-{parsed.datum_address}"
    raise ValueError("write_format must be one of: dot, hyphen, local")


def datum_identifier_candidates(value: object, *, local_msn_id: object = "") -> list[str]:
    parsed = parse_datum_ref(value, field_name="datum_ref")
    out = [parsed.datum_address]
    if parsed.qualified:
        out.append(parsed.canonical_hyphen)
        out.append(parsed.canonical_dot)
        return out

    local = _as_text(local_msn_id)
    if _is_numeric_hyphen_token(local):
        out.append(f"{local}-{parsed.datum_address}")
        out.append(f"{local}.{parsed.datum_address}")
    return out
