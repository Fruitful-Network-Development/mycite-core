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

  var tenantProfiles = {};
  var latestPreviewByTenant = {};

  function tenantId() {
    var select = qs("#awst-tenant");
    return (select && select.value) || "";
  }

  function updateTenantRefView() {
    var id = tenantId();
    var refs = ((tenantProfiles[id] || {}).profile_refs || {});
    var profileNode = qs("#awst-ref-profile");
    var listNode = qs("#awst-ref-list");
    var entryNode = qs("#awst-ref-entry");
    if (profileNode) profileNode.textContent = String(refs.aws_profile_id || "");
    if (listNode) listNode.textContent = String(refs.aws_emailer_list_ref || "");
    if (entryNode) entryNode.textContent = String(refs.aws_emailer_entry_ref || "");
  }

  async function loadTenants() {
    var select = qs("#awst-tenant");
    if (!select) return;
    try {
      var data = await api("GET", "/portal/api/progeny/members");
      var items = (data.items || []).filter(function (item) {
        var caps = item.capabilities || {};
        var status = item.status || {};
        return !!caps.aws && (status.state || "active") === "active";
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
        select.innerHTML = '<option value="">No AWS-capable tenants</option>';
      }
      updateTenantRefView();
    } catch (err) {
      out("Failed to load tenants: " + err.message);
    }
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

  async function previewEmailerSource() {
    var id = tenantId();
    if (!id) {
      out("Select a tenant first.");
      return;
    }
    try {
      var payload = await api("GET", "/portal/api/aws/member/" + encodeURIComponent(id) + "/emailer_preview");
      latestPreviewByTenant[id] = payload;
      out(payload);
      appendLog({
        type: "portal.aws.tenant.emailer.preview.loaded",
        tenant_id: id,
        status: "ok",
        details: {
          entries_total: (((payload || {}).summary || {}).entries_total || 0),
          entries_subscribed: (((payload || {}).summary || {}).entries_subscribed || 0),
          contacts_total: (((payload || {}).summary || {}).contacts_total || 0),
        },
      });
    } catch (err) {
      out("Error: " + err.message);
      appendLog({
        type: "portal.aws.tenant.emailer.preview.failed",
        tenant_id: id,
        status: "failed",
        details: { error: err.message },
      });
    }
  }

  async function queueEmailerSync() {
    var id = tenantId();
    if (!id) {
      out("Select a tenant first.");
      return;
    }
    var preview = latestPreviewByTenant[id];
    if (!preview || !preview.ok) {
      out("Load a successful emailer preview before queueing.");
      return;
    }
    var formatHint = ((qs("#awst-format-hint") || {}).value || "text_byte_email_format").trim();
    try {
      var payload = await api("POST", "/portal/api/admin/aws/tenant/" + encodeURIComponent(id) + "/provision", {
        action: "emailer_sync_preview",
        payload: {
          emailer_preview: preview,
          format_hint: formatHint,
        },
      });
      out(payload);
      appendLog({
        type: "portal.aws.tenant.emailer.sync.queued",
        tenant_id: id,
        status: "ok",
        details: {
          request_id: payload.request_id || "",
          format_hint: formatHint,
        },
      });
    } catch (err) {
      out("Error: " + err.message);
      appendLog({
        type: "portal.aws.tenant.emailer.sync.failed",
        tenant_id: id,
        status: "failed",
        details: { error: err.message, format_hint: formatHint },
      });
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
  var previewBtn = qs("#awst-preview");
  if (previewBtn) previewBtn.addEventListener("click", previewEmailerSource);
  var queueBtn = qs("#awst-emailer-queue");
  if (queueBtn) queueBtn.addEventListener("click", queueEmailerSync);
  var provisionBtn = qs("#awst-provision");
  if (provisionBtn) provisionBtn.addEventListener("click", provision);
  var tenantSelect = qs("#awst-tenant");
  if (tenantSelect) {
    tenantSelect.addEventListener("change", updateTenantRefView);
  }
  loadTenants();
})();
