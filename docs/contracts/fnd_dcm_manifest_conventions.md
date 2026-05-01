# FND-DCM Manifest And Collection Conventions

`FND-DCM` normalizes hosted-site manifests into one shared read model without forcing all hosted frontends into one renderer.

The normalized top-level buckets are fixed:

- `site`
- `navigation`
- `footer`
- `pages`
- `collections`
- `issues`
- `extensions`

Schema mapping:

- `webdz.site_content.v2` maps shell metadata, navigation, footer, page definitions, and collections into the shared buckets
- `webdz.site_content.v3` maps site shell metadata, icon sets, footer columns, page definitions, and collections into the shared buckets
- machine-surface metadata (when present under `machine` or legacy `machine_surfaces`) is surfaced additively in `extensions.machine_surface_summary`
- schema-specific behavior that should not constrain future frontend work remains in `extensions`

Collection conventions:

- `json_file` resolves one source file beneath the frontend root
- `markdown_directory` resolves a directory plus glob pattern beneath the frontend root
- `markdown_documents` resolves explicit source files beneath the frontend root
- collection file metadata is surfaced as supporting evidence in the workbench

CVCC board-profile canonical item shape:

- `id`
- `name`
- `image`
- `summary_bio`
- `bio`
- `email`
- `secondary_email`
- `phone`
- `why_joined_the_board`
- `year_joined_board`
- `socials`
- `tags`

Board-profile normalization rules:

- `alternative_email` becomes `secondary_email`
- `contact_phone_number` becomes `phone`
- `why_joined_board` becomes `why_joined_the_board`
- `~` and empty strings are treated as missing
- `socials` normalizes to `[{ "platform": <canonical_platform>, "value": <string> }]`
- `summary_bio` is preferred for the profile card summary
- when `summary_bio` is absent, the renderer may fall back to `bio[0]`

Renderer boundary:

- `FND-DCM` owns read-model normalization
- client frontend renderers remain client-specific in v1
- renderer centralization is intentionally deferred
