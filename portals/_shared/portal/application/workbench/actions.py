from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from _shared.portal.data_engine.resource_registry import remove_inherited_source
from _shared.portal.sandbox.local_resource_lifecycle import LocalResourceLifecycleService


@dataclass
class WorkbenchActionService:
    data_root: Path
    local_resource_service: LocalResourceLifecycleService
    inherited_subscription_service_factory: Callable[[], Any] | None = None

    def create_local_resource(self, *, resource_kind: str, resource_name: str, seed_payload: dict[str, Any]) -> dict[str, Any]:
        return self.local_resource_service.create(
            resource_kind=resource_kind,
            resource_name=resource_name,
            seed_payload=seed_payload,
        )

    def stage_sandbox_resource(self, *, resource_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.local_resource_service.stage(resource_id=resource_id, payload=payload)

    def save_sandbox_resource(self, *, resource_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.local_resource_service.update(resource_id=resource_id, payload=payload)

    def compile_sandbox_resource(self, *, resource_id: str) -> dict[str, Any]:
        return self.local_resource_service.compile(resource_id=resource_id)

    def refresh_inherited_resource(self, *, contract_id: str, resource_id: str, force_refresh: bool = True) -> dict[str, Any]:
        service = self._require_inherited_service()
        payload = service.refresh_resource(
            contract_id=contract_id,
            resource_id=resource_id,
            force_refresh=force_refresh,
        )
        payload["schema"] = "mycite.portal.references.refresh.v2"
        return payload

    def refresh_inherited_source(self, *, source_msn_id: str, force_refresh: bool = True) -> dict[str, Any]:
        service = self._require_inherited_service()
        payload = service.refresh_source(source_msn_id=source_msn_id, force_refresh=force_refresh)
        payload["schema"] = "mycite.portal.references.refresh_source.v2"
        return payload

    def disconnect_inherited_source(self, *, source_msn_id: str) -> dict[str, Any]:
        payload = remove_inherited_source(self.data_root, source_msn_id=source_msn_id)
        payload["ok"] = True
        payload["schema"] = "mycite.portal.references.disconnect_source.v2"
        if self.inherited_subscription_service_factory is not None:
            sync_payload = self._require_inherited_service().disconnect_source(source_msn_id=source_msn_id)
            payload["reference_exchange_sync"] = sync_payload
            payload["contract_sync"] = sync_payload
        return payload

    def _require_inherited_service(self):
        if self.inherited_subscription_service_factory is None:
            raise RuntimeError("external resource resolver is unavailable")
        return self.inherited_subscription_service_factory()
