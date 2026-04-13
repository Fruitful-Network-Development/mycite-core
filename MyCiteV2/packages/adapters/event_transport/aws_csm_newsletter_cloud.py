from __future__ import annotations

import json
from typing import Any

from MyCiteV2.packages.ports.aws_csm_newsletter import AwsCsmNewsletterCloudPort


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


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
        expected_function_arn_suffix = f":function:{expected_lambda_name}" if expected_lambda_name else ""
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            recipients = [str(item or "").lower() for item in list(rule.get("Recipients") or [])]
            actions = list(rule.get("Actions") or [])
            lambda_ok = any(
                isinstance(action, dict)
                and isinstance(action.get("LambdaAction"), dict)
                and (
                    not expected_function_arn_suffix
                    or str((action.get("LambdaAction") or {}).get("FunctionArn") or "").endswith(expected_function_arn_suffix)
                )
                for action in actions
            )
            s3_ok = any(isinstance(action, dict) and isinstance(action.get("S3Action"), dict) for action in actions)
            if expected_recipient.lower() in recipients:
                matching.append(
                    {
                        "rule_name": _as_text(rule.get("Name")),
                        "recipient_match": True,
                        "s3_action_present": s3_ok,
                        "lambda_action_present": lambda_ok,
                    }
                )
        if not matching:
            return {
                "status": "not_ready",
                "domain": _as_text(domain),
                "expected_recipient": expected_recipient,
                "message": "No active SES receipt rule matches the canonical news@ recipient.",
            }
        ready = any(row["s3_action_present"] and row["lambda_action_present"] for row in matching)
        return {
            "status": "ok" if ready else "not_ready",
            "domain": _as_text(domain),
            "expected_recipient": expected_recipient,
            "matching_rules": matching,
        }
