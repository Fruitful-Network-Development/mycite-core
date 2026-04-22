# MOS SG-4 Standard Closure and Compatibility Retirement Policy

Date: 2026-04-21

Doc type: `policy`  
Normativity: `supporting`  
Lifecycle: `completed`  
Last reviewed: `2026-04-22`

## Purpose

Close `SG-4` from `docs/plans/master_plan_mos.md` by defining the formal criteria for declaring native MOS closure and the rules for retiring compatibility-only semantics.

## Native MOS Closure Criteria

Native MOS may be declared decision-complete only when all of the following are true:

1. `SG-1`, `SG-2`, and `SG-3` have published closure artifacts.
2. The active SQL adapter and its regression suite implement the published version-identity, hyphae, and edit/remap policies.
3. `docs/plans/master_plan_mos.md` no longer carries unresolved Track B semantic claims.
4. `docs/plans/mos_semantic_gate_register_2026-04-21.md` records all four gates as closed.
5. Compatibility-only forms are explicitly enumerated with retirement conditions.
6. The Track A SQL cutover evidence remains green for the approved authority surfaces.

## Compatibility Retirement Rules

Compatibility-only behavior may be retired only in this order:

1. Detect
   - the form is identified in docs and runtime warnings or audit output
2. Freeze
   - new writes in that form are blocked or normalized into canonical form
3. Migrate
   - authoritative content is rewritten or proven absent in active inventories
4. Retire
   - active runtime handling is removed, while at least one offline migration/import path remains for historical recovery

Retirement readiness requires all of the following:

1. no active authoritative documents depend on the compatibility form in the latest audited inventory
2. canonical rewrite coverage exists or the form is proven absent
3. regression coverage proves canonical behavior without the compatibility path
4. one retained report or migration artifact records the change and rollback posture

## Current Compatibility-Only Forms

- hyphen-qualified local refs in mutation surfaces
- historical MSS/file-naming assumptions that are not proven equivalent to `mos.mss_sha256_v1`

## Relationship to Track C

- Track C is not a blocker for native MOS closure under this policy.
- Directive-context widening remains a later design/spec decision and does not reopen Track B once the semantic closure artifacts are published.

## Evidence

- `docs/plans/mos_sg1_version_identity_policy_2026-04-21.md`
- `docs/plans/mos_sg2_hyphae_derivation_policy_2026-04-21.md`
- `docs/plans/mos_sg3_edit_remap_policy_2026-04-21.md`
- `MyCiteV2/tests/adapters/test_sql_datum_store_adapter.py`

## Closure Statement

`SG-4` is closed for current repo truth because the closure checklist, compatibility retirement sequence, and non-blocking relationship to Track C are now explicit.
