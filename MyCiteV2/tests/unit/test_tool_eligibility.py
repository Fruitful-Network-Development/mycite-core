"""Unit tests for recognize_applicable_tools().

Covers:
  - extensions are excluded from the palette
  - archetype intersection match (document_metadata)
  - source_kind intersection match
  - per-row archetype reached via hyphae chain widens the archetype set
  - deterministic, tool_id-sorted output ordering
  - empty datum_address returns ()
  - unknown datum_address returns () (recognizer swallows ValueError)
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.ports.datum_store.contracts import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.state_machine.portal_shell.shell import (
    ARCHETYPE_HYPHAE_RUDI,
    ARCHETYPE_SAMRAS_FAMILY,
    CTS_GIS_TOOL_ENTRYPOINT_ID,
    CTS_GIS_TOOL_ROUTE,
    CTS_GIS_TOOL_SURFACE_ID,
    SURFACE_POSTURE_PALETTE_TARGET,
    TOOL_KIND_GENERAL,
    UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
    PortalToolRegistryEntry,
)
from MyCiteV2.packages.state_machine.portal_shell.tool_eligibility import (
    recognize_applicable_tools,
)


def _palette_tool(
    tool_id: str,
    *,
    applies_to_archetype: tuple[str, ...] = (),
    applies_to_source_kind: tuple[str, ...] = (),
) -> PortalToolRegistryEntry:
    return PortalToolRegistryEntry(
        tool_id=tool_id,
        label=tool_id,
        surface_id=CTS_GIS_TOOL_SURFACE_ID,
        entrypoint_id=CTS_GIS_TOOL_ENTRYPOINT_ID,
        route=CTS_GIS_TOOL_ROUTE,
        tool_kind=TOOL_KIND_GENERAL,
        surface_posture=SURFACE_POSTURE_PALETTE_TARGET,
        read_write_posture="write",
        applies_to_archetype=applies_to_archetype,
        applies_to_source_kind=applies_to_source_kind,
    )


def _extension(tool_id: str) -> PortalToolRegistryEntry:
    return PortalToolRegistryEntry(
        tool_id=tool_id,
        label=tool_id,
        surface_id=UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
        entrypoint_id="portal.utilities." + tool_id,
        route="/portal/utilities/tool-exposure",
        tool_kind=TOOL_KIND_GENERAL,
        surface_posture=SURFACE_POSTURE_PALETTE_TARGET,
        read_write_posture="write",
        is_extension=True,
    )


def _build_doc(
    *,
    source_kind: str = "sandbox_source",
    archetype: str | None = None,
    rows: list[tuple[str, dict]] | None = None,
) -> AuthoritativeDatumDocument:
    metadata: dict = {}
    if archetype is not None:
        metadata["archetype"] = archetype
    row_specs = rows if rows is not None else [("0-0-1", {"value": "a"})]
    return AuthoritativeDatumDocument(
        document_id="lv.fnd.test.fixture.deadbeef",
        source_kind=source_kind,
        document_name="fixture",
        relative_path="fixture.json",
        canonical_name="fixture",
        document_metadata=metadata or None,
        rows=tuple(
            AuthoritativeDatumDocumentRow(datum_address=addr, raw=raw)
            for addr, raw in row_specs
        ),
    )


class RecognizeApplicableToolsTests(unittest.TestCase):
    def test_extensions_are_excluded(self) -> None:
        registry = (
            _extension("ext_aws_email"),
            _palette_tool("cts_gis", applies_to_source_kind=("sandbox_source",)),
        )
        result = recognize_applicable_tools(_build_doc(), "0-0-1", registry)
        self.assertEqual([e.tool_id for e in result], ["cts_gis"])

    def test_archetype_intersection_match_from_document_metadata(self) -> None:
        registry = (
            _palette_tool("cts_gis", applies_to_archetype=(ARCHETYPE_SAMRAS_FAMILY,)),
            _palette_tool("other", applies_to_archetype=("unrelated_archetype",)),
        )
        doc = _build_doc(archetype=ARCHETYPE_SAMRAS_FAMILY)
        result = recognize_applicable_tools(doc, "0-0-1", registry)
        self.assertEqual([e.tool_id for e in result], ["cts_gis"])

    def test_source_kind_intersection_match(self) -> None:
        registry = (
            _palette_tool("cts_gis", applies_to_source_kind=("sandbox_source",)),
            _palette_tool("other", applies_to_source_kind=("system_anthology",)),
        )
        doc = _build_doc(source_kind="sandbox_source")
        result = recognize_applicable_tools(doc, "0-0-1", registry)
        self.assertEqual([e.tool_id for e in result], ["cts_gis"])

    def test_per_row_archetype_widens_set_via_hyphae_chain(self) -> None:
        # Row 0-0-2 declares an archetype; its hyphae chain includes 0-0-1 and 0-0-2.
        # A tool applicable to that row's archetype should be offered even when the
        # document-level metadata has no archetype set.
        registry = (
            _palette_tool("hyphae_tool", applies_to_archetype=(ARCHETYPE_HYPHAE_RUDI,)),
        )
        doc = _build_doc(
            rows=[
                ("0-0-1", {"value": "rudi-1"}),
                ("0-0-2", {"value": "rudi-2", "archetype": ARCHETYPE_HYPHAE_RUDI, "refs": ["0-0-1"]}),
            ],
        )
        result = recognize_applicable_tools(doc, "0-0-2", registry)
        self.assertEqual([e.tool_id for e in result], ["hyphae_tool"])

    def test_deterministic_tool_id_sort_order(self) -> None:
        registry = (
            _palette_tool("zeta", applies_to_source_kind=("sandbox_source",)),
            _palette_tool("alpha", applies_to_source_kind=("sandbox_source",)),
            _palette_tool("mu", applies_to_source_kind=("sandbox_source",)),
        )
        result = recognize_applicable_tools(_build_doc(), "0-0-1", registry)
        self.assertEqual([e.tool_id for e in result], ["alpha", "mu", "zeta"])

    def test_empty_datum_address_returns_empty(self) -> None:
        registry = (_palette_tool("cts_gis", applies_to_source_kind=("sandbox_source",)),)
        self.assertEqual(recognize_applicable_tools(_build_doc(), "", registry), ())

    def test_unknown_datum_address_returns_empty(self) -> None:
        registry = (_palette_tool("cts_gis", applies_to_source_kind=("sandbox_source",)),)
        self.assertEqual(
            recognize_applicable_tools(_build_doc(), "9-9-9", registry), ()
        )

    def test_no_match_returns_empty(self) -> None:
        registry = (
            _palette_tool("cts_gis", applies_to_source_kind=("system_anthology",)),
        )
        doc = _build_doc(source_kind="sandbox_source")
        self.assertEqual(recognize_applicable_tools(doc, "0-0-1", registry), ())


class ExtensionFieldValidationTests(unittest.TestCase):
    """Phase 1 contract: is_extension=True requires UTILITIES_TOOL_EXPOSURE_SURFACE_ID."""

    def test_extension_must_use_utilities_surface_id(self) -> None:
        with self.assertRaises(ValueError):
            PortalToolRegistryEntry(
                tool_id="bad_extension",
                label="bad",
                surface_id=CTS_GIS_TOOL_SURFACE_ID,  # wrong surface for an extension
                entrypoint_id="portal.utilities.bad",
                route="/portal/utilities/tool-exposure",
                tool_kind=TOOL_KIND_GENERAL,
                surface_posture=SURFACE_POSTURE_PALETTE_TARGET,
                read_write_posture="write",
                is_extension=True,
            )

    def test_extension_with_utilities_surface_id_constructs(self) -> None:
        entry = PortalToolRegistryEntry(
            tool_id="ext_paypal",
            label="PayPal",
            surface_id=UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
            entrypoint_id="portal.utilities.paypal",
            route="/portal/utilities/tool-exposure",
            tool_kind=TOOL_KIND_GENERAL,
            surface_posture=SURFACE_POSTURE_PALETTE_TARGET,
            read_write_posture="write",
            is_extension=True,
        )
        self.assertTrue(entry.is_extension)
        self.assertEqual(entry.surface_id, UTILITIES_TOOL_EXPOSURE_SURFACE_ID)

    def test_to_dict_includes_new_fields(self) -> None:
        entry = _palette_tool(
            "cts_gis",
            applies_to_archetype=(ARCHETYPE_SAMRAS_FAMILY,),
            applies_to_source_kind=("sandbox_source",),
        )
        payload = entry.to_dict()
        self.assertEqual(payload["applies_to_archetype"], [ARCHETYPE_SAMRAS_FAMILY])
        self.assertEqual(payload["applies_to_source_kind"], ["sandbox_source"])
        self.assertFalse(payload["is_extension"])
        self.assertEqual(entry.surface_id, CTS_GIS_TOOL_SURFACE_ID)


if __name__ == "__main__":
    unittest.main()
