"""One-shot migration: fold the stranded doubled-``private/private`` contact
logs back into the single canonical tree.

Background: the retired ``MosDatumNewsletterContactLogAdapter`` shim derived its
store dir as ``Path(authority_db_file).parent / "private"``. With the live
authority DB at ``<private>/mos_authority.sqlite3`` that resolved to the doubled
``<private>/private/utilities/tools/aws-csm/newsletter/`` — a directory the
dashboard never read. After the consolidation, every writer uses the single
``<private>/utilities/tools/aws-csm/newsletter/`` tree. This script merges any
rows left in the doubled tree into the single tree.

Idempotent + safe to re-run: it merges by lowercased email (the row with the
newer ``updated_at`` wins), unions dispatch history, then renames each migrated
source file to ``*.migrated``. Run it AFTER the consolidation is deployed so no
new rows land in the doubled tree mid-migration.

Usage:
    python -m MyCiteV2.scripts.migrate_contact_log_tree [--private-dir PATH] [--dry-run]

``--private-dir`` defaults to $PRIVATE_DIR, else the parent of
$MYCITE_V2_PORTAL_AUTHORITY_DB.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import FilesystemNewsletterStateAdapter

_NEWSLETTER_SUBPATH = ("utilities", "tools", "aws-csm", "newsletter")


def _resolve_private_dir(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    env_private = os.environ.get("PRIVATE_DIR")
    if env_private:
        return Path(env_private)
    authority = os.environ.get("MYCITE_V2_PORTAL_AUTHORITY_DB")
    if authority:
        return Path(authority).parent
    raise SystemExit(
        "Could not resolve the private dir: pass --private-dir or set "
        "PRIVATE_DIR / MYCITE_V2_PORTAL_AUTHORITY_DB."
    )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _domain_from_filename(path: Path) -> str:
    return path.name.removeprefix("newsletter.").removesuffix(".contacts.json").strip().lower()


def _merge_contacts(
    target: list[dict[str, Any]], source: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Union by lowercased email; the row with the newer updated_at wins."""
    by_email: dict[str, dict[str, Any]] = {}
    for row in [*target, *source]:
        if not isinstance(row, dict):
            continue
        email = str(row.get("email", "")).strip().lower()
        if not email:
            continue
        held = by_email.get(email)
        if held is None or str(row.get("updated_at", "")) >= str(held.get("updated_at", "")):
            by_email[email] = row
    return list(by_email.values())


def migrate(private_dir: Path, *, dry_run: bool) -> int:
    doubled_root = private_dir.joinpath("private", *_NEWSLETTER_SUBPATH)
    if not doubled_root.is_dir():
        print(f"No doubled tree at {doubled_root} — nothing to migrate.")
        return 0

    adapter = FilesystemNewsletterStateAdapter(private_dir)
    migrated = 0
    for source_path in sorted(doubled_root.glob("newsletter.*.contacts.json")):
        domain = _domain_from_filename(source_path)
        if not domain:
            print(f"  ? skipping unparseable filename: {source_path.name}")
            continue
        source = _load_json(source_path)
        source_contacts = list(source.get("contacts") or [])
        target = adapter.load_contact_log(domain=domain) or {}
        target_contacts = list(target.get("contacts") or [])

        merged_contacts = _merge_contacts(target_contacts, source_contacts)
        merged_dispatches = list(target.get("dispatches") or []) + [
            d for d in (source.get("dispatches") or []) if d not in (target.get("dispatches") or [])
        ]
        print(
            f"  {domain}: doubled={len(source_contacts)} + single={len(target_contacts)} "
            f"-> merged={len(merged_contacts)}"
        )
        if dry_run:
            continue
        payload = dict(target)
        payload["domain"] = domain
        payload["contacts"] = merged_contacts
        payload["dispatches"] = merged_dispatches
        adapter.save_contact_log(domain=domain, payload=payload)
        source_path.rename(source_path.with_suffix(source_path.suffix + ".migrated"))
        migrated += 1

    print(
        f"Done. {'(dry-run) ' if dry_run else ''}migrated {migrated} domain file(s) "
        f"into {private_dir.joinpath(*_NEWSLETTER_SUBPATH)}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return migrate(_resolve_private_dir(args.private_dir), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
