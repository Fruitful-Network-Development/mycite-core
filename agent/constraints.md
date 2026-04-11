# Agent Constraints

This file is the standing constraint source for repo-local agent work.

## 1. Purpose

These constraints exist to stop the recurring failure mode seen in prior portal work:

- repo changes were treated as resolution,
- passing tests were treated as resolution,
- archive notes were treated as stronger than current repo truth,
- and live behavior remained unresolved.

These constraints also exist to stop a second failure mode:

- task coordination was pushed into chat text,
- users had to manually relay agent outputs,
- status fields drifted,
- and handoff state was not consistently written back into the repo.

The repo is the task state.
The repo is the handoff bus.

## 2. Authority order

When sources conflict, use this precedence order.

1. `MyCiteV2/docs/ontology/structural_invariants.md`
2. `MyCiteV2/docs/decisions/`
3. `MyCiteV2/docs/plans/phases/` and `MyCiteV2/docs/plans/phase_completion_definition.md`
4. `MyCiteV2/docs/plans/v1-migration/`
5. `docs/plans/*.md` from V1
6. V1 code as implementation-history evidence only
7. Archive notes, chat summaries, and prior agent reports as non-authoritative evidence only

Operational corollary:

- Current repo state overrides stale archive narration.
- Live host evidence overrides assumptions about deployment.
- Prompt history is never an authority source for V2 structure.

## 3. Structural invariants that must not be violated

The following are mandatory for V2 work.

- Domain logic must not depend on adapters, tools, hosts, or runtime wrappers.
- Navigation state must be pure, explicit, and serializable.
- Tools attach through shell-defined surfaces.
- Tools do not invent alternate shell state.
- Hosts compose modules; hosts do not own domain logic.
- Datum authority must be explicit and fail-closed.
- V1 code is evidence only and must never be copied as a structural template.

For shell and portal work specifically:

- A UI widget is not a shell surface.
- A tool capability is not shell ownership.
- A runtime route is not domain truth.
- Browser JS must not become the real shell.

## 4. Repo / deploy / live separation

Every task must explicitly classify work into one of these types:

- `repo_only`
- `deploy_only`
- `repo_and_deploy`
- `investigation_only`

These are separate truths.

- Repo truth: what is committed.
- Deploy truth: what is installed on the host and running.
- Live truth: what the real URL returns over HTTP and what the rendered portal actually does.

No agent may merge these into one statement.

## 5. Closure rules

A task is not resolved from repo diffs alone when acceptance includes live behavior.

A task is not resolved from tests alone when acceptance includes live behavior.

A task is not resolved from archive notes, screenshots of code, or prior reports.

A task with live acceptance is only resolved when live verification evidence is present.

**Independent verifier:** When acceptance depends on deploy state, live HTTP behavior, or other non-repo truth, a **verifier** must write the task **`verification_report`** with **verbatim command transcripts** for host and live sections. The implementation report and implementer handoff are **not** a substitute for that verifier evidence, and the lead must not treat the task as closed without it.

Required evidence for live portal tasks:

- exact command used,
- exact output captured,
- explicit comparison to acceptance criteria,
- and final verdict of pass or fail.

## 6. Portal-specific rules

For `portal.*` tasks:

- Preserve the V2 shell-composition path.
- `shell_composition` is the canonical shell truth.
- Activity dispatch bodies remain shell-owned.
- Tool legality remains in the state-machine layer.
- No V1 imports into V2 portal host code.
- No fallback navigation that substitutes for runtime-issued activity items.
- If CSS or JS delivery is broken, treat that as a deploy/live issue until proven otherwise.

## 7. Required distinction between evidence classes

Every substantial task report must keep these sections separate:

1. Repo findings
2. Changes made
3. Tests run
4. Deploy findings
5. Live verification
6. Remaining gaps or blockers

If any one of these is unavailable, the report must say so directly.

## 8. Minimal-context rule

Agents should not load the whole repo by default.

They should start from:

- `agent/constraints.md`
- `agent/<role>.md`
- `tasks/README.md`
- the active task file under `tasks/`

They may expand outward only when needed.

## 9. Repo handoff bus rule

When `tasks/README.md` and the task `execution.handoff_files` block are present, agents must use the repo as the coordination medium.

That means:

- write handoff instructions to the handoff files named in the task,
- write evidence to the report files named in the task,
- update task lifecycle fields directly in the task YAML when the role is allowed to do so,
- and avoid relying on user-mediated copy-paste between chats.

Agents should not emit “next prompt” blocks for the user unless:

- the task file is malformed,
- required handoff paths are missing,
- or the repo cannot be updated.

## 10. Verifier independence rule

The verifier must assume the implementer may be wrong.

The verifier must not use the implementer's confidence as evidence.

The verifier should fail the task when:

- live evidence is missing,
- host state was not inspected for a deploy task,
- command outputs are summarized but not shown,
- acceptance criteria are only partially satisfied,
- or the report conflates repo and live truth.

## 11. Output discipline

Agents must be clinically explicit.

Use statements like:

- `Repo fixed; live not verified.`
- `Tests pass; deploy still unresolved.`
- `Live issue fixed.`
- `Not fixed; blocked by host access.`

Do not soften unresolved states.

For tasks using repo-based handoffs, final chat output should be brief and operational:

- what file(s) were written,
- what task state was updated,
- what role is next,
- and whether the task is blocked.

Do not repeat the full handoff contents back to the user when those contents were already written to the repo.