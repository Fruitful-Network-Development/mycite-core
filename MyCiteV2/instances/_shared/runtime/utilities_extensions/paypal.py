"""ext_paypal — operator-surface payload builder (dissolved).

The PayPal operator extension surface (``_build_paypal_extension_payload``
plus its ``_export_action`` helper) was removed when the FND-CSM operator
apparatus was dissolved (portal-tool-overlay-restructure). The live PayPal
admin/ingest logic — order create/capture, webhook verification, and the
``/__fnd/paypal/admin/export`` CSV route — lives in the portal host
(``instances/_shared/portal_host/app.py``); nothing imports from this module
anymore. Kept as a placeholder so the package layout stays stable.
"""
