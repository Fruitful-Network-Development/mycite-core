# SAMRAS

This package owns the pure structural SAMRAS contract in V2:

- canonical encode/decode for breadth-first child-count magnitudes
- legacy fixed-header and numeric-hyphen migration decode paths
- address derivation and round-trip validation
- structure-only semantics without CTS-GIS-specific presentation logic

CTS-GIS consumes this package as the authority for tree shape. Row overlays remain secondary label evidence.
