from __future__ import annotations

from dataclasses import dataclass

from _shared.portal.sandbox.local_resource_lifecycle import LocalResourceLifecycleService


@dataclass
class WorkbenchPublishService:
    local_resource_service: LocalResourceLifecycleService

    def publish_local_resource(self, *, resource_id: str, resource_name: str = "", resource_kind: str = "") -> dict:
        return self.local_resource_service.publish(
            resource_id=resource_id,
            resource_name=resource_name,
            resource_kind=resource_kind,
        )
