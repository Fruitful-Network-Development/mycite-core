# CTS-GIS HOPS-First Stage-A Audit

Data root: `/srv/repo/mycite-core/deployed/fnd/data`

## Totals

- Projection documents audited: 32
- Stage-A safe to strip: 29
- Stage-A stripped this run: 29
- Deterministic fixes applied: 2

## Stage-A Safe Documents

- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-11.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-12.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-13.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-3.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-4.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-5.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-6.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-7.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-8.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-9.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-1.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-2.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-3.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-4.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-5.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-6.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-7.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-8.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-9.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-1.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-2.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-3.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-4.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-5.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-6.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-7.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-8.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-9.json`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77.json`

## Needs Repair / Blocked

- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-1.json`
  - contract: 5-0-1 has duplicate references
  - projection_without_reference: projectable/hops/features=1
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-10.json`
  - contract: 4-21-1 declares 21 HOPS tokens but carries 20
  - projection_without_reference: projectable_degraded/hops/features=1
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-2.json`
  - contract: 5-0-1 references missing row (4-1505-2)
  - projection_without_reference: projectable/hops/features=1

## Before/After Projection Snapshots

| Document | With Reference | Without Reference |
| --- | --- | --- |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-1.json` | `projectable_degraded/hops/f1/w1` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-10.json` | `projectable_degraded/hops/f1/w3` | `projectable_degraded/hops/f1/w1` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-11.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-12.json` | `projectable_degraded/hops/f1/w3` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-13.json` | `projectable_degraded/hops/f1/w2` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-2.json` | `projectable_degraded/hops/f1/w1` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-3.json` | `projectable_degraded/hops/f1/w5` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-4.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-5.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-6.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-7.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-8.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-9.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-1.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-2.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-3.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-4.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-5.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-6.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-7.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-8.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-9.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-1.json` | `projectable_degraded/hops/f1/w2` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-2.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-3.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-4.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-5.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-6.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-7.json` | `projectable_degraded/hops/f1/w2` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-8.json` | `projectable_degraded/hops/f1/w2` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-9.json` | `projectable_degraded/hops/f1/w2` | `projectable/hops/f1/w0` |
| `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77.json` | `projectable/hops/f1/w0` | `projectable/hops/f1/w0` |

