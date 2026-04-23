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
