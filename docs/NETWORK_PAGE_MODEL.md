# Network Engine and Page Model

## Scope

Current active implementation scope is FND + TFF.

NETWORK is both:

- a shell workbench page at `/portal/network`
- the runtime surface for portal-to-portal metadata, request logs, aliases, hosted views, and contract context

Data Tool entry is now canonical at `/portal/data` (`/portal/tools/data_tool/home`), while Network remains the canonical contract editing surface.

## Tabs

Canonical NETWORK tabs:

- `Messages`
- `Hosted`
- `Profile`
- `Contracts`

Canonical routes:

- `/portal/network?tab=messages&kind=alias|log|p2p&id=...`
- `/portal/network?tab=hosted`
- `/portal/network?tab=profile`
- `/portal/network?tab=contracts&id=<contract_id>`

`NETWORK > Contracts` is the canonical contract editor.

`NETWORK > Profile` now uses shared datum-backed field contracts and write intents:

- field contract schema from `/portal/api/data/write/field_contracts`
- preview via `/portal/api/data/write/preview`
- apply via `/portal/api/data/write/apply`

Profile/config JSON edits flow through shared write preview/apply so config values remain canonical datum refs (dot-qualified when portal MSN is known). The profile tab should treat JSON as a ref surface, not as semantic datum storage.

Current write-model guarantees for Profile:

- field contracts define allowed write modes and required inputs per profile field
- write preview validates contract + template semantics before any mutation
- apply emits deterministic mutation summaries (created/reused actions) and surfaces `contract_mss_sync` pass-through from anthology writes

## Qualifier model

Network APIs remain grouped into:

- `anonymous`
- `asymmetric`
- `symmetric`

Asymmetric verification remains the canonical trust boundary for request and confirmation ingress.

## Contract context model

Contracts carry shared MSS context so foreign datum refs can be understood without transferring a full anthology.

Canonical contract context fields:

- `owner_selected_refs`
- `owner_mss`
- `counterparty_mss`

Local behavior:

- `owner_selected_refs` is the editable local source
- `owner_mss` is compiled from the local anthology when refs are present
- `counterparty_mss` is read-only in the editor

Foreign datum resolution:

- local `<msn_id>.<datum>` resolves from the local anthology
- foreign `<msn_id>.<datum>` resolves through the matching contract MSS context

See:

- `docs/MSS_COMPACT_ARRAY_SPEC.md`
- `docs/MSS_CONTRACT_CONTEXT_STATUS.md`

## Request-log and handshake flow

Current contract flow:

1. requesting portal sends a signed asymmetric proposal
2. proposal carries the sender-side `owner_mss` and `owner_selected_refs`
3. receiving portal verifies signer identity and persists the remote MSS as `counterparty_mss`
4. receiving portal returns confirmation with its own local-side MSS
5. each side stores its own local compiled MSS as `owner_mss` and the remote side as `counterparty_mss`

Request logs remain part of the Network Engine surface and remain file-backed.

## Daemon boundary

NETWORK no longer maintains a separate daemon wrapper for foreign datum resolution.

The Network layer may still use Data Engine APIs for anthology-backed local tools, but contract-scoped foreign datum resolution is MSS-backed, not daemon-wrapper-backed.
