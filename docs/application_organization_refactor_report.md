## Refactor report

This report supersedes the earlier layered-platform proposal by making two corrections: HTTP routes are **not** a primary architectural boundary, and anthology/resources/inheritance should converge into **one host-agnostic workbench interface model**. That is consistent with your attached notes and earlier draft, while removing the parts that were still web-shaped or over-separated.  

The target state is:

* one **application core**
* one **shell/workbench model**
* one **workspace document interface**
* multiple **adapters** for host, storage, and transport

Your current docs already support most of this direction: the shell is already fixed around activity bar, context sidebar, workbench, and inspector; tools are already supposed to consume the shared shell; resources already carry `anthology_compatible_payload`; and sandbox is already described as a lifecycle service rather than the inventory owner.    

---

## 1. Overall architectural change

### What should be removed

The application should stop being organized primarily as:

* route surfaces
* page templates
* tool-local orchestration
* separate anthology/resource/inheritance UI systems

That earlier model appears in the attached draft, especially where “route registrars / controllers” were treated as a main organizing layer. That part should be removed. 

### What it should instead exist as

The application should instead exist as:

* a **host-agnostic application core**
* composed of **bounded contexts**
* using a **single shell/workbench contract**
* exposed through **adapters** for web, desktop, and storage

This is the main simplification.

---

## 2. Transport and routing

### What should change

HTTP routes should no longer be treated as one of the core architectural layers.

### What it should instead exist as

Routes should instead exist as:

* a **web adapter**
* responsible only for transport translation

They should:

* deserialize request input
* call a host-agnostic application service
* serialize the result

They should not:

* own orchestration
* define domain boundaries
* define UI state
* define canonical application structure

This directly adapts the attached report by downgrading the earlier “route registrars / controllers” layer into an adapter concern. 

---

## 3. Canonical shell

### What should change

The shell should stop existing mainly as:

* `base.html`
* portal-specific copied JS/CSS
* route/path-driven page behavior

### What it should instead exist as

The shell should instead exist as:

* a **platform UI runtime**
* defined by:

  * shell state
  * shell actions
  * region contracts
  * renderer-neutral view models

The shell’s invariant regions should remain:

* activity bar
* context sidebar
* workbench
* inspector

That matches the current shell docs and should remain the stable UI spine across browser and desktop hosts.  

### Canonical shell state

The shell should be driven by state like:

* `activeService`
* `activeTool`
* `activeTab`
* `selection`
* `inspector`
* `editorMode`
* `layoutState`

The shell should not know storage distinctions like anthology registry ownership or sandbox inventory rules.

---

## 4. Workbench

### What should change

The application currently still implies multiple major surfaces:

* anthology workbench
* local resources
* inheritance
* tool-specific work surfaces

### What it should instead exist as

The workbench should instead exist as:

* one **canonical editor surface**
* over one **workspace document interface**

This is the main simplification you asked for.

The workbench should provide:

* explorer
* graph/list/table lenses
* focused editor
* inspector cards
* actions such as inspect, draft, preview, apply, refresh

The workbench should not fork into different interaction systems just because the backing payload came from anthology, a local resource file, or an inherited snapshot. That is supported by the current resource convention because resources already store `anthology_compatible_payload` with the same deterministic normalization rules. 

---

## 5. Anthology and resources

### What should change

Anthology and resources should stop existing as separate workbench interaction models.

### What they should instead exist as

At the application/workbench boundary, both should instead exist as one normalized type:

* **workspace document**

Each workspace document should expose:

* `document_family` — `anthology` or `resource`
* `scope` — `local` or `inherited`
* `document_id`
* `payload`
* `metadata`
* `capabilities`

### Why this is the correct simplification

Storage can remain split:

* anthology stays in `data/anthology.json`
* local resources stay in `data/resources/local/*.json`
* inherited resources stay in `data/resources/inherited/...`

But the UI and most application services should not branch on those categories. They should operate on the normalized workspace document model instead. That is exactly the implication of `anthology_compatible_payload`. 

### What still remains different internally

Anthology and resources can still differ in:

* storage adapter
* lifecycle rules
* allowed mutations
* compile/publish/sync capabilities

Those differences should live in adapters and capability metadata, not in separate workbench architectures.

---

## 6. Inheritance

### What should change

Inheritance should stop existing as a parallel UI system or a competing major interaction model.

### What it should instead exist as

Inheritance should instead exist as:

* a **scope mode**
* plus a **capability profile**
* within the same workbench

In practice:

* inherited items are still workspace documents
* they simply have `scope=inherited`
* the capability model can restrict editing, enable refresh/disconnect, and show sync metadata

This aligns with the current docs, which already say `SYSTEM > Inheritance` should not become a second full contract editor and that inherited resources are inventory/controller concerns rather than separate semantic owners.  

So inheritance should be **a mode inside the workbench**, not a parallel UI system.

---

## 7. Sandbox

### What should change

Sandbox should stop being treated as something that could become a user-facing parallel surface or competing page model.

### What it should instead exist as

Sandbox should instead exist as:

* a **resource lifecycle engine**
* responsible for:

  * stage
  * decode
  * compile
  * adapt
  * save
  * publish

It should not be a first-class user-facing category that competes with Workbench, Network, or tool modes.

The current docs already point this way by defining sandbox as canonical shared-core lifecycle logic and explicitly saying it is not the cross-scope inventory owner. 

---

## 8. Application services

### What should change

Application orchestration should stop being spread across:

* web routes
* tool routes
* template-driven page logic

### What it should instead exist as

Application orchestration should instead exist as explicit host-agnostic use-case services.

Examples:

* `load_workbench_document`
* `build_workbench_view`
* `select_workbench_node`
* `preview_document_mutation`
* `apply_document_mutation`
* `resolve_inherited_document_context`
* `compile_contract_context`
* `save_resource_draft`
* `refresh_inherited_snapshot`

These services should:

* coordinate repositories and domain services
* enforce sequencing rules
* return domain results or view models
* remain independent of HTTP, templates, DOM, and URL routing

This keeps the valid parts of the attached report while removing the web-shaped layer ordering. 

---

## 9. Domain core

### What should change

The domain core should be made stricter and more isolated.

### What it should instead exist as

The domain core should instead exist as:

* pure logic
* no Flask imports
* no template knowledge
* no route/HTTP concerns
* no shell state concerns

This part from the attached draft remains correct and should be kept exactly. 

It should own:

* datum identity
* anthology normalization
* MSS compilation
* compact-array logic
* sandbox compile/decode/adapt
* mediation/property geometry logic
* inheritance adaptation

The existing canonical data engine and sandbox docs already describe this ownership pattern.  

---

## 10. Persistence and storage

### What should change

Storage should stop being embedded in service helpers and route logic.

### What it should instead exist as

Storage should instead exist as explicit repository ports with file-backed adapters.

Examples:

* `AnthologyRepository`
* `ResourceRepository`
* `ContractRepository`
* `HostedRepository`
* `RequestLogRepository`
* `WorkbenchStateRepository`

The file-backed runtime stays. The refactor is about isolation, not replacing the storage model. Your docs explicitly state the runtime is file-backed and that resources, anthologies, hosted metadata, request logs, and related state are stored that way.   

---

## 11. Tools

### What should change

Tools should stop behaving like semi-independent UI systems.

### What they should instead exist as

Each tool should instead exist as:

* a **workbench mode extension**
* with:

  * source filters
  * tool-specific actions
  * tool-specific validation
  * tool-specific inspector cards
  * optional tool-specific capability adapters

A tool should not own:

* a parallel shell
* a separate explorer architecture
* a distinct editor model
* its own platform semantics

This is already consistent with your current rule that tools consume shell slots and core APIs rather than define alternate shells. 

AGRO-ERP in particular should remain a thin consumer/orchestrator over shared write/geometry/resource services, not a separate UI architecture. 

---

## 12. SYSTEM page

### What should change

SYSTEM should stop exposing multiple top-level surfaces that imply different interaction models.

### What it should instead exist as

SYSTEM should instead exist as:

* one **Workbench** surface
* with a small source/scope selector

For example:

* `Source: Anthology | Resources`
* `Scope: Local | Inherited`

Or:

* `Local Anthology`
* `Local Resources`
* `Inherited Resources`

But all inside the same workbench contract.

This is simpler than separate top-level categories because the interaction model remains the same.

---

## 13. View models

### What should change

UI-facing payloads should stop being assembled implicitly in route/template flows.

### What they should instead exist as

The application should instead have explicit view-model builders such as:

* `build_shell_model`
* `build_workbench_model`
* `build_context_sidebar_model`
* `build_inspector_model`
* `build_tool_mode_model`

This adapts one of the stronger parts of the attached report: explicit view-model builders are correct, but they should now be host-neutral and organized around the unified workbench, not separate anthology/resources/inheritance pages. 

---

## 14. Host adapters

### What should change

Web delivery should stop being the de facto canonical runtime.

### What it should instead exist as

The application should instead have explicit host adapters:

* **Web adapter**

  * HTTP routes
  * browser deep-link serialization
  * HTML/CSS/JS rendering

* **Desktop adapter**

  * desktop command bridge / IPC
  * local window lifecycle
  * desktop-native or webview renderer integration

Both should call the same application services and consume the same shell/workbench view models.

That is the cleanest way to satisfy the environment-agnostic requirement.

---

## 15. Flavor runtimes

### What should change

Flavor runtimes should stop carrying duplicated shell or semantic behavior.

### What they should instead exist as

Flavors should instead exist as:

* thin composition/configuration layers
* theme/navigation differences
* enabled-tool sets
* flavor-specific default policies

They should not own:

* divergent shell logic
* divergent workbench semantics
* divergent data semantics

This matches the current docs, which already describe flavor runtimes as composition wrappers and push shared ownership into shared core. 

---

## 16. Recommended target structure

A better modular shape is:

```text
core/
  contexts/
    anthology/
    resources/
    contracts/
    sandbox/
    network/
    workbench/
    tools/
application/
  commands/
  queries/
  services/
ports/
  repositories/
  host/
  transport/
adapters/
  web/
  desktop/
  storage/file/
ui/
  shell/
  workbench/
  inspector/
  view_models/
flavors/
  fnd/
  tff/
```

### How each area should exist

* `core/contexts/*` — pure domain rules and context models
* `application/*` — host-agnostic orchestration
* `ports/*` — interfaces for storage, host services, transport
* `adapters/web/*` — HTTP transport only
* `adapters/desktop/*` — desktop host only
* `adapters/storage/file/*` — concrete file-backed persistence
* `ui/*` — shell state, actions, renderer-neutral models
* `flavors/*` — thin configuration/composition

---

## 17. Refactor order

### Phase 1

Unify anthology, local resources, and inherited resources into one **workspace document** model.

### Phase 2

Refactor SYSTEM into one workbench with source/scope selection instead of separate parallel surfaces.

### Phase 3

Move orchestration out of routes and tool handlers into explicit application services.

### Phase 4

Convert tools into workbench-mode extensions.

### Phase 5

Refactor web-specific routing/template logic into host adapters.

### Phase 6

Collapse shell duplication into one canonical shell runtime.

---

## Final recommendation

The application should be refactored so that:

* the **workbench** is the canonical operator surface
* **anthology and resources** are unified at the interface level
* **inheritance** is a scope/capability mode, not a parallel UI system
* **sandbox** is lifecycle infrastructure, not a competing user-facing surface
* **tools** extend the workbench instead of creating side architectures
* **HTTP routes** are web adapters, not core architecture
* **desktop and server-hosted builds** run the same application model
* **storage and transport differences** live behind adapters

That is the modular organization your notes point to, once the earlier route/controller-centered pieces are removed and the anthology/resource split is flattened into one canonical workbench model.

