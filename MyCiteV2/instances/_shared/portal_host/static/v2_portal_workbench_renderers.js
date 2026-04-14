/**
 * Generic workbench renderer for the one-shell portal.
 */
(function () {
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
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
          renderTable({ columns: subsection.columns, items: subsection.rows || [] }) +
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

  function renderProfileForm(surfacePayload) {
    var form = surfacePayload.form || {};
    var fields = form.fields || [];
    if (!fields.length) return "";
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>' +
      escapeHtml(form.title || "Edit") +
      "</h3>" +
      (form.status ? '<p class="ide-controlpanel__empty">Status: <strong>' + escapeHtml(form.status) + "</strong></p>" : "") +
      '<form id="v2-profile-basics-form" data-action-route="' +
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
      "</button></div></form></section>"
    );
  }

  function bindProfileForm(ctx, target) {
    var form = target.querySelector("#v2-profile-basics-form");
    if (!form) return;
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var body = { schema: form.getAttribute("data-action-schema") || "" };
      Array.prototype.forEach.call(form.querySelectorAll("input, textarea"), function (field) {
        body[field.name] = field.value;
      });
      ctx.loadRuntimeView(form.getAttribute("data-action-route"), body);
    });
  }

  window.PortalShellWorkbenchRenderer = {
    render: function (ctx) {
      var target = ctx.target;
      var region = ctx.region || {};
      if (!target) return;
      var surfacePayload = region.surface_payload || {};
      target.innerHTML =
        renderCards(surfacePayload.cards || []) +
        renderSections(surfacePayload.sections || []) +
        renderNotes(surfacePayload.notes || []) +
        renderProfileForm(surfacePayload);
      bindProfileForm(ctx, target);
    },
  };
})();
