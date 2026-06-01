# Portal Datum-Model Audit — 2026-05-31

Date: 2026-05-31
Scope: the MyCite Portal's sandbox / datum-document / datum-interfacing
model — how datums are stored, identified, viewed, manipulated, and bound
to tools and lenses — framed against the target three-layer architecture
(L1 CORE / L2 SURFACE / L3 UI), with the delta and recommendations.
Method: three deep layer audits (L1 datum kernel, L2 materialization +
mutation, L3 UI + tool/lens binding) plus ground-truthing every cited
`path:line` against the working tree and the live test suite (1187 tests
collected via `MyCiteV2/tests`).

This is the front-of-house artifact for a 21-unit audit batch. It states
the findings and links into the `docs/wiki/` pages (see
[Appendix — links](#appendix--links)) for layer-by-layer depth. Wiki
links are forward references; companion units in this batch publish them.

---

## Executive summary

The portal stack already mirrors the target layers and the model works
end-to-end: a sandbox is a set of datum sheets in the MOS SQLite authority
(L1), it is materialized and mutated through a WORKBOOK-YAML codec and a
canonical mutation runtime (L2), and it is loaded into an Excel-like
read surface with menu-bar tool eligibility and per-datum lens resolution
(L3). You can select a datum, see the tools its hyphae chain makes
eligible, and apply a cross-document workbook edit that re-mints canonical
ids and persists to MOS.

The delta to the target vision is **five gaps**, none of which break the
working model today:

1. **core→adapter dependency inversion (HIGH)** — the "lean L1 core"
   `datum_ops` package imports its address/hyphae/MSS engine *up* from
   the SQL adapter, and a near-duplicate identity module exists in core.
2. **materialization read/write split (HIGH)** — the WORKBOOK-YAML codec
   drives the write path, but the read path reprojects SQL→JSON directly
   per request through a separate ~900-LOC service.
3. **no first-class hyphae-flag / minimum-complete abstraction path; MSS
   is JSON+SHA256, not a SAMRAS bitstream (MED)** — tool/lens binding
   works, but on archetype/source_kind tokens rather than the canonical
   compiled-path the vision describes.
4. **no Utilities-manage / Control-Panel-toggle lens UX (MED)** — the
   tool palette (search → dropdown → panel) ships; lens management does
   not have a surface.
5. **network / crypto / contract future is entirely stubbed (LOW now /
   HIGH later)** — the asymmetric-key Manager/Subordinate contracts,
   msn_registry, reference-exchange, and mediation surface are 1-LOC
   placeholders. Persistence is form-factor-agnostic, so the eventual
   desktop app + local DB is not blocked.

The recommended near-term work — and what *this* batch lands — is the
core-refactor (invert the dependency + retire the duplicate + add a
boundary test), the workbook sheet-key fix, stub-intent docs, and an
end-to-end harness. The crypto/contract surfaces stay deferred until the
near-term tool/lens focus is complete.

---

## Inventory & how-it-works

Per-layer, concise, with the load-bearing anchors. Depth is deferred to
the wiki pages linked in the appendix.

### L1 — CORE (the MOS datum kernel)

The datum database is MOS: SQLite is the canonical authority; nothing
writes datum state to disk (the MOS-only storage rule). A datum is
addressed `<layer>-<vg>-<iter>`; the rudimentary anchor rows live at
`0-0-*`; a row's hyphae value is its full dependency set.

- **Real engine:** `MyCiteV2/packages/adapters/sql/datum_semantics.py`
  (663 LOC) is the address parser, MSS-hash, hyphae-chain, and
  preview/reorder engine. It depends only on the datum-store port
  (`MyCiteV2/packages/ports/datum_store`) plus a sibling JSON helper
  (`._sqlite`) — no upward dependency on anything heavier.
- **Operations:** `MyCiteV2/packages/core/datum_ops/ops.py` (row-level
  ops) and `MyCiteV2/packages/core/datum_ops/node_ops.py` (mint /
  relocate / repoint / rename / drop + RewriteRefs / RecompileMagnitude)
  are pure dataclasses that transform an in-memory `Workbook` and return
  a `WorkbookDelta`. `compile_workbook` + `plan_migration` thread the
  deltas and re-mint canonical ids
  (`MyCiteV2/packages/core/datum_ops/__init__.py:15,21`).
- **MSS identity:** the canonical hash + hyphae derivation used by tool
  binding lives in `MyCiteV2/packages/core/mss/datum_identity.py`
  (`compute_mss_hash:101`, `derive_hyphae_chain:126`). MSS here is a
  JSON-canonicalized SHA256 version identity — not yet the
  single-sequence SAMRAS bitstream the vision describes.

### L2 — SURFACE (materialization + canonical mutation)

A sandbox is materialized as a multi-sheet WORKBOOK-YAML envelope — the
standardized, interface-ready transport form (never persisted):

- **Codec (transport only):** `MyCiteV2/packages/core/datum_io/codec.py`
  (121 LOC) and the `Workbook ⇄ WORKBOOK-YAML` bridge
  `MyCiteV2/packages/core/datum_ops/workbook.py` (31 LOC). Both depend
  only on the datum-store port; both document themselves as transport,
  honoring the MOS-only rule.
- **Write path:** the canonical mutation runtime
  `MyCiteV2/instances/_shared/runtime/portal_datum_workbench_mutation_runtime.py`
  (1189 LOC). The `apply_workbook` action loads the baseline workbook,
  reconstructs the edited workbook with `workbook_codec.from_yaml`,
  compiles localized edits with `compile_workbook`, plans the migration,
  and persists through the store-bound executor
  (`datum_workbook_apply`) — re-minting canonical ids
  (`portal_datum_workbench_mutation_runtime.py:495-536`).
- **Save naming:** documents persist with the canonical id shape
  `<document_type>.<msn_id>.<sandbox>.<name>.<hash>`, parsed and inserted
  by `MyCiteV2/packages/adapters/sql/datum_workbook_apply.py:60-62`.

### L3 — UI (read surface + tool/lens binding)

- **Read surface:** `MyCiteV2/packages/tools/workbench_ui/service.py`
  (992 LOC). `WorkbenchUiReadService.read_surface` (`:586`) reads the
  authoritative catalog via `SqliteSystemDatumStoreAdapter` (`:471`,
  `:598`) and reprojects SQL→JSON each request, filtered/sorted/grouped
  per view params, with a process-local projection cache keyed by a
  catalog content fingerprint (`:398-440`). This is a *separate* path
  from the codec, not the same WORKBOOK-YAML form the write path uses.
- **Tool binding:** `MyCiteV2/packages/state_machine/portal_shell/tool_eligibility.py`
  (115 LOC). `recognize_applicable_tools` (`:64`) intersects each tool's
  `applies_to_archetype` / `applies_to_source_kind` against the
  document's archetype set, which is *widened* by walking the hyphae
  chain (`derive_hyphae_chain`, imported at `:21`) to reach per-row
  archetype tokens.
- **Lens binding:** `MyCiteV2/packages/state_machine/lens/registry.py`
  (86 LOC). `DatumLensRegistry.resolve` (`:51`) matches on
  `recognized_family` first, then `primary_value_kind` — the Excel
  "cell equation vs value" lens distinction.
- **Palette UX:** `MyCiteV2/instances/_shared/portal_host/static/v2_portal_tool_palette.js`
  is the menu-bar search → dropdown → panel, fetching
  `GET /portal/api/tools/eligible`
  (`MyCiteV2/instances/_shared/portal_host/app.py:1707`).

---

## The five findings

### Finding 1 — core→adapter dependency inversion (HIGH)

**What:** The L1 "lean core" `datum_ops` package imports its
address/hyphae engine *up* from the SQL adapter, inverting the intended
core→port dependency direction. Separately, a near-duplicate of the MSS
identity engine lives in core but is barely used.

**Evidence:**
- `MyCiteV2/packages/core/datum_ops/ops.py:24` imports
  `parse_datum_address`, `preview_document_delete/insert/move` from
  `MyCiteV2.packages.adapters.sql.datum_semantics`.
- `MyCiteV2/packages/core/datum_ops/node_ops.py:17` imports
  `parse_datum_address` from the same adapter module.
- The real 663-LOC engine `MyCiteV2/packages/adapters/sql/datum_semantics.py`
  itself only imports the datum-store port (`:7`) + a sibling JSON
  helper — it is correctly leaf-ward; the inversion is that *core*
  reaches sideways/up into `adapters/` for it.
- `MyCiteV2/packages/core/mss/datum_identity.py` is a near-duplicate of
  that engine's identity half (`compute_mss_hash:101`,
  `derive_hyphae_chain:126`), imported only by
  `tool_eligibility.py:21` and `tests/unit/test_datum_identity_core.py`.
- No boundary test guards this: `MyCiteV2/tests/architecture/` has
  `test_core_datum_refs_boundaries.py` and
  `test_core_datum_rules_boundaries.py` but **no**
  `test_core_datum_ops_boundaries.py`.

**Severity:** HIGH — this is the central architectural inversion of the
target model; left unguarded it will re-accrete with every new op.

**Recommendation:** Relocate the address/MSS primitives so core owns them
(or expose them through a core-side seam that the SQL adapter consumes),
collapse the `core/mss/datum_identity.py` duplicate into the single
canonical engine, and add
`tests/architecture/test_core_datum_ops_boundaries.py` asserting
`core/datum_ops` does not import from `adapters/`. *This batch lands this
fix.*

### Finding 2 — materialization read/write split (HIGH)

**What:** The WORKBOOK-YAML codec drives the write path, but the read
path reprojects SQL→JSON directly through a separate ~900-LOC service.
Two materializations of the same sandbox exist.

**Evidence:**
- Write: `portal_datum_workbench_mutation_runtime.py:495-536` uses
  `workbook_codec.from_yaml` + `compile_workbook` + `plan_migration`
  (the codec at `core/datum_io/codec.py` + `core/datum_ops/workbook.py`,
  both transport-only).
- Read: `MyCiteV2/packages/tools/workbench_ui/service.py:586` projects
  the SQL catalog (`:598`) into a view JSON per request, with its own
  column/group/lens projection helpers — it does not go through the
  WORKBOOK-YAML form.

**Severity:** HIGH — the target L3 loads the sandbox as WORKBOOK-YAML at
runtime; today read and write disagree on the materialization, so a UI
that edits what it reads must round-trip through two unrelated shapes.

**Recommendation:** Converge on the WORKBOOK-YAML envelope as the single
runtime materialization (read service hydrates the same workbook the
mutation runtime consumes), keeping the projection cache for view-param
derivations only. Medium effort; sequence after Finding 1 so the codec
sits cleanly in core.

### Finding 3 — no first-class hyphae-flag / minimum-complete path; MSS ≈ JSON+SHA256, not SAMRAS bitstream (MED)

**What:** Tool/lens binding works, but on archetype/source_kind tokens
widened by the hyphae chain — not on a first-class "hyphae match → flag →
bind" mechanism, and the canonical datum is not compiled along a
minimum-but-complete abstraction path. MSS is a JSON-canonicalized
SHA256, not the single-sequence SAMRAS bitstream (address-size / bitmap /
start-stop slices, multi-top-level) the vision specifies.

**Evidence:**
- Tool binding widened by the hyphae chain:
  `portal_shell/tool_eligibility.py:44-74` derives an archetype set by
  walking `derive_hyphae_chain` to per-row archetypes, then intersects
  with `applies_to_archetype` / `applies_to_source_kind`.
- Lens binding by family/value_kind: `lens/registry.py:51-66`.
- MSS form: `core/mss/datum_identity.py:101` (`compute_mss_hash`) hashes
  canonical JSON — no bitstream slicing.

**Severity:** MED — the bound-tool/lens experience is real and useful;
this is a fidelity gap against the canonical-compile vision, not a broken
path.

**Recommendation:** Introduce a first-class hyphae-flag on the canonical
datum and a minimum-complete abstraction-path compiler as the binding
key, with the SAMRAS single-sequence encoding behind it. Treat as a
roadmap item after the L1/L2 convergence; document the intended SAMRAS
form in the L1 wiki page now.

### Finding 4 — no Utilities-manage / Control-Panel-toggle lens UX (MED)

**What:** The near-term tool palette exists end-to-end, but lenses have
no management surface (Utilities) and no per-surface toggle (Control
Panel).

**Evidence:**
- Tool palette present: `static/v2_portal_tool_palette.js` (search →
  dropdown → panel) backed by `app.py:1707`
  (`GET /portal/api/tools/eligible`).
- Lens registry resolves a lens (`lens/registry.py`) but no Utilities or
  Control-Panel module references it — there is no
  `tools/utilities` lens-management surface and no Control-Panel toggle
  wiring (grep for lens in those surfaces returns nothing).

**Severity:** MED — lenses resolve automatically, but the user cannot
manage or toggle them, which is the stated near-term UX.

**Recommendation:** Add a lens catalog under Utilities (register / view
available lenses) and a Control-Panel toggle that pins a lens per
surface, reusing the palette's fetch→render pattern. Medium effort;
pairs naturally with Finding 3's first-class binding.

### Finding 5 — network / crypto / contract future entirely stubbed (LOW now / HIGH later)

**What:** The future surfaces — asymmetric-key Manager/Subordinate
contracts, reference-exchange, msn_registry, mediation surface, shared
tool scaffolding, sandbox orchestration — are all 1-LOC placeholders.
This is expected for the current phase, and persistence is
form-factor-agnostic so the eventual desktop app + local DB is not
blocked.

**Evidence (each a 1-LOC `__init__.py`):**
- `MyCiteV2/packages/core/crypto/__init__.py`
- `MyCiteV2/packages/modules/domains/contracts/__init__.py`
- `MyCiteV2/packages/modules/domains/reference_exchange/__init__.py`
- `MyCiteV2/packages/state_machine/mediation_surface/__init__.py`
- `MyCiteV2/packages/tools/_shared/__init__.py`
- `MyCiteV2/packages/sandboxes/__init__.py`,
  `.../sandboxes/orchestration/__init__.py`,
  `.../sandboxes/system/__init__.py`

**Severity:** LOW now / HIGH later — no current functionality depends on
these; they become the critical path once the tool/lens near-term work
lands and the msn contact-card / FND-profile-card / contract model
begins.

**Recommendation:** Leave the stubs in place but document their intent
(what each will hold, the asymmetric-key Manager/Subordinate contract
shape, the msn_registry) so the placeholders are legible and not mistaken
for dead code. *This batch lands the stub-intent docs.*

---

## Recommendations & next steps

Tied to the roadmap, ordered by the dependency between findings:

1. **Core refactor (Finding 1, HIGH) — lands this batch.** Invert the
   `datum_ops`→`adapters` dependency, retire the
   `core/mss/datum_identity.py` duplicate, add
   `tests/architecture/test_core_datum_ops_boundaries.py`. Unblocks a
   clean L1 for everything below.
2. **Workbook sheet-key fix (L2) — lands this batch.** Harden the
   `_sheet_key` derivation in `core/datum_ops/workbook.py` so the
   read/write materializations key sheets identically (prerequisite for
   converging Finding 2).
3. **Materialization convergence (Finding 2, HIGH) — roadmap, after 1+2.**
   Single WORKBOOK-YAML runtime form for read and write.
4. **First-class hyphae-flag + SAMRAS encoding (Finding 3, MED) —
   roadmap.** Canonical-compile binding key; document SAMRAS form now.
5. **Lens Utilities/Control-Panel UX (Finding 4, MED) — roadmap.**
   Catalog + toggle, reusing the palette pattern.
6. **Stub-intent docs (Finding 5) — lands this batch.** Document the
   crypto/contract/registry placeholders; keep them deferred.
7. **End-to-end harness — lands this batch.** A select→eligible-tools→
   apply-workbook→re-read e2e test pinning the working model so the
   convergence work has a regression net.

The current model is sound and shipping; the batch lands the foundational
fixes (core refactor + sheet-key + stub docs + e2e harness) and stages the
two HIGH/MED convergence items for the roadmap.

---

## Appendix — links

### Wiki pages (forward references; companion units publish them)

- [`../wiki/README.md`](../wiki/README.md) — wiki orientation index
- [`../wiki/separation_and_responsibility.md`](../wiki/separation_and_responsibility.md) — cross-repo ownership
- [`../wiki/datum_model_overview.md`](../wiki/datum_model_overview.md) — the three-layer model at a glance
- [`../wiki/l1_core_datum_kernel.md`](../wiki/l1_core_datum_kernel.md) — L1: addresses, hyphae, MSS, SAMRAS target
- [`../wiki/l2_surface_materialization.md`](../wiki/l2_surface_materialization.md) — L2: WORKBOOK-YAML codec + canonical mutation
- [`../wiki/l3_ui_read_surface.md`](../wiki/l3_ui_read_surface.md) — L3: read service + Excel-like UX
- [`../wiki/tool_eligibility_and_binding.md`](../wiki/tool_eligibility_and_binding.md) — hyphae-widened tool binding + palette
- [`../wiki/lens_resolution_and_management.md`](../wiki/lens_resolution_and_management.md) — lens registry + Utilities/Control-Panel target
- [`../wiki/mss_and_hyphae_identity.md`](../wiki/mss_and_hyphae_identity.md) — MSS hash vs SAMRAS bitstream
- [`../wiki/sandbox_save_naming.md`](../wiki/sandbox_save_naming.md) — `<document_type>.<msn_id>.<sandbox>.<name>.<hash>`
- [`../wiki/core_adapter_boundary.md`](../wiki/core_adapter_boundary.md) — the Finding-1 inversion and its fix
- [`../wiki/materialization_read_write_paths.md`](../wiki/materialization_read_write_paths.md) — the Finding-2 split
- [`../wiki/network_crypto_contract_future.md`](../wiki/network_crypto_contract_future.md) — the Finding-5 stub surfaces

### Cited code anchors

- L1: `MyCiteV2/packages/adapters/sql/datum_semantics.py`,
  `MyCiteV2/packages/core/datum_ops/ops.py:24`,
  `MyCiteV2/packages/core/datum_ops/node_ops.py:17`,
  `MyCiteV2/packages/core/mss/datum_identity.py:101,126`
- L2: `MyCiteV2/packages/core/datum_io/codec.py`,
  `MyCiteV2/packages/core/datum_ops/workbook.py`,
  `MyCiteV2/instances/_shared/runtime/portal_datum_workbench_mutation_runtime.py:495`,
  `MyCiteV2/packages/adapters/sql/datum_workbook_apply.py:60`
- L3: `MyCiteV2/packages/tools/workbench_ui/service.py:586`,
  `MyCiteV2/packages/state_machine/portal_shell/tool_eligibility.py:64`,
  `MyCiteV2/packages/state_machine/lens/registry.py:51`,
  `MyCiteV2/instances/_shared/portal_host/static/v2_portal_tool_palette.js`,
  `MyCiteV2/instances/_shared/portal_host/app.py:1707`

### Test command

```bash
cd /srv/repo/mycite-core && \
  /srv/venvs/fnd_portal/bin/python -m pytest MyCiteV2/tests -q
```

1187 tests collected. (This is a docs-only unit; pytest is not run here —
the verification recipe is the docs sanity + anchor-resolution check.)
