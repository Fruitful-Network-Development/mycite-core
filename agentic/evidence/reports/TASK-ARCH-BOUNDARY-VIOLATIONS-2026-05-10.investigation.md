# Investigation Report: Architecture Boundary Violations

**Task:** TASK-ARCH-BOUNDARY-VIOLATIONS-2026-05-10  
**Date:** 2026-05-10  
**Status:** Complete — fix approved for immediate implementation

---

## Finding

All four boundary violations reduce to **a single one-line import in each file**:

```python
from MyCiteV2.packages.modules.shared.scalars import as_text
```

| File | Line |
|---|---|
| `packages/state_machine/portal_shell/shell_composition.py` | 7 |
| `packages/state_machine/portal_shell/shell_registry.py` | 5 |
| `packages/state_machine/portal_shell/shell_request.py` | 14 |
| `packages/state_machine/portal_shell/shell_state.py` | 12 |

---

## What shared.scalars Contains

`MyCiteV2/packages/modules/shared/scalars.py` defines four scalar coercion utilities:

```python
def as_text(value: object) -> str        # None → "", else str(v).strip()
def as_dict(value: Any) -> dict          # non-dict → {}
def as_list(value: object) -> list       # non-list → []
def as_dict_list(value: object) -> list  # list of dicts only
```

Only `as_text` is imported by the four violating files. The other three utilities
are not used in the portal_shell package.

---

## All Callers of shared.scalars

Six files total; only the four in state_machine are boundary violations:

| File | Layer | Violation? |
|---|---|---|
| `packages/state_machine/portal_shell/shell_composition.py` | state_machine | **YES** |
| `packages/state_machine/portal_shell/shell_registry.py` | state_machine | **YES** |
| `packages/state_machine/portal_shell/shell_request.py` | state_machine | **YES** |
| `packages/state_machine/portal_shell/shell_state.py` | state_machine | **YES** |
| `instances/_shared/runtime/portal_system_workspace_runtime.py` | instances | no |
| `instances/_shared/runtime/portal_workbench.py` | instances | no |

The `instances/` files importing `shared.scalars` are not restricted — the boundary
rule only applies to `packages/state_machine` importing from `packages/modules`.

---

## Correct Home

`as_text` is a primitive scalar coercion utility with zero dependencies. It belongs
in `packages/core/`, which is the layer permitted to be imported by all other layers
including state_machine.

An identical implementation already exists at
`packages/core/structures/samras/structure.py:7-8` but is not exported — evidence
that this function has been independently re-created rather than shared.

**Fix:** Create `packages/core/scalars.py` as the canonical home for scalar
coercion utilities. The full `shared/scalars.py` content is copied here so that
`instances/` callers can also migrate to the canonical path over time without a
second refactor.

---

## Minimal Change

| Action | Files affected |
|---|---|
| Create `packages/core/scalars.py` (31 lines, copy of shared/scalars.py) | 1 new file |
| Update import in each of the 4 violating portal_shell files (1 line each) | 4 files |

`shared/scalars.py` is **not deleted** — the two `instances/` callers continue
to import from it, and removing it would be a separate cleanup task.

---

## Risk Assessment

- **Zero behavior change.** `as_text` implementation is byte-for-byte identical.
- **No circular imports.** `core/` has no imports from state_machine or modules.
- **No caller changes** beyond the 4 violating files.
- **instances/ callers unaffected** — they still import from shared.scalars.
- **No test fixture impact** — the function behavior is unchanged.
