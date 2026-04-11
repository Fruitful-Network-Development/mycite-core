# Port And Adapter Ownership Matrix

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

This matrix fixes ownership boundaries for current and future seams.

| Seam | Semantic owner | Port owner | Adapter owner | Runtime role | Forbidden drift |
|---|---|---|---|---|---|
| `audit_log` | `packages/modules/cross_domain/local_audit` | `packages/ports/audit_log` | `packages/adapters/filesystem` for MVP | instantiate and call only | no redaction policy in the port, no local-audit semantics in the adapter, no filesystem paths in the module |
| `aws_read_only_status` | `packages/modules/cross_domain/aws_operational_visibility` | `packages/ports/aws_read_only_status` | `packages/adapters/filesystem` for the first AWS slice | instantiate and call only | no secret-bearing fields in the port result, no AWS semantic policy in the adapter, no runtime-defined provider semantics |
| `aws_narrow_write` | `packages/modules/cross_domain/aws_narrow_write` | `packages/ports/aws_narrow_write` | `packages/adapters/filesystem` for the first AWS write slice | instantiate and call only | no writable-field policy in the port, no AWS write semantics in the adapter, no audit semantics in runtime, no broad provider-admin mutation surface |
| `datum_store` | whichever domain module owns the datum lifecycle for the slice, expected first in `packages/modules/domains/publication` | `packages/ports/datum_store` | `packages/adapters/filesystem` first, other adapters later | instantiate and call only | no utility JSON as datum truth, no adapter-defined datum semantics, no runtime-path helper reuse |
| `payload_store` | the module that owns derived-artifact production for the slice | `packages/ports/payload_store` | filesystem or object-store adapters later | instantiate and call only | no payload authority transfer to the adapter, no cache treated as source truth |
| `event_log` | `packages/modules/cross_domain/external_events` once rebuilt | `packages/ports/event_log` | filesystem or transport adapters later | instantiate and call only | no runtime-defined event meaning, no merge of `local_audit` and `external_events` by convenience |
| `resource_resolution` | the calling domain module, expected first in `packages/modules/domains/reference_exchange` or `packages/modules/domains/publication` | `packages/ports/resource_resolution` | external or local resolution adapters later | instantiate and call only | no adapter-chosen authority chain, no direct portal-resource imports into domain code |
| `session_keys` | `packages/core/crypto` plus the narrow module that needs session capability | `packages/ports/session_keys` | `packages/adapters/session_vault` later | instantiate and call only | no revival of `vault_session` as one mixed owner |
| `time_projection` | `packages/state_machine/mediation_surface` or other HOPS-aware caller when explicitly rebuilt | `packages/ports/time_projection` | adapters added later | instantiate and call only | no utility anchor files treated as time truth, no projection logic collapsed into runtime |
| `shell_surface` | `packages/state_machine/` only | `packages/ports/shell_surface` | future host or transport adapters only | expose and call only | no tool-owned shell legality, no runtime-owned shell legality |

## Matrix rule

- No port may absorb the semantics named in the semantic-owner column.
- No adapter may absorb the semantics named in the semantic-owner column.
- Runtime composition may only instantiate and connect the named port and adapter.
