"""Local Domain viewer — the lcl tree extended with expand-to-table instance containers.

The tool reuses the SAMRAS tree builder (nodes carry a ``record_view`` token from the lcl
doc's ``rf.3-1-8`` VIEW markers) and maps each token to an existing record viewer via
``VIEW_DISPATCH``. Tests the registration, the dispatch/normalizer contract, and (live) that
the tree's expandable nodes mirror the lcl doc's VIEW markers and each record view leads with
the lcl-id. Robust across the restructure migration: the marker-driven assertions compare the
tree to whatever VIEW markers the live lcl doc currently carries.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import MyCiteV2.packages.tools.local_domain_viewer as ld
from MyCiteV2.instances._shared.runtime.portal_palette_runtime import LIVE_TOOL_IDS
from MyCiteV2.packages.core.datum_ops.datum_resolve import view_token_index
from MyCiteV2.packages.tools import get as tools_get
from MyCiteV2.packages.tools._archetype import find_named_document, read_sandbox_catalog

_LIVE_DB = Path("/srv/webapps/mycite/fnd/private/mos_authority.sqlite3")


class TestRegistration(unittest.TestCase):
    def test_registered_and_live(self) -> None:
        self.assertIsInstance(tools_get("local_domain"), ld.LocalDomainViewer)
        self.assertIn("local_domain", LIVE_TOOL_IDS)
        # Same surfacing as the samras viewer it extends.
        from MyCiteV2.packages.tools.samras_structure_viewer import SamrasStructureViewer
        self.assertEqual(
            set(ld.LocalDomainViewer.applies_to_archetype),
            set(SamrasStructureViewer.applies_to_archetype),
        )


class TestDispatch(unittest.TestCase):
    def test_view_dispatch_tokens(self) -> None:
        self.assertEqual(set(ld.VIEW_DISPATCH), {"product", "invoice", "contract", "contacts"})

    def test_unknown_token_returns_none(self) -> None:
        # Dispatch happens before any DB access, so this needs no live DB.
        self.assertIsNone(ld.build_record_view("nope", authority_db_file=None, sandbox_id="agro_erp"))


@unittest.skipUnless(_LIVE_DB.exists(), "live MOS not present")
class TestLive(unittest.TestCase):
    def _tree(self):
        return ld.LocalDomainViewer().build_panel_payload(
            authority_db_file=_LIVE_DB, sandbox_id="agro_erp", document_id="", datum_address="",
        )

    def test_tree_builds(self) -> None:
        p = self._tree()
        self.assertIsNone(p.get("error"))
        self.assertEqual(p["container"], "local_tree")
        self.assertGreater(len(p["nodes"]), 0)

    def test_expandable_nodes_mirror_view_markers(self) -> None:
        # The tree's record_view-bearing nodes must equal exactly the lcl doc's VIEW markers
        # (none pre-restructure, the four instance containers post-restructure).
        docs, err = read_sandbox_catalog(_LIVE_DB, tenant_id="fnd")
        self.assertFalse(err)
        markers = view_token_index(find_named_document(docs, sandbox="agro_erp", name="lcl"))
        tree_views = {n["full_slug"]: n["record_view"] for n in self._tree()["nodes"] if n.get("record_view")}
        self.assertEqual(tree_views, markers)

    def test_record_views_lead_with_lcl_id(self) -> None:
        import re
        node_addr = re.compile(r"^\d+(-\d+)+$")
        for token in ld.VIEW_DISPATCH:
            t = ld.build_record_view(token, authority_db_file=_LIVE_DB, sandbox_id="agro_erp")
            self.assertEqual(t["container"], "record_table")
            self.assertEqual(t["columns"][0], "lcl_id", f"{token} table must lead with lcl_id")
            if t["rows"]:
                # the leading lcl_id must be a NODE ADDRESS (datum denotation), not a display name.
                self.assertRegex(t["rows"][0]["lcl_id"], node_addr, f"{token} lcl_id must be a node address")


if __name__ == "__main__":
    unittest.main()
