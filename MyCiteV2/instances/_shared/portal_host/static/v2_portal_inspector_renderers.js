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

  function toolSurfaceAdapter() {
    return window.PortalToolSurfaceAdapter || {};
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

  function directoryOptionTitle(option, depth) {
    var title = String((option && option.title) || "");
    return depth === 1 && title ? title.toUpperCase() : title;
  }

  function selectedDirectoryOption(dropdown) {
    var selectedNodeId = String((dropdown && dropdown.selected_node_id) || "");
    if (!selectedNodeId) return null;
    var options = (dropdown && dropdown.options) || [];
    var optionIndex = options.findIndex(function (option) {
      return String((option && option.node_id) || "") === selectedNodeId;
    });
    if (optionIndex < 0) return null;
    return {
      option: options[optionIndex] || {},
      optionIndex: optionIndex,
    };
  }

  function renderDirectorySelectionBlocks(dropdowns) {
    return (dropdowns || [])
      .map(function (dropdown, dropdownIndex) {
        var selected = selectedDirectoryOption(dropdown);
        if (!selected) return "";
        var option = selected.option || {};
        var depth = Number(dropdown.depth || dropdownIndex + 1);
        var title = directoryOptionTitle(option, depth);
        return (
          '<section class="cts-gis-stageSelectionBlock">' +
          '<button type="button" class="cts-gis-stageColumn' +
          (option.selected ? " is-active" : "") +
          '" data-cts-gis-dropdown-index="' +
          escapeHtml(String(dropdownIndex)) +
          '" data-cts-gis-option-index="' +
          escapeHtml(String(selected.optionIndex)) +
          '">' +
          '<span class="cts-gis-stageColumn__frame">' +
          '<span class="cts-gis-stageColumn__text">' +
          '<span class="cts-gis-stageColumn__nodeId">' +
          escapeHtml(option.node_id || "") +
          "</span>" +
          (title
            ? '<span class="cts-gis-stageColumn__title">' + escapeHtml(title) + "</span>"
            : "") +
          "</span>" +
          "</span>" +
          "</button>" +
          "</section>"
        );
      })
      .join("");
  }

  function renderDirectoryStageTable(dropdown, dropdownIndex) {
    var depth = Number((dropdown && dropdown.depth) || dropdownIndex + 1);
    var options = (dropdown && dropdown.options) || [];
    var prompt = depth === 1 ? "Select address node" : "Select child node";
    return (
      '<section class="cts-gis-stageTable">' +
      '<header class="cts-gis-stageTable__header">' +
      '<span class="cts-gis-stageTable__eyebrow">Depth ' +
      escapeHtml(String(depth)) +
      "</span>" +
      '<span class="cts-gis-stageTable__prompt">' +
      escapeHtml(prompt) +
      "</span>" +
      "</header>" +
      (options.length
        ? '<div class="cts-gis-stageTable__rows">' +
          options
            .map(function (option, optionIndex) {
              var title = directoryOptionTitle(option, depth);
              return (
                '<button type="button" class="cts-gis-stageRow' +
                (option.selected ? " is-active" : "") +
                '" data-cts-gis-dropdown-index="' +
                escapeHtml(String(dropdownIndex)) +
                '" data-cts-gis-option-index="' +
                escapeHtml(String(optionIndex)) +
                '">' +
                '<span class="cts-gis-stageRow__nodeId">' +
                escapeHtml(option.node_id || "") +
                "</span>" +
                '<span class="cts-gis-stageRow__title">' +
                escapeHtml(title || "") +
                "</span>" +
                "</button>"
              );
            })
            .join("") +
          "</div>"
        : renderProjectionPlaceholder("No SAMRAS address options are available.", "cts-gis-stageTable__empty")) +
      "</section>"
    );
  }

  function renderDirectoryDropdownCanvas(navigationCanvas) {
    var dropdowns = navigationCanvas.dropdowns || [];
    var decodeState = navigationCanvas.decode_state || "blocked_invalid_magnitude";
    var currentDropdown = dropdowns.length ? dropdowns[dropdowns.length - 1] : null;
    var ancestorDropdowns = dropdowns.slice(0, Math.max(dropdowns.length - 1, 0));
    return (
      '<div class="cts-gis-directoryCanvas">' +
      (currentDropdown
        ? '<div class="cts-gis-stageSelector">' +
          renderDirectorySelectionBlocks(ancestorDropdowns) +
          renderDirectoryStageTable(currentDropdown, dropdowns.length - 1) +
          "</div>"
        : renderProjectionPlaceholder(
            decodeState === "ready"
              ? "No SAMRAS address options are available."
              : "CTS-GIS navigation is blocked until the active SAMRAS magnitude and node bindings are repaired.",
            "cts-gis-directoryCanvas__empty"
          )) +
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

  function renderStagedDiktataographCanvas(stagedBlocks) {
    var blocks = stagedBlocks || [];
    return (
      '<div class="cts-gis-stagedDiktataograph">' +
      (blocks.length
        ? blocks
            .map(function (block, blockIndex) {
              var entries = block.entries || [];
              var rowHeight = entries.length ? 100 / entries.length : 100;
              return (
                '<section class="cts-gis-lineageBlockWrap" data-cts-gis-lineage-wrap data-block-index="' +
                escapeHtml(String(blockIndex)) +
                '" data-block-id="' +
                escapeHtml(block.block_id || ("block_" + String(blockIndex))) +
                '" data-spawn-from-node-id="' +
                escapeHtml(block.spawn_from_node_id || "") +
                '">' +
                '<article class="cts-gis-lineageBlock" data-cts-gis-lineage-block data-block-id="' +
                escapeHtml(block.block_id || ("block_" + String(blockIndex))) +
                '" data-selected-node-id="' +
                escapeHtml(block.selected_node_id || "") +
                '">' +
                '<header class="cts-gis-lineageBlock__header">' +
                '<span class="cts-gis-lineageBlock__eyebrow">Depth ' +
                escapeHtml(String(block.depth || 0)) +
                "</span>" +
                '<span class="cts-gis-lineageBlock__anchor">' +
                escapeHtml(block.anchor_title || block.anchor_node_id || "root") +
                "</span>" +
                "</header>" +
                '<div class="cts-gis-lineageBlock__rows">' +
                (entries.length
                  ? entries
                      .map(function (entry, entryIndex) {
                        return (
                          '<button type="button" class="cts-gis-lineageRow' +
                          (entry.selected ? " is-active" : "") +
                          (entry.in_active_path ? " is-in-path" : "") +
                          '" data-cts-gis-entry-kind="staged_row" data-cts-gis-entry-index="' +
                          String(Number(entry._renderIndex || 0)) +
                          '" data-row-index="' +
                          escapeHtml(String(entryIndex)) +
                          '" data-row-node-id="' +
                          escapeHtml(entry.node_id || "") +
                          '" style="--row-top:' +
                          escapeHtml(String(entryIndex * rowHeight)) +
                          '%; --row-height:' +
                          escapeHtml(String(rowHeight)) +
                          '%; --row-font-size:0.78rem; --row-opacity:1; --row-label-opacity:1;">' +
                          '<span class="cts-gis-lineageRow__label">' +
                          escapeHtml(entry.label || entry.title || entry.node_id || "Node") +
                          "</span>" +
                          '<span class="cts-gis-lineageRow__meta">' +
                          escapeHtml(entry.msn_id || entry.node_id || "") +
                          "</span>" +
                          "</button>"
                        );
                      })
                      .join("")
                  : '<div class="cts-gis-lineageBlock__empty"><p class="ide-controlpanel__empty">No staged rows available.</p></div>') +
                "</div>" +
                "</article>" +
                "</section>"
              );
            })
            .join("")
        : '<p class="ide-controlpanel__empty">No staged lineage blocks are available.</p>') +
      "</div>"
    );
  }

  function renderOrderedHierarchyCanvas(orderedHierarchy, activeNodeId) {
    var hierarchy = orderedHierarchy || {};
    var columns = hierarchy.columns || [];
    var activePath = hierarchy.active_path || [];
    var selectedNodeId = hierarchy.selected_node_id || activeNodeId || "";
    return (
      '<div class="cts-gis-orderedHierarchy">' +
      '<section class="cts-gis-orderedHierarchy__spine">' +
      '<h4>Lineage Spine</h4>' +
      '<div class="cts-gis-orderedHierarchy__path">' +
      (activePath.length
        ? activePath
            .map(function (entry) {
              var titleText = entry.title || "";
              return (
                '<button type="button" class="cts-gis-orderedPathNode' +
                (entry.selected ? " is-active" : "") +
                '" data-cts-gis-entry-kind="ordered_path" data-cts-gis-entry-index="' +
                String(Number(entry._renderIndex || 0)) +
                '">' +
                '<span class="cts-gis-orderedPathNode__msn">' +
                escapeHtml(entry.msn_id || entry.node_id || "—") +
                "</span>" +
                '<span class="cts-gis-orderedPathNode__title">' +
                escapeHtml(titleText) +
                "</span>" +
                "</button>"
              );
            })
            .join("")
        : '<p class="ide-controlpanel__empty">No lineage path is available.</p>') +
      "</div>" +
      "</section>" +
      '<section class="cts-gis-orderedHierarchy__columns">' +
      (columns.length
        ? columns
            .map(function (column) {
              var anchorNodeId = column.anchor_msn_id || column.anchor_node_id || "";
              var anchorTitle = column.anchor_title || "";
              return (
                '<article class="cts-gis-orderedColumn" data-cts-gis-column-depth="' +
                escapeHtml(String(column.depth || 0)) +
                '">' +
                '<header class="cts-gis-orderedColumn__header">' +
                '<span class="cts-gis-orderedColumn__eyebrow">Depth ' +
                escapeHtml(String(column.depth || 0)) +
                "</span>" +
                '<span class="cts-gis-orderedColumn__anchor">' +
                escapeHtml(anchorNodeId || "root") +
                (anchorTitle ? " · " + escapeHtml(anchorTitle) : "") +
                "</span>" +
                "</header>" +
                '<div class="cts-gis-orderedColumn__rows">' +
                ((column.entries || []).length
                  ? (column.entries || [])
                      .map(function (entry) {
                        return (
                          '<button type="button" class="cts-gis-orderedNode' +
                          (entry.selected ? " is-active" : "") +
                          (entry.in_active_path ? " is-in-path" : "") +
                          '" style="--cts-gis-ordered-step:' +
                          escapeHtml(String(column.depth || 1)) +
                          '" data-cts-gis-entry-kind="ordered_node" data-cts-gis-entry-index="' +
                          String(Number(entry._renderIndex || 0)) +
                          '">' +
                          '<span class="cts-gis-orderedNode__msn">' +
                          escapeHtml(entry.msn_id || entry.node_id || "") +
                          "</span>" +
                          '<span class="cts-gis-orderedNode__title">' +
                          escapeHtml(entry.title || "") +
                          "</span>" +
                          "</button>"
                        );
                      })
                      .join("")
                  : '<p class="ide-controlpanel__empty">No nodes at this depth.</p>') +
                "</div>" +
                "</article>"
              );
            })
            .join("")
        : '<p class="ide-controlpanel__empty">No hierarchy columns are available.</p>') +
      "</section>" +
      '<p class="cts-gis-orderedHierarchy__selected">selected: ' +
      escapeHtml(selectedNodeId || "—") +
      "</p>" +
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

  function ringPathData(ring, bounds, width, height, pad) {
    var projected = (ring || []).map(function (point) {
      var xy = projectPoint(point, bounds, width, height, pad);
      return String(xy[0]) + " " + String(xy[1]);
    });
    if (!projected.length) return "";
    return "M " + projected.join(" L ") + " Z";
  }

  function polygonPathData(polygons, bounds, width, height, pad) {
    return (polygons || [])
      .map(function (polygon) {
        return (polygon || [])
          .map(function (ring) {
            return ringPathData(ring, bounds, width, height, pad);
          })
          .filter(Boolean)
          .join(" ");
      })
      .filter(Boolean)
      .join(" ");
  }

  function renderFeatureShape(feature, bounds, width, height, pad) {
    var geometry = (feature || {}).geometry || {};
    var featureId = escapeHtml(feature.feature_id || feature.id || "");
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
    if (geometry.type === "Polygon" || geometry.type === "MultiPolygon") {
      var pathData = polygonPathData(
        geometry.type === "Polygon" ? [geometry.coordinates || []] : geometry.coordinates || [],
        bounds,
        width,
        height,
        pad
      );
      if (!pathData) return "";
      return (
        '<path class="' +
        className +
        '" data-feature-id="' +
        featureId +
        '" fill-rule="evenodd" d="' +
        escapeHtml(pathData) +
        '"></path>'
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
            escapeHtml(entry.display_label || entry.title || entry.node_id || "Node") +
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

  function renderProjectionPlaceholder(message, className) {
    return (
      '<div class="' +
      escapeHtml(className || "cts-gis-projectionPlaceholder") +
      '"><p class="ide-controlpanel__empty">' +
      escapeHtml(message || "No projection available.") +
      "</p></div>"
    );
  }

  function renderWarningList(items, className) {
    if (!items || !items.length) return "";
    return (
      '<ul class="' +
      escapeHtml(className || "cts-gis-warningList") +
      '">' +
      items
        .map(function (item) {
          return "<li>" + escapeHtml(item || "") + "</li>";
        })
        .join("") +
      "</ul>"
    );
  }

  function renderNavigationDiagnostics(diagnostics) {
    if (!diagnostics || !diagnostics.length) return "";
    return (
      '<section class="cts-gis-navDiagnostics">' +
      "<h4>Diagnostics</h4>" +
      '<div class="cts-gis-navDiagnostics__items">' +
      diagnostics
        .map(function (item) {
          return (
            '<article class="cts-gis-navDiagnostics__item">' +
            '<strong>' +
            escapeHtml(item.code || item.severity || "notice") +
            "</strong>" +
            '<span class="cts-gis-navDiagnostics__meta">' +
            escapeHtml(item.message || "") +
            "</span>" +
            "</article>"
          );
        })
        .join("") +
      "</div>" +
      "</section>"
    );
  }

  function normalizeCtsGisInterfaceBody(interfaceBody) {
    var body = interfaceBody || {};
    if (body.navigation_canvas && body.garland_split_projection) {
      var navCanvas = body.navigation_canvas || {};
      body.navigation_canvas = Object.assign({}, navCanvas, {
        mode: navCanvas.mode || "directory_dropdowns",
        source_authority: navCanvas.source_authority || "samras_magnitude",
        decode_state: navCanvas.decode_state || "blocked_invalid_magnitude",
        diagnostics: navCanvas.diagnostics || [],
        dropdowns: navCanvas.dropdowns || [],
        active_path: navCanvas.active_path || [],
        active_node_id: navCanvas.active_node_id || "",
      });
      body.garland_split_projection.geospatial_projection = Object.assign(
        {
          projection_source: "none",
          decode_summary: {
            reference_binding_count: 0,
            decoded_coordinate_count: 0,
            failed_token_count: 0,
          },
          warnings: [],
        },
        body.garland_split_projection.geospatial_projection || {}
      );
      body.garland_split_projection.profile_projection = Object.assign(
        {
          has_profile_state: false,
        },
        body.garland_split_projection.profile_projection || {}
      );
      return body;
    }
    var garland = body.garland || {};
    return {
      kind: body.kind || "cts_gis_interface_body",
      layout: body.layout || "diktataograph_garland_split",
      narrow_layout: body.narrow_layout || "diktataograph_garland_stack",
      feature_flags: body.feature_flags || {},
      navigation_canvas: {
        kind: "diktataograph_navigation_canvas",
        title: "Diktataograph",
        summary: "",
        mode: "directory_dropdowns",
        source_authority: "samras_magnitude",
        decode_state: "blocked_invalid_magnitude",
        diagnostics: [],
        dropdowns: [],
        active_path: [],
        active_node_id: "",
      },
      garland_split_projection: {
        kind: "garland_split_projection",
        title: garland.title || "Garland",
        summary: garland.summary || "",
        geospatial_projection: {
          title: "Geospatial Projection",
          projection_state: "",
          projection_source: "none",
          feature_count: 0,
          render_feature_count: 0,
          render_row_count: 0,
          decode_summary: {
            reference_binding_count: 0,
            decoded_coordinate_count: 0,
            failed_token_count: 0,
          },
          warnings: [],
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
          has_real_projection: false,
        },
        profile_projection: {
          title: "Profile Projection",
          active_profile: {
            label: "",
            node_id: "",
            feature_count: 0,
            child_count: 0,
          },
          hierarchy: [],
          summary_rows: garland.summary_rows || [],
          projected_rows: garland.row_entries || [],
          correlated_profiles: garland.related_profiles || [],
          warnings: garland.warnings || [],
          empty_message: "No projected profile is available until the active path resolves real CTS-GIS evidence.",
          has_profile_state: false,
          has_real_projection: false,
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

  function bindDirectoryDropdowns(target, ctx, dropdowns) {
    function loadSelection(dropdownIndex, optionIndex) {
      if (!Number.isFinite(dropdownIndex) || !Number.isFinite(optionIndex)) return;
      var dropdown = (dropdowns || [])[dropdownIndex] || {};
      var option = (dropdown.options || [])[optionIndex] || {};
      if (option.shell_request) {
        ctx.loadShell(option.shell_request);
      }
    }

    Array.prototype.forEach.call(target.querySelectorAll("[data-cts-gis-dropdown-index]"), function (node) {
      var dropdownIndex = Number(node.getAttribute("data-cts-gis-dropdown-index"));
      if ((node.tagName || "").toUpperCase() === "SELECT") {
        node.addEventListener("change", function () {
          if (node.value === "") return;
          loadSelection(dropdownIndex, Number(node.value));
        });
        return;
      }
      if (!node.hasAttribute("data-cts-gis-option-index")) return;
      node.addEventListener("click", function () {
        loadSelection(dropdownIndex, Number(node.getAttribute("data-cts-gis-option-index")));
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

  function bindOrderedHierarchyEnhancement(target) {
    Array.prototype.forEach.call(target.querySelectorAll(".cts-gis-orderedColumn__rows"), function (lane) {
      var buttons = Array.prototype.slice.call(lane.querySelectorAll(".cts-gis-orderedNode"));
      if (!buttons.length) return;

      function applyWeights(activeIndex) {
        buttons.forEach(function (button, index) {
          var delta = activeIndex < 0 ? 999 : Math.abs(index - activeIndex);
          var weight = activeIndex < 0 ? 1 : Math.max(1, 5 - delta);
          button.style.setProperty("--cts-gis-ordered-weight", String(weight));
        });
      }

      applyWeights(-1);
      lane.addEventListener("mousemove", function (event) {
        var hit = event.target && event.target.closest ? event.target.closest(".cts-gis-orderedNode") : null;
        if (!hit) return;
        var idx = buttons.indexOf(hit);
        if (idx >= 0) applyWeights(idx);
      });
      lane.addEventListener("mouseleave", function () {
        applyWeights(-1);
      });
    });
  }

  function bindStagedDiktataographEnhancement(target) {
    var stage = target.querySelector(".cts-gis-stagedDiktataograph");
    var wraps = Array.prototype.slice.call(target.querySelectorAll("[data-cts-gis-lineage-wrap]"));
    if (!stage || !wraps.length) return;

    function clamp(value, min, max) {
      return Math.max(min, Math.min(max, value));
    }

    wraps.forEach(function (wrap, wrapIndex) {
      var block = wrap.querySelector("[data-cts-gis-lineage-block]");
      var rowsContainer = wrap.querySelector(".cts-gis-lineageBlock__rows");
      var rows = Array.prototype.slice.call(wrap.querySelectorAll(".cts-gis-lineageRow"));
      if (!block || !rowsContainer || !rows.length) return;

      var selectedNodeId = block.getAttribute("data-selected-node-id") || "";
      var selectedIndex = rows.findIndex(function (row) {
        return (row.getAttribute("data-row-node-id") || "") === selectedNodeId;
      });
      var focusIndex = selectedIndex >= 0 ? selectedIndex : (rows.length - 1) / 2;
      var targetFocusIndex = focusIndex;
      var lastY = rowsContainer.clientHeight / 2;
      var lastMoveTime = performance.now();
      var speedBoost = 0;
      var hovering = false;

      var MIN_H = 2;
      var MAX_H = 64;
      var BASE_SPREAD = 3.2;
      var EXTRA_SPREAD = 22;
      var SPEED_SMOOTHING = 0.16;
      var FOCUS_SMOOTHING = 0.2;
      var LABEL_THRESHOLD = 10;

      function defaultHeights(height) {
        var total = rows.length || 1;
        var perRow = height / total;
        return rows.map(function (_, index) {
          return {
            top: perRow * index,
            height: perRow,
            fontSize: 12,
            opacity: 1,
            labelOpacity: 1,
          };
        });
      }

      function applyLayout(layoutRows) {
        var selectedRowTop = 0;
        rows.forEach(function (row, index) {
          var metrics = layoutRows[index] || { top: 0, height: 0, fontSize: 12, opacity: 1, labelOpacity: 1 };
          row.style.setProperty("--row-top", String(metrics.top) + "px");
          row.style.setProperty("--row-height", String(metrics.height) + "px");
          row.style.setProperty("--row-font-size", String(metrics.fontSize) + "px");
          row.style.setProperty("--row-opacity", String(metrics.opacity));
          row.style.setProperty("--row-label-opacity", String(metrics.labelOpacity));
          if (index === selectedIndex) selectedRowTop = metrics.top;
        });
        wrap.style.setProperty("--cts-gis-selected-top", String(selectedRowTop) + "px");
        if (wrapIndex > 0) {
          var parentWrap = wraps[wrapIndex - 1];
          wrap.style.setProperty("--cts-gis-attach-offset", parentWrap.style.getPropertyValue("--cts-gis-selected-top") || "0px");
        } else {
          wrap.style.setProperty("--cts-gis-attach-offset", "0px");
        }
      }

      function layout() {
        var blockHeight = rowsContainer.clientHeight;
        if (!blockHeight) {
          requestAnimationFrame(layout);
          return;
        }
        if (!hovering && selectedIndex < 0) {
          applyLayout(defaultHeights(blockHeight));
          requestAnimationFrame(layout);
          return;
        }

        focusIndex += (targetFocusIndex - focusIndex) * FOCUS_SMOOTHING;
        speedBoost += (0 - speedBoost) * SPEED_SMOOTHING;

        var spread = BASE_SPREAD + speedBoost * EXTRA_SPREAD;
        var heights = new Array(rows.length);
        var sum = 0;

        rows.forEach(function (_, index) {
          var distance = Math.abs(index - focusIndex);
          var weight = 1 / (1 + Math.log1p(distance) / spread);
          var height = MIN_H + (MAX_H - MIN_H) * Math.pow(weight, 3.2);
          heights[index] = height;
          sum += height;
        });

        var scale = blockHeight / Math.max(sum, 1);
        var top = 0;
        var layoutRows = heights.map(function (height, index) {
          var computedHeight = height * scale;
          var distance = Math.abs(index - focusIndex);
          var emphasis = Math.max(0, 1 - distance / (spread * 1.35 + 2));
          var metrics = {
            top: top,
            height: computedHeight,
            fontSize: 8 + emphasis * 20,
            opacity: computedHeight < 5 ? 0.62 : 1,
            labelOpacity: computedHeight < LABEL_THRESHOLD ? 0 : 1,
          };
          top += computedHeight;
          return metrics;
        });

        applyLayout(layoutRows);
        requestAnimationFrame(layout);
      }

      rowsContainer.addEventListener("mousemove", function (event) {
        hovering = true;
        var rect = rowsContainer.getBoundingClientRect();
        var y = clamp(event.clientY - rect.top, 0, rect.height);
        var now = performance.now();
        var dt = Math.max(8, now - lastMoveTime);
        var dy = Math.abs(y - lastY);
        var pxPerMs = dy / dt;

        targetFocusIndex = (y / Math.max(rect.height, 1)) * (rows.length - 1);
        speedBoost = clamp(pxPerMs * 2.6, 0, 1);
        lastY = y;
        lastMoveTime = now;
      });

      rowsContainer.addEventListener("mouseenter", function (event) {
        var rect = rowsContainer.getBoundingClientRect();
        var y = clamp(event.clientY - rect.top, 0, rect.height);
        hovering = true;
        targetFocusIndex = (y / Math.max(rect.height, 1)) * (rows.length - 1);
        lastY = y;
        lastMoveTime = performance.now();
      });

      rowsContainer.addEventListener("mouseleave", function () {
        hovering = false;
        targetFocusIndex = selectedIndex >= 0 ? selectedIndex : focusIndex;
        speedBoost = 0;
      });

      requestAnimationFrame(layout);
    });
  }

  function renderCtsGisInspector(ctx, target, region) {
    var interfaceBody = normalizeCtsGisInterfaceBody(region.interface_body || {});
    var navigationCanvas = interfaceBody.navigation_canvas || {};
    var navMode = navigationCanvas.mode || "directory_dropdowns";
    var garlandSplit = interfaceBody.garland_split_projection || {};
    var geospatialProjection = garlandSplit.geospatial_projection || {};
    var profileProjection = garlandSplit.profile_projection || {};
    var decodeSummary = geospatialProjection.decode_summary || {};
    var activePathEntries = navigationCanvas.active_path || [];
    activePathEntries.forEach(function (entry, index) {
      entry._renderIndex = index;
    });
    (profileProjection.projected_rows || []).forEach(function (entry, index) {
      entry._renderIndex = index;
    });
    (geospatialProjection.features || []).forEach(function (entry, index) {
      entry._renderIndex = index;
    });
    var navigationCanvasMarkup =
      navMode === "directory_dropdowns"
        ? renderDirectoryDropdownCanvas(navigationCanvas)
        : renderProjectionPlaceholder("This CTS-GIS navigation mode is no longer supported.", "cts-gis-directoryCanvas__empty");
    var entriesByKind = {
      path: activePathEntries,
      row: profileProjection.projected_rows || [],
      feature: geospatialProjection.features || [],
    };
    var hasRealGeospatialProjection = !!geospatialProjection.has_real_projection;
    var hasRealProfileProjection = !!profileProjection.has_real_projection;
    var hasProfileState = !!profileProjection.has_profile_state;
    var activeProfile = profileProjection.active_profile || {};
    var activeProfileCounts = hasRealProfileProjection
      ? String(activeProfile.feature_count || 0) + " features · " + String(activeProfile.child_count || 0) + " children"
      : "— features · — children";
    var geospatialMarkup = hasRealGeospatialProjection
      ? '<div class="cts-gis-mapCanvas">' +
        '<div class="cts-gis-mapCanvas__state">' +
        '<span class="cts-gis-mapCanvas__status">state: ' +
        escapeHtml(geospatialProjection.projection_state || "inspect_only") +
        "</span>" +
        '<span class="cts-gis-mapCanvas__status">source: ' +
        escapeHtml(geospatialProjection.projection_source || "none") +
        "</span>" +
        '<span class="cts-gis-mapCanvas__status">features: ' +
        escapeHtml(String(geospatialProjection.feature_count || 0)) +
        "</span>" +
        '<span class="cts-gis-mapCanvas__status">rows: ' +
        escapeHtml(String(geospatialProjection.render_row_count || 0)) +
        "</span>" +
        '<span class="cts-gis-mapCanvas__status">decoded: ' +
        escapeHtml(
          String(decodeSummary.decoded_coordinate_count || 0) +
            "/" +
            String(decodeSummary.reference_binding_count || 0)
        ) +
        "</span>" +
        '<span class="cts-gis-mapCanvas__status">failed: ' +
        escapeHtml(String(decodeSummary.failed_token_count || 0)) +
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
        renderWarningList(geospatialProjection.warnings || []) +
        "</div>"
      : '<div class="cts-gis-mapCanvas cts-gis-mapCanvas--empty">' +
        renderProjectionPlaceholder(
          geospatialProjection.empty_message || "No projected geometry is available until the active path resolves real CTS-GIS evidence.",
          "cts-gis-mapCanvas__empty"
        ) +
        "</div>";
    var profileMarkup = (hasRealProfileProjection || hasProfileState)
      ? '<section class="cts-gis-garlandSplit__profileBody">' +
        '<section class="cts-gis-garlandSplit__profileBlock"><h5>Hierarchy</h5>' +
        renderProfileHierarchy(profileProjection.hierarchy || []) +
        "</section>" +
        '<section class="cts-gis-garlandSplit__profileBlock"><h5>Current Profile</h5>' +
        '<article class="cts-gis-profileSummary cts-gis-profileSummary--active">' +
        "<strong>" +
        escapeHtml(activeProfile.label || "Active profile") +
        "</strong>" +
        '<span class="cts-gis-profileSummary__meta">' +
        escapeHtml(activeProfile.node_id || "") +
        "</span>" +
        '<span class="cts-gis-profileSummary__meta">' +
        escapeHtml(activeProfileCounts) +
        "</span>" +
        "</article></section>" +
        ((profileProjection.summary_rows || []).length ? renderRows(profileProjection.summary_rows || []) : "") +
        '<section class="cts-gis-garlandSplit__profileBlock"><h5>Projected Rows</h5>' +
        renderRequestButtons(profileProjection.projected_rows || [], "row", {
          emptyMessage: profileProjection.empty_message || "No projected rows available.",
        }) +
        "</section>" +
        '<section class="cts-gis-garlandSplit__profileBlock"><h5>Correlated Profiles</h5>' +
        renderProfileSummaries(profileProjection.correlated_profiles || []) +
        "</section>" +
        ((profileProjection.warnings || []).length
          ? '<section class="cts-gis-garlandSplit__profileBlock"><h5>Warnings</h5>' +
            renderWarningList(profileProjection.warnings || []) +
            "</section>"
          : "") +
        "</section>"
      : renderProjectionPlaceholder(
          profileProjection.empty_message || "No projected profile is available until the active path resolves real CTS-GIS evidence.",
          "cts-gis-profileProjection cts-gis-profileProjection--empty"
        );

    target.innerHTML =
      '<div class="system-tool-interface cts-gis-interface">' +
      '<div class="system-tool-interface__body cts-gis-interface__body" data-cts-gis-layout="' +
      escapeHtml(interfaceBody.layout || "diktataograph_garland_split") +
      '" data-cts-gis-narrow-layout="' +
      escapeHtml(interfaceBody.narrow_layout || "diktataograph_garland_stack") +
      '">' +
      '<section class="v2-card cts-gis-pane cts-gis-pane--diktataograph">' +
      '<header class="cts-gis-pane__header"><h3>' +
      escapeHtml(navigationCanvas.title || "Diktataograph") +
      "</h3><p>" +
      escapeHtml(navigationCanvas.summary || "") +
      "</p></header>" +
      '<section class="cts-gis-navCanvas" data-cts-gis-nav-canvas="structure">' +
      '<div class="cts-gis-navCanvas__mode" data-cts-gis-nav-mode="' +
      escapeHtml(navMode) +
      '">' +
      navigationCanvasMarkup +
      "</div>" +
      renderNavigationDiagnostics(navigationCanvas.diagnostics || []) +
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
      geospatialMarkup +
      "</section>" +
      '<section class="cts-gis-garlandSplit__profile"><h4>' +
      escapeHtml(profileProjection.title || "Profile Projection") +
      "</h4>" +
      profileMarkup +
      "</section>" +
      "</div>" +
      "</section>" +
      "</div>" +
      "</div>";
    bindShellRequestEntries(target, ctx, entriesByKind);
    bindDirectoryDropdowns(target, ctx, navigationCanvas.dropdowns || []);
  }

  window.PortalShellInspectorRenderer = {
    render: function (ctx) {
      var target = ctx.target;
      var region = ctx.region || {};
      var sections = region.sections || [];
      var surfacePayload = region.surface_payload || {};
      var adapter = toolSurfaceAdapter();
      if (!target) return;
      if (region.visible === false) {
        target.innerHTML = "";
        return;
      }
      if (
        window.PortalAwsCsmInspectorRenderer &&
        typeof window.PortalAwsCsmInspectorRenderer.render === "function" &&
        region.kind === "aws_csm_inspector"
      ) {
        window.PortalAwsCsmInspectorRenderer.render(ctx, target, surfacePayload);
        return;
      } else if (region.kind === "aws_csm_inspector") {
        adapter.renderWrappedSurface(
          target,
          adapter.resolveSurfaceState({
            region: region,
            surfacePayload: surfacePayload,
            title: "AWS-CSM Interface Panel",
            unsupported: true,
            message: "The AWS-CSM interface renderer is unavailable.",
          }),
          ""
        );
        return;
      }
      if (
        window.PortalNetworkInspectorRenderer &&
        typeof window.PortalNetworkInspectorRenderer.render === "function" &&
        region.kind === "network_system_log_inspector"
      ) {
        window.PortalNetworkInspectorRenderer.render(ctx, target, surfacePayload);
        return;
      } else if (region.kind === "network_system_log_inspector") {
        adapter.renderWrappedSurface(
          target,
          adapter.resolveSurfaceState({
            region: region,
            surfacePayload: surfacePayload,
            title: "NETWORK Detail",
            unsupported: true,
            message: "The NETWORK detail renderer is unavailable.",
          }),
          ""
        );
        return;
      }
      if (region.kind === "tool_mediation_panel" && region.interface_body && region.interface_body.kind === "cts_gis_interface_body") {
        renderCtsGisInspector(ctx, target, region);
        return;
      } else if (region.kind === "tool_mediation_panel" && region.interface_body) {
        adapter.renderWrappedSurface(
          target,
          adapter.resolveSurfaceState({
            region: region,
            surfacePayload: surfacePayload,
            title: region.title || "Tool Interface Panel",
            unsupported: true,
            message: "This tool interface is not supported by the current renderer set.",
          }),
          ""
        );
        return;
      }
      adapter.renderWrappedSurface(
        target,
        adapter.resolveSurfaceState({
          region: region,
          surfacePayload: surfacePayload,
          title: region.title || "Interface Panel",
          hasContent: !!region.subject || !!sections.length,
          message: region.summary || "Select an item to load interface panel content.",
        }),
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
        "</div>"
      );
    },
  };
})();
