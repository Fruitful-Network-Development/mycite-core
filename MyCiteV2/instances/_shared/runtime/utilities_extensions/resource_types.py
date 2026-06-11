"""Leaflet TYPE registry + by-type indexing for the resources extension.

The Resource extension's OVERALL view browses every leaflet by TYPE, off the
master manifest's ``type_tree`` (the SSOT leaflet type registry):

    clients/_shared/site-core/schema/0000-00-00.artifact-manifest.mycite.schema.yaml

A node's full type token is its dash-segment PATH joined by ``-`` (e.g.
``artifact → profile → legal_entity → ag → producer → apiary`` ==
``artifact-profile-legal_entity-ag-producer-apiary``). Each node carries
``{label, icon, icon_ref?, color?, children?}``.

This module is the read/index half: load + flatten the tree, parse a leaflet
filename's TYPE token (the 2nd of the four dot-fields), match an on-disk token
to its nearest registered node, index/roll-up leaflets per type, and route an
instance to its viewer. It REUSES the existing helpers in
``resources_extension`` (site-core resolution, YAML load, gallery metadata,
asset descriptor) and deliberately mirrors ``build_farm_network.py``'s tree
walk — but, unlike that build (which ``sys.exit``s on a broken manifest), every
function here degrades to empty so the portal render can never crash on a
malformed registry (the ``render_extension`` resilience contract).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._shared import _as_text
from .resources_extension import (
    _asset_descriptor,
    _load_yaml_mapping,
    _profile_entity_flavor,
    _profile_slug,
    _scalar_str,
    _site_core_root,
    asset_url_prefix_for,
)

# Master manifest location relative to the site-core root.
_MANIFEST_SCHEMA_REL = ("schema", "0000-00-00.artifact-manifest.mycite.schema.yaml")

# Site-core leaflet directories the type browser scans. The PII-bearing dirs are
# scanned only when include_pii=True (grantee-scoped), mirroring the OVERALL
# library's PII boundary (resources_extension._GALLERY_META comment).
_TYPE_SCAN_GALLERIES: tuple[str, ...] = (
    "profiles", "icon", "image", "document", "audio",
    "analytics", "newsletter", "schema",
    "event", "custom", "contacts",
)
_PII_GALLERIES: frozenset[str] = frozenset({"event", "custom", "contacts"})


# --------------------------------------------------------------------------- #
# manifest type_tree loader (NON-FATAL port of build_farm_network tree walk)
# --------------------------------------------------------------------------- #
def manifest_schema_path(webapps_root: str | Path | None) -> Path | None:
    root = _site_core_root(webapps_root)
    return root.joinpath(*_MANIFEST_SCHEMA_REL) if root is not None else None


def load_type_tree(webapps_root: str | Path | None) -> dict[str, Any]:
    """The master manifest's ``type_tree`` mapping (``{}`` on any problem)."""
    path = manifest_schema_path(webapps_root)
    if path is None or not path.is_file():
        return {}
    tree = _load_yaml_mapping(path).get("type_tree")
    return tree if isinstance(tree, dict) else {}


def load_manifest_default_style(webapps_root: str | Path | None) -> dict[str, Any]:
    """The ``default_style`` ("Other" bucket) node, ``{}`` when absent."""
    path = manifest_schema_path(webapps_root)
    if path is None or not path.is_file():
        return {}
    style = _load_yaml_mapping(path).get("default_style")
    return style if isinstance(style, dict) else {}


def flatten_type_tree(webapps_root: str | Path | None) -> list[dict[str, Any]]:
    """Depth-first flatten of the ``type_tree`` into one row per TYPE node.

    Row: ``{full_slug, segments, label, icon, icon_ref, color, depth,
    parent_slug, child_slugs, has_children}``. Deterministic (YAML file order).
    Returns ``[]`` on a missing/broken manifest.
    """
    rows: list[dict[str, Any]] = []

    def walk(mapping: Any, segments: list[str]) -> None:
        if not isinstance(mapping, dict):
            return
        for seg, node in mapping.items():
            if not isinstance(node, dict):
                continue
            seg_s = _as_text(seg)
            path = [*segments, seg_s]
            children = node.get("children")
            child_keys = [_as_text(k) for k in children] if isinstance(children, dict) else []
            rows.append(
                {
                    "full_slug": "-".join(path),
                    "segments": list(path),
                    "label": _as_text(node.get("label")) or seg_s,
                    "icon": _as_text(node.get("icon")),
                    "icon_ref": _as_text(node.get("icon_ref")),
                    "color": _as_text(node.get("color")),
                    "depth": len(path) - 1,
                    "parent_slug": "-".join(path[:-1]),
                    "child_slugs": ["-".join([*path, k]) for k in child_keys],
                    "has_children": bool(child_keys),
                }
            )
            walk(children, path)

    walk(load_type_tree(webapps_root), [])
    return rows


def registered_full_slugs(webapps_root: str | Path | None) -> set[str]:
    return {row["full_slug"] for row in flatten_type_tree(webapps_root)}


def type_node_full(webapps_root: str | Path | None, full_slug: str) -> dict[str, Any] | None:
    """The raw ``type_tree`` node for a full dash-path token, or ``None``.

    Segments split on ``-``; segment KEYS use underscores internally
    (``legal_entity``, ``food_hub``), so dash-splitting is the correct
    segmentation.
    """
    full_slug = _as_text(full_slug)
    if not full_slug:
        return None
    node: Any = load_type_tree(webapps_root)
    last: dict[str, Any] | None = None
    for seg in full_slug.split("-"):
        if not isinstance(node, dict):
            return None
        child = node.get(seg)
        if not isinstance(child, dict):
            return None
        last = child
        node = child.get("children") or {}
    return last


# --------------------------------------------------------------------------- #
# filename TYPE parsing + node matching
# --------------------------------------------------------------------------- #
def parse_leaflet_type(filename: str) -> str:
    """The TYPE token (2nd of the four dot-fields) of a leaflet filename, or "".

    ``0000-00-00.artifact-event-hebdomadal.owner.name.yaml`` →
    ``artifact-event-hebdomadal``;
    ``0000-00-00.artifact-profile-natural_entity.nathan_seals.profile.yaml`` →
    ``artifact-profile-natural_entity``. Mirrors
    ``clients/_shared/site-core/scripts/lint_assets.py parse_filename`` (+
    ``KINDS_ARTIFACT_KNOWN``), the SSOT spec; re-implemented here to avoid
    importing across the webapps/ boundary.
    """
    name = str(filename)
    if "." not in name:
        return ""
    stem = name.rsplit(".", 1)[0]  # drop the file extension
    slots = stem.split(".")
    return slots[1] if len(slots) >= 2 else ""


def match_type_to_node(full_slugs: set[str], type_token: str) -> tuple[str, str]:
    """Map an on-disk TYPE token to its nearest registered node + the tail.

    Longest registered dash-prefix wins; unmatched trailing dash-segments become
    ``subtype_tail`` (e.g. token ``artifact-event-finite`` when the tree stops at
    ``artifact-event`` → node ``artifact-event``, tail ``finite``). Returns
    ``("", token)`` when nothing matches (caller buckets under "Other").
    """
    segs = _as_text(type_token).split("-")
    for cut in range(len(segs), 0, -1):
        candidate = "-".join(segs[:cut])
        if candidate in full_slugs:
            return candidate, "-".join(segs[cut:])
    return "", _as_text(type_token)


def _is_pii_type(full_type: str) -> bool:
    token = _as_text(full_type)
    return token.startswith("artifact-event") or token.startswith("artifact-custom")


# --------------------------------------------------------------------------- #
# by-type leaflet index + roll-up counts
# --------------------------------------------------------------------------- #
def build_type_leaflet_index(
    webapps_root: str | Path | None, *, include_pii: bool = False
) -> dict[str, list[dict[str, Any]]]:
    """Map each on-disk leaflet TYPE token → list of leaflet rows.

    Scans the shared site-core leaflet dirs and types each file by its filename
    TYPE field. PII-bearing dirs (event/custom/contacts) are skipped unless
    ``include_pii`` — the OVERALL view keeps them out; the per-grantee subtab
    passes ``include_pii=True`` (grantee scope enforced upstream). Each row reuses
    the ``build_grouped_gallery`` member shape plus ``full_type``/``node_slug``/
    ``subtype_tail``/``gallery``.
    """
    root = _site_core_root(webapps_root)
    index: dict[str, list[dict[str, Any]]] = {}
    if root is None:
        return index
    full_slugs = registered_full_slugs(webapps_root)
    for gallery in _TYPE_SCAN_GALLERIES:
        if gallery in _PII_GALLERIES and not include_pii:
            continue
        gdir = root / gallery
        if not gdir.is_dir():
            continue
        url_prefix = asset_url_prefix_for(gallery) or f"/site-core/{gallery}/"
        is_profiles = gallery == "profiles"
        try:
            children = sorted(gdir.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            continue
        for p in children:
            if not p.is_file() or p.name.startswith(".") or ".example." in p.name:
                continue
            type_token = parse_leaflet_type(p.name)
            if not type_token:
                continue
            node_slug, tail = match_type_to_node(full_slugs, type_token)
            if is_profiles:
                slug, owner, ext = _profile_slug(p.name), _profile_entity_flavor(p.name), "yaml"
            else:
                slug, owner, ext = _asset_descriptor(p.name)
            try:
                size = p.stat().st_size
            except OSError:
                size = 0
            index.setdefault(type_token, []).append(
                {
                    "filename": p.name,
                    "asset_path": url_prefix + p.name,
                    "gallery": gallery,
                    "full_type": type_token,
                    "node_slug": node_slug,
                    "subtype_tail": tail,
                    "slug": slug,
                    "owner": owner,
                    "ext": ext,
                    "size_bytes": int(size),
                    "image_url": (url_prefix + p.name) if gallery in ("icon", "image") else "",
                }
            )
    return index


def leaflets_for_type(
    webapps_root: str | Path | None,
    full_slug: str,
    *,
    include_subtypes: bool = True,
    include_pii: bool = False,
) -> list[dict[str, Any]]:
    """Every leaflet whose TYPE token is ``full_slug`` (or, with
    ``include_subtypes``, a dash-descendant of it). Base type ⊇ subtype rollup.
    """
    full_slug = _as_text(full_slug)
    index = build_type_leaflet_index(webapps_root, include_pii=include_pii)
    out: list[dict[str, Any]] = []
    for token, rows in index.items():
        if token == full_slug or (include_subtypes and token.startswith(full_slug + "-")):
            out.extend(rows)
    out.sort(key=lambda r: (r["full_type"], r["slug"], r["filename"]))
    return out


def type_leaflet_counts(
    webapps_root: str | Path | None, *, include_pii: bool = False
) -> dict[str, int]:
    """Leaflet count per registered node ``full_slug``, ROLLED UP so a base type
    includes all dash-descendants. Tokens matching no registered node roll into
    the ``""`` ("Other") bucket.
    """
    index = build_type_leaflet_index(webapps_root, include_pii=include_pii)
    full_slugs = [row["full_slug"] for row in flatten_type_tree(webapps_root)]
    counts: dict[str, int] = {fs: 0 for fs in full_slugs}
    other = 0
    for token, rows in index.items():
        n = len(rows)
        matched = False
        for fs in full_slugs:
            if token == fs or token.startswith(fs + "-"):
                counts[fs] += n
                matched = True
        if not matched:
            other += n
    if other:
        counts[""] = other
    return counts


# --------------------------------------------------------------------------- #
# instance viewer routing + generic structured view
# --------------------------------------------------------------------------- #
# Longest dash-prefix wins. Filename TYPE keys NAVIGATION only; archetype-bound
# tools (analytics/farm_profile) re-resolve their own document downstream.
_TYPE_VIEWER_ROUTES: tuple[tuple[str, dict[str, Any]], ...] = (
    ("artifact-profile", {"viewer": "profile", "param": "slug"}),
    ("record-analytics", {"viewer": "analytics"}),
    ("artifact-event", {"viewer": "event"}),
    ("artifact-icon", {"viewer": "asset"}),
    ("artifact-image", {"viewer": "asset"}),
    ("artifact-logo", {"viewer": "asset"}),
    ("artifact-document", {"viewer": "asset"}),
)
_GENERIC_VIEWER: dict[str, Any] = {"viewer": "generic"}


def resolve_instance_viewer(full_type: str) -> dict[str, Any]:
    """The viewer descriptor for a leaflet TYPE token (longest dash-prefix wins).

    profile → profile editor, record-analytics → analytics dashboard,
    artifact-event → event view, binary asset galleries → asset preview,
    everything else (custom/link/quote/record-*/dataset/…) → the generic
    structured viewer.
    """
    token = _as_text(full_type)
    best: dict[str, Any] | None = None
    best_len = -1
    for prefix, desc in _TYPE_VIEWER_ROUTES:
        if (token == prefix or token.startswith(prefix + "-")) and len(prefix) > best_len:
            best, best_len = desc, len(prefix)
    return dict(best) if best is not None else dict(_GENERIC_VIEWER)


def _resolve_site_core_asset(webapps_root: str | Path | None, asset_path: str) -> Path | None:
    """Resolve an emitted ``asset_path`` back to a site-core file by BASENAME
    (basename-only join prevents path traversal)."""
    root = _site_core_root(webapps_root)
    if root is None:
        return None
    fname = _as_text(asset_path).rsplit("/", 1)[-1]
    if not fname or "/" in fname or fname.startswith("."):
        return None
    for gallery in _TYPE_SCAN_GALLERIES:
        cand = root / gallery / fname
        if cand.is_file():
            return cand
    return None


def structured_leaflet_view(
    webapps_root: str | Path | None, full_type: str, asset_path: str
) -> dict[str, Any] | None:
    """Generic read-only view of any leaflet: every top-level field flattened
    (reusing ``_scalar_str``) + the raw YAML. ``None`` when the file is missing.
    """
    path = _resolve_site_core_asset(webapps_root, asset_path)
    if path is None:
        return None
    data = _load_yaml_mapping(path)
    fields = [
        {
            "key": _as_text(k),
            "label": _as_text(k).replace("_", " ").title(),
            "value": _scalar_str(v),
            "is_nested": isinstance(v, (dict, list)),
        }
        for k, v in data.items()
    ]
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        raw = ""
    return {
        "filename": path.name,
        "full_type": _as_text(full_type),
        "label": path.name,
        "fields": fields,
        "raw_yaml": raw,
    }


__all__ = [
    "build_type_leaflet_index",
    "flatten_type_tree",
    "leaflets_for_type",
    "load_manifest_default_style",
    "load_type_tree",
    "manifest_schema_path",
    "match_type_to_node",
    "parse_leaflet_type",
    "registered_full_slugs",
    "resolve_instance_viewer",
    "structured_leaflet_view",
    "type_leaflet_counts",
    "type_node_full",
]
