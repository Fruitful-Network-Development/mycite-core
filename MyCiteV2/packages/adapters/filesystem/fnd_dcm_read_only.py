from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from ...ports.fnd_dcm_read_only import (
    FndDcmReadOnlyPort,
    FndDcmReadOnlyRequest,
    FndDcmReadOnlyResult,
    FndDcmReadOnlySource,
)

FND_DCM_PROFILE_SCHEMA = "mycite.service_tool.fnd_dcm.profile.v1"
DEFAULT_WEBAPPS_ROOT = Path("/srv/webapps")


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _normalize_domain(value: object) -> str:
    token = _as_text(value).lower()
    if not token or "." not in token or "/" in token or "\\" in token or ".." in token:
        raise ValueError("fnd_dcm profile domain must be a plain domain-like value")
    return token


def _safe_json_object(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_json_value(path: Path | None) -> Any:
    if path is None or not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _relative_path(path: Path, *, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


def _resolve_relative_path(root: Path, relative_path: object, *, field_name: str) -> Path:
    token = _as_text(relative_path)
    if not token:
        raise ValueError(f"{field_name} is required")
    raw = Path(token)
    if raw.is_absolute():
        raise ValueError(f"{field_name} must be relative to the frontend root")
    candidate = (root / raw).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"{field_name} must stay within the frontend root") from exc
    return candidate


def _issue(*, severity: str, code: str, message: str, path: str = "", context: str = "") -> dict[str, str]:
    payload = {
        "severity": _as_text(severity) or "warning",
        "code": _as_text(code) or "issue",
        "message": _as_text(message) or "Issue detected.",
    }
    if _as_text(path):
        payload["path"] = _as_text(path)
    if _as_text(context):
        payload["context"] = _as_text(context)
    return payload


def _navigation_items(value: object) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in _as_list(value):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "id": _as_text(item.get("id")),
                "label": _as_text(item.get("label")),
                "href": _as_text(item.get("href")),
                "icon": _as_text(item.get("icon")),
            }
        )
    return rows


def _collect_collection_refs(
    value: object,
    *,
    known_collection_ids: set[str],
) -> list[str]:
    found: set[str] = set()

    def _visit(node: object, *, parent_key: str = "") -> None:
        if isinstance(node, dict):
            for key, item in node.items():
                key_token = _as_text(key)
                if key_token == "collection" or key_token.endswith("_collection"):
                    token = _as_text(item)
                    if token in known_collection_ids:
                        found.add(token)
                _visit(item, parent_key=key_token)
            return
        if isinstance(node, list):
            for item in node:
                _visit(item, parent_key=parent_key)

    _visit(value)
    return sorted(found)


def _page_rows(pages_payload: dict[str, Any], *, known_collection_ids: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page_id, raw_page in pages_payload.items():
        page = _as_dict(raw_page)
        rows.append(
            {
                "id": _as_text(page_id),
                "file": _as_text(page.get("file")),
                "template": _as_text(page.get("template")),
                "title": _as_text(page.get("title")),
                "description": _as_text(page.get("description")),
                "collection_refs": _collect_collection_refs(page, known_collection_ids=known_collection_ids),
                "raw": page,
            }
        )
    return rows


def _collection_source_rows(
    *,
    frontend_root: Path,
    collection_id: str,
    collection_type: str,
    collection_payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    sources: list[dict[str, Any]] = []
    collection_rows: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    if collection_type == "json_file":
        source_token = _as_text(collection_payload.get("source"))
        source_path = _resolve_relative_path(
            frontend_root,
            source_token,
            field_name=f"collections.{collection_id}.source",
        )
        exists = source_path.exists() and source_path.is_file()
        preview_payload = _safe_json_value(source_path) if exists else None
        sources.append(
            {
                "collection_id": collection_id,
                "source_kind": "json_file",
                "path": str(source_path),
                "relative_path": _relative_path(source_path, root=frontend_root),
                "exists": exists,
            }
        )
        collection_rows.append(
            {
                "id": collection_id,
                "type": collection_type,
                "source": source_token,
                "source_files": [item["relative_path"] for item in sources],
                "source_count": len(sources),
                "preview_payload": preview_payload,
            }
        )
        if not exists:
            issues.append(
                _issue(
                    severity="warning",
                    code="collection_source_missing",
                    message="JSON collection source file is missing.",
                    path=str(source_path),
                    context=collection_id,
                )
            )
        return collection_rows, sources, issues
    if collection_type == "markdown_directory":
        directory_token = _as_text(collection_payload.get("directory"))
        pattern = _as_text(collection_payload.get("pattern")) or "*.md"
        directory_path = _resolve_relative_path(
            frontend_root,
            directory_token,
            field_name=f"collections.{collection_id}.directory",
        )
        if directory_path.exists() and directory_path.is_dir():
            for matched in sorted(directory_path.glob(pattern)):
                sources.append(
                    {
                        "collection_id": collection_id,
                        "source_kind": "markdown_document",
                        "path": str(matched),
                        "relative_path": _relative_path(matched, root=frontend_root),
                        "exists": matched.is_file(),
                    }
                )
        else:
            issues.append(
                _issue(
                    severity="warning",
                    code="collection_directory_missing",
                    message="Markdown collection directory is missing.",
                    path=str(directory_path),
                    context=collection_id,
                )
            )
        collection_rows.append(
            {
                "id": collection_id,
                "type": collection_type,
                "directory": directory_token,
                "pattern": pattern,
                "sort_by": _as_text(collection_payload.get("sort_by")),
                "sort_order": _as_text(collection_payload.get("sort_order")) or "asc",
                "source_files": [item["relative_path"] for item in sources],
                "source_count": len(sources),
            }
        )
        return collection_rows, sources, issues
    if collection_type == "markdown_documents":
        for raw_item in _as_list(collection_payload.get("items")):
            item = _as_dict(raw_item)
            source_token = _as_text(item.get("source"))
            if not source_token:
                continue
            source_path = _resolve_relative_path(
                frontend_root,
                source_token,
                field_name=f"collections.{collection_id}.items[].source",
            )
            sources.append(
                {
                    "collection_id": collection_id,
                    "source_kind": "markdown_document",
                    "path": str(source_path),
                    "relative_path": _relative_path(source_path, root=frontend_root),
                    "exists": source_path.exists() and source_path.is_file(),
                }
            )
        collection_rows.append(
            {
                "id": collection_id,
                "type": collection_type,
                "source_files": [item["relative_path"] for item in sources],
                "source_count": len(sources),
            }
        )
        for row in sources:
            if not row["exists"]:
                issues.append(
                    _issue(
                        severity="warning",
                        code="collection_source_missing",
                        message="Markdown document source file is missing.",
                        path=_as_text(row.get("path")),
                        context=collection_id,
                    )
                )
        return collection_rows, sources, issues
    collection_rows.append(
        {
            "id": collection_id,
            "type": collection_type,
            "source_files": [],
            "source_count": 0,
        }
    )
    issues.append(
        _issue(
            severity="warning",
            code="collection_type_unsupported",
            message="Collection type is unsupported by the FND-DCM normalizer.",
            context=collection_id,
        )
    )
    return collection_rows, sources, issues


def _normalize_footer(footer_payload: object) -> dict[str, Any]:
    footer = _as_dict(footer_payload)
    columns = [dict(item) for item in _as_list(footer.get("columns")) if isinstance(item, dict)]
    return {
        "copyright": _as_text(footer.get("copyright")),
        "column_count": len(columns),
        "column_templates": [
            _as_text(item.get("template")) or _as_text(item.get("class_name")) or "column"
            for item in columns
        ],
    }


def _machine_surface_summary(manifest_payload: dict[str, Any]) -> dict[str, Any]:
    machine_payload = _as_dict(manifest_payload.get("machine"))
    if not machine_payload:
        machine_payload = _as_dict(manifest_payload.get("machine_surfaces"))
    if not machine_payload:
        return {}

    inpage = _as_dict(machine_payload.get("inpage"))
    pages = _as_dict(machine_payload.get("pages"))
    endpoint_maps = _as_dict(machine_payload.get("endpoint_maps"))
    blocks = [item for item in _as_list(inpage.get("blocks")) if isinstance(item, dict)]
    endpoints = [item for item in _as_list(pages.get("endpoints")) if isinstance(item, dict)]

    return {
        "root_keys": sorted(machine_payload.keys()),
        "inpage_root": _as_text(inpage.get("root")),
        "inpage_block_count": len(blocks),
        "inpage_block_ids": [_as_text(item.get("id")) for item in blocks if _as_text(item.get("id"))],
        "pages_root": _as_text(pages.get("root")),
        "endpoint_count": len(endpoints),
        "endpoint_rels": [_as_text(item.get("rel")) for item in endpoints if _as_text(item.get("rel"))],
        "endpoint_maps": endpoint_maps,
    }


def _normalize_manifest(
    manifest_payload: dict[str, Any],
    *,
    domain: str,
    label: str,
    manifest_relative_path: str,
    render_script_relative_path: str,
    frontend_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, str]], list[str]]:
    schema = _as_text(manifest_payload.get("schema"))
    issues: list[dict[str, str]] = []
    evidence: list[str] = []
    site_payload = _as_dict(manifest_payload.get("site"))
    navigation = _navigation_items(manifest_payload.get("navigation"))
    footer = _normalize_footer(manifest_payload.get("footer"))
    collections_payload = _as_dict(manifest_payload.get("collections"))
    known_collection_ids = {str(key) for key in collections_payload.keys()}
    collection_rows: list[dict[str, Any]] = []
    collection_sources: list[dict[str, Any]] = []
    for collection_id, raw_collection in collections_payload.items():
        collection_payload = _as_dict(raw_collection)
        collection_type = _as_text(collection_payload.get("type"))
        try:
            rows, sources, next_issues = _collection_source_rows(
                frontend_root=frontend_root,
                collection_id=_as_text(collection_id),
                collection_type=collection_type,
                collection_payload=collection_payload,
            )
        except ValueError as exc:
            rows = [
                {
                    "id": _as_text(collection_id),
                    "type": collection_type,
                    "source_files": [],
                    "source_count": 0,
                }
            ]
            sources = []
            next_issues = [
                _issue(
                    severity="warning",
                    code="collection_path_invalid",
                    message=str(exc),
                    context=_as_text(collection_id),
                )
            ]
        collection_rows.extend(rows)
        collection_sources.extend(sources)
        issues.extend(next_issues)

    pages_payload = _as_dict(manifest_payload.get("pages"))
    pages = _page_rows(pages_payload, known_collection_ids=known_collection_ids)
    extensions: dict[str, Any]
    if schema == "webdz.site_content.v2":
        evidence.append("Mapped webdz.site_content.v2 site shell, navigation, footer, pages, and collections into the shared read model.")
        extensions = {
            "schema": schema,
            "site_shell": _as_dict(site_payload.get("shell")),
            "stylesheets": [str(item) for item in _as_list(site_payload.get("stylesheets")) if _as_text(item)],
            "scripts": [str(item) for item in _as_list(site_payload.get("scripts")) if _as_text(item)],
        }
    elif schema == "webdz.site_content.v3":
        evidence.append("Mapped webdz.site_content.v3 site shell, icon sets, footer columns, pages, and collections into the shared read model.")
        extensions = {
            "schema": schema,
            "site_shell": _as_dict(site_payload.get("shell")),
            "icons": _as_dict(manifest_payload.get("icons")),
        }
    else:
        issues.append(
            _issue(
                severity="error",
                code="manifest_schema_unsupported",
                message="Manifest schema is unsupported by the FND-DCM normalizer.",
                context=schema or "missing",
            )
        )
        evidence.append("Manifest could not be fully normalized because the schema is unsupported.")
        extensions = {"schema": schema}

    machine_summary = _machine_surface_summary(manifest_payload)
    if machine_summary:
        extensions["machine_surface_summary"] = machine_summary
        evidence.append("Captured additive machine-surface summary under extensions.machine_surface_summary.")

    projection = {
        "site": {
            "domain": domain,
            "label": label,
            "schema": schema,
            "name": _as_text(site_payload.get("name")),
            "description": _as_text(site_payload.get("description")),
            "homepage_href": _as_text(site_payload.get("homepage_href")),
            "manifest_relative_path": manifest_relative_path,
            "render_script_relative_path": render_script_relative_path,
        },
        "navigation": navigation,
        "footer": footer,
        "pages": pages,
        "collections": collection_rows,
        "issues": issues,
        "extensions": extensions,
    }
    return projection, collection_sources, issues, evidence


class FilesystemFndDcmReadOnlyAdapter(FndDcmReadOnlyPort):
    def __init__(
        self,
        private_dir: str | Path | None,
        *,
        webapps_root: str | Path | None = None,
    ) -> None:
        self._private_dir = Path(private_dir) if private_dir is not None else None
        self._webapps_root = Path(webapps_root) if webapps_root is not None else DEFAULT_WEBAPPS_ROOT

    def _tool_root(self) -> Path | None:
        if self._private_dir is None:
            return None
        return self._private_dir / "utilities" / "tools" / "fnd-dcm"

    def _profile_paths(self) -> Iterable[Path]:
        tool_root = self._tool_root()
        if tool_root is None or not tool_root.exists() or not tool_root.is_dir():
            return ()
        return sorted(tool_root.glob("fnd-dcm.*.json"))

    def read_fnd_dcm_read_only(self, request: FndDcmReadOnlyRequest) -> FndDcmReadOnlyResult:
        profiles: list[dict[str, Any]] = []
        warnings: list[str] = []
        for profile_path in self._profile_paths():
            payload = _safe_json_object(profile_path)
            schema = _as_text(payload.get("schema"))
            if schema != FND_DCM_PROFILE_SCHEMA:
                warnings.append(f"Skipping unsupported FND-DCM profile schema in {profile_path.name}")
                continue
            try:
                domain = _normalize_domain(payload.get("domain"))
            except ValueError:
                warnings.append(f"Skipping invalid FND-DCM profile domain in {profile_path.name}")
                continue
            label = _as_text(payload.get("label")) or domain
            manifest_relative_path = _as_text(payload.get("manifest_relative_path"))
            render_script_relative_path = _as_text(payload.get("render_script_relative_path"))
            frontend_root = self._webapps_root / "clients" / domain / "frontend"
            issues: list[dict[str, str]] = []
            normalization_evidence: list[str] = []
            try:
                manifest_path = _resolve_relative_path(
                    frontend_root,
                    manifest_relative_path,
                    field_name="manifest_relative_path",
                )
            except ValueError as exc:
                manifest_path = frontend_root / _as_text(manifest_relative_path)
                issues.append(
                    _issue(
                        severity="error",
                        code="manifest_path_invalid",
                        message=str(exc),
                        path=str(manifest_path),
                        context=domain,
                    )
                )
            try:
                render_script_path = _resolve_relative_path(
                    frontend_root,
                    render_script_relative_path,
                    field_name="render_script_relative_path",
                )
            except ValueError as exc:
                render_script_path = frontend_root / _as_text(render_script_relative_path)
                issues.append(
                    _issue(
                        severity="error",
                        code="render_script_path_invalid",
                        message=str(exc),
                        path=str(render_script_path),
                        context=domain,
                    )
                )

            raw_manifest = _safe_json_object(manifest_path)
            if not raw_manifest:
                issues.append(
                    _issue(
                        severity="warning",
                        code="manifest_missing",
                        message="Manifest file is missing or unreadable.",
                        path=str(manifest_path),
                        context=domain,
                    )
                )
                projection = {
                    "site": {
                        "domain": domain,
                        "label": label,
                        "schema": "",
                        "name": "",
                        "description": "",
                        "homepage_href": "",
                        "manifest_relative_path": manifest_relative_path,
                        "render_script_relative_path": render_script_relative_path,
                    },
                    "navigation": [],
                    "footer": {"copyright": "", "column_count": 0, "column_templates": []},
                    "pages": [],
                    "collections": [],
                    "issues": list(issues),
                    "extensions": {},
                }
                collection_sources = []
                normalization_evidence.append("Manifest projection is empty because the manifest file could not be loaded.")
            else:
                projection, collection_sources, next_issues, next_evidence = _normalize_manifest(
                    raw_manifest,
                    domain=domain,
                    label=label,
                    manifest_relative_path=manifest_relative_path,
                    render_script_relative_path=render_script_relative_path,
                    frontend_root=frontend_root,
                )
                issues.extend(next_issues)
                normalization_evidence.extend(next_evidence)

            if not render_script_path.exists() or not render_script_path.is_file():
                issues.append(
                    _issue(
                        severity="warning",
                        code="render_script_missing",
                        message="Render script is missing or unreadable.",
                        path=str(render_script_path),
                        context=domain,
                    )
                )

            profiles.append(
                {
                    "schema": schema,
                    "domain": domain,
                    "label": label,
                    "profile_file": str(profile_path),
                    "frontend_root": str(frontend_root),
                    "manifest_relative_path": manifest_relative_path,
                    "render_script_relative_path": render_script_relative_path,
                    "manifest_path": str(manifest_path),
                    "render_script_path": str(render_script_path),
                    "manifest_schema": _as_text(projection.get("site", {}).get("schema")),
                    "raw_manifest": raw_manifest,
                    "projection": projection,
                    "collection_sources": collection_sources,
                    "normalization_evidence": normalization_evidence,
                    "issues": issues,
                    "warnings": [
                        _as_text(issue.get("message"))
                        for issue in issues
                        if _as_text(issue.get("severity")).lower() == "warning"
                    ],
                }
            )

        profiles.sort(key=lambda item: (0 if item.get("domain") == request.site else 1, _as_text(item.get("label")).lower()))
        payload = {
            "portal_tenant_id": request.portal_tenant_id,
            "profiles": profiles,
            "warnings": warnings,
        }
        return FndDcmReadOnlyResult(source=FndDcmReadOnlySource(payload=payload))
