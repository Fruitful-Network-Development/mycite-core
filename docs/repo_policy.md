# mycite-core Repo Policy

## Commit allowed

- Portal framework source code and templates
- Tool runtime modules and shared UI/tool scripts
- Canonical framework documentation
- Non-secret example/config scaffolding

## Never commit

- Live secrets, `.env` values, keys/certs
- Runtime state (`state/`, request-log ndjson, queue/cache artifacts)
- Vault content or tenant-specific operational credentials
- Local virtualenvs and machine-specific cache files

## Practical rules

- Keep runtime/provisioning concerns in `srv-infra`
- Keep product/framework intent and API behavior in `mycite-core`
- If a file contains environment-specific host data, keep it out of this repo
