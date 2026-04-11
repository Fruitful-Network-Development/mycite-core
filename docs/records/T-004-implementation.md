# T-004 implementation report

**Task:** T-004 — Standardize implementation and verification evidence artifacts  
**Role:** implementer  
**Date:** 2026-04-11

---

## 1. Files changed

| Path | Change type |
|------|-------------|
| `reports/templates/implementation_report_template.md` | documentation |
| `reports/templates/verification_report_template.md` | documentation |
| `agent/lead.md` | documentation |
| `tasks/README.md` | documentation |

---

## 2. Why each file changed

- **`reports/templates/implementation_report_template.md`:** Align section titles with **repo / host / live** separation; add a short **task-type** cue block for `repo_only` vs `repo_and_deploy` / `deploy_only`; keep placeholders command-oriented per `implementation_requirements`.
- **`reports/templates/verification_report_template.md`:** Same task-type cue block; keep **Final verdict** as a required `PASS` / `FAIL` field; clarify when host/live lines may be `not applicable` vs when transcripts are mandatory.
- **`agent/lead.md`:** Satisfy acceptance that **role docs** state verifier-written evidence is mandatory for non-repo closure — explicit sentence under closure rules (cross-links to README §9 and verification template).
- **`tasks/README.md`:** Tighten **§9.2** `closure_rule` semantics (name reports + verifier pass + transcripts when §9.3 applies); document optional **`artifacts.template_paths`**; extend the §10 example YAML accordingly.

---

## 3. Commands run

None required by task (`execution.repo_test_command: not_applicable`). No ad hoc commands were run for this documentation-only change set.

```text
not applicable
```

---

## 4. Tests run

```text
not applicable (repo_test_command: not_applicable)
```

---

## 5. Deploy actions taken

None. **primary_type:** `repo_only`; no host changes.

---

## 6. What still requires independent verification

The **verifier** should confirm per `tasks/T-004-evidence-artifacts-and-verification.yaml`:

- Templates enforce **implementer vs verifier** role separation and keep **repo / host / live** evidence classes separable.
- Templates support both **`repo_only`** (host/live `not applicable`) and **`repo_and_deploy`** (transcript expectations per §9.3).
- Standing docs (`agent/lead.md`, `tasks/README.md`, existing `agent/constraints.md` / `agent/implementer.md` / `agent/verifier.md`) clearly require **verifier-written** evidence when closure depends on deploy/live behavior.

**Example tasks** already referencing **`artifacts.implementation_report`** and **`artifacts.verification_report`** plus mirrored **`execution.reports`:** `tasks/T-002-deploy-truth-automation.yaml`, `tasks/T-003-shell-region-contracts.yaml`, and this task’s YAML.

---

## 7. Recommended next status

`status: verification_pending`  
`execution.current_role: verifier`  
`execution.next_role: lead`  
`verification_result: pending` (unchanged until verifier acts)

# Verifier → Lead: T-004

## Verification commands used

1. `cd /srv/repo/mycite-core && ls -la reports/templates/ && wc -l reports/templates/*.md && rg -l "implementation_report:|verification_report:" tasks/*.yaml | sort` — `rg` not available in verifier shell (`exit 127` on that segment).
2. `cd /srv/repo/mycite-core && grep -l "implementation_report:" tasks/*.yaml | sort` and the same for `verification_report:` — both lists match; all six active task YAMLs under `tasks/` declare both paths.

## Evidence summary

- **Templates:** `reports/templates/implementation_report_template.md` and `verification_report_template.md` exist; headings separate repo, host, and live; task-type cues cover `repo_only` vs deploy/live types; verification template requires **Final verdict** `PASS` / `FAIL`.
- **Standing docs:** `agent/lead.md` closure rules require verifier-written verification report with verbatim host/live transcripts when non-repo truth gates closure; `agent/constraints.md`, `agent/implementer.md`, `agent/verifier.md`, and `tasks/README.md` §9.3 reinforce mandatory verifier evidence for live-behavior closure.
- **Example tasks:** T-001 through T-006 each reference `artifacts.implementation_report` and `artifacts.verification_report` (grep listing in verification report appendix).
- **Implementation / handoff:** Read `reports/T-004-implementation.md` and `reports/handoffs/T-004/implementer_to_verifier.md`; consistent with observed repo state.

## Verdict

**PASS** — all acceptance criteria in `tasks/T-004-evidence-artifacts-and-verification.yaml` are met.

## Mismatches

None.

## Recommended final status

- `status: verified_pass` (verifier-set)
- `verification_result: pass`
- `execution.current_role: lead`, `execution.next_role: lead`

Lead may set `status: resolved` when satisfied with `reports/T-004-verification.md` and `closure_rule` on the task file.

# Lead → Implementer: T-004 evidence artifacts and verification

## Task classification

- **primary_type:** `repo_only` (confirmed; `live_systems: []`, `live_check_command: not_applicable`).
- **Closure evidence:** Standard templates under `reports/templates/`, aligned agent docs / `tasks/README.md` conventions, `reports/T-004-implementation.md`, `reports/handoffs/T-004/implementer_to_verifier.md`, independent verifier pass and `reports/T-004-verification.md`.

## Exact files to read (in order)

1. `tasks/T-004-evidence-artifacts-and-verification.yaml` — acceptance and `artifacts.template_paths`.
2. `tasks/README.md` — especially §9 (reports), §9.1–§9.3 (templates, YAML artifact paths, when verifier evidence is mandatory).
3. `reports/templates/implementation_report_template.md` and `reports/templates/verification_report_template.md` — current content vs task acceptance.
4. `agent/constraints.md` — §5, §7, §10 (evidence classes; independent verifier; verbatim transcripts for non-repo truth).
5. `agent/implementer.md` and `agent/verifier.md` — role separation and verifier independence.
6. `agent/lead.md` — closure rules; check whether it **explicitly** states that verifier-written evidence is mandatory for live-behavior / non-repo acceptance (task acceptance names “agent role docs **or** constraints”; if `lead.md` is the gap, add one short operational sentence there).

Optional: skim one resolved task YAML (e.g. `tasks/T-003-shell-region-contracts.yaml`) as the “example” that references both `artifacts.implementation_report` / `artifacts.verification_report` and mirrored `execution.reports` — only extend task examples if no task currently satisfies the acceptance bullet.

## Exact goal

Satisfy **all** `acceptance` items in T-004 with **minimal** edits:

1. Reusable **implementation** and **verification** report templates exist and stay **short and operational**, with **separate repo / host / live** sections and guidance for `repo_only` vs `repo_and_deploy`.
2. **Task YAML + README** clearly document artifact paths and **closure_rule** semantics (README §9.2 already sketches this — tighten or cross-link if anything is ambiguous).
3. **Standing agent docs** (at minimum `constraints.md`; plus any gap in `lead.md` / `verifier.md` / `implementer.md` needed for the acceptance bullet) clearly state that **verifier evidence is mandatory** when closure depends on deploy or live behavior (not substitutable by implementer narrative).
4. At least **one** task file documents both implementation and verification artifact paths per README pattern.

Favor **exact command / output placeholders** over long prose in templates (`implementation_requirements`).

## Constraints that matter

- Do not conflate repo, deploy, and live truth in a single narrative block (`agent/constraints.md` §4, §7).
- Templates must support **both** `repo_only` (host/live `not applicable`) and `repo_and_deploy` (mandatory host/live transcripts where task requires).
- Verification template must include a **required final verdict** field (already present — preserve or strengthen if verifier asks).

## Required outputs

1. Updated or confirmed files so acceptance is met (templates, `tasks/README.md`, `agent/*.md` as needed — **smallest diff**).
2. `reports/T-004-implementation.md` per `tasks/README.md` §9.
3. `reports/handoffs/T-004/implementer_to_verifier.md` per §8.
4. **Task YAML (implementer):** after work, set `status` to `verification_pending` (or `blocked` if stuck), `execution.current_role` to `verifier`, `execution.next_role` to `lead`. Do **not** set `verification_result` or `resolved`.

**Note:** `reports/handoffs/T-004/implementer_to_verifier.md` and `verifier_to_lead.md` may exist from an earlier attempt; treat them as **non-authoritative** until you overwrite or invalidate via your new implementation report and handoff.

## Stop conditions

- If acceptance would require inventing policy not grounded in `constraints.md` / `tasks/README.md`, set task `blocked` and document the defect in `reports/T-004-implementation.md`.
- `repo_test_command` is `not_applicable`; do not claim repo test runs unless you run optional sanity checks and paste output.

## Recommended next task status after implementation

- `status: verification_pending`
- `execution.current_role: verifier`
- `execution.next_role: lead`
- `verification_result: pending` (unchanged until verifier acts)

# Implementer → Verifier: T-004

## Files changed

- `reports/templates/implementation_report_template.md`
- `reports/templates/verification_report_template.md`
- `agent/lead.md`
- `tasks/README.md`

## Commands run

- None (`repo_test_command: not_applicable`).

## Reports written

- `reports/T-004-implementation.md` (this cycle)
- Templates updated in place under `reports/templates/`

## Unresolved risks

- None known; scope is repo-only documentation and templates.

## What must be independently verified

1. Templates remain **short and operational**, with **separate repo / host / live** sections and clear behavior for **`repo_only`** vs **`repo_and_deploy`**.
2. **Verification template** retains a **required final verdict** (`PASS` / `FAIL`).
3. **Role separation:** implementer template vs verifier template; lead **closure** text now states verifier report + transcripts are mandatory when non-repo truth gates closure.
4. **At least one example task** with both artifact paths: see `tasks/T-002-deploy-truth-automation.yaml`, `tasks/T-003-shell-region-contracts.yaml`, `tasks/T-004-evidence-artifacts-and-verification.yaml` (`artifacts` + `execution.reports`).

## Recommended next task status

- `status: verification_pending`
- `execution.current_role: verifier`
- `execution.next_role: lead`
- `verification_result: pending` until you record `pass` or `fail`

Please write `reports/T-004-verification.md` using `reports/templates/verification_report_template.md` and `reports/handoffs/T-004/verifier_to_lead.md` per `tasks/README.md`.

# Verification report

**Task:** T-004 — Standardize implementation and verification evidence artifacts  
**Role:** verifier  
**Date:** 2026-04-11

**Task type:** `repo_only`  
- **Host** and **Live** = `not applicable` (no deploy/live acceptance for T-004).

---

## 1. Repo layer

Confirmed on disk under `/srv/repo/mycite-core`:

- `reports/templates/implementation_report_template.md` — implementer-oriented sections **1 Repo findings**, **5 Host state**, **6 Live HTTP / operational checks**; opening **Task type** block distinguishes `repo_only` vs `repo_and_deploy` / `deploy_only` with explicit `not applicable` vs transcript rules.
- `reports/templates/verification_report_template.md` — verifier-oriented **1 Repo layer**, **2 Host layer**, **3 Live HTTP / operational layer**; same task-type cue; **6 Final verdict** requires `PASS` or `FAIL`.
- `agent/lead.md` — **Decision rules for closure** (lines 125–138) requires verifier-written `verification_report` with verbatim host/live transcripts when closure depends on non-repo truth; references `tasks/README.md` §9 and the verification template.
- `agent/constraints.md` — §5 **Independent verifier** and §7 evidence-class separation already require verifier transcripts for live acceptance.
- `agent/implementer.md` — states implementer is not closer for live-behavior tasks and verifier-written evidence is mandatory.
- `agent/verifier.md` — defines independent verifier duties and mandatory transcripts for deploy/live tasks.
- `tasks/README.md` — §9.2 `closure_rule` semantics, optional `artifacts.template_paths`, §9.3 **When verifier evidence is mandatory**, §10 example YAML with `template_paths`.

**Example tasks** with both `artifacts.implementation_report` and `artifacts.verification_report` (and mirrored `execution.reports` where present): `tasks/T-001-live-portal-shell.yaml` through `tasks/T-006-operational-smoke-and-regression-gates.yaml` (all six list both keys per `grep` below).

Independent read of `reports/T-004-implementation.md` and `reports/handoffs/T-004/implementer_to_verifier.md`: scope and file list align with repo state above.

---

## 2. Host layer

```text
not applicable (primary_type: repo_only; T-004 acceptance does not require host inspection)
```

---

## 3. Live HTTP / operational layer

```text
not applicable (primary_type: repo_only; execution.live_check_command: not_applicable)
```

---

## 4. Acceptance mapping

| Acceptance criterion | Evidence (section #) | Result (pass / fail) |
|----------------------|----------------------|----------------------|
| Standard implementation report template exists | §1 — `reports/templates/implementation_report_template.md` on disk | pass |
| Standard verification report template exists | §1 — `reports/templates/verification_report_template.md` on disk | pass |
| Templates distinguish repo, host, and live HTTP evidence | §1 — section headings and task-type cues in both templates | pass |
| Role docs or constraints state verifier evidence mandatory for live-behavior tasks | §1 — `agent/constraints.md`, `agent/lead.md`, `agent/implementer.md`, `agent/verifier.md`, `tasks/README.md` §9.3 | pass |
| At least one example task references both implementation and verification artifact paths | §1 — six tasks under `tasks/` name both keys (command output §2) | pass |
| Templates enforce implementer vs verifier role separation | §1 — separate template files; impl = findings/changes/commands/tests/host/live as implementer evidence; verification = independent layers + acceptance table + verdict | pass |
| Templates support `repo_only` and `repo_and_deploy` patterns | §1 — task-type blocks in both templates | pass |

---

## 5. Repo / host / live mismatches

None identified. Repo-only scope; no host or live claims to contradict.

---

## 6. Final verdict

**Verdict (required):** `PASS`

All T-004 acceptance items are satisfied in the committed tree; templates are short, operational, and keep evidence classes and roles separable.

---

## 7. Recommended next status

`status: verified_pass`  
`verification_result: pass`  
`execution.current_role: lead`  
`execution.next_role: lead`  

Lead may set `status: resolved` per `closure_rule` after reviewing this report.

---

## Appendix: commands used (verbatim)

### Command 1

```text
cd /srv/repo/mycite-core && ls -la reports/templates/ && wc -l reports/templates/*.md && rg -l "implementation_report:|verification_report:" tasks/*.yaml | sort
```

### Output 1

```text
total 16
drwxrwxr-x 2 admin admin 4096 Apr 11 04:02 .
drwxrwxr-x 4 admin admin 4096 Apr 11 04:03 ..
-rw-rw-r-- 1 admin admin 1711 Apr 11 04:07 implementation_report_template.md
-rw-rw-r-- 1 admin admin 1569 Apr 11 04:07 verification_report_template.md
  79 reports/templates/implementation_report_template.md
  69 reports/templates/verification_report_template.md
 148 total
--: line 1: rg: command not found
```

### Command 2 (substitute listing; `rg` unavailable in environment)

```text
cd /srv/repo/mycite-core && grep -l "implementation_report:" tasks/*.yaml | sort && grep -l "verification_report:" tasks/*.yaml | sort
```

### Output 2

```text
tasks/T-001-live-portal-shell.yaml
tasks/T-002-deploy-truth-automation.yaml
tasks/T-003-shell-region-contracts.yaml
tasks/T-004-evidence-artifacts-and-verification.yaml
tasks/T-005-routing-truth-unification.yaml
tasks/T-006-operational-smoke-and-regression-gates.yaml
tasks/T-001-live-portal-shell.yaml
tasks/T-002-deploy-truth-automation.yaml
tasks/T-003-shell-region-contracts.yaml
tasks/T-004-evidence-artifacts-and-verification.yaml
tasks/T-005-routing-truth-unification.yaml
tasks/T-006-operational-smoke-and-regression-gates.yaml
```

The two lists are identical: every listed task declares both artifact paths.
