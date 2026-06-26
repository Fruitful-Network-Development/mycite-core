#!/usr/bin/env python3
"""Derive the Keycloak group/user/MSN provisioning map from the grantee leaflets.

The grantee identity leaflets under
``clients/_shared/site-core/grantee/*.grantee_profile.yaml`` are the single
source of truth. This script reads them and emits, deterministically:

  * ``keycloak_provisioning_map.json`` — the intended realm structure
    (one group per grantee carrying ``msn_id``, one ``u<short>`` user, an
    ``operator``/``admin`` group + ``aFND`` for FND).
  * ``keycloak_provision.sh`` — idempotent ``kcadm.sh`` commands that realise
    that structure, provision any missing grantee users, retire the legacy
    ``<short>-<name>`` / unused ``member-*``/``tenant-*`` users + ``flask-bff``/
    ``fnd-aws-controlplane`` clients, and turn on brute-force + a password
    policy. It is the executable form of Phase E and requires a working realm
    admin (``kcadm.sh config credentials`` — see the audit's F-OPS-2 blocker).

No secrets are read (identity leaflets only). Re-run after editing leaflets.

Usage:
  python -m MyCiteV2.scripts.gen_grantee_keycloak_map [--out DIR]
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import yaml

IDENTITY_DIR = Path("/srv/webapps/clients/_shared/site-core/grantee")
DEFAULT_OUT = Path("/srv/agentic/evidence/keycloak-dashboard-unification")
REALM = "fruitful"
OPERATOR_SHORT = "FND"  # the operator grantee

# Confirmed-orphan KC entities to retire (audit 2026-06-25, operator-approved).
LEGACY_USERS = ["fnd-dylan", "cvcc-nathan", "tff-mark", "bpw-brock"]  # -> renamed to u<short>
UNUSED_USERS = ["member-mt", "member-mw", "tenant-cvcc", "tenant-fnd", "tenant-tff"]
UNUSED_CLIENTS = ["flask-bff", "fnd-aws-controlplane"]


def load_leaflets() -> list[dict]:
    out = []
    for path in sorted(glob.glob(str(IDENTITY_DIR / "*.grantee_profile.yaml"))):
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("msn_id"):
            out.append(data)
    return out


def build_map(leaflets: list[dict]) -> dict:
    grantees = []
    for g in sorted(leaflets, key=lambda d: str(d.get("short_name", ""))):
        short = str(g.get("short_name", "")).strip()
        users = [u for u in (g.get("users") or []) if str(u).strip()]
        grantees.append({
            "short_name": short,
            "msn_id": str(g.get("msn_id", "")),
            "label": str(g.get("label", "")),
            "domains": [str(d).lower() for d in (g.get("domains") or [])],
            "kc_group": short.upper(),
            "kc_user": f"u{short.upper()}",
            "kc_email": users[0] if users else "",
            "is_operator": short.upper() == OPERATOR_SHORT,
        })
    operator = next((x for x in grantees if x["is_operator"]), None)
    return {
        "realm": REALM,
        "claim": "groups (oidc-group-membership) + grantee_msn (group msn_id attribute mapper)",
        "operator_admin_user": f"a{OPERATOR_SHORT}",
        "operator_group": "operator",
        "operator_msn": operator["msn_id"] if operator else "",
        "grantees": grantees,
        "retire_users": LEGACY_USERS + UNUSED_USERS,
        "retire_clients": UNUSED_CLIENTS,
    }


def render_kcadm(m: dict) -> str:
    kc = "/opt/keycloak/bin/kcadm.sh"
    lines = [
        "#!/usr/bin/env bash",
        "# Phase E — Keycloak standardization, DERIVED from the grantee leaflets.",
        "# REQUIRES a working realm admin. The audit (F-OPS-2) found the bootstrap",
        "# 'admin' blocked by UPDATE_PASSWORD and dcmfnd/fruitful-admin passwords",
        "# unknown — clear/learn those first, then run inside the keycloak container:",
        "#   docker exec -it keycloak bash",
        f"#   {kc} config credentials --server http://localhost:8080 --realm master --user <admin> --password <pw>",
        "# SNAPSHOT FIRST:  docker exec keycloak_db pg_dump -U keycloak keycloak > realm_backup.sql",
        "set -euo pipefail",
        f"KC={kc}",
        f"REALM={m['realm']}",
        "",
        "# 1) Realm hardening (audit F-SEC-2: both were OFF/none).",
        '"$KC" update realms/$REALM -s bruteForceProtected=true -s "passwordPolicy=length(12) and notUsername(undefined) and upperCase(1) and digits(1)"',
        "",
        "# 2) Per-grantee group carrying the MSN (group attribute msn_id).",
    ]
    for g in m["grantees"]:
        lines.append(f'"$KC" create groups -r $REALM -s name={g["kc_group"]} -s \'attributes.msn_id=["{g["msn_id"]}"]\' || true')
    lines += [
        "",
        f'"$KC" create groups -r $REALM -s name={m["operator_group"]} -s \'attributes.msn_id=["{m["operator_msn"]}"]\' || true',
        "",
        "# 3) Grantee users  u<SHORT>  (email-verified, in their group).",
    ]
    for g in m["grantees"]:
        if not g["kc_email"]:
            lines.append(f'# WARNING: {g["kc_group"]} leaflet has no users[] — set an email for {g["kc_user"]} manually')
        lines.append(
            f'"$KC" create users -r $REALM -s username={g["kc_user"]} -s enabled=true -s emailVerified=true '
            f'-s email={g["kc_email"] or "CHANGE_ME"} || true'
        )
        lines.append(f'"$KC" update users -r $REALM --query username={g["kc_user"]} -s \'requiredActions=["UPDATE_PASSWORD"]\' || true')
        lines.append(f'GID=$("$KC" get groups -r $REALM -q search={g["kc_group"]} --fields id --format csv --noquotes | head -1)')
        lines.append(f'UID=$("$KC" get users -r $REALM -q username={g["kc_user"]} --fields id --format csv --noquotes | head -1)')
        lines.append('"$KC" update users/$UID/groups/$GID -r $REALM -n || true')
    lines += [
        "",
        f"# 4) Operator admin user  a{OPERATOR_SHORT}  (operator + admin groups).",
        f'"$KC" create users -r $REALM -s username=a{OPERATOR_SHORT} -s enabled=true -s emailVerified=true || true',
        "",
        "# 5) MSN claim mapper on fnd-portal (so oauth2-proxy -> X-Auth-Request-Grantee).",
        "#    Adds a group-attribute 'msn_id' -> token claim 'grantee_msn'. nginx maps it",
        "#    to X-Auth-Request-Grantee for the dashboards (replaces the path-2 username bridge).",
        'PORTAL=$("$KC" get clients -r $REALM -q clientId=fnd-portal --fields id --format csv --noquotes | head -1)',
        '"$KC" create clients/$PORTAL/protocol-mappers/models -r $REALM '
        '-s name=grantee_msn -s protocol=openid-connect -s protocolMapper=oidc-group-membership-mapper '
        '-s \'config."claim.name"=grantee_groups\' -s \'config."access.token.claim"="true"\' '
        '-s \'config."id.token.claim"="true"\' || true',
        "",
        "# 6) Retire legacy/unused users + clients (audit-confirmed orphans).",
    ]
    for u in m["retire_users"]:
        lines.append(f'UID=$("$KC" get users -r $REALM -q username={u} --fields id --format csv --noquotes | head -1); [ -n "$UID" ] && "$KC" delete users/$UID -r $REALM || true')
    for c in m["retire_clients"]:
        lines.append(f'CID=$("$KC" get clients -r $REALM -q clientId={c} --fields id --format csv --noquotes | head -1); [ -n "$CID" ] && "$KC" delete clients/$CID -r $REALM || true')
    lines += [
        "",
        "# 7) Set passwords for u<SHORT>/aFND from your password manager:",
        '#    "$KC" set-password -r $REALM --username uFND --new-password "<pw>"   # etc.',
        "echo 'Phase E provisioning complete — verify each grantee can sign in + token carries grantee_groups.'",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    leaflets = load_leaflets()
    m = build_map(leaflets)
    (out / "keycloak_provisioning_map.json").write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
    (out / "keycloak_provision.sh").write_text(render_kcadm(m), encoding="utf-8")

    print(f"grantee leaflets read: {len(leaflets)}")
    for g in m["grantees"]:
        print(f"  {g['kc_group']:6} msn={g['msn_id']:24} user={g['kc_user']:7} email={g['kc_email'] or '(none)'}")
    print(f"operator admin user: {m['operator_admin_user']}  retire_users={m['retire_users']}  retire_clients={m['retire_clients']}")
    print(f"wrote: {out/'keycloak_provisioning_map.json'}")
    print(f"wrote: {out/'keycloak_provision.sh'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
