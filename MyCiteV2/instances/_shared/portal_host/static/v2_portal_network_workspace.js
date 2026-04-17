/**
 * Dedicated renderer for the NETWORK system-log workbench.
 */
(function () {
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function prettyJson(value) {
    if (value == null) return "";
    try {
      return JSON.stringify(value, null, 2);
    } catch (_) {
      return String(value);
    }
  }

  function toolSurfaceAdapter() {
    return window.PortalToolSurfaceAdapter || {};
  }

  function buildSurfaceRequest(ctx, surfacePayload, overrides) {
    var workspace = (surfacePayload && surfacePayload.workspace) || {};
    return toolSurfaceAdapter().buildDirectSurfaceRequest(ctx, {
      defaultSurfaceId: "network.root",
      baseQuery: { view: "system_logs" },
      activeFilters: workspace.active_filters || {},
      filterMap: {
        contract_id: "contract",
        event_type_id: "type",
        record_id: "record",
      },
      overrides: overrides,
    });
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

  function renderFilterSummary(workspace) {
    var active = workspace.active_filters || {};
    var parts = ["view: system_logs"];
    if (active.contract_id) parts.push("contract: " + active.contract_id);
    if (active.event_type_id) parts.push("type: " + active.event_type_id);
    if (active.record_id) parts.push("record: " + active.record_id);
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>Current Lens</h3><p>' +
      escapeHtml(parts.join(" · ")) +
      "</p><p>" +
      escapeHtml(workspace.document_path || "") +
      "</p></section>"
    );
  }

  function renderRecordTable(workspace) {
    var rows = workspace.records || [];
    if (!rows.length) {
      return (
        '<section class="v2-card" style="margin-top:12px"><h3>System Log Rows</h3><p>' +
        escapeHtml(workspace.empty_text || "No rows are available.") +
        "</p></section>"
      );
    }
    return (
      '<section class="v2-card" style="margin-top:12px"><h3>System Log Rows</h3>' +
      '<div class="v2-tableWrap"><table class="v2-table v2-networkTable"><thead><tr>' +
      "<th>Timestamp</th><th>Type</th><th>Status</th><th>Counterparty</th><th>Contract</th><th>Title</th><th>Action</th>" +
      "</tr></thead><tbody>" +
      rows
        .map(function (row) {
          var actionLabel = row.selected ? "Selected" : "Focus";
          return (
            '<tr class="v2-networkTable__row' +
            (row.selected ? " is-selected" : "") +
            '" data-record-id="' +
            escapeHtml(row.datum_address || "") +
            '">' +
            "<td>" + escapeHtml(row.hops_timestamp || "—") + "</td>" +
            "<td>" + escapeHtml(row.event_type_label || "—") + "</td>" +
            "<td>" + escapeHtml(row.status || "—") + "</td>" +
            "<td>" + escapeHtml(row.counterparty || "—") + "</td>" +
            "<td>" + escapeHtml(row.contract_id || "—") + "</td>" +
            "<td>" + escapeHtml(row.title || row.label || "—") + "</td>" +
            '<td><button class="v2-networkTable__action" type="button" data-record-focus="' +
            escapeHtml(row.datum_address || "") +
            '">' +
            escapeHtml(actionLabel) +
            "</button></td></tr>"
          );
        })
        .join("") +
      "</tbody></table></div></section>"
    );
  }

  window.PortalNetworkWorkspaceRenderer = {
    render: function (ctx, target, surfacePayload) {
      var workspace = (surfacePayload && surfacePayload.workspace) || {};
      var adapter = toolSurfaceAdapter();
      if (!target) return;
      adapter.renderWrappedSurface(
        target,
        adapter.resolveSurfaceState({
          region: ctx.region,
          surfacePayload: surfacePayload,
          title: "NETWORK",
          hasContent: true,
        }),
        renderCards(surfacePayload.cards || []) +
          renderFilterSummary(workspace) +
          renderRecordTable(workspace) +
          renderNotes(surfacePayload.notes || [])
      );
      Array.prototype.forEach.call(target.querySelectorAll("[data-record-focus]"), function (button) {
        button.addEventListener("click", function () {
          var recordId = button.getAttribute("data-record-focus") || "";
          ctx.loadShell(buildSurfaceRequest(ctx, surfacePayload, { record: recordId }));
        });
      });
      Array.prototype.forEach.call(target.querySelectorAll("[data-record-id]"), function (row) {
        row.addEventListener("click", function (event) {
          if (event.target && event.target.closest && event.target.closest("button")) return;
          var recordId = row.getAttribute("data-record-id") || "";
          if (!recordId) return;
          ctx.loadShell(buildSurfaceRequest(ctx, surfacePayload, { record: recordId }));
        });
      });
    },
  };

  window.PortalNetworkInspectorRenderer = {
    render: function (ctx, target, surfacePayload) {
      var workspace = (surfacePayload && surfacePayload.workspace) || {};
      var record = workspace.selected_record || null;
      var contract = workspace.selected_contract || null;
      var adapter = toolSurfaceAdapter();
      if (!target) return;
      if (!record) {
        adapter.renderWrappedSurface(
          target,
          adapter.resolveSurfaceState({
            region: ctx.region,
            surfacePayload: surfacePayload,
            title: "Log Record",
            hasContent: false,
            message: "Select a system-log row to inspect its canonical payload and any linked contract summary.",
          }),
          '<div class="v2-inspector-stack"><section class="v2-card"><h3>Log Record</h3><p>Select a system-log row to inspect its canonical payload and any linked contract summary.</p></section></div>'
        );
        return;
      }
      adapter.renderWrappedSurface(
        target,
        adapter.resolveSurfaceState({
          region: ctx.region,
          surfacePayload: surfacePayload,
          title: "NETWORK Detail",
          hasContent: true,
        }),
        '<div class="v2-inspector-stack">' +
        '<section class="v2-card"><h3>Record Summary</h3>' +
        '<dl class="v2-surface-dl">' +
        "<dt>datum</dt><dd><strong>" + escapeHtml(record.datum_address || "—") + "</strong></dd>" +
        "<dt>timestamp</dt><dd><strong>" + escapeHtml(record.hops_timestamp || "—") + "</strong></dd>" +
        "<dt>type</dt><dd><strong>" + escapeHtml(record.event_type_label || record.event_type_slug || "—") + "</strong></dd>" +
        "<dt>status</dt><dd><strong>" + escapeHtml(record.status || "—") + "</strong></dd>" +
        "<dt>counterparty</dt><dd><strong>" + escapeHtml(record.counterparty || "—") + "</strong></dd>" +
        "<dt>contract</dt><dd><strong>" + escapeHtml(record.contract_id || "—") + "</strong></dd>" +
        "<dt>source</dt><dd><strong>" + escapeHtml(record.source_kind || "—") + "</strong><br />" + escapeHtml(record.source_timestamp || "—") + "</dd>" +
        "</dl></section>" +
        (contract
          ? '<section class="v2-card" style="margin-top:12px"><h3>Linked Contract</h3><pre class="v2-networkInspector__json">' +
            escapeHtml(prettyJson(contract)) +
            "</pre></section>"
          : "") +
        '<section class="v2-card" style="margin-top:12px"><h3>Raw Payload</h3><pre class="v2-networkInspector__json">' +
        escapeHtml(prettyJson(record.raw || {})) +
        "</pre></section></div>"
      );
    },
  };
})();
