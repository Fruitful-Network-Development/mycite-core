from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from flask import Flask

    HAS_FLASK = True
except ModuleNotFoundError:  # pragma: no cover
    HAS_FLASK = False
    Flask = None  # type: ignore[assignment]

from _shared.portal.data_engine.profile_config_refs import get_path
from _shared.portal.sandbox import LocalResourceLifecycleService, SandboxEngine
from _shared.portal.sandbox.tool_sandbox_session import (
    ToolSandboxPromotionHooks,
    ToolSandboxRuntimeDeps,
    ToolSandboxSessionManager,
)
from _shared.portal.sandbox.workspace_contract import AGRO_ERP_SANDBOX_DECLARATION


def _load_register_data_routes():
    import importlib.util

    path = (
        Path(__file__).resolve().parents[1]
        / "portals"
        / "_shared"
        / "portal"
        / "api"
        / "data_workspace.py"
    )
    portals_root = path.parents[4]
    token = str(portals_root)
    if token not in __import__("sys").path:
        __import__("sys").path.insert(0, token)
    spec = importlib.util.spec_from_file_location("data_workspace_tool_session_tests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.register_data_routes


class _WorkspaceStub:
    def __init__(self, *, data_dir: str) -> None:
        self.storage = type("StorageStub", (), {"data_dir": data_dir})()

    def list_tables(self):
        return []

    def get_state_snapshot(self):
        return {}

    def update_anthology_profile(self, **kwargs):
        return {"ok": True, "errors": [], "warnings": [], "kwargs": kwargs}


class ToolSandboxSessionServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "sandbox" / "resources").mkdir(parents=True, exist_ok=True)
        self.engine = SandboxEngine(data_root=self.root)
        self.lr = LocalResourceLifecycleService(data_root=self.root, sandbox_engine=self.engine)
        self.mgr = ToolSandboxSessionManager()

    def tearDown(self):
        self.tmp.cleanup()

    def _deps(self, *, cfg=None, rows=None):
        cfg = cfg if cfg is not None else {}
        rows = rows if rows is not None else {"rows": {}}
        return ToolSandboxRuntimeDeps(
            data_root=self.root,
            sandbox_engine=self.engine,
            local_resource_service=self.lr,
            get_active_config=lambda: cfg,
            get_canonical_rows_payload=lambda: rows,
            get_path=get_path,
        )

    def test_open_stage_promote_resource(self):
        self.engine.save_resource("preloaded", {"resource_id": "preloaded", "note": "seed"})
        decl = {"tool_id": "t1", "required_resources": [{"resource_id": "preloaded", "required": True}]}
        sess = self.mgr.open_session(self._deps(), tool_key="t1", declaration=decl)  # type: ignore[arg-type]
        self.assertFalse(sess.errors)
        sess.stage_resource("preloaded", {"resource_id": "preloaded", "note": "updated"})
        prom = sess.promote(hooks=ToolSandboxPromotionHooks())
        self.assertTrue(prom.get("ok"))
        reread = self.engine.get_resource("preloaded")
        self.assertFalse(bool(reread.get("missing")))
        self.assertEqual(reread.get("note"), "updated")

    def test_required_resource_missing_records_error(self):
        decl = {"tool_id": "t1", "required_resources": [{"resource_id": "nope", "required": True}]}
        sess = self.mgr.open_session(self._deps(), tool_key="t1", declaration=decl)  # type: ignore[arg-type]
        self.assertTrue(any("nope" in e for e in sess.errors))

    def test_config_coordinate_paths_in_loaded_config_inputs(self):
        decl = {
            "tool_id": "t1",
            "config_coordinate_paths": ["agro.inherited.product_profile_ref"],
        }
        cfg = {"agro": {"inherited": {"product_profile_ref": "8-5-11"}}}
        sess = self.mgr.open_session(self._deps(cfg=cfg), tool_key="t1", declaration=decl)  # type: ignore[arg-type]
        self.assertEqual(sess.loaded_config_inputs.get("agro.inherited.product_profile_ref"), "8-5-11")

    def test_consumes_anthology_datum_ids_load_refs(self):
        rows = {
            "rows": {
                "1-1-1": {
                    "row_id": "1-1-1",
                    "identifier": "1-1-1",
                    "label": "L",
                    "pairs": [{"reference": "2-1-1", "magnitude": "1"}],
                    "reference": "2-1-1",
                    "magnitude": "1",
                }
            }
        }
        decl = {"tool_id": "t1", "consumes_anthology_datum_ids": ["1-1-1"]}
        sess = self.mgr.open_session(self._deps(rows=rows), tool_key="t1", declaration=decl)  # type: ignore[arg-type]
        self.assertIn("1-1-1", sess.loaded_anthology_refs)

    def test_anthology_promote_invokes_hook_with_override(self):
        rows = {
            "rows": {
                "1-1-1": {
                    "row_id": "1-1-1",
                    "identifier": "1-1-1",
                    "label": "L",
                    "pairs": [{"reference": "2-1-1", "magnitude": "1"}],
                    "reference": "2-1-1",
                    "magnitude": "1",
                }
            }
        }
        decl = {"tool_id": "t1", "consumes_anthology_datum_ids": ["1-1-1"]}
        sess = self.mgr.open_session(self._deps(rows=rows), tool_key="t1", declaration=decl)  # type: ignore[arg-type]
        updated = dict(sess.working_anthology_rows["1-1-1"])
        updated["label"] = "L2"
        sess.stage_anthology_row("1-1-1", updated)
        called: list[tuple[str, str]] = []

        def hook(did: str, row: dict):
            called.append((did, str(row.get("label") or "")))
            return {"ok": True, "errors": [], "warnings": []}

        prom = sess.promote(
            hooks=ToolSandboxPromotionHooks(update_anthology_row=hook),
            rule_write_override=True,
            rule_write_override_reason="unit test",
        )
        self.assertTrue(prom.get("ok"))
        self.assertEqual(called[0][1], "L2")

    def test_agro_declaration_tool_id_matches(self):
        decl = dict(AGRO_ERP_SANDBOX_DECLARATION)
        sess = self.mgr.open_session(self._deps(), tool_key="agro_erp", declaration=decl)  # type: ignore[arg-type]
        self.assertEqual(sess.tool_key, "agro_erp")
        self.assertFalse(sess.errors)

    def test_reopen_session_reloads_resource_from_disk(self):
        self.engine.save_resource("r1", {"resource_id": "r1", "version": 1})
        decl = {"tool_id": "t1", "required_resources": [{"resource_id": "r1", "required": True}]}
        deps = self._deps()
        s1 = self.mgr.open_session(deps, tool_key="t1", declaration=decl, session_id="session-stable")  # type: ignore[arg-type]
        self.assertEqual(s1.loaded_resources.get("r1", {}).get("version"), 1)
        self.engine.save_resource("r1", {"resource_id": "r1", "version": 2})
        s2 = self.mgr.reopen_session(
            deps,
            session_id="session-stable",
            tool_key="t1",
            declaration=decl,  # type: ignore[arg-type]
        )
        self.assertEqual(s2.session_id, "session-stable")
        self.assertEqual(s2.loaded_resources.get("r1", {}).get("version"), 2)

    def test_refresh_canonical_snapshot_updates_rows(self):
        rows = {
            "rows": {
                "9-9-9": {
                    "row_id": "9-9-9",
                    "identifier": "9-9-9",
                    "label": "L",
                    "pairs": [{"reference": "2-1-1", "magnitude": "1"}],
                    "reference": "2-1-1",
                    "magnitude": "1",
                }
            }
        }
        decl = {"tool_id": "t1", "consumes_anthology_datum_ids": ["9-9-9"]}
        deps = self._deps(rows=rows)
        sess = self.mgr.open_session(deps, tool_key="t1", declaration=decl)  # type: ignore[arg-type]
        self.assertIn("9-9-9", sess.loaded_anthology_refs)
        rows2 = {
            "rows": {
                "9-9-9": {
                    "row_id": "9-9-9",
                    "identifier": "9-9-9",
                    "label": "L2",
                    "pairs": [{"reference": "2-1-1", "magnitude": "1"}],
                    "reference": "2-1-1",
                    "magnitude": "1",
                }
            }
        }
        sess.refresh_canonical_snapshot(
            ToolSandboxRuntimeDeps(
                data_root=self.root,
                sandbox_engine=self.engine,
                local_resource_service=self.lr,
                get_active_config=lambda: {},
                get_canonical_rows_payload=lambda: rows2,
                get_path=get_path,
            )
        )
        self.assertEqual(sess.loaded_anthology_refs.get("9-9-9", {}).get("label"), "L2")

    def test_staged_tool_config_write_promotes_via_hook(self):
        decl = {"tool_id": "t1"}
        sess = self.mgr.open_session(self._deps(), tool_key="t1", declaration=decl)  # type: ignore[arg-type]
        preview = {
            "ok": True,
            "intent": {},
            "validation": {},
            "plan": {},
            "config_updates": [],
            "write_actions": [],
            "warnings": [],
            "errors": [],
        }
        sess.stage_tool_config_write(
            "inherited_product_profile_ref",
            {"write_preview": preview, "resource_ref": "sandbox:txa.demo"},
        )
        calls: list[tuple[str, dict]] = []

        def _hook(field_id: str, bundle: dict):
            calls.append((field_id, bundle))
            return {"ok": True, "errors": [], "warnings": [], "mutation_summary": {}}

        prom = sess.promote(hooks=ToolSandboxPromotionHooks(apply_tool_config_write=_hook))
        self.assertTrue(prom.get("ok"))
        self.assertEqual(len(calls), 1)
        self.assertFalse(sess.staged_tool_config_writes)

    @patch("_shared.portal.sandbox.tool_sandbox_session.evaluate_resource_payload_write")
    def test_promote_blocked_when_resource_row_eval_fails(self, mock_ev):
        mock_ev.return_value = {"ok": False, "errors": ["invalid graph"], "warnings": []}
        self.engine.save_resource(
            "rx",
            {
                "resource_id": "rx",
                "anthology_compatible_payload": {"rows": {"1-1-1": {"row_id": "1-1-1"}}},
            },
        )
        decl = {"tool_id": "t1", "required_resources": [{"resource_id": "rx", "required": True}]}
        sess = self.mgr.open_session(self._deps(), tool_key="t1", declaration=decl)  # type: ignore[arg-type]
        sess.stage_resource(
            "rx",
            {
                "resource_id": "rx",
                "anthology_compatible_payload": {"rows": {"1-1-1": {"row_id": "1-1-1"}}},
            },
        )
        prom = sess.promote(hooks=ToolSandboxPromotionHooks())
        self.assertFalse(prom.get("ok"))
        self.assertTrue(mock_ev.called)

    @patch("_shared.portal.sandbox.tool_sandbox_session.evaluate_resource_payload_write")
    def test_promote_resource_allowed_under_rule_write_override(self, mock_ev):
        def _side_effect(_payload, *, rule_write_override=False):
            if rule_write_override:
                return {"ok": True, "errors": [], "warnings": ["override used"]}
            return {"ok": False, "errors": ["would block"], "warnings": []}

        mock_ev.side_effect = _side_effect
        self.engine.save_resource(
            "rx",
            {
                "resource_id": "rx",
                "anthology_compatible_payload": {"rows": {"1-1-1": {"row_id": "1-1-1"}}},
            },
        )
        decl = {"tool_id": "t1", "required_resources": [{"resource_id": "rx", "required": True}]}
        sess = self.mgr.open_session(self._deps(), tool_key="t1", declaration=decl)  # type: ignore[arg-type]
        sess.stage_resource(
            "rx",
            {
                "resource_id": "rx",
                "anthology_compatible_payload": {"rows": {"1-1-1": {"row_id": "1-1-1"}}},
            },
        )
        prom = sess.promote(
            hooks=ToolSandboxPromotionHooks(),
            rule_write_override=True,
            rule_write_override_reason="unit test override",
        )
        self.assertTrue(prom.get("ok"))


@unittest.skipUnless(HAS_FLASK, "flask is not installed in host python")
class ToolSandboxSessionRouteTests(unittest.TestCase):
    def setUp(self):
        register_data_routes = _load_register_data_routes()
        self._tmpdir = tempfile.TemporaryDirectory()
        root = Path(self._tmpdir.name)
        (root / "sandbox" / "resources").mkdir(parents=True, exist_ok=True)
        self.app = Flask(__name__)
        register_data_routes(
            self.app,
            workspace=_WorkspaceStub(data_dir=str(root)),
            anthology_payload_provider=lambda: {},
            active_config_provider=lambda: {"agro": {"inherited": {"product_profile_ref": "8-5-11"}}},
            active_config_saver=lambda payload: True,
            msn_id_provider=lambda: "9-9-9",
            include_home_redirect=False,
            include_legacy_shims=False,
        )
        self.client = self.app.test_client()
        self.root = root

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_tool_session_open_get_stage_promote_close(self):
        op = self.client.post("/portal/api/data/sandbox/tool_session/open", json={"tool_key": "agro_erp"})
        self.assertEqual(op.status_code, 200, op.get_data(as_text=True))
        body = op.get_json() or {}
        sid = str(body.get("session_id") or "")
        self.assertTrue(sid)
        self.assertIn("agro.inherited.product_profile_ref", (body.get("loaded_config_inputs") or {}))

        g = self.client.get(f"/portal/api/data/sandbox/tool_session/{sid}")
        self.assertEqual(g.status_code, 200)

        st = self.client.post(
            f"/portal/api/data/sandbox/tool_session/{sid}/stage",
            json={"resources": {"plot.x": {"resource_id": "plot.x", "resource_kind": "plot_plan"}}},
        )
        self.assertEqual(st.status_code, 200)

        pr = self.client.post(f"/portal/api/data/sandbox/tool_session/{sid}/promote", json={})
        self.assertEqual(pr.status_code, 200)
        prom = pr.get_json() or {}
        self.assertTrue(prom.get("ok"))

        cl = self.client.delete(f"/portal/api/data/sandbox/tool_session/{sid}")
        self.assertEqual(cl.status_code, 200)
        self.assertTrue((cl.get_json() or {}).get("ok"))

    def test_tool_session_open_reopen_reloads_resource(self):
        from _shared.portal.sandbox.engine import SandboxEngine

        eng = SandboxEngine(data_root=Path(self.root))
        eng.save_resource("r1", {"resource_id": "r1", "version": 1})
        decl = {"tool_id": "t1", "required_resources": [{"resource_id": "r1", "required": True}]}
        op1 = self.client.post(
            "/portal/api/data/sandbox/tool_session/open",
            json={"tool_key": "t1", "declaration": decl, "session_id": "ab"},
        )
        self.assertEqual(op1.status_code, 200, op1.get_data(as_text=True))
        eng.save_resource("r1", {"resource_id": "r1", "version": 2})
        op2 = self.client.post(
            "/portal/api/data/sandbox/tool_session/open",
            json={"tool_key": "t1", "declaration": decl, "session_id": "ab", "reopen": True},
        )
        self.assertEqual(op2.status_code, 200)
        body = op2.get_json() or {}
        self.assertEqual(((body.get("loaded_resources") or {}).get("r1") or {}).get("version"), 2)

    def test_tool_session_understanding_and_refresh_routes(self):
        op = self.client.post("/portal/api/data/sandbox/tool_session/open", json={"tool_key": "agro_erp"})
        self.assertEqual(op.status_code, 200)
        sid = (op.get_json() or {}).get("session_id")
        self.assertTrue(sid)
        un = self.client.get(f"/portal/api/data/sandbox/tool_session/{sid}/understanding")
        self.assertEqual(un.status_code, 200)
        uj = un.get_json() or {}
        self.assertTrue(uj.get("ok"))
        self.assertIn("datum_understanding", uj)
        rf = self.client.post(f"/portal/api/data/sandbox/tool_session/{sid}/refresh", json={})
        self.assertEqual(rf.status_code, 200)

    def test_stage_accepts_staged_rows_alias(self):
        op = self.client.post("/portal/api/data/sandbox/tool_session/open", json={"tool_key": "agro_erp"})
        sid = (op.get_json() or {}).get("session_id")
        st = self.client.post(
            f"/portal/api/data/sandbox/tool_session/{sid}/stage",
            json={
                "staged_rows": {
                    "1-1-1": {
                        "row_id": "1-1-1",
                        "identifier": "1-1-1",
                        "label": "z",
                        "pairs": [{"reference": "2-1-1", "magnitude": "1"}],
                        "reference": "2-1-1",
                        "magnitude": "1",
                    }
                }
            },
        )
        self.assertEqual(st.status_code, 200)
        body = st.get_json() or {}
        self.assertIn("1-1-1", body.get("staged_rows") or [])

    def test_samras_workspace_route_returns_view_model(self):
        from _shared.portal.sandbox.engine import SandboxEngine

        eng = SandboxEngine(data_root=Path(self.root))
        eng.save_resource(
            "txa.samras.demo",
            {
                "resource_id": "txa.samras.demo",
                "resource_kind": "txa",
                "rows_by_address": {"1": ["Root"], "1-1": ["Child"]},
            },
        )
        op = self.client.post("/portal/api/data/sandbox/tool_session/open", json={"tool_key": "agro_erp"})
        sid = (op.get_json() or {}).get("session_id")
        url = (
            "/portal/api/data/sandbox/samras_workspace?resource_id=txa.samras.demo"
            f"&selected_address=1-1&sandbox_session_id={sid}"
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json() or {}
        self.assertTrue(payload.get("ok"))
        vm = payload.get("view_model") if isinstance(payload.get("view_model"), dict) else {}
        self.assertEqual(vm.get("schema"), "mycite.portal.sandbox.samras_workspace.view_model.v1")
        self.assertEqual((vm.get("branch_context") or {}).get("selected_address_id"), "1-1")


if __name__ == "__main__":
    unittest.main()
