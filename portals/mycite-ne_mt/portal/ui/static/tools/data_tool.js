(function () {
  function qs(selector, root) { return (root || document).querySelector(selector); }
  function qsa(selector, root) { return Array.prototype.slice.call((root || document).querySelectorAll(selector)); }

  var app = qs("#dataToolApp");
  if (!app) return;
  var activeDataTab = String(app.getAttribute("data-active-tab") || "anthology").trim().toLowerCase();

  var sourceSel = qs("#dtSource", app);
  var subjectInput = qs("#dtSubject", app);
  var invMethodSel = qs("#dtInvMethod", app);
  var modeSel = qs("#dtMode", app);
  var lensSel = qs("#dtLens", app);

  var tableInput = qs("#dtTableId", app);
  var rowInput = qs("#dtRowId", app);
  var fieldInput = qs("#dtFieldId", app);
  var valueInput = qs("#dtValue", app);
  var scopeSel = qs("#dtScope", app);

  var navBtn = qs("#dtNavBtn", app);
  var invBtn = qs("#dtInvBtn", app);
  var modeBtn = qs("#dtModeBtn", app);
  var lensBtn = qs("#dtLensBtn", app);
  var stageBtn = qs("#dtStageBtn", app);
  var resetBtn = qs("#dtResetBtn", app);
  var commitBtn = qs("#dtCommitBtn", app);
  var refreshBtn = qs("#dtRefreshBtn", app);

  var anthologyRefreshBtn = qs("#dtAnthologyRefreshBtn", app);
  var anthologyGraphRefreshBtn = qs("#dtAnthologyGraphRefreshBtn", app);

  var messagesEl = qs("#dtMessages", app);
  var stateEl = qs("#dtStateSummary", app);
  var modelMetaEl = qs("#dtModelMeta", app);
  var leftPaneEl = qs("#dtLeftPane", app);
  var rightPaneEl = qs("#dtRightPane", app);
  var anthologyLayersEl = qs("#dtAnthologyLayers", app);
  var anthologyStatusEl = qs("#dtAnthologyStatus", app);
  var anthologyGraphEl = qs("#dtAnthologyGraph", app);
  var anthologyGraphStatusEl = qs("#dtAnthologyGraphStatus", app);
  var nimmSummaryEl = qs("#dtNimmSummary", app);
  var nimmOpenBtn = qs("#dtOpenNimmBtn", app);
  var nimmOverlay = qs("#dtNimmOverlay");
  var nimmCloseBtn = qs("#dtCloseNimmBtn");

  var tsEnsureBaseBtn = qs("#dttsEnsureBaseBtn", app);
  var tsRefreshBtn = qs("#dttsRefreshBtn", app);
  var tsStatusEl = qs("#dttsStatus", app);
  var tsPointRefInput = qs("#dttsPointRef", app);
  var tsDurationRefInput = qs("#dttsDurationRef", app);
  var tsStartInput = qs("#dttsStart", app);
  var tsDurationInput = qs("#dttsDuration", app);
  var tsLabelInput = qs("#dttsLabel", app);
  var tsCreateBtn = qs("#dttsCreateBtn", app);
  var tsEventListEl = qs("#dttsEventList", app);
  var tsEventDetailEl = qs("#dttsEventDetail", app);
  var tsTableSelect = qs("#dttsTableSelect", app);
  var tsTableModeSelect = qs("#dttsTableMode", app);
  var tsTableLoadBtn = qs("#dttsTableLoadBtn", app);
  var tsTableOutputEl = qs("#dttsTableOutput", app);

  var samrasStatusEl = qs("#dtsamrasStatus", app);
  var samrasInstanceTabsEl = qs("#dtsamrasInstanceTabs", app);
  var samrasTableNameInput = qs("#dtsamrasTableName", app);
  var samrasInstanceIdInput = qs("#dtsamrasInstanceId", app);
  var samrasCreateBtn = qs("#dtsamrasCreateBtn", app);
  var samrasAddressIdInput = qs("#dtsamrasAddressId", app);
  var samrasTitleInput = qs("#dtsamrasTitle", app);
  var samrasUpsertBtn = qs("#dtsamrasUpsertBtn", app);
  var samrasAddChildBtn = qs("#dtsamrasAddChildBtn", app);
  var samrasAddRootBtn = qs("#dtsamrasAddRootBtn", app);
  var samrasDeleteSelectedBtn = qs("#dtsamrasDeleteSelectedBtn", app);
  var samrasFormResetBtn = qs("#dtsamrasFormResetBtn", app);
  var samrasFilterInput = qs("#dtsamrasFilter", app);
  var samrasGraphModeSel = qs("#dtsamrasGraphMode", app);
  var samrasRefreshBtn = qs("#dtsamrasRefreshBtn", app);
  var samrasRowsEl = qs("#dtsamrasRows", app);
  var samrasGraphEl = qs("#dtsamrasGraph", app);
  var samrasSelectedNodeTitleEl = qs("#dtsamrasSelectedNodeTitle", app);
  var samrasSelectedNodeMetaEl = qs("#dtsamrasSelectedNodeMeta", app);

  var profileModal = qs("#dtProfileModal");
  var profileCloseBtn = qs("#dtProfileCloseBtn");
  var profileTargetEl = qs("#dtProfileTarget");
  var profileTitleEl = qs("#dtProfileTitle");
  var profileIdentifierEl = qs("#dtProfileIdentifier");
  var profileLabelInput = qs("#dtProfileLabel");
  var profileSaveBtn = qs("#dtProfileSaveBtn");
  var profilePairsEl = qs("#dtProfilePairs");
  var profilePairAddBtn = qs("#dtProfilePairAddBtn");

  var profileIconSearchInput = qs("#dtProfileIconSearch");
  var profileIconClearBtn = qs("#dtProfileIconClearBtn");
  var profileIconCurrentEl = qs("#dtProfileIconCurrent");
  var profileIconListEl = qs("#dtProfileIconList");

  var profileAbstractionEl = qs("#dtProfileAbstraction");
  var profileTabButtons = qsa("[data-profile-tab]", profileModal);
  var profilePanels = qsa("[data-profile-panel]", profileModal);

  var appendModal = qs("#dtAppendModal");
  var appendCloseBtn = qs("#dtAppendCloseBtn");
  var appendTargetEl = qs("#dtAppendTarget");
  var appendLayerInput = qs("#dtAppendLayer");
  var appendValueGroupInput = qs("#dtAppendValueGroup");
  var appendLabelInput = qs("#dtAppendLabel");
  var appendPairsEl = qs("#dtAppendPairs");
  var appendPairAddBtn = qs("#dtAppendPairAddBtn");
  var appendSaveBtn = qs("#dtAppendSaveBtn");

  var iconCatalog = [];
  var iconCatalogLoaded = false;
  var iconRelpathMode = "path";

  var currentProfileRowId = "";
  var currentProfileIdentifier = "";
  var currentProfileIconRelpath = "";
  var currentProfileValueGroup = 1;

  var anthologyUiState = {
    initialized: false,
    layerOpen: {},
    valueGroupOpen: {},
    rowByIdentifier: {},
    rowById: {},
    graphByIdentifier: {},
  };

  var timeSeriesUiState = {
    selectedEventRef: "",
    events: [],
    eventEnabledTables: [],
  };

  var samrasUiState = {
    instances: [],
    activeInstanceId: "",
    tableRows: [],
    graph: {},
    filter: "",
    expandedByInstance: {},
    selectedNodeId: "",
    graphMode: "full_span",
  };

  function escapeText(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function setMessages(errors, warnings) {
    var err = Array.isArray(errors) ? errors.filter(Boolean) : [];
    var warn = Array.isArray(warnings) ? warnings.filter(Boolean) : [];
    if (!messagesEl) return;
    if (!err.length && !warn.length) {
      messagesEl.style.display = "none";
      messagesEl.innerHTML = "";
      return;
    }

    messagesEl.style.display = "block";
    messagesEl.innerHTML = "";

    err.forEach(function (msg) {
      var row = document.createElement("div");
      row.className = "data-message is-error";
      row.textContent = msg;
      messagesEl.appendChild(row);
    });

    warn.forEach(function (msg) {
      var row = document.createElement("div");
      row.className = "data-message is-warn";
      row.textContent = msg;
      messagesEl.appendChild(row);
    });
  }

  function parseDatumIdentifier(identifier) {
    var token = String(identifier || "").trim();
    var match = token.match(/^([0-9]+)-([0-9]+)-([0-9]+)$/);
    if (!match) return null;
    return {
      layer: parseInt(match[1], 10),
      value_group: parseInt(match[2], 10),
      iteration: parseInt(match[3], 10),
    };
  }

  function normalizePairs(rawPairs, fallbackReference, fallbackMagnitude) {
    var out = [];
    if (Array.isArray(rawPairs)) {
      rawPairs.forEach(function (item) {
        if (!item || typeof item !== "object") return;
        var reference = String(item.reference || "").trim();
        var magnitude = String(item.magnitude || "").trim();
        if (!reference && !magnitude) return;
        out.push({ reference: reference, magnitude: magnitude });
      });
    }
    if (out.length) return out;

    var ref = String(fallbackReference || "").trim();
    var mag = String(fallbackMagnitude || "").trim();
    if (!ref && !mag) return [];
    return [{ reference: ref, magnitude: mag }];
  }

  function pairsToSummary(pairs) {
    var list = Array.isArray(pairs) ? pairs : [];
    if (!list.length) return "no pairs";
    var preview = list.slice(0, 2).map(function (pair) {
      var ref = String(pair.reference || "").trim();
      var mag = String(pair.magnitude || "").trim();
      return ref + " -> " + mag;
    });
    var suffix = list.length > 2 ? " (+" + String(list.length - 2) + " more)" : "";
    return String(list.length) + " pair" + (list.length === 1 ? "" : "s") + ": " + preview.join("; ") + suffix;
  }

  function clipSpan(text) {
    var span = document.createElement("span");
    span.className = "data-tool__clip";
    span.textContent = String(text || "");
    span.title = String(text || "");
    return span;
  }

  function isModalVisible(node) {
    return !!(node && !node.hidden);
  }

  function updateBodyModalState() {
    var anyModalOpen = isModalVisible(profileModal) || isModalVisible(appendModal) || isModalVisible(nimmOverlay);
    document.body.classList.toggle("is-modal-open", anyModalOpen);
  }

  function closeNimmOverlay() {
    if (!nimmOverlay) return;
    nimmOverlay.hidden = true;
    nimmOverlay.setAttribute("aria-hidden", "true");
    nimmOverlay.style.display = "none";
    updateBodyModalState();
  }

  function openNimmOverlay() {
    if (!nimmOverlay) return;
    nimmOverlay.hidden = false;
    nimmOverlay.setAttribute("aria-hidden", "false");
    nimmOverlay.style.display = "grid";
    updateBodyModalState();
  }

  function layerStateKey(layerValue) {
    return String(layerValue == null ? "unknown" : layerValue);
  }

  function valueGroupStateKey(layerValue, groupValue) {
    return layerStateKey(layerValue) + "::" + String(groupValue == null ? "unknown" : groupValue);
  }

  function captureAnthologyOpenState() {
    if (!anthologyLayersEl) return;
    var layerNodes = qsa(".data-tool__layerGroup[data-layer-key]", anthologyLayersEl);
    var groupNodes = qsa(".data-tool__valueGroup[data-group-key]", anthologyLayersEl);

    layerNodes.forEach(function (node) {
      var key = node.getAttribute("data-layer-key");
      if (!key) return;
      anthologyUiState.layerOpen[key] = !!node.open;
    });

    groupNodes.forEach(function (node) {
      var key = node.getAttribute("data-group-key");
      if (!key) return;
      anthologyUiState.valueGroupOpen[key] = !!node.open;
    });

    if (layerNodes.length || groupNodes.length) {
      anthologyUiState.initialized = true;
    }
  }

  function addPairRow(targetEl, referenceValue, magnitudeValue, removeClassName) {
    if (!targetEl) return;

    var row = document.createElement("div");
    row.className = "data-tool__appendPairRow";

    var refLabel = document.createElement("label");
    var refSpan = document.createElement("span");
    refSpan.textContent = "reference";
    var refInput = document.createElement("input");
    refInput.type = "text";
    refInput.className = "js-pair-reference";
    refInput.placeholder = "e.g. 4-1-9";
    refInput.value = String(referenceValue || "");
    refLabel.appendChild(refSpan);
    refLabel.appendChild(refInput);

    var magLabel = document.createElement("label");
    magLabel.className = "js-pair-magnitude-label";
    var magSpan = document.createElement("span");
    magSpan.textContent = "magnitude";
    var magInput = document.createElement("input");
    magInput.type = "text";
    magInput.className = "js-pair-magnitude";
    magInput.placeholder = "e.g. 3-2-3-17-...";
    magInput.value = String(magnitudeValue || "");
    magLabel.appendChild(magSpan);
    magLabel.appendChild(magInput);

    var removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "data-tool__actionBtn " + removeClassName;
    removeBtn.textContent = "Remove";

    row.appendChild(refLabel);
    row.appendChild(magLabel);
    row.appendChild(removeBtn);
    targetEl.appendChild(row);
  }

  function ensurePairRows(targetEl, removeClassName) {
    if (!targetEl) return;
    if (qsa(".data-tool__appendPairRow", targetEl).length) return;
    addPairRow(targetEl, "", "", removeClassName);
  }

  function resetPairRows(targetEl, removeClassName, pairs) {
    if (!targetEl) return;
    targetEl.innerHTML = "";
    var list = Array.isArray(pairs) ? pairs : [];
    if (!list.length) {
      addPairRow(targetEl, "", "", removeClassName);
      return;
    }
    list.forEach(function (pair) {
      addPairRow(targetEl, pair.reference, pair.magnitude, removeClassName);
    });
  }

  function readPairRows(targetEl) {
    return readPairRowsForValueGroup(targetEl, 1);
  }

  function readPairRowsForValueGroup(targetEl, valueGroupToken) {
    if (!targetEl) return [];
    var rows = qsa(".data-tool__appendPairRow", targetEl);
    var pairs = [];
    var vg = parseNonNegativeInt(valueGroupToken, 1);
    var isVg0 = vg === 0;

    rows.forEach(function (row) {
      var refInput = qs(".js-pair-reference", row);
      var magInput = qs(".js-pair-magnitude", row);
      var reference = String(refInput ? refInput.value : "").trim();
      var magnitude = isVg0 ? "0" : String(magInput ? magInput.value : "").trim();
      if (!reference && (!magnitude || isVg0)) return;
      pairs.push({ reference: reference, magnitude: magnitude });
    });

    return pairs;
  }

  function syncPairRowMode(targetEl, valueGroupToken) {
    if (!targetEl) return;
    var vg = parseNonNegativeInt(valueGroupToken, 1);
    var isVg0 = vg === 0;
    qsa(".data-tool__appendPairRow", targetEl).forEach(function (row) {
      var magLabel = qs(".js-pair-magnitude-label", row);
      var magInput = qs(".js-pair-magnitude", row);
      if (!magLabel || !magInput) return;

      if (isVg0) {
        if (!String(magInput.value || "").trim()) {
          magInput.value = "0";
          magInput.setAttribute("data-auto-vg0", "1");
        }
        magInput.disabled = true;
        magLabel.style.display = "none";
      } else {
        magInput.disabled = false;
        magLabel.style.display = "";
        if (magInput.getAttribute("data-auto-vg0") === "1") {
          magInput.value = "";
          magInput.removeAttribute("data-auto-vg0");
        }
      }
    });
  }

  function buildDatumLookup(rows) {
    var lookup = Object.create(null);
    var list = Array.isArray(rows) ? rows : [];
    list.forEach(function (row) {
      if (!row || typeof row !== "object") return;
      var identifier = String(row.identifier || row.row_id || "").trim();
      if (!identifier) return;
      if (!lookup[identifier]) lookup[identifier] = row;

      var parts = identifier.split("-");
      if (parts.length >= 4) {
        var tail = parts.slice(parts.length - 3).join("-");
        if (!lookup[tail]) lookup[tail] = row;
      }
    });
    return lookup;
  }

  function createPairCard(pair, lookup) {
    var reference = String(pair && pair.reference != null ? pair.reference : "").trim();
    var magnitude = String(pair && pair.magnitude != null ? pair.magnitude : "").trim();
    var refDatum = reference && lookup ? lookup[reference] : null;
    var iconUrl = refDatum && refDatum.icon_url ? String(refDatum.icon_url) : "";
    var label = refDatum && refDatum.label ? String(refDatum.label) : "";

    var card = document.createElement("div");
    card.className = "data-tool__pairCard";

    var iconWrap = document.createElement("span");
    iconWrap.className = "data-tool__pairIcon";
    if (iconUrl) {
      var img = document.createElement("img");
      img.src = iconUrl;
      img.alt = "";
      img.className = "datum-icon";
      iconWrap.appendChild(img);
    } else {
      var placeholder = document.createElement("span");
      placeholder.className = "datum-icon datum-icon--placeholder";
      placeholder.textContent = "+";
      iconWrap.appendChild(placeholder);
    }

    var body = document.createElement("div");
    body.className = "data-tool__pairBody";

    var addr = document.createElement("div");
    addr.className = "data-tool__pairAddress data-tool__clip";
    addr.textContent = reference || "(no reference)";
    addr.title = reference || "(no reference)";

    var mag = document.createElement("div");
    mag.className = "data-tool__pairMagnitude data-tool__clip";
    mag.textContent = magnitude || "(no magnitude)";
    mag.title = magnitude || "(no magnitude)";

    body.appendChild(addr);
    if (label) {
      var refLabel = document.createElement("div");
      refLabel.className = "data-tool__pairLabel data-tool__clip";
      refLabel.textContent = label;
      refLabel.title = label;
      body.appendChild(refLabel);
    }
    body.appendChild(mag);

    card.appendChild(iconWrap);
    card.appendChild(body);
    return card;
  }

  function normalizeSelectionReferences(rawRefs, fallbackMagnitude) {
    var refs = [];
    var seen = {};
    function pushRef(value) {
      var token = String(value == null ? "" : value).trim();
      if (!token || token === "0" || seen[token]) return;
      seen[token] = true;
      refs.push(token);
    }

    if (Array.isArray(rawRefs)) {
      rawRefs.forEach(pushRef);
    }
    if (refs.length) return refs;

    var magnitudeToken = String(fallbackMagnitude == null ? "" : fallbackMagnitude).trim();
    if (!magnitudeToken) return refs;
    if (magnitudeToken.charAt(0) === "[" && magnitudeToken.charAt(magnitudeToken.length - 1) === "]") {
      try {
        var parsed = JSON.parse(magnitudeToken);
        if (Array.isArray(parsed)) parsed.forEach(pushRef);
      } catch (_) {}
    } else {
      magnitudeToken.split(",").forEach(pushRef);
    }
    return refs;
  }

  function parseNonNegativeInt(value, fallback) {
    var parsed = parseInt(String(value == null ? "" : value).trim(), 10);
    if (!Number.isFinite(parsed) || parsed < 0) return fallback;
    return parsed;
  }

  function parsePositiveInt(value, fallback) {
    var parsed = parseInt(String(value == null ? "" : value).trim(), 10);
    if (!Number.isFinite(parsed) || parsed < 1) return fallback;
    return parsed;
  }

  function formatUnixSeconds(value) {
    var parsed = parseInt(String(value == null ? "" : value).trim(), 10);
    if (!Number.isFinite(parsed) || parsed < 0) return "";
    var stamp = new Date(parsed * 1000);
    if (!stamp || !Number.isFinite(stamp.getTime())) return "";
    return stamp.toISOString();
  }

  function summarizeEvent(event) {
    var eventRef = String(event && event.event_ref ? event.event_ref : "").trim();
    var label = String(event && event.label ? event.label : "").trim();
    var startToken = String(event && event.start_unix_s != null ? event.start_unix_s : "").trim();
    var durationToken = String(event && event.duration_s != null ? event.duration_s : "").trim();
    var iso = formatUnixSeconds(startToken);
    var parts = [];
    if (label) parts.push(label);
    if (eventRef) parts.push(eventRef);
    if (startToken) parts.push("start=" + startToken);
    if (durationToken) parts.push("duration=" + durationToken + "s");
    if (iso) parts.push(iso);
    return parts.join(" | ");
  }

  function renderTimeSeriesTableOptions(tables) {
    if (!tsTableSelect) return;
    var selected = String(tsTableSelect.value || "").trim();
    var list = Array.isArray(tables) ? tables : [];
    tsTableSelect.innerHTML = "";

    var placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = list.length ? "Select table" : "No event-enabled tables";
    tsTableSelect.appendChild(placeholder);

    list.forEach(function (item) {
      var tableId = String(item && item.table_id ? item.table_id : "").trim();
      if (!tableId) return;
      var option = document.createElement("option");
      option.value = tableId;
      option.textContent =
        tableId +
        " (" +
        String(item.event_row_count || 0) +
        "/" +
        String(item.row_count || 0) +
        " rows)";
      if (tableId === selected) option.selected = true;
      tsTableSelect.appendChild(option);
    });

    if (!list.length) {
      tsTableSelect.value = "";
    }
  }

  function renderTimeSeriesEventList(events) {
    if (!tsEventListEl) return;
    var list = Array.isArray(events) ? events : [];
    tsEventListEl.innerHTML = "";

    if (!list.length) {
      var empty = document.createElement("p");
      empty.className = "data-tool__empty";
      empty.textContent = "No events in 4-1-* yet.";
      tsEventListEl.appendChild(empty);
      return;
    }

    var wrap = document.createElement("div");
    wrap.className = "data-tool__datumList";

    list.forEach(function (event) {
      var eventRef = String(event && event.event_ref ? event.event_ref : "").trim();
      var row = document.createElement("div");
      row.className = "data-tool__datumRow";

      var textWrap = document.createElement("div");
      textWrap.className = "data-tool__datumText";

      var title = document.createElement("div");
      title.className = "data-tool__datumTitle";
      title.textContent = String(event && event.label ? event.label : eventRef || "event");

      var meta = document.createElement("div");
      meta.className = "data-tool__datumMeta";
      meta.textContent = summarizeEvent(event);

      textWrap.appendChild(title);
      textWrap.appendChild(meta);

      var actions = document.createElement("div");
      actions.className = "data-tool__valueGroupActions";

      var inspectBtn = document.createElement("button");
      inspectBtn.type = "button";
      inspectBtn.className = "data-tool__actionBtn js-dtts-inspect";
      inspectBtn.setAttribute("data-event-ref", eventRef);
      inspectBtn.textContent = "Inspect";

      var editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.className = "data-tool__actionBtn js-dtts-edit";
      editBtn.setAttribute("data-event-ref", eventRef);
      editBtn.textContent = "Edit";

      var deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "data-tool__actionBtn data-tool__actionBtn--danger js-dtts-delete";
      deleteBtn.setAttribute("data-event-ref", eventRef);
      deleteBtn.textContent = "Delete";

      actions.appendChild(inspectBtn);
      actions.appendChild(editBtn);
      actions.appendChild(deleteBtn);

      row.appendChild(textWrap);
      row.appendChild(actions);
      wrap.appendChild(row);
    });

    tsEventListEl.appendChild(wrap);
  }

  function renderTimeSeriesEventDetail(payload) {
    if (!tsEventDetailEl) return;
    tsEventDetailEl.innerHTML = "";

    var detail = payload && typeof payload === "object" ? payload : {};
    var event = detail.event && typeof detail.event === "object" ? detail.event : null;
    if (!event) {
      var empty = document.createElement("p");
      empty.className = "data-tool__empty";
      empty.textContent = "Select an event to inspect.";
      tsEventDetailEl.appendChild(empty);
      return;
    }

    var eventRef = String(event.event_ref || "").trim();
    var referencedBy = Array.isArray(detail.referenced_by) ? detail.referenced_by : [];
    var eventTables = Array.isArray(detail.event_enabled_tables) ? detail.event_enabled_tables : [];
    var startDisplay = formatUnixSeconds(event.start_unix_s);

    var wrapper = document.createElement("div");
    wrapper.innerHTML =
      "<div class=\"data-tool__controlRow data-tool__editRow\">" +
      "<label><span>event_ref</span><input id=\"dttsDetailEventRef\" type=\"text\" readonly value=\"" + escapeText(eventRef) + "\" /></label>" +
      "<label><span>point_ref</span><input id=\"dttsDetailPointRef\" type=\"text\" value=\"" + escapeText(event.point_ref || "") + "\" /></label>" +
      "<label><span>duration_ref</span><input id=\"dttsDetailDurationRef\" type=\"text\" value=\"" + escapeText(event.duration_ref || "") + "\" /></label>" +
      "<label><span>start_unix_s</span><input id=\"dttsDetailStart\" type=\"number\" min=\"0\" step=\"1\" value=\"" + escapeText(event.start_unix_s) + "\" /></label>" +
      "<label><span>duration_s</span><input id=\"dttsDetailDuration\" type=\"number\" min=\"1\" step=\"1\" value=\"" + escapeText(event.duration_s) + "\" /></label>" +
      "</div>" +
      "<div class=\"data-tool__controlRow\">" +
      "<label style=\"min-width: 360px;\"><span>label</span><input id=\"dttsDetailLabel\" type=\"text\" value=\"" + escapeText(event.label || "") + "\" /></label>" +
      "<button type=\"button\" class=\"data-tool__actionBtn js-dtts-detail-save\">Save Event</button>" +
      "<button type=\"button\" class=\"data-tool__actionBtn data-tool__actionBtn--danger js-dtts-detail-delete\" data-event-ref=\"" + escapeText(eventRef) + "\">Delete Event</button>" +
      "</div>" +
      "<p class=\"data-tool__legendText\">" + escapeText(startDisplay ? ("Timestamp: " + startDisplay) : "Timestamp unavailable") + "</p>" +
      "<div class=\"card__kicker\" style=\"margin-top: 8px;\">Datums Referencing This Event</div>";

    if (!referencedBy.length) {
      wrapper.innerHTML += "<p class=\"data-tool__empty\">No rows currently reference this event.</p>";
    } else {
      wrapper.innerHTML += "<ul class=\"bullets\">" +
        referencedBy
          .map(function (row) {
            return "<li><code>" +
              escapeText(row.identifier || "") +
              "</code>" +
              (row.label ? " - " + escapeText(row.label) : "") +
              "</li>";
          })
          .join("") +
        "</ul>";
    }

    wrapper.innerHTML += "<div class=\"card__kicker\" style=\"margin-top: 8px;\">Event-Enabled Tables</div>";
    if (!eventTables.length) {
      wrapper.innerHTML += "<p class=\"data-tool__empty\">No event-enabled tables detected.</p>";
    } else {
      wrapper.innerHTML += "<ul class=\"bullets\">" +
        eventTables
          .map(function (item) {
            return "<li><code>" +
              escapeText(item.table_id || "") +
              "</code> (" +
              escapeText(item.event_row_count || 0) +
              "/" +
              escapeText(item.row_count || 0) +
              " rows)</li>";
          })
          .join("") +
        "</ul>";
    }

    tsEventDetailEl.appendChild(wrapper);
  }

  function samrasSortKey(token) {
    return String(token || "")
      .split("-")
      .map(function (part) {
        var value = parseInt(part, 10);
        return Number.isFinite(value) ? value : 999999999;
      });
  }

  function compareSamrasIds(a, b) {
    var ak = samrasSortKey(a);
    var bk = samrasSortKey(b);
    var maxLen = Math.max(ak.length, bk.length);
    for (var idx = 0; idx < maxLen; idx += 1) {
      var av = idx < ak.length ? ak[idx] : -1;
      var bv = idx < bk.length ? bk[idx] : -1;
      if (av < bv) return -1;
      if (av > bv) return 1;
    }
    return String(a || "").localeCompare(String(b || ""));
  }

  function getSamrasExpanded(instanceId) {
    var token = String(instanceId || "").trim();
    if (!token) return [];
    var current = samrasUiState.expandedByInstance[token];
    if (!Array.isArray(current)) {
      samrasUiState.expandedByInstance[token] = [];
      return [];
    }
    return current.filter(function (item) { return String(item || "").trim(); });
  }

  function setSamrasExpanded(instanceId, values) {
    var token = String(instanceId || "").trim();
    if (!token) return;
    var list = Array.isArray(values) ? values : [];
    var dedup = [];
    list.forEach(function (item) {
      var value = String(item || "").trim();
      if (!value || dedup.indexOf(value) !== -1) return;
      dedup.push(value);
    });
    dedup.sort(compareSamrasIds);
    samrasUiState.expandedByInstance[token] = dedup;
  }

  function renderSamrasStatus() {
    if (!samrasStatusEl) return;
    var active = String(samrasUiState.activeInstanceId || "").trim();
    if (!active) {
      samrasStatusEl.textContent = "No SAMRAS instance selected.";
      return;
    }
    var tableRows = Array.isArray(samrasUiState.tableRows) ? samrasUiState.tableRows.length : 0;
    var total = samrasUiState.graph && samrasUiState.graph.total_count != null ? samrasUiState.graph.total_count : tableRows;
    var visible = samrasUiState.graph && samrasUiState.graph.visible_count != null ? samrasUiState.graph.visible_count : tableRows;
    var selected = String(samrasUiState.selectedNodeId || "").trim();
    samrasStatusEl.textContent =
      "Instance " + active +
      " | rows " + String(tableRows) +
      " | graph " + String(visible) + "/" + String(total) +
      (selected ? " | selected " + selected : "");
  }

  function findSamrasRowById(addressId) {
    var token = String(addressId || "").trim();
    if (!token) return null;
    var rows = Array.isArray(samrasUiState.tableRows) ? samrasUiState.tableRows : [];
    for (var idx = 0; idx < rows.length; idx += 1) {
      var row = rows[idx] || {};
      var rowId = String(row.address_id || row.row_id || "").trim();
      if (rowId === token) {
        return row;
      }
    }
    return null;
  }

  function samrasParentAddress(addressId) {
    var token = String(addressId || "").trim();
    if (!token) return "";
    var parts = token.split("-");
    if (parts.length <= 1) return "";
    return parts.slice(0, -1).join("-");
  }

  function samrasDepth(addressId) {
    var token = String(addressId || "").trim();
    if (!token) return 0;
    return token.split("-").length;
  }

  function samrasDirectChildren(addressId) {
    var parent = String(addressId || "").trim();
    if (!parent) return [];
    var parentDepth = samrasDepth(parent);
    var rows = Array.isArray(samrasUiState.tableRows) ? samrasUiState.tableRows : [];
    return rows
      .filter(function (row) {
        var childId = String((row && (row.address_id || row.row_id)) || "").trim();
        if (!childId) return false;
        if (samrasParentAddress(childId) !== parent) return false;
        return samrasDepth(childId) === parentDepth + 1;
      })
      .sort(function (left, right) {
        return compareSamrasIds(
          left && (left.address_id || left.row_id),
          right && (right.address_id || right.row_id)
        );
      });
  }

  function samrasNextRootAddress() {
    var rows = Array.isArray(samrasUiState.tableRows) ? samrasUiState.tableRows : [];
    var maxRoot = 0;
    rows.forEach(function (row) {
      var addressId = String((row && (row.address_id || row.row_id)) || "").trim();
      if (!addressId) return;
      var parts = addressId.split("-");
      if (parts.length !== 1) return;
      var value = parseInt(parts[0], 10);
      if (Number.isFinite(value) && value > maxRoot) maxRoot = value;
    });
    return String(maxRoot + 1);
  }

  function samrasNextChildAddress(parentAddress) {
    var parent = String(parentAddress || "").trim();
    if (!parent) return "";
    var maxSegment = 0;
    samrasDirectChildren(parent).forEach(function (row) {
      var addressId = String((row && (row.address_id || row.row_id)) || "").trim();
      var parts = addressId.split("-");
      var tail = parseInt(parts[parts.length - 1], 10);
      if (Number.isFinite(tail) && tail > maxSegment) maxSegment = tail;
    });
    return parent + "-" + String(maxSegment + 1);
  }

  function renderSamrasSelectionMeta() {
    var selectedId = String(samrasUiState.selectedNodeId || "").trim();
    var selectedRow = findSamrasRowById(selectedId);
    var parentId = samrasParentAddress(selectedId);
    var children = samrasDirectChildren(selectedId);

    if (samrasSelectedNodeTitleEl) {
      samrasSelectedNodeTitleEl.textContent = selectedId || "No node selected";
    }
    if (samrasSelectedNodeMetaEl) {
      if (!selectedId) {
        samrasSelectedNodeMetaEl.textContent = "Select a hierarchy node to edit and inspect context.";
      } else {
        var label = String((selectedRow && (selectedRow.title || selectedRow.name)) || "").trim();
        samrasSelectedNodeMetaEl.textContent =
          (label ? ("title: " + label + " | ") : "") +
          "parent: " + (parentId || "none") +
          " | children: " + String(children.length);
      }
    }
  }

  function renderSamrasInstanceTabs() {
    if (!samrasInstanceTabsEl) return;
    samrasInstanceTabsEl.innerHTML = "";
    var items = Array.isArray(samrasUiState.instances) ? samrasUiState.instances : [];
    if (!items.length) {
      var empty = document.createElement("p");
      empty.className = "data-tool__empty";
      empty.textContent = "No SAMRAS instances discovered yet.";
      samrasInstanceTabsEl.appendChild(empty);
      return;
    }
    items.forEach(function (item) {
      var instanceId = String(item && item.instance_id ? item.instance_id : "").trim();
      if (!instanceId) return;
      var button = document.createElement("button");
      button.type = "button";
      button.className = "servicetabs__tab js-dtsamras-instance";
      if (instanceId === samrasUiState.activeInstanceId) {
        button.classList.add("is-active");
      }
      button.setAttribute("data-instance-id", instanceId);
      var tableName = String(item && item.table_name ? item.table_name : instanceId).trim();
      var rowCount = parseInt(String(item && item.row_count != null ? item.row_count : "0"), 10);
      if (!Number.isFinite(rowCount)) rowCount = 0;
      button.textContent = tableName + " (" + instanceId + ") [" + String(rowCount) + "]";
      samrasInstanceTabsEl.appendChild(button);
    });
  }

  function renderSamrasRows(rows) {
    if (!samrasRowsEl) return;
    samrasRowsEl.innerHTML = "";
    var list = Array.isArray(rows) ? rows : [];
    if (!list.length) {
      var trEmpty = document.createElement("tr");
      var tdEmpty = document.createElement("td");
      tdEmpty.colSpan = 4;
      tdEmpty.className = "data-tool__empty";
      tdEmpty.textContent = "No SAMRAS rows for this instance.";
      trEmpty.appendChild(tdEmpty);
      samrasRowsEl.appendChild(trEmpty);
      return;
    }

    var selectedId = String(samrasUiState.selectedNodeId || "").trim();
    if (!selectedId) {
      var trNoSelection = document.createElement("tr");
      var tdNoSelection = document.createElement("td");
      tdNoSelection.colSpan = 4;
      tdNoSelection.className = "data-tool__empty";
      tdNoSelection.textContent = "Select a node in the hierarchy to load context rows.";
      trNoSelection.appendChild(tdNoSelection);
      samrasRowsEl.appendChild(trNoSelection);
      return;
    }

    var selectedRow = findSamrasRowById(selectedId);
    var parentId = samrasParentAddress(selectedId);
    var parentRow = findSamrasRowById(parentId);
    var children = samrasDirectChildren(selectedId);
    var siblings = list
      .filter(function (row) {
        var rowId = String((row && (row.address_id || row.row_id)) || "").trim();
        return rowId && rowId !== selectedId && samrasParentAddress(rowId) === parentId;
      })
      .sort(function (left, right) {
        return compareSamrasIds(
          left && (left.address_id || left.row_id),
          right && (right.address_id || right.row_id)
        );
      });

    var contextRows = [];
    if (selectedRow) {
      contextRows.push({ relation: "selected", row: selectedRow });
    }
    if (parentRow) {
      contextRows.push({ relation: "parent", row: parentRow });
    }
    children.forEach(function (row) {
      contextRows.push({ relation: "child", row: row });
    });
    siblings.slice(0, 8).forEach(function (row) {
      contextRows.push({ relation: "sibling", row: row });
    });

    if (!contextRows.length) {
      var trNoContext = document.createElement("tr");
      var tdNoContext = document.createElement("td");
      tdNoContext.colSpan = 4;
      tdNoContext.className = "data-tool__empty";
      tdNoContext.textContent = "Selected node is not present in the current filtered table.";
      trNoContext.appendChild(tdNoContext);
      samrasRowsEl.appendChild(trNoContext);
      return;
    }

    contextRows.forEach(function (entry) {
      var row = entry.row || {};
      var relation = String(entry.relation || "").trim();
      var addressId = String(row.address_id || row.row_id || "").trim();
      var title = String(row.title || row.name || "").trim();
      var tr = document.createElement("tr");
      if (addressId === selectedId) tr.className = "is-active";

      var relationTd = document.createElement("td");
      relationTd.textContent = relation || "";
      tr.appendChild(relationTd);

      var addressTd = document.createElement("td");
      var addressCode = document.createElement("code");
      addressCode.textContent = addressId;
      addressTd.appendChild(addressCode);
      tr.appendChild(addressTd);

      var titleTd = document.createElement("td");
      titleTd.appendChild(clipSpan(title));
      tr.appendChild(titleTd);

      var selectTd = document.createElement("td");
      var selectBtn = document.createElement("button");
      selectBtn.type = "button";
      selectBtn.className = "data-tool__actionBtn js-dtsamras-select";
      selectBtn.setAttribute("data-address-id", addressId);
      selectBtn.textContent = addressId === selectedId ? "Selected" : "Select";
      selectTd.appendChild(selectBtn);
      tr.appendChild(selectTd);

      samrasRowsEl.appendChild(tr);
    });
  }

  function buildSamrasTree(rows) {
    var sortedRows = Array.isArray(rows) ? rows.slice() : [];
    sortedRows.sort(function (left, right) {
      return compareSamrasIds(
        left && (left.address_id || left.row_id),
        right && (right.address_id || right.row_id)
      );
    });

    var byId = {};
    var childrenById = {};
    sortedRows.forEach(function (row) {
      var addressId = String((row && (row.address_id || row.row_id)) || "").trim();
      if (!addressId) return;
      byId[addressId] = {
        address_id: addressId,
        title: String((row && (row.title || row.name)) || "").trim(),
        parent_id: samrasParentAddress(addressId),
        depth: samrasDepth(addressId),
        leaf_span: 1,
      };
      if (!childrenById[addressId]) childrenById[addressId] = [];
    });

    Object.keys(byId).forEach(function (addressId) {
      var node = byId[addressId];
      var parentId = String(node.parent_id || "").trim();
      if (!parentId || !byId[parentId]) return;
      childrenById[parentId].push(addressId);
    });

    Object.keys(childrenById).forEach(function (parentId) {
      childrenById[parentId].sort(compareSamrasIds);
    });

    var roots = Object.keys(byId).filter(function (addressId) {
      var parentId = String((byId[addressId] && byId[addressId].parent_id) || "").trim();
      return !parentId || !byId[parentId];
    }).sort(compareSamrasIds);

    function computeLeafSpan(addressId) {
      var childIds = childrenById[addressId] || [];
      if (!childIds.length) {
        byId[addressId].leaf_span = 1;
        return 1;
      }
      var total = 0;
      childIds.forEach(function (childId) {
        total += computeLeafSpan(childId);
      });
      byId[addressId].leaf_span = Math.max(1, total);
      return byId[addressId].leaf_span;
    }

    var totalSpan = 0;
    roots.forEach(function (rootId) {
      totalSpan += computeLeafSpan(rootId);
    });

    var lanes = {};
    function walk(addressId) {
      var node = byId[addressId];
      if (!node) return;
      var depth = Number.isFinite(node.depth) ? node.depth : 1;
      if (!lanes[depth]) lanes[depth] = [];
      lanes[depth].push(node);
      (childrenById[addressId] || []).forEach(function (childId) {
        walk(childId);
      });
    }
    roots.forEach(function (rootId) {
      walk(rootId);
    });

    return {
      roots: roots,
      lanes: lanes,
      by_id: byId,
      children_by_id: childrenById,
      total_span: Math.max(1, totalSpan),
    };
  }

  function renderSamrasFullSpanGraph(rows) {
    if (!samrasGraphEl) return;
    samrasGraphEl.innerHTML = "";
    samrasGraphEl.classList.remove("is-branch-layout");
    samrasGraphEl.classList.add("is-full-layout");

    var tree = buildSamrasTree(rows);
    var laneDepths = Object.keys(tree.lanes)
      .map(function (token) { return parseInt(token, 10); })
      .filter(function (value) { return Number.isFinite(value) && value > 0; })
      .sort(function (left, right) { return left - right; });

    if (!laneDepths.length) {
      var empty = document.createElement("p");
      empty.className = "data-tool__empty";
      empty.textContent = "No hierarchy nodes to display.";
      samrasGraphEl.appendChild(empty);
      return;
    }

    var graphWrap = document.createElement("div");
    graphWrap.className = "data-tool__samrasSpanGraph";
    graphWrap.style.setProperty("--samras-total-span", String(tree.total_span));

    laneDepths.forEach(function (depth) {
      var lane = document.createElement("section");
      lane.className = "data-tool__samrasSpanLane";

      var laneHead = document.createElement("div");
      laneHead.className = "data-tool__samrasSpanLaneHead";
      laneHead.textContent = "Depth " + String(depth);
      lane.appendChild(laneHead);

      var laneBody = document.createElement("div");
      laneBody.className = "data-tool__samrasSpanLaneBody";

      (tree.lanes[depth] || []).forEach(function (node) {
        var addressId = String(node.address_id || "").trim();
        var title = String(node.title || "").trim();
        var childCount = (tree.children_by_id[addressId] || []).length;
        var span = Math.max(1, parseInt(String(node.leaf_span || 1), 10) || 1);
        var isSelected = addressId && addressId === String(samrasUiState.selectedNodeId || "").trim();

        var nodeBtn = document.createElement("button");
        nodeBtn.type = "button";
        nodeBtn.className = "data-tool__samrasSpanNode";
        nodeBtn.setAttribute("data-node-id", addressId);
        nodeBtn.style.flex = String(span) + " 0 0";
        nodeBtn.title = addressId + (title ? " - " + title : "");
        if (childCount > 0) nodeBtn.classList.add("is-branch");
        if (isSelected) nodeBtn.classList.add("is-selected");

        var titleEl = document.createElement("span");
        titleEl.className = "data-tool__samrasSpanNodeTitle";
        titleEl.textContent = title || "(untitled)";
        var addressEl = document.createElement("span");
        addressEl.className = "data-tool__samrasSpanNodeAddress";
        addressEl.textContent = addressId;

        nodeBtn.appendChild(titleEl);
        nodeBtn.appendChild(addressEl);
        laneBody.appendChild(nodeBtn);
      });

      lane.appendChild(laneBody);
      graphWrap.appendChild(lane);
    });

    samrasGraphEl.appendChild(graphWrap);
  }

  function renderSamrasBranchGraph(graphPayload) {
    if (!samrasGraphEl) return;
    samrasGraphEl.innerHTML = "";
    samrasGraphEl.classList.remove("is-full-layout");
    samrasGraphEl.classList.add("is-branch-layout");
    var graph = graphPayload && typeof graphPayload === "object" ? graphPayload : {};
    var columns = Array.isArray(graph.columns) ? graph.columns : [];
    if (!columns.length) {
      var empty = document.createElement("p");
      empty.className = "data-tool__empty";
      empty.textContent = "No hierarchy nodes to display.";
      samrasGraphEl.appendChild(empty);
      return;
    }

    columns.forEach(function (column) {
      var depth = String(column && column.depth != null ? column.depth : "").trim();
      var colWrap = document.createElement("div");
      colWrap.className = "data-tool__samrasColumn";

      var head = document.createElement("div");
      head.className = "data-tool__samrasColumnHead";
      head.textContent = "Depth " + depth;
      colWrap.appendChild(head);

      var nodes = Array.isArray(column && column.nodes) ? column.nodes : [];
      nodes.sort(function (left, right) {
        return compareSamrasIds(left && left.address_id, right && right.address_id);
      });
      nodes.forEach(function (node) {
        var addressId = String(node && node.address_id ? node.address_id : "").trim();
        var title = String(node && node.title ? node.title : "").trim();
        var hasChildren = !!(node && node.has_children);
        var isExpanded = !!(node && node.is_expanded);
        var isSelected = addressId && addressId === String(samrasUiState.selectedNodeId || "").trim();

        var nodeWrap = document.createElement("div");
        nodeWrap.className = "data-tool__samrasNode";
        if (hasChildren) nodeWrap.classList.add("is-branch");
        if (isExpanded) nodeWrap.classList.add("is-expanded");
        if (isSelected) nodeWrap.classList.add("is-selected");
        nodeWrap.setAttribute("data-node-id", addressId);

        var toggleBtn = document.createElement("button");
        toggleBtn.type = "button";
        toggleBtn.className = "data-tool__samrasNodeToggle";
        toggleBtn.setAttribute("data-node-toggle", addressId);
        toggleBtn.textContent = hasChildren ? (isExpanded ? "▾" : "▸") : "•";
        toggleBtn.disabled = !hasChildren;

        var selectBtn = document.createElement("button");
        selectBtn.type = "button";
        selectBtn.className = "data-tool__samrasNodeSelect";
        selectBtn.setAttribute("data-node-id", addressId);

        var textWrap = document.createElement("span");
        textWrap.className = "data-tool__samrasNodeText";
        var top = document.createElement("span");
        top.className = "data-tool__samrasNodeAddress";
        top.textContent = addressId;
        var bottom = document.createElement("span");
        bottom.className = "data-tool__samrasNodeTitle";
        bottom.textContent = title || "(untitled)";
        textWrap.appendChild(top);
        textWrap.appendChild(bottom);

        selectBtn.appendChild(textWrap);
        nodeWrap.appendChild(toggleBtn);
        nodeWrap.appendChild(selectBtn);
        colWrap.appendChild(nodeWrap);
      });
      samrasGraphEl.appendChild(colWrap);
    });
  }

  function renderSamrasGraph(graphPayload) {
    var mode = String(samrasUiState.graphMode || "full_span").trim().toLowerCase();
    if (mode === "branch") {
      renderSamrasBranchGraph(graphPayload);
      return;
    }
    renderSamrasFullSpanGraph(samrasUiState.tableRows);
  }

  function syncSamrasFormFromSelection() {
    var selectedId = String(samrasUiState.selectedNodeId || "").trim();
    var row = findSamrasRowById(selectedId);
    if (samrasAddressIdInput) samrasAddressIdInput.value = selectedId || "";
    if (samrasTitleInput) {
      samrasTitleInput.value = row ? String(row.title || row.name || "").trim() : "";
    }
    renderSamrasSelectionMeta();
    renderSamrasRows(samrasUiState.tableRows);
    renderSamrasStatus();
  }

  function setSamrasSelection(addressId) {
    var token = String(addressId || "").trim();
    if (!token) {
      samrasUiState.selectedNodeId = "";
      syncSamrasFormFromSelection();
      renderSamrasGraph(samrasUiState.graph);
      return;
    }
    samrasUiState.selectedNodeId = token;
    syncSamrasFormFromSelection();
    renderSamrasGraph(samrasUiState.graph);
  }

  function primeSamrasRootDraft() {
    if (!samrasAddressIdInput) return;
    samrasAddressIdInput.value = samrasNextRootAddress();
    if (samrasTitleInput) {
      samrasTitleInput.value = "";
      samrasTitleInput.focus();
    }
  }

  function primeSamrasChildDraft() {
    var selectedId = String(samrasUiState.selectedNodeId || "").trim();
    if (!selectedId) throw new Error("Select a node first to draft a child address");
    var childAddress = samrasNextChildAddress(selectedId);
    if (!childAddress) throw new Error("Unable to compute next child address");
    if (samrasAddressIdInput) samrasAddressIdInput.value = childAddress;
    if (samrasTitleInput) {
      samrasTitleInput.value = "";
      samrasTitleInput.focus();
    }
  }

  function samrasExpandedQuery(instanceId) {
    return getSamrasExpanded(instanceId).join(",");
  }

  async function getSamrasInstances() {
    var payload = await api("/portal/api/data/samras/instances");
    var instances = Array.isArray(payload.instances) ? payload.instances : [];
    instances.sort(function (left, right) {
      return compareSamrasIds(left && left.instance_id, right && right.instance_id);
    });
    samrasUiState.instances = instances;
    if (!samrasUiState.activeInstanceId && instances.length) {
      samrasUiState.activeInstanceId = String(instances[0].instance_id || "").trim();
    }
    if (
      samrasUiState.activeInstanceId &&
      !instances.some(function (item) { return String(item && item.instance_id ? item.instance_id : "").trim() === samrasUiState.activeInstanceId; })
    ) {
      samrasUiState.activeInstanceId = instances.length ? String(instances[0].instance_id || "").trim() : "";
    }
    renderSamrasInstanceTabs();
    setMessages(payload.errors || [], payload.warnings || []);
    return payload;
  }

  async function getSamrasTable(instanceId) {
    var token = String(instanceId || samrasUiState.activeInstanceId || "").trim();
    if (!token) {
      samrasUiState.tableRows = [];
      samrasUiState.graph = {};
      samrasUiState.selectedNodeId = "";
      renderSamrasRows([]);
      renderSamrasGraph({});
      renderSamrasSelectionMeta();
      renderSamrasStatus();
      return null;
    }
    samrasUiState.activeInstanceId = token;
    var filterToken = String(samrasUiState.filter || "").trim();
    var query =
      "?filter=" + encodeURIComponent(filterToken) +
      "&expanded=" + encodeURIComponent(samrasExpandedQuery(token));
    var payload = await api("/portal/api/data/samras/table/" + encodeURIComponent(token) + query);
    var rows = Array.isArray(payload.rows) ? payload.rows : [];
    var graph = payload.graph && typeof payload.graph === "object" ? payload.graph : {};
    if (Array.isArray(graph.expanded)) {
      setSamrasExpanded(token, graph.expanded);
    }
    samrasUiState.tableRows = rows;
    samrasUiState.graph = graph;
    var selected = String(samrasUiState.selectedNodeId || "").trim();
    if (selected && !findSamrasRowById(selected)) {
      selected = "";
    }
    if (!selected && rows.length) {
      selected = String(rows[0].address_id || rows[0].row_id || "").trim();
    }
    samrasUiState.selectedNodeId = selected;
    renderSamrasInstanceTabs();
    renderSamrasGraph(graph);
    syncSamrasFormFromSelection();
    setMessages(payload.errors || [], payload.warnings || []);
    return payload;
  }

  async function refreshSamras() {
    await getSamrasInstances();
    if (samrasUiState.activeInstanceId) {
      await getSamrasTable(samrasUiState.activeInstanceId);
    } else {
      samrasUiState.selectedNodeId = "";
      renderSamrasRows([]);
      renderSamrasGraph({});
      renderSamrasSelectionMeta();
      renderSamrasStatus();
    }
  }

  async function createSamrasTable() {
    var payload = await api("/portal/api/data/samras/table/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        table_name: samrasTableNameInput ? samrasTableNameInput.value : "",
        instance_id: samrasInstanceIdInput ? samrasInstanceIdInput.value : "",
      }),
    });
    var created = payload && payload.created ? payload.created : {};
    var instanceId = String(created.instance_id || "").trim();
    if (samrasTableNameInput) samrasTableNameInput.value = "";
    if (samrasInstanceIdInput) samrasInstanceIdInput.value = "";
    if (instanceId) samrasUiState.activeInstanceId = instanceId;
    await refreshSamras();
    if (instanceId) {
      if (!samrasUiState.expandedByInstance[instanceId]) samrasUiState.expandedByInstance[instanceId] = [];
      await getSamrasTable(instanceId);
    }
    setMessages(payload.errors || [], payload.warnings || []);
    return payload;
  }

  async function upsertSamrasRow() {
    var instanceId = String(samrasUiState.activeInstanceId || "").trim();
    if (!instanceId) throw new Error("Select a SAMRAS instance first");
    var payload = await api("/portal/api/data/samras/row/upsert", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        instance_id: instanceId,
        address_id: samrasAddressIdInput ? samrasAddressIdInput.value : "",
        title: samrasTitleInput ? samrasTitleInput.value : "",
      }),
    });
    var submittedAddress = String(samrasAddressIdInput ? samrasAddressIdInput.value : "").trim();
    var table = payload && payload.table ? payload.table : null;
    if (table && table.graph) {
      samrasUiState.tableRows = Array.isArray(table.rows) ? table.rows : [];
      samrasUiState.graph = table.graph;
      if (Array.isArray(table.graph.expanded)) {
        setSamrasExpanded(instanceId, table.graph.expanded);
      }
      if (submittedAddress) {
        samrasUiState.selectedNodeId = submittedAddress;
      }
      renderSamrasGraph(samrasUiState.graph);
      syncSamrasFormFromSelection();
    } else {
      await getSamrasTable(instanceId);
    }
    await getSamrasInstances();
    setMessages(payload.errors || [], payload.warnings || []);
    return payload;
  }

  async function deleteSamrasRow(addressId) {
    var instanceId = String(samrasUiState.activeInstanceId || "").trim();
    if (!instanceId) throw new Error("Select a SAMRAS instance first");
    var payload = await api("/portal/api/data/samras/row/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        instance_id: instanceId,
        address_id: String(addressId || "").trim(),
      }),
    });
    var table = payload && payload.table ? payload.table : null;
    if (table && table.graph) {
      samrasUiState.tableRows = Array.isArray(table.rows) ? table.rows : [];
      samrasUiState.graph = table.graph;
      if (Array.isArray(table.graph.expanded)) {
        setSamrasExpanded(instanceId, table.graph.expanded);
      }
      if (String(samrasUiState.selectedNodeId || "").trim() === String(addressId || "").trim()) {
        samrasUiState.selectedNodeId = "";
      }
      if (!samrasUiState.selectedNodeId && samrasUiState.tableRows.length) {
        samrasUiState.selectedNodeId = String(
          samrasUiState.tableRows[0].address_id || samrasUiState.tableRows[0].row_id || ""
        ).trim();
      }
      renderSamrasGraph(samrasUiState.graph);
      syncSamrasFormFromSelection();
    } else {
      await getSamrasTable(instanceId);
    }
    await getSamrasInstances();
    setMessages(payload.errors || [], payload.warnings || []);
    return payload;
  }

  function requiredPairCountForValueGroup(valueGroupToken) {
    var vg = parseNonNegativeInt(valueGroupToken, 1);
    if (vg <= 0) return 1;
    return vg;
  }

  function ensurePairRowsMin(targetEl, removeClassName, minCount) {
    if (!targetEl) return;
    var required = Math.max(1, parseNonNegativeInt(minCount, 1));
    var rows = qsa(".data-tool__appendPairRow", targetEl);
    while (rows.length < required) {
      addPairRow(targetEl, "", "", removeClassName);
      rows = qsa(".data-tool__appendPairRow", targetEl);
    }
    if (!rows.length) {
      addPairRow(targetEl, "", "", removeClassName);
    }
  }

  function updateAppendTarget() {
    if (!appendTargetEl) return;
    var layerToken = appendLayerInput ? String(appendLayerInput.value || "1").trim() : "1";
    var valueGroupToken = appendValueGroupInput ? String(appendValueGroupInput.value || "1").trim() : "1";
    var requiredPairs = requiredPairCountForValueGroup(valueGroupToken);
    if (parseNonNegativeInt(valueGroupToken, 1) === 0) {
      appendTargetEl.textContent =
        "Appending to layer " +
        (layerToken || "1") +
        ", value group " +
        (valueGroupToken || "0") +
        ". Provide one or more references; the datum magnitude stores the selection reference list.";
      return;
    }

    appendTargetEl.textContent =
      "Appending to layer " +
      (layerToken || "1") +
      ", value group " +
      (valueGroupToken || "1") +
      ". Requires at least " +
      String(requiredPairs) +
      " reference/magnitude pair" +
      (requiredPairs === 1 ? "" : "s") +
      ".";
  }

  function syncAppendPairRequirements() {
    var requiredPairs = requiredPairCountForValueGroup(
      appendValueGroupInput ? appendValueGroupInput.value : "1"
    );
    ensurePairRowsMin(appendPairsEl, "js-remove-append-pair", requiredPairs);
    syncPairRowMode(appendPairsEl, appendValueGroupInput ? appendValueGroupInput.value : "1");
    updateAppendTarget();
  }

  function extractDatumEntries(payload) {
    var out = [];

    function walk(value) {
      if (!value) return;
      if (Array.isArray(value)) {
        value.forEach(walk);
        return;
      }
      if (typeof value !== "object") return;

      var datumId = typeof value.datum_id === "string" ? value.datum_id.trim() : "";
      var labelText = typeof value.label_text === "string" ? value.label_text.trim() : "";
      var iconRelpath = typeof value.icon_relpath === "string" ? value.icon_relpath.trim() : "";
      var iconUrl = typeof value.icon_url === "string" ? value.icon_url.trim() : "";

      if (datumId) {
        out.push({
          datum_id: datumId,
          label_text: labelText || datumId,
          icon_relpath: iconRelpath,
          icon_url: iconUrl,
        });
      }

      Object.keys(value).forEach(function (key) { walk(value[key]); });
    }

    walk(payload);
    return out;
  }

  function renderDatumList(targetEl, entries) {
    targetEl.innerHTML = "";

    if (!entries.length) {
      var empty = document.createElement("p");
      empty.className = "data-tool__empty";
      empty.textContent = "No datum entries for this pane.";
      targetEl.appendChild(empty);
      return;
    }

    var list = document.createElement("div");
    list.className = "data-tool__datumList";

    entries.forEach(function (entry) {
      var row = document.createElement("div");
      row.className = "data-tool__datumRow";

      var openBtn = document.createElement("button");
      openBtn.type = "button";
      openBtn.className = "data-tool__iconButton js-open-datum-profile";
      openBtn.setAttribute("data-row-id", entry.datum_id);
      openBtn.setAttribute("title", "Open datum profile for " + entry.datum_id);

      if (entry.icon_url) {
        var image = document.createElement("img");
        image.src = entry.icon_url;
        image.alt = "";
        image.className = "datum-icon";
        openBtn.appendChild(image);
      } else {
        var placeholder = document.createElement("span");
        placeholder.className = "datum-icon datum-icon--placeholder";
        placeholder.textContent = "+";
        openBtn.appendChild(placeholder);
      }

      var textWrap = document.createElement("div");
      textWrap.className = "data-tool__datumText";

      var title = document.createElement("div");
      title.className = "data-tool__datumTitle";
      title.textContent = entry.label_text;

      var meta = document.createElement("div");
      meta.className = "data-tool__datumMeta";
      meta.innerHTML = "<code>" + escapeText(entry.datum_id) + "</code>";

      textWrap.appendChild(title);
      textWrap.appendChild(meta);

      row.appendChild(openBtn);
      row.appendChild(textWrap);
      list.appendChild(row);
    });

    targetEl.appendChild(list);
  }

  function renderPane(targetEl, paneVm) {
    if (!targetEl) return;

    var pane = paneVm && typeof paneVm === "object" ? paneVm : {};
    var payload = pane.payload && typeof pane.payload === "object" ? pane.payload : {};
    var entries = extractDatumEntries(payload);

    targetEl.innerHTML = "";

    var kindEl = document.createElement("div");
    kindEl.className = "data-tool__paneKind";
    kindEl.textContent = "kind: " + (pane.kind || "none");
    targetEl.appendChild(kindEl);

    var listWrap = document.createElement("div");
    listWrap.className = "data-tool__paneList";
    renderDatumList(listWrap, entries);
    targetEl.appendChild(listWrap);

    var details = document.createElement("details");
    details.className = "data-tool__raw";
    var summary = document.createElement("summary");
    summary.textContent = "Raw pane payload";
    var pre = document.createElement("pre");
    pre.textContent = JSON.stringify(payload, null, 2);
    details.appendChild(summary);
    details.appendChild(pre);
    targetEl.appendChild(details);
  }

  function renderNimmSummary(snapshot) {
    if (!nimmSummaryEl) return;
    var state = snapshot && snapshot.state ? snapshot.state : {};
    nimmSummaryEl.textContent = JSON.stringify(
      {
        focus_source: state.focus_source || "auto",
        focus_subject: state.focus_subject || "",
        mode: state.mode || "general",
        lens_context: state.lens_context || "default",
        aitas_context: state.aitas_context || {},
        selection: state.selection || {},
        staged_edits_count: Array.isArray(snapshot && snapshot.staged_edits) ? snapshot.staged_edits.length : 0,
        daemon_ports_count: Array.isArray(snapshot && snapshot.daemon_ports) ? snapshot.daemon_ports.length : 0,
      },
      null,
      2
    );
  }

  function render(snapshot) {
    var state = snapshot && snapshot.state ? snapshot.state : {};
    var modelMeta = snapshot && snapshot.model_meta ? snapshot.model_meta : {};
    var left = snapshot && snapshot.left_pane_vm ? snapshot.left_pane_vm : {};
    var right = snapshot && snapshot.right_pane_vm ? snapshot.right_pane_vm : {};

    if (stateEl) {
      stateEl.textContent = JSON.stringify(
        {
          focus_source: state.focus_source,
          focus_subject: state.focus_subject,
          mode: state.mode,
          lens_context: state.lens_context,
          aitas_context: state.aitas_context || {},
          selection: state.selection,
          staged_edits: snapshot.staged_edits || [],
          staged_presentation_edits: snapshot.staged_presentation_edits || { datum_icons: {} },
        },
        null,
        2
      );
    }

    if (modelMetaEl) {
      modelMetaEl.textContent = JSON.stringify(modelMeta, null, 2);
    }

    renderNimmSummary(snapshot);

    renderPane(leftPaneEl, left);
    renderPane(rightPaneEl, right);

    if (modeSel && state.mode) modeSel.value = state.mode;
    if (sourceSel && state.focus_source) sourceSel.value = state.focus_source;

    var selection = state.selection || {};
    if (tableInput && selection.table_id && !tableInput.value) tableInput.value = selection.table_id;
    if (rowInput && selection.row_id && !rowInput.value) rowInput.value = selection.row_id;
    if (fieldInput && selection.field_id && !fieldInput.value) fieldInput.value = selection.field_id;

    setMessages(snapshot.errors || [], snapshot.warnings || []);
  }

  function renderAnthologyTable(view) {
    if (!anthologyLayersEl) return;

    var table = view && view.table ? view.table : {};
    var layers = Array.isArray(view && view.layers) ? view.layers : [];
    var rowsForLookup = Array.isArray(view && view.rows) ? view.rows : [];
    var datumLookup = buildDatumLookup(rowsForLookup);
    anthologyUiState.rowByIdentifier = {};
    anthologyUiState.rowById = {};
    rowsForLookup.forEach(function (row) {
      var identifier = String(row && row.identifier ? row.identifier : "").trim();
      var rowId = String(row && row.row_id ? row.row_id : identifier).trim();
      if (identifier) anthologyUiState.rowByIdentifier[identifier] = row;
      if (rowId) anthologyUiState.rowById[rowId] = row;
    });

    anthologyLayersEl.innerHTML = "";
    if (anthologyStatusEl) {
      anthologyStatusEl.textContent = "Rows: " + String(table.row_count || 0);
    }

    if (!layers.length) {
      var empty = document.createElement("p");
      empty.className = "data-tool__empty";
      empty.textContent = "No anthology rows found.";
      anthologyLayersEl.appendChild(empty);
      return;
    }

    layers.forEach(function (layerBlock, layerIndex) {
      var layerToken = layerBlock.layer == null ? "unknown" : String(layerBlock.layer);
      var layerKey = layerStateKey(layerToken);
      var layerDetails = document.createElement("details");
      layerDetails.className = "data-tool__layerGroup";
      layerDetails.setAttribute("data-layer-key", layerKey);
      if (anthologyUiState.initialized && Object.prototype.hasOwnProperty.call(anthologyUiState.layerOpen, layerKey)) {
        layerDetails.open = !!anthologyUiState.layerOpen[layerKey];
      } else {
        layerDetails.open = layerIndex < 2;
      }
      layerDetails.addEventListener("toggle", function () {
        anthologyUiState.layerOpen[layerKey] = !!layerDetails.open;
      });

      var layerSummary = document.createElement("summary");
      layerSummary.textContent = "Layer " + layerToken + " (" + String(layerBlock.row_count || 0) + " rows)";
      layerDetails.appendChild(layerSummary);

      var valueWrap = document.createElement("div");
      valueWrap.className = "data-tool__valueGroups";

      var valueGroups = Array.isArray(layerBlock.value_groups) ? layerBlock.value_groups : [];
      var maxValueGroup = 0;
      valueGroups.forEach(function (groupBlock) {
        var groupToken = groupBlock.value_group == null ? "unknown" : String(groupBlock.value_group);
        var groupNumber = parseInt(groupToken, 10);
        if (!isNaN(groupNumber)) {
          maxValueGroup = Math.max(maxValueGroup, groupNumber);
        }

        var groupKey = valueGroupStateKey(layerToken, groupToken);
        var groupDetails = document.createElement("details");
        groupDetails.className = "data-tool__valueGroup";
        groupDetails.setAttribute("data-group-key", groupKey);
        if (anthologyUiState.initialized && Object.prototype.hasOwnProperty.call(anthologyUiState.valueGroupOpen, groupKey)) {
          groupDetails.open = !!anthologyUiState.valueGroupOpen[groupKey];
        } else {
          groupDetails.open = true;
        }
        groupDetails.addEventListener("toggle", function () {
          anthologyUiState.valueGroupOpen[groupKey] = !!groupDetails.open;
        });

        var groupSummary = document.createElement("summary");
        groupSummary.textContent = "Value Group " + groupToken + " (" + String(groupBlock.row_count || 0) + " rows)";
        groupDetails.appendChild(groupSummary);

        var tableWrap = document.createElement("div");
        tableWrap.className = "data-tool__tableWrap";

        var dataTable = document.createElement("table");
        dataTable.className = "data-tool__table";

        var thead = document.createElement("thead");
        thead.innerHTML = "<tr><th>iter</th><th>datum</th><th>pairs</th><th>actions</th></tr>";
        dataTable.appendChild(thead);

        var tbody = document.createElement("tbody");
        var rows = Array.isArray(groupBlock.rows) ? groupBlock.rows : [];

        rows.forEach(function (row) {
          var tr = document.createElement("tr");
          var parsed = parseDatumIdentifier(row.identifier);
          var rowToken = String(row.row_id || row.identifier || "");
          var rowPairs = normalizePairs(row.pairs, row.reference, row.magnitude);
          var rowValueGroup = parseNonNegativeInt(row.value_group, parsed && parsed.value_group != null ? parsed.value_group : 0);
          var selectionRefs = normalizeSelectionReferences(row.selection_references, row.magnitude);

          var iterationTd = document.createElement("td");
          iterationTd.textContent = parsed && parsed.iteration != null ? String(parsed.iteration) : "";
          tr.appendChild(iterationTd);

          var datumTd = document.createElement("td");
          var datumCell = document.createElement("div");
          datumCell.className = "data-tool__datumCell";

          var icon = document.createElement("span");
          icon.className = "data-tool__datumIcon";
          if (row.icon_url) {
            var iconImg = document.createElement("img");
            iconImg.src = String(row.icon_url);
            iconImg.alt = "";
            iconImg.className = "datum-icon";
            icon.appendChild(iconImg);
          } else {
            var iconPlaceholder = document.createElement("span");
            iconPlaceholder.className = "datum-icon datum-icon--placeholder";
            iconPlaceholder.textContent = "+";
            icon.appendChild(iconPlaceholder);
          }

          var datumMain = document.createElement("div");
          datumMain.className = "data-tool__datumMain";

          var datumName = document.createElement("div");
          datumName.className = "data-tool__datumName data-tool__clip";
          datumName.textContent = String(row.label || row.identifier || "");
          datumName.title = String(row.label || row.identifier || "");

          var datumId = document.createElement("div");
          datumId.className = "data-tool__datumId data-tool__clip";
          datumId.textContent = String(row.identifier || "");
          datumId.title = String(row.identifier || "");

          datumMain.appendChild(datumName);
          datumMain.appendChild(datumId);

          datumCell.appendChild(icon);
          datumCell.appendChild(datumMain);
          datumTd.appendChild(datumCell);
          tr.appendChild(datumTd);

          var pairsTd = document.createElement("td");
          var pairCards = document.createElement("div");
          pairCards.className = "data-tool__pairCards";
          if (rowValueGroup === 0) {
            if (!selectionRefs.length) {
              var emptySelections = document.createElement("span");
              emptySelections.className = "data-tool__statusText";
              emptySelections.textContent = "No selection references";
              pairCards.appendChild(emptySelections);
            } else {
              selectionRefs.forEach(function (reference) {
                pairCards.appendChild(createPairCard({ reference: reference, magnitude: "selection" }, datumLookup));
              });
            }
          } else {
            if (!rowPairs.length) {
              var emptyPairs = document.createElement("span");
              emptyPairs.className = "data-tool__statusText";
              emptyPairs.textContent = "No pairs";
              pairCards.appendChild(emptyPairs);
            } else {
              rowPairs.forEach(function (pair) {
                pairCards.appendChild(createPairCard(pair, datumLookup));
              });
            }
          }
          pairsTd.appendChild(pairCards);
          tr.appendChild(pairsTd);

          var actionsTd = document.createElement("td");
          var editBtn = document.createElement("button");
          editBtn.type = "button";
          editBtn.className = "data-tool__actionBtn js-open-datum-profile";
          editBtn.setAttribute("data-row-id", rowToken);
          editBtn.textContent = "Edit";

          var deleteBtn = document.createElement("button");
          deleteBtn.type = "button";
          deleteBtn.className = "data-tool__actionBtn data-tool__actionBtn--danger js-delete-datum";
          deleteBtn.setAttribute("data-row-id", rowToken);
          deleteBtn.textContent = "Delete";

          actionsTd.appendChild(editBtn);
          actionsTd.appendChild(deleteBtn);
          tr.appendChild(actionsTd);

          tbody.appendChild(tr);
        });

        dataTable.appendChild(tbody);
        tableWrap.appendChild(dataTable);
        groupDetails.appendChild(tableWrap);

        var groupActions = document.createElement("div");
        groupActions.className = "data-tool__valueGroupActions";
        var appendBtn = document.createElement("button");
        appendBtn.type = "button";
        appendBtn.className = "data-tool__actionBtn js-open-append-modal";
        appendBtn.setAttribute("data-layer", layerToken);
        appendBtn.setAttribute("data-value-group", groupToken);
        appendBtn.textContent = "+ Append datum";
        groupActions.appendChild(appendBtn);
        groupDetails.appendChild(groupActions);

        valueWrap.appendChild(groupDetails);
      });

      layerDetails.appendChild(valueWrap);

      var layerActions = document.createElement("div");
      layerActions.className = "data-tool__layerActions";
      var appendValueGroupBtn = document.createElement("button");
      appendValueGroupBtn.type = "button";
      appendValueGroupBtn.className = "data-tool__actionBtn js-open-append-value-group";
      appendValueGroupBtn.setAttribute("data-layer", layerToken);
      appendValueGroupBtn.setAttribute("data-next-value-group", String(maxValueGroup + 1));
      appendValueGroupBtn.textContent = "+ Append value group";
      layerActions.appendChild(appendValueGroupBtn);
      layerDetails.appendChild(layerActions);

      anthologyLayersEl.appendChild(layerDetails);
    });

    captureAnthologyOpenState();
  }

  function renderAnthologyGraph(payload) {
    if (!anthologyGraphEl) return;
    var graph = payload && typeof payload === "object" ? payload : {};
    var nodes = Array.isArray(graph.nodes) ? graph.nodes : [];
    var edges = Array.isArray(graph.edges) ? graph.edges : [];
    var stats = graph.stats && typeof graph.stats === "object" ? graph.stats : {};
    var layers = Array.isArray(graph.layers) ? graph.layers : [];

    anthologyUiState.graphByIdentifier = {};
    nodes.forEach(function (node) {
      var identifier = String(node && node.identifier ? node.identifier : "").trim();
      if (!identifier) return;
      anthologyUiState.graphByIdentifier[identifier] = node;
    });

    if (anthologyGraphStatusEl) {
      anthologyGraphStatusEl.textContent =
        "Nodes: " + String(stats.node_count != null ? stats.node_count : nodes.length) +
        " | Edges: " + String(stats.edge_count != null ? stats.edge_count : edges.length) +
        " | Unresolved: " + String(stats.unresolved_edge_count != null ? stats.unresolved_edge_count : 0);
    }

    anthologyGraphEl.innerHTML = "";
    if (!nodes.length) {
      var empty = document.createElement("p");
      empty.className = "data-tool__empty";
      empty.textContent = "No anthology graph nodes.";
      anthologyGraphEl.appendChild(empty);
      return;
    }

    var fallbackByLayer = {};
    if (layers.length) {
      layers.forEach(function (layerBlock) {
        if (!layerBlock || typeof layerBlock !== "object") return;
        var layerToken = String(layerBlock.layer == null ? "unknown" : layerBlock.layer).trim() || "unknown";
        var layerNodes = Array.isArray(layerBlock.nodes) ? layerBlock.nodes : [];
        fallbackByLayer[layerToken] = layerNodes.filter(function (node) {
          return node && typeof node === "object";
        });
      });
    }
    if (!Object.keys(fallbackByLayer).length) {
      nodes.forEach(function (node) {
        var layerToken = String(node && node.layer != null ? node.layer : "unknown").trim() || "unknown";
        if (!fallbackByLayer[layerToken]) fallbackByLayer[layerToken] = [];
        fallbackByLayer[layerToken].push(node);
      });
    }

    var orderedLayers = Object.keys(fallbackByLayer).sort(function (a, b) {
      var ai = parseInt(a, 10);
      var bi = parseInt(b, 10);
      if (!isNaN(ai) && !isNaN(bi)) return ai - bi;
      if (!isNaN(ai)) return -1;
      if (!isNaN(bi)) return 1;
      return a.localeCompare(b);
    });

    var maxLayerNodes = 1;
    orderedLayers.forEach(function (layerToken) {
      var count = Array.isArray(fallbackByLayer[layerToken]) ? fallbackByLayer[layerToken].length : 0;
      if (count > maxLayerNodes) maxLayerNodes = count;
    });

    var layerCount = Math.max(orderedLayers.length, 1);
    var graphWidth = Math.max(920, layerCount * 220);
    var graphHeight = Math.max(560, Math.min(2400, maxLayerNodes * 6 + 180));
    var margin = { top: 56, right: 48, bottom: 54, left: 48 };
    var usableWidth = Math.max(240, graphWidth - margin.left - margin.right);
    var usableHeight = Math.max(240, graphHeight - margin.top - margin.bottom);

    var colorPalette = ["#1f6f43", "#2364aa", "#b26d00", "#8f2f6b", "#0f766e", "#92400e", "#374151"];

    function layerColor(layerToken, index) {
      var parsed = parseInt(layerToken, 10);
      if (!isNaN(parsed)) return colorPalette[Math.abs(parsed) % colorPalette.length];
      return colorPalette[index % colorPalette.length];
    }

    function nodeSortKey(node) {
      if (!node || typeof node !== "object") return "999-999-999";
      var vg = parseInt(node.value_group, 10);
      var it = parseInt(node.iteration, 10);
      var identifier = String(node.identifier || "").trim();
      return (
        String(isNaN(vg) ? 999 : vg).padStart(4, "0") +
        "-" +
        String(isNaN(it) ? 999999 : it).padStart(8, "0") +
        "-" +
        identifier
      );
    }

    var svgNs = "http://www.w3.org/2000/svg";
    var viewport = document.createElement("div");
    viewport.className = "data-tool__graphViewport";
    var svg = document.createElementNS(svgNs, "svg");
    svg.setAttribute("class", "data-tool__graphSvg");
    svg.setAttribute("viewBox", "0 0 " + String(graphWidth) + " " + String(graphHeight));
    svg.setAttribute("preserveAspectRatio", "xMinYMin meet");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Anthology node graph");

    var guidesGroup = document.createElementNS(svgNs, "g");
    guidesGroup.setAttribute("class", "data-tool__graphGuides");
    var edgesGroup = document.createElementNS(svgNs, "g");
    edgesGroup.setAttribute("class", "data-tool__graphEdges");
    var nodesGroup = document.createElementNS(svgNs, "g");
    nodesGroup.setAttribute("class", "data-tool__graphNodes");

    var nodePositions = {};
    orderedLayers.forEach(function (layerToken, layerIndex) {
      var layerNodes = Array.isArray(fallbackByLayer[layerToken]) ? fallbackByLayer[layerToken].slice() : [];
      layerNodes.sort(function (a, b) {
        return nodeSortKey(a).localeCompare(nodeSortKey(b));
      });
      if (!layerNodes.length) return;

      var x =
        margin.left +
        (layerCount === 1 ? usableWidth / 2 : (layerIndex / Math.max(layerCount - 1, 1)) * usableWidth);

      var lane = document.createElementNS(svgNs, "line");
      lane.setAttribute("x1", String(x));
      lane.setAttribute("y1", String(margin.top - 18));
      lane.setAttribute("x2", String(x));
      lane.setAttribute("y2", String(graphHeight - margin.bottom + 14));
      lane.setAttribute("class", "data-tool__graphLayerLane");
      guidesGroup.appendChild(lane);

      var layerLabel = document.createElementNS(svgNs, "text");
      layerLabel.setAttribute("x", String(x));
      layerLabel.setAttribute("y", String(margin.top - 28));
      layerLabel.setAttribute("text-anchor", "middle");
      layerLabel.setAttribute("class", "data-tool__graphLayerLabel");
      layerLabel.textContent = "L" + layerToken;
      guidesGroup.appendChild(layerLabel);

      layerNodes.forEach(function (node, nodeIndex) {
        var identifier = String(node && node.identifier ? node.identifier : "").trim();
        if (!identifier) return;
        var rowId = String(node && node.row_id ? node.row_id : identifier).trim();
        var y = margin.top + ((nodeIndex + 1) / (layerNodes.length + 1)) * usableHeight;
        nodePositions[identifier] = { x: x, y: y };

        var nodeGroup = document.createElementNS(svgNs, "g");
        nodeGroup.setAttribute("class", "data-tool__graphNodeGroup js-anthology-graph-node");
        nodeGroup.setAttribute("data-identifier", identifier);
        nodeGroup.setAttribute("data-row-id", rowId);

        var dot = document.createElementNS(svgNs, "circle");
        dot.setAttribute("cx", String(x));
        dot.setAttribute("cy", String(y));
        dot.setAttribute("r", "4");
        dot.setAttribute("class", "data-tool__graphNode js-anthology-graph-node");
        dot.setAttribute("data-identifier", identifier);
        dot.setAttribute("data-row-id", rowId);
        dot.setAttribute("fill", layerColor(layerToken, layerIndex));

        var title = document.createElementNS(svgNs, "title");
        var label = String(node && node.label ? node.label : identifier).trim() || identifier;
        title.textContent = label + " [" + identifier + "]";
        dot.appendChild(title);

        nodeGroup.appendChild(dot);
        nodesGroup.appendChild(nodeGroup);
      });
    });

    var maxRenderedEdges = 3500;
    var renderedEdges = 0;
    edges.forEach(function (edge) {
      if (renderedEdges >= maxRenderedEdges) return;
      var source = String(edge && edge.source ? edge.source : "").trim();
      var target = String(edge && edge.target ? edge.target : "").trim();
      if (!source || !target) return;
      var start = nodePositions[source];
      var end = nodePositions[target];
      if (!start || !end) return;

      var segment = document.createElementNS(svgNs, "line");
      segment.setAttribute("x1", String(start.x));
      segment.setAttribute("y1", String(start.y));
      segment.setAttribute("x2", String(end.x));
      segment.setAttribute("y2", String(end.y));
      segment.setAttribute("class", "data-tool__graphEdge" + (edge && edge.resolved === false ? " is-unresolved" : ""));
      edgesGroup.appendChild(segment);
      renderedEdges += 1;
    });

    svg.appendChild(guidesGroup);
    svg.appendChild(edgesGroup);
    svg.appendChild(nodesGroup);
    viewport.appendChild(svg);
    anthologyGraphEl.appendChild(viewport);

    var legend = document.createElement("div");
    legend.className = "data-tool__graphLegend";
    orderedLayers.forEach(function (layerToken, layerIndex) {
      var chip = document.createElement("span");
      chip.className = "data-tool__graphLegendChip";
      chip.style.borderColor = layerColor(layerToken, layerIndex);
      var layerNodes = Array.isArray(fallbackByLayer[layerToken]) ? fallbackByLayer[layerToken] : [];
      chip.textContent = "L" + layerToken + ": " + String(layerNodes.length);
      legend.appendChild(chip);
    });
    if (edges.length > maxRenderedEdges) {
      var overflow = document.createElement("span");
      overflow.className = "data-tool__statusText";
      overflow.textContent = "Edge rendering capped at " + String(maxRenderedEdges) + " for responsiveness.";
      legend.appendChild(overflow);
    }
    anthologyGraphEl.appendChild(legend);
  }

  async function api(path, options) {
    var res = await fetch(path, options || {});
    var payload = {};
    try {
      payload = await res.json();
    } catch (_) {
      payload = {};
    }
    if (!res.ok) {
      throw new Error(payload.description || payload.message || "Request failed");
    }
    return payload;
  }

  async function getState() {
    var payload = await api("/portal/api/data/state");
    render(payload);
    return payload;
  }

  async function getAnthologyTable() {
    captureAnthologyOpenState();
    var payload = await api("/portal/api/data/anthology/table");
    renderAnthologyTable(payload);
    var graphWarnings = [];
    try {
      await getAnthologyGraph();
    } catch (err) {
      var warn = err && err.message ? err.message : "Failed to load anthology graph";
      graphWarnings.push(warn);
    }
    setMessages(payload.errors || [], (payload.warnings || []).concat(graphWarnings));
    return payload;
  }

  async function getAnthologyGraph() {
    if (!anthologyGraphEl) return {};
    var payload = await api("/portal/api/data/anthology/graph");
    renderAnthologyGraph(payload);
    return payload;
  }

  async function appendAnthologyDatum() {
    var valueGroupToken = appendValueGroupInput ? String(appendValueGroupInput.value || "").trim() : "";
    var pairs = readPairRowsForValueGroup(appendPairsEl, valueGroupToken || "1");
    var requiredPairs = requiredPairCountForValueGroup(valueGroupToken || "1");
    if (pairs.length < requiredPairs) {
      throw new Error(
        "value_group=" +
          String(valueGroupToken || "1") +
          " requires at least " +
          String(requiredPairs) +
          " reference/magnitude pair" +
          (requiredPairs === 1 ? "" : "s") +
          "."
      );
    }

    captureAnthologyOpenState();
    var payload = await api("/portal/api/data/anthology/append", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        layer: appendLayerInput ? appendLayerInput.value : "",
        value_group: appendValueGroupInput ? appendValueGroupInput.value : "",
        label: appendLabelInput ? appendLabelInput.value : "",
        pairs: pairs,
      }),
    });

    if (payload.table_view) {
      renderAnthologyTable(payload.table_view);
      await getAnthologyGraph();
    } else {
      await getAnthologyTable();
    }

    if (payload.created_count) closeAppendModal();
    if (appendLabelInput) appendLabelInput.value = "";
    resetPairRows(appendPairsEl, "js-remove-append-pair", []);
    syncAppendPairRequirements();

    setMessages(payload.errors || [], payload.warnings || []);
    return payload;
  }

  async function deleteAnthologyDatum(rowToken) {
    var token = String(rowToken || "").trim();
    if (!token) {
      throw new Error("row_id is required");
    }

    captureAnthologyOpenState();
    var payload = await api("/portal/api/data/anthology/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ row_id: token }),
    });

    if (payload.table_view) {
      renderAnthologyTable(payload.table_view);
      await getAnthologyGraph();
    } else {
      await getAnthologyTable();
    }

    setMessages(payload.errors || [], payload.warnings || []);
    return payload;
  }

  async function getTimeSeriesState() {
    var payload = await api("/portal/api/data/time_series/state");
    var events = Array.isArray(payload.events) ? payload.events : [];
    var tables = Array.isArray(payload.event_enabled_tables) ? payload.event_enabled_tables : [];
    timeSeriesUiState.events = events;
    timeSeriesUiState.eventEnabledTables = tables;
    renderTimeSeriesEventList(events);
    renderTimeSeriesTableOptions(tables);

    if (tsStatusEl) {
      tsStatusEl.textContent =
        "Events: " +
        String(events.length) +
        " | index: " +
        String(payload.anchor_internal || "4-0-1");
    }

    var hasSelected = false;
    if (timeSeriesUiState.selectedEventRef) {
      hasSelected = events.some(function (item) {
        return String(item && item.event_ref ? item.event_ref : "").trim() === timeSeriesUiState.selectedEventRef;
      });
    }
    if (hasSelected) {
      await inspectTimeSeriesEvent(timeSeriesUiState.selectedEventRef);
    } else {
      renderTimeSeriesEventDetail(null);
    }

    setMessages(payload.errors || [], payload.warnings || []);
    return payload;
  }

  async function ensureTimeSeriesBase() {
    var payload = await api("/portal/api/data/time_series/ensure_base", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    await getTimeSeriesState();
    setMessages(payload.errors || [], payload.warnings || []);
    return payload;
  }

  async function createTimeSeriesEvent() {
    var startToken = parseNonNegativeInt(tsStartInput ? tsStartInput.value : "", -1);
    var durationToken = parsePositiveInt(tsDurationInput ? tsDurationInput.value : "", -1);
    if (startToken < 0) throw new Error("start_unix_s must be >= 0");
    if (durationToken < 1) throw new Error("duration_s must be >= 1");

    var payload = await api("/portal/api/data/time_series/event/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        point_ref: tsPointRefInput ? tsPointRefInput.value : "",
        duration_ref: tsDurationRefInput ? tsDurationRefInput.value : "",
        start_unix_s: startToken,
        duration_s: durationToken,
        label: tsLabelInput ? tsLabelInput.value : "",
      }),
    });

    var eventRef = String(payload && payload.event && payload.event.event_ref ? payload.event.event_ref : "").trim();
    timeSeriesUiState.selectedEventRef = eventRef;
    if (tsLabelInput) tsLabelInput.value = "";
    await getTimeSeriesState();
    if (eventRef) await inspectTimeSeriesEvent(eventRef);
    setMessages(payload.errors || [], payload.warnings || []);
    return payload;
  }

  async function updateTimeSeriesEvent(eventRef, values) {
    var payload = await api("/portal/api/data/time_series/event/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event_ref: eventRef,
        point_ref: values.point_ref,
        duration_ref: values.duration_ref,
        start_unix_s: values.start_unix_s,
        duration_s: values.duration_s,
        label: values.label,
      }),
    });
    timeSeriesUiState.selectedEventRef = eventRef;
    await getTimeSeriesState();
    await inspectTimeSeriesEvent(eventRef);
    setMessages(payload.errors || [], payload.warnings || []);
    return payload;
  }

  async function deleteTimeSeriesEvent(eventRef) {
    var token = String(eventRef || "").trim();
    if (!token) throw new Error("event_ref is required");
    var payload = await api("/portal/api/data/time_series/event/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event_ref: token }),
    });
    if (timeSeriesUiState.selectedEventRef === token) {
      timeSeriesUiState.selectedEventRef = "";
    }
    await getTimeSeriesState();
    setMessages(payload.errors || [], payload.warnings || []);
    return payload;
  }

  async function inspectTimeSeriesEvent(eventRef) {
    var token = String(eventRef || "").trim();
    if (!token) {
      renderTimeSeriesEventDetail(null);
      return null;
    }
    var payload = await api("/portal/api/data/time_series/event/" + encodeURIComponent(token));
    timeSeriesUiState.selectedEventRef = String(payload && payload.event && payload.event.event_ref ? payload.event.event_ref : token).trim();
    renderTimeSeriesEventDetail(payload);
    setMessages(payload.errors || [], payload.warnings || []);
    return payload;
  }

  async function loadTimeSeriesTableView() {
    var tableId = String(tsTableSelect ? tsTableSelect.value : "").trim();
    if (!tableId) throw new Error("Select an event-enabled table first");
    var mode = String(tsTableModeSelect ? tsTableModeSelect.value : "normal").trim() || "normal";
    var payload = await api(
      "/portal/api/data/time_series/table/" + encodeURIComponent(tableId) + "/view?mode=" + encodeURIComponent(mode)
    );
    if (tsTableOutputEl) {
      tsTableOutputEl.textContent = JSON.stringify(payload, null, 2);
    }
    setMessages(payload.errors || [], payload.warnings || []);
    return payload;
  }

  function closeAppendModal() {
    if (!appendModal) return;
    appendModal.hidden = true;
    appendModal.setAttribute("aria-hidden", "true");
    appendModal.style.display = "none";
    updateBodyModalState();
  }

  function openAppendModal(layerToken, valueGroupToken) {
    if (!appendModal) return;
    resetPairRows(appendPairsEl, "js-remove-append-pair", []);
    if (appendLayerInput) appendLayerInput.value = String(layerToken || "1");
    if (appendValueGroupInput) appendValueGroupInput.value = String(valueGroupToken || "1");
    if (appendLabelInput) appendLabelInput.value = "";
    syncAppendPairRequirements();
    appendModal.hidden = false;
    appendModal.setAttribute("aria-hidden", "false");
    appendModal.style.display = "grid";
    updateBodyModalState();
  }

  async function postDirective(action, subject, method, args) {
    var payload = await api("/portal/api/data/directive", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: action, subject: subject, method: method, args: args || {} }),
    });
    render(payload);
    return payload;
  }

  async function stageEdit() {
    var payload = await api("/portal/api/data/stage_edit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        table_id: tableInput ? tableInput.value : "",
        row_id: rowInput ? rowInput.value : "",
        field_id: fieldInput ? fieldInput.value : "",
        display_value: valueInput ? valueInput.value : "",
      }),
    });
    render(payload);
    return payload;
  }

  async function resetStaging() {
    var payload = await api("/portal/api/data/reset_staging", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scope: scopeSel ? scopeSel.value : "all",
        table_id: tableInput ? tableInput.value : "",
        row_id: rowInput ? rowInput.value : "",
      }),
    });
    render(payload);
    return payload;
  }

  async function commit() {
    var payload = await api("/portal/api/data/commit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scope: scopeSel ? scopeSel.value : "all",
        table_id: tableInput ? tableInput.value : "",
        row_id: rowInput ? rowInput.value : "",
      }),
    });
    render(payload);
    return payload;
  }

  function normalizeIconToken(value) {
    var token = String(value || "").trim().replace(/\\/g, "/");
    token = token.replace(/^\/+/, "");
    if (token.indexOf("assets/icons/") === 0) token = token.slice("assets/icons/".length);
    if (iconRelpathMode === "basename") {
      var parts = token.split("/");
      token = parts[parts.length - 1] || token;
    }
    return token;
  }

  async function loadIconCatalog() {
    if (iconCatalogLoaded) return iconCatalog;
    var payload = await api("/portal/api/data/icons/list");
    iconCatalog = Array.isArray(payload.icon_relpaths) ? payload.icon_relpaths : [];
    iconRelpathMode = String(payload.icon_relpath_mode || "path");
    iconCatalogLoaded = true;
    return iconCatalog;
  }

  function switchProfileTab(tabName) {
    profileTabButtons.forEach(function (btn) {
      var active = btn.getAttribute("data-profile-tab") === tabName;
      btn.classList.toggle("is-active", active);
    });
    profilePanels.forEach(function (panel) {
      var active = panel.getAttribute("data-profile-panel") === tabName;
      panel.classList.toggle("is-active", active);
    });
  }

  function updateProfileIconPreview() {
    if (!profileIconCurrentEl) return;
    profileIconCurrentEl.innerHTML = "";

    var wrap = document.createElement("div");
    wrap.className = "data-tool__datumCell";

    var icon = document.createElement("span");
    icon.className = "data-tool__datumIcon";
    var token = normalizeIconToken(currentProfileIconRelpath);

    if (token) {
      var img = document.createElement("img");
      img.src = "/portal/static/icons/" + token;
      img.alt = "";
      img.className = "datum-icon";
      icon.appendChild(img);
    } else {
      var placeholder = document.createElement("span");
      placeholder.className = "datum-icon datum-icon--placeholder";
      placeholder.textContent = "+";
      icon.appendChild(placeholder);
    }

    var text = document.createElement("div");
    text.className = "data-tool__datumMain";

    var name = document.createElement("div");
    name.className = "data-tool__datumName";
    name.textContent = token || "No icon selected";

    text.appendChild(name);
    wrap.appendChild(icon);
    wrap.appendChild(text);
    profileIconCurrentEl.appendChild(wrap);
  }

  function renderProfileAbstraction(chain) {
    if (!profileAbstractionEl) return;
    profileAbstractionEl.innerHTML = "";

    var items = Array.isArray(chain) ? chain : [];
    if (!items.length) {
      var empty = document.createElement("p");
      empty.className = "data-tool__empty";
      empty.textContent = "No abstraction path found for this datum.";
      profileAbstractionEl.appendChild(empty);
      return;
    }

    var list = document.createElement("ol");
    list.className = "data-tool__pathList";

    items.forEach(function (item) {
      var li = document.createElement("li");
      li.className = "data-tool__pathItem";

      var head = document.createElement("div");
      head.className = "data-tool__datumCell";

      var icon = document.createElement("span");
      icon.className = "data-tool__datumIcon";
      if (item.icon_url) {
        var img = document.createElement("img");
        img.src = String(item.icon_url);
        img.alt = "";
        img.className = "datum-icon";
        icon.appendChild(img);
      } else {
        var placeholder = document.createElement("span");
        placeholder.className = "datum-icon datum-icon--placeholder";
        placeholder.textContent = "+";
        icon.appendChild(placeholder);
      }

      var main = document.createElement("div");
      main.className = "data-tool__datumMain";
      var title = document.createElement("div");
      title.className = "data-tool__datumName data-tool__clip";
      title.textContent = String(item.label || item.identifier || "");
      title.title = String(item.label || item.identifier || "");

      var meta = document.createElement("div");
      meta.className = "data-tool__datumId";
      meta.textContent = String(item.identifier || "") + " (L" + String(item.layer == null ? "?" : item.layer) + ")";

      main.appendChild(title);
      main.appendChild(meta);
      head.appendChild(icon);
      head.appendChild(main);
      li.appendChild(head);

      var ref = document.createElement("div");
      ref.className = "data-tool__pathRef";
      ref.textContent = "reference: " + String(item.reference || "(none)");
      ref.title = String(item.reference || "(none)");
      li.appendChild(ref);

      list.appendChild(li);
    });

    profileAbstractionEl.appendChild(list);
  }

  function renderProfileIconOptions() {
    if (!profileIconListEl) return;
    var filter = profileIconSearchInput ? profileIconSearchInput.value.trim().toLowerCase() : "";
    var current = normalizeIconToken(currentProfileIconRelpath);

    profileIconListEl.innerHTML = "";

    var filtered = iconCatalog.filter(function (rel) {
      if (!filter) return true;
      return String(rel).toLowerCase().indexOf(filter) !== -1;
    });

    if (!filtered.length) {
      var empty = document.createElement("p");
      empty.className = "data-tool__empty";
      empty.textContent = "No icons match current filter.";
      profileIconListEl.appendChild(empty);
      return;
    }

    filtered.forEach(function (rel) {
      var relToken = String(rel || "");
      var relNorm = normalizeIconToken(relToken);

      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "data-tool__iconOption";
      if (relNorm && relNorm === current) btn.classList.add("is-selected");
      btn.setAttribute("data-icon-relpath", relToken);

      var img = document.createElement("img");
      img.src = "/portal/static/icons/" + relToken;
      img.alt = "";
      img.className = "datum-icon";

      var textWrap = document.createElement("span");
      textWrap.className = "data-tool__iconOptionText";

      var name = document.createElement("strong");
      name.textContent = relToken.split("/").pop() || relToken;
      textWrap.appendChild(name);

      var meta = document.createElement("small");
      meta.className = "data-tool__iconOptionMeta";
      meta.textContent = iconRelpathMode === "basename" ? ("stored as " + (relToken.split("/").pop() || relToken)) : relToken;
      textWrap.appendChild(meta);

      btn.appendChild(img);
      btn.appendChild(textWrap);
      profileIconListEl.appendChild(btn);
    });
  }

  function closeProfileModal() {
    if (!profileModal) return;
    profileModal.hidden = true;
    profileModal.setAttribute("aria-hidden", "true");
    profileModal.style.display = "none";
    updateBodyModalState();
  }

  async function openProfileModal(rowToken) {
    var token = String(rowToken || "").trim();
    if (!token) return;

    var payload = await api("/portal/api/data/anthology/profile/" + encodeURIComponent(token));
    var datum = payload.datum || {};

    currentProfileRowId = String(datum.row_id || datum.identifier || token);
    currentProfileIdentifier = String(datum.identifier || currentProfileRowId);
    currentProfileIconRelpath = String(datum.icon_relpath || "");
    var parsedIdentifier = parseDatumIdentifier(currentProfileIdentifier);
    currentProfileValueGroup = parsedIdentifier && parsedIdentifier.value_group != null ? parsedIdentifier.value_group : 1;

    if (profileTitleEl) profileTitleEl.textContent = "Datum " + currentProfileIdentifier;
    if (profileTargetEl) profileTargetEl.innerHTML = "Editing <code>" + escapeText(currentProfileRowId) + "</code>";
    if (profileIdentifierEl) profileIdentifierEl.textContent = currentProfileIdentifier;
    if (profileLabelInput) profileLabelInput.value = String(datum.label || currentProfileIdentifier);

    var pairs = normalizePairs(datum.pairs, datum.reference, datum.magnitude);
    resetPairRows(profilePairsEl, "js-remove-profile-pair", pairs);
    syncPairRowMode(profilePairsEl, currentProfileValueGroup);

    renderProfileAbstraction(payload.abstraction_path || []);
    updateProfileIconPreview();

    if (!iconCatalogLoaded) {
      try { await loadIconCatalog(); } catch (_) {}
    }
    renderProfileIconOptions();
    switchProfileTab("details");

    profileModal.hidden = false;
    profileModal.setAttribute("aria-hidden", "false");
    profileModal.style.display = "grid";
    updateBodyModalState();
  }

  async function openInvestigationInspector(rowToken) {
    var token = String(rowToken || "").trim();
    if (!token) return;

    if (!window.PortalInspector || typeof window.PortalInspector.open !== "function") {
      await openProfileModal(token);
      return;
    }

    var payload = await api("/portal/api/data/anthology/profile/" + encodeURIComponent(token));
    var datum = payload.datum || {};
    var rowId = String(datum.row_id || datum.identifier || token);
    var identifier = String(datum.identifier || rowId || token);
    var label = String(datum.label || identifier);
    var pairs = normalizePairs(datum.pairs, datum.reference, datum.magnitude);
    var abstractionPath = Array.isArray(payload.abstraction_path) ? payload.abstraction_path : [];

    var pairsMarkup = pairs.length
      ? "<ul>" + pairs.map(function (pair) {
          return "<li><code>" + escapeText(pair.reference || "") + "</code> -> <code>" + escapeText(pair.magnitude || "") + "</code></li>";
        }).join("") + "</ul>"
      : "<p>No reference/magnitude pairs.</p>";

    var pathMarkup = abstractionPath.length
      ? "<ol>" + abstractionPath.map(function (item) {
          return "<li><code>" + escapeText(item.identifier || "") + "</code> " + escapeText(item.label || "") + "</li>";
        }).join("") + "</ol>"
      : "<p>No abstraction path available.</p>";

    window.PortalInspector.open({
      title: "Datum Investigation",
      subtitle: identifier,
      html:
        "<article class=\"card\">" +
          "<div class=\"card__kicker\">Investigation</div>" +
          "<div class=\"card__title\">" + escapeText(label) + "</div>" +
          "<div class=\"card__body\">" +
            "<p><strong>row_id:</strong> <code>" + escapeText(rowId) + "</code></p>" +
            "<p><strong>identifier:</strong> <code>" + escapeText(identifier) + "</code></p>" +
            "<h4>Reference / Magnitude</h4>" +
            pairsMarkup +
            "<h4>Abstraction Path</h4>" +
            pathMarkup +
            "<p><button type=\"button\" class=\"js-inspector-open-profile\" data-row-id=\"" + escapeText(rowId) + "\">Open Full Datum Editor</button></p>" +
          "</div>" +
        "</article>",
    });
  }

  async function saveProfileChanges() {
    if (!currentProfileRowId) return;
    var labelValue = profileLabelInput ? profileLabelInput.value : "";
    var pairs = readPairRowsForValueGroup(profilePairsEl, currentProfileValueGroup);

    captureAnthologyOpenState();
    var payload = await api("/portal/api/data/anthology/profile/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        row_id: currentProfileRowId,
        label: String(labelValue || ""),
        pairs: pairs,
        icon_relpath: String(currentProfileIconRelpath || ""),
      }),
    });

    if (payload.table_view) {
      renderAnthologyTable(payload.table_view);
      await getAnthologyGraph();
    } else {
      await getAnthologyTable();
    }

    var updated = payload.updated || {};
    if (updated && profileLabelInput) {
      profileLabelInput.value = String(updated.label || "");
    }
    if (updated) {
      resetPairRows(profilePairsEl, "js-remove-profile-pair", normalizePairs(updated.pairs, updated.reference, updated.magnitude));
      syncPairRowMode(profilePairsEl, currentProfileValueGroup);
    }

    setMessages(payload.errors || [], payload.warnings || []);
  }

  async function applyQueryBootstrap() {
    var url = new URL(window.location.href);
    var source = (url.searchParams.get("source") || "").trim().toLowerCase();
    var subject = (url.searchParams.get("subject") || "").trim();
    var invMethod = (url.searchParams.get("inv_method") || "summary").trim().toLowerCase();
    var mode = (url.searchParams.get("mode") || "").trim().toLowerCase();
    var lens = (url.searchParams.get("lens") || "").trim().toLowerCase();

    if (source && sourceSel) {
      sourceSel.value = source;
      await postDirective("nav", source, "top_level_view", {});
    }

    if (subject && subjectInput) {
      subjectInput.value = subject;
      if (invMethodSel && invMethod) invMethodSel.value = invMethod;
      await postDirective("inv", subject, invMethod || "summary", {});
    }

    if (mode && modeSel) {
      modeSel.value = mode;
      await postDirective("med", "state", "mode=" + mode, { mode: mode });
    }

    if (lens && lensSel) {
      lensSel.value = lens;
      await postDirective("med", "state", "lens=" + lens, { lens: lens });
    }
  }

  function onClickDatumAction(event) {
    var target = event.target;
    if (!target || !target.closest) return;

    var graphNodeBtn = target.closest(".js-anthology-graph-node");
    if (graphNodeBtn) {
      var graphIdentifier = String(graphNodeBtn.getAttribute("data-identifier") || "").trim();
      if (!graphIdentifier) return;
      if (subjectInput) subjectInput.value = graphIdentifier;
      if (invMethodSel) invMethodSel.value = "summary";
      postDirective("inv", graphIdentifier, "summary", {}).catch(function (err) {
        setMessages([err.message], []);
      });
      return;
    }

    var profileBtn = target.closest(".js-open-datum-profile");
    if (profileBtn) {
      var profileRowToken = profileBtn.getAttribute("data-row-id") || profileBtn.getAttribute("data-datum-id") || "";
      openProfileModal(profileRowToken).catch(function (err) {
        setMessages([err.message], []);
      });
      return;
    }

    var deleteBtn = target.closest(".js-delete-datum");
    if (deleteBtn) {
      var deleteRowToken = deleteBtn.getAttribute("data-row-id") || "";
      if (!window.confirm("Delete datum " + deleteRowToken + "?")) return;
      deleteAnthologyDatum(deleteRowToken).catch(function (err) {
        setMessages([err.message], []);
      });
      return;
    }

    var appendOpenBtn = target.closest(".js-open-append-modal");
    if (appendOpenBtn) {
      var layerToken = appendOpenBtn.getAttribute("data-layer") || "1";
      var groupToken = appendOpenBtn.getAttribute("data-value-group") || "1";
      openAppendModal(layerToken, groupToken);
      return;
    }

    var appendValueGroupBtn = target.closest(".js-open-append-value-group");
    if (appendValueGroupBtn) {
      var targetLayer = appendValueGroupBtn.getAttribute("data-layer") || "1";
      var nextValueGroup = appendValueGroupBtn.getAttribute("data-next-value-group") || "1";
      openAppendModal(targetLayer, nextValueGroup);
      return;
    }
  }

  if (leftPaneEl) leftPaneEl.addEventListener("click", onClickDatumAction);
  if (rightPaneEl) rightPaneEl.addEventListener("click", onClickDatumAction);
  if (anthologyLayersEl) anthologyLayersEl.addEventListener("click", onClickDatumAction);
  if (anthologyGraphEl) anthologyGraphEl.addEventListener("click", onClickDatumAction);
  if (anthologyGraphEl) {
    anthologyGraphEl.addEventListener("dblclick", function (event) {
      var target = event.target;
      if (!target || !target.closest) return;
      var graphNodeBtn = target.closest(".js-anthology-graph-node");
      if (!graphNodeBtn) return;
      var rowToken = String(graphNodeBtn.getAttribute("data-row-id") || "").trim();
      if (!rowToken) return;
      openInvestigationInspector(rowToken).catch(function (err) {
        setMessages([err.message], []);
      });
    });
  }

  document.addEventListener("click", function (event) {
    var inspectorBtn = event.target && event.target.closest ? event.target.closest(".js-inspector-open-profile") : null;
    if (!inspectorBtn) return;
    event.preventDefault();
    var rowToken = String(inspectorBtn.getAttribute("data-row-id") || "").trim();
    if (!rowToken) return;
    openProfileModal(rowToken).catch(function (err) {
      setMessages([err.message], []);
    });
  });

  if (profileCloseBtn) profileCloseBtn.addEventListener("click", closeProfileModal);
  qsa("[data-role='close-profile-modal']", profileModal).forEach(function (node) {
    node.addEventListener("click", closeProfileModal);
  });
  if (appendCloseBtn) appendCloseBtn.addEventListener("click", closeAppendModal);
  qsa("[data-role='close-append-modal']", appendModal).forEach(function (node) {
    node.addEventListener("click", closeAppendModal);
  });
  if (nimmOpenBtn) nimmOpenBtn.addEventListener("click", openNimmOverlay);
  if (nimmCloseBtn) nimmCloseBtn.addEventListener("click", closeNimmOverlay);
  qsa("[data-role='close-nimm-overlay']", nimmOverlay).forEach(function (node) {
    node.addEventListener("click", closeNimmOverlay);
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    if (isModalVisible(profileModal)) closeProfileModal();
    if (isModalVisible(appendModal)) closeAppendModal();
    if (isModalVisible(nimmOverlay)) closeNimmOverlay();
  });

  if (profileSaveBtn) {
    profileSaveBtn.addEventListener("click", function () {
      saveProfileChanges().catch(function (err) {
        setMessages([err.message], []);
      });
    });
  }

  profileTabButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var tab = btn.getAttribute("data-profile-tab") || "details";
      switchProfileTab(tab);
    });
  });

  if (profileIconSearchInput) {
    profileIconSearchInput.addEventListener("input", renderProfileIconOptions);
  }

  if (profileIconClearBtn) {
    profileIconClearBtn.addEventListener("click", function () {
      currentProfileIconRelpath = "";
      updateProfileIconPreview();
      renderProfileIconOptions();
    });
  }

  if (profileIconListEl) {
    profileIconListEl.addEventListener("click", function (event) {
      var btn = event.target && event.target.closest ? event.target.closest(".data-tool__iconOption") : null;
      if (!btn) return;
      currentProfileIconRelpath = btn.getAttribute("data-icon-relpath") || "";
      updateProfileIconPreview();
      renderProfileIconOptions();
    });
  }

  if (profilePairAddBtn) {
    profilePairAddBtn.addEventListener("click", function () {
      addPairRow(profilePairsEl, "", "", "js-remove-profile-pair");
      syncPairRowMode(profilePairsEl, currentProfileValueGroup);
    });
  }

  if (profilePairsEl) {
    profilePairsEl.addEventListener("click", function (event) {
      var removeBtn = event.target && event.target.closest ? event.target.closest(".js-remove-profile-pair") : null;
      if (!removeBtn) return;
      var row = removeBtn.closest(".data-tool__appendPairRow");
      if (!row) return;
      row.remove();
      ensurePairRows(profilePairsEl, "js-remove-profile-pair");
      syncPairRowMode(profilePairsEl, currentProfileValueGroup);
    });
  }

  if (navBtn) {
    navBtn.addEventListener("click", function () {
      postDirective("nav", sourceSel ? sourceSel.value : "auto", "top_level_view", {}).catch(function (err) {
        setMessages([err.message], []);
      });
    });
  }

  if (invBtn) {
    invBtn.addEventListener("click", function () {
      postDirective("inv", subjectInput ? subjectInput.value : "", invMethodSel ? invMethodSel.value : "summary", {}).catch(function (err) {
        setMessages([err.message], []);
      });
    });
  }

  if (modeBtn) {
    modeBtn.addEventListener("click", function () {
      var mode = modeSel ? modeSel.value : "general";
      postDirective("med", "state", "mode=" + mode, { mode: mode }).catch(function (err) {
        setMessages([err.message], []);
      });
    });
  }

  if (lensBtn) {
    lensBtn.addEventListener("click", function () {
      var lens = lensSel ? lensSel.value : "default";
      postDirective("med", "state", "lens=" + lens, { lens: lens }).catch(function (err) {
        setMessages([err.message], []);
      });
    });
  }

  if (stageBtn) {
    stageBtn.addEventListener("click", function () {
      stageEdit().catch(function (err) { setMessages([err.message], []); });
    });
  }

  if (resetBtn) {
    resetBtn.addEventListener("click", function () {
      resetStaging().catch(function (err) { setMessages([err.message], []); });
    });
  }

  if (commitBtn) {
    commitBtn.addEventListener("click", function () {
      commit().catch(function (err) { setMessages([err.message], []); });
    });
  }

  if (refreshBtn) {
    refreshBtn.addEventListener("click", function () {
      Promise.all([getState(), getAnthologyTable()]).catch(function (err) {
        setMessages([err.message], []);
      });
    });
  }

  if (anthologyRefreshBtn) {
    anthologyRefreshBtn.addEventListener("click", function () {
      getAnthologyTable().catch(function (err) { setMessages([err.message], []); });
    });
  }

  if (anthologyGraphRefreshBtn) {
    anthologyGraphRefreshBtn.addEventListener("click", function () {
      getAnthologyGraph().catch(function (err) { setMessages([err.message], []); });
    });
  }

  if (appendPairAddBtn) {
    appendPairAddBtn.addEventListener("click", function () {
      addPairRow(appendPairsEl, "", "", "js-remove-append-pair");
      syncAppendPairRequirements();
    });
  }

  if (appendPairsEl) {
    appendPairsEl.addEventListener("click", function (event) {
      var removeBtn = event.target && event.target.closest ? event.target.closest(".js-remove-append-pair") : null;
      if (!removeBtn) return;
      var row = removeBtn.closest(".data-tool__appendPairRow");
      if (!row) return;
      row.remove();
      syncAppendPairRequirements();
    });
  }

  if (appendSaveBtn) {
    appendSaveBtn.addEventListener("click", function () {
      appendAnthologyDatum().catch(function (err) { setMessages([err.message], []); });
    });
  }

  if (appendValueGroupInput) {
    appendValueGroupInput.addEventListener("input", function () {
      syncAppendPairRequirements();
    });
  }

  if (appendLayerInput) {
    appendLayerInput.addEventListener("input", function () {
      updateAppendTarget();
    });
  }

  if (tsEnsureBaseBtn) {
    tsEnsureBaseBtn.addEventListener("click", function () {
      ensureTimeSeriesBase().catch(function (err) { setMessages([err.message], []); });
    });
  }

  if (tsRefreshBtn) {
    tsRefreshBtn.addEventListener("click", function () {
      getTimeSeriesState().catch(function (err) { setMessages([err.message], []); });
    });
  }

  if (tsCreateBtn) {
    tsCreateBtn.addEventListener("click", function () {
      createTimeSeriesEvent().catch(function (err) { setMessages([err.message], []); });
    });
  }

  if (tsEventListEl) {
    tsEventListEl.addEventListener("click", function (event) {
      var target = event.target;
      if (!target || !target.closest) return;

      var inspectBtn = target.closest(".js-dtts-inspect");
      if (inspectBtn) {
        inspectTimeSeriesEvent(inspectBtn.getAttribute("data-event-ref") || "").catch(function (err) {
          setMessages([err.message], []);
        });
        return;
      }

      var editBtn = target.closest(".js-dtts-edit");
      if (editBtn) {
        inspectTimeSeriesEvent(editBtn.getAttribute("data-event-ref") || "").catch(function (err) {
          setMessages([err.message], []);
        });
        return;
      }

      var deleteBtn = target.closest(".js-dtts-delete");
      if (deleteBtn) {
        var token = deleteBtn.getAttribute("data-event-ref") || "";
        if (!window.confirm("Delete event " + token + "?")) return;
        deleteTimeSeriesEvent(token).catch(function (err) { setMessages([err.message], []); });
      }
    });
  }

  if (tsEventDetailEl) {
    tsEventDetailEl.addEventListener("click", function (event) {
      var target = event.target;
      if (!target || !target.closest) return;

      var saveBtn = target.closest(".js-dtts-detail-save");
      if (saveBtn) {
        var eventRefInput = qs("#dttsDetailEventRef", tsEventDetailEl);
        var pointRefInput = qs("#dttsDetailPointRef", tsEventDetailEl);
        var durationRefInput = qs("#dttsDetailDurationRef", tsEventDetailEl);
        var startInput = qs("#dttsDetailStart", tsEventDetailEl);
        var durationInput = qs("#dttsDetailDuration", tsEventDetailEl);
        var labelInput = qs("#dttsDetailLabel", tsEventDetailEl);
        var eventRef = String(eventRefInput ? eventRefInput.value : "").trim();
        updateTimeSeriesEvent(eventRef, {
          point_ref: pointRefInput ? pointRefInput.value : "",
          duration_ref: durationRefInput ? durationRefInput.value : "",
          start_unix_s: parseNonNegativeInt(startInput ? startInput.value : "", -1),
          duration_s: parsePositiveInt(durationInput ? durationInput.value : "", -1),
          label: labelInput ? labelInput.value : "",
        }).catch(function (err) {
          setMessages([err.message], []);
        });
        return;
      }

      var deleteBtn = target.closest(".js-dtts-detail-delete");
      if (deleteBtn) {
        var token = deleteBtn.getAttribute("data-event-ref") || "";
        if (!window.confirm("Delete event " + token + "?")) return;
        deleteTimeSeriesEvent(token).catch(function (err) { setMessages([err.message], []); });
      }
    });
  }

  if (tsTableLoadBtn) {
    tsTableLoadBtn.addEventListener("click", function () {
      loadTimeSeriesTableView().catch(function (err) { setMessages([err.message], []); });
    });
  }

  if (samrasCreateBtn) {
    samrasCreateBtn.addEventListener("click", function () {
      createSamrasTable().catch(function (err) { setMessages([err.message], []); });
    });
  }

  if (samrasUpsertBtn) {
    samrasUpsertBtn.addEventListener("click", function () {
      upsertSamrasRow().catch(function (err) { setMessages([err.message], []); });
    });
  }

  if (samrasAddChildBtn) {
    samrasAddChildBtn.addEventListener("click", function () {
      try {
        primeSamrasChildDraft();
      } catch (err) {
        setMessages([err && err.message ? err.message : "Unable to create child draft"], []);
      }
    });
  }

  if (samrasAddRootBtn) {
    samrasAddRootBtn.addEventListener("click", function () {
      primeSamrasRootDraft();
    });
  }

  if (samrasDeleteSelectedBtn) {
    samrasDeleteSelectedBtn.addEventListener("click", function () {
      var selectedId = String(samrasUiState.selectedNodeId || "").trim();
      if (!selectedId) {
        setMessages(["Select a node first"], []);
        return;
      }
      if (!window.confirm("Delete SAMRAS node " + selectedId + "?")) return;
      deleteSamrasRow(selectedId).catch(function (err) { setMessages([err.message], []); });
    });
  }

  if (samrasFormResetBtn) {
    samrasFormResetBtn.addEventListener("click", function () {
      if (samrasAddressIdInput) samrasAddressIdInput.value = "";
      if (samrasTitleInput) samrasTitleInput.value = "";
    });
  }

  if (samrasRefreshBtn) {
    samrasRefreshBtn.addEventListener("click", function () {
      samrasUiState.filter = String(samrasFilterInput ? samrasFilterInput.value : "").trim();
      refreshSamras().catch(function (err) { setMessages([err.message], []); });
    });
  }

  if (samrasGraphModeSel) {
    samrasUiState.graphMode = String(samrasGraphModeSel.value || "full_span").trim().toLowerCase();
    samrasGraphModeSel.addEventListener("change", function () {
      samrasUiState.graphMode = String(samrasGraphModeSel.value || "full_span").trim().toLowerCase();
      renderSamrasGraph(samrasUiState.graph);
    });
  }

  if (samrasFilterInput) {
    samrasFilterInput.addEventListener("input", function () {
      samrasUiState.filter = String(samrasFilterInput.value || "").trim();
    });
    samrasFilterInput.addEventListener("change", function () {
      samrasUiState.filter = String(samrasFilterInput.value || "").trim();
      getSamrasTable(samrasUiState.activeInstanceId).catch(function (err) { setMessages([err.message], []); });
    });
  }

  if (samrasInstanceTabsEl) {
    samrasInstanceTabsEl.addEventListener("click", function (event) {
      var target = event.target;
      if (!target || !target.closest) return;
      var button = target.closest(".js-dtsamras-instance");
      if (!button) return;
      var instanceId = String(button.getAttribute("data-instance-id") || "").trim();
      if (!instanceId) return;
      samrasUiState.activeInstanceId = instanceId;
      getSamrasTable(instanceId).catch(function (err) { setMessages([err.message], []); });
    });
  }

  if (samrasRowsEl) {
    samrasRowsEl.addEventListener("click", function (event) {
      var target = event.target;
      if (!target || !target.closest) return;
      var selectBtn = target.closest(".js-dtsamras-select");
      if (!selectBtn) return;
      var addressId = String(selectBtn.getAttribute("data-address-id") || "").trim();
      if (!addressId) return;
      setSamrasSelection(addressId);
    });
  }

  if (samrasGraphEl) {
    samrasGraphEl.addEventListener("click", function (event) {
      var target = event.target;
      if (!target || !target.closest) return;

      var spanNodeBtn = target.closest(".data-tool__samrasSpanNode");
      if (spanNodeBtn) {
        var spanNodeId = String(spanNodeBtn.getAttribute("data-node-id") || "").trim();
        if (!spanNodeId) return;
        setSamrasSelection(spanNodeId);
        return;
      }

      var toggleBtn = target.closest(".data-tool__samrasNodeToggle");
      var instanceId = String(samrasUiState.activeInstanceId || "").trim();
      if (!instanceId) return;
      if (toggleBtn) {
        var toggleId = String(toggleBtn.getAttribute("data-node-toggle") || "").trim();
        if (!toggleId) return;
        var expanded = getSamrasExpanded(instanceId).slice();
        var toggleIndex = expanded.indexOf(toggleId);
        if (toggleIndex >= 0) {
          expanded.splice(toggleIndex, 1);
        } else {
          expanded.push(toggleId);
        }
        setSamrasExpanded(instanceId, expanded);
        getSamrasTable(instanceId).catch(function (err) { setMessages([err.message], []); });
        return;
      }

      var selectBtn = target.closest(".data-tool__samrasNodeSelect");
      if (selectBtn) {
        var nodeId = String(selectBtn.getAttribute("data-node-id") || "").trim();
        if (!nodeId) return;
        setSamrasSelection(nodeId);
      }
    });
  }

  if (sourceSel) sourceSel.value = "anthology";
  if (appendLayerInput && !appendLayerInput.value) appendLayerInput.value = "1";
  if (appendValueGroupInput && !appendValueGroupInput.value) appendValueGroupInput.value = "1";
  syncAppendPairRequirements();
  ensurePairRows(profilePairsEl, "js-remove-profile-pair");

  var openNimmOnLoad = String(app.getAttribute("data-open-nimm") || "0").trim() === "1";

  closeProfileModal();
  closeAppendModal();
  closeNimmOverlay();

  if (activeDataTab === "samras") {
    Promise.all([getState(), refreshSamras()])
      .then(function () {
        if (openNimmOnLoad) openNimmOverlay();
      })
      .catch(function (err) {
        setMessages([err.message], []);
      });
    return;
  }

  if (activeDataTab === "time-series") {
    Promise.all([
      getState(),
      ensureTimeSeriesBase().catch(function () {
        return getTimeSeriesState();
      }),
    ])
      .then(function () {
        if (openNimmOnLoad) openNimmOverlay();
      })
      .catch(function (err) {
        setMessages([err.message], []);
      });
    return;
  }

  if (activeDataTab === "geographic") {
    getState()
      .then(function () {
        if (openNimmOnLoad) openNimmOverlay();
      })
      .catch(function (err) {
        setMessages([err.message], []);
      });
    return;
  }

  Promise.all([getState().then(function () { return applyQueryBootstrap(); }), getAnthologyTable()])
    .then(function () {
      if (openNimmOnLoad) openNimmOverlay();
    })
    .catch(function (err) {
      setMessages([err.message], []);
    });
})();
