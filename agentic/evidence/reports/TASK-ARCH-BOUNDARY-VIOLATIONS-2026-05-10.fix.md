# Fix Report: Architecture Boundary Violations

**Task:** TASK-ARCH-BOUNDARY-VIOLATIONS-2026-05-10  
**Date:** 2026-05-10  
**Status:** Complete

---

## Changes Applied

| File | Change |
|---|---|
| `MyCiteV2/packages/core/scalars.py` | Created — canonical home for `as_text`, `as_dict`, `as_list`, `as_dict_list` |
| `packages/state_machine/portal_shell/shell_composition.py:7` | `modules.shared.scalars` → `core.scalars` |
| `packages/state_machine/portal_shell/shell_registry.py:5` | `modules.shared.scalars` → `core.scalars` |
| `packages/state_machine/portal_shell/shell_request.py:14` | `modules.shared.scalars` → `core.scalars` |
| `packages/state_machine/portal_shell/shell_state.py:12` | `modules.shared.scalars` → `core.scalars` |

`shared/scalars.py` is retained unchanged — two `instances/` callers depend on it
and are not restricted by the boundary rule.

---

## Verification

```
test_state_machine_boundaries: 2/2 PASS
Full portal suite: 115 tests, 0 failures, 19 skipped
```

---

## Acceptance

- [x] AC-1: Four forbidden imports identified (all `as_text` from `shared.scalars`)
- [x] AC-2: `shared.scalars` documented — 4 coercion utilities; 6 callers total
- [x] AC-3: Fix strategy: move to `core/scalars.py` (canonical primitive layer)
- [x] AC-4: Risk assessed — zero behavior change; `instances/` callers unaffected
- [x] AC-5: `test_state_machine_boundaries` passes after fix
