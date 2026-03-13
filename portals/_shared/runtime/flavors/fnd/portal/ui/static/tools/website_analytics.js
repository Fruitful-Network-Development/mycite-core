(function () {
  var runtime = window.ProviderToolRuntime || {};
  var qs = runtime.qs || function (sel) { return document.querySelector(sel); };
  var api = runtime.api;
  var loadMemberProfiles = runtime.loadMemberProfiles;
  var appendLog = runtime.appendLog || (async function () {});

  var analyticsByMember = {};

  function setOut(value) {
    var node = qs("#wan-output");
    if (!node) return;
    node.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  }

  function selectedMemberId() {
    return ((qs("#wan-member") || {}).value || "").trim();
  }

  function renderSelected(item) {
    item = item || {};
    var metrics = item.metrics || {};
    if (qs("#wan-domain")) qs("#wan-domain").textContent = String(item.domain || "");
    if (qs("#wan-base-url")) qs("#wan-base-url").textContent = String(item.base_url || "");
    if (qs("#wan-ref")) qs("#wan-ref").textContent = String(item.analytics_ref || "");
    if (qs("#wan-callback")) qs("#wan-callback").textContent = String(item.callback_email || "");
    setOut({
      member_id: item.member_id || "",
      title: item.title || "",
      provider: item.provider || "",
      status: item.status || "",
      domain: item.domain || "",
      base_url: item.base_url || "",
      analytics_ref: item.analytics_ref || "",
      callback_email: item.callback_email || "",
      metrics: metrics
    });
  }

  function renderTable(items) {
    var body = qs("#wan-table");
    if (!body) return;
    items = Array.isArray(items) ? items : [];
    if (!items.length) {
      body.innerHTML = '<tr><td colspan="6">No analytics-aware members found.</td></tr>';
      return;
    }
    body.innerHTML = items.map(function (item) {
      var metrics = item.metrics || {};
      return [
        "<tr>",
        "<td><strong>" + String(item.title || item.member_id || "") + "</strong><br><code>" + String(item.member_id || "") + "</code></td>",
        "<td><code>" + String(item.domain || "") + "</code></td>",
        "<td>" + String(item.status || "") + "</td>",
        "<td>" + String(metrics.page_views_7d || 0) + "</td>",
        "<td>" + String(metrics.unique_visitors_7d || 0) + "</td>",
        "<td>" + String(metrics.contact_events_30d || 0) + "</td>",
        "</tr>"
      ].join("");
    }).join("");
  }

  async function refreshList() {
    if (!api || !loadMemberProfiles) return;
    try {
      var analytics = await api("GET", "/portal/api/analytics/members");
      var items = Array.isArray(analytics.items) ? analytics.items : [];
      analyticsByMember = {};
      items.forEach(function (item) {
        var id = String(item.member_id || "").trim();
        if (id) analyticsByMember[id] = item;
      });
      renderTable(items);

      var loaded = await loadMemberProfiles({
        select: "#wan-member",
        capability: "analytics",
        emptyLabel: "No analytics-aware members"
      });
      var selectedId = selectedMemberId();
      if (!selectedId && loaded.items && loaded.items.length) {
        selectedId = String(loaded.items[0].member_id || loaded.items[0].tenant_id || "").trim();
        var select = qs("#wan-member");
        if (select) select.value = selectedId;
      }
      renderSelected(analyticsByMember[selectedId] || items[0] || {});
    } catch (err) {
      setOut("Error: " + err.message);
    }
  }

  async function loadMemberAnalytics() {
    if (!api) return;
    var memberId = selectedMemberId();
    if (!memberId) {
      setOut("Select a member first.");
      return;
    }
    try {
      var payload = await api("GET", "/portal/api/analytics/members/" + encodeURIComponent(memberId));
      analyticsByMember[memberId] = payload.item || {};
      renderSelected(payload.item || {});
      appendLog({
        type: "portal.website_analytics.member.loaded",
        member_id: memberId,
        status: "ok",
        details: { domain: String(((payload.item || {}).domain) || "") }
      });
    } catch (err) {
      setOut("Error: " + err.message);
      appendLog({
        type: "portal.website_analytics.member.failed",
        member_id: memberId,
        status: "failed",
        details: { error: err.message }
      });
    }
  }

  var refreshBtn = qs("#wan-refresh");
  if (refreshBtn) refreshBtn.addEventListener("click", refreshList);
  var loadBtn = qs("#wan-load");
  if (loadBtn) loadBtn.addEventListener("click", loadMemberAnalytics);
  var memberSelect = qs("#wan-member");
  if (memberSelect) {
    memberSelect.addEventListener("change", function () {
      renderSelected(analyticsByMember[selectedMemberId()] || {});
    });
  }

  refreshList();
})();
