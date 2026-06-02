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
    } else if (id === "agro_erp") {
      svg =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M12 4c-2 3-2 6 0 9c2-3 2-6 0-9z"></path>' +
        '<path d="M5 12c2 0 4 1 5 3"></path>' +
        '<path d="M19 12c-2 0-4 1-5 3"></path>' +
        '<path d="M12 13v7"></path>' +
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

  function renderModeTabs(ctx, workbenchMode) {
    // Workbench three-mode tab strip. Hidden when the panel surface
    // does not carry workbench_mode (i.e. legacy / non-workbench
    // surfaces stay unaffected).
    if (!workbenchMode || !Array.isArray(workbenchMode.tabs) || workbenchMode.tabs.length === 0) {
      return "";
    }
    var html = '<nav class="ide-controlpanel__modeTabs" role="tablist">';
    workbenchMode.tabs.forEach(function (tab, index) {
      var classes = ["ide-controlpanel__modeTab"];
      if (tab.active) classes.push("ide-controlpanel__modeTab--active");
      if (!tab.available) classes.push("ide-controlpanel__modeTab--disabled");
      html +=
        '<button type="button" class="' + classes.join(" ") +
        '" role="tab" aria-selected="' + (tab.active ? "true" : "false") + '"' +
        (tab.available ? "" : " disabled") +
        ' data-workbench-mode-index="' + String(index) + '">' +
        ctx.escapeHtml(tab.label || tab.mode || "") +
        "</button>";
    });
    html += "</nav>";
    return html;
  }

  function renderDisclosureGroups(ctx, disclosureGroups) {
    if (!Array.isArray(disclosureGroups) || disclosureGroups.length === 0) return "";
    var html = '<div class="ide-controlpanel__disclosures">';
    disclosureGroups.forEach(function (group) {
      var expanded = group.expanded ? " open" : "";
      html +=
        '<details class="ide-controlpanel__disclosure"' + expanded + ">" +
        '<summary class="ide-controlpanel__disclosureSummary">' +
        ctx.escapeHtml(group.title || "") +
        "</summary>" +
        '<div class="ide-controlpanel__disclosureBody">';
      // Nested groups (e.g. "Display options" wraps several nav groups).
      (group.groups || []).forEach(function (nested) {
        html +=
          '<div class="ide-controlpanel__selectionGroup">' +
          '<header class="ide-controlpanel__selectionGroupTitle">' +
          ctx.escapeHtml(nested.title || "") +
          "</header>" +
          '<div class="ide-controlpanel__selectionPanel">';
        (nested.entries || []).forEach(function (entry) {
          html += renderEntry(entry, ctx.escapeHtml);
        });
        html += "</div></div>";
      });
      // Inspector-style context conditions.
      if (Array.isArray(group.context_conditions) && group.context_conditions.length) {
        html += '<div class="ide-controlpanel__contextRows">';
        group.context_conditions.forEach(function (cond) {
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
      html += "</div></details>";
    });
    html += "</div>";
    return html;
  }

  function renderAuthorForms(ctx, workbenchMode) {
    // Author-mode forms: a title input for new documents (no template/type
    // picker — document shape is authored later, inside the document), and a
    // YAML textarea for new datums. The renderer builds vanilla HTML form
    // controls; submission is handled by bindAuthorForms (POST stage →
    // preview → apply) which posts operation=create_document.
    if (!workbenchMode || workbenchMode.active !== "author") return "";
    var forms = workbenchMode.author_forms || {};
    var html = "";
    var nsf = forms.new_source_document;
    if (nsf) {
      var nameInput = nsf.name_input || {};
      html +=
        '<form class="ide-controlpanel__authorForm" data-author-form-kind="new_source_document">' +
        '<header class="ide-controlpanel__selectionGroupTitle">+ New document</header>';
      // Title-only: free-text title (the backend sanitizes it into a canonical
      // name segment). No template/type selection at the creation gate.
      html += '<label class="ide-controlpanel__authorLabel">Title' +
        '<input type="text" name="document_name" required' +
        ' maxlength="' + String(nameInput.max_length || 80) + '"' +
        ' placeholder="' + ctx.escapeHtml(nameInput.placeholder || "Document title") + '" />' +
        "</label>";
      html += '<button type="submit" class="ide-controlpanel__authorSubmit">Create document</button>';
      html += '<p class="ide-controlpanel__authorStatus" data-author-form-status></p>';
      html += "</form>";
    }
    var ndf = forms.new_datum;
    if (ndf) {
      var docId = ndf.document_id_default || "";
      html +=
        '<form class="ide-controlpanel__authorForm" data-author-form-kind="new_datum">' +
        '<header class="ide-controlpanel__selectionGroupTitle">+ New datum</header>';
      if (!docId) {
        html +=
          '<p class="ide-controlpanel__authorEmpty">Select a document first.</p>';
      } else {
        html += '<p class="ide-controlpanel__authorMeta">Document: <code>' +
          ctx.escapeHtml(docId) + "</code></p>";
        var rt = ndf.raw_payload_textarea || {};
        html += '<label class="ide-controlpanel__authorLabel">' +
          ctx.escapeHtml(rt.label || "Datum row (YAML 4-tuple)") +
          '<textarea name="raw_payload" rows="6" required placeholder="' +
          ctx.escapeHtml(rt.placeholder || "") + '"></textarea></label>';
        html += '<button type="submit" class="ide-controlpanel__authorSubmit">Insert datum</button>';
        html += '<p class="ide-controlpanel__authorStatus" data-author-form-status></p>';
      }
      html += "</form>";
    }
    return html;
  }

  function bindModeTabs(root, ctx, workbenchMode) {
    if (!workbenchMode || !Array.isArray(workbenchMode.tabs)) return;
    Array.prototype.forEach.call(
      root.querySelectorAll("[data-workbench-mode-index]"),
      function (node) {
        node.addEventListener("click", function () {
          var index = Number(node.getAttribute("data-workbench-mode-index"));
          var tab = (workbenchMode.tabs || [])[index] || {};
          if (!tab.available || tab.active) return;
          if (tab.shell_request) ctx.loadShell(tab.shell_request);
        });
      }
    );
  }

  function bindAuthorForms(root, ctx, workbenchMode) {
    if (!workbenchMode || workbenchMode.active !== "author") return;
    var forms = workbenchMode.author_forms || {};
    Array.prototype.forEach.call(
      root.querySelectorAll("[data-author-form-kind]"),
      function (form) {
        form.addEventListener("submit", function (event) {
          event.preventDefault();
          var kind = form.getAttribute("data-author-form-kind");
          var contract = kind === "new_source_document" ? forms.new_source_document : forms.new_datum;
          if (!contract) return;
          var statusEl = form.querySelector("[data-author-form-status]");
          function setStatus(msg) { if (statusEl) statusEl.textContent = msg; }
          var payload = {
            target_authority: "datum_workbench",
            sandbox_id: contract.sandbox_id,
          };
          if (kind === "new_source_document") {
            payload.operation = "create_document";
            payload.document_name = form.document_name.value;
            payload.msn_id = contract.msn_id_default || "";
          } else {
            payload.operation = "insert_datum";
            payload.document_id = contract.document_id_default;
            payload.raw_payload = form.raw_payload.value;
          }
          var endpoints = [contract.endpoint_stage, contract.endpoint_preview, contract.endpoint_apply];
          var labels = ["staging", "previewing", "applying"];
          setStatus(labels[0] + "…");
          var step = 0;
          function nextStep(prev) {
            if (step >= endpoints.length) {
              setStatus("done. Reloading…");
              setTimeout(function () { window.location.reload(); }, 500);
              return;
            }
            var url = endpoints[step];
            setStatus(labels[step] + "…");
            fetch(url, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(prev || payload),
            }).then(function (res) {
              if (!res.ok) throw new Error(labels[step] + " failed: " + res.status);
              return res.json();
            }).then(function (body) {
              step += 1;
              nextStep(body);
            }).catch(function (err) {
              setStatus("error: " + (err && err.message ? err.message : String(err)));
            });
          }
          nextStep();
        });
      }
    );
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
    var disclosureGroups = region.disclosure_groups || [];
    var workbenchMode = region.workbench_mode || null;

    // Build HTML
    var html = '<section class="ide-controlpanel__section">';

    // Portal Identity (compact row) — appended with the workbench
    // sandbox label when in three-mode workbench surfaces so the user
    // sees "fnd · local — Agro-ERP" instead of just "fnd".
    var identityHtml =
      '<div class="ide-controlpanel__identity">' +
      '<span class="ide-controlpanel__portalId">' +
      ctx.escapeHtml(portalIdentity.portal_instance_id || "") +
      "</span>" +
      (portalIdentity.host_shape ? ' · ' + ctx.escapeHtml(portalIdentity.host_shape) : "");
    if (workbenchMode && workbenchMode.sandbox_label) {
      identityHtml += ' — <span class="ide-controlpanel__sandboxLabel">' +
        ctx.escapeHtml(workbenchMode.sandbox_label) + "</span>";
    }
    identityHtml += "</div>";
    html += identityHtml;

    // Mode tabs (workbench surfaces only).
    html += renderModeTabs(ctx, workbenchMode);

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

    // Author-mode inline forms (rendered before disclosure groups so
    // the user sees the create affordances at the top of Author mode).
    html += renderAuthorForms(ctx, workbenchMode);

    // Disclosure groups (Display options, Inspector). Rendered as
    // <details> elements, collapsed by default.
    html += renderDisclosureGroups(ctx, disclosureGroups);

    html += renderToolExtensions(ctx, toolExtensions);

    // Non-duplicate control-panel controls (TASK-2026-06-02-002): lens on/off
    // toggles + a document-context tool search. The mount points are filled by
    // shell_core (PortalLensPanel / PortalToolPalette) after this render. The
    // workbench owns document/datum lists; these act ON the current selection.
    var cpControls = region.control_panel_controls || null;
    if (cpControls) {
      if (cpControls.lenses) {
        html +=
          '<details class="ide-controlpanel__disclosure" open>' +
          '<summary class="ide-controlpanel__disclosureSummary">Lenses</summary>' +
          '<div class="ide-controlpanel__disclosureBody" data-cp-lens-mount></div>' +
          "</details>";
      }
      if (cpControls.tool_search) {
        html +=
          '<details class="ide-controlpanel__disclosure" open>' +
          '<summary class="ide-controlpanel__disclosureSummary">Tools</summary>' +
          '<nav class="ide-controlpanel__toolSearch" aria-label="Tool search" data-cp-tool-search-mount></nav>' +
          "</details>";
      }
    }

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
    bindModeTabs(root, ctx, workbenchMode);
    bindAuthorForms(root, ctx, workbenchMode);
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
