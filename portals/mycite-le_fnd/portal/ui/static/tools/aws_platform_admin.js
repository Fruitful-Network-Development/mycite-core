(function () {
  function qs(sel) {
    return document.querySelector(sel);
  }

  function out(value) {
    var node = qs("#awsp-output");
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
      var payload = await api("GET", "/portal/api/admin/aws/fnd/status");
      out(payload);
      appendLog({ type: "portal.aws.fnd.status.checked", status: "ok" });
    } catch (err) {
      out("Error: " + err.message);
      appendLog({ type: "portal.aws.fnd.status.failed", status: "failed", details: { error: err.message } });
    }
  }

  var btn = qs("#awsp-status");
  if (btn) btn.addEventListener("click", status);
  status();
})();
