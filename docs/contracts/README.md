# Contracts

This directory defines reusable rules for module boundaries, terminology, and imports.

- [repo_and_runtime_boundary.md](repo_and_runtime_boundary.md) defines the shared repo-owned-authority vs runtime/deployment boundary.
- [portal_auth_and_audience_boundary.md](portal_auth_and_audience_boundary.md) defines the browser auth, trusted header, and runtime audience split for the live V2 portal.
- [tool_state_and_datum_authority.md](tool_state_and_datum_authority.md) defines the shared rule for tool code, utility state, datum truth, and derived artifacts.
- [tool_exposure_and_admin_activity_bar_contract.md](tool_exposure_and_admin_activity_bar_contract.md) defines the forward V2 split between shell-owned tool legality and instance-level `tool_exposure` gating.
- [v2_surface_ownership_map.md](v2_surface_ownership_map.md) maps the major V2 repo surfaces to their intended ownership boundaries.
- [shell_region_kinds.md](shell_region_kinds.md) defines V2 admin portal `shell_composition` region shapes, `kind` discriminants, and runtime ↔ client mapping.
- [admin_maps_read_only_surface.md](admin_maps_read_only_surface.md) defines the current admin Maps read-only request, surface, and projection contract.
- [trusted_tenant_shell_region_kinds.md](trusted_tenant_shell_region_kinds.md) defines the current trusted-tenant portal region kinds and runtime ↔ client mapping.
- [datum_io_and_recognition.md](datum_io_and_recognition.md) defines authoritative datum source boundaries, read-only recognition diagnostics, and render-hint payload rules.
- [module_contract_template.md](module_contract_template.md) is the standard contract format for future modules.
- [import_rules.md](import_rules.md) defines allowed and forbidden import direction.
- [terminology_usage_rules.md](terminology_usage_rules.md) prevents synonym drift.

Authority comes from [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md).
