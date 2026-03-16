from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..data_engine.external_resources.contact_card_catalog import parse_public_resource_catalog
from ..datum_refs import normalize_datum_ref, parse_datum_ref
from ..mss import decode_mss_payload, preview_mss_context
from .models import (
    ExposedResourceValue,
    InheritedResourceContext,
    MSSCompactArray,
    MSSResource,
    SAMRASResource,
    SandboxCompileResult,
    SandboxStageResult,
)
from .samras import (
    decode_resource_rows,
    decode_structure_payload,
    encode_resource_rows,
    ensure_resource_object,
)


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


class SandboxEngine:
    """
    Shared-core sandbox service layer.

    This layer is intentionally derived/rebuildable and does not replace anthology authority.
    """

    def __init__(self, *, data_root: Path):
        self._data_root = Path(data_root)
        self._sandbox_root = self._data_root / "sandbox"
        self._resources_root = self._sandbox_root / "resources"
        self._stage_root = self._sandbox_root / "staging"

    def _resource_path(self, resource_id: str) -> Path:
        token = _as_text(resource_id).replace("/", "_")
        return self._resources_root / f"{token}.json"

    def _stage_path(self, resource_id: str) -> Path:
        token = _as_text(resource_id).replace("/", "_")
        return self._stage_root / f"{token}.stage.json"

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.exists() or not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def list_resources(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not self._resources_root.exists():
            return out
        for path in sorted(self._resources_root.glob("*.json"), key=lambda item: item.name):
            payload = self._read_json(path)
            out.append(
                {
                    "resource_id": _as_text(payload.get("resource_id")) or path.stem,
                    "schema": _as_text(payload.get("schema")),
                    "kind": _as_text(payload.get("kind")),
                    "path": str(path),
                }
            )
        return out

    def get_resource(self, resource_id: str) -> dict[str, Any]:
        path = self._resource_path(resource_id)
        payload = self._read_json(path)
        if payload:
            return payload
        return {"schema": "", "resource_id": _as_text(resource_id), "kind": "", "missing": True}

    def save_resource(self, resource_id: str, payload: dict[str, Any]) -> SandboxStageResult:
        try:
            out = dict(payload if isinstance(payload, dict) else {})
            out.setdefault("resource_id", _as_text(resource_id))
            self._write_json(self._resource_path(resource_id), out)
            return SandboxStageResult(
                ok=True,
                resource_type=_as_text(out.get("kind")) or "resource",
                resource_id=_as_text(resource_id),
                staged_payload=out,
                warnings=[],
                errors=[],
            )
        except Exception as exc:
            return SandboxStageResult(
                ok=False,
                resource_type="resource",
                resource_id=_as_text(resource_id),
                staged_payload={},
                warnings=[],
                errors=[str(exc)],
            )

    def stage_resource(self, resource_id: str, payload: dict[str, Any]) -> SandboxStageResult:
        try:
            out = dict(payload if isinstance(payload, dict) else {})
            out.setdefault("resource_id", _as_text(resource_id))
            self._write_json(self._stage_path(resource_id), out)
            return SandboxStageResult(
                ok=True,
                resource_type=_as_text(out.get("kind")) or "resource",
                resource_id=_as_text(resource_id),
                staged_payload=out,
                warnings=[],
                errors=[],
            )
        except Exception as exc:
            return SandboxStageResult(
                ok=False,
                resource_type="resource",
                resource_id=_as_text(resource_id),
                staged_payload={},
                warnings=[],
                errors=[str(exc)],
            )

    def compile_mss_resource(
        self,
        *,
        resource_id: str,
        selected_refs: list[str],
        anthology_payload: dict[str, Any],
        local_msn_id: str,
    ) -> SandboxCompileResult:
        try:
            preview = preview_mss_context(
                anthology_payload=anthology_payload if isinstance(anthology_payload, dict) else {},
                selected_refs=[_as_text(item) for item in selected_refs if _as_text(item)],
                bitstring="",
                local_msn_id=_as_text(local_msn_id),
            )
            resource = MSSResource(
                resource_id=_as_text(resource_id),
                selected_refs=[_as_text(item) for item in selected_refs if _as_text(item)],
                bitstring=_as_text(preview.get("bitstring")),
                metadata=dict(preview.get("metadata") if isinstance(preview.get("metadata"), dict) else {}),
                rows=[dict(item) for item in list(preview.get("rows") or []) if isinstance(item, dict)],
            )
            payload = {
                "schema": "mycite.sandbox.mss_resource.v1",
                "kind": "mss_resource",
                **resource.to_dict(),
            }
            self._write_json(self._resource_path(resource_id), payload)
            return SandboxCompileResult(
                ok=True,
                resource_type="mss_resource",
                resource_id=_as_text(resource_id),
                compiled_payload=payload,
                warnings=[str(item) for item in list(preview.get("warnings") or [])],
                errors=[],
            )
        except Exception as exc:
            return SandboxCompileResult(
                ok=False,
                resource_type="mss_resource",
                resource_id=_as_text(resource_id),
                compiled_payload={},
                warnings=[],
                errors=[str(exc)],
            )

    def decode_mss_resource(self, *, bitstring: str, resource_id: str = "mss_decode") -> SandboxCompileResult:
        try:
            decoded = decode_mss_payload(_as_text(bitstring))
            compact = MSSCompactArray(
                resource_id=_as_text(resource_id),
                bitstring=_as_text(decoded.get("bitstring")),
                metadata=dict(decoded.get("metadata") if isinstance(decoded.get("metadata"), dict) else {}),
                rows=[dict(item) for item in list(decoded.get("rows") or []) if isinstance(item, dict)],
            )
            return SandboxCompileResult(
                ok=True,
                resource_type="mss_compact_array",
                resource_id=_as_text(resource_id),
                compiled_payload=compact.to_dict(),
                warnings=[str(item) for item in list(decoded.get("warnings") or [])],
                errors=[],
            )
        except Exception as exc:
            return SandboxCompileResult(
                ok=False,
                resource_type="mss_compact_array",
                resource_id=_as_text(resource_id),
                compiled_payload={},
                warnings=[],
                errors=[str(exc)],
            )

    def create_or_update_samras_resource(
        self,
        *,
        resource_id: str,
        structure_payload: str,
        rows: list[dict[str, Any]],
        value_kind: str,
        source: str = "local",
    ) -> SandboxStageResult:
        try:
            descriptor = decode_structure_payload(
                _as_text(structure_payload),
                value_kind=_as_text(value_kind) or "address_id",
                source_ref=_as_text(source),
            )
            payload = ensure_resource_object(
                {
                    "kind": "samras_resource",
                    "source": _as_text(source) or "local",
                    "value_kind": _as_text(value_kind) or "address_id",
                },
                resource_id=_as_text(resource_id),
                descriptor=descriptor,
                rows_by_address=encode_resource_rows(rows if isinstance(rows, list) else []),
            )
            self._write_json(self._resource_path(resource_id), payload)
            return SandboxStageResult(
                ok=True,
                resource_type="samras_resource",
                resource_id=_as_text(resource_id),
                staged_payload=payload,
                warnings=[],
                errors=[],
            )
        except Exception as exc:
            return SandboxStageResult(
                ok=False,
                resource_type="samras_resource",
                resource_id=_as_text(resource_id),
                staged_payload={},
                warnings=[],
                errors=[str(exc)],
            )

    def decode_samras_resource(self, resource_id: str) -> SandboxCompileResult:
        payload = self.get_resource(resource_id)
        if bool(payload.get("missing")):
            return SandboxCompileResult(
                ok=False,
                resource_type="samras_resource",
                resource_id=_as_text(resource_id),
                compiled_payload={},
                warnings=[],
                errors=[f"resource not found: {resource_id}"],
            )
        descriptor = payload.get("descriptor") if isinstance(payload.get("descriptor"), dict) else {}
        rows = decode_resource_rows(payload)
        model = SAMRASResource(
            resource_id=_as_text(payload.get("resource_id") or resource_id),
            value_kind=_as_text(payload.get("value_kind") or descriptor.get("value_kind")),
            descriptor=dict(descriptor),
            rows=[dict(item) for item in rows],
            source=_as_text(payload.get("source")) or "local",
        )
        return SandboxCompileResult(
            ok=True,
            resource_type="samras_resource",
            resource_id=model.resource_id,
            compiled_payload=model.to_dict(),
            warnings=[],
            errors=[],
        )

    def generate_exposed_resource_values(self, *, local_msn_id: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in self.list_resources():
            resource_id = _as_text(item.get("resource_id"))
            resource_payload = self.get_resource(resource_id)
            if bool(resource_payload.get("missing")):
                continue
            value = ExposedResourceValue(
                resource_id=resource_id,
                kind="sandbox_resource",
                export_family="mycite.sandbox.resource.v1",
                lens_hint="sandbox",
                href=f"/portal/api/data/sandbox/resources/{resource_id}/value",
                availability="public",
                value={
                    "resource_id": resource_id,
                    "schema": _as_text(resource_payload.get("schema")),
                    "kind": _as_text(resource_payload.get("kind")),
                    "local_msn_id": _as_text(local_msn_id),
                },
            )
            out.append(value.to_dict())
        return out

    def resolve_inherited_resource_context(
        self,
        *,
        resource_ref: str,
        local_msn_id: str,
        external_resolver: Any | None = None,
    ) -> InheritedResourceContext:
        token = _as_text(resource_ref)
        local_msn = _as_text(local_msn_id)
        if not token:
            return InheritedResourceContext(
                ok=False,
                scope="",
                local_ref="",
                canonical_ref="",
                source_msn_id="",
                resource_id="",
                resource_value={},
                provenance={},
                warnings=[],
                errors=["resource_ref is required"],
            )
        # local: sandbox:<resource_id> or bare resource id
        if token.startswith("sandbox:") or "." not in token:
            rid = token.split(":", 1)[1] if token.startswith("sandbox:") else token
            payload = self.get_resource(rid)
            if bool(payload.get("missing")):
                return InheritedResourceContext(
                    ok=False,
                    scope="local",
                    local_ref=rid,
                    canonical_ref=f"{local_msn}.{rid}" if local_msn else rid,
                    source_msn_id=local_msn,
                    resource_id=rid,
                    resource_value={},
                    provenance={},
                    warnings=[],
                    errors=[f"local sandbox resource not found: {rid}"],
                )
            return InheritedResourceContext(
                ok=True,
                scope="local",
                local_ref=rid,
                canonical_ref=f"{local_msn}.{rid}" if local_msn else rid,
                source_msn_id=local_msn,
                resource_id=rid,
                resource_value=payload,
                provenance={"origin": "local_sandbox"},
                warnings=[],
                errors=[],
            )
        # foreign form: <msn_id>.<resource_id>
        source_msn, rid = token.split(".", 1)
        source_msn = _as_text(source_msn)
        rid = _as_text(rid)
        if external_resolver is None:
            return InheritedResourceContext(
                ok=False,
                scope="foreign",
                local_ref=rid,
                canonical_ref=token,
                source_msn_id=source_msn,
                resource_id=rid,
                resource_value={},
                provenance={},
                warnings=[],
                errors=["external resolver unavailable for foreign resource context"],
            )
        fetched = external_resolver.fetch_and_cache_bundle(source_msn_id=source_msn, resource_id=rid, force_refresh=False)
        if not bool((fetched or {}).get("ok")):
            return InheritedResourceContext(
                ok=False,
                scope="foreign",
                local_ref=rid,
                canonical_ref=token,
                source_msn_id=source_msn,
                resource_id=rid,
                resource_value={},
                provenance={},
                warnings=[],
                errors=[_as_text((fetched or {}).get("error")) or "failed to fetch foreign resource"],
            )
        bundle = fetched.get("bundle") if isinstance(fetched.get("bundle"), dict) else {}
        return InheritedResourceContext(
            ok=True,
            scope="foreign",
            local_ref=rid,
            canonical_ref=token,
            source_msn_id=source_msn,
            resource_id=rid,
            resource_value=dict(bundle),
            provenance={"origin": "external_bundle", "source_msn_id": source_msn},
            warnings=[],
            errors=[],
        )

    def generate_contact_card_public_resources(
        self,
        *,
        card_payload: dict[str, Any],
        local_msn_id: str,
    ) -> dict[str, Any]:
        parsed = parse_public_resource_catalog(
            source_msn_id=_as_text(local_msn_id),
            card_payload=card_payload if isinstance(card_payload, dict) else {},
        )
        sandbox_resources = self.generate_exposed_resource_values(local_msn_id=local_msn_id)
        return {
            "ok": True,
            "source_msn_id": _as_text(local_msn_id),
            "contact_card_public_resources": [item.to_dict() for item in parsed],
            "sandbox_exposed_resources": sandbox_resources,
        }

    def parse_canonical_datum_ref(self, datum_ref: str, *, local_msn_id: str) -> dict[str, Any]:
        canonical = normalize_datum_ref(
            datum_ref,
            local_msn_id=_as_text(local_msn_id),
            write_format="dot",
            field_name="datum_ref",
        )
        parsed = parse_datum_ref(canonical, field_name="datum_ref")
        return {
            "datum_ref": _as_text(datum_ref),
            "canonical_ref": canonical,
            "source_msn_id": _as_text(parsed.msn_id),
            "datum_address": _as_text(parsed.datum_address),
            "qualified": bool(parsed.qualified),
        }
