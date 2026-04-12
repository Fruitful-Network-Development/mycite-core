# FND-DCM

Canonical name: `FND-DCM`  
Working expansion: `Digital Content Manager`  
Tool family posture: `new V2.3 family`  
Primary exposure: `internal-admin` first, later bounded `trusted-tenant` sub-slices  
Primary read/write posture: `bounded-write`

## 1. Completion intent

`FND-DCM` is the manifest-backed web design and digital content tool for hosted sites. Its job is to make page composition stable without requiring manual intervention in served files, while still allowing bounded editing of content and selected media.

This tool is distinct from `FND-EBI`.

- `FND-DCM` owns how a hosted site is composed and edited.
- `FND-EBI` owns what is happening operationally for that site.

## 2. Source basis

Repo-native constraints used here:

- `docs/plans/v2-authority_stack.md`
- `docs/ontology/structural_invariants.md`
- `docs/contracts/tool_exposure_and_admin_activity_bar_contract.md`
- `docs/plans/v2.3-tool_exposure_and_admin_activity_bar_alignment.md`
- `docs/plans/post_mvp_rollout/post_aws_tool_platform/future_tool_drop_in_contract.md`
- `docs/plans/post_mvp_rollout/post_aws_tool_platform/read_only_and_bounded_write_patterns.md`
- `docs/plans/post_mvp_rollout/slice_registry/band2_profile_basics_write_surface.md`

User-defined completion requirements used here because no current repo-native `FND-DCM` tool brief was found during investigation:

- stable site design should come from a canonical site `manifest.json`-style source
- rendered pages are projections, not the source of truth
- editing should happen in a contained rendered preview
- hover highlights should expose editable features
- edits should update draft JSON, not the live served state
- only explicit save/promote should become the new stable served version
- per-profile editing should be able to change bounded text and choose allowed images/icons for declared positions
- target sites called out: `trappfamilyfarm.com` and `cuyahogavalleycountrysideconservancy.org`

## 3. Core V2.3 position

`FND-DCM` should complete as a bounded manifest-editing family, not as a generic page builder.

That means:

- shell legality remains shell-owned
- config gating remains visibility-only
- the rendered DOM is never canonical truth
- live served assets are not directly edited from the browser
- the tool edits declared manifest slots only
- draft and stable state are separate
- promotion to stable is explicit, auditable, and read-after-write confirmed

## 4. Stable source-of-truth model

### 4.1 Stable design truth

Every hosted site controlled by this tool should have one canonical stable design manifest.

That stable manifest must own:

- section order
- slot identities
- allowed slot kinds
- layout variants
- declared asset positions
- references to allowed image/icon pools
- references to profile-editable text/media slots
- render options required to build the served page

### 4.2 Draft design truth

Editing does not mutate the stable manifest directly.

Instead, the mutable authoring surface is a draft manifest that may include:

- draft section changes
- draft slot values
- draft layout variant selections
- draft selected asset refs
- draft profile-bound content overlays

### 4.3 Derived artifacts

These are derived only:

- rendered preview output
- frontend build products
- page HTML projections
- caches
- thumbnails
- transformed assets

Derived artifacts must never become the authority source.

## 5. Content model

`FND-DCM` should separate three layers.

### 5.1 Site manifest layer

The structural layer that defines what the page may contain.

### 5.2 Profile content layer

Bounded values for slots that the manifest explicitly marks as profile-editable, such as:

- titles
- summaries
- body snippets
- button labels
- selected image or icon from an allowed pool

Profile content may fill slots. It may not redefine page structure.

### 5.3 Render projection layer

The layer that composes stable or draft manifest state with allowed content and assets to produce preview or served output.

## 6. Editor interaction model

### 6.1 Rendered preview

The preview should render the page in a contained tool surface that uses manifest state, not arbitrary live DOM scraping.

### 6.2 Hover highlights

Hover highlights are allowed only over declared editable slots.

Each selectable overlay should be backed by structured slot metadata such as:

- `slot_id`
- `slot_kind`
- `editable_scope`
- `current_source`
- `allowed_actions`

Editability must not be inferred from arbitrary HTML structure.

### 6.3 Slot editors

Selecting a slot opens a bounded editor by slot kind.

Examples:

- `text` -> constrained text editor
- `image` -> asset chooser limited to an allowed pool
- `icon` -> icon chooser limited to an allowed set
- `variant` -> bounded variant selector only if the manifest explicitly permits it

### 6.4 Save actions

There are only two meaningful writes:

- `save_draft`
- `promote_to_stable`

`save_draft` updates draft state only.

`promote_to_stable` validates the draft, writes the stable manifest, emits audit records, and updates the served projection.

## 7. Stable data roots

The exact storage paths can evolve, but the authority shape should be:

- stable site manifest
- draft site manifest
- allowed asset catalog
- bounded profile-content overlays
- build/projection outputs
- local audit trail

The storage scheme must separate stable, draft, and derived outputs.

## 8. Completion slices

### Slice 1 — manifest inspection and preview
Read-only.

Must provide:

- manifest inspection
- rendered preview
- editable-slot overlay metadata
- stable vs draft status visibility

### Slice 2 — draft editing
Bounded write.

Must provide:

- slot editing against draft only
- bounded text edits
- image/icon selection from approved sets
- draft validation
- local audit emission for accepted draft writes

### Slice 3 — promote to stable
Bounded write.

Must provide:

- stable promotion workflow
- validation before promotion
- read-after-write confirmation
- rollback or repair instructions
- build/projection refresh

### Slice 4 — tenant-scoped profile editing
Later follow-on.

Must provide:

- only profile-editable slots
- no structural editing
- narrower audience and field bounds than internal-admin authoring

## 9. Do not carry forward

Do not let this tool become:

- a second shell
- a freeform WYSIWYG page builder
- a raw HTML editor
- an analytics dashboard
- a generic file browser
- a catch-all CMS for unrelated content
- config-owned routing or legality
- direct browser-to-live-filesystem mutation

## 10. Acceptance boundary

`FND-DCM` is complete only when:

- a site can be rendered from canonical manifest data
- draft editing stays bounded to declared slots
- stable serve state changes only through explicit promotion
- profile editing is limited to declared profile-editable positions
- read-after-write and audit requirements exist for every accepted write
- the browser never becomes the source of truth

## 11. Recommended V2.3 landing statement

Treat `FND-DCM` as one bounded-write digital-content family with a manifest-backed preview-and-promote model. Do not split design editing, asset choosing, and profile-bound content editing into separate root tools.
