# FND-CSM Baseline Audit

**Date:** 2026-05-13
**Surface:** `system.tools.fnd_csm` — `portal.system.tools.fnd_csm`
**Sandbox:** `fnd_csm`
**Authority DB used:** `/srv/mycite-state/instances/fnd/private/mos_authority.sqlite3`
**Private dir:** `/srv/mycite-state/instances/fnd/private`

This audit establishes the baseline operability of the FND-CSM tool surface before
the workbench is enabled and the first sandbox datum document is materialized
(see `frolicking-questing-meerkat` plan, Phases 2–5).

---

## Unit-test baseline

`pytest MyCiteV2/tests/unit/test_portal_fnd_csm_runtime.py` — **25 / 25 pass**.

Coverage spans grantee profile loading, per-tab builders (`_build_email_tab`,
`_build_analytics_tab`, `_build_newsletter_tab`, `_build_paypal_tab`),
component frame composition, the `engage_component_frame` action, and the
bundle entry-point. No regressions.

---

## Live bundle exercise

`run_portal_fnd_csm({"requested_surface_id": "system.tools.fnd_csm"}, private_dir=…, webapps_root="/srv/webapps", portal_instance_id="fnd", portal_domain="trappfamilyfarm.com", authority_db_file=…)` returns a clean envelope (no `error`, no `warnings`).

`shell_composition.regions` keys observed: `activity_bar`, `control_panel`,
`workbench`, `interface_panel`. The workbench reports
`kind="datum_file_workbench"`, `visible=False`, `sandbox={"id":"fnd-csm","label":"FND-CSM"}`,
`document_collection.documents=[]`, `active_document=None` — exactly matching the
known blockers (anchor missing, no sandbox docs, sandbox token uses URL-slug).

The interface panel reports `kind="tabbed_interface_panel"`, `visible=True`,
`default_tab_id="email"`, four tabs.

### Per-tab status

| Tab ID | Initializer intent | Renders | Has data (sample domain) | Notes |
|--------|---------------------|---------|---------------------------|-------|
| `email` | `resolve_email_profile` | yes | mailboxes=1; domain_status=conditional | `fnd_csm.email.domain_status` only emits when `email_tab.domain_record` has scalar items. CVCC: present. TFF: absent. **Behavior is intentional**, not a gap. |
| `analytics` | `resolve_analytics_summary` | yes | summary=4 items; events=20 rows | Reads `webapps/clients/<domain>/analytics/events/*.ndjson` with a 3-month window. Working. |
| `newsletter` | `resolve_newsletter_state` | yes | sender=3 options; contacts=0 rows | Sender list resolves from grantee `users[]`. Contacts read from `private/utilities/tools/aws-csm/newsletter/newsletter.<domain>.contacts.json`, which is **empty across all configured domains**. See Gap 1. |
| `paypal` | `resolve_paypal_orders` | yes | webhook=1 item; orders=variable | Webhook config from `private/utilities/tools/paypal-csm/paypal-webhook.<msn>.json` (when present). Orders from `private/utilities/tools/paypal-csm/orders.ndjson`, filtered by domain. |

### Frame `kind` is `None`

Every component frame returns `kind=None` over the wire. This is not a bug —
the FND-CSM workspace JS renderer (`v2_portal_fnd_csm_workspace.js`) dispatches by
`frame_id` convention (`fnd_csm.tab.<tabId>` and `fnd_csm.<tab>.<frame>`), not by
`kind`. The renderer is functioning as designed.

---

## Gaps identified

### Gap 1 — Newsletter contacts directory empty (defer to Phase 5)
`/srv/mycite-state/instances/fnd/private/utilities/tools/aws-csm/newsletter/` does
not exist. The legacy data lives at
`/srv/webapps/clients/<domain>/contacts/<domain>-contact_log.json` with the
**legacy** schema `mycite.webapp.contact_log.v1`, while
`FilesystemAwsCsmNewsletterStateAdapter.load_contact_log`
(`packages/adapters/filesystem/aws_csm_newsletter_state.py:150`) requires the
**new** schema `mycite.service_tool.aws_csm.newsletter_contact_log.v1` at
`<private>/utilities/tools/aws-csm/newsletter/newsletter.<domain>.contacts.json`.

**Action:** do **not** patch this in Phase 1. The migration target is the
`fnd_newsletter_contact_log` datum (schema `mycite.v2.datum.fnd.newsletter.contact_log.v1`,
contract at `docs/contracts/fnd_newsletter_contact_log_datum.md`). The new
template-driven seed script (Phase 5) will read the legacy JSON and materialize
the first FND-CSM datum document, replacing the filesystem adapter path.

### Gap 2 — Workbench sandbox token uses URL-slug form (fix in Phase 2.2)
`portal_fnd_csm_runtime.py:899` passes `sandbox_id="fnd-csm"` to
`build_datum_file_workbench`. Per
`docs/contracts/datum_document_naming_taxonomy.md` §"URL Slug vs Sandbox Token",
canonical sandbox tokens use **underscores** (`fnd_csm`); URL slugs use
hyphens. The mutation runtime
(`portal_datum_workbench_mutation_runtime.py:78-87`) compares against the
canonical token from the `documents` table and would reject any mutation
attempt with `sandbox_document_mismatch` once docs exist.

**Action:** fix in Phase 2.2 (Task #5).

### Gap 3 — Workbench is invisible by design pending Phase 2 wiring
`workbench.visible=False` because `anchor_document=None` and `sandbox_documents=[]`.
This is the blocker addressed by Phase 2 (Tasks #5–#8): bootstrap the FND-CSM
sandbox anchor in MOS, load sandbox docs from the SQL adapter, set `visible=True`.

### Gap 4 — Domain selection from request payload is ignored at first-load
`run_portal_fnd_csm` always resolves the active domain from shell_state
(default: alphabetically first grantee + first domain). A `selected_domain` field
on the initial request payload has no effect; switching domains requires a
follow-up `select_domain` action via `run_portal_fnd_csm_action`. This is a
documented runtime invariant (shell_state owns focus); not a defect for Phase 1.

---

## Conclusion

- All four FND-CSM tabs render with their expected child frames and consume the
  expected data sources.
- No tab is structurally broken; data emptiness in the Newsletter tab is a
  migration / data-population concern that is the explicit subject of Phase 5.
- The only in-scope baseline defect is the sandbox-token form (Gap 2). Fix in
  Phase 2.2 along with workbench enablement.
- Phase 1 acceptance: **PASS** (with deferred actions explicitly routed to
  Phases 2 and 5).
