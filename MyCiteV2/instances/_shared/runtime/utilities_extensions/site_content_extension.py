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
        out.sort(key=lambda e: e["path"] != "/")  # float the home page to pages[0]
        return out
    # static: every page-level .html minus tooling/asset dirs
    out = []
    for p in sorted(fd.rglob("*.html")):
        rel = p.relative_to(fd).as_posix()
        if rel in _STATIC_SKIP or rel.split("/")[0] in _STATIC_SKIP_DIRS:
            continue
        out.append({"page": rel, "path": _page_path_from_file(rel),
                    "label": rel[:-5].replace("/", " · ").replace("-", " ").title()})
    out.sort(key=lambda e: e["path"] != "/")  # float the home page to pages[0]
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


def _deep_count_equal(obj: Any, needle: str) -> int:
    if isinstance(obj, str):
        return 1 if obj == needle else 0
    if isinstance(obj, dict):
        return sum(_deep_count_equal(v, needle) for v in obj.values())
    if isinstance(obj, list):
        return sum(_deep_count_equal(v, needle) for v in obj)
    return 0


def _deep_replace_equal(obj: Any, old: str, new: str) -> Any:
    if isinstance(obj, str):
        return new if obj == old else obj
    if isinstance(obj, dict):
        return {k: _deep_replace_equal(v, old, new) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_replace_equal(v, old, new) for v in obj]
    return obj


def _dedupe(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    out, seen = [], set()
    for m, r in pairs:
        if m and m not in seen:
            seen.add(m)
            out.append((m, r))
    return out


# Rendered text arrives as unicode (em-dash, curly quotes, ellipsis) but the SOURCE stores
# entities (&mdash;, &rsquo;, &hellip;), so a raw / html.escape match misses them. Map
# the common typographic chars back to the entities authors use.
_NAMED_ENTITIES: dict[str, str] = {
    "\u2014": "&mdash;", "\u2013": "&ndash;", "\u2026": "&hellip;",
    "\u2019": "&rsquo;", "\u2018": "&lsquo;", "\u201d": "&rdquo;", "\u201c": "&ldquo;",
    "\u203a": "&rsaquo;", "\u2039": "&lsaquo;", "\u00ab": "&laquo;", "\u00bb": "&raquo;",
    "\u00a0": "&nbsp;", "\u2022": "&bull;", "\u00a9": "&copy;", "\u00ae": "&reg;",
    "\u2122": "&trade;",
}


def _entify(s: str) -> str:
    """Encode rendered text toward the page SOURCE's HTML form: escape ``<>&`` then map
    the common typographic characters to the NAMED entities authors use (``&mdash;``,
    ``&rsquo;``, ...), so an edit captured from rendered ``textContent`` matches an
    entity-encoded source string."""
    out = _html.escape(s, quote=False)
    for ch, ent in _NAMED_ENTITIES.items():
        if ch in out:
            out = out.replace(ch, ent)
    return out


def _deep_apply_unescaped(obj: Any, old: str, new: str) -> tuple[Any, int]:
    """Entity-TOLERANT placement (handles any entity the ``_entify`` map misses, incl.
    numeric): replace a whole string value, OR a ``>...<`` text segment, whose
    HTML-UNESCAPED form equals ``old`` (storing ``new`` with only ``<>&`` escaped).
    Returns ``(obj, count)``."""
    count = 0
    seg = re.compile(r">([^<>]*)<")

    def walk(o: Any) -> Any:
        nonlocal count
        if isinstance(o, str):
            if _html.unescape(o) == old:
                count += 1
                return _html.escape(new, quote=False)

            def repl(mo: re.Match[str]) -> str:
                nonlocal count
                if _html.unescape(mo.group(1)) == old:
                    count += 1
                    return ">" + _html.escape(new, quote=False) + "<"
                return mo.group(0)

            return seg.sub(repl, o)
        if isinstance(o, dict):
            return {k: walk(v) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v) for v in o]
        return o

    return walk(obj), count


def _apply_text_edit(container: Any, old: str, new: str) -> tuple[Any, bool]:
    """Place a text edit precisely, trying in order: (1) an exact field VALUE
    (typed fields — replace every equal value, so visible + meta stay consistent);
    (2) the element-content form ``>old<`` (targets the rendered element, not
    attributes/title/JSON-LD, and is word-boundary safe); (3) a unique plain
    substring — each tried in raw, ``html.escape``, AND named-entity (``_entify``)
    forms so a rendered-textContent edit matches an entity-encoded source; finally
    (4) an entity-TOLERANT (``html.unescape``-normalized) value/segment match for any
    remaining entity. Returns (container, applied)."""
    esc = lambda s: _html.escape(s, quote=False)  # noqa: E731
    for m, r in _dedupe([(old, new), (esc(old), esc(new)), (_entify(old), _entify(new))]):
        if _deep_count_equal(container, m) > 0:
            return _deep_replace_equal(container, m, r), True
    for m, r in _dedupe([
        (f">{old}<", f">{new}<"), (f">{esc(old)}<", f">{esc(new)}<"),
        (f">{_entify(old)}<", f">{_entify(new)}<"),
    ]):
        if _deep_count(container, m) > 0:
            return _deep_replace(container, m, r), True
    for m, r in _dedupe([(old, new), (esc(old), esc(new)), (_entify(old), _entify(new))]):
        if _deep_count(container, m) == 1:
            return _deep_replace(container, m, r), True
    obj, applied = _deep_apply_unescaped(container, old, new)
    if applied > 0:
        return obj, True
    return container, False


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
        # Keep this BELOW gunicorn's worker --timeout (180s): a runaway render
        # must fail here as a clean error, not let gunicorn SIGKILL the single
        # worker mid-write (which would 502 every grantee + risk a partial site).
        done = subprocess.run([sys.executable, "-c", code], check=False,
                              capture_output=True, timeout=150, cwd=str(frontend_dir))
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


def _restore_files(snapshot: dict[str, bytes | None]) -> None:
    """Best-effort rollback after a failed multi-file save: rewrite each file to
    its pre-save bytes, or remove one that didn't exist before. Writing into an
    existing file preserves its mode."""
    for p, data in snapshot.items():
        try:
            if data is None:
                Path(p).unlink(missing_ok=True)
            else:
                Path(p).write_bytes(data)
        except OSError:
            pass


def save_site_content(
    webapps_root: str | Path | None,
    site: str,
    page: str,
    edits: list[dict[str, Any]] | None = None,
    swaps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Apply text edits + image/icon swaps to a page, then (manifest sites) re-render.

    ``edits`` = ``[{old, new}]`` text; ``swaps`` = ``[{old, new, kind}]`` assets.
    Both are value-replacements against the page SOURCE (a ``container`` — the
    manifest + data/*.json for manifest sites, or the .html string for static
    sites). All-or-nothing: any error → nothing is written.
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

    # Build a single replaceable container for either site kind. For manifest
    # sites scope it to {shared top-level keys} + {ONLY the edited page} so an
    # edit/swap can't bleed into OTHER pages, while still reaching shared
    # nav/footer and keeping a page's visible + meta fields in sync.
    mp = html_path = None
    orig_manifest: dict[str, Any] = {}
    scoped_page: str | None = None
    orig_data: dict[str, Any] = {}
    if kind == "manifest":
        mp = _site_manifest_path(webapps_root, site)
        if mp is None:
            return {"ok": False, "error": "no_manifest"}
        try:
            orig_manifest = json.loads(mp.read_text(encoding="utf-8"))
            orig_data = {str(p): json.loads(p.read_text(encoding="utf-8"))
                         for p in (fd / "data").glob("*.json")} if (fd / "data").is_dir() else {}
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": "unreadable_source", "detail": str(exc)}
        man_view = json.loads(json.dumps(orig_manifest))   # deep copy to edit
        pages = man_view.get("pages")
        if isinstance(pages, dict) and page in pages:
            scoped_page = page
            man_view["pages"] = {page: pages[page]}
        container: Any = {"manifest": man_view,
                          "data": {k: json.loads(json.dumps(v)) for k, v in orig_data.items()}}
    else:
        rel = rx._as_text(page).lstrip("/") or "index.html"
        html_path = (fd / rel).resolve()
        if fd.resolve() not in html_path.parents or not html_path.is_file():
            return {"ok": False, "error": "no_page"}
        try:
            container = {"html": html_path.read_text(encoding="utf-8")}
        except OSError as exc:
            return {"ok": False, "error": "unreadable_source", "detail": str(exc)}

    applied = 0
    for sw in swaps:
        old, new = rx._as_text(sw.get("old")), rx._as_text(sw.get("new"))
        gk = rx._as_text(sw.get("kind")) or _swap_kind(new)
        if not new or new not in gallery.get(gk, []):
            errors.append(f"'{new}' is not in your {gk} gallery")
            continue
        if _deep_count(container, old) == 0:
            errors.append("image not found on the page")
            continue
        container = _deep_replace(container, old, new)
        if gk == "image":
            new_images.append(new)
        applied += 1
    for ed in edits:
        old = _CONTROL_RE.sub("", rx._as_text(ed.get("old")))
        new = _CONTROL_RE.sub("", rx._as_text(ed.get("new")))
        if not old or not new.strip() or len(new) > _MAX_TEXT:
            # Reject empty/whitespace-only `new`: an inline edit must not blank a
            # heading/section to "" (silent content loss on the live page).
            errors.append("invalid text edit")
            continue
        container, done = _apply_text_edit(container, old, new)
        if done:
            applied += 1
        else:
            errors.append(f"couldn't place text edit safely: {old[:40]!r}")

    if errors:
        return {"ok": False, "errors": errors, "applied": 0}
    if applied == 0:
        return {"ok": True, "applied": 0, "rebuilt": False}

    if kind == "manifest":
        # Merge the scoped edited view back into the full manifest: only the
        # edited page + shared top-level keys change; other pages are untouched.
        edited = container["manifest"]
        if scoped_page is not None:
            result_manifest = orig_manifest
            for k, v in edited.items():
                if k == "pages":
                    result_manifest["pages"][scoped_page] = v[scoped_page]
                else:
                    result_manifest[k] = v
        else:
            result_manifest = edited
        targets: dict[str, str] = {
            str(mp): json.dumps(result_manifest, indent=2, ensure_ascii=False) + "\n"}
        for k, d in container["data"].items():
            if d != orig_data.get(k):
                targets[k] = json.dumps(d, indent=2, ensure_ascii=False) + "\n"
        # Snapshot originals so a failed write OR render rolls back cleanly — no
        # manifest<->HTML divergence left on the live site.
        snapshot = {p: (Path(p).read_bytes() if Path(p).exists() else None) for p in targets}
        try:
            for p, text in targets.items():
                rx._atomic_write_text(Path(p), text)
        except OSError as exc:
            _restore_files(snapshot)
            return {"ok": False, "applied": 0, "rebuilt": False,
                    "error": "write_failed", "detail": str(exc)}
        ok, note = _render_site(fd)
        if not ok:
            _restore_files(snapshot)
            return {"ok": False, "applied": 0, "rebuilt": False,
                    "error": "render_failed", "detail": note}
        _allocate_images(webapps_root, site, new_images)
        return {"ok": True, "applied": applied, "rebuilt": True, "detail": note}

    try:
        rx._atomic_write_text(html_path, container["html"])
    except OSError as exc:
        return {"ok": False, "applied": 0, "rebuilt": False,
                "error": "write_failed", "detail": str(exc)}
    _allocate_images(webapps_root, site, new_images)
    return {"ok": True, "applied": applied, "rebuilt": False}


def _allocate_images(webapps_root: str | Path | None, site: str, paths: list[str]) -> None:
    """Declare newly-used images in the site record-manifest (deploy-lint safe)."""
    entity = _entity(site)
    for img in dict.fromkeys(paths):
        asset_id = img.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        rx.add_asset_to_manifest(webapps_root, site=site, kind="image",
                                 asset_id=asset_id, asset_path=img, entity_scope=entity)
