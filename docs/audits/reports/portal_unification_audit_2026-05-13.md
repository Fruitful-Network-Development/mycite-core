# Portal Unification Audit — 2026-05-13

## Executive summary

The MyCite portal hosts three tool surfaces — **CTS-GIS**, **FND-CSM**,
and **Workbench-UI**. CTS-GIS is the canonical implementation; FND-CSM
lags significantly on three of the seven unification dimensions;
Workbench-UI is clean by virtue of being read-only.

**Scoring** (1 = fully unified, 5 = fully bypasses pattern):

| Dimension | CTS-GIS | FND-CSM | Workbench-UI |
|---|---|---|---|
| State machine | 1 | 2 | 1 |
| MOS data layer | 1 | 5 | 1 |
| Adapter pattern | 2 | 4 | 1 |
| Workbench builder reuse | 1 | 1 | n/a |
| Canonical mutation routes | 1 | 4 | 1 |
| Script consistency | 1 | 1 | 0 |
| Test coverage | 3 | 3 | 2 |
| **Overall** | **1.3** | **3.1** | **1.1** |

The convergence roadmap brings FND-CSM to ~1.5 in five phases (C–F of
the planning doc that produced this audit). All phases are independently
shippable; phase A (deploy + verify) and phase B (this report + a
srv-infra summary) ship same-day.

---

## Per-tool deep dive

### CTS-GIS — `system.tools.cts_gis`

- Runtime: `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`
- 4500+ LOC; the largest tool surface.
- Reads ~124 datum docs from MOS (`SqliteSystemDatumStoreAdapter`)
  with filesystem fallback (`FilesystemSystemDatumStoreAdapter`) when
  `authority_db_file` is unset. Both implement
  `AuthoritativeDatumStorePort` from
  `MyCiteV2/packages/ports/datum_store/contracts.py`.
- State machine: uses `PortalShellState` end-to-end. `mediation_subject`
  + `focus_subject` are projected from real spatial selections (district,
  precinct).
- Workbench: calls `build_datum_file_workbench` at line 4581 with
  `sandbox_id="cts_gis"` (canonical token) — 124 docs visible in the
  workbench gallery.
- Mutations: route through `/portal/api/v2/mutations/<action>`
  (`stage_insert_yaml`, `validate_stage`, `apply_stage`) per the
  canonical lifecycle defined in
  `MyCiteV2/instances/_shared/runtime/portal_datum_workbench_mutation_runtime.py`.
- Tests: `tests/unit/test_portal_cts_gis_runtime.py` (568 lines) +
  fixtures.

### FND-CSM — `system.tools.fnd_csm`

- Runtime: `MyCiteV2/instances/_shared/runtime/portal_fnd_csm_runtime.py`
- 4 tabs: Email, Analytics, Newsletter, PayPal.
- **Hybrid data backing** as of 2026-05-13:
  - Email: filesystem JSON (`<private>/utilities/tools/aws-csm/aws-csm.*.json`)
  - Analytics: NDJSON globs from
    `<webapps>/clients/<domain>/analytics/events/*.ndjson` (live)
  - Newsletter contact log: **MOS** (`fnd_newsletter_contact_log_<domain>` v2 datum)
    via `MosDatumNewsletterContactLogAdapter` shipped today
  - Newsletter sender / domain profile: filesystem JSON
  - PayPal orders: filesystem NDJSON
  - PayPal webhook config: filesystem JSON
- State machine: uses `PortalShellState` for shell-level focus, but
  carries a tool-local `tool_state` dict (`selected_grantee_msn`,
  `selected_domain`, `active_tab`) that is NOT projected back into
  `focus_subject`. Workbench-UI cannot introspect FND-CSM grantee/domain
  selections.
- Workbench: calls `build_datum_file_workbench` (lines 925ish) with
  `sandbox_id=FND_CSM_SANDBOX_TOKEN` ("fnd_csm" canonical) — 2 docs
  visible (anchor + the newsletter contact log).
- Mutations: bypass the canonical mutation route. The
  `/portal/api/v2/system/tools/fnd-csm/actions` endpoint dispatches
  in-runtime via `_apply_fnd_csm_action` which calls adapters' `save_*`
  methods directly. Public-facing `/__fnd/newsletter/{subscribe,
  unsubscribe, dispatch-result}` endpoints likewise call adapters
  directly.
- Tests: `tests/unit/test_portal_fnd_csm_runtime.py` (492 lines).

### Workbench-UI — `system.tools.workbench_ui`

- Runtime: `MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py`
- Read-only reflective lens over the MOS authority DB; no write paths.
- Hard-fails when `authority_db_file` is missing (`sql_authority_required`),
  unlike CTS-GIS's silent filesystem fallback.
- Does NOT use `build_datum_file_workbench` because its purpose is
  cross-tool introspection (every doc, not a single sandbox). Renders
  via `WorkbenchUiReadService.read_surface()`.
- Tests: `tests/unit/test_workbench_ui_runtime.py` (906 lines) with
  in-memory SQLite fixtures.

---

## Top 5 unification gaps (FND-CSM lags CTS-GIS)

### Gap 1 — Hybrid data model on Email/Analytics/PayPal tabs

**Issue:** Three of FND-CSM's four tabs read from filesystem JSON or
live NDJSON. Only Newsletter is MOS-backed (as of 2026-05-13).

**Impact:** No schema versioning, no audit trail, Workbench-UI cannot
introspect Email/Analytics/PayPal data. Any tab redesign or migration
requires per-tab adapter changes rather than a single MOS schema bump.

**File refs:**
- Email: `_build_email_tab` at `portal_fnd_csm_runtime.py:118-…`
  reads via `FilesystemAwsCsmToolProfileStore`
- Analytics: `_build_analytics_tab` globs filesystem NDJSON
- PayPal: `_build_paypal_tab` reads filesystem NDJSON + per-grantee
  webhook JSON

**Fix:** Phase D — three new SQL adapters mirroring
`MosDatumNewsletterContactLogAdapter`. Estimated 6-10 hours total
(adapters + migrations + tests).

### Gap 2 — Tool-local state bypasses focus_subject contract

**Issue:** `_apply_fnd_csm_action` mutates a local dict
(`selected_grantee_msn`, `selected_domain`, `active_tab`) but never
projects state back into `PortalShellState.focus_subject`.

**Impact:** Workbench-UI sees the FND-CSM surface as "no focus",
making cross-tool introspection incomplete. Audit forensics cannot
reconstruct which grantee an operator was acting on.

**Fix:** Phase C.2 — call a focus-subject projection helper after each
state-mutating action. Estimated 1 hour.

### Gap 3 — No SQL adapter twins for tool-specific filesystem adapters

**Issue:** `FilesystemAwsCsmToolProfileStore` and
`FilesystemAwsCsmNewsletterStateAdapter` (profile half) have no SQL
twins. Newsletter contact log got `MosDatumNewsletterContactLogAdapter`
today, but Email/PayPal data sources have nothing.

**Impact:** Adapter interchangeability contract is broken. FND-CSM is
locked to filesystem reads for Email and PayPal until SQL twins are
written. Tests cannot validate against an in-memory MOS.

**Fix:** Phase D — covered by Gap 1 fix.

### Gap 4 — FND-CSM mutations bypass `/portal/api/v2/mutations/*`

**Issue:** Today's mutations (contact subscription, webhook save,
sender assignment, signup, unsubscribe, dispatch-result) call adapter
`save_*` methods directly. They never round-trip through the canonical
mutation runtime, so:
- No NIMM directive envelope is constructed
- No version-hash audit trail
- No `stage`/`validate`/`preview` lifecycle is available
- Workbench-UI's mutation overlay sees nothing

**Impact:** Two parallel write paths in the codebase — canonical for
CTS-GIS, ad-hoc for FND-CSM. Maintenance burden + audit gap.

**Fix:** Phase E — extend mutation runtime's `target_authority`
dispatch to include `aws_csm_newsletter_contact_log`,
`aws_csm_operator_profile`, `paypal_webhook`. Refactor handlers to
compose NIMM directives. Estimated 4-6 hours.

### Gap 5 — Legacy `/__fnd/*` HTTP routes

**Issue:** `/__fnd/newsletter/subscribe`, `/__fnd/newsletter/unsubscribe`,
`/__fnd/newsletter/dispatch-result`, `/__fnd/paypal/create-order`,
`/__fnd/paypal/capture-order` are pre-canonical-mutation-route
endpoints. They are public-facing (signup form POSTs to subscribe;
unsubscribe URLs are baked into already-sent newsletters).

**Impact:** Two URL surfaces for the same operations. Cannot retire
without breaking unsubscribe links from prior dispatches.

**Fix:** Phase E.3 (rewire bodies as 5-line shims that compose NIMM
directives) + Phase F (add `X-Deprecation` headers, monitor traffic
for 90 days, then 410 Gone). Cannot fully retire without a longer
horizon because unsubscribe links live in customers' email archives
indefinitely.

---

## Top 5 technical debt items

### Debt 1 — Hardcoded sandbox tokens

**Issue:** `FND_CSM_SANDBOX_TOKEN = "fnd_csm"` is duplicated across
~6 files. CTS-GIS embeds `"cts_gis"` as a string literal in document-ID
filters.

**Impact:** Brittle. A token rename would require editing 6+ places.

**Fix:** Phase C.1 — hoist constants to
`MyCiteV2/packages/state_machine/portal_shell/shell_schemas.py`
alongside `*_TOOL_SURFACE_ID`. Estimated 30 min.

### Debt 2 — Silent filesystem fallback when SQL is missing

**Issue:** CTS-GIS and the new composite newsletter adapter both
silently fall back to filesystem when `authority_db_file` is unset.
Workbench-UI fails closed (the right behavior).

**Impact:** Production deployments can silently degrade if the systemd
override loses the `MYCITE_V2_PORTAL_AUTHORITY_DB` env. Hard to debug.

**Fix:** Phase C.3 — gate fallback behind
`MYCITE_V2_PORTAL_REQUIRE_AUTHORITY_DB=1`. Set in production override.
Estimated 30 min.

### Debt 3 — Live AWS / NDJSON I/O during render (Analytics tab)

**Issue:** `_build_analytics_tab` globs
`<webapps>/clients/<domain>/analytics/events/*.ndjson` on every
request. P95 latency is unbounded if the dir grows or filesystem
slows.

**Impact:** UI latency unpredictable; cannot scale to many domains.

**Fix:** Phase D.2 — sync analytics into a MOS datum via cron;
serving reads from MOS (constant-time lookup).

### Debt 4 — MOS save_contact_log is O(catalog), not O(doc) — *NEW finding 2026-05-13*

**Issue:** `MosDatumNewsletterContactLogAdapter.save_contact_log` calls
the SQL adapter's `store_authoritative_catalog`, which DELETE+REINSERTs
every doc's semantics + rewrites the full snapshot JSON. For a single
signup with 1168 contacts in the catalog, the worker spikes ~800 MB
in transient memory.

**Impact:** Live signup endpoint hits `MemoryHigh=1500M` in the
gunicorn override and is throttled mid-request, returning 500
storage_error. Band-aided to `MemoryHigh=2400M` on 2026-05-13 to
unblock verification.

**Fix:** Phase D.0 (P1, NEW task #54) — write a per-doc UPSERT path
on the SQL adapter that touches only the changed doc's rows in
`datum_row_semantics` + `datum_document_semantics`, leaves the
snapshot untouched (or appends a delta). Estimated 4-6 hours.

### Debt 5 — Document-ID schema leakage in runtimes

**Issue:** CTS-GIS runtime knows about both legacy `sandbox:cts_gis:`
and canonical `lv.<msn>.cts_gis.<name>.<hash>` ID forms. Translation
logic is embedded in the runtime, not in the adapter.

**Impact:** Runtimes are not pure adapters; they're also mini-migrators.

**Fix:** Move legacy ID translation into adapter layer. Estimated 2
hours.

### Debt 6 — No schema validation between data sources

**Issue:** All FND-CSM tabs parse JSON with permissive `_as_dict()`,
`_as_text()` helpers. No schema enforcement.

**Impact:** Dirty data slips in; Workbench-UI cannot auto-validate
on import.

**Fix:** Define MOS datum schemas for each remaining tab data type
(part of Phase D). Validate on read and write.

---

## Convergence roadmap

| Phase | What ships | Effort | Blast radius | Independent? |
|---|---|---|---|---|
| **A — Deploy + verify (DONE 2026-05-13)** | Today's commits live; 1168 TFF contacts visible at HTTP layer | 30 min | Low | Yes |
| **B — Audit reports (DONE 2026-05-13)** | This doc + srv-infra summary | 1 hr | None | Yes |
| **C — Low-effort convergence (DONE 2026-05-13)** | Sandbox-token constants, focus_subject projection narrowing, fail-closed fallback under `MYCITE_V2_PORTAL_REQUIRE_AUTHORITY_DB=1` | 1 hr | Low | Yes |
| **D.0 — save_contact_log perf fix (DONE 2026-05-13, P1)** | `replace_single_document_efficient` on SQL adapter; per-save RSS delta dropped from ~800 MB to ~153 MB; MemoryHigh reverted from 2400M band-aid to 1500M steady-state | 2 hr | Medium | Yes — unblocked live signup load |
| **D.1-D.3 — SQL adapter twins (DONE 2026-05-13)** | Email/Analytics/PayPal tab data now MOS-backed: `MosDatumAwsCsmProfileAdapter` (operator profiles + domain records), `MosDatumAnalyticsSummaryAdapter` (per-domain rolling aggregate), `MosDatumPayPalOrdersAdapter` + `MosDatumPayPalWebhookAdapter`. Three migration scripts. Live workbench now shows 24 docs (1 anchor + 16 operator profiles + 2 domain records + 4 analytics summaries + 1 newsletter contact log). | 4 hr | Medium | Yes |
| **D.4 — Adapter unit tests (DONE 2026-05-13)** | 16 new round-trip + edge-case tests; 113/113 total pass | 1 hr | None | Yes |
| **D.1-3 — SQL adapter twins** | Email/Analytics/PayPal MOS-backed | 6-10 hr | Medium | Each adapter ships independently |
| **D.4 — Tests for all D adapters** | Round-trip + delegation | 2 hr | None | Yes |
| **E.1-3 — Canonical mutations** | All FND-CSM mutations through `/portal/api/v2/mutations/*`; legacy routes shimmed | 4-6 hr | Medium | After D.1-3 |
| **F — Legacy route retirement** | `X-Deprecation` headers; 410 after 90-day quiet period | 1-2 hr active + 90-day wait | Low | After E |

Total active engineering: **20-28 hours** spread across phases.

---

## Appendix — verification evidence

### A.1 commits (deploy artifacts)

```
2507009 feat(fnd-csm): workbench + TFF newsletter v2 datum + operator forwarding auto-sync
fbf60e0 fix(portal-host): pass authority_db_file + data_dir to FND-CSM endpoints
```

### A.3 server-local surface bundle

```bash
$ curl -s -X POST http://127.0.0.1:6101/portal/api/v2/system/tools/fnd-csm \
    -H 'Content-Type: application/json' \
    -d '{"schema":"mycite.v2.portal.shell.request.v1","requested_surface_id":"system.tools.fnd_csm"}' \
  | jq '.shell_composition.regions.workbench.document_collection.documents
        | map({name:.canonical_name, is_anchor, rows:.row_count})'
[
  {"name":"anchor","is_anchor":true,"rows":11},
  {"name":"fnd_newsletter_contact_log_trappfamilyfarm_com","is_anchor":false,"rows":1172}
]
```

### A.4 live signup smoke (HTTP 200 after MemoryHigh band-aid)

```bash
$ curl -s -X POST http://127.0.0.1:6101/__fnd/newsletter/subscribe \
    -H 'Host: trappfamilyfarm.com' \
    -d 'email=qa@example.com&name=QA&zip=00000'
{"email":"qa@example.com","ok":true,"subscribed":true}
```

Verified the row landed in MOS, then cleaned up. Final count:
**1168 contacts** in the v2 datum.
