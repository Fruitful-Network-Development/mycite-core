# Runtime Entrypoints

`runtime/` is the canonical home for stable process entrypoints and validation
helpers. Legacy entrypoints under `portals/runtime/` remain as compatibility
wrappers while the live native services continue to import through the old
paths.

Rules:

- keep process startup and loader logic here;
- keep portal behavior out of this directory;
- route flavor/application composition through `portal_core/`;
- treat `portals/runtime/*` as transitional wrappers only.

