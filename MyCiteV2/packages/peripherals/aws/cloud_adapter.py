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

    def ensure_domain_identity(self, domain: str) -> dict[str, Any]:
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
        return {"ok": True, "changed": changed, "domain": token}

    def sync_domain_dns(self, domain: str) -> dict[str, Any]:
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
                                    "rua=mailto:dylan@fruitfulnetworkdevelopment.com; "
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

        if not desired_changes:
            return {"ok": True, "changed": [], "domain": token, "zone_id": zone_id}

        r53.change_resource_record_sets(
            HostedZoneId=zone_id,
            ChangeBatch={"Comment": "aws-peripheral sync_domain_dns", "Changes": desired_changes},
        )
        return {
            "ok": True,
            "changed": [c["ResourceRecordSet"]["Type"] for c in desired_changes],
            "domain": token,
            "zone_id": zone_id,
        }

    def ensure_domain_receipt_rule(self, domain: str) -> dict[str, Any]:
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
        return {"ok": True, "changed": [rule_name], "rule_name": rule_name}

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


__all__ = ["AwsPeripheralCloudAdapter"]
