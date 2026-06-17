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
  function renderDendrogram(nodes, p, collapsed) {
    var lay = clusterLayout(nodes, collapsed);
    var paths = lay.links.map(function (l) {
      var mx = (l.sx + l.tx) / 2;
      return '<path class="v2-dendro__link" d="M' + l.sx + "," + l.sy +
        "C" + mx + "," + l.sy + " " + mx + "," + l.ty + " " + l.tx + "," + l.ty + '" />';
    }).join("");
    var svg = '<svg class="v2-dendro__links" width="' + lay.width + '" height="' + lay.height +
      '" viewBox="0 0 ' + lay.width + " " + lay.height + '" aria-hidden="true">' + paths + "</svg>";
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
    return (
      '<div class="v2-dendro__toolbar">' +
      '<button type="button" class="v2-dendro__all" data-dendro-all="expand">Expand all</button>' +
      '<button type="button" class="v2-dendro__all" data-dendro-all="collapse">Collapse all</button>' +
      "</div>" +
      '<div class="v2-dendro" style="width:' + lay.width + "px;height:" + lay.height + 'px">' +
      svg + nodeHtml + "</div>"
    );
  }

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
  function _ideRowCells(cell, columns) {
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
        case "magnitude":
          return head ? _ideCellText(head[slot++]) : "";
        case "references": {
          var rest = head ? head.slice(slot).map(_ideCellText).join(", ") : "";
          if (head) slot = head.length;
          return rest;
        }
        case "record_key":
          return (tail && typeof tail === "object" && !Array.isArray(tail)) ? _ideCellText(tail[col.key]) : "";
        case "value":
          return _ideCellText(raw);
        default:
          return "";
      }
    });
  }
  function renderDatumIdeGridRow(cell, columns) {
    var values = _ideRowCells(cell, columns);
    var tds = columns.map(function (col, i) {
      var full = values[i];
      var shown = _ideTruncate(full, 28);
      return '<td class="v2-ide__cell v2-ide__cell--' + escapeHtml(col.role) + '" title="' +
        escapeHtml(full) + '">' +
        (shown ? escapeHtml(shown) : '<span class="v2-ide__blank">·</span>') + "</td>";
    }).join("");
    return '<tr class="v2-ide__row' + (cell.selected ? " is-selected" : "") +
      '" data-datum-address="' + escapeHtml(asText(cell.datum_address)) + '">' + tds + "</tr>";
  }
  function renderDatumIdeValueGroup(group) {
    var columns = asList(group.column_template);
    if (!columns.length) columns = [{ role: "address" }];
    var cells = asList(group.cells);
    var headCells = columns.map(function (col) {
      return '<th class="v2-ide__col v2-ide__col--' + escapeHtml(col.role) + '">' +
        escapeHtml(_ideColumnLabel(col)) + "</th>";
    }).join("");
    var bodyRows = cells.map(function (cell) { return renderDatumIdeGridRow(cell, columns); }).join("");
    return '<section class="v2-ide__valueGroup" data-value-group-id="' +
      escapeHtml(String(asObject(group).value_group)) + '">' +
      '<header class="v2-ide__vgHeader"><h5>' +
      escapeHtml(asText(group.title) || ("Value Group " + asObject(group).value_group)) +
      "</h5><small>" + cells.length + " datum" + (cells.length === 1 ? "" : "s") + "</small></header>" +
      '<div class="v2-tableWrap"><table class="v2-table v2-ide__table"><thead><tr>' + headCells +
      "</tr></thead><tbody>" + bodyRows + "</tbody></table></div></section>";
  }
  function renderDatumIdeGrid(datumGrid) {
    var layers = asList(datumGrid.layers);
    if (!layers.length) {
      return '<div class="v2-ide" data-region="datum-ide"><p class="v2-workbenchUi__empty">' +
        "No datum rows yet — use the composer above to author the first datum.</p></div>";
    }
    var sections = layers.map(function (layer) {
      var layerId = String(asObject(layer).layer);
      var vgs = asList(layer.value_groups).map(renderDatumIdeValueGroup).join("");
      return '<section class="v2-ide__layer" data-layer-id="' + escapeHtml(layerId) + '">' +
        '<header class="v2-ide__layerHeader"><h4>' +
        escapeHtml(asText(layer.title) || ("Layer " + layerId)) + "</h4></header>" + vgs + "</section>";
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
        renderDatumComposer(workspace, surfacePayload) +
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
      "<h3>" +
      escapeHtml(shortDocumentLabel(docLabel) || docLabel || docId) +
      "</h3>" +
      "<small>" +
      escapeHtml(docId) +
      "</small></header>" +
      renderDatumComposer(workspace, surfacePayload) +
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
      var payloadText;
      try {
        if (mode === "raw") {
          var textarea = rowRawTextarea(rowEl);
          payloadText = textarea ? textarea.value : "";
          JSON.parse(payloadText);  // throw if invalid JSON before staging
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
        operation: "update_row_raw",
        payload_text: payloadText,
      };
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

  function bindWorkbenchNavigation(ctx, target, workspace, surfacePayload, region) {
    bindDocumentColumn(ctx, target, workspace, surfacePayload || {});
    bindDatumComposer(ctx, target, workspace, surfacePayload || {});
    bindDocumentEditor(ctx, target, workspace, surfacePayload || {});
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

  function renderFarmProfile(payload, content) {
    payload = payload || {};
    if (errorOr(payload, content)) return;
    var fc = payload.feature_collection || {};
    var features = Array.isArray(fc.features) ? fc.features : [];
    var fields = Array.isArray(payload.fields) ? payload.fields : [];

    // Collect all lon/lat for a shared projection (equirectangular fit-to-box).
    var pts = [];
    features.forEach(function (f) {
      var g = (f && f.geometry) || {};
      ((g.coordinates && g.coordinates[0]) || []).forEach(function (c) {
        if (Array.isArray(c) && c.length >= 2) pts.push(c);
      });
    });
    var W = 460, H = 320, PAD = 12, svg = "";
    if (pts.length) {
      var minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
      pts.forEach(function (c) {
        if (c[0] < minx) minx = c[0]; if (c[0] > maxx) maxx = c[0];
        if (c[1] < miny) miny = c[1]; if (c[1] > maxy) maxy = c[1];
      });
      var sx = (maxx - minx) || 1e-9, sy = (maxy - miny) || 1e-9;
      var scale = Math.min((W - 2 * PAD) / sx, (H - 2 * PAD) / sy);
      var proj = function (c) {
        var x = PAD + (c[0] - minx) * scale;
        var y = H - PAD - (c[1] - miny) * scale; // flip Y (north up)
        return x.toFixed(1) + "," + y.toFixed(1);
      };
      var paths = features.map(function (f) {
        var g = (f && f.geometry) || {};
        var p = (f && f.properties) || {};
        var ring = (g.coordinates && g.coordinates[0]) || [];
        if (!ring.length) return "";
        var pointsAttr = ring.map(proj).join(" ");
        var isPlot = p.kind === "plot";
        var fill = isPlot ? "rgba(46,160,67,0.35)" : "rgba(31,111,235,0.12)";
        var stroke = isPlot ? "#2ea043" : "#1f6feb";
        return '<polygon points="' + pointsAttr + '" fill="' + fill +
          '" stroke="' + stroke + '" stroke-width="1"><title>' +
          esc(p.label || "") + " (" + esc(p.kind || "") + ")</title></polygon>";
      }).join("");
      svg = '<svg class="v2-farm__svg" viewBox="0 0 ' + W + " " + H +
        '" width="100%" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Farm map">' +
        paths + "</svg>";
    } else {
      svg = '<p class="v2-farm__empty">No projectable geometry in this farm_profile.</p>';
    }

    var fieldRows = fields.map(function (f) {
      return "<tr><td>" + esc(f.label || "") + "</td><td>" + esc(f.value != null ? f.value : "") + "</td></tr>";
    }).join("");

    content.innerHTML =
      '<section class="v2-farm">' +
      '<header class="v2-farm__header">' + esc(payload.feature_count || features.length) +
      " features · plots: " + esc(payload.plots_source || "—") + "</header>" +
      '<div class="v2-farm__map">' + svg + "</div>" +
      (fieldRows
        ? '<table class="v2-farm__values"><tbody>' + fieldRows + "</tbody></table>"
        : "") +
      "</section>";
  }

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

  function renderTxaTreeNode(node) {
    node = node || {};
    var isEmpty = node.status === "empty";
    var head =
      '<span class="v2-txatree__addr">' + esc(node.address || "") + "</span> " +
      (isEmpty
        ? '<span class="v2-txatree__emptyTag">(undefined — denoted by magnitude)</span>'
        : '<span class="v2-txatree__label">' + esc(node.label || "") + "</span>");
    var kids = Array.isArray(node.children) ? node.children : [];
    if (kids.length) {
      return (
        '<details class="v2-txatree__node' + (isEmpty ? " is-empty" : "") + '">' +
        "<summary>" + head + "</summary>" +
        kids.map(renderTxaTreeNode).join("") +
        "</details>"
      );
    }
    return '<div class="v2-txatree__leaf' + (isEmpty ? " is-empty" : "") + '">' + head + "</div>";
  }

  function renderTxaTree(payload, content) {
    // Collapsible node-address tree: DEFINED nodes show their label; EMPTY nodes
    // (denoted by the anchor magnitude but not defined in txa) are flagged. Collapsed
    // by default so a 1000+ node tree only paints expanded branches.
    payload = payload || {};
    if (errorOr(payload, content)) return;
    var tree = Array.isArray(payload.tree) ? payload.tree : [];
    content.innerHTML =
      '<section class="v2-txatree">' +
      '<header class="v2-txatree__header">' +
      esc(payload.magnitude || "txa") + " magnitude · " +
      esc(payload.denoted_count || 0) + " denoted · " +
      esc(payload.defined_count || 0) + " defined · " +
      esc(payload.empty_count || 0) + " empty</header>" +
      '<div class="v2-txatree__body">' +
      (tree.length
        ? tree.map(renderTxaTreeNode).join("")
        : '<p class="v2-txatree__empty">No nodes denoted by the magnitude.</p>') +
      "</div></section>";
  }

  window.__MYCITE_V2_TOOL_RENDERERS = window.__MYCITE_V2_TOOL_RENDERERS || {};
  window.__MYCITE_V2_TOOL_RENDERERS["cts_gis"] = renderCtsGisMap;
  window.__MYCITE_V2_TOOL_RENDERERS["farm_profile"] = renderFarmProfile;
  window.__MYCITE_V2_TOOL_RENDERERS["contracts"] = renderContracts;
  window.__MYCITE_V2_TOOL_RENDERERS["txa_tree"] = renderTxaTree;
  // lcl_structure shares txa_tree's payload shape (tree/denoted/defined/empty), so it
  // reuses the same renderer; the header reads "lcl magnitude" from payload.magnitude.
  window.__MYCITE_V2_TOOL_RENDERERS["lcl_structure"] = renderTxaTree;
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
    content.innerHTML =
      '<section class="v2-recordTable">' +
      '<header class="v2-recordTable__header">' + esc(payload.title || "") +
      (payload.count_label ? " · " + esc(payload.count_label) : "") + "</header>" +
      (rows.length
        ? '<div class="v2-recordTable__wrap"><table class="v2-recordTable__table"><thead>' +
          head + "</thead><tbody>" + body + "</tbody></table></div>"
        : '<p class="v2-recordTable__empty">' + esc(payload.empty_text || "No records.") + "</p>") +
      "</section>";
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

  window.__MYCITE_V2_CONTAINER_RENDERERS = window.__MYCITE_V2_CONTAINER_RENDERERS || {};
  window.__MYCITE_V2_CONTAINER_RENDERERS["record_table"] = renderRecordTable;
  window.__MYCITE_V2_CONTAINER_RENDERERS["record_list"] = renderRecordList;
})();
