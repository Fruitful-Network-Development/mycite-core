# System page composition

## Regions

| Region | Responsibility |
|--------|----------------|
| **Control panel** | Current file/datum summary plus compatible mediations. No separate anthology/resources or Local Resources/Inheritance navigation. |
| **Center workbench** | Unified layered SYSTEM table for `anthology.json`, `samras-txa.json`, and `samras-msn.json`. |
| **Details** | NIMM-driven file or datum details for Navigate / Investigate / Mediate / Manipulate. |

## Unified workbench

- The anthology/resources split is removed.
- The layered anthology-style table is now the canonical SYSTEM surface for all three files.
- Default file attention is `anthology.json`.
- The old resources file switcher is replaced by `Navigate` at file focus.
- The old hardcoded AGRO launch buttons are removed; mediation is opened through compatible-tool discovery.
- Legacy `local_resources`, `inheritance`, `workbench=anthology`, and `workbench=resources` queries resolve into this same shell as compatibility aliases.

## File focus vs datum focus

- With no datum selected, the workbench attends to a file and the Details panel shows file-level Navigate / Investigate / Mediate / Manipulate content.
- Selecting a datum moves the workbench to datum focus and updates the AITAS strip.
- Changing files clears datum selection and any active mediated subview.

## Manipulate mode

- File focus:
  - plus controls create datums in the active file
  - minus controls delete datums from the layered table
  - TXA/MSN staging can be published
- Datum focus:
  - anthology rows reuse anthology profile editing
  - TXA/MSN rows use the generic canonical-row editor in Details

## Tests

- `tests/test_system_page_composition.py`
- `tests/test_resources_workbench_js_contract.py`
- `tests/test_fnd_portal_shell_routes.py`
- `tests/test_tff_portal_shell_routes.py`
