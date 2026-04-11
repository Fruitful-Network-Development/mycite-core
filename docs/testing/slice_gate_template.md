# Slice Gate Template

Authority: [../plans/authority_stack.md](../plans/authority_stack.md)

Use this checklist when deciding whether a slice is ready for implementation or exposure.

## Slice identity

- Slice file:
- Slice status:
- Requested rollout band:
- Requested exposure status:
- Runtime entrypoint id:

## Specification gate

- [ ] Slice file exists in `docs/plans/post_mvp_rollout/slice_registry/`
- [ ] Owning layers are named explicitly
- [ ] Required ports and adapters are named explicitly
- [ ] Runtime composition is named explicitly
- [ ] Out-of-scope items are explicit

## Architecture gate

- [ ] Slice does not bypass the authority stack
- [ ] Slice does not pull frozen areas into the current band
- [ ] Ownership lines match `port_adapter_ownership_matrix.md`
- [ ] Runtime remains composition-only

## Test gate

- [ ] Unit loop defined where semantics live
- [ ] Contract loop defined where seam behavior lives
- [ ] Adapter loop defined where outward implementation lives
- [ ] Integration loop defined for the slice path
- [ ] Architecture boundary loop defined for all touched layers
- [ ] Exact test commands or test files are recorded

## Client-safety gate

- [ ] Client-visible fields are intentional
- [ ] No instance paths or secret-bearing fields leak
- [ ] Error surface is explicit
- [ ] Exposure posture is clear

## Band gate

- [ ] Band 1 slice is read-only
- [ ] Band 2 slice is the only writable slice under active rollout
- [ ] Band 3 rollout has separate explicit approval

## Admin/tool-bearing gate

- [ ] If this is an admin-first slice, the admin-first ordering is respected
- [ ] The admin shell remains the only stable landing surface
- [ ] The tool registry/launcher owns discoverability and launch resolution
- [ ] No direct tool route bypasses the shell
- [ ] AWS precedes Maps and Maps precedes AGRO-ERP where relevant

## Decision

- Result: `approved_for_build` / `blocked` / `approved_for_exposure`
- Test commands:
- Runtime entrypoint review:
- Blocking items:
- Notes:
