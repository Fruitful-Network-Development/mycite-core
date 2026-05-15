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
  var _lastRegionRenderKeys = {};
  var _lastRenderedSurfaceId = "";
  var TOOL_STATE_SESSION_PREFIX = "mycite_v2_tool_state__";

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

  function persistToolStateForSurface(surfaceId, toolState) {
    var normalizedSurfaceId = asText(surfaceId);
    if (!normalizedSurfaceId || !toolState) return;
    try {
      if (window.sessionStorage) {
        window.sessionStorage.setItem(TOOL_STATE_SESSION_PREFIX + normalizedSurfaceId, JSON.stringify(toolState));
      }
    } catch (_) {}
  }

  function readPersistedToolStateForSurface(surfaceId) {
    var normalizedSurfaceId = asText(surfaceId);
    if (!normalizedSurfaceId) return null;
    try {
      if (!window.sessionStorage) return null;
      var raw = window.sessionStorage.getItem(TOOL_STATE_SESSION_PREFIX + normalizedSurfaceId);
      if (!raw) return null;
      var parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
    } catch (_) {
      return null;
    }
  }

  function persistToolStateFromEnvelope(envelope) {
    var surfacePayload = (envelope && envelope.surface_payload) || {};
    var requestContract = surfacePayload.request_contract || {};
    if (requestContract.tool_state_supported && surfacePayload.tool_state) {
      persistToolStateForSurface(envelope.surface_id, surfacePayload.tool_state);
    }
  }

  function hydrateShellRequestToolState(shellRequest) {
    var requestBody = cloneRequest(shellRequest || {});
    if (requestBody.tool_state) return requestBody;
    var targetSurfaceId =
      asText(requestBody.requested_surface_id) ||
      asText(requestBody.surface_id) ||
      asText(lastEnvelope && lastEnvelope.surface_id);
    var persistedToolState = readPersistedToolStateForSurface(targetSurfaceId);
    if (persistedToolState) {
      requestBody.tool_state = cloneRequest(persistedToolState);
    }
    return requestBody;
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
    var interfacePanel = qs("#portalInterfacePanel");
    var interfacePanelContent = qs("#portalInterfacePanelContent");
    var menubarTitle = qs(".ide-menubar__pageTitle");
    var menubarSub = qs(".ide-menubar__pageSub");
    var interfacePanelRegion = (composition.regions && composition.regions.interface_panel) || {};
    var workbenchRegion = (composition.regions && composition.regions.workbench) || {};
    var routeKey = (options && options.routeKey) || routeKeyFromUrl((lastEnvelope && lastEnvelope.canonical_url) || "");
    var workbenchVisible = !(composition.workbench_collapsed === true || workbenchRegion.visible === false);
    var interfacePanelVisible =
      interfacePanelRegion.visible !== false && !(composition.interface_panel_collapsed === true);
    if (!shell) return;

    shell.setAttribute("data-active-service", composition.active_service || "system");
    shell.setAttribute("data-shell-composition", composition.composition_mode || "system");
    shell.setAttribute("data-foreground-shell-region", composition.foreground_shell_region || "center-workbench");
    shell.setAttribute("data-control-panel-collapsed", composition.control_panel_collapsed ? "true" : "false");
    // Phase 4 follow-up — preserve the user's manual workbench /
    // interface-panel layout across action dispatches. When the
    // surface hasn't changed (action dispatch on the same tool — e.g.
    // select_district_row, select_precinct_row, engage_component_frame),
    // we trust the local state set by toggle handlers and skip the
    // server-side default. Only the very first applyChrome for this
    // surface (or a real surface switch) writes these attributes.
    var isInitialOrSurfaceChange = !shell.hasAttribute("data-shell-chrome-initialized")
      || shell.getAttribute("data-shell-chrome-initialized") !== routeKey;
    if (isInitialOrSurfaceChange) {
      shell.setAttribute("data-workbench-collapsed", workbenchVisible ? "false" : "true");
      shell.setAttribute("data-interface-panel-collapsed", interfacePanelVisible ? "false" : "true");
      shell.setAttribute("data-shell-chrome-initialized", routeKey);
    }

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
    if (interfacePanel) {
      interfacePanel.setAttribute("data-primary-surface", interfacePanelRegion.primary_surface ? "true" : "false");
      interfacePanel.setAttribute("data-surface-layout", interfacePanelRegion.layout_mode || "sidebar");
    }
    if (interfacePanelContent) {
      interfacePanelContent.setAttribute(
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

  function shouldSkipRegionRender(regionName, region) {
    var key = asText(region && region.render_key);
    if (!key) return false;
    if (_lastRegionRenderKeys[regionName] === key) return true;
    _lastRegionRenderKeys[regionName] = key;
    return false;
  }

  function renderRegions(composition) {
    var chromeRenderers = resolveRegisteredModuleExport("region_renderers", "PortalShellRegionRenderers") || {};
    var workbenchRenderer = resolveRegisteredModuleExport("workbench_renderers", "PortalShellWorkbenchRenderer");
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
    // Phase 3 retired the interface panel and Phase 3e deleted its renderer
    // module + manifest entry. build_shell_composition_payload forces the
    // region's `visible=false`, so even if the composition still emits an
    // interface_panel region for schema continuity, the renderer never runs.
    // The resolve + dispatch lines are gone with the module.
    chromeRenderers.renderActivityBar(buildRendererContext(composition.regions.activity_bar, qs("#v2-activity-nav")));
    chromeRenderers.renderControlPanel(buildRendererContext(composition.regions.control_panel, qs("#portalControlPanel")));
    workbenchRenderer.render(buildRendererContext(composition.regions.workbench, qs("#v2-workbench-body")));
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
    var surfaceId = asText(envelope.surface_id);
    if (surfaceId !== _lastRenderedSurfaceId) {
      _lastRegionRenderKeys = {};
      _lastRenderedSurfaceId = surfaceId;
    }
    lastEnvelope = envelope;
    lastShellRequest = canonicalShellRequestFromEnvelope(envelope) || lastShellRequest;
    persistToolStateFromEnvelope(envelope);
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
    var requestBody = hydrateShellRequestToolState(shellRequest);
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
    var surfacePayload = envelope.surface_payload || {};
    var requestContract = surfacePayload.request_contract || {};
    if (requestContract.tool_state_supported && surfacePayload.tool_state) {
      requestBody.tool_state = cloneRequest(surfacePayload.tool_state || {});
    }
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

    function reassertAnchorFocusIfNeeded(envelope) {
      if (!envelope || !envelope.reducer_owned) return;
      var composition =
        (envelope.shell_composition && envelope.shell_composition) ||
        (envelope.composition && envelope.composition) ||
        {};
      var workbenchRegion = (composition.regions && composition.regions.workbench) || {};
      var reflection = (workbenchRegion && workbenchRegion.state_reflection) || {};
      var currentFile = (reflection && reflection.current_file) || "";
      var collection = (workbenchRegion && workbenchRegion.document_collection) || {};
      var anchorDocument = (collection && collection.anchor_document) || {};
      var anchorId = (anchorDocument && anchorDocument.document_id) || "";
      var anchorName = (anchorDocument && anchorDocument.canonical_name) || "";
      if (!currentFile || currentFile === "anchor" || currentFile === "anthology" || currentFile === anchorId || currentFile === anchorName) return;
      var sandbox = (workbenchRegion && workbenchRegion.sandbox) || {};
      var sandboxId =
        (sandbox && sandbox.id) ||
        (workbenchRegion && workbenchRegion.sandbox_id) ||
        (workbenchRegion.surface_payload && workbenchRegion.surface_payload.sandbox_id) ||
        "";
      if (!sandboxId) return;
      dispatchTransition({ kind: "focus_sandbox", sandbox_id: sandboxId });
    }

    function isToolCompositionActive() {
      var shell = qs(".ide-shell");
      return shell ? shell.getAttribute("data-shell-composition") === "tool" : false;
    }

    function handleInterfacePanelToggle() {
      var shell = qs(".ide-shell");
      if (!shell) return;
      if (isToolCompositionActive()) {
        var isOpenOnTool = shell.getAttribute("data-interface-panel-collapsed") !== "true";
        if (!isOpenOnTool) {
          // opening interface panel on a tool surface closes the workbench
          setWorkbenchOpenLocal(false);
        }
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
      if (!isOpen) {
        reassertAnchorFocusIfNeeded(envelope);
      }
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

    document.addEventListener("mycite:v2:interface-panel-toggle-request", handleInterfacePanelToggle);
    document.addEventListener("mycite:v2:interface-panel-dismiss-request", handleInterfacePanelDismiss);
    document.addEventListener("mycite:v2:workbench-toggle-request", function () {
      var shell = qs(".ide-shell");
      if (!shell) return;
      var isOpenLocal = shell.getAttribute("data-workbench-collapsed") !== "true";
      if (isToolCompositionActive() && !isOpenLocal) {
        // opening workbench on a tool surface closes the interface panel
        setInterfacePanelOpenLocal(false);
      }
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
  bootstrapRequest = hydrateShellRequestToolState(bootstrapRequest);

  loadShell(bootstrapRequest, { replaceHistory: true }).catch(function (err) {
    showFatal(err && err.message ? err.message : "The shell request failed before the runtime returned.", "shell_post_failed");
  });
})();
