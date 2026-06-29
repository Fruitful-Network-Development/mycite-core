/**
 * Workbench renderer for the one-shell portal.
 */
(function () {
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      // Escape the single quote too: some attributes here are single-quoted
      // (e.g. data-mailbox-edit-payload='...'), so an unescaped ' would
      // break out of the attribute. &#39; is safe in both HTML text and
      // single/double-quoted attribute contexts.
      .replace(/'/g, "&#39;");
  }

  function asObject(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function asList(value) {
    return Array.isArray(value) ? value.slice() : [];
  }

  function asText(value) {
    return String(value == null ? "" : value).trim();
  }

  function stripJsonSuffix(value) {
    return asText(value).replace(/\.json$/i, "");
  }

  // Extracts a short, navigable label from a datum-document filename.
  // The new naming conventions encode the salient identifier as a
  // recognizable middle segment:
  //   sc.<corpus>.cts_gis.ruigi-<id>.<hash>.json   -> "ruigi-<id>"
  //   sc.<corpus>.msn-<id>.<hash>.json             -> "msn-<id>"
  //   sc.<corpus>.registrar.json                   -> "registrar"
  // Legacy conventions:
  //   sc.<corpus>.cts.<id_underscored>.json        -> "cts.<id_underscored>"
  //   sc.<corpus>.fnd.<id>.json                    -> "fnd.<id>"
  // Anything else falls back to the filename minus `.json`.
  function shortDocumentLabel(value) {
    var name = stripJsonSuffix(value);
    if (!name) return "";
    var m;
    // ruigi precinct: sc.<corpus>.cts_gis.ruigi-<id>.<hash>
    m = name.match(/\.(cts_gis\.ruigi-[^.]+)\.[0-9a-f]+$/);
    if (m) return m[1].replace(/^cts_gis\./, "");
    // msn-SAMRAS source datum (with hash): sc.<corpus>.msn-<id>.<hash>
    m = name.match(/\.(msn-[^.]+)\.[0-9a-f]+$/);
    if (m) return m[1];
    // msn-* cache files (no hash): sc.<corpus>.msn-<name>
    m = name.match(/\.(msn-[^.]+)$/);
    if (m) return m[1];
    // Legacy: sc.<corpus>.cts.<id_underscored>
    m = name.match(/\.(cts\.[^.]+)$/);
    if (m) return m[1];
    // Legacy: sc.<corpus>.fnd.<id>
    m = name.match(/\.(fnd\.[^.]+)$/);
    if (m) return m[1];
    // Singleton tool/registrar files: sc.<corpus>.<bare-name>
    m = name.match(/\.([a-z][a-z0-9_-]*)$/);
    if (m) return m[1];
    return name;
  }

  function prettyJson(value) {
    if (value == null) return "";
    try {
      return JSON.stringify(value, null, 2);
    } catch (_) {
      return String(value);
    }
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
          renderTable({ columns: subsection.columns, items: subsection.rows || subsection.items || [] }) +
          (subsection.preformatted
            ? '<pre class="lr-workbench__miniPre">' + escapeHtml(subsection.preformatted) + "</pre>"
            : "") +
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
          (section.preformatted ? '<pre class="lr-workbench__miniPre">' + escapeHtml(section.preformatted) + "</pre>" : "") +
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

  function renderGranteeSelector(selector) {
    if (!selector) return "";
    var grantees = asList(selector.grantees);
    var label = asText(selector.label) || "Grantee";
    if (!grantees.length) {
      return (
        '<section class="v2-card v2-granteeSelector" style="margin-top:0">' +
        "<h3>" +
        escapeHtml(label) +
        "</h3>" +
        '<p class="v2-granteeSelector__empty">' +
        escapeHtml(asText(selector.empty_message) || "No grantees configured.") +
        "</p></section>"
      );
    }
    var optionsHtml = grantees
      .map(function (grantee, index) {
        var msn = asText(grantee.msn_id);
        var name = asText(grantee.label) || msn || "—";
        var domains = asList(grantee.domains).join(", ");
        var active = grantee.active === true;
        var isOverall = grantee.is_overall === true;
        return (
          '<button type="button" class="v2-granteeSelector__option' +
          (active ? " is-active" : "") +
          (isOverall ? " is-overall" : "") +
          '" data-grantee-msn="' +
          escapeHtml(msn) +
          '" data-grantee-index="' +
          String(index) +
          '" aria-pressed="' +
          (active ? "true" : "false") +
          '">' +
          '<span class="v2-granteeSelector__optionLabel">' +
          escapeHtml(name) +
          "</span>" +
          (domains
            ? '<span class="v2-granteeSelector__optionDomains">' + escapeHtml(domains) + "</span>"
            : "") +
          "</button>"
        );
      })
      .join("");
    return (
      '<section class="v2-card v2-granteeSelector" style="margin-top:0">' +
      "<h3>" +
      escapeHtml(label) +
      "</h3>" +
      '<div class="v2-granteeSelector__options" role="group">' +
      optionsHtml +
      "</div></section>"
    );
  }

  function bindGranteeSelector(ctx, target, selector) {
    if (!selector || !target) return;
    var grantees = asList(selector.grantees);
    if (!grantees.length) return;
    Array.prototype.forEach.call(
      target.querySelectorAll(".v2-granteeSelector__option"),
      function (node) {
        // Idempotency guard (like bindInnerSubtabs/bindResourcesApp): the in-card
        // picker means this can be invoked more than once per render; never
        // double-bind a click handler.
        if (node.dataset.granteeBound === "1") return;
        node.dataset.granteeBound = "1";
        node.addEventListener("click", function () {
          var index = Number(node.getAttribute("data-grantee-index"));
          if (Number.isNaN(index) || index < 0 || index >= grantees.length) return;
          var grantee = grantees[index] || {};
          var action = asObject(grantee.select_action);
          var payload = asObject(action.payload);
          if (!payload || !payload.requested_surface_id) return;
          if (typeof ctx.loadShell === "function") {
            ctx.loadShell(payload);
          }
        });
      }
    );
  }

  // Phase 15a — extension subtab strip (Email / Analytics / Newsletter
  // / PayPal). Mirrors the grantee selector mechanic: server-side
  // reload on click via ctx.loadShell so the page's surface_payload
  // narrows to the active tab.
  function renderExtensionTabs(selector) {
    if (!selector) return "";
    var tabs = asList(selector.tabs);
    if (!tabs.length) return "";
    var label = asText(selector.label) || "Extension";
    var optionsHtml = tabs
      .map(function (tab, index) {
        var toolId = asText(tab.tool_id);
        var labelText = asText(tab.label) || toolId || "—";
        var active = tab.active === true;
        return (
          '<button type="button" class="v2-extensionTabs__option' +
          (active ? " is-active" : "") +
          '" data-extension-tool-id="' +
          escapeHtml(toolId) +
          '" data-extension-tab-index="' +
          String(index) +
          '" aria-pressed="' +
          (active ? "true" : "false") +
          '">' +
          '<span class="v2-extensionTabs__optionLabel">' +
          escapeHtml(labelText) +
          "</span>" +
          "</button>"
        );
      })
      .join("");
    return (
      '<section class="v2-card v2-extensionTabs" style="margin-top:0">' +
      "<h3>" +
      escapeHtml(label) +
      "</h3>" +
      '<div class="v2-extensionTabs__options" role="tablist">' +
      optionsHtml +
      "</div></section>"
    );
  }

  function bindExtensionTabs(ctx, target, selector) {
    if (!selector || !target) return;
    var tabs = asList(selector.tabs);
    if (!tabs.length) return;
    Array.prototype.forEach.call(
      target.querySelectorAll(".v2-extensionTabs__option"),
      function (node) {
        node.addEventListener("click", function () {
          var index = Number(node.getAttribute("data-extension-tab-index"));
          if (Number.isNaN(index) || index < 0 || index >= tabs.length) return;
          var tab = tabs[index] || {};
          var action = asObject(tab.select_action);
          var payload = asObject(action.payload);
          if (!payload || !payload.requested_surface_id) return;
          if (typeof ctx.loadShell === "function") {
            ctx.loadShell(payload);
          }
        });
      }
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

  function buildModuleRegistrationMessage(label, moduleId, globalName, callableName) {
    var message =
      "The " +
      asText(label || "surface") +
      " renderer contract is unavailable. " +
      "module_id=" +
      moduleId +
      " expected_global=" +
      globalName +
      " expected_callable=" +
      callableName +
      ".";
    if (typeof window.__MYCITE_V2_GET_SHELL_MODULE_DIAGNOSTICS !== "function") {
      return message;
    }
    var diagnostics = window.__MYCITE_V2_GET_SHELL_MODULE_DIAGNOSTICS(moduleId) || {};
    var loadedScripts = asList(diagnostics.script_load_order)
      .map(function (entry) {
        return asText((entry && entry.module_id) || (entry && entry.file));
      })
      .filter(Boolean);
    var registeredModules = asList(diagnostics.registered_module_ids)
      .map(function (entry) {
        return asText(entry);
      })
      .filter(Boolean);
    var invalidMessages = asList(diagnostics.invalid_messages)
      .map(function (entry) {
        return asText(entry);
      })
      .filter(Boolean);
    var failures = asList(diagnostics.failures)
      .map(function (entry) {
        return asText(entry);
      })
      .filter(Boolean);
    return (
      message +
      " boot_stage=" +
      (asText(diagnostics.boot_stage) || "unknown") +
      " loaded_scripts=" +
      (loadedScripts.join(" -> ") || "none") +
      " registered_modules=" +
      (registeredModules.join(", ") || "none") +
      " invalid_registrations=" +
      (invalidMessages.join("; ") || "none") +
      (failures.length ? " contract_failures=" + failures.join("; ") : "")
    );
  }

  // Phase 14a: render the utilities-tab extension payloads emitted by
  // _build_utilities_extensions. The runtime returns a list of
  // `{tool_id, label, summary, payload}` entries; the payload shape
  // varies by extension (form_frame / configuration+rows / orders /
  // contact_rows / events). renderExtensionCard dispatches by shape.
  function renderConfigurationItems(items) {
    if (!items || !items.length) return "";
    return (
      '<dl class="v2-extensionCard__configList">' +
      items
        .map(function (item) {
          return (
            "<dt>" +
            escapeHtml(asText(item.label) || "") +
            "</dt><dd>" +
            escapeHtml(asText(item.value) || "—") +
            "</dd>"
          );
        })
        .join("") +
      "</dl>"
    );
  }

  function renderConfigurationSection(cfg) {
    var c = asObject(cfg);
    if (!c.label && !asList(c.items).length && !c.edit_link) return "";
    var editLink = asObject(c.edit_link);
    var editHref = asText(editLink.href);
    var editLabel = asText(editLink.label) || "Edit in Grantee Profile";
    return (
      '<section class="v2-extensionCard__config">' +
      (c.label ? "<h4>" + escapeHtml(asText(c.label)) + "</h4>" : "") +
      (c.summary ? '<p class="v2-extensionCard__summary">' + escapeHtml(asText(c.summary)) + "</p>" : "") +
      renderConfigurationItems(asList(c.items)) +
      (editHref
        ? '<a class="v2-extensionCard__editLink" href="' +
          escapeHtml(editHref) +
          '">' +
          escapeHtml(editLabel) +
          "</a>"
        : "") +
      "</section>"
    );
  }

  function renderRowsTable(title, rows, columns) {
    var rowList = asList(rows);
    if (!rowList.length) return "";
    return (
      '<section class="v2-extensionCard__table">' +
      (title ? "<h4>" + escapeHtml(asText(title)) + "</h4>" : "") +
      '<div class="v2-tableWrap"><table class="v2-table"><thead><tr>' +
      columns
        .map(function (col) {
          return "<th>" + escapeHtml(asText(col.label)) + "</th>";
        })
        .join("") +
      "</tr></thead><tbody>" +
      rowList
        .map(function (row) {
          return (
            "<tr>" +
            columns
              .map(function (col) {
                var v = row[col.key];
                if (typeof v === "boolean") v = v ? "yes" : "no";
                if (v == null) v = "";
                return "<td>" + escapeHtml(String(v)) + "</td>";
              })
              .join("") +
            "</tr>"
          );
        })
        .join("") +
      "</tbody></table></div></section>"
    );
  }

  function componentLibrary() {
    return window.PortalComponentLibrary || null;
  }

  function renderAdminForms(forms) {
    var list = asList(forms);
    if (!list.length) return "";
    var lib = componentLibrary();
    if (!lib || typeof lib.renderComponentFrame !== "function") return "";
    return list
      .map(function (frame) {
        return lib.renderComponentFrame(asObject(frame));
      })
      .join("");
  }

  function renderRowAction(action) {
    var a = asObject(action);
    if (!a.route || !a.label) return "";
    var variant = asText(a.variant) || "secondary";
    var payload = JSON.stringify(asObject(a.payload));
    var schema = asText(a.schema);
    var confirm = asText(a.confirm);
    // Server can mark an action disabled (e.g. reminder still in 24h
    // cooldown) by setting action.disabled === true. We render the button
    // with the HTML `disabled` attribute + a "is-disabled" class so the
    // existing click handler in bindRowAction will not fire.
    var disabled = a.disabled === true;
    return (
      '<button type="button" class="v2-rowAction v2-rowAction--' +
      escapeHtml(variant) + (disabled ? " is-disabled" : "") +
      '"' +
      (disabled ? " disabled" : "") +
      ' data-row-action-route="' +
      escapeHtml(asText(a.route)) +
      '"' +
      (schema ? ' data-row-action-schema="' + escapeHtml(schema) + '"' : "") +
      (confirm ? ' data-row-action-confirm="' + escapeHtml(confirm) + '"' : "") +
      " data-row-action-payload='" +
      escapeHtml(payload) +
      "'>" +
      escapeHtml(asText(a.label)) +
      "</button>"
    );
  }

  // B3 — overlay badge config. Each state from the server's AwsEvidence
  // payload maps to a glyph + a CSS modifier class + a hover-tooltip
  // prefix. Unknown states fall through to the dim "no data" appearance.
  var OVERLAY_BADGE_BY_STATE = {
    confirmed:    { glyph: "✓",  cls: "is-confirmed",    tip: "AWS confirms" },
    auto_advance: { glyph: "↑",  cls: "is-autoadvance",  tip: "AWS evidence advances this step" },
    drift:        { glyph: "⚠",  cls: "is-drift",        tip: "Flag says complete but AWS has no evidence" },
    absent:       { glyph: "·",  cls: "is-absent",       tip: "No AWS evidence yet" },
    error:        { glyph: "?",  cls: "is-error",        tip: "Probe failed" }
  };

  function renderOverlayBadge(evidence) {
    var e = asObject(evidence);
    var state = asText(e.state);
    if (!state) return "";
    var spec = OVERLAY_BADGE_BY_STATE[state] || OVERLAY_BADGE_BY_STATE.absent;
    var detail = asText(e.detail);
    var title = spec.tip + (detail ? ": " + detail : "");
    return (
      '<span class="v2-overlayBadge v2-overlayBadge--' +
      escapeHtml(spec.cls) + '" title="' + escapeHtml(title) + '">' +
      escapeHtml(spec.glyph) +
      '</span>'
    );
  }

  function renderOnboardingProgressCell(progress) {
    var p = asObject(progress);
    var total = Number(p.steps_total) || 0;
    var done = Number(p.steps_done) || 0;
    var pct = Number(p.percent) || 0;
    var nextStep = asObject(p.next_step);
    var nextLabel = asText(nextStep.label);
    var title = done + " of " + total + " complete";
    if (nextLabel) title += " · next: " + nextLabel;
    // B3 — overlay badges per probed step. Server emits aws_evidence as a
    // dict keyed by step name; we render one badge per present key. Steps
    // with no probe (1, 3, 5) are absent from the dict and render nothing.
    var evidence = asObject(p.aws_evidence);
    var badges = "";
    ["ses_identity_ready", "handoff_acked", "inbound_verified"].forEach(function (k) {
      if (evidence[k]) badges += renderOverlayBadge(evidence[k]);
    });
    // Use semantic <progress> so screen readers + CSS-less rendering still
    // convey the value. value/max are integers; the visible % label sits
    // below so a glance reads the same number assistive tech announces.
    return (
      '<td class="v2-mailboxes__progressCell" title="' +
      escapeHtml(title) + '">' +
      '<progress class="v2-mailboxes__progress" value="' + pct +
      '" max="100">' + pct + '%</progress>' +
      '<span class="v2-mailboxes__progressLabel">' + pct + '%' +
      (total ? ' (' + done + '/' + total + ')' : '') +
      '</span>' +
      (badges ? '<span class="v2-mailboxes__overlayBadges">' + badges + '</span>' : "") +
      '</td>'
    );
  }

  function renderRowsTableWithActions(title, rows, columns, actionKey, actionLabel) {
    var rowList = asList(rows);
    if (!rowList.length) return "";
    var hasActions = rowList.some(function (r) {
      var a = asObject(r)[actionKey];
      return a && asObject(a).route;
    });
    return (
      '<section class="v2-extensionCard__table">' +
      (title ? "<h4>" + escapeHtml(asText(title)) + "</h4>" : "") +
      '<div class="v2-tableWrap"><table class="v2-table"><thead><tr>' +
      columns
        .map(function (col) {
          return "<th>" + escapeHtml(asText(col.label)) + "</th>";
        })
        .join("") +
      (hasActions ? "<th>" + escapeHtml(asText(actionLabel) || "Actions") + "</th>" : "") +
      "</tr></thead><tbody>" +
      rowList
        .map(function (row) {
          var cells = columns
            .map(function (col) {
              var v = row[col.key];
              if (typeof v === "boolean") v = v ? "yes" : "no";
              if (v == null) v = "";
              return "<td>" + escapeHtml(String(v)) + "</td>";
            })
            .join("");
          var actionCell = hasActions
            ? "<td>" + renderRowAction(row[actionKey]) + "</td>"
            : "";
          return "<tr>" + cells + actionCell + "</tr>";
        })
        .join("") +
      "</tbody></table></div></section>"
    );
  }

  function renderContactsTable(rows) {
    // Phase 15b: split-name + email columns; Phase 16a: phone, zip,
    // signup_date columns + per-row inline edit form (expanded on
    // demand via bindContactEditActions).
    var rowList = asList(rows);
    if (!rowList.length) return "";
    var columns = [
      { key: "email", label: "Email" },
      { key: "name", label: "Name" },
      { key: "phone", label: "Phone" },
      { key: "zip", label: "ZIP" },
      { key: "signup_date", label: "Signup" },
      { key: "subscribed", label: "Subscribed" },
      { key: "source", label: "Source" },
      { key: "send_count", label: "Sends" },
      { key: "last_sent", label: "Last sent" },
    ];
    var hasActions = rowList.some(function (r) {
      var rm = asObject(r).remove_action;
      var ed = asObject(r).edit_action;
      return (rm && rm.route) || (ed && ed.route);
    });
    var actionColspan = columns.length + (hasActions ? 1 : 0);
    return (
      '<section class="v2-extensionCard__table v2-extensionCard__contacts">' +
      "<h4>Contacts</h4>" +
      '<div class="v2-tableWrap"><table class="v2-table"><thead><tr>' +
      columns
        .map(function (col) {
          return "<th>" + escapeHtml(asText(col.label)) + "</th>";
        })
        .join("") +
      (hasActions ? "<th>Actions</th>" : "") +
      "</tr></thead><tbody>" +
      rowList
        .map(function (row, index) {
          var cells = columns
            .map(function (col) {
              var v = row[col.key];
              if (typeof v === "boolean") v = v ? "yes" : "no";
              if (v == null) v = "";
              return "<td>" + escapeHtml(String(v)) + "</td>";
            })
            .join("");
          var actionCell = "";
          if (hasActions) {
            var inner = "";
            if (asObject(row.edit_action).route) {
              inner += renderEditToggleButton(row.edit_action, index);
            }
            if (asObject(row.remove_action).route) {
              inner += renderRowAction(row.remove_action);
            }
            actionCell = "<td>" + inner + "</td>";
          }
          var mainRow = '<tr data-contact-row-index="' + String(index) + '">' + cells + actionCell + "</tr>";
          var editForm = "";
          if (asObject(row.edit_action).route) {
            editForm =
              '<tr class="v2-contactEditRow" data-contact-edit-index="' + String(index) +
              '" hidden><td colspan="' + String(actionColspan) + '">' +
              renderInlineEditForm(row.edit_action) +
              "</td></tr>";
          }
          return mainRow + editForm;
        })
        .join("") +
      "</tbody></table></div></section>"
    );
  }

  function renderEditToggleButton(action, index) {
    var a = asObject(action);
    var variant = asText(a.variant) || "secondary";
    return (
      '<button type="button" class="v2-rowAction v2-rowAction--' +
      escapeHtml(variant) +
      '" data-contact-edit-toggle="' +
      String(index) +
      '">' +
      escapeHtml(asText(a.label) || "Edit") +
      "</button>"
    );
  }

  function renderInlineEditForm(action) {
    var a = asObject(action);
    var fields = asList(a.editable_fields);
    var route = asText(a.route);
    var schema = asText(a.schema);
    var payload = JSON.stringify(asObject(a.payload));
    return (
      '<form class="v2-contactEditForm" data-contact-edit-route="' +
      escapeHtml(route) +
      '" data-contact-edit-schema="' +
      escapeHtml(schema) +
      "\" data-contact-edit-payload='" +
      escapeHtml(payload) +
      "'>" +
      fields
        .map(function (f) {
          var key = asText(f.key);
          var label = asText(f.label) || key;
          var value = asText(f.value);
          return (
            '<label class="v2-contactEditForm__label">' +
            "<span>" +
            escapeHtml(label) +
            "</span>" +
            '<input type="text" data-contact-edit-key="' +
            escapeHtml(key) +
            '" value="' +
            escapeHtml(value) +
            '">' +
            "</label>"
          );
        })
        .join("") +
      '<div class="v2-contactEditForm__actions">' +
      '<button type="submit" class="v2-rowAction v2-rowAction--primary">Save</button>' +
      '<button type="button" class="v2-rowAction v2-rowAction--secondary" data-contact-edit-cancel="1">Cancel</button>' +
      "</div></form>"
    );
  }

  function renderConnectSubmissionsTable(rows) {
    // Phase 17b — Connect-form submissions table. Wider than the
    // newsletter contacts table because each row carries a subject +
    // free-text message that the operator needs to read in place.
    var rowList = asList(rows);
    if (!rowList.length) return "";
    var columns = [
      { key: "signup_date", label: "Date" },
      { key: "name", label: "Name" },
      { key: "email", label: "Email" },
      { key: "phone", label: "Phone" },
      { key: "zip", label: "ZIP" },
      { key: "subject", label: "Subject" },
      { key: "message", label: "Message" },
      { key: "forward_status", label: "Forwarded" },
      { key: "subscribed_to_newsletter", label: "Subscribed" },
    ];
    return (
      '<section class="v2-extensionCard__table v2-extensionCard__connect">' +
      "<h4>Connect submissions</h4>" +
      '<div class="v2-tableWrap"><table class="v2-table"><thead><tr>' +
      columns.map(function (c) { return "<th>" + escapeHtml(asText(c.label)) + "</th>"; }).join("") +
      "</tr></thead><tbody>" +
      rowList.map(function (row) {
        return "<tr>" + columns.map(function (col) {
          var v = row[col.key];
          if (typeof v === "boolean") v = v ? "yes" : "no";
          if (v == null) v = "";
          // Message column gets a wrapper so long bodies don't blow
          // out the table width.
          if (col.key === "message") {
            return '<td><div class="v2-extensionCard__connectMessage">' +
              escapeHtml(String(v)) + "</div></td>";
          }
          return "<td>" + escapeHtml(String(v)) + "</td>";
        }).join("") + "</tr>";
      }).join("") +
      "</tbody></table></div></section>"
    );
  }

  // B3 — what AWS source each step is verifiable against. Keyed by the
  // step's `key` field (server-side _ONBOARDING_STEPS). Steps without
  // a probe show "—". Surfaced as the legend table's "Live evidence"
  // column so the operator knows which steps the overlay badges reflect.
  var STEP_KEY_TO_LIVE_EVIDENCE_SOURCE = {
    profile_created:    "—",
    ses_identity_ready: "SES VerificationStatus",
    handoff_sent:       "—",
    handoff_acked:      "CloudWatch AWS/SES Send (per identity)",
    inbound_configured: "—",
    inbound_verified:   "S3 inbound/<domain>/ objects"
  };

  function renderOnboardingLegendTable(legend) {
    // 2026-05-23: static reference table above the Mailboxes table.
    // Explains what each step in the per-row "X of 6" progress bar
    // actually means so the operator doesn't have to read JSON to
    // interpret a partial score. Rows are static (server emits the
    // same six rows for every grantee) — no actions, no edit cell.
    //
    // B3 (2026-05-23): adds a "Live evidence" column documenting which
    // AWS data source the overlay badge for each step is computed from
    // (— for steps without a live probe).
    var rowList = asList(legend);
    if (!rowList.length) return "";
    var columns = [
      { key: "step", label: "#" },
      { key: "stage", label: "Stage" },
      { key: "meaning", label: "What it means" },
      { key: "_live", label: "Live evidence" },
    ];
    return (
      '<section class="v2-extensionCard__table v2-extensionCard__onboardingLegend">' +
      "<h4>Onboarding stages</h4>" +
      '<p class="v2-extensionCard__summary">Each mailbox’s progress bar advances through these six stages in order. The right column shows which AWS data source the live-evidence badge on a row reflects.</p>' +
      '<div class="v2-tableWrap"><table class="v2-table"><thead><tr>' +
      columns.map(function (c) { return "<th>" + escapeHtml(asText(c.label)) + "</th>"; }).join("") +
      "</tr></thead><tbody>" +
      rowList.map(function (row) {
        var r = asObject(row);
        var live = STEP_KEY_TO_LIVE_EVIDENCE_SOURCE[asText(r.key)] || "—";
        return "<tr>" + columns.map(function (c) {
          if (c.key === "_live") {
            return "<td>" + escapeHtml(live) + "</td>";
          }
          return "<td>" + escapeHtml(asText(r[c.key])) + "</td>";
        }).join("") + "</tr>";
      }).join("") +
      "</tbody></table></div></section>"
    );
  }

  function renderMailboxesTable(rows) {
    // Phase 16c: Domain column so operators of multi-domain grantees
    // (e.g. CVCC owns cvcc + cvccboard) can tell which mailbox lives
    // where. Rows are sorted by domain then mailbox server-side.
    //
    // 2026-05-22: per-row onboarding-progress bar + three-action cell
    // (suspend / resend handoff / send reminder). The progress cell has
    // its own renderer (renderOnboardingProgressCell); other columns are
    // plain text. The action cell concatenates whichever of the actions
    // the server provided — empty actions render nothing.
    //
    // 2026-05-23: added per-row Edit (inline form expands a hidden row)
    // and Remove buttons. Edit uses the same `renderInlineEditForm`
    // primitive as the contacts table; bindMailboxEditActions handles
    // toggle/cancel/submit using the dedicated data-mailbox-edit-* attrs
    // so it can't collide with the contacts-table bindings.
    var rowList = asList(rows);
    if (!rowList.length) return "";
    var textColumns = [
      { key: "domain", label: "Domain" },
      { key: "mailbox", label: "Mailbox" },
      { key: "send_as", label: "Send-as" },
      { key: "role", label: "Role" },
      { key: "lifecycle", label: "Lifecycle" },
      { key: "inbound", label: "Inbound" },
    ];
    var actionKeys = [
      "edit_action",
      "suspend_action",
      "resend_handoff_action",
      "send_reminder_action",
      "remove_action",
    ];
    var hasActions = rowList.some(function (r) {
      var ro = asObject(r);
      return actionKeys.some(function (k) {
        var a = asObject(ro[k]);
        return a && a.route;
      });
    });
    var headerCells = textColumns
      .map(function (col) { return "<th>" + escapeHtml(asText(col.label)) + "</th>"; })
      .join("") + "<th>Onboarding</th>" +
      (hasActions ? "<th>Actions</th>" : "");
    var actionColspan = textColumns.length + 1 + (hasActions ? 1 : 0);
    var bodyRows = rowList.map(function (row, index) {
      var r = asObject(row);
      var textCells = textColumns.map(function (col) {
        var v = r[col.key];
        if (typeof v === "boolean") v = v ? "yes" : "no";
        if (v == null) v = "";
        return "<td>" + escapeHtml(String(v)) + "</td>";
      }).join("");
      var progressCell = renderOnboardingProgressCell(r.onboarding_progress);
      var actionCell = "";
      if (hasActions) {
        var parts = [];
        if (asObject(r.edit_action).route) {
          parts.push(renderMailboxEditToggleButton(r.edit_action, index));
        }
        ["suspend_action", "resend_handoff_action", "send_reminder_action", "remove_action"]
          .forEach(function (k) {
            if (asObject(r[k]).route) parts.push(renderRowAction(r[k]));
          });
        actionCell = "<td>" + parts.join(" ") + "</td>";
      }
      var mainRow =
        '<tr data-mailbox-row-index="' + String(index) + '">' +
        textCells + progressCell + actionCell + "</tr>";
      var editRow = "";
      if (asObject(r.edit_action).route) {
        editRow =
          '<tr class="v2-mailboxEditRow" data-mailbox-edit-index="' + String(index) +
          '" hidden><td colspan="' + String(actionColspan) + '">' +
          renderMailboxInlineEditForm(r.edit_action) +
          "</td></tr>";
      }
      return mainRow + editRow;
    }).join("");
    return (
      '<section class="v2-extensionCard__table v2-extensionCard__mailboxes">' +
      "<h4>Mailboxes</h4>" +
      '<div class="v2-tableWrap"><table class="v2-table"><thead><tr>' +
      headerCells + "</tr></thead><tbody>" + bodyRows +
      "</tbody></table></div></section>"
    );
  }

  function renderMailboxEditToggleButton(action, index) {
    var a = asObject(action);
    var variant = asText(a.variant) || "secondary";
    return (
      '<button type="button" class="v2-rowAction v2-rowAction--' +
      escapeHtml(variant) +
      '" data-mailbox-edit-toggle="' +
      String(index) +
      '">' +
      escapeHtml(asText(a.label) || "Edit") +
      "</button>"
    );
  }

  function renderMailboxInlineEditForm(action) {
    var a = asObject(action);
    var fields = asList(a.editable_fields);
    var route = asText(a.route);
    var schema = asText(a.schema);
    var payload = JSON.stringify(asObject(a.payload));
    return (
      '<form class="v2-mailboxEditForm" data-mailbox-edit-route="' +
      escapeHtml(route) +
      '" data-mailbox-edit-schema="' +
      escapeHtml(schema) +
      "\" data-mailbox-edit-payload='" +
      escapeHtml(payload) +
      "'>" +
      fields.map(function (f) {
        var key = asText(f.key);
        var label = asText(f.label) || key;
        var value = asText(f.value);
        return (
          '<label class="v2-mailboxEditForm__label">' +
          "<span>" + escapeHtml(label) + "</span>" +
          '<input type="text" data-mailbox-edit-key="' +
          escapeHtml(key) +
          '" value="' + escapeHtml(value) + '">' +
          "</label>"
        );
      }).join("") +
      '<div class="v2-mailboxEditForm__actions">' +
      '<button type="submit" class="v2-rowAction v2-rowAction--primary">Save</button>' +
      '<button type="button" class="v2-rowAction v2-rowAction--secondary" data-mailbox-edit-cancel="1">Cancel</button>' +
      "</div></form>"
    );
  }

  // GLOBAL ("Overall") roster for an operational extension: one row per
  // grantee with a cheap status. Informational — engagement is via the
  // grantee selector at the top of the surface.
  function renderOverallRoster(p) {
    var grantees = asList(p.grantees);
    var label = asText(p.extension_label) || "Overall";
    var intro =
      '<p class="v2-extensionCard__intro">' + escapeHtml(label) +
      " — all grantees (" + escapeHtml(String(p.count != null ? p.count : grantees.length)) +
      "). Select a grantee above to manage one individually.</p>";
    if (!grantees.length) {
      return intro + '<p class="v2-extensionCard__empty">No grantees configured.</p>';
    }
    var rows = grantees.map(function (g) {
      var gg = asObject(g);
      return {
        grantee: asText(gg.label) || asText(gg.msn_id),
        domains: asList(gg.domains).join(", ") || "—",
        status: asText(gg.summary) || "—",
      };
    });
    return (
      intro +
      renderRowsTable("", rows, [
        { key: "grantee", label: "Grantee" },
        { key: "domains", label: "Domains" },
        { key: "status", label: "Status" },
      ])
    );
  }

  function renderExtensionCardBody(payload) {
    var p = asObject(payload);
    // The Per-grantee subtab hosts the grantee picker in-card (when present).
    var picker = p.grantee_picker ? renderGranteeSelector(p.grantee_picker) : "";
    var html = picker;

    // ext_resources renders its own self-contained asset-library app.
    if (p.resources_app) {
      return picker + renderResourcesApp(p);
    }

    // Per-grantee subtab with no grantee chosen yet → picker + a prompt.
    if (asText(p.per_grantee_prompt)) {
      return picker +
        '<p class="v2-extensionCard__empty">' + escapeHtml(asText(p.per_grantee_prompt)) + "</p>";
    }

    // GLOBAL ("Overall") mode: a read-only roster of every grantee for this
    // extension. Pick one from the Per-grantee subtab to manage it.
    if (p.overall_roster) {
      return picker + renderOverallRoster(p);
    }

    if (asObject(p.form_frame).component_type) {
      var lib = componentLibrary();
      if (lib && typeof lib.renderComponentFrame === "function") {
        html += lib.renderComponentFrame(p.form_frame);
      }
    }
    html += renderAdminForms(p.admin_forms);
    if (asObject(p.refresh_action).route) {
      html +=
        '<div class="v2-extensionCard__refresh">' +
        renderRowAction(p.refresh_action) +
        "</div>";
    }
    if (asObject(p.export_action).href) {
      var ea = asObject(p.export_action);
      var variant = asText(ea.variant) || "secondary";
      html +=
        '<div class="v2-extensionCard__export">' +
        '<a class="v2-extensionCard__exportLink v2-rowAction--' +
        escapeHtml(variant) +
        '" href="' +
        escapeHtml(asText(ea.href)) +
        '"' +
        (asText(ea.download) ? ' download="' + escapeHtml(asText(ea.download)) + '"' : "") +
        ">" +
        escapeHtml(asText(ea.label) || "Export") +
        "</a></div>";
    }
    if (asText(p.notice)) {
      html +=
        '<p class="v2-extensionCard__notice">' + escapeHtml(asText(p.notice)) + "</p>";
    }
    if (asObject(p.configuration).items || asObject(p.configuration).label) {
      html += renderConfigurationSection(p.configuration);
    }
    if (asObject(p.data_source).label) {
      html += renderConfigurationSection(p.data_source);
    }
    if (asObject(p.summary) && Object.keys(asObject(p.summary)).length) {
      var summaryRows = Object.keys(p.summary).map(function (k) {
        return { key: k, count: p.summary[k] };
      });
      html += renderRowsTable("Event totals", summaryRows, [
        { key: "key", label: "Event type" },
        { key: "count", label: "Count" },
      ]);
    }
    if (asList(p.top_paths).length) {
      html += renderRowsTable("Top paths", p.top_paths, [
        { key: "path", label: "Path" },
        { key: "count", label: "Views" },
      ]);
    }
    // Phase 18c: insight tables computed on-demand from the raw
    // NDJSON log by the Analytics extension renderer.
    if (
      typeof p.visitor_count !== "undefined"
      || typeof p.repeat_visitor_count !== "undefined"
      || typeof p.high_intent_count !== "undefined"
    ) {
      html += renderRowsTable("Visitor breakdown", [
        { metric: "Distinct visitors (humans)", value: String(p.visitor_count || 0) },
        { metric: "Repeat visitors (>= 2 sessions)", value: String(p.repeat_visitor_count || 0) },
        { metric: "High-intent sessions", value: String(p.high_intent_count || 0) },
        { metric: "Sessions (total)", value: String(p.session_count || 0) },
        { metric: "Bot events filtered", value: String(p.bot_event_count || 0) },
        { metric: "VPN / geo-jump flags", value: String(p.vpn_geo_jump_count || 0) },
      ], [
        { key: "metric", label: "Metric" },
        { key: "value", label: "Count" },
      ]);
    }
    if (asList(p.top_referrers).length) {
      html += renderRowsTable("Top referrers", p.top_referrers, [
        { key: "referrer_domain", label: "Referrer" },
        { key: "sessions", label: "Sessions" },
        { key: "unique_visitors", label: "Visitors" },
        { key: "average_active_time_ms", label: "Avg active ms" },
      ]);
    }
    if (asList(p.top_entry_pages).length) {
      html += renderRowsTable("Top entry pages", p.top_entry_pages, [
        { key: "page_path", label: "Entry page" },
        { key: "count", label: "Sessions" },
      ]);
    }
    if (asList(p.top_exit_pages).length) {
      html += renderRowsTable("Top exit pages", p.top_exit_pages, [
        { key: "page_path", label: "Exit page" },
        { key: "count", label: "Sessions" },
      ]);
    }
    if (asList(p.common_paths).length) {
      html += renderRowsTable("Common page sequences", p.common_paths, [
        { key: "path", label: "Sequence" },
        { key: "count", label: "Count" },
      ]);
    }
    if (asList(p.recent_events).length) {
      html += renderRowsTable("Recent events", p.recent_events, [
        { key: "event_type", label: "Event" },
        { key: "path", label: "Path" },
        { key: "timestamp", label: "Time" },
      ]);
    }
    if (asList(p.contact_rows).length) {
      html += renderContactsTable(p.contact_rows);
    }
    if (asList(p.submissions).length) {
      html += renderConnectSubmissionsTable(p.submissions);
    }
    if (asList(p.orders).length) {
      html += renderRowsTable("Orders", p.orders, [
        { key: "order_id", label: "Order" },
        { key: "amount", label: "Amount" },
        { key: "currency_code", label: "Currency" },
        { key: "status", label: "Status" },
        { key: "event", label: "Event" },
      ]);
    }
    if (asList(p.profiles).length || asList(p.onboarding_legend).length) {
      html += renderOnboardingLegendTable(p.onboarding_legend);
    }
    if (asList(p.profiles).length) {
      html += renderMailboxesTable(p.profiles);
    }
    if (asText(p.empty_message) && !html) {
      html += '<p class="v2-extensionCard__empty">' + escapeHtml(asText(p.empty_message)) + "</p>";
    }
    return html;
  }

  // --- ext_resources: the shared site-core asset library ----------------
  // The resources extension is a small app rendered inside its extension
  // card: a phone-contacts-style profiles roster (logo thumbnail + name) that
  // opens a per-profile detail/edit view, gallery counts, an upload form, and
  // icon-dedup affordances. All actions post to the /__fnd/resources/* +
  // /portal/api/resources/* routes. See resources_extension.py.
  function renderResourcesUpload(payload) {
    var action = asObject(payload.upload_action);
    var route = asText(action.route) || "/portal/api/resources/upload";
    return (
      '<details class="v2-resourcesUpload" open><summary>Upload / create an asset</summary>' +
      '<form class="v2-resourcesUploadForm" data-resources-upload-route="' +
      escapeHtml(route) +
      '">' +
      '<label>Kind<select name="kind">' +
      '<option value="image">image (raster → AVIF)</option>' +
      '<option value="logo">logo (brand mark → 512² AVIF)</option>' +
      '<option value="icon">icon (SVG)</option>' +
      '<option value="document">document</option>' +
      '<option value="audio">audio</option>' +
      "</select></label>" +
      '<label>Title<input type="text" name="title" /></label>' +
      '<label>Slug<input type="text" name="slug" /></label>' +
      '<label>Owner<input type="text" name="owner" /></label>' +
      '<label>File<input type="file" name="file" required /></label>' +
      '<button type="submit" class="v2-rowAction--primary">Upload</button>' +
      '<p class="v2-resourcesUpload__hint">A <strong>logo</strong> named for an ' +
      "entity slug (e.g. <code>aurora_springs_honey</code>) is fit to a 512² AVIF " +
      "and resolves automatically against that profile's predetermined logo_ref — " +
      "no profile edit needed. <strong>Owner</strong> is ignored for logo/profile." +
      "</p>" +
      '<p class="v2-resourcesUpload__result" hidden></p>' +
      "</form></details>"
    );
  }

  // One uniform row per leaflet (any type) in the flat library table. Every
  // type is treated identically; the only organizing variable is the naming
  // convention (carried in data-resources-search for the filter). The full
  // metadata rides on data-* so the binary detail panel needs no extra fetch.
  // One compact, selectable list item per leaflet (any type). The full leaflet
  // object lives in JS state keyed by filename; the right pane shows detail +
  // actions on select. No per-row action buttons (those live in the detail).
  function renderLeafletListItem(r) {
    var leaf = asObject(r);
    var thumb = asText(leaf.image_url)
      ? '<img class="v2-resourcesThumb v2-resourcesThumb--sm" src="' +
        escapeHtml(asText(leaf.image_url)) +
        '" alt="" loading="lazy" onerror="this.style.display=\'none\'" />'
      : '<span class="v2-resourcesThumb v2-resourcesThumb--sm v2-resourcesThumb--dot" aria-hidden="true"></span>';
    var sub = asText(leaf.kind) +
      (asText(leaf.entity_type) ? " · " + asText(leaf.entity_type) : "") +
      (asText(leaf.owner) ? " · " + asText(leaf.owner) : "");
    return (
      '<button type="button" class="v2-leafletItem" data-filename="' +
      escapeHtml(asText(leaf.filename)) + '">' + thumb +
      '<span class="v2-leafletItem__text">' +
      '<span class="v2-leafletItem__title">' + escapeHtml(asText(leaf.title) || asText(leaf.slug)) + "</span>" +
      '<span class="v2-leafletItem__sub">' + escapeHtml(sub) + "</span></span>" +
      (leaf.in_use ? '<span class="v2-resourcesMember__badge">in use</span>' : "") +
      "</button>"
    );
  }

  function renderProfileHead(r) {
    var img = asText(r.image_url)
      ? '<img class="v2-resourcesThumb v2-resourcesThumb--lg" src="' + escapeHtml(asText(r.image_url)) +
        '" alt="" onerror="this.style.display=\'none\'" />'
      : "";
    return '<div class="v2-resourcesDetail__head">' + img + "<h4>" +
      escapeHtml(asText(r.title) || asText(r.slug)) + "</h4></div>";
  }

  // Read-only metadata for a non-profile leaflet, built from the leaflet object.
  function renderBinaryDetail(r) {
    var img = asText(r.image_url)
      ? '<img class="v2-resourcesThumb v2-resourcesThumb--lg" src="' + escapeHtml(asText(r.image_url)) +
        '" alt="" onerror="this.style.display=\'none\'" />'
      : "";
    var rows = [
      ["Kind", r.kind], ["Slug", r.slug], ["Variant", r.slug_variant], ["Owner", r.owner],
      ["Filename", r.filename], ["Asset path", r.asset_path], ["Extension", r.ext],
      ["Size (bytes)", String(r.size_bytes || 0)], ["In use", r.in_use ? "yes" : "no"],
    ].map(function (kv) {
      return '<div class="v2-resourcesField"><label>' + escapeHtml(kv[0]) +
        "</label><div>" + escapeHtml(asText(kv[1]) || "—") + "</div></div>";
    }).join("");
    return "<h4>" + escapeHtml(asText(r.title) || asText(r.display_name) || asText(r.slug)) + "</h4>" + img +
      '<div class="v2-resourcesDetail__meta">' + rows + "</div>";
  }

  function renderWhereUsed(r) {
    // Protected-from-delete: tell the operator exactly where the leaflet is in
    // use so they can de-allocate it (e.g. remove a profile from the network
    // map in the per-grantee Allocation view) and unlock Delete.
    var places = asList(r.in_use_by);
    var items = places.length
      ? "<ul class=\"v2-resourcesDetail__usedList\">" +
        places.map(function (p) { return "<li>" + escapeHtml(asText(p)) + "</li>"; }).join("") +
        "</ul>"
      : "";
    return '<div class="v2-resourcesDetail__protected">' +
      '<span class="v2-resourcesDedup__locked" title="In use by a site">In use — protected from delete.</span>' +
      items +
      '<p class="v2-resourcesDetail__hint">Remove it from these first (Allocation view), then Delete becomes available.</p>' +
      "</div>";
  }

  function renderManageActions(r) {
    var del = r.in_use
      ? renderWhereUsed(r)
      : '<button type="button" class="v2-rowAction--danger" data-manage="delete">Delete</button>';
    return '<div class="v2-resourcesDetail__actions">' +
      '<button type="button" class="v2-rowAction" data-manage="retitle">Retitle</button>' +
      '<button type="button" class="v2-rowAction" data-manage="rename">Rename slug</button>' +
      del + "</div>";
  }

  function titleCaseLabel(value) {
    var s = asText(value);
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
  }

  function renderResourcesLibrary(p) {
    var leaflets = asList(p.leaflets);
    // Embed the leaflet index as JSON for the client-side controller (filtering
    // + no-reload refresh read from JS state, not the DOM). Escape "<" so the
    // JSON can never close the script element early.
    var data = JSON.stringify(leaflets).replace(/</g, "\\u003c");
    function attr(name, val, dflt) { return " " + name + '="' + escapeHtml(asText(val) || dflt) + '"'; }
    return (
      '<div class="v2-resourcesApp" data-resources-mode="library"' +
      attr("data-detail-route", p.profile_detail_route, "/__fnd/resources/profile/detail") +
      attr("data-save-route", p.profile_save_route, "/__fnd/resources/profile/save") +
      attr("data-retitle-route", p.retitle_route, "/__fnd/resources/asset/retitle") +
      attr("data-rename-route", p.rename_slug_route, "/__fnd/resources/asset/rename-slug") +
      attr("data-rename-preview-route", p.rename_preview_route, "/__fnd/resources/asset/rename-preview") +
      attr("data-delete-route", p.delete_route, "/__fnd/resources/asset/delete") +
      attr("data-leaflets-route", p.leaflets_route, "/__fnd/resources/leaflets") + ">" +
      '<p class="v2-extensionCard__intro">Every shared leaflet in one place (' +
      escapeHtml(String(leaflets.length)) + "). Filter by naming convention on the left; " +
      "select a leaflet to view or edit it on the right.</p>" +
      '<script type="application/json" class="v2-leafletData">' + data + "</script>" +
      '<div class="v2-resourcesTwoPane">' +
        '<div class="v2-resourcesPane v2-resourcesPane--list">' +
          '<div class="v2-facetBar"></div>' +
          '<div class="v2-leafletList"></div>' +
          renderResourcesUpload(p) +
        "</div>" +
        '<div class="v2-resourcesPane v2-resourcesPane--detail">' +
          '<div class="v2-resourcesApp__detail">' +
          '<p class="v2-resourcesDetail__placeholder">Select a leaflet to view or edit.</p></div>' +
        "</div>" +
      "</div></div>"
    );
  }

  // Per-grantee ALLOCATION: per resource type, every library leaflet with an
  // Add / Remove toggle reflecting whether it is in this site's consolidated
  // shared_resources manifest (resources[kind]). In use / Available split.
  // Posts to manifest add/remove.
  function renderResourcesAllocationGallery(a, routes) {
    var gallery = asText(a.gallery);
    var kind = asText(a.kind);
    var candidates = asList(a.candidates);
    function renderMember(c) {
      var m = asObject(c);
      var allocated = m.allocated === true;
      var label = asText(m.slug) || asText(m.filename);
      var search = (asText(m.slug) + " " + asText(m.filename) + " " + asText(m.asset_id)).toLowerCase();
      var thumb = asText(m.image_url)
        ? '<img class="v2-resourcesThumb v2-resourcesThumb--sm" src="' +
          escapeHtml(asText(m.image_url)) + '" alt="" loading="lazy" onerror="this.style.display=\'none\'" />'
        : "";
      var btn = allocated
        ? '<button type="button" class="v2-rowAction--danger" data-resources-alloc="remove" data-kind="' +
          escapeHtml(kind) + '" data-asset-path="' + escapeHtml(asText(m.asset_path)) + '">Remove</button>'
        : '<button type="button" class="v2-rowAction" data-resources-alloc="add" data-kind="' +
          escapeHtml(kind) + '" data-asset-path="' + escapeHtml(asText(m.asset_path)) +
          '" data-asset-id="' + escapeHtml(asText(m.asset_id)) + '">Add</button>';
      return (
        '<div class="v2-resourcesMember' + (allocated ? " is-allocated" : "") +
        '" data-resources-search="' + escapeHtml(search) + '">' + thumb +
        '<code class="v2-resourcesMember__file">' + escapeHtml(label) + "</code> " +
        (allocated ? '<span class="v2-resourcesMember__badge">used</span>' : "") +
        '<span class="v2-resourcesMember__actions">' + btn + "</span></div>"
      );
    }
    // Split into "in use" (Remove) and "available" (Add) so the two affordances
    // are never confused — the operator's reported gripe was Add appearing next
    // to resources already in use.
    var inUse = candidates.filter(function (c) { return asObject(c).allocated === true; });
    var available = candidates.filter(function (c) { return asObject(c).allocated !== true; });
    function subsection(title, list, emptyMsg) {
      return '<p class="v2-resourcesManaged__subhead">' + escapeHtml(title) +
        " (" + escapeHtml(String(list.length)) + ")</p>" +
        (list.length
          ? list.map(renderMember).join("")
          : '<p class="v2-extensionCard__empty">' + escapeHtml(emptyMsg) + "</p>");
    }
    var usedCount = a.used_count || 0;
    var body = candidates.length
      ? subsection("In use — remove to de-allocate", inUse, "Nothing allocated yet.") +
        '<hr class="v2-resourcesManaged__divider" />' +
        subsection("Available — search and add", available, "Everything is allocated.")
      : '<p class="v2-extensionCard__empty">Empty gallery.</p>';
    return (
      '<details class="v2-resourcesManaged" data-gallery="' + escapeHtml(gallery) + '"' +
      (usedCount ? " open" : "") + ">" +
      "<summary>" + escapeHtml(titleCaseLabel(gallery)) + " — " + escapeHtml(String(usedCount)) +
      " used / " + escapeHtml(String(candidates.length)) + " available</summary>" +
      '<div class="v2-resourcesManaged__groups"><div class="v2-resourcesGroup">' +
      body +
      "</div></div></details>"
    );
  }

  function renderResourcesAllocation(p) {
    var site = asText(p.site);
    if (!p.site_exists) {
      return (
        '<div class="v2-resourcesApp" data-resources-mode="allocation">' +
        '<p class="v2-extensionCard__empty">No website found for this grantee (' +
        escapeHtml(asText(p.domain) || "no domain") + ").</p></div>"
      );
    }
    var routes = {
      add: asText(p.manifest_add_route) || "/__fnd/resources/manifest/add",
      remove: asText(p.manifest_remove_route) || "/__fnd/resources/manifest/remove",
    };
    var sections = asList(p.allocations)
      .map(function (a) { return renderResourcesAllocationGallery(asObject(a), routes); })
      .join("");
    return (
      '<div class="v2-resourcesApp" data-resources-mode="allocation" data-site="' +
      escapeHtml(site) + '" data-add-route="' + escapeHtml(routes.add) +
      '" data-remove-route="' + escapeHtml(routes.remove) + '">' +
      '<p class="v2-extensionCard__intro">Allocating shared resources to <strong>' +
      escapeHtml(asText(p.grantee_label) || site) + "</strong> (" + escapeHtml(site) +
      "). Add a leaflet to publish it in this site's manifest; remove to de-allocate. " +
      "For the FND site, allocating a <em>profile</em> adds/removes it on the /more network map.</p>" +
      '<input type="search" class="v2-resourcesSearch" placeholder="Search resources…" aria-label="Search resources" />' +
      sections + "</div>"
    );
  }

  // ---- Type browser: inner subtabs + Manifest / Browse renderers --------
  function renderInnerSubtabs(selector) {
    var s = asObject(selector);
    var tabs = asList(s.tabs);
    if (!tabs.length) return "";
    var opts = tabs
      .map(function (t) {
        var tab = asObject(t);
        var action = JSON.stringify(asObject(tab.select_action).payload || {});
        return (
          '<button type="button" class="v2-innerSubtabs__option' +
          (tab.active === true ? " is-active" : "") +
          '" data-subtab-action="' + escapeHtml(action) +
          '" aria-pressed="' + (tab.active === true ? "true" : "false") + '">' +
          escapeHtml(asText(tab.label) || asText(tab.id)) + "</button>"
        );
      })
      .join("");
    return (
      '<section class="v2-card v2-innerSubtabs" style="margin-top:0">' +
      '<div class="v2-innerSubtabs__options" role="tablist">' + opts + "</div></section>"
    );
  }

  function renderTypeIcon(node, p) {
    var n = asObject(node);
    var prefix = asText(p && p.icon_url_prefix) || "/assets/icons/";
    var iconRef = asText(n.icon_ref);
    if (iconRef) {
      return '<img class="v2-typeIcon" src="' + escapeHtml(prefix + iconRef + ".svg") +
        '" alt="" loading="lazy" onerror="this.style.display=\'none\'" />';
    }
    var sprite = asText(p && p.sprite_href);
    var icon = asText(n.icon);
    if (sprite && icon) {
      return '<svg class="v2-typeIcon" aria-hidden="true"><use href="' +
        escapeHtml(sprite + "#" + icon) + '"></use></svg>';
    }
    return '<span class="v2-typeIcon v2-typeIcon--none"></span>';
  }

  // Horizontal cluster tree (dendrogram) geometry. Pure layout over the flat
  // node list: true leaves (no children) align in the rightmost column (the
  // dendrogram property), internal/collapsed nodes sit at their own depth, and
  // each parent is centered on its visible children (post-order breadth). A
  // collapsed node is a layout-leaf (occupies one row) but keeps its own depth.
  var DENDRO = { COL_W: 230, ROW_H: 30, NODE_W: 170, PAD_X: 14, PAD_Y: 18, TAIL: 300 };

  function clusterLayout(nodes, collapsed) {
    var list = asList(nodes).map(asObject);
    var byParent = {};
    var maxDepth = 0;
    list.forEach(function (n) {
      var parent = asText(n.parent_slug);
      (byParent[parent] = byParent[parent] || []).push(n);
      var d = Number(n.depth || 0);
      if (d > maxDepth) maxDepth = d;
    });
    var placed = [];
    var pos = {};
    var slot = 0;
    function walk(node) {
      var full = asText(node.full_slug);
      var depth = Number(node.depth || 0);
      var hasChildren = !!node.has_children;
      var isCollapsed = hasChildren && collapsed && collapsed.has(full);
      var kids = !isCollapsed && byParent[full] ? byParent[full] : [];
      // Place every node at its OWN depth (tidy-tree), NOT pushed to the deepest
      // leaf column. The type tree is very unbalanced (profile is 5 deep while
      // icon/image/document/audio are depth-1 leaves); equal-depth leaves exiled
      // those shallow types to the far-right column, off-screen in the card.
      var x = depth * DENDRO.COL_W + DENDRO.PAD_X;
      var y;
      if (!kids.length) {
        y = slot * DENDRO.ROW_H + DENDRO.PAD_Y;
        slot += 1;
      } else {
        var ys = kids.map(walk);
        y = (ys[0] + ys[ys.length - 1]) / 2;
      }
      pos[full] = { x: x, y: y };
      placed.push({
        node: node, x: x, y: y, hasChildren: hasChildren,
        collapsed: isCollapsed, isLeaf: !hasChildren,
      });
      return y;
    }
    (byParent[""] || []).forEach(walk);
    var links = [];
    placed.forEach(function (pl) {
      var parent = asText(pl.node.parent_slug);
      if (parent && pos[parent]) {
        links.push({ sx: pos[parent].x + DENDRO.NODE_W, sy: pos[parent].y, tx: pl.x, ty: pl.y });
      }
    });
    return {
      placed: placed,
      links: links,
      width: maxDepth * DENDRO.COL_W + DENDRO.TAIL,
      height: slot * DENDRO.ROW_H + DENDRO.PAD_Y + 12,
    };
  }

  // Hybrid render: SVG <path>s draw the links; absolutely-positioned HTML draws
  // the nodes (so renderTypeIcon + real buttons + CSS ellipsis are reused). Each
  // node carries an expand/collapse toggle and a [data-open-type] "view" button.
  // Shared dendrogram scaffold so the Resource type tree (renderDendrogram) and
  // the SAMRAS structure tree (_samrasDendroBody) keep identical link geometry,
  // SVG viewBox, and Expand/Collapse-all toolbar — only the per-node body differs.
  function _dendroLinks(lay) {
    var paths = lay.links.map(function (l) {
      var mx = (l.sx + l.tx) / 2;
      return '<path class="v2-dendro__link" d="M' + l.sx + "," + l.sy +
        "C" + mx + "," + l.sy + " " + mx + "," + l.ty + " " + l.tx + "," + l.ty + '" />';
    }).join("");
    return '<svg class="v2-dendro__links" width="' + lay.width + '" height="' + lay.height +
      '" viewBox="0 0 ' + lay.width + " " + lay.height + '" aria-hidden="true">' + paths + "</svg>";
  }
  function _dendroWrap(lay, svg, nodeHtml) {
    return (
      '<div class="v2-dendro__toolbar">' +
      '<button type="button" class="v2-dendro__all" data-dendro-all="expand">Expand all</button>' +
      '<button type="button" class="v2-dendro__all" data-dendro-all="collapse">Collapse all</button>' +
      "</div>" +
      '<div class="v2-dendro" style="width:' + lay.width + "px;height:" + lay.height + 'px">' +
      svg + nodeHtml + "</div>"
    );
  }

  function renderDendrogram(nodes, p, collapsed) {
    var lay = clusterLayout(nodes, collapsed);
    var svg = _dendroLinks(lay);
    var nodeHtml = lay.placed.map(function (pl) {
      var n = pl.node;
      var full = asText(n.full_slug);
      var toggle = pl.hasChildren
        ? '<button type="button" class="v2-dendro__toggle" data-dendro-toggle="' + escapeHtml(full) +
          '" aria-label="' + (pl.collapsed ? "Expand" : "Collapse") + ' structure" title="' +
          (pl.collapsed ? "Expand" : "Collapse") + ' structure">' + (pl.collapsed ? "▸" : "▾") + "</button>"
        : '<span class="v2-dendro__toggle v2-dendro__toggle--leaf" aria-hidden="true"></span>';
      var view =
        '<button type="button" class="v2-dendro__view" data-open-type="' + escapeHtml(full) +
        '" title="View instances of this type">' + renderTypeIcon(n, p) +
        '<span class="v2-dendro__label">' + escapeHtml(asText(n.label) || full) + "</span>" +
        '<span class="v2-dendro__count">' + escapeHtml(String(n.count || 0)) + "</span></button>";
      // The dendrogram IS the manifest: every node can reassign its own icon
      // (the old Manifest tab's only unique capability, folded in per-node).
      var edit =
        '<button type="button" class="v2-dendro__editIcon" data-edit-icon="' + escapeHtml(full) +
        '" title="Change this type’s icon" aria-label="Change icon">✎</button>';
      return '<div class="v2-dendro__node' + (pl.isLeaf ? " is-leaf" : "") + '" style="left:' + pl.x +
        "px;top:" + pl.y + 'px">' + toggle + view + edit + "</div>";
    }).join("");
    return _dendroWrap(lay, svg, nodeHtml);
  }

  // ── SAMRAS structure dendrogram (txa / msn / lcl id-space) ────────────────
  // The SAMRAS id-space rendered with the SAME cluster diagram as the Resource type
  // browser — reuses clusterLayout + DENDRO + the .v2-dendro markup/links — but the
  // nodes are browse-only (address + label + status glyph + child-count pill; no edit)
  // and a structure <select> reloads the shell. Lives in IIFE#1 so clusterLayout is in scope.
  function _samrasDendroBody(nodes, collapsed) {
    var lay = clusterLayout(nodes, collapsed);
    var svg = _dendroLinks(lay);
    var nodeHtml = lay.placed.map(function (pl) {
      var n = pl.node;
      var full = asText(n.full_slug);
      var isEmpty = asText(n.status) === "empty";
      var toggle = pl.hasChildren
        ? '<button type="button" class="v2-dendro__toggle" data-dendro-toggle="' + escapeHtml(full) +
          '" aria-label="' + (pl.collapsed ? "Expand" : "Collapse") + '" title="' +
          (pl.collapsed ? "Expand" : "Collapse") + '">' + (pl.collapsed ? "▸" : "▾") + "</button>"
        : '<span class="v2-dendro__toggle v2-dendro__toggle--leaf" aria-hidden="true"></span>';
      // Status glyph stands in for the Resource browser's per-type icon (SAMRAS nodes
      // carry no icon_ref): ● filled = DEFINED, ○ ring = EMPTY (denoted-but-undefined).
      var status = '<span class="v2-dendro__status v2-dendro__status--' +
        (isEmpty ? "empty" : "defined") + '" aria-hidden="true"></span>';
      var label = isEmpty
        ? '<span class="v2-dendro__empty">(undefined)</span>'
        : '<span class="v2-dendro__label">' + escapeHtml(asText(n.label) || full) + "</span>";
      // Direct child-count pill — the SAMRAS analog of the type-instance count badge.
      // Hidden on leaves (count 0) so the structure tree isn't littered with "0" badges.
      var count = n.count > 0
        ? '<span class="v2-dendro__count">' + escapeHtml(String(n.count)) + "</span>"
        : "";
      var title = isEmpty
        ? "Denoted by the magnitude but undefined in the title document"
        : asText(n.label) || full;
      var body = '<span class="v2-dendro__view v2-dendro__view--static' +
        (isEmpty ? " is-empty" : " is-defined") + '" title="' + escapeHtml(title) + '">' +
        status + '<span class="v2-dendro__addr">' + escapeHtml(full) + "</span>" +
        label + count + "</span>";
      return '<div class="v2-dendro__node' + (pl.isLeaf ? " is-leaf" : "") + '" style="left:' + pl.x +
        "px;top:" + pl.y + 'px">' + toggle + body + "</div>";
    }).join("");
    return _dendroWrap(lay, svg, nodeHtml);
  }

  function _samrasCollapsedInit(nodes) {
    // Collapse every branch by default (a 4670-node tree must not paint at once), then
    // expand the root(s) so the top categories are visible on open.
    var collapsed = new Set();
    asList(nodes).forEach(function (n) {
      var o = asObject(n);
      if (o.has_children) collapsed.add(asText(o.full_slug));
    });
    asList(nodes).forEach(function (n) {
      var o = asObject(n);
      if (o.has_children && !asText(o.parent_slug)) collapsed.delete(asText(o.full_slug));
    });
    return collapsed;
  }

  function renderSamrasDendrogram(payload, content) {
    payload = asObject(payload);
    if (asText(payload.error)) {
      content.innerHTML = '<p class="ide-visualizationPanel__error">' +
        escapeHtml(asText(payload.error)) + "</p>";
      return;
    }
    var nodes = asList(payload.nodes);
    var structures = asList(payload.structures);
    var selected = asText(payload.structure || payload.magnitude);
    var options = structures.map(function (s) {
      s = asObject(s);
      var name = asText(s.name);
      var sel = name === selected ? " selected" : "";
      var hint = s.has_titles ? "" : " (no titles)";
      return '<option value="' + escapeHtml(name) + '"' + sel + ">" + escapeHtml(name + hint) + "</option>";
    }).join("");
    var selector = structures.length
      ? '<div class="v2-samras__bar"><label class="v2-samras__label">Structure ' +
        '<select class="v2-samras__select" data-samras-select>' + options + "</select></label>" +
        (payload.has_titles ? "" : '<span class="v2-samras__note">no title document — addresses only</span>') +
        "</div>"
      : "";
    content.innerHTML =
      '<section class="v2-clusterTree">' +
      selector +
      '<header class="v2-clusterTree__header">' +
      escapeHtml(selected || "structure") + " · " +
      escapeHtml(String(payload.denoted_count || 0)) + " denoted · " +
      escapeHtml(String(payload.defined_count || 0)) + " defined · " +
      escapeHtml(String(payload.empty_count || 0)) + " empty</header>" +
      '<div class="v2-dendro__host" data-samras-host></div></section>';
    var selectEl = content.querySelector("[data-samras-select]");
    if (selectEl) selectEl.addEventListener("change", function () {
      if (window.PortalShellCore && typeof window.PortalShellCore.setSurfaceQuery === "function") {
        window.PortalShellCore.setSurfaceQuery("samras_structure", selectEl.value);
      }
    });
    var host = content.querySelector("[data-samras-host]");
    if (!host) return;
    if (!nodes.length) {
      host.innerHTML = '<p class="v2-clusterTree__empty">No nodes denoted by the magnitude.</p>';
      return;
    }
    var collapsed = _samrasCollapsedInit(nodes);
    function rerender() { host.innerHTML = _samrasDendroBody(nodes, collapsed); }
    rerender();
    host.addEventListener("click", function (e) {
      var el = e.target;
      if (!el || !el.closest) return;
      var tog = el.closest("[data-dendro-toggle]");
      if (tog && host.contains(tog)) {
        e.preventDefault();
        var slug = tog.getAttribute("data-dendro-toggle");
        if (collapsed.has(slug)) collapsed.delete(slug); else collapsed.add(slug);
        rerender();
        return;
      }
      var all = el.closest("[data-dendro-all]");
      if (all && host.contains(all)) {
        e.preventDefault();
        collapsed.clear();
        if (all.getAttribute("data-dendro-all") === "collapse") {
          asList(nodes).forEach(function (n) {
            var o = asObject(n);
            if (o.has_children) collapsed.add(asText(o.full_slug));
          });
        }
        rerender();
      }
    });
  }

  window.__MYCITE_V2_TOOL_RENDERERS = window.__MYCITE_V2_TOOL_RENDERERS || {};
  window.__MYCITE_V2_TOOL_RENDERERS["samras_structure"] = renderSamrasDendrogram;

  // ── Local Domain dendrogram (lcl id-space + expand-to-table nodes) ─────────
  // Same cluster diagram as the SAMRAS viewer, but a node carrying a record_view token
  // renders a diagonal "expand view" button (⤢) INSTEAD of the child-dropdown: clicking it
  // sets the local_view overlay param, which the agronomics tool turns into a full-tab
  // record table (tools/agronomics_viewer.py). Expandable nodes are force-collapsed so their
  // (instance) children never paint in the tree — they live in the table instead.
  function _localDomainBody(nodes, collapsed) {
    var lay = clusterLayout(nodes, collapsed);
    var svg = _dendroLinks(lay);
    var nodeHtml = lay.placed.map(function (pl) {
      var n = pl.node;
      var full = asText(n.full_slug);
      var rv = asText(n.record_view);
      var isEmpty = asText(n.status) === "empty";
      var toggle;
      if (rv) {
        toggle = '<button type="button" class="v2-dendro__expand" data-local-expand="' +
          escapeHtml(rv) + '" data-local-node="' + escapeHtml(full) + '" title="Open ' +
          escapeHtml(asText(n.label) || full) + ' records" aria-label="Open records">⤢</button>';
      } else if (pl.hasChildren) {
        toggle = '<button type="button" class="v2-dendro__toggle" data-dendro-toggle="' + escapeHtml(full) +
          '" aria-label="' + (pl.collapsed ? "Expand" : "Collapse") + '" title="' +
          (pl.collapsed ? "Expand" : "Collapse") + '">' + (pl.collapsed ? "▸" : "▾") + "</button>";
      } else {
        toggle = '<span class="v2-dendro__toggle v2-dendro__toggle--leaf" aria-hidden="true"></span>';
      }
      var status = '<span class="v2-dendro__status v2-dendro__status--' +
        (isEmpty ? "empty" : "defined") + '" aria-hidden="true"></span>';
      var label = isEmpty
        ? '<span class="v2-dendro__empty">(undefined)</span>'
        : '<span class="v2-dendro__label">' + escapeHtml(asText(n.label) || full) + "</span>";
      var count = (n.count > 0 && !rv)
        ? '<span class="v2-dendro__count">' + escapeHtml(String(n.count)) + "</span>"
        : "";
      var title = isEmpty ? "Denoted by the magnitude but undefined in the title document"
        : (rv ? "Expand " + (asText(n.label) || full) + " into a record table" : (asText(n.label) || full));
      var body = '<span class="v2-dendro__view v2-dendro__view--static' +
        (isEmpty ? " is-empty" : " is-defined") + (rv ? " is-expandable" : "") +
        '" title="' + escapeHtml(title) + '">' +
        status + '<span class="v2-dendro__addr">' + escapeHtml(full) + "</span>" +
        label + count + "</span>";
      return '<div class="v2-dendro__node' + (pl.isLeaf ? " is-leaf" : "") + '" style="left:' + pl.x +
        "px;top:" + pl.y + 'px">' + toggle + body + "</div>";
    }).join("");
    return _dendroWrap(lay, svg, nodeHtml);
  }

  function renderLocalDomain(payload, content) {
    payload = asObject(payload);
    if (asText(payload.error)) {
      content.innerHTML = '<p class="ide-visualizationPanel__error">' +
        escapeHtml(asText(payload.error)) + "</p>";
      return;
    }
    var nodes = asList(payload.nodes);
    // Structure switcher (txa / msn / lcl) — same selector the SAMRAS viewer offers, so the
    // Agronomics FARM pane keeps the ability to switch the structure (not locked to lcl).
    var structures = asList(payload.structures);
    var selectedStruct = asText(payload.structure || payload.magnitude || "lcl");
    var options = structures.map(function (s) {
      s = asObject(s);
      var name = asText(s.name);
      return '<option value="' + escapeHtml(name) + '"' + (name === selectedStruct ? " selected" : "") +
        ">" + escapeHtml(name + (s.has_titles ? "" : " (no titles)")) + "</option>";
    }).join("");
    var selector = structures.length
      ? '<div class="v2-samras__bar"><label class="v2-samras__label">Structure ' +
        '<select class="v2-samras__select" data-samras-select>' + options + "</select></label></div>"
      : "";
    content.innerHTML =
      '<section class="v2-clusterTree">' +
      selector +
      '<header class="v2-clusterTree__header">' +
      escapeHtml(selectedStruct) + " · " +
      escapeHtml(String(payload.denoted_count || 0)) + " denoted · " +
      escapeHtml(String(payload.defined_count || 0)) + " defined · " +
      "<span class=\"v2-clusterTree__hint\">⤢ = expand to records</span></header>" +
      '<div class="v2-dendro__host" data-local-host></div></section>';
    var structSel = content.querySelector("[data-samras-select]");
    if (structSel) structSel.addEventListener("change", function () {
      if (window.PortalShellCore && typeof window.PortalShellCore.setSurfaceQuery === "function") {
        window.PortalShellCore.setSurfaceQuery("samras_structure", structSel.value);
      }
    });
    var host = content.querySelector("[data-local-host]");
    if (!host) return;
    if (!nodes.length) {
      host.innerHTML = '<p class="v2-clusterTree__empty">No nodes denoted by the magnitude.</p>';
      return;
    }
    // Collapse every branch by default; expand the root(s). Then default to 3 visible layers
    // by also expanding the domain nodes (children of the root) — root → domains → domain
    // children all show on open.
    var collapsed = _samrasCollapsedInit(nodes);
    var rootSlugs = {};
    asList(nodes).forEach(function (n) {
      var o = asObject(n);
      if (!asText(o.parent_slug)) rootSlugs[asText(o.full_slug)] = true;
    });
    asList(nodes).forEach(function (n) {
      var o = asObject(n);
      if (o.has_children && rootSlugs[asText(o.parent_slug)]) collapsed.delete(asText(o.full_slug));
    });
    // ALWAYS keep expandable (record_view) nodes collapsed so their instance children never
    // paint in the tree (they live in the expand-to-table view instead).
    asList(nodes).forEach(function (n) {
      var o = asObject(n);
      if (asText(o.record_view)) collapsed.add(asText(o.full_slug));
    });
    function rerender() { host.innerHTML = _localDomainBody(nodes, collapsed); }
    rerender();
    host.addEventListener("click", function (e) {
      var el = e.target;
      if (!el || !el.closest) return;
      var exp = el.closest("[data-local-expand]");
      if (exp && host.contains(exp)) {
        e.preventDefault();
        if (window.PortalShellCore && typeof window.PortalShellCore.setSurfaceQuery === "function") {
          window.PortalShellCore.setSurfaceQuery("local_view", exp.getAttribute("data-local-expand"));
        }
        return;
      }
      var tog = el.closest("[data-dendro-toggle]");
      if (tog && host.contains(tog)) {
        e.preventDefault();
        var slug = tog.getAttribute("data-dendro-toggle");
        if (collapsed.has(slug)) collapsed.delete(slug); else collapsed.add(slug);
        rerender();
      }
    });
  }

  window.__MYCITE_V2_TOOL_RENDERERS["local_domain"] = renderLocalDomain;

  function renderGenericLeaflet(detail) {
    var d = asObject(detail);
    var fields = asList(d.fields).map(function (f) {
      var fld = asObject(f);
      return '<div class="v2-resourcesField"><label>' + escapeHtml(asText(fld.label) || asText(fld.key)) +
        "</label><div>" + escapeHtml(asText(fld.value) || "—") + "</div></div>";
    }).join("");
    var raw = asText(d.raw_yaml);
    return "<h4>" + escapeHtml(asText(d.label) || asText(d.filename)) + "</h4>" +
      '<div class="v2-genericLeaflet__fields">' + fields + "</div>" +
      (raw ? '<details class="v2-genericLeaflet__rawWrap"><summary>Raw YAML</summary>' +
        '<pre class="v2-genericLeaflet__raw">' + escapeHtml(raw) + "</pre></details>" : "");
  }

  // Content-field representation: render a leaflet's contact + social VALUES as
  // icon-bearing links (field/value → icon convention; server resolves the icon).
  function renderFieldLinks(links) {
    var list = asList(links);
    if (!list.length) return "";
    var rows = list.map(function (l) {
      var o = asObject(l);
      var icon = asText(o.icon_url)
        ? '<img class="v2-fieldLink__icon" src="' + escapeHtml(asText(o.icon_url)) +
          '" alt="" loading="lazy" onerror="this.style.display=\'none\'" />'
        : '<span class="v2-fieldLink__icon v2-fieldLink__icon--none" aria-hidden="true"></span>';
      var val = escapeHtml(asText(o.value));
      var href = asText(o.href);
      var inner = href
        ? '<a class="v2-fieldLink__val" href="' + escapeHtml(href) +
          '" target="_blank" rel="noopener noreferrer">' + val + "</a>"
        : '<span class="v2-fieldLink__val">' + val + "</span>";
      return '<div class="v2-fieldLink" title="' + escapeHtml(asText(o.label)) + '">' + icon + inner + "</div>";
    }).join("");
    return '<div class="v2-fieldLinks">' + rows + "</div>";
  }

  // Grantee-scoped extra fields: one block per scope (e.g. CVCC), each with its
  // icon-bearing contact/social links + the remaining scalar fields.
  function renderProfileScopes(scopes) {
    var list = asList(scopes);
    if (!list.length) return "";
    return list.map(function (sc) {
      var o = asObject(sc);
      var fields = asList(o.fields).map(function (f) {
        var fld = asObject(f);
        return '<div class="v2-resourcesField"><label>' + escapeHtml(asText(fld.label) || asText(fld.key)) +
          "</label><div>" + escapeHtml(asText(fld.value) || "—") + "</div></div>";
      }).join("");
      return '<section class="v2-scopeBlock"><h5 class="v2-scopeBlock__head">' +
        escapeHtml(asText(o.label) || asText(o.scope)) + "</h5>" +
        renderFieldLinks(o.links) +
        '<div class="v2-resourcesDetail__meta">' + fields + "</div></section>";
    }).join("");
  }

  // Shared scalar field-row renderer (DRY: header band, typed sections, scopes).
  function renderFieldRows(fields) {
    return asList(fields).map(function (f) {
      var fld = asObject(f);
      return '<div class="v2-resourcesField"><label>' + escapeHtml(asText(fld.label) || asText(fld.key)) +
        "</label><div>" + escapeHtml(asText(fld.value) || "—") + "</div></div>";
    }).join("");
  }

  // Header band: profile name + base fields (left) beside an enlarged logo/headshot.
  function renderProfileHeader(d) {
    var dd = asObject(d);
    var img = asText(dd.image_url)
      ? '<img class="v2-resourcesThumb v2-resourcesThumb--xl" src="' + escapeHtml(asText(dd.image_url)) +
        '" alt="" onerror="this.style.display=\'none\'" />'
      : "";
    var base = renderFieldRows(dd.base_fields);
    return '<div class="v2-resourcesDetail__head v2-resourcesDetail__head--band">' +
      '<div class="v2-resourcesDetail__headText"><h4>' +
      escapeHtml(asText(dd.display_name) || asText(dd.slug)) + "</h4>" +
      (base ? '<div class="v2-resourcesDetail__meta v2-resourcesDetail__meta--inline">' + base + "</div>" : "") +
      "</div>" + img + "</div>";
  }

  function renderBrowseInstance(p) {
    var inst = asObject(p.instance);
    var viewer = asText(inst.viewer);
    var d = asObject(inst.detail);
    var body;
    if (viewer === "profile") {
      var pslug = asText(d.slug);
      // Layered/typed layout: base header band, contact links, then one section
      // block per typed group (legal / ag / admin / additional), server-ordered.
      body = renderProfileHeader(d) +
        renderFieldLinks(d.contact_links) +
        asList(d.sections).map(function (s) {
          var o = asObject(s);
          var head = escapeHtml(asText(o.label));
          if (asText(o.id) === "ag" && asText(d.ag_role)) {
            head += " · " + escapeHtml(asText(d.ag_role)) +
              (asText(d.ag_subtype) ? " / " + escapeHtml(asText(d.ag_subtype)) : "");
          }
          return '<section class="v2-typedBlock"><h5 class="v2-typedBlock__head">' + head + "</h5>" +
            '<div class="v2-resourcesDetail__meta">' + renderFieldRows(o.fields) + "</div></section>";
        }).join("") +
        // Grantee-scoped extra fields (scope_fields): one block per grantee scope,
        // shown here + on the grantee's own site, kept out of the general FND views.
        renderProfileScopes(d.scopes) +
        // Edit reuses the library's profile detail/save endpoints (fetched lazily
        // on click): the read-only view stays the default, "Edit profile" swaps in
        // the same component-library form + save→propagate the library uses.
        (pslug
          ? '<div class="v2-browseEdit"><button type="button" class="v2-browseEdit__btn" data-edit-profile="' +
            escapeHtml(pslug) + '">Edit profile</button><div class="v2-browseEdit__pane"></div></div>'
          : "");
    } else if (viewer === "asset") {
      body = renderBinaryDetail(d);
    } else {
      body = renderGenericLeaflet(d);
    }
    return '<div class="v2-leafletDir__bar"><button type="button" class="v2-leafletDir__back" ' +
      'data-browse-back="directory">&larr; ' + escapeHtml(asText(p.type_label) || "Directory") + "</button></div>" +
      '<div class="v2-genericLeaflet">' + body + "</div>";
  }

  function leafletBytes(n) {
    n = Number(n || 0);
    if (!n) return "";
    if (n < 1024) return n + " B";
    if (n < 1048576) return Math.round(n / 1024) + " KB";
    return (n / 1048576).toFixed(1) + " MB";
  }

  function leafletMeta(r) {
    // A compact info-preview line for an instance (the operator's "preview of
    // information or a small thumbnail" — non-image rows get this text preview).
    var bits = [];
    if (asText(r.subtype_tail)) bits.push(asText(r.subtype_tail));
    if (asText(r.owner)) bits.push(asText(r.owner));
    if (asText(r.gallery)) bits.push(asText(r.gallery));
    var sz = leafletBytes(r.size_bytes);
    if (sz) bits.push(sz);
    else if (asText(r.ext)) bits.push(asText(r.ext));
    return bits.join(" · ");
  }

  function renderBrowseDirectory(p) {
    var leaflets = asList(p.leaflets);
    var subtypes = asList(p.subtypes);
    var chips = subtypes.length
      ? '<div class="v2-browseFilters"><button type="button" class="v2-browseFilter is-active" ' +
        'data-subtype-filter="">All</button>' +
        subtypes.map(function (s) {
          var n = asObject(s);
          return '<button type="button" class="v2-browseFilter" data-subtype-filter="' +
            escapeHtml(asText(n.full_slug)) + '">' + escapeHtml(asText(n.label)) + "</button>";
        }).join("") + "</div>"
      : "";
    var search =
      '<input type="search" class="v2-leafletDir__search" aria-label="Search instances" placeholder="Search ' +
      escapeHtml(String(leaflets.length)) + " instance" + (leaflets.length === 1 ? "" : "s") + '…" />';
    var rows = leaflets.map(function (l) {
      var r = asObject(l);
      var name = asText(r.display_name) || asText(r.slug) || asText(r.filename);
      var thumb = asText(r.image_url)
        ? '<img class="v2-resourcesThumb v2-resourcesThumb--sm" src="' + escapeHtml(asText(r.image_url)) +
          '" alt="" loading="lazy" onerror="this.style.display=\'none\'" />'
        : '<span class="v2-resourcesThumb v2-resourcesThumb--sm v2-resourcesThumb--dot" aria-hidden="true"></span>';
      var meta = leafletMeta(r);
      var hay = (name + " " + asText(r.filename) + " " + asText(r.full_type) + " " + asText(r.owner)).toLowerCase();
      return '<button type="button" class="v2-leafletDir__item" data-open-instance="' +
        escapeHtml(asText(r.asset_path)) + '" data-full-type="' + escapeHtml(asText(r.full_type)) +
        '" data-search="' + escapeHtml(hay) + '">' + thumb +
        '<span class="v2-leafletDir__text"><span class="v2-leafletDir__name">' + escapeHtml(name) + "</span>" +
        (meta ? '<span class="v2-leafletDir__meta">' + escapeHtml(meta) + "</span>" : "") +
        // The leaflet's display NAME is the card title (the subtype/owner ride the meta
        // line). The full TYPE token is redundant here — you're already inside that
        // type's directory — and as a non-shrinking <code> it overflowed the grid card
        // and squeezed the name to nothing. Drop it so the card shows only the name.
        "</span></button>";
    }).join("");
    return '<div class="v2-leafletDir__bar"><button type="button" class="v2-leafletDir__back" ' +
      'data-browse-back="hierarchy">&larr; Types</button><h4>' +
      escapeHtml(asText(p.type_label) || asText(p.browse_type)) + '</h4>' +
      '<span class="v2-leafletDir__count">' + escapeHtml(String(leaflets.length)) + "</span></div>" +
      search + chips + '<div class="v2-leafletDir__list">' +
      (rows || '<p class="v2-extensionCard__empty">No leaflets of this type.</p>') +
      '</div><p class="v2-leafletDir__empty" hidden>No instances match your search.</p>';
  }

  function renderResourcesBrowse(p) {
    var view = asText(p.browse_view) || "hierarchy";
    var inner;
    if (view === "instance") {
      inner = renderBrowseInstance(p);
    } else if (view === "directory") {
      inner = renderBrowseDirectory(p);
    } else {
      // Cluster-tree (dendrogram) = the UNIFIED type tab (registry + browser): the
      // node data is stashed on the host so the binder can recompute the layout on
      // expand/collapse with NO shell reload.
      var other = Number(asObject(p).other_count || 0);
      inner =
        '<p class="v2-extensionCard__intro">The leaflet TYPE registry and browser in one: ' +
        "▸/▾ expands a type’s structure, ✎ changes its icon, and clicking a type lists every " +
        "leaflet under it (and its subtypes).</p>" +
        '<div class="v2-dendro__host" data-dendro-host data-dendro-nodes="' +
        escapeHtml(JSON.stringify(asList(p.nodes))) + '">' +
        renderDendrogram(p.nodes, p, new Set()) + "</div>" +
        (other
          ? '<p class="v2-dendro__other">+ ' + escapeHtml(String(other)) +
            " leaflet(s) of unregistered types (no icon to assign)</p>"
          : "");
    }
    return '<div class="v2-resourcesApp v2-typeBrowse" data-nav-base="' +
      escapeHtml(JSON.stringify(asObject(p.nav_base_query))) + '" data-dir-type="' +
      escapeHtml(asText(p.browse_type)) + '" data-sprite-href="' +
      escapeHtml(asText(p.sprite_href)) + '" data-icon-prefix="' +
      escapeHtml(asText(p.icon_url_prefix)) + '" data-set-icon-route="' +
      escapeHtml(asText(p.set_icon_ref_route)) + '" data-icon-options-route="' +
      escapeHtml(asText(p.icon_options_route)) + '" data-profile-detail-route="' +
      escapeHtml(asText(p.profile_detail_route)) + '" data-profile-save-route="' +
      escapeHtml(asText(p.profile_save_route)) + '"><div class="v2-leafletDir">' + inner + "</div></div>";
  }

  function renderResourcesApp(payload) {
    var p = asObject(payload);
    // The inner subtab strip is now rendered at the card level (renderExtensions)
    // uniformly for every extension, so it is NOT prepended here.
    var sub = asText(p.resources_subtab);
    var body;
    // "browse" is the unified type tab; "manifest" is legacy (any stale client
    // state) → same renderer.
    if (sub === "browse" || sub === "manifest") {
      body = renderResourcesBrowse(p);
    } else if (sub === "per_grantee") {
      body = asText(p.per_grantee_prompt)
        ? '<div class="v2-resourcesApp"><p class="v2-extensionCard__empty">' +
          escapeHtml(asText(p.per_grantee_prompt)) + "</p></div>"
        : renderResourcesAllocation(p);
    } else if (asText(p.resources_mode) === "allocation") {
      body = renderResourcesAllocation(p);
    } else {
      body = renderResourcesLibrary(p);
    }
    return body;
  }

  function renderExtensions(extensions) {
    var list = asList(extensions);
    if (!list.length) return "";
    return (
      '<div class="v2-extensions">' +
      list
        .map(function (entry) {
          var e = asObject(entry);
          // Inner subtab strip (Overall / Per-grantee, or Manifest/Browse/...) is
          // rendered at the card level uniformly for EVERY extension that declares
          // subtabs server-side.
          var subtabs = renderInnerSubtabs(asObject(e.payload).inner_subtab_selector);
          var body = renderExtensionCardBody(e.payload);
          return (
            '<article class="v2-card v2-extensionCard" data-tool-id="' +
            escapeHtml(asText(e.tool_id)) +
            '">' +
            "<h3>" +
            escapeHtml(asText(e.label) || asText(e.tool_id)) +
            "</h3>" +
            (e.summary
              ? '<p class="v2-extensionCard__intro">' + escapeHtml(asText(e.summary)) + "</p>"
              : "") +
            subtabs +
            body +
            "</article>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function collectFormFieldValues(form) {
    var values = {};
    Array.prototype.forEach.call(
      form.querySelectorAll("[data-form-field-key]"),
      function (node) {
        var key = node.getAttribute("data-form-field-key");
        var type = node.getAttribute("data-form-field-type");
        if (type === "boolean") {
          values[key] = !!node.checked;
        } else if (type === "string_list") {
          try {
            values[key] = JSON.parse(node.getAttribute("data-form-field-values") || "[]");
          } catch (_) {
            values[key] = [];
          }
        } else {
          values[key] = node.value || "";
        }
      }
    );
    return values;
  }

  function showFormResultBanner(form, ok, message) {
    var existing = form.querySelector(".v2-form__banner");
    if (existing) existing.parentNode.removeChild(existing);
    var banner = document.createElement("div");
    banner.className = "v2-form__banner v2-form__banner--" + (ok ? "ok" : "error");
    banner.textContent = message;
    form.appendChild(banner);
  }

  function bindFormSubmit(ctx, form) {
    if (!form || form.dataset.formBound === "1") return;
    form.dataset.formBound = "1";
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var route = form.getAttribute("data-form-submit-route");
      var schema = form.getAttribute("data-form-submit-schema");
      var basePayload = {};
      try {
        basePayload = JSON.parse(form.getAttribute("data-form-base-payload") || "{}");
      } catch (_) {}
      var fields = collectFormFieldValues(form);
      var body = Object.assign({}, basePayload, { schema: schema, fields: fields });
      var submitBtn = form.querySelector(".v2-form__submit");
      if (submitBtn) submitBtn.disabled = true;
      fetch(route, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        credentials: "same-origin",
      })
        .then(function (r) {
          return r.json().then(function (j) {
            return { status: r.status, body: j };
          });
        })
        .then(function (out) {
          if (submitBtn) submitBtn.disabled = false;
          var ok = out.status >= 200 && out.status < 300 && out.body && out.body.ok !== false;
          var msg = ok
            ? "Saved."
            : "Save failed: " +
              (out.body && (out.body.detail || out.body.error || ("HTTP " + out.status)) || "unknown");
          showFormResultBanner(form, ok, msg);
          if (ok && typeof ctx.loadShell === "function") {
            // Refresh the surface so the saved values surface in the next render.
            var envelope = ctx.getEnvelope && ctx.getEnvelope();
            if (envelope) {
              ctx.loadShell({
                schema: "mycite.v2.portal.shell.request.v1",
                requested_surface_id: envelope.surface_id,
                surface_query: envelope.surface_query || {},
              });
            }
          }
        })
        .catch(function (err) {
          if (submitBtn) submitBtn.disabled = false;
          showFormResultBanner(form, false, "Network error: " + (err && err.message ? err.message : err));
        });
    });
  }

  function bindRowAction(ctx, button) {
    if (!button || button.dataset.rowActionBound === "1") return;
    button.dataset.rowActionBound = "1";
    button.addEventListener("click", function () {
      var route = button.getAttribute("data-row-action-route");
      var schema = button.getAttribute("data-row-action-schema") || "";
      var confirmMsg = button.getAttribute("data-row-action-confirm") || "";
      if (!route) return;
      if (confirmMsg && typeof window.confirm === "function" && !window.confirm(confirmMsg)) {
        return;
      }
      var basePayload = {};
      try {
        basePayload = JSON.parse(button.getAttribute("data-row-action-payload") || "{}");
      } catch (_) {}
      button.disabled = true;
      var body = Object.assign({ schema: schema }, basePayload);
      fetch(route, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        credentials: "same-origin",
      })
        .then(function (r) {
          return r.json().then(function (j) {
            return { status: r.status, body: j };
          });
        })
        .then(function (out) {
          button.disabled = false;
          var ok = out.status >= 200 && out.status < 300 && out.body && out.body.ok !== false;
          if (ok && typeof ctx.loadShell === "function") {
            var envelope = ctx.getEnvelope && ctx.getEnvelope();
            if (envelope) {
              ctx.loadShell({
                schema: "mycite.v2.portal.shell.request.v1",
                requested_surface_id: envelope.surface_id,
                surface_query: envelope.surface_query || {},
              });
            }
          } else if (!ok) {
            var msg =
              (out.body && (out.body.detail || out.body.error || ("HTTP " + out.status))) ||
              "unknown error";
            try {
              window.alert("Action failed: " + msg);
            } catch (_) {}
          }
        })
        .catch(function (err) {
          button.disabled = false;
          try {
            window.alert("Network error: " + (err && err.message ? err.message : err));
          } catch (_) {}
        });
    });
  }

  function bindContactEditActions(ctx, target) {
    // Phase 16a: per-row inline edit. The toggle button shows/hides
    // the hidden edit row; the form submits to /__fnd/newsletter/
    // admin/edit and refreshes the shell on success.
    if (!target) return;
    Array.prototype.forEach.call(
      target.querySelectorAll("[data-contact-edit-toggle]"),
      function (btn) {
        if (btn.dataset.contactEditBound === "1") return;
        btn.dataset.contactEditBound = "1";
        var index = btn.getAttribute("data-contact-edit-toggle");
        btn.addEventListener("click", function () {
          var row = target.querySelector(
            '[data-contact-edit-index="' + index + '"]'
          );
          if (!row) return;
          row.hidden = !row.hidden;
        });
      }
    );
    Array.prototype.forEach.call(
      target.querySelectorAll("[data-contact-edit-cancel]"),
      function (btn) {
        if (btn.dataset.contactCancelBound === "1") return;
        btn.dataset.contactCancelBound = "1";
        btn.addEventListener("click", function () {
          var editRow = btn.closest(".v2-contactEditRow");
          if (editRow) editRow.hidden = true;
        });
      }
    );
    Array.prototype.forEach.call(
      target.querySelectorAll("form.v2-contactEditForm"),
      function (form) {
        if (form.dataset.contactEditFormBound === "1") return;
        form.dataset.contactEditFormBound = "1";
        form.addEventListener("submit", function (event) {
          event.preventDefault();
          var route = form.getAttribute("data-contact-edit-route");
          var schema = form.getAttribute("data-contact-edit-schema") || "";
          var basePayload = {};
          try {
            basePayload = JSON.parse(form.getAttribute("data-contact-edit-payload") || "{}");
          } catch (_) {}
          var fields = asObject(basePayload).fields || {};
          Array.prototype.forEach.call(
            form.querySelectorAll("[data-contact-edit-key]"),
            function (input) {
              fields[input.getAttribute("data-contact-edit-key")] = input.value || "";
            }
          );
          var body = Object.assign({}, basePayload, { schema: schema, fields: fields });
          var saveBtn = form.querySelector('button[type="submit"]');
          if (saveBtn) saveBtn.disabled = true;
          fetch(route, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
            credentials: "same-origin",
          })
            .then(function (r) {
              return r.json().then(function (j) {
                return { status: r.status, body: j };
              });
            })
            .then(function (out) {
              if (saveBtn) saveBtn.disabled = false;
              var ok = out.status >= 200 && out.status < 300 && out.body && out.body.ok !== false;
              if (ok && typeof ctx.loadShell === "function") {
                var envelope = ctx.getEnvelope && ctx.getEnvelope();
                if (envelope) {
                  ctx.loadShell({
                    schema: "mycite.v2.portal.shell.request.v1",
                    requested_surface_id: envelope.surface_id,
                    surface_query: envelope.surface_query || {},
                  });
                }
              } else if (!ok) {
                var msg =
                  (out.body && (out.body.detail || out.body.error || ("HTTP " + out.status))) ||
                  "unknown error";
                try {
                  window.alert("Edit failed: " + msg);
                } catch (_) {}
              }
            })
            .catch(function (err) {
              if (saveBtn) saveBtn.disabled = false;
              try {
                window.alert("Network error: " + (err && err.message ? err.message : err));
              } catch (_) {}
            });
        });
      }
    );
  }

  function bindMailboxEditActions(ctx, target) {
    // 2026-05-23: per-row inline edit on the Mailboxes table. Toggle
    // button shows/hides the hidden edit row; the form submits to
    // /__fnd/email/admin/edit and refreshes the shell on success.
    // Mirrors bindContactEditActions but operates on the dedicated
    // data-mailbox-edit-* attributes so the two tables can coexist
    // without selector collisions.
    if (!target) return;
    Array.prototype.forEach.call(
      target.querySelectorAll("[data-mailbox-edit-toggle]"),
      function (btn) {
        if (btn.dataset.mailboxEditBound === "1") return;
        btn.dataset.mailboxEditBound = "1";
        var index = btn.getAttribute("data-mailbox-edit-toggle");
        btn.addEventListener("click", function () {
          var row = target.querySelector(
            '[data-mailbox-edit-index="' + index + '"]'
          );
          if (!row) return;
          row.hidden = !row.hidden;
        });
      }
    );
    Array.prototype.forEach.call(
      target.querySelectorAll("[data-mailbox-edit-cancel]"),
      function (btn) {
        if (btn.dataset.mailboxCancelBound === "1") return;
        btn.dataset.mailboxCancelBound = "1";
        btn.addEventListener("click", function () {
          var editRow = btn.closest(".v2-mailboxEditRow");
          if (editRow) editRow.hidden = true;
        });
      }
    );
    Array.prototype.forEach.call(
      target.querySelectorAll("form.v2-mailboxEditForm"),
      function (form) {
        if (form.dataset.mailboxEditFormBound === "1") return;
        form.dataset.mailboxEditFormBound = "1";
        form.addEventListener("submit", function (event) {
          event.preventDefault();
          var route = form.getAttribute("data-mailbox-edit-route");
          var schema = form.getAttribute("data-mailbox-edit-schema") || "";
          var basePayload = {};
          try {
            basePayload = JSON.parse(form.getAttribute("data-mailbox-edit-payload") || "{}");
          } catch (_) {}
          var fields = asObject(basePayload).fields || {};
          Array.prototype.forEach.call(
            form.querySelectorAll("[data-mailbox-edit-key]"),
            function (input) {
              fields[input.getAttribute("data-mailbox-edit-key")] = input.value || "";
            }
          );
          var body = Object.assign({}, basePayload, { schema: schema, fields: fields });
          var saveBtn = form.querySelector('button[type="submit"]');
          if (saveBtn) saveBtn.disabled = true;
          fetch(route, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
            credentials: "same-origin",
          })
            .then(function (r) {
              return r.json().then(function (j) {
                return { status: r.status, body: j };
              });
            })
            .then(function (out) {
              if (saveBtn) saveBtn.disabled = false;
              var ok = out.status >= 200 && out.status < 300 && out.body && out.body.ok !== false;
              if (ok && typeof ctx.loadShell === "function") {
                var envelope = ctx.getEnvelope && ctx.getEnvelope();
                if (envelope) {
                  ctx.loadShell({
                    schema: "mycite.v2.portal.shell.request.v1",
                    requested_surface_id: envelope.surface_id,
                    surface_query: envelope.surface_query || {},
                  });
                }
              } else if (!ok) {
                var msg =
                  (out.body && (out.body.detail || out.body.error || ("HTTP " + out.status))) ||
                  "unknown error";
                try {
                  window.alert("Edit failed: " + msg);
                } catch (_) {}
              }
            })
            .catch(function (err) {
              if (saveBtn) saveBtn.disabled = false;
              try {
                window.alert("Network error: " + (err && err.message ? err.message : err));
              } catch (_) {}
            });
        });
      }
    );
  }

  // --- ext_resources interactions ---------------------------------------
  // The Library is a stateful master/detail controller: leaflets live in JS
  // state, filtering + sorting + mutations happen client-side, and mutations
  // refresh the list via GET /__fnd/resources/leaflets — NO full shell reload
  // (the operator's facets, scroll and open detail survive).
  function bindResourcesLibrary(ctx, app) {
    var listEl = app.querySelector(".v2-leafletList");
    var facetEl = app.querySelector(".v2-facetBar");
    var detailPane = app.querySelector(".v2-resourcesApp__detail");
    var dataEl = app.querySelector(".v2-leafletData");
    var routes = {
      detail: app.getAttribute("data-detail-route"),
      save: app.getAttribute("data-save-route"),
      retitle: app.getAttribute("data-retitle-route"),
      rename: app.getAttribute("data-rename-route"),
      renamePreview: app.getAttribute("data-rename-preview-route"),
      del: app.getAttribute("data-delete-route"),
      leaflets: app.getAttribute("data-leaflets-route"),
    };
    var FACETS = [
      { key: "kind", label: "Kind", field: "kind" },
      { key: "owner", label: "Owner", field: "owner" },
      { key: "entity_type", label: "Entity", field: "entity_type" },
      { key: "ext", label: "Ext", field: "ext" },
      { key: "variant", label: "Variant", field: "slug_variant" },
    ];
    var state = { leaflets: [], filters: { text: "" }, sortDesc: false, selected: "" };
    try { state.leaflets = JSON.parse((dataEl && dataEl.textContent) || "[]"); } catch (_) { state.leaflets = []; }

    function byFilename(fn) {
      for (var i = 0; i < state.leaflets.length; i++) {
        if (asText(state.leaflets[i].filename) === fn) return state.leaflets[i];
      }
      return null;
    }
    function distinct(field) {
      var seen = {};
      state.leaflets.forEach(function (r) { var v = asText(r[field]); if (v) seen[v] = 1; });
      return Object.keys(seen).sort();
    }
    function filtered() {
      var f = state.filters;
      var rows = state.leaflets.filter(function (r) {
        for (var i = 0; i < FACETS.length; i++) {
          var fc = FACETS[i];
          if (f[fc.key] && asText(r[fc.field]) !== f[fc.key]) return false;
        }
        if (f.text && asText(r.naming).indexOf(f.text) === -1) return false;
        return true;
      });
      rows.sort(function (a, b) {
        var av = asText(a.slug), bv = asText(b.slug);
        if (av === bv) return 0;
        return state.sortDesc ? (av < bv ? 1 : -1) : (av < bv ? -1 : 1);
      });
      return rows;
    }
    function renderFacets() {
      var selects = FACETS.map(function (fc) {
        var opts = distinct(fc.field).map(function (v) {
          return '<option value="' + escapeHtml(v) + '"' + (state.filters[fc.key] === v ? " selected" : "") + ">" + escapeHtml(v) + "</option>";
        }).join("");
        return '<label class="v2-facet"><span>' + escapeHtml(fc.label) + "</span>" +
          '<select data-facet="' + fc.key + '"><option value="">all</option>' + opts + "</select></label>";
      }).join("");
      facetEl.innerHTML =
        '<input type="search" class="v2-resourcesSearch" data-facet-text placeholder="Filter by naming…" value="' + escapeHtml(state.filters.text) + '" />' +
        '<div class="v2-facetRow">' + selects +
        '<button type="button" class="v2-rowAction v2-facet__sort" data-facet-sort>Slug ' + (state.sortDesc ? "▴" : "▾") + "</button></div>";
      Array.prototype.forEach.call(facetEl.querySelectorAll("select[data-facet]"), function (sel) {
        sel.addEventListener("change", function () { state.filters[sel.getAttribute("data-facet")] = sel.value; renderList(); });
      });
      var textBox = facetEl.querySelector("[data-facet-text]");
      if (textBox) textBox.addEventListener("input", function () { state.filters.text = (textBox.value || "").trim().toLowerCase(); renderList(); });
      var sortBtn = facetEl.querySelector("[data-facet-sort]");
      if (sortBtn) sortBtn.addEventListener("click", function () { state.sortDesc = !state.sortDesc; renderFacets(); renderList(); });
    }
    function renderList() {
      var rows = filtered();
      listEl.innerHTML = rows.length
        ? '<div class="v2-leafletList__count">' + rows.length + " of " + state.leaflets.length + "</div>" +
          rows.map(renderLeafletListItem).join("")
        : '<p class="v2-extensionCard__empty">No leaflets match.</p>';
      Array.prototype.forEach.call(listEl.querySelectorAll(".v2-leafletItem"), function (item) {
        if (item.getAttribute("data-filename") === state.selected) item.classList.add("is-active");
        item.addEventListener("click", function () {
          Array.prototype.forEach.call(listEl.querySelectorAll(".v2-leafletItem.is-active"), function (n) { n.classList.remove("is-active"); });
          item.classList.add("is-active");
          openDetail(byFilename(item.getAttribute("data-filename")));
        });
      });
    }
    function refresh() {
      if (!routes.leaflets) return;
      fetch(routes.leaflets, { credentials: "same-origin" })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (!j || !j.ok) return;
          state.leaflets = asList(j.leaflets);
          renderFacets(); renderList();
          if (state.selected && !byFilename(state.selected)) {
            detailPane.innerHTML = '<p class="v2-resourcesDetail__placeholder">Select a leaflet to view or edit.</p>';
            state.selected = "";
          }
        })
        .catch(function () {});
    }
    function openDetail(r) {
      if (!r || !detailPane) return;
      state.selected = asText(r.filename);
      if (asText(r.gallery) === "profiles") { openProfileDetail(r); }
      else { detailPane.innerHTML = renderBinaryDetail(r) + renderManageActions(r); bindManage(r); }
    }
    function openProfileDetail(r) {
      detailPane.innerHTML = '<p class="v2-resourcesDetail__loading">Loading…</p>';
      fetch(routes.detail + "?slug=" + encodeURIComponent(asText(r.slug)), { credentials: "same-origin" })
        .then(function (x) { return x.json(); })
        .then(function (j) {
          if (!j || !j.ok) { detailPane.innerHTML = '<p class="v2-resourcesDetail__error">Could not load profile.</p>'; return; }
          var lib = componentLibrary();
          var formHtml = (lib && j.edit_frame && typeof lib.renderComponentFrame === "function")
            ? lib.renderComponentFrame(j.edit_frame)
            : '<p class="v2-resourcesDetail__error">Editor unavailable.</p>';
          // Build the head from the FETCHED profile so it reflects just-saved
          // values (the list-row object can be stale right after a save).
          var prof = asObject(j.profile);
          var head = { title: asText(prof.display_name) || asText(r.slug), image_url: asText(prof.image_url), slug: asText(r.slug) };
          detailPane.innerHTML = renderProfileHead(head) + formHtml +
            '<div class="v2-resourcesDetail__result"></div>' + renderManageActions(r);
          bindProfileSave(r);
          bindManage(r);
        })
        .catch(function () { detailPane.innerHTML = '<p class="v2-resourcesDetail__error">Network error.</p>'; });
    }
    function bindProfileSave(r) {
      var form = detailPane.querySelector("form");
      if (!form) return;
      var resultEl = detailPane.querySelector(".v2-resourcesDetail__result");
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var fields = collectFormFieldValues(form);
        var btn = form.querySelector('button[type="submit"]');
        if (btn) btn.disabled = true;
        if (resultEl) resultEl.textContent = "Saving & rebuilding…";
        fetch(routes.save, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ slug: asText(r.slug), fields: fields }), credentials: "same-origin" })
          .then(function (x) { return x.json().then(function (j) { return { status: x.status, body: j }; }); })
          .then(function (out) {
            if (btn) btn.disabled = false;
            var ok = out.body && out.body.ok;
            if (resultEl) {
              if (ok) {
                var prop = (out.body && out.body.propagation) || {};
                var rebuilt = (prop.rebuilt || []).length;
                resultEl.textContent = "Saved." + (rebuilt ? " Rebuilt " + rebuilt + " site(s)." : "");
              } else {
                resultEl.textContent = "Save failed: " + ((out.body && (out.body.detail || out.body.error)) || ("HTTP " + out.status));
              }
            }
            if (ok) refresh();  // refresh the list; the form keeps the saved values + message
          })
          .catch(function () { if (btn) btn.disabled = false; if (resultEl) resultEl.textContent = "Network error."; });
      });
    }
    function postManage(btn, route, body, clearDetail) {
      btn.disabled = true;
      fetch(route, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), credentials: "same-origin" })
        .then(function (x) { return x.json().then(function (j) { return { status: x.status, body: j }; }); })
        .then(function (out) {
          btn.disabled = false;
          if (out.body && out.body.ok) {
            if (clearDetail) { detailPane.innerHTML = '<p class="v2-resourcesDetail__placeholder">Select a leaflet to view or edit.</p>'; state.selected = ""; }
            refresh();
          } else {
            try { window.alert("Failed: " + ((out.body && (out.body.detail || out.body.error)) || ("HTTP " + out.status))); } catch (_) {}
          }
        })
        .catch(function () { btn.disabled = false; });
    }
    function cascadeRename(btn, oldSlug, newSlug) {
      var payload = { gallery: "profiles", old_slug: oldSlug, new_slug: newSlug };
      btn.disabled = true;
      fetch(routes.renamePreview, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload), credentials: "same-origin" })
        .then(function (x) { return x.json().then(function (j) { return { status: x.status, body: j }; }); })
        .then(function (out) {
          btn.disabled = false;
          var rep = out.body || {};
          if (!rep.ok) { try { window.alert("Cannot rename: " + (rep.detail || rep.error || ("HTTP " + out.status))); } catch (_) {} return; }
          var c = asObject(rep.report);
          var msg = "Rename profile slug '" + oldSlug + "' → '" + newSlug + "'?\n\nThis cascade will update:\n" +
            "  • canonical profile\n  • " + asList(c.excerpts).length + " per-site excerpt(s)\n" +
            "  • " + asList(c.related).length + " related-reference(s)\n  • FND network refs: " + (c.fnd_network ? "yes" : "no") + "\n" +
            "  • " + asList(c.data_files).length + " data-file URL ref(s)\n  • rebuild " + asList(c.sites).length + " site(s)";
          if (typeof window.confirm === "function" && !window.confirm(msg)) return;
          postManage(btn, routes.rename, payload, true);
        })
        .catch(function () { btn.disabled = false; });
    }
    function bindManage(r) {
      Array.prototype.forEach.call(detailPane.querySelectorAll("[data-manage]"), function (btn) {
        btn.addEventListener("click", function () {
          var action = btn.getAttribute("data-manage");
          if (action === "retitle") {
            var nt = window.prompt && window.prompt("New title for " + asText(r.filename) + ":", asText(r.title));
            if (!nt) return;
            postManage(btn, routes.retitle, { gallery: asText(r.gallery), filename: asText(r.filename), new_asset_id: nt });
          } else if (action === "rename") {
            var ns = window.prompt && window.prompt("Rename slug '" + asText(r.slug) + "' to:", asText(r.slug));
            if (!ns || ns === asText(r.slug)) return;
            if (asText(r.gallery) === "profiles") { cascadeRename(btn, asText(r.slug), ns); return; }
            postManage(btn, routes.rename, { gallery: asText(r.gallery), old_slug: asText(r.slug), new_slug: ns });
          } else if (action === "delete") {
            if (typeof window.confirm === "function" && !window.confirm("Delete " + asText(r.filename) + "? (only if unused)")) return;
            postManage(btn, routes.del, { gallery: asText(r.gallery), filename: asText(r.filename) }, true);
          }
        });
      });
    }
    renderFacets();
    renderList();
  }

  function bindResourcesAllocation(ctx, app) {
    function reloadSurface() {
      if (typeof ctx.loadShell !== "function") return;
      var env = ctx.getEnvelope && ctx.getEnvelope();
      if (env) ctx.loadShell({ schema: "mycite.v2.portal.shell.request.v1", requested_surface_id: env.surface_id, surface_query: env.surface_query || {} });
    }
    var searchBox = app.querySelector(".v2-resourcesSearch");
    if (searchBox) searchBox.addEventListener("input", function () {
      var q = (searchBox.value || "").trim().toLowerCase();
      Array.prototype.forEach.call(app.querySelectorAll(".v2-resourcesMember"), function (m) {
        var hit = !q || (m.getAttribute("data-resources-search") || "").indexOf(q) !== -1;
        m.style.display = hit ? "" : "none";
      });
    });
    var allocSite = app.getAttribute("data-site");
    var allocAddRoute = app.getAttribute("data-add-route");
    var allocRemoveRoute = app.getAttribute("data-remove-route");
    Array.prototype.forEach.call(app.querySelectorAll("[data-resources-alloc]"), function (btn) {
      btn.addEventListener("click", function () {
        var action = btn.getAttribute("data-resources-alloc");
        var route = action === "remove" ? allocRemoveRoute : allocAddRoute;
        if (!route || !allocSite) return;
        var body = { site: allocSite, kind: btn.getAttribute("data-kind"), asset_path: btn.getAttribute("data-asset-path") };
        if (action === "add") body.asset_id = btn.getAttribute("data-asset-id") || "";
        btn.disabled = true;
        fetch(route, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), credentials: "same-origin" })
          .then(function (r) { return r.json().then(function (j) { return { status: r.status, body: j }; }); })
          .then(function (out) {
            btn.disabled = false;
            if (out.body && out.body.ok) reloadSurface();
            else { try { window.alert("Allocation failed: " + ((out.body && (out.body.detail || out.body.error)) || ("HTTP " + out.status))); } catch (_) {} }
          })
          .catch(function () { btn.disabled = false; });
      });
    });
  }

  function bindInnerSubtabs(ctx, target) {
    Array.prototype.forEach.call(target.querySelectorAll(".v2-innerSubtabs__option"), function (node) {
      if (node.dataset.subtabBound === "1") return;
      node.dataset.subtabBound = "1";
      node.addEventListener("click", function () {
        var payload;
        try {
          payload = JSON.parse(node.getAttribute("data-subtab-action") || "{}");
        } catch (_) {
          return;
        }
        if (payload && payload.requested_surface_id && typeof ctx.loadShell === "function") {
          ctx.loadShell(payload);
        }
      });
    });
  }

  // Browse drill-down reloads the shell with the SERVER-STAMPED base query
  // (data-nav-base: the pinned extension/subtab/grantee/mode keys) plus a
  // per-action patch. The runtime envelope exposes surface_id but NOT
  // surface_query, so the base MUST come from the payload, not the envelope.
  function resourcesNav(ctx, app, patch) {
    var env = ctx.getEnvelope && ctx.getEnvelope();
    if (!env || typeof ctx.loadShell !== "function") return;
    var base = {};
    try {
      base = JSON.parse((app && app.getAttribute("data-nav-base")) || "{}");
    } catch (_) {
      base = {};
    }
    var sq = Object.assign({}, base);
    Object.keys(patch || {}).forEach(function (k) {
      if (patch[k] === null) {
        delete sq[k];
      } else {
        sq[k] = patch[k];
      }
    });
    ctx.loadShell({
      schema: "mycite.v2.portal.shell.request.v1",
      requested_surface_id: env.surface_id,
      surface_query: sq,
    });
  }

  function bindResourcesBrowse(ctx, app) {
    var dirType = app.getAttribute("data-dir-type") || "";
    // Navigation (drill-down) is DELEGATED on the container so the dendrogram's
    // view buttons keep working after a client-side expand/collapse re-render.
    app.addEventListener("click", function (e) {
      var el = e.target;
      if (!el || !el.closest) return;
      var ot = el.closest("[data-open-type]");
      if (ot && app.contains(ot)) {
        e.preventDefault();
        resourcesNav(ctx, app, { browse_view: "directory", browse_type: ot.getAttribute("data-open-type"), browse_instance: null });
        return;
      }
      var oi = el.closest("[data-open-instance]");
      if (oi && app.contains(oi)) {
        resourcesNav(ctx, app, { browse_view: "instance", browse_type: dirType, browse_instance: oi.getAttribute("data-open-instance") });
        return;
      }
      var bk = el.closest("[data-browse-back]");
      if (bk && app.contains(bk)) {
        if (bk.getAttribute("data-browse-back") === "hierarchy") {
          resourcesNav(ctx, app, { browse_view: "hierarchy", browse_type: null, browse_instance: null });
        } else {
          resourcesNav(ctx, app, { browse_view: "directory", browse_type: dirType, browse_instance: null });
        }
      }
    });
    bindDendrogram(ctx, app);
    bindDirectoryFilter(app);
    bindBrowseInstanceEdit(ctx, app);
  }

  // Dendrogram expand/collapse + per-node icon editing (the folded-in Manifest).
  // Expand/collapse mutates a client-side `collapsed` Set and re-renders ONLY the
  // dendro host (no shell reload). Icon edit reuses the manifest endpoints and
  // reloads the surface so the new icon shows. The host listener persists across
  // re-renders; nav (data-open-type) is handled by the container delegation above.
  function bindDendrogram(ctx, app) {
    var host = app.querySelector("[data-dendro-host]");
    if (!host) return;
    var nodes;
    try { nodes = asList(JSON.parse(host.getAttribute("data-dendro-nodes") || "[]")); }
    catch (_) { nodes = []; }
    var p = {
      sprite_href: app.getAttribute("data-sprite-href") || "",
      icon_url_prefix: app.getAttribute("data-icon-prefix") || "",
    };
    var setRoute = app.getAttribute("data-set-icon-route");
    var optionsRoute = app.getAttribute("data-icon-options-route");
    var optionsCache = null;
    function loadIconOptions() {
      if (optionsCache) return Promise.resolve(optionsCache);
      if (!optionsRoute) return Promise.resolve([]);
      return fetch(optionsRoute, { credentials: "same-origin" })
        .then(function (r) { return r.json(); })
        .then(function (j) { optionsCache = (j && j.options) || []; return optionsCache; })
        .catch(function () { return []; });
    }
    var collapsed = new Set();
    function rerender() { host.innerHTML = renderDendrogram(nodes, p, collapsed); }
    host.addEventListener("click", function (e) {
      var el = e.target;
      if (!el || !el.closest) return;
      var tog = el.closest("[data-dendro-toggle]");
      if (tog) {
        e.preventDefault();
        var slug = tog.getAttribute("data-dendro-toggle");
        if (collapsed.has(slug)) collapsed.delete(slug); else collapsed.add(slug);
        rerender();
        return;
      }
      var all = el.closest("[data-dendro-all]");
      if (all) {
        e.preventDefault();
        collapsed.clear();
        if (all.getAttribute("data-dendro-all") === "collapse") {
          nodes.forEach(function (n) {
            var o = asObject(n);
            if (o.has_children) collapsed.add(asText(o.full_slug));
          });
        }
        rerender();
        return;
      }
      var edit = el.closest("[data-edit-icon]");
      if (edit && setRoute) {
        e.preventDefault();
        e.stopPropagation();
        var full = edit.getAttribute("data-edit-icon");
        var node = edit.closest(".v2-dendro__node");
        if (!node || node.querySelector(".v2-dendro__picker")) return;
        loadIconOptions().then(function (options) {
          var sel = document.createElement("select");
          sel.className = "v2-dendro__picker";
          sel.appendChild(new Option("(manifest default)", ""));
          options.forEach(function (o) {
            sel.appendChild(new Option(asText(o.icon_ref), asText(o.icon_ref)));
          });
          sel.addEventListener("change", function () {
            fetch(setRoute, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              credentials: "same-origin",
              body: JSON.stringify({ full_slug: full, icon_ref: sel.value }),
            })
              .then(function (r) { return r.json(); })
              .then(function (res) { if (res && res.ok) resourcesNav(ctx, app, {}); })
              .catch(function () {});
          });
          node.appendChild(sel);
          sel.focus();
        });
      }
    });
  }

  // Directory: unified text-search + subtype-chip filter over the instance list.
  function bindDirectoryFilter(app) {
    var items = app.querySelectorAll(".v2-leafletDir__item");
    if (!items.length) return;
    var searchEl = app.querySelector(".v2-leafletDir__search");
    var chips = app.querySelectorAll(".v2-browseFilter");
    var emptyEl = app.querySelector(".v2-leafletDir__empty");
    var activeChip = "";
    function apply() {
      var q = searchEl ? (searchEl.value || "").trim().toLowerCase() : "";
      var shown = 0;
      Array.prototype.forEach.call(items, function (item) {
        var t = item.getAttribute("data-full-type") || "";
        var inChip = !activeChip || t === activeChip || t.indexOf(activeChip + "-") === 0;
        var inSearch = !q || (item.getAttribute("data-search") || "").indexOf(q) !== -1;
        var show = inChip && inSearch;
        item.style.display = show ? "" : "none";
        if (show) shown += 1;
      });
      if (emptyEl) emptyEl.hidden = shown !== 0;
    }
    Array.prototype.forEach.call(chips, function (chip) {
      chip.addEventListener("click", function () {
        activeChip = chip.getAttribute("data-subtype-filter") || "";
        Array.prototype.forEach.call(chips, function (c) { c.classList.toggle("is-active", c === chip); });
        apply();
      });
    });
    if (searchEl) searchEl.addEventListener("input", apply);
  }

  // Instance view: lazily fetch the library's profile editor frame + bind save
  // (reuses /__fnd/resources/profile/{detail,save} → save propagates + rebuilds).
  function bindBrowseInstanceEdit(ctx, app) {
    var editBtn = app.querySelector("[data-edit-profile]");
    if (!editBtn) return;
    var detailRoute = app.getAttribute("data-profile-detail-route");
    var saveRoute = app.getAttribute("data-profile-save-route");
    var pane = app.querySelector(".v2-browseEdit__pane");
    if (!detailRoute || !pane) return;
    editBtn.addEventListener("click", function () {
      if (editBtn.getAttribute("data-open") === "1") {
        pane.innerHTML = "";
        editBtn.removeAttribute("data-open");
        editBtn.textContent = "Edit profile";
        return;
      }
      var slug = editBtn.getAttribute("data-edit-profile");
      pane.innerHTML = '<p class="v2-resourcesDetail__loading">Loading…</p>';
      fetch(detailRoute + "?slug=" + encodeURIComponent(slug), { credentials: "same-origin" })
        .then(function (x) { return x.json(); })
        .then(function (j) {
          if (!j || !j.ok) { pane.innerHTML = '<p class="v2-resourcesDetail__error">Could not load profile.</p>'; return; }
          var lib = componentLibrary();
          var formHtml = lib && j.edit_frame && typeof lib.renderComponentFrame === "function"
            ? lib.renderComponentFrame(j.edit_frame)
            : '<p class="v2-resourcesDetail__error">Editor unavailable.</p>';
          pane.innerHTML = formHtml + '<div class="v2-resourcesDetail__result"></div>';
          editBtn.setAttribute("data-open", "1");
          editBtn.textContent = "Close editor";
          bindBrowseProfileSave(pane, slug, saveRoute);
        })
        .catch(function () { pane.innerHTML = '<p class="v2-resourcesDetail__error">Network error.</p>'; });
    });
  }

  function bindBrowseProfileSave(pane, slug, saveRoute) {
    var form = pane.querySelector("form");
    if (!form || !saveRoute) return;
    var resultEl = pane.querySelector(".v2-resourcesDetail__result");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var fields = collectFormFieldValues(form);
      var btn = form.querySelector('button[type="submit"]');
      if (btn) btn.disabled = true;
      if (resultEl) resultEl.textContent = "Saving & rebuilding…";
      fetch(saveRoute, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ slug: slug, fields: fields }), credentials: "same-origin" })
        .then(function (x) { return x.json().then(function (j) { return { status: x.status, body: j }; }); })
        .then(function (out) {
          if (btn) btn.disabled = false;
          var ok = out.body && out.body.ok;
          if (resultEl) {
            if (ok) {
              var prop = (out.body && out.body.propagation) || {};
              var rebuilt = (prop.rebuilt || []).length;
              resultEl.textContent = "Saved." + (rebuilt ? " Rebuilt " + rebuilt + " site(s)." : "");
            } else {
              resultEl.textContent = "Save failed: " + ((out.body && (out.body.detail || out.body.error)) || ("HTTP " + out.status));
            }
          }
        })
        .catch(function () { if (btn) btn.disabled = false; if (resultEl) resultEl.textContent = "Network error."; });
    });
  }

  function bindResourcesApp(ctx, target) {
    bindInnerSubtabs(ctx, target);
    var app = target.querySelector(".v2-resourcesApp");
    if (!app || app.dataset.resourcesBound === "1") return;
    app.dataset.resourcesBound = "1";
    var uploadForm = app.querySelector("[data-resources-upload-route]");
    if (uploadForm) bindResourcesUpload(uploadForm);
    var mode = app.getAttribute("data-resources-mode");
    if (app.classList.contains("v2-typeBrowse")) {
      bindResourcesBrowse(ctx, app);
    } else if (mode === "library") {
      bindResourcesLibrary(ctx, app);
    } else if (mode === "allocation") {
      bindResourcesAllocation(ctx, app);
    }
  }

  function bindResourcesUpload(form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var route = form.getAttribute("data-resources-upload-route");
      var resultEl = form.querySelector(".v2-resourcesUpload__result");
      var data = new FormData(form);
      var submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;
      if (resultEl) { resultEl.hidden = false; resultEl.textContent = "Uploading…"; }
      fetch(route, { method: "POST", body: data, credentials: "same-origin" })
        .then(function (r) { return r.json().then(function (j) { return { status: r.status, body: j }; }); })
        .then(function (out) {
          if (submitBtn) submitBtn.disabled = false;
          if (resultEl) {
            resultEl.textContent = out.body && out.body.ok
              ? "Uploaded: " + (out.body.asset_path || out.body.asset_id || "")
              : "Upload failed: " + ((out.body && (out.body.detail || out.body.error)) || ("HTTP " + out.status));
          }
        })
        .catch(function (err) {
          if (submitBtn) submitBtn.disabled = false;
          if (resultEl) resultEl.textContent = "Network error: " + (err && err.message ? err.message : err);
        });
    });
  }

  function bindExtensionActions(ctx, target, extensions) {
    if (!target || !extensions || !extensions.length) return;
    bindResourcesApp(ctx, target);
    // Bind the in-card grantee picker hosted by the Per-grantee subtab (reuses the
    // grantee-selector mechanic: a click posts its select_action via loadShell).
    asList(extensions).forEach(function (entry) {
      var picker = asObject(asObject(entry).payload).grantee_picker;
      if (picker && asList(picker.grantees).length) {
        bindGranteeSelector(ctx, target, picker);
      }
    });
    Array.prototype.forEach.call(
      target.querySelectorAll("form[data-form-submit-route]"),
      function (form) {
        bindFormSubmit(ctx, form);
      }
    );
    Array.prototype.forEach.call(
      target.querySelectorAll(".v2-rowAction[data-row-action-route]"),
      function (button) {
        bindRowAction(ctx, button);
      }
    );
    bindContactEditActions(ctx, target);
    bindMailboxEditActions(ctx, target);
  }

  function renderGenericSurface(ctx, target, region, surfacePayload) {
    var adapter = toolSurfaceAdapter();
    var granteeSelector = surfacePayload && surfacePayload.grantee_selector
      ? asObject(surfacePayload.grantee_selector)
      : null;
    var extensionTabs = surfacePayload && surfacePayload.extension_subtab_selector
      ? asObject(surfacePayload.extension_subtab_selector)
      : null;
    var extensions = asList(surfacePayload && surfacePayload.extensions);
    var hasContent =
      adapter.hasGenericContent(surfacePayload) ||
      (granteeSelector && asList(granteeSelector.grantees).length > 0) ||
      (extensionTabs && asList(extensionTabs.tabs).length > 0) ||
      extensions.length > 0;
    var rendered = adapter.renderWrappedSurface(
      target,
      adapter.resolveSurfaceState({
        region: region,
        surfacePayload: surfacePayload,
        title: region.title || "Workbench",
        hasContent: hasContent,
      }),
      renderGranteeSelector(granteeSelector) +
        renderExtensionTabs(extensionTabs) +
        renderCards(surfacePayload.cards || []) +
        renderSections(surfacePayload.sections || []) +
        renderExtensions(extensions) +
        renderNotes(surfacePayload.notes || [])
    );
    if (rendered && granteeSelector) {
      bindGranteeSelector(ctx, target, granteeSelector);
    }
    if (rendered && extensionTabs) {
      bindExtensionTabs(ctx, target, extensionTabs);
    }
    if (rendered && extensions.length) {
      bindExtensionActions(ctx, target, extensions);
    }
    return rendered;
  }

  function renderIdentityBadge(shortValue, fullValue) {
    var shortToken = asText(shortValue) || "—";
    var fullToken = asText(fullValue);
    return (
      '<div class="v2-workbenchUi__identity">' +
      '<span class="v2-workbenchUi__badge">' +
      escapeHtml(shortToken) +
      "</span>" +
      (fullToken
        ? '<div class="v2-workbenchUi__subvalue">' + escapeHtml(fullToken) + "</div>"
        : "") +
      "</div>"
    );
  }

  function renderDocumentRows(rows, sourceVisibility) {
    if (!rows.length) {
      return '<tr><td colspan="' + String(sourceVisibility === "hide" ? 4 : 5) + '">No authoritative documents matched the current filter.</td></tr>';
    }
    return rows
      .map(function (row, index) {
        var selection = row.selected ? '<span class="v2-workbenchUi__selectedTag">Selected</span>' : "";
        return (
          '<tr class="v2-workbenchUi__row v2-workbenchUi__row--document' +
          (row.selected ? " is-selected" : "") +
          '" tabindex="0" data-workbench-document-index="' +
          String(index) +
          '">' +
          '<td><div class="v2-workbenchUi__primaryCell">' +
          selection +
          '<strong>' +
          escapeHtml(stripJsonSuffix(row.canonical_name || row.label || row.document_name || row.document_id || "—")) +
          "</strong>" +
          '<div class="v2-workbenchUi__subvalue">' +
          escapeHtml(row.document_id || "—") +
          "</div></div></td>" +
          (sourceVisibility === "hide"
            ? ""
            : "<td>" +
              escapeHtml(row.source_kind || "—") +
              "</td>") +
          "<td>" +
          renderIdentityBadge(row.version_hash_short, row.version_hash) +
          "</td>" +
          "<td>" +
          escapeHtml(String(row.row_count || 0)) +
          "</td>" +
          '<td><button class="v2-workbenchUi__action" type="button" data-workbench-document-index="' +
          String(index) +
          '">' +
          escapeHtml(row.selected ? "Selected" : "Focus") +
          "</button></td></tr>"
        );
      })
      .join("");
  }

  function renderDatumCell(row, lens) {
    if (lens === "raw") {
      return (
        '<div class="v2-workbenchUi__primaryCell"><strong>' +
        escapeHtml(row.raw_preview || row.raw_json || "—") +
        "</strong></div>"
      );
    }
    var primary = row.display_value || row.labels || row.primary_value_token || row.object_ref || "—";
    var detail = row.display_summary || ((row.relation || "—") + " -> " + (row.object_ref || "—"));
    return (
      '<div class="v2-workbenchUi__primaryCell"><strong>' +
      escapeHtml(primary) +
      "</strong>" +
      '<div class="v2-workbenchUi__subvalue">' +
      escapeHtml(detail) +
      "</div></div>"
    );
  }

  function renderDatumRows(rows, options) {
    var opts = options || {};
    var lens = asText(opts.lens) || "interpreted";
    if (!rows.length) {
      return '<tr><td colspan="6">No datum rows matched the current filter.</td></tr>';
    }
    return rows
      .map(function (row, index) {
        var globalIndex = opts.offset + index;
        var selection = row.selected ? '<span class="v2-workbenchUi__selectedTag">Selected</span>' : "";
        return (
          '<tr class="v2-workbenchUi__row v2-workbenchUi__row--datum' +
          (row.selected ? " is-selected" : "") +
          '" tabindex="0" data-workbench-row-index="' +
          String(globalIndex) +
          '">' +
          '<td><div class="v2-workbenchUi__primaryCell">' +
          selection +
          '<strong>' +
          escapeHtml(row.datum_address || "—") +
          "</strong>" +
          '<div class="v2-workbenchUi__subvalue">' +
          escapeHtml("L" + String(row.layer || 0) + " · VG" + String(row.value_group || 0) + " · I" + String(row.iteration || 0)) +
          "</div></div></td>" +
          "<td>" +
          renderDatumCell(row, lens) +
          "</td>" +
          "<td>" +
          renderIdentityBadge(row.hyphae_hash_short, row.hyphae_hash) +
          "</td>" +
          '<td><button class="v2-workbenchUi__action" type="button" data-workbench-row-index="' +
          String(globalIndex) +
          '">' +
          escapeHtml(row.selected ? "Selected" : "Focus") +
          "</button></td></tr>"
        );
      })
      .join("");
  }

  function renderDatumGroup(group, lens, offset) {
    var rows = asList(group.items);
    return (
      '<section class="v2-workbenchUi__group">' +
      '<div class="v2-workbenchUi__groupHeader"><h4>' +
      escapeHtml(group.title || "Rows") +
      "</h4>" +
      (group.summary ? "<p>" + escapeHtml(group.summary) + "</p>" : "") +
      "</div>" +
      '<div class="v2-tableWrap v2-workbenchUi__tableWrap">' +
      '<table class="v2-table v2-workbenchUiTable"><thead class="v2-workbenchUi__stickyHeader"><tr>' +
      "<th>Datum</th><th>" +
      escapeHtml(lens === "raw" ? "Raw Payload" : "Interpreted Row") +
      "</th><th>Identity</th><th>Action</th>" +
      "</tr></thead><tbody>" +
      renderDatumRows(rows, { lens: lens, offset: offset }) +
      "</tbody></table></div></section>"
    );
  }

  function flattenDatumRows(workspace) {
    var datumGrid = asObject(workspace.datum_grid);
    var layers = asList(datumGrid.layers);
    if (layers.length) {
      var matrixRows = [];
      layers.forEach(function (layer) {
        asList(asObject(layer).value_groups).forEach(function (valueGroup) {
          asList(asObject(valueGroup).cells).forEach(function (row) {
            matrixRows.push(row);
          });
        });
      });
      if (matrixRows.length) return matrixRows;
    }
    var groups = asList(datumGrid.groups);
    if (groups.length) {
      var rows = [];
      groups.forEach(function (group) {
        asList(asObject(group).items).forEach(function (row) {
          rows.push(row);
        });
      });
      return rows;
    }
    return asList(datumGrid.rows);
  }

  function renderDatumMatrixCell(row, globalIndex) {
    var selection = row.selected ? "Selected · " : "";
    var diagnostics = asList(row.diagnostic_states).join(", ");
    var detailBits = [
      row.display_summary || "",
      diagnostics,
      row.hyphae_hash_short ? "ID " + row.hyphae_hash_short : "",
    ].filter(Boolean);
    return (
      '<button class="v2-workbenchUi__navButton" style="text-align:left;min-height:120px" type="button" data-workbench-row-index="' +
      String(globalIndex) +
      '">' +
      '<strong>' +
      escapeHtml(selection + "I" + String(row.iteration || 0) + " · " + (row.datum_address || "—")) +
      "</strong>" +
      '<small>' +
      escapeHtml(row.display_value || row.labels || row.primary_value_token || "—") +
      "</small>" +
      '<small>' +
      escapeHtml(detailBits.join(" · ") || "—") +
      "</small></button>"
    );
  }

  function renderDatumMatrix(layers) {
    var offset = 0;
    return asList(layers)
      .map(function (layer) {
        var valueGroupHtml = asList(asObject(layer).value_groups)
          .map(function (valueGroup) {
            var cells = asList(asObject(valueGroup).cells);
            var cards = cells
              .map(function (row, index) {
                return renderDatumMatrixCell(row, offset + index);
              })
              .join("");
            offset += cells.length;
            return (
              '<section class="v2-card" style="margin-top:12px"><h4>' +
              escapeHtml(asObject(valueGroup).title || "Value Group") +
              "</h4>" +
              '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px">' +
              cards +
              "</div></section>"
            );
          })
          .join("");
        return (
          '<section class="v2-workbenchUi__group">' +
          '<div class="v2-workbenchUi__groupHeader"><h4>' +
          escapeHtml(asObject(layer).title || "Layer") +
          "</h4>" +
          (asObject(layer).summary ? "<p>" + escapeHtml(asObject(layer).summary) + "</p>" : "") +
          "</div>" +
          valueGroupHtml +
          "</section>"
        );
      })
      .join("");
  }

  // ------------------------------------------------------------------
  // Trifecta workbench layout (Portal-Workbench-Trifecta-Layout-2026-05-18)
  // Three regions:
  //   1. Sandbox toggle bar (top)
  //   2. Slim document column with "+" affordance (left)
  //   3. Datum document editor (right)
  // ------------------------------------------------------------------

  function activeSandboxToken(region) {
    var fromRegion = asText(
      asObject(asObject(region).document_collection).sandbox_id
    );
    if (fromRegion) return fromRegion;
    try {
      var fromUrl = new URLSearchParams(window.location.search).get("sandbox");
      if (fromUrl) return asText(fromUrl);
    } catch (_) {}
    return "system";
  }

  function availableSandboxes() {
    var globals = Array.isArray(window.__MYCITE_V2_SANDBOXES)
      ? window.__MYCITE_V2_SANDBOXES
      : [];
    return globals.map(function (s) {
      return {
        token: asText(s.token),
        label: asText(s.label) || asText(s.token),
        writable: !!s.writable,
      };
    });
  }


  function renderDocumentColumnItem(row, index) {
    var label = stripJsonSuffix(
      row.canonical_name || row.label || row.document_name || row.document_id || "—"
    );
    var rowCount = String(row.row_count || 0);
    var versionShort = asText(row.version_hash_short);
    return (
      '<li class="v2-workbenchUi__docItem' +
      (row.selected ? " is-selected" : "") +
      '" tabindex="0" data-workbench-document-index="' +
      String(index) +
      '" data-doc-id="' +
      escapeHtml(row.document_id || "") +
      '" title="' +
      escapeHtml(row.document_id || label) +
      '">' +
      '<span class="v2-workbenchUi__docName">' +
      escapeHtml(shortDocumentLabel(label) || label || "—") +
      "</span>" +
      '<span class="v2-workbenchUi__docMeta">' +
      escapeHtml(rowCount + " rows" + (versionShort ? " · " + versionShort : "")) +
      "</span></li>"
    );
  }

  function renderDocumentColumn(workspace, surfacePayload) {
    var documentTable = asObject(workspace.document_table);
    var rows = asList(documentTable.rows);
    var newForm = asObject(surfacePayload.new_source_document_form);
    var addButton =
      '<button type="button" class="v2-workbenchUi__addBtn" data-action="open-new-document" title="Create datum document" aria-label="Create datum document">+</button>';
    // Title-only creation: a free-text title (the backend sanitizes it into a
    // canonical name segment). No template/type picker at the creation gate —
    // document shape is authored later, inside the document.
    var formHtml =
      '<form class="v2-workbenchUi__newDocForm" data-form="new-document" hidden>' +
      '<input name="document_name" type="text" placeholder="Document title" ' +
      'maxlength="80" required autocomplete="off" />' +
      '<div class="v2-workbenchUi__newDocActions">' +
      '<button type="submit" class="v2-workbenchUi__primary">Create</button>' +
      '<button type="button" data-action="cancel-new-document">Cancel</button>' +
      "</div>" +
      '<small class="v2-workbenchUi__formStatus" data-role="status" hidden></small>' +
      "</form>";
    var itemsHtml = rows.length
      ? '<ul class="v2-workbenchUi__docList">' +
        rows.map(renderDocumentColumnItem).join("") +
        "</ul>"
      : '<p class="v2-workbenchUi__empty">No datum documents in this sandbox yet.</p>';
    return (
      '<aside class="v2-workbenchUi__docColumn" data-region="document-column">' +
      '<header class="v2-workbenchUi__docColumnHeader">' +
      "<h3>Documents</h3>" +
      addButton +
      "</header>" +
      formHtml +
      itemsHtml +
      "</aside>"
    );
  }

  function derivePrimaryKeyPath(raw) {
    if (!Array.isArray(raw) || raw.length < 2) return "";
    var second = raw[1];
    if (Array.isArray(second)) return "labels.0";
    if (second && typeof second === "object") {
      var keys = Object.keys(second);
      if (keys.length) return "magnitudes." + keys[0];
    }
    return "";
  }

  function renderDocumentEditorRow(row, index) {
    var primary = row.display_value || row.labels || row.primary_value_token || "";
    var addr = row.datum_address || "";
    var rawJson = row.raw_json || (row.raw != null ? JSON.stringify(row.raw) : "");
    var primaryKeyPath = row.primary_key_path || "";
    if (!primaryKeyPath) {
      try {
        primaryKeyPath = derivePrimaryKeyPath(row.raw != null ? row.raw : JSON.parse(rawJson || "null"));
      } catch (e) {
        primaryKeyPath = "";
      }
    }
    return (
      '<tr class="v2-workbenchUi__editorRow' +
      (row.selected ? " is-selected" : "") +
      '" data-row-index="' +
      String(index) +
      '" data-row-edit-mode="quick" data-datum-address="' +
      escapeHtml(addr) +
      '" data-row-raw="' +
      escapeHtml(rawJson) +
      '" data-row-primary-key="' +
      escapeHtml(primaryKeyPath) +
      '" data-row-lens="' +
      escapeHtml(asText(row.resolved_lens)) +
      '">' +
      '<td class="v2-workbenchUi__editorAddr">' +
      escapeHtml(addr || "—") +
      "</td>" +
      '<td class="v2-workbenchUi__editorValue">' +
      '<div class="v2-workbenchUi__editorQuick">' +
      '<input type="text" data-field="primary_value" data-original-value="' +
      escapeHtml(primary) +
      '" value="' +
      escapeHtml(primary) +
      '" />' +
      "</div>" +
      '<div class="v2-workbenchUi__editorRaw" hidden>' +
      '<textarea data-field="raw_payload" data-original-value="' +
      escapeHtml(rawJson) +
      '" rows="3">' +
      escapeHtml(rawJson) +
      "</textarea>" +
      "</div>" +
      (row.display_summary
        ? '<div class="v2-workbenchUi__editorSummary">' +
          escapeHtml(row.display_summary) +
          "</div>"
        : "") +
      "</td>" +
      '<td class="v2-workbenchUi__editorActions">' +
      '<button type="button" data-action="toggle-raw" title="Toggle raw JSON edit">Raw</button>' +
      '<button type="button" data-action="save-row" class="v2-workbenchUi__primary" disabled>Save</button>' +
      '<button type="button" data-action="discard-row" disabled>Discard</button>' +
      '<small class="v2-workbenchUi__editorRowStatus" data-role="row-status"></small>' +
      "</td>" +
      "</tr>"
    );
  }

  function flattenDatumGridForEditor(datumGrid) {
    var layers = asList(datumGrid.layers);
    if (layers.length) {
      var matrixRows = [];
      layers.forEach(function (layer) {
        asList(asObject(layer).value_groups).forEach(function (valueGroup) {
          asList(asObject(valueGroup).cells).forEach(function (row) {
            matrixRows.push(row);
          });
        });
      });
      if (matrixRows.length) return matrixRows;
    }
    var groups = asList(datumGrid.groups);
    if (groups.length) {
      var out = [];
      groups.forEach(function (group) {
        asList(asObject(group).items).forEach(function (row) {
          out.push(row);
        });
      });
      return out;
    }
    return asList(datumGrid.rows);
  }

  function computeNextAddress(addresses, defLayer, defGroup) {
    var maxIter = 0;
    addresses.forEach(function (a) {
      var m = /^(\d+)-(\d+)-(\d+)$/.exec(a);
      if (!m) return;
      if (parseInt(m[1], 10) === defLayer && parseInt(m[2], 10) === defGroup) {
        var it = parseInt(m[3], 10);
        if (it > maxIter) maxIter = it;
      }
    });
    return String(defLayer) + "-" + String(defGroup) + "-" + String(maxIter + 1);
  }

  function renderDatumComposer(workspace, surfacePayload) {
    var newDatumForm = asObject(surfacePayload.new_datum_form);
    var docId = asText(newDatumForm.document_id_default);
    if (!asText(newDatumForm.sandbox_id) || !docId) {
      return (
        '<section class="v2-workbenchUi__composer" data-region="datum-composer" data-empty="true">' +
        '<small>Select a datum document to compose new datums.</small>' +
        "</section>"
      );
    }
    var datumGrid = asObject(workspace.datum_grid);
    var existingRows = flattenDatumGridForEditor(datumGrid);
    var existingAddrs = existingRows
      .map(function (r) { return asText(asObject(r).datum_address); })
      .filter(Boolean);
    var composer = asObject(newDatumForm.composer);
    var defaultLayer = 4;
    var defaultGroup = 2;
    if (existingAddrs.length) {
      var firstParse = /^(\d+)-(\d+)-/.exec(existingAddrs[existingAddrs.length - 1]);
      if (firstParse) {
        defaultLayer = parseInt(firstParse[1], 10);
        defaultGroup = parseInt(firstParse[2], 10);
      }
    }
    var nextHint = computeNextAddress(existingAddrs, defaultLayer, defaultGroup);
    var datalistOptions = existingAddrs
      .map(function (a) {
        return '<option value="' + escapeHtml(a) + '"></option>';
      })
      .join("");
    var refRelDefault = asText(composer.default_relation_for_reference_list) || "~";
    return (
      '<section class="v2-workbenchUi__composer" data-region="datum-composer" data-mode="tuple"' +
      ' data-default-layer="' + String(defaultLayer) + '"' +
      ' data-default-group="' + String(defaultGroup) + '"' +
      ' data-ref-rel-default="' + escapeHtml(refRelDefault) + '">' +
      '<header class="v2-workbenchUi__composerHeader">' +
      "<strong>Compose new datum</strong>" +
      '<label>Mode <select data-composer-mode>' +
      '<option value="tuple">Tuple datum</option>' +
      '<option value="reference_list">Reference list (value group 0)</option>' +
      "</select></label>" +
      '<label>Address <input type="text" data-composer-address ' +
      'placeholder="next: ' + escapeHtml(nextHint) + '" ' +
      'pattern="^\\d+-\\d+-\\d+$" /></label>' +
      "</header>" +
      '<fieldset class="v2-workbenchUi__composerSection" data-composer-tuples>' +
      "<legend>Triples (relation + object)</legend>" +
      '<div class="v2-workbenchUi__composerTupleRow">' +
      '<label>Rel <input type="text" data-composer-tuple-rel placeholder="rf.3-1-1 / ~ / …" /></label>' +
      '<label>Obj <input type="text" list="composer-refs-datalist" data-composer-tuple-obj placeholder="object ref" /></label>' +
      '<button type="button" data-composer-tuple-remove title="Remove tuple">×</button>' +
      "</div>" +
      '<button type="button" data-composer-tuple-add>+ Add tuple</button>' +
      "</fieldset>" +
      '<datalist id="composer-refs-datalist">' + datalistOptions + "</datalist>" +
      '<fieldset class="v2-workbenchUi__composerSection" data-composer-magnitudes>' +
      "<legend>Magnitudes (optional)</legend>" +
      '<div class="v2-workbenchUi__composerMagRow">' +
      '<label>Name <input type="text" data-composer-mag-name placeholder="e.g. common_name" /></label>' +
      '<label>Value <input type="text" data-composer-mag-value placeholder="value" /></label>' +
      '<button type="button" data-composer-mag-remove title="Remove magnitude">×</button>' +
      "</div>" +
      '<button type="button" data-composer-mag-add>+ Add magnitude</button>' +
      "</fieldset>" +
      '<footer class="v2-workbenchUi__composerFooter">' +
      '<label>Label <input type="text" data-composer-label placeholder="optional row label" /></label>' +
      '<button type="button" data-composer-create class="v2-workbenchUi__primary">Create</button>' +
      '<button type="button" data-composer-reset>Reset</button>' +
      '<output data-composer-status></output>' +
      "</footer>" +
      "</section>"
    );
  }

  // --- Datum IDE grid (L3) -------------------------------------------------
  // Renders datum_grid.layers as an Excel-esque cell matrix: per layer, per
  // value-group, columns come from the backend column_template (datum_rules),
  // cells are the positional decomposition of each row's raw payload. Read-only
  // in this pass; the raw row editor stays available beneath the grid.
  function _ideCellText(value) {
    if (value == null) return "";
    if (typeof value === "object") {
      try { return JSON.stringify(value); } catch (e) { return String(value); }
    }
    return String(value);
  }
  function _ideTruncate(text, max) {
    text = _ideCellText(text);
    return text.length <= max ? text : text.slice(0, max) + "…";
  }
  function _ideColumnLabel(col) {
    switch (col.role) {
      case "address": return "Datum";
      case "relation": return "↳";
      case "reference": return "Ref " + col.index;
      case "magnitude": return "Mag " + col.index;
      case "references": return "References";
      case "record_key": return col.key || "field";
      case "value": return "Value";
      default: return col.role || "";
    }
  }
  // Map each column onto the row's positional payload. The head (raw[0]) is a
  // flat array whose slots correspond, IN ORDER, to the head-backed columns
  // (address, relation, reference, magnitude); `references` (the RUDI variadic)
  // consumes the rest of the head; record_key/value read the dict/scalar tail.
  // Walking positionally — rather than re-deriving a head index per role — is
  // the one mapping correct across PAIRS / RUDI / RECORD: a RECORD head is
  // [address, "~", ref], so its single reference sits at head[2], not at
  // head[1] as a PAIRS-style 2*index-1 would assume. It also degrades
  // gracefully when a row is shorter than its family's template (extra cells
  // stay blank, since head[slot] is then undefined).
  // Interpreted lens: show the server's lens-decoded value ONLY for the cell the lens
  // actually resolved for — the one whose raw token equals primary_value_token (e.g.
  // the binary title → "brassica"). Gating on resolved_lens != identity AND an exact
  // token match keeps sibling magnitudes (e.g. the node-address "1") raw, which a
  // blanket decode would mangle to "1 bits". lens === "raw" disables it entirely.
  function _ideInterpret(cell, rawText, lens) {
    if (lens === "raw" || !cell) return rawText;
    var resolved = cell.resolved_lens;
    if (!resolved || resolved === "identity") return rawText;
    if (cell.display_value && asText(rawText) === asText(cell.primary_value_token)) {
      return asText(cell.display_value);
    }
    return rawText;
  }
  function _ideRowCells(cell, columns, lens) {
    var raw = cell.raw;
    var head = (raw && Array.isArray(raw) && Array.isArray(raw[0])) ? raw[0] : null;
    var tail = (raw && Array.isArray(raw) && raw.length > 1) ? raw[1] : null;
    var slot = 0;
    return columns.map(function (col) {
      switch (col.role) {
        case "address": {
          var addr = asText(cell.datum_address) || (head ? _ideCellText(head[slot]) : _ideCellText(raw));
          slot += 1;
          return addr;
        }
        case "relation":
        case "reference":
          return head ? _ideCellText(head[slot++]) : "";
        case "magnitude":
          return _ideInterpret(cell, head ? _ideCellText(head[slot++]) : "", lens);
        case "references": {
          var rest = head ? head.slice(slot).map(_ideCellText).join(", ") : "";
          if (head) slot = head.length;
          return rest;
        }
        case "record_key": {
          var rk = (tail && typeof tail === "object" && !Array.isArray(tail)) ? _ideCellText(tail[col.key]) : "";
          return _ideInterpret(cell, rk, lens);
        }
        case "value":
          return _ideInterpret(cell, _ideCellText(raw), lens);
        default:
          return "";
      }
    });
  }
  function _icon(name) { return window.iconImg ? window.iconImg(name) : ""; }
  // A magnitude cell is "refracted" when interpreted mode resolved a non-identity lens for the
  // row's primary token (so _ideRowCells decoded it to the human-readable display_value). The
  // refracted magnitude + its adjacent reference are consolidated into ONE white cell prefixed by
  // the │ℹ│︙│ controls; sibling rows keep their separate ref/mag cells (the per-VG grid isolates).
  function _refractedMagIndex(cell, columns, values, lens) {
    if (lens === "raw" || !cell) return -1;
    var resolved = cell.resolved_lens;
    if (!resolved || resolved === "identity" || !cell.display_value) return -1;
    for (var i = 0; i < columns.length; i++) {
      if (columns[i].role === "magnitude" && asText(values[i]) === asText(cell.display_value)) return i;
    }
    return -1;
  }
  function _refractedCellHtml(cell, value, span) {
    var addr = escapeHtml(asText(cell.datum_address));
    return "<td" + (span ? ' colspan="2"' : "") +
      ' class="v2-ide__cell v2-ide__cell--refracted" data-datum-refracted="1" data-datum-address="' + addr + '">' +
      '<span class="v2-ide__refractCtl">' +
      '<button type="button" class="mc-iconBtn mc-iconBtn--sm v2-ide__refractBtn" data-datum-info data-datum-address="' +
      addr + '" aria-label="Datum information">' + _icon("info") + "</button>" +
      '<button type="button" class="mc-iconBtn mc-iconBtn--sm v2-ide__refractBtn" data-datum-kebab data-datum-address="' +
      addr + '" aria-label="Datum menu">' + _icon("kebab") + "</button></span>" +
      '<span class="v2-ide__refractValue" title="' + escapeHtml(asText(value)) + '">' +
      escapeHtml(_ideTruncate(value, 40)) + "</span></td>";
  }
  function _plainCellHtml(col, full) {
    var shown = _ideTruncate(full, 28);
    return '<td class="v2-ide__cell v2-ide__cell--' + escapeHtml(col.role) + '" title="' +
      escapeHtml(full) + '">' +
      (shown ? escapeHtml(shown) : '<span class="v2-ide__blank">·</span>') + "</td>";
  }
  function renderDatumIdeGridRow(cell, columns, lens) {
    var values = _ideRowCells(cell, columns, lens);
    var magIdx = _refractedMagIndex(cell, columns, values, lens);
    var refIdx = (magIdx > 0 && columns[magIdx - 1] && columns[magIdx - 1].role === "reference") ? magIdx - 1 : -1;
    var tds = [];
    for (var i = 0; i < columns.length; i++) {
      if (i === refIdx && magIdx === i + 1) {
        tds.push(_refractedCellHtml(cell, values[magIdx], true));  // merged reference+magnitude
        i = magIdx;
        continue;
      }
      if (i === magIdx && refIdx === -1) {
        tds.push(_refractedCellHtml(cell, values[magIdx], false)); // lone refracted magnitude
        continue;
      }
      tds.push(_plainCellHtml(columns[i], values[i]));
    }
    return '<tr class="v2-ide__row' + (cell.selected ? " is-selected" : "") +
      '" data-datum-address="' + escapeHtml(asText(cell.datum_address)) + '">' + tds.join("") + "</tr>";
  }
  // The repeated "Datum / Ref n / Mag n" column-label row is replaced by a compact color-key
  // box. Each value group's grid is self-contained (its own column_template), so cells are read
  // by ROLE-COLOR — datum address = medium theme accent, reference = darker grey, magnitude =
  // lighter grey — and the legend names those colors once per group instead of per column.
  var _IDE_ROLE_KEY = {
    address: "datum",
    record_key: "field",
    relation: "↳",
    reference: "ref",
    references: "refs",
    magnitude: "mag",
    value: "val",
  };
  function _ideKeyBox(columns) {
    var seen = {};
    var chips = [];
    columns.forEach(function (col) {
      var role = (col && col.role) || "";
      if (!role || seen[role]) return;
      seen[role] = true;
      chips.push(
        '<span class="v2-ide__keyChip v2-ide__keyChip--' + escapeHtml(role) +
        '"><span class="v2-ide__keySwatch"></span>' +
        escapeHtml(_IDE_ROLE_KEY[role] || role) + "</span>"
      );
    });
    return '<div class="v2-ide__keybox" aria-label="column colour key">' + chips.join("") + "</div>";
  }
  function _ideAddRow(layerId, valueGroup) {
    return '<tr class="v2-ide__addRow"><td colspan="99"><button type="button" ' +
      'class="mc-iconBtn v2-ide__addBtn" data-dov-add="vg" data-layer="' + escapeHtml(String(layerId)) +
      '" data-value-group="' + escapeHtml(String(valueGroup)) + '" aria-label="Add datum to value group">' +
      (window.iconImg ? window.iconImg("add") : "+") + "</button></td></tr>";
  }
  function renderDatumIdeValueGroup(group, lens, layerId) {
    var columns = asList(group.column_template);
    if (!columns.length) columns = [{ role: "address" }];
    var cells = asList(group.cells);
    var vg = asObject(group).value_group;
    var bodyRows = cells.map(function (cell) { return renderDatumIdeGridRow(cell, columns, lens); }).join("");
    return '<section class="v2-ide__valueGroup" data-value-group-id="' +
      escapeHtml(String(vg)) + '">' +
      '<header class="v2-ide__vgHeader">' +
      '<button type="button" class="mc-iconBtn mc-iconBtn--sm v2-ide__collapseBtn" data-ide-collapse="vg" aria-label="Collapse value group">' +
      (window.iconImg ? window.iconImg("up") : "▾") + "</button>" +
      "<h5>" +
      escapeHtml(asText(group.title) || ("Value Group " + vg)) +
      "</h5><small>" + cells.length + " datum" + (cells.length === 1 ? "" : "s") + "</small>" +
      _ideKeyBox(columns) + "</header>" +
      '<div class="v2-tableWrap"><table class="v2-table v2-ide__table"><tbody>' + bodyRows +
      _ideAddRow(layerId, vg) +
      "</tbody></table></div></section>";
  }
  function renderDatumIdeGrid(datumGrid) {
    var layers = asList(datumGrid.layers);
    if (!layers.length) {
      return '<div class="v2-ide" data-region="datum-ide"><p class="v2-workbenchUi__empty">' +
        "No datum rows yet — use the composer above to author the first datum.</p></div>";
    }
    var lens = asText(datumGrid.lens) || "interpreted";
    var sections = layers.map(function (layer) {
      var layerId = String(asObject(layer).layer);
      var vgs = asList(layer.value_groups).map(function (vg) { return renderDatumIdeValueGroup(vg, lens, layerId); }).join("");
      return '<section class="v2-ide__layer" data-layer-id="' + escapeHtml(layerId) + '">' +
        '<header class="v2-ide__layerHeader">' +
        '<button type="button" class="mc-iconBtn mc-iconBtn--sm v2-ide__collapseBtn" data-ide-collapse="layer" aria-label="Collapse layer">' +
        (window.iconImg ? window.iconImg("up") : "▾") + "</button>" +
        "<h4>" +
        escapeHtml(asText(layer.title) || ("Layer " + layerId)) + "</h4></header>" + vgs +
        '<div class="v2-ide__addLayer"><button type="button" class="mc-iconBtn v2-ide__addBtn" ' +
        'data-dov-add="layer" data-layer="' + escapeHtml(layerId) + '" aria-label="Add datum to layer">' +
        (window.iconImg ? window.iconImg("add") : "+") + "<span> add to layer " + escapeHtml(layerId) + "</span></button></div>" +
        "</section>";
    }).join("");
    return '<div class="v2-ide" data-region="datum-ide">' + sections + "</div>";
  }

  function renderDocumentEditor(workspace, surfacePayload, region) {
    var selectedDocument = asObject(workspace.selected_document);
    var datumGrid = asObject(workspace.datum_grid);
    var lens = asText(datumGrid.lens) || "interpreted";
    var docLabel = stripJsonSuffix(
      selectedDocument.canonical_name ||
        selectedDocument.document_name ||
        selectedDocument.document_id ||
        ""
    );
    var docId = asText(selectedDocument.document_id);
    if (!docId) {
      return (
        '<main class="v2-workbenchUi__editor" data-region="document-editor">' +
        '<header class="v2-workbenchUi__editorHeader"><h3>Editor</h3></header>' +
        '<p class="v2-workbenchUi__empty">Select a datum document on the left to begin editing.</p>' +
        "</main>"
      );
    }
    var rows = flattenDatumGridForEditor(datumGrid);
    var gridHtml = renderDatumIdeGrid(datumGrid);
    var tableHtml = rows.length
      ? '<div class="v2-tableWrap"><table class="v2-table v2-workbenchUi__editorTable">' +
        '<thead><tr><th class="v2-workbenchUi__editorAddr">Datum</th><th>' +
        escapeHtml(lens === "raw" ? "Raw Payload" : "Interpreted Value") +
        '</th><th class="v2-workbenchUi__editorActions">Actions</th></tr></thead><tbody>' +
        rows
          .map(function (row, i) {
            return renderDocumentEditorRow(row, i);
          })
          .join("") +
        "</tbody></table></div>"
      : '<p class="v2-workbenchUi__empty">This document has no datum rows yet.</p>';
    // Grid is the primary view; the proven raw row-editor stays available under a
    // disclosure (keeps bindDocumentEditor + editing intact — no regression).
    var bodyHtml =
      gridHtml +
      '<details class="v2-ide__rowEditor"' + (rows.length ? "" : " open") + ">" +
      "<summary>Row editor — edit raw datum payloads</summary>" +
      tableHtml +
      "</details>";
    return (
      '<main class="v2-workbenchUi__editor" data-region="document-editor">' +
      '<header class="v2-workbenchUi__editorHeader">' +
      '<button type="button" class="mc-iconBtn v2-workbenchUi__editDoc" data-dov-edit-doc aria-label="New datum">' +
      (window.iconImg ? window.iconImg("edit") : "✎") + "</button>" +
      "<h3>" +
      escapeHtml(shortDocumentLabel(docLabel) || docLabel || docId) +
      "</h3>" +
      "<small>" +
      escapeHtml(docId) +
      "</small></header>" +
      bodyHtml +
      "</main>"
    );
  }

  function renderWorkbenchSurface(surfacePayload, region) {
    var workspace = asObject(surfacePayload.workspace);
    // TASK-interface-panel-migration: the in-workbench sandbox toggle bar was removed —
    // sandbox switching now lives solely in the control-panel sandbox selector.
    return (
      '<div class="v2-workbenchUi__trifecta" data-region="workbench-trifecta">' +
      '<div class="v2-workbenchUi__columns">' +
      renderDocumentColumn(workspace, surfacePayload) +
      renderDocumentEditor(workspace, surfacePayload, region) +
      "</div></div>"
    );
  }

  function bindDocumentColumn(ctx, target, workspace, surfacePayload) {
    var documents = asList(asObject(workspace.document_table).rows);

    function loadRequest(request) {
      if (!request || typeof ctx.loadShell !== "function") return;
      ctx.loadShell(request);
    }

    Array.prototype.forEach.call(
      target.querySelectorAll("li[data-workbench-document-index]"),
      function (node) {
        var index = Number(node.getAttribute("data-workbench-document-index"));
        if (Number.isNaN(index) || index < 0 || index >= documents.length) return;
        var item = documents[index] || {};
        node.addEventListener("click", function () {
          loadRequest(item.shell_request);
        });
        node.addEventListener("keydown", function (event) {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            loadRequest(item.shell_request);
            return;
          }
          if (event.key === "ArrowDown" && index + 1 < documents.length) {
            event.preventDefault();
            loadRequest((documents[index + 1] || {}).shell_request);
            return;
          }
          if (event.key === "ArrowUp" && index - 1 >= 0) {
            event.preventDefault();
            loadRequest((documents[index - 1] || {}).shell_request);
          }
        });
      }
    );

    var newForm = asObject(surfacePayload.new_source_document_form);
    if (!asText(newForm.sandbox_id)) return;
    var openBtn = target.querySelector('[data-action="open-new-document"]');
    var form = target.querySelector('form[data-form="new-document"]');
    var cancelBtn = target.querySelector('[data-action="cancel-new-document"]');
    var statusEl = form && form.querySelector('[data-role="status"]');
    if (!openBtn || !form) return;

    function showForm() {
      form.hidden = false;
      var input = form.querySelector('input[name="document_name"]');
      if (input) {
        input.value = "";
        input.focus();
      }
      if (statusEl) {
        statusEl.hidden = true;
        statusEl.textContent = "";
      }
    }
    function hideForm() {
      form.hidden = true;
    }
    function setStatus(msg) {
      if (!statusEl) return;
      statusEl.hidden = !msg;
      statusEl.textContent = msg || "";
    }

    openBtn.addEventListener("click", showForm);
    if (cancelBtn) cancelBtn.addEventListener("click", hideForm);

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var input = form.querySelector('input[name="document_name"]');
      var documentName = input ? asText(input.value) : "";
      if (!documentName) {
        setStatus("Name is required.");
        return;
      }
      if (input && !input.checkValidity()) {
        setStatus("Enter a document title.");
        return;
      }
      var submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;
      setStatus("Creating…");

      var body = {
        schema: "mycite.v2.portal.mutations.stage.request.v1",
        target_authority: asText(newForm.target_authority) || "datum_workbench",
        sandbox_id: asText(newForm.sandbox_id),
        msn_id: asText(newForm.msn_id_default),
        document_name: documentName,
        canonical_name: documentName,
        operation: "create_document",
      };

      stageThenApply(
        body,
        asText(newForm.endpoint_stage),
        asText(newForm.endpoint_apply)
      )
        .then(function (applied) {
          setStatus("");
          hideForm();
          var newDocId = asText(
            (applied && applied.preview && applied.preview.document_id) ||
              (applied && applied.document_id) ||
              (applied && applied.applied_document_id) ||
              ""
          );
          var envelope = ctx.getEnvelope && ctx.getEnvelope();
          var nextQuery = Object.assign(
            {},
            (envelope && envelope.surface_query) || {}
          );
          if (newDocId) {
            nextQuery.document = newDocId;
            nextQuery.mode = "datums";
          }
          ctx.loadShell({
            schema: "mycite.v2.portal.shell.request.v1",
            requested_surface_id: (envelope && envelope.surface_id) || "",
            surface_query: nextQuery,
          });
        })
        .catch(function (err) {
          if (submitBtn) submitBtn.disabled = false;
          setStatus(asText(err && err.message) || "Create failed.");
        });
    });
  }

  function stageThenApply(body, stageEndpoint, applyEndpoint) {
    stageEndpoint = stageEndpoint || "/portal/api/v2/mutations/stage";
    applyEndpoint = applyEndpoint || "/portal/api/v2/mutations/apply";
    function readResponse(r) {
      return r.json().then(
        function (j) { return { status: r.status, body: j }; },
        function () { return { status: r.status, body: {} }; }
      );
    }
    function fail(stage, out) {
      var detail =
        (out.body && out.body.error && (out.body.error.message || out.body.error)) ||
        (out.body && (out.body.detail || out.body.message)) ||
        "HTTP " + out.status;
      throw new Error(stage + " failed: " + detail);
    }
    return fetch(stageEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      credentials: "same-origin",
    })
      .then(readResponse)
      .then(function (out) {
        if (out.status < 200 || out.status >= 300 || (out.body && out.body.ok === false)) {
          fail("stage", out);
        }
        return fetch(applyEndpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          credentials: "same-origin",
        });
      })
      .then(readResponse)
      .then(function (out) {
        if (out.status < 200 || out.status >= 300 || (out.body && out.body.ok === false)) {
          fail("apply", out);
        }
        return out.body || {};
      });
  }

  function applyPrimaryPatch(rawJson, primaryKeyPath, newValue) {
    var raw;
    try {
      raw = JSON.parse(rawJson || "null");
    } catch (e) {
      throw new Error("Row's raw payload is not parseable JSON — use Raw mode.");
    }
    if (!Array.isArray(raw) || raw.length < 2) {
      throw new Error("Row's raw shape is not [triple, second] — use Raw mode.");
    }
    var second = raw[1];
    var path = primaryKeyPath || "labels.0";
    var dot = path.indexOf(".");
    var prefix = dot >= 0 ? path.slice(0, dot) : path;
    var key = dot >= 0 ? path.slice(dot + 1) : "";
    if (prefix === "labels") {
      if (!Array.isArray(second)) {
        throw new Error("Row's labels slot is not a list — use Raw mode.");
      }
      var idx = parseInt(key, 10);
      if (isNaN(idx) || idx < 0) idx = 0;
      while (second.length <= idx) second.push("");
      second[idx] = newValue;
    } else if (prefix === "magnitudes") {
      if (!second || typeof second !== "object" || Array.isArray(second)) {
        throw new Error("Row's magnitudes slot is not a dict — use Raw mode.");
      }
      if (!key) {
        throw new Error("Primary magnitude key missing — use Raw mode.");
      }
      second[key] = newValue;
    } else {
      throw new Error("Unknown primary key path '" + prefix + "' — use Raw mode.");
    }
    return raw;
  }

  function bindDocumentEditor(ctx, target, workspace, surfacePayload) {
    var newDatumForm = asObject(surfacePayload.new_datum_form);
    var stageEndpoint = asText(newDatumForm.endpoint_stage) || "/portal/api/v2/mutations/stage";
    var applyEndpoint = asText(newDatumForm.endpoint_apply) || "/portal/api/v2/mutations/apply";
    var sandboxId = asText(newDatumForm.sandbox_id);
    var documentId = asText(newDatumForm.document_id_default);
    var targetAuthority = asText(newDatumForm.target_authority) || "datum_workbench";

    function rowQuickInput(rowEl) {
      return rowEl.querySelector('.v2-workbenchUi__editorQuick input[data-field="primary_value"]');
    }
    function rowRawTextarea(rowEl) {
      return rowEl.querySelector('.v2-workbenchUi__editorRaw textarea[data-field="raw_payload"]');
    }
    function rowQuickContainer(rowEl) {
      return rowEl.querySelector('.v2-workbenchUi__editorQuick');
    }
    function rowRawContainer(rowEl) {
      return rowEl.querySelector('.v2-workbenchUi__editorRaw');
    }
    function setRowStatus(rowEl, text, state) {
      var el = rowEl.querySelector('[data-role="row-status"]');
      if (!el) return;
      el.textContent = text || "";
      if (state) el.setAttribute("data-state", state);
      else el.removeAttribute("data-state");
    }
    function getMode(rowEl) {
      return rowEl.getAttribute("data-row-edit-mode") || "quick";
    }
    function setMode(rowEl, mode) {
      rowEl.setAttribute("data-row-edit-mode", mode);
      var quick = rowQuickContainer(rowEl);
      var raw = rowRawContainer(rowEl);
      if (quick) quick.hidden = mode !== "quick";
      if (raw) raw.hidden = mode !== "raw";
    }
    function updateDirty(rowEl) {
      var mode = getMode(rowEl);
      var saveBtn = rowEl.querySelector('[data-action="save-row"]');
      var discardBtn = rowEl.querySelector('[data-action="discard-row"]');
      var dirty = false;
      if (mode === "quick") {
        var input = rowQuickInput(rowEl);
        if (input) dirty = input.value !== (input.getAttribute("data-original-value") || "");
      } else {
        var textarea = rowRawTextarea(rowEl);
        if (textarea) dirty = textarea.value !== (textarea.getAttribute("data-original-value") || "");
      }
      if (saveBtn) saveBtn.disabled = !dirty;
      if (discardBtn) discardBtn.disabled = !dirty;
    }

    function saveRow(rowEl) {
      var address = rowEl.getAttribute("data-datum-address") || "";
      if (!address) {
        setRowStatus(rowEl, "Missing datum address.", "error");
        return;
      }
      if (!sandboxId || !documentId) {
        setRowStatus(rowEl, "Editor is missing sandbox or document context.", "error");
        return;
      }
      var mode = getMode(rowEl);
      var lens = rowEl.getAttribute("data-row-lens") || "";
      var operation = "update_row_raw";
      var payloadText = null;
      var displayValue = null;
      try {
        if (mode === "raw") {
          var textarea = rowRawTextarea(rowEl);
          payloadText = textarea ? textarea.value : "";
          JSON.parse(payloadText);  // throw if invalid JSON before staging
        } else if (lens === "binary_text") {
          // Title edit in ASCII: the server re-encodes to the canonical binary
          // (encode_label) and syncs the head magnitude + tail label, so the quick
          // value is sent as a display_value, not a raw-payload patch.
          var titleInput = rowQuickInput(rowEl);
          operation = "update_primary_value";
          displayValue = titleInput ? titleInput.value : "";
        } else {
          var input = rowQuickInput(rowEl);
          var quickValue = input ? input.value : "";
          var originalRawJson = rowEl.getAttribute("data-row-raw") || "";
          var primaryKeyPath = rowEl.getAttribute("data-row-primary-key") || "";
          var patched = applyPrimaryPatch(originalRawJson, primaryKeyPath, quickValue);
          payloadText = JSON.stringify(patched);
        }
      } catch (err) {
        setRowStatus(rowEl, String(err && err.message ? err.message : err), "error");
        return;
      }
      var saveBtn = rowEl.querySelector('[data-action="save-row"]');
      var discardBtn = rowEl.querySelector('[data-action="discard-row"]');
      if (saveBtn) saveBtn.disabled = true;
      if (discardBtn) discardBtn.disabled = true;
      setRowStatus(rowEl, "Saving…", "");
      var body = {
        schema: "mycite.v2.portal.mutations.stage.request.v1",
        target_authority: targetAuthority,
        sandbox_id: sandboxId,
        document_id: documentId,
        datum_address: address,
        operation: operation,
      };
      if (payloadText != null) body.payload_text = payloadText;
      if (displayValue != null) body.display_value = displayValue;
      stageThenApply(body, stageEndpoint, applyEndpoint)
        .then(function () {
          setRowStatus(rowEl, "Saved.", "ok");
          var envelope = ctx.getEnvelope && ctx.getEnvelope();
          if (envelope) {
            ctx.loadShell({
              schema: "mycite.v2.portal.shell.request.v1",
              requested_surface_id: envelope.surface_id,
              surface_query: envelope.surface_query || {},
            });
          }
        })
        .catch(function (err) {
          setRowStatus(rowEl, String(err && err.message ? err.message : err), "error");
          if (saveBtn) saveBtn.disabled = false;
          if (discardBtn) discardBtn.disabled = false;
        });
    }

    function discardRow(rowEl) {
      var input = rowQuickInput(rowEl);
      if (input) input.value = input.getAttribute("data-original-value") || "";
      var textarea = rowRawTextarea(rowEl);
      if (textarea) textarea.value = textarea.getAttribute("data-original-value") || "";
      updateDirty(rowEl);
      setRowStatus(rowEl, "", "");
    }

    Array.prototype.forEach.call(
      target.querySelectorAll("tr.v2-workbenchUi__editorRow"),
      function (rowEl) {
        var input = rowQuickInput(rowEl);
        if (input) {
          input.addEventListener("input", function () {
            updateDirty(rowEl);
          });
        }
        var textarea = rowRawTextarea(rowEl);
        if (textarea) {
          textarea.addEventListener("input", function () {
            updateDirty(rowEl);
          });
        }
        var toggleBtn = rowEl.querySelector('[data-action="toggle-raw"]');
        if (toggleBtn) {
          toggleBtn.addEventListener("click", function () {
            var nextMode = getMode(rowEl) === "raw" ? "quick" : "raw";
            setMode(rowEl, nextMode);
            updateDirty(rowEl);
          });
        }
        var saveBtn = rowEl.querySelector('[data-action="save-row"]');
        if (saveBtn) {
          saveBtn.addEventListener("click", function () {
            saveRow(rowEl);
          });
        }
        var discardBtn = rowEl.querySelector('[data-action="discard-row"]');
        if (discardBtn) {
          discardBtn.addEventListener("click", function () {
            discardRow(rowEl);
          });
        }
      }
    );
  }

  function bindDatumComposer(ctx, target, workspace, surfacePayload) {
    var composerEl = target.querySelector('[data-region="datum-composer"]');
    if (!composerEl) return;
    if (composerEl.getAttribute("data-empty") === "true") return;
    var newDatumForm = asObject(surfacePayload.new_datum_form);
    var sandboxId = asText(newDatumForm.sandbox_id);
    var documentId = asText(newDatumForm.document_id_default);
    var stageEndpoint = asText(newDatumForm.endpoint_stage) || "/portal/api/v2/mutations/stage";
    var applyEndpoint = asText(newDatumForm.endpoint_apply) || "/portal/api/v2/mutations/apply";
    var targetAuthority = asText(newDatumForm.target_authority) || "datum_workbench";
    var operation = asText(newDatumForm.operation) || "insert_datum";
    var modeSelect = composerEl.querySelector('[data-composer-mode]');
    var addrInput = composerEl.querySelector('[data-composer-address]');
    var tuplesEl = composerEl.querySelector('[data-composer-tuples]');
    var magsEl = composerEl.querySelector('[data-composer-magnitudes]');
    var labelInput = composerEl.querySelector('[data-composer-label]');
    var statusEl = composerEl.querySelector('[data-composer-status]');
    var createBtn = composerEl.querySelector('[data-composer-create]');
    var resetBtn = composerEl.querySelector('[data-composer-reset]');
    var defaultLayer = parseInt(composerEl.getAttribute("data-default-layer") || "4", 10);
    var defaultGroup = parseInt(composerEl.getAttribute("data-default-group") || "2", 10);
    var refRelDefault = composerEl.getAttribute("data-ref-rel-default") || "~";

    function existingAddresses() {
      var grid = asObject(workspace.datum_grid);
      return flattenDatumGridForEditor(grid)
        .map(function (r) { return asText(asObject(r).datum_address); })
        .filter(Boolean);
    }
    function setStatus(text, state) {
      if (!statusEl) return;
      statusEl.textContent = text || "";
      if (state) statusEl.setAttribute("data-state", state);
      else statusEl.removeAttribute("data-state");
    }
    function refreshAddressPlaceholder() {
      var mode = modeSelect ? modeSelect.value : "tuple";
      var layer = mode === "reference_list" ? 0 : defaultLayer;
      var group = mode === "reference_list" ? 0 : defaultGroup;
      var hint = computeNextAddress(existingAddresses(), layer, group);
      if (addrInput) addrInput.placeholder = "next: " + hint;
    }
    function applyMode(mode) {
      composerEl.setAttribute("data-mode", mode);
      if (magsEl) magsEl.hidden = mode === "reference_list";
      if (mode === "reference_list") {
        Array.prototype.forEach.call(
          composerEl.querySelectorAll('[data-composer-tuple-rel]'),
          function (i) { if (!i.value) i.value = refRelDefault; }
        );
      }
      refreshAddressPlaceholder();
    }
    if (modeSelect) {
      modeSelect.addEventListener("change", function () {
        applyMode(modeSelect.value);
      });
    }
    refreshAddressPlaceholder();

    composerEl.addEventListener("click", function (event) {
      var t = event.target;
      if (!t) return;
      if (t.matches('[data-composer-tuple-add]')) {
        event.preventDefault();
        var row = document.createElement("div");
        row.className = "v2-workbenchUi__composerTupleRow";
        row.innerHTML =
          '<label>Rel <input type="text" data-composer-tuple-rel placeholder="rf.3-1-1 / ~ / …" /></label>' +
          '<label>Obj <input type="text" list="composer-refs-datalist" data-composer-tuple-obj placeholder="object ref" /></label>' +
          '<button type="button" data-composer-tuple-remove title="Remove tuple">×</button>';
        if (modeSelect && modeSelect.value === "reference_list") {
          row.querySelector('[data-composer-tuple-rel]').value = refRelDefault;
        }
        t.parentNode.insertBefore(row, t);
      } else if (t.matches('[data-composer-tuple-remove]')) {
        event.preventDefault();
        var rows = composerEl.querySelectorAll('.v2-workbenchUi__composerTupleRow');
        if (rows.length > 1 && t.parentNode) t.parentNode.parentNode.removeChild(t.parentNode);
      } else if (t.matches('[data-composer-mag-add]')) {
        event.preventDefault();
        var mrow = document.createElement("div");
        mrow.className = "v2-workbenchUi__composerMagRow";
        mrow.innerHTML =
          '<label>Name <input type="text" data-composer-mag-name placeholder="e.g. common_name" /></label>' +
          '<label>Value <input type="text" data-composer-mag-value placeholder="value" /></label>' +
          '<button type="button" data-composer-mag-remove title="Remove magnitude">×</button>';
        t.parentNode.insertBefore(mrow, t);
      } else if (t.matches('[data-composer-mag-remove]')) {
        event.preventDefault();
        if (t.parentNode && t.parentNode.parentNode) {
          t.parentNode.parentNode.removeChild(t.parentNode);
        }
      }
    });

    if (resetBtn) {
      resetBtn.addEventListener("click", function () {
        Array.prototype.forEach.call(
          composerEl.querySelectorAll('input'),
          function (i) { i.value = ""; }
        );
        var trows = composerEl.querySelectorAll('.v2-workbenchUi__composerTupleRow');
        for (var i = trows.length - 1; i > 0; i--) {
          trows[i].parentNode.removeChild(trows[i]);
        }
        var mrows = composerEl.querySelectorAll('.v2-workbenchUi__composerMagRow');
        for (var j = mrows.length - 1; j > 0; j--) {
          mrows[j].parentNode.removeChild(mrows[j]);
        }
        applyMode(modeSelect ? modeSelect.value : "tuple");
        setStatus("");
      });
    }

    if (createBtn) {
      createBtn.addEventListener("click", function () {
        var mode = modeSelect ? modeSelect.value : "tuple";
        var typedAddr = addrInput ? addrInput.value.trim() : "";
        var addrPlaceholder = addrInput ? addrInput.placeholder || "" : "";
        var address = typedAddr || addrPlaceholder.replace(/^next:\s*/, "");
        if (!/^\d+-\d+-\d+$/.test(address)) {
          setStatus("Address must be in the form layer-group-iteration (e.g. 4-2-3).", "error");
          return;
        }
        var tuples = [];
        Array.prototype.forEach.call(
          composerEl.querySelectorAll('.v2-workbenchUi__composerTupleRow'),
          function (row) {
            var rel = ((row.querySelector('[data-composer-tuple-rel]') || {}).value || "").trim();
            var obj = ((row.querySelector('[data-composer-tuple-obj]') || {}).value || "").trim();
            if (rel || obj) tuples.push([rel, obj]);
          }
        );
        if (!tuples.length) {
          setStatus("At least one tuple is required.", "error");
          return;
        }
        var labelText = labelInput ? labelInput.value.trim() : "";
        var secondPart;
        if (mode === "reference_list") {
          secondPart = labelText ? [labelText] : [];
        } else {
          var mags = {};
          Array.prototype.forEach.call(
            composerEl.querySelectorAll('.v2-workbenchUi__composerMagRow'),
            function (row) {
              var n = ((row.querySelector('[data-composer-mag-name]') || {}).value || "").trim();
              var v = ((row.querySelector('[data-composer-mag-value]') || {}).value || "").trim();
              if (n) mags[n] = v;
            }
          );
          var magKeys = Object.keys(mags);
          if (magKeys.length) {
            secondPart = mags;
          } else if (labelText) {
            secondPart = [labelText];
          } else {
            secondPart = [];
          }
        }
        var firstPart = [address];
        tuples.forEach(function (pair) {
          firstPart.push(pair[0], pair[1]);
        });
        var raw = [firstPart, secondPart];
        createBtn.disabled = true;
        setStatus("Creating " + address + "…", "");
        var body = {
          schema: "mycite.v2.portal.mutations.stage.request.v1",
          target_authority: targetAuthority,
          sandbox_id: sandboxId,
          document_id: documentId,
          datum_address: address,
          target_address: address,
          operation: operation,
          payload_text: JSON.stringify(raw),
        };
        stageThenApply(body, stageEndpoint, applyEndpoint)
          .then(function () {
            setStatus("Created " + address + ".", "ok");
            var envelope = ctx.getEnvelope && ctx.getEnvelope();
            if (envelope) {
              var nextQuery = Object.assign({}, envelope.surface_query || {});
              nextQuery.document = documentId;
              ctx.loadShell({
                schema: "mycite.v2.portal.shell.request.v1",
                requested_surface_id: envelope.surface_id,
                surface_query: nextQuery,
              });
            } else {
              createBtn.disabled = false;
            }
          })
          .catch(function (err) {
            setStatus(String(err && err.message ? err.message : err), "error");
            createBtn.disabled = false;
          });
      });
    }
  }

  // ===== Datum-editing overlay (#portalDatumOverlay) =====
  // A non-tool overlay opened from a refracted cell (ℹ / kebab / merged cell) or a value-group /
  // layer add-row. DENOTATION denotes/edits a datum (insert_datum / update_row_raw / delete_datum
  // via the existing mutation endpoints); INFORMATION shows the hyphae abstraction path; MEDIATION
  // is reserved. New datum → DENOTATION default (INFORMATION/MEDIATION greyed); existing → INFORMATION.
  var _dov = { ctx: null, documentId: "", sandboxId: "agro_erp", address: "", layer: null,
    valueGroup: null, mode: "create", raw: null, activeTab: "denotation", bound: false };
  function _dovEl() { return document.getElementById("portalDatumOverlay"); }
  function _dovExisting() { return _dov.mode !== "create"; }

  function openDatumOverlay(opts) {
    opts = opts || {};
    var ov = _dovEl();
    if (!ov) return;
    _dov.ctx = opts.ctx || _dov.ctx;
    _dov.workspaceRef = opts.workspace || _dov.workspaceRef;
    _dov.documentId = asText(opts.documentId) || _dov.documentId;
    _dov.sandboxId = asText(opts.sandboxId) || _dov.sandboxId || "agro_erp";
    _dov.address = asText(opts.address);
    _dov.layer = opts.layer != null ? opts.layer : null;
    _dov.valueGroup = opts.valueGroup != null ? opts.valueGroup : null;
    _dov.raw = opts.raw || null;
    _dov.mode = opts.mode || (_dov.address ? "edit" : "create");
    _dov.activeTab = opts.activeTab || (_dov.mode === "create" ? "denotation" : "information");
    _bindDatumOverlayOnce();
    _renderDatumOverlay();
    ov.hidden = false;
    ov.setAttribute("aria-hidden", "false");
    if (document.body) document.body.classList.add("is-modal-open");
    try { window.history.pushState({ myciteDatumOverlay: _dov.address || "new" }, "", window.location.href); _dov.pushed = true; } catch (e) { _dov.pushed = false; }
  }
  function closeDatumOverlay(popHistory) {
    var ov = _dovEl();
    if (!ov || ov.hidden) return;
    ov.hidden = true;
    ov.setAttribute("aria-hidden", "true");
    if (document.body && !document.body.querySelector(".ide-toolOverlay:not([hidden])")) {
      document.body.classList.remove("is-modal-open");
    }
    var c = ov.querySelector("[data-datum-overlay-content]");
    if (c) c.innerHTML = "";
    if (popHistory && _dov.pushed) { _dov.pushed = false; try { window.history.back(); } catch (e) {} }
  }
  function _bindDatumOverlayOnce() {
    if (_dov.bound) return;
    _dov.bound = true;
    document.addEventListener("click", function (ev) {
      var t = ev.target;
      if (!t || !t.closest) return;
      if (t.closest("[data-datum-overlay-close]") || t.closest("[data-datum-overlay-dismiss]")) {
        closeDatumOverlay(true);
      }
    });
    document.addEventListener("keydown", function (ev) {
      var ov = _dovEl();
      if ((ev.key === "Escape" || ev.key === "Esc") && ov && !ov.hidden) closeDatumOverlay(true);
    });
    window.addEventListener("popstate", function () {
      var ov = _dovEl();
      if (ov && !ov.hidden) closeDatumOverlay(false);
    });
  }
  function _renderDatumOverlay() {
    var ov = _dovEl();
    if (!ov) return;
    var titleNode = ov.querySelector("[data-datum-overlay-title]");
    if (titleNode) {
      titleNode.textContent = _dov.mode === "create"
        ? ("New datum" + (_dov.layer != null ? " · L" + _dov.layer + (_dov.valueGroup != null ? "·VG" + _dov.valueGroup : "") : ""))
        : ("Datum " + _dov.address);
    }
    var tabsNode = ov.querySelector("[data-datum-overlay-tabs]");
    var TABS = [
      { id: "denotation", label: "DENOTATION", enabled: true },
      { id: "information", label: "INFORMATION", enabled: _dovExisting() },
      { id: "mediation", label: "MEDIATION", enabled: _dovExisting() },
    ];
    if (tabsNode) {
      tabsNode.innerHTML = TABS.map(function (tb) {
        return '<button type="button" class="ide-datumOverlay__tab' + (tb.id === _dov.activeTab ? " is-active" : "") +
          '" role="tab" data-datum-tab="' + tb.id + '"' + (tb.enabled ? "" : " disabled") + ">" + tb.label + "</button>";
      }).join("");
      tabsNode.onclick = function (ev) {
        var btn = ev.target && ev.target.closest ? ev.target.closest("[data-datum-tab]") : null;
        if (!btn || btn.disabled) return;
        _dov.activeTab = btn.getAttribute("data-datum-tab");
        _renderDatumOverlay();
      };
    }
    var content = ov.querySelector("[data-datum-overlay-content]");
    if (!content) return;
    if (_dov.activeTab === "information") { _dovRenderInformation(content); return; }
    if (_dov.activeTab === "mediation") { content.innerHTML = '<div class="v2-mediation">Mediation — reserved for a later session.</div>'; return; }
    _dovRenderDenotation(content);
  }
  function _dovTupleRowHtml(rel, obj) {
    return '<div class="v2-denote__row v2-denote__tuple">' +
      '<input type="text" data-dov-rel placeholder="rf.3-1-1 / ~" value="' + escapeHtml(asText(rel)) + '" />' +
      '<input type="text" data-dov-obj placeholder="object ref" value="' + escapeHtml(asText(obj)) + '" />' +
      '<button type="button" class="v2-btn" data-dov-tuple-remove title="Remove">×</button></div>';
  }
  function _dovMagRowHtml(name, val) {
    return '<div class="v2-denote__row v2-denote__mag">' +
      '<input type="text" data-dov-mag-name placeholder="name" value="' + escapeHtml(asText(name)) + '" />' +
      '<input type="text" data-dov-mag-value placeholder="value" value="' + escapeHtml(asText(val)) + '" />' +
      '<button type="button" class="v2-btn" data-dov-mag-remove title="Remove">×</button></div>';
  }
  function _dovSeedFromRaw(raw) {
    var head = (raw && Array.isArray(raw) && Array.isArray(raw[0])) ? raw[0] : null;
    var tail = (raw && Array.isArray(raw) && raw.length > 1) ? raw[1] : null;
    var tuples = [];
    if (head) {
      for (var i = 1; i + 1 < head.length; i += 2) tuples.push([head[i], head[i + 1]]);
    }
    var mags = [];
    var label = "";
    if (tail && typeof tail === "object" && !Array.isArray(tail)) {
      Object.keys(tail).forEach(function (k) { mags.push([k, tail[k]]); });
    } else if (Array.isArray(tail) && tail.length) {
      label = asText(tail[0]);
    }
    return { tuples: tuples, mags: mags, label: label };
  }
  function _dovSeedAddress() {
    if (_dov.address) return _dov.address;
    var grid = asObject(asObject(_dov.workspaceRef).datum_grid);
    var existing = (typeof flattenDatumGridForEditor === "function" ? flattenDatumGridForEditor(grid) : [])
      .map(function (r) { return asText(asObject(r).datum_address); }).filter(Boolean);
    var layer = _dov.layer != null ? _dov.layer : 4;
    var group = _dov.valueGroup != null ? _dov.valueGroup : 2;
    if (typeof computeNextAddress === "function") return computeNextAddress(existing, layer, group);
    return layer + "-" + group + "-1";
  }
  function _dovRenderDenotation(content) {
    var seed = _dov.raw ? _dovSeedFromRaw(_dov.raw) : { tuples: [["", ""]], mags: [], label: "" };
    if (!seed.tuples.length) seed.tuples = [["", ""]];
    var addr = _dovExisting() ? _dov.address : _dovSeedAddress();
    var html =
      '<div class="v2-denote__field"><label>Datum address (layer-group-iteration)</label>' +
      '<input type="text" data-dov-address value="' + escapeHtml(addr) + '" placeholder="4-2-3" /></div>' +
      '<div class="v2-denote__sectionLabel">References (relation · object)</div>' +
      '<div data-dov-tuples>' + seed.tuples.map(function (p) { return _dovTupleRowHtml(p[0], p[1]); }).join("") + "</div>" +
      '<button type="button" class="v2-btn" data-dov-tuple-add>+ reference</button>' +
      '<div class="v2-denote__sectionLabel">Magnitudes (name · value)</div>' +
      '<div data-dov-mags>' + seed.mags.map(function (m) { return _dovMagRowHtml(m[0], m[1]); }).join("") + "</div>" +
      '<button type="button" class="v2-btn" data-dov-mag-add>+ magnitude</button>' +
      '<div class="v2-denote__field" style="margin-top:10px"><label>Label (optional)</label>' +
      '<input type="text" data-dov-label value="' + escapeHtml(seed.label) + '" placeholder="human label" /></div>' +
      '<div class="v2-denote__actions">' +
      (_dovExisting()
        ? '<button type="button" class="v2-btn v2-btn--primary" data-dov-save>Save</button>' +
          '<button type="button" class="v2-btn v2-btn--danger" data-dov-delete>Delete</button>'
        : '<button type="button" class="v2-btn v2-btn--primary" data-dov-create>Create datum</button>') +
      "</div><div class=\"v2-denote__status\" data-dov-status></div>";
    content.innerHTML = html;
    _bindDenotation(content);
  }
  function _bindDenotation(content) {
    content.onclick = function (ev) {
      var t = ev.target;
      if (!t || !t.matches) return;
      if (t.matches("[data-dov-tuple-add]")) { var tw = content.querySelector("[data-dov-tuples]"); tw.insertAdjacentHTML("beforeend", _dovTupleRowHtml("", "")); }
      else if (t.matches("[data-dov-tuple-remove]")) { var tr = t.closest(".v2-denote__tuple"); if (tr) tr.parentNode.removeChild(tr); }
      else if (t.matches("[data-dov-mag-add]")) { var mw = content.querySelector("[data-dov-mags]"); mw.insertAdjacentHTML("beforeend", _dovMagRowHtml("", "")); }
      else if (t.matches("[data-dov-mag-remove]")) { var mr = t.closest(".v2-denote__mag"); if (mr) mr.parentNode.removeChild(mr); }
      else if (t.matches("[data-dov-create]")) { _dovSubmit("insert_datum", content); }
      else if (t.matches("[data-dov-save]")) { _dovSubmit("update_row_raw", content); }
      else if (t.matches("[data-dov-delete]")) { _dovSubmit("delete_datum", content); }
    };
  }
  function _dovStatus(content, text, state) {
    var s = content.querySelector("[data-dov-status]");
    if (!s) return;
    s.textContent = text || "";
    if (state) s.setAttribute("data-state", state); else s.removeAttribute("data-state");
  }
  function _dovSubmit(operation, content) {
    var address = asText((content.querySelector("[data-dov-address]") || {}).value).trim();
    if (!/^\d+-\d+-\d+$/.test(address)) { _dovStatus(content, "Address must be layer-group-iteration (e.g. 4-2-3).", "error"); return; }
    var raw;
    if (operation === "delete_datum") {
      raw = _dov.raw || [[address], []];
    } else {
      var first = [address];
      Array.prototype.forEach.call(content.querySelectorAll(".v2-denote__tuple"), function (row) {
        var rel = asText((row.querySelector("[data-dov-rel]") || {}).value).trim();
        var obj = asText((row.querySelector("[data-dov-obj]") || {}).value).trim();
        if (rel || obj) first.push(rel, obj);
      });
      if (first.length < 2) { _dovStatus(content, "At least one reference is required.", "error"); return; }
      var mags = {};
      Array.prototype.forEach.call(content.querySelectorAll(".v2-denote__mag"), function (row) {
        var n = asText((row.querySelector("[data-dov-mag-name]") || {}).value).trim();
        var v = asText((row.querySelector("[data-dov-mag-value]") || {}).value).trim();
        if (n) mags[n] = v;
      });
      var label = asText((content.querySelector("[data-dov-label]") || {}).value).trim();
      var second = Object.keys(mags).length ? mags : (label ? [label] : []);
      raw = [first, second];
    }
    _dovStatus(content, (operation === "delete_datum" ? "Deleting " : "Saving ") + address + "…", "");
    var body = {
      schema: "mycite.v2.portal.mutations.stage.request.v1",
      target_authority: "datum_workbench",
      sandbox_id: _dov.sandboxId,
      document_id: _dov.documentId,
      datum_address: address,
      target_address: address,
      operation: operation,
      payload_text: JSON.stringify(raw),
    };
    if (typeof stageThenApply !== "function") { _dovStatus(content, "Mutation pipeline unavailable.", "error"); return; }
    stageThenApply(body, "/portal/api/v2/mutations/stage", "/portal/api/v2/mutations/apply")
      .then(function () { closeDatumOverlay(true); _dovRefreshShell(); })
      .catch(function (err) { _dovStatus(content, asText(err && err.message ? err.message : err), "error"); });
  }
  function _dovRefreshShell() {
    var ctx = _dov.ctx;
    if (!ctx || typeof ctx.loadShell !== "function") return;
    var envelope = ctx.getEnvelope && ctx.getEnvelope();
    if (!envelope) { ctx.loadShell({ schema: "mycite.v2.portal.shell.request.v1" }); return; }
    var nextQuery = Object.assign({}, envelope.surface_query || {});
    if (_dov.documentId) nextQuery.document = _dov.documentId;
    ctx.loadShell({ schema: "mycite.v2.portal.shell.request.v1", requested_surface_id: envelope.surface_id, surface_query: nextQuery });
  }
  function _dovRenderInformation(content) {
    content.innerHTML = '<div class="v2-info__meta">Loading abstraction path…</div>';
    var url = "/portal/api/v2/datum/info?document=" + encodeURIComponent(_dov.documentId) +
      "&address=" + encodeURIComponent(_dov.address);
    fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j || !j.ok) { content.innerHTML = '<div class="v2-info__meta">' + escapeHtml((j && j.error) || "No information.") + "</div>"; return; }
        var path = j.path || [];
        var nodes = path.map(function (n, i) {
          return (i > 0 ? '<div class="v2-info__arrow">↓</div>' : "") +
            '<div class="v2-info__node' + (n.is_target ? " is-target" : "") + '">' +
            "<span>" + escapeHtml(n.datum_address) + "</span>" +
            '<span class="v2-info__hash">' + escapeHtml(asText(n.semantic_hash).replace(/^sha256:/, "").slice(0, 12)) + "</span></div>";
        }).join("");
        content.innerHTML =
          '<div class="v2-info__meta">Abstraction path — the datum’s minimum-but-complete dependency closure (' +
          path.length + " node" + (path.length === 1 ? "" : "s") + ").</div>" +
          '<div class="v2-info__path">' + (nodes || '<div class="v2-info__meta">No dependencies.</div>') + "</div>" +
          '<div class="v2-denote__sectionLabel">Hyphae value</div>' +
          '<div class="v2-info__hyphae" data-info-hyphae>' + escapeHtml(asText(j.hyphae_hash)) + "</div>" +
          '<div class="v2-denote__actions"><button type="button" class="v2-btn" data-info-generate>Generate hyphae value</button></div>';
        var gen = content.querySelector("[data-info-generate]");
        if (gen) gen.onclick = function () { _dovRenderInformation(content); };
      })
      .catch(function () { content.innerHTML = '<div class="v2-info__meta">Could not load datum information.</div>'; });
  }
  window.openDatumOverlay = openDatumOverlay;
  window.closeDatumOverlay = closeDatumOverlay;

  // ===== Context menu (kebab on a refracted cell) + SAMRAS collapse =====
  function _rawForAddress(address) {
    var c = _dovTriggerCtx;
    if (!c) return null;
    var grid = asObject(asObject(c.workspace).datum_grid);
    var rows = typeof flattenDatumGridForEditor === "function" ? flattenDatumGridForEditor(grid) : [];
    for (var i = 0; i < rows.length; i++) {
      if (asText(asObject(rows[i]).datum_address) === address) return asObject(rows[i]).raw;
    }
    return null;
  }
  function _ctxOutside(ev) { if (!ev.target.closest || !ev.target.closest("#portalContextMenu")) _closeContextMenu(); }
  function _ctxKey(ev) { if (ev.key === "Escape" || ev.key === "Esc") _closeContextMenu(); }
  function _closeContextMenu() {
    var m = document.getElementById("portalContextMenu");
    if (m && m.parentNode) m.parentNode.removeChild(m);
    document.removeEventListener("click", _ctxOutside, true);
    document.removeEventListener("keydown", _ctxKey, true);
  }
  function showContextMenu(x, y, items) {
    _closeContextMenu();
    var menu = document.createElement("div");
    menu.id = "portalContextMenu";
    menu.className = "v2-ctxMenu";
    menu.innerHTML = items.map(function (it, i) {
      if (it.separator) return '<div class="v2-ctxMenu__sep"></div>';
      return '<button type="button" class="v2-ctxMenu__item' + (it.danger ? " is-danger" : "") + '" data-ctx-index="' + i + '">' +
        escapeHtml(it.label) + (it.submenu ? '<span class="v2-ctxMenu__arrow">▸</span>' : "") + "</button>";
    }).join("");
    document.body.appendChild(menu);
    var w = menu.offsetWidth, h = menu.offsetHeight;
    menu.style.left = Math.max(4, Math.min(x, window.innerWidth - w - 8)) + "px";
    menu.style.top = Math.max(4, Math.min(y, window.innerHeight - h - 8)) + "px";
    menu.addEventListener("click", function (ev) {
      var btn = ev.target.closest ? ev.target.closest("[data-ctx-index]") : null;
      if (!btn) return;
      var it = items[parseInt(btn.getAttribute("data-ctx-index"), 10)];
      if (!it) return;
      if (it.submenu) {
        // drill-down: replace the menu with the submenu (+ a back item), same anchor
        showContextMenu(x, y, [{ label: "‹ back", onClick: function () { showContextMenu(x, y, items); } }, { separator: true }].concat(it.submenu));
        return;
      }
      _closeContextMenu();
      if (it.onClick) it.onClick();
    });
    setTimeout(function () {
      document.addEventListener("click", _ctxOutside, true);
      document.addEventListener("keydown", _ctxKey, true);
    }, 0);
  }

  function _samrasNodeKey(raw) {
    var head = raw && Array.isArray(raw) && Array.isArray(raw[0]) ? raw[0] : null;
    if (!head || head.length < 3) return null;
    var marker = asText(head[1]);
    if (marker !== "rf.3-1-1" && marker !== "rf.3-1-5") return null;  // NODE_ID / LCL_ID samras markers
    return asText(head[2]);
  }
  function _samrasContext(address) {
    var key = _samrasNodeKey(_rawForAddress(address));
    if (!key) return null;
    var row = document.querySelector('.v2-ide__row[data-datum-address="' + address + '"]');
    var vg = row && row.closest ? row.closest(".v2-ide__valueGroup") : null;
    if (!vg) return null;
    var siblings = [];
    Array.prototype.forEach.call(vg.querySelectorAll(".v2-ide__row[data-datum-address]"), function (tr) {
      var a = tr.getAttribute("data-datum-address");
      var k = _samrasNodeKey(_rawForAddress(a));
      if (k) siblings.push({ address: a, key: k, tr: tr });
    });
    return siblings.length >= 2 ? { key: key, siblings: siblings, vg: vg } : null;
  }
  var _selCounter = 0;
  function _collapseRows(trs) {
    trs = (trs || []).filter(Boolean);
    if (!trs.length) return;
    var gid = "sel" + (++_selCounter);
    trs.forEach(function (tr) { tr.classList.add("is-sel-collapsed"); tr.setAttribute("data-sel-group", gid); });
    var first = trs[0];
    var colspan = (first.children && first.children.length) || 3;
    var divider = document.createElement("tr");
    divider.className = "v2-ide__selDivider";
    divider.setAttribute("data-sel-divider", gid);
    divider.innerHTML = '<td colspan="' + colspan + '">' +
      '<button type="button" class="mc-iconBtn mc-iconBtn--sm mc-iconBtn--light v2-ide__selExpand" data-sel-expand="' + gid + '" aria-label="Expand">' +
      (window.iconImg ? window.iconImg("down") : "▾") + "</button>" +
      '<span class="v2-ide__selCount">' + trs.length + " collapsed</span>" +
      '<button type="button" class="mc-iconBtn mc-iconBtn--sm mc-iconBtn--light v2-ide__selClear" data-sel-clear="' + gid + '" aria-label="Expand and clear">' +
      (window.iconImg ? window.iconImg("exit") : "×") + "</button></td>";
    if (first.parentNode) first.parentNode.insertBefore(divider, first);
  }
  function _collapseSamrasDescendants(address) {
    var sx = _samrasContext(address);
    if (!sx) return;
    var trs = sx.siblings.filter(function (s) { return s.key !== sx.key && s.key.indexOf(sx.key + "-") === 0; }).map(function (s) { return s.tr; });
    _collapseRows(trs);
  }
  function _samrasSliceItems(address) {
    var sx = _samrasContext(address);
    if (!sx) return [{ label: "(no adjacent nodes)", onClick: function () {} }];
    var sibs = sx.siblings;
    var idx = -1;
    for (var i = 0; i < sibs.length; i++) if (sibs[i].address === address) { idx = i; break; }
    var items = [];
    sibs.forEach(function (s, j) {
      if (j === idx) return;
      items.push({ label: (j < idx ? "↑ to " : "↓ to ") + s.key, onClick: function () {
        var lo = Math.min(idx, j), hi = Math.max(idx, j);
        _collapseRows(sibs.slice(lo, hi + 1).map(function (x) { return x.tr; }));
      } });
    });
    return items.length ? items : [{ label: "(no adjacent nodes)", onClick: function () {} }];
  }
  function _deleteDatum(address, c) {
    var body = { schema: "mycite.v2.portal.mutations.stage.request.v1", target_authority: "datum_workbench",
      sandbox_id: c.sandboxId, document_id: c.documentId, datum_address: address, target_address: address,
      operation: "delete_datum", payload_text: JSON.stringify(_rawForAddress(address) || [[address], []]) };
    if (typeof stageThenApply !== "function") return;
    _dov.ctx = c.ctx; _dov.documentId = c.documentId;
    stageThenApply(body, "/portal/api/v2/mutations/stage", "/portal/api/v2/mutations/apply")
      .then(function () { _dovRefreshShell(); })
      .catch(function () {});
  }
  function _showDatumContextMenu(x, y, address, c) {
    var items = [
      { label: "Edit", onClick: function () { openDatumOverlay({ ctx: c.ctx, workspace: c.workspace, documentId: c.documentId, sandboxId: c.sandboxId, address: address, raw: _rawForAddress(address), mode: "edit", activeTab: "denotation" }); } },
      { label: "Delete", danger: true, onClick: function () { _deleteDatum(address, c); } },
    ];
    if (_samrasContext(address)) {
      items.push({ separator: true });
      items.push({ label: "SAMRAS", submenu: [
        { label: "Collapse descendants", onClick: function () { _collapseSamrasDescendants(address); } },
        { label: "Collapse slice", submenu: _samrasSliceItems(address) },
      ] });
    }
    showContextMenu(x, y, items);
  }
  window.showContextMenu = showContextMenu;

  // Datum-overlay open triggers (refracted cell ℹ / kebab / merged cell, the add-rows, the
  // top-left edit icon). Bound ONCE on document; the per-render context (ctx/workspace/doc/sandbox)
  // is refreshed in _dovTriggerCtx each render so the single listener never goes stale or duplicates.
  var _dovTriggerCtx = null;
  var _dovTriggersBound = false;
  function _intAttr(el, name) { var v = parseInt(el.getAttribute(name), 10); return isNaN(v) ? null : v; }
  function _bindDatumOverlayTriggers(ctx, workspace, surfacePayload) {
    var sp = asObject(surfacePayload);
    var ndf = asObject(sp.new_datum_form);
    var selDoc = asObject(asObject(workspace).selected_document);
    _dovTriggerCtx = {
      ctx: ctx,
      workspace: workspace,
      documentId: asText(selDoc.document_id) || asText(ndf.document_id_default),
      sandboxId: asText(ndf.sandbox_id) || "agro_erp",
    };
    if (_dovTriggersBound) return;
    _dovTriggersBound = true;
    document.addEventListener("click", function (ev) {
      var c = _dovTriggerCtx;
      if (!c) return;
      var t = ev.target;
      if (!t || !t.closest || !t.closest('[data-region="document-editor"]')) return;
      function rawFor(address) {
        var grid = asObject(asObject(c.workspace).datum_grid);
        var rows = typeof flattenDatumGridForEditor === "function" ? flattenDatumGridForEditor(grid) : [];
        for (var i = 0; i < rows.length; i++) {
          if (asText(asObject(rows[i]).datum_address) === address) return asObject(rows[i]).raw;
        }
        return null;
      }
      function base() { return { ctx: c.ctx, workspace: c.workspace, documentId: c.documentId, sandboxId: c.sandboxId }; }
      // Collapse toggles (layer / value group) — pure client-side; the button swaps up/down.
      var collapseBtn = t.closest("[data-ide-collapse]");
      if (collapseBtn) {
        ev.preventDefault();
        var kind = collapseBtn.getAttribute("data-ide-collapse");
        var sect = collapseBtn.closest(kind === "layer" ? ".v2-ide__layer" : ".v2-ide__valueGroup");
        if (sect) {
          var collapsed = sect.classList.toggle("is-collapsed");
          collapseBtn.innerHTML = window.iconImg ? window.iconImg(collapsed ? "down" : "up") : (collapsed ? "▸" : "▾");
        }
        return;
      }
      // Selection-collapse divider: ui-down expands in place (toggles to ui-up); ui-exit expands + clears.
      var selExpand = t.closest("[data-sel-expand]");
      if (selExpand) {
        ev.preventDefault();
        var gid = selExpand.getAttribute("data-sel-expand");
        var div = document.querySelector('[data-sel-divider="' + gid + '"]');
        var revealed = div ? div.classList.toggle("is-expanded") : false;
        Array.prototype.forEach.call(document.querySelectorAll('[data-sel-group="' + gid + '"]'), function (tr) { tr.classList.toggle("is-revealed", revealed); });
        selExpand.innerHTML = window.iconImg ? window.iconImg(revealed ? "up" : "down") : (revealed ? "▴" : "▾");
        return;
      }
      var selClear = t.closest("[data-sel-clear]");
      if (selClear) {
        ev.preventDefault();
        var gid2 = selClear.getAttribute("data-sel-clear");
        Array.prototype.forEach.call(document.querySelectorAll('[data-sel-group="' + gid2 + '"]'), function (tr) { tr.classList.remove("is-sel-collapsed", "is-revealed"); tr.removeAttribute("data-sel-group"); });
        var d2 = document.querySelector('[data-sel-divider="' + gid2 + '"]');
        if (d2 && d2.parentNode) d2.parentNode.removeChild(d2);
        return;
      }
      var editDoc = t.closest("[data-dov-edit-doc]");
      var addBtn = t.closest("[data-dov-add]");
      var infoBtn = t.closest("[data-datum-info]");
      var kebabBtn = t.closest("[data-datum-kebab]");
      var refracted = t.closest(".v2-ide__cell--refracted");
      if (editDoc) {
        ev.preventDefault();
        openDatumOverlay(Object.assign(base(), { mode: "create", activeTab: "denotation" }));
      } else if (addBtn) {
        ev.preventDefault();
        openDatumOverlay(Object.assign(base(), { mode: "create", activeTab: "denotation",
          layer: _intAttr(addBtn, "data-layer"), valueGroup: _intAttr(addBtn, "data-value-group") }));
      } else if (infoBtn) {
        ev.preventDefault();
        var ia = infoBtn.getAttribute("data-datum-address");
        openDatumOverlay(Object.assign(base(), { address: ia, raw: rawFor(ia), mode: "edit", activeTab: "information" }));
      } else if (kebabBtn) {
        ev.preventDefault();
        var ka = kebabBtn.getAttribute("data-datum-address");
        var kr = kebabBtn.getBoundingClientRect();
        _showDatumContextMenu(kr.left, kr.bottom + 2, ka, base());
      } else if (refracted) {
        ev.preventDefault();
        var ra = refracted.getAttribute("data-datum-address");
        openDatumOverlay(Object.assign(base(), { address: ra, raw: rawFor(ra), mode: "edit", activeTab: "information" }));
      }
    });
  }
  function bindWorkbenchNavigation(ctx, target, workspace, surfacePayload, region) {
    bindDocumentColumn(ctx, target, workspace, surfacePayload || {});
    bindDatumComposer(ctx, target, workspace, surfacePayload || {});
    bindDocumentEditor(ctx, target, workspace, surfacePayload || {});
    _bindDatumOverlayTriggers(ctx, workspace, surfacePayload || {});
  }

  function renderRegisteredWorkspaceSurface(ctx, target, region, surfacePayload, moduleSpec) {
    var adapter = toolSurfaceAdapter();
    var spec = asObject(moduleSpec);
    var renderer = resolveRegisteredModuleExport(spec.moduleId, spec.globalName);
    if (renderer && typeof renderer.render === "function") {
      renderer.render(ctx, target, surfacePayload);
      return;
    }
    if (typeof window.__MYCITE_V2_LOAD_SHELL_MODULE === "function" && asText(spec.moduleId)) {
      adapter.renderWrappedSurface(
        target,
        {
          state: "loading",
          title: region.title || surfacePayload.title || spec.label || "Workbench",
          message: "Loading deferred renderer module…",
          warnings: [],
          readiness: {},
          toolId: asText(spec.moduleId),
        },
        ""
      );
      window.__MYCITE_V2_LOAD_SHELL_MODULE(spec.moduleId, {
        reason: "reflective_workspace:" + (asText(spec.label) || asText(spec.moduleId) || "unknown"),
      })
        .then(function () {
          var resolved = resolveRegisteredModuleExport(spec.moduleId, spec.globalName);
          if (resolved && typeof resolved.render === "function") {
            resolved.render(ctx, target, surfacePayload);
            return;
          }
          adapter.renderWrappedSurface(
            target,
            adapter.resolveSurfaceState({
              region: region,
              surfacePayload: surfacePayload,
              title: region.title || surfacePayload.title || spec.label || "Workbench",
              unsupported: true,
              message: buildModuleRegistrationMessage(
                spec.label || "workspace",
                spec.moduleId,
                spec.globalName,
                "render"
              ),
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
              title: region.title || surfacePayload.title || spec.label || "Workbench",
              unsupported: true,
              message:
                buildModuleRegistrationMessage(
                  spec.label || "workspace",
                  spec.moduleId,
                  spec.globalName,
                  "render"
                ) +
                " " +
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
        title: region.title || surfacePayload.title || spec.label || "Workbench",
        unsupported: true,
        message: buildModuleRegistrationMessage(
          spec.label || "workspace",
          spec.moduleId,
          spec.globalName,
          "render"
        ),
      }),
      ""
    );
  }

  function renderWorkbenchUiSurface(ctx, target, region, surfacePayload) {
    var adapter = toolSurfaceAdapter();
    if (
      adapter.renderWrappedSurface(
        target,
        adapter.resolveSurfaceState({
          region: region,
          surfacePayload: surfacePayload,
          title: region.title || "Workbench UI",
          hasContent: true,
        }),
        renderWorkbenchSurface(surfacePayload, region)
      )
    ) {
      bindWorkbenchNavigation(
        ctx,
        target,
        asObject(surfacePayload.workspace),
        surfacePayload,
        region
      );
    }
  }

  function renderReflectiveWorkspaceHost(ctx, target, region, surfacePayload) {
    var adapter = toolSurfaceAdapter();
    var mode =
      (adapter &&
        typeof adapter.resolveReflectiveWorkspaceMode === "function" &&
        adapter.resolveReflectiveWorkspaceMode(region, surfacePayload)) ||
      "generic_surface";
    var moduleSpec =
      (adapter &&
        typeof adapter.resolveReflectiveWorkspaceModuleSpec === "function" &&
        adapter.resolveReflectiveWorkspaceModuleSpec(region, surfacePayload)) ||
      {};

    // Handle loading state
    if (mode === "loading") {
      target.innerHTML =
        '<section class="v2-card" style="margin:12px">' +
        '<h3>Loading Workbench</h3>' +
        '<p>Loading tool workbench renderer...</p>' +
        '</section>';
      return;
    }

    if (mode === "registered_workspace" && asObject(moduleSpec).moduleId) {
      renderRegisteredWorkspaceSurface(ctx, target, region, surfacePayload, moduleSpec);
      return;
    }
    if (asText(surfacePayload && surfacePayload.kind) === "sql_authority_lens" || asText(region && region.kind) === "sql_authority_lens") {
      renderWorkbenchUiSurface(ctx, target, region, surfacePayload);
      return;
    }

    // Fallback for tools without ANY workbench content. The earlier check
    // looked only at `region.{sections,cards,rows}`, which misses the
    // `surface_payload`-shaped tools (utilities tool-exposure, integrations)
    // whose content lives one level deeper. Phase 12h added `grantee_selector`
    // to the surface payload — include it in the content probe.
    var hasSurfaceContent =
      adapter.hasGenericContent(surfacePayload) ||
      (surfacePayload && surfacePayload.grantee_selector);
    if (
      mode === "generic_surface" &&
      !region.sections &&
      !region.cards &&
      !region.rows &&
      !hasSurfaceContent
    ) {
      target.innerHTML =
        '<section class="v2-card" style="margin:12px">' +
        '<h3>Workbench</h3>' +
        '<p>This tool does not provide a workbench view.</p>' +
        '</section>';
      return;
    }

    renderGenericSurface(ctx, target, region, surfacePayload);
  }

  function renderDatumFileWorkbenchHeader(region) {
    var sandbox = asObject(region && region.sandbox);
    var sandboxLabel = asText(sandbox.label) || asText(sandbox.id) || "Sandbox";
    var subtitle = asText(region && region.subtitle);
    return (
      '<header class="v2-card" style="margin-bottom:12px">' +
      '<h2 style="margin:0">' +
      escapeHtml(asText(region && region.title) || "Datum File Workbench") +
      "</h2>" +
      '<p style="margin:4px 0 0 0"><small>Sandbox: ' +
      escapeHtml(sandboxLabel) +
      "</small>" +
      (subtitle ? "<br /><small>" + escapeHtml(subtitle) + "</small>" : "") +
      "</p>" +
      "</header>"
    );
  }

  function buildLayeredDatumRowHtml(row) {
    var coords = asObject(row.coordinates);
    var editActions = asList(row.edit_actions);
    var editAction = asObject(editActions[0]);
    return (
      "<tr><td>" +
      escapeHtml(coords.iteration != null ? String(coords.iteration) : "—") +
      "</td><td>" +
      escapeHtml(asText(row.label) || asText(row.datum_id) || "Datum") +
      "</td><td>" +
      escapeHtml(asText(row.display_value) || asText(row.primary_value_token) || "—") +
      "</td><td>" +
      (asText(editAction.action)
        ? '<button type="button" data-datum-edit-action="' +
          escapeHtml(asText(editAction.action)) +
          '" data-datum-document-id="' +
          escapeHtml(asText(editAction.document_id)) +
          '" data-datum-address="' +
          escapeHtml(asText(editAction.datum_address)) +
          '" data-datum-sandbox-id="' +
          escapeHtml(asText(editAction.sandbox_id)) +
          '">Edit</button>'
        : "—") +
      "</td></tr>"
    );
  }

  function buildLayeredDatumTableHtml(vgRows) {
    return (
      '<div class="v2-tableWrap"><table class="v2-table"><thead><tr><th>Iter</th><th>Datum</th><th>Value</th><th>Action</th></tr></thead><tbody>' +
      vgRows.map(buildLayeredDatumRowHtml).join("") +
      "</tbody></table></div>"
    );
  }

  function pendingLayeredRowsRegistry() {
    if (!window.__CTS_GIS_PENDING_ROWS) {
      window.__CTS_GIS_PENDING_ROWS = new Map();
    }
    return window.__CTS_GIS_PENDING_ROWS;
  }

  function pendingLayeredRowsKey(layerId, valueGroupId) {
    return String(layerId) + "|" + String(valueGroupId);
  }

  function renderLayeredDatumTable(region) {
    var table = asObject(region && region.layered_datum_table);
    var doc = asObject(table.document);
    var layerGroups = asList(table.layer_groups);
    var rows = asList(table.rows);
    var heading =
      '<header class="v2-card" style="margin-bottom:12px">' +
      "<h3>" +
      escapeHtml(stripJsonSuffix(asText(doc.canonical_name) || asText(doc.document_name) || asText(doc.document_id) || "Datum file")) +
      "</h3>" +
      ((asText(doc.document_name) || asText(doc.document_id))
        ? '<small>' +
          escapeHtml(stripJsonSuffix(asText(doc.document_name) || asText(doc.document_id))) +
          "</small>"
        : "") +
      "</header>";
    if (layerGroups.length) {
      var pending = pendingLayeredRowsRegistry();
      return (
        heading +
        layerGroups
          .map(function (layer, layerIndex) {
            var valueGroups = asList(layer.value_groups);
            var layerSelected = !!layer.selected;
            var layerId = layer.layer != null ? String(layer.layer) : "unstructured-" + layerIndex;
            return (
              '<details class="v2-card" data-layer-id="' +
              escapeHtml(layerId) +
              '"' +
              (layerSelected ? " open" : "") +
              ' style="margin-top:12px"><summary>' +
              escapeHtml(
                asText(layer.label) +
                  " (" +
                  String(asList(layer.rows).length || layer.row_count || 0) +
                  " rows)"
              ) +
              "</summary>" +
              valueGroups
                .map(function (vg, vgIndex) {
                  var vgRows = asList(vg.rows);
                  var vgSelected = !!vg.selected;
                  var preRender = layerSelected || vgSelected;
                  var valueGroupId = vg.value_group != null ? String(vg.value_group) : "unstructured-" + vgIndex;
                  var bodyHtml;
                  if (preRender || !vgRows.length) {
                    bodyHtml = buildLayeredDatumTableHtml(vgRows);
                  } else {
                    pending.set(pendingLayeredRowsKey(layerId, valueGroupId), vgRows);
                    bodyHtml = '<div class="cts-gis-rows-pending">Loading rows…</div>';
                  }
                  return (
                    '<details class="v2-card" data-layer-id="' +
                    escapeHtml(layerId) +
                    '" data-value-group-id="' +
                    escapeHtml(valueGroupId) +
                    '"' +
                    (preRender ? " open" : "") +
                    ' style="margin-top:12px"><summary>' +
                    escapeHtml(
                      asText(vg.label) +
                        " (" +
                        String(vgRows.length || vg.row_count || 0) +
                        " rows)"
                    ) +
                    "</summary>" +
                    bodyHtml +
                    "</details>"
                  );
                })
                .join("") +
              "</details>"
            );
          })
          .join("")
      );
    }
    if (!rows.length) {
      return (
        heading +
        '<section class="v2-card" style="margin-top:12px">' +
        '<p>No datum rows are currently projected for this document.</p>' +
        "</section>"
      );
    }
    return (
      heading +
      '<section class="v2-card" style="margin-top:12px"><div class="v2-tableWrap">' +
      '<table class="v2-table"><thead><tr><th>Datum</th><th>Value</th><th>Action</th></tr></thead><tbody>' +
      rows
        .map(function (row) {
          var rowObj = asObject(row);
          var editActions = asList(rowObj.edit_actions);
          var editAction = asObject(editActions[0]);
          return (
            "<tr><td>" +
            escapeHtml(asText(rowObj.label) || asText(rowObj.datum_id) || "Datum") +
            "</td><td>" +
            escapeHtml(asText(rowObj.display_value) || asText(rowObj.primary_value_token) || "—") +
            "</td><td>" +
            (asText(editAction.action)
              ? '<button type="button" data-datum-edit-action="' +
                escapeHtml(asText(editAction.action)) +
                '" data-datum-document-id="' +
                escapeHtml(asText(editAction.document_id)) +
                '" data-datum-address="' +
                escapeHtml(asText(editAction.datum_address)) +
                '" data-datum-sandbox-id="' +
                escapeHtml(asText(editAction.sandbox_id)) +
                '">Edit</button>'
              : "—") +
            "</td></tr>"
          );
        })
        .join("") +
      "</tbody></table></div></section>"
    );
  }

  function renderSandboxDocumentCollection(region) {
    var collection = asObject(region && region.document_collection);
    var documents = asList(collection.documents);
    if (!documents.length) {
      return (
        '<section class="v2-card" style="margin-top:12px">' +
        '<h3>Sandbox Documents</h3>' +
        "<p>No datum documents are owned by this sandbox yet.</p>" +
        "</section>"
      );
    }
    // Sort documents alphabetically by the short label so cards land
    // in a navigable order. Anchor documents float to the top (they're
    // the entry point for the sandbox), then everything else A-Z.
    var sortedDocuments = documents.slice().sort(function (a, b) {
      var ao = asObject(a);
      var bo = asObject(b);
      var aAnchor = !!ao.is_anchor;
      var bAnchor = !!bo.is_anchor;
      if (aAnchor !== bAnchor) return aAnchor ? -1 : 1;
      var an = shortDocumentLabel(asText(ao.document_name) || asText(ao.canonical_name) || asText(ao.document_id));
      var bn = shortDocumentLabel(asText(bo.document_name) || asText(bo.canonical_name) || asText(bo.document_id));
      return an.localeCompare(bn, undefined, { numeric: true, sensitivity: "base" });
    });
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Sandbox Documents</h3>' +
      '<div class="v2-card-grid">' +
      sortedDocuments
        .map(function (card) {
          var cardObj = asObject(card);
          var documentId = asText(cardObj.document_id);
          var canonicalName = stripJsonSuffix(asText(cardObj.canonical_name) || asText(cardObj.label));
          var rawName = stripJsonSuffix(asText(cardObj.document_name) || asText(cardObj.secondary_label) || asText(cardObj.relative_path));
          // Derive the visible card title from the FILENAME first since
          // that has stable structural markers (`.msn-`, `.cts_gis.`, etc.)
          // that map cleanly to a short navigable label. canonical_name
          // from the catalog may include concatenated hash segments
          // (e.g. "3-2-3-17-77-1-10d7568c17b6bb"). Fall back to
          // canonical_name then documentId if the filename is empty.
          var displayLabel = shortDocumentLabel(rawName || canonicalName || documentId);
          var isAnchor = !!cardObj.is_anchor;
          return (
            '<article class="v2-card v2-wb-docCard' +
            (cardObj.selected ? " is-selected" : "") +
            (isAnchor ? " is-anchor" : "") +
            '" tabindex="0" role="button" data-shell-transition-kind="focus_file" data-shell-file-key="' +
            escapeHtml(documentId) +
            '" title="' +
            escapeHtml(canonicalName || rawName || documentId) +
            '">' +
            '<div class="v2-wb-docCard__header">' +
            '<h3 class="v2-wb-docCard__name">' +
            escapeHtml(displayLabel || documentId || "Document") +
            (isAnchor ? ' <small>(anchor)</small>' : "") +
            "</h3>" +
            '<span class="v2-wb-docCard__actions">' +
            '<button class="v2-wb-renameBtn" data-rename-document-id="' + escapeHtml(documentId) + '" title="Rename" aria-label="Rename">✎</button>' +
            (!isAnchor
              ? '<button class="v2-wb-deleteBtn" data-delete-document-id="' + escapeHtml(documentId) + '" data-document-is-anchor="false" title="Delete" aria-label="Delete">×</button>'
              : '<button class="v2-wb-deleteBtn" data-delete-document-id="' + escapeHtml(documentId) + '" data-document-is-anchor="true" title="Anchor cannot be deleted" aria-label="Delete" disabled>×</button>'
            ) +
            "</span>" +
            "</div>" +
            ((rawName || documentId)
              ? "<p><small>" + escapeHtml(rawName || documentId) + "</small></p>"
              : "") +
            (documentId ? "<p><small>" + escapeHtml(documentId) + "</small></p>" : "") +
            "<p>Rows: " +
            escapeHtml(String(cardObj.row_count || 0)) +
            "</p>" +
            "</article>"
          );
        })
        .join("") +
      "</div></section>"
    );
  }

  function bindDocumentCardActions(target, ctx) {
    Array.prototype.forEach.call(target.querySelectorAll("[data-rename-document-id]"), function (btn) {
      btn.addEventListener("click", function (event) {
        event.stopPropagation();
        event.preventDefault();
        var documentId = btn.getAttribute("data-rename-document-id") || "";
        var card = btn.closest(".v2-wb-docCard");
        if (!card) return;
        var nameEl = card.querySelector(".v2-wb-docCard__name");
        if (!nameEl || card.querySelector(".v2-wb-renameInput")) return;
        var currentName = nameEl.textContent.replace(/\s*\(anchor\)\s*$/, "").trim();
        var input = document.createElement("input");
        input.className = "v2-wb-renameInput";
        input.value = currentName;
        input.setAttribute("data-document-id", documentId);
        nameEl.replaceWith(input);
        input.focus();
        input.select();
        function commit() {
          var newName = input.value.trim();
          var restoredEl = document.createElement("h3");
          restoredEl.className = "v2-wb-docCard__name";
          restoredEl.textContent = newName || currentName;
          input.replaceWith(restoredEl);
          if (newName && newName !== currentName && typeof ctx.dispatchToolAction === "function") {
            ctx.dispatchToolAction({ action_kind: "rename_document", document_id: documentId, new_name: newName });
          }
        }
        input.addEventListener("blur", commit);
        input.addEventListener("keydown", function (e) {
          if (e.key === "Enter") { e.preventDefault(); commit(); }
          if (e.key === "Escape") {
            var restoredEl = document.createElement("h3");
            restoredEl.className = "v2-wb-docCard__name";
            restoredEl.textContent = currentName;
            input.removeEventListener("blur", commit);
            input.replaceWith(restoredEl);
          }
        });
      });
    });
    Array.prototype.forEach.call(target.querySelectorAll("[data-delete-document-id]"), function (btn) {
      btn.addEventListener("click", function (event) {
        event.stopPropagation();
        event.preventDefault();
        var isAnchor = btn.getAttribute("data-document-is-anchor") === "true";
        if (isAnchor) {
          var card = btn.closest(".v2-wb-docCard");
          if (card) {
            var warn = card.querySelector(".v2-wb-anchorWarn");
            if (!warn) {
              warn = document.createElement("p");
              warn.className = "v2-wb-anchorWarn";
              warn.style.color = "var(--color-warning, #c77)";
              warn.textContent = "Anchor cannot be deleted.";
              card.appendChild(warn);
              setTimeout(function () { if (warn.parentNode) warn.parentNode.removeChild(warn); }, 3000);
            }
          }
          return;
        }
        var documentId = btn.getAttribute("data-delete-document-id") || "";
        if (documentId && typeof ctx.dispatchToolAction === "function") {
          ctx.dispatchToolAction({ action_kind: "delete_document", document_id: documentId });
        }
      });
    });
  }

  function renderDatumFileWorkbench(ctx, target, region) {
    var activeDocument = asObject(region && region.active_document);
    var table = asObject(region && region.layered_datum_table);
    var body = (activeDocument.document_id || asObject(table.document).document_id)
      ? renderLayeredDatumTable(region)
      : renderSandboxDocumentCollection(region);
    target.innerHTML = renderDatumFileWorkbenchHeader(region) + body;
    bindDatumFileWorkbenchEvents(ctx, target, region);
    bindDocumentCardActions(target, ctx);
  }

  function bindDatumFileWorkbenchEvents(ctx, target, region) {
    Array.prototype.forEach.call(target.querySelectorAll("[data-shell-transition-kind]"), function (node) {
      function activate(event) {
        if (event.type === "keydown" && event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        var kind = node.getAttribute("data-shell-transition-kind") || "";
        var fileKey = node.getAttribute("data-shell-file-key") || "";
        if (kind && typeof ctx.dispatchTransition === "function") {
          ctx.dispatchTransition({ kind: kind, file_key: fileKey });
        }
      }
      node.addEventListener("click", activate);
      node.addEventListener("keydown", activate);
      node.addEventListener("dblclick", function (event) {
        var kind = node.getAttribute("data-shell-transition-kind") || "";
        var fileKey = node.getAttribute("data-shell-file-key") || "";
        if (kind === "focus_file" && fileKey && typeof ctx.dispatchTransition === "function") {
          event.preventDefault();
          ctx.dispatchTransition({ kind: "focus_file", file_key: fileKey });
        }
      });
    });
    // Wire NIMM directive actions: buttons with data-nimm-action-id dispatch the
    // corresponding transition directive from state_reflection.nimm.actions
    var stateReflection = asObject(region && region.state_reflection);
    var nimmActions = asList((asObject(stateReflection.nimm)).actions);
    if (nimmActions.length) {
      var nimmActionMap = {};
      nimmActions.forEach(function (entry) {
        var action = entry && typeof entry === "object" ? entry : {};
        var actionId = asText(action.action_id);
        if (actionId) nimmActionMap[actionId] = action;
      });
      Array.prototype.forEach.call(target.querySelectorAll("[data-nimm-action-id]"), function (node) {
        node.addEventListener("click", function (event) {
          event.preventDefault();
          var actionId = node.getAttribute("data-nimm-action-id") || "";
          var actionEntry = nimmActionMap[actionId];
          if (!actionEntry) return;
          var directive = asText(actionEntry.directive);
          if (directive && typeof ctx.dispatchTransition === "function") {
            ctx.dispatchTransition({ kind: "nimm_directive", directive: directive, action_id: actionId });
          }
        });
      });
    }

    bindDatumEditActionButtons(target, target, region);

    target.addEventListener("toggle", function (event) {
      var node = event.target;
      if (!node || node.tagName !== "DETAILS") return;
      if (!node.open) return;
      var valueGroupId = node.getAttribute("data-value-group-id");
      if (valueGroupId == null) return;
      var layerId = node.getAttribute("data-layer-id") || "";
      var pending = pendingLayeredRowsRegistry();
      var key = pendingLayeredRowsKey(layerId, valueGroupId);
      if (!pending.has(key)) return;
      var vgRows = pending.get(key);
      pending.delete(key);
      var placeholder = node.querySelector(".cts-gis-rows-pending");
      var html = buildLayeredDatumTableHtml(vgRows);
      if (placeholder && placeholder.parentNode) {
        var wrapper = document.createElement("div");
        wrapper.innerHTML = html;
        var inserted = wrapper.firstChild;
        placeholder.parentNode.replaceChild(inserted, placeholder);
        bindDatumEditActionButtons(inserted, target, region);
      } else {
        node.insertAdjacentHTML("beforeend", html);
        bindDatumEditActionButtons(node, target, region);
      }
    }, true);
  }

  function bindDatumEditActionButtons(scope, target, region) {
    Array.prototype.forEach.call(scope.querySelectorAll("[data-datum-edit-action]"), function (node) {
      if (node.getAttribute("data-datum-edit-action-bound") === "1") return;
      node.setAttribute("data-datum-edit-action-bound", "1");
      node.addEventListener("click", function () {
        var table = asObject(region && region.layered_datum_table);
        var documentId = node.getAttribute("data-datum-document-id") || asText(asObject(table.document).document_id);
        var datumAddress = node.getAttribute("data-datum-address") || "";
        var sandboxId = node.getAttribute("data-datum-sandbox-id") || asText(asObject(region && region.sandbox).id);
        var editor = target.querySelector("[data-datum-inline-editor]");
        if (!editor) {
          editor = document.createElement("section");
          editor.className = "v2-card";
          editor.setAttribute("data-datum-inline-editor", "true");
          editor.style.marginTop = "12px";
          target.appendChild(editor);
        }
        editor.innerHTML =
          "<h3>Datum Editor</h3>" +
          "<p><small>" +
          escapeHtml(documentId) +
          " · " +
          escapeHtml(datumAddress) +
          "</small></p>" +
          '<textarea data-datum-edit-payload rows="5" style="width:100%"></textarea>' +
          '<div style="margin-top:8px">' +
          '<button type="button" data-datum-stage>Stage</button> ' +
          '<button type="button" data-datum-validate>Validate</button> ' +
          '<button type="button" data-datum-preview>Preview</button> ' +
          '<button type="button" data-datum-apply>Apply</button> ' +
          '<button type="button" data-datum-discard>Discard</button>' +
          "</div>" +
          '<pre data-datum-edit-status style="white-space:pre-wrap"></pre>';
        bindDatumEditorActions(editor, {
          sandbox_id: sandboxId,
          document_id: documentId,
          datum_address: datumAddress,
          action: node.getAttribute("data-datum-edit-action") || "update_row_raw",
        });
      });
    });
  }

  function bindDatumEditorActions(editor, basePayload) {
    function postMutation(stage) {
      var textarea = editor.querySelector("[data-datum-edit-payload]");
      var status = editor.querySelector("[data-datum-edit-status]");
      var payloadText = textarea ? textarea.value : "";
      var body = {
        target_authority: "datum_workbench",
        operation: basePayload.action,
        sandbox_id: basePayload.sandbox_id,
        document_id: basePayload.document_id,
        datum_address: basePayload.datum_address,
        payload_text: payloadText,
      };
      if (status) status.textContent = "pending " + stage + "...";
      fetch("/portal/api/v2/mutations/" + stage, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
        .then(function (response) {
          return response.json().catch(function () {
            return { ok: response.ok, status: response.status };
          });
        })
        .then(function (payload) {
          if (status) status.textContent = prettyJson(payload);
        })
        .catch(function (error) {
          if (status) status.textContent = String(error && error.message ? error.message : error);
        });
    }
    [
      ["data-datum-stage", "stage"],
      ["data-datum-validate", "validate"],
      ["data-datum-preview", "preview"],
      ["data-datum-apply", "apply"],
      ["data-datum-discard", "discard"],
    ].forEach(function (pair) {
      var node = editor.querySelector("[" + pair[0] + "]");
      if (node) node.addEventListener("click", function () { postMutation(pair[1]); });
    });
  }

  window.PortalShellWorkbenchRenderer = {
    render: function (ctx) {
      var target = ctx.target;
      var region = ctx.region || {};
      var surfacePayload = region.surface_payload || {};
      if (!target) return;
      if (asText(region.kind) === "datum_file_workbench") {
        renderDatumFileWorkbench(ctx, target, region);
        return;
      }
      var adapter = toolSurfaceAdapter();
      var family =
        (adapter && typeof adapter.resolveRegionFamily === "function" && adapter.resolveRegionFamily(region)) ||
        "";
      var mode =
        (adapter &&
          typeof adapter.resolveReflectiveWorkspaceMode === "function" &&
          adapter.resolveReflectiveWorkspaceMode(region, surfacePayload)) ||
        "generic_surface";
      if (family === "reflective_workspace" || mode !== "generic_surface") {
        renderReflectiveWorkspaceHost(ctx, target, region, surfacePayload);
        return;
      }
      renderGenericSurface(ctx, target, region, surfacePayload);
    },
  };
  if (typeof window.__MYCITE_V2_REGISTER_SHELL_MODULE === "function") {
    window.__MYCITE_V2_REGISTER_SHELL_MODULE("workbench_renderers");
  }
})();

/**
 * Product-document visualizer renderer (Plan v2).
 *
 * Paints the panel_payload from MyCiteV2.packages.tools.product_document_view
 * (a labelled product table with cross-document-resolved names) into the
 * workbench visualization panel. Registered into the __MYCITE_V2_TOOL_RENDERERS
 * registry keyed by tool_id "product_document"; v2_portal_shell_core.js looks it
 * up when the selected tool's panel_payload lands in regions.visualization_panel.
 * Includes a client-side name filter — the "search" over the sandbox's products.
 */
(function () {
  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function buildTable(payload, query) {
    var products = Array.isArray(payload.products) ? payload.products : [];
    var columns = Array.isArray(payload.columns) ? payload.columns : [];
    var q = String(query || "").trim().toLowerCase();
    if (q) {
      products = products.filter(function (p) {
        return String(p.product_name || "").toLowerCase().indexOf(q) !== -1;
      });
    }
    var head =
      "<tr><th>product</th>" +
      columns.map(function (c) { return "<th>" + esc(c) + "</th>"; }).join("") +
      "</tr>";
    var body = products
      .map(function (p) {
        var byField = {};
        (p.fields || []).forEach(function (f) { byField[f.field] = f; });
        var cells = columns
          .map(function (c) {
            var f = byField[c] || {};
            var resolved = f.resolved ? String(f.resolved) : "";
            var magnitude = f.magnitude ? String(f.magnitude) : "";
            // Show the resolved label; reveal the raw magnitude on hover.
            var text = resolved || magnitude;
            var title = resolved && magnitude && resolved !== magnitude ? ' title="' + esc(magnitude) + '"' : "";
            return "<td" + title + ">" + esc(text) + "</td>";
          })
          .join("");
        return '<tr><td class="v2-product__name">' + esc(p.product_name) + "</td>" + cells + "</tr>";
      })
      .join("");
    return (
      '<div class="v2-product__count">' + esc(products.length) + " shown</div>" +
      '<div class="v2-product__tableWrap"><table class="v2-product__table"><thead>' +
      head + "</thead><tbody>" + body + "</tbody></table></div>"
    );
  }

  function renderProductDocument(payload, content) {
    payload = payload || {};
    if (!content) return;
    if (payload.error) {
      content.innerHTML =
        '<p class="ide-visualizationPanel__error">' + esc(payload.error) + "</p>";
      return;
    }
    var total = payload.product_count != null ? payload.product_count : (payload.products || []).length;
    content.innerHTML =
      '<section class="v2-product__viewer">' +
      '<header class="v2-product__header">' +
      esc(total) + " products · sandbox " + esc(payload.sandbox_id || "") +
      " · " + esc(payload.lcl_index_size || 0) + " names indexed" +
      "</header>" +
      '<input type="search" class="v2-product__search" data-product-search ' +
      'placeholder="Filter products by name…" aria-label="Filter products by name" />' +
      '<div data-product-table>' + buildTable(payload, "") + "</div>" +
      "</section>";
    var input = content.querySelector("[data-product-search]");
    var tableHost = content.querySelector("[data-product-table]");
    if (input && tableHost) {
      input.addEventListener("input", function () {
        tableHost.innerHTML = buildTable(payload, input.value);
      });
    }
  }

  window.__MYCITE_V2_TOOL_RENDERERS = window.__MYCITE_V2_TOOL_RENDERERS || {};
  window.__MYCITE_V2_TOOL_RENDERERS["product_document"] = renderProductDocument;
})();

// --------------------------------------------------------------------------- //
// CTS-GIS thin tools (read-only): map / district / admin. Each renders into a
// uniform visualization box from a compiled-artifact / MOS-direct payload.
// --------------------------------------------------------------------------- //
(function () {
  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function errorOr(payload, content) {
    if (!content) return true;
    if (payload && payload.error) {
      content.innerHTML = '<p class="ide-visualizationPanel__error">' + esc(payload.error) + "</p>";
      return true;
    }
    return false;
  }

  function renderCtsGisMap(payload, content) {
    payload = payload || {};
    if (errorOr(payload, content)) return;
    var fc = payload.feature_collection || {};
    var features = Array.isArray(fc.features) ? fc.features : [];
    var rows = features
      .map(function (f) {
        var p = (f && f.properties) || {};
        var id = (f && (f.id != null ? f.id : p.node_id)) || "";
        var label = p.label || p.name || "";
        return "<tr><td>" + esc(id) + "</td><td>" + esc(label) +
          "</td><td>" + esc((f && f.geometry && f.geometry.type) || "") + "</td></tr>";
      })
      .join("");
    content.innerHTML =
      '<section class="v2-ctsgis v2-ctsgis--map">' +
      '<header class="v2-ctsgis__header">' + esc(payload.feature_count || features.length) +
      " features · " + esc(payload.projection_state || "") + "</header>" +
      (features.length
        ? '<div class="v2-ctsgis__tableWrap"><table class="v2-ctsgis__table"><thead>' +
          "<tr><th>feature</th><th>label</th><th>geometry</th></tr></thead><tbody>" + rows +
          "</tbody></table></div>"
        : '<p class="v2-ctsgis__empty">No projected geometry — recompile the CTS-GIS artifact.</p>') +
      "</section>";
  }

  function renderCtsGisDistrict(payload, content) {
    payload = payload || {};
    if (errorOr(payload, content)) return;
    var members = Array.isArray(payload.member_precinct_ids) ? payload.member_precinct_ids : [];
    var items = members.map(function (m) { return "<li>" + esc(m) + "</li>"; }).join("");
    content.innerHTML =
      '<section class="v2-ctsgis v2-ctsgis--district">' +
      '<header class="v2-ctsgis__header">' + esc(payload.collection_label || payload.collection_id || "district") +
      " · " + esc(payload.member_count || members.length) + " precincts" +
      (payload.timeframe ? " · " + esc(payload.timeframe) : "") + "</header>" +
      '<ul class="v2-ctsgis__members">' + items + "</ul>" +
      "</section>";
  }

  function renderCtsGisAdmin(payload, content) {
    payload = payload || {};
    if (errorOr(payload, content)) return;
    var fields = Array.isArray(payload.fields) ? payload.fields : [];
    var rows = fields
      .map(function (f) {
        var label = (f && (f.label || f.field || f.key)) || "";
        var value = (f && (f.value != null ? f.value : f.magnitude)) || "";
        return "<tr><td>" + esc(label) + "</td><td>" + esc(value) + "</td></tr>";
      })
      .join("");
    content.innerHTML =
      '<section class="v2-ctsgis v2-ctsgis--admin">' +
      '<header class="v2-ctsgis__header">' + esc(payload.node_label || payload.node_id || "admin root") +
      " · " + esc(payload.node_id || "") + "</header>" +
      '<dl class="v2-ctsgis__meta">' +
      "<dt>capital</dt><dd>" + esc(payload.capital_msn_id || "—") + "</dd>" +
      "<dt>geometry</dt><dd>" + esc(payload.feature_count || 0) + " features" +
      (payload.has_real_projection ? "" : " (none — recompile)") + "</dd></dl>" +
      (fields.length
        ? '<div class="v2-ctsgis__tableWrap"><table class="v2-ctsgis__table"><tbody>' + rows + "</tbody></table></div>"
        : "") +
      "</section>";
  }

  // Per-kind SVG fill/stroke for the farm map.
  function _farmPolyStyle(kind) {
    if (kind === "plot") return { fill: "rgba(46,160,67,0.42)", stroke: "#2ea043" };
    if (kind === "field") return { fill: "rgba(214,158,46,0.20)", stroke: "#d69e2e" };
    if (kind === "parcel") return { fill: "rgba(31,111,235,0.05)", stroke: "#1f6feb" };
    return { fill: "rgba(31,111,235,0.10)", stroke: "#1f6feb" };
  }

  // Two-level geospatial projection window: OVERALL (parcels + the field with its plots faintly tiled)
  // ⇄ FIELD (click the field to zoom into it; plots become individually hoverable with a top-right label
  // popup; a top-left back arrow returns). Only the .v2-farm__map content changes — purely client-side,
  // no refetch. Works standalone AND inside the Agronomics FARM tab (renderComposite delegates here).
  // The field/plots map (geospatial_projection base, reused by plot_manager). Renders ONLY the
  // map; identity (profile card) is a sibling pane in the farm_profile composite.
  function renderGeospatialProjection(payload, content) {
    payload = payload || {};
    if (errorOr(payload, content)) return;
    var fc = payload.feature_collection || {};
    var features = Array.isArray(fc.features) ? fc.features : [];
    // Plot-selection mode (Plot Manager): when payload.selectable, field-view plots become
    // click-selectable (single / ctrl / shift); the chosen lcl nodes live in payload._selected.
    var selectable = !!payload.selectable;
    var selected = payload._selected || (payload._selected = new Set());
    var onSelect = typeof payload._onSelect === "function" ? payload._onSelect : function () {};

    var W = 460, H = 320, PAD = 12;

    // Fit-to-box equirectangular projection over an arbitrary feature subset (overall = all features,
    // field view = just the field + its plots, so the window zooms to the field's bounding box).
    function makeProjection(subset) {
      var pts = [];
      subset.forEach(function (f) {
        var g = (f && f.geometry) || {};
        ((g.coordinates && g.coordinates[0]) || []).forEach(function (c) {
          if (Array.isArray(c) && c.length >= 2) pts.push(c);
        });
      });
      if (!pts.length) return null;
      var minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
      pts.forEach(function (c) {
        if (c[0] < minx) minx = c[0]; if (c[0] > maxx) maxx = c[0];
        if (c[1] < miny) miny = c[1]; if (c[1] > maxy) maxy = c[1];
      });
      var sx = (maxx - minx) || 1e-9, sy = (maxy - miny) || 1e-9;
      var scale = Math.min((W - 2 * PAD) / sx, (H - 2 * PAD) / sy);
      return function (c) {
        var x = PAD + (c[0] - minx) * scale;
        var y = H - PAD - (c[1] - miny) * scale; // flip Y (north up)
        return x.toFixed(1) + "," + y.toFixed(1);
      };
    }

    function polySvg(f, proj, opts) {
      opts = opts || {};
      var g = (f && f.geometry) || {};
      var p = (f && f.properties) || {};
      var ring = (g.coordinates && g.coordinates[0]) || [];
      if (!ring.length || !proj) return "";
      var st = _farmPolyStyle(p.kind);
      var isSel = opts.plotHit && p.lcl_node && selected.has(p.lcl_node);
      var cls = "v2-farm__poly" + (opts.faint ? " is-faint" : "") + (isSel ? " is-selected" : "");
      var data = ' data-kind="' + esc(p.kind || "") + '" data-label="' + esc(p.label || "") + '"';
      if (opts.fieldTarget) data += ' data-fp-role="field"';
      if (opts.plotHit) {
        data += ' data-fp-plot="1"';
        if (p.lcl_node) data += ' data-lcl="' + esc(p.lcl_node) + '"';
      }
      return '<polygon class="' + cls + '" points="' + ring.map(proj).join(" ") +
        '" fill="' + st.fill + '" stroke="' + st.stroke + '" stroke-width="1"' + data +
        ' aria-label="' + esc((p.label || "") + " " + (p.kind || "")) + '"></polygon>';
    }

    function svgWrap(inner) {
      return '<svg class="v2-farm__svg" viewBox="0 0 ' + W + " " + H +
        '" width="100%" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Farm map">' +
        inner + "</svg>";
    }

    var parcels = features.filter(function (f) { return (f.properties || {}).kind === "parcel"; });
    var fieldFeats = features.filter(function (f) { return (f.properties || {}).kind === "field"; });
    // Single-field model: every plot belongs to the one field, so the field view shows them all
    // (no per-plot containment test needed — revisit if farm_profile ever carries multiple fields).
    var plots = features.filter(function (f) { return (f.properties || {}).kind === "plot"; });

    var mode = "overall";

    function paintOverall(host) {
      var proj = makeProjection(features);
      if (!proj) {
        host.innerHTML = '<p class="v2-farm__empty">No projectable geometry in this farm_profile.</p>';
        return;
      }
      // Layer: parcels (bottom) → plots faint (texture, non-interactive) → field (amber, on top, the
      // click target). The translucent field fill lets the faint plot tiling show through.
      var inner =
        parcels.map(function (f) { return polySvg(f, proj, {}); }).join("") +
        plots.map(function (f) { return polySvg(f, proj, { faint: true }); }).join("") +
        fieldFeats.map(function (f) { return polySvg(f, proj, { fieldTarget: true }); }).join("");
      host.innerHTML = svgWrap(inner);
    }

    function paintField(host) {
      var subset = fieldFeats.concat(plots);
      var proj = makeProjection(subset.length ? subset : features);
      if (!proj) { host.innerHTML = '<p class="v2-farm__empty">No field geometry.</p>'; return; }
      var inner =
        fieldFeats.map(function (f) { return polySvg(f, proj, {}); }).join("") +
        plots.map(function (f) { return polySvg(f, proj, { plotHit: true }); }).join("");
      host.innerHTML =
        '<button type="button" class="v2-farm__back" data-fp-back aria-label="Back to farm view">&larr; Farm</button>' +
        '<div class="v2-farm__plotLabel" data-fp-plotlabel hidden></div>' +
        svgWrap(inner);
    }

    function paintMap(host) {
      if (mode === "field" && fieldFeats.length) paintField(host); else paintOverall(host);
    }

    content.innerHTML =
      '<section class="v2-farm">' +
      '<header class="v2-farm__header">' + esc(payload.feature_count || features.length) +
      " features · plots: " + esc(payload.plots_source || "—") + "</header>" +
      '<div class="v2-farm__map" data-farm-map></div>' +
      "</section>";

    var host = content.querySelector("[data-farm-map]");
    if (!host) return;
    paintMap(host);

    // Delegated listeners — attached ONCE to the stable map host; survive paintMap re-renders.
    host.addEventListener("click", function (e) {
      var t = e.target;
      if (!t || !t.closest) return;
      if (t.closest("[data-fp-back]")) { mode = "overall"; paintMap(host); return; }
      if (selectable && mode === "field") {
        var plot = t.closest("[data-fp-plot]");
        if (plot && host.contains(plot)) {
          var ln = plot.getAttribute("data-lcl");
          if (ln) {
            if (e.ctrlKey || e.metaKey) { if (selected.has(ln)) selected.delete(ln); else selected.add(ln); }
            else if (e.shiftKey) { selected.add(ln); }
            else { selected.clear(); selected.add(ln); }  // single click = select just this one
            onSelect(selected);
            paintMap(host);
          }
          return;
        }
      }
      if (mode === "overall" && t.closest('[data-fp-role="field"]')) { mode = "field"; paintMap(host); }
    });
    host.addEventListener("mouseover", function (e) {
      var poly = e.target && e.target.closest ? e.target.closest("polygon") : null;
      if (!poly || !host.contains(poly)) return;
      poly.classList.add("is-hover"); // hover "indent"
      if (mode === "field" && poly.getAttribute("data-fp-plot")) {
        var lbl = host.querySelector("[data-fp-plotlabel]");
        if (lbl) { lbl.textContent = poly.getAttribute("data-label") || ""; lbl.hidden = false; }
      }
    });
    host.addEventListener("mouseout", function (e) {
      var poly = e.target && e.target.closest ? e.target.closest("polygon") : null;
      if (poly) poly.classList.remove("is-hover");
      if (mode === "field") {
        var lbl = host.querySelector("[data-fp-plotlabel]");
        if (lbl) { lbl.hidden = true; lbl.textContent = ""; }
      }
    });
  }

  // Plot Manager: the geospatial map (selectable) framed by a DATE widget above (inline-editable,
  // calendar icon) and a CREATE-cluster bar below. Drill into the field to select plots
  // (single/ctrl/shift), then ＋ records the union outline as a date-stamped cluster.
  function renderPlotManager(payload, content) {
    var asObject = function (x) { return x || {}; },
        asText = function (x) { return x == null ? "" : String(x); },
        escapeHtml = esc;
    payload = asObject(payload);
    if (errorOr(payload, content)) return;
    var today = asText(payload.today);
    var selected = new Set();
    content.innerHTML =
      '<section class="v2-plotmgr">' +
      '<div class="v2-plotmgr__date" title="Click the date to edit">' +
      '<span class="v2-plotmgr__cal" aria-hidden="true">📅</span>' +
      '<span class="v2-plotmgr__day" data-pm-day contenteditable="true" spellcheck="false">' +
      escapeHtml(today) + "</span></div>" +
      '<div class="v2-farm__map v2-plotmgr__map" data-farm-map></div>' +
      '<div class="v2-plotmgr__bar">' +
      '<span class="v2-plotmgr__count" data-pm-count>0 plots selected</span>' +
      '<button type="button" class="v2-plotmgr__create" data-pm-create>➕ create cluster</button>' +
      "</div>" +
      '<div class="v2-plotmgr__status" data-pm-status></div>' +
      "</section>";
    var host = content.querySelector("[data-farm-map]");
    var countEl = content.querySelector("[data-pm-count]");
    function onSel(set) {
      if (countEl) countEl.textContent = set.size + " plot" + (set.size === 1 ? "" : "s") + " selected";
    }
    payload._selected = selected;
    payload._onSelect = onSel;
    payload.selectable = true;
    if (host) renderGeospatialProjection(payload, host);
    var createBtn = content.querySelector("[data-pm-create]");
    var dayEl = content.querySelector("[data-pm-day]");
    var statusEl = content.querySelector("[data-pm-status]");
    if (createBtn) createBtn.addEventListener("click", function () {
      if (!selected.size) { statusEl.textContent = "Drill into the field and select plots first."; return; }
      statusEl.textContent = "Creating cluster…";
      fetch(asText(payload.create_route), {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "same-origin",
        body: JSON.stringify({ sandbox_id: asText(payload.sandbox_id) || "agro_erp",
          plot_nodes: Array.prototype.slice.call(selected), day: (dayEl.textContent || today).trim() }),
      }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (o) {
          if (!o.ok) { statusEl.textContent = "Error: " + ((o.j && o.j.error) || "create failed"); return; }
          statusEl.textContent = "Created " + ((o.j && (o.j.cluster_name || o.j.cluster)) || "cluster") + ".";
          if (window.PortalShellCore && typeof window.PortalShellCore.refetchOverlayPanels === "function") {
            window.PortalShellCore.refetchOverlayPanels({});
          }
        }).catch(function (e) { statusEl.textContent = "Error: " + e; });
    });
  }
  window.__MYCITE_V2_TOOL_RENDERERS = window.__MYCITE_V2_TOOL_RENDERERS || {};
  window.__MYCITE_V2_TOOL_RENDERERS["plot_manager"] = renderPlotManager;

  // Record form (Record Studio / Contract Editor): a field spec → inline inputs + a submit that
  // POSTs the field values to a domain write route, then refetches the overlay.
  function renderRecordForm(payload, content) {
    var asObject = function (x) { return x || {}; },
        asList = function (x) { return Array.isArray(x) ? x : []; },
        asText = function (x) { return x == null ? "" : String(x); },
        escapeHtml = esc;
    payload = asObject(payload);
    if (errorOr(payload, content)) return;
    var fields = asList(payload.fields);
    var inner = fields.map(function (f) {
      f = asObject(f);
      var key = asText(f.key), label = asText(f.label), type = asText(f.type) || "text", val = asText(f.value);
      var input;
      if (type === "select") {
        var opts = asList(f.options).map(function (o) {
          o = asObject(o); var ov = asText(o.value);
          return '<option value="' + escapeHtml(ov) + '"' + (ov === val ? " selected" : "") + ">" +
            escapeHtml(asText(o.label) || ov) + "</option>";
        }).join("");
        input = '<select data-form-field="' + escapeHtml(key) + '"><option value="">—</option>' + opts + "</select>";
      } else {
        input = '<input type="text" data-form-field="' + escapeHtml(key) + '" value="' + escapeHtml(val) + '" />';
      }
      return '<label class="v2-recordForm__field"><span>' + escapeHtml(label) + "</span>" + input + "</label>";
    }).join("");
    content.innerHTML =
      '<section class="v2-recordForm"><header class="v2-recordForm__header">' +
      escapeHtml(asText(payload.title)) + "</header>" +
      '<div class="v2-recordForm__fields">' + inner + "</div>" +
      '<button type="button" class="v2-recordForm__submit" data-form-submit>' +
      escapeHtml(asText(payload.submit_label) || "Save") + "</button>" +
      '<span class="v2-recordForm__status" data-form-status></span></section>';
    var sub = asObject(payload.submit_action);
    var btn = content.querySelector("[data-form-submit]");
    var statusEl = content.querySelector("[data-form-status]");
    if (btn) btn.addEventListener("click", function () {
      var body = { sandbox_id: asText(sub.sandbox_id) || "agro_erp" };
      if (asText(sub.datum_address)) body.datum_address = asText(sub.datum_address);
      Array.prototype.forEach.call(content.querySelectorAll("[data-form-field]"), function (el) {
        body[el.getAttribute("data-form-field")] = el.value;
      });
      statusEl.textContent = "Saving…";
      fetch(asText(sub.route), {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "same-origin",
        body: JSON.stringify(body),
      }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (o) {
          statusEl.textContent = o.ok ? ("Saved " + ((o.j && o.j.datum_address) || "")) : ("Error: " + ((o.j && o.j.error) || "save failed"));
          if (o.ok && window.PortalShellCore && typeof window.PortalShellCore.refetchOverlayPanels === "function") {
            window.PortalShellCore.refetchOverlayPanels({});
          }
        }).catch(function (e) { statusEl.textContent = "Error: " + e; });
    });
  }
  window.__MYCITE_V2_CONTAINER_RENDERERS = window.__MYCITE_V2_CONTAINER_RENDERERS || {};
  window.__MYCITE_V2_CONTAINER_RENDERERS["record_form"] = renderRecordForm;

  function renderContracts(payload, content) {
    payload = payload || {};
    if (errorOr(payload, content)) return;
    var contracts = Array.isArray(payload.contracts) ? payload.contracts : [];
    var drawDown = Array.isArray(payload.draw_down) ? payload.draw_down : [];
    var crows = contracts.map(function (c) {
      return "<tr><td>" + esc(c.date) + "</td><td>" + esc(c.invoice) + "</td><td>" +
        esc(c.plot) + "</td><td>" + esc(c.amount) + "</td><td>" + esc(c.cost) + "</td></tr>";
    }).join("");
    var drows = drawDown.map(function (d) {
      return '<tr' + (d.over_committed ? ' class="is-over"' : "") + "><td>" + esc(d.invoice) +
        "</td><td>" + esc(d.purchased_weight) + "</td><td>" + esc(d.committed) +
        "</td><td>" + esc(d.remaining) + "</td></tr>";
    }).join("");
    content.innerHTML =
      '<section class="v2-contracts">' +
      '<header class="v2-contracts__header">' + esc(payload.contract_count || 0) +
      " contracts · " + esc(payload.archetype || "") + "</header>" +
      (contracts.length
        ? '<table class="v2-contracts__table"><thead><tr><th>date</th><th>invoice</th>' +
          "<th>plot</th><th>amount</th><th>cost</th></tr></thead><tbody>" + crows + "</tbody></table>"
        : '<p class="v2-contracts__empty">No contracts yet — bind a plot to an invoice to create one.</p>') +
      (drawDown.length
        ? '<h4 class="v2-contracts__subhead">Weight draw-down</h4>' +
          '<table class="v2-contracts__drawdown"><thead><tr><th>invoice</th><th>purchased</th>' +
          "<th>committed</th><th>remaining</th></tr></thead><tbody>" + drows + "</tbody></table>"
        : "") +
      "</section>";
  }

  // Profile-card base renderer — the standardized profile (visual + title + SAMRAS chip). Shared by
  // the profile_card tool/container AND composed at the top of farm_profile (which builds on it).
  function _profileCardHtml(profile) {
    profile = profile || {};
    var title = esc(profile.title || "—");
    var samras = esc(profile.samras_node || "");
    var visual = profile.has_visual && profile.visual_url
      ? '<div class="v2-profileCard__visual"><img src="' + esc(profile.visual_url) + '" alt="" onerror="this.style.display=\'none\'" /></div>'
      : '<div class="v2-profileCard__visual v2-profileCard__visual--placeholder">' + esc((profile.title || "?").slice(0, 1).toUpperCase()) + "</div>";
    return '<div class="v2-profileCard">' + visual +
      '<div class="v2-profileCard__body"><div class="v2-profileCard__title">' + title + "</div>" +
      (samras ? '<div class="v2-profileCard__samras"><span class="v2-profileCard__chip">SAMRAS</span> ' + samras + "</div>" : "") +
      "</div></div>";
  }
  function renderProfileCard(payload, content) {
    payload = payload || {};
    if (errorOr(payload, content)) return;
    // Optional fields table (e.g. farm_profile's parcels/field/plots/plots_source counts) below
    // the identity card — the consolidation routes those through this pane's `fields`.
    var fields = Array.isArray(payload.fields) ? payload.fields : [];
    var rows = fields.map(function (f) {
      f = f || {};
      return "<tr><td>" + esc(f.label || "") + "</td><td>" + esc(f.value != null ? f.value : "") + "</td></tr>";
    }).join("");
    content.innerHTML = '<section class="v2-profile">' + _profileCardHtml(payload.profile) +
      (rows ? '<table class="v2-profile__fields"><tbody>' + rows + "</tbody></table>" : "") + "</section>";
  }

  window.__MYCITE_V2_TOOL_RENDERERS = window.__MYCITE_V2_TOOL_RENDERERS || {};
  window.__MYCITE_V2_TOOL_RENDERERS["cts_gis"] = renderCtsGisMap;
  // farm_profile is a composite now (profile_card + geospatial_projection) → renderComposite;
  // the map renderer is registered under geospatial_projection.
  window.__MYCITE_V2_TOOL_RENDERERS["geospatial_projection"] = renderGeospatialProjection;
  window.__MYCITE_V2_TOOL_RENDERERS["profile_card"] = renderProfileCard;
  // contracts now renders via the shared record_table container (Contract Viewer extends
  // RecordViewerBase); its weight draw-down rides record_table's extra_tables. (renderContracts
  // kept below for reference but no longer registered.)
  // samras_structure renders via the cluster dendrogram (renderSamrasDendrogram), defined
  // and registered in IIFE#1 alongside clusterLayout (the Resource type-browser diagram).
  window.__MYCITE_V2_TOOL_RENDERERS["cts_gis_district"] = renderCtsGisDistrict;
  window.__MYCITE_V2_TOOL_RENDERERS["cts_gis_admin"] = renderCtsGisAdmin;

  // ---- Declarative container renderers (consolidation spine) --------------- //
  // A tool whose panel_payload declares {container: "<kind>", ...} is painted by
  // one shared renderer instead of a bespoke per-tool_id function. v2_portal_shell
  // _core falls back to these when no tool_id-keyed renderer exists. New datum-doc
  // viewers (invoices/contacts/plots/…) ride these — no new JS per tool.

  function renderRecordTable(payload, content) {
    payload = payload || {};
    if (errorOr(payload, content)) return;
    var cols = Array.isArray(payload.columns) ? payload.columns : [];
    var rows = Array.isArray(payload.rows) ? payload.rows : [];
    var rck = payload.row_class_key;
    var head = "<tr>" + cols.map(function (c) { return "<th>" + esc(c) + "</th>"; }).join("") + "</tr>";
    var body = rows.map(function (r) {
      r = r || {};
      var cls = rck && r[rck] ? ' class="is-flagged"' : "";
      return "<tr" + cls + ">" + cols.map(function (c) {
        return "<td>" + esc(r[c] != null ? r[c] : "") + "</td>";
      }).join("") + "</tr>";
    }).join("");
    // Optional back affordance: payload.back = {label, param, value}. Renders a ← bar that
    // clears the overlay param via setSurfaceQuery (drives the agronomics full-tab takeover
    // exit). Generic — any record_table can opt in.
    var back = payload.back && typeof payload.back === "object" ? payload.back : null;
    var backBar = back
      ? '<button type="button" class="v2-recordTable__back" data-record-back="' +
        esc(back.param || "") + '" data-record-back-value="' + esc(back.value != null ? back.value : "") +
        '">&larr; ' + esc(back.label || "Back") + "</button>"
      : "";
    // Optional secondary tables (e.g. the contracts invoice draw-down) rendered below the main.
    function tableHtml(c, r) {
      var h = "<tr>" + c.map(function (x) { return "<th>" + esc(x) + "</th>"; }).join("") + "</tr>";
      var b = (Array.isArray(r) ? r : []).map(function (row) {
        row = row || {};
        return "<tr>" + c.map(function (x) { return "<td>" + esc(row[x] != null ? row[x] : "") + "</td>"; }).join("") + "</tr>";
      }).join("");
      return '<div class="v2-recordTable__wrap"><table class="v2-recordTable__table"><thead>' +
        h + "</thead><tbody>" + b + "</tbody></table></div>";
    }
    var extra = (Array.isArray(payload.extra_tables) ? payload.extra_tables : []).map(function (t) {
      t = t || {};
      return '<header class="v2-recordTable__header">' + esc(t.title || "") + "</header>" +
        tableHtml(Array.isArray(t.columns) ? t.columns : [], t.rows);
    }).join("");
    content.innerHTML =
      '<section class="v2-recordTable">' +
      backBar +
      '<header class="v2-recordTable__header">' + esc(payload.title || "") +
      (payload.count_label ? " · " + esc(payload.count_label) : "") + "</header>" +
      (rows.length
        ? '<div class="v2-recordTable__wrap"><table class="v2-recordTable__table"><thead>' +
          head + "</thead><tbody>" + body + "</tbody></table></div>"
        : '<p class="v2-recordTable__empty">' + esc(payload.empty_text || "No records.") + "</p>") +
      extra +
      "</section>";
    if (back) {
      var backBtn = content.querySelector("[data-record-back]");
      if (backBtn) backBtn.addEventListener("click", function () {
        if (window.PortalShellCore && typeof window.PortalShellCore.setSurfaceQuery === "function") {
          window.PortalShellCore.setSurfaceQuery(
            backBtn.getAttribute("data-record-back"),
            backBtn.getAttribute("data-record-back-value") || "");
        }
      });
    }
  }

  function renderRecordList(payload, content) {
    payload = payload || {};
    if (errorOr(payload, content)) return;
    var items = Array.isArray(payload.items) ? payload.items : [];
    function card(it) {
      it = it || {};
      var fields = (Array.isArray(it.fields) ? it.fields : []).map(function (f) {
        f = f || {};
        return '<div class="v2-recordList__field"><label>' + esc(f.label || "") +
          "</label><div>" + esc(f.value != null && f.value !== "" ? f.value : "—") + "</div></div>";
      }).join("");
      var hay = ((it.title || "") + " " + (it.subtitle || "")).toLowerCase();
      return '<article class="v2-recordList__item" data-search="' + esc(hay) + '"><h4>' +
        esc(it.title || "") + "</h4>" +
        (it.subtitle ? '<p class="v2-recordList__subtitle">' + esc(it.subtitle) + "</p>" : "") +
        '<div class="v2-recordList__fields">' + fields + "</div></article>";
    }
    content.innerHTML =
      '<section class="v2-recordList">' +
      '<header class="v2-recordList__header">' + esc(payload.title || "") +
      (payload.count_label ? " · " + esc(payload.count_label) : "") + "</header>" +
      '<input type="search" class="v2-recordList__search" placeholder="' +
      esc(payload.search_placeholder || "Search…") + '" aria-label="Search records" />' +
      '<div class="v2-recordList__items">' +
      (items.length ? items.map(card).join("")
                    : '<p class="v2-recordList__empty">' + esc(payload.empty_text || "No records.") + "</p>") +
      "</div></section>";
    var inp = content.querySelector(".v2-recordList__search");
    var cards = content.querySelectorAll(".v2-recordList__item");
    if (inp) inp.addEventListener("input", function () {
      var q = (inp.value || "").trim().toLowerCase();
      Array.prototype.forEach.call(cards, function (c) {
        c.style.display = (!q || (c.getAttribute("data-search") || "").indexOf(q) !== -1) ? "" : "none";
      });
    });
  }

  // Generic composite container: lay out N panes side by side, delegating each pane's
  // body to its own tool (or container) renderer. The seam for multi-tool sections — a
  // composite is just a declaration of panes (see tools/agronomics_viewer.py), so a
  // section can be reworked, or new composites assembled, without touching the sub-tools.
  function renderComposite(payload, content) {
    payload = payload || {};
    if (errorOr(payload, content)) return;
    var panes = Array.isArray(payload.panes) ? payload.panes : [];
    if (!panes.length) {
      content.innerHTML = '<p class="ide-visualizationPanel__empty">No panes to display.</p>';
      return;
    }
    // direction "column" stacks panes vertically (e.g. the PLAN tab: top row over a bottom bar).
    var dirCls = payload.direction === "column" ? " v2-composite--column" : "";
    content.innerHTML =
      '<div class="v2-composite' + dirCls + '">' +
      panes
        .map(function (p, i) {
          p = p || {};
          var pcls = "v2-composite__pane" + (p.label ? "" : " v2-composite__pane--unlabeled");
          return '<section class="' + pcls + '" data-pane-index="' + i + '">' +
            (p.label ? '<header class="v2-composite__paneHeader">' + esc(p.label) + "</header>" : "") +
            '<div class="v2-composite__paneBody" data-pane-body></div></section>';
        })
        .join("") +
      "</div>";
    var bodies = content.querySelectorAll("[data-pane-body]");
    panes.forEach(function (p, i) {
      p = p || {};
      var body = bodies[i];
      if (body) paintPanelInto(p.panel_payload, body, p.tool_id);
    });
  }

  // Shared pane/tab body dispatch: render a panel_payload into `node` using the tool_id
  // renderer (the caller's hint, else the payload's own tool_id) first, otherwise the
  // declarative container renderer keyed by panel_payload.container. Used by renderComposite
  // (panes) and renderTabbed (tabs) so both delegate identically.
  function paintPanelInto(panelPayload, node, toolIdHint) {
    if (!node) return;
    var sub = panelPayload || {};
    var toolRenderers = window.__MYCITE_V2_TOOL_RENDERERS || {};
    var containerRenderers = window.__MYCITE_V2_CONTAINER_RENDERERS || {};
    var fn =
      (toolIdHint && toolRenderers[toolIdHint]) ||
      (sub.tool_id && toolRenderers[sub.tool_id]) ||
      containerRenderers[(sub.container) || ""];
    if (typeof fn === "function") {
      try {
        fn(sub, node);
      } catch (err) {
        node.innerHTML =
          '<p class="ide-visualizationPanel__error">Pane render failed: ' +
          esc(err && err.message ? err.message : String(err)) + "</p>";
      }
    } else if (sub.error) {
      node.innerHTML =
        '<p class="ide-visualizationPanel__error">' + esc(String(sub.error)) + "</p>";
    } else {
      node.innerHTML =
        '<p class="ide-visualizationPanel__empty">No renderer for <code>' +
        esc(sub.container || sub.tool_id || toolIdHint || "") + "</code>.</p>";
    }
  }

  // Generic tabbed container: a tab strip + one body, switched CLIENT-SIDE (no shell reload —
  // contrast renderExtensionTabs, which reloads via ctx.loadShell). Each tab carries an
  // optional panel_payload delegated via paintPanelInto; a null payload renders a scaffold
  // placeholder. Drives the agronomics FARM/PLAN/NETWORK tabs (tools/agronomics_viewer.py).
  function renderTabbed(payload, content) {
    payload = payload || {};
    if (errorOr(payload, content)) return;
    var tabs = Array.isArray(payload.tabs) ? payload.tabs : [];
    if (!tabs.length) {
      content.innerHTML = '<p class="ide-visualizationPanel__empty">No tabs to display.</p>';
      return;
    }
    var requestedActive = payload.active_tab || (tabs[0] && tabs[0].id) || "";
    var active = "";
    for (var ai = 0; ai < tabs.length; ai++) {
      if (tabs[ai] && tabs[ai].id === requestedActive) { active = requestedActive; break; }
    }
    if (!active) active = (tabs[0] && tabs[0].id) || "";
    content.innerHTML =
      '<div class="v2-tabbed">' +
      '<div class="v2-tabbed__strip" role="tablist">' +
      tabs
        .map(function (t) {
          t = t || {};
          var on = t.id === active;
          return (
            '<button type="button" class="v2-tabbed__tab' + (on ? " is-active" : "") +
            '" role="tab" aria-selected="' + (on ? "true" : "false") +
            '" data-tab-id="' + esc(t.id) + '">' + esc(t.label || t.id) + "</button>"
          );
        })
        .join("") +
      "</div>" +
      '<div class="v2-tabbed__body" data-tabbed-body></div>' +
      "</div>";
    var bodyNode = content.querySelector("[data-tabbed-body]");
    var strip = content.querySelector(".v2-tabbed__strip");

    function paintTab(tabId) {
      var tab = null;
      for (var i = 0; i < tabs.length; i++) {
        if (tabs[i] && tabs[i].id === tabId) { tab = tabs[i]; break; }
      }
      if (!tab) tab = tabs[0] || {};
      if (!bodyNode) return;
      if (tab.panel_payload == null) {
        bodyNode.innerHTML =
          '<p class="v2-tabbed__placeholder">' +
          esc((tab.label || tab.id || "This tab") + " — no sub-tools yet.") + "</p>";
        return;
      }
      paintPanelInto(tab.panel_payload, bodyNode, tab.tool_id);
    }

    if (strip) {
      strip.addEventListener("click", function (ev) {
        var btn = ev.target && ev.target.closest ? ev.target.closest("[data-tab-id]") : null;
        if (!btn) return;
        Array.prototype.forEach.call(strip.querySelectorAll(".v2-tabbed__tab"), function (b) {
          var on = b === btn;
          b.classList.toggle("is-active", on);
          b.setAttribute("aria-selected", on ? "true" : "false");
        });
        var tabId = btn.getAttribute("data-tab-id");
        paintTab(tabId);
        // Persist the chosen tab into the overlay param set so a later sub-tool refetch
        // (e.g. the SAMRAS structure selector) re-opens on this tab instead of resetting.
        if (payload.tab_query_param && window.PortalShellCore &&
            typeof window.PortalShellCore.recordOverlayParam === "function") {
          window.PortalShellCore.recordOverlayParam(payload.tab_query_param, tabId);
        }
      });
    }
    paintTab(active);
  }


  // Synopsis: a compact derived-figure widget (label · figure), e.g. the PLAN tab's
  // far-right inventory (product → unit count). Not a full table — a short summary list.
  function renderSynopsis(payload, content) {
    payload = payload || {};
    if (errorOr(payload, content)) return;
    var items = Array.isArray(payload.items) ? payload.items : [];
    var rows = items.map(function (it) {
      it = it || {};
      return '<li class="v2-synopsis__row"><span class="v2-synopsis__label">' +
        esc(it.label != null ? it.label : "") + '</span><span class="v2-synopsis__figure">' +
        esc(it.figure != null ? it.figure : "") + "</span></li>";
    }).join("");
    content.innerHTML =
      '<section class="v2-synopsis">' +
      '<header class="v2-synopsis__header">' + esc(payload.title || "") +
      (payload.count_label ? " · " + esc(payload.count_label) : "") + "</header>" +
      (payload.value_label
        ? '<div class="v2-synopsis__colhead"><span></span><span>' + esc(payload.value_label) + "</span></div>"
        : "") +
      (items.length
        ? '<ul class="v2-synopsis__list">' + rows + "</ul>"
        : '<p class="v2-synopsis__empty">' + esc(payload.empty_text || "Nothing to summarize.") + "</p>") +
      "</section>";
  }

  window.__MYCITE_V2_CONTAINER_RENDERERS = window.__MYCITE_V2_CONTAINER_RENDERERS || {};
  window.__MYCITE_V2_CONTAINER_RENDERERS["record_table"] = renderRecordTable;
  window.__MYCITE_V2_CONTAINER_RENDERERS["record_list"] = renderRecordList;
  window.__MYCITE_V2_CONTAINER_RENDERERS["composite"] = renderComposite;
  window.__MYCITE_V2_CONTAINER_RENDERERS["tabbed"] = renderTabbed;
  window.__MYCITE_V2_CONTAINER_RENDERERS["profile_card"] = renderProfileCard;
  window.__MYCITE_V2_CONTAINER_RENDERERS["synopsis"] = renderSynopsis;
})();
