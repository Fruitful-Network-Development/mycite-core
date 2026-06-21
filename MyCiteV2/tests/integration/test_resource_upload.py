"""Wave-1 — POST /portal/api/resources/upload contract.

Exercises the upload+AVIF backend end-to-end through the Flask test client
against a TEMP webapps_root:

  - a raster PNG posted as kind=image is converted to AVIF and lands in the
    image/ gallery as an ``.avif`` artifact;
  - an SVG posted as kind=icon lands in icon/ unchanged (bytes + name);
  - a path-traversal slug is rejected with 400 and writes nothing.

avifenc (the real binary at /usr/bin/avifenc) is used directly — no mocking —
so the conversion path is genuinely verified.
"""

from __future__ import annotations

import base64
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None
# AVIF conversion shells out to the avifenc binary (prod + CI install it). Guard
# the conversion-dependent tests so the suite skips (not fails) on a machine
# without it.
HAS_AVIFENC = os.path.exists("/usr/bin/avifenc")

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app

# A valid 1x1 truecolor PNG (red pixel). Decoded inline so the test carries no
# binary fixture file. avifenc reads this happily.
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)

_SVG_ICON = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M0 0h16v16H0z"/></svg>'

_SITE_CORE = ("clients", "_shared", "site-core")


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class ResourceUploadRouteTests(unittest.TestCase):
    def _build_client(self):
        tmp = Path(tempfile.mkdtemp(prefix="w1_resource_upload_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        authority_db = tmp / "authority.sqlite3"
        authority_db.touch()
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="fruitfulnetworkdevelopment.com",
            webapps_root=tmp / "webapps",
            authority_db_file=authority_db,
        )
        return create_app(config).test_client(), tmp

    def _gallery(self, tmp: Path, name: str) -> Path:
        return tmp.joinpath("webapps", *_SITE_CORE, name)

    def _post(self, client, *, data_bytes, filename, kind, **form):
        payload = {
            "kind": kind,
            "title": form.pop("title", "A Title"),
            "slug": form.pop("slug", "my-slug"),
            "given_name": form.pop("given_name", ""),
            "owner": form.pop("owner", "fnd_owner"),
            **form,
            "file": (io.BytesIO(data_bytes), filename),
        }
        return client.post(
            "/portal/api/resources/upload",
            data=payload,
            content_type="multipart/form-data",
            base_url="http://fruitfulnetworkdevelopment.com",
        )

    @unittest.skipUnless(HAS_AVIFENC, "avifenc (/usr/bin/avifenc) not installed")
    def test_png_image_is_converted_to_avif(self) -> None:
        client, tmp = self._build_client()
        resp = self._post(
            client,
            data_bytes=_PNG_1X1,
            filename="photo.png",
            kind="image",
            slug="brand-mark",
            owner="brocks_pressure_washing",
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["asset_id"].endswith(".avif"))

        image_dir = self._gallery(tmp, "image")
        avifs = list(image_dir.glob("*.avif"))
        self.assertEqual(len(avifs), 1, f"expected one .avif, found {avifs}")
        written = avifs[0]
        self.assertEqual(
            written.name,
            "0000-00-00.artifact-image.brocks_pressure_washing.brand-mark.avif",
        )
        # The stored bytes are a real AVIF (ISO-BMFF ftyp box), not the PNG.
        head = written.read_bytes()[:12]
        self.assertEqual(head[4:8], b"ftyp")
        self.assertNotEqual(written.read_bytes()[:8], _PNG_1X1[:8])

    @unittest.skipUnless(HAS_AVIFENC, "avifenc (/usr/bin/avifenc) not installed")
    def test_already_avif_passes_through(self) -> None:
        client, tmp = self._build_client()
        # Minimal AVIF-looking header is not enough for avifenc; reuse a real
        # AVIF produced from the PNG by uploading the PNG first, then re-upload
        # the produced bytes as an AVIF.
        resp1 = self._post(
            client, data_bytes=_PNG_1X1, filename="p.png", kind="image", slug="seed"
        )
        avif_path = self._gallery(tmp, "image") / resp1.get_json()["asset_id"]
        avif_bytes = avif_path.read_bytes()

        resp2 = self._post(
            client,
            data_bytes=avif_bytes,
            filename="already.avif",
            kind="image",
            slug="passthru",
        )
        self.assertEqual(resp2.status_code, 200, resp2.get_data(as_text=True))
        stored = self._gallery(tmp, "image") / resp2.get_json()["asset_id"]
        self.assertEqual(stored.read_bytes(), avif_bytes)

    def test_svg_icon_lands_unchanged(self) -> None:
        client, tmp = self._build_client()
        resp = self._post(
            client,
            data_bytes=_SVG_ICON,
            filename="logo.svg",
            kind="icon",
            slug="logo",
            owner="mycite-ui",
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertEqual(
            body["asset_id"], "0000-00-00.artifact-icon.mycite-ui.logo.svg"
        )
        icon_dir = self._gallery(tmp, "icon")
        written = icon_dir / body["asset_id"]
        self.assertTrue(written.exists())
        self.assertEqual(written.read_bytes(), _SVG_ICON)

    def test_profile_yaml_lands_in_profiles(self) -> None:
        client, tmp = self._build_client()
        resp = self._post(
            client,
            data_bytes=b"schema: profile\nname: Acme\n",
            filename="acme.yaml",
            kind="profile",
            slug="acme_farm",
            given_name="legal_entity",
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertEqual(
            body["asset_id"],
            "0000-00-00.artifact-profile-legal_entity.acme_farm.profile.yaml",
        )
        self.assertTrue((self._gallery(tmp, "profiles") / body["asset_id"]).exists())

    def test_path_traversal_slug_rejected(self) -> None:
        client, tmp = self._build_client()
        resp = self._post(
            client,
            data_bytes=_SVG_ICON,
            filename="x.svg",
            kind="icon",
            slug="../../../etc/passwd",
            owner="mycite-ui",
        )
        self.assertEqual(resp.status_code, 400)
        body = resp.get_json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "invalid_upload")
        # Nothing leaked outside the gallery.
        icon_dir = self._gallery(tmp, "icon")
        self.assertEqual(list(icon_dir.glob("*")) if icon_dir.exists() else [], [])

    def test_path_traversal_owner_rejected(self) -> None:
        client, _tmp = self._build_client()
        resp = self._post(
            client,
            data_bytes=_SVG_ICON,
            filename="x.svg",
            kind="icon",
            slug="ok",
            owner="../evil",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "invalid_upload")

    def test_unsupported_raster_rejected(self) -> None:
        client, _tmp = self._build_client()
        resp = self._post(
            client,
            data_bytes=b"GIF89a\x01\x00\x01\x00",
            filename="x.gif",
            kind="image",
            slug="gif-thing",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "invalid_upload")

    def test_missing_file_rejected(self) -> None:
        client, _tmp = self._build_client()
        resp = client.post(
            "/portal/api/resources/upload",
            data={"kind": "icon", "title": "t", "slug": "s", "owner": "o"},
            content_type="multipart/form-data",
            base_url="http://fruitfulnetworkdevelopment.com",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "file_required")

    # ---- logo kind (brand mark → 512² AVIF leaflet) --------------------
    def _use_stub_encoder(self, tmp: Path) -> None:
        """Stage a fake process_logos.py `_encode-batch` worker + point the
        encoder env at this interpreter, so the logo path is exercised without
        the real Pillow venv. The stub writes a sentinel AVIF per job."""
        scripts = tmp.joinpath("webapps", *_SITE_CORE, "scripts")
        scripts.mkdir(parents=True, exist_ok=True)
        (scripts / "process_logos.py").write_text(
            "import json, sys\n"
            "jobs = json.load(open(sys.argv[2]))\n"
            "for j in jobs:\n"
            "    open(j['dst'], 'wb').write(b'AVIFSTUB')\n"
            "json.dump([{'dst': j['dst'], 'status': 'ok-new'} for j in jobs],"
            " open(sys.argv[3], 'w'))\n",
            encoding="utf-8",
        )
        prev = os.environ.get("MYCITE_LOGO_ENCODER_PYTHON")
        os.environ["MYCITE_LOGO_ENCODER_PYTHON"] = sys.executable
        self.addCleanup(self._restore_encoder_env, prev)

    @staticmethod
    def _restore_encoder_env(prev) -> None:
        if prev is None:
            os.environ.pop("MYCITE_LOGO_ENCODER_PYTHON", None)
        else:
            os.environ["MYCITE_LOGO_ENCODER_PYTHON"] = prev

    def test_logo_kind_lands_as_logo_leaflet(self) -> None:
        client, tmp = self._build_client()
        self._use_stub_encoder(tmp)
        resp = self._post(
            client,
            data_bytes=_PNG_1X1,
            filename="bee.png",
            kind="logo",
            slug="aurora_springs_honey",
            owner="",  # ignored for logo
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        # No owner segment; role token is "logo" → matches a profile's
        # predetermined logo_ref so it resolves with no profile edit.
        self.assertEqual(
            body["asset_id"],
            "0000-00-00.artifact-logo.aurora_springs_honey.logo.avif",
        )
        self.assertEqual(body["gallery"], "image")
        written = self._gallery(tmp, "image") / body["asset_id"]
        self.assertEqual(written.read_bytes(), b"AVIFSTUB")

    def test_logo_unsupported_input_rejected(self) -> None:
        client, _tmp = self._build_client()
        resp = self._post(
            client,
            data_bytes=b"GIF89a\x01\x00\x01\x00",
            filename="x.gif",
            kind="logo",
            slug="acme_farm",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "invalid_upload")

    def test_logo_missing_encoder_returns_clear_400(self) -> None:
        client, tmp = self._build_client()
        prev = os.environ.get("MYCITE_LOGO_ENCODER_PYTHON")
        os.environ["MYCITE_LOGO_ENCODER_PYTHON"] = str(tmp / "no-such-python")
        self.addCleanup(self._restore_encoder_env, prev)
        resp = self._post(
            client,
            data_bytes=_PNG_1X1,
            filename="x.png",
            kind="logo",
            slug="acme_farm",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "invalid_upload")
        self.assertIn("logo encoder", resp.get_json()["detail"])


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class GranteeUploadTests(unittest.TestCase):
    """handle_grantee_upload: client uploads an image (→AVIF) or document into
    its OWN site + registers it in the record-manifest. Image/document only."""

    def _site(self):
        import yaml
        tmp = Path(tempfile.mkdtemp(prefix="grantee_upload_"))
        assets = tmp / "example.test" / "frontend" / "assets"
        assets.mkdir(parents=True)
        man = assets / "0000-00-00.record-manifest.test_site-website.shared_resources.yaml"
        man.write_text(yaml.safe_dump({
            "manifest_kind": "record-manifest", "site_entity": "test_site",
            "site_domain": "example.test",
            "resources": {"image": [], "document": []},
        }), encoding="utf-8")
        return tmp, man

    @unittest.skipUnless(HAS_AVIFENC, "avifenc required")
    def test_image_upload_converts_to_avif_and_registers(self):
        import yaml
        from MyCiteV2.instances._shared.runtime.utilities_extensions.resource_upload import (
            handle_grantee_upload,
        )
        tmp, man = self._site()
        res = handle_grantee_upload(
            _PNG_1X1, "shot.png", "image", title="Hero", slug="hero_shot",
            domain="example.test", clients_root=tmp,
        )
        self.assertEqual(res["asset_id"], "0000-00-00.artifact-image.test_site.hero_shot")
        self.assertEqual(res["asset_path"], "/assets/images/0000-00-00.artifact-image.test_site.hero_shot.avif")
        out = tmp / "example.test/frontend/assets/images/0000-00-00.artifact-image.test_site.hero_shot.avif"
        self.assertTrue(out.exists())
        self.assertIn(b"ftyp", out.read_bytes()[:16])
        ids = [e["asset_id"] for e in yaml.safe_load(man.read_text())["resources"]["image"]]
        self.assertIn("0000-00-00.artifact-image.test_site.hero_shot", ids)

    def test_document_upload_registers(self):
        import yaml
        from MyCiteV2.instances._shared.runtime.utilities_extensions.resource_upload import (
            handle_grantee_upload,
        )
        tmp, man = self._site()
        res = handle_grantee_upload(
            b"%PDF-1.4 test", "resume.pdf", "document", title="Resume",
            slug="resume", domain="example.test", clients_root=tmp,
        )
        self.assertEqual(res["asset_path"], "/assets/documents/0000-00-00.artifact-document.test_site.resume.pdf")
        self.assertEqual(len(yaml.safe_load(man.read_text())["resources"]["document"]), 1)

    def test_rejects_non_select_kinds(self):
        from MyCiteV2.instances._shared.runtime.utilities_extensions.resource_upload import (
            UploadError, handle_grantee_upload,
        )
        tmp, _ = self._site()
        for kind in ("icon", "profile", "logo", "type"):
            with self.assertRaises(UploadError):
                handle_grantee_upload(_SVG_ICON, "x.svg", kind, title="x",
                                      slug="x", domain="example.test", clients_root=tmp)

    def test_rejects_traversal_slug(self):
        from MyCiteV2.instances._shared.runtime.utilities_extensions.resource_upload import (
            UploadError, handle_grantee_upload,
        )
        tmp, _ = self._site()
        with self.assertRaises(UploadError):
            handle_grantee_upload(_PNG_1X1, "x.png", "image", title="x",
                                  slug="../evil", domain="example.test", clients_root=tmp)
