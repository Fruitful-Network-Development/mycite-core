# Benchmark Fixtures

Deterministic benchmark fixtures used by `scripts/benchmarks/*`.

## Files

- `portal_shell_fixture_v1.json`
- `cts_gis_projection_fixture_v1.json`
- `interaction_journeys_v1.json`

## Notes

- Fixtures are intentionally stable and synthetic for repeatable baseline checks.
- Real-world scenario expansions can add `*_v2.json` files without mutating v1 fixtures.
- Update `CHECKSUMS.sha256` when fixture contents change.

