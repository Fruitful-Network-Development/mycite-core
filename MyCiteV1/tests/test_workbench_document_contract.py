from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _shared.portal.application.workbench.catalog import DocumentCatalogService
from _shared.portal.application.workbench.document_contract import DOCUMENT_SCHEMA, build_workbench_document
from _shared.portal.sandbox.engine import SandboxEngine
from _shared.portal.sandbox.local_resource_lifecycle import LocalResourceLifecycleService


class WorkbenchDocumentContractTests(unittest.TestCase):
    def test_build_workbench_document_has_required_sections(self) -> None:
        payload = build_workbench_document(
            document_id="workbench:test:one",
            instance_id="fnd",
            logical_key="one",
            display_name="One",
            family_kind="resource",
            family_type="samras",
            scope_kind="local",
            payload={"hello": "world"},
        )
        self.assertEqual(payload.get("schema"), DOCUMENT_SCHEMA)
        self.assertIn("identity", payload)
        self.assertIn("family", payload)
        self.assertIn("scope", payload)
        self.assertIn("payload", payload)
        self.assertIn("metadata", payload)
        self.assertIn("capabilities", payload)
        self.assertIn("provenance", payload)
        self.assertIn("persistence", payload)
        self.assertIn("mutability", payload)
        self.assertIn("revision", payload)
        self.assertIn("inheritance", payload)

    def test_catalog_local_inventory_adds_documents(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        engine = SandboxEngine(data_root=root)
        local = LocalResourceLifecycleService(
            data_root=root,
            sandbox_engine=engine,
            local_msn_id="3-2-3-17-77-1-6-4-1-4",
        )
        local.create(resource_kind="samras_msn", resource_name="samras.msn", seed_payload={"rows": {}})
        catalog = DocumentCatalogService(
            data_root=root,
            local_inventory_provider=local.list_local_inventory,
            sandbox_engine=engine,
            instance_id_provider=lambda: "fnd",
        )
        payload = catalog.local_inventory_payload()
        self.assertEqual(payload.get("schema"), "mycite.portal.resources.inventory.v2")
        self.assertEqual(payload.get("documents_schema"), DOCUMENT_SCHEMA)
        self.assertEqual(len(payload.get("documents") or []), 1)
        document = (payload.get("documents") or [])[0]
        self.assertEqual(document.get("scope", {}).get("kind"), "resource")
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
