/**
 * Compatibility wrapper retained so health checks, existing contracts, and
 * one-release deployment overlap can keep referencing the historical bundle
 * path while the real shell now loads from ordered static scripts.
 */
(function () {
  window.__MYCITE_V2_SHELL_COMPAT_BUNDLE_PRESENT = true;
  window.__MYCITE_V2_SHELL_COMPAT_RENDER_MARKERS = [
    "tenant_home_status",
    "operational_status",
    "audit_activity",
    "profile_basics_write",
  ];
})();
