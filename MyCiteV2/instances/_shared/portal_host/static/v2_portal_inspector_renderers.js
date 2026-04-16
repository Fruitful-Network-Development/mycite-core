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

  function nodeParts(nodeId) {
    var token = String(nodeId || "");
    if (!token) return [];
    return token.split("-").filter(function (part) {
      return part !== "";
    });
  }

  function sortNodeEntries(entries) {
    return (entries || []).slice().sort(function (left, right) {
      var leftDepth = Number(left.depth || nodeParts(left.node_id).length || 0);
      var rightDepth = Number(right.depth || nodeParts(right.node_id).length || 0);
      if (leftDepth !== rightDepth) return leftDepth - rightDepth;
      return String(left.node_id || "").localeCompare(String(right.node_id || ""));
    });
  }

  function renderCanvasNodeButton(entry, kind, className) {
    var buttonClass = className || "cts-gis-entryButton";
    return (
      '<button type="button" class="' +
      escapeHtml(buttonClass) +
      (entry.selected ? " is-active" : "") +
      '" data-cts-gis-entry-kind="' +
      escapeHtml(kind) +
      '" data-cts-gis-entry-index="' +
      String(Number(entry._renderIndex || 0)) +
      '">' +
      '<span class="cts-gis-entryButton__title">' +
      escapeHtml(entry.label || entry.node_id || "Node") +
      "</span>" +
      (entry.node_id
        ? '<span class="cts-gis-entryButton__meta">' + escapeHtml(entry.node_id) + "</span>"
        : "") +
      (entry.detail
        ? '<span class="cts-gis-entryButton__meta">' + escapeHtml(entry.detail) + "</span>"
        : "") +
      "</button>"
    );
  }

  function groupNavigationByBranch(entries, activeNodeId) {
    var rootParts = nodeParts(activeNodeId);
    var rootDepth = rootParts.length;
    var grouped = {};
    sortNodeEntries(entries).forEach(function (entry) {
      var parts = nodeParts(entry.node_id);
      var branchKey = parts.slice(0, Math.min(parts.length, rootDepth + 1)).join("-");
      if (!branchKey) branchKey = String(entry.node_id || "");
      if (!grouped[branchKey]) {
        grouped[branchKey] = {
          branchKey: branchKey,
          entries: [],
        };
      }
      grouped[branchKey].entries.push(entry);
    });
    return Object.keys(grouped)
      .sort(function (left, right) {
        return left.localeCompare(right);
      })
      .map(function (key) {
        var entriesForKey = sortNodeEntries(grouped[key].entries);
        var lead = entriesForKey.find(function (entry) {
          return nodeParts(entry.node_id).length === rootDepth + 1;
        }) || entriesForKey[0] || {};
        return {
          branchKey: key,
          lead: lead,
          entries: entriesForKey.filter(function (entry) {
            return String(entry.node_id || "") !== String((lead || {}).node_id || "");
          }),
        };
      });
  }

  function renderStructureCanvas(anchoredPathEntries, structureEntries, activeNodeId) {
    var pathEntries = anchoredPathEntries || [];
    var nodeEntries = structureEntries || [];
    var branches = groupNavigationByBranch(nodeEntries, activeNodeId);
    var activePathEntry =
      pathEntries.find(function (entry) {
        return entry.selected;
      }) ||
      pathEntries[pathEntries.length - 1] ||
      nodeEntries.find(function (entry) {
        return entry.selected;
      }) || {
        label: activeNodeId || "Structure root",
        node_id: activeNodeId || "",
        detail: "",
      };

    return (
      '<div class="cts-gis-structureCanvas">' +
      '<div class="cts-gis-structureCanvas__pathway">' +
      (pathEntries.length
        ? pathEntries
            .map(function (entry, index) {
              return (
                '<div class="cts-gis-canvasColumnWrap">' +
                '<span class="cts-gis-canvasColumnWrap__step">Layer ' +
                escapeHtml(String(index + 1)) +
                "</span>" +
                '<button type="button" class="cts-gis-canvasColumn' +
                (entry.selected ? " is-active" : "") +
                '" style="--cts-gis-column-step:' +
                escapeHtml(String(index + 1)) +
                '" data-cts-gis-entry-kind="path" data-cts-gis-entry-index="' +
                String(Number(entry._renderIndex || 0)) +
                '">' +
                '<span class="cts-gis-canvasColumn__label">' +
                escapeHtml(entry.label || entry.node_id || "Path") +
                "</span>" +
                '<span class="cts-gis-canvasColumn__meta">' +
                escapeHtml(entry.node_id || "") +
                "</span>" +
                "</button></div>"
              );
            })
            .join("")
        : '<p class="ide-controlpanel__empty">No anchored path yet.</p>') +
      "</div>" +
      '<section class="cts-gis-structureCanvas__focusCard">' +
      '<span class="cts-gis-structureCanvas__eyebrow">Navigation Root</span>' +
      "<strong>" +
      escapeHtml(activePathEntry.label || activePathEntry.node_id || "Structure root") +
      "</strong>" +
      '<span class="cts-gis-structureCanvas__meta">' +
      escapeHtml(activePathEntry.node_id || "") +
      "</span>" +
      (activePathEntry.detail
        ? '<span class="cts-gis-structureCanvas__meta">' + escapeHtml(activePathEntry.detail) + "</span>"
        : "") +
      "</section>" +
      '<div class="cts-gis-structureCanvas__branches">' +
      (branches.length
        ? branches
            .map(function (branch) {
              return (
                '<section class="cts-gis-branchCluster" data-cts-gis-node-group="' +
                escapeHtml(branch.branchKey) +
                '">' +
                '<div class="cts-gis-branchCluster__lead">' +
                renderCanvasNodeButton(
                  branch.lead,
                  "node",
                  "cts-gis-entryButton cts-gis-entryButton--node cts-gis-entryButton--branchLead"
                ) +
                "</div>" +
                '<div class="cts-gis-branchCluster__entries">' +
                (branch.entries.length
                  ? branch.entries
                      .map(function (entry) {
                        return renderCanvasNodeButton(
                          entry,
                          "node",
                          "cts-gis-entryButton cts-gis-entryButton--node cts-gis-entryButton--branchLeaf"
                        );
                      })
                      .join("")
                  : '<p class="ide-controlpanel__empty">No deeper nodes.</p>') +
                "</div>" +
                "</section>"
              );
            })
            .join("")
        : '<p class="ide-controlpanel__empty">No structure addresses are available for this navigation root.</p>') +
      "</div>" +
      "</div>"
    );
  }

  function collectGeometryPoints(geometry) {
    var geo = geometry || {};
    if (geo.type === "Point") {
      return [geo.coordinates || []];
    }
    if (geo.type === "Polygon") {
      return (geo.coordinates || []).reduce(function (all, ring) {
        return all.concat(ring || []);
      }, []);
    }
    if (geo.type === "MultiPolygon") {
      return (geo.coordinates || []).reduce(function (all, polygon) {
        return all.concat(
          (polygon || []).reduce(function (memo, ring) {
            return memo.concat(ring || []);
          }, [])
        );
      }, []);
    }
    return [];
  }

  function normalizeFeatureBounds(bounds, features) {
    if (bounds && bounds.length === 4) return bounds;
    var points = [];
    (features || []).forEach(function (feature) {
      points = points.concat(collectGeometryPoints((feature || {}).geometry));
    });
    if (!points.length) return [-1, -1, 1, 1];
    var xs = points.map(function (point) {
      return Number(point[0] || 0);
    });
    var ys = points.map(function (point) {
      return Number(point[1] || 0);
    });
    return [
      Math.min.apply(Math, xs),
      Math.min.apply(Math, ys),
      Math.max.apply(Math, xs),
      Math.max.apply(Math, ys),
    ];
  }

  function projectPoint(point, bounds, width, height, pad) {
    var minX = Number(bounds[0] || 0);
    var minY = Number(bounds[1] || 0);
    var maxX = Number(bounds[2] || minX + 1);
    var maxY = Number(bounds[3] || minY + 1);
    var safeWidth = Math.max(0.0001, maxX - minX);
    var safeHeight = Math.max(0.0001, maxY - minY);
    var usableWidth = width - pad * 2;
    var usableHeight = height - pad * 2;
    var x = pad + ((Number(point[0] || 0) - minX) / safeWidth) * usableWidth;
    var y = height - pad - ((Number(point[1] || 0) - minY) / safeHeight) * usableHeight;
    return [x, y];
  }

  function renderFeatureShape(feature, bounds, width, height, pad) {
    var geometry = (feature || {}).geometry || {};
    var featureId = escapeHtml(feature.feature_id || "");
    var className = "cts-gis-mapStage__shape" + (feature.selected ? " is-selected" : "");
    if (geometry.type === "Point") {
      var point = projectPoint(geometry.coordinates || [], bounds, width, height, pad);
      return (
        '<circle class="' +
        className +
        '" data-feature-id="' +
        featureId +
        '" cx="' +
        String(point[0]) +
        '" cy="' +
        String(point[1]) +
        '" r="' +
        String(feature.selected ? 8 : 5.5) +
        '"></circle>'
      );
    }
    if (geometry.type === "Polygon") {
      var ring = ((geometry.coordinates || [])[0] || []).map(function (point) {
        var projected = projectPoint(point, bounds, width, height, pad);
        return String(projected[0]) + "," + String(projected[1]);
      });
      if (!ring.length) return "";
      return (
        '<polygon class="' +
        className +
        '" data-feature-id="' +
        featureId +
        '" points="' +
        escapeHtml(ring.join(" ")) +
        '"></polygon>'
      );
    }
    return "";
  }

  function renderGeospatialStage(geospatialProjection) {
    var collection = (geospatialProjection || {}).feature_collection || {};
    var features = collection.features || [];
    if (!features.length) {
      return (
        '<div class="cts-gis-mapStage cts-gis-mapStage--empty">' +
        '<p class="ide-controlpanel__empty">' +
        escapeHtml((geospatialProjection || {}).empty_message || "No projected geometry is available for the current navigation root.") +
        "</p></div>"
      );
    }
    var width = 560;
    var height = 360;
    var pad = 24;
    var bounds = normalizeFeatureBounds((geospatialProjection || {}).collection_bounds || collection.bounds || [], features);
    var selectedFeature = features.find(function (feature) {
      return feature.selected;
    }) || features[0] || {};
    return (
      '<div class="cts-gis-mapStage">' +
      '<div class="cts-gis-mapStage__frame">' +
      '<svg class="cts-gis-mapStage__svg" viewBox="0 0 ' +
      String(width) +
      " " +
      String(height) +
      '" role="img" aria-label="CTS-GIS geospatial projection">' +
      '<rect class="cts-gis-mapStage__backdrop" x="0" y="0" width="' +
      String(width) +
      '" height="' +
      String(height) +
      '"></rect>' +
      features
        .map(function (feature) {
          return renderFeatureShape(feature, bounds, width, height, pad);
        })
        .join("") +
      "</svg></div>" +
      '<div class="cts-gis-mapStage__caption">' +
      '<span class="cts-gis-mapStage__eyebrow">Projection Focus</span>' +
      "<strong>" +
      escapeHtml(selectedFeature.label || selectedFeature.node_id || "Projected feature") +
      "</strong>" +
      '<span class="cts-gis-mapStage__meta">' +
      escapeHtml(selectedFeature.node_id || "") +
      "</span>" +
      "</div></div>"
    );
  }

  function renderProfileHierarchy(entries) {
    if (!entries || !entries.length) {
      return '<p class="ide-controlpanel__empty">No hierarchy is available.</p>';
    }
    return (
      '<div class="cts-gis-profileHierarchy">' +
      entries
        .map(function (entry) {
          return (
            '<button type="button" class="cts-gis-profileHierarchy__item' +
            (entry.selected ? " is-active" : "") +
            '" data-cts-gis-entry-kind="path" data-cts-gis-entry-index="' +
            String(Number(entry._renderIndex || 0)) +
            '">' +
            '<span class="cts-gis-profileHierarchy__label">' +
            escapeHtml(entry.label || entry.node_id || "Node") +
            "</span>" +
            '<span class="cts-gis-profileHierarchy__meta">' +
            escapeHtml(entry.node_id || "") +
            "</span></button>"
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
          supporting_document_name: "",
          projection_document_name: "",
          selected_feature_id: "",
          selected_feature_geometry_type: "",
          selected_feature_bounds: [],
          collection_bounds: [],
          empty_message: "No projected geometry is available for the current navigation root.",
          feature_collection: {
            type: "FeatureCollection",
            features: [],
            bounds: [],
          },
          features: [],
        },
        profile_projection: {
          title: "Profile Projection",
          active_profile: {
            label: "",
            node_id: "",
            feature_count: 0,
            child_count: 0,
          },
          hierarchy: diktataograph.lineage || [],
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
    Array.prototype.forEach.call(target.querySelectorAll(".cts-gis-branchCluster__entries"), function (lane) {
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
    (anchoredPath.entries || []).forEach(function (entry, index) {
      entry._renderIndex = index;
    });
    (structureField.entries || []).forEach(function (entry, index) {
      entry._renderIndex = index;
    });
    (projectionRuleField.entries || []).forEach(function (entry, index) {
      entry._renderIndex = index;
    });
    (profileProjection.projected_rows || []).forEach(function (entry, index) {
      entry._renderIndex = index;
    });
    (geospatialProjection.features || []).forEach(function (entry, index) {
      entry._renderIndex = index;
    });
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
      renderStructureCanvas(anchoredPath.entries || [], structureField.entries || [], navigationCanvas.active_node_id || "") +
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
      renderGeospatialStage(geospatialProjection) +
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
      '<section class="cts-gis-garlandSplit__profileBlock"><h5>Hierarchy</h5>' +
      renderProfileHierarchy(profileProjection.hierarchy || []) +
      "</section>" +
      '<section class="cts-gis-garlandSplit__profileBlock"><h5>Current Profile</h5>' +
      '<article class="cts-gis-profileSummary cts-gis-profileSummary--active">' +
      "<strong>" +
      escapeHtml((profileProjection.active_profile || {}).label || "Active profile") +
      "</strong>" +
      '<span class="cts-gis-profileSummary__meta">' +
      escapeHtml((profileProjection.active_profile || {}).node_id || "") +
      "</span>" +
      '<span class="cts-gis-profileSummary__meta">' +
      escapeHtml(
        String((profileProjection.active_profile || {}).feature_count || 0) +
          " features · " +
          String((profileProjection.active_profile || {}).child_count || 0) +
          " children"
      ) +
      "</span>" +
      "</article></section>" +
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
