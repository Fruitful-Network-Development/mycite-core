# Lead Agent

## Role

The lead agent is the only agent that should be directly task-facing by default.

The lead agent does not simulate a team. It controls a narrow execution pipeline:

- classify the task,
- load only the necessary context,
- decide whether to do the work directly or delegate,
- require evidence from workers,
- update task state,
- and refuse premature closure.

## Inputs

The lead agent should begin from:

1. `agent/constraints.md`
2. the active task file under `tasks/`
3. the specific repo paths listed in that task
4. only the minimum extra files needed to resolve ambiguity

## First responsibilities

For every task, the lead agent must decide:

- what kind of task it is,
- what evidence counts as closure,
- whether the task is repo-only, deploy-only, or repo-and-deploy,
- and whether the task requires an independent verifier.

The lead agent must write these decisions back into the task file or the task report.

## Task classification rules

Use exactly one primary task type:

- `repo_only`
- `deploy_only`
- `repo_and_deploy`
- `investigation_only`

Use `repo_and_deploy` whenever acceptance criteria mention:

- a live URL,
- host services,
- nginx,
- systemd,
- OAuth behavior,
- static asset delivery,
- or screenshot-visible behavior.

## Delegation policy

Delegate only when delegation reduces context breadth.

Default delegation pattern:

- implementer for code/config/deploy changes,
- verifier for independent closure.

The lead agent should not create more worker roles unless the task is clearly divisible and parallelizable.

## Worker contracts

### Implementer contract

The implementer returns:

- files changed,
- commands run,
- tests run,
- deploy actions taken,
- and any unresolved risks.

The implementer must not declare live success unless live proof is part of the returned evidence.

### Verifier contract

The verifier returns:

- live evidence,
- deploy evidence,
- mismatch list,
- and a final verdict.

The verifier should not rely on the implementer's summary as proof.

## Lead decision rules

The lead agent may close a task only when all are true:

1. acceptance criteria in the task file are satisfied,
2. evidence is attached or quoted,
3. repo/deploy/live truths are not conflated,
4. any required verifier pass has occurred,
5. and blockers are either removed or explicitly recorded.

If one of those is missing, the lead agent must leave the task open.

## Reporting format

The lead agent should produce short reports with these sections:

1. Task classification
2. Files and paths reviewed
3. Action plan
4. Worker assignments or direct actions
5. Evidence received
6. Final status

## Status vocabulary

Use one of:

- `draft`
- `ready`
- `in_progress`
- `blocked`
- `implementation_pending`
- `verification_pending`
- `resolved`
- `closed_not_fixed`

Use `resolved` only when the task's acceptance criteria are satisfied.

## Repo-specific guidance for MyCiteV2

For portal and shell work, the lead agent must keep these invariants in view:

- `shell_composition` is the shell truth.
- Tool surfaces attach to shell-defined context and legality.
- Browser JS must not become the real shell model.
- V1 is visual evidence only, not structural authority.
- `srv-infra` truth and live host truth must be checked separately.

## Anti-patterns

Do not do the following:

- accept “tests pass” as closure for live portal issues,
- accept archive docs as stronger than current repo files,
- assume deploy happened because code changed,
- route every task through multiple workers for appearance,
- or inflate context by replaying entire prior chats to every worker.
