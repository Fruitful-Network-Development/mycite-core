from __future__ import annotations

import json
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql.datum_semantics import build_document_version_identity
from MyCiteV2.packages.modules.cross_domain.cts_gis import (
    CTS_GIS_STAGE_INSERT_SCHEMA,
    CtsGisMutationError,
    CtsGisMutationService,
)
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)


def _ascii_bits(value: str, *, width: int = 256) -> str:
    bitstream = "".join(format(ord(char), "08b") for char in value)
    return bitstream.ljust(width, "0")


def _row(datum_address: str, node_address: str, title: str) -> AuthoritativeDatumDocumentRow:
    return AuthoritativeDatumDocumentRow(
        datum_address=datum_address,
        raw=[
            [datum_address, "rf.3-1-2", node_address, "rf.3-1-3", _ascii_bits(title)],
            [title.replace(" ", "_")],
        ],
    )


def _document(*rows: AuthoritativeDatumDocumentRow) -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id="sandbox:cts_gis:sc.example.json",
        source_kind="sandbox_source",
        document_name="sc.example.json",
        relative_path="sandbox/cts-gis/sources/sc.example.json",
        tool_id="cts_gis",
        rows=rows,
    )


class _FakeMutationStore:
    def __init__(self, document: AuthoritativeDatumDocument) -> None:
        self.document = document

    def read_authoritative_datum_documents(self, request: AuthoritativeDatumDocumentRequest) -> AuthoritativeDatumDocumentCatalogResult:
        normalized = (
            request
            if isinstance(request, AuthoritativeDatumDocumentRequest)
            else AuthoritativeDatumDocumentRequest.from_dict(request)
        )
        return AuthoritativeDatumDocumentCatalogResult(
            tenant_id=normalized.tenant_id,
            documents=(self.document,),
            source_files={self.document.relative_path: {"exists": True}},
            readiness_status={"authoritative_catalog": "loaded"},
        )

    def read_document_version_identity(self, *, tenant_id: str, document_id: str) -> dict[str, str] | None:
        del tenant_id
        if document_id != self.document.document_id:
            return None
        return build_document_version_identity(self.document)

    def replace_authoritative_document(
        self,
        *,
        tenant_id: str,
        document_id: str,
        updated_document: AuthoritativeDatumDocument,
    ) -> AuthoritativeDatumDocumentCatalogResult:
        del tenant_id
        if document_id != self.document.document_id:
            raise ValueError("authoritative_document_missing")
        self.document = updated_document
        return AuthoritativeDatumDocumentCatalogResult(
            tenant_id="fnd",
            documents=(self.document,),
            source_files={self.document.relative_path: {"exists": True}},
            readiness_status={"authoritative_catalog": "loaded"},
        )


class CtsGisMutationServiceTests(unittest.TestCase):
    def _store(self) -> _FakeMutationStore:
        return _FakeMutationStore(
            _document(
                _row("4-2-1", "3-2-3-17-77-1", "ALPHA STREET"),
                _row("4-2-2", "3-2-3-17-77-2", "BETA STREET"),
                _row("4-2-3", "3-2-3-17-77-2", "GAMMA STREET"),
            )
        )

    def _stage_document(self) -> dict[str, object]:
        return {
            "schema": CTS_GIS_STAGE_INSERT_SCHEMA,
            "document_id": "sandbox:cts_gis:sc.example.json",
            "document_name": "sc.example.json",
            "operation": "insert_datums",
            "datums": [
                {
                    "family": "administrative_street",
                    "valueGroup": 2,
                    "targetNodeAddress": "3-2-3-17-77-1",
                    "title": "MAIN STREET",
                    "references": [
                        {"type": "title", "text": "MAIN STREET"},
                        {"type": "msn-samras", "nodeAddress": "3-2-3-17-77-1"},
                    ],
                },
                {
                    "family": "administrative_street",
                    "valueGroup": 2,
                    "targetNodeAddress": "3-2-3-17-77-1",
                    "title": "OAK STREET",
                    "references": [
                        {"type": "title", "text": "OAK STREET"},
                        {"type": "msn-samras", "nodeAddress": "3-2-3-17-77-1"},
                    ],
                },
            ],
        }

    def _tool_state(self, service: CtsGisMutationService) -> dict[str, object]:
        stage_state, _ = service.build_stage_state(
            stage_document=self._stage_document(),
            draft_text="stage",
            draft_format="yaml",
            placeholder_title_requested=False,
        )
        return {
            "source": {"attention_document_id": "sandbox:cts_gis:sc.example.json"},
            "selected_node_id": "3-2-3-17-77-1",
            "staged_insert": stage_state,
        }

    def test_happy_path_validates_previews_and_applies(self) -> None:
        store = self._store()
        service = CtsGisMutationService(store)
        tool_state = self._tool_state(service)

        validation = service.validate_stage(tenant_id="fnd", tool_state=tool_state)
        self.assertEqual(validation["expected_document_version_hash"][:7], "sha256:")
        self.assertEqual(validation["insertion_plan"]["groups"][0]["planned_assignments"][0]["iteration"], 2)

        preview = service.preview_stage(tenant_id="fnd", tool_state=tool_state)
        self.assertEqual(
            [row["datum_address"] for row in preview["proposed_inserted_rows"]],
            ["4-2-2", "4-2-3"],
        )
        self.assertEqual(
            [row["to"] for row in preview["remaps"]],
            ["4-2-4", "4-2-5"],
        )

        tool_state["staged_insert"]["last_preview"] = {
            key: value for key, value in preview.items() if key != "updated_document"
        }
        applied = service.apply_stage(tenant_id="fnd", tool_state=tool_state)

        self.assertEqual(applied["persisted_version_hash"][:7], "sha256:")
        self.assertEqual(store.document.row_count, 5)
        self.assertEqual(
            [row.datum_address for row in store.document.rows],
            ["4-2-1", "4-2-2", "4-2-3", "4-2-4", "4-2-5"],
        )

    def test_reorders_references_and_emits_placeholder_warning_when_requested(self) -> None:
        store = self._store()
        service = CtsGisMutationService(store)
        stage_state, warnings = service.build_stage_state(
            stage_document={
                "schema": CTS_GIS_STAGE_INSERT_SCHEMA,
                "document_id": "sandbox:cts_gis:sc.example.json",
                "document_name": "sc.example.json",
                "operation": "insert_datums",
                "datums": [
                    {
                        "family": "administrative_street",
                        "valueGroup": 2,
                        "targetNodeAddress": "3-2-3-17-77-1",
                        "title": "",
                        "references": [
                            {"type": "title", "text": ""},
                            {"type": "msn-samras", "nodeAddress": "3-2-3-17-77-1"},
                        ],
                    }
                ],
            },
            draft_text="stage",
            draft_format="yaml",
            placeholder_title_requested=True,
        )

        references = stage_state["normalized_payload"]["datums"][0]["references"]
        self.assertEqual([reference["type"] for reference in references], ["msn-samras", "title"])
        self.assertEqual(stage_state["normalized_payload"]["datums"][0]["title"], "UNLABELED")
        self.assertIn("placeholder_title:3-2-3-17-77-1", warnings)

    def test_rejects_non_contiguous_iteration_groups(self) -> None:
        store = _FakeMutationStore(
            _document(
                _row("4-2-1", "3-2-3-17-77-1", "ALPHA STREET"),
                _row("4-2-2", "3-2-3-17-77-2", "BETA STREET"),
                _row("4-2-3", "3-2-3-17-77-1", "GAMMA STREET"),
            )
        )
        service = CtsGisMutationService(store)
        tool_state = self._tool_state(service)

        with self.assertRaises(CtsGisMutationError) as context:
            service.validate_stage(tenant_id="fnd", tool_state=tool_state)

        self.assertEqual(context.exception.code, "non_contiguous_iteration_plan")

    def test_rejects_contract_denied_validation(self) -> None:
        store = self._store()
        service = CtsGisMutationService(store)
        tool_state = self._tool_state(service)

        with self.assertRaises(CtsGisMutationError) as context:
            service.validate_stage(
                tenant_id="fnd",
                tool_state=tool_state,
                contract_state={"configured": True, "enabled": False, "missing_capabilities": []},
            )

        self.assertEqual(context.exception.code, "contract_denied")

    def test_preview_is_idempotent_for_same_stage_and_version(self) -> None:
        store = self._store()
        service = CtsGisMutationService(store)
        tool_state = self._tool_state(service)

        preview_a = service.preview_stage(tenant_id="fnd", tool_state=tool_state)
        preview_b = service.preview_stage(tenant_id="fnd", tool_state=tool_state)

        preview_a.pop("updated_document", None)
        preview_b.pop("updated_document", None)
        self.assertEqual(preview_a, preview_b)

    def test_apply_rejects_stale_preview(self) -> None:
        store = self._store()
        service = CtsGisMutationService(store)
        tool_state = self._tool_state(service)
        preview = service.preview_stage(tenant_id="fnd", tool_state=tool_state)
        tool_state["staged_insert"]["last_preview"] = {
            key: value for key, value in preview.items() if key != "updated_document"
        }

        store.replace_authoritative_document(
            tenant_id="fnd",
            document_id=store.document.document_id,
            updated_document=_document(
                _row("4-2-1", "3-2-3-17-77-1", "ALPHA STREET"),
                _row("4-2-2", "3-2-3-17-77-2", "BETA STREET"),
                _row("4-2-3", "3-2-3-17-77-2", "GAMMA STREET"),
                _row("4-2-4", "3-2-3-17-77-3", "DELTA STREET"),
            ),
        )

        with self.assertRaises(CtsGisMutationError) as context:
            service.apply_stage(tenant_id="fnd", tool_state=tool_state)

        self.assertEqual(context.exception.code, "stale_preview_version")


    def test_json_stage_text_parses_without_yaml_dependency(self) -> None:
        store = self._store()
        service = CtsGisMutationService(store)
        stage_text = json.dumps(self._stage_document())
        with patch("MyCiteV2.packages.modules.cross_domain.cts_gis.mutation_service.yaml", None):
            stage_document, metadata = service.parse_stage_input({"stage_text": stage_text})
        self.assertEqual(stage_document["schema"], CTS_GIS_STAGE_INSERT_SCHEMA)
        self.assertEqual(metadata["draft_format"], "json")

    def test_yaml_stage_text_requires_yaml_dependency(self) -> None:
        store = self._store()
        service = CtsGisMutationService(store)
        stage_text = "schema: mycite.v2.cts_gis.stage_insert.v1"
        with patch("MyCiteV2.packages.modules.cross_domain.cts_gis.mutation_service.yaml", None):
            with self.assertRaises(CtsGisMutationError) as context:
                service.parse_stage_input({"stage_text": stage_text})
        self.assertEqual(context.exception.code, "yaml_dependency_missing")


if __name__ == "__main__":
    unittest.main()
