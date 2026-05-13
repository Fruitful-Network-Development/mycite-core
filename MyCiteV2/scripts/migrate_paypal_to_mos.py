"""Migrate filesystem PayPal orders + webhook configs into MOS datums.

Reads:
* ``<private>/utilities/tools/paypal-csm/orders.ndjson`` (one NDJSON
  line per order; "domain" field on each row picks the destination
  datum).
* ``<private>/utilities/tools/fnd-csm/paypal-webhook.<msn>.json`` (one
  file per grantee MSN; "webhook_url" field).

Writes:
* ``fnd_paypal_orders_<domain_token>`` datums (up to N most-recent
  orders per domain).
* ``fnd_paypal_webhook_<msn_id_token>`` datums (one per grantee).

Idempotent — re-running with no source changes is a no-op (each datum's
version_hash only advances when its payload differs).

Usage::

    python -m MyCiteV2.scripts.migrate_paypal_to_mos \
        --private-dir /srv/mycite-state/instances/fnd/private \
        [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql.fnd_paypal import (
    ORDERS_MAX_PER_DOMAIN,
    MosDatumPayPalOrdersAdapter,
    MosDatumPayPalWebhookAdapter,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument(
        "--authority-db",
        type=Path,
        default=Path("/srv/mycite-state/instances/fnd/private/mos_authority.sqlite3"),
    )
    parser.add_argument("--tenant-id", default="fnd")
    parser.add_argument("--msn-id", default="3-2-3-17-77-1-6-4-1-4")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    orders_path = args.private_dir / "utilities" / "tools" / "paypal-csm" / "orders.ndjson"
    webhook_dir = args.private_dir / "utilities" / "tools" / "fnd-csm"

    # 1. Orders → per-domain datums (newest first, capped per domain).
    orders_by_domain: dict[str, list[dict[str, object]]] = {}
    if orders_path.exists():
        for line in reversed(orders_path.read_text(encoding="utf-8").splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                order = json.loads(line)
            except json.JSONDecodeError:
                continue
            domain = str(order.get("domain") or "").strip().lower()
            if not domain:
                continue
            bucket = orders_by_domain.setdefault(domain, [])
            if len(bucket) < ORDERS_MAX_PER_DOMAIN:
                bucket.append(order)
    print(f"Orders: {len(orders_by_domain)} domains")
    for domain, orders in sorted(orders_by_domain.items()):
        print(f"  {domain}: {len(orders)} orders")

    # 2. Webhooks → per-MSN datums.
    webhook_paths = sorted(webhook_dir.glob("paypal-webhook.*.json"))
    print(f"\nWebhooks: {len(webhook_paths)} files")
    webhooks: list[tuple[str, str]] = []
    for path in webhook_paths:
        # filename pattern: paypal-webhook.<msn_id>.json
        token = path.name.removeprefix("paypal-webhook.").removesuffix(".json")
        if not token:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        webhook_url = str(payload.get("webhook_url") or "").strip()
        webhooks.append((token, webhook_url))
        print(f"  {token}: {webhook_url}")

    if args.dry_run:
        print("\n--dry-run: not writing")
        return 0

    orders_adapter = MosDatumPayPalOrdersAdapter(
        authority_db_file=args.authority_db,
        tenant_id=args.tenant_id,
        msn_id=args.msn_id,
    )
    for domain, orders in orders_by_domain.items():
        orders_adapter.save_orders(domain=domain, orders=orders)

    webhook_adapter = MosDatumPayPalWebhookAdapter(
        authority_db_file=args.authority_db,
        tenant_id=args.tenant_id,
        msn_id=args.msn_id,
    )
    for msn_id, webhook_url in webhooks:
        webhook_adapter.save_webhook(grantee_msn_id=msn_id, webhook_url=webhook_url)

    print(
        f"\nSeeded: orders={len(orders_by_domain)} domains, webhooks={len(webhooks)} grantees"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
