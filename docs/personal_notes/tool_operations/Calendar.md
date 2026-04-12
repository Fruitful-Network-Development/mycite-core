# Calendar

Canonical name: `Calendar`  
Tool family posture: `new V2.3 family`  
Primary exposure: `default app in every portal`  
Primary read/write posture: `read-only first`

## 1. Completion intent

`Calendar` should be the default chronological app in every portal.

Its primary authority model should be chronological and event-log based, using:

- `System_logs.json` as the primary event/document source you specified
- HOPS chronological structure as the primary viewing structure
- chronological interpretation first
- no SAMRAS dependency for the core calendar viewing model

## 2. Source basis

Repo-native sources investigated:

- `docs/wiki/legacy/hops/homogeneous_ordinal_partition_structure.md`
- `docs/plans/post_mvp_rollout/slice_registry/band1_operational_status_surface.md`
- `docs/plans/post_mvp_rollout/slice_registry/band1_audit_activity_visibility.md`
- `docs/contracts/tool_exposure_and_admin_activity_bar_contract.md`

Important note:

- `System_logs.json` as the primary input source was not found as a current repo-native calendar contract during this investigation.
- It is therefore treated here as a user-defined required authority source that should be formalized by the future tool docs and slice files.

## 3. Core V2.3 position

`Calendar` should be one chronological family rooted in HOPS-style ordered time partitions.

This means:

- the primary viewing structure is chronological subdivision
- the core structure is HOPS, not SAMRAS
- event documents are projected into HOPS-governed chronological views
- the calendar is not just a grid widget; it is a chronological inspection family

## 4. Stable source-of-truth model

### 4.1 Primary source
`System_logs.json` and related declared chronological event documents should be the primary input family.

### 4.2 Structural authority
HOPS chronological structure should define how time is partitioned and viewed.

### 4.3 Derived views
Rendered calendars, timelines, grouped activity cards, and chronological summaries are derived projections only.

## 5. Family behavior

The first complete `Calendar` family should provide:

- chronological overview
- recent chronological event visibility
- event grouping by HOPS-defined chronology
- drill-down from larger to smaller chronological partitions
- read-only activity/event projection first

Examples of valid views:

- high-level time partition view
- recent activity window
- chronological timeline
- partition drill-down
- day or scope-level event summaries

## 6. Relationship to other families

`Calendar` should not be collapsed into:

- local audit as a root tool
- generic status as a root tool
- AGRO-ERP chronology
- Maps

Instead:

- local audit and status can supply events or summaries into Calendar
- AGRO-ERP may use chronology as a supporting lens
- Calendar remains the default generic chronological app

## 7. Completion slices

### Slice 1 — read-only chronological event view
The first required slice.

It should:

- read from declared system-log/event sources
- interpret chronology through HOPS
- render chronological partitions and recent event summaries
- avoid any write workflow

### Slice 2 — bounded drill-down and filtering
Later read-only expansion.

### Slice 3 — bounded annotations or user-facing chronology actions
Only later if explicit write semantics are defined.

## 8. Why not SAMRAS

The HOPS source investigated makes the distinction clear:

- SAMRAS reconstructs variable shape
- HOPS defines ordered subdivision

For a default calendar app, your stated requirement is correct: use HOPS as the primary chronological viewing structure, not SAMRAS.

## 9. Do not carry forward

Do not carry forward:

- ad hoc time handling with no governing chronological structure
- generic grid-only calendar semantics as the core model
- a second shell for chronology
- treating AGRO or Maps chronology as the portal-wide default chronology family
- unformalized event sources with no declared authority

## 10. Acceptance boundary

`Calendar` is complete when:

- one read-only chronological slice exists
- `System_logs.json` or the declared event source family is formalized
- HOPS chronology governs partitioning and drill-down
- Calendar can serve as the default chronological app in every portal

## 11. Recommended V2.3 landing statement

Create `Calendar` as one portal-wide chronological family with HOPS chronology as its primary structure and `System_logs.json` as its first declared event source, then expand it through read-only chronological slices before any write features are considered.
