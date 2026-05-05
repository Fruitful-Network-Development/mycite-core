"""Portal shell request/response normalization, query canonicalization, and URL building."""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urlencode

from MyCiteV2.packages.core.network_root_surface_query import normalize_network_surface_query
from MyCiteV2.packages.state_machine.nimm import (
    NimmDirective,
    NimmDirectiveEnvelope,
    NimmTargetAddress,
)
from MyCiteV2.packages.modules.shared.scalars import as_text

from .shell_schemas import (
    AWS_CSM_TOOL_SURFACE_ID,
    FND_DCM_DEFAULT_SITE,
    FND_DCM_TOOL_SURFACE_ID,
    FOCUS_LEVEL_DATUM,
    FOCUS_LEVEL_FILE,
    FOCUS_LEVEL_OBJECT,
    FOCUS_LEVEL_SANDBOX,
    NETWORK_ROOT_SURFACE_ID,
    SYSTEM_ANCHOR_FILE_KEY,
    SYSTEM_ROOT_ROUTE,
    SYSTEM_ROOT_SURFACE_ID,
    SYSTEM_SANDBOX_QUERY_FILE_TOKEN,
    TRANSITION_ENTER_SURFACE,
    VERB_MEDIATE,
    VERB_NAVIGATE,
    WORKBENCH_UI_TOOL_SURFACE_ID,
)
from .shell_state import (
    PortalFocusSegment,
    PortalScope,
    PortalShellChrome,
    PortalShellRequest,
    PortalShellResolution,
    PortalShellState,
    PortalShellTransition,
    _normalize_slug,
    _normalize_surface_query,
    _subject_from_segment,
)
from .shell_registry import (
    build_portal_surface_catalog,
    canonical_route_for_surface,
    is_tool_surface,
    requires_shell_state_machine,
    resolve_portal_surface,
)
from .shell import (
    anchor_file_key_for_sandbox,
    canonicalize_portal_shell_state,
    initial_portal_shell_state,
    reduce_portal_shell_state,
    sandbox_id_for_surface,
    segment_id_for_level,
)


def canonical_query_for_shell_state(
    shell_state: PortalShellState | dict[str, Any] | None,
    *,
    surface_id: str,
) -> dict[str, str]:
    if not requires_shell_state_machine(surface_id):
        return {}
    state = shell_state if isinstance(shell_state, PortalShellState) else PortalShellState.from_value(shell_state)
    file_id = segment_id_for_level(state, level=FOCUS_LEVEL_FILE)
    query: dict[str, str] = {
        "file": file_id or SYSTEM_SANDBOX_QUERY_FILE_TOKEN,
        "verb": state.verb,
    }
    datum_id = segment_id_for_level(state, level=FOCUS_LEVEL_DATUM)
    object_id = segment_id_for_level(state, level=FOCUS_LEVEL_OBJECT)
    if datum_id:
        query["datum"] = datum_id
    if object_id:
        query["object"] = object_id
    return query


def canonical_query_for_surface_query(
    surface_query: Mapping[str, Any] | None,
    *,
    surface_id: str,
) -> dict[str, str]:
    if surface_id == NETWORK_ROOT_SURFACE_ID:
        if surface_query is not None and not isinstance(surface_query, Mapping):
            raise ValueError("portal_shell_request.surface_query must be a mapping or null")
        query, _ = normalize_network_surface_query(surface_query)
        return query
    normalized = _normalize_surface_query(
        surface_query,
        field_name="portal_shell_request.surface_query",
    )
    if surface_id == AWS_CSM_TOOL_SURFACE_ID:
        query = {"view": "domains"}
        if as_text(normalized.get("domain")):
            query["domain"] = as_text(normalized.get("domain")).lower()
        if as_text(normalized.get("profile")):
            query["profile"] = as_text(normalized.get("profile"))
        section = as_text(normalized.get("section")).lower()
        if section in {"users", "onboarding", "newsletter"}:
            query["section"] = section
        return query
    if surface_id == FND_DCM_TOOL_SURFACE_ID:
        view = as_text(normalized.get("view")).lower()
        if view not in {"overview", "pages", "collections", "issues"}:
            view = "overview"
        query = {
            "site": as_text(normalized.get("site")).lower() or FND_DCM_DEFAULT_SITE,
            "view": view,
        }
        if view == "pages" and as_text(normalized.get("page")):
            query["page"] = as_text(normalized.get("page"))
        if view == "collections" and as_text(normalized.get("collection")):
            query["collection"] = as_text(normalized.get("collection"))
        return query
    if surface_id == WORKBENCH_UI_TOOL_SURFACE_ID:
        query: dict[str, str] = {}
        document_id = as_text(normalized.get("document"))
        if document_id:
            query["document"] = document_id
        document_filter = as_text(normalized.get("document_filter"))
        if document_filter:
            query["document_filter"] = document_filter
        document_sort_key = as_text(normalized.get("document_sort")).lower()
        if document_sort_key in {"document_id", "document_name", "source_kind", "row_count", "version_hash"}:
            query["document_sort"] = document_sort_key
        document_sort_direction = as_text(normalized.get("document_dir")).lower()
        if document_sort_direction in {"asc", "desc"}:
            query["document_dir"] = document_sort_direction
        text_filter = as_text(normalized.get("filter"))
        if text_filter:
            query["filter"] = text_filter
        sort_key = as_text(normalized.get("sort")).lower()
        if sort_key in {
            "datum_address",
            "layer",
            "value_group",
            "iteration",
            "labels",
            "relation",
            "object_ref",
            "hyphae_hash",
        }:
            query["sort"] = sort_key
        sort_direction = as_text(normalized.get("dir")).lower()
        if sort_direction in {"asc", "desc"}:
            query["dir"] = sort_direction
        group_mode = as_text(normalized.get("group")).lower()
        if group_mode in {"flat", "layer", "layer_value_group", "layer_value_group_iteration"}:
            query["group"] = group_mode
        workbench_lens = as_text(normalized.get("workbench_lens")).lower()
        if workbench_lens in {"interpreted", "raw"}:
            query["workbench_lens"] = workbench_lens
        source_visibility = as_text(normalized.get("source")).lower()
        if source_visibility in {"show", "hide"}:
            query["source"] = source_visibility
        overlay = as_text(normalized.get("overlay")).lower()
        if overlay in {"show", "hide"}:
            query["overlay"] = overlay
        row_id = as_text(normalized.get("row"))
        if row_id:
            query["row"] = row_id
        return query
    return {}


def canonical_query_for_runtime_request_payload(
    request_payload: Mapping[str, Any] | None,
    *,
    surface_id: str,
    legacy_query_keys: tuple[str, ...] = (),
) -> dict[str, str]:
    payload = dict(request_payload or {})
    raw_surface_query = payload.get("surface_query")
    surface_query: Mapping[str, Any] | None
    if isinstance(raw_surface_query, Mapping):
        surface_query = raw_surface_query
    elif legacy_query_keys:
        legacy_surface_query: dict[str, Any] = {}
        for key in legacy_query_keys:
            token = as_text(payload.get(key))
            if token:
                legacy_surface_query[key] = token
        surface_query = legacy_surface_query
    else:
        surface_query = None
    return canonical_query_for_surface_query(
        surface_query,
        surface_id=surface_id,
    )


def _normalize_runtime_payload_schema(
    payload: Mapping[str, Any] | None,
    *,
    expected_schema: str,
) -> dict[str, Any]:
    normalized_payload = dict(payload or {})
    if normalized_payload.get("schema") in {None, ""}:
        normalized_payload = {"schema": expected_schema, **normalized_payload}
    if as_text(normalized_payload.get("schema")) != expected_schema:
        raise ValueError(f"request.schema must be {expected_schema}")
    return normalized_payload


def normalize_runtime_surface_request_payload(
    payload: Mapping[str, Any] | None,
    *,
    expected_schema: str,
    surface_id: str,
    legacy_query_keys: tuple[str, ...] = (),
) -> tuple[PortalScope, dict[str, Any], dict[str, str]]:
    normalized_payload = _normalize_runtime_payload_schema(payload, expected_schema=expected_schema)
    portal_scope = PortalScope.from_value(normalized_payload.get("portal_scope"))
    surface_query = canonical_query_for_runtime_request_payload(
        normalized_payload,
        surface_id=surface_id,
        legacy_query_keys=legacy_query_keys,
    )
    return portal_scope, normalized_payload, surface_query


def normalize_runtime_surface_action_request_payload(
    payload: Mapping[str, Any] | None,
    *,
    expected_schema: str,
    surface_id: str,
    legacy_query_keys: tuple[str, ...] = (),
) -> tuple[PortalScope, dict[str, Any], dict[str, str], dict[str, Any] | None, str, dict[str, Any]]:
    portal_scope, normalized_payload, surface_query = normalize_runtime_surface_request_payload(
        payload,
        expected_schema=expected_schema,
        surface_id=surface_id,
        legacy_query_keys=legacy_query_keys,
    )
    raw_shell_state = normalized_payload.get("shell_state")
    shell_state = dict(raw_shell_state) if isinstance(raw_shell_state, dict) else None
    action_kind = as_text(normalized_payload.get("action_kind"))
    raw_action_payload = normalized_payload.get("action_payload")
    action_payload = dict(raw_action_payload) if isinstance(raw_action_payload, Mapping) else {}
    return portal_scope, normalized_payload, surface_query, shell_state, action_kind, action_payload


def normalize_runtime_shell_surface_request_payload(
    payload: Mapping[str, Any] | None,
    *,
    expected_schema: str,
    surface_id: str,
) -> tuple[PortalScope, PortalShellState, dict[str, Any]]:
    normalized_payload = _normalize_runtime_payload_schema(payload, expected_schema=expected_schema)
    portal_scope = PortalScope.from_value(normalized_payload.get("portal_scope"))
    shell_state = canonicalize_portal_shell_state(
        normalized_payload.get("shell_state"),
        active_surface_id=surface_id,
        portal_scope=portal_scope,
        seed_anchor_file=normalized_payload.get("shell_state") is None,
    )
    return portal_scope, shell_state, normalized_payload


def normalize_runtime_shell_action_request_payload(
    payload: Mapping[str, Any] | None,
    *,
    expected_schema: str,
    surface_id: str,
) -> tuple[PortalScope, PortalShellState, dict[str, Any], str, dict[str, Any]]:
    portal_scope, shell_state, normalized_payload = normalize_runtime_shell_surface_request_payload(
        payload,
        expected_schema=expected_schema,
        surface_id=surface_id,
    )
    action_kind = as_text(normalized_payload.get("action_kind"))
    raw_action_payload = normalized_payload.get("action_payload")
    action_payload = dict(raw_action_payload) if isinstance(raw_action_payload, Mapping) else {}
    return portal_scope, shell_state, normalized_payload, action_kind, action_payload


def build_canonical_url(*, surface_id: str, query: Mapping[str, str] | None = None) -> str:
    route = canonical_route_for_surface(surface_id)
    filtered = {key: value for key, value in dict(query or {}).items() if as_text(value)}
    if not filtered:
        return route
    return f"{route}?{urlencode(filtered)}"


def build_portal_shell_state_from_query(
    *,
    surface_id: str,
    portal_scope: PortalScope,
    query: Mapping[str, Any] | None,
) -> PortalShellState | None:
    if not requires_shell_state_machine(surface_id):
        return None
    params = dict(query or {})
    file_token = as_text(params.get("file"))
    verb = _normalize_slug(params.get("verb")) or (VERB_MEDIATE if is_tool_surface(surface_id) else VERB_NAVIGATE)
    sandbox_id = sandbox_id_for_surface(surface_id)
    segments: list[PortalFocusSegment] = [PortalFocusSegment(level=FOCUS_LEVEL_SANDBOX, id=sandbox_id)]
    if file_token and file_token != SYSTEM_SANDBOX_QUERY_FILE_TOKEN:
        segments.append(PortalFocusSegment(level=FOCUS_LEVEL_FILE, id=file_token))
    elif not file_token:
        segments.append(PortalFocusSegment(level=FOCUS_LEVEL_FILE, id=anchor_file_key_for_sandbox(sandbox_id)))
    datum_id = as_text(params.get("datum"))
    object_id = as_text(params.get("object"))
    if datum_id:
        if len(segments) == 1:
            segments.append(PortalFocusSegment(level=FOCUS_LEVEL_FILE, id=anchor_file_key_for_sandbox(sandbox_id)))
        segments.append(PortalFocusSegment(level=FOCUS_LEVEL_DATUM, id=datum_id))
    if object_id:
        if not datum_id:
            return canonicalize_portal_shell_state(
                PortalShellState(
                    active_surface_id=surface_id,
                    focus_path=tuple(segments),
                    focus_subject=_subject_from_segment(segments[-1]),
                    mediation_subject=None,
                    verb=VERB_NAVIGATE,
                ),
                active_surface_id=surface_id,
                portal_scope=portal_scope,
                seed_anchor_file=True,
            )
        segments.append(PortalFocusSegment(level=FOCUS_LEVEL_OBJECT, id=object_id))
    base_state = PortalShellState(
        active_surface_id=surface_id,
        focus_path=tuple(segments),
        focus_subject=_subject_from_segment(segments[-1]),
        mediation_subject=_subject_from_segment(segments[-1]) if verb == VERB_MEDIATE else None,
        verb=verb,
        chrome=PortalShellChrome(interface_panel_open=verb == VERB_MEDIATE),
    )
    return canonicalize_portal_shell_state(
        base_state,
        active_surface_id=surface_id,
        portal_scope=portal_scope,
        seed_anchor_file=True,
    )


def build_portal_shell_request_payload(
    *,
    requested_surface_id: str,
    portal_scope: PortalScope | dict[str, Any] | None,
    shell_state: PortalShellState | dict[str, Any] | None = None,
    transition: PortalShellTransition | dict[str, Any] | None = None,
    nimm_envelope: NimmDirectiveEnvelope | dict[str, Any] | None = None,
    surface_query: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    scope = portal_scope if isinstance(portal_scope, PortalScope) else PortalScope.from_value(portal_scope)
    state = (
        shell_state
        if isinstance(shell_state, PortalShellState) or shell_state is None
        else PortalShellState.from_value(shell_state, portal_scope=scope, fallback_surface_id=requested_surface_id)
    )
    normalized_transition = (
        transition
        if isinstance(transition, PortalShellTransition) or transition is None
        else PortalShellTransition.from_value(transition)
    )
    normalized_nimm_envelope = (
        nimm_envelope
        if isinstance(nimm_envelope, NimmDirectiveEnvelope) or nimm_envelope is None
        else NimmDirectiveEnvelope.from_dict(nimm_envelope)
    )
    return PortalShellRequest(
        requested_surface_id=requested_surface_id,
        portal_scope=scope,
        shell_state=state,
        transition=normalized_transition,
        nimm_envelope=normalized_nimm_envelope,
        surface_query=_normalize_surface_query(
            surface_query,
            field_name="portal_shell_request.surface_query",
        ),
    ).to_dict()


def build_nimm_envelope_for_shell_state(
    *,
    shell_state: PortalShellState | dict[str, Any],
    target_authority: str,
    document_id: str = "",
    aitas_defaults: dict[str, Any] | None = None,
    aitas_overrides: dict[str, Any] | None = None,
) -> NimmDirectiveEnvelope:
    state = shell_state if isinstance(shell_state, PortalShellState) else PortalShellState.from_value(shell_state)
    focus_targets = [
        NimmTargetAddress(
            file_key=segment_id_for_level(state, level=FOCUS_LEVEL_FILE) or SYSTEM_SANDBOX_QUERY_FILE_TOKEN,
            datum_address=segment_id_for_level(state, level=FOCUS_LEVEL_DATUM),
            object_ref=segment_id_for_level(state, level=FOCUS_LEVEL_OBJECT),
        )
    ]
    directive = NimmDirective(
        verb=state.verb,
        target_authority=target_authority,
        document_id=document_id,
        targets=tuple(focus_targets),
        payload={"source": "portal_shell_state"},
    )
    return NimmDirectiveEnvelope.with_merged_aitas(
        directive=directive,
        defaults=aitas_defaults,
        overrides=aitas_overrides,
    )


def resolve_portal_shell_request(request: PortalShellRequest | dict[str, Any] | None) -> PortalShellResolution:
    normalized_request = request if isinstance(request, PortalShellRequest) else PortalShellRequest.from_dict(request)
    requested_surface_id = normalized_request.requested_surface_id
    surface_entry = resolve_portal_surface(requested_surface_id)
    if surface_entry is None or not surface_entry.launchable:
        fallback_state = initial_portal_shell_state(surface_id=SYSTEM_ROOT_SURFACE_ID, portal_scope=normalized_request.portal_scope)
        fallback_query = canonical_query_for_shell_state(fallback_state, surface_id=SYSTEM_ROOT_SURFACE_ID)
        return PortalShellResolution(
            requested_surface_id=requested_surface_id,
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            selection_status="unknown",
            allowed=False,
            reducer_owned=True,
            shell_state=fallback_state,
            canonical_route=SYSTEM_ROOT_ROUTE,
            canonical_query=fallback_query,
            canonical_url=build_canonical_url(surface_id=SYSTEM_ROOT_SURFACE_ID, query=fallback_query),
            reason_code="surface_unknown",
            reason_message=f"Surface is not approved: {requested_surface_id}",
        )

    reducer_owned = requires_shell_state_machine(surface_entry.surface_id)
    shell_state: PortalShellState | None
    if reducer_owned:
        shell_state = reduce_portal_shell_state(
            active_surface_id=surface_entry.surface_id,
            portal_scope=normalized_request.portal_scope,
            current_state=normalized_request.shell_state,
            transition=normalized_request.transition,
            seed_anchor_file=normalized_request.shell_state is None,
        )
        canonical_query = canonical_query_for_shell_state(shell_state, surface_id=surface_entry.surface_id)
    else:
        shell_state = normalized_request.shell_state if isinstance(normalized_request.shell_state, PortalShellState) else None
        canonical_query = canonical_query_for_surface_query(
            normalized_request.surface_query,
            surface_id=surface_entry.surface_id,
        )
    canonical_route = canonical_route_for_surface(surface_entry.surface_id)
    return PortalShellResolution(
        requested_surface_id=requested_surface_id,
        active_surface_id=surface_entry.surface_id,
        selection_status="available",
        allowed=True,
        reducer_owned=reducer_owned,
        shell_state=shell_state,
        canonical_route=canonical_route,
        canonical_query=canonical_query,
        canonical_url=build_canonical_url(surface_id=surface_entry.surface_id, query=canonical_query),
    )


def build_portal_activity_dispatch_bodies(
    *,
    portal_scope: PortalScope | dict[str, Any],
    shell_state: PortalShellState | dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    scope = portal_scope if isinstance(portal_scope, PortalScope) else PortalScope.from_value(portal_scope)
    bodies: dict[str, dict[str, Any]] = {}
    for entry in build_portal_surface_catalog():
        if not requires_shell_state_machine(entry.surface_id):
            continue
        bodies[entry.surface_id] = build_portal_shell_request_payload(
            requested_surface_id=entry.surface_id,
            portal_scope=scope,
            shell_state=shell_state,
            transition={"kind": TRANSITION_ENTER_SURFACE, "surface_id": entry.surface_id},
        )
    return bodies
