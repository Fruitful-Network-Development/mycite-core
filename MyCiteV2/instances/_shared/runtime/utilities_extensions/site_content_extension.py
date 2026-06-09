"""Grantee-facing site page-content editor — typed slots in the existing manifest.

The dashboard "Design" tab lets a grantee edit the text and swap the images/icons
of their own site, constrained to the **typed slots** an operator marked editable
in the site manifest (a section's ``html`` carries ``{{slot}}`` placeholders + a
``fields`` list — see ``frontend/scripts/render_lib/templates.py``). There is no
separate content store: this module patches the field *values* in the manifest and
re-runs the site's deterministic ``render_manifest.py`` so the edit reaches live HTML.

Reuses the profile-editor machinery in ``resources_extension`` (atomic write, the
record-manifest asset listing) rather than reinventing it.
"""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import resources_extension as rx

# Sites whose manifest has been converted to typed slots + are wired live. Other
# sites get {enabled: false} so the shared dashboard tab degrades gracefully.
EDITABLE_SITES: frozenset[str] = frozenset({"fruitfulnetworkdevelopment.com"})

_TEXT_TYPES = frozenset({"text", "textarea"})
_ASSET_TYPES = frozenset({"image_ref", "icon_ref"})
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SYMBOL_RE = re.compile(r'<symbol[^>]*\bid="([A-Za-z0-9_-]+)"')


def site_content_enabled(site: str) -> bool:
    return os.path.basename(rx._as_text(site)) in EDITABLE_SITES


def _frontend_dir(webapps_root: str | Path | None, site: str) -> Path | None:
    if not webapps_root:
        return None
    d = Path(webapps_root) / "clients" / os.path.basename(rx._as_text(site)) / "frontend"
    return d if d.is_dir() else None


def _site_manifest_path(webapps_root: str | Path | None, site: str) -> Path | None:
    fd = _frontend_dir(webapps_root, site)
    if fd is None:
        return None
    matches = sorted(glob.glob(str(fd / "assets" / "*.manifest.*.site.json")))
    return Path(matches[0]) if matches else None


def _clean_text(value: Any) -> str:
    return _CONTROL_RE.sub("", "" if value is None else str(value))


def _icon_options(webapps_root: str | Path | None) -> list[str]:
    """Sprite symbols available for icon_ref slots: every ``<symbol id>`` in each
    shared sprite, as a ``/assets/icons/<sprite>.svg#<id>`` href."""
    core = rx._site_core_root(webapps_root)
    if core is None:
        return []
    out: list[str] = []
    for sprite in sorted((core / "icon").glob("*sprite*.svg")):
        url = "/assets/icons/" + sprite.name
        try:
            text = sprite.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        out.extend(url + "#" + sym for sym in _SYMBOL_RE.findall(text))
    return out


def _editable_sections(manifest: dict[str, Any]) -> list[tuple[str, dict, dict]]:
    """(page_key, section, field-by-key) for every section carrying fields."""
    found: list[tuple[str, dict, dict]] = []
    pages = manifest.get("pages")
    if not isinstance(pages, dict):
        return found
    for page_key, page in pages.items():
        if not isinstance(page, dict):
            continue
        sections = (page.get("content") or {}).get("sections") if isinstance(page.get("content"), dict) else None
        if not isinstance(sections, list):
            continue
        for section in sections:
            if isinstance(section, dict) and isinstance(section.get("fields"), list) and section["fields"]:
                by_key = {f.get("key"): f for f in section["fields"] if isinstance(f, dict) and f.get("key")}
                found.append((page_key, section, by_key))
    return found


def _asset_options(webapps_root: str | Path | None, site: str, manifest: dict[str, Any]) -> dict[str, list[str]]:
    """Allow-listed asset paths a grantee may pick: the site's record-manifest
    images + sprite icons, unioned with whatever the slots already reference (so a
    current value is always valid even if not separately allocated)."""
    images = [r["asset_path"] for r in rx.site_manifest_entries(webapps_root, site, "image") if r.get("asset_path")]
    icons = _icon_options(webapps_root)
    for _pk, _section, by_key in _editable_sections(manifest):
        for field in by_key.values():
            if field.get("type") == "image_ref" and field.get("value"):
                images.append(rx._as_text(field.get("value")))
            elif field.get("type") == "icon_ref" and field.get("value"):
                icons.append(rx._as_text(field.get("value")))
    # de-dupe, preserve order
    return {"image": list(dict.fromkeys(images)), "icon": list(dict.fromkeys(icons))}


def read_site_content(webapps_root: str | Path | None, site: str) -> dict[str, Any]:
    """Editable sections + asset pickers for a site's Design tab. ``enabled`` is
    false (with an empty body) for sites not yet wired."""
    site = os.path.basename(rx._as_text(site))
    if not site_content_enabled(site):
        return {"enabled": False, "site": site, "sections": [], "assets": {"image": [], "icon": []}}
    manifest_path = _site_manifest_path(webapps_root, site)
    if manifest_path is None:
        return {"enabled": False, "site": site, "sections": [], "assets": {"image": [], "icon": []}}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sections: list[dict[str, Any]] = []
    for page_key, section, _by_key in _editable_sections(manifest):
        sections.append({
            "page": page_key,
            "section_id": rx._as_text(section.get("id")),
            "label": rx._as_text((section.get("editor") or {}).get("label")) or rx._as_text(section.get("id")),
            "fields": [
                {
                    "key": rx._as_text(f.get("key")),
                    "label": rx._as_text(f.get("label")) or rx._as_text(f.get("key")),
                    "type": rx._as_text(f.get("type")) or "text",
                    "value": rx._as_text(f.get("value")),
                    "max_chars": f.get("max_chars") if isinstance(f.get("max_chars"), int) else None,
                }
                for f in section["fields"] if isinstance(f, dict) and f.get("key")
            ],
        })
    return {
        "enabled": True,
        "site": site,
        "sections": sections,
        "assets": _asset_options(webapps_root, site, manifest),
    }


def _render_site(frontend_dir: Path) -> tuple[bool, str]:
    """Re-run the site's deterministic render_manifest.py (full build; a manifest
    edit legitimately owns every page it regenerates)."""
    script = frontend_dir / "scripts" / "render_manifest.py"
    if not script.is_file():
        return False, f"no render_manifest.py at {script}"
    try:
        completed = subprocess.run(
            [sys.executable, str(script)],
            check=False, capture_output=True, timeout=300, cwd=str(frontend_dir),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"build failed to launch: {exc}"
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        return False, f"build exited {completed.returncode}: {detail[:400]}"
    return True, "rebuilt"


def save_site_content(webapps_root: str | Path | None, site: str, edits: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate + apply field-value edits to the manifest, then re-render.

    ``edits`` = ``[{page, section_id, key, value}, …]``. Each value is validated
    SERVER-side against the field's own declared type + max_chars and (for assets)
    the allow-list — the client cannot widen what's editable. Returns
    ``{ok, applied, errors, rebuilt}``.
    """
    site = os.path.basename(rx._as_text(site))
    if not site_content_enabled(site):
        return {"ok": False, "error": "not_editable"}
    manifest_path = _site_manifest_path(webapps_root, site)
    frontend_dir = _frontend_dir(webapps_root, site)
    if manifest_path is None or frontend_dir is None:
        return {"ok": False, "error": "no_manifest"}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # index sections by (page, id) and the allow-lists once.
    index: dict[tuple[str, str], dict] = {}
    for page_key, section, by_key in _editable_sections(manifest):
        index[(page_key, rx._as_text(section.get("id")))] = by_key
    allowed = _asset_options(webapps_root, site, manifest)

    errors: list[str] = []
    applied = 0
    for edit in edits if isinstance(edits, list) else []:
        if not isinstance(edit, dict):
            continue
        page = rx._as_text(edit.get("page"))
        sid = rx._as_text(edit.get("section_id"))
        key = rx._as_text(edit.get("key"))
        by_key = index.get((page, sid))
        field = by_key.get(key) if by_key else None
        if field is None:
            errors.append(f"{page}/{sid}/{key}: not an editable field")
            continue
        ftype = rx._as_text(field.get("type")) or "text"
        if ftype in _ASSET_TYPES:
            value = rx._as_text(edit.get("value"))
            kind = "image" if ftype == "image_ref" else "icon"
            if value not in allowed.get(kind, []):
                errors.append(f"{page}/{sid}/{key}: asset not in the {kind} library")
                continue
        else:
            value = _clean_text(edit.get("value"))
            max_chars = field.get("max_chars")
            if isinstance(max_chars, int) and len(value) > max_chars:
                errors.append(f"{page}/{sid}/{key}: exceeds {max_chars} characters")
                continue
        field["value"] = value
        applied += 1

    if errors:
        return {"ok": False, "errors": errors, "applied": 0}
    if applied == 0:
        return {"ok": True, "applied": 0, "rebuilt": False}

    text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    try:
        rx._atomic_write_text(manifest_path, text)
    except OSError as exc:
        return {"ok": False, "error": "write_failed", "detail": str(exc)}
    rebuilt, note = _render_site(frontend_dir)
    return {"ok": rebuilt, "applied": applied, "rebuilt": rebuilt, "detail": note}
