from __future__ import annotations

from typing import Any

from .actions import (
    SHELL_ACTION_FOCUS_SUBJECT,
    SHELL_ACTION_INVESTIGATE,
    SHELL_ACTION_MANIPULATE,
    SHELL_ACTION_MEDIATE,
    SHELL_ACTION_NAVIGATE,
    SHELL_ACTION_SET_LENS,
    build_shell_action,
)

SHELL_VERB_ORDER = ("navigate", "investigate", "mediate", "manipulate")
SELECTION_CONTEXT_SCHEMA = "mycite.shell.selected_context.v1"
CONFIG_CONTEXT_SCHEMA = "mycite.shell.config_context.v1"
TOOL_CAPABILITY_SCHEMA = "mycite.shell.tool_capability.v1"
INSPECTOR_CARD_SCHEMA = "mycite.shell.inspector_card.v1"
SHELL_CONTROL_SCHEMA = "mycite.shell.control.v1"


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalize_shell_verb(raw: object, default: str = "navigate") -> str:
    token = _text(raw).lower()
    return token if token in SHELL_VERB_ORDER else default


def resolve_shell_verb_from_payload(payload: Any, *, default: str = "navigate") -> str:
    body = payload if isinstance(payload, dict) else {}
    return normalize_shell_verb(
        body.get("shell_verb") or body.get("current_verb") or body.get("verb"),
        default=default,
    )


def build_shell_verbs_payload(active_verb: object = "navigate") -> list[dict[str, Any]]:
    active = normalize_shell_verb(active_verb)
    labels = {
        "navigate": "Navigate",
        "investigate": "Investigate",
        "mediate": "Mediate",
        "manipulate": "Manipulate",
    }
    summaries = {
        "navigate": "Trace family, scope, and neighboring records.",
        "investigate": "Inspect structure, lineage, and abstraction path.",
        "mediate": "Open compatible tools and mediation workspaces.",
        "manipulate": "Edit, stage, preview, and apply controlled changes.",
    }
    return [
        {
            "verb": verb,
            "label": labels.get(verb, verb.title()),
            "summary": summaries.get(verb, ""),
            "active": verb == active,
            "action": build_shell_action(
                {
                    "navigate": SHELL_ACTION_NAVIGATE,
                    "investigate": SHELL_ACTION_INVESTIGATE,
                    "mediate": SHELL_ACTION_MEDIATE,
                    "manipulate": SHELL_ACTION_MANIPULATE,
                }.get(verb, SHELL_ACTION_NAVIGATE),
                payload={"shell_verb": verb},
            ),
        }
        for verb in SHELL_VERB_ORDER
    ]


def build_inspector_card(
    *,
    card_id: str,
    title: str,
    body: dict[str, Any] | None = None,
    summary: str = "",
    kind: str = "metadata",
    status: str = "info",
) -> dict[str, Any]:
    return {
        "schema": INSPECTOR_CARD_SCHEMA,
        "card_id": _text(card_id),
        "title": _text(title),
        "summary": _text(summary),
        "kind": _text(kind) or "metadata",
        "status": _text(status) or "info",
        "body": dict(body) if isinstance(body, dict) else {},
    }


def build_shell_controls_payload(active_verb: object = "navigate", *, focus_subject: str = "") -> list[dict[str, Any]]:
    controls = []
    for item in build_shell_verbs_payload(active_verb):
        controls.append(
            {
                "schema": SHELL_CONTROL_SCHEMA,
                "control_id": f"verb:{item['verb']}",
                "kind": "verb_button",
                "label": item["label"],
                "summary": item["summary"],
                "active": bool(item["active"]),
                "action": dict(item["action"]),
            }
        )
    controls.append(
        {
            "schema": SHELL_CONTROL_SCHEMA,
            "control_id": "focus:subject",
            "kind": "focus_subject",
            "label": "Focus Subject",
            "summary": "Move shell attention to the active subject.",
            "active": bool(focus_subject),
            "action": build_shell_action(SHELL_ACTION_FOCUS_SUBJECT, payload={"focus_subject": _text(focus_subject)}),
        }
    )
    controls.append(
        {
            "schema": SHELL_CONTROL_SCHEMA,
            "control_id": "lens:set_default",
            "kind": "lens_selector",
            "label": "Apply Lens",
            "summary": "Dispatch a typed lens-selection action.",
            "active": False,
            "action": build_shell_action(SHELL_ACTION_SET_LENS, payload={"lens": "default"}),
        }
    )
    return controls
