# Portal Shell Contract

The repository owns one neutral portal shell contract.

## Shell Model

- One request schema: `mycite.v2.portal.shell.request.v1`
- One shell state schema: `mycite.v2.portal.shell.state.v1`
- One shell composition schema: `mycite.v2.portal.shell.composition.v1`
- One runtime envelope schema: `mycite.v2.portal.runtime.envelope.v1`
- One entrypoint descriptor schema: `mycite.v2.portal.runtime_entrypoint_descriptor.v1`

## Root Surfaces

- `SYSTEM`
- `NETWORK`
- `UTILITIES`

Every visible page belongs under one of those roots.

## Tool Ownership

- Tool work pages are `SYSTEM` child surfaces.
- Tool configuration, enabling, exposure, and integration state belong under `UTILITIES`.
- A service tool may remain visible while `operational=false` when an external integration is missing.
