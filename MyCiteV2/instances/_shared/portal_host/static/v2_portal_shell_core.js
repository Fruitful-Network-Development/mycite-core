/**
 * V2 portal shell core.
 * Owns bootstrap, runtime POSTs, envelope validation, chrome application,
 * fatal-state taxonomy, and dispatch into dedicated renderer modules.
 */
(function () {
  var BODY_DATA = document.body || document.documentElement;
  var SHELL_URL = (BODY_DATA && BODY_DATA.getAttribute("data-shell-endpoint")) || "/portal/api/v2/admin/shell";
  var RUNTIME_ENVELOPE_SCHEMA =
    (BODY_DATA && BODY_DATA.getAttribute("data-runtime-envelope-schema")) ||
    "mycite.v2.admin.runtime.envelope.v1";
  var lastShellRequest = null;
  var lastComposition = null;
  var lastDirectView = null;
  var lastEnvelope = null;

  window.__MYCITE_V2_SHELL_CORE_LOADED = true;
  window.__MYCITE_V2_SHELL_HYDRATED = false;
  window.__MYCITE_V2_SHELL_FATAL_SHOWN = false;
  if (BODY_DATA) {
    BODY_DATA.setAttribute("data-shell-boot-state", "core_loaded");
  }

  function setBootState(state) {
    if (!BODY_DATA) return;
    BODY_DATA.setAttribute("data-shell-boot-state", String(state || "").trim() || "template");
  }

  function setFatalClass(fatalClass) {
    if (!BODY_DATA) return;
    if (fatalClass) {
      BODY_DATA.setAttribute("data-shell-fatal-class", fatalClass);
      return;
    }
    BODY_DATA.removeAttribute("data-shell-fatal-class");
  }

  function patchFatalState(message, fatalClass) {
    if (typeof window.__MYCITE_V2_PATCH_FATAL_STATE === "function") {
      window.__MYCITE_V2_PATCH_FATAL_STATE(message, fatalClass);
      return;
    }
    setBootState("fatal");
    setFatalClass(fatalClass || "render_dispatch_failed");
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

  function showFatal(message, fatalClass) {
    if (window.__MYCITE_V2_SHELL_FATAL_SHOWN) {
      return;
    }
    window.__MYCITE_V2_SHELL_HYDRATED = false;
    window.__MYCITE_V2_SHELL_FATAL_SHOWN = true;
    setBootState("fatal");
    setFatalClass(fatalClass || "render_dispatch_failed");
    patchFatalState(message, fatalClass || "render_dispatch_failed");
  }
  window.__MYCITE_V2_SHOW_FATAL = showFatal;

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function compactJson(value) {
    if (value == null) return "—";
    try {
      return JSON.stringify(value);
    } catch (_) {
      return String(value);
    }
  }

  function cloneRequestWithoutChrome(req) {
    var next = JSON.parse(JSON.stringify(req || {}));
    delete next.shell_chrome;
    return next;
  }

  function readBootstrapRequest() {
    var el = document.getElementById("v2-bootstrap-shell-request");
    if (!el || !el.textContent) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (_) {
      return null;
    }
  }

  function postJson(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(function (response) {
      return response.text().then(function (text) {
        var json = null;
        try {
          json = text ? JSON.parse(text) : null;
        } catch (_) {
          json = null;
        }
        return {
          ok: response.ok,
          status: response.status,
          json: json,
          bodySnippet: text ? text.slice(0, 280) : "",
        };
      });
    });
  }

  function postShellChrome(chromePartial) {
    if (lastDirectView && lastDirectView.url && lastDirectView.requestBody) {
      var nextDirect = JSON.parse(JSON.stringify(lastDirectView.requestBody || {}));
      nextDirect.shell_chrome = Object.assign({}, nextDirect.shell_chrome || {}, chromePartial);
      return loadRuntimeView(lastDirectView.url, nextDirect);
    }
    if (!lastShellRequest) return Promise.resolve();
    var next = JSON.parse(JSON.stringify(lastShellRequest));
    next.shell_chrome = Object.assign({}, next.shell_chrome || {}, chromePartial);
    return loadShell(next);
  }

  function applyChrome(comp) {
    var shell = qs(".ide-shell");
    var inspectorRegion = (comp.regions && comp.regions.inspector) || {};
    var workbench = qs(".ide-workbench");
    var inspector = document.getElementById("portalInspector");
    var inspectorContent = document.getElementById("portalInspectorContent");
    var menubarTitle = qs(".ide-menubar__pageTitle");
    var menubarSub = qs(".ide-menubar__pageSub");
    var pageheadTitle = qs("#v2-workbench-title");
    var pageheadSub = qs("#v2-workbench-subtitle");
    var workbenchRegion = (comp.regions && comp.regions.workbench) || {};
    if (!shell) return;

    shell.setAttribute("data-active-service", comp.active_service || "system");
    shell.setAttribute("data-shell-composition", comp.composition_mode || "system");
    shell.setAttribute("data-foreground-shell-region", comp.foreground_shell_region || "center-workbench");
    shell.setAttribute("data-control-panel-collapsed", comp.control_panel_collapsed ? "true" : "false");
    shell.setAttribute("data-inspector-collapsed", comp.inspector_collapsed ? "true" : "false");
    if (comp.active_tool_slice_id) {
      shell.setAttribute("data-active-mediate-tool", comp.active_tool_slice_id);
    } else {
      shell.removeAttribute("data-active-mediate-tool");
    }

    if (menubarTitle && comp.page_title) menubarTitle.textContent = comp.page_title;
    if (menubarSub && comp.page_subtitle != null) menubarSub.textContent = comp.page_subtitle;
    if (pageheadTitle && workbenchRegion.title) pageheadTitle.textContent = workbenchRegion.title;
    if (pageheadSub && workbenchRegion.subtitle != null) pageheadSub.textContent = workbenchRegion.subtitle;

    if (workbench) {
      workbench.setAttribute("data-active-service", comp.active_service || "system");
      workbench.setAttribute(
        "data-foreground-visible",
        comp.foreground_shell_region === "center-workbench" ? "true" : "false"
      );
      workbench.setAttribute("aria-hidden", comp.foreground_shell_region === "center-workbench" ? "false" : "true");
    }
    if (inspector) {
      inspector.setAttribute("data-primary-surface", inspectorRegion.primary_surface ? "true" : "false");
      inspector.setAttribute("data-surface-layout", inspectorRegion.layout_mode || "sidebar");
      inspector.setAttribute("aria-hidden", comp.inspector_collapsed ? "true" : "false");
    }
    if (inspectorContent) {
      inspectorContent.setAttribute(
        "data-interface-panel-active-root",
        (comp.composition_mode || "system") === "tool" ? "tool" : "system"
      );
    }
    if (BODY_DATA && BODY_DATA.classList) {
      BODY_DATA.classList.toggle(
        "portal-interface-panel-primary",
        comp.foreground_shell_region === "interface-panel" && !comp.inspector_collapsed
      );
    }
    document.dispatchEvent(
      new CustomEvent("mycite:shell:composition-changed", {
        detail: { composition: comp.composition_mode || "system" },
      })
    );
    if (window.PortalShell && typeof window.PortalShell.syncFromDom === "function") {
      window.PortalShell.syncFromDom();
    }
  }

  function buildRendererContext(region, target, extras) {
    return Object.assign({
      region: region,
      target: target,
      escapeHtml: escapeHtml,
      compactJson: compactJson,
      loadShell: loadShell,
      loadRuntimeView: loadRuntimeView,
      postJson: postJson,
      postShellChrome: postShellChrome,
      cloneRequestWithoutChrome: cloneRequestWithoutChrome,
      getEnvelope: function () { return lastEnvelope; },
      getLastShellRequest: function () { return lastShellRequest; },
    }, extras || {});
  }

  function renderRegions(comp) {
    var chromeRenderers = window.PortalShellRegionRenderers || {};
    var workbenchRenderer = window.PortalShellWorkbenchRenderer;
    var inspectorRenderer = window.PortalShellInspectorRenderer;
    if (typeof chromeRenderers.renderActivityBar !== "function") {
      throw new Error("Activity-bar renderer unavailable.");
    }
    if (typeof chromeRenderers.renderControlPanel !== "function") {
      throw new Error("Control-panel renderer unavailable.");
    }
    if (!workbenchRenderer || typeof workbenchRenderer.render !== "function") {
      throw new Error("Workbench renderer unavailable.");
    }
    if (!inspectorRenderer || typeof inspectorRenderer.render !== "function") {
      throw new Error("Inspector renderer unavailable.");
    }
    chromeRenderers.renderActivityBar(buildRendererContext(comp.regions.activity_bar || {}, document.getElementById("v2-activity-nav")));
    chromeRenderers.renderControlPanel(buildRendererContext(comp.regions.control_panel || {}, document.getElementById("portalControlPanel")));
    workbenchRenderer.render(buildRendererContext(comp.regions.workbench || {}, document.getElementById("v2-workbench-body")));
    inspectorRenderer.render(
      buildRendererContext(comp.regions.inspector || {}, document.getElementById("v2-inspector-dynamic"), {
        titleEl: document.getElementById("portalInspectorTitle"),
      })
    );
  }

  function applyEnvelope(env, options) {
    if (!env || env.schema !== RUNTIME_ENVELOPE_SCHEMA) {
      showFatal("Invalid runtime envelope schema from shell route.", "render_dispatch_failed");
      return;
    }
    var comp = env.shell_composition;
    if (!comp || !comp.regions) {
      showFatal("Runtime envelope is missing shell_composition.regions.", "render_dispatch_failed");
      return;
    }
    if (options && options.trackDirectView) {
      lastDirectView = {
        url: options.url,
        requestBody: JSON.parse(JSON.stringify(options.requestBody || {})),
      };
    } else if (options && options.clearDirectView) {
      lastDirectView = null;
    }
    lastEnvelope = env;
    lastComposition = comp;
    try {
      applyChrome(comp);
      renderRegions(comp);
    } catch (error) {
      showFatal(
        "Shell render dispatch failed. " + String((error && error.message) || error || "Unknown renderer error."),
        "render_dispatch_failed"
      );
      return;
    }
    setFatalClass("");
    setBootState("hydrated");
    window.__MYCITE_V2_SHELL_HYDRATED = true;
    window.__MYCITE_V2_SHELL_FATAL_SHOWN = false;
    if (window.PortalShell && typeof window.PortalShell.rebalanceWorkbench === "function") {
      window.PortalShell.rebalanceWorkbench();
    }
    return env;
  }

  function loadShell(requestBody) {
    lastShellRequest = requestBody;
    lastDirectView = null;
    setFatalClass("");
    setBootState("shell_posting");
    window.__MYCITE_V2_SHELL_HYDRATED = false;
    window.__MYCITE_V2_SHELL_FATAL_SHOWN = false;
    return postJson(SHELL_URL, requestBody).then(function (response) {
      var env = response.json;
      if (!response.ok || !env) {
        showFatal(
          "Shell POST failed (HTTP " +
            response.status +
            "). Check auth, nginx upstream (6101), and service logs. " +
            (response.bodySnippet ? "Body: " + response.bodySnippet : ""),
          "shell_post_failed"
        );
        return;
      }
      return applyEnvelope(env, { clearDirectView: true });
    });
  }

  function loadRuntimeView(url, requestBody) {
    setFatalClass("");
    setBootState("shell_posting");
    window.__MYCITE_V2_SHELL_HYDRATED = false;
    window.__MYCITE_V2_SHELL_FATAL_SHOWN = false;
    return postJson(url, requestBody).then(function (response) {
      var env = response.json;
      if (!response.ok || !env) {
        showFatal(
          "Shell POST failed (HTTP " +
            response.status +
            "). " +
            (response.bodySnippet ? "Body: " + response.bodySnippet : ""),
          "shell_post_failed"
        );
        return;
      }
      return applyEnvelope(env, { trackDirectView: true, url: url, requestBody: requestBody });
    });
  }

  function boot() {
    setBootState("bundle_loaded");
    var bootstrap = readBootstrapRequest();
    if (!bootstrap) {
      showFatal("Missing server bootstrap shell request.", "render_dispatch_failed");
      return;
    }
    loadShell(bootstrap).catch(function () {
      showFatal("Shell request failed.", "shell_post_failed");
    });

    document.addEventListener("mycite:v2:inspector-dismiss-request", function () {
      postShellChrome({ inspector_collapsed: true });
    });
    document.addEventListener("mycite:v2:inspector-toggle-request", function () {
      var collapsed = !!(lastComposition && lastComposition.inspector_collapsed);
      postShellChrome({ inspector_collapsed: !collapsed });
    });
    document.addEventListener("mycite:v2:control-panel-toggle-request", function () {
      var collapsed = !!(lastComposition && lastComposition.control_panel_collapsed);
      postShellChrome({ control_panel_collapsed: !collapsed });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
