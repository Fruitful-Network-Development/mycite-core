/**
 * V2 portal: renders shell chrome from runtime-issued shell_composition only.
 * Dispatches navigation via the page-selected shell endpoint using server-provided shell_request bodies.
 * Tool writes use submit_contract routes from the inspector region only.
 */
(function () {
  const BODY_DATA = document.body || document.documentElement;
  const SHELL_URL = (BODY_DATA && BODY_DATA.getAttribute("data-shell-endpoint")) || "/portal/api/v2/admin/shell";
  const RUNTIME_ENVELOPE_SCHEMA =
    (BODY_DATA && BODY_DATA.getAttribute("data-runtime-envelope-schema")) ||
    "mycite.v2.admin.runtime.envelope.v1";
  let lastShellRequest = null;
  let lastComposition = null;

  function cloneRequestWithoutChrome(req) {
    var next = JSON.parse(JSON.stringify(req || {}));
    delete next.shell_chrome;
    return next;
  }

  function postShellChrome(chromePartial) {
    if (!lastShellRequest) return Promise.resolve();
    var next = JSON.parse(JSON.stringify(lastShellRequest));
    next.shell_chrome = Object.assign({}, next.shell_chrome || {}, chromePartial);
    return loadShell(next);
  }

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function readBootstrapRequest() {
    const el = document.getElementById("v2-bootstrap-shell-request");
    if (!el || !el.textContent) return null;
    try {
      return JSON.parse(el.textContent);
    } catch {
      return null;
    }
  }

  function postJson(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(function (r) {
      return r.text().then(function (text) {
        var j = null;
        try {
          j = text ? JSON.parse(text) : null;
        } catch (_) {
          j = null;
        }
        return {
          ok: r.ok,
          status: r.status,
          json: j,
          bodySnippet: text ? text.slice(0, 280) : "",
        };
      });
    });
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function applyChrome(comp) {
    var el = qs(".ide-shell");
    if (!el || !comp) return;
    el.setAttribute("data-active-service", comp.active_service || "system");
    el.setAttribute("data-shell-composition", comp.composition_mode || "system");
    el.setAttribute("data-foreground-shell-region", comp.foreground_shell_region || "center-workbench");
    el.setAttribute("data-control-panel-collapsed", comp.control_panel_collapsed ? "true" : "false");
    el.setAttribute("data-inspector-collapsed", comp.inspector_collapsed ? "true" : "false");
    if (comp.active_tool_slice_id) {
      el.setAttribute("data-active-mediate-tool", comp.active_tool_slice_id);
    } else {
      el.removeAttribute("data-active-mediate-tool");
    }

    var menubarTitle = qs(".ide-menubar__pageTitle");
    var menubarSub = qs(".ide-menubar__pageSub");
    if (menubarTitle && comp.page_title) menubarTitle.textContent = comp.page_title;
    if (menubarSub && comp.page_subtitle != null) menubarSub.textContent = comp.page_subtitle;

    var pageheadTitle = qs("#v2-workbench-title");
    var pageheadSub = qs("#v2-workbench-subtitle");
    var wbRegion = comp.regions && comp.regions.workbench;
    if (pageheadTitle && wbRegion && wbRegion.title) pageheadTitle.textContent = wbRegion.title;
    if (pageheadSub && wbRegion && wbRegion.subtitle != null) pageheadSub.textContent = wbRegion.subtitle;

    var wb = qs(".ide-workbench");
    if (wb) {
      var tool = comp.composition_mode === "tool";
      wb.setAttribute("data-foreground-visible", tool ? "false" : "true");
      wb.setAttribute("aria-hidden", tool ? "true" : "false");
    }

    var insp = document.getElementById("portalInspector");
    if (insp) {
      var collapsed = !!comp.inspector_collapsed;
      insp.classList.toggle("is-collapsed", collapsed);
      insp.setAttribute("aria-hidden", collapsed ? "true" : "false");
      insp.setAttribute("data-primary-surface", comp.composition_mode === "tool" ? "true" : "false");
      insp.setAttribute("data-surface-layout", comp.composition_mode === "tool" ? "primary-fill" : "sidebar");
    }
  }

  function renderActivityItems(items) {
    var nav = document.getElementById("v2-activity-nav");
    if (!nav) return;
    if (!items || !items.length) {
      nav.innerHTML =
        '<p class="ide-sessionLine ide-sessionLine--dim" style="padding:8px;text-align:center;font-size:10px">No activity items from shell composition.</p>';
      return;
    }
    nav.innerHTML = "";
    items.forEach(function (item) {
      var a = document.createElement("a");
      a.className = "ide-activitylink" + (item.active ? " is-active" : "");
      a.href = "#";
      a.setAttribute("aria-label", item.label || "");
      var label = (item.label || "").toUpperCase();
      a.innerHTML = "<span>" + escapeHtml(label.length > 22 ? label.slice(0, 20) + "…" : label) + "</span>";
      a.addEventListener("click", function (e) {
        e.preventDefault();
        if (!item.shell_request) return;
        loadShell(item.shell_request);
      });
      nav.appendChild(a);
    });
  }

  function renderControlPanel(region) {
    var root = document.getElementById("portalControlPanel");
    if (!root || !region || !region.sections) return;
    root.innerHTML = "";
    region.sections.forEach(function (sec) {
      var section = document.createElement("section");
      section.className = "ide-controlpanel__section";
      var h = document.createElement("header");
      h.className = "ide-controlpanel__title";
      h.textContent = sec.title || "";
      section.appendChild(h);
      var entries = sec.entries || [];
      if (!entries.length) {
        var empty = document.createElement("div");
        empty.className = "ide-controlpanel__empty";
        empty.textContent = "No entries";
        section.appendChild(empty);
      } else {
        var ul = document.createElement("ul");
        ul.className = "ide-controlpanel__list";
        entries.forEach(function (ent) {
          var li = document.createElement("li");
          var link = document.createElement("a");
          link.className = "ide-controlpanel__link" + (ent.active ? " is-active" : "");
          link.href = "#";
          var span = document.createElement("span");
          span.textContent = ent.label || "";
          link.appendChild(span);
          if (ent.meta) {
            var sm = document.createElement("small");
            sm.textContent = ent.meta;
            link.appendChild(sm);
          }
          if (ent.gated) {
            link.classList.add("is-gated");
            link.setAttribute("aria-disabled", "true");
          }
          link.addEventListener("click", function (e) {
            e.preventDefault();
            if (ent.shell_request) loadShell(ent.shell_request);
          });
          li.appendChild(link);
          ul.appendChild(li);
        });
        section.appendChild(ul);
      }
      root.appendChild(section);
    });
  }

  function renderWorkbench(wb) {
    var body = document.getElementById("v2-workbench-body");
    if (!body || !wb) {
      return;
    }
    var kind = wb.kind || "empty";
    if (kind === "hidden" || wb.visible === false) {
      body.innerHTML = '<p class="ide-controlpanel__empty">Workbench hidden for this shell mode.</p>';
      return;
    }
    if (kind === "error") {
      body.innerHTML =
        '<div class="v2-card"><h3>' +
        escapeHtml(wb.title || "Error") +
        "</h3><p>" +
        escapeHtml(wb.message || "") +
        "</p></div>";
      return;
    }
    if (kind === "home_summary") {
      var blocks = wb.blocks || [];
      var cards =
        '<div class="v2-card-grid">' +
        blocks
          .map(function (b) {
            return (
              '<article class="v2-card"><h3>' +
              escapeHtml(b.label || "") +
              "</h3><p>" +
              escapeHtml(String(b.value != null ? b.value : "—")) +
              "</p></article>"
            );
          })
          .join("") +
        "</div>";
      body.innerHTML = cards;
      return;
    }
    if (kind === "tenant_home_status") {
      var tenantProfile = wb.tenant_profile || {};
      var availableSlices = wb.available_slices || [];
      var warnings = wb.warnings || [];
      var warningBlock =
        warnings.length > 0
          ? '<div class="v2-card" style="margin-bottom:12px"><h3>Warnings</h3><ul>' +
            warnings
              .map(function (warning) {
                return "<li>" + escapeHtml(String(warning)) + "</li>";
              })
              .join("") +
            "</ul></div>"
          : "";
      var cards =
        '<div class="v2-card-grid">' +
        '<article class="v2-card"><h3>You are here</h3><p>' +
        escapeHtml(wb.where_you_are || "Portal home") +
        "</p></article>" +
        '<article class="v2-card"><h3>Rollout band</h3><p>' +
        escapeHtml(wb.rollout_band || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Exposure</h3><p>' +
        escapeHtml(wb.exposure_status || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Profile in view</h3><p>' +
        escapeHtml(tenantProfile.profile_title || "—") +
        "</p></article>" +
        "</div>";
      var details =
        '<dl class="v2-surface-dl">' +
        "<dt>Tenant</dt><dd>" +
        escapeHtml(tenantProfile.tenant_id || "—") +
        "</dd>" +
        "<dt>Domain</dt><dd>" +
        escapeHtml(tenantProfile.tenant_domain || "—") +
        "</dd>" +
        "<dt>Entity type</dt><dd>" +
        escapeHtml(tenantProfile.entity_type || "—") +
        "</dd>" +
        "<dt>Profile summary</dt><dd>" +
        escapeHtml(tenantProfile.profile_summary || "—") +
        "</dd>" +
        "<dt>Contact email</dt><dd>" +
        escapeHtml(tenantProfile.contact_email || "—") +
        "</dd>" +
        "<dt>Public website</dt><dd>" +
        escapeHtml(tenantProfile.public_website_url || "—") +
        "</dd>" +
        "<dt>Publication mode</dt><dd>" +
        escapeHtml(tenantProfile.publication_mode || "—") +
        "</dd>" +
        "<dt>Profile resolution</dt><dd>" +
        escapeHtml(tenantProfile.profile_resolution || "—") +
        "</dd>" +
        "<dt>Available documents</dt><dd>" +
        escapeHtml((tenantProfile.available_documents || []).join(", ") || "—") +
        "</dd></dl>";
      var slicesHtml =
        "<table class=\"v2-table\"><thead><tr><th>Slice</th><th>Status</th><th>Posture</th></tr></thead><tbody>" +
        availableSlices
          .map(function (slice) {
            return (
              "<tr><td>" +
              escapeHtml(slice.label || slice.slice_id || "") +
              "</td><td>" +
              escapeHtml(slice.status_summary || "—") +
              "</td><td>" +
              escapeHtml(slice.read_write_posture || "—") +
              "</td></tr>"
            );
          })
          .join("") +
        "</tbody></table>";
      body.innerHTML = warningBlock + cards + details + '<div class="v2-card" style="margin-top:12px"><h3>Available slices</h3>' + slicesHtml + "</div>";
      return;
    }
    if (kind === "operational_status") {
      var auditPersistence = wb.audit_persistence || {};
      var statusWarnings = wb.warnings || [];
      var statusSlices = wb.available_slices || [];
      var statusWarningBlock =
        statusWarnings.length > 0
          ? '<div class="v2-card" style="margin-bottom:12px"><h3>Warnings</h3><ul>' +
            statusWarnings
              .map(function (warning) {
                return "<li>" + escapeHtml(String(warning)) + "</li>";
              })
              .join("") +
            "</ul></div>"
          : "";
      var statusCards =
        '<div class="v2-card-grid">' +
        '<article class="v2-card"><h3>Rollout band</h3><p>' +
        escapeHtml(wb.current_rollout_band || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Exposure</h3><p>' +
        escapeHtml(wb.exposure_status || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Read/write posture</h3><p>' +
        escapeHtml(wb.read_write_posture || "—") +
        "</p></article>" +
        '<article class="v2-card"><h3>Audit health</h3><p>' +
        escapeHtml(String(auditPersistence.health_state || "—").replace(/_/g, " ")) +
        "</p></article>" +
        "</div>";
      var statusDetails =
        '<dl class="v2-surface-dl">' +
        "<dt>Storage state</dt><dd>" +
        escapeHtml(String(auditPersistence.storage_state || "—").replace(/_/g, " ")) +
        "</dd>" +
        "<dt>Recent window limit</dt><dd>" +
        escapeHtml(String(auditPersistence.recent_window_limit != null ? auditPersistence.recent_window_limit : "—")) +
        "</dd>" +
        "<dt>Recent record count</dt><dd>" +
        escapeHtml(String(auditPersistence.recent_record_count != null ? auditPersistence.recent_record_count : "—")) +
        "</dd>" +
        "<dt>Latest persisted at</dt><dd>" +
        escapeHtml(
          String(
            auditPersistence.latest_recorded_at_unix_ms != null
              ? auditPersistence.latest_recorded_at_unix_ms
              : "—"
          )
        ) +
        "</dd></dl>";
      var statusTable =
        "<table class=\"v2-table\"><thead><tr><th>Slice</th><th>Status</th><th>Posture</th></tr></thead><tbody>" +
        statusSlices
          .map(function (slice) {
            return (
              "<tr><td>" +
              escapeHtml(slice.label || slice.slice_id || "") +
              "</td><td>" +
              escapeHtml(slice.status_summary || "—") +
              "</td><td>" +
              escapeHtml(slice.read_write_posture || "—") +
              "</td></tr>"
            );
          })
          .join("") +
        "</tbody></table>";
      body.innerHTML =
        statusWarningBlock +
        statusCards +
        statusDetails +
        '<div class="v2-card" style="margin-top:12px"><h3>Visible slices</h3>' +
        statusTable +
        "</div>";
      return;
    }
    if (kind === "tool_registry") {
      var rows = wb.tool_rows || [];
      var banner = wb.banner;
      var bannerHtml = "";
      if (banner && banner.message) {
        bannerHtml =
          '<div class="v2-card" style="border-color:#c5221f;margin-bottom:12px"><p><strong>' +
          escapeHtml(banner.code || "notice") +
          ":</strong> " +
          escapeHtml(banner.message) +
          "</p></div>";
      }
      var table =
        "<table class=\"v2-table\"><thead><tr><th>Tool</th><th>Slice</th><th>Entrypoint</th></tr></thead><tbody>" +
        rows
          .map(function (row) {
            return (
              "<tr><td>" +
              escapeHtml(row.label || row.tool_id || "") +
              "</td><td><code>" +
              escapeHtml(row.slice_id || "") +
              "</code></td><td><code>" +
              escapeHtml(row.entrypoint_id || "") +
              "</code></td></tr>"
            );
          })
          .join("") +
        "</tbody></table>";
      body.innerHTML = bannerHtml + table;
      return;
    }
    if (kind === "datum_workbench") {
      var summ = wb.summary || {};
      var warns = wb.warnings || [];
      var warnBlock =
        warns.length > 0
          ? '<div class="v2-card" style="margin-bottom:12px"><h3>Warnings</h3><ul>' +
            warns.map(function (w) {
              return "<li>" + escapeHtml(String(w)) + "</li>";
            }).join("") +
            "</ul></div>"
          : "";
      var meta =
        '<div class="v2-card-grid">' +
        '<article class="v2-card"><h3>Rows</h3><p>' +
        escapeHtml(String(summ.row_count != null ? summ.row_count : "—")) +
        "</p></article>" +
        '<article class="v2-card"><h3>OK</h3><p>' +
        escapeHtml(String(summ.ok != null ? summ.ok : "—")) +
        "</p></article>" +
        '<article class="v2-card"><h3>Tenant</h3><p>' +
        escapeHtml(String(summ.tenant_id || "—")) +
        "</p></article></div>";
      var preview = wb.rows_preview || [];
      var table =
        "<table class=\"v2-table\"><thead><tr><th>Resource</th><th>Subject</th><th>Relation</th><th>Object</th></tr></thead><tbody>" +
        preview
          .map(function (row) {
            return (
              "<tr><td><code>" +
              escapeHtml(String((row && row.resource_id) || "")) +
              "</code></td><td>" +
              escapeHtml(String((row && row.subject_ref) || "")) +
              "</td><td>" +
              escapeHtml(String((row && row.relation) || "")) +
              "</td><td>" +
              escapeHtml(String((row && row.object_ref) || "")) +
              "</td></tr>"
            );
          })
          .join("") +
        "</tbody></table>";
      body.innerHTML = warnBlock + meta + table;
      return;
    }
    if (kind === "tool_collapsed_inspector") {
      body.innerHTML =
        '<div class="v2-card"><h3>' +
        escapeHtml(wb.title || "Tool") +
        "</h3><p>" +
        escapeHtml(wb.subtitle || "") +
        "</p></div>";
      return;
    }
    if (kind === "tool_placeholder") {
      body.innerHTML = '<p class="ide-controlpanel__empty">' + escapeHtml(wb.subtitle || "") + "</p>";
      return;
    }
    body.innerHTML = '<pre class="v2-json-panel">' + escapeHtml(JSON.stringify(wb, null, 2)) + "</pre>";
  }

  function renderInspector(region) {
    var titleEl = document.getElementById("portalInspectorTitle");
    var content = document.getElementById("v2-inspector-dynamic");
    if (!region) {
      if (titleEl) titleEl.textContent = "Overview";
      if (content) content.innerHTML = "";
      return;
    }
    if (titleEl) titleEl.textContent = region.title || "Interface panel";
    if (!content) return;
    var kind = region.kind || "empty";
    if (kind === "empty") {
      content.innerHTML = "<p class=\"ide-inspector__empty\">" + escapeHtml(region.body_text || "") + "</p>";
      return;
    }
    if (kind === "json_document") {
      content.innerHTML =
        '<pre class="v2-json-panel">' + escapeHtml(JSON.stringify(region.document || {}, null, 2)) + "</pre>";
      return;
    }
    if (kind === "aws_read_only_surface") {
      var ps = region.profile_summary || {};
      var doms = (region.allowed_send_domains || []).join(", ");
      var cw = (region.compatibility_warnings || [])
        .map(function (w) {
          return "<li>" + escapeHtml(String(w)) + "</li>";
        })
        .join("");
      content.innerHTML =
        '<dl class="v2-surface-dl">' +
        "<dt>Tenant scope</dt><dd>" +
        escapeHtml(region.tenant_scope_id || "—") +
        "</dd>" +
        "<dt>Mailbox readiness</dt><dd>" +
        escapeHtml(region.mailbox_readiness || "—") +
        "</dd>" +
        "<dt>SMTP</dt><dd>" +
        escapeHtml(region.smtp_state || "—") +
        "</dd>" +
        "<dt>Gmail</dt><dd>" +
        escapeHtml(region.gmail_state || "—") +
        "</dd>" +
        "<dt>Verified sender</dt><dd><code>" +
        escapeHtml(region.selected_verified_sender || "") +
        "</code></dd>" +
        "<dt>Allowed send domains</dt><dd>" +
        escapeHtml(doms || "—") +
        "</dd>" +
        "<dt>Profile</dt><dd>" +
        escapeHtml(ps.profile_id || "—") +
        " · " +
        escapeHtml(ps.domain || "—") +
        "</dd>" +
        "<dt>Write capability</dt><dd>" +
        escapeHtml(region.write_capability || "—") +
        "</dd></dl>" +
        (cw ? "<section class=\"v2-card\" style=\"margin-top:12px\"><h3>Compatibility</h3><ul>" + cw + "</ul></section>" : "");
      return;
    }
    if (kind === "aws_tool_error") {
      var wn = (region.warnings || [])
        .map(function (w) {
          return "<li>" + escapeHtml(String(w)) + "</li>";
        })
        .join("");
      content.innerHTML =
        '<div class="v2-card" style="border-color:#c5221f"><h3>' +
        escapeHtml(region.error_code || "error") +
        "</h3><p>" +
        escapeHtml(region.error_message || "") +
        "</p>" +
        (wn ? "<ul>" + wn + "</ul>" : "") +
        "</div>";
      return;
    }
    if (kind === "tenant_profile_summary") {
      var summary = region.summary || {};
      content.innerHTML =
        '<dl class="v2-surface-dl">' +
        "<dt>Profile title</dt><dd>" +
        escapeHtml(summary.profile_title || "—") +
        "</dd>" +
        "<dt>Tenant</dt><dd>" +
        escapeHtml(summary.tenant_id || "—") +
        "</dd>" +
        "<dt>Domain</dt><dd>" +
        escapeHtml(summary.tenant_domain || "—") +
        "</dd>" +
        "<dt>Entity type</dt><dd>" +
        escapeHtml(summary.entity_type || "—") +
        "</dd>" +
        "<dt>Profile summary</dt><dd>" +
        escapeHtml(summary.profile_summary || "—") +
        "</dd>" +
        "<dt>Contact email</dt><dd>" +
        escapeHtml(summary.contact_email || "—") +
        "</dd>" +
        "<dt>Public website</dt><dd>" +
        escapeHtml(summary.public_website_url || "—") +
        "</dd>" +
        "<dt>Available documents</dt><dd>" +
        escapeHtml((summary.available_documents || []).join(", ") || "—") +
        "</dd></dl>";
      return;
    }
    if (kind === "operational_status_summary") {
      var operational = region.audit_persistence || {};
      content.innerHTML =
        '<dl class="v2-surface-dl">' +
        "<dt>Rollout band</dt><dd>" +
        escapeHtml(region.current_rollout_band || "—") +
        "</dd>" +
        "<dt>Exposure</dt><dd>" +
        escapeHtml(region.exposure_status || "—") +
        "</dd>" +
        "<dt>Read/write posture</dt><dd>" +
        escapeHtml(region.read_write_posture || "—") +
        "</dd>" +
        "<dt>Audit health</dt><dd>" +
        escapeHtml(String(operational.health_state || "—").replace(/_/g, " ")) +
        "</dd>" +
        "<dt>Storage state</dt><dd>" +
        escapeHtml(String(operational.storage_state || "—").replace(/_/g, " ")) +
        "</dd>" +
        "<dt>Recent records</dt><dd>" +
        escapeHtml(String(operational.recent_record_count != null ? operational.recent_record_count : "—")) +
        "</dd>" +
        "<dt>Latest persisted at</dt><dd>" +
        escapeHtml(
          String(
            operational.latest_recorded_at_unix_ms != null
              ? operational.latest_recorded_at_unix_ms
              : "—"
          )
        ) +
        "</dd></dl>";
      return;
    }
    if (kind === "narrow_write_form") {
      var contract = region.submit_contract || {};
      var initial = contract.initial_values || {};
      var fixed = contract.fixed_request_fields || {};
      var html =
        '<form id="v2-narrow-write-form" class="v2-card" style="max-width:520px">' +
        "<h3>Bounded write</h3>" +
        '<p class="ide-controlpanel__empty" style="margin:0 0 10px">Request schema: <code>' +
        escapeHtml(contract.request_schema || "") +
        "</code></p>" +
        '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">profile_id</label>' +
        '<input name="profile_id" value="' +
        escapeHtml(initial.profile_id || "") +
        '" style="width:100%;box-sizing:border-box;margin-bottom:10px;padding:6px 8px" />' +
        '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">selected_verified_sender</label>' +
        '<input name="selected_verified_sender" value="' +
        escapeHtml(initial.selected_verified_sender || "") +
        '" style="width:100%;box-sizing:border-box;margin-bottom:12px;padding:6px 8px" />' +
        '<button type="submit" class="ide-sessionAction ide-sessionAction--button" style="border-radius:6px">Apply narrow write</button>' +
        "</form>" +
        '<pre id="v2-narrow-write-result" class="v2-json-panel" style="margin-top:12px" hidden></pre>';
      content.innerHTML = html;
      var form = document.getElementById("v2-narrow-write-form");
      var out = document.getElementById("v2-narrow-write-result");
      if (form && out) {
        form.addEventListener("submit", function (ev) {
          ev.preventDefault();
          var fd = new FormData(form);
          var body = {
            schema: contract.request_schema,
            profile_id: (fd.get("profile_id") || "").toString().trim(),
            selected_verified_sender: (fd.get("selected_verified_sender") || "").toString().trim(),
          };
          if (fixed.focus_subject != null) body.focus_subject = fixed.focus_subject;
          if (fixed.tenant_scope) body.tenant_scope = fixed.tenant_scope;
          out.hidden = false;
          out.textContent = "…";
          postJson(contract.route || "/portal/api/v2/admin/aws/narrow-write", body).then(function (res) {
            out.textContent = JSON.stringify(res.json, null, 2);
            if (lastShellRequest) loadShell(cloneRequestWithoutChrome(lastShellRequest));
          });
        });
      }
      return;
    }
    if (kind === "csm_onboarding_form") {
      var contract = region.submit_contract || {};
      var initial = contract.initial_values || {};
      var fixed = contract.fixed_request_fields || {};
      var options = contract.onboarding_action_options || [];
      var optHtml = options
        .map(function (a) {
          return (
            '<option value="' +
            escapeHtml(a) +
            '"' +
            (a === (initial.onboarding_action || "") ? " selected" : "") +
            ">" +
            escapeHtml(a) +
            "</option>"
          );
        })
        .join("");
      var html =
        '<form id="v2-csm-onboarding-form" class="v2-card" style="max-width:560px">' +
        "<h3>AWS-CSM onboarding</h3>" +
        '<p class="ide-controlpanel__empty" style="margin:0 0 10px">Request schema: <code>' +
        escapeHtml(contract.request_schema || "") +
        "</code></p>" +
        '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">onboarding_action</label>' +
        '<select name="onboarding_action" style="width:100%;box-sizing:border-box;margin-bottom:10px;padding:6px 8px">' +
        optHtml +
        "</select>" +
        '<label class="ide-controlpanel__empty" style="display:block;margin-bottom:4px">profile_id</label>' +
        '<input name="profile_id" value="' +
        escapeHtml(initial.profile_id || "") +
        '" style="width:100%;box-sizing:border-box;margin-bottom:12px;padding:6px 8px" />' +
        '<button type="submit" class="ide-sessionAction ide-sessionAction--button" style="border-radius:6px">Apply onboarding step</button>' +
        "</form>" +
        '<pre id="v2-csm-onboarding-result" class="v2-json-panel" style="margin-top:12px" hidden></pre>';
      content.innerHTML = html;
      var form = document.getElementById("v2-csm-onboarding-form");
      var out = document.getElementById("v2-csm-onboarding-result");
      if (form && out) {
        form.addEventListener("submit", function (ev) {
          ev.preventDefault();
          var fd = new FormData(form);
          var body = {
            schema: contract.request_schema,
            profile_id: (fd.get("profile_id") || "").toString().trim(),
            onboarding_action: (fd.get("onboarding_action") || "").toString().trim(),
          };
          if (fixed.focus_subject != null) body.focus_subject = fixed.focus_subject;
          if (fixed.tenant_scope) body.tenant_scope = fixed.tenant_scope;
          out.hidden = false;
          out.textContent = "…";
          postJson(contract.route || "/portal/api/v2/admin/aws/csm-onboarding", body).then(function (res) {
            out.textContent = JSON.stringify(res.json, null, 2);
            if (lastShellRequest) loadShell(cloneRequestWithoutChrome(lastShellRequest));
          });
        });
      }
      return;
    }
    content.innerHTML = '<pre class="v2-json-panel">' + escapeHtml(JSON.stringify(region, null, 2)) + "</pre>";
  }

  function showFatal(message) {
    var nav = document.getElementById("v2-activity-nav");
    if (nav) {
      nav.innerHTML =
        '<p class="ide-sessionLine" style="padding:8px;color:#c5221f;font-size:10px;text-align:center">' +
        escapeHtml(message) +
        "</p>";
    }
    var body = document.getElementById("v2-workbench-body");
    if (body) {
      body.innerHTML = "<p>" + escapeHtml(message) + "</p>";
    }
  }

  function loadShell(requestBody) {
    lastShellRequest = requestBody;
    return postJson(SHELL_URL, requestBody).then(function (r) {
      var env = r.json;
      if (!r.ok || !env) {
        showFatal(
          "Shell POST failed (HTTP " +
            r.status +
            "). Check auth, nginx upstream (6101), and service logs. " +
            (r.bodySnippet ? "Body: " + r.bodySnippet : "")
        );
        return;
      }
      if (env.schema !== RUNTIME_ENVELOPE_SCHEMA) {
        showFatal("Invalid runtime envelope schema from shell route.");
        return;
      }
      var comp = env.shell_composition;
      if (!comp || !comp.regions) {
        showFatal("Runtime envelope is missing shell_composition.regions.");
        return;
      }
      applyChrome(comp);
      lastComposition = comp;
      if (window.PortalShell && typeof window.PortalShell.rebalanceWorkbench === "function") {
        window.PortalShell.rebalanceWorkbench();
      }
      var act = comp.regions.activity_bar || {};
      renderActivityItems(act.items);
      renderControlPanel(comp.regions.control_panel);
      renderWorkbench(comp.regions.workbench);
      renderInspector(comp.regions.inspector);
      return env;
    });
  }

  function boot() {
    var bootstrap = readBootstrapRequest();
    if (!bootstrap) {
      showFatal("Missing server bootstrap shell request.");
      return;
    }
    loadShell(bootstrap).catch(function () {
      showFatal("Shell request failed.");
    });

    document.addEventListener("mycite:v2:inspector-dismiss-request", function () {
      postShellChrome({ inspector_collapsed: true });
    });
    document.addEventListener("mycite:v2:inspector-toggle-request", function () {
      var collapsed = !!(lastComposition && lastComposition.inspector_collapsed);
      postShellChrome({ inspector_collapsed: !collapsed });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
