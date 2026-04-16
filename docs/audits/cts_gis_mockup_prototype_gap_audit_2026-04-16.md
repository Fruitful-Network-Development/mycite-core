# CTS-GIS Mockup/Prototype Implementation Gap Audit (2026-04-16)

## Scope

This audit explains why recent CTS-GIS commits did not fully implement the mockup design and the prototype behavior documented in:

- `docs/personal_notes/CTS-GIS-prototype-mockup/hover-expand-nested.html`
- `docs/personal_notes/CTS-GIS-prototype-mockup/hover-expand-log-nav.html`
- `docs/personal_notes/CTS-GIS-prototype-mockup/ordered_hierarchy_navigation.md`

It also evaluates alignment with SAMRAS-driven structural navigation and hierarchy behavior inside the active portal runtime.

## Findings summary

1. **Recent commits implemented naming/contract convergence more than interaction parity.**
   - The portal now consistently emits a dual-section CTS-GIS interface contract (`Diktataograph` + `Garland`) with a compact context strip and narrow-layout fallback.
   - But the implemented UI behavior still reflects card/grid rendering and request-button interaction, not the prototype's continuous hover redistribution model.

2. **The core prototype behavior is explicitly disabled in runtime output.**
   - Runtime emits `feature_flags.hover_attention_redistribution = False`, so the renderer does not activate enhanced hover redistribution paths.

3. **SAMRAS navigation is structurally present, but interaction depth is capped by intention defaults.**
   - Default intention is `descendants_depth_1_or_2` and render sets are built from constrained descendants rather than open-ended recursive, attention-graded expansion.

4. **Hierarchy is represented as discrete lists/path cards, not as an attached recursive hover continuum.**
   - The current hierarchy is rendered as anchored path entries and branch clusters.
   - Prototype hierarchy calls for compressed-full-range visibility, local expansion by attention, speed-sensitive focus widening, and recursive subordinate rails.

5. **Testing currently validates surface contract shape and vocabulary, not prototype dynamics.**
   - Existing tests assert contract keys/tokens (`layout`, `narrow_layout`, `garland_split_projection`, intention token values), but do not verify motion model behavior (hover speed effect, graded compression, recursive subordinate reveal).

## Evidence and commit-by-commit diagnosis

### A) Prototype introduction was isolated from runtime integration

The prototype files define dynamic interaction locally in standalone HTML/JS:

- `hover-expand-log-nav.html` implements log-like focus falloff and speed-modulated expansion over a dense rail.
- `hover-expand-nested.html` adds anchored selection and subordinate continuation panels.
- `ordered_hierarchy_navigation.md` states the core model: preserve full ordered context at rest, redistribute finite space around attention, recurse into subordinate hierarchy, and vary focus spread by pointer speed.

These files are conceptual/reference artifacts; they are not wired into portal runtime renderers.

### B) “Mockup-aligned” commits delivered contract language and sectional composition

The CTS-GIS runtime now returns a composed interface body with:

- `layout = dual_section`
- `narrow_layout = context_diktataograph_garland_stack`
- `navigation_canvas` (Diktataograph)
- `garland_split_projection` (Garland)

This is visible in runtime bundle construction and aligns with updated shell contract docs.

### C) Why behavior still misses prototype parity

#### 1) Hover redistribution flag is hard-disabled

Runtime sets:

- `feature_flags.hover_attention_redistribution: False`

The inspector renderer only binds navigation-canvas enhancement when this flag is true. Therefore, prototype-like enhancement paths are not active in the running UI.

#### 2) Existing enhancement path is limited even if enabled

`bindNavigationCanvasEnhancement` only changes `--cts-gis-nav-weight` for sibling node buttons in branch entry lanes. It does **not** implement:

- whole-rail compression-at-rest with full sequence visibility,
- speed-based spread widening/narrowing,
- attached subordinate panel recursion with bridge continuity,
- continuous geometric redistribution across all hierarchy levels.

So, current implementation is a local weighting tweak, not the prototype's generalized ordered-hierarchy navigation model.

#### 3) SAMRAS attention pipeline is bounded by intention token logic

Service defaults and normalization center on:

- `_DEFAULT_INTENTION_TOKEN = descendants_depth_1_or_2`,
- fallback to self/children/branch token behavior,
- render set generation from bounded descendant ranges.

This achieves stable SAMRAS-driven mediation but narrows exploration behavior compared with prototype expectations of dynamic recursive expansion over dense ordered sets.

#### 4) Seed behavior can degrade to first sorted profile when default root is absent

Document summaries mark SAMRAS seed status (`ready`/`missing`), but when canonical default is absent, the runtime chooses the first sorted profile as default attention node. This keeps the interface operational but can drift from strict “canonical seed first” orientation during mismatch cases.

#### 5) CSS/DOM architecture favors card/grid readability over rail mechanics

The current CTS-GIS CSS builds a two-pane card layout (`cts-gis-interface__body`, `cts-gis-structureCanvas`, `cts-gis-garlandSplit`) with branch clusters and lists. That supports legibility and shell consistency, but not the prototype's dense logarithmic/continuous rail mechanics.

## SAMRAS and hierarchy implications

- **What is aligned:**
  - SAMRAS-defined address space is represented in `navigation_canvas` and linked to correlated projection in `garland_split_projection`.
  - Diktataograph drives attention/intention updates, and Garland follows selected navigation root.

- **What is not aligned with prototype behavior:**
  - Hierarchy is not being treated as a continuously redistributing attention field.
  - No speed-aware attention spread, no subordinate rail recursion, no finite-space redistribution model as primary interaction law.

In short: the repo currently materializes **SAMRAS data contract + section composition**, but not the **prototype interaction engine**.

## Root causes (systemic)

1. **Delivery focus skewed toward contract stabilization** (terminology, shell compatibility, maps-to-cts-gis cleanup) over interaction model implementation.
2. **Prototype artifacts were treated as reference notes** without a tracked engineering bridge spec from prototype JS primitives to portal renderer/runtime state.
3. **Feature gating without activation plan** (`hover_attention_redistribution` remains false).
4. **Test strategy validates structure, not dynamics** (shape-level assertions pass while behavior-level parity remains unimplemented).
5. **UI architecture optimized for deterministic cards/lists** rather than animation/stateful continuous navigation fields.

## What must change to achieve true mockup/prototype parity

1. **Introduce a first-class navigation interaction state model** in CTS-GIS interface body (hover index/position, speed factor, spread, anchor path stack, recursive lane descriptors).
2. **Turn prototype mechanics into renderer primitives** (continuous rail layout function, recursive subordinate rail mounting, bridge continuity drawing).
3. **Activate and harden feature flag path** (`hover_attention_redistribution`) with staged rollout.
4. **Expand intention semantics** so SAMRAS mediation can support “continuous hierarchy browsing” mode in addition to current tokenized render modes.
5. **Add behavioral tests** that verify:
   - full-range visibility-at-rest,
   - local expansion/compression under hover,
   - speed-sensitive spread change,
   - recursive subordinate continuation,
   - Garland synchronization with active anchored node.

## Bottom line

Past commits did not “fail” to implement CTS-GIS; they successfully implemented **contractual and sectional shell integration**. They failed specifically at implementing the **interaction mathematics and recursive hierarchy behavior** defined by the prototype HTML5 references.

The gap is therefore not vocabulary or SAMRAS presence; it is the missing translation from prototype interaction model to production renderer/runtime state machinery.
