(function () {
  function qs(sel) {
    return document.querySelector(sel);
  }

  function out(value) {
    var node = qs("#ppt-output");
    if (!node) return;
    node.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  }

  async function api(method, path, body) {
    var res = await fetch(path, {
      method: method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    var payload = {};
    try {
      payload = await res.json();
    } catch (_) {
      payload = {};
    }
    if (!res.ok) {
      throw new Error(payload.error || ("HTTP " + res.status));
    }
    return payload;
  }

  async function appendLog(event) {
    try {
      await api("POST", "/portal/api/request_log", event);
    } catch (_) {
      // best-effort only
    }
  }

  var tenantProfiles = {};
  var latestCheckoutPreviewByTenant = {};

  function tenantId() {
    var select = qs("#ppt-tenant");
    return (select && select.value) || "";
  }

  function updateTenantRefView() {
    var id = tenantId();
    var refs = ((tenantProfiles[id] || {}).profile_refs || {});
    var profileNode = qs("#ppt-ref-profile");
    var siteNode = qs("#ppt-ref-site");
    var returnNode = qs("#ppt-ref-return");
    var cancelNode = qs("#ppt-ref-cancel");
    var webhookNode = qs("#ppt-ref-webhook");
    var brandNode = qs("#ppt-ref-brand");
    if (profileNode) profileNode.textContent = String(refs.paypal_profile_id || "");
    if (siteNode) siteNode.textContent = String(refs.paypal_site_base_url || "");
    if (returnNode) returnNode.textContent = String(refs.paypal_checkout_return_url || "");
    if (cancelNode) cancelNode.textContent = String(refs.paypal_checkout_cancel_url || "");
    if (webhookNode) webhookNode.textContent = String(refs.paypal_webhook_listener_url || "");
    if (brandNode) brandNode.textContent = String(refs.paypal_checkout_brand_name || "");
  }

  async function loadTenants() {
    var select = qs("#ppt-tenant");
    if (!select) return;
    try {
      var data = await api("GET", "/portal/api/progeny/members");
      var items = (data.items || []).filter(function (item) {
        var caps = item.capabilities || {};
        var status = item.status || {};
        return !!caps.paypal && (status.state || "active") === "active";
      });
      tenantProfiles = {};
      items.forEach(function (item) {
        var id = String(item.member_id || item.tenant_id || "").trim();
        if (id) tenantProfiles[id] = item;
      });
      select.innerHTML = items
        .map(function (item) {
          var id = String(item.member_id || item.tenant_id || "").trim();
          var label = (item.display || {}).title || id;
          return '<option value="' + id + '">' + label + " (" + id + ")</option>";
        })
        .join("");
      if (!items.length) {
        select.innerHTML = '<option value="">No PayPal-capable tenants</option>';
      }
      updateTenantRefView();
    } catch (err) {
      out("Failed to load tenants: " + err.message);
    }
  }

  async function checkStatus() {
    var id = tenantId();
    if (!id) {
      out("Select a tenant first.");
      return;
    }
    try {
      var payload = await api("GET", "/portal/api/admin/paypal/tenant/" + encodeURIComponent(id) + "/status");
      out(payload);
      appendLog({ type: "portal.paypal.tenant.status.checked", tenant_id: id, status: "ok" });
    } catch (err) {
      out("Error: " + err.message);
      appendLog({ type: "portal.paypal.tenant.status.failed", tenant_id: id, status: "failed", details: { error: err.message } });
    }
  }

  async function previewCheckoutProfile() {
    var id = tenantId();
    if (!id) {
      out("Select a tenant first.");
      return;
    }
    try {
      var payload = await api("GET", "/portal/api/paypal/member/" + encodeURIComponent(id) + "/checkout_preview");
      latestCheckoutPreviewByTenant[id] = payload;
      out(payload);
      appendLog({
        type: "portal.paypal.tenant.checkout.preview.loaded",
        tenant_id: id,
        status: "ok",
        details: {
          paypal_profile_id: (((payload || {}).source || {}).paypal_profile_id || ""),
        },
      });
    } catch (err) {
      out("Error: " + err.message);
      appendLog({
        type: "portal.paypal.tenant.checkout.preview.failed",
        tenant_id: id,
        status: "failed",
        details: { error: err.message },
      });
    }
  }

  async function syncCheckoutProfile() {
    var id = tenantId();
    if (!id) {
      out("Select a tenant first.");
      return;
    }
    var preview = latestCheckoutPreviewByTenant[id];
    if (!preview || !preview.ok) {
      out("Load a successful checkout preview before syncing.");
      return;
    }
    try {
      var payload = await api("POST", "/portal/api/admin/paypal/tenant/" + encodeURIComponent(id) + "/profile/sync", {
        action: "checkout_profile_sync",
        payload: {
          checkout_preview: preview,
        },
      });
      out(payload);
      appendLog({
        type: "portal.paypal.tenant.checkout.sync.queued",
        tenant_id: id,
        status: "ok",
        details: {
          request_id: payload.request_id || "",
          paypal_profile_id: (((preview || {}).source || {}).paypal_profile_id || ""),
        },
      });
    } catch (err) {
      out("Error: " + err.message);
      appendLog({
        type: "portal.paypal.tenant.checkout.sync.failed",
        tenant_id: id,
        status: "failed",
        details: { error: err.message },
      });
    }
  }

  async function createOrder() {
    var id = tenantId();
    if (!id) {
      out("Select a tenant first.");
      return;
    }
    var amount = (qs("#ppt-amount") || {}).value || "10.00";
    var currency = ((qs("#ppt-currency") || {}).value || "USD").toUpperCase();
    var preview = latestCheckoutPreviewByTenant[id] || {};
    var source = preview.source || {};
    try {
      var payload = await api("POST", "/portal/api/admin/paypal/tenant/" + encodeURIComponent(id) + "/orders/create", {
        amount: amount,
        currency: currency,
        return_url: source.return_url || "",
        cancel_url: source.cancel_url || "",
      });
      out(payload);
      appendLog({
        type: "portal.paypal.tenant.order.created",
        tenant_id: id,
        status: "ok",
        details: { amount: amount, currency: currency, order_id: payload.order_id || "" },
      });
    } catch (err) {
      out("Error: " + err.message);
      appendLog({
        type: "portal.paypal.tenant.order.failed",
        tenant_id: id,
        status: "failed",
        details: { amount: amount, currency: currency, error: err.message },
      });
    }
  }

  var statusBtn = qs("#ppt-status");
  if (statusBtn) statusBtn.addEventListener("click", checkStatus);
  var previewBtn = qs("#ppt-preview");
  if (previewBtn) previewBtn.addEventListener("click", previewCheckoutProfile);
  var syncBtn = qs("#ppt-sync");
  if (syncBtn) syncBtn.addEventListener("click", syncCheckoutProfile);
  var createBtn = qs("#ppt-create-order");
  if (createBtn) createBtn.addEventListener("click", createOrder);
  var tenantSelect = qs("#ppt-tenant");
  if (tenantSelect) tenantSelect.addEventListener("change", updateTenantRefView);
  loadTenants();
})();
