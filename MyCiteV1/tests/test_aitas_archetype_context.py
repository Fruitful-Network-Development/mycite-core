from __future__ import annotations

import sys
import unittest
from pathlib import Path

portals_root = Path(__file__).resolve().parents[1] / "instances"
token = str(portals_root)
if token not in sys.path:
    sys.path.insert(0, token)

from _shared.portal.data_engine.aitas_context import (  # noqa: E402
    inspect_archetype_context,
    inspect_archetype_trace,
    list_derived_archetype_bindings,
)
from _shared.portal.data_engine.archetypes import get_archetype_definition, list_archetype_definitions  # noqa: E402


def _anthology_fixture(*, target_id: str = "10-1-3") -> dict:
    return {
        "rows": [
            {
                "identifier": "10-1-1",
                "label": "ASCII root",
                "pairs": [],
                "magnitude": '{"family":"ascii"}',
            },
            {
                "identifier": "10-1-2",
                "label": "Babel bridge",
                "pairs": [{"reference": "10-1-1", "magnitude": "inherits"}],
                "magnitude": '{"kind":"babel"}',
            },
            {
                "identifier": target_id,
                "label": "ASCII Babel 64 Field",
                "pairs": [{"reference": "10-1-2", "magnitude": "inherits"}],
                "magnitude": '{"field_length":64,"alphabet_cardinality":256}',
                "source_identifier": "99-1-500",
            },
        ]
    }


class AitasArchetypeContextTests(unittest.TestCase):
    def test_registry_contains_ascii_babel_64_anchor(self):
        definitions = list_archetype_definitions()
        keys = [item.archetype_key for item in definitions]
        self.assertIn("ascii_babel_64", keys)
        definition = get_archetype_definition("ascii_babel_64")
        self.assertIsNotNone(definition)
        self.assertEqual(definition.constraint_expectation.get("field_length"), 64)
        self.assertEqual(definition.constraint_expectation.get("alphabet_cardinality"), 256)

    def test_recognition_builds_binding_from_chain_and_constraints(self):
        payload = inspect_archetype_context(
            datum_ref="10-1-3",
            local_msn_id="1-2-3",
            anthology_payload=_anthology_fixture(),
            now_fn=lambda: 1700000000,
        )
        self.assertTrue(payload.get("ok"))
        archetype = (((payload.get("aitas") or {}).get("archetype")) or {})
        self.assertTrue(archetype.get("recognized"))
        binding = archetype.get("binding") or {}
        self.assertEqual(binding.get("archetype_key"), "ascii_babel_64")
        self.assertEqual(binding.get("local_ref"), "10-1-3")
        self.assertEqual(binding.get("canonical_ref"), "1-2-3.10-1-3")
        self.assertEqual(binding.get("source_identifier"), "99-1-500")
        self.assertEqual(((binding.get("compiled_constraint") or {}).get("field_length")), 64)
        self.assertEqual(((binding.get("compiled_constraint") or {}).get("alphabet_cardinality")), 256)
        self.assertEqual(binding.get("derived_at_unix_ms"), 1700000000)

    def test_recognition_not_tied_to_one_row_identifier(self):
        payload = inspect_archetype_context(
            datum_ref="10-1-99",
            local_msn_id="1-2-3",
            anthology_payload=_anthology_fixture(target_id="10-1-99"),
        )
        self.assertTrue(payload.get("ok"))
        binding = ((((payload.get("aitas") or {}).get("archetype")) or {}).get("binding") or {})
        self.assertEqual(binding.get("archetype_key"), "ascii_babel_64")
        self.assertEqual(binding.get("local_ref"), "10-1-99")

    def test_trace_returns_visualization_ready_nodes_and_edges(self):
        payload = inspect_archetype_trace(
            datum_ref="10-1-3",
            local_msn_id="1-2-3",
            anthology_payload=_anthology_fixture(),
        )
        self.assertTrue(payload.get("ok"))
        trace = payload.get("trace") or {}
        nodes = trace.get("nodes") or []
        edges = trace.get("edges") or []
        self.assertGreaterEqual(len(nodes), 3)
        self.assertTrue(any(item.get("kind") == "archetype" for item in nodes))
        self.assertTrue(any(item.get("kind") == "inherits" for item in edges))

    def test_list_derived_bindings_remains_anthology_derived(self):
        payload = list_derived_archetype_bindings(
            local_msn_id="1-2-3",
            anthology_payload=_anthology_fixture(),
            limit=10,
        )
        self.assertTrue(payload.get("ok"))
        bindings = payload.get("bindings") or []
        self.assertEqual(len(bindings), 1)
        self.assertEqual((bindings[0] or {}).get("archetype_key"), "ascii_babel_64")

    def test_compiled_constraint_includes_samras_structure_when_chain_is_samras_backed(self):
        payload = {
            "rows": [
                {"identifier": "1-1-3", "label": "txa-SAMRAS", "pairs": [], "magnitude": "3-3-0-0-1-1-4,0-0-0-0-8"},
                {"identifier": "2-1-12", "label": "SAMRAS-space-txa", "pairs": [{"reference": "1-1-3", "magnitude": "1"}], "magnitude": "1"},
                {"identifier": "3-1-5", "label": "txa_id-babelette-txa_id", "pairs": [{"reference": "2-1-12", "magnitude": "0"}], "magnitude": "0"},
                {"identifier": "8-5-1", "label": "product-profile", "pairs": [{"reference": "3-1-5", "magnitude": "abc"}], "magnitude": "abc"},
            ]
        }
        inspected = inspect_archetype_context(
            datum_ref="8-5-1",
            local_msn_id="1-2-3",
            anthology_payload=payload,
        )
        self.assertTrue(inspected.get("ok"))
        compiled = (((inspected.get("aitas") or {}).get("archetype") or {}).get("compiled_constraint") or {})
        self.assertEqual(compiled.get("constraint_family"), "samras")
        self.assertEqual(compiled.get("value_kind"), "txa_id")
        self.assertTrue(compiled.get("descriptor_digest"))


if __name__ == "__main__":
    unittest.main()
