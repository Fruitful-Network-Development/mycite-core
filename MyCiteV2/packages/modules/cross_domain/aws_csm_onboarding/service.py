"""Shell-owned AWS-CSM onboarding semantics (V1 provision-class mapping, no V1 imports)."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from MyCiteV2.packages.core.datum_refs import normalize_datum_ref
from MyCiteV2.packages.ports.aws_csm_onboarding import (
    AwsCsmOnboardingCloudPort,
    AwsCsmOnboardingCommand,
    AwsCsmOnboardingOutcome,
    AwsCsmOnboardingPolicyError,
    AwsCsmOnboardingProfileStorePort,
)
from MyCiteV2.packages.ports.aws_read_only_status import AwsReadOnlyStatusRequest


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _merge_section(dst: dict[str, Any], key: str, delta: dict[str, Any] | None) -> None:
    if not delta:
        return
    base = _as_dict(dst.get(key))
    base.update(delta)
    dst[key] = base


def _deep_merge_profile(dst: dict[str, Any], fragment: dict[str, Any]) -> None:
    for key, val in fragment.items():
        if isinstance(val, dict) and isinstance(dst.get(key), dict):
            merged = dict(_as_dict(dst.get(key)))
            merged.update(val)
            dst[key] = merged
        elif val is not None:
            dst[key] = val


class AwsCsmOnboardingService:
    """Orchestrates cataloged onboarding actions with bounded profile writes."""

    def __init__(
        self,
        *,
        profile_store: AwsCsmOnboardingProfileStorePort,
        cloud: AwsCsmOnboardingCloudPort,
    ) -> None:
        self._profile_store = profile_store
        self._cloud = cloud

    def apply(self, payload: AwsCsmOnboardingCommand | dict[str, Any]) -> AwsCsmOnboardingOutcome:
        command = payload if isinstance(payload, AwsCsmOnboardingCommand) else self._command_from_dict(payload)
        if command.onboarding_action == "replay_verification_forward":
            raise AwsCsmOnboardingPolicyError(
                "replay_verification_forward_not_enabled",
                "Legacy Lambda forwarder replay is omitted from the default V2 shell; use portal-native capture.",
            )

        profile = self._profile_store.load_profile(
            tenant_scope_id=command.tenant_scope_id,
            profile_id=command.profile_id,
        )
        if profile is None:
            raise ValueError("onboarding profile not found for tenant_scope_id and profile_id")

        working = deepcopy(profile)
        updated = self._mutate_for_action(command, working)
        cloud_patch = self._cloud.supplemental_profile_patch(command.onboarding_action, working)
        _deep_merge_profile(working, cloud_patch)

        saved = self._profile_store.save_profile(
            tenant_scope_id=command.tenant_scope_id,
            profile_id=command.profile_id,
            payload=working,
        )

        return AwsCsmOnboardingOutcome(
            command=command,
            updated_sections=tuple(updated),
            saved_profile=saved,
        )

    def _command_from_dict(self, payload: dict[str, Any]) -> AwsCsmOnboardingCommand:
        if not isinstance(payload, dict):
            raise ValueError("aws_csm_onboarding command must be a dict")
        focus = normalize_datum_ref(
            payload.get("focus_subject"),
            require_qualified=True,
            write_format="dot",
            field_name="aws_csm_onboarding.focus_subject",
        )
        tenant_scope = _as_dict(payload.get("tenant_scope"))
        scope_id = _as_text(tenant_scope.get("scope_id") or tenant_scope.get("tenant_id"))
        return AwsCsmOnboardingCommand(
            tenant_scope_id=scope_id,
            focus_subject=focus,
            profile_id=_as_text(payload.get("profile_id")),
            onboarding_action=_as_text(payload.get("onboarding_action")),
        )

    def _mutate_for_action(self, command: AwsCsmOnboardingCommand, working: dict[str, Any]) -> list[str]:
        action = command.onboarding_action
        touched: list[str] = []

        if action == "begin_onboarding":
            wf = _as_dict(working.get("workflow"))
            wf["initiated"] = True
            wf["initiated_at"] = _utc_now_iso()
            working["workflow"] = wf
            touched.append("workflow")

        elif action in {"prepare_send_as", "stage_smtp_credentials"}:
            # Operator handoff + SES/secret material arrives via cloud patch; mark staging intent locally.
            wf = _as_dict(working.get("workflow"))
            wf["smtp_staging_requested_at"] = _utc_now_iso()
            working["workflow"] = wf
            smtp = _as_dict(working.get("smtp"))
            smtp["staging_state"] = "requested"
            working["smtp"] = smtp
            touched.extend(["workflow", "smtp"])

        elif action == "capture_verification":
            ver = _as_dict(working.get("verification"))
            ver["portal_state"] = "capture_requested"
            ver["last_capture_requested_at"] = _utc_now_iso()
            working["verification"] = ver
            inbound = _as_dict(working.get("inbound"))
            inbound["receive_state"] = "awaiting_message"
            working["inbound"] = inbound
            touched.extend(["verification", "inbound"])

        elif action == "refresh_provider_status":
            prov = _as_dict(working.get("provider"))
            prov["last_refresh_requested_at"] = _utc_now_iso()
            working["provider"] = prov
            touched.append("provider")

        elif action == "refresh_inbound_status":
            inbound = _as_dict(working.get("inbound"))
            inbound["last_refresh_requested_at"] = _utc_now_iso()
            working["inbound"] = inbound
            touched.append("inbound")

        elif action == "enable_inbound_capture":
            inbound = _as_dict(working.get("inbound"))
            inbound["capture_enable_requested_at"] = _utc_now_iso()
            inbound["mx_receipt_enable_intent"] = "requested"
            working["inbound"] = inbound
            wf = _as_dict(working.get("workflow"))
            wf["inbound_enablement_requested_at"] = _utc_now_iso()
            working["workflow"] = wf
            touched.extend(["inbound", "workflow"])

        elif action == "confirm_receive_verified":
            inbound = _as_dict(working.get("inbound"))
            inbound["receive_verified"] = True
            inbound["receive_state"] = "receive_operational"
            inbound["portal_native_display_ready"] = True
            working["inbound"] = inbound
            touched.append("inbound")

        elif action == "confirm_verified":
            if not self._cloud.gmail_confirmation_evidence_satisfied(working):
                raise AwsCsmOnboardingPolicyError(
                    "gmail_confirmation_evidence_required",
                    "confirm_verified requires Gmail confirmation evidence from the cloud port.",
                )
            ver = _as_dict(working.get("verification"))
            ver["status"] = "verified"
            ver["portal_state"] = "verified"
            working["verification"] = ver
            prov = _as_dict(working.get("provider"))
            prov["gmail_send_as_status"] = "verified"
            working["provider"] = prov
            wf = _as_dict(working.get("workflow"))
            wf["is_ready_for_user_handoff"] = True
            working["workflow"] = wf
            inbound = _as_dict(working.get("inbound"))
            inbound["portal_native_display_ready"] = True
            working["inbound"] = inbound
            touched.extend(["verification", "provider", "workflow", "inbound"])

        else:
            raise ValueError(f"unhandled cataloged action: {action}")

        return touched


__all__ = [
    "AwsCsmOnboardingService",
]
