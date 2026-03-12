# NETWORK Page Model

## Goal

NETWORK is a page-specific workbench consumer with Discord-like interaction structure:

- global activity bar remains shell-global
- left context sidebar groups interface/channel selections
- center workbench changes with selected alias/log/P2P
- right inspector holds profile/context detail

## Context Sidebar Groups

Provided via page-local sidebar sections:

- aliases / organization interfaces
- request-log channels
- P2P channels

Network template adds local filter input for these lists.

## Workbench Modes

Template:

- `portals/mycite-le_fnd/portal/ui/templates/services/network.html`
- mirrored in TFF

Center workbench mode changes by `network_view`:

- `alias`: organization interface workspace
- `log`: request history workspace
- `p2p`: direct conversation workspace

## Inspector Usage

Right inspector templates on NETWORK:

- portal contact card/profile
- selected interface/channel detail
- configuration/geography detail

## Aliases / Request Logs / P2P Semantics

- aliases: organization-scoped interface entries
- request logs: request/history channel entries
- P2P: direct-message-like conversation channels

## Current Limitation

Network center workbench is still a structured prototype view (not full chat composer/thread engine). Selection-driven composition and inspector integration are implemented.
