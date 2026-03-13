(function () {
  function qs(sel, root) {
    return (root || document).querySelector(sel);
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

  async function loadMemberProfiles(options) {
    var settings = options || {};
    var select = qs(settings.select || "");
    if (!select) return { items: [], profiles: {} };

    var data = await api("GET", settings.path || "/portal/api/progeny/members");
    var capability = String(settings.capability || "").trim();
    var items = (data.items || []).filter(function (item) {
      var caps = item.capabilities || {};
      var status = item.status || {};
      if (capability && !caps[capability]) return false;
      return (status.state || "active") === "active";
    });

    var profiles = {};
    items.forEach(function (item) {
      var id = String(item.member_id || item.tenant_id || "").trim();
      if (id) profiles[id] = item;
    });

    select.innerHTML = items
      .map(function (item) {
        var id = String(item.member_id || item.tenant_id || "").trim();
        var label = (item.display || {}).title || id;
        return '<option value="' + id + '">' + label + " (" + id + ")</option>";
      })
      .join("");
    if (!items.length) {
      select.innerHTML = '<option value="">' + String(settings.emptyLabel || "No matching members") + "</option>";
    }

    return { items: items, profiles: profiles };
  }

  function renderRefMap(refs, fieldMap) {
    var values = refs || {};
    Object.keys(fieldMap || {}).forEach(function (fieldKey) {
      var node = qs(fieldMap[fieldKey]);
      if (node) node.textContent = String(values[fieldKey] || "");
    });
  }

  window.ProviderToolRuntime = {
    api: api,
    appendLog: appendLog,
    loadMemberProfiles: loadMemberProfiles,
    qs: qs,
    renderRefMap: renderRefMap,
  };
})();
