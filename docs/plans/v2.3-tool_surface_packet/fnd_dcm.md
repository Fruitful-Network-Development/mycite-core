# FND-DCM

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Canonical name: `FND-DCM`\
Packet role: `family_root`\
Queue posture: `typed family plan only`\
Primary future gate target: `tool_exposure.fnd_dcm`

## Completion intent

`FND-DCM` is the bounded digital-content and site-design family for hosted
sites.

It is distinct from `FND-EBI`:

- `FND-DCM` owns manifest-backed editing and preview/promote behavior
- `FND-EBI` owns operational visibility for hosted sites and services

## Core V2.3 position

`FND-DCM` should complete as one bounded manifest-editing family, not as a
generic page builder or raw file browser.

Its core rules are:

- shell legality remains shell-owned
- `tool_exposure` remains visibility-only
- rendered pages are projections, not source truth
- edits apply to declared slots only
- draft and stable state stay separate
- promotion to stable is explicit, auditable, and read-after-write confirmed

## Stable authority model

The family should separate:

- stable site manifest authority
- draft site manifest authority
- profile-content overlays for declared editable slots
- derived render/build outputs

Derived previews, built pages, and caches must never become the authority
source.

## First completion sequence

### Slice 1 — manifest inspection and preview

Read-only.

Must provide:

- manifest inspection
- rendered preview
- editable-slot overlay metadata
- stable-vs-draft visibility

### Slice 2 — draft editing

Bounded write.

Must provide:

- draft-only slot editing
- bounded text edits
- allowed image/icon selection
- draft validation
- local audit emission for accepted draft writes

### Slice 3 — promote to stable

Bounded write.

Must provide:

- promotion workflow
- validation before promotion
- read-after-write confirmation
- rollback or repair guidance

## Do not carry forward

Do not carry forward:

- a freeform WYSIWYG page builder
- direct browser-to-live-filesystem mutation
- raw HTML editing as the primary model
- a generic analytics or operations dashboard hidden inside the design tool
