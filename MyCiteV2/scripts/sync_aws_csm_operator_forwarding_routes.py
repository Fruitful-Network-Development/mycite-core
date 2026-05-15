"""Reconcile FORWARD_TO_MAP_JSON on the ses-forwarder lambda.

Reads every operator profile under ``<private-dir>/utilities/tools/aws-csm/``,
calls
:meth:`MyCiteV2.packages.adapters.event_transport.aws_csm_onboarding_cloud.AwsEc2RoleOnboardingCloudAdapter.sync_operator_forwarding_routes`,
and prints the structured result. Idempotent: re-running with no profile
changes is a no-op.

Usage::

    python -m MyCiteV2.scripts.sync_aws_csm_operator_forwarding_routes \
        --private-dir /srv/mycite-state/instances/fnd/private \
        [--dry-run]

In ``--dry-run`` mode no AWS write occurs; the script reports the
desired-vs-actual route diff and any rule wiring that would be added.

Backfill use case: after first deploy of the operator-forwarding sync
seam, run once without ``--dry-run`` to populate the route map for every
profile already in ``receive_pending`` / ``receive_configured`` /
``receive_operational`` state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.event_transport.aws_csm_onboarding_cloud import (
    _FORWARDER_LAMBDA_NAME,
    _FORWARDER_ROUTE_MAP_ENV_KEY,
    AwsEc2RoleOnboardingCloudAdapter,
)
from MyCiteV2.packages.adapters.filesystem.aws_csm_tool_profile_store import (
    FilesystemAwsCsmToolProfileStore,
)

DEFAULT_PRIVATE_DIR = Path("/srv/mycite-state/instances/fnd/private")


def _load_profiles(private_dir: Path) -> list[dict]:
    tool_root = private_dir / "utilities" / "tools" / "aws-csm"
    store = FilesystemAwsCsmToolProfileStore(tool_root)
    return list(store.list_profiles(tenant_scope_id=None) or [])


def _desired_routes(profiles: list[dict]) -> dict[str, str]:
    return AwsEc2RoleOnboardingCloudAdapter._operator_forwarding_routes_from_profiles(
        profiles=profiles,
    )


def _current_routes(adapter: AwsEc2RoleOnboardingCloudAdapter) -> dict[str, str]:
    client = adapter._client("lambda", region="us-east-1")
    config = client.get_function_configuration(FunctionName=_FORWARDER_LAMBDA_NAME)
    env = (config.get("Environment") or {}).get("Variables") or {}
    raw = env.get(_FORWARDER_ROUTE_MAP_ENV_KEY) or "{}"
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--private-dir",
        type=Path,
        default=DEFAULT_PRIVATE_DIR,
        help=f"Portal instance private dir (default: {DEFAULT_PRIVATE_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and print the desired-vs-actual diff without mutating AWS.",
    )
    args = parser.parse_args(argv)

    if not args.private_dir.exists():
        raise SystemExit(f"private dir not found: {args.private_dir}")

    profiles = _load_profiles(args.private_dir)
    desired = _desired_routes(profiles)
    print(f"Loaded {len(profiles)} operator profiles from {args.private_dir}")
    print(f"Desired route_count: {len(desired)}")
    for recipient, destination in sorted(desired.items()):
        print(f"  {recipient} -> {destination}")
    print()

    adapter = AwsEc2RoleOnboardingCloudAdapter()
    if args.dry_run:
        try:
            current = _current_routes(adapter)
        except Exception as exc:
            print(f"failed to read current lambda env: {exc}")
            return 1
        added = sorted(set(desired) - set(current))
        removed = sorted(set(current) - set(desired))
        unchanged = sorted(set(desired) & set(current))
        print(f"Current route_count: {len(current)}")
        print(f"Diff: +{len(added)} new, -{len(removed)} removed, ={len(unchanged)} unchanged")
        for recipient in added:
            print(f"  + {recipient} -> {desired[recipient]}")
        for recipient in removed:
            print(f"  - {recipient}  (was -> {current[recipient]})")
        return 0

    result = adapter.sync_operator_forwarding_routes(profiles=profiles)
    print("=== sync result ===")
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
