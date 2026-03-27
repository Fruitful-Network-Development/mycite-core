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

  var systemWorkspace = qs(".system-center-workspace");
  if (!systemWorkspace) {
    return;
  }

  var els = {
    selectionSummary: qs("#systemSelectionSummary"),
    compatibleTools: qs("#systemCompatibleTools"),
    inspectorCardsRoot: qs("#systemShellInspectorCards"),
    inspectorCardsMount: qs("#systemInspectorCardsMount"),
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
      source: ""
    }
  };

  function syncToolLayerUiState() {
    var active = !!(state.toolLayer && state.toolLayer.active);
    systemWorkspace.classList.toggle("is-tool-layer-active", active);
    document.body.classList.toggle("portal-tool-layer-active", active);
  }

  function enterToolLayer(toolId, source) {
    state.toolLayer.active = true;
    state.toolLayer.locked = true;
    state.toolLayer.toolId = text(toolId).toLowerCase();
    state.toolLayer.source = text(source) || "runtime";
    state.activeVerb = "mediate";
    syncToolLayerUiState();
  }

  function exitToolLayer() {
    state.toolLayer.active = false;
    state.toolLayer.locked = false;
    state.toolLayer.toolId = "";
    state.toolLayer.source = "";
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
      "<div><strong>Attention</strong><br/><code>" + esc(attentionAddress || selection.selected_ref_or_document_id || "") + "</code></div>" +
      "<div><strong>Label</strong><br/><span>" + esc(selection.display_name || "") + "</span></div>" +
      "<div><strong>Directive</strong><br/><span>" + esc(directive || "navigate") + "</span></div>" +
      "<div><strong>Archetype</strong><br/><span>" + esc(resolved.family || family.kind || "datum") + "</span></div>" +
      "<div><strong>Time</strong><br/><code>" + esc(timeAddress || "not selected") + "</code></div>";
  }

  function renderCompatibleTools() {
    if (!els.compatibleTools) return;
    els.compatibleTools.innerHTML = "";
    var tools = activeCompatibleTools();
    if (!tools.length) {
      var emptyMessage = state.activeVerb === "mediate"
        ? "No compatible mediations for the current context."
        : "Open Mediate to browse compatible tools for the current context.";
      els.compatibleTools.innerHTML = '<div class="ide-controlpanel__empty">' + esc(emptyMessage) + "</div>";
      return;
    }
    var list = document.createElement("div");
    list.className = "ide-controlpanel__list";
    tools.forEach(function (tool) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "ide-controlpanel__link" + (text(tool.tool_id) === state.activeToolId ? " is-active" : "");
      button.setAttribute("data-shell-tool-id", text(tool.tool_id));
      var contribution = toolContribution(tool);
      button.innerHTML =
        "<span>" + esc(tool.label || tool.tool_id || "tool") + "</span>" +
        "<small>" + esc(contribution.label || contribution.workspace_id || "mediation workspace") + "</small>";
      button.addEventListener("click", function () {
        openTool(text(tool.tool_id));
      });
      list.appendChild(button);
    });
    els.compatibleTools.appendChild(list);
  }

  function renderInspectorCards() {
    if (!els.inspectorCardsRoot || !els.inspectorCardsMount) return;
    var cards = [];
    if (state.selectedContext && Array.isArray(state.selectedContext.inspector_cards)) {
      cards = cards.concat(state.selectedContext.inspector_cards);
    }
    var tool = activeTool();
    var toolCtx = tool ? toolContext(tool.tool_id) : null;
    if (toolCtx && Array.isArray(toolCtx.inspector_cards)) {
      cards = cards.concat(toolCtx.inspector_cards);
    }
    els.inspectorCardsMount.innerHTML = "";
    els.inspectorCardsRoot.hidden = cards.length === 0;
    cards.forEach(function (card) {
      var article = document.createElement("article");
      article.className = "card";
      var body = card && card.body && typeof card.body === "object" ? card.body : {};
      article.innerHTML =
        '<div class="card__kicker">' + esc(card.kind || "Inspector") + "</div>" +
        '<div class="card__title">' + esc(card.title || "Card") + "</div>" +
        '<div class="card__body">' +
        (card.summary ? "<p>" + esc(card.summary) + "</p>" : "") +
        '<pre class="jsonblock">' + esc(JSON.stringify(body, null, 2)) + "</pre>" +
        "</div>";
      els.inspectorCardsMount.appendChild(article);
    });
  }

  function ensureToolContext(tool, force) {
    var token = text(tool && tool.tool_id).toLowerCase();
    if (!token) return Promise.resolve({});
    if (state.toolContexts[token] && !force) {
      return Promise.resolve(state.toolContexts[token]);
    }
    var inspector = toolInspectorContribution(tool);
    var contribution = toolContribution(tool);
    var route = text(inspector.config_context_route || contribution.activation_route);
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

  function renderMediationWorkspaceBody() {
    if (!els.mediationBody || !els.mediationWorkbench) return;
    var tool = activeTool();
    if (state.activeVerb !== "mediate" || !tool) {
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
    els.mediationBody.innerHTML = provider.render(tool, state.activeMediationMode);
    if (typeof provider.bind === "function") {
      provider.bind(tool);
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
    renderInspectorCards();
    renderMediationWorkspaceBody();
  }

  function openTool(toolId) {
    var tool = findCompatibleTool(toolId);
    if (!tool) return;
    state.activeToolId = text(tool.tool_id);
    if (state.toolLayer.active && text(tool.tool_id).toLowerCase() === text(state.toolLayer.toolId)) {
      state.activeVerb = "mediate";
    }
    state.activeMediationMode = activeToolProvider().defaultMode(tool);
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

  function renderChronologyWorkbench(tool) {
    var bucket = agroState(tool);
    var calendar = bucket.timeContext && bucket.timeContext.calendar && typeof bucket.timeContext.calendar === "object"
      ? bucket.timeContext.calendar
      : {};
    var monthLabels = Array.isArray(calendar.month_labels) ? calendar.month_labels : ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
    var year = Number(calendar.year || new Date().getUTCFullYear());
    var selectedMonth = Number(calendar.month || 1);
    var selectedDay = Number(calendar.day || 1);
    var dayCount = Number(calendar.days_in_month || 31);
    var selectedScope = text(bucket.timeContext && bucket.timeContext.selected_scope);
    if (selectedScope) setSelectedTimeContext(selectedScope);
    var visibleObjects = Array.isArray(bucket.timeContext && bucket.timeContext.objects) ? bucket.timeContext.objects : [];
    var monthArc = monthLabels.map(function (label, idx) {
      var month = idx + 1;
      var active = month === selectedMonth ? " is-active" : "";
      return '<button type="button" class="agro-time__month' + active + '" data-agro-time-scope="13-787-' + year + '-' + month + '">' + esc(label) + "</button>";
    }).join("");
    var dayTicks = Array(Math.max(dayCount, 1)).fill(0).map(function (_, idx) {
      var d = idx + 1;
      var active = d === selectedDay ? " is-active" : "";
      return '<button type="button" class="agro-time__tick' + active + '" data-agro-time-scope="13-787-' + year + '-' + selectedMonth + '-' + d + '" title="Day ' + d + '"></button>';
    }).join("");
    var dayRow = Array(Math.max(dayCount, 1)).fill(0).map(function (_, idx) {
      var d = idx + 1;
      var active = d === selectedDay ? " is-active" : "";
      return '<button type="button" class="agro-time__dayCell' + active + '" data-agro-time-scope="13-787-' + year + '-' + selectedMonth + '-' + d + '">' + d + "</button>";
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
      '<div class="agro-time__scope"><strong>' + esc(selectedScope || "13-787-" + year) + "</strong></div>" +
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
    return api(endpoint, "POST", { selected_scope: scope }).then(function (payload) {
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
          var target = dir === "prev" ? year - 1 : year + 1;
          loadAgroTimeScope(tool, "13-787-" + target).catch(function (err) {
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
    var parts = [];
    parts.push('<div class="fnd-ebi-gallery">');
    rows.forEach(function (row) {
      var c = row.card || {};
      var s = row.analytics || {};
      var snapshot = fndEbiSnapshotFromCard(c);
      var accessState = snapshot.access_log && typeof snapshot.access_log === "object" ? snapshot.access_log : {};
      var errorState = snapshot.error_log && typeof snapshot.error_log === "object" ? snapshot.error_log : {};
      var eventState = snapshot.events_file && typeof snapshot.events_file === "object" ? snapshot.events_file : {};
      var traffic = snapshot.traffic && typeof snapshot.traffic === "object" ? snapshot.traffic : {};
      var eventsSummary = snapshot.events_summary && typeof snapshot.events_summary === "object" ? snapshot.events_summary : {};
      var snapWarnings = Array.isArray(snapshot.warnings) ? snapshot.warnings : [];
      var title = text(c.title || c.card_id || "Site");
      var health = text(snapshot.health_label || "healthy");
      var sparkline = fndEbiSparkline(traffic.trend_7d || []);
      parts.push('<article class="card fnd-ebi-card" data-fnd-ebi-select-domain="' + esc(text(snapshot.domain || title)) + '">');
      parts.push('<div class="card__kicker">' + esc(health) + "</div>");
      parts.push('<div class="card__title">' + esc(title) + "</div>");
      parts.push('<div class="card__body">');
      parts.push("<p><strong>Domain</strong> <code>" + esc(fndEbiDomainFromCard(c) || "") + "</code></p>");
      parts.push("<p><strong>Freshness</strong> access=" + esc(text((snapshot.freshness || {}).access_last_seen_utc || "n/a")) + "</p>");
      parts.push("<ul class=\"fnd-ebi-metrics\">");
      parts.push("<li><span>Requests (30d)</span> <strong>" + esc(String(traffic.requests_30d || 0)) + "</strong></li>");
      parts.push("<li><span>Unique visitors</span> <strong>" + esc(String(traffic.unique_visitors_approx_30d || 0)) + "</strong></li>");
      parts.push("<li><span>Events (30d)</span> <strong>" + esc(String(eventsSummary.events_30d || 0)) + "</strong></li>");
      parts.push("<li><span>Errors</span> <strong>" + esc(String((traffic.response_breakdown || {})["4xx"] || 0)) + "</strong></li>");
      parts.push("<li><span>Bot share</span> <strong>" + esc(fndEbiFormatPct(traffic.bot_share)) + "</strong></li>");
      parts.push("<li><span>Probes</span> <strong>" + esc(String(traffic.suspicious_probe_count || 0)) + "</strong></li>");
      parts.push("</ul>");
      parts.push('<p><strong>Trend</strong> <span class="fnd-ebi-sparkline">' + esc(sparkline) + "</span></p>");
      parts.push("<p><small>logs: access " + esc(accessState.present ? "ok" : "missing") + " · error " + esc(errorState.present ? "ok" : "missing") + " · events " + esc(eventState.present ? "ok" : "missing") + "</small></p>");
      if (snapWarnings.length) {
        parts.push('<ul class="fnd-ebi-warnings">');
        snapWarnings.slice(0, 8).forEach(function (warning) {
          parts.push("<li>" + esc(text(warning)) + "</li>");
        });
        parts.push("</ul>");
      }
      parts.push("</div></article>");
    });
    parts.push("</div>");
    if (!rows.length && !snapshots.length) {
      return '<p class="data-tool__empty">No profile cards from tool sandbox. Check utilities/tools/fnd-ebi and web-analytics.json.</p>';
    }
    var selected = fndEbiSelectedSnapshot(tool);
    if (selected) {
      var trafficSelected = selected.traffic && typeof selected.traffic === "object" ? selected.traffic : {};
      var eventsSelected = selected.events_summary && typeof selected.events_summary === "object" ? selected.events_summary : {};
      var noiseSelected = selected.errors_noise && typeof selected.errors_noise === "object" ? selected.errors_noise : {};
      parts.push('<article class="card fnd-ebi-detail">');
      parts.push('<div class="card__kicker">Domain Detail</div>');
      parts.push('<div class="card__title">' + esc(text(selected.domain || "")) + "</div>");
      parts.push('<div class="card__body">');
      parts.push("<p><strong>Traffic trend 30d</strong> <span class=\"fnd-ebi-sparkline\">" + esc(fndEbiSparkline(trafficSelected.trend_30d || [])) + "</span></p>");
      parts.push("<p><strong>Page vs Asset</strong> page=" + esc(String(((trafficSelected.asset_vs_page || {}).page_requests) || 0)) + " · asset=" + esc(String(((trafficSelected.asset_vs_page || {}).asset_requests) || 0)) + "</p>");
      parts.push("<p><strong>Bot vs Human-like</strong> bot=" + esc(fndEbiFormatPct(trafficSelected.bot_share || 0)) + " · human=" + esc(fndEbiFormatPct(1 - (Number(trafficSelected.bot_share) || 0))) + "</p>");
      parts.push("<h4>Top Pages</h4>" + fndEbiListRows(trafficSelected.top_pages, "No page requests parsed."));
      parts.push("<h4>Top Referrers</h4>" + fndEbiListRows(trafficSelected.top_referrers, "No referrers parsed."));
      parts.push("<h4>Top Error Routes</h4>" + fndEbiListRows(noiseSelected.top_error_routes, "No error routes."));
      parts.push("<h4>Suspicious Probes</h4>" + fndEbiListRows(noiseSelected.suspicious_probe_examples, "No suspicious probes parsed."));
      parts.push("<h4>Event Coverage</h4>" + fndEbiListRows(Object.keys(eventsSelected.event_type_counts || {}).map(function (k) { return { key: k, count: (eventsSelected.event_type_counts || {})[k] }; }), "No event types parsed."));
      parts.push("</div></article>");
    }
    return parts.join("");
  }

  function renderFndEbiTraffic(tool) {
    var ctx = toolContext(tool.tool_id) || {};
    var snapshots = Array.isArray(ctx.analytics_snapshots) ? ctx.analytics_snapshots : [];
    if (!snapshots.length) return '<p class="data-tool__empty">No traffic snapshots available.</p>';
    var out = [];
    snapshots.forEach(function (s) {
      var t = s.traffic && typeof s.traffic === "object" ? s.traffic : {};
      out.push('<article class="card fnd-ebi-card"><div class="card__title">' + esc(text(s.domain || "")) + '</div><div class="card__body">');
      out.push("<p>24h: <strong>" + esc(String(t.requests_24h || 0)) + "</strong> · 7d: <strong>" + esc(String(t.requests_7d || 0)) + "</strong> · 30d: <strong>" + esc(String(t.requests_30d || 0)) + "</strong></p>");
      out.push("<p>Responses 2xx/3xx/4xx/5xx: " + esc(String((t.response_breakdown || {})["2xx"] || 0)) + "/" + esc(String((t.response_breakdown || {})["3xx"] || 0)) + "/" + esc(String((t.response_breakdown || {})["4xx"] || 0)) + "/" + esc(String((t.response_breakdown || {})["5xx"] || 0)) + "</p>");
      out.push("<p>Bot share: <strong>" + esc(fndEbiFormatPct(t.bot_share || 0)) + "</strong> · Probes: <strong>" + esc(String(t.suspicious_probe_count || 0)) + "</strong></p>");
      out.push("<p>Trend 7d: <span class=\"fnd-ebi-sparkline\">" + esc(fndEbiSparkline(t.trend_7d || [])) + "</span></p>");
      out.push("</div></article>");
    });
    return out.join("");
  }

  function renderFndEbiEvents(tool) {
    var ctx = toolContext(tool.tool_id) || {};
    var snapshots = Array.isArray(ctx.analytics_snapshots) ? ctx.analytics_snapshots : [];
    if (!snapshots.length) return '<p class="data-tool__empty">No events snapshots available.</p>';
    var out = [];
    snapshots.forEach(function (s) {
      var e = s.events_summary && typeof s.events_summary === "object" ? s.events_summary : {};
      out.push('<article class="card fnd-ebi-card"><div class="card__title">' + esc(text(s.domain || "")) + '</div><div class="card__body">');
      out.push("<p>Events 24h/7d/30d: <strong>" + esc(String(e.events_24h || 0)) + "</strong> / <strong>" + esc(String(e.events_7d || 0)) + "</strong> / <strong>" + esc(String(e.events_30d || 0)) + "</strong></p>");
      out.push("<p>Sessions approx: <strong>" + esc(String(e.session_count_approx || 0)) + "</strong></p>");
      out.push("<p>Trend 30d: <span class=\"fnd-ebi-sparkline\">" + esc(fndEbiSparkline(e.trend_30d || [])) + "</span></p>");
      out.push(fndEbiListRows(Object.keys(e.event_type_counts || {}).map(function (k) { return { key: k, count: (e.event_type_counts || {})[k] }; }), "No event type data."));
      out.push("</div></article>");
    });
    return out.join("");
  }

  function renderFndEbiErrorsNoise(tool) {
    var ctx = toolContext(tool.tool_id) || {};
    var snapshots = Array.isArray(ctx.analytics_snapshots) ? ctx.analytics_snapshots : [];
    if (!snapshots.length) return '<p class="data-tool__empty">No errors/noise snapshots available.</p>';
    var out = [];
    snapshots.forEach(function (s) {
      var n = s.errors_noise && typeof s.errors_noise === "object" ? s.errors_noise : {};
      out.push('<article class="card fnd-ebi-card"><div class="card__title">' + esc(text(s.domain || "")) + '</div><div class="card__body">');
      out.push("<h4>Error Severity</h4>" + fndEbiListRows(Object.keys(n.error_severity_counts || {}).map(function (k) { return { key: k, count: (n.error_severity_counts || {})[k] }; }), "No error severity rows."));
      out.push("<h4>Top Error Routes</h4>" + fndEbiListRows(n.top_error_routes, "No top error routes."));
      out.push("<h4>Probe Examples</h4>" + fndEbiListRows(n.suspicious_probe_examples, "No suspicious probes."));
      out.push("</div></article>");
    });
    return out.join("");
  }

  function renderFndEbiFiles(tool) {
    var ctx = toolContext(tool.tool_id) || {};
    var files = Array.isArray(ctx.collection_files) ? ctx.collection_files : [];
    var warnings = Array.isArray(ctx.warnings) ? ctx.warnings : [];
    if (!files.length && !warnings.length) {
      return '<p class="data-tool__empty">No tool files discovered.</p>';
    }
    var rows = [];
    rows.push("<table class=\"fnd-ebi-table\"><thead><tr><th>File</th><th>Kind</th><th>Records</th></tr></thead><tbody>");
    files.forEach(function (f) {
      if (!f || typeof f !== "object") return;
      rows.push(
        "<tr><td><code>" +
          esc(text(f.relative_path || f.file_name || "")) +
          "</code></td><td>" +
          esc(text(f.content_kind || "")) +
          "</td><td>" +
          esc(String(f.record_count != null ? f.record_count : "")) +
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

  var fndEbiMediationProvider = {
    defaultMode: function () {
      return "overview";
    },
    modes: function () {
      return [
        { id: "overview", label: "Overview" },
        { id: "traffic", label: "Traffic" },
        { id: "events", label: "Events" },
        { id: "errors_noise", label: "Errors / Noise" },
        { id: "files", label: "Files" }
      ];
    },
    title: function (tool) {
      return text(tool && (tool.label || tool.tool_id)) || "FND EBI";
    },
    kicker: function (tool) {
      return text(toolContribution(tool).label) || "Hosted site analytics";
    },
    meta: function (tool) {
      var ctx = toolContext(tool.tool_id) || {};
      var n = Array.isArray(ctx.analytics_snapshots) ? ctx.analytics_snapshots.length : 0;
      return "Domains: " + String(n) + " · source: analytics/nginx + analytics/events";
    },
    ensureReady: function (tool, force) {
      return ensureToolContext(tool, force).then(function (ctx) {
        var snapshots = Array.isArray(ctx.analytics_snapshots) ? ctx.analytics_snapshots : [];
        var bucket = providerStateFor(tool.tool_id);
        if (!text(bucket.selectedDomain) && snapshots.length) {
          bucket.selectedDomain = text(snapshots[0].domain || "").toLowerCase();
        }
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
    bind: function (tool) {
      qsa("[data-fnd-ebi-select-domain]", els.mediationBody).forEach(function (node) {
        node.addEventListener("click", function () {
          fndEbiSelectDomain(text(node.getAttribute("data-fnd-ebi-select-domain")));
          state.activeMediationMode = "overview";
          renderMediationWorkspaceBody();
        });
      });
    }
  };

  var mediationProviders = {
    agro_erp: agroMediationProvider,
    fnd_ebi: fndEbiMediationProvider
  };

  function bootstrapMediateToolFromQuery() {
    try {
      var params = new URLSearchParams(window.location.search || "");
      var tid = text(params.get("mediate_tool"));
      if (!tid) return Promise.resolve();
      enterToolLayer(tid, "query");
      return api("/portal/api/data/system/sandbox_context", "POST", {
        shell_verb: "mediate",
        current_verb: "mediate",
        shell_surface: "tool_mediation",
        mediation_scope: "system_sandbox",
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
