from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


class Lens(ABC):
    """Stateless codec overlay for display/canonical transforms."""

    lens_id = "lens"

    @abstractmethod
    def decode(self, canonical_value: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    def encode(self, display_value: Any) -> Any:
        raise NotImplementedError

    def validate_display(self, display_value: Any) -> tuple[str, ...]:
        del display_value
        return ()


class IdentityLens(Lens):
    lens_id = "identity"

    def decode(self, canonical_value: Any) -> Any:
        return canonical_value

    def encode(self, display_value: Any) -> Any:
        return display_value


class TrimmedStringLens(Lens):
    lens_id = "trimmed_string"

    def decode(self, canonical_value: Any) -> str:
        return _as_text(canonical_value)

    def encode(self, display_value: Any) -> str:
        return _as_text(display_value)


class SamrasTitleLens(TrimmedStringLens):
    lens_id = "samras_title"

    def encode(self, display_value: Any) -> str:
        return " ".join(_as_text(display_value).split()).upper()

    def validate_display(self, display_value: Any) -> tuple[str, ...]:
        value = self.encode(display_value)
        if not value:
            return ("title_required",)
        try:
            value.encode("ascii")
        except UnicodeEncodeError:
            return ("title_must_be_ascii",)
        return ()


class EmailAddressLens(TrimmedStringLens):
    lens_id = "email_address"

    def encode(self, display_value: Any) -> str:
        return _as_text(display_value).lower()

    def validate_display(self, display_value: Any) -> tuple[str, ...]:
        value = self.encode(display_value)
        if not value:
            return ("email_required",)
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            return ("email_invalid",)
        return ()


class SecretReferenceLens(TrimmedStringLens):
    lens_id = "secret_reference"

    def decode(self, canonical_value: Any) -> str:
        value = _as_text(canonical_value)
        return value if value else "not_configured"

    def encode(self, display_value: Any) -> str:
        return _as_text(display_value)

    def validate_display(self, display_value: Any) -> tuple[str, ...]:
        value = self.encode(display_value)
        if not value:
            return ("secret_reference_required",)
        if "password" in value.lower():
            return ("secret_reference_must_not_contain_secret_value",)
        return ()
