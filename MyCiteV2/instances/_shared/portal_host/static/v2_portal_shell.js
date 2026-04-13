/**
 * Compatibility wrapper retained so health checks, existing contracts, and
 * one-release deployment overlap can keep referencing the historical bundle
 * path while the real shell now loads from ordered static scripts.
 */
(function () {
  window.__MYCITE_V2_SHELL_COMPAT_BUNDLE_PRESENT = true;
})();
