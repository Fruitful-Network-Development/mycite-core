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

  function stripJsonSuffix(value) {
    var token = String(value == null ? "" : value).trim();
    return token.replace(/\.json$/i, "");
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

  function firstMatchingEntry(entries, prefix) {
    for (var index = 0; index < entries.length; index += 1) {
      var entry = entries[index] || {};
      if (String(entry.label || "").indexOf(prefix) === 0) return entry;
    }
    return {};
  }

  function ctsGisIntentionDisplay(entry) {
    var token = String((entry && entry.prefix) || "").trim();
    if (token === "self") return "1";
    if (/^\d+(?:-\d+)*-0-0$/.test(token)) return "0-0";
    if (/^\d+(?:-\d+)*-0$/.test(token)) return "0";
    return String((entry && entry.label) || "").replace(/^Intention\s+\u00b7\s+/, "") || "1";
  }

  function deriveCtsGisDirectiveState(region) {
    var groups = Array.isArray(region && region.groups) ? region.groups : [];
    var stateGroup = null;
    for (var index = 0; index < groups.length; index += 1) {
      var candidate = groups[index] || {};
      if (String(candidate.title || "") === "STATE DIRECTIVE") {
        stateGroup = candidate;
        break;
      }
    }
    var entries = Array.isArray(stateGroup && stateGroup.entries) ? stateGroup.entries : [];
    var nimmButtons = ["NAV", "INV", "MED", "MAN"].map(function (label) {
      var entry = firstMatchingEntry(entries, label);
      return {
        label: label,
        active: !!entry.active,
      };
    });
    var intentionLevels = entries
      .filter(function (entry) {
        return String(entry.label || "").indexOf("Intention \u00b7 ") === 0;
      })
      .map(function (entry) {
        return {
          display: ctsGisIntentionDisplay(entry),
          shell_request: entry.shell_request || null,
          active: !!entry.active,
        };
      });
    var activeIndex = 0;
    for (var levelIndex = 0; levelIndex < intentionLevels.length; levelIndex += 1) {
      if (intentionLevels[levelIndex].active) {
        activeIndex = levelIndex;
        break;
      }
    }
    var attentionEntries = entries.filter(function (entry) {
      return String(entry.label || "").indexOf("Attention \u00b7 ") === 0;
    });
    var timeEntries = entries.filter(function (entry) {
      return String(entry.label || "").indexOf("Time \u00b7 ") === 0;
    });
    var activeAttentionEntry = attentionEntries.filter(function (entry) {
      return !!entry.active;
    })[0] || attentionEntries[0] || {};
    var activeTimeEntry = timeEntries.filter(function (entry) {
      return !!entry.active;
    })[0] || timeEntries[0] || {};
    return {
      contextItems: Array.isArray(region && region.context_items) ? region.context_items : [],
      nimmButtons: nimmButtons,
      aitasModes: [
        { id: "A", label: "A" },
        { id: "I", label: "I" },
        { id: "T", label: "T" },
        { id: "A2", label: "A", locked: true },
        { id: "S", label: "S", locked: true },
      ],
      activeMode: "I",
      intentionLevels: intentionLevels,
      activeIndex: activeIndex,
      scriptPlaceholder: "/enter...",
      scriptHelp: "Directive script input is not active yet.",
      attentionValue: String(activeAttentionEntry.prefix || ""),
      timeValue: String(activeTimeEntry.prefix || ""),
      attentionTemplate: cloneJson(activeAttentionEntry.shell_request),
      timeTemplate: cloneJson(activeTimeEntry.shell_request),
      nodeIdPattern: /^\d+(?:-\d+)*$/,
      invalidAttentionMessage: "Invalid attention node id.",
      invalidTimeMessage: "Invalid time token; use HOPS-style address id.",
    };
  }

  function renderCtsGisDirectivePanel(ctx, root, region) {
    var directiveState = deriveCtsGisDirectiveState(region);
    var contextItems = directiveState.contextItems;
    var nimmButtons = directiveState.nimmButtons;
    var aitasModes = directiveState.aitasModes;
    var activeMode = String(directiveState.activeMode || "I");
    var intentionLevels = directiveState.intentionLevels;
    var activeIndex = Number(directiveState.activeIndex || 0);
    if (activeIndex < 0 || activeIndex >= intentionLevels.length) activeIndex = 0;
    var activeLevel = intentionLevels[activeIndex] || {};
    var scriptPlaceholder = String(directiveState.scriptPlaceholder || "/enter...");
    var scriptHelp = String(directiveState.scriptHelp || "Directive input unavailable.");
    var attentionValue = String(directiveState.attentionValue || "");
    var timeValue = String(directiveState.timeValue || "");
    var nodeIdPattern = directiveState.nodeIdPattern || /^\d+(?:-\d+)*$/;
    var invalidAttentionMessage = String(directiveState.invalidAttentionMessage || "Invalid attention node id.");
    var invalidTimeMessage = String(directiveState.invalidTimeMessage || "Invalid time token.");

    if (!intentionLevels.length) {
      renderGenericFocusSelectionPanel(ctx, root, region);
      return;
    }

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
        var template = currentMode === "A" ? cloneJson(directiveState.attentionTemplate) : cloneJson(directiveState.timeTemplate);
        if (!Object.keys(template).length) {
          setFeedback("This directive action is unavailable for the current panel state.", true);
          return;
        }
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
