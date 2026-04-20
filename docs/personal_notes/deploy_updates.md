Done — you now have a single wrapper script for exactly this.

Created:
- `MyCiteV2/scripts/deploy.sh`

It supports:
- `./deploy.sh all` → sync deployed `data/public/private` + deploy portal code
- `./deploy.sh data` → sync deployed `data/public/private` only
- `./deploy.sh portal` (or `code`) → deploy portal code only
- `./deploy.sh -- ...` → pass raw options straight to `deploy_portal_update.sh`

I also made it executable and verified all three modes with dry-runs:
- `./deploy.sh all --instance fnd --dry-run`
- `./deploy.sh data --instance fnd --dry-run`
- `./deploy.sh portal --instance fnd --dry-run`

So for your normal need, you can now run:

- Update everything:
  - `cd /srv/repo/mycite-core/MyCiteV2/scripts`
  - `./deploy.sh all --instance fnd`

- Update deployed repo data only:
  - `./deploy.sh data --instance fnd`

- Update portal code only:
  - `./deploy.sh portal --instance fnd`

If you want, I can run a real `./deploy.sh all --instance fnd` now (non-dry-run).