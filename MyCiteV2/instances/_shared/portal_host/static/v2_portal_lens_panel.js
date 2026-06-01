/**
 * Portal lens panel — Phase 5 (docs/wiki/81-lens-authoring-guide.md).
 *
 * The Control-Panel surface for managing presentation lenses: lists the built-in
 * lenses (id / label / description / bindings) with an enable/disable toggle. A
 * disabled lens falls back to the identity passthrough in the workbench render
 * path. Lenses are discovered/curated here and toggled per portal.
 *
 *   GET  /portal/api/lenses               -> {schema, lenses: [{lens_id,label,description,bindings,enabled}]}
 *   POST /portal/api/lenses/toggle {lens_id, enabled} -> {ok, schema, lenses:[...]}
 *
 * Exposed surface (window.PortalLensPanel):
 *   - fetch() -> Promise<{schema, lenses: [...]}>
 *   - toggle(lensId, enabled) -> Promise<{ok, lenses:[...]}>
 *   - mount(target) -> void   (renders the toggle list into a DOM node)
 *   - refresh(target) -> void
 */
(function () {
  "use strict";

  function asText(v) {
    return String(v == null ? "" : v).trim();
  }

  function escapeHtml(v) {
    return asText(v)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fetchCatalog() {
    return fetch("/portal/api/lenses", {
      method: "GET",
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    }).then(function (resp) {
      if (!resp.ok) throw new Error("lens catalog HTTP " + resp.status);
      return resp.json();
    });
  }

  function toggle(lensId, enabled) {
    return fetch("/portal/api/lenses/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ lens_id: asText(lensId), enabled: !!enabled }),
    }).then(function (resp) {
      return resp.json();
    });
  }

  function renderList(target, lenses) {
    if (!target) return;
    var items = (lenses || []).map(function (lens) {
      var id = escapeHtml(lens.lens_id);
      var checked = lens.enabled ? " checked" : "";
      var bindings = lens.bindings || {};
      var bound = []
        .concat(bindings.families || [], bindings.value_kinds || [], bindings.overlays || [])
        .map(escapeHtml)
        .join(", ");
      return (
        '<li class="portal-lens-panel__item" data-lens-id="' + id + '">' +
        '<label class="portal-lens-panel__toggle">' +
        '<input type="checkbox" class="portal-lens-panel__checkbox" data-lens-id="' + id + '"' + checked + " />" +
        '<span class="portal-lens-panel__label">' + escapeHtml(lens.label || lens.lens_id) + "</span>" +
        "</label>" +
        '<p class="portal-lens-panel__desc">' + escapeHtml(lens.description || "") + "</p>" +
        (bound ? '<p class="portal-lens-panel__bindings">binds: ' + bound + "</p>" : "") +
        "</li>"
      );
    });
    target.innerHTML = '<ul class="portal-lens-panel__list">' + items.join("") + "</ul>";
    var boxes = target.querySelectorAll(".portal-lens-panel__checkbox");
    Array.prototype.forEach.call(boxes, function (box) {
      box.addEventListener("change", function () {
        toggle(box.getAttribute("data-lens-id"), box.checked).then(function (payload) {
          if (payload && payload.lenses) renderList(target, payload.lenses);
        });
      });
    });
  }

  function refresh(target) {
    return fetchCatalog().then(function (payload) {
      renderList(target, (payload && payload.lenses) || []);
      return payload;
    });
  }

  window.PortalLensPanel = {
    fetch: fetchCatalog,
    toggle: toggle,
    mount: refresh,
    refresh: refresh,
  };
})();
