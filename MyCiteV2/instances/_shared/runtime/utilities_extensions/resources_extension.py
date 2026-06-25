"""ext_resources — the shared site-core asset library, as a Utilities extension.

Wave 2 RETIRES the Wave-1 ``resources.root`` top-level surface and re-homes
resources where every comparable operator feature lives: under
**Utilities → Extensions**, beside ext_aws_email / ext_paypal / etc.

This module owns:

  * ``_render_ext_resources(ctx)`` — the EXTENSION_RENDERERS entry. Builds the
    payload the resources extension card renders from (gallery galleries +
    the profiles "contact app" list + per-profile detail/edit form).
  * pure backend helpers used by the POST/GET routes in ``portal_host/app.py``:
      - ``list_profiles`` / ``profile_detail`` / ``resolve_profile_image``
      - ``save_profile`` (atomic canonical write)
      - ``derive_profile_excerpt`` (refill a per-site excerpt from canonical)
      - ``propagate_profile`` (derive every excerpt + rebuild the owning site)
      - ``icon_duplicate_groups`` / ``remove_icon_duplicate`` (sha256 dedup)
      - ``add_asset_to_manifest`` (append an entry to a site record-manifest)

Profiles are the operator's core need: a phone-contacts-style list (logo
thumbnail + name) whose rows open a full detail view (every field, including
EMPTY ones) and an edit form that writes the canonical
``clients/_shared/site-core/profiles/<file>.profile.yaml`` AND re-derives the
per-site excerpt + rebuilds the owning site so the edit reaches the live page.
"""

from __future__ import annotations

import glob
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from ._shared import _as_text

# Path of the shared site-core gallery root relative to webapps_root.
_SITE_CORE_REL = ("clients", "_shared", "site-core")

# Profile filename suffix; the slug is the token between the archetype and
# ``.profile.yaml`` (e.g. ``nathan_seals`` in
# ``0000-00-00.artifact-profile-natural_entity.nathan_seals.profile.yaml``).
_PROFILE_SUFFIX = ".profile.yaml"

# Tokens a per-entity image filename carries when it is the entity's logo /
# headshot (used when a profile has no explicit image_ref/logo_ref).
_IMAGE_ROLE_TOKENS = ("logo", "primary_mark", "headshot", "profile_headshot", "brand-mark")

# Image gallery URL prefix served by nginx (snippets/shared-assets.conf, also
# included by the portal vhost) → /assets/images/<file>.avif.
_IMAGE_URL_PREFIX = "/assets/images/"


# --------------------------------------------------------------------------- #
# path helpers
# --------------------------------------------------------------------------- #
def _site_core_root(webapps_root: str | Path | None) -> Path | None:
    if not webapps_root:
        return None
    return Path(webapps_root).joinpath(*_SITE_CORE_REL)


def _profiles_dir(webapps_root: str | Path | None) -> Path | None:
    root = _site_core_root(webapps_root)
    return root / "profiles" if root is not None else None


def _profile_slug(filename: str) -> str:
    """Return the entity slug from a profile filename.

    ``0000-00-00.artifact-profile-legal_entity.bloom_hill_farm.profile.yaml``
    → ``bloom_hill_farm``. Falls back to the basename sans suffix.
    """
    name = str(filename)
    if name.endswith(_PROFILE_SUFFIX):
        name = name[: -len(_PROFILE_SUFFIX)]
    # The slug is the last dot-separated token of the remaining stem.
    return name.rsplit(".", 1)[-1]


def _profile_entity_flavor(filename: str) -> str:
    """Return the entity flavor of a profile filename, or "".

    ``0000-00-00.artifact-profile-legal_entity.bloom_hill_farm.profile.yaml``
    → ``legal_entity`` (the token between ``artifact-profile-`` and the slug).
    """
    name = str(filename)
    if name.endswith(_PROFILE_SUFFIX):
        name = name[: -len(_PROFILE_SUFFIX)]
    head = name.rsplit(".", 1)[0]  # drop the trailing .<slug>
    marker = "artifact-profile-"
    idx = head.find(marker)
    return head[idx + len(marker):] if idx != -1 else ""


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_yaml_mapping_required(path: Path) -> dict[str, Any]:
    """Like ``_load_yaml_mapping`` but distinguishes an UNPARSEABLE existing file
    (raises ``ValueError``) from a genuinely absent one (``{}``). Callers that
    LOAD -> mutate -> overwrite the same file must use this, so a momentarily
    corrupt manifest is never silently replaced by a near-empty one that drops
    every previously-recorded entry."""
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"unparseable manifest {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"manifest {path} is not a mapping")
    return data


def _atomic_write_text(path: Path, text: str) -> None:
    """Served-perms atomic write (preserve dest mode, else 0644 so nginx can
    still read the page/manifest). Thin shim over the shared
    :func:`atomic_io.atomic_write_text`."""
    from MyCiteV2.packages.adapters.filesystem.atomic_io import atomic_write_text

    atomic_write_text(path, text)


# --------------------------------------------------------------------------- #
# image resolution — "assumed logo if present"
# --------------------------------------------------------------------------- #
def _resolve_ref_image(
    profile: dict[str, Any], image_gallery_dir: Path | None
) -> str:
    """Honor an explicit ``image_ref``/``logo_ref`` (existence-aware) → URL or "".

    refs are stored without the .avif extension by convention. When a gallery dir
    is given, only honor a ref whose file exists (so a pre-registered-but-absent
    ``logo_ref`` falls through instead of emitting a 404 <img>); without one, fall
    back to the historic best-effort behavior.
    """
    for key in ("image_ref", "logo_ref"):
        ref = _as_text(profile.get(key))
        if not ref:
            continue
        fname = ref if ref.lower().endswith(
            (".avif", ".png", ".jpg", ".jpeg", ".svg")) else ref + ".avif"
        if image_gallery_dir is None or (image_gallery_dir / fname).exists():
            return _IMAGE_URL_PREFIX + fname
    return ""


def resolve_profile_image(
    profile: dict[str, Any], slug: str, image_gallery_dir: Path | None
) -> str:
    """Resolve a profile's display image URL, or "" when none is found.

    Order:
      1. explicit ``image_ref`` / ``logo_ref`` → /assets/images/<ref>.avif,
         but ONLY when the referenced file is present (existence-aware).
      2. a gallery file whose name contains the slug AND a role token
         (logo / primary_mark / headshot / profile_headshot / brand-mark)
      3. "" (the UI renders a neutral placeholder).

    Existence-awareness matters because the logo convention *pre-registers* a
    predetermined ``logo_ref`` on every entity (``…artifact-logo.<slug>.logo``)
    even before its leaflet is produced. An absent ref must fall through to the
    slug+role search / placeholder, never emit a broken 404 <img>.
    """
    ref_url = _resolve_ref_image(profile, image_gallery_dir)
    if ref_url:
        return ref_url
    if image_gallery_dir is None or not slug:
        return ""
    try:
        names = sorted(p.name for p in image_gallery_dir.iterdir() if p.is_file())
    except OSError:
        return ""
    for name in names:
        lower = name.lower()
        if slug in lower and any(token in lower for token in _IMAGE_ROLE_TOKENS):
            return _IMAGE_URL_PREFIX + name
    return ""


def attach_profile_thumbnails(
    webapps_root: str | Path | None, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Populate ``image_url`` on ``profiles`` rows IN PLACE from the image gallery.

    The by-type index (``resource_types.build_type_leaflet_index``) types profiles by
    FILENAME only (no YAML load), so a profile row arrives with ``image_url == ""``.
    Resolve each profile's logo/headshot by the same slug + role-token convention as
    ``resolve_profile_image`` branch 2 — but list the image gallery ONCE for the whole
    row set (calling ``resolve_profile_image`` per row would re-glob the dir every
    time) and memoize per slug. Rows with no match keep ``image_url == ""`` → the
    directory renders the neutral dot placeholder. Used by the Browse *directory* view
    only (never the hierarchy), so the dendrogram render pays nothing for it. The
    cheap slug+role match deliberately skips the explicit ``image_ref``/``logo_ref``
    path (that needs a per-profile YAML load); the predetermined logo/headshot
    filenames embed the slug, so they still resolve.
    """
    site_core = _site_core_root(webapps_root)
    image_dir = (site_core / "image") if site_core is not None else None
    if image_dir is None or not image_dir.is_dir():
        return rows
    try:
        names = sorted(p.name for p in image_dir.iterdir() if p.is_file())
    except OSError:
        return rows
    lowered = [(name, name.lower()) for name in names]
    profiles_dir = _profiles_dir(webapps_root)
    by_slug: dict[str, str] = {}
    for row in rows:
        if row.get("gallery") != "profiles" or _as_text(row.get("image_url")):
            continue
        slug = _as_text(row.get("slug"))
        if not slug:
            continue
        if slug not in by_slug:
            url = ""
            for name, lower in lowered:
                if slug in lower and any(t in lower for t in _IMAGE_ROLE_TOKENS):
                    url = _IMAGE_URL_PREFIX + name
                    break
            # The cheap slug-substring pass misses logos whose stem is a SHORTER
            # form of the registered slug (e.g. logo ``akron_microgreens`` vs the
            # slug ``akron_microgreens_llc`` after the legal-name enrichment), and
            # logos whose stem differs entirely (``moon_farm`` → ``moon_farm_
            # microgreens``). Fall back to the profile's explicit logo_ref/image_ref
            # — one YAML load, and ONLY for the rows the slug pass missed.
            if not url and profiles_dir is not None:
                filename = _as_text(row.get("filename"))
                if filename:
                    profile = _load_yaml_mapping(profiles_dir / filename)
                    if profile:
                        url = _resolve_ref_image(profile, image_dir)
            by_slug[slug] = url
        if by_slug[slug]:
            row["image_url"] = by_slug[slug]
    return rows


# --------------------------------------------------------------------------- #
# profile listing + detail
# --------------------------------------------------------------------------- #
# Profile ``entity_type`` now holds a primary NAICS code (see the shared
# profile convention). Short display titles for the codes in use; unknown
# codes fall back to the raw code so nothing is hidden.
_NAICS_TITLES: dict[str, str] = {
    "111219": "Vegetable & Melon Farming",
    "111331": "Apple Orchards",
    "111339": "Noncitrus Fruit Farming",
    "111411": "Mushroom Production",
    "111419": "Food Crops Grown Under Cover",
    "111421": "Nursery & Tree Production",
    "111422": "Floriculture Production",
    "111998": "Misc. Crop Farming",
    "112120": "Dairy Cattle & Milk",
    "112310": "Chicken Egg Production",
    "112320": "Poultry & Egg Production",
    "112410": "Sheep & Wool Farming",
    "112420": "Goat Farming",
    "112910": "Apiculture (Beekeeping)",
    "112990": "Animal Production",
    "312130": "Wineries",
    "424480": "Produce Wholesale",
    "445110": "Grocery Retailers",
    "445230": "Fruit & Vegetable Retail",
    "513210": "Software Publishers",
    "541511": "Software / Services",
    "541714": "Biotech R&D",
    "611310": "Colleges & Universities",
    "712120": "Historical Sites",
    "813312": "Conservation Org",
}


def _naics_title(value: str | None) -> str:
    """Human title for a NAICS code; the raw value if unknown; '' if empty."""
    if not value:
        return ""
    return _NAICS_TITLES.get(str(value).strip(), str(value))


def _profile_display_name(profile: dict[str, Any], slug: str) -> str:
    for key in ("display_name", "name", "card_id", "title"):
        value = _as_text(profile.get(key))
        if value:
            return value
    return slug.replace("_", " ").title()


# Typed-section taxonomy for the layered profile detail. Keys are bucketed by
# entity flavor so the viewer reads top-down: base identity → legal → ag → admin
# → everything else. Contact/social keys are rendered as icon links
# (``contact_links``) and name keys live in the header, so both are excluded.
_HEADER_KEYS = frozenset({"name", "display_name", "title"})
_BASE_KEYS = ("location", "summary_bio", "tags")
_LEGAL_KEYS = ("legal_name", "legal_title", "principal_owner", "entity_type")
_AG_KEYS = ("offerings", "operations", "operation_type", "gallery_refs")
_ADMIN_KEYS = ("business_type", "map_pin")
# Mirrors the keys of ``_FIELD_NAME_KIND`` (defined later) + socials; inlined so
# this module-level constant doesn't depend on definition order.
_CONTACT_KEYS = frozenset(
    {"website", "email", "secondary_email", "org_email", "phone", "secondary_phone", "socials"}
)


def _profile_field(profile: dict[str, Any], key: str) -> dict[str, str]:
    """One ``{key, label, value}`` detail row (NAICS code annotated with title)."""
    value = _scalar_str(profile.get(key))
    if key == "entity_type" and value:
        title = _naics_title(value)
        if title and title != value:
            value = f"{value} — {title}"
    return {
        "key": key,
        "label": "NAICS Code" if key == "entity_type" else str(key).replace("_", " ").title(),
        "value": value,
    }


def _profile_sections(
    profile: dict[str, Any], flavor: str
) -> tuple[list[dict[str, str]], list[dict[str, Any]], dict[str, Any]]:
    """Split a profile's fields into the header band (``base_fields``) + ordered,
    non-empty typed ``sections``, branching on the filename entity flavor. Returns
    ``(base_fields, sections, meta)`` where ``meta`` carries flavor/ag descriptors.
    """
    segs = flavor.split("-") if flavor else []
    is_legal = segs[:1] == ["legal_entity"]
    is_admin = segs[:1] == ["administrative_entity"]
    is_ag = "ag" in segs
    ag_role = ag_subtype = ""
    if is_ag:
        i = segs.index("ag")
        ag_role = segs[i + 1] if len(segs) > i + 1 else ""
        ag_subtype = segs[i + 2] if ag_role == "producer" and len(segs) > i + 2 else ""

    base, legal, ag, admin, other = [], [], [], [], []
    for key in profile:
        if key in _CONTACT_KEYS or key in _HEADER_KEYS:
            continue
        fld = _profile_field(profile, key)
        if key in _BASE_KEYS:
            base.append(fld)
        elif is_legal and key in _LEGAL_KEYS:
            legal.append(fld)
        elif is_ag and key in _AG_KEYS:
            ag.append(fld)
        elif is_admin and key in _ADMIN_KEYS:
            admin.append(fld)
        else:
            other.append(fld)

    sections: list[dict[str, Any]] = []
    if legal:
        sections.append({"id": "legal", "label": "Legal entity", "fields": legal})
    if is_ag:  # emit even with no ag-specific YAML fields so the role/subtype shows
        sections.append({"id": "ag", "label": "Agricultural", "fields": ag})
    if admin:
        sections.append({"id": "admin", "label": "Administrative", "fields": admin})
    if other:
        sections.append({"id": "other", "label": "Additional", "fields": other})

    meta = {
        "entity_flavor": flavor,
        "is_ag": is_ag,
        "ag_role": ag_role,
        "ag_subtype": ag_subtype,
    }
    return base, sections, meta


def list_profiles(webapps_root: str | Path | None) -> list[dict[str, Any]]:
    """Phone-contacts-style roster: one row per canonical profile.

    Each row = {slug, filename, display_name, subtitle, image_url, public,
    entity_scope, related}. The ``public`` / ``entity_scope`` / ``related``
    keys let grantee-scoped callers (the client dashboard) filter the roster
    down to the public, in-scope subset without re-reading the YAML. Sorted by
    display_name. Tolerant of a missing profiles dir (returns []).
    """
    profiles_dir = _profiles_dir(webapps_root)
    site_core = _site_core_root(webapps_root)
    image_dir = (site_core / "image") if site_core is not None else None
    if profiles_dir is None or not profiles_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(profiles_dir.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file() or not path.name.endswith(_PROFILE_SUFFIX):
            continue
        if path.name.startswith(".") or ".example." in path.name:
            continue
        profile = _load_yaml_mapping(path)
        slug = _profile_slug(path.name)
        related = profile.get("related")
        rows.append(
            {
                "slug": slug,
                "filename": path.name,
                "display_name": _profile_display_name(profile, slug),
                "subtitle": _naics_title(_as_text(profile.get("entity_type")))
                or _as_text(profile.get("role")),
                "image_url": resolve_profile_image(profile, slug, image_dir),
                # Visibility + scoping hints (the dashboard never shows a
                # non-public profile; the operator portal shows all of them).
                "public": bool(profile.get("public", False)),
                "entity_scope": _as_text(profile.get("entity_scope")),
                "related": [_as_text(r) for r in related] if isinstance(related, list) else [],
            }
        )
    rows.sort(key=lambda r: r["display_name"].lower())
    return rows


def grantee_profiles(
    webapps_root: str | Path | None, scope_tokens: list[str] | None = None
) -> list[dict[str, Any]]:
    """Read-only, grantee-facing profile roster for the client dashboard.

    Returns the subset of ``list_profiles`` rows a grantee may see:

      * always restricted to ``public: true`` profiles (a grantee never sees a
        non-public/operator-only profile);
      * when ``scope_tokens`` identifies the grantee's own entity (e.g. its
        short_name / domain / slug), narrowed to profiles whose slug,
        ``entity_scope`` or ``related`` references one of those tokens;
      * when scoping is ambiguous (no token matches any profile — the common
        case today, since canonical profiles carry no per-grantee scope yet),
        the full public roster is returned. Read-only, so showing the public
        roster is safe.
    """
    rows = [r for r in list_profiles(webapps_root) if r.get("public")]
    tokens = {_normalize_scope_token(t) for t in (scope_tokens or [])}
    tokens.discard("")
    if not tokens:
        return rows
    scoped = [r for r in rows if _profile_in_scope(r, tokens)]
    return scoped if scoped else rows


def _normalize_scope_token(value: Any) -> str:
    """Lower-case a scope token and collapse separators to underscores so a
    grantee short_name / domain / slug compares against a profile slug.

    ``"Bloom Hill Farm"`` / ``"bloom-hill-farm"`` / ``"bloomhillfarm.com"``
    all normalize toward ``"bloom_hill_farm"`` segments for comparison.
    """
    text = _as_text(value).lower()
    # Drop a domain TLD tail so "bloomhillfarm.com" → "bloomhillfarm".
    if "." in text and "/" not in text and " " not in text:
        text = text.rsplit(".", 1)[0]
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _profile_in_scope(row: dict[str, Any], tokens: set[str]) -> bool:
    """True when a profile row references any of the grantee's scope tokens.

    Matches on WHOLE-token equality of the normalized values: a grantee token
    must equal the profile's normalized slug, ``entity_scope`` or one of its
    ``related`` references. Segment-membership matching is deliberately avoided
    — a grantee whose short_name/label normalizes to a common word (e.g.
    "valley", "farm", "market") must NOT scope-match every unrelated public
    profile that happens to contain that word, which would silently hide the
    rest of the public roster. When no token matches exactly, ``grantee_profiles``
    falls back to the full public roster (read-only, so that is safe).
    """
    candidates = {_normalize_scope_token(row.get("slug"))}
    candidates.add(_normalize_scope_token(row.get("entity_scope")))
    for ref in row.get("related") or []:
        candidates.add(_normalize_scope_token(ref))
    candidates.discard("")
    return bool(tokens & candidates)


def _scalar_str(value: Any) -> str:
    """Flatten a YAML value to a display string (lists → newline-joined)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        parts = [_scalar_str(v) for v in value]
        return "\n".join(p for p in parts if p)
    if isinstance(value, dict):
        return yaml.safe_dump(value, default_flow_style=False, allow_unicode=True).strip()
    return str(value)


def profile_detail(
    webapps_root: str | Path | None, slug: str
) -> dict[str, Any] | None:
    """Full detail view for one profile: every field as {label, key, value}
    INCLUDING empty ones (value-or-""). Returns None when not found.
    """
    profiles_dir = _profiles_dir(webapps_root)
    site_core = _site_core_root(webapps_root)
    image_dir = (site_core / "image") if site_core is not None else None
    if profiles_dir is None or not profiles_dir.is_dir() or not slug:
        return None
    path = _resolve_profile_path(profiles_dir, slug)
    if path is None:
        return None
    profile = _load_yaml_mapping(path)
    # Flat field list (EVERY key incl. empties) — kept for back-compat with the
    # Library detail/edit form and existing tests.
    fields = [_profile_field(profile, key) for key in profile]
    # Layered/typed view for the Browse instance: a header band of base fields
    # beside the enlarged logo, then ordered typed section blocks.
    base_fields, sections, meta = _profile_sections(profile, _profile_entity_flavor(path.name))
    return {
        "slug": slug,
        "filename": path.name,
        "display_name": _profile_display_name(profile, slug),
        "image_url": resolve_profile_image(profile, slug, image_dir),
        "fields": fields,
        "base_fields": base_fields,
        "sections": sections,
        **meta,  # entity_flavor / is_ag / ag_role / ag_subtype
        # Contact + social values as icon-bearing links (field/value → icon map).
        "contact_links": resolve_field_links(profile, webapps_root),
        # Grantee-scoped extra fields (scope_fields) — shown in the grantee's own
        # views, kept out of the general FND views.
        "scopes": resolve_profile_scopes(profile, webapps_root),
    }


def _resolve_profile_path(profiles_dir: Path, slug: str) -> Path | None:
    """Find the single canonical profile file whose slug matches.

    Match is exact on the slug token; rejects ambiguous matches (None).
    """
    if not slug:
        return None
    matches = [
        p
        for p in profiles_dir.iterdir()
        if p.is_file()
        and p.name.endswith(_PROFILE_SUFFIX)
        and not p.name.startswith(".")
        and ".example." not in p.name
        and _profile_slug(p.name) == slug
    ]
    if len(matches) == 1:
        return matches[0]
    return None


# --------------------------------------------------------------------------- #
# edit / save (canonical) + propagation
# --------------------------------------------------------------------------- #
# Editable profile fields and their FORM TYPE. The type drives both the editor
# (build_profile_edit_frame → component-library form) and save_profile's
# decoding: ``text`` → scalar str/None; ``multiline`` → scalar str; ``bio`` →
# a multiline textarea stored as a paragraph list; ``string_list`` → a chip
# editor stored as list[str]. Structured dict-lists (socials/operations/
# coordinates/include) and admin keys are NOT listed → preserved untouched.
_PROFILE_FIELD_TYPES: dict[str, str] = {
    "display_name": "text",
    "name": "text",
    "card_id": "text",
    "entity_type": "text",
    "role": "text",
    "organization": "text",
    "location": "text",
    "website": "url",
    "email": "email",
    "secondary_email": "email",
    "org_email": "email",
    "phone": "text",
    "image_ref": "text",
    "logo_ref": "text",
    "summary_bio": "multiline",
    "bio": "bio",
    "tags": "string_list",
    "offerings": "string_list",
    "gallery_refs": "string_list",
    "related": "string_list",
}


def _split_paragraphs(text: str) -> list[str]:
    """A multi-paragraph textarea → a list of paragraph strings.

    Paragraphs are separated by BLANK lines (the natural break); a single block
    of text — even with soft line wraps — stays ONE paragraph (no per-line
    shattering). Empty paragraphs are dropped.
    """
    chunks = re.split(r"\n\s*\n", _as_text(text).replace("\r\n", "\n").strip())
    return [c.strip() for c in chunks if c.strip()]


def _coerce_string_list(value: Any) -> list[str]:
    """A string_list form value (array, or newline/comma text) → list[str]."""
    if isinstance(value, list):
        items = value
    else:
        items = re.split(r"[\n,]", _as_text(value))
    return [_as_text(x).strip() for x in items if _as_text(x).strip()]


def save_profile(
    webapps_root: str | Path | None, slug: str, fields: dict[str, Any]
) -> dict[str, Any]:
    """Patch the editable scalar fields of a canonical profile and write it
    back atomically. Non-editable / unknown keys are preserved untouched.

    NOTE: the canonical YAML is round-tripped through PyYAML, so the cosmetic
    ``# --- Section ---`` comment dividers in the hand-authored files are
    dropped on first save (PyYAML is not comment-preserving). Key order and all
    data are preserved (``sort_keys=False``); only the decorative comments are
    lost. This is intentional for now — adopting a comment-preserving loader
    (ruamel) would add a dependency for a purely cosmetic gain.

    Returns {"ok": True, "filename": ..., "path": ...} or
    {"ok": False, "error": ...}.
    """
    profiles_dir = _profiles_dir(webapps_root)
    if profiles_dir is None or not profiles_dir.is_dir():
        return {"ok": False, "error": "no_profiles_dir"}
    path = _resolve_profile_path(profiles_dir, slug)
    if path is None:
        return {"ok": False, "error": "profile_not_found"}
    profile = _load_yaml_mapping(path)
    if not profile:
        return {"ok": False, "error": "profile_unreadable"}
    for key, ftype in _PROFILE_FIELD_TYPES.items():
        if key not in fields:
            continue
        value = fields[key]
        if ftype == "string_list":
            profile[key] = _coerce_string_list(value)
        elif ftype == "bio":
            profile[key] = _split_paragraphs(_as_text(value))
        else:  # text / url / email / multiline scalar
            text = _as_text(value)
            profile[key] = text if text else None  # YAML null for cleared optionals
    text = yaml.safe_dump(
        profile, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    try:
        _atomic_write_text(path, text)
    except OSError as exc:
        return {"ok": False, "error": "write_failed", "detail": str(exc)}
    return {"ok": True, "filename": path.name, "path": str(path)}


def build_profile_edit_frame(
    webapps_root: str | Path | None, slug: str
) -> dict[str, Any] | None:
    """A component-library FORM frame for editing a profile.

    Uses the portal's shared form-component system (the same one
    ``ext_grantee_profile`` uses via ``build_form_component_frame``) rather than
    a one-off editor: scalars → text, summary_bio/bio → multiline, simple lists
    → string_list chips. Values are read from the RAW canonical YAML so
    list/multiline fields round-trip. Returns None when the profile is missing.
    """
    from MyCiteV2.packages.state_machine.nimm.mediate_handlers import (
        build_form_component_frame,
    )

    profiles_dir = _profiles_dir(webapps_root)
    path = _resolve_profile_path(profiles_dir, slug) if profiles_dir else None
    if path is None:
        return None
    profile = _load_yaml_mapping(path)
    fields: list[dict[str, Any]] = []
    for key, ftype in _PROFILE_FIELD_TYPES.items():
        if key not in profile:
            continue
        raw = profile.get(key)
        if ftype == "string_list":
            # Rendered as a multiline textarea (one item per line) rather than the
            # component-library chip editor, which has no add/remove wiring.
            # save_profile's _coerce_string_list accepts the newline text.
            value: Any = "\n".join(_as_text(x) for x in raw) if isinstance(raw, list) else _as_text(raw)
            field_type = "multiline"
        elif ftype == "bio":
            value = "\n\n".join(_as_text(x) for x in raw) if isinstance(raw, list) else _as_text(raw)
            field_type = "multiline"
        elif ftype == "multiline":
            value = _as_text(raw)
            field_type = "multiline"
        else:
            value = _as_text(raw)
            field_type = ftype if ftype in ("text", "url", "email") else "text"
        fields.append(
            {
                "key": key,
                "label": key.replace("_", " ").title(),
                "type": field_type,
                "value": value,
            }
        )
    if not fields:
        return None
    return build_form_component_frame(
        frame_id=f"profile_edit_{slug}",
        label=_profile_display_name(profile, slug),
        intro=(
            "Edit this profile. Saving re-derives the per-site excerpts and "
            "rebuilds the owning sites so the change reaches the live pages."
        ),
        fields=fields,
        submit_action={
            "route": "/__fnd/resources/profile/save",
            "schema": "mycite.v2.resources.profile.save.v1",
            "payload": {"slug": slug},
        },
        submit_label="Save & publish",
        target_authority="utilities",
    )


def derive_profile_excerpt(canonical_path: str | Path, excerpt_path: str | Path) -> bool:
    """Refill an EXISTING per-site excerpt's keys from the canonical profile.

    The excerpt is a strict subset of canonical keys (see
    ``...nathan_seals-board_member_bio.yaml``). This re-reads each key the
    excerpt already declares from the canonical and rewrites the excerpt
    atomically, preserving the excerpt's key SET and order. Returns True when
    the excerpt was rewritten, False when either file is missing/unreadable.
    """
    canonical = _load_yaml_mapping(Path(canonical_path))
    excerpt_p = Path(excerpt_path)
    if not canonical or not excerpt_p.is_file():
        return False
    excerpt = _load_yaml_mapping(excerpt_p)
    if not excerpt:
        return False
    # Refill only the keys the excerpt already declares AND the canonical
    # still defines — never widen the excerpt's surface or invent keys.
    refilled = {
        key: canonical[key] if key in canonical else excerpt[key] for key in excerpt
    }
    text = yaml.safe_dump(
        refilled, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    try:
        _atomic_write_text(excerpt_p, text)
    except OSError:
        return False
    return True


def _excerpt_paths_for_slug(webapps_root: str | Path, slug: str) -> list[Path]:
    """Glob every per-site excerpt whose filename references this slug.

    Per-site excerpts live at clients/<site>/frontend/assets/*<slug>*.yaml and
    are NOT record-manifests, NOT the canonical (which lives under
    _shared/site-core), and NOT *.example.* templates.
    """
    clients_root = Path(webapps_root) / "clients"
    out: list[Path] = []
    pattern = str(clients_root / "*" / "frontend" / "assets" / f"*{slug}*.yaml")
    for hit in glob.glob(pattern):
        p = Path(hit)
        name = p.name
        if "_shared" in p.parts:
            continue
        if "record-manifest" in name or ".example." in name:
            continue
        # Guard against substring over-match (e.g. slug "localize" hitting a
        # different entity's excerpt). The slug must appear as a whole token —
        # bounded on each side by a name separator (start/dot/dash/underscore
        # before, dash/dot/end after) — matching the
        # ``<entity>.<slug>-<role>.yaml`` / ``<slug>.yaml`` convention.
        if not _slug_is_token(name, slug):
            continue
        out.append(p)
    return sorted(out)


def _slug_is_token(filename: str, slug: str) -> bool:
    """True when ``slug`` appears as a whole name-token within ``filename``.

    A token boundary is the string start/end or one of ``. - _``. This rejects
    a slug that is merely a substring of a longer unrelated token while still
    accepting the real per-site excerpt naming (``...entity.slug-role.yaml``).
    """
    return re.search(rf"(?:^|[._-]){re.escape(slug)}(?:[.\-]|$)", filename) is not None


def _git_dirty_paths(repo_cwd: Path) -> set[str]:
    """Return the set of porcelain-reported dirty paths (repo-relative).

    Empty set when not a git repo or git is unavailable — the caller then
    skips scoping rather than failing the build.
    """
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            check=False,
            capture_output=True,
            timeout=60,
            cwd=str(repo_cwd),
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if out.returncode != 0:
        return set()
    paths: set[str] = set()
    for line in out.stdout.decode("utf-8", "replace").splitlines():
        # Porcelain: XY <path> (rename uses " -> "; take the destination).
        entry = line[3:].strip()
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        if entry:
            paths.add(entry.strip('"'))
    return paths


def _build_site_for_excerpt(excerpt_path: Path, slug: str) -> tuple[bool, str]:
    """Run the owning site's render_manifest build_site so the excerpt's edit
    reaches the rendered HTML, then SCOPE the result to ``slug``.

    GOTCHA (per Nathan Seals): build_site rebuilds the WHOLE site and can emit
    render-noise / revert hand-edited rendered pages. So we capture the git
    dirty set BEFORE the build and, after, ``git checkout --`` every rendered
    .html the build newly dirtied that does NOT reference ``slug`` — keeping the
    change scoped to the page(s) actually about this profile and never
    clobbering unrelated hand-edits. Best-effort: when not a git repo, the build
    still runs unscoped (the same behavior as before).
    """
    # excerpt: clients/<site>/frontend/assets/<file>.yaml → frontend dir is
    # two parents up from the assets dir.
    assets_dir = excerpt_path.parent
    frontend_dir = assets_dir.parent
    script = frontend_dir / "scripts" / "render_manifest.py"
    if not script.is_file():
        return False, f"no render_manifest.py at {script}"

    dirty_before = _git_dirty_paths(frontend_dir)
    try:
        completed = subprocess.run(
            [sys.executable, str(script)],
            check=False,
            capture_output=True,
            timeout=300,
            cwd=str(frontend_dir),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"build failed to launch: {exc}"
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        return False, f"build_site exited {completed.returncode}: {detail[:400]}"

    reverted = _scope_rebuild_to_slug(frontend_dir, slug, dirty_before)
    note = "rebuilt"
    if reverted:
        note = f"rebuilt (scoped: reverted {reverted} unrelated page(s))"
    return True, note


def _scope_rebuild_to_slug(
    frontend_dir: Path, slug: str, dirty_before: set[str]
) -> int:
    """Revert rendered .html files the build newly dirtied that don't mention
    ``slug``. Returns the count reverted. No-op outside a git repo.
    """
    dirty_after = _git_dirty_paths(frontend_dir)
    newly = dirty_after - dirty_before
    if not newly:
        return 0
    to_revert: list[str] = []
    for rel in newly:
        if not rel.endswith(".html"):
            continue
        # Porcelain paths are relative to the git repo root, not frontend_dir;
        # recover the absolute path via the repo root.
        candidate = _resolve_repo_relative(frontend_dir, rel)
        if candidate is None or not candidate.is_file():
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        if slug.replace("_", " ").lower() in text.lower() or slug in text:
            # This page legitimately reflects the profile — keep the rebuild.
            continue
        to_revert.append(rel)
    if not to_revert:
        return 0
    # Porcelain paths are repo-root-relative, so run the checkout FROM the repo
    # root (not frontend_dir) or the paths won't resolve.
    repo_root = _git_repo_root(frontend_dir)
    if repo_root is None:
        return 0
    try:
        out = subprocess.run(
            ["git", "checkout", "--", *to_revert],
            check=False,
            capture_output=True,
            timeout=120,
            cwd=str(repo_root),
        )
    except (OSError, subprocess.TimeoutExpired):
        return 0
    if out.returncode != 0:
        return 0
    return len(to_revert)


def _git_repo_root(cwd: Path) -> Path | None:
    """Absolute path of the git repo root containing ``cwd``, or None."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            timeout=60,
            cwd=str(cwd),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return Path(out.stdout.decode("utf-8", "replace").strip())


def _resolve_repo_relative(frontend_dir: Path, rel: str) -> Path | None:
    """Map a git-porcelain repo-relative path to an absolute path.

    git status (run in frontend_dir) reports paths relative to the repo ROOT,
    so we locate the repo root once and join.
    """
    root = _git_repo_root(frontend_dir)
    return (root / rel) if root is not None else None


def propagate_profile(
    webapps_root: str | Path | None, slug: str, *, rebuild: bool = True
) -> dict[str, Any]:
    """After a canonical save: re-derive every per-site excerpt for ``slug``
    and (optionally) rebuild each owning site so the edit reaches live HTML.

    Returns {"derived": [paths], "rebuilt": [sites], "errors": [...],
    "fnd_network": <note|None>}. ``fnd_network`` is the result of regenerating
    the FND agricultural-network map dataset when this profile feeds it.
    """
    result: dict[str, Any] = {
        "derived": [],
        "rebuilt": [],
        "errors": [],
        "fnd_network": None,
    }
    if not webapps_root or not slug:
        result["errors"].append("missing_webapps_root_or_slug")
        return result
    profiles_dir = _profiles_dir(webapps_root)
    if profiles_dir is None:
        result["errors"].append("no_profiles_dir")
        return result
    canonical = _resolve_profile_path(profiles_dir, slug)
    if canonical is None:
        result["errors"].append("canonical_not_found")
        return result
    excerpts = _excerpt_paths_for_slug(webapps_root, slug)
    rebuilt_frontends: set[Path] = set()
    for excerpt in excerpts:
        if derive_profile_excerpt(canonical, excerpt):
            result["derived"].append(str(excerpt))
            if rebuild:
                frontend_dir = excerpt.parent.parent
                if frontend_dir not in rebuilt_frontends:
                    ok, detail = _build_site_for_excerpt(excerpt, slug)
                    if ok:
                        result["rebuilt"].append(str(frontend_dir))
                    else:
                        result["errors"].append(detail)
                    rebuilt_frontends.add(frontend_dir)
        else:
            result["errors"].append(f"derive_failed:{excerpt}")
    # A network MAP renders from a pre-generated dataset, not from excerpts — so a
    # profile that a site lists in its consolidated manifest profile section (and
    # that site ships a build script) needs the dataset regenerated separately.
    if rebuild:
        ok, note = _regenerate_network_for_profile(webapps_root, slug)
        if note:
            result["fnd_network"] = note
        if not ok and note and not note.startswith("skipped"):
            result["errors"].append(f"fnd_network:{note}")
    return result


# Per-site network map: the /more map renders from the site's CONSOLIDATED
# manifest profile section (resources.profile) via the per-site
# build_farm_network.py. A profile add/remove on a mapped site is followed by a
# rebuild. FND is the only site shipping a map today, but nothing here is
# FND-specific — any site with a build_farm_network.py participates.
_FND_SITE_DIR = "fruitfulnetworkdevelopment.com"


def _network_build_script(webapps_root: str | Path, site: str) -> Path:
    """Path to a site's network-map dataset builder (may not exist)."""
    return (
        Path(webapps_root)
        / "clients"
        / os.path.basename(_as_text(site))
        / "frontend"
        / "scripts"
        / "build_farm_network.py"
    )


def _site_has_network_build(webapps_root: str | Path, site: str) -> bool:
    """True when the site ships a network-map dataset builder."""
    return _network_build_script(webapps_root, site).is_file()


def _run_site_network_build(webapps_root: str | Path, site: str) -> tuple[bool, str]:
    """Run a site's ``build_farm_network.py`` to regenerate its map dataset.

    The map renders from the site's consolidated manifest profile section, so a
    profile add/remove on a mapped site is followed by this rebuild. Returns
    ``(ok, note)``; a skip note when the site has no build script. Mirrors the
    subprocess pattern of ``_build_site_for_excerpt``.
    """
    script = _network_build_script(webapps_root, site)
    if not script.is_file():
        return True, "skipped: no build_farm_network.py"
    frontend_dir = script.parent.parent
    try:
        completed = subprocess.run(
            [sys.executable, str(script)],
            check=False,
            capture_output=True,
            timeout=300,
            cwd=str(frontend_dir),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"build_farm_network failed to launch: {exc}"
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        return False, f"build_farm_network exited {completed.returncode}: {detail[:300]}"
    return True, "network dataset regenerated"


def _sites_using_profile(webapps_root: str | Path, slug: str) -> list[str]:
    """Sites whose consolidated manifest profile section lists ``slug``."""
    slug = _as_text(slug)
    if not webapps_root or not slug:
        return []
    out: list[str] = []
    pattern = str(
        Path(webapps_root) / "clients" / "*" / "frontend" / "assets"
        / "*.shared_resources.yaml"
    )
    for path in glob.glob(pattern):
        site = Path(path).parts[-4]
        for e in site_manifest_entries(webapps_root, site, "profile"):
            if e["asset_id"] == slug or _profile_slug(os.path.basename(e["asset_path"])) == slug:
                out.append(site)
                break
    return sorted(set(out))


def _regenerate_network_for_profile(
    webapps_root: str | Path, slug: str
) -> tuple[bool, str]:
    """Rebuild the map dataset for every site whose consolidated manifest profile
    section lists ``slug`` and that ships a build script. Used by
    ``propagate_profile`` so editing a mapped profile refreshes the map.
    """
    notes: list[str] = []
    ok_all = True
    for site in _sites_using_profile(webapps_root, slug):
        if _site_has_network_build(webapps_root, site):
            ok, note = _run_site_network_build(webapps_root, site)
            ok_all = ok_all and ok
            notes.append(f"{site}: {note}")
    return ok_all, "; ".join(notes) or "skipped: profile not on any map"


def _after_profile_manifest_write(
    webapps_root: str | Path, site: str, kind: str, result: dict[str, Any]
) -> dict[str, Any]:
    """Post-write hook: when a PROFILE was allocated/de-allocated on a site that
    ships a map, regenerate the dataset. The manifest is the source of truth, so
    a build failure is reported as a warning but does NOT fail the write (the
    dataset can be regenerated; a stale dataset is recoverable, a lost manifest
    edit is not).
    """
    if result.get("ok") and kind == "profile" and _site_has_network_build(webapps_root, site):
        ok, note = _run_site_network_build(webapps_root, site)
        result["network_build"] = note
        if not ok:
            result["network_build_ok"] = False
    return result


# --------------------------------------------------------------------------- #
# icon dedup (sha256 byte-identical) + manifest referencing
# --------------------------------------------------------------------------- #
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    try:
        h.update(path.read_bytes())
    except OSError:
        return ""
    return h.hexdigest()


def _icon_manifest_referenced_paths(webapps_root: str | Path) -> set[str]:
    """Asset_paths referenced by any site *icon_use.yaml record-manifest.

    Thin alias over the generalized :func:`manifest_referenced_paths`; kept so
    ``icon_duplicate_groups`` / ``remove_icon_duplicate`` read identically.
    """
    return manifest_referenced_paths(webapps_root, "icon")


def icon_duplicate_groups(webapps_root: str | Path | None) -> list[dict[str, Any]]:
    """Group byte-identical icons (sha256). Each group lists its members with
    whether each is referenced in any site icon_use manifest. Single-member
    groups (no duplicate) are omitted.
    """
    site_core = _site_core_root(webapps_root)
    if site_core is None:
        return []
    icon_dir = site_core / "icon"
    if not icon_dir.is_dir():
        return []
    referenced = _icon_manifest_referenced_paths(webapps_root)
    by_hash: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(icon_dir.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file() or path.name.startswith("."):
            continue
        digest = _sha256(path)
        if not digest:
            continue
        asset_path = f"/assets/icons/{path.name}"
        by_hash.setdefault(digest, []).append(
            {
                "filename": path.name,
                "asset_path": asset_path,
                "referenced": asset_path in referenced,
            }
        )
    groups = [
        {"sha256": digest, "members": members}
        for digest, members in by_hash.items()
        if len(members) > 1
    ]
    groups.sort(key=lambda g: g["members"][0]["filename"])
    return groups


def remove_icon_duplicate(
    webapps_root: str | Path | None, filename: str
) -> dict[str, Any]:
    """Remove a single icon file ONLY when it is (a) part of a byte-identical
    duplicate group and (b) itself unreferenced by any manifest. Refuses
    otherwise — never deletes a unique or referenced asset.
    """
    site_core = _site_core_root(webapps_root)
    if site_core is None:
        return {"ok": False, "error": "no_webapps_root"}
    name = os.path.basename(_as_text(filename))
    if not name or name.startswith("."):
        return {"ok": False, "error": "invalid_filename"}
    target = site_core / "icon" / name
    if not target.is_file():
        return {"ok": False, "error": "not_found"}
    asset_path = f"/assets/icons/{name}"
    if asset_path in _icon_manifest_referenced_paths(webapps_root):
        return {"ok": False, "error": "referenced"}
    digest = _sha256(target)
    duplicates = [
        p
        for p in (site_core / "icon").iterdir()
        if p.is_file() and p.name != name and _sha256(p) == digest
    ]
    if not duplicates:
        return {"ok": False, "error": "not_a_duplicate"}
    try:
        target.unlink()
    except OSError as exc:
        return {"ok": False, "error": "delete_failed", "detail": str(exc)}
    return {"ok": True, "removed": name, "remaining": [p.name for p in duplicates]}


# --------------------------------------------------------------------------- #
# add-to-manifest
# --------------------------------------------------------------------------- #
def add_asset_to_manifest(
    webapps_root: str | Path | None,
    *,
    site: str,
    kind: str,
    asset_id: str,
    asset_path: str,
    entity_scope: str = "",
) -> dict[str, Any]:
    """Append an asset entry to the ``resources[<kind>]`` section of a site's
    consolidated ``shared_resources.yaml`` record-manifest.

    Dedupes by asset_path (no-op when already present), preserves hand-edited
    entries, writes atomically. ``site`` is the client domain dir under
    clients/. When ``kind == 'profile'`` and the site ships a network-map build
    script, the map dataset is regenerated afterward (see
    ``_after_profile_manifest_write``). Returns {"ok", "added", "manifest"}.
    """
    if not webapps_root:
        return {"ok": False, "error": "no_webapps_root"}
    site = os.path.basename(_as_text(site))
    kind = _as_text(kind)
    asset_path = _as_text(asset_path)
    if not site or not kind or not asset_path:
        return {"ok": False, "error": "missing_field"}
    assets_dir = Path(webapps_root) / "clients" / site / "frontend" / "assets"
    if not assets_dir.is_dir():
        return {"ok": False, "error": "unknown_site"}
    manifest_path = _shared_manifest_path(webapps_root, site)
    if manifest_path is None:
        return {"ok": False, "error": "no_manifest"}
    try:
        data = _load_yaml_mapping_required(manifest_path)
    except ValueError as exc:
        # Refuse to overwrite a corrupt manifest with a 1-entry file (would drop
        # every previously-allocated asset). Leave it for a human to repair.
        return {"ok": False, "error": "unparseable_manifest", "detail": str(exc)}
    section = _manifest_section(data, kind)
    for entry in section:
        if isinstance(entry, dict) and _as_text(entry.get("asset_path")) == asset_path:
            return {"ok": True, "added": False, "manifest": str(manifest_path)}
    section.append(
        {
            "asset_id": _as_text(asset_id) or asset_path,
            "asset_path": asset_path,
            "consumers": [],
            "entity_scope": _as_text(entity_scope)
            or _as_text(data.get("site_entity")),
        }
    )
    text = yaml.safe_dump(
        data, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    try:
        _atomic_write_text(manifest_path, text)
    except OSError as exc:
        return {"ok": False, "error": "write_failed", "detail": str(exc)}
    result = {"ok": True, "added": True, "manifest": str(manifest_path)}
    return _after_profile_manifest_write(webapps_root, site, kind, result)


def _shared_manifest_path(webapps_root: str | Path, site: str) -> Path | None:
    """Resolve a site's single consolidated ``*.shared_resources.yaml``
    record-manifest, or None. Replaces the per-kind ``*_use.yaml`` files."""
    assets_dir = Path(webapps_root) / "clients" / os.path.basename(_as_text(site)) / "frontend" / "assets"
    matches = glob.glob(str(assets_dir / "*.shared_resources.yaml"))
    return Path(sorted(matches)[0]) if matches else None


def _manifest_section(data: dict[str, Any], kind: str) -> list:
    """The live ``resources[kind]`` list inside a loaded consolidated manifest,
    creating empty containers as needed so callers can mutate it in place."""
    res = data.get("resources")
    if not isinstance(res, dict):
        res = {}
        data["resources"] = res
    section = res.get(_as_text(kind))
    if not isinstance(section, list):
        section = []
        res[_as_text(kind)] = section
    return section


def site_manifest_entries(
    webapps_root: str | Path | None, site: str, kind: str
) -> list[dict[str, Any]]:
    """The entries in a site's consolidated manifest ``resources[<kind>]`` section.

    Each row = {asset_id, asset_path, entity_scope}. Empty list when the site or
    manifest is absent. Reuses ``_load_yaml_mapping``.
    """
    if not webapps_root:
        return []
    manifest_path = _shared_manifest_path(webapps_root, site)
    if manifest_path is None:
        return []
    data = _load_yaml_mapping(manifest_path)
    res = data.get("resources") if isinstance(data.get("resources"), dict) else {}
    rows: list[dict[str, Any]] = []
    for entry in res.get(_as_text(kind)) or []:
        if isinstance(entry, dict):
            rows.append(
                {
                    "asset_id": _as_text(entry.get("asset_id")),
                    "asset_path": _as_text(entry.get("asset_path")),
                    "entity_scope": _as_text(entry.get("entity_scope")),
                }
            )
    return rows


def remove_asset_from_manifest(
    webapps_root: str | Path | None, *, site: str, kind: str, asset_path: str
) -> dict[str, Any]:
    """Drop the entry whose ``asset_path`` matches from the ``resources[<kind>]``
    section of a site's consolidated ``shared_resources.yaml`` manifest (the
    de-allocation sibling of ``add_asset_to_manifest``). Atomic; no-op when not
    present. For ``profile`` on a mapped site the map dataset is regenerated.
    Returns ``{ok, removed: bool, manifest}``.
    """
    if not webapps_root:
        return {"ok": False, "error": "no_webapps_root"}
    site = os.path.basename(_as_text(site))
    kind = _as_text(kind)
    asset_path = _as_text(asset_path)
    if not site or not kind or not asset_path:
        return {"ok": False, "error": "missing_field"}
    manifest_path = _shared_manifest_path(webapps_root, site)
    if manifest_path is None:
        return {"ok": False, "error": "no_manifest"}
    data = _load_yaml_mapping(manifest_path)
    res = data.get("resources") if isinstance(data.get("resources"), dict) else {}
    entries = res.get(kind)
    if not isinstance(entries, list):
        return {"ok": True, "removed": False, "manifest": str(manifest_path)}
    kept = [
        e
        for e in entries
        if not (isinstance(e, dict) and _as_text(e.get("asset_path")) == asset_path)
    ]
    if len(kept) == len(entries):
        return {"ok": True, "removed": False, "manifest": str(manifest_path)}
    res[kind] = kept
    data["resources"] = res
    text = yaml.safe_dump(
        data, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    try:
        _atomic_write_text(manifest_path, text)
    except OSError as exc:
        return {"ok": False, "error": "write_failed", "detail": str(exc)}
    result = {"ok": True, "removed": True, "manifest": str(manifest_path)}
    return _after_profile_manifest_write(webapps_root, site, kind, result)


# --------------------------------------------------------------------------- #
# collective gallery management — slug-grouped library (all leaflet types)
# --------------------------------------------------------------------------- #
# gallery dir name -> (manifest kind, nginx asset URL prefix). The manifest
# kind is the token in clients/<site>/frontend/assets/*<kind>_use.yaml; the URL
# prefix is where nginx serves that gallery (snippets/shared-assets.conf).
_GALLERY_META: dict[str, dict[str, str]] = {
    "profiles": {"kind": "profile", "url_prefix": "/assets/profiles/"},
    "icon": {"kind": "icon", "url_prefix": "/assets/icons/"},
    "image": {"kind": "image", "url_prefix": "/assets/images/"},
    "document": {"kind": "document", "url_prefix": "/assets/document/"},
    "audio": {"kind": "audio", "url_prefix": "/assets/audio/"},
    # Declaration-only (non-nginx) galleries. Their leaflets may carry PII
    # (BPW job residuals / finite events), so they are recognised here for
    # kind/dir resolution but kept OUT of the global MANAGED_GALLERIES library
    # scan — surfaced grantee-scoped via custom_detail + the dashboard CUSTOM
    # subtab. asset_path is the logical /site-core/<dir>/<file> pseudo-path.
    "event": {"kind": "event", "url_prefix": "/site-core/event/"},
    "custom": {"kind": "custom", "url_prefix": "/site-core/custom/"},
}
# Galleries the operator can manage as a collective gallery (non-PII). events +
# contacts + custom are deliberately excluded — events/custom are PII-bearing and
# managed grantee-scoped; contacts stay read-only filename/count only.
MANAGED_GALLERIES: tuple[str, ...] = ("profiles", "icon", "image", "document", "audio")

# A slug segment: letters/digits start, then letters/digits/dash/underscore.
_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def gallery_dir_for(webapps_root: str | Path | None, gallery: str) -> Path | None:
    root = _site_core_root(webapps_root)
    if root is None or gallery not in _GALLERY_META:
        return None
    return root / gallery


def asset_url_prefix_for(gallery: str) -> str:
    meta = _GALLERY_META.get(_as_text(gallery))
    return meta["url_prefix"] if meta else ""


def manifest_kind_for(gallery: str) -> str:
    meta = _GALLERY_META.get(_as_text(gallery))
    return meta["kind"] if meta else ""


def manifest_referenced_paths(webapps_root: str | Path | None, kind: str) -> set[str]:
    """Every ``asset_path`` in any site's consolidated manifest
    ``resources[<kind>]`` section.

    Works for any kind (profile/image/icon/document/audio/event/custom); used to
    gate delete and to flag which library members are in use by some site.
    """
    referenced: set[str] = set()
    kind = _as_text(kind)
    if not webapps_root or not kind:
        return referenced
    pattern = str(
        Path(webapps_root) / "clients" / "*" / "frontend" / "assets" / "*.shared_resources.yaml"
    )
    for hit in glob.glob(pattern):
        data = _load_yaml_mapping(Path(hit))
        res = data.get("resources") if isinstance(data.get("resources"), dict) else {}
        for entry in res.get(kind) or []:
            if isinstance(entry, dict):
                ap = _as_text(entry.get("asset_path"))
                if ap:
                    referenced.add(ap)
    return referenced


def _asset_descriptor(filename: str) -> tuple[str, str, str]:
    """Split a generic gallery filename into (slug, owner, ext).

    ``0000-00-00.artifact-icon.mycite-ui.add.svg`` → ("add", "mycite-ui", "svg").
    The slug is the dot-token immediately before the extension; the owner is the
    token before the slug. NOT for profiles (use ``_profile_slug``).
    """
    name = str(filename)
    ext = ""
    stem = name
    if "." in name:
        stem, ext = name.rsplit(".", 1)
    parts = stem.split(".")
    slug = parts[-1] if parts else stem
    owner = parts[-2] if len(parts) >= 2 else ""
    return slug, owner, ext.lower()


def _leaflet_display_name(slug: str) -> str:
    """A human display name from a leaflet's NAME slug: snake/kebab → Title Case
    (``greenfield_berry_farm`` → ``Greenfield Berry Farm``), falling back to the raw
    slug. Uniform across leaflet types so the browser shows the name, not the full
    filename or the snake_case slug."""
    pretty = _as_text(slug).replace("_", " ").replace("-", " ").strip()
    return pretty.title() if pretty else _as_text(slug)


# --------------------------------------------------------------------------- #
# field/value → icon convention (CONTENT representation; SEPARATE from the
# type→icon manifest). A leaflet's contact + social VALUES (website / email /
# phone / socials[].platform) render with recognizable icons in the portal viewer
# and dashboard. Operator overrides live in a side-car keyed by VALUE KIND, so the
# same uniform mapping is reused across leaflets and surfaces.
# --------------------------------------------------------------------------- #
_FIELD_ICON_MAP_REL = ("schema", "field_icon_map.mycite.yaml")
_FIELD_ICON_DEFAULTS: dict[str, str] = {
    "website": "0000-00-00.artifact-icon.mycite.globe",
    "email": "0000-00-00.artifact-icon.mycite-ui.mail",
    "phone": "0000-00-00.artifact-icon.mycite.phoneme",
    "link": "0000-00-00.artifact-icon.mycite-ui.link",
    "facebook": "0000-00-00.artifact-logo.facebook.logo",
    "instagram": "0000-00-00.artifact-logo.instagram.logo",
    "linkedin": "0000-00-00.artifact-logo.linkedin.logo",
    "youtube": "0000-00-00.artifact-logo.youtube.logo",
    "x": "0000-00-00.artifact-logo.x_twitter.logo",
    "twitter": "0000-00-00.artifact-logo.x_twitter.logo",
    "gmail": "0000-00-00.artifact-logo.gmail.logo",
}
# Contact field NAME → value kind. A social entry's ``platform`` is itself the kind.
_FIELD_NAME_KIND: dict[str, str] = {
    "website": "website",
    "email": "email",
    "secondary_email": "email",
    "org_email": "email",
    "phone": "phone",
    "secondary_phone": "phone",
}
_FIELD_ICON_PREFIX = "/assets/icons/"


def _field_icon_map_path(webapps_root: str | Path | None) -> Path | None:
    root = _site_core_root(webapps_root)
    return root.joinpath(*_FIELD_ICON_MAP_REL) if root is not None else None


def load_field_icon_map(webapps_root: str | Path | None) -> dict[str, str]:
    """``kind -> icon_ref`` for content-field representation: the seeded defaults
    merged over the operator override side-car. SEPARATE from the type→icon manifest
    (this maps a VALUE kind inside a leaflet, not the leaflet's type)."""
    merged = dict(_FIELD_ICON_DEFAULTS)
    path = _field_icon_map_path(webapps_root)
    if path is not None and path.is_file():
        for k, v in _load_yaml_mapping(path).items():
            key = _as_text(k).lower()
            if key:
                merged[key] = _as_text(v)
    return merged


def set_field_icon(webapps_root: str | Path | None, kind: str, icon_ref: str) -> dict[str, Any]:
    """Persist an operator field-kind → icon override (atomic side-car). ``icon_ref``
    "" removes the override (falls back to the seeded default / no icon)."""
    kind = _as_text(kind).lower()
    icon_ref = _as_text(icon_ref)
    if not kind:
        return {"ok": False, "error": "missing field kind"}
    path = _field_icon_map_path(webapps_root)
    if path is None:
        return {"ok": False, "error": "site-core root unavailable"}
    overrides: dict[str, str] = {}
    if path.is_file():
        overrides = {
            _as_text(k).lower(): _as_text(v)
            for k, v in _load_yaml_mapping(path).items()
            if _as_text(k)
        }
    if icon_ref:
        overrides[kind] = icon_ref
    else:
        overrides.pop(kind, None)
    _atomic_write_text(
        path, yaml.safe_dump(overrides, default_flow_style=False, sort_keys=True, allow_unicode=True)
    )
    return {"ok": True, "kind": kind, "icon_ref": icon_ref}


def _field_link_href(kind: str, value: str) -> str:
    v = _as_text(value)
    if not v:
        return ""
    if v.lower().startswith(("http://", "https://", "mailto:", "tel:")):
        return v
    if kind == "email" or "@" in v:
        return "mailto:" + v
    if kind == "phone":
        digits = "".join(c for c in v if c.isdigit() or c == "+")
        return ("tel:" + digits) if digits else v
    return ("https://" + v) if "." in v else v


def resolve_field_links(profile: dict[str, Any], webapps_root: str | Path | None) -> list[dict[str, Any]]:
    """A profile's contact + social values as icon-bearing links:
    ``[{kind, label, value, href, icon_ref, icon_url}]`` — for the portal viewer and
    dashboard. Uses the field-icon map; unknown social platforms fall back to the
    generic 'link' icon."""
    icon_map = load_field_icon_map(webapps_root)
    links: list[dict[str, Any]] = []

    def emit(kind: str, value: Any, label: str) -> None:
        v = _as_text(value)
        if not v:
            return
        ref = icon_map.get(kind) or icon_map.get("link", "")
        links.append(
            {
                "kind": kind,
                "label": label,
                "value": v,
                "href": _field_link_href(kind, v),
                "icon_ref": ref,
                "icon_url": (_FIELD_ICON_PREFIX + ref + ".svg") if ref else "",
            }
        )

    for fname, kind in _FIELD_NAME_KIND.items():
        emit(kind, profile.get(fname), _as_text(fname).replace("_", " ").title())
    socials = profile.get("socials")
    if isinstance(socials, list):
        for s in socials:
            if isinstance(s, dict):
                platform = _as_text(s.get("platform")).lower()
                emit(platform or "link", s.get("value"), platform.title() if platform else "Link")
    return links


def resolve_profile_scopes(profile: dict[str, Any], webapps_root: str | Path | None) -> list[dict[str, Any]]:
    """A profile's grantee-scoped EXTRA fields (``scope_fields: {<grantee>: {k: v}}``)
    as one block per grantee scope — for views that should show them (the grantee's own
    site + dashboard), kept OUT of the general FND views. Each block: ``{scope, label,
    fields: [{key,label,value}], links: [field-link…]}`` (contact/social values inside a
    scope block get icons via the field-icon convention). Empty when no scope_fields."""
    raw = profile.get("scope_fields")
    if not isinstance(raw, dict):
        return []
    out: list[dict[str, Any]] = []
    for scope, block in raw.items():
        if not isinstance(block, dict):
            continue
        fields = [
            {"key": _as_text(k), "label": _as_text(k).replace("_", " ").title(), "value": _scalar_str(v)}
            for k, v in block.items()
        ]
        out.append(
            {
                "scope": _as_text(scope),
                "label": _as_text(scope).upper(),
                "fields": fields,
                "links": resolve_field_links(block, webapps_root),
            }
        )
    return out


def _gallery_slug(gallery: str, filename: str) -> str:
    """The organizing slug for a gallery member (profiles use _profile_slug)."""
    if gallery == "profiles":
        return _profile_slug(filename)
    return _asset_descriptor(filename)[0]


def _replace_last_token(stem: str, new_token: str) -> str:
    """Replace the last dot-token of ``stem`` with ``new_token``.

    When ``stem`` has no dot the slug IS the whole stem, so it is replaced
    entirely (``add`` → ``plus``, not ``add.plus``).
    """
    if "." in stem:
        return f"{stem.rsplit('.', 1)[0]}.{new_token}"
    return new_token


def _filename_with_slug(filename: str, gallery: str, new_slug: str) -> str:
    """Return ``filename`` with its slug token swapped for ``new_slug``."""
    name = str(filename)
    if gallery == "profiles":
        if not name.endswith(_PROFILE_SUFFIX):
            return name
        stem = name[: -len(_PROFILE_SUFFIX)]
        return f"{_replace_last_token(stem, new_slug)}{_PROFILE_SUFFIX}"
    stem, _, ext = name.rpartition(".")
    if not stem:  # no extension — the whole name is the slug token
        return new_slug
    return f"{_replace_last_token(stem, new_slug)}.{ext}"


def _gallery_members(gallery_dir: Path, gallery: str, slug: str) -> list[Path]:
    """Files in ``gallery_dir`` whose organizing slug equals ``slug``."""
    out: list[Path] = []
    try:
        children = sorted(gallery_dir.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return out
    for p in children:
        if not p.is_file() or p.name.startswith(".") or ".example." in p.name:
            continue
        if _gallery_slug(gallery, p.name) == slug:
            out.append(p)
    return out


def build_grouped_gallery(
    webapps_root: str | Path | None,
    gallery: str,
    *,
    compute_referenced: bool = True,
) -> dict[str, Any]:
    """A gallery's leaflets grouped by slug (the operator's organizing key).

    Returns ``{gallery, kind, url_prefix, count, groups:[{slug, label, count,
    members:[{filename, asset_path, owner, ext, size_bytes, referenced,
    image_url?, display_name?, subtitle?}]}]}``. Profiles reuse ``list_profiles``
    (rich rows with display_name/image); the binary galleries enumerate the dir.
    Members carry ``referenced`` (in some site manifest) so the library UI can
    gate delete and show usage. Pass ``compute_referenced=False`` to skip the
    all-sites manifest glob when the caller does not need it (e.g. allocation,
    which derives its own per-site ``allocated`` flag).
    """
    gallery = _as_text(gallery)
    meta = _GALLERY_META.get(gallery)
    if meta is None:
        return {"gallery": gallery, "kind": "", "url_prefix": "", "count": 0, "groups": []}
    url_prefix = meta["url_prefix"]
    referenced = (
        manifest_referenced_paths(webapps_root, meta["kind"])
        if compute_referenced
        else set()
    )
    groups: dict[str, list[dict[str, Any]]] = {}

    if gallery == "profiles":
        for row in list_profiles(webapps_root):
            asset_path = url_prefix + _as_text(row.get("filename"))
            groups.setdefault(_as_text(row.get("slug")), []).append(
                {
                    "filename": _as_text(row.get("filename")),
                    "asset_path": asset_path,
                    "owner": _as_text(row.get("entity_scope")),
                    "ext": "yaml",
                    "size_bytes": 0,
                    "referenced": asset_path in referenced,
                    "display_name": _as_text(row.get("display_name")),
                    "subtitle": _as_text(row.get("subtitle")),
                    "image_url": _as_text(row.get("image_url")),
                }
            )
    else:
        gdir = gallery_dir_for(webapps_root, gallery)
        if gdir is not None and gdir.is_dir():
            for p in sorted(gdir.iterdir(), key=lambda x: x.name.lower()):
                if not p.is_file() or p.name.startswith(".") or ".example." in p.name:
                    continue
                slug, owner, ext = _asset_descriptor(p.name)
                asset_path = url_prefix + p.name
                try:
                    size = p.stat().st_size
                except OSError:
                    size = 0
                groups.setdefault(slug, []).append(
                    {
                        "filename": p.name,
                        "asset_path": asset_path,
                        "owner": owner,
                        "ext": ext,
                        "size_bytes": int(size),
                        "referenced": asset_path in referenced,
                        # icons + images are previewable inline by URL.
                        "image_url": asset_path if gallery in ("icon", "image") else "",
                    }
                )

    group_list = [
        {
            "slug": slug,
            "label": slug.replace("_", " ").replace("-", " ").title() or slug,
            "count": len(members),
            "members": members,
        }
        for slug, members in sorted(groups.items())
    ]
    return {
        "gallery": gallery,
        "kind": meta["kind"],
        "url_prefix": url_prefix,
        "count": sum(len(g["members"]) for g in group_list),
        "groups": group_list,
    }


def _profile_site_index(webapps_root: str | Path | None) -> dict[str, list[tuple[str, bool]]]:
    """Reverse index ``slug -> [(site, site_has_network_build)]`` built from every
    site's consolidated manifest ``resources.profile`` section.

    Computed once per ``build_leaflet_index`` call so per-profile usage labels
    don't re-scan every manifest. ``site_has_network_build`` lets the label say
    "network map" vs a plain manifest reference.
    """
    idx: dict[str, list[tuple[str, bool]]] = {}
    if not webapps_root:
        return idx
    pattern = str(
        Path(webapps_root) / "clients" / "*" / "frontend" / "assets"
        / "*.shared_resources.yaml"
    )
    for path in glob.glob(pattern):
        site = Path(path).parts[-4]
        has_build = _site_has_network_build(webapps_root, site)
        data = _load_yaml_mapping(Path(path))
        res = data.get("resources") if isinstance(data.get("resources"), dict) else {}
        for entry in res.get("profile") or []:
            if not isinstance(entry, dict):
                continue
            slug = _as_text(entry.get("asset_id")) or _profile_slug(
                os.path.basename(_as_text(entry.get("asset_path")))
            )
            if slug:
                idx.setdefault(slug, []).append((site, has_build))
    return idx


def _profile_usage_labels(
    *, sites: list[tuple[str, bool]], excerpt_paths: list[Path]
) -> list[str]:
    """Human "in use by" labels from already-computed usage signals.

    De-duped, stable order. Shared by :func:`profile_usage` and
    :func:`build_leaflet_index` so the two never drift. A manifest reference on a
    site that ships a network map reads as "network map"; otherwise as a plain
    manifest reference. Excerpts read as page content.
    """
    labels: list[str] = []
    for site, has_build in sites:
        labels.append(f"{site} (network map /more)" if has_build else f"{site} (site manifest)")
    for p in excerpt_paths:
        parts = p.parts
        site = parts[parts.index("clients") + 1] if "clients" in parts else ""
        if site:
            labels.append(f"{site} (page content)")
    seen: set[str] = set()
    out: list[str] = []
    for label in labels:
        if label not in seen:
            seen.add(label)
            out.append(label)
    return out


def profile_usage(webapps_root: str | Path | None, slug: str) -> list[str]:
    """Human labels for every place a profile slug is consumed by a site.

    Explains why the library refuses to delete an in-use profile: it covers each
    site's consolidated manifest ``resources.profile`` section (which drives the
    network map where present) and per-site derived excerpts — the same signals
    :func:`delete_asset_if_unreferenced` gates on. Empty list = safe to delete.
    """
    if not webapps_root:
        return []
    slug = _as_text(slug)
    if not slug:
        return []
    return _profile_usage_labels(
        sites=_profile_site_index(webapps_root).get(slug, []),
        excerpt_paths=_excerpt_paths_for_slug(webapps_root, slug),
    )


def build_leaflet_index(webapps_root: str | Path | None) -> list[dict[str, Any]]:
    """A single, type-agnostic, flat index of EVERY managed leaflet.

    Flattens all ``MANAGED_GALLERIES`` (reusing ``build_grouped_gallery``) into
    one uniform row list so the Resource view can present every leaflet
    identically and the operator can filter purely by naming convention. Each
    row:
    ``{gallery, kind, filename, slug, owner, entity_type, title, ext,
    asset_path, referenced, in_use, image_url, size_bytes, naming}`` where
    ``entity_type`` is the profile flavor (legal_entity/natural_entity) or "",
    ``in_use`` means a site consumes it (profiles: a derived excerpt or a
    manifest reference; binaries: a manifest reference), and ``naming`` is the
    lowercased substring-filter key. Sorted by (slug, kind, filename).
    """
    # Reverse index slug -> [(site, has_map)] from every consolidated manifest's
    # profile section, computed once and reused for every profile row's in_use_by.
    profile_idx = _profile_site_index(webapps_root)
    rows: list[dict[str, Any]] = []
    for gallery in MANAGED_GALLERIES:
        grouped = build_grouped_gallery(webapps_root, gallery)
        kind = grouped["kind"]
        for group in grouped["groups"]:
            slug = _as_text(group.get("slug"))
            for member in group.get("members", []):
                filename = _as_text(member.get("filename"))
                referenced = bool(member.get("referenced"))
                if gallery == "profiles":
                    entity_type = _profile_entity_flavor(filename)
                    title = _as_text(member.get("display_name")) or slug
                    # One excerpt glob, reused for both in_use and the "where
                    # used" labels (so the detail pane can tell the operator what
                    # to de-allocate before delete becomes available).
                    in_use_by = _profile_usage_labels(
                        sites=profile_idx.get(slug, []),
                        excerpt_paths=_excerpt_paths_for_slug(webapps_root, slug)
                        if webapps_root
                        else [],
                    )
                    in_use = bool(in_use_by)
                else:
                    entity_type = ""
                    title = slug
                    in_use = referenced
                    in_use_by = []
                owner = _as_text(member.get("owner"))
                # The in-slug dash convention: split the slug on its FIRST dash
                # into base + variant (suffix). The variant (e.g. profile_headshot,
                # after, before, mark, monochrome, brochure) is a facet so the
                # operator can group all headshots / before-after pairs / marks.
                base, _, variant = slug.partition("-")
                naming = " ".join(
                    [filename, slug, owner, entity_type, kind, title, variant]
                ).lower()
                rows.append(
                    {
                        "gallery": gallery,
                        "kind": kind,
                        "filename": filename,
                        "slug": slug,
                        "slug_base": base,
                        "slug_variant": variant,
                        "owner": owner,
                        "entity_type": entity_type,
                        "title": title,
                        "ext": _as_text(member.get("ext")),
                        "asset_path": _as_text(member.get("asset_path")),
                        "referenced": referenced,
                        "in_use": in_use,
                        "in_use_by": in_use_by,
                        "image_url": _as_text(member.get("image_url")),
                        "size_bytes": int(member.get("size_bytes") or 0),
                        "naming": naming,
                    }
                )
    rows.sort(key=lambda r: (r["slug"], r["kind"], r["filename"]))
    return rows


def _update_manifests_for_asset(
    webapps_root: str | Path,
    kind: str,
    match_path: str,
    *,
    new_path: str | None = None,
    patch: dict[str, Any] | None = None,
) -> list[str]:
    """Update every consolidated-manifest ``resources[<kind>]`` entry whose
    asset_path == match_path.

    Optionally set ``asset_path=new_path`` and/or merge ``patch`` into the
    entry. Atomic per manifest. Returns the list of manifest paths changed.
    """
    updated: list[str] = []
    kind = _as_text(kind)
    pattern = str(
        Path(webapps_root) / "clients" / "*" / "frontend" / "assets" / "*.shared_resources.yaml"
    )
    for hit in sorted(glob.glob(pattern)):
        manifest_path = Path(hit)
        data = _load_yaml_mapping(manifest_path)
        res = data.get("resources") if isinstance(data.get("resources"), dict) else {}
        entries = res.get(kind)
        if not isinstance(entries, list):
            continue
        changed = False
        for entry in entries:
            if isinstance(entry, dict) and _as_text(entry.get("asset_path")) == match_path:
                if patch:
                    for key, value in patch.items():
                        entry[key] = value
                    changed = True
                if new_path is not None:
                    entry["asset_path"] = new_path
                    changed = True
        if changed:
            text = yaml.safe_dump(
                data, default_flow_style=False, allow_unicode=True, sort_keys=False
            )
            try:
                _atomic_write_text(manifest_path, text)
                updated.append(str(manifest_path))
            except OSError:
                continue
    return updated


def retitle_asset(
    webapps_root: str | Path | None, gallery: str, filename: str, new_asset_id: str
) -> dict[str, Any]:
    """Rename the *title* (not the file) of a gallery member.

    Profiles: set the canonical ``display_name`` (via ``save_profile``) AND
    propagate to the per-site excerpts + owning site (same as the profile-save
    route) so the new title reaches the live page. Binary galleries: rewrite the
    ``asset_id`` of every manifest entry referencing the asset — the file on
    disk is untouched. Returns ``{ok, ...}``.
    """
    gallery = _as_text(gallery)
    meta = _GALLERY_META.get(gallery)
    if meta is None:
        return {"ok": False, "error": "unknown_gallery"}
    new_title = _as_text(new_asset_id)
    if not new_title:
        return {"ok": False, "error": "missing_title"}
    name = os.path.basename(_as_text(filename))
    if not name or name.startswith("."):
        return {"ok": False, "error": "invalid_filename"}
    if gallery == "profiles":
        slug = _profile_slug(name)
        saved = save_profile(webapps_root, slug, {"display_name": new_title})
        if not saved.get("ok"):
            return saved
        propagation = propagate_profile(webapps_root, slug)
        return {"ok": True, "saved": saved, "propagation": propagation, "retitled": name}
    if not webapps_root:
        return {"ok": False, "error": "no_webapps_root"}
    asset_path = meta["url_prefix"] + name
    updated = _update_manifests_for_asset(
        webapps_root, meta["kind"], asset_path, patch={"asset_id": new_title}
    )
    return {"ok": True, "retitled": name, "manifests_updated": updated}


def _replace_slug_token(name: str, old: str, new: str) -> str:
    """Replace the slug token ``old`` with ``new`` in a filename, respecting
    token boundaries (start/end or one of ``.`` ``-`` ``_``) so a mere substring
    is never hit. Works for canonical, profile-excerpt, and operation-excerpt
    filenames alike (the slug always sits between such boundaries)."""
    return re.sub(
        rf"(^|[._-]){re.escape(old)}([.\-]|$)",
        lambda m: f"{m.group(1)}{new}{m.group(2)}",
        name,
    )


def _backup_file(path: Path) -> None:
    """Best-effort ``<name>.bak`` copy before an in-place edit."""
    try:
        Path(str(path) + ".bak").write_bytes(path.read_bytes())
    except OSError:
        pass


def _find_related_referencing(
    webapps_root: str | Path, stem: str, *, exclude: set[str]
) -> list[str]:
    """Canonical + excerpt YAML files (other than ``exclude``) whose text
    contains ``stem`` — i.e. they reference the profile by its filename stem in a
    ``related:`` list. ``stem`` is a long unique string, so a plain containment
    test has no realistic false positives."""
    hits: list[str] = []
    patterns = [
        str(Path(webapps_root) / "clients" / "_shared" / "site-core" / "profiles" / "*.yaml"),
        str(Path(webapps_root) / "clients" / "*" / "frontend" / "assets" / "*.yaml"),
    ]
    for pattern in patterns:
        for f in glob.glob(pattern):
            name = Path(f).name
            # Skip the file itself, templates, and record-manifests (the
            # profile_use manifest's asset_path contains the stem but is handled
            # separately by _update_manifests_for_asset, not as a related-ref).
            if f in exclude or ".example." in name or "record-manifest" in name:
                continue
            try:
                if stem in Path(f).read_text(encoding="utf-8"):
                    hits.append(f)
            except OSError:
                continue
    return sorted(set(hits))


def _find_data_profile_refs(
    webapps_root: str | Path, slug: str
) -> tuple[list[str], list[str]]:
    """Hand-authored ``clients/<domain>/frontend/data/*.json`` files: ones with a
    ``/profile/<slug>`` URL (auto-rewritten) and ones with OTHER ``<slug>``
    occurrences (reported for operator review, not auto-edited)."""
    url = "/profile/" + slug
    with_url: list[str] = []
    other: list[str] = []
    pattern = str(Path(webapps_root) / "clients" / "*" / "frontend" / "data" / "*.json")
    for f in glob.glob(pattern):
        try:
            text = Path(f).read_text(encoding="utf-8")
        except OSError:
            continue
        if url in text:
            with_url.append(f)
        if slug in text.replace(url, ""):
            other.append(f)
    return sorted(with_url), sorted(other)


def _excerpt_is_owned_by_slug(filename: str, slug: str) -> bool:
    """True when ``slug`` is the SUBJECT of this excerpt — not its owner /
    site-entity segment.

    Profile excerpts are ``...profile-<flavor>.<owner>.<slug>-<role>.yaml`` (the
    slug sits immediately before ``-<role>``); operation excerpts are
    ``...profile-operation.<slug>.<op>.yaml`` (slug right after the marker). The
    org/site-entity slug appears only in the ``<owner>`` segment (followed by a
    dot), so it is NOT owned by this test — which is what stops a cascade rename
    of an org profile from clobbering every farm/board excerpt it merely owns.
    """
    name = str(filename)
    if ".profile-operation." in name:
        after = name.split(".profile-operation.", 1)[1]
        return after.split(".", 1)[0] == slug
    return re.search(rf"(?:^|[.]){re.escape(slug)}-", name) is not None


def _owner_link_files(webapps_root: str | Path, slug: str) -> list[Path]:
    """Event leaflets that link a profile via their internal ``owner:`` slug.
    The related-ref scan keys on the canonical filename STEM, so these (which
    name the profile only by its slug) are otherwise missed by a rename."""
    out: list[Path] = []
    root = Path(webapps_root) / "clients" / "_shared" / "site-core" / "event"
    if not root.is_dir():
        return out
    for p in sorted(root.glob("*.yaml")):
        if _as_text(_load_yaml_mapping(p).get("owner")) == slug:
            out.append(p)
    return out


def _rewrite_owner_links(
    webapps_root: str | Path, old_slug: str, new_slug: str
) -> list[dict[str, str]]:
    """Repoint event leaflets owned by a renamed profile: rewrite the ``owner:``
    field and the filename slug token (collision-guarded). Returns a per-file
    change list. Without this a profile rename orphans the farm's market-event
    pins (events resolve their profile via ``owner``, not the canonical stem)."""
    changes: list[dict[str, str]] = []
    for p in _owner_link_files(webapps_root, old_slug):
        data = _load_yaml_mapping(p)
        data["owner"] = new_slug
        new_path = p.parent / _replace_slug_token(p.name, old_slug, new_slug)
        if new_path != p and new_path.exists():
            changes.append({"old": str(p), "skipped": "collision"})
            continue
        _backup_file(p)
        _atomic_write_text(
            p, yaml.safe_dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        )
        if new_path != p:
            os.replace(str(p), str(new_path))
        changes.append({"old": str(p), "new": str(new_path)})
    return changes


def cascade_rename_profile_slug(
    webapps_root: str | Path | None,
    old_slug: str,
    new_slug: str,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    """Rename a profile's slug across EVERY reference (in-use safe).

    Runs a discovery pass always; mutates only when ``apply=True``, with ``.bak``
    backups + atomic writes and a collision guard. Returns
    ``{ok, report}`` where ``report`` lists the change-set (so the UI can preview
    it before applying), or ``{ok: False, error, detail}`` on a guard failure.

    Reference classes (see the profile-rename reference map): canonical file,
    per-site profile + operation excerpts, ``related:`` cross-refs in other
    profiles/excerpts, FND network ``profile_refs``, ``profile_use`` manifests,
    hand-authored ``/profile/<slug>`` URLs, then ``propagate_profile`` re-derives
    excerpts + rebuilds sites + regenerates the FND map dataset.
    """
    old_slug = _as_text(old_slug)
    new_slug = _as_text(new_slug)
    report: dict[str, Any] = {
        "old_slug": old_slug,
        "new_slug": new_slug,
        "applied": False,
        "canonical": None,
        "excerpts": [],
        "related": [],
        "profile_use": [],
        "fnd_network": False,
        "data_files": [],
        "data_other": [],
        "owner_links": [],
        "sites": [],
    }
    if not webapps_root:
        return {"ok": False, "error": "no_webapps_root"}
    if not old_slug or not new_slug:
        return {"ok": False, "error": "missing_slug"}
    if not _SLUG_RE.match(new_slug):
        return {"ok": False, "error": "invalid_new_slug"}
    if old_slug == new_slug:
        return {"ok": True, "report": report, "note": "no_change"}
    profiles_dir = _profiles_dir(webapps_root)
    canonical = _resolve_profile_path(profiles_dir, old_slug) if profiles_dir else None
    if canonical is None:
        return {"ok": False, "error": "profile_not_found"}
    if _resolve_profile_path(profiles_dir, new_slug) is not None:
        return {"ok": False, "error": "collision", "detail": new_slug}

    new_canonical_name = _replace_slug_token(canonical.name, old_slug, new_slug)
    # Direct filename collision — guards the case where the canonical resolver
    # returns None on an AMBIGUOUS new_slug (0-or-many) yet the target file
    # already exists on disk.
    if (canonical.parent / new_canonical_name).exists():
        return {"ok": False, "error": "collision", "detail": new_canonical_name}
    report["canonical"] = {"old": canonical.name, "new": new_canonical_name}

    # Excerpts: keep ONLY those this profile is the SUBJECT of. A slug that also
    # appears as the OWNER/site-entity segment of OTHER profiles' excerpts (an
    # org profile) must NOT be renamed here — that would rewrite the owner token
    # of every excerpt it owns. Refuse such a rename outright.
    all_excerpts = _excerpt_paths_for_slug(webapps_root, old_slug)
    owned = [p for p in all_excerpts if _excerpt_is_owned_by_slug(p.name, old_slug)]
    owner_only = [p for p in all_excerpts if p not in owned]
    if owner_only:
        return {
            "ok": False,
            "error": "site_entity_slug",
            "detail": (
                "this slug names a site entity that owns other profiles' "
                "excerpts; renaming it here is not supported"
            ),
            "owned_count": len(owned),
            "owner_count": len(owner_only),
        }
    excerpt_plan: list[tuple[Path, Path]] = []
    for ex in owned:
        new_ex = ex.parent / _replace_slug_token(ex.name, old_slug, new_slug)
        if new_ex != ex and new_ex.exists():
            return {"ok": False, "error": "collision", "detail": new_ex.name}
        excerpt_plan.append((ex, new_ex))
        report["excerpts"].append({"old": str(ex), "new": str(new_ex)})

    old_stem = canonical.name[: -len(".yaml")]
    new_stem = new_canonical_name[: -len(".yaml")]
    exclude = {str(canonical)} | {str(ex) for ex, _ in excerpt_plan}
    related_files = _find_related_referencing(webapps_root, old_stem, exclude=exclude)
    report["related"] = related_files

    # Does this profile feed a network map? (= listed in a mapped site's
    # consolidated manifest profile section.) Informational + decides the regen.
    report["fnd_network"] = any(
        _site_has_network_build(webapps_root, s)
        for s in _sites_using_profile(webapps_root, old_slug)
    )

    old_asset = "/assets/profiles/" + canonical.name
    new_asset = "/assets/profiles/" + new_canonical_name

    data_files, data_other = _find_data_profile_refs(webapps_root, old_slug)
    report["data_files"] = data_files
    report["data_other"] = data_other
    report["owner_links"] = [str(p) for p in _owner_link_files(webapps_root, old_slug)]
    report["sites"] = sorted({str(ex.parent.parent) for ex, _ in excerpt_plan})

    if not apply:
        return {"ok": True, "report": report}

    # ---- APPLY (backups on edits; renames recorded in the report). Best-effort
    # atomic: discovery + collision checks ran above, so the remaining work is
    # mechanical. A mid-way failure is surfaced (with the partial report) rather
    # than silently swallowed; full rollback is intentionally out of scope. ----
    try:
        for ex, new_ex in excerpt_plan:
            if new_ex != ex:
                os.replace(str(ex), str(new_ex))
            # Operation excerpts carry an internal ``entity_slug`` field that
            # derive_profile_excerpt cannot repair (the canonical does not define
            # it) — rewrite it to the new slug.
            if ".profile-operation." in new_ex.name:
                op = _load_yaml_mapping(new_ex)
                if _as_text(op.get("entity_slug")) == old_slug:
                    op["entity_slug"] = new_slug
                    _atomic_write_text(
                        new_ex,
                        yaml.safe_dump(
                            op, default_flow_style=False, allow_unicode=True, sort_keys=False
                        ),
                    )
        for rel in related_files:
            p = Path(rel)
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            if old_stem in text:
                _backup_file(p)
                _atomic_write_text(p, text.replace(old_stem, new_stem))
        # The profile lives in each site's consolidated manifest profile section
        # (which drives the map where present), so repointing that entry's
        # asset_path + asset_id is all that's needed — the obsolete site-JSON
        # ``profile_refs`` rewrite is gone. The map dataset is regenerated by the
        # propagate_profile call below (new_slug now in the section).
        report["profile_use"] = _update_manifests_for_asset(
            webapps_root, "profile", old_asset, new_path=new_asset,
            patch={"asset_id": new_slug},
        )
        for df in data_files:
            p = Path(df)
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            # Bound the slug at a URL delimiter so a prefix-sibling slug is not
            # clobbered (old_slug "dan" must not rewrite "/profile/dan_white").
            new_text = re.sub(
                rf"(/profile/){re.escape(old_slug)}(?=[\"'/?#\s]|$)",
                lambda m: m.group(1) + new_slug,
                text,
            )
            if new_text != text:
                _backup_file(p)
                _atomic_write_text(p, new_text)
        # Event leaflets link a profile via their internal ``owner:`` slug (not
        # the canonical stem), so the related-ref scan misses them — repoint them
        # or the rename orphans the farm's market-event pins (O5).
        report["owner_links"] = _rewrite_owner_links(webapps_root, old_slug, new_slug)
        # Move the canonical file LAST (before propagate, which resolves by the
        # new slug): a mid-cascade failure then leaves the profile reachable at
        # the OLD name with referrers consistent instead of orphaned (O6).
        os.replace(str(canonical), str(canonical.parent / new_canonical_name))
        # Re-derive the (now new-named) excerpts + rebuild owning sites +
        # regenerate the FND map dataset (new_slug is now in the FND refs).
        report["propagation"] = propagate_profile(webapps_root, new_slug)
    except OSError as exc:
        return {"ok": False, "error": "apply_failed", "detail": str(exc), "report": report}
    report["applied"] = True
    return {"ok": True, "report": report}


def rename_slug(
    webapps_root: str | Path | None, gallery: str, old_slug: str, new_slug: str
) -> dict[str, Any]:
    """Rename a slug group: rename its file(s) on disk and repoint every
    manifest entry. Refuses on a name collision. Profiles route through
    :func:`cascade_rename_profile_slug` (in-use safe).
    """
    gallery = _as_text(gallery)
    meta = _GALLERY_META.get(gallery)
    if meta is None:
        return {"ok": False, "error": "unknown_gallery"}
    gdir = gallery_dir_for(webapps_root, gallery)
    if gdir is None or not gdir.is_dir():
        return {"ok": False, "error": "no_gallery_dir"}
    old_slug = _as_text(old_slug)
    new_slug = _as_text(new_slug)
    if not old_slug or not new_slug:
        return {"ok": False, "error": "missing_slug"}
    if not _SLUG_RE.match(new_slug):
        return {"ok": False, "error": "invalid_new_slug"}
    if old_slug == new_slug:
        return {"ok": True, "renamed": [], "note": "no_change"}
    if gallery == "profiles":
        # Profile slug renames CASCADE through the canonical file, every per-site
        # excerpt, profile_use manifests, the FND network refs, related-refs, and
        # hand-authored profile-URL refs, then rebuild the owning sites.
        return cascade_rename_profile_slug(
            webapps_root, old_slug, new_slug, apply=True
        )
    members = _gallery_members(gdir, gallery, old_slug)
    if not members:
        return {"ok": False, "error": "slug_not_found"}
    # Plan + collision-check before any mutation.
    plan: list[tuple[Path, Path, str]] = []
    for src in members:
        new_name = _filename_with_slug(src.name, gallery, new_slug)
        dst = gdir / new_name
        if dst.exists():
            return {"ok": False, "error": "collision", "detail": new_name}
        plan.append((src, dst, new_name))
    renamed: list[str] = []
    for src, dst, new_name in plan:
        old_path = meta["url_prefix"] + src.name
        new_path = meta["url_prefix"] + new_name
        try:
            os.replace(str(src), str(dst))
        except OSError as exc:
            return {
                "ok": False,
                "error": "rename_failed",
                "detail": str(exc),
                "renamed": renamed,
            }
        if webapps_root:
            _update_manifests_for_asset(
                webapps_root, meta["kind"], old_path, new_path=new_path
            )
        renamed.append(new_name)
    return {"ok": True, "renamed": renamed}


def delete_asset_if_unreferenced(
    webapps_root: str | Path | None, gallery: str, filename: str
) -> dict[str, Any]:
    """Delete a single gallery file ONLY when no site manifest references it
    (and, for profiles, no per-site derived excerpt exists). Refuses otherwise —
    never deletes an asset a live site is using.
    """
    gallery = _as_text(gallery)
    meta = _GALLERY_META.get(gallery)
    if meta is None:
        return {"ok": False, "error": "unknown_gallery"}
    gdir = gallery_dir_for(webapps_root, gallery)
    if gdir is None:
        return {"ok": False, "error": "no_webapps_root"}
    name = os.path.basename(_as_text(filename))
    if not name or name.startswith("."):
        return {"ok": False, "error": "invalid_filename"}
    target = gdir / name
    if not target.is_file():
        return {"ok": False, "error": "not_found"}
    asset_path = meta["url_prefix"] + name
    if asset_path in manifest_referenced_paths(webapps_root, meta["kind"]):
        return {"ok": False, "error": "referenced"}
    if gallery == "profiles":
        pslug = _profile_slug(name)
        # A profile is "in use" if a site has a derived excerpt. (Manifest
        # references — including a site's network-map profile section — are
        # already caught by the manifest_referenced_paths check above.)
        if _excerpt_paths_for_slug(webapps_root, pslug):
            return {"ok": False, "error": "referenced"}
    try:
        target.unlink()
    except OSError as exc:
        return {"ok": False, "error": "delete_failed", "detail": str(exc)}
    return {"ok": True, "removed": name}


# --------------------------------------------------------------------------- #
# events detail (read-only operator view) — reuses utilities_extensions.events
# --------------------------------------------------------------------------- #
def _customer_name(row: dict[str, Any]) -> str:
    """Best-effort customer display name from a job-kind event leaflet.

    The job extras nest the customer under ``customer.name``; fall back to
    first/last name parts, then "".
    """
    customer = row.get("customer") if isinstance(row.get("customer"), dict) else {}
    name = _as_text(customer.get("name"))
    if name:
        return name
    parts = [
        _as_text(customer.get("first_name")),
        _as_text(customer.get("last_name")),
    ]
    return " ".join(p for p in parts if p)


def _event_total(row: dict[str, Any]) -> float:
    pricing = row.get("pricing") if isinstance(row.get("pricing"), dict) else {}
    try:
        return float(pricing.get("total") or 0)
    except (TypeError, ValueError):
        return 0.0


def events_detail(webapps_root: str | Path | None) -> dict[str, Any]:
    """Formatted, read-only operator view of every event leaflet.

    Reuses ``list_events`` (all clients — operator scope) + ``events_summary``.
    Returns ``{rows, summary, count}`` where each row is a flat, display-ready
    dict (``date · client · title · status · customer · total``). The total is
    rounded to whole dollars-and-cents for display; the raw revenue KPIs come
    from ``events_summary``. Tolerant of a missing gallery (returns empty).
    """
    from MyCiteV2.instances._shared.runtime.utilities_extensions.events import (
        events_summary,
        list_events,
    )

    if not webapps_root:
        return {"rows": [], "summary": events_summary([]), "count": 0}
    raw = list_events(webapps_root)
    rows: list[dict[str, Any]] = []
    for row in raw:
        rows.append(
            {
                "id": _as_text(row.get("id")),
                "date": _as_text(row.get("date")),
                "client": _as_text(row.get("client")),
                "title": _as_text(row.get("title")),
                "status": _as_text(row.get("status")) or "unknown",
                "location": _as_text(row.get("location")),
                "customer": _customer_name(row),
                "total": round(_event_total(row), 2),
            }
        )
    return {"rows": rows, "summary": events_summary(raw), "count": len(rows)}


# --------------------------------------------------------------------------- #
# contacts detail (read-only operator view) — reuses contact_leaflet adapter
# --------------------------------------------------------------------------- #
_CONTACTS_REL = (*_SITE_CORE_REL, "contacts")
_CONTACTS_SUFFIX = ".contacts.yaml"


def _contacts_dir(webapps_root: str | Path | None) -> Path | None:
    if not webapps_root:
        return None
    return Path(webapps_root).joinpath(*_CONTACTS_REL)


def _contact_entity_slug(filename: str) -> str:
    """Extract the entity slug from a contacts leaflet filename.

    ``0000-00-00.record-data.<entity>.contacts.yaml`` → ``<entity>``. The
    entity token may itself contain dots? No — entity slugs are
    underscore-joined, so the token between ``record-data.`` and
    ``.contacts.yaml`` is the entity.
    """
    name = str(filename)
    if name.endswith(_CONTACTS_SUFFIX):
        name = name[: -len(_CONTACTS_SUFFIX)]
    # Strip the leading "<date>.record-data." prefix if present, else fall
    # back to the last dot-token.
    marker = ".record-data."
    idx = name.find(marker)
    if idx != -1:
        return name[idx + len(marker):]
    return name.rsplit(".", 1)[-1]


def _entity_label(slug: str) -> str:
    return slug.replace("_", " ").title()


def _contact_display_name(contact: dict[str, Any]) -> str:
    parts = [
        _as_text(contact.get("first_name")),
        _as_text(contact.get("middle_name")),
        _as_text(contact.get("last_name")),
    ]
    name = " ".join(p for p in parts if p)
    return name or _as_text(contact.get("email"))


def contacts_detail(webapps_root: str | Path | None) -> dict[str, Any]:
    """Formatted, read-only operator view of every per-entity contact roster.

    Enumerates ``*.contacts.yaml`` leaflets under the contacts gallery (skips
    dotfiles + ``.example.`` templates), loads each via the contact-leaflet
    adapter (``load_roster``), and groups the rows by entity. Each contact row
    is flattened to ``name · email · phone · subscribed · organization`` for
    the operator table. Returns ``{entities, total_contacts}``.
    """
    from MyCiteV2.packages.adapters.filesystem.contact_leaflet import load_roster

    contacts_dir = _contacts_dir(webapps_root)
    if contacts_dir is None or not contacts_dir.is_dir():
        return {"entities": [], "total_contacts": 0}
    entities: list[dict[str, Any]] = []
    total = 0
    for path in sorted(contacts_dir.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file() or not path.name.endswith(_CONTACTS_SUFFIX):
            continue
        if path.name.startswith(".") or ".example." in path.name:
            continue
        slug = _contact_entity_slug(path.name)
        if not slug:
            continue
        # The adapter derives webapps_root from private_dir in the live layout;
        # here we pass webapps_root explicitly so the contacts dir resolves to
        # the same gallery we enumerated. private_dir is required by the
        # signature but unused for resolution when webapps_root is given.
        roster = load_roster(
            slug, private_dir=webapps_root, webapps_root=webapps_root
        )
        rows = [
            {
                "name": _contact_display_name(c),
                "email": _as_text(c.get("email")),
                "phone": _as_text(c.get("phone")),
                "subscribed": bool(c.get("subscribed")),
                "organization": _as_text(c.get("organization")),
                "domain": _as_text(c.get("domain")),
            }
            for c in roster
        ]
        total += len(rows)
        entities.append(
            {
                "entity": slug,
                "label": _entity_label(slug),
                "count": len(rows),
                "contacts": rows,
            }
        )
    return {"entities": entities, "total_contacts": total}


def custom_detail(webapps_root: str | Path | None, client: str | None = None) -> dict[str, Any]:
    """Read-only view of ``artifact-custom`` residual leaflets, optionally scoped
    to a ``client`` (owner). These carry PII (BPW job residuals), so callers MUST
    scope at the route — the dashboard CUSTOM subtab passes the grantee slug.
    Returns ``{rows, count}`` where each row flattens the residual job data
    (event_ref · services · total · paid · notes)."""
    root = _site_core_root(webapps_root)
    if root is None:
        return {"rows": [], "count": 0}
    cdir = root / "custom"
    if not cdir.is_dir():
        return {"rows": [], "count": 0}
    want = _as_text(client).strip().lower() if client else None
    rows: list[dict[str, Any]] = []
    for path in sorted(cdir.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file() or not path.name.endswith(".yaml"):
            continue
        if path.name.startswith(".") or ".example." in path.name:
            continue
        doc = _load_yaml_mapping(path)
        owner = _as_text(doc.get("owner")).strip().lower()
        if want and owner != want:
            continue
        pricing = doc.get("pricing") if isinstance(doc.get("pricing"), dict) else {}
        tags = doc.get("tags") if isinstance(doc.get("tags"), list) else []
        rows.append(
            {
                "file": path.name,
                "event_ref": _as_text(doc.get("event_ref")),
                "services": ", ".join(
                    _as_text(t.get("type")) for t in tags
                    if isinstance(t, dict) and t.get("type")
                ),
                "total": pricing.get("total"),
                "paid": bool(pricing.get("paid")),
                "notes": _as_text(doc.get("notes")),
            }
        )
    return {"rows": rows, "count": len(rows)}


# --------------------------------------------------------------------------- #
# extension renderer — GLOBAL (Library) vs PER-GRANTEE (Allocation)
# --------------------------------------------------------------------------- #
def _resources_library_payload(webapps_root: str | Path | None) -> dict[str, Any]:
    """GLOBAL mode: the shared Resource LIBRARY as ONE uniform, type-agnostic
    leaflet index.

    No per-type differentiation: every leaflet (profile/icon/image/document/
    audio) is a uniform row in a single flat list (``build_leaflet_index``),
    the operator filters purely by naming convention, and opening a row shows
    its detail (profiles editable via the existing routes, binaries metadata).
    Carries only the uniform management route hints + upload. The allocation
    (add-to-manifest) affordance lives only in per-grantee mode.
    """
    return {
        "resources_app": True,
        "resources_mode": "library",
        "leaflets": build_leaflet_index(webapps_root),
        "image_url_prefix": _IMAGE_URL_PREFIX,
        "upload_action": {"route": "/portal/api/resources/upload", "method": "POST"},
        "profile_detail_route": "/__fnd/resources/profile/detail",
        "profile_save_route": "/__fnd/resources/profile/save",
        "retitle_route": "/__fnd/resources/asset/retitle",
        "rename_slug_route": "/__fnd/resources/asset/rename-slug",
        "rename_preview_route": "/__fnd/resources/asset/rename-preview",
        "delete_route": "/__fnd/resources/asset/delete",
        "leaflets_route": "/__fnd/resources/leaflets",
    }


def _resources_allocation_payload(ctx: dict[str, Any]) -> dict[str, Any]:
    """PER-GRANTEE mode: allocate library leaflets onto the selected grantee's
    site manifests.

    For the selected grantee's site (``ctx["domain"]`` → ``clients/<domain>/``),
    list, per managed resource type, which leaflets are currently "used" (in
    that type's ``*_use.yaml`` manifest) with remove affordances, plus the
    candidate leaflets (the library, grouped by slug) to add from. Reuses
    ``site_manifest_entries`` + ``build_grouped_gallery``. Carries the add +
    remove route hints.
    """
    webapps_root = ctx.get("webapps_root")
    grantee = ctx.get("grantee") if isinstance(ctx.get("grantee"), dict) else {}
    domain = _as_text(ctx.get("domain"))
    site = os.path.basename(domain)
    site_exists = bool(site) and (
        Path(webapps_root) / "clients" / site / "frontend" / "assets"
    ).is_dir() if webapps_root else False

    allocations: list[dict[str, Any]] = []
    for gallery in MANAGED_GALLERIES:
        kind = manifest_kind_for(gallery)
        # Allocation derives its own per-site ``allocated`` flag from
        # ``used_paths`` below, so skip the all-sites ``referenced`` glob. Every
        # kind (profiles included) reads from the site's consolidated manifest
        # ``resources[kind]`` section — for a mapped site the profile section IS
        # the /more network map, so Add/Remove there add/remove map farms.
        grouped = build_grouped_gallery(
            webapps_root, gallery, compute_referenced=False
        )
        used = site_manifest_entries(webapps_root, site, kind)
        used_paths = {e["asset_path"] for e in used}
        candidates = [
            {
                "filename": m["filename"],
                "asset_path": m["asset_path"],
                "asset_id": m.get("display_name") or _gallery_slug(gallery, m["filename"]),
                "slug": _gallery_slug(gallery, m["filename"]),
                "allocated": m["asset_path"] in used_paths,
                "image_url": m.get("image_url", ""),
            }
            for group in grouped["groups"]
            for m in group["members"]
        ]
        allocations.append(
            {
                "gallery": gallery,
                "kind": kind,
                "url_prefix": asset_url_prefix_for(gallery),
                "used": used,
                "used_count": len(used),
                "candidates": candidates,
            }
        )

    return {
        "resources_app": True,
        "resources_mode": "allocation",
        "grantee_msn_id": _as_text(grantee.get("msn_id")),
        "grantee_label": _as_text(grantee.get("label")) or _as_text(grantee.get("msn_id")),
        "site": site,
        "domain": domain,
        "site_exists": site_exists,
        "allocations": allocations,
        "manifest_add_route": "/__fnd/resources/manifest/add",
        "manifest_remove_route": "/__fnd/resources/manifest/remove",
    }


# --------------------------------------------------------------------------- #
# Type-browser subtabs (Manifest / Browse / Per-grantee). Reuse resource_types
# for the type registry + by-type index. Icon sprite/asset URLs are served by
# the existing /assets/icons/ nginx alias (snippets/shared-assets.conf).
# resource_types imports helpers FROM this module, so import it LAZILY here to
# avoid an import cycle.
# --------------------------------------------------------------------------- #
_ICON_SPRITE_HREF = "/assets/icons/0000-00-00.artifact-icon.mycite-ui.sprite.svg"
_ICON_URL_PREFIX = "/assets/icons/"

# Browse drill-down (hierarchy → directory → instance) rides the shell-reload
# mechanism via surface_query (browse_view/browse_type/browse_instance), so the
# only fetch endpoints are the icon picker + the icon-edit mutation.
_RESOURCES_TYPE_ROUTES = {
    "set_icon_ref_route": "/__fnd/resources/manifest/set-icon-ref",
    "icon_options_route": "/__fnd/resources/icon-options",
}


def _resources_nav_base_query(ctx: dict[str, Any], subtab: str) -> dict[str, str]:
    """The pinned surface_query keys every Resources nav action must carry so a
    drill-down / reload stays on this extension + subtab + grantee + mode. The JS
    merges its per-action patch onto this; the runtime envelope does NOT expose
    surface_query (only surface_id), so it must be stamped server-side."""
    sq = ctx.get("surface_query") if isinstance(ctx.get("surface_query"), dict) else {}
    return {
        "selected_extension_tool_id": "ext_resources",
        "extension_subtab": subtab,
        "selected_grantee_msn": _as_text(sq.get("selected_grantee_msn")),
        "utilities_mode": _as_text(ctx.get("mode")) or "grantee",
    }


def _resources_browse_instance(
    webapps_root: str | Path | None, full_type: str, asset_path: str, *, include_pii: bool
) -> dict[str, Any]:
    """Resolve a chosen leaflet to its viewer payload (profile editor / asset
    preview / generic structured view), per the type→viewer routing."""
    from . import resource_types as rt

    fname = _as_text(asset_path).rsplit("/", 1)[-1]
    # Resolve the viewer from the OPENED leaflet's OWN type (parsed from its
    # filename) — NOT the directory node, whose token mis-routes when it is a
    # roll-up/root (e.g. an icon opened from the `artifact` directory must use the
    # asset preview, not the generic viewer). browse_type stays for the back-link.
    actual_type = rt.parse_leaflet_type(fname) or full_type
    viewer = _as_text(rt.resolve_instance_viewer(actual_type).get("viewer")) or "generic"
    if viewer == "profile":
        slug = _profile_slug(fname)
        return {"viewer": "profile", "slug": slug, "detail": profile_detail(webapps_root, slug) or {}}
    if viewer == "asset":
        for row in rt.leaflets_for_type(webapps_root, actual_type, include_pii=include_pii):
            if _as_text(row.get("filename")) == fname:
                return {"viewer": "asset", "detail": row}
        return {"viewer": "asset", "detail": {"filename": fname, "asset_path": asset_path}}
    # analytics / event / generic → read-only structured view (deep-linking the
    # full analytics/event editors is a follow-up).
    detail = rt.structured_leaflet_view(webapps_root, actual_type, asset_path, include_pii=include_pii)
    return {"viewer": "generic", "detail": detail or {"filename": fname}}


def _resources_browse_payload(ctx: dict[str, Any]) -> dict[str, Any]:
    """Browse subtab: hierarchy → directory → instance (keyed by browse_view).
    PII types (event/custom/contacts) are NEVER listed here — they are managed
    grantee-scoped via the Per-grantee subtab + dashboard, so a cross-grantee
    Browse can't leak them. (Owner-scoped PII browse is a follow-up.)"""
    from . import resource_types as rt

    webapps_root = ctx.get("webapps_root")
    include_pii = False
    view = _as_text(ctx.get("browse_view")) or "hierarchy"
    browse_type = _as_text(ctx.get("browse_type"))
    base: dict[str, Any] = {
        "resources_app": True,
        "resources_subtab": "browse",
        "sprite_href": _ICON_SPRITE_HREF,
        "icon_url_prefix": _ICON_URL_PREFIX,
        "browse_view": view,
        "nav_base_query": _resources_nav_base_query(ctx, "browse"),
        # In-browse profile view/edit reuses the library's detail+save endpoints
        # (the instance viewer renders the edit_frame + posts a save → propagate).
        "profile_detail_route": "/__fnd/resources/profile/detail",
        "profile_save_route": "/__fnd/resources/profile/save",
        **_RESOURCES_TYPE_ROUTES,
    }
    nodes_by_slug = {n["full_slug"]: n for n in rt.flatten_type_tree(webapps_root)}
    if view == "instance" and browse_type:
        base["browse_type"] = browse_type
        base["type_label"] = _as_text(nodes_by_slug.get(browse_type, {}).get("label")) or browse_type
        base["instance"] = _resources_browse_instance(
            webapps_root, browse_type, _as_text(ctx.get("browse_instance")), include_pii=include_pii
        )
        return base
    if view == "directory" and browse_type:
        node = nodes_by_slug.get(browse_type, {})
        base["browse_type"] = browse_type
        base["type_label"] = _as_text(node.get("label")) or browse_type
        base["leaflets"] = rt.leaflets_for_type(
            webapps_root, browse_type, include_subtypes=True, include_pii=include_pii
        )
        # Profiles arrive image-less (typed by filename only) — resolve each one's
        # logo/headshot once so the instance list shows a thumbnail, not just a dot.
        attach_profile_thumbnails(webapps_root, base["leaflets"])
        base["subtypes"] = [
            nodes_by_slug[c] for c in node.get("child_slugs", []) if c in nodes_by_slug
        ]
        return base
    # hierarchy (default + fall-through when browse_type is missing): force
    # browse_view to match the data shape so the JS renders the right branch.
    base["browse_view"] = "hierarchy"
    # Show EVERY on-disk leaflet type, not just the manifest-registered ones, so
    # icons/images/documents/audio/… and any unregistered subtype are visible and
    # browsable (the old code listed only registered nodes → those types vanished
    # into a parent's rollup). complete_type_nodes synthesizes the missing nodes.
    base["nodes"] = rt.complete_type_nodes(webapps_root, include_pii=include_pii)
    # Every on-disk type is now its own node, so nothing is left in "Other".
    base["other_count"] = 0
    return base


def _resources_per_grantee_payload(ctx: dict[str, Any]) -> dict[str, Any]:
    """Per-grantee subtab: the existing allocation view for the grantee chosen in
    the top selector, or a prompt to pick one."""
    grantee = ctx.get("grantee") if isinstance(ctx.get("grantee"), dict) else {}
    if _as_text(ctx.get("mode")) == "grantee" and _as_text(grantee.get("msn_id")):
        payload = _resources_allocation_payload(ctx)
        payload["resources_subtab"] = "per_grantee"
        return payload
    return {
        "resources_app": True,
        "resources_subtab": "per_grantee",
        "per_grantee_prompt": (
            "Select a grantee to manage the leaflets allocated to its site."
        ),
    }


def _render_ext_resources(ctx: dict[str, Any]) -> dict[str, Any]:
    """Render the resources extension card payload.

    The Extensions surface threads an ``extension_subtab`` into ctx → dispatch to
    the type-browser subtabs (Manifest default / Browse / Per-grantee). Legacy
    direct callers (tests, non-surface paths) that DON'T thread the key keep the
    original library/allocation behavior, so nothing regresses.
    """
    if "extension_subtab" not in ctx:
        grantee = ctx.get("grantee") if isinstance(ctx.get("grantee"), dict) else {}
        if _as_text(ctx.get("mode")) == "grantee" and _as_text(grantee.get("msn_id")):
            return _resources_allocation_payload(ctx)
        return _resources_library_payload(ctx.get("webapps_root"))
    subtab = _as_text(ctx.get("extension_subtab")) or "browse"
    if subtab == "per_grantee":
        return _resources_per_grantee_payload(ctx)
    if subtab == "create":
        # The two-pane LIBRARY view: upload form (incl. the logo kind) + the
        # flat searchable leaflet list with retitle / rename-slug / delete /
        # icon-dedup. Folding Manifest into Browse had orphaned this payload
        # from the surface (it set extension_subtab, so the legacy keyless
        # path that reached it never fired); the Create subtab restores it.
        return _resources_library_payload(ctx.get("webapps_root"))
    # "browse" (and any legacy "manifest" link) → the UNIFIED type tab.
    return _resources_browse_payload(ctx)


__all__ = [
    "MANAGED_GALLERIES",
    "_render_ext_resources",
    "add_asset_to_manifest",
    "asset_url_prefix_for",
    "build_grouped_gallery",
    "build_leaflet_index",
    "build_profile_edit_frame",
    "cascade_rename_profile_slug",
    "contacts_detail",
    "custom_detail",
    "delete_asset_if_unreferenced",
    "derive_profile_excerpt",
    "events_detail",
    "gallery_dir_for",
    "grantee_profiles",
    "icon_duplicate_groups",
    "list_profiles",
    "manifest_kind_for",
    "manifest_referenced_paths",
    "profile_detail",
    "profile_usage",
    "propagate_profile",
    "remove_asset_from_manifest",
    "remove_icon_duplicate",
    "rename_slug",
    "resolve_profile_image",
    "retitle_asset",
    "save_profile",
    "site_manifest_entries",
]
