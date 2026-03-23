# Development Declaration: SYSTEM as a Reflective Directive/Context State Machine

## Status of this declaration

This document is a **development declaration** for the `SYSTEM` page and its surrounding shell/runtime model. It is not a narrow implementation note. It is intended to serve as a durable framing document for ongoing refactor passes so that incremental work continues to converge toward the same backbone.

This declaration exists because the target is not merely a cleaned-up UI. The target is a system whose UI becomes a **reflective projection of state**, where the state is defined in terms of canonical datum attention, directive, and contextual facets, and where future development can compound without reintroducing alternate interaction models.

This declaration is therefore intentionally broader than the presently implemented feature set. It states the direction that development should continue to enforce, even where some axes remain incomplete today.

## Purpose

The purpose of this declaration is to establish that:

- the `SYSTEM` page is not to be treated as a collection of separate views, tabs, or tool-specific sub-applications
- the `SYSTEM` page is to be treated as one canonical **stateful workbench**
- the stateful workbench is to be driven by:
  - **attention**
  - **directive**
  - contextual facets such as **archetype** and **time**
  - mutation/edit posture
- UI elements are to be understood as **projections of state**, not as isolated page widgets
- future implementation passes should increase the fidelity of this state machine rather than add parallel logic paths

The goal is directional as much as immediate: even where the full machine is not yet complete, development should move toward a form where the axes can come together through compounding passes instead of fragmenting further.

---

## Core declaration

The `SYSTEM` runtime shall be developed as a **state machine over canonical MSS-addressable attention targets**.

At any given moment, the system’s attention shall not be on “the page” in an abstract sense. The system’s attention shall always resolve to an addressable subject. That subject may be:

- a **file**
- a **datum** in that file
- a **facet** of that datum

The active directive shall determine how the system is permitted to interface with the current subject.

This means the `SYSTEM` page is not fundamentally organized around:
- tabs
- alternate page surfaces
- tool-specific shells
- separate “anthology” vs “resources” interaction models

Instead, it is organized around:
- the current attention target
- the current directive
- the current contextual interpretation of the subject
- the UI projection that follows from those values

---

## Guiding principles

### 1. The workbench is canonical

The center `SYSTEM` workbench is the canonical operator surface.

There is not to be a separate user-facing ontology for:
- anthology mode
- resources mode
- inheritance mode
- AGRO-specific mini-app pages

These may continue to exist internally as compatibility routes, data authorities, storage distinctions, or provider capabilities, but they are not to be allowed to define the visible interaction model.

### 2. State precedes UI

The UI is not primary.

The correct development sequence is:

1. define state
2. define transitions
3. define guards
4. define derived UI projections

The incorrect sequence is:

1. create a widget or view
2. add conditional logic
3. later try to explain what state it implies

### 3. Direction matters, even when incomplete

Not every axis is fully developed today. That is acceptable.

However, incompleteness must not be treated as permission to introduce an alternate conceptual model. Development should prefer:
- placeholders over contradictions
- scaffolding over silent divergence
- formally empty context values over ad hoc stand-ins

### 4. Compatibility is allowed; visible regression is not

Compatibility entry points may remain internally where necessary. However:
- they must normalize into the unified `SYSTEM` workbench
- they must not reappear as active visible product framing
- they must not define the conceptual model for new work

### 5. Tools are providers, not shells

Tools are not to be treated as alternate applications with independent page logic. Tools are mediation providers or capability providers operating within the unified shell and workbench model.

---

## The canonical subject model

The fundamental question is: **what is the system attending to?**

Attention is never on “the system page” itself.

If no datum is selected, attention is on the current file.
If a datum is selected, attention is on that datum.
If the user is interfacing with a facet of that datum, attention is on that facet.

This yields a canonical subject hierarchy:

- **file**
- **datum**
- **facet**

This hierarchy replaces earlier vague notions such as “page mode,” “view,” or “tab.”

---

## Attention model

### Declaration

The system shall use **attention** as a canonical state field.

Attention is the current subject of the machine.

### Legal attention forms

The recommended formal grammar is:

```text
file:<file_id>
datum:<file_id>/<datum_id>
facet:<file_id>/<datum_id>/<facet_kind>/<facet_ref?>
```

This grammar is intentionally more precise than a loose selected-file / selected-datum pair because it allows the model to grow without inventing new page categories.

### Meaning of each form

#### `file:<file_id>`
The system is attending to a canonical file as an address space of datums.

Examples:
- `file:anthology.json`
- `file:samras-txa.json`
- `file:samras-msn.json`

At this level:
- no datum is selected
- navigation operates across files or file-level structures
- mediation is only allowed if file-level mediation is intentionally defined
- manipulation operates at file scope, such as datum creation/deletion

#### `datum:<file_id>/<datum_id>`
The system is attending to one specific datum inside the current file.

At this level:
- the datum becomes the subject
- archetype context may now exist
- investigation can treat the datum as an object
- mediation can treat the datum in terms of its facets or relations
- manipulation can edit the datum

#### `facet:<file_id>/<datum_id>/<facet_kind>/<facet_ref?>`
The system is attending not just to the datum, but to a specific mediated aspect of that datum.

This is the more formal replacement for the intuitive notion of being “in a datum.”

At this level:
- the datum remains the parent subject
- the active interface is now oriented around a facet of the datum
- navigation may move across sibling facets or outward to the parent datum
- mediation becomes much more explicit and extensible

---

## Why the earlier “Spacial” field should be retired

Earlier thinking used a `Spacial` field to describe whether the system was:

- on a file
- on a datum
- in a datum

That concept was useful because it captured depth, but the term is too ambiguous and ends up doing conceptual work that is better handled by the attention model itself.

### Declaration

The field name `Spacial` should be retired from the canonical conceptual model.

### Replacement

Depth should be inferred from the canonical **attention address**:

- `file:*` = file-level attention
- `datum:*` = datum-level attention
- `facet:*` = facet-level attention

If a separate field is still needed temporarily for compatibility or debugging, it should be reframed as something like:
- `attention_plane`
- `focus_plane`
- `scope_level`
- `depth`

But the long-term model should prefer the fully qualified attention address over a loosely named parallel depth field.

---

## Directive model

Directive is a canonical state axis.

Directive is **not** the same thing as an event.
A click is an event.
The active directive is a current state value.

### Canonical directives

The current canonical directive set is:

- `navigate`
- `investigate`
- `mediate`
- `manipulate`

These are persistent shell verbs. They are not temporary buttons with isolated meanings.

### Directive meaning

#### `navigate`
`Navigate` governs movement through the address space.

Its purpose is to change position, scope, or subject.

Examples:
- change files
- move from file attention to datum attention
- move between sibling datums
- move from datum attention into a facet
- move outward from facet to datum
- move outward from datum to file

`Navigate` is therefore the directive of **positional movement**.

#### `investigate`
`Investigate` governs interaction with the current subject **as an object**.

It asks:
- what is this object?
- what is its abstraction path?
- what is its canonical MSS form?
- what does the system understand about it as an object in isolation or local placement?

This directive is object-facing.

For a datum, `Investigate` may provide:
- isolated abstraction path
- canonical compact-array representation
- local structural assumptions
- direct contextual interpretation of the datum as a datum

`Investigate` is therefore the directive of **object-oriented examination**.

#### `mediate`
`Mediate` governs interaction with the current subject through its:
- properties
- facets
- relations
- derived presentations
- meta-physical or meta-structural interpretations

This directive is not about “what is this object?” but rather:
- what aspect of it is being interfaced with?
- what relations does it have?
- what family/template does it imply?
- what sequences or derived forms can be surfaced?

Examples include:
- abstraction-path mediation
- archetype-family mediation
- sequential/value-stream mediation
- temporal mediation
- relation/coexistence mediation

`Mediate` is therefore the directive of **facet and relation interface**.

#### `manipulate`
`Manipulate` governs mutation.

At file attention, this means file-scoped structure changes such as:
- create datum
- delete datum

At datum attention, this means datum-scoped mutation such as:
- edit values
- alter associated structure
- stage or apply changes

At facet attention, it may eventually mean:
- editing a specific mediated representation
- editing a facet-specific projection

`Manipulate` is therefore the directive of **change**.

---

## Investigate vs Mediate

One of the most important distinctions to preserve is the difference between `Investigate` and `Mediate`.

### Investigate
Investigate interfaces with the attended subject as an actual object.

It is concerned with:
- identity
- direct abstraction
- structure of the datum itself
- canonical MSS representation
- the subject as a datum in a vacuum or in immediate local placement

### Mediate
Mediate interfaces with:
- aspects of the datum
- emergent properties
- relations to other datums
- family/template resemblance
- temporal or sequential projections
- provider-specific interpretations

### Declaration

This distinction should be preserved explicitly in future work.

When the system becomes muddled, it should ask:
- is this feature about the datum **as an object**?
- or is it about a **facet/property/relation** of the datum?

If it is the former, it belongs closer to `Investigate`.
If it is the latter, it belongs closer to `Mediate`.

---

## Context facets

Two contextual facets were explicitly identified as important:
- archetype context
- time context

These must not be treated as globally present at all times.

### Archetype context

There is no archetype context until a datum with an archetype becomes the subject of attention.

This means:
- at file attention, archetype context is absent
- at datum attention, archetype context may be:
  - unknown
  - unresolved
  - recognized
  - represented by a known family/template

Even when a datum’s archetype is unknown, the datum may still possess archetypal existence. The machine should therefore be able to distinguish:
- no archetype context because no datum is the subject
- archetype context exists but is currently unknown

### Time context

There is no time context unless time is actively being mediated.

This means:
- at file attention, time context is absent unless a file-level temporal mediation is explicitly defined
- at datum attention, time context remains absent unless the datum has entered time-oriented mediation
- at facet attention, time context becomes active only when the attended facet is explicitly temporal or sequence-temporal

### Declaration

Archetype and time are contextual axes that should be present only when made meaningful by the current attention target and directive.

They must not be populated merely to satisfy a UI strip.

---

## Recommended context fields

The recommended canonical context fields are:

- `attention`
- `directive`
- `archetype_context`
- `time_context`
- `mutation_mode`

A practical current form might be:

```text
attention         = file:* | datum:* | facet:*
directive         = navigate | investigate | mediate | manipulate
archetype_context = null | unknown | <archetype_id>
time_context      = null | <time_axis_descriptor>
mutation_mode     = view | edit
```

### Recommended semantics

#### `attention`
The current subject.

#### `directive`
The current interface posture.

#### `archetype_context`
The currently known or unknown archetype interpretation of the subject, if applicable.

#### `time_context`
The currently active temporal mediation context, if applicable.

#### `mutation_mode`
Whether the current interaction is in read/view posture or mutation/edit posture.

This is enough to support immediate work while leaving room for later refinement.

---

## Facet model

Facet attention is central to making the machine more rigorous.

### Why facet attention matters

Without a facet layer, the machine can only say:
- file
- datum

But your intended model clearly needs a deeper level where the system is no longer merely on a datum but is interfacing with one of its meaningful aspects.

This includes examples such as:

- abstraction path
- archetype family
- sequence of values
- time-based projection
- relation to surrounding datums

### Recommended initial facet kinds

The first closed facet set should likely be:

- `abstraction_path`
- `archetype`
- `sequence`
- `time`
- `relation`

These should be treated as initial first-class facet kinds for development.

### Notes on each facet kind

#### `abstraction_path`
This allows a datum to be treated in isolation through its abstraction chain or canonical MSS compact form.

#### `archetype`
This allows the system to interface with the datum through:
- family resemblance
- type template
- instance family
- possible creation of another instance of the same nature

#### `sequence`
This allows the system to interface with the ordered values that compose the datum’s sequence.

Examples:
- image frames -> video
- logic capture -> logic analyzer-style projection
- serial samples -> stream visualization

#### `time`
This allows the system to explicitly treat the datum or sequence in temporal terms, where time is not merely one more value, but the active mediation axis.

#### `relation`
This allows the system to consider how the datum coexists with or relates to other datums in the file or local address space.

---

## Navigation model

Navigation should not be thought of as page switching. It should be thought of as movement through attention space.

### File-level navigation
At file attention:
- side-to-side navigation moves across files or file-level structures
- inward navigation moves to a selected datum
- outward navigation may be undefined or remain on the file as root subject

### Datum-level navigation
At datum attention:
- side-to-side navigation moves across peer datums in the same attention plane
- inward navigation may move into a facet
- outward navigation returns to the file

### Facet-level navigation
At facet attention:
- side-to-side navigation moves across peer facets or peer values in the same mediated plane
- inward navigation may later move to deeper sub-facets if defined
- outward navigation returns to the datum

### Declaration

Long-term navigation should be understood as:
- inward
- outward
- lateral

not primarily as page mode switching.

---

## Mutation model

Mutation should remain directive-bound.

### File attention + Manipulate
At file attention under `Manipulate`, the system may:
- create datums
- delete datums
- alter file-level structure if later defined

This is where plus/minus affordances belong.

### Datum attention + Manipulate
At datum attention under `Manipulate`, the system may:
- edit datum values
- stage changes
- apply or publish changes according to file policy

This is where the right-side Details editor belongs.

### Facet attention + Manipulate
At facet attention under `Manipulate`, future development may allow:
- editing a facet-specific representation
- editing a derived sequence arrangement
- editing relation mappings

This should remain future-facing and not force a premature design today.

---

## File policies

The unified workbench still operates over multiple canonical files with different write policies.

This storage distinction remains valid.

### Canonical files
- `anthology.json`
- `samras-txa.json`
- `samras-msn.json`

### Policy distinction
- `anthology.json` may continue using direct write authority
- `samras-txa.json` and `samras-msn.json` may continue using staged mutate/publish flow

### Declaration

Storage or publish policy differences must not be allowed to fragment the visible state machine. They are backend capability distinctions, not alternate user-facing shells.

---

## Event model

The machine should be advanced by **events**.

Directive is state.
Event is what changes state.

### Recommended initial event set

- `load_system`
- `select_file(file_id)`
- `select_datum(datum_id)`
- `enter_facet(facet_kind, facet_ref?)`
- `exit_facet()`
- `clear_selection()`
- `set_directive(directive)`
- `begin_edit()`
- `commit_edit(payload)`
- `cancel_edit()`
- `create_datum(parent_context?)`
- `delete_datum(datum_id)`
- `stage_changes()`
- `publish_changes()`
- `activate_provider(provider_id)`
- `deactivate_provider()`

This is a practical event set large enough to formalize current and near-term work.

---

## Transition rules

### `load_system`
Initializes the machine.

Recommended result:
- create/load base anthology if absent
- set `attention = file:anthology.json`
- set `directive = navigate`
- set `archetype_context = null`
- set `time_context = null`
- set `mutation_mode = view`

### `select_file(file_id)`
Moves attention to a file.

Rules:
- datum or facet attention must be cleared
- active provider or mediated facet state should be cleared if incompatible
- resulting attention becomes `file:<file_id>`

### `select_datum(datum_id)`
Moves attention to a datum in the current file.

Rules:
- legal only if current attention is file-level or datum-level within same file
- resulting attention becomes `datum:<file_id>/<datum_id>`
- archetype context may now become `unknown` or a resolved archetype
- time context remains `null` unless explicitly activated

### `enter_facet(facet_kind, facet_ref?)`
Moves attention inward into a datum facet.

Rules:
- legal only from datum attention
- resulting attention becomes `facet:<file_id>/<datum_id>/<facet_kind>/<facet_ref?>`
- contextual fields may change depending on facet kind

### `exit_facet()`
Moves outward from facet attention to datum attention.

### `clear_selection()`
Returns attention outward.

Recommended rule:
- if at facet attention -> datum attention
- if at datum attention -> file attention
- if at file attention -> remain file attention

### `set_directive(directive)`
Changes the interface posture.

Rules:
- does not by itself change the attention target
- may change what actions are legal
- may change what the Details panel or workbench projection should show

### `begin_edit()`
Enters edit posture.

Rules:
- legal only under `directive = manipulate`
- should set `mutation_mode = edit`

### `commit_edit(payload)`
Applies mutation.

Rules:
- legal only under manipulate/edit posture
- backend side effect depends on file policy

### `create_datum(parent_context?)`
Creates a datum.

Rules:
- legal only under `directive = manipulate`
- usually from file attention or later approved parent context
- may create a new datum and optionally move attention to it

### `delete_datum(datum_id)`
Deletes a datum.

Rules:
- legal only under `directive = manipulate`
- if deleting current attention target, attention must reset outward appropriately

### `activate_provider(provider_id)`
Activates a mediation/tool provider.

Rules:
- should not replace shell state ownership
- should be legal only when compatible with the current attention target
- should generally operate under or through `directive = mediate`

### `deactivate_provider()`
Clears active provider mediation and returns to native mediation or neutral mediated state.

---

## Reset rules

Reset policy is critical because unclear resets cause drift.

### File change reset
When changing files:
- clear datum attention
- clear facet attention
- clear incompatible provider state
- clear time context
- clear archetype context
- return mutation mode to view unless deliberately preserved for a justified reason

### Datum exit reset
When exiting a datum back to file attention:
- clear facet attention
- clear archetype context
- clear time context
- return Details projection to file-level state

### Facet exit reset
When exiting a facet back to datum attention:
- clear facet-specific mediation state
- keep datum attention
- keep archetype context if still relevant
- clear time context if it was only facet-specific

### Directive change reset
Changing directives should not reset attention by default.
It should only reset:
- projections owned exclusively by the old directive
- illegal temporary state no longer compatible with the new directive

---

## Derived UI rules

The UI should be derived from the state fields.

### Control panel
Derived primarily from:
- current attention
- compatible provider set
- current context summary

It should not become a second alternate navigation model.

### Center workbench
Derived primarily from:
- current attention
- current directive
- current provider activation, if any

It remains the canonical surface.

### Details panel
Derived primarily from:
- current attention
- current directive
- mutation posture
- contextual fields

### AITAS strip
Should be derived, not independently stored.

Recommended mapping:
- `Attention` -> current attention target
- `Intention` -> current directive
- `Time` -> current time context
- `Archetype` -> current archetype context
- `Spacial` -> retired in favor of depth implied by attention

If a UI strip still shows a depth field temporarily, it should be understood as a compatibility projection, not the long-term canonical field.

---

## Tool/provider model

Tools must remain providers.

### Declaration
A provider may:
- interpret the current attention target
- expose compatible mediated views
- contribute mediation-specific UI
- request shell events

A provider may not:
- invent a new top-level shell
- redefine directives
- own canonical attention state
- preserve incompatible state after attention changes

### AGRO-ERP implication
AGRO-ERP and similar systems should be understood as capability-driven providers, not as privileged alternate shells.

This is a major part of preventing regression.

---

## Inheritance and sandbox

Inheritance and sandbox remain valid concepts, but not as user-facing alternate page models.

### Inheritance
Inheritance may continue as:
- a source/capability condition
- a browseable context
- a mediated interpretation source

But it should not return as a visible separate top-level SYSTEM ontology.

### Sandbox
Sandbox may continue as:
- staging
- derived local abstraction workspace
- compile/decode/adapt lifecycle engine

But it should not redefine the `SYSTEM` shell.

---

## Directional development posture

A major intent of this declaration is that development should move **directionally** toward the full machine even if some axes remain incomplete now.

This means future passes should prefer:

- introducing the canonical field before fully exploiting it
- introducing an event before fully optimizing its projections
- introducing placeholder context values over inventing alternate models
- expanding the attention grammar instead of adding tabs or isolated surfaces
- moving logic toward the transition model rather than accumulating one-off conditions

### Practical consequence
If a new feature arises and the team is tempted to say:
- “we’ll just add a temporary panel”
- “we’ll just add a tab for this”
- “we’ll just keep a separate mode over here”

the correct question should instead be:
- what attention target is this about?
- what directive does this belong to?
- is this a datum object, or a datum facet?
- what event enters this state?
- what existing state field should project this UI?

---

## What is intentionally unfinished

This declaration does not require all of the following to be fully implemented immediately:

- complete archetype resolution
- complete time mediation
- deep facet taxonomies
- provider lifecycle sophistication
- full relation modeling between datums
- nested sub-facet navigation
- all mutation workflows at facet level
- all navigation gestures across peer facets/values

Those may remain incomplete.

However, none of that incompleteness should justify reintroducing an alternate conceptual backbone.

---

## Current implementation priority

The next implementation passes should prioritize:

1. formalizing the attention grammar
2. adopting the event set
3. documenting and enforcing reset rules
4. deriving UI projections from state rather than ad hoc conditionals
5. deprecating `Spacial` in favor of attention depth
6. preserving the `Investigate` vs `Mediate` distinction
7. keeping tools/provider behavior subordinate to shell state

---

## Testing and enforcement

This declaration should eventually be backed by tests that fail when the model is violated.

### Test classes to maintain or add
- shell composition tests
- unified SYSTEM page composition tests
- selected-context runtime tests
- provider runtime contract tests
- route normalization tests
- legacy regression tests

### Conditions that should fail tests
- reintroduction of visible anthology/resources tabs
- reintroduction of visible Local Resources/Inheritance navigation
- tools surfacing as alternate shells
- attention becoming a vague page-level concept
- provider state persisting incompatibly across file or datum changes
- manipulate affordances showing outside manipulate posture
- incompatible context values being shown as if present

---

## Final declaration

The `SYSTEM` page shall continue to be developed as one canonical workbench whose visible UI is a reflective projection of state.

That state shall be increasingly formalized around:

- a canonical **attention** address
- a canonical **directive**
- contextual interpretation fields such as **archetype** and **time**
- a mutation/edit posture
- provider mediation that remains subordinate to shell state

The long-term target is not merely a cleaner interface. It is a runtime in which the machine’s subject, posture, and contextual interpretation are explicit enough that future features can be added by extending the model rather than bypassing it.

Even where everything is not developed right now, development should continue to inch toward that reflection so that the axes of the machine can be brought together through compounding passes instead of being fractured by expedient local implementations.
