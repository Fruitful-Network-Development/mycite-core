from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import urlopen

from ...mss import decode_mss_payload
from ...services.profile_resolver import find_local_contact_card
from .cache import ExternalResourceCache
from .contact_card_catalog import PublicResourceDescriptor, parse_public_resource_catalog
from .isolate_bundle import IsolateBundle, build_isolate_bundle
from .provenance import ResourceProvenance
from .write_planner import MaterializationPlan, plan_local_materialization


class ExternalResourceResolver:
    def __init__(self, *, data_dir: Path, public_dir: Path, local_msn_id: str) -> None:
        self._data_dir = Path(data_dir)
        self._public_dir = Path(public_dir)
        self._local_msn_id = str(local_msn_id or "").strip()
        self._cache = ExternalResourceCache(self._data_dir)

    def _read_json(self, path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}

    def _load_contact_card(self, msn_id: str) -> dict[str, Any]:
        token = str(msn_id or "").strip()
        if not token:
            return {}
        local_path = find_local_contact_card(
            public_dir=self._public_dir,
            fallback_dir=None,
            msn_id=token,
            include_fnd=True,
        )
        if local_path is not None:
            return self._read_json(local_path)
        base = str(os.environ.get("MYCITE_CONTACT_BASE_URL") or "").strip().rstrip("/")
        if not base:
            return {}
        url = f"{base}/{quote(token, safe='')}.json"
        try:
            with urlopen(url, timeout=5) as response:  # nosec - controlled by env/config
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
                return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def list_public_resources(self, *, source_msn_id: str) -> list[dict[str, Any]]:
        card = self._load_contact_card(source_msn_id)
        descriptors = parse_public_resource_catalog(card, source_msn_id=source_msn_id)
        return [item.to_dict() for item in descriptors]

    def _resolve_descriptor(self, *, source_msn_id: str, resource_id: str) -> PublicResourceDescriptor | None:
        card = self._load_contact_card(source_msn_id)
        descriptors = parse_public_resource_catalog(card, source_msn_id=source_msn_id)
        for item in descriptors:
            if item.resource_id == resource_id:
                return item
        return None

    def _fetch_resource_payload(self, *, descriptor: PublicResourceDescriptor) -> dict[str, Any]:
        href = str(descriptor.href or "").strip()
        if not href:
            return {}
        if href.startswith("http://") or href.startswith("https://"):
            with urlopen(href, timeout=5) as response:  # nosec - configured endpoint
                raw = response.read()
                if href.endswith(".bin"):
                    decoded = decode_mss_payload(raw.decode("utf-8", errors="replace"))
                    return decoded if isinstance(decoded, dict) else {}
                payload = json.loads(raw.decode("utf-8", errors="replace"))
                return payload if isinstance(payload, dict) else {}
        rel = Path(href)
        if rel.is_absolute():
            path = rel
        else:
            path = self._public_dir / rel
        if path.exists() and path.is_file():
            if str(path.name).lower().endswith(".bin"):
                decoded = decode_mss_payload(path.read_bytes().decode("utf-8", errors="replace"))
                return decoded if isinstance(decoded, dict) else {}
            return self._read_json(path)
        return {}

    def fetch_and_cache_bundle(
        self,
        *,
        source_msn_id: str,
        resource_id: str,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        cached = None if force_refresh else self._cache.get(source_msn_id=source_msn_id, resource_id=resource_id)
        if cached:
            return {
                "ok": True,
                "from_cache": True,
                "bundle": cached.get("bundle") if isinstance(cached.get("bundle"), dict) else {},
                "payload": cached.get("payload") if isinstance(cached.get("payload"), dict) else {},
            }

        descriptor = self._resolve_descriptor(source_msn_id=source_msn_id, resource_id=resource_id)
        if descriptor is None:
            return {"ok": False, "error": f"unknown resource_id: {resource_id}"}
        payload = self._fetch_resource_payload(descriptor=descriptor)
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        payload_sha256 = hashlib.sha256(raw).hexdigest()
        provenance = ResourceProvenance(
            source_msn_id=source_msn_id,
            resource_id=resource_id,
            export_family=descriptor.export_family,
            wire_variant=descriptor.export_family,
            source_href=descriptor.href,
            fetched_unix_ms=int(time.time() * 1000),
            payload_sha256=payload_sha256,
            source_card_revision=str(descriptor.metadata.get("source_card_revision") or ""),
        )
        bundle: IsolateBundle = build_isolate_bundle(
            source_msn_id=source_msn_id,
            resource_id=resource_id,
            export_family=descriptor.export_family,
            wire_variant=descriptor.export_family,
            payload_sha256=payload_sha256,
            payload=payload,
            provenance=provenance,
            source_card_revision=str(descriptor.metadata.get("source_card_revision") or ""),
        )
        cached_payload = {"bundle": bundle.to_dict(), "payload": payload}
        self._cache.put(source_msn_id=source_msn_id, resource_id=resource_id, payload=cached_payload)
        return {"ok": True, "from_cache": False, "bundle": bundle.to_dict(), "payload": payload}

    def preview_required_closure(self, *, source_msn_id: str, resource_id: str, target_refs: list[str]) -> dict[str, Any]:
        fetched = self.fetch_and_cache_bundle(source_msn_id=source_msn_id, resource_id=resource_id, force_refresh=False)
        if not fetched.get("ok"):
            return {"ok": False, "error": fetched.get("error", "unable to fetch bundle")}
        bundle = fetched.get("bundle") if isinstance(fetched.get("bundle"), dict) else {}
        available = {
            str(item.get("canonical_ref") or "").strip()
            for item in bundle.get("isolates", [])
            if isinstance(item, dict)
        }
        required = [str(item or "").strip() for item in target_refs if str(item or "").strip()]
        missing = sorted([item for item in required if item not in available])
        return {"ok": True, "required_refs": required, "available_bundle_refs": sorted(available), "missing_refs": missing}

    def plan_materialization(
        self,
        *,
        source_msn_id: str,
        resource_id: str,
        target_ref: str,
        required_refs: list[str],
        anthology_payload: dict[str, Any],
        allow_auto_create: bool,
    ) -> MaterializationPlan:
        fetched = self.fetch_and_cache_bundle(source_msn_id=source_msn_id, resource_id=resource_id, force_refresh=False)
        if not fetched.get("ok"):
            return MaterializationPlan(
                ok=False,
                target_ref=target_ref,
                required_refs=required_refs,
                existing_local_refs=[],
                missing_refs=required_refs,
                satisfiable_from_bundle_refs=[],
                auto_create_refs=[],
                ordered_writes=[],
                warnings=[],
                errors=[str(fetched.get("error") or "unable to fetch isolate bundle")],
            )
        bundle = fetched.get("bundle") if isinstance(fetched.get("bundle"), dict) else {}
        bundle_refs = [
            str(item.get("canonical_ref") or "").strip()
            for item in bundle.get("isolates", [])
            if isinstance(item, dict)
        ]
        return plan_local_materialization(
            local_msn_id=self._local_msn_id,
            anthology_payload=anthology_payload,
            target_ref=target_ref,
            required_refs=required_refs,
            bundle_refs=bundle_refs,
            allow_auto_create=allow_auto_create,
        )
