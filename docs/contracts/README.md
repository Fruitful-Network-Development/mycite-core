# Contracts

This directory defines reusable V2 rules for ownership, shell behavior, tool
typing, and network/domain boundaries.

- Start with [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md).
- Use [../governance/document_registry.yaml](../governance/document_registry.yaml)
  to confirm lifecycle and supersession state.
- [tool_exposure_and_admin_activity_bar_contract.md](tool_exposure_and_admin_activity_bar_contract.md)
  defines shell-owned legality plus instance-level visibility gating.
- [tool_kind_and_portal_attachment_contract.md](tool_kind_and_portal_attachment_contract.md)
  defines `tool_kind`, shared capability declarations, and the root-service vs
  tool split.
- [admin_cts_gis_read_only_surface.md](admin_cts_gis_read_only_surface.md)
  defines the live CTS-GIS read-only surface contract.
- [cts_gis_hops_projection_lens_contract.md](cts_gis_hops_projection_lens_contract.md)
  defines the CTS-GIS SAMRAS/HOPS mediation and projection boundary.
- [admin_fnd_ebi_read_only_surface.md](admin_fnd_ebi_read_only_surface.md)
  defines the live FND-EBI read-only visibility surface contract.
- [admin_network_root_read_model.md](admin_network_root_read_model.md)
  defines the live `NETWORK` root read model.
- [chronology_mediation_contract.md](chronology_mediation_contract.md)
  defines chronology as mediation, not an active tool packet item.
- [host_alias_and_portal_instance_contract.md](host_alias_and_portal_instance_contract.md)
  defines the hosted/network entity set.
- [network_operation_and_p2p_boundary.md](network_operation_and_p2p_boundary.md)
  defines `/portal/network` tab ownership and hosted/P2P separation.
- [shell_region_kinds.md](shell_region_kinds.md) defines admin shell region
  shapes and current runtime ↔ client mapping.
- [trusted_tenant_shell_region_kinds.md](trusted_tenant_shell_region_kinds.md)
  defines trusted-tenant region kinds.
- [datum_io_and_recognition.md](datum_io_and_recognition.md) and
  [tool_state_and_datum_authority.md](tool_state_and_datum_authority.md) remain
  the datum-authority references.

Use [admin_maps_read_only_surface.md](admin_maps_read_only_surface.md) only as a
superseded pointer to CTS-GIS naming.
