# Canonical MyCite Data Engine

## 1) Canonical Source

`data/anthology.json` is the canonical datum source for workbench navigation, focus, investigation, and mediation.

Deterministic ordering is always:

1. `layer`
2. `value_group`
3. `iteration`

Shared normalization logic lives in:

- `portals/_shared/portal/data_engine/anthology_normalization.py`

FND/TFF/MT storage and workspace adapters consume this shared logic.

## 2) Mediation Registry (Lenses)

Default mediated value types are first-class registry entries with:

- matcher rule + matcher
- decode
- encode
- validation (`magnitude`, `value`)
- render hint

Canonical registry:

- `portals/_shared/portal/mediation/registry.py`

Default registry entries:

- `boolean_ref`
- `ascii_char`
- `dns_wire_format`
- `text_byte_format`
- `timestamp_unix_s`
- `duration_s`
- `length_m`
- `coordinate`

Compatibility aliases remain supported (`boolean`, `char`, `ascii`, `text_byte_email_format`, `time_span_s`, `coordinate_fixed_hex`).

Lenses are structural/typed interpreters. Tools consume lenses and add domain workflow semantics.

## 3) AITAS State Model

Canonical facets:

- `attention`
- `intention`
- `temporal`
- `archetype`
- `spatial`

Compatibility mirror:

- legacy `spacial` is accepted and mirrored for backwards compatibility.

State phase is explicit:

- `navigate`
- `focus`
- `investigate`
- `mediate`

Implementation:

- `portals/mycite-le_fnd/data/engine/nimm/state.py`
- mirrored in TFF/MT workspace stack

## 4) NIMM Directive Expectations

Directive behavior is engine-driven:

- `nav` updates navigation phase/context
- `inv` updates focus/investigation state
- `med` updates mediation mode/lens/facets
- `man` performs managed edits/commit/reset

Pattern hooks are explicit and active:

- `portals/mycite-le_fnd/data/engine/patterns.py`
- row-level pattern annotation in anthology table payload

## 5) Daemon Contract

Daemon ports are constrained execution wrappers into NIMM/anthology.

Minimum contract:

- target datum reference
- allowed operation scope
- default focus
- optional AITAS context
- output strategy

Canonical methods:

- `daemon_port_catalog`
- `daemon_port_resolve`
- `daemon_resolve_tokens`

Routes:

- `GET /portal/api/data/daemon/ports`
- `POST /portal/api/data/daemon/resolve`
- `POST /portal/api/data/daemon/resolve_tokens`

## 6) Progeny / Member / Alias Runtime Model

Canonical legal-entity baseline classes:

- `poc`
- `member`
- `user`

Legacy compatibility aliases remain accepted:

- `tenant -> member`
- `board_member -> member`

Shared model helpers:

- `portals/_shared/portal/progeny_model/*`

Runtime network card model now includes alias->progeny inheritance resolution with explicit rules:

- `portals/_shared/portal/core_services/network_cards.py`

## 7) Workbench Graph Architecture

Workbench graph is a stateful control surface (not decoration):

- click: focus summary (`inv summary`)
- double click: investigate (`inv abstraction_path`) + structured inspector
- supports context controls: `focus`, `depth`, `layout`, `context`

API:

- `GET /portal/api/data/anthology/graph?focus=&depth=&layout=&context=`

Layouts:

- `linear`
- `radial`

Context modes:

- `global`
- `local` (focus-local extraction)

## 8) Geographic / Spatial Base

Core geography model resolves config references through anthology-compatible coordinate decoding.

Shared model:

- `portals/_shared/portal/core_services/geography.py`

Network page consumes this model for config-facing polygon/GeoJSON rendering in both FND and TFF.

## 9) Extension Rule (Core vs Tools)

Core engine contracts live in shared/core engine modules.

Tools mount via tool runtime registry and consume engine APIs; they do not fork core data architecture.

Tool runtime:

- `portals/_shared/portal/tools/runtime.py`

## 10) Shell/Page Relationship

Page/shell are consumers of data engine contracts:

- engine decides state/model semantics
- UI dispatches directives and renders returned state
- no parallel non-engine state model should replace AITAS/NIMM

Primary SYSTEM workbench files:

- `portal/ui/templates/tools/partials/data_tool_shell.html`
- `portal/ui/static/tools/data_tool.js`

## 11) Deprecations

Deprecated runtime assumptions:

- conspectus-driven navigation as primary runtime model
- separate data-tab split workflows as canonical SYSTEM path

Current transitional note:

- non-target legacy portals may keep scoped fallback loaders; FND/TFF are anthology-authoritative.
