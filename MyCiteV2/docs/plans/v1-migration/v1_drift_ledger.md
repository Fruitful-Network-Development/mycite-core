# V1 Drift Ledger

Authority: [../authority_stack.md](../authority_stack.md)

This is the named ledger of drift patterns that v2 must prevent.

## Mixed runtime and domain imports

- `../../../mycite_core/state_machine/aitas.py` imports `instances._shared.portal.data_engine.*`
- `../../../mycite_core/reference_exchange/imported_refs.py` imports portal resource resolver and registry code
- `../../../mycite_core/contract_line/context.py` imports `instances._shared.portal.sandbox.SandboxEngine`
- `../../../mycite_core/contract_line/alias_service.py` imports portal services directly

## Mixed shell and tool ownership

- `../../../instances/_shared/portal/application/service_tools.py` carries shared tool mediation logic near runtime-facing concerns
- `../../../mycite_core/state_machine/tool_capabilities.py` shows why tool capability and shell ownership must stay separate
- `../../../../docs/plans/tool_dev.md` and `../../../../docs/plans/tool_alignment.md` explicitly warn that the shell surface is primary

## Mixed service and domain naming

- `external_events`, `local_audit`, and `vault_session` are not one ontological category even though v1 naming invites a generic service bucket
- `../../../../docs/modularity/module_inventory.md` and `../../../../docs/modularity/module_contracts.md` show the naming pressure that v2 must tighten

## Mixed datum, utility JSON, and derived payload authority

- `../../../../docs/plans/tool_dev.md` distinguishes `private/utilities/tools`, `data/sandbox`, and `data/payloads`
- `../../../instances/_shared/portal/application/time_address_schema.py` reads anchor paths in a way that shows how authority surfaces can blur if not fixed
- `../../../instances/_shared/portal/application/service_tools.py` shows utility collection selection and tool contract handling close together

## Instance-path assumptions embedded in reusable logic

- `../../../mycite_core/runtime_paths.py` reexports runtime host path helpers into reusable code
- `../../../mycite_core/external_events/store.py`, `../../../mycite_core/local_audit/store.py`, `../../../mycite_core/contract_line/store.py`, and `../../../mycite_core/vault_session/session.py` depend on runtime path helpers

## V2 response

- Use explicit ports instead of runtime-path helper imports
- keep shell legality inside `packages/state_machine/`
- keep sandboxes as orchestration only
- split mixed concerns before recreation
