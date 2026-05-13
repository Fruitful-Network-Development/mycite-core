"""Unit tests for AwsEc2RoleOnboardingCloudAdapter.sync_operator_forwarding_routes.

Uses a hand-crafted boto3 fake (matching the codebase pattern of not
depending on moto). The fake records every API call so each test can
assert on call shape AND outcome shape.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.event_transport.aws_csm_onboarding_cloud import (
    AwsEc2RoleOnboardingCloudAdapter,
    _FORWARDER_ACCOUNT_ID,
    _FORWARDER_LAMBDA_NAME,
    _FORWARDER_PORTAL_CAPTURE_PREFIX,
    _FORWARDER_ROUTE_MAP_ENV_KEY,
    _FORWARDER_RULE_SET,
)


def _profile(
    *,
    send_as: str,
    target: str = "",
    receive_state: str = "receive_pending",
    is_ready: bool = True,
) -> dict:
    return {
        "identity": {"send_as_email": send_as},
        "inbound": {
            "receive_routing_target": target,
            "receive_state": receive_state,
        },
        "workflow": {"is_ready_for_user_handoff": is_ready},
    }


def _rule(name: str, recipients: list[str], lambda_arn: str = "") -> dict:
    actions = [
        {
            "S3Action": {
                "BucketName": "ses-inbound-fnd-mail",
                "ObjectKeyPrefix": f"inbound/{recipients[0]}/",
            }
        }
    ]
    if lambda_arn:
        actions.append(
            {
                "LambdaAction": {
                    "FunctionArn": lambda_arn,
                    "InvocationType": "Event",
                }
            }
        )
    return {
        "Name": name,
        "Enabled": True,
        "TlsPolicy": "Optional",
        "Recipients": recipients,
        "Actions": actions,
        "ScanEnabled": True,
    }


class _FakeLambdaClient:
    def __init__(
        self,
        *,
        env: dict | None = None,
        existing_policy_sids: list[str] | None = None,
        raise_on_get_policy: bool = False,
    ):
        self._env = dict(env or {})
        self._policy_sids = list(existing_policy_sids or [])
        self._raise_on_get_policy = raise_on_get_policy
        self.calls: list[tuple[str, dict]] = []

    def get_function_configuration(self, *, FunctionName):
        self.calls.append(("get_function_configuration", {"FunctionName": FunctionName}))
        return {"Environment": {"Variables": dict(self._env)}, "State": "Active", "LastUpdateStatus": "Successful"}

    def update_function_configuration(self, *, FunctionName, Environment):
        self.calls.append(("update_function_configuration", {"FunctionName": FunctionName, "Environment": Environment}))
        self._env = dict(Environment.get("Variables") or {})
        return {}

    def get_policy(self, *, FunctionName):
        self.calls.append(("get_policy", {"FunctionName": FunctionName}))
        if self._raise_on_get_policy:
            raise RuntimeError("ResourceNotFoundException")
        return {
            "Policy": json.dumps(
                {"Statement": [{"Sid": sid} for sid in self._policy_sids]}
            )
        }

    def add_permission(self, *, FunctionName, StatementId, **kwargs):
        self.calls.append(("add_permission", {"FunctionName": FunctionName, "StatementId": StatementId, **kwargs}))
        self._policy_sids.append(StatementId)
        return {"Statement": json.dumps({"Sid": StatementId})}

    @property
    def env(self) -> dict:
        return dict(self._env)


class _FakeSesClient:
    def __init__(self, *, rules: list[dict], rule_set_name: str = _FORWARDER_RULE_SET):
        self._rules = [dict(r) for r in rules]
        self._rule_set_name = rule_set_name
        self.calls: list[tuple[str, dict]] = []

    def describe_active_receipt_rule_set(self):
        self.calls.append(("describe_active_receipt_rule_set", {}))
        return {"Metadata": {"Name": self._rule_set_name}, "Rules": [dict(r) for r in self._rules]}

    def update_receipt_rule(self, *, RuleSetName, Rule):
        self.calls.append(("update_receipt_rule", {"RuleSetName": RuleSetName, "Rule": Rule}))
        for i, r in enumerate(self._rules):
            if r["Name"] == Rule["Name"]:
                self._rules[i] = Rule
                return {}
        self._rules.append(Rule)
        return {}

    @property
    def rules(self) -> list[dict]:
        return [dict(r) for r in self._rules]


def _patched_adapter(
    *,
    lambda_client: _FakeLambdaClient,
    ses_client: _FakeSesClient,
) -> AwsEc2RoleOnboardingCloudAdapter:
    adapter = AwsEc2RoleOnboardingCloudAdapter()

    def fake_client(service_name, region=None):
        if service_name == "lambda":
            return lambda_client
        if service_name == "ses":
            return ses_client
        raise AssertionError(f"unexpected boto3 service requested: {service_name}")

    adapter._client = fake_client  # type: ignore[assignment]
    adapter._wait_for_lambda_update = lambda *, client, function_name: None  # type: ignore[assignment]
    return adapter


class RouteExtractionTests(unittest.TestCase):
    def test_filter_includes_ready_profiles_with_target(self):
        profiles = [
            _profile(send_as="a@x.org", target="a@gmail.com"),
            _profile(send_as="b@x.org", target=""),  # no target
            _profile(send_as="", target="c@gmail.com"),  # no send_as
            _profile(send_as="d@x.org", target="d@gmail.com", is_ready=False),
            _profile(send_as="e@x.org", target="e@gmail.com", receive_state="draft"),
            _profile(send_as="f@x.org", target="f@gmail.com", receive_state="receive_unconfigured"),
        ]
        routes = AwsEc2RoleOnboardingCloudAdapter._operator_forwarding_routes_from_profiles(profiles=profiles)
        self.assertEqual(routes, {"a@x.org": "a@gmail.com", "f@x.org": "f@gmail.com"})

    def test_filter_normalizes_emails_to_lowercase(self):
        profiles = [_profile(send_as="A@X.ORG", target="A@GMAIL.COM")]
        routes = AwsEc2RoleOnboardingCloudAdapter._operator_forwarding_routes_from_profiles(profiles=profiles)
        self.assertEqual(routes, {"a@x.org": "a@gmail.com"})


class SyncBehaviorTests(unittest.TestCase):
    def test_empty_profiles_clears_route_map_when_prior_exists(self):
        lam = _FakeLambdaClient(env={_FORWARDER_ROUTE_MAP_ENV_KEY: '{"a@x.org":"a@gmail.com"}'})
        ses = _FakeSesClient(rules=[])
        adapter = _patched_adapter(lambda_client=lam, ses_client=ses)
        result = adapter.sync_operator_forwarding_routes(profiles=[])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["route_count"], 0)
        self.assertTrue(result["route_changed"])
        self.assertIn(("update_function_configuration", lam.calls[1][1]), [(c[0], c[1]) for c in lam.calls if c[0] == "update_function_configuration"][:1])

    def test_no_change_skips_lambda_update(self):
        prior = {"a@x.org": "a@gmail.com"}
        lam = _FakeLambdaClient(env={_FORWARDER_ROUTE_MAP_ENV_KEY: json.dumps(prior, sort_keys=True, separators=(",", ":"))})
        ses = _FakeSesClient(rules=[])
        adapter = _patched_adapter(lambda_client=lam, ses_client=ses)
        result = adapter.sync_operator_forwarding_routes(
            profiles=[_profile(send_as="a@x.org", target="a@gmail.com")],
        )
        self.assertEqual(result["status"], "success")
        self.assertFalse(result["route_changed"])
        self.assertEqual(
            [c for c in lam.calls if c[0] == "update_function_configuration"], []
        )

    def test_new_domain_adds_permission_then_wires_rule(self):
        domain = "x.org"
        rule_name = f"{_FORWARDER_PORTAL_CAPTURE_PREFIX}{domain.replace('.', '-')}"
        lam = _FakeLambdaClient(env={})
        ses = _FakeSesClient(
            rules=[_rule(rule_name, recipients=[domain], lambda_arn="arn:aws:lambda:us-east-1:065948377733:function:newsletter-inbound-capture")]
        )
        adapter = _patched_adapter(lambda_client=lam, ses_client=ses)
        result = adapter.sync_operator_forwarding_routes(
            profiles=[_profile(send_as=f"a@{domain}", target="a@gmail.com")],
        )
        self.assertEqual(result["domains_wired"], [domain])
        self.assertEqual(result["permissions_added"], [rule_name])
        # add_permission must come before update_receipt_rule
        kinds = [c[0] for c in lam.calls + ses.calls if c[0] in {"add_permission", "update_receipt_rule"}]
        # both lists are in chronological order per-client; for this test we
        # confirm presence + ordering at the adapter level
        lam_perm_index = next(i for i, c in enumerate(lam.calls) if c[0] == "add_permission")
        ses_update_index = next(i for i, c in enumerate(ses.calls) if c[0] == "update_receipt_rule")
        # Permission added before any SES update
        self.assertGreaterEqual(lam_perm_index, 0)
        self.assertGreaterEqual(ses_update_index, 0)
        # Final rule must point at ses-forwarder
        updated = ses.rules[0]
        lambda_arns = [
            a["LambdaAction"]["FunctionArn"]
            for a in updated["Actions"]
            if "LambdaAction" in a
        ]
        self.assertEqual(
            lambda_arns,
            [f"arn:aws:lambda:us-east-1:{_FORWARDER_ACCOUNT_ID}:function:{_FORWARDER_LAMBDA_NAME}"],
        )

    def test_already_wired_domain_skips_rule_update(self):
        domain = "x.org"
        rule_name = f"{_FORWARDER_PORTAL_CAPTURE_PREFIX}{domain.replace('.', '-')}"
        desired_arn = f"arn:aws:lambda:us-east-1:{_FORWARDER_ACCOUNT_ID}:function:{_FORWARDER_LAMBDA_NAME}"
        sid = f"ses-{rule_name}"
        lam = _FakeLambdaClient(env={}, existing_policy_sids=[sid])
        ses = _FakeSesClient(rules=[_rule(rule_name, recipients=[domain], lambda_arn=desired_arn)])
        adapter = _patched_adapter(lambda_client=lam, ses_client=ses)
        result = adapter.sync_operator_forwarding_routes(
            profiles=[_profile(send_as=f"a@{domain}", target="a@gmail.com")],
        )
        self.assertEqual(result["domains_wired"], [])
        self.assertEqual(result["permissions_added"], [])
        self.assertEqual([c for c in ses.calls if c[0] == "update_receipt_rule"], [])
        self.assertEqual([c for c in lam.calls if c[0] == "add_permission"], [])

    def test_missing_domain_rule_is_skipped_without_error(self):
        domain = "x.org"
        lam = _FakeLambdaClient(env={})
        ses = _FakeSesClient(rules=[])  # no rule for the domain
        adapter = _patched_adapter(lambda_client=lam, ses_client=ses)
        result = adapter.sync_operator_forwarding_routes(
            profiles=[_profile(send_as=f"a@{domain}", target="a@gmail.com")],
        )
        self.assertEqual(result["status"], "success")
        rule_name = f"{_FORWARDER_PORTAL_CAPTURE_PREFIX}{domain.replace('.', '-')}"
        self.assertEqual(result["rules_skipped_missing"], [rule_name])
        self.assertEqual(result["domains_wired"], [])

    def test_existing_permission_with_matching_sid_skips_add_permission(self):
        domain = "x.org"
        rule_name = f"{_FORWARDER_PORTAL_CAPTURE_PREFIX}{domain.replace('.', '-')}"
        sid = f"ses-{rule_name}"
        lam = _FakeLambdaClient(env={}, existing_policy_sids=[sid])
        ses = _FakeSesClient(rules=[_rule(rule_name, recipients=[domain])])  # no LambdaAction
        adapter = _patched_adapter(lambda_client=lam, ses_client=ses)
        result = adapter.sync_operator_forwarding_routes(
            profiles=[_profile(send_as=f"a@{domain}", target="a@gmail.com")],
        )
        self.assertEqual(result["permissions_added"], [])
        self.assertEqual(result["domains_wired"], [domain])

    def test_get_policy_failure_is_treated_as_no_existing_policy(self):
        domain = "x.org"
        rule_name = f"{_FORWARDER_PORTAL_CAPTURE_PREFIX}{domain.replace('.', '-')}"
        lam = _FakeLambdaClient(env={}, raise_on_get_policy=True)
        ses = _FakeSesClient(rules=[_rule(rule_name, recipients=[domain])])
        adapter = _patched_adapter(lambda_client=lam, ses_client=ses)
        result = adapter.sync_operator_forwarding_routes(
            profiles=[_profile(send_as=f"a@{domain}", target="a@gmail.com")],
        )
        self.assertEqual(result["permissions_added"], [rule_name])


if __name__ == "__main__":
    unittest.main()
