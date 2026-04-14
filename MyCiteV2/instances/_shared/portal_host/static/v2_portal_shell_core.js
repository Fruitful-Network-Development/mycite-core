/**
 * One-shell portal core.
 * Owns shell bootstrap, runtime POSTs, envelope validation, and dispatch into
 * dedicated region/workbench/inspector renderers.
 */
(function () {
  var BODY_DATA = document.body || document.documentElement;
  var SHELL_URL = (BODY_DATA && BODY_DATA.getAttribute("data-shell-endpoint")) || "/portal/api/v2/shell";
  var RUNTIME_ENVELOPE_SCHEMA =
    (BODY_DATA && BODY_DATA.getAttribute("data-runtime-envelope-schema")) ||
    "mycite.v2.portal.runtime.envelope.v1";

  var lastShellRequest = null;
  var lastEnvelope = null;
  var lastDirectView = null;

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

  function setBootState(state) {
    if (!BODY_DATA) return;
    BODY_DATA.setAttribute("data-shell-boot-state", String(state || "").trim() || "template");
  }

  function showFatal(message, fatalClass) {
    if (BODY_DATA) {
      BODY_DATA.setAttribute("data-shell-boot-state", "fatal");
      BODY_DATA.setAttribute("data-shell-fatal-class", fatalClass || "render_dispatch_failed");
    }
    var placeholder = qs("#v2-control-panel-placeholder");
    if (placeholder) placeholder.textContent = message;
    var workbenchBody = qs("#v2-workbench-body");
    if (workbenchBody) {
      workbenchBody.innerHTML =
        '<section class="v2-card" style="max-width:720px"><h3>Shell hydration failed</h3><p>' +
        escapeHtml(message) +
        "</p></section>";
    }
  }

  function postJson(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
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

  function cloneRequest(req) {
    return JSON.parse(JSON.stringify(req || {}));
  }

  function readBootstrapRequest() {
    var el = qs("#v2-bootstrap-shell-request");
    if (!el || !el.textContent) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (_) {
      return null;
    }
  }

  function applyChrome(composition) {
    var shell = qs(".ide-shell");
    var workbench = qs(".ide-workbench");
    var inspector = qs("#portalInspector");
    var inspectorContent = qs("#portalInspectorContent");
    var menubarTitle = qs(".ide-menubar__pageTitle");
    var menubarSub = qs(".ide-menubar__pageSub");
    var pageheadTitle = qs("#v2-workbench-title");
    var pageheadSub = qs("#v2-workbench-subtitle");
    var inspectorRegion = (composition.regions && composition.regions.inspector) || {};
    var workbenchRegion = (composition.regions && composition.regions.workbench) || {};
    if (!shell) return;

    shell.setAttribute("data-active-service", composition.active_service || "system");
    shell.setAttribute("data-shell-composition", composition.composition_mode || "system");
    shell.setAttribute("data-foreground-shell-region", composition.foreground_shell_region || "center-workbench");
    shell.setAttribute("data-control-panel-collapsed", composition.control_panel_collapsed ? "true" : "false");
    shell.setAttribute("data-inspector-collapsed", composition.inspector_collapsed ? "true" : "false");

    if (menubarTitle && composition.page_title) menubarTitle.textContent = composition.page_title;
    if (menubarSub) {
      menubarSub.textContent =
        composition.page_subtitle ||
        [
          BODY_DATA && BODY_DATA.getAttribute("data-host-shape"),
          "portal " + ((BODY_DATA && BODY_DATA.getAttribute("data-portal-instance-id")) || ""),
          (BODY_DATA && BODY_DATA.getAttribute("data-portal-domain")) || "",
        ]
          .filter(Boolean)
          .join(" · ");
    }
    if (pageheadTitle && workbenchRegion.title) pageheadTitle.textContent = workbenchRegion.title;
    if (pageheadSub) pageheadSub.textContent = workbenchRegion.subtitle || composition.page_subtitle || "";

    if (workbench) {
      workbench.setAttribute("data-active-service", composition.active_service || "system");
      workbench.setAttribute(
        "data-foreground-visible",
        composition.foreground_shell_region === "center-workbench" ? "true" : "false"
      );
      workbench.setAttribute("aria-hidden", composition.foreground_shell_region === "center-workbench" ? "false" : "true");
    }
    if (inspector) {
      inspector.setAttribute("data-primary-surface", inspectorRegion.primary_surface ? "true" : "false");
      inspector.setAttribute("data-surface-layout", inspectorRegion.layout_mode || "sidebar");
      inspector.setAttribute("aria-hidden", composition.inspector_collapsed ? "true" : "false");
    }
    if (inspectorContent) {
      inspectorContent.setAttribute(
        "data-interface-panel-active-root",
        (composition.composition_mode || "system") === "tool" ? "tool" : "system"
      );
    }
  }

  function buildRendererContext(region, target) {
    return {
      region: region || {},
      target: target,
      escapeHtml: escapeHtml,
      compactJson: compactJson,
      loadShell: loadShell,
      loadRuntimeView: loadRuntimeView,
      postJson: postJson,
      cloneRequest: cloneRequest,
      getEnvelope: function () { return lastEnvelope; },
      getLastShellRequest: function () { return lastShellRequest; },
    };
  }

  function renderRegions(composition) {
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
    chromeRenderers.renderActivityBar(buildRendererContext(composition.regions.activity_bar, qs("#v2-activity-nav")));
    chromeRenderers.renderControlPanel(buildRendererContext(composition.regions.control_panel, qs("#portalControlPanel")));
    workbenchRenderer.render(buildRendererContext(composition.regions.workbench, qs("#v2-workbench-body")));
    inspectorRenderer.render(buildRendererContext(composition.regions.inspector, qs("#v2-inspector-dynamic")));
  }

  function applyEnvelope(envelope, options) {
    if (!envelope || envelope.schema !== RUNTIME_ENVELOPE_SCHEMA) {
      showFatal("Invalid runtime envelope schema from shell route.", "render_dispatch_failed");
      return;
    }
    if (!envelope.shell_composition || !envelope.shell_composition.regions) {
      showFatal("Runtime envelope is missing shell_composition.regions.", "render_dispatch_failed");
      return;
    }
    if (envelope.error && envelope.error.message) {
      console.warn("Portal runtime warning:", envelope.error.message);
    }
    lastEnvelope = envelope;
    if (options && options.trackDirectView) {
      lastDirectView = {
        url: options.url,
        requestBody: cloneRequest(options.requestBody),
      };
    } else {
      lastDirectView = null;
    }
    applyChrome(envelope.shell_composition);
    renderRegions(envelope.shell_composition);
    setBootState("hydrated");
  }

  function loadShell(shellRequest) {
    var requestBody = cloneRequest(shellRequest);
    lastShellRequest = requestBody;
    return postJson(SHELL_URL, requestBody).then(function (result) {
      if (!result.ok || !result.json) {
        showFatal(
          "The shell request failed (" + result.status + "). " + (result.bodySnippet || "No response body was returned."),
          "shell_post_failed"
        );
        return;
      }
      applyEnvelope(result.json, { trackDirectView: false });
    });
  }

  function loadRuntimeView(url, requestBody) {
    var body = cloneRequest(requestBody);
    return postJson(url, body).then(function (result) {
      if (!result.ok || !result.json) {
        showFatal(
          "The surface request failed (" + result.status + "). " + (result.bodySnippet || "No response body was returned."),
          "runtime_post_failed"
        );
        return;
      }
      applyEnvelope(result.json, { trackDirectView: true, url: url, requestBody: body });
    });
  }

  window.PortalShell = {
    loadShell: loadShell,
    loadRuntimeView: loadRuntimeView,
    syncFromDom: function () {},
  };
  window.__MYCITE_V2_SHELL_CORE_LOADED = true;
  setBootState("core_loaded");

  var bootstrapRequest = readBootstrapRequest();
  if (!bootstrapRequest) {
    showFatal("Bootstrap shell request is missing or invalid.", "bootstrap_invalid");
    return;
  }

  loadShell(bootstrapRequest).catch(function (err) {
    showFatal(err && err.message ? err.message : "Shell bootstrap failed.", "shell_bootstrap_failed");
  });
})();
