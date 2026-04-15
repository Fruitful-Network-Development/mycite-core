from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem.network_root_read_model import (  # noqa: E402
    rebuild_network_system_log_document,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild the canonical NETWORK system_log.json document.")
    parser.add_argument("--portal-tenant-id", required=True, help="Portal tenant id, for example fnd.")
    parser.add_argument("--portal-domain", default="", help="Portal domain for reporting.")
    parser.add_argument("--data-dir", required=True, help="Path to the instance data directory.")
    parser.add_argument("--private-dir", required=True, help="Path to the instance private directory.")
    parser.add_argument(
        "--output",
        default="",
        help="Optional output path. Defaults to <data-dir>/system/system_log.json.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip writing a timestamped backup of the existing output file.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    data_dir = Path(args.data_dir)
    output_path = Path(args.output) if args.output else data_dir / "system" / "system_log.json"
    rebuilt = rebuild_network_system_log_document(
        data_dir=data_dir,
        private_dir=Path(args.private_dir),
        portal_tenant_id=args.portal_tenant_id,
        portal_domain=args.portal_domain,
    )
    document = rebuilt["system_log_document"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not args.no_backup:
        stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = output_path.with_name(f"{output_path.stem}.pre_network_rebuild.{stamp}{output_path.suffix}")
        backup_path.write_text(output_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Backup written: {backup_path}")
    output_path.write_text(json.dumps(document, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"Wrote canonical system log: {output_path}")
    print(f"Record count: {rebuilt['record_count']}")
    print(f"Contract count: {rebuilt['contract_count']}")
    for warning in rebuilt.get("warnings") or []:
        print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
