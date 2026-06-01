"""ext_tooling — reference scaffold for new utilities extensions.

This file is the canonical empty shape every new extension should copy.
The pattern:

1. **One module per extension** living under
   ``MyCiteV2/instances/_shared/runtime/utilities_extensions/<name>.py``.
2. **One public builder** named ``_build_<name>_extension_payload`` (the
   underscore prefix matches the rest of this directory — these are
   runtime-internal builders, not public API).
3. **Signature**: ``(grantee: dict, domain: str, private_dir,
   authority_db_file, portal_instance_id) -> dict``. Match keyword
   defaults so the call site can pass `**common_kwargs`.
4. **Imports**: only from `MyCiteV2.packages.peripherals.*` (peripheral
   packages) and `._shared` (shared helper functions). **Never** import
   another extension module.
5. **Return shape**: a dict with a stable top-level structure (the
   `configuration` block + any number of secondary blocks) so the
   surface renderer can lay it out consistently. See `email.py` and
   `newsletter.py` for living examples.

To add a new extension:

* Copy this file → `<my_extension>.py`.
* Replace the docstring + builder name.
* Wire the builder into the renderer at
  `instances/_shared/runtime/portal_shell_runtime.py` alongside the
  email + newsletter calls.
* Register the surface kind in
  `MyCiteV2/packages/state_machine/portal_shell/shell_registry.py`.
* Add an integration test under
  `MyCiteV2/tests/integration/test_utilities_surface_split.py`.

The tooling extension itself surfaces meta-information about the
grantee's portal tools (what's deployed, where the tool dirs live,
which tools are operational). The implementation is intentionally
minimal — it serves as the reference shape while the actual content
fills in as new tooling needs emerge.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._shared import _as_list, _as_text, _grantee_edit_link

EXTENSION_ID = "tooling"
EXTENSION_LABEL = "Tooling"


def _build_tooling_extension_payload(
    grantee: dict[str, Any],
    domain: str,
    private_dir: str | Path | None,
    authority_db_file: str | Path | None = None,
    portal_instance_id: str | None = None,
) -> dict[str, Any]:
    configuration = {
        "label": "Tooling",
        "summary": (
            "Per-grantee portal tooling surface. Lists deployed tools under "
            "`deployed/<grantee>/private/utilities/tools/`, their on-disk paths, "
            "and operational state. Intentionally minimal — extend as tooling needs emerge."
        ),
        "items": [
            {"label": "Grantee", "value": _as_text(grantee.get("name"))},
            {"label": "Domain", "value": _as_text(domain)},
        ],
        "edit_link": _grantee_edit_link("tooling"),
    }

    tools: list[dict[str, Any]] = []
    if private_dir is not None:
        tools_root = Path(private_dir) / "utilities" / "tools"
        if tools_root.is_dir():
            for entry in sorted(tools_root.iterdir()):
                if entry.is_dir():
                    tools.append(
                        {
                            "tool_id": entry.name,
                            "path": str(entry),
                            "present": True,
                        }
                    )

    return {
        "extension_id": EXTENSION_ID,
        "label": EXTENSION_LABEL,
        "configuration": configuration,
        "tools": tools,
        "domains": [_as_text(d) for d in _as_list(grantee.get("domains")) if _as_text(d)],
        "notes": [
            "This extension is the reference shape for new extensions.",
            "Copy this file when adding more — see the module docstring.",
        ],
    }


__all__ = ["EXTENSION_ID", "EXTENSION_LABEL", "_build_tooling_extension_payload"]
