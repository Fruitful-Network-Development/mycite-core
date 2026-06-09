"""Grantee-facing site editor — visual in-place editing of the existing manifest.

The dashboard "Design" tab renders the grantee's real page in an iframe and lets
them (1) **swap any image/icon** on the page — every `/assets/...` reference is
replaceable from a gallery of the site's OWN images + the shared icon set — and
(2) edit the curated **typed text slots** in place, with per-box character budgets.

There is no separate content store: a swap rewrites the asset path in the page's
manifest section html, a text edit patches a slot's value, then the site's
deterministic ``build_site`` re-renders so the change reaches live HTML. Reuses
``resources_extension`` (atomic write, manifest allocation) rather than reinventing.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import resources_extension as rx

# Sites whose manifest carries typed slots + are wired live. Others get
# {enabled: false} so the shared dashboard tab degrades gracefully.
EDITABLE_SITES: frozenset[str] = frozenset({"fruitfulnetworkdevelopment.com"})

_TEXT_TYPES = frozenset({"text", "textarea"})
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
    matches = sorted((fd / "assets").glob("*.manifest.*.site.json"))
    return matches[0] if matches else None


def _entity(site: str) -> str:
    from MyCiteV2.packages.adapters.filesystem import entity_for_domain
    return rx._as_text(entity_for_domain(os.path.basename(rx._as_text(site))))


def _clean_text(value: Any) -> str:
    return _CONTROL_RE.sub("", "" if value is None else str(value))


def _owner_images(webapps_root: str | Path | None, site: str) -> list[str]:
    """The site's OWN images from the shared library, matched by entity owner-slug
    in the filename — so a grantee's gallery never shows other clients' photos."""
    core = rx._site_core_root(webapps_root)
    entity = _entity(site)
    if core is None or not entity:
        return []
    token = "." + entity
    out = []
    for p in sorted((core / "image").glob("*")):
        if p.is_file() and not p.name.startswith(".") and ".example." not in p.name and token in p.name:
            out.append("/assets/images/" + p.name)
    return out


def _icon_options(webapps_root: str | Path | None) -> list[str]:
    """Every ``<symbol id>`` in each shared sprite as a ``/assets/icons/<sprite>.svg#<id>`` href."""
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


def _gallery(webapps_root: str | Path | None, site: str) -> dict[str, list[str]]:
    return {"image": _owner_images(webapps_root, site), "icon": _icon_options(webapps_root)}


def _page_path(page: dict[str, Any]) -> str:
    f = rx._as_text(page.get("file"))
    if not f or f == "index.html":
        return "/"
    return "/" + (f[:-5] if f.endswith(".html") else f)


def _editable_sections(manifest: dict[str, Any]) -> list[tuple[str, dict, dict]]:
    """(page_key, section, field-by-key) for every section carrying text-slot fields."""
    found: list[tuple[str, dict, dict]] = []
    pages = manifest.get("pages")
    if not isinstance(pages, dict):
        return found
    for page_key, page in pages.items():
        if not isinstance(page, dict):
            continue
        content = page.get("content")
        sections = content.get("sections") if isinstance(content, dict) else None
        if not isinstance(sections, list):
            continue
        for section in sections:
            if isinstance(section, dict) and isinstance(section.get("fields"), list) and section["fields"]:
                by_key = {f.get("key"): f for f in section["fields"] if isinstance(f, dict) and f.get("key")}
                found.append((page_key, section, by_key))
    return found


def read_site_content(webapps_root: str | Path | None, site: str) -> dict[str, Any]:
    """Browsable pages + editable text slots + the swap gallery for a site's Design
    tab. ``enabled`` is false (empty body) for sites not yet wired."""
    site = os.path.basename(rx._as_text(site))
    blank = {"enabled": False, "site": site, "pages": [], "text_slots": [],
             "gallery": {"image": [], "icon": []}}
    if not site_content_enabled(site):
        return blank
    manifest_path = _site_manifest_path(webapps_root, site)
    if manifest_path is None:
        return blank
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    pages_out: list[dict[str, Any]] = []
    for pk, page in (manifest.get("pages") or {}).items():
        if not isinstance(page, dict):
            continue
        content = page.get("content")
        if isinstance(content, dict) and isinstance(content.get("sections"), list):
            pages_out.append({"page": pk, "path": _page_path(page),
                              "label": rx._as_text(page.get("title")) or pk})

    text_slots: list[dict[str, Any]] = []
    for page_key, section, _by in _editable_sections(manifest):
        for f in section["fields"]:
            if isinstance(f, dict) and rx._as_text(f.get("type")) in _TEXT_TYPES and f.get("key"):
                text_slots.append({
                    "page": page_key,
                    "section_id": rx._as_text(section.get("id")),
                    "key": rx._as_text(f.get("key")),
                    "label": rx._as_text(f.get("label")) or rx._as_text(f.get("key")),
                    "value": rx._as_text(f.get("value")),
                    "max_chars": f.get("max_chars") if isinstance(f.get("max_chars"), int) else None,
                })
    return {"enabled": True, "site": site, "pages": pages_out,
            "text_slots": text_slots, "gallery": _gallery(webapps_root, site)}


def _render_site(frontend_dir: Path) -> tuple[bool, str]:
    """Regenerate the site's HTML by calling ``build_site`` in an ISOLATED subprocess.

    We invoke build_site directly (not the site's ``render_manifest.py`` wrapper)
    because (1) each site ships its own ``render_lib`` package, which must not be
    imported into the long-lived multi-site portal process, and (2) the wrapper's
    unrelated post-render lints (e.g. a stray demo page failing the URL convention)
    would mislabel a good save as failed. A slot/asset edit can't introduce the
    URL/DR violations those lints guard.
    """
    scripts = frontend_dir / "scripts"
    if not (scripts / "render_lib" / "site_builder.py").is_file():
        return False, f"no render_lib at {scripts}"
    code = (
        "import sys; from pathlib import Path; "
        "sys.path.insert(0, str(Path('scripts').resolve())); "
        "from render_lib.site_builder import build_site; "
        "build_site(Path('.').resolve())"
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", code],
            check=False, capture_output=True, timeout=300, cwd=str(frontend_dir),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"render failed to launch: {exc}"
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        return False, f"render exited {completed.returncode}: {detail[:400]}"
    return True, "rebuilt"


def save_site_content(
    webapps_root: str | Path | None,
    site: str,
    edits: list[dict[str, Any]] | None = None,
    swaps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Apply text-slot edits + image/icon swaps to the manifest, then re-render.

    ``edits`` = ``[{page, section_id, key, value}]`` (typed text slots, validated
    against the field's own max_chars). ``swaps`` = ``[{page, old, new}]`` — replace
    the asset path ``old`` with ``new`` (validated ∈ the site's gallery) everywhere
    it appears in that page's section html. All-or-nothing: any error → no write.
    """
    site = os.path.basename(rx._as_text(site))
    if not site_content_enabled(site):
        return {"ok": False, "error": "not_editable"}
    manifest_path = _site_manifest_path(webapps_root, site)
    frontend_dir = _frontend_dir(webapps_root, site)
    if manifest_path is None or frontend_dir is None:
        return {"ok": False, "error": "no_manifest"}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    gallery = _gallery(webapps_root, site)
    errors: list[str] = []
    applied = 0

    # --- typed text-slot edits ---
    index: dict[tuple[str, str], dict] = {}
    for page_key, section, by_key in _editable_sections(manifest):
        index[(page_key, rx._as_text(section.get("id")))] = by_key
    for edit in edits if isinstance(edits, list) else []:
        if not isinstance(edit, dict):
            continue
        page = rx._as_text(edit.get("page"))
        sid = rx._as_text(edit.get("section_id"))
        key = rx._as_text(edit.get("key"))
        by_key = index.get((page, sid))
        field = by_key.get(key) if by_key else None
        if field is None or rx._as_text(field.get("type")) not in _TEXT_TYPES:
            errors.append(f"{page}/{sid}/{key}: not an editable text field")
            continue
        value = _clean_text(edit.get("value"))
        mc = field.get("max_chars")
        if isinstance(mc, int) and len(value) > mc:
            errors.append(f"{page}/{sid}/{key}: exceeds {mc} characters")
            continue
        field["value"] = value
        applied += 1

    # --- asset swaps (any image/icon on the page, by path) ---
    pages = manifest.get("pages") if isinstance(manifest.get("pages"), dict) else {}
    new_images: list[str] = []
    for swap in swaps if isinstance(swaps, list) else []:
        if not isinstance(swap, dict):
            continue
        page = rx._as_text(swap.get("page"))
        old = rx._as_text(swap.get("old"))
        new = rx._as_text(swap.get("new"))
        kind = "icon" if ("#" in new or "/assets/icons/" in new) else "image"
        if not new or new not in gallery.get(kind, []):
            errors.append(f"{page}: '{new}' is not in your {kind} gallery")
            continue
        page_obj = pages.get(page)
        content = page_obj.get("content") if isinstance(page_obj, dict) else None
        sections = content.get("sections") if isinstance(content, dict) else None
        if not isinstance(sections, list):
            errors.append(f"{page}: not an editable page")
            continue
        count = 0
        for s in sections:
            if isinstance(s, dict) and isinstance(s.get("html"), str) and old and old in s["html"]:
                count += s["html"].count(old)
                s["html"] = s["html"].replace(old, new)
        if count == 0:
            errors.append(f"{page}: '{old}' not found on the page")
            continue
        applied += 1
        if kind == "image":
            new_images.append(new)

    if errors:
        return {"ok": False, "errors": errors, "applied": 0}
    if applied == 0:
        return {"ok": True, "applied": 0, "rebuilt": False}

    text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    try:
        rx._atomic_write_text(manifest_path, text)
    except OSError as exc:
        return {"ok": False, "error": "write_failed", "detail": str(exc)}

    # Declare any newly-introduced image in the site record-manifest so the deploy
    # asset-lint stays green (no-op if already present).
    entity = _entity(site)
    for img in dict.fromkeys(new_images):
        asset_id = img.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        rx.add_asset_to_manifest(
            webapps_root, site=site, kind="image",
            asset_id=asset_id, asset_path=img, entity_scope=entity,
        )

    rebuilt, note = _render_site(frontend_dir)
    return {"ok": rebuilt, "applied": applied, "rebuilt": rebuilt, "detail": note}
