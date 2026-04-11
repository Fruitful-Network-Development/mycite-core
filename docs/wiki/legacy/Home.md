# Mycite Portal Wiki Home

Use this page as the starting point for the current Mycite Portal application model.

## Root References

- [Wiki README](README.md)
- [Glossary](Glossary.md)

## Table Of Contents

- [Architecture](architecture/README.md)
  - [System State Machine](architecture/system-state-machine.md)
  - [Shell And Page Composition](architecture/shell-and-page-composition.md)
  - [Application Core And Adapters](architecture/application-core-and-adapters.md)
  - [AITAS Context](architecture/aitas-context.md)
- [Data Model](data-model/README.md)
  - [Canonical Data Artifacts](data-model/canonical-data-artifacts.md)
  - [Datum Identity And Resolution](data-model/datum-identity-and-resolution.md)
  - [Write Pipeline](data-model/write-pipeline.md)
  - [Mediation Defaults](data-model/mediation-defaults.md)
  - [Datum Rule Policy](data-model/datum-rule-policy.md)
  - [External Resource Isolates](data-model/external-resource-isolates.md)
  - [Time Series Abstraction](data-model/time-series-abstraction.md)
  - [Derived Views](data-model/derived-views.md)
- [Contracts And MSS](contracts-mss/README.md)
  - [MSS Compact Array](contracts-mss/mss-compact-array.md)
  - [Contract Context Model](contracts-mss/contract-context-model.md)
  - [Compiled Datum Index](contracts-mss/compiled-datum-index.md)
  - [Contract Update Protocol](contracts-mss/contract-update-protocol.md)
- [Sandbox And Resources](sandbox-resources/README.md)
  - [Sandbox Lifecycle](sandbox-resources/sandbox-lifecycle.md)
  - [Resource Storage And Ownership](sandbox-resources/resource-storage-and-ownership.md)
  - [Inherited Resource Context](sandbox-resources/inherited-resource-context.md)
- [SAMRAS](samras/README.md)
  - [Structural Model](samras/structural-model.md)
  - [Validity And Mutation](samras/validity-and-mutation.md)
  - [Engine UI Boundary](samras/engine-ui-boundary.md)
- [Tools](tools/README.md)
  - [Provider Model](tools/provider-model.md)
  - [AGRO-ERP Mediation](tools/agro-erp-mediation.md)
  - [Member Service Integrations](tools/member-service-integrations.md)
- [Runtime And Build](runtime-build/README.md)
  - [Shared Core And Flavor Boundaries](runtime-build/shared-core-and-flavor-boundaries.md)
  - [Build And Materialization](runtime-build/build-and-materialization.md)
  - [Portal Config Model](runtime-build/portal-config-model.md)
- [Network And Hosted](network-hosted/README.md)
  - [Network Page Model](network-hosted/network-page-model.md)
  - [Hosted Sessions And Alias Shell](network-hosted/hosted-sessions-and-alias-shell.md)
  - [Progeny And Profile Models](network-hosted/progeny-and-profile-models.md)
  - [Request Log And Audit](network-hosted/request-log-and-audit.md)
- [Governance](governance/README.md)
  - [Documentation Governance](governance/documentation-governance.md)
  - [Repository Boundaries](governance/repository-boundaries.md)
- [Archive](archive/README.md)
  - [Historical Lineage](archive/historical-lineage.md)

## Key Frozen Logic Pages

- [System State Machine](architecture/system-state-machine.md)
- [Datum Identity And Resolution](data-model/datum-identity-and-resolution.md)
- [MSS Compact Array](contracts-mss/mss-compact-array.md)
- [SAMRAS Structural Model](samras/structural-model.md)

## Reading Paths

- To understand the current product model, start with `Architecture`, then `Data Model`, then `Contracts And MSS`.
- To understand frozen structural logic, read `Datum Identity And Resolution`, `MSS Compact Array`, and `SAMRAS Structural Model`.
- To understand integration boundaries, read `Sandbox And Resources`, `Runtime And Build`, and `Network And Hosted`.
