from __future__ import annotations

from typing import Any


SHELL_VERB_ORDER = ("navigate", "investigate", "mediate", "manipulate")
SELECTION_CONTEXT_SCHEMA = "mycite.shell.selected_context.v1"
CONFIG_CONTEXT_SCHEMA = "mycite.shell.config_context.v1"
TOOL_CAPABILITY_SCHEMA = "mycite.shell.tool_capability.v1"
INSPECTOR_CARD_SCHEMA = "mycite.shell.inspector_card.v1"


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
