from __future__ import annotations

DEFAULT_SHELL_VERB = "navigate"
SUPPORTED_SHELL_VERBS = (DEFAULT_SHELL_VERB,)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_shell_verb(value: object, *, field_name: str = "shell_verb") -> str:
    token = _as_text(value).lower()
    if token not in SUPPORTED_SHELL_VERBS:
        supported = ", ".join(SUPPORTED_SHELL_VERBS)
        raise ValueError(f"{field_name} must be one of: {supported}")
    return token
