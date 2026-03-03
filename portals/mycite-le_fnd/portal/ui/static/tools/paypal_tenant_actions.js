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

  async function loadTenants() {
    var select = qs("#ppt-tenant");
    if (!select) return;
    try {
      var data = await api("GET", "/portal/api/progeny/tenants");
      var items = (data.items || []).filter(function (item) {
        var caps = item.capabilities || {};
        var status = item.status || {};
        return !!caps.paypal && (status.state || "active") === "active";
      });
      select.innerHTML = items
        .map(function (item) {
          var label = (item.display || {}).title || item.tenant_id;
          return '<option value="' + item.tenant_id + '">' + label + " (" + item.tenant_id + ")</option>";
        })
        .join("");
      if (!items.length) {
        select.innerHTML = '<option value="">No PayPal-capable tenants</option>';
      }
    } catch (err) {
      out("Failed to load tenants: " + err.message);
    }
  }

  function tenantId() {
    var select = qs("#ppt-tenant");
    return (select && select.value) || "";
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

  async function createOrder() {
    var id = tenantId();
    if (!id) {
      out("Select a tenant first.");
      return;
    }
    var amount = (qs("#ppt-amount") || {}).value || "10.00";
    var currency = ((qs("#ppt-currency") || {}).value || "USD").toUpperCase();
    try {
      var payload = await api("POST", "/portal/api/admin/paypal/tenant/" + encodeURIComponent(id) + "/orders/create", {
        amount: amount,
        currency: currency,
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
  var createBtn = qs("#ppt-create-order");
  if (createBtn) createBtn.addEventListener("click", createOrder);
  loadTenants();
})();
