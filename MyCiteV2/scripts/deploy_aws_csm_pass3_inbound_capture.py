from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_ROOT = Path("/srv/mycite-state/instances/fnd/private/utilities/tools/aws-csm")
LAMBDA_SOURCE = REPO_ROOT / "MyCiteV2" / "packages" / "adapters" / "event_transport" / "aws_csm_inbound_capture_lambda.py"
RULE_SET_NAME = "fnd-inbound-rules"
FUNCTION_NAME = "newsletter-inbound-capture"
FUNCTION_REGION = "us-east-1"
FUNCTION_ROLE_NAME = "newsletter-inbound-capture-role"
FUNCTION_ROLE_POLICY_NAME = "NewsletterInboundCaptureExecution"
FORWARD_FROM_ADDRESS = "forwarder@fruitfulnetworkdevelopment.com"
INBOUND_BUCKET = "ses-inbound-fnd-mail"
INBOUND_SECRET_NAME = "aws-cms/newsletter/inbound-capture/fnd"


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _normalized_domain(value: object) -> str:
    token = _text(value).lower()
    if token.startswith("www."):
        token = token[4:]
    return token


def _normalized_email(value: object) -> str:
    token = _text(value).lower()
    if token.count("@") != 1 or any(ch.isspace() for ch in token):
        return ""
    local_part, domain_part = token.split("@", 1)
    if not local_part or not domain_part or "." not in domain_part:
        return ""
    return token


def _normalized_handoff_provider(value: object) -> str:
    token = _text(value).lower()
    if token in {"gmail", "outlook", "yahoo", "proofpoint", "generic_manual"}:
        return token
    return ""


def _provider_from_email(email: object) -> str:
    token = _normalized_email(email)
    domain = token.split("@", 1)[1] if token else ""
    if domain in {"gmail.com", "googlemail.com"}:
        return "gmail"
    if domain in {"outlook.com", "hotmail.com", "live.com", "msn.com"}:
        return "outlook"
    if domain in {"yahoo.com", "rocketmail.com", "ymail.com"}:
        return "yahoo"
    if domain.endswith("proofpoint.com"):
        return "proofpoint"
    return "generic_manual"


def _resolve_forward_target(
    *,
    start_recipient: str,
    routes: dict[str, dict[str, Any]],
) -> tuple[str, str, list[str]]:
    current = _normalized_email(start_recipient)
    chain: list[str] = []
    visited: set[str] = set()
    while current:
        if current in visited:
            chain.append(current)
            return current, "cycle_detected", chain
        visited.add(current)
        chain.append(current)
        route = dict(routes.get(current) or {})
        target = _normalized_email(route.get("forward_to_email"))
        if not target:
            return "", "missing_target", chain
        if target == current:
            chain.append(target)
            return target, "resolved_self", chain
        if target not in routes:
            chain.append(target)
            return target, "resolved_external", chain
        if len(chain) >= 24:
            chain.append(target)
            return target, "max_hops_exceeded", chain
        current = target
    return "", "missing_target", chain


def _aws(*args: str, expect_json: bool = True) -> Any:
    command = ["aws", *args]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"AWS CLI command failed ({' '.join(command)}):\n{completed.stderr.strip() or completed.stdout.strip()}"
        )
    output = completed.stdout.strip()
    if not expect_json:
        return output
    if not output:
        return {}
    return json.loads(output)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return dict(payload) if isinstance(payload, dict) else {}


def _build_route_map(state_root: Path) -> dict[str, dict[str, Any]]:
    routes: dict[str, dict[str, Any]] = {}
    for path in sorted(state_root.glob("aws-csm.*.json")):
        payload = _load_json(path)
        if _text(payload.get("schema")) != "mycite.service_tool.aws_csm.profile.v1":
            continue
        identity = payload.get("identity") if isinstance(payload.get("identity"), dict) else {}
        smtp = payload.get("smtp") if isinstance(payload.get("smtp"), dict) else {}
        provider = payload.get("provider") if isinstance(payload.get("provider"), dict) else {}
        send_as_email = _normalized_email(identity.get("send_as_email") or smtp.get("send_as_email"))
        forward_to_email = _normalized_email(smtp.get("forward_to_email") or identity.get("operator_inbox_target"))
        if not send_as_email or not forward_to_email:
            continue
        routes[send_as_email] = {
            "forward_to_email": forward_to_email,
            "profile_id": _text(identity.get("profile_id")),
            "domain": _normalized_domain(identity.get("domain")) or send_as_email.split("@", 1)[1],
            "handoff_provider": (
                _normalized_handoff_provider(
                    provider.get("handoff_provider")
                    or identity.get("handoff_provider")
                    or smtp.get("handoff_provider")
                )
                or _provider_from_email(forward_to_email)
            ),
        }
    resolved: dict[str, dict[str, Any]] = {}
    for send_as_email, route in sorted(routes.items()):
        resolved_forward_to_email, resolution_status, chain = _resolve_forward_target(
            start_recipient=send_as_email,
            routes=routes,
        )
        resolved[send_as_email] = {
            "forward_to_email": _text(route.get("forward_to_email")),
            "resolved_forward_to_email": resolved_forward_to_email or _text(route.get("forward_to_email")),
            "source_forward_to_email": _text(route.get("forward_to_email")),
            "forward_resolution_status": resolution_status,
            "forward_chain": list(chain),
            "profile_id": _text(route.get("profile_id")),
            "domain": _text(route.get("domain")),
            "handoff_provider": _text(route.get("handoff_provider")) or "generic_manual",
        }
    return resolved


def _package_lambda_source() -> Path:
    if not LAMBDA_SOURCE.exists():
        raise FileNotFoundError(f"lambda source not found: {LAMBDA_SOURCE}")
    temp_dir = Path(tempfile.mkdtemp(prefix="aws-csm-pass3-lambda-"))
    zip_path = temp_dir / "newsletter-inbound-capture-pass3.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(LAMBDA_SOURCE, arcname="lambda_function.py")
    return zip_path


def _build_role_policy_document() -> dict[str, Any]:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowLogs",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                "Resource": "*",
            },
            {
                "Sid": "AllowInboundSecretRead",
                "Effect": "Allow",
                "Action": [
                    "secretsmanager:GetSecretValue",
                ],
                "Resource": f"arn:aws:secretsmanager:{FUNCTION_REGION}:065948377733:secret:{INBOUND_SECRET_NAME}*",
            },
            {
                "Sid": "AllowReadInboundCaptureObjects",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                ],
                "Resource": f"arn:aws:s3:::{INBOUND_BUCKET}/inbound/*",
            },
            {
                "Sid": "AllowForwardVerificationMail",
                "Effect": "Allow",
                "Action": [
                    "ses:SendEmail",
                    "ses:SendRawEmail",
                    "sesv2:SendEmail",
                ],
                "Resource": "*",
            },
        ],
    }


def _wait_for_function_update(function_name: str) -> None:
    deadline = time.time() + 300
    while time.time() < deadline:
        payload = _aws(
            "lambda",
            "get-function-configuration",
            "--function-name",
            function_name,
            "--region",
            FUNCTION_REGION,
        )
        status = _text(payload.get("LastUpdateStatus"))
        state = _text(payload.get("State"))
        if status in {"Successful", ""} and state in {"Active", ""}:
            return
        if status == "Failed":
            raise RuntimeError(f"Lambda update failed for {function_name}: {_text(payload.get('LastUpdateStatusReason'))}")
        time.sleep(3)
    raise TimeoutError(f"Timed out waiting for Lambda update on {function_name}")


def _update_function_code(function_name: str, zip_path: Path) -> None:
    _aws(
        "lambda",
        "update-function-code",
        "--function-name",
        function_name,
        "--region",
        FUNCTION_REGION,
        "--zip-file",
        f"fileb://{zip_path}",
    )
    _wait_for_function_update(function_name)


def _update_function_configuration(function_name: str, *, route_map: dict[str, dict[str, str]]) -> dict[str, Any]:
    current = _aws(
        "lambda",
        "get-function-configuration",
        "--function-name",
        function_name,
        "--region",
        FUNCTION_REGION,
    )
    environment = dict((current.get("Environment") or {}).get("Variables") or {})
    environment.update(
        {
            "S3_BUCKET": INBOUND_BUCKET,
            "S3_PREFIX_TEMPLATE": "inbound/{domain}/",
            "INBOUND_SECRET_NAME": INBOUND_SECRET_NAME,
            "CALLBACK_URL_TEMPLATE": "https://{domain}/__fnd/newsletter/inbound-capture",
            "SES_REGION": FUNCTION_REGION,
            "VERIFICATION_ROUTE_MAP_JSON": json.dumps(route_map, separators=(",", ":"), sort_keys=True),
            "VERIFICATION_ALLOWED_SENDERS_JSON": json.dumps(["gmail-noreply@google.com"]),
            "VERIFICATION_FORWARD_FROM_ADDRESS": FORWARD_FROM_ADDRESS,
        }
    )
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump({"Variables": environment}, handle)
        env_path = Path(handle.name)
    try:
        _aws(
            "lambda",
            "update-function-configuration",
            "--function-name",
            function_name,
            "--region",
            FUNCTION_REGION,
            "--environment",
            f"file://{env_path}",
            "--timeout",
            "30",
        )
    finally:
        env_path.unlink(missing_ok=True)
    _wait_for_function_update(function_name)
    return environment


def _put_role_policy(role_name: str, policy_name: str, policy_document: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(policy_document, handle)
        path = Path(handle.name)
    try:
        _aws(
            "iam",
            "put-role-policy",
            "--role-name",
            role_name,
            "--policy-name",
            policy_name,
            "--policy-document",
            f"file://{path}",
            expect_json=False,
        )
    finally:
        path.unlink(missing_ok=True)


def _source_rule_arn(rule_name: str) -> str:
    return f"arn:aws:ses:{FUNCTION_REGION}:065948377733:receipt-rule-set/{RULE_SET_NAME}:receipt-rule/{rule_name}"


def _current_lambda_policy(function_name: str) -> dict[str, Any]:
    try:
        payload = _aws(
            "lambda",
            "get-policy",
            "--function-name",
            function_name,
            "--region",
            FUNCTION_REGION,
        )
    except RuntimeError:
        return {}
    policy_text = _text(payload.get("Policy"))
    if not policy_text:
        return {}
    return json.loads(policy_text)


def _ensure_lambda_permission(function_name: str, rule_name: str) -> None:
    current = _current_lambda_policy(function_name)
    statements = list(current.get("Statement") or []) if isinstance(current, dict) else []
    statement_id = rule_name
    desired_source_arn = _source_rule_arn(rule_name)
    existing = next((row for row in statements if isinstance(row, dict) and _text(row.get("Sid")) == statement_id), None)
    if existing is not None:
        arn_like = ((existing.get("Condition") or {}).get("ArnLike") or {}).get("AWS:SourceArn")
        source_account = ((existing.get("Condition") or {}).get("StringEquals") or {}).get("AWS:SourceAccount")
        if _text(arn_like) == desired_source_arn and _text(source_account) == "065948377733":
            return
        _aws(
            "lambda",
            "remove-permission",
            "--function-name",
            function_name,
            "--region",
            FUNCTION_REGION,
            "--statement-id",
            statement_id,
            expect_json=False,
        )
    _aws(
        "lambda",
        "add-permission",
        "--function-name",
        function_name,
        "--region",
        FUNCTION_REGION,
        "--statement-id",
        statement_id,
        "--action",
        "lambda:InvokeFunction",
        "--principal",
        "ses.amazonaws.com",
        "--source-account",
        "065948377733",
        "--source-arn",
        desired_source_arn,
    )


def _updated_rule(rule: dict[str, Any], *, function_arn: str) -> dict[str, Any]:
    name = _text(rule.get("Name"))
    actions = list(rule.get("Actions") or [])
    s3_action = next(
        (dict(action.get("S3Action") or {}) for action in actions if isinstance(action, dict) and isinstance(action.get("S3Action"), dict)),
        {},
    )
    other_actions = [
        action
        for action in actions
        if isinstance(action, dict) and not isinstance(action.get("S3Action"), dict) and not isinstance(action.get("LambdaAction"), dict)
    ]
    if name == "mode-a-forward-dcmontgomery":
        s3_action["BucketName"] = INBOUND_BUCKET
        s3_action["ObjectKeyPrefix"] = "inbound/fruitfulnetworkdevelopment.com/"
    new_actions: list[dict[str, Any]] = []
    if s3_action:
        new_actions.append({"S3Action": s3_action})
    new_actions.append(
        {
            "LambdaAction": {
                "FunctionArn": function_arn,
                "InvocationType": "Event",
            }
        }
    )
    new_actions.extend(other_actions)
    return {
        "Name": name,
        "Enabled": bool(rule.get("Enabled", True)),
        "TlsPolicy": _text(rule.get("TlsPolicy")) or "Optional",
        "Recipients": list(rule.get("Recipients") or []),
        "Actions": new_actions,
        "ScanEnabled": bool(rule.get("ScanEnabled", True)),
    }


def _update_receipt_rules(function_arn: str) -> list[dict[str, Any]]:
    active = _aws("ses", "describe-active-receipt-rule-set", "--region", FUNCTION_REGION)
    rules = list(active.get("Rules") or [])
    target_names = [
        "portal-capture-trappfamilyfarm-com",
        "portal-capture-cuyahogavalleycountrysideconservancy-org",
        "mode-a-forward-dcmontgomery",
    ]
    updated: list[dict[str, Any]] = []
    for rule_name in target_names:
        source = next((rule for rule in rules if isinstance(rule, dict) and _text(rule.get("Name")) == rule_name), None)
        if source is None:
            raise LookupError(f"active receipt rule not found: {rule_name}")
        payload = _updated_rule(source, function_arn=function_arn)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            json.dump(payload, handle)
            path = Path(handle.name)
        try:
            _aws(
                "ses",
                "update-receipt-rule",
                "--region",
                FUNCTION_REGION,
                "--rule-set-name",
                RULE_SET_NAME,
                "--rule",
                f"file://{path}",
                expect_json=False,
            )
        finally:
            path.unlink(missing_ok=True)
        updated.append(payload)
    return updated


def deploy(*, apply: bool, state_root: Path) -> dict[str, Any]:
    route_map = _build_route_map(state_root)
    if not route_map:
        raise RuntimeError(f"no AWS-CSM verification routes discovered under {state_root}")
    current = _aws(
        "lambda",
        "get-function-configuration",
        "--function-name",
        FUNCTION_NAME,
        "--region",
        FUNCTION_REGION,
    )
    summary = {
        "function_name": FUNCTION_NAME,
        "function_region": FUNCTION_REGION,
        "route_count": len(route_map),
        "tracked_recipients": sorted(route_map),
        "forward_targets": {key: value["forward_to_email"] for key, value in route_map.items()},
        "apply": apply,
    }
    if not apply:
        return summary

    zip_path = _package_lambda_source()
    try:
        _put_role_policy(FUNCTION_ROLE_NAME, FUNCTION_ROLE_POLICY_NAME, _build_role_policy_document())
        _update_function_code(FUNCTION_NAME, zip_path)
        environment = _update_function_configuration(FUNCTION_NAME, route_map=route_map)
        for rule_name in (
            "portal-capture-trappfamilyfarm-com",
            "portal-capture-cuyahogavalleycountrysideconservancy-org",
            "mode-a-forward-dcmontgomery",
        ):
            _ensure_lambda_permission(FUNCTION_NAME, rule_name)
        updated_rules = _update_receipt_rules(_text(current.get("FunctionArn")) or f"arn:aws:lambda:{FUNCTION_REGION}:065948377733:function:{FUNCTION_NAME}")
    finally:
        zip_path.unlink(missing_ok=True)
        zip_path.parent.rmdir()
    summary["environment"] = environment
    summary["updated_rules"] = [row["Name"] for row in updated_rules]
    return summary


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Deploy AWS-CSM pass 3 inbound capture replacement.")
    parser.add_argument("--apply", action="store_true", help="Apply the live AWS changes instead of printing the plan.")
    parser.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT), help="Path to the aws-csm state root.")
    args = parser.parse_args(argv)

    summary = deploy(apply=bool(args.apply), state_root=Path(args.state_root))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
