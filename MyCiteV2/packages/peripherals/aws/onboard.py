"""Per-user / per-role onboarding for the alias email convention.

Two flows here:

* ``onboard_alias(...)`` — writes (or refreshes) the operator profile JSON
  for ``<local>@<domain>`` and re-syncs the ses-forwarder routing map.
  Idempotent. Pure profile-store + AWS Lambda env updates; no IAM ops.

* ``issue_smtp_credentials(...)`` — creates an IAM user scoped to a
  single SES From: address, creates an access key, derives the SES SMTP
  password, writes an operator-private packet under
  ``/srv/agentic/evidence/SMTP-Creds-<address>-<date>/`` containing the
  credentials + the user-facing Gmail Send-As walkthrough. Requires
  ``iam:CreateUser`` / ``iam:CreateAccessKey`` / ``iam:PutUserPolicy`` —
  the EC2 instance role intentionally lacks these (see srv-infra docs),
  so this runs from an operator session with broader IAM. The function
  raises a clear ``OperatorIamRequiredError`` when run without those
  perms, with the exact paste-and-run snippet to use instead.

See ``clients/_shared/site-core/docs/email_convention.md`` for the
convention this implements and the user-facing walkthrough template at
``clients/_shared/site-core/docs/email_send_as_setup_gmail.md``.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

from .smtp_creds import (
    derive_smtp_password,
    scoped_send_policy_document,
    slugify_iam_user_name,
    smtp_host_for_region,
)

# Region SES is configured in. The package-level SES_REGION (in
# cloud_adapter.py) defaults to us-east-1; this mirrors that default so
# onboard.py is self-contained.
SES_REGION_DEFAULT = "us-east-1"

# Where credentials packets land. Operator-private; never committed.
EVIDENCE_ROOT = Path("/srv/agentic/evidence")

# Template lives under the shared site-core docs so it's editable in one
# place and surfaces in the convention bundle.
WALKTHROUGH_TEMPLATE = Path(
    "/srv/webapps/clients/_shared/site-core/docs/email_send_as_setup_gmail.md"
)


class OperatorIamRequiredError(RuntimeError):
    """Raised when ``issue_smtp_credentials`` is invoked under a session
    that lacks ``iam:CreateUser`` / ``iam:CreateAccessKey`` /
    ``iam:PutUserPolicy``. Message body includes the exact snippet to run
    from a session that has those perms."""


# ---------------------------------------------------------------------------
# Profile-store helpers — write the aws-csm.<bucket>.<local>.json that the
# sync-forwarding-routes reconciler picks up. `<bucket>` is the operator's
# short tenant slug (e.g. cvccboard, cvcc, bpw, tff, fnd) and is unique
# per domain. Derived automatically from existing profiles when the domain
# is already known; must be passed explicitly for genuinely new domains.

def _derive_bucket_from_existing(store: Any, domain: str) -> str | None:
    """Return the bucket slug used by existing profiles on ``domain``, or
    None if no existing profile matches. Lets ``onboard_alias`` auto-fill
    the bucket for clients we already manage."""
    domain = (domain or "").strip().lower()
    for profile in store.list_profiles():
        ident = (profile.get("identity") or {})
        if (ident.get("domain") or "").strip().lower() != domain:
            continue
        src = profile.get("_source_path") or ""
        # aws-csm.<bucket>.<user>.json
        name = Path(src).name if src else ""
        parts = name.split(".")
        if len(parts) >= 4 and parts[0] == "aws-csm":
            return parts[1]
    return None


def _profile_path(store: Any, bucket: str, local: str) -> Path:
    return Path(store.root) / f"aws-csm.{bucket}.{local}.json"


def _profile_payload(
    *,
    grantee: str,
    domain: str,
    local: str,
    forward_to: str,
    display_name: str,
    kind: str,
) -> dict[str, Any]:
    """Build a minimal aws-csm profile JSON the existing reconciler
    accepts (``iter_profile_recipient_targets`` only looks at
    ``identity.send_as_email`` + ``identity.operator_inbox_target``).
    Kind (`user` vs `role`) is captured in the workflow block as
    metadata; the reconciler doesn't distinguish."""
    address = f"{local}@{domain}"
    profile_id = f"aws-csm.{grantee}.{local}"
    return {
        "schema": "mycite.service_tool.aws.profile.v2",
        "identity": {
            "profile_id": profile_id,
            "tenant_id": grantee,
            "domain": domain,
            "region": SES_REGION_DEFAULT,
            "mailbox_local_part": local,
            "role": kind,  # "user" | "role"
            "profile_kind": "mailbox",
            "operator_inbox_target": forward_to,
            "send_as_email": address,
            "display_name": display_name,
        },
        "workflow": {
            "lifecycle_state": "operational",
            "onboarded_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        },
    }


def onboard_alias(
    *,
    adapter,  # AwsPeripheralCloudAdapter
    store,
    kind: str,
    domain: str,
    local: str,
    forward_to: str,
    display_name: str = "",
    tenant_slug: str | None = None,
) -> dict[str, Any]:
    """Write (or refresh) the operator profile + re-sync forwarder.

    The profile filename is ``aws-csm.<tenant_slug>.<local>.json`` where
    ``tenant_slug`` is the short bucket name for that org's profiles
    (e.g. ``cvccboard`` for cvccboard.org). If not passed explicitly, we
    auto-derive it from any existing profile on the same domain; if no
    such profile exists this is a new client and the caller must supply
    one (the function raises ValueError telling them so)."""
    if kind not in ("user", "role"):
        raise ValueError("kind must be 'user' or 'role'")
    if "@" in local or "@" in domain:
        raise ValueError("local / domain must not include @")
    if tenant_slug is None:
        tenant_slug = _derive_bucket_from_existing(store, domain)
    if not tenant_slug:
        raise ValueError(
            f"no existing profile on {domain} — pass --tenant-slug for the first user on a new client "
            f"(by convention: a short org name, e.g. cvccboard for cvccboard.org)."
        )
    grantee = getattr(store, "grantee", "fnd")
    path = _profile_path(store, tenant_slug, local)
    payload = _profile_payload(
        grantee=tenant_slug, domain=domain, local=local,
        forward_to=forward_to, display_name=display_name, kind=kind,
    )
    pre_existed = path.exists()
    if pre_existed:
        # Preserve any extra operator-added keys (notifications, lifecycle
        # history, etc.) by merging the new identity over the old.
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            old = {}
        old.setdefault("identity", {}).update(payload["identity"])
        old.setdefault("workflow", {}).update(payload["workflow"])
        out = old
    else:
        out = payload
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    # Push the new route to the Lambda env.
    sync_result = adapter.sync_operator_forwarding_routes(dry_run=False)

    return {
        "ok": True,
        "address": f"{local}@{domain}",
        "forward_to": forward_to,
        "kind": kind,
        "profile_path": str(path),
        "profile_pre_existed": pre_existed,
        "route_count_after_sync": sync_result["route_count"],
        "route_changed": sync_result["route_changed"],
    }


# ---------------------------------------------------------------------------
# IAM + SMTP credentials issuance — requires broader IAM than the EC2 role.

_OPERATOR_SNIPPET = (
    "Run this from a session with iam:CreateUser / iam:CreateAccessKey / "
    "iam:PutUserPolicy (e.g. your local console with the admin profile):\n\n"
    "    aws iam create-user --user-name {user}\n"
    "    aws iam put-user-policy --user-name {user} --policy-name {policy} \\\n"
    "        --policy-document '{policy_doc}'\n"
    "    aws iam create-access-key --user-name {user}\n\n"
    "Then re-run, passing the access key id + secret via env vars:\n\n"
    "    SES_SMTP_ACCESS_KEY_ID=AKIAxxxxxx \\\n"
    "    SES_SMTP_SECRET_ACCESS_KEY=xxxxxxxxxxxx \\\n"
    "      {cli_self} issue-smtp-credentials --address {address}\n"
)


def issue_smtp_credentials(
    *,
    address: str,
    region: str = SES_REGION_DEFAULT,
    packet_dir: str | None = None,
) -> dict[str, Any]:
    """Provision IAM + SMTP credentials for ``address``; write the packet."""
    if "@" not in address:
        raise ValueError("address must be an email")
    iam_user = slugify_iam_user_name(address)
    policy_name = "SesSendOnlyAsThisAddress"
    policy_doc = scoped_send_policy_document(address)

    # If the operator already minted the IAM creds out-of-band and is
    # passing them in via env, skip the IAM API calls and go straight to
    # SMTP-password derivation + packet assembly. Lets the operator
    # re-run from any session (incl. the EC2 instance role) once the IAM
    # half is done elsewhere.
    env_key = os.environ.get("SES_SMTP_ACCESS_KEY_ID", "").strip()
    env_secret = os.environ.get("SES_SMTP_SECRET_ACCESS_KEY", "").strip()

    if env_key and env_secret:
        access_key_id, secret_access_key = env_key, env_secret
        iam_provisioned_here = False
    else:
        iam = boto3.client("iam")
        try:
            iam.create_user(UserName=iam_user)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code == "EntityAlreadyExists":
                pass  # idempotent
            elif code in ("AccessDenied", "AccessDeniedException"):
                raise OperatorIamRequiredError(
                    _OPERATOR_SNIPPET.format(
                        user=iam_user,
                        policy=policy_name,
                        policy_doc=json.dumps(policy_doc).replace("'", "'\\''"),
                        cli_self="python -m MyCiteV2.packages.peripherals.aws.cli --grantee fnd",
                        address=address,
                    )
                )
            else:
                raise
        try:
            iam.put_user_policy(
                UserName=iam_user, PolicyName=policy_name,
                PolicyDocument=json.dumps(policy_doc),
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code", "") in ("AccessDenied", "AccessDeniedException"):
                raise OperatorIamRequiredError(
                    _OPERATOR_SNIPPET.format(
                        user=iam_user, policy=policy_name,
                        policy_doc=json.dumps(policy_doc).replace("'", "'\\''"),
                        cli_self="python -m MyCiteV2.packages.peripherals.aws.cli --grantee fnd",
                        address=address,
                    )
                )
            raise
        try:
            ak = iam.create_access_key(UserName=iam_user)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code", "") in ("AccessDenied", "AccessDeniedException"):
                raise OperatorIamRequiredError(
                    _OPERATOR_SNIPPET.format(
                        user=iam_user, policy=policy_name,
                        policy_doc=json.dumps(policy_doc).replace("'", "'\\''"),
                        cli_self="python -m MyCiteV2.packages.peripherals.aws.cli --grantee fnd",
                        address=address,
                    )
                )
            raise
        access_key_id = ak["AccessKey"]["AccessKeyId"]
        secret_access_key = ak["AccessKey"]["SecretAccessKey"]
        iam_provisioned_here = True

    smtp_password = derive_smtp_password(secret_access_key, region)
    smtp_host = smtp_host_for_region(region)

    # Personalised user packet under operator-private evidence dir.
    today = _dt.date.today().isoformat()
    local, domain = address.split("@", 1)
    dest = Path(packet_dir) if packet_dir else (
        EVIDENCE_ROOT / f"SMTP-Creds-{domain}-{local}-{today}"
    )
    dest.mkdir(parents=True, exist_ok=True)

    # Render the walkthrough by substituting {{placeholders}}.
    try:
        template = WALKTHROUGH_TEMPLATE.read_text(encoding="utf-8")
    except FileNotFoundError:
        template = ""
    rendered = (
        template
        .replace("{{ADDRESS}}", address)
        .replace("{{SMTP_HOST}}", smtp_host)
        .replace("{{SMTP_PORT}}", "587")
        .replace("{{SMTP_USERNAME}}", access_key_id)
        .replace("{{SMTP_PASSWORD}}", smtp_password)
        .replace("{{DOMAIN}}", domain)
        .replace("{{LOCAL}}", local)
    )
    packet_path = dest / f"{local}_send_as_packet.md"
    packet_path.write_text(rendered, encoding="utf-8")

    # A separate machine-readable summary the operator can grep/audit.
    summary = {
        "address": address,
        "iam_user": iam_user,
        "iam_provisioned_here": iam_provisioned_here,
        "region": region,
        "smtp_host": smtp_host,
        "smtp_port": 587,
        "smtp_username": access_key_id,
        "smtp_password": smtp_password,  # only present in this in-memory return; not logged
        "packet_path": str(packet_path),
        "issued_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
    }
    return summary
