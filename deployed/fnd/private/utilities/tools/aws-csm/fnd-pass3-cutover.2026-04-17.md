# AWS-CSM Pass 3 Cutover

Date: 2026-04-17

## Summary

- Pass 3 was cut over onto the existing Lambda `newsletter-inbound-capture`.
- The legacy Lambda `ses-forwarder` was left in place for rollback, but it is no
  longer in the active receipt-rule path.
- FND, TFF, and CVCC verification-class inbound mail now routes through the
  repo-owned replacement flow.

## Live changes applied

- Updated Lambda code for `newsletter-inbound-capture` from the repo-owned pass
  3 source.
- Updated Lambda environment to include:
  - `VERIFICATION_ROUTE_MAP_JSON`
  - `VERIFICATION_ALLOWED_SENDERS_JSON`
  - `VERIFICATION_FORWARD_FROM_ADDRESS`
- Updated Lambda timeout from `20` to `30`.
- Updated inline policy `NewsletterInboundCaptureExecution` on
  `newsletter-inbound-capture-role` to include:
  - `s3:GetObject` on `arn:aws:s3:::ses-inbound-fnd-mail/inbound/*`
  - `ses:SendEmail`
  - `ses:SendRawEmail`
  - `sesv2:SendEmail`
- Added SES invoke permission for:
  - `portal-capture-trappfamilyfarm-com`
  - `portal-capture-cuyahogavalleycountrysideconservancy-org`
  - `mode-a-forward-dcmontgomery`
- Updated receipt rules:
  - `portal-capture-trappfamilyfarm-com` now includes a Lambda action to
    `newsletter-inbound-capture`
  - `portal-capture-cuyahogavalleycountrysideconservancy-org` now includes a
    Lambda action to `newsletter-inbound-capture`
  - `mode-a-forward-dcmontgomery` now targets `newsletter-inbound-capture`
    instead of `ses-forwarder`
  - `mode-a-forward-dcmontgomery` now writes to
    `inbound/fruitfulnetworkdevelopment.com/`

## Smoke verification

### Confirmation forward

- Invoked `newsletter-inbound-capture` with the live captured Gmail
  confirmation message:
  - S3 object: `s3://ses-inbound-fnd-mail/inbound/o3j0tp3ac8smo7b5s1gpsul0aqrhdluk4dvurko1`
  - Recipient: `dylan@fruitfulnetworkdevelopment.com`
- Result:
  - Lambda returned `forwarded[0].sent_to =
    dylancarsonmontgomery@gmail.com`
  - The returned forward message id was
    `0100019d9a1e6dc6-3ff60141-cd98-4060-aa64-a0da32da27d4-000000`

### Report suppression

- Invoked `newsletter-inbound-capture` with the live DMARC/report sample:
  - S3 object: `s3://ses-inbound-fnd-mail/inbound/3r851tctbmlit8nkd6ljo0tig5gc3mu0tppe1ng1`
  - Subject:
    `[FWD] Report domain: fruitfulnetworkdevelopment.com Submitter: google.com Report-ID: 4554987642169396140`
- Result:
  - Lambda returned `forwarded: []`
  - The report remained captured in S3 and did not trigger a forwarded message

## Remaining follow-up

- Remove stale invoke-policy statements from `ses-forwarder` in a later cleanup
  pass.
- Decide separately whether to retire `ses-forwarder` and
  `ses-forwarder-role-l0ypgdpr` after additional live observation.
