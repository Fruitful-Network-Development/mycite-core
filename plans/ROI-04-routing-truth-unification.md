# ROI 04 — Routing Truth Unification

## Objective

Remove drift between `srv-infra`, actual host nginx config, and the portal service routing assumptions used by `mycite-core`.

## Why this is high ROI

Current portal work still shows the classic split:

- `mycite-core` may be ahead
- `srv-infra` may lag
- live nginx may differ from both

That is a direct source of wasted effort. It causes repeated uncertainty over whether the issue is code, config, deploy, or host drift.

## Scope

Primary files and systems:

- `srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`
- live nginx config on host
- systemd unit or service config for portal host
- any deploy mechanism that copies repo config to host

## Deliverables

1. A declared source of truth for portal routing.
2. Updated `srv-infra` config aligned with the intended live path.
3. A verification step that compares repo config to live config.
4. A small deployment note stating how config reaches the host.

## Definition of done

This ROI area is complete when:

- the intended V2 routing is explicit in repo config
- the live nginx config matches repo intent
- any exceptions are documented
- config drift can be detected quickly

## Suggested implementation shape

Document one of these explicitly:

- `srv-infra` is the routing source of truth and host config is copied from it
- or host config is managed elsewhere and `srv-infra` is reference-only

If `srv-infra` is the source of truth, add a small verification note or script that checks:

- repo config block
- host config block
- running nginx syntax and reload status

## Task classification

`repo_and_deploy`

## Agent execution plan

### Lead

- frame the task as routing-truth unification, not just “fix nginx”
- require repo and host inspection as separate acceptance items

### Implementer

- update `srv-infra` config if needed
- inspect live host config
- align the host with repo intent
- reload nginx and capture outputs

### Verifier

- compare `srv-infra` repo state with actual host config
- confirm live HTTP behavior matches the intended route path
- fail if repo and host still diverge without explicit documentation

## Required evidence pattern

- repo nginx snippet
- host nginx snippet
- reload command output
- live HTTP output proving routing is correct
