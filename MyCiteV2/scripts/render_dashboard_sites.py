#!/usr/bin/env python3
"""render_dashboard_sites.py — render or lint per-site grantee dashboards.

Two modes:

  --render   Generate /srv/webapps/clients/<domain>/dashboard/ for every
             site config under SITES from the canonical shell under
             /srv/webapps/clients/_shared/dashboard/. Per-site copies
             differ ONLY in:
               - index.html placeholder substitutions
                 (__SHORT_NAME__, __LABEL__, __MSN_ID__, etc.)
               - dashboard.css :root color overrides
               - config.json (drives the per-site brand + footer)

  --check    Re-render the per-site files in-memory and compare to what
             exists on disk. Any byte-level drift fails the check. This
             is the CI gate that prevents copy-paste rot.

The same substitution table is used for both modes so the lint cannot
diverge from the renderer.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

CANONICAL_DIR = Path("/srv/webapps/clients/_shared/dashboard")
CLIENTS_ROOT  = Path("/srv/webapps/clients")
GRANTEE_DIR   = Path("/srv/webapps/mycite/fnd/private/utilities/tools/fnd-csm")


# ----------------------------------------------------------------------
# Site catalog — one entry per client site. Brand colors are the only
# field that doesn't come from the canonical grantee profile JSON.
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class Site:
    short_name: str
    domain: str
    site_title: str          # short title in the browser tab
    brand_primary: str       # #RRGGBB
    brand_primary_dark: str  # #RRGGBB
    brand_accent_soft: str   # #RRGGBB
    optional_tabs_jobs: bool = False


SITES: tuple[Site, ...] = (
    Site(
        short_name="BPW",
        domain="brockspressurewashing.com",
        site_title="Brock's Pressure Washing",
        brand_primary="#1f6fb2",
        brand_primary_dark="#155485",
        brand_accent_soft="#d8e9f5",
        optional_tabs_jobs=True,
    ),
    Site(
        short_name="CVCC",
        domain="cuyahogavalleycountrysideconservancy.org",
        site_title="CVCC",
        brand_primary="#3a6b35",
        brand_primary_dark="#264720",
        brand_accent_soft="#dceadc",
    ),
    Site(
        short_name="FND",
        domain="fruitfulnetworkdevelopment.com",
        site_title="FND",
        brand_primary="#0f6e56",
        brand_primary_dark="#0a5b46",
        brand_accent_soft="#d7ece4",
    ),
    Site(
        short_name="TFF",
        domain="trappfamilyfarm.com",
        site_title="Trapp Family Farm",
        brand_primary="#8b5a2b",
        brand_primary_dark="#6b4321",
        brand_accent_soft="#ede2d4",
    ),
)


# ----------------------------------------------------------------------
# Grantee profile lookup
# ----------------------------------------------------------------------

def load_grantee_for_site(site: Site) -> dict:
    """Find the grantee profile dict whose `short_name` matches `site`.
    Cross-validates domain ownership."""
    import sys
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
        load_grantee_directory,
    )
    for data in load_grantee_directory(GRANTEE_DIR):
        if str(data.get("short_name", "")).lower() != site.short_name.lower():
            continue
        domains = [str(d).lower() for d in data.get("domains") or []]
        if site.domain.lower() not in domains:
            raise SystemExit(
                f"grantee profile for short_name={site.short_name} "
                f"does not own {site.domain} — fix the catalog or the profile"
            )
        return data
    raise SystemExit(
        f"no grantee profile for short_name={site.short_name} "
        f"found under {GRANTEE_DIR}"
    )


# ----------------------------------------------------------------------
# Substitution
# ----------------------------------------------------------------------

def substitutions_for(site: Site, grantee: dict) -> dict[str, str]:
    """Return the placeholder→value map used in BOTH render and check."""
    primary_user = ""
    users = grantee.get("users") or []
    if users:
        primary_user = str(users[0])
    return {
        "__SHORT_NAME__":               site.short_name,
        "__LABEL__":                    str(grantee.get("label") or site.site_title),
        "__MSN_ID__":                   str(grantee.get("msn_id") or ""),
        "__PRIMARY_DOMAIN__":           site.domain,
        "__SITE_TITLE__":               site.site_title,
        "__BRAND_PRIMARY_COLOR__":      site.brand_primary,
        "__BRAND_PRIMARY_COLOR_DARK__": site.brand_primary_dark,
        "__BRAND_ACCENT_SOFT__":        site.brand_accent_soft,
        "__FOOTER_CONTACT_EMAIL__":     primary_user or f"hello@{site.domain}",
    }


def apply_subs(text: str, subs: dict[str, str]) -> str:
    out = text
    for needle, value in subs.items():
        out = out.replace(needle, value)
    return out


# ----------------------------------------------------------------------
# Per-site config.json — derived from catalog + grantee profile
# ----------------------------------------------------------------------

def site_config_payload(site: Site, grantee: dict) -> dict:
    users = grantee.get("users") or []
    contact = str(users[0]) if users else f"hello@{site.domain}"
    return {
        "schema": "mycite.v2.dashboard.site_config.v1",
        "msn_id": str(grantee.get("msn_id") or ""),
        "short_name": site.short_name,
        "label": str(grantee.get("label") or site.site_title),
        "primary_domain": site.domain,
        "site_title": site.site_title,
        "brand": {
            "primary_color":      site.brand_primary,
            "primary_color_dark": site.brand_primary_dark,
            "accent_soft":        site.brand_accent_soft,
        },
        "footer": {"contact_email": contact},
        "optional_tabs": {"jobs": site.optional_tabs_jobs},
    }


# ----------------------------------------------------------------------
# Render / check
# ----------------------------------------------------------------------

# Files whose content gets placeholder substitution.
SUBSTITUTED_FILES = ("index.html", "dashboard.css", "README.md")
# Files copied byte-for-byte.
COPIED_FILES = ("dashboard.js",)
# Subdirs walked recursively and copied byte-for-byte.
COPIED_DIRS = ("tabs", "lib")
# Files generated from the site catalog (not from canonical).
GENERATED_FILES = ("config.json",)


_CANONICAL_CACHE: list[tuple[Path, bytes]] | None = None


def _canonical_files() -> list[tuple[Path, bytes]]:
    """Return [(path, bytes)] for every canonical-source file. Cached;
    re-reading the canonical tree per-site was the dominant cost of
    --check across N sites."""
    global _CANONICAL_CACHE
    if _CANONICAL_CACHE is not None:
        return _CANONICAL_CACHE
    files: list[tuple[Path, bytes]] = []
    for name in SUBSTITUTED_FILES + COPIED_FILES:
        path = CANONICAL_DIR / name
        if not path.exists():
            raise SystemExit(f"canonical file missing: {path}")
        files.append((path, path.read_bytes()))
    for d in COPIED_DIRS:
        root = CANONICAL_DIR / d
        if not root.exists():
            raise SystemExit(f"canonical dir missing: {root}")
        for path in sorted(root.rglob("*")):
            if path.is_file():
                files.append((path, path.read_bytes()))
    _CANONICAL_CACHE = files
    return files


def render_for_site(site: Site) -> dict[str, bytes]:
    """Return {relative_path: content_bytes} for everything we own under
    the site's dashboard/ directory."""
    grantee = load_grantee_for_site(site)
    subs = substitutions_for(site, grantee)

    out: dict[str, bytes] = {}
    for src, payload in _canonical_files():
        rel = src.relative_to(CANONICAL_DIR).as_posix()
        if rel in SUBSTITUTED_FILES:
            payload = apply_subs(payload.decode("utf-8"), subs).encode("utf-8")
        out[rel] = payload
    out["config.json"] = (
        json.dumps(site_config_payload(site, grantee), indent=2, sort_keys=False) + "\n"
    ).encode("utf-8")
    return out


def site_dir_for(site: Site) -> Path:
    return CLIENTS_ROOT / site.domain / "dashboard"


def write_site(site: Site, files: dict[str, bytes]) -> list[str]:
    """Write rendered files; return list of relative paths actually changed."""
    dst_root = site_dir_for(site)
    changed: list[str] = []
    for rel, payload in files.items():
        dst = dst_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and dst.read_bytes() == payload:
            continue
        dst.write_bytes(payload)
        changed.append(rel)
    return changed


def check_site(site: Site, files: dict[str, bytes]) -> list[str]:
    """Return list of {rel:reason} drift descriptions. Empty list = clean."""
    dst_root = site_dir_for(site)
    drift: list[str] = []
    for rel, payload in files.items():
        dst = dst_root / rel
        if not dst.exists():
            drift.append(f"{site.domain}/{rel}: MISSING")
            continue
        actual = dst.read_bytes()
        if actual != payload:
            drift.append(
                f"{site.domain}/{rel}: DRIFT ({len(actual)} bytes on disk vs "
                f"{len(payload)} bytes rendered)"
            )
    # Detect EXTRA files in the per-site dashboard dir that the renderer
    # would never emit — those are also drift.
    expected = {(dst_root / rel).resolve() for rel in files}
    if dst_root.exists():
        for p in dst_root.rglob("*"):
            if not p.is_file():
                continue
            if p.resolve() not in expected:
                drift.append(f"{site.domain}/{p.relative_to(dst_root).as_posix()}: UNEXPECTED")
    return drift


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--render", action="store_true",
                      help="write per-site files from canonical")
    mode.add_argument("--check", action="store_true",
                      help="exit non-zero if any per-site file drifts from canonical")
    ap.add_argument("--site", action="append", default=[],
                    help="restrict to one or more domains (defaults to all)")
    args = ap.parse_args()

    selected = SITES
    if args.site:
        wanted = {s.lower() for s in args.site}
        selected = tuple(s for s in SITES if s.domain in wanted)
        if not selected:
            print(f"no matching sites in catalog: {args.site!r}", file=sys.stderr)
            return 2

    if args.render:
        total_changes = 0
        for site in selected:
            files = render_for_site(site)
            changes = write_site(site, files)
            if changes:
                print(f"[{site.domain}] wrote {len(changes)} files:")
                for rel in changes:
                    print(f"  - {rel}")
            else:
                print(f"[{site.domain}] up to date")
            total_changes += len(changes)
        print(f"render complete; {total_changes} file(s) written")
        return 0

    if args.check:
        all_drift: list[str] = []
        for site in selected:
            files = render_for_site(site)
            drift = check_site(site, files)
            if drift:
                all_drift.extend(drift)
        if all_drift:
            print("DASHBOARD PARITY LINT FAILED:", file=sys.stderr)
            for line in all_drift:
                print(f"  {line}", file=sys.stderr)
            print(
                "\nFix by running:\n"
                "  python3 /srv/repo/mycite-core/MyCiteV2/scripts/render_dashboard_sites.py --render",
                file=sys.stderr,
            )
            return 1
        print("dashboard parity OK")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
