from __future__ import annotations

from dataclasses import dataclass

from .base import (
    BinaryTextLens,
    EmailAddressLens,
    IdentityLens,
    Lens,
    NumericHyphenLens,
    SamrasTitleLens,
    SecretReferenceLens,
    TrimmedStringLens,
)


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
        # Lens-id → lens, for resolving a hyphae-flag's bound lens_id. Covers the
        # full built-in surface so a flag can name any of them.
        self._by_lens_id = {
            lens.lens_id: lens
            for lens in (
                IdentityLens(),
                TrimmedStringLens(),
                NumericHyphenLens(),
                BinaryTextLens(),
                SamrasTitleLens(),
                EmailAddressLens(),
                SecretReferenceLens(),
            )
        }

    def lens_by_id(self, lens_id: object) -> Lens | None:
        return self._by_lens_id.get(_as_text(lens_id))

    def resolve(
        self,
        *,
        recognized_family: object = "",
        primary_value_kind: object = "",
        overlay_kind: object = "",
        flag_lens_id: object = "",
    ) -> LensResolution:
        # Highest precedence: a hyphae-flag explicitly bound a lens to this datum
        # (by its canonical hyphae value). Falls through to the family/value-kind
        # resolution below when unset or unknown — so an empty flag registry is
        # fully behavior-preserving.
        flag_lens_token = _as_text(flag_lens_id)
        if flag_lens_token:
            flag_lens = self._by_lens_id.get(flag_lens_token)
            if flag_lens is not None:
                return LensResolution(lens=flag_lens, matched_on="hyphae_flag", token=flag_lens_token)
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
    flag_lens_id: object = "",
) -> LensResolution:
    return DEFAULT_DATUM_LENS_REGISTRY.resolve(
        recognized_family=recognized_family,
        primary_value_kind=primary_value_kind,
        overlay_kind=overlay_kind,
        flag_lens_id=flag_lens_id,
    )


__all__ = ["DEFAULT_DATUM_LENS_REGISTRY", "DatumLensRegistry", "LensResolution", "resolve_datum_lens"]
