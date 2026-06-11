"""Unit tests for the leaflet TYPE registry / by-type indexer (resource_types).

Hermetic: each test seeds a temp ``webapps_root`` with a small but representative
master-manifest ``type_tree`` + sample leaflets, then pins the loader, filename
TYPE parser, nearest-node matcher, by-type index (+ PII boundary + rollup),
viewer routing, and the generic structured view.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.utilities_extensions import resource_types as rt

_MANIFEST = """\
manifest_kind: mycite_schema
type_tree:
  artifact:
    label: Artifact
    icon: icon-tag
    children:
      profile:
        label: Profile
        icon: icon-contacts
        children:
          legal_entity:
            label: Legal Entity
            icon: icon-leaf
            children:
              ag:
                label: Agriculture
                icon: icon-leaf
                children:
                  producer:
                    label: Producers
                    icon: icon-leaf
                    icon_ref: 0000-00-00.artifact-icon.mycite.farm
                    children:
                      crop: {label: Crop, icon: icon-crop, icon_ref: 0000-00-00.artifact-icon.mycite.crop}
                      apiary: {label: Apiary, icon: icon-apiary, icon_ref: 0000-00-00.artifact-icon.mycite.apiary}
          natural_entity: {label: Person, icon: icon-contacts}
      icon: {label: Icon, icon: icon-tag}
      event:
        label: Event
        icon: icon-calendar
        children:
          hebdomadal: {label: Weekly, icon: icon-calendar}
          seasonal: {label: Seasonal, icon: icon-calendar}
  record:
    label: Record
    icon: icon-archive
    children:
      analytics: {label: Analytics, icon: icon-analytics}
default_style: {label: Other, color: '#95a5a6', icon: icon-leaf}
"""


def _seed(root: Path) -> Path:
    sc = root / "clients" / "_shared" / "site-core"
    for d in ("schema", "profiles", "icon", "event", "custom", "analytics"):
        (sc / d).mkdir(parents=True, exist_ok=True)
    (sc / "schema" / "0000-00-00.artifact-manifest.mycite.schema.yaml").write_text(_MANIFEST, encoding="utf-8")
    (sc / "profiles" / "0000-00-00.artifact-profile-legal_entity-ag-producer-crop.bloom_hill_farm.profile.yaml").write_text("display_name: Bloom Hill Farm\n", encoding="utf-8")
    (sc / "profiles" / "0000-00-00.artifact-profile-natural_entity.nathan_seals.profile.yaml").write_text("display_name: Nathan Seals\n", encoding="utf-8")
    (sc / "icon" / "0000-00-00.artifact-icon.mycite.crop.svg").write_text("<svg/>", encoding="utf-8")
    (sc / "event" / "0000-00-00.artifact-event-finite.brocks_pressure_washing.jane_roe.yaml").write_text("customer: Jane\n", encoding="utf-8")
    (sc / "custom" / "2026-04-10.artifact-custom.brocks_pressure_washing-jobs.deck.yaml").write_text("price: 100\nspec:\n  size: large\n", encoding="utf-8")
    (sc / "analytics" / "0000-00-00.record-analytics.fnd.2026-05.yaml").write_text("visitors: []\n", encoding="utf-8")
    return root


class ResourceTypesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.root = _seed(Path(self._td.name))

    def tearDown(self) -> None:
        self._td.cleanup()

    # ---- loader / flatten ------------------------------------------------ #
    def test_flatten_full_slug_and_metadata(self) -> None:
        rows = {r["full_slug"]: r for r in rt.flatten_type_tree(self.root)}
        apiary = rows["artifact-profile-legal_entity-ag-producer-apiary"]
        self.assertEqual(apiary["depth"], 5)
        self.assertEqual(apiary["parent_slug"], "artifact-profile-legal_entity-ag-producer")
        self.assertEqual(apiary["icon"], "icon-apiary")
        self.assertEqual(apiary["icon_ref"], "0000-00-00.artifact-icon.mycite.apiary")
        self.assertFalse(apiary["has_children"])
        producer = rows["artifact-profile-legal_entity-ag-producer"]
        self.assertTrue(producer["has_children"])
        self.assertIn("artifact-profile-legal_entity-ag-producer-crop", producer["child_slugs"])
        # top-level artifact label + icon
        self.assertEqual(rows["artifact"]["label"], "Artifact")

    def test_flatten_nonfatal_on_missing_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(rt.flatten_type_tree(Path(empty)), [])
            self.assertEqual(rt.load_type_tree(Path(empty)), {})
            self.assertEqual(rt.flatten_type_tree(None), [])

    def test_type_node_full(self) -> None:
        node = rt.type_node_full(self.root, "artifact-profile-legal_entity-ag-producer-crop")
        self.assertIsNotNone(node)
        self.assertEqual(node["label"], "Crop")
        self.assertIsNone(rt.type_node_full(self.root, "artifact-nope"))

    # ---- filename TYPE parse + node match -------------------------------- #
    def test_parse_leaflet_type(self) -> None:
        self.assertEqual(
            rt.parse_leaflet_type("0000-00-00.artifact-event-hebdomadal.owner.name.yaml"),
            "artifact-event-hebdomadal",
        )
        self.assertEqual(
            rt.parse_leaflet_type("0000-00-00.artifact-profile-natural_entity.nathan_seals.profile.yaml"),
            "artifact-profile-natural_entity",
        )
        self.assertEqual(
            rt.parse_leaflet_type("0000-00-00.artifact-icon.mycite-ui.add.svg"), "artifact-icon"
        )
        self.assertEqual(rt.parse_leaflet_type("notaleaflet"), "")

    def test_match_type_to_node(self) -> None:
        slugs = rt.registered_full_slugs(self.root)
        # exact
        self.assertEqual(
            rt.match_type_to_node(slugs, "artifact-profile-legal_entity-ag-producer-crop"),
            ("artifact-profile-legal_entity-ag-producer-crop", ""),
        )
        # nearest-ancestor + tail (event tree stops at hebdomadal/seasonal; no 'finite')
        self.assertEqual(rt.match_type_to_node(slugs, "artifact-event-finite"), ("artifact-event", "finite"))
        # unknown subtype rolls under its nearest KNOWN ancestor (here top-level "artifact")
        self.assertEqual(rt.match_type_to_node(slugs, "artifact-zzz"), ("artifact", "zzz"))
        # truly unmatched (unregistered first segment) → "Other" bucket
        self.assertEqual(rt.match_type_to_node(slugs, "widget-foo"), ("", "widget-foo"))

    # ---- by-type index + PII + rollup ------------------------------------ #
    def test_index_excludes_pii_by_default(self) -> None:
        idx = rt.build_type_leaflet_index(self.root)
        self.assertIn("artifact-profile-legal_entity-ag-producer-crop", idx)
        self.assertIn("artifact-icon", idx)
        self.assertIn("record-analytics", idx)
        self.assertNotIn("artifact-event-finite", idx)  # event dir = PII
        self.assertNotIn("artifact-custom", idx)        # custom dir = PII

    def test_index_includes_pii_when_requested(self) -> None:
        idx = rt.build_type_leaflet_index(self.root, include_pii=True)
        self.assertIn("artifact-event-finite", idx)
        self.assertIn("artifact-custom", idx)

    def test_leaflets_for_type_rollup(self) -> None:
        # base type rolls up both profile subtypes (crop + natural_entity)
        rolled = rt.leaflets_for_type(self.root, "artifact-profile", include_subtypes=True)
        self.assertEqual(len(rolled), 2)
        # exact-only: no leaflet is typed literally "artifact-profile"
        self.assertEqual(rt.leaflets_for_type(self.root, "artifact-profile", include_subtypes=False), [])
        # PII type requires include_pii
        self.assertEqual(rt.leaflets_for_type(self.root, "artifact-event"), [])
        self.assertEqual(len(rt.leaflets_for_type(self.root, "artifact-event", include_pii=True)), 1)

    def test_type_leaflet_counts_rollup(self) -> None:
        counts = rt.type_leaflet_counts(self.root)
        self.assertEqual(counts["artifact-profile"], 2)
        self.assertEqual(counts["artifact-profile-legal_entity-ag-producer-crop"], 1)
        self.assertEqual(counts["artifact-profile-natural_entity"], 1)
        self.assertEqual(counts["artifact-icon"], 1)
        self.assertEqual(counts["record-analytics"], 1)
        self.assertEqual(counts["artifact-event"], 0)  # PII excluded

    # ---- viewer routing + generic view ----------------------------------- #
    def test_resolve_instance_viewer(self) -> None:
        self.assertEqual(rt.resolve_instance_viewer("artifact-profile-natural_entity")["viewer"], "profile")
        self.assertEqual(rt.resolve_instance_viewer("record-analytics")["viewer"], "analytics")
        self.assertEqual(rt.resolve_instance_viewer("artifact-event-finite")["viewer"], "event")
        self.assertEqual(rt.resolve_instance_viewer("artifact-icon")["viewer"], "asset")
        self.assertEqual(rt.resolve_instance_viewer("artifact-custom")["viewer"], "generic")
        self.assertEqual(rt.resolve_instance_viewer("record-table")["viewer"], "generic")

    def test_structured_leaflet_view(self) -> None:
        view = rt.structured_leaflet_view(
            self.root, "artifact-custom",
            "/site-core/custom/2026-04-10.artifact-custom.brocks_pressure_washing-jobs.deck.yaml",
        )
        self.assertIsNotNone(view)
        keys = {f["key"] for f in view["fields"]}
        self.assertEqual(keys, {"price", "spec"})
        nested = next(f for f in view["fields"] if f["key"] == "spec")
        self.assertTrue(nested["is_nested"])
        self.assertIn("price: 100", view["raw_yaml"])
        # missing file → None; traversal-proof
        self.assertIsNone(rt.structured_leaflet_view(self.root, "x", "/site-core/custom/nope.yaml"))
        self.assertIsNone(rt.structured_leaflet_view(self.root, "x", "/etc/passwd"))


if __name__ == "__main__":
    unittest.main()
