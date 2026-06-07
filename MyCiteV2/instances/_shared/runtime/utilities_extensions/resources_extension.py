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
import tempfile
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


def _atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically (temp file + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".yaml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# --------------------------------------------------------------------------- #
# image resolution — "assumed logo if present"
# --------------------------------------------------------------------------- #
def resolve_profile_image(
    profile: dict[str, Any], slug: str, image_gallery_dir: Path | None
) -> str:
    """Resolve a profile's display image URL, or "" when none is found.

    Order:
      1. explicit ``image_ref`` / ``logo_ref`` → /assets/images/<ref>.avif
      2. a gallery file whose name contains the slug AND a role token
         (logo / primary_mark / headshot / profile_headshot / brand-mark)
      3. "" (the UI renders a neutral placeholder).
    """
    for key in ("image_ref", "logo_ref"):
        ref = _as_text(profile.get(key))
        if ref:
            # refs are stored without the .avif extension by convention.
            if ref.lower().endswith((".avif", ".png", ".jpg", ".jpeg", ".svg")):
                return _IMAGE_URL_PREFIX + ref
            return _IMAGE_URL_PREFIX + ref + ".avif"
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
    fields = []
    for key in profile:
        value = _scalar_str(profile.get(key))
        # entity_type now holds a NAICS code — annotate with its title.
        if key == "entity_type" and value:
            title = _naics_title(value)
            if title and title != value:
                value = f"{value} — {title}"
        fields.append({
            "key": key,
            "label": "NAICS Code" if key == "entity_type" else str(key).replace("_", " ").title(),
            "value": value,
        })
    return {
        "slug": slug,
        "filename": path.name,
        "display_name": _profile_display_name(profile, slug),
        "image_url": resolve_profile_image(profile, slug, image_dir),
        "fields": fields,
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
    # The FND agricultural-network MAP renders from a pre-generated dataset, not
    # from excerpts — so a profile that feeds the map needs the dataset
    # regenerated separately. Best-effort: only runs when the slug is one of the
    # FND network's profile_refs.
    if rebuild:
        ok, note = _regenerate_fnd_network_dataset(webapps_root, slug)
        if note:
            result["fnd_network"] = note
        if not ok and note and not note.startswith("skipped"):
            result["errors"].append(f"fnd_network:{note}")
    return result


# FND agricultural-network map: the panel keypath whose profile_refs the map's
# dataset is built from, and the generator that rebuilds it.
_FND_SITE_DIR = "fruitfulnetworkdevelopment.com"
_FND_NETWORK_KEYPATH = ("pages", "more", "content", "network")


def _fnd_network_refs(webapps_root: str | Path) -> set[str]:
    """The set of profile slugs the FND network map is built from.

    Reads ``pages.more.content.network.panel.{profile_refs,farm_profile_refs}``
    from the FND site manifest JSON. Empty set on any miss.
    """
    import json

    manifest = (
        Path(webapps_root)
        / "clients"
        / _FND_SITE_DIR
        / "frontend"
        / "assets"
        / "0000-00-00.manifest.fnd.fnd.site.json"
    )
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    node: Any = data
    for key in _FND_NETWORK_KEYPATH:
        node = node.get(key, {}) if isinstance(node, dict) else {}
    panel = node.get("panel", {}) if isinstance(node, dict) else {}
    # Union BOTH ref lists for presence detection — a slug present in only
    # ``farm_profile_refs`` (back-compat alias) must still register as in-network
    # so the cascade updates it and the dataset regen fires.
    out: set[str] = set()
    for refs_key in ("profile_refs", "farm_profile_refs"):
        refs = panel.get(refs_key)
        if isinstance(refs, list):
            out.update(_as_text(r) for r in refs if _as_text(r))
    return out


def _regenerate_fnd_network_dataset(
    webapps_root: str | Path, slug: str
) -> tuple[bool, str]:
    """Regenerate the FND network-map dataset when ``slug`` feeds the map.

    Runs the site's ``scripts/build_farm_network.py`` (writes only the dataset
    JSON, no HTML). Returns ``(ok, note)``; ``("skipped...", )`` when the slug is
    not a network ref or the FND site/script is absent. Mirrors the subprocess
    pattern of ``_build_site_for_excerpt``.
    """
    if slug not in _fnd_network_refs(webapps_root):
        return True, "skipped: slug not in FND network refs"
    frontend_dir = Path(webapps_root) / "clients" / _FND_SITE_DIR / "frontend"
    script = frontend_dir / "scripts" / "build_farm_network.py"
    if not script.is_file():
        return True, "skipped: no build_farm_network.py"
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
    return True, "fnd network dataset regenerated"


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
    """Append an asset entry to a site's *<kind>_use.yaml record-manifest.

    Dedupes by asset_path (no-op when already present), preserves hand-edited
    entries, writes atomically. ``site`` is the client domain dir under
    clients/. Returns {"ok": True, "added": bool, "manifest": path}.
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
    manifest_path = _site_manifest_path(webapps_root, site, kind)
    if manifest_path is None:
        return {"ok": False, "error": "no_manifest_for_kind"}
    data = _load_yaml_mapping(manifest_path)
    entries = data.get("entries")
    if not isinstance(entries, list):
        entries = []
        data["entries"] = entries
    for entry in entries:
        if isinstance(entry, dict) and _as_text(entry.get("asset_path")) == asset_path:
            return {"ok": True, "added": False, "manifest": str(manifest_path)}
    entries.append(
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
    return {"ok": True, "added": True, "manifest": str(manifest_path)}


def _site_manifest_path(
    webapps_root: str | Path, site: str, kind: str
) -> Path | None:
    """Resolve a site's ``*<kind>_use.yaml`` record-manifest, or None."""
    assets_dir = Path(webapps_root) / "clients" / os.path.basename(_as_text(site)) / "frontend" / "assets"
    matches = glob.glob(str(assets_dir / f"*{_as_text(kind)}_use.yaml"))
    return Path(sorted(matches)[0]) if matches else None


def site_manifest_entries(
    webapps_root: str | Path | None, site: str, kind: str
) -> list[dict[str, Any]]:
    """The entries currently allocated to a site's ``*<kind>_use.yaml`` manifest.

    Each row = {asset_id, asset_path, entity_scope}. Empty list when the site or
    manifest is absent. Reuses ``_load_yaml_mapping``.
    """
    if not webapps_root:
        return []
    manifest_path = _site_manifest_path(webapps_root, site, kind)
    if manifest_path is None:
        return []
    data = _load_yaml_mapping(manifest_path)
    rows: list[dict[str, Any]] = []
    for entry in data.get("entries") or []:
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
    """Drop the entry whose ``asset_path`` matches from a site's
    ``*<kind>_use.yaml`` manifest (the de-allocation sibling of
    ``add_asset_to_manifest``). Atomic; no-op when not present.
    Returns ``{ok, removed: bool, manifest}``.
    """
    if not webapps_root:
        return {"ok": False, "error": "no_webapps_root"}
    site = os.path.basename(_as_text(site))
    kind = _as_text(kind)
    asset_path = _as_text(asset_path)
    if not site or not kind or not asset_path:
        return {"ok": False, "error": "missing_field"}
    manifest_path = _site_manifest_path(webapps_root, site, kind)
    if manifest_path is None:
        return {"ok": False, "error": "no_manifest_for_kind"}
    data = _load_yaml_mapping(manifest_path)
    entries = data.get("entries")
    if not isinstance(entries, list):
        return {"ok": True, "removed": False, "manifest": str(manifest_path)}
    kept = [
        e
        for e in entries
        if not (isinstance(e, dict) and _as_text(e.get("asset_path")) == asset_path)
    ]
    if len(kept) == len(entries):
        return {"ok": True, "removed": False, "manifest": str(manifest_path)}
    data["entries"] = kept
    text = yaml.safe_dump(
        data, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    try:
        _atomic_write_text(manifest_path, text)
    except OSError as exc:
        return {"ok": False, "error": "write_failed", "detail": str(exc)}
    return {"ok": True, "removed": True, "manifest": str(manifest_path)}


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
    """Every ``asset_path`` referenced by any site ``*<kind>_use.yaml`` manifest.

    Generalizes the icon-only ``_icon_manifest_referenced_paths`` to any kind
    (profile/image/icon/document/audio); used to gate delete and to flag which
    library members are in use by some site.
    """
    referenced: set[str] = set()
    kind = _as_text(kind)
    if not webapps_root or not kind:
        return referenced
    pattern = str(
        Path(webapps_root) / "clients" / "*" / "frontend" / "assets" / f"*{kind}_use.yaml"
    )
    for hit in glob.glob(pattern):
        data = _load_yaml_mapping(Path(hit))
        for entry in data.get("entries") or []:
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
    # The FND network map consumes profiles by slug from its manifest (NOT via
    # excerpts or *_use.yaml), so fold those refs into a profile's in_use.
    # Computed once and reused across all profile rows.
    fnd_refs = _fnd_network_refs(webapps_root) if webapps_root else set()
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
                    in_use = (
                        referenced
                        or slug in fnd_refs
                        or bool(_excerpt_paths_for_slug(webapps_root, slug))
                    )
                else:
                    entity_type = ""
                    title = slug
                    in_use = referenced
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
    """Update every ``*<kind>_use.yaml`` entry whose asset_path == match_path.

    Optionally set ``asset_path=new_path`` and/or merge ``patch`` into the
    entry. Atomic per manifest. Returns the list of manifest paths changed.
    """
    updated: list[str] = []
    pattern = str(
        Path(webapps_root) / "clients" / "*" / "frontend" / "assets" / f"*{kind}_use.yaml"
    )
    for hit in sorted(glob.glob(pattern)):
        manifest_path = Path(hit)
        data = _load_yaml_mapping(manifest_path)
        entries = data.get("entries")
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
    import json

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

    webapps = Path(webapps_root)
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

    fnd_manifest = (
        webapps / "clients" / _FND_SITE_DIR / "frontend" / "assets"
        / "0000-00-00.manifest.fnd.fnd.site.json"
    )
    report["fnd_network"] = old_slug in _fnd_network_refs(webapps_root)

    old_asset = "/assets/profiles/" + canonical.name
    new_asset = "/assets/profiles/" + new_canonical_name

    data_files, data_other = _find_data_profile_refs(webapps_root, old_slug)
    report["data_files"] = data_files
    report["data_other"] = data_other
    report["sites"] = sorted({str(ex.parent.parent) for ex, _ in excerpt_plan})

    if not apply:
        return {"ok": True, "report": report}

    # ---- APPLY (backups on edits; renames recorded in the report). Best-effort
    # atomic: discovery + collision checks ran above, so the remaining work is
    # mechanical. A mid-way failure is surfaced (with the partial report) rather
    # than silently swallowed; full rollback is intentionally out of scope. ----
    try:
        os.replace(str(canonical), str(canonical.parent / new_canonical_name))
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
        if report["fnd_network"] and fnd_manifest.is_file():
            try:
                data = json.loads(fnd_manifest.read_text(encoding="utf-8"))
                node: Any = data
                for key in _FND_NETWORK_KEYPATH:
                    node = node.get(key, {}) if isinstance(node, dict) else {}
                panel = node.get("panel", {}) if isinstance(node, dict) else {}
                changed = False
                for refs_key in ("profile_refs", "farm_profile_refs"):
                    refs = panel.get(refs_key)
                    if isinstance(refs, list):
                        new_refs = [new_slug if _as_text(r) == old_slug else r for r in refs]
                        if new_refs != refs:
                            panel[refs_key] = new_refs
                            changed = True
                if changed:
                    _backup_file(fnd_manifest)
                    _atomic_write_text(
                        fnd_manifest, json.dumps(data, indent=2, ensure_ascii=False) + "\n"
                    )
            except (OSError, ValueError):
                pass
        report["profile_use"] = _update_manifests_for_asset(
            webapps_root, "profile", old_asset, new_path=new_asset
        )
        for df in data_files:
            p = Path(df)
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            needle = "/profile/" + old_slug
            if needle in text:
                _backup_file(p)
                _atomic_write_text(p, text.replace(needle, "/profile/" + new_slug))
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
        # A profile is "in use" if a site has a derived excerpt OR the FND
        # network map references its slug (which is not a manifest/excerpt ref).
        if _excerpt_paths_for_slug(webapps_root, pslug) or pslug in _fnd_network_refs(webapps_root):
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
        used = site_manifest_entries(webapps_root, site, kind)
        used_paths = {e["asset_path"] for e in used}
        # Allocation derives its own per-site ``allocated`` flag from
        # ``used_paths`` below, so skip the all-sites ``referenced`` glob.
        grouped = build_grouped_gallery(
            webapps_root, gallery, compute_referenced=False
        )
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


def _render_ext_resources(ctx: dict[str, Any]) -> dict[str, Any]:
    """Render the resources extension card payload.

    Two modes (the operator's "overall library vs per-grantee allocation"):
      * LIBRARY (default) → the shared Resource LIBRARY (search/view/manage all
        leaflets by type, organized by slug). Reads the shared site-core
        galleries straight from ``webapps_root`` (not grantee-scoped). This is
        the default whenever no specific grantee is engaged — including a bare
        ctx — so it is the back-compatible behavior.
      * ALLOCATION → only when grantee mode is active AND a grantee is selected:
        manage which leaflets are "used" in that site's per-type ``*_use.yaml``
        manifest (``_resources_allocation_payload``, per-grantee phase).
    """
    grantee = ctx.get("grantee") if isinstance(ctx.get("grantee"), dict) else {}
    if _as_text(ctx.get("mode")) == "grantee" and _as_text(grantee.get("msn_id")):
        return _resources_allocation_payload(ctx)
    return _resources_library_payload(ctx.get("webapps_root"))


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
    "propagate_profile",
    "remove_asset_from_manifest",
    "remove_icon_duplicate",
    "rename_slug",
    "resolve_profile_image",
    "retitle_asset",
    "save_profile",
    "site_manifest_entries",
]
