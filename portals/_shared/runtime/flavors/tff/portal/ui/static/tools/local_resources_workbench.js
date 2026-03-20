/**
 * Local Resources tab: sandbox resource workbench (inventory + editor + SAMRAS sidebar).
 * Source of truth: GET/POST /portal/api/data/sandbox/resources/...
 */
(function () {
  var root = document.getElementById("lrWorkbenchRoot");
  if (!root) return;

  var el = {
    inventoryList: document.getElementById("lrInventoryList"),
    inventorySearch: document.getElementById("lrInventorySearch"),
    statusBar: document.getElementById("lrStatusBar"),
    resourceTitle: document.getElementById("lrResourceTitle"),
    tabWorkspace: document.getElementById("lrTabWorkspace"),
    tabRaw: document.getElementById("lrTabRaw"),
    tabStructured: document.getElementById("lrTabStructured"),
    tabStaged: document.getElementById("lrTabStaged"),
    panelWorkspace: document.getElementById("lrPanelWorkspace"),
    panelRaw: document.getElementById("lrPanelRaw"),
    panelStructured: document.getElementById("lrPanelStructured"),
    panelStaged: document.getElementById("lrPanelStaged"),
    workspaceMount: document.getElementById("lrWorkspaceMount"),
    rawEditor: document.getElementById("lrRawEditor"),
    stagedEditor: document.getElementById("lrStagedEditor"),
    structuredMount: document.getElementById("lrStructuredMount"),
    btnReload: document.getElementById("lrBtnReload"),
    btnSave: document.getElementById("lrBtnSave"),
    btnStage: document.getElementById("lrBtnStage"),
    btnCompile: document.getElementById("lrBtnCompile"),
    badgeStaged: document.getElementById("lrBadgeStaged"),
    sidebarMount: document.getElementById("lrSidebarMount"),
    sidebarTitle: document.getElementById("lrSidebarTitle"),
    resultJson: document.getElementById("sandboxResultJson"),
  };

  var state = {
    selectedId: "",
    lastDetail: null,
    samrasSelectedAddress: "",
    sandboxResources: [],
    localResources: [],
  };

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

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

  function setStatus(msg, isError) {
    if (!el.statusBar) return;
    el.statusBar.textContent = msg || "";
    el.statusBar.className = "lr-workbench__status" + (isError ? " is-error" : "");
  }

  function activateTab(name) {
    var tabs = [el.tabWorkspace, el.tabStructured, el.tabRaw, el.tabStaged];
    var panels = [el.panelWorkspace, el.panelStructured, el.panelRaw, el.panelStaged];
    tabs.forEach(function (t) {
      if (!t) return;
      t.classList.toggle("is-active", t.getAttribute("data-lr-tab") === name);
    });
    panels.forEach(function (p) {
      if (!p) return;
      p.hidden = p.getAttribute("data-lr-panel") !== name;
    });
  }

  if (el.tabWorkspace)
    el.tabWorkspace.addEventListener("click", function () {
      activateTab("workspace");
    });
  if (el.tabRaw)
    el.tabRaw.addEventListener("click", function () {
      activateTab("raw");
    });
  if (el.tabStructured)
    el.tabStructured.addEventListener("click", function () {
      activateTab("structured");
    });
  if (el.tabStaged)
    el.tabStaged.addEventListener("click", function () {
      activateTab("staged");
    });

  function mergedResourceIds() {
    var ids = Object.create(null);
    state.sandboxResources.forEach(function (r) {
      var id = String((r && r.resource_id) || "").trim();
      if (id) ids[id] = { id: id, source: "sandbox", kind: (r && r.kind) || "" };
    });
    state.localResources.forEach(function (r) {
      var id = String((r && r.resource_id) || "").trim();
      if (!id) return;
      if (!ids[id]) ids[id] = { id: id, source: "local_index", kind: (r && r.resource_kind) || "" };
      else ids[id].local_index = true;
    });
    return Object.keys(ids)
      .sort()
      .map(function (k) {
        return ids[k];
      });
  }

  function renderInventoryList() {
    if (!el.inventoryList) return;
    var q = String((el.inventorySearch && el.inventorySearch.value) || "")
      .trim()
      .toLowerCase();
    var items = mergedResourceIds().filter(function (row) {
      if (!q) return true;
      return String(row.id).toLowerCase().indexOf(q) >= 0;
    });
    el.inventoryList.innerHTML = "";
    items.forEach(function (row) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "lr-workbench__inventoryItem";
      if (row.id === state.selectedId) btn.classList.add("is-selected");
      var src = row.source === "local_index" && !row.local_index ? "index" : row.source;
      btn.innerHTML =
        "<span class=\"lr-workbench__inventoryId\">" +
        esc(row.id) +
        "</span>" +
        "<span class=\"lr-workbench__inventoryMeta\">" +
        esc(row.kind || "") +
        " · " +
        esc(src) +
        "</span>";
      btn.addEventListener("click", function () {
        selectResource(row.id);
      });
      el.inventoryList.appendChild(btn);
    });
    if (!items.length) {
      var empty = document.createElement("p");
      empty.className = "data-tool__empty";
      empty.textContent = "No resources found. Refresh or create sandbox/local entries.";
      el.inventoryList.appendChild(empty);
    }
  }

  function renderWorkspace(detail) {
    if (!el.workspaceMount) return;
    el.workspaceMount.innerHTML = "";
    var res = detail && detail.resource && typeof detail.resource === "object" ? detail.resource : {};
    var missing = !!res.missing;
    var wb = detail && detail.workbench && typeof detail.workbench === "object" ? detail.workbench : {};
    var u = wb.understanding && typeof wb.understanding === "object" ? wb.understanding : {};
    var hero = document.createElement("div");
    hero.className = "lr-workbench__workspaceHero";
    var h = document.createElement("h3");
    h.textContent = missing ? "Resource missing in sandbox" : "Resource workspace";
    hero.appendChild(h);
    var meta = document.createElement("div");
    meta.className = "lr-workbench__workspaceMeta";
    var chips = [];
    chips.push(
      '<span class="lr-workbench__workspaceChip">understanding: ' + (u.ok === false ? "issues" : "ok") + "</span>"
    );
    var anthLayers = Array.isArray(wb.anthology_layers) ? wb.anthology_layers : [];
    var anthRows = anthLayers.reduce(function (acc, layer) {
      return acc + (Array.isArray(layer && layer.rows) ? layer.rows.length : 0);
    }, 0);
    var samCount = Array.isArray(wb.samras_row_summaries) ? wb.samras_row_summaries.length : 0;
    chips.push('<span class="lr-workbench__workspaceChip">anthology rows: ' + String(anthRows) + "</span>");
    chips.push('<span class="lr-workbench__workspaceChip">SAMRAS rows: ' + String(samCount) + "</span>");
    if (detail && detail.staged_present) {
      chips.push('<span class="lr-workbench__workspaceChip">staged snapshot present</span>');
    }
    meta.innerHTML = chips.join(" ");
    hero.appendChild(meta);
    el.workspaceMount.appendChild(hero);
    var hint = document.createElement("p");
    hint.className = "data-tool__legendText";
    hint.innerHTML =
      "The <strong>Structured</strong> tab lists layer/value-group and SAMRAS tables. Use <strong>Raw JSON</strong> for full-document edits. Branch/path context for SAMRAS-backed bodies is in the right inspector.";
    el.workspaceMount.appendChild(hint);
    if ((u.warnings || []).length || (u.errors || []).length) {
      var w = document.createElement("div");
      w.className = "lr-workbench__understanding";
      if ((u.warnings || []).length) {
        w.innerHTML += '<div class="lr-workbench__warn">warnings: ' + esc(u.warnings.join("; ")) + "</div>";
      }
      if ((u.errors || []).length) {
        w.innerHTML += '<div class="lr-workbench__err">errors: ' + esc(u.errors.join("; ")) + "</div>";
      }
      el.workspaceMount.appendChild(w);
    }
  }

  function renderStructured(workbench, detail) {
    if (!el.structuredMount) return;
    el.structuredMount.innerHTML = "";
    var wb = workbench && typeof workbench === "object" ? workbench : {};
    var u = wb.understanding && typeof wb.understanding === "object" ? wb.understanding : {};
    var head = document.createElement("div");
    head.className = "lr-workbench__understanding";
    head.innerHTML =
      "<strong>Understanding</strong>: " +
      (u.ok === false ? "issues" : "ok") +
      " · rows " +
      String((wb.anthology_row_summaries || []).length + (wb.samras_row_summaries || []).length);
    if ((u.warnings || []).length)
      head.innerHTML += "<br/><span class=\"lr-workbench__warn\">warnings: " + esc(u.warnings.join("; ")) + "</span>";
    if ((u.errors || []).length)
      head.innerHTML += "<br/><span class=\"lr-workbench__err\">errors: " + esc(u.errors.join("; ")) + "</span>";
    el.structuredMount.appendChild(head);

    var anth = Array.isArray(wb.anthology_layers) ? wb.anthology_layers : [];
    if (anth.length) {
      var h2 = document.createElement("h3");
      h2.className = "lr-workbench__subhead";
      h2.textContent = "Anthology-compatible rows (layer / value group)";
      el.structuredMount.appendChild(h2);
      anth.forEach(function (layer) {
        var det = document.createElement("details");
        det.className = "lr-workbench__layer";
        det.open = true;
        var sum = document.createElement("summary");
        sum.textContent =
          "Layer " +
          String(layer.layer == null ? "?" : layer.layer) +
          " · VG " +
          String(layer.value_group == null ? "?" : layer.value_group) +
          " (" +
          String(layer.row_count || 0) +
          ")";
        det.appendChild(sum);
        var tbl = document.createElement("table");
        tbl.className = "data-tool__table data-tool__table--compact lr-workbench__table";
        tbl.innerHTML =
          "<thead><tr><th>ID</th><th>Label</th><th>Ref</th><th>Rule / lens</th></tr></thead><tbody></tbody>";
        var tb = tbl.querySelector("tbody");
        (layer.rows || []).forEach(function (r) {
          var tr = document.createElement("tr");
          var pol =
            (r.rule_family ? "family:" + r.rule_family : "") +
            (r.lens_id ? " lens:" + r.lens_id : "");
          tr.innerHTML =
            "<td><code>" +
            esc(r.identifier) +
            "</code></td><td>" +
            esc(r.label) +
            "</td><td><code>" +
            esc(r.reference) +
            "</code></td><td>" +
            esc(pol) +
            "</td>";
          tb.appendChild(tr);
        });
        det.appendChild(tbl);
        el.structuredMount.appendChild(det);
      });
    }

    var sam = Array.isArray(wb.samras_row_summaries) ? wb.samras_row_summaries : [];
    if (sam.length) {
      var h3 = document.createElement("h3");
      h3.className = "lr-workbench__subhead";
      h3.textContent = "SAMRAS rows (rows_by_address)";
      el.structuredMount.appendChild(h3);
      var tbl2 = document.createElement("table");
      tbl2.className = "data-tool__table data-tool__table--compact lr-workbench__table";
      tbl2.innerHTML = "<thead><tr><th>Address</th><th>Title</th><th></th></tr></thead><tbody></tbody>";
      var tb2 = tbl2.querySelector("tbody");
      sam.forEach(function (r) {
        var tr = document.createElement("tr");
        if (String(r.address_id) === state.samrasSelectedAddress) tr.classList.add("is-selected");
        var td0 = document.createElement("td");
        td0.innerHTML = "<code>" + esc(r.address_id) + "</code>";
        var td1 = document.createElement("td");
        td1.textContent = r.title || "";
        var td2 = document.createElement("td");
        var b = document.createElement("button");
        b.type = "button";
        b.className = "lr-workbench__miniBtn";
        b.textContent = "Select";
        b.addEventListener("click", function () {
          state.samrasSelectedAddress = String(r.address_id || "").trim();
          refreshSamrasSidebar();
        });
        td2.appendChild(b);
        tr.appendChild(td0);
        tr.appendChild(td1);
        tr.appendChild(td2);
        tb2.appendChild(tr);
      });
      el.structuredMount.appendChild(tbl2);
    }

    if (!anth.length && !sam.length) {
      var p = document.createElement("p");
      p.className = "data-tool__empty";
      p.textContent = "No anthology rows or SAMRAS rows detected in this resource body.";
      el.structuredMount.appendChild(p);
    }
  }

  function renderSamrasSidebar(detail) {
    if (!el.sidebarMount) return;
    el.sidebarMount.innerHTML = "";
    var sw = detail && detail.samras_workspace && typeof detail.samras_workspace === "object" ? detail.samras_workspace : null;
    if (!sw) {
      el.sidebarMount.innerHTML =
        "<p class=\"data-tool__empty\">No SAMRAS workspace view for this resource. Generic resource editing still uses raw JSON.</p>";
      if (el.sidebarTitle) el.sidebarTitle.textContent = "Resource detail";
      return;
    }
    if (el.sidebarTitle) el.sidebarTitle.textContent = "SAMRAS structure";

    var bc = sw.branch_context && typeof sw.branch_context === "object" ? sw.branch_context : {};
    var path = Array.isArray(bc.path_to_root) ? bc.path_to_root : [];
    var sec1 = document.createElement("section");
    sec1.className = "lr-workbench__sidebarSection";
    sec1.innerHTML = "<h4>Path</h4>";
    var ol = document.createElement("div");
    ol.className = "lr-workbench__path";
    path.forEach(function (seg) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "lr-workbench__pathSeg";
      b.textContent = String(seg);
      b.addEventListener("click", function () {
        state.samrasSelectedAddress = String(seg || "").trim();
        refreshSamrasSidebar();
      });
      ol.appendChild(b);
    });
    sec1.appendChild(ol);
    el.sidebarMount.appendChild(sec1);

    var sd = sw.structural_detail && typeof sw.structural_detail === "object" ? sw.structural_detail : {};
    var levels = Array.isArray(sd.levels) ? sd.levels : [];
    levels.forEach(function (lvl) {
      var sec = document.createElement("section");
      sec.className = "lr-workbench__sidebarSection";
      var h = document.createElement("h4");
      h.textContent = String((lvl && lvl.label) || "level");
      sec.appendChild(h);
      (lvl.items || []).forEach(function (it) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "lr-workbench__sidebarBtn";
        var aid = String((it && it.address_id) || "").trim();
        btn.textContent = aid + ((it && it.title) ? " — " + String(it.title) : "");
        btn.addEventListener("click", function () {
          state.samrasSelectedAddress = aid;
          refreshSamrasSidebar();
        });
        sec.appendChild(btn);
      });
      el.sidebarMount.appendChild(sec);
    });

    var nx = document.createElement("p");
    nx.className = "data-tool__legendText";
    nx.innerHTML =
      "<strong>Next child preview:</strong> <code>" + esc(String(bc.next_child_preview || "")) + "</code>";
    el.sidebarMount.appendChild(nx);
  }

  function refreshSamrasSidebar() {
    if (!state.selectedId) return;
    var url = "/portal/api/data/sandbox/samras_workspace/view_model";
    requestJson(url, "POST", {
      resource_id: state.selectedId,
      selected_address_id: state.samrasSelectedAddress,
      staged_entries: [],
    }).then(function (res) {
      if (!res.ok || !res.body || res.body.ok === false) return;
      var vm = Object.assign({}, res.body);
      delete vm.ok;
      if (state.lastDetail) {
        state.lastDetail.samras_workspace = vm;
        renderSamrasSidebar(state.lastDetail);
        if (state.lastDetail.workbench) renderStructured(state.lastDetail.workbench, state.lastDetail);
      }
    });
  }

  function applyDetail(detail) {
    state.lastDetail = detail;
    var res = detail && detail.resource && typeof detail.resource === "object" ? detail.resource : {};
    var missing = !!res.missing;
    if (el.resourceTitle) {
      el.resourceTitle.textContent = missing ? state.selectedId + " (missing)" : state.selectedId;
    }
    if (el.badgeStaged) {
      el.badgeStaged.hidden = !detail.staged_present;
    }
    if (el.rawEditor) {
      el.rawEditor.value = missing ? "{}" : JSON.stringify(res, null, 2);
    }
    if (el.stagedEditor) {
      el.stagedEditor.value = detail.staged_present
        ? JSON.stringify(detail.staged_payload || {}, null, 2)
        : "";
      if (el.tabStaged) el.tabStaged.disabled = !detail.staged_present;
      if (!detail.staged_present && el.tabStaged && el.tabStaged.classList.contains("is-active")) {
        activateTab("workspace");
      }
    }
    renderWorkspace(detail);
    renderStructured(detail.workbench, detail);
    renderSamrasSidebar(detail);
    setStatus(missing ? "Resource not found in sandbox/resources." : "Loaded sandbox resource.", missing);
  }

  function selectResource(id) {
    state.selectedId = String(id || "").trim();
    state.samrasSelectedAddress = "";
    if (!state.selectedId) return;
    setStatus("Loading…");
    requestJson("/portal/api/data/sandbox/resources/" + encodeURIComponent(state.selectedId), "GET").then(function (res) {
      if (!res.ok) {
        setStatus("Failed to load: HTTP " + res.status, true);
        return;
      }
      applyDetail(res.body || {});
      renderInventoryList();
    });
  }

  function refreshLists() {
    setStatus("Refreshing lists…");
    Promise.all([
      requestJson("/portal/api/data/sandbox/resources", "GET"),
      requestJson("/portal/api/data/resources/local", "GET"),
    ]).then(function (results) {
      var s = results[0].body || {};
      var l = results[1].body || {};
      state.sandboxResources = Array.isArray(s.resources) ? s.resources : [];
      state.localResources = Array.isArray(l.resources) ? l.resources : [];
      renderInventoryList();
      setStatus("Inventory refreshed.");
      if (el.resultJson) {
        el.resultJson.textContent = JSON.stringify(
          { sandbox: s, local_index: l },
          null,
          2
        );
      }
      var localPre = document.getElementById("localResourcesJson");
      if (localPre) {
        localPre.textContent = JSON.stringify(l || {}, null, 2);
      }
    });
  }

  if (el.btnReload) el.btnReload.addEventListener("click", refreshLists);

  if (el.btnSave) {
    el.btnSave.addEventListener("click", function () {
      if (!state.selectedId) return;
      var text = String((el.rawEditor && el.rawEditor.value) || "").trim();
      var payload;
      try {
        payload = JSON.parse(text);
      } catch (e) {
        setStatus("Invalid JSON: " + e.message, true);
        return;
      }
      requestJson(
        "/portal/api/data/sandbox/resources/" + encodeURIComponent(state.selectedId) + "/save",
        "POST",
        payload
      ).then(function (res) {
        if (el.resultJson) el.resultJson.textContent = JSON.stringify(res.body || {}, null, 2);
        if (!res.ok) {
          setStatus("Save failed (HTTP " + res.status + ")", true);
          return;
        }
        setStatus("Saved.");
        selectResource(state.selectedId);
      });
    });
  }

  if (el.btnStage) {
    el.btnStage.addEventListener("click", function () {
      if (!state.selectedId) return;
      var text = String((el.rawEditor && el.rawEditor.value) || "").trim();
      var payload;
      try {
        payload = JSON.parse(text);
      } catch (e) {
        setStatus("Invalid JSON: " + e.message, true);
        return;
      }
      requestJson(
        "/portal/api/data/sandbox/resources/" + encodeURIComponent(state.selectedId) + "/stage",
        "POST",
        { payload: payload }
      ).then(function (res) {
        if (el.resultJson) el.resultJson.textContent = JSON.stringify(res.body || {}, null, 2);
        if (!res.ok) {
          setStatus("Stage failed (HTTP " + res.status + ")", true);
          return;
        }
        setStatus("Staged.");
        selectResource(state.selectedId);
      });
    });
  }

  if (el.btnCompile) {
    el.btnCompile.addEventListener("click", function () {
      if (!state.selectedId) return;
      requestJson(
        "/portal/api/data/sandbox/resources/" + encodeURIComponent(state.selectedId) + "/compile",
        "POST",
        {}
      ).then(function (res) {
        if (el.resultJson) el.resultJson.textContent = JSON.stringify(res.body || {}, null, 2);
        if (!res.ok) {
          setStatus("Compile failed (HTTP " + res.status + ")", true);
          return;
        }
        setStatus("Compile requested.");
        selectResource(state.selectedId);
      });
    });
  }

  if (el.inventorySearch) {
    el.inventorySearch.addEventListener("input", function () {
      renderInventoryList();
    });
  }

  /* Advanced panel hooks */
  var localMigrateBtn = document.getElementById("localResourcesMigrateBtn");
  if (localMigrateBtn) {
    localMigrateBtn.addEventListener("click", function () {
      requestJson("/portal/api/data/resources/local/migrate_legacy_samras", "POST", { apply: true }).then(function (result) {
        if (el.resultJson) el.resultJson.textContent = JSON.stringify(result.body || {}, null, 2);
        refreshLists();
      });
    });
  }
  var sandboxRefreshBtn = document.getElementById("sandboxRefreshBtn");
  if (sandboxRefreshBtn) sandboxRefreshBtn.addEventListener("click", refreshLists);
  var compileMssBtn = document.getElementById("sandboxMssCompileBtn");
  if (compileMssBtn) {
    compileMssBtn.addEventListener("click", function () {
      var refs = String((document.getElementById("sandboxMssRefs") || {}).value || "")
        .split(/[\n,]/)
        .map(function (item) {
          return String(item || "").trim();
        })
        .filter(Boolean);
      requestJson("/portal/api/data/sandbox/mss/compile", "POST", {
        resource_id: "system-sandbox-mss",
        selected_refs: refs,
      }).then(function (result) {
        if (el.resultJson) el.resultJson.textContent = JSON.stringify(result.body || {}, null, 2);
        refreshLists();
      });
    });
  }
  var decodeMssBtn = document.getElementById("sandboxMssDecodeBtn");
  if (decodeMssBtn) {
    decodeMssBtn.addEventListener("click", function () {
      var bitstring = String((document.getElementById("sandboxMssBitstring") || {}).value || "").trim();
      requestJson("/portal/api/data/sandbox/mss/decode", "POST", {
        resource_id: "system-sandbox-mss-decode",
        bitstring: bitstring,
      }).then(function (result) {
        if (el.resultJson) el.resultJson.textContent = JSON.stringify(result.body || {}, null, 2);
      });
    });
  }
  var migrateDryBtn = document.getElementById("sandboxMigrateDryRunBtn");
  if (migrateDryBtn) {
    migrateDryBtn.addEventListener("click", function () {
      requestJson("/portal/api/data/sandbox/migrate/fnd_samras", "POST", { apply: false }).then(function (result) {
        if (el.resultJson) el.resultJson.textContent = JSON.stringify(result.body || {}, null, 2);
        refreshLists();
      });
    });
  }

  activateTab("workspace");
  refreshLists();
})();
