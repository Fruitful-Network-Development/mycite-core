"""ext_newsletter — operator-surface payload builder (dissolved).

The newsletter operator extension surface
(``_build_newsletter_extension_payload`` plus its add-subscriber /
set-sender / per-row action form helpers) was removed when the FND-CSM
operator apparatus was dissolved (portal-tool-overlay-restructure). The live
newsletter admin/ingest routes (``/__fnd/newsletter/admin/*`` and
``/__fnd/newsletter/subscribe``) live in the portal host
(``instances/_shared/portal_host/app.py``); nothing imports from this module
anymore. Kept as a placeholder so the package layout stays stable.
"""
