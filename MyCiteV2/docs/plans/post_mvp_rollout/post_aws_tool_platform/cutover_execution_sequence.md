# Cutover Execution Sequence

Authority: [../../authority_stack.md](../../authority_stack.md)

This is the shortest safe sequence for moving from tested V2 admin runtime to live `/portal` use.

## Step 1: Lock The Isolation Boundary

- Keep `MyCiteV1/` and `MyCiteV2/` as the only code roots.
- Do not recreate root compatibility symlinks.
- Keep live V1 services restartable through direct `MyCiteV1` paths until the V2 bridge or host replaces them.

Done when:

- root-level legacy code directories are absent
- systemd no longer relies on root-level repo compatibility paths

## Step 2: Implement The Deployment Bridge

Use [deployment_bridge_contract.md](deployment_bridge_contract.md).

Preferred path for fewest prompts:

- implement Shape B first
- mount a tiny V1 host bridge to cataloged V2 runtime entrypoints
- keep all V2 decisions in V2 runtime/catalog docs

Done when:

- bridge tests pass
- V2 Admin Band 0 and AWS regression tests pass
- nginx can route to the bridge through the existing `/portal` upstream

Status: done for the internal bridge route surface. The V1 host now mounts explicit V2 bridge routes for shell entry, AWS read-only, AWS narrow-write, and bridge health.

## Step 3: Implement Live State Mapping

Use [live_state_authority_and_mapping.md](live_state_authority_and_mapping.md).

Preferred path:

- derive AWS read-only state from canonical live AWS profile JSON first
- expose `admin.aws.read_only`
- only then enable `admin.aws.narrow_write` against canonical live profile JSON with read-after-write and audit

Done when:

- no V2 shadow state exists
- read-after-write proves the canonical live artifact changed
- denied writes leave live state unchanged

Status: done for the FND/TFF bridge configuration. `MYCITE_V2_AWS_STATUS_FILE` points at canonical live `aws-csm.*.json` profiles, and the V2 live AWS profile adapter performs read-only mapping plus narrow-write read-after-write against that same artifact.

## Step 4: Gate Internal Exposure

Expose `admin.shell_entry` internally first.

Done when:

- internal shell entry returns the V2 runtime envelope
- unknown slices are denied
- non-internal audiences are denied for Admin Band 0
- bridge payloads expose no secrets or instance paths

## Step 5: Gate Trusted-Tenant AWS Read-Only

Expose `admin.aws.read_only` to the trusted-tenant path only after Step 4 passes.

Done when:

- trusted tenant scope receives only the approved AWS read-only fields
- no write endpoint is reachable through the read-only route
- no secret-bearing fields leak

## Step 6: Gate AWS Narrow Write

Expose `admin.aws.narrow_write` only after read-only is stable.

Done when:

- writable field set is still only `selected_verified_sender`
- accepted write emits local audit
- read-after-write confirms the same live artifact
- rollback or manual recovery reference is present

## Step 7: Update Deployment Claim

Only after Steps 1-6 pass, update:

- [v2_admin_cutover_readiness.md](v2_admin_cutover_readiness.md)
- [README.md](README.md)
- the matching slice registry entry

The claim may then say V2 is deployed for the admin shell and AWS slices. It must not claim Maps, AGRO-ERP, sandbox, or broader portal parity.
