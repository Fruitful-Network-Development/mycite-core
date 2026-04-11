# Architecture Boundary Checks

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This file defines the checks future automation must enforce.

## Required checks

1. Import boundary check
   - Fail if inward layers import outward layers.
2. Shell ownership check
   - Fail if tool or adapter code defines shell-state truth.
3. Datum authority check
   - Fail if utility JSON or derived artifacts are treated as datum truth.
4. Instance-path leakage check
   - Fail if reusable logic embeds live instance paths or instance ids.
5. Derived-artifact write check
   - Fail if payload binaries or caches are written as source truth.
6. Naming drift check
   - Fail if forbidden synonyms replace glossary terms in authoritative docs.
7. Sandbox role check
   - Fail if sandbox code owns domain semantics instead of orchestration.

## Evidence sources for the initial rule set

- [../contracts/tool_state_and_datum_authority.md](../contracts/tool_state_and_datum_authority.md)
- [../contracts/repo_and_runtime_boundary.md](../contracts/repo_and_runtime_boundary.md)
- [../plans/version-migration/v1_drift_ledger.md](../plans/version-migration/v1_drift_ledger.md)
- [../plans/legacy/v1-tool_dev.md](../plans/legacy/v1-tool_dev.md)
