# FND-EBI Donations Cross-Domain Module

Composes donations seam read-only surface for the FND-EBI portal.

Does not own filesystem authority. Uses one explicit donations read-only port.

The service selects the appropriate profile by `selected_domain` and
projects a donations surface dict for consumption by the portal runtime.
