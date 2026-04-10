# ADR 0012: Post-AWS Tool Platform Stabilization

## Status

Accepted

## Context

Admin Band 0, AWS read-only, and AWS narrow-write proved the admin shell, registry, runtime envelope, read-only pattern, bounded-write pattern, audit emission, and read-after-write confirmation. Without stabilizing those into shared contracts, future tools would be likely to re-solve launch policy and runtime envelopes differently.

## Decision

The post-AWS shared platform is fixed around:

- shell-owned `AdminToolRegistryEntry` descriptors
- static runtime entrypoint descriptors in `instances/_shared/runtime/runtime_platform.py`
- shared admin runtime envelope construction
- read-only and bounded-write slice patterns derived from AWS
- v2 admin cutover through the shell-owned admin entry and registry, not route parity with v1

## Consequences

- Future tools add one descriptor, one runtime descriptor, one seam, one adapter family when needed, one runtime entrypoint, and one test/gate set.
- Tools cannot self-register, scan packages, or own launch legality.
- Runtime remains composition-only.
- Maps is the next allowed tool track after this platform pass, but Maps semantics remain outside this decision.
