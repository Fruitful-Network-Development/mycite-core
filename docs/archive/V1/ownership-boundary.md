# Ownership Boundary

`mycite-core` is the canonical source of truth for portal application behavior.

It owns:

- portal Python application code;
- portal storage semantics and canonical filesystem contracts;
- sandbox, resource, reference, and migration logic;
- admin integration behavior;
- UI behavior and mediation behavior.

It does not own:

- host runtime topology;
- NGINX routing files;
- `systemd` units or compose orchestration as an authoritative app-definition surface;
- mutable runtime state under `/srv/mycite-state/instances/*`;
- retired compatibility copies or symlinks under `/srv/compose/portals/state/*`.

Operational rule:

- runtime state is a deployment product, not an authoring surface;
- schema or storage-model changes must land in `mycite-core` first, then be promoted through controlled migrations;
- hidden or duplicated state surfaces should be deleted once the canonical runtime path is updated;
- `srv-infra` may provide wrappers that invoke migration code against live state, but it must not define new portal data semantics.
