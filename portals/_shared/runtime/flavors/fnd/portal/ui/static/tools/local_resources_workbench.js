/**
 * Local Resources: file-backed sandbox resource editor (sandbox/resources/*.json).
 * SAMRAS-backed bodies use the shared samras_workspace view-model (TXA, MSN, …).
 */
(function () {
  var root = document.getElementById("lrWorkbenchRoot");
  if (!root) return;

  /* Same sessionStorage namespace as data_tool.js (TXA_STAGED_STORAGE_PREFIX) for cross-tab parity */
  var SAMRAS_STAGED_PREFIX = "mycite.data_tool.txa_staged.v1:";

  var el = {
    inventoryList: document.getElementById("lrInventoryList"),
    inventorySearch: document.getElementById("lrInventorySearch"),
    statusBar: document.getElementById("lrStatusBar"),
    resourceTitle: document.getElementById("lrResourceTitle"),
    canonicalPath: document.getElementById("lrCanonicalPath"),
    kindChip: document.getElementById("lrKindChip"),
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
    btnPromoteSamras: document.getElementById("lrBtnPromoteSamras"),
    btnClearSamrasStaged: document.getElementById("lrBtnClearSamrasStaged"),
    samrasActionRow: document.getElementById("lrSamrasActionRow"),
    badgeStaged: document.getElementById("lrBadgeStaged"),
    sidebarMount: document.getElementById("lrSidebarMount"),
    sidebarTitle: document.getElementById("lrSidebarTitle"),
    inspectorKicker: document.getElementById("lrInspectorKicker"),
    resultJson: document.getElementById("sandboxResultJson"),
  };

  var state = {
    selectedId: "",
    lastDetail: null,
    samrasSelectedAddress: "",
    sandboxResources: [],
    localResources: [],
  };

  function compatibilityRuntime() {
    var runtime = window.MyCiteSystemCompatibilityRuntime;
    return runtime && typeof runtime === "object" ? runtime : null;
  }

  function activeTabName() {
    var tabs = [el.tabWorkspace, el.tabStructured, el.tabRaw, el.tabStaged];
    for (var i = 0; i < tabs.length; i++) {
      var tab = tabs[i];
      if (tab && tab.classList.contains("is-active")) {
        return String(tab.getAttribute("data-lr-tab") || "").trim();
      }
    }
    return "workspace";
  }

  function localCompatibilityVerb() {
    var activeTab = activeTabName();
    if (activeTab === "structured") return "investigate";
    return "manipulate";
  }

  function selectedRowForDetail(detail) {
    var token = String(state.samrasSelectedAddress || "").trim();
    if (!token) return null;
    var vm = detail && detail.samras_workspace && typeof detail.samras_workspace === "object" ? detail.samras_workspace : {};
    var candidates = []
      .concat(Array.isArray(vm.title_table_rows) ? vm.title_table_rows : [])
      .concat(Array.isArray(vm.children) ? vm.children : [])
      .concat(Array.isArray(vm.siblings) ? vm.siblings : [])
      .concat(Array.isArray(vm.samras_row_summaries) ? vm.samras_row_summaries : []);
    var picked = null;
    for (var i = 0; i < candidates.length; i++) {
      var row = candidates[i];
      if (row && String(row.address_id || "").trim() === token) {
        picked = row;
        break;
      }
    }
    return {
      identifier: token,
      label: String((picked && (picked.title || picked.label)) || token).trim(),
      file_key: "txa",
      source: "samras_workspace",
      address_id: token,
      reference: String((picked && picked.reference) || "").trim(),
    };
  }

  function emitCompatibilityWorkbenchMode() {
    var runtime = compatibilityRuntime();
    if (!runtime || typeof runtime.emitWorkbenchMode !== "function") return;
    runtime.setCurrentVerb(localCompatibilityVerb(), { silent: true });
    runtime.emitWorkbenchMode({
      current_verb: localCompatibilityVerb(),
    });
  }

  function emitCompatibilityWorkbenchPayload(payload) {
    var runtime = compatibilityRuntime();
    if (!runtime || typeof runtime.emitWorkbenchPayload !== "function") return;
    runtime.setCurrentVerb(localCompatibilityVerb(), { silent: true });
    runtime.emitWorkbenchPayload(payload || {}, {
      current_verb: localCompatibilityVerb(),
    });
  }

  function emitSelectionContext(detail) {
    var body = detail && typeof detail === "object" ? detail : state.lastDetail;
    var documentPayload = body && body.document && typeof body.document === "object" ? body.document : null;
    if (!documentPayload) return;
    var runtime = compatibilityRuntime();
    if (!runtime || typeof runtime.emitSelectionInput !== "function") return;
    runtime.setCurrentVerb(localCompatibilityVerb(), { silent: true });
    runtime.emitSelectionInput({
      document: documentPayload,
      selected_row: selectedRowForDetail(body),
      current_verb: localCompatibilityVerb(),
    });
  }

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
    emitCompatibilityWorkbenchMode();
    var runtime = compatibilityRuntime();
    if (runtime && typeof runtime.setCurrentVerb === "function") {
      runtime.setCurrentVerb(localCompatibilityVerb());
    }
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

  function preferredAutoSelectRow(rows) {
    var firstSandbox = null;
    for (var i = 0; i < rows.length; i++) {
      if (rows[i] && rows[i].source === "sandbox") {
        firstSandbox = rows[i];
        break;
      }
    }
    return firstSandbox || rows[0] || null;
  }

  function sandboxFileRelPath(resourceId) {
    var token = String(resourceId || "").trim().replace(/\//g, "_");
    return "sandbox/resources/" + token + ".json";
  }

  function samrasStagedKey(rid) {
    return SAMRAS_STAGED_PREFIX + String(rid || "").trim();
  }

  function loadSamrasStaged(rid) {
    try {
      var raw = window.sessionStorage.getItem(samrasStagedKey(rid));
      if (!raw) return [];
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function saveSamrasStaged(rid, entries) {
    try {
      window.sessionStorage.setItem(samrasStagedKey(rid), JSON.stringify(entries || []));
    } catch (e) {
      /* ignore */
    }
  }

  function workbenchVm(detail) {
    return detail && detail.workbench && typeof detail.workbench === "object" ? detail.workbench : {};
  }

  function isSamrasBacked(detail) {
    var wb = workbenchVm(detail);
    if (wb.is_samras_backed) return true;
    return !!(detail && detail.samras_workspace);
  }

  function setSamrasActionRowVisible(on) {
    if (el.samrasActionRow) el.samrasActionRow.hidden = !on;
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
      var srcLabel = src === "sandbox" ? "sandbox file" : src === "local_index" ? "local index" : src;
      btn.innerHTML =
        '<span class="lr-workbench__inventoryId">' +
        esc(row.id) +
        '</span><span class="lr-workbench__inventoryMeta">' +
        esc(row.kind || "kind ?") +
        " · " +
        esc(srcLabel) +
        "</span>";
      btn.addEventListener("click", function () {
        selectResource(row.id);
      });
      el.inventoryList.appendChild(btn);
    });
    if (!items.length) {
      var empty = document.createElement("p");
      empty.className = "data-tool__empty";
      empty.textContent = "No resources in sandbox or local index.";
      el.inventoryList.appendChild(empty);
    }
  }

  function renderFileIdentity(detail) {
    var res = detail && detail.resource && typeof detail.resource === "object" ? detail.resource : {};
    var missing = !!res.missing;
    var wb = workbenchVm(detail);
    var kind = String(wb.resource_kind || res.kind || res.resource_kind || "").trim();

    if (el.resourceTitle) {
      el.resourceTitle.textContent = state.selectedId
        ? state.selectedId + (missing ? " (missing in sandbox)" : "")
        : "Select a resource file";
    }
    if (el.canonicalPath) {
      if (state.selectedId) {
        el.canonicalPath.textContent = sandboxFileRelPath(state.selectedId);
        el.canonicalPath.hidden = false;
      } else {
        el.canonicalPath.textContent = "";
        el.canonicalPath.hidden = true;
      }
    }
    if (el.kindChip) {
      el.kindChip.textContent = kind || "—";
      el.kindChip.hidden = !state.selectedId;
    }
    return { missing: missing, kind: kind, wb: wb };
  }

  function renderNonSamrasSummary(detail, idInfo) {
    if (!el.workspaceMount || idInfo.missing) return;
    var wb = idInfo.wb;
    var u = wb.understanding && typeof wb.understanding === "object" ? wb.understanding : {};
    var row = document.createElement("div");
    row.className = "lr-workbench__fileSummary";
    var anthLayers = Array.isArray(wb.anthology_layers) ? wb.anthology_layers : [];
    var anthRows = anthLayers.reduce(function (acc, layer) {
      return acc + (Array.isArray(layer && layer.rows) ? layer.rows.length : 0);
    }, 0);
    var parts = [];
    parts.push("Anthology-shaped rows: " + String(anthRows));
    parts.push("understanding: " + (u.ok === false ? "issues" : "ok"));
    if (detail && detail.staged_present) parts.push("staging file present");
    row.textContent = parts.join(" · ");
    el.workspaceMount.appendChild(row);
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

  function renderSamrasTitleTable(mount, rows, onPick) {
    var wrap = document.createElement("div");
    wrap.className = "lr-workbench__samrasTableWrap data-tool__tableWrap";
    var tbl = document.createElement("table");
    tbl.className = "data-tool__table data-tool__table--compact";
    tbl.innerHTML =
      "<thead><tr><th>Status</th><th>Address</th><th>Title</th><th>Parent</th></tr></thead><tbody></tbody>";
    var tb = tbl.querySelector("tbody");
    var list = Array.isArray(rows) ? rows : [];
    var sel = String(state.samrasSelectedAddress || "").trim();
    list.forEach(function (row) {
      var aid = String(row.address_id || "").trim();
      var tr = document.createElement("tr");
      if (aid && aid === sel) tr.classList.add("is-selected");
      var st = String(row.status || "").trim();
      var badge =
        st === "staged"
          ? '<span class="data-tool__badge data-tool__badge--staged">staged</span>'
          : '<span class="data-tool__badge data-tool__badge--saved">saved</span>';
      tr.innerHTML =
        "<td>" +
        badge +
        "</td><td><code>" +
        esc(aid) +
        "</code></td><td>" +
        esc(row.title || "") +
        "</td><td><code>" +
        esc(row.parent_address || "") +
        "</code></td>";
      tr.addEventListener("click", function () {
        state.samrasSelectedAddress = aid;
        if (typeof onPick === "function") onPick();
      });
      tb.appendChild(tr);
    });
    if (!list.length) {
      var tr0 = document.createElement("tr");
      tr0.innerHTML = '<td colspan="4"><p class="data-tool__empty">No SAMRAS title rows decoded.</p></td>';
      tb.appendChild(tr0);
    }
    wrap.appendChild(tbl);
    mount.appendChild(wrap);
  }

  function renderSamrasMiniGraph(mount, branch) {
    var box = document.createElement("div");
    box.className = "data-tool__txaMiniGraph lr-workbench__samrasMiniGraph";
    var path = Array.isArray(branch && branch.path_to_root) ? branch.path_to_root : [];
    if (!path.length) {
      var empty = document.createElement("p");
      empty.className = "data-tool__empty";
      empty.textContent = "Select a row to see the path from root.";
      box.appendChild(empty);
      mount.appendChild(box);
      return;
    }
    var chip = document.createElement("div");
    chip.className = "data-tool__txaPathChip";
    var sel = String(state.samrasSelectedAddress || "").trim();
    path.forEach(function (seg, idx) {
      var token = String(seg || "").trim();
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "data-tool__txaPathSeg";
      if (token === sel) btn.classList.add("is-selected");
      btn.textContent = token;
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        state.samrasSelectedAddress = token;
        refreshSamrasWorkspace();
      });
      chip.appendChild(btn);
      if (idx < path.length - 1) {
        var sep = document.createElement("span");
        sep.textContent = " › ";
        sep.setAttribute("aria-hidden", "true");
        chip.appendChild(sep);
      }
    });
    box.appendChild(chip);
    var chWrap = document.createElement("div");
    chWrap.className = "data-tool__txaMiniChildren";
    var chHead = document.createElement("div");
    chHead.innerHTML = "<strong>Direct children</strong>";
    chWrap.appendChild(chHead);
    var kids = Array.isArray(branch && branch.children) ? branch.children : [];
    if (!kids.length) {
      var none = document.createElement("p");
      none.className = "data-tool__empty";
      none.textContent = "No children under this node.";
      chWrap.appendChild(none);
    } else {
      kids.forEach(function (c) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "data-tool__txaBranchItem";
        b.textContent = String(c.address_id || "") + (c.title ? " — " + String(c.title) : "");
        b.addEventListener("click", function () {
          state.samrasSelectedAddress = String(c.address_id || "").trim();
          refreshSamrasWorkspace();
        });
        chWrap.appendChild(b);
      });
    }
    box.appendChild(chWrap);
    mount.appendChild(box);
  }

  function renderStructuralBurst(mount, payload) {
    var detail = payload && typeof payload.structural_detail === "object" ? payload.structural_detail : null;
    if (!detail) {
      var p = document.createElement("p");
      p.className = "data-tool__empty";
      p.textContent = "No structural detail.";
      mount.appendChild(p);
      return;
    }
    var wrap = document.createElement("div");
    wrap.className = "data-tool__samrasBurstColumns";
    var levels = Array.isArray(detail.levels) ? detail.levels : [];
    levels.forEach(function (lvl) {
      var col = document.createElement("div");
      col.className = "data-tool__samrasBurstCol";
      var h = document.createElement("div");
      h.className = "data-tool__samrasBurstColTitle";
      h.textContent = String((lvl && lvl.label) || (lvl && lvl.key) || "level");
      col.appendChild(h);
      var items = Array.isArray(lvl && lvl.items) ? lvl.items : [];
      if (!items.length) {
        var empty = document.createElement("p");
        empty.className = "data-tool__empty";
        empty.textContent = "—";
        col.appendChild(empty);
      } else {
        items.forEach(function (it) {
          var row = document.createElement("button");
          row.type = "button";
          row.className = "data-tool__samrasBurstRow";
          var aid = String((it && it.address_id) || "").trim();
          var title = String((it && it.title) || "").trim();
          row.textContent = aid + (title ? " — " + title : "");
          row.addEventListener("click", function () {
            if (!aid) return;
            state.samrasSelectedAddress = aid;
            refreshSamrasWorkspace();
          });
          col.appendChild(row);
        });
      }
      wrap.appendChild(col);
    });
    var staged = Array.isArray(detail.staged_structural_preview) ? detail.staged_structural_preview : [];
    if (staged.length) {
      var st = document.createElement("div");
      st.className = "data-tool__samrasBurstStaged";
      var head = document.createElement("div");
      head.className = "data-tool__samrasBurstColTitle";
      head.textContent = "Staged structural preview";
      st.appendChild(head);
      staged.forEach(function (s) {
        var p = document.createElement("p");
        p.className = "data-tool__legendText";
        p.textContent =
          String((s && s.provisional_child_address) || "") +
          " under " +
          String((s && s.parent_address) || "") +
          ": " +
          String((s && s.title) || "");
        st.appendChild(p);
      });
      wrap.appendChild(st);
    }
    mount.appendChild(wrap);
  }

  function renderSamrasInspector(vm) {
    if (!el.sidebarMount) return;
    el.sidebarMount.innerHTML = "";
    if (el.inspectorKicker) el.inspectorKicker.textContent = "SAMRAS";
    if (el.sidebarTitle) el.sidebarTitle.textContent = "Branch & structure";

    var branch = vm && vm.branch_context && typeof vm.branch_context === "object" ? vm.branch_context : {};
    var sel = String(state.samrasSelectedAddress || "").trim();

    var pathSec = document.createElement("section");
    pathSec.className = "lr-workbench__sidebarSection";
    pathSec.innerHTML = "<h4>Path to root</h4>";
    var pathStack = document.createElement("div");
    pathStack.className = "data-tool__txaBranchPathStack";
    var segs = Array.isArray(branch.path_to_root) ? branch.path_to_root : [];
    if (!segs.length) {
      pathStack.innerHTML = '<p class="data-tool__empty">No selection.</p>';
    } else {
      segs.forEach(function (seg, idx) {
        var token = String(seg || "").trim();
        var row = document.createElement("div");
        row.className = "data-tool__txaBranchPathRow";
        var depth = document.createElement("span");
        depth.className = "data-tool__txaBranchPathDepth";
        depth.textContent = String(idx + 1);
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "data-tool__txaInspectorPathSeg";
        if (token && token === sel) btn.classList.add("is-selected");
        btn.textContent = token || "(segment)";
        btn.addEventListener("click", function () {
          state.samrasSelectedAddress = token;
          refreshSamrasWorkspace();
        });
        row.appendChild(depth);
        row.appendChild(btn);
        pathStack.appendChild(row);
      });
    }
    pathSec.appendChild(pathStack);
    el.sidebarMount.appendChild(pathSec);

    function listSection(title, items, pickKey) {
      var sec = document.createElement("section");
      sec.className = "lr-workbench__sidebarSection";
      var h = document.createElement("h4");
      h.textContent = title;
      sec.appendChild(h);
      var box = document.createElement("div");
      box.className = "data-tool__txaBranchList";
      (items || []).forEach(function (item) {
        var addr = String(item.address_id || "").trim();
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "data-tool__txaBranchItem" + (item.is_selected ? " is-selected" : "");
        btn.textContent = addr + (item.title ? " — " + String(item.title) : "");
        btn.addEventListener("click", function () {
          state.samrasSelectedAddress = addr;
          refreshSamrasWorkspace();
        });
        box.appendChild(btn);
      });
      if (!items || !items.length) {
        var p = document.createElement("p");
        p.className = "data-tool__empty";
        p.textContent = "None.";
        box.appendChild(p);
      }
      sec.appendChild(box);
      el.sidebarMount.appendChild(sec);
    }

    listSection("Siblings", Array.isArray(branch.siblings) ? branch.siblings : []);
    listSection(
      "Children",
      (Array.isArray(branch.children) ? branch.children : []).map(function (c) {
        return { address_id: c.address_id, title: c.title };
      })
    );

    var nextSec = document.createElement("section");
    nextSec.className = "lr-workbench__sidebarSection";
    nextSec.innerHTML = "<h4>Next child slot</h4>";
    var next = String((branch && branch.next_child_preview) || "").trim();
    nextSec.innerHTML += next
      ? "<p>Next free child under <code>" +
        esc(sel) +
        "</code>:</p><p><code>" +
        esc(next) +
        "</code></p>"
      : '<p class="data-tool__empty">Select a node to preview the next child address.</p>';
    el.sidebarMount.appendChild(nextSec);

    var burstSec = document.createElement("section");
    burstSec.className = "lr-workbench__sidebarSection";
    burstSec.innerHTML = "<h4>Structural detail</h4>";
    renderStructuralBurst(burstSec, vm);
    el.sidebarMount.appendChild(burstSec);
  }

  function renderGenericInspector(detail) {
    if (!el.sidebarMount) return;
    if (el.inspectorKicker) el.inspectorKicker.textContent = "Resource";
    if (el.sidebarTitle) el.sidebarTitle.textContent = "File notes";
    el.sidebarMount.innerHTML = "";
    var res = detail && detail.resource && typeof detail.resource === "object" ? detail.resource : {};
    var missing = !!res.missing;
    var p = document.createElement("div");
    p.className = "lr-workbench__sidebarSection";
    p.innerHTML =
      "<p class=\"data-tool__legendText\">" +
      (missing
        ? "This id is listed in the local index but no sandbox JSON file exists yet. Use <strong>Raw JSON</strong> + <strong>Save</strong> to create <code>" +
          esc(sandboxFileRelPath(state.selectedId)) +
          "</code>."
        : "SAMRAS branch tools appear when the saved JSON body is SAMRAS-backed (title tree / rows_by_address).") +
      "</p>";
    el.sidebarMount.appendChild(p);
  }

  function renderSamrasCenter(vm) {
    if (!el.workspaceMount) return;
    var stageRow = document.createElement("div");
    stageRow.className = "data-tool__controlRow data-tool__controlRow--wrap lr-workbench__samrasStageRow";
    var label = document.createElement("label");
    label.className = "data-tool__growLabel";
    label.innerHTML = "<span>New title (next child)</span>";
    var input = document.createElement("input");
    input.type = "text";
    input.id = "lrSamrasNewTitle";
    input.placeholder = "e.g. cultivar_slug";
    label.appendChild(input);
    var stageBtn = document.createElement("button");
    stageBtn.type = "button";
    stageBtn.textContent = "Stage as next child";
    stageBtn.addEventListener("click", function () {
      var title = String(input.value || "").trim();
      var parent = String(state.samrasSelectedAddress || "").trim();
      if (!state.selectedId || !title || !parent) {
        setStatus("Select a parent node and enter a title.", true);
        return;
      }
      var staged = loadSamrasStaged(state.selectedId);
      staged.push({ parent_address: parent, title: title });
      saveSamrasStaged(state.selectedId, staged);
      input.value = "";
      refreshSamrasWorkspace();
    });
    stageRow.appendChild(label);
    stageRow.appendChild(stageBtn);
    el.workspaceMount.appendChild(stageRow);

    var hint = document.createElement("p");
    hint.className = "data-tool__statusInline";
    var n = (vm.normalized_staged_entries || []).length;
    hint.textContent = n
      ? n + " staged row(s) in this browser session — Promote to persist into the sandbox JSON file."
      : "Session staging only — use Promote to write through the shared sandbox engine.";
    el.workspaceMount.appendChild(hint);

    renderSamrasTitleTable(el.workspaceMount, vm.title_table_rows || [], function () {
      refreshSamrasWorkspace();
    });
    renderSamrasMiniGraph(el.workspaceMount, vm.branch_context || {});
  }

  function applySamrasVmPayload(payload) {
    if (!state.lastDetail) return;
    var vm = Object.assign({}, payload || {});
    delete vm.ok;
    state.lastDetail.samras_workspace = vm;
    if (!state.samrasSelectedAddress && Array.isArray(vm.title_table_rows) && vm.title_table_rows.length) {
      state.samrasSelectedAddress = String(vm.title_table_rows[0].address_id || "").trim();
      return true;
    }
    return false;
  }

  function refreshSamrasWorkspace() {
    if (!state.selectedId || !isSamrasBacked(state.lastDetail)) return;
    var body = {
      resource_id: state.selectedId,
      selected_address_id: state.samrasSelectedAddress,
      staged_entries: loadSamrasStaged(state.selectedId),
    };
    return requestJson("/portal/api/data/sandbox/samras_workspace/view_model", "POST", body).then(function (res) {
      if (!res.ok || !res.body || res.body.ok === false) {
        setStatus("SAMRAS workspace failed to load.", true);
        return;
      }
      var needsRefetch = applySamrasVmPayload(res.body);
      var vm = state.lastDetail.samras_workspace || {};
      if (needsRefetch) {
        body.selected_address_id = state.samrasSelectedAddress;
        return requestJson("/portal/api/data/sandbox/samras_workspace/view_model", "POST", body).then(function (res2) {
          if (res2.ok && res2.body && res2.body.ok !== false) applySamrasVmPayload(res2.body);
          paintSamrasSurfaces();
          emitSelectionContext(state.lastDetail);
        });
      }
      paintSamrasSurfaces();
      emitSelectionContext(state.lastDetail);
    });
  }

  function paintSamrasSurfaces() {
    var vm = state.lastDetail && state.lastDetail.samras_workspace;
    if (!el.workspaceMount || !vm) return;
    /* Rebuild workspace body below file card */
    var card = el.workspaceMount.querySelector(".lr-workbench__fileCard");
    el.workspaceMount.innerHTML = "";
    if (card) el.workspaceMount.appendChild(card);
    renderSamrasCenter(vm);
    renderSamrasInspector(vm);
    var sw = Array.isArray(vm.stage_warnings) ? vm.stage_warnings : [];
    if (sw.length) {
      setStatus("Staging warnings: " + sw.length, true);
    }
  }

  function renderWorkspaceSurface(detail) {
    if (!el.workspaceMount) return;
    el.workspaceMount.innerHTML = "";
    var idInfo = renderFileIdentity(detail);

    var card = document.createElement("div");
    card.className = "lr-workbench__fileCard";
    if (state.selectedId) {
      var h = document.createElement("h3");
      h.className = "lr-workbench__fileCardTitle";
      h.textContent = "Sandbox JSON file";
      card.appendChild(h);
      var pathLine = document.createElement("p");
      pathLine.className = "lr-workbench__filePath";
      pathLine.innerHTML =
        "Editing <code>" + esc(sandboxFileRelPath(state.selectedId)) + "</code>" + (idInfo.missing ? " (not on disk yet)" : "");
      card.appendChild(pathLine);
      var chips = document.createElement("div");
      chips.className = "lr-workbench__fileChips";
      chips.innerHTML =
        '<span class="lr-workbench__workspaceChip">kind: ' +
        esc(idInfo.kind || "—") +
        "</span>" +
        (detail && detail.staged_present
          ? '<span class="lr-workbench__workspaceChip">staging snapshot on disk</span>'
          : "");
      card.appendChild(chips);
    } else {
      var empty = document.createElement("p");
      empty.className = "data-tool__empty";
      empty.textContent = "Choose a resource from the list — each entry maps to a JSON file in sandbox/resources (or the local index).";
      card.appendChild(empty);
    }
    el.workspaceMount.appendChild(card);

    setSamrasActionRowVisible(!!state.selectedId && isSamrasBacked(detail) && !idInfo.missing);

    if (!state.selectedId || idInfo.missing) {
      renderGenericInspector(detail);
      return;
    }

    if (isSamrasBacked(detail)) {
      refreshSamrasWorkspace().catch(function () {
        setStatus("SAMRAS workspace request failed.", true);
      });
    } else {
      renderNonSamrasSummary(detail, idInfo);
      renderGenericInspector(detail);
    }
  }

  function renderStructured(workbench, detail) {
    if (!el.structuredMount) return;
    el.structuredMount.innerHTML = "";
    var wb = workbench && typeof workbench === "object" ? workbench : {};
    var u = wb.understanding && typeof wb.understanding === "object" ? wb.understanding : {};
    if ((u.warnings || []).length || (u.errors || []).length || u.ok === false) {
      var head = document.createElement("div");
      head.className = "lr-workbench__understanding";
      head.innerHTML =
        "<strong>Understanding</strong>: " +
        (u.ok === false ? "issues" : "ok") +
        ((u.warnings || []).length ? "<br/><span class=\"lr-workbench__warn\">warnings: " + esc(u.warnings.join("; ")) + "</span>" : "") +
        ((u.errors || []).length ? "<br/><span class=\"lr-workbench__err\">errors: " + esc(u.errors.join("; ")) + "</span>" : "");
      el.structuredMount.appendChild(head);
    }

    var anth = Array.isArray(wb.anthology_layers) ? wb.anthology_layers : [];
    if (anth.length) {
      var h2 = document.createElement("h3");
      h2.className = "lr-workbench__subhead";
      h2.textContent = "Anthology-compatible rows";
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
      tbl2.innerHTML = "<thead><tr><th>Address</th><th>Title</th></tr></thead><tbody></tbody>";
      var tb2 = tbl2.querySelector("tbody");
      sam.forEach(function (r) {
        var tr = document.createElement("tr");
        if (String(r.address_id) === state.samrasSelectedAddress) tr.classList.add("is-selected");
        tr.innerHTML =
          "<td><code>" +
          esc(r.address_id) +
          "</code></td><td>" +
          esc(r.title) +
          "</td>";
        tr.addEventListener("click", function () {
          state.samrasSelectedAddress = String(r.address_id || "").trim();
          refreshSamrasWorkspace();
        });
        tb2.appendChild(tr);
      });
      el.structuredMount.appendChild(tbl2);
    }

    if (!anth.length && !sam.length && !((u.warnings || []).length || (u.errors || []).length)) {
      var p = document.createElement("p");
      p.className = "data-tool__empty";
      p.textContent = "No structured rows detected.";
      el.structuredMount.appendChild(p);
    }
  }

  function applyDetail(detail) {
    state.lastDetail = detail;
    var res = detail && detail.resource && typeof detail.resource === "object" ? detail.resource : {};
    var missing = !!res.missing;
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
    renderWorkspaceSurface(detail);
    renderStructured(detail.workbench, detail);
    setStatus(missing ? "No sandbox file yet — use Raw JSON + Save to create it." : "Loaded.", missing);
    emitCompatibilityWorkbenchMode();
    emitSelectionContext(detail);
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
    emitCompatibilityWorkbenchMode();
    Promise.all([
      requestJson("/portal/api/data/sandbox/resources", "GET"),
      requestJson("/portal/api/data/resources/local", "GET"),
    ]).then(function (results) {
      var s = results[0].body || {};
      var l = results[1].body || {};
      state.sandboxResources = Array.isArray(s.resources) ? s.resources : [];
      state.localResources = Array.isArray(l.resources) ? l.resources : [];
      var rows = mergedResourceIds();
      var preferred = preferredAutoSelectRow(rows);
      if (!state.selectedId && preferred && preferred.id) {
        selectResource(preferred.id);
      } else {
        renderInventoryList();
        setStatus("Lists ready.");
      }
      if (el.resultJson) {
        el.resultJson.textContent = JSON.stringify({ sandbox: s, local_index: l }, null, 2);
      }
      emitCompatibilityWorkbenchPayload({ sandbox: s, local_index: l });
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
        setStatus("Saved to " + sandboxFileRelPath(state.selectedId) + ".");
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
        setStatus("Staged snapshot written.");
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

  if (el.btnPromoteSamras) {
    el.btnPromoteSamras.addEventListener("click", function () {
      if (!state.selectedId) return;
      var staged = loadSamrasStaged(state.selectedId);
      if (!staged.length) {
        setStatus("No session-staged SAMRAS titles to promote.", true);
        return;
      }
      requestJson(
        "/portal/api/data/sandbox/resources/" + encodeURIComponent(state.selectedId) + "/promote_staged_samras_titles",
        "POST",
        { staged_entries: staged }
      ).then(function (res) {
        if (el.resultJson) el.resultJson.textContent = JSON.stringify(res.body || {}, null, 2);
        if (!res.ok) {
          setStatus("Promote failed (HTTP " + res.status + ")", true);
          return;
        }
        saveSamrasStaged(state.selectedId, []);
        setStatus("Promoted staged titles into sandbox JSON.");
        selectResource(state.selectedId);
      });
    });
  }

  if (el.btnClearSamrasStaged) {
    el.btnClearSamrasStaged.addEventListener("click", function () {
      if (!state.selectedId) return;
      saveSamrasStaged(state.selectedId, []);
      setStatus("Cleared session SAMRAS staging.");
      if (isSamrasBacked(state.lastDetail)) refreshSamrasWorkspace();
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
  emitCompatibilityWorkbenchMode();
  refreshLists();
})();
