from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from ..data_engine.external_resources.contact_card_catalog import parse_public_resource_catalog
from ..data_engine.inherited_txa_adapter import (
    adapt_published_txa_resource_value,
    build_field_ref_bindings,
)
from ..data_engine.resource_registry import INHERITED_SCOPE, read_resource_file, resource_file_path
from ..data_engine.samras_descriptor_compiler import compile_samras_descriptors_from_rows
from ..datum_refs import normalize_datum_ref, parse_datum_ref
from mycite_core.mss_resolution import decode_mss_payload, preview_mss_context
from ..samras import (
    InvalidSamrasStructure,
    address_sort_key,
    build_workspace_view_model,
    load_workspace_from_resource_body,
    mutate_resource_body,
    parent_address as parent_of_address,
    rebuild_structure_from_addresses,
)
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
    SamrasRole,
    SamrasStructure,
    compile_canonical_samras_bitstring,
    decode_samras_structure,
    decode_resource_rows,
    decode_structure_payload,
    encode_resource_rows,
    ensure_resource_object,
    inspect_node_by_address,
    validate_samras_structure,
)


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


_DATUM_TOKEN_RE = re.compile(r"^[0-9]+-[0-9]+-[0-9]+$")


def _normalize_address_seed_map(title_by_address: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    raw_addresses = [token for token in title_by_address.keys() if token]
    if not raw_addresses:
        return {}, []

    expanded: set[str] = set()
    for token in raw_addresses:
        cursor = token
        while cursor:
            expanded.add(cursor)
            cursor = parent_of_address(cursor)

    children_by_parent: dict[str, list[str]] = {}
    for address in sorted(expanded, key=address_sort_key):
        children_by_parent.setdefault(parent_of_address(address), []).append(address)

    mapping: dict[str, str] = {}

    def _assign(old_address: str, new_address: str) -> None:
        mapping[old_address] = new_address
        for index, child in enumerate(children_by_parent.get(old_address, []), start=1):
            _assign(child, f"{new_address}-{index}")

    for index, root in enumerate(children_by_parent.get("", []), start=1):
        _assign(root, str(index))

    ordered = sorted((mapping[address] for address in expanded if address in mapping), key=address_sort_key)
    return mapping, ordered


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
            kind = _as_text(payload.get("kind")) or _as_text(payload.get("resource_kind"))
            out.append(
                {
                    "resource_id": _as_text(payload.get("resource_id")) or path.stem,
                    "schema": _as_text(payload.get("schema")),
                    "kind": kind,
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

    def peek_stage_payload(self, resource_id: str) -> tuple[bool, dict[str, Any]]:
        """Return whether a staging file exists and its payload (empty dict if unreadable)."""
        path = self._stage_path(resource_id)
        if not path.is_file():
            return False, {}
        payload = self._read_json(path)
        return True, payload

    def save_resource(self, resource_id: str, payload: dict[str, Any]) -> SandboxStageResult:
        try:
            out = dict(payload if isinstance(payload, dict) else {})
            out.setdefault("resource_id", _as_text(resource_id))
            out.setdefault("updated_at", int(time.time()))
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
            out.setdefault("updated_at", int(time.time()))
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
            title_by_address = (
                {
                    _as_text(item.get("address_id")): _as_text(item.get("title"))
                    for item in rows
                    if isinstance(item, dict)
                }
                if isinstance(rows, list)
                else {}
            )
            warnings: list[str] = []
            try:
                decoded_structure = decode_samras_structure(
                    _as_text(structure_payload),
                    root_ref="0-0-5",
                )
            except Exception:
                address_mapping, normalized_addresses = _normalize_address_seed_map(title_by_address)
                if not normalized_addresses:
                    raise
                decoded_structure = rebuild_structure_from_addresses(
                    normalized_addresses,
                    root_ref="0-0-5",
                )
                title_by_address = {
                    address_mapping[address]: title
                    for address, title in title_by_address.items()
                    if address in address_mapping and address_mapping[address]
                }
                warnings.append("structure_payload was descriptor-only; derived SAMRAS structure from title rows")
            address_map = dict(decoded_structure.address_map or {})
            unknown_addresses = [address for address in title_by_address.keys() if address and address not in address_map]
            if unknown_addresses:
                raise InvalidSamrasStructure(
                    "title rows reference addresses not present in the governing structure: "
                    + ", ".join(sorted(unknown_addresses))
                )
            validation = validate_samras_structure(decoded_structure)
            if not bool(validation.get("ok")):
                raise ValueError("; ".join(list(validation.get("errors") or [])) or "invalid SAMRAS structure")
            canonical_magnitude = compile_canonical_samras_bitstring(decoded_structure)
            descriptor = decode_structure_payload(
                "0",
                shape_root="0-0-5",
                role=SamrasRole.VALUE,
                value_kind=_as_text(value_kind) or "address_id",
                source_ref=_as_text(source),
            )
            payload = ensure_resource_object(
                {
                    "kind": "samras_resource",
                    "source": _as_text(source) or "local",
                    "value_kind": _as_text(value_kind) or "address_id",
                    "root_ref": "0-0-5",
                    "source_format": "canonical",
                    "canonical_state": "canonical",
                    "samras_structure": decode_samras_structure(canonical_magnitude, root_ref="0-0-5").to_dict(),
                    "legacy_structure_payload_input": _as_text(structure_payload),
                    "canonical_magnitude": canonical_magnitude,
                },
                resource_id=_as_text(resource_id),
                descriptor=descriptor,
                rows_by_address=encode_resource_rows(
                    [
                        {
                            "address_id": key,
                            "title": _as_text(title_by_address.get(key, "")),
                        }
                        for key in sorted(address_map.keys(), key=lambda token: tuple(int(part) for part in token.split("-")))
                    ]
                    if isinstance(rows, list)
                        else [{"address_id": key, "title": ""} for key in sorted(address_map.keys(), key=lambda token: tuple(int(part) for part in token.split("-")))]
                ),
            )
            payload["structure_payload"] = canonical_magnitude
            self._write_json(self._resource_path(resource_id), payload)
            return SandboxStageResult(
                ok=True,
                resource_type="samras_resource",
                resource_id=_as_text(resource_id),
                staged_payload=payload,
                warnings=warnings + list(validation.get("warnings") or []),
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
        structure_payload = _as_text(payload.get("structure_payload"))
        if not structure_payload:
            structure_payload = _as_text(payload.get("canonical_magnitude"))
        warnings: list[str] = []
        structure_dict: dict[str, Any] = {}
        if structure_payload:
            try:
                structure = decode_samras_structure(structure_payload, root_ref="0-0-5")
                structure_dict = structure.to_dict()
                validation = validate_samras_structure(structure)
                warnings.extend([str(item) for item in list(validation.get("warnings") or [])])
                payload["canonical_magnitude"] = compile_canonical_samras_bitstring(structure)
                try:
                    workspace = load_workspace_from_resource_body(payload)
                    payload["samras_workspace"] = build_workspace_view_model(workspace, selected_address_id="", staged_entries=[])
                except Exception as exc:
                    warnings.append(f"unable to build SAMRAS workspace view: {exc}")
            except Exception as exc:
                warnings.append(f"unable to decode structure payload: {exc}")
        rows = decode_resource_rows(payload)
        model = SAMRASResource(
            resource_id=_as_text(payload.get("resource_id") or resource_id),
            value_kind=_as_text(payload.get("value_kind") or descriptor.get("value_kind")),
            descriptor=dict(descriptor),
            rows=[dict(item) for item in rows],
            source=_as_text(payload.get("source")) or "local",
        )
        compiled = model.to_dict()
        compiled["samras_structure"] = dict(payload.get("samras_structure") if isinstance(payload.get("samras_structure"), dict) else structure_dict)
        compiled["canonical_magnitude"] = _as_text(payload.get("canonical_magnitude") or structure_payload)
        compiled["root_ref"] = _as_text(payload.get("root_ref")) or "0-0-5"
        compiled["canonical_state"] = _as_text(payload.get("canonical_state")) or "canonical"
        return SandboxCompileResult(
            ok=True,
            resource_type="samras_resource",
            resource_id=model.resource_id,
            compiled_payload=compiled,
            warnings=warnings,
            errors=[],
        )

    def _load_samras_structure(self, resource_id: str) -> SamrasStructure:
        payload = self.get_resource(resource_id)
        if bool(payload.get("missing")):
            raise ValueError(f"resource not found: {resource_id}")
        raw = _as_text(payload.get("structure_payload") or payload.get("canonical_magnitude"))
        if not raw:
            raw = _as_text(payload.get("legacy_structure_payload_input"))
        if not raw:
            raise ValueError("resource does not contain structure payload")
        return decode_samras_structure(raw, root_ref="0-0-5")

    def _persist_samras_structure(self, resource_id: str, *, structure: SamrasStructure) -> dict[str, Any]:
        payload = self.get_resource(resource_id)
        if bool(payload.get("missing")):
            raise ValueError(f"resource not found: {resource_id}")
        validation = validate_samras_structure(structure)
        if not bool(validation.get("ok")):
            raise ValueError("; ".join(list(validation.get("errors") or [])) or "invalid SAMRAS structure")
        canonical = compile_canonical_samras_bitstring(structure)
        payload["structure_payload"] = canonical
        payload["canonical_magnitude"] = canonical
        payload["samras_structure"] = structure.to_dict()
        payload["root_ref"] = "0-0-5"
        payload["source_format"] = "canonical_binary"
        payload["canonical_state"] = "canonical"
        payload["updated_at"] = int(time.time())
        self._write_json(self._resource_path(resource_id), payload)
        return payload

    def inspect_samras_node(self, *, resource_id: str, address_id: str) -> dict[str, Any]:
        structure = self._load_samras_structure(resource_id)
        result = inspect_node_by_address(structure, address_id)
        result["resource_id"] = _as_text(resource_id)
        result["schema"] = "mycite.portal.sandbox.samras.inspect_node.v1"
        return result

    def set_samras_node(self, *, resource_id: str, address_id: str, value: int) -> dict[str, Any]:
        payload = self.get_resource(resource_id)
        if bool(payload.get("missing")):
            raise ValueError(f"resource not found: {resource_id}")
        updated, workspace, mutation = mutate_resource_body(
            payload,
            action="samras_set_child_count",
            address_id=address_id,
            child_count=int(value),
        )
        self._write_json(self._resource_path(resource_id), updated)
        return {
            "ok": True,
            "schema": "mycite.portal.sandbox.samras.set_node.v1",
            "resource_id": _as_text(resource_id),
            "address_id": _as_text(address_id),
            "value": int(value),
            "canonical_magnitude": _as_text(updated.get("canonical_magnitude")),
            "samras_structure": dict(updated.get("samras_structure") if isinstance(updated.get("samras_structure"), dict) else {}),
            "samras_workspace": build_workspace_view_model(workspace, selected_address_id=_as_text(address_id), staged_entries=[]),
            "mutation": mutation,
        }

    def create_samras_child(self, *, resource_id: str, parent_address: str, value: int = 0) -> dict[str, Any]:
        payload = self.get_resource(resource_id)
        if bool(payload.get("missing")):
            raise ValueError(f"resource not found: {resource_id}")
        updated, workspace, mutation = mutate_resource_body(
            payload,
            action="samras_add_child",
            parent_address=parent_address,
        )
        created = str(((mutation.get("created_addresses") or [""])[0]) if isinstance(mutation, dict) else "")
        if created and int(value) > 0:
            updated, workspace, resize_mutation = mutate_resource_body(
                updated,
                action="samras_set_child_count",
                address_id=created,
                child_count=int(value),
            )
            mutation = {
                "action": "samras_add_child",
                "samras_structure": resize_mutation.get("samras_structure") if isinstance(resize_mutation, dict) else {},
                "canonical_magnitude": resize_mutation.get("canonical_magnitude") if isinstance(resize_mutation, dict) else "",
                "address_mapping": resize_mutation.get("address_mapping") if isinstance(resize_mutation, dict) else {},
                "created_addresses": [created],
                "removed_addresses": resize_mutation.get("removed_addresses") if isinstance(resize_mutation, dict) else [],
            }
        self._write_json(self._resource_path(resource_id), updated)
        return {
            "ok": True,
            "schema": "mycite.portal.sandbox.samras.create_child.v1",
            "resource_id": _as_text(resource_id),
            "parent_address": _as_text(parent_address),
            "created_address": created,
            "canonical_magnitude": _as_text(updated.get("canonical_magnitude")),
            "samras_structure": dict(updated.get("samras_structure") if isinstance(updated.get("samras_structure"), dict) else {}),
            "samras_workspace": build_workspace_view_model(workspace, selected_address_id=created, staged_entries=[]),
            "mutation": mutation,
        }

    def delete_samras_address(self, *, resource_id: str, address_id: str) -> dict[str, Any]:
        payload = self.get_resource(resource_id)
        if bool(payload.get("missing")):
            raise ValueError(f"resource not found: {resource_id}")
        updated, workspace, mutation = mutate_resource_body(
            payload,
            action="samras_delete_branch",
            address_id=address_id,
        )
        self._write_json(self._resource_path(resource_id), updated)
        return {
            "ok": True,
            "schema": "mycite.portal.sandbox.samras.delete_address.v1",
            "resource_id": _as_text(resource_id),
            "deleted_address": _as_text(address_id),
            "canonical_magnitude": _as_text(updated.get("canonical_magnitude")),
            "samras_structure": dict(updated.get("samras_structure") if isinstance(updated.get("samras_structure"), dict) else {}),
            "samras_workspace": build_workspace_view_model(workspace, selected_address_id="", staged_entries=[]),
            "mutation": mutation,
        }

    def move_samras_branch(self, *, resource_id: str, from_address: str, to_parent_address: str) -> dict[str, Any]:
        payload = self.get_resource(resource_id)
        if bool(payload.get("missing")):
            raise ValueError(f"resource not found: {resource_id}")
        updated, workspace, mutation = mutate_resource_body(
            payload,
            action="samras_move_branch",
            address_id=from_address,
            parent_address=to_parent_address,
        )
        self._write_json(self._resource_path(resource_id), updated)
        return {
            "ok": True,
            "schema": "mycite.portal.sandbox.samras.move_branch.v1",
            "resource_id": _as_text(resource_id),
            "from_address": _as_text(from_address),
            "to_parent_address": _as_text(to_parent_address),
            "canonical_magnitude": _as_text(updated.get("canonical_magnitude")),
            "samras_structure": dict(updated.get("samras_structure") if isinstance(updated.get("samras_structure"), dict) else {}),
            "samras_workspace": build_workspace_view_model(workspace, selected_address_id=_as_text(to_parent_address), staged_entries=[]),
            "mutation": mutation,
        }

    def generate_exposed_resource_values(self, *, local_msn_id: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in self.list_resources():
            resource_id = _as_text(item.get("resource_id"))
            resource_payload = self.get_resource(resource_id)
            if bool(resource_payload.get("missing")):
                continue
            schema = _as_text(resource_payload.get("schema"))
            kind = _as_text(resource_payload.get("kind") or resource_payload.get("resource_kind"))
            if schema == "mycite.sandbox.singular_mss_resource.v1":
                compiled_state = resource_payload.get("compile_metadata") if isinstance(resource_payload.get("compile_metadata"), dict) else {}
                published_value = resource_payload.get("published_value") if isinstance(resource_payload.get("published_value"), dict) else {}
                mss_form = resource_payload.get("mss_form") if isinstance(resource_payload.get("mss_form"), dict) else {}
                value_payload = {
                    "resource_id": resource_id,
                    "resource_kind": _as_text(resource_payload.get("resource_kind")),
                    "origin_kind": _as_text(resource_payload.get("origin_kind")),
                    "mss_form": dict(mss_form),
                    "compile_metadata": dict(compiled_state),
                    "published_value": dict(published_value),
                    "local_msn_id": _as_text(local_msn_id),
                }
            else:
                value_payload = {
                    "resource_id": resource_id,
                    "schema": schema,
                    "kind": kind,
                    "local_msn_id": _as_text(local_msn_id),
                }
            value = ExposedResourceValue(
                resource_id=resource_id,
                kind="sandbox_resource",
                export_family="mycite.sandbox.resource.v1",
                lens_hint="sandbox",
                href=f"/portal/api/data/sandbox/resources/{resource_id}/value",
                availability="public",
                value=value_payload,
            )
            out.append(value.to_dict())
        return out

    def compile_isolated_mss_resource(self, *, resource_id: str) -> SandboxCompileResult:
        payload = self.get_resource(resource_id)
        if bool(payload.get("missing")):
            return SandboxCompileResult(
                ok=False,
                resource_type="singular_mss_resource",
                resource_id=_as_text(resource_id),
                compiled_payload={},
                warnings=[],
                errors=[f"resource not found: {resource_id}"],
            )
        if _as_text(payload.get("schema")) != "mycite.sandbox.singular_mss_resource.v1":
            return SandboxCompileResult(
                ok=False,
                resource_type="singular_mss_resource",
                resource_id=_as_text(resource_id),
                compiled_payload={},
                warnings=[],
                errors=["resource schema is not mycite.sandbox.singular_mss_resource.v1"],
            )
        canonical = payload.get("canonical_state") if isinstance(payload.get("canonical_state"), dict) else {}
        compact_payload = canonical.get("compact_payload") if isinstance(canonical.get("compact_payload"), dict) else {}
        selected = canonical.get("selected_ids") if isinstance(canonical.get("selected_ids"), list) else []
        selected_refs = [_as_text(item) for item in selected if _as_text(item)]
        local_msn_id = _as_text(payload.get("source_portal")) or "local"
        resource_kind = _as_text(payload.get("resource_kind") or "txa")
        try:
            preview = preview_mss_context(
                anthology_payload=compact_payload,
                selected_refs=selected_refs,
                bitstring="",
                local_msn_id=local_msn_id,
            )
            compiled_bitstring = _as_text(preview.get("bitstring"))
            compile_metadata = {
                "compiled": True,
                "warnings": [str(item) for item in list(preview.get("warnings") or [])],
                "selected_ref_count": len(selected_refs),
                "row_count": len(list(preview.get("rows") or [])),
                "compiled_at": int(time.time()),
            }
            field_ref_bindings = build_field_ref_bindings(selected_refs, source_msn_id=local_msn_id)
            descriptor_digest = adapt_published_txa_resource_value(
                payload={
                    "resource_id": _as_text(payload.get("resource_id") or resource_id),
                    "resource_kind": resource_kind,
                    "mss_form": {"bitstring": compiled_bitstring},
                },
                context_source="sandbox.compile_isolated_mss_resource.digest_seed",
            ).get("descriptor_digest")
            compile_metadata["descriptor_digest"] = _as_text(descriptor_digest)
            compile_metadata["mss_form_bitstring"] = compiled_bitstring
            compile_metadata["provisional_state"] = "compiled"
            payload["mss_form"] = {
                "bitstring": compiled_bitstring,
                "wire_variant": "canonical",
            }
            payload["compile_metadata"] = compile_metadata
            payload["published_value"] = {
                "resource_ref": _as_text(payload.get("source_ref")) or _as_text(resource_id),
                "resource_kind": resource_kind,
                "mss_form_bitstring": compiled_bitstring,
                "field_ref_bindings": field_ref_bindings,
                "descriptor_digest": _as_text(descriptor_digest),
            }
            payload["updated_at"] = int(time.time())
            self._write_json(self._resource_path(resource_id), payload)
            return SandboxCompileResult(
                ok=True,
                resource_type="singular_mss_resource",
                resource_id=_as_text(resource_id),
                compiled_payload=dict(payload),
                warnings=list(compile_metadata.get("warnings") or []),
                errors=[],
            )
        except Exception as exc:
            return SandboxCompileResult(
                ok=False,
                resource_type="singular_mss_resource",
                resource_id=_as_text(resource_id),
                compiled_payload={},
                warnings=[],
                errors=[str(exc)],
            )

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
        cached_path = resource_file_path(
            self._data_root,
            scope=INHERITED_SCOPE,
            source_msn_id=source_msn,
            resource_name=rid,
        )
        cached_payload = read_resource_file(cached_path)
        if isinstance(cached_payload, dict) and cached_payload:
            return InheritedResourceContext(
                ok=True,
                scope="foreign_cached",
                local_ref=rid,
                canonical_ref=token,
                source_msn_id=source_msn,
                resource_id=rid,
                resource_value=dict(cached_payload.get("anthology_compatible_payload") or cached_payload),
                provenance={"origin": "inherited_cache", "path": str(cached_path), "source_msn_id": source_msn},
                warnings=[],
                errors=[],
            )
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

    @staticmethod
    def _collect_ref_tokens(payload: Any) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()

        def _walk(value: Any) -> None:
            if isinstance(value, dict):
                for item in value.values():
                    _walk(item)
                return
            if isinstance(value, list):
                for item in value:
                    _walk(item)
                return
            if isinstance(value, (str, int, float)):
                token = _as_text(value)
                if not token or token in seen:
                    return
                # Accept canonical refs and raw datum ids; keep permissive for provisional ingest.
                if "." in token:
                    left, _, right = token.partition(".")
                    if left and right and _DATUM_TOKEN_RE.fullmatch(right):
                        seen.add(token)
                        out.append(token)
                        return
                if _DATUM_TOKEN_RE.fullmatch(token):
                    seen.add(token)
                    out.append(token)

        _walk(payload)
        return out

    @staticmethod
    def _is_txa_ref(token: str) -> bool:
        raw = _as_text(token).lower()
        if not raw:
            return False
        if "txa" in raw:
            return True
        if ".8-4-" in raw or ".8-5-" in raw:
            return True
        if raw.startswith("8-4-") or raw.startswith("8-5-"):
            return True
        return False

    def compile_txa_inherited_context(
        self,
        *,
        resource_ref: str,
        local_msn_id: str,
        external_resolver: Any | None = None,
        merged_rows_by_id: dict[str, dict[str, Any]] | None = None,
        inherited_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        context = self.resolve_inherited_resource_context(
            resource_ref=resource_ref,
            local_msn_id=local_msn_id,
            external_resolver=external_resolver,
        )
        if not context.ok:
            return {
                "ok": False,
                "resource_ref": _as_text(resource_ref),
                "errors": list(context.errors),
                "warnings": list(context.warnings),
            }
        context_payload = context.to_dict()
        adapted = adapt_published_txa_resource_value(
            payload=context.resource_value if isinstance(context.resource_value, dict) else {},
            context_source="sandbox.resolve_inherited_resource_context",
        )
        bindings = adapted.get("field_ref_bindings") if isinstance(adapted.get("field_ref_bindings"), dict) else {}
        txa_refs = [str(item).strip() for item in list(bindings.get("all_refs") or []) if str(item).strip()]
        if not txa_refs:
            discovered = self._collect_ref_tokens(context.resource_value)
            explicit = [_as_text(item) for item in list(inherited_refs or []) if _as_text(item)]
            candidates = []
            seen: set[str] = set()
            for token in explicit + discovered:
                if token in seen:
                    continue
                seen.add(token)
                candidates.append(token)
            txa_refs = [token for token in candidates if self._is_txa_ref(token)]
            if not txa_refs and context.canonical_ref and self._is_txa_ref(context.canonical_ref):
                txa_refs.append(context.canonical_ref)

        descriptors = compile_samras_descriptors_from_rows(
            merged_rows_by_id if isinstance(merged_rows_by_id, dict) else {},
            context_source="sandbox.txa_inherited_context",
        )
        txa_descriptor = {}
        for item in descriptors:
            if _as_text(item.get("value_kind")) == "txa_id":
                txa_descriptor = dict(item)
                break
        if not txa_descriptor and descriptors:
            txa_descriptor = dict(descriptors[0])
        if bool(adapted.get("descriptor_digest")):
            txa_descriptor.setdefault("descriptor_digest", _as_text(adapted.get("descriptor_digest")))
            txa_descriptor.setdefault("value_kind", _as_text(adapted.get("value_kind") or "txa_id"))
            txa_descriptor.setdefault("constraint_family", _as_text(adapted.get("constraint_family") or "samras"))
            txa_descriptor.setdefault("role", _as_text(adapted.get("role") or "value"))
            txa_descriptor.setdefault("context_source", _as_text(adapted.get("context_source") or "published_resource"))
            txa_descriptor.setdefault("provisional_state", _as_text(adapted.get("provisional_state") or "compiled"))

        return {
            "ok": True,
            "resource_ref": _as_text(resource_ref),
            "inherited_context": context_payload,
            "constraint_family": "samras",
            "txa_descriptor": txa_descriptor,
            "txa_refs": txa_refs,
            "field_usable_refs": list(txa_refs),
            "field_ref_bindings": dict(bindings),
            "resource_adapter": dict(adapted),
            "context_source": "inherited_compact_or_contact_card",
            "warnings": list(context.warnings),
            "errors": [],
        }

    def adapt_published_txa_context(
        self,
        *,
        published_resource_value: dict[str, Any],
        context_source: str = "sandbox.published_resource_value",
    ) -> dict[str, Any]:
        adapted = adapt_published_txa_resource_value(
            payload=published_resource_value if isinstance(published_resource_value, dict) else {},
            context_source=context_source,
        )
        if not bool(adapted.get("ok")):
            return {
                "ok": False,
                "errors": ["unable to adapt published resource value"],
                "warnings": [],
            }
        refs = []
        bindings = adapted.get("field_ref_bindings") if isinstance(adapted.get("field_ref_bindings"), dict) else {}
        for token in list(bindings.get("all_refs") or []):
            text = _as_text(token)
            if text:
                refs.append(text)
        return {
            "ok": True,
            "constraint_family": _as_text(adapted.get("constraint_family") or "samras"),
            "descriptor_digest": _as_text(adapted.get("descriptor_digest")),
            "value_kind": _as_text(adapted.get("value_kind") or "txa_id"),
            "role": _as_text(adapted.get("role") or "value"),
            "resource_id": _as_text(adapted.get("resource_id")),
            "resource_kind": _as_text(adapted.get("resource_kind") or "txa"),
            "origin_kind": _as_text(adapted.get("origin_kind") or "local"),
            "published_value": dict(adapted.get("published_value") if isinstance(adapted.get("published_value"), dict) else {}),
            "mss_form": dict(adapted.get("mss_form") if isinstance(adapted.get("mss_form"), dict) else {}),
            "compile_metadata": dict(
                adapted.get("compile_metadata") if isinstance(adapted.get("compile_metadata"), dict) else {}
            ),
            "field_ref_bindings": dict(bindings),
            "field_usable_refs": refs,
            "binding_selection_source": _as_text(adapted.get("binding_selection_source")),
            "provisional_state": _as_text(adapted.get("provisional_state") or "compiled"),
            "context_source": _as_text(adapted.get("context_source") or context_source),
            "errors": [],
            "warnings": [str(item).strip() for item in list(adapted.get("warnings") or []) if str(item).strip()],
        }

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
