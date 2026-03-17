# Compose File Tree

- Source root: `/srv/compose`
- Generated (UTC): 2026-03-17 20:37:26Z
- Generator: `python3` deterministic path walk (sorted), excluding `*.svg` files

```text
/srv/compose
├── platform
│   ├── docs
│   │   ├── design_manifest-v4.json
│   │   └── development-manifest.md
│   ├── keycloak
│   │   ├── realm
│   │   │   └── README.md
│   │   └── Dockerfile
│   ├── platform-schema
│   │   ├── analytics_init.sql
│   │   ├── aws_config.schema.v1.json
│   │   ├── aws_module_init.sql
│   │   ├── fnd_init.sql
│   │   ├── mss_init.sql
│   │   ├── mss_ui_init.sql
│   │   ├── newsletter_init.sql
│   │   ├── paypal_init.sql
│   │   └── platform_init.sql
│   ├── scripts
│   │   ├── auth_health_gate.sh
│   │   └── restart
│   ├── .dockerignore
│   ├── .env
│   ├── README.md
│   ├── docker-compose.yml
│   ├── rsync.filter
│   ├── smoke_core.sh
│   └── smoke_oidc.sh
├── portals
│   ├── fnd_proxy
│   │   ├── __pycache__
│   │   │   └── app.cpython-313.pyc
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   └── requirements.txt
│   ├── host_control_api
│   │   ├── __pycache__
│   │   │   └── server.cpython-313.pyc
│   │   └── server.py
│   ├── scripts
│   │   ├── legacy-usage-report
│   │   ├── logs-fnd
│   │   ├── migrate_legacy_admin_state.sh
│   │   ├── restart-fnd
│   │   ├── seed_fnd_state.sh
│   │   ├── seed_portal_state.sh
│   │   └── status
│   ├── state
│   │   ├── aws_proxy
│   │   │   ├── tenants
│   │   │   │   └── 1.json
│   │   │   ├── actions.ndjson
│   │   │   ├── fnd.json
│   │   │   └── provision_requests.ndjson
│   │   ├── example_portal
│   │   │   ├── data
│   │   │   │   ├── cache
│   │   │   │   │   └── external_resources
│   │   │   │   ├── presentation
│   │   │   │   │   └── datum_icons.json
│   │   │   │   ├── anthology.json
│   │   │   │   └── anthology.seed-from-tff-workshop-20260313T000000Z.json
│   │   │   ├── private
│   │   │   │   ├── daemon_state
│   │   │   │   │   └── data_workspace.json
│   │   │   │   ├── network
│   │   │   │   │   ├── progeny
│   │   │   │   │   ├── request_log
│   │   │   │   │   │   └── types
│   │   │   │   │   └── hosted.json
│   │   │   │   ├── utilities
│   │   │   │   │   ├── peripherals
│   │   │   │   │   └── vault
│   │   │   │   │       └── keypass_inventory.json
│   │   │   │   ├── config.json
│   │   │   │   ├── mycite-config-0-0-0-0-0-0-0-0-0-0.json
│   │   │   │   └── tools.manifest.json
│   │   │   └── public
│   │   │       ├── fnd-0-0-0-0-0-0-0-0-0-0.json
│   │   │       └── msn-0-0-0-0-0-0-0-0-0-0.json
│   │   ├── fnd_portal
│   │   │   ├── data
│   │   │   │   ├── cache
│   │   │   │   │   ├── contacts
│   │   │   │   │   ├── external_resources
│   │   │   │   │   └── tenant
│   │   │   │   ├── presentation
│   │   │   │   │   └── datum_icons.json
│   │   │   │   ├── sandbox
│   │   │   │   │   └── resources
│   │   │   │   │       ├── msn.samras.5-0-2.json
│   │   │   │   │       └── txa.samras.5-0-1.json
│   │   │   │   ├── anthology.json
│   │   │   │   └── anthology.pre-sandbox-extract-20260316T221215Z.json
│   │   │   ├── private
│   │   │   │   ├── admin_runtime
│   │   │   │   │   ├── aws
│   │   │   │   │   │   ├── tenants
│   │   │   │   │   │   │   └── 1.json
│   │   │   │   │   │   ├── actions.ndjson
│   │   │   │   │   │   ├── fnd.json
│   │   │   │   │   │   └── provision_requests.ndjson
│   │   │   │   │   └── paypal
│   │   │   │   │       ├── tenants
│   │   │   │   │       │   ├── 1.json
│   │   │   │   │       │   └── demo-tenant.json
│   │   │   │   │       ├── actions.ndjson
│   │   │   │   │       ├── fnd.json
│   │   │   │   │       ├── orders.ndjson
│   │   │   │   │       └── profile_sync.ndjson
│   │   │   │   ├── daemon_state
│   │   │   │   │   └── data_workspace.json
│   │   │   │   ├── network
│   │   │   │   │   ├── aliases
│   │   │   │   │   │   └── alias-3-2-3-17-77-2-6-3-1-6-3-2-3-17-77-1-6-4-1-4-member.json
│   │   │   │   │   ├── contracts
│   │   │   │   │   │   ├── aliases_contracts
│   │   │   │   │   │   ├── p2p_contracts
│   │   │   │   │   │   ├── progeny_contracts
│   │   │   │   │   │   ├── contract-contract-fnd-tff-member-001.json
│   │   │   │   │   │   └── msn-3-2-3-17-77-1-6-4-1-4.contract-3-2-3-17-77-2-6-3-1-6.json
│   │   │   │   │   ├── progeny
│   │   │   │   │   │   └── msn-3-2-3-17-77-1-6-4-1-4.member-3-2-3-17-77-2-6-3-1-6.json
│   │   │   │   │   ├── request_log
│   │   │   │   │   │   ├── types
│   │   │   │   │   │   │   ├── contract_proposal.confirmed.ndjson
│   │   │   │   │   │   │   └── contract_proposal.ndjson
│   │   │   │   │   │   └── request_log.ndjson
│   │   │   │   │   └── hosted.json
│   │   │   │   ├── progeny
│   │   │   │   │   └── tenant
│   │   │   │   ├── utilities
│   │   │   │   │   ├── peripherals
│   │   │   │   │   ├── tools
│   │   │   │   │   └── vault
│   │   │   │   │       ├── contracts
│   │   │   │   │       ├── keys
│   │   │   │   │       │   └── 3-2-3-17-77-1-6-4-1-4_private.pem
│   │   │   │   │       └── keypass_inventory.json
│   │   │   │   ├── config.json
│   │   │   │   ├── identity_map.json
│   │   │   │   ├── mycite-config-3-2-3-17-77-1-6-4-1-4.json
│   │   │   │   └── tools.manifest.json
│   │   │   └── public
│   │   │       ├── fnd-3-2-3-17-77-1-6-4-1-4.json
│   │   │       └── msn-3-2-3-17-77-1-6-4-1-4.json
│   │   ├── paypal_proxy
│   │   │   ├── tenants
│   │   │   │   └── 1.json
│   │   │   ├── actions.ndjson
│   │   │   ├── fnd.json
│   │   │   ├── orders.ndjson
│   │   │   └── profile_sync.ndjson
│   │   ├── tff_portal
│   │   │   ├── data
│   │   │   │   ├── cache
│   │   │   │   │   └── external_resources
│   │   │   │   ├── presentation
│   │   │   │   │   └── datum_icons.json
│   │   │   │   ├── anthology.backup-20260312T232758Z.json
│   │   │   │   └── anthology.json
│   │   │   ├── private
│   │   │   │   ├── contracts
│   │   │   │   │   └── .gitkeep
│   │   │   │   ├── daemon_state
│   │   │   │   │   └── data_workspace.json
│   │   │   │   ├── network
│   │   │   │   │   ├── aliases
│   │   │   │   │   │   ├── .gitkeep
│   │   │   │   │   │   └── alias-3-2-3-17-77-1-6-4-1-4-3-2-3-17-77-2-6-3-1-6-member.json
│   │   │   │   │   ├── contracts
│   │   │   │   │   │   ├── .gitkeep
│   │   │   │   │   │   ├── contract-contract-fnd-tff-member-001.json
│   │   │   │   │   │   └── msn-3-2-3-17-77-2-6-3-1-6.contract-3-2-3-17-77-1-6-4-1-4.json
│   │   │   │   │   ├── progeny
│   │   │   │   │   │   ├── msn-3-2-3-17-77-2-6-3-1-6.admin-3-2-3-17-77-2-6-3-1-1.json
│   │   │   │   │   │   └── msn-3-2-3-17-77-2-6-3-1-6.member-3-2-3-17-77-2-6-3-1-1.json
│   │   │   │   │   ├── request_log
│   │   │   │   │   │   ├── types
│   │   │   │   │   │   │   ├── .gitkeep
│   │   │   │   │   │   │   ├── contract_proposal.confirmed.ndjson
│   │   │   │   │   │   │   ├── contract_proposal.delivery_failed.ndjson
│   │   │   │   │   │   │   └── contract_proposal.ndjson
│   │   │   │   │   │   ├── .gitkeep
│   │   │   │   │   │   ├── 3-2-3-17-77-2-6-3-1-6.ndjson
│   │   │   │   │   │   └── request_log.ndjson
│   │   │   │   │   └── hosted.json
│   │   │   │   ├── progeny
│   │   │   │   │   └── internal
│   │   │   │   ├── request_log
│   │   │   │   │   └── 3-2-3-17-77-2-6-3-1-6.ndjson
│   │   │   │   ├── tools
│   │   │   │   │   └── agro_erp.spec.json
│   │   │   │   ├── utilities
│   │   │   │   │   ├── peripherals
│   │   │   │   │   │   └── .gitkeep
│   │   │   │   │   ├── tools
│   │   │   │   │   │   └── .gitkeep
│   │   │   │   │   └── vault
│   │   │   │   │       ├── keys
│   │   │   │   │       │   └── 3-2-3-17-77-2-6-3-1-6_private.pem
│   │   │   │   │       └── keypass_inventory.json
│   │   │   │   ├── config.json
│   │   │   │   ├── mycite-config-3-2-3-17-77-2-6-3-1-6.json
│   │   │   │   └── tools.manifest.json
│   │   │   └── public
│   │   │       ├── fnd-3-2-3-17-77-2-6-3-1-6.json
│   │   │       └── msn-3-2-3-17-77-2-6-3-1-6.json
│   │   └── portal_instances.json
│   ├── .env
│   ├── .env.example
│   ├── .gitignore
│   ├── README.md
│   └── docker-compose.yml
└── README.md
```
