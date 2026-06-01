"""Phase 4a — canonical hyphae value + flag registry + flag-first binding.

Proves the additive foundation:
- ``compile_hyphae_value`` is address-independent (re-nesting preserves it).
- ``build_minimum_complete_path`` excludes the rudi-range fill.
- a flag with a ``lens_id`` makes the lens resolver pick that lens FIRST.
- a tool whose ``applies_to_hyphae_value`` matches is unioned into eligibility.
- with an EMPTY registry / no flag inputs, every path is behavior-preserving.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.datum_ops import labels
from MyCiteV2.packages.core.datum_semantics import (
    build_minimum_complete_path,
    compile_hyphae_value,
)
from MyCiteV2.packages.core.hyphae_flags import (
    HyphaeFlag,
    HyphaeFlagRegistry,
    raise_flags,
)
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.state_machine.lens import DEFAULT_DATUM_LENS_REGISTRY, resolve_datum_lens
from MyCiteV2.packages.state_machine.portal_shell import PortalToolRegistryEntry
from MyCiteV2.packages.state_machine.portal_shell.tool_eligibility import recognize_applicable_tools

_NID, _TITLE = "rf.3-1-1", "rf.3-1-2"


def _doc(name: str, rows: list[tuple[str, object]]) -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id=f"lv.3-2-3-17-77-1-6-4-1-4.s.{name}." + ("a" * 64),
        source_kind="sandbox_source", document_name=name, relative_path=f"s/{name}.json",
        rows=tuple(AuthoritativeDatumDocumentRow(datum_address=a, raw=r) for a, r in rows),
    )


def _genus_leaf(leaf_addr: str) -> AuthoritativeDatumDocument:
    return _doc("txa", [
        ("4-2-1", [["4-2-1", _NID, "1", _TITLE, labels.encode_label_bits("g")], ["g"]]),
        (leaf_addr, [[leaf_addr, _NID, "1-1", "2-1", "4-2-1"], ["leaf"]]),
    ])


class CanonicalHyphaeValueTests(unittest.TestCase):
    def _doc_with_rudis(self, r1_title: str):
        # A datum (1-1-1) that references rudi 0-0-5; 0-0-1 is a PRECEDING rudi it
        # does NOT reference directly. Per the MOS spec the canonical hyphae value
        # must still account for 0-0-1 (ordinal context: "include 0-0-1 .. 0-0-5").
        return _doc("anchor", [
            ("0-0-1", [["0-0-1", "~", "0-0-0"], [r1_title]]),
            ("0-0-5", [["0-0-5", "~", "0-0-0"], ["nop"]]),
            ("1-1-1", [["1-1-1", "0-0-5", "128"], ["thing"]]),
        ])

    def test_value_carries_ordinal_rudi_context(self) -> None:
        # 1-1-1 references only 0-0-5, but changing the content of the preceding,
        # UNREFERENCED rudi 0-0-1 must change 1-1-1's canonical hyphae value —
        # proving the value is anchored to the full ordinal rudi scaffold.
        v_a = compile_hyphae_value(self._doc_with_rudis("top"), "1-1-1")
        v_b = compile_hyphae_value(self._doc_with_rudis("TOP-changed"), "1-1-1")
        self.assertTrue(v_a.startswith("sha256:"))
        self.assertNotEqual(v_a, v_b)

    def test_minimum_complete_path_is_the_focus_closure(self) -> None:
        # build_minimum_complete_path is the focus-selection (the downward
        # reference closure), NOT the rudi-complete value basis: it includes only
        # referenced datums, target last. The rudi scaffold is added when the
        # VALUE is compiled (see test_value_carries_ordinal_rudi_context).
        doc = _doc("txa", [
            ("0-0-1", [["0-0-1", "~", "x"], ["r1"]]),
            ("0-0-3", [["0-0-3", "~", "y"], ["r3"]]),
            ("4-2-1", [["4-2-1", _NID, "1", "2-1", "0-0-3"], ["leaf"]]),
        ])
        path = build_minimum_complete_path(doc, "4-2-1")
        self.assertIn("0-0-3", path)        # referenced → in the focus closure
        self.assertNotIn("0-0-1", path)     # unreferenced → not in the closure
        self.assertEqual(path[-1], "4-2-1")  # target last

    def test_absent_address_raises(self) -> None:
        with self.assertRaises(ValueError):
            compile_hyphae_value(_genus_leaf("4-2-2"), "9-9-9")


class FlagRegistryTests(unittest.TestCase):
    def test_empty_registry_raises_nothing(self) -> None:
        self.assertEqual(raise_flags(_genus_leaf("4-2-2"), registry=HyphaeFlagRegistry()), {})

    def test_raise_flags_matches_compiled_value(self) -> None:
        doc = _genus_leaf("4-2-2")
        value = compile_hyphae_value(doc, "4-2-2")
        reg = HyphaeFlagRegistry()
        reg.register(HyphaeFlag(hyphae_value=value, tool_id="t_demo", lens_id="numeric_hyphen", label="Demo"))
        raised = raise_flags(doc, registry=reg)
        self.assertIn("4-2-2", raised)
        self.assertEqual(raised["4-2-2"].tool_ids, ("t_demo",))
        self.assertEqual(raised["4-2-2"].lens_id, "numeric_hyphen")

    def test_flag_requires_a_binding(self) -> None:
        with self.assertRaises(ValueError):
            HyphaeFlag(hyphae_value="sha256:x")


class FlagFirstLensTests(unittest.TestCase):
    def test_unset_flag_lens_is_behavior_preserving(self) -> None:
        baseline = resolve_datum_lens(recognized_family="samras")
        flagged = resolve_datum_lens(recognized_family="samras", flag_lens_id="")
        self.assertEqual(baseline.lens_id, flagged.lens_id)
        self.assertEqual(baseline.matched_on, flagged.matched_on)

    def test_flag_lens_wins_over_family(self) -> None:
        # family 'samras' would resolve numeric_hyphen; the flag forces binary_text.
        res = resolve_datum_lens(recognized_family="samras", flag_lens_id="binary_text")
        self.assertEqual(res.lens_id, "binary_text")
        self.assertEqual(res.matched_on, "hyphae_flag")

    def test_unknown_flag_lens_falls_through(self) -> None:
        res = resolve_datum_lens(recognized_family="samras", flag_lens_id="no_such_lens")
        self.assertEqual(res.matched_on, "family")

    def test_lens_by_id_covers_builtins(self) -> None:
        for lens_id in ("identity", "numeric_hyphen", "binary_text"):
            self.assertIsNotNone(DEFAULT_DATUM_LENS_REGISTRY.lens_by_id(lens_id))


class FlagToolEligibilityTests(unittest.TestCase):
    def _tool(self, **kw) -> PortalToolRegistryEntry:
        from MyCiteV2.packages.state_machine.portal_shell import (
            SURFACE_POSTURE_PALETTE_TARGET,
            TOOL_KIND_GENERAL,
            WORKBENCH_UI_TOOL_SURFACE_ID,
        )
        defaults = dict(
            tool_id="t_hyphae", label="Hyphae Tool", surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
            entrypoint_id="portal.shell", route="/portal/system", tool_kind=TOOL_KIND_GENERAL,
            surface_posture=SURFACE_POSTURE_PALETTE_TARGET, read_write_posture="read-only",
        )
        defaults.update(kw)
        return PortalToolRegistryEntry(**defaults)

    def test_tool_bound_by_hyphae_value_is_eligible(self) -> None:
        doc = _genus_leaf("4-2-2")
        value = compile_hyphae_value(doc, "4-2-2")
        tool = self._tool(applies_to_hyphae_value=(value,))
        # Without passing the value → not eligible (no archetype/source match).
        self.assertEqual(recognize_applicable_tools(doc, "4-2-2", (tool,)), ())
        # With the datum's compiled value → unioned in.
        eligible = recognize_applicable_tools(doc, "4-2-2", (tool,), hyphae_values=[value])
        self.assertEqual([e.tool_id for e in eligible], ["t_hyphae"])


if __name__ == "__main__":
    unittest.main()
