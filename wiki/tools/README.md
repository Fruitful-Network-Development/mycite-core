# Tools

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md)

## Status

Canonical topic

## Current Contract

Tools are capability providers inside the unified `SYSTEM` shell. They may contribute mediated views and workflows, but they do not define alternate shells or replace the workbench state machine.

Tools may be exposed as first-class activity-bar entries when configured by the portal instance. These entries still normalize into the canonical `SYSTEM` runtime and open mediation through `?mediate_tool=<tool_id>`.

## Pages

- [Provider Model](provider-model.md)
- [AGRO-ERP Mediation](agro-erp-mediation.md)
- [AGRO-ERP Datum Decision Ledger](agro-erp-datum-decision-ledger.md)
- [Member Service Integrations](member-service-integrations.md)
- [Internal File Sources](internal-file-sources.md)
- [Tool Layer Mediation](tool-layer-mediation.md)

## Source Docs

- `docs/development_declaration_state_machine.md`
- `docs/AGRO_ERP_TOOL.md`
- `docs/AGRO_ERP_INTENTION.md`
- `docs/AWS_EMAILER_ABSTRACTION.md`
- `docs/PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md`

## Update Triggers

- Changes to provider activation or lifecycle rules
- Changes to how tools integrate with `SYSTEM`
- Changes to AGRO-ERP scope or ownership boundaries
