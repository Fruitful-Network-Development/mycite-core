/**
 * Workbench renderer for the one-shell portal.
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
        return (
          '<button type="button" class="v2-granteeSelector__option' +
          (active ? " is-active" : "") +
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
    return (
      '<button type="button" class="v2-rowAction v2-rowAction--' +
      escapeHtml(variant) +
      '"' +
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

  function renderMailboxesTable(rows) {
    // Phase 16c: Domain column so operators of multi-domain grantees
    // (e.g. CVCC owns cvcc + cvccboard) can tell which mailbox lives
    // where. Rows are sorted by domain then mailbox server-side.
    return renderRowsTableWithActions(
      "Mailboxes",
      rows,
      [
        { key: "domain", label: "Domain" },
        { key: "mailbox", label: "Mailbox" },
        { key: "send_as", label: "Send-as" },
        { key: "role", label: "Role" },
        { key: "lifecycle", label: "Lifecycle" },
        { key: "inbound", label: "Inbound" },
      ],
      "suspend_action",
      "Actions"
    );
  }

  function renderExtensionCardBody(payload) {
    var p = asObject(payload);
    var html = "";

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
    if (asList(p.profiles).length) {
      html += renderMailboxesTable(p.profiles);
    }
    if (asText(p.empty_message) && !html) {
      html += '<p class="v2-extensionCard__empty">' + escapeHtml(asText(p.empty_message)) + "</p>";
    }
    return html;
  }

  function renderExtensions(extensions) {
    var list = asList(extensions);
    if (!list.length) return "";
    return (
      '<div class="v2-extensions">' +
      list
        .map(function (entry) {
          var e = asObject(entry);
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

  function bindExtensionActions(ctx, target, extensions) {
    if (!target || !extensions || !extensions.length) return;
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
          escapeHtml(stripJsonSuffix(row.document_name || row.label || row.document_id || "—")) +
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

  function renderWorkbenchSummary(workspace) {
    var selectedDocument = asObject(workspace.selected_document);
    var selectedRow = asObject(workspace.selected_row);
    var query = asObject(workspace.query);
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Current Lens</h3>' +
      '<dl class="v2-surface-dl">' +
      "<dt>document</dt><dd><strong>" +
      escapeHtml(selectedDocument.canonical_name || selectedDocument.document_name || selectedDocument.document_id || "—") +
      "</strong></dd>" +
      "<dt>version</dt><dd><strong>" +
      escapeHtml(selectedDocument.version_hash || "—") +
      "</strong></dd>" +
      "<dt>row</dt><dd><strong>" +
      escapeHtml(selectedRow.datum_address || "—") +
      "</strong></dd>" +
      "<dt>group</dt><dd><strong>" +
      escapeHtml(query.group || workspace.datum_grid.group_mode || "flat") +
      "</strong></dd>" +
      "<dt>lens</dt><dd><strong>" +
      escapeHtml(query.workbench_lens || workspace.datum_grid.lens || "interpreted") +
      "</strong></dd>" +
      "<dt>source</dt><dd><strong>" +
      escapeHtml(query.source || workspace.source_visibility || "show") +
      "</strong></dd>" +
      "<dt>overlay</dt><dd><strong>" +
      escapeHtml(query.overlay || workspace.overlay_visibility || "show") +
      "</strong></dd>" +
      "</dl></section>"
    );
  }

  function renderWorkbenchNavigation(workspace) {
    var navigation = asObject(workspace.navigation);
    var buttons = [];
    [
      ["previous_document", "Previous Document"],
      ["next_document", "Next Document"],
      ["previous_row", "Previous Row"],
      ["next_row", "Next Row"],
    ].forEach(function (entry) {
      var item = asObject(navigation[entry[0]]);
      if (!item.shell_request) return;
      buttons.push(
        '<button class="v2-workbenchUi__navButton" type="button" data-workbench-nav-key="' +
          escapeHtml(entry[0]) +
          '">' +
          escapeHtml(entry[1]) +
          '<small>' +
          escapeHtml(item.label || item.id || "—") +
          "</small></button>"
      );
    });
    if (!buttons.length) return "";
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Navigation</h3><div class="v2-workbenchUi__navButtons">' +
      buttons.join("") +
      "</div></section>"
    );
  }

  function renderWorkbenchSurface(surfacePayload) {
    var workspace = asObject(surfacePayload.workspace);
    var documentTable = asObject(workspace.document_table);
    var datumGrid = asObject(workspace.datum_grid);
    var groups = asList(datumGrid.groups);
    var layers = asList(datumGrid.layers);
    var lens = asText(datumGrid.lens) || "interpreted";
    var sourceVisibility = asText(workspace.source_visibility) || "show";
    var offset = 0;
    var groupHtml = groups
      .map(function (group) {
        var html = renderDatumGroup(asObject(group), lens, offset);
        offset += asList(asObject(group).items).length;
        return html;
      })
      .join("");
    var matrixHtml = renderDatumMatrix(layers);
    var flatRows = asList(datumGrid.rows);
    return (
      renderCards(surfacePayload.cards || []) +
      renderWorkbenchSummary(workspace) +
      '<div class="v2-workbenchUi__layout">' +
      '<section class="v2-card v2-workbenchUi__pane"><div class="v2-workbenchUi__paneHeader"><h3>Document Table</h3><p>Read-only authoritative documents keyed by SQL version identity.</p></div>' +
      '<div class="v2-tableWrap v2-workbenchUi__tableWrap">' +
      '<table class="v2-table v2-workbenchUiTable"><thead class="v2-workbenchUi__stickyHeader"><tr>' +
      "<th>Document</th>" +
      (sourceVisibility === "hide" ? "" : "<th>Source</th>") +
      "<th>Version</th><th>Rows</th><th>Action</th>" +
      "</tr></thead><tbody>" +
      renderDocumentRows(asList(documentTable.rows), sourceVisibility) +
      "</tbody></table></div></section>" +
      '<section class="v2-card v2-workbenchUi__pane"><div class="v2-workbenchUi__paneHeader"><h3>Datum Grid</h3><p>' +
      escapeHtml(
        lens === "raw"
          ? "Canonical datum rows rendered through the raw payload lens."
          : "Spreadsheet-like interpreted rows for the selected authoritative document."
      ) +
      "</p></div>" +
      (asText(datumGrid.group_mode) === "layer_value_group_iteration" && layers.length
        ? matrixHtml
        : groups.length
        ? groupHtml
        : '<div class="v2-tableWrap v2-workbenchUi__tableWrap"><table class="v2-table v2-workbenchUiTable"><thead class="v2-workbenchUi__stickyHeader"><tr><th>Datum</th><th>' +
          escapeHtml(lens === "raw" ? "Raw Payload" : "Interpreted Row") +
          "</th><th>Identity</th><th>Action</th></tr></thead><tbody>" +
          renderDatumRows(flatRows, { lens: lens, offset: 0 }) +
          "</tbody></table></div>") +
      "</section></div>" +
      renderWorkbenchNavigation(workspace) +
      renderNotes(surfacePayload.notes || [])
    );
  }

  function bindWorkbenchNavigation(ctx, target, workspace) {
    var documents = asList(asObject(workspace.document_table).rows);
    var datumRows = flattenDatumRows(workspace);
    var navigation = asObject(workspace.navigation);

    function loadRequest(request) {
      if (!request || typeof ctx.loadShell !== "function") return;
      ctx.loadShell(request);
    }

    function bindSelectableRows(selector, attrName, items) {
      Array.prototype.forEach.call(target.querySelectorAll(selector), function (node) {
        var index = Number(node.getAttribute(attrName));
        if (Number.isNaN(index) || index < 0 || index >= items.length) return;
        var item = items[index] || {};
        node.addEventListener("click", function (event) {
          if (event.target && event.target.closest && event.target.closest("button")) return;
          loadRequest(item.shell_request);
        });
        node.addEventListener("keydown", function (event) {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            loadRequest(item.shell_request);
            return;
          }
          if (event.key === "ArrowDown" && index + 1 < items.length) {
            event.preventDefault();
            loadRequest((items[index + 1] || {}).shell_request);
            return;
          }
          if (event.key === "ArrowUp" && index - 1 >= 0) {
            event.preventDefault();
            loadRequest((items[index - 1] || {}).shell_request);
          }
        });
      });
    }

    Array.prototype.forEach.call(target.querySelectorAll("button[data-workbench-document-index]"), function (button) {
      button.addEventListener("click", function () {
        var index = Number(button.getAttribute("data-workbench-document-index"));
        if (Number.isNaN(index) || index < 0 || index >= documents.length) return;
        loadRequest((documents[index] || {}).shell_request);
      });
    });

    Array.prototype.forEach.call(target.querySelectorAll("button[data-workbench-row-index]"), function (button) {
      button.addEventListener("click", function () {
        var index = Number(button.getAttribute("data-workbench-row-index"));
        if (Number.isNaN(index) || index < 0 || index >= datumRows.length) return;
        loadRequest((datumRows[index] || {}).shell_request);
      });
    });

    Array.prototype.forEach.call(target.querySelectorAll("[data-workbench-nav-key]"), function (button) {
      button.addEventListener("click", function () {
        var key = button.getAttribute("data-workbench-nav-key") || "";
        loadRequest(asObject(navigation[key]).shell_request);
      });
    });

    bindSelectableRows("tr[data-workbench-document-index]", "data-workbench-document-index", documents);
    bindSelectableRows("tr[data-workbench-row-index]", "data-workbench-row-index", datumRows);
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
        renderWorkbenchSurface(surfacePayload)
      )
    ) {
      bindWorkbenchNavigation(ctx, target, asObject(surfacePayload.workspace));
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
