from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class WorkbenchSandboxSessionService:
    manager_factory: Callable[[], Any]
    runtime_deps_factory: Callable[[], Any]
    declaration_resolver: Callable[[str, Any], dict[str, Any]]
    promotion_hooks_factory: Callable[[], Any]

    def open(self, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        tool_key = str(body.get("tool_key") or body.get("tool_id") or "").strip()
        if not tool_key:
            return {"ok": False, "error": "tool_key is required"}, 400
        declaration = self.declaration_resolver(tool_key, body.get("declaration"))
        initial_context = body.get("initial_context") if isinstance(body.get("initial_context"), dict) else None
        session_id = str(body.get("session_id") or "").strip() or None
        reopen = bool(body.get("reopen"))
        try:
            manager = self.manager_factory()
            if reopen and session_id:
                session = manager.reopen_session(
                    self.runtime_deps_factory(),
                    session_id=session_id,
                    tool_key=tool_key,
                    declaration=declaration,
                    initial_context=initial_context,
                )
            else:
                session = manager.open_session(
                    self.runtime_deps_factory(),
                    tool_key=tool_key,
                    declaration=declaration,
                    session_id=session_id,
                    initial_context=initial_context,
                )
        except ValueError as exc:
            return {"ok": False, "error": str(exc), "schema": "mycite.portal.sandbox.tool_session.open.v1"}, 400
        out = session.to_public_dict()
        out["ok"] = not bool(session.errors)
        return out, (200 if out["ok"] else 400)

    def get(self, session_id: str) -> tuple[dict[str, Any], int]:
        session = self.manager_factory().get(session_id)
        if session is None:
            return {"ok": False, "error": "session not found", "schema": "mycite.portal.sandbox.tool_session.get.v1"}, 404
        out = session.to_public_dict()
        out["ok"] = True
        return out, 200

    def stage(self, session_id: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        session = self.manager_factory().get(session_id)
        if session is None:
            return {"ok": False, "error": "session not found"}, 404
        resources = body.get("resources") if isinstance(body.get("resources"), dict) else {}
        anthology_rows = body.get("anthology_rows") if isinstance(body.get("anthology_rows"), dict) else {}
        if not anthology_rows and isinstance(body.get("staged_rows"), dict):
            anthology_rows = body.get("staged_rows") or {}
        for resource_id, payload in resources.items():
            if isinstance(payload, dict):
                session.stage_resource(str(resource_id), payload)
        for datum_id, row in anthology_rows.items():
            if isinstance(row, dict):
                session.stage_anthology_row(str(datum_id), row)
        out = session.to_public_dict()
        out["ok"] = True
        return out, 200

    def promote(self, session_id: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        session = self.manager_factory().get(session_id)
        if session is None:
            return {"ok": False, "error": "session not found"}, 404
        override = bool(body.get("rule_write_override"))
        reason = str(body.get("rule_write_override_reason") or "").strip()
        promotion = session.promote(
            hooks=self.promotion_hooks_factory(),
            rule_write_override=override,
            rule_write_override_reason=reason,
        )
        if override and not reason:
            promotion.setdefault("warnings", []).append("rule_write_override used without rule_write_override_reason")
        promotion["session"] = session.to_public_dict()
        return promotion, (200 if bool(promotion.get("ok")) else 400)

    def close(self, session_id: str) -> tuple[dict[str, Any], int]:
        closed = self.manager_factory().close(session_id)
        return {"ok": bool(closed), "schema": "mycite.portal.sandbox.tool_session.close.v1"}, 200

    def refresh(self, session_id: str) -> tuple[dict[str, Any], int]:
        session = self.manager_factory().get(session_id)
        if session is None:
            return {
                "ok": False,
                "error": "session not found",
                "schema": "mycite.portal.sandbox.tool_session.refresh.v1",
            }, 404
        session.refresh_canonical_snapshot(self.runtime_deps_factory())
        out = session.to_public_dict()
        out["ok"] = True
        return out, 200

    def understanding(self, session_id: str) -> tuple[dict[str, Any], int]:
        session = self.manager_factory().get(session_id)
        if session is None:
            return {
                "ok": False,
                "error": "session not found",
                "schema": "mycite.portal.sandbox.tool_session.understanding.v1",
            }, 404
        session.recompute_understanding()
        session.build_promotion_targets()
        return {
            "ok": True,
            "schema": "mycite.portal.sandbox.tool_session.understanding.v1",
            "session_id": session.session_id,
            "datum_understanding": session.datum_understanding,
            "rule_policy": session.rule_policy,
            "warnings": list(session.warnings),
            "promotion_targets": session.promotion_targets,
        }, 200
