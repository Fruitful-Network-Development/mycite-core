# Code Bloat Data I/O Caching Audit Plan

Date: 2026-04-24

Doc type: `audit-plan`
Normativity: `planning`
Lifecycle: `active`
Last reviewed: `2026-04-24`

## Registry

- Stream ID: `STREAM-CODE-BLOAT-DEEP-AUDIT`
- Compatibility initiative ID: `INIT-CODE-BLOAT-DEEP-AUDIT`
- Task ID: `TASK-CODE-BLOAT-AUDIT-004`
- Source report: `docs/audits/reports/code_bloat_diagnosis.md`
- Status: planning only; audit not executed.

## Audit Objective

Find synchronous I/O, large payload construction, repeated data loading, missing
cache boundaries, and background-job candidates that inflate startup or request
latency.

## Goes Further Than Diagnosis

The diagnosis notes synchronous JSON reads and limited caching. This plan
requires route-level timing, payload-size accounting, data freshness rules,
cache invalidation constraints, and failure-mode review before proposing any
cache, stream, or async boundary.

## Evidence Targets

- `MyCiteV2/instances/_shared/portal_host/app.py`
- `MyCiteV2/instances/_shared/runtime/`
- `MyCiteV2/packages/adapters/`
- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/tool_operating_contract.md`
- `docs/audits/reports/performance_weight_speed_report_2026-04-16.md`

## Audit Procedure

1. Inventory file, JSON, SQL, network, and AWS service reads on portal startup
   and high-traffic request paths.
2. Measure payload byte size and construction time for shell composition,
   tool surfaces, runtime reports, and static schema payloads.
3. Classify data by freshness: immutable static, release-scoped, session-scoped,
   request-scoped, or action-result scoped.
4. Identify safe cache candidates with invalidation owner, TTL rationale,
   confidentiality posture, and failure behavior.
5. Identify endpoints or actions whose slow work should become streamed,
   paginated, backgrounded, or explicitly left synchronous.
6. Define benchmark and regression evidence required before implementation.

## Acceptance Criteria

- Audit output maps I/O hot spots to route/action owners and measurable cost.
- Cache/async candidates include invalidation, security, and rollback posture.
- Findings report links to `TASK-CODE-BLOAT-AUDIT-004` and
  `STREAM-CODE-BLOAT-DEEP-AUDIT`.
