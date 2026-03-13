(function () {
  var runtime = window.ProviderToolRuntime || {};
  var qs = runtime.qs || function (sel) { return document.querySelector(sel); };
  var api = runtime.api;
  var appendLog = runtime.appendLog || (async function () {});
  var loadMemberProfiles = runtime.loadMemberProfiles;
  var renderRefMap = runtime.renderRefMap || function () {};

  function out(value) {
    var node = qs("#ppt-output");
    if (!node) return;
    node.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
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
    renderRefMap(refs, {
      paypal_profile_id: "#ppt-ref-profile",
      paypal_site_base_url: "#ppt-ref-site",
      paypal_checkout_return_url: "#ppt-ref-return",
      paypal_checkout_cancel_url: "#ppt-ref-cancel",
      paypal_webhook_listener_url: "#ppt-ref-webhook",
      paypal_checkout_brand_name: "#ppt-ref-brand",
    });
  }

  async function loadTenants() {
    if (!loadMemberProfiles) return;
    try {
      var loaded = await loadMemberProfiles({
        select: "#ppt-tenant",
        capability: "paypal",
        emptyLabel: "No PayPal-capable members",
      });
      tenantProfiles = {};
      tenantProfiles = loaded.profiles || {};
      updateTenantRefView();
    } catch (err) {
      out("Failed to load members: " + err.message);
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
