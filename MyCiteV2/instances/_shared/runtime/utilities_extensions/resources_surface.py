"""Resources gallery listing — the read-only gallery half of ext_resources.

Produces a read-only payload listing one subtab per site-core gallery, each
listing the gallery's entries (filename + basic metadata) and a count, read
from

    <webapps_root>/clients/_shared/site-core/<gallery>/

Wave 2 re-homed this under the ``ext_resources`` Utilities extension (the
Wave-1 ``resources.root`` top-level surface was retired); the rich
per-gallery UX (contact-app, icon dedup, editing, upload) is layered on top
by ``resources_extension.py``. This builder stays strictly read-only: it
never writes, mutates, or deletes, and for the PII galleries (events,
contacts) it lists filenames and counts ONLY — it does not read or expose
file CONTENTS.

Galleries may not exist yet on disk (events / contacts are forthcoming);
a missing directory yields an empty subtab rather than an error.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Schema for the resources gallery listing payload. Formerly derived from the
# retired ``resources.root`` surface; now a stable standalone identifier so the
# builder no longer depends on a top-level surface registration.
RESOURCES_GALLERY_SCHEMA = "mycite.v2.portal.resources.gallery.v1"

# Path of the shared site-core gallery root relative to webapps_root.
SITE_CORE_RELATIVE_PATH = ("clients", "_shared", "site-core")

# Galleries surfaced as subtabs, in display order. ``pii`` galleries list
# filenames + counts only — their file CONTENTS are never read in this
# scaffold.
RESOURCE_GALLERIES: tuple[dict[str, Any], ...] = (
    {"gallery": "profiles", "label": "Profiles", "pii": False},
    {"gallery": "icon", "label": "Icons", "pii": False},
    {"gallery": "image", "label": "Images", "pii": False},
    {"gallery": "document", "label": "Documents", "pii": False},
    {"gallery": "audio", "label": "Audio", "pii": False},
    {"gallery": "events", "label": "Events", "pii": True},
    {"gallery": "contacts", "label": "Contacts", "pii": True},
)


def _gallery_entries(gallery_dir: Path) -> list[dict[str, Any]]:
    """List the immediate files in ``gallery_dir`` with basic metadata.

    Returns an empty list when the directory is absent or unreadable.
    Only regular files at the top level are listed (no recursion, no
    directory entries). Basic metadata = byte size + extension; file
    CONTENTS are never read.
    """
    entries: list[dict[str, Any]] = []
    try:
        children = sorted(gallery_dir.iterdir(), key=lambda path: path.name.lower())
    except (FileNotFoundError, NotADirectoryError, PermissionError, OSError):
        return entries
    for child in children:
        try:
            if not child.is_file():
                continue
            # Skip dotfiles (e.g. .gitkeep placeholders) and the tracked
            # *.example.* schema templates — they are scaffolding, not real
            # resources, and shouldn't show or be counted in the gallery.
            if child.name.startswith(".") or ".example." in child.name:
                continue
            size_bytes = child.stat().st_size
        except OSError:
            continue
        entries.append(
            {
                "filename": child.name,
                "extension": child.suffix.lstrip(".").lower(),
                "size_bytes": int(size_bytes),
            }
        )
    return entries


def _subtab_for_gallery(
    *,
    gallery: str,
    label: str,
    pii: bool,
    site_core_root: Path,
) -> dict[str, Any]:
    gallery_dir = site_core_root / gallery
    exists = gallery_dir.is_dir()
    entries = _gallery_entries(gallery_dir) if exists else []
    return {
        "gallery": gallery,
        "label": label,
        "pii": pii,
        "exists": exists,
        "count": len(entries),
        "entries": entries,
    }


def build_resources_surface_payload(webapps_root: str | Path | None) -> dict[str, Any]:
    """Build the read-only Resources surface payload.

    One subtab per site-core gallery. Tolerant of a missing webapps_root
    or missing gallery directories — those simply yield empty subtabs.
    """
    site_core_root: Path | None = None
    if webapps_root:
        site_core_root = Path(webapps_root).joinpath(*SITE_CORE_RELATIVE_PATH)

    subtabs: list[dict[str, Any]] = []
    for spec in RESOURCE_GALLERIES:
        gallery = str(spec["gallery"])
        label = str(spec["label"])
        pii = bool(spec["pii"])
        if site_core_root is None:
            subtabs.append(
                {
                    "gallery": gallery,
                    "label": label,
                    "pii": pii,
                    "exists": False,
                    "count": 0,
                    "entries": [],
                }
            )
            continue
        subtabs.append(
            _subtab_for_gallery(
                gallery=gallery,
                label=label,
                pii=pii,
                site_core_root=site_core_root,
            )
        )

    return {
        "schema": RESOURCES_GALLERY_SCHEMA,
        "kind": "resources",
        "title": "Resources",
        "subtitle": (
            "Read-only listing of the shared site-core galleries. "
            "Rich per-gallery management arrives in Wave 2."
        ),
        "site_core_root": str(site_core_root) if site_core_root is not None else "",
        "subtabs": subtabs,
    }
