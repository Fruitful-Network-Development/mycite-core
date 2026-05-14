"""Phase 12e postcondition: every entry in EXTENSION_RENDERERS is a
callable with the contract `(ctx: dict) -> dict`, and every is_extension
tool in the registry has a matching renderer.

Phases 2 and 9 wired the four (then five) utilities extensions through
this dispatch table. Drift here would surface as a silent empty
extension in the Utilities surface payload — the extension's tile
appears but its body is empty because render_extension swallows
exceptions per the resilience contract.

The test pins the signature contract and the registry↔dispatch
bijection so a future extension addition needs explicit wiring on
both sides.
"""

from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_fnd_csm_runtime import (
    EXTENSION_RENDERERS,
    render_extension,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    build_portal_tool_registry_entries,
)


class ExtensionRendererParityTests(unittest.TestCase):
    def test_every_renderer_is_a_callable(self) -> None:
        for tool_id, renderer in EXTENSION_RENDERERS.items():
            self.assertTrue(
                callable(renderer),
                f"EXTENSION_RENDERERS[{tool_id!r}] is not callable: {renderer!r}",
            )

    def test_every_renderer_takes_one_positional_ctx_arg(self) -> None:
        for tool_id, renderer in EXTENSION_RENDERERS.items():
            sig = inspect.signature(renderer)
            params = list(sig.parameters.values())
            self.assertEqual(
                len(params),
                1,
                f"renderer for {tool_id!r} must accept exactly one positional "
                f"ctx parameter; got {sig}",
            )
            (ctx_param,) = params
            self.assertIn(
                ctx_param.kind,
                {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.POSITIONAL_ONLY},
                f"renderer for {tool_id!r}'s ctx parameter is not positional: {ctx_param}",
            )

    def test_every_renderer_returns_a_dict_when_called_with_empty_ctx(self) -> None:
        # Resilience contract from Phase 2: render_extension swallows
        # per-renderer exceptions and returns {}. Calling each renderer
        # with an empty dict should not raise and should return a dict.
        for tool_id, renderer in EXTENSION_RENDERERS.items():
            try:
                out = renderer({})
            except Exception as exc:
                self.fail(
                    f"renderer for {tool_id!r} raised on empty ctx: {exc!r}. "
                    "Renderers should degrade gracefully because the "
                    "runtime cannot guarantee every context key is set."
                )
            self.assertIsInstance(
                out,
                dict,
                f"renderer for {tool_id!r} returned non-dict on empty ctx: {type(out)}",
            )

    def test_every_is_extension_registry_entry_has_a_renderer(self) -> None:
        registered_extension_tool_ids = {
            entry.tool_id
            for entry in build_portal_tool_registry_entries()
            if entry.is_extension
        }
        missing = registered_extension_tool_ids - set(EXTENSION_RENDERERS.keys())
        self.assertEqual(
            missing,
            set(),
            "These registry entries are marked is_extension=True but have "
            "no matching renderer in EXTENSION_RENDERERS. Wire them or "
            "drop is_extension.",
        )

    def test_no_orphan_renderer_without_a_registry_entry(self) -> None:
        registered_extension_tool_ids = {
            entry.tool_id
            for entry in build_portal_tool_registry_entries()
            if entry.is_extension
        }
        orphans = set(EXTENSION_RENDERERS.keys()) - registered_extension_tool_ids
        self.assertEqual(
            orphans,
            set(),
            "These EXTENSION_RENDERERS entries have no matching is_extension "
            "registry entry. Register the extension or drop the renderer.",
        )

    def test_render_extension_returns_empty_dict_for_unknown_tool_id(self) -> None:
        # The dispatch wrapper's resilience contract.
        self.assertEqual(render_extension("nonexistent_tool", {}), {})
        self.assertEqual(render_extension("", {}), {})


if __name__ == "__main__":
    unittest.main()
