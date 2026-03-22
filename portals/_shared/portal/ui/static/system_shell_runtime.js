(function () {
  "use strict";

  function qs(selector, root) {
    return (root || document).querySelector(selector);
  }

  function qsa(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
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

  var systemWorkspace = qs(".system-center-workspace");
  if (!systemWorkspace || String(systemWorkspace.getAttribute("data-system-tab") || "").trim() !== "workbench") {
    return;
  }

  var els = {
    selectionSummary: qs("#systemSelectionSummary"),
    sourceScopeSummary: qs("#systemSourceScopeSummary"),
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
    agroOpenBtn: qs("#systemAgroOpenBtn"),
    mediationCloseBtn: qs("#systemMediationCloseBtn")
  };

  var state = {
    selectedContext: null,
    lastSelectionInput: null,
    agroConfigContext: null,
    activeVerb: "navigate",
    workbenchMode: String(systemWorkspace.getAttribute("data-system-workbench-mode") || "anthology").trim().toLowerCase() || "anthology",
    activeToolId: "",
    activeMediationMode: "overview",
    agroModel: null,
    agroSessionId: "",
    agroLastPreview: null,
    agroLastApply: null,
    agroReadback: null
  };

  function selectionHint() {
    return String(systemWorkspace.getAttribute("data-system-empty-selection") || "").trim() || "Select a resource datum to activate the canonical shell.";
  }

  function sourceScopeHint() {
    return String(systemWorkspace.getAttribute("data-system-empty-source-scope") || "").trim() || "Source and scope details appear here.";
  }

  function setActiveVerbButtons() {
    qsa("[data-shell-verb]").forEach(function (btn) {
      var token = String(btn.getAttribute("data-shell-verb") || "").trim();
      btn.classList.toggle("is-active", token === state.activeVerb);
    });
  }

  function renderSelectionSummary() {
    if (!els.selectionSummary) return;
    var ctx = state.selectedContext;
    if (!ctx || !ctx.selection) {
      els.selectionSummary.className = "ide-contextEmpty";
      els.selectionSummary.textContent = selectionHint();
      if (els.resourcesInspectorEmpty) els.resourcesInspectorEmpty.hidden = false;
      if (els.sourceScopeSummary) {
        els.sourceScopeSummary.textContent = sourceScopeHint();
      }
      return;
    }
    var selection = ctx.selection || {};
    var family = ctx.family || {};
    var scope = ctx.scope || {};
    var resolved = ctx.resolved_archetype || {};
    els.selectionSummary.className = "data-tool__resourcesDatumCard";
    if (els.resourcesInspectorEmpty) els.resourcesInspectorEmpty.hidden = true;
    els.selectionSummary.innerHTML =
      "<div><strong>Selected</strong><br/><code>" + esc(selection.selected_ref_or_document_id || "") + "</code></div>" +
      "<div><strong>Label</strong><br/><span>" + esc(selection.display_name || "") + "</span></div>" +
      "<div><strong>Archetype</strong><br/><span>" + esc(resolved.family || family.kind || "datum") + "</span></div>";
    if (els.sourceScopeSummary) {
      els.sourceScopeSummary.innerHTML =
        "<strong>Source</strong> " + esc(((ctx.provenance || {}).source_adapter) || "unknown") +
        " · <strong>Scope</strong> " + esc(scope.kind || "unknown") +
        " · <strong>Family</strong> " + esc(family.type || family.kind || "resource");
    }
  }

  function renderCompatibleTools() {
    if (!els.compatibleTools) return;
    els.compatibleTools.innerHTML = "";
    var tools = [];
    if (state.selectedContext && Array.isArray(state.selectedContext.compatible_tools)) {
      tools = state.selectedContext.compatible_tools.slice();
    }
    if ((!tools.length) && state.agroConfigContext && Array.isArray(state.agroConfigContext.compatible_tools)) {
      tools = state.agroConfigContext.compatible_tools.slice();
    }
    if (!tools.length) {
      els.compatibleTools.innerHTML = '<div class="ide-contextEmpty">No compatible mediations for the current context.</div>';
      return;
    }
    var list = document.createElement("div");
    list.className = "ide-contextList";
    tools.forEach(function (tool) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "ide-contextLink" + (String(tool.tool_id || "") === state.activeToolId ? " is-active" : "");
      button.setAttribute("data-shell-tool-id", String(tool.tool_id || ""));
      var contribution = tool.workbench_contribution && typeof tool.workbench_contribution === "object" ? tool.workbench_contribution : {};
      button.innerHTML =
        "<span>" + esc(tool.label || tool.tool_id || "tool") + "</span>" +
        "<small>" + esc(contribution.label || contribution.workspace_id || "mediation workspace") + "</small>";
      button.addEventListener("click", function () {
        openTool(String(tool.tool_id || "").trim());
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
    if (state.agroConfigContext && Array.isArray(state.agroConfigContext.inspector_cards)) {
      cards = cards.concat(state.agroConfigContext.inspector_cards);
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

  function renderMediationModes() {
    if (!els.mediationModes) return;
    els.mediationModes.innerHTML = "";
    var modes = [
      ["overview", "Overview"],
      ["taxonomy", "Taxonomy browse/select"],
      ["supplier", "Supplier browse/select"],
      ["product", "Product profile compose"],
      ["invoice", "Supply log compose"],
      ["preview", "Preview/apply"]
    ];
    modes.forEach(function (entry) {
      var id = entry[0];
      var label = entry[1];
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "data-tool__actionBtn" + (state.activeMediationMode === id ? " is-active" : "");
      btn.textContent = label;
      btn.addEventListener("click", function () {
        state.activeMediationMode = id;
        renderMediationWorkspaceBody();
        renderMediationModes();
      });
      els.mediationModes.appendChild(btn);
    });
  }

  function renderTaxonomyTree(node, depth) {
    if (!node || typeof node !== "object" || depth > 4) {
      return "";
    }
    var label = String(node.label || node.identifier || node.title || "").trim();
    var identifier = String(node.identifier || "").trim();
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

  function renderAgroOverview() {
    var ctx = state.agroConfigContext || {};
    return (
      "<p><strong>Binding truth:</strong> " + esc(ctx.binding_truth || "config") + "</p>" +
      "<p><strong>Browse truth:</strong> " + esc(ctx.browse_truth || "inherited_resources") + "</p>" +
      "<p><strong>Staging truth:</strong> " + esc(ctx.staging_truth || "sandbox_reduced") + "</p>" +
      "<p><strong>Commit truth:</strong> " + esc(ctx.commit_truth || "anthology_semantic_minimum") + "</p>" +
      '<pre class="jsonblock">' + esc(JSON.stringify(ctx.resource_role_bindings || {}, null, 2)) + "</pre>"
    );
  }

  function renderAgroTaxonomy() {
    var model = state.agroModel || {};
    var taxonomy = model.taxonomy && typeof model.taxonomy === "object" ? model.taxonomy : {};
    var tree = taxonomy.tree && typeof taxonomy.tree === "object" ? taxonomy.tree : {};
    var treeHtml = renderTaxonomyTree(tree, 0);
    return (
      "<p><strong>Ref:</strong> <code>" + esc(taxonomy.ref || "") + "</code></p>" +
      "<p><strong>Scope:</strong> " + esc(taxonomy.scope || "unknown") + "</p>" +
      (treeHtml ? "<ul class=\"data-tool__pathList\">" + treeHtml + "</ul>" : '<p class="data-tool__empty">No taxonomy tree is currently resolvable.</p>')
    );
  }

  function renderAgroSupplierBrowse() {
    var ctx = state.agroConfigContext || {};
    var roles = ctx.resource_role_bindings && typeof ctx.resource_role_bindings === "object" ? ctx.resource_role_bindings : {};
    return (
      "<p>This mode uses inherited resources directly for browse/lookup where available and falls back to local bindings only when necessary.</p>" +
      '<pre class="jsonblock">' + esc(JSON.stringify(roles, null, 2)) + "</pre>"
    );
  }

  function renderAgroCompose(kind) {
    var label = kind === "product" ? "Product profile" : "Supply log";
    var previewKey = kind === "product" ? "product_profile" : "supply_log";
    var actionButtons =
      '<div class="data-tool__controlRow data-tool__controlRow--wrap">' +
      '<button type="button" data-agro-action="preview" data-agro-kind="' + esc(kind) + '">Preview</button>' +
      '<button type="button" data-agro-action="apply" data-agro-kind="' + esc(kind) + '">Apply</button>' +
      "</div>";
    var previewState = state.agroLastPreview && state.agroLastPreview.kind === previewKey ? state.agroLastPreview.payload : {};
    var applyState = state.agroLastApply && state.agroLastApply.kind === previewKey ? state.agroLastApply.payload : {};
    return (
      "<p><strong>" + esc(label) + "</strong> uses reduced staging semantics. Inherited resources remain browse truth, and only minimal refs are committed.</p>" +
      actionButtons +
      '<details class="data-tool__advanced" open><summary>Latest preview</summary><pre class="jsonblock">' + esc(JSON.stringify(previewState || {}, null, 2)) + "</pre></details>" +
      '<details class="data-tool__advanced"><summary>Latest apply</summary><pre class="jsonblock">' + esc(JSON.stringify(applyState || {}, null, 2)) + "</pre></details>"
    );
  }

  function renderAgroPreviewSummary() {
    return (
      '<details class="data-tool__advanced" open><summary>Readback</summary><pre class="jsonblock">' +
      esc(JSON.stringify(state.agroReadback || {}, null, 2)) +
      "</pre></details>"
    );
  }

  function bindAgroActions() {
    qsa("[data-agro-action]", els.mediationBody).forEach(function (btn) {
      btn.addEventListener("click", function () {
        var kind = String(btn.getAttribute("data-agro-kind") || "").trim();
        var action = String(btn.getAttribute("data-agro-action") || "").trim();
        if (!kind || !action) return;
        runAgroAction(kind, action).catch(function (err) {
          if (els.mediationMeta) {
            els.mediationMeta.textContent = err && err.message ? err.message : "AGRO ERP action failed.";
          }
        });
      });
    });
  }

  function renderMediationWorkspaceBody() {
    if (!els.mediationBody || !els.mediationWorkbench) return;
    if (state.activeToolId !== "agro_erp") {
      els.mediationWorkbench.hidden = true;
      if (els.mediationCloseBtn) els.mediationCloseBtn.hidden = true;
      return;
    }
    els.mediationWorkbench.hidden = false;
    if (els.mediationCloseBtn) els.mediationCloseBtn.hidden = false;
    if (els.mediationTitle) els.mediationTitle.textContent = "AGRO ERP";
    if (els.mediationKicker) els.mediationKicker.textContent = "Canonical mediation workspace";
    if (els.mediationMeta) {
      var activation = state.agroConfigContext && state.agroConfigContext.activation && typeof state.agroConfigContext.activation === "object"
        ? state.agroConfigContext.activation
        : {};
      els.mediationMeta.textContent =
        "Session: " + (state.agroSessionId || "(not opened)") +
        " · can_open=" + String(!!activation.can_open);
    }
    renderMediationModes();
    if (state.activeMediationMode === "taxonomy") {
      els.mediationBody.innerHTML = renderAgroTaxonomy();
    } else if (state.activeMediationMode === "supplier") {
      els.mediationBody.innerHTML = renderAgroSupplierBrowse();
    } else if (state.activeMediationMode === "product") {
      els.mediationBody.innerHTML = renderAgroCompose("product");
    } else if (state.activeMediationMode === "invoice") {
      els.mediationBody.innerHTML = renderAgroCompose("invoice");
    } else if (state.activeMediationMode === "preview") {
      els.mediationBody.innerHTML = renderAgroPreviewSummary();
    } else {
      els.mediationBody.innerHTML = renderAgroOverview();
    }
    bindAgroActions();
  }

  function renderAll() {
    setActiveVerbButtons();
    renderSelectionSummary();
    renderCompatibleTools();
    renderInspectorCards();
    renderMediationWorkspaceBody();
  }

  function ensureAgroConfigContext(force) {
    if (state.agroConfigContext && !force) {
      return Promise.resolve(state.agroConfigContext);
    }
    return api("/portal/api/data/system/config_context/agro_erp").then(function (payload) {
      state.agroConfigContext = payload || {};
      renderAll();
      return state.agroConfigContext;
    });
  }

  function ensureAgroModel(force) {
    if (state.agroModel && !force) {
      return Promise.resolve(state.agroModel);
    }
    return api("/portal/tools/agro_erp/model.json").then(function (payload) {
      state.agroModel = payload || {};
      return state.agroModel;
    });
  }

  function ensureAgroSession(force) {
    return ensureAgroConfigContext(force).then(function (configContext) {
      var activation = configContext && configContext.activation && typeof configContext.activation === "object" ? configContext.activation : {};
      var requestPayload = activation.request_payload && typeof activation.request_payload === "object" ? activation.request_payload : {};
      if (!activation.can_open || !Object.keys(requestPayload).length) {
        return { ok: false, error: "AGRO ERP has no resolved browse source in config-context." };
      }
      if (state.agroSessionId && !force) {
        return { ok: true, sandbox_session_id: state.agroSessionId };
      }
      return api("/portal/tools/agro_erp/mvp/resource/select_or_load", "POST", requestPayload).then(function (payload) {
        state.agroSessionId = String((payload && payload.sandbox_session_id) || "").trim();
        state.agroReadback = payload || {};
        return payload || {};
      });
    });
  }

  function runAgroAction(kind, action) {
    var endpoint;
    var previewKey = kind === "product" ? "product_profile" : "supply_log";
    if (kind === "product") {
      endpoint = action === "preview" ? "/portal/tools/agro_erp/mvp/product/preview" : "/portal/tools/agro_erp/mvp/product/apply";
    } else {
      endpoint = action === "preview" ? "/portal/tools/agro_erp/mvp/invoice/preview" : "/portal/tools/agro_erp/mvp/invoice/apply";
    }
    return ensureAgroSession(false).then(function (sessionPayload) {
      if (!sessionPayload || sessionPayload.ok === false) {
        throw new Error((sessionPayload && sessionPayload.error) || "AGRO ERP session is unavailable.");
      }
      var body = { sandbox_session_id: state.agroSessionId };
      return api(endpoint, "POST", body).then(function (payload) {
        if (action === "preview") {
          state.agroLastPreview = { kind: previewKey, payload: payload || {} };
        } else {
          state.agroLastApply = { kind: previewKey, payload: payload || {} };
          return api("/portal/tools/agro_erp/mvp/workflow/readback?resource_ref=" + encodeURIComponent("session:" + state.agroSessionId)).catch(function () {
            return {};
          }).then(function (readback) {
            state.agroReadback = readback || {};
            return payload;
          });
        }
        return payload;
      }).then(function (payload) {
        renderAll();
        return payload;
      });
    });
  }

  function openTool(toolId) {
    var token = String(toolId || "").trim().toLowerCase();
    if (!token) return;
    state.activeToolId = token;
    state.activeMediationMode = "overview";
    if (token === "agro_erp") {
      Promise.all([ensureAgroConfigContext(false), ensureAgroModel(false)]).then(function () {
        return ensureAgroSession(false);
      }).catch(function (err) {
        if (els.mediationMeta) {
          els.mediationMeta.textContent = err && err.message ? err.message : "AGRO ERP could not open.";
        }
      }).finally(function () {
        renderAll();
      });
      return;
    }
    renderAll();
  }

  document.addEventListener("mycite:shell:selection-input", function (event) {
    var detail = event && event.detail && typeof event.detail === "object" ? event.detail : {};
    var documentPayload = detail.document && typeof detail.document === "object" ? detail.document : null;
    if (!documentPayload) return;
    state.lastSelectionInput = {
      document: documentPayload,
      selected_row: detail.selected_row && typeof detail.selected_row === "object" ? detail.selected_row : null
    };
    state.activeVerb = String(detail.current_verb || state.activeVerb || "navigate").trim() || "navigate";
    api("/portal/api/data/system/selection_context", "POST", {
      document: documentPayload,
      selected_row: detail.selected_row && typeof detail.selected_row === "object" ? detail.selected_row : null,
      current_verb: state.activeVerb
    }).then(function (payload) {
      state.selectedContext = payload || {};
      renderAll();
    }).catch(function (err) {
      if (els.sourceScopeSummary) {
        els.sourceScopeSummary.textContent = err && err.message ? err.message : "Selection context failed to load.";
      }
    });
  });

  document.addEventListener("mycite:shell:verb-changed", function (event) {
    var detail = event && event.detail && typeof event.detail === "object" ? event.detail : {};
    state.activeVerb = String(detail.verb || state.activeVerb || "navigate").trim() || "navigate";
    if (state.lastSelectionInput && state.lastSelectionInput.document) {
      document.dispatchEvent(new CustomEvent("mycite:shell:selection-input", {
        detail: {
          document: state.lastSelectionInput.document,
          selected_row: state.lastSelectionInput.selected_row,
          current_verb: state.activeVerb
        }
      }));
    } else {
      renderAll();
    }
  });

  document.addEventListener("mycite:shell:workbench-mode", function (event) {
    var detail = event && event.detail && typeof event.detail === "object" ? event.detail : {};
    var mode = String(detail.workbench_mode || "").trim().toLowerCase();
    if (mode) {
      state.workbenchMode = mode;
    }
    var verb = String(detail.current_verb || "").trim().toLowerCase();
    if (verb) {
      state.activeVerb = verb;
    }
    renderAll();
  });

  document.addEventListener("mycite:shell:workbench-payload", function (event) {
    var detail = event && event.detail && typeof event.detail === "object" ? event.detail : {};
    var mode = String(detail.workbench_mode || "").trim().toLowerCase();
    if (mode) {
      state.workbenchMode = mode;
    }
    renderAll();
  });

  if (els.agroOpenBtn) {
    els.agroOpenBtn.addEventListener("click", function () {
      openTool("agro_erp");
    });
  }

  if (els.mediationCloseBtn) {
    els.mediationCloseBtn.addEventListener("click", function () {
      state.activeToolId = "";
      renderAll();
    });
  }

  ensureAgroConfigContext(false).catch(function () {
    return null;
  }).finally(function () {
    renderAll();
  });
})();
