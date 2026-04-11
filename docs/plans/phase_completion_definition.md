# Phase Completion Definition

Authority: [authority_stack.md](authority_stack.md)

A phase is complete only when all of the following are true:

1. The phase outputs named in its phase doc exist.
2. The phase required tests pass at the correct boundary.
3. No prohibited shortcut named in the phase doc remains.
4. The phase does not rely on later-layer code to make its outputs meaningful.
5. The touched docs still align with [../testing/phase_gates.md](../testing/phase_gates.md).

This file defines the general rule. Per-phase specifics live in `docs/plans/phases/*.md`.
