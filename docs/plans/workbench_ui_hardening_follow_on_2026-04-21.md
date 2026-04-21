# Workbench UI Hardening Follow-On

Date: 2026-04-21

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-21`

## Purpose

Define the next minimal hardening steps for `workbench_ui` as the canonical datum-file workbench surface without turning it into a heavy or parallel frontend stack.

## Current Baseline

- `workbench_ui` is the canonical datum-file workbench surface for SQL-backed inspection.
- The left pane is a document table keyed by `version_hash`.
- The right pane is a layered datum table for the selected anchor file or source document.
- Each datum row exposes structural coordinates: `layer`, `value_group`, and `iteration`.
- The inspector is the current workbench lens for selected datum-row detail and additive overlay summary.
- The surface is shell-attached, script-backed, read-only, and additive-only.

## Constraints

- Keep the datum-file workbench shell-attached.
- Keep it script-backed and query-driven.
- Keep it read-only.
- Keep overlays additive-only.
- Do not introduce a parallel frontend framework.
- Prefer small query-contract or payload-shape additions over large client-state systems.

## Follow-On Work

### 1. Keyboard navigation

Goal:

- let operators move through the document table and layered datum table without requiring pointer-only interaction

Minimal shape:

- add runtime-owned next/previous selection actions for document and datum-row movement
- keep navigation query-driven so shell state and direct routes stay aligned
- cover row and document movement in runtime tests

### 2. Frozen headers and clearer selection state

Goal:

- keep the document table and layered datum table readable during longer scroll sessions

Minimal shape:

- add sticky header intent in the surface payload for both panes
- add explicit selected-document and selected-datum-row markers in the payload rather than implying row focus only through the inspector
- keep selection clarity text-first and utilitarian

### 3. Layer/value-group grouping options

Goal:

- make the layered datum table easier to scan without changing datum-row order

Minimal shape:

- add optional grouping modes such as `flat`, `layer`, and `layer_value_group`
- preserve structural-coordinate sort within each grouping mode
- keep grouping reversible and query-driven

### 4. Raw versus interpreted workbench lens

Goal:

- let operators switch the workbench lens between canonical raw payloads and the current interpreted row summary

Minimal shape:

- add a `workbench_lens` query key with `interpreted` and `raw`
- keep interpreted mode close to the current `labels` / `relation` / `object_ref` surface
- keep raw mode grounded in the canonical datum-row payload rather than an expanded mutation editor

### 5. Semantic identity badges

Goal:

- make `version_hash` and `hyphae_hash` easier to scan as identifiers instead of long plain strings

Minimal shape:

- keep full values available in the workbench lens and inspector
- add short badge-style summaries in the document table, layered datum table, and control-panel context
- do not hide the full canonical values behind hover-only behavior

### 6. Source and overlay visibility controls

Goal:

- let operators simplify the datum-file workbench without losing grounded source or overlay context

Minimal shape:

- keep the existing additive overlay visibility control
- add source-visibility controls for source metadata columns or sections
- keep visibility state query-driven so it can be shared, reproduced, and tested

### 7. Saved filters and sorts only if they remain simple

Goal:

- support recurring inspection patterns without creating a heavy preference system

Minimal shape:

- treat saved filters/sorts as named query bundles only
- keep persistence script-grounded and optional
- defer this step until keyboard navigation, selection clarity, grouping, workbench-lens, and visibility controls are complete

## Non-Goals

- no datum-row mutation controls
- no WYSIWYG editor posture
- no standalone SPA or secondary frontend framework
- no widening of directive-context authority beyond additive summaries

## Verification

- extend `MyCiteV2.tests.unit.test_workbench_ui_runtime` as features land
- keep `MyCiteV2.tests.contracts.test_contract_docs_alignment` green if query vocabulary or contract language changes
- keep doc/reference integrity tests green when new datum-file workbench docs are added

## Result

The next datum-file workbench steps are now bounded and utilitarian: better navigation, clearer table posture, better workbench-lens control, and clearer identity/source visibility without changing the shell-attached, script-backed, read-only nature of `workbench_ui`.
