"""One-shot migration: split the per-domain newsletter contact logs into the
new store layout.

  ROSTER   (contacts[])   -> per-ENTITY YAML leaflet
                            <webapps_root>/clients/_shared/site-core/contacts/
                                0000-00-00.record-data.<entity>.contacts.yaml
  DISPATCH (dispatches[]) -> STAYS in the legacy per-domain JSON contact log
                            <private>/utilities/tools/aws-csm/newsletter/
                                newsletter.<domain>.contacts.json

For each ``newsletter.<domain>.contacts.json`` we resolve the owning entity
(via the explicit domain->entity map), stamp every contact with its ``domain``,
and MERGE the rows into that entity's YAML leaflet keyed by lowercased email
(later/newer ``updated_at`` wins). Multiple domains can fold into ONE entity
(CVCC owns two) — every row keeps a ``domain`` field so the composed read can
scope back to a single domain.

The JSON log is left in place for dispatch history. With ``--clear-json-contacts``
its ``contacts[]`` is emptied (so the roster has exactly one home); the dispatch
history is always preserved untouched.

Safety:
  * ``--dry-run`` is the DEFAULT — it prints the plan and writes nothing.
  * ``--apply`` performs the writes. Each JSON source is backed up to ``*.bak``
    before any in-place edit.
  * Idempotent: re-running merges the same rows to the same leaflet without
    duplicating (email-keyed) and re-uses the existing ``.bak`` (won't clobber).

Usage:
    python -m MyCiteV2.scripts.migrate_contacts_json_to_yaml \
        [--private-dir PATH] [--webapps-root PATH] \
        [--apply] [--clear-json-contacts]

DO NOT run ``--apply`` against the live tree from an unattended worker — the
real run is a deliberate post-merge operator step.
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

from MyCiteV2.packages.adapters.filesystem.contact_leaflet import (
    ContactLeafletStore,
    entity_for_domain,
    normalized_domain,
)

_NEWSLETTER_SUBPATH = ("utilities", "tools", "aws-csm", "newsletter")


def _resolve_private_dir(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    env_private = os.environ.get("PRIVATE_DIR")
    if env_private:
        return Path(env_private)
    raise SystemExit(
        "Could not resolve the private dir: pass --private-dir or set PRIVATE_DIR."
    )


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _domain_from_filename(path: Path) -> str:
    name = path.name
    token = name.removeprefix("newsletter.").removesuffix(".contacts.json")
    return normalized_domain(token)


def _merge_into(
    by_email: dict[str, dict[str, Any]], rows: list[dict[str, Any]], *, domain: str
) -> None:
    """Merge ``rows`` into ``by_email`` keyed by lowercased email. The row with
    the newer ``updated_at`` wins; every kept row carries its ``domain``."""
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        email = _as_text(raw.get("email")).lower()
        if not email:
            continue
        row = dict(raw)
        row["email"] = email
        row.setdefault("domain", domain)
        if not _as_text(row.get("domain")):
            row["domain"] = domain
        existing = by_email.get(email)
        if existing is None:
            by_email[email] = row
            continue
        # Newer updated_at wins; ties keep the existing.
        if _as_text(row.get("updated_at")) > _as_text(existing.get("updated_at")):
            by_email[email] = row


def run_migration(
    *,
    private_dir: Path,
    webapps_root: Path | None,
    apply: bool,
    clear_json_contacts: bool,
) -> dict[str, Any]:
    """Execute (or plan) the split. Returns a summary dict for logging/tests."""
    newsletter_root = private_dir.joinpath(*_NEWSLETTER_SUBPATH)
    store = ContactLeafletStore(
        private_dir=private_dir, webapps_root=webapps_root
    )

    sources = (
        sorted(newsletter_root.glob("newsletter.*.contacts.json"))
        if newsletter_root.exists()
        else []
    )

    # Group incoming domains by their owning entity so we merge all of an
    # entity's domains into ONE leaflet in a single write.
    per_entity: dict[str, dict[str, dict[str, Any]]] = {}
    domain_to_entity: dict[str, str] = {}
    json_edits: list[Path] = []
    for src in sources:
        domain = _domain_from_filename(src)
        if not domain:
            continue
        entity = entity_for_domain(domain)
        domain_to_entity[domain] = entity
        payload = _load_json(src)
        rows = list(payload.get("contacts") or [])
        # Seed the per-entity bucket with whatever already lives in the leaflet
        # (idempotency: re-running converges instead of dropping prior rows).
        bucket = per_entity.setdefault(entity, {})
        if not bucket:
            _merge_into(
                bucket,
                store.load_roster(entity),
                domain=domain,
            )
        _merge_into(bucket, rows, domain=domain)
        if clear_json_contacts and rows:
            json_edits.append(src)

    summary: dict[str, Any] = {
        "apply": apply,
        "private_dir": str(private_dir),
        "contacts_dir": str(store.contacts_dir),
        "source_count": len(sources),
        "domain_to_entity": domain_to_entity,
        "entities": {},
        "json_backed_up": [],
        "json_contacts_cleared": [],
    }

    for entity, bucket in sorted(per_entity.items()):
        contacts = [bucket[key] for key in sorted(bucket.keys())]
        summary["entities"][entity] = {
            "leaflet": str(store.leaflet_path(entity)),
            "contact_count": len(contacts),
        }
        if apply:
            store.save_roster(entity, contacts)

    if apply:
        for src in json_edits:
            bak = src.with_suffix(src.suffix + ".bak")
            if not bak.exists():
                bak.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                summary["json_backed_up"].append(str(bak))
            payload = _load_json(src)
            payload["contacts"] = []
            tmp = src.with_suffix(src.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            os.replace(str(tmp), str(src))
            summary["json_contacts_cleared"].append(str(src))

    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", default=None)
    parser.add_argument("--webapps-root", default=None)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the writes (default is a dry-run plan only).",
    )
    parser.add_argument(
        "--clear-json-contacts",
        action="store_true",
        help="Empty contacts[] in the JSON log after copying to YAML "
        "(dispatches[] always preserved). Backs up to *.bak first.",
    )
    args = parser.parse_args(argv)

    private_dir = _resolve_private_dir(args.private_dir)
    webapps_root = Path(args.webapps_root) if args.webapps_root else None

    summary = run_migration(
        private_dir=private_dir,
        webapps_root=webapps_root,
        apply=args.apply,
        clear_json_contacts=args.clear_json_contacts,
    )

    mode = "APPLY" if summary["apply"] else "DRY-RUN (no writes)"
    print(f"[migrate_contacts_json_to_yaml] {mode}")
    print(f"  private_dir : {summary['private_dir']}")
    print(f"  contacts_dir: {summary['contacts_dir']}")
    print(f"  sources     : {summary['source_count']}")
    for domain, entity in sorted(summary["domain_to_entity"].items()):
        print(f"    {domain} -> {entity}")
    for entity, info in sorted(summary["entities"].items()):
        print(f"  entity {entity}: {info['contact_count']} contacts -> {info['leaflet']}")
    if summary["json_backed_up"]:
        print(f"  backed up   : {len(summary['json_backed_up'])} JSON file(s)")
    if summary["json_contacts_cleared"]:
        print(f"  cleared json contacts in: {len(summary['json_contacts_cleared'])} file(s)")
    if not summary["apply"]:
        print("  (re-run with --apply to write; --clear-json-contacts to empty JSON contacts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
