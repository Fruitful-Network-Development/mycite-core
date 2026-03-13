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

  function splitLines(value) {
    return String(value || "")
      .split(/\r?\n|,/)
      .map(function (item) { return item.trim(); })
      .filter(Boolean);
  }

  async function loadHosted() {
    try {
      var payload = await api("GET", "/portal/api/hosted");
      var item = payload.item || {};
      var aws = item.aws || {};
      var callbacks = aws.callback_mailboxes || {};
      var workflow = item.workflow || {};
      var general = Array.isArray(workflow.callback_mailboxes) ? workflow.callback_mailboxes : [];
      var member = Array.isArray(callbacks.member_callback_addresses) ? callbacks.member_callback_addresses : [];
      var generalNode = qs("#awsp-callbacks");
      var memberNode = qs("#awsp-member-callbacks");
      if (generalNode) generalNode.value = general.join("\n");
      if (memberNode) memberNode.value = member.join("\n");
      out(payload);
    } catch (err) {
      out("Error: " + err.message);
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

  async function saveHosted() {
    try {
      var hosted = await api("GET", "/portal/api/hosted");
      var item = hosted.item || {};
      if (!item.aws || typeof item.aws !== "object") item.aws = {};
      if (!item.aws.callback_mailboxes || typeof item.aws.callback_mailboxes !== "object") {
        item.aws.callback_mailboxes = {};
      }
      if (!item.workflow || typeof item.workflow !== "object") item.workflow = {};
      item.workflow.callback_mailboxes = splitLines((qs("#awsp-callbacks") || {}).value || "");
      item.aws.callback_mailboxes.fnd_callback_addresses = item.workflow.callback_mailboxes.slice();
      item.aws.callback_mailboxes.member_callback_addresses = splitLines((qs("#awsp-member-callbacks") || {}).value || "");
      var saved = await api("PUT", "/portal/api/hosted", item);
      out(saved);
      appendLog({
        type: "portal.aws.fnd.callback_mailboxes.saved",
        status: "ok",
        details: {
          workflow_callback_count: item.workflow.callback_mailboxes.length,
          member_callback_count: item.aws.callback_mailboxes.member_callback_addresses.length
        }
      });
    } catch (err) {
      out("Error: " + err.message);
      appendLog({
        type: "portal.aws.fnd.callback_mailboxes.failed",
        status: "failed",
        details: { error: err.message }
      });
    }
  }

  var btn = qs("#awsp-status");
  if (btn) btn.addEventListener("click", status);
  var loadBtn = qs("#awsp-load-hosted");
  if (loadBtn) loadBtn.addEventListener("click", loadHosted);
  var saveBtn = qs("#awsp-save-hosted");
  if (saveBtn) saveBtn.addEventListener("click", saveHosted);
  status();
  loadHosted();
})();
