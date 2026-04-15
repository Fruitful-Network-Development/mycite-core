# Deployed Snapshots

`deployed/` preserves archived instance snapshots that were moved out of the
retired split-runtime tree.

- These files are not live runtime source.
- Live state is read from `/srv/mycite-state/instances/<instance_id>/`.
- Snapshot metadata must not point back at removed runtime trees.
- Snapshot datum files may be retained as-is unless metadata cleanup is needed.
