# ROI 03 — Evidence Artifacts and Verification Reports

## Objective

Make implementation evidence and live verification evidence first-class repo artifacts for all repo+deploy tasks.

## Why this is high ROI

The Prompt 1 / Prompt 2 pattern worked because it separated implementation from verification. Without persistent artifacts, that discipline is easy to lose and the same arguments repeat later.

This area yields high return because it creates durable proof instead of relying on memory or chat summaries.

## Scope

Primary directories and workflow surfaces:

- `tasks/`
- `reports/`
- `agent/lead.md`
- `agent/implementer.md`
- `agent/verifier.md`

## Deliverables

1. A standard implementation report template.
2. A standard verification report template.
3. A task convention requiring both reports for `repo_and_deploy` tasks.
4. A rule that command output must be quoted or attached, not paraphrased.

## Definition of done

This ROI area is complete when:

- every `repo_and_deploy` task has an implementation report path
- every `repo_and_deploy` task has a verification report path
- the lead refuses closure without both when live acceptance exists
- report structure is stable and reusable

## Suggested implementation shape

Create templates such as:

- `reports/_template_implementation.md`
- `reports/_template_verification.md`

Implementation report sections:

1. Repo findings
2. Changes made
3. Tests run
4. Deploy actions taken
5. Risks or unresolved items

Verification report sections:

1. Live evidence
2. Host evidence
3. Mismatches, if any
4. Final verdict

## Task classification

`repo_and_deploy` or `deploy_only`

## Agent execution plan

### Lead

- require report paths in the task YAML before work starts
- mark `verification_pending` after implementation
- close only after verifier report is present

### Implementer

- write only the implementation report
- include exact commands and outputs that support implementation claims
- explicitly mark what still requires verification

### Verifier

- write only the verification report
- run independent checks
- return `verified fixed` or `not verified fixed`

## Required evidence pattern

- task file references both reports
- implementation report exists
- verification report exists
- closure matches verifier verdict
