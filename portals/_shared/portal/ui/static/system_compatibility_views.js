(function () {
  "use strict";

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function clear(node) {
    if (!node) return;
    node.innerHTML = "";
  }

  function buildField(label, value, useCode) {
    var display = String(value || "").trim();
    if (!display) return "";
    return (
      "<p><strong>" +
      esc(label) +
      "</strong><br/>" +
      (useCode ? "<code>" + esc(display) + "</code>" : esc(display)) +
      "</p>"
    );
  }

  function actionPayloadFromMount(mount, fallback) {
    var root = mount || document;
    var defaults = fallback && typeof fallback === "object" ? fallback : {};
    function read(selector, key) {
      var input = root.querySelector(selector);
      var token = String((input && input.value) || defaults[key] || "").trim();
      return token;
    }
    return {
      source_msn_id: read("[data-inheritance-field='source_msn_id']", "source_msn_id"),
      contract_id: read("[data-inheritance-field='contract_id']", "contract_id"),
      resource_id: read("[data-inheritance-field='resource_id']", "resource_id"),
    };
  }

  function setBusy(mount, busy) {
    if (!mount) return;
    Array.prototype.slice.call(mount.querySelectorAll("[data-inheritance-action]")).forEach(function (button) {
      button.disabled = !!busy;
    });
  }

  function renderInheritanceDetail(options) {
    var mount = options && options.mount;
    if (!mount) return;

    var resource = options && options.resource && typeof options.resource === "object" ? options.resource : null;
    var selectedSource = String((options && options.selectedSource) || (resource && resource.source_msn_id) || "").trim();
    var status = options && options.status && typeof options.status === "object" ? options.status : {};
    var requestJson = options && typeof options.requestJson === "function" ? options.requestJson : null;
    var afterAction = options && typeof options.afterAction === "function" ? options.afterAction : null;
    var resourceId = String((resource && resource.resource_id) || "").trim();
    var displayName = String((resource && (resource.resource_name || resource.resource_id)) || "").trim();
    var contractId = String((resource && resource.contract_id) || "").trim();
    var cachePath = String((resource && resource.cache_path) || "").trim();

    clear(mount);

    var wrapper = document.createElement("div");
    wrapper.className = "inh-workbench__detail";
    wrapper.innerHTML =
      (resource
        ? buildField("Display name", displayName, false) +
          buildField("resource_id", resourceId, true) +
          buildField("source_msn_id", selectedSource, true) +
          (contractId ? buildField("contract_id", contractId, true) : "") +
          (cachePath
            ? '<details class="data-tool__advanced"><summary>Advanced: cache path</summary><p><code>' +
              esc(cachePath) +
              "</code></p></details>"
            : "")
        : '<p class="data-tool__empty">Select an inherited resource.</p>') +
      '<details class="data-tool__advanced" open>' +
      "<summary>Source &amp; contract actions</summary>" +
      '<label><strong>Source msn_id</strong><input type="text" data-inheritance-field="source_msn_id" value="' +
      esc(selectedSource) +
      '" placeholder="3-2-3-..." /></label>' +
      '<label><strong>Contract ID (optional)</strong><input type="text" data-inheritance-field="contract_id" value="' +
      esc(contractId) +
      '" placeholder="contract-..." /></label>' +
      '<label><strong>Resource ID (optional)</strong><input type="text" data-inheritance-field="resource_id" value="' +
      esc(resourceId) +
      '" placeholder="samras.txa" /></label>' +
      '<div class="data-tool__controlRow data-tool__controlRow--wrap">' +
      '<button type="button" data-inheritance-action="refresh_one">Refresh one</button>' +
      '<button type="button" data-inheritance-action="refresh_source">Refresh source</button>' +
      '<button type="button" data-inheritance-action="disconnect_source">Disconnect source</button>' +
      "</div>" +
      "</details>" +
      '<details class="data-tool__advanced">' +
      "<summary>Advanced: last API JSON</summary>" +
      '<pre class="jsonblock" data-inheritance-status-pre>' +
      esc(JSON.stringify(status || {}, null, 2)) +
      "</pre>" +
      "</details>";

    mount.appendChild(wrapper);

    if (!requestJson) {
      return;
    }

    Array.prototype.slice.call(wrapper.querySelectorAll("[data-inheritance-action]")).forEach(function (button) {
      button.addEventListener("click", function () {
        var action = String(button.getAttribute("data-inheritance-action") || "").trim();
        if (!action) return;
        var endpoint = {
          refresh_one: "/portal/api/data/resources/inherited/refresh",
          refresh_source: "/portal/api/data/resources/inherited/refresh_source",
          disconnect_source: "/portal/api/data/resources/inherited/disconnect_source",
        }[action];
        if (!endpoint) return;
        var payload = actionPayloadFromMount(wrapper, {
          source_msn_id: selectedSource,
          contract_id: contractId,
          resource_id: resourceId,
        });
        setBusy(wrapper, true);
        Promise.resolve(requestJson(endpoint, "POST", payload))
          .then(function (result) {
            if (afterAction) {
              return afterAction((result && result.body) || {});
            }
            return result;
          })
          .finally(function () {
          setBusy(wrapper, false);
          });
      });
    });
  }

  window.MyCiteSystemCompatibilityViews = Object.assign({}, window.MyCiteSystemCompatibilityViews || {}, {
    renderInheritanceDetail: renderInheritanceDetail,
  });
})();
