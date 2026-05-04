"""Portal shell state machine: reducer, canonicalization, and focus helpers."""

from __future__ import annotations

from typing import Any

from MyCiteV2.packages.modules.shared.scalars import as_text

from .shell_schemas import (
    FOCUS_LEVEL_DATUM,
    FOCUS_LEVEL_FILE,
    FOCUS_LEVEL_INDEX,
    FOCUS_LEVEL_OBJECT,
    FOCUS_LEVEL_SANDBOX,
    PORTAL_SCOPE_DEFAULT_ID,
    SYSTEM_ANCHOR_FILE_KEY,
    SYSTEM_ROOT_SURFACE_ID,
    SYSTEM_SANDBOX_QUERY_FILE_TOKEN,
    TRANSITION_BACK_OUT,
    TRANSITION_CLOSE_INTERFACE_PANEL,
    TRANSITION_ENTER_SURFACE,
    TRANSITION_FOCUS_DATUM,
    TRANSITION_FOCUS_FILE,
    TRANSITION_FOCUS_OBJECT,
    TRANSITION_OPEN_INTERFACE_PANEL,
    TRANSITION_SET_VERB,
    VERB_MEDIATE,
    VERB_NAVIGATE,
)
from .shell_state import (
    PortalFocusSegment,
    PortalScope,
    PortalShellChrome,
    PortalShellState,
    PortalShellTransition,
    _normalize_focus_path,
    _normalize_slug,
    _subject_from_segment,
)
from .shell_registry import (
    is_tool_surface,
    requires_shell_state_machine,
)


def default_focus_path(*, scope_id: str, include_anchor_file: bool) -> tuple[PortalFocusSegment, ...]:
    segments = [PortalFocusSegment(level=FOCUS_LEVEL_SANDBOX, id=scope_id or PORTAL_SCOPE_DEFAULT_ID)]
    if include_anchor_file:
        segments.append(PortalFocusSegment(level=FOCUS_LEVEL_FILE, id=SYSTEM_ANCHOR_FILE_KEY))
    return tuple(segments)


def initial_portal_shell_state(
    *,
    surface_id: str,
    portal_scope: PortalScope | dict[str, Any],
) -> PortalShellState:
    normalized_scope = portal_scope if isinstance(portal_scope, PortalScope) else PortalScope.from_value(portal_scope)
    focus_path = default_focus_path(
        scope_id=normalized_scope.scope_id,
        include_anchor_file=requires_shell_state_machine(surface_id),
    )
    base_state = PortalShellState(
        active_surface_id=surface_id,
        focus_path=focus_path,
        focus_subject=_subject_from_segment(focus_path[-1]),
        mediation_subject=None,
        verb=VERB_NAVIGATE,
        chrome=PortalShellChrome(control_panel_collapsed=False, interface_panel_open=False),
    )
    return canonicalize_portal_shell_state(
        base_state,
        active_surface_id=surface_id,
        portal_scope=normalized_scope,
        seed_anchor_file=True,
    )


def focus_level_for_shell_state(shell_state: PortalShellState | dict[str, Any] | None) -> str:
    if shell_state is None:
        return FOCUS_LEVEL_SANDBOX
    state = shell_state if isinstance(shell_state, PortalShellState) else PortalShellState.from_value(shell_state)
    return state.focus_path[-1].level if state.focus_path else FOCUS_LEVEL_SANDBOX


def segment_id_for_level(shell_state: PortalShellState | dict[str, Any] | None, *, level: str) -> str:
    if shell_state is None:
        return ""
    state = shell_state if isinstance(shell_state, PortalShellState) else PortalShellState.from_value(shell_state)
    for segment in state.focus_path:
        if segment.level == level:
            return segment.id
    return ""


def _focus_path_contains_subject(focus_path: tuple[PortalFocusSegment, ...], subject: dict[str, str] | None) -> bool:
    if not isinstance(subject, dict):
        return False
    subject_level = _normalize_slug(subject.get("level"))
    subject_id = as_text(subject.get("id"))
    if subject_level not in FOCUS_LEVEL_INDEX or not subject_id:
        return False
    for segment in focus_path:
        if segment.level == subject_level and segment.id == subject_id:
            return True
    return False


def _state_with(
    state: PortalShellState,
    *,
    active_surface_id: str | None = None,
    focus_path: tuple[PortalFocusSegment, ...] | None = None,
    focus_subject: dict[str, str] | None | object = ...,
    mediation_subject: dict[str, str] | None | object = ...,
    verb: str | None = None,
    chrome: PortalShellChrome | None = None,
) -> PortalShellState:
    next_focus_path = focus_path if focus_path is not None else state.focus_path
    next_focus_subject = state.focus_subject if focus_subject is ... else focus_subject
    next_mediation_subject = state.mediation_subject if mediation_subject is ... else mediation_subject
    return PortalShellState(
        active_surface_id=active_surface_id or state.active_surface_id,
        focus_path=next_focus_path,
        focus_subject=next_focus_subject,
        mediation_subject=next_mediation_subject,
        verb=verb or state.verb,
        chrome=chrome or state.chrome,
    )


def _subject_for_level(focus_path: tuple[PortalFocusSegment, ...], *, level: str) -> dict[str, str] | None:
    for segment in focus_path:
        if segment.level == level:
            return segment.to_dict()
    return None


def _with_focus_path(
    shell_state: PortalShellState,
    *,
    active_surface_id: str,
    portal_scope: PortalScope,
    focus_path: tuple[PortalFocusSegment, ...],
) -> PortalShellState:
    next_focus_subject = _subject_from_segment(focus_path[-1]) if focus_path else None
    next_mediation_subject = shell_state.mediation_subject
    if next_mediation_subject and not _focus_path_contains_subject(focus_path, next_mediation_subject):
        next_mediation_subject = None
    next_verb = shell_state.verb
    next_chrome = shell_state.chrome
    if active_surface_id == SYSTEM_ROOT_SURFACE_ID and next_mediation_subject is None and next_verb == VERB_MEDIATE:
        next_verb = VERB_NAVIGATE
        next_chrome = PortalShellChrome(
            control_panel_collapsed=shell_state.chrome.control_panel_collapsed,
            interface_panel_open=False,
        )
    return PortalShellState(
        active_surface_id=active_surface_id,
        focus_path=focus_path,
        focus_subject=next_focus_subject,
        mediation_subject=next_mediation_subject,
        verb=next_verb,
        chrome=next_chrome,
    )


def canonicalize_portal_shell_state(
    shell_state: PortalShellState | dict[str, Any] | None,
    *,
    active_surface_id: str,
    portal_scope: PortalScope,
    seed_anchor_file: bool,
) -> PortalShellState:
    state = PortalShellState.from_value(
        shell_state,
        portal_scope=portal_scope,
        fallback_surface_id=active_surface_id,
    )
    focus_path = _normalize_focus_path(state.focus_path, scope_id=portal_scope.scope_id)
    if seed_anchor_file and len(focus_path) == 1:
        focus_path = default_focus_path(scope_id=portal_scope.scope_id, include_anchor_file=True)
    focus_subject = _subject_from_segment(focus_path[-1])
    mediation_subject = state.mediation_subject if _focus_path_contains_subject(focus_path, state.mediation_subject) else None
    verb = state.verb
    chrome = state.chrome

    if is_tool_surface(active_surface_id):
        mediation_subject = mediation_subject or focus_subject
        verb = VERB_MEDIATE
        chrome = PortalShellChrome(
            control_panel_collapsed=chrome.control_panel_collapsed,
            interface_panel_open=True,
        )
    elif active_surface_id == SYSTEM_ROOT_SURFACE_ID:
        if verb == VERB_MEDIATE:
            if mediation_subject is None:
                verb = VERB_NAVIGATE
                chrome = PortalShellChrome(
                    control_panel_collapsed=chrome.control_panel_collapsed,
                    interface_panel_open=False,
                )
            else:
                chrome = PortalShellChrome(
                    control_panel_collapsed=chrome.control_panel_collapsed,
                    interface_panel_open=True,
                )
        else:
            mediation_subject = None
            chrome = PortalShellChrome(
                control_panel_collapsed=chrome.control_panel_collapsed,
                interface_panel_open=False,
            )

    return PortalShellState(
        active_surface_id=active_surface_id,
        focus_path=focus_path,
        focus_subject=focus_subject,
        mediation_subject=mediation_subject,
        verb=verb,
        chrome=chrome,
    )


def reduce_portal_shell_state(
    *,
    active_surface_id: str,
    portal_scope: PortalScope | dict[str, Any],
    current_state: PortalShellState | dict[str, Any] | None,
    transition: PortalShellTransition | dict[str, Any] | None,
    seed_anchor_file: bool,
) -> PortalShellState:
    normalized_scope = portal_scope if isinstance(portal_scope, PortalScope) else PortalScope.from_value(portal_scope)
    state = canonicalize_portal_shell_state(
        current_state,
        active_surface_id=active_surface_id,
        portal_scope=normalized_scope,
        seed_anchor_file=seed_anchor_file,
    )
    normalized_transition = PortalShellTransition.from_value(transition)
    if normalized_transition is None:
        return canonicalize_portal_shell_state(
            state,
            active_surface_id=active_surface_id,
            portal_scope=normalized_scope,
            seed_anchor_file=seed_anchor_file,
        )

    focus_path = list(state.focus_path)
    verb = state.verb
    mediation_subject = state.mediation_subject
    chrome = state.chrome

    if normalized_transition.kind == TRANSITION_ENTER_SURFACE:
        return canonicalize_portal_shell_state(
            state,
            active_surface_id=active_surface_id,
            portal_scope=normalized_scope,
            seed_anchor_file=seed_anchor_file,
        )

    if normalized_transition.kind == TRANSITION_FOCUS_FILE:
        next_file_key = as_text(normalized_transition.file_key)
        if next_file_key == SYSTEM_SANDBOX_QUERY_FILE_TOKEN:
            focus_path = [PortalFocusSegment(level=FOCUS_LEVEL_SANDBOX, id=normalized_scope.scope_id)]
        else:
            if not next_file_key:
                next_file_key = SYSTEM_ANCHOR_FILE_KEY
            focus_path = [
                PortalFocusSegment(level=FOCUS_LEVEL_SANDBOX, id=normalized_scope.scope_id),
                PortalFocusSegment(level=FOCUS_LEVEL_FILE, id=next_file_key),
            ]
    elif normalized_transition.kind == TRANSITION_FOCUS_DATUM:
        file_key = normalized_transition.file_key or segment_id_for_level(state, level=FOCUS_LEVEL_FILE) or SYSTEM_ANCHOR_FILE_KEY
        focus_path = [
            PortalFocusSegment(level=FOCUS_LEVEL_SANDBOX, id=normalized_scope.scope_id),
            PortalFocusSegment(level=FOCUS_LEVEL_FILE, id=file_key),
        ]
        if normalized_transition.datum_id:
            focus_path.append(PortalFocusSegment(level=FOCUS_LEVEL_DATUM, id=normalized_transition.datum_id))
    elif normalized_transition.kind == TRANSITION_FOCUS_OBJECT:
        file_key = normalized_transition.file_key or segment_id_for_level(state, level=FOCUS_LEVEL_FILE) or SYSTEM_ANCHOR_FILE_KEY
        datum_id = normalized_transition.datum_id or segment_id_for_level(state, level=FOCUS_LEVEL_DATUM)
        focus_path = [
            PortalFocusSegment(level=FOCUS_LEVEL_SANDBOX, id=normalized_scope.scope_id),
            PortalFocusSegment(level=FOCUS_LEVEL_FILE, id=file_key),
        ]
        if datum_id:
            focus_path.append(PortalFocusSegment(level=FOCUS_LEVEL_DATUM, id=datum_id))
        if normalized_transition.object_id:
            focus_path.append(PortalFocusSegment(level=FOCUS_LEVEL_OBJECT, id=normalized_transition.object_id))
    elif normalized_transition.kind == TRANSITION_BACK_OUT:
        if len(focus_path) > 1:
            focus_path = focus_path[:-1]
        else:
            focus_path = focus_path[:]
    elif normalized_transition.kind == TRANSITION_SET_VERB:
        verb = normalized_transition.verb or VERB_NAVIGATE
        if verb == VERB_MEDIATE:
            mediation_subject = _subject_from_segment(focus_path[-1])
            chrome = PortalShellChrome(
                control_panel_collapsed=chrome.control_panel_collapsed,
                interface_panel_open=True,
            )
        else:
            mediation_subject = None
            chrome = PortalShellChrome(
                control_panel_collapsed=chrome.control_panel_collapsed,
                interface_panel_open=False,
            )
    elif normalized_transition.kind == TRANSITION_OPEN_INTERFACE_PANEL:
        if active_surface_id == SYSTEM_ROOT_SURFACE_ID:
            mediation_subject = _subject_from_segment(focus_path[-1])
            verb = VERB_MEDIATE
        chrome = PortalShellChrome(
            control_panel_collapsed=chrome.control_panel_collapsed,
            interface_panel_open=True,
        )
    elif normalized_transition.kind == TRANSITION_CLOSE_INTERFACE_PANEL:
        if active_surface_id == SYSTEM_ROOT_SURFACE_ID:
            mediation_subject = None
            verb = VERB_NAVIGATE
            chrome = PortalShellChrome(
                control_panel_collapsed=chrome.control_panel_collapsed,
                interface_panel_open=False,
            )

    next_state = PortalShellState(
        active_surface_id=active_surface_id,
        focus_path=tuple(focus_path),
        focus_subject=_subject_from_segment(focus_path[-1]) if focus_path else _subject_for_level(tuple(focus_path), level=FOCUS_LEVEL_SANDBOX),
        mediation_subject=mediation_subject,
        verb=verb,
        chrome=chrome,
    )
    return canonicalize_portal_shell_state(
        next_state,
        active_surface_id=active_surface_id,
        portal_scope=normalized_scope,
        seed_anchor_file=seed_anchor_file,
    )


__all__ = [
    "canonicalize_portal_shell_state",
    "default_focus_path",
    "focus_level_for_shell_state",
    "initial_portal_shell_state",
    "reduce_portal_shell_state",
    "segment_id_for_level",
]
