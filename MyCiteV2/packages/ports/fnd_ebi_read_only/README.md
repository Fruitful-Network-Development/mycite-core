# FND-EBI Read-Only Port

This port defines the bounded read contract for the first V2 `FND-EBI`
service-tool slice.

The port owns:

- request fields for selecting one hosted profile/domain view
- JSON-safe source payload exchange between adapters and the semantic owner
- read-only only behavior

The port does not own:

- filesystem path derivation rules
- analytics parsing logic
- runtime composition or shell behavior
