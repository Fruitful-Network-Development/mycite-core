# Workbench UI Hardening Follow-On

Date: 2026-04-21

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-22`

## Canonical Contract Links

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`
- `docs/contracts/portal_vocabulary_glossary.md`

## Purpose

Define the next minimal hardening steps for `workbench_ui` as the SQL authority inspector surface under `SYSTEM` without turning it into a heavy or parallel frontend stack.

## Current Baseline

- `SYSTEM` remains the canonical anthology-centered datum-file workbench at `/portal/system`.
- `workbench_ui` is the separate shell-attached SQL authority inspector for authoritative document inspection under `SYSTEM`.
- fresh `workbench_ui` entry deliberately prefers a CTS-GIS authoritative document when one is available and falls back to the first available authoritative document otherwise.
- The left pane is a document table keyed by `version_hash`.
- The right pane is a layered datum table for the selected authoritative document.
- Each datum row exposes structural coordinates: `layer`, `value_group`, and `iteration`.
- The inspector is the current workbench lens for selected datum-row detail and additive overlay summary.
- Query-driven next/previous navigation actions and Arrow Up/Down keyboard selection are present for document and row movement.
- Sticky headers, explicit selected-document/selected-row markers, grouping modes, raw/interpreted lens switching, identity badges, and source/overlay visibility controls are present in the deployed runtime and covered by tests.
- The surface is shell-attached, script-backed, read-only, and additive-only.

## Constraints

- Keep the SQL authority inspector shell-attached.
- Keep it script-backed and query-driven.
- Keep it read-only.
- Keep overlays additive-only.
- Do not repurpose `/portal/system` into a database manager.
- Do not introduce a parallel frontend framework.
- Prefer small query-contract or payload-shape additions over large client-state systems.

## Remaining Follow-On Work

### 1. Saved filters and sorts only if they remain simple

Goal:

- support recurring inspection patterns without creating a heavy preference system

Minimal shape:

- treat saved filters/sorts as named query bundles only
- keep persistence script-grounded and optional
- defer this step unless it remains lighter than the already-shipped query-driven navigation, grouping, lens, identity, and visibility baseline

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

The current deployed `workbench_ui` already ships the minimal navigation, table-posture,
lens, identity, and visibility hardening targeted in this pass. Remaining follow-on scope
is now limited to optional saved query bundles, and only if they stay simple,
script-grounded, and clearly subordinate to the existing shell-attached, read-only role.
