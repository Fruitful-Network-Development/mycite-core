# FND-EBI Cross-Domain Module

Composes profile-led hosted site visibility into a bounded read-only service
surface for the V2 admin portal.

This module does not own raw filesystem authority. It reuses one explicit
read-only port and adds only:

- selected hosted-profile resolution
- overview, traffic, events, errors/noise, and file-state projection
- warnings and selection logic for one focused service profile at a time
