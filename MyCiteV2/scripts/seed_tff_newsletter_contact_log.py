"""Seed the TFF (or any domain's) newsletter contact log datum from a CSV.

Pipeline:

1. Load the ``fnd_newsletter_contact_log`` template from the registry.
2. Run the template's ``csv_intake_pipeline`` over each CSV row to
   produce a list of v2 magnitudes (with bacillete-encoded binary forms
   and ``*_confirmed`` flags).
3. Build a ``contact_log`` payload in the legacy shape that
   ``MosDatumNewsletterContactLogAdapter.save_contact_log`` accepts.
4. Save via the adapter — which atomically replaces any prior version
   of the canonical ``fnd_newsletter_contact_log_<domain_token>``
   document.

Usage::

    python -m MyCiteV2.scripts.seed_tff_newsletter_contact_log \
        --authority-db /srv/mycite-state/instances/fnd/private/mos_authority.sqlite3 \
        --csv "/srv/webapps/clients/trappfamilyfarm.com/contacts/contacts 05022026.csv" \
        --domain trappfamilyfarm.com \
        --msn-id 3-2-3-17-77-1-6-4-1-4 \
        [--replace-existing] [--dry-run]

The ``--replace-existing`` flag is implicit in ``save_contact_log``;
the script accepts it for documentation parity with the bootstrap
script.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql.newsletter_contact_log import (
    MosDatumNewsletterContactLogAdapter,
)
from MyCiteV2.packages.core.datum_templates import TemplateRegistry
from MyCiteV2.packages.core.datum_templates.csv_intake import import_csv_via_template

DEFAULT_TENANT_ID = "fnd"
DEFAULT_MSN_ID = "3-2-3-17-77-1-6-4-1-4"


def _utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-db", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--msn-id", default=DEFAULT_MSN_ID)
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    parser.add_argument("--template-id", default="fnd_newsletter_contact_log")
    parser.add_argument("--replace-existing", action="store_true",
                        help="Documentation flag (save always replaces).")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.authority_db.exists():
        raise SystemExit(f"authority db not found: {args.authority_db}")
    if not args.csv.exists():
        raise SystemExit(f"csv not found: {args.csv}")

    registry = TemplateRegistry()
    template = registry.get(args.template_id)
    if template is None:
        raise SystemExit(f"template not found: {args.template_id}")
    if not template.csv_intake_pipeline:
        raise SystemExit(
            f"template {args.template_id!r} has no csv_intake_pipeline; "
            "use the v2 template definition."
        )

    intake = import_csv_via_template(template, args.csv)
    print(f"CSV intake from {args.csv}")
    print(f"  template:        {args.template_id}")
    print(f"  rows accepted:   {len(intake.new_rows)}")
    print(f"  rows skipped:    {len(intake.skipped_csv_rows)}")
    if intake.warnings:
        warning_summary: dict[str, int] = {}
        for w in intake.warnings:
            key = w.split(":", 1)[0]
            warning_summary[key] = warning_summary.get(key, 0) + 1
        print("  warning kinds:")
        for kind, count in sorted(warning_summary.items()):
            print(f"    {kind}: {count}")

    contacts = []
    for row in intake.new_rows:
        magnitudes = row.raw[1] if isinstance(row.raw, list) and len(row.raw) >= 2 else {}
        if isinstance(magnitudes, dict):
            # Phase 15b: persist the split first/middle/last names from
            # the CSV alongside the composed ``name`` token. The adapter
            # writes both back into the magnitudes datum.
            contacts.append(
                {
                    "email": magnitudes.get("email_ascii", ""),
                    "name": magnitudes.get("name_ascii", ""),
                    "first_name": magnitudes.get("first_name_ascii", ""),
                    "middle_name": magnitudes.get("middle_name_ascii", ""),
                    "last_name": magnitudes.get("last_name_ascii", ""),
                    # Phase 16a: phone + zip + signup_date come from the
                    # template's default_field_values + (when present)
                    # CSV column mapping.
                    "phone": magnitudes.get("phone_ascii", ""),
                    "zip": magnitudes.get("zip_ascii", ""),
                    "signup_date": magnitudes.get("signup_date", ""),
                    "subscribed": bool(magnitudes.get("subscribed", True)),
                    "source": magnitudes.get("source", "csv_import"),
                    "send_count": int(magnitudes.get("send_count") or 0),
                    "last_newsletter_sent_at": magnitudes.get("last_newsletter_sent_at", ""),
                    "created_at": magnitudes.get("created_at") or _utc_now_iso(),
                }
            )

    payload = {
        "domain": args.domain,
        "msn_id": args.msn_id,
        "contacts": contacts,
        "dispatches": [],
        "updated_at": _utc_now_iso(),
    }
    print(f"  contacts to persist: {len(contacts)}")

    if args.dry_run:
        print("--dry-run: not writing to MOS")
        return 0

    adapter = MosDatumNewsletterContactLogAdapter(
        authority_db_file=args.authority_db,
        tenant_id=args.tenant_id,
        msn_id=args.msn_id,
    )
    saved = adapter.save_contact_log(domain=args.domain, payload=payload)
    print(f"\nSaved. New row count in datum: {len(saved.get('contacts', []))}")
    # Resolve the new document_id
    doc = adapter._find_document(domain=args.domain)  # type: ignore[attr-defined]
    if doc is not None:
        print(f"document_id: {doc.document_id}")
        print(f"row_count:   {doc.row_count}  (4 header + {len(saved.get('contacts', []))} contacts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
