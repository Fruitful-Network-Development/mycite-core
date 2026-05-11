/**
 * Portal component library.
 *
 * Generic renderers for interface panel component frames.
 * Each renderer accepts a component frame dict (as defined in
 * interface_panel_component_frame_contract.md) and returns an HTML string.
 *
 * Load order: must load after v2_portal_interface_panel_host.js.
 * Heavy tool-specific rendering (e.g. geospatial map stage) is delegated to
 * registered renderer modules via window.PortalComponentRenderers.
 */
(function () {
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function asObject(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function asText(value) {
    return String(value == null ? "" : value).trim();
  }

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function layoutSlotAttr(frame, payload) {
    var slot = asText((payload || {}).layout_slot) || asText((frame || {}).layout_slot);
    return slot ? ' data-layout-slot="' + escapeHtml(slot) + '"' : "";
  }

  function renderNestedComponentFrame(frame) {
    if (!frame) return "";
    if (typeof window.__MYCITE_V2_RENDER_COMPONENT_FRAME_RECURSIVE === "function") {
      return window.__MYCITE_V2_RENDER_COMPONENT_FRAME_RECURSIVE(frame);
    }
    return renderComponentFrame(asObject(frame));
  }

  // ---------------------------------------------------------------------------
  // Renderer registry
  //
  // Tool-specific modules may register custom renderers for component types:
  //   window.PortalComponentRenderers.register("geospatial_projection", myFn);
  // The registered function receives (frame) and returns an HTML string.
  // ---------------------------------------------------------------------------

  var _rendererRegistry = Object.create(null);

  var rendererRegistry = {
    register: function (componentType, fn) {
      if (typeof fn === "function") {
        _rendererRegistry[componentType] = fn;
      }
    },
    resolve: function (componentType) {
      return _rendererRegistry[componentType] || null;
    },
  };

  // ---------------------------------------------------------------------------
  // Frame engagement button
  // ---------------------------------------------------------------------------

  function renderEngageButton(frame) {
    var frameId = asText(frame.frame_id);
    var initializer = JSON.stringify(asObject(frame.initializer));
    return (
      '<button type="button" class="v2-component-frame__engageBtn"' +
      ' data-engage-frame="' + escapeHtml(frameId) + '"' +
      ' data-engage-initializer="' + escapeHtml(initializer) + '"' +
      ' title="Re-engage this component">' +
      "↺" +
      "</button>"
    );
  }

  // ---------------------------------------------------------------------------
  // Profile component
  // ---------------------------------------------------------------------------

  function renderProfileFields(fields) {
    var rows = asArray(fields);
    if (!rows.length) return "";
    return (
      '<dl class="v2-component-frame__fields">' +
      rows.map(function (row) {
        var r = asObject(row);
        return (
          "<dt>" + escapeHtml(r.label || "") + "</dt>" +
          "<dd>" + escapeHtml(r.value || "—") + "</dd>"
        );
      }).join("") +
      "</dl>"
    );
  }

  function renderProfileFieldGroups(groups) {
    var list = asArray(groups);
    if (!list.length) return "";
    return list.map(function (group) {
      var g = asObject(group);
      return (
        '<section class="v2-component-frame__fieldGroup">' +
        '<h5 class="v2-component-frame__minorTitle">' + escapeHtml(asText(g.label) || "Fields") + "</h5>" +
        renderProfileFields(asArray(g.fields)) +
        "</section>"
      );
    }).join("");
  }

  function placeholderItemLabel(collectionLabel, index) {
    var base = asText(collectionLabel).toUpperCase();
    var singular = base.replace(/_COLLECTIONS?$/, "_LIST").replace(/S$/, "");
    var suffix = String(index).padStart(2, "0");
    return (singular || "ITEM") + "_" + suffix;
  }

  function renderProfileCollections(collections) {
    var list = asArray(collections);
    if (!list.length) return "";
    return list.map(function (collection) {
      var c = asObject(collection);
      var items = asArray(c.items);
      var placeholderCount = Math.max(0, parseInt(c.placeholder_item_count, 10) || 0);
      var itemsHtml;
      if (items.length) {
        itemsHtml =
          '<dl class="v2-component-frame__collectionItems">' +
          items.map(function (item) {
            var it = asObject(item);
            return (
              "<dt>" + escapeHtml(asText(it.label) || "item") + "</dt>" +
              "<dd>" + escapeHtml(asText(it.value) || "—") +
              (asText(it.detail) ? "<br /><small>" + escapeHtml(asText(it.detail)) + "</small>" : "") +
              "</dd>"
            );
          }).join("") +
          "</dl>";
      } else if (placeholderCount > 0) {
        var placeholders = "";
        for (var i = 1; i <= placeholderCount; i++) {
          placeholders +=
            "<dt>" + escapeHtml(placeholderItemLabel(c.label, i)) + "</dt>" +
            "<dd>—</dd>";
        }
        itemsHtml =
          '<dl class="v2-component-frame__collectionItems v2-component-frame__collectionItems--placeholder">' +
          placeholders +
          "</dl>";
      } else {
        itemsHtml = '<p class="v2-component-frame__empty">' + escapeHtml(asText(c.empty_message) || "No collection entries available.") + "</p>";
      }
      return (
        '<section class="v2-component-frame__collection">' +
        '<h5 class="v2-component-frame__minorTitle">' + escapeHtml(asText(c.label) || "Collection") + "</h5>" +
        itemsHtml +
        "</section>"
      );
    }).join("");
  }

  function renderProfileChildren(children) {
    var list = asArray(children);
    if (!list.length) return "";
    return (
      '<div class="v2-component-frame__children">' +
      list.map(function (child) { return renderNestedComponentFrame(asObject(child)); }).join("") +
      "</div>"
    );
  }

  function renderSubjectSlot(subjectFrame) {
    if (!subjectFrame) return "";
    var frame = asObject(subjectFrame);
    return (
      '<div class="v2-component-frame__subjectSlot" data-subject-frame-id="' +
      escapeHtml(asText(frame.frame_id)) +
      '">' +
      renderNestedComponentFrame(frame) +
      "</div>"
    );
  }

  function renderProfileComponent(frame) {
    var payload = asObject(frame.payload);
    var label = asText(payload.label) || asText(payload.msn_id) || "Profile";
    var msn_id = asText(payload.msn_id);
    var fields = asArray(payload.fields);
    var subjectSlot = payload.subject_slot;
    var variant = asText(payload.variant);
    var subjectHtml = renderSubjectSlot(subjectSlot);
    var detailHtml =
      renderProfileFields(fields) +
      renderProfileFieldGroups(payload.field_groups) +
      renderProfileCollections(payload.collections) +
      renderProfileChildren(payload.children);
    var bodyHtml = (variant === "administrative_node" || variant === "precinct")
      ? subjectHtml + detailHtml
      : detailHtml + subjectHtml;
    return (
      '<div class="v2-component-frame v2-component-frame--profile"' +
      ' data-frame-id="' + escapeHtml(asText(frame.frame_id)) + '"' +
      ' data-component-type="profile"' +
      ' data-render-key="' + escapeHtml(asText(frame.render_key)) + '"' +
      layoutSlotAttr(frame, payload) +
      (variant ? ' data-profile-variant="' + escapeHtml(variant) + '"' : "") +
      ">" +
      '<div class="v2-component-frame__header">' +
      '<h3 class="v2-component-frame__title">' + escapeHtml(label) + "</h3>" +
      (msn_id ? '<span class="v2-component-frame__subtitle">' + escapeHtml(msn_id) + "</span>" : "") +
      renderEngageButton(frame) +
      "</div>" +
      bodyHtml +
      "</div>"
    );
  }

  // ---------------------------------------------------------------------------
  // Geospatial projection component
  // ---------------------------------------------------------------------------

  function renderGeospatialProjectionFallback(frame) {
    var payload = asObject(frame.payload);
    var state = asText(payload.projection_state) || "inspect_only";
    var featureCount = parseInt(payload.feature_count || 0, 10);
    var emptyMessage = asText(payload.empty_message) || "No projected geometry is available.";
    var hasRealProjection = state !== "inspect_only" && state !== "" && featureCount > 0;
    return (
      '<div class="v2-component-frame__geospatialFallback">' +
      '<p class="v2-component-frame__geospatialState">' +
      '<span>state: ' + escapeHtml(state) + "</span>" +
      '<span>features: ' + escapeHtml(String(featureCount)) + "</span>" +
      "</p>" +
      (!hasRealProjection
        ? '<p class="v2-component-frame__geospatialEmpty">' + escapeHtml(emptyMessage) + "</p>"
        : "") +
      "</div>"
    );
  }

  function renderGeospatialProjectionComponent(frame) {
    var payload = asObject(frame.payload);
    var customRenderer = rendererRegistry.resolve("geospatial_projection");
    var innerHtml = customRenderer
      ? customRenderer(frame)
      : renderGeospatialProjectionFallback(frame);
    return (
      '<div class="v2-component-frame v2-component-frame--geospatial"' +
      ' data-frame-id="' + escapeHtml(asText(frame.frame_id)) + '"' +
      ' data-component-type="geospatial_projection"' +
      ' data-render-key="' + escapeHtml(asText(frame.render_key)) + '"' +
      layoutSlotAttr(frame, payload) +
      ">" +
      '<div class="v2-component-frame__header">' +
      '<h4 class="v2-component-frame__title">' +
      escapeHtml(asText(frame.label) || "Spatial Projection") +
      "</h4>" +
      renderEngageButton(frame) +
      "</div>" +
      innerHtml +
      "</div>"
    );
  }

  // ---------------------------------------------------------------------------
  // Characteristic set component
  // ---------------------------------------------------------------------------

  function renderCharacteristicSetComponent(frame) {
    var payload = asObject(frame.payload);
    var label = asText(payload.label) || asText(frame.label) || "Characteristics";
    var items = asArray(payload.items);
    var itemsHtml = items.length
      ? '<dl class="v2-component-frame__charItems">' +
        items.map(function (item) {
          var it = asObject(item);
          return (
            "<dt>" + escapeHtml(it.label || "") + "</dt>" +
            "<dd>" +
            escapeHtml(it.value || "—") +
            (it.detail ? "<br /><small>" + escapeHtml(it.detail) + "</small>" : "") +
            "</dd>"
          );
        }).join("") +
        "</dl>"
      : '<p class="v2-component-frame__empty">No characteristics available.</p>';
    return (
      '<div class="v2-component-frame v2-component-frame--characteristicSet"' +
      ' data-frame-id="' + escapeHtml(asText(frame.frame_id)) + '"' +
      ' data-component-type="characteristic_set"' +
      ' data-render-key="' + escapeHtml(asText(frame.render_key)) + '"' +
      layoutSlotAttr(frame, payload) +
      ">" +
      '<div class="v2-component-frame__header">' +
      '<h4 class="v2-component-frame__title">' + escapeHtml(label) + "</h4>" +
      renderEngageButton(frame) +
      "</div>" +
      itemsHtml +
      "</div>"
    );
  }

  // ---------------------------------------------------------------------------
  // Component group
  // ---------------------------------------------------------------------------

  function renderComponentGroupComponent(frame) {
    var payload = asObject(frame.payload);
    var children = asArray(payload.children);
    var layout = asText(payload.layout) || "stack";
    var childrenHtml = children.length
      ? children.map(function (child) { return renderNestedComponentFrame(asObject(child)); }).join("")
      : '<p class="v2-component-frame__empty">' + escapeHtml(asText(payload.empty_message) || "No component frames available.") + "</p>";
    return (
      '<div class="v2-component-group v2-component-group--' + escapeHtml(layout) + '"' +
      ' data-frame-id="' + escapeHtml(asText(frame.frame_id)) + '"' +
      ' data-component-type="component_group"' +
      ' data-render-key="' + escapeHtml(asText(frame.render_key)) + '"' +
      layoutSlotAttr(frame, payload) +
      ">" +
      '<div class="v2-component-group__children">' +
      childrenHtml +
      "</div></div>"
    );
  }

  // ---------------------------------------------------------------------------
  // Listing
  // ---------------------------------------------------------------------------

  function renderListingComponent(frame) {
    var payload = asObject(frame.payload);
    var columns = asArray(payload.columns);
    var rows = asArray(payload.rows);
    var placeholderCount = Math.max(0, parseInt(payload.placeholder_row_count, 10) || 0);
    var tableHtml;
    if (rows.length && columns.length) {
      tableHtml =
        '<table class="v2-component-listing__table"><thead><tr>' +
        columns.map(function (column) {
          var c = asObject(column);
          return "<th>" + escapeHtml(asText(c.label) || asText(c.key)) + "</th>";
        }).join("") +
        "</tr></thead><tbody>" +
        rows.map(function (row) {
          var r = asObject(row);
          return "<tr>" + columns.map(function (column) {
            var key = asText(asObject(column).key);
            return "<td>" + escapeHtml(r[key] == null ? "" : String(r[key])) + "</td>";
          }).join("") + "</tr>";
        }).join("") +
        "</tbody></table>";
    } else if (columns.length && placeholderCount > 0) {
      var indexKey = asText(asObject(columns[0]).key);
      var placeholderRows = "";
      for (var i = 1; i <= placeholderCount; i++) {
        var indexText = String(i).padStart(2, "0");
        placeholderRows +=
          '<tr class="v2-component-listing__row--placeholder">' +
          columns.map(function (column, columnIndex) {
            var columnObj = asObject(column);
            var key = asText(columnObj.key);
            var isIndexColumn = columnIndex === 0 && (!key || key === indexKey);
            var cellClass = isIndexColumn
              ? "v2-component-listing__cell--placeholder v2-component-listing__cell--placeholderIndex"
              : "v2-component-listing__cell--placeholder";
            return '<td class="' + cellClass + '">' + (isIndexColumn ? escapeHtml(indexText) : "&nbsp;") + "</td>";
          }).join("") +
          "</tr>";
      }
      tableHtml =
        '<table class="v2-component-listing__table v2-component-listing__table--placeholder"><thead><tr>' +
        columns.map(function (column) {
          var c = asObject(column);
          return "<th>" + escapeHtml(asText(c.label) || asText(c.key)) + "</th>";
        }).join("") +
        "</tr></thead><tbody>" +
        placeholderRows +
        "</tbody></table>";
    } else {
      tableHtml = '<p class="v2-component-frame__empty">' + escapeHtml(asText(payload.empty_message) || "No entries available.") + "</p>";
    }
    return (
      '<div class="v2-component-frame v2-component-frame--listing"' +
      ' data-frame-id="' + escapeHtml(asText(frame.frame_id)) + '"' +
      ' data-component-type="listing"' +
      ' data-render-key="' + escapeHtml(asText(frame.render_key)) + '"' +
      layoutSlotAttr(frame, payload) +
      ">" +
      '<div class="v2-component-frame__header">' +
      '<h4 class="v2-component-frame__title">' + escapeHtml(asText(frame.label) || asText(payload.label) || "Listing") + "</h4>" +
      renderEngageButton(frame) +
      "</div>" +
      tableHtml +
      "</div>"
    );
  }

  // ---------------------------------------------------------------------------
  // Chronology matrix
  // ---------------------------------------------------------------------------

  function renderChronologyMatrixComponent(frame) {
    var payload = asObject(frame.payload);
    var rows = asArray(payload.row_headers);
    var columns = asArray(payload.column_headers);
    var eventMap = Object.create(null);
    asArray(payload.events).forEach(function (event) {
      var e = asObject(event);
      eventMap[asText(e.row_key) + "::" + asText(e.column_key)] = asText(e.value) || "•";
    });
    var matrixHtml = rows.length && columns.length
      ? '<table class="v2-component-chronology__table"><thead><tr><th>Election Type / District</th>' +
        columns.map(function (column) { return "<th>" + escapeHtml(asText(column)) + "</th>"; }).join("") +
        "</tr></thead><tbody>" +
        rows.map(function (row) {
          var r = asObject(row);
          var rowKey = asText(r.key);
          return "<tr><th>" + escapeHtml(asText(r.label) || rowKey) + "</th>" +
            columns.map(function (column) {
              var columnKey = asText(column);
              return "<td>" + escapeHtml(eventMap[rowKey + "::" + columnKey] || "") + "</td>";
            }).join("") +
            "</tr>";
        }).join("") +
        "</tbody></table>"
      : '<p class="v2-component-frame__empty">' + escapeHtml(asText(payload.empty_message) || "No chronological events available.") + "</p>";
    return (
      '<div class="v2-component-frame v2-component-frame--chronologyMatrix"' +
      ' data-frame-id="' + escapeHtml(asText(frame.frame_id)) + '"' +
      ' data-component-type="chronology_matrix"' +
      ' data-render-key="' + escapeHtml(asText(frame.render_key)) + '"' +
      layoutSlotAttr(frame, payload) +
      ">" +
      '<div class="v2-component-frame__header">' +
      '<h4 class="v2-component-frame__title">' + escapeHtml(asText(frame.label) || asText(payload.label) || "Chronology") + "</h4>" +
      renderEngageButton(frame) +
      "</div>" +
      matrixHtml +
      "</div>"
    );
  }

  // ---------------------------------------------------------------------------
  // Dispatcher
  // ---------------------------------------------------------------------------

  function renderComponentFrame(frame) {
    var f = asObject(frame);
    var componentType = asText(f.component_type);
    switch (componentType) {
      case "component_group":
        return renderComponentGroupComponent(f);
      case "profile":
        return renderProfileComponent(f);
      case "geospatial_projection":
        return renderGeospatialProjectionComponent(f);
      case "characteristic_set":
        return renderCharacteristicSetComponent(f);
      case "listing":
        return renderListingComponent(f);
      case "chronology_matrix":
        return renderChronologyMatrixComponent(f);
      default:
        return (
          '<div class="v2-component-frame v2-component-frame--unknown"' +
          ' data-frame-id="' + escapeHtml(asText(f.frame_id)) + '"' +
          ' data-component-type="' + escapeHtml(componentType) + '">' +
          '<p class="v2-component-frame__empty">Unknown component type: ' +
          escapeHtml(componentType) +
          "</p></div>"
        );
    }
  }

  function renderComponentFrameList(frames) {
    var list = asArray(frames);
    if (!list.length) return '<p class="v2-component-frames__empty">No component frames available.</p>';
    return (
      '<div class="v2-component-frames">' +
      list.map(function (frame) { return renderNestedComponentFrame(asObject(frame)); }).join("") +
      "</div>"
    );
  }

  // ---------------------------------------------------------------------------
  // Workbench Components
  // ---------------------------------------------------------------------------

  function renderDocumentCard(card, options) {
    var c = asObject(card);
    var opts = asObject(options);
    var documentId = asText(c.document_id);
    var canonicalName = stripJsonSuffix ? stripJsonSuffix(asText(c.canonical_name) || asText(c.document_name)) : (asText(c.canonical_name) || asText(c.document_name));
    var rawName = asText(c.relative_path) || asText(c.document_name);
    var isAnchor = !!c.is_anchor;
    var isSelected = !!c.selected;
    var showRename = !!opts.showRename;
    var showDelete = !!opts.showDelete;
    return (
      '<article class="v2-card v2-wb-docCard' +
      (isSelected ? " is-selected" : "") +
      (isAnchor ? " is-anchor" : "") +
      '" tabindex="0" role="button" data-shell-transition-kind="focus_file" data-shell-file-key="' +
      escapeHtml(documentId) +
      '">' +
      '<div class="v2-wb-docCard__header">' +
      '<h3 class="v2-wb-docCard__name">' +
      escapeHtml(canonicalName || documentId || "Document") +
      (isAnchor ? ' <small>(anchor)</small>' : "") +
      "</h3>" +
      (showRename || showDelete
        ? '<span class="v2-wb-docCard__actions">' +
          (showRename ? '<button class="v2-wb-renameBtn" data-rename-document-id="' + escapeHtml(documentId) + '" title="Rename" aria-label="Rename">✎</button>' : "") +
          (showDelete
            ? (!isAnchor
              ? '<button class="v2-wb-deleteBtn" data-delete-document-id="' + escapeHtml(documentId) + '" data-document-is-anchor="false" title="Delete" aria-label="Delete">×</button>'
              : '<button class="v2-wb-deleteBtn" data-delete-document-id="' + escapeHtml(documentId) + '" data-document-is-anchor="true" title="Anchor cannot be deleted" aria-label="Delete" disabled>×</button>'
            )
            : "") +
          "</span>"
        : "") +
      "</div>" +
      (rawName ? "<p><small>" + escapeHtml(rawName) + "</small></p>" : "") +
      (documentId ? "<p><small>" + escapeHtml(documentId) + "</small></p>" : "") +
      "<p>Rows: " + escapeHtml(String(c.row_count || 0)) + "</p>" +
      "</article>"
    );
  }

  function renderDatumRowItem(row, options) {
    var r = asObject(row);
    var opts = asObject(options);
    var address = asText(r.datum_address);
    var layer = asText(r.layer);
    var valueGroup = asText(r.value_group);
    var iteration = asText(r.iteration);
    var displayValues = asObject(r.display_values);
    var showEdit = !!opts.showEdit;
    return (
      '<div class="v2-wb-datumRow" data-datum-address="' + escapeHtml(address) + '">' +
      '<span class="v2-wb-datumRow__addr">' + escapeHtml(address) + "</span>" +
      (layer ? '<span class="v2-wb-datumRow__layer">' + escapeHtml(layer) + "</span>" : "") +
      (valueGroup ? '<span class="v2-wb-datumRow__group">' + escapeHtml(valueGroup) + "</span>" : "") +
      (iteration ? '<span class="v2-wb-datumRow__iter">' + escapeHtml(iteration) + "</span>" : "") +
      (showEdit ? '<button class="v2-wb-datumRow__editBtn" data-edit-datum-address="' + escapeHtml(address) + '" title="Edit row">✎</button>' : "") +
      "</div>"
    );
  }

  // ---------------------------------------------------------------------------
  // Component action dispatch helper (Path A standard)
  // ---------------------------------------------------------------------------

  /**
   * buildComponentActionDispatch(ctx, surfacePayload, actionKind, actionPayload)
   *
   * Standard Path A dispatch for component-level mutations and selection changes.
   * Reads route and schema from surfacePayload.request_contract; no hardcoded values.
   * Returns a zero-argument function that fires the action when called.
   *
   * Usage: button.addEventListener("click", buildComponentActionDispatch(ctx, sp, "kind", {data}));
   */
  function buildComponentActionDispatch(ctx, surfacePayload, actionKind, actionPayload) {
    var contract = asObject(surfacePayload && surfacePayload.request_contract);
    var route = asText(contract.action_route || contract.route);
    var schema = asText(contract.action_schema);
    var toolState = asObject(surfacePayload && surfacePayload.tool_state);
    return function dispatch() {
      if (typeof ctx.loadRuntimeView === "function") {
        ctx.loadRuntimeView(route, {
          schema: schema,
          action_kind: actionKind,
          action_payload: asObject(actionPayload),
          tool_state: toolState,
        });
      }
    };
  }

  // ---------------------------------------------------------------------------
  // Export
  // ---------------------------------------------------------------------------

  window.PortalComponentLibrary = {
    rendererRegistry: rendererRegistry,
    renderComponentFrame: renderComponentFrame,
    renderComponentFrameList: renderComponentFrameList,
    renderComponentGroupComponent: renderComponentGroupComponent,
    renderProfileComponent: renderProfileComponent,
    renderGeospatialProjectionComponent: renderGeospatialProjectionComponent,
    renderCharacteristicSetComponent: renderCharacteristicSetComponent,
    renderListingComponent: renderListingComponent,
    renderChronologyMatrixComponent: renderChronologyMatrixComponent,
    renderDocumentCard: renderDocumentCard,
    renderDatumRowItem: renderDatumRowItem,
    buildComponentActionDispatch: buildComponentActionDispatch,
  };

  if (typeof window.__MYCITE_V2_REGISTER_SHELL_MODULE === "function") {
    window.__MYCITE_V2_REGISTER_SHELL_MODULE("portal_component_library");
  }
})();
