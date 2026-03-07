# PayPal Payment Processing Abstraction (Prototype)

## Purpose

Define tenant-scoped, non-secret metadata needed to connect PayPal checkout flows to each client website.

This abstraction is configuration-first:

- portal metadata stores routing/context refs only
- `paypal_proxy` stores runtime checkout context state
- credentials remain in state/runtime and are never stored in tenant progeny metadata

## Tenant metadata keys

Tenant `profile_refs` now supports:

```json
"profile_refs": {
  "paypal_profile_id": "paypal:tenant:<tenant_id>",
  "paypal_site_base_url": "https://client.example.com",
  "paypal_checkout_return_url": "https://client.example.com/payments/paypal/return",
  "paypal_checkout_cancel_url": "https://client.example.com/payments/paypal/cancel",
  "paypal_webhook_listener_url": "https://api.example.com/paypal/webhook",
  "paypal_checkout_brand_name": "Client Brand"
}
```

These are non-secret references only.

## Preview endpoint (FND portal)

- `GET /portal/api/paypal/tenant/<tenant_id>/checkout_preview`

The endpoint:

1. loads tenant metadata refs
2. validates URL shape
3. derives return/cancel URLs from `paypal_site_base_url` if needed
4. returns deterministic checkout context + order template

## Queue/sync endpoint (paypal_proxy)

- `POST /api/admin/paypal/tenant/<tenant_id>/profile/sync`

Expected body:

```json
{
  "action": "checkout_profile_sync",
  "payload": {
    "checkout_preview": { "... preview response object ..." }
  }
}
```

Behavior:

- validates preview payload
- writes `checkout_context` under tenant state config
- returns queued response (`202`) with `request_id`

## Order creation behavior

- `POST /api/admin/paypal/tenant/<tenant_id>/orders/create`
- response now includes resolved `checkout_context` (return/cancel URLs and brand metadata)

No direct end-user browser redirect is forced in this milestone; the tool returns deterministic context for staged integration with hosted tenant websites.
