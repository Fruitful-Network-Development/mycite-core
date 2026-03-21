/**
 * System → Inheritance: grouped-by-source manager (uses grouped_by_source from API).
 */
(function () {
  var root = document.getElementById("inhWorkbenchRoot");
  if (!root) return;

  function requestJson(url, method, payload) {
    return fetch(url, {
      method: method || "GET",
      headers: payload ? { "Content-Type": "application/json" } : undefined,
      body: payload ? JSON.stringify(payload) : undefined,
    }).then(function (resp) {
      return resp
        .json()
        .catch(function () {
          return {};
        })
        .then(function (body) {
          return { ok: resp.ok, status: resp.status, body: body || {} };
        });
    });
  }

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  var el = {
    sourceList: document.getElementById("inheritanceSourceList"),
    sourceFilter: document.getElementById("inheritanceSourceFilter"),
    resourceList: document.getElementById("inheritanceResourceList"),
    centerTitle: document.getElementById("inheritanceCenterTitle"),
    detailMount: document.getElementById("inheritanceCompatibilityDetailMount"),
    rawPre: document.getElementById("inheritanceResourcesJson"),
    refreshBtn: document.getElementById("inheritanceRefreshBtn"),
  };

  var state = {
    payload: null,
    selectedSource: "",
    selectedResourceId: "",
    lastActionStatus: {},
  };

  function compatibilityRuntime() {
    var runtime = window.MyCiteSystemCompatibilityRuntime;
    return runtime && typeof runtime === "object" ? runtime : null;
  }

  function compatibilityViews() {
    var views = window.MyCiteSystemCompatibilityViews;
    return views && typeof views === "object" ? views : null;
  }

  function inheritanceCompatibilityVerb() {
    return "investigate";
  }

  function documentsList() {
    var docs = state.payload && state.payload.documents;
    return Array.isArray(docs) ? docs : [];
  }

  function documentForSelection(picked) {
    if (!picked || typeof picked !== "object") return null;
    var rid = String(picked.resource_id || "").trim();
    var source = String(picked.source_msn_id || state.selectedSource || "").trim();
    var docs = documentsList();
    for (var i = 0; i < docs.length; i++) {
      var doc = docs[i];
      if (!doc || typeof doc !== "object") continue;
      var identity = doc.identity && typeof doc.identity === "object" ? doc.identity : {};
      var provenance = doc.provenance && typeof doc.provenance === "object" ? doc.provenance : {};
      var logicalKey = String(identity.logical_key || "").trim();
      var sourceRid = String(provenance.source_resource_id || "").trim();
      var sourceMsn = String(provenance.source_msn_id || "").trim();
      if ((logicalKey === rid || sourceRid === rid) && (!source || !sourceMsn || sourceMsn === source)) {
        return doc;
      }
    }
    return null;
  }

  function emitCompatibilityWorkbenchMode() {
    var runtime = compatibilityRuntime();
    if (!runtime || typeof runtime.emitWorkbenchMode !== "function") return;
    runtime.setCurrentVerb(inheritanceCompatibilityVerb(), { silent: true });
    runtime.emitWorkbenchMode({
      current_verb: inheritanceCompatibilityVerb(),
    });
  }

  function emitCompatibilityWorkbenchPayload(payload) {
    var runtime = compatibilityRuntime();
    if (!runtime || typeof runtime.emitWorkbenchPayload !== "function") return;
    runtime.setCurrentVerb(inheritanceCompatibilityVerb(), { silent: true });
    runtime.emitWorkbenchPayload(payload || {}, {
      current_verb: inheritanceCompatibilityVerb(),
    });
  }

  function emitSelectionContext(picked) {
    var documentPayload = documentForSelection(picked);
    if (!documentPayload) return;
    var runtime = compatibilityRuntime();
    if (!runtime || typeof runtime.emitSelectionInput !== "function") return;
    runtime.setCurrentVerb(inheritanceCompatibilityVerb(), { silent: true });
    runtime.emitSelectionInput({
      document: documentPayload,
      selected_row: {
        identifier: String((picked && picked.resource_id) || "").trim(),
        label: String((picked && (picked.resource_name || picked.resource_id)) || "").trim(),
        source: "inherited_resource",
      },
      current_verb: inheritanceCompatibilityVerb(),
    });
  }

  function groupedMap() {
    var g = state.payload && state.payload.grouped_by_source;
    return g && typeof g === "object" ? g : {};
  }

  function renderSources() {
    if (!el.sourceList) return;
    var q = String((el.sourceFilter && el.sourceFilter.value) || "")
      .trim()
      .toLowerCase();
    var map = groupedMap();
    var keys = Object.keys(map).sort();
    el.sourceList.innerHTML = "";
    keys
      .filter(function (k) {
        return !q || String(k).toLowerCase().indexOf(q) >= 0;
      })
      .forEach(function (src) {
        var items = Array.isArray(map[src]) ? map[src] : [];
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "inh-workbench__item";
        if (src === state.selectedSource) btn.classList.add("is-selected");
        btn.innerHTML =
          "<strong>" +
          esc(src) +
          "</strong>" +
          '<span class="inh-workbench__itemMeta">' +
          String(items.length) +
          " resource(s)</span>";
        btn.addEventListener("click", function () {
          state.selectedSource = src;
          state.selectedResourceId = "";
          emitCompatibilityWorkbenchMode();
          renderSources();
          renderResources();
          renderCompatibilityDetail();
        });
        el.sourceList.appendChild(btn);
      });
    if (!keys.length) {
      var p = document.createElement("p");
      p.className = "data-tool__empty";
      p.textContent = "No inherited resources in index.";
      el.sourceList.appendChild(p);
    }
  }

  function renderResources() {
    if (!el.resourceList) return;
    var map = groupedMap();
    var list = Array.isArray(map[state.selectedSource]) ? map[state.selectedSource] : [];
    if (el.centerTitle) {
      el.centerTitle.textContent = state.selectedSource
        ? "Inherited resources — " + state.selectedSource
        : "Select a source";
    }
    el.resourceList.innerHTML = "";
    list.forEach(function (row) {
      if (!row || typeof row !== "object") return;
      var rid = String(row.resource_id || row.resource_name || "").trim();
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "inh-workbench__item";
      if (rid && rid === state.selectedResourceId) btn.classList.add("is-selected");
      var name = String(row.resource_name || row.resource_id || "").trim();
      btn.innerHTML =
        "<strong>" +
        esc(name || rid || "(resource)") +
        "</strong>" +
        '<span class="inh-workbench__itemMeta"><code>' +
        esc(rid) +
        "</code></span>";
      btn.addEventListener("click", function () {
        state.selectedResourceId = rid;
        emitCompatibilityWorkbenchMode();
        renderResources();
        renderCompatibilityDetail();
      });
      el.resourceList.appendChild(btn);
    });
    if (state.selectedSource && !list.length) {
      var empty = document.createElement("p");
      empty.className = "data-tool__empty";
      empty.textContent = "No resources for this source.";
      el.resourceList.appendChild(empty);
    }
  }

  function selectedResource() {
    var map = groupedMap();
    var list = Array.isArray(map[state.selectedSource]) ? map[state.selectedSource] : [];
    return (
      list.find(function (r) {
        return r && String(r.resource_id || "").trim() === state.selectedResourceId;
      }) || null
    );
  }

  function renderCompatibilityDetail() {
    var helper = compatibilityViews();
    var picked = selectedResource();
    if (helper && typeof helper.renderInheritanceDetail === "function") {
      helper.renderInheritanceDetail({
        mount: el.detailMount,
        resource: picked,
        selectedSource: state.selectedSource,
        status: state.lastActionStatus,
        requestJson: requestJson,
        afterAction: function (body) {
          state.lastActionStatus = body || {};
          return refreshPayload();
        },
      });
    } else if (el.detailMount) {
      el.detailMount.innerHTML = '<p class="data-tool__empty">Select an inherited resource.</p>';
    }
    if (picked) {
      emitCompatibilityWorkbenchMode();
      emitSelectionContext(picked);
    }
  }

  function refreshPayload() {
    emitCompatibilityWorkbenchMode();
    return requestJson("/portal/api/data/resources/inherited", "GET").then(function (result) {
      state.payload = result.body || {};
      if (el.rawPre) el.rawPre.textContent = JSON.stringify(state.payload || {}, null, 2);
      emitCompatibilityWorkbenchPayload(state.payload);
      if (!state.selectedSource) {
        var keys = Object.keys(groupedMap());
        if (keys.length === 1) state.selectedSource = keys[0];
      }
      renderSources();
      renderResources();
      renderCompatibilityDetail();
      return state.payload;
    });
  }

  if (el.refreshBtn) el.refreshBtn.addEventListener("click", refreshPayload);
  if (el.sourceFilter) el.sourceFilter.addEventListener("input", renderSources);

  emitCompatibilityWorkbenchMode();
  refreshPayload();
})();
