"""Tests for the datum_templates package — recognition + scaffolding."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.datum_templates import (
    DatumTemplate,
    HeaderRowSpec,
    MagnitudeSpec,
    RepeatingArchetypeSpec,
    TemplateRegistry,
    recognize_archetype,
    recognize_archetype_in_registry,
    scaffold_from_template,
)
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRow,
)


def _subscriber_template() -> DatumTemplate:
    return DatumTemplate(
        template_id="fnd_newsletter_contact_log",
        schema="mycite.v2.datum.fnd.newsletter.contact_log.v1",
        sandbox="fnd_csm",
        archetype="fnd_subscriber",
        header_rows=(
            HeaderRowSpec(
                address="0-0-1",
                field_name="schema",
                raw_template="mycite.v2.datum.fnd.newsletter.contact_log.v1",
            ),
            HeaderRowSpec(address="0-0-2", field_name="domain", raw_template="{{domain}}"),
            HeaderRowSpec(address="0-0-3", field_name="msn_id", raw_template="{{msn_id}}"),
        ),
        repeating_archetype=RepeatingArchetypeSpec(
            layer=1,
            magnitudes=(
                MagnitudeSpec(name="email", magnitude_kind="trimmed_string"),
                MagnitudeSpec(name="subscribed", magnitude_kind="boolean"),
                MagnitudeSpec(name="source", magnitude_kind="trimmed_string"),
            ),
        ),
        csv_column_map={"email": "email", "sub": "subscribed", "src": "source"},
    )


class ScaffoldTests(unittest.TestCase):
    def test_scaffold_materializes_header_rows_and_interpolates_placeholders(self) -> None:
        template = _subscriber_template()
        document = scaffold_from_template(
            template,
            msn_id="3-2-3-17-77-1-6-4-1-4",
            document_id="lv.x.fnd_csm.fnd_newsletter_contact_log_example_com." + "f" * 64,
            document_name="contact_log.example_com.json",
            relative_path="sandbox/fnd-csm/contact_log.example_com.json",
            context={"domain": "example.com", "msn_id": "3-2-3-17-77-1-6-4-1-4"},
        )
        self.assertEqual(len(document.rows), 3)
        self.assertEqual(document.rows[1].raw, "example.com")
        self.assertEqual(document.rows[2].raw, "3-2-3-17-77-1-6-4-1-4")
        self.assertEqual(document.tool_id, "fnd_csm")
        self.assertEqual(
            document.document_metadata.get("datum_template_id"),
            "fnd_newsletter_contact_log",
        )

    def test_scaffold_leaves_unfilled_placeholders_alone(self) -> None:
        template = _subscriber_template()
        document = scaffold_from_template(
            template,
            msn_id="x",
            document_id="lv.x.fnd_csm.demo." + "0" * 64,
            document_name="demo.json",
            relative_path="sandbox/fnd-csm/demo.json",
            context={},
        )
        self.assertEqual(document.rows[1].raw, "{{domain}}")


class RecognizeTests(unittest.TestCase):
    def _doc_with_subscriber_rows(
        self,
        rows: tuple[AuthoritativeDatumDocumentRow, ...],
    ) -> AuthoritativeDatumDocument:
        return AuthoritativeDatumDocument(
            document_id="lv.x.fnd_csm.demo." + "1" * 64,
            source_kind="sandbox_source",
            document_name="demo.json",
            relative_path="sandbox/fnd-csm/demo.json",
            canonical_name="demo",
            tool_id="fnd_csm",
            rows=rows,
        )

    def test_recognize_matches_when_every_layer_row_carries_required_magnitudes(self) -> None:
        template = _subscriber_template()
        rows = (
            AuthoritativeDatumDocumentRow(
                datum_address="1-0-1",
                raw=[["1-0-1", "~", "0-0-11"], {"email": "a@b.com", "subscribed": True, "source": "signup"}],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="1-0-2",
                raw=[["1-0-2", "~", "0-0-11"], {"email": "c@d.com", "subscribed": False, "source": "signup"}],
            ),
        )
        report = recognize_archetype(self._doc_with_subscriber_rows(rows), template=template)
        self.assertTrue(report.matched)
        self.assertEqual(report.archetype, "fnd_subscriber")
        self.assertEqual(report.repeating_layer, 1)
        self.assertEqual(report.matched_row_count, 2)
        self.assertEqual(report.total_row_count, 2)

    def test_recognize_rejects_when_a_row_is_missing_required_magnitude(self) -> None:
        template = _subscriber_template()
        rows = (
            AuthoritativeDatumDocumentRow(
                datum_address="1-0-1",
                raw=[["1-0-1", "~", "0-0-11"], {"email": "a@b.com", "subscribed": True, "source": "signup"}],
            ),
            AuthoritativeDatumDocumentRow(
                datum_address="1-0-2",
                raw=[["1-0-2", "~", "0-0-11"], {"email": "missing-source", "subscribed": True}],
            ),
        )
        report = recognize_archetype(self._doc_with_subscriber_rows(rows), template=template)
        self.assertFalse(report.matched)
        self.assertEqual(report.matched_row_count, 1)
        self.assertEqual(report.total_row_count, 2)

    def test_recognize_returns_unmatched_when_repeating_layer_is_empty(self) -> None:
        template = _subscriber_template()
        report = recognize_archetype(self._doc_with_subscriber_rows(()), template=template)
        self.assertFalse(report.matched)
        self.assertEqual(report.matched_row_count, 0)
        self.assertEqual(report.total_row_count, 0)


class TemplateRegistryTests(unittest.TestCase):
    def test_registry_loads_yaml_templates_from_disk(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.yaml"
            path.write_text(
                """
template_id: demo
schema: mycite.v2.datum.demo.v1
sandbox: fnd_csm
archetype: demo_archetype
header_rows:
  - { address: "0-0-1", field: schema, raw: "demo" }
repeating_archetype:
  layer: 1
  value_group_reference_design:
    name: { magnitude_kind: trimmed_string, required: true }
csv_column_map:
  name: name
""",
                encoding="utf-8",
            )
            registry = TemplateRegistry(template_dir=Path(tmp))
            template = registry.get("demo")
            self.assertIsNotNone(template)
            assert template is not None
            self.assertEqual(template.archetype, "demo_archetype")
            self.assertEqual(template.csv_column_map, {"name": "name"})
            self.assertEqual([t.template_id for t in registry.by_archetype("demo_archetype")], ["demo"])

    def test_registry_loads_real_fnd_newsletter_template(self) -> None:
        # Sanity check on the bundled template at
        # MyCiteV2/data/datum_templates/fnd_newsletter_contact_log.yaml.
        registry = TemplateRegistry()
        template = registry.get("fnd_newsletter_contact_log")
        self.assertIsNotNone(template)
        assert template is not None
        self.assertEqual(template.sandbox, "fnd_csm")
        self.assertEqual(template.archetype, "fnd_subscriber")
        # v2 column map keys the dirty-CSV headers; values are working
        # magnitude names that the intake pipeline composes into the
        # final per-contact row.
        self.assertEqual(template.csv_column_map["E-mail 1 - Value"], "email_ascii")
        self.assertEqual(template.csv_column_map["First Name"], "_name_first")


class RegistryRecognitionIntegrationTests(unittest.TestCase):
    def test_registry_match_returns_first_template_that_matches(self) -> None:
        registry = TemplateRegistry()
        document = AuthoritativeDatumDocument(
            document_id="lv.x.fnd_csm.demo." + "2" * 64,
            source_kind="sandbox_source",
            document_name="demo.json",
            relative_path="sandbox/fnd-csm/demo.json",
            canonical_name="demo",
            tool_id="fnd_csm",
            rows=(
                AuthoritativeDatumDocumentRow(
                    datum_address="1-0-1",
                    raw=[
                        ["1-0-1", "~", "0-0-11"],
                        # v2 row carries ASCII + bacillete-encoded
                        # binary + confirmed flags. Recognizer keys on
                        # presence of every required magnitude.
                        {
                            "email_ascii": "a@b.com",
                            "email_binary": "141100142056143157155",
                            "email_confirmed": True,
                            "name_confirmed": False,
                            "subscribed": True,
                            "source": "signup",
                            "last_newsletter_sent_at": "",
                            "send_count": 0,
                        },
                    ],
                ),
            ),
        )
        report = recognize_archetype_in_registry(document, registry)
        self.assertIsNotNone(report)
        assert report is not None
        self.assertEqual(report.template_id, "fnd_newsletter_contact_log")


if __name__ == "__main__":
    unittest.main()
