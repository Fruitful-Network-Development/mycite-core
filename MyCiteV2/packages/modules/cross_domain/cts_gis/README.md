# CTS-GIS Cross-Domain Module

Composes the authoritative datum-recognition projection into a bounded
CTS-GIS surface for the V2 admin portal.

This module does not own datum authority. It reuses the authoritative datum
document seam plus datum recognition and adds only:

- SAMRAS attention/intention mediation over profile rows
- intra-document linkage from profile rows to geometry rows
- HOPS-backed geographic projection
- title and SAMRAS display overlays
- CTS-GIS-specific selection and lens state
- staged YAML/JSON insert validation, preview, and SQL-backed apply flows
