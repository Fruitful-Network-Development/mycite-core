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

    # onboard-user / onboard-role — writes (or updates) the operator profile
    # JSON, then re-syncs the forwarder routing map so inbound takes effect.
    ou = sub.add_parser("onboard-user",
        help="provision a personal user alias (<user>@<domain> forwarding to a real mailbox)")
    ou.add_argument("--domain", required=True)
    ou.add_argument("--user", required=True, help="local-part (firstname); becomes <user>@<domain>")
    ou.add_argument("--forward-to", required=True, help="real mailbox to forward inbound to")
    ou.add_argument("--display-name", default="", help="human name for the From: display, optional")
    ou.add_argument("--tenant-slug", default=None,
        help="short bucket name (e.g. cvccboard); auto-derived from existing profiles on the same domain; required for the first user on a new client")

    orole = sub.add_parser("onboard-role",
        help="provision a role alias (admin/info/support/...) per the email convention")
    orole.add_argument("--domain", required=True)
    orole.add_argument("--role", required=True,
        choices=["postmaster", "abuse", "info", "admin", "support",
                 "noreply", "news", "donate", "sales", "webmaster"],
        help="RFC 2142 / convention role; see docs/email_convention.md")
    orole.add_argument("--forward-to", required=True)
    orole.add_argument("--tenant-slug", default=None,
        help="see --tenant-slug on onboard-user")

    # issue-smtp-credentials — requires iam:CreateUser/CreateAccessKey/PutUserPolicy,
    # which the EC2 instance role does NOT have by design. Run from a session
    # with broader IAM (your local console + admin profile). The output packet
    # is operator-private and is NEVER committed.
    isc = sub.add_parser("issue-smtp-credentials",
        help="create per-user IAM + SES SMTP credentials for Send-As (requires iam:*)")
    isc.add_argument("--address", required=True, help="e.g. marilyn@cvccboard.org")
    isc.add_argument("--region", default="us-east-1")
    isc.add_argument("--packet-dir", default=None,
        help="dir to write the packet; default /srv/agentic/evidence/SMTP-Creds-<address>-<date>/")

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
    if args.command == "onboard-user":
        from .onboard import onboard_alias
        result = onboard_alias(
            adapter=adapter, store=store, kind="user",
            domain=args.domain, local=args.user,
            forward_to=args.forward_to, display_name=args.display_name,
            tenant_slug=args.tenant_slug,
        )
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "onboard-role":
        from .onboard import onboard_alias
        result = onboard_alias(
            adapter=adapter, store=store, kind="role",
            domain=args.domain, local=args.role,
            forward_to=args.forward_to, display_name="",
            tenant_slug=args.tenant_slug,
        )
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "issue-smtp-credentials":
        from .onboard import issue_smtp_credentials, OperatorIamRequiredError
        try:
            result = issue_smtp_credentials(
                address=args.address, region=args.region, packet_dir=args.packet_dir,
            )
        except OperatorIamRequiredError as exc:
            # Clean output — no traceback. The exception body IS the
            # paste-and-run snippet operator needs.
            print("# Cannot issue SMTP credentials from this session — IAM perms missing.\n", file=sys.stderr)
            print(str(exc), file=sys.stderr)
            return 3
        # Print everything but the secret — that lives in the packet file only.
        safe = {k: v for k, v in result.items() if k != "smtp_password"}
        print(json.dumps(safe, indent=2))
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
