"""Unit tests for `_strict_projection_context_differs`.

Verifies the predicate correctly distinguishes "no live re-projection needed"
(empty/missing fields default to compiled artifact's defaults) from "must
re-read the live service surface" (an explicit override that diverges from
the compiled artifact's default tool state).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import (  # noqa: E402
    _strict_projection_context_differs,
)


_ARTIFACT = {
    "default_tool_state": {
        "selected_node_id": "n_default",
        "aitas": {"time_directive": "now"},
        "source": {
            "attention_document_id": "doc_a",
            "precinct_district_overlay_enabled": False,
        },
        "selection": {"selected_row_address": "1-0-0", "selected_feature_id": "f1"},
    },
    "projection_model": {"profile_summary": {"node_id": "n_default"}},
}


class StrictProjectionContextDiffersTests(unittest.TestCase):
    def test_empty_request_does_not_force_live_read(self):
        self.assertFalse(
            _strict_projection_context_differs(
                compiled_artifact=_ARTIFACT, requested_tool_state={}
            )
        )

    def test_explicit_request_matching_defaults_does_not_force_live_read(self):
        self.assertFalse(
            _strict_projection_context_differs(
                compiled_artifact=_ARTIFACT,
                requested_tool_state={
                    "selected_node_id": "n_default",
                    "aitas": {"time_directive": "now"},
                    "source": {"attention_document_id": "doc_a"},
                    "selection": {
                        "selected_row_address": "1-0-0",
                        "selected_feature_id": "f1",
                    },
                },
            )
        )

    def test_explicit_empty_string_treated_as_default(self):
        self.assertFalse(
            _strict_projection_context_differs(
                compiled_artifact=_ARTIFACT,
                requested_tool_state={
                    "selected_node_id": "",
                    "aitas": {"time_directive": ""},
                    "source": {
                        "attention_document_id": "",
                        "precinct_district_overlay_enabled": False,
                    },
                    "selection": {
                        "selected_row_address": "",
                        "selected_feature_id": "",
                    },
                },
            )
        )

    def test_different_selected_node_forces_live_read(self):
        self.assertTrue(
            _strict_projection_context_differs(
                compiled_artifact=_ARTIFACT,
                requested_tool_state={"selected_node_id": "n_other"},
            )
        )

    def test_different_time_directive_forces_live_read(self):
        self.assertTrue(
            _strict_projection_context_differs(
                compiled_artifact=_ARTIFACT,
                requested_tool_state={"aitas": {"time_directive": "past"}},
            )
        )

    def test_different_attention_document_forces_live_read(self):
        self.assertTrue(
            _strict_projection_context_differs(
                compiled_artifact=_ARTIFACT,
                requested_tool_state={"source": {"attention_document_id": "doc_b"}},
            )
        )

    def test_overlay_toggle_change_forces_live_read(self):
        self.assertTrue(
            _strict_projection_context_differs(
                compiled_artifact=_ARTIFACT,
                requested_tool_state={
                    "source": {"precinct_district_overlay_enabled": True}
                },
            )
        )

    def test_different_selected_row_forces_live_read(self):
        self.assertTrue(
            _strict_projection_context_differs(
                compiled_artifact=_ARTIFACT,
                requested_tool_state={"selection": {"selected_row_address": "1-0-1"}},
            )
        )

    def test_different_selected_feature_forces_live_read(self):
        self.assertTrue(
            _strict_projection_context_differs(
                compiled_artifact=_ARTIFACT,
                requested_tool_state={"selection": {"selected_feature_id": "f2"}},
            )
        )


if __name__ == "__main__":
    unittest.main()
