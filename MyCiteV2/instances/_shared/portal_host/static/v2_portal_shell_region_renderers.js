/**
 * Activity bar and control-panel renderers for the one-shell portal.
 */
(function () {
  var api = window.PortalShellRegionRenderers || (window.PortalShellRegionRenderers = {});

  function toolSurfaceAdapter() {
    return window.PortalToolSurfaceAdapter || {};
  }

  function activityIconMarkup(iconId) {
    var id = String(iconId || "generic");
    var svg = "";
    if (id === "system") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M4 7.5h16v9H4z"></path><path d="M8 16.5h8"></path><path d="M10 4.5h4"></path>' +
        "</svg>";
    } else if (id === "network") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<circle cx="6" cy="12" r="2.2"></circle><circle cx="18" cy="6" r="2.2"></circle><circle cx="18" cy="18" r="2.2"></circle>' +
        '<path d="M8 11l7.8-4"></path><path d="M8 13l7.8 4"></path>' +
        "</svg>";
    } else if (id === "utilities") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M4 7h16v10H4z"></path><path d="M9 7V5.5h6V7"></path><path d="M12 11v5"></path><path d="M9.5 13.5h5"></path>' +
        "</svg>";
    } else if (id === "cts_gis") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M12 20s5-4.3 5-9a5 5 0 1 0-10 0c0 4.7 5 9 5 9z"></path><circle cx="12" cy="11" r="1.8"></circle>' +
        "</svg>";
    } else {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<circle cx="12" cy="12" r="8"></circle>' +
        "</svg>";
    }
    return '<span class="ide-activityicon" aria-hidden="true">' + svg + "</span>";
  }

  function bindSurfaceNavigation(node, entry, ctx) {
    if (!node || !entry) return;
    node.addEventListener("click", function (event) {
      if (entry.shell_request) {
        event.preventDefault();
        ctx.loadShell(entry.shell_request);
      }
    });
  }

  api.renderActivityBar = function (ctx) {
    var region = ctx.region || {};
    var nav = ctx.target || document.getElementById("v2-activity-nav");
    var items = region.items || [];
    if (!nav) return;
    if (!items.length) {
      nav.innerHTML = '<p class="ide-sessionLine ide-sessionLine--dim" style="padding:8px;text-align:center;font-size:10px">No surfaces.</p>';
      return;
    }
    nav.innerHTML = "";
    items.forEach(function (item) {
      var link = document.createElement("a");
      link.className = "ide-activitylink" + (item.active ? " is-active" : "");
      link.href = item.href || "#";
      link.setAttribute("aria-label", item.label || "");
      link.setAttribute("title", item.label || "");
      link.innerHTML = activityIconMarkup(item.icon_id);
      bindSurfaceNavigation(link, item, ctx);
      nav.appendChild(link);
    });
  };

  function renderEntry(entry, escapeHtml) {
    var meta = entry.meta ? '<small>' + escapeHtml(entry.meta) + "</small>" : "";
    return (
      '<a class="ide-controlpanel__link' +
      (entry.active ? " is-active" : "") +
      '" href="' +
      escapeHtml(entry.href || "#") +
      '">' +
      "<span>" +
      escapeHtml(entry.label || "") +
      "</span>" +
      meta +
      "</a>"
    );
  }

  function renderFacts(facts, escapeHtml) {
    if (!facts || !facts.length) return "";
    return (
      '<dl class="v2-surface-dl">' +
      facts
        .map(function (fact) {
          return (
            "<dt>" +
            escapeHtml(fact.label || "") +
            "</dt><dd><strong>" +
            escapeHtml(fact.value || "—") +
            "</strong>" +
            (fact.detail ? "<br />" + escapeHtml(fact.detail) : "") +
            "</dd>"
          );
        })
        .join("") +
      "</dl>"
    );
  }

  function renderSelectionEntry(entry, escapeHtml) {
    var meta = entry.meta ? '<small>' + escapeHtml(entry.meta) + "</small>" : "";
    var prefix = entry.prefix ? '<span class="ide-controlpanel__entryPrefix">' + escapeHtml(entry.prefix) + "</span>" : "";
    var body =
      '<span class="ide-controlpanel__entryBody">' +
      prefix +
      '<span class="ide-controlpanel__entryLabel">' +
      escapeHtml(entry.label || "") +
      "</span>" +
      meta +
      "</span>";
    if (entry.shell_request || entry.href) {
      return (
        '<a class="ide-controlpanel__selectionEntry' +
        (entry.active ? " is-active" : "") +
        '" href="' +
        escapeHtml(entry.href || "#") +
        '">' +
        body +
        "</a>"
      );
    }
    return (
      '<div class="ide-controlpanel__selectionEntry is-static' +
      (entry.active ? " is-active" : "") +
      '">' +
      body +
      "</div>"
    );
  }

  function cloneJson(value) {
    try {
      return JSON.parse(JSON.stringify(value || {}));
    } catch (error) {
      return {};
    }
  }

  function stripJsonSuffix(value) {
    var token = String(value == null ? "" : value).trim();
    return token.replace(/\.json$/i, "");
  }

  // Phase 12c (drift remediation): the CTS-GIS bespoke directive panel
  // (renderCtsGisDirectivePanel + deriveCtsGisDirectiveState + their
  // helpers buildActivePathFromNodeId, firstMatchingEntry,
  // ctsGisIntentionDisplay, plus the aitasModes literal) was deleted
  // here. The unified NIMM-AITAS UI panel that consumed this state was
  // removed in Phase 5; the per-tool directive controls that consumed
  // this renderer were the last live caller. The whole cluster
  // (~310 LOC) was unreachable.

  function renderGenericFocusSelectionPanel(ctx, root, region) {
    var contextItems = region.context_items || [];
    var verbTabs = region.verb_tabs || [];
    var groups = region.groups || [];
    var actions = region.actions || [];
    root.innerHTML =
      '<section class="ide-controlpanel__section"><div class="ide-controlpanel__selectionPanel">' +
      '<header class="ide-controlpanel__selectionHeader">' +
      '<div class="ide-controlpanel__title">' +
      ctx.escapeHtml(region.title || "Control Panel") +
      '</div><div class="ide-controlpanel__surfaceLabel">' +
      ctx.escapeHtml(region.surface_label || "") +
      "</div></header>" +
      '<div class="ide-controlpanel__contextRows">' +
      contextItems
        .map(function (item) {
          return (
            '<div class="ide-controlpanel__contextRow">' +
            '<span class="ide-controlpanel__contextKey">' +
            ctx.escapeHtml(item.label || "") +
            ':</span><span class="ide-controlpanel__contextValue">' +
            ctx.escapeHtml(item.value || "—") +
            "</span></div>"
          );
        })
        .join("") +
      "</div>" +
      (verbTabs.length
        ? '<div class="ide-controlpanel__verbTabs">' +
          verbTabs
            .map(function (tab, index) {
              return (
                '<button type="button" class="ide-controlpanel__verbTab' +
                (tab.active ? " is-active" : "") +
                '" data-control-verb-index="' +
                String(index) +
                '">' +
                ctx.escapeHtml(tab.label || "") +
                "</button>"
              );
            })
            .join("") +
          "</div>"
        : "") +
      groups
        .map(function (group) {
          return (
            '<section class="ide-controlpanel__selectionGroup">' +
            (group.title
              ? '<header class="ide-controlpanel__selectionGroupTitle">' + ctx.escapeHtml(group.title) + "</header>"
              : "") +
            '<div class="ide-controlpanel__selectionList">' +
            (group.entries || [])
              .map(function (entry) {
                return renderSelectionEntry(entry, ctx.escapeHtml);
              })
              .join("") +
            "</div></section>"
          );
        })
        .join("") +
      (actions.length
        ? '<div class="ide-controlpanel__actions">' +
          actions
            .map(function (action, index) {
              return (
                '<button type="button" class="ide-controlpanel__action ide-controlpanel__action--full" data-control-action-index="' +
                String(index) +
                '"' +
                (action.disabled ? " disabled" : "") +
                ">" +
                ctx.escapeHtml(action.label || "") +
                "</button>"
              );
            })
            .join("") +
          "</div>"
        : "") +
      "</div></section>";

    Array.prototype.forEach.call(root.querySelectorAll("[data-control-verb-index]"), function (node) {
      var index = Number(node.getAttribute("data-control-verb-index"));
      var entry = verbTabs[index];
      bindSurfaceNavigation(node, entry, ctx);
    });
    var flatEntries = [];
    groups.forEach(function (group) {
      (group.entries || []).forEach(function (entry) {
        flatEntries.push(entry);
      });
    });
    Array.prototype.forEach.call(root.querySelectorAll(".ide-controlpanel__selectionEntry"), function (node, index) {
      bindSurfaceNavigation(node, flatEntries[index], ctx);
    });
    Array.prototype.forEach.call(root.querySelectorAll("[data-control-action-index]"), function (node) {
      node.addEventListener("click", function () {
        var index = Number(node.getAttribute("data-control-action-index"));
        var action = actions[index] || {};
        if (action.disabled) return;
        if (action.action_kind === "copy_text" && action.value) {
          if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
            navigator.clipboard.writeText(String(action.value)).catch(function () {});
          }
          return;
        }
        if (
          (action.route || action.request_schema || action.action_kind) &&
          typeof ctx.dispatchToolAction === "function"
        ) {
          ctx.dispatchToolAction(action);
        }
      });
    });
  }

  function renderSectionModules(ctx, root, region) {
    var sections = region.sections || [];
    root.innerHTML =
      '<section class="ide-controlpanel__section">' +
      '<header class="ide-controlpanel__title">' +
      ctx.escapeHtml(region.title || "Control Panel") +
      "</header>" +
      sections
        .map(function (section) {
          return (
            '<div class="ide-controlpanel__module' +
            (section.compressed ? " is-compressed" : "") +
            '">' +
            '<div class="ide-controlpanel__moduleHeader"><div class="ide-controlpanel__moduleTitle">' +
            ctx.escapeHtml(section.title || "Section") +
            "</div></div>" +
            renderFacts(section.facts || [], ctx.escapeHtml) +
            '<ul class="ide-controlpanel__list">' +
            (section.entries || [])
              .map(function (entry) {
                return "<li>" + renderEntry(entry, ctx.escapeHtml) + "</li>";
              })
              .join("") +
            "</ul></div>"
          );
        })
        .join("") +
      "</section>";
    Array.prototype.forEach.call(root.querySelectorAll(".ide-controlpanel__link"), function (link, index) {
      var flatEntries = [];
      sections.forEach(function (section) {
        (section.entries || []).forEach(function (entry) {
          flatEntries.push(entry);
        });
      });
      bindSurfaceNavigation(link, flatEntries[index], ctx);
    });
  }

  function renderToolExtensions(ctx, toolExtensions) {
    if (!toolExtensions || typeof toolExtensions !== "object") return "";
    var keys = Object.keys(toolExtensions);
    if (!keys.length) return "";
    var blocks = keys
      .map(function (key) {
        var value = toolExtensions[key];
        if (value === null || value === undefined) return "";
        var label = key
          .split("_")
          .map(function (token) {
            return token.charAt(0).toUpperCase() + token.slice(1);
          })
          .join(" ");
        var body = "";
        if (Array.isArray(value)) {
          if (!value.length) return "";
          body = '<ul class="ide-controlpanel__list">' +
            value
              .map(function (entry) {
                if (entry && typeof entry === "object") {
                  return "<li>" + renderEntry(entry, ctx.escapeHtml) + "</li>";
                }
                return '<li class="ide-controlpanel__selectionEntry">' + ctx.escapeHtml(String(entry)) + "</li>";
              })
              .join("") +
            "</ul>";
        } else if (typeof value === "object") {
          var rows = Object.keys(value)
            .map(function (rowKey) {
              var rowValue = value[rowKey];
              if (rowValue === null || rowValue === undefined) return "";
              var displayValue = typeof rowValue === "object" ? JSON.stringify(rowValue) : String(rowValue);
              return (
                '<div class="ide-controlpanel__contextRow">' +
                '<span class="ide-controlpanel__contextKey">' +
                ctx.escapeHtml(rowKey) +
                ':</span><span class="ide-controlpanel__contextValue">' +
                ctx.escapeHtml(displayValue) +
                "</span></div>"
              );
            })
            .filter(function (entry) {
              return entry;
            })
            .join("");
          if (!rows) return "";
          body = '<div class="ide-controlpanel__contextRows">' + rows + "</div>";
        } else {
          body =
            '<div class="ide-controlpanel__contextRow">' +
            '<span class="ide-controlpanel__contextValue">' +
            ctx.escapeHtml(String(value)) +
            "</span></div>";
        }
        return (
          '<div class="ide-controlpanel__toolExtension" data-tool-extension-key="' +
          ctx.escapeHtml(key) +
          '">' +
          '<header class="ide-controlpanel__sectionHeader">' +
          ctx.escapeHtml(label) +
          "</header>" +
          body +
          "</div>"
        );
      })
      .filter(function (block) {
        return block;
      })
      .join("");
    if (!blocks) return "";
    return '<div class="ide-controlpanel__toolExtensions">' + blocks + "</div>";
  }

  function contextControlHasDispatch(source) {
    return !!(source && (source.shell_request || source.action || source.action_kind || source.route || source.request_schema));
  }

  function renderContextControlButton(ctx, control, controlIndex, buttonIndex) {
    var disabled = control.disabled || !contextControlHasDispatch(control);
    return (
      '<button type="button" class="ide-controlpanel__contextButton"' +
      ' data-context-control-index="' + String(controlIndex) + '"' +
      ' data-context-control-button-index="' + String(buttonIndex) + '"' +
      (disabled ? " disabled" : "") +
      ">" +
      ctx.escapeHtml(control.label || "") +
      "</button>"
    );
  }

  function renderContextControls(ctx, controls) {
    if (!controls || !controls.length) return "";
    return (
      '<div class="ide-controlpanel__contextControls">' +
      controls.map(function (control, controlIndex) {
        var options = control.options || [];
        var buttons = control.controls || [];
        var controlType = String(control.control_type || "disabled");
        var selectorHtml = "";
        var buttonsHtml = "";
        if (controlType === "select") {
          selectorHtml =
            '<select class="ide-controlpanel__contextSelect" data-context-control-index="' + String(controlIndex) + '"' +
            (options.some(contextControlHasDispatch) ? "" : " disabled") +
            ">" +
            (options.length
              ? options.map(function (option, optionIndex) {
                  return (
                    '<option value="' + String(optionIndex) + '"' +
                    (option.active ? " selected" : "") +
                    (option.disabled || !contextControlHasDispatch(option) ? " disabled" : "") +
                    ">" +
                    ctx.escapeHtml(option.label || option.value || "") +
                    "</option>"
                  );
                }).join("")
              : '<option value="" selected disabled>' + ctx.escapeHtml(control.empty_message || "No options") + "</option>") +
            "</select>";
        }
        if (controlType === "stepper" || controlType === "directional") {
          buttonsHtml =
            '<div class="ide-controlpanel__contextButtons ide-controlpanel__contextButtons--' +
            ctx.escapeHtml(controlType) +
            '">' +
            buttons.map(function (button, buttonIndex) {
              return renderContextControlButton(ctx, button, controlIndex, buttonIndex);
            }).join("") +
            "</div>";
        }
        return (
          '<section class="ide-controlpanel__contextControl" data-context-id="' +
          ctx.escapeHtml(control.context_id || "") +
          '">' +
          '<div class="ide-controlpanel__contextControlText">' +
          '<h4 class="ide-controlpanel__contextControlTitle">' + ctx.escapeHtml(control.label || control.context_id || "Context") + "</h4>" +
          '<span class="ide-controlpanel__contextCurrent">' + ctx.escapeHtml(control.current_value || "<context_value>") + "</span>" +
          "</div>" +
          '<div class="ide-controlpanel__contextControlInput">' +
          selectorHtml +
          buttonsHtml +
          "</div>" +
          "</section>"
        );
      }).join("") +
      "</div>"
    );
  }

  function dispatchContextControl(source, ctx) {
    if (!source || source.disabled) return;
    if (source.shell_request && typeof ctx.loadShell === "function") {
      ctx.loadShell(source.shell_request);
      return;
    }
    if (source.action && source.action.shell_request && typeof ctx.loadShell === "function") {
      ctx.loadShell(source.action.shell_request);
      return;
    }
    if (source.action && typeof ctx.dispatchToolAction === "function") {
      ctx.dispatchToolAction(source.action);
      return;
    }
    if ((source.action_kind || source.route || source.request_schema) && typeof ctx.dispatchToolAction === "function") {
      ctx.dispatchToolAction(source);
    }
  }

  function bindContextControls(root, ctx, controls) {
    Array.prototype.forEach.call(root.querySelectorAll("select[data-context-control-index]"), function (node) {
      node.addEventListener("change", function () {
        var controlIndex = Number(node.getAttribute("data-context-control-index"));
        var optionIndex = Number(node.value);
        var control = (controls || [])[controlIndex] || {};
        var option = (control.options || [])[optionIndex] || {};
        dispatchContextControl(option, ctx);
      });
    });
    Array.prototype.forEach.call(root.querySelectorAll("button[data-context-control-index]"), function (node) {
      node.addEventListener("click", function () {
        var controlIndex = Number(node.getAttribute("data-context-control-index"));
        var buttonIndex = Number(node.getAttribute("data-context-control-button-index"));
        var control = (controls || [])[controlIndex] || {};
        var button = (control.controls || [])[buttonIndex] || {};
        dispatchContextControl(button, ctx);
      });
    });
  }

  function renderUnifiedDirectivePanel(ctx, root, region) {
    // Phase 5 (portal_tool_surface_contract.md): the unified NIMM-AITAS control
    // section is retired. Region payloads no longer carry nimm_aitas_control.
    // Context controls live on the region directly when a runtime still emits
    // them as a transitional state.
    var portalIdentity = region.portal_identity || {};
    var contextConditions = region.context_conditions || [];
    var contextControls = region.context_controls || [];
    var terminalControl = region.terminal_control || {};
    var navigationGroups = region.navigation_groups || [];
    var actions = region.actions || [];
    var toolExtensions = region.tool_extensions || {};

    // Build HTML
    var html = '<section class="ide-controlpanel__section">';

    // Portal Identity (compact row)
    html +=
      '<div class="ide-controlpanel__identity">' +
      '<span class="ide-controlpanel__portalId">' +
      ctx.escapeHtml(portalIdentity.portal_instance_id || "") +
      "</span>" +
      (portalIdentity.host_shape ? ' · ' + ctx.escapeHtml(portalIdentity.host_shape) : "") +
      "</div>";

    // Context Conditions
    if (contextConditions.length) {
      html += '<div class="ide-controlpanel__contextRows">';
      contextConditions.forEach(function (cond) {
        html +=
          '<div class="ide-controlpanel__contextRow">' +
          '<span class="ide-controlpanel__contextKey">' +
          ctx.escapeHtml(cond.label || "") +
          ':</span><span class="ide-controlpanel__contextValue">' +
          ctx.escapeHtml(cond.value || "—") +
          "</span></div>";
      });
      html += "</div>";
    }

    // Terminal Control Interface
    if (terminalControl.interface) {
      html +=
        '<div class="ide-controlpanel__terminal">' +
        '<header class="ide-controlpanel__sectionHeader">' +
        ctx.escapeHtml(terminalControl.title || "Terminal") +
        "</header>" +
        '<textarea class="ide-controlpanel__terminalInput" placeholder="' +
        ctx.escapeHtml(terminalControl.interface.placeholder || "> inject directive...") +
        '"></textarea>' +
        '<div class="ide-controlpanel__terminalActions">';

      (terminalControl.quick_actions || []).forEach(function (action, index) {
        html +=
          '<button class="ide-controlpanel__terminalAction" data-terminal-action-index="' +
          String(index) +
          '"' +
          (action.disabled ? ' disabled title="' + ctx.escapeHtml(action.disabled_reason || "unavailable") + '"' : "") +
          ">" +
          ctx.escapeHtml(action.label || "") +
          (action.shortcut ? ' <kbd>' + ctx.escapeHtml(action.shortcut) + "</kbd>" : "") +
          "</button>";
      });

      html += "</div></div>";
    }

    html += renderContextControls(ctx, contextControls);

    // Navigation Groups
    navigationGroups.forEach(function (group) {
      html +=
        '<div class="ide-controlpanel__selectionGroup">' +
        '<header class="ide-controlpanel__selectionGroupTitle">' +
        ctx.escapeHtml(group.title || "") +
        "</header>" +
        '<div class="ide-controlpanel__selectionPanel">';

      (group.entries || []).forEach(function (entry) {
        html += renderEntry(entry, ctx.escapeHtml);
      });

      html += "</div></div>";
    });

    html += renderToolExtensions(ctx, toolExtensions);

    // Actions
    if (actions.length) {
      html += '<div class="ide-controlpanel__actions">';
      actions.forEach(function (action, index) {
        html +=
          '<button class="ide-controlpanel__action" data-control-action-index="' +
          String(index) +
          '"' +
          (action.disabled ? " disabled" : "") +
          ">" +
          ctx.escapeHtml(action.label || "") +
          "</button>";
      });
      html += "</div>";
    }

    html += "</section>";

    root.innerHTML = html;

    // Bind navigation
    var flatEntries = [];
    navigationGroups.forEach(function (group) {
      (group.entries || []).forEach(function (entry) {
        flatEntries.push(entry);
      });
    });
    Array.prototype.forEach.call(root.querySelectorAll(".ide-controlpanel__selectionEntry"), function (node, index) {
      bindSurfaceNavigation(node, flatEntries[index], ctx);
    });
    Array.prototype.forEach.call(root.querySelectorAll(".ide-controlpanel__link"), function (node, index) {
      bindSurfaceNavigation(node, flatEntries[index], ctx);
    });
    // Phase 5: verb/nav-arrow bindings derived from nimm_aitas_control are
    // retired. The render block that emitted these data attributes is gone;
    // if a future region payload re-introduces them we'll wire them again.
    var navArrowRequests = {};
    Array.prototype.forEach.call(root.querySelectorAll("[data-nav-arrow-key]"), function (node) {
      node.addEventListener("click", function () {
        var key = String(node.getAttribute("data-nav-arrow-key") || "");
        var request = navArrowRequests[key] || null;
        if (request) ctx.loadShell(request);
      });
    });
    bindContextControls(root, ctx, contextControls);
    var terminalTextarea = root.querySelector(".ide-controlpanel__terminalInput");

    function dispatchTerminalAction(action) {
      if (!action || action.disabled) return;
      if (action.action_kind && typeof ctx.dispatchToolAction === "function") {
        var directiveText = terminalTextarea ? (terminalTextarea.value || "").trim() : "";
        ctx.dispatchToolAction(Object.assign({}, action, { directive_text: directiveText }));
        return;
      }
      if (action.shell_request) ctx.loadShell(action.shell_request);
    }

    Array.prototype.forEach.call(root.querySelectorAll("[data-terminal-action-index]"), function (node) {
      node.addEventListener("click", function () {
        var index = Number(node.getAttribute("data-terminal-action-index"));
        var action = (terminalControl.quick_actions || [])[index] || {};
        dispatchTerminalAction(action);
      });
    });

    if (terminalTextarea) {
      terminalTextarea.addEventListener("keydown", function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
          e.preventDefault();
          var injectAction = (terminalControl.quick_actions || []).find(function (a) {
            return a.action_id === "inject_directive" && !a.disabled;
          });
          if (injectAction) dispatchTerminalAction(injectAction);
        }
      });
    }

    // Bind actions
    Array.prototype.forEach.call(root.querySelectorAll("[data-control-action-index]"), function (node) {
      node.addEventListener("click", function () {
        var index = Number(node.getAttribute("data-control-action-index"));
        var action = actions[index] || {};
        if (action.disabled) return;
        if (action.action_kind === "copy_text" && action.value) {
          if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
            navigator.clipboard.writeText(String(action.value)).catch(function () {});
          }
          return;
        }
        if (
          (action.route || action.request_schema || action.action_kind) &&
          typeof ctx.dispatchToolAction === "function"
        ) {
          ctx.dispatchToolAction(action);
        }
      });
    });
  }

  function renderDirectivePanelHost(ctx, root, region) {
    var adapter = toolSurfaceAdapter();
    var mode =
      (adapter && typeof adapter.resolveDirectivePanelMode === "function" && adapter.resolveDirectivePanelMode(region)) ||
      "sections_panel";

    if (
      mode === "unified_directive_panel" ||
      region.kind === "unified_directive_panel" ||
      region.terminal_control
    ) {
      renderUnifiedDirectivePanel(ctx, root, region);
      return;
    }

    if (mode === "focus_selection_panel") {
      renderGenericFocusSelectionPanel(ctx, root, region);
      return;
    }

    renderSectionModules(ctx, root, region);
  }

  api.renderControlPanel = function (ctx) {
    var adapter = toolSurfaceAdapter();
    var region = ctx.region || {};
    var root = ctx.target || document.getElementById("portalControlPanel");
    if (!root) return;

    // Always use directive panel host for intelligent routing
    renderDirectivePanelHost(ctx, root, region);
  };
  if (typeof window.__MYCITE_V2_REGISTER_SHELL_MODULE === "function") {
    window.__MYCITE_V2_REGISTER_SHELL_MODULE("region_renderers");
  }
})();
