"""Agro-ERP portal tool runtime — a thin back-compat shim.

The Agro-ERP "tool" is no longer a separate runtime. It is the unified
workbench (see ``portal_workbench_ui_runtime.build_portal_workbench_ui_bundle``)
opened against the ``agro_erp`` sandbox. The workbench handles document
filtering, the ``new_source_document_form`` + ``new_datum_form`` slots,
the write posture, and the sandbox-aware labels.

This module exists only to:

1. Provide stable import names for the legacy routing dispatch in
   ``portal_shell_runtime._build_agro_erp_tool_bundle`` and for existing
   tests that import ``build_portal_agro_erp_surface_bundle``.
2. Re-stamp the surface_payload + request_contract with the Agro-ERP
   schema/route/entrypoint identifiers so external bookmarks at
   ``/portal/system/tools/agro-erp`` continue to resolve.

The doctrinal rule from the user: "modularization and reuse but
different setting of use" — the workbench is the modular code, the
sandbox is the setting. No tool-specific divergence.

Per ``docs/contracts/mos_authority_enforcement.md`` the underlying
workbench reads exclusively from the MOS authority via
``SqliteSystemDatumStoreAdapter``. No filesystem datum reads.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.portal_lens_runtime import enabled_lens_ids
from MyCiteV2.instances._shared.runtime.portal_workbench_ui_runtime import (
    build_portal_workbench_ui_bundle,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    AGRO_ERP_SANDBOX_TOKEN,
    AGRO_ERP_TOOL_ENTRYPOINT_ID,
    AGRO_ERP_TOOL_ROUTE,
    AGRO_ERP_TOOL_SURFACE_ID,
    PortalScope,
)

AGRO_ERP_TOOL_SURFACE_SCHEMA = "mycite.v2.portal.system.tools.agro_erp.surface.v1"
AGRO_ERP_TOOL_REQUEST_SCHEMA = "mycite.v2.portal.system.tools.agro_erp.request.v1"


def build_portal_agro_erp_surface_bundle(
    *,
    portal_scope: PortalScope,
    portal_domain: str,
    shell_state: object | None,
    authority_db_file: str | Path | None,
    tool_rows: list[dict[str, Any]] | None = None,
    surface_query: dict[str, Any] | None = None,
    private_dir: str | Path | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Build the surface bundle for ``/portal/system/tools/agro-erp``.

    Delegates to the unified workbench runtime with ``sandbox="agro_erp"``
    and re-stamps the surface identifiers so legacy routes and bookmarks
    still resolve to the Agro-ERP schema. Honors the operator's Control-Panel
    lens toggles (``enabled_lens_ids``) like the ``/portal/system`` path does —
    previously this surface ran all-lenses-enabled regardless of the toggles.
    """
    bundle = build_portal_workbench_ui_bundle(
        portal_scope=portal_scope,
        portal_domain=portal_domain,
        shell_state=shell_state,
        authority_db_file=authority_db_file,
        tool_rows=tool_rows,
        surface_query=surface_query,
        sandbox=AGRO_ERP_SANDBOX_TOKEN,
        enabled_lens_ids=enabled_lens_ids(private_dir),
    )

    # Re-stamp the surface identifiers so the route and schema remain
    # agro-erp-specific even though the runtime is now the workbench.
    payload = bundle.setdefault("surface_payload", {})
    payload["schema"] = AGRO_ERP_TOOL_SURFACE_SCHEMA
    payload["kind"] = "agro_erp_workbench"
    payload["title"] = "Agro-ERP"
    payload["subtitle"] = "Agro-ERP taxonomy and source-document workbench."
    payload["request_contract"] = {
        "schema": AGRO_ERP_TOOL_REQUEST_SCHEMA,
        "route": AGRO_ERP_TOOL_ROUTE,
        "surface_id": AGRO_ERP_TOOL_SURFACE_ID,
        "entrypoint_id": AGRO_ERP_TOOL_ENTRYPOINT_ID,
    }
    bundle["page_title"] = "Agro-ERP"
    bundle["page_subtitle"] = "Agro-ERP taxonomy and source-document workbench."
    bundle["entrypoint_id"] = AGRO_ERP_TOOL_ENTRYPOINT_ID
    bundle["route"] = AGRO_ERP_TOOL_ROUTE
    return bundle
