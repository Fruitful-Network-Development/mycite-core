# Tool State And Datum Authority

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This file captures the shared rule that survived from V1 into V2: tool code,
tool utility state, datum authority, and derived artifacts must not be
collapsed into one surface.

## Current contract

- Tool code lives in repo-owned code under `MyCiteV2/` or, for legacy evidence,
  under `MyCiteV1/`. Live instance state must not become the source of tool
  code.
- Mutable non-datum tool state belongs under
  `/srv/mycite-state/instances/<tenant>/private/utilities/tools/<tool>/`.
- Tool utility state may hold profile JSON, audit snapshots, helper files, and
  launcher inputs, but it does not become datum truth by convenience.
- Datum authority must remain explicit and fail-closed. If a workflow is
  datum-backed, the owning V2 module, port, and adapter must name the
  authoritative datum surface directly.
- Payload binaries, decoded caches, and other regenerated outputs under
  `/srv/mycite-state/instances/<tenant>/data/payloads/` are derived artifacts,
  never source truth.
- `private/config.json` or any registry/discovery surface may expose a tool, but
  it does not define datum truth.
- Tools attach through shell-defined surfaces. Tools do not define their own
  shell legality or runtime ownership.

## Cross-version interpretation

These rules are shared across both versions, but the structural owner changed:

- In V1, the doctrine is expressed through `packages/tools/`, shared runtime
  glue, and legacy tool/state docs.
- In V2, the doctrine is enforced through `packages/tools/`, semantic modules,
  ports, adapters, shell-owned launch rules, and explicit datum-authority
  contracts.

Keep the rule. Do not copy the V1 package or route shape.

## Use this doc when promoting legacy content

Promote legacy content here when it is really about:

- tool utility state vs datum truth
- payload/cache non-authority
- shell-owned tool attachment
- config exposure vs semantic authority

Leave content in `docs/*/legacy/` when it is really about:

- V1 tool routes
- V1 provider-specific UI
- V1 runtime file trees
- superseded standalone tool surfaces

## Source authorities

- [../ontology/structural_invariants.md](../ontology/structural_invariants.md)
- [../ontology/interface_surfaces.md](../ontology/interface_surfaces.md)
- [../decisions/decision_record_0004_tools_attach_through_shell_surfaces.md](../decisions/decision_record_0004_tools_attach_through_shell_surfaces.md)
- [../plans/legacy/v1-tool_dev.md](../plans/legacy/v1-tool_dev.md)
- [../plans/legacy/modularity/tool_development_guide.md](../plans/legacy/modularity/tool_development_guide.md)
- [../../MyCiteV1/packages/tools/README.md](../../MyCiteV1/packages/tools/README.md)
- [../../MyCiteV2/packages/tools/README.md](../../MyCiteV2/packages/tools/README.md)
