# Network Engine and Page Model

## Scope

Current active implementation scope is FND + TFF.

NETWORK is both:

- a shell workbench page (`/portal/network`)
- the runtime surface for portal-to-portal metadata, request logs, alias interfaces, and hosted relationship views

Hosted metadata is now consolidated into `private/network/hosted.json`. In the current direction that file absorbs the metadata responsibilities that had previously been modeled as separate `subject_congregation.json`, `broadcaster.json`, and progeny-template JSON concepts.

## Qualifier model

Network APIs are grouped into three qualifier classes:

- `anonymous`
  - public options and discoverable contact resources
- `asymmetric`
  - signed portal-to-portal contract request/confirmation
- `symmetric`
  - vault-backed contract renewal and rotation flows

Asymmetric verification remains the canonical trust boundary for inter-portal contract requests and confirmations.

## Request-log and contract flow

Current contract flow:

1. requesting portal sends a signed asymmetric request
2. receiving portal verifies signer `msn_id` and public key against the contact card
3. receiving portal appends verified evidence to its request log
4. receiving portal returns/pushes confirmation evidence to the counterparty request log

Request logs are part of the Network Engine surface and remain file-backed.

## External contact collection

Network external-contact-by-collection resolution should reuse Data Engine resolution rather than duplicate graph logic.

Canonical alias/member contact source priority:

1. `profile_refs.contact_collection_ref`
2. explicit override for tooling/tests

This is the bridge between anthology-backed contact collections and hosted alias views.

## Reference inheritance

Canonical network metadata ref syntax:

- `<msn_id>.<datum>`

Compatibility policy:

- dual-read for local, hyphen-qualified, and dot-qualified refs
- dot-write for new network metadata

Reference inheritance is a network-metadata layer concern in this phase. Anthology pair storage is not being redefined here.

## Daemon boundary

Network wrapper routes may request reference resolution, but daemon ownership remains in the Data Engine.

The Network layer should call Data Engine resolution wrappers instead of maintaining a separate token/graph runtime.

## NETWORK page behavior

Canonical routes:

- `/portal/network?tab=messages&kind=alias|log|p2p&id=...`
- `/portal/network?tab=hosted`
- `/portal/network?tab=profile`

Workbench modes:

- `alias`: hosted/member interface relationship
- `log`: request-log channel evidence
- `p2p`: direct conversation channel derived from logged pairs
- `hosted`: hosted interface payloads from `private/network/hosted.json`
- `profile`: portal config and public-card inspection

The page keeps the existing left-context / central-workbench / right-inspector model.
