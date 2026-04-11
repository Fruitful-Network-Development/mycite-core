# Tasks README

This file is the operational contract for all YAML task files in `tasks/`.

Its purpose is to let every task be driven with the same minimal user instruction:

> You are `<agent role>`, read `agent/constraints.md`, `agent/<role>.md`, `tasks/README.md`, then proceed with `tasks/<task-id>.yaml`.

If this README and the task YAML are written correctly, the user should not need to manually restate:
- what the task means,
- what files matter,
- what status updates are valid,
- what outputs each agent must write,
- or what counts as closure.

---

## 1. Core rule

A task file must be self-sufficient enough that an agent can begin from only:

1. `agent/constraints.md`
2. `agent/<role>.md`
3. `tasks/README.md`
4. `tasks/<task-id>.yaml`

and then load only the files referenced by that task.

Prompt history is not task state.

Chat summaries are not task state.

The repo is task state.

---

## 2. Directory purpose

- `tasks/` contains machine-readable task definitions.
- `reports/` contains implementation, verification, and handoff artifacts.
- `agent/` contains standing role behavior, not per-task instructions.

Task-specific instructions belong in the task YAML and in the handoff files it names.

---

## 3. Standard user instruction pattern

For every task, the user should only need to say one of the following.

### Lead
`You are lead, read agent/constraints.md, agent/lead.md, tasks/README.md, then proceed with tasks/<task-id>.yaml.`

### Implementer
`You are implementer, read agent/constraints.md, agent/implementer.md, tasks/README.md, then proceed with tasks/<task-id>.yaml.`

### Verifier
`You are verifier, read agent/constraints.md, agent/verifier.md, tasks/README.md, then proceed with tasks/<task-id>.yaml.`

Agents are expected to discover the correct next files from the task YAML itself.

The user should not need to paste handoff text between chats when the task file and report paths are correctly populated.

---

## 4. Agent roles

### Lead
The lead:
- classifies the task,
- confirms scope and evidence requirements,
- writes the lead handoff artifact,
- advances the task into implementation,
- and performs final closure only after verification evidence exists.

### Implementer
The implementer:
- performs code, config, docs, script, or deploy work allowed by the task,
- writes the implementation report,
- writes the implementer-to-verifier handoff,
- updates task execution state,
- and does not self-certify closure.

### Verifier
The verifier:
- independently checks the task outcome,
- writes the verification report,
- writes the verifier-to-lead handoff,
- updates verification state,
- and issues only `pass` or `fail`.

---

## 5. Required task lifecycle fields

Every task YAML must contain these lifecycle fields.

```yaml
primary_type: repo_only | deploy_only | repo_and_deploy | investigation_only
status: proposed | ready | in_progress | verification_pending | verified_pass | verified_fail | blocked | resolved | closed_not_fixed
verification_result: pending | pass | fail | not_required
owner: lead
```

### Lifecycle meaning

- `primary_type` is the class of work. It must never be overloaded with status.
- `status` is the current lifecycle state.
- `verification_result` records verification outcome separately from status.

### Allowed transitions

Only these transitions should occur.

#### Lead may set
- `proposed -> ready`
- `ready -> in_progress`
- `verified_pass -> resolved`
- `verified_fail -> blocked`
- `blocked -> ready` when blocker is removed

#### Implementer may set
- `in_progress -> verification_pending`
- `in_progress -> blocked`

#### Verifier may set
- `verification_pending -> verified_pass`
- `verification_pending -> verified_fail`

### Important
A task should never end up like:
- `primary_type: resolved`
- `status: in_progress`

`primary_type` is the work category, not the completion state.

---

## 6. Required execution block

Every task YAML must include an `execution` section.

```yaml
execution:
  current_role: lead | implementer | verifier
  next_role: implementer | verifier | lead | none
  requires_verifier: true | false
  handoff_files:
    lead_to_implementer: reports/handoffs/<task-id>/lead_to_implementer.md
    implementer_to_verifier: reports/handoffs/<task-id>/implementer_to_verifier.md
    verifier_to_lead: reports/handoffs/<task-id>/verifier_to_lead.md
  reports:
    implementation: reports/<task-id>-implementation.md
    verification: reports/<task-id>-verification.md
  repo_test_command: <single canonical command or script>
  live_check_command: <single canonical command or script, if applicable>
```

This block is what makes the same user prompt reusable.

Agents should use this block to determine:
- what they are expected to read,
- what they are expected to write,
- and who is supposed to act next.

---

## 7. Required artifact paths

Every task must define artifact paths explicitly.

At minimum:

```yaml
artifacts:
  implementation_report: reports/<task-id>-implementation.md
  verification_report: reports/<task-id>-verification.md
```

For any task using role handoffs, also include:

```yaml
execution:
  handoff_files:
    lead_to_implementer: reports/handoffs/<task-id>/lead_to_implementer.md
    implementer_to_verifier: reports/handoffs/<task-id>/implementer_to_verifier.md
    verifier_to_lead: reports/handoffs/<task-id>/verifier_to_lead.md
```

Agents must write their handoff files there instead of assuming the user will manually move information between chats.

---

## 8. Required handoff contents

### `lead_to_implementer.md`
Must contain:
- task classification,
- exact files to read,
- exact goal,
- constraints that matter,
- required outputs,
- stop conditions,
- and the recommended next task status after implementation.

### `implementer_to_verifier.md`
Must contain:
- files changed,
- commands run,
- reports written,
- unresolved risks,
- what must be independently verified,
- and the recommended next task status.

### `verifier_to_lead.md`
Must contain:
- exact verification commands used,
- exact evidence summary,
- pass/fail verdict,
- mismatches found,
- and recommended final status.

These files are the internal task bus.

---

## 9. Required reports

### Implementation report
Must contain these sections:
1. Files changed
2. Why each file changed
3. Commands run
4. Tests run
5. Deploy actions taken
6. Remaining gaps / unresolved risks
7. Recommended next status

### Verification report
Must contain these sections:
1. Exact commands used
2. Exact captured stdout/stderr
3. Acceptance mapping: pass/fail by criterion
4. Repo/host/live mismatches
5. Final verdict
6. Recommended next status

For `repo_only` tasks, host/live sections may say `not applicable`.

For `repo_and_deploy` tasks, host/live sections are mandatory.

---

## 10. Required task sections

Every task YAML should use this structure.

```yaml
id: T-000
title: Clear title
primary_type: repo_only
owner: lead
status: proposed
verification_result: pending
priority: high

objective: >
  One-sentence statement of what success means.

authority:
  precedence:
    - path/to/highest/authority.md
  notes:
    - specific invariant or rule

scope:
  repos:
    - mycite-core
  repo_paths:
    - path/one
    - path/two
  live_systems: []

required_outputs:
  - output one
  - output two

acceptance:
  - measurable acceptance item one
  - measurable acceptance item two

implementation_requirements:
  - what implementer must do
  - what implementer must not do

verification_requirements:
  - what verifier must prove
  - what causes failure

artifacts:
  implementation_report: reports/T-000-implementation.md
  verification_report: reports/T-000-verification.md

execution:
  current_role: lead
  next_role: implementer
  requires_verifier: true
  handoff_files:
    lead_to_implementer: reports/handoffs/T-000/lead_to_implementer.md
    implementer_to_verifier: reports/handoffs/T-000/implementer_to_verifier.md
    verifier_to_lead: reports/handoffs/T-000/verifier_to_lead.md
  reports:
    implementation: reports/T-000-implementation.md
    verification: reports/T-000-verification.md
  repo_test_command: <canonical repo command>
  live_check_command: <canonical live command or not_applicable>

closure_rule: >
  State exactly what must exist before lead may mark the task resolved.
```

---

## 11. Role behavior against the task file

### Lead behavior
When told to proceed with a task, the lead must:
1. read the task YAML,
2. validate that the lifecycle fields are sane,
3. validate that artifact and handoff paths exist or can be created,
4. write `lead_to_implementer.md`,
5. update:
   - `status` to `ready` or `in_progress`,
   - `execution.current_role` to `implementer`,
   - `execution.next_role` to `verifier` or `lead` depending on task type.

The lead must not implement.

### Implementer behavior
When told to proceed with a task, the implementer must:
1. read the task YAML,
2. read `lead_to_implementer.md`,
3. perform only scoped work,
4. write the implementation report,
5. write `implementer_to_verifier.md`,
6. update:
   - `status` to `verification_pending` or `blocked`,
   - `execution.current_role` to `verifier` or `lead`,
   - `execution.next_role` accordingly.

The implementer must not mark a task resolved.

### Verifier behavior
When told to proceed with a task, the verifier must:
1. read the task YAML,
2. read the implementation report,
3. read `implementer_to_verifier.md`,
4. run or inspect the required checks independently,
5. write the verification report,
6. write `verifier_to_lead.md`,
7. update:
   - `status` to `verified_pass`, `verified_fail`, or `blocked`,
   - `verification_result` to `pass` or `fail`,
   - `execution.current_role` to `lead`,
   - `execution.next_role` to `lead`.

The verifier must not mark a task resolved.

---

## 12. Closure rule

A task is only resolved when:
- acceptance criteria are satisfied,
- required reports exist,
- required handoff files exist,
- any required verifier pass exists,
- and the lead updates `status: resolved`.

For `repo_and_deploy` tasks, live evidence is required when acceptance mentions:
- live URLs,
- rendered portal behavior,
- nginx,
- systemd,
- OAuth behavior,
- static asset delivery,
- health endpoints,
- or screenshots of production behavior.

---

## 13. Minimal context rule

Agents should not load the whole repo by default.

They should start from:
- `agent/constraints.md`
- `agent/<role>.md`
- `tasks/README.md`
- `tasks/<task-id>.yaml`

Then they should read only:
- the files named in `scope.repo_paths`,
- the report files named in `artifacts`,
- the handoff files named in `execution.handoff_files`,
- and only the smallest number of additional files needed to remove ambiguity.

---

## 14. Repo-specific MyCiteV2 rules

These are inherited from standing constraints and should shape all task authoring.

- `shell_composition` is the shell truth.
- Tools attach through shell-defined surfaces.
- Browser JS must not become the real shell model.
- V1 is implementation-history evidence only.
- Repo truth, deploy truth, and live truth must remain separate.
- Archive notes and prior agent reports are non-authoritative unless validated against current repo state.

---

## 15. Task authoring rules

When creating a new task:
- keep the objective singular,
- keep scope tight,
- define exact acceptance,
- define exact artifact paths,
- define exact role transitions,
- and define the canonical repo/live commands if applicable.

Do not create a task that says only “improve system” or “investigate issue” without measurable acceptance.

Bad:
- vague objective,
- no artifact paths,
- no lifecycle fields,
- no closure rule.

Good:
- one concrete objective,
- exact files,
- exact outputs,
- exact evidence requirements,
- exact role transitions.

---

## 16. Example role invocations

### Lead
`You are lead, read agent/constraints.md, agent/lead.md, tasks/README.md, then proceed with tasks/T-003-shell-region-contracts.yaml.`

### Implementer
`You are implementer, read agent/constraints.md, agent/implementer.md, tasks/README.md, then proceed with tasks/T-003-shell-region-contracts.yaml.`

### Verifier
`You are verifier, read agent/constraints.md, agent/verifier.md, tasks/README.md, then proceed with tasks/T-003-shell-region-contracts.yaml.`

These should be enough.

If the task YAML is missing critical information, the agent should record that as a task defect and set the task to `blocked` instead of making up hidden requirements.

---

## 17. Recommended immediate cleanup

Existing tasks should be normalized to this README.

In particular:
- `primary_type` must remain a work category such as `repo_and_deploy`.
- `status` must carry lifecycle state.
- `verification_result` should be added where missing.
- `execution` should be added where missing.
- handoff file paths should be added where missing.

This prevents state drift and eliminates the need for manual handoff copy-paste.

---

## 18. Final principle

The user should choose:
- the task id,
- the role,
- and the chat.

Everything else should be discoverable from:
- the role file,
- this README,
- and the task YAML.