# NETWORK Page Model

## Goal

NETWORK is a page-specific workbench consumer with Discord-like interaction structure:

- global activity bar remains shell-global
- left context sidebar stays stable across the page and groups view tabs plus interface/channel selections
- center workbench changes with selected alias/log/P2P or hosted/profile tabs
- right inspector holds profile/context detail

## Context Sidebar Groups

Provided via page-local sidebar sections:

- network view tabs: `messages`, `hosted`, `profile`
- aliases / organization interfaces
- request-log channels
- P2P channels

Network template adds local filter input for these lists.

## Workbench Modes

Template:

- `portals/mycite-le_fnd/portal/ui/templates/services/network.html`
- mirrored in TFF

Canonical route model:

- `/portal/network?tab=messages&kind=alias|log|p2p&id=...`
- `/portal/network?tab=hosted`
- `/portal/network?tab=profile`

Messages workbench mode changes by `kind`:

- `alias`: organization interface workspace
- `log`: request history workspace backed by `private/network/request_log/request_log.ndjson`
- `p2p`: direct conversation workspace derived from request-log transmitter/receiver pairs

Hosted renders from `private/network/hosted.json` with canonical `type` and `type_values`.

Profile renders a three-pane workbench for:

- `private/config.json`
- `public/msn-<msn_id>.json`
- `public/fnd-<msn_id>.json`

## Inspector Usage

Right inspector templates on NETWORK:

- portal contact card/profile
- selected interface/channel detail
- configuration/geography detail

## Aliases / Request Logs / P2P Semantics

- aliases: organization-scoped interface entries
- request logs: request/history channel entries
- P2P: direct-message-like conversation channels

Legacy `view=alias|log|p2p` links remain redirect-compatible during rollout.
