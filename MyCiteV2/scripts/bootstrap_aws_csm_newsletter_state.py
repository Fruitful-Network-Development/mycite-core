from __future__ import annotations

import argparse
import json
from pathlib import Path
import secrets
import shutil
from typing import Any

from MyCiteV2.packages.adapters.event_transport import AwsEc2RoleNewsletterCloudAdapter
from MyCiteV2.packages.adapters.filesystem import FilesystemAwsCsmNewsletterStateAdapter
from MyCiteV2.packages.modules.cross_domain.aws_csm_newsletter import (
    AWS_CSM_NEWSLETTER_PROFILE_SCHEMA,
    AwsCsmNewsletterService,
)

RUNTIME_SECRETS_SCHEMA = "mycite.service_tool.aws_csm.newsletter_runtime_secrets.v1"


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalized_domain(value: object) -> str:
    token = _as_text(value).lower()
    if token.startswith("www."):
        token = token[4:]
    return token


def _optional_email(value: object) -> str:
    token = _as_text(value).lower()
    if not token or token.count("@") != 1 or any(ch.isspace() for ch in token):
        return ""
    local_part, domain_part = token.split("@", 1)
    if not local_part or not domain_part or "." not in domain_part:
        return ""
    return token


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _dispatcher_callback_url(*, domain: str, tenant_id: str) -> str:
    return f"https://{domain}/__{tenant_id}/newsletter/dispatch-result"


def _inbound_callback_url(*, domain: str, tenant_id: str) -> str:
    return f"https://{domain}/__{tenant_id}/newsletter/inbound-capture"


def _newsletter_root(private_dir: Path) -> Path:
    return private_dir / "utilities" / "tools" / "aws-csm" / "newsletter"


def _legacy_root(private_dir: Path) -> Path:
    return private_dir / "utilities" / "tools" / "newsletter-admin"


def _runtime_secrets_path(private_dir: Path) -> Path:
    return _newsletter_root(private_dir) / "runtime_secrets.json"


def _canonical_profile_payload(
    *,
    domain: str,
    tenant_id: str,
    existing: dict[str, Any],
    legacy: dict[str, Any],
) -> dict[str, Any]:
    token = _normalized_domain(domain)
    callback_url = _dispatcher_callback_url(domain=token, tenant_id=tenant_id)
    inbound_url = _inbound_callback_url(domain=token, tenant_id=tenant_id)
    payload = dict(existing if _as_text(existing.get("schema")) == AWS_CSM_NEWSLETTER_PROFILE_SCHEMA else {})
    payload["schema"] = AWS_CSM_NEWSLETTER_PROFILE_SCHEMA
    payload["domain"] = token
    payload["list_address"] = f"news@{token}"
    payload["sender_address"] = f"news@{token}"
    payload["selected_author_profile_id"] = _as_text(
        payload.get("selected_author_profile_id")
        or legacy.get("selected_author_profile_id")
        or legacy.get("selected_sender_profile_id")
    )
    payload["selected_author_address"] = _optional_email(
        payload.get("selected_author_address")
        or legacy.get("selected_author_address")
        or legacy.get("selected_sender_address")
    )
    payload["delivery_mode"] = _as_text(payload.get("delivery_mode") or legacy.get("delivery_mode")) or "inbound-mail-workflow"
    payload["aws_region"] = _as_text(payload.get("aws_region") or legacy.get("aws_region")) or "us-east-1"
    payload["dispatch_queue_url"] = _as_text(payload.get("dispatch_queue_url") or legacy.get("dispatch_queue_url"))
    payload["dispatch_queue_arn"] = _as_text(payload.get("dispatch_queue_arn") or legacy.get("dispatch_queue_arn"))
    payload["dispatcher_lambda_name"] = _as_text(payload.get("dispatcher_lambda_name") or legacy.get("dispatcher_lambda_name")) or "newsletter-dispatcher"
    payload["inbound_processor_lambda_name"] = _as_text(payload.get("inbound_processor_lambda_name")) or "newsletter-inbound-capture"
    payload["callback_url"] = _as_text(payload.get("callback_url") or legacy.get("dispatcher_callback_url")) or callback_url
    payload["inbound_callback_url"] = _as_text(payload.get("inbound_callback_url")) or inbound_url
    payload["unsubscribe_secret_name"] = _as_text(payload.get("unsubscribe_secret_name")) or f"aws-cms/newsletter/unsubscribe-signing/{tenant_id}"
    payload["dispatch_callback_secret_name"] = _as_text(payload.get("dispatch_callback_secret_name")) or f"aws-cms/newsletter/dispatch-callback/{tenant_id}"
    payload["inbound_callback_secret_name"] = _as_text(payload.get("inbound_callback_secret_name")) or f"aws-cms/newsletter/inbound-capture/{tenant_id}"
    for key in (
        "last_inbound_message_id",
        "last_inbound_status",
        "last_inbound_checked_at",
        "last_inbound_processed_at",
        "last_inbound_subject",
        "last_inbound_sender",
        "last_inbound_recipient",
        "last_inbound_error",
        "last_inbound_s3_uri",
        "last_dispatch_id",
        "updated_at",
    ):
        payload[key] = _as_text(payload.get(key) or legacy.get(key))
    return payload


def _merge_runtime_secrets(private_dir: Path) -> dict[str, Any]:
    canonical_path = _runtime_secrets_path(private_dir)
    legacy_path = _legacy_root(private_dir) / "runtime_secrets.json"
    canonical = _read_json(canonical_path)
    legacy = _read_json(legacy_path)
    merged = {
        "schema": RUNTIME_SECRETS_SCHEMA,
        "signing_secret": _as_text(canonical.get("signing_secret") or legacy.get("signing_secret")) or secrets.token_urlsafe(32),
        "dispatch_secret": _as_text(canonical.get("dispatch_secret") or legacy.get("dispatch_secret")) or secrets.token_urlsafe(32),
        "inbound_secret": _as_text(canonical.get("inbound_secret")) or secrets.token_urlsafe(32),
    }
    _write_json(canonical_path, merged)
    return merged


def _legacy_domains(private_dir: Path) -> dict[str, dict[str, Any]]:
    root = _legacy_root(private_dir)
    out: dict[str, dict[str, Any]] = {}
    if not root.exists():
        return out
    for path in sorted(root.glob("newsletter-admin.*.json")):
        if path.name == "runtime_secrets.json":
            continue
        payload = _read_json(path)
        domain = _normalized_domain(payload.get("domain") or path.name.removeprefix("newsletter-admin.").removesuffix(".json"))
        if domain:
            out[domain] = payload
    return out


def run(*, private_dir: Path, tenant_id: str, prune_legacy_root: bool) -> dict[str, Any]:
    tenant_token = _as_text(tenant_id).lower() or "fnd"
    state = FilesystemAwsCsmNewsletterStateAdapter(private_dir)
    legacy_profiles = _legacy_domains(private_dir)
    runtime_secrets = _merge_runtime_secrets(private_dir)

    for domain, legacy_profile in legacy_profiles.items():
        existing = state.load_profile(domain=domain)
        merged = _canonical_profile_payload(
            domain=domain,
            tenant_id=tenant_token,
            existing=existing,
            legacy=legacy_profile,
        )
        state.save_profile(domain=domain, payload=merged)

    cloud = AwsEc2RoleNewsletterCloudAdapter()
    service = AwsCsmNewsletterService(state, cloud, tenant_id=tenant_token)
    domains = sorted(set(state.list_newsletter_domains()) | set(legacy_profiles.keys()))
    domain_states: list[dict[str, Any]] = []
    for domain in domains:
        domain_states.append(
            service.resolve_domain_state(
                domain=domain,
                dispatcher_callback_url=_dispatcher_callback_url(domain=domain, tenant_id=tenant_token),
                inbound_callback_url=_inbound_callback_url(domain=domain, tenant_id=tenant_token),
            )
        )

    legacy_root = _legacy_root(private_dir)
    if prune_legacy_root and legacy_root.exists():
        shutil.rmtree(legacy_root)

    return {
        "tenant_id": tenant_token,
        "private_dir": str(private_dir),
        "runtime_secrets_path": str(_runtime_secrets_path(private_dir)),
        "runtime_secrets_keys": sorted(key for key in runtime_secrets.keys() if key != "schema"),
        "domains": [
            {
                "domain": state_payload.get("domain"),
                "contact_count": state_payload.get("contact_count"),
                "warnings": list(state_payload.get("warnings") or []),
            }
            for state_payload in domain_states
        ],
        "legacy_root_pruned": bool(prune_legacy_root and not legacy_root.exists()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap canonical AWS-CSM newsletter state and retire newsletter-admin.")
    parser.add_argument(
        "--private-dir",
        default="/srv/mycite-state/instances/fnd/private",
        help="Portal private state root.",
    )
    parser.add_argument(
        "--tenant-id",
        default="fnd",
        help="Tenant token used in canonical callback routes and secret names.",
    )
    parser.add_argument(
        "--prune-legacy-root",
        action="store_true",
        help="Delete private/utilities/tools/newsletter-admin after bootstrap succeeds.",
    )
    args = parser.parse_args()
    payload = run(
        private_dir=Path(args.private_dir),
        tenant_id=args.tenant_id,
        prune_legacy_root=bool(args.prune_legacy_root),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
