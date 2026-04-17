from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from MyCiteV2.packages.ports.aws_csm_newsletter import AwsCsmNewsletterCloudPort


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalized_domain(value: object) -> str:
    token = _as_text(value).lower()
    if token.startswith("www."):
        token = token[4:]
    return token


def _normalized_email(value: object) -> str:
    token = _as_text(value).lower()
    if token.count("@") != 1 or any(ch.isspace() for ch in token):
        return ""
    local_part, domain_part = token.split("@", 1)
    if not local_part or not domain_part or "." not in domain_part:
        return ""
    return token


def _email_domain(value: object) -> str:
    token = _normalized_email(value)
    return token.split("@", 1)[1] if token else ""


def _iso_timestamp(value: object) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return _as_text(value)


def _split_s3_uri(s3_uri: str) -> tuple[str, str]:
    token = _as_text(s3_uri)
    if not token.startswith("s3://"):
        raise ValueError("s3_uri must start with s3://")
    body = token[5:]
    if "/" not in body:
        raise ValueError("s3_uri must include an object key")
    bucket, key = body.split("/", 1)
    if not bucket or not key:
        raise ValueError("s3_uri must include a bucket and key")
    return bucket, key


class AwsEc2RoleNewsletterCloudAdapter(AwsCsmNewsletterCloudPort):
    def _client(self, service_name: str, *, region: str | None = None) -> Any:
        import boto3

        kwargs = {"region_name": region} if region else {}
        return boto3.client(service_name, **kwargs)

    def get_or_create_secret_value(
        self,
        *,
        secret_name: str,
        initial_value: str,
    ) -> str:
        client = self._client("secretsmanager", region="us-east-1")
        try:
            response = client.get_secret_value(SecretId=secret_name)
            return _as_text(response.get("SecretString"))
        except client.exceptions.ResourceNotFoundException:
            client.create_secret(Name=secret_name, SecretString=initial_value)
            response = client.get_secret_value(SecretId=secret_name)
            return _as_text(response.get("SecretString"))

    def queue_dispatch_message(
        self,
        *,
        queue_url: str,
        payload: dict[str, Any],
        region: str,
    ) -> str:
        client = self._client("sqs", region=region)
        response = client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(payload, separators=(",", ":")),
        )
        return _as_text(response.get("MessageId"))

    def read_s3_bytes(self, *, s3_uri: str, region: str) -> bytes:
        bucket, key = _split_s3_uri(s3_uri)
        client = self._client("s3", region=region)
        response = client.get_object(Bucket=bucket, Key=key)
        body = response.get("Body")
        if body is None:
            raise ValueError("s3 object response did not include a body")
        return bytes(body.read())

    def list_s3_objects(
        self,
        *,
        bucket: str,
        prefix: str,
        region: str,
        max_keys: int = 20,
    ) -> list[dict[str, str]]:
        client = self._client("s3", region=region)
        response = client.list_objects_v2(
            Bucket=_as_text(bucket),
            Prefix=_as_text(prefix),
            MaxKeys=max(1, int(max_keys)),
        )
        out: list[dict[str, str]] = []
        for row in list(response.get("Contents") or []):
            if not isinstance(row, dict):
                continue
            key = _as_text(row.get("Key"))
            if not key:
                continue
            out.append(
                {
                    "bucket": _as_text(bucket),
                    "key": key,
                    "s3_uri": f"s3://{_as_text(bucket)}/{key}",
                    "last_modified": _iso_timestamp(row.get("LastModified")),
                    "etag": _as_text(row.get("ETag")),
                    "size": _as_text(row.get("Size")),
                }
            )
        out.sort(key=lambda item: item.get("last_modified") or "", reverse=True)
        return out

    def caller_identity_summary(self) -> dict[str, Any]:
        try:
            response = self._client("sts").get_caller_identity()
            return {
                "status": "ok",
                "account": _as_text(response.get("Account")),
                "arn": _as_text(response.get("Arn")),
                "user_id": _as_text(response.get("UserId")),
            }
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "message": _as_text(exc)}

    def queue_health_summary(self, *, queue_url: str, queue_arn: str, region: str) -> dict[str, Any]:
        try:
            attrs = self._client("sqs", region=region).get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=["QueueArn", "ApproximateNumberOfMessages"],
            )
            values = dict(attrs.get("Attributes") or {})
            return {
                "status": "ok",
                "queue_arn": _as_text(values.get("QueueArn")) or queue_arn,
                "pending_message_count": int(values.get("ApproximateNumberOfMessages") or 0),
            }
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "message": _as_text(exc)}

    def lambda_health_summary(self, *, function_name: str, region: str) -> dict[str, Any]:
        try:
            response = self._client("lambda", region=region).get_function(FunctionName=function_name)
            configuration = dict(response.get("Configuration") or {})
            return {
                "status": _as_text(configuration.get("State")).lower() or "ok",
                "function_arn": _as_text(configuration.get("FunctionArn")),
                "role": _as_text(configuration.get("Role")),
                "last_modified": _as_text(configuration.get("LastModified")),
            }
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "message": _as_text(exc)}

    def receipt_rule_summary(
        self,
        *,
        domain: str,
        expected_recipient: str,
        expected_lambda_name: str,
        region: str,
    ) -> dict[str, Any]:
        try:
            response = self._client("ses", region=region).describe_active_receipt_rule_set()
            rules = list(response.get("Rules") or [])
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "message": _as_text(exc)}
        matching = []
        expected_email = _normalized_email(expected_recipient)
        expected_domain = _email_domain(expected_email) or _normalized_domain(domain)
        expected_function_arn_suffix = f":function:{expected_lambda_name}" if expected_lambda_name else ""
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            recipients = [str(item or "").lower() for item in list(rule.get("Recipients") or [])]
            actions = list(rule.get("Actions") or [])
            lambda_actions = [
                dict(action.get("LambdaAction") or {})
                for action in actions
                if isinstance(action, dict) and isinstance(action.get("LambdaAction"), dict)
            ]
            s3_actions = [
                dict(action.get("S3Action") or {})
                for action in actions
                if isinstance(action, dict) and isinstance(action.get("S3Action"), dict)
            ]
            lambda_ok = any(
                (
                    not expected_function_arn_suffix
                    or _as_text(action.get("FunctionArn")).endswith(expected_function_arn_suffix)
                )
                for action in lambda_actions
            )
            s3_ok = bool(s3_actions)
            matched_recipient = ""
            match_kind = ""
            for candidate in recipients:
                if expected_email and candidate == expected_email:
                    matched_recipient = candidate
                    match_kind = "exact_recipient"
                    break
                if expected_domain and candidate == expected_domain:
                    matched_recipient = candidate
                    match_kind = "domain_recipient"
                    break
            if matched_recipient:
                primary_s3 = s3_actions[0] if s3_actions else {}
                primary_lambda = lambda_actions[0] if lambda_actions else {}
                matching.append(
                    {
                        "rule_name": _as_text(rule.get("Name")),
                        "recipient_match": True,
                        "recipient_match_kind": match_kind,
                        "matched_recipient": matched_recipient,
                        "s3_action_present": s3_ok,
                        "lambda_action_present": lambda_ok,
                        "lambda_function_arn": _as_text(primary_lambda.get("FunctionArn")),
                        "s3_bucket": _as_text(primary_s3.get("BucketName")),
                        "s3_prefix": _as_text(primary_s3.get("ObjectKeyPrefix")),
                        "s3_uri_prefix": (
                            f"s3://{_as_text(primary_s3.get('BucketName'))}/{_as_text(primary_s3.get('ObjectKeyPrefix'))}"
                            if _as_text(primary_s3.get("BucketName"))
                            else ""
                        ),
                    }
                )
        if not matching:
            return {
                "status": "not_ready",
                "domain": _as_text(domain),
                "expected_recipient": expected_email or _as_text(expected_recipient),
                "expected_domain": expected_domain,
                "message": "No active SES receipt rule matches the expected send-as address or its domain recipient.",
            }
        ready = any(row["s3_action_present"] and row["lambda_action_present"] for row in matching)
        return {
            "status": "ok" if ready else "not_ready",
            "domain": _as_text(domain),
            "expected_recipient": expected_email or _as_text(expected_recipient),
            "expected_domain": expected_domain,
            "matching_rules": matching,
        }
