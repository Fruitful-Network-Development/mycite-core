"""
Tool sandbox session — runtime owner for tool-local workspace behavior.

This module is the **service boundary** for tool sandbox sessions: not a plain
data class. Sessions **stage** edits only; canonical anthology and local
resource stores are updated only through **promotion** via shared lifecycle
paths (LocalResourceLifecycleService + optional anthology hooks).

**Ownership (frozen):**

Inside the session:
  - Declared resources (loaded snapshots), declared anthology datum refs,
    config-derived inputs, staged rows/resources, understanding + RulePolicy
    reports, promotion targets (last computed), warnings/errors.

Outside the session (must NOT be owned here):
  - Contract / MSS compilation authority, Data Tool anthology authority,
    ad hoc route-local semantics, direct tool-local file persistence.

Contract authority and MSS compilation remain outside this module by design.
"""

from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from _shared.portal.data_engine.rules import understand_datums
from _shared.portal.data_engine.rules.base import parse_datum_id
from _shared.portal.data_engine.rules.write_evaluation import (
    evaluate_probe_write,
    evaluate_resource_payload_write,
    extract_rows_payload_from_resource_body,
)
from _shared.portal.sandbox.local_resource_lifecycle import LocalResourceLifecycleService
from _shared.portal.sandbox.workspace_contract import ToolSandboxDeclaration


def _utc_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _deepcopy_jsonish(obj: Any) -> Any:
    try:
        return copy.deepcopy(obj)
    except Exception:
        return obj


def _row_id_key(row: Mapping[str, Any]) -> str:
    return str(row.get("id") or row.get("row_id") or row.get("identifier") or "").strip()


def _normalize_canonical_rows_list(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Normalize ``get_canonical_rows_payload()`` (dict or list rows) to a row list."""
    rows = payload.get("rows") if isinstance(payload, dict) else None
    out: list[dict[str, Any]] = []
    if isinstance(rows, dict):
        for rid, row in rows.items():
            if not isinstance(row, dict):
                continue
            r = dict(row)
            token = str(rid or "").strip()
            if token:
                r.setdefault("id", token)
                r.setdefault("row_id", str(r.get("row_id") or token))
                r.setdefault("identifier", str(r.get("identifier") or token))
            out.append(r)
        return out
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                r = dict(row)
                token = _row_id_key(r)
                if token:
                    r.setdefault("id", token)
                    r.setdefault("row_id", str(r.get("row_id") or token))
                    r.setdefault("identifier", str(r.get("identifier") or token))
                out.append(r)
    return out


def _row_by_id(rows: Sequence[Mapping[str, Any]], row_id: str) -> dict[str, Any] | None:
    rid = str(row_id or "").strip()
    if not rid:
        return None
    for row in rows:
        if _row_id_key(row) == rid:
            return dict(row)
    return None


def _rows_payload_dict_for_probe(base_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for r in base_rows:
        rid = _row_id_key(r)
        if rid:
            rows[rid] = dict(r)
    return {"rows": rows}


def _merge_rows_for_understanding(
    *,
    base_rows: list[dict[str, Any]],
    overrides: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply overrides by row id; keep other base rows."""
    by_id: dict[str, dict[str, Any]] = {}
    for r in base_rows:
        k = _row_id_key(r)
        if k:
            by_id[k] = dict(r)
    for rid, snap in overrides.items():
        rid_s = str(rid or "").strip()
        if not rid_s or not isinstance(snap, dict):
            continue
        merged = dict(by_id.get(rid_s, {}))
        merged.update(snap)
        merged["id"] = rid_s
        merged["row_id"] = str(merged.get("row_id") or rid_s)
        merged["identifier"] = str(merged.get("identifier") or rid_s)
        by_id[rid_s] = merged
    return list(by_id.values())


@dataclass
class ToolSandboxRuntimeDeps:
    """Injected dependencies for opening a session (no Flask globals)."""

    data_root: Path
    sandbox_engine: Any
    local_resource_service: LocalResourceLifecycleService
    get_active_config: Callable[[], Mapping[str, Any]]
    get_canonical_rows_payload: Callable[[], Mapping[str, Any]]
    get_path: Callable[[Mapping[str, Any], str], Any]


@dataclass
class ToolSandboxPromotionHooks:
    """
    Flavor/workspace hooks for promoting staged **anthology** rows.
    Resources always promote via LocalResourceLifecycleService.
    """

    update_anthology_row: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None
    """(datum_id, row_snapshot) -> {ok, errors, warnings, ...}"""


@dataclass
class ToolSandboxSession:
    """
    Runtime session: staging workspace for a tool. Not a canonical store.
    """

    session_id: str
    tool_key: str
    declaration: ToolSandboxDeclaration
    loaded_resources: dict[str, Any] = field(default_factory=dict)
    loaded_anthology_refs: dict[str, Any] = field(default_factory=dict)
    loaded_config_inputs: dict[str, Any] = field(default_factory=dict)
    staged_resources: dict[str, Any] = field(default_factory=dict)
    staged_anthology_rows: dict[str, dict[str, Any]] = field(default_factory=dict)
    working_resources: dict[str, Any] = field(default_factory=dict)
    working_anthology_rows: dict[str, dict[str, Any]] = field(default_factory=dict)
    datum_understanding: dict[str, Any] = field(default_factory=dict)
    rule_policy: dict[str, Any] = field(default_factory=dict)
    promotion_targets: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_ts)
    updated_at: str = field(default_factory=_utc_ts)
    _canonical_rows_snapshot: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _local_resource: LocalResourceLifecycleService | None = field(default=None, init=False, repr=False)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema": "mycite.portal.sandbox.tool_session.v1",
            "session_id": self.session_id,
            "tool_key": self.tool_key,
            "declaration": dict(self.declaration),
            "loaded_resources": {k: _deepcopy_jsonish(v) for k, v in self.loaded_resources.items()},
            "loaded_anthology_refs": {k: _deepcopy_jsonish(v) for k, v in self.loaded_anthology_refs.items()},
            "loaded_config_inputs": _deepcopy_jsonish(self.loaded_config_inputs),
            "staged_resources": list(self.staged_resources.keys()),
            # Anthology-shaped staged rows (alias: staged_rows) — same keys as staged_anthology_rows.
            "staged_anthology_rows": list(self.staged_anthology_rows.keys()),
            "staged_rows": list(self.staged_anthology_rows.keys()),
            "working_resources": {k: _deepcopy_jsonish(v) for k, v in self.working_resources.items()},
            "working_anthology_rows": {k: _deepcopy_jsonish(v) for k, v in self.working_anthology_rows.items()},
            "datum_understanding": _deepcopy_jsonish(self.datum_understanding),
            "rule_policy": dict(self.rule_policy),
            "promotion_targets": _deepcopy_jsonish(self.promotion_targets),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def _touch(self) -> None:
        self.updated_at = _utc_ts()

    def refresh_canonical_snapshot(self, deps: ToolSandboxRuntimeDeps) -> None:
        """Reload anthology row snapshot from ``deps`` (e.g. after external anthology edits)."""
        canonical = deps.get_canonical_rows_payload()
        self._canonical_rows_snapshot = copy.deepcopy(
            _normalize_canonical_rows_list(canonical if isinstance(canonical, Mapping) else {})
        )
        # Re-bind declared anthology refs; keep working/staged overlays for ids still declared.
        for did in list(self.declaration.get("consumes_anthology_datum_ids") or []):
            ds = str(did or "").strip()
            if not ds:
                continue
            row = _row_by_id(self._canonical_rows_snapshot, ds)
            if row is None:
                self.warnings.append(f"refresh: anthology datum id not found: {ds}")
                self.loaded_anthology_refs.pop(ds, None)
            else:
                snap = _deepcopy_jsonish(row)
                self.loaded_anthology_refs[ds] = snap
                if ds not in self.staged_anthology_rows:
                    self.working_anthology_rows[ds] = snap
        self._touch()
        self.recompute_understanding()
        self.build_promotion_targets()

    def stage_resource(self, resource_id: str, body: Mapping[str, Any]) -> None:
        rid = str(resource_id or "").strip()
        if not rid:
            self.errors.append("stage_resource: resource_id is required")
            return
        self.staged_resources[rid] = dict(body)
        self.working_resources[rid] = _deepcopy_jsonish(dict(body))
        self._touch()
        self.recompute_understanding()

    def stage_anthology_row(self, datum_id: str, row: Mapping[str, Any]) -> None:
        did = str(datum_id or "").strip()
        if not did:
            self.errors.append("stage_anthology_row: datum_id is required")
            return
        self.staged_anthology_rows[did] = dict(row)
        self.working_anthology_rows[did] = _deepcopy_jsonish(dict(row))
        self._touch()
        self.recompute_understanding()

    def recompute_understanding(self) -> None:
        self.warnings = [w for w in self.warnings if not str(w).startswith("understanding:")]
        rows_for_ud: list[dict[str, Any]] = _merge_rows_for_understanding(
            base_rows=list(self._canonical_rows_snapshot),
            overrides=self.working_anthology_rows,
        )
        consumed = list(self.declaration.get("consumes_anthology_datum_ids") or [])
        if consumed:
            allow = {str(x).strip() for x in consumed if str(x).strip()}
            rows_for_ud = [r for r in rows_for_ud if _row_id_key(r) in allow]
        elif self.working_anthology_rows:
            allow = {str(x).strip() for x in self.working_anthology_rows if str(x).strip()}
            rows_for_ud = [r for r in rows_for_ud if _row_id_key(r) in allow]
        else:
            rows_for_ud = []
        try:
            ud = understand_datums({"rows": rows_for_ud})
            self.datum_understanding = ud.to_dict() if hasattr(ud, "to_dict") else {}
        except Exception as exc:
            self.datum_understanding = {}
            self.warnings.append(f"understanding: anthology slice failed: {exc}")

        for rid, body in self.working_resources.items():
            res_rows = extract_rows_payload_from_resource_body(body if isinstance(body, dict) else {})
            if not res_rows:
                continue
            try:
                rp = extract_rows_payload_from_resource_body(body if isinstance(body, dict) else {})
                if rp is None:
                    continue
                eval_res = evaluate_resource_payload_write(rp, rule_write_override=False)
                prefix = f"resource:{rid}"
                if not eval_res.get("ok"):
                    for e in eval_res.get("errors") or []:
                        self.warnings.append(f"understanding:{prefix}: {e}")
                for w in eval_res.get("warnings") or []:
                    self.warnings.append(f"understanding:{prefix}: {w}")
            except Exception as exc:
                self.warnings.append(f"understanding:{rid}: {exc}")

        self.rule_policy = {
            "version": "v2",
            "ambiguous_unknown_writable": True,
            "invalid_blocked_by_default": True,
        }
        self._touch()

    def build_promotion_targets(self) -> dict[str, Any]:
        targets: dict[str, Any] = {
            "resources": sorted(self.staged_resources.keys()),
            "anthology_rows": sorted(self.staged_anthology_rows.keys()),
        }
        self.promotion_targets = targets
        self._touch()
        return targets

    def promote(
        self,
        *,
        hooks: ToolSandboxPromotionHooks | None = None,
        rule_write_override: bool = False,
        rule_write_override_reason: str = "",
    ) -> dict[str, Any]:
        """
        Persist staged content via local resource lifecycle and optional anthology hooks.
        Recomputes understanding/policy immediately before promotion.
        """
        self.recompute_understanding()
        self.build_promotion_targets()
        hooks = hooks or ToolSandboxPromotionHooks()
        if rule_write_override and not str(rule_write_override_reason or "").strip():
            self.warnings.append("rule_write_override used without rule_write_override_reason")

        out: dict[str, Any] = {
            "ok": True,
            "schema": "mycite.portal.sandbox.tool_session.promote.v1",
            "session_id": self.session_id,
            "saved_resources": [],
            "saved_anthology_rows": [],
            "errors": [],
            "warnings": list(self.warnings),
        }

        # Block on invalid graph state for staged resource row payloads
        for rid, body in self.staged_resources.items():
            if not isinstance(body, dict):
                out["errors"].append(f"resource {rid}: payload must be an object")
                continue
            res_rows = extract_rows_payload_from_resource_body(body)
            if res_rows is not None:
                ev = evaluate_resource_payload_write(res_rows, rule_write_override=bool(rule_write_override))
                if not ev.get("ok") and not rule_write_override:
                    out["ok"] = False
                    out["errors"].extend([f"resource {rid}: {e}" for e in (ev.get("errors") or [])])
                    continue
                out["warnings"].extend([f"resource {rid}: {w}" for w in (ev.get("warnings") or [])])

        # Anthology staged rows: probe vs canonical
        for did, row in self.staged_anthology_rows.items():
            if not isinstance(row, dict):
                out["errors"].append(f"anthology {did}: row must be an object")
                out["ok"] = False
                continue
            probe_row = dict(row)
            probe_row.setdefault("row_id", did)
            probe_row.setdefault("identifier", did)
            _, vg_hint, _ = parse_datum_id(did)
            base_payload = _rows_payload_dict_for_probe(self._canonical_rows_snapshot)
            probe = evaluate_probe_write(
                base_payload,
                probe_row_id=did,
                probe_row_dict=probe_row,
                rule_write_override=bool(rule_write_override),
                value_group_hint=vg_hint,
            )
            if not probe.get("ok") and not rule_write_override:
                out["ok"] = False
                out["errors"].extend([f"anthology {did}: {e}" for e in (probe.get("errors") or [])])
                continue
            out["warnings"].extend([f"anthology {did}: {w}" for w in (probe.get("warnings") or [])])

        if not out["ok"]:
            self.errors.extend(out["errors"])
            self._touch()
            return out

        if self._local_resource is None:
            out["ok"] = False
            out["errors"].append("local resource lifecycle service is not bound on this session")
            self._touch()
            return out

        # Persist resources
        for rid, body in self.staged_resources.items():
            try:
                saved = self._local_resource.update(resource_id=rid, payload=body if isinstance(body, dict) else {})
                out["saved_resources"].append({"resource_id": rid, "result": saved})
            except Exception as exc:
                out["ok"] = False
                out["errors"].append(f"resource {rid}: persist failed: {exc}")

        # Persist anthology rows
        if self.staged_anthology_rows and hooks.update_anthology_row is None:
            out["ok"] = False
            out["errors"].append("anthology promotion hook not configured but staged anthology rows present")
        elif hooks.update_anthology_row:
            for did, row in self.staged_anthology_rows.items():
                try:
                    res = hooks.update_anthology_row(did, dict(row))
                    out["saved_anthology_rows"].append({"datum_id": did, "result": res})
                    if isinstance(res, dict) and res.get("ok") is False:
                        errs = res.get("errors") or []
                        out["errors"].extend([f"anthology {did}: {e}" for e in errs])
                        out["ok"] = False
                except Exception as exc:
                    out["ok"] = False
                    out["errors"].append(f"anthology {did}: {exc}")

        if out["ok"]:
            self.staged_resources.clear()
            self.staged_anthology_rows.clear()
        self._touch()
        return out


class ToolSandboxSessionManager:
    """Registry of open sessions (in-process). Routes or tools may share one manager per app."""

    def __init__(self) -> None:
        self._sessions: dict[str, ToolSandboxSession] = {}

    def open_session(
        self,
        deps: ToolSandboxRuntimeDeps,
        *,
        tool_key: str,
        declaration: ToolSandboxDeclaration,
        session_id: str | None = None,
        initial_context: Mapping[str, Any] | None = None,
    ) -> ToolSandboxSession:
        sid = str(session_id or "").strip() or str(uuid.uuid4())
        decl_tool = str(declaration.get("tool_id") or "").strip()
        if decl_tool and decl_tool != str(tool_key).strip():
            raise ValueError(f"declaration.tool_id {decl_tool!r} does not match tool_key {tool_key!r}")

        canonical = deps.get_canonical_rows_payload()
        canon_rows = _normalize_canonical_rows_list(canonical if isinstance(canonical, Mapping) else {})

        sess = ToolSandboxSession(
            session_id=sid,
            tool_key=str(tool_key).strip(),
            declaration=dict(declaration),
            _canonical_rows_snapshot=copy.deepcopy(canon_rows),
        )
        sess._local_resource = deps.local_resource_service

        cfg = deps.get_active_config()
        if not isinstance(cfg, Mapping):
            cfg = {}

        # Config-derived inputs (dotted paths)
        for path in declaration.get("config_coordinate_paths") or []:
            p = str(path or "").strip()
            if not p:
                continue
            try:
                sess.loaded_config_inputs[p] = deps.get_path(cfg, p)
            except Exception as exc:
                sess.warnings.append(f"config path {p!r}: {exc}")

        if initial_context:
            sess.loaded_config_inputs["tool_context"] = _deepcopy_jsonish(dict(initial_context))

        # Required / optional resources
        for spec in declaration.get("required_resources") or []:
            if not isinstance(spec, dict):
                sess.errors.append("required_resources entry must be an object")
                continue
            rid = str(spec.get("resource_id") or "").strip()
            if not rid:
                sess.errors.append("required_resources: resource_id is required")
                continue
            snap = deps.sandbox_engine.get_resource(rid)
            if bool(snap.get("missing")):
                sess.errors.append(f"required resource missing in sandbox: {rid}")
            else:
                body = snap.get("resource") if isinstance(snap.get("resource"), dict) else snap
                sess.loaded_resources[rid] = _deepcopy_jsonish(body)
                sess.working_resources[rid] = _deepcopy_jsonish(body)

        for spec in declaration.get("optional_resources") or []:
            if not isinstance(spec, dict):
                continue
            rid = str(spec.get("resource_id") or "").strip()
            if not rid:
                continue
            snap = deps.sandbox_engine.get_resource(rid)
            if bool(snap.get("missing")):
                sess.warnings.append(f"optional resource not present: {rid}")
            else:
                body = snap.get("resource") if isinstance(snap.get("resource"), dict) else snap
                sess.loaded_resources[rid] = _deepcopy_jsonish(body)
                sess.working_resources[rid] = _deepcopy_jsonish(body)

        for path in declaration.get("optional_sandbox_resource_id_paths") or []:
            p = str(path or "").strip()
            if not p:
                continue
            try:
                rid = str(deps.get_path(cfg, p) or "").strip()
            except Exception as exc:
                sess.warnings.append(f"optional_sandbox_resource_id_paths {p!r}: {exc}")
                continue
            if not rid:
                sess.warnings.append(f"optional sandbox resource id empty at config path: {p}")
                continue
            snap = deps.sandbox_engine.get_resource(rid)
            if bool(snap.get("missing")):
                sess.warnings.append(f"optional resource not present: {rid} (from {p})")
            else:
                body = snap.get("resource") if isinstance(snap.get("resource"), dict) else snap
                sess.loaded_resources[rid] = _deepcopy_jsonish(body)
                sess.working_resources[rid] = _deepcopy_jsonish(body)

        # Anthology datum refs declared by id
        for did in declaration.get("consumes_anthology_datum_ids") or []:
            ds = str(did or "").strip()
            if not ds:
                continue
            row = _row_by_id(canon_rows, ds)
            if row is None:
                sess.warnings.append(f"anthology datum id not found in canonical context: {ds}")
            else:
                snap = _deepcopy_jsonish(row)
                sess.loaded_anthology_refs[ds] = snap
                sess.working_anthology_rows[ds] = snap

        sess.recompute_understanding()
        sess.build_promotion_targets()
        self._sessions[sid] = sess
        return sess

    def get(self, session_id: str) -> ToolSandboxSession | None:
        return self._sessions.get(str(session_id or "").strip())

    def reopen_session(
        self,
        deps: ToolSandboxRuntimeDeps,
        *,
        session_id: str,
        tool_key: str,
        declaration: ToolSandboxDeclaration,
        initial_context: Mapping[str, Any] | None = None,
    ) -> ToolSandboxSession:
        """
        Replace an existing session id with a fresh load (same id), or open if missing.

        Use when the tool needs to **reload** declared resources/refs from disk/canonical
        state without minting a new session id.
        """
        sid = str(session_id or "").strip()
        if not sid:
            raise ValueError("session_id is required for reopen_session")
        self.close(sid)
        return self.open_session(
            deps,
            tool_key=tool_key,
            declaration=declaration,
            session_id=sid,
            initial_context=initial_context,
        )

    def close(self, session_id: str) -> bool:
        sid = str(session_id or "").strip()
        if sid in self._sessions:
            del self._sessions[sid]
            return True
        return False
