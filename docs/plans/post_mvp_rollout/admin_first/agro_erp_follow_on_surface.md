# AGRO-ERP Follow-On Surface

Authority: [../../v2-authority_stack.md](../../v2-authority_stack.md)

This file defines what must be true before AGRO-ERP work begins after CTS-GIS.

## Sequence rule

AGRO-ERP follows CTS-GIS.

It does not displace AWS.
It does not start in parallel with the first CTS-GIS reopening.

## Why AGRO-ERP waits

AGRO-ERP carries more structural breadth than AWS and CTS-GIS:

- tool-bearing mediation
- HOPS and time-address dependence
- config-binding semantics
- likely future sandbox and staging pressure

That makes it a poor first operational replacement target.

## What must be true before AGRO-ERP starts

- the admin shell, runtime envelope, and registry/launcher are stable
- the AWS-first path is proven
- the post-AWS tool platform is stable
- the first CTS-GIS slice is proven or at least implemented internally
- AGRO-ERP has its own slice file and gate record
- any HOPS or time-projection seams needed for AGRO are explicitly approved
- utility-anchor drift is not reintroduced as a shortcut

## First AGRO-ERP planning posture

The first AGRO-ERP slice should be admin-first and narrow.

It should start with:

- read-only operational visibility
- config-binding clarity
- explicit role-binding diagnostics

It should not start with:

- broad ERP editing
- sandbox sessions
- publish/workbench revival
- multi-surface launcher sprawl
