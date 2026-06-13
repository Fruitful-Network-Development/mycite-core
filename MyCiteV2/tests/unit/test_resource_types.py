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

    def test_complete_type_nodes_synthesizes_unregistered_types(self) -> None:
        # An on-disk leaflet TYPE the manifest does NOT register (here: audio) must
        # become a synthesized, browsable node — not vanish into a parent's rollup.
        audio = self.root / "clients" / "_shared" / "site-core" / "audio"
        audio.mkdir(parents=True, exist_ok=True)
        (audio / "0000-00-00.artifact-audio.fnd.welcome.yaml").write_text("x\n", encoding="utf-8")
        nodes = {n["full_slug"]: n for n in rt.complete_type_nodes(self.root)}
        # the unregistered audio type is now a node, under the registered 'artifact' root
        self.assertIn("artifact-audio", nodes)
        self.assertTrue(nodes["artifact-audio"].get("synthetic"))
        self.assertEqual(nodes["artifact-audio"]["count"], 1)
        self.assertEqual(nodes["artifact-audio"]["parent_slug"], "artifact")
        self.assertEqual(nodes["artifact-audio"]["label"], "Audio")
        self.assertIn("artifact-audio", nodes["artifact"]["child_slugs"])
        # registered nodes keep their manifest label
        self.assertEqual(nodes["artifact-profile"]["label"], "Profile")
        self.assertFalse(nodes["artifact-profile"].get("synthetic"))

    def test_set_icon_ref_accepts_unregistered_on_disk_type(self) -> None:
        # The ✎ icon edit on a synthesized node must succeed (validated against the
        # browsable set, not just manifest-registered slugs).
        audio = self.root / "clients" / "_shared" / "site-core" / "audio"
        audio.mkdir(parents=True, exist_ok=True)
        (audio / "0000-00-00.artifact-audio.fnd.welcome.yaml").write_text("x\n", encoding="utf-8")
        icon = rt.list_icon_options(self.root)[0]["icon_ref"]
        res = rt.set_type_icon_ref(self.root, "artifact-audio", icon)
        self.assertTrue(res["ok"], res)
        # the override now shows on the synthesized node
        nodes = {n["full_slug"]: n for n in rt.complete_type_nodes(self.root)}
        self.assertEqual(nodes["artifact-audio"]["icon_ref"], icon)

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
        path = "/site-core/custom/2026-04-10.artifact-custom.brocks_pressure_washing-jobs.deck.yaml"
        # custom is PII → OVERALL (no include_pii) must NOT resolve its contents
        self.assertIsNone(rt.structured_leaflet_view(self.root, "artifact-custom", path))
        # grantee scope (include_pii) sees it
        view = rt.structured_leaflet_view(self.root, "artifact-custom", path, include_pii=True)
        self.assertIsNotNone(view)
        keys = {f["key"] for f in view["fields"]}
        self.assertEqual(keys, {"price", "spec"})
        nested = next(f for f in view["fields"] if f["key"] == "spec")
        self.assertTrue(nested["is_nested"])
        self.assertIn("price: 100", view["raw_yaml"])
        # missing file → None; traversal-proof
        self.assertIsNone(
            rt.structured_leaflet_view(self.root, "x", "/site-core/custom/nope.yaml", include_pii=True)
        )
        self.assertIsNone(rt.structured_leaflet_view(self.root, "x", "/etc/passwd"))

    # ---- editable manifest (icon override side-car) ---------------------- #
    def test_icon_override_roundtrip(self) -> None:
        opts = {o["icon_ref"] for o in rt.list_icon_options(self.root)}
        self.assertIn("0000-00-00.artifact-icon.mycite.crop", opts)
        # set an override on a registered node
        res = rt.set_type_icon_ref(self.root, "artifact-icon", "0000-00-00.artifact-icon.mycite.crop")
        self.assertTrue(res["ok"])
        rows = {r["full_slug"]: r for r in rt.flatten_type_tree(self.root)}
        self.assertEqual(rows["artifact-icon"]["icon_ref"], "0000-00-00.artifact-icon.mycite.crop")
        # SSOT manifest is untouched (override lives in the side-car)
        manifest = (self.root / "clients" / "_shared" / "site-core" / "schema"
                    / "0000-00-00.artifact-manifest.mycite.schema.yaml").read_text()
        self.assertNotIn("0000-00-00.artifact-icon.mycite.crop", manifest.split("icon:")[0])
        # validation: unknown node / unknown icon rejected
        self.assertFalse(rt.set_type_icon_ref(self.root, "widget-foo", "x")["ok"])
        self.assertFalse(rt.set_type_icon_ref(self.root, "artifact-icon", "no.such.icon")["ok"])
        # clear → falls back to manifest value
        self.assertTrue(rt.set_type_icon_ref(self.root, "artifact-icon", "")["ok"])
        rows = {r["full_slug"]: r for r in rt.flatten_type_tree(self.root)}
        self.assertEqual(rows["artifact-icon"]["icon_ref"], "")  # manifest 'icon' node has no icon_ref


if __name__ == "__main__":
    unittest.main()
