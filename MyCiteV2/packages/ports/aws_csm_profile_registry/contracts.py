from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AwsCsmProfileRegistryPort(Protocol):
    """Registry access for canonical AWS-CSM tool profile documents."""

    def list_profiles(self) -> list[dict[str, Any]]:
        ...

    def resolve_domain_seed(self, *, domain: str) -> dict[str, Any] | None:
        ...

    def create_profile(self, *, profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...


__all__ = ["AwsCsmProfileRegistryPort"]
