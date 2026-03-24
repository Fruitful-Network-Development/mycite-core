from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


_ALLOWED_SOURCES = {"anthology", "samras", "auto"}
_ALLOWED_MODES = {"general", "inspect", "raw", "inferred"}
_AITAS_FIELDS = ("attention", "intention", "temporal", "archetype", "spatial")
_AITAS_LEGACY_FIELDS = ("spacial",)
_ALLOWED_AITAS_PHASES = {"navigate", "focus", "investigate", "mediate"}


def normalize_aitas_context(payload: dict[str, Any] | None) -> dict[str, str]:
    data = payload if isinstance(payload, dict) else {}
    out: dict[str, str] = {}
    for key in _AITAS_FIELDS:
        if key == "spatial":
            out[key] = str(data.get("spatial") or data.get("spacial") or "").strip()
            continue
        out[key] = str(data.get(key) or "").strip()
    return out


def serialize_aitas_context(payload: dict[str, Any] | None) -> dict[str, str]:
    out = normalize_aitas_context(payload)
    # Compatibility projection for older clients that still read the typo'd key.
    for key in _AITAS_LEGACY_FIELDS:
        if key == "spacial":
            out[key] = out.get("spatial", "")
    return out


def normalize_aitas_phase(token: str, default: str = "navigate") -> str:
    value = str(token or "").strip().lower()
    return value if value in _ALLOWED_AITAS_PHASES else default


def normalize_source(token: str, default: str = "auto") -> str:
    value = str(token or "").strip().lower()
    return value if value in _ALLOWED_SOURCES else default


def normalize_mode(token: str, default: str = "general") -> str:
    value = str(token or "").strip().lower()
    return value if value in _ALLOWED_MODES else default


@dataclass
class DataViewState:
    focus_source: str = "auto"
    focus_subject: str = ""
    left_pane: dict[str, Any] = field(default_factory=lambda: {"kind": "empty", "payload": {}})
    right_pane: dict[str, Any] = field(default_factory=lambda: {"kind": "empty", "payload": {}})
    mode: str = "general"
    lens_context: dict[str, Any] = field(default_factory=lambda: {"default": "default", "overrides": {}})
    staged_edits: dict[str, dict[str, str]] = field(default_factory=dict)
    staged_presentation_edits: dict[str, dict[str, str]] = field(default_factory=lambda: {"datum_icons": {}})
    validation_errors: list[str] = field(default_factory=list)
    selection: dict[str, Any] = field(default_factory=dict)
    aitas_context: dict[str, str] = field(default_factory=lambda: normalize_aitas_context({}))
    aitas_phase: str = "navigate"

    def to_dict(self) -> dict[str, Any]:
        staged_presentation = (
            dict(self.staged_presentation_edits)
            if isinstance(self.staged_presentation_edits, dict)
            else {"datum_icons": {}}
        )
        if not isinstance(staged_presentation.get("datum_icons"), dict):
            staged_presentation["datum_icons"] = {}

        return {
            "focus_source": normalize_source(self.focus_source),
            "focus_subject": str(self.focus_subject or ""),
            "left_pane": dict(self.left_pane or {"kind": "empty", "payload": {}}),
            "right_pane": dict(self.right_pane or {"kind": "empty", "payload": {}}),
            "mode": normalize_mode(self.mode),
            "lens_context": {
                "default": str((self.lens_context or {}).get("default") or "default").strip().lower() or "default",
                "overrides": dict((self.lens_context or {}).get("overrides") or {}),
            },
            "staged_edits": dict(self.staged_edits or {}),
            "staged_presentation_edits": staged_presentation,
            "validation_errors": list(self.validation_errors or []),
            "selection": dict(self.selection or {}),
            "aitas_context": serialize_aitas_context(self.aitas_context),
            "aitas_phase": normalize_aitas_phase(self.aitas_phase),
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
        *,
        default_focus_source: str = "auto",
        default_mode: str = "general",
        default_lens: str = "default",
    ) -> "DataViewState":
        data = payload if isinstance(payload, dict) else {}
        lens_context = data.get("lens_context") if isinstance(data.get("lens_context"), dict) else {}
        staged_presentation = (
            data.get("staged_presentation_edits")
            if isinstance(data.get("staged_presentation_edits"), dict)
            else {"datum_icons": {}}
        )
        if not isinstance(staged_presentation.get("datum_icons"), dict):
            staged_presentation["datum_icons"] = {}

        return cls(
            focus_source=normalize_source(str(data.get("focus_source") or default_focus_source), normalize_source(default_focus_source)),
            focus_subject=str(data.get("focus_subject") or ""),
            left_pane=dict(data.get("left_pane") or {"kind": "empty", "payload": {}}),
            right_pane=dict(data.get("right_pane") or {"kind": "empty", "payload": {}}),
            mode=normalize_mode(str(data.get("mode") or default_mode), normalize_mode(default_mode)),
            lens_context={
                "default": str(lens_context.get("default") or default_lens).strip().lower() or "default",
                "overrides": dict(lens_context.get("overrides") or {}),
            },
            staged_edits=dict(data.get("staged_edits") or {}),
            staged_presentation_edits=dict(staged_presentation),
            validation_errors=list(data.get("validation_errors") or []),
            selection=dict(data.get("selection") or {}),
            aitas_context=normalize_aitas_context(data.get("aitas_context") if isinstance(data.get("aitas_context"), dict) else {}),
            aitas_phase=normalize_aitas_phase(str(data.get("aitas_phase") or "navigate")),
        )
