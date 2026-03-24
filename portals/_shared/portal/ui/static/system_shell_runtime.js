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
    var prefix = text(tool && tool.route_prefix);
    if (prefix) return prefix;
    var homePath = text(tool && tool.home_path);
    if (homePath && /\/home$/.test(homePath)) {
      return homePath.replace(/\/home$/, "");
    }
    var toolId = text(tool && tool.tool_id);
    return toolId ? ("/portal/tools/" + toolId) : "";
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
    mediationCloseBtn: qs("#systemMediationCloseBtn")
  };

  var state = {
    selectedContext: null,
    lastSelectionInput: null,
    activeVerb: "navigate",
    activeToolId: "",
    activeMediationMode: "",
    toolContexts: {},
    providerState: {}
  };

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
    var attentionAddress = text(systemState.attention_address || "");
    var directive = text(systemState.directive || state.activeVerb || "navigate");
    els.selectionSummary.className = "data-tool__resourcesDatumCard";
    if (els.resourcesInspectorEmpty) els.resourcesInspectorEmpty.hidden = true;
    els.selectionSummary.innerHTML =
      "<div><strong>Attention</strong><br/><code>" + esc(attentionAddress || selection.selected_ref_or_document_id || "") + "</code></div>" +
      "<div><strong>Label</strong><br/><span>" + esc(selection.display_name || "") + "</span></div>" +
      "<div><strong>Directive</strong><br/><span>" + esc(directive || "navigate") + "</span></div>" +
      "<div><strong>Archetype</strong><br/><span>" + esc(resolved.family || family.kind || "datum") + "</span></div>";
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
    els.mediationBody.innerHTML = provider.render(tool, state.activeMediationMode);
    if (typeof provider.bind === "function") {
      provider.bind(tool);
    }
  }

  function renderAll() {
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
      return bucket.model;
    });
  }

  function ensureAgroSession(tool, force) {
    var bucket = agroState(tool);
    return ensureToolContext(tool, force).then(function (configContext) {
      var activation = configContext && typeof configContext.activation === "object" ? configContext.activation : {};
      var requestPayload = activation.request_payload && typeof activation.request_payload === "object" ? activation.request_payload : {};
      if (!activation.can_open || !Object.keys(requestPayload).length) {
        bucket.lastError = "AGRO ERP has no resolved browse source in config-context.";
        return { ok: false, error: bucket.lastError };
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
      return agroModeId(toolContribution(tool).default_mode || "overview") || "overview";
    },
    modes: function () {
      return [
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
    }
  };

  var mediationProviders = {
    agro_erp: agroMediationProvider
  };

  document.addEventListener("mycite:shell:selection-input", function (event) {
    var detail = event && event.detail && typeof event.detail === "object" ? event.detail : {};
    var documentPayload = detail.document && typeof detail.document === "object" ? detail.document : null;
    if (!documentPayload) return;
    state.lastSelectionInput = {
      document: documentPayload,
      selected_row: detail.selected_row && typeof detail.selected_row === "object" ? detail.selected_row : null
    };
    state.activeVerb = text(detail.current_verb || state.activeVerb || "navigate") || "navigate";
    api("/portal/api/data/system/selection_context", "POST", {
      document: documentPayload,
      selected_row: detail.selected_row && typeof detail.selected_row === "object" ? detail.selected_row : null,
      current_verb: state.activeVerb
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
    state.activeVerb = text(detail.verb || state.activeVerb || "navigate") || "navigate";
    if (state.lastSelectionInput && state.lastSelectionInput.document) {
      emitShellEvent("mycite:shell:selection-input", {
        document: state.lastSelectionInput.document,
        selected_row: state.lastSelectionInput.selected_row,
        current_verb: state.activeVerb
      });
    } else {
      renderAll();
    }
  });

  document.addEventListener("mycite:shell:workbench-payload", function () {
    renderAll();
  });

  document.addEventListener("mycite:shell:file-focus-changed", function () {
    state.activeToolId = "";
    state.activeMediationMode = "";
    renderAll();
  });

  if (els.mediationCloseBtn) {
    els.mediationCloseBtn.addEventListener("click", function () {
      state.activeToolId = "";
      state.activeMediationMode = "";
      renderAll();
    });
  }

  renderAll();
})();
