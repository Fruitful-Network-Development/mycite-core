# Deep Audit of Corrections for **mycite‑core**

This audit compares each **articulation point** provided by the user with the current state of the Fruitful‑Network‑Development/mycite‑core repository. Evidence from the repository is cited to highlight where the current design already aligns with the articulated concept and where refactoring is needed. The audit is followed by a **comprehensive prompt** that can be given to a coding agent to implement the necessary refactoring and testing in incremental passes. The goal is to unify development and close conceptual gaps **without forcing a major redesign**.

Phase 1 execution artifacts (2026-04-23):

- `docs/plans/refinement_phase1_task_board.yaml`
- `docs/plans/refinement_phase1_glossary_2026-04-23.md`
- `docs/audits/reports/refinement_phase1_audit_report_2026-04-23.md`

Phase 2 execution artifacts (2026-04-23):

- `docs/plans/refinement_phase2_task_board.yaml`
- `docs/audits/reports/refinement_phase2_foundation_report_2026-04-23.md`

Phase 3 execution artifacts (2026-04-23):

- `docs/plans/refinement_phase3_task_board.yaml`
- `docs/audits/reports/refinement_phase3_implementation_report_2026-04-23.md`

Phase 4 execution artifacts (2026-04-23):

- `docs/plans/refinement_phase4_task_board.yaml`
- `docs/audits/reports/refinement_phase4_validation_report_2026-04-23.md`

## 1 Separate Authorities – shell vs directive vs lens

### Audit

* **Shell authority:** The tool operating contract states that the shell has **fixed responsibilities**: orchestrating routes, posture and region visibility, and projecting directive outputs. It explicitly declares that the shell does *not* mutate authoritative state; runtime does that, while surfaces only view state[\[1\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/tool_operating_contract.md#L15-L91). This matches the first part of the articulation: the shell owns route, posture and region orchestration.

* **Directive script:** Currently nimm only implements the navigate verb; the other verbs (investigate, mediate, manipulate) are deferred[\[2\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/packages/state_machine/nimm/README.md#L7-L17). There is **no definition of a general directive script**, so the mutation authority is missing. The portal\_shell code lists verbs but does not define a directive grammar[\[3\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/packages/state_machine/portal_shell/shell.py#L75-L84).

* **Lens layer:** The repo refers to the interface panel and its components, but there is no explicit “lens” abstraction outside of the CTS‑GIS tool where lens\_type is used to select projections. The design track for directive context notes that context overlays are read-only and separate from mutation[\[4\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/plans/mos_directive_context_design_track_2026-04-21.md#L29-L37), but the concept of a **lens** as a codec overlay remains under‑defined. The audit confirms the need to **formalise lenses** as UI codec overlays that transform data but do not decide operations.

### Implications

Refactoring should enforce three separate authority layers: 1\. **Shell** – route, posture, region orchestration; never mutates state. 2\. **Directive script** – canonical representation of intended state changes; needs to be defined for NIMM beyond navigate. 3\. **Lens** – codec overlay for human‑readable transforms; must not contain mutation logic.

## 2 *NIMM* as Canonical Mutation Instruction

### Audit

* The nimm package currently supports **only navigate**; investigate, mediate and manipulate are deferred[\[2\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/packages/state_machine/nimm/README.md#L7-L17). There is no **formal definition** of a NIMM directive grammar in code or docs. NIMM values in CTS‑GIS tool state are simply string labels ("nav") used to choose a UI mode but not compiled into a mutation script.

* The portal shell exposes a manipulate verb in the enumeration but does not implement it[\[3\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/packages/state_machine/portal_shell/shell.py#L75-L84).

### Implications

A proper NIMM mutation script (e.g., YAML or JSON schema) must be defined. It should capture the intended operation (nav/inv/med/man), the target authority and datum, and remain separate from UI state. This script will be the canonical input for the runtime to perform authoritative changes.

## 3 *AITAS* as Interpretation Envelope

### Audit

* The **directive context** design track describes an overlay keyed by version\_hash or hyphae\_hash that conveys context such as attention and intention but does not mutate authoritative data[\[4\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/plans/mos_directive_context_design_track_2026-04-21.md#L29-L37). This corresponds to the AITAS concept (Attention, Intention, Time, Archetype, Scope). The CTS‑GIS tool currently maintains aitas fields in its local state to express context, but they are not integrated into a cross‑tool model.

* There is no unified AITAS class or contract to wrap NIMM directives and provide interpretation context.

### Implications

Refactoring should define an AITAS data structure that wraps a NIMM directive, carrying interpretation metadata. It must be used for projection (preview/apply) but must not itself perform mutation. This aligns with the design track.

## 4 Lenses as Codec Overlays

### Audit

* The repository uses the term **interface panel** for UI surfaces. CTS‑GIS defines lens\_type to choose between overlays like hex\_bin, highlight, profile etc., but does not formalise a general lens interface.

* The tool operating contract and portal refactor plan emphasise that surfaces **present state** and do not mutate it[\[1\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/tool_operating_contract.md#L15-L91). However, there is no explicit separation between **lens** (encoding/decoding) and **widget** (presentation). This conflation can lead to mutation logic creeping into UI code.

### Implications

Introduce a **lens abstraction** that performs only decoding, formatting, validation and re‑encoding of data. Lenses must not decide operations; they simply provide human‑readable views and accept user edits that will later be compiled into a NIMM directive by the runtime.

## 5 The Staging Boundary

### Audit

* The **workbench UI** is currently **read‑only**[\[5\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/route_model.md#L108-L140). There is no support for editing cell values or staging. CTS‑GIS has some UI for editing samras structures, but these are tool‑specific and not compiled into a general mutation script.

* The tool operating contract emphasises that the workbench remains read-focused unless a separate mutation contract exists[\[1\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/tool_operating_contract.md#L15-L91). However, the user indicates a need for a general staging layer where human edits produce staged values that are normalised by lenses and then compiled into a NIMM manipulation script. This mechanism does not yet exist.

### Implications

Implement a **staging boundary**: user edits go into a staging area (e.g., YAML stage) attached to rows. Lenses normalise these values into canonical raw data. The runtime compiles these raw units into a NIMM script, which is the only object that can change state. This will close the gap between the read‑only workbench and the desired mutation workflow.

## 6 UI Reflectivity and Non‑inference

### Audit

* The route model states that the client must not infer transitions from edited cells; instead, the control panel returns the legal next directives, and the client renders them[\[6\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/route_model.md#L142-L168). This implies UI reflectivity: the UI should show the current state, staged delta and legal next directives, but the client does not determine legality.

* The portal shell contract emphasises that the control panel is the legal transition plane and transitions are not inferred client‑side[\[7\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/portal_shell_contract.md#L32-L46).

### Implications

UI surfaces should render state and preview/apply information provided by runtime. They must not guess or enforce transitions based on local heuristics. All legal transitions come from the runtime after evaluating the NIMM directive in context.

## 7 Region Roles for Mutation‑capable Tools

### Audit

* The tool operating contract defines three canonical region families (Reflective Workspace / Workbench, Directive Panel / Control Panel, Presentation Surface / Interface Panel)[\[1\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/tool_operating_contract.md#L15-L91). It states that the workbench remains read‑focused, the control panel manages legal actions, and the interface panel hosts the editing surfaces. This aligns with the proposed roles.

* The portal shell contract enumerates region family IDs and emphasises that only workbench\_primary can be open by default; other tools are interface‑panel‑led and read‑only[\[7\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/portal_shell_contract.md#L32-L46).

### Implications

The existing region roles match the articulation. Future mutation tools must respect these boundaries: control panel owns NIMM/AITAS state and action dispatch; workbench holds authoritative rows and previewed deltas; interface panel holds staged editing surfaces with lenses. Implementation must avoid bleeding mutation UI into the shell.

## 8 Cell Editing vs Canonical Data Model

### Audit

* The Workbench UI is read‑only; there is no cell editing mechanism[\[5\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/route_model.md#L108-L140). This means cell edits currently cannot occur, which is safe but prevents mutation.

* The articulation emphasises that **cell editing** should be a **staging convenience** for operators, while the canonical mutation object remains the NIMM directive. This aligns with the design track and ensures the grid itself is not the write protocol.

### Implications

Implement cell editing purely as a staging affordance. It should update the staging area, not the authoritative data, and must flow through lenses and NIMM compilation before any state change.

## 9 Define Mutation Contract Separate from Read Contract

### Audit

* The route model lists read routes and states that actions like navigate operate via GET requests; there is **no contract** for stage, validate, preview, apply or discard operations[\[6\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/route_model.md#L142-L168). The portal shell contract notes that mutation actions must be separate and treat the workbench as read‑only unless a separate contract exists[\[1\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/tool_operating_contract.md#L15-L91).

* This confirms the need for a **distinct mutation contract**: endpoints for staging and applying changes, including validation and preview.

### Implications

Design and implement a mutation contract (API endpoints and runtime handlers) for tools that can mutate authority. This contract should support staging, validating, previewing, applying and discarding NIMM directives. Read surfaces continue to use the existing read contract.

## 10 Minimum Grammar of a *NIMM* Script

### Audit

* The repository lacks a defined grammar for NIMM manipulation scripts. The docs and code mention nimm\_directive with values like "nav", but there is no schema to specify directive, target authority, datum addresses, etc.

* The user proposes a grammar with directive (nav, inv, med, man), conceptual target, AITAS context, and target addresses following the MOS 'file' naming convention.

### Implications

Define a minimal grammar for NIMM scripts. At a minimum, include:

* verb (directive type: nav, inv, med, man),

* target\_authority / document,

* AITAS context or reference to default context,

* targets array using the MOS file/datum address convention. This grammar should be versioned and validated by runtime.

## 11 CTS‑GIS as Structural Attention Investigation

### Audit

* The CTS‑GIS runtime uses nimm\_directive \= nav and aitas to hold local state for *attention* and *investigation* over SAMRAS structures. It does **not perform mutation**; it just controls navigation and projections[\[6\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/route_model.md#L142-L168). The design track emphasises that directive context can shape navigation or mediation posture without performing mutation[\[4\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/plans/mos_directive_context_design_track_2026-04-21.md#L29-L37).

### Implications

Keep CTS‑GIS as a structural attention investigation tool. It should maintain tool-local state for navigation and possibly mediation but must not attempt to mutate data. When mutation is needed (e.g., editing SAMRAS), it should output a NIMM manipulation directive to the separate mutation contract rather than performing mutation directly.

## 12 SAMRAS Expansion as Compound Directive

### Audit

* SAMRAS (spatial magnitude) updates in CTS‑GIS are currently implemented with ad‑hoc UI actions. The code sets samras\_active flags and updates selected\_node\_id without a formal directive grammar. The user proposes distinguishing between structure space mutation (expanding SAMRAS) and datum mutation.

### Implications

Extend the NIMM grammar to support **compound directives**: one directive for structure space mutation (e.g., expanding SAMRAS to introduce new node addresses) and subsequent directives for ordinary datum insertion or modification. The runtime should treat these as separate steps with validation and preview phases.

## 13 Source/Supporting Evidence vs Mutation Subject

### Audit

* The route model distinguishes between supportive evidence (e.g., geospatial overlays, profile material) and the mutation subject. Evidence can help form or validate a staged mutation but is not itself mutated unless explicitly targeted[\[6\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/route_model.md#L142-L168).

### Implications

Ensure that workbench and interface surfaces can display evidence (maps, profiles, GeoJSON overlays) without confusing them with mutation subjects. Mutation contracts should operate only on the specified targets; evidence remains read-only unless included in the directive.

## 14 Terminology Normalisation

### Audit

* The portal refactor plan encourages **terminology hardening** and a single shell model[\[8\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/plans/one_shell_portal_refactor.md#L21-L42). The articulation proposes consistent terms: “Interface Panel” instead of “inspector”; “lens” for codecs; “NIMM directive script” for mutations; “AITAS context”; “Yaml stage”; “apply”.

### Implications

Rename variables, docs and UI labels to reflect consistent terminology. Avoid conflating lens, directive and surface. This aligns with the repository’s ongoing refactor.

---

## Comprehensive Agent Prompt

**Objective:** unify the mycite‑core portal stack by implementing the above articulation points without discarding the current design. Work iteratively in **passes**: first audit and document, then refactor code and docs, then implement tests, minimising disruption. Below is your step‑by‑step brief.

### Phase 1 – Audit and Documentation

1. **Review code and docs** for existing authority boundaries and region roles. Confirm that the shell only orchestrates routes and region visibility and that runtime is the only state-changing layer[\[1\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/tool_operating_contract.md#L15-L91). Identify where mutation logic has crept into UI code or where lenses mix with directives.

2. **Inspect the nimm package**. Note that only the navigate verb is implemented[\[2\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/packages/state_machine/nimm/README.md#L7-L17). Document places where other verbs (investigate, mediate, manipulate) appear but lack implementation[\[3\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/packages/state_machine/portal_shell/shell.py#L75-L84).

3. **Survey CTS‑GIS runtime** for local state keys (e.g., nimm\_directive, aitas) and current SAMRAS editing flows. Confirm that no mutation is performed and that nimm\_directive is just a label[\[6\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/route_model.md#L142-L168).

4. **Create a glossary** summarising proper terminology: Interface Panel, Workbench, Control Panel; lens; directive script; NIMM directive; AITAS context; YAML stage; preview/apply. Compare with existing docs and note mismatches[\[8\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/plans/one_shell_portal_refactor.md#L21-L42).

### Phase 2 – Define Foundations

1. **Design a minimal NIMM directive schema**. Define fields: verb (nav, inv, med, man), target\_authority or document, an optional AITAS context block (with attention, intention, time, archetype, scope), and targets list using MOS file/datum address conventions. Express this schema in JSON/YAML and implement dataclasses in the state\_machine/nimm package. Provide validators and versioning.

2. **Define an AITAS wrapper**. Create a dataclass for AITAS context that can wrap a NIMM directive. It must store metadata for interpretation but must not perform mutations. Add utilities to merge default context with overrides.

3. **Introduce a lens abstraction**. Define an abstract Lens class that performs decoding, formatting, validation and encoding of data units. Lenses convert between human‑readable forms and canonical raw units. They must be stateless and not decide operations. Identify existing per-tool lenses (e.g., geospatial overlays) and refactor them to inherit from Lens.

4. **Design a staging layer**. Implement a YamlStage or StagingArea that stores user‑edited values keyed by row/datum address. Edits in the interface panel update this stage via lenses. Create functions to compile staged raw units into a NIMM manipulation script (one directive per row or compound directives). Ensure this stage is separate from the authoritative workbench data.

5. **Specify a mutation contract**. Draft API endpoints and runtime handlers for stage, validate, preview, apply, and discard. Read surfaces stay the same; mutation endpoints accept NIMM scripts and return preview states. Only the apply endpoint performs an authoritative change; it returns the updated state and resets the stage.

### Phase 3 – Refactor Implementation

1. **Refactor portal\_shell** to recognise the new NIMM directive grammar and AITAS wrapper. Update the verbs enumeration to tie into the new schema. Ensure the shell remains narrow; it should only dispatch directives to runtime and manage region visibility.

2. **Update state\_machine/nimm** to implement the directive schema and provide functions for creating, serialising and validating NIMM scripts. Implement stub handlers for investigate, mediate, and manipulate verbs; these can raise NotImplemented until their semantics are defined.

3. **Refactor CTS‑GIS runtime**. Move any mutation logic (e.g., SAMRAS expansions) out of the UI layer. On user actions, update the staging layer through a lens and compile a NIMM script. Pass this script to the mutation contract for preview/apply. Keep the existing navigation and investigation flows intact[\[4\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/plans/mos_directive_context_design_track_2026-04-21.md#L29-L37).

4. **Implement the staging UI** in the interface panel. For each editable cell, use a lens to convert between display and canonical forms. When the user edits, update the staging area. Provide controls (buttons) to stage, validate, preview, and apply the compiled NIMM script. Show preview diffs in the workbench.

5. **Create compound directive support** for SAMRAS. Define directives for structure-space mutations (e.g., expanding SAMRAS) separate from datum insertions. When a user triggers SAMRAS expansion, build a NIMM directive with verb=man and a target address representing the structure space. After preview and apply, allow ordinary datum mutation directives to follow.

6. **Normalize terminology** across the codebase and docs. Rename variables and UI labels to match the glossary. Update contract documents (tool\_operating\_contract.md, route\_model.md, etc.) to describe the new directive grammar, lens concept, staging layer and mutation contract. Retain backwards compatibility by noting that existing read routes remain unchanged.

### Phase 4 – Testing and Validation

1. **Write unit tests** for the NIMM directive parser and validator. Ensure that all required fields are validated and invalid scripts are rejected. Add tests for AITAS merging and lens transformations.

2. **Add integration tests** for the staging layer and mutation contract. Simulate user edits, stage values, compile NIMM scripts, preview changes, and apply them. Verify that the workbench displays the correct authoritative rows after apply and that staged values are cleared.

3. **Test CTS‑GIS flows**. Ensure that navigation and investigation still work and that SAMRAS expansions operate via NIMM directives. Confirm that the UI reflects staged deltas and preview/apply states without inferring transitions client‑side[\[7\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/portal_shell_contract.md#L32-L46).

4. **Review documentation**. After implementing the refactor, update all relevant docs (contracts, readme files) with examples of NIMM directives, AITAS contexts, lens definitions and mutation contract usage. Make sure the docs emphasise the three separate authorities and the staging boundary.

### Notes

* Work iteratively: complete each phase with code, tests and documentation before moving to the next. Use version control to commit logical units separately.

* Avoid large redesigns; build on the existing shell, runtime and SQL-backed workbench. Keep read routes untouched; only add new mutation pathways.

* Always return to the guiding principle that **authoritative state changes occur only through validated NIMM manipulation scripts interpreted within the current AITAS context**, projected back through the control panel, workbench and interface panel.

---

[\[1\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/tool_operating_contract.md#L15-L91) tool\_operating\_contract.md

[https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/tool\_operating\_contract.md](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/tool_operating_contract.md)

[\[2\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/packages/state_machine/nimm/README.md#L7-L17) README.md

[https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/packages/state\_machine/nimm/README.md](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/packages/state_machine/nimm/README.md)

[\[3\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/packages/state_machine/portal_shell/shell.py#L75-L84) shell.py

[https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/packages/state\_machine/portal\_shell/shell.py](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/MyCiteV2/packages/state_machine/portal_shell/shell.py)

[\[4\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/plans/mos_directive_context_design_track_2026-04-21.md#L29-L37) mos\_directive\_context\_design\_track\_2026-04-21.md

[https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/plans/mos\_directive\_context\_design\_track\_2026-04-21.md](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/plans/mos_directive_context_design_track_2026-04-21.md)

[\[5\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/route_model.md#L108-L140) [\[6\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/route_model.md#L142-L168) route\_model.md

[https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/route\_model.md](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/route_model.md)

[\[7\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/portal_shell_contract.md#L32-L46) portal\_shell\_contract.md

[https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/portal\_shell\_contract.md](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/contracts/portal_shell_contract.md)

[\[8\]](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/plans/one_shell_portal_refactor.md#L21-L42) one\_shell\_portal\_refactor.md

[https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/plans/one\_shell\_portal\_refactor.md](https://github.com/Fruitful-Network-Development/mycite-core/blob/main/docs/plans/one_shell_portal_refactor.md)