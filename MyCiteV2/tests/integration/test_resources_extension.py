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
    resources_extension as rx,
)

_MANIFEST_KINDS = ("image", "icon", "audio", "document", "profile", "event", "custom")


def render_extension(tool_id: str, ctx: dict) -> dict:
    """Local stand-in for the dissolved ext_resources shell renderer.

    The operator portal extension surface (``_render_ext_resources`` +
    ``EXTENSION_RENDERERS``) was removed; this mirrors its trivial dispatch over
    the RETAINED ``_resources_*`` payload helpers so the kept resources backend
    stays covered.
    """
    assert tool_id == "ext_resources"
    as_text = rx._as_text
    if "extension_subtab" not in ctx:
        grantee = ctx.get("grantee") if isinstance(ctx.get("grantee"), dict) else {}
        if as_text(ctx.get("mode")) == "grantee" and as_text(grantee.get("msn_id")):
            return rx._resources_allocation_payload(ctx)
        return rx._resources_library_payload(ctx.get("webapps_root"))
    subtab = as_text(ctx.get("extension_subtab")) or "browse"
    if subtab == "per_grantee":
        return rx._resources_per_grantee_payload(ctx)
    if subtab == "create":
        return rx._resources_library_payload(ctx.get("webapps_root"))
    return rx._resources_browse_payload(ctx)


def _write_shared_manifest(assets: Path, entity: str, **sections) -> Path:
    """Write a site's consolidated shared_resources.yaml with the given
    resources sections (any omitted kind defaults to [])."""
    res = {k: list(sections.get(k, [])) for k in _MANIFEST_KINDS}
    assets.mkdir(parents=True, exist_ok=True)
    path = assets / f"0000-00-00.record-manifest.{entity}-website.shared_resources.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "manifest_kind": "shared_resources",
                "site_entity": entity,
                "site_domain": "",
                "generated_at": "0000-00-00",
                "resources": res,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


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
    # The explicit image_ref resolves only because its file is present (the
    # resolver is existence-aware — an absent ref must NOT yield a 404 <img>).
    (sc / "image" / "0000-00-00.artifact-image.org.jane_doe-profile_headshot.avif").write_text(
        "x", encoding="utf-8")
    # Profile WITHOUT image_ref — image resolved by slug+role search.
    (sc / "profiles" / "0000-00-00.artifact-profile-legal_entity.acme_farm.profile.yaml").write_text(
        yaml.safe_dump({"name": "Acme Farm", "image_ref": None, "logo_ref": None}, sort_keys=False),
        encoding="utf-8",
    )
    (sc / "image" / "0000-00-00.artifact-image.org.acme_farm-logo.avif").write_text("x", encoding="utf-8")
    # Profile carrying a PREDETERMINED logo_ref whose leaflet has not been
    # produced — must fall through to a neutral placeholder, not a broken URL.
    (sc / "profiles" / "0000-00-00.artifact-profile-legal_entity.ghost_farm.profile.yaml").write_text(
        yaml.safe_dump(
            {"name": "Ghost Farm", "image_ref": None,
             "logo_ref": "0000-00-00.artifact-logo.ghost_farm.logo"},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return webapps_root


class ExtResourcesRegistrationTests(unittest.TestCase):
    def test_renderer_produces_resources_app_payload(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="ext_res_render_"))
        _seed_profiles(tmp)
        payload = render_extension("ext_resources", {"webapps_root": tmp})
        self.assertTrue(payload.get("resources_app"))
        # The library is a single flat leaflet index; profiles appear as rows.
        slugs = {row["slug"] for row in payload["leaflets"] if row["kind"] == "profile"}
        self.assertEqual(slugs, {"jane_doe", "acme_farm", "ghost_farm"})


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
        # A predetermined logo_ref whose leaflet is absent falls through to "".
        self.assertEqual(rows["ghost_farm"]["image_url"], "")

    def test_profile_detail_includes_empty_fields(self) -> None:
        detail = rx.profile_detail(self.tmp, "jane_doe")
        self.assertIsNotNone(detail)
        by_key = {f["key"]: f for f in detail["fields"]}
        # entity_type was null in the source — present with empty value.
        self.assertIn("entity_type", by_key)
        self.assertEqual(by_key["entity_type"]["value"], "")
        self.assertEqual(by_key["email"]["value"], "old@x.org")

    def test_profile_detail_layered_sections(self) -> None:
        # An ag legal_entity profile yields a header band (base_fields) + ordered
        # typed sections (legal / ag), branched on the filename flavor; the flat
        # ``fields`` list stays for back-compat, and contact keys (website) stay
        # out of the sections (they render as contact_links).
        sc = self.tmp / "clients" / "_shared" / "site-core"
        (sc / "profiles" / "0000-00-00.artifact-profile-legal_entity-ag-producer-crop.bloom_farm.profile.yaml").write_text(
            yaml.safe_dump(
                {"name": "Bloom Farm", "legal_name": "Bloom Farm, LLC", "entity_type": "111419",
                 "location": "Akron, OH", "website": "https://bloom.example"},
                sort_keys=False),
            encoding="utf-8")
        d = rx.profile_detail(self.tmp, "bloom_farm")
        self.assertEqual(d["entity_flavor"], "legal_entity-ag-producer-crop")
        self.assertTrue(d["is_ag"])
        self.assertEqual((d["ag_role"], d["ag_subtype"]), ("producer", "crop"))
        sec = {s["id"]: {f["key"] for f in s["fields"]} for s in d["sections"]}
        self.assertIn("legal", sec)
        self.assertIn("ag", sec)
        self.assertTrue({"legal_name", "entity_type"} <= sec["legal"])
        base_keys = {f["key"] for f in d["base_fields"]}
        self.assertIn("location", base_keys)
        self.assertNotIn("website", base_keys)  # contact key → contact_links, not a section
        self.assertTrue(any(f["key"] == "legal_name" for f in d["fields"]))  # back-compat

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
        _write_shared_manifest(
            self.assets, "site",
            icon=[{"asset_id": "a", "asset_path": "/assets/icons/keep.svg", "consumers": [], "entity_scope": "site"}],
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
        paths = [e["asset_path"] for e in data["resources"]["icon"]]
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
    # Unified model: each job is a finite EVENT + CUSTOM residual + customer
    # PROFILE. events_detail -> list_events hydrates the triple back to a flat
    # row, so we seed all three leaflets per job.
    sc = webapps_root / "clients" / "_shared" / "site-core"
    ev = sc / "event"
    cu = sc / "custom"
    pr = sc / "profiles"
    for d in (ev, cu, pr):
        d.mkdir(parents=True, exist_ok=True)

    def _profile(name_us: str, name: str) -> str:
        stem = f"0000-00-00.artifact-profile-natural_entity.brocks_pressure_washing.{name_us}.profile"
        (pr / f"{stem}.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema": "mycite.site_core.profile.v1",
                    "profile_kind": "customer",
                    "entity_class": "natural_entity",
                    "owner": "brocks_pressure_washing",
                    "public": False,
                    "name": name,
                    "phone": "",
                    "address": "",
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        return stem

    def _custom(stem: str, total: float, paid: bool, tag: str) -> None:
        (cu / f"{stem}.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema": "mycite.site_core.custom.v1",
                    "kind": "artifact-custom",
                    "owner": "brocks_pressure_washing",
                    "customer_context": {"lead_source": None, "is_repeat": None, "referred_by": None},
                    "home": {},
                    "tags": [{"type": tag}] if tag else [],
                    "pricing": {"total": total, "paid": paid},
                    "notes": "",
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def _event(stem: str, *, eid, date, status, title, location, service, cref, xref) -> None:
        (ev / f"{stem}.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema": "mycite.site_core.event.v2",
                    "kind": "artifact-event-finite",
                    "recurrence": "finite",
                    "owner": "brocks_pressure_washing",
                    "id": eid,
                    "date": date,
                    "status": status,
                    "title": title,
                    "location": location,
                    "service": service,
                    "customer_ref": cref,
                    "custom_ref": xref,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    p1 = _profile("jane_roe", "Jane Roe")
    c1 = "2026-05-01.artifact-custom.brocks_pressure_washing-jobs.akron"
    _custom(c1, 250.0, True, "driveway")
    _event(
        "2026-05-01.artifact-event-finite.brocks_pressure_washing.jane_roe",
        eid="2026-0001", date="2026-05-01", status="completed",
        title="Driveway wash", location="Akron", service="driveway", cref=p1, xref=c1,
    )

    p2 = _profile("bob", "Bob")
    c2 = "2026-04-10.artifact-custom.brocks_pressure_washing-jobs.deck"
    _custom(c2, 120, False, "deck")
    _event(
        "2026-04-10.artifact-event-finite.brocks_pressure_washing.bob",
        eid="2026-0002", date="2026-04-10", status="booked",
        title="Deck", location="", service="deck", cref=p2, xref=c2,
    )

    # The tracked *.example.* template must be ignored, not counted.
    (ev / "0000-00-00.artifact-event-finite.sample.template.example.yaml").write_text(
        "schema: mycite.site_core.event.v2\n", encoding="utf-8"
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

    def test_custom_detail_lists_and_scopes_residuals(self) -> None:
        # _seed_events writes two artifact-custom residuals owned by BPW.
        detail = rx.custom_detail(self.tmp)
        self.assertEqual(detail["count"], 2)
        row = detail["rows"][0]
        self.assertIn("event_ref", row)
        self.assertIn("services", row)
        # Owner-scoping: the owning grantee sees them; another does not.
        self.assertEqual(rx.custom_detail(self.tmp, client="brocks_pressure_washing")["count"], 2)
        self.assertEqual(rx.custom_detail(self.tmp, client="other_co")["count"], 0)

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
    _write_shared_manifest(
        assets, "site",
        icon=[{
            "asset_id": "mail",
            "asset_path": "/assets/icons/0000-00-00.artifact-icon.mycite-ui.mail.svg",
            "consumers": [],
            "entity_scope": "site",
        }],
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
            / "0000-00-00.record-manifest.site-website.shared_resources.yaml"
        )
        data = yaml.safe_load(manifest.read_text())
        self.assertEqual(data["resources"]["icon"][0]["asset_id"], "Mail Glyph")

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
            / "0000-00-00.record-manifest.site-website.shared_resources.yaml"
        )
        data = yaml.safe_load(manifest.read_text())
        self.assertEqual(
            data["resources"]["icon"][0]["asset_path"],
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
    # site.org consolidated manifest: profile section referencing farm_a's canonical.
    _write_shared_manifest(
        assets, "site",
        profile=[{
            "asset_id": "farm_a",
            "asset_path": "/assets/profiles/0000-00-00.artifact-profile-legal_entity.farm_a.profile.yaml",
            "consumers": [], "entity_scope": "site",
        }],
    )
    # Hand-authored data file with a /profile/farm_a URL.
    data = root / "clients" / "site.org" / "frontend" / "data"
    data.mkdir(parents=True)
    (data / "timeline.json").write_text(
        '{"items":[{"profile_path":"/profile/farm_a"}]}\n', encoding="utf-8"
    )
    # FND consolidated manifest: profile section drives the network map. A stub
    # build_farm_network.py makes the site "mapped" (so the cascade regenerates).
    fnd = root / "clients" / "fruitfulnetworkdevelopment.com" / "frontend" / "assets"
    _write_shared_manifest(
        fnd, "fruitful_network_development_llc",
        profile=[
            {"asset_id": "farm_a",
             "asset_path": "/assets/profiles/0000-00-00.artifact-profile-legal_entity.farm_a.profile.yaml",
             "consumers": [], "entity_scope": "fruitful_network_development_llc"},
            {"asset_id": "farm_b",
             "asset_path": "/assets/profiles/0000-00-00.artifact-profile-legal_entity.farm_b.profile.yaml",
             "consumers": [], "entity_scope": "fruitful_network_development_llc"},
        ],
    )
    scripts = root / "clients" / "fruitfulnetworkdevelopment.com" / "frontend" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "build_farm_network.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
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
        # site.org consolidated manifest profile section repointed.
        pu = yaml.safe_load((assets / "0000-00-00.record-manifest.site-website.shared_resources.yaml").read_text())
        self.assertIn("farm_c.profile.yaml", pu["resources"]["profile"][0]["asset_path"])
        self.assertEqual(pu["resources"]["profile"][0]["asset_id"], "farm_c")
        # FND consolidated manifest profile section (drives the map) updated.
        fnd = yaml.safe_load((self.tmp / "clients" / "fruitfulnetworkdevelopment.com" / "frontend" / "assets"
                              / "0000-00-00.record-manifest.fruitful_network_development_llc-website.shared_resources.yaml").read_text())
        fnd_slugs = {e["asset_id"] for e in fnd["resources"]["profile"]}
        self.assertIn("farm_c", fnd_slugs)
        self.assertNotIn("farm_a", fnd_slugs)
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


def _seed_fnd_network(root: Path, refs: list[str], extra_profiles: list[str] | None = None) -> Path:
    """Shared profiles for ``refs`` (+ any ``extra_profiles`` off the map), an FND
    CONSOLIDATED manifest whose profile section lists ``refs``, and a stub
    build_farm_network.py so FND counts as a "mapped" site."""
    sc = root / "clients" / "_shared" / "site-core" / "profiles"
    sc.mkdir(parents=True)
    for slug in list(refs) + list(extra_profiles or []):
        (sc / f"0000-00-00.artifact-profile-legal_entity.{slug}.profile.yaml").write_text(
            yaml.safe_dump({"name": slug.replace("_", " ").title()}, sort_keys=False),
            encoding="utf-8",
        )
    fnd_assets = root / "clients" / rx._FND_SITE_DIR / "frontend" / "assets"
    _write_shared_manifest(
        fnd_assets, "fruitful_network_development_llc",
        profile=[
            {"asset_id": slug,
             "asset_path": f"/assets/profiles/0000-00-00.artifact-profile-legal_entity.{slug}.profile.yaml",
             "consumers": [], "entity_scope": "fruitful_network_development_llc"}
            for slug in refs
        ],
    )
    scripts = root / "clients" / rx._FND_SITE_DIR / "frontend" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "build_farm_network.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    return root


def _fnd_profile_section(tmp: Path) -> list[str]:
    """The slugs currently in the FND consolidated manifest profile section."""
    return [e["asset_id"] for e in rx.site_manifest_entries(tmp, rx._FND_SITE_DIR, "profile")]


class NetworkRefsAllocationTests(unittest.TestCase):
    """FND profiles allocate via the consolidated manifest profile section, which
    drives the /more network map (the section is the single source of truth)."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="ext_res_netrefs_"))
        _seed_fnd_network(self.tmp, ["wellspring_farm", "rose_leaf"], extra_profiles=["off_map_farm"])
        # Stub the network-map rebuild subprocess (the seeded build script is a
        # no-op stub anyway; this records invocations + avoids spawning python).
        self._builds: list[str] = []
        self._orig_build = rx._run_site_network_build
        rx._run_site_network_build = lambda wr, site: (self._builds.append(site) or (True, "stub"))

    def tearDown(self) -> None:
        rx._run_site_network_build = self._orig_build

    def test_profile_section_ordered(self) -> None:
        self.assertEqual(_fnd_profile_section(self.tmp), ["wellspring_farm", "rose_leaf"])

    def test_add_and_remove_mutate_section_and_rebuild(self) -> None:
        ap = "/assets/profiles/0000-00-00.artifact-profile-legal_entity.off_map_farm.profile.yaml"
        added = rx.add_asset_to_manifest(
            self.tmp, site=rx._FND_SITE_DIR, kind="profile", asset_id="off_map_farm", asset_path=ap
        )
        self.assertTrue(added["ok"] and added["added"])
        self.assertEqual(
            _fnd_profile_section(self.tmp),
            ["wellspring_farm", "rose_leaf", "off_map_farm"],  # appended, order kept
        )
        # idempotent add = no-op (still ok), but still ran the build hook once on add.
        again = rx.add_asset_to_manifest(
            self.tmp, site=rx._FND_SITE_DIR, kind="profile", asset_id="off_map_farm", asset_path=ap
        )
        self.assertTrue(again["ok"] and not again["added"])
        removed = rx.remove_asset_from_manifest(
            self.tmp, site=rx._FND_SITE_DIR, kind="profile",
            asset_path="/assets/profiles/0000-00-00.artifact-profile-legal_entity.rose_leaf.profile.yaml",
        )
        self.assertTrue(removed["ok"] and removed["removed"])
        self.assertEqual(_fnd_profile_section(self.tmp), ["wellspring_farm", "off_map_farm"])
        # add(once-real) + remove(once) each fired the build hook; the no-op add did not.
        self.assertEqual(self._builds, [rx._FND_SITE_DIR, rx._FND_SITE_DIR])

    def test_non_mapped_site_profile_does_not_rebuild(self) -> None:
        # A profile on a site with NO build script writes the manifest but fires
        # no rebuild. (site.org here has no consolidated manifest -> no_manifest.)
        ap = "/assets/profiles/0000-00-00.artifact-profile-legal_entity.wellspring_farm.profile.yaml"
        res = rx.add_asset_to_manifest(
            self.tmp, site="site.org", kind="profile", asset_id="w", asset_path=ap
        )
        self.assertFalse(res["ok"])
        self.assertEqual(self._builds, [])

    def test_allocation_payload_profiles_reflect_section(self) -> None:
        payload = render_extension(
            "ext_resources",
            {
                "webapps_root": self.tmp,
                "mode": "grantee",
                "grantee": {"msn_id": "fnd", "label": "FND"},
                "domain": rx._FND_SITE_DIR,
            },
        )
        self.assertEqual(payload["resources_mode"], "allocation")
        prof = next(a for a in payload["allocations"] if a["gallery"] == "profiles")
        self.assertEqual(prof["used_count"], 2)  # the two profile-section entries
        allocated = {c["slug"] for c in prof["candidates"] if c["allocated"]}
        self.assertEqual(allocated, {"wellspring_farm", "rose_leaf"})
        available = {c["slug"] for c in prof["candidates"] if not c["allocated"]}
        self.assertIn("off_map_farm", available)

    def test_profile_usage_and_index_in_use_by(self) -> None:
        label = f"{rx._FND_SITE_DIR} (network map /more)"
        self.assertIn(label, rx.profile_usage(self.tmp, "wellspring_farm"))
        self.assertEqual(rx.profile_usage(self.tmp, "off_map_farm"), [])
        idx = rx.build_leaflet_index(self.tmp)
        on_map = next(r for r in idx if r["slug"] == "wellspring_farm")
        self.assertTrue(on_map["in_use"])
        self.assertIn(label, on_map["in_use_by"])
        off_map = next(r for r in idx if r["slug"] == "off_map_farm")
        self.assertFalse(off_map["in_use"])
        self.assertEqual(off_map["in_use_by"], [])


class OwnerLinkRewriteTests(unittest.TestCase):
    """O5 — a profile rename must repoint event leaflets linked by ``owner:``."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="ext_owner_links_"))
        self.ev = self.root / "clients" / "_shared" / "site-core" / "event"
        self.ev.mkdir(parents=True)

    def _event(self, name: str, owner: str) -> Path:
        p = self.ev / name
        p.write_text(yaml.safe_dump(
            {"schema": "mycite.site_core.event.v2", "owner": owner, "title": "Market Day"},
            sort_keys=False), encoding="utf-8")
        return p

    def test_owner_link_files_filters_by_owner(self) -> None:
        self._event("2026-05-20.artifact-event-finite.greenfield_berry_farm.a.yaml", "greenfield_berry_farm")
        self._event("2026-05-20.artifact-event-finite.zzz.b.yaml", "zzz")
        hits = rx._owner_link_files(self.root, "greenfield_berry_farm")
        self.assertEqual([p.name for p in hits],
                         ["2026-05-20.artifact-event-finite.greenfield_berry_farm.a.yaml"])

    def test_rewrite_owner_links_repoints_and_renames(self) -> None:
        self._event("2026-05-20.artifact-event-finite.greenfield_berry_farm.market.yaml",
                    "greenfield_berry_farm")
        self._event("2026-05-20.artifact-event-finite.other_farm.market.yaml", "other_farm")
        changes = rx._rewrite_owner_links(self.root, "greenfield_berry_farm", "greenfield_farm")
        self.assertEqual(len(changes), 1)
        names = {p.name for p in self.ev.glob("*.yaml")}
        self.assertIn("2026-05-20.artifact-event-finite.greenfield_farm.market.yaml", names)
        self.assertNotIn("2026-05-20.artifact-event-finite.greenfield_berry_farm.market.yaml", names)
        moved = yaml.safe_load(
            (self.ev / "2026-05-20.artifact-event-finite.greenfield_farm.market.yaml").read_text())
        self.assertEqual(moved["owner"], "greenfield_farm")
        # the unrelated farm's event is untouched (no bleed)
        other = yaml.safe_load(
            (self.ev / "2026-05-20.artifact-event-finite.other_farm.market.yaml").read_text())
        self.assertEqual(other["owner"], "other_farm")


class ManifestCorruptionGuardTests(unittest.TestCase):
    """O3 — add_asset_to_manifest must NOT overwrite an unparseable manifest."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="ext_manifest_guard_"))
        self.assets = self.root / "clients" / "demo.com" / "frontend" / "assets"
        self.assets.mkdir(parents=True)
        self.mp = self.assets / "0000-00-00.demo.shared_resources.yaml"

    def test_add_asset_refuses_unparseable_manifest(self) -> None:
        self.mp.write_text("resources:\n  image: [unclosed\n", encoding="utf-8")  # invalid YAML
        before = self.mp.read_text()
        r = rx.add_asset_to_manifest(self.root, site="demo.com", kind="image",
                                     asset_id="x", asset_path="/assets/images/x.avif")
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "unparseable_manifest")
        self.assertEqual(before, self.mp.read_text())  # left intact for a human


if __name__ == "__main__":
    unittest.main()
