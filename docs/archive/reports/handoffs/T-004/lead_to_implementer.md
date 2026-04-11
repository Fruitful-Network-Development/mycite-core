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
