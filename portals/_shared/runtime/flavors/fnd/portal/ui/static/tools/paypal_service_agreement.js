(function () {
  var runtime = window.ProviderToolRuntime || {};
  var qs = runtime.qs || function (sel) { return document.querySelector(sel); };
  var api = runtime.api;
  var appendLog = runtime.appendLog || (async function () {});

  function out(value) {
    var node = qs("#pps-output");
    if (!node) return;
    node.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
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
