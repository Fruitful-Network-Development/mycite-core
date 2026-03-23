# Mycite Portal Wiki

This wiki is the primary maintained knowledge base for the Mycite Portal application in `repo/mycite-core`.

It explains the current portal model in concept-first pages so future refactors can update one local topic instead of auditing a large set of mixed milestone docs.

## What This Wiki Owns

- Current application concepts and contracts for the portal runtime.
- Stable explanations of the `SYSTEM` workbench, data model, MSS, SAMRAS, sandbox, hosted model, and build/runtime boundaries.
- The maintenance workflow for updating documentation after code or architecture changes.

## Former `docs/` Tree

The former `docs/` tree has been retired. Its current, valid content has been consolidated into this wiki, and its superseded material has been reduced to lineage notes in `archive/`.

## Source-Of-Truth Precedence

When pages in this wiki synthesize older source material, use this precedence:

1. March 23, 2026 declarations and refactor reports.
2. The former canonical contract set that was indexed before the wiki migration.
3. Supporting docs that extend current behavior without redefining it.
4. Historical and background docs for lineage only.

When sources disagree, prefer the newer model:

- one unified `SYSTEM` workbench
- tools as providers inside `SYSTEM`
- routing and HTTP as adapter concerns
- sandbox as a lifecycle engine, not the inventory owner
- SAMRAS structural logic from the migrated shape-addressed mixed-radix source specification
- `spacial` as compatibility vocabulary, not the canonical state concept

## Wiki Structure

- `Home.md` is the landing page and navigation map.
- `Glossary.md` defines stable shared terms.
- Each topic directory uses `README.md` as the parent topic page.
- Leaf pages hold isolated concepts that should change locally when behavior changes.

## Leaf Page Contract

Every leaf page should keep these sections in order:

1. `Status`
2. `Parent Topic`
3. `Current Contract`
4. `Directional Intent` only when the source explicitly defines a target state
5. `Boundaries`
6. `Authoritative Paths / Files`
7. `Source Docs`
8. `Update Triggers`

## Linking Rules

- Leaf pages may link only to `Home.md`, `Glossary.md`, their own parent `README.md`, and root topic pages.
- Parent topic pages own child-page navigation.
- Avoid sibling-to-sibling deep-link meshes.
- Refer to source implementation files as plain paths unless a direct wiki navigation link is needed.

## Wiki Maintenance Workflow

When the portal changes:

1. Identify the single owning concept page for the change.
2. Update that leaf page first.
3. Update the parent topic `README.md` only if the scope, child list, or ownership summary changed.
4. Update `Home.md` only if navigation changed.
5. Add a short lineage note or archive entry instead of editing unrelated concept pages.

## Refactor Guidance

Use the wiki to preserve stable explanations, not transient implementation narration.

- Prefer concept pages over report-style pages.
- Split frozen logic into its own file when it can change independently of surrounding UI or architecture.
- Keep current-state pages in present tense.
- Move milestone wording, deprecated interaction models, and superseded framing into `archive/`.

## Coverage Expectation

Every major current contract area should map to either:

- one owning wiki leaf page, or
- one parent topic page when the concept is too small to justify a separate leaf.

Start at [Home](Home.md).
