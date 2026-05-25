"""Import Trapp Family Farm contacts from the operator's exported CSV
into the FND portal's per-domain newsletter contact log.

Source : ``/srv/webapps/clients/trappfamilyfarm.com/frontend/<csv>``
         (4-column export: First / Middle / Last / E-mail 1 - Value)
Target : ``<private>/utilities/tools/aws-csm/newsletter/newsletter.trappfamilyfarm.com.contacts.json``
         — same JSON the ``/__fnd/contacts/list`` route reads to feed the
         dashboard Contacts tab.

Why this is needed: the dashboard Contacts tab reads the per-domain
newsletter contact log via the ``FilesystemNewsletterStateAdapter``.
When the operator restored a previously-archived address book to the
client site as a CSV under ``frontend/``, the dashboard kept showing
only the live newsletter signups (the 2 existing rows) because nothing
copied the CSV rows into the contact log JSON. This importer closes
that loop.

Strictly additive: contacts already in the log are left alone (no field
overwrites). New CSV rows are appended with ``source=csv_import_2026-05-02``
and ``subscribed=false`` so they show up in the dashboard address book
without being treated as opt-in subscribers for newsletter sends.

CSV quirks handled:
* Many rows have the email duplicated in the "First Name" field (a CRM
  export artefact). Those are detected via ``"@" in first_name`` and the
  first_name is treated as empty so the contact gets just the email
  (not the email-as-first-name).
* Rows where every column is blank or whose email is malformed are
  dropped.
* Internal duplicates within the CSV (~7 in the current export) are
  deduped by lowercased email.

Usage::

    python -m MyCiteV2.scripts.tff_contacts_import_from_csv --dry-run
    python -m MyCiteV2.scripts.tff_contacts_import_from_csv
    python -m MyCiteV2.scripts.tff_contacts_import_from_csv \\
        --csv <path> --domain trappfamilyfarm.com --private-dir <path>
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem.newsletter_state import (
    FilesystemNewsletterStateAdapter,
)

DEFAULT_CSV = Path(
    "/srv/webapps/clients/trappfamilyfarm.com/frontend/"
    "2026-05-02.artifact-table.trapp_family_farm.contacts.csv"
)
DEFAULT_DOMAIN = "trappfamilyfarm.com"
DEFAULT_PRIVATE_DIR = Path("/srv/webapps/mycite/fnd/private")
DEFAULT_SOURCE = "csv_import_2026-05-02"

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def _norm(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _norm_email(value: object) -> str:
    """Lowercased, trimmed email; empty if it doesn't match a basic
    user@host.tld shape."""
    text = _norm(value).lower()
    if not text or not _EMAIL_RE.match(text):
        return ""
    return text


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_contact(
    row: dict[str, str], *, source: str, now_iso: str,
) -> dict[str, Any] | None:
    """Convert one CSV row → contact-log record, or None if unusable."""
    raw_first = _norm(row.get("First Name"))
    middle = _norm(row.get("Middle Name"))
    last = _norm(row.get("Last Name"))
    email_col = _norm(row.get("E-mail 1 - Value"))

    # CRM export artefact: many rows put the email into the First Name
    # field. If first_name looks like an email, drop it (the canonical
    # email is in the dedicated column).
    first = "" if "@" in raw_first else raw_first

    # Some rows have only an email in First Name and a blank E-mail
    # column. Fall back so we don't lose them.
    email = _norm_email(email_col) or _norm_email(raw_first)
    if not email:
        return None

    parts = [p for p in (first, middle, last) if p]
    name = " ".join(parts)
    return {
        "email": email,
        "name": name,
        "first_name": first,
        "middle_name": middle,
        "last_name": last,
        "phone": "",
        "zip": "",
        "subscribed": False,
        "source": source,
        "signup_date": now_iso[:10],
        "created_at": now_iso,
        "updated_at": now_iso,
        "subscribed_at": "",
        "unsubscribed_at": "",
        "last_newsletter_sent_at": "",
        "send_count": 0,
        "notes": "",
        "forward_status": "",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--domain", default=DEFAULT_DOMAIN)
    parser.add_argument("--private-dir", type=Path, default=DEFAULT_PRIVATE_DIR)
    parser.add_argument("--source", default=DEFAULT_SOURCE,
                        help="Value to stamp on imported rows' `source` field.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report counts without writing.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if not args.csv.exists():
        print(f"ERROR: CSV not found at {args.csv}", file=sys.stderr)
        return 2
    if not args.private_dir.exists():
        print(f"ERROR: private dir not found at {args.private_dir}", file=sys.stderr)
        return 2

    adapter = FilesystemNewsletterStateAdapter(args.private_dir)
    log = adapter.load_contact_log(domain=args.domain)
    if not log:
        # Empty / unbootstrapped log — start from a minimal shape; the
        # adapter's save will stamp the v2 schema + domain on write.
        log = {"contacts": [], "dispatches": [], "domain": args.domain}
    existing = list(log.get("contacts") or [])
    by_email: dict[str, dict[str, Any]] = {
        _norm_email(c.get("email")): c
        for c in existing
        if isinstance(c, dict) and _norm_email(c.get("email"))
    }
    print(f"contact log loaded: {len(existing)} existing contacts at "
          f"{adapter._contacts_path(args.domain)}")

    n_total = 0
    n_unusable = 0
    n_already = 0
    n_csv_dupe = 0
    n_added = 0
    now_iso = _now_iso()
    pending_emails: set[str] = set()
    new_records: list[dict[str, Any]] = []

    with args.csv.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row_idx, row in enumerate(reader, start=2):  # row 1 = header
            n_total += 1
            contact = _row_to_contact(row, source=args.source, now_iso=now_iso)
            if contact is None:
                n_unusable += 1
                if args.verbose:
                    print(f"row {row_idx}: skipped (no usable email) {row}")
                continue
            email = contact["email"]
            if email in by_email:
                n_already += 1
                if args.verbose:
                    print(f"row {row_idx}: already in log → {email}")
                continue
            if email in pending_emails:
                n_csv_dupe += 1
                if args.verbose:
                    print(f"row {row_idx}: duplicate inside CSV → {email}")
                continue
            pending_emails.add(email)
            new_records.append(contact)
            n_added += 1

    if not args.dry_run:
        existing.extend(new_records)
        log["contacts"] = existing
        log["updated_at"] = now_iso
        adapter.save_contact_log(domain=args.domain, payload=log)

    print()
    print(f"CSV rows scanned         : {n_total}")
    print(f"  unusable (no email)    : {n_unusable}")
    print(f"  already in contact log : {n_already}")
    print(f"  duplicate inside CSV   : {n_csv_dupe}")
    print(f"  {'would add (dry-run)' if args.dry_run else 'added                 '}: {n_added}")
    if not args.dry_run:
        final = adapter.load_contact_log(domain=args.domain)
        print(f"  contact log now holds  : {len(final.get('contacts') or [])} rows")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
