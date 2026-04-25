from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any, Mapping

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - runtime fallback
    yaml = None

from MyCiteV2.packages.adapters.sql.datum_semantics import (
    build_document_version_identity,
    datum_address_sort_key,
    format_datum_address,
    parse_datum_address,
    preview_document_insert as preview_document_insert_mutation,
)
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentMutationPort,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)

CTS_GIS_STAGE_INSERT_SCHEMA = "mycite.v2.cts_gis.stage_insert.v1"
CTS_GIS_STAGED_INSERT_STATE_SCHEMA = "mycite.v2.cts_gis.staged_insert.state.v1"

_SUPPORTED_OPERATION = "insert_datums"
_SUPPORTED_FAMILY = "administrative_street"
_SUPPORTED_REFERENCE_TYPES = ("msn-samras", "title")
_ALLOWED_STAGE_ROOT_KEYS = {"schema", "document_id", "document_name", "operation", "datums"}
_ALLOWED_DATUM_KEYS = {"family", "valueGroup", "targetNodeAddress", "title", "references"}
_ALLOWED_REFERENCE_KEYS = {"type", "nodeAddress", "text"}


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _json_clone(value: object) -> Any:
    return json.loads(json.dumps(value))


def _payload_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _ascii_normalize(value: object) -> str:
    token = _as_text(value)
    if not token:
        return ""
    normalized = unicodedata.normalize("NFKD", token).encode("ascii", "ignore").decode("ascii")
    normalized = " ".join(normalized.split())
    return normalized.strip()


def _ascii_bits(value: object, *, target_length: int) -> str:
    text = _ascii_normalize(value)
    bitstream = "".join(format(ord(char), "08b") for char in text)
    if target_length > 0:
        if len(bitstream) > target_length:
            raise ValueError("title_exceeds_template_bit_capacity")
        return bitstream.ljust(target_length, "0")
    return bitstream


def _samras_key(value: object) -> tuple[int, ...]:
    token = _as_text(value)
    if not token:
        return (10**9,)
    parts = token.split("-")
    if any(not part.isdigit() for part in parts):
        return (10**9, sum(ord(char) for char in token))
    return tuple(int(part, 10) for part in parts)


def _label_token(title: str) -> str:
    token = _ascii_normalize(title)
    if not token:
        return "UNLABELED"
    return token.replace(" ", "_")


def _reference_order(references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rank = {"msn-samras": 0, "title": 1}
    return sorted(
        references,
        key=lambda item: (
            rank.get(_as_text(item.get("type")).lower(), 10**9),
            _samras_key(item.get("nodeAddress")),
            _as_text(item.get("text")).lower(),
        ),
    )


def _looks_like_placeholder_title(title: object) -> bool:
    token = _ascii_normalize(title).upper()
    if not token:
        return True
    for marker in ("PLACEHOLDER", "TBD", "UNKNOWN", "UNLABELED", "MISSING"):
        if marker in token:
            return True
    return False


def _reference_value_by_type(references: list[dict[str, Any]], reference_type: str) -> dict[str, Any] | None:
    for reference in references:
        if _as_text(reference.get("type")).lower() == reference_type:
            return reference
    return None


def _longest_shared_prefix_depth(left: object, right: object) -> int:
    left_parts = [part for part in _as_text(left).split("-") if part]
    right_parts = [part for part in _as_text(right).split("-") if part]
    depth = 0
    for left_part, right_part in zip(left_parts, right_parts):
        if left_part != right_part:
            break
        depth += 1
    return depth


class CtsGisMutationError(ValueError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = _as_text(code) or "cts_gis_mutation_error"
        self.details = dict(details or {})


class CtsGisMutationService:
    def __init__(self, datum_store: AuthoritativeDatumDocumentMutationPort | None) -> None:
        self._datum_store = datum_store

    def _require_store(self) -> AuthoritativeDatumDocumentMutationPort:
        if self._datum_store is None:
            raise CtsGisMutationError(
                "authority_store_unavailable",
                "CTS-GIS mutation support requires a SQL-backed authority store.",
            )
        return self._datum_store

    def _catalog(self, *, tenant_id: str) -> AuthoritativeDatumDocumentCatalogResult:
        return self._require_store().read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id=tenant_id)
        )

    def _document(
        self,
        *,
        tenant_id: str,
        document_id: str,
    ) -> AuthoritativeDatumDocument:
        for document in self._catalog(tenant_id=tenant_id).documents:
            if document.document_id == _as_text(document_id):
                return document
        raise CtsGisMutationError(
            "unresolved_target_document",
            "The requested CTS-GIS authoritative document could not be resolved.",
            details={"document_id": _as_text(document_id)},
        )

    def _document_identity(self, *, tenant_id: str, document_id: str) -> dict[str, Any]:
        identity = self._require_store().read_document_version_identity(
            tenant_id=tenant_id,
            document_id=document_id,
        )
        if not isinstance(identity, dict) or not _as_text(identity.get("version_hash")):
            raise CtsGisMutationError(
                "document_version_identity_missing",
                "CTS-GIS mutations require a stable authoritative document version identity.",
                details={"document_id": _as_text(document_id)},
            )
        return dict(identity)

    def _parse_stage_text(self, text: str) -> tuple[dict[str, Any], str]:
        if not text.strip():
            raise CtsGisMutationError("stage_text_required", "action_payload.stage_text is required.")
        stripped = text.lstrip()
        if stripped.startswith("{"):
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise CtsGisMutationError("stage_text_invalid", f"CTS-GIS stage text could not be parsed: {exc}") from exc
            if not isinstance(payload, dict):
                raise CtsGisMutationError(
                    "stage_document_type_invalid",
                    "The CTS-GIS stage document must decode to one mapping object.",
                )
            return dict(payload), "json"
        if yaml is None:
            raise CtsGisMutationError(
                "yaml_dependency_missing",
                "CTS-GIS YAML stage parsing requires PyYAML. Install PyYAML or send JSON stage_text.",
            )
        try:
            payload = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise CtsGisMutationError("stage_text_invalid", f"CTS-GIS stage text could not be parsed: {exc}") from exc
        if not isinstance(payload, dict):
            raise CtsGisMutationError(
                "stage_document_type_invalid",
                "The CTS-GIS stage document must decode to one mapping object.",
            )
        return dict(payload), "yaml"

    def parse_stage_input(self, action_payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = _as_dict(action_payload)
        stage_text = _as_text(payload.get("stage_text"))
        stage_document = payload.get("stage_document")
        if stage_text:
            stage_mapping, draft_format = self._parse_stage_text(stage_text)
            draft_text = stage_text
        else:
            if not isinstance(stage_document, dict):
                raise CtsGisMutationError(
                    "stage_document_required",
                    "Provide action_payload.stage_text or action_payload.stage_document.",
                )
            stage_mapping = dict(stage_document)
            draft_format = "json"
            draft_text = json.dumps(stage_mapping, indent=2, sort_keys=True)
        if isinstance(stage_document, list):
            raise CtsGisMutationError(
                "stage_document_type_invalid",
                "CTS-GIS stage documents must be YAML/JSON objects, not arrays.",
            )
        return stage_mapping, {
            "draft_text": draft_text,
            "draft_format": draft_format,
            "placeholder_title_requested": bool(payload.get("placeholder_title_requested")),
        }

    def _normalize_reference(self, raw_reference: object) -> dict[str, Any]:
        reference = _as_dict(raw_reference)
        extra_keys = sorted(set(reference.keys()) - _ALLOWED_REFERENCE_KEYS)
        if extra_keys:
            raise CtsGisMutationError(
                "reference_keys_invalid",
                "CTS-GIS staged references contain unsupported fields.",
                details={"keys": extra_keys},
            )
        reference_type = _as_text(reference.get("type")).lower()
        if reference_type not in _SUPPORTED_REFERENCE_TYPES:
            raise CtsGisMutationError(
                "reference_type_invalid",
                f"CTS-GIS staged references must use one of {_SUPPORTED_REFERENCE_TYPES}.",
            )
        if reference_type == "msn-samras":
            node_address = _as_text(reference.get("nodeAddress"))
            if not node_address:
                raise CtsGisMutationError(
                    "reference_node_missing",
                    "msn-samras references must include nodeAddress.",
                )
            return {"type": "msn-samras", "nodeAddress": node_address}
        title_text = _ascii_normalize(reference.get("text"))
        return {"type": "title", "text": title_text}

    def normalize_stage_document(
        self,
        stage_document: Mapping[str, Any],
        *,
        placeholder_title_requested: bool,
        selected_document_id: str = "",
        selected_document_name: str = "",
    ) -> tuple[dict[str, Any], list[str]]:
        payload = _as_dict(stage_document)
        extra_root_keys = sorted(set(payload.keys()) - _ALLOWED_STAGE_ROOT_KEYS)
        if extra_root_keys:
            raise CtsGisMutationError(
                "stage_root_keys_invalid",
                "CTS-GIS stage documents contain unsupported top-level fields.",
                details={"keys": extra_root_keys},
            )
        schema = _as_text(payload.get("schema"))
        if schema != CTS_GIS_STAGE_INSERT_SCHEMA:
            raise CtsGisMutationError(
                "stage_schema_invalid",
                f"schema must be {CTS_GIS_STAGE_INSERT_SCHEMA}",
            )
        operation = _as_text(payload.get("operation"))
        if operation != _SUPPORTED_OPERATION:
            raise CtsGisMutationError(
                "stage_operation_invalid",
                f"operation must be {_SUPPORTED_OPERATION}",
            )
        document_id = _as_text(payload.get("document_id")) or _as_text(selected_document_id)
        document_name = _as_text(payload.get("document_name")) or _as_text(selected_document_name)
        if not document_id:
            raise CtsGisMutationError("stage_document_id_required", "document_id is required.")
        if not document_name:
            raise CtsGisMutationError("stage_document_name_required", "document_name is required.")
        raw_datums = _as_list(payload.get("datums"))
        if not raw_datums:
            raise CtsGisMutationError("stage_datums_required", "CTS-GIS staged inserts require at least one datum.")

        warnings: list[str] = []
        normalized_datums: list[dict[str, Any]] = []
        for index, raw_datum in enumerate(raw_datums):
            datum = _as_dict(raw_datum)
            extra_datum_keys = sorted(set(datum.keys()) - _ALLOWED_DATUM_KEYS)
            if extra_datum_keys:
                raise CtsGisMutationError(
                    "stage_datum_keys_invalid",
                    "CTS-GIS staged datums contain unsupported fields.",
                    details={"index": index, "keys": extra_datum_keys},
                )
            family = _as_text(datum.get("family"))
            if family != _SUPPORTED_FAMILY:
                raise CtsGisMutationError(
                    "stage_family_invalid",
                    f"CTS-GIS staged inserts currently support only {_SUPPORTED_FAMILY}.",
                    details={"index": index},
                )
            try:
                value_group = int(datum.get("valueGroup"))
            except (TypeError, ValueError):
                value_group = -1
            if value_group != 2:
                raise CtsGisMutationError(
                    "stage_value_group_invalid",
                    "CTS-GIS staged inserts require valueGroup: 2.",
                    details={"index": index},
                )
            target_node_address = _as_text(datum.get("targetNodeAddress"))
            if not target_node_address:
                raise CtsGisMutationError(
                    "target_node_missing",
                    "targetNodeAddress is required for each staged CTS-GIS datum.",
                    details={"index": index},
                )
            references = [self._normalize_reference(item) for item in _as_list(datum.get("references"))]
            if not references:
                raise CtsGisMutationError(
                    "references_required",
                    "Each staged CTS-GIS datum must provide references.",
                    details={"index": index},
                )
            normalized_references = _reference_order(references)
            node_reference = _reference_value_by_type(normalized_references, "msn-samras")
            title_reference = _reference_value_by_type(normalized_references, "title")
            if node_reference is None or title_reference is None:
                raise CtsGisMutationError(
                    "reference_form_invalid",
                    "Each staged CTS-GIS datum must include msn-samras and title references.",
                    details={"index": index},
                )
            if _as_text(node_reference.get("nodeAddress")) != target_node_address:
                raise CtsGisMutationError(
                    "target_node_reference_mismatch",
                    "targetNodeAddress must match the msn-samras nodeAddress.",
                    details={"index": index},
                )
            normalized_title = _ascii_normalize(datum.get("title") or title_reference.get("text"))
            placeholder = _looks_like_placeholder_title(normalized_title)
            if placeholder and not placeholder_title_requested:
                raise CtsGisMutationError(
                    "placeholder_title_denied",
                    "Placeholder titles require placeholder_title_requested=true.",
                    details={"index": index},
                )
            if placeholder:
                normalized_title = normalized_title or "UNLABELED"
                warnings.append(f"placeholder_title:{target_node_address}")
            title_reference = {"type": "title", "text": normalized_title}
            normalized_datums.append(
                {
                    "family": family,
                    "valueGroup": 2,
                    "targetNodeAddress": target_node_address,
                    "title": normalized_title,
                    "references": [dict(node_reference), title_reference],
                }
            )
        normalized_datums.sort(
            key=lambda item: (
                _samras_key(item.get("targetNodeAddress")),
                _ascii_normalize(item.get("title")).lower(),
            )
        )
        return (
            {
                "schema": CTS_GIS_STAGE_INSERT_SCHEMA,
                "document_id": document_id,
                "document_name": document_name,
                "operation": _SUPPORTED_OPERATION,
                "datums": normalized_datums,
            },
            warnings,
        )

    def build_stage_state(
        self,
        *,
        stage_document: Mapping[str, Any],
        draft_text: str,
        draft_format: str,
        placeholder_title_requested: bool,
        selected_document_id: str = "",
        selected_document_name: str = "",
    ) -> tuple[dict[str, Any], list[str]]:
        normalized_payload, warnings = self.normalize_stage_document(
            stage_document,
            placeholder_title_requested=placeholder_title_requested,
            selected_document_id=selected_document_id,
            selected_document_name=selected_document_name,
        )
        return (
            {
                "schema": CTS_GIS_STAGED_INSERT_STATE_SCHEMA,
                "draft_text": draft_text,
                "draft_format": _as_text(draft_format) or "yaml",
                "normalized_payload": normalized_payload,
                "placeholder_title_requested": bool(placeholder_title_requested),
                "last_validation": {},
                "last_preview": {},
            },
            warnings,
        )

    def _document_row_node_address(self, row: AuthoritativeDatumDocumentRow) -> str:
        raw = row.raw
        if not isinstance(raw, list) or not raw:
            return ""
        data_tokens = raw[0] if isinstance(raw[0], list) else raw
        tokens = list(data_tokens) if isinstance(data_tokens, list) else []
        if len(tokens) < 5:
            return ""
        for index in range(len(tokens) - 1):
            if _as_text(tokens[index]).lower() == "rf.3-1-2":
                return _as_text(tokens[index + 1])
        return ""

    def _document_row_title_bits(self, row: AuthoritativeDatumDocumentRow) -> str:
        raw = row.raw
        if not isinstance(raw, list) or not raw:
            return ""
        data_tokens = raw[0] if isinstance(raw[0], list) else raw
        tokens = list(data_tokens) if isinstance(data_tokens, list) else []
        if len(tokens) < 5:
            return ""
        for index in range(len(tokens) - 1):
            if _as_text(tokens[index]).lower() == "rf.3-1-3":
                return _as_text(tokens[index + 1])
        return ""

    def _template_row(
        self,
        *,
        document: AuthoritativeDatumDocument,
        target_node_address: str,
    ) -> AuthoritativeDatumDocumentRow:
        candidates: list[tuple[tuple[int, int, int, tuple[int, int, int]], AuthoritativeDatumDocumentRow]] = []
        for row in document.rows:
            layer, value_group, _ = parse_datum_address(row.datum_address)
            if value_group != 2:
                continue
            title_bits = self._document_row_title_bits(row)
            node_address = self._document_row_node_address(row)
            if not title_bits or not node_address:
                continue
            prefix_depth = _longest_shared_prefix_depth(node_address, target_node_address)
            candidates.append(
                (
                    (
                        0 if len(title_bits) % 8 == 0 else 1,
                        -prefix_depth,
                        layer,
                        datum_address_sort_key(row.datum_address),
                    ),
                    row,
                )
            )
        if not candidates:
            raise CtsGisMutationError(
                "template_row_missing",
                "CTS-GIS could not derive a reusable administrative datum template from the target document.",
                details={"document_id": document.document_id},
            )
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def _compile_insert_raw(
        self,
        *,
        template_row: AuthoritativeDatumDocumentRow,
        target_node_address: str,
        title: str,
    ) -> Any:
        raw = _json_clone(template_row.raw)
        if not isinstance(raw, list) or not raw:
            raise CtsGisMutationError("template_row_invalid", "CTS-GIS template rows must use list-backed MOS raw rows.")
        data_tokens = raw[0] if isinstance(raw[0], list) else raw
        if not isinstance(data_tokens, list) or len(data_tokens) < 5:
            raise CtsGisMutationError(
                "template_row_invalid",
                "CTS-GIS template rows must include rf.3-1-2 and rf.3-1-3 reference bindings.",
            )
        updated_tokens = list(data_tokens)
        node_rewritten = False
        title_rewritten = False
        for index in range(len(updated_tokens) - 1):
            token = _as_text(updated_tokens[index]).lower()
            if token == "rf.3-1-2":
                updated_tokens[index + 1] = target_node_address
                node_rewritten = True
            if token == "rf.3-1-3":
                template_bits = _as_text(updated_tokens[index + 1])
                try:
                    updated_tokens[index + 1] = _ascii_bits(title, target_length=len(template_bits))
                except ValueError as exc:
                    raise CtsGisMutationError(
                        "title_bit_capacity_exceeded",
                        "The normalized title exceeds the bit capacity of the CTS-GIS template row.",
                    ) from exc
                title_rewritten = True
        if not node_rewritten or not title_rewritten:
            raise CtsGisMutationError(
                "template_row_invalid",
                "CTS-GIS template rows must include one node binding and one title binding.",
            )
        raw[0] = updated_tokens
        if len(raw) > 1 and isinstance(raw[1], list):
            raw[1] = [_label_token(title)]
        return raw

    def _administrative_rows(self, document: AuthoritativeDatumDocument) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in sorted(document.rows, key=lambda item: datum_address_sort_key(item.datum_address)):
            layer, value_group, iteration = parse_datum_address(row.datum_address)
            if value_group != 2:
                continue
            rows.append(
                {
                    "datum_address": row.datum_address,
                    "layer": layer,
                    "value_group": value_group,
                    "iteration": iteration,
                    "target_node_address": self._document_row_node_address(row),
                    "raw": _json_clone(row.raw),
                }
            )
        return rows

    def _group_iteration_state(self, document: AuthoritativeDatumDocument) -> tuple[int, dict[str, list[int]], int]:
        rows = self._administrative_rows(document)
        family_layer = rows[0]["layer"] if rows else 4
        grouped: dict[str, list[int]] = {}
        for row in rows:
            target = _as_text(row.get("target_node_address"))
            if target:
                grouped.setdefault(target, []).append(int(row.get("iteration") or 0))
        for target_node_address, iterations in grouped.items():
            ordered = sorted(iterations)
            expected = ordered[0]
            for value in ordered:
                if value != expected:
                    raise CtsGisMutationError(
                        "non_contiguous_iteration_plan",
                        "CTS-GIS administrative rows must stay contiguous within each target node group.",
                        details={"targetNodeAddress": target_node_address, "iterations": ordered},
                    )
                expected += 1
        max_iteration = max((row["iteration"] for row in rows), default=0)
        return family_layer, grouped, max_iteration

    def validate_stage(
        self,
        *,
        tenant_id: str,
        tool_state: Mapping[str, Any],
        contract_state: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = _as_dict(tool_state)
        stage_state = _as_dict(state.get("staged_insert"))
        normalized_payload = _as_dict(stage_state.get("normalized_payload"))
        if not normalized_payload:
            raise CtsGisMutationError("stage_missing", "Stage a CTS-GIS insert batch before validation.")

        contract = _as_dict(contract_state)
        if contract:
            if contract.get("configured") is False:
                raise CtsGisMutationError("contract_denied", "CTS-GIS is not configured for mutation in this runtime.")
            if contract.get("enabled") is False:
                raise CtsGisMutationError("contract_denied", "CTS-GIS is disabled in this runtime.")
            missing_capabilities = [item for item in _as_list(contract.get("missing_capabilities")) if _as_text(item)]
            if missing_capabilities:
                raise CtsGisMutationError(
                    "contract_denied",
                    "CTS-GIS mutation requires capabilities that are missing from this portal scope.",
                    details={"missing_capabilities": missing_capabilities},
                )

        selected_document_id = _as_text(_as_dict(state.get("source")).get("attention_document_id"))
        document_id = _as_text(normalized_payload.get("document_id"))
        if selected_document_id and selected_document_id != document_id:
            raise CtsGisMutationError(
                "selected_document_mismatch",
                "The staged CTS-GIS document must match the currently selected source document.",
                details={"selected_document_id": selected_document_id, "document_id": document_id},
            )
        document = self._document(tenant_id=tenant_id, document_id=document_id)
        if _as_text(document.tool_id) != "cts_gis":
            raise CtsGisMutationError(
                "target_document_tool_mismatch",
                "The selected authoritative document is not owned by CTS-GIS.",
                details={"document_id": document.document_id, "tool_id": document.tool_id},
            )
        identity = self._document_identity(tenant_id=tenant_id, document_id=document.document_id)
        family_layer, grouped_iterations, max_iteration = self._group_iteration_state(document)
        warnings = []
        warnings.extend(_as_list(stage_state.get("warnings")))
        warnings.extend(_as_list((stage_state.get("last_validation") or {}).get("warnings")))
        warnings = [item for item in warnings if _as_text(item)]

        groups: dict[str, list[dict[str, Any]]] = {}
        for datum in _as_list(normalized_payload.get("datums")):
            normalized_datum = _as_dict(datum)
            groups.setdefault(_as_text(normalized_datum.get("targetNodeAddress")), []).append(normalized_datum)
        plan_groups: list[dict[str, Any]] = []
        for target_node_address, items in groups.items():
            current_iterations = sorted(int(value) for value in grouped_iterations.get(target_node_address, []))
            next_iteration = current_iterations[-1] + 1 if current_iterations else max_iteration + 1
            ordered_items = sorted(
                items,
                key=lambda item: (
                    _samras_key(_as_dict(_reference_value_by_type(_as_list(item.get("references")), "msn-samras")).get("nodeAddress")),
                    _ascii_normalize(item.get("title")).lower(),
                ),
            )
            assignments = []
            for offset, item in enumerate(ordered_items):
                assignments.append(
                    {
                        "title": _as_text(item.get("title")),
                        "target_node_address": target_node_address,
                        "iteration": next_iteration + offset,
                    }
                )
            plan_groups.append(
                {
                    "target_node_address": target_node_address,
                    "current_iterations": current_iterations,
                    "current_max_iteration": current_iterations[-1] if current_iterations else 0,
                    "insert_count": len(assignments),
                    "planned_assignments": assignments,
                }
            )
        plan_groups.sort(
            key=lambda item: (
                item.get("current_max_iteration") or max_iteration + 1,
                _samras_key(item.get("target_node_address")),
            )
        )
        validation = {
            "schema": "mycite.v2.cts_gis.stage_validation.v1",
            "normalized_payload": _json_clone(normalized_payload),
            "warnings": warnings,
            "insertion_plan": {
                "document_id": document.document_id,
                "document_name": document.document_name,
                "family_layer": family_layer,
                "value_group": 2,
                "groups": plan_groups,
            },
            "expected_document_version_hash": _as_text(identity.get("version_hash")),
            "payload_hash": _payload_hash(normalized_payload),
        }
        return validation

    def preview_stage(
        self,
        *,
        tenant_id: str,
        tool_state: Mapping[str, Any],
        contract_state: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = _as_dict(tool_state)
        validation = self.validate_stage(
            tenant_id=tenant_id,
            tool_state=state,
            contract_state=contract_state,
        )
        normalized_payload = _as_dict(validation.get("normalized_payload"))
        document = self._document(tenant_id=tenant_id, document_id=_as_text(normalized_payload.get("document_id")))
        current_document = document
        original_address_map = {
            row.datum_address: row.datum_address
            for row in sorted(document.rows, key=lambda item: datum_address_sort_key(item.datum_address))
        }
        affected_existing_rows: dict[str, dict[str, Any]] = {}
        inserted_rows: list[dict[str, Any]] = []
        remap_by_original: dict[str, str] = dict(original_address_map)

        family_layer = int(_as_dict(validation.get("insertion_plan")).get("family_layer") or 4)
        groups = _as_list(_as_dict(validation.get("insertion_plan")).get("groups"))
        for group in groups:
            target_node_address = _as_text(_as_dict(group).get("target_node_address"))
            datums = [
                datum
                for datum in _as_list(normalized_payload.get("datums"))
                if _as_text(_as_dict(datum).get("targetNodeAddress")) == target_node_address
            ]
            ordered_datums = sorted(
                [_as_dict(item) for item in datums],
                key=lambda item: (
                    _samras_key(_as_dict(_reference_value_by_type(_as_list(item.get("references")), "msn-samras")).get("nodeAddress")),
                    _ascii_normalize(item.get("title")).lower(),
                ),
            )
            for datum in ordered_datums:
                _, grouped_iterations, max_iteration = self._group_iteration_state(current_document)
                current_iterations = sorted(int(value) for value in grouped_iterations.get(target_node_address, []))
                next_iteration = current_iterations[-1] + 1 if current_iterations else max_iteration + 1
                target_address = format_datum_address(family_layer, 2, next_iteration)
                template_row = self._template_row(document=current_document, target_node_address=target_node_address)
                raw = self._compile_insert_raw(
                    template_row=template_row,
                    target_node_address=target_node_address,
                    title=_as_text(datum.get("title")),
                )
                preview = preview_document_insert_mutation(
                    current_document,
                    target_address=target_address,
                    raw=raw,
                )
                address_map = {
                    _as_text(from_address): _as_text(to_address)
                    for from_address, to_address in _as_dict(preview.get("address_map")).items()
                    if _as_text(from_address)
                }
                for original_address, current_address in list(remap_by_original.items()):
                    remap_by_original[original_address] = address_map.get(current_address, current_address)
                    if remap_by_original[original_address] != original_address:
                        affected_existing_rows[original_address] = {
                            "from": original_address,
                            "to": remap_by_original[original_address],
                        }
                current_document = preview["updated_document"]
                inserted_rows.append(
                    {
                        "datum_address": target_address,
                        "iteration": next_iteration,
                        "target_node_address": target_node_address,
                        "title": _as_text(datum.get("title")),
                        "raw": _json_clone(raw),
                    }
                )

        updated_identity = build_document_version_identity(current_document)
        preview_rows = self._administrative_rows(current_document)
        preview_result = {
            "schema": "mycite.v2.cts_gis.stage_preview.v1",
            "expected_document_version_hash": _as_text(validation.get("expected_document_version_hash")),
            "payload_hash": _as_text(validation.get("payload_hash")),
            "affected_document": {
                "document_id": document.document_id,
                "document_name": document.document_name,
                "version_hash_before": _as_text(validation.get("expected_document_version_hash")),
                "version_hash_after": _as_text(updated_identity.get("version_hash")),
                "row_count_before": int(document.row_count),
                "row_count_after": int(current_document.row_count),
            },
            "affected_rows": sorted(
                list(affected_existing_rows.values()),
                key=lambda item: datum_address_sort_key(item["from"]),
            ),
            "proposed_inserted_rows": inserted_rows,
            "final_assignments": [
                {
                    "datum_address": row["datum_address"],
                    "iteration": row["iteration"],
                    "target_node_address": row["target_node_address"],
                    "title": next(
                        (
                            insert["title"]
                            for insert in inserted_rows
                            if insert["datum_address"] == row["datum_address"]
                        ),
                        "",
                    ),
                }
                for row in preview_rows
                if any(insert["datum_address"] == row["datum_address"] for insert in inserted_rows)
            ],
            "remaps": [
                {"from": from_address, "to": to_address}
                for from_address, to_address in sorted(remap_by_original.items(), key=lambda item: datum_address_sort_key(item[0]))
                if from_address != to_address
            ],
            "warnings": list(_as_list(validation.get("warnings"))),
            "updated_document": current_document,
        }
        return preview_result

    def apply_stage(
        self,
        *,
        tenant_id: str,
        tool_state: Mapping[str, Any],
        contract_state: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = _as_dict(tool_state)
        stage_state = _as_dict(state.get("staged_insert"))
        last_preview = _as_dict(stage_state.get("last_preview"))
        if not last_preview:
            raise CtsGisMutationError(
                "preview_required",
                "Preview the staged CTS-GIS insert plan before applying it.",
            )
        normalized_payload = _as_dict(stage_state.get("normalized_payload"))
        current_identity = self._document_identity(
            tenant_id=tenant_id,
            document_id=_as_text(normalized_payload.get("document_id")),
        )
        if _as_text(last_preview.get("expected_document_version_hash")) != _as_text(current_identity.get("version_hash")):
            raise CtsGisMutationError(
                "stale_preview_version",
                "The authoritative CTS-GIS document changed after preview; run preview again before applying.",
            )
        if _as_text(last_preview.get("payload_hash")) != _payload_hash(normalized_payload):
            raise CtsGisMutationError(
                "stale_preview_payload",
                "The staged CTS-GIS payload changed after preview; run preview again before applying.",
            )
        preview_result = self.preview_stage(
            tenant_id=tenant_id,
            tool_state=state,
            contract_state=contract_state,
        )
        updated_document = preview_result.get("updated_document")
        if not isinstance(updated_document, AuthoritativeDatumDocument):
            raise CtsGisMutationError(
                "apply_document_missing",
                "CTS-GIS apply could not materialize an updated authoritative document.",
            )
        persisted_catalog = self._require_store().replace_authoritative_document(
            tenant_id=tenant_id,
            document_id=updated_document.document_id,
            updated_document=updated_document,
        )
        latest_identity = self._document_identity(
            tenant_id=tenant_id,
            document_id=updated_document.document_id,
        )
        preview_result["persisted_catalog"] = persisted_catalog
        preview_result["persisted_version_hash"] = _as_text(latest_identity.get("version_hash"))
        return preview_result


__all__ = [
    "CTS_GIS_STAGE_INSERT_SCHEMA",
    "CTS_GIS_STAGED_INSERT_STATE_SCHEMA",
    "CtsGisMutationError",
    "CtsGisMutationService",
]
