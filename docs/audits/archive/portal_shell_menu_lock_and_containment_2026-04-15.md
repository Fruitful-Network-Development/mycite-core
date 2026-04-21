# Portal Shell Menu Lock + Containment Audit

This audit records the v2.5.3 shell stabilization pass for menubar controls, peer-region containment, and tool-panel lock behavior.

## Findings

- Menubar shell controls mixed text and icon buttons, which drifted from the icon-only shell chrome contract.
- Tool surfaces lacked a canonical, explicit lock mechanism for co-visible `Workbench` + `Interface Panel`.
- Desktop interface panel width could remain visually constrained when the workbench was collapsed, producing cramped tool layouts.
- Header title/subtitle containment could still clip awkwardly under narrow menubar space competition.

## Corrections

- Menubar shell actions are now an icon-only trio (`Control Panel`, `Workbench`, `Interface Panel`) with hover labels and accessibility labels.
- Tool surfaces now default to single-click exclusive toggling between `Workbench` and `Interface Panel`.
- Double-clicking the `Workbench` or `Interface Panel` icon toggles route-scoped tool lock mode, enabling co-visible panel posture without persistent global state.
- Shell chrome emits explicit route-scoped lock signal via `data-tool-panel-lock` on `ide-shell`.
- Peer-region CSS was hardened so collapsed-workbench interface-panel posture fills available track width and no longer stays fixed-width constrained.
- Menubar containment was tightened (`min-width: 0`, bounded overflow, ellipsis behavior) for title/subtitle stability.

## Compatibility

- Legacy `inspector` payload aliases, storage keys, and event aliases remain accepted in soft migration mode.
- Canonical vocabulary now lives in `docs/contracts/portal_vocabulary_glossary.md`.
