(function () {
  var runtime = window.ProviderToolRuntime || {};
  var qs = runtime.qs || function (sel) { return document.querySelector(sel); };
  var api = runtime.api;
  var appendLog = runtime.appendLog || (async function () {});

  function out(value) {
    var node = qs("#awsp-output");
    if (!node) return;
    node.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
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
