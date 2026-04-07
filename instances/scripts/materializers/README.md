# Instance Materializers

`instances/materializers/` is the canonical home for offline instance capture,
materialization, and state-alignment logic.

Current transitional seam:

- `instances/scripts/portal_build.py` remains the CLI entrypoint used by existing
  docs and tests.
- `instances/scripts/correct_portal_sandbox_contract.py` remains the corrective
  migration entrypoint.

Both scripts now resolve declarations and canonical state roots through
`instances.scripts.declarations` and `mycite_core.runtime_host.state_roots` so the next move
can relocate implementation here without changing the runtime contract again.
