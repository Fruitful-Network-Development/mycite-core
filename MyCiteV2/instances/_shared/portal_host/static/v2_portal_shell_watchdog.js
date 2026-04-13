/**
 * Detects missing or non-executing shell bundles and surfaces a visible fatal
 * state in the template instead of leaving the bootstrap placeholder stranded.
 */
(function () {
  function patchFatalState(message) {
    var body = document.body || document.documentElement;
    if (body) {
      body.setAttribute("data-shell-boot-state", "fatal");
    }
    var placeholder = document.getElementById("v2-control-panel-placeholder");
    if (placeholder) {
      placeholder.textContent = message;
    }
    var workbenchBody = document.getElementById("v2-workbench-body");
    if (workbenchBody) {
      workbenchBody.innerHTML =
        '<section class="v2-card" style="max-width:720px"><h3>Shell hydration failed</h3><p>' +
        String(message)
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;") +
        "</p></section>";
    }
    window.__MYCITE_V2_SHELL_FATAL_SHOWN = true;
  }

  function showFatal(message) {
    if (window.__MYCITE_V2_SHELL_FATAL_SHOWN) {
      return;
    }
    if (typeof window.__MYCITE_V2_SHOW_FATAL === "function") {
      window.__MYCITE_V2_SHOW_FATAL(message);
      return;
    }
    patchFatalState(message);
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
      if (!window.__MYCITE_V2_SHELL_CORE_LOADED) {
        showFatal("The portal shell bundle did not load or did not execute.");
        return;
      }
      showFatal("The portal shell did not finish hydrating. The shell POST may have failed.");
    }, timeoutMs);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startWatchdog, { once: true });
  } else {
    startWatchdog();
  }
})();
