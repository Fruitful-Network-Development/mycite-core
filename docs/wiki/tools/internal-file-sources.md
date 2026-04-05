# Internal File Sources

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Tools](README.md)

## Status

Canonical

## Parent Topic

[Tools](README.md)

## Current Contract

Internal operational files may be consumed by tools only through shared-core read-only services. Tools do not receive raw filesystem authority.

The shared-core internal-source contract currently supports:

- `json`
- `ndjson`
- `nginx_access_log`
- `nginx_error_log`
- `text` fallback

Current implementation seam:

- `_shared.portal.application.internal_sources`
- consumed by service-collection config-context assembly in `_shared.portal.application.service_tools`

## FND-EBI Pattern

`fnd_ebi` remains a service-collection tool anchored by `tool.<msn_id>.fnd-ebi.json` in the tool sandbox. `web-analytics.json` is compatibility-read only. Profile members such as `fnd-ebi.fnd.json` provide:

- `domain`
- `site_root`

Analytics paths are derived by shared core logic:

- `client_root = dirname(site_root)`
- `analytics_root = client_root + "/analytics"`
- `access_log = analytics_root + "/nginx/access.log"`
- `error_log = analytics_root + "/nginx/error.log"`
- `events_file = analytics_root + "/events/YYYY-MM.ndjson"` (current UTC month)

The profile JSON remains the canonical input. Full analytics file paths are derived and not duplicated in profile payloads by default.

Current FND-EBI projection from those derived sources includes:

- freshness (`last_seen_utc`) per access/error/events source when parseable
- traffic windows (`24h`, `7d`, `30d`)
- approximate unique visitors (IP-based)
- response class breakdown (`2xx/3xx/4xx/5xx`)
- bot-share and suspicious-probe counts
- top pages, referrers, and top error routes
- asset-vs-page request split
- events coverage summary and event-type counts
- explicit warning surfaces for missing/unreadable/stale/no-events/no-robots signals

## AWS-CMS Pattern (Operator Send-As Staging)

`aws_platform_admin` is the active AWS-CMS service-style tool projection over `aws-csm` sandbox profiles.

Canonical profile schema: `mycite.service_tool.aws_csm.profile.v1`

Canonical state root:

- `private/utilities/tools/aws-csm/`

Retired state root:

- `private/admin_runtime/aws/` is removed and is no longer read as compatibility state.

Required baseline groups:

- `identity` (mailbox profile identity, tenant/domain ownership, mailbox role, send-as address, and operator inbox target)
- `smtp` (Gmail send-as handoff fields, forwarding destination/status, SMTP readiness, and secret-reference metadata without raw credentials)
- `verification` (code/link/status/timestamps for the active send-as verification step)
- `provider` (provider-facing SES and Gmail send-as status snapshots)
- `workflow` (operator-only readiness, initiation state, lifecycle state, pre-handoff blockers, Gmail-side blockers, and completion-boundary summary)
- `inbound` (receive-routing target, receive state, forwarder dependency, and latest captured-message metadata)

Legacy flat fields (for example `alias_email`, `forward_to_email`, `gmail_send_as_status`) are normalized into these groups at service-tool context assembly. This is a compatibility transform only; canonical writes target grouped mailbox-profile documents under deterministic names such as `aws-csm.fnd.dylan.json` or `aws-csm.tff.technicalContact.json`.

Canonical grouped profile writes flow through `PUT /portal/api/admin/aws/profile/<profile_id>` in the admin integrations runtime. That path writes only to `private/utilities/tools/aws-csm/aws-csm.<profile>.json` and rejects raw secret-like keys; secret values remain external in Secrets Manager.

Canonical operator workflow actions flow through `POST /portal/api/admin/aws/profile/<profile_id>/provision`. The current live operator-facing actions are:

- `begin_onboarding`
- `refresh_provider_status`
- `refresh_inbound_status`
- `capture_verification`
- `replay_verification_forward`
- `confirm_receive_verified`
- `confirm_verified`

These actions keep the current operator send-as workflow on a single control plane instead of ad hoc file edits.

Current scope is intentionally narrow:

- one operator
- one mailbox profile at a time
- simple SES SMTP and Gmail send-as onboarding
- optional inbound-verification automation only as a future extension seam

Read-only operational inspection is available from the server through:

- `python3 /srv/repo/mycite-core/scripts/aws_csm_inspect.py --tenant <tenant>`

The inspector reads the canonical staged profile, inspects matching SES, Route 53, Secrets Manager, and inbound-mail resources through the AWS CLI, and emits a non-destructive classification report. It is intended for safe inventory and cleanup planning, not live mutation.

The inspector now also emits `aws.smtp_secret_health`, which safely reports whether the referenced secret looks placeholder-like and whether SMTP AUTH succeeded, without exposing raw secret values.

Current readiness boundary is explicit:

- the EC2 server acts through manager role `EC2-AWSCMS-Admin`; SMTP mailbox
  credentials belong to separate IAM users rather than to the manager role
- SMTP IAM users should be scoped under IAM path `/aws-cms/smtp/`; that path is
  an IAM naming/policy prefix, not a filesystem directory
- `identity.profile_id` is mailbox-scoped and deterministic; mailbox profiles are the canonical operational unit instead of one-profile-per-domain.
- `workflow.initiated` and `workflow.lifecycle_state` distinguish staged/uninitiated mailboxes from initiated onboarding work.
- `smtp.credentials_secret_name` and `smtp.credentials_secret_state` may describe a placeholder reference or a known auth failure without implying that real SMTP credentials are resolved.
- `smtp.credentials_secret_state = configured` together with a resolved `smtp.username` means the SMTP side is ready for Gmail handoff, not that Gmail send-as is already verified.
- `smtp.credentials_source` continues to default to `operator_managed` in the
  active model.
- `smtp.handoff_ready` is derived from the same configuration boundary as `workflow.is_ready_for_user_handoff` so the SMTP group and workflow group stay in sync.
- `workflow.configuration_blockers_now` is the list that must clear before Gmail/inbox handoff is trustworthy.
- `workflow.gmail_handoff_blockers_now` is the intentional remaining boundary after AWS-side staging is complete.
- `workflow.inbound_blockers_now` is the receive-path gap list for portal-native capture/display and inbound confirmation.
- `workflow.operational_blockers_now` is the union of Gmail-side and inbound-side blockers for full mailbox operationality.
- `workflow.is_ready_for_user_handoff = true` means ready for Gmail/inbox handoff, not that send-as is fully verified.
- `workflow.handoff_status`, `workflow.lifecycle_state`, and `workflow.completion_boundary` distinguish staging, uninitiated mailboxes, SMTP-configured mailboxes, Gmail-handoff readiness, receive-path follow-through, and confirmed completion.
- `workflow.handoff_status = ready_for_gmail_handoff` means AWS-side SMTP
  material is provisioned and operator Gmail work can begin; it does not mean
  the send-as is already verified.
- `verification.portal_state = verification_email_received` means the latest Gmail confirmation message has been captured and surfaced, but the operator still needs to complete or confirm the Gmail step.
- `verification.portal_state = verified`, `verification.status = verified`, and
  `provider.gmail_send_as_status = verified` together mark the confirmed
  send-as completion state.
- `inbound.receive_state` is mailbox-scoped and distinct from send-as state: `receive_unconfigured`, `receive_configured`, `receive_pending`, `receive_verified`, and `receive_operational` are derived from routing, capture visibility, and operator confirmation.
- uninitiated mailbox files such as `aws-csm.tff.mark.json` or
  `aws-csm.cvcc.marilyn.json` may keep `smtp.username` blank and
  `smtp.credentials_secret_state=missing`; they are still mailbox records, not
  domain summary records
- active technical-contact mailbox files such as
  `aws-csm.tff.technicalContact.json` and
  `aws-csm.cvcc.technicalContact.json` should show resolved SMTP username state
  and `handoff_status=ready_for_gmail_handoff` while still reporting
  `verification.status=not_started` and `inbound.receive_state=receive_pending`
- `inbound.portal_native_display_ready = true` means the portal has enough captured-message metadata to show the latest inbound event directly, without relying on the forwarded Gmail copy as the primary operator view.
- `inbound.legacy_dependency_state` and `inbound.legacy_replay_available` explicitly show when the active legacy `ses-forwarder` Lambda path is still required for compatibility actions such as replay.
- On April 2, 2026, the active Gmail verification path for FND was confirmed to use the legacy SES receipt rule + S3 + Lambda forwarder chain. The portal now surfaces the latest captured verification message metadata and replay action so operators no longer have to rely on mailbox hunting alone.
- Replay remains a compatibility action in the current model. Portal-native metadata and link display should replace mailbox hunting first; only after replay no longer depends on the legacy Lambda chain should `ses-forwarder-role-l0ypgdpr` be considered removable.
- On March 31, 2026, repo inspection found no local Gmail API/OAuth automation path or Google client dependency for completing Gmail send-as confirmation from the server; that step remains a human handoff unless automation is added later.
- The inline IAM policy `AWSCMSManageSmtpCredentials` is now conceptually obsolete for the active SES SMTP model. The shared `aws-cms-smtp` user may still exist as transitional operational behavior, but future mailbox workflows should move toward mailbox-specific IAM users under `/aws-cms/smtp/` and must not depend on `CreateServiceSpecificCredential` or related APIs.
- future per-mailbox or per-domain SMTP credentials may move to mailbox-specific
  IAM users and KeyPass-managed secrets keyed by `identity.profile_id`, but that
  is architectural guidance only in the current phase.

Current reference onboarding case:

- `aws-csm.fnd.dylan.json` with canonical sender `dylan@fruitfulnetworkdevelopment.com`
- legacy FND inbound automation and `dcmontgomery.*` mail artifacts remain classified as active legacy infrastructure, not baseline onboarding truth

Active AWS-CMS scope does not include:

- newsletter workflows
- emailer preview or queue-sync flows
- member-facing or tenant-facing self-service onboarding

## Ownership Boundary

- **Core owns:** path derivation helpers, internal-root safety, file-kind detection, read-only parsing/normalization.
- **Tool owns:** interpretation/projection of the normalized payload into mediated cards and views.
- **Shell owns:** directive and attention state; tools must not own canonical shell state.

## Read-Only Scope

This contract is read-only in current form. No mutate/apply path is introduced for internal analytics files.

## Update Triggers

- Changes to internal file-kind support
- Changes to allowed-root policy for internal reads
- Changes to profile-to-analytics derivation rules
- Any proposal to move internal file reads out of shared core
