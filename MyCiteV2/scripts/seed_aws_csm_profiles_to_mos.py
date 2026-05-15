"""Migrate every AWS-CSM operator profile + domain record into MOS.

Reads ``<private>/utilities/tools/aws-csm/aws-csm.*.json`` (operator
profiles) and ``aws-csm-domain.*.json`` (domain records), writes each
as a datum document in the ``fnd_csm`` sandbox via
:class:`MosDatumAwsCsmProfileAdapter`.

Idempotent: re-running with no profile changes is a no-op (each
profile's version_hash only advances when its payload differs).

Usage::

    python -m MyCiteV2.scripts.seed_aws_csm_profiles_to_mos \
        --private-dir /srv/mycite-state/instances/fnd/private \
        [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql.aws_csm_profile_registry import (
    MosDatumAwsCsmProfileAdapter,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument(
        "--authority-db",
        type=Path,
        default=Path("/srv/mycite-state/instances/fnd/private/mos_authority.sqlite3"),
    )
    parser.add_argument("--tenant-id", default="fnd")
    parser.add_argument("--msn-id", default="3-2-3-17-77-1-6-4-1-4")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    tool_root = args.private_dir / "utilities" / "tools" / "aws-csm"
    if not tool_root.exists():
        raise SystemExit(f"aws-csm dir not found: {tool_root}")

    profile_paths = sorted(tool_root.glob("aws-csm.*.json"))
    domain_paths = sorted(tool_root.glob("aws-csm-domain.*.json"))
    print(f"Found {len(profile_paths)} operator profiles + {len(domain_paths)} domain records")

    if args.dry_run:
        for p in profile_paths:
            print(f"  [dry-run] profile {p.name}")
        for p in domain_paths:
            print(f"  [dry-run] domain  {p.name}")
        return 0

    adapter = MosDatumAwsCsmProfileAdapter(
        authority_db_file=args.authority_db,
        tenant_id=args.tenant_id,
        msn_id=args.msn_id,
    )
    profile_count = 0
    for path in profile_paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"  SKIP {path.name}: {exc}")
            continue
        profile_id = str((payload.get("identity") or {}).get("profile_id") or "").strip()
        if not profile_id:
            print(f"  SKIP {path.name}: no identity.profile_id")
            continue
        adapter.create_profile(profile_id=profile_id, payload=payload)
        profile_count += 1
        print(f"  profile {profile_id}")
    domain_count = 0
    for path in domain_paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"  SKIP {path.name}: {exc}")
            continue
        tenant_id = str((payload.get("identity") or {}).get("tenant_id") or "").strip()
        if not tenant_id:
            print(f"  SKIP {path.name}: no identity.tenant_id")
            continue
        adapter.save_domain(tenant_id=tenant_id, payload=payload)
        domain_count += 1
        print(f"  domain  {tenant_id}")

    print(f"\nSeeded: {profile_count} profiles + {domain_count} domains")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
