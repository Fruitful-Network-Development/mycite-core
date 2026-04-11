# ROI 02 — Shell Region Contracts

## Objective

Turn current workbench and inspector `kind` behavior into an explicit, documented V2 contract so new tool surfaces do not require rediscovery through runtime and JS code.

## Why this is high ROI

The repo now has a real V2 shell-composition path, but much of the region contract still lives implicitly across `admin_runtime.py` and `v2_portal_shell.js`. That makes future work slower and more error-prone.

This area yields high return because it reduces ambiguity for:

- portal surface additions
- new tool surfaces
- agent prompts
- review and verification work
- future modularization of rendering

## Scope

Primary files and authorities:

- `MyCiteV2/docs/ontology/interface_surfaces.md`
- `MyCiteV2/docs/ontology/structural_invariants.md`
- `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py`
- `MyCiteV2/instances/_shared/runtime/admin_runtime.py`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell.js`

## Deliverables

1. A contract doc, for example:
   - `MyCiteV2/docs/contracts/shell_region_kinds.md`
2. An enumeration of valid `workbench.kind` values.
3. An enumeration of valid `inspector.kind` values.
4. Required fields per kind.
5. Valid composition modes per kind.
6. Guidance for how new tools add a new kind without redefining shell truth.

## Definition of done

This ROI area is complete when:

- every currently used workbench kind is documented
- every currently used inspector kind is documented
- field requirements are explicit
- shell ownership versus renderer responsibility is explicit
- the document is linked from relevant portal/shell docs

## Suggested implementation shape

Document at least these categories:

- shell composition mode
- active surface semantics
- region ownership
- workbench kinds
- inspector kinds
- fallback/error semantics
- tool registration expectations
- rendering responsibilities versus shell responsibilities

## Task classification

`repo_only`

## Agent execution plan

### Lead

- scope the contract doc task tightly
- list exact source files to mine for current kinds
- require the doc to reflect current repo truth, not archive notes

### Implementer

- extract all current kinds and fields from runtime and renderer
- write the contract doc
- add links from nearby docs where appropriate
- keep the doc aligned with authority stack and interface surface rules

### Verifier

- compare the contract doc to current runtime and JS behavior
- flag any kind present in code but absent in docs
- flag any documented kind not present in code unless intentionally planned

## Required evidence pattern

- Current kinds found in code
- Contract doc created or updated
- Mismatches remaining
- Final verdict
