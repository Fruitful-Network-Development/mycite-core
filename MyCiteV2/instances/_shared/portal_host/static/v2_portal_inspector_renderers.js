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

  window.PortalShellInspectorRenderer = {
    render: function (ctx) {
      var target = ctx.target;
      var region = ctx.region || {};
      var sections = region.sections || [];
      if (!target) return;
      if (region.visible === false) {
        target.innerHTML = "";
        return;
      }
      target.innerHTML =
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
        sections
          .map(function (section) {
            return (
              '<section class="v2-card" style="margin-top:12px"><h3>' +
              escapeHtml(section.title || "Section") +
              "</h3>" +
              renderRows(section.rows || []) +
              "</section>"
            );
          })
          .join("") +
        "</div>";
    },
  };
})();
