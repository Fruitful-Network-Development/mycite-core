from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SandboxCompileResult:
    ok: bool
    resource_type: str
    resource_id: str
    compiled_payload: dict[str, Any]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "compiled_payload": dict(self.compiled_payload),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class SandboxStageResult:
    ok: bool
    resource_type: str
    resource_id: str
    staged_payload: dict[str, Any]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "staged_payload": dict(self.staged_payload),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class MSSResource:
    resource_id: str
    selected_refs: list[str]
    bitstring: str
    metadata: dict[str, Any]
    rows: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "selected_refs": list(self.selected_refs),
            "bitstring": self.bitstring,
            "metadata": dict(self.metadata),
            "rows": [dict(item) for item in self.rows],
        }


@dataclass(frozen=True)
class MSSCompactArray:
    resource_id: str
    bitstring: str
    metadata: dict[str, Any]
    rows: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "bitstring": self.bitstring,
            "metadata": dict(self.metadata),
            "rows": [dict(item) for item in self.rows],
        }


@dataclass(frozen=True)
class SAMRASResource:
    resource_id: str
    value_kind: str
    descriptor: dict[str, Any]
    rows: list[dict[str, Any]]
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "value_kind": self.value_kind,
            "descriptor": dict(self.descriptor),
            "rows": [dict(item) for item in self.rows],
            "source": self.source,
        }


@dataclass(frozen=True)
class ExposedResourceValue:
    resource_id: str
    kind: str
    export_family: str
    lens_hint: str
    href: str
    availability: str
    value: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "kind": self.kind,
            "export_family": self.export_family,
            "lens_hint": self.lens_hint,
            "href": self.href,
            "availability": self.availability,
            "value": dict(self.value),
        }


@dataclass(frozen=True)
class InheritedResourceContext:
    ok: bool
    scope: str
    local_ref: str
    canonical_ref: str
    source_msn_id: str
    resource_id: str
    resource_value: dict[str, Any]
    provenance: dict[str, Any]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "scope": self.scope,
            "local_ref": self.local_ref,
            "canonical_ref": self.canonical_ref,
            "source_msn_id": self.source_msn_id,
            "resource_id": self.resource_id,
            "resource_value": dict(self.resource_value),
            "provenance": dict(self.provenance),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }
