# Glossary

## SYSTEM

The canonical portal workbench at `/portal/system`. It is one stateful operator surface, not a collection of separate sub-applications or visible split tabs.

## NIMM

The persistent directive set used by the workbench: `Navigate`, `Investigate`, `Mediate`, and `Manipulate`.

## AITAS

The shared context frame used by the workbench: `Attention`, `Intention`, `Time`, `Archetype`, and compatibility `Spacial`.

## Attention

The canonical subject of the machine. It resolves to a file, datum, or facet rather than a vague page mode.

## Directive

The current interaction posture of the workbench. In current portal language this is the NIMM directive.

## Facet

A mediated aspect of a datum, such as abstraction path, archetype, sequence, time, or relation.

## Anthology

The canonical local datum authority stored in `data/anthology.json`, with a repo-owned base registry merged at runtime.

## MSS

The compact-array form used to carry scoped anthology context between portals without moving a full anthology.

## Contract Context

The NETWORK contract payload that carries `owner_selected_refs`, `owner_mss`, and `counterparty_mss` so foreign datum references can resolve through compact-array context.

## SAMRAS

Shape-Addressed Mixed-Radix Address Space. A structural value model where addresses are derived from breadth-first child counts and the canonical write path is decode, derive, mutate, and re-encode.

## Sandbox

The shared lifecycle engine for resource staging, compile, decode, adapt, save, and publish flows. It is not the canonical inventory owner.

## Provider

A tool or mediation capability that operates inside the unified `SYSTEM` shell. A provider may contribute mediated views, but it does not own shell state or define a parallel application.

## Hosted

The runtime model for alias and subject-congregation style hosted interfaces derived from build-seeded and runtime-normalized hosted metadata.

## Progeny

A relationship-scoped hosted/profile model for member, poc, user, and related configurations and profile cards.

## Canonical Datum Path

The semantic datum identity used for resolution and comparison, typically normalized to dot-qualified form such as `<msn_id>.<datum>`.

## Storage Address

The layer/value-group/iteration address inside a specific anthology or MSS snapshot. It is not the durable semantic identity of a datum.

## Datum Address

The local anthology/resource row address format `<layer>-<value_group>-<iteration>`. Ordering is numeric by those three segments, never lexicographic string order.

## SAMRAS Structural Address

An address derived from SAMRAS node topology (breadth-first child-count structure). It is not interchangeable with datum addresses.

## MSS Snapshot Index

A compact-array transport-local row/index position inside an isolated closure. It is not interchangeable with anthology/resource datum addresses.
