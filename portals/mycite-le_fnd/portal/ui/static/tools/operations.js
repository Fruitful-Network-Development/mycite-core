(function () {
  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function qsa(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  async function api(method, path) {
    var res = await fetch(path, {
      method: method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
    });
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

  async function runAction(card, service, action) {
    var out = qs("[data-ops-output]", card);
    if (out) out.textContent = action + "…";

    try {
      var method = action === "status" ? "GET" : "POST";
      var payload = await api(method, endpoint(service, action));
      if (out) out.textContent = JSON.stringify(payload, null, 2);
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
})();

