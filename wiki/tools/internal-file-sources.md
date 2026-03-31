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

- `identity` (profile/operator identity for a single send-as setup)
- `smtp` (Gmail send-as handoff fields, forwarding destination/status, SMTP readiness, secret-reference metadata without raw credentials)
- `verification` (code/link/status/timestamps for the active send-as verification step)
- `provider` (provider-facing SES and Gmail send-as status snapshots)
- `workflow` (operator-only readiness, pre-handoff blockers, Gmail-side blockers, and completion-boundary summary)

Legacy flat fields (for example `alias_email`, `forward_to_email`, `gmail_send_as_status`) are normalized into these groups at service-tool context assembly. This is a compatibility transform only; canonical writes target grouped profile documents under `aws-csm.<profile>.json`.

Current scope is intentionally narrow:

- one operator
- one profile at a time
- simple SES SMTP and Gmail send-as onboarding
- optional inbound-verification automation only as a future extension seam

Read-only operational inspection is available from the server through:

- `python3 /srv/repo/mycite-core/scripts/aws_csm_inspect.py --tenant <tenant>`

The inspector reads the canonical staged profile, inspects matching SES, Route 53, Secrets Manager, and inbound-mail resources through the AWS CLI, and emits a non-destructive classification report. It is intended for safe inventory and cleanup planning, not live mutation.

Current readiness boundary is explicit:

- `smtp.credentials_secret_name` and `smtp.credentials_secret_state` may describe a placeholder secret reference without implying that real SMTP credentials are resolved.
- `workflow.configuration_blockers_now` is the list that must clear before Gmail/inbox handoff is trustworthy.
- `workflow.gmail_handoff_blockers_now` is the intentional remaining boundary after AWS-side staging is complete.
- `workflow.is_ready_for_user_handoff = true` means ready for Gmail/inbox handoff, not that send-as is fully verified.
- `workflow.handoff_status` and `workflow.completion_boundary` distinguish staging, Gmail-handoff readiness, and confirmed completion.

Current reference onboarding case:

- `aws-csm.fnd.json` with canonical sender `dylan@fruitfulnetworkdevelopment.com`
- legacy FND inbound automation and `dcmontgomery.*` mail artifacts remain classified as out-of-scope legacy infrastructure, not baseline onboarding truth

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
