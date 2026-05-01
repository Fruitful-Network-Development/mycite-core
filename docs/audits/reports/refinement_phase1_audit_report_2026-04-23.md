# Refinement Phase 1 Audit Report

Date: 2026-04-23

Doc type: `audit-report`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-23`

## Initiative and Task Mapping

- Initiative: `INIT-REFINEMENT-PHASE1`
- Task board: `docs/plans/refinement_phase1_task_board.yaml`
- Covered tasks:
  - `TASK-REFINE-P1-001`
  - `TASK-REFINE-P1-002`
  - `TASK-REFINE-P1-003`
  - `TASK-REFINE-P1-004`

## Canonical Contract Anchors

- `docs/contracts/tool_operating_contract.md`
- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`
- `docs/contracts/portal_vocabulary_glossary.md`
- `docs/plans/one_shell_portal_refactor.md`

## Task 1 Findings: Separate Authorities (Shell vs Directive vs Lens)

### Verified alignment

- Shell ownership is clearly constrained to route synchronization, region orchestration, directive dispatch, and first-load posture ownership.
- Runtime ownership is clearly constrained to canonical state, canonical query/url projection, and region payload generation.
- Widget/UI ownership is presentation-only and explicitly non-authoritative.

### Drift or under-definition

- The articulation asks for a canonical "directive script" authority, but current NIMM implementation only validates one shell verb (`navigate`) and does not yet implement full script semantics.
- The articulation asks for a formal lens abstraction; current repo uses lens-like terms (`workbench_lens`, overlay/lens modes) without one shared codec contract.
- Compatibility aliases for `inspector` remain active; this is intentional but still a terminology surface that can blur Interface Panel naming if not normalized in follow-on passes.

## Task 2 Findings: NIMM Package Inspection

### Current implementation

- `MyCiteV2/packages/state_machine/nimm/directives.py` defines:
  - `DEFAULT_SHELL_VERB = "navigate"`
  - `SUPPORTED_SHELL_VERBS = ("navigate",)`
  - `normalize_shell_verb(...)` that rejects non-`navigate` verbs.
- `MyCiteV2/packages/state_machine/nimm/README.md` explicitly states `investigate`, `mediate`, and `manipulate` are deferred.

### Cross-surface evidence of deferred semantics

- `MyCiteV2/packages/state_machine/portal_shell/shell.py` enumerates `navigate`, `investigate`, `mediate`, `manipulate` at shell-state level.
- CTS-GIS carries `nimm_directive` as tool-local state label and control-panel context, but this is not a fully versioned cross-tool NIMM script grammar.

## Task 3 Findings: CTS-GIS Runtime and SAMRAS Staging Survey

### Tool-local state evidence

- CTS-GIS request/runtime normalization includes:
  - `tool_state.nimm_directive`
  - `tool_state.active_path`
  - `tool_state.selected_node_id`
  - `tool_state.aitas.*`
  - `tool_state.source.*`
  - `tool_state.selection.*`
  - `tool_state.staged_insert`
- Runtime action kinds are constrained to:
  - `stage_insert_yaml`
  - `validate_stage`
  - `preview_apply`
  - `apply_stage`
  - `discard_stage`

### Mutation ownership boundary evidence

- Interface renderer (`v2_portal_inspector_renderers.js`) dispatches action requests from stage buttons and does not write SQL/files directly.
- Runtime action handler (`portal_cts_gis_runtime.py`) routes stage/validate/preview/apply/discard to `CtsGisMutationService`.
- Authoritative apply path persists via SQL mutation adapter (`replace_authoritative_document`) through mutation service and runtime action handling.

### SAMRAS posture evidence

- CTS-GIS structural navigation remains SAMRAS-derived and tool-local.
- Stage/preview/apply workflow is explicit and additive to shell contracts, preserving the shell non-authoritative posture.

## Task 4 Findings: Glossary and Mismatch Log

- Published: `docs/plans/refinement_phase1_glossary_2026-04-23.md`
- Major normalization targets:
  - clarify `NIMM directive script` vs shell `verb`;
  - formalize shared `Lens` abstraction;
  - keep `Interface Panel` as canonical term while compatibility aliases remain;
  - keep tool-local AITAS distinct from any future shared AITAS contract.

## Phase 1 Completion Verdict

Phase 1 audit and documentation objectives are complete.

- All phase 1 tasks are marked `done` in `docs/plans/refinement_phase1_task_board.yaml`.
- Evidence artifacts exist for each task acceptance criterion.
- No shell-authority regression was found in the audited surfaces.
- Primary remaining gaps are foundational (phase 2): canonical NIMM script schema, AITAS wrapper contract, and shared Lens abstraction.
