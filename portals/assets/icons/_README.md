# Icon Library Conventions

- Store SVG-only assets in this tree.
- Keep filenames lowercase; use `-` or `_` separators.
- Paths are referenced by portals as relative paths under `assets/icons`.
- Do not include scripts or external references inside SVG files.
- Current default is **ambiguous/flat filename mode** (for rapid prototyping).
  - Example: `msn_index.svg`
  - Folder taxonomy is optional and can be reintroduced later.
- Reserved subdirectory: `ui/` for service-shell symbols and control/info markers.
- If foldered paths are used later, preserve unique filenames where possible.

Folder categories are intentionally deferred while prototyping.
If/when reintroduced, keep naming globally unique so basename mode remains workable.
