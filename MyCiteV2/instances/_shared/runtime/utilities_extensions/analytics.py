"""ext_analytics — operator-surface payload builder (dissolved).

The analytics operator extension surface
(``_build_analytics_extension_payload``) was removed when the FND-CSM
operator apparatus was dissolved (portal-tool-overlay-restructure). Derived
analytics insights are still produced by
``MyCiteV2.packages.core.analytics.derivations`` (read by the dashboard and
the ``/__fnd/analytics/*`` routes in the portal host); nothing imports from
this module anymore. Kept as a placeholder so the package layout stays stable.
"""
