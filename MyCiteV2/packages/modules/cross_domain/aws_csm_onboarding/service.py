"""Shell-owned AWS-CSM onboarding semantics."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from MyCiteV2.packages.modules.shared import as_dict, as_text, normalize_focus_subject, utc_now_iso
from MyCiteV2.packages.ports.aws_csm_onboarding import (
    AwsCsmOnboardingCloudPort,
    AwsCsmOnboardingCommand,
    AwsCsmOnboardingOutcome,
    AwsCsmOnboardingPolicyError,
    AwsCsmOnboardingProfileStorePort,
)


def _merge_section(dst: dict[str, Any], key: str, delta: dict[str, Any] | None) -> None:
    if not delta:
        return
    base = as_dict(dst.get(key))
    base.update(delta)
    dst[key] = base


def _deep_merge_profile(dst: dict[str, Any], fragment: dict[str, Any]) -> None:
    for key, val in fragment.items():
        if isinstance(val, dict) and isinstance(dst.get(key), dict):
            merged = dict(as_dict(dst.get(key)))
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
                "Forwarder replay is omitted from the canonical shell; use portal-native capture.",
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
        focus = normalize_focus_subject(
            payload.get("focus_subject"),
            field_name="aws_csm_onboarding.focus_subject",
        )
        tenant_scope = as_dict(payload.get("tenant_scope"))
        scope_id = as_text(tenant_scope.get("scope_id") or tenant_scope.get("tenant_id"))
        return AwsCsmOnboardingCommand(
            tenant_scope_id=scope_id,
            focus_subject=focus,
            profile_id=as_text(payload.get("profile_id")),
            onboarding_action=as_text(payload.get("onboarding_action")),
        )

    def _confirmation_evidence_satisfied(self, profile: dict[str, Any]) -> bool:
        probe = getattr(self._cloud, "confirmation_evidence_satisfied", None)
        if callable(probe):
            return bool(probe(profile))
        legacy_probe = getattr(self._cloud, "gmail_confirmation_evidence_satisfied", None)
        if callable(legacy_probe):
            return bool(legacy_probe(profile))
        return False

    def _mutate_for_action(self, command: AwsCsmOnboardingCommand, working: dict[str, Any]) -> list[str]:
        action = command.onboarding_action
        touched: list[str] = []

        if action == "begin_onboarding":
            wf = as_dict(working.get("workflow"))
            wf["initiated"] = True
            wf["initiated_at"] = utc_now_iso(seconds_precision=True)
            working["workflow"] = wf
            touched.append("workflow")

        elif action in {"prepare_send_as", "stage_smtp_credentials"}:
            # Operator handoff + SES/secret material arrives via cloud patch; mark staging intent locally.
            wf = as_dict(working.get("workflow"))
            wf["smtp_staging_requested_at"] = utc_now_iso(seconds_precision=True)
            working["workflow"] = wf
            smtp = as_dict(working.get("smtp"))
            smtp["staging_state"] = "requested"
            working["smtp"] = smtp
            touched.extend(["workflow", "smtp"])

        elif action == "capture_verification":
            ver = as_dict(working.get("verification"))
            ver["portal_state"] = "capture_requested"
            ver["last_capture_requested_at"] = utc_now_iso(seconds_precision=True)
            working["verification"] = ver
            inbound = as_dict(working.get("inbound"))
            inbound["receive_state"] = "awaiting_message"
            working["inbound"] = inbound
            touched.extend(["verification", "inbound"])

        elif action == "refresh_provider_status":
            prov = as_dict(working.get("provider"))
            prov["last_refresh_requested_at"] = utc_now_iso(seconds_precision=True)
            working["provider"] = prov
            touched.append("provider")

        elif action == "refresh_inbound_status":
            inbound = as_dict(working.get("inbound"))
            inbound["last_refresh_requested_at"] = utc_now_iso(seconds_precision=True)
            working["inbound"] = inbound
            touched.append("inbound")

        elif action == "enable_inbound_capture":
            inbound = as_dict(working.get("inbound"))
            inbound["capture_enable_requested_at"] = utc_now_iso(seconds_precision=True)
            inbound["mx_receipt_enable_intent"] = "requested"
            working["inbound"] = inbound
            wf = as_dict(working.get("workflow"))
            wf["inbound_enablement_requested_at"] = utc_now_iso(seconds_precision=True)
            working["workflow"] = wf
            touched.extend(["inbound", "workflow"])

        elif action == "confirm_receive_verified":
            inbound = as_dict(working.get("inbound"))
            inbound["receive_verified"] = True
            inbound["receive_state"] = "receive_operational"
            inbound["portal_native_display_ready"] = True
            working["inbound"] = inbound
            touched.append("inbound")

        elif action == "confirm_verified":
            if not self._confirmation_evidence_satisfied(working):
                raise AwsCsmOnboardingPolicyError(
                    "confirmation_evidence_required",
                    "confirm_verified requires confirmation evidence from the cloud port.",
                )
            ver = as_dict(working.get("verification"))
            ver["status"] = "verified"
            ver["portal_state"] = "verified"
            ver["verified_at"] = utc_now_iso(seconds_precision=True)
            ver["verification_mode"] = "evidence"
            ver["verified_by_focus_subject"] = command.focus_subject
            working["verification"] = ver
            prov = as_dict(working.get("provider"))
            handoff_provider = as_text(
                prov.get("handoff_provider")
                or as_dict(working.get("identity")).get("handoff_provider")
            ).lower()
            prov["handoff_provider"] = handoff_provider or "generic_manual"
            prov["send_as_provider_status"] = "verified"
            if prov["handoff_provider"] == "gmail":
                prov["gmail_send_as_status"] = "verified"
            working["provider"] = prov
            wf = as_dict(working.get("workflow"))
            wf["is_ready_for_user_handoff"] = True
            wf["handoff_status"] = "send_as_confirmed"
            working["workflow"] = wf
            inbound = as_dict(working.get("inbound"))
            inbound["portal_native_display_ready"] = True
            working["inbound"] = inbound
            touched.extend(["verification", "provider", "workflow", "inbound"])

        elif action == "confirm_verified_attested":
            ver = as_dict(working.get("verification"))
            ver["status"] = "verified"
            ver["portal_state"] = "verified"
            ver["verified_at"] = utc_now_iso(seconds_precision=True)
            ver["verification_mode"] = "attested"
            ver["attested_at"] = utc_now_iso(seconds_precision=True)
            ver["attested_by_focus_subject"] = command.focus_subject
            working["verification"] = ver
            prov = as_dict(working.get("provider"))
            handoff_provider = as_text(
                prov.get("handoff_provider")
                or as_dict(working.get("identity")).get("handoff_provider")
            ).lower()
            prov["handoff_provider"] = handoff_provider or "generic_manual"
            prov["send_as_provider_status"] = "verified"
            if prov["handoff_provider"] == "gmail":
                prov["gmail_send_as_status"] = "verified"
            working["provider"] = prov
            wf = as_dict(working.get("workflow"))
            wf["is_ready_for_user_handoff"] = True
            wf["handoff_status"] = "send_as_confirmed_attested"
            working["workflow"] = wf
            inbound = as_dict(working.get("inbound"))
            inbound["portal_native_display_ready"] = True
            working["inbound"] = inbound
            touched.extend(["verification", "provider", "workflow", "inbound"])

        else:
            raise ValueError(f"unhandled cataloged action: {action}")

        return touched


__all__ = [
    "AwsCsmOnboardingService",
]
