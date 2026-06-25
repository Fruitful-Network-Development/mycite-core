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
  // portal-tool-overlay-restructure: state for the menubar-search → full-screen tool overlay.
  var _overlayState = { toolId: "", label: "", ctx: null, params: {} };

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
    // TASK-interface-panel-migration: the interface_panel is REVIVED as the tool surface
    // (search + tool render), rendered by renderInterfacePanel below.
    chromeRenderers.renderActivityBar(buildRendererContext(composition.regions.activity_bar, qs("#v2-activity-nav")));
    chromeRenderers.renderControlPanel(buildRendererContext(composition.regions.control_panel, qs("#portalControlPanel")));
    mountControlPanelControls(composition.regions.control_panel);
    workbenchRenderer.render(buildRendererContext(composition.regions.workbench, qs("#v2-workbench-body")));
    renderInterfacePanel(composition);
    mountMenubarToolSearch(composition);
  }

  function renderInterfacePanel(composition) {
    // TASK-interface-panel-migration: the interface_panel is the unified TOOL SURFACE —
    // a tool SEARCH bar at the top + the selected tools' visualizations below, in one
    // right-side panel. It is visible on workbench surfaces so search is reachable before
    // a tool is picked. (The old separate visualization_panel region is gone.)
    var region = (composition && composition.regions && composition.regions.interface_panel) || {};
    var aside = qs("#portalInterfacePanel");
    var splitter = document.querySelector(".ide-splitter--interface-panel");
    var title = qs("#portalInterfacePanelTitle");
    var content = qs("#portalInterfacePanelContent");
    if (!aside || !content) return;
    var visible = region.visible !== false && !!region.tool_search;
    if (!visible) {
      aside.setAttribute("hidden", "hidden");
      aside.setAttribute("aria-hidden", "true");
      aside.classList.add("is-collapsed");
      if (splitter) splitter.setAttribute("hidden", "hidden");
      content.innerHTML = "";
      return;
    }
    aside.removeAttribute("hidden");
    aside.setAttribute("aria-hidden", "false");
    aside.classList.remove("is-collapsed");
    if (splitter) splitter.removeAttribute("hidden");

    var panels = Array.isArray(region.panels) ? region.panels : [];
    if (!panels.length && region.tool_id) {
      panels = [{ tool_id: region.tool_id, tool_label: region.tool_label, panel_payload: region.panel_payload }];
    }
    if (title) {
      title.textContent = panels.length === 1 ? (panels[0].tool_label || panels[0].tool_id) : "Tools";
    }
    // Search bar (always present) + one removable box per selected tool.
    var boxesHtml = panels
      .map(function (p) {
        return (
          '<article class="ide-vizBox" data-viz-box="' + escapeHtml(p.tool_id) + '">' +
          '<header class="ide-vizBox__header"><span class="ide-vizBox__title">' +
          escapeHtml(p.tool_label || p.tool_id) + "</span>" +
          '<button type="button" class="ide-vizBox__close" data-viz-box-close data-tool-id="' +
          escapeHtml(p.tool_id) + '" aria-label="Remove ' + escapeHtml(p.tool_label || p.tool_id) +
          '">×</button></header>' +
          '<div class="ide-vizBox__content" data-viz-box-content></div>' +
          "</article>"
        );
      })
      .join("");
    content.innerHTML =
      '<nav class="ide-interfacePanel__toolSearch portal-tool-palette" aria-label="Tool search" data-ip-tool-search-mount></nav>' +
      '<div class="ide-interfacePanel__tools" data-ip-tools>' +
      (boxesHtml || '<p class="ide-interfacePanel__empty">Search for a tool above to open it here.</p>') +
      "</div>";

    mountInterfacePanelSearch(region.tool_search || {});

    var boxes = content.querySelectorAll("[data-viz-box]");
    panels.forEach(function (p, i) {
      var box = boxes[i];
      var body = box && box.querySelector("[data-viz-box-content]");
      if (body) renderToolPanelBody(p, body);
    });
  }

  // Dispatch one {tool_id, tool_label, panel_payload} panel into `bodyNode`: the tool_id-keyed
  // renderer wins, else the declarative container renderer keyed by panel_payload.container
  // (the consolidation-spine path). Shared by the (now-dormant) interface-panel sidebar and
  // the tool overlay so both render byte-identical bodies.
  function renderToolPanelBody(panel, bodyNode) {
    if (!bodyNode) return;
    var p = panel || {};
    var renderers = window.__MYCITE_V2_TOOL_RENDERERS || {};
    var fn = renderers[p.tool_id];
    if (typeof fn !== "function") {
      var containers = window.__MYCITE_V2_CONTAINER_RENDERERS || {};
      fn = containers[((p.panel_payload || {}).container) || ""];
    }
    if (typeof fn === "function") {
      try {
        fn(p.panel_payload || {}, bodyNode);
      } catch (err) {
        bodyNode.innerHTML =
          '<p class="ide-visualizationPanel__error">Tool render failed: ' +
          escapeHtml(err && err.message ? err.message : String(err)) + "</p>";
      }
    } else {
      bodyNode.innerHTML =
        '<p class="ide-visualizationPanel__empty">No client renderer registered for tool <code>' +
        escapeHtml(p.tool_id) + "</code>.</p>";
    }
  }

  // Mount the document-context tool search palette into the interface panel (the tool
  // surface). Selecting a tool appends it to surface_query.tools and reloads, so it
  // renders as a box below the search bar in this same panel.
  function mountInterfacePanelSearch(search) {
    var mount = qs("[data-ip-tool-search-mount]");
    if (!mount) return;
    var ctx = {
      tenantId: search.tenant_id || ((BODY_DATA && BODY_DATA.getAttribute("data-portal-instance-id")) || "fnd"),
      sandboxId: search.sandbox_id || "",
      documentId: search.document_id || "",
      datumAddress: search.datum_address || "",
      onDispatch: function (item) { appendToolToShell(item, mount); },
    };
    function doMount() {
      if (!window.PortalToolPalette || typeof window.PortalToolPalette.mount !== "function") return false;
      window.PortalToolPalette.mount(mount, ctx);
      var input = mount.querySelector("[data-palette-input]");
      var list = mount.querySelector("[data-palette-list]");
      if (input && list) {
        input.addEventListener("focus", function () { list.removeAttribute("hidden"); });
        input.addEventListener("blur", function () {
          setTimeout(function () { list.setAttribute("hidden", "hidden"); }, 200);
        });
      }
      return true;
    }
    if (doMount()) return;
    // tool_palette is startup-critical but the sequential module loader can bring it
    // up AFTER shell_core has already fired the bootstrap render — so on a fresh page
    // load PortalToolPalette may not exist yet the first time this runs, which left the
    // Tools panel permanently empty until some other interaction forced a re-render.
    // Mount as soon as the module registers (one-shot; later renders mount above).
    if (mount.__awaitingPalette) return;
    mount.__awaitingPalette = true;
    var onModuleReady = function (ev) {
      if (ev && ev.detail && ev.detail.module_id && ev.detail.module_id !== "tool_palette") return;
      if (doMount()) {
        mount.__awaitingPalette = false;
        window.removeEventListener("mycite:shell-module-ready", onModuleReady);
      }
    };
    window.addEventListener("mycite:shell-module-ready", onModuleReady);
  }

  // ===== portal-tool-overlay-restructure: menubar search → full-screen tool overlay =====

  // Mount the tool search into the MENU BAR (right side). Selecting a tool opens the overlay
  // (openToolOverlay) instead of appending it to the interface-panel sidebar. Mounts once; its
  // ctx (sandbox/document) is refreshed in place on each render. sandboxId defaults to
  // "agro_erp" so the three live tools list on first load before a doc/sandbox is selected.
  function mountMenubarToolSearch(composition) {
    var mount = qs("[data-menubar-tool-search-mount]");
    if (!mount) return;
    var region = (composition && composition.regions && composition.regions.interface_panel) || {};
    var search = region.tool_search || {};
    var ctx = mount.__menubarCtx;
    if (!ctx) {
      ctx = {
        tenantId: asText(search.tenant_id) || ((BODY_DATA && BODY_DATA.getAttribute("data-portal-instance-id")) || "fnd"),
        sandboxId: asText(search.sandbox_id) || "agro_erp",
        documentId: asText(search.document_id),
        datumAddress: asText(search.datum_address),
        onDispatch: function (item) { openToolOverlay(item, ctx); },
      };
      mount.__menubarCtx = ctx;
    } else {
      ctx.tenantId = asText(search.tenant_id) || ctx.tenantId;
      ctx.sandboxId = asText(search.sandbox_id) || ctx.sandboxId || "agro_erp";
      ctx.documentId = asText(search.document_id);
      ctx.datumAddress = asText(search.datum_address);
    }
    if (mount.__menubarSearchMounted) {
      if (window.PortalToolPalette && typeof window.PortalToolPalette.refresh === "function") {
        window.PortalToolPalette.refresh(mount, ctx);
      }
      return;
    }
    function doMount() {
      if (!window.PortalToolPalette || typeof window.PortalToolPalette.mount !== "function") return false;
      window.PortalToolPalette.mount(mount, ctx);
      var input = mount.querySelector("[data-palette-input]");
      var list = mount.querySelector("[data-palette-list]");
      if (input && list) {
        input.addEventListener("focus", function () { list.removeAttribute("hidden"); });
        input.addEventListener("blur", function () {
          setTimeout(function () { list.setAttribute("hidden", "hidden"); }, 200);
        });
      }
      mount.__menubarSearchMounted = true;
      return true;
    }
    if (doMount()) return;
    // tool_palette can register AFTER shell_core's first render (sequential module loader) —
    // mount as soon as it announces itself (one-shot).
    if (mount.__awaitingPalette) return;
    mount.__awaitingPalette = true;
    var onModuleReady = function (ev) {
      if (ev && ev.detail && ev.detail.module_id && ev.detail.module_id !== "tool_palette") return;
      if (doMount()) {
        mount.__awaitingPalette = false;
        window.removeEventListener("mycite:shell-module-ready", onModuleReady);
      }
    };
    window.addEventListener("mycite:shell-module-ready", onModuleReady);
  }

  function toolPanelsEndpoint(params) {
    var qp = new URLSearchParams();
    if (params.tool) qp.set("tool", params.tool);
    if (params.sandbox) qp.set("sandbox", params.sandbox);
    if (params.tenant) qp.set("tenant_id", params.tenant);
    if (params.document) qp.set("document", params.document);
    if (params.datum) qp.set("datum_address", params.datum);
    var extra = params.extra || {};
    Object.keys(extra).forEach(function (k) {
      var v = extra[k];
      if (v != null && v !== "") qp.set(k, v);
    });
    return "/portal/api/tool-panels?" + qp.toString();
  }

  function fetchToolPanels(params) {
    return fetch(toolPanelsEndpoint(params), {
      method: "GET",
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    })
      .then(function (resp) { if (!resp.ok) throw new Error("tool-panels: " + resp.status); return resp.json(); })
      .then(function (json) { return json && Array.isArray(json.panels) ? json.panels : []; })
      .catch(function () { return []; });
  }

  // Paint fetched tool panel(s) into the overlay content node. The overlay shows one tool at
  // a time (no removable viz-box chrome — the overlay's top-left "x" closes it).
  function paintToolPanels(panels, contentNode) {
    if (!contentNode) return;
    panels = Array.isArray(panels) ? panels : [];
    if (!panels.length) {
      contentNode.innerHTML = '<p class="ide-toolOverlay__empty">No tool to display.</p>';
      return;
    }
    contentNode.innerHTML = panels
      .map(function (p, i) { return '<div class="ide-toolOverlay__panelBody" data-overlay-panel="' + i + '"></div>'; })
      .join("");
    var bodies = contentNode.querySelectorAll("[data-overlay-panel]");
    panels.forEach(function (p, i) {
      if (bodies[i]) renderToolPanelBody(p, bodies[i]);
    });
  }

  function isToolOverlayOpen() {
    var overlay = qs("#portalToolOverlay");
    return !!(overlay && !overlay.hidden);
  }

  function openToolOverlay(item, ctx) {
    var overlay = qs("#portalToolOverlay");
    if (!overlay) return;
    var toolId = (item && item.tool_id) || "";
    if (!toolId) return;
    _overlayState.toolId = toolId;
    _overlayState.label = (item && item.label) || toolId;
    _overlayState.ctx = ctx || _overlayState.ctx || {};
    _overlayState.params = {};
    var titleNode = overlay.querySelector("[data-tool-overlay-title]");
    var contentNode = overlay.querySelector("[data-tool-overlay-content]");
    if (titleNode) titleNode.textContent = _overlayState.label;
    if (contentNode) contentNode.innerHTML = '<p class="ide-toolOverlay__loading">Loading…</p>';
    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    if (document.body) document.body.classList.add("is-modal-open");
    refetchOverlayPanels({});
    var closeBtn = overlay.querySelector("[data-tool-overlay-close]");
    if (closeBtn) closeBtn.focus();
    var list = document.querySelector("[data-menubar-tool-search-mount] [data-palette-list]");
    if (list) list.setAttribute("hidden", "hidden");
  }

  // (Re)fetch the overlay tool's panels with accumulated per-tool params (e.g. a sub-tool's
  // structure selector routed here via setSurfaceQuery) and repaint. Merges `extra` into the
  // running param set so successive selector changes compose.
  function refetchOverlayPanels(extra) {
    var overlay = qs("#portalToolOverlay");
    if (!overlay) return;
    var contentNode = overlay.querySelector("[data-tool-overlay-content]");
    var ctx = _overlayState.ctx || {};
    if (extra) {
      Object.keys(extra).forEach(function (k) { _overlayState.params[k] = extra[k]; });
    }
    fetchToolPanels({
      tool: _overlayState.toolId,
      sandbox: asText(ctx.sandboxId) || "agro_erp",
      tenant: asText(ctx.tenantId),
      document: asText(ctx.documentId),
      datum: asText(ctx.datumAddress),
      extra: _overlayState.params,
    }).then(function (panels) { paintToolPanels(panels, contentNode); });
  }

  function closeToolOverlay() {
    var overlay = qs("#portalToolOverlay");
    if (!overlay) return;
    overlay.hidden = true;
    overlay.setAttribute("aria-hidden", "true");
    if (document.body) document.body.classList.remove("is-modal-open");
    var contentNode = overlay.querySelector("[data-tool-overlay-content]");
    if (contentNode) contentNode.innerHTML = "";
    _overlayState.params = {};
    var input = document.querySelector("[data-menubar-tool-search-mount] [data-palette-input]");
    if (input) input.focus();
  }

  function bindToolOverlay() {
    document.addEventListener("click", function (ev) {
      var t = ev.target;
      if (!t || !t.closest) return;
      if (t.closest("[data-tool-overlay-close]") || t.closest("[data-tool-overlay-dismiss]")) {
        closeToolOverlay();
      }
    });
    document.addEventListener("keydown", function (ev) {
      if ((ev.key === "Escape" || ev.key === "Esc") && isToolOverlayOpen()) closeToolOverlay();
    });
  }

  // surface_query.tools is a comma-joined, ordered, de-duplicated tool-id list.
  function vizToolList(surfaceQuery) {
    var raw = (surfaceQuery && (surfaceQuery.tools || surfaceQuery.tool)) || "";
    var out = [];
    String(raw).split(",").forEach(function (t) {
      var id = t.trim();
      if (id && out.indexOf(id) === -1) out.push(id);
    });
    return out;
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
    // Set one surface_query param and reload, preserving the rest (document, tools,
    // sandbox, lens). Same clone-request+loadShell pattern as the sandbox selector and
    // the tool palette; reachable from tool renderers (separate IIFE) via this global.
    setSurfaceQuery: function (key, value) {
      if (!key) return;
      // portal-tool-overlay-restructure: when the tool overlay is open, a sub-tool param
      // change (e.g. the SAMRAS structure selector inside the agronomics FARM tab) must
      // re-render INSIDE the overlay, not reload the whole shell (which would tear the overlay
      // down). Route it through the overlay refetch. Outside the overlay this path is unchanged.
      if (isToolOverlayOpen()) {
        var patch = {};
        patch[key] = value;
        refetchOverlayPanels(patch);
        return;
      }
      var request = canonicalShellRequestFromEnvelope(lastEnvelope) || lastShellRequest;
      if (!request) return;
      var next = cloneRequest(request);
      next.surface_query =
        next.surface_query && typeof next.surface_query === "object" ? next.surface_query : {};
      next.surface_query[key] = value;
      loadShell(next).catch(function () {});
    },
  };
  if (typeof window.__MYCITE_V2_REGISTER_SHELL_MODULE === "function") {
    window.__MYCITE_V2_REGISTER_SHELL_MODULE("shell_core");
  }
  window.__MYCITE_V2_SHOW_FATAL = showFatal;
  window.__MYCITE_V2_SHELL_CORE_LOADED = true;

  setBootState("core_loaded");
  bindShellChromeEvents();
  bindVisualizationPanelClose();
  bindToolOverlay();
  // Sandbox selection + tool search now live in the control panel + interface panel
  // respectively; both are wired in mountControlPanelControls / renderInterfacePanel
  // after each shell render (the menubar tool-search palette was removed).
  window.addEventListener("popstate", onPopState);

  function bindVisualizationPanelClose() {
    // Each tool box in the interface panel has an 'x' (data-viz-box-close) that removes
    // only that tool from surface_query.tools; the panel empties when the last tool goes.
    // (The legacy whole-panel close lived on the retired visualization_panel DOM — gone.)
    document.addEventListener("click", function (event) {
      var target = event.target;
      if (!target || !target.closest) return;
      var boxClose = target.closest("[data-viz-box-close]");
      if (!boxClose) return;
      var request = canonicalShellRequestFromEnvelope(lastEnvelope) || lastShellRequest;
      if (!request) return;
      var next = cloneRequest(request);
      next.surface_query = next.surface_query && typeof next.surface_query === "object" ? next.surface_query : {};
      var tools = vizToolList(next.surface_query);
      var removeId = boxClose.getAttribute("data-tool-id") || "";
      tools = tools.filter(function (t) { return t !== removeId; });
      delete next.surface_query.tool;
      if (tools.length) {
        next.surface_query.tools = tools.join(",");
      } else {
        delete next.surface_query.tools;
      }
      loadShell(next).catch(function () {});
    });
  }

  function bindSandboxSelector(activeSandbox) {
    var select = qs("[data-sandbox-selector]");
    if (!select) return;
    var sandboxes = Array.isArray(window.__MYCITE_V2_SANDBOXES) ? window.__MYCITE_V2_SANDBOXES : [];
    if (!sandboxes.length) {
      select.setAttribute("hidden", "hidden");
      return;
    }
    // Reflect the ACTIVE sandbox the server resolved (control_panel_controls.sandbox_selector
    // .sandbox_id), preferring an explicit ?sandbox=. WITHOUT this the <select> shows its
    // first option (SANDBOX_DISPLAY_NAMES is sorted, so "agro_erp" leads) while the workbench
    // is really in another sandbox (e.g. "system" on the default /portal/system) — so opening
    // the dropdown and re-picking the already-shown option fires NO `change` event and the
    // user cannot switch INTO it. Sync the value on every render (the options/listener bind
    // once via the guard below) so the control always tracks reality.
    var urlSandbox = "";
    try {
      urlSandbox = new URLSearchParams(window.location.search).get("sandbox") || "";
    } catch (e) {}
    if (select.getAttribute("data-sandbox-bound") !== "true") {
      select.setAttribute("data-sandbox-bound", "true");
      // Populate options.
      select.innerHTML = sandboxes
        .map(function (s) {
          return '<option value="' + escapeHtml(s.token) + '">' + escapeHtml(s.label) + "</option>";
        })
        .join("");
      bindSandboxSelectorChange(select);
    }
    var seed = urlSandbox || (activeSandbox != null ? String(activeSandbox) : "");
    if (seed) select.value = seed;
  }

  function bindSandboxSelectorChange(select) {
    select.addEventListener("change", function () {
      var token = select.value;
      var request = canonicalShellRequestFromEnvelope(lastEnvelope) || lastShellRequest;
      if (!request) return;
      var next = cloneRequest(request);
      next.surface_query = next.surface_query && typeof next.surface_query === "object" ? next.surface_query : {};
      next.surface_query.sandbox_filter = token;
      // Switching sandbox always returns the user to Docs mode and clears
      // any selected document/row that belonged to the old sandbox.
      delete next.surface_query.document;
      delete next.surface_query.row;
      delete next.surface_query.mode;
      // Clear the interface panel too: a tool widget is only valid where its datum docs
      // exist, so switching sandbox empties the open tool containers (re-add per sandbox).
      delete next.surface_query.tools;
      delete next.surface_query.tool;
      loadShell(next).catch(function () {});
    });
  }

  function appendToolToShell(item, mount) {
    var request = canonicalShellRequestFromEnvelope(lastEnvelope) || lastShellRequest;
    if (!request) return;
    var next = cloneRequest(request);
    next.surface_query = next.surface_query && typeof next.surface_query === "object" ? next.surface_query : {};
    var tools = vizToolList(next.surface_query);
    var picked = item.tool_id || "";
    if (picked && tools.indexOf(picked) === -1) tools.push(picked);
    delete next.surface_query.tool;
    next.surface_query.tools = tools.join(",");
    loadShell(next).catch(function () {});
    if (mount) {
      var list = mount.querySelector("[data-palette-list]");
      if (list) list.setAttribute("hidden", "hidden");
    }
  }

  // TASK-interface-panel-migration: the CONTROL PANEL hosts only lens on/off toggles
  // (PortalLensPanel) + the SANDBOX SELECTOR (the sole sandbox-switch affordance now).
  // The Documents/Datums tab strip is presentational (emitted by the region renderer).
  // Tool search moved to the interface panel. Runs after every control-panel render
  // (re-mount/re-bind is idempotent).
  function mountControlPanelControls(region) {
    var controls = region && region.control_panel_controls;
    if (!controls) return;
    if (controls.lenses) {
      var lensMount = qs("[data-cp-lens-mount]");
      if (lensMount && window.PortalLensPanel && typeof window.PortalLensPanel.mount === "function") {
        window.PortalLensPanel.mount(lensMount).catch(function () {});
      }
    }
    if (controls.sandbox_selector) {
      bindSandboxSelector(controls.sandbox_selector.sandbox_id);
    }
  }

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
