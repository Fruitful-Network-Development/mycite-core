# Maps Cross-Domain Module

Composes the authoritative datum-recognition projection into a bounded
read-only maps surface for the V2 admin portal.

This module does not own datum authority. It reuses the authoritative datum
document seam plus datum recognition and adds only:

- HOPS-backed geographic projection
- title and SAMRAS display overlays
- maps-specific selection and lens state
