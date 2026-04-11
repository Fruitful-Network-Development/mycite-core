# Runtime Envelope And Launch Results

Authority: [../../authority_stack.md](../../authority_stack.md)

The shared admin runtime envelope helper is `build_admin_runtime_envelope` in `instances/_shared/runtime/runtime_platform.py`.

## Fixed envelope keys

Every admin runtime response must contain:

- `schema`
- `admin_band`
- `exposure_status`
- `tenant_scope`
- `requested_slice_id`
- `slice_id`
- `entrypoint_id`
- `read_write_posture`
- `shell_state`
- `surface_payload`
- `warnings`
- `error`

## Denied and unavailable results

Denied, gated, and unavailable results must:

- preserve the same envelope keys
- set `surface_payload` to `None`
- set `error.code` and `error.message`
- put user-facing denial text in `warnings`
- retain the shell launch decision in `shell_state`

## Successful results

Successful tool results must:

- return one surface payload matching the cataloged surface schema
- include no provider secrets
- include no filesystem or instance paths
- keep runtime metadata outside tool semantics

## Forbidden runtime drift

- no alternate error envelope for convenience
- no exception payload containing provider internals
- no direct host route as a launch result
- no hidden write path in a read-only envelope
