from __future__ import annotations

DEFAULT_ATTENTION_NODE_ID = "3-2-3-17-77"
DEFAULT_ATTENTION_PROFILE_LABEL = "summit_county"
DEFAULT_SUPPORTING_DOCUMENT_NAME = "sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json"
DEFAULT_PROJECTION_DOCUMENT_SUFFIX = f".{DEFAULT_ATTENTION_NODE_ID}.json"

DEFAULT_INTENTION_TOKEN = "descendants_depth_1_or_2"
LEGACY_SELF_INTENTION_TOKEN = "0"
CHILDREN_INTENTION_TOKEN = "1-0"
BRANCH_INTENTION_PREFIX = "branch:"

DEFAULT_TIME_DIRECTIVE = "4-447-751-507-819"
DEFAULT_ARCHETYPE_FAMILY_ID = "samras_nominal"
DEFAULT_NIMM_DIRECTIVE = "mediate"

CTS_GIS_CANONICAL_TOOL_PUBLIC_ID = "cts_gis"
CTS_GIS_CANONICAL_DOCUMENT_PREFIX = "sandbox:cts_gis:"
CTS_GIS_NAV_MODE_DIRECTORY = "directory_dropdowns"
CTS_GIS_COMPILED_ARTIFACT_SCHEMA = "mycite.v2.portal.system.tools.cts_gis.compiled.v1"
CTS_GIS_RUNTIME_MODE_PRODUCTION_STRICT = "production_strict"
CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC = "audit_forensic"


def as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def descendants_intention_token(attention_node_id: object) -> str:
    node_id = as_text(attention_node_id)
    return f"{node_id}-0-0" if node_id else DEFAULT_INTENTION_TOKEN


def children_intention_token(attention_node_id: object) -> str:
    node_id = as_text(attention_node_id)
    return f"{node_id}-0" if node_id else "children"


def canonical_service_intention_token(requested: object, *, attention_node_id: object) -> str:
    token = as_text(requested) or DEFAULT_INTENTION_TOKEN
    if token in {LEGACY_SELF_INTENTION_TOKEN, "self"}:
        return "self"
    if token in {"children", CHILDREN_INTENTION_TOKEN, children_intention_token(attention_node_id)}:
        return children_intention_token(attention_node_id)
    if token in {DEFAULT_INTENTION_TOKEN, descendants_intention_token(attention_node_id)}:
        return descendants_intention_token(attention_node_id)
    return token


def canonical_runtime_intention_rule_id(service_token: object, *, attention_node_id: object) -> str:
    token = as_text(service_token)
    if not token:
        return DEFAULT_INTENTION_TOKEN
    if token == "self":
        return "self"
    if token in {"children", CHILDREN_INTENTION_TOKEN, children_intention_token(attention_node_id)}:
        return children_intention_token(attention_node_id)
    if token in {DEFAULT_INTENTION_TOKEN, descendants_intention_token(attention_node_id)}:
        return descendants_intention_token(attention_node_id)
    return token


__all__ = [
    "BRANCH_INTENTION_PREFIX",
    "CHILDREN_INTENTION_TOKEN",
    "CTS_GIS_CANONICAL_DOCUMENT_PREFIX",
    "CTS_GIS_CANONICAL_TOOL_PUBLIC_ID",
    "CTS_GIS_COMPILED_ARTIFACT_SCHEMA",
    "CTS_GIS_NAV_MODE_DIRECTORY",
    "CTS_GIS_RUNTIME_MODE_AUDIT_FORENSIC",
    "CTS_GIS_RUNTIME_MODE_PRODUCTION_STRICT",
    "DEFAULT_ARCHETYPE_FAMILY_ID",
    "DEFAULT_ATTENTION_NODE_ID",
    "DEFAULT_ATTENTION_PROFILE_LABEL",
    "DEFAULT_INTENTION_TOKEN",
    "DEFAULT_NIMM_DIRECTIVE",
    "DEFAULT_PROJECTION_DOCUMENT_SUFFIX",
    "DEFAULT_SUPPORTING_DOCUMENT_NAME",
    "DEFAULT_TIME_DIRECTIVE",
    "LEGACY_SELF_INTENTION_TOKEN",
    "as_text",
    "canonical_runtime_intention_rule_id",
    "canonical_service_intention_token",
    "children_intention_token",
    "descendants_intention_token",
]
