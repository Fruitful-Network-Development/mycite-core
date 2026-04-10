## Prompt:
Address and solve each and every one of these Findings you've found, appliying hard cuts to drift logic and documentation.
Proceed with alignment for each of the areas you listed above.
If operational decisions come up, refer to the file [tool_dev.md](repo/mycite-core/docs/plans/tool_dev.md) , and also noting that the main goal is the surface of interfacing. (So UI shells matter more about keeping track of whats legal, keeping a hyphae mss form datum list, etc. Then those can be exposed to a UI in standard ways that a UI can attach its self to for use. Similarly tools are hosted by the portal so they must interface with a tool surface that tools are developed to attach to). 
- That last part is a precedent to refer to while navigating and addressing each of the findings and alignment areas.

---

## Output:

**Aligned**
I applied the hard cuts across code, docs, tests, live state, and runtime wrappers.

- The authority model is now explicit in [tool_dev.md](/srv/repo/mycite-core/docs/plans/tool_dev.md), [tool_development_guide.md](/srv/repo/mycite-core/docs/modularity/tool_development_guide.md), [ownership-boundary.md](/srv/repo/mycite-core/docs/ownership-boundary.md), and [wiki README](/srv/repo/mycite-core/docs/wiki/README.md): `private/config.json` is exposure/utility selection only, `private/utilities/tools/<tool>/` is non-datum utility state only, `data/sandbox/<tool>/` is tool datum authority, and `data/payloads/` is payload authority.
- I finished the remaining runtime boundary cuts in [service_tools.py](/srv/repo/mycite-core/instances/_shared/portal/application/service_tools.py), [time_address_schema.py](/srv/repo/mycite-core/instances/_shared/portal/application/time_address_schema.py), [view_model.py](/srv/repo/mycite-core/mycite_core/state_machine/view_model.py), [admin_integrations.py](/srv/repo/mycite-core/instances/_shared/runtime/flavors/fnd/portal/api/admin_integrations.py), and [newsletter_admin.py](/srv/repo/mycite-core/instances/_shared/runtime/flavors/fnd/portal/api/newsletter_admin.py).
- I swept the stale `portals/...` path language out of the active docs/tests/scripts and updated the affected assertions in [test_system_page_composition.py](/srv/repo/mycite-core/tests/test_system_page_composition.py), [test_newsletter_admin_api.py](/srv/repo/mycite-core/tests/test_newsletter_admin_api.py), and [test_anthology_registry_overlay.py](/srv/repo/mycite-core/tests/test_anthology_registry_overlay.py).
- I removed stale repo-side mutable PayPal state from the runtime tree and the old deployed `admin_runtime/paypal` snapshot. The deployed mirror now carries utility collections under [instances/deployed/fnd/private/utilities/tools](/srv/repo/mycite-core/instances/deployed/fnd/private/utilities/tools) and an explicit empty tools root for [TFF](/srv/repo/mycite-core/instances/deployed/tff/private/utilities/tools).

**Live State**
The FND live instance is cleaned up and matches the intended surface better now.

- [live FND config](/srv/mycite-state/instances/fnd/private/config.json) no longer exposes `newsletter-admin`.
- [newsletter-admin live root](/srv/mycite-state/instances/fnd/private/utilities/tools/newsletter-admin) now keeps only visible profile JSON plus `runtime_secrets.json`; the hidden dotfiles and retired standalone manifest/spec are gone.
- [aws-csm live root](/srv/mycite-state/instances/fnd/private/utilities/tools/aws-csm) now uses visible `smtp_provision.lock` instead of a hidden lockfile.
- Empty live `code/` dirs and the empty `calendar/` tool dir were removed.
- The stale `/srv/compose/portals` copies I could safely cut are gone: the old `host_control_api` copy, the backup tgz files, the compose yml backup, and the retired `state/paypal_proxy` shim. What remains under `/srv/compose/portals` is the still-used `.env`, `docker-compose.yml`, README, and helper scripts.

**Runtime + Verification**
The operational findings are resolved.

- [paypal-proxy.service](/srv/repo/srv-infra/systemd/paypal-proxy.service) now points at `packages/tools/paypal_csm/backend`, and the live unit was updated.
- `fnd-portal.service`, `tff-portal.service`, and `paypal-proxy.service` are all active under systemd now, with `200` responses on `127.0.0.1:5101`, `:5203`, and `:5102`.
- Focused verification passed: `python3 -m unittest ...` ran 92 tests with `OK (skipped=16)`.

The one intentional residual is `/srv/compose/portals/.env` plus the helper scripts around it. Current systemd/control-api wiring still reads that env surface, so I left it in place rather than inventing a second migration in the same turn.