"""Operator profile JSON store for the AWS peripheral.

Reads files at
``/srv/repo/mycite-core/deployed/<grantee>/private/utilities/tools/aws-csm/aws-csm.*.json``.
That on-disk directory name (`aws-csm/`) is a legacy slot name and is
preserved — renaming the directory would break the portal's tool
discovery. The directory's *contents* are the canonical operator profile
JSONs; this store is the only authorized reader for the peripheral.

No MOS, no SQL, no caching. The caller can hold a reference to a
ProfileStore for the lifetime of a request — it does not pre-load files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ._normalize import as_text, normalized_domain


DEFAULT_GRANTEE = "fnd"
DEFAULT_PROFILE_ROOT = Path(
    "/srv/repo/mycite-core/deployed/{grantee}/private/utilities/tools/aws-csm"
)
PROFILE_GLOB = "aws-csm.*.json"
DOMAIN_GLOB = "aws-csm-domain.*.json"
SKIP_FILENAME_PARTS = ("sender-audit", "tool.")


class ProfileStore:
    def __init__(self, grantee: str = DEFAULT_GRANTEE, *, root: Path | None = None) -> None:
        if root is not None:
            self._root = Path(root)
        else:
            self._root = Path(str(DEFAULT_PROFILE_ROOT).format(grantee=grantee))

    @property
    def root(self) -> Path:
        return self._root

    def list_profiles(self) -> list[dict]:
        out: list[dict] = []
        for path in sorted(self._root.glob(PROFILE_GLOB)):
            if any(part in path.name for part in SKIP_FILENAME_PARTS):
                continue
            data = self._read_json(path)
            if data is None:
                continue
            data["_source_path"] = str(path)
            out.append(data)
        return out

    def list_domains(self) -> list[dict]:
        out: list[dict] = []
        for path in sorted(self._root.glob(DOMAIN_GLOB)):
            data = self._read_json(path)
            if data is None:
                continue
            data["_source_path"] = str(path)
            out.append(data)
        return out

    def get_domain(self, domain: str) -> dict | None:
        """Return the domain seed JSON whose identity.domain matches."""
        token = normalized_domain(domain)
        if not token:
            return None
        for record in self.list_domains():
            ident = record.get("identity") or {}
            if normalized_domain(ident.get("domain")) == token:
                return record
        return None

    def get_profile(self, profile_id: str) -> dict | None:
        target = as_text(profile_id)
        if not target:
            return None
        for profile in self.list_profiles():
            ident = profile.get("identity") or {}
            if as_text(ident.get("profile_id")) == target:
                return profile
        return None

    def load_profile(self, *, tenant_scope_id: str, profile_id: str) -> dict | None:
        """Tenant-scoped load. Returns the profile if its identity matches
        ``profile_id`` AND its tenant_id / domain / profile_id matches
        ``tenant_scope_id`` (case-insensitive on the scope only)."""
        from ._normalize import normalized_domain as _ndom
        scope = as_text(tenant_scope_id).lower()
        target = as_text(profile_id)
        if not scope or not target:
            return None
        for profile in self.list_profiles():
            ident = profile.get("identity") or {}
            if as_text(ident.get("profile_id")) != target:
                continue
            allowed = {
                as_text(ident.get("tenant_id")).lower(),
                _ndom(ident.get("domain")),
                as_text(ident.get("profile_id")).lower(),
            }
            if scope in allowed:
                return profile
        return None

    def save_profile(
        self, *, tenant_scope_id: str, profile_id: str, payload: dict
    ) -> dict:
        """Write the profile JSON back to disk. Reads previous version
        to discover the source path; falls back to the canonical
        `aws-csm.<scope>.<mailbox>.json` naming if no prior file."""
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        ident = payload.get("identity") or {}
        if as_text(ident.get("profile_id")) != as_text(profile_id):
            raise ValueError("payload identity.profile_id mismatch")
        current = self.load_profile(tenant_scope_id=tenant_scope_id, profile_id=profile_id)
        if current is not None and "_source_path" in current:
            path = Path(current["_source_path"])
        else:
            # Canonical naming: aws-csm.<tenant_scope>.<local>.json
            local = as_text(ident.get("mailbox_local_part")) or as_text(profile_id).split(".")[-1]
            path = self._root / f"aws-csm.{tenant_scope_id}.{local}.json"
        clean = {k: v for k, v in payload.items() if k != "_source_path"}
        path.write_text(json.dumps(clean, indent=2), encoding="utf-8")
        return clean

    def profiles_by_domain(self, domain: str) -> list[dict]:
        token = normalized_domain(domain)
        if not token:
            return []
        out = []
        for profile in self.list_profiles():
            ident = profile.get("identity") or {}
            if normalized_domain(ident.get("domain")) == token:
                out.append(profile)
        return out

    def domains(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for profile in self.list_profiles():
            ident = profile.get("identity") or {}
            domain = normalized_domain(ident.get("domain"))
            if domain and domain not in seen:
                seen.add(domain)
                out.append(domain)
        return out

    def _read_json(self, path: Path) -> dict | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None


def iter_profile_recipient_targets(profiles: Iterable[dict]) -> list[tuple[str, str, str]]:
    """Yield `(profile_id, send_as_email, receive_routing_target)` tuples
    for every profile that has a well-formed send_as + target pair.
    Skips profiles with missing or invalid fields (caller may surface as
    issues separately)."""
    from ._normalize import normalized_email

    out: list[tuple[str, str, str]] = []
    for profile in profiles:
        ident = profile.get("identity") or {}
        inbound = profile.get("inbound") or {}
        send_as = normalized_email(ident.get("send_as_email"))
        target = normalized_email(
            inbound.get("receive_routing_target") or ident.get("operator_inbox_target")
        )
        profile_id = as_text(ident.get("profile_id"))
        if not send_as or not target or send_as == target:
            continue
        out.append((profile_id, send_as, target))
    return out


__all__ = ["ProfileStore", "iter_profile_recipient_targets"]
