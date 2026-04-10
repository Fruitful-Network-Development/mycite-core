/* V2 native portal: hydrate activity bar from admin shell; call JSON tool routes only. */
(function () {
  const ADMIN_SHELL_REQUEST_SCHEMA = "mycite.v2.admin.shell.request.v1";
  const ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA = "mycite.v2.admin.aws.read_only.request.v1";
  const ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA = "mycite.v2.admin.aws.narrow_write.request.v1";
  const SLICE_HOME = "admin_band0.home_status";
  const SLICE_REGISTRY = "admin_band0.tool_registry";
  const SLICE_AWS_RO = "admin_band1.aws_read_only_surface";
  const SLICE_AWS_NW = "admin_band2.aws_narrow_write_surface";

  const qs = (sel, root) => (root || document).querySelector(sel);
  const qsa = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  const tenantId = (document.body.dataset.tenantId || "fnd").trim();

  let lastAwsReadOnly = null;

  function postJson(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => r.json().then((j) => ({ ok: r.ok, status: r.status, json: j })));
  }

  function setWorkbench(title, subtitle, html) {
    const t = qs("#v2-workbench-title");
    const s = qs("#v2-workbench-subtitle");
    const b = qs("#v2-workbench-body");
    if (t) t.textContent = title;
    if (s) s.textContent = subtitle;
    if (b) b.innerHTML = html;
  }

  function openInspector(title, jsonPayload) {
    const shell = qs(".ide-shell");
    const inspector = qs("#portalInspector");
    const titleEl = qs("#portalInspectorTitle");
    const emptyEl = qs("#portalInspectorEmptyDefault");
    const pre = qs("#v2-inspector-json");
    if (titleEl) titleEl.textContent = title;
    if (emptyEl) emptyEl.hidden = true;
    if (pre) {
      pre.hidden = false;
      pre.textContent = JSON.stringify(jsonPayload, null, 2);
    }
    if (inspector) {
      inspector.classList.remove("is-collapsed");
      inspector.setAttribute("aria-hidden", "false");
    }
    if (shell) {
      shell.setAttribute("data-inspector-collapsed", "false");
      shell.setAttribute("data-shell-composition", "tool");
    }
  }

  function closeInspector() {
    const shell = qs(".ide-shell");
    const inspector = qs("#portalInspector");
    const emptyEl = qs("#portalInspectorEmptyDefault");
    const pre = qs("#v2-inspector-json");
    if (emptyEl) emptyEl.hidden = false;
    if (pre) {
      pre.hidden = true;
      pre.textContent = "";
    }
    if (inspector) {
      inspector.classList.add("is-collapsed");
      inspector.setAttribute("aria-hidden", "true");
    }
    if (shell) {
      shell.setAttribute("data-inspector-collapsed", "true");
      shell.setAttribute("data-shell-composition", "system");
    }
  }

  function renderHomeCards(health, shellEnvelope) {
    const hOk = health && health.ok;
    const datum = health && health.datum_health;
    const aws = health && health.aws_config_health;
    const surface = shellEnvelope && shellEnvelope.surface_payload;
    const audit = surface && surface.runtime_health && surface.runtime_health.audit_log;
    return (
      '<div class="v2-card-grid">' +
      '<article class="v2-card"><h3>Portal health</h3><p>' +
      (hOk ? "Ready" : "Degraded — see /portal/healthz") +
      "</p></article>" +
      '<article class="v2-card"><h3>Canonical datum</h3><p>' +
      (datum ? datum.row_count + " rows" : "—") +
      "</p></article>" +
      '<article class="v2-card"><h3>AWS profile file</h3><p>' +
      (aws && aws.live_profile_mapping ? "Live profile mapped" : "Not a live profile") +
      "</p></article>" +
      '<article class="v2-card"><h3>Admin audit</h3><p>' +
      (audit ? audit.status : "—") +
      "</p></article>" +
      "</div>"
    );
  }

  async function loadHome() {
    setWorkbench("Home", "Admin shell + host health", "<p>Loading…</p>");
    qsa("#v2-activity-nav .ide-activitylink").forEach((a) => a.classList.remove("is-active"));
    const homeLink = qs('#v2-activity-nav a[data-nav="home"]');
    if (homeLink) homeLink.classList.add("is-active");

    const [healthR, shellR] = await Promise.all([
      fetch("/portal/healthz", { credentials: "same-origin" }).then((r) => r.json()),
      postJson("/portal/api/v2/admin/shell", {
        schema: ADMIN_SHELL_REQUEST_SCHEMA,
        requested_slice_id: SLICE_HOME,
        tenant_scope: { scope_id: "internal-admin", audience: "internal" },
      }),
    ]);

    const err = shellR.json && shellR.json.error;
    const subtitle = err && err.message ? err.message : "Internal admin shell";
    setWorkbench(
      "Home",
      subtitle,
      renderHomeCards(healthR, shellR.json) +
        '<h3 style="margin-top:1.25rem;font-size:14px">Shell envelope</h3>' +
        '<pre class="v2-json-panel" style="margin-top:8px">' +
        JSON.stringify(shellR.json, null, 2) +
        "</pre>"
    );
  }

  async function loadToolRegistry() {
    setWorkbench("Tool registry", "Shell-owned catalog", "<p>Loading…</p>");
    qsa("#v2-activity-nav .ide-activitylink").forEach((a) => a.classList.remove("is-active"));
    const link = qs('#v2-activity-nav a[data-nav="registry"]');
    if (link) link.classList.add("is-active");

    const shellR = await postJson("/portal/api/v2/admin/shell", {
      schema: ADMIN_SHELL_REQUEST_SCHEMA,
      requested_slice_id: SLICE_REGISTRY,
      tenant_scope: { scope_id: "internal-admin", audience: "internal" },
    });
    setWorkbench(
      "Tool registry",
      "Launch AWS tools from the activity bar",
      '<pre class="v2-json-panel">' + JSON.stringify(shellR.json, null, 2) + "</pre>"
    );
  }

  async function loadAwsReadOnly() {
    setWorkbench("AWS (read-only)", "Trusted-tenant runtime envelope", "<p>Loading…</p>");
    qsa("#v2-activity-nav .ide-activitylink").forEach((a) => a.classList.remove("is-active"));
    const link = qs('#v2-activity-nav a[data-nav="aws-ro"]');
    if (link) link.classList.add("is-active");

    const res = await postJson("/portal/api/v2/admin/aws/read-only", {
      schema: ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA,
      tenant_scope: { scope_id: tenantId, audience: "trusted-tenant" },
    });
    lastAwsReadOnly = res.json;
    const sp = res.json && res.json.surface_payload;
    const allowed = sp && sp.allowed_send_domains ? sp.allowed_send_domains.join(", ") : "";
    setWorkbench(
      "AWS (read-only)",
      res.ok ? "Surface loaded" : "Error — see JSON",
      (allowed ? "<p><strong>Allowed send domains:</strong> " + allowed + "</p>" : "") +
        '<pre class="v2-json-panel">' +
        JSON.stringify(res.json, null, 2) +
        "</pre>"
    );
    openInspector("AWS read-only", res.json);
  }

  async function loadResourceWorkbench() {
    setWorkbench("Resource workbench", "Canonical system datum", "<p>Loading…</p>");
    qsa("#v2-activity-nav .ide-activitylink").forEach((a) => a.classList.remove("is-active"));
    const link = qs('#v2-activity-nav a[data-nav="datum"]');
    if (link) link.classList.add("is-active");

    const r = await fetch("/portal/api/v2/data/system/resource-workbench", { credentials: "same-origin" });
    const j = await r.json();
    setWorkbench(
      "Resource workbench",
      j.row_count != null ? j.row_count + " rows" : "—",
      '<pre class="v2-json-panel">' + JSON.stringify(j, null, 2) + "</pre>"
    );
  }

  function loadAwsNarrowWriteForm() {
    setWorkbench("AWS narrow write", "Bounded field: selected_verified_sender", "");
    qsa("#v2-activity-nav .ide-activitylink").forEach((a) => a.classList.remove("is-active"));
    const link = qs('#v2-activity-nav a[data-nav="aws-nw"]');
    if (link) link.classList.add("is-active");

    const sp = lastAwsReadOnly && lastAwsReadOnly.surface_payload;
    const profileId =
      (sp && sp.canonical_newsletter_operational_profile && sp.canonical_newsletter_operational_profile.profile_id) || "";
    const currentSender = (sp && sp.selected_verified_sender) || "";

    const html =
      '<form id="v2-narrow-write-form" class="v2-card" style="max-width:520px">' +
      "<h3>Update verified sender</h3>" +
      '<p style="font-size:13px;margin:0 0 10px">Uses tenant <code>' +
      tenantId +
      "</code> and trusted-tenant audience.</p>" +
      '<label style="display:block;font-size:13px;margin-bottom:6px">profile_id</label>' +
      '<input name="profile_id" value="' +
      profileId +
      '" style="width:100%;box-sizing:border-box;margin-bottom:10px;padding:6px 8px" />' +
      '<label style="display:block;font-size:13px;margin-bottom:6px">selected_verified_sender</label>' +
      '<input name="selected_verified_sender" value="' +
      currentSender +
      '" style="width:100%;box-sizing:border-box;margin-bottom:12px;padding:6px 8px" />' +
      '<button type="submit" class="ide-sessionAction ide-sessionAction--button" style="border-radius:6px">Apply narrow write</button>' +
      "</form>" +
      '<pre id="v2-narrow-write-result" class="v2-json-panel" style="margin-top:12px" hidden></pre>';

    setWorkbench("AWS narrow write", "Read-only surface must be loaded once this session for profile hints.", html);

    const form = qs("#v2-narrow-write-form");
    const out = qs("#v2-narrow-write-result");
    if (!form || !out) return;

    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const fd = new FormData(form);
      const body = {
        schema: ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA,
        tenant_scope: { scope_id: tenantId, audience: "trusted-tenant" },
        focus_subject: "v2-portal-ui",
        profile_id: (fd.get("profile_id") || "").toString().trim(),
        selected_verified_sender: (fd.get("selected_verified_sender") || "").toString().trim(),
      };
      out.hidden = false;
      out.textContent = "…";
      const res = await postJson("/portal/api/v2/admin/aws/narrow-write", body);
      out.textContent = JSON.stringify(res.json, null, 2);
      openInspector("AWS narrow write", res.json);
    });
  }

  function buildActivityNav() {
    const nav = qs("#v2-activity-nav");
    if (!nav) return;

    const items = [
      { nav: "home", label: "HOME", action: loadHome },
      { nav: "registry", label: "REGISTRY", action: loadToolRegistry },
      { nav: "aws-ro", label: "AWS", action: loadAwsReadOnly },
      { nav: "aws-nw", label: "AWS WRITE", action: loadAwsNarrowWriteForm },
      { nav: "datum", label: "DATUM", action: loadResourceWorkbench },
    ];

    nav.innerHTML = "";
    items.forEach((item) => {
      const a = document.createElement("a");
      a.className = "ide-activitylink";
      a.href = "#";
      a.dataset.nav = item.nav;
      a.innerHTML = "<span>" + item.label + "</span>";
      a.addEventListener("click", (e) => {
        e.preventDefault();
        item.action();
      });
      nav.appendChild(a);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    buildActivityNav();
    loadHome();
    const closeBtn = qs("[data-inspector-close]");
    if (closeBtn) closeBtn.addEventListener("click", closeInspector);
  });
})();
