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
          escapeHtml(row.document_name || row.label || row.document_id || "—") +
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
    return (
      '<div class="v2-workbenchUi__primaryCell"><strong>' +
      escapeHtml(row.labels || "—") +
      "</strong>" +
      '<div class="v2-workbenchUi__subvalue">' +
      escapeHtml((row.relation || "—") + " -> " + (row.object_ref || "—")) +
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

  function renderWorkbenchSummary(workspace) {
    var selectedDocument = asObject(workspace.selected_document);
    var selectedRow = asObject(workspace.selected_row);
    var query = asObject(workspace.query);
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Current Lens</h3>' +
      '<dl class="v2-surface-dl">' +
      "<dt>document</dt><dd><strong>" +
      escapeHtml(selectedDocument.document_name || selectedDocument.document_id || "—") +
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
      (groups.length
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

  window.PortalShellWorkbenchRenderer = {
    render: function (ctx) {
      var target = ctx.target;
      var region = ctx.region || {};
      var surfacePayload = region.surface_payload || {};
      var adapter = toolSurfaceAdapter();
      if (!target) return;
      if (region.visible === false) {
        target.innerHTML = "";
        return;
      }
      if (
        window.PortalAwsCsmWorkspaceRenderer &&
        typeof window.PortalAwsCsmWorkspaceRenderer.render === "function" &&
        surfacePayload.kind === "aws_csm_workspace"
      ) {
        window.PortalAwsCsmWorkspaceRenderer.render(ctx, target, surfacePayload);
        return;
      } else if (surfacePayload.kind === "aws_csm_workspace") {
        adapter.renderWrappedSurface(
          target,
          adapter.resolveSurfaceState({
            region: region,
            surfacePayload: surfacePayload,
            title: "AWS-CSM",
            unsupported: true,
            message: "The AWS-CSM workspace renderer is unavailable.",
          }),
          ""
        );
        return;
      }
      if (
        window.PortalSystemWorkspaceRenderer &&
        typeof window.PortalSystemWorkspaceRenderer.render === "function" &&
        surfacePayload.kind === "system_workspace"
      ) {
        window.PortalSystemWorkspaceRenderer.render(ctx, target, surfacePayload);
        return;
      } else if (surfacePayload.kind === "system_workspace") {
        adapter.renderWrappedSurface(
          target,
          adapter.resolveSurfaceState({
            region: region,
            surfacePayload: surfacePayload,
            title: "System",
            unsupported: true,
            message: "The system workspace renderer is unavailable.",
          }),
          ""
        );
        return;
      }
      if (
        window.PortalNetworkWorkspaceRenderer &&
        typeof window.PortalNetworkWorkspaceRenderer.render === "function" &&
        surfacePayload.kind === "network_system_log_workspace"
      ) {
        window.PortalNetworkWorkspaceRenderer.render(ctx, target, surfacePayload);
        return;
      } else if (surfacePayload.kind === "network_system_log_workspace") {
        adapter.renderWrappedSurface(
          target,
          adapter.resolveSurfaceState({
            region: region,
            surfacePayload: surfacePayload,
            title: "NETWORK",
            unsupported: true,
            message: "The NETWORK workspace renderer is unavailable.",
          }),
          ""
        );
        return;
      }
      if (surfacePayload.kind === "workbench_ui_surface") {
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
        return;
      }
      if (surfacePayload.kind === "tool_secondary_evidence") {
        var secondaryHtml = "";
        if (surfacePayload.tool_id === "cts_gis") {
          var sourceEvidence = surfacePayload.source_evidence || {};
          var readiness = sourceEvidence.readiness || {};
          secondaryHtml =
            '<section class="v2-card"><h3>' +
            escapeHtml(region.title || "CTS-GIS Evidence") +
            "</h3><p>" +
            escapeHtml(region.subtitle || "Secondary evidence remains workbench-only.") +
            '</p><dl class="v2-surface-dl">' +
            "<dt>Readiness</dt><dd><strong>" +
            escapeHtml(readiness.state || "pending") +
            "</strong><br />" +
            escapeHtml(readiness.message || "") +
            "</dd>" +
            "<dt>Tool spec</dt><dd><strong>" +
            escapeHtml((sourceEvidence.tool_spec && sourceEvidence.tool_spec.file) || "spec.json") +
            "</strong></dd>" +
            "<dt>Tool anchor</dt><dd><strong>" +
            escapeHtml((sourceEvidence.tool_anchor && sourceEvidence.tool_anchor.file) || "tool.<msn>.cts-gis.json") +
            "</strong></dd>" +
            "<dt>Registrar payload</dt><dd><strong>" +
            escapeHtml((sourceEvidence.registrar_payload && sourceEvidence.registrar_payload.file) || "registrar.json") +
            "</strong></dd>" +
            "<dt>Administrative source</dt><dd><strong>" +
            escapeHtml((sourceEvidence.administrative_source && sourceEvidence.administrative_source.document_name) || "—") +
            "</strong></dd>" +
            "</dl></section>";
        } else {
          secondaryHtml =
            '<section class="v2-card"><h3>' +
            escapeHtml(region.title || "Supporting Evidence") +
            "</h3><p>" +
            escapeHtml(region.subtitle || "This tool is currently leading through the interface panel.") +
            "</p></section>";
        }
        adapter.renderWrappedSurface(
          target,
          adapter.resolveSurfaceState({
            region: region,
            surfacePayload: surfacePayload,
            title: region.title || "Supporting Evidence",
            hasContent: true,
          }),
          secondaryHtml
        );
        return;
      }
      renderGenericSurface(ctx, target, region, surfacePayload);
    },
  };
})();
