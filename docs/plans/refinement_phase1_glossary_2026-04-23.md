# Refinement Phase 1 Glossary

Date: 2026-04-23

Doc type: `glossary`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-23`

## Purpose

Define the canonical terminology required by `docs/plans/refinement.md` phase 1 and record where current repo language still diverges.

## Canonical Terms

- `Shell`
  - Meaning: host orchestration for route, visibility/posture, and region-family projection.
  - Boundary: no authoritative data mutation.
  - Primary anchors: `docs/contracts/tool_operating_contract.md`, `docs/contracts/portal_shell_contract.md`.

- `Runtime`
  - Meaning: canonical state and contract execution authority.
  - Boundary: owns canonical query/url projection and authoritative mutation handlers.
  - Primary anchors: `docs/contracts/tool_operating_contract.md`, `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`.

- `Directive Script (NIMM script)`
  - Meaning: canonical mutation instruction artifact describing verb, target, and intent context.
  - Current state: shell verb validation is implemented only for `navigate` in `MyCiteV2/packages/state_machine/nimm/directives.py`.
  - Gap: no full script grammar for `investigate`, `mediate`, and `manipulate`.

- `AITAS context`
  - Meaning: interpretation envelope (attention, intention, time, archetype, scope) surrounding directives.
  - Current state: CTS-GIS carries AITAS tool-local state in request/runtime `tool_state`.
  - Gap: no shared dataclass/contract that wraps canonical NIMM scripts cross-tool.

- `Lens`
  - Meaning: stateless codec overlay that decodes/validates/encodes user-facing forms.
  - Current state: "lens" appears as tool-specific display toggles and overlays (for example `workbench_lens` and CTS-GIS overlay mode).
  - Gap: no shared `Lens` abstraction contract in state-machine/runtime packages.

- `YAML stage`
  - Meaning: non-authoritative staging payload where editable values are captured before apply.
  - Current state: CTS-GIS stage uses `tool_state.staged_insert` plus action route operations.
  - Boundary: stage is not authoritative until runtime apply succeeds.

- `Validate / Preview / Apply / Discard`
  - Meaning: explicit mutation pipeline verbs for staged edits.
  - Current state: implemented for CTS-GIS via action kinds `validate_stage`, `preview_apply`, `apply_stage`, `discard_stage`.
  - Boundary: renderer dispatches actions only; runtime/service executes authoritative updates.

## Normalization Targets Identified in Phase 1

- Replace generic "verb" references with explicit `NIMM directive` language where mutation semantics are intended.
- Keep `inspector` only as compatibility alias and prefer `Interface Panel` in active docs/code comments.
- Avoid describing `workbench_lens` as mutation logic; treat it as display codec behavior.
- Distinguish "tool-local AITAS" from "shared shell AITAS" until a unified contract is introduced.
- Treat CTS-GIS stage flow as a mutation contract seam, not as the final cross-tool NIMM grammar.
