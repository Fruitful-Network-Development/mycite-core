# Instance payment + grantee storage (no MOS)

How grantee operational config and PayPal records are stored. **All of it is
plain instance-specific files** under a portal instance's private tree —
**never MOS**. (MOS is for portal *content* datums, not grantee operational
state. See `feedback_no_mos_for_grantee_paypal`.)

Base: `<private>/utilities/tools/` where `<private>` is the instance's private
dir, e.g. `/srv/webapps/mycite/fnd/private`.

## `fnd-csm/` — grantee profiles + tolling

| File | What | Writer / Reader |
|---|---|---|
| `grantee.<sponsor_msn>.<grantee_msn>.json` | The grantee profile: PayPal config (`paypal.{mode,client_id,client_secret,environment,plan_id,payment_link,webhook_url,webhook_id}`), SES creds, domains, etc. | `packages/core/grantee/store.py` `save_grantee_profile` (atomic: temp + fsync + `os.replace`) / `load_grantee_profile`; enumerated by `operational_store.load_grantee_profiles`. |
| `tolling.<sponsor>.<msn>.json` | Derived per-grantee tolling invoice (recomputed from the ledger). | `app.py` tolling routes (reuses the atomic grantee writer). |
| `tolling_ledger.json`, `tolling_billing_rules.json` | AWS cost ledger + rules. | tolling runtime. |

**Double-MSN filename is intentional**, not redundancy: `<sponsor_msn>` is the
operator that sponsors the grantee, `<grantee_msn>` is the grantee. One operator
(FND) currently sponsors all grantees, so the first segment repeats — but the
scheme supports multi-operator sponsorship.

## `paypal-csm/` — PayPal records + tenant config

| File | What | Writer / Reader |
|---|---|---|
| `orders.ndjson` | **Append-only event ledger** — one JSON object per line. Events: `create_order`, `capture_order`, `webhook_capture`. The canonical record of every PayPal order/capture/webhook. | written by `app.py` `_append_to_ndjson` (flush + `os.fsync` per line); read by `paypal.py` `_build_paypal_extension_payload` (recent 30 for the dashboard), the CSV export route, and the create/capture lookup helpers. |
| `paypal-csm.<domain>.json` | Per-domain PayPal config (operator-authored, static). | read by `_load_paypal_config_for_domain`. |
| `tenants/<ref>.json` | PayPal merchant/tenant config (operator-authored, static). | read by `_load_tenant_config`. |
| `fnd.json`, `spec.json`, `tool.<msn>.paypal-csm.json` | Tool/webhook metadata. | operator/portal forms. |

The public site never reads any of this directly — it calls
`GET /__fnd/paypal/config` (domain-resolved, secret-free) and the
create-order/capture-order/webhook routes.

## Retired
- `paypal-webhook.<msn>.json` sidecar — superseded by the inline
  `grantee.paypal.webhook_url`; the read-side fallback (`_hydrate_paypal_from_sidecar`)
  was removed 2026-06-08. No sidecar files exist.
- `actions.ndjson`, `profile_sync.ndjson` — empty, no readers/writers; deleted.
- MOS PayPal adapters are no longer consulted by the live path (the
  `adapters/sql/fnd_paypal.py` module remains only for separate workbench tooling).

## Future work (deferred — touches live records)
- `orders.ndjson` is append-only and unbounded. At meaningful volume, add
  rotation/archival (e.g. month-partitioned files, or migrate to SQLite for
  indexed queries). Premature today (single-digit orders); not done.
