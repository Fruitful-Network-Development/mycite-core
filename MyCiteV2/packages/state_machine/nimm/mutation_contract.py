from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .envelope import NimmDirectiveEnvelope

DEFAULT_MUTATION_ENDPOINTS = {
    "stage": "/portal/api/v2/mutations/stage",
    "validate": "/portal/api/v2/mutations/validate",
    "preview": "/portal/api/v2/mutations/preview",
    "apply": "/portal/api/v2/mutations/apply",
    "discard": "/portal/api/v2/mutations/discard",
}

DEFAULT_MUTATION_ACTIONS = ("stage", "validate", "preview", "apply", "discard")


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def mutation_action_endpoint(action: object) -> str:
    action_name = _as_text(action).lower()
    if action_name not in DEFAULT_MUTATION_ENDPOINTS:
        allowed = ", ".join(sorted(DEFAULT_MUTATION_ENDPOINTS))
        raise ValueError(f"mutation action must be one of: {allowed}")
    return DEFAULT_MUTATION_ENDPOINTS[action_name]


@dataclass(frozen=True)
class MutationContractResult:
    status: str
    message: str
    envelope: NimmDirectiveEnvelope | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": _as_text(self.status) or "accepted",
            "message": _as_text(self.message),
        }
        if self.envelope is not None:
            payload["envelope"] = self.envelope.to_dict()
        if isinstance(self.details, dict) and self.details:
            payload["details"] = dict(self.details)
        return payload


class MutationContractRuntimeHandler(ABC):
    """Runtime handler seam for stage/validate/preview/apply/discard."""

    @abstractmethod
    def stage(self, envelope: NimmDirectiveEnvelope) -> MutationContractResult:
        raise NotImplementedError

    @abstractmethod
    def validate(self, envelope: NimmDirectiveEnvelope) -> MutationContractResult:
        raise NotImplementedError

    @abstractmethod
    def preview(self, envelope: NimmDirectiveEnvelope) -> MutationContractResult:
        raise NotImplementedError

    @abstractmethod
    def apply(self, envelope: NimmDirectiveEnvelope) -> MutationContractResult:
        raise NotImplementedError

    @abstractmethod
    def discard(self, envelope: NimmDirectiveEnvelope) -> MutationContractResult:
        raise NotImplementedError
