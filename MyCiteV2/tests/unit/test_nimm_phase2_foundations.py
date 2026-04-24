from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.state_machine.aitas import AitasContext, merge_aitas_context
from MyCiteV2.packages.state_machine.lens import EmailAddressLens, SamrasTitleLens, SecretReferenceLens, TrimmedStringLens
from MyCiteV2.packages.state_machine.nimm import (
    MINIMAL_NIMM_VERBS,
    NIMM_DIRECTIVE_GRAMMAR_V1,
    NIMM_DIRECTIVE_SCHEMA_V1,
    NIMM_ENVELOPE_SCHEMA_V1,
    VERB_INVESTIGATE,
    VERB_MANIPULATE,
    handle_nimm_investigate,
    NimmDirective,
    NimmDirectiveEnvelope,
    NimmTargetAddress,
    StagingArea,
    cts_gis_runtime_action_kind,
    validate_nimm_directive_payload,
    mutation_action_endpoint,
    normalize_mutation_lifecycle_action,
    normalize_nimm_verb,
)
from MyCiteV2.packages.state_machine.portal_shell import PortalShellState, build_nimm_envelope_for_shell_state


class NimmPhase2FoundationTests(unittest.TestCase):
    def test_nimm_directive_round_trips_with_versioned_schema(self) -> None:
        directive = NimmDirective(
            verb=VERB_MANIPULATE,
            target_authority="system",
            document_id="sandbox:cts_gis:test-doc",
            targets=(
                {"file_key": "anthology", "datum_address": "4-1-77"},
                {"file_key": "anthology", "datum_address": "4-1-78", "object_ref": "node-1"},
            ),
            payload={"operation": "insert"},
        )
        payload = directive.to_dict()
        self.assertEqual(payload["schema"], NIMM_DIRECTIVE_SCHEMA_V1)
        self.assertEqual(payload["verb"], VERB_MANIPULATE)
        reparsed = NimmDirective.from_dict(payload)
        self.assertEqual(reparsed.to_dict(), payload)

    def test_minimal_nimm_aliases_normalize_to_canonical_verbs(self) -> None:
        self.assertEqual(MINIMAL_NIMM_VERBS, ("nav", "inv", "med", "man"))
        self.assertEqual(NIMM_DIRECTIVE_GRAMMAR_V1["minimal_aliases"]["man"], VERB_MANIPULATE)
        self.assertEqual(normalize_nimm_verb("nav"), "navigate")
        directive = NimmDirective(
            verb="man",
            target_authority="system",
            targets=({"file_key": "anthology"},),
        )
        self.assertEqual(directive.verb, VERB_MANIPULATE)

    def test_aitas_context_merge_applies_overrides_without_mutation(self) -> None:
        defaults = AitasContext(
            attention="3-2-3-17-77-1-6-4-1-4.4-1-77",
            intention="mediate",
            time="present",
            archetype="samras_nominal",
            scope="sandbox",
        )
        merged = merge_aitas_context(
            defaults=defaults,
            overrides={
                "intention": "manipulate",
                "time_directive": "future",
            },
        )
        self.assertEqual(merged.attention, defaults.attention)
        self.assertEqual(merged.intention, "manipulate")
        self.assertEqual(merged.time, "future")
        self.assertEqual(merged.archetype, "samras_nominal")
        self.assertEqual(merged.scope, "sandbox")

    def test_staging_area_compiles_manipulation_envelope(self) -> None:
        stage = StagingArea()
        stage = stage.stage_with_lens(
            target={"file_key": "anthology", "datum_address": "4-1-77"},
            lens=TrimmedStringLens(),
            display_value="  updated value  ",
        )
        envelope = stage.compile_manipulation_envelope(
            target_authority="system",
            document_id="sandbox:cts_gis:test-doc",
            aitas={"intention": "manipulate", "scope": "sandbox"},
        )
        payload = envelope.to_dict()
        self.assertEqual(payload["schema"], NIMM_ENVELOPE_SCHEMA_V1)
        self.assertEqual(payload["directive"]["verb"], VERB_MANIPULATE)
        staged_values = payload["directive"]["payload"]["staged_values"]
        self.assertEqual(staged_values[0]["canonical_value"], "updated value")
        reparsed = NimmDirectiveEnvelope.from_dict(payload)
        self.assertEqual(reparsed.to_dict(), payload)

    def test_mutation_action_endpoint_validates_allowed_actions(self) -> None:
        self.assertEqual(mutation_action_endpoint("stage"), "/portal/api/v2/mutations/stage")
        self.assertEqual(mutation_action_endpoint("stage_insert_yaml"), "/portal/api/v2/mutations/stage")
        self.assertEqual(cts_gis_runtime_action_kind("preview"), "preview_apply")
        self.assertEqual(normalize_mutation_lifecycle_action("apply_stage"), "apply")
        with self.assertRaisesRegex(ValueError, "mutation action must be one of"):
            mutation_action_endpoint("publish")

    def test_portal_shell_can_build_nimm_envelope_from_shell_state(self) -> None:
        state = PortalShellState(
            active_surface_id="system.root",
            focus_path=(
                {"level": "sandbox", "id": "fnd"},
                {"level": "file", "id": "anthology"},
                {"level": "datum", "id": "4-1-77"},
            ),
            verb="mediate",
        )
        envelope = build_nimm_envelope_for_shell_state(
            shell_state=state,
            target_authority="system",
            document_id="sandbox:cts_gis:test-doc",
            aitas_defaults={"scope": "sandbox"},
            aitas_overrides={"intention": "mediate"},
        )
        payload = envelope.to_dict()
        self.assertEqual(payload["directive"]["verb"], "mediate")
        self.assertEqual(payload["aitas"]["intention"], "mediate")
        self.assertEqual(payload["directive"]["targets"][0]["datum_address"], "4-1-77")

    def test_non_navigation_handlers_are_stubbed_as_deferred(self) -> None:
        directive = NimmDirective(
            verb=VERB_INVESTIGATE,
            target_authority="system",
            targets=({"file_key": "anthology"},),
        )
        with self.assertRaises(NotImplementedError):
            handle_nimm_investigate(directive)

    def test_nimm_validator_rejects_invalid_payloads(self) -> None:
        with self.assertRaisesRegex(ValueError, "nimm.target_authority or nimm.document_id is required"):
            validate_nimm_directive_payload(
                {
                    "schema": NIMM_DIRECTIVE_SCHEMA_V1,
                    "verb": "navigate",
                    "targets": [{"file_key": "anthology"}],
                }
            )
        with self.assertRaisesRegex(ValueError, "nimm.verb must be one of"):
            validate_nimm_directive_payload(
                {
                    "schema": NIMM_DIRECTIVE_SCHEMA_V1,
                    "verb": "publish",
                    "target_authority": "system",
                    "targets": [{"file_key": "anthology"}],
                }
            )
        with self.assertRaisesRegex(ValueError, "nimm.targets must contain at least one target"):
            validate_nimm_directive_payload(
                {
                    "schema": NIMM_DIRECTIVE_SCHEMA_V1,
                    "verb": "navigate",
                    "target_authority": "system",
                    "targets": [],
                }
            )
        with self.assertRaisesRegex(ValueError, "nimm.target requires at least one"):
            NimmTargetAddress()

    def test_lens_transform_is_applied_during_stage_compilation(self) -> None:
        stage = StagingArea().stage_with_lens(
            target={"file_key": "anthology", "datum_address": "4-1-77"},
            lens=TrimmedStringLens(),
            display_value="  MAIN STREET  ",
        )
        staged = stage.to_dict()["staged_values"][0]
        self.assertEqual(staged["lens_id"], "trimmed_string")
        self.assertEqual(staged["canonical_value"], "MAIN STREET")

    def test_tool_lenses_validate_and_encode_canonical_values(self) -> None:
        self.assertEqual(SamrasTitleLens().encode("  Main Street  "), "MAIN STREET")
        self.assertEqual(SamrasTitleLens().validate_display("Main Street"), ())
        self.assertEqual(EmailAddressLens().encode("USER@EXAMPLE.COM"), "user@example.com")
        self.assertEqual(EmailAddressLens().validate_display("not-an-email"), ("email_invalid",))
        self.assertEqual(SecretReferenceLens().validate_display("smtp/password/value"), ("secret_reference_must_not_contain_secret_value",))


if __name__ == "__main__":
    unittest.main()
