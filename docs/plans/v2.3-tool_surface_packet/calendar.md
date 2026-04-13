# Calendar

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Canonical name: `Calendar`\
Packet role: `family_root`\
Queue posture: `typed family plan only`\
Primary future gate target: `tool_exposure.calendar`

## Completion intent

`Calendar` is the portal-wide chronological family.

It should become the default chronological app across portals, with
chronological interpretation owned by declared event sources plus HOPS-style
time partitioning rather than by ad hoc grid UI behavior.

## Core V2.3 position

`Calendar` should remain one chronology family.

It should not be collapsed into:

- generic status
- local audit as a root tool
- AGRO-ERP chronology
- Maps

Other families may feed it events or supporting lenses, but they do not replace
it as the default chronology family.

## Stable authority model

The first declared authority family is chronological event documents, with
`System_logs.json` treated as the current user-defined lead source until a
typed repo contract formalizes that source family.

Chronological partitioning should remain HOPS-governed.

Rendered calendars, timelines, grouped cards, and drill-down summaries are
derived projections only.

## First completion sequence

### Slice 1 — read-only chronological event view

Must provide:

- declared event-source reads
- HOPS-governed chronological partitioning
- recent event summaries
- read-only chronological drill-down

### Slice 2 — bounded drill-down and filtering

Later read-only expansion.

### Slice 3 — bounded annotations or chronology actions

Later only if explicit write semantics are approved.

## Do not carry forward

Do not carry forward:

- grid-only calendar semantics as the core model
- a second shell for chronology
- unformalized event sources with no declared authority
- treating AGRO or Maps chronology as the portal-wide default chronology family
