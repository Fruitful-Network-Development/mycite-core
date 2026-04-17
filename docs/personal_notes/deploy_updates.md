Not currently in this repo. There isn’t an existing deploy script checked in.

You can use this as your repeatable deploy script:

```bash
#!/usr/bin/env bash
set -euo pipefail

# restart both portal services
sudo systemctl restart mycite-v2-fnd-portal.service mycite-v2-tff-portal.service

# verify services are active
systemctl is-active mycite-v2-fnd-portal.service mycite-v2-tff-portal.service

# health checks
curl -fsS http://127.0.0.1:6101/portal/healthz >/dev/null
curl -fsS http://127.0.0.1:6203/portal/healthz >/dev/null

echo "Deploy restart + health checks passed."
```

If you want, I can add this as a tracked file (for example `scripts/deploy_portals.sh`) and make it executable.