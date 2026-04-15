# Tool sandbox (`packages.sandboxes.tool`)

Orchestration-only helpers for tool workflows. Domain semantics stay in
`packages/modules`; adapters stay thin per ADR 0006.

## AWS-CSM staging

- `aws_csm_staging.validate_staged_aws_csm_profile_path` — ensures a path is a
  readable file whose JSON declares schema `mycite.service_tool.aws_csm.profile.v1`
  (via `is_live_aws_profile_file`).

Runtime and portal configuration for **which** path to use lives in host config
and the unified AWS-CSM runtime under `instances/_shared/runtime/portal_aws_runtime.py`, not here.
