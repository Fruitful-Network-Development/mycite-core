/**
 * Interface-panel renderer for the one-shell portal.
 */
(function () {
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderRows(rows) {
    if (!rows || !rows.length) {
      return '<p class="ide-controlpanel__empty">No interface panel details.</p>';
    }
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

  function renderEntryButtons(entries, kind) {
    if (!entries || !entries.length) {
      return '<p class="ide-controlpanel__empty">No items available.</p>';
    }
    return (
      '<div class="cts-gis-entryList">' +
      entries
        .map(function (entry, index) {
          return (
            '<button type="button" class="cts-gis-entryButton' +
            (entry.selected ? " is-active" : "") +
            '" data-cts-gis-entry-kind="' +
            escapeHtml(kind) +
            '" data-cts-gis-entry-index="' +
            String(index) +
            '">' +
            '<span class="cts-gis-entryButton__title">' +
            escapeHtml(entry.label || entry.node_id || entry.token || "Item") +
            "</span>" +
            (entry.node_id
              ? '<span class="cts-gis-entryButton__meta">' + escapeHtml(entry.node_id) + "</span>"
              : "") +
            (entry.detail
              ? '<span class="cts-gis-entryButton__meta">' + escapeHtml(entry.detail) + "</span>"
              : "") +
            "</button>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function bindShellRequestEntries(target, ctx, entriesByKind) {
    Array.prototype.forEach.call(target.querySelectorAll("[data-cts-gis-entry-kind]"), function (node) {
      node.addEventListener("click", function () {
        var kind = node.getAttribute("data-cts-gis-entry-kind") || "";
        var index = Number(node.getAttribute("data-cts-gis-entry-index"));
        var entries = entriesByKind[kind] || [];
        var entry = entries[index] || {};
        if (entry.shell_request) {
          ctx.loadShell(entry.shell_request);
        }
      });
    });
  }

  function renderProfileSummaries(items) {
    if (!items || !items.length) {
      return '<p class="ide-controlpanel__empty">No correlated profiles.</p>';
    }
    return (
      '<div class="cts-gis-profileSummaryList">' +
      items
        .map(function (item) {
          return (
            '<article class="cts-gis-profileSummary">' +
            '<strong>' +
            escapeHtml(item.profile_label || item.node_id || "profile") +
            "</strong>" +
            '<span class="cts-gis-profileSummary__meta">' +
            escapeHtml(item.node_id || "") +
            "</span>" +
            '<span class="cts-gis-profileSummary__meta">' +
            escapeHtml(item.relation || "") +
            "</span>" +
            "</article>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderCtsGisInspector(ctx, target, region, surfacePayload) {
    var interfaceBody = region.interface_body || {};
    var contextStrip = interfaceBody.context_strip || {};
    var diktataograph = interfaceBody.diktataograph || {};
    var garland = interfaceBody.garland || {};
    var entriesByKind = {
      lineage: diktataograph.lineage || [],
      navigation: diktataograph.navigation_entries || [],
      intention: diktataograph.intention_entries || [],
      row: garland.row_entries || [],
    };
    target.innerHTML =
      '<div class="system-tool-interface cts-gis-interface">' +
      '<section class="v2-card cts-gis-contextStrip">' +
      '<h3>' +
      escapeHtml((contextStrip && contextStrip.title) || "CTS-GIS Context") +
      "</h3>" +
      renderRows((contextStrip && contextStrip.items) || []) +
      "</section>" +
      '<div class="system-tool-interface__body cts-gis-interface__body" data-cts-gis-layout="' +
      escapeHtml(interfaceBody.layout || "dual_section") +
      '" data-cts-gis-narrow-layout="' +
      escapeHtml(interfaceBody.narrow_layout || "context_diktataograph_garland_stack") +
      '">' +
      '<section class="v2-card cts-gis-pane cts-gis-pane--diktataograph">' +
      '<header class="cts-gis-pane__header"><h3>' +
      escapeHtml(diktataograph.title || "Diktataograph") +
      "</h3><p>" +
      escapeHtml(diktataograph.summary || "") +
      "</p></header>" +
      '<section class="cts-gis-pane__section"><h4>Lineage</h4>' +
      renderEntryButtons(diktataograph.lineage || [], "lineage") +
      "</section>" +
      '<section class="cts-gis-pane__section"><h4>Structure</h4>' +
      renderEntryButtons(diktataograph.navigation_entries || [], "navigation") +
      "</section>" +
      '<section class="cts-gis-pane__section"><h4>Projection Rule</h4>' +
      renderEntryButtons(diktataograph.intention_entries || [], "intention") +
      "</section>" +
      "</section>" +
      '<section class="v2-card cts-gis-pane cts-gis-pane--garland">' +
      '<header class="cts-gis-pane__header"><h3>' +
      escapeHtml(garland.title || "Garland") +
      "</h3><p>" +
      escapeHtml(garland.summary || "") +
      "</p></header>" +
      '<section class="cts-gis-pane__section"><h4>Profile Projection</h4>' +
      renderRows(garland.summary_rows || []) +
      "</section>" +
      '<section class="cts-gis-pane__section"><h4>Projected Rows</h4>' +
      renderEntryButtons(garland.row_entries || [], "row") +
      "</section>" +
      '<section class="cts-gis-pane__section"><h4>Correlated Profiles</h4>' +
      renderProfileSummaries(garland.related_profiles || []) +
      "</section>" +
      ((garland.warnings || []).length
        ? '<section class="cts-gis-pane__section"><h4>Warnings</h4><ul class="cts-gis-warningList">' +
          (garland.warnings || [])
            .map(function (warning) {
              return "<li>" + escapeHtml(warning) + "</li>";
            })
            .join("") +
          "</ul></section>"
        : "") +
      "</section>" +
      "</div>" +
      "</div>";
    bindShellRequestEntries(target, ctx, entriesByKind);
  }

  window.PortalShellInspectorRenderer = {
    render: function (ctx) {
      var target = ctx.target;
      var region = ctx.region || {};
      var sections = region.sections || [];
      var surfacePayload = region.surface_payload || {};
      if (!target) return;
      if (
        window.PortalAwsCsmInspectorRenderer &&
        typeof window.PortalAwsCsmInspectorRenderer.render === "function" &&
        region.kind === "aws_csm_inspector"
      ) {
        window.PortalAwsCsmInspectorRenderer.render(ctx, target, surfacePayload);
        return;
      }
      if (
        window.PortalNetworkInspectorRenderer &&
        typeof window.PortalNetworkInspectorRenderer.render === "function" &&
        region.kind === "network_system_log_inspector"
      ) {
        window.PortalNetworkInspectorRenderer.render(ctx, target, surfacePayload);
        return;
      }
      if (region.kind === "tool_mediation_panel" && region.interface_body && region.interface_body.kind === "cts_gis_interface_body") {
        renderCtsGisInspector(ctx, target, region, surfacePayload);
        return;
      }
      target.innerHTML =
        '<div class="v2-inspector-stack">' +
        (region.subject
          ? '<section class="v2-card"><h3>Subject</h3>' +
            renderRows([
              {
                label: region.subject.level || "level",
                value: region.subject.id || "—",
              },
            ]) +
            "</section>"
          : "") +
        (!region.subject && !sections.length
          ? '<section class="v2-card"><h3>Interface Panel</h3><p>' +
            escapeHtml(region.summary || "Select an item to load interface panel content.") +
            "</p></section>"
          : "") +
        sections
          .map(function (section) {
            return (
              '<section class="v2-card" style="margin-top:12px"><h3>' +
              escapeHtml(section.title || "Section") +
              "</h3>" +
              renderRows(section.rows || []) +
              "</section>"
            );
          })
          .join("") +
        "</div>";
    },
  };
})();
