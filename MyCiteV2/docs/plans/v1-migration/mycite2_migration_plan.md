# MyCite2 Migration Plan

Authority: [../authority_stack.md](../authority_stack.md)

This file keeps the historical title `MyCite2` only because it names a preexisting synthesis surface. In v2 prose, the normalized term is `MyCiteV2`.

This document supersedes [historical/3-Migration.md](historical/3-Migration.md).

## Migration rule

Migration means recreation under v2 ontology, not relocation of v1 files.

## Ordered migration posture

1. Fix ontology and authority first
2. Recreate pure core
3. Recreate shell/state-machine contracts
4. Define ports
5. Recreate domain and cross-domain modules
6. Implement adapters
7. Recreate tools
8. Recreate sandboxes as orchestration
9. Compose runtime
10. Run integration and boundary checks
11. Review v1 retirement

## Hard cuts

- Do not import v1 modules into v2.
- Do not preserve ambiguous names when the ontology has been clarified.
- Do not let compatibility wrappers define v2 structure.
