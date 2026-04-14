from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.filesystem import FilesystemAuditLogAdapter
from MyCiteV2.packages.modules.cross_domain.local_audit import LocalAuditService
from MyCiteV2.packages.state_machine.portal_shell import PortalShellRequest, resolve_portal_shell_request


def run_shell_action_to_local_audit(
    shell_action_payload: dict[str, Any],
    *,
    storage_file: str | Path,
) -> dict[str, Any]:
    normalized_request = PortalShellRequest.from_dict(shell_action_payload)
    shell_result = resolve_portal_shell_request(normalized_request)

    audit_log_adapter = FilesystemAuditLogAdapter(storage_file)
    local_audit_service = LocalAuditService(audit_log_adapter)

    append_receipt = local_audit_service.append_record(
        {
            "event_type": "portal.shell.request.accepted",
            "requested_surface_id": shell_result.requested_surface_id,
            "active_surface_id": shell_result.active_surface_id,
            "details": {
                "allowed": shell_result.allowed,
                "selection_status": shell_result.selection_status,
                "reason_code": shell_result.reason_code,
            },
        }
    )
    stored_record = local_audit_service.read_record(append_receipt.record_id)
    if stored_record is None:
        raise RuntimeError("runtime read-back failed for appended local audit record")

    return {
        "normalized_requested_surface_id": shell_result.requested_surface_id,
        "normalized_active_surface_id": shell_result.active_surface_id,
        "normalized_shell_state": shell_result.to_dict(),
        "persisted_audit_identifier": stored_record.record_id,
        "persisted_audit_timestamp": stored_record.recorded_at_unix_ms,
    }
