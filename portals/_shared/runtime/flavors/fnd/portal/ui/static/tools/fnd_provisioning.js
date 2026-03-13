(function () {
  var API_BASE = "/portal/api/admin/fnd";
  var CT = { "Content-Type": "application/json" };

  function esc(s) {
    var d = document.createElement("div");
    d.textContent = String(s == null ? "" : s);
    return d.innerHTML;
  }

  function fndStat(id, msg, ok) {
    var e = document.getElementById(id);
    if (!e) return;
    e.textContent = msg;
    e.className = "fnd-status " + (ok ? "fnd-status--ok" : "fnd-status--err");
  }

  function tryJson(s) {
    try {
      return JSON.parse(s);
    } catch (_) {
      return null;
    }
  }

  function jsStringLiteral(value) {
    return String(value == null ? "" : value).replace(/\\/g, "\\\\").replace(/'/g, "\\'");
  }

  function cpBtn(val) {
    return (
      '<button class="cp-btn" title="Copy" onclick="navigator.clipboard.writeText(\'' +
      jsStringLiteral(val) +
      '\')">copy</button>'
    );
  }

  function url(path) {
    return API_BASE + path;
  }

  /* Tab switching */
  window.fndShowTab = function (name, btn) {
    ["tenants", "sites", "integrations", "bindings"].forEach(function (t) {
      var el = document.getElementById("fnd-tab-" + t);
      if (el) el.style.display = t === name ? "block" : "none";
    });
    document.querySelectorAll(".fnd-tabs button").forEach(function (b) {
      b.classList.remove("is-active");
    });
    if (btn) btn.classList.add("is-active");
  };

  /* Golden Path Provision */
  window.gpProvision = async function () {
    var slug = (document.getElementById("gp-slug") || {}).value || "";
    var domain = (document.getElementById("gp-domain") || {}).value || "";
    slug = slug.trim();
    domain = domain.trim();
    if (!slug || !domain) {
      fndStat("gp-status", "Slug and domain are required", false);
      return;
    }

    fndStat("gp-status", "Provisioning…", true);
    var resultDiv = document.getElementById("gp-result");
    if (resultDiv) {
      resultDiv.style.display = "none";
      resultDiv.innerHTML = "";
    }

    var ids = {};
    try {
      /* 1. Tenant */
      var r = await fetch(url("/tenants"), {
        method: "POST",
        headers: CT,
        body: JSON.stringify({ slug: slug }),
      });
      if (r.status === 409) {
        var tenants = await (await fetch(url("/tenants"))).json();
        var found = (tenants.items || []).find(function (t) {
          return t.slug === slug;
        });
        if (found) ids.tenant_id = found.id;
        else {
          fndStat("gp-status", "Tenant conflict but could not find existing", false);
          return;
        }
      } else if (r.ok) {
        var d = await r.json();
        ids.tenant_id = d.item.id;
      } else {
        fndStat("gp-status", "Tenant create failed: " + (await r.text()), false);
        return;
      }

      /* 2. Site */
      r = await fetch(url("/sites"), {
        method: "POST",
        headers: CT,
        body: JSON.stringify({ tenant_id: ids.tenant_id, domain: domain, kind: "client_webapp" }),
      });
      if (r.status === 409) {
        var sites = await (await fetch(url("/sites?tenant_id=" + ids.tenant_id))).json();
        var foundSite = (sites.items || []).find(function (s) {
          return s.domain === domain;
        });
        if (foundSite) ids.site_id = foundSite.id;
        else {
          fndStat("gp-status", "Site conflict but not found", false);
          return;
        }
      } else if (r.ok) {
        var sd = await r.json();
        ids.site_id = sd.item.id;
      } else {
        fndStat("gp-status", "Site create failed: " + (await r.text()), false);
        return;
      }

      /* 3. Integration: paypal */
      r = await fetch(url("/integrations"), {
        method: "POST",
        headers: CT,
        body: JSON.stringify({ tenant_id: ids.tenant_id, type: "paypal", label: slug + "-paypal", status: "active" }),
      });
      if (r.ok) ids.paypal_iid = (await r.json()).item.id;
      else {
        var ints = await (await fetch(url("/integrations?tenant_id=" + ids.tenant_id + "&type=paypal"))).json();
        if (ints.items && ints.items.length > 0) ids.paypal_iid = ints.items[0].id;
      }

      /* 4. Integration: aws */
      r = await fetch(url("/integrations"), {
        method: "POST",
        headers: CT,
        body: JSON.stringify({ tenant_id: ids.tenant_id, type: "aws", label: slug + "-aws", status: "active" }),
      });
      if (r.ok) ids.aws_iid = (await r.json()).item.id;
      else {
        var awsInts = await (await fetch(url("/integrations?tenant_id=" + ids.tenant_id + "&type=aws"))).json();
        if (awsInts.items && awsInts.items.length > 0) ids.aws_iid = awsInts.items[0].id;
      }

      /* 5. Integration: newsletter */
      r = await fetch(url("/integrations"), {
        method: "POST",
        headers: CT,
        body: JSON.stringify({
          tenant_id: ids.tenant_id,
          type: "newsletter",
          label: slug + "-newsletter",
          status: "active",
        }),
      });
      if (r.ok) ids.newsletter_iid = (await r.json()).item.id;
      else {
        var nlInts = await (await fetch(url("/integrations?tenant_id=" + ids.tenant_id + "&type=newsletter"))).json();
        if (nlInts.items && nlInts.items.length > 0) ids.newsletter_iid = nlInts.items[0].id;
      }

      /* 6. Bind all */
      var bindIds = [ids.paypal_iid, ids.aws_iid, ids.newsletter_iid].filter(Boolean);
      for (var i = 0; i < bindIds.length; i++) {
        var bi = bindIds[i];
        await fetch(url("/site-integrations"), {
          method: "POST",
          headers: CT,
          body: JSON.stringify({ site_id: ids.site_id, integration_instance_id: bi }),
        });
      }

      fndStat("gp-status", "✓ Provisioned successfully!", true);
      if (resultDiv) {
        resultDiv.style.display = "block";
        resultDiv.innerHTML =
          "<strong>Created IDs:</strong><br>" +
          "Tenant: <code>" +
          ids.tenant_id +
          "</code> " +
          cpBtn(ids.tenant_id) +
          "<br>" +
          "Site: <code>" +
          ids.site_id +
          "</code> " +
          cpBtn(ids.site_id) +
          "<br>" +
          (ids.paypal_iid ? "PayPal Instance: <code>" + ids.paypal_iid + "</code> " + cpBtn(ids.paypal_iid) + "<br>" : "") +
          (ids.aws_iid ? "AWS Instance: <code>" + ids.aws_iid + "</code> " + cpBtn(ids.aws_iid) + "<br>" : "") +
          (ids.newsletter_iid
            ? "Newsletter Instance: <code>" + ids.newsletter_iid + "</code> " + cpBtn(ids.newsletter_iid) + "<br>"
            : "");
      }

      window.fndLoadAll();
    } catch (e) {
      fndStat("gp-status", "Error: " + e, false);
    }
  };

  window.fndCreateTenant = async function () {
    var slug = (document.getElementById("t-slug") || {}).value || "";
    slug = slug.trim();
    if (!slug) {
      fndStat("t-status", "slug is required", false);
      return;
    }
    var meta = tryJson(((document.getElementById("t-meta") || {}).value || "").trim());
    try {
      var r = await fetch(url("/tenants"), {
        method: "POST",
        headers: CT,
        body: JSON.stringify({ slug: slug, meta: meta }),
      });
      var d = await r.json();
      if (!r.ok) {
        fndStat("t-status", "Error: " + (d.error || r.status), false);
        return;
      }
      fndStat("t-status", "Tenant created: id=" + d.item.id, true);
      document.getElementById("t-slug").value = "";
      document.getElementById("t-meta").value = "";
      window.fndLoadTenants();
    } catch (e) {
      fndStat("t-status", "Fetch error: " + e, false);
    }
  };

  window.fndCreateSite = async function () {
    var tid = (document.getElementById("s-tid") || {}).value || "";
    var domain = (document.getElementById("s-domain") || {}).value || "";
    domain = domain.trim();
    if (!tid || !domain) {
      fndStat("s-status", "tenant_id and domain required", false);
      return;
    }
    var kind = ((document.getElementById("s-kind") || {}).value || "").trim() || "client_webapp";
    var meta = tryJson(((document.getElementById("s-meta") || {}).value || "").trim());
    try {
      var r = await fetch(url("/sites"), {
        method: "POST",
        headers: CT,
        body: JSON.stringify({ tenant_id: parseInt(tid, 10), domain: domain, kind: kind, meta: meta }),
      });
      var d = await r.json();
      if (!r.ok) {
        fndStat("s-status", "Error: " + (d.error || r.status), false);
        return;
      }
      fndStat("s-status", "Site created: id=" + d.item.id, true);
      document.getElementById("s-domain").value = "";
      document.getElementById("s-meta").value = "";
      window.fndLoadSites();
    } catch (e) {
      fndStat("s-status", "Fetch error: " + e, false);
    }
  };

  window.fndCreateIntegration = async function () {
    var tid = (document.getElementById("i-tid") || {}).value || "";
    var typ = (document.getElementById("i-type") || {}).value || "";
    if (!tid) {
      fndStat("i-status-msg", "tenant_id required", false);
      return;
    }
    var label = ((document.getElementById("i-label") || {}).value || "").trim() || null;
    var status = (document.getElementById("i-status") || {}).value || "active";
    var meta = tryJson(((document.getElementById("i-meta") || {}).value || "").trim());
    try {
      var r = await fetch(url("/integrations"), {
        method: "POST",
        headers: CT,
        body: JSON.stringify({ tenant_id: parseInt(tid, 10), type: typ, label: label, status: status, meta: meta }),
      });
      var d = await r.json();
      if (!r.ok) {
        fndStat("i-status-msg", "Error: " + (d.error || r.status), false);
        return;
      }
      fndStat("i-status-msg", "Integration created: id=" + d.item.id, true);
      document.getElementById("i-label").value = "";
      document.getElementById("i-meta").value = "";
      window.fndLoadIntegrations();
    } catch (e) {
      fndStat("i-status-msg", "Fetch error: " + e, false);
    }
  };

  window.fndBindSiteIntegration = async function () {
    var sid = (document.getElementById("b-sid") || {}).value || "";
    var iid = (document.getElementById("b-iid") || {}).value || "";
    if (!sid || !iid) {
      fndStat("b-status", "site_id and integration_instance_id required", false);
      return;
    }
    try {
      var r = await fetch(url("/site-integrations"), {
        method: "POST",
        headers: CT,
        body: JSON.stringify({ site_id: parseInt(sid, 10), integration_instance_id: parseInt(iid, 10) }),
      });
      var d = await r.json();
      if (!r.ok) {
        fndStat("b-status", "Error: " + (d.error || r.status), false);
        return;
      }
      fndStat("b-status", "Bound site " + sid + " ↔ instance " + iid, true);
    } catch (e) {
      fndStat("b-status", "Fetch error: " + e, false);
    }
  };

  window.fndToggleStatus = async function (id, currentStatus) {
    var newStatus = currentStatus === "active" ? "inactive" : "active";
    if (!confirm("Set integration " + id + " to " + newStatus + "?")) return;
    try {
      var r = await fetch(url("/integrations/" + id + "/status"), {
        method: "PUT",
        headers: CT,
        body: JSON.stringify({ status: newStatus }),
      });
      if (r.ok) window.fndLoadIntegrations();
      else alert("Error: " + (await r.text()));
    } catch (e) {
      alert("Fetch error: " + e);
    }
  };

  window.loadBindingsHealth = async function () {
    var sid = (document.getElementById("health-sid") || {}).value || "";
    if (!sid) {
      var body = document.getElementById("health-body");
      if (body) body.innerHTML = '<tr><td colspan="5" style="color:var(--fg-light)">Enter a Site ID</td></tr>';
      return;
    }
    try {
      var r = await fetch(url("/bindings-health?site_id=" + sid));
      var d = await r.json();
      var tb = document.getElementById("health-body");
      if (!tb) return;
      tb.innerHTML = "";

      (d.items || []).forEach(function (b) {
        var configStatus = "";
        if (b.type === "paypal") {
          configStatus = b.paypal_config_exists
            ? '<span class="badge badge--ok">paypal.config ✓</span>'
            : '<span class="badge badge--err">paypal.config ✗</span>';
        } else if (b.type === "aws" || b.type === "aws_ses") {
          configStatus = b.aws_config_exists
            ? '<span class="badge badge--ok">aws.config ✓</span>'
            : '<span class="badge badge--err">aws.config ✗</span>';
        } else {
          configStatus = '<span class="badge badge--warn">n/a</span>';
        }

        var statusBadge =
          b.status === "active"
            ? '<span class="badge badge--ok">active</span>'
            : '<span class="badge badge--err">' + esc(b.status) + "</span>";

        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" +
          esc(b.integration_instance_id) +
          " " +
          cpBtn(b.integration_instance_id) +
          "</td>" +
          "<td>" +
          esc(b.type) +
          "</td>" +
          "<td>" +
          esc(b.label || "—") +
          "</td>" +
          "<td>" +
          statusBadge +
          "</td>" +
          "<td>" +
          configStatus +
          "</td>";
        tb.appendChild(tr);
      });

      if (!d.items || d.items.length === 0) {
        tb.innerHTML = '<tr><td colspan="5" style="color:var(--fg-light)">No bindings for site ' + esc(sid) + "</td></tr>";
      }
    } catch (e) {
      var tbErr = document.getElementById("health-body");
      if (tbErr) tbErr.innerHTML = '<tr><td colspan="5">Error: ' + esc(e) + "</td></tr>";
    }
  };

  window.fndLoadTenants = async function () {
    try {
      var r = await fetch(url("/tenants"));
      var d = await r.json();
      var tb = document.getElementById("list-tenants");
      if (!tb) return;
      tb.innerHTML = "";
      (d.items || []).forEach(function (t) {
        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" +
          esc(t.id) +
          " " +
          cpBtn(t.id) +
          "</td><td>" +
          esc(t.slug) +
          "</td><td>" +
          esc(JSON.stringify(t.meta)) +
          "</td><td>" +
          esc(t.created_at) +
          "</td><td></td>";
        tb.appendChild(tr);
      });
      if (!d.items || d.items.length === 0) {
        tb.innerHTML = '<tr><td colspan="5" style="color:var(--fg-light)">No tenants</td></tr>';
      }
    } catch (_) {
      var tbErr = document.getElementById("list-tenants");
      if (tbErr) tbErr.innerHTML = '<tr><td colspan="5">Error</td></tr>';
    }
  };

  window.fndLoadSites = async function () {
    try {
      var tid = (document.getElementById("sites-filter-tid") || {}).value || "";
      var listUrl = "/sites";
      if (tid) listUrl += "?tenant_id=" + tid;
      var r = await fetch(url(listUrl));
      var d = await r.json();
      var tb = document.getElementById("list-sites");
      if (!tb) return;
      tb.innerHTML = "";
      (d.items || []).forEach(function (s) {
        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" +
          esc(s.id) +
          " " +
          cpBtn(s.id) +
          "</td><td>" +
          esc(s.tenant_id) +
          "</td><td>" +
          esc(s.domain) +
          "</td><td>" +
          esc(s.kind) +
          "</td><td>" +
          esc(s.created_at) +
          "</td><td></td>";
        tb.appendChild(tr);
      });
      if (!d.items || d.items.length === 0) {
        tb.innerHTML = '<tr><td colspan="6" style="color:var(--fg-light)">No sites</td></tr>';
      }
    } catch (_) {
      var tbErr = document.getElementById("list-sites");
      if (tbErr) tbErr.innerHTML = '<tr><td colspan="6">Error</td></tr>';
    }
  };

  window.fndLoadIntegrations = async function () {
    try {
      var tid = (document.getElementById("int-filter-tid") || {}).value || "";
      var typ = (document.getElementById("int-filter-type") || {}).value || "";
      var params = [];
      if (tid) params.push("tenant_id=" + tid);
      if (typ) params.push("type=" + encodeURIComponent(typ));
      var listUrl = "/integrations" + (params.length ? "?" + params.join("&") : "");

      var r = await fetch(url(listUrl));
      var d = await r.json();
      var tb = document.getElementById("list-integrations");
      if (!tb) return;
      tb.innerHTML = "";
      (d.items || []).forEach(function (i) {
        var statusBadge =
          i.status === "active"
            ? '<span class="badge badge--ok">active</span>'
            : '<span class="badge badge--err">' + esc(i.status) + "</span>";

        var toggleBtn =
          '<button class="fnd-btn fnd-btn--sm ' +
          (i.status === "active" ? "fnd-btn--danger" : "fnd-btn--outline") +
          '" onclick="fndToggleStatus(' +
          i.id +
          ",'" +
          esc(i.status) +
          "')\">" +
          (i.status === "active" ? "Deactivate" : "Activate") +
          "</button>";

        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" +
          esc(i.id) +
          " " +
          cpBtn(i.id) +
          "</td><td>" +
          esc(i.tenant_id) +
          "</td><td>" +
          esc(i.type) +
          "</td><td>" +
          esc(i.label || "—") +
          "</td><td>" +
          statusBadge +
          "</td><td>" +
          esc(i.created_at) +
          "</td><td>" +
          toggleBtn +
          "</td>";
        tb.appendChild(tr);
      });
      if (!d.items || d.items.length === 0) {
        tb.innerHTML = '<tr><td colspan="7" style="color:var(--fg-light)">No integrations</td></tr>';
      }
    } catch (_) {
      var tbErr = document.getElementById("list-integrations");
      if (tbErr) tbErr.innerHTML = '<tr><td colspan="7">Error</td></tr>';
    }
  };

  window.fndLoadBindings = async function () {
    var sid = (document.getElementById("bind-filter-sid") || {}).value || "";
    if (!sid) {
      var tbEmpty = document.getElementById("list-bindings");
      if (tbEmpty) tbEmpty.innerHTML = '<tr><td colspan="5" style="color:var(--fg-light)">Enter a site ID</td></tr>';
      return;
    }
    try {
      var r = await fetch(url("/site-integrations?site_id=" + sid));
      var d = await r.json();
      var tb = document.getElementById("list-bindings");
      if (!tb) return;
      tb.innerHTML = "";
      (d.items || []).forEach(function (b) {
        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" +
          esc(b.site_id) +
          "</td><td>" +
          esc(b.integration_instance_id) +
          " " +
          cpBtn(b.integration_instance_id) +
          "</td><td>" +
          esc(b.type) +
          "</td><td>" +
          esc(b.label || "—") +
          "</td><td>" +
          esc(b.status) +
          "</td>";
        tb.appendChild(tr);
      });
      if (!d.items || d.items.length === 0) {
        tb.innerHTML = '<tr><td colspan="5" style="color:var(--fg-light)">No bindings</td></tr>';
      }
    } catch (_) {
      var tbErr = document.getElementById("list-bindings");
      if (tbErr) tbErr.innerHTML = '<tr><td colspan="5">Error</td></tr>';
    }
  };

  window.fndLoadAll = function () {
    window.fndLoadTenants();
    window.fndLoadSites();
    window.fndLoadIntegrations();
  };

  /* Initial load */
  window.fndLoadAll();
})();
