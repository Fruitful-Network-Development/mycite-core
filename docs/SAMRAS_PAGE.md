# SAMRAS Data Sub-Tab (FND First)

## Purpose

Define the active SAMRAS page contract under the Data service.
SAMRAS stands for **Shape-Addressed Mixed-Radix Address Space**.

This milestone implements FND-first, JSON-only SAMRAS instances with a two-column table editor and hierarchy view.

## Route and Placement

- `GET /portal/data/samras`
- SAMRAS is a Data sub-tab, not a top-level service route in this milestone.

## Instance Discovery

SAMRAS instances are auto-discovered from runtime data files:

- `data/<msn_id>.<instance_id>.json`

Examples:

- `data/3-2-3-17-77-1-6-4-1-4.1-1-4.json`
- `data/3-2-3-17-77-1-6-4-1-4.1-1-5.json`

Each discovered `instance_id` is rendered as an inner SAMRAS tab.

## Row Contract

Canonical row fields:

- `address_id` (required, numeric-hyphen radix path)
- `title` (required)

Persistence form in each instance file:

```json
{
  "3-2-3-17": ["ohio"],
  "3-2-3-17-18": ["cuyahoga_county"]
}
```

## Hierarchy Contract

Hierarchy is inferred by radix-prefix segmentation:

- parent of `a-b-c` is `a-b`
- roots are single-segment IDs
- missing parent rows are allowed and surfaced as warnings

Graph UI behavior:

- horizontal column layout by depth
- default collapse depth = 2
- clicking a node toggles branch expansion
- filter by `address_id` or `title` focuses rows and graph

## Anthology Linkage for New SAMRAS Tables

Creating a new SAMRAS table also writes anthology linkage:

- reserve/ensure anchor datum: `1-0-1` (`samras_tables`)
- create link datum row under `1-1-*`
- directive reference format:
  - `inv;(med;<msn_id>-1-0-1;samras_table);<row_number>`

Link datum label metadata schema:

```json
{
  "schema": "mycite.samras.link.v1",
  "instance_id": "<instance_id>",
  "table_name": "<table_name>"
}
```

## API Endpoints

- `GET /portal/api/data/samras/instances`
- `GET /portal/api/data/samras/table/<instance_id>?filter=<token>&expanded=<id,id,...>`
- `POST /portal/api/data/samras/table/create`
- `POST /portal/api/data/samras/row/upsert`
- `POST /portal/api/data/samras/row/delete`
- `GET /portal/api/data/samras/graph/<instance_id>?filter=<token>&expanded=<id,id,...>`

## Validation Rules

- `instance_id` must match numeric-hyphen format
- `address_id` must match numeric-hyphen format
- `title` is required for row upsert
- upsert is idempotent on `address_id`

## Storage and Security Posture

- JSON-only persistence
- no DB, no migration backend added
- no secret material stored in SAMRAS instance files
