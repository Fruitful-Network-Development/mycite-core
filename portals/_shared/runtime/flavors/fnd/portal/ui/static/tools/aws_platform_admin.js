(function () {
  var runtime = window.ProviderToolRuntime || {};
  var qs = runtime.qs || function (sel) { return document.querySelector(sel); };
  var api = runtime.api;
  var appendLog = runtime.appendLog || (async function () {});

  function summary(value) {
    var node = qs("#awsp-summary");
    if (!node) return;
    node.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  }

  function out(value) {
    var node = qs("#awsp-output");
    if (!node) return;
    node.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  }

  async function loadContext() {
    try {
      var payload = await api("GET", "/portal/api/data/system/config_context/aws_platform_admin");
      out(payload);
      appendLog({ type: "portal.aws_csm.context.checked", status: "ok" });
      return payload;
    } catch (err) {
      out("Error: " + err.message);
      appendLog({ type: "portal.aws_csm.context.failed", status: "failed", details: { error: err.message } });
      throw err;
    }
  }

  async function status() {
    try {
      var payload = await api("GET", "/portal/api/admin/aws/fnd/status");
      var profiles = Array.isArray(payload.profiles) ? payload.profiles : [];
      summary({
        canonical_root: payload.canonical_root || "",
        tenant_profiles_count: payload.tenant_profiles_count || profiles.length,
        ready_for_handoff_count: payload.ready_for_handoff_count || 0,
        send_as_confirmed_count: payload.send_as_confirmed_count || 0,
        profiles: profiles
      });
      appendLog({ type: "portal.aws_csm.status.checked", status: "ok" });
      return payload;
    } catch (err) {
      summary("Error: " + err.message);
      appendLog({ type: "portal.aws_csm.status.failed", status: "failed", details: { error: err.message } });
      throw err;
    }
  }

  async function refreshAll() {
    await status();
    await loadContext();
  }

  var btn = qs("#awsp-status");
  if (btn) btn.addEventListener("click", status);
  var contextBtn = qs("#awsp-context");
  if (contextBtn) contextBtn.addEventListener("click", loadContext);
  refreshAll().catch(function () {});
})();
