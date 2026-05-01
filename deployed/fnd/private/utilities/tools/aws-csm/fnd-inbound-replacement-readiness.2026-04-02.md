# FND Inbound Replacement Readiness

Date: 2026-04-02

## Current Live Legacy Dependency Inventory

- SES active receipt rule set: `fnd-inbound-rules`
- SES receipt rule: `mode-a-forward-dcmontgomery`
- Receipt recipients: `fruitfulnetworkdevelopment.com`
- Capture bucket: `ses-inbound-fnd-mail`
- Capture prefix: `inbound/`
- Lambda forwarder: `ses-forwarder`
- Lambda role: `ses-forwarder-role-l0ypgdpr`
- Lambda environment:
  - `S3_BUCKET=ses-inbound-fnd-mail`
  - `S3_PREFIX=inbound/`
  - `FORWARD_TO=dylancarsonmontgomery@gmail.com`
  - `FROM_ADDRESS=forwarder@fruitfulnetworkdevelopment.com`
  - `SES_REGION=us-east-1`

## What The Current Portal Can Already Replace

- Portal-native latest inbound message metadata display from the captured SES message.
- Portal-native capture reference display via `s3://ses-inbound-fnd-mail/inbound/<message-id>`.
- Portal-native extracted verification-link display.
- Portal-native receive-path status refresh.
- Portal-native operator confirmation of receive-path visibility.

These features mean the forwarded Gmail copy is no longer the primary operator interface for verification.

## What Still Depends On The Legacy Forwarder Chain

- Compatibility replay of the latest verification message still invokes the `ses-forwarder` Lambda.
- Any workflow that depends on receiving a forwarded copy in `dylancarsonmontgomery@gmail.com` still depends on:
  - `fnd-inbound-rules`
  - `mode-a-forward-dcmontgomery`
  - `ses-forwarder`
  - `ses-forwarder-role-l0ypgdpr`
  - the current `FORWARD_TO` environment value

## Live AWS Notes

- The `ses-forwarder` Lambda policy still contains stale invoke permissions for `default-receive/forward-to-gmail`.
- Those policy entries are cleanup candidates for a later pass, but they should not be removed until the replacement path is fully verified.
- `ses-forwarder-role-l0ypgdpr` is active legacy infrastructure, not dead residue.

## Retirement Gates For `ses-forwarder-role-l0ypgdpr`

Do not remove the role until all of the following are true:

1. Portal-native latest-message metadata display is verified for active mailbox profiles.
2. Portal-native verification-link display is verified for active mailbox profiles.
3. Operators no longer rely on forwarded Gmail copies as the normal verification workflow.
4. Replay is either no longer needed or has been moved to a replacement service/function that does not use `ses-forwarder-role-l0ypgdpr`.
5. Active mailbox receive-routing status can be refreshed and confirmed without the legacy Lambda path.
6. A rollback path exists to restore the old replay/forward behavior if the replacement path fails.

## Cleanup Readiness Checklist

- [ ] Verify portal-native inbound message display against all active mailbox profiles that use verification mail.
- [ ] Verify portal-native extracted link display against live captured messages.
- [ ] Decide whether replay should remain, be replaced, or be removed entirely.
- [ ] If replay remains, implement the replacement replay mechanism and test it against a captured message.
- [ ] Remove operator documentation that still tells users to search Gmail spam/junk as the primary path.
- [ ] Confirm no production workflow still depends on `forwarder@fruitfulnetworkdevelopment.com` mail delivery.
- [ ] Remove stale Lambda invoke-policy entries for `default-receive/forward-to-gmail`.
- [ ] Remove the receipt rule Lambda action only after replacement replay/visibility is verified.
- [ ] Remove `ses-forwarder-role-l0ypgdpr` only after the Lambda is no longer in the active path.

## Rollback Strategy

- Keep the current receipt rule set, S3 capture bucket, Lambda function, and role intact until the replacement path has been exercised against live traffic.
- If portal-native replacement fails, retain the current rule + S3 + Lambda path and continue using forwarded Gmail copies as a compatibility fallback until the replacement is repaired.
