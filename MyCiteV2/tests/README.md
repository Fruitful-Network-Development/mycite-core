# Tests

Authority: [../docs/plans/v2-authority_stack.md](../docs/plans/v2-authority_stack.md)

`tests/` is organized by boundary loop rather than by implementation
convenience.

Historical bridge-era coverage remains in the suite, but it is opt-in only.
Set `MYCITE_ENABLE_HISTORICAL_BRIDGE_TESTS=1` when you need to replay the
quarantined V1-host bridge evidence.
