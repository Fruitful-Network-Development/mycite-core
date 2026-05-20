"""AWS peripheral CLI.

Examples:
    python -m MyCiteV2.packages.peripherals.aws.cli sync-forwarding-routes [--dry-run]
    python -m MyCiteV2.packages.peripherals.aws.cli describe-profile aws-csm.fnd.dylan
    python -m MyCiteV2.packages.peripherals.aws.cli describe-domain fruitfulnetworkdevelopment.com
    python -m MyCiteV2.packages.peripherals.aws.cli ensure-domain-identity brockspressurewashing.com
    python -m MyCiteV2.packages.peripherals.aws.cli sync-domain-dns brockspressurewashing.com
    python -m MyCiteV2.packages.peripherals.aws.cli ensure-domain-receipt-rule brockspressurewashing.com
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .cloud_adapter import AwsPeripheralCloudAdapter
from .profile_store import ProfileStore


def _adapter(grantee: str, profile_root: Path | None) -> AwsPeripheralCloudAdapter:
    store = ProfileStore(grantee=grantee, root=profile_root) if profile_root else ProfileStore(grantee=grantee)
    return AwsPeripheralCloudAdapter(profile_store=store)


def main() -> int:
    parser = argparse.ArgumentParser(description="AWS peripheral CLI")
    parser.add_argument("--grantee", default="fnd", help="grantee slug (default: fnd)")
    parser.add_argument(
        "--profile-root",
        type=Path,
        default=None,
        help="override profile dir (otherwise derived from --grantee)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("sync-forwarding-routes")
    s.add_argument("--dry-run", action="store_true")

    sub.add_parser("list-profiles")
    p = sub.add_parser("describe-profile")
    p.add_argument("profile_id")
    d = sub.add_parser("describe-domain")
    d.add_argument("domain")
    e = sub.add_parser("ensure-domain-identity")
    e.add_argument("domain")
    n = sub.add_parser("sync-domain-dns")
    n.add_argument("domain")
    r = sub.add_parser("ensure-domain-receipt-rule")
    r.add_argument("domain")

    args = parser.parse_args()
    adapter = _adapter(args.grantee, args.profile_root)
    store = adapter._profiles  # type: ignore[attr-defined]

    if args.command == "sync-forwarding-routes":
        result = adapter.sync_operator_forwarding_routes(dry_run=args.dry_run)
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "list-profiles":
        rows = []
        for profile in store.list_profiles():
            ident = profile.get("identity") or {}
            inbound = profile.get("inbound") or {}
            rows.append(
                {
                    "profile_id": ident.get("profile_id"),
                    "send_as": ident.get("send_as_email"),
                    "target": inbound.get("receive_routing_target")
                    or ident.get("operator_inbox_target"),
                    "lifecycle": (profile.get("workflow") or {}).get("lifecycle_state"),
                }
            )
        print(json.dumps(rows, indent=2))
        return 0
    if args.command == "describe-profile":
        profile = store.get_profile(args.profile_id)
        if not profile:
            print(json.dumps({"error": "profile_not_found", "profile_id": args.profile_id}))
            return 2
        print(json.dumps(adapter.describe_profile_readiness(profile), indent=2))
        return 0
    if args.command == "describe-domain":
        print(json.dumps(adapter.describe_domain_status(args.domain), indent=2))
        return 0
    if args.command == "ensure-domain-identity":
        print(json.dumps(adapter.ensure_domain_identity(args.domain), indent=2))
        return 0
    if args.command == "sync-domain-dns":
        print(json.dumps(adapter.sync_domain_dns(args.domain), indent=2))
        return 0
    if args.command == "ensure-domain-receipt-rule":
        print(json.dumps(adapter.ensure_domain_receipt_rule(args.domain), indent=2))
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
