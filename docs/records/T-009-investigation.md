# T-009 Investigation: V1 AWS-CMS onboarding control plane vs post-T-008 V2 seams

## 1. Repo findings

### 1.1 V1 control plane (evidence only)

**Surface:** `POST /portal/api/admin/aws/profile/<profile_id>/provision` with JSON `action` in `MyCiteV1/instances/_shared/runtime/flavors/fnd/portal/api/admin_integrations.py` (see `allowed_actions` and dispatch ~L2224–2305). UI triggers the same verbs from `aws_platform_admin.js` and `system_shell_runtime.js`.

**Semantics contract:** [`docs/V1/modularity/contracts/aws_csm.md`](../docs/V1/modularity/contracts/aws_csm.md) describes mailbox-scoped profile JSON, workflow vs verification vs inbound independence, and IAM/SMTP operational model.

**Normalization:** `MyCiteV1/packages/tools/aws_csm/state_adapter/profile.py` (`normalize_aws_csm_profile_payload`) — evidence for field semantics; V2 uses the same **live profile schema** via `FilesystemLiveAwsProfileAdapter` / `mycite.service_tool.aws_csm.profile.v1`, not this package as structure.

### 1.2 Post-T-008 V2 seams (current repo baseline)

| Seam | Location | Posture |
|------|----------|---------|
| Read-only trusted-tenant AWS tool | `admin_band1.aws_read_only_surface`, `run_admin_aws_read_only`, `POST .../admin/aws/read-only` | **Existing read-only seam** — maps canonical live profile to `AwsOperationalVisibilityService` output; no provision verbs. |
| Narrow bounded write | `admin_band2.aws_narrow_write_surface`, `run_admin_aws_narrow_write`, `AwsNarrowWriteService` | **Existing bounded-write seam** — today only `selected_verified_sender` (+ derived send_as / smtp local_part in adapter) per `ALLOWED_AWS_NARROW_WRITE_FIELDS` in `MyCiteV2/packages/modules/cross_domain/aws_narrow_write/service.py`. |
| Internal sandbox read-only | `admin_band3.aws_csm_sandbox_surface`, `run_admin_aws_csm_sandbox_read_only`, `sandboxes/tool/aws_csm_staging.py`, `MYCITE_V2_AWS_CSM_SANDBOX_STATUS_FILE` | **Existing sandbox seam (read-only only)** per `admin_band3_aws_csm_sandbox_surface.md` — path validation + same read path as Band 1; **no narrow write** on this slice. |
| Shell / composition | `admin_shell.py`, `admin_runtime.py`, `shell_region_kinds.md`, `v2_portal_shell.js` | Tool mode for all three AWS-related slices; activity/control dispatch bodies are shell-owned. |

**Conclusion:** V2 has **strong read-only and one-field narrow-write** plus **sandbox read-only rehearsal**. It has **no** shell-registered onboarding orchestration equivalent to V1’s ten provision actions.

### 1.3 Per-action V1 behavior vs V2 mapping

Actions are ordered as in task acceptance. Classifications use: **RO** = existing read-only seam, **NW** = existing bounded-write seam, **SB** = existing sandbox seam, **Slice** = new shell-visible onboarding slice/surface, **Orch** = orchestration beneath fewer shell verbs, **Omit** = intentionally dropped or legacy-only.

| V1 action | V1 effect (repo-grounded) | V2 today | Classification |
|-----------|---------------------------|----------|------------------|
| `begin_onboarding` | Sets `workflow.initiated` / `initiated_at` via `_update_aws_profile` (~L1169–1198). | Read-only shows derived readiness; narrow write cannot set workflow flags. | **Gap →** new **bounded-write** field set (extend narrow-write contract) **or** **Orch** step under a new **Slice** verb `admin.aws.csm_onboarding` with explicit sub-commands — **not** SB-first (trusted-tenant canonical file). |
| `prepare_send_as` | Alias of `_stage_smtp_credentials_for_profile` with `response_action="prepare_send_as"` (~L1284–1290). | None. | **Gap →** **Orch** + **Slice** (operator handoff bundle is UX-critical). |
| `stage_smtp_credentials` | SES identity read, `_provision_smtp_secret_material`, merge identity/smtp/provider/workflow/inbound, returns `smtp_handoff` (~L1202–1278). | None. | **Gap →** **Orch** (Secrets Manager / IAM / local material per V1) + **module** + **adapter ports** + **Slice**; secrets never in visibility payload (already forbidden keys in `aws_operational_visibility`). |
| `capture_verification` | `_find_latest_verification_message` (S3), merges `verification` + `workflow` + `inbound` (~L1293–1356). | None. | **Gap →** **Orch** (S3 read port) + profile write via bounded pattern; **Slice** or sub-verb. |
| `refresh_provider_status` | `_ses_identity_status` + `_update_aws_profile` provider fields (~L1091–1123). | Read-only reflects **file** state; no live SES refresh writeback. | **Gap →** **Orch** (SES read port) + bounded profile patch; expose refreshed summary via **RO** after write. |
| `refresh_inbound_status` | Locates latest verification message + inbound patch, writes profile (~L1127–1165). | Partial overlap conceptually with `inbound_capture` **derivation** in visibility service from **static** file only. | **Gap →** **Orch** + bounded write (same as capture path family). |
| `enable_inbound_capture` | Route53 MX + SES receipt rule + `_refresh_inbound_status` (~L610–633). | None. | **Gap →** **Orch** (Route53 + SES receipt ports); high blast radius — **trusted-tenant** shell slice, strict audit, **not** sandbox until policy exists. |
| `replay_verification_forward` | Lambda invoke on legacy forwarder (~L1359–1427); explicit compatibility warning. | None. | **Gap →** classify as **Omit** from default V2 shell **or** **Orch**-only compatibility tool hidden behind explicit gate — not default onboarding slice. |
| `confirm_receive_verified` | Re-runs capture then sets inbound receive_verified flags (~L1431–1471). | None. | **Gap →** **bounded write** (possibly merged with narrow-write family as additional allowed fields **or** dedicated verb). |
| `confirm_verified` | Requires Gmail evidence via `_has_gmail_confirmation_evidence`; sets verification + provider gmail + workflow + inbound (~L1475–1538). | None. | **Gap →** **bounded write** + evidence guardrails in **module** (fail-closed). |

### 1.4 Sandbox vs trusted-tenant for onboarding

- **T-008 sandbox** is **internal-only, read-only** (`admin_band3_aws_csm_sandbox_surface.md`). Onboarding steps that **mutate AWS control plane** (Route53, SES rules, secrets) or **canonical production profile** should remain under **trusted-tenant** Band 1/2-style entrypoints (or new **Band 2+** write slice), not the internal sandbox slice, until product policy explicitly allows sandbox writes.
- **Sandboxes package** remains appropriate for **staging path validation** and future **orchestrated dry-runs**; it does not replace shell-owned workflow legality.

### 1.5 Live deployment / exposure

- **This investigation:** `live_systems: []` — no host inspection.
- **Follow-on implementation (repo build):** can remain **`repo_only`** if acceptance is limited to unittest + temp profile files + stubbed/mocked ports (same closure pattern as T-008).
- **Separate later task (`repo_and_deploy`)** when acceptance includes operators using onboarding against **live** AWS accounts, real DNS/SES, systemd/env rollout, and HTTP-visible behavior — then **verifier transcripts** per `tasks/README.md` §9.3.

## 2. Changes made

None. Investigation-only; no product code.

## 3. Tests run

Not applicable (no code changes for this deliverable).

## 4. Deploy findings

Not inspected (out of scope).

## 5. Live verification

Not applicable.

## 6. Parity-gap ownership table

| Area | Gap | Likely owners |
|------|-----|----------------|
| Shell state / legality | New slice(s) or extended tool registry; activity + control_panel dispatch bodies; fail-closed audience rules | `hanus_shell/admin_shell.py`, `admin_runtime.py`, `shell_region_kinds.md`, `v2_portal_shell.js` |
| Runtime / orchestration | New entrypoint(s), compose with existing `run_admin_shell_entry` | `admin_aws_runtime.py`, `admin_runtime.py`, `runtime_platform.py`, `portal_host/app.py` |
| Semantic modules | Onboarding state transitions, evidence checks, merge rules (no adapter imports) | new or extended `packages/modules/cross_domain/*` |
| Ports / adapters | SES, S3 message discovery, Route53, receipt rules, secrets material — thin adapters | `packages/ports/*`, `packages/adapters/*` |
| Sandbox | Optional: staged profile rehearsal; **not** default home for production writes | `packages/sandboxes/tool/` |
| Tests | Integration per verb or verb-class; architecture import boundaries | `MyCiteV2/tests/integration/`, `MyCiteV2/tests/architecture/` |

## 7. Shell-owned slices vs orchestration-only

- **Shell-visible:** operator-facing steps that change mailbox meaning or require confirmation: begin/initiate, prepare/stage SMTP handoff, capture/confirm verification, enable inbound, confirm receive/send-as complete. These should appear as **registry-backed** tools or **shell-dispatched** workflow requests with explicit `shell_request` bodies (not ad-hoc browser POST shapes).
- **Orchestration-only beneath fewer surfaces:** SES/Route53/S3/Lambda calls chained inside a single **bounded** runtime entrypoint per user intent (e.g. “refresh provider” performs read + patch + read-after-write) rather than exposing raw AWS APIs.
- **Intentionally narrowed:** `replay_verification_forward` — **legacy Lambda** path; default V2 should prefer **portal-native capture**; replay remains optional compatibility **Orch** or **Omit**.

## 8. Recommended primary_type for follow-on build

**`repo_only`** for `tasks/T-010-v2-aws-csm-onboarding-workflow.yaml` — implement orchestration + shell surfaces + tests with **file-backed profiles and test doubles** for AWS ports. Defer **`repo_and_deploy`** until acceptance explicitly requires live operator verification.

## 9. Exact repo paths likely to change (T-010)

- `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py`
- `MyCiteV2/instances/_shared/runtime/admin_runtime.py`
- `MyCiteV2/instances/_shared/runtime/admin_aws_runtime.py`
- `MyCiteV2/instances/_shared/runtime/runtime_platform.py`
- `MyCiteV2/instances/_shared/portal_host/app.py`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell.js` (if new region kinds or control wiring)
- `MyCiteV2/docs/contracts/shell_region_kinds.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/` (new slice doc)
- `MyCiteV2/packages/modules/cross_domain/` (onboarding / provision semantics)
- `MyCiteV2/packages/ports/` and `MyCiteV2/packages/adapters/` (AWS IO seams)
- `MyCiteV2/packages/sandboxes/tool/` (optional staging helpers only)
- `MyCiteV2/tests/integration/`, `MyCiteV2/tests/architecture/`, `MyCiteV2/tests/unit/`

## 10. Next task

See `tasks/T-010-v2-aws-csm-onboarding-workflow.yaml`.
