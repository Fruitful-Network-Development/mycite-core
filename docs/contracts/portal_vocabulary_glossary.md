# Portal Vocabulary Glossary

Canonical vocabulary for v2.5.3 shell/docs/runtime alignment.

| Legacy or Parallel Term | Canonical Term | Status in v2.5.3 | Deprecation Target |
|---|---|---|---|
| `inspector` (public shell term) | `Interface Panel` | Kept as compatibility alias in payload and internal code paths | Remove public alias in next schema revision |
| `regions.inspector` | `regions.interface_panel` | Both emitted; `regions.interface_panel` is canonical public name | Remove alias in next schema revision |
| `inspector_collapsed` | `interface_panel_collapsed` | Both emitted; `interface_panel_collapsed` is canonical public name | Remove alias in next schema revision |
| `mycite.layout.inspector.width` / `mycite.layout.inspector.open` | `mycite.layout.interface_panel.width` / `mycite.layout.interface_panel.open` | Legacy storage keys still readable; canonical keys remain source of truth | Remove legacy storage reads after compatibility window |
| `mycite:v2:inspector-toggle-request` / `mycite:v2:inspector-dismiss-request` | `mycite:v2:interface-panel-toggle-request` / `mycite:v2:interface-panel-dismiss-request` | Legacy event names still accepted | Remove legacy event aliases after compatibility window |
| Header text buttons for `Control Panel` / `Workbench` | Menubar icon-toggle trio: `Control Panel`, `Workbench`, `Interface Panel` | Canonical | N/A |
| Tool free-form panel coexistence wording | Tool default single-click exclusivity + double-click route lock mode | Canonical | N/A |
| `stacked_focus_panel` | `focus_selection_panel` | Legacy removed; canonical contract retained | Removed |
| `operational-status` surface language | Unified shell/tool posture language | Legacy removed; canonical contract retained | Removed |

Notes:

- CTS-GIS phase-B (v2.5.4) removes legacy CTS-GIS alias acceptance from active contracts.
- The canonical shell chrome language is `ide-shell`, `ide-menubar`, `ide-body`, `Activity Bar`, `Control Panel`, `Workbench`, and `Interface Panel`.
