# AWS CSM Tool

- Owns: AWS onboarding/backend logic, AWS tool contracts, AWS state adapter,
  AWS migrations.
- Does not own: portal runtime bootstrap, generic service-tool catalog rules,
  newsletter contact-list management, unrelated tool state.
- Reads: instance-scoped AWS tool state under
  `private/utilities/tools/aws-csm/`.
- Writes: AWS mailbox profile JSON plus action/provision logs inside that tool
  bubble.
- Depends on: `tools/_shared`, `mycite_core/runtime_host`,
  `mycite_core/state_machine`.
- Depended on by: FND admin integrations and future dedicated AWS tool routes.

## Runtime IAM Model

The EC2 server is the manager actor.

- Manager identity: IAM role `EC2-AWSCMS-Admin`, attached through the EC2
  instance profile.
- The role's managed and inline policies define what AWS actions the server can
  perform.
- SMTP identities are separate IAM users, not alternate forms of the EC2 role.
- Each managed SMTP IAM user should live under IAM path `/aws-cms/smtp/`.
- The IAM path is a policy-scoping prefix, not a filesystem path.
- The manager role should only be permitted to create, rotate, update, and
  delete SMTP IAM users under that IAM path.
- Each SMTP IAM user should carry its own narrow inline policy that allows
  `ses:SendRawEmail` only for its assigned mailbox or domain scope.

In short:

- the role manages
- policies grant actions
- mailbox IAM users hold the actual SMTP credentials

## Current Operational Model

Mailbox profiles are the canonical operational unit.

Each mailbox profile owns its own:

- `identity.profile_id`
- `identity.send_as_email`
- `identity.operator_inbox_target`
- `smtp.credentials_secret_name`
- `workflow.initiated`
- `verification.*`
- `inbound.*`

This means AWS-CMS should be read as mailbox-scoped state, even when profiles
are grouped by domain in the UI.

Examples:

- uninitiated mailboxes such as `aws-csm.tff.mark` or `aws-csm.cvcc.marilyn`
  may keep `smtp.username` blank and `smtp.credentials_secret_state=missing`
  while their mailbox onboarding remains uninitiated
- those same uninitiated mailboxes may still have an inbound routing shape, so
  their `inbound.receive_state` can be `receive_configured` rather than a fake
  catch-all `staged` receive label
- active technical-contact mailboxes can have
  `smtp.credentials_secret_state=configured`, a resolved `smtp.username`, and
  `workflow.handoff_status=ready_for_gmail_handoff` while still reporting
  `verification.status=not_started`,
  `provider.gmail_send_as_status=not_started`, and
  `inbound.receive_state=receive_pending`

`ready_for_gmail_handoff` does not mean Gmail send-as is verified.

Send-as verification is complete only when:

- a captured verification message or equivalent confirmation evidence exists
- `verification.status=verified`
- `provider.gmail_send_as_status=verified`

## State Semantics

The AWS-CMS workflow separates AWS-side SMTP readiness, Gmail send-as
verification, and inbound receive-path readiness.

- `smtp.credentials_secret_state=configured` plus a resolved `smtp.username`
  means SMTP material is provisioned and the mailbox is ready for Gmail handoff
- `workflow.handoff_status=ready_for_gmail_handoff` means the operator can begin
  Gmail send-as setup, not that Gmail confirmation is complete
- `workflow.is_send_as_confirmed=true` means both mailbox verification state and
  provider Gmail state are confirmed
- `workflow.is_mailbox_operational=true` additionally requires inbound receive
  readiness to be complete

Inbound state is independent from send-as state:

- `receive_unconfigured`
- `receive_configured`
- `receive_pending`
- `receive_verified`
- `receive_operational`

The portal and API should surface these mailbox-level fields directly instead of
flattening them into a domain-only readiness claim.

## SMTP Credential Guidance

Current default:

- `smtp.credentials_source` defaults to `operator_managed`

Current caution:

- the inline policy `AWSCMSManageSmtpCredentials` is obsolete for the live SES
  SMTP model
- future workflows must not rely on
  `CreateServiceSpecificCredential` or related APIs

Current implementation reality may still reuse a shared SMTP manager user such
as `aws-cms-smtp`, but that should be treated as transitional operational
behavior rather than the long-term mailbox contract.

## Future Per-Mailbox / Per-Domain Credential Guidance

Do not implement this in the current pass.

Future direction:

- each mailbox or domain can move to its own SMTP IAM user under
  `/aws-cms/smtp/`
- each mailbox profile's `smtp.credentials_secret_name` can point to a
  KeyPass-managed secret keyed by `identity.profile_id`
- a new admin-level IAM principal can create and rotate those per-mailbox or
  per-domain credentials
- the mailbox IAM user, not the EC2 role, remains the SMTP credential holder

This is architectural guidance only. The active default remains
`credentials_source=operator_managed` until the per-mailbox model is introduced.

## Live Alignment Reminder

Operational readiness still depends on live instance alignment.

- restart and deploy scripts must preserve canonical state roots such as
  `/srv/mycite-state/instances/<instance>/...`
- runtime environment variables must continue to point the portal at those
  canonical paths on deploy
- validate restart automation after deployment; during recent live work,
  `systemctl start fnd-portal.service` required interactive authentication, so
  manual runtime recovery was needed to keep the portal aligned with live state
