"""Portal shell schema identifiers, surface IDs, routes, entrypoints, and constants."""

from __future__ import annotations

PORTAL_SHELL_REQUEST_SCHEMA = "mycite.v2.portal.shell.request.v1"
PORTAL_SHELL_STATE_SCHEMA = "mycite.v2.portal.shell.state.v1"
PORTAL_SHELL_COMPOSITION_SCHEMA = "mycite.v2.portal.shell.composition.v1"
PORTAL_SHELL_REGION_ACTIVITY_BAR_SCHEMA = "mycite.v2.portal.shell.region.activity_bar.v1"
PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA = "mycite.v2.portal.shell.region.control_panel.v1"
PORTAL_SHELL_REGION_WORKBENCH_SCHEMA = "mycite.v2.portal.shell.region.workbench.v1"
PORTAL_SHELL_REGION_INTERFACE_PANEL_SCHEMA = "mycite.v2.portal.shell.region.interface_panel.v1"
PORTAL_SURFACE_CATALOG_ENTRY_SCHEMA = "mycite.v2.portal.surface_catalog.entry.v1"
PORTAL_TOOL_REGISTRY_ENTRY_SCHEMA = "mycite.v2.portal.tool_registry.entry.v1"

SYSTEM_ROOT_SURFACE_ID = "system.root"
NETWORK_ROOT_SURFACE_ID = "network.root"
UTILITIES_ROOT_SURFACE_ID = "utilities.root"
UTILITIES_TOOL_EXPOSURE_SURFACE_ID = "utilities.tool_exposure"
UTILITIES_INTEGRATIONS_SURFACE_ID = "utilities.integrations"

CTS_GIS_TOOL_SURFACE_ID = "system.tools.cts_gis"
FND_CSM_TOOL_SURFACE_ID = "system.tools.fnd_csm"
WORKBENCH_UI_TOOL_SURFACE_ID = "system.tools.workbench_ui"

# Canonical sandbox tokens (underscore form per
# docs/contracts/datum_document_naming_taxonomy.md §"URL Slug vs
# Sandbox Token"). These are the only authoritative spellings —
# downstream code must import these constants rather than re-literal
# the strings.
CTS_GIS_SANDBOX_TOKEN = "cts_gis"
FND_CSM_SANDBOX_TOKEN = "fnd_csm"
WORKBENCH_UI_SANDBOX_TOKEN = "system"  # Workbench-UI is a system-sandbox reflective view

PORTAL_SHELL_ENTRYPOINT_ID = "portal.shell"
CTS_GIS_TOOL_ENTRYPOINT_ID = "portal.system.tools.cts_gis"
FND_CSM_TOOL_ENTRYPOINT_ID = "portal.system.tools.fnd_csm"
WORKBENCH_UI_TOOL_ENTRYPOINT_ID = "portal.system.tools.workbench_ui"

SYSTEM_ROOT_ROUTE = "/portal/system"
NETWORK_ROOT_ROUTE = "/portal/network"
UTILITIES_ROOT_ROUTE = "/portal/utilities"
UTILITIES_TOOL_EXPOSURE_ROUTE = "/portal/utilities/tool-exposure"
UTILITIES_INTEGRATIONS_ROUTE = "/portal/utilities/integrations"

CTS_GIS_TOOL_ROUTE = "/portal/system/tools/cts-gis"
FND_CSM_TOOL_ROUTE = "/portal/system/tools/fnd-csm"
WORKBENCH_UI_TOOL_ROUTE = "/portal/system/tools/workbench-ui"

SYSTEM_ANCHOR_FILE_KEY = "anthology"
TOOL_ANCHOR_FILE_KEY = "anchor"
SYSTEM_ACTIVITY_FILE_KEY = "activity"
SYSTEM_PROFILE_BASICS_FILE_KEY = "profile_basics"
SYSTEM_SANDBOX_QUERY_FILE_TOKEN = "sandbox"

PORTAL_SCOPE_DEFAULT_ID = "fnd"
SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY = "interface_panel_primary"
TOOL_KIND_GENERAL = "general_tool"
TOOL_KIND_SERVICE = "service_tool"
TOOL_KIND_HOST_ALIAS = "host_alias_tool"

FOCUS_LEVEL_SANDBOX = "sandbox"
FOCUS_LEVEL_FILE = "file"
FOCUS_LEVEL_DATUM = "datum"
FOCUS_LEVEL_OBJECT = "object"
FOCUS_LEVELS = (
    FOCUS_LEVEL_SANDBOX,
    FOCUS_LEVEL_FILE,
    FOCUS_LEVEL_DATUM,
    FOCUS_LEVEL_OBJECT,
)
FOCUS_LEVEL_INDEX = {level: index for index, level in enumerate(FOCUS_LEVELS)}

VERB_NAVIGATE = "navigate"
VERB_INVESTIGATE = "investigate"
VERB_MEDIATE = "mediate"
VERB_MANIPULATE = "manipulate"
PORTAL_SHELL_VERBS = (
    VERB_NAVIGATE,
    VERB_INVESTIGATE,
    VERB_MEDIATE,
    VERB_MANIPULATE,
)

TRANSITION_ENTER_SURFACE = "enter_surface"
TRANSITION_FOCUS_SANDBOX = "focus_sandbox"
TRANSITION_FOCUS_FILE = "focus_file"
TRANSITION_FOCUS_DATUM = "focus_datum"
TRANSITION_FOCUS_OBJECT = "focus_object"
TRANSITION_BACK_OUT = "back_out"
TRANSITION_SET_VERB = "set_verb"
TRANSITION_OPEN_INTERFACE_PANEL = "open_interface_panel"
TRANSITION_CLOSE_INTERFACE_PANEL = "close_interface_panel"
PORTAL_SHELL_TRANSITIONS = (
    TRANSITION_ENTER_SURFACE,
    TRANSITION_FOCUS_SANDBOX,
    TRANSITION_FOCUS_FILE,
    TRANSITION_FOCUS_DATUM,
    TRANSITION_FOCUS_OBJECT,
    TRANSITION_BACK_OUT,
    TRANSITION_SET_VERB,
    TRANSITION_OPEN_INTERFACE_PANEL,
    TRANSITION_CLOSE_INTERFACE_PANEL,
)

ROOT_SURFACE_IDS = frozenset(
    {
        SYSTEM_ROOT_SURFACE_ID,
        NETWORK_ROOT_SURFACE_ID,
        UTILITIES_ROOT_SURFACE_ID,
    }
)
TOOL_SURFACE_IDS = frozenset(
    {
        CTS_GIS_TOOL_SURFACE_ID,
        FND_CSM_TOOL_SURFACE_ID,
        WORKBENCH_UI_TOOL_SURFACE_ID,
    }
)
SYSTEM_SURFACE_IDS = frozenset({SYSTEM_ROOT_SURFACE_ID, *TOOL_SURFACE_IDS})
NETWORK_SURFACE_IDS = frozenset({NETWORK_ROOT_SURFACE_ID})
UTILITIES_SURFACE_IDS = frozenset(
    {
        UTILITIES_ROOT_SURFACE_ID,
        UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
        UTILITIES_INTEGRATIONS_SURFACE_ID,
    }
)
REDUCER_OWNED_SURFACE_IDS = frozenset(
    {
        SYSTEM_ROOT_SURFACE_ID,
        CTS_GIS_TOOL_SURFACE_ID,
        FND_CSM_TOOL_SURFACE_ID,
    }
)
