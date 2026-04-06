(function () {
  "use strict";

  function qs(selector, root) {
    return (root || document).querySelector(selector);
  }

  function qsa(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  function text(value) {
    return String(value == null ? "" : value).trim();
  }

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function limitText(value, maxLen) {
    var token = text(value);
    var limit = Math.max(8, Number(maxLen) || 64);
    if (token.length <= limit) return token;
    return token.slice(0, limit - 3) + "...";
  }

  function api(path, method, payload) {
    var opts = {
      method: method || "GET",
      credentials: "same-origin",
      headers: { Accept: "application/json" }
    };
    if (payload !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(payload);
    }
    return fetch(path, opts).then(function (response) {
      return response.json().catch(function () {
        return {};
      }).then(function (body) {
        if (!response.ok) {
          var error = new Error(String((body && (body.error || body.message)) || ("HTTP " + response.status)));
          error.status = response.status;
          error.body = body;
          throw error;
        }
        return body;
      });
    });
  }

  function emitShellEvent(name, detail) {
    try {
      document.dispatchEvent(new CustomEvent(name, { detail: detail || {} }));
    } catch (_) {
      /* noop */
    }
  }

  function normalizeModeId(value) {
    return text(value).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  }

  function titleCase(value) {
    return text(value)
      .split(/[_\-\s]+/)
      .filter(Boolean)
      .map(function (token) {
        return token.charAt(0).toUpperCase() + token.slice(1);
      })
      .join(" ");
  }

  function routePrefixForTool(tool) {
    return text(tool && tool.route_prefix);
  }

  function toolContribution(tool) {
    return tool && typeof tool.workbench_contribution === "object" ? tool.workbench_contribution : {};
  }

  function toolInterfaceContribution(tool) {
    return tool && typeof tool.interface_panel_contribution === "object" ? tool.interface_panel_contribution : {};
  }

  function toolInspectorContribution(tool) {
    return tool && typeof tool.inspector_card_contribution === "object" ? tool.inspector_card_contribution : {};
  }

  function toolMutationPolicy(tool) {
    return tool && typeof tool.mutation_policy === "object" ? tool.mutation_policy : {};
  }

  function toolPreviewHooks(tool) {
    return tool && typeof tool.preview_hooks === "object" ? tool.preview_hooks : {};
  }

  function toolApplyHooks(tool) {
    return tool && typeof tool.apply_hooks === "object" ? tool.apply_hooks : {};
  }

  function toolShellComposition(tool) {
    return text(tool && tool.shell_composition_mode).toLowerCase() === "tool" ? "tool" : "system";
  }

  function toolForegroundSurface(tool) {
    return text(tool && tool.foreground_surface).toLowerCase() === "interface_panel"
      ? "interface_panel"
      : "center_workbench";
  }

  var systemWorkspace = qs(".system-center-workspace");
  if (!systemWorkspace) {
    return;
  }

  var els = {
    shell: qs(".ide-shell"),
    inspectorTitle: qs("#portalInspectorTitle"),
    selectionSummary: qs("#systemSelectionSummary"),
    toolContextMount: qs("#systemToolContextMount"),
    compatibleTools: qs("#systemCompatibleTools"),
    systemInspectorRoot: qs("#systemShellInspectorRoot"),
    inspectorCardsRoot: qs("#systemShellInspectorCards"),
    inspectorCardsMount: qs("#systemInspectorCardsMount"),
    inspectorTransientMount: qs("#portalInspectorTransientMount"),
    toolInterfaceRoot: qs("#systemToolInterfaceRoot"),
    toolInterfaceKicker: qs("#systemToolInterfaceKicker"),
    toolInterfaceTitle: qs("#systemToolInterfaceTitle"),
    toolInterfaceMeta: qs("#systemToolInterfaceMeta"),
    toolInterfaceControls: qs("#systemToolInterfaceControls"),
    toolInterfaceBody: qs("#systemToolInterfaceBody"),
    resourcesInspectorEmpty: qs("#dtResourcesInspectorEmpty"),
    mediationWorkbench: qs("#systemMediationWorkbench"),
    mediationTitle: qs("#systemMediationTitle"),
    mediationKicker: qs("#systemMediationKicker"),
    mediationMeta: qs("#systemMediationMeta"),
    mediationModes: qs("#systemMediationModes"),
    mediationBody: qs("#systemMediationBody"),
    mediationCloseBtn: qs("#systemMediationCloseBtn"),
    sideModeControls: qs("#systemToolViewModes")
  };

  function setInterfacePanelRootState(node, active) {
    if (!node) return;
    node.hidden = !active;
    node.setAttribute("aria-hidden", active ? "false" : "true");
    if ("inert" in node) {
      node.inert = !active;
    }
    node.toggleAttribute("data-interface-panel-active", !!active);
  }

  function setInterfacePanelActiveRoot(kind) {
    var token = text(kind).toLowerCase();
    if (els.systemInspectorRoot) {
      setInterfacePanelRootState(els.systemInspectorRoot, token === "system");
    }
    if (els.toolInterfaceRoot) {
      setInterfacePanelRootState(els.toolInterfaceRoot, token === "tool");
    }
    if (els.inspectorTransientMount) {
      if (token !== "transient") {
        els.inspectorTransientMount.innerHTML = "";
      }
      setInterfacePanelRootState(els.inspectorTransientMount, token === "transient");
    }
    var contentRoot = qs("#portalInspectorContent");
    if (contentRoot) {
      contentRoot.setAttribute("data-interface-panel-active-root", token || "");
    }
    if (window.PortalInspector && typeof window.PortalInspector.activatePersistentRoot === "function" && token !== "transient") {
      window.PortalInspector.activatePersistentRoot(token || "system");
    }
  }

  var state = {
    selectedContext: null,
    lastSelectionInput: null,
    activeVerb: "navigate",
    activeToolId: "",
    activeMediationMode: "",
    toolContexts: {},
    providerState: {},
    toolLayer: {
      active: false,
      toolId: "",
      locked: false,
      source: "",
      composition: text(qs(".ide-shell") && qs(".ide-shell").getAttribute("data-shell-composition")) || "system"
    }
  };

  function syncToolLayerUiState() {
    var active = !!(state.toolLayer && state.toolLayer.active);
    var composition = active && text(state.toolLayer.composition).toLowerCase() === "tool" ? "tool" : "system";
    systemWorkspace.classList.toggle("is-tool-layer-active", active && composition === "tool");
    document.body.classList.toggle("portal-tool-layer-active", active && composition === "tool");
    if (window.PortalShell && typeof window.PortalShell.setShellComposition === "function") {
      window.PortalShell.setShellComposition(composition);
    }
  }

  function enterToolLayer(toolId, source, composition) {
    state.toolLayer.active = true;
    state.toolLayer.locked = true;
    state.toolLayer.toolId = text(toolId).toLowerCase();
    state.toolLayer.source = text(source) || "runtime";
    state.toolLayer.composition = text(composition).toLowerCase() === "tool" ? "tool" : "system";
    state.activeVerb = "mediate";
    syncToolLayerUiState();
  }

  function exitToolLayer() {
    state.toolLayer.active = false;
    state.toolLayer.locked = false;
    state.toolLayer.toolId = "";
    state.toolLayer.source = "";
    state.toolLayer.composition = "system";
    syncToolLayerUiState();
  }

  function selectionOrigin(detail) {
    return text(detail && detail.origin).toLowerCase();
  }

  function isExplicitSelectionOrigin(origin) {
    return ["user_select", "user_file_focus", "user_task_change", "user_explicit"].indexOf(origin) !== -1;
  }

  function shouldIgnoreSelectionInput(detail) {
    if (!state.toolLayer.active || !state.toolLayer.locked) return false;
    var origin = selectionOrigin(detail);
    if (!origin) return true;
    return !isExplicitSelectionOrigin(origin);
  }

  function selectionHint() {
    return text(systemWorkspace.getAttribute("data-system-empty-selection")) || "Select a file or datum to activate the SYSTEM workbench.";
  }

  function activeCompatibleTools() {
    return state.selectedContext && Array.isArray(state.selectedContext.compatible_tools)
      ? state.selectedContext.compatible_tools.slice()
      : [];
  }

  function findCompatibleTool(toolId) {
    var token = text(toolId).toLowerCase();
    if (!token) return null;
    var tools = activeCompatibleTools();
    for (var i = 0; i < tools.length; i += 1) {
      var tool = tools[i];
      if (text(tool && tool.tool_id).toLowerCase() === token) {
        return tool;
      }
    }
    return null;
  }

  function activeTool() {
    return findCompatibleTool(state.activeToolId);
  }

  function toolOwnsShellState(tool) {
    if (!tool || typeof tool !== "object") return true;
    if (tool.owns_shell_state === false) return false;
    return text(tool.surface_mode || "tool_shell") !== "mediation_only";
  }

  function toolContext(toolId) {
    return state.toolContexts[text(toolId).toLowerCase()] || null;
  }

  function providerStateFor(toolId) {
    var token = text(toolId).toLowerCase();
    if (!token) return {};
    if (!state.providerState[token] || typeof state.providerState[token] !== "object") {
      state.providerState[token] = {};
    }
    return state.providerState[token];
  }

  function activeToolProvider() {
    var tool = activeTool();
    if (!tool) return genericMediationProvider;
    return mediationProviders[text(tool.tool_id).toLowerCase()] || genericMediationProvider;
  }

  function reconcileActiveTool() {
    var compatibleById = {};
    activeCompatibleTools().forEach(function (tool) {
      compatibleById[text(tool && tool.tool_id).toLowerCase()] = true;
    });
    Object.keys(state.toolContexts).forEach(function (token) {
      if (compatibleById[token]) return;
      delete state.toolContexts[token];
      delete state.providerState[token];
    });
    Object.keys(state.providerState).forEach(function (token) {
      if (compatibleById[token]) return;
      delete state.providerState[token];
    });
    if (state.activeToolId && !findCompatibleTool(state.activeToolId)) {
      state.activeToolId = "";
      state.activeMediationMode = "";
    }
  }

  function setActiveVerbButtons() {
    qsa("[data-shell-verb]").forEach(function (btn) {
      var token = text(btn.getAttribute("data-shell-verb"));
      btn.classList.toggle("is-active", token === state.activeVerb);
    });
  }

  function renderSelectionSummary() {
    if (!els.selectionSummary) return;
    var ctx = state.selectedContext;
    if (!ctx || !ctx.selection) {
      els.selectionSummary.className = "ide-controlpanel__empty";
      els.selectionSummary.textContent = selectionHint();
      if (els.resourcesInspectorEmpty) els.resourcesInspectorEmpty.hidden = false;
      return;
    }
    var selection = ctx.selection || {};
    var family = ctx.family || {};
    var resolved = ctx.resolved_archetype || {};
    var systemState = ctx.system_state || {};
    var aitas = systemState.aitas && typeof systemState.aitas === "object" ? systemState.aitas : {};
    var timeState = aitas.time && typeof aitas.time === "object" ? aitas.time : {};
    var attentionAddress = text(systemState.attention_address || "");
    var directive = text(systemState.directive || state.activeVerb || "navigate");
    var timeAddress = text(timeState.value || "");
    els.selectionSummary.className = "data-tool__resourcesDatumCard";
    if (els.resourcesInspectorEmpty) els.resourcesInspectorEmpty.hidden = true;
    els.selectionSummary.innerHTML =
      "<div><strong>Attention</strong><br/><code title=\"" + esc(attentionAddress || selection.selected_ref_or_document_id || "") + "\">" + esc(limitText(attentionAddress || selection.selected_ref_or_document_id || "", 96)) + "</code></div>" +
      "<div><strong>Label</strong><br/><span>" + esc(selection.display_name || "") + "</span></div>" +
      "<div><strong>Directive</strong><br/><span>" + esc(directive || "navigate") + "</span></div>" +
      "<div><strong>Archetype</strong><br/><span>" + esc(resolved.family || family.kind || "datum") + "</span></div>" +
      "<div><strong>Time</strong><br/><code title=\"" + esc(timeAddress || "not selected") + "\">" + esc(limitText(timeAddress || "not selected", 96)) + "</code></div>";
  }

  function renderCompatibleTools() {
    if (!els.compatibleTools) return;
    els.compatibleTools.innerHTML = "";
    els.compatibleTools.hidden = true;
  }

  function renderCardKeyValueRows(fields) {
    var rows = [];
    Object.keys(fields || {}).forEach(function (key) {
      var value = fields[key];
      if (value == null || value === "") return;
      rows.push(
        '<div class="tool-valueGrid__row">' +
          '<dt class="tool-valueGrid__term">' + esc(String(key)) + "</dt>" +
          '<dd class="tool-valueGrid__value">' + esc(String(value)) + "</dd>" +
        "</div>"
      );
    });
    if (!rows.length) return "";
    return '<dl class="tool-valueGrid">' + rows.join("") + "</dl>";
  }

  function renderInterfacePanelCardBody(card, body) {
    if (body && typeof body === "object") {
      if (body.identity && body.smtp && body.verification) {
        var identity = body.identity && typeof body.identity === "object" ? body.identity : {};
        var smtp = body.smtp && typeof body.smtp === "object" ? body.smtp : {};
        var verification = body.verification && typeof body.verification === "object" ? body.verification : {};
        var provider = body.provider && typeof body.provider === "object" ? body.provider : {};
        var workflow = body.workflow && typeof body.workflow === "object" ? body.workflow : {};
        var missing = Array.isArray(workflow.missing_required_now) ? workflow.missing_required_now : [];
        var html = "";
        html += renderCardKeyValueRows({
          domain: text(identity.domain),
          profile: text(identity.profile_id),
          tenant: text(identity.tenant_id),
          "single user": text(identity.single_user_email || identity.single_user_msn_id),
          region: text(identity.region),
          "send as": text(smtp.send_as_email),
          "smtp host": text(smtp.host),
          "smtp port": text(smtp.port),
          "smtp username": text(smtp.username),
          "credentials source": text(smtp.credentials_source),
          "forward to": text(smtp.forward_to_email),
          "forwarding status": text(smtp.forwarding_status),
          "verification status": text(verification.status),
          "verification code": text(verification.code),
          "verification link": text(verification.link),
          "verification email": text(verification.email_received_at),
          "verified at": text(verification.verified_at),
          "portal state": text(verification.portal_state),
          "provider send-as": text(provider.gmail_send_as_status),
          "ses identity": text(provider.aws_ses_identity_status),
          "last checked": text(provider.last_checked_at),
          "handoff ready": workflow.is_ready_for_user_handoff ? "yes" : "no",
          "send-as confirmed": workflow.is_send_as_confirmed ? "yes" : "no"
        });
        if (missing.length) {
          html += "<p><strong>Missing required now</strong></p><ul class=\"fnd-ebi-warnings\">";
          missing.forEach(function (item) { html += "<li>" + esc(text(item)) + "</li>"; });
          html += "</ul>";
        }
        return html || '<pre class="jsonblock">' + esc(JSON.stringify(body, null, 2)) + "</pre>";
      }
      if (Object.prototype.hasOwnProperty.call(body, "traffic_summary") || Object.prototype.hasOwnProperty.call(body, "events_file")) {
        var traffic = body.traffic_summary && typeof body.traffic_summary === "object" ? body.traffic_summary : {};
        var events = body.event_summary && typeof body.event_summary === "object" ? body.event_summary : {};
        var accessLog = body.access_log && typeof body.access_log === "object" ? body.access_log : {};
        var errorLog = body.error_log && typeof body.error_log === "object" ? body.error_log : {};
        var eventsFile = body.events_file && typeof body.events_file === "object" ? body.events_file : {};
        var frontend = body.frontend && typeof body.frontend === "object" ? body.frontend : {};
        var warnings = Array.isArray(body.warnings) ? body.warnings : [];
        var html2 = "";
        html2 += renderCardKeyValueRows({
          domain: text(body.domain),
          "site root": text(body.site_root),
          "analytics root": text(body.analytics_root),
          "access log": text(accessLog.state || (accessLog.present ? "present" : "missing")),
          "error log": text(errorLog.state || (errorLog.present ? "present" : "missing")),
          "events file": text(eventsFile.state || (eventsFile.present ? "present" : "missing")),
          "frontend instrumentation": frontend.client_instrumentation_detected ? "detected" : "not detected",
          "robots.txt": frontend.robots_present ? "present" : "missing",
          "sitemap.xml": frontend.sitemap_present ? "present" : "missing",
          "requests 30d": String(traffic.requests_30d || 0),
          "real page req 30d": String(traffic.real_page_requests_30d || 0),
          "events 30d": String(events.events_30d || 0),
          "unique visitors": String(traffic.unique_visitors_approx_30d || 0),
          "bot share": ((Number(traffic.bot_share) || 0) * 100).toFixed(1) + "%"
        });
        if (warnings.length) {
          html2 += "<ul class=\"fnd-ebi-warnings\">";
          warnings.slice(0, 8).forEach(function (warning) { html2 += "<li>" + esc(text(warning)) + "</li>"; });
          html2 += "</ul>";
        }
        return html2 || '<pre class="jsonblock">' + esc(JSON.stringify(body, null, 2)) + "</pre>";
      }
    }
    return '<pre class="jsonblock">' + esc(JSON.stringify(body || {}, null, 2)) + "</pre>";
  }

  function renderInspectorCards() {
    if (!els.inspectorCardsRoot || !els.inspectorCardsMount) return;
    var tool = activeTool();
    var toolCtx = tool ? toolContext(tool.tool_id) : null;
    var cards = [];
    if (toolCtx && Array.isArray(toolCtx.inspector_cards)) {
      cards = cards.concat(toolCtx.inspector_cards);
    } else if (state.selectedContext && Array.isArray(state.selectedContext.inspector_cards)) {
      cards = cards.concat(state.selectedContext.inspector_cards);
    }
    var hasProfileCards = cards.some(function (card) {
      return text(card && card.kind).toLowerCase() === "profile";
    });
    if (hasProfileCards) {
      cards = cards.filter(function (card) {
        var kind = text(card && card.kind).toLowerCase();
        if (kind === "profile") return true;
        var cardId = text(card && card.card_id).toLowerCase();
        if (cardId.endsWith("-collection") || cardId.endsWith("-profiles")) return false;
        return kind !== "metadata";
      });
    }
    els.inspectorCardsMount.innerHTML = "";
    els.inspectorCardsRoot.hidden = cards.length === 0;
    cards.forEach(function (card) {
      var article = document.createElement("article");
      article.className = "card";
      var body = card && card.body && typeof card.body === "object" ? card.body : {};
      article.innerHTML =
        '<div class="card__kicker">' + esc(card.kind || "Interface") + "</div>" +
        '<div class="card__title">' + esc(card.title || "Card") + "</div>" +
        '<div class="card__body">' +
        (card.summary ? "<p>" + esc(card.summary) + "</p>" : "") +
        renderInterfacePanelCardBody(card, body) +
        "</div>";
      els.inspectorCardsMount.appendChild(article);
    });
  }

  function ensureInterfacePanelForServiceTool(tool) {
    if (!tool || typeof tool !== "object") return;
    if (toolShellComposition(tool) !== "tool" || toolForegroundSurface(tool) !== "interface_panel") return;
    if (window.PortalShell && typeof window.PortalShell.setInspectorOpen === "function") {
      window.PortalShell.setInspectorOpen(true, false);
    }
  }

  function ensureToolContext(tool, force) {
    var token = text(tool && tool.tool_id).toLowerCase();
    if (!token) return Promise.resolve({});
    if (state.toolContexts[token] && !force) {
      return Promise.resolve(state.toolContexts[token]);
    }
    var interfaceContribution = toolInterfaceContribution(tool);
    var inspector = toolInspectorContribution(tool);
    var contribution = toolContribution(tool);
    var route = text(interfaceContribution.config_context_route || inspector.config_context_route || contribution.activation_route);
    if (!route) {
      state.toolContexts[token] = {};
      return Promise.resolve(state.toolContexts[token]);
    }
    return api(route).then(function (payload) {
      state.toolContexts[token] = payload || {};
      renderAll();
      return state.toolContexts[token];
    });
  }

  function renderMediationModes(tool, provider) {
    if (!els.mediationModes) return;
    els.mediationModes.innerHTML = "";
    var modes = provider.modes(tool);
    var allowedIds = modes.map(function (entry) { return entry.id; });
    if (!allowedIds.length) {
      modes = [{ id: "overview", label: "Overview" }];
      allowedIds = ["overview"];
    }
    if (allowedIds.indexOf(state.activeMediationMode) === -1) {
      state.activeMediationMode = provider.defaultMode(tool);
      if (allowedIds.indexOf(state.activeMediationMode) === -1) {
        state.activeMediationMode = allowedIds[0];
      }
    }
    modes.forEach(function (entry) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "data-tool__actionBtn" + (state.activeMediationMode === entry.id ? " is-active" : "");
      btn.textContent = entry.label;
      btn.addEventListener("click", function () {
        state.activeMediationMode = entry.id;
        renderMediationWorkspaceBody();
      });
      els.mediationModes.appendChild(btn);
    });
  }

  function renderToolInterfaceModes(tool, provider) {
    if (!els.toolInterfaceControls) return;
    els.toolInterfaceControls.innerHTML = "";
    if (typeof provider.showModes === "function" && !provider.showModes(tool)) {
      els.toolInterfaceControls.hidden = true;
      return;
    }
    els.toolInterfaceControls.hidden = false;
    var modes = provider.modes(tool);
    var allowedIds = modes.map(function (entry) { return entry.id; });
    if (!allowedIds.length) {
      els.toolInterfaceControls.hidden = true;
      return;
    }
    if (allowedIds.indexOf(state.activeMediationMode) === -1) {
      state.activeMediationMode = provider.defaultMode(tool);
      if (allowedIds.indexOf(state.activeMediationMode) === -1) {
        state.activeMediationMode = allowedIds[0];
      }
    }
    modes.forEach(function (entry) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "data-tool__actionBtn" + (state.activeMediationMode === entry.id ? " is-active" : "");
      btn.textContent = entry.label;
      btn.setAttribute("data-tool-interface-mode", entry.id);
      btn.addEventListener("click", function () {
        state.activeMediationMode = entry.id;
        renderAll();
      });
      els.toolInterfaceControls.appendChild(btn);
    });
  }

  function activeToolUsesInterfacePanel(tool) {
    return !!(tool && state.toolLayer.active && toolShellComposition(tool) === "tool" && toolForegroundSurface(tool) === "interface_panel");
  }

  function renderToolContextMount() {
    if (!els.toolContextMount) return;
    var tool = activeTool();
    if (!activeToolUsesInterfacePanel(tool)) {
      els.toolContextMount.hidden = true;
      els.toolContextMount.innerHTML = "";
      return;
    }
    var provider = activeToolProvider();
    var html = typeof provider.renderControlPanel === "function" ? provider.renderControlPanel(tool) : "";
    if (!text(html)) {
      els.toolContextMount.hidden = true;
      els.toolContextMount.innerHTML = "";
      return;
    }
    els.toolContextMount.hidden = false;
    els.toolContextMount.innerHTML = html;
    if (typeof provider.bindControlPanel === "function") {
      provider.bindControlPanel(tool);
    }
  }

  function renderToolInterfaceLens() {
    if (!els.toolInterfaceRoot || !els.toolInterfaceBody) return;
    var tool = activeTool();
    if (!tool && state.toolLayer.active && text(state.toolLayer.composition).toLowerCase() === "tool") {
      setInterfacePanelActiveRoot("tool");
      if (els.inspectorTitle && !text(els.inspectorTitle.textContent)) {
        els.inspectorTitle.textContent = "Tool mediation";
      }
      return;
    }
    if (!activeToolUsesInterfacePanel(tool)) {
      setInterfacePanelActiveRoot("system");
      if (els.inspectorTitle && text(els.inspectorTitle.textContent).toLowerCase() !== "overview") {
        els.inspectorTitle.textContent = "Overview";
      }
      return;
    }
    var provider = activeToolProvider();
    setInterfacePanelActiveRoot("tool");
    if (els.inspectorTitle) {
      els.inspectorTitle.textContent = provider.title(tool);
    }
    if (els.toolInterfaceKicker) {
      els.toolInterfaceKicker.textContent = provider.kicker(tool);
    }
    if (els.toolInterfaceTitle) {
      var showModes = !(typeof provider.showModes === "function") || provider.showModes(tool);
      els.toolInterfaceTitle.textContent = showModes
        ? provider.title(tool) + " · " + titleCase(state.activeMediationMode || provider.defaultMode(tool))
        : provider.title(tool);
    }
    if (els.toolInterfaceMeta) {
      els.toolInterfaceMeta.textContent = provider.meta(tool);
    }
    renderToolInterfaceModes(tool, provider);
    try {
      els.toolInterfaceBody.innerHTML = typeof provider.renderInterface === "function"
        ? provider.renderInterface(tool, state.activeMediationMode)
        : provider.render(tool, state.activeMediationMode);
      if (typeof provider.bindInterface === "function") {
        provider.bindInterface(tool);
      }
    } catch (err) {
      if (els.toolInterfaceMeta) {
        els.toolInterfaceMeta.textContent = err && err.message ? err.message : "Interface lens failed to render.";
      }
      els.toolInterfaceBody.innerHTML =
        '<article class="card"><div class="card__kicker">Interface unavailable</div>' +
        '<div class="card__title">Tool mediation lens failed safely</div>' +
        '<div class="card__body"><p>The interface-panel lens hit a runtime error and was isolated from the shared shell host.</p></div></article>';
    }
  }

  function renderMediationWorkspaceBody() {
    if (!els.mediationBody || !els.mediationWorkbench) return;
    var tool = activeTool();
    if (state.activeVerb !== "mediate" || !tool || activeToolUsesInterfacePanel(tool)) {
      if (els.sideModeControls) els.sideModeControls.hidden = true;
      els.mediationWorkbench.hidden = true;
      if (els.mediationCloseBtn) els.mediationCloseBtn.hidden = true;
      return;
    }
    var provider = activeToolProvider();
    els.mediationWorkbench.hidden = false;
    if (els.mediationCloseBtn) els.mediationCloseBtn.hidden = false;
    if (els.mediationTitle) els.mediationTitle.textContent = provider.title(tool);
    if (els.mediationKicker) els.mediationKicker.textContent = provider.kicker(tool);
    if (els.mediationMeta) els.mediationMeta.textContent = provider.meta(tool);
    renderMediationModes(tool, provider);
    renderToolSideModeControls(tool, provider);
    try {
      els.mediationBody.innerHTML = provider.render(tool, state.activeMediationMode);
      if (typeof provider.bind === "function") {
        provider.bind(tool);
      }
    } catch (err) {
      if (els.sideModeControls) els.sideModeControls.hidden = true;
      if (els.mediationMeta) {
        els.mediationMeta.textContent = err && err.message
          ? err.message
          : "Mediation provider failed to render.";
      }
      els.mediationBody.innerHTML =
        '<article class="card"><div class="card__kicker">Mediation unavailable</div>' +
        '<div class="card__title">Provider render failed safely</div>' +
        '<div class="card__body"><p>The tool mediation hit a runtime error and was isolated from the base SYSTEM surface.</p></div></article>';
    }
  }

  function renderToolSideModeControls(tool, provider) {
    if (!els.sideModeControls) return;
    var toolId = text(tool && tool.tool_id).toLowerCase();
    if (toolId !== "agro_erp") {
      els.sideModeControls.hidden = true;
      return;
    }
    els.sideModeControls.hidden = false;
    qsa("[data-agro-side-mode]", els.sideModeControls).forEach(function (btn) {
      var mode = text(btn.getAttribute("data-agro-side-mode"));
      btn.classList.toggle("is-active", state.activeMediationMode === mode);
      btn.onclick = function () {
        state.activeMediationMode = mode;
        renderMediationWorkspaceBody();
      };
    });
  }

  function renderAll() {
    syncToolLayerUiState();
    reconcileActiveTool();
    setActiveVerbButtons();
    renderSelectionSummary();
    renderCompatibleTools();
    renderToolContextMount();
    renderInspectorCards();
    renderToolInterfaceLens();
    renderMediationWorkspaceBody();
  }

  function openTool(toolId) {
    var tool = findCompatibleTool(toolId);
    if (!tool) return;
    state.activeToolId = text(tool.tool_id);
    state.toolLayer.composition = toolShellComposition(tool);
    if (state.toolLayer.active && text(tool.tool_id).toLowerCase() === text(state.toolLayer.toolId)) {
      state.activeVerb = "mediate";
    }
    state.activeMediationMode = activeToolProvider().defaultMode(tool);
    ensureInterfacePanelForServiceTool(tool);
    renderAll();
    activeToolProvider().ensureReady(tool, false).catch(function (err) {
      if (els.mediationMeta) {
        els.mediationMeta.textContent = err && err.message ? err.message : "Mediation workspace could not open.";
      }
    }).finally(function () {
      renderAll();
    });
  }

  function renderTaxonomyTree(node, depth) {
    if (!node || typeof node !== "object" || depth > 4) {
      return "";
    }
    var label = text(node.label || node.identifier || node.title);
    var identifier = text(node.identifier);
    var children = Array.isArray(node.children) ? node.children : [];
    var html = "<li><strong>" + esc(label || identifier || "node") + "</strong>";
    if (identifier) {
      html += " <code>" + esc(identifier) + "</code>";
    }
    if (children.length) {
      html += "<ul>";
      children.slice(0, 12).forEach(function (child) {
        html += renderTaxonomyTree(child, depth + 1);
      });
      html += "</ul>";
    }
    html += "</li>";
    return html;
  }

  var genericMediationProvider = {
    defaultMode: function (tool) {
      var contribution = toolContribution(tool);
      return normalizeModeId(contribution.default_mode || "overview") || "overview";
    },
    modes: function (tool) {
      var contribution = toolContribution(tool);
      var seen = { overview: true };
      var out = [{ id: "overview", label: "Overview" }];
      var rawModes = Array.isArray(contribution.modes) ? contribution.modes : [];
      rawModes.forEach(function (mode) {
        var id = normalizeModeId(mode);
        if (!id || seen[id]) return;
        seen[id] = true;
        out.push({ id: id, label: titleCase(mode) });
      });
      return out;
    },
    title: function (tool) {
      return text(tool && (tool.label || tool.tool_id)) || "Compatible mediation";
    },
    kicker: function (tool) {
      var contribution = toolContribution(tool);
      return text(contribution.label || contribution.workspace_id) || "Compatible mediation workspace";
    },
    meta: function (tool) {
      var contribution = toolContribution(tool);
      var sourceCount = Array.isArray(tool && tool.supported_source_contracts) ? tool.supported_source_contracts.length : 0;
      return [
        "Workspace: " + (text(contribution.workspace_id) || "shared"),
        "Sources: " + String(sourceCount),
        "Verbs: " + (Array.isArray(tool && tool.supported_verbs) ? tool.supported_verbs.join(", ") : "mediate")
      ].join(" · ");
    },
    ensureReady: function (tool, force) {
      return ensureToolContext(tool, force);
    },
    render: function (tool, mode) {
      var contribution = toolContribution(tool);
      var config = toolContext(tool.tool_id) || {};
      var mutationPolicy = toolMutationPolicy(tool);
      return (
        "<p><strong>Mode:</strong> " + esc(titleCase(mode || "overview")) + "</p>" +
        "<p><strong>Launch path:</strong> SYSTEM Mediate is the canonical entry for this provider.</p>" +
        '<details class="data-tool__advanced" open><summary>Contribution</summary><pre class="jsonblock">' +
        esc(JSON.stringify(contribution, null, 2)) +
        "</pre></details>" +
        '<details class="data-tool__advanced"><summary>Mutation policy</summary><pre class="jsonblock">' +
        esc(JSON.stringify(mutationPolicy, null, 2)) +
        "</pre></details>" +
        '<details class="data-tool__advanced"><summary>Config context</summary><pre class="jsonblock">' +
        esc(JSON.stringify(config, null, 2)) +
        "</pre></details>"
      );
    },
    bind: function () {
      return;
    }
  };

  function agroModeId(value) {
    var token = normalizeModeId(value);
    if (token === "taxonomy_browse") return "taxonomy";
    if (token === "supplier_browse") return "supplier";
    if (token === "product_profile_compose") return "product";
    if (token === "supply_log_compose") return "invoice";
    if (token === "preview_apply") return "preview";
    return token || "overview";
  }

  function agroState(tool) {
    return providerStateFor(tool && tool.tool_id);
  }

  function ensureAgroModel(tool, force) {
    var bucket = agroState(tool);
    if (bucket.model && !force) {
      return Promise.resolve(bucket.model);
    }
    return api(routePrefixForTool(tool) + "/model.json").then(function (payload) {
      bucket.model = payload || {};
      var timeCtx = bucket.model.time_context && typeof bucket.model.time_context === "object" ? bucket.model.time_context : {};
      if (!bucket.timeContext || typeof bucket.timeContext !== "object") {
        bucket.timeContext = {
          selected_scope: text(timeCtx.selected_scope),
          specificity: text(timeCtx.specificity),
          calendar: timeCtx.calendar && typeof timeCtx.calendar === "object" ? timeCtx.calendar : {},
          objects: Array.isArray(timeCtx.objects) ? timeCtx.objects : []
        };
      }
      return bucket.model;
    });
  }

  function ensureAgroSession(tool, force) {
    var bucket = agroState(tool);
    return ensureToolContext(tool, force).then(function (configContext) {
      var activation = configContext && typeof configContext.activation === "object" ? configContext.activation : {};
      var requestPayload = activation.request_payload && typeof activation.request_payload === "object" ? activation.request_payload : {};
      if (!activation.can_open || !Object.keys(requestPayload).length) {
        bucket.lastError = "";
        bucket.sessionId = "";
        bucket.readback = {};
        return { ok: true, empty_view: true, sandbox_session_id: "" };
      }
      if (bucket.sessionId && !force) {
        bucket.lastError = "";
        return { ok: true, sandbox_session_id: bucket.sessionId };
      }
      return api(routePrefixForTool(tool) + "/mvp/resource/select_or_load", "POST", requestPayload).then(function (payload) {
        bucket.sessionId = text(payload && payload.sandbox_session_id);
        bucket.readback = payload || {};
        bucket.lastError = "";
        return payload || {};
      });
    });
  }

  function renderAgroOverview(tool) {
    var ctx = toolContext(tool.tool_id) || {};
    var mutationPolicy = toolMutationPolicy(tool);
    return (
      "<p><strong>Binding truth:</strong> " + esc(ctx.binding_truth || mutationPolicy.binding_truth || "config") + "</p>" +
      "<p><strong>Browse truth:</strong> " + esc(ctx.browse_truth || mutationPolicy.browse_truth || "inherited_resources") + "</p>" +
      "<p><strong>Staging truth:</strong> " + esc(ctx.staging_truth || mutationPolicy.sandbox_truth || "reduced_local_staging") + "</p>" +
      "<p><strong>Commit truth:</strong> " + esc(ctx.commit_truth || mutationPolicy.anthology_truth || "semantic_minimum_commit") + "</p>" +
      '<pre class="jsonblock">' + esc(JSON.stringify(ctx.resource_role_bindings || {}, null, 2)) + "</pre>"
    );
  }

  function setSelectedTimeContext(scopeToken) {
    var scope = text(scopeToken);
    if (!scope) return;
    var ctx = state.selectedContext && typeof state.selectedContext === "object" ? state.selectedContext : null;
    if (!ctx) return;
    var systemState = ctx.system_state && typeof ctx.system_state === "object" ? ctx.system_state : {};
    var aitas = systemState.aitas && typeof systemState.aitas === "object" ? systemState.aitas : {};
    aitas.time = { kind: "time_address", value: scope };
    systemState.aitas = aitas;
    ctx.system_state = systemState;
    state.selectedContext = ctx;
  }

  function parseTimeScopeSegments(scopeToken) {
    var token = text(scopeToken);
    if (!token) return [];
    var parts = token.split("-");
    var out = [];
    for (var i = 0; i < parts.length; i += 1) {
      var n = Number(parts[i]);
      if (!Number.isFinite(n)) return [];
      out.push(n);
    }
    return out;
  }

  function hopsScopeFromCalendar(calendar, overrides) {
    var cal = calendar && typeof calendar === "object" ? calendar : {};
    var patch = overrides && typeof overrides === "object" ? overrides : {};
    var prefix = Array.isArray(cal.prefix) ? cal.prefix.slice(0, 2) : [0, 0];
    var segmentRadices = Array.isArray(cal.segment_radices) ? cal.segment_radices : [];
    var year = Number(patch.year != null ? patch.year : cal.year || 0);
    var month = Number(patch.month != null ? patch.month : cal.month || 0);
    var day = Number(patch.day != null ? patch.day : cal.day || 0);
    var depth = Number(patch.depth != null ? patch.depth : 3);
    if (!Number.isFinite(depth) || depth < 1) depth = 1;
    function clampByRadix(value, idx) {
      var radix = Number(segmentRadices[idx] || 1000);
      var raw = Number(value || 0);
      if (!Number.isFinite(raw)) raw = 0;
      if (!Number.isFinite(radix) || radix <= 0) return Math.max(0, raw);
      return Math.max(0, Math.min(raw, radix - 1));
    }
    var temporal = [clampByRadix(year, 0)];
    if (depth >= 2) temporal.push(clampByRadix(month, 1));
    if (depth >= 3) temporal.push(clampByRadix(day, 2));
    var all = prefix.concat(temporal).map(function (n) { return String(Math.trunc(Number(n) || 0)); });
    return all.join("-");
  }

  function selectedScopeFromCalendar(calendar) {
    var cal = calendar && typeof calendar === "object" ? calendar : {};
    var token = text(cal.selected_scope);
    if (token) return token;
    return hopsScopeFromCalendar(cal, { depth: 1 });
  }

  function renderChronologyWorkbench(tool) {
    var bucket = agroState(tool);
    var calendar = bucket.timeContext && bucket.timeContext.calendar && typeof bucket.timeContext.calendar === "object"
      ? bucket.timeContext.calendar
      : {};
    var monthLabels = Array.isArray(calendar.month_labels) ? calendar.month_labels : [];
    var year = Number(calendar.year || 0);
    var selectedMonth = Number(calendar.month || 0);
    var selectedDay = Number(calendar.day || 0);
    var dayCount = Number(calendar.days_in_month || 31);
    var selectedScope = text(bucket.timeContext && bucket.timeContext.selected_scope);
    if (selectedScope) setSelectedTimeContext(selectedScope);
    var scopeSegments = parseTimeScopeSegments(selectedScopeFromCalendar(calendar));
    var prefixText = scopeSegments.length >= 2 ? (String(scopeSegments[0]) + "-" + String(scopeSegments[1])) : "";
    var monthCount = Math.max(1, Number(calendar.months_in_year || monthLabels.length || 12));
    if (!monthLabels.length) {
      monthLabels = Array(monthCount).fill(0).map(function (_, idx) { return "M" + String(idx + 1); });
    }
    var visibleObjects = Array.isArray(bucket.timeContext && bucket.timeContext.objects) ? bucket.timeContext.objects : [];
    var monthArc = monthLabels.map(function (label, idx) {
      var month = idx;
      var active = month === selectedMonth ? " is-active" : "";
      return '<button type="button" class="agro-time__month' + active + '" data-agro-time-scope="' + esc(hopsScopeFromCalendar(calendar, { year: year, month: month, depth: 2 })) + '">' + esc(label) + "</button>";
    }).join("");
    var dayTicks = Array(Math.max(dayCount, 1)).fill(0).map(function (_, idx) {
      var d = idx;
      var active = d === selectedDay ? " is-active" : "";
      return '<button type="button" class="agro-time__tick' + active + '" data-agro-time-scope="' + esc(hopsScopeFromCalendar(calendar, { year: year, month: selectedMonth, day: d, depth: 3 })) + '" title="Day ' + String(d) + '"></button>';
    }).join("");
    var dayRow = Array(Math.max(dayCount, 1)).fill(0).map(function (_, idx) {
      var d = idx;
      var active = d === selectedDay ? " is-active" : "";
      return '<button type="button" class="agro-time__dayCell' + active + '" data-agro-time-scope="' + esc(hopsScopeFromCalendar(calendar, { year: year, month: selectedMonth, day: d, depth: 3 })) + '">' + String(d) + "</button>";
    }).join("");
    var objectRows = visibleObjects.length
      ? (
        '<ul class="agro-time__objects">' +
        visibleObjects.slice(0, 16).map(function (item) {
          var stamp = Array.isArray(item.time_stamp) ? item.time_stamp : [];
          return '<li><strong>' + esc(item.label || item.object_id || "object") + '</strong><small>' + esc((stamp[0] || "") + " -> " + (stamp[1] || "")) + "</small></li>";
        }).join("") +
        "</ul>"
      )
      : '<p class="data-tool__empty">No objects intersect the selected time scope.</p>';
    return (
      '<section class="agro-time" aria-label="Chronological address workbench">' +
      '<div class="agro-time__topTicks" aria-hidden="true">' + dayTicks + "</div>" +
      '<div class="agro-time__arc">' +
      '<div class="agro-time__months">' + monthArc + "</div>" +
      '<div class="agro-time__yearCore"><strong>' + esc(String(year)) + "</strong><span>GMT-4</span></div>" +
      "</div>" +
      '<div class="agro-time__yearRail">' +
      '<button type="button" class="agro-time__yearNav" data-agro-time-nav="prev" aria-label="Previous year">' +
      '<span class="agro-time__yearTag">' + esc(String(year - 1)) + '</span><span class="agro-time__arrow">◀</span></button>' +
      '<div class="agro-time__scope"><strong>' + esc(selectedScope || hopsScopeFromCalendar(calendar, { depth: 1 })) + "</strong><small>" + esc(prefixText) + "</small></div>" +
      '<button type="button" class="agro-time__yearNav" data-agro-time-nav="next" aria-label="Next year">' +
      '<span class="agro-time__yearTag">' + esc(String(year + 1)) + '</span><span class="agro-time__arrow">▶</span></button>' +
      "</div>" +
      '<div class="agro-time__dayRow">' + dayRow + "</div>" +
      '<div class="agro-time__band" aria-hidden="true">' + dayTicks + "</div>" +
      '<div class="agro-time__results"><h5>Filtered contextual objects</h5>' + objectRows + "</div>" +
      "</section>"
    );
  }

  function loadAgroTimeScope(tool, scope) {
    var bucket = agroState(tool);
    var endpoint = routePrefixForTool(tool) + "/time/filter";
    var scopeParts = parseTimeScopeSegments(scope);
    return api(endpoint, "POST", {
      selected_scope: scope,
      selected_time: {
        kind: "time_address",
        segments: scopeParts,
        specificity_hint: scopeParts.length <= 3 ? "year" : (scopeParts.length === 4 ? "month" : "day")
      }
    }).then(function (payload) {
      var calendar = payload && payload.calendar && typeof payload.calendar === "object" ? payload.calendar : {};
      bucket.timeContext = {
        selected_scope: text(payload && payload.selected_scope),
        specificity: text(payload && payload.specificity),
        calendar: calendar,
        objects: Array.isArray(payload && payload.objects) ? payload.objects : []
      };
      setSelectedTimeContext(bucket.timeContext.selected_scope);
      renderAll();
      return payload || {};
    });
  }

  function renderAgroDualPaneScaffold(tool, mode) {
    var spatialMode = mode === "spatial";
    var model = agroState(tool).model || {};
    var ordering = model.ordering_subject && typeof model.ordering_subject === "object" ? model.ordering_subject : {};
    var primarySvg = ordering.primary_svg && typeof ordering.primary_svg === "object"
      ? ordering.primary_svg
      : (model.active_parcel_polygon_svg && typeof model.active_parcel_polygon_svg === "object"
        ? model.active_parcel_polygon_svg
        : (model.polygon_svg && typeof model.polygon_svg === "object" ? model.polygon_svg : {}));
    var profile = model.profile_context && typeof model.profile_context === "object" ? model.profile_context : {};
    var entities = Array.isArray(ordering.entities) ? ordering.entities : [];
    var orderingLeft = spatialMode
      ? (
        '<svg class="agro-scaffold__svg" viewBox="' + esc(primarySvg.viewbox || "0 0 420 240") + '" role="img" aria-label="Property polygon preview">' +
        (primarySvg.points ? '<polygon points="' + esc(primarySvg.points) + '" fill="rgba(182, 199, 174, 0.72)" stroke="rgba(86, 103, 78, 0.86)" stroke-width="1.6"></polygon>' : "") +
        "</svg>"
      )
      : (
        '<div class="agro-scaffold__svg" aria-hidden="true" style="display:grid;grid-template-columns:repeat(16,1fr);gap:2px;padding:5px;">' +
        Array(192).fill(0).map(function (_, idx) {
          var val = (idx * 17) % 100;
          var tone = val < 45 ? "rgba(109,164,122,0.55)" : "rgba(181,123,79,0.6)";
          return '<span style="display:block;height:8px;border-radius:1px;background:' + tone + ';"></span>';
        }).join("") +
        "</div>"
      );
    var orderingLegend = entities.length
      ? (
        "<ul class=\"agro-scaffold__legend\">" +
        entities.slice(0, 5).map(function (row) {
          return "<li><strong>" + esc(row.label || row.role || "property") + ":</strong> " + esc(row.ref || "") + "</li>";
        }).join("") +
        "</ul>"
      )
      : "<p class=\"data-tool__empty\">No profile entities resolved yet.</p>";
    var orderingArea =
      '<div class="agro-scaffold__ordering">' +
      '<article class="agro-scaffold__orderingCard"><h5>Ordering</h5>' + orderingLeft + "</article>" +
      '<article class="agro-scaffold__orderingCard"><h5>Profile refs</h5>' +
      "<p><strong>fnd:</strong> " + esc(profile.fnd_profile_path || "(missing)") + "</p>" +
      "<p><strong>msn:</strong> " + esc(profile.msn_profile_path || "(missing)") + "</p>" +
      orderingLegend +
      "</article>" +
      "</div>";
    var left =
      spatialMode
        ? (
          '<div class="agro-scaffold__grid agro-scaffold__grid--spatial">' +
          '<div class="agro-scaffold__block agro-scaffold__block--a"></div>' +
          '<div class="agro-scaffold__block agro-scaffold__block--b"></div>' +
          '<div class="agro-scaffold__block agro-scaffold__block--c"></div>' +
          "</div>"
        )
        : (
          renderChronologyWorkbench(tool)
        );
    var right =
      '<div class="agro-scaffold__stack">' +
      '<div class="agro-scaffold__block agro-scaffold__block--context"></div>' +
      '<div class="agro-scaffold__block agro-scaffold__block--companion"></div>' +
      "</div>";
    return (
      '<div class="agro-scaffold">' +
      '<section class="agro-scaffold__pane agro-scaffold__pane--left">' +
      '<h4>Operational subject (' + esc(spatialMode ? "spatial" : "chronological") + ")</h4>" +
      orderingArea +
      left +
      "</section>" +
      '<section class="agro-scaffold__pane agro-scaffold__pane--right">' +
      "<h4>Contextual companion</h4>" +
      right +
      "</section>" +
      "</div>" +
      '<p class="agro-scaffold__note">Empty scaffold staged from config + profile context. Deeper datum-family commits remain decision-gated.</p>'
    );
  }

  function renderAgroTaxonomy(tool) {
    var model = agroState(tool).model || {};
    var taxonomy = model.taxonomy && typeof model.taxonomy === "object" ? model.taxonomy : {};
    var tree = taxonomy.tree && typeof taxonomy.tree === "object" ? taxonomy.tree : {};
    var treeHtml = renderTaxonomyTree(tree, 0);
    return (
      "<p><strong>Ref:</strong> <code>" + esc(taxonomy.ref || "") + "</code></p>" +
      "<p><strong>Scope:</strong> " + esc(taxonomy.scope || "unknown") + "</p>" +
      (treeHtml ? "<ul class=\"data-tool__pathList\">" + treeHtml + "</ul>" : '<p class="data-tool__empty">No taxonomy tree is currently resolvable.</p>')
    );
  }

  function renderAgroSupplierBrowse(tool) {
    var ctx = toolContext(tool.tool_id) || {};
    var roles = ctx.resource_role_bindings && typeof ctx.resource_role_bindings === "object" ? ctx.resource_role_bindings : {};
    return (
      "<p>This mode uses inherited resources directly for browse and lookup where available, then stages only reduced local abstractions before minimal anthology commit.</p>" +
      '<pre class="jsonblock">' + esc(JSON.stringify(roles, null, 2)) + "</pre>"
    );
  }

  function renderAgroCompose(tool, kind) {
    var label = kind === "product" ? "Product profile" : "Supply log";
    var previewKey = kind === "product" ? "product_profile" : "supply_log";
    var bucket = agroState(tool);
    var actionButtons =
      '<div class="data-tool__controlRow data-tool__controlRow--wrap">' +
      '<button type="button" data-agro-action="preview" data-agro-kind="' + esc(kind) + '">Preview</button>' +
      '<button type="button" data-agro-action="apply" data-agro-kind="' + esc(kind) + '">Apply</button>' +
      "</div>";
    var previewState = bucket.lastPreview && bucket.lastPreview.kind === previewKey ? bucket.lastPreview.payload : {};
    var applyState = bucket.lastApply && bucket.lastApply.kind === previewKey ? bucket.lastApply.payload : {};
    return (
      "<p><strong>" + esc(label) + "</strong> stays config-bound and mediation-scoped. Inherited resources remain browse truth, sandbox carries reduced staging, and anthology receives only the semantic minimum commit.</p>" +
      actionButtons +
      '<details class="data-tool__advanced" open><summary>Latest preview</summary><pre class="jsonblock">' + esc(JSON.stringify(previewState || {}, null, 2)) + "</pre></details>" +
      '<details class="data-tool__advanced"><summary>Latest apply</summary><pre class="jsonblock">' + esc(JSON.stringify(applyState || {}, null, 2)) + "</pre></details>"
    );
  }

  function renderAgroPreviewSummary(tool) {
    return (
      '<details class="data-tool__advanced" open><summary>Readback</summary><pre class="jsonblock">' +
      esc(JSON.stringify(agroState(tool).readback || {}, null, 2)) +
      "</pre></details>"
    );
  }

  function runAgroAction(tool, kind, action) {
    var previewKey = kind === "product" ? "product_profile" : "supply_log";
    var hooks = action === "preview" ? toolPreviewHooks(tool) : toolApplyHooks(tool);
    var endpoint = text(hooks[previewKey]);
    var bucket = agroState(tool);
    if (!endpoint) {
      return Promise.reject(new Error("No endpoint is registered for the requested AGRO ERP action."));
    }
    return ensureAgroSession(tool, false).then(function (sessionPayload) {
      if (!sessionPayload || sessionPayload.ok === false) {
        throw new Error((sessionPayload && sessionPayload.error) || "AGRO ERP session is unavailable.");
      }
      return api(endpoint, "POST", { sandbox_session_id: bucket.sessionId }).then(function (payload) {
        if (action === "preview") {
          bucket.lastPreview = { kind: previewKey, payload: payload || {} };
          return payload;
        }
        bucket.lastApply = { kind: previewKey, payload: payload || {} };
        var readbackPath = routePrefixForTool(tool) + "/mvp/workflow/readback?resource_ref=" + encodeURIComponent("session:" + bucket.sessionId);
        return api(readbackPath).catch(function () {
          return {};
        }).then(function (readback) {
          bucket.readback = readback || {};
          return payload;
        });
      }).then(function (payload) {
        renderAll();
        return payload;
      });
    });
  }

  var agroMediationProvider = {
    defaultMode: function (tool) {
      return agroModeId(toolContribution(tool).default_mode || "spatial") || "spatial";
    },
    modes: function () {
      return [
        { id: "spatial", label: "Spatial" },
        { id: "chronological", label: "Chronological" },
        { id: "overview", label: "Overview" },
        { id: "taxonomy", label: "Taxonomy browse/select" },
        { id: "supplier", label: "Supplier browse/select" },
        { id: "product", label: "Product profile compose" },
        { id: "invoice", label: "Supply log compose" },
        { id: "preview", label: "Preview/apply" }
      ];
    },
    title: function (tool) {
      return text(tool && (tool.label || tool.tool_id)) || "AGRO ERP";
    },
    kicker: function (tool) {
      return text(toolContribution(tool).label) || "Canonical mediation workspace";
    },
    meta: function (tool) {
      var ctx = toolContext(tool.tool_id) || {};
      var bucket = agroState(tool);
      var activation = ctx.activation && typeof ctx.activation === "object" ? ctx.activation : {};
      if (bucket.lastError) {
        return bucket.lastError;
      }
      return "Session: " + (bucket.sessionId || "(not opened)") + " · can_open=" + String(!!activation.can_open);
    },
    ensureReady: function (tool, force) {
      var bucket = agroState(tool);
      return Promise.all([
        ensureToolContext(tool, force),
        ensureAgroModel(tool, force)
      ]).then(function () {
        return ensureAgroSession(tool, force);
      }).catch(function (err) {
        bucket.lastError = err && err.message ? err.message : "AGRO ERP could not open.";
        throw err;
      });
    },
    render: function (tool, mode) {
      if (mode === "spatial" || mode === "chronological") return renderAgroDualPaneScaffold(tool, mode);
      if (mode === "taxonomy") return renderAgroTaxonomy(tool);
      if (mode === "supplier") return renderAgroSupplierBrowse(tool);
      if (mode === "product") return renderAgroCompose(tool, "product");
      if (mode === "invoice") return renderAgroCompose(tool, "invoice");
      if (mode === "preview") return renderAgroPreviewSummary(tool);
      return renderAgroOverview(tool);
    },
    bind: function (tool) {
      qsa("[data-agro-action]", els.mediationBody).forEach(function (btn) {
        btn.addEventListener("click", function () {
          var kind = text(btn.getAttribute("data-agro-kind"));
          var action = text(btn.getAttribute("data-agro-action"));
          if (!kind || !action) return;
          runAgroAction(tool, kind, action).catch(function (err) {
            if (els.mediationMeta) {
              els.mediationMeta.textContent = err && err.message ? err.message : "AGRO ERP action failed.";
            }
          });
        });
      });
      qsa("[data-agro-time-scope]", els.mediationBody).forEach(function (btn) {
        btn.addEventListener("click", function () {
          var scope = text(btn.getAttribute("data-agro-time-scope"));
          if (!scope) return;
          loadAgroTimeScope(tool, scope).catch(function (err) {
            if (els.mediationMeta) {
              els.mediationMeta.textContent = err && err.message ? err.message : "Time scope selection failed.";
            }
          });
        });
      });
      qsa("[data-agro-time-nav]", els.mediationBody).forEach(function (btn) {
        btn.addEventListener("click", function () {
          var dir = text(btn.getAttribute("data-agro-time-nav"));
          var bucket = agroState(tool);
          var calendar = bucket.timeContext && bucket.timeContext.calendar && typeof bucket.timeContext.calendar === "object"
            ? bucket.timeContext.calendar
            : {};
          var year = Number(calendar.year || new Date().getUTCFullYear());
          var target = dir === "prev"
            ? text(calendar.prev_year_scope || "")
            : text(calendar.next_year_scope || "");
          if (!target) {
            target = hopsScopeFromCalendar(calendar, { year: dir === "prev" ? (year - 1) : (year + 1), depth: 1 });
          }
          loadAgroTimeScope(tool, target).catch(function (err) {
            if (els.mediationMeta) {
              els.mediationMeta.textContent = err && err.message ? err.message : "Year navigation failed.";
            }
          });
        });
      });
    }
  };

  function fndEbiDomainFromCard(card) {
    var body = card && card.body && typeof card.body === "object" ? card.body : {};
    return text(body.domain || card.title || "");
  }

  function fndEbiAnalyticsRows(profileCards, analyticsItems) {
    var byDomain = {};
    (analyticsItems || []).forEach(function (item) {
      var d = text(item && item.domain).toLowerCase();
      if (d) byDomain[d] = item;
    });
    return (profileCards || []).map(function (card) {
      var d = fndEbiDomainFromCard(card).toLowerCase();
      return { card: card, analytics: d && byDomain[d] ? byDomain[d] : null };
    });
  }

  function fndEbiSnapshotFromCard(card) {
    var body = card && card.body && typeof card.body === "object" ? card.body : {};
    return body.analytics_snapshot && typeof body.analytics_snapshot === "object" ? body.analytics_snapshot : {};
  }

  function fndEbiSparkline(values) {
    var points = Array.isArray(values) ? values : [];
    if (!points.length) return "......";
    var chars = "▁▂▃▄▅▆▇█";
    var max = 0;
    points.forEach(function (v) {
      var n = Number(v) || 0;
      if (n > max) max = n;
    });
    if (max <= 0) return ".".repeat(Math.min(points.length, 12));
    return points.slice(-12).map(function (v) {
      var n = Number(v) || 0;
      var idx = Math.max(0, Math.min(chars.length - 1, Math.floor((n / max) * (chars.length - 1))));
      return chars.charAt(idx);
    }).join("");
  }

  function fndEbiFormatPct(value) {
    var n = Number(value) || 0;
    return (n * 100).toFixed(1) + "%";
  }

  function fndEbiListRows(rows, emptyLabel) {
    var items = Array.isArray(rows) ? rows : [];
    if (!items.length) {
      return '<p class="data-tool__empty">' + esc(emptyLabel || "No rows.") + "</p>";
    }
    var out = ["<ul class=\"fnd-ebi-list\">"];
    items.slice(0, 8).forEach(function (entry) {
      if (!entry || typeof entry !== "object") return;
      out.push("<li><code>" + esc(text(entry.key || "")) + "</code><strong>" + esc(String(entry.count || 0)) + "</strong></li>");
    });
    out.push("</ul>");
    return out.join("");
  }

  function fndEbiSourceRows(source) {
    if (!source || typeof source !== "object") return "";
    return renderCardKeyValueRows({
      state: text(source.state),
      modified: text(source.modified_utc),
      "last seen": text(source.last_seen_utc),
      "size bytes": String(source.file_size_bytes || 0),
      "raw lines": String(source.raw_line_count || 0),
      "parsed lines": String(source.parsed_line_count || 0),
      "truncated": source.truncated ? "yes" : "no",
      path: text(source.path)
    });
  }

  function fndEbiSelectDomain(domain) {
    var token = text(domain).toLowerCase();
    if (!token) return;
    var bucket = providerStateFor("fnd_ebi");
    bucket.selectedDomain = token;
  }

  function fndEbiSelectedSnapshot(tool) {
    var ctx = toolContext(tool.tool_id) || {};
    var snapshots = Array.isArray(ctx.analytics_snapshots) ? ctx.analytics_snapshots : [];
    if (!snapshots.length) return null;
    var bucket = providerStateFor(tool.tool_id);
    var selected = text(bucket.selectedDomain).toLowerCase();
    if (!selected) return snapshots[0];
    for (var i = 0; i < snapshots.length; i += 1) {
      var snap = snapshots[i];
      if (text(snap && snap.domain).toLowerCase() === selected) {
        return snap;
      }
    }
    return snapshots[0];
  }

  function renderFndEbiOverview(tool) {
    var ctx = toolContext(tool.tool_id) || {};
    var cards = Array.isArray(ctx.profile_cards) ? ctx.profile_cards : [];
    var snapshots = Array.isArray(ctx.analytics_snapshots) ? ctx.analytics_snapshots : [];
    var rows = fndEbiAnalyticsRows(cards, snapshots);
    var selected = fndEbiSelectedSnapshot(tool);
    if (!rows.length && !selected) {
      return '<p class="data-tool__empty">No profile cards from tool sandbox. Check utilities/tools/fnd-ebi and web-analytics.json.</p>';
    }
    var out = [];
    if (selected) {
      var traffic = selected.traffic && typeof selected.traffic === "object" ? selected.traffic : {};
      var eventsSummary = selected.events_summary && typeof selected.events_summary === "object" ? selected.events_summary : {};
      var freshness = selected.freshness && typeof selected.freshness === "object" ? selected.freshness : {};
      out.push('<article class="card">');
      out.push('<div class="card__kicker">Interface Lens</div>');
      out.push('<div class="card__title">' + esc(text(selected.domain || "Hosted analytics")) + '</div>');
      out.push('<div class="card__body">');
      out.push(renderCardKeyValueRows({
        "health label": text(selected.health_label),
        "site root": text(selected.site_root),
        "analytics root": text(selected.analytics_root),
        "requests 30d": String(traffic.requests_30d || 0),
        "real page req 30d": String(traffic.real_page_requests_30d || 0),
        "events 30d": String(eventsSummary.events_30d || 0),
        "unique visitors": String(traffic.unique_visitors_approx_30d || 0),
        "bot share": fndEbiFormatPct(traffic.bot_share || 0),
        "last access": text(freshness.access_last_seen_utc || ""),
        "last events": text(freshness.events_last_seen_utc || "")
      }));
      if (Array.isArray(selected.warnings) && selected.warnings.length) {
        out.push("<p><strong>Warnings</strong></p><ul class=\"fnd-ebi-warnings\">");
        selected.warnings.slice(0, 8).forEach(function (warning) {
          out.push("<li>" + esc(text(warning)) + "</li>");
        });
        out.push("</ul>");
      }
      out.push("</div></article>");
      out.push('<article class="card">');
      out.push('<div class="card__kicker">Source Diagnostics</div>');
      out.push('<div class="card__title">File and log readiness</div>');
      out.push('<div class="card__body">');
      out.push(renderInterfacePanelCardBody(null, {
        domain: text(selected.domain),
        site_root: text(selected.site_root),
        analytics_root: text(selected.analytics_root),
        access_log: selected.access_log,
        error_log: selected.error_log,
        events_file: selected.events_file,
        traffic_summary: {
          requests_30d: Number(traffic.requests_30d || 0),
          unique_visitors_approx_30d: Number(traffic.unique_visitors_approx_30d || 0),
          bot_share: Number(traffic.bot_share || 0),
          response_breakdown: traffic.response_breakdown || {}
        },
        event_summary: {
          events_30d: Number(eventsSummary.events_30d || 0),
          event_type_counts: eventsSummary.event_type_counts || {}
        },
        frontend: selected.frontend,
        errors_noise: selected.errors_noise,
        warnings: selected.warnings || []
      }));
      out.push("</div></article>");
    }
    if (rows.length) {
      var selectedDomain = text(selected && selected.domain).toLowerCase();
      out.push('<section class="fnd-ebi-gallery">');
      rows.forEach(function (row) {
        var c = row.card || {};
        var snapshot = row.analytics || fndEbiSnapshotFromCard(c);
        var traffic2 = snapshot.traffic && typeof snapshot.traffic === "object" ? snapshot.traffic : {};
        var eventsSummary2 = snapshot.events_summary && typeof snapshot.events_summary === "object" ? snapshot.events_summary : {};
        var title = text(c.title || c.card_id || "Site");
        var domainToken = text(snapshot.domain || title);
        out.push('<article class="card fnd-ebi-card' + (selectedDomain === domainToken.toLowerCase() ? ' is-active' : '') + '" data-fnd-ebi-select-domain="' + esc(domainToken) + '">');
        out.push('<div class="card__kicker">' + esc(text(snapshot.health_label || "status")) + "</div>");
        out.push('<div class="card__title">' + esc(title) + "</div>");
        out.push('<div class="card__body">');
        out.push("<p><strong>Requests 30d:</strong> " + esc(String(traffic2.requests_30d || 0)) + " · <strong>Real pages:</strong> " + esc(String(traffic2.real_page_requests_30d || 0)) + "</p>");
        out.push("<p><strong>Events 30d:</strong> " + esc(String(eventsSummary2.events_30d || 0)) + " · <strong>Bot share:</strong> " + esc(fndEbiFormatPct(traffic2.bot_share || 0)) + "</p>");
        out.push("<p><strong>Unique visitors:</strong> " + esc(String(traffic2.unique_visitors_approx_30d || 0)) + "</p>");
        out.push("<p><small>Select to focus this hosted profile in the interface lens.</small></p>");
        out.push("</div></article>");
      });
      out.push("</section>");
    }
    return out.join("");
  }

  function awsWorkflowFromCard(card) {
    var body = card && card.body && typeof card.body === "object" ? card.body : {};
    return body.workflow && typeof body.workflow === "object" ? body.workflow : {};
  }

  function awsIdentityFromCard(card) {
    var body = card && card.body && typeof card.body === "object" ? card.body : {};
    return body.identity && typeof body.identity === "object" ? body.identity : {};
  }

  function awsSmtpFromCard(card) {
    var body = card && card.body && typeof card.body === "object" ? card.body : {};
    return body.smtp && typeof body.smtp === "object" ? body.smtp : {};
  }

  function awsVerificationFromCard(card) {
    var body = card && card.body && typeof card.body === "object" ? card.body : {};
    return body.verification && typeof body.verification === "object" ? body.verification : {};
  }

  function awsProviderFromCard(card) {
    var body = card && card.body && typeof card.body === "object" ? card.body : {};
    return body.provider && typeof body.provider === "object" ? body.provider : {};
  }

  function awsInboundFromCard(card) {
    var body = card && card.body && typeof card.body === "object" ? card.body : {};
    return body.inbound && typeof body.inbound === "object" ? body.inbound : {};
  }

  function awsProfileToken(card) {
    var identity = awsIdentityFromCard(card);
    return text(card && (card.card_id || card.title) || identity.profile_id || identity.domain).toLowerCase();
  }

  function awsProfileSections(tool) {
    var ctx = toolContext(tool.tool_id) || {};
    var sections = Array.isArray(ctx.profile_domain_sections) ? ctx.profile_domain_sections : [];
    if (sections.length) return sections;
    var cards = Array.isArray(ctx.profile_cards) ? ctx.profile_cards : [];
    var grouped = {};
    cards.forEach(function (card) {
      var identity = awsIdentityFromCard(card);
      var domain = text(identity.domain || "unscoped");
      if (!grouped[domain]) grouped[domain] = [];
      grouped[domain].push(card);
    });
    return Object.keys(grouped).sort().map(function (domain) {
      return {
        domain: domain,
        card_count: grouped[domain].length,
        cards: grouped[domain]
      };
    });
  }

  function awsSelectProfile(toolId, token) {
    var bucket = providerStateFor(toolId);
    bucket.selectedProfile = text(token).toLowerCase();
  }

  function awsSelectedCard(tool) {
    var ctx = toolContext(tool.tool_id) || {};
    var cards = Array.isArray(ctx.profile_cards) ? ctx.profile_cards : [];
    if (!cards.length) return null;
    var bucket = providerStateFor(tool.tool_id);
    var selected = text(bucket.selectedProfile).toLowerCase();
    if (!selected) return null;
    for (var i = 0; i < cards.length; i += 1) {
      if (awsProfileToken(cards[i]) === selected) {
        return cards[i];
      }
    }
    return null;
  }

  function awsSecretStateIsPlaceholder(value) {
    var token = text(value).toLowerCase();
    return token === "placeholder" || token === "placeholder_present";
  }

  function awsSecretIsPlaceholderBacked(smtp) {
    var source = smtp && typeof smtp === "object" ? smtp : {};
    return awsSecretStateIsPlaceholder(source.credentials_secret_state);
  }

  function awsSecretIsProvisioned(smtp) {
    var source = smtp && typeof smtp === "object" ? smtp : {};
    return !awsSecretStateIsPlaceholder(source.credentials_secret_state) && text(source.credentials_secret_state) === "configured" && !!text(source.username);
  }

  function awsHasConfirmationEvidence(card, verificationState) {
    var verification = awsVerificationFromCard(card);
    var inbound = awsInboundFromCard(card);
    var state = verificationState && typeof verificationState === "object" ? verificationState : {};
    var message = state.verification_message && typeof state.verification_message === "object"
      ? state.verification_message
      : {};
    return !!(
      text(message.confirmation_link) ||
      text(message.s3_uri) ||
      text(message.message_id) ||
      text(verification.link) ||
      text(verification.latest_message_reference) ||
      inbound.latest_message_has_verification_link
    );
  }

  function awsProvisioningLabel(card) {
    var smtp = awsSmtpFromCard(card);
    var workflow = awsWorkflowFromCard(card);
    var verification = awsVerificationFromCard(card);
    var hasEvidence = awsHasConfirmationEvidence(card);
    if (workflow && workflow.is_send_as_confirmed && hasEvidence) return "Gmail verified";
    if (hasEvidence || text(verification.status) === "pending" || text(verification.portal_state) === "verification_email_received") {
      return "Gmail pending";
    }
    if (workflow && workflow.is_ready_for_user_handoff) return "Gmail handoff pending";
    if (awsSecretIsProvisioned(smtp)) return "Secret provisioned / SMTP ready";
    return "No secret provisioned";
  }

  function awsCopyAction(label, value) {
    var token = text(value);
    if (!token) return "";
    return '<button type="button" class="data-tool__actionBtn data-tool__actionBtn--quiet aws-csm-copyBtn" data-copy-text="' + esc(token) + '">' + esc(label) + "</button>";
  }

  function awsInfoLine(label, value, options) {
    var opts = options && typeof options === "object" ? options : {};
    var token = text(value);
    if (!token) return "";
    var compact = opts.compact ? " aws-csm-infoRow--compact" : "";
    var title = opts.title ? ' title="' + esc(text(opts.title)) + '"' : "";
    var display = limitText(token, Number(opts.limit) || (opts.compact ? 44 : 92));
    var actions = Array.isArray(opts.actions) ? opts.actions.join("") : "";
    return '<div class="aws-csm-infoRow' + compact + '"><dt>' + esc(label) + '</dt><dd' + title + '><span>' + esc(display) + '</span>' + actions + "</dd></div>";
  }

  function awsProfileCardBody(card, compact) {
    var identity = awsIdentityFromCard(card);
    var verification = awsVerificationFromCard(card);
    var inbound = awsInboundFromCard(card);
    var workflow = awsWorkflowFromCard(card);
    var title = text(card && (card.title || identity.send_as_email || identity.profile_id) || "profile");
    var missing = Array.isArray(workflow.missing_required_now) ? workflow.missing_required_now : [];
    var out = [];
    out.push('<div class="aws-csm-profileCard__title" title="' + esc(title) + '">' + esc(limitText(title, compact ? 34 : 56)) + "</div>");
    out.push('<div class="aws-csm-profileCard__meta">' + esc(text(identity.role || "mailbox").replace(/_/g, " ")) + " · " + esc(awsProvisioningLabel(card)) + "</div>");
    out.push('<div class="aws-csm-profileCard__stats">');
    out.push('<span>' + esc(text(identity.mailbox_local_part || "(mailbox)")) + "</span>");
    out.push('<span>' + esc(text(verification.status || "not_started").replace(/_/g, " ")) + "</span>");
    out.push('<span>' + esc(awsReceiveStateLabel(inbound || {})) + "</span>");
    out.push('<span>' + esc(String(missing.length)) + " blockers</span>");
    out.push("</div>");
    return out.join("");
  }

  function renderAwsNewsletterCards(section) {
    var cards = Array.isArray(section && section.newsletter_cards) ? section.newsletter_cards : [];
    if (!cards.length) return "";
    var out = [];
    out.push('<div class="aws-csm-newsletterList">');
    cards.forEach(function (card) {
      if (!card || typeof card !== "object") return;
      out.push('<article class="aws-csm-newsletterCard">');
      out.push('<div class="aws-csm-newsletterCard__title" title="' + esc(text(card.title || "newsletter")) + '">' + esc(limitText(text(card.title || "newsletter"), 44)) + '</div>');
      out.push('<div class="aws-csm-newsletterCard__meta">' + esc(text(card.dispatch_mode || "aws_internal").replace(/_/g, " ")) + '</div>');
      out.push('<div class="aws-csm-newsletterCard__stats">');
      if (text(card.sender_address)) out.push('<span title="' + esc(text(card.sender_address)) + '">' + esc(limitText(text(card.sender_address), 34)) + '</span>');
      if (text(card.ingest_address)) out.push('<span title="' + esc(text(card.ingest_address)) + '">' + esc(limitText(text(card.ingest_address), 34)) + '</span>');
      if (text(card.allowed_from_csv)) out.push('<span title="' + esc(text(card.allowed_from_csv)) + '">' + esc(limitText(text(card.allowed_from_csv), 34)) + '</span>');
      out.push('</div></article>');
    });
    out.push('</div>');
    return out.join("");
  }

  function renderAwsProfileSections(tool, options) {
    var opts = options && typeof options === "object" ? options : {};
    var compact = !!opts.compact;
    var sections = awsProfileSections(tool);
    if (!sections.length) {
      return '<div class="ide-controlpanel__empty">No AWS-CMS onboarding profiles are staged in the tool sandbox.</div>';
    }
    var selected = awsSelectedCard(tool);
    var selectedToken = awsProfileToken(selected);
    var out = [];
    sections.forEach(function (section) {
      var domain = text(section && section.domain || "unscoped");
      var cards = Array.isArray(section && section.cards) ? section.cards : [];
      out.push('<section class="aws-csm-domainSection' + (compact ? " aws-csm-domainSection--compact" : "") + '">');
      out.push('<header class="aws-csm-domainSection__header"><div class="aws-csm-domainSection__title">' + esc(domain) + '</div><div class="aws-csm-domainSection__count">' + esc(String(cards.length)) + " profile" + (cards.length === 1 ? "" : "s") + "</div></header>");
      out.push('<div class="aws-csm-profileGrid' + (compact ? " aws-csm-profileGrid--compact" : "") + '">');
      cards.forEach(function (card) {
        var token = awsProfileToken(card);
        var active = token === selectedToken;
        out.push('<button type="button" class="aws-csm-profileCard' + (active ? " is-active" : "") + (compact ? " aws-csm-profileCard--compact" : "") + '" data-aws-profile="' + esc(token) + '" title="' + esc(text(card && (card.title || token) || token)) + '">');
        out.push(awsProfileCardBody(card, compact));
        out.push("</button>");
      });
      out.push("</div>");
      out.push(renderAwsNewsletterCards(section));
      out.push("</section>");
    });
    return out.join("");
  }

  function renderAwsSelectedOverview(tool, selectedCard) {
    var identity = awsIdentityFromCard(selectedCard);
    var smtp = awsSmtpFromCard(selectedCard);
    var verification = awsVerificationFromCard(selectedCard);
    var workflow = awsWorkflowFromCard(selectedCard);
    var inbound = awsInboundFromCard(selectedCard);
    var provider = awsProviderFromCard(selectedCard);
    var out = [];
    out.push('<article class="card"><div class="card__kicker">Focused Profile</div><div class="card__title">' + esc(text(selectedCard.title || identity.domain || "AWS-CMS profile")) + '</div><div class="card__body">');
    out.push(renderCardKeyValueRows({
      domain: text(identity.domain),
      profile: text(identity.profile_id),
      mailbox: text(identity.mailbox_local_part),
      role: text(identity.role),
      "operator inbox": text(identity.operator_inbox_target || identity.single_user_email),
      "send as": text(identity.send_as_email || smtp.send_as_email),
      "smtp state": awsProvisioningLabel(selectedCard),
      "handoff status": awsHandoffStatusLabel(workflow),
      "verification": text(verification.status),
      "provider send-as": text(provider.gmail_send_as_status),
      "receive state": awsReceiveStateLabel(inbound)
    }));
    if (Array.isArray(workflow.missing_required_now) && workflow.missing_required_now.length) {
      out.push("<p><strong>Still missing:</strong> " + esc(workflow.missing_required_now.join(", ")) + "</p>");
    }
    out.push("</div></article>");
    return out.join("");
  }

  function renderAwsOverview(tool) {
    var ctx = toolContext(tool.tool_id) || {};
    var cards = Array.isArray(ctx.profile_cards) ? ctx.profile_cards : [];
    if (!cards.length) {
      return '<p class="data-tool__empty">No AWS-CMS onboarding profiles are staged in the canonical aws-csm root.</p>';
    }
    var selectedCard = awsSelectedCard(tool);
    var ready = cards.filter(function (card) {
      return !!awsWorkflowFromCard(card).is_ready_for_user_handoff;
    }).length;
    var out = [];
    out.push('<article class="card aws-csm-overviewIntro"><div class="card__kicker">Tool Sandbox</div><div class="card__title">AWS-CMS mailbox profiles</div><div class="card__body">');
    out.push("<p>Select a mailbox profile to enter the onboarding workflow. Profiles are grouped by domain, and newsletter cards appear only when the sandbox already carries newsletter sender/ingest state for that domain.</p>");
    out.push("<p><strong>Total profiles:</strong> " + esc(String(cards.length)) + " · <strong>Ready for handoff:</strong> " + esc(String(ready)) + "</p>");
    if (!selectedCard) {
      out.push("<p><strong>Next step:</strong> choose a profile card below to open Overview, SMTP, Verification, and Files for that mailbox only.</p>");
    }
    out.push("</div></article>");
    if (selectedCard) {
      out.push(renderAwsSelectedOverview(tool, selectedCard));
    }
    out.push(renderAwsProfileSections(tool, { compact: false }));
    return out.join("");
  }

  function renderAwsSmtp(tool) {
    var selectedCard = awsSelectedCard(tool);
    if (!selectedCard) {
      return '<p class="data-tool__empty">Select an AWS-CMS profile to inspect SMTP handoff fields.</p>';
    }
    var identity = awsIdentityFromCard(selectedCard);
    var smtp = awsSmtpFromCard(selectedCard);
    var inbound = awsInboundFromCard(selectedCard);
    var workflow = awsWorkflowFromCard(selectedCard);
    var out = [];
    out.push('<article class="card"><div class="card__kicker">SMTP Handoff</div><div class="card__title">' + esc(text(selectedCard.title || identity.domain || "AWS-CMS profile")) + '</div><div class="card__body">');
    out.push(renderCardKeyValueRows({
      "operator inbox": text(identity.operator_inbox_target || identity.single_user_email),
      role: text(identity.role),
      mailbox: text(identity.mailbox_local_part),
      "send as": text(smtp.send_as_email),
      host: text(smtp.host),
      port: text(smtp.port),
      username: text(smtp.username),
      "credentials source": text(smtp.credentials_source),
      "secret ref": text(smtp.credentials_secret_name),
      "secret state": text(smtp.credentials_secret_state),
      "smtp state": awsProvisioningLabel(selectedCard),
      "username known": text(smtp.username) ? "yes" : "no",
      "forward to": text(smtp.forward_to_email),
      "forwarding status": text(smtp.forwarding_status),
      "receive state": awsReceiveStateLabel(inbound),
      "workflow handoff ready": workflow.is_ready_for_user_handoff ? "yes" : "no",
      "handoff status": awsHandoffStatusLabel(workflow)
    }));
    if (!awsSecretIsProvisioned(smtp)) {
      if (awsSecretIsPlaceholderBacked(smtp)) {
        out.push("<p><strong>Placeholder-backed SMTP:</strong> provision real SES SMTP credentials before Gmail handoff.</p>");
      } else {
        out.push("<p><strong>No secret provisioned:</strong> begin onboarding to provision real SES SMTP credentials before Gmail handoff.</p>");
      }
    } else if (text(smtp.credentials_secret_state) === "auth_failed" && !text(smtp.username)) {
      out.push("<p><strong>SMTP auth failed:</strong> the referenced credential set is present, but not yet usable for SES SMTP handoff.</p>");
    } else if (workflow.is_ready_for_user_handoff && !workflow.is_send_as_confirmed) {
      out.push("<p><strong>SMTP ready:</strong> the portal can hand the SES SMTP details to the operator for Gmail send-as setup.</p>");
    }
    out.push("</div></article>");
    return out.join("");
  }

  function renderAwsHandoffInstructions(bundle, selectedCard) {
    var smtp = bundle && typeof bundle === "object" ? bundle : {};
    var identity = awsIdentityFromCard(selectedCard);
    var out = [];
    out.push('<article class="card aws-csm-handoffCard"><div class="card__kicker">SMTP Handoff</div><div class="card__title">Use these values in the supporting email app</div><div class="card__body">');
    if (!awsSecretIsProvisioned(smtp)) {
      if (awsSecretIsPlaceholderBacked(smtp)) {
        out.push("<p><strong>Placeholder-backed SMTP:</strong> the portal will only display SMTP copy fields after real SES SMTP secret material has replaced the placeholder secret.</p>");
      } else {
        out.push("<p><strong>No secret provisioned:</strong> the portal will only display SMTP copy fields after real SES SMTP secret material has been provisioned.</p>");
      }
      if (text(smtp.secret_ref)) {
        out.push("<p><strong>Secret ref:</strong> <code>" + esc(text(smtp.secret_ref)) + "</code></p>");
      }
      out.push("</div></article>");
      return out.join("");
    }
    out.push('<dl class="aws-csm-infoGrid">');
    out.push(awsInfoLine("Send mail as", text(smtp.send_as_email || identity.send_as_email), { actions: [awsCopyAction("Copy", text(smtp.send_as_email || identity.send_as_email))] }));
    out.push(awsInfoLine("SMTP server", text(smtp.host), { actions: [awsCopyAction("Copy", text(smtp.host))] }));
    out.push(awsInfoLine("Port", text(smtp.port), { actions: [awsCopyAction("Copy", text(smtp.port))] }));
    out.push(awsInfoLine("Username", text(smtp.username), { actions: [awsCopyAction("Copy", text(smtp.username))] }));
    out.push(awsInfoLine("Password", text(smtp.password), { actions: [awsCopyAction("Copy", text(smtp.password))] }));
    out.push(awsInfoLine("Security", text(smtp.security_label || "Secured connection using TLS")));
    out.push("</dl>");
    out.push("<p><strong>Direction:</strong> choose <em>Secured connection using TLS</em> in the supporting email application.</p>");
    if (text(smtp.secret_ref)) {
      out.push("<p><strong>Secret ref:</strong> <code>" + esc(text(smtp.secret_ref)) + "</code></p>");
    }
    out.push("</div></article>");
    return out.join("");
  }

  function renderAwsVerification(tool) {
    var selectedCard = awsSelectedCard(tool);
    if (!selectedCard) {
      return '<p class="data-tool__empty">Select an AWS-CMS profile to inspect verification state.</p>';
    }
    var bucket = providerStateFor(tool.tool_id);
    var identity = awsIdentityFromCard(selectedCard);
    var verification = awsVerificationFromCard(selectedCard);
    var provider = awsProviderFromCard(selectedCard);
    var workflow = awsWorkflowFromCard(selectedCard);
    var inbound = awsInboundFromCard(selectedCard);
    var handoff = bucket.latestHandoff && typeof bucket.latestHandoff === "object" ? bucket.latestHandoff : {};
    var verificationState = bucket.latestVerification && typeof bucket.latestVerification === "object" ? bucket.latestVerification : {};
    var verificationMessage = verificationState.verification_message && typeof verificationState.verification_message === "object"
      ? verificationState.verification_message
      : {};
    var confirmationLink = text(verificationMessage.confirmation_link || verification.link);
    var canConfirmVerified = awsHasConfirmationEvidence(selectedCard, verificationState) && !workflow.is_send_as_confirmed;
    var out = [];
    out.push('<article class="card"><div class="card__kicker">Verification</div><div class="card__title">' + esc(text(selectedCard.title || identity.domain || "AWS-CMS profile")) + '</div><div class="card__body">');
    out.push("<p>This workflow begins in the portal, hands the SMTP settings to the operator, then watches the receive path for the Gmail verification message.</p>");
    out.push('<div class="aws-csm-flowForm">');
    out.push('<label class="aws-csm-flowForm__field"><span>Supporting email inbox</span><input type="email" class="data-tool__fieldInput" data-aws-operator-email value="' + esc(text(identity.operator_inbox_target || identity.single_user_email)) + '" placeholder="name@example.com" /></label>');
    out.push('<div class="aws-csm-flowForm__actions">');
    out.push('<button type="button" class="data-tool__actionBtn is-active" data-aws-action="begin-onboarding">Begin Onboarding</button>');
    out.push('<button type="button" class="data-tool__actionBtn" data-aws-action="refresh-verification">Check Verification</button>');
    if (canConfirmVerified) {
      out.push('<button type="button" class="data-tool__actionBtn" data-aws-action="confirm-verified">Confirm Verified</button>');
    }
    out.push("</div></div>");
    out.push(renderCardKeyValueRows({
      status: text(verification.status),
      "portal state": text(verification.portal_state),
      "ses identity": text(provider.aws_ses_identity_status),
      "gmail send-as": text(provider.gmail_send_as_status),
      "smtp state": awsProvisioningLabel(selectedCard),
      "handoff status": awsHandoffStatusLabel(workflow),
      "completion boundary": awsCompletionBoundaryLabel(workflow),
      "receive state": awsReceiveStateLabel(inbound),
      "receive verified": inbound.receive_verified ? "yes" : "no"
    }));
    if (bucket.pendingAwsAction) {
      out.push("<p><strong>Working:</strong> " + esc(text(bucket.pendingAwsAction)) + "…</p>");
    }
    if (text(bucket.awsError)) {
      out.push('<p class="fnd-ebi-warning"><strong>Action error:</strong> ' + esc(text(bucket.awsError)) + "</p>");
    }
    if (handoff && Object.keys(handoff).length) {
      out.push("</div></article>");
      out.push(renderAwsHandoffInstructions(handoff, selectedCard));
    } else {
      if (workflow.is_ready_for_user_handoff && !workflow.is_send_as_confirmed) {
        out.push("<p><strong>Ready:</strong> the mailbox can proceed to Gmail send-as handoff as soon as you load the SMTP bundle.</p>");
      } else if (!awsSecretIsProvisioned(awsSmtpFromCard(selectedCard))) {
        if (awsSecretIsPlaceholderBacked(awsSmtpFromCard(selectedCard))) {
          out.push("<p><strong>Blocked before handoff:</strong> this mailbox is still backed by placeholder SMTP material.</p>");
        } else {
          out.push("<p><strong>Blocked before handoff:</strong> no real SES SMTP secret has been provisioned for this mailbox yet.</p>");
        }
      } else if (Array.isArray(workflow.configuration_blockers_now) && workflow.configuration_blockers_now.length) {
        out.push("<p><strong>Blocked before handoff:</strong> " + esc(workflow.configuration_blockers_now.join(", ")) + "</p>");
      }
      out.push("</div></article>");
    }
    out.push('<article class="card"><div class="card__kicker">Receive-path automation</div><div class="card__title">Portal verification watcher</div><div class="card__body">');
    out.push("<p>The portal watches for the Gmail verification email after onboarding begins. When it captures a confirmation link, it will surface it here for the operator.</p>");
    out.push(renderCardKeyValueRows({
      "last checked": text(inbound.receive_last_checked_at || provider.last_checked_at),
      "latest sender": text(inbound.latest_message_sender),
      "latest subject": text(inbound.latest_message_subject),
      "captured at": text(inbound.latest_message_captured_at),
      "capture ref": text(inbound.capture_source_reference || inbound.latest_message_s3_uri)
    }));
    if (confirmationLink) {
      out.push('<p><strong>Confirmation link:</strong> <a href="' + esc(confirmationLink) + '" target="_blank" rel="noopener noreferrer">Open Gmail verification link</a> ' + awsCopyAction("Copy link", confirmationLink) + "</p>");
    } else if (bucket.awsPollingVerification) {
      out.push("<p><strong>Watching:</strong> the portal is polling the receive path for the Gmail verification message.</p>");
    } else {
      out.push("<p><strong>No verification email captured yet.</strong> Start onboarding, configure Send mail as in the supporting inbox, then the portal will look for the verification email.</p>");
    }
    if (!canConfirmVerified && !workflow.is_send_as_confirmed) {
      out.push("<p><strong>Verification lock:</strong> Gmail verification cannot be confirmed until the portal has captured confirmation evidence for this mailbox.</p>");
    }
    out.push("</div></article>");
    return out.join("");
  }

  function renderAwsFiles(tool) {
    var ctx = toolContext(tool.tool_id) || {};
    var files = Array.isArray(ctx.collection_files) ? ctx.collection_files : [];
    var selectedCard = awsSelectedCard(tool);
    var rows = [];
    if (selectedCard) {
      rows.push(renderAwsSelectedOverview(tool, selectedCard));
    }
    if (!files.length) {
      rows.push('<p class="data-tool__empty">No AWS-CMS files discovered in the canonical root.</p>');
      return rows.join("");
    }
    rows.push('<section class="aws-csm-fileList">');
    files.forEach(function (f) {
      if (!f || typeof f !== "object") return;
      var relativePath = text(f.relative_path || f.file_name || "");
      rows.push('<article class="card aws-csm-fileCard">');
      rows.push('<div class="card__kicker">' + esc(text(f.content_kind || "json")) + '</div>');
      rows.push('<div class="card__title" title="' + esc(relativePath) + '">' + esc(limitText(relativePath, 44)) + "</div>");
      rows.push('<div class="card__body">');
      rows.push("<p><strong>Records:</strong> " + esc(String(f.record_count != null ? f.record_count : "")) + "</p>");
      if (text(f.schema)) {
        rows.push("<p><strong>Schema:</strong> " + esc(text(f.schema)) + "</p>");
      }
      rows.push("</div></article>");
    });
    rows.push("</section>");
    return rows.join("");
  }

  function awsSelectedProfileId(tool) {
    var selectedCard = awsSelectedCard(tool);
    var identity = awsIdentityFromCard(selectedCard);
    return text(identity.profile_id || awsProfileToken(selectedCard));
  }

  function awsStopPolling(toolId) {
    var bucket = providerStateFor(toolId);
    if (bucket.awsPollTimer) {
      window.clearTimeout(bucket.awsPollTimer);
      bucket.awsPollTimer = 0;
    }
    bucket.awsPollingVerification = false;
  }

  async function awsReloadToolContext(tool) {
    await ensureToolContext(tool, true);
    renderAll();
  }

  async function awsRunProvision(tool, action, extra) {
    var profileId = awsSelectedProfileId(tool);
    if (!profileId) {
      throw new Error("Select an AWS-CMS profile first.");
    }
    var bucket = providerStateFor(tool.tool_id);
    bucket.pendingAwsAction = action;
    bucket.awsError = "";
    renderAll();
    try {
      var payload = await api(
        "/portal/api/admin/aws/profile/" + encodeURIComponent(profileId) + "/provision",
        "POST",
        Object.assign({ action: action }, extra || {})
      );
      bucket.latestAwsResponse = payload;
      if (payload.smtp_handoff && typeof payload.smtp_handoff === "object") {
        bucket.latestHandoff = payload.smtp_handoff;
      }
      if (payload.verification_message && typeof payload.verification_message === "object") {
        bucket.latestVerification = payload;
      }
      await awsReloadToolContext(tool);
      return payload;
    } catch (err) {
      bucket.awsError = err && err.message ? err.message : "AWS-CMS action failed.";
      renderAll();
      throw err;
    } finally {
      bucket.pendingAwsAction = "";
      renderAll();
    }
  }

  async function awsCheckVerification(tool) {
    var payload = await awsRunProvision(tool, "refresh_inbound_status");
    var verificationMessage = payload && payload.verification_message && typeof payload.verification_message === "object"
      ? payload.verification_message
      : {};
    if (!text(verificationMessage.confirmation_link)) {
      payload = await awsRunProvision(tool, "capture_verification");
    }
    return payload;
  }

  function awsStartVerificationWatcher(tool) {
    var bucket = providerStateFor(tool.tool_id);
    awsStopPolling(tool.tool_id);
    bucket.awsPollingVerification = true;
    bucket.awsPollAttempts = 0;
    function tick() {
      var liveBucket = providerStateFor(tool.tool_id);
      liveBucket.awsPollAttempts = Number(liveBucket.awsPollAttempts || 0) + 1;
      awsCheckVerification(tool).then(function (payload) {
        var verificationMessage = payload && payload.verification_message && typeof payload.verification_message === "object"
          ? payload.verification_message
          : {};
        if (text(verificationMessage.confirmation_link) || Number(liveBucket.awsPollAttempts || 0) >= 18) {
          awsStopPolling(tool.tool_id);
          renderAll();
          return;
        }
        liveBucket.awsPollTimer = window.setTimeout(tick, 10000);
        renderAll();
      }).catch(function (err) {
        liveBucket.awsError = err && err.message ? err.message : "Verification watch failed.";
        awsStopPolling(tool.tool_id);
        renderAll();
      });
    }
    tick();
  }

  async function awsBeginOnboarding(tool, root) {
    var emailInput = qs("[data-aws-operator-email]", root || els.toolInterfaceBody);
    var operatorEmail = text(emailInput && emailInput.value);
    if (!operatorEmail) {
      throw new Error("Enter the supporting email inbox before beginning onboarding.");
    }
    var payload = await awsRunProvision(tool, "prepare_send_as", {
      operator_inbox_target: operatorEmail
    });
    await awsRunProvision(tool, "enable_inbound_capture");
    awsStartVerificationWatcher(tool);
    return payload;
  }

  async function awsConfirmVerified(tool) {
    awsStopPolling(tool.tool_id);
    return awsRunProvision(tool, "confirm_verified");
  }

  function bindAwsInterfaceActions(tool, root) {
    qsa("[data-aws-profile]", root || els.toolInterfaceBody).forEach(function (node) {
      node.addEventListener("click", function () {
        awsSelectProfile(tool.tool_id, node.getAttribute("data-aws-profile"));
        state.activeMediationMode = "overview";
        renderAll();
      });
    });
    qsa("[data-aws-file]", root || els.toolInterfaceBody).forEach(function (node) {
      node.addEventListener("click", function () {
        var bucket = providerStateFor(tool.tool_id);
        bucket.selectedFile = text(node.getAttribute("data-aws-file"));
        var profileToken = text(node.getAttribute("data-aws-profile-file"));
        if (profileToken) {
          awsSelectProfile(tool.tool_id, profileToken);
        }
        state.activeMediationMode = "files";
        renderAll();
      });
    });
    qsa("[data-copy-text]", root || els.toolInterfaceBody).forEach(function (node) {
      node.addEventListener("click", function () {
        var value = text(node.getAttribute("data-copy-text"));
        if (!value || !navigator.clipboard || typeof navigator.clipboard.writeText !== "function") return;
        navigator.clipboard.writeText(value).catch(function () {});
      });
    });
    qsa("[data-aws-action]", root || els.toolInterfaceBody).forEach(function (node) {
      node.addEventListener("click", function () {
        var action = text(node.getAttribute("data-aws-action"));
        if (action === "begin-onboarding") {
          awsBeginOnboarding(tool, root).catch(function () {});
          return;
        }
        if (action === "refresh-verification") {
          awsCheckVerification(tool).catch(function () {});
          return;
        }
        if (action === "confirm-verified") {
          awsConfirmVerified(tool).catch(function () {});
        }
      });
    });
  }

  function awsHandoffStatusLabel(workflow) {
    var status = text(workflow && workflow.handoff_status);
    if (status === "uninitiated") return "uninitiated";
    if (status === "smtp_configured") return "SMTP configured";
    if (status === "ready_for_gmail_handoff") return "ready for Gmail handoff";
    if (status === "send_as_confirmed") return "send-as confirmed";
    if (status === "staged") return "staged";
    return "staging required";
  }

  function awsCompletionBoundaryLabel(workflow) {
    var boundary = text(workflow && workflow.completion_boundary);
    if (boundary === "uninitiated") return "uninitiated";
    if (boundary === "receive_path_pending") return "receive path pending";
    if (boundary === "gmail_inbox_dependent") return "gmail/inbox dependent";
    if (boundary === "completed") return "completed";
    return boundary.replace(/_/g, " ");
  }

  function awsReceiveStateLabel(inbound) {
    var state = text(inbound && inbound.receive_state);
    if (state === "receive_unconfigured") return "receive unconfigured";
    if (state === "receive_configured") return "receive configured";
    if (state === "receive_pending") return "receive pending";
    if (state === "receive_verified") return "receive verified";
    if (state === "receive_operational") return "receive operational";
    if (state === "receive_legacy_dependent") return "receive legacy dependent";
    return state.replace(/_/g, " ");
  }

  function awsBlockerCount(items) {
    return Array.isArray(items) ? String(items.length) : "0";
  }

  function renderFndEbiTraffic(tool) {
    var s = fndEbiSelectedSnapshot(tool);
    if (!s) return '<p class="data-tool__empty">No traffic snapshots available.</p>';
    var t = s.traffic && typeof s.traffic === "object" ? s.traffic : {};
    var out = [];
    out.push('<article class="card fnd-ebi-card"><div class="card__title">' + esc(text(s.domain || "")) + '</div><div class="card__body">');
    out.push("<p>24h: <strong>" + esc(String(t.requests_24h || 0)) + "</strong> · 7d: <strong>" + esc(String(t.requests_7d || 0)) + "</strong> · 30d: <strong>" + esc(String(t.requests_30d || 0)) + "</strong></p>");
    out.push("<p>Real pages 30d: <strong>" + esc(String(t.real_page_requests_30d || 0)) + "</strong> · Assets 30d: <strong>" + esc(String((t.asset_vs_page || {}).asset_requests || 0)) + "</strong></p>");
    out.push("<p>Responses 2xx/3xx/4xx/5xx: " + esc(String((t.response_breakdown || {})["2xx"] || 0)) + "/" + esc(String((t.response_breakdown || {})["3xx"] || 0)) + "/" + esc(String((t.response_breakdown || {})["4xx"] || 0)) + "/" + esc(String((t.response_breakdown || {})["5xx"] || 0)) + "</p>");
    out.push("<p>Bot share: <strong>" + esc(fndEbiFormatPct(t.bot_share || 0)) + "</strong> · Probes: <strong>" + esc(String(t.suspicious_probe_count || 0)) + "</strong></p>");
    out.push("<h4>Top Real Pages</h4>" + fndEbiListRows(t.top_pages, "No likely-human page traffic."));
    out.push("<h4>Top Requested Paths</h4>" + fndEbiListRows(t.top_requested_paths, "No path data."));
    out.push("<h4>Top Referrers</h4>" + fndEbiListRows(t.top_referrers, "No top referrers."));
    out.push("<p>Trend 7d: <span class=\"fnd-ebi-sparkline\">" + esc(fndEbiSparkline(t.trend_7d || [])) + "</span></p>");
    out.push("</div></article>");
    return out.join("");
  }

  function renderFndEbiEvents(tool) {
    var s = fndEbiSelectedSnapshot(tool);
    if (!s) return '<p class="data-tool__empty">No events snapshots available.</p>';
    var e = s.events_summary && typeof s.events_summary === "object" ? s.events_summary : {};
    var frontend = s.frontend && typeof s.frontend === "object" ? s.frontend : {};
    var source = s.events_file && typeof s.events_file === "object" ? s.events_file : {};
    var out = [];
    out.push('<article class="card fnd-ebi-card"><div class="card__title">' + esc(text(s.domain || "")) + '</div><div class="card__body">');
    out.push("<p>Events 24h/7d/30d: <strong>" + esc(String(e.events_24h || 0)) + "</strong> / <strong>" + esc(String(e.events_7d || 0)) + "</strong> / <strong>" + esc(String(e.events_30d || 0)) + "</strong></p>");
    out.push("<p>Sessions approx: <strong>" + esc(String(e.session_count_approx || 0)) + "</strong></p>");
    out.push(renderCardKeyValueRows({
      "events file state": text(source.state),
      "events file modified": text(source.modified_utc),
      "events raw lines": String(source.raw_line_count || 0),
      "frontend instrumentation": frontend.client_instrumentation_detected ? "detected" : "not detected",
      "instrumentation files": Array.isArray(frontend.instrumentation_files) ? frontend.instrumentation_files.join(", ") : ""
    }));
    out.push("<p>Trend 30d: <span class=\"fnd-ebi-sparkline\">" + esc(fndEbiSparkline(e.trend_30d || [])) + "</span></p>");
    out.push(fndEbiListRows(Object.keys(e.event_type_counts || {}).map(function (k) { return { key: k, count: (e.event_type_counts || {})[k] }; }), "No event type data."));
    out.push("</div></article>");
    return out.join("");
  }

  function renderFndEbiErrorsNoise(tool) {
    var s = fndEbiSelectedSnapshot(tool);
    if (!s) return '<p class="data-tool__empty">No errors/noise snapshots available.</p>';
    var n = s.errors_noise && typeof s.errors_noise === "object" ? s.errors_noise : {};
    var out = [];
    out.push('<article class="card fnd-ebi-card"><div class="card__title">' + esc(text(s.domain || "")) + '</div><div class="card__body">');
    out.push("<h4>Error Severity</h4>" + fndEbiListRows(Object.keys(n.error_severity_counts || {}).map(function (k) { return { key: k, count: (n.error_severity_counts || {})[k] }; }), "No error severity rows."));
    out.push("<h4>Top Site 4xx/5xx Routes</h4>" + fndEbiListRows(n.top_site_error_routes, "No site-route errors."));
    out.push("<h4>Top Asset 4xx/5xx Routes</h4>" + fndEbiListRows(n.top_asset_error_routes, "No asset-route errors."));
    out.push("<h4>Top Probe Routes</h4>" + fndEbiListRows(n.top_probe_routes, "No suspicious probes."));
    out.push("<h4>All Error Routes</h4>" + fndEbiListRows(n.top_error_routes, "No top error routes."));
    out.push("<h4>Probe Examples</h4>" + fndEbiListRows(n.suspicious_probe_examples, "No suspicious probes."));
    out.push("</div></article>");
    return out.join("");
  }

  function renderFndEbiFiles(tool) {
    var ctx = toolContext(tool.tool_id) || {};
    var files = Array.isArray(ctx.collection_files) ? ctx.collection_files : [];
    var warnings = Array.isArray(ctx.warnings) ? ctx.warnings : [];
    var selected = fndEbiSelectedSnapshot(tool);
    if (!files.length && !warnings.length) {
      return '<p class="data-tool__empty">No tool files discovered.</p>';
    }
    var rows = [];
    if (selected) {
      rows.push('<article class="card"><div class="card__kicker">Focused Profile</div><div class="card__title">' + esc(text(selected.domain || "")) + '</div><div class="card__body">');
      rows.push(renderInterfacePanelCardBody(null, {
        domain: text(selected.domain),
        site_root: text(selected.site_root),
        analytics_root: text(selected.analytics_root),
        access_log: selected.access_log,
        error_log: selected.error_log,
        events_file: selected.events_file,
        traffic_summary: selected.traffic || {},
        event_summary: selected.events_summary || {},
        frontend: selected.frontend || {},
        errors_noise: selected.errors_noise || {},
        warnings: selected.warnings || []
      }));
      rows.push("<h4>Access Log</h4>" + fndEbiSourceRows(selected.access_log));
      rows.push("<h4>Error Log</h4>" + fndEbiSourceRows(selected.error_log));
      rows.push("<h4>Events File</h4>" + fndEbiSourceRows(selected.events_file));
      rows.push("</div></article>");
    }
    rows.push("<table class=\"fnd-ebi-table\"><thead><tr><th>File</th><th>Kind</th><th>Records</th><th>Modified</th><th>Raw</th><th>Parsed</th><th>Truncated</th></tr></thead><tbody>");
    files.forEach(function (f) {
      if (!f || typeof f !== "object") return;
      var details = f.summary && typeof f.summary === "object" ? (f.summary.details && typeof f.summary.details === "object" ? f.summary.details : f.summary) : {};
      rows.push(
        "<tr><td><code>" +
          esc(text(f.relative_path || f.file_name || "")) +
          "</code></td><td>" +
          esc(text(f.content_kind || "")) +
          "</td><td>" +
          esc(String(f.record_count != null ? f.record_count : "")) +
          "</td><td>" +
          esc(text(f.modified_utc || details.modified_utc || "")) +
          "</td><td>" +
          esc(String(f.raw_line_count != null ? f.raw_line_count : (details.raw_line_count || ""))) +
          "</td><td>" +
          esc(String(f.parsed_line_count != null ? f.parsed_line_count : (details.parsed_line_count || ""))) +
          "</td><td>" +
          esc((f.truncated || details.truncated) ? "yes" : "no") +
          "</td></tr>"
      );
    });
    rows.push("</tbody></table>");
    if (warnings.length) {
      rows.push("<p><strong>Warnings</strong></p><ul class=\"fnd-ebi-warnings\">");
      warnings.forEach(function (w) {
        rows.push("<li>" + esc(text(w)) + "</li>");
      });
      rows.push("</ul>");
    }
    return rows.join("");
  }

  function renderFndEbiControlPanel(tool) {
    var ctx = toolContext(tool.tool_id) || {};
    var cards = Array.isArray(ctx.profile_cards) ? ctx.profile_cards : [];
    var snapshots = Array.isArray(ctx.analytics_snapshots) ? ctx.analytics_snapshots : [];
    var rows = fndEbiAnalyticsRows(cards, snapshots);
    if (!rows.length) {
      return '<div class="ide-controlpanel__empty">No hosted analytics profiles are staged in the tool sandbox.</div>';
    }
    var selectedDomain = text(fndEbiSelectedSnapshot(tool) && fndEbiSelectedSnapshot(tool).domain).toLowerCase();
    var out = [];
    rows.forEach(function (row) {
      var snapshot = row.analytics || fndEbiSnapshotFromCard(row.card || {});
      var traffic = snapshot.traffic && typeof snapshot.traffic === "object" ? snapshot.traffic : {};
      var eventsSummary = snapshot.events_summary && typeof snapshot.events_summary === "object" ? snapshot.events_summary : {};
      var domain = text(snapshot.domain || fndEbiDomainFromCard(row.card));
      out.push('<button type="button" class="system-tool-contextCard' + (selectedDomain === domain.toLowerCase() ? ' is-active' : '') + '" data-fnd-ebi-select-domain="' + esc(domain) + '">');
      out.push('<strong>' + esc(domain || "profile") + '</strong>');
      out.push('<small>' + esc(text(snapshot.health_label || "analytics")) + " · " + esc(String(traffic.real_page_requests_30d || 0)) + " real pages 30d</small>");
      out.push('<span>' + esc(String(eventsSummary.events_30d || 0)) + ' events 30d</span>');
      out.push('</button>');
    });
    return out.join("");
  }

  function awsProfileTokenFromFile(file) {
    var relativePath = text(file && (file.relative_path || file.file_name));
    if (!/^aws-csm\\..+\\.json$/i.test(relativePath)) return "";
    return relativePath.replace(/\\.json$/i, "").toLowerCase();
  }

  function renderAwsControlPanel(tool) {
    var ctx = toolContext(tool.tool_id) || {};
    var files = Array.isArray(ctx.collection_files) ? ctx.collection_files : [];
    if (!files.length) {
      return '<div class="ide-controlpanel__empty">No AWS-CMS sandbox files found.</div>';
    }
    var selectedCard = awsSelectedCard(tool);
    var selectedToken = awsProfileToken(selectedCard);
    var bucket = providerStateFor(tool.tool_id);
    var selectedFile = text(bucket.selectedFile);
    var out = [];
    out.push('<section class="aws-csm-controlFiles">');
    files.forEach(function (file) {
      if (!file || typeof file !== "object") return;
      var relativePath = text(file.relative_path || file.file_name || "");
      var profileToken = awsProfileTokenFromFile(file);
      var active = (profileToken && profileToken === selectedToken) || (!profileToken && selectedFile === relativePath);
      out.push('<button type="button" class="aws-csm-fileEntry' + (active ? ' is-active' : '') + '" data-aws-file="' + esc(relativePath) + '" data-aws-profile-file="' + esc(profileToken) + '">');
      out.push('<span class="aws-csm-fileEntry__name" title="' + esc(relativePath) + '">' + esc(limitText(relativePath, 38)) + '</span>');
      out.push('<span class="aws-csm-fileEntry__meta">' + esc(text(file.content_kind || "json")) + '</span>');
      out.push('</button>');
    });
    out.push('</section>');
    return out.join("");
  }

  function newsletterBodyFromCard(card) {
    return card && card.body && typeof card.body === "object" ? card.body : {};
  }

  function newsletterDomainFromCard(card) {
    var body = newsletterBodyFromCard(card);
    return text(body.domain || card && card.title || "");
  }

  function newsletterCards(tool) {
    var ctx = toolContext(tool.tool_id) || {};
    return Array.isArray(ctx.profile_cards) ? ctx.profile_cards : [];
  }

  function newsletterSelectDomain(toolId, domain) {
    var bucket = providerStateFor(toolId);
    bucket.selectedDomain = text(domain).toLowerCase();
  }

  function newsletterSelectedCard(tool) {
    var cards = newsletterCards(tool);
    if (!cards.length) return null;
    var bucket = providerStateFor(tool.tool_id);
    var selected = text(bucket.selectedDomain).toLowerCase();
    if (!selected) {
      newsletterSelectDomain(tool.tool_id, newsletterDomainFromCard(cards[0]));
      return cards[0];
    }
    for (var i = 0; i < cards.length; i += 1) {
      if (newsletterDomainFromCard(cards[i]).toLowerCase() === selected) {
        return cards[i];
      }
    }
    return cards[0];
  }

  function newsletterVerifiedSenders(card) {
    var body = newsletterBodyFromCard(card);
    return Array.isArray(body.verified_senders) ? body.verified_senders : [];
  }

  function newsletterSelectedSender(card) {
    var body = newsletterBodyFromCard(card);
    return body.selected_sender && typeof body.selected_sender === "object" ? body.selected_sender : {};
  }

  function newsletterStatusLabel(card) {
    var body = newsletterBodyFromCard(card);
    var sender = newsletterSelectedSender(card);
    if (!newsletterVerifiedSenders(card).length) return "no verified sender";
    if (!text(sender.send_as_email)) return "sender required";
    if (Number(body.subscribed_count || 0) <= 0) return "ready / no subscribers";
    return "ready to send";
  }

  function renderNewsletterDomainCards(tool) {
    var cards = newsletterCards(tool);
    if (!cards.length) {
      return '<div class="ide-controlpanel__empty">No newsletter domains are staged yet. Add a newsletter-admin domain profile and contact log first.</div>';
    }
    var selected = newsletterSelectedCard(tool);
    var selectedDomain = newsletterDomainFromCard(selected).toLowerCase();
    var out = [];
    cards.forEach(function (card) {
      var body = newsletterBodyFromCard(card);
      var domain = newsletterDomainFromCard(card);
      var active = domain.toLowerCase() === selectedDomain;
      out.push('<button type="button" class="system-tool-contextCard' + (active ? ' is-active' : '') + '" data-newsletter-domain="' + esc(domain) + '">');
      out.push('<strong>' + esc(domain) + '</strong>');
      out.push('<small>' + esc(newsletterStatusLabel(card)) + '</small>');
      out.push('<span>' + esc(String(body.subscribed_count || 0)) + ' subscribed · ' + esc(String(body.unsubscribed_count || 0)) + ' unsubscribed</span>');
      out.push('</button>');
    });
    return out.join("");
  }

  function renderNewsletterOverview(tool) {
    var cards = newsletterCards(tool);
    if (!cards.length) {
      return '<p class="data-tool__empty">No newsletter domains are configured.</p>';
    }
    var selected = newsletterSelectedCard(tool);
    var body = newsletterBodyFromCard(selected);
    var sender = newsletterSelectedSender(selected);
    var out = [];
    out.push('<article class="card"><div class="card__kicker">Newsletter Admin</div><div class="card__title">' + esc(newsletterDomainFromCard(selected)) + '</div><div class="card__body">');
    out.push('<p>The website contact log under <code>/srv/webapps/clients/&lt;domain&gt;/contacts/</code> is the canonical list for signup, send, and unsubscribe state.</p>');
    out.push(renderCardKeyValueRows({
      domain: newsletterDomainFromCard(selected),
      "list address": text(body.list_address),
      "newsletter sender": text(body.sender_address || body.list_address),
      "author mailbox": text(sender.send_as_email),
      "author profile": text(sender.profile_id),
      "delivery mode": text((body.profile || {}).delivery_mode || "aws_sqs_lambda_us_east_1"),
      "contact log": text(body.contact_log_path),
      contacts: String(body.contact_count || 0),
      subscribed: String(body.subscribed_count || 0),
      unsubscribed: String(body.unsubscribed_count || 0),
      status: newsletterStatusLabel(selected)
    }));
    out.push('</div></article>');
    out.push('<article class="card"><div class="card__kicker">Domains</div><div class="card__title">Newsletter-ready domains</div><div class="card__body">');
    out.push(renderNewsletterDomainCards(tool));
    out.push('</div></article>');
    return out.join("");
  }

  function renderNewsletterContacts(tool) {
    var selected = newsletterSelectedCard(tool);
    if (!selected) {
      return '<p class="data-tool__empty">Select a newsletter domain to inspect contacts.</p>';
    }
    var body = newsletterBodyFromCard(selected);
    var contacts = Array.isArray(body.contacts) ? body.contacts : [];
    var out = [];
    out.push('<article class="card"><div class="card__kicker">Canonical Contact Log</div><div class="card__title">' + esc(newsletterDomainFromCard(selected)) + '</div><div class="card__body">');
    out.push('<p><strong>Path:</strong> <code>' + esc(text(body.contact_log_path)) + '</code></p>');
    if (!contacts.length) {
      out.push('<p>No contacts are in the canonical log yet. Submit a website signup form to create the first subscriber.</p>');
    } else {
      out.push('<table class="fnd-ebi-table"><thead><tr><th>Email</th><th>Name</th><th>Status</th><th>Sent</th><th>Last sent</th><th>Updated</th></tr></thead><tbody>');
      contacts.forEach(function (row) {
        if (!row || typeof row !== "object") return;
        out.push('<tr>');
        out.push('<td><code>' + esc(text(row.email)) + '</code></td>');
        out.push('<td>' + esc(text(row.name)) + '</td>');
        out.push('<td>' + esc(row.subscribed ? "subscribed" : "unsubscribed") + '</td>');
        out.push('<td>' + esc(String(row.send_count || 0)) + '</td>');
        out.push('<td>' + esc(text(row.last_newsletter_sent_at)) + '</td>');
        out.push('<td>' + esc(text(row.updated_at)) + '</td>');
        out.push('</tr>');
      });
      out.push('</tbody></table>');
    }
    out.push('</div></article>');
    return out.join("");
  }

  function renderNewsletterComposer(tool) {
    var selected = newsletterSelectedCard(tool);
    if (!selected) {
      return '<p class="data-tool__empty">Select a newsletter domain to compose a test send.</p>';
    }
    var body = newsletterBodyFromCard(selected);
    var verified = newsletterVerifiedSenders(selected);
    var sender = newsletterSelectedSender(selected);
    var latestDispatch = body.latest_dispatch && typeof body.latest_dispatch === "object" ? body.latest_dispatch : {};
    var bucket = providerStateFor(tool.tool_id);
    var out = [];
    out.push('<article class="card"><div class="card__kicker">Compose</div><div class="card__title">Send a one-by-one test newsletter</div><div class="card__body">');
    out.push('<p>The live send queues one recipient job at a time. The selected verified mailbox submits the newsletter to <code>' + esc(text(body.list_address)) + '</code>, and recipients receive it from <code>' + esc(text(body.sender_address || body.list_address)) + '</code>.</p>');
    out.push('<div class="aws-csm-flowForm">');
    out.push('<label class="aws-csm-flowForm__field"><span>Author mailbox</span><select class="data-tool__fieldInput" data-newsletter-sender>');
    verified.forEach(function (item) {
      if (!item || typeof item !== "object") return;
      var profileId = text(item.profile_id);
      var selectedAttr = profileId === text(sender.profile_id) ? ' selected="selected"' : "";
      out.push('<option value="' + esc(profileId) + '"' + selectedAttr + '>' + esc(text(item.send_as_email)) + '</option>');
    });
    out.push('</select></label>');
    out.push('<label class="aws-csm-flowForm__field"><span>Subject</span><input type="text" class="data-tool__fieldInput" data-newsletter-subject placeholder="Test newsletter subject" value="Newsletter test for ' + esc(newsletterDomainFromCard(selected)) + '" /></label>');
    out.push('<label class="aws-csm-flowForm__field"><span>Body</span><textarea class="data-tool__fieldInput" data-newsletter-body rows="8" placeholder="Write a test message.">This is a test newsletter message for ' + esc(newsletterDomainFromCard(selected)) + '.\n\nIf this reaches you, the signup, canonical contact log, send, and unsubscribe loop is wired through the live website-root contact log.</textarea></label>');
    out.push('<div class="aws-csm-flowForm__actions">');
    out.push('<button type="button" class="data-tool__actionBtn is-active" data-newsletter-action="send">Send to subscribed contacts</button>');
    out.push('<button type="button" class="data-tool__actionBtn" data-newsletter-action="refresh">Refresh</button>');
    out.push('</div></div>');
    out.push(renderCardKeyValueRows({
      domain: newsletterDomainFromCard(selected),
      "newsletter sender": text(body.sender_address || body.list_address),
      "submission target": text(body.list_address),
      subscribed: String(body.subscribed_count || 0),
      unsubscribed: String(body.unsubscribed_count || 0),
      "verified author mailboxes": String(verified.length),
      status: newsletterStatusLabel(selected)
    }));
    if (!verified.length) {
      out.push('<p><strong>Blocked:</strong> no Gmail-verified mailbox is available for this domain yet.</p>');
    }
    if (bucket.pendingNewsletterAction) {
      out.push('<p><strong>Working:</strong> ' + esc(text(bucket.pendingNewsletterAction)) + '…</p>');
    }
    if (text(bucket.newsletterError)) {
      out.push('<p class="fnd-ebi-warning"><strong>Action error:</strong> ' + esc(text(bucket.newsletterError)) + '</p>');
    }
    out.push('</div></article>');
    if (latestDispatch && Object.keys(latestDispatch).length) {
      out.push('<article class="card"><div class="card__kicker">Latest Dispatch</div><div class="card__title">' + esc(text(latestDispatch.subject || "dispatch")) + '</div><div class="card__body">');
      out.push(renderCardKeyValueRows({
        "requested at": text(latestDispatch.requested_at),
        "completed at": text(latestDispatch.completed_at),
        "requested by": text(latestDispatch.requested_by),
        sender: text(latestDispatch.sender_address),
        author: text(latestDispatch.author_address),
        "reply to": text(latestDispatch.reply_to_address),
        targets: String(latestDispatch.target_count || 0),
        queued: String(latestDispatch.queued_count || 0),
        sent: String(latestDispatch.sent_count || 0)
      }));
      var results = Array.isArray(latestDispatch.results) ? latestDispatch.results : [];
      if (results.length) {
        out.push('<table class="fnd-ebi-table"><thead><tr><th>Email</th><th>Status</th><th>Message</th><th>Unsubscribe</th></tr></thead><tbody>');
        results.forEach(function (row) {
          if (!row || typeof row !== "object") return;
          out.push('<tr><td><code>' + esc(text(row.email)) + '</code></td><td>' + esc(text(row.status)) + '</td><td>' + esc(text(row.message_id || row.error)) + '</td><td>' + esc(limitText(text(row.unsubscribe_url), 72)) + '</td></tr>');
        });
        out.push('</tbody></table>');
      }
      out.push('</div></article>');
    }
    return out.join("");
  }

  function renderNewsletterFiles(tool) {
    var ctx = toolContext(tool.tool_id) || {};
    var files = Array.isArray(ctx.collection_files) ? ctx.collection_files : [];
    var selected = newsletterSelectedCard(tool);
    var out = [];
    if (selected) {
      var body = newsletterBodyFromCard(selected);
      out.push('<article class="card"><div class="card__kicker">Focused Domain</div><div class="card__title">' + esc(newsletterDomainFromCard(selected)) + '</div><div class="card__body">');
      out.push(renderCardKeyValueRows({
        "contact log": text(body.contact_log_path),
        "profile path": text(body.profile_path),
        "list address": text(body.list_address),
        "newsletter sender": text(body.sender_address || body.list_address),
        "author mailbox": text((body.selected_author || body.selected_sender || {}).send_as_email)
      }));
      out.push('</div></article>');
    }
    if (!files.length) {
      out.push('<p class="data-tool__empty">No newsletter-admin tool files were discovered.</p>');
      return out.join("");
    }
    out.push('<table class="fnd-ebi-table"><thead><tr><th>File</th><th>Kind</th><th>Records</th></tr></thead><tbody>');
    files.forEach(function (file) {
      if (!file || typeof file !== "object") return;
      out.push('<tr><td><code>' + esc(text(file.relative_path || file.path || file.file_name)) + '</code></td><td>' + esc(text(file.content_kind)) + '</td><td>' + esc(String(file.record_count || 0)) + '</td></tr>');
    });
    out.push('</tbody></table>');
    return out.join("");
  }

  function newsletterRefresh(tool) {
    var bucket = providerStateFor(tool.tool_id);
    bucket.newsletterError = "";
    return ensureToolContext(tool, true).then(function () {
      renderAll();
    }).catch(function (err) {
      bucket.newsletterError = err && err.message ? err.message : "Refresh failed.";
      renderAll();
      throw err;
    });
  }

  function newsletterSaveSender(tool, root) {
    var selected = newsletterSelectedCard(tool);
    if (!selected) return Promise.resolve();
    var domain = newsletterDomainFromCard(selected);
    var select = qs("[data-newsletter-sender]", root || els.toolInterfaceBody);
    var profileId = text(select && select.value);
    if (!profileId) return Promise.resolve();
    var bucket = providerStateFor(tool.tool_id);
    bucket.pendingNewsletterAction = "Saving sender";
    bucket.newsletterError = "";
    renderAll();
    return api("/portal/api/admin/newsletter/domain/" + encodeURIComponent(domain) + "/config", "POST", {
      selected_sender_profile_id: profileId
    }).then(function () {
      bucket.pendingNewsletterAction = "";
      return ensureToolContext(tool, true);
    }).then(function () {
      renderAll();
    }).catch(function (err) {
      bucket.pendingNewsletterAction = "";
      bucket.newsletterError = err && err.message ? err.message : "Unable to save sender.";
      renderAll();
      throw err;
    });
  }

  function newsletterSend(tool, root) {
    var selected = newsletterSelectedCard(tool);
    if (!selected) return Promise.resolve();
    var domain = newsletterDomainFromCard(selected);
    var senderSelect = qs("[data-newsletter-sender]", root || els.toolInterfaceBody);
    var subjectInput = qs("[data-newsletter-subject]", root || els.toolInterfaceBody);
    var bodyInput = qs("[data-newsletter-body]", root || els.toolInterfaceBody);
    var subject = text(subjectInput && subjectInput.value);
    var body = text(bodyInput && bodyInput.value);
    var selectedSenderProfileId = text(senderSelect && senderSelect.value);
    var bucket = providerStateFor(tool.tool_id);
    bucket.pendingNewsletterAction = "Sending newsletter";
    bucket.newsletterError = "";
    renderAll();
    return api("/portal/api/admin/newsletter/domain/" + encodeURIComponent(domain) + "/send", "POST", {
      subject: subject,
      body_text: body,
      selected_sender_profile_id: selectedSenderProfileId
    }).then(function () {
      bucket.pendingNewsletterAction = "";
      return ensureToolContext(tool, true);
    }).then(function () {
      renderAll();
    }).catch(function (err) {
      bucket.pendingNewsletterAction = "";
      bucket.newsletterError = err && err.message ? err.message : "Newsletter send failed.";
      renderAll();
      throw err;
    });
  }

  function bindNewsletterInterfaceActions(tool, root) {
    qsa("[data-newsletter-domain]", root || els.toolInterfaceBody).forEach(function (node) {
      node.addEventListener("click", function () {
        newsletterSelectDomain(tool.tool_id, node.getAttribute("data-newsletter-domain"));
        state.activeMediationMode = "overview";
        renderAll();
      });
    });
    qsa("[data-newsletter-sender]", root || els.toolInterfaceBody).forEach(function (node) {
      node.addEventListener("change", function () {
        newsletterSaveSender(tool, root).catch(function () {});
      });
    });
    qsa("[data-newsletter-action]", root || els.toolInterfaceBody).forEach(function (node) {
      node.addEventListener("click", function () {
        var action = text(node.getAttribute("data-newsletter-action"));
        if (action === "send") {
          newsletterSend(tool, root).catch(function () {});
          return;
        }
        if (action === "refresh") {
          newsletterRefresh(tool).catch(function () {});
        }
      });
    });
  }

  var fndEbiMediationProvider = {
    defaultMode: function (tool) {
      return normalizeModeId(toolInterfaceContribution(tool).default_mode || "overview") || "overview";
    },
    modes: function (tool) {
      var contribution = toolInterfaceContribution(tool);
      var rawModes = Array.isArray(contribution.modes) ? contribution.modes : ["overview", "traffic", "events", "errors_noise", "files"];
      return rawModes.map(function (mode) {
        var id = normalizeModeId(mode) || "overview";
        return { id: id, label: titleCase(mode) };
      });
    },
    title: function (tool) {
      return text(tool && (tool.label || tool.tool_id)) || "FND EBI";
    },
    kicker: function (tool) {
      return text(toolInterfaceContribution(tool).label) || "Hosted site analytics";
    },
    meta: function (tool) {
      var ctx = toolContext(tool.tool_id) || {};
      var snapshots = Array.isArray(ctx.analytics_snapshots) ? ctx.analytics_snapshots : [];
      var selected = fndEbiSelectedSnapshot(tool);
      return "Domains: " + String(snapshots.length) + " · focus: " + (text(selected && selected.domain) || "unselected");
    },
    ensureReady: function (tool, force) {
      return ensureToolContext(tool, force).then(function (ctx) {
        var snapshots = Array.isArray(ctx.analytics_snapshots) ? ctx.analytics_snapshots : [];
        var bucket = providerStateFor(tool.tool_id);
        if (!text(bucket.selectedDomain) && snapshots.length) {
          bucket.selectedDomain = text(snapshots[0].domain || "").toLowerCase();
        }
        ensureInterfacePanelForServiceTool(tool);
        return ctx;
      });
    },
    render: function (tool, mode) {
      if (mode === "traffic") return renderFndEbiTraffic(tool);
      if (mode === "events") return renderFndEbiEvents(tool);
      if (mode === "errors_noise") return renderFndEbiErrorsNoise(tool);
      if (mode === "files") return renderFndEbiFiles(tool);
      return renderFndEbiOverview(tool);
    },
    renderInterface: function (tool, mode) {
      return this.render(tool, mode);
    },
    renderControlPanel: function (tool) {
      return renderFndEbiControlPanel(tool);
    },
    bind: function (tool, root) {
      qsa("[data-fnd-ebi-select-domain]", root || els.mediationBody).forEach(function (node) {
        node.addEventListener("click", function () {
          fndEbiSelectDomain(text(node.getAttribute("data-fnd-ebi-select-domain")));
          state.activeMediationMode = "overview";
          renderAll();
        });
      });
    },
    bindInterface: function (tool) {
      this.bind(tool, els.toolInterfaceBody);
    },
    bindControlPanel: function (tool) {
      this.bind(tool, els.toolContextMount);
    }
  };

  var awsServiceMediationProvider = {
    defaultMode: function (tool) {
      return normalizeModeId(toolInterfaceContribution(tool).default_mode || "overview") || "overview";
    },
    modes: function (tool) {
      var contribution = toolInterfaceContribution(tool);
      var rawModes = Array.isArray(contribution.modes) ? contribution.modes : ["overview", "smtp", "verification", "files"];
      return rawModes.map(function (mode) {
        var id = normalizeModeId(mode) || "overview";
        var label = titleCase(mode);
        if (id === "smtp") label = "SMTP";
        if (id === "files") label = "File";
        return { id: id, label: label };
      });
    },
    showModes: function (tool) {
      return !!awsSelectedCard(tool);
    },
    title: function (tool) {
      return text(tool && (tool.label || tool.tool_id)) || "AWS-CMS";
    },
    kicker: function () {
      return "Operator send-as onboarding";
    },
    meta: function (tool) {
      var ctx = toolContext(tool.tool_id) || {};
      var cards = Array.isArray(ctx.profile_cards) ? ctx.profile_cards : [];
      var ready = cards.filter(function (card) {
        var workflow = awsWorkflowFromCard(card);
        return !!workflow.is_ready_for_user_handoff;
      }).length;
      var focused = awsSelectedCard(tool);
      var identity = focused && focused.body && typeof focused.body === "object" && focused.body.identity && typeof focused.body.identity === "object"
        ? focused.body.identity
        : {};
      var focusLabel = text(identity.domain || focused && (focused.title || focused.card_id) || "");
      var suffix = focusLabel ? " · focus: " + focusLabel : "";
      return "Profiles: " + String(cards.length) + " · ready for handoff: " + String(ready) + suffix;
    },
    ensureReady: function (tool, force) {
      return ensureToolContext(tool, force).then(function (ctx) {
        ensureInterfacePanelForServiceTool(tool);
        return ctx;
      });
    },
    render: function (tool, mode) {
      if (mode === "smtp") {
        return renderAwsSmtp(tool);
      }
      if (mode === "verification") {
        return renderAwsVerification(tool);
      }
      if (mode === "files") {
        return renderAwsFiles(tool);
      }
      return renderAwsOverview(tool);
    },
    renderInterface: function (tool, mode) {
      return this.render(tool, mode);
    },
    renderControlPanel: function (tool) {
      return renderAwsControlPanel(tool);
    },
    bind: function (tool, root) {
      bindAwsInterfaceActions(tool, root || els.mediationBody);
    },
    bindInterface: function (tool) {
      bindAwsInterfaceActions(tool, els.toolInterfaceBody);
    },
    bindControlPanel: function (tool) {
      bindAwsInterfaceActions(tool, els.toolContextMount);
    }
  };

  var newsletterAdminProvider = {
    defaultMode: function (tool) {
      return normalizeModeId(toolInterfaceContribution(tool).default_mode || "overview") || "overview";
    },
    modes: function (tool) {
      var contribution = toolInterfaceContribution(tool);
      var rawModes = Array.isArray(contribution.modes) ? contribution.modes : ["overview", "contacts", "composer", "files"];
      return rawModes.map(function (mode) {
        var id = normalizeModeId(mode) || "overview";
        return { id: id, label: titleCase(mode) };
      });
    },
    title: function (tool) {
      return text(tool && (tool.label || tool.tool_id)) || "Newsletter Admin";
    },
    kicker: function () {
      return "Website-owned contact logs";
    },
    meta: function (tool) {
      var cards = newsletterCards(tool);
      var selected = newsletterSelectedCard(tool);
      var focus = selected ? " · focus: " + newsletterDomainFromCard(selected) : "";
      return "Domains: " + String(cards.length) + focus;
    },
    ensureReady: function (tool, force) {
      return ensureToolContext(tool, force).then(function (ctx) {
        var cards = Array.isArray(ctx.profile_cards) ? ctx.profile_cards : [];
        if (cards.length) {
          newsletterSelectDomain(tool.tool_id, newsletterDomainFromCard(newsletterSelectedCard(tool) || cards[0]));
        }
        ensureInterfacePanelForServiceTool(tool);
        return ctx;
      });
    },
    render: function (tool, mode) {
      if (mode === "contacts") return renderNewsletterContacts(tool);
      if (mode === "composer") return renderNewsletterComposer(tool);
      if (mode === "files") return renderNewsletterFiles(tool);
      return renderNewsletterOverview(tool);
    },
    renderInterface: function (tool, mode) {
      return this.render(tool, mode);
    },
    renderControlPanel: function (tool) {
      return renderNewsletterDomainCards(tool);
    },
    bind: function (tool, root) {
      bindNewsletterInterfaceActions(tool, root || els.mediationBody);
    },
    bindInterface: function (tool) {
      bindNewsletterInterfaceActions(tool, els.toolInterfaceBody);
    },
    bindControlPanel: function (tool) {
      bindNewsletterInterfaceActions(tool, els.toolContextMount);
    }
  };

  var mediationProviders = {
    agro_erp: agroMediationProvider,
    fnd_ebi: fndEbiMediationProvider,
    aws_platform_admin: awsServiceMediationProvider,
    newsletter_admin: newsletterAdminProvider
  };

  function bootstrapMediateToolFromQuery() {
    try {
      var params = new URLSearchParams(window.location.search || "");
      var tid = text(params.get("mediate_tool"));
      if (!tid) return Promise.resolve();
      enterToolLayer(
        tid,
        "query",
        text(els.shell && els.shell.getAttribute("data-shell-composition")) || "system"
      );
      ensureInterfacePanelForServiceTool({
        shell_composition_mode: text(els.shell && els.shell.getAttribute("data-shell-composition")) || "system",
        foreground_surface: "interface_panel"
      });
      return api("/portal/api/data/system/sandbox_context", "POST", {
        shell_verb: "mediate",
        current_verb: "mediate",
        shell_surface: "tool_mediation",
        mediation_scope: "tool_sandbox",
        tool_id: tid
      }).then(function (payload) {
        state.selectedContext = payload || {};
        renderAll();
        openTool(tid);
      });
    } catch (e) {
      return Promise.resolve();
    }
  }

  document.addEventListener("mycite:shell:selection-input", function (event) {
    var detail = event && event.detail && typeof event.detail === "object" ? event.detail : {};
    var documentPayload = detail.document && typeof detail.document === "object" ? detail.document : null;
    if (!documentPayload) return;
    var origin = selectionOrigin(detail);
    if (shouldIgnoreSelectionInput(detail)) {
      return;
    }
    if (state.toolLayer.active && state.toolLayer.locked && isExplicitSelectionOrigin(origin)) {
      exitToolLayer();
      state.activeToolId = "";
      state.activeMediationMode = "";
    }
    state.lastSelectionInput = {
      document: documentPayload,
      selected_row: detail.selected_row && typeof detail.selected_row === "object" ? detail.selected_row : null,
      origin: origin
    };
    state.activeVerb = text(detail.current_verb || detail.shell_verb || state.activeVerb || "navigate") || "navigate";
    api("/portal/api/data/system/selection_context", "POST", {
      document: documentPayload,
      selected_row: detail.selected_row && typeof detail.selected_row === "object" ? detail.selected_row : null,
      current_verb: state.activeVerb,
      shell_verb: state.activeVerb,
      origin: origin
    }).then(function (payload) {
      state.selectedContext = payload || {};
      renderAll();
    }).catch(function (err) {
      if (els.selectionSummary) {
        els.selectionSummary.className = "ide-controlpanel__empty";
        els.selectionSummary.textContent = err && err.message ? err.message : "Selection context failed to load.";
      }
    });
  });

  document.addEventListener("mycite:shell:verb-changed", function (event) {
    var detail = event && event.detail && typeof event.detail === "object" ? event.detail : {};
    if (state.toolLayer.active && state.toolLayer.locked) {
      state.activeVerb = "mediate";
      renderAll();
      return;
    }
    state.activeVerb = text(detail.verb || state.activeVerb || "navigate") || "navigate";
    if (state.lastSelectionInput && state.lastSelectionInput.document) {
      emitShellEvent("mycite:shell:selection-input", {
        document: state.lastSelectionInput.document,
        selected_row: state.lastSelectionInput.selected_row,
        current_verb: state.activeVerb,
        origin: text(state.lastSelectionInput.origin || "user_task_change")
      });
    } else {
      renderAll();
    }
  });

  document.addEventListener("mycite:shell:workbench-payload", function () {
    renderAll();
  });

  document.addEventListener("mycite:shell:file-focus-changed", function (event) {
    var detail = event && event.detail && typeof event.detail === "object" ? event.detail : {};
    var origin = selectionOrigin(detail);
    if (state.toolLayer.active && state.toolLayer.locked && !isExplicitSelectionOrigin(origin)) {
      return;
    }
    if (state.toolLayer.active && state.toolLayer.locked && isExplicitSelectionOrigin(origin)) {
      exitToolLayer();
    }
    state.activeToolId = "";
    state.activeMediationMode = "";
    renderAll();
  });

  if (els.mediationCloseBtn) {
    els.mediationCloseBtn.addEventListener("click", function () {
      exitToolLayer();
      state.activeToolId = "";
      state.activeMediationMode = "";
      renderAll();
    });
  }

  bootstrapMediateToolFromQuery()
    .catch(function () {})
    .finally(function () {
      renderAll();
    });
})();
