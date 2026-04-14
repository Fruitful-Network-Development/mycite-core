/**
 * Detects incomplete canonical-shell hydration and reports a distinct fatal
 * taxonomy for bundle-delivery vs shell POST failure.
 */
(function () {
  function showFatal(message, fatalClass) {
    if (window.__MYCITE_V2_SHELL_FATAL_SHOWN) {
      return;
    }
    if (typeof window.__MYCITE_V2_SHOW_FATAL === "function") {
      window.__MYCITE_V2_SHOW_FATAL(message, fatalClass);
      return;
    }
    if (typeof window.__MYCITE_V2_PATCH_FATAL_STATE === "function") {
      window.__MYCITE_V2_PATCH_FATAL_STATE(message, fatalClass);
      return;
    }
    var body = document.body || document.documentElement;
    if (body) {
      body.setAttribute("data-shell-boot-state", "fatal");
      body.setAttribute("data-shell-fatal-class", fatalClass || "shell_post_failed");
    }
  }

  function startWatchdog() {
    var body = document.body || document.documentElement;
    var timeoutMs = Number((body && body.getAttribute("data-shell-watchdog-timeout-ms")) || 1800);
    if (!isFinite(timeoutMs) || timeoutMs < 250) {
      timeoutMs = 1800;
    }
    window.setTimeout(function () {
      if (window.__MYCITE_V2_SHELL_HYDRATED || window.__MYCITE_V2_SHELL_FATAL_SHOWN) {
        return;
      }
      if (!window.__MYCITE_V2_SHELL_ENTRY_LOADED || !window.__MYCITE_V2_SHELL_INTERNALS_READY || !window.__MYCITE_V2_SHELL_CORE_LOADED) {
        showFatal("The portal shell bundle did not load or did not execute.", "bundle_not_loaded");
        return;
      }
      showFatal("The portal shell did not finish hydrating. The shell POST may have failed.", "shell_post_failed");
    }, timeoutMs);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startWatchdog, { once: true });
  } else {
    startWatchdog();
  }
})();
