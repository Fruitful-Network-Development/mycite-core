(function () {
  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function qsa(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  async function api(method, path, body) {
    var init = {
      method: method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" }
    };
    if (body && (method === "POST" || method === "PUT" || method === "PATCH")) {
      init.body = JSON.stringify(body);
    }

    var res = await fetch(path, init);
    var payload = {};
    try {
      payload = await res.json();
    } catch (_) {
      payload = {};
    }
    if (!res.ok) {
      var msg = payload.error || payload.message || ("HTTP " + res.status);
      throw new Error(msg);
    }
    return payload;
  }

  function endpoint(service, action) {
    return "/portal/api/admin/control/" + encodeURIComponent(service) + "/" + encodeURIComponent(action);
  }

  function portalStatusEndpoint(portalId) {
    return "/portal/api/admin/control/portal_instances/" + encodeURIComponent(portalId) + "/status";
  }

  function portalModeEndpoint(portalId) {
    return "/portal/api/admin/control/portal_instances/" + encodeURIComponent(portalId) + "/mode";
  }

  function portalListEndpoint() {
    return "/portal/api/admin/control/portal_instances";
  }

  function format(payload) {
    return JSON.stringify(payload, null, 2);
  }

  async function runAction(card, service, action) {
    var out = qs("[data-ops-output]", card);
    if (out) out.textContent = action + "…";

    try {
      var method = action === "status" ? "GET" : "POST";
      var payload = await api(method, endpoint(service, action));
      if (out) out.textContent = format(payload);
    } catch (e) {
      if (out) out.textContent = "Error: " + e.message;
    }
  }

  function renderPortalCard(card, item) {
    var out = qs("[data-portal-output]", card);
    var modeSel = qs("[data-portal-mode]", card);
    var authSel = qs("[data-portal-auth]", card);
    var loopback = qs("[data-portal-loopback]", card);
    var live = qs("[data-portal-live]", card);

    if (modeSel && item.mode) {
      modeSel.value = item.mode;
    }
    if (authSel && item.auth_mode) {
      authSel.value = item.auth_mode;
    }
    if (loopback) {
      loopback.textContent = item.loopback_url || "n/a";
    }
    if (live) {
      live.textContent = item.live_url || "(not configured)";
    }
    if (out) {
      out.textContent = format(item);
    }
  }

  async function fetchPortalList() {
    var payload = await api("GET", portalListEndpoint());
    var items = Array.isArray(payload.items) ? payload.items : [];
    var byId = {};
    items.forEach(function (item) {
      byId[String(item.portal_id || "")] = item;
    });

    qsa("[data-portal-instance]").forEach(function (card) {
      var portalId = card.getAttribute("data-portal-instance") || "";
      var item = byId[portalId];
      if (item) {
        renderPortalCard(card, item);
      }
    });
  }

  async function loadPortalStatus(card, portalId) {
    var out = qs("[data-portal-output]", card);
    if (out) out.textContent = "status…";
    try {
      var payload = await api("GET", portalStatusEndpoint(portalId));
      if (payload && payload.item) {
        renderPortalCard(card, payload.item);
      } else if (out) {
        out.textContent = format(payload);
      }
    } catch (e) {
      if (out) out.textContent = "Error: " + e.message;
    }
  }

  async function applyPortalMode(card, portalId) {
    var out = qs("[data-portal-output]", card);
    var modeSel = qs("[data-portal-mode]", card);
    var authSel = qs("[data-portal-auth]", card);
    var mode = modeSel ? modeSel.value : "off";
    var auth = authSel ? authSel.value : "none";

    if (out) out.textContent = "apply…";
    try {
      var payload = await api("POST", portalModeEndpoint(portalId), {
        mode: mode,
        auth_mode: auth
      });
      if (out) out.textContent = format(payload);
      await loadPortalStatus(card, portalId);
    } catch (e) {
      if (out) out.textContent = "Error: " + e.message;
    }
  }

  qsa("[data-ops-service]").forEach(function (card) {
    var service = card.getAttribute("data-ops-service");
    qsa("[data-action]", card).forEach(function (btn) {
      btn.addEventListener("click", function () {
        var action = btn.getAttribute("data-action");
        runAction(card, service, action);
      });
    });
  });

  qsa("[data-portal-instance]").forEach(function (card) {
    var portalId = card.getAttribute("data-portal-instance");
    qsa("[data-portal-action]", card).forEach(function (btn) {
      btn.addEventListener("click", function () {
        var action = btn.getAttribute("data-portal-action");
        if (action === "status") {
          loadPortalStatus(card, portalId);
          return;
        }
        if (action === "apply") {
          applyPortalMode(card, portalId);
        }
      });
    });
  });

  fetchPortalList().catch(function () {
    // list endpoint may be unavailable when bypassing nginx/admin headers
  });
})();
