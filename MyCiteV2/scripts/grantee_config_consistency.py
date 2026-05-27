"""Grantee config-consistency linter (stack operating contract: SSOT + drift-lint).

The grantee profiles (``<private>/utilities/tools/fnd-csm/grantee.*.json``) are the
domain registry of record. Every dependent per-domain config store must be
consistent with them. This linter DERIVES the domain set from the grantee profiles
(self-extending — a new grantee is covered with no edit here) and reports, per
grantee, whether each dependent config is present, so a gap is a VISIBLE lint
finding instead of a runtime 404 (the failure mode behind the contact-form outage).

Gap classes:
  REQUIRED          — breaks a surface regardless of operator intent (e.g. no
                      ``aws_ses.identity`` => the grantee can send no mail at all).
  OPERATOR_DECISION — depends on whether the grantee offers that surface (e.g. a
                      newsletter-admin profile; a contact ``forward_to_email``).
                      Surfaced so the operator fills a validated field or confirms N/A.

A grantee's FIRST domain is treated as primary; the rest are aliases (which
legitimately have no standalone configs).

Usage:
    python -m MyCiteV2.scripts.grantee_config_consistency \\
        --private-dir /srv/webapps/mycite/fnd/private [--strict]

``--strict`` exits non-zero when any REQUIRED gap is present (for CI / deploy gating).
Without it the linter is report-only (exit 0) — OPERATOR_DECISION gaps are warnings.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


def _newsletter_admin_path(private_dir: Path, domain: str) -> Path:
    return (
        private_dir
        / "utilities" / "tools" / "newsletter-admin"
        / f"newsletter-admin.{domain}.json"
    )


def check_grantee(private_dir: Path, grantee: dict[str, Any]) -> dict[str, Any]:
    """Return {primary, aliases, ok: bool, gaps: [(class, field, detail)]}."""
    domains = [str(d).strip().lower() for d in (grantee.get("domains") or []) if str(d).strip()]
    primary = domains[0] if domains else ""
    aliases = domains[1:]
    gaps: list[tuple[str, str, str]] = []

    aws = grantee.get("aws_ses") if isinstance(grantee.get("aws_ses"), dict) else {}
    if not str(aws.get("identity") or "").strip():
        gaps.append(("REQUIRED", "aws_ses.identity", "grantee can send NO mail (newsletter/connect/receipts)"))

    connect = grantee.get("connect") if isinstance(grantee.get("connect"), dict) else {}
    if not str(connect.get("forward_to_email") or "").strip():
        gaps.append(("OPERATOR_DECISION", "connect.forward_to_email",
                     "contact-form submissions persist but are never emailed to an operator"))

    if primary and not _newsletter_admin_path(private_dir, primary).is_file():
        gaps.append(("OPERATOR_DECISION", "newsletter-admin profile",
                     f"public newsletter signup 404s for {primary} (no newsletter-admin.{primary}.json)"))

    return {"primary": primary, "aliases": aliases, "gaps": gaps, "ok": not gaps}


def run(private_dir: Path) -> dict[str, Any]:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from MyCiteV2.instances._shared.runtime.operational_store import load_grantee_profiles

    grantees = load_grantee_profiles(private_dir)
    results = [check_grantee(private_dir, g) for g in grantees]
    required = sum(1 for r in results for (cls, _, _) in r["gaps"] if cls == "REQUIRED")
    operator = sum(1 for r in results for (cls, _, _) in r["gaps"] if cls == "OPERATOR_DECISION")
    return {"grantees": len(results), "results": results, "required_gaps": required, "operator_gaps": operator}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--private-dir", required=True, type=Path, help="Instance private dir (holds utilities/tools/...).")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on any REQUIRED gap.")
    args = parser.parse_args(argv)

    report = run(args.private_dir)
    print(f"grantee config consistency — {report['grantees']} grantee(s)\n")
    for r in sorted(report["results"], key=lambda r: r["primary"]):
        alias_note = f"  (aliases: {', '.join(r['aliases'])})" if r["aliases"] else ""
        if r["ok"]:
            print(f"  OK   {r['primary']}{alias_note}")
        else:
            print(f"  GAP  {r['primary']}{alias_note}")
            for cls, field, detail in r["gaps"]:
                print(f"         [{cls}] {field} — {detail}")
    print(
        f"\nsummary: {report['required_gaps']} REQUIRED gap(s), "
        f"{report['operator_gaps']} OPERATOR_DECISION gap(s)"
    )
    if report["operator_gaps"]:
        print("OPERATOR_DECISION gaps are fillable validated fields (or confirm N/A) — see the operator checklist.")
    if args.strict and report["required_gaps"]:
        print("STRICT: REQUIRED gap(s) present — failing.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
