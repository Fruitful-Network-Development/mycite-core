"""ext_resources — the resources Utilities extension (Wave 2).

Covers the extension that REPLACES the retired ``resources.root`` surface:

  1. ``ext_resources`` is registered as an ``is_extension=True`` entry on the
     Utilities → Extensions surface, has a renderer in EXTENSION_RENDERERS,
     and renders a ``resources_app`` payload (profiles roster + galleries).
  2. The profiles contact-app: ``list_profiles`` rows carry slug/display_name/
     image_url; ``profile_detail`` returns EVERY field including empty ones;
     ``resolve_profile_image`` honors image_ref then slug+role search.
  3. ``save_profile`` patches the canonical YAML atomically;
     ``derive_profile_excerpt`` refills a per-site excerpt from canonical
     (round-trip), preserving the excerpt's key set.
  4. ``add_asset_to_manifest`` appends one entry, deduped by asset_path.
  5. ``icon_duplicate_groups`` groups byte-identical icons;
     ``remove_icon_duplicate`` refuses referenced/unique icons.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.utilities_extensions import (
    EXTENSION_RENDERERS,
    render_extension,
)
from MyCiteV2.instances._shared.runtime.utilities_extensions import (
    resources_extension as rx,
)
from MyCiteV2.packages.state_machine.portal_shell.shell_registry import (
    build_portal_tool_registry_entries,
)


def _seed_profiles(webapps_root: Path) -> Path:
    sc = webapps_root / "clients" / "_shared" / "site-core"
    (sc / "profiles").mkdir(parents=True)
    (sc / "image").mkdir(parents=True)
    (sc / "icon").mkdir(parents=True)
    # Profile with explicit image_ref.
    (sc / "profiles" / "0000-00-00.artifact-profile-natural_entity.jane_doe.profile.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "Jane Doe",
                "display_name": "Jane Doe",
                "role": "Chair",
                "entity_type": None,
                "email": "old@x.org",
                "summary_bio": "Old bio",
                "image_ref": "0000-00-00.artifact-image.org.jane_doe-profile_headshot",
                "bio": ["line one"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    # Profile WITHOUT image_ref — image resolved by slug+role search.
    (sc / "profiles" / "0000-00-00.artifact-profile-legal_entity.acme_farm.profile.yaml").write_text(
        yaml.safe_dump({"name": "Acme Farm", "image_ref": None, "logo_ref": None}, sort_keys=False),
        encoding="utf-8",
    )
    (sc / "image" / "0000-00-00.artifact-image.org.acme_farm-logo.avif").write_text("x", encoding="utf-8")
    return webapps_root


class ExtResourcesRegistrationTests(unittest.TestCase):
    def test_registered_as_extension_on_extensions_surface(self) -> None:
        entries = {e.tool_id: e for e in build_portal_tool_registry_entries()}
        self.assertIn("ext_resources", entries)
        entry = entries["ext_resources"]
        self.assertTrue(entry.is_extension)
        self.assertEqual(entry.surface_id, "utilities.extensions")
        self.assertEqual(entry.entrypoint_id, "portal.utilities.ext_resources")
        self.assertIn("ext_resources", EXTENSION_RENDERERS)

    def test_renderer_produces_resources_app_payload(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="ext_res_render_"))
        _seed_profiles(tmp)
        payload = render_extension("ext_resources", {"webapps_root": tmp})
        self.assertTrue(payload.get("resources_app"))
        # The library is a single flat leaflet index; profiles appear as rows.
        slugs = {row["slug"] for row in payload["leaflets"] if row["kind"] == "profile"}
        self.assertEqual(slugs, {"jane_doe", "acme_farm"})


class ProfilesContactAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="ext_res_profiles_"))
        _seed_profiles(self.tmp)

    def test_list_profiles_rows(self) -> None:
        rows = {r["slug"]: r for r in rx.list_profiles(self.tmp)}
        self.assertEqual(rows["jane_doe"]["display_name"], "Jane Doe")
        # image_ref honored.
        self.assertTrue(rows["jane_doe"]["image_url"].endswith("jane_doe-profile_headshot.avif"))
        # slug+role search resolves the logo for the ref-less profile.
        self.assertTrue(rows["acme_farm"]["image_url"].endswith("acme_farm-logo.avif"))

    def test_profile_detail_includes_empty_fields(self) -> None:
        detail = rx.profile_detail(self.tmp, "jane_doe")
        self.assertIsNotNone(detail)
        by_key = {f["key"]: f for f in detail["fields"]}
        # entity_type was null in the source — present with empty value.
        self.assertIn("entity_type", by_key)
        self.assertEqual(by_key["entity_type"]["value"], "")
        self.assertEqual(by_key["email"]["value"], "old@x.org")

    def test_save_profile_patches_canonical(self) -> None:
        result = rx.save_profile(self.tmp, "jane_doe", {"email": "new@x.org", "summary_bio": "New bio"})
        self.assertTrue(result["ok"])
        path = (
            self.tmp / "clients" / "_shared" / "site-core" / "profiles"
            / "0000-00-00.artifact-profile-natural_entity.jane_doe.profile.yaml"
        )
        data = yaml.safe_load(path.read_text())
        self.assertEqual(data["email"], "new@x.org")
        self.assertEqual(data["summary_bio"], "New bio")
        # Non-edited list field preserved.
        self.assertEqual(data["bio"], ["line one"])

    def test_derive_excerpt_round_trip(self) -> None:
        canonical = (
            self.tmp / "clients" / "_shared" / "site-core" / "profiles"
            / "0000-00-00.artifact-profile-natural_entity.jane_doe.profile.yaml"
        )
        assets = self.tmp / "clients" / "site.org" / "frontend" / "assets"
        assets.mkdir(parents=True)
        excerpt = assets / "0000-00-00.profile-natural_entity.site.jane_doe-bio.yaml"
        excerpt.write_text(
            yaml.safe_dump({"name": "Jane Doe", "role": "Chair", "email": "old@x.org"}, sort_keys=False),
            encoding="utf-8",
        )
        rx.save_profile(self.tmp, "jane_doe", {"email": "new@x.org"})
        self.assertTrue(rx.derive_profile_excerpt(canonical, excerpt))
        derived = yaml.safe_load(excerpt.read_text())
        # Excerpt key SET preserved, value refilled from canonical.
        self.assertEqual(set(derived.keys()), {"name", "role", "email"})
        self.assertEqual(derived["email"], "new@x.org")

    def test_propagate_without_rebuild_finds_and_derives_excerpt(self) -> None:
        assets = self.tmp / "clients" / "site.org" / "frontend" / "assets"
        assets.mkdir(parents=True)
        excerpt = assets / "0000-00-00.profile-natural_entity.site.jane_doe-bio.yaml"
        excerpt.write_text(yaml.safe_dump({"email": "old@x.org"}, sort_keys=False), encoding="utf-8")
        rx.save_profile(self.tmp, "jane_doe", {"email": "fresh@x.org"})
        out = rx.propagate_profile(self.tmp, "jane_doe", rebuild=False)
        self.assertIn(str(excerpt), out["derived"])
        self.assertEqual(yaml.safe_load(excerpt.read_text())["email"], "fresh@x.org")


class ManifestAndIconTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="ext_res_manifest_"))
        sc = self.tmp / "clients" / "_shared" / "site-core"
        (sc / "icon").mkdir(parents=True)
        self.assets = self.tmp / "clients" / "site.org" / "frontend" / "assets"
        self.assets.mkdir(parents=True)
        (self.assets / "0000-00-00.record-manifest.site-website.icon_use.yaml").write_text(
            yaml.safe_dump(
                {
                    "manifest_kind": "icon_use",
                    "site_entity": "site",
                    "entries": [
                        {"asset_id": "a", "asset_path": "/assets/icons/keep.svg", "consumers": [], "entity_scope": "site"}
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def test_add_asset_to_manifest_dedupes(self) -> None:
        first = rx.add_asset_to_manifest(
            self.tmp, site="site.org", kind="icon", asset_id="b",
            asset_path="/assets/icons/new.svg",
        )
        self.assertTrue(first["ok"] and first["added"])
        again = rx.add_asset_to_manifest(
            self.tmp, site="site.org", kind="icon", asset_id="b",
            asset_path="/assets/icons/new.svg",
        )
        self.assertTrue(again["ok"])
        self.assertFalse(again["added"])
        data = yaml.safe_load(Path(first["manifest"]).read_text())
        paths = [e["asset_path"] for e in data["entries"]]
        self.assertEqual(paths.count("/assets/icons/new.svg"), 1)

    def test_icon_dedup_groups_and_safe_removal(self) -> None:
        icon_dir = self.tmp / "clients" / "_shared" / "site-core" / "icon"
        # Two byte-identical icons (a duplicate), one of them referenced.
        (icon_dir / "keep.svg").write_text("<svg>same</svg>", encoding="utf-8")
        (icon_dir / "dupe.svg").write_text("<svg>same</svg>", encoding="utf-8")
        (icon_dir / "unique.svg").write_text("<svg>other</svg>", encoding="utf-8")
        groups = rx.icon_duplicate_groups(self.tmp)
        self.assertEqual(len(groups), 1)
        members = {m["filename"]: m for m in groups[0]["members"]}
        self.assertEqual(set(members), {"keep.svg", "dupe.svg"})
        self.assertTrue(members["keep.svg"]["referenced"])
        self.assertFalse(members["dupe.svg"]["referenced"])
        # Referenced member cannot be removed.
        self.assertFalse(rx.remove_icon_duplicate(self.tmp, "keep.svg")["ok"])
        # Unreferenced duplicate can.
        removed = rx.remove_icon_duplicate(self.tmp, "dupe.svg")
        self.assertTrue(removed["ok"])
        self.assertFalse((icon_dir / "dupe.svg").exists())
        # Unique icon is never removable.
        self.assertFalse(rx.remove_icon_duplicate(self.tmp, "unique.svg")["ok"])


def _seed_events(webapps_root: Path) -> Path:
    ev = webapps_root / "clients" / "_shared" / "site-core" / "events"
    ev.mkdir(parents=True)
    (ev / "2026-05-01.event-job.brocks_pressure_washing.driveway.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "mycite.site_core.event_job.v1",
                "event_kind": "job",
                "client": "brocks_pressure_washing",
                "id": "2026-0001",
                "date": "2026-05-01",
                "status": "completed",
                "title": "Driveway wash",
                "location": "Akron",
                "customer": {"name": "Jane Roe"},
                "pricing": {"total": 250.0, "paid": True},
                "tags": [{"type": "driveway"}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (ev / "2026-04-10.event-job.brocks_pressure_washing.deck.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "mycite.site_core.event_job.v1",
                "client": "brocks_pressure_washing",
                "id": "2026-0002",
                "date": "2026-04-10",
                "status": "booked",
                "title": "Deck",
                "customer": {"name": "Bob"},
                "pricing": {"total": 120},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    # The tracked *.example.* template must be ignored, not counted.
    (ev / "0000-00-00.event-job.sample.template.example.yaml").write_text(
        "schema: mycite.site_core.event_job.v1\n", encoding="utf-8"
    )
    return webapps_root


def _seed_contacts(webapps_root: Path) -> Path:
    ct = webapps_root / "clients" / "_shared" / "site-core" / "contacts"
    ct.mkdir(parents=True)
    (ct / "0000-00-00.record-data.brocks_pressure_washing.contacts.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "mycite.site_core.contact_record.v1",
                "entity": "brocks_pressure_washing",
                "contacts": [
                    {
                        "email": "amy@x.com",
                        "first_name": "Amy",
                        "last_name": "Adams",
                        "phone": "555-1",
                        "subscribed": True,
                        "organization": "Acme",
                        "domain": "brockspressurewashing.com",
                    },
                    {"email": "ben@x.com", "first_name": "Ben", "subscribed": False},
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    # example template ignored.
    (ct / "0000-00-00.record-data.sample.contacts.example.yaml").write_text(
        "schema: x\n", encoding="utf-8"
    )
    return webapps_root


class EventsDetailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="ext_res_events_"))
        _seed_events(self.tmp)

    def test_events_detail_formats_rows_and_kpis(self) -> None:
        detail = rx.events_detail(self.tmp)
        self.assertEqual(detail["count"], 2)  # example skipped
        # Sorted by date descending — the completed driveway job first.
        first = detail["rows"][0]
        self.assertEqual(first["date"], "2026-05-01")
        self.assertEqual(first["title"], "Driveway wash")
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["customer"], "Jane Roe")
        self.assertEqual(first["total"], 250.0)
        # KPI line: total events + revenue (completed only).
        self.assertEqual(detail["summary"]["total_events"], 2)
        self.assertEqual(detail["summary"]["total_revenue"], 250.0)

    def test_events_detail_empty_when_no_gallery(self) -> None:
        empty = rx.events_detail(Path(tempfile.mkdtemp(prefix="ext_res_noev_")))
        self.assertEqual(empty["rows"], [])
        self.assertEqual(empty["count"], 0)


class ContactsDetailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="ext_res_contacts_"))
        _seed_contacts(self.tmp)

    def test_contacts_detail_groups_per_entity(self) -> None:
        detail = rx.contacts_detail(self.tmp)
        self.assertEqual(detail["total_contacts"], 2)
        entities = {e["entity"]: e for e in detail["entities"]}
        self.assertIn("brocks_pressure_washing", entities)
        ent = entities["brocks_pressure_washing"]
        self.assertEqual(ent["count"], 2)
        rows = {c["email"]: c for c in ent["contacts"]}
        self.assertEqual(rows["amy@x.com"]["name"], "Amy Adams")
        self.assertEqual(rows["amy@x.com"]["phone"], "555-1")
        self.assertTrue(rows["amy@x.com"]["subscribed"])
        self.assertEqual(rows["amy@x.com"]["organization"], "Acme")
        # A contact with only a first name + no org falls back gracefully.
        self.assertEqual(rows["ben@x.com"]["name"], "Ben")
        self.assertFalse(rows["ben@x.com"]["subscribed"])

    def test_contacts_detail_empty_when_no_gallery(self) -> None:
        empty = rx.contacts_detail(Path(tempfile.mkdtemp(prefix="ext_res_noct_")))
        self.assertEqual(empty["entities"], [])
        self.assertEqual(empty["total_contacts"], 0)


class RenderPayloadShapeTests(unittest.TestCase):
    def test_library_is_a_flat_index_without_pii_views(self) -> None:
        # The unified library is one type-agnostic leaflet index; the PII
        # events/contacts read-only views are no longer part of this surface.
        tmp = Path(tempfile.mkdtemp(prefix="ext_res_payload_"))
        _seed_profiles(tmp)
        _seed_events(tmp)
        _seed_contacts(tmp)
        payload = render_extension("ext_resources", {"webapps_root": tmp})
        self.assertEqual(payload["resources_mode"], "library")
        self.assertIn("leaflets", payload)
        self.assertNotIn("events_detail", payload)
        self.assertNotIn("contacts_detail", payload)


def _seed_managed_gallery(webapps_root: Path) -> Path:
    """A site-core icon gallery + a site icon_use manifest referencing one icon."""
    sc = webapps_root / "clients" / "_shared" / "site-core"
    (sc / "icon").mkdir(parents=True, exist_ok=True)
    used = sc / "icon" / "0000-00-00.artifact-icon.mycite-ui.mail.svg"
    unused = sc / "icon" / "0000-00-00.artifact-icon.mycite-ui.spare.svg"
    used.write_text("<svg/>", encoding="utf-8")
    unused.write_text("<svg/>", encoding="utf-8")
    assets = webapps_root / "clients" / "site.org" / "frontend" / "assets"
    assets.mkdir(parents=True)
    (assets / "0000-00-00.record-manifest.site-website.icon_use.yaml").write_text(
        yaml.safe_dump(
            {
                "manifest_kind": "icon_use",
                "site_entity": "site",
                "entries": [
                    {
                        "asset_id": "mail",
                        "asset_path": "/assets/icons/0000-00-00.artifact-icon.mycite-ui.mail.svg",
                        "consumers": [],
                        "entity_scope": "site",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return webapps_root


class CollectiveGalleryManagementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="ext_res_manage_"))
        _seed_managed_gallery(self.tmp)

    def test_grouped_gallery_groups_by_slug_with_referenced_flag(self) -> None:
        grouped = rx.build_grouped_gallery(self.tmp, "icon")
        by_slug = {g["slug"]: g for g in grouped["groups"]}
        self.assertEqual(set(by_slug), {"mail", "spare"})
        mail = by_slug["mail"]["members"][0]
        self.assertTrue(mail["referenced"])
        self.assertFalse(by_slug["spare"]["members"][0]["referenced"])

    def test_manifest_referenced_paths(self) -> None:
        ref = rx.manifest_referenced_paths(self.tmp, "icon")
        self.assertIn("/assets/icons/0000-00-00.artifact-icon.mycite-ui.mail.svg", ref)

    def test_retitle_rewrites_manifest_asset_id(self) -> None:
        result = rx.retitle_asset(
            self.tmp, "icon", "0000-00-00.artifact-icon.mycite-ui.mail.svg", "Mail Glyph"
        )
        self.assertTrue(result["ok"])
        manifest = (
            self.tmp / "clients" / "site.org" / "frontend" / "assets"
            / "0000-00-00.record-manifest.site-website.icon_use.yaml"
        )
        data = yaml.safe_load(manifest.read_text())
        self.assertEqual(data["entries"][0]["asset_id"], "Mail Glyph")

    def test_delete_refuses_referenced_asset(self) -> None:
        result = rx.delete_asset_if_unreferenced(
            self.tmp, "icon", "0000-00-00.artifact-icon.mycite-ui.mail.svg"
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "referenced")

    def test_delete_removes_unreferenced_asset(self) -> None:
        result = rx.delete_asset_if_unreferenced(
            self.tmp, "icon", "0000-00-00.artifact-icon.mycite-ui.spare.svg"
        )
        self.assertTrue(result["ok"])
        self.assertFalse(
            (self.tmp / "clients" / "_shared" / "site-core" / "icon"
             / "0000-00-00.artifact-icon.mycite-ui.spare.svg").exists()
        )

    def test_rename_slug_renames_file_and_repoints_manifest(self) -> None:
        result = rx.rename_slug(self.tmp, "icon", "mail", "envelope")
        self.assertTrue(result["ok"], result)
        icon_dir = self.tmp / "clients" / "_shared" / "site-core" / "icon"
        self.assertTrue((icon_dir / "0000-00-00.artifact-icon.mycite-ui.envelope.svg").exists())
        self.assertFalse((icon_dir / "0000-00-00.artifact-icon.mycite-ui.mail.svg").exists())
        manifest = (
            self.tmp / "clients" / "site.org" / "frontend" / "assets"
            / "0000-00-00.record-manifest.site-website.icon_use.yaml"
        )
        data = yaml.safe_load(manifest.read_text())
        self.assertEqual(
            data["entries"][0]["asset_path"],
            "/assets/icons/0000-00-00.artifact-icon.mycite-ui.envelope.svg",
        )

    def test_rename_slug_refuses_collision(self) -> None:
        result = rx.rename_slug(self.tmp, "icon", "mail", "spare")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "collision")


class AllocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="ext_res_alloc_"))
        _seed_managed_gallery(self.tmp)

    def test_site_manifest_entries_lists_allocated(self) -> None:
        rows = rx.site_manifest_entries(self.tmp, "site.org", "icon")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["asset_id"], "mail")

    def test_remove_then_add_round_trip(self) -> None:
        path = "/assets/icons/0000-00-00.artifact-icon.mycite-ui.mail.svg"
        removed = rx.remove_asset_from_manifest(
            self.tmp, site="site.org", kind="icon", asset_path=path
        )
        self.assertTrue(removed["ok"])
        self.assertTrue(removed["removed"])
        self.assertEqual(rx.site_manifest_entries(self.tmp, "site.org", "icon"), [])
        # removing again is a no-op (idempotent), still ok.
        again = rx.remove_asset_from_manifest(
            self.tmp, site="site.org", kind="icon", asset_path=path
        )
        self.assertTrue(again["ok"])
        self.assertFalse(again["removed"])
        # re-add via the existing helper.
        added = rx.add_asset_to_manifest(
            self.tmp, site="site.org", kind="icon", asset_id="mail", asset_path=path
        )
        self.assertTrue(added["ok"])
        self.assertEqual(len(rx.site_manifest_entries(self.tmp, "site.org", "icon")), 1)

    def test_allocation_payload_marks_allocated_candidates(self) -> None:
        payload = render_extension(
            "ext_resources",
            {
                "webapps_root": self.tmp,
                "mode": "grantee",
                "grantee": {"msn_id": "acme", "label": "Acme"},
                "domain": "site.org",
            },
        )
        self.assertEqual(payload["resources_mode"], "allocation")
        self.assertTrue(payload["site_exists"])
        icon_alloc = next(a for a in payload["allocations"] if a["gallery"] == "icon")
        self.assertEqual(icon_alloc["used_count"], 1)
        allocated = [c for c in icon_alloc["candidates"] if c["allocated"]]
        self.assertEqual(len(allocated), 1)
        self.assertTrue(allocated[0]["asset_path"].endswith("mail.svg"))


class FullProfileEditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="ext_res_edit_"))
        sc = self.tmp / "clients" / "_shared" / "site-core" / "profiles"
        sc.mkdir(parents=True)
        self.path = sc / "0000-00-00.artifact-profile-legal_entity.farm_z.profile.yaml"
        self.path.write_text(
            yaml.safe_dump(
                {
                    "name": "Farm Z",
                    "summary_bio": "Old summary.",
                    "bio": ["Para one.", "Para two."],
                    "tags": ["historic"],
                    "socials": [{"platform": "x", "value": "@z"}],  # structured: preserved
                    "coordinates": {"lat": 1.0, "lng": 2.0},  # structured: preserved
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def test_save_typed_fields_round_trip(self) -> None:
        # bio arrives as a multiline string (the textarea), tags as a list.
        rx.save_profile(
            self.tmp,
            "farm_z",
            {
                "summary_bio": "New summary.",
                "bio": "First paragraph.\n\nSecond paragraph.\n\nThird.",
                "tags": ["historic", "agritourism"],
                "name": "Farm Z",
            },
        )
        data = yaml.safe_load(self.path.read_text())
        self.assertEqual(data["summary_bio"], "New summary.")
        self.assertEqual(data["bio"], ["First paragraph.", "Second paragraph.", "Third."])
        self.assertEqual(data["tags"], ["historic", "agritourism"])
        # Structured fields untouched.
        self.assertEqual(data["socials"], [{"platform": "x", "value": "@z"}])
        self.assertEqual(data["coordinates"], {"lat": 1.0, "lng": 2.0})

    def test_edit_frame_field_types(self) -> None:
        frame = rx.build_profile_edit_frame(self.tmp, "farm_z")
        self.assertEqual(frame["component_type"], "form")
        ftypes = {f["key"]: f["type"] for f in frame["payload"]["fields"]}
        self.assertEqual(ftypes["bio"], "multiline")
        self.assertEqual(ftypes["summary_bio"], "multiline")
        # Simple lists render as multiline (one per line), not the unwired chips.
        self.assertEqual(ftypes["tags"], "multiline")
        tags_field = next(f for f in frame["payload"]["fields"] if f["key"] == "tags")
        self.assertEqual(tags_field["value"], "historic")
        bio_field = next(f for f in frame["payload"]["fields"] if f["key"] == "bio")
        self.assertIn("Para one.", bio_field["value"])
        self.assertIn("Para two.", bio_field["value"])


class LeafletIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="ext_res_index_"))
        _seed_profiles(self.tmp)
        _seed_managed_gallery(self.tmp)

    def test_entity_flavor_parsing(self) -> None:
        self.assertEqual(
            rx._profile_entity_flavor(
                "0000-00-00.artifact-profile-legal_entity.wallace_farm.profile.yaml"
            ),
            "legal_entity",
        )
        self.assertEqual(
            rx._profile_entity_flavor(
                "0000-00-00.artifact-profile-natural_entity.jane_doe.profile.yaml"
            ),
            "natural_entity",
        )

    def test_index_flattens_all_types_with_naming(self) -> None:
        idx = rx.build_leaflet_index(self.tmp)
        kinds = {r["kind"] for r in idx}
        self.assertIn("profile", kinds)
        self.assertIn("icon", kinds)
        jane = next(r for r in idx if r["slug"] == "jane_doe")
        self.assertEqual(jane["kind"], "profile")
        self.assertEqual(jane["entity_type"], "natural_entity")
        self.assertIn("jane_doe", jane["naming"])
        # icon members carry no entity_type but a slug + naming.
        mail = next(r for r in idx if r["slug"] == "mail" and r["kind"] == "icon")
        self.assertEqual(mail["entity_type"], "")
        self.assertTrue(mail["referenced"])  # referenced by the seeded manifest
        # dash facet: slug split on first dash into base + variant.
        self.assertEqual(mail["slug_base"], "mail")
        self.assertEqual(mail["slug_variant"], "")

    def test_slug_variant_facet(self) -> None:
        # An icon whose slug carries an in-slug dash → base + variant.
        icon_dir = self.tmp / "clients" / "_shared" / "site-core" / "icon"
        (icon_dir / "0000-00-00.artifact-icon.org.logo-monochrome.svg").write_text(
            "<svg/>", encoding="utf-8"
        )
        idx = rx.build_leaflet_index(self.tmp)
        row = next(r for r in idx if r["slug"] == "logo-monochrome")
        self.assertEqual(row["slug_base"], "logo")
        self.assertEqual(row["slug_variant"], "monochrome")


def _seed_cascade_tree(root: Path) -> Path:
    sc = root / "clients" / "_shared" / "site-core" / "profiles"
    sc.mkdir(parents=True)
    # farm_a (to be renamed) + farm_b (references farm_a via related stem).
    (sc / "0000-00-00.artifact-profile-legal_entity.farm_a.profile.yaml").write_text(
        yaml.safe_dump(
            {"name": "Farm A", "display_name": "Farm A", "role": "grower",
             "coordinates": {"lat": 41.0, "lng": -81.0}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (sc / "0000-00-00.artifact-profile-legal_entity.farm_b.profile.yaml").write_text(
        yaml.safe_dump(
            {"name": "Farm B",
             "related": ["0000-00-00.artifact-profile-legal_entity.farm_a.profile"]},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    # CVCC-style derived excerpt for farm_a + an operation excerpt (entity_slug).
    assets = root / "clients" / "site.org" / "frontend" / "assets"
    assets.mkdir(parents=True)
    (assets / "0000-00-00.profile-legal_entity.site.farm_a-summary_bio.yaml").write_text(
        yaml.safe_dump({"name": "Farm A", "role": "grower"}, sort_keys=False),
        encoding="utf-8",
    )
    (assets / "0000-00-00.profile-operation.farm_a.upick.yaml").write_text(
        yaml.safe_dump({"entity_slug": "farm_a", "operation_id": "upick"}, sort_keys=False),
        encoding="utf-8",
    )
    # profile_use manifest referencing farm_a's canonical.
    (assets / "0000-00-00.record-manifest.site-website.profile_use.yaml").write_text(
        yaml.safe_dump(
            {"manifest_kind": "profile_use", "site_entity": "site", "entries": [
                {"asset_id": "farm_a",
                 "asset_path": "/assets/profiles/0000-00-00.artifact-profile-legal_entity.farm_a.profile.yaml",
                 "consumers": [], "entity_scope": "site"}]},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    # Hand-authored data file with a /profile/farm_a URL.
    data = root / "clients" / "site.org" / "frontend" / "data"
    data.mkdir(parents=True)
    (data / "timeline.json").write_text(
        '{"items":[{"profile_path":"/profile/farm_a"}]}\n', encoding="utf-8"
    )
    # FND network manifest listing farm_a in profile_refs.
    fnd = root / "clients" / "fruitfulnetworkdevelopment.com" / "frontend" / "assets"
    fnd.mkdir(parents=True)
    (fnd / "0000-00-00.manifest.fnd.fnd.site.json").write_text(
        '{"pages":{"more":{"content":{"network":{"panel":{"profile_refs":["farm_a","farm_b"]}}}}}}\n',
        encoding="utf-8",
    )
    return root


class CascadeRenameTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="ext_res_cascade_"))
        _seed_cascade_tree(self.tmp)

    def test_dry_run_discovers_all_classes(self) -> None:
        res = rx.cascade_rename_profile_slug(self.tmp, "farm_a", "farm_c", apply=False)
        self.assertTrue(res["ok"])
        r = res["report"]
        self.assertFalse(r["applied"])
        self.assertEqual(len(r["excerpts"]), 2)  # summary_bio + operation
        self.assertTrue(r["fnd_network"])
        self.assertEqual(len(r["related"]), 1)
        self.assertEqual(len(r["data_files"]), 1)
        # Dry run mutates nothing.
        self.assertTrue(
            (self.tmp / "clients" / "_shared" / "site-core" / "profiles"
             / "0000-00-00.artifact-profile-legal_entity.farm_a.profile.yaml").exists()
        )

    def test_apply_renames_and_repoints_everything(self) -> None:
        res = rx.cascade_rename_profile_slug(self.tmp, "farm_a", "farm_c", apply=True)
        self.assertTrue(res["ok"], res)
        profiles = self.tmp / "clients" / "_shared" / "site-core" / "profiles"
        self.assertTrue((profiles / "0000-00-00.artifact-profile-legal_entity.farm_c.profile.yaml").exists())
        self.assertFalse((profiles / "0000-00-00.artifact-profile-legal_entity.farm_a.profile.yaml").exists())
        assets = self.tmp / "clients" / "site.org" / "frontend" / "assets"
        self.assertTrue((assets / "0000-00-00.profile-legal_entity.site.farm_c-summary_bio.yaml").exists())
        # profile_use repointed.
        pu = yaml.safe_load((assets / "0000-00-00.record-manifest.site-website.profile_use.yaml").read_text())
        self.assertIn("farm_c.profile.yaml", pu["entries"][0]["asset_path"])
        # FND refs updated.
        import json
        fnd = json.loads((self.tmp / "clients" / "fruitfulnetworkdevelopment.com" / "frontend" / "assets"
                          / "0000-00-00.manifest.fnd.fnd.site.json").read_text())
        refs = fnd["pages"]["more"]["content"]["network"]["panel"]["profile_refs"]
        self.assertIn("farm_c", refs)
        self.assertNotIn("farm_a", refs)
        # farm_b's related stem updated.
        fb = (profiles / "0000-00-00.artifact-profile-legal_entity.farm_b.profile.yaml").read_text()
        self.assertIn("farm_c.profile", fb)
        self.assertNotIn("farm_a.profile", fb)
        # data-file /profile URL rewritten.
        tl = (self.tmp / "clients" / "site.org" / "frontend" / "data" / "timeline.json").read_text()
        self.assertIn("/profile/farm_c", tl)
        self.assertNotIn("/profile/farm_a", tl)

    def test_apply_refuses_collision(self) -> None:
        res = rx.cascade_rename_profile_slug(self.tmp, "farm_a", "farm_b", apply=True)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "collision")

    def test_dry_run_picks_only_owned_excerpts(self) -> None:
        # farm_a owns 2 excerpts (summary_bio + operation); it is NOT the owner
        # of any other profile's excerpt, so all matches are owned.
        res = rx.cascade_rename_profile_slug(self.tmp, "farm_a", "farm_c", apply=False)
        names = {e["old"].split("/")[-1] for e in res["report"]["excerpts"]}
        self.assertEqual(len(names), 2)
        self.assertTrue(any("profile-operation.farm_a." in n for n in names))

    def test_apply_rewrites_operation_entity_slug(self) -> None:
        res = rx.cascade_rename_profile_slug(self.tmp, "farm_a", "farm_c", apply=True)
        self.assertTrue(res["ok"], res)
        op = self.tmp / "clients" / "site.org" / "frontend" / "assets" / "0000-00-00.profile-operation.farm_c.upick.yaml"
        self.assertTrue(op.exists())
        self.assertEqual(yaml.safe_load(op.read_text())["entity_slug"], "farm_c")

    def test_refuses_site_entity_owner_slug(self) -> None:
        # A slug that is the OWNER segment of another profile's excerpt (an org /
        # site-entity profile) must be refused — renaming it would clobber the
        # owner token of every excerpt it owns.
        org = Path(tempfile.mkdtemp(prefix="ext_res_owner_"))
        prof = org / "clients" / "_shared" / "site-core" / "profiles"
        prof.mkdir(parents=True)
        (prof / "0000-00-00.artifact-profile-legal_entity.org_x.profile.yaml").write_text(
            yaml.safe_dump({"name": "Org X"}, sort_keys=False), encoding="utf-8"
        )
        assets = org / "clients" / "site.org" / "frontend" / "assets"
        assets.mkdir(parents=True)
        # owner=org_x, subject=some_farm
        (assets / "0000-00-00.profile-legal_entity.org_x.some_farm-summary_bio.yaml").write_text(
            yaml.safe_dump({"name": "Some Farm"}, sort_keys=False), encoding="utf-8"
        )
        res = rx.cascade_rename_profile_slug(org, "org_x", "org_y", apply=False)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "site_entity_slug")


class ResourcesModeDispatchTests(unittest.TestCase):
    def test_library_is_default_without_grantee(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="ext_res_mode_lib_"))
        _seed_profiles(tmp)
        payload = render_extension("ext_resources", {"webapps_root": tmp, "mode": "global"})
        self.assertEqual(payload["resources_mode"], "library")
        # The library is one uniform flat leaflet index (no per-type galleries).
        self.assertIn("leaflets", payload)
        self.assertNotIn("managed_galleries", payload)
        # No allocation affordance in the library.
        self.assertNotIn("manifest_add_route", payload)

    def test_allocation_when_grantee_selected(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="ext_res_mode_alloc_"))
        _seed_profiles(tmp)
        payload = render_extension(
            "ext_resources",
            {"webapps_root": tmp, "mode": "grantee", "grantee": {"msn_id": "acme"}, "domain": "acme.org"},
        )
        self.assertEqual(payload["resources_mode"], "allocation")


if __name__ == "__main__":
    unittest.main()
