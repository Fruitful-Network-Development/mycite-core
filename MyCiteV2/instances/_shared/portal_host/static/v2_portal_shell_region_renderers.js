/**
 * Activity bar and control-panel renderers for the one-shell portal.
 */
(function () {
  var api = window.PortalShellRegionRenderers || (window.PortalShellRegionRenderers = {});

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
    } else if (id === "aws") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M7.5 17.5h8a4 4 0 0 0 .7-7.94A5.2 5.2 0 0 0 6.7 8.5 3.6 3.6 0 0 0 7.5 17.5z"></path>' +
        '<path d="M8 20c2 .9 5 .9 8 0"></path>' +
        "</svg>";
    } else if (id === "cts_gis") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M12 20s5-4.3 5-9a5 5 0 1 0-10 0c0 4.7 5 9 5 9z"></path><circle cx="12" cy="11" r="1.8"></circle>' +
        "</svg>";
    } else if (id === "fnd_dcm") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M7 4.5h7l3 3V19.5H7z"></path><path d="M14 4.5v3h3"></path><path d="M10 11h7"></path><path d="M10 15h7"></path><path d="M4.5 9.5v7"></path><path d="M2.5 11.5h4"></path>' +
        "</svg>";
    } else if (id === "fnd_ebi") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M4.5 6.5h15"></path><path d="M4.5 12h15"></path><path d="M4.5 17.5h9"></path>' +
        '<path d="M17 16l2.5 2.5"></path><circle cx="14.5" cy="13.5" r="3.5"></circle>' +
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

  function buildActivePathFromNodeId(nodeId) {
    var token = String(nodeId || "").trim();
    if (!token || !/^\d+(?:-\d+)*$/.test(token)) return [];
    var parts = token.split("-");
    var out = [];
    for (var depth = 1; depth <= parts.length; depth += 1) {
      out.push(parts.slice(0, depth).join("-"));
    }
    return out;
  }

  function renderCtsGisDirectivePanel(ctx, root, region) {
    var compact = region.state_directive_compact || {};
    var contextItems = region.context_items || [];
    var nimmButtons = compact.nimm_buttons || [];
    var aitasModes = compact.aitas_modes || [];
    var activeMode = String(compact.active_mode || "I");
    var intention = compact.intention || {};
    var intentionLevels = intention.levels || [];
    var activeIndex = Number(intention.active_index || 0);
    if (activeIndex < 0 || activeIndex >= intentionLevels.length) activeIndex = 0;
    var activeLevel = intentionLevels[activeIndex] || {};
    var scriptPlaceholder = ((compact.script_input || {}).placeholder || "/enter...").toString();
    var scriptHelp = ((compact.script_input || {}).help || "Directive input unavailable.").toString();
    var attentionValue = ((compact.attention || {}).value || "").toString();
    var timeValue = ((compact.time || {}).value || "").toString();
    var validation = compact.validation || {};
    var nodeIdPattern = new RegExp((validation.node_id_pattern || "^\\d+(?:-\\d+)*$").toString());
    var invalidAttentionMessage = (validation.invalid_attention_message || "Invalid attention node id.").toString();
    var invalidTimeMessage = (validation.invalid_time_message || "Invalid time token.").toString();

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
      '</div><section class="ide-controlpanel__selectionGroup">' +
      '<header class="ide-controlpanel__selectionGroupTitle">STATE DIRECTIVE</header>' +
      '<div class="ide-controlpanel__directiveBlock">' +
      '<div class="ide-controlpanel__directiveRow ide-controlpanel__directiveRow--nimm">' +
      nimmButtons
        .map(function (button, index) {
          return (
            '<button type="button" class="ide-controlpanel__directiveButton' +
            (button.active ? " is-active" : "") +
            '" data-cts-gis-directive-nimm-index="' +
            String(index) +
            '" disabled>' +
            ctx.escapeHtml(button.label || "") +
            "</button>"
          );
        })
        .join("") +
      "</div>" +
      '<form class="ide-controlpanel__directiveRow ide-controlpanel__directiveRow--script" data-cts-gis-directive-script-form>' +
      '<input class="ide-controlpanel__directiveInput" data-cts-gis-directive-script-input type="text" placeholder="' +
      ctx.escapeHtml(scriptPlaceholder) +
      '" />' +
      "</form>" +
      '<div class="ide-controlpanel__directiveRow ide-controlpanel__directiveRow--aitas">' +
      aitasModes
        .map(function (mode, index) {
          var modeId = String(mode.id || "");
          var locked = !!mode.locked;
          return (
            '<button type="button" class="ide-controlpanel__directiveButton ide-controlpanel__directiveButton--aitas' +
            (modeId === activeMode ? " is-active" : "") +
            (locked ? " is-locked" : "") +
            '" data-cts-gis-directive-mode-index="' +
            String(index) +
            '"' +
            (locked ? " disabled" : "") +
            ">" +
            ctx.escapeHtml(mode.label || modeId) +
            "</button>"
          );
        })
        .join("") +
      "</div>" +
      '<div class="ide-controlpanel__directiveRow ide-controlpanel__directiveRow--value" data-cts-gis-directive-value-row>' +
      '<div class="ide-controlpanel__directiveIntention" data-cts-gis-directive-intention>' +
      '<span class="ide-controlpanel__directiveValueText" data-cts-gis-directive-intention-display>' +
      ctx.escapeHtml(activeLevel.display || "1") +
      "</span>" +
      '<div class="ide-controlpanel__directiveStepButtons">' +
      '<button type="button" class="ide-controlpanel__directiveStep" data-cts-gis-directive-plus>+</button>' +
      '<button type="button" class="ide-controlpanel__directiveStep" data-cts-gis-directive-minus>−</button>' +
      "</div></div>" +
      '<form class="ide-controlpanel__directiveApply" data-cts-gis-directive-apply-form>' +
      '<input class="ide-controlpanel__directiveInput" data-cts-gis-directive-apply-input type="text" value="" />' +
      "</form></div>" +
      '<p class="ide-controlpanel__directiveFeedback" data-cts-gis-directive-feedback></p>' +
      "</div></section></div></section>";

    var currentMode = activeMode;
    var applyInput = root.querySelector("[data-cts-gis-directive-apply-input]");
    var applyForm = root.querySelector("[data-cts-gis-directive-apply-form]");
    var feedback = root.querySelector("[data-cts-gis-directive-feedback]");
    var intentionBlock = root.querySelector("[data-cts-gis-directive-intention]");
    var plusButton = root.querySelector("[data-cts-gis-directive-plus]");
    var minusButton = root.querySelector("[data-cts-gis-directive-minus]");
    var intentionDisplay = root.querySelector("[data-cts-gis-directive-intention-display]");
    var scriptForm = root.querySelector("[data-cts-gis-directive-script-form]");

    function setFeedback(message, isError) {
      if (!feedback) return;
      feedback.textContent = String(message || "");
      feedback.classList.toggle("is-error", !!isError);
      feedback.classList.toggle("is-info", !isError && !!message);
    }

    function updateValueMode() {
      var isIntention = currentMode === "I";
      if (intentionBlock) intentionBlock.style.display = isIntention ? "flex" : "none";
      if (applyForm) applyForm.style.display = isIntention ? "none" : "block";
      if (applyInput) {
        if (currentMode === "A") {
          applyInput.value = attentionValue;
          applyInput.placeholder = "attention node id";
        } else if (currentMode === "T") {
          applyInput.value = timeValue;
          applyInput.placeholder = "time token / node id";
        } else {
          applyInput.value = "";
          applyInput.placeholder = "";
        }
      }
      setFeedback("", false);
    }

    Array.prototype.forEach.call(root.querySelectorAll("[data-cts-gis-directive-mode-index]"), function (node) {
      node.addEventListener("click", function () {
        var index = Number(node.getAttribute("data-cts-gis-directive-mode-index"));
        var mode = aitasModes[index] || {};
        if (mode.locked) return;
        currentMode = String(mode.id || currentMode);
        Array.prototype.forEach.call(root.querySelectorAll("[data-cts-gis-directive-mode-index]"), function (button) {
          button.classList.remove("is-active");
        });
        node.classList.add("is-active");
        updateValueMode();
      });
    });

    if (scriptForm) {
      scriptForm.addEventListener("submit", function (event) {
        event.preventDefault();
        setFeedback(scriptHelp, false);
      });
    }

    if (plusButton) {
      plusButton.addEventListener("click", function () {
        var nextIndex = Math.min(activeIndex + 1, intentionLevels.length - 1);
        var nextLevel = intentionLevels[nextIndex] || {};
        if (nextLevel.shell_request) {
          ctx.loadShell(nextLevel.shell_request);
        }
      });
    }
    if (minusButton) {
      minusButton.addEventListener("click", function () {
        var nextIndex = Math.max(activeIndex - 1, 0);
        var nextLevel = intentionLevels[nextIndex] || {};
        if (nextLevel.shell_request) {
          ctx.loadShell(nextLevel.shell_request);
        }
      });
    }
    if (intentionDisplay) {
      intentionDisplay.textContent = String(activeLevel.display || "1");
    }

    if (applyForm) {
      applyForm.addEventListener("submit", function (event) {
        event.preventDefault();
        if (currentMode !== "A" && currentMode !== "T") return;
        var raw = ((applyInput && applyInput.value) || "").trim();
        if (!nodeIdPattern.test(raw)) {
          setFeedback(currentMode === "A" ? invalidAttentionMessage : invalidTimeMessage, true);
          return;
        }
        var template =
          currentMode === "A" ? cloneJson((compact.attention || {}).shell_template) : cloneJson((compact.time || {}).shell_template);
        if (!template.tool_state) template.tool_state = {};
        if (!template.tool_state.aitas) template.tool_state.aitas = {};
        if (currentMode === "A") {
          template.tool_state.selected_node_id = raw;
          template.tool_state.active_path = buildActivePathFromNodeId(raw);
          template.tool_state.aitas.attention_node_id = raw;
        } else {
          template.tool_state.aitas.time_directive = raw;
        }
        ctx.loadShell(template);
      });
    }

    updateValueMode();
  }

  function renderFocusSelectionPanel(ctx, root, region) {
    if (region.surface_label === "CTS-GIS" && region.state_directive_compact) {
      renderCtsGisDirectivePanel(ctx, root, region);
      return;
    }
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
                '">' +
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
        if (action.action_kind === "copy_text" && action.value) {
          if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
            navigator.clipboard.writeText(String(action.value)).catch(function () {});
          }
        }
      });
    });
  }

  api.renderControlPanel = function (ctx) {
    var region = ctx.region || {};
    var root = ctx.target || document.getElementById("portalControlPanel");
    if (!root) return;
    if (region.kind === "focus_selection_panel") {
      renderFocusSelectionPanel(ctx, root, region);
      return;
    }
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
  };
})();
