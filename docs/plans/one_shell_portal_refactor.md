# One-Shell Portal Refactor

This repository now implements a single portal shell rooted in:

- `SYSTEM`
- `NETWORK`
- `UTILITIES`

Implementation outcomes:

- tenant-only route families removed
- split shell/runtime envelope families removed
- one neutral terminology set adopted
- service tools rendered by capability and configuration, not by portal identity
- FND peripheral routing treated as shared infrastructure capability
