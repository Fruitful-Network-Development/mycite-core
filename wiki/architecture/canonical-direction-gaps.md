# Canonical Direction Gaps

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Architecture](README.md)

## Status

Living audit

## Purpose

Track implementation-risk areas where legacy behavior, recent changes, and canonical direction can diverge. This page is an architectural guardrail, not a backlog.

## Current High-Risk Couplings

1. **SSR vs runtime directive posture**
   - Risk: server-rendered shell context can default to `navigate` while runtime enters mediation via query launch.
   - Canonical direction: initial shell verb must follow launch contract (`mediate` for `?mediate_tool`).

2. **Selection-event precedence across endpoints**
   - Risk: different field-order precedence (`shell_verb` vs `current_verb`) causes inconsistent compatibility outcomes.
   - Canonical direction: one deterministic verb resolver shared by selection and sandbox context routes.

3. **Auto workbench emissions overriding tool mediation**
   - Risk: anthology bootstrap selection (`auto_init`) replaces tool-layer state unexpectedly.
   - Canonical direction: event provenance is mandatory and lock-aware; auto events cannot override tool-layer mediation.

4. **Permissive sandbox compatibility matching**
   - Risk: config-context tools can appear in contexts that are not true tool-layer surfaces.
   - Canonical direction: sandbox compatibility requires explicit `shell_surface=tool_mediation` + `mediation_scope=system_sandbox`.

## Items Not Fully Canonicalized Yet

- **Per-tool unlock policy granularity**
  - Current direction: explicit user selection can unlock tool-layer mediation.
  - Open detail: whether unlock policy should be globally fixed or tool-specific (`strict`, `soft`, `none`).

- **Activity-bar saturation policy**
  - Current direction: first-class tool entries are allowed.
  - Open detail: thresholds/ordering when many tools are enabled (overflow, grouping, pinning rules).

These are acceptable temporary ambiguities; implementers must document chosen policy when changing shell/tool routing.

