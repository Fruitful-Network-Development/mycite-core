(function () {
  function qs(sel) {
    return document.querySelector(sel);
  }

  function out(value) {
    var node = qs("#awst-output");
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
    var select = qs("#awst-tenant");
    if (!select) return;
    try {
      var data = await api("GET", "/portal/api/progeny/tenants");
      var items = (data.items || []).filter(function (item) {
        var caps = item.capabilities || {};
        var status = item.status || {};
        return !!caps.aws && (status.state || "active") === "active";
      });
      select.innerHTML = items
        .map(function (item) {
          var label = (item.display || {}).title || item.tenant_id;
          return '<option value="' + item.tenant_id + '">' + label + " (" + item.tenant_id + ")</option>";
        })
        .join("");
      if (!items.length) {
        select.innerHTML = '<option value="">No AWS-capable tenants</option>';
      }
    } catch (err) {
      out("Failed to load tenants: " + err.message);
    }
  }

  function tenantId() {
    var select = qs("#awst-tenant");
    return (select && select.value) || "";
  }

  async function status() {
    var id = tenantId();
    if (!id) {
      out("Select a tenant first.");
      return;
    }
    try {
      var payload = await api("GET", "/portal/api/admin/aws/tenant/" + encodeURIComponent(id) + "/status");
      out(payload);
      appendLog({ type: "portal.aws.tenant.status.checked", tenant_id: id, status: "ok" });
    } catch (err) {
      out("Error: " + err.message);
      appendLog({ type: "portal.aws.tenant.status.failed", tenant_id: id, status: "failed", details: { error: err.message } });
    }
  }

  async function provision() {
    var id = tenantId();
    if (!id) {
      out("Select a tenant first.");
      return;
    }
    var action = ((qs("#awst-action") || {}).value || "provision").trim().toLowerCase();
    try {
      var payload = await api("POST", "/portal/api/admin/aws/tenant/" + encodeURIComponent(id) + "/provision", {
        action: action,
      });
      out(payload);
      appendLog({
        type: "portal.aws.tenant.provision.queued",
        tenant_id: id,
        status: "ok",
        details: { action: action, request_id: payload.request_id || "" },
      });
    } catch (err) {
      out("Error: " + err.message);
      appendLog({
        type: "portal.aws.tenant.provision.failed",
        tenant_id: id,
        status: "failed",
        details: { action: action, error: err.message },
      });
    }
  }

  var statusBtn = qs("#awst-status");
  if (statusBtn) statusBtn.addEventListener("click", status);
  var provisionBtn = qs("#awst-provision");
  if (provisionBtn) provisionBtn.addEventListener("click", provision);
  loadTenants();
})();
