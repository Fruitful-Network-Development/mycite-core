"""Production implementation of `AwsPeripheralPort` via boto3.

All 8 operational methods are implemented here. The adapter is
stateless aside from the lazy boto3 client cache; safe to construct on
every request, or to hold for the lifetime of a process.

Lambda function names referenced by this adapter are configured at the
module level — the adapter is tied to the two functions that the AWS
peripheral owns. Changing those names requires editing this file *and*
the live AWS resources together.
"""

from __future__ import annotations

import json
from typing import Any

from ._normalize import as_text, normalized_domain, normalized_email
from .contracts import (
    AwsPeripheralPort,
    CostBreakdown,
    CostLineItem,
    DomainStatus,
    ForwardingRoutesSyncResult,
    ProfileReadiness,
    SesSendError,
    SesSendResult,
    TagOperationResult,
)
from .profile_store import ProfileStore, iter_profile_recipient_targets


SES_REGION = "us-east-1"

SES_FORWARDER_FN = "ses-forwarder"
SES_FORWARDER_ENV_KEY = "FORWARD_TO_MAP_JSON"

ACTIVE_RECEIPT_RULE_SET = "fnd-inbound-rules"


class AwsPeripheralCloudAdapter(AwsPeripheralPort):
    def __init__(self, profile_store: ProfileStore | None = None) -> None:
        self._profiles = profile_store or ProfileStore()
        self._cached_clients: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # boto3 client cache

    def _client(self, service_name: str, region: str | None = None):
        key = f"{service_name}@{region or SES_REGION}"
        if key not in self._cached_clients:
            import boto3
            self._cached_clients[key] = boto3.client(
                service_name, region_name=region or SES_REGION
            )
        return self._cached_clients[key]

    # ------------------------------------------------------------------
    # Method 1: sync_operator_forwarding_routes

    def sync_operator_forwarding_routes(
        self,
        *,
        profiles: list[dict[str, Any]] | None = None,
        dry_run: bool = False,
    ) -> ForwardingRoutesSyncResult:
        profile_list = profiles if profiles is not None else self._profiles.list_profiles()
        pairs = iter_profile_recipient_targets(profile_list)
        forward_map: dict[str, str] = {}
        for _pid, send_as, target in pairs:
            forward_map[send_as] = target

        forward_json = json.dumps(forward_map, sort_keys=True, separators=(",", ":"))
        forwarder_changed = self._update_lambda_env(
            function_name=SES_FORWARDER_FN,
            key=SES_FORWARDER_ENV_KEY,
            new_value_json=forward_json,
            dry_run=dry_run,
        )

        # newsletter-inbound-capture no longer reads a verification map —
        # the Lambda is newsletter-mode only after the 2026-05-19 deploy.
        # We don't write to it.

        return ForwardingRoutesSyncResult(
            status="ok",
            route_count=len(forward_map),
            tracked_recipients=sorted(forward_map.keys()),
            route_changed=forwarder_changed,
            domains_wired=sorted({recipient.split("@", 1)[1] for recipient in forward_map}),
            permissions_added=[],
            notes=(
                ["dry_run"] if dry_run else []
            ),
        )

    def _update_lambda_env(
        self,
        *,
        function_name: str,
        key: str,
        new_value_json: str,
        dry_run: bool,
    ) -> bool:
        lam = self._client("lambda")
        cfg = lam.get_function_configuration(FunctionName=function_name)
        env = dict((cfg.get("Environment") or {}).get("Variables") or {})
        current = env.get(key, "")
        try:
            current_obj = json.loads(current) if current else {}
        except json.JSONDecodeError:
            current_obj = {}
        new_obj = json.loads(new_value_json)
        if current_obj == new_obj:
            return False
        if dry_run:
            return True
        env[key] = new_value_json
        lam.update_function_configuration(
            FunctionName=function_name,
            Environment={"Variables": env},
        )
        return True

    # ------------------------------------------------------------------
    # Methods 2 + 7 + 8: read-only profile / evidence checks

    def describe_profile_readiness(self, profile: dict[str, Any]) -> ProfileReadiness:
        ident = profile.get("identity") or {}
        profile_id = as_text(ident.get("profile_id"))
        domain = normalized_domain(ident.get("domain"))
        send_as = normalized_email(ident.get("send_as_email"))
        notes: list[str] = []

        ses_identity_verified = False
        dkim_verified = False
        if domain:
            try:
                ses = self._client("ses")
                attrs = ses.get_identity_verification_attributes(Identities=[domain])
                vstatus = (
                    attrs.get("VerificationAttributes", {})
                    .get(domain, {})
                    .get("VerificationStatus", "")
                )
                ses_identity_verified = vstatus == "Success"
                dkim_attrs = ses.get_identity_dkim_attributes(Identities=[domain])
                dstatus = (
                    dkim_attrs.get("DkimAttributes", {})
                    .get(domain, {})
                    .get("DkimVerificationStatus", "")
                )
                dkim_verified = dstatus == "Success"
            except Exception as exc:  # noqa: BLE001
                notes.append(f"ses_describe_error: {exc}")

        receipt_rule_present = False
        if domain:
            try:
                ses = self._client("ses")
                rules = ses.describe_active_receipt_rule_set().get("Rules", [])
                for rule in rules:
                    if domain in (rule.get("Recipients") or []):
                        receipt_rule_present = True
                        break
            except Exception as exc:  # noqa: BLE001
                notes.append(f"receipt_rule_lookup_error: {exc}")

        forward_map_contains_send_as = False
        lambda_permission_present = False
        if send_as:
            try:
                lam = self._client("lambda")
                cfg = lam.get_function_configuration(FunctionName=SES_FORWARDER_FN)
                env = (cfg.get("Environment") or {}).get("Variables") or {}
                fmap = json.loads(env.get(SES_FORWARDER_ENV_KEY, "{}") or "{}")
                forward_map_contains_send_as = send_as in fmap
                policy = lam.get_policy(FunctionName=SES_FORWARDER_FN)
                lambda_permission_present = domain.replace(".", "-") in policy.get("Policy", "")
            except Exception as exc:  # noqa: BLE001
                notes.append(f"lambda_describe_error: {exc}")

        return ProfileReadiness(
            profile_id=profile_id,
            ses_identity_verified=ses_identity_verified,
            dkim_verified=dkim_verified,
            receipt_rule_present=receipt_rule_present,
            forward_map_contains_send_as=forward_map_contains_send_as,
            lambda_permission_present=lambda_permission_present,
            notes=notes,
        )

    def confirmation_evidence_satisfied(self, profile: dict[str, Any]) -> bool:
        verification = profile.get("verification") or {}
        provider = profile.get("provider") or {}
        verified_at = as_text(verification.get("verified_at"))
        gmail_status = as_text(provider.get("gmail_send_as_status"))
        return bool(verified_at) and gmail_status == "verified"

    def gmail_confirmation_evidence_satisfied(self, profile: dict[str, Any]) -> bool:
        return self.confirmation_evidence_satisfied(profile)

    # ------------------------------------------------------------------
    # B1 — Activity-based onboarding-overlay probes
    # ------------------------------------------------------------------
    # Each probe returns the AwsEvidence triple (state, detail, observed_at)
    # the email-extension renderer overlays onto the per-step progress bar.
    #
    # State semantics:
    #   "confirmed"    — AWS evidence agrees the step is complete
    #   "drift"        — declared complete (JSON flag) but AWS has no evidence
    #   "auto_advance" — AWS evidence positive, JSON flag still unset
    #   "absent"       — neither side has evidence
    #   "error"        — probe failed; detail carries the exception message
    #
    # Probes do NOT cache themselves; the caller wraps with ProbeCache.
    # They DO use the existing _client cache so repeated calls in the
    # same request reuse the boto3 client.

    def probe_ses_identity_aws_evidence(
        self,
        send_as_email: str,
        *,
        declared_verified: bool = False,
    ) -> dict[str, Any]:
        """Step 2 overlay — query SES for the identity's verification status.

        SES verification is granted at two granularities: a specific
        email-address identity (e.g. ``noreply@fnd...``) OR a whole-domain
        identity (e.g. ``fruitfulnetworkdevelopment.com``). A domain
        identity covers EVERY address on that domain — so a mailbox whose
        domain is verified can send even though its exact email address
        was never registered as a standalone identity.

        Most grantees verify at the domain level (confirmed live: only the
        5 FND domains + a handful of explicit fnd email identities are
        registered; per-grantee mailbox addresses are NOT). So we check the
        email-address identity first, then fall back to the domain
        identity. Reporting "drift" off the email-address check alone would
        false-alarm on every domain-verified mailbox.
        """
        from datetime import datetime, timezone
        observed_at = datetime.now(timezone.utc).isoformat()
        token = as_text(send_as_email).strip().lower()
        if not token:
            return {"state": "error", "detail": "send_as_email empty", "observed_at": observed_at}
        try:
            ses = self._client("ses")
            identities_to_check = [token]
            domain = token.split("@", 1)[1] if "@" in token else ""
            if domain:
                identities_to_check.append(domain)
            attrs = ses.get_identity_verification_attributes(
                Identities=identities_to_check
            )
            va = attrs.get("VerificationAttributes", {})
            email_status = va.get(token, {}).get("VerificationStatus", "")
            domain_status = va.get(domain, {}).get("VerificationStatus", "") if domain else ""
        except Exception as exc:  # noqa: BLE001
            return {
                "state": "error",
                "detail": f"ses_get_identity_verification_attributes: {exc}",
                "observed_at": observed_at,
            }
        if email_status == "Success":
            aws_verified, via = True, "email-identity"
        elif domain_status == "Success":
            aws_verified, via = True, "domain-identity"
        else:
            aws_verified, via = False, ""
        if aws_verified and declared_verified:
            state = "confirmed"
            detail = f"SES verified via {via}; flag agrees"
        elif aws_verified and not declared_verified:
            state = "auto_advance"
            detail = f"SES verified via {via}; JSON flag not yet set"
        elif not aws_verified and declared_verified:
            state = "drift"
            detail = (
                f"flag says verified; SES email={email_status or 'absent'}, "
                f"domain={domain_status or 'absent'}"
            )
        else:
            state = "absent"
            detail = (
                f"SES email={email_status or 'absent'}, "
                f"domain={domain_status or 'absent'}"
            )
        return {"state": state, "detail": detail, "observed_at": observed_at}

    def probe_operator_sends_aws_evidence(
        self,
        send_as_email: str,
        *,
        declared_operational: bool = False,
        lookback_days: int = 7,
    ) -> dict[str, Any]:
        """Step 4 overlay — CloudWatch AWS/SES Send metric for this identity.

        A non-zero send count over the lookback window means the operator
        actually used the mailbox (sent at least one message via SES SMTP
        or send_email under this identity).

        IMPORTANT (verified live 2026-05-24): the AWS/SES Send metric is
        only published with NO dimension (account-wide) and with the
        ``ses:configuration-set`` dimension — there is NO
        ``ses:source-address`` dimension unless a configuration set is
        explicitly configured to emit one. So a per-identity query returns
        zero datapoints whether or not the operator actually sent.

        Consequence: a zero result is NOT proof of "no sends" — it's
        "no per-identity signal available". We therefore treat a positive
        count as trustworthy (confirmed / auto_advance) but a zero count as
        ``absent`` (no data), NEVER ``drift``. Emitting drift off an
        unmeasurable negative would false-alarm on every operational
        mailbox. Per-identity send attribution becomes real once the A10
        SES event sink is deployed + a configset dimension on the sender is
        added; until then this probe only ever advances on positive
        evidence.

        Requires cloudwatch:GetMetricStatistics on the EC2 role (folded
        into the AWSCMSDiagnosticsLogsReadOnly inline policy); without it
        the probe returns state=error.
        """
        from datetime import datetime, timedelta, timezone
        observed_at = datetime.now(timezone.utc).isoformat()
        token = as_text(send_as_email).strip().lower()
        if not token:
            return {"state": "error", "detail": "send_as_email empty", "observed_at": observed_at}
        try:
            cw = self._client("cloudwatch")
            now = datetime.now(timezone.utc)
            start_time = now - timedelta(days=max(1, lookback_days))
            response = cw.get_metric_statistics(
                Namespace="AWS/SES",
                MetricName="Send",
                Dimensions=[{"Name": "ses:source-address", "Value": token}],
                StartTime=start_time,
                EndTime=now,
                Period=86400,
                Statistics=["Sum"],
            )
            total = sum(
                float(dp.get("Sum") or 0) for dp in response.get("Datapoints", [])
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "state": "error",
                "detail": f"cloudwatch_get_metric_statistics: {exc}",
                "observed_at": observed_at,
            }
        sent_count = int(total)
        if sent_count > 0 and declared_operational:
            state = "confirmed"
            detail = f"{sent_count} sends in last {lookback_days}d; flag agrees"
        elif sent_count > 0 and not declared_operational:
            state = "auto_advance"
            detail = f"{sent_count} sends in last {lookback_days}d; lifecycle not yet operational"
        else:
            # Zero datapoints is unmeasurable (no per-identity dimension),
            # not a confirmed negative — return absent, never drift, so we
            # don't false-alarm on operational mailboxes.
            state = "absent"
            detail = (
                f"no per-identity send signal (AWS/SES Send has no "
                f"ses:source-address dimension); {lookback_days}d window"
            )
        return {"state": state, "detail": detail, "observed_at": observed_at}

    def probe_inbound_verified_aws_evidence(
        self,
        domain: str,
        *,
        declared_verified: bool = False,
        bucket: str = "ses-inbound-fnd-mail",
        prefix_template: str = "inbound/{domain}/",
    ) -> dict[str, Any]:
        """Step 6 overlay — check the SES inbound S3 bucket for any object
        captured for this domain.

        At least one S3 object under inbound/<domain>/ means SES received +
        wrote an inbound message — proof the inbound rule fired end-to-end.
        Doesn't check the forwarder Lambda separately (a successful forward
        implies the S3 write succeeded; if the S3 write failed, the
        forwarder would never have been invoked).
        """
        from datetime import datetime, timezone
        observed_at = datetime.now(timezone.utc).isoformat()
        token = normalized_domain(domain)
        if not token:
            return {"state": "error", "detail": "invalid_domain", "observed_at": observed_at}
        prefix = prefix_template.format(domain=token).lstrip("/")
        try:
            s3 = self._client("s3")
            response = s3.list_objects_v2(
                Bucket=bucket, Prefix=prefix, MaxKeys=1
            )
            key_count = int(response.get("KeyCount") or 0)
        except Exception as exc:  # noqa: BLE001
            return {
                "state": "error",
                "detail": f"s3_list_objects_v2: {exc}",
                "observed_at": observed_at,
            }
        any_inbound = key_count > 0
        if any_inbound and declared_verified:
            state = "confirmed"
            detail = f"inbound S3 objects present at s3://{bucket}/{prefix}"
        elif any_inbound and not declared_verified:
            state = "auto_advance"
            detail = f"inbound S3 objects present; JSON flag not yet set"
        elif (not any_inbound) and declared_verified:
            state = "drift"
            detail = f"flag says verified; no S3 objects under {prefix}"
        else:
            state = "absent"
            detail = f"no inbound S3 objects under {prefix}"
        return {"state": state, "detail": detail, "observed_at": observed_at}

    # ------------------------------------------------------------------
    # Method 3: describe_domain_status

    def describe_domain_status(self, domain: str) -> DomainStatus:
        token = normalized_domain(domain)
        notes: list[str] = []
        if not token:
            return DomainStatus(
                domain=as_text(domain),
                hosted_zone_id="",
                ses_identity_verified=False,
                dkim_verified=False,
                mx_present=False,
                spf_present=False,
                dmarc_present=False,
                dkim_cnames_present=0,
                receipt_rule_present=False,
                notes=["invalid_domain"],
            )

        hosted_zone_id = ""
        mx_present = spf_present = dmarc_present = False
        dkim_cnames_present = 0
        try:
            r53 = self._client("route53")
            zones = r53.list_hosted_zones().get("HostedZones", [])
            zone_id = ""
            for z in zones:
                if as_text(z.get("Name")).rstrip(".") == token:
                    zone_id = as_text(z.get("Id")).rsplit("/", 1)[-1]
                    break
            hosted_zone_id = zone_id
            if zone_id:
                rrs = r53.list_resource_record_sets(HostedZoneId=zone_id).get(
                    "ResourceRecordSets", []
                )
                for rr in rrs:
                    rtype = rr.get("Type", "")
                    name = as_text(rr.get("Name", "")).rstrip(".")
                    values = [as_text(v.get("Value", "")) for v in (rr.get("ResourceRecords") or [])]
                    if rtype == "MX" and name == token:
                        mx_present = True
                    elif rtype == "TXT" and name == token:
                        if any("v=spf1" in v for v in values):
                            spf_present = True
                    elif rtype == "TXT" and name == f"_dmarc.{token}":
                        if any("v=DMARC1" in v for v in values):
                            dmarc_present = True
                    elif rtype == "CNAME" and name.endswith(f"._domainkey.{token}"):
                        dkim_cnames_present += 1
        except Exception as exc:  # noqa: BLE001
            notes.append(f"route53_error: {exc}")

        ses_identity_verified = dkim_verified = False
        try:
            ses = self._client("ses")
            attrs = ses.get_identity_verification_attributes(Identities=[token])
            ses_identity_verified = (
                attrs.get("VerificationAttributes", {}).get(token, {}).get(
                    "VerificationStatus", ""
                )
                == "Success"
            )
            dkim_attrs = ses.get_identity_dkim_attributes(Identities=[token])
            dkim_verified = (
                dkim_attrs.get("DkimAttributes", {}).get(token, {}).get(
                    "DkimVerificationStatus", ""
                )
                == "Success"
            )
        except Exception as exc:  # noqa: BLE001
            notes.append(f"ses_error: {exc}")

        receipt_rule_present = False
        try:
            ses = self._client("ses")
            rules = ses.describe_active_receipt_rule_set().get("Rules", [])
            for rule in rules:
                if token in (rule.get("Recipients") or []):
                    receipt_rule_present = True
                    break
        except Exception as exc:  # noqa: BLE001
            notes.append(f"receipt_rule_error: {exc}")

        return DomainStatus(
            domain=token,
            hosted_zone_id=hosted_zone_id,
            ses_identity_verified=ses_identity_verified,
            dkim_verified=dkim_verified,
            mx_present=mx_present,
            spf_present=spf_present,
            dmarc_present=dmarc_present,
            dkim_cnames_present=dkim_cnames_present,
            receipt_rule_present=receipt_rule_present,
            notes=notes,
        )

    # ------------------------------------------------------------------
    # Methods 4 / 5 / 6: mutating domain provisioning

    def _account_id(self) -> str:
        """Lazy STS caller-identity lookup; cached on the adapter."""
        cached = getattr(self, "_cached_account_id", None)
        if cached:
            return cached
        sts = self._client("sts", region="us-east-1")
        try:
            ident = sts.get_caller_identity()
            account_id = str(ident.get("Account", "")) or ""
        except Exception:  # noqa: BLE001
            account_id = ""
        self._cached_account_id = account_id
        return account_id

    def ensure_domain_identity(
        self, domain: str, *, tags: dict[str, str] | None = None
    ) -> dict[str, Any]:
        token = normalized_domain(domain)
        if not token:
            return {"ok": False, "error": "invalid_domain"}
        ses = self._client("ses")
        status_before = ses.get_identity_verification_attributes(Identities=[token])
        already_verified = (
            status_before.get("VerificationAttributes", {})
            .get(token, {})
            .get("VerificationStatus", "")
            == "Success"
        )
        changed: list[str] = []
        if not already_verified:
            ses.verify_domain_identity(Domain=token)
            changed.append("verify_domain_identity")
        dkim = ses.get_identity_dkim_attributes(Identities=[token])
        existing_tokens = (
            dkim.get("DkimAttributes", {}).get(token, {}).get("DkimTokens", []) or []
        )
        if not existing_tokens:
            ses.verify_domain_dkim(Domain=token)
            changed.append("verify_domain_dkim")
        dkim_enabled = (
            dkim.get("DkimAttributes", {}).get(token, {}).get("DkimEnabled", False)
        )
        if not dkim_enabled:
            ses.set_identity_dkim_enabled(Identity=token, DkimEnabled=True)
            changed.append("set_identity_dkim_enabled")
        # Auto-tag-on-create. SES v1 verify_domain_identity does NOT accept
        # Tags directly; tag the identity via the ResourceGroupsTagging
        # API after creation. Opportunistic — if tagging fails (e.g. ARN
        # construction races a concurrent delete), we still return ok=True
        # for the verification work that did land.
        tagged_arn = ""
        if tags:
            account_id = self._account_id()
            if account_id:
                identity_arn = f"arn:aws:ses:{SES_REGION}:{account_id}:identity/{token}"
                try:
                    self.tag_resource(arns=[identity_arn], tags=tags)
                    tagged_arn = identity_arn
                except Exception:  # noqa: BLE001
                    pass
        result: dict[str, Any] = {"ok": True, "changed": changed, "domain": token}
        if tagged_arn:
            result["tagged_arn"] = tagged_arn
        return result

    def sync_domain_dns(
        self, domain: str, *, tags: dict[str, str] | None = None
    ) -> dict[str, Any]:
        token = normalized_domain(domain)
        if not token:
            return {"ok": False, "error": "invalid_domain"}
        r53 = self._client("route53")
        zones = r53.list_hosted_zones().get("HostedZones", [])
        zone_id = ""
        for z in zones:
            if as_text(z.get("Name")).rstrip(".") == token:
                zone_id = as_text(z.get("Id")).rsplit("/", 1)[-1]
                break
        if not zone_id:
            return {"ok": False, "error": "hosted_zone_missing", "domain": token}

        rrs = {
            (rr.get("Name", "").rstrip("."), rr.get("Type", ""))
            for rr in r53.list_resource_record_sets(HostedZoneId=zone_id).get(
                "ResourceRecordSets", []
            )
        }
        desired_changes: list[dict[str, Any]] = []
        if (token, "MX") not in rrs:
            desired_changes.append(
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": f"{token}.",
                        "Type": "MX",
                        "TTL": 300,
                        "ResourceRecords": [
                            {"Value": "10 inbound-smtp.us-east-1.amazonaws.com"}
                        ],
                    },
                }
            )
        if (token, "TXT") not in rrs:
            desired_changes.append(
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": f"{token}.",
                        "Type": "TXT",
                        "TTL": 300,
                        "ResourceRecords": [
                            {"Value": '"v=spf1 include:amazonses.com ~all"'}
                        ],
                    },
                }
            )
        dmarc_name = f"_dmarc.{token}"
        if (dmarc_name, "TXT") not in rrs:
            desired_changes.append(
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": f"{dmarc_name}.",
                        "Type": "TXT",
                        "TTL": 300,
                        "ResourceRecords": [
                            {
                                "Value": (
                                    '"v=DMARC1; p=none; '
                                    "rua=mailto:dmarc-reports@fruitfulnetworkdevelopment.com; "
                                    'adkim=s; aspf=s"'
                                )
                            }
                        ],
                    },
                }
            )

        ses = self._client("ses")
        dkim = ses.get_identity_dkim_attributes(Identities=[token])
        tokens_list = (
            dkim.get("DkimAttributes", {}).get(token, {}).get("DkimTokens", []) or []
        )
        for dt in tokens_list:
            dkim_name = f"{dt}._domainkey.{token}"
            if (dkim_name, "CNAME") not in rrs:
                desired_changes.append(
                    {
                        "Action": "CREATE",
                        "ResourceRecordSet": {
                            "Name": f"{dkim_name}.",
                            "Type": "CNAME",
                            "TTL": 300,
                            "ResourceRecords": [{"Value": f"{dt}.dkim.amazonses.com"}],
                        },
                    }
                )

        # C1 — Custom MAIL FROM auto-bootstrap. The bare-domain MAIL FROM
        # ("amazonses.com" envelope) trips DMARC-strict alignment because
        # the From: domain (e.g. brock@brockspressurewashing.com) doesn't
        # match the envelope domain (amazonses.com). Pointing MAIL FROM at
        # a subdomain we control (mail.<domain>) restores alignment and
        # closes the manual SES-console step in the client-onboarding
        # runbook.
        #
        # Idempotent: get_identity_mail_from_domain_attributes returns the
        # current setting; we only call set_identity_mail_from_domain if
        # it differs from the desired mail.<domain> target.
        mail_from_domain = f"mail.{token}"
        mail_from_changed = False
        try:
            mf_attrs = ses.get_identity_mail_from_domain_attributes(
                Identities=[token]
            )
            current_mf = (
                mf_attrs.get("MailFromDomainAttributes", {})
                .get(token, {})
                .get("MailFromDomain", "")
            )
            if current_mf != mail_from_domain:
                ses.set_identity_mail_from_domain(
                    Identity=token,
                    MailFromDomain=mail_from_domain,
                    BehaviorOnMXFailure="UseDefaultValue",
                )
                mail_from_changed = True
        except Exception:  # noqa: BLE001
            # Don't fail the sync if SES MAIL FROM API errors; the rest
            # of DKIM/SPF/DMARC still lands. Operator can retry.
            pass

        # MX record for the MAIL FROM subdomain — per SES docs, point to
        # feedback-smtp.<region>.amazonses.com on priority 10.
        mail_from_mx_name = mail_from_domain
        if (mail_from_mx_name, "MX") not in rrs:
            desired_changes.append(
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": f"{mail_from_mx_name}.",
                        "Type": "MX",
                        "TTL": 300,
                        "ResourceRecords": [
                            {"Value": f"10 feedback-smtp.{SES_REGION}.amazonses.com"}
                        ],
                    },
                }
            )
        # SPF TXT for the MAIL FROM subdomain — required so the envelope
        # passes SPF in addition to the apex SPF (which authorizes the
        # apex's senders). Two distinct records, two distinct SPF lookups.
        if (mail_from_mx_name, "TXT") not in rrs:
            desired_changes.append(
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": f"{mail_from_mx_name}.",
                        "Type": "TXT",
                        "TTL": 300,
                        "ResourceRecords": [
                            {"Value": '"v=spf1 include:amazonses.com -all"'}
                        ],
                    },
                }
            )

        if desired_changes:
            r53.change_resource_record_sets(
                HostedZoneId=zone_id,
                ChangeBatch={
                    "Comment": "aws-peripheral sync_domain_dns",
                    "Changes": desired_changes,
                },
            )
        # Auto-tag-on-create — tag the hosted zone. Route53 records aren't
        # taggable; the zone is. Opportunistic; tag failure doesn't fail
        # the DNS sync. Runs even when the DNS records are already in
        # place (desired_changes empty) so an already-synced zone still
        # picks up cost-allocation tags on a follow-up call.
        tagged_zone = False
        if tags and zone_id:
            try:
                r53.change_tags_for_resource(
                    ResourceType="hostedzone",
                    ResourceId=zone_id,
                    AddTags=[{"Key": k, "Value": v} for k, v in tags.items()],
                )
                tagged_zone = True
            except Exception:  # noqa: BLE001
                pass
        result: dict[str, Any] = {
            "ok": True,
            "changed": [c["ResourceRecordSet"]["Type"] for c in desired_changes],
            "domain": token,
            "zone_id": zone_id,
        }
        if tagged_zone:
            result["tagged_zone"] = True
        if mail_from_changed:
            result["mail_from_domain"] = mail_from_domain
            result["mail_from_changed"] = True
        return result

    # ------------------------------------------------------------------
    # C3 — DMARC policy ramp (read + guarded apply)

    def get_dmarc_policy(self, domain: str) -> dict[str, Any]:
        """Read the current _dmarc.<domain> TXT record from Route53 and
        parse it. Returns {ok, domain, zone_id, record, tags} or
        {ok: False, error}."""
        from .dmarc_ramp import parse_dmarc_policy

        token = normalized_domain(domain)
        if not token:
            return {"ok": False, "error": "invalid_domain"}
        r53 = self._client("route53")
        zone_id = ""
        for z in r53.list_hosted_zones().get("HostedZones", []):
            if as_text(z.get("Name")).rstrip(".") == token:
                zone_id = as_text(z.get("Id")).rsplit("/", 1)[-1]
                break
        if not zone_id:
            return {"ok": False, "error": "hosted_zone_missing", "domain": token}
        dmarc_name = f"_dmarc.{token}"
        record_value = ""
        for rr in r53.list_resource_record_sets(HostedZoneId=zone_id).get(
            "ResourceRecordSets", []
        ):
            if rr.get("Name", "").rstrip(".") == dmarc_name and rr.get("Type") == "TXT":
                values = [
                    rec.get("Value", "") for rec in rr.get("ResourceRecords", [])
                ]
                record_value = " ".join(values)
                break
        return {
            "ok": True,
            "domain": token,
            "zone_id": zone_id,
            "record": record_value,
            "tags": parse_dmarc_policy(record_value),
        }

    def apply_dmarc_policy(
        self, domain: str, proposed_record: str, *, dry_run: bool = True
    ) -> dict[str, Any]:
        """UPSERT the _dmarc.<domain> TXT record. Guarded: callers should
        only invoke this with a ``proposed_record`` from
        ``compute_dmarc_ramp`` that came back ``allowed=True``.

        Per active-task guardrail G-2 this is an UPSERT (never DELETE), so
        a concurrent operator-managed DMARC change is overwritten by the
        exact computed value rather than removed. ``dry_run`` returns the
        ChangeBatch without submitting it."""
        token = normalized_domain(domain)
        if not token:
            return {"ok": False, "error": "invalid_domain"}
        if not (proposed_record or "").strip():
            return {"ok": False, "error": "empty_proposed_record"}
        r53 = self._client("route53")
        zone_id = ""
        for z in r53.list_hosted_zones().get("HostedZones", []):
            if as_text(z.get("Name")).rstrip(".") == token:
                zone_id = as_text(z.get("Id")).rsplit("/", 1)[-1]
                break
        if not zone_id:
            return {"ok": False, "error": "hosted_zone_missing", "domain": token}
        dmarc_name = f"_dmarc.{token}"
        # DMARC TXT values must be quoted in the Route53 record.
        quoted = proposed_record if proposed_record.startswith('"') else f'"{proposed_record}"'
        change_batch = {
            "Comment": "aws-peripheral dmarc ramp (UPSERT)",
            "Changes": [
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": f"{dmarc_name}.",
                        "Type": "TXT",
                        "TTL": 300,
                        "ResourceRecords": [{"Value": quoted}],
                    },
                }
            ],
        }
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "domain": token,
                "zone_id": zone_id,
                "change_batch": change_batch,
            }
        r53.change_resource_record_sets(
            HostedZoneId=zone_id, ChangeBatch=change_batch
        )
        return {
            "ok": True,
            "dry_run": False,
            "domain": token,
            "zone_id": zone_id,
            "applied_record": quoted,
        }

    def ensure_domain_receipt_rule(
        self, domain: str, *, tags: dict[str, str] | None = None
    ) -> dict[str, Any]:
        token = normalized_domain(domain)
        if not token:
            return {"ok": False, "error": "invalid_domain"}
        rule_name = f"portal-capture-{token.replace('.', '-')}"
        ses = self._client("ses")
        rules = ses.describe_active_receipt_rule_set().get("Rules", [])
        existing = next((r for r in rules if r.get("Name") == rule_name), None)
        if existing:
            return {"ok": True, "changed": [], "rule_name": rule_name, "already_present": True}
        rule = {
            "Name": rule_name,
            "Enabled": True,
            "TlsPolicy": "Optional",
            "Recipients": [token],
            "Actions": [
                {
                    "S3Action": {
                        "BucketName": "ses-inbound-fnd-mail",
                        "ObjectKeyPrefix": f"inbound/{token}/",
                    }
                },
                {
                    "LambdaAction": {
                        "FunctionArn": (
                            f"arn:aws:lambda:us-east-1:065948377733:function:{SES_FORWARDER_FN}"
                        ),
                        "InvocationType": "Event",
                    }
                },
            ],
            "ScanEnabled": True,
        }
        lam = self._client("lambda")
        rule_arn = (
            f"arn:aws:ses:us-east-1:065948377733:"
            f"receipt-rule-set/{ACTIVE_RECEIPT_RULE_SET}:receipt-rule/{rule_name}"
        )
        try:
            lam.add_permission(
                FunctionName=SES_FORWARDER_FN,
                StatementId=f"ses-{rule_name}",
                Action="lambda:InvokeFunction",
                Principal="ses.amazonaws.com",
                SourceAccount="065948377733",
                SourceArn=rule_arn,
            )
        except Exception:  # noqa: BLE001
            # Already-present permissions raise ResourceConflictException;
            # idempotent: we just want the grant to exist.
            pass
        ses.create_receipt_rule(RuleSetName=ACTIVE_RECEIPT_RULE_SET, Rule=rule)
        # Auto-tag-on-create. SES v1 receipt rules do NOT support per-rule
        # tagging — only the parent rule-set is taggable (via sesv2). We
        # accept the kwarg for API uniformity with the sibling ensure_*
        # methods but currently no-op; the retroactive tagger handles the
        # rule-set + receipt infrastructure separately. Surface the tags
        # in the return value so the caller can audit the intent.
        result: dict[str, Any] = {
            "ok": True,
            "changed": [rule_name],
            "rule_name": rule_name,
        }
        if tags:
            result["tags_requested"] = dict(tags)
            result["tags_applied"] = False
            result["tags_note"] = (
                "SES v1 receipt rules are not directly taggable; "
                "rule-set-level tagging belongs in a separate sesv2 path."
            )
        return result

    # ------------------------------------------------------------------
    # SES send surface (used by portal extensions: connect-form forward,
    # donation receipt, future transactional mail). Newsletter Lambda is
    # a separate runtime and mirrors these patterns via env config.

    def send_email(
        self,
        *,
        aws_ses_profile: dict[str, Any],
        to: list[str],
        subject: str,
        body_text: str,
        body_html: str | None = None,
        reply_to: list[str] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> SesSendResult:
        import email.utils
        from email.message import EmailMessage

        from_address = as_text(aws_ses_profile.get("from_address")) or as_text(
            aws_ses_profile.get("identity")
        )
        from_name = as_text(aws_ses_profile.get("from_name"))
        if not from_address:
            raise SesSendError(
                operation="send_email",
                identity="",
                reason="aws_ses_profile missing from_address/identity",
            )

        msg = EmailMessage()
        msg["From"] = f'"{from_name}" <{from_address}>' if from_name else from_address
        msg["To"] = ", ".join(to)
        msg["Subject"] = subject
        if reply_to:
            msg["Reply-To"] = ", ".join(reply_to)
        if extra_headers:
            for header_name, header_value in extra_headers.items():
                msg[header_name] = header_value
        # Standards-compliance: domain-anchored Message-ID + RFC 2822 Date.
        # Python's EmailMessage auto-generates Message-ID at as_bytes() time
        # using the local hostname (e.g. `@ec2-xxx.compute.internal`), which
        # spam filters score as suspicious because the host domain doesn't
        # match the From domain. Anchor it to the sender's domain instead.
        # Caller wins — if extra_headers already set Message-ID/Date, skip.
        from_domain = from_address.rsplit("@", 1)[-1].strip().strip(">")
        if "Message-ID" not in msg:
            msg["Message-ID"] = (
                email.utils.make_msgid(domain=from_domain)
                if from_domain
                else email.utils.make_msgid()
            )
        if "Date" not in msg:
            # usegmt=True emits "GMT" rather than "-0000"; some spam filters
            # treat "-0000" as "unspecified offset" and score it lower.
            msg["Date"] = email.utils.formatdate(usegmt=True)
        msg.set_content(body_text)
        if body_html:
            msg.add_alternative(body_html, subtype="html")

        return self.send_raw_email(
            aws_ses_profile=aws_ses_profile,
            destinations=list(to),
            raw_message_bytes=msg.as_bytes(),
        )

    def send_raw_email(
        self,
        *,
        aws_ses_profile: dict[str, Any],
        destinations: list[str],
        raw_message_bytes: bytes,
    ) -> SesSendResult:
        identity = as_text(aws_ses_profile.get("identity")) or as_text(
            aws_ses_profile.get("from_address")
        )
        region = as_text(aws_ses_profile.get("region")) or SES_REGION
        configuration_set = as_text(aws_ses_profile.get("configuration_set"))
        if not identity:
            raise SesSendError(
                operation="send_raw_email",
                identity="",
                reason="aws_ses_profile missing identity/from_address",
            )
        if not destinations:
            raise SesSendError(
                operation="send_raw_email",
                identity=identity,
                reason="destinations empty",
            )

        ses = self._client("ses", region=region)
        kwargs: dict[str, Any] = {
            "Source": identity,
            "Destinations": destinations,
            "RawMessage": {"Data": raw_message_bytes},
        }
        if configuration_set:
            kwargs["ConfigurationSetName"] = configuration_set

        try:
            response = ses.send_raw_email(**kwargs)
        except Exception as exc:  # noqa: BLE001
            from botocore.exceptions import BotoCoreError, ClientError

            if isinstance(exc, ClientError):
                err = exc.response.get("Error", {}) if exc.response else {}
                meta = exc.response.get("ResponseMetadata", {}) if exc.response else {}
                raise SesSendError(
                    operation="send_raw_email",
                    identity=identity,
                    reason=str(err.get("Message") or exc),
                    aws_error_code=str(err.get("Code", "")),
                    aws_request_id=str(meta.get("RequestId", "")),
                ) from exc
            if isinstance(exc, BotoCoreError):
                raise SesSendError(
                    operation="send_raw_email",
                    identity=identity,
                    reason=str(exc),
                ) from exc
            raise

        return SesSendResult(
            status="sent",
            message_id=str(response.get("MessageId", "")),
            configuration_set=configuration_set,
        )

    # ------------------------------------------------------------------
    # Tagging + cost attribution (tolling extension prerequisites)

    def tag_resource(
        self,
        *,
        arns: list[str],
        tags: dict[str, str],
    ) -> TagOperationResult:
        if not arns:
            return TagOperationResult(ok=True, tagged_arns=[], failed_arns=[])
        if not tags:
            return TagOperationResult(ok=False, tagged_arns=[], failed_arns=[
                {"arn": arn, "error_code": "EmptyTags",
                 "error_message": "tags dict was empty"} for arn in arns
            ])
        # ResourceGroupsTagging API is region-scoped — call in the region
        # the resources live. For cross-region resources (route53 is
        # global, s3 buckets carry their own region) callers should
        # split ARNs by region and call once per region.
        client = self._client("resourcegroupstaggingapi")
        response = client.tag_resources(ResourceARNList=arns, Tags=tags)
        failed_map = response.get("FailedResourcesMap") or {}
        failed = [
            {
                "arn": arn,
                "error_code": str(detail.get("ErrorCode", "")),
                "error_message": str(detail.get("ErrorMessage", "")),
            }
            for arn, detail in failed_map.items()
        ]
        tagged = [arn for arn in arns if arn not in failed_map]
        return TagOperationResult(
            ok=not failed,
            tagged_arns=tagged,
            failed_arns=failed,
        )

    @staticmethod
    def _parse_cost_response_by_service(group: dict[str, Any]) -> tuple[str, str, dict[str, str]]:
        """Extract (currency, grand_total, by_service) from a Cost
        Explorer GroupBy=SERVICE result."""
        currency = ""
        services: dict[str, str] = {}
        total = 0.0
        for entry in group.get("Groups", []) or []:
            keys = entry.get("Keys") or []
            metric = (entry.get("Metrics") or {}).get("UnblendedCost") or {}
            amount = str(metric.get("Amount", "0"))
            currency = currency or str(metric.get("Unit", ""))
            if keys:
                services[keys[0]] = amount
            try:
                total += float(amount)
            except ValueError:
                pass
        return currency, f"{total:.10f}", services

    def get_costs_by_grantee(
        self,
        *,
        msn_id: str,
        start: str,
        end: str,
        granularity: str = "MONTHLY",
    ) -> CostBreakdown:
        # Cost Explorer is a global service hosted in us-east-1.
        client = self._client("ce", region="us-east-1")
        response = client.get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity=granularity,
            Metrics=["UnblendedCost"],
            Filter={"Tags": {"Key": "msn_id", "Values": [msn_id]}},
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        # GetCostAndUsage returns ResultsByTime[] when granularity is
        # DAILY/MONTHLY; we sum across periods into a single breakdown.
        currency = ""
        by_service: dict[str, float] = {}
        for result in response.get("ResultsByTime", []) or []:
            cur, _, services = self._parse_cost_response_by_service(result)
            currency = currency or cur
            for svc, amount in services.items():
                try:
                    by_service[svc] = by_service.get(svc, 0.0) + float(amount)
                except ValueError:
                    continue
        grand = sum(by_service.values())
        return CostBreakdown(
            currency=currency,
            grand_total=f"{grand:.10f}",
            by_service={k: f"{v:.10f}" for k, v in by_service.items()},
            period_start=start,
            period_end=end,
            granularity=granularity,
        )

    # Usage-type-groups that scale with shared-instance egress. AWS
    # splits transfer-out spend across multiple groups (public
    # internet, inter-region, CloudFront origin pulls); we sum them
    # for per-tenant attribution. Inter-AZ + transfer-in are
    # deliberately excluded — they don't track grantee traffic.
    _DATA_TRANSFER_OUT_GROUPS = (
        "EC2: Data Transfer - Internet (Out)",
        "EC2: Data Transfer - Region to Region (Out)",
        "EC2: Data Transfer - CloudFront (Out)",
        "S3: Data Transfer - Internet (Out)",
        "S3: Data Transfer - Region to Region (Out)",
    )

    def get_data_transfer_out_cost(
        self,
        *,
        start: str,
        end: str,
        granularity: str = "MONTHLY",
    ) -> dict[str, str]:
        """Total Data-Transfer-Out spend across the account in the window.

        Returns `{currency, amount}` (decimal-as-string). Used by the
        tolling extension to multiply by each grantee's nginx-byte
        share so bandwidth becomes a dollar figure on dashboards.

        Sums across the egress usage-type groups in
        `_DATA_TRANSFER_OUT_GROUPS`. AWS free tier covers up to ~100GB/mo
        for many of these, so on low-traffic deployments the total is
        legitimately near-zero; the dashboard renders that as
        "negligible" rather than "$0.00".
        """
        client = self._client("ce", region="us-east-1")
        response = client.get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity=granularity,
            Metrics=["UnblendedCost"],
            Filter={
                "Dimensions": {
                    "Key": "USAGE_TYPE_GROUP",
                    "Values": list(self._DATA_TRANSFER_OUT_GROUPS),
                }
            },
        )
        total = 0.0
        currency = ""
        for result in response.get("ResultsByTime", []) or []:
            metric = (result.get("Total") or {}).get("UnblendedCost") or {}
            currency = currency or str(metric.get("Unit", ""))
            try:
                total += float(metric.get("Amount", "0"))
            except ValueError:
                continue
        return {"currency": currency, "amount": f"{total:.10f}"}

    def get_costs_overview(
        self,
        *,
        start: str,
        end: str,
        granularity: str = "MONTHLY",
    ) -> dict[str, CostBreakdown]:
        client = self._client("ce", region="us-east-1")
        response = client.get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity=granularity,
            Metrics=["UnblendedCost"],
            GroupBy=[
                {"Type": "TAG", "Key": "msn_id"},
                {"Type": "DIMENSION", "Key": "SERVICE"},
            ],
        )
        # Two-dimensional grouping: Keys are [tag_value, service_name]
        # where tag_value may be "msn_id$<value>" or "msn_id$" (untagged).
        agg: dict[str, dict[str, float]] = {}
        currency = ""
        for result in response.get("ResultsByTime", []) or []:
            for entry in result.get("Groups", []) or []:
                keys = entry.get("Keys") or []
                if len(keys) < 2:
                    continue
                tag_key = keys[0]
                msn_value = tag_key.split("$", 1)[1] if "$" in tag_key else ""
                service = keys[1]
                metric = (entry.get("Metrics") or {}).get("UnblendedCost") or {}
                currency = currency or str(metric.get("Unit", ""))
                try:
                    amount = float(metric.get("Amount", "0"))
                except ValueError:
                    amount = 0.0
                agg.setdefault(msn_value, {})[service] = (
                    agg.get(msn_value, {}).get(service, 0.0) + amount
                )
        out: dict[str, CostBreakdown] = {}
        for msn_value, services in agg.items():
            grand = sum(services.values())
            out[msn_value] = CostBreakdown(
                currency=currency,
                grand_total=f"{grand:.10f}",
                by_service={k: f"{v:.10f}" for k, v in services.items()},
                period_start=start,
                period_end=end,
                granularity=granularity,
            )
        return out

    # ------------------------------------------------------------------
    # Fine-grained Cost Explorer (ledger surface)

    @staticmethod
    def _ce_group_spec(token: str) -> dict[str, str]:
        if token.startswith("TAG:"):
            return {"Type": "TAG", "Key": token.split(":", 1)[1]}
        return {"Type": "DIMENSION", "Key": token}

    def get_costs_breakdown(
        self,
        *,
        start: str,
        end: str,
        group_by: tuple[str, ...] = ("SERVICE", "USAGE_TYPE"),
        tag_filter: dict[str, list[str]] | None = None,
        service_filter: list[str] | None = None,
        granularity: str = "MONTHLY",
    ) -> list[CostLineItem]:
        if not 1 <= len(group_by) <= 2:
            raise ValueError("group_by must have 1 or 2 entries (Cost Explorer limit)")
        client = self._client("ce", region="us-east-1")
        kwargs: dict[str, Any] = {
            "TimePeriod": {"Start": start, "End": end},
            "Granularity": granularity,
            "Metrics": ["UnblendedCost", "UsageQuantity"],
            "GroupBy": [self._ce_group_spec(g) for g in group_by],
        }
        clauses: list[dict[str, Any]] = []
        if tag_filter:
            clauses.append({"Tags": tag_filter})
        if service_filter:
            clauses.append({"Dimensions": {"Key": "SERVICE", "Values": list(service_filter)}})
        if len(clauses) == 1:
            kwargs["Filter"] = clauses[0]
        elif len(clauses) > 1:
            kwargs["Filter"] = {"And": clauses}

        # Sum across time periods per (group-key-tuple).
        agg_cost: dict[tuple[str, ...], float] = {}
        agg_qty: dict[tuple[str, ...], float] = {}
        units: dict[tuple[str, ...], str] = {}
        currency = ""
        for result in client.get_cost_and_usage(**kwargs).get("ResultsByTime", []) or []:
            for entry in result.get("Groups", []) or []:
                keys_raw = entry.get("Keys") or []
                # CE encodes tag groups as "key$value"; strip the prefix
                # so the returned line key is just the value.
                keys = tuple(
                    (k.split("$", 1)[1] if "$" in k else k) for k in keys_raw
                )
                metrics = entry.get("Metrics") or {}
                cost = metrics.get("UnblendedCost") or {}
                qty = metrics.get("UsageQuantity") or {}
                currency = currency or str(cost.get("Unit", ""))
                try:
                    agg_cost[keys] = agg_cost.get(keys, 0.0) + float(cost.get("Amount", "0"))
                except ValueError:
                    pass
                try:
                    agg_qty[keys] = agg_qty.get(keys, 0.0) + float(qty.get("Amount", "0"))
                except ValueError:
                    pass
                if qty.get("Unit") and not units.get(keys):
                    units[keys] = str(qty.get("Unit"))

        out: list[CostLineItem] = []
        for keys, amount in agg_cost.items():
            if amount == 0.0 and agg_qty.get(keys, 0.0) == 0.0:
                # Cost Explorer often emits zero-cost groups for free-tier
                # usage; keep them out of the ledger.
                continue
            out.append(CostLineItem(
                keys=keys,
                amount=f"{amount:.10f}",
                currency=currency,
                usage_quantity=f"{agg_qty.get(keys, 0.0):.10f}",
                usage_unit=units.get(keys, ""),
            ))
        # Sort by amount desc so the largest line items are first.
        out.sort(key=lambda r: float(r["amount"]), reverse=True)
        return out

    def get_untagged_residue(
        self,
        *,
        start: str,
        end: str,
        granularity: str = "MONTHLY",
    ) -> CostBreakdown:
        overview = self.get_costs_overview(
            start=start, end=end, granularity=granularity,
        )
        residue = overview.get("")
        if residue is not None:
            return residue
        # No untagged slice in the window — return an empty breakdown
        # rather than KeyError so callers don't need defensive code.
        return CostBreakdown(
            currency="",
            grand_total="0",
            by_service={},
            period_start=start,
            period_end=end,
            granularity=granularity,
        )

    def get_route53_registrar_renewal_lines(
        self,
        *,
        start: str,
        end: str,
        granularity: str = "MONTHLY",
    ) -> list[CostLineItem]:
        return self.get_costs_breakdown(
            start=start, end=end,
            group_by=("SERVICE", "USAGE_TYPE"),
            service_filter=["Amazon Registrar"],
            granularity=granularity,
        )


__all__ = ["AwsPeripheralCloudAdapter"]
