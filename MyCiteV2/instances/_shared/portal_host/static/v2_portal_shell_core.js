/**
 * One-shell portal core.
 * Owns runtime POSTs, reducer transitions, envelope validation, and runtime-
 * owned history synchronization.
 */
(function () {
  var BODY_DATA = document.body || document.documentElement;
  var SHELL_URL = (BODY_DATA && BODY_DATA.getAttribute("data-shell-endpoint")) || "/portal/api/v2/shell";
  var RUNTIME_ENVELOPE_SCHEMA =
    (BODY_DATA && BODY_DATA.getAttribute("data-runtime-envelope-schema")) ||
    "mycite.v2.portal.runtime.envelope.v1";

  var lastShellRequest = null;
  var lastEnvelope = null;

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
    window.__MYCITE_V2_SHELL_FATAL_SHOWN = true;
    window.__MYCITE_V2_SHELL_HYDRATED = false;
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

  function canonicalShellRequestFromEnvelope(envelope) {
    if (!envelope || !envelope.reducer_owned || !envelope.shell_state) return null;
    return {
      schema: "mycite.v2.portal.shell.request.v1",
      requested_surface_id: envelope.surface_id || "system.root",
      portal_scope: cloneRequest(envelope.portal_scope || {}),
      shell_state: cloneRequest(envelope.shell_state || {}),
    };
  }

  function applyChrome(composition) {
    var shell = qs(".ide-shell");
    var workbench = qs(".ide-workbench");
    var inspector = qs("#portalInspector");
    var inspectorContent = qs("#portalInspectorContent");
    var menubarTitle = qs(".ide-menubar__pageTitle");
    var menubarSub = qs(".ide-menubar__pageSub");
    var inspectorRegion = (composition.regions && composition.regions.inspector) || {};
    var workbenchRegion = (composition.regions && composition.regions.workbench) || {};
    var workbenchVisible = workbenchRegion.visible !== false;
    var inspectorVisible = inspectorRegion.visible !== false && !composition.inspector_collapsed;
    if (!shell) return;

    shell.setAttribute("data-active-service", composition.active_service || "system");
    shell.setAttribute("data-shell-composition", composition.composition_mode || "system");
    shell.setAttribute("data-foreground-shell-region", composition.foreground_shell_region || "center-workbench");
    shell.setAttribute("data-control-panel-collapsed", composition.control_panel_collapsed ? "true" : "false");
    shell.setAttribute("data-inspector-collapsed", inspectorVisible ? "false" : "true");

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
    document.title = composition.page_title ? composition.page_title + " | MyCite Portal Workspace" : "MyCite Portal Workspace";

    if (workbench) {
      workbench.setAttribute("data-active-service", composition.active_service || "system");
      workbench.setAttribute("data-foreground-visible", workbenchVisible ? "true" : "false");
      workbench.setAttribute("aria-hidden", workbenchVisible ? "false" : "true");
      workbench.style.display = workbenchVisible ? "" : "none";
    }
    if (inspector) {
      inspector.setAttribute("data-primary-surface", inspectorRegion.primary_surface ? "true" : "false");
      inspector.setAttribute("data-surface-layout", inspectorRegion.layout_mode || "sidebar");
      inspector.setAttribute("aria-hidden", inspectorVisible ? "false" : "true");
      inspector.style.display = inspectorVisible ? "" : "none";
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
      dispatchTransition: dispatchTransition,
      postJson: postJson,
      cloneRequest: cloneRequest,
      getEnvelope: function () {
        return lastEnvelope;
      },
      getLastShellRequest: function () {
        return lastShellRequest;
      },
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

  function syncHistory(envelope, historyPayload, options) {
    if (!envelope || !envelope.canonical_url) return;
    var state = cloneRequest(historyPayload || {});
    var replace = options && options.replaceHistory;
    if (replace) {
      window.history.replaceState(state, "", envelope.canonical_url);
      return;
    }
    window.history.pushState(state, "", envelope.canonical_url);
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
    lastShellRequest = canonicalShellRequestFromEnvelope(envelope) || lastShellRequest;
    applyChrome(envelope.shell_composition);
    renderRegions(envelope.shell_composition);
    if (!(options && options.updateHistory === false)) {
      syncHistory(envelope, options && options.historyPayload, options || {});
    }
    window.__MYCITE_V2_SHELL_HYDRATED = true;
    setBootState("hydrated");
  }

  function loadShell(shellRequest, options) {
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
      applyEnvelope(result.json, {
        historyPayload: { kind: "shell", requestBody: canonicalShellRequestFromEnvelope(result.json) || requestBody },
        updateHistory: !(options && options.updateHistory === false),
        replaceHistory: options && options.replaceHistory,
      });
    });
  }

  function loadRuntimeView(url, requestBody, options) {
    var body = cloneRequest(requestBody);
    return postJson(url, body).then(function (result) {
      if (!result.ok || !result.json) {
        showFatal(
          "The surface request failed (" + result.status + "). " + (result.bodySnippet || "No response body was returned."),
          "runtime_post_failed"
        );
        return;
      }
      applyEnvelope(result.json, {
        historyPayload: {
          kind: result.json && result.json.reducer_owned ? "shell" : "direct",
          requestBody: canonicalShellRequestFromEnvelope(result.json) || body,
          url: url,
        },
        updateHistory: !(options && options.updateHistory === false),
        replaceHistory: !!(options && options.replaceHistory),
      });
    });
  }

  function dispatchTransition(transition, requestedSurfaceId) {
    var envelope = lastEnvelope;
    if (!envelope || !envelope.reducer_owned) return Promise.resolve();
    var requestBody = {
      schema: "mycite.v2.portal.shell.request.v1",
      requested_surface_id: requestedSurfaceId || envelope.surface_id || "system.root",
      portal_scope: cloneRequest(envelope.portal_scope || {}),
      shell_state: cloneRequest(envelope.shell_state || {}),
      transition: cloneRequest(transition || {}),
    };
    return loadShell(requestBody);
  }

  function onPopState(event) {
    var state = event && event.state;
    if (!state) return;
    if (state.kind === "shell" && state.requestBody) {
      loadShell(state.requestBody, { updateHistory: false, replaceHistory: true });
      return;
    }
    if (state.kind === "direct" && state.url) {
      window.location.href = state.url;
    }
  }

  function bindShellChromeEvents() {
    function setInspectorOpenLocal(isOpen) {
      var shell = qs(".ide-shell");
      var inspector = qs("#portalInspector");
      if (!shell || !inspector) return;
      shell.setAttribute("data-inspector-collapsed", isOpen ? "false" : "true");
      inspector.classList.toggle("is-collapsed", !isOpen);
      inspector.setAttribute("aria-hidden", isOpen ? "false" : "true");
      inspector.style.display = isOpen ? "" : "none";
    }

    document.addEventListener("mycite:v2:inspector-toggle-request", function () {
      var envelope = lastEnvelope;
      if (!envelope || !envelope.reducer_owned) {
        var workbenchRegion = envelope && envelope.shell_composition && envelope.shell_composition.regions
          ? envelope.shell_composition.regions.workbench || {}
          : {};
        if (workbenchRegion.visible === false) return;
        var shell = qs(".ide-shell");
        if (!shell) return;
        var isOpenLocal = shell.getAttribute("data-inspector-collapsed") !== "true";
        setInspectorOpenLocal(!isOpenLocal);
        return;
      }
      var isOpen = envelope.shell_state && envelope.shell_state.chrome && envelope.shell_state.chrome.interface_panel_open;
      dispatchTransition({ kind: isOpen ? "close_interface_panel" : "open_interface_panel" });
    });
    document.addEventListener("mycite:v2:inspector-dismiss-request", function () {
      var envelope = lastEnvelope;
      if (!envelope || !envelope.reducer_owned) {
        var workbenchRegion = envelope && envelope.shell_composition && envelope.shell_composition.regions
          ? envelope.shell_composition.regions.workbench || {}
          : {};
        if (workbenchRegion.visible === false) return;
        setInspectorOpenLocal(false);
        return;
      }
      dispatchTransition({ kind: "close_interface_panel" });
    });
    document.addEventListener("mycite:v2:control-panel-toggle-request", function () {
      var shell = qs(".ide-shell");
      var controlPanel = qs("#portalControlPanel");
      if (!shell || !controlPanel) return;
      var collapsed = shell.getAttribute("data-control-panel-collapsed") === "true";
      shell.setAttribute("data-control-panel-collapsed", collapsed ? "false" : "true");
      controlPanel.classList.toggle("is-collapsed", !collapsed);
      controlPanel.setAttribute("aria-hidden", collapsed ? "false" : "true");
    });
  }

  window.PortalShellCore = {
    loadShell: loadShell,
    loadRuntimeView: loadRuntimeView,
    dispatchTransition: dispatchTransition,
    getEnvelope: function () {
      return lastEnvelope;
    },
  };
  window.__MYCITE_V2_SHOW_FATAL = showFatal;
  window.__MYCITE_V2_SHELL_CORE_LOADED = true;

  setBootState("core_loaded");
  bindShellChromeEvents();
  window.addEventListener("popstate", onPopState);

  var bootstrapRequest = readBootstrapRequest();
  if (!bootstrapRequest) {
    showFatal("Bootstrap shell request was not embedded into the page.", "bootstrap_missing");
    return;
  }

  loadShell(bootstrapRequest, { replaceHistory: true }).catch(function (err) {
    showFatal(err && err.message ? err.message : "The shell request failed before the runtime returned.", "shell_post_failed");
  });
})();
