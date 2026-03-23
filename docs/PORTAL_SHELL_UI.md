## Portal shell UI model

This document records the intended shell behavior after the SYSTEM workbench unification.

### Shell mental model

- **Control panel**
  - page-local context and lightweight summaries
  - toggled from the menubar as `Context`
- **Workbench**
  - primary interactive surface
  - should remain visible whenever possible
- **Details**
  - richer contextual pane
  - toggled from the menubar as `Details`

### SYSTEM-specific guidance

- The left page-local region is referred to as the **control panel**.
- The SYSTEM page no longer uses separate anthology/resources tabs.
- Legacy split-view SYSTEM aliases are removed from active navigation and should not be reintroduced as current tabs or page modes.
- The top-left of the SYSTEM workbench always shows the four NIMM directives plus the AITAS strip.
- File switching belongs to `Navigate`, not to separate SYSTEM view links.
- Mediation entry points come from compatible-tool discovery, not hardcoded AGRO buttons.

### Layout notes

- The menubar must keep `Context`, `Details`, and `Theme` aligned on one row.
- The control panel may shrink before the center workbench loses visibility.
- On smaller screens, the Details panel can overlay, but the workbench should remain the base layer.
