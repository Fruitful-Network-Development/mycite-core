/* V2 native portal: activity bar from admin shell catalog; JSON tool routes only. */
(function () {
  const ADMIN_SHELL_REQUEST_SCHEMA = "mycite.v2.admin.shell.request.v1";
  const ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA = "mycite.v2.admin.aws.read_only.request.v1";
  const ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA = "mycite.v2.admin.aws.narrow_write.request.v1";
  const SLICE_HOME = "admin_band0.home_status";
  const SLICE_REGISTRY = "admin_band0.tool_registry";
  const SLICE_AWS_RO = "admin_band1.aws_read_only_surface";
  const SLICE_AWS_NW = "admin_band2.aws_narrow_write_surface";
  const SLICE_DATUM = "datum.workbench";

  const qs = (sel, root) => (root || document).querySelector(sel);
  const qsa = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  const tenantId = (document.body.dataset.tenantId || "fnd").trim();

  let lastAwsReadOnly = null;

  const SLICE_HANDLERS = {
    [SLICE_HOME]: loadHome,
    [SLICE_REGISTRY]: loadToolRegistry,
    [SLICE_AWS_RO]: loadAwsReadOnly,
    [SLICE_AWS_NW]: loadAwsNarrowWriteForm,
    [SLICE_DATUM]: loadResourceWorkbench,
  };

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

  function setActiveNav(sliceId) {
    qsa("#v2-activity-nav .ide-activitylink").forEach((a) => {
      a.classList.toggle("is-active", a.dataset.sliceId === sliceId);
    });
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
    setActiveNav(SLICE_HOME);

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
    setActiveNav(SLICE_REGISTRY);

    const shellR = await postJson("/portal/api/v2/admin/shell", {
      schema: ADMIN_SHELL_REQUEST_SCHEMA,
      requested_slice_id: SLICE_REGISTRY,
      tenant_scope: { scope_id: "internal-admin", audience: "internal" },
    });
    setWorkbench(
      "Tool registry",
      "Tools below are registered by the shell; launch uses cataloged runtime entrypoints.",
      '<pre class="v2-json-panel">' + JSON.stringify(shellR.json, null, 2) + "</pre>"
    );
  }

  async function loadAwsReadOnly() {
    setWorkbench("AWS (read-only)", "Trusted-tenant runtime envelope", "<p>Loading…</p>");
    setActiveNav(SLICE_AWS_RO);

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
    setActiveNav(SLICE_DATUM);

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
    setActiveNav(SLICE_AWS_NW);

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

    setWorkbench("AWS narrow write", "Load AWS read-only once per session for profile hints.", html);

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

  function labelForEntry(entry, sliceId) {
    const raw = (entry && (entry.label || entry.tool_id)) || sliceId;
    const u = String(raw).toUpperCase();
    return u.length > 22 ? u.slice(0, 20) + "…" : u;
  }

  function buildFallbackNav(nav) {
    nav.innerHTML = "";
    const items = [
      { id: SLICE_HOME, label: "HOME", fn: loadHome },
      { id: SLICE_REGISTRY, label: "REGISTRY", fn: loadToolRegistry },
      { id: SLICE_AWS_RO, label: "AWS", fn: loadAwsReadOnly },
      { id: SLICE_AWS_NW, label: "AWS WRITE", fn: loadAwsNarrowWriteForm },
      { id: SLICE_DATUM, label: "DATUM", fn: loadResourceWorkbench },
    ];
    items.forEach((item) => {
      const a = document.createElement("a");
      a.className = "ide-activitylink";
      a.href = "#";
      a.dataset.sliceId = item.id;
      a.innerHTML = "<span>" + item.label + "</span>";
      a.addEventListener("click", (e) => {
        e.preventDefault();
        item.fn();
      });
      nav.appendChild(a);
    });
  }

  async function buildActivityNavFromShellCatalog() {
    const nav = qs("#v2-activity-nav");
    if (!nav) return;

    const shellR = await postJson("/portal/api/v2/admin/shell", {
      schema: ADMIN_SHELL_REQUEST_SCHEMA,
      requested_slice_id: SLICE_HOME,
      tenant_scope: { scope_id: "internal-admin", audience: "internal" },
    });

    const sp = shellR.json && shellR.json.surface_payload;
    nav.innerHTML = "";
    const seen = new Set();

    function addLink(sliceId, entry) {
      if (seen.has(sliceId)) return;
      const fn = SLICE_HANDLERS[sliceId];
      if (!fn) return;
      seen.add(sliceId);
      const a = document.createElement("a");
      a.className = "ide-activitylink";
      a.href = "#";
      a.dataset.sliceId = sliceId;
      a.innerHTML = "<span>" + labelForEntry(entry, sliceId) + "</span>";
      a.title = (entry && entry.label) || sliceId;
      a.addEventListener("click", (e) => {
        e.preventDefault();
        fn();
      });
      nav.appendChild(a);
    }

    if (sp && Array.isArray(sp.available_admin_slices)) {
      sp.available_admin_slices.forEach((entry) => {
        if (!entry || !entry.launchable || !entry.slice_id) return;
        addLink(entry.slice_id, entry);
      });
    }

    if (sp && Array.isArray(sp.available_tool_slices)) {
      sp.available_tool_slices.forEach((entry) => {
        if (!entry || !entry.launchable || !entry.slice_id) return;
        addLink(entry.slice_id, entry);
      });
    }

    addLink(SLICE_DATUM, { label: "Resource workbench" });

    if (!nav.children.length) {
      buildFallbackNav(nav);
    }
  }

  function boot() {
    buildActivityNavFromShellCatalog()
      .then(() => loadHome())
      .catch(() => {
        const nav = qs("#v2-activity-nav");
        if (nav) buildFallbackNav(nav);
        return loadHome();
      });

    const closeBtn = qs("[data-inspector-close]");
    if (closeBtn) closeBtn.addEventListener("click", closeInspector);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
