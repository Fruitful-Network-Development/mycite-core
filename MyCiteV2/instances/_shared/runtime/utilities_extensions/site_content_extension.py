"""Grantee site editor — one unified mechanism across every site type.

The dashboard "Design" tab renders the grantee's real page in an iframe and lets
them **swap any image/icon** (from a gallery of their own assets + shared icons)
and **edit any simple text** in place. Every edit is a ``{old, new}`` value pair;
the backend replaces ``old → new`` in the page's SOURCE, picked per site kind:

* **manifest** sites (FND, CVCC) — deep-walk the site manifest JSON, replace the
  matching string value(s), then ``build_site`` re-renders. Catches FND's raw-HTML
  sections AND CVCC's typed fields uniformly.
* **static** sites (TFF, BPW) — replace directly in the page's ``.html`` file; no
  rebuild (nginx serves the tree).

There are no slots/markers: text and images are discovered in the iframe. Text edits
are guarded (exactly-one-occurrence, encoding-tolerant) so an ambiguous edit is
rejected, never mis-applied. Reuses ``resources_extension`` for atomic writes +
record-manifest allocation.
"""

from __future__ import annotations

import html as _html
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import resources_extension as rx

EDITABLE_SITES: frozenset[str] = frozenset({
    "fruitfulnetworkdevelopment.com",
    "cuyahogavalleycountrysideconservancy.org",
    "trappfamilyfarm.com",
    "brockspressurewashing.com",
})

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SYMBOL_RE = re.compile(r'<symbol[^>]*\bid="([A-Za-z0-9_-]+)"')
_MAX_TEXT = 2000
_STATIC_SKIP = ("dashboard.html",)
_STATIC_SKIP_DIRS = ("css", "scripts", "data", "assets")


def site_content_enabled(site: str) -> bool:
    return os.path.basename(rx._as_text(site)) in EDITABLE_SITES


def _frontend_dir(webapps_root: str | Path | None, site: str) -> Path | None:
    if not webapps_root:
        return None
    d = Path(webapps_root) / "clients" / os.path.basename(rx._as_text(site)) / "frontend"
    return d if d.is_dir() else None


def _entity(site: str) -> str:
    from MyCiteV2.packages.adapters.filesystem import entity_for_domain
    return rx._as_text(entity_for_domain(os.path.basename(rx._as_text(site))))


def _site_manifest_path(webapps_root: str | Path | None, site: str) -> Path | None:
    fd = _frontend_dir(webapps_root, site)
    if fd is None:
        return None
    for p in sorted((fd / "assets").glob("*.json")):
        n = p.name.lower()
        if "manifest" in n and "site" in n:
            return p
    return None


def _site_kind(webapps_root: str | Path | None, site: str) -> str:
    fd = _frontend_dir(webapps_root, site)
    if fd is None:
        return "static"
    if (fd / "scripts" / "render_lib" / "site_builder.py").is_file() and _site_manifest_path(webapps_root, site):
        return "manifest"
    return "static"


def _page_path_from_file(rel: str) -> str:
    rel = rel.replace("\\", "/")
    if rel in ("index.html", "/index.html"):
        return "/"
    stem = rel[:-5] if rel.endswith(".html") else rel
    return "/" + stem.lstrip("/")


def _pages(webapps_root: str | Path | None, site: str, kind: str) -> list[dict[str, Any]]:
    fd = _frontend_dir(webapps_root, site)
    if fd is None:
        return []
    if kind == "manifest":
        mp = _site_manifest_path(webapps_root, site)
        manifest = json.loads(mp.read_text(encoding="utf-8")) if mp else {}
        out = []
        for pk, page in (manifest.get("pages") or {}).items():
            if isinstance(page, dict) and page.get("file"):
                out.append({"page": pk, "path": _page_path_from_file(rx._as_text(page.get("file"))),
                            "label": rx._as_text(page.get("title")) or pk})
        return out
    # static: every page-level .html minus tooling/asset dirs
    out = []
    for p in sorted(fd.rglob("*.html")):
        rel = p.relative_to(fd).as_posix()
        if rel in _STATIC_SKIP or rel.split("/")[0] in _STATIC_SKIP_DIRS:
            continue
        out.append({"page": rel, "path": _page_path_from_file(rel),
                    "label": rel[:-5].replace("/", " · ").replace("-", " ").title()})
    return out


def _owner_files(webapps_root: str | Path | None, site: str, subdir: str, *, exclude_sprite=False) -> list[str]:
    core = rx._site_core_root(webapps_root)
    entity = _entity(site)
    if core is None or not entity:
        return []
    token = "." + entity
    url = "/assets/icons/" if subdir == "icon" else "/assets/" + subdir + "s/"
    out = []
    for p in sorted((core / subdir).glob("*")):
        if not p.is_file() or p.name.startswith(".") or ".example." in p.name:
            continue
        if exclude_sprite and "sprite" in p.name:
            continue
        if token in p.name:
            out.append(url + p.name)
    return out


def _icon_sprites(webapps_root: str | Path | None) -> list[str]:
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
    return {
        "image": _owner_files(webapps_root, site, "image"),
        "icon_file": _owner_files(webapps_root, site, "icon", exclude_sprite=True),
        "icon_sprite": _icon_sprites(webapps_root),
    }


def read_site_content(webapps_root: str | Path | None, site: str) -> dict[str, Any]:
    site = os.path.basename(rx._as_text(site))
    blank = {"enabled": False, "site": site, "kind": "", "pages": [],
             "gallery": {"image": [], "icon_file": [], "icon_sprite": []}}
    if not site_content_enabled(site):
        return blank
    kind = _site_kind(webapps_root, site)
    pages = _pages(webapps_root, site, kind)
    if not pages:
        return blank
    return {"enabled": True, "site": site, "kind": kind, "pages": pages,
            "gallery": _gallery(webapps_root, site)}


# --------------------------------------------------------------------------- #
# value-replace primitives
# --------------------------------------------------------------------------- #
def _deep_count(obj: Any, needle: str) -> int:
    if isinstance(obj, str):
        return obj.count(needle)
    if isinstance(obj, dict):
        return sum(_deep_count(v, needle) for v in obj.values())
    if isinstance(obj, list):
        return sum(_deep_count(v, needle) for v in obj)
    return 0


def _deep_replace(obj: Any, old: str, new: str) -> Any:
    if isinstance(obj, str):
        return obj.replace(old, new)
    if isinstance(obj, dict):
        return {k: _deep_replace(v, old, new) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_replace(v, old, new) for v in obj]
    return obj


def _text_pairs(old: str, new: str) -> list[tuple[str, str]]:
    """(match, replacement) candidates: the raw value and its HTML-escaped form, so
    a text edit lands whether the source stores decoded (typed fields) or escaped
    (html blobs / static .html) copy."""
    pairs = [(old, new)]
    esc_old = _html.escape(old, quote=False)
    if esc_old != old:
        pairs.append((esc_old, _html.escape(new, quote=False)))
    return pairs


def _render_site(frontend_dir: Path) -> tuple[bool, str]:
    """Regenerate a manifest site's HTML via build_site in an ISOLATED subprocess
    (each site ships its own render_lib; don't import it into the portal process)."""
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
        done = subprocess.run([sys.executable, "-c", code], check=False,
                              capture_output=True, timeout=300, cwd=str(frontend_dir))
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"render failed to launch: {exc}"
    if done.returncode != 0:
        return False, f"render exited {done.returncode}: {done.stderr.decode('utf-8','replace').strip()[:400]}"
    return True, "rebuilt"


def _swap_kind(new: str) -> str:
    if "#" in new:
        return "icon_sprite"
    if "/assets/icons/" in new:
        return "icon_file"
    return "image"


def save_site_content(
    webapps_root: str | Path | None,
    site: str,
    page: str,
    edits: list[dict[str, Any]] | None = None,
    swaps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Apply text edits + image/icon swaps to a page, then (manifest sites) re-render.

    ``edits`` = ``[{old, new}]`` text; ``swaps`` = ``[{old, new, kind}]`` assets.
    All-or-nothing: any error → nothing is written.
    """
    site = os.path.basename(rx._as_text(site))
    if not site_content_enabled(site):
        return {"ok": False, "error": "not_editable"}
    fd = _frontend_dir(webapps_root, site)
    if fd is None:
        return {"ok": False, "error": "no_site"}
    kind = _site_kind(webapps_root, site)
    gallery = _gallery(webapps_root, site)
    edits = edits if isinstance(edits, list) else []
    swaps = swaps if isinstance(swaps, list) else []
    errors: list[str] = []
    new_images: list[str] = []

    if kind == "manifest":
        mp = _site_manifest_path(webapps_root, site)
        if mp is None:
            return {"ok": False, "error": "no_manifest"}
        manifest = json.loads(mp.read_text(encoding="utf-8"))
        data_files = {p: json.loads(p.read_text(encoding="utf-8")) for p in (fd / "data").glob("*.json")} \
            if (fd / "data").is_dir() else {}

        def count(needle):
            return _deep_count(manifest, needle) + sum(_deep_count(d, needle) for d in data_files.values())

        applied = 0
        for sw in swaps:
            old, new = rx._as_text(sw.get("old")), rx._as_text(sw.get("new"))
            gk = rx._as_text(sw.get("kind")) or _swap_kind(new)
            if not new or new not in gallery.get(gk, []):
                errors.append(f"'{new}' is not in your {gk} gallery")
                continue
            if count(old) == 0:
                errors.append("image not found on the page")
                continue
            manifest = _deep_replace(manifest, old, new)
            data_files = {p: _deep_replace(d, old, new) for p, d in data_files.items()}
            if gk == "image":
                new_images.append(new)
            applied += 1
        for ed in edits:
            old, new = _CONTROL_RE.sub("", rx._as_text(ed.get("old"))), _CONTROL_RE.sub("", rx._as_text(ed.get("new")))
            if not old or len(new) > _MAX_TEXT:
                errors.append("invalid text edit")
                continue
            done = False
            for m, r in _text_pairs(old, new):
                if count(m) == 1:
                    manifest = _deep_replace(manifest, m, r)
                    data_files = {p: _deep_replace(d, m, r) for p, d in data_files.items()}
                    done = True
                    applied += 1
                    break
            if not done:
                errors.append(f"couldn't place text edit safely: {old[:40]!r}")
        if errors:
            return {"ok": False, "errors": errors, "applied": 0}
        if applied == 0:
            return {"ok": True, "applied": 0, "rebuilt": False}
        rx._atomic_write_text(mp, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        for p, d in data_files.items():
            rx._atomic_write_text(p, json.dumps(d, indent=2, ensure_ascii=False) + "\n")
        _allocate_images(webapps_root, site, new_images)
        ok, note = _render_site(fd)
        return {"ok": ok, "applied": applied, "rebuilt": ok, "detail": note}

    # ---- static site: edit the page's .html directly ----
    rel = os.path.basename(rx._as_text(page)) if "/" not in rx._as_text(page) else rx._as_text(page)
    rel = rel.lstrip("/")
    html_path = (fd / rel).resolve()
    if fd.resolve() not in html_path.parents or not html_path.is_file():
        return {"ok": False, "error": "no_page"}
    text = html_path.read_text(encoding="utf-8")
    applied = 0
    for sw in swaps:
        old, new = rx._as_text(sw.get("old")), rx._as_text(sw.get("new"))
        gk = rx._as_text(sw.get("kind")) or _swap_kind(new)
        if not new or new not in gallery.get(gk, []):
            errors.append(f"'{new}' is not in your {gk} gallery")
            continue
        if old not in text:
            errors.append("image not found on the page")
            continue
        text = text.replace(old, new)
        if gk == "image":
            new_images.append(new)
        applied += 1
    for ed in edits:
        old, new = _CONTROL_RE.sub("", rx._as_text(ed.get("old"))), _CONTROL_RE.sub("", rx._as_text(ed.get("new")))
        if not old or len(new) > _MAX_TEXT:
            errors.append("invalid text edit")
            continue
        done = False
        for m, r in _text_pairs(old, new):
            if text.count(m) == 1:
                text = text.replace(m, r)
                done = True
                applied += 1
                break
        if not done:
            errors.append(f"couldn't place text edit safely: {old[:40]!r}")
    if errors:
        return {"ok": False, "errors": errors, "applied": 0}
    if applied == 0:
        return {"ok": True, "applied": 0, "rebuilt": False}
    rx._atomic_write_text(html_path, text)
    _allocate_images(webapps_root, site, new_images)
    return {"ok": True, "applied": applied, "rebuilt": False}


def _allocate_images(webapps_root: str | Path | None, site: str, paths: list[str]) -> None:
    """Declare newly-used images in the site record-manifest (deploy-lint safe)."""
    entity = _entity(site)
    for img in dict.fromkeys(paths):
        asset_id = img.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        rx.add_asset_to_manifest(webapps_root, site=site, kind="image",
                                 asset_id=asset_id, asset_path=img, entity_scope=entity)
