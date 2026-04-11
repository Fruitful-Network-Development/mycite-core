# Client Exposure Gates

Authority: [../authority_stack.md](../authority_stack.md)

No slice becomes client-visible until all gates in this file are satisfied.

Use [../../testing/slice_gate_template.md](../../testing/slice_gate_template.md) to record the gate result for a specific slice.

## Gate 1: Slice definition

- The slice has a file in [slice_registry/](slice_registry/).
- The slice names its rollout band and exposure status.
- The slice lists owning layers, required ports, required adapters, runtime composition, tests, and out-of-scope items.
- The slice links the v1 evidence that informed prioritization without treating v1 layout as a template.

## Gate 2: Architecture readiness

- The slice does not bypass the authority stack.
- The slice does not require tools or sandboxes unless the slice file says so explicitly.
- The slice does not pull later-band concerns into an earlier band.
- All required seams have an owner in [port_adapter_ownership_matrix.md](port_adapter_ownership_matrix.md).

## Gate 3: Implementation readiness

- The slice implements only the owning layers named in its slice file.
- Runtime code composes only. It does not own new semantics.
- No hidden flavor expansion or second runtime path appears.
- No forbidden v1 drift pattern reappears.
- Tool-bearing slices have one shell-owned descriptor and one runtime entrypoint descriptor.

## Gate 4: Test readiness

- The slice passes the loop that matches each touched layer.
- The slice passes its integration loop.
- The slice passes the architecture boundary loop for all touched layers.
- Negative tests exist for the slice boundary where misuse or overreach is likely.

## Gate 5: Client-safety readiness

- The slice returns only fields that are intentionally client-visible.
- The slice exposes no instance paths, secret-bearing fields, or provider-internal state by accident.
- The slice error surface is explicit and stable.
- The slice README or registry entry tells future agents what remains internal-only.

## Band-specific additions

### Band 1 read-only gate

- The slice contains no write action.
- The runtime path contains no hidden mutation.
- The slice can be withdrawn without blocking the rest of the portal.

### Band 2 writable gate

- The writable field set is explicitly bounded in the slice file.
- Read-after-write behavior is proven end to end.
- A local audit record is emitted for the accepted write path.
- Rollback or manual recovery steps are written down before exposure.
- Only one Band 2 writable slice may be exposed at a time unless a new decision record changes that rule.

### Band 3 broader rollout gate

- Not approved in the current operating band.
- Requires an explicit future decision after Band 1 and Band 2 success.

### Admin-first tool-bearing addition

- `Admin Band 0` shell entry, runtime envelope, home/status surface, and tool registry/launcher must already be stable.
- The tool-bearing slice must launch through the shell-owned registry and a cataloged runtime entrypoint.
- AWS must be the first trusted-tenant tool-bearing slice.
- Maps may not start before AWS is stable.
- AGRO-ERP may not start before Maps is stable.

### Post-AWS platform addition

- Future tools must follow [post_aws_tool_platform/future_tool_drop_in_contract.md](post_aws_tool_platform/future_tool_drop_in_contract.md).
- Read-only tools must follow the read-only pattern in [post_aws_tool_platform/read_only_and_bounded_write_patterns.md](post_aws_tool_platform/read_only_and_bounded_write_patterns.md).
- Writable tools must follow the bounded-write pattern in [post_aws_tool_platform/read_only_and_bounded_write_patterns.md](post_aws_tool_platform/read_only_and_bounded_write_patterns.md).
