# CTS-GIS Follow-On Surface

Authority: [../../v2-authority_stack.md](../../v2-authority_stack.md)

This file defines what must be true before CTS-GIS work begins after AWS.

## Sequence rule

CTS-GIS follows AWS.

CTS-GIS is not the first tool-bearing target.

## Why CTS-GIS waits

CTS-GIS depends on broader shell mediation and structure-specific projection work.

Those are not needed to restore a usable admin portal as quickly and safely as AWS.

## What must be true before CTS-GIS starts

- `Admin Band 0` is stable
- the AWS read-only slice is stable
- the AWS narrow-write slice is stable
- the post-AWS tool platform is stable
- the tool registry/launcher model is proven
- a dedicated CTS-GIS slice file exists
- any reopened mediation-surface work is explicitly approved
- the shell still owns navigation legality and tool discoverability

## First CTS-GIS planning posture

The first CTS-GIS slice should be admin-first and read-only.

It should focus on:

- a narrow SAMRAS-oriented mediation surface
- shell-attached visualization only
- no broad public mapping portal
- no write workflow

## Explicitly out of scope while CTS-GIS is still follow-on

- AGRO-ERP composition
- public map rollout
- multi-tool launcher expansion by convenience
- sandboxes or workbench resurrection
