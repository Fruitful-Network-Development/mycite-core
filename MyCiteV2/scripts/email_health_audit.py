#!/usr/bin/env python3
"""Daily email-deliverability health audit.

Runs the full set of state checks that, taken together, make sure the
email plumbing for every client domain stays healthy:

  1. ses-forwarder routing-map drift — the on-disk operator profiles
     under /srv/webapps/mycite/fnd/private/utilities/tools/aws-csm/
     are the canonical source for the Lambda's FORWARD_TO_MAP_JSON.
     Drift means messages to one or more aliases are being captured
     to S3 but never forwarded (the exact failure mode that ate 11
     days of cvccboard.org mail on 2026-05-30).
  2. DNS state for every managed domain — SPF on the root, custom
     MAIL FROM (TXT + MX on mail.<domain>), DMARC at p=quarantine
     with strict alignment, inbound MX on the root. Catches accidental
     DNS reverts.
  3. SES identity state — domain verification, DKIM verification,
     MAIL FROM verification. Catches the SES side losing trust.
  4. Sending reputation — bounce + complaint rate over the last 14
     days against AWS's review thresholds (5% bounce / 0.1% complaint).

Exit code is the number of failing checks (0 = all clean). Failures
also trigger an SES alert email to dylan@fruitfulnetworkdevelopment.com
from alerts@fruitfulnetworkdevelopment.com with the full diagnostic
body.

Intended to run from a systemd timer (email-health-audit.timer) once
per day. The drift checks here are the same shape as the in-deploy
smoke gate added in webDZ 7131254; the deploy gate catches drift at
push time, this catches drift in the 24h between pushes. Defence in
depth.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Imports deferred so the bare --help / import audit still works under
# environments without boto3 installed.

MANAGED_DOMAINS = [
    "fruitfulnetworkdevelopment.com",
    "cuyahogavalleycountrysideconservancy.org",
    "cvccboard.org",
    "brockspressurewashing.com",
    "trappfamilyfarm.com",
]

# Expected DNS record substrings; full equality would be brittle (DKIM
# tokens are domain-specific). We check the presence of each invariant.
EXPECTED_ROOT_SPF       = "v=spf1 include:amazonses.com"
EXPECTED_MAILFROM_SPF   = "v=spf1 include:amazonses.com"
EXPECTED_MAILFROM_MX    = "feedback-smtp.us-east-1.amazonses.com"
EXPECTED_INBOUND_MX     = "inbound-smtp.us-east-1.amazonaws.com"
# DMARC is checked tag-by-tag (see check_dns) rather than by substring —
# substring matching conflated p= with sp= (a revert to p=none while
# sp=quarantine remained would falsely pass) and demanded an sp= tag that
# is optional per RFC 7489 (it inherits p when absent).

# AWS publishes review thresholds at 5% bounce / 0.1% complaint —
# we alert below those (3% / 0.05%) so we have headroom to investigate
# before AWS pauses the account.
BOUNCE_ALERT_PCT     = 3.0
COMPLAINT_ALERT_PCT  = 0.05

ALERT_FROM = "alerts@fruitfulnetworkdevelopment.com"
ALERT_TO   = "dylan@fruitfulnetworkdevelopment.com"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""

@dataclass
class AuditReport:
    results: list[CheckResult] = field(default_factory=list)
    def add(self, r: CheckResult) -> None: self.results.append(r)
    @property
    def failed(self) -> list[CheckResult]:
        return [r for r in self.results if not r.ok]
    @property
    def passed(self) -> list[CheckResult]:
        return [r for r in self.results if r.ok]


# ---------------------------------------------------------------------------
# 1. Forwarder routing-map drift

def check_forwarder_map(report: AuditReport) -> None:
    """Dry-run sync-forwarding-routes; fail if route_changed True."""
    try:
        out = subprocess.run(
            [sys.executable, "-m", "MyCiteV2.packages.peripherals.aws.cli",
             "--grantee", "fnd", "sync-forwarding-routes", "--dry-run"],
            capture_output=True, text=True, check=False, timeout=60,
            env={**os.environ, "PYTHONPATH": "/srv/repo/mycite-core"},
        )
    except subprocess.TimeoutExpired as exc:
        report.add(CheckResult("forwarder-map", False, f"timeout: {exc}"))
        return
    if out.returncode != 0:
        report.add(CheckResult("forwarder-map", False, f"cli exit {out.returncode}: {out.stderr[:400]}"))
        return
    try:
        data = json.loads(out.stdout)
    except Exception:
        # Tolerate a stray log/deprecation line on stdout: parse the JSON
        # object span rather than assuming stdout is pure JSON.
        start, end = out.stdout.find("{"), out.stdout.rfind("}")
        try:
            data = json.loads(out.stdout[start:end + 1]) if 0 <= start < end else {}
        except Exception as exc:
            report.add(CheckResult("forwarder-map", False, f"unparseable cli output: {exc}: {out.stdout[:200]}"))
            return
    if data.get("route_changed"):
        report.add(CheckResult(
            "forwarder-map", False,
            f"live FORWARD_TO_MAP_JSON drifts from on-disk profiles "
            f"(route_count={data.get('route_count')}). "
            f"Recover with: PYTHONPATH=/srv/repo/mycite-core "
            f"/srv/venvs/fnd_portal/bin/python -m "
            f"MyCiteV2.packages.peripherals.aws.cli --grantee fnd "
            f"sync-forwarding-routes",
        ))
    else:
        report.add(CheckResult("forwarder-map", True,
            f"in sync ({data.get('route_count')} routes)"))


# ---------------------------------------------------------------------------
# 2. DNS state per domain

def _dig_txt(name: str) -> list[str]:
    try:
        out = subprocess.run(["dig", "+short", "TXT", name],
            capture_output=True, text=True, check=False, timeout=10).stdout.strip()
    except Exception:
        return []
    return [line.strip().strip('"') for line in out.splitlines() if line.strip()]


def _dig_mx(name: str) -> list[str]:
    try:
        out = subprocess.run(["dig", "+short", "MX", name],
            capture_output=True, text=True, check=False, timeout=10).stdout.strip()
    except Exception:
        return []
    return [line.strip().rstrip(".") for line in out.splitlines() if line.strip()]


def check_dns(report: AuditReport) -> None:
    for domain in MANAGED_DOMAINS:
        issues: list[str] = []

        root_txt = _dig_txt(domain)
        if not any(EXPECTED_ROOT_SPF in t for t in root_txt):
            issues.append(f"root SPF missing/changed: {root_txt!r}")

        mf_txt = _dig_txt(f"mail.{domain}")
        if not any(EXPECTED_MAILFROM_SPF in t for t in mf_txt):
            issues.append(f"mail.{domain} SPF missing/changed: {mf_txt!r}")
        mf_mx = _dig_mx(f"mail.{domain}")
        if not any(EXPECTED_MAILFROM_MX in m for m in mf_mx):
            issues.append(f"mail.{domain} MX missing/changed: {mf_mx!r}")

        inbound_mx = _dig_mx(domain)
        if not any(EXPECTED_INBOUND_MX in m for m in inbound_mx):
            issues.append(f"inbound MX missing/changed: {inbound_mx!r}")

        # Tag-aware DMARC parse — reuse the same parser the adapter uses so
        # the audit and the live deliverability ramp agree on tag semantics.
        from MyCiteV2.packages.peripherals.aws.dmarc_ramp import parse_dmarc_policy
        dmarc = _dig_txt(f"_dmarc.{domain}")
        tags: dict[str, str] = {}
        for record in dmarc:
            parsed = parse_dmarc_policy(record)
            if parsed:
                tags = parsed
                break
        if not tags:
            issues.append(f"DMARC record missing/unparseable: {dmarc!r}")
        else:
            p = tags.get("p", "").lower()
            if p not in ("quarantine", "reject"):
                issues.append(f"DMARC policy p={p or 'absent'} (want quarantine/reject)")
            # sp is OPTIONAL (inherits p when absent); only flag an explicit
            # sp that weakens enforcement below quarantine.
            sp = tags.get("sp")
            if sp is not None and sp.lower() not in ("quarantine", "reject"):
                issues.append(f"DMARC subdomain policy sp={sp} weaker than quarantine")
            if tags.get("adkim", "").lower() != "s":
                issues.append("DMARC strict DKIM alignment (adkim=s) missing")
            if tags.get("aspf", "").lower() != "s":
                issues.append("DMARC strict SPF alignment (aspf=s) missing")

        if issues:
            report.add(CheckResult(f"dns:{domain}", False, "; ".join(issues)))
        else:
            report.add(CheckResult(f"dns:{domain}", True, "all records correct"))


# ---------------------------------------------------------------------------
# 3. SES identity state

def check_ses_identities(report: AuditReport) -> None:
    import boto3
    ses = boto3.client("ses", region_name="us-east-1")
    try:
        verif = ses.get_identity_verification_attributes(Identities=MANAGED_DOMAINS).get("VerificationAttributes", {})
        dkim  = ses.get_identity_dkim_attributes(Identities=MANAGED_DOMAINS).get("DkimAttributes", {})
        mfm   = ses.get_identity_mail_from_domain_attributes(Identities=MANAGED_DOMAINS).get("MailFromDomainAttributes", {})
    except Exception as exc:
        report.add(CheckResult("ses-identities", False, f"SES describe failed: {exc}"))
        return
    for domain in MANAGED_DOMAINS:
        problems = []
        v_status = (verif.get(domain) or {}).get("VerificationStatus")
        if v_status != "Success":
            problems.append(f"verification={v_status!r}")
        d_status = (dkim.get(domain) or {}).get("DkimVerificationStatus")
        if d_status != "Success":
            problems.append(f"dkim={d_status!r}")
        if not (dkim.get(domain) or {}).get("DkimEnabled"):
            problems.append("dkim_disabled")
        mfm_status = (mfm.get(domain) or {}).get("MailFromDomainStatus")
        if mfm_status != "Success":
            problems.append(f"mail_from={mfm_status!r}")
        if problems:
            report.add(CheckResult(f"ses-identity:{domain}", False, ", ".join(problems)))
        else:
            report.add(CheckResult(f"ses-identity:{domain}", True, "verified + dkim + mail-from"))


# ---------------------------------------------------------------------------
# 4. Sending reputation (bounce + complaint over 14d)

def check_reputation(report: AuditReport) -> None:
    import boto3
    ses = boto3.client("ses", region_name="us-east-1")
    try:
        stats = ses.get_send_statistics().get("SendDataPoints", [])
    except Exception as exc:
        report.add(CheckResult("ses-reputation", False, f"get_send_statistics failed: {exc}"))
        return
    sent = sum(p.get("DeliveryAttempts", 0) for p in stats)
    bounces = sum(p.get("Bounces", 0) for p in stats)
    complaints = sum(p.get("Complaints", 0) for p in stats)
    if sent == 0:
        report.add(CheckResult("ses-reputation", True, "no sends in 14d (no signal — clean)"))
        return
    bounce_pct = bounces * 100.0 / sent
    complaint_pct = complaints * 100.0 / sent
    problems = []
    if bounce_pct >= BOUNCE_ALERT_PCT:
        problems.append(f"bounce {bounce_pct:.2f}% >= {BOUNCE_ALERT_PCT}%")
    if complaint_pct >= COMPLAINT_ALERT_PCT:
        problems.append(f"complaint {complaint_pct:.3f}% >= {COMPLAINT_ALERT_PCT}%")
    if problems:
        report.add(CheckResult("ses-reputation", False,
            f"{sent} sends/14d, " + "; ".join(problems)))
    else:
        report.add(CheckResult("ses-reputation", True,
            f"{sent} sends/14d, bounce {bounce_pct:.2f}%, complaint {complaint_pct:.3f}%"))


# ---------------------------------------------------------------------------
# Alert dispatcher (SES, eats own dog food)

def send_alert(report: AuditReport) -> None:
    import boto3
    if not report.failed:
        return
    body_lines = [
        f"Email-health audit detected {len(report.failed)} drift(s) on the FND/cvcc/cvccboard/bpw/tff stack.",
        "",
        "Failing checks:",
    ]
    for r in report.failed:
        body_lines.append(f"  ✗ {r.name}")
        body_lines.append(f"      {r.detail}")
    body_lines.extend([
        "",
        "Passing checks:",
    ])
    for r in report.passed:
        body_lines.append(f"  ✓ {r.name} — {r.detail}")
    body_lines.extend([
        "",
        "Source: /srv/repo/mycite-core/MyCiteV2/scripts/email_health_audit.py",
        "Runs daily via systemd email-health-audit.timer.",
    ])
    body = "\n".join(body_lines)
    ses = boto3.client("ses", region_name="us-east-1")
    try:
        ses.send_email(
            Source=ALERT_FROM,
            Destination={"ToAddresses": [ALERT_TO]},
            Message={
                "Subject": {"Data": f"[FND email-health-audit] {len(report.failed)} drift(s) detected"},
                "Body": {"Text": {"Data": body}},
            },
        )
    except Exception as exc:
        # Log to stderr; systemd will surface in journal. Audit exit
        # code still reflects the underlying drifts.
        print(f"WARN: failed to dispatch alert email: {exc}", file=sys.stderr)


def run_checks() -> AuditReport:
    """Run every email-health check and return the populated report.

    Shared by ``main()`` (CLI + systemd timer) and the portal
    ``/portal/email-health`` surface so both see identical results from a
    single source of truth.
    """
    report = AuditReport()
    check_forwarder_map(report)
    check_dns(report)
    check_ses_identities(report)
    check_reputation(report)
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--no-alert", action="store_true",
        help="run checks + print summary; do NOT send the SES alert email even on drift")
    parser.add_argument("--json", action="store_true",
        help="emit machine-readable JSON instead of human-readable text")
    args = parser.parse_args(argv)

    report = run_checks()

    if args.json:
        print(json.dumps(
            {"results": [{"name": r.name, "ok": r.ok, "detail": r.detail} for r in report.results]},
            indent=2,
        ))
    else:
        for r in report.results:
            mark = "✓" if r.ok else "✗"
            print(f"  {mark} {r.name:48s} {r.detail}")
        print(f"\n{len(report.passed)} passed, {len(report.failed)} failed")

    if report.failed and not args.no_alert:
        send_alert(report)

    return len(report.failed)


if __name__ == "__main__":
    sys.exit(main())
