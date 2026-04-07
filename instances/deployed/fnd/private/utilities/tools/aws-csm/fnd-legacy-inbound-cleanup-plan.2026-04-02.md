# FND Legacy Inbound Cleanup Plan

Generated: `2026-04-02T16:28:00Z`

## Current purpose

This file captures the active legacy inbound dependency chain that is still participating in the FND Gmail send-as workflow.

It is intentionally preparation-only.

Do not remove these resources in this pass.

## Active dependency chain

1. SES active receipt rule set: `fnd-inbound-rules`
2. Matching receipt rule for FND verification mail: `mode-a-forward-dcmontgomery`
3. Rule recipients: `fruitfulnetworkdevelopment.com`
4. Rule S3 capture target: `s3://ses-inbound-fnd-mail/inbound/`
5. Rule Lambda action: `arn:aws:lambda:us-east-1:065948377733:function:ses-forwarder`
6. Lambda execution role: `arn:aws:iam::065948377733:role/service-role/ses-forwarder-role-l0ypgdpr`
7. Lambda environment:
   - `S3_BUCKET=ses-inbound-fnd-mail`
   - `S3_PREFIX=inbound/`
   - `FORWARD_TO=dylancarsonmontgomery@gmail.com`
   - `FROM_ADDRESS=forwarder@fruitfulnetworkdevelopment.com`
   - `SES_REGION=us-east-1`

## Verified current behavior

- The Gmail confirmation mail for `dylan@fruitfulnetworkdevelopment.com` was captured in S3 at:
  - `s3://ses-inbound-fnd-mail/inbound/o3j0tp3ac8smo7b5s1gpsul0aqrhdluk4dvurko1`
- The message subject was:
  - `Gmail Confirmation - Send Mail as dylan@fruitfulnetworkdevelopment.com`
- The portal now surfaces that captured message and its confirmation link directly.
- The legacy forwarder path is still active and replayable through `ses-forwarder`.
- The operator-confirmed Gmail verification succeeded after the forwarded message landed in Gmail junk.

## Inventory by classification

### Still required for the current verification-link and replay workflow

- `fnd-inbound-rules`
- `mode-a-forward-dcmontgomery`
- S3 bucket `ses-inbound-fnd-mail`
- S3 prefix `inbound/`
- Lambda `ses-forwarder`
- IAM role `ses-forwarder-role-l0ypgdpr`
- Lambda invoke permission from SES receipt rule `fnd-inbound-rules:mode-a-forward-dcmontgomery`

Why:

- S3 capture is the canonical source for the latest Gmail verification message metadata and confirmation link.
- Lambda replay still depends on `ses-forwarder` and its execution role.
- The operator-facing replay action currently routes through the existing forwarder rather than a new mail path.

### Replaceable by a cleaner portal-native verification surface

- Reliance on the forwarded Gmail copy for link discovery
- Reliance on Gmail junk/spam placement as the operator’s only path to the verification link
- Lambda replay as the only operator-visible resend mechanism

Why:

- The portal now reads the captured message metadata and confirmation link directly from S3 through the canonical admin AWS API.
- Once that portal-native path is accepted as the primary workflow, the system no longer needs mailbox hunting as the discovery mechanism.

### Active but unrelated or separately scoped leftovers

- Custom MAIL FROM: `dcmontgomery.fruitfulnetworkdevelopment.com`
- DMARC reporting target to `dcmontgomery@fruitfulnetworkdevelopment.com`
- SES receipt rule `mode-c-broadcast-command`
- Old Lambda resource-policy statements referencing `receipt-rule-set/default-receive:receipt-rule/forward-to-gmail`

Why:

- These are not required for the new operator-only AWS-CMS send-as baseline.
- They should be handled in their own cleanup pass, not mixed into send-as completion.

## Lambda role details

Role: `ses-forwarder-role-l0ypgdpr`

Attached policies:

- `AmazonSESFullAccess`
- `AmazonS3ReadOnlyAccess`
- `AWSLambdaBasicExecutionRole-fab59400-5094-4882-83b2-d7b92f0b6e59`

Inline policies:

- none

Observed state:

- `RoleLastUsed`: `2026-04-02T15:31:29+00:00`

Interpretation:

- This role is active legacy infrastructure, not removable residue.

## What must exist before the forwarder role can be removed

1. The portal-native verification surface must remain able to read the latest captured Gmail verification message and confirmation link without any Lambda forward.
2. A conscious decision must be made about whether forwarded copies to Gmail are still wanted as an operator convenience.
3. If replay is still needed, a replacement resend path must exist before removing `ses-forwarder`.
4. If replay is no longer needed, the operator workflow must explicitly rely on S3-captured message metadata + portal link display instead of forwarded Gmail copies.
5. SES receipt rule changes must be planned so capture remains available while Lambda forwarding is removed.
6. Historical inbound objects needed for audit/debugging must remain accessible or be archived first.

## Safe removal-readiness checklist for the next pass

- Confirm the portal verification workflow is accepted as the primary operator path:
  - refresh status
  - show latest verification message metadata
  - show verification link
  - confirm verified
- Decide whether `Replay Verification Forward` is still required after operators trust the portal-native link surface.
- If replay is no longer required:
  - remove the Lambda action from `mode-a-forward-dcmontgomery`
  - keep S3 capture in place long enough to validate the portal-only workflow
- If replay is still required:
  - build and validate the replacement resend mechanism first
- After the replacement decision is validated:
  - remove obsolete Lambda resource-policy statements tied to `default-receive/forward-to-gmail`
  - remove the `ses-forwarder` Lambda only after the receipt rule no longer invokes it
  - remove `ses-forwarder-role-l0ypgdpr` only after the Lambda is removed or no longer uses it
- Handle `dcmontgomery.*` MAIL FROM and DMARC cleanup separately from the receipt-rule/Lambda removal

## Notes for the next pass

- `AWSCMSManageSmtpCredentials` is obsolete for the current SMTP model and should not shape the cleanup design.
- The next cleanup pass should explicitly separate:
  - verification workflow replacement
  - Lambda/role removal
  - custom MAIL FROM cleanup
  - DMARC target cleanup
