# Tests

Authority: [../docs/README.md](../docs/README.md)

`tests/` is organized by boundary loop rather than by implementation
convenience.

The suite protects one live shell model:

- `/portal` redirects to `/portal/system`
- root surfaces are `SYSTEM`, `NETWORK`, and `UTILITIES`
- no split-instance public ingress remains in the active repo
- no retired bridge or compatibility package remains in the active repo
