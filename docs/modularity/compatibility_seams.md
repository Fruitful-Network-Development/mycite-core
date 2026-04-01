# Compatibility Seams

These seams remain intentionally for runtime safety. They are transitional and
must not become new development homes.

| Seam | Type | Purpose | Retirement condition |
| --- | --- | --- | --- |
| `portals/runtime/app.py` | Wrapper | Preserve current Gunicorn import path while canonical entrypoint lives in `runtime/app.py` | Native service units and docs no longer reference `portals/runtime/app.py` |
| `portals/runtime/bin/run_portal.sh` | Wrapper | Preserve existing launcher path while canonical script lives in `runtime/bin/run_portal.sh` | Deploy/runtime docs and unit files use the canonical script directly |
| `portals/_shared/portal/runtime_paths.py` | Wrapper | Preserve old import path for runtime path helpers | Legacy `_shared` imports are removed from active code |
| `portals/_shared/portal/application/runtime/instance_context.py` | Wrapper | Preserve old import path for instance context builder | Flavor app bootstrap is moved to canonical imports |
| `portals/_shared/portal/application/shell/contracts.py` | Wrapper | Preserve old shell contract imports | Shell callers import `portal_core.shell.contracts` directly |
| `portals/_shared/portal/application/shell/tools.py` | Wrapper | Preserve old shell tool-capability imports | Shell/tool callers import `portal_core.shell.tool_capabilities` directly |
| `portals/_shared/portal/tools/runtime.py` | Wrapper | Preserve legacy tool-runtime import path used by flavor packages and tests | Flavor-specific tool packages move to canonical tool packages |
| `portals/_shared/portal/tools/specs.py` | Wrapper | Preserve legacy tool spec-loader path | Tool callers import `tools._shared.tool_contracts.specs` directly |
| `portals/_shared/portal/application/service_tools.py` | Transitional aggregator | Still builds service-tool config contexts and interface cards for legacy callers | Split config-context rendering into dedicated tool modules |
| `portals/scripts/portal_build.py` | Transitional CLI | Existing capture/materialize command-line surface | Implementation moves into `instances/materializers` with wrapper retained only briefly |
| `portals/scripts/correct_portal_sandbox_contract.py` | Transitional CLI | Existing corrective migration CLI surface | Implementation moves into `instances/materializers` |
| `tools/paypal_csm/backend/webhook_compat_app.py` | Compatibility runtime | Minimal webhook ingress required by current PayPal compatibility surface | Canonical runtime absorbs or retires `/paypal/webhook` |
| `admin_integrations._legacy_paypal_root()` | Data migration seam | Reads old PayPal admin-runtime data only long enough to bridge old state | No remaining legacy PayPal state reads or migrations are needed |

Rules for all seams:

- no new feature work should originate inside a seam;
- seams may delegate, re-export, or translate only;
- every seam must point to one canonical owner;
- when a seam is removed, remove its doc entry in the same change.

