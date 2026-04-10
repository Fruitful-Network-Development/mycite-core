# Read-Only And Bounded-Write Patterns

Authority: [../../authority_stack.md](../../authority_stack.md)

AWS is the reference implementation for the two approved post-AWS tool patterns.

## Read-only pattern

Reference slice: `admin_band1.aws_read_only_surface`

Required pieces:

- one semantic owner under `packages/modules/cross_domain/` or `packages/modules/domains/`
- one narrow read-only port
- one adapter family if outward data is needed
- one runtime entrypoint
- one shell-owned registry descriptor
- no write methods
- no local-audit write emission unless the slice explicitly records a read-access audit requirement

## Bounded-write pattern

Reference slice: `admin_band2.aws_narrow_write_surface`

Required pieces:

- one semantic owner for allowed field policy
- one narrow write port
- one adapter family
- one runtime entrypoint
- one shell-owned registry descriptor
- explicit writable field set
- read-after-write confirmation
- accepted-write local-audit emission
- rollback or manual recovery documentation before exposure

## Ownership split

- semantic owner defines allowed fields and normalization
- port defines the contract only
- adapter performs outward read/write mechanics only
- local audit emits accepted-write records
- runtime composes the flow only
- shell owns launch legality

## Forbidden pattern drift

- no broad provider-admin control plane
- no raw secret writes
- no manual dispatch workflow by convenience
- no adapter-owned allowed field set
- no runtime-owned semantic validation
- no write behavior through a read-only seam
