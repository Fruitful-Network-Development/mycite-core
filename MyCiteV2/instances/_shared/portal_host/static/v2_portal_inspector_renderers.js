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

  function asObject(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function asText(value) {
    return String(value == null ? "" : value).trim();
  }

  function normalizePresentationTabs(tabs, fallbackTabs, defaultTabId) {
    var candidates = Array.isArray(tabs) && tabs.length ? tabs : Array.isArray(fallbackTabs) ? fallbackTabs : [];
    var normalized = candidates
      .map(function (tab, index) {
        var source = asObject(tab);
        var id = asText(source.id) || asText(source.tab_id) || "tab-" + String(index + 1);
        if (!id) return null;
        return {
          id: id,
          label: asText(source.label) || asText(source.title) || id,
          summary: asText(source.summary),
          active: source.active === true,
        };
      })
      .filter(function (tab) {
        return !!tab;
      });
    if (!normalized.length) return [];
    var requestedDefault = asText(defaultTabId);
    var activeId = "";
    normalized.forEach(function (tab) {
      if (!activeId && tab.active) activeId = tab.id;
    });
    if (!activeId) {
      activeId = normalized.some(function (tab) {
        return tab.id === requestedDefault;
      })
        ? requestedDefault
        : normalized[0].id;
    }
    return normalized.map(function (tab) {
      return Object.assign({}, tab, { active: tab.id === activeId });
    });
  }

  function activePresentationTabId(tabs, fallbackId) {
    var normalized = Array.isArray(tabs) ? tabs : [];
    for (var index = 0; index < normalized.length; index += 1) {
      if (normalized[index] && normalized[index].active) return normalized[index].id;
    }
    return normalized.length ? normalized[0].id : asText(fallbackId);
  }

  function renderPresentationTabs(tabs) {
    if (!tabs || !tabs.length) return "";
    return (
      '<div class="v2-surfaceTabs" role="tablist" aria-label="Interface tabs">' +
      tabs
        .map(function (tab) {
          return (
            '<button type="button" class="v2-surfaceTabs__tab' +
            (tab.active ? " is-active" : "") +
            '" data-interface-tab="' +
            escapeHtml(tab.id) +
            '" role="tab" aria-selected="' +
            (tab.active ? "true" : "false") +
            '">' +
            escapeHtml(tab.label || tab.id) +
            "</button>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderPresentationTabPanel(tabId, activeTabId, contentHtml, className) {
    var panelClass = "v2-surfaceTabPanel" + (className ? " " + className : "");
    var active = !asText(tabId) || asText(tabId) === asText(activeTabId);
    return (
      '<div class="' +
      escapeHtml(panelClass + (active ? " is-active" : "")) +
      '" data-interface-tab-panel="' +
      escapeHtml(tabId || "") +
      '" role="tabpanel"' +
      (active ? "" : ' hidden="hidden"') +
      ">" +
      String(contentHtml || "") +
      "</div>"
    );
  }

  function bindPresentationTabs(target) {
    if (!target) return;
    var buttons = Array.prototype.slice.call(target.querySelectorAll("[data-interface-tab]"));
    var panels = Array.prototype.slice.call(target.querySelectorAll("[data-interface-tab-panel]"));
    if (!buttons.length || !panels.length) return;

    function activate(tabId) {
      buttons.forEach(function (button) {
        var active = String(button.getAttribute("data-interface-tab") || "") === tabId;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-selected", active ? "true" : "false");
      });
      panels.forEach(function (panel) {
        var active = String(panel.getAttribute("data-interface-tab-panel") || "") === tabId;
        panel.hidden = !active;
        panel.classList.toggle("is-active", active);
      });
    }

    var initialTabId = activePresentationTabId(
      buttons.map(function (button) {
        return {
          id: String(button.getAttribute("data-interface-tab") || ""),
          active: button.classList.contains("is-active"),
        };
      }),
      String(buttons[0].getAttribute("data-interface-tab") || "")
    );
    activate(initialTabId);
    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        activate(String(button.getAttribute("data-interface-tab") || ""));
      });
    });
  }

  window.__MYCITE_V2_INTERFACE_TAB_HOST = {
    normalizeTabs: normalizePresentationTabs,
    activeTabId: activePresentationTabId,
    renderTabs: renderPresentationTabs,
    renderTabPanel: renderPresentationTabPanel,
    bindTabs: bindPresentationTabs,
  };

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

  function resolveRegisteredModuleExport(moduleId, globalName) {
    if (typeof window.__MYCITE_V2_RESOLVE_SHELL_MODULE_EXPORT === "function") {
      return window.__MYCITE_V2_RESOLVE_SHELL_MODULE_EXPORT(moduleId, globalName);
    }
    return window[globalName] || null;
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

  function directoryOptionTitle(option, depth) {
    var title = String((option && option.title) || "");
    return depth === 1 && title ? title.toUpperCase() : title;
  }

  function directoryOptionDisplayTitle(option, depth) {
    var title = directoryOptionTitle(option, depth);
    if (title) return title;
    return String((option && option.node_id) || "");
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
        var title = directoryOptionDisplayTitle(option, depth);
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
              var title = directoryOptionDisplayTitle(option, depth);
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
    function normalizePoint(point) {
      if (!Array.isArray(point) || point.length < 2) return null;
      var x = Number(point[0]);
      var y = Number(point[1]);
      if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
      return [x, y];
    }
    if (geo.type === "Point") {
      var pair = normalizePoint(geo.coordinates || []);
      return pair ? [pair] : [];
    }
    if (geo.type === "Polygon") {
      return (geo.coordinates || []).reduce(function (all, ring) {
        var normalized = (ring || []).map(normalizePoint).filter(Boolean);
        return all.concat(normalized);
      }, []);
    }
    if (geo.type === "MultiPolygon") {
      return (geo.coordinates || []).reduce(function (all, polygon) {
        return all.concat(
          (polygon || []).reduce(function (memo, ring) {
            var normalized = (ring || []).map(normalizePoint).filter(Boolean);
            return memo.concat(normalized);
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

  function buildProjectionViewport(bounds, width, height, pad) {
    var minX = Number(bounds[0] || 0);
    var minY = Number(bounds[1] || 0);
    var maxX = Number(bounds[2] || minX + 1);
    var maxY = Number(bounds[3] || minY + 1);
    var safeWidth = Math.max(0.0001, maxX - minX);
    var safeHeight = Math.max(0.0001, maxY - minY);
    var usableWidth = Math.max(1, width - pad * 2);
    var usableHeight = Math.max(1, height - pad * 2);
    var scale = Math.min(usableWidth / safeWidth, usableHeight / safeHeight);
    if (!Number.isFinite(scale) || scale <= 0) {
      scale = 1;
    }
    return {
      minX: minX,
      minY: minY,
      width: width,
      height: height,
      scale: scale,
      offsetX: pad + (usableWidth - safeWidth * scale) / 2,
      offsetY: pad + (usableHeight - safeHeight * scale) / 2,
    };
  }

  function projectPoint(point, viewport) {
    if (!Array.isArray(point) || point.length < 2) return null;
    var stage = viewport || {};
    var px = Number(point[0]);
    var py = Number(point[1]);
    if (!Number.isFinite(px) || !Number.isFinite(py)) return null;
    var x = Number(stage.offsetX || 0) + (px - Number(stage.minX || 0)) * Number(stage.scale || 1);
    var y = Number(stage.height || 0) - Number(stage.offsetY || 0) - (py - Number(stage.minY || 0)) * Number(stage.scale || 1);
    return [x, y];
  }

  function ringPathData(ring, viewport) {
    var projected = (ring || []).map(function (point) {
      var xy = projectPoint(point, viewport);
      if (!xy) return "";
      return String(xy[0]) + " " + String(xy[1]);
    }).filter(Boolean);
    if (!projected.length) return "";
    return "M " + projected.join(" L ") + " Z";
  }

  function polygonPathData(polygons, viewport) {
    return (polygons || [])
      .map(function (polygon) {
        return (polygon || [])
          .map(function (ring) {
            return ringPathData(ring, viewport);
          })
          .filter(Boolean)
          .join(" ");
      })
      .filter(Boolean)
      .join(" ");
  }

  function renderFeatureShape(feature, viewport) {
    var geometry = (feature || {}).geometry || {};
    var featureId = escapeHtml(feature.feature_id || feature.id || "");
    var className = "cts-gis-mapStage__shape" + (feature.selected ? " is-selected" : "");
    if (geometry.type === "Point") {
      var point = projectPoint(geometry.coordinates || [], viewport);
      if (!point) return "";
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
        viewport
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
    var width = 960;
    var height = 720;
    var pad = 36;
    var bounds = normalizeFeatureBounds((geospatialProjection || {}).collection_bounds || collection.bounds || [], features);
    var focusBounds = normalizeFeatureBounds((geospatialProjection || {}).focus_bounds || [], []);
    var selectedBounds = normalizeFeatureBounds((geospatialProjection || {}).selected_feature_bounds || [], []);
    function boundsArea(rect) {
      if (!Array.isArray(rect) || rect.length !== 4) return 0;
      var widthVal = Number(rect[2]) - Number(rect[0]);
      var heightVal = Number(rect[3]) - Number(rect[1]);
      if (!Number.isFinite(widthVal) || !Number.isFinite(heightVal)) return 0;
      return Math.abs(widthVal * heightVal);
    }
    var globalArea = boundsArea(bounds);
    var focusArea = boundsArea(focusBounds);
    var selectedArea = boundsArea(selectedBounds);
    if (focusArea > 0 && (globalArea <= 0 || globalArea / focusArea > 200)) {
      bounds = focusBounds;
    } else if (
      selectedArea > 0 &&
      Boolean((geospatialProjection || {}).selected_feature_explicit) &&
      (globalArea <= 0 || globalArea / selectedArea > 400)
    ) {
      bounds = selectedBounds;
    }
    var viewport = buildProjectionViewport(bounds, width, height, pad);
    var selectedFeatureId = String((geospatialProjection || {}).selected_feature_id || "");
    var selectedFeature = features.find(function (feature) {
      if (selectedFeatureId && String(feature.id || feature.feature_id || "") === selectedFeatureId) return true;
      return feature.selected;
    }) || features[0] || {};
    return (
      '<div class="cts-gis-mapStage">' +
      '<div class="cts-gis-mapStage__frame">' +
      '<svg class="cts-gis-mapStage__svg" viewBox="0 0 ' +
      String(width) +
      " " +
      String(height) +
      '" preserveAspectRatio="xMidYMid meet" role="img" aria-label="CTS-GIS geospatial projection">' +
      '<rect class="cts-gis-mapStage__backdrop" x="0" y="0" width="' +
      String(width) +
      '" height="' +
      String(height) +
      '"></rect>' +
      features
        .map(function (feature) {
          return renderFeatureShape(feature, viewport);
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

  function renderDistrictPrecinctCollections(collections) {
    if (!collections || !collections.length) {
      return '<p class="ide-controlpanel__empty">No district precinct collections are defined for this profile.</p>';
    }
    return (
      '<div class="cts-gis-collectionCards">' +
      collections
        .map(function (collection) {
          var previewSource = (collection.member_labels && collection.member_labels.length)
            ? collection.member_labels
            : (collection.member_node_ids || []);
          var previewItems = previewSource.slice(0, 8);
          var overflowCount = Math.max(previewSource.length - previewItems.length, 0);
          var statusText = collection.summary_state || (collection.overlay_active ? "loaded" : "deferred");
          var countText = collection.precinct_count_known
            ? String(collection.precinct_count || 0) + " precincts"
            : "members deferred";
          return (
            '<article class="cts-gis-collectionCard' +
            (collection.overlay_active ? " is-active" : "") +
            '">' +
            '<div class="cts-gis-collectionCard__header">' +
            "<strong>" +
            escapeHtml(collection.label || collection.timeframe_token || "District precinct collection") +
            "</strong>" +
            '<span class="cts-gis-collectionCard__meta">' +
            escapeHtml(collection.timeframe_token || "") +
            "</span></div>" +
            '<div class="cts-gis-collectionCard__badges">' +
            '<span class="cts-gis-collectionBadge">' +
            escapeHtml(statusText) +
            "</span>" +
            (collection.scope_kind
              ? '<span class="cts-gis-collectionBadge">' + escapeHtml(collection.scope_kind) + "</span>"
              : "") +
            '<span class="cts-gis-collectionBadge">' +
            escapeHtml(collection.timeframe_match ? "timeframe match" : "timeframe scoped") +
            "</span>" +
            '<span class="cts-gis-collectionBadge">' +
            escapeHtml(countText) +
            "</span></div>" +
            '<p class="cts-gis-collectionCard__detail">' +
            escapeHtml(
              collection.precinct_count_known
                ? "Precinct members were loaded from the canonical precinct cohort overlay."
                : "Compiled precinct members stay deferred until overlay is enabled so Garland keeps the load light."
            ) +
            "</p>" +
            (previewItems.length
              ? '<div class="cts-gis-collectionCard__members">' +
                previewItems
                  .map(function (item) {
                    return '<span class="cts-gis-collectionMember">' + escapeHtml(item || "") + "</span>";
                  })
                  .join("") +
                (overflowCount > 0
                  ? '<span class="cts-gis-collectionMember cts-gis-collectionMember--overflow">+' +
                    escapeHtml(String(overflowCount)) +
                    " more</span>"
                  : "") +
                "</div>"
              : "") +
            ((collection.gate_failures || []).length && statusText === "blocked"
              ? '<p class="cts-gis-collectionCard__detail cts-gis-collectionCard__detail--warn">blocked: ' +
                escapeHtml((collection.gate_failures || []).join(", ")) +
                "</p>"
              : "") +
            "</article>"
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
    var severityCounts = {};
    diagnostics.forEach(function (item) {
      var severity = (item && item.severity) || "notice";
      severityCounts[severity] = (severityCounts[severity] || 0) + 1;
    });
    var severityOrder = Object.keys(severityCounts).sort();
    var previewItems = diagnostics.slice(0, 5);
    var overflowCount = Math.max(diagnostics.length - previewItems.length, 0);
    function renderItems(items) {
      return (items || [])
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
        .join("");
    }
    return (
      '<section class="cts-gis-navDiagnostics">' +
      "<h4>Diagnostics</h4>" +
      '<div class="cts-gis-navDiagnostics__summary">' +
      '<span class="cts-gis-navDiagnostics__meta">' +
      escapeHtml(String(diagnostics.length) + " total") +
      "</span>" +
      '<span class="cts-gis-navDiagnostics__meta">' +
      severityOrder
        .map(function (severity) {
          return escapeHtml(String(severity) + ":" + String(severityCounts[severity] || 0));
        })
        .join(" · ") +
      "</span>" +
      "</div>" +
      '<div class="cts-gis-navDiagnostics__items">' +
      renderItems(previewItems) +
      "</div>" +
      (overflowCount
        ? '<details class="cts-gis-navDiagnostics__expand"><summary>' +
          escapeHtml("Show all diagnostics (" + String(diagnostics.length) + ")") +
          "</summary>" +
          '<div class="cts-gis-navDiagnostics__items">' +
          renderItems(diagnostics) +
          "</div></details>"
        : "") +
      "</section>"
    );
  }

  function normalizeCtsGisInterfaceBody(interfaceBody) {
    var body = interfaceBody || {};
    var fallbackTabs = [
      { id: "diktataograph", label: "Diktataograph", active: true },
      { id: "garland", label: "Garland" },
    ];
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
          projection_health: { state: "empty", reason_codes: [] },
          fallback_reason_codes: [],
          focus_bounds: [],
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
          district_precinct_collections: [],
        },
        body.garland_split_projection.profile_projection || {}
      );
      body.staging_widget = Object.assign(
        {
          title: "Staged Insert",
          summary: "",
          draft_text: "",
          draft_format: "yaml",
          placeholder_title_requested: false,
          validation: {},
          preview: {},
          action_result: {},
          actions: {},
          ready: false,
        },
        body.staging_widget || {}
      );
      body.tabs = normalizePresentationTabs(body.tabs, fallbackTabs, body.default_tab_id || "diktataograph");
      body.default_tab_id = activePresentationTabId(body.tabs, "diktataograph");
      body.tab_host = asText(body.tab_host) || "shared_interface_tabs";
      return body;
    }
    var garland = body.garland || {};
    return {
      tab_host: "shared_interface_tabs",
      tabs: normalizePresentationTabs(body.tabs, fallbackTabs, body.default_tab_id || "diktataograph"),
      default_tab_id: asText(body.default_tab_id) || "diktataograph",
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
      staging_widget: {
        title: "Staged Insert",
        summary: "",
        draft_text: "",
        draft_format: "yaml",
        placeholder_title_requested: false,
        validation: {},
        preview: {},
        action_result: {},
        actions: {},
        ready: false,
      },
      garland_split_projection: {
        kind: "garland_split_projection",
        title: garland.title || "Garland",
        summary: garland.summary || "",
        geospatial_projection: {
          title: "Geospatial Projection",
          projection_state: "",
          projection_source: "none",
          projection_health: {
            state: "empty",
            reason_codes: [],
          },
          fallback_reason_codes: [],
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
          selected_feature_explicit: false,
          focus_bounds: [],
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
          district_precinct_collections: [],
          summary_rows: garland.summary_rows || [],
          warnings: garland.warnings || [],
          empty_message: "No projected profile is available until the active path resolves real CTS-GIS evidence.",
          has_profile_state: false,
          has_real_projection: false,
        },
      },
    };
  }

  function renderCtsGisStagingWidget(widget) {
    var validation = widget.validation || {};
    var preview = widget.preview || {};
    var actionResult = widget.action_result || {};
    var compiledNimm = widget.compiled_nimm_envelope || {};
    var compoundDirectives = widget.compound_directives || {};
    var proposedRows = preview.proposed_inserted_rows || [];
    var warnings = []
      .concat(validation.warnings || [])
      .concat(preview.warnings || [])
      .concat(actionResult.warnings || []);
    return (
      '<section class="cts-gis-stageWidget">' +
      '<header class="cts-gis-stageWidget__header"><h4>' +
      escapeHtml(widget.title || "Staged Insert") +
      "</h4><p>" +
      escapeHtml(widget.summary || "") +
      "</p></header>" +
      '<div class="cts-gis-stageWidget__meta">' +
      '<span class="cts-gis-stageWidget__metaItem">document: ' +
      escapeHtml(widget.document_name || widget.document_id || "—") +
      "</span>" +
      '<span class="cts-gis-stageWidget__metaItem">node: ' +
      escapeHtml(widget.selected_node_id || "—") +
      "</span>" +
      "</div>" +
      '<label class="cts-gis-stageWidget__label" for="cts-gis-stage-textarea">Stage YAML</label>' +
      '<textarea id="cts-gis-stage-textarea" class="cts-gis-stageWidget__textarea" data-cts-gis-stage-input="yaml">' +
      escapeHtml(widget.draft_text || "") +
      "</textarea>" +
      '<label class="cts-gis-stageWidget__toggle">' +
      '<input type="checkbox" data-cts-gis-stage-placeholder' +
      (widget.placeholder_title_requested ? " checked" : "") +
      " />" +
      "<span>Allow placeholder title warnings</span>" +
      "</label>" +
      '<div class="cts-gis-stageWidget__actions">' +
      '<button type="button" class="cts-gis-entryButton" data-cts-gis-stage-action="stage_insert_yaml">Stage</button>' +
      '<button type="button" class="cts-gis-entryButton" data-cts-gis-stage-action="validate_stage"' +
      (widget.ready ? "" : " disabled") +
      ">Validate</button>" +
      '<button type="button" class="cts-gis-entryButton" data-cts-gis-stage-action="preview_apply"' +
      (widget.ready ? "" : " disabled") +
      ">Preview</button>" +
      '<button type="button" class="cts-gis-entryButton" data-cts-gis-stage-action="apply_stage"' +
      (proposedRows.length ? "" : " disabled") +
      ">Apply</button>" +
      '<button type="button" class="cts-gis-entryButton" data-cts-gis-stage-action="discard_stage"' +
      ((widget.draft_text || widget.document_id) ? "" : " disabled") +
      ">Discard</button>" +
      "</div>" +
      ((actionResult.message || "")
        ? '<p class="cts-gis-stageWidget__status"><strong>' +
          escapeHtml(actionResult.status || "pending") +
          ":</strong> " +
          escapeHtml(actionResult.message || "") +
          "</p>"
        : "") +
      ((validation.expected_document_version_hash || "")
        ? '<p class="cts-gis-stageWidget__status">validation hash: ' +
          escapeHtml(String(validation.expected_document_version_hash || "").slice(0, 12)) +
          "</p>"
        : "") +
      ((compiledNimm.schema || "")
        ? '<p class="cts-gis-stageWidget__status">nimm envelope: ' +
          escapeHtml(String(compiledNimm.schema)) +
          "</p>"
        : "") +
      ((compoundDirectives.schema || "")
        ? '<p class="cts-gis-stageWidget__status">compound directives: ' +
          escapeHtml(String((compoundDirectives.steps || []).length)) +
          "</p>"
        : "") +
      (proposedRows.length
        ? '<p class="cts-gis-stageWidget__status">preview rows: ' +
          escapeHtml(String(proposedRows.length)) +
          "</p>"
        : "") +
      renderWarningList(warnings) +
      "</section>"
    );
  }

  function bindCtsGisStagingWidget(target, ctx, widget) {
    var actions = widget.actions || {};
    var textarea = target.querySelector("[data-cts-gis-stage-input='yaml']");
    var placeholderToggle = target.querySelector("[data-cts-gis-stage-placeholder]");
    Array.prototype.forEach.call(target.querySelectorAll("[data-cts-gis-stage-action]"), function (node) {
      node.addEventListener("click", function () {
        if (node.hasAttribute("disabled") || typeof ctx.dispatchToolAction !== "function") return;
        var kind = node.getAttribute("data-cts-gis-stage-action") || "";
        var action = actions[kind] || {};
        var extraPayload = {};
        if (kind === "stage_insert_yaml") {
          extraPayload.stage_text = textarea ? textarea.value : "";
          extraPayload.placeholder_title_requested = !!(placeholderToggle && placeholderToggle.checked);
        }
        ctx.dispatchToolAction(action, { action_payload: extraPayload });
      });
    });
  }

  function loadCtsGisEntry(ctx, entry) {
    if (entry && entry.shell_request) {
      ctx.loadShell(entry.shell_request);
      return;
    }
    if (
      entry &&
      entry.action &&
      typeof ctx.dispatchToolAction === "function"
    ) {
      ctx.dispatchToolAction(entry.action);
    }
  }

  function bindShellRequestEntries(target, ctx, entriesByKind) {
    Array.prototype.forEach.call(target.querySelectorAll("[data-cts-gis-entry-kind]"), function (node) {
      node.addEventListener("click", function () {
        var kind = node.getAttribute("data-cts-gis-entry-kind") || "";
        var index = Number(node.getAttribute("data-cts-gis-entry-index"));
        var entries = entriesByKind[kind] || [];
        var entry = entries[index] || {};
        if (
          kind === "district_toggle" &&
          entry.action &&
          typeof ctx.dispatchToolAction === "function"
        ) {
          ctx.dispatchToolAction(entry.action);
        } else {
          loadCtsGisEntry(ctx, entry);
        }
      });
    });
  }

  function bindDirectoryDropdowns(target, ctx, dropdowns) {
    function loadSelection(dropdownIndex, optionIndex) {
      if (!Number.isFinite(dropdownIndex) || !Number.isFinite(optionIndex)) return;
      var dropdown = (dropdowns || [])[dropdownIndex] || {};
      var option = (dropdown.options || [])[optionIndex] || {};
      loadCtsGisEntry(ctx, option);
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
    var stagingWidget = interfaceBody.staging_widget || {};
    var navMode = navigationCanvas.mode || "directory_dropdowns";
    var garlandSplit = interfaceBody.garland_split_projection || {};
    var interfaceTabs = normalizePresentationTabs(
      interfaceBody.tabs,
      [
        { id: "diktataograph", label: navigationCanvas.title || "Diktataograph", active: true },
        { id: "garland", label: garlandSplit.title || "Garland" },
      ],
      interfaceBody.default_tab_id || "diktataograph"
    );
    var activeTabId = activePresentationTabId(interfaceTabs, "diktataograph");
    var geospatialProjection = garlandSplit.geospatial_projection || {};
    var profileProjection = garlandSplit.profile_projection || {};
    var districtToggle = profileProjection.district_overlay_toggle || {};
    var districtCollections = profileProjection.district_precinct_collections || [];
    var hasDistrictToggleRequest = !!(
      (districtToggle.shell_request && districtToggle.shell_request.tool_state) ||
      districtToggle.action
    );
    var decodeSummary = geospatialProjection.decode_summary || {};
    var activePathEntries = navigationCanvas.active_path || [];
    activePathEntries.forEach(function (entry, index) {
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
      feature: geospatialProjection.features || [],
      district_toggle: hasDistrictToggleRequest ? [districtToggle] : [],
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
        '<section class="cts-gis-garlandSplit__profileBlock"><h5>District Precinct Collections</h5>' +
        '<button type="button" class="cts-gis-entryButton cts-gis-entryButton--toggle' +
        (districtToggle.enabled ? " is-active" : "") +
        '" data-cts-gis-entry-kind="district_toggle" data-cts-gis-entry-index="0"' +
        (hasDistrictToggleRequest ? "" : " disabled") +
        ">" +
        '<span class="cts-gis-entryButton__title">' +
        escapeHtml(districtToggle.enabled ? "Hide compiled precincts" : "Load compiled precincts") +
        "</span>" +
        '<span class="cts-gis-entryButton__meta">time: ' +
        escapeHtml(districtToggle.time_token || "inactive") +
        " · " +
        escapeHtml(districtToggle.timeframe_match ? "within timeframe" : "outside timeframe") +
        " · " +
        escapeHtml(districtToggle.overlay_active ? "overlay active" : "overlay inactive") +
        "</span>" +
        "</button>" +
        renderDistrictPrecinctCollections(districtCollections) +
        "</section>" +
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

    var diktataographPanel =
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
      renderCtsGisStagingWidget(stagingWidget) +
      "</section>";
    var garlandPanel =
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
      "</section>";
    target.innerHTML =
      '<div class="system-tool-interface cts-gis-interface">' +
      renderPresentationTabs(interfaceTabs) +
      '<div class="system-tool-interface__body cts-gis-interface__body" data-cts-gis-layout="' +
      escapeHtml(interfaceBody.layout || "diktataograph_garland_split") +
      '" data-cts-gis-narrow-layout="' +
      escapeHtml(interfaceBody.narrow_layout || "diktataograph_garland_stack") +
      '">' +
      renderPresentationTabPanel("diktataograph", activeTabId, diktataographPanel, "cts-gis-interface__tabPanel") +
      renderPresentationTabPanel("garland", activeTabId, garlandPanel, "cts-gis-interface__tabPanel") +
      "</div>" +
      "</div>";
    bindPresentationTabs(target);
    bindShellRequestEntries(target, ctx, entriesByKind);
    bindDirectoryDropdowns(target, ctx, navigationCanvas.dropdowns || []);
    bindNavigationCanvasEnhancement(target, navMode === "directory_dropdowns");
    bindOrderedHierarchyEnhancement(target);
    bindStagedDiktataographEnhancement(target);
    bindCtsGisStagingWidget(target, ctx, stagingWidget);
  }

  function renderGenericInspectorSurface(target, region, surfacePayload) {
    var sections = region.sections || [];
    var interfaceBody = asObject(region.interface_body);
    var interfaceTabs = normalizePresentationTabs(interfaceBody.tabs, [], interfaceBody.default_tab_id);
    var adapter = toolSurfaceAdapter();
    var rendered = adapter.renderWrappedSurface(
      target,
      adapter.resolveSurfaceState({
        region: region,
        surfacePayload: surfacePayload,
        title: region.title || "Interface Panel",
        hasContent: !!region.subject || !!sections.length,
        message: region.summary || "Select an item to load interface panel content.",
      }),
      (function () {
        function renderSectionCards(sectionList) {
          return (sectionList || [])
            .map(function (section) {
              return (
                '<section class="v2-card" style="margin-top:12px"><h3>' +
                escapeHtml(section.title || "Section") +
                "</h3>" +
                renderRows(section.rows || []) +
                "</section>"
              );
            })
            .join("");
        }

        function renderTabbedSections(tabs, sectionList) {
          if (!tabs.length) return renderSectionCards(sectionList);
          var activeTabId = activePresentationTabId(tabs, tabs[0].id);
          var sectionsByTab = {};
          tabs.forEach(function (tab) {
            sectionsByTab[tab.id] = [];
          });
          (sectionList || []).forEach(function (section) {
            var tabId = asText(section && section.tab_id);
            if (!tabId || !sectionsByTab[tabId]) tabId = tabs[0].id;
            sectionsByTab[tabId].push(section);
          });
          return (
            renderPresentationTabs(tabs) +
            tabs
              .map(function (tab) {
                var tabSections = sectionsByTab[tab.id] || [];
                var panelHtml =
                  renderSectionCards(tabSections) ||
                  ('<section class="v2-card" style="margin-top:12px"><h3>' +
                    escapeHtml(tab.label || tab.id) +
                    "</h3><p>No interface panel details.</p></section>");
                return renderPresentationTabPanel(tab.id, activeTabId, panelHtml);
              })
              .join("")
          );
        }

        return (
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
          renderTabbedSections(interfaceTabs, sections) +
          "</div>"
        );
      })()
    );
    if (rendered && interfaceTabs.length) bindPresentationTabs(target);
  }

  function renderRegisteredPresentationSurface(ctx, target, region, surfacePayload, spec) {
    var moduleSpec = asObject(spec);
    var adapter = toolSurfaceAdapter();
    var renderer = resolveRegisteredModuleExport(moduleSpec.moduleId, moduleSpec.globalName);

    if (renderer && typeof renderer.render === "function") {
      renderer.render(ctx, target, surfacePayload);
      return;
    }
    if (typeof window.__MYCITE_V2_LOAD_SHELL_MODULE === "function" && asText(moduleSpec.moduleId)) {
      adapter.renderWrappedSurface(
        target,
        {
          state: "loading",
          title: asText(moduleSpec.label) || region.title || "Interface Panel",
          message: "Loading deferred interface renderer module…",
          warnings: [],
          readiness: {},
          toolId: asText(moduleSpec.moduleId),
        },
        ""
      );
      window.__MYCITE_V2_LOAD_SHELL_MODULE(moduleSpec.moduleId, {
        reason: "presentation_surface:" + (asText(moduleSpec.label) || asText(moduleSpec.moduleId) || "unknown"),
      })
        .then(function () {
          var resolved = resolveRegisteredModuleExport(moduleSpec.moduleId, moduleSpec.globalName);
          if (resolved && typeof resolved.render === "function") {
            resolved.render(ctx, target, surfacePayload);
            return;
          }
          adapter.renderWrappedSurface(
            target,
            adapter.resolveSurfaceState({
              region: region,
              surfacePayload: surfacePayload,
              title: asText(moduleSpec.label) || region.title || "Interface Panel",
              unsupported: true,
              message:
                "The " +
                (asText(moduleSpec.label) || "interface panel") +
                " renderer is unavailable.",
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
              title: asText(moduleSpec.label) || region.title || "Interface Panel",
              unsupported: true,
              message:
                "The " +
                (asText(moduleSpec.label) || "interface panel") +
                " renderer is unavailable. " +
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
        title: asText(moduleSpec.label) || region.title || "Interface Panel",
        unsupported: true,
        message:
          "The " +
          (asText(moduleSpec.label) || "interface panel") +
          " renderer is unavailable.",
      }),
      ""
    );
  }

  function renderPresentationSurfaceHost(ctx, target, region, surfacePayload) {
    var adapter = toolSurfaceAdapter();
    var mode =
      (adapter &&
        typeof adapter.resolvePresentationSurfaceMode === "function" &&
        adapter.resolvePresentationSurfaceMode(region, surfacePayload)) ||
      "summary_surface";
    var moduleSpec =
      (adapter &&
        typeof adapter.resolvePresentationSurfaceModuleSpec === "function" &&
        adapter.resolvePresentationSurfaceModuleSpec(region, surfacePayload)) ||
      {};

    if (mode === "registered_surface" && asObject(moduleSpec).moduleId) {
      renderRegisteredPresentationSurface(ctx, target, region, surfacePayload, moduleSpec);
      return;
    }
    if (mode === "structured_interface_body") {
      renderCtsGisInspector(ctx, target, region);
      return;
    }
    if (mode === "unsupported_interface_body") {
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
    renderGenericInspectorSurface(target, region, surfacePayload);
  }

  window.PortalCtsGisInspectorRenderer = {
    render: function (ctx) {
      var target = ctx.target;
      var region = ctx.region || {};
      if (!target) return;
      if (region.visible === false) {
        target.innerHTML = "";
        return;
      }
      renderCtsGisInspector(ctx, target, region);
    },
  };
  if (typeof window.__MYCITE_V2_REGISTER_SHELL_MODULE === "function") {
    window.__MYCITE_V2_REGISTER_SHELL_MODULE("cts_gis_surface");
  }
})();
