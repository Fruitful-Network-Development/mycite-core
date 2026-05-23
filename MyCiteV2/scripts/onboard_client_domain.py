#!/usr/bin/env python3
"""One-shot client-domain onboarding orchestrator (C4).

Runs the full provisioning sequence for a new client domain that the
operator previously had to do by hand across the AWS console + several
manual portal/CLI steps:

    1. ensure_domain_identity      — SES domain identity + DKIM
    2. sync_domain_dns             — MX / SPF / DMARC(p=none) / DKIM CNAMEs
                                     + custom MAIL FROM (C1)
    3. ensure_domain_receipt_rule  — inbound capture → S3 + forwarder Lambda
    4. sync_operator_forwarding_routes — refresh FORWARD_TO_MAP_JSON

Then prints a checklist of the steps that still need a human (the SES
verification-email click, DNS propagation wait, DMARC ramp later).

USAGE
-----
    # Dry run — print the planned AWS calls, touch nothing.
    python3 -m MyCiteV2.scripts.onboard_client_domain \
        --domain example.org --tenant acme --dry-run

    # Apply.
    python3 -m MyCiteV2.scripts.onboard_client_domain \
        --domain example.org --tenant acme --apply

PREREQUISITES
-------------
- A Route53 hosted zone for <domain> must already exist (this script does
  NOT create zones — domain registration / delegation is out of scope).
- The EC2 role's existing SES + Route53 + Lambda grants.

DESIGN
------
Each step is wrapped so a failure in one is reported but does not abort the
others — the operator gets a full status table, not a half-finished domain
with an opaque traceback. ``--dry-run`` short-circuits before every mutating
call and records what *would* run (honoring active-task guardrail G-4: AWS
writes are dry-run-loggable before execution).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _step(
    name: str,
    fn,
    *,
    dry_run: bool,
    dry_run_summary: str,
) -> dict[str, Any]:
    """Run one onboarding step, returning a uniform status dict.

    In dry-run mode the step is not executed; ``dry_run_summary`` describes
    what would happen.
    """
    if dry_run:
        return {"step": name, "status": "dry_run", "detail": dry_run_summary}
    try:
        result = fn()
        ok = bool(result.get("ok", True)) if isinstance(result, dict) else True
        return {
            "step": name,
            "status": "ok" if ok else "failed",
            "detail": result if isinstance(result, dict) else {"result": str(result)},
        }
    except Exception as exc:  # noqa: BLE001 — report, don't abort the sequence
        return {"step": name, "status": "error", "detail": str(exc)}


def run_onboarding(
    *,
    domain: str,
    tenant: str,
    dry_run: bool,
    adapter: Any | None = None,
) -> list[dict[str, Any]]:
    """Execute (or dry-run) the onboarding sequence. Returns the per-step
    status list. ``adapter`` is injectable for testing; defaults to a real
    AwsPeripheralCloudAdapter."""
    if adapter is None:
        from MyCiteV2.packages.peripherals.aws import AwsPeripheralCloudAdapter
        adapter = AwsPeripheralCloudAdapter()

    tags = {"tenant": tenant} if tenant else None

    steps: list[dict[str, Any]] = []
    steps.append(_step(
        "ensure_domain_identity",
        lambda: adapter.ensure_domain_identity(domain, tags=tags),
        dry_run=dry_run,
        dry_run_summary=f"SES verify_domain_identity + DKIM for {domain}"
        + (f"; tag tenant={tenant}" if tenant else ""),
    ))
    steps.append(_step(
        "sync_domain_dns",
        lambda: adapter.sync_domain_dns(domain, tags=tags),
        dry_run=dry_run,
        dry_run_summary=(
            f"Route53 MX/SPF/DMARC(p=none)/DKIM + custom MAIL FROM "
            f"(mail.{domain}) for {domain}"
        ),
    ))
    steps.append(_step(
        "ensure_domain_receipt_rule",
        lambda: adapter.ensure_domain_receipt_rule(domain, tags=tags),
        dry_run=dry_run,
        dry_run_summary=f"SES inbound receipt rule → S3 + forwarder for {domain}",
    ))
    steps.append(_step(
        "sync_operator_forwarding_routes",
        lambda: adapter.sync_operator_forwarding_routes(dry_run=False),
        dry_run=dry_run,
        dry_run_summary="refresh ses-forwarder FORWARD_TO_MAP_JSON",
    ))
    return steps


_NEXT_STEPS_CHECKLIST = """
Operator next steps (not automatable from this host):
  [ ] Click the SES domain-verification email if SES sent one (only on the
      very first identity for a brand-new domain). Verification is usually
      automatic via the DKIM CNAMEs + the MX once DNS propagates.
  [ ] Wait for DNS propagation (DKIM + MAIL FROM verification flips to
      "Success" in the SES console within ~15-60 min).
  [ ] Create the per-mailbox operator-profile JSON(s) under
      deployed/<grantee>/private/utilities/tools/aws-csm/ (or via the
      portal email tab) so FORWARD_TO_MAP_JSON gets the send-as → inbox
      routes. Re-run sync_operator_forwarding_routes after.
  [ ] DMARC ramp: leave p=none for >= 1 week, confirm >=95% alignment in
      the aggregate reports, THEN ramp to p=quarantine pct=20 (never jump
      straight to p=reject). Tracked separately — see
      TASK-FND-DMARC-RAMP-* if present.
"""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--domain", required=True, help="Client domain to onboard.")
    parser.add_argument(
        "--tenant", default="",
        help="Short tenant tag (msn short_name) applied to created resources.",
    )
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--dry-run", action="store_true",
                     help="Print the planned AWS calls and exit. No mutations.")
    grp.add_argument("--apply", action="store_true", help="Execute the sequence.")
    args = parser.parse_args(argv)

    steps = run_onboarding(
        domain=args.domain, tenant=args.tenant, dry_run=args.dry_run,
    )

    print(f"\nOnboarding {'(DRY RUN) ' if args.dry_run else ''}{args.domain}:")
    any_failed = False
    for s in steps:
        marker = {"ok": "✓", "dry_run": "•", "failed": "✗", "error": "✗"}.get(
            s["status"], "?"
        )
        print(f"  {marker} {s['step']}: {s['status']}")
        if s["status"] in ("failed", "error"):
            any_failed = True
            print(f"      detail: {s['detail']}")
    print(_NEXT_STEPS_CHECKLIST)
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
