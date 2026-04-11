# Compatibility Seams

These seams remain intentionally for runtime safety. They are transitional and
must not become development homes.

| Seam | Type | Canonical owner | Retirement condition |
| --- | --- | --- | --- |
| `portals/runtime/app.py` | Wrapper | `runtime/app.py` | Service units and docs no longer reference the old path |
| `portals/runtime/bin/run_portal.sh` | Wrapper | `runtime/bin/run_portal.sh` | Launch docs and unit files use the canonical script directly |
| `instances/_shared/portal/runtime_paths.py` | Wrapper | `mycite_core/runtime_host/paths.py` | Legacy `_shared` imports are removed from active code |
| `instances/_shared/portal/application/runtime/instance_context.py` | Wrapper | `mycite_core/runtime_host/instance_context.py` | Flavor bootstrap uses canonical imports directly |
| `instances/_shared/portal/application/shell/contracts.py` | Wrapper | `mycite_core/state_machine/controls.py` | Shell callers stop importing the legacy adapter |
| `instances/_shared/portal/application/shell/tools.py` | Wrapper | `mycite_core/state_machine/tool_capabilities.py` | Tool callers stop importing the legacy adapter |
| `instances/_shared/portal/application/shell/runtime.py` | Wrapper | `mycite_core/state_machine/view_model.py` | Shell routes and views import the canonical owner directly |
| `instances/_shared/portal/data_engine/aitas_context.py` | Wrapper | `mycite_core/state_machine/aitas.py` | AITAS callers stop importing the legacy adapter |
| `instances/_shared/portal/tools/runtime.py` | Wrapper | `tools/_shared/tool_state_api/runtime.py` | Flavor-specific tool packages move to canonical tool packages |
| `instances/_shared/portal/tools/specs.py` | Wrapper | `tools/_shared/tool_contracts/specs.py` | Tool callers import the canonical spec loader directly |

Rules for all seams:

- no new feature work should originate inside a seam;
- seams may delegate or re-export only;
- every seam must point to one canonical owner;
- when a seam is removed, remove its doc entry in the same change.
