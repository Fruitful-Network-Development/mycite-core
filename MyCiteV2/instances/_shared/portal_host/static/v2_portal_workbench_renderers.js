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
          renderTable({ columns: subsection.columns, items: subsection.rows || [] }) +
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

  function renderGenericSurface(target, surfacePayload) {
    target.innerHTML =
      renderCards(surfacePayload.cards || []) +
      renderSections(surfacePayload.sections || []) +
      renderNotes(surfacePayload.notes || []);
  }

  window.PortalShellWorkbenchRenderer = {
    render: function (ctx) {
      var target = ctx.target;
      var region = ctx.region || {};
      var surfacePayload = region.surface_payload || {};
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
      }
      if (
        window.PortalSystemWorkspaceRenderer &&
        typeof window.PortalSystemWorkspaceRenderer.render === "function" &&
        surfacePayload.kind === "system_workspace"
      ) {
        window.PortalSystemWorkspaceRenderer.render(ctx, target, surfacePayload);
        return;
      }
      if (
        window.PortalNetworkWorkspaceRenderer &&
        typeof window.PortalNetworkWorkspaceRenderer.render === "function" &&
        surfacePayload.kind === "network_system_log_workspace"
      ) {
        window.PortalNetworkWorkspaceRenderer.render(ctx, target, surfacePayload);
        return;
      }
      if (surfacePayload.kind === "tool_secondary_evidence") {
        if (surfacePayload.tool_id === "cts_gis") {
          var sourceEvidence = surfacePayload.source_evidence || {};
          var readiness = sourceEvidence.readiness || {};
          target.innerHTML =
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
          return;
        }
        target.innerHTML =
          '<section class="v2-card"><h3>' +
          escapeHtml(region.title || "Supporting Evidence") +
          "</h3><p>" +
          escapeHtml(region.subtitle || "This tool is currently leading through the interface panel.") +
          "</p></section>";
        return;
      }
      renderGenericSurface(target, surfacePayload);
    },
  };
})();
