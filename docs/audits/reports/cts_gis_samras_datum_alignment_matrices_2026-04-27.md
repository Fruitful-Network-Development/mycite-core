# CTS-GIS SAMRAS And Datum Alignment Matrices

Date: 2026-04-27

Doc type: `audit`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-27`

## Planning Registry

- Stream ID: `STREAM-CTS-GIS-OPEN`
- Compatibility initiative ID: `INIT-CTS-GIS-OPEN-ALIGNMENT`
- Supporting tasks:
  - `TASK-CTSGIS-SAMRAS-002`
  - `TASK-CTSGIS-DATUM-002`
- Umbrella closure tasks still gated by external acknowledgment:
  - `TASK-CTSGIS-SAMRAS-001`
  - `TASK-CTSGIS-DATUM-001`

## Purpose

Publish the traceable SAMRAS and datum drift matrices required by the contextual
planning system while keeping owner-signoff state explicit.

## SAMRAS Structural / Mutation / Mediation Matrix

| Drift category | Severity | Current disposition | Evidence anchors | Owner sign-off field |
| --- | --- | --- | --- | --- |
| Source-layout drift from monolithic-source assumptions | high | closed | `MyCiteV2/scripts/validate_cts_gis_sources.py`, `MyCiteV2/tests/unit/test_cts_gis_read_only.py`, `docs/audits/reports/cts_gis_runtime_readiness_report_2026-04-25.md` | `cts-gis-domain-owner: pending explicit acknowledgment` |
| `production_strict` artifact freshness drift | high | closed | `MyCiteV2/tests/unit/test_cts_gis_compiled_runtime.py`, `docs/contracts/cts_gis_compiled_artifact_contract.md`, `docs/contracts/cts_gis_operating_contract.md` | `cts-gis-contract-owner: pending explicit acknowledgment` |
| Diagnostic rebuild path leaking into production behavior | medium | closed with control | `portal_cts_gis_runtime.py`, `docs/audits/reports/cts_gis_deployed_portal_precinct_optimization_follow_on_2026-04-27.md`, `benchmarks/results/cts_gis_production_strict_probe_2026-04-27.json` | `cts-gis-runtime-owner: pending explicit acknowledgment` |
| Structural navigation / mediation parity | medium | closed | `MyCiteV2/tests/unit/test_cts_gis_read_only.py`, `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`, `docs/contracts/cts_gis_samras_addressing.md` | `cts-gis-domain-owner: pending explicit acknowledgment` |

## Datum Identity / Source-Precedence / Ordering / Projection Matrix

| Drift category | Severity | Current disposition | Evidence anchors | Owner sign-off field |
| --- | --- | --- | --- | --- |
| Datum identity and authoritative-source precedence | high | controlled and evidenced | `MyCiteV2/tests/unit/test_cts_gis_read_only.py`, `docs/audits/reports/cts_gis_sql_authority_assurance_report_2026-04-21.md`, `docs/contracts/cts_gis_hops_profile_sources.md` | `datum-domain-owner: pending explicit acknowledgment` |
| Ordering/editing mutation posture | medium | closed with deterministic guardrails | `MyCiteV2/tests/unit/test_portal_cts_gis_actions.py`, `MyCiteV2/tests/integration/test_nimm_mutation_contract_flow.py`, `docs/contracts/mutation_contract.md` | `datum-domain-owner: pending explicit acknowledgment` |
| Projection parity between compiled baseline and runtime selection state | medium | closed | `MyCiteV2/tests/unit/test_cts_gis_compiled_runtime.py`, `benchmarks/results/cts_gis_production_strict_probe_2026-04-27.json` | `cts-gis-contract-owner: pending explicit acknowledgment` |
| Precinct-context transport safety in `production_strict` | medium | closed | `docs/contracts/cts_gis_compiled_artifact_contract.md`, `docs/audits/reports/cts_gis_deployed_portal_precinct_optimization_follow_on_2026-04-27.md` | `cts-gis-runtime-owner: pending explicit acknowledgment` |

## Deterministic Validation Set

- `python3 -m unittest MyCiteV2.tests.unit.test_cts_gis_read_only`
- `python3 -m unittest MyCiteV2.tests.unit.test_cts_gis_compiled_runtime`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_workspace_runtime_behavior`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_cts_gis_actions`
- `python3 MyCiteV2/scripts/validate_cts_gis_sources.py --data-dir /srv/mycite-state/instances/fnd/data --scope-id fnd --require-compiled-match`

## Closure Interpretation

- `TASK-CTSGIS-SAMRAS-002`: matrix publication evidence satisfied
- `TASK-CTSGIS-DATUM-002`: matrix publication evidence satisfied
- `TASK-CTSGIS-SAMRAS-001`: remains blocked pending explicit owner
  acknowledgment fields moving from `pending` to approved
- `TASK-CTSGIS-DATUM-001`: remains blocked pending explicit owner
  acknowledgment fields moving from `pending` to approved

