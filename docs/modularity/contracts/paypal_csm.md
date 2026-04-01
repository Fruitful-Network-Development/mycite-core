# PayPal CSM Tool

- Owns: PayPal backend/ui/contracts/state adapter and compatibility webhook
  surface when still required.
- Does not own: general portal admin logic, unrelated tool state, shell verbs.
- Reads: instance-scoped PayPal tool state under
  `private/utilities/tools/paypal-csm/`.
- Writes: PayPal tenant state, FND PayPal state, action/order/profile-sync logs
  inside that tool bubble.
- Depends on: `tools/_shared`, `portal_core/shared`.
- Depended on by: FND admin integrations and the compatibility webhook runtime.

