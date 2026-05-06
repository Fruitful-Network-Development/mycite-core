/**
 * Workbench renderer for the one-shell portal.
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

  function asList(value) {
    return Array.isArray(value) ? value.slice() : [];
  }

  function asText(value) {
    return String(value == null ? "" : value).trim();
  }

  function stripJsonSuffix(value) {
    return asText(value).replace(/\.json$/i, "");
  }

  function prettyJson(value) {
    if (value == null) return "";
    try {
      return JSON.stringify(value, null, 2);
    } catch (_) {
      return String(value);
    }
  }

  function renderCards(cards) {
    if (!cards || !cards.length) return "";
    return (
      '<div class="v2-card-grid">' +
      cards
        .map(function (card) {
          return (
            '<article class="v2-card"><h3>' +
            escapeHtml(card.label || "") +
            "</h3><p>" +
            escapeHtml(card.value || "—") +
            "</p>" +
            (card.meta ? '<small>' + escapeHtml(card.meta) + "</small>" : "") +
            "</article>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderRows(rows) {
    if (!rows || !rows.length) return "";
    return (
      '<dl class="v2-surface-dl">' +
      rows
        .map(function (row) {
          return (
            "<dt>" +
            escapeHtml(row.label || "") +
            "</dt><dd><strong>" +
            escapeHtml(row.status || row.value || "—") +
            "</strong>" +
            (row.detail ? "<br />" + escapeHtml(row.detail) : "") +
            "</dd>"
          );
        })
        .join("") +
      "</dl>"
    );
  }

  function renderTable(section) {
    var columns = section.columns || [];
    var items = section.items || [];
    if (!columns.length) return "";
    return (
      '<div class="v2-tableWrap"><table class="v2-table"><thead><tr>' +
      columns
        .map(function (column) {
          return "<th>" + escapeHtml(column.label || column.key || "") + "</th>";
        })
        .join("") +
      "</tr></thead><tbody>" +
      (items.length
        ? items
            .map(function (item) {
              return (
                "<tr>" +
                columns
                  .map(function (column) {
                    return "<td>" + escapeHtml(item[column.key] || "—") + "</td>";
                  })
                  .join("") +
                "</tr>"
              );
            })
            .join("")
        : '<tr><td colspan="' + String(columns.length) + '">No entries.</td></tr>') +
      "</tbody></table></div>"
    );
  }

  function renderSubsections(subsections) {
    if (!subsections || !subsections.length) return "";
    return subsections
      .map(function (subsection) {
        return (
          '<div class="v2-card" style="margin-top:12px"><h3>' +
          escapeHtml(subsection.title || "Section") +
          "</h3>" +
          renderRows(subsection.facts || subsection.rows || []) +
          renderTable({ columns: subsection.columns, items: subsection.rows || subsection.items || [] }) +
          (subsection.preformatted
            ? '<pre class="lr-workbench__miniPre">' + escapeHtml(subsection.preformatted) + "</pre>"
            : "") +
          "</div>"
        );
      })
      .join("");
  }

  function renderSections(sections) {
    if (!sections || !sections.length) return "";
    return sections
      .map(function (section) {
        return (
          '<section class="v2-card" style="margin-top:12px"><h3>' +
          escapeHtml(section.title || "Section") +
          "</h3>" +
          (section.summary ? "<p>" + escapeHtml(section.summary) + "</p>" : "") +
          renderRows(section.rows || []) +
          renderTable(section) +
          (section.preformatted ? '<pre class="lr-workbench__miniPre">' + escapeHtml(section.preformatted) + "</pre>" : "") +
          renderSubsections(section.subsections || []) +
          "</section>"
        );
      })
      .join("");
  }

  function renderNotes(notes) {
    if (!notes || !notes.length) return "";
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Notes</h3><ul>' +
      notes
        .map(function (note) {
          return "<li>" + escapeHtml(note) + "</li>";
        })
        .join("") +
      "</ul></section>"
    );
  }

  function toolSurfaceAdapter() {
    return window.PortalToolSurfaceAdapter || {};
  }

  function resolveRegisteredModuleExport(moduleId, globalName) {
    if (typeof window.__MYCITE_V2_RESOLVE_SHELL_MODULE_EXPORT === "function") {
      return window.__MYCITE_V2_RESOLVE_SHELL_MODULE_EXPORT(moduleId, globalName);
    }
    return window[globalName] || null;
  }

  function buildModuleRegistrationMessage(label, moduleId, globalName, callableName) {
    var message =
      "The " +
      asText(label || "surface") +
      " renderer contract is unavailable. " +
      "module_id=" +
      moduleId +
      " expected_global=" +
      globalName +
      " expected_callable=" +
      callableName +
      ".";
    if (typeof window.__MYCITE_V2_GET_SHELL_MODULE_DIAGNOSTICS !== "function") {
      return message;
    }
    var diagnostics = window.__MYCITE_V2_GET_SHELL_MODULE_DIAGNOSTICS(moduleId) || {};
    var loadedScripts = asList(diagnostics.script_load_order)
      .map(function (entry) {
        return asText((entry && entry.module_id) || (entry && entry.file));
      })
      .filter(Boolean);
    var registeredModules = asList(diagnostics.registered_module_ids)
      .map(function (entry) {
        return asText(entry);
      })
      .filter(Boolean);
    var invalidMessages = asList(diagnostics.invalid_messages)
      .map(function (entry) {
        return asText(entry);
      })
      .filter(Boolean);
    var failures = asList(diagnostics.failures)
      .map(function (entry) {
        return asText(entry);
      })
      .filter(Boolean);
    return (
      message +
      " boot_stage=" +
      (asText(diagnostics.boot_stage) || "unknown") +
      " loaded_scripts=" +
      (loadedScripts.join(" -> ") || "none") +
      " registered_modules=" +
      (registeredModules.join(", ") || "none") +
      " invalid_registrations=" +
      (invalidMessages.join("; ") || "none") +
      (failures.length ? " contract_failures=" + failures.join("; ") : "")
    );
  }

  function renderGenericSurface(ctx, target, region, surfacePayload) {
    var adapter = toolSurfaceAdapter();
    return adapter.renderWrappedSurface(
      target,
      adapter.resolveSurfaceState({
        region: region,
        surfacePayload: surfacePayload,
        title: region.title || "Workbench",
        hasContent: adapter.hasGenericContent(surfacePayload),
      }),
      renderCards(surfacePayload.cards || []) +
        renderSections(surfacePayload.sections || []) +
        renderNotes(surfacePayload.notes || [])
    );
  }

  function renderIdentityBadge(shortValue, fullValue) {
    var shortToken = asText(shortValue) || "—";
    var fullToken = asText(fullValue);
    return (
      '<div class="v2-workbenchUi__identity">' +
      '<span class="v2-workbenchUi__badge">' +
      escapeHtml(shortToken) +
      "</span>" +
      (fullToken
        ? '<div class="v2-workbenchUi__subvalue">' + escapeHtml(fullToken) + "</div>"
        : "") +
      "</div>"
    );
  }

  function renderDocumentRows(rows, sourceVisibility) {
    if (!rows.length) {
      return '<tr><td colspan="' + String(sourceVisibility === "hide" ? 4 : 5) + '">No authoritative documents matched the current filter.</td></tr>';
    }
    return rows
      .map(function (row, index) {
        var selection = row.selected ? '<span class="v2-workbenchUi__selectedTag">Selected</span>' : "";
        return (
          '<tr class="v2-workbenchUi__row v2-workbenchUi__row--document' +
          (row.selected ? " is-selected" : "") +
          '" tabindex="0" data-workbench-document-index="' +
          String(index) +
          '">' +
          '<td><div class="v2-workbenchUi__primaryCell">' +
          selection +
          '<strong>' +
          escapeHtml(stripJsonSuffix(row.document_name || row.label || row.document_id || "—")) +
          "</strong>" +
          '<div class="v2-workbenchUi__subvalue">' +
          escapeHtml(row.document_id || "—") +
          "</div></div></td>" +
          (sourceVisibility === "hide"
            ? ""
            : "<td>" +
              escapeHtml(row.source_kind || "—") +
              "</td>") +
          "<td>" +
          renderIdentityBadge(row.version_hash_short, row.version_hash) +
          "</td>" +
          "<td>" +
          escapeHtml(String(row.row_count || 0)) +
          "</td>" +
          '<td><button class="v2-workbenchUi__action" type="button" data-workbench-document-index="' +
          String(index) +
          '">' +
          escapeHtml(row.selected ? "Selected" : "Focus") +
          "</button></td></tr>"
        );
      })
      .join("");
  }

  function renderDatumCell(row, lens) {
    if (lens === "raw") {
      return (
        '<div class="v2-workbenchUi__primaryCell"><strong>' +
        escapeHtml(row.raw_preview || row.raw_json || "—") +
        "</strong></div>"
      );
    }
    var primary = row.display_value || row.labels || row.primary_value_token || row.object_ref || "—";
    var detail = row.display_summary || ((row.relation || "—") + " -> " + (row.object_ref || "—"));
    return (
      '<div class="v2-workbenchUi__primaryCell"><strong>' +
      escapeHtml(primary) +
      "</strong>" +
      '<div class="v2-workbenchUi__subvalue">' +
      escapeHtml(detail) +
      "</div></div>"
    );
  }

  function renderDatumRows(rows, options) {
    var opts = options || {};
    var lens = asText(opts.lens) || "interpreted";
    if (!rows.length) {
      return '<tr><td colspan="6">No datum rows matched the current filter.</td></tr>';
    }
    return rows
      .map(function (row, index) {
        var globalIndex = opts.offset + index;
        var selection = row.selected ? '<span class="v2-workbenchUi__selectedTag">Selected</span>' : "";
        return (
          '<tr class="v2-workbenchUi__row v2-workbenchUi__row--datum' +
          (row.selected ? " is-selected" : "") +
          '" tabindex="0" data-workbench-row-index="' +
          String(globalIndex) +
          '">' +
          '<td><div class="v2-workbenchUi__primaryCell">' +
          selection +
          '<strong>' +
          escapeHtml(row.datum_address || "—") +
          "</strong>" +
          '<div class="v2-workbenchUi__subvalue">' +
          escapeHtml("L" + String(row.layer || 0) + " · VG" + String(row.value_group || 0) + " · I" + String(row.iteration || 0)) +
          "</div></div></td>" +
          "<td>" +
          renderDatumCell(row, lens) +
          "</td>" +
          "<td>" +
          renderIdentityBadge(row.hyphae_hash_short, row.hyphae_hash) +
          "</td>" +
          '<td><button class="v2-workbenchUi__action" type="button" data-workbench-row-index="' +
          String(globalIndex) +
          '">' +
          escapeHtml(row.selected ? "Selected" : "Focus") +
          "</button></td></tr>"
        );
      })
      .join("");
  }

  function renderDatumGroup(group, lens, offset) {
    var rows = asList(group.items);
    return (
      '<section class="v2-workbenchUi__group">' +
      '<div class="v2-workbenchUi__groupHeader"><h4>' +
      escapeHtml(group.title || "Rows") +
      "</h4>" +
      (group.summary ? "<p>" + escapeHtml(group.summary) + "</p>" : "") +
      "</div>" +
      '<div class="v2-tableWrap v2-workbenchUi__tableWrap">' +
      '<table class="v2-table v2-workbenchUiTable"><thead class="v2-workbenchUi__stickyHeader"><tr>' +
      "<th>Datum</th><th>" +
      escapeHtml(lens === "raw" ? "Raw Payload" : "Interpreted Row") +
      "</th><th>Identity</th><th>Action</th>" +
      "</tr></thead><tbody>" +
      renderDatumRows(rows, { lens: lens, offset: offset }) +
      "</tbody></table></div></section>"
    );
  }

  function flattenDatumRows(workspace) {
    var datumGrid = asObject(workspace.datum_grid);
    var layers = asList(datumGrid.layers);
    if (layers.length) {
      var matrixRows = [];
      layers.forEach(function (layer) {
        asList(asObject(layer).value_groups).forEach(function (valueGroup) {
          asList(asObject(valueGroup).cells).forEach(function (row) {
            matrixRows.push(row);
          });
        });
      });
      if (matrixRows.length) return matrixRows;
    }
    var groups = asList(datumGrid.groups);
    if (groups.length) {
      var rows = [];
      groups.forEach(function (group) {
        asList(asObject(group).items).forEach(function (row) {
          rows.push(row);
        });
      });
      return rows;
    }
    return asList(datumGrid.rows);
  }

  function renderDatumMatrixCell(row, globalIndex) {
    var selection = row.selected ? "Selected · " : "";
    var diagnostics = asList(row.diagnostic_states).join(", ");
    var detailBits = [
      row.display_summary || "",
      diagnostics,
      row.hyphae_hash_short ? "ID " + row.hyphae_hash_short : "",
    ].filter(Boolean);
    return (
      '<button class="v2-workbenchUi__navButton" style="text-align:left;min-height:120px" type="button" data-workbench-row-index="' +
      String(globalIndex) +
      '">' +
      '<strong>' +
      escapeHtml(selection + "I" + String(row.iteration || 0) + " · " + (row.datum_address || "—")) +
      "</strong>" +
      '<small>' +
      escapeHtml(row.display_value || row.labels || row.primary_value_token || "—") +
      "</small>" +
      '<small>' +
      escapeHtml(detailBits.join(" · ") || "—") +
      "</small></button>"
    );
  }

  function renderDatumMatrix(layers) {
    var offset = 0;
    return asList(layers)
      .map(function (layer) {
        var valueGroupHtml = asList(asObject(layer).value_groups)
          .map(function (valueGroup) {
            var cells = asList(asObject(valueGroup).cells);
            var cards = cells
              .map(function (row, index) {
                return renderDatumMatrixCell(row, offset + index);
              })
              .join("");
            offset += cells.length;
            return (
              '<section class="v2-card" style="margin-top:12px"><h4>' +
              escapeHtml(asObject(valueGroup).title || "Value Group") +
              "</h4>" +
              '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px">' +
              cards +
              "</div></section>"
            );
          })
          .join("");
        return (
          '<section class="v2-workbenchUi__group">' +
          '<div class="v2-workbenchUi__groupHeader"><h4>' +
          escapeHtml(asObject(layer).title || "Layer") +
          "</h4>" +
          (asObject(layer).summary ? "<p>" + escapeHtml(asObject(layer).summary) + "</p>" : "") +
          "</div>" +
          valueGroupHtml +
          "</section>"
        );
      })
      .join("");
  }

  function renderWorkbenchSummary(workspace) {
    var selectedDocument = asObject(workspace.selected_document);
    var selectedRow = asObject(workspace.selected_row);
    var query = asObject(workspace.query);
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Current Lens</h3>' +
      '<dl class="v2-surface-dl">' +
      "<dt>document</dt><dd><strong>" +
      escapeHtml(selectedDocument.canonical_name || selectedDocument.document_name || selectedDocument.document_id || "—") +
      "</strong></dd>" +
      "<dt>version</dt><dd><strong>" +
      escapeHtml(selectedDocument.version_hash || "—") +
      "</strong></dd>" +
      "<dt>row</dt><dd><strong>" +
      escapeHtml(selectedRow.datum_address || "—") +
      "</strong></dd>" +
      "<dt>group</dt><dd><strong>" +
      escapeHtml(query.group || workspace.datum_grid.group_mode || "flat") +
      "</strong></dd>" +
      "<dt>lens</dt><dd><strong>" +
      escapeHtml(query.workbench_lens || workspace.datum_grid.lens || "interpreted") +
      "</strong></dd>" +
      "<dt>source</dt><dd><strong>" +
      escapeHtml(query.source || workspace.source_visibility || "show") +
      "</strong></dd>" +
      "<dt>overlay</dt><dd><strong>" +
      escapeHtml(query.overlay || workspace.overlay_visibility || "show") +
      "</strong></dd>" +
      "</dl></section>"
    );
  }

  function renderWorkbenchNavigation(workspace) {
    var navigation = asObject(workspace.navigation);
    var buttons = [];
    [
      ["previous_document", "Previous Document"],
      ["next_document", "Next Document"],
      ["previous_row", "Previous Row"],
      ["next_row", "Next Row"],
    ].forEach(function (entry) {
      var item = asObject(navigation[entry[0]]);
      if (!item.shell_request) return;
      buttons.push(
        '<button class="v2-workbenchUi__navButton" type="button" data-workbench-nav-key="' +
          escapeHtml(entry[0]) +
          '">' +
          escapeHtml(entry[1]) +
          '<small>' +
          escapeHtml(item.label || item.id || "—") +
          "</small></button>"
      );
    });
    if (!buttons.length) return "";
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Navigation</h3><div class="v2-workbenchUi__navButtons">' +
      buttons.join("") +
      "</div></section>"
    );
  }

  function renderWorkbenchSurface(surfacePayload) {
    var workspace = asObject(surfacePayload.workspace);
    var documentTable = asObject(workspace.document_table);
    var datumGrid = asObject(workspace.datum_grid);
    var groups = asList(datumGrid.groups);
    var layers = asList(datumGrid.layers);
    var lens = asText(datumGrid.lens) || "interpreted";
    var sourceVisibility = asText(workspace.source_visibility) || "show";
    var offset = 0;
    var groupHtml = groups
      .map(function (group) {
        var html = renderDatumGroup(asObject(group), lens, offset);
        offset += asList(asObject(group).items).length;
        return html;
      })
      .join("");
    var matrixHtml = renderDatumMatrix(layers);
    var flatRows = asList(datumGrid.rows);
    return (
      renderCards(surfacePayload.cards || []) +
      renderWorkbenchSummary(workspace) +
      '<div class="v2-workbenchUi__layout">' +
      '<section class="v2-card v2-workbenchUi__pane"><div class="v2-workbenchUi__paneHeader"><h3>Document Table</h3><p>Read-only authoritative documents keyed by SQL version identity.</p></div>' +
      '<div class="v2-tableWrap v2-workbenchUi__tableWrap">' +
      '<table class="v2-table v2-workbenchUiTable"><thead class="v2-workbenchUi__stickyHeader"><tr>' +
      "<th>Document</th>" +
      (sourceVisibility === "hide" ? "" : "<th>Source</th>") +
      "<th>Version</th><th>Rows</th><th>Action</th>" +
      "</tr></thead><tbody>" +
      renderDocumentRows(asList(documentTable.rows), sourceVisibility) +
      "</tbody></table></div></section>" +
      '<section class="v2-card v2-workbenchUi__pane"><div class="v2-workbenchUi__paneHeader"><h3>Datum Grid</h3><p>' +
      escapeHtml(
        lens === "raw"
          ? "Canonical datum rows rendered through the raw payload lens."
          : "Spreadsheet-like interpreted rows for the selected authoritative document."
      ) +
      "</p></div>" +
      (asText(datumGrid.group_mode) === "layer_value_group_iteration" && layers.length
        ? matrixHtml
        : groups.length
        ? groupHtml
        : '<div class="v2-tableWrap v2-workbenchUi__tableWrap"><table class="v2-table v2-workbenchUiTable"><thead class="v2-workbenchUi__stickyHeader"><tr><th>Datum</th><th>' +
          escapeHtml(lens === "raw" ? "Raw Payload" : "Interpreted Row") +
          "</th><th>Identity</th><th>Action</th></tr></thead><tbody>" +
          renderDatumRows(flatRows, { lens: lens, offset: 0 }) +
          "</tbody></table></div>") +
      "</section></div>" +
      renderWorkbenchNavigation(workspace) +
      renderNotes(surfacePayload.notes || [])
    );
  }

  function bindWorkbenchNavigation(ctx, target, workspace) {
    var documents = asList(asObject(workspace.document_table).rows);
    var datumRows = flattenDatumRows(workspace);
    var navigation = asObject(workspace.navigation);

    function loadRequest(request) {
      if (!request || typeof ctx.loadShell !== "function") return;
      ctx.loadShell(request);
    }

    function bindSelectableRows(selector, attrName, items) {
      Array.prototype.forEach.call(target.querySelectorAll(selector), function (node) {
        var index = Number(node.getAttribute(attrName));
        if (Number.isNaN(index) || index < 0 || index >= items.length) return;
        var item = items[index] || {};
        node.addEventListener("click", function (event) {
          if (event.target && event.target.closest && event.target.closest("button")) return;
          loadRequest(item.shell_request);
        });
        node.addEventListener("keydown", function (event) {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            loadRequest(item.shell_request);
            return;
          }
          if (event.key === "ArrowDown" && index + 1 < items.length) {
            event.preventDefault();
            loadRequest((items[index + 1] || {}).shell_request);
            return;
          }
          if (event.key === "ArrowUp" && index - 1 >= 0) {
            event.preventDefault();
            loadRequest((items[index - 1] || {}).shell_request);
          }
        });
      });
    }

    Array.prototype.forEach.call(target.querySelectorAll("button[data-workbench-document-index]"), function (button) {
      button.addEventListener("click", function () {
        var index = Number(button.getAttribute("data-workbench-document-index"));
        if (Number.isNaN(index) || index < 0 || index >= documents.length) return;
        loadRequest((documents[index] || {}).shell_request);
      });
    });

    Array.prototype.forEach.call(target.querySelectorAll("button[data-workbench-row-index]"), function (button) {
      button.addEventListener("click", function () {
        var index = Number(button.getAttribute("data-workbench-row-index"));
        if (Number.isNaN(index) || index < 0 || index >= datumRows.length) return;
        loadRequest((datumRows[index] || {}).shell_request);
      });
    });

    Array.prototype.forEach.call(target.querySelectorAll("[data-workbench-nav-key]"), function (button) {
      button.addEventListener("click", function () {
        var key = button.getAttribute("data-workbench-nav-key") || "";
        loadRequest(asObject(navigation[key]).shell_request);
      });
    });

    bindSelectableRows("tr[data-workbench-document-index]", "data-workbench-document-index", documents);
    bindSelectableRows("tr[data-workbench-row-index]", "data-workbench-row-index", datumRows);
  }

  function renderRegisteredWorkspaceSurface(ctx, target, region, surfacePayload, moduleSpec) {
    var adapter = toolSurfaceAdapter();
    var spec = asObject(moduleSpec);
    var renderer = resolveRegisteredModuleExport(spec.moduleId, spec.globalName);
    if (renderer && typeof renderer.render === "function") {
      renderer.render(ctx, target, surfacePayload);
      return;
    }
    if (typeof window.__MYCITE_V2_LOAD_SHELL_MODULE === "function" && asText(spec.moduleId)) {
      adapter.renderWrappedSurface(
        target,
        {
          state: "loading",
          title: region.title || surfacePayload.title || spec.label || "Workbench",
          message: "Loading deferred renderer module…",
          warnings: [],
          readiness: {},
          toolId: asText(spec.moduleId),
        },
        ""
      );
      window.__MYCITE_V2_LOAD_SHELL_MODULE(spec.moduleId, {
        reason: "reflective_workspace:" + (asText(spec.label) || asText(spec.moduleId) || "unknown"),
      })
        .then(function () {
          var resolved = resolveRegisteredModuleExport(spec.moduleId, spec.globalName);
          if (resolved && typeof resolved.render === "function") {
            resolved.render(ctx, target, surfacePayload);
            return;
          }
          adapter.renderWrappedSurface(
            target,
            adapter.resolveSurfaceState({
              region: region,
              surfacePayload: surfacePayload,
              title: region.title || surfacePayload.title || spec.label || "Workbench",
              unsupported: true,
              message: buildModuleRegistrationMessage(
                spec.label || "workspace",
                spec.moduleId,
                spec.globalName,
                "render"
              ),
            }),
            ""
          );
        })
        .catch(function (error) {
          adapter.renderWrappedSurface(
            target,
            adapter.resolveSurfaceState({
              region: region,
              surfacePayload: surfacePayload,
              title: region.title || surfacePayload.title || spec.label || "Workbench",
              unsupported: true,
              message:
                buildModuleRegistrationMessage(
                  spec.label || "workspace",
                  spec.moduleId,
                  spec.globalName,
                  "render"
                ) +
                " " +
                asText(error && error.message),
            }),
            ""
          );
        });
      return;
    }
    adapter.renderWrappedSurface(
      target,
      adapter.resolveSurfaceState({
        region: region,
        surfacePayload: surfacePayload,
        title: region.title || surfacePayload.title || spec.label || "Workbench",
        unsupported: true,
        message: buildModuleRegistrationMessage(
          spec.label || "workspace",
          spec.moduleId,
          spec.globalName,
          "render"
        ),
      }),
      ""
    );
  }

  function renderWorkbenchUiSurface(ctx, target, region, surfacePayload) {
    var adapter = toolSurfaceAdapter();
    if (
      adapter.renderWrappedSurface(
        target,
        adapter.resolveSurfaceState({
          region: region,
          surfacePayload: surfacePayload,
          title: region.title || "Workbench UI",
          hasContent: true,
        }),
        renderWorkbenchSurface(surfacePayload)
      )
    ) {
      bindWorkbenchNavigation(ctx, target, asObject(surfacePayload.workspace));
    }
  }

  function renderReflectiveWorkspaceHost(ctx, target, region, surfacePayload) {
    var adapter = toolSurfaceAdapter();
    var mode =
      (adapter &&
        typeof adapter.resolveReflectiveWorkspaceMode === "function" &&
        adapter.resolveReflectiveWorkspaceMode(region, surfacePayload)) ||
      "generic_surface";
    var moduleSpec =
      (adapter &&
        typeof adapter.resolveReflectiveWorkspaceModuleSpec === "function" &&
        adapter.resolveReflectiveWorkspaceModuleSpec(region, surfacePayload)) ||
      {};

    // Handle loading state
    if (mode === "loading") {
      target.innerHTML =
        '<section class="v2-card" style="margin:12px">' +
        '<h3>Loading Workbench</h3>' +
        '<p>Loading tool workbench renderer...</p>' +
        '</section>';
      return;
    }

    if (mode === "registered_workspace" && asObject(moduleSpec).moduleId) {
      renderRegisteredWorkspaceSurface(ctx, target, region, surfacePayload, moduleSpec);
      return;
    }
    if (mode === "workbench_ui_surface") {
      renderWorkbenchUiSurface(ctx, target, region, surfacePayload);
      return;
    }

    // Fallback for tools without specific workbench
    if (mode === "generic_surface" && !region.sections && !region.cards && !region.rows) {
      target.innerHTML =
        '<section class="v2-card" style="margin:12px">' +
        '<h3>Workbench</h3>' +
        '<p>This tool does not provide a workbench view. ' +
        'Use the interface panel to interact with the tool.</p>' +
        '</section>';
      return;
    }

    renderGenericSurface(ctx, target, region, surfacePayload);
  }

  function renderDatumFileWorkbenchHeader(region) {
    var sandbox = asObject(region && region.sandbox);
    var sandboxLabel = asText(sandbox.label) || asText(sandbox.id) || "Sandbox";
    var subtitle = asText(region && region.subtitle);
    return (
      '<header class="v2-card" style="margin-bottom:12px">' +
      '<h2 style="margin:0">' +
      escapeHtml(asText(region && region.title) || "Datum File Workbench") +
      "</h2>" +
      '<p style="margin:4px 0 0 0"><small>Sandbox: ' +
      escapeHtml(sandboxLabel) +
      "</small>" +
      (subtitle ? "<br /><small>" + escapeHtml(subtitle) + "</small>" : "") +
      "</p>" +
      "</header>"
    );
  }

  function renderLayeredDatumTable(region) {
    var table = asObject(region && region.layered_datum_table);
    var doc = asObject(table.document);
    var layerGroups = asList(table.layer_groups);
    var rows = asList(table.rows);
    var heading =
      '<header class="v2-card" style="margin-bottom:12px">' +
      "<h3>" +
      escapeHtml(stripJsonSuffix(asText(doc.canonical_name) || asText(doc.document_name) || asText(doc.document_id) || "Datum file")) +
      "</h3>" +
      ((asText(doc.document_name) || asText(doc.document_id))
        ? '<small>' +
          escapeHtml(stripJsonSuffix(asText(doc.document_name) || asText(doc.document_id))) +
          "</small>"
        : "") +
      "</header>";
    if (layerGroups.length) {
      return (
        heading +
        layerGroups
          .map(function (layer) {
            var valueGroups = asList(layer.value_groups);
            return (
              '<details class="v2-card" open style="margin-top:12px"><summary>' +
              escapeHtml(
                asText(layer.label) +
                  " (" +
                  String(asList(layer.rows).length || layer.row_count || 0) +
                  " rows)"
              ) +
              "</summary>" +
              valueGroups
                .map(function (vg) {
                  var vgRows = asList(vg.rows);
                  return (
                    '<details class="v2-card" open style="margin-top:12px"><summary>' +
                    escapeHtml(
                      asText(vg.label) +
                        " (" +
                        String(vgRows.length || vg.row_count || 0) +
                        " rows)"
                    ) +
                    "</summary>" +
                    '<div class="v2-tableWrap"><table class="v2-table"><thead><tr><th>Iter</th><th>Datum</th><th>Value</th><th>Action</th></tr></thead><tbody>' +
                    vgRows
                      .map(function (row) {
                        var coords = asObject(row.coordinates);
                        var editActions = asList(row.edit_actions);
                        var editAction = asObject(editActions[0]);
                        return (
                          "<tr><td>" +
                          escapeHtml(coords.iteration != null ? String(coords.iteration) : "—") +
                          "</td><td>" +
                          escapeHtml(asText(row.label) || asText(row.datum_id) || "Datum") +
                          "</td><td>" +
                          escapeHtml(asText(row.display_value) || asText(row.primary_value_token) || "—") +
                          "</td><td>" +
                          (asText(editAction.action)
                            ? '<button type="button" data-datum-edit-action="' +
                              escapeHtml(asText(editAction.action)) +
                              '" data-datum-document-id="' +
                              escapeHtml(asText(editAction.document_id)) +
                              '" data-datum-address="' +
                              escapeHtml(asText(editAction.datum_address)) +
                              '" data-datum-sandbox-id="' +
                              escapeHtml(asText(editAction.sandbox_id)) +
                              '">Edit</button>'
                            : "—") +
                          "</td></tr>"
                        );
                      })
                      .join("") +
                    "</tbody></table></div></details>"
                  );
                })
                .join("") +
              "</details>"
            );
          })
          .join("")
      );
    }
    if (!rows.length) {
      return (
        heading +
        '<section class="v2-card" style="margin-top:12px">' +
        '<p>No datum rows are currently projected for this document.</p>' +
        "</section>"
      );
    }
    return (
      heading +
      '<section class="v2-card" style="margin-top:12px"><div class="v2-tableWrap">' +
      '<table class="v2-table"><thead><tr><th>Datum</th><th>Value</th><th>Action</th></tr></thead><tbody>' +
      rows
        .map(function (row) {
          var rowObj = asObject(row);
          var editActions = asList(rowObj.edit_actions);
          var editAction = asObject(editActions[0]);
          return (
            "<tr><td>" +
            escapeHtml(asText(rowObj.label) || asText(rowObj.datum_id) || "Datum") +
            "</td><td>" +
            escapeHtml(asText(rowObj.display_value) || asText(rowObj.primary_value_token) || "—") +
            "</td><td>" +
            (asText(editAction.action)
              ? '<button type="button" data-datum-edit-action="' +
                escapeHtml(asText(editAction.action)) +
                '" data-datum-document-id="' +
                escapeHtml(asText(editAction.document_id)) +
                '" data-datum-address="' +
                escapeHtml(asText(editAction.datum_address)) +
                '" data-datum-sandbox-id="' +
                escapeHtml(asText(editAction.sandbox_id)) +
                '">Edit</button>'
              : "—") +
            "</td></tr>"
          );
        })
        .join("") +
      "</tbody></table></div></section>"
    );
  }

  function renderSandboxDocumentGallery(region) {
    var gallery = asObject(region && region.gallery);
    var documents = asList(gallery.documents);
    if (!documents.length) {
      return (
        '<section class="v2-card" style="margin-top:12px">' +
        '<h3>Sandbox Document Gallery</h3>' +
        "<p>No datum documents are owned by this sandbox yet.</p>" +
        "</section>"
      );
    }
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Sandbox Document Gallery</h3>' +
      '<div class="v2-card-grid">' +
      documents
        .map(function (card) {
          var cardObj = asObject(card);
          var documentId = asText(cardObj.document_id);
          var canonicalName = stripJsonSuffix(asText(cardObj.canonical_name) || asText(cardObj.label));
          var rawName = stripJsonSuffix(asText(cardObj.document_name) || asText(cardObj.secondary_label) || asText(cardObj.relative_path));
          return (
            '<article class="v2-card' +
            (cardObj.selected ? " is-selected" : "") +
            (cardObj.is_anchor ? " is-anchor" : "") +
            '" tabindex="0" role="button" data-shell-transition-kind="focus_file" data-shell-file-key="' +
            escapeHtml(documentId) +
            '">' +
            "<h3>" +
            escapeHtml(canonicalName || documentId || "Document") +
            (cardObj.is_anchor ? ' <small>(anchor)</small>' : "") +
            "</h3>" +
            ((rawName || documentId)
              ? "<p><small>" + escapeHtml(rawName || documentId) + "</small></p>"
              : "") +
            (documentId ? "<p><small>" + escapeHtml(documentId) + "</small></p>" : "") +
            "<p>Rows: " +
            escapeHtml(String(cardObj.row_count || 0)) +
            "</p>" +
            "</article>"
          );
        })
        .join("") +
      "</div></section>"
    );
  }

  function renderDatumFileWorkbench(ctx, target, region) {
    var mode = asText(region && region.mode) || "anchor";
    var body;
    if (mode === "gallery") {
      body = renderSandboxDocumentGallery(region);
    } else {
      body = renderLayeredDatumTable(region);
    }
    target.innerHTML = renderDatumFileWorkbenchHeader(region) + body;
    bindDatumFileWorkbenchEvents(ctx, target, region);
  }

  function bindDatumFileWorkbenchEvents(ctx, target, region) {
    Array.prototype.forEach.call(target.querySelectorAll("[data-shell-transition-kind]"), function (node) {
      function activate(event) {
        if (event.type === "keydown" && event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        var kind = node.getAttribute("data-shell-transition-kind") || "";
        var fileKey = node.getAttribute("data-shell-file-key") || "";
        if (kind && typeof ctx.dispatchTransition === "function") {
          ctx.dispatchTransition({ kind: kind, file_key: fileKey });
        }
      }
      node.addEventListener("click", activate);
      node.addEventListener("keydown", activate);
    });
    Array.prototype.forEach.call(target.querySelectorAll("[data-datum-edit-action]"), function (node) {
      node.addEventListener("click", function () {
        var table = asObject(region && region.layered_datum_table);
        var documentId = node.getAttribute("data-datum-document-id") || asText(asObject(table.document).document_id);
        var datumAddress = node.getAttribute("data-datum-address") || "";
        var sandboxId = node.getAttribute("data-datum-sandbox-id") || asText(asObject(region && region.sandbox).id);
        var editor = target.querySelector("[data-datum-inline-editor]");
        if (!editor) {
          editor = document.createElement("section");
          editor.className = "v2-card";
          editor.setAttribute("data-datum-inline-editor", "true");
          editor.style.marginTop = "12px";
          target.appendChild(editor);
        }
        editor.innerHTML =
          "<h3>Datum Editor</h3>" +
          "<p><small>" +
          escapeHtml(documentId) +
          " · " +
          escapeHtml(datumAddress) +
          "</small></p>" +
          '<textarea data-datum-edit-payload rows="5" style="width:100%"></textarea>' +
          '<div style="margin-top:8px">' +
          '<button type="button" data-datum-stage>Stage</button> ' +
          '<button type="button" data-datum-validate>Validate</button> ' +
          '<button type="button" data-datum-preview>Preview</button> ' +
          '<button type="button" data-datum-apply>Apply</button> ' +
          '<button type="button" data-datum-discard>Discard</button>' +
          "</div>" +
          '<pre data-datum-edit-status style="white-space:pre-wrap"></pre>';
        bindDatumEditorActions(editor, {
          sandbox_id: sandboxId,
          document_id: documentId,
          datum_address: datumAddress,
          action: node.getAttribute("data-datum-edit-action") || "update_row_raw",
        });
      });
    });
  }

  function bindDatumEditorActions(editor, basePayload) {
    function postMutation(stage) {
      var textarea = editor.querySelector("[data-datum-edit-payload]");
      var status = editor.querySelector("[data-datum-edit-status]");
      var payloadText = textarea ? textarea.value : "";
      var body = {
        target_authority: "datum_workbench",
        operation: basePayload.action,
        sandbox_id: basePayload.sandbox_id,
        document_id: basePayload.document_id,
        datum_address: basePayload.datum_address,
        payload_text: payloadText,
      };
      if (status) status.textContent = "pending " + stage + "...";
      fetch("/portal/api/v2/mutations/" + stage, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
        .then(function (response) {
          return response.json().catch(function () {
            return { ok: response.ok, status: response.status };
          });
        })
        .then(function (payload) {
          if (status) status.textContent = prettyJson(payload);
        })
        .catch(function (error) {
          if (status) status.textContent = String(error && error.message ? error.message : error);
        });
    }
    [
      ["data-datum-stage", "stage"],
      ["data-datum-validate", "validate"],
      ["data-datum-preview", "preview"],
      ["data-datum-apply", "apply"],
      ["data-datum-discard", "discard"],
    ].forEach(function (pair) {
      var node = editor.querySelector("[" + pair[0] + "]");
      if (node) node.addEventListener("click", function () { postMutation(pair[1]); });
    });
  }

  window.PortalShellWorkbenchRenderer = {
    render: function (ctx) {
      var target = ctx.target;
      var region = ctx.region || {};
      var surfacePayload = region.surface_payload || {};
      if (!target) return;
      if (asText(region.kind) === "datum_file_workbench") {
        renderDatumFileWorkbench(ctx, target, region);
        return;
      }
      var adapter = toolSurfaceAdapter();
      var family =
        (adapter && typeof adapter.resolveRegionFamily === "function" && adapter.resolveRegionFamily(region)) ||
        "";
      var mode =
        (adapter &&
          typeof adapter.resolveReflectiveWorkspaceMode === "function" &&
          adapter.resolveReflectiveWorkspaceMode(region, surfacePayload)) ||
        "generic_surface";
      if (family === "reflective_workspace" || mode !== "generic_surface") {
        renderReflectiveWorkspaceHost(ctx, target, region, surfacePayload);
        return;
      }
      renderGenericSurface(ctx, target, region, surfacePayload);
    },
  };
  if (typeof window.__MYCITE_V2_REGISTER_SHELL_MODULE === "function") {
    window.__MYCITE_V2_REGISTER_SHELL_MODULE("workbench_renderers");
  }
})();
