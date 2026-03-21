(function () {
  "use strict";

  function qs(selector, root) {
    return (root || document).querySelector(selector);
  }

  function qsa(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  function allowedVerb(token) {
    var value = String(token || "").trim().toLowerCase();
    if (value === "navigate" || value === "investigate" || value === "mediate" || value === "manipulate") {
      return value;
    }
    return "";
  }

  var workspace = qs(".system-center-workspace");
  if (!workspace || String(workspace.getAttribute("data-system-tab") || "").trim() !== "workbench") {
    return;
  }

  var compatibilityView = String(workspace.getAttribute("data-system-compat-view") || "").trim();
  if (compatibilityView !== "local_resources" && compatibilityView !== "inheritance") {
    return;
  }

  var selectionSummary = qs("#systemSelectionSummary");
  var sourceScopeSummary = qs("#systemSourceScopeSummary");
  var verbButtons = qsa("[data-shell-verb]");

  var state = {
    compatibilityView: compatibilityView,
    workbenchMode: String(workspace.getAttribute("data-system-workbench-mode") || "resources").trim().toLowerCase() || "resources",
    currentVerb: compatibilityView === "inheritance" ? "investigate" : "manipulate"
  };

  function dispatch(name, detail) {
    try {
      document.dispatchEvent(new CustomEvent(name, { detail: detail || {} }));
    } catch (_) {
      /* no-op */
    }
  }

  function selectionHint() {
    if (state.compatibilityView === "inheritance") {
      return "Select an inherited resource to inspect source provenance, inheritance, and compatible mediations.";
    }
    return "Select a local sandbox resource to inspect provenance, scope, and compatible mediations.";
  }

  function sourceScopeHint() {
    if (state.compatibilityView === "inheritance") {
      return "Inherited-resource provenance and source scope appear here.";
    }
    return "Sandbox file scope and local-index provenance appear here.";
  }

  function setWorkspaceHints() {
    workspace.setAttribute("data-system-empty-selection", selectionHint());
    workspace.setAttribute("data-system-empty-source-scope", sourceScopeHint());
    if (selectionSummary && selectionSummary.classList.contains("ide-contextEmpty")) {
      selectionSummary.textContent = selectionHint();
    }
    if (sourceScopeSummary && !String(sourceScopeSummary.innerHTML || "").trim()) {
      sourceScopeSummary.textContent = sourceScopeHint();
    }
  }

  function setActiveVerbButtons() {
    verbButtons.forEach(function (button) {
      var token = allowedVerb(button.getAttribute("data-shell-verb"));
      button.classList.toggle("is-active", !!token && token === state.currentVerb);
    });
  }

  function setCurrentVerb(verb, options) {
    var opts = options && typeof options === "object" ? options : {};
    var token = allowedVerb(verb) || state.currentVerb || "navigate";
    state.currentVerb = token;
    setActiveVerbButtons();
    if (!opts.silent) {
      dispatch("mycite:shell:verb-changed", {
        verb: state.currentVerb,
        compatibility_view: state.compatibilityView,
      });
    }
    return state.currentVerb;
  }

  function emitWorkbenchMode(detail) {
    var extra = detail && typeof detail === "object" ? detail : {};
    var verb = setCurrentVerb(extra.current_verb || state.currentVerb, { silent: true });
    dispatch(
      "mycite:shell:workbench-mode",
      Object.assign(
        {
          workbench_mode: state.workbenchMode,
          compatibility_view: state.compatibilityView,
          current_verb: verb,
        },
        extra
      )
    );
  }

  function emitWorkbenchPayload(payload, detail) {
    var extra = detail && typeof detail === "object" ? detail : {};
    var verb = setCurrentVerb(extra.current_verb || state.currentVerb, { silent: true });
    dispatch(
      "mycite:shell:workbench-payload",
      Object.assign(
        {
          workbench_mode: state.workbenchMode,
          compatibility_view: state.compatibilityView,
          current_verb: verb,
          payload: payload || {},
        },
        extra
      )
    );
  }

  function emitSelectionInput(detail) {
    var data = detail && typeof detail === "object" ? detail : {};
    var documentPayload = data.document && typeof data.document === "object" ? data.document : null;
    if (!documentPayload) return;
    var verb = setCurrentVerb(data.current_verb || state.currentVerb, { silent: true });
    dispatch("mycite:shell:selection-input", {
      document: documentPayload,
      selected_row: data.selected_row && typeof data.selected_row === "object" ? data.selected_row : null,
      current_verb: verb,
      compatibility_view: state.compatibilityView,
    });
  }

  function bindVerbButtons() {
    verbButtons.forEach(function (button) {
      button.addEventListener("click", function (event) {
        event.preventDefault();
        var verb = allowedVerb(button.getAttribute("data-shell-verb"));
        if (!verb) return;
        setCurrentVerb(verb);
        emitWorkbenchMode();
      });
    });
  }

  window.MyCiteSystemCompatibilityRuntime = {
    compatibilityView: state.compatibilityView,
    currentVerb: function () {
      return state.currentVerb;
    },
    setCurrentVerb: setCurrentVerb,
    emitWorkbenchMode: emitWorkbenchMode,
    emitWorkbenchPayload: emitWorkbenchPayload,
    emitSelectionInput: emitSelectionInput,
  };

  setWorkspaceHints();
  bindVerbButtons();
  setCurrentVerb(state.currentVerb, { silent: true });
  emitWorkbenchMode();
})();
