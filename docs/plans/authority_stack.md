# Authority Stack

This file is the single precedence source for MyCiteV2.

## Precedence order

1. [../ontology/structural_invariants.md](../ontology/structural_invariants.md)
2. [../decisions/](../decisions/)
3. [phases/](phases/) and [phase_completion_definition.md](phase_completion_definition.md)
4. [v1-migration/](v1-migration/)
5. Legacy v1 planning and wiki snapshots under [../V1/](../V1/) (subordinate to items 1–4; migration and drift evidence only)
6. v1 code as implementation-history evidence only

## Resolution rule

When two sources conflict, the higher-precedence source wins. The lower-precedence source must be updated, annotated, or ignored.

## Required links

This file must be linked from:

- `MyCiteV2/README.md`
- every phase doc
- every major-root `README.md`
- `docs/contracts/module_contract_template.md`
- `docs/plans/v1-migration/README.md`
