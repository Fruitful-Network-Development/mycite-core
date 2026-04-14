from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
    BAND2_TRUSTED_TENANT_WRITABLE_NAME,
    PROFILE_BASICS_WRITE_RECOVERY_REFERENCE,
    TRUSTED_TENANT_PROFILE_BASICS_WRITE_ENTRYPOINT_ID,
    TRUSTED_TENANT_PROFILE_BASICS_WRITE_REQUEST_SCHEMA,
    TRUSTED_TENANT_PROFILE_BASICS_WRITE_SURFACE_SCHEMA,
    TRUSTED_TENANT_WRITABLE_EXPOSURE_STATUS,
    build_trusted_tenant_runtime_envelope,
    build_trusted_tenant_runtime_error,
)
from MyCiteV2.instances._shared.runtime.tenant_portal_runtime import (
    build_trusted_tenant_visible_slice_catalog,
)
from MyCiteV2.packages.adapters.filesystem import (
    FilesystemAuditLogAdapter,
    FilesystemSystemDatumStoreAdapter,
)
from MyCiteV2.packages.modules.cross_domain.local_audit import LocalAuditService
from MyCiteV2.packages.modules.domains.publication import (
    PublicationProfileBasicsService,
    PublicationTenantSummary,
    PublicationTenantSummaryService,
)
from MyCiteV2.packages.state_machine.trusted_tenant_portal import (
    TRUSTED_TENANT_PORTAL_REGION_CONTROL_PANEL_SCHEMA,
    TRUSTED_TENANT_PORTAL_REGION_INSPECTOR_SCHEMA,
    TRUSTED_TENANT_PORTAL_REGION_WORKBENCH_SCHEMA,
    TRUSTED_TENANT_PORTAL_STATE_SCHEMA,
    TrustedTenantPortalChrome,
    TrustedTenantPortalScope,
    build_trusted_tenant_activity_items,
    build_trusted_tenant_control_panel_region,
    build_trusted_tenant_portal_composition_payload,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _require_schema(payload: dict[str, Any], *, expected: str, field_name: str) -> None:
    schema = _as_text(payload.get("schema"))
    if schema != expected:
        raise ValueError(f"{field_name} must be {expected}")


def _normalize_bool(value: object, *, field_name: str) -> bool:
    if value in (None, False, ""):
        return False
    if value is True:
        return True
    token = _as_text(value).lower()
    if token in {"1", "true", "yes", "on"}:
        return True
    if token in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{field_name} must be a boolean-like value")


@dataclass(frozen=True)
class TrustedTenantProfileBasicsWriteRequest:
    tenant_scope: TrustedTenantPortalScope = field(
        default_factory=lambda: TrustedTenantPortalScope(scope_id="fnd")
    )
    shell_chrome: TrustedTenantPortalChrome = field(default_factory=TrustedTenantPortalChrome)
    apply_change: bool = False
    profile_title: str = ""
    profile_summary: str = ""
    contact_email: str = ""
    public_website_url: str = ""
    schema: str = field(default=TRUSTED_TENANT_PROFILE_BASICS_WRITE_REQUEST_SCHEMA, init=False)

    def __post_init__(self) -> None:
        tenant_scope = (
            self.tenant_scope
            if isinstance(self.tenant_scope, TrustedTenantPortalScope)
            else TrustedTenantPortalScope.from_value(self.tenant_scope)
        )
        shell_chrome = (
            self.shell_chrome
            if isinstance(self.shell_chrome, TrustedTenantPortalChrome)
            else TrustedTenantPortalChrome.from_value(self.shell_chrome)
        )
        object.__setattr__(self, "tenant_scope", tenant_scope)
        object.__setattr__(self, "shell_chrome", shell_chrome)
        object.__setattr__(
            self,
            "apply_change",
            _normalize_bool(
                self.apply_change,
                field_name="trusted_tenant_profile_basics_write_request.apply_change",
            ),
        )
        object.__setattr__(self, "profile_title", _as_text(self.profile_title))
        object.__setattr__(self, "profile_summary", _as_text(self.profile_summary))
        object.__setattr__(self, "contact_email", _as_text(self.contact_email))
        object.__setattr__(self, "public_website_url", _as_text(self.public_website_url))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": self.schema,
            "tenant_scope": self.tenant_scope.to_dict(),
        }
        chrome = self.shell_chrome.to_dict()
        if chrome:
            payload["shell_chrome"] = chrome
        if self.apply_change:
            payload["apply_change"] = True
            payload["profile_title"] = self.profile_title
            payload["profile_summary"] = self.profile_summary
            payload["contact_email"] = self.contact_email
            payload["public_website_url"] = self.public_website_url
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "TrustedTenantProfileBasicsWriteRequest":
        if payload is None:
            return cls()
        if not isinstance(payload, dict):
            raise ValueError("trusted_tenant_profile_basics_write_request must be a dict")
        _require_schema(
            payload,
            expected=TRUSTED_TENANT_PROFILE_BASICS_WRITE_REQUEST_SCHEMA,
            field_name="trusted_tenant_profile_basics_write_request.schema",
        )
        return cls(
            tenant_scope=TrustedTenantPortalScope.from_value(payload.get("tenant_scope")),
            shell_chrome=TrustedTenantPortalChrome.from_value(
                payload.get("shell_chrome") if isinstance(payload.get("shell_chrome"), dict) else None
            ),
            apply_change=payload.get("apply_change", False),
            profile_title=payload.get("profile_title") or "",
            profile_summary=payload.get("profile_summary") or "",
            contact_email=payload.get("contact_email") or "",
            public_website_url=payload.get("public_website_url") or "",
        )


def _normalize_request(
    payload: dict[str, Any] | None,
) -> TrustedTenantProfileBasicsWriteRequest:
    if payload is None:
        return TrustedTenantProfileBasicsWriteRequest()
    if not isinstance(payload, dict):
        raise ValueError("trusted_tenant_profile_basics_write_runtime.request_payload must be a dict")
    return TrustedTenantProfileBasicsWriteRequest.from_dict(payload)


def _selection_state(
    *,
    allowed: bool,
    selection_status: str,
    reason_code: str = "",
    reason_message: str = "",
) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_STATE_SCHEMA,
        "requested_slice_id": BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
        "active_surface_id": BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
        "selection_status": selection_status,
        "allowed": bool(allowed),
        "reason_code": _as_text(reason_code),
        "reason_message": _as_text(reason_message),
    }


def _apply_shell_chrome_to_composition(
    composition: dict[str, Any],
    chrome: TrustedTenantPortalChrome,
) -> None:
    echo = chrome.to_dict()
    if echo:
        composition["requested_shell_chrome"] = echo
    if chrome.control_panel_collapsed is not None:
        composition["control_panel_collapsed"] = bool(chrome.control_panel_collapsed)
    if chrome.inspector_collapsed is not None:
        composition["inspector_collapsed"] = bool(chrome.inspector_collapsed)


def _derive_read_write_posture(available_slices: list[dict[str, Any]]) -> str:
    for entry in available_slices:
        if _as_text(entry.get("read_write_posture")) == "write":
            return "write"
    return "read-only"


def _activity_items(*, portal_tenant_id: str) -> list[dict[str, Any]]:
    return build_trusted_tenant_activity_items(
        portal_tenant_id=portal_tenant_id,
        active_surface_id=BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
    )


def _control_panel_region(
    *,
    portal_tenant_id: str,
    available_slices: list[dict[str, Any]],
    read_write_posture: str,
    write_status: str,
) -> dict[str, Any]:
    attention_entries = [
        {
            "label": "Write status",
            "meta": write_status,
            "active": False,
        }
    ]
    return build_trusted_tenant_control_panel_region(
        portal_tenant_id=portal_tenant_id,
        active_surface_id=BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
        title="Profile basics",
        subtitle="Bounded-write context and approved tenant surfaces.",
        current_rollout_band=BAND2_TRUSTED_TENANT_WRITABLE_NAME,
        exposure_status=TRUSTED_TENANT_WRITABLE_EXPOSURE_STATUS,
        read_write_posture=read_write_posture,
        attention_entries=attention_entries,
        context_entries=[
            {
                "label": "Recovery reference",
                "meta": PROFILE_BASICS_WRITE_RECOVERY_REFERENCE,
                "active": False,
            }
        ],
    )


def _workbench_error(*, message: str) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_REGION_WORKBENCH_SCHEMA,
        "kind": "error",
        "title": "Profile basics",
        "subtitle": "Trusted-tenant bounded write surface",
        "visible": True,
        "message": message,
    }


def _workbench_profile_basics(
    *,
    confirmed_summary: PublicationTenantSummary,
    available_slices: list[dict[str, Any]],
    read_write_posture: str,
    write_status: str,
    requested_change: dict[str, Any] | None,
    audit: dict[str, Any] | None,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_REGION_WORKBENCH_SCHEMA,
        "kind": "profile_basics_write",
        "title": "Profile basics",
        "subtitle": "Trusted-tenant bounded write surface",
        "visible": True,
        "current_rollout_band": BAND2_TRUSTED_TENANT_WRITABLE_NAME,
        "exposure_status": TRUSTED_TENANT_WRITABLE_EXPOSURE_STATUS,
        "read_write_posture": read_write_posture,
        "write_status": write_status,
        "confirmed_profile_basics": confirmed_summary.to_dict(),
        "requested_change": None if requested_change is None else dict(requested_change),
        "audit": None if audit is None else dict(audit),
        "rollback_reference": PROFILE_BASICS_WRITE_RECOVERY_REFERENCE,
        "available_slices": list(available_slices),
        "warnings": list(warnings),
    }


def _inspector_error(*, body_text: str) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_REGION_INSPECTOR_SCHEMA,
        "title": "Profile basics editor",
        "kind": "empty",
        "body_text": body_text,
    }


def _inspector_profile_basics_form(
    *,
    confirmed_summary: PublicationTenantSummary,
    request: TrustedTenantProfileBasicsWriteRequest,
) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_REGION_INSPECTOR_SCHEMA,
        "title": "Profile basics editor",
        "kind": "profile_basics_write_form",
        "submit_contract": {
            "route": "/portal/api/v2/tenant/profile-basics",
            "request_schema": TRUSTED_TENANT_PROFILE_BASICS_WRITE_REQUEST_SCHEMA,
            "fixed_request_fields": {
                "tenant_scope": request.tenant_scope.to_dict(),
                "apply_change": True,
            },
            "initial_values": {
                "profile_title": confirmed_summary.profile_title,
                "profile_summary": confirmed_summary.profile_summary,
                "contact_email": confirmed_summary.contact_email,
                "public_website_url": confirmed_summary.public_website_url,
            },
            "writable_field_set": [
                "profile_title",
                "profile_summary",
                "contact_email",
                "public_website_url",
            ],
        },
    }


def _surface_payload(
    *,
    confirmed_summary: PublicationTenantSummary,
    available_slices: list[dict[str, Any]],
    read_write_posture: str,
    write_status: str,
    requested_change: dict[str, Any] | None,
    audit: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PROFILE_BASICS_WRITE_SURFACE_SCHEMA,
        "active_surface_id": BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
        "current_rollout_band": BAND2_TRUSTED_TENANT_WRITABLE_NAME,
        "exposure_status": TRUSTED_TENANT_WRITABLE_EXPOSURE_STATUS,
        "read_write_posture": read_write_posture,
        "location": {
            "surface_label": "Profile basics",
            "audience": "trusted-tenant",
        },
        "writable_field_set": [
            "profile_title",
            "profile_summary",
            "contact_email",
            "public_website_url",
        ],
        "confirmed_profile_basics": confirmed_summary.to_dict(),
        "requested_change": None if requested_change is None else dict(requested_change),
        "audit": None if audit is None else dict(audit),
        "rollback_reference": PROFILE_BASICS_WRITE_RECOVERY_REFERENCE,
        "write_status": write_status,
        "available_slices": list(available_slices),
        "slice_gate_posture": {
            "hidden_write_actions": "narrowly_exposed",
            "provider_admin_surfaces": "out_of_band",
            "tool_and_sandbox_surfaces": "out_of_band",
            "selection_status": "available",
        },
    }


def _error_envelope(
    *,
    tenant_scope: dict[str, Any],
    shell_state: dict[str, Any],
    portal_tenant_id: str,
    page_subtitle: str,
    message: str,
    inspector_body_text: str,
    warnings: list[str],
    error_code: str,
    error_message: str,
) -> dict[str, Any]:
    shell_composition = build_trusted_tenant_portal_composition_payload(
        active_surface_id=BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
        portal_tenant_id=portal_tenant_id,
        page_title="MyCite",
        page_subtitle=page_subtitle,
        activity_items=_activity_items(portal_tenant_id=portal_tenant_id),
        control_panel={
            "schema": TRUSTED_TENANT_PORTAL_REGION_CONTROL_PANEL_SCHEMA,
            "sections": [],
        },
        workbench=_workbench_error(message=message),
        inspector=_inspector_error(body_text=inspector_body_text),
    )
    return build_trusted_tenant_runtime_envelope(
        rollout_band=BAND2_TRUSTED_TENANT_WRITABLE_NAME,
        exposure_status=TRUSTED_TENANT_WRITABLE_EXPOSURE_STATUS,
        tenant_scope=tenant_scope,
        requested_slice_id=BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
        slice_id=BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
        entrypoint_id=TRUSTED_TENANT_PROFILE_BASICS_WRITE_ENTRYPOINT_ID,
        read_write_posture="write",
        shell_state=shell_state,
        surface_payload=None,
        shell_composition=shell_composition,
        warnings=list(warnings),
        error=build_trusted_tenant_runtime_error(
            code=error_code,
            message=error_message,
        ),
    )


def run_trusted_tenant_profile_basics_write(
    request_payload: dict[str, Any] | None = None,
    *,
    data_dir: str | Path | None = None,
    public_dir: str | Path | None = None,
    audit_storage_file: str | Path | None = None,
    portal_tenant_id: str = "fnd",
    tenant_domain: str = "",
) -> dict[str, Any]:
    normalized_request = _normalize_request(request_payload)
    tenant_scope = normalized_request.tenant_scope.to_dict()
    normalized_portal_tenant_id = _as_text(portal_tenant_id).lower() or "fnd"
    normalized_tenant_domain = _as_text(tenant_domain).lower()

    if normalized_request.tenant_scope.audience != "trusted-tenant":
        return _error_envelope(
            tenant_scope=tenant_scope,
            shell_state=_selection_state(
                allowed=False,
                selection_status="audience_denied",
                reason_code="audience_not_allowed",
                reason_message="Trusted-tenant portal requests require trusted-tenant audience.",
            ),
            portal_tenant_id=normalized_portal_tenant_id,
            page_subtitle="Audience rejected",
            message="Trusted-tenant portal requests require trusted-tenant audience.",
            inspector_body_text="Profile basics editing is unavailable for a rejected audience.",
            warnings=["Trusted-tenant profile basics rejected because the audience was not trusted-tenant."],
            error_code="audience_not_allowed",
            error_message="Trusted-tenant portal requests require trusted-tenant audience.",
        )

    if normalized_request.tenant_scope.scope_id.lower() != normalized_portal_tenant_id:
        return _error_envelope(
            tenant_scope=tenant_scope,
            shell_state=_selection_state(
                allowed=False,
                selection_status="unknown",
                reason_code="tenant_scope_mismatch",
                reason_message=(
                    "Trusted-tenant profile basics requests must stay inside the configured portal tenant scope."
                ),
            ),
            portal_tenant_id=normalized_portal_tenant_id,
            page_subtitle="Tenant scope mismatch",
            message="Trusted-tenant profile basics requests must stay inside the configured portal tenant scope.",
            inspector_body_text="Profile basics editing is unavailable for a rejected tenant scope.",
            warnings=["Trusted-tenant profile basics rejected because the tenant scope did not match the portal tenant."],
            error_code="tenant_scope_mismatch",
            error_message="Trusted-tenant profile basics requests must match the configured portal tenant scope.",
        )

    if data_dir is None or public_dir is None or not normalized_tenant_domain:
        return _error_envelope(
            tenant_scope=tenant_scope,
            shell_state=_selection_state(
                allowed=False,
                selection_status="unknown",
                reason_code="publication_source_not_configured",
                reason_message="Profile basics requires publication-backed profile configuration.",
            ),
            portal_tenant_id=normalized_portal_tenant_id,
            page_subtitle="Profile basics unavailable",
            message="The profile-basics runtime is missing its publication-backed profile configuration.",
            inspector_body_text="Profile basics editing is unavailable until the runtime is configured.",
            warnings=["Trusted-tenant profile basics runtime is missing data_dir, public_dir, or tenant_domain."],
            error_code="publication_source_not_configured",
            error_message="The trusted-tenant profile basics runtime requires data_dir, public_dir, and tenant_domain.",
        )

    if audit_storage_file is None:
        return _error_envelope(
            tenant_scope=tenant_scope,
            shell_state=_selection_state(
                allowed=False,
                selection_status="unknown",
                reason_code="audit_log_not_configured",
                reason_message="Profile basics write requires an audit storage file.",
            ),
            portal_tenant_id=normalized_portal_tenant_id,
            page_subtitle="Profile basics unavailable",
            message="The profile-basics runtime is missing its audit persistence configuration.",
            inspector_body_text="Profile basics editing is unavailable until audit storage is configured.",
            warnings=["Trusted-tenant profile basics runtime is missing audit_storage_file."],
            error_code="audit_log_not_configured",
            error_message="The trusted-tenant profile basics runtime requires audit_storage_file.",
        )

    available_slices = [dict(entry) for entry in build_trusted_tenant_visible_slice_catalog()]
    read_write_posture = _derive_read_write_posture(available_slices)
    datum_store = FilesystemSystemDatumStoreAdapter(
        Path(data_dir),
        public_dir=Path(public_dir),
    )
    read_service = PublicationTenantSummaryService(datum_store)

    warnings: list[str] = []
    audit_payload: dict[str, Any] | None = None
    requested_change: dict[str, Any] | None = None
    write_status = "ready"

    if normalized_request.apply_change:
        try:
            outcome = PublicationProfileBasicsService(datum_store).apply_write(
                {
                    "tenant_id": normalized_portal_tenant_id,
                    "tenant_domain": normalized_tenant_domain,
                    "profile_title": normalized_request.profile_title,
                    "profile_summary": normalized_request.profile_summary,
                    "contact_email": normalized_request.contact_email,
                    "public_website_url": normalized_request.public_website_url,
                }
            )
        except ValueError as exc:
            return _error_envelope(
                tenant_scope=tenant_scope,
                shell_state=_selection_state(
                    allowed=True,
                    selection_status="available",
                    reason_code="write_rejected",
                    reason_message=str(exc),
                ),
                portal_tenant_id=normalized_portal_tenant_id,
                page_subtitle="Write rejected",
                message=str(exc),
                inspector_body_text="Profile basics editing remains available after a rejected write.",
                warnings=[str(exc)],
                error_code="write_rejected",
                error_message=str(exc),
            )

        audit_service = LocalAuditService(FilesystemAuditLogAdapter(audit_storage_file))
        audit_receipt = audit_service.append_record(outcome.to_local_audit_payload())
        confirmed_summary = outcome.confirmed_summary
        warnings.extend(list(confirmed_summary.warnings))
        audit_payload = audit_receipt.to_dict()
        requested_change = {
            "profile_title": outcome.command.profile_title,
            "profile_summary": outcome.command.profile_summary,
            "contact_email": outcome.command.contact_email,
            "public_website_url": outcome.command.public_website_url,
        }
        write_status = "applied"
    else:
        confirmed_summary = read_service.read_summary(
            normalized_portal_tenant_id,
            normalized_tenant_domain,
        )
        if confirmed_summary is None:
            return _error_envelope(
                tenant_scope=tenant_scope,
                shell_state=_selection_state(
                    allowed=True,
                    selection_status="available",
                    reason_code="publication_profile_not_found",
                    reason_message="No publication-backed profile basics source was found for this tenant.",
                ),
                portal_tenant_id=normalized_portal_tenant_id,
                page_subtitle="Profile basics unavailable",
                message="No publication-backed profile basics source was found for this tenant.",
                inspector_body_text="Profile basics editing is unavailable until a publication profile is mapped.",
                warnings=["Trusted-tenant profile basics could not resolve a publication-backed profile."],
                error_code="publication_profile_not_found",
                error_message="No publication-backed profile basics source was found for this tenant.",
            )
        warnings.extend(list(confirmed_summary.warnings))

    shell_composition = build_trusted_tenant_portal_composition_payload(
        active_surface_id=BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
        portal_tenant_id=normalized_portal_tenant_id,
        page_title="MyCite",
        page_subtitle="Profile basics",
        activity_items=_activity_items(portal_tenant_id=normalized_portal_tenant_id),
        control_panel=_control_panel_region(
            portal_tenant_id=normalized_portal_tenant_id,
            available_slices=available_slices,
            read_write_posture=read_write_posture,
            write_status=write_status,
        ),
        workbench=_workbench_profile_basics(
            confirmed_summary=confirmed_summary,
            available_slices=available_slices,
            read_write_posture=read_write_posture,
            write_status=write_status,
            requested_change=requested_change,
            audit=audit_payload,
            warnings=warnings,
        ),
        inspector=_inspector_profile_basics_form(
            confirmed_summary=confirmed_summary,
            request=normalized_request,
        ),
    )
    _apply_shell_chrome_to_composition(shell_composition, normalized_request.shell_chrome)

    return build_trusted_tenant_runtime_envelope(
        rollout_band=BAND2_TRUSTED_TENANT_WRITABLE_NAME,
        exposure_status=TRUSTED_TENANT_WRITABLE_EXPOSURE_STATUS,
        tenant_scope=tenant_scope,
        requested_slice_id=BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
        slice_id=BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
        entrypoint_id=TRUSTED_TENANT_PROFILE_BASICS_WRITE_ENTRYPOINT_ID,
        read_write_posture=read_write_posture,
        shell_state=_selection_state(allowed=True, selection_status="available"),
        surface_payload=_surface_payload(
            confirmed_summary=confirmed_summary,
            available_slices=available_slices,
            read_write_posture=read_write_posture,
            write_status=write_status,
            requested_change=requested_change,
            audit=audit_payload,
        ),
        shell_composition=shell_composition,
        warnings=warnings,
        error=None,
    )


__all__ = [
    "TrustedTenantProfileBasicsWriteRequest",
    "TRUSTED_TENANT_PROFILE_BASICS_WRITE_REQUEST_SCHEMA",
    "TRUSTED_TENANT_PROFILE_BASICS_WRITE_SURFACE_SCHEMA",
    "run_trusted_tenant_profile_basics_write",
]
