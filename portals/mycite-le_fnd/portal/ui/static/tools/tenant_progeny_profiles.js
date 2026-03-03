(function () {
  function qs(sel) {
    return document.querySelector(sel);
  }

  function esc(value) {
    var d = document.createElement("div");
    d.textContent = String(value == null ? "" : value);
    return d.innerHTML;
  }

  function setOut(obj) {
    var out = qs("#tp-output");
    if (out) out.textContent = typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
  }

  async function loadProfiles() {
    try {
      var res = await fetch("/portal/api/progeny/tenants", { credentials: "same-origin" });
      var data = await res.json();
      if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));

      var body = qs("#tp-body");
      if (!body) return;
      var items = Array.isArray(data.items) ? data.items : [];
      if (items.length === 0) {
        body.innerHTML = '<tr><td colspan="7">No tenant progeny profiles found.</td></tr>';
      } else {
        body.innerHTML = items
          .map(function (item) {
            var caps = item.capabilities || {};
            var refs = item.profile_refs || {};
            var status = item.status || {};
            return (
              "<tr>" +
              "<td><code>" + esc(item.tenant_id) + "</code></td>" +
              "<td>" + esc((item.display || {}).title || "") + "</td>" +
              "<td><code>" + esc(item.tenant_msn_id || "") + "</code></td>" +
              "<td>" + (caps.paypal ? "enabled" : "disabled") + "</td>" +
              "<td>" + (caps.aws ? "enabled" : "disabled") + "</td>" +
              "<td>" + esc(status.state || "active") + "</td>" +
              "<td><code>" + esc(refs.paypal_profile_id || "") + "</code><br><code>" + esc(refs.aws_profile_id || "") + "</code></td>" +
              "</tr>"
            );
          })
          .join("");
      }
      setOut({ ok: true, count: items.length });
    } catch (err) {
      setOut("Error: " + err.message);
    }
  }

  var btn = qs("#tp-refresh");
  if (btn) btn.addEventListener("click", loadProfiles);
  loadProfiles();
})();
