# Portal Sandbox Canonicalization Context Recovery

## Purpose

This note is a recovery document for the current state of the portal sandbox canonicalization effort.

It is meant to let work resume without re-deriving:
- why the old directory drift kept returning,
- what canonical filesystem contract was chosen,
- what has already been changed in the repo,
- what still needs to be done on the live instances and in any remaining edge cases.

---

## 1. Core diagnosis that drove this effort

The original problem was not random reversion.

The directory tree kept returning to a messy duplicated state because different parts of the portal logic were still asserting different filesystem realities at the same time. The old model mixed:
- root datum-style files,
- `resources/local` and `resources/inherited`,
- sidecar indexes such as `index.local.json` and `index.inherited.json`,
- presentation sidecars such as `datum_icons.json`,
- cache trees that were doing more than cache work,
- contract/public exposure logic using legacy `rec` / `ref` semantics.

That meant deleting drift on disk was not enough. Old bootstrap, compatibility, migration, or runtime write paths could re-materialize it.

---

## 2. Canonical filesystem judgment that was chosen

The chosen direction is:

- the system sandbox is the canonical data environment
- `data/anthology.json` is the anchor file
- datum-bearing files belong only in:
  - `data/resources/`
  - `data/references/`
- canonical local resource names are:
  - `rc.<msn_id>.<name>.json`
- canonical outside-origin reference names are:
  - `rf.<msn_id>.<name>.json`
- cache is only for encoded / MSS forms:
  - `data/cache/RC/rc.<msn_id>.<name>.bin`
  - `data/cache/RF/rf.<msn_id>.<name>.bin`
- icon state should live in datum entries themselves
- there should be no canonical persisted filesystem distinction based on:
  - local
  - inherited
  - external
  - internal

The directories/files that were judged non-canonical and targeted for removal from runtime behavior were:

- `data/resources/local/`
- `data/resources/inherited/`
- `data/resources/index.local.json`
- `data/resources/index.inherited.json`
- `data/presentation/`
- `data/presentation/datum_icons.json`
- `data/cache/external_resources/`
- `data/cache/tenant/`
- `data/cache/contacts/`
- legacy canonical runtime naming with `rec.*` and `ref.*`

A further important decision was:

- `samras-txa` and `samras-msn` may remain conceptual identities in UI/state logic if needed,
- but they should not be canonical root datum files in storage.

---

## 3. Why this direction made sense

This aligned with the broader project direction:

- the SYSTEM page is supposed to converge on one canonical workbench model rather than separate anthology/resources/inheritance ontologies
- SAMRAS structure is supposed to be engine-owned and deterministically regenerated rather than persisted through parallel ad hoc structural files
- the old drift was a consequence of multiple asserted truths coexisting in the same runtime

---

## 4. What the live-instance audit found before repo correction

Before the repo changes were applied, the active live audit found major contradictions such as:

- root datum-style `samras-msn.json` and `samras-txa.json`
- `data/presentation/datum_icons.json`
- `data/resources/local/`
- `data/resources/inherited/`
- `index.local.json`
- `index.inherited.json`
- `rec.*` local resource files
- `ref.*` outside-origin reference files
- no canonical `rc.*`, `rf.*`, `data/cache/RC`, or `data/cache/RF` representation in active truth
- forbidden cache trees such as `external_resources`, `tenant`, and `contacts`
- contract/contact-card/public state still encoding old `ref` semantics

The audit also identified concrete code paths that were likely re-materializing the old state.

---

## 5. What appears to have been corrected in the repo since then

The repo now appears materially closer to the chosen canonical contract.

### 5.1 Resource registry and canonical layout

`instances/_shared/portal/data_engine/resource_registry.py` now appears to implement:

- `resources/`
- `references/`
- `cache/RC`
- `cache/RF`

It also defines canonical filename handling for:
- `rc.<msn_id>.<name>.json`
- `rf.<msn_id>.<name>.json`
- matching `.bin` cache artifacts

It also appears to include:
- layout creation for only the new structure
- migration helpers for legacy root SAMRAS files
- migration helpers for legacy `rec.*`
- cache materialization from canonical resource files

### 5.2 Runtime startup behavior

`instances/_shared/runtime/flavors/fnd/app.py` now appears to warm the system resource workbench without materializing legacy root files.

That is a major change from the earlier state.

### 5.3 Icons no longer depend on `datum_icons.json`

`instances/_shared/runtime/flavors/fnd/data/storage_json.py` now appears to derive icon mappings from anthology rows, not from a separate `data/presentation/datum_icons.json` sidecar.

That is aligned with the chosen contract.

### 5.4 External-resource cache restriction

`instances/_shared/portal/data_engine/external_resources/cache.py` now appears to define an in-memory compatibility cache rather than persisting external-resource JSON under `data/cache`.

That is aligned with the rule that `data/cache/` should only hold encoded/MSS forms.

### 5.5 Config normalization now understands canonical reference semantics

`instances/_shared/portal/core_services/config_loader.py` now appears to normalize reference entries into canonical `rf.<source>.<name>.bin` form and remove old `refferences` drift.

### 5.6 Local publish path now writes canonical local resources

`instances/_shared/portal/sandbox/local_resource_lifecycle.py` now appears to publish local resources into canonical `rc.*` resource files.

### 5.7 Inherited contract resources now materialize as canonical references

`instances/_shared/portal/data_engine/inherited_contract_resources.py` now appears to materialize imported references as canonical `rf.*` references with reference-scoped metadata.

### 5.8 System workbench now appears to resolve TXA/MSN through canonical resources

`instances/_shared/portal/sandbox/resource_workbench.py` now appears to resolve:
- anthology via `data/anthology.json`
- TXA via `data/resources/rc.*.txa.json`
- MSN via `data/resources/rc.*.msn.json`

That is substantially better than re-materializing root `samras-txa.json` / `samras-msn.json`.

---

## 6. What is now likely true

The repo is no longer in the original broad “full corrective pass still needed from scratch” state.

The repo now appears to have already absorbed most of the key structural corrections.

That means the next stage is no longer:
- “rewrite the whole filesystem contract in repo logic”

It is now more narrowly:
- verify remaining contradictions
- migrate the live instances
- validate that services and public outputs actually behave according to the new contract
- close any residual edge cases

---

## 7. What still needs to be done

### 7.1 Live instance migration still needs to be verified or completed

Repo changes do not prove that the active live instances on the server were migrated.

The active instances still need to be checked for:
- legacy `rec.*`
- legacy `ref.*`
- `resources/local`
- `resources/inherited`
- index sidecars
- `datum_icons.json`
- forbidden cache trees
- old public/contact-card outputs
- old contract payload semantics

### 7.2 Service restart and non-reversion validation still need to be proven

Even if code is corrected, the following still need proof on the server:

- services restarted successfully
- active instances load successfully
- startup does not recreate old structures
- normal portal usage does not recreate old structures

### 7.3 Public/contact-card semantics still need explicit live validation

Repo normalization looks better, but live validation is still needed for:

- what `public/` artifacts are generated
- whether native local resources are exposed as `rc.*`
- whether outside-origin references remain clearly `rf.*`
- whether any outward payload still advertises old `ref.*` native semantics

### 7.4 One edge case still looks potentially open

`storage_json.py` still appears to include support for SAMRAS instance files directly under `data/` using `<msn>.<instance>.json`.

If those are treated as canonical datum-bearing files, that would still conflict with the stricter filesystem decision that datum-bearing files belong only in `data/resources/` or `data/references/`.

This needs to be explicitly decided:

- either these are legacy compatibility only and should be removed from runtime use,
- or they are a justified exception and the contract must be revised to say so.

At the moment, they look like the main remaining repo-level conceptual inconsistency.

### 7.5 UI/state-level TXA/MSN identity must remain conceptual only

It is acceptable for UI/state logic to continue thinking in terms of anthology / txa / msn conceptual surfaces.

It is not acceptable for that to cause forbidden root datum file materialization again.

This should be verified in practice.

---

## 8. Recommended immediate next step

The next useful step is not the old broad corrective prompt.

The next step should be a narrower prompt with this scope:

1. audit the current repo after the updates and list only remaining contradictions against the chosen contract
2. audit the active live instances and compare them to the updated repo behavior
3. migrate any remaining live drift
4. restart the necessary services
5. validate non-reversion
6. explicitly resolve the SAMRAS-instance root-file question if it is still active

---

## 9. Recommended narrow follow-up checklist

Use this checklist for the next pass.

### Repo residual check
- verify no active runtime writer still creates:
  - `resources/local`
  - `resources/inherited`
  - `index.local.json`
  - `index.inherited.json`
  - `presentation/datum_icons.json`
  - `cache/external_resources`
  - `cache/tenant`
  - `cache/contacts`
- verify no active runtime writer still creates canonical `rec.*` or `ref.*`
- verify TXA/MSN conceptual handling does not materialize root datum files
- decide whether `<msn>.<instance>.json` SAMRAS instance files are still allowed

### Live instance migration check
For each active instance:
- inventory current files
- identify residual old layout
- migrate old files into:
  - `data/resources/rc.*`
  - `data/references/rf.*`
  - `data/cache/RC/*.bin`
  - `data/cache/RF/*.bin`
- remove forbidden directories/files
- update private/public/contract state as needed

### Validation check
- restart only necessary services
- verify startup success
- verify old directories/files do not reappear
- verify public/contact-card outputs use the new semantics
- verify icons resolve without `datum_icons.json`

---

## 10. Practical working judgment now

The situation is better than before.

The repo appears to have absorbed most of the structural correction already.

The remaining work is now mostly:
- live-instance alignment,
- runtime validation,
- public-output validation,
- and possibly one remaining SAMRAS storage edge case.

That is a much smaller and better-defined problem than the original one.

---

## 11. Context sources that matter

The core context for this situation came from four strands:

1. the SYSTEM workbench/state-machine direction
2. the SAMRAS engine-owned canonical-structure direction
3. the root-cause reversion diagnosis
4. the canonical sandbox filesystem judgment

Use those as the conceptual basis for any future prompt or corrective pass.

---

## 12. One-sentence status summary

The repo now appears largely aligned with the chosen canonical sandbox contract, but the active server instances, outward public/contact-card behavior, service-level non-reversion proof, and a possible SAMRAS root-file edge case still need to be verified or corrected.
