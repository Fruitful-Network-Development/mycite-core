(function () {
  function qs(sel) {
    return document.querySelector(sel);
  }

  function out(value) {
    var node = qs("#pps-output");
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

  async function status() {
    try {
      var payload = await api("GET", "/portal/api/admin/paypal/fnd/status");
      out(payload);
      appendLog({ type: "portal.paypal.fnd.status.checked", status: "ok" });
    } catch (err) {
      out("Error: " + err.message);
      appendLog({ type: "portal.paypal.fnd.status.failed", status: "failed", details: { error: err.message } });
    }
  }

  async function registerWebhook() {
    var webhookUrl = ((qs("#pps-webhook-url") || {}).value || "").trim();
    var eventsRaw = ((qs("#pps-events") || {}).value || "").trim();
    var eventTypes = eventsRaw
      ? eventsRaw.split(",").map(function (v) { return v.trim(); }).filter(Boolean)
      : ["PAYMENT.CAPTURE.COMPLETED"];
    try {
      var payload = await api("POST", "/portal/api/admin/paypal/fnd/webhooks/register", {
        webhook_url: webhookUrl,
        event_types: eventTypes,
      });
      out(payload);
      appendLog({
        type: "portal.paypal.fnd.webhook.registered",
        status: "ok",
        details: { webhook_url: webhookUrl, event_types: eventTypes },
      });
    } catch (err) {
      out("Error: " + err.message);
      appendLog({
        type: "portal.paypal.fnd.webhook.failed",
        status: "failed",
        details: { webhook_url: webhookUrl, error: err.message },
      });
    }
  }

  var statusBtn = qs("#pps-status");
  if (statusBtn) statusBtn.addEventListener("click", status);
  var registerBtn = qs("#pps-register");
  if (registerBtn) registerBtn.addEventListener("click", registerWebhook);
  status();
})();
