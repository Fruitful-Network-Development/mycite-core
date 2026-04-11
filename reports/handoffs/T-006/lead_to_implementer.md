# Lead → Implementer: T-006 operational smoke and regression gates

## Task classification

- **primary_type:** `repo_and_deploy` (confirmed). `live_systems` includes the production portal host; acceptance requires **stable repo commands**, **stable live smoke**, and **verifier-rerun** with evidence — not narrative closure alone.
- **Evidence:** Per `agent/constraints.md` §5 / §88 and `closure_rule`, the implementer produces `reports/T-006-implementation.md`, **`reports/T-006-smoke-gate.md`** (`artifacts.smoke_gate_doc`), and `reports/handoffs/T-006/implementer_to_verifier.md` with **separate** repo vs live (and host if applicable) sections and **verbatim** command transcripts. The **verifier** independently runs the documented gate and records outcomes in `reports/T-006-verification.md` with **verbatim** output; implementer output does **not** substitute.

## Exact files to read (in order)

1. `tasks/T-006-operational-smoke-and-regression-gates.yaml` — acceptance, `execution.repo_test_command`, `execution.live_check_command`, artifacts.
2. `tasks/T-002-deploy-truth-automation.yaml` — resolved reference for deploy-truth scope and how `verify_v2_portal_deploy_truth.sh` fits the stack.
3. **Authority / tests:** `MyCiteV2/docs/ontology/structural_invariants.md`, `MyCiteV2/docs/plans/authority_stack.md`, `MyCiteV2/tests/architecture/test_v2_native_portal_host_boundaries.py`, `MyCiteV2/tests/integration/test_v2_native_portal_host.py` — boundaries the gate must **not** violate; **do not** replace these with smoke-only checks (`implementation_requirements`: layer, do not swap).
4. **`scripts/verify_v2_portal_deploy_truth.sh`** — current live/repo/host checks (shell markers, static URLs, health schema, nginx, systemd); **reuse** as the live leg unless you extend it with a documented, minimal delta.
5. **`tasks/README.md`** §9–§9.3 — report templates and when verifier evidence is mandatory.

## Exact goal

1. **`reports/T-006-smoke-gate.md`** — single **operator-facing** document that any verifier (or CI) can follow **without chat history**:
   - **Step 1 — Repo:** Run the **exact** portal-host unittest sequence. Default source of truth is the task’s **`execution.repo_test_command`** (multi-directory `unittest discover` with `PYTHONPATH` and venv path as written). If you change the command, update **both** the smoke doc **and** `tasks/T-006-operational-smoke-and-regression-gates.yaml` so they stay identical.
   - **Step 2 — Live smoke:** Run the **exact** **`execution.live_check_command`** (`bash scripts/verify_v2_portal_deploy_truth.sh` from `mycite-core` root unless task YAML is updated in lockstep).
   - Explicitly state that **failure at either step blocks closure** (acceptance).
   - Call out, in plain language, that the live script covers **shell markers**, **static asset routes** (`/portal/static/...`), and **health / static bundle** expectations (align wording with what the script actually checks — read the rest of the script if needed).
2. **Optional narrow additions:** Small script wrapper (e.g. under `scripts/`) *only if* it reduces duplication without broadening scope beyond “current portal shell risks” (`implementation_requirements`). Prefer documenting the two canonical commands if that suffices.
3. **Evidence paths:** The smoke doc must name where implementer and verifier record runs (`reports/T-006-implementation.md`, `reports/T-006-verification.md`) and point at standard templates under `reports/templates/` if helpful.

## Constraints that matter

- **Repo / live separation** in reports; no merged “everything passed” without two layers of evidence.
- **Do not** drop or bypass existing integration/architecture tests in favor of curl-only smoke.
- **Determinism:** Documented commands must be copy-paste stable (paths, venv, env vars such as `MYCITE_CORE` / `SRV_INFRA` if the script depends on them — mirror `verify_v2_portal_deploy_truth.sh` header).
- **Verifier independence:** Document what the verifier must re-run; do not ask the verifier to trust implementer-only runs for closure.

## Required outputs

1. **`reports/T-006-smoke-gate.md`** — canonical gate procedure (repo then live; explicit failure semantics).
2. **`reports/T-006-implementation.md`** — per `tasks/README.md` §9.
3. **`reports/handoffs/T-006/implementer_to_verifier.md`** — per §8: files changed, commands run, verbatim highlights, what verifier must rerun, risks.
4. **Task YAML (implementer):** If `repo_test_command` or `live_check_command` strings change, edit **`tasks/T-006-operational-smoke-and-regression-gates.yaml`** to match the smoke doc **exactly**. When handing off: `status: verification_pending`, `execution.current_role: verifier`, `execution.next_role: lead`. Do **not** set `verification_result` or `resolved`.

## Stop conditions

- If a **single** stable repo command cannot be defined (e.g. venv path wrong for all environments), document the blocker and set `status: blocked` with honest limits in the implementation report — do not invent fake universality.
- If live checks cannot run from the implementer environment, still complete the **repo** doc and handoff; note live gap for verifier — do **not** claim full gate pass yourself.

## Recommended next task status after implementation

- `status: verification_pending`
- `execution.current_role: verifier`
- `execution.next_role: lead`
- `verification_result: pending`
