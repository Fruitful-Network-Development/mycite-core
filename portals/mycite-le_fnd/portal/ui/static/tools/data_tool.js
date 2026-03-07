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

  var messagesEl = qs("#dtMessages", app);
  var stateEl = qs("#dtStateSummary", app);
  var modelMetaEl = qs("#dtModelMeta", app);
  var leftPaneEl = qs("#dtLeftPane", app);
  var rightPaneEl = qs("#dtRightPane", app);
  var anthologyLayersEl = qs("#dtAnthologyLayers", app);
  var anthologyStatusEl = qs("#dtAnthologyStatus", app);
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
  };

  var timeSeriesUiState = {
    selectedEventRef: "",
    events: [],
    eventEnabledTables: [],
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

  function normalizeConspectusReferences(rawRefs) {
    var refs = [];
    if (!Array.isArray(rawRefs)) return refs;
    rawRefs.forEach(function (item) {
      var token = String(item == null ? "" : item).trim();
      if (!token) return;
      refs.push(token);
    });
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
        ". Provide one or more references; magnitude is fixed to 0 and conspectus is derived from those references.";
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
        selection: state.selection || {},
        staged_edits_count: Array.isArray(snapshot && snapshot.staged_edits) ? snapshot.staged_edits.length : 0,
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
    var datumLookup = buildDatumLookup(view && view.rows);

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
          var conspectusRefs = normalizeConspectusReferences(row.conspectus_references);

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
            if (!conspectusRefs.length) {
              var emptyConspectus = document.createElement("span");
              emptyConspectus.className = "data-tool__statusText";
              emptyConspectus.textContent = "No conspectus references";
              pairCards.appendChild(emptyConspectus);
            } else {
              conspectusRefs.forEach(function (reference) {
                pairCards.appendChild(createPairCard({ reference: reference, magnitude: "conspectus" }, datumLookup));
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
    setMessages(payload.errors || [], payload.warnings || []);
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

  if (sourceSel) sourceSel.value = "anthology";
  if (appendLayerInput && !appendLayerInput.value) appendLayerInput.value = "1";
  if (appendValueGroupInput && !appendValueGroupInput.value) appendValueGroupInput.value = "1";
  syncAppendPairRequirements();
  ensurePairRows(profilePairsEl, "js-remove-profile-pair");

  var openNimmOnLoad = String(app.getAttribute("data-open-nimm") || "0").trim() === "1";

  closeProfileModal();
  closeAppendModal();
  closeNimmOverlay();

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
