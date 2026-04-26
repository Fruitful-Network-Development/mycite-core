from __future__ import annotations

from dataclasses import dataclass

from .base import BinaryTextLens, IdentityLens, Lens, NumericHyphenLens, TrimmedStringLens


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


@dataclass(frozen=True)
class LensResolution:
    lens: Lens
    matched_on: str
    token: str

    @property
    def lens_id(self) -> str:
        return _as_text(getattr(self.lens, "lens_id", "")) or "identity"


class DatumLensRegistry:
    """Resolve a bounded presentation lens for recognized datum families/kinds."""

    def __init__(self) -> None:
        self._family_lenses = {
            "nominal_babelette": BinaryTextLens(),
            "network_babelette": BinaryTextLens(),
            "title_babelette": BinaryTextLens(),
            "samras": NumericHyphenLens(),
            "samras_babelette": NumericHyphenLens(),
            "hops": NumericHyphenLens(),
            "hops_babelette": NumericHyphenLens(),
        }
        self._value_kind_lenses = {
            "binary_string": BinaryTextLens(),
            "numeric_hyphen": NumericHyphenLens(),
            "literal_text": TrimmedStringLens(),
            "tuple": IdentityLens(),
            "unknown": IdentityLens(),
        }
        self._overlay_lenses = {
            "title_babelette": BinaryTextLens(),
            "binary_overlay": BinaryTextLens(),
        }
        self._default_lens = IdentityLens()

    def resolve(
        self,
        *,
        recognized_family: object = "",
        primary_value_kind: object = "",
        overlay_kind: object = "",
    ) -> LensResolution:
        family = _as_text(recognized_family).lower()
        if family in self._family_lenses:
            return LensResolution(lens=self._family_lenses[family], matched_on="family", token=family)
        overlay = _as_text(overlay_kind).lower()
        if overlay in self._overlay_lenses:
            return LensResolution(lens=self._overlay_lenses[overlay], matched_on="overlay", token=overlay)
        value_kind = _as_text(primary_value_kind).lower() or "unknown"
        if value_kind in self._value_kind_lenses:
            return LensResolution(lens=self._value_kind_lenses[value_kind], matched_on="value_kind", token=value_kind)
        return LensResolution(lens=self._default_lens, matched_on="fallback", token="identity")


DEFAULT_DATUM_LENS_REGISTRY = DatumLensRegistry()


def resolve_datum_lens(
    *,
    recognized_family: object = "",
    primary_value_kind: object = "",
    overlay_kind: object = "",
) -> LensResolution:
    return DEFAULT_DATUM_LENS_REGISTRY.resolve(
        recognized_family=recognized_family,
        primary_value_kind=primary_value_kind,
        overlay_kind=overlay_kind,
    )


__all__ = ["DatumLensRegistry", "DEFAULT_DATUM_LENS_REGISTRY", "LensResolution", "resolve_datum_lens"]
