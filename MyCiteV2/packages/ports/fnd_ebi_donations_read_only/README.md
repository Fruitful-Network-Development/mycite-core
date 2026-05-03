# FND-EBI Donations Read-Only Port

Bounded read contract for the FND-EBI donations seam.

The port owns:

- request/result/source exchange for donations log read operations
- read-only posture
- domain and tenant normalization at the contract boundary

The port does not own:

- filesystem path derivation
- record parsing logic
- runtime composition or shell behavior
