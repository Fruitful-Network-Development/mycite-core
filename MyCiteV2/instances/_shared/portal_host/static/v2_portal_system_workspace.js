/**
 * SYSTEM workspace renderer and transition bindings.
 * This is the only workbench renderer that understands the ordered sandbox ->
 * file -> datum -> object focus path.
 */
(function () {
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function button(label, attrs) {
    var attrPairs = [];
    Object.keys(attrs || {}).forEach(function (key) {
      if (attrs[key] == null || attrs[key] === false) return;
      attrPairs.push(key + '="' + escapeHtml(attrs[key]) + '"');
    });
    return '<button type="button" class="ide-sessionAction ide-sessionAction--button" ' + attrPairs.join(" ") + ">" + escapeHtml(label) + "</button>";
  }

  function actionButton(label, attrs) {
    var attrPairs = [];
    Object.keys(attrs || {}).forEach(function (key) {
      if (attrs[key] == null || attrs[key] === false) return;
      attrPairs.push(key + '="' + escapeHtml(attrs[key]) + '"');
    });
    return '<button type="button" class="data-tool__actionBtn" ' + attrPairs.join(" ") + ">" + escapeHtml(label) + "</button>";
  }

  function infoList(rows) {
    if (!rows || !rows.length) return "";
    return (
      '<dl class="v2-surface-dl">' +
      rows
        .map(function (row) {
          return (
            "<dt>" +
            escapeHtml(row.label || "") +
            "</dt><dd><strong>" +
            escapeHtml(row.value || "—") +
            "</strong>" +
            (row.detail ? "<br />" + escapeHtml(row.detail) : "") +
            "</dd>"
          );
        })
        .join("") +
      "</dl>"
    );
  }

  function renderFileButtons(files) {
    if (!files || !files.length) return '<p class="ide-controlpanel__empty">No files are available yet.</p>';
    return (
      '<div class="v2-card-grid">' +
      files
        .map(function (file) {
          return (
            '<article class="v2-card">' +
            "<h3>" +
            escapeHtml(file.label || file.file_key || "File") +
            "</h3>" +
            "<p>" +
            escapeHtml(file.detail || "") +
            "</p>" +
            button(file.active ? "Focused" : "Open", {
              "data-shell-transition-kind": "focus_file",
              "data-shell-file-key": file.file_key || "",
              "data-shell-active": file.active ? "true" : "false",
            }) +
            "</article>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderDatumTable(documentPayload) {
    var rows = (documentPayload && documentPayload.rows) || [];
    if (!rows.length) return '<p class="ide-controlpanel__empty">This file does not expose datum rows.</p>';
    return (
      '<div class="v2-tableWrap"><table class="v2-table"><thead><tr><th>Datum</th><th>Diagnostics</th><th></th></tr></thead><tbody>' +
      rows
        .map(function (row) {
          return (
            "<tr>" +
            "<td>" +
            escapeHtml(row.label || row.datum_id || "Datum") +
            "</td>" +
            "<td>" +
            escapeHtml(row.detail || "ok") +
            "</td>" +
            "<td>" +
            button(row.selected ? "Focused" : "Focus", {
              "data-shell-transition-kind": "focus_datum",
              "data-shell-datum-id": row.datum_id || "",
            }) +
            "</td>" +
            "</tr>"
          );
        })
        .join("") +
      "</tbody></table></div>"
    );
  }

  function chip(text) {
    return '<span class="data-tool__editorChip">' + escapeHtml(text || "") + "</span>";
  }

  function coordinatesChips(coordinates) {
    if (!coordinates) return chip("unstructured");
    return (
      chip("L" + String(coordinates.layer)) +
      chip("VG" + String(coordinates.value_group)) +
      chip("I" + String(coordinates.iteration))
    );
  }

  function datumSummary(row) {
    var parts = [];
    if (row.primary_value_token) parts.push(row.primary_value_token);
    if (row.recognized_family) parts.push("family: " + row.recognized_family);
    if (row.recognized_anchor) parts.push("anchor: " + row.recognized_anchor);
    return parts.length ? parts.join(" | ") : "No recognized value summary.";
  }

  function renderReferenceBindings(selectedDatum) {
    var bindings = (selectedDatum && selectedDatum.reference_bindings) || [];
    if (!bindings.length) return '<p class="ide-controlpanel__empty">No reference bindings are available for this datum.</p>';
    return (
      '<div class="v2-card-grid">' +
      bindings
        .map(function (binding) {
          return (
            '<article class="v2-card">' +
            "<h3>" +
            escapeHtml(binding.label || binding.object_id || "Object") +
            "</h3>" +
            "<p>" +
            escapeHtml(binding.resolution_state || binding.value_token || "reference binding") +
            "</p>" +
            actionButton("Focus Object", {
              "data-shell-transition-kind": "focus_object",
              "data-shell-datum-id": selectedDatum.datum_id || "",
              "data-shell-object-id": binding.object_id || "",
            }) +
            "</article>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderDatumInspector(documentPayload) {
    var selectedDatum = (documentPayload && documentPayload.selected_datum) || null;
    var hint =
      (documentPayload && documentPayload.inspector_hint) ||
      "Select a datum row to inspect its structural coordinates, bindings, and raw payload.";
    if (!selectedDatum) {
      return (
        '<aside class="data-tool__anthologyInspector">' +
        '<div class="data-tool__paneHead data-tool__paneHead--compact"><div class="card__title">Datum Inspector</div></div>' +
        '<div class="data-tool__anthologyInspectorBody">' +
        '<p class="data-tool__inspectorHint ide-controlpanel__empty">' + escapeHtml(hint) + "</p>" +
        "</div></aside>"
      );
    }
    return (
      '<aside class="data-tool__anthologyInspector">' +
      '<div class="data-tool__paneHead data-tool__paneHead--compact">' +
      '<div class="card__title">Datum Inspector</div>' +
      "<p>" +
      escapeHtml(selectedDatum.label || selectedDatum.datum_id || "Datum") +
      "</p>" +
      "</div>" +
      '<article class="data-tool__datumEditor">' +
      '<div class="data-tool__editorHeader">' +
      '<div class="data-tool__editorHeadline">' +
      "<strong>" +
      escapeHtml(selectedDatum.label || selectedDatum.datum_id || "Datum") +
      "</strong>" +
      "<code>" +
      escapeHtml(selectedDatum.datum_id || "") +
      "</code>" +
      "</div>" +
      '<div class="data-tool__editorChips">' +
      coordinatesChips(selectedDatum.coordinates) +
      (selectedDatum.recognized_family ? chip(selectedDatum.recognized_family) : "") +
      (selectedDatum.recognized_anchor ? chip(selectedDatum.recognized_anchor) : "") +
      "</div>" +
      "</div>" +
      infoList([
        { label: "diagnostics", value: (selectedDatum.diagnostic_states || []).join(", ") || "ok" },
        { label: "primary value", value: selectedDatum.primary_value_token || "—" },
        { label: "labels", value: (selectedDatum.labels || []).join(", ") || "—" },
      ]) +
      '<section class="data-tool__anthologyInvSection">' +
      '<h4 class="data-tool__inspectorSectionTitle">Reference Bindings</h4>' +
      renderReferenceBindings(selectedDatum) +
      "</section>" +
      '<section class="data-tool__anthologyInvSection">' +
      '<h4 class="data-tool__inspectorSectionTitle">Read-Only Posture</h4>' +
      '<p class="data-tool__inspectorHint">Editing is intentionally deferred in this pass so the canonical SYSTEM datum-file workbench stays stable while the reducer-owned model settles.</p>' +
      "</section>" +
      '<details class="data-tool__anthologyInvSection">' +
      "<summary>Raw Datum</summary>" +
      "<pre>" +
      escapeHtml(JSON.stringify(selectedDatum.raw == null ? null : selectedDatum.raw, null, 2)) +
      "</pre>" +
      "</details>" +
      "</article>" +
      "</aside>"
    );
  }

  function renderAnthologyLayeredTable(documentPayload) {
    var layerGroups = (documentPayload && documentPayload.layer_groups) || [];
    if (!layerGroups.length) return '<p class="ide-controlpanel__empty">No anthology rows were available for the anchor file.</p>';
    return (
      '<div class="data-tool__anthologyWorkbench">' +
      '<div class="data-tool__workbenchWithInspector">' +
      '<div class="data-tool__workbenchCenter">' +
      '<article class="data-tool__tablePane data-tool__anthologyTableHost">' +
      '<div class="data-tool__paneHead">' +
      '<div class="card__title">Layered Datum Table</div>' +
      "<p>" +
      escapeHtml(documentPayload.summary || "Canonical system anchor file rendered as a layered datum table.") +
      "</p>" +
      "</div>" +
      '<div class="data-tool__anthologyLayers">' +
      layerGroups
        .map(function (layerGroup) {
          return (
            '<details class="v2-card" open>' +
            "<summary>" +
            escapeHtml((layerGroup.label || "Layer") + " (" + String(layerGroup.row_count || 0) + " rows)") +
            "</summary>" +
            (layerGroup.value_groups || [])
              .map(function (valueGroup) {
                return (
                  '<details class="v2-card" open style="margin-top:12px">' +
                  "<summary>" +
                  escapeHtml((valueGroup.label || "Value Group") + " (" + String(valueGroup.row_count || 0) + " rows)") +
                  "</summary>" +
                  '<div class="data-tool__tableWrap">' +
                  '<table class="data-tool__table"><thead><tr><th>Iter</th><th>Datum</th><th>Value / recognition</th><th>Diagnostics</th><th>Action</th></tr></thead><tbody>' +
                  (valueGroup.rows || [])
                    .map(function (row) {
                      var selectedClass = row.selected ? " is-compact-selected" : "";
                      return (
                        '<tr class="js-anthology-row' +
                        selectedClass +
                        '" tabindex="0" role="button" data-shell-transition-kind="focus_datum" data-shell-datum-id="' +
                        escapeHtml(row.datum_id || "") +
                        '">' +
                        "<td>" +
                        escapeHtml(
                          row.coordinates && row.coordinates.iteration != null ? String(row.coordinates.iteration) : "—"
                        ) +
                        "</td>" +
                        "<td>" +
                        '<div class="data-tool__datumMain">' +
                        '<div class="data-tool__datumName data-tool__clip">' +
                        escapeHtml(row.label || row.datum_id || "Datum") +
                        "</div>" +
                        '<div class="data-tool__datumId data-tool__clip">' +
                        escapeHtml(row.datum_id || "") +
                        "</div>" +
                        '<div class="data-tool__editorChips" style="margin-top:6px">' +
                        coordinatesChips(row.coordinates) +
                        "</div>" +
                        "</div>" +
                        "</td>" +
                        "<td>" +
                        escapeHtml(datumSummary(row)) +
                        "</td>" +
                        "<td>" +
                        escapeHtml((row.diagnostics || []).join(", ") || "ok") +
                        "</td>" +
                        "<td>" +
                        actionButton(row.selected ? "Focused" : "Inspect", {
                          "data-shell-transition-kind": "focus_datum",
                          "data-shell-datum-id": row.datum_id || "",
                        }) +
                        "</td>" +
                        "</tr>"
                      );
                    })
                    .join("") +
                  "</tbody></table></div></details>"
                );
              })
              .join("") +
            "</details>"
          );
        })
        .join("") +
      "</div></article></div>" +
      renderDatumInspector(documentPayload) +
      "</div></div>"
    );
  }

  function renderObjectButtons(bindings) {
    if (!bindings || !bindings.length) return '<p class="ide-controlpanel__empty">No object bindings are available for this datum.</p>';
    return (
      '<div class="v2-card-grid">' +
      bindings
        .map(function (binding) {
          return (
            '<article class="v2-card">' +
            "<h3>" +
            escapeHtml(binding.label || binding.object_id || "Object") +
            "</h3>" +
            "<p>" +
            escapeHtml(binding.resolution_state || binding.value_token || "") +
            "</p>" +
            button("Focus Object", {
              "data-shell-transition-kind": "focus_object",
              "data-shell-datum-id": binding.datum_id || "",
              "data-shell-object-id": binding.object_id || "",
            }) +
            "</article>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderVerbButtons(activeVerb) {
    var verbs = ["navigate", "investigate", "mediate", "manipulate"];
    return (
      '<div class="data-tool__controlRow data-tool__controlRow--wrap">' +
      verbs
        .map(function (verb) {
          return button(verb === activeVerb ? verb + " (active)" : verb, {
            "data-shell-transition-kind": "set_verb",
            "data-shell-verb": verb,
          });
        })
        .join("") +
      "</div>"
    );
  }

  function bindTransitions(root, ctx) {
    function dispatchFromNode(node, event) {
      if (event) {
        event.preventDefault();
        event.stopPropagation();
      }
      var kind = node.getAttribute("data-shell-transition-kind") || "";
      var transition = { kind: kind };
      var fileKey = node.getAttribute("data-shell-file-key");
      var datumId = node.getAttribute("data-shell-datum-id");
      var objectId = node.getAttribute("data-shell-object-id");
      var verb = node.getAttribute("data-shell-verb");
      if (fileKey) transition.file_key = fileKey;
      if (datumId) transition.datum_id = datumId;
      if (objectId) transition.object_id = objectId;
      if (verb) transition.verb = verb;
      ctx.dispatchTransition(transition);
    }

    Array.prototype.forEach.call(root.querySelectorAll("[data-shell-transition-kind]"), function (node) {
      node.addEventListener("click", function (event) {
        dispatchFromNode(node, event);
      });
      if (node.tagName !== "BUTTON") {
        node.addEventListener("keydown", function (event) {
          if (event.key === "Enter" || event.key === " ") {
            dispatchFromNode(node, event);
          }
        });
      });
    });
  }

  function bindProfileForm(root, ctx) {
    var form = root.querySelector("#v2-system-profile-basics-form");
    if (!form) return;
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var envelope = ctx.getEnvelope ? ctx.getEnvelope() : null;
      var body = {
        schema: form.getAttribute("data-action-schema") || "",
        portal_scope: envelope && envelope.portal_scope ? envelope.portal_scope : undefined,
        shell_state: envelope && envelope.shell_state ? envelope.shell_state : undefined,
      };
      Array.prototype.forEach.call(form.querySelectorAll("input, textarea"), function (field) {
        body[field.name] = field.value;
      });
      ctx.loadRuntimeView(form.getAttribute("data-action-route"), body, { replaceHistory: true });
    });
  }

  function renderProfileBasics(profileBasics) {
    var form = (profileBasics && profileBasics.form) || {};
    var fields = form.fields || [];
    return (
      '<section class="v2-card"><h3>Profile Basics</h3>' +
      infoList([
        { label: "profile title", value: profileBasics.profile_title || "—" },
        { label: "profile resolution", value: profileBasics.profile_resolution || "—" },
        { label: "publication mode", value: profileBasics.publication_mode || "—" },
      ]) +
      '<form id="v2-system-profile-basics-form" data-action-route="' +
      escapeHtml(form.action_route || "") +
      '" data-action-schema="' +
      escapeHtml(form.schema || "") +
      '">' +
      fields
        .map(function (field) {
          if (field.type === "textarea") {
            return (
              '<label class="v2-formField"><span>' +
              escapeHtml(field.label || field.field_id || "") +
              '</span><textarea name="' +
              escapeHtml(field.field_id || "") +
              '" rows="4">' +
              escapeHtml(field.value || "") +
              "</textarea></label>"
            );
          }
          return (
            '<label class="v2-formField"><span>' +
            escapeHtml(field.label || field.field_id || "") +
            '</span><input type="' +
            escapeHtml(field.type || "text") +
            '" name="' +
            escapeHtml(field.field_id || "") +
            '" value="' +
            escapeHtml(field.value || "") +
            '" /></label>'
          );
        })
        .join("") +
      '<div style="margin-top:12px"><button type="submit" class="ide-sessionAction ide-sessionAction--button">' +
      escapeHtml(form.action_label || "Save") +
      "</button></div>" +
      (form.status ? '<p class="ide-controlpanel__empty">Status: <strong>' + escapeHtml(form.status) + "</strong></p>" : "") +
      "</form></section>"
    );
  }

  function renderWorkspace(ctx, root, surfacePayload) {
    var workspace = (surfacePayload && surfacePayload.workspace) || {};
    var breadcrumbs = (workspace.focus_path || []).map(function (segment) {
      return '<span class="data-tool__editorChip">' + escapeHtml(segment.level + ":" + segment.id) + "</span>";
    });
    var body = "";

    if (workspace.workbench_mode === "sandbox_management") {
      body +=
        '<section class="v2-card"><h3>Sandbox Management</h3><p>Backed out of all files. Choose a workspace file or source document to continue.</p>' +
        renderFileButtons(workspace.files || []) +
        "</section>";
    } else if (workspace.active_file_key === "activity" && workspace.activity) {
      var records = workspace.activity.records || [];
      body +=
        '<section class="v2-card"><h3>Activity</h3><p>Workspace activity remains inside SYSTEM as a file mode, not a separate page.</p>' +
        (records.length
          ? '<div class="v2-tableWrap"><table class="v2-table"><thead><tr><th>Timestamp</th><th>Event</th><th>Verb</th><th>Focus</th></tr></thead><tbody>' +
            records
              .map(function (record) {
                return (
                  "<tr><td>" +
                  escapeHtml(record.timestamp || "") +
                  "</td><td>" +
                  escapeHtml(record.event_type || "") +
                  "</td><td>" +
                  escapeHtml(record.shell_verb || "") +
                  "</td><td>" +
                  escapeHtml(record.focus_subject || "") +
                  "</td></tr>"
                );
              })
              .join("") +
            "</tbody></table></div>"
          : '<p class="ide-controlpanel__empty">No local activity records were available.</p>') +
        "</section>";
    } else if (workspace.active_file_key === "profile_basics" && workspace.profile_basics) {
      body += renderProfileBasics(workspace.profile_basics);
    } else if (workspace.document) {
      if (workspace.document.presentation === "anthology_layered_table") {
        body +=
          '<section class="v2-card"><h3>' +
          escapeHtml(workspace.document.label || "Anthology") +
          "</h3><p>" +
          escapeHtml(workspace.document.detail || "") +
          "</p>" +
          renderAnthologyLayeredTable(workspace.document) +
          "</section>";
      } else {
        body +=
          '<section class="v2-card"><h3>' +
          escapeHtml(workspace.document.label || "Document") +
          "</h3><p>" +
          escapeHtml(workspace.document.detail || "") +
          "</p>" +
          renderDatumTable(workspace.document) +
          "</section>";
        if (workspace.document.selected_datum) {
          body +=
            '<section class="v2-card" style="margin-top:12px"><h3>Focused Datum</h3>' +
            infoList([
              { label: "datum", value: workspace.document.selected_datum.datum_id || "—" },
              { label: "label", value: workspace.document.selected_datum.label || "—" },
              {
                label: "diagnostics",
                value: (workspace.document.selected_datum.diagnostic_states || []).join(", ") || "ok",
              },
            ]) +
            renderVerbButtons(workspace.verb || "navigate") +
            renderObjectButtons(
              (workspace.document.selected_datum.reference_bindings || []).map(function (item) {
                return {
                  datum_id: workspace.document.selected_datum.datum_id || "",
                  object_id: item.object_id || "",
                  label: item.label || item.object_id || "",
                  resolution_state: item.resolution_state || item.value_token || "",
                };
              })
            ) +
            "</section>";
        }
        if (workspace.document.selected_object) {
          body +=
            '<section class="v2-card" style="margin-top:12px"><h3>Focused Object</h3>' +
            infoList([
              { label: "object", value: workspace.document.selected_object.label || "—" },
              { label: "detail", value: workspace.document.selected_object.detail || "—" },
            ]) +
            "</section>";
        }
      }
    }

    root.innerHTML =
      '<section class="system-center-workspace">' +
      '<div class="v2-card"><h3>System Datum-File Workbench</h3><p>SYSTEM owns the core datum-file workbench. The URL mirrors runtime state; it does not own it.</p>' +
      '<div class="data-tool__controlRow data-tool__controlRow--wrap">' +
      button("Back Out", { "data-shell-transition-kind": "back_out" }) +
      renderVerbButtons(workspace.verb || "navigate") +
      "</div>" +
      '<div style="margin-top:12px">' + breadcrumbs.join(" ") + "</div>" +
      "</div>" +
      '<div style="margin-top:12px">' + body + "</div>" +
      "</section>";
    bindTransitions(root, ctx);
    bindProfileForm(root, ctx);
  }

  window.PortalSystemWorkspaceRenderer = {
    render: renderWorkspace,
  };
  if (typeof window.__MYCITE_V2_REGISTER_SHELL_MODULE === "function") {
    window.__MYCITE_V2_REGISTER_SHELL_MODULE("system_workspace");
  }
})();
