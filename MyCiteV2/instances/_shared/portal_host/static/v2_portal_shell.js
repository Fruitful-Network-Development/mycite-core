/**
 * Canonical V2 portal shell entrypoint.
 * Loads the internal shell modules in order and owns fatal handling for
 * internal bundle-delivery failures.
 */
(function () {
  var body = document.body || document.documentElement;
  var internalScripts = [
    "/portal/static/v2_portal_shell_region_renderers.js",
    "/portal/static/v2_portal_workbench_renderers.js",
    "/portal/static/v2_portal_inspector_renderers.js",
    "/portal/static/v2_portal_shell_core.js",
    "/portal/static/v2_portal_shell_watchdog.js",
  ];

  function setBootState(state) {
    if (!body) return;
    body.setAttribute("data-shell-boot-state", String(state || "").trim() || "template");
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function patchFatalState(message, fatalClass) {
    if (body) {
      body.setAttribute("data-shell-boot-state", "fatal");
      body.setAttribute("data-shell-fatal-class", fatalClass || "render_dispatch_failed");
    }
    var placeholder = document.getElementById("v2-control-panel-placeholder");
    if (placeholder) {
      placeholder.textContent = message;
    }
    var workbenchBody = document.getElementById("v2-workbench-body");
    if (workbenchBody) {
      workbenchBody.innerHTML =
        '<section class="v2-card" style="max-width:720px"><h3>Shell hydration failed</h3><p>' +
        escapeHtml(message) +
        "</p></section>";
    }
    window.__MYCITE_V2_SHELL_FATAL_SHOWN = true;
  }

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var script = document.createElement("script");
      script.src = src;
      script.async = false;
      script.onload = function () { resolve(src); };
      script.onerror = function () {
        reject(new Error("Failed to load " + src));
      };
      (document.head || document.documentElement).appendChild(script);
    });
  }

  window.__MYCITE_V2_SHELL_CANONICAL_ASSET = true;
  window.__MYCITE_V2_SHELL_ENTRY_LOADED = true;
  window.__MYCITE_V2_PATCH_FATAL_STATE = patchFatalState;
  setBootState("entry_loaded");

  internalScripts
    .reduce(function (chain, src) {
      return chain.then(function () {
        return loadScript(src);
      });
    }, Promise.resolve())
    .then(function () {
      window.__MYCITE_V2_SHELL_INTERNALS_READY = true;
      var currentState = body && body.getAttribute("data-shell-boot-state");
      if (
        !window.__MYCITE_V2_SHELL_FATAL_SHOWN &&
        (!currentState || currentState === "template" || currentState === "entry_loaded" || currentState === "core_loaded")
      ) {
        setBootState("bundle_loaded");
      }
    })
    .catch(function () {
      patchFatalState("The portal shell bundle did not load or did not execute.", "bundle_not_loaded");
    });
})();
