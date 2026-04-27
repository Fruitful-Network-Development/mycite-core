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

  function asList(value) {
    return Array.isArray(value) ? value.slice() : [];
  }

  function asText(value) {
    return String(value == null ? "" : value).trim();
  }

  function resolveRegisteredModuleExport(moduleId, globalName) {
    if (typeof window.__MYCITE_V2_RESOLVE_SHELL_MODULE_EXPORT === "function") {
      return window.__MYCITE_V2_RESOLVE_SHELL_MODULE_EXPORT(moduleId, globalName);
    }
    return window[globalName] || null;
  }

  function buildModuleRegistrationError(label, moduleId, globalName, callableName) {
    var message =
      asText(label || "Renderer") +
      " renderer unavailable. " +
      "module_id=" +
      moduleId +
      " expected_global=" +
      globalName +
      " expected_callable=" +
      callableName +
      ".";
    if (typeof window.__MYCITE_V2_GET_SHELL_MODULE_DIAGNOSTICS === "function") {
      var diagnostics = window.__MYCITE_V2_GET_SHELL_MODULE_DIAGNOSTICS(moduleId) || {};
      var loadedScripts = asList(diagnostics.script_load_order)
        .map(function (entry) {
          return asText((entry && entry.module_id) || (entry && entry.file));
        })
        .filter(Boolean);
      var registeredModules = asList(diagnostics.registered_module_ids)
        .map(function (entry) {
          return asText(entry);
        })
        .filter(Boolean);
      var invalidMessages = asList(diagnostics.invalid_messages)
        .map(function (entry) {
          return asText(entry);
        })
        .filter(Boolean);
      var failures = asList(diagnostics.failures)
        .map(function (entry) {
          return asText(entry);
        })
        .filter(Boolean);
      message +=
        " boot_stage=" +
        (asText(diagnostics.boot_stage) || "unknown") +
        " loaded_scripts=" +
        (loadedScripts.join(" -> ") || "none") +
        " registered_modules=" +
        (registeredModules.join(", ") || "none") +
        " invalid_registrations=" +
        (invalidMessages.join("; ") || "none") +
        (failures.length ? " contract_failures=" + failures.join("; ") : "");
    }
    var error = new Error(message);
    error.fatalClass = "module_registration_missing";
    return error;
  }

  function routeKeyFromUrl(rawUrl) {
    if (!rawUrl) {
      return `${window.location.pathname || ""}${window.location.search || ""}`;
    }
    try {
      var parsed = new URL(rawUrl, window.location.origin);
      return `${parsed.pathname || ""}${parsed.search || ""}`;
    } catch (_) {
      return String(rawUrl || "").trim().charAt(0) === "/"
        ? String(rawUrl || "").trim()
        : `${window.location.pathname || ""}${window.location.search || ""}`;
    }
  }

  function setBootState(state) {
    if (!BODY_DATA) return;
    BODY_DATA.setAttribute("data-shell-boot-state", asText(state) || "template");
    if (typeof window.__MYCITE_V2_SET_SHELL_BOOT_STAGE === "function") {
      window.__MYCITE_V2_SET_SHELL_BOOT_STAGE(state);
    }
  }

  function showFatal(message, fatalClass) {
    if (BODY_DATA) {
      BODY_DATA.setAttribute("data-shell-boot-state", "fatal");
      BODY_DATA.setAttribute("data-shell-fatal-class", fatalClass || "render_dispatch_failed");
    }
    if (typeof window.__MYCITE_V2_SET_SHELL_BOOT_STAGE === "function") {
      window.__MYCITE_V2_SET_SHELL_BOOT_STAGE("fatal");
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
    var value = req || {};
    if (typeof window.structuredClone === "function") {
      try {
        return window.structuredClone(value);
      } catch (_) {}
    }
    try {
      return JSON.parse(JSON.stringify(value));
    } catch (_) {
      if (Array.isArray(value)) return value.slice();
      if (value && typeof value === "object") return Object.assign({}, value);
      return {};
    }
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
    var requestBody = {
      schema: "mycite.v2.portal.shell.request.v1",
      requested_surface_id: envelope.surface_id || "system.root",
      portal_scope: cloneRequest(envelope.portal_scope || {}),
      shell_state: cloneRequest(envelope.shell_state || {}),
    };
    var surfacePayload = (envelope && envelope.surface_payload) || {};
    var requestContract = (surfacePayload && surfacePayload.request_contract) || {};
    if (requestContract.tool_state_supported && surfacePayload.tool_state) {
      requestBody.tool_state = cloneRequest(surfacePayload.tool_state || {});
    }
    return requestBody;
  }

  function applyChrome(composition, options) {
    var shell = qs(".ide-shell");
    var workbench = qs(".ide-workbench");
    var inspector = qs("#portalInspector");
    var inspectorContent = qs("#portalInspectorContent");
    var menubarTitle = qs(".ide-menubar__pageTitle");
    var menubarSub = qs(".ide-menubar__pageSub");
    var inspectorRegion =
      ((composition.regions && composition.regions.interface_panel) ||
        (composition.regions && composition.regions.inspector)) ||
      {};
    var workbenchRegion = (composition.regions && composition.regions.workbench) || {};
    var routeKey = (options && options.routeKey) || routeKeyFromUrl((lastEnvelope && lastEnvelope.canonical_url) || "");
    var workbenchVisible = !(composition.workbench_collapsed === true || workbenchRegion.visible === false);
    var inspectorVisible =
      inspectorRegion.visible !== false &&
      !(composition.interface_panel_collapsed === true || composition.inspector_collapsed === true);
    if (!shell) return;

    shell.setAttribute("data-active-service", composition.active_service || "system");
    shell.setAttribute("data-shell-composition", composition.composition_mode || "system");
    shell.setAttribute("data-foreground-shell-region", composition.foreground_shell_region || "center-workbench");
    shell.setAttribute("data-control-panel-collapsed", composition.control_panel_collapsed ? "true" : "false");
    shell.setAttribute("data-workbench-collapsed", workbenchVisible ? "false" : "true");
    shell.setAttribute("data-inspector-collapsed", inspectorVisible ? "false" : "true");
    shell.setAttribute("data-interface-panel-collapsed", inspectorVisible ? "false" : "true");

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
    }
    if (inspector) {
      inspector.setAttribute("data-primary-surface", inspectorRegion.primary_surface ? "true" : "false");
      inspector.setAttribute("data-surface-layout", inspectorRegion.layout_mode || "sidebar");
    }
    if (inspectorContent) {
      inspectorContent.setAttribute(
        "data-interface-panel-active-root",
        (composition.composition_mode || "system") === "tool" ? "tool" : "system"
      );
    }
    if (window.PortalShell && typeof window.PortalShell.setShellComposition === "function") {
      window.PortalShell.setShellComposition(composition.composition_mode || "system", { routeKey: routeKey });
    }
    if (window.PortalShell && typeof window.PortalShell.syncFromDom === "function") {
      window.PortalShell.syncFromDom({ fromShellComposition: true, routeKey: routeKey });
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
      dispatchToolAction: dispatchToolAction,
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
    var chromeRenderers = resolveRegisteredModuleExport("region_renderers", "PortalShellRegionRenderers") || {};
    var workbenchRenderer = resolveRegisteredModuleExport("workbench_renderers", "PortalShellWorkbenchRenderer");
    var inspectorRenderer = resolveRegisteredModuleExport("inspector_renderers", "PortalShellInspectorRenderer");
    var interfacePanelRegion =
      ((composition.regions && composition.regions.interface_panel) ||
        (composition.regions && composition.regions.inspector)) ||
      {};
    if (typeof chromeRenderers.renderActivityBar !== "function") {
      throw buildModuleRegistrationError(
        "Activity-bar",
        "region_renderers",
        "PortalShellRegionRenderers",
        "renderActivityBar"
      );
    }
    if (typeof chromeRenderers.renderControlPanel !== "function") {
      throw buildModuleRegistrationError(
        "Control-panel",
        "region_renderers",
        "PortalShellRegionRenderers",
        "renderControlPanel"
      );
    }
    if (!workbenchRenderer || typeof workbenchRenderer.render !== "function") {
      throw buildModuleRegistrationError(
        "Workbench",
        "workbench_renderers",
        "PortalShellWorkbenchRenderer",
        "render"
      );
    }
    if (!inspectorRenderer || typeof inspectorRenderer.render !== "function") {
      throw buildModuleRegistrationError(
        "Inspector",
        "inspector_renderers",
        "PortalShellInspectorRenderer",
        "render"
      );
    }
    chromeRenderers.renderActivityBar(buildRendererContext(composition.regions.activity_bar, qs("#v2-activity-nav")));
    chromeRenderers.renderControlPanel(buildRendererContext(composition.regions.control_panel, qs("#portalControlPanel")));
    workbenchRenderer.render(buildRendererContext(composition.regions.workbench, qs("#v2-workbench-body")));
    inspectorRenderer.render(buildRendererContext(interfacePanelRegion, qs("#v2-inspector-dynamic")));
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
    applyChrome(envelope.shell_composition, { routeKey: routeKeyFromUrl(envelope.canonical_url) });
    try {
      renderRegions(envelope.shell_composition);
    } catch (error) {
      showFatal(
        error && error.message ? error.message : "The shell render dispatch failed.",
        error && error.fatalClass ? error.fatalClass : "render_dispatch_failed"
      );
      return;
    }
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

  function dispatchToolAction(action, overrides) {
    var envelope = lastEnvelope || {};
    var surfacePayload = envelope.surface_payload || {};
    var requestContract = surfacePayload.request_contract || {};
    var actionContract = requestContract.action_contract || {};
    var baseAction = cloneRequest(action || {});
    var extra = cloneRequest(overrides || {});
    var route = baseAction.route || extra.route || actionContract.route;
    var requestSchema =
      baseAction.request_schema ||
      extra.request_schema ||
      actionContract.schema ||
      "";
    var actionKind =
      baseAction.action_kind ||
      baseAction.kind ||
      extra.action_kind ||
      "";
    var actionPayload = Object.assign(
      {},
      cloneRequest(baseAction.action_payload || baseAction.payload || {}),
      cloneRequest(extra.action_payload || extra.payload || {})
    );
    var toolState = cloneRequest(extra.tool_state || surfacePayload.tool_state || {});
    var runtimeMode =
      extra.runtime_mode ||
      baseAction.runtime_mode ||
      surfacePayload.runtime_mode ||
      "";
    if (!route || !requestSchema || !actionKind) {
      return Promise.resolve();
    }
    var requestBody = {
      schema: requestSchema,
      portal_scope: cloneRequest(envelope.portal_scope || {}),
      shell_state: cloneRequest(envelope.shell_state || {}),
      tool_state: toolState,
      action_kind: actionKind,
      action_payload: actionPayload,
    };
    if (runtimeMode) {
      requestBody.runtime_mode = runtimeMode;
    }
    return loadRuntimeView(route, requestBody);
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
    function withPortalShell(action) {
      if (!window.PortalShell) return false;
      action(window.PortalShell);
      return true;
    }

    function setWorkbenchOpenLocal(isOpen) {
      withPortalShell(function (portalShell) {
        if (typeof portalShell.setWorkbenchOpen === "function") {
          portalShell.setWorkbenchOpen(!!isOpen, true);
        }
      });
    }

    function setInterfacePanelOpenLocal(isOpen) {
      withPortalShell(function (portalShell) {
        if (typeof portalShell.setInterfacePanelOpen === "function") {
          portalShell.setInterfacePanelOpen(!!isOpen, true);
        }
      });
    }

    function setControlPanelOpenLocal(isOpen) {
      withPortalShell(function (portalShell) {
        if (typeof portalShell.setControlPanelOpen === "function") {
          portalShell.setControlPanelOpen(!!isOpen, true);
        }
      });
    }

    function handleInterfacePanelToggle() {
      var shell = qs(".ide-shell");
      if (!shell) return;
      var isToolComposition = shell.getAttribute("data-shell-composition") === "tool";
      if (isToolComposition) {
        var isOpenOnTool = shell.getAttribute("data-interface-panel-collapsed") !== "true";
        setInterfacePanelOpenLocal(!isOpenOnTool);
        return;
      }
      var envelope = lastEnvelope;
      if (!envelope || !envelope.reducer_owned) {
        var isOpenLocal = shell.getAttribute("data-interface-panel-collapsed") !== "true";
        setInterfacePanelOpenLocal(!isOpenLocal);
        return;
      }
      var isOpen = envelope.shell_state && envelope.shell_state.chrome && envelope.shell_state.chrome.interface_panel_open;
      dispatchTransition({ kind: isOpen ? "close_interface_panel" : "open_interface_panel" });
    }

    function handleInterfacePanelDismiss() {
      var shell = qs(".ide-shell");
      if (!shell) return;
      if (shell.getAttribute("data-shell-composition") === "tool") {
        setInterfacePanelOpenLocal(false);
        return;
      }
      var envelope = lastEnvelope;
      if (!envelope || !envelope.reducer_owned) {
        setInterfacePanelOpenLocal(false);
        return;
      }
      dispatchTransition({ kind: "close_interface_panel" });
    }

    ["mycite:v2:interface-panel-toggle-request", "mycite:v2:inspector-toggle-request"].forEach(function (eventName) {
      document.addEventListener(eventName, handleInterfacePanelToggle);
    });
    ["mycite:v2:interface-panel-dismiss-request", "mycite:v2:inspector-dismiss-request"].forEach(function (eventName) {
      document.addEventListener(eventName, handleInterfacePanelDismiss);
    });
    document.addEventListener("mycite:v2:workbench-toggle-request", function () {
      var shell = qs(".ide-shell");
      if (!shell) return;
      var isOpenLocal = shell.getAttribute("data-workbench-collapsed") !== "true";
      setWorkbenchOpenLocal(!isOpenLocal);
    });
    document.addEventListener("mycite:v2:control-panel-toggle-request", function () {
      var shell = qs(".ide-shell");
      if (!shell) return;
      var collapsed = shell.getAttribute("data-control-panel-collapsed") === "true";
      setControlPanelOpenLocal(collapsed);
    });
  }

  window.PortalShellCore = {
    loadShell: loadShell,
    loadRuntimeView: loadRuntimeView,
    dispatchTransition: dispatchTransition,
    dispatchToolAction: dispatchToolAction,
    getEnvelope: function () {
      return lastEnvelope;
    },
  };
  if (typeof window.__MYCITE_V2_REGISTER_SHELL_MODULE === "function") {
    window.__MYCITE_V2_REGISTER_SHELL_MODULE("shell_core");
  }
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
