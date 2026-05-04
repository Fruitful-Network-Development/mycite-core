from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import FilesystemFndDcmReadOnlyAdapter
from MyCiteV2.packages.ports.fnd_dcm_read_only import FndDcmReadOnlyRequest


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_fnd_dcm_profile(
    private_dir: Path,
    *,
    domain: str,
    manifest_relative_path: str = "assets/docs/manifest.json",
    render_script_relative_path: str = "scripts/render_manifest.py",
    label: str = "",
    schema: str = "mycite.service_tool.fnd_dcm.profile.v1",
) -> None:
    tool_root = private_dir / "utilities" / "tools" / "fnd-dcm"
    tool_root.mkdir(parents=True, exist_ok=True)
    _write_json(
        tool_root / f"fnd-dcm.{domain.split('.', 1)[0]}.json",
        {
            "schema": schema,
            "domain": domain,
            "label": label or domain,
            "manifest_relative_path": manifest_relative_path,
            "render_script_relative_path": render_script_relative_path,
        },
    )


def _write_cvcc_frontend(webapps_root: Path) -> None:
    frontend_root = webapps_root / "clients" / "cuyahogavalleycountrysideconservancy.org" / "frontend"
    _write_json(
        frontend_root / "assets" / "docs" / "manifest.json",
        {
            "schema": "webdz.site_content.v2",
            "site": {
                "name": "CVCC",
                "description": "Countryside",
                "homepage_href": "index.html",
                "shell": {"masthead_class": "masthead"},
            },
            "navigation": [{"id": "home", "label": "Home", "href": "index.html"}],
            "footer": {"columns": [{"template": "rich_text"}], "copyright": "©"},
            "collections": {
                "board_profiles": {"type": "json_file", "source": "assets/docs/board_profiles.json"},
                "blog_posts": {
                    "type": "markdown_directory",
                    "directory": "assets/docs/blogs",
                    "pattern": "*.md",
                    "sort_by": "published_sort",
                    "sort_order": "desc",
                },
            },
            "pages": {
                "people": {
                    "file": "people.html",
                    "template": "board_directory",
                    "content": {"collection": "board_profiles"},
                },
                "newsletter": {
                    "file": "newsletter.html",
                    "template": "article_archive",
                    "content": {"collection": "blog_posts"},
                },
            },
        },
    )
    _write_json(
        frontend_root / "assets" / "docs" / "board_profiles.json",
        [
            {
                "name": "Jane Example",
                "alternative_email": "~",
                "contact_phone_number": "330-555-0100",
                "bio": ["Jane supports local farming.", "She helps with outreach."],
                "socials": [{"linkedin": "linkedin.com/in/jane-example"}],
                "tags": ["board_chair"],
            }
        ],
    )
    (frontend_root / "assets" / "docs" / "blogs").mkdir(parents=True, exist_ok=True)
    (frontend_root / "assets" / "docs" / "blogs" / "spring.md").write_text("# Spring\n", encoding="utf-8")
    (frontend_root / "scripts").mkdir(parents=True, exist_ok=True)
    (frontend_root / "scripts" / "render_manifest.py").write_text("print('ok')\n", encoding="utf-8")


def _write_tff_frontend(webapps_root: Path) -> None:
    frontend_root = webapps_root / "clients" / "trappfamilyfarm.com" / "frontend"
    _write_json(
        frontend_root / "assets" / "docs" / "manifest.json",
        {
            "schema": "webdz.site_content.v3",
            "site": {
                "name": "Trapp Family Farm",
                "homepage_href": "home.html",
                "shell": {"menu_label": "Menu"},
            },
            "icons": {"favicon": "/favicon.svg"},
            "navigation": [{"id": "home", "label": "Home", "href": "home.html"}],
            "footer": {"columns": [{"template": "contact_lines"}], "copyright": "©"},
            "collections": {
                "newsletters": {
                    "type": "markdown_documents",
                    "items": [{"source": "assets/docs/newsletters/fall-2024.md"}],
                }
            },
            "machine": {
                "inpage": {
                    "root": "machine/inpage",
                    "blocks": [
                        {
                            "id": "tff-org-schema",
                            "source": "home.organization.ld+json",
                            "injection_pattern": "script:application/ld+json",
                            "page": "/home.html",
                        }
                    ],
                },
                "pages": {
                    "root": "machine/pages",
                    "endpoints": [
                        {"rel": "machine-index", "href": "/machine/pages/tff-machine-index.json", "format": "application/json"}
                    ],
                },
                "endpoint_maps": {
                    "machine_index": "/machine/pages/tff-machine-index.json",
                    "page_manifest": "/machine/pages/tff-pages.manifest.json",
                    "llm_context": "/llms.md",
                    "organization_schema_id": "tff-org-schema",
                },
            },
            "pages": {
                "home": {"file": "home.html", "template": "home_featured"},
                "newsletter": {
                    "file": "newsletter.html",
                    "template": "article_archive",
                    "content": {"collection": "newsletters"},
                },
            },
        },
    )
    (frontend_root / "assets" / "docs" / "newsletters").mkdir(parents=True, exist_ok=True)
    (frontend_root / "assets" / "docs" / "newsletters" / "fall-2024.md").write_text("# Fall\n", encoding="utf-8")
    (frontend_root / "scripts").mkdir(parents=True, exist_ok=True)
    (frontend_root / "scripts" / "render_manifest.py").write_text("print('ok')\n", encoding="utf-8")


class FilesystemFndDcmReadOnlyAdapterTests(unittest.TestCase):
    def test_reads_v2_and_v3_manifests_into_one_projection(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            private_dir = root / "private"
            webapps_root = root / "webapps"
            _write_cvcc_frontend(webapps_root)
            _write_tff_frontend(webapps_root)
            _write_fnd_dcm_profile(
                private_dir,
                domain="cuyahogavalleycountrysideconservancy.org",
                label="CVCC",
            )
            _write_fnd_dcm_profile(
                private_dir,
                domain="trappfamilyfarm.com",
                label="Trapp Family Farm",
            )

            result = FilesystemFndDcmReadOnlyAdapter(
                private_dir,
                webapps_root=webapps_root,
            ).read_fnd_dcm_read_only(
                FndDcmReadOnlyRequest(
                    portal_tenant_id="fnd",
                    site="cuyahogavalleycountrysideconservancy.org",
                )
            )

            profiles = result.source.payload["profiles"]
            self.assertEqual(len(profiles), 2)
            cvcc = profiles[0]
            tff = profiles[1]
            self.assertEqual(cvcc["manifest_schema"], "webdz.site_content.v2")
            self.assertEqual(tff["manifest_schema"], "webdz.site_content.v3")
            self.assertEqual(cvcc["projection"]["site"]["name"], "CVCC")
            self.assertEqual(tff["projection"]["site"]["name"], "Trapp Family Farm")
            self.assertEqual(cvcc["projection"]["collections"][0]["id"], "board_profiles")
            self.assertEqual(tff["projection"]["collections"][0]["id"], "newsletters")
            self.assertTrue(cvcc["collection_sources"])
            machine_summary = tff["projection"]["extensions"]["machine_surface_summary"]
            self.assertEqual(machine_summary["inpage_block_count"], 1)
            self.assertEqual(machine_summary["endpoint_count"], 1)

    def test_missing_manifest_and_render_script_are_reported(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            private_dir = root / "private"
            webapps_root = root / "webapps"
            frontend_root = webapps_root / "clients" / "trappfamilyfarm.com" / "frontend"
            frontend_root.mkdir(parents=True, exist_ok=True)
            _write_fnd_dcm_profile(private_dir, domain="trappfamilyfarm.com")

            result = FilesystemFndDcmReadOnlyAdapter(
                private_dir,
                webapps_root=webapps_root,
            ).read_fnd_dcm_read_only(FndDcmReadOnlyRequest(portal_tenant_id="fnd"))

            profile = result.source.payload["profiles"][0]
            issue_codes = {row["code"] for row in profile["issues"]}
            self.assertIn("manifest_missing", issue_codes)
            self.assertIn("render_script_missing", issue_codes)

    def test_invalid_relative_path_and_unsupported_schema_are_captured(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            private_dir = root / "private"
            webapps_root = root / "webapps"
            _write_cvcc_frontend(webapps_root)
            _write_fnd_dcm_profile(
                private_dir,
                domain="cuyahogavalleycountrysideconservancy.org",
                manifest_relative_path="../escape.json",
                schema="mycite.service_tool.fnd_dcm.profile.v9",
            )
            _write_fnd_dcm_profile(
                private_dir,
                domain="trappfamilyfarm.com",
                manifest_relative_path="../escape.json",
            )

            result = FilesystemFndDcmReadOnlyAdapter(
                private_dir,
                webapps_root=webapps_root,
            ).read_fnd_dcm_read_only(FndDcmReadOnlyRequest(portal_tenant_id="fnd"))

            self.assertIn("Skipping unsupported FND-DCM profile schema", " ".join(result.source.payload["warnings"]))
            profile = result.source.payload["profiles"][0]
            issue_codes = {row["code"] for row in profile["issues"]}
            self.assertIn("manifest_path_invalid", issue_codes)


if __name__ == "__main__":
    unittest.main()
