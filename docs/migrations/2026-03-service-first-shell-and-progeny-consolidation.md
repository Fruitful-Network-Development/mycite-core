# 2026-03 Service-First Shell and Progeny Consolidation

## Summary

This migration replaced tool-first home navigation with service-first routes across runnable portals and consolidated legacy standalone NE profile folders into CVCC internal progeny cards.

## Service shell changes

- Added canonical routes:
  - `/portal/home`
  - `/portal/data`
  - `/portal/network/contracts`
  - `/portal/network/magnetlinks`
  - `/portal/network/progeny`
  - `/portal/network/alias`
  - `/portal/tools`
  - `/portal/inbox`
- `/portal` now redirects to `/portal/home`.
- Shared core service runtime added under `portals/_shared/portal/core_services/`.

## Tool runtime compatibility

- `data_tool` in `enabled_tools` is treated as a legacy token and ignored in Tools menu registration.
- Data service is now first-class at `/portal/data`.

## Progeny migration

### Removed directories

- `portals/mycite-ne_dg`
- `portals/mycite-ne_eb`
- `portals/mycite-ne_jt`
- `portals/mycite-ne_ks`

### Added files

- `portals/mycite-le_cvcc/private/progeny/internal/board-member-dg.json`
- `portals/mycite-le_cvcc/private/progeny/internal/board-member-eb.json`
- `portals/mycite-le_cvcc/private/progeny/internal/board-member-jt.json`
- `portals/mycite-le_cvcc/private/progeny/internal/board-member-ks.json`

### Updated files

- `portals/mycite-le_cvcc/private/mycite-config-3-2-3-17-77-2-6-1-1-2.json`
  - fixed JSON validity
  - appended internal progeny references

## Validation checklist

- route compile and startup checks pass for all runnable portal apps
- service pages render without query-param tab dependency
- alias session and embed routes remain intact
- legacy NE directories are absent
