from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.filesystem import FilesystemAuditLogAdapter
from MyCiteV2.packages.modules.cross_domain.local_audit import LocalAuditService
from MyCiteV2.packages.state_machine.hanus_shell import ShellAction, ShellState, reduce_shell_action


def run_shell_action_to_local_audit(
    shell_action_payload: dict[str, Any],
    *,
    storage_file: str | Path,
) -> dict[str, Any]:
    action = ShellAction.from_dict(shell_action_payload)
    shell_result = reduce_shell_action(ShellState(), action)

    audit_log_adapter = FilesystemAuditLogAdapter(storage_file)
    local_audit_service = LocalAuditService(audit_log_adapter)

    append_receipt = local_audit_service.append_record(
        {
            "event_type": "shell.transition.accepted",
            "focus_subject": shell_result.focus_subject,
            "shell_verb": shell_result.shell_verb,
            "details": {},
        }
    )
    stored_record = local_audit_service.read_record(append_receipt.record_id)
    if stored_record is None:
        raise RuntimeError("runtime read-back failed for appended local audit record")

    return {
        "normalized_subject": shell_result.focus_subject,
        "normalized_shell_verb": shell_result.shell_verb,
        "normalized_shell_state": shell_result.shell_state.to_dict(),
        "persisted_audit_identifier": stored_record.record_id,
        "persisted_audit_timestamp": stored_record.recorded_at_unix_ms,
    }
