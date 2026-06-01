#!/usr/bin/env python3
"""One-shot AWS resource tagging for the tolling extension.

Tags every per-grantee AWS resource (Route53 hosted zones, SES
configuration sets, SES identities, Lambda functions, S3 buckets, EC2
instance) with the grantee's `msn_id` + `tenant` so Cost Explorer can
slice spend per grantee.

Idempotent: re-running with the same plan is a no-op.

USAGE
-----
    # Dry run — print the plan, don't call AWS.
    python3 aws_tag_grantee_resources.py --dry-run

    # Apply.
    python3 aws_tag_grantee_resources.py --apply

PREREQUISITES
-------------
- IAM role must allow `tag:TagResources` on the target resources and
  `ce:ListCostAllocationTags` + `ce:UpdateCostAllocationTagsStatus` on
  Cost Explorer (covered by the `AWSCMSCostExplorerAndSns` policy).
- Run `--apply --activate-tags` (or `--activate-tags` standalone after
  a prior tagging pass) to activate `msn_id`, `tenant`, and `shared`
  as billing cost-allocation tags. Activation is account-level and
  idempotent. Wait ~24h for Cost Explorer to backfill the dimension
  before querying.

EDITING THIS SCRIPT
-------------------
The grantee → resource mapping is hard-coded below for the initial
tagging pass. Once a new grantee onboards, add their msn_id +
short_name + resources to GRANTEE_RESOURCES. The peripheral's
`ensure_domain_*` methods will eventually auto-tag new resources on
creation, but those don't backfill the existing fleet — this script
does that.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------
# Grantee → resource mapping.
#
# Pulled from /srv/webapps/mycite/fnd/private/utilities/tools/fnd-csm/
# grantee profiles + the live AWS state (Route53 zones, SES configset,
# Lambdas, S3 bucket, EC2 instance).
#
# `shared` resources are tagged with the operator (FND) plus a
# `shared=true` tag so cost attribution puts shared infra on FND's
# plate (which is correct — FND pays for shared infra and charges
# grantees per use, not per-resource).
# ---------------------------------------------------------------------
import os as _os

from MyCiteV2.packages.peripherals.aws.cloud_adapter import AwsPeripheralCloudAdapter

# Environment-overridable so the script can target staging / other
# accounts without an edit. Defaults are FND's production account.
AWS_ACCOUNT = _os.environ.get("MYCITE_AWS_ACCOUNT", "065948377733")
SES_REGION = _os.environ.get("MYCITE_SES_REGION", "us-east-1")
EC2_INSTANCE = _os.environ.get("MYCITE_EC2_INSTANCE", "i-046f5861584b180c8")

COST_ALLOCATION_TAG_KEYS = ("msn_id", "tenant", "shared", "cost_pool")

# Cost pools enumerate how shared infrastructure should be billed across
# grantees. `cost_pool` is a tag emitted on every `shared=true` resource;
# the tolling extension's billing-rules layer chooses the per-pool split
# (absorb_fnd / by_bandwidth_share / equal).
#
# - fnd_operator: shared infra operated by FND for itself + clients.
#   Lambdas, S3 inbound bucket, EC2 host, EBS volumes, CloudWatch log
#   groups. Default rule: absorb_fnd (FND eats the cost; clients see
#   only direct attribution + a derived bandwidth share).
#
# - clients_server: reserved for a future second EC2 hosting only client
#   sites. No resources tagged into it today. When that server lands,
#   add its ARNs to the FND grantee's shared_* lists with
#   `shared_cost_pool = COST_POOL_CLIENTS_SERVER`. The tolling rule for
#   that pool defaults to `by_bandwidth_share`.
COST_POOL_FND_OPERATOR = "fnd_operator"
COST_POOL_CLIENTS_SERVER = "clients_server"

GRANTEE_RESOURCES: dict[str, dict[str, list[str] | str | bool]] = {
    # FND — the operator. Owns the shared infra.
    "3-2-3-17-77-1-6-4-1-4": {
        "tenant": "fnd",
        "label": "Fruitful Network Development",
        "route53_zones": ["Z0820667F5GC4U3JXL9V"],  # fruitfulnetworkdevelopment.com
        "ses_configuration_sets": ["fnd-default"],
        "ses_identities": ["fruitfulnetworkdevelopment.com"],
        # Shared infrastructure — tagged with FND + shared=true +
        # cost_pool=fnd_operator. Cost-attribution rule decided downstream
        # in tolling_billing_rules.json.
        "shared_cost_pool": COST_POOL_FND_OPERATOR,
        "shared_lambdas": [
            "ses-forwarder",
            "newsletter-dispatcher",
            "newsletter-inbound-capture",
        ],
        "shared_log_groups": [
            "/aws/lambda/ses-forwarder",
            "/aws/lambda/newsletter-dispatcher",
            "/aws/lambda/newsletter-inbound-capture",
        ],
        "shared_s3_buckets": ["ses-inbound-fnd-mail"],
        "shared_ec2_instances": [EC2_INSTANCE],
        # Dynamic discovery: every EBS volume in the account belongs to
        # this single-host setup. The tag-API (tag:GetResources) is
        # already granted by AWSCMSCostExplorerAndSns. When the second
        # EC2 lands, swap this for an explicit volume-id list.
        "shared_ebs_dynamic": True,
    },
    # CVCC — 501(c)(3) conservancy.
    "3-2-3-17-77-3-6-1-1-2": {
        "tenant": "cvcc",
        "label": "Cuyahoga Valley Countryside Conservancy",
        "route53_zones": [
            "Z09517872ZM94H1UQZ0MD",  # cuyahogavalleycountrysideconservancy.org
            "Z05968042395KDRPX4PLG",  # cvccboard.org
        ],
    },
    # TFF — Trapp Family Farm.
    "3-2-3-17-77-3-6-3-1-6": {
        "tenant": "tff",
        "label": "Trapp Family Farm",
        "route53_zones": ["Z07127663NGY0TH4ZZIEI"],  # trappfamilyfarm.com
    },
    # BPW — Brock's Pressure Washing.
    "3-2-3-17-77-3-6-5-1-9": {
        "tenant": "bpw",
        "label": "Brock's Pressure Washing",
        "route53_zones": ["Z06717982X5JX84P87CIY"],  # brockspressurewashing.com
    },
}

# Resources owned operationally by FND but for clients without their
# own grantee profile yet. Empty now that BPW has a profile.
FND_OPERATED_DOMAINS: dict[str, str] = {}


def _arn_for_route53_zone(zone_id: str) -> str:
    # Route53 zones use a slash-free ARN: arn:aws:route53:::hostedzone/Z...
    raw = zone_id.split("/")[-1]
    return f"arn:aws:route53:::hostedzone/{raw}"


def _arn_for_ses_configuration_set(name: str) -> str:
    return f"arn:aws:ses:{SES_REGION}:{AWS_ACCOUNT}:configuration-set/{name}"


def _arn_for_ses_identity(identity: str) -> str:
    # Domain identities are addressed by name in the identity-ARN form.
    return f"arn:aws:ses:{SES_REGION}:{AWS_ACCOUNT}:identity/{identity}"


def _arn_for_lambda(name: str) -> str:
    return f"arn:aws:lambda:{SES_REGION}:{AWS_ACCOUNT}:function:{name}"


def _arn_for_s3_bucket(name: str) -> str:
    return f"arn:aws:s3:::{name}"


def _arn_for_ec2_instance(instance_id: str) -> str:
    return f"arn:aws:ec2:{SES_REGION}:{AWS_ACCOUNT}:instance/{instance_id}"


def _arn_for_log_group(name: str) -> str:
    # CloudWatch Logs ARN form: arn:aws:logs:region:account:log-group:NAME
    return f"arn:aws:logs:{SES_REGION}:{AWS_ACCOUNT}:log-group:{name}"


def _discover_shared_ebs_volumes() -> list[str]:
    """Return ARNs of all EBS volumes in the account.

    Uses the Resource Groups Tagging API (tag:GetResources, granted by
    AWSCMSCostExplorerAndSns) so no ec2:DescribeInstances is needed.
    Single-host setup today, so every volume belongs to the FND-operator
    pool. When a second EC2 lands, replace this dynamic call with explicit
    per-server volume lists in GRANTEE_RESOURCES.
    """
    import boto3
    client = boto3.client("resourcegroupstaggingapi", region_name=SES_REGION)
    arns: list[str] = []
    token: str | None = None
    while True:
        kwargs: dict[str, object] = {"ResourceTypeFilters": ["ec2:volume"]}
        if token:
            kwargs["PaginationToken"] = token
        resp = client.get_resources(**kwargs)
        for entry in resp.get("ResourceTagMappingList", []):
            arn = entry.get("ResourceARN")
            if arn:
                arns.append(str(arn))
        token = resp.get("PaginationToken") or None
        if not token:
            break
    return arns


def build_plan() -> list[tuple[str, dict[str, str]]]:
    """Return a list of (arn, tags) pairs to apply."""
    plan: list[tuple[str, dict[str, str]]] = []
    for msn_id, cfg in GRANTEE_RESOURCES.items():
        tenant = str(cfg.get("tenant", ""))
        base_tags = {"msn_id": msn_id, "tenant": tenant}
        # Per-grantee resources
        for zone_id in cfg.get("route53_zones", []) or []:
            plan.append((_arn_for_route53_zone(str(zone_id)), dict(base_tags)))
        for cs_name in cfg.get("ses_configuration_sets", []) or []:
            plan.append((_arn_for_ses_configuration_set(str(cs_name)), dict(base_tags)))
        for ident in cfg.get("ses_identities", []) or []:
            plan.append((_arn_for_ses_identity(str(ident)), dict(base_tags)))
        # Shared resources — tag with the grantee that operates them
        # (FND today) plus `shared=true` + `cost_pool=<pool>` so the
        # tolling rules engine can split cost across grantees per-pool.
        shared_tags = {**base_tags, "shared": "true"}
        pool = cfg.get("shared_cost_pool")
        if pool:
            shared_tags["cost_pool"] = str(pool)
        for fn in cfg.get("shared_lambdas", []) or []:
            plan.append((_arn_for_lambda(str(fn)), dict(shared_tags)))
        for lg in cfg.get("shared_log_groups", []) or []:
            plan.append((_arn_for_log_group(str(lg)), dict(shared_tags)))
        for bucket in cfg.get("shared_s3_buckets", []) or []:
            plan.append((_arn_for_s3_bucket(str(bucket)), dict(shared_tags)))
        for inst in cfg.get("shared_ec2_instances", []) or []:
            plan.append((_arn_for_ec2_instance(str(inst)), dict(shared_tags)))
        if cfg.get("shared_ebs_dynamic"):
            for arn in _discover_shared_ebs_volumes():
                plan.append((arn, dict(shared_tags)))
    # FND-operated domains that don't yet have their own grantee profile.
    for zone_id, domain_name in FND_OPERATED_DOMAINS.items():
        plan.append((
            _arn_for_route53_zone(zone_id),
            {"msn_id": "3-2-3-17-77-1-6-4-1-4", "tenant": "fnd",
             "shared": "true", "operated_for": domain_name},
        ))
    return plan


def activate_cost_allocation_tags(
    adapter: AwsPeripheralCloudAdapter,
    *,
    dry_run: bool,
    keys: tuple[str, ...] = COST_ALLOCATION_TAG_KEYS,
) -> dict[str, str]:
    """Activate `keys` as cost-allocation tags in the AWS billing layer.

    Idempotent. Reads current status via `ce:ListCostAllocationTags` and
    only calls `ce:UpdateCostAllocationTagsStatus` for keys whose status
    is currently "Inactive" (i.e. tagged on resources but not yet
    activated for billing slicing). Cost Explorer is a global service
    pinned to us-east-1.

    Returns a mapping `{key: prior_status}` for the keys that were
    activated by this call. An empty dict means everything was already
    Active (or, in `--dry-run`, means activation would be a no-op).
    """
    ce = adapter._client("ce", region="us-east-1")
    statuses: dict[str, str] = {}
    paginator_token: str | None = None
    while True:
        kwargs: dict[str, object] = {"MaxResults": 100}
        if paginator_token:
            kwargs["NextToken"] = paginator_token
        resp = ce.list_cost_allocation_tags(**kwargs)
        for tag in resp.get("CostAllocationTags", []):
            statuses[str(tag.get("TagKey"))] = str(tag.get("Status"))
        paginator_token = resp.get("NextToken")
        if not paginator_token:
            break

    # AWS only allows activating keys that already appear in
    # CostAllocationTags (i.e. that have surfaced from the tagged
    # resources — up to 24h propagation lag for a brand-new key).
    # Activating an unknown key raises ValidationException, so split
    # the candidates: activate the surfaced-but-Inactive ones now,
    # report the unsurfaced ones as pending propagation.
    surfaced = [k for k in keys if k in statuses]
    not_surfaced = [k for k in keys if k not in statuses]
    to_activate = [k for k in surfaced if statuses.get(k) != "Active"]
    changed: dict[str, str] = {k: statuses.get(k, "Unknown") for k in to_activate}

    if not_surfaced:
        print("activate-tags: pending AWS propagation (re-run later): "
              + ", ".join(not_surfaced))

    if not to_activate:
        if surfaced:
            print("activate-tags: all surfaced keys already Active "
                  f"({', '.join(surfaced)})")
        return changed

    print("activate-tags: pending "
          + ", ".join(f"{k} ({statuses.get(k, 'Unknown')} -> Active)"
                      for k in to_activate))
    if dry_run:
        return changed

    ce.update_cost_allocation_tags_status(
        CostAllocationTagsStatus=[
            {"TagKey": k, "Status": "Active"} for k in to_activate
        ],
    )
    print("activate-tags: activated " + ", ".join(to_activate))
    return changed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--dry-run", action="store_true",
                     help="Print the tagging plan and exit. No AWS calls.")
    grp.add_argument("--apply", action="store_true",
                     help="Apply the tagging plan.")
    parser.add_argument("--activate-tags", action="store_true",
                        help="Also activate msn_id/tenant/shared/cost_pool as cost-"
                             "allocation tags after tagging. Idempotent. Requires "
                             "ce:UpdateCostAllocationTagsStatus on the caller.")
    args = parser.parse_args(argv)

    plan = build_plan()
    if not plan:
        print("nothing to tag", file=sys.stderr)
        # Still allow --activate-tags as a standalone follow-up after a
        # prior tagging pass.
        if args.activate_tags:
            adapter = AwsPeripheralCloudAdapter()
            activate_cost_allocation_tags(adapter, dry_run=args.dry_run)
        return 0

    if args.dry_run:
        print(f"Plan: {len(plan)} resources to tag")
        for arn, tags in plan:
            print(f"  {arn}")
            for k, v in sorted(tags.items()):
                print(f"      {k} = {v}")
        if args.activate_tags:
            adapter = AwsPeripheralCloudAdapter()
            activate_cost_allocation_tags(adapter, dry_run=True)
        return 0

    # --apply
    adapter = AwsPeripheralCloudAdapter()
    overall_ok = True
    for arn, tags in plan:
        result = adapter.tag_resource(arns=[arn], tags=tags)
        status = "ok" if result["ok"] else "FAILED"
        print(f"{status}  {arn}")
        if not result["ok"]:
            overall_ok = False
            for failed in result["failed_arns"]:
                print(
                    f"      code={failed['error_code']} msg={failed['error_message']}",
                    file=sys.stderr,
                )

    if args.activate_tags:
        activate_cost_allocation_tags(adapter, dry_run=False)

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
