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
    centerHint: document.getElementById("inheritanceCenterHint"),
    inspectorEmpty: document.getElementById("inheritanceInspectorEmpty"),
    inspectorDetail: document.getElementById("inheritanceInspectorDetail"),
    rawPre: document.getElementById("inheritanceResourcesJson"),
    statusPre: document.getElementById("inheritanceStatusJson"),
    refreshBtn: document.getElementById("inheritanceRefreshBtn"),
    sourceMsn: document.getElementById("inheritanceSourceMsn"),
    contractId: document.getElementById("inheritanceContractId"),
    resourceId: document.getElementById("inheritanceResourceId"),
    refreshSingle: document.getElementById("inheritanceRefreshSingleBtn"),
    refreshSource: document.getElementById("inheritanceRefreshSourceBtn"),
    disconnect: document.getElementById("inheritanceDisconnectBtn"),
  };

  var state = {
    payload: null,
    selectedSource: "",
    selectedResourceId: "",
  };

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
          syncFormFromSelection();
          renderSources();
          renderResources();
          renderInspector();
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
        ? "Resources — " + state.selectedSource
        : "Select a source";
    }
    if (el.centerHint) {
      el.centerHint.hidden = !!state.selectedSource;
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
        syncFormFromSelection();
        renderResources();
        renderInspector();
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

  function renderInspector() {
    var map = groupedMap();
    var list = Array.isArray(map[state.selectedSource]) ? map[state.selectedSource] : [];
    var picked =
      list.find(function (r) {
        return r && String(r.resource_id || "").trim() === state.selectedResourceId;
      }) || null;
    if (!el.inspectorEmpty || !el.inspectorDetail) return;
    if (!picked) {
      el.inspectorEmpty.hidden = false;
      el.inspectorDetail.hidden = true;
      el.inspectorDetail.innerHTML = "";
      return;
    }
    el.inspectorEmpty.hidden = true;
    el.inspectorDetail.hidden = false;
    var lines = [
      "<p><strong>resource_id</strong><br/><code>" + esc(String(picked.resource_id || "")) + "</code></p>",
      "<p><strong>resource_name</strong><br/>" + esc(String(picked.resource_name || "")) + "</p>",
      "<p><strong>source_msn_id</strong><br/><code>" + esc(String(picked.source_msn_id || state.selectedSource || "")) + "</code></p>",
    ];
    if (picked.contract_id) {
      lines.push("<p><strong>contract_id</strong><br/><code>" + esc(String(picked.contract_id)) + "</code></p>");
    }
    if (picked.cache_path) {
      lines.push(
        '<details class="data-tool__advanced"><summary>Advanced: cache path</summary><p><code>' +
          esc(String(picked.cache_path)) +
          "</code></p></details>"
      );
    }
    el.inspectorDetail.innerHTML = '<div class="inh-workbench__detail">' + lines.join("") + "</div>";
  }

  function syncFormFromSelection() {
    if (el.sourceMsn && state.selectedSource) el.sourceMsn.value = state.selectedSource;
    if (el.resourceId && state.selectedResourceId) el.resourceId.value = state.selectedResourceId;
  }

  function inheritanceInputs() {
    return {
      source_msn_id: String((el.sourceMsn && el.sourceMsn.value) || "").trim(),
      contract_id: String((el.contractId && el.contractId.value) || "").trim(),
      resource_id: String((el.resourceId && el.resourceId.value) || "").trim(),
    };
  }

  function setInheritanceStatus(body) {
    if (el.statusPre) el.statusPre.textContent = JSON.stringify(body || {}, null, 2);
    refreshPayload();
  }

  function refreshPayload() {
    requestJson("/portal/api/data/resources/inherited", "GET").then(function (result) {
      state.payload = result.body || {};
      if (el.rawPre) el.rawPre.textContent = JSON.stringify(state.payload || {}, null, 2);
      if (!state.selectedSource) {
        var keys = Object.keys(groupedMap());
        if (keys.length === 1) state.selectedSource = keys[0];
      }
      renderSources();
      renderResources();
      renderInspector();
    });
  }

  if (el.refreshBtn) el.refreshBtn.addEventListener("click", refreshPayload);
  if (el.sourceFilter) el.sourceFilter.addEventListener("input", renderSources);

  if (el.refreshSingle) {
    el.refreshSingle.addEventListener("click", function () {
      requestJson("/portal/api/data/resources/inherited/refresh", "POST", inheritanceInputs()).then(function (result) {
        setInheritanceStatus(result.body || {});
      });
    });
  }
  if (el.refreshSource) {
    el.refreshSource.addEventListener("click", function () {
      requestJson("/portal/api/data/resources/inherited/refresh_source", "POST", inheritanceInputs()).then(function (result) {
        setInheritanceStatus(result.body || {});
      });
    });
  }
  if (el.disconnect) {
    el.disconnect.addEventListener("click", function () {
      requestJson("/portal/api/data/resources/inherited/disconnect_source", "POST", inheritanceInputs()).then(function (result) {
        setInheritanceStatus(result.body || {});
      });
    });
  }

  refreshPayload();
})();
