"""Phase 5 — lens management: catalog, Control-Panel enabled-state, render effect.

Covers the full stack of the lens Utilities/Control-Panel UX (docs/wiki/81):
- the lens catalog + per-lens bindings,
- the resolver honoring an enabled-set (disabled → identity passthrough),
- the runtime's persistence + toggle,
- the /portal/api/lenses GET + toggle POST round-trip,
- the workbench render path applying a disabled lens (resolved_lens → identity).
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_lens_runtime import (
    build_lens_catalog_response,
    enabled_lens_ids,
    read_disabled_lens_ids,
    set_lens_enabled,
)
from MyCiteV2.packages.core.datum_ops import labels, samras_deps
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.state_machine.lens import DEFAULT_DATUM_LENS_REGISTRY, resolve_datum_lens
from MyCiteV2.packages.tools.workbench_ui.service import WorkbenchUiReadService

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None
_NID, _TITLE = "rf.3-1-1", "rf.3-1-2"


class LensCatalogTests(unittest.TestCase):
    def test_catalog_lists_builtins_with_bindings_and_excludes_identity(self) -> None:
        catalog = DEFAULT_DATUM_LENS_REGISTRY.catalog()
        ids = {entry["lens_id"] for entry in catalog}
        self.assertIn("numeric_hyphen", ids)
        self.assertIn("binary_text", ids)
        self.assertNotIn("identity", ids)  # always-on passthrough, not toggleable
        numeric = next(e for e in catalog if e["lens_id"] == "numeric_hyphen")
        self.assertTrue(numeric["label"])
        self.assertIn("samras", numeric["bindings"]["families"])


class EnabledStateResolutionTests(unittest.TestCase):
    def test_none_is_behavior_preserving(self) -> None:
        self.assertEqual(resolve_datum_lens(recognized_family="samras").lens_id, "numeric_hyphen")
        self.assertEqual(
            resolve_datum_lens(recognized_family="samras", enabled_lens_ids=None).lens_id,
            "numeric_hyphen",
        )

    def test_disabled_lens_falls_back_to_identity(self) -> None:
        res = resolve_datum_lens(recognized_family="samras", enabled_lens_ids=frozenset())
        self.assertEqual(res.lens_id, "identity")
        self.assertEqual(res.matched_on, "lens_disabled")

    def test_enabled_lens_resolves_normally(self) -> None:
        res = resolve_datum_lens(recognized_family="samras", enabled_lens_ids=frozenset({"numeric_hyphen"}))
        self.assertEqual(res.lens_id, "numeric_hyphen")
        self.assertEqual(res.matched_on, "family")


class LensRuntimePersistenceTests(unittest.TestCase):
    def test_default_all_enabled_then_toggle_round_trip(self) -> None:
        with TemporaryDirectory() as tmp:
            private = Path(tmp)
            self.assertEqual(read_disabled_lens_ids(private), frozenset())
            all_ids = {e["lens_id"] for e in DEFAULT_DATUM_LENS_REGISTRY.catalog()}
            self.assertEqual(enabled_lens_ids(private), frozenset(all_ids))

            set_lens_enabled(private, lens_id="numeric_hyphen", enabled=False)
            self.assertEqual(read_disabled_lens_ids(private), frozenset({"numeric_hyphen"}))
            self.assertNotIn("numeric_hyphen", enabled_lens_ids(private))
            catalog = build_lens_catalog_response(private)["lenses"]
            numeric = next(e for e in catalog if e["lens_id"] == "numeric_hyphen")
            self.assertFalse(numeric["enabled"])

            set_lens_enabled(private, lens_id="numeric_hyphen", enabled=True)
            self.assertEqual(read_disabled_lens_ids(private), frozenset())

    def test_unknown_lens_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                set_lens_enabled(Path(tmp), lens_id="no_such_lens", enabled=False)


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class LensApiTests(unittest.TestCase):
    def _client(self):
        from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app
        tmp = Path(tempfile.mkdtemp(prefix="lens_api_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        config = V2PortalHostConfig(
            portal_instance_id="fnd", public_dir=tmp / "public", private_dir=tmp / "private",
            data_dir=tmp / "data", portal_domain="example.test", webapps_root=tmp / "webapps",
        )
        return create_app(config).test_client()

    def test_get_then_toggle(self) -> None:
        client = self._client()
        resp = client.get("/portal/api/lenses")
        self.assertEqual(resp.status_code, 200)
        lenses = resp.get_json()["lenses"]
        self.assertTrue(all(e["enabled"] for e in lenses))  # default: all enabled

        toggled = client.post("/portal/api/lenses/toggle", json={"lens_id": "binary_text", "enabled": False})
        self.assertEqual(toggled.status_code, 200, toggled.get_data(as_text=True))
        binary = next(e for e in toggled.get_json()["lenses"] if e["lens_id"] == "binary_text")
        self.assertFalse(binary["enabled"])

    def test_toggle_unknown_lens_400(self) -> None:
        resp = self._client().post("/portal/api/lenses/toggle", json={"lens_id": "nope"})
        self.assertEqual(resp.status_code, 400)


class RenderHonorsDisabledLensTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.db = Path(self._tmp.name) / "mos.sqlite3"
        bits = samras_deps.build_magnitude_bitstream({"1", "2", "2-1"})
        txa = AuthoritativeDatumDocument(
            document_id=f"lv.3-2-3-17-77-1-6-4-1-4.agro_erp.txa.{'a' * 64}",
            source_kind="sandbox_source", document_name="txa", relative_path="agro_erp/txa.json",
            rows=(
                AuthoritativeDatumDocumentRow(datum_address="4-2-1", raw=[["4-2-1", _NID, "1", _TITLE, labels.encode_label_bits("g")], ["g"]]),
                AuthoritativeDatumDocumentRow(datum_address="1-1-1", raw=[["1-1-1", "0-0-5", bits], ["txa-SAMRAS"]]),
            ),
        )
        self._store().store_authoritative_catalog(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id="fnd", documents=(txa,),
                source_files={"sandbox_source": "agro_erp/"}, readiness_status={"x": "y"},
            )
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _store(self):
        from MyCiteV2.packages.adapters.sql.datum_store import SqliteSystemDatumStoreAdapter
        return SqliteSystemDatumStoreAdapter(self.db, allow_legacy_writes=False)

    def _resolved_lenses(self, enabled):
        svc = WorkbenchUiReadService(self.db)
        model = svc.read_surface(
            portal_instance_id="fnd", portal_domain="example.test",
            surface_query={"document": f"lv.3-2-3-17-77-1-6-4-1-4.agro_erp.txa.{'a' * 64}"},
            enabled_lens_ids=enabled,
        )
        rows = model.get("visible_row_items") or model.get("rows") or []
        return {(r["datum_address"], r["resolved_lens"], r["resolved_lens_match"]) for r in rows}

    def test_disabled_lens_renders_as_identity(self) -> None:
        # With everything enabled (None), the SAMRAS anchor row resolves a real lens.
        baseline = self._resolved_lenses(None)
        self.assertTrue(baseline, "expected some rows")
        # With an empty enabled-set, every non-identity lens is disabled → identity/lens_disabled.
        disabled = self._resolved_lenses(frozenset())
        for _addr, lens_id, match in disabled:
            self.assertTrue(
                lens_id == "identity" or match in ("fallback", "lens_disabled"),
                f"expected identity/disabled, got {lens_id}/{match}",
            )
        self.assertNotEqual(baseline, disabled)


if __name__ == "__main__":
    unittest.main()
