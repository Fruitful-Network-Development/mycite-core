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

  function renderCompactContextStrip(items) {
    if (!items || !items.length) {
      return '<p class="ide-controlpanel__empty">No context.</p>';
    }
    return (
      '<div class="cts-gis-contextStrip__row">' +
      items
        .map(function (item) {
          return (
            '<div class="cts-gis-contextChip">' +
            '<span class="cts-gis-contextChip__label">' +
            escapeHtml(item.label || "Context") +
            "</span>" +
            '<span class="cts-gis-contextChip__value">' +
            escapeHtml(item.value || "—") +
            "</span>" +
            (item.detail
              ? '<span class="cts-gis-contextChip__detail">' + escapeHtml(item.detail) + "</span>"
              : "") +
            "</div>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderRequestButtons(entries, kind, options) {
    var opts = options || {};
    var listClass = opts.listClass || "cts-gis-entryList";
    var buttonClass = opts.buttonClass || "cts-gis-entryButton";
    var emptyMessage = opts.emptyMessage || "No items available.";
    if (!entries || !entries.length) {
      return '<p class="ide-controlpanel__empty">' + escapeHtml(emptyMessage) + "</p>";
    }
    return (
      '<div class="' +
      escapeHtml(listClass) +
      '">' +
      entries
        .map(function (entry, index) {
          return (
            '<button type="button" class="' +
            escapeHtml(buttonClass) +
            (entry.selected ? " is-active" : "") +
            '" data-cts-gis-entry-kind="' +
            escapeHtml(kind) +
            '" data-cts-gis-entry-index="' +
            String(index) +
            '">' +
            '<span class="cts-gis-entryButton__title">' +
            escapeHtml(entry.label || entry.node_id || entry.token || entry.feature_id || "Item") +
            "</span>" +
            (entry.node_id
              ? '<span class="cts-gis-entryButton__meta">' + escapeHtml(entry.node_id) + "</span>"
              : "") +
            (entry.geometry_type
              ? '<span class="cts-gis-entryButton__meta">' + escapeHtml(entry.geometry_type) + "</span>"
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
            "<strong>" +
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

  function renderNavigationLanes(entries) {
    if (!entries || !entries.length) {
      return '<p class="ide-controlpanel__empty">No structure addresses are available.</p>';
    }
    var grouped = {};
    entries.forEach(function (entry) {
      var depth = Number(entry.depth || 0);
      var lane = Number.isFinite(depth) && depth > 0 ? depth : 0;
      if (!grouped[lane]) grouped[lane] = [];
      grouped[lane].push(entry);
    });
    var lanes = Object.keys(grouped)
      .map(function (key) {
        return Number(key);
      })
      .sort(function (a, b) {
        return a - b;
      });
    return (
      '<div class="cts-gis-navField__lanes">' +
      lanes
        .map(function (depth) {
          return (
            '<section class="cts-gis-navLane" data-cts-gis-lane="' +
            String(depth) +
            '">' +
            '<h5 class="cts-gis-navLane__title">Depth ' +
            String(depth) +
            "</h5>" +
            renderRequestButtons(grouped[depth] || [], "node", {
              listClass: "cts-gis-navLane__entries",
              buttonClass: "cts-gis-entryButton cts-gis-entryButton--node",
            }) +
            "</section>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function normalizeCtsGisInterfaceBody(interfaceBody) {
    var body = interfaceBody || {};
    if (body.navigation_canvas && body.garland_split_projection) {
      return body;
    }
    var diktataograph = body.diktataograph || {};
    var garland = body.garland || {};
    return {
      kind: body.kind || "cts_gis_interface_body",
      layout: body.layout || "dual_section",
      narrow_layout: body.narrow_layout || "context_diktataograph_garland_stack",
      feature_flags: body.feature_flags || {},
      context_strip: body.context_strip || { title: "CTS-GIS Context", compact: true, items: [] },
      navigation_canvas: {
        kind: "diktataograph_navigation_canvas",
        title: diktataograph.title || "Diktataograph",
        summary: diktataograph.summary || "",
        anchored_path: {
          title: "Anchored Path",
          entries: diktataograph.lineage || [],
        },
        structure_field: {
          title: "Structure Field",
          entries: diktataograph.navigation_entries || [],
        },
        projection_rule_field: {
          title: "Projection Rule",
          entries: diktataograph.intention_entries || [],
        },
      },
      garland_split_projection: {
        kind: "garland_split_projection",
        title: garland.title || "Garland",
        summary: garland.summary || "",
        geospatial_projection: {
          title: "Geospatial Projection",
          projection_state: "",
          feature_count: 0,
          render_feature_count: 0,
          render_row_count: 0,
          selected_feature_id: "",
          selected_feature_geometry_type: "",
          selected_feature_bounds: [],
          collection_bounds: [],
          empty_message: "No projected geometry is available for the current navigation root.",
          features: [],
        },
        profile_projection: {
          title: "Profile Projection",
          summary_rows: garland.summary_rows || [],
          projected_rows: garland.row_entries || [],
          correlated_profiles: garland.related_profiles || [],
          warnings: garland.warnings || [],
        },
      },
    };
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

  function bindNavigationCanvasEnhancement(target, enabled) {
    if (!enabled) return;
    Array.prototype.forEach.call(target.querySelectorAll(".cts-gis-navLane__entries"), function (lane) {
      var buttons = Array.prototype.slice.call(lane.querySelectorAll(".cts-gis-entryButton--node"));
      if (!buttons.length) return;

      function applyWeights(activeIndex) {
        buttons.forEach(function (button, index) {
          var delta = activeIndex < 0 ? 999 : Math.abs(index - activeIndex);
          var weight = activeIndex < 0 ? 1 : Math.max(1, 4 - delta);
          button.style.setProperty("--cts-gis-nav-weight", String(weight));
        });
      }

      applyWeights(-1);
      lane.addEventListener("mousemove", function (event) {
        var hit = event.target && event.target.closest ? event.target.closest(".cts-gis-entryButton--node") : null;
        if (!hit) return;
        var idx = buttons.indexOf(hit);
        if (idx >= 0) applyWeights(idx);
      });
      lane.addEventListener("mouseleave", function () {
        applyWeights(-1);
      });
    });
  }

  function renderCtsGisInspector(ctx, target, region) {
    var interfaceBody = normalizeCtsGisInterfaceBody(region.interface_body || {});
    var contextStrip = interfaceBody.context_strip || {};
    var navigationCanvas = interfaceBody.navigation_canvas || {};
    var anchoredPath = navigationCanvas.anchored_path || {};
    var structureField = navigationCanvas.structure_field || {};
    var projectionRuleField = navigationCanvas.projection_rule_field || {};
    var garlandSplit = interfaceBody.garland_split_projection || {};
    var geospatialProjection = garlandSplit.geospatial_projection || {};
    var profileProjection = garlandSplit.profile_projection || {};
    var entriesByKind = {
      path: anchoredPath.entries || [],
      node: structureField.entries || [],
      rule: projectionRuleField.entries || [],
      row: profileProjection.projected_rows || [],
      feature: geospatialProjection.features || [],
      lineage: anchoredPath.entries || [],
      navigation: structureField.entries || [],
      intention: projectionRuleField.entries || [],
    };

    target.innerHTML =
      '<div class="system-tool-interface cts-gis-interface">' +
      '<section class="cts-gis-contextStrip cts-gis-contextStrip--compact">' +
      '<h3>' +
      escapeHtml((contextStrip && contextStrip.title) || "CTS-GIS Context") +
      "</h3>" +
      renderCompactContextStrip((contextStrip && contextStrip.items) || []) +
      "</section>" +
      '<div class="system-tool-interface__body cts-gis-interface__body" data-cts-gis-layout="' +
      escapeHtml(interfaceBody.layout || "dual_section") +
      '" data-cts-gis-narrow-layout="' +
      escapeHtml(interfaceBody.narrow_layout || "context_diktataograph_garland_stack") +
      '">' +
      '<section class="v2-card cts-gis-pane cts-gis-pane--diktataograph">' +
      '<header class="cts-gis-pane__header"><h3>' +
      escapeHtml(navigationCanvas.title || "Diktataograph") +
      "</h3><p>" +
      escapeHtml(navigationCanvas.summary || "") +
      "</p></header>" +
      '<section class="cts-gis-navCanvas" data-cts-gis-nav-canvas="structure">' +
      '<section class="cts-gis-navField cts-gis-navField--anchoredPath"><h4>' +
      escapeHtml(anchoredPath.title || "Anchored Path") +
      "</h4>" +
      renderRequestButtons(anchoredPath.entries || [], "path", {
        listClass: "cts-gis-navField__pathEntries",
        buttonClass: "cts-gis-entryButton cts-gis-entryButton--path",
        emptyMessage: "No anchored path yet.",
      }) +
      "</section>" +
      '<section class="cts-gis-navField cts-gis-navField--structureField"><h4>' +
      escapeHtml(structureField.title || "Structure Field") +
      "</h4>" +
      renderNavigationLanes(structureField.entries || []) +
      "</section>" +
      '<section class="cts-gis-navField cts-gis-navField--projectionRules"><h4>' +
      escapeHtml(projectionRuleField.title || "Projection Rule") +
      "</h4>" +
      renderRequestButtons(projectionRuleField.entries || [], "rule", {
        listClass: "cts-gis-navField__ruleEntries",
        buttonClass: "cts-gis-entryButton cts-gis-entryButton--rule",
        emptyMessage: "No projection rules are available.",
      }) +
      "</section>" +
      "</section>" +
      "</section>" +
      '<section class="v2-card cts-gis-pane cts-gis-pane--garland">' +
      '<header class="cts-gis-pane__header"><h3>' +
      escapeHtml(garlandSplit.title || "Garland") +
      "</h3><p>" +
      escapeHtml(garlandSplit.summary || "") +
      "</p></header>" +
      '<div class="cts-gis-garlandSplit">' +
      '<section class="cts-gis-garlandSplit__geospatial"><h4>' +
      escapeHtml(geospatialProjection.title || "Geospatial Projection") +
      "</h4>" +
      '<div class="cts-gis-mapCanvas">' +
      '<div class="cts-gis-mapCanvas__state">' +
      '<span class="cts-gis-mapCanvas__status">state: ' +
      escapeHtml(geospatialProjection.projection_state || "inspect_only") +
      "</span>" +
      '<span class="cts-gis-mapCanvas__status">features: ' +
      escapeHtml(String(geospatialProjection.feature_count || 0)) +
      "</span>" +
      '<span class="cts-gis-mapCanvas__status">rows: ' +
      escapeHtml(String(geospatialProjection.render_row_count || 0)) +
      "</span>" +
      "</div>" +
      ((geospatialProjection.collection_bounds || []).length
        ? '<p class="cts-gis-mapCanvas__meta">collection bounds: ' +
          escapeHtml((geospatialProjection.collection_bounds || []).join(", ")) +
          "</p>"
        : "") +
      ((geospatialProjection.selected_feature_id || "")
        ? '<p class="cts-gis-mapCanvas__meta">selected feature: ' +
          escapeHtml(geospatialProjection.selected_feature_id || "") +
          (geospatialProjection.selected_feature_geometry_type
            ? " (" + escapeHtml(geospatialProjection.selected_feature_geometry_type || "") + ")"
            : "") +
          "</p>"
        : "") +
      ((geospatialProjection.selected_feature_bounds || []).length
        ? '<p class="cts-gis-mapCanvas__meta">selected bounds: ' +
          escapeHtml((geospatialProjection.selected_feature_bounds || []).join(", ")) +
          "</p>"
        : "") +
      '<div class="cts-gis-mapCanvas__featureList">' +
      renderRequestButtons(geospatialProjection.features || [], "feature", {
        listClass: "cts-gis-mapCanvas__featureEntries",
        buttonClass: "cts-gis-entryButton cts-gis-entryButton--feature",
        emptyMessage: geospatialProjection.empty_message || "No projected geometry is available for the current navigation root.",
      }) +
      "</div>" +
      "</div>" +
      "</section>" +
      '<section class="cts-gis-garlandSplit__profile"><h4>' +
      escapeHtml(profileProjection.title || "Profile Projection") +
      "</h4>" +
      renderRows(profileProjection.summary_rows || []) +
      '<section class="cts-gis-garlandSplit__profileBlock"><h5>Projected Rows</h5>' +
      renderRequestButtons(profileProjection.projected_rows || [], "row", {
        emptyMessage: "No projected rows available.",
      }) +
      "</section>" +
      '<section class="cts-gis-garlandSplit__profileBlock"><h5>Correlated Profiles</h5>' +
      renderProfileSummaries(profileProjection.correlated_profiles || []) +
      "</section>" +
      ((profileProjection.warnings || []).length
        ? '<section class="cts-gis-garlandSplit__profileBlock"><h5>Warnings</h5><ul class="cts-gis-warningList">' +
          (profileProjection.warnings || [])
            .map(function (warning) {
              return "<li>" + escapeHtml(warning) + "</li>";
            })
            .join("") +
          "</ul></section>"
        : "") +
      "</section>" +
      "</div>" +
      "</section>" +
      "</div>" +
      "</div>";
    bindShellRequestEntries(target, ctx, entriesByKind);
    bindNavigationCanvasEnhancement(target, !!((interfaceBody.feature_flags || {}).hover_attention_redistribution));
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
        renderCtsGisInspector(ctx, target, region);
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
