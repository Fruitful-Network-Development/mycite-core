from __future__ import annotations

from typing import Any

SERVICE_TOOL_CONTRACT_SCHEMA = "mycite.service_tool.contract.v1"
SERVICE_TOOL_BINDINGS_SCHEMA = "mycite.service_tool.config_bindings.v1"
FND_EBI_PROFILE_SCHEMA = "mycite.service_tool.fnd_ebi.profile.v1"
AWS_CSM_PROFILE_SCHEMA = "mycite.service_tool.aws_csm.profile.v1"
NEWSLETTER_PROFILE_SCHEMA = "mycite.service_tool.newsletter.profile.v1"
AWS_CSM_DEFAULT_REGION = "us-east-1"

SERVICE_TOOL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "fnd_ebi": {
        "namespace": "fnd-ebi",
        "workspace_id": "service.fnd_ebi",
        "label": "Analytics profile cards",
        "default_mode": "overview",
        "modes": ["overview", "traffic", "events", "errors_noise", "files"],
        "config_patterns": ["tool.*.fnd-ebi.json", "fnd-ebi.{portal_instance_id}.json", "fnd-ebi.*.json"],
        "collection_patterns": ["tool.*.fnd-ebi.json", "web-analytics.json"],
        "member_patterns": ["spec.json", "fnd-ebi.*.json", "*.ndjson"],
        "profile_schema": FND_EBI_PROFILE_SCHEMA,
    },
    "aws_platform_admin": {
        "namespace": "aws-csm",
        "workspace_id": "service.aws_csm",
        "label": "AWS send-as onboarding",
        "default_mode": "overview",
        "modes": ["overview", "smtp", "verification", "files"],
        "config_patterns": [
            "tool.*.aws-csm.json",
            "aws-csm.{portal_instance_id}.*.json",
            "aws-csm.{portal_instance_id}.json",
            "aws-csm.*.json",
        ],
        "collection_patterns": ["tool.*.aws-csm.json"],
        "member_patterns": ["spec.json", "aws-csm.*.json", "*audit*.json", "actions.ndjson", "provision_requests.ndjson"],
        "profile_schema": AWS_CSM_PROFILE_SCHEMA,
    },
    "newsletter_admin": {
        "namespace": "newsletter-admin",
        "workspace_id": "service.newsletter_admin",
        "label": "Newsletter contact lists",
        "default_mode": "overview",
        "modes": ["overview", "contacts", "composer", "files"],
        "config_patterns": [
            "tool.*.newsletter-admin.json",
            "newsletter-admin.{portal_instance_id}.json",
            "newsletter-admin.*.json",
        ],
        "collection_patterns": ["tool.*.newsletter-admin.json"],
        "member_patterns": ["spec.json", "newsletter-admin.*.json", "*.ndjson"],
        "profile_schema": NEWSLETTER_PROFILE_SCHEMA,
    },
    "paypal_service_agreement": {
        "namespace": "paypal-csm",
        "workspace_id": "service.paypal_service_agreement",
        "label": "PayPal service profiles",
        "default_mode": "profiles",
        "modes": ["profiles", "collections", "files"],
        "config_patterns": ["tool.*.paypal-csm.json", "{portal_instance_id}.json", "paypal-csm.{portal_instance_id}.json"],
        "collection_patterns": ["tool.*.paypal-csm.json", "paypal-csm.collection.json"],
        "member_patterns": ["spec.json", "paypal-csm.collection.json", "{portal_instance_id}.json", "paypal-csm.{portal_instance_id}.json", "*.ndjson"],
    },
    "paypal_tenant_actions": {
        "namespace": "paypal-csm",
        "workspace_id": "service.paypal_tenant_actions",
        "label": "PayPal service profiles",
        "default_mode": "profiles",
        "modes": ["profiles", "collections", "files"],
        "config_patterns": ["tool.*.paypal-csm.json", "{portal_instance_id}.json", "paypal-csm.{portal_instance_id}.json"],
        "collection_patterns": ["tool.*.paypal-csm.json", "paypal-csm.collection.json"],
        "member_patterns": ["spec.json", "paypal-csm.collection.json", "{portal_instance_id}.json", "paypal-csm.{portal_instance_id}.json", "*.ndjson"],
    },
    "operations": {
        "namespace": "keycloak-sso",
        "workspace_id": "service.operations",
        "label": "Portal operations cards",
        "default_mode": "profiles",
        "modes": ["profiles", "collections", "files"],
        "config_patterns": ["tool.*.keycloak-sso.json", "keycloak-sso.{portal_instance_id}.json", "keycloak-sso.*.json"],
        "collection_patterns": ["tool.*.keycloak-sso.json", "portal_instances.json"],
        "member_patterns": ["spec.json", "portal_instances.json", "keycloak-sso.*.json", "*.ndjson"],
    },
    "fnd_provisioning": {
        "namespace": "keycloak-sso",
        "workspace_id": "service.fnd_provisioning",
        "label": "Portal operations cards",
        "default_mode": "profiles",
        "modes": ["profiles", "collections", "files"],
        "config_patterns": ["tool.*.keycloak-sso.json", "keycloak-sso.{portal_instance_id}.json", "keycloak-sso.*.json"],
        "collection_patterns": ["tool.*.keycloak-sso.json", "portal_instances.json"],
        "member_patterns": ["spec.json", "portal_instances.json", "keycloak-sso.*.json", "*.ndjson"],
    },
}


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def service_tool_definition(tool_id: str) -> dict[str, Any]:
    return dict(SERVICE_TOOL_DEFINITIONS.get(_text(tool_id).lower()) or {})
