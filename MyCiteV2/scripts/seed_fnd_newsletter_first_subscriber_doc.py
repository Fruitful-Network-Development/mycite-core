"""Seed the first FND-CSM subscriber datum document for one chosen domain.

Uses the ``fnd_newsletter_contact_log`` template via the workbench
mutation lifecycle:

1. Compose a NIMM ``manipulate`` envelope with operation
   ``scaffold_datum``.
2. Run ``run_datum_workbench_mutation_action(action="apply", ...)``
   against the MOS authority DB. The runtime computes the canonical
   ``lv.<msn>.fnd_csm.fnd_newsletter_contact_log_<domain>.<sha>``
   document id, materializes the template's header rows, and persists.
3. Optionally migrate the existing legacy contact log
   (``/srv/webapps/clients/<domain>/contacts/<domain>-contact_log.json``)
   into the freshly minted datum doc by emitting one
   ``insert_datum`` per contact.

Idempotent: if the canonical document already exists, the runtime
reports ``status=already_present`` without writing.

Usage::

    python -m MyCiteV2.scripts.seed_fnd_newsletter_first_subscriber_doc \
        --authority-db /srv/mycite-state/instances/fnd/private/mos_authority.sqlite3 \
        --tenant-id fnd \
        --msn-id 3-2-3-17-77-1-6-4-1-4 \
        --domain trappfamilyfarm.com \
        --webapps-root /srv/webapps \
        --migrate-legacy
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
    run_datum_workbench_mutation_action,
)
from MyCiteV2.packages.state_machine.portal_shell import FND_CSM_SANDBOX_TOKEN

SANDBOX_TOKEN = FND_CSM_SANDBOX_TOKEN
TEMPLATE_ID = "fnd_newsletter_contact_log"
DEFAULT_TENANT_ID = "fnd"
DEFAULT_MSN_ID = "3-2-3-17-77-1-6-4-1-4"


def _canonical_name_for(domain: str) -> str:
    return f"fnd_newsletter_contact_log_{domain.replace('.', '_').replace('-', '_')}"


def _now_utc_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _legacy_contact_log_path(*, webapps_root: Path, domain: str) -> Path:
    return webapps_root / "clients" / domain / "contacts" / f"{domain}-contact_log.json"


def _legacy_contacts(*, webapps_root: Path, domain: str) -> list[dict[str, object]]:
    path = _legacy_contact_log_path(webapps_root=webapps_root, domain=domain)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    contacts = data.get("contacts") if isinstance(data, dict) else None
    return list(contacts or [])


def scaffold_doc(
    *,
    authority_db: Path,
    tenant_id: str,
    msn_id: str,
    domain: str,
) -> dict[str, object]:
    canonical_name = _canonical_name_for(domain)
    document_name = f"fnd-newsletter-contact-log.{domain}.json"
    relative_path = f"sandbox/fnd-csm/{document_name}"
    payload = {
        "target_authority": "datum_workbench",
        "sandbox_id": SANDBOX_TOKEN,
        "operation": "scaffold_datum",
        "template_id": TEMPLATE_ID,
        "msn_id": msn_id,
        "canonical_name": canonical_name,
        "document_name": document_name,
        "relative_path": relative_path,
        "context": {
            "domain": domain,
            "msn_id": msn_id,
            "updated_at": _now_utc_iso(),
        },
    }
    return run_datum_workbench_mutation_action(
        "apply",
        payload,
        authority_db_file=authority_db,
        portal_instance_id=tenant_id,
    )


def migrate_legacy_contacts(
    *,
    authority_db: Path,
    tenant_id: str,
    document_id: str,
    legacy_contacts: list[dict[str, object]],
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for index, contact in enumerate(legacy_contacts, start=1):
        magnitudes = {
            "email": str(contact.get("email") or ""),
            "subscribed": bool(contact.get("subscribed")),
            "source": str(contact.get("source") or ""),
            "last_newsletter_sent_at": str(contact.get("last_newsletter_sent_at") or ""),
            "send_count": int(contact.get("send_count") or 0),
        }
        if contact.get("created_at"):
            magnitudes["created_at"] = str(contact.get("created_at"))
        target_address = f"1-0-{index}"
        raw = [[target_address, "~", "0-0-11"], magnitudes]
        payload = {
            "target_authority": "datum_workbench",
            "sandbox_id": SANDBOX_TOKEN,
            "document_id": document_id,
            "datum_address": target_address,
            "operation": "insert_datum",
            "target_address": target_address,
            "raw": raw,
        }
        result = run_datum_workbench_mutation_action(
            "apply",
            payload,
            authority_db_file=authority_db,
            portal_instance_id=tenant_id,
        )
        results.append({"target_address": target_address, "ok": result.get("ok"), "error": result.get("error")})
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-db", type=Path, required=True)
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    parser.add_argument("--msn-id", default=DEFAULT_MSN_ID)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--webapps-root", type=Path, default=Path("/srv/webapps"))
    parser.add_argument("--migrate-legacy", action="store_true")
    args = parser.parse_args(argv)

    if not args.authority_db.exists():
        raise SystemExit(f"authority db does not exist: {args.authority_db}")

    scaffold_result = scaffold_doc(
        authority_db=args.authority_db,
        tenant_id=args.tenant_id,
        msn_id=args.msn_id,
        domain=args.domain,
    )
    print("scaffold:")
    print(json.dumps(_redacted(scaffold_result), indent=2, default=str))

    if not scaffold_result.get("ok"):
        return 1

    document_id = (scaffold_result.get("preview") or {}).get("document_id") or ""
    status = (scaffold_result.get("preview") or {}).get("status") or ""
    print(f"document_id: {document_id}")
    print(f"status: {status}")

    if args.migrate_legacy and document_id and status != "already_present":
        legacy = _legacy_contacts(webapps_root=args.webapps_root, domain=args.domain)
        if not legacy:
            print(f"no legacy contacts found at {_legacy_contact_log_path(webapps_root=args.webapps_root, domain=args.domain)}")
            return 0
        print(f"migrating {len(legacy)} legacy contacts...")
        migration_results = migrate_legacy_contacts(
            authority_db=args.authority_db,
            tenant_id=args.tenant_id,
            document_id=document_id,
            legacy_contacts=legacy,
        )
        ok_count = sum(1 for r in migration_results if r["ok"])
        fail_count = len(migration_results) - ok_count
        print(f"migration: {ok_count} ok, {fail_count} failed")
        if fail_count:
            for r in migration_results:
                if not r["ok"]:
                    print(f"  FAIL  {r}")
            return 1
    return 0


def _redacted(payload: dict[str, object]) -> dict[str, object]:
    """Trim large updated_document blob from output for legibility."""
    out = dict(payload)
    preview = dict(out.get("preview") or {})
    if "scaffolded_document" in preview:
        preview["scaffolded_document"] = "<elided>"
    out["preview"] = preview
    return out


if __name__ == "__main__":
    raise SystemExit(main())
