"""ext_connect — operator-surface payload builder (dissolved).

The Connect operator extension surface (``_build_connect_extension_payload``)
was removed when the FND-CSM operator apparatus was dissolved
(portal-tool-overlay-restructure). The live Connect-form ingest + SES
forwarding logic lives in the portal host
(``instances/_shared/portal_host/app.py``); nothing imports from this module
anymore. Kept as a placeholder so the package layout stays stable.
"""
